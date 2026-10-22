import pytest
from pathlib import Path
from backend.sub_processor import is_whisper_hallucination, SubtitleSegment
from backend.wuby_ocr_overlay import build_wuby_ass_subtitles, match_ocr_events_with_subtitles

def test_whisper_hallucination_detection():
    # Music & non-speech tags
    assert is_whisper_hallucination("[Music]") is True
    assert is_whisper_hallucination("(music)") is True
    assert is_whisper_hallucination("（音乐）") is True
    assert is_whisper_hallucination("【音乐】") is True
    assert is_whisper_hallucination("Nhạc") is True
    assert is_whisper_hallucination("(Nhạc)") is True
    assert is_whisper_hallucination("tiếng nhạc") is True

    # Boilerplate across languages
    assert is_whisper_hallucination("Thanks for watching!") is True
    assert is_whisper_hallucination("Thank you for watching") is True
    assert is_whisper_hallucination("Please subscribe to my channel") is True
    assert is_whisper_hallucination("Subtitles by fignyafsyakaya") is True
    assert is_whisper_hallucination("자막은 설정에서 선택하실 수 있습니다.") is True
    assert is_whisper_hallucination("Jangan lupa SUBSCRIBE, LIKE, KOMEN dan SHARE...") is True
    assert is_whisper_hallucination("明镜需要您的支持 欢迎收看订阅明镜") is True
    assert is_whisper_hallucination("欢迎收看") is True
    assert is_whisper_hallucination("Woo! Woo! Woo! Woo!") is True

    # Genuine speech must NOT be treated as hallucination
    assert is_whisper_hallucination("Hôm nay trời rất đẹp", duration=2.0, lang_prob=0.95) is False
    assert is_whisper_hallucination("Bởi vì tôi là con gái", duration=2.5, lang_prob=0.98) is False
    assert is_whisper_hallucination("你不理你的人看你", duration=2.0, lang_prob=0.92) is False

def test_ass_motion_tracking_consolidated(tmp_path):
    out_ass = tmp_path / "test_motion.ass"
    # Create an event moving across 24 keyframes over 1 second
    kfs = [
        {"time": i / 24.0, "box": [100 + i * 5, 200 + i * 5, 120, 60], "bg_bgr": [255, 255, 255]}
        for i in range(24)
    ]
    ev = {
        "start": 0.0,
        "end": 1.0,
        "box": [100, 200, 120, 60],
        "bg_bgr": [255, 255, 255],
        "vi_text": "Chữ di chuyển",
        "motion_type": "MOVE",
        "keyframes": kfs
    }
    build_wuby_ass_subtitles(
        out_ass,
        vid_w=1080,
        vid_h=1920,
        ocr_events=[ev],
        movie_title="TEST TITLE",
        title_config={"enabled": True, "mode": "intro_scene", "duration_sec": 3.0}
    )
    content = out_ass.read_text(encoding="utf-8")
    dialogues = [line for line in content.splitlines() if line.startswith("Dialogue:")]
    # Dialogue 1 is TitleCard, Dialogue 2 is the consolidated moving subtitle (must NOT be 24 fragmented lines!)
    assert len(dialogues) == 2
    assert r"\move(" in dialogues[1]

def test_no_duplicate_banner_when_global_title_active(tmp_path):
    out_ass = tmp_path / "test_banner.ass"
    banner_ev = {
        "start": 0.0,
        "end": 4.0,
        "box": [100, 100, 400, 80],
        "is_banner": True,
        "vi_text": "BẠN THÂN NÓI GIỎI",
    }
    build_wuby_ass_subtitles(
        out_ass,
        vid_w=1080,
        vid_h=1920,
        ocr_events=[banner_ev],
        movie_title="BẠN THÂN NÓI GIỎI",
        title_config={"enabled": True, "mode": "intro_scene"}
    )
    content = out_ass.read_text(encoding="utf-8")
    dialogues = [line for line in content.splitlines() if line.startswith("Dialogue:")]
    # Only 1 TitleCard line (Dialogue 1) should be present, not duplicated by Dialogue 2
    title_dialogues = [d for d in dialogues if "TitleCard" in d]
    assert len(title_dialogues) == 1

def test_whisper_repetition_loop_pruning():
    from backend.sub_processor import prune_intersegment_repetition_loops
    # Simulate the 7x "Tôi là" loop from video 7682609577711422726
    looping_segs = [
        SubtitleSegment(float(i), float(i + 1), "Tôi là")
        for i in range(7)
    ]
    cleaned = prune_intersegment_repetition_loops(looping_segs)
    assert len(cleaned) == 0  # Loop completely discarded

    # Legitimate alternating or non-looping segments are preserved
    legit_segs = [
        SubtitleSegment(0.0, 1.5, "Xin chào bạn"),
        SubtitleSegment(1.6, 3.0, "Tôi là Minh"),
        SubtitleSegment(3.1, 4.5, "Rất vui được gặp bạn")
    ]
    cleaned_legit = prune_intersegment_repetition_loops(legit_segs)
    assert len(cleaned_legit) == 3

def test_hallucination_expanded_boilerplate():
    assert is_whisper_hallucination("Cảm ơn bạn rất nhiều vì đã tham gia cùng chúng tôi.") is True
    assert is_whisper_hallucination("Tình nguyện viên phụ đề Lý Tông Thịnh") is True
    assert is_whisper_hallucination("Đó là bởi vì bởi vì", duration=9.91) is True
    assert is_whisper_hallucination("Hẹn gặp lại các bạn ở video sau") is True

