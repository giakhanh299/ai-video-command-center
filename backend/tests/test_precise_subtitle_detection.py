"""Regression checks for missing blur; no source videos or OCR models are used."""
import sys
import unittest
import tempfile
import subprocess
import shutil
from unittest.mock import patch
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from precise_subtitle_detection import ensure_blur_coverage, timed_blur_filters, consensus_box, lower_third_lines, similar_text, recover_source_caption_regions
from video_merger import create_master_subtitles_ass

class PreciseSubtitleTests(unittest.TestCase):
    def test_recover_missing_source_caption_requires_two_matching_real_frames(self):
        class Capture:
            def get(self, prop): return {3:1920,4:1080,5:25}.get(prop,0)
            def set(self, *_): return True
            def read(self): return True, np.zeros((1080,1920,3),np.uint8)
            def release(self): pass
        class Engine:
            def __init__(self): self.calls=0
            def __call__(self, _):
                self.calls+=1
                return ([([[500,200],[1400,200],[1400,280],[500,280]],
                          '退赛只因身体原因',.99)],None)
        engine=Engine()
        missing=[dict(start=55.875,end=56.25,box=None,status='empty')]
        source=[(55.875,56.25,'退赛只因身体原因')]
        with patch('precise_subtitle_detection.cv2.VideoCapture',return_value=Capture()), \
             patch('rapid_ocr_service.get_rapid_ocr',return_value=engine):
            result=recover_source_caption_regions('fake.mp4',missing,source,.75)
        self.assertEqual(engine.calls,2)
        covered=next(r for r in result if r['start']<=56.0<r['end'])
        self.assertEqual(covered['status'],'verified')
        self.assertEqual(covered['verification_method'],'SOURCE_TRANSCRIPT_TWO_FRAME_OCR')
        self.assertIsNotNone(covered['box'])
        self.assertGreater(covered['box']['y'],850)

    def test_recover_missing_source_caption_rejects_unrelated_ocr(self):
        class Capture:
            def get(self, prop): return {3:1920,4:1080,5:25}.get(prop,0)
            def set(self, *_): return True
            def read(self): return True, np.zeros((1080,1920,3),np.uint8)
            def release(self): pass
        engine=lambda _:([([[500,200],[1400,200],[1400,280],[500,280]],
                            '完全不同的文字',.99)],None)
        missing=[dict(start=55.875,end=56.25,box=None,status='empty')]
        with patch('precise_subtitle_detection.cv2.VideoCapture',return_value=Capture()), \
             patch('rapid_ocr_service.get_rapid_ocr',return_value=engine):
            result=recover_source_caption_regions('fake.mp4',missing,
                                                   [(55.875,56.25,'退赛只因身体原因')],.75)
        covered=next(r for r in result if r['start']<=56.0<r['end'])
        self.assertIsNone(covered['box'])
        self.assertEqual(covered['status'],'empty')

    def test_large_burned_landscape_caption_is_not_discarded_as_banner(self):
        # Actual K5 source OCR: 91px glyph height in a 1080px frame.
        hit=([[468,198],[1450,200],[1449,291],[468,288]],'一条快老死的狗也当个宝',.99)
        lines=lower_third_lines([hit],1920,1080,692)
        self.assertEqual(len(lines),1)
        self.assertGreater(lines[0]['y'],880)
    def test_all_empty_report_gets_blur_only_during_dialogue(self):
        result=ensure_blur_coverage([dict(start=0,end=10,box=None,status='empty')],[(1,3,'Một câu'),(5,7,'Câu khác')],1920,1080)
        self.assertEqual([(r['start'],r['end']) for r in result if r['box']],[(1,3),(5,7)])
        self.assertTrue(all(r['status']=='fallback_estimated' for r in result if r['box']))
        self.assertTrue(all(r['box']['w']<1920 and r['box']['h']<173 for r in result if r['box']))

    def test_detected_fallback_and_verified_box_are_preserved(self):
        verified=dict(x=200,y=800,w=300,h=40)
        fallback=dict(x=100,y=900,w=500,h=50)
        regions=[dict(start=0,end=1,box=verified,status='verified'),dict(start=1,end=2,box=None,status='uncertain')]
        result=ensure_blur_coverage(regions,[(0,2,'Một câu')],1080,1920,fallback)
        self.assertEqual(result[0]['box'],verified)
        self.assertEqual(result[1]['box'],fallback)
        self.assertEqual(result[1]['status'],'fallback_detected')

    def test_empty_list_or_unavailable_ocr_still_gets_backdrop(self):
        for regions in ([],[dict(start=0,end=2,box=None,status='ocr_unavailable')]):
            result=ensure_blur_coverage(regions,[(0,2,'Lời thoại')],720,1280)
            self.assertTrue(result[0]['box'])

    def test_no_dialogue_no_guessed_mask(self):
        result=ensure_blur_coverage([dict(start=0,end=2,box=None,status='empty')],[],720,1280)
        self.assertFalse(any(r['box'] for r in result))

    def test_subtitle_uses_same_center_as_fallback(self):
        regions=ensure_blur_coverage([],[(0,2,'Một câu')],720,1280)
        b=regions[0]['box']
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'sub.ass'
            create_master_subtitles_ass(path,720,1280,45,50,segments=[dict(start=0,end=2,text='Một câu')],caption_regions=regions)
            self.assertIn(f"\\pos({b['x']+b['w']/2:.1f},{b['y']+b['h']/2:.1f})",path.read_text(encoding='utf-8'))

    def test_one_wide_outlier_does_not_expand_consensus(self):
        obs=[]
        for i in range(7):
            x,w=(10,700) if i==6 else (210,300)
            points=[[x,240],[x+w,240],[x+w,264],[x,264]]
            obs.append((i,lower_third_lines([(points,'字幕',.9)],720,1200,800)))
        self.assertLess(consensus_box(obs,720,1200)['w'],330)

    def test_minor_ocr_spelling_change_is_not_new_text(self):
        self.assertTrue(similar_text('channel','channel1'))

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg unavailable')
    def test_ffmpeg_mask_has_correct_position_opacity_and_time(self):
        with tempfile.TemporaryDirectory() as d:
            filters,label=timed_blur_filters([dict(start=0,end=.5,box=dict(x=80,y=100,w=100,h=40))],320,180,'[0:v]',Path(d)/'mask.ass')
            p=subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=white:s=320x180:r=10:d=1','-filter_complex',';'.join(filters),'-map',label,'-pix_fmt','rgb24','-f','rawvideo','-'],capture_output=True,timeout=30)
            self.assertEqual(p.returncode,0,p.stderr.decode(errors='replace'))
            frames=np.frombuffer(p.stdout,np.uint8).reshape(-1,180,320,3)
            self.assertEqual(len(frames),10)
            self.assertTrue(100<int(frames[1,115,110,0])<230)
            self.assertGreater(int(frames[1,30,30,0]),245)
            self.assertGreater(int(frames[8,115,110,0]),245)
            ys,xs=np.where(frames[1,:,:,0]<230)
            self.assertEqual((int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())),(80,100,179,139))

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg unavailable')
    def test_opaque_mask_contains_no_source_pixels(self):
        with tempfile.TemporaryDirectory() as d:
            filters,label=timed_blur_filters(
                [dict(start=0,end=.5,box=dict(x=80,y=100,w=100,h=40))],
                320,180,'[0:v]',Path(d)/'mask.ass',alpha=1.0)
            self.assertTrue(any('drawbox=' in f and 'black@1' in f for f in filters))
            self.assertFalse(any('alphamerge' in f for f in filters))
            p=subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
                              'color=white:s=320x180:r=10:d=1','-filter_complex',';'.join(filters),
                              '-map',label,'-pix_fmt','rgb24','-f','rawvideo','-'],
                             capture_output=True,timeout=30)
            self.assertEqual(p.returncode,0,p.stderr.decode(errors='replace'))
            frames=np.frombuffer(p.stdout,np.uint8).reshape(-1,180,320,3)
            # Limited-range YUV black decodes near RGB 16-18 in this FFmpeg path.
            self.assertLess(int(frames[1,115,110,0]),25)
            self.assertGreater(int(frames[1,30,30,0]),245)
            self.assertGreater(int(frames[8,115,110,0]),245)

if __name__=='__main__': unittest.main()
