from __future__ import annotations
from film_bars import compute_film_black_bars, escape_subtitle_path_windows

import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

from pathlib import Path
import shutil
import subprocess
import cv2
import numpy as np
import re
from typing import Any

def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y", "on"}

def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "."))
    except Exception:
        return default

def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(str(value).replace(",", ".")))
    except Exception:
        return default

def _file_exists(path_value: Any) -> bool:
    if not path_value:
        return False
    path = Path(str(path_value))
    return path.exists() and path.is_file()

def _ffmpeg_executable() -> str:
    configured = os.environ.get("FFMPEG_BINARY") or os.environ.get("FFMPEG_PATH")
    if configured and Path(configured).is_file():
        return configured
    found = shutil.which("ffmpeg")
    if found:
        return found
    local_appdata = os.environ.get("LOCALAPPDATA")
    candidates = []
    if local_appdata:
        candidates.append(Path(local_appdata) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe")
    candidates.append(Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return "ffmpeg"

def _target_size(channel_cfg: dict) -> tuple[int, int]:
    width = _to_int(channel_cfg.get("output_width"), 0)
    height = _to_int(channel_cfg.get("output_height"), 0)
    aspect = str(channel_cfg.get("aspect_ratio", "")).strip().lower()
    if width > 0 and height > 0:
        return width, height
    if aspect in {"16:9", "landscape"}:
        return 1920, 1080
    if aspect in {"1:1", "square"}:
        return 1080, 1080
    return 1080, 1920 # Default vertical

def _video_filter(input_label: str, channel_cfg: dict) -> tuple[list[str], str]:
    width, height = _target_size(channel_cfg)
    fit_mode = str(
        channel_cfg.get("fit_mode")
        or ("blur_bg" if _to_bool(channel_cfg.get("background_blur"), False) else "contain")
    ).strip().lower()
    speed = max(_to_float(channel_cfg.get("speed"), 1.0), 0.01)
    setpts = f"setpts={1 / speed:.6f}*PTS"
    
    filters = []
    base_label = "[vbase]"

    if fit_mode in {"cover", "crop"}:
        filters.append(f"{input_label}scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},{setpts}{base_label}")
    elif fit_mode in {"blur_bg", "vertical_blur"}:
        blur_strength = _to_int(channel_cfg.get("blur_strength"), 28)
        fg_width = _to_int(channel_cfg.get("foreground_width"), 0)
        if fg_width <= 0:
            fg_width = int(width * 0.84)
        filters.extend([
            f"{input_label}scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},gblur=sigma={blur_strength},{setpts}[bg]",
            f"{input_label}scale={fg_width}:-2:force_original_aspect_ratio=decrease,{setpts}[fg]",
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2{base_label}"
        ])
    else:
        filters.append(f"{input_label}scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,{setpts}{base_label}")

    # Subtitle blurring logic
    if _to_bool(channel_cfg.get("blur_subtitle"), False):
        blur_h = channel_cfg.get("blur_subtitle_height_ratio", 0.25) # Default bottom 25%
        # Crop the bottom part, blur it, and overlay back
        filters.extend([
            f"{base_label}split[vmain][vsubarea]",
            f"[vsubarea]crop=iw:ih*{blur_h}:0:ih-ih*{blur_h},boxblur=15:5[vblurredsub]",
            f"[vmain][vblurredsub]overlay=0:H-h[vblurred]"
        ])
        base_label = "[vblurred]"

    return filters, base_label

def _subtitle_filter(path_value: Any) -> str:
    subtitle_path = str(path_value).replace("\\", "/").replace(":", "\\:")
    return f"subtitles='{subtitle_path}'"

def build_render_command(input_video: Path, voice_audio: Path | None, output_video: Path, channel_cfg: dict) -> list[str]:
    inputs = ["-i", str(input_video)]
    next_input_index = 1
    voice_index = None
    if voice_audio:
        inputs += ["-i", str(voice_audio)]
        voice_index = next_input_index
        next_input_index += 1

    background_audio_path = channel_cfg.get("background_audio_path")
    music_path = channel_cfg.get("music_path")
    logo_path = channel_cfg.get("logo_path")
    subtitle_path = channel_cfg.get("subtitle_path") or channel_cfg.get("subtitles_path")
    
    has_music = _file_exists(music_path)
    has_background_audio = _file_exists(background_audio_path)
    has_logo = _file_exists(logo_path)
    has_subtitles = _to_bool(channel_cfg.get("burn_subtitles"), False) and _file_exists(subtitle_path)

    music_index = None
    background_audio_index = None
    logo_index = None
    
    if has_background_audio:
        inputs += ["-i", str(Path(str(background_audio_path)))]
        background_audio_index = next_input_index
        next_input_index += 1
    if has_music:
        inputs += ["-stream_loop", "-1", "-i", str(Path(str(music_path)))]
        music_index = next_input_index
        next_input_index += 1
    if has_logo:
        inputs += ["-i", str(Path(str(logo_path)))]
        logo_index = next_input_index

    filters, video_label = _video_filter("[0:v]", channel_cfg)

    if has_subtitles:
        filters.append(f"{video_label}{_subtitle_filter(subtitle_path)}[vsub]")
        video_label = "[vsub]"

    if has_logo and logo_index is not None:
        opacity = _to_float(channel_cfg.get("logo_opacity"), 0.16)
        x = channel_cfg.get("logo_x", 30)
        y = channel_cfg.get("logo_y", 40)
        logo_width = _to_int(channel_cfg.get("logo_width"), 0)
        logo_filter = f"[{logo_index}:v]format=rgba"
        if logo_width > 0:
            logo_filter += f",scale={logo_width}:-1"
        logo_filter += f",colorchannelmixer=aa={opacity}[logo]"
        filters.append(logo_filter)
        filters.append(f"{video_label}[logo]overlay={x}:{y}[vout]")
        video_label = "[vout]"

    audio_inputs = []
    keep_original_audio = _to_bool(channel_cfg.get("keep_original_audio"), False)
    original_audio_volume = _to_float(channel_cfg.get("original_audio_volume"), 0.0 if voice_index is not None else 1.0)
    background_audio_volume = _to_float(channel_cfg.get("background_audio_volume"), 0.35)
    tts_audio_volume = _to_float(channel_cfg.get("tts_audio_volume"), 1.0)
    music_volume = _to_float(channel_cfg.get("music_volume"), 0.07)

    if keep_original_audio and original_audio_volume > 0:
        filters.append(f"[0:a]volume={original_audio_volume}[aorig]")
        audio_inputs.append("[aorig]")
    if background_audio_index is not None and background_audio_volume > 0:
        filters.append(f"[{background_audio_index}:a]volume={background_audio_volume}[abg]")
        audio_inputs.append("[abg]")
    if voice_index is not None:
        filters.append(f"[{voice_index}:a]volume={tts_audio_volume}[atts]")
        audio_inputs.append("[atts]")
    if has_music and music_index is not None and music_volume > 0:
        filters.append(f"[{music_index}:a]volume={music_volume}[amusic]")
        audio_inputs.append("[amusic]")

    audio_label = ""
    if len(audio_inputs) > 1:
        filters.append(
            f"{''.join(audio_inputs)}"
            f"amix=inputs={len(audio_inputs)}:duration=first:dropout_transition=2:normalize=0[aout]"
        )
        audio_label = "[aout]"
    elif len(audio_inputs) == 1:
        audio_label = audio_inputs[0]
    elif voice_index is not None:
        audio_label = f"{voice_index}:a:0"
    elif keep_original_audio:
        audio_label = "0:a:0"

    cmd = [_ffmpeg_executable(), "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters), "-map", video_label]
    if audio_label:
        cmd += ["-map", audio_label]

    if _to_bool(channel_cfg.get("use_nvenc"), True):
        cmd += ["-c:v", "h264_nvenc", "-preset", str(channel_cfg.get("nvenc_preset", "p4")), "-cq", str(channel_cfg.get("cq", 23))]
    else:
        cmd += ["-c:v", "libx264", "-preset", str(channel_cfg.get("x264_preset", "veryfast")), "-crf", str(channel_cfg.get("crf", 23))]

    if audio_label:
        cmd += ["-c:a", "aac", "-b:a", str(channel_cfg.get("audio_bitrate", "192k"))]
    cmd += ["-shortest", str(output_video)]
    return cmd

class AdvancedRenderService:
    def render_video(self, input_video: str, voice_audio: str, output_video: str, channel_cfg: dict = None) -> None:
        if channel_cfg is None:
            channel_cfg = {}
            
        in_vid = Path(input_video)
        voice_aud = Path(voice_audio) if voice_audio and os.path.exists(voice_audio) else None
        out_vid = Path(output_video)
        
        out_vid.parent.mkdir(parents=True, exist_ok=True)
        
        cmd = build_render_command(in_vid, voice_aud, out_vid, channel_cfg)
        
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            # Fallback to x264 if nvenc fails
            if not _to_bool(channel_cfg.get("use_nvenc"), True):
                raise
            print("NVENC failed, falling back to libx264...")
            fallback_cfg = dict(channel_cfg)
            fallback_cfg["use_nvenc"] = False
            fallback_cmd = build_render_command(in_vid, voice_aud, out_vid, fallback_cfg)
            subprocess.run(fallback_cmd, check=True)

# Compatibility wrapper for old calls
def merge_video_audio(original_video: str, new_audio: str, output_video: str, channel_cfg: dict = None):
    if channel_cfg is None:
        # Default config mimicking the old simple behavior but with nvenc
        channel_cfg = {
            "use_nvenc": True,
            "background_blur": False,
            "blur_subtitle": True,
            "keep_original_audio": True,
            "original_audio_volume": 0.05,  # Giảm 50% âm thanh gốc (từ 0.10 xuống 0.05)

            "tts_audio_volume": 1.0
        }
    
    renderer = AdvancedRenderService()
    renderer.render_video(original_video, new_audio, output_video, channel_cfg)

def detect_letterbox_bars(video_path: str, num_samples: int = 16) -> tuple[int, int]:
    """
    Tự động nhận diện dải viền đen (letterbox / pillarbox bars) ở trên và dưới video.
    Dù có comment, icon tim, logo kênh hay phụ đề Trung Quốc nằm trong dải đen,
    thuật toán vẫn xác định chính xác đường biên giữa dải đen và nội dung phim.
    Trả về: (top_bar, bot_bar) tính theo pixel chẵn.
    """
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return 0, 0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < 10 or h < 200:
            cap.release()
            return 0, 0
            
        sample_indices = np.linspace(int(total_frames * 0.05), int(total_frames * 0.95), num_samples, dtype=int)
        frames_gray = []
        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret and frame is not None:
                frames_gray.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        cap.release()
        
        if not frames_gray:
            return 0, 0
            
        # Tỷ lệ pixel đen (< 28) trên mỗi dòng y cho từng frame
        black_ratios = [np.mean(fg < 28, axis=1) for fg in frames_gray]
        avg_black_ratio = np.mean(black_ratios, axis=0)
        
        # 1. Tìm viền đen trên (tối đa 32% chiều cao video)
        max_top_search = int(h * 0.32)
        top_bar = 0
        for y in range(max_top_search):
            if avg_black_ratio[y] >= 0.70:
                top_bar = y + 1
            else:
                lookahead = avg_black_ratio[y:min(y+4, max_top_search)]
                if len(lookahead) > 0 and np.all(lookahead < 0.70):
                    break
                    
        # 2. Tìm viền đen dưới (tối đa 32% chiều cao video từ đáy)
        min_bot_search = int(h * 0.68)
        bot_bar = 0
        for y in range(h - 1, min_bot_search, -1):
            if avg_black_ratio[y] >= 0.70:
                bot_bar = h - y
            else:
                lookahead = avg_black_ratio[max(min_bot_search, y-3):y+1]
                if len(lookahead) > 0 and np.all(lookahead < 0.70):
                    break
                    
        # Chỉ áp dụng nếu viền đen đủ lớn (>= 24px) và làm tròn số chẵn
        top_bar = (top_bar // 2) * 2 if top_bar >= 24 else 0
        bot_bar = (bot_bar // 2) * 2 if bot_bar >= 24 else 0
        return top_bar, bot_bar
    except Exception as e:
        print(f"[VideoMerger] Lỗi kiểm tra viền đen: {e}")
        return 0, 0

def detect_top_watermark_box(video_path: str, top_offset: int = 0, bottom_offset: int = 0, num_samples: int = 15) -> list[dict]:
    """
    Quét 18% phần đỉnh của video để phát hiện logo, watermark hoặc văn bản tĩnh tiếng Trung.
    Nếu logo/watermark xuất hiện liên tục (>= 35% số frame), kiểm tra mật độ cạnh Canny
    để không bị nhận nhầm bầu trời hay các mảng màu sáng tự nhiên của phim.
    """
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return []
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < 10:
            cap.release()
            return []
            
        usable_h = h - top_offset - bottom_offset
        if usable_h < 150:
            cap.release()
            return []
            
        sample_indices = np.linspace(int(total_frames * 0.05), int(total_frames * 0.95), num_samples, dtype=int)
        
        roi_y1 = top_offset
        roi_y2 = top_offset + int(usable_h * 0.18)
        
        masks = []
        rois_gray = []
        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret and frame is not None:
                roi = frame[roi_y1:roi_y2, :]
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                white = cv2.inRange(gray, 205, 255)
                masks.append(white > 0)
                rois_gray.append(gray)
        cap.release()
        
        if len(masks) < 5:
            return []
            
        presence_ratio = np.mean(masks, axis=0)
        static_mask = (presence_ratio >= 0.40).astype(np.uint8) * 255
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 7))
        closed = cv2.morphologyEx(static_mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        boxes = []
        for c in contours:
            x, y, bw, bh = cv2.boundingRect(c)
            # Watermark / logo nằm ở đỉnh: kích thước thực tế vừa vặn, không quá to
            if 20 <= bw <= int(w * 0.35) and 10 <= bh <= int(usable_h * 0.10):
                # Kiểm tra mật độ cạnh (Edge density): Logo/chữ luôn có viền sắc nét
                # Cắt vùng tương ứng trên ảnh xám trung bình để tính Canny edges
                patch = static_mask[y:y+bh, x:x+bw]
                edges = cv2.Canny(patch, 50, 150)
                edge_density = np.mean(edges > 0)
                if edge_density >= 0.05:
                    bx1 = max(0, ((x - 4) // 2) * 2)
                    by1 = max(0, (((y - 4)) // 2) * 2)
                    bx2 = min(w, ((x + bw + 5) // 2) * 2)
                    by2 = min(usable_h, (((y + bh + 5)) // 2) * 2)
                    boxes.append({'x': bx1, 'y': by1, 'w': bx2 - bx1, 'h': by2 - by1})
        return boxes
    except Exception as e:
        print(f"[VideoMerger] Lỗi quét watermark góc trên: {e}")
        return []

def detect_subtitle_box_20_frames(
    video_path: str,
    segments: list | None = None,
    top_offset: int = 0,
    bottom_offset: int = 0
) -> dict | None:
    """
    Xác định vị trí lớn nhất của phụ đề theo thuật toán:
    1. Chọn 10 đoạn có nội dung câu dài nhất từ bước bóc tách lời thoại
    2. Lấy 2 khung hình trên mỗi đoạn đó (tại 35% và 70% thời lượng câu) -> 20 khung hình
    3. Quét trong vùng 22% đáy của khu vực phim khả dụng (sau khi trừ top_offset và bottom_offset)
    4. Xác định toạ độ bao ngoài lớn nhất (Max Bounding Box)
    """
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
            
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        duration_sec = total_frames / fps
        
        if duration_sec < 1.0:
            cap.release()
            return None
            
        usable_h = height - top_offset - bottom_offset
        if usable_h < 150:
            cap.release()
            return None

        # 1. Chọn 10 đoạn có nội dung dài nhất và lấy 2 khung hình mỗi đoạn
        timestamps = []
        if segments and len(segments) > 0:
            def get_text(s):
                if isinstance(s, dict):
                    return s.get('text', '') or ''
                return getattr(s, 'text', '') or str(s)

            def get_times(s):
                if isinstance(s, dict):
                    st = float(s.get('start', 0.0))
                    en = float(s.get('end', st + 2.0))
                    return st, en
                st = float(getattr(s, 'start', 0.0))
                en = float(getattr(s, 'end', st + 2.0))
                return st, en

            sorted_segs = sorted(segments, key=lambda s: len(get_text(s)), reverse=True)
            top_segments = sorted_segs[:10]
            for seg in top_segments:
                s_start, s_end = get_times(seg)
                if s_end > s_start:
                    t1 = s_start + (s_end - s_start) * 0.35
                    t2 = s_start + (s_end - s_start) * 0.70
                else:
                    t1 = s_start
                    t2 = s_start + 0.5
                timestamps.extend([t1, t2])
            print(f"[VideoMerger] Lấy 20 khung hình từ 10 câu dài nhất (tổng cộng {len(timestamps)} mốc thời gian)...")
        else:
            timestamps = list(np.linspace(duration_sec * 0.05, duration_sec * 0.95, 20))
        
        detected_boxes = []
        
        # Vùng tập trung phụ đề: Quét chính xác 22% ở đáy vùng hiển thị khả dụng
        roi_top = top_offset + int(usable_h * (1.0 - 0.22))
        roi_bottom = height - bottom_offset
        
        for ts in timestamps:
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
                
            roi = frame[roi_top:roi_bottom, :]
            # Nhận diện màu chữ phụ đề (trắng hoặc vàng sáng)
            white = cv2.inRange(roi, (200, 200, 200), (255, 255, 255))
            yellow = cv2.inRange(roi, (0, 180, 180), (120, 255, 255))
            mask = cv2.bitwise_or(white, yellow)
            
            k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3))
            closed = cv2.morphologyEx(white, cv2.MORPH_CLOSE, k_close)
            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for c in contours:
                x, y, bw, bh = cv2.boundingRect(c)
                cx = x + bw / 2.0
                # Tiêu chuẩn phụ đề trong 22% đáy:
                # - Nằm ở dải trung tâm màn hình (lệch tâm <= 28% chiều rộng)
                # - Chiều rộng văn bản bw >= 40, dạng chữ ngang (bw / bh >= 1.4)
                # - Chiều cao chữ trong ngưỡng 14px đến 12% chiều cao video
                if abs(cx - width / 2.0) <= (width * 0.28) and bw >= 40 and 14 <= bh <= int(usable_h * 0.12) and (bw / float(bh)) >= 1.4:
                    abs_y1 = (roi_top - top_offset) + y
                    abs_y2 = abs_y1 + bh
                    cy = (abs_y1 + abs_y2) / 2.0
                    detected_boxes.append({'x1': x, 'x2': x + bw, 'y1': abs_y1, 'y2': abs_y2, 'w': bw, 'h': bh, 'center_y': cy})
                
        cap.release()
        
        if not detected_boxes:
            print("[VideoMerger] Quét vùng đáy: Không phát hiện phụ đề cứng trong khung hình.")
            return None
            
        # 2. Dùng thuật toán Median Clustering để tìm toạ độ tâm Y chuẩn xác 100%, loại bỏ mọi nhiễu ánh sáng
        all_cys = [b['center_y'] for b in detected_boxes]
        med_cy = float(np.median(all_cys))
        consistent = [b for b in detected_boxes if abs(b['center_y'] - med_cy) <= 12]
        if not consistent:
            consistent = detected_boxes
            
        final_cy = int(round(np.median([b['center_y'] for b in consistent])))
        line_h = int(round(np.median([b['h'] for b in consistent])))
        
        # 3. Lấy toạ độ chính xác theo dòng sub thực tế
        final_y1 = max(0, ((final_cy - line_h // 2) // 2) * 2)
        final_y2 = min(usable_h, ((final_cy + (line_h + 1) // 2) // 2) * 2)
        box_h = final_y2 - final_y1
        
        # 4. Chiều rộng lấy chính xác theo phạm vi phụ đề phát hiện được
        raw_min_x = min(b['x1'] for b in consistent)
        raw_max_x = max(b['x2'] for b in consistent)
        box_x1 = max(0, (raw_min_x // 2) * 2)
        box_x2 = min(width, ((raw_max_x + 1) // 2) * 2)
        box_w = box_x2 - box_x1
        
        print(f"[VideoMerger] Bắt toạ độ sub đáy chuẩn xác: X={box_x1}..{box_x2} (Cao: {box_h}px, Rộng: {box_w}px, CenterY: {final_cy})")
        return {"x": box_x1, "y": final_y1, "w": box_w, "h": box_h, "center_y": final_cy, "vid_w": width, "vid_h": usable_h}
    except Exception as e:
        print(f"[VideoMerger] Lỗi quét toạ độ sub bằng OpenCV: {e}")
        return None

def format_ass_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def parse_srt_file_to_events(srt_path: str) -> list[tuple[float, float, str]]:
    """Parses .srt file into list of (start_sec, end_sec, text)."""
    events = []
    if not os.path.exists(srt_path):
        return events
    try:
        content = Path(srt_path).read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        try:
            content = Path(srt_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return events

    blocks = re.split(r'\n\s*\n', content.strip())
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) >= 2:
            time_line = None
            text_lines = []
            for idx, line in enumerate(lines):
                if '-->' in line:
                    time_line = line
                    text_lines = lines[idx + 1:]
                    break
            if time_line:
                parts = time_line.split('-->')
                if len(parts) == 2:
                    def to_sec(t_str):
                        p = re.split('[:,]', t_str.strip())
                        if len(p) == 4:
                            return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2]) + int(p[3]) / 1000.0
                        return 0.0
                    start_s = to_sec(parts[0])
                    end_s = to_sec(parts[1])
                    text = "\\N".join(text_lines)
                    events.append((start_s, end_s, text))
    return events

def _ass_color(value: Any, fallback: str = "&H00FFFFFF") -> str:
    """Convert #RRGGBB / RRGGBB into ASS &HAABBGGRR color."""
    raw = str(value or "").strip()
    if raw.startswith("&H"):
        return raw
    raw = raw.lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{6}", raw):
        rr, gg, bb = raw[0:2], raw[2:4], raw[4:6]
        return f"&H00{bb}{gg}{rr}".upper()
    return fallback


def _overlay_position(cfg: dict[str, Any]) -> tuple[str, str]:
    position = str(cfg.get("position") or "bottom_right").strip().lower()
    mx = _to_int(cfg.get("margin_x"), 20)
    my = _to_int(cfg.get("margin_y"), 20)
    if position == "bottom_left":
        return str(mx), f"H-h-{my}"
    if position == "bottom_center":
        return "(W-w)/2", f"H-h-{my}"
    if position == "top_left":
        return str(mx), str(my)
    if position == "top_center":
        return "(W-w)/2", str(my)
    if position == "top_right":
        return f"W-w-{mx}", str(my)
    if position == "center":
        return "(W-w)/2", "(H-h)/2"
    return f"W-w-{mx}", f"H-h-{my}"


def create_master_subtitles_ass(
    out_ass_path: Path,
    vid_w: int,
    vid_h: int,
    dialogue_font_size: int,
    dialogue_margin_v: int,
    srt_path: str | None = None,
    segments: list | None = None,
    movie_title: str | None = None,
    title_font_size: int | None = None,
    title_margin_v: int | None = None,
    title_persistent: bool = False,
    style_cfg: dict[str, Any] | None = None,
) -> Path:
    """Build one ASS file for Vietnamese title + dialogue using render-profile styles."""
    style_cfg = style_cfg or {}
    title_cfg = style_cfg.get("title") if isinstance(style_cfg.get("title"), dict) else {}
    subtitle_cfg = style_cfg.get("subtitle") if isinstance(style_cfg.get("subtitle"), dict) else {}

    if title_font_size is None:
        title_font_size = max(44, int(round(vid_w * 0.068)))
    if title_margin_v is None:
        title_margin_v = max(35, int(round(vid_h * 0.10)))

    dialogue_font_size = _to_int(subtitle_cfg.get("font_size"), dialogue_font_size)
    dialogue_margin_v = _to_int(subtitle_cfg.get("margin_v"), dialogue_margin_v)
    title_font_size = _to_int(title_cfg.get("font_size"), title_font_size)
    title_margin_v = _to_int(title_cfg.get("margin_v"), title_margin_v)

    dialogue_font = str(subtitle_cfg.get("font") or "Arial")
    title_font = str(title_cfg.get("font") or "Arial")
    dialogue_primary = _ass_color(subtitle_cfg.get("color"), "&H00FFFFFF")  # &H00FFFFFF kept as safe white fallback
    dialogue_outline_color = _ass_color(subtitle_cfg.get("outline_color"), "&H00000000")
    title_primary = _ass_color(title_cfg.get("color"), "&H0000E6FF")
    title_outline_color = _ass_color(title_cfg.get("outline_color"), "&H00000000")

    dialogue_outline = _to_int(subtitle_cfg.get("outline_size"), 6)
    dialogue_bold = -1 if _to_bool(subtitle_cfg.get("bold"), True) else 0
    title_bold = -1 if _to_bool(title_cfg.get("bold"), True) else 0
    dialogue_alignment = _to_int(subtitle_cfg.get("alignment"), 2)
    title_alignment = _to_int(title_cfg.get("alignment"), 8)
    dialogue_margin_l = _to_int(subtitle_cfg.get("margin_l"), 20)
    dialogue_margin_r = _to_int(subtitle_cfg.get("margin_r"), 20)
    title_margin_l = _to_int(title_cfg.get("margin_l"), 30)
    title_margin_r = _to_int(title_cfg.get("margin_r"), 30)

    formatted_title = ""
    has_title_event = bool(movie_title and movie_title.strip() and _to_bool(title_cfg.get("enabled"), True))
    if has_title_event:
        raw_t = movie_title.strip()
        if _to_bool(title_cfg.get("uppercase"), True):
            raw_t = raw_t.upper()
        single_line = _to_bool(title_cfg.get("single_line", True), True)
        break_at = _to_int(title_cfg.get("line_break_at"), 0)
        if not single_line and break_at > 0 and len(raw_t) > break_at and " " in raw_t:
            words = raw_t.split()
            mid = len(words) // 2
            formatted_title = " ".join(words[:mid]) + "\\N" + " ".join(words[mid:])
        else:
            formatted_title = raw_t
            max_avail_w = max(200, vid_w - title_margin_l - title_margin_r - 20)
            est_w = len(formatted_title) * title_font_size * 0.60
            if est_w > max_avail_w and len(formatted_title) > 0:
                title_font_size = max(24, int(round(max_avail_w / (len(formatted_title) * 0.60))))

    title_outline = _to_int(title_cfg.get("outline_size"), max(3, int(round(title_font_size * 0.08))))

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {vid_w}
PlayResY: {vid_h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dialogue,{dialogue_font},{dialogue_font_size},{dialogue_primary},&H000000FF,{dialogue_outline_color},&H00000000,{dialogue_bold},0,0,0,100,100,0,0,3,{dialogue_outline},0,{dialogue_alignment},{dialogue_margin_l},{dialogue_margin_r},{dialogue_margin_v},1
Style: TitleCard,{title_font},{title_font_size},{title_primary},&H000000FF,{title_outline_color},&H00000000,{title_bold},0,0,0,100,100,0,0,1,{title_outline},0,{title_alignment},{title_margin_l},{title_margin_r},{title_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    event_lines: list[str] = []

    if has_title_event and formatted_title:
        if title_persistent or _to_bool(title_cfg.get("persistent"), False):
            event_lines.append(
                f"Dialogue: 1,0:00:00.00,9:59:59.00,TitleCard,,0,0,0,,{{\\q2\\b1}}{formatted_title}{{\\b0}}"
            )
        else:
            duration = max(0.5, _to_float(title_cfg.get("intro_duration"), 6.0))
            fade_in = _to_int(title_cfg.get("fade_in_ms"), 400)
            fade_out = _to_int(title_cfg.get("fade_out_ms"), 500)
            event_lines.append(
                f"Dialogue: 1,0:00:00.50,{format_ass_timestamp(0.5 + duration)},TitleCard,,0,0,0,,{{\\q2\\fad({fade_in},{fade_out})\\b1}}{formatted_title}{{\\b0}}"
            )

    if _to_bool(subtitle_cfg.get("enabled"), True):
        if segments:
            for seg in segments:
                text = getattr(seg, "text", "")
                if text and text.strip():
                    clean_t = text.strip().replace("\n", "\\N")
                    st = format_ass_timestamp(seg.start)
                    et = format_ass_timestamp(seg.end)
                    event_lines.append(f"Dialogue: 0,{st},{et},Dialogue,,0,0,0,,{clean_t}")
        elif srt_path and os.path.exists(srt_path):
            for st_s, et_s, text in parse_srt_file_to_events(srt_path):
                if text:
                    st = format_ass_timestamp(st_s)
                    et = format_ass_timestamp(et_s)
                    event_lines.append(f"Dialogue: 0,{st},{et},Dialogue,,0,0,0,,{text}")

    full_ass = header + "\n".join(event_lines) + "\n"
    out_ass_path.write_text(full_ass, encoding="utf-8")
    return out_ass_path


def process_video_sub_and_mute(
    input_video: str,
    output_video: str,
    srt_path: str | None = None,
    voice_audio: str | None = None,
    keep_bg_audio: bool = True,
    bg_volume: float = 0.10,
    blur_sub: bool = True,
    use_nvenc: bool = True,
    segments: list | None = None,
    movie_title: str | None = None,
    is_film_mode: bool = True,
    mask_mode: str = "black_bar",
    channel_cfg: dict[str, Any] | None = None,
) -> str:
    """
    Main production renderer.

    Besides the legacy arguments, channel_cfg can now carry a resolved v2 render profile,
    per-channel logo/cover assets, title/subtitle style and encoder settings.
    """
    channel_cfg = channel_cfg or {}
    render_cfg = channel_cfg.get("render") if isinstance(channel_cfg.get("render"), dict) else {}
    title_cfg = render_cfg.get("title") if isinstance(render_cfg.get("title"), dict) else {}
    subtitle_cfg = render_cfg.get("subtitle") if isinstance(render_cfg.get("subtitle"), dict) else {}
    bars_cfg = render_cfg.get("film_bars") if isinstance(render_cfg.get("film_bars"), dict) else {}
    logo_cfg = render_cfg.get("logo") if isinstance(render_cfg.get("logo"), dict) else {}
    cover_cfg = render_cfg.get("cover") if isinstance(render_cfg.get("cover"), dict) else {}
    encoder_cfg = render_cfg.get("encoder") if isinstance(render_cfg.get("encoder"), dict) else {}
    assets_cfg = channel_cfg.get("_assets") if isinstance(channel_cfg.get("_assets"), dict) else {}

    keep_bg_audio = _to_bool(channel_cfg.get("keep_bg_audio"), keep_bg_audio)
    bg_volume = _to_float(channel_cfg.get("bg_volume"), bg_volume)
    vocal_cut = _to_bool(render_cfg.get("vocal_cut", channel_cfg.get("vocal_cut", True)), True)
    slev = _to_float(render_cfg.get("slev", channel_cfg.get("slev", 0.5)), 0.5)
    mlev = _to_float(render_cfg.get("mlev", channel_cfg.get("mlev", 0.08)), 0.08)
    use_nvenc = _to_bool(encoder_cfg.get("use_nvenc"), use_nvenc)

    raw_movie_title = movie_title
    if not _to_bool(channel_cfg.get("show_title_card"), True) or not _to_bool(title_cfg.get("enabled"), True):
        movie_title = None

    is_wuby_mode = (mask_mode == "in_video_overlay" or _to_bool(render_cfg.get("ocr_enabled"), False))
    if mask_mode == "none":
        is_film_mode = False
        blur_sub = False
    elif mask_mode == "blur":
        is_film_mode = False
        blur_sub = True
    elif mask_mode == "black_bar":
        is_film_mode = True
    elif is_wuby_mode:
        is_film_mode = False
        blur_sub = False
    else:
        is_film_mode = True

    in_vid = Path(input_video)
    out_vid = Path(output_video)
    out_vid.parent.mkdir(parents=True, exist_ok=True)

    if out_vid.exists() and out_vid.stat().st_size > 500000:
        print(f"[VideoMerger] [RESUME] Video kết quả đã tồn tại hoàn chỉnh ({out_vid.stat().st_size / (1024*1024):.2f} MB): {out_vid}")
        return str(out_vid)

    tmp_out = out_vid.with_name(f"{out_vid.stem}.rendering.mp4")
    if tmp_out.exists():
        try:
            tmp_out.unlink()
        except Exception:
            pass

    if "BG_AUDIO_VOLUME" in os.environ:
        try:
            bg_volume = float(os.environ["BG_AUDIO_VOLUME"])
        except Exception:
            pass

    wuby_events = []
    if is_wuby_mode:
        try:
            import wuby_ocr_overlay
            cap_probe = cv2.VideoCapture(str(in_vid))
            probe_h = int(cap_probe.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1920)
            ocr_fps = 24.0
            if channel_cfg and isinstance(channel_cfg, dict):
                ocr_fps = float(channel_cfg.get("ocr_fps", channel_cfg.get("sample_fps", 24.0)))
            wuby_events = wuby_ocr_overlay.scan_video_text_events(str(in_vid), sample_fps=ocr_fps)
            wuby_events = wuby_ocr_overlay.match_ocr_events_with_subtitles(
                wuby_events, segments=segments, srt_path=srt_path,
                movie_title=raw_movie_title, vid_h=probe_h
            )
            cleaned_temp = wuby_ocr_overlay.clean_video_ocr_backgrounds(str(in_vid), str(output_video), wuby_events)
            if cleaned_temp and os.path.exists(cleaned_temp):
                in_vid = Path(cleaned_temp)
        except Exception as ocr_err:
            print(f"[VideoMerger] [WubyOCR] Cảnh báo lỗi OCR overlay: {ocr_err}")

    inputs = ["-i", str(in_vid)]
    next_input_index = 1
    has_voice = voice_audio and os.path.exists(voice_audio) and os.path.getsize(voice_audio) > 0
    voice_index = None
    if has_voice:
        inputs += ["-i", str(voice_audio)]
        voice_index = next_input_index
        next_input_index += 1

    logo_path = assets_cfg.get("logo_path") or channel_cfg.get("logo_path")
    cover_path = assets_cfg.get("cover_path") or channel_cfg.get("cover_path")
    has_logo = _to_bool(logo_cfg.get("enabled"), True) and _file_exists(logo_path)
    has_cover = _to_bool(cover_cfg.get("enabled"), False) and _file_exists(cover_path)

    cover_index = None
    logo_index = None
    if has_cover:
        inputs += ["-i", str(cover_path)]
        cover_index = next_input_index
        next_input_index += 1
    if has_logo:
        inputs += ["-i", str(logo_path)]
        logo_index = next_input_index
        next_input_index += 1

    filters: list[str] = []
    current_label = "[0:v]"

    cap_probe = cv2.VideoCapture(str(in_vid))
    vid_w = int(cap_probe.get(cv2.CAP_PROP_FRAME_WIDTH) or 1080)
    vid_h = int(cap_probe.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1920)
    cap_probe.release()

    top_bar, bot_bar = detect_letterbox_bars(str(in_vid))
    top_boxes = detect_top_watermark_box(str(in_vid), top_offset=0, bottom_offset=0)

    cover_top_h = 0
    if top_bar >= 24:
        cover_top_h = top_bar
    elif top_boxes:
        max_box_bottom = max(b["y"] + b["h"] for b in top_boxes)
        cover_top_h = max(60, min(int(vid_h * 0.12), ((max_box_bottom + 10) // 2) * 2))

    has_top_cover = cover_top_h >= 24
    top_cover_cfg = render_cfg.get("top_cover") if isinstance(render_cfg.get("top_cover"), dict) else {}
    top_cover_enabled = _to_bool(top_cover_cfg.get("enabled"), True)

    # Review-film behavior requested by the user: wipe the full top strip to black,
    # then draw the Vietnamese title on top via ASS. (Never apply to wuby mode!)
    if not is_wuby_mode and has_top_cover and top_cover_enabled and str(top_cover_cfg.get("mode") or "black").lower() == "black":
        filters.append(f"{current_label}drawbox=x=0:y=0:w=iw:h={cover_top_h}:color=black@1:t=fill[vtopblack]")
        current_label = "[vtopblack]"
        title_fs = _to_int(title_cfg.get("font_size"), max(32, int(round(cover_top_h * _to_float(title_cfg.get("font_ratio_on_bar"), 0.44)))))
        title_mv = _to_int(title_cfg.get("margin_v"), max(8, int(round((cover_top_h - title_fs) / 2))))
        title_persistent = _to_bool(title_cfg.get("persistent_on_top_bar"), True)
        print(f"[VideoMerger] Đè đen toàn bộ vùng chữ/viền trên: {cover_top_h}px")
    else:
        title_fs = _to_int(title_cfg.get("font_size"), max(44, int(round(vid_w * _to_float(title_cfg.get("font_ratio"), 0.068)))))
        title_mv = _to_int(title_cfg.get("margin_v"), max(35, int(round(vid_h * 0.10))))
        title_persistent = _to_bool(title_cfg.get("persistent"), False)

    detected_sub_box = None
    if blur_sub or is_film_mode:
        detected_sub_box = detect_subtitle_box_20_frames(str(in_vid), segments=segments)

    if is_film_mode:
        bars_info = compute_film_black_bars(
            vid_w,
            vid_h,
            detected_sub_box,
            top_ratio=_to_float(bars_cfg.get("top_ratio"), 0.10),
            bottom_ratio=_to_float(bars_cfg.get("bottom_ratio"), 0.22),
            bottom_max_ratio=_to_float(bars_cfg.get("bottom_max_ratio"), 0.35),
        )
        top_h = bars_info["top_h"]
        bot_h = bars_info["bottom_h"]
        dialogue_fs = _to_int(subtitle_cfg.get("font_size"), bars_info["dialogue_fs"])
        dialogue_mv = _to_int(subtitle_cfg.get("margin_v"), bars_info["dialogue_mv"])

        bot_y = vid_h - bot_h
        # Keep these exact patterns for regression tests and OC-010 behavior.
        filters.append(f"{current_label}drawbox=x=0:y=0:w=iw:h={top_h}:color=black@1:t=fill[vtopblack]")
        filters.append(f"[vtopblack]drawbox=x=0:y={bot_y}:w=iw:h={bot_h}:color=black@1:t=fill[vblackbars]")
        current_label = "[vblackbars]"
        print(f"[VideoMerger] Film profile -> dải đen trên={top_h}px, dưới={bot_h}px")
    elif blur_sub:
        if detected_sub_box:
            bx = max(0, detected_sub_box.get("x", 0))
            by = max(0, detected_sub_box.get("y", int(vid_h * 0.75)))
            bw = min(vid_w - bx, detected_sub_box.get("w", vid_w))
            bh = min(vid_h - by, detected_sub_box.get("h", int(vid_h * 0.22)))
        else:
            bx, by, bw, bh = 0, int(vid_h * 0.75), vid_w, int(vid_h * 0.22)
        bw = (bw // 2) * 2
        bh = (bh // 2) * 2
        blur_radius = _to_int(render_cfg.get("blur_strength"), 18)
        filters.append(f"{current_label}split[vmain][vsubarea]")
        filters.append(f"[vsubarea]crop={bw}:{bh}:{bx}:{by},boxblur={blur_radius}:6[vblurredsub]")
        filters.append(f"[vmain][vblurredsub]overlay={bx}:{by}[vblurred]")
        current_label = "[vblurred]"
        dialogue_fs = _to_int(subtitle_cfg.get("font_size"), max(28, int(round(vid_h * 0.056))))
        dialogue_mv = _to_int(subtitle_cfg.get("margin_v"), max(16, int(round(vid_h * 0.065))))
    else:
        dialogue_fs = _to_int(subtitle_cfg.get("font_size"), max(28, int(round(vid_h * 0.056))))
        dialogue_mv = _to_int(subtitle_cfg.get("margin_v"), max(16, int(round(vid_h * 0.065))))

    burn_sub_enabled = _to_bool(channel_cfg.get("burn_sub"), True) and _to_bool(subtitle_cfg.get("enabled"), True)
    has_sub = burn_sub_enabled and ((srt_path and os.path.exists(srt_path) and os.path.getsize(srt_path) > 0) or bool(segments))
    if movie_title or has_sub or (is_wuby_mode and wuby_events):
        ass_path = out_vid.parent / f"{out_vid.stem}_styled.ass"
        if is_wuby_mode and wuby_events:
            try:
                import wuby_ocr_overlay
                scenes = []
                for ev in wuby_events:
                    if "scene_start" in ev and "scene_end" in ev:
                        s_item = {"scene_id": ev.get("scene_id", 0), "start": float(ev["scene_start"]), "end": float(ev["scene_end"])}
                        if s_item not in scenes:
                            scenes.append(s_item)
                scenes.sort(key=lambda s: s["start"])

                wuby_ocr_overlay.build_wuby_ass_subtitles(
                    out_ass_path=ass_path,
                    vid_w=vid_w,
                    vid_h=vid_h,
                    ocr_events=wuby_events,
                    movie_title=movie_title,
                    title_config={"enabled": False},
                    scene_ranges=scenes or None
                )
            except Exception as wuby_ass_err:
                print(f"[VideoMerger] Lỗi build Wuby ASS: {wuby_ass_err}")
                create_master_subtitles_ass(
                    out_ass_path=ass_path,
                    vid_w=vid_w,
                    vid_h=vid_h,
                    dialogue_font_size=dialogue_fs,
                    dialogue_margin_v=dialogue_mv,
                    srt_path=srt_path if burn_sub_enabled else None,
                    segments=segments if burn_sub_enabled else None,
                    movie_title=movie_title,
                    title_font_size=title_fs,
                    title_margin_v=title_mv,
                    title_persistent=title_persistent,
                    style_cfg=render_cfg,
                )
        else:
            create_master_subtitles_ass(
                out_ass_path=ass_path,
                vid_w=vid_w,
                vid_h=vid_h,
                dialogue_font_size=dialogue_fs,
                dialogue_margin_v=dialogue_mv,
                srt_path=srt_path if burn_sub_enabled else None,
                segments=segments if burn_sub_enabled else None,
                movie_title=movie_title,
                title_font_size=title_fs,
                title_margin_v=title_mv,
                title_persistent=title_persistent,
                style_cfg=render_cfg,
            )
        clean_ass = escape_subtitle_path_windows(ass_path)
        filters.append(f"{current_label}subtitles='{clean_ass}'[vsubout]")
        current_label = "[vsubout]"

    # Per-channel cover: by default replaces the first N seconds with cover.jpg/cover.png.
    if has_cover and cover_index is not None and str(cover_cfg.get("mode") or "intro").lower() == "intro":
        duration = max(0.2, _to_float(cover_cfg.get("duration"), 1.2))
        fit = str(cover_cfg.get("fit") or "cover").lower()
        if fit == "contain":
            cover_filter = f"[{cover_index}:v]scale={vid_w}:{vid_h}:force_original_aspect_ratio=decrease,pad={vid_w}:{vid_h}:(ow-iw)/2:(oh-ih)/2,format=rgba[coverimg]"
        else:
            cover_filter = f"[{cover_index}:v]scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,crop={vid_w}:{vid_h},format=rgba[coverimg]"
        filters.append(cover_filter)
        filters.append(f"{current_label}[coverimg]overlay=0:0:enable='between(t,0,{duration:.3f})'[vcover]")
        current_label = "[vcover]"
        print(f"[VideoMerger] Cover kênh: {Path(str(cover_path)).name} ({duration:.1f}s)")

    # Per-channel low-opacity logo/watermark, usually hidden subtly at the bottom.
    if has_logo and logo_index is not None:
        opacity = max(0.0, min(_to_float(logo_cfg.get("opacity"), 0.12), 1.0))
        logo_width = _to_int(logo_cfg.get("width"), 0)
        if logo_width <= 0:
            logo_width = max(48, int(round(vid_w * _to_float(logo_cfg.get("width_ratio"), 0.18))))
        x_expr, y_expr = _overlay_position(logo_cfg)
        filters.append(f"[{logo_index}:v]scale={logo_width}:-1,format=rgba,colorchannelmixer=aa={opacity}[chlogo]")
        filters.append(f"{current_label}[chlogo]overlay={x_expr}:{y_expr}[vlogo]")
        current_label = "[vlogo]"
        print(f"[VideoMerger] Logo kênh: {Path(str(logo_path)).name}, opacity={opacity:.2f}, pos={logo_cfg.get('position', 'bottom_right')}")

    audio_label = None
    if has_voice and voice_index is not None:
        if keep_bg_audio and bg_volume > 0.001:
            if vocal_cut:
                filters.append(f"[0:a]stereotools=mlev={mlev}:slev={slev},volume={bg_volume}[abg]")
            else:
                filters.append(f"[0:a]volume={bg_volume}[abg]")
            filters.append(f"[{voice_index}:a]volume=1.0[avoice]")
            filters.append("[abg][avoice]amix=inputs=2:duration=first:dropout_transition=2[aout]")
            audio_label = "[aout]"
        else:
            filters.append(f"[{voice_index}:a]volume=1.0[avoice]")
            audio_label = "[avoice]"

    ffmpeg_bin = _ffmpeg_executable()

    def run_cmd(encoder: str, extra_args: list[str]):
        cmd = [ffmpeg_bin, "-y", "-loglevel", "error", *inputs]
        if filters:
            cmd += ["-filter_complex", ";".join(filters), "-map", current_label]
        else:
            cmd += ["-map", "0:v:0"]

        if audio_label:
            cmd += ["-map", audio_label, "-c:a", "aac", "-b:a", str(encoder_cfg.get("audio_bitrate", "96k")), "-ar", "44100"]
        else:
            cmd += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", str(encoder_cfg.get("audio_bitrate", "96k")), "-ar", "44100"]

        cmd += ["-c:v", encoder, *extra_args, "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", str(tmp_out)]
        subprocess.run(cmd, check=True)
        if tmp_out.exists():
            if out_vid.exists():
                out_vid.unlink()
            tmp_out.rename(out_vid)

    nvenc_preset = str(encoder_cfg.get("nvenc_preset", "p4"))
    cq = str(_to_int(encoder_cfg.get("cq"), 28))
    bitrate = str(encoder_cfg.get("bitrate", "950k"))
    maxrate = str(encoder_cfg.get("maxrate", "1350k"))
    bufsize = str(encoder_cfg.get("bufsize", "2500k"))
    crf = str(_to_int(encoder_cfg.get("crf"), 28))

    try:
        if use_nvenc:
            run_cmd("h264_nvenc", [
                "-preset", nvenc_preset,
                "-rc", "vbr",
                "-cq", cq,
                "-b:v", bitrate,
                "-maxrate", maxrate,
                "-bufsize", bufsize,
                "-profile:v", "high",
            ])
        else:
            run_cmd("libx264", [
                "-preset", str(encoder_cfg.get("x264_preset", "veryfast")),
                "-crf", crf,
                "-maxrate", maxrate,
                "-bufsize", bufsize,
                "-profile:v", "high",
            ])
    except Exception as err:
        if use_nvenc:
            print(f"[VideoMerger] NVENC failed ({err}), falling back to libx264...")
            run_cmd("libx264", [
                "-preset", str(encoder_cfg.get("x264_preset", "veryfast")),
                "-crf", crf,
                "-maxrate", maxrate,
                "-bufsize", bufsize,
                "-profile:v", "high",
            ])
        else:
            raise

    return str(out_vid)
