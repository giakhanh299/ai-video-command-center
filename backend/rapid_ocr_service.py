"""RapidOCR integration for ultra-fast, pinpoint text detection and bounding box masking."""
import sys
import re
import cv2
import numpy as np
from pathlib import Path

_engine = None

def get_rapid_ocr():
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            import os, site
            roaming_site = os.path.expandvars(r"%APPDATA%\Python\Python310\site-packages")
            if os.path.exists(roaming_site):
                site.addsitedir(roaming_site)
            from rapidocr_onnxruntime import RapidOCR
        # Bound CPU threads; the default creates several all-core ONNX pools.
        # A cropped subtitle strip must be limited by its longest edge instead
        # of being enlarged until its short edge reaches 736px.
        _engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1,
                           det_limit_type='max', det_limit_side_len=1280)
    return _engine


def scan_rapid_ocr_boxes(video_path: str, max_samples: int = 35) -> list[dict]:
    """Quét video bằng RapidOCR để tìm tọa độ chuẩn xác các dải chữ (Subtitle & Watermark).
    
    Returns:
        list[dict(zone, x, y, w, h, center_y)]
    """
    engine = get_rapid_ocr()
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1080
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1920
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    dur = total_frames / fps if fps > 0 else 0

    if dur > 5.0:
        early = list(range(1, min(int(dur), 90), 3))
        later = [int(x) for x in np.linspace(90, max(90, dur - 4), 15)]
        probe_ts = sorted(list(set(early + later)))[:max_samples]
    else:
        probe_ts = [1.0, 2.0, 3.0]

    y_crop_start = int(h * 0.45)
    all_detections = []

    try:
        for ts in probe_ts:
            cap.set(cv2.CAP_PROP_POS_MSEC, float(ts) * 1000.0)
            ok, frame = cap.read()
            if not ok:
                continue
            crop = frame[y_crop_start:, :]
            res, _ = engine(crop)
            if not res:
                continue
            for pts, txt, score in res:
                if score < 0.25:
                    continue
                # Exclude standalone English sports/fashion prints on clothing if isolated
                xs = [p[0] for p in pts]
                ys = [p[1] + y_crop_start for p in pts]
                bx = int(min(xs))
                by = int(min(ys))
                bw = int(max(xs) - min(xs))
                bh = int(max(ys) - min(ys))
                cy = (by + by + bh) / 2.0
                all_detections.append({
                    'ts': ts,
                    'txt': txt,
                    'score': float(score),
                    'x': bx,
                    'y': by,
                    'w': bw,
                    'h': bh,
                    'cy': cy,
                    'rel_cy': cy / h
                })
    finally:
        cap.release()

    if not all_detections:
        return []

    # Filter into Subtitle zone and Watermark zone
    sub_dets = [d for d in all_detections if 0.50 <= d['rel_cy'] < 0.76]
    wm_dets = [d for d in all_detections if d['rel_cy'] >= 0.76]

    boxes = []

    if sub_dets:
        # Dialogue subtitle baseline clustering
        cys = [d['cy'] for d in sub_dets]
        med_cy = sorted(cys)[len(cys) // 2]
        inliers = [d for d in sub_dets if abs(d['cy'] - med_cy) <= max(40, h * 0.05)]
        if not inliers:
            inliers = sub_dets

        x1 = min(d['x'] for d in inliers)
        y1 = min(d['y'] for d in inliers)
        x2 = max(d['x'] + d['w'] for d in inliers)
        y2 = max(d['y'] + d['h'] for d in inliers)

        # Đặt dải mờ Gaussian đối xứng chính giữa tâm dòng chữ Trung (med_cy)
        max_detected_h = max(d['h'] for d in inliers)
        target_box_h = min(120, max(88, int(round(max_detected_h + 24))))
        
        by = max(0, int(round((med_cy - target_box_h / 2.0) // 2) * 2))
        bh = int(round(target_box_h // 2) * 2)

        # Chiều rộng dải mờ: phủ rộng đối xứng toàn bộ vùng thoại để che sạch các câu dài
        bw = min(w - 48, max(int(w * 0.90), int(round((x2 - x1) + 80))))
        bx = max(0, ((w - bw) // 2 // 2) * 2)

        boxes.append({
            'zone': 'subtitle',
            'x': bx,
            'y': by,
            'w': bw,
            'h': bh,
            'center_y': by + bh / 2.0,
            'count': len(inliers)
        })
        print(f"[RapidOCR] Subtitle box (Gọn gàng): x={bx} y={by} w={bw} h={bh} (CenterY={by+bh/2.0:.1f}) [count={len(inliers)}]")

    if wm_dets:
        # Watermark/brand logo at bottom: chỉ gom cụm logo sát đáy thật sự
        cys = [d['cy'] for d in wm_dets]
        med_cy = sorted(cys)[len(cys) // 2]
        # Giới hạn sai lệch chặt chẽ <= 35px để không gom nhầm chữ trên quần áo
        inliers = [d for d in wm_dets if abs(d['cy'] - med_cy) <= 35]
        if inliers and len(inliers) >= 3:
            x1 = min(d['x'] for d in inliers)
            y1 = min(d['y'] for d in inliers)
            x2 = max(d['x'] + d['w'] for d in inliers)
            y2 = max(d['y'] + d['h'] for d in inliers)

            pad_v = 4
            pad_h = 16

            bx = max(0, ((x1 - pad_h) // 2) * 2)
            by = max(0, ((y1 - pad_v) // 2) * 2)
            bw = min(w - bx, (((x2 + pad_h) - (x1 - pad_h)) // 2) * 2)
            bh = min(h - by, (((y2 + pad_v) - (y1 - pad_v)) // 2) * 2)

            # Giới hạn chiều cao logo đáy tối đa 76px
            MAX_WM_H = 76
            if bh > MAX_WM_H:
                diff = bh - MAX_WM_H
                by += (diff // 2 // 2) * 2
                bh = MAX_WM_H

            boxes.append({
                'zone': 'watermark',
                'x': bx,
                'y': by,
                'w': bw,
                'h': bh,
                'center_y': by + bh / 2.0,
                'count': len(inliers)
            })
            print(f"[RapidOCR] Watermark box (Gọn gàng): x={bx} y={by} w={bw} h={bh} (CenterY={by+bh/2.0:.1f}) [count={len(inliers)}]")

    return boxes
