"""OCR caption regions in source-video coordinates and timed ASS placement."""
import math
import re
import cv2
import os


def _read_text(reader, image):
    batch = max(1, min(8, int(os.getenv('DOUYIN_OCR_BATCH_SIZE', '1'))))
    if batch > 1 and type(reader).__module__.startswith('easyocr.'):
        return reader.readtext(image, batch_size=batch)
    return reader.readtext(image)


def read_caption_detections(reader, frame):
    detections = list(_read_text(reader, frame))
    height,width = frame.shape[:2]
    recovered=[]
    for points,text,confidence in detections:
        if confidence >= .35:
            continue
        xs,ys=zip(*points)
        w,h=max(xs)-min(xs),max(ys)-min(ys)
        if h < max(14,height*.018) or w < h*1.4 or min(ys)<height*.20:
            continue
        x,y=max(0,int(min(xs))-8),max(0,int(min(ys))-8)
        right,bottom=min(width,int(max(xs))+9),min(height,int(max(ys))+9)
        crop=frame[y:bottom,x:right]
        white=cv2.inRange(crop,(185,185,185),(255,255,255))
        yellow=cv2.inRange(crop,(0,170,170),(140,255,255))
        # Recover outlined captions on a plain background; keep full-frame coordinates.
        plain=255-cv2.bitwise_or(white,yellow)
        for local,txt,prob in _read_text(reader, plain):
            if prob >= .35:
                recovered.append(([[float(px)+x,float(py)+y] for px,py in local],txt,float(prob)))
    return detections+recovered


