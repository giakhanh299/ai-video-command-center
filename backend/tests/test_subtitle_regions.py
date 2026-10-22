import sys
from pathlib import Path
import tempfile
import unittest
import numpy as np
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from subtitle_regions import caption_box, positioned_parts, region_filters, stabilize_regions, read_caption_detections
from video_merger import create_master_subtitles_ass


def hit(x,y,w,h,text='中文字幕',confidence=.9):
    return ([[x,y],[x+w,y],[x+w,y+h],[x,y+h]],text,confidence)


class CaptionTests(unittest.TestCase):
    def test_native_ocr_batch_preserves_source_coordinates(self):
        class Reader:
            __module__='easyocr.easyocr'
            calls=[]
            def readtext(self,image,**kwargs):
                self.calls.append((image.shape,kwargs))
                return [hit(200,700,400,40)]
        reader=Reader();frame=np.zeros((1080,1920,3),dtype=np.uint8)
        with patch.dict('os.environ',{'DOUYIN_OCR_BATCH_SIZE':'8'}):
            result=read_caption_detections(reader,frame)
        self.assertEqual(reader.calls,[((1080,1920,3),{'batch_size':8})])
        self.assertEqual(result[0][0][0],[200,700])

    def test_top_scene_text_leaves_no_dialogue_region(self):
        self.assertIsNone(caption_box([hit(200,205,500,35)],1080,1000))

    def test_existing_bottom_bar_keeps_short_caption_on_one_line(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'bottom.ass'
            regions = [dict(start=0, end=12, status='existing_bottom_bar',
                            box=dict(x=0, y=964, w=1920, h=116))]
            create_master_subtitles_ass(path, 1920, 1080, 36, 40,
                segments=[dict(start=3.22, end=5.08, text='Tương lai của cô ấy sẽ ra sao')],
                caption_regions=regions)
            content = path.read_text(encoding='utf-8')
            self.assertIn(r'\pos(960.0,1022.0)', content)
            self.assertIn('Tương lai của cô ấy sẽ ra sao', content)

    def test_recovered_crop_coordinates_are_source_coordinates(self):
        class Reader:
            count=0
            def readtext(self,image):
                self.count+=1
                return [hit(400,1200,250,100,confidence=.002)] if self.count==1 else [hit(10,10,230,80)]
        result=read_caption_detections(Reader(),np.zeros((1920,1080,3),dtype=np.uint8))
        self.assertEqual(result[-1][0][0],[402.0,1202.0])
        b=caption_box(result,1080,1920)
        self.assertGreater(b['y'],1100)

    def test_wide_caption_not_capped(self):
        b=caption_box([hit(30,900,1000,40)],1080,1920)
        self.assertLessEqual(b['x'],30)
        self.assertGreaterEqual(b['x']+b['w'],1030)

    def test_two_lines_and_bottom_ten_percent(self):
        b=caption_box([hit(220,930,400,22),hit(200,960,440,22)],1080,1000)
        self.assertLessEqual(b['y'],930)
        self.assertGreaterEqual(b['y']+b['h'],982)

    def test_vertical_and_unrecognized_scene_shapes_rejected(self):
        self.assertIsNone(caption_box([hit(30,300,40,400),hit(80,700,500,30,'',.9),hit(80,700,500,30,confidence=.1)],1080,1920))

    def test_even_bounds_at_edges(self):
        b=caption_box([hit(0,950,1080,50)],1080,1000)
        self.assertEqual(b['x'],0)
        self.assertEqual(b['w'],1080)
        self.assertEqual(b['y']+b['h'],1000)
        self.assertTrue(all(b[k]%2==0 for k in ['x','y','w','h']))

    def test_position_change_splits_dialogue_and_mask(self):
        a=caption_box([hit(40,500,300,40)],1080,1920)
        b=caption_box([hit(600,900,400,40)],1080,1920)
        events=[dict(start=0,end=1,box=a),dict(start=1,end=2,box=b)]
        parts=list(positioned_parts(0,2,'Một câu phụ đề thử nghiệm',events,40,1080,1920))
        self.assertEqual([(p[0],p[1]) for p in parts],[(0,1),(1,2)])
        self.assertIn('\\pos(190.0,520.0)',parts[0][2])
        self.assertIn('\\pos(800.0,920.0)',parts[1][2])
        for mode in ['black_bar','sub_black_bar','blur_sub_black']:
            filters,_=region_filters(events,mode,1080,1920,'[0:v]')
            self.assertIn('lt(t,1.000000)',','.join(filters))

    def test_gap_does_not_inherit_stale_region(self):
        box=caption_box([hit(40,500,300,40)],1080,1920)
        events=[dict(start=0,end=1,box=box),dict(start=1,end=2,box=None),dict(start=2,end=3,box=box)]
        self.assertEqual(len(stabilize_regions(events,1080,1920)),3)
        parts=list(positioned_parts(0,3,'Một câu',events,40,1080,1920))
        self.assertNotIn('\\pos',parts[1][2])

    def test_merge_preserves_widest_extent(self):
        events=[dict(start=0,end=1,box=dict(x=200,y=600,w=400,h=40,center_y=620)),dict(start=1,end=2,box=dict(x=100,y=600,w=600,h=40,center_y=620))]
        merged=stabilize_regions(events,1080,1920)
        self.assertEqual(len(merged),1)
        self.assertEqual(merged[0]['box']['w'],600)

    def test_ass_real_integration_dict_segments(self):
        box=caption_box([hit(40,500,300,40)],1080,1920)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.ass'
            create_master_subtitles_ass(p,1080,1920,40,50,segments=[dict(start=0,end=2,text='Một câu')],caption_regions=[dict(start=0,end=2,box=box)])
            result=p.read_text(encoding='utf-8')
            self.assertIn('\\an5\\pos(190.0,520.0)',result)
            self.assertIn('PlayResY: 1920',result)


if __name__=='__main__':unittest.main()
