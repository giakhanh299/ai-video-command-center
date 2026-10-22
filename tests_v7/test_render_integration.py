import json
from fractions import Fraction
from pathlib import Path
import numpy as np
import pytest
from PIL import Image,ImageDraw
from wuby_studio.captions import Cue,cue_hash
from wuby_studio.renderer import render,rerender
from wuby_studio.media import probe,frame_rate
from wuby_studio.common import NeedsReview,ConfigError,sha256,atomic_json,run,binary

def test_real_render_fps_caption_logo_audio(tmp_path,cfg,source_video):
    logo=tmp_path/'logo.png';Image.new('RGBA',(180,50),(20,10,10,180)).save(logo)
    cfg['logo'].update(enabled=True,path=str(logo),mode='drift_fade')
    out=tmp_path/'render.mp4'
    render(source_video,out,[Cue(.1,1.0,'Xin ch\u00e0o'),Cue(1.2,2.3,'D\u1ec5 th\u01b0\u01a1ng')],'Wuby',cfg)
    report=json.loads(out.with_name('render_render_report.json').read_text())
    assert report['fps'] in ('12/1', '24/1') and report['layout_collisions']==0 and not report['clone_conditioned']
    assert probe(out)['audio'] and abs(probe(out)['duration']-2.5)<.05
    run([binary('ffmpeg'),'-v','error','-i',str(out),'-f','null','-'])
    assert len(list((tmp_path/'render_frames').glob('*.jpg')))==5

def test_missing_clone_audio_no_preset_substitute(tmp_path,cfg,source_video):
    cfg['audio']['mode']='clone'
    with pytest.raises(NeedsReview,match='CLONE_AUDIO_REQUIRED'):render(source_video,tmp_path/'out.mp4',[],'',cfg)

def test_reprocessed_burnt_input_requires_crop(tmp_path,cfg,source_video):
    cfg['cleanup']['input_already_rendered']=True
    with pytest.raises(NeedsReview,match='ALREADY_BURNED'):render(source_video,tmp_path/'out.mp4',[],'',cfg)

def test_visual_rerender_hash_guards(tmp_path,cfg,source_video):
    out=tmp_path/'out.mp4';render(source_video,out,[],'',cfg)
    packet=out.with_name('out_visual_packet.json')
    rerender(packet,tmp_path/'mint.mp4',{'theme':'mint'})
    assert (tmp_path/'mint.mp4').is_file()
    with pytest.raises(ConfigError):rerender(packet,tmp_path/'bad.mp4',{'audio':{'mode':'silent'}})
    source_video.write_bytes(source_video.read_bytes()+b'changed')
    with pytest.raises(NeedsReview,match='SOURCE_CHANGED'):rerender(packet,tmp_path/'bad.mp4')

def test_sfx_skips_speech_and_mixes_gap(tmp_path,cfg,source_video,tone):
    p=tone(tmp_path/'fx.wav',.15,hz=880);cfg['sfx'].update(enabled=True,events=[{'path':str(p),'start':.2},{'path':str(p),'start':1.5}])
    out=tmp_path/'sfx.mp4';render(source_video,out,[Cue(0,1,'Hi')],'',cfg)
    r=json.loads(out.with_name('sfx_render_report.json').read_text())
    assert [x['status'] for x in r['sfx']]==['skipped_over_speech','mixed']

def test_legacy_entrypoint_reaches_v7(tmp_path,cfg,source_video):
    from backend.video_merger import process_video_sub_and_mute
    out=tmp_path/'compat.mp4'
    process_video_sub_and_mute(str(source_video),str(out),segments=[Cue(.1,2,'Hello')],channel_cfg={'workflow':'wuby','wuby_studio':cfg})
    assert out.is_file() and out.with_name('compat_visual_packet.json').is_file()

def test_fps_source_fraction_not_rounded():
    m={'video':{'avg_frame_rate':'24000/1001','r_frame_rate':'24000/1001'}}
    assert Fraction(frame_rate(m))==Fraction(24000,1001)
    assert Fraction(frame_rate(m,'30'))==30

def test_clone_mix_does_not_keep_original_speech(tmp_path,cfg,source_video,tone):
    from wuby_studio.audio import align_track
    p=tone(tmp_path/'fake_backend_tone.wav',sec=.8,hz=700)
    cues=[Cue(.1,1,'Test fixture only')];voice=tmp_path/'voice.wav'
    report=align_track(cues,[p],voice,2.5)
    report.update(schema=7,output_sha256=sha256(voice),clone_conditioned=True)
    atomic_json(voice.with_name('voice_voice_report.json'),report)
    cfg['audio']['mode']='clone';cfg['audio']['normalize_voice']=False
    out=tmp_path/'mix.mp4';render(source_video,out,cues,'',cfg,voice)
    raw=run([binary('ffmpeg'),'-v','error','-i',str(out),'-vn','-f','f32le','-ac','1','-ar','24000','-']).stdout
    x=np.frombuffer(raw,dtype='<f4');window=x[round(.2*24000):round(.7*24000)]
    spectrum=np.abs(np.fft.rfft(window));freq=np.fft.rfftfreq(len(window),1/24000)
    a=np.max(spectrum[(freq>695)&(freq<705)]);b=np.max(spectrum[(freq>325)&(freq<335)])
    assert a>20*b
    # This validates mix routing using tones, NOT cloning quality.
