"""Dịch vụ nhận diện & tạo Title Card / Banner cho đoạn đầu video (Chị Đẹp Đi Câu / Cấu hình 2)."""
import os
import re
import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def get_vietnamese_font(size: int = 48, bold: bool = True):
    font_candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahomabd.ttf" if bold else "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for p in font_candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uac00-\ud7a3]')


def _iou(a, b) -> float:
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    ix = max(0, min(ax2, bx2) - max(a["x"], b["x"]))
    iy = max(0, min(ay2, by2) - max(a["y"], b["y"]))
    inter = ix * iy
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / union if union > 0 else 0.0


def scan_intro_text_tracks(video_path: str, step_sec: float = 0.5, min_scan_sec: float = 3.0,
                           max_scan_sec: float = 8.0) -> list[dict] | None:
    """Quét OCR TOÀN MÀN HÌNH giai đoạn đầu video, theo dõi từng cụm chữ theo thời gian.

    Trả về list track {x,y,w,h,t_start,t_end,text,persistent} (toạ độ khung gốc),
    hoặc None nếu không có RapidOCR (để fallback sang dò màu).
    """
    try:
        try:
            from .rapid_ocr_service import get_rapid_ocr
        except ImportError:
            from rapid_ocr_service import get_rapid_ocr
        engine = get_rapid_ocr()
    except Exception as ocr_err:
        print(f"[IntroScan] RapidOCR không khả dụng ({ocr_err}), fallback dò màu.")
        return None

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1080
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1920
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    dur = (cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / fps if fps > 0 else 0
    if dur > 0:
        max_scan_sec = min(max_scan_sec, max(0.0, dur - 0.1))
    scale = 720.0 / w if w > 720 else 1.0

    tracks: list[dict] = []
    t = 0.0
    last_t = 0.0
    try:
        while t <= max_scan_sec + 1e-6:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ok, frame = cap.read()
            if not ok:
                break
            last_t = t
            small = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale != 1.0 else frame
            result, _ = engine(small)
            for item in (result or []):
                pts, text, conf = item[0], str(item[1]), float(item[2])
                if conf < 0.5 or not _CJK_RE.search(text):
                    continue
                xs = [p[0] / scale for p in pts]
                ys = [p[1] / scale for p in pts]
                box = {"x": int(min(xs)), "y": int(min(ys)),
                       "w": int(max(xs) - min(xs)), "h": int(max(ys) - min(ys))}
                if box["h"] < h * 0.012:
                    continue
                match = next((tr for tr in tracks if tr["t_last"] >= t - step_sec - 1e-6 and _iou(tr, box) > 0.3), None)
                if match:
                    # Gộp toạ độ (union) để che đủ cả khi chữ có hiệu ứng phóng to/nhảy nhẹ
                    x2 = max(match["x"] + match["w"], box["x"] + box["w"])
                    y2 = max(match["y"] + match["h"], box["y"] + box["h"])
                    match["x"], match["y"] = min(match["x"], box["x"]), min(match["y"], box["y"])
                    match["w"], match["h"] = x2 - match["x"], y2 - match["y"]
                    match["t_last"] = t
                else:
                    tracks.append({**box, "t_start": t, "t_last": t, "text": text})
            # Quét tối thiểu min_scan_sec; sau đó chỉ quét tiếp khi còn chữ chưa biến mất
            alive = any(tr["t_last"] >= t - 1e-6 for tr in tracks)
            if t >= min_scan_sec and not alive:
                break
            t = round(t + step_sec, 3)
    finally:
        cap.release()

    out = []
    for tr in tracks:
        persistent = tr["t_last"] >= last_t - 1e-6 and last_t >= min_scan_sec
        out.append({
            "x": tr["x"], "y": tr["y"], "w": tr["w"], "h": tr["h"],
            # Bắt đầu sớm hơn nửa bước, kết thúc trễ hơn 1 bước để không lọt frame chuyển tiếp
            "t_start": max(0.0, round(tr["t_start"] - step_sec / 2.0, 3)) if tr["t_start"] > 0 else 0.0,
            "t_end": round(tr["t_last"] + step_sec, 3),
            "text": tr["text"],
            "persistent": persistent,
            "center_y": tr["y"] + tr["h"] / 2.0,
        })
    print(f"[IntroScan] Quét toàn màn hình 0-{last_t:.1f}s: {len(out)} cụm chữ " +
          ", ".join(f"'{b['text']}'@y{b['y']} {b['t_start']}-{b['t_end']}s" for b in out))
    return out


def _intro_title_cluster(boxes: list[dict], vid_h: int) -> dict | None:
    """Chọn cụm tiêu đề chính: chữ xuất hiện sớm nhất (<=1s), gộp các dòng gần nhau, lấy cụm lớn nhất."""
    early = [b for b in boxes if b["t_start"] <= 1.0]
    if not early:
        return None
    early.sort(key=lambda b: b["y"])
    groups: list[list[dict]] = []
    for b in early:
        if groups:
            g = groups[-1]
            g_bottom = max(x["y"] + x["h"] for x in g)
            if b["y"] - g_bottom <= max(40, vid_h * 0.03):
                g.append(b)
                continue
        groups.append([b])
    best = max(groups, key=lambda g: sum(x["w"] * x["h"] for x in g))
    x1 = min(b["x"] for b in best); y1 = min(b["y"] for b in best)
    x2 = max(b["x"] + b["w"] for b in best); y2 = max(b["y"] + b["h"] for b in best)
    return {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1, "center_y": (y1 + y2) / 2.0,
            "t_end": max(b["t_end"] for b in best)}


def detect_intro_hook_info(video_path: str) -> dict:
    """Quét các frame đầu để nhận diện ảnh bìa ngắn + toàn bộ chữ tiêu đề/sticker (quét toàn màn hình)."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {
            "has_cover": False,
            "cut_ts": 0.15,
            "banner_box": {"x": 60, "y": 680, "w": 960, "h": 250},
            "sticker_box": None,
            "vid_w": 1080,
            "vid_h": 1920
        }

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1080
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1920
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    frames = []
    for _ in range(min(15, int(fps * 0.8))):
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()

    has_cover = False
    cut_ts = 0.15
    if len(frames) >= 4:
        # So sánh chênh lệch giữa frame 0 và frame 3 (0.1s) xem có đổi cảnh bìa Douyin
        diff_0_3 = cv2.absdiff(frames[0], frames[3]).mean()
        if diff_0_3 > 25.0:
            has_cover = True
            cut_ts = round(3.5 / fps, 3)

    # Ưu tiên: quét OCR toàn màn hình theo thời gian
    intro_boxes = scan_intro_text_tracks(video_path)
    sticker_box = None
    if intro_boxes is not None:
        # Bỏ dòng thoại cố định ở đáy (tồn tại suốt quá trình quét) - đã có dải blur phụ đề lo
        intro_boxes = [b for b in intro_boxes if not (b["persistent"] and b["center_y"] > h * 0.6)]
        sticker_box = _intro_title_cluster(intro_boxes, h)
    else:
        intro_boxes = []

    # Fallback khi không có OCR: dò màu vàng vùng giữa màn hình (25% - 52% chiều cao)
    if sticker_box is None and not intro_boxes and frames:
        candidate_boxes = []
        for f in frames[:3]:
            hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
            # Mask màu vàng rực (đặc trưng phụ đề/sticker Douyin)
            mask_yellow = cv2.inRange(hsv, (18, 100, 130), (35, 255, 255))
            roi_mask = np.zeros((h, w), dtype=np.uint8)
            roi_mask[int(h * 0.25):int(h * 0.52), int(w * 0.20):int(w * 0.80)] = 255
            y_roi = cv2.bitwise_and(mask_yellow, roi_mask)

            contours, _ = cv2.findContours(y_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                if cv2.contourArea(c) > 500:
                    bx, by, bw, bh = cv2.boundingRect(c)
                    candidate_boxes.append((bx, by, bw, bh))

        if candidate_boxes:
            y_min = min(b[1] for b in candidate_boxes)
            y_max = max(b[1] + b[3] for b in candidate_boxes)
            x_min = min(b[0] for b in candidate_boxes)
            x_max = max(b[0] + b[2] for b in candidate_boxes)
            sticker_box = {
                "x": x_min,
                "y": y_min,
                "w": x_max - x_min,
                "h": y_max - y_min,
                "center_y": (y_min + y_max) / 2.0,
                "t_end": 2.0
            }
            intro_boxes = [dict(sticker_box, t_start=0.0, text="", persistent=False)]

    # Tính kích thước và vị trí banner ôm sát cụm sticker
    bw = min(w - 60, int(w * 0.94))
    bh = 240
    bx = (w - bw) // 2

    if sticker_box:
        # Đặt banner trùm lên tâm cụm sticker
        by = max(int(h * 0.15), int(sticker_box["center_y"] - bh / 2.0))
        # Đảm bảo viền banner trùm qua mép trên và mép dưới sticker
        if by > sticker_box["y"] - 15:
            by = max(int(h * 0.15), sticker_box["y"] - 25)
        if by + bh < sticker_box["y"] + sticker_box["h"] + 15:
            bh = (sticker_box["y"] + sticker_box["h"] + 25) - by
    else:
        # Nếu không có sticker cụ thể, đặt banner ở vùng 35% chiều cao (trên ngực/mặt)
        by = int(h * 0.35)

    banner_duration = 2.5
    if sticker_box:
        banner_duration = round(max(2.5, min(8.0, float(sticker_box.get("t_end", 2.5)) + 0.3)), 2)

    return {
        "has_cover": has_cover,
        "cut_ts": cut_ts,
        "banner_box": {"x": bx, "y": by, "w": bw, "h": bh},
        "banner_duration": banner_duration,
        "sticker_box": sticker_box,
        "intro_boxes": intro_boxes,
        "vid_w": w,
        "vid_h": h
    }


def create_title_banner_png(
    title_main: str,
    brand_text: str = "CHỊ ĐẸP ĐI CÂU",
    out_path: str = None,
    banner_w: int = 940,
    banner_h: int = 240
) -> str:
    """Tạo file PNG Banner trong suốt bo tròn góc với hiệu ứng sang trọng, che trọn chữ Trung Quốc."""
    if not out_path:
        out_path = "workspace/intro_banner_temp.png"
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGBA", (banner_w, banner_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Vẽ nền bo góc màu đen than chì sang trọng (opacity 100% che sạch hoàn toàn)
    radius = 32
    bg_color = (15, 18, 24, 255)
    border_color = (255, 215, 0, 255)  # Viền vàng Gold nổi bật
    border_width = 5

    draw.rounded_rectangle(
        [(border_width, border_width), (banner_w - border_width, banner_h - border_width)],
        radius=radius,
        fill=bg_color,
        outline=border_color,
        width=border_width
    )

    # 2. Viền phụ màu xanh ngọc bên trong tạo chiều sâu
    inner_pad = 8
    draw.rounded_rectangle(
        [(border_width + inner_pad, border_width + inner_pad),
         (banner_w - border_width - inner_pad, banner_h - border_width - inner_pad)],
        radius=radius - 6,
        outline=(0, 210, 230, 180),
        width=2
    )

    # 3. Typography
    font_brand = get_vietnamese_font(size=42, bold=True)
    
    # Làm sạch tiêu đề: KHÔNG BAO GIỜ hiển thị chữ Trung Quốc trên banner
    title_clean = title_main.strip().upper()
    if re.search(r'[\u4e00-\u9fff]', title_clean) or not title_clean:
        title_clean = "SĂN CÁ KHỦNG CÙNG CHỊ ĐẸP"

    # Tính cỡ chữ cho title_main sao cho vừa khít bề ngang banner
    base_title_size = 36
    if len(title_clean) > 36:
        base_title_size = 26
    elif len(title_clean) > 26:
        base_title_size = 30

    font_title = get_vietnamese_font(size=base_title_size, bold=True)

    cx = banner_w // 2

    # Vẽ Dòng 1: Brand "CHỊ ĐẸP ĐI CÂU"
    brand_y = int(banner_h * 0.24)
    # Shadow
    draw.text((cx + 2, brand_y + 2), brand_text, font=font_brand, fill=(0, 0, 0, 220), anchor="mm")
    draw.text((cx, brand_y), brand_text, font=font_brand, fill=(255, 215, 0, 255), anchor="mm")

    # Đường kẻ ngăn cách mảnh
    line_y = int(banner_h * 0.44)
    line_w = int(banner_w * 0.70)
    line_x1 = (banner_w - line_w) // 2
    draw.line([(line_x1, line_y), (line_x1 + line_w, line_y)], fill=(255, 215, 0, 180), width=2)

    # Vẽ Dòng 2: Tiêu đề video tiếng Việt
    title_y = int(banner_h * 0.70)
    # Shadow
    draw.text((cx + 2, title_y + 2), title_clean, font=font_title, fill=(0, 0, 0, 240), anchor="mm")
    draw.text((cx, title_y), title_clean, font=font_title, fill=(255, 255, 255, 255), anchor="mm")

    try:
        img.save(str(out_file), "PNG")
        return str(out_file)
    except PermissionError:
        import time
        alt_file = out_file.parent / f"{out_file.stem}_{int(time.time()*1000)}.png"
        img.save(str(alt_file), "PNG")
        return str(alt_file)


def generate_prerender_preview(
    video_path: str,
    title_text: str = "SĂN CÁ KHỦNG CÙNG CHỊ ĐẸP",
    brand_text: str = "CHỊ ĐẸP ĐI CÂU",
    out_preview_path: str = None
) -> dict:
    """Tạo 1 bức ảnh so sánh Preview tổng hợp 2 phương án (Dùng Banner vs Làm mờ/Cắt sạch) để gửi lên Telegram."""
    if not out_preview_path:
        out_preview_path = "workspace/preview_prerender.jpg"
    out_file = Path(out_preview_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    info = detect_intro_hook_info(video_path)
    banner_box = info["banner_box"]
    sticker_box = info["sticker_box"]
    cut_ts = info["cut_ts"]

    cap = cv2.VideoCapture(str(video_path))
    ret0, frame0 = cap.read()

    # Lấy frame sau khi cắt bỏ nếu có bìa
    cap.set(cv2.CAP_PROP_POS_MSEC, max(150, cut_ts * 1000.0))
    ret_cut, frame_cut = cap.read()
    cap.release()

    if not ret0:
        raise RuntimeError(f"Không thể đọc video: {video_path}")
    if not ret_cut:
        frame_cut = frame0.copy()

    # Lọc tiêu đề tiếng Việt chuẩn: không dùng chữ Trung
    clean_title_text = title_text.strip()
    if re.search(r'[\u4e00-\u9fff]', clean_title_text) or not clean_title_text:
        clean_title_text = "SĂN CÁ KHỦNG CÙNG CHỊ ĐẸP"

    # 1. Tạo Banner PNG
    banner_png = out_file.parent / f"{out_file.stem}_banner.png"
    create_title_banner_png(
        title_main=clean_title_text,
        brand_text=brand_text,
        out_path=str(banner_png),
        banner_w=banner_box["w"],
        banner_h=banner_box["h"]
    )

    # 2. Ghép Banner lên Frame 0 (Phương án A)
    frame_banner = frame0.copy()
    banner_img = cv2.imread(str(banner_png), cv2.IMREAD_UNCHANGED)
    if banner_img is not None and banner_img.shape[2] == 4:
        bx = max(0, banner_box["x"])
        by = max(0, banner_box["y"])
        bw = min(frame_banner.shape[1] - bx, banner_box["w"])
        bh = min(frame_banner.shape[0] - by, banner_box["h"])
        resized_banner = cv2.resize(banner_img, (bw, bh), interpolation=cv2.INTER_AREA)

        alpha = resized_banner[:, :, 3] / 255.0
        for c in range(3):
            frame_banner[by:by+bh, bx:bx+bw, c] = (
                alpha * resized_banner[:, :, c] + (1 - alpha) * frame_banner[by:by+bh, bx:bx+bw, c]
            )

    # 3. Xử lý Phương án B (Làm mờ sạch chữ Trung hoặc Cắt bìa)
    frame_b = frame0.copy()
    b_label = "B. LÀM MỜ CHỮ TRUNG (SẠCH)"
    if sticker_box:
        # Áp dụng Gaussian blur làm mờ sạch cụm sticker tiếng Trung
        sx, sy, sw, sh = sticker_box["x"], sticker_box["y"], sticker_box["w"], sticker_box["h"]
        pad_x, pad_y = 35, 25
        h_f, w_f = frame_b.shape[:2]
        x1, y1 = max(0, sx - pad_x), max(0, sy - pad_y)
        x2, y2 = min(w_f, sx + sw + pad_x), min(h_f, sy + sh + pad_y)
        roi = frame_b[y1:y2, x1:x2]
        frame_b[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (55, 55), 35)
    else:
        # Nếu không có sticker thì dùng frame đã cắt bìa
        frame_b = frame_cut.copy()
        b_label = "B. CẮT BỎ 0.15s ĐẦU (SẠCH)"

    # 4. Tạo ảnh so sánh ghép đôi (Side-by-side) gửi Telegram
    target_h = 960
    target_w = int(target_h * 9 / 16)  # 540

    side_banner = cv2.resize(frame_banner, (target_w, target_h), interpolation=cv2.INTER_AREA)
    side_b = cv2.resize(frame_b, (target_w, target_h), interpolation=cv2.INTER_AREA)

    combined = np.zeros((target_h, target_w * 2, 3), dtype=np.uint8)
    combined[:, :target_w] = side_banner
    combined[:, target_w:] = side_b

    # Thêm nhãn header phân biệt từng bên
    pil_comb = Image.fromarray(cv2.cvtColor(combined, cv2.COLOR_BGR2RGB))
    pdraw = ImageDraw.Draw(pil_comb)
    lbl_font = get_vietnamese_font(size=24, bold=True)

    # Tag Bên trái: Phương án A (Dùng Banner)
    pdraw.rectangle([(16, 16), (target_w - 16, 68)], fill=(20, 20, 30, 230), outline=(255, 215, 0), width=2)
    pdraw.text((target_w // 2, 42), "A. DÙNG BANNER TIÊU ĐỀ", font=lbl_font, fill=(255, 215, 0), anchor="mm")

    # Tag Bên phải: Phương án B (Làm mờ chữ Trung sạch)
    pdraw.rectangle([(target_w + 16, 16), (target_w * 2 - 16, 68)], fill=(20, 20, 30, 230), outline=(0, 220, 255), width=2)
    pdraw.text((target_w + target_w // 2, 42), b_label, font=lbl_font, fill=(0, 220, 255), anchor="mm")

    res_bgr = cv2.cvtColor(np.array(pil_comb), cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(out_file), res_bgr)

    return {
        "preview_path": str(out_file),
        "banner_png": str(banner_png),
        "banner_box": banner_box,
        "sticker_box": sticker_box,
        "cut_ts": cut_ts,
        "title_text": clean_title_text,
        "brand_text": brand_text
    }
