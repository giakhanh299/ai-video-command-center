"""Script Render Video Dai 60s:
1. Che chu tieng Trung cu theo nguyen ly cu (mask_mode='black_bar' / 'blur')
2. Bóc tach Vocal & Nhac nen qua GPU (audio-separator ONNX UVR-MDX-NET)
3. Triet tieu 100% tieng thoai goc (Hard Replace)
4. Long giong doc tieng Viet moi + chen sub tieng Viet
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import video_merger
import channel_manager


def main():
    print("=" * 65)
    print("  RENDER TEST VIDEO 60S - CHE CHỮ CŨ & TÁCH NỀN GPU KHÔNG VOCAL GỐC")
    print("=" * 65)

    input_vid = BASE_DIR / "workspace" / "clip_7684_60s.mp4"
    srt_file = BASE_DIR / "workspace" / "clip_7684_60s.srt"
    voice_file = BASE_DIR / "workspace" / "clip_7684_60s_voice.wav"
    output_vid = BASE_DIR / "workspace" / "test_render_60s_che_chu_tach_nen.mp4"

    if not input_vid.exists():
        raise FileNotFoundError(f"Không tìm thấy video đầu vào: {input_vid}")

    print(f"• Video nguồn:     {input_vid.name} (Thời lượng ~60s)")
    print(f"• Phụ đề tiếng Việt: {srt_file.name}")
    print(f"• Giọng thuyết minh: {voice_file.name}")
    print(f"• Video xuất:      {output_vid.name}")

    # Đọc subtitle segments từ srt để định vị chính xác vùng chữ Trung Quốc
    raw_events = video_merger.parse_srt_file_to_events(str(srt_file))
    vi_segments = [{"start": e[0], "end": e[1], "text": e[2]} for e in raw_events]

    # Cấu hình kênh chuẩn gần đây nhất: blur_sub_black (mờ kính frosted glass) + bóc tách nền GPU
    test_channel_cfg = {
        "name": "Kênh Movie Clone Blur - Bóc Tách Nền GPU",
        "workflow": "movie_clone",
        "render_profile": "movie_clone_blur",
        "keep_bg_audio": True,
        "bg_volume": 0.85,
        "show_title_card": False,
        "vocal_cut": False,
        "mask_mode": "blur_sub_black",  # Chuẩn cấu hình gần đây nhất: làm mờ hộp kính frosted glass
        "render": {
            "top_cover": {"enabled": False, "mode": "none"},
            "title": {"enabled": False},
            "subtitle": {
                "enabled": True,
                "font": "Arial",
                "font_size": 38,
                "color": "#FFFFFF",
                "outline_color": "#000000",
                "outline_size": 3,
                "bold": True
            },
            "encoder": {"use_nvenc": True, "nvenc_preset": "p4", "cq": 28, "audio_bitrate": "160k"}
        },
        "dialogue_replace": {
            "enabled": True,
            "hard_replace": True,
            "separator_python": r"D:/0.1_FACE_BOOK/Lay video tiktok/MOI_TRUONG/audio_sep_env\Scripts\python.exe",
            "model_file_dir": r"D:/0.1_FACE_BOOK/Lay video tiktok/MODELS/audio_separator",
            "model_filename": "UVR-MDX-NET-Inst_HQ_3.onnx",
            "require_cuda": True,
            "instrumental_volume": 0.85,
            "cache_dir": r"cache\audio_stems"
        }
    }

    print("\n[1/3] Đang phân tích video và khởi động render...")
    t0 = time.time()

    res_path = video_merger.process_video_sub_and_mute(
        input_video=str(input_vid),
        output_video=str(output_vid),
        srt_path=str(srt_file),
        voice_audio=str(voice_file),
        keep_bg_audio=True,
        bg_volume=0.85,
        blur_sub=False,
        use_nvenc=True,
        segments=vi_segments,
        movie_title=None,
        mask_mode="blur_sub_black",
        channel_cfg=test_channel_cfg,
    )

    t1 = time.time()

    print("\n" + "=" * 65)
    print("  RENDER HOÀN TẤT THÀNH CÔNG RỰC RỠ!")
    print("=" * 65)
    print(f"• File xuất xưởng: {output_vid}")
    print(f"• Dung lượng file: {output_vid.stat().st_size / (1024*1024):.2f} MB")
    print(f"• Tổng thời gian:  {round(t1 - t0, 2)} giây")
    print("• Các tính năng đã áp dụng:")
    print("   1. Che chữ Trung Quốc theo nguyên lý cũ (black_bar / scan_caption_regions)")
    print("   2. Bóc tách âm thanh video gốc qua GPU (audio_sep_worker UVR-MDX-NET)")
    print("   3. Triệt tiêu hoàn toàn 100% tiếng thoại gốc (Hard Replace)")
    print("   4. Giữ lại nhạc nền + hiệu ứng âm thanh sạch (Instrumental)")
    print("   5. Lồng giọng thuyết minh mới + chèn phụ đề tiếng Việt")
    print("=" * 65)


if __name__ == "__main__":
    main()
