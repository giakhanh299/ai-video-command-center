from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from wuby_studio.audio import align_track
from wuby_studio.common import TimingError


def test_slow_clone_is_sped_up_without_changing_pitch_or_timeline(tmp_path):
    sr = 24000
    raw = tmp_path/'raw.wav'
    x = 0.2*np.sin(2*np.pi*440*np.arange(sr*2)/sr)
    sf.write(raw, x, sr)
    cue = SimpleNamespace(start=1.0, end=3.5, text='Chào cô gái', speaker='cute')
    out = tmp_path/'fitted.wav'
    report = align_track([cue], [raw], out, duration=4.0,
                         max_speedup=1.8, adaptive=False, base_tempo=1.4/0.9)
    item = report['cues'][0]
    assert item['start'] == 1.0
    assert item['spoken_end'] <= item['reserved_end']
    assert item['atempo'] == pytest.approx(1.4/0.9)
    assert item['spoken_end']-item['start'] == pytest.approx(2/(1.4/0.9), abs=0.06)
    y, actual_sr = sf.read(out)
    active = y[int(1.1*sr):int(1.8*sr)]
    hz = np.fft.rfftfreq(len(active), 1/actual_sr)[np.argmax(np.abs(np.fft.rfft(active)))]
    assert hz == pytest.approx(440, abs=5)
    assert len(y)/actual_sr == 4.0
    assert report['truncated_cues'] == 0


def test_overlong_sentence_is_rejected_without_cutting_words(tmp_path):
    sr=24000
    raw=tmp_path/'long.wav'
    sf.write(raw, .2*np.sin(2*np.pi*440*np.arange(sr*3)/sr), sr)
    cue=SimpleNamespace(start=0.0,end=0.5,text='Câu quá dài',speaker='cute')
    with pytest.raises(TimingError, match='VOICE_TOO_LONG'):
        align_track([cue],[raw],tmp_path/'out.wav',duration=.5,
                    max_speedup=1.8,adaptive=False,base_tempo=1.4/.9)
    assert not (tmp_path/'out.wav').exists()


def test_short_sentence_can_borrow_only_preceding_silence(tmp_path):
    sr=24000
    raw=tmp_path/'raw.wav'
    sf.write(raw,.2*np.sin(2*np.pi*440*np.arange(int(sr*1.5))/sr),sr)
    cue=SimpleNamespace(start=1.0,end=1.7,text='Cháu câu ít về',speaker='cute')
    report=align_track([cue],[raw],tmp_path/'out.wav',duration=1.7,
                      max_speedup=1.8,adaptive=False,base_tempo=1.4/.9,max_early_start=.25)
    item=report['cues'][0]
    assert .75 <= item['start'] < 1.0
    assert item['spoken_end'] <= 1.7
    assert report['truncated_cues']==0
