import asyncio,copy,json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import soundfile as sf
import pytest
from backend import voice_router as router,sub_processor
from wuby_studio.captions import Cue,write_srt
from wuby_studio.audio import align_track,require_voice_report,waveform_quality
from wuby_studio.voice_pipeline import render,generation_identity,check_approval,approval_key
from wuby_studio.common import WubyError,TimingError,NeedsReview,sha256,atomic_json

@pytest.fixture
def voice(tmp_path,tone,monkeypatch):
    ref=tone(tmp_path/'ref.wav',sec=2.4)
    cfg={'engine':'omnivoice','model':'test_model_not_real','num_step':20,'guidance_scale':2,'require_clone':True,
         'ref_audio':str(ref),'ref_text':'reference transcript','project_root':str(tmp_path),'speed':1.0}
    calls=[]
    class FakeBackend:
        is_clone_backend=True
        def synthesize(self,text,out):calls.append(text);return tone(out,sec=.4)
        def release(self):pass
    monkeypatch.setattr(router,'_make_backend',lambda *a:FakeBackend())
    monkeypatch.setattr(router,'_empty_cuda_cache',lambda:None)
    srt=tmp_path/'in.srt';write_srt([Cue(0,1,'Xin chao'),Cue(1.1,2,'Em vui')],srt)
    return cfg,srt,calls,FakeBackend

def perform(tmp_path,voice):
    cfg,srt,_,_=voice;out=tmp_path/'voice.wav';render(router,srt,out,cfg,video_duration=2.5);return out

def test_strict_cache_and_truthful_report(tmp_path,voice):
    out=perform(tmp_path,voice);assert len(voice[2])==2
    perform(tmp_path,voice);assert len(voice[2])==2
    report=json.loads(out.with_name('voice_voice_report.json').read_text())
    assert report['clone_conditioned'] is True and report['speaker_identity_verified'] is False
    assert report['clone_success'] is False and report['new_cue_count']==0
    assert report['overlap_count']==report['truncated_cues']==0

@pytest.mark.parametrize('field,value',[('num_step',25),('guidance_scale',2.6),('speed',1.1),('model','other_model'),('ref_text','new reference')])
def test_generation_change_invalidates(tmp_path,voice,field,value):
    perform(tmp_path,voice);voice[0][field]=value;perform(tmp_path,voice);assert len(voice[2])==4

def test_reference_same_filename_changed_bytes(tmp_path,voice,tone):
    perform(tmp_path,voice);tone(voice[0]['ref_audio'],sec=2.4,hz=500);perform(tmp_path,voice);assert len(voice[2])==4

def test_cache_audio_modified_rejected(tmp_path,voice,tone):
    perform(tmp_path,voice);p=next((tmp_path/'.cache/wuby_voice_v7').glob('*.wav'));tone(p,sec=.4,hz=500)
    perform(tmp_path,voice);assert len(voice[2])==3

def test_cache_preset_not_clone(tmp_path,voice):
    perform(tmp_path,voice);p=next((tmp_path/'.cache/wuby_voice_v7').glob('*.meta.json'));d=json.loads(p.read_text());d['is_clone']=False;atomic_json(p,d)
    perform(tmp_path,voice);assert len(voice[2])==3

def test_no_preset_fallback_when_model_fails(tmp_path,voice,monkeypatch):
    def fail(*a):raise RuntimeError('model OOM simulation')
    monkeypatch.setattr(router,'_make_backend',fail)
    with pytest.raises(router.VoiceBackendError,match='CLONE_FAILED'):perform(tmp_path,voice)
    assert not (tmp_path/'voice.wav').exists()

def test_preset_backend_rejected(tmp_path,voice):
    voice[3].is_clone_backend=False
    with pytest.raises(WubyError,match='PRESET_RETURNED'):perform(tmp_path,voice)
    assert not (tmp_path/'voice.wav').exists()

def test_missing_reference_stops_before_model(tmp_path,voice):
    voice[0]['ref_audio']=str(tmp_path/'missing.wav')
    with pytest.raises(router.VoiceBackendError,match='MISSING'):perform(tmp_path,voice)
    assert not voice[2]

def test_silent_ref_rejected(tmp_path,voice):
    sf.write(voice[0]['ref_audio'],np.zeros(57600),24000)
    with pytest.raises(WubyError,match='SILENT'):perform(tmp_path,voice)

def test_no_silent_or_empty_script(tmp_path):
    with pytest.raises(WubyError,match='EMPTY_SCRIPT'):sub_processor.generate_dubbed_audio([],str(tmp_path/'o.wav'))

def test_unknown_profile_fails(tmp_path):
    with pytest.raises(WubyError,match='UNKNOWN_VOICE_PROFILE'):sub_processor.generate_dubbed_audio([Cue(0,1,'x')],str(tmp_path/'o.wav'),voice='unknown')

def test_unknown_engine_never_edge(tmp_path):
    with pytest.raises(RuntimeError,match='UNKNOWN_TTS_ENGINE'):
        asyncio.run(sub_processor._render_tts_chunk('Hi',{'engine':'TYPO','require_clone':False},str(tmp_path/'x.wav')))

def test_long_voice_no_truncation_or_overlap(tmp_path,tone):
    paths=[tone(tmp_path/'a.wav',2),tone(tmp_path/'b.wav',.4)]
    with pytest.raises(TimingError,match='VOICE_TOO_LONG'):align_track([Cue(0,1,'a'),Cue(1.1,2,'b')],paths,tmp_path/'out.wav',2.5)
    assert not (tmp_path/'out.wav').exists()

def test_atempo_pitch_preserving(tmp_path,tone):
    p=tone(tmp_path/'raw.wav',2.12,hz=440)
    report=align_track([Cue(0,2,'tone')],[p],tmp_path/'out.wav',2)
    y,sr=sf.read(tmp_path/'out.wav');spec=np.abs(np.fft.rfft(y));freq=np.fft.rfftfreq(len(y),1/sr)[np.argmax(spec)]
    assert abs(freq-440)<3 and report['pitch_preserving_time_stretch']
    assert report['cues'][0]['spoken_end']<=2

def test_voice_report_stale_not_allowed(tmp_path,voice,tone):
    out=perform(tmp_path,voice);tone(out,.5)
    with pytest.raises(NeedsReview,match='STALE'):require_voice_report(out,[Cue(0,1,'Xin chao'),Cue(1.1,2,'Em vui')])

def test_nested_secret_not_in_cache_identity():
    ident=generation_identity({'router':{'token':'secret','steps':12},'api_key':'secret','model':'a'})
    assert ident=={'router':{'steps':12},'model':'a'}

def test_approval_missing(tmp_path,voice):
    ref=router._reference_from_config(voice[1],voice[0])
    with pytest.raises(NeedsReview,match='APPROVAL_REQUIRED'):check_approval(voice[0],ref,tmp_path)

def test_full_config_reaches_router_once_speed(tmp_path,voice,monkeypatch):
    captured={}
    def spy(srt,out,cfg,**kw):captured.update(cfg);return str(out)
    monkeypatch.setattr(router,'render_srt_voice_track',spy)
    cfg=voice[0];cfg['speed']=1.0;cfg['speed_multiplier']=1.1
    sub_processor.generate_dubbed_audio([Cue(0,1,'Hi')],str(tmp_path/'out.wav'),voice_profile=cfg,total_duration_sec=1)
    assert captured['num_step']==20 and captured['guidance_scale']==2 and abs(captured['speed']-1.1)<1e-8
    assert captured['reference']['text']=='reference transcript'
