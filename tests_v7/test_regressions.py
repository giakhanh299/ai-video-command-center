import json,subprocess,sys
from types import SimpleNamespace as NS
from pathlib import Path
import numpy as np
import pytest
from wuby_studio.common import ROOT,WubyError,NeedsReview
from wuby_studio.captions import Cue
from wuby_studio.renderer import render
from backend import voice_router,sub_processor,wuby_ocr_overlay

def test_short_bottom_chinese_is_not_filtered(source_video,monkeypatch):
    class Reader:
        def readtext(self,frame):return [([[20,500],[220,500],[220,540],[20,540]],'\u4f60\u597d',.8)]
    monkeypatch.setattr(wuby_ocr_overlay,'get_ocr_reader',lambda:Reader())
    monkeypatch.setattr(wuby_ocr_overlay,'detect_scene_ranges',lambda p:[{'scene_id':0,'start':0,'end':2.5,'start_frame':0,'end_frame':59}])
    events=wuby_ocr_overlay.scan_video_text_events(str(source_video),sample_fps=2)
    assert events and events[0]['box'][1]>640*.68

def test_duplicate_title_hidden_not_drawn_twice(tmp_path,cfg,source_video):
    p=tmp_path/'dup.mp4';render(source_video,p,[Cue(.1,2,'Wuby')],'Wuby',cfg)
    r=json.loads(p.with_name('dup_render_report.json').read_text())
    assert any(n['type']=='duplicate_title_hidden_during_caption' for n in r['notes'])

def test_backend_gets_prompt_and_actual_params(tmp_path):
    from backend.voice_router import KhanhOmniVoiceBackend
    b=KhanhOmniVoiceBackend.__new__(KhanhOmniVoiceBackend);captured={}
    b.cfg={'language':'vi','num_step':23,'guidance_scale':2.4,'speed':1.07};b.prompt=object();b.sample_rate=24000;b.reference=NS(audio=tmp_path/'r.wav',text='ref')
    def generate(**kw):captured.update(kw);return [np.sin(np.arange(2400)/10)*.2]
    b.model=NS(generate=generate);b.synthesize('Hi',tmp_path/'raw.wav')
    assert captured['voice_clone_prompt'] is b.prompt and captured['num_step']==23 and captured['guidance_scale']==2.4
    assert captured['speed']==1.07 and captured['language']=='vi'

def test_multi_roles_not_silently_one_voice(tmp_path):
    with pytest.raises(WubyError,match='MULTI_SPEAKER'):sub_processor.generate_dubbed_audio([Cue(0,1,'a','host'),Cue(1,2,'b','character')],str(tmp_path/'o.wav'))

def test_flat_backend_import_works_outside_project(tmp_path):
    code=f"import sys;sys.path.insert(0,{str(ROOT/'backend')!r});import sub_processor,voice_router;import wuby_studio"
    r=subprocess.run([sys.executable,'-c',code],cwd=tmp_path,capture_output=True)
    assert r.returncode==0,r.stderr.decode()