def caption_box(detections, width, height):
    candidates = []
    for points, text, confidence in detections:
        # Nhan dien chu Trung, Han, Anh/Latin hoac so
        has_cjk_or_hangul = bool(re.search(r'[\u4e00-\u9fff\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]', text))
        has_text_alpha = bool(re.search(r'[a-zA-Z0-9]', text))
        if confidence < .20 or (not has_cjk_or_hangul and not has_text_alpha):
            continue
        xs, ys = zip(*points)
        x, y, right, bottom = min(xs), min(ys), max(xs), max(ys)
        w, h = right - x, bottom - y
        # Exclude vertical watermarks and tiny scene text, but include low captions.
        if h < max(10, height * .009) or w < h * 1.2 or y < height * .20:
            continue
        candidates.append((x, y, right, bottom))
    if not candidates:
        return None
    # Prefer substantial lower dialogue lines over small signs in the scene.
    main = max(candidates, key=lambda b: (b[2]-b[0]) * (0.5 + b[3]/height))
    mh = main[3] - main[1]  # chieu cao dong main

    # Nhom tat ca box trong dai day man hinh:
    #   - KHONG yeu cau overlap ngang (phim co 2 dong: 1 tren 1 duoi)
    #   - Chi can center_y trong pham vi +-3.5 line-height so voi main
    main_cy = (main[1] + main[3]) / 2.0
    max_cy_gap = max(mh * 3.5, height * 0.12)
    lines = [b for b in candidates
             if abs((b[1] + b[3]) / 2.0 - main_cy) <= max_cy_gap
             and b[3] > height * 0.25]
    if not lines:
        return None

    px, py = max(12, width * .015), max(8, height * .010)
    x = max(0, math.floor((min(b[0] for b in lines) - px) / 2) * 2)
    y = max(0, math.floor((min(b[1] for b in lines) - py) / 2) * 2)
    right = min(width // 2 * 2, math.ceil((max(b[2] for b in lines) + px) / 2) * 2)
    bottom = min(height // 2 * 2, math.ceil((max(b[3] for b in lines) + py) / 2) * 2)
    return dict(x=x, y=y, w=right-x, h=bottom-y, center_y=(y+bottom)/2)


def scan_caption_regions(path, sample_fps=2.0):

    from wuby_ocr_overlay import get_ocr_reader
    reader = get_ocr_reader()
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f'Cannot open caption source: {path}')
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        duration = cap.get(cv2.CAP_PROP_FRAME_COUNT)/fps
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        step = 1/max(.1, float(sample_fps))
        events = []
        # Scan every interval, including empty intervals: never hold a stale box
        # over a long scene change or a section with no captions.
        for i in range(math.ceil(duration/step)):
            start, end = i*step, min(duration,(i+1)*step)
            cap.set(cv2.CAP_PROP_POS_MSEC, (start+end)*500)
            ok, frame = cap.read()
            box = caption_box(read_caption_detections(reader,frame),width,height) if ok else None
            events.append(dict(start=start,end=end,box=box))
        anchors=[e for e in events if e['box']]
        for event in events:
            if event['box']:
                continue
            nearby=[e for e in anchors if abs(e['start']-event['start'])<=1.0]
            if not nearby:
                continue
            anchor=min(nearby,key=lambda e:abs(e['start']-event['start']))['box']
            cap.set(cv2.CAP_PROP_POS_MSEC,(event['start']+event['end'])*500)
            ok,frame=cap.read()
            if not ok:
                continue
            x,y=max(0,anchor['x']-32),max(0,anchor['y']-24)
            right,bottom=min(width,anchor['x']+anchor['w']+32),min(height,anchor['y']+anchor['h']+24)
            crop=frame[y:bottom,x:right]
            plain=255-cv2.bitwise_or(cv2.inRange(crop,(185,185,185),(255,255,255)),cv2.inRange(crop,(0,170,170),(140,255,255)))
            recovered=[([[float(px)+x,float(py)+y] for px,py in pts],txt,float(prob)) for pts,txt,prob in _read_text(reader, plain)]
            # A neighbouring position is only a search hint, never a blind hold.
            event['box']=caption_box(recovered,width,height)
        return stabilize_regions(events, width, height)
    finally:
        cap.release()


def stabilize_regions(events, width, height):
    """Union neighbouring widths on the same baseline, without clipping a hit.

    Keep scene position changes and empty intervals separate. This also keeps
    long-video FFmpeg graphs bounded by region changes rather than OCR jitter.
    """
    runs=[]
    for event in events:
        box=event['box']
        previous=runs[-1] if runs else None
        old=previous['box'] if previous else None
        same = (box and old and abs(old['center_y']-box['center_y']) <= height*.012
                and abs((old['x']+old['w']/2)-(box['x']+box['w']/2)) <= width*.06)
        if previous and abs(previous['end']-event['start'])<.001 and (same or (box is None and old is None)):
            previous['end']=event['end']
            if same:
                x,y=min(old['x'],box['x']),min(old['y'],box['y'])
                r,b=max(old['x']+old['w'],box['x']+box['w']),max(old['y']+old['h'],box['y']+box['h'])
                previous['box']=dict(x=x,y=y,w=r-x,h=b-y,center_y=(y+b)/2)
        else:
            runs.append(dict(event))
    return runs


def region_filters(events, mode, width, height, label):
    filters = []
    # Coalesce adjacent identical regions to reduce the FFmpeg graph size.
    runs = []
    for event in events:
        if not event['box']:
            continue
        b = event['box']
        if runs and runs[-1]['box'] == b and abs(runs[-1]['end']-event['start']) < .001:
            runs[-1]['end'] = event['end']
        else:
            runs.append(dict(event))
    for i,e in enumerate(runs):
        b=e['box']; x,y,w,h=(b[k] for k in ('x','y','w','h'))
        enable=f"gte(t,{e['start']:.6f})*lt(t,{e['end']:.6f})"
        out=f'[caption_{i}]'
        if mode=='black_bar':
            filters.append(f"{label}drawbox=x=0:y={y}:w=iw:h={height-y}:color=black:t=fill:enable='{enable}'{out}")
        elif mode=='blur_sub_black':
            filters.extend([f'{label}split[cb{i}][cc{i}]',
                f'[cc{i}]crop={w}:{h}:{x}:{y},gblur=sigma=12[cf{i}]',
                f"[cb{i}][cf{i}]overlay={x}:{y}:enable='{enable}'[co{i}]",
                f"[co{i}]drawbox=x={x}:y={y}:w={w}:h={h}:color=black@0.58:t=fill:enable='{enable}'{out}"])
        else:
            filters.append(f"{label}drawbox=x={x}:y={y}:w={w}:h={h}:color=black:t=fill:enable='{enable}'{out}")
        label=out
    return filters,label


def positioned_parts(start,end,text,events,font_size,width,height):
    """Split caption times at region boundaries; center and fit both lines."""
    cuts=sorted({start,end}|{e[k] for e in events for k in ('start','end') if start<e[k]<end})
    for a,b in zip(cuts,cuts[1:]):
        box=next((e['box'] for e in events if e['start']<b and e['end']>a),None)
        if not box:
            # No verified cover: retain dialogue in a normal bottom position.
            yield a,b,text
            continue
        clean=text.replace('\\N',' ').replace('\n',' ')
        words=clean.split()
        if not words:
            continue
        lines=[clean]
        if len(clean)>24:
            mid=min(range(1,len(words)),key=lambda i:abs(len(' '.join(words[:i]))-len(' '.join(words[i:])))) if len(words)>1 else 0
            if mid: lines=[' '.join(words[:mid]),' '.join(words[mid:])]
        # Dùng font_size cố định (tính theo chiều cao video), KHÔNG thu nhỏ theo box OCR.
        # Box OCR chỉ bao quanh chữ gốc (có thể rất hẹp), nếu min() theo box thì chữ lúc to lúc nhỏ.
        size = font_size
        cx,cy=box['x']+box['w']/2,box['y']+box['h']/2
        content='\\N'.join(lines)
        yield a,b,f'{{\\an5\\pos({cx:.1f},{cy:.1f})\\fs{size}\\q2}}{content}'


def scan_multi_blur_boxes(video_path, probe_timestamps=None, max_samples: int = 35):
    """Quét các frame của video để nhận diện đa vùng chữ cần che:
    - Zone 1: Subtitle / Captions / Dialogue stickers (0.48 <= rel_cy < 0.76)
    - Zone 2: Brand / Watermark / Bottom logo (rel_cy >= 0.76)

    Áp dụng median clustering theo trục Y để loại bỏ chữ in áo / họa tiết ngẫu nhiên.
    Thêm +2% padding gọn gàng, căn chẵn 2 pixel cho FFmpeg.

    Returns:
        list[dict(zone, x, y, w, h, center_y)]
    """
    # Ưu tiên sử dụng RapidOCR bắt điểm tọa độ chữ chuẩn xác theo yêu cầu người dùng
    try:
        from rapid_ocr_service import scan_rapid_ocr_boxes
        rapid_boxes = scan_rapid_ocr_boxes(video_path, max_samples=max_samples)
        if rapid_boxes:
            return rapid_boxes
    except Exception as rapid_err:
        print(f"[scan_multi_blur_boxes] RapidOCR error ({rapid_err}), fallback to EasyOCR...")

    from wuby_ocr_overlay import get_ocr_reader
    import numpy as np

    reader = get_ocr_reader()
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1080
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1920
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    dur = total_frames / fps if fps > 0 else 0

    if not probe_timestamps or len(probe_timestamps) == 0:
        if dur > 5.0:
            # Lấy mẫu tập trung đầu, giữa và cuối video
            early_samples = list(range(1, min(int(dur), 120), 4))
            later_samples = list(np.linspace(min(120, dur * 0.4), max(10, dur - 3), 15))
            probe_timestamps = sorted(list(set(early_samples + [int(x) for x in later_samples])))
        else:
            probe_timestamps = [1.0, 2.0, 3.0]

    probe_timestamps = list(probe_timestamps)[:max_samples]
    raw_detections = []

    try:
        for ts in probe_timestamps:
            cap.set(cv2.CAP_PROP_POS_MSEC, float(ts) * 1000.0)
            ok, frame = cap.read()
            if not ok:
                continue
            y_offset = int(h * 0.48)
            crop = frame[y_offset:, :]
            dets = reader.readtext(crop)
            for pts, txt, conf in dets:
                has_cjk = bool(re.search(r'[\u4e00-\u9fff\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]', txt))
                has_alpha = bool(re.search(r'[a-zA-Z0-9]{2,}', txt))
                if conf < 0.20 or (not has_cjk and not has_alpha):
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] + y_offset for p in pts]
                bw = max(xs) - min(xs)
                bh = max(ys) - min(ys)
                if bh < 12 or bw < 14:
                    continue
                cy = (min(ys) + max(ys)) / 2.0
                raw_detections.append({
                    'ts': ts,
                    'txt': txt,
                    'conf': conf,
                    'x': min(xs),
                    'y': min(ys),
                    'w': bw,
                    'h': bh,
                    'cy': cy,
                    'rel_cy': cy / h
                })
    finally:
        cap.release()

    if not raw_detections:
        print(f"[scan_multi_blur_boxes] Không detect được chữ nào từ {len(probe_timestamps)} frame")
        return []

    sub_candidates = [d for d in raw_detections if 0.48 <= d['rel_cy'] < 0.76]
    wm_candidates = [d for d in raw_detections if d['rel_cy'] >= 0.76]

    boxes = []

    def cluster_zone(candidates, zone_name, max_height_ratio=0.12):
        if not candidates:
            return None

        cys = [c['cy'] for c in candidates]
        med_cy = sorted(cys)[len(cys) // 2]

        # Chỉ giữ các candidate trong phạm vi sai lệch <= 6% chiều cao so với median
        max_dev = max(45.0, h * 0.06)
        inliers = [c for c in candidates if abs(c['cy'] - med_cy) <= max_dev]
        if not inliers:
            inliers = candidates

        x_min = min(c['x'] for c in inliers)
        y_min = min(c['y'] for c in inliers)
        x_max = max(c['x'] + c['w'] for c in inliers)
        y_max = max(c['y'] + c['h'] for c in inliers)

        # Padding +2% gọn gàng theo yêu cầu
        pad_v = max(8, int(round(h * 0.02)))
        pad_h = max(20, int(round(w * 0.03)))

        y1 = max(0, int(y_min - pad_v))
        y2 = min(h, int(y_max + pad_v))
        x1 = max(0, int(x_min - pad_h))
        x2 = min(w, int(x_max + pad_h))

        bx = (x1 // 2) * 2
        by = (y1 // 2) * 2
        bw = ((x2 - x1) // 2) * 2
        bh = ((y2 - y1) // 2) * 2

        # Giới hạn chiều cao tối đa không che vào người/mặt
        max_bh = int(round(h * max_height_ratio))
        if bh > max_bh:
            bottom = by + bh
            bh = max_bh
            by = max(0, bottom - bh)

        # Căn giữa theo chiều ngang đối xứng nếu nằm trong khoảng giữa
        cx = (x1 + x2) / 2.0
        if abs(cx - w / 2.0) <= w * 0.18:
            bx = max(0, ((w - bw) // 2 // 2) * 2)

        cy = by + bh / 2.0
        return {
            'zone': zone_name,
            'x': bx,
            'y': by,
            'w': bw,
            'h': bh,
            'center_y': cy,
            'count': len(inliers)
        }

    box_sub = cluster_zone(sub_candidates, 'subtitle', max_height_ratio=0.10)
    if box_sub:
        # Chuẩn hóa độ rộng dải phụ đề để che đủ các câu dài ngắn khác nhau
        min_sub_w = int(w * 0.65)
        if box_sub['w'] < min_sub_w:
            box_sub['w'] = min_sub_w
            box_sub['x'] = max(0, (w - min_sub_w) // 2 // 2 * 2)
        boxes.append(box_sub)
        print(f"[scan_multi_blur_boxes] Phát hiện Zone Subtitle: x={box_sub['x']} y={box_sub['y']} w={box_sub['w']} h={box_sub['h']} (CenterY={box_sub['center_y']:.1f})")

    box_wm = cluster_zone(wm_candidates, 'watermark', max_height_ratio=0.13)
    if box_wm:
        # Đảm bảo box watermark đủ bao trùm các biến thể logo góc/đáy
        min_wm_w = int(w * 0.60)
        if box_wm['w'] < min_wm_w:
            box_wm['w'] = min_wm_w
            box_wm['x'] = max(0, (w - min_wm_w) // 2 // 2 * 2)
        boxes.append(box_wm)
        print(f"[scan_multi_blur_boxes] Phát hiện Zone Watermark: x={box_wm['x']} y={box_wm['y']} w={box_wm['w']} h={box_wm['h']} (CenterY={box_wm['center_y']:.1f})")

    return boxes


def scan_fixed_blur_box(video_path, probe_timestamps, max_samples: int = 20):
    """Fallback tương thích ngược: trả về box phụ đề chính hoặc box watermark."""
    boxes = scan_multi_blur_boxes(video_path, probe_timestamps, max_samples=max_samples)
    if not boxes:
        return None
    # Ưu tiên box subtitle nếu có, ngược lại lấy box đầu tiên
    for b in boxes:
        if b.get('zone') == 'subtitle':
            return b
    return boxes[0]

