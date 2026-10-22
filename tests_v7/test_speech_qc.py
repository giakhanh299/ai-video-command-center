from types import SimpleNamespace as NS
import pytest
from wuby_studio.speech_qc import compare,verify
from wuby_studio.common import NeedsReview
from wuby_studio.captions import Cue

def test_normalized_words_not_punctuation():
    assert compare('Xin ch\u00e0o!', 'xin ch\u00e0o.')['matched']

def test_repeated_generated_phrase_flagged():
    r=compare('em vui', 'em vui em vui em vui')
    assert not r['matched'] and r['possible_repetition_or_extra_words']

def test_missing_words_flagged():assert not compare('em muon di choi vao ngay mai','em')['matched']

def test_preapproved_repetition_not_deleted():assert compare('ha ha ha','ha ha ha')['matched']

def test_mismatch_saves_evidence_not_rewrites(tmp_path,tone):
    audio=tone(tmp_path/'voice.wav',1)
    mock=lambda *a,**k:([NS(start=0,end=1,text='something entirely different')],NS())
    with pytest.raises(NeedsReview,match='SPOKEN_TEXT_MISMATCH'):verify(audio,[Cue(0,1,'xin chao')],{'speech_qc':{'enabled':True}},mock)
    assert audio.with_name('voice_speech_qc.json').is_file()

def test_disabled_not_pass(tmp_path,tone):
    a=tone(tmp_path/'v.wav',1);assert verify(a,[Cue(0,1,'Hi')],{'speech_qc':{'enabled':False}})['status']=='not_run'
