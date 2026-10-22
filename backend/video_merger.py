from __future__ import annotations

# Compatibility facade: support both backend.video_merger and legacy video_merger imports.
if __package__:
    from .render_modules.config_values import _to_bool, _to_float, _to_int, _file_exists
    from .render_modules.subtitle_text import (
        format_ass_timestamp, parse_srt_file_to_events, _ass_color,
        format_balanced_sub_text, make_karaoke_ass_text,
    )
else:
    from render_modules.config_values import _to_bool, _to_float, _to_int, _file_exists
    from render_modules.subtitle_text import (
        format_ass_timestamp, parse_srt_file_to_events, _ass_color,
        format_balanced_sub_text, make_karaoke_ass_text,
    )
from channel_manager import resolve_logo_text
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





def _ffmpeg_executable() -> str:
    configured = os.environ.get("FFMPEG_BINARY") or os.environ.get("FFMPEG_PATH")
    if configured and Path(configured).is_file():
        return configured
    found = shutil.which("ffmpeg")
    if found:
        return found
    local_bin = Path(__file__).resolve().parent.parent / "tools" / "bin" / "ffmpeg.exe"
    if local_bin.is_file():
        return str(local_bin)
    local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    candidates = []
    if local_appdata:
        candidates.append(Path(local_appdata) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe")
        for pkg_ffmpeg in Path(local_appdata).glob("Microsoft/WinGet/Packages/Gyan.FFmpeg*/**/ffmpeg.exe"):
            candidates.append(pkg_ffmpeg)
    candidates.append(Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe")
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except Exception:
            pass
    return "ffmpeg"

def get_video_duration(video_path: str | Path) -> float:
    """Trả về tổng thời lượng video (giây) bằng OpenCV."""
    try:
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
            cap.release()
            if frames > 0 and fps > 0:
                return float(frames / fps)
    except Exception:
        pass
    return 0.0

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
            
        # Thêm ngẫu nhiên 16 bytes vào cuối file để thay đổi MD5
        try:
            with open(out_vid, 'ab') as f:
                f.write(os.urandom(16))
        except Exception as e:
            print(f"Lỗi khi đổi MD5: {e}")

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

def detect_letterbox_bars(video_path: str, num_samples: int = 24) -> tuple[int, int]:
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
            
        # Tỷ lệ pixel đen (< 35) trên mỗi dòng y cho từng frame (bao gồm cả chuẩn nén video)
        black_ratios = [np.mean(fg < 35, axis=1) for fg in frames_gray]
        avg_black_ratio = np.mean(black_ratios, axis=0)
        
        # 1. Tìm viền đen trên (tối đa 32% chiều cao video)
        max_top_search = int(h * 0.32)
        top_bar = 0
        for y in range(max_top_search):
            if avg_black_ratio[y] >= 0.65:
                top_bar = y + 1
            else:
                lookahead = avg_black_ratio[y:min(y+4, max_top_search)]
                if len(lookahead) > 0 and np.all(lookahead < 0.65):
                    break
                    
        # 2. Tìm viền đen dưới (tối đa 32% chiều cao video từ đáy)
        min_bot_search = int(h * 0.68)
        bot_bar = 0
        for y in range(h - 1, min_bot_search, -1):
            if avg_black_ratio[y] >= 0.65:
                bot_bar = h - y
            else:
                lookahead = avg_black_ratio[max(min_bot_search, y-3):y+1]
                if len(lookahead) > 0 and np.all(lookahead < 0.65):
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

def detect_vertical_left_watermark(video_path: str, top_offset: int = 0, bottom_offset: int = 0) -> list[dict]:
    """
    Quét dải lề trái video (x < 150) để phát hiện cột chữ Trung dọc (vertical title / account watermark)
    xuất hiện tĩnh hoặc liên tục qua nhiều khung hình.
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
        sample_indices = np.linspace(int(total_frames * 0.05), int(total_frames * 0.90), 15, dtype=int)
        masks = []
        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret and frame is not None:
                roi = frame[:int(usable_h * 0.45), :160]
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                white = cv2.inRange(gray, 200, 255)
                masks.append(white > 0)
        cap.release()
        if len(masks) < 5:
            return []
            
        presence = np.mean(masks, axis=0)
        static_mask = (presence >= 0.35).astype(np.uint8) * 255
        kernel_vert = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 35))
        closed = cv2.morphologyEx(static_mask, cv2.MORPH_CLOSE, kernel_vert)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        vert_boxes = []
        for c in contours:
            x, y, bw, bh = cv2.boundingRect(c)
            if x < 120 and bh >= 70 and bw <= 85:
                bx1 = max(0, ((x - 6) // 2) * 2)
                by1 = max(0, ((y - 6) // 2) * 2)
                bx2 = min(w, ((x + bw + 8) // 2) * 2)
                by2 = min(h, ((y + bh + 8) // 2) * 2)
                vert_boxes.append({'x': bx1, 'y': by1, 'w': bx2 - bx1, 'h': by2 - by1})
        if vert_boxes:
            print(f"[VideoMerger] Phát hiện {len(vert_boxes)} khối chữ Trung dọc bên trái: {vert_boxes}")
        return vert_boxes
    except Exception as e:
        print(f"[VideoMerger] Lỗi quét chữ dọc bên trái: {e}")
        return []

def detect_vertical_right_watermark(video_path: str, top_offset: int = 0, bottom_offset: int = 0) -> list[dict]:
    """Find narrow, persistent vertical lettering in the right edge only.

    Requiring repeated bright pixels and a tall, narrow contour avoids
    blurring arbitrary signs or moving subjects in the rest of the frame.
    """
    cap = None
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return []
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        usable_h = h - top_offset - bottom_offset
        if frames < 10 or w < 180 or usable_h < 160:
            return []

        roi_x = w - 160
        roi_h = min(h, int(usable_h * 0.45))
        masks = []
        for idx in np.linspace(int(frames * 0.05), int(frames * 0.90), 15, dtype=int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, frame = cap.read()
            if ok and frame is not None:
                gray = cv2.cvtColor(frame[:roi_h, roi_x:], cv2.COLOR_BGR2GRAY)
                masks.append(cv2.inRange(gray, 200, 255) > 0)
        if len(masks) < 5:
            return []

        static = (np.mean(masks, axis=0) >= 0.35).astype(np.uint8) * 255
        closed = cv2.morphologyEx(
            static, cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (15, 35)),
        )
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for contour in contours:
            x, y, bw, bh = cv2.boundingRect(contour)
            if x >= 120 or bh < 70 or bw > 85 or bh < bw * 2.5:
                continue
            bx1 = max(roi_x, ((roi_x + x - 6) // 2) * 2)
            by1 = max(0, ((y - 6) // 2) * 2)
            bx2 = min(w, ((roi_x + x + bw + 8) // 2) * 2)
            by2 = min(h, ((y + bh + 8) // 2) * 2)
            if bx2 > bx1 and by2 > by1:
                boxes.append({'x': bx1, 'y': by1, 'w': bx2 - bx1, 'h': by2 - by1})
        if boxes:
            print(f"[VideoMerger] Phát hiện {len(boxes)} vùng chữ dọc cạnh phải: {boxes}")
        return boxes
    except Exception as exc:
        print(f"[VideoMerger] Lỗi quét chữ dọc bên phải: {exc}")
        return []
    finally:
        if cap is not None:
            cap.release()

def detect_subtitle_box_20_frames(
    video_path: str,
    segments: list | None = None,
    top_offset: int = 0,
    bottom_offset: int = 0
) -> dict | None:
    """
    Xác định vị trí lớn nhất của phụ đề theo thuật toán:
    1. Chọn 20 đoạn có nội dung câu dài nhất từ bước bóc tách lời thoại
    2. Lấy 2 khung hình trên mỗi đoạn đó (tại 35% và 70% thời lượng câu) -> 40 khung hình
    3. Quét trong vùng phụ đề thoại (45% đến 90% chiều cao video)
    4. Phân cụm (Clustering) toạ độ Y để xác định chính xác dòng phụ đề thoại chính
    5. Tính Max Bounding Box + padding TRÊN +3%, DƯỚI +3% chiều cao video
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

        # 1. Chọn 20 đoạn có nội dung dài nhất từ lời thoại và lấy 2 khung hình mỗi đoạn
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
            top_segments = sorted_segs[:20]
            for seg in top_segments:
                s_start, s_end = get_times(seg)
                if s_end > s_start:
                    t1 = s_start + (s_end - s_start) * 0.35
                    t2 = s_start + (s_end - s_start) * 0.70
                else:
                    t1 = s_start
                    t2 = s_start + 0.5
                timestamps.extend([t1, t2])
            print(f"[VideoMerger] Lấy khung hình từ {len(top_segments)} câu dài nhất (tổng cộng {len(timestamps)} mốc thời gian)...")
        else:
            timestamps = list(np.linspace(duration_sec * 0.05, duration_sec * 0.95, 30))
        
        detected_boxes = []
        
        # 2. Vùng tập trung phụ đề thoại: Quét từ 55% đến 98.5% chiều cao phim khả dụng (tránh cắt mất phụ đề sát mép đáy)
        roi_top = top_offset + int(usable_h * 0.55)
        roi_bottom = top_offset + min(usable_h, int(usable_h * 0.985))
        
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
            closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_close)
            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for c in contours:
                x, y, bw, bh = cv2.boundingRect(c)
                cx = x + bw / 2.0
                # Tiêu chuẩn phụ đề thoại:
                # - Nằm ở dải trung tâm màn hình (lệch tâm <= 35% chiều rộng)
                # - Chiều rộng văn bản bw >= 40, dạng chữ ngang (bw / bh >= 1.2)
                # - Chiều cao chữ trong ngưỡng 14px đến 12% chiều cao video
                if abs(cx - width / 2.0) <= (width * 0.35) and bw >= 40 and 14 <= bh <= int(usable_h * 0.12) and (bw / float(bh)) >= 1.2:
                    abs_y1 = roi_top + y
                    abs_y2 = abs_y1 + bh
                    cy = (abs_y1 + abs_y2) / 2.0
                    detected_boxes.append({'x1': x, 'x2': x + bw, 'y1': abs_y1, 'y2': abs_y2, 'w': bw, 'h': bh, 'center_y': cy})
                
        cap.release()
        
        if not detected_boxes:
            print("[VideoMerger] Không phát hiện phụ đề cứng trong khung hình.")
            return None
            
        # 3. Phân cụm theo bin 25px để xác định chính xác dòng phụ đề thoại chính (có tần suất xuất hiện cao nhất)
        bins = {}
        for b in detected_boxes:
            bin_idx = int(round(b['center_y'] / 25.0)) * 25
            bins.setdefault(bin_idx, []).append(b)

        sorted_bins = sorted(bins.items(), key=lambda x: len(x[1]), reverse=True)
        dominant_boxes = sorted_bins[0][1]
        
        all_cys = [b['center_y'] for b in dominant_boxes]
        med_cy = float(np.median(all_cys))
        consistent = [b for b in dominant_boxes if abs(b['center_y'] - med_cy) <= 18]
        if not consistent:
            consistent = dominant_boxes
            
        final_cy = int(round(np.median([b['center_y'] for b in consistent])))
        line_h = int(round(np.median([b['h'] for b in consistent])))
        
        # 4. Toạ độ mép chữ gốc
        final_y1 = max(0, ((final_cy - line_h // 2) // 2) * 2)
        final_y2 = min(height, ((final_cy + (line_h + 1) // 2) // 2) * 2)
        
        # 5. Thêm padding dọc thon gọn: ~1.2% chiều cao video (~13px) để dải mờ vừa vặn, không dày cộm
        pad_v = max(6, int(round(height * 0.012)))
        padded_y1 = max(0, ((final_y1 - pad_v) // 2) * 2)
        padded_y2 = min(height, ((final_y2 + pad_v) // 2) * 2)
        padded_h = padded_y2 - padded_y1
        
        # 6. Chiều rộng lấy chính xác theo phạm vi phụ đề phát hiện được + padding ngang
        raw_min_x = min(b['x1'] for b in consistent)
        raw_max_x = max(b['x2'] for b in consistent)
        box_x1 = max(0, ((raw_min_x - 35) // 2) * 2)
        box_x2 = min(width, ((raw_max_x + 36) // 2) * 2)
        box_w = box_x2 - box_x1
        
        print(f"[VideoMerger] Bắt toạ độ sub chuẩn xác (20 câu dài nhất): X={box_x1}..{box_x2} (Gốc: Y={final_y1}..{final_y2}, sau padding gọn: Y={padded_y1}..{padded_y2}, Cao={padded_h}px, Rộng={box_w}px, CenterY={final_cy})")
        return {
            "x": box_x1,
            "y": padded_y1,
            "w": box_w,
            "h": padded_h,
            "raw_y1": final_y1,
            "raw_y2": final_y2,
            "center_y": final_cy,
            "pad_v": pad_v,
            "vid_w": width,
            "vid_h": height,
        }
    except Exception as e:
        print(f"[VideoMerger] Lỗi quét toạ độ sub bằng OpenCV: {e}")
        return None





def _overlay_position(cfg: dict[str, Any]) -> tuple[str, str]:
    position = str(cfg.get("position") or "bottom_right").strip().lower()
    mx = _to_int(cfg.get("margin_x"), 20)
    my = _to_int(cfg.get("margin_y"), 20)
    if position in ("floating", "floating_drift", "chay_an", "moving", "drift"):
        speed_x = _to_float(cfg.get("speed_x", 45), 45.0)
        speed_y = _to_float(cfg.get("speed_y", 30), 30.0)
        return f"(W-w)/2+(W-w)*0.38*sin(2*PI*t/{speed_x:.1f})", f"(H-h)/2+(H-h)*0.30*cos(2*PI*t/{speed_y:.1f})"
    if position in ("drift_bottom", "chay_day", "bottom_drift"):
        speed_x = _to_float(cfg.get("speed_x", 35), 35.0)
        return f"(W-w)/2+(W-w)*0.40*sin(2*PI*t/{speed_x:.1f})", f"H-h-{my}"
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
    caption_regions: list | None = None,
    sub_pos_center: tuple[float, float] | None = None,
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

    is_karaoke = (str(subtitle_cfg.get("style_mode", "")).lower() == "karaoke")
    dialogue_font = str(subtitle_cfg.get("font") or "Arial")
    title_font = str(title_cfg.get("font") or "Arial")
    dialogue_primary = _ass_color(subtitle_cfg.get("color"), "&H0000E6FF" if is_karaoke else "&H00FFFFFF")
    dialogue_secondary = _ass_color(subtitle_cfg.get("secondary_color"), "&H00FFFFFF" if is_karaoke else "&H000000FF")
    dialogue_outline_color = _ass_color(subtitle_cfg.get("outline_color"), "&H00000000")
    title_primary = _ass_color(title_cfg.get("color"), "&H0000E6FF")
    title_outline_color = _ass_color(title_cfg.get("outline_color"), "&H00000000")

    dialogue_outline = _to_float(subtitle_cfg.get("outline_size"), 3.5 if is_karaoke else 3)
    dialogue_shadow = _to_float(subtitle_cfg.get("shadow_size"), 1.5 if is_karaoke else 0)
    dialogue_border_style = _to_int(subtitle_cfg.get("border_style"), 1)
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
Style: Dialogue,{dialogue_font},{dialogue_font_size},{dialogue_primary},{dialogue_secondary},{dialogue_outline_color},&H00000000,{dialogue_bold},0,0,0,100,100,0,0,{dialogue_border_style},{dialogue_outline},{dialogue_shadow},{dialogue_alignment},{dialogue_margin_l},{dialogue_margin_r},{dialogue_margin_v},1
Style: TitleCard,{title_font},{title_font_size},{title_primary},&H000000FF,{title_outline_color},&H00000000,{title_bold},0,0,0,100,100,0,0,1,{title_outline},0,{title_alignment},{title_margin_l},{title_margin_r},{title_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    event_lines: list[str] = []

    if has_title_event and formatted_title:
        if title_persistent or _to_bool(title_cfg.get("persistent"), False):
            max_end = 0.0
            if segments:
                max_end = max((float(getattr(s, "end", 0.0)) for s in segments), default=0.0)
            elif srt_path and os.path.exists(srt_path):
                events = parse_srt_file_to_events(srt_path)
                if events:
                    max_end = max((float(et) for _, et, _ in events), default=0.0)
            if max_end <= 0.0:
                max_end = 600.0
            event_lines.append(
                f"Dialogue: 1,0:00:00.00,{format_ass_timestamp(max_end)},TitleCard,,0,0,0,,{{\\q2\\b1}}{formatted_title}{{\\b0}}"
            )
        else:
            duration = max(0.5, _to_float(title_cfg.get("intro_duration"), 6.0))
            fade_in = _to_int(title_cfg.get("fade_in_ms"), 400)
            fade_out = _to_int(title_cfg.get("fade_out_ms"), 500)
            event_lines.append(
                f"Dialogue: 1,0:00:00.50,{format_ass_timestamp(0.5 + duration)},TitleCard,,0,0,0,,{{\\q2\\fad({fade_in},{fade_out})\\b1}}{formatted_title}{{\\b0}}"
            )

    if _to_bool(subtitle_cfg.get("enabled"), True):
        from subtitle_regions import positioned_parts
        source_events = []
        if segments:
            for seg in segments:
                get = seg.get if isinstance(seg, dict) else lambda k, default=None: getattr(seg, k, default)
                source_events.append((float(get('start', 0)), float(get('end', 0)), get('text', '')))
        elif srt_path and os.path.exists(srt_path):
            source_events = parse_srt_file_to_events(srt_path)
        for start, end, text in source_events:
            if not text or not text.strip() or end <= start:
                continue
            clean = format_balanced_sub_text(text.strip(), max_chars=34)
            if is_karaoke:
                clean = make_karaoke_ass_text(clean, end - start)
            if caption_regions and caption_regions[0].get('status') == 'existing_bottom_bar':
                box = caption_regions[0]['box']
                cx, cy = box['x'] + box['w']/2, box['y'] + box['h']/2
                parts = [(start, end, f"{{\\an5\\pos({cx:.1f},{cy:.1f})\\q2}}{clean}")]
            elif caption_regions:
                parts = positioned_parts(start, end, clean, caption_regions, dialogue_font_size, vid_w, vid_h)
            elif sub_pos_center:
                cx, cy = sub_pos_center
                parts = [(start, end, f"{{\\an5\\pos({cx:.1f},{cy:.1f})\\q2}}{clean}")]
            else:
                parts = [(start, end, clean)]
            for a, b, content in parts:
                event_lines.append(f"Dialogue: 0,{format_ass_timestamp(a)},{format_ass_timestamp(b)},Dialogue,,0,0,0,,{content}")

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
    wuby_studio_cfg = channel_cfg.get("wuby_studio") if isinstance(channel_cfg.get("wuby_studio"), dict) else {}
    is_editorial_card = channel_cfg.get("render_profile") in ("wuby_v7_editorial", "wuby_editorial") or (
        channel_cfg.get("workflow") == "wuby" and mask_mode != "in_video_overlay" and channel_cfg.get("mask_mode") != "in_video_overlay"
    )
    if is_editorial_card and wuby_studio_cfg.get("enabled", True) and (wuby_studio_cfg or channel_cfg.get("workflow") == "wuby"):
        from wuby_studio.bridge import render_legacy_call
        return render_legacy_call(input_video, output_video, srt_path, voice_audio, segments, movie_title, channel_cfg)

    render_cfg = channel_cfg.get("render") if isinstance(channel_cfg.get("render"), dict) else {}
    detection_cfg = channel_cfg.get("subtitle_detection") or {}
    precise_blur = mask_mode == "blur_sub_black" and detection_cfg.get("mode") == "lower_third_precise"
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
    elif mask_mode == "blur_sub_black":
        is_film_mode = False
        blur_sub = False  # handled separately in the elif chain below
    elif mask_mode == "black_bar":
        is_film_mode = True
    elif is_wuby_mode:
        is_film_mode = False
        blur_sub = False
    elif mask_mode in ["sub_black_bar", "sub_box", "black_box"]:
        is_film_mode = False
        blur_sub = False
    else:
        is_film_mode = True

    in_vid = Path(input_video)
    out_vid = Path(output_video)
    out_vid.parent.mkdir(parents=True, exist_ok=True)

    force_render = _to_bool(channel_cfg.get("force_render"), False)
    dialogue_replace_enabled = isinstance(channel_cfg.get("dialogue_replace"), dict) and _to_bool(channel_cfg.get("dialogue_replace", {}).get("enabled"), False)
    regions_report = out_vid.with_suffix(".subtitle_regions.json")
    needs_regions = (mask_mode in {"black_bar", "sub_black_bar", "sub_box", "black_box"} or precise_blur) and not is_wuby_mode
    geometry_current = not needs_regions or (regions_report.exists() and regions_report.stat().st_mtime >= max(Path(__file__).stat().st_mtime, Path(__file__).with_name("subtitle_regions.py").stat().st_mtime))
    if out_vid.exists() and out_vid.stat().st_size > 500000 and not force_render and not dialogue_replace_enabled and geometry_current:
        print(f"[VideoMerger] [RESUME] Video kết quả đã tồn tại ({out_vid.stat().st_size / (1024*1024):.2f} MB): {out_vid}")
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
            probe_w = int(cap_probe.get(cv2.CAP_PROP_FRAME_WIDTH) or 1080)
            probe_h = int(cap_probe.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1920)
            cap_probe.release()
            ocr_fps = 24.0
            if channel_cfg and isinstance(channel_cfg, dict):
                ocr_fps = float(channel_cfg.get("ocr_fps", channel_cfg.get("sample_fps", 24.0)))

            preflight = channel_cfg.get("_wuby_preflight") if isinstance(channel_cfg.get("_wuby_preflight"), dict) else {}
            preflight_has_ocr = bool(preflight) and "ocr_events" in preflight
            if preflight_has_ocr:
                # Preflight already scanned and matched OCR tracks before TTS/render.
                # Reuse exactly that geometry so analysis and final render cannot disagree.
                wuby_events = preflight.get("ocr_events") or []
                print(f"[VideoMerger] [WubyPreflight] Reuse {len(wuby_events)} OCR tracks @ {ocr_fps:.2f}fps plan")
                wuby_events = wuby_ocr_overlay.filter_semantic_ocr_events(wuby_events)
                # Always rematch text assignment. Geometry stays from preflight, while
                # current matching rules can fix watermark / duplicate-caption bugs.
                wuby_events = wuby_ocr_overlay.match_ocr_events_with_subtitles(
                    wuby_events, segments=segments, srt_path=srt_path,
                    movie_title=raw_movie_title, vid_h=probe_h, vid_w=probe_w
                )
            else:
                wuby_events = wuby_ocr_overlay.scan_video_text_events(str(in_vid), sample_fps=ocr_fps)
                wuby_events = wuby_ocr_overlay.filter_semantic_ocr_events(wuby_events)
                wuby_events = wuby_ocr_overlay.match_ocr_events_with_subtitles(
                    wuby_events, segments=segments, srt_path=srt_path,
                    movie_title=raw_movie_title, vid_h=probe_h, vid_w=probe_w
                )

            cleaned_temp = wuby_ocr_overlay.clean_video_ocr_backgrounds(str(in_vid), str(output_video), wuby_events)
            if cleaned_temp and os.path.exists(cleaned_temp):
                in_vid = Path(cleaned_temp)
        except Exception as ocr_err:
            print(f"[VideoMerger] [WubyOCR] Cảnh báo lỗi OCR overlay: {ocr_err}")
            frame_cfg = (channel_cfg.get("wuby_studio") or {}).get("hybrid_frame") or {}
            if channel_cfg.get("workflow") == "wuby" and frame_cfg.get("enabled", False):
                raise RuntimeError(f"WUBY_OCR_FAILED: {ocr_err}") from ocr_err

    trim_sec = _to_float(channel_cfg.get("trim_start_sec"), 0.0)
    intro_act = str(channel_cfg.get("intro_action") or "").lower()
    if intro_act == "trim" and trim_sec <= 0.0:
        trim_sec = 0.15

    if trim_sec > 0.001:
        inputs = ["-ss", f"{trim_sec:.3f}", "-i", str(in_vid)]
        print(f"[VideoMerger] Tự động cắt bỏ {trim_sec:.3f}s đầu video để loại bỏ ảnh bìa/chữ rác!")
    else:
        inputs = ["-i", str(in_vid)]

    next_input_index = 1
    has_voice = voice_audio and os.path.exists(voice_audio) and os.path.getsize(voice_audio) > 0
    strict_dialogue = channel_cfg.get("dialogue_replace") or {}
    if strict_dialogue.get("enabled") and strict_dialogue.get("required") and not has_voice:
        raise RuntimeError("DUBBED_AUDIO_REQUIRED: missing dubbed voice; refusing original-audio output")
    if has_voice and (channel_cfg.get('voice_accuracy') or {}).get('enabled'):
        try:
            from .dub_accuracy import verify_or_repair
        except ImportError:
            from dub_accuracy import verify_or_repair
        voice_audio = verify_or_repair(voice_audio, srt_path, channel_cfg,
                                      get_video_duration(str(in_vid)))
        if (channel_cfg.get('_voice_profile') or {}).get('playback_speed'):
            try:
                from .dub_accuracy import aligned_srt_for_voice
                from .sub_processor import parse_srt_to_segments
            except ImportError:
                from dub_accuracy import aligned_srt_for_voice
                from sub_processor import parse_srt_to_segments
            srt_path = aligned_srt_for_voice(voice_audio, srt_path)
            segments = parse_srt_to_segments(srt_path)
    voice_index = None
    if has_voice:
        inputs += ["-i", str(voice_audio)]
        voice_index = next_input_index
        next_input_index += 1

    banner_index = None
    intro_banner_png = channel_cfg.get("intro_banner_png")
    if intro_act == "banner" and intro_banner_png and os.path.exists(intro_banner_png):
        inputs += ["-i", str(intro_banner_png)]
        banner_index = next_input_index
        next_input_index += 1
        print(f"[VideoMerger] Đã thêm Banner Title Card vào input [{banner_index}]: {intro_banner_png}")

    # Optional dialogue replacement mode:
    # - TTS silent  -> original audio full
    # - TTS talking -> separated instrumental/background + Vietnamese TTS
    # The switch follows the actual generated TTS waveform, not subtitle timestamps.
    dialogue_cfg = channel_cfg.get("dialogue_replace") if isinstance(channel_cfg.get("dialogue_replace"), dict) else {}
    dialogue_assets = None
    instrumental_index = speech_instrumental_index = voice_mask_index = original_mask_index = None
    if has_voice and keep_bg_audio and dialogue_cfg.get("enabled", False):
        try:
            try:
                from .dialogue_replace import prepare_dialogue_replacement as prep_diag
            except ImportError:
                from dialogue_replace import prepare_dialogue_replacement as prep_diag

            stems = prep_diag(
                video_path=str(in_vid),
                cache_root=dialogue_cfg.get("cache_dir", r"cache\audio_stems"),
                worker_script=dialogue_cfg.get("worker_script"),
                model_filename=dialogue_cfg.get("model_filename", "UVR-MDX-NET-Inst_HQ_3.onnx"),
                model_dir=dialogue_cfg.get("model_file_dir", r"D:/0.1_FACE_BOOK/Lay video tiktok/MODELS/audio_separator"),
                audio_sep_python=dialogue_cfg.get("separator_python", r"D:/0.1_FACE_BOOK/Lay video tiktok/MOI_TRUONG/audio_sep_env\Scripts\python.exe"),
                require_cuda=bool(dialogue_cfg.get("require_cuda", True)),
            )
            dialogue_assets = {
                "instrumental": stems["instrumental"],
                "vocals": stems.get("vocals"),
                "separator": f"audio_sep_worker:{dialogue_cfg.get('model_filename', 'UVR-MDX-NET-Inst_HQ_3.onnx')}",
            }
            inputs += ["-i", str(dialogue_assets["instrumental"])]
            instrumental_index = next_input_index
            next_input_index += 1
            print(f"[VideoMerger] Dialogue replace assets ready: {dialogue_assets.get('instrumental')}")
        except Exception as dialogue_err:
            if dialogue_cfg.get("hard_replace", True) or dialogue_cfg.get("required", False):
                # LUẬT BẮT BUỘC: KHÔNG ĐƯỢC FALLBACK VỀ AUDIO GỐC KHI HARD_REPLACE = TRUE!
                raise RuntimeError(
                    f"[VideoMerger FATAL] Separator thất bại (hard_replace=True). "
                    f"Dừng render ngay lập tức để không lọt tiếng thoại gốc: {dialogue_err}"
                ) from dialogue_err
            print(f"[VideoMerger] Dialogue replace fallback to legacy mix: {dialogue_err}")
            dialogue_assets = None

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
    probe_fps = float(cap_probe.get(cv2.CAP_PROP_FPS) or 24.0)
    probe_frames = int(cap_probe.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    total_duration = probe_frames / probe_fps if probe_fps > 0 else 0.0
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

    # Xóa sạch chữ Trung dọc bên trái (chỉ áp dụng cho phim/review có watermark dọc, không áp dụng cho video câu cá/đời sống tự nhiên)
    skip_vert = channel_cfg.get("workflow") in ["gaidep_cauca", "chidep_cauca"] or mask_mode == "blur_sub_black"
    left_vert_boxes = [] if skip_vert else detect_vertical_left_watermark(str(in_vid), top_offset=cover_top_h if has_top_cover else 0)
    for v_idx, v_box in enumerate(left_vert_boxes or []):
        vx, vy, vw, vh = v_box['x'], v_box['y'], v_box['w'], v_box['h']
        filters.append(f"{current_label}split[v_base_l{v_idx}][v_lsub{v_idx}]")
        filters.append(f"[v_lsub{v_idx}]crop={vw}:{vh}:{vx}:{vy},gblur=sigma=12[v_lblur{v_idx}]")
        filters.append(f"[v_base_l{v_idx}][v_lblur{v_idx}]overlay={vx}:{vy}[v_lcleaned{v_idx}]")
        current_label = f"[v_lcleaned{v_idx}]"
        print(f"[VideoMerger] Làm mờ chữ Trung dọc bên trái: x={vx}, y={vy}, w={vw}, h={vh}")

    # Only opted-in profiles clean right-edge text; restrict blur to detected boxes.
    right_vert_boxes = (
        detect_vertical_right_watermark(str(in_vid), top_offset=cover_top_h if has_top_cover else 0)
        if not skip_vert and _to_bool(render_cfg.get("vertical_right_watermark"), False)
        else []
    )
    for v_idx, v_box in enumerate(right_vert_boxes):
        vx, vy, vw, vh = (v_box[k] for k in ('x', 'y', 'w', 'h'))
        filters.append(f"{current_label}split[v_base_r{v_idx}][v_rsub{v_idx}]")
        filters.append(f"[v_rsub{v_idx}]crop={vw}:{vh}:{vx}:{vy},gblur=sigma=18[v_rblur{v_idx}]")
        filters.append(f"[v_base_r{v_idx}][v_rblur{v_idx}]overlay={vx}:{vy}[v_rcleaned{v_idx}]")
        current_label = f"[v_rcleaned{v_idx}]"
        print(f"[VideoMerger] Làm mờ chữ dọc cạnh phải: x={vx}, y={vy}, w={vw}, h={vh}")

    # Review-film behavior requested by the user: wipe the full top strip to black,
    # then draw the Vietnamese title on top via ASS. (Never apply to wuby mode!)
    if not is_wuby_mode and has_top_cover and top_cover_enabled and str(top_cover_cfg.get("mode") or "black").lower() == "black":
        filters.append(f"{current_label}drawbox=x=0:y=0:w=iw:h={cover_top_h}:color=black@1:t=fill[vtopblack]")
        current_label = "[vtopblack]"
        title_fs = _to_int(title_cfg.get("font_size"), max(32, int(round(cover_top_h * _to_float(title_cfg.get("font_ratio_on_bar"), 0.44)))))
        title_mv = _to_int(title_cfg.get("margin_v"), max(8, int(round((cover_top_h - title_fs) / 2))))
        title_persistent = _to_bool(title_cfg.get("persistent_on_top_bar"), False)
        print(f"[VideoMerger] Đè đen toàn bộ vùng chữ/viền trên: {cover_top_h}px (persistent={title_persistent})")
    else:
        title_fs = _to_int(title_cfg.get("font_size"), max(44, int(round(vid_w * _to_float(title_cfg.get("font_ratio"), 0.068)))))
        title_mv = _to_int(title_cfg.get("margin_v"), max(35, int(round(vid_h * 0.10))))
        title_persistent = _to_bool(title_cfg.get("persistent"), False)

    detected_sub_box = None
    caption_regions = None
    film_sub_center = None
    tracked_modes = {"black_bar", "sub_black_bar", "sub_box", "black_box"}
    use_bottom_caption_bar = (
        mask_mode == "blur_sub_black"
        and _to_bool(render_cfg.get("prefer_existing_bottom_bar"), False)
        and bot_bar >= max(48, int(vid_h * .06))
    )
    if use_bottom_caption_bar:
        # Source captions already occupy the black letterbox. Clear it completely
        # instead of treating dialogue as a watermark and blurring scene signage.
        import json
        caption_regions = [dict(
            start=0.0, end=total_duration,
            box=dict(x=0, y=vid_h-bot_bar, w=vid_w, h=bot_bar),
            status="existing_bottom_bar",
        )]
        filters.append(f"{current_label}drawbox=x=0:y={vid_h-bot_bar}:w=iw:h={bot_bar}:color=black@1:t=fill[vbottomcaption]")
        current_label = "[vbottomcaption]"
        dialogue_fs = min(_to_int(subtitle_cfg.get("font_size"), min(46, max(28, int(vid_h*.035)))), max(20, int(bot_bar*.32)))
        dialogue_mv = max(8, (bot_bar-dialogue_fs)//2)
        out_vid.with_suffix('.subtitle_regions.json').write_text(
            json.dumps(caption_regions, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"[VideoMerger] Sub Việt trong dải đen gốc: y={vid_h-bot_bar}, h={bot_bar}; che kín chữ gốc, không blur cảnh.")
    elif mask_mode in tracked_modes and not is_wuby_mode:
        from subtitle_regions import scan_caption_regions, region_filters
        import json
        caption_regions = scan_caption_regions(in_vid, sample_fps=_to_float(render_cfg.get("subtitle_scan_fps"), 2.0))
        out_vid.with_suffix(".subtitle_regions.json").write_text(json.dumps(caption_regions, ensure_ascii=False, indent=2), encoding="utf-8")
        dialogue_fs = _to_int(subtitle_cfg.get("font_size"), max(24, int(vid_h*.035)))
        dialogue_mv = _to_int(subtitle_cfg.get("margin_v"), max(16, int(vid_h*.065)))
        if is_film_mode:
            bars = compute_film_black_bars(vid_w, vid_h, top_ratio=_to_float(bars_cfg.get("top_ratio"), .10), bottom_ratio=_to_float(bars_cfg.get("bottom_ratio"), .22))
            filters.append(f"{current_label}drawbox=x=0:y=0:w=iw:h={bars['top_h']}:color=black:t=fill,drawbox=x=0:y={vid_h-bars['bottom_h']}:w=iw:h={bars['bottom_h']}:color=black:t=fill[caption_bars]")
            current_label = '[caption_bars]'
            # Không set film_sub_center khi đã có caption_regions từ scan_caption_regions.
            # Để caption_regions điều khiển vị trí sub Việt bám theo chữ gốc thực tế.
            # film_sub_center chỉ dùng khi không có caption_regions (branch elif is_film_mode bên dưới).
        extra, current_label = region_filters(caption_regions, mask_mode, vid_w, vid_h, current_label)
        filters.extend(extra)
    elif precise_blur:
        from precise_subtitle_detection import scan_precise_caption_regions, timed_blur_filters, ensure_blur_coverage
        import json
        raw_events = []
        if segments:
            for seg in segments:
                get = seg.get if isinstance(seg, dict) else lambda k, d=None: getattr(seg, k, d)
                raw_events.append((float(get('start', 0)), float(get('end', 0)), get('text', '') or ''))
        elif srt_path and os.path.exists(srt_path):
            raw_events = parse_srt_file_to_events(srt_path)
        cached_regions = channel_cfg.get('_caption_regions_cache')
        if cached_regions is not None:
            from render_review_policy import bound_caption_regions
            caption_regions = bound_caption_regions(cached_regions,in_vid,detection_cfg,vid_w,vid_h,total_duration)
        else:
            caption_regions = scan_precise_caption_regions(
                str(in_vid), raw_events,
                ocr_backend=detection_cfg.get('ocr_backend', 'easyocr'),
                min_center_ratio=_to_float(detection_cfg.get('min_center_ratio'), 2/3))
        source_srt = Path(srt_path).with_suffix('.orig.srt') if srt_path else None
        if source_srt and source_srt.is_file():
            from precise_subtitle_detection import recover_source_caption_regions
            caption_regions = recover_source_caption_regions(
                str(in_vid),caption_regions,parse_srt_file_to_events(str(source_srt)),
                _to_float(detection_cfg.get('min_center_ratio'),2/3))
        dialogue_fs = _to_int(subtitle_cfg.get('font_size'), min(46, max(36, int(round(vid_h*.042)))))
        missing_blur = any(not r.get('box') and any(s < r['end'] and e > r['start'] for s, e, _ in raw_events)
                           for r in caption_regions) or (bool(raw_events) and not caption_regions)
        fallback_box = None
        allow_fallback = _to_bool(detection_cfg.get('allow_estimated_mask'), True)
        if missing_blur and allow_fallback:
            fallback_box = detect_subtitle_box_20_frames(str(in_vid), segments=[
                dict(start=s, end=e, text=t) for s, e, t in raw_events])
        if allow_fallback:
            caption_regions = ensure_blur_coverage(
                caption_regions, raw_events, vid_w, vid_h, fallback_box, dialogue_fs)
        if any(r.get('status') == 'fallback_estimated' for r in caption_regions):
            print('[VideoMerger] OCR/OpenCV chưa xác định được chữ gốc ở một số đoạn: dùng nền blur theo sub Việt, vị trí chữ gốc chưa được xác minh.')
        out_vid.with_suffix('.subtitle_regions.json').write_text(
            json.dumps(caption_regions, ensure_ascii=False, indent=2), encoding='utf-8')
        extra, current_label = timed_blur_filters(
            caption_regions, vid_w, vid_h, current_label,
            out_vid.with_suffix('.subtitle_mask.ass'),
            alpha=_to_float(render_cfg.get('blur_bg_alpha'), .35),
            sigma=_to_float(render_cfg.get('blur_strength'),16))
        filters.extend(extra)
        dialogue_fs = _to_int(subtitle_cfg.get('font_size'), min(46, max(36, int(round(vid_h*.042)))))
        dialogue_mv = _to_int(subtitle_cfg.get('margin_v'), max(16, int(round(vid_h*.055))))
    elif mask_mode == "blur_sub_black":
        detected_sub_box = None
        detected_blur_boxes = []
        try:
            from subtitle_regions import scan_multi_blur_boxes, scan_fixed_blur_box
            probe_ts = []
            raw_events = []
            if segments:
                for seg in segments:
                    get = seg.get if isinstance(seg, dict) else lambda k, d=None: getattr(seg, k, d)
                    raw_events.append((float(get('start', 0)), float(get('end', 0)), get('text', '') or ''))
            elif srt_path and os.path.exists(srt_path):
                raw_events = parse_srt_file_to_events(srt_path)

            if raw_events:
                sorted_by_len = sorted(raw_events, key=lambda e: len(e[2]), reverse=True)
                probe_ts = [(e[0] + e[1]) / 2.0 for e in sorted_by_len[:25]]
            else:
                total_dur = get_video_duration(str(in_vid))
                if total_dur > 1.0:
                    import numpy as np
                    early = list(range(1, min(int(total_dur), 120), 4))
                    later = list(np.linspace(min(120, total_dur * 0.4), max(10, total_dur - 3), 15))
                    probe_ts = sorted(list(set(early + [int(x) for x in later])))

            detected_blur_boxes = scan_multi_blur_boxes(str(in_vid), probe_ts, max_samples=35)
            if detected_blur_boxes:
                detected_sub_box = next((b for b in detected_blur_boxes if b.get('zone') == 'subtitle'), detected_blur_boxes[0])
        except Exception as ocr_err:
            print(f"[VideoMerger] scan_multi_blur_boxes bỏ qua ({ocr_err}), dùng OpenCV chuẩn xác...")
            detected_sub_box = None
            detected_blur_boxes = []

        if not detected_sub_box and not detected_blur_boxes:
            print("[VideoMerger] Quét toạ độ phụ đề chính xác bằng OpenCV (detect_subtitle_box_20_frames)...")
            detected_sub_box = detect_subtitle_box_20_frames(str(in_vid), segments=segments)
            if detected_sub_box:
                detected_blur_boxes = [detected_sub_box]
    elif blur_sub:
        detected_sub_box = detect_subtitle_box_20_frames(str(in_vid), segments=segments)

    if caption_regions is not None:
        pass  # Timed OCR masks and matching ASS positions have already been prepared.
    elif is_film_mode:
        bars_info = compute_film_black_bars(
            vid_w,
            vid_h,
            detected_sub_box,
            top_ratio=_to_float(bars_cfg.get("top_ratio"), 0.10),
            bottom_ratio=_to_float(bars_cfg.get("bottom_ratio"), 0.22),
            bottom_max_ratio=_to_float(bars_cfg.get("bottom_max_ratio"), 0.42),
        )
        top_h = bars_info["top_h"]
        bot_h = bars_info["bottom_h"]
        dialogue_fs = _to_int(subtitle_cfg.get("font_size"), bars_info["dialogue_fs"])
        dialogue_mv = _to_int(subtitle_cfg.get("margin_v"), bars_info["dialogue_mv"])

        bot_y = vid_h - bot_h
        filters.append(f"{current_label}drawbox=x=0:y=0:w=iw:h={top_h}:color=black@1:t=fill[vtopblack]")
        filters.append(f"[vtopblack]drawbox=x=0:y={bot_y}:w=iw:h={bot_h}:color=black@1:t=fill[vblackbars]")
        current_label = "[vblackbars]"
        
        # Đảm bảo dải đen đáy bám trọn chữ Trung gốc, triệt tiêu hoàn toàn 2 lớp subtitle
        if detected_sub_box:
            by = detected_sub_box.get("y", 0)
            bh = detected_sub_box.get("h", 0)
            if by > 0 and by < bot_y:
                filters.append(f"{current_label}drawbox=x=0:y={by}:w=iw:h={bot_y - by + 4}:color=black@1:t=fill[vextrablack]")
                current_label = "[vextrablack]"
                bot_y = by
                bot_h = vid_h - by
            sub_cy = detected_sub_box.get("center_y", bot_y + (vid_h - bot_y) // 2)
            dialogue_mv = max(12, int(round(vid_h - sub_cy - (dialogue_fs / 2))))
            # Có detected_sub_box: dialogue_mv đã bám đúng chữ gốc; KHÔNG set film_sub_center
            # để sub Việt đặt theo MarginV tính từ tọa độ chữ Trung, không cố định giữa dải đen.
            print(f"[VideoMerger] Sub Việt bám chữ gốc tại sub_cy={sub_cy:.0f}px, MarginV={dialogue_mv}px")
        else:
            # Không scan được chữ gốc: fallback đặt sub ở giữa dải đen như cũ.
            film_sub_center = (vid_w / 2.0, vid_h - bot_h / 2.0)
            print(f"[VideoMerger] Sub Việt fallback giữa dải đen: y={(vid_h - bot_h / 2.0):.0f}px")
        print(f"[VideoMerger] Film profile -> dải đen trên={top_h}px, dưới={bot_h}px (MarginV={dialogue_mv}px)")
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
        filters.append(f"[vsubarea]crop={bw}:{bh}:{bx}:{by},boxblur={blur_radius}:2[vblurredsub]")
        filters.append(f"[vmain][vblurredsub]overlay={bx}:{by}[vblurred]")
        current_label = "[vblurred]"
        dialogue_fs = _to_int(subtitle_cfg.get("font_size"), max(28, int(round(vid_h * 0.056))))
        dialogue_mv = _to_int(subtitle_cfg.get("margin_v"), max(16, int(round(vid_h * 0.065))))
    elif mask_mode in ["blur_sub_black", "sub_black_bar", "sub_box", "black_box"]:
        # BẮT ĐÚNG HÌNH CHỮ NHẬT TẠI VỊ TRÍ PHỤ ĐỀ (X, Y, W, H) - KHÔNG CHE HẾT BỀ NGANG
        is_landscape = (vid_w >= vid_h)
        # Giới hạn chặt: portrait tối đa 78%, landscape tối đa 82%
        max_box_w = min(int(vid_w * 0.82), 1400) if is_landscape else min(int(vid_w * 0.78), 840)
        min_box_w = 320 if is_landscape else 240

        # Ước lượng chiều rộng cần thiết từ độ dài text sub dịch (tiếng Việt)
        # ~1 ký tự Việt ≈ font_size * 0.55px trên màn hình, 1 dòng tối đa 35 ký tự
        _est_fs = min(46, max(36, int(round(vid_h * 0.042))))
        _all_texts = []
        if segments:
            for _seg in segments:
                _get = _seg.get if isinstance(_seg, dict) else lambda k, d=None: getattr(_seg, k, d)
                _txt = _get("text", "") or ""
                if _txt.strip():
                    _all_texts.append(_txt.strip())
        elif srt_path and os.path.exists(srt_path):
            _srt_evts = parse_srt_file_to_events(srt_path)
            _all_texts = [e[2] for e in _srt_evts if e[2].strip()]
        if _all_texts:
            _longest = max(_all_texts, key=len)
            # Chia thành 2 dòng nếu > 30 ký tự, lấy dòng dài nhất để tính width
            _words = _longest.split()
            if len(_longest) > 30 and len(_words) > 1:
                _mid = min(range(1, len(_words)), key=lambda i: abs(len(' '.join(_words[:i])) - len(' '.join(_words[i:]))))
                _line1 = ' '.join(_words[:_mid])
                _line2 = ' '.join(_words[_mid:])
                _ref_line = max(_line1, _line2, key=len)
            else:
                _ref_line = _longest
            # Ước lượng pixel width: mỗi ký tự ~0.58 * font_size (Latin/Việt)
            _text_w_est = int(len(_ref_line) * _est_fs * 0.58)
            # Padding +4% mỗi bên
            _pad_x_text = max(20, int(round(vid_w * 0.04)))
            _text_based_w = _text_w_est + 2 * _pad_x_text
        else:
            _text_based_w = 0

        if detected_sub_box:
            by = detected_sub_box.get("y")
            bh = detected_sub_box.get("h")
            det_x = detected_sub_box.get("x", 0)
            det_w = detected_sub_box.get("w", 0)

            # Chọn chiều rộng nhỏ hơn trong: OCR box và text-based estimate
            # → tránh OCR detect toàn bề ngang do chữ gốc trải dài
            pad_x = max(20, int(round(vid_w * 0.02)))
            ocr_based_w = det_w + 2 * pad_x
            if _text_based_w > min_box_w:
                # Dùng max của 2 ước lượng nhưng cap bởi max_box_w
                candidate_w = max(ocr_based_w, _text_based_w)
            else:
                candidate_w = ocr_based_w
            bw = min(max_box_w, max(min_box_w, candidate_w))

            sub_cx = det_x + det_w / 2.0
            if abs(sub_cx - vid_w / 2.0) <= (vid_w * 0.15):
                bx = (vid_w - bw) // 2
            else:
                bx = int(round(sub_cx - bw / 2.0))
                bx = max(10, min(vid_w - bw - 10, bx))
            sub_cy = detected_sub_box.get("center_y", by + bh // 2)
        else:
            # Fallback: dùng text-based estimate hoặc 60% width
            _fb_w = _text_based_w if _text_based_w > min_box_w else int(vid_w * 0.60)
            _font_h = _est_fs
            bh = int(_font_h * 2.6)   # 2 dòng + padding
            by = vid_h - bh - max(8, int(round(vid_h * 0.015)))
            bw = min(max_box_w, max(min_box_w, _fb_w))
            bx = (vid_w - bw) // 2
            sub_cy = by + bh // 2

        # Giới hạn chiều cao: tối đa 2 dòng sub + 4% padding (khoảng 13% chiều cao video)
        max_box_h = int(round(vid_h * 0.15))
        if bh > max_box_h:
            # Phụ đề bám đáy màn hình, luôn neo theo đáy (bottom) để không bị hở mép dưới chữ
            bottom_edge = by + bh
            bh = max_box_h
            by = max(0, bottom_edge - bh)
            sub_cy = by + bh // 2


        bx = (bx // 2) * 2
        by = (by // 2) * 2
        bw = (bw // 2) * 2
        bh = (bh // 2) * 2

        if mask_mode == "blur_sub_black":
            # Làm mờ Gaussian Blur tự nhiên, mềm mịn, không dùng hộp đen đè lên
            blur_alpha = _to_float(render_cfg.get("blur_bg_alpha"), 0.0)
            blur_strength = _to_int(render_cfg.get("blur_strength"), 20)
            boxes_to_blur = detected_blur_boxes if ('detected_blur_boxes' in locals() and detected_blur_boxes) else [dict(x=bx, y=by, w=bw, h=bh, center_y=sub_cy)]

            # Tính thời điểm bắt đầu có tiếng thoại đầu tiên để không làm mờ oan vào con cá/cảnh đầu khi chưa nói
            first_sub_t = 0.0
            if segments:
                first_sub_t = min((float(s.get('start', 0) if isinstance(s, dict) else s.start) for s in segments if (s.get('text', '') if isinstance(s, dict) else s.text).strip()), default=0.0)
            elif srt_path and os.path.exists(srt_path):
                _evts = parse_srt_file_to_events(srt_path)
                if _evts:
                    first_sub_t = min((float(e[0]) for e in _evts if str(e[2]).strip()), default=0.0)

            for b_idx, box in enumerate(boxes_to_blur):
                _bx = (int(box['x']) // 2) * 2
                _by = (int(box['y']) // 2) * 2
                _bw = (int(box['w']) // 2) * 2
                _bh = (int(box['h']) // 2) * 2
                is_sub_zone = box.get('zone') == 'subtitle'
                enable_expr = f":enable='gte(t,{max(0.0, first_sub_t - 0.2):.2f})'" if (is_sub_zone and first_sub_t > 0.6) else ""

                filters.append(f"{current_label}split[vm_{b_idx}][vs_{b_idx}]")
                filters.append(f"[vs_{b_idx}]crop={_bw}:{_bh}:{_bx}:{_by},gblur=sigma={blur_strength}:steps=2[vb_{b_idx}]")
                filters.append(f"[vm_{b_idx}][vb_{b_idx}]overlay={_bx}:{_by}{enable_expr}[vo_{b_idx}]")
                if blur_alpha > 0.01:
                    filters.append(f"[vo_{b_idx}]drawbox=x={_bx}:y={_by}:w={_bw}:h={_bh}:color=black@{blur_alpha:.2f}:t=fill{enable_expr}[vt_{b_idx}]")
                    current_label = f"[vt_{b_idx}]"
                else:
                    current_label = f"[vo_{b_idx}]"
                print(f"[VideoMerger] Vùng Gaussian Blur [{box.get('zone', b_idx)}]: x={_bx}px, y={_by}px, rộng={_bw}px, cao={_bh}px (Sigma={blur_strength}, Alpha={blur_alpha}{', Hẹn giờ thoại ' + enable_expr if enable_expr else ''})")

            # Nếu có Banner Title Card, overlay lên trong 2.5s đầu rồi mờ dần biến mất (Fade out)
            if banner_index is not None:
                info_banner = channel_cfg.get("intro_banner_box") or {}
                bbx = info_banner.get("x", (vid_w - 960) // 2)
                bby = info_banner.get("y", int(vid_h * 0.35))
                duration_banner = _to_float(channel_cfg.get("intro_banner_duration"), 2.5)
                fade_start = max(0.5, duration_banner - 0.4)
                filters.append(f"[{banner_index}:v]format=rgba,fade=t=out:st={fade_start:.2f}:d=0.4:alpha=1[vfaded_banner]")
                filters.append(f"{current_label}[vfaded_banner]overlay={bbx}:{bby}:enable='lte(t,{duration_banner:.2f})'[vwithbanner]")
                current_label = "[vwithbanner]"
                print(f"[VideoMerger] Đã thêm Banner Title Card: x={bbx}, y={bby}, hiển thị {duration_banner}s (fade out từ {fade_start:.2f}s)")
            else:
                # Nếu không dùng Banner (Phương án B) và có sticker tiếng Trung ở đoạn đầu, áp dụng Gaussian Blur che sạch
                intro_sticker_box = channel_cfg.get("intro_sticker_box")
                if intro_sticker_box and isinstance(intro_sticker_box, dict) and intro_sticker_box.get("w", 0) > 0:
                    sbx = max(0, intro_sticker_box.get("x", 0) - 35)
                    sby = max(0, intro_sticker_box.get("y", 0) - 25)
                    sbw = min(vid_w - sbx, intro_sticker_box.get("w", 100) + 70)
                    sbh = min(vid_h - sby, intro_sticker_box.get("h", 100) + 50)
                    filters.append(
                        f"{current_label}split[v_stk_main][v_stk_crop];"
                        f"[v_stk_crop]crop={sbw}:{sbh}:{sbx}:{sby},gblur=sigma=30[v_stk_blurred];"
                        f"[v_stk_main][v_stk_blurred]overlay={sbx}:{sby}:enable='lte(t,2.0)'[vwithstkblur]"
                    )
                    current_label = "[vwithstkblur]"
                    print(f"[VideoMerger] Đã áp dụng làm mờ cụm chữ Trung Quốc (Phương án B): x={sbx}, y={sby}, w={sbw}, h={sbh} (2.0s đầu)")

            # Cỡ chữ phụ đề chuẩn đẹp, thanh thoát (~4.2% chiều cao video, khoảng 44-46px trên 1080p, không bị quá to)
            dialogue_fs = _to_int(subtitle_cfg.get("font_size"), min(46, max(36, int(round(vid_h * 0.042)))))
            # Căn giữa tâm dải blur cho khối chữ (1-2 dòng)
            calculated_mv = int(round(vid_h - sub_cy - (dialogue_fs * 1.05)))
            dialogue_mv = _to_int(subtitle_cfg.get("margin_v"), max(8, calculated_mv))
        else:
            # Legacy mask modes (sub_black_bar / sub_box / black_box):
            # Hình chữ nhật ĐEN TUYỀN đè đúng vị trí chữ cũ, KHÔNG che hết bề ngang
            filters.append(f"{current_label}drawbox=x={bx}:y={by}:w={bw}:h={bh}:color=black@1:t=fill[vsubblack]")
            current_label = "[vsubblack]"
            dialogue_fs = _to_int(subtitle_cfg.get("font_size"), min(46, max(36, int(round(vid_h * 0.042)))))
            calculated_mv = int(round(vid_h - sub_cy - (dialogue_fs * 1.05)))
            dialogue_mv = _to_int(subtitle_cfg.get("margin_v"), max(8, calculated_mv))
            print(f"[VideoMerger] Hình chữ nhật đen đè sub: x={bx}px, y={by}px, rộng={bw}px, cao={bh}px (CenterY={sub_cy:.1f}px, MarginV={dialogue_mv}px, FontSize={dialogue_fs}px)")
    else:
        dialogue_fs = _to_int(subtitle_cfg.get("font_size"), min(46, max(36, int(round(vid_h * 0.042)))))
        dialogue_mv = _to_int(subtitle_cfg.get("margin_v"), max(16, int(round(vid_h * 0.055))))

    burn_sub_enabled = _to_bool(channel_cfg.get("burn_sub"), True) and _to_bool(subtitle_cfg.get("enabled"), True)
    has_sub = burn_sub_enabled and ((srt_path and os.path.exists(srt_path) and os.path.getsize(srt_path) > 0) or bool(segments))
    if movie_title or has_sub or (is_wuby_mode and wuby_events):
        ass_path = out_vid.parent / f"{out_vid.stem}_styled.ass"
        if is_wuby_mode and wuby_events:
            try:
                import wuby_ocr_overlay
                preflight = channel_cfg.get("_wuby_preflight") if isinstance(channel_cfg.get("_wuby_preflight"), dict) else {}
                scenes = list(preflight.get("scene_ranges") or [])
                if not scenes:
                    for ev in wuby_events:
                        if "scene_start" in ev and "scene_end" in ev:
                            s_item = {"scene_id": ev.get("scene_id", 0), "start": float(ev["scene_start"]), "end": float(ev["scene_end"])}
                            if s_item not in scenes:
                                scenes.append(s_item)
                    scenes.sort(key=lambda s: s["start"])

                # When the source already has a top banner, its OCR replacement is the
                # title. Do not add a second generated title card on top of it.
                wuby_has_banner = any(
                    ev.get("is_banner") and (ev.get("vi_text") or "").strip()
                    for ev in wuby_events
                )
                wuby_movie_title = None if wuby_has_banner else movie_title

                wuby_ocr_overlay.build_wuby_ass_subtitles(
                    out_ass_path=ass_path,
                    vid_w=vid_w,
                    vid_h=vid_h,
                    ocr_events=wuby_events,
                    movie_title=wuby_movie_title,
                    title_config={
                        "enabled": bool(wuby_movie_title),
                        "mode": "full_video" if title_persistent else title_cfg.get("mode", "intro_scene"),
                        "duration_sec": _to_float(title_cfg.get("duration"), 3.0),
                        "font_size": title_fs,
                        "margin_v": title_mv,
                    },
                    scene_ranges=scenes or None,
                    video_duration=total_duration,
                    follow_motion=_to_bool(subtitle_cfg.get("follow_motion"), True),
                    min_font_size=_to_int(subtitle_cfg.get("min_font_size"), 34),
                    max_font_size=_to_int(subtitle_cfg.get("max_font_size"), 56),
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
                    # Ưu tiên caption_regions (vị trí chữ gốc thực tế) trước film_sub_center.
                    # film_sub_center chỉ được dùng khi không có caption_regions (không nhận diện được chữ gốc).
                    caption_regions=caption_regions if caption_regions is not None else None,
                    sub_pos_center=(None if caption_regions is not None else
                                    film_sub_center or
                                    ((bx + bw / 2.0, sub_cy) if (mask_mode in ("blur_sub_black", "sub_black_bar") and caption_regions is None) else None)),
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
                # Ưu tiên caption_regions (vị trí chữ gốc thực tế) trước film_sub_center.
                # film_sub_center chỉ được dùng khi không có caption_regions (không nhận diện được chữ gốc).
                caption_regions=caption_regions if caption_regions is not None else None,
                sub_pos_center=(None if caption_regions is not None else
                                film_sub_center or
                                ((bx + bw / 2.0, sub_cy) if (mask_mode in ("blur_sub_black", "sub_black_bar") and caption_regions is None) else None)),
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

    _logo_type = channel_cfg.get("_logo_type") or (channel_cfg.get("logo", {}).get("type") if isinstance(channel_cfg.get("logo"), dict) and channel_cfg.get("logo", {}).get("enabled", True) else None)
    if _logo_type:
        font_path = "C\\:/Windows/Fonts/arialbd.ttf"
        corner_text, drift_text = resolve_logo_text(_logo_type, channel_cfg.get("logo"))

        # Add corner logo (top right corner to not overlap with Wuby character overlay on left)
        filters.append(f"{current_label}drawtext=fontfile='{font_path}':text='{corner_text}':fontcolor=white:fontsize=36:x=w-tw-40:y=40:alpha=0.6[vtext1]")
        # Add drifting logo (floating across bottom like a bubble)
        drift_x = r"mod(t*60\,w)"
        drift_y = r"h-150+sin(t*1.5)*50+cos(t*0.8)*20"
        filters.append(f"[vtext1]drawtext=fontfile='{font_path}':text='{drift_text}':fontcolor=white:fontsize=28:x={drift_x}:y={drift_y}:alpha=0.5[vtext2]")
        current_label = "[vtext2]"
        print(f"[VideoMerger] Đã thêm Logo FFMPEG Drawtext: {corner_text} và {drift_text} (Alpha: 0.5, Floating)")

    audio_label = None
    if has_voice and voice_index is not None:
        tts_volume = _to_float(dialogue_cfg.get("tts_volume"), 1.0) if dialogue_cfg else 1.0
        filters.append(f"[{voice_index}:a]volume={tts_volume:.4f}[avoice]")
        if keep_bg_audio and dialogue_assets and instrumental_index is not None:
            inst_volume = _to_float(dialogue_cfg.get("instrumental_volume"), bg_volume if bg_volume > 0.01 else 0.8)
            mute_original_speech = _to_bool(dialogue_cfg.get("mute_original_speech", dialogue_cfg.get("hard_replace", True)), True)
            filters.append(f"[{instrumental_index}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={inst_volume:.4f}[ainst]")

            if not mute_original_speech and voice_mask_index is not None and original_mask_index is not None:
                filters.append("[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[aorig]")
                filters.append(f"[{voice_mask_index}:a]aresample=48000,pan=stereo|c0=c0|c1=c0[vmask]")
                filters.append(f"[{original_mask_index}:a]aresample=48000,pan=stereo|c0=c0|c1=c0[omask]")
                filters.append("[aorig][omask]amultiply[aorigpass]")
                filters.append("[ainst][vmask]amultiply[ainstpass]")
                filters.append("[aorigpass][ainstpass][avoice]amix=inputs=3:duration=first:dropout_transition=0:normalize=0[aout]")
                audio_label = "[aout]"
            else:
                # Hard dialogue replacement: chỉ mix [ainst] (nhạc nền) + [avoice] (voice mới)
                # Tuyệt đối KHÔNG có [0:a] trong output
                separator_method = str((dialogue_assets or {}).get("separator") or "audio_sep_worker")
                filters.append("[ainst][avoice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
                audio_label = "[aout]"
                print(f"[VideoMerger] Hard replace thoại gốc THÀNH CÔNG: [ainst] (vol={inst_volume:.2f}) + [avoice] qua amix/alimiter ({separator_method})")
        elif keep_bg_audio and bg_volume > 0.001:
            mute_speech = _to_bool(
                dialogue_cfg.get("mute_original_speech") if (dialogue_cfg and "mute_original_speech" in dialogue_cfg)
                else channel_cfg.get("mute_original_speech"),
                False if channel_cfg.get("workflow") == "gaidep_cauca" else True
            )
            if mute_speech:
                # Tránh lọt tiếng Trung/ngoại ngữ gốc khi không có bóc tách vocal sạch
                print("[VideoMerger] Triệt tiêu hoàn toàn giọng nói gốc để tránh lọt tiếng Trung, chỉ dùng giọng thuyết minh/clone chuẩn [avoice]")
                audio_label = "[avoice]"
            else:
                # Fallback né âm tự động: triệt tiêu giọng người nói ở giữa (vocal cut), chỉ giữ nhạc nền
                vocal_cut_val = vocal_cut or _to_bool(channel_cfg.get("vocal_cut"), False)
                eff_bg_vol = min(bg_volume, 0.50)
                if vocal_cut_val:
                    filters.append(f"[0:a]stereotools=mlev={mlev}:slev={eff_bg_vol:.2f}[abg_raw]")
                else:
                    filters.append(f"[0:a]volume={eff_bg_vol:.2f}[abg_raw]")
                filters.append("[abg_raw][avoice]sidechaincompress=threshold=0.015:ratio=20:attack=15:release=250[abg]")
                filters.append("[abg][avoice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
                audio_label = "[aout]"
                print(f"[VideoMerger] Mix âm thanh nền dã ngoại ({eff_bg_vol:.2f}) + Giọng đọc AI qua sidechain ducking & alimiter")
        else:
            audio_label = "[avoice]"

    if audio_label:
        # Bộ lọc EBU R128 True Peak limiter: triệt tiêu hoàn toàn hiện tượng méo tiếng / clipping / âm quá nóng
        filters.append(f"{audio_label}alimiter=limit=0.92:attack=5:release=50:asc=1[alimited]")
        audio_label = "[alimited]"

    ffmpeg_bin = _ffmpeg_executable()

    def run_cmd(encoder: str, extra_args: list[str]):
        cmd = [ffmpeg_bin, "-y", "-loglevel", "error", *inputs]
        script_file = None
        if filters:
            filter_str = ";".join(filters)
            if len(filter_str) > 4000:
                script_file = out_vid.parent / f"filter_{out_vid.stem}.txt"
                script_file.write_text(filter_str, encoding="utf-8")
                cmd += ["-filter_complex_script", str(script_file), "-map", current_label]
            else:
                cmd += ["-filter_complex", filter_str, "-map", current_label]
        else:
            cmd += ["-map", "0:v:0"]

        if audio_label:
            cmd += ["-map", audio_label, "-c:a", "aac", "-b:a", str(encoder_cfg.get("audio_bitrate", "96k")), "-ar", "44100"]
        else:
            cmd += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", str(encoder_cfg.get("audio_bitrate", "96k")), "-ar", "44100"]

        out_fps = _to_int(encoder_cfg.get("fps"), 0)
        fps_args = ["-r", str(out_fps), "-fps_mode", "cfr"] if out_fps > 0 else []
        cmd += ["-c:v", encoder, *extra_args, *fps_args, "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", str(tmp_out)]
        try:
            subprocess.run(cmd, check=True)
        finally:
            if script_file and script_file.exists():
                try:
                    script_file.unlink()
                except Exception:
                    pass
        if not tmp_out.is_file() or tmp_out.stat().st_size == 0:
            raise RuntimeError(f"FFmpeg did not create a nonempty render: {tmp_out}")
        if tmp_out.exists():
            if out_vid.exists():
                try:
                    out_vid.unlink()
                except Exception:
                    pass
            for _attempt in range(5):
                try:
                    tmp_out.rename(out_vid)
                    break
                except (PermissionError, OSError):
                    time.sleep(0.5)
            else:
                shutil.move(str(tmp_out), str(out_vid))

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
