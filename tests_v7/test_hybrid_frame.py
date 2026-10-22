import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from wuby_studio.hybrid import frame_finished_wuby, hybrid_config, render_hybrid, reviewed_crop


class HybridFrameTests(unittest.TestCase):
    def test_processed_video_uses_only_visual_frame(self):
        cfg = hybrid_config()
        self.assertEqual(cfg['audio']['mode'], 'preserve')
        self.assertEqual(cfg['cleanup']['mode'], 'none')
        self.assertTrue(cfg['cleanup']['input_already_rendered'])
        self.assertFalse(cfg['subtitle']['enabled'])
        self.assertAlmostEqual(cfg['layout']['video'][3], 0.80)

    def test_missing_processed_video_is_rejected_before_renderer(self):
        with self.assertRaises(FileNotFoundError):
            render_hybrid('not_a_real_video.mp4', 'preview.mp4', 'Sample title')

    def test_hybrid_config_does_not_touch_channel_presets(self):
        first = hybrid_config('mint')
        second = hybrid_config('peach')
        self.assertEqual(first['theme'], 'mint')
        self.assertEqual(second['theme'], 'peach')
        self.assertNotIn('presets', first)

    def test_crop_must_be_explicit_and_within_source(self):
        self.assertIsNone(reviewed_crop(None))
        self.assertEqual(hybrid_config(crop='0,0.22,1,0.56')['cleanup']['crop'],
                         [0.0, 0.22, 1.0, 0.56])
        for invalid in ('0,0,1,2', '-0.1,0,1,1', '0,0,0,1', 'nan,0,1,1', '0,0,1'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                reviewed_crop(invalid)

    def test_square_source_gets_square_card_without_letterbox(self):
        cfg = hybrid_config(source_aspect=1.0)
        rect = cfg['layout']['video']
        self.assertAlmostEqual((rect[2] * 1080) / (rect[3] * 1920), 1.0)
        self.assertLess(rect[3], 0.55)
        with self.assertRaises(ValueError):
            hybrid_config(source_aspect=16 / 9)

    def test_only_enabled_wuby_enters_second_visual_pass(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / 'finished.mp4'
            source.write_bytes(b'finished')
            config = {'workflow': 'wuby', 'wuby_studio': {
                'hybrid_frame': {'enabled': True, 'theme': 'mint'}}}
            with patch('wuby_studio.hybrid.render_hybrid') as render:
                output = frame_finished_wuby(source, 'Vietnamese title', config)
            self.assertEqual(output, source.with_name('finished_hybrid.mp4'))
            render.assert_called_once_with(source, output, 'Vietnamese title',
                                           'mint', None, write_review_artifacts=False)
            with patch('wuby_studio.hybrid.render_hybrid') as render:
                self.assertEqual(frame_finished_wuby(source, 'Title',
                    {'workflow': 'cauhinh4', 'wuby_studio': config['wuby_studio']}), source)
                self.assertEqual(frame_finished_wuby(source, 'Title',
                    {'workflow': 'wuby', 'wuby_studio': {'hybrid_frame': {'enabled': False}}}), source)
                render.assert_not_called()

    def test_enabled_hybrid_fails_if_first_pass_missing(self):
        with self.assertRaises(FileNotFoundError):
            frame_finished_wuby('no-first-pass.mp4', 'Title',
                                {'workflow': 'wuby', 'wuby_studio': {'hybrid_frame': {'enabled': True}}})


if __name__ == '__main__':
    unittest.main()
