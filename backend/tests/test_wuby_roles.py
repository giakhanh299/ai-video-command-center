import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
import channel_manager
from wuby_roles import build_ocr_voice_segments, classify_roles, render_roles
from wuby_studio.captions import Cue


def test_wuby_resolves_both_requested_samples_only_for_wuby():
    _,cfg=channel_manager.get_channel_config('wuby')
    roles=cfg['_voice_profile']['role_profiles']
    assert Path(roles['character']['ref_audio']).name=='giongnucute.wav'
    assert Path(roles['narrator']['ref_audio']).name=='2_nu_tre_trung.mp3'
    assert all(r['require_clone'] and not r['fallback_voice'] for r in roles.values())
    _,film=channel_manager.get_channel_config('cauhinh2')
    assert 'role_profiles' not in film['_voice_profile']


def test_ocr_voice_timeline_deduplicates_headers_and_merges_short_cues():
    events = [
        {"start": 0.0, "end": 1.0, "text": "晕车时的我", "vi_text": "Tôi khi bị say xe", "keyframes": [{}] * 20},
        {"start": 1.1, "end": 4.0, "text": "晕车时的我", "vi_text": "TÔI KHI BỊ SAY XE", "keyframes": [{}] * 50},
        {"start": 5.0, "end": 5.2, "text": "打开窗", "vi_text": "Mở cửa sổ", "keyframes": [{}] * 5},
        {"start": 5.5, "end": 6.0, "text": "透透气", "vi_text": "Cho thoáng gió", "keyframes": [{}] * 10},
        {"start": 8.0, "end": 10.0, "text": "晕车时的我", "vi_text": "Tôi khi bị say xe", "keyframes": [{}] * 30},
    ]
    cues = build_ocr_voice_segments(events, 12.0)
    assert len(cues) == 2
    assert cues[0].text == "Tôi khi bị say xe"
    assert cues[0].speaker == "narrator"
    assert cues[1].text == "Mở cửa sổ. Cho thoáng gió"
    assert cues[1].end == 12.0


def client_with(entries):
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs:SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({'roles':entries})))]))))


def test_classification_keeps_explicit_role_and_requires_complete_output():
    cues=[Cue(0,1,'Lời dẫn','narrator'),Cue(2,3,'Câu nhân vật')]
    client=client_with([{'id':0,'role':'character'},{'id':1,'role':'character'}])
    assert classify_roles(cues,client)==['narrator','character']
    with pytest.raises(Exception,match='CLASSIFICATION_FAILED'):
        classify_roles(cues,client_with([{'id':0,'role':'narrator'}]))


def test_role_audio_order_matches_original_timeline(tmp_path):
    import voice_router
    _,cfg=channel_manager.get_channel_config('wuby')
    cues=[Cue(0,3,'Lời dẫn','narrator'),Cue(4,7,'Lời nhân vật','character'),Cue(8,11,'Lời dẫn tiếp','narrator')]
    generated={}
    def synth(texts,paths,cfg,ref):
        for text,path in zip(texts,paths):
            generated[path]=(text,ref.audio.name)
            path.with_suffix('.meta.json').write_text(json.dumps({'is_clone':True}))
        return ['khanh_omnivoice'],[]
    def align(actual,paths,out,*args,**kwargs):
        assert [generated[p][0] for p in paths]==[c.text for c in cues]
        assert [generated[p][1] for p in paths]==['2_nu_tre_trung.mp3','giongnucute.wav','2_nu_tre_trung.mp3']
        assert kwargs['adaptive'] is False
        out.write_bytes(b'test')
        return {}
    with patch.object(voice_router,'_synthesize_missing',side_effect=synth),patch('wuby_studio.audio.align_track',side_effect=align):
        render_roles(cues,tmp_path/'out.wav',cfg['_voice_profile'],12,1)
    report=json.loads((tmp_path/'out_voice_report.json').read_text(encoding='utf-8'))
    assert set(report['role_references'])=={'character','narrator'}
