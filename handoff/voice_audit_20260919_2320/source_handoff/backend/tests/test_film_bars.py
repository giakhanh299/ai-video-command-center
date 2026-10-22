import unittest
import os
import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from film_bars import compute_film_black_bars, escape_subtitle_path_windows

class TestFilmBars(unittest.TestCase):
    def setUp(self):
        # Clean environment before each test
        for k in ["FILM_TOP_BAR_RATIO", "FILM_BOTTOM_BAR_RATIO", "WHISPER_MODEL"]:
            if k in os.environ:
                del os.environ[k]

    def test_default_ratios(self):
        """Test default ratios: 10% top and 22% bottom for 1080x1920 video."""
        res = compute_film_black_bars(1080, 1920, detected_box=None)
        self.assertEqual(res["top_h"], 192, "Top bar must be 192px (10% of 1920)")
        self.assertEqual(res["bottom_h"], 422, "Bottom bar must be 422px (22% of 1920)")
        self.assertTrue(res["dialogue_fs"] >= 28, "Dialogue font size must be >= 28")
        self.assertTrue(res["dialogue_mv"] >= 12, "Dialogue margin V must be >= 12")

    def test_env_override(self):
        """Test env override for FILM_TOP_BAR_RATIO and FILM_BOTTOM_BAR_RATIO."""
        os.environ["FILM_TOP_BAR_RATIO"] = "0.15"
        os.environ["FILM_BOTTOM_BAR_RATIO"] = "0.20"
        res = compute_film_black_bars(1080, 1920, detected_box=None)
        self.assertEqual(res["top_h"], 288, "Top bar must be 288px (15% of 1920)")
        self.assertEqual(res["bottom_h"], 384, "Bottom bar must be 384px (20% of 1920)")

    def test_invalid_ratios_fail_closed(self):
        """Test invalid ratio raises ValueError with INVALID_FILM_RATIO."""
        # Top < 0.05
        os.environ["FILM_TOP_BAR_RATIO"] = "0.03"
        with self.assertRaises(ValueError) as ctx:
            compute_film_black_bars(1080, 1920)
        self.assertIn("INVALID_FILM_RATIO", str(ctx.exception))

        # Bottom > 0.35
        os.environ["FILM_TOP_BAR_RATIO"] = "0.10"
        os.environ["FILM_BOTTOM_BAR_RATIO"] = "0.38"
        with self.assertRaises(ValueError) as ctx:
            compute_film_black_bars(1080, 1920)
        self.assertIn("INVALID_FILM_RATIO", str(ctx.exception))

        # Total > 0.50
        os.environ["FILM_TOP_BAR_RATIO"] = "0.30"
        os.environ["FILM_BOTTOM_BAR_RATIO"] = "0.25"
        with self.assertRaises(ValueError) as ctx:
            compute_film_black_bars(1080, 1920)
        self.assertIn("INVALID_FILM_RATIO", str(ctx.exception))

    def test_detector_box_expansion_and_cap(self):
        """Test detector box expands bottom bar up to maximum 35% cap."""
        # Old sub box at y=1400, h=80 -> needed_bot_h = 1920 - 1400 + 4 = 524px (> 422 default)
        box = {"x": 200, "y": 1400, "w": 680, "h": 80}
        res = compute_film_black_bars(1080, 1920, detected_box=box)
        self.assertEqual(res["bottom_h"], 524, "Bottom bar must expand to 524px to cover old sub")

        # Old sub box at y=1000 -> needed 924px, capped at 35% of 1920 = 672px
        high_box = {"x": 200, "y": 1000, "w": 680, "h": 80}
        res_high = compute_film_black_bars(1080, 1920, detected_box=high_box)
        self.assertEqual(res_high["bottom_h"], 672, "Bottom bar must cap at 35% (672px)")

    def test_windows_unicode_path_escaping(self):
        """Test Windows path and Unicode escaping for FFmpeg filter graph."""
        raw_path = "C:\\Users\\USER\\My Video\\phụ_đề'test.ass"
        escaped = escape_subtitle_path_windows(raw_path)
        self.assertEqual(escaped, "C\\:/Users/USER/My Video/phụ_đề\\'test.ass")
        self.assertNotIn("\\\\", escaped)

    def test_filter_order_and_sub_style_in_source(self):
        """Verify filter graph order: drawbox top -> drawbox bottom -> subtitles and ASS 2-line style."""
        merger_file = backend_dir / "video_merger.py"
        self.assertTrue(merger_file.exists(), "video_merger.py must exist")
        content = merger_file.read_text(encoding="utf-8")

        # 1. Filter graph order
        top_idx = content.find("drawbox=x=0:y=0:w=iw:h={top_h}")
        bot_idx = content.find("drawbox=x=0:y={bot_y}:w=iw:h={bot_h}")
        sub_idx = content.find("filters.append(f\"{current_label}subtitles='{clean_ass}'[vsubout]\")")

        self.assertTrue(top_idx > 0, "Top drawbox must be present")
        self.assertTrue(bot_idx > top_idx, "Bottom drawbox must follow top drawbox")
        self.assertTrue(sub_idx > bot_idx, "Subtitles filter must follow bottom drawbox")

        # 2. Subtitle style: white font (&H00FFFFFF), black outline, max 2 lines
        self.assertIn("&H00FFFFFF", content, "Dialogue style must have white font")
        self.assertIn("WrapStyle: 0", content, "WrapStyle must be standard wrap (max 2 lines)")


    def test_mode_guard(self):
        """Verify is_film_mode guard exists in process_video_sub_and_mute signature."""
        merger_file = backend_dir / "video_merger.py"
        content = merger_file.read_text(encoding="utf-8")
        self.assertIn("is_film_mode: bool = True", content, "process_video_sub_and_mute must have is_film_mode guard")
        self.assertIn("if is_film_mode:", content, "Drawbox bars must be guarded by is_film_mode check")

    def test_whisper_cache_and_env_override(self):
        """Verify get_transcriber reuses cached instance and respects env override without reloading per chunk."""
        sub_file = backend_dir / "sub_processor.py"
        content = sub_file.read_text(encoding="utf-8")
        self.assertIn("global _cached_transcriber", content, "Transcriber must be cached globally")
        self.assertIn('DEFAULT_WHISPER_MODEL = os.getenv("WHISPER_MODEL", "large-v3")', content)
        self.assertIn("WHISPER_MODEL_LOAD_FAILED", content, "Must fail closed with WHISPER_MODEL_LOAD_FAILED")

if __name__ == "__main__":
    unittest.main()
