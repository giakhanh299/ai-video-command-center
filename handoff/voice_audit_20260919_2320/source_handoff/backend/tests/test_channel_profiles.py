import json
import sys
import unittest
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import channel_manager


class TestChannelProfiles(unittest.TestCase):
    def test_config_is_v2(self):
        cfg = channel_manager.load_channels_config(force_reload=True)
        self.assertEqual(cfg.get("schema_version"), 2)
        self.assertIn("channels", cfg)
        self.assertIn("render_profiles", cfg)
        self.assertIn("voice_profiles", cfg)
        self.assertIn("workflows", cfg)

    def test_deep_merge_keeps_siblings(self):
        base = {"render": {"title": {"font": "Arial", "color": "white"}}}
        override = {"render": {"title": {"color": "yellow"}}}
        out = channel_manager.deep_merge(base, override)
        self.assertEqual(out["render"]["title"]["font"], "Arial")
        self.assertEqual(out["render"]["title"]["color"], "yellow")

    def test_preset_does_not_rename_chat_channel(self):
        _, cfg = channel_manager.get_channel_config("-5579042871", text="https://x #blur")
        self.assertEqual(cfg.get("name"), "Kênh Review Nam")
        self.assertEqual(cfg.get("workflow"), "film_review_blur")
        self.assertEqual(cfg.get("mask_mode"), "blur")

    def test_omnivoice_profile_resolves_sample(self):
        _, cfg = channel_manager.get_channel_config("default", text="https://x #vutruphim")
        vp = cfg.get("_voice_profile", {})
        self.assertEqual(vp.get("engine"), "omnivoice")
        self.assertTrue(Path(vp.get("ref_audio", "")).is_file())


if __name__ == "__main__":
    unittest.main()
