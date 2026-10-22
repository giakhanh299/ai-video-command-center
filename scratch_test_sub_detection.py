import cv2
import sys
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

cap = cv2.VideoCapture(r'D:/0.1_FACE_BOOK/Lay video tiktok\workspace\douyin_test_raw.mp4')
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

roi_top = int(h * 0.50)
roi_bottom = int(h * 0.88)
print(f"Scanning ROI: Y={roi_top}..{roi_bottom} (H={roi_bottom-roi_top})")

timestamps = [5.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0, 105.0]
detected_boxes = []

for ts in timestamps:
    cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
    ret, frame = cap.read()
    if not ret or frame is None:
        continue
    roi = frame[roi_top:roi_bottom, :]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 205, 255, cv2.THRESH_BINARY)
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, k_close)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        cx = x + bw / 2.0
        if abs(cx - w / 2.0) <= (w * 0.32) and bw >= 80 and 20 <= bh <= int(h * 0.08) and (bw / float(bh)) >= 1.6:
            abs_y1 = roi_top + y
            abs_y2 = abs_y1 + bh
            cy = (abs_y1 + abs_y2) / 2.0
            detected_boxes.append({'x1': x, 'x2': x + bw, 'y1': abs_y1, 'y2': abs_y2, 'w': bw, 'h': bh, 'center_y': cy, 'ts': ts})

cap.release()
print(f"Total detected candidate boxes: {len(detected_boxes)}")
for b in detected_boxes[:15]:
    print(f"  ts={b['ts']}s: Y={b['y1']}..{b['y2']} (H={b['h']}), X={b['x1']}..{b['x2']} (W={b['w']}), center_y={b['center_y']}")

# Clustering on center_y
if detected_boxes:
    all_cys = [b['center_y'] for b in detected_boxes]
    med_cy = float(np.median(all_cys))
    consistent = [b for b in detected_boxes if abs(b['center_y'] - med_cy) <= 25]
    if not consistent:
        consistent = detected_boxes
    final_cy = int(round(np.median([b['center_y'] for b in consistent])))
    line_h = int(round(np.median([b['h'] for b in consistent])))
    min_x = min(b['x1'] for b in consistent)
    max_x = max(b['x2'] for b in consistent)
    print(f"\n===> CLUSTER RESULT: CenterY={final_cy}, LineH={line_h}, X={min_x}..{max_x}")
    print(f"     Subtitle bounding box: Y={final_cy - line_h//2}..{final_cy + line_h//2}")
