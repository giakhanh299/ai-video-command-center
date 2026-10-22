import json
from pathlib import Path

import pytest
import dub_accuracy as qc


def test_wer_counts_missing_and_extra_words_and_keeps_vietnamese_accents():
    assert qc.score('Chào, cô gái!', 'chào cô gái')['accuracy'] == 1
    assert qc.score('một hai ba bốn', 'một ba bốn')['accuracy'] == 0.75
    assert qc.score('cá', 'ca')['accuracy'] == 0
    assert qc.score('một', 'một hai')['accuracy'] == 0
    with pytest.raises(ValueError):
        qc.score('', 'lời không có trong kịch bản')


@pytest.fixture
def job(tmp_path, monkeypatch):
    wav, srt = tmp_path/'voice.wav', tmp_path/'script.srt'
    wav.write_bytes(b'original voice')
    srt.write_text('1\n00:00:00,000 --> 00:00:03,000\nChào cô gái\n', encoding='utf-8')
    monkeypatch.setattr(qc, 'export_mp3', lambda wav, mp3: Path(mp3).write_bytes(Path(wav).read_bytes()))
    return wav, srt, {'voice_accuracy': {'enabled': True, 'max_attempts': 3},
                      'speed': 1.15, '_voice_profile': {'engine': 'omnivoice'}}


def test_repair_then_approve_only_recognized_correct_audio(job, monkeypatch):
    wav, srt, cfg = job
    transcripts = iter(['Chào chú', 'Chào cô gái'])
    monkeypatch.setattr(qc, 'transcribe', lambda _: [dict(start=0, end=3, text=next(transcripts))])
    regenerated = []
    def repair(srt, out, cfg, speed, duration):
        regenerated.append(speed)
        Path(out).write_bytes(b'corrected audio')
    monkeypatch.setattr(qc, 'regenerate', repair)
    approved = qc.verify_or_repair(wav, srt, cfg, 3)
    assert approved != str(wav)
    assert wav.read_bytes() == b'original voice'
    report = json.loads((wav.parent/'voice_accuracy/report.json').read_text())
    assert report['passed'] and report['attempts'][-1]['accuracy'] == 1
    assert len(report['attempts']) == 2
    assert Path(report['approved_mp3']).exists()
    # A verified cached artifact is reused without rerunning ASR.
    assert qc.verify_or_repair(wav, srt, cfg, 3) == approved
    assert len(regenerated) == 1


def test_exhausted_retries_block_output_and_keep_diagnostics(job, monkeypatch):
    wav, srt, cfg = job
    monkeypatch.setattr(qc, 'transcribe', lambda _: [dict(start=0, end=3, text='không khớp')])
    monkeypatch.setattr(qc, 'regenerate', lambda srt, out, *args: Path(out).write_bytes(b'candidate'))
    with pytest.raises(RuntimeError, match='BELOW_THRESHOLD'):
        qc.verify_or_repair(wav, srt, cfg, 3)
    report = json.loads((wav.parent/'voice_accuracy/report.json').read_text())
    assert not report['passed'] and report['approved_mp3'] is None
    assert len(report['attempts']) == 3
    assert (wav.parent/'voice_accuracy/attempt_2_recognized.srt').exists()


def test_missing_script_is_never_approved(job):
    wav, srt, cfg = job
    with pytest.raises(RuntimeError, match='REQUIRES_APPROVED_SRT'):
        qc.verify_or_repair(wav, srt.with_name('missing.srt'), cfg, 3)


def test_subtitles_follow_actual_fitted_voice_and_reject_changed_audio(job):
    wav,srt,cfg=job
    report=wav.with_name('voice_voice_report.json')
    report.write_text(json.dumps({'output_sha256':qc.digest(wav),
        'cues':[dict(start=.1,spoken_end=2.6,text='Chào cô gái')]}),encoding='utf-8')
    aligned=qc.aligned_srt_for_voice(wav,srt)
    assert '00:00:00,100 --> 00:00:02,600' in Path(aligned).read_text(encoding='utf-8')
    wav.write_bytes(b'changed')
    with pytest.raises(RuntimeError,match='STALE'):
        qc.aligned_srt_for_voice(wav,srt)