def test_overlay_banner_and_dialogue_consolidation(tmp_path):
    out_ass = tmp_path / "test_consolidation.ass"
    # 4 fragmented banner tracks as in 7686743717423762688
    ocr_events = [
        {"start": 0.00, "end": 6.12, "is_banner": True, "vi_text": "BẠN THÂN NÓI GIỎI\\NTÔI CHỈ VIỆC GẬT ĐẦU", "box": [100, 100, 500, 80]},
        {"start": 0.21, "end": 3.21, "is_banner": True, "vi_text": "BẠN THÂN NÓI GIỎI TÔI CHỈ VIỆC GẬT ĐẦU", "box": [100, 100, 500, 80]},
        {"start": 1.54, "end": 4.71, "is_banner": True, "vi_text": "BẠN THÂN NÓI GIỎI TÔI CHỈ VIỆC GẬT ĐẦU", "box": [100, 100, 500, 80]},
        {"start": 2.63, "end": 6.12, "is_banner": True, "vi_text": "BẠN THÂN NÓI GIỎI TÔI CHỈ VIỆC GẬT ĐẦU", "box": [100, 100, 500, 80]},
        # A hallucinated music tag on screen
        {"start": 0.00, "end": 2.12, "is_banner": False, "vi_text": "Nhạc", "box": [200, 300, 100, 50]},
        # 3 connecting dialogue tracks as in 7675252187865419060
        {"start": 0.59, "end": 0.79, "is_banner": False, "vi_text": "Ồ, là gà-cừu-bò", "box": [99, 459, 120, 50]},
        {"start": 0.75, "end": 2.79, "is_banner": False, "vi_text": "Ồ, là gà-cừu-bò", "box": [123, 457, 120, 50]},
        {"start": 1.25, "end": 1.79, "is_banner": False, "vi_text": "Ồ, là gà-cừu-bò", "box": [214, 457, 120, 50]},
    ]
    build_wuby_ass_subtitles(
        out_ass,
        vid_w=1080,
        vid_h=1920,
        ocr_events=ocr_events,
        movie_title="",  # No global title, so banner must be generated from OCR
        title_config=None
    )
    content = out_ass.read_text(encoding="utf-8")
    dialogues = [line for line in content.splitlines() if line.startswith("Dialogue:")]
    
    # 1. TitleCard: The 4 banner fragments must consolidate into EXACTLY 1 TitleCard line
    title_dialogues = [d for d in dialogues if "TitleCard" in d]
    assert len(title_dialogues) == 1
    assert "0:00:00.00,0:00:06.12" in title_dialogues[0]

    # 2. Hallucination "Nhạc" must NOT be present
    assert not any("Nhạc" in d for d in dialogues)

    # 3. Dialogue "Ồ, là gà-cừu-bò": The 3 fragments must consolidate into EXACTLY 1 dialogue line spanning 0.59 to 2.79
    speech_dialogues = [d for d in dialogues if "Ồ, là gà-cừu-bò" in d]
    assert len(speech_dialogues) == 1
    assert "0:00:00.59,0:00:02.79" in speech_dialogues[0]

def test_no_infinite_95959_title_duration(tmp_path):
    from backend.video_merger import create_master_subtitles_ass
    out_ass = tmp_path / "test_persistent.ass"
    segs = [
        SubtitleSegment(0.0, 3.0, "Câu thứ nhất"),
        SubtitleSegment(3.5, 7.2, "Câu thứ hai")
    ]
    create_master_subtitles_ass(
        out_ass_path=out_ass,
        vid_w=1080,
        vid_h=1920,
        dialogue_font_size=40,
        dialogue_margin_v=120,
        segments=segs,
        movie_title="TIÊU ĐỀ BỀN VỮNG",
        title_persistent=True
    )
    content = out_ass.read_text(encoding="utf-8")
    assert "9:59:59" not in content
    # Must be clamped to the end of segments (7.2s -> 0:00:07.20)
    assert "0:00:07.20" in content

def test_cauhinh2_default_and_channel_specific_speed():
    import json
    cfg_path = Path("backend/channels_config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["presets"]["cauhinh2"]["speed"] == 1.3
    assert data["channels"]["-5579042871"]["speed"] == 1.7

def test_split_long_segments():
    from backend.sub_processor import split_long_segments
    # Long sentence (15 words, 68 chars)
    long_seg = SubtitleSegment(0.0, 3.6, "Một chiếc xe tải nhỏ lùi vào bên cạnh ngân hàng để chuẩn bị hành động")
    short_seg = SubtitleSegment(4.0, 5.5, "Xin chào các bạn")
    
    result = split_long_segments([long_seg, short_seg], max_words=12, max_chars=44)
    # Long segment must be split into 2 natural chunks
    assert len(result) == 3
    assert result[0].start == 0.0
    assert result[0].end == result[1].start
    assert result[1].end == 3.6
    assert len(result[0].text.split()) <= 12
    assert len(result[1].text.split()) <= 12
    # Short segment remains unchanged
    assert result[2].text == "Xin chào các bạn"
    assert result[2].start == 4.0
    assert result[2].end == 5.5

def test_format_balanced_sub_text():
    from backend.video_merger import format_balanced_sub_text
    # Line over 34 chars
    long_line = "Một chiếc xe tải nhỏ lùi vào bên cạnh ngân hàng"
    balanced = format_balanced_sub_text(long_line, max_chars=34)
    assert r"\N" in balanced
    parts = balanced.split(r"\N")
    assert len(parts) == 2
    assert all(len(p) <= 34 for p in parts)
    
    # Short line remains single line
    short_line = "Xin chào các bạn"
    assert format_balanced_sub_text(short_line, max_chars=34) == "Xin chào các bạn"


