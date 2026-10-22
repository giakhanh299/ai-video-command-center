import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import wuby_ocr_overlay as o

class OCRHandoffTests(unittest.TestCase):
 def det(self,i,text='甲乙丙',x=100,scene=0):
  return dict(frame_idx=i,time=i/24,scene_id=scene,box=[x,500,600,80],text=text,text_class='chinese',prob=.9,bg_bgr=[255]*3)
 def tracks(self,raw,rate=24,scenes=None):
  return o.build_text_tracks(raw,scenes or [dict(scene_id=0,start=0,end=1)],24,rate)
 def assert_exclusive(self,tracks):
  for i in range(24):
   self.assertLessEqual(sum(t['start']<=i/24<t['end'] for t in tracks),1)
 def test_caption_change_24(self):
  ts=self.tracks([self.det(i,'甲乙丙' if i<6 else '丁戊己') for i in range(24)])
  self.assertEqual(len(ts),2); self.assert_exclusive(ts)
  self.assertEqual(ts[0]['end'],.25);self.assertEqual(ts[1]['start'],.25)
 def test_caption_change_6(self):
  ts=self.tracks([self.det(i,'甲乙丙' if i<6 else '丁戊己') for i in range(0,24,4)],6)
  self.assert_exclusive(ts)
 def test_jitter_does_not_resurrect_old_track(self):
  ts=self.tracks([self.det(0),self.det(1,'丁戊己'),self.det(2)])
  self.assertEqual(len(ts),3);self.assert_exclusive(ts)
 def test_simultaneous_regions_preserved(self):
  ts=self.tracks([self.det(0),self.det(0,'丁戊己',900)])
  self.assertEqual(len(ts),2);self.assertEqual(ts[0]['start'],ts[1]['start'])
 def test_scene_end_exclusive_includes_last_frame(self):
  ts=self.tracks([self.det(23)])
  self.assertEqual(ts[0]['end'],1)
  self.assertTrue(ts[0]['start']<=23/24<ts[0]['end'])
 def test_no_detection(self):self.assertEqual(self.tracks([]),[])
 def test_short_missing_detection_keeps_track(self):
  self.assertEqual(len(self.tracks([self.det(0),self.det(3)])),1)

class AssignmentTests(unittest.TestCase):
 def test_split_lines_get_one_translation(self):
  from types import SimpleNamespace
  evs=[dict(start=0,end=1,box=[100,500,600,80],keyframes=[{}]*24),
       dict(start=.3,end=.4,box=[800,900,100,100],keyframes=[{}]*2)]
  o.match_ocr_events_with_subtitles(evs,segments=[SimpleNamespace(start=0,end=1,text='Một câu thoại')])
  self.assertEqual(sum(bool(e.get('vi_text')) for e in evs),1)
 def test_fast_sequential_fragments_keep_translation(self):
  from types import SimpleNamespace
  evs=[dict(start=0,end=.5,box=[100,500,600,80]),dict(start=.5,end=1,box=[100,500,600,80])]
  o.match_ocr_events_with_subtitles(evs,segments=[SimpleNamespace(start=0,end=1,text='Một câu thoại')])
  self.assertEqual(sum(bool(e.get('vi_text')) for e in evs),2)
 def test_cut_bounds(self):
  helper=OCRHandoffTests();raw=[helper.det(11),helper.det(12,scene=1)]
  ts=helper.tracks(raw,scenes=[dict(scene_id=0,start=0,end=.5),dict(scene_id=1,start=.5,end=1)])
  self.assertLessEqual(ts[0]['end'],.5);self.assertGreaterEqual(ts[1]['start'],.5)

if __name__=='__main__':unittest.main()
