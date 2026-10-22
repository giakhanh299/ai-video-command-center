"""Audio-only ASR gate. Caller already owns the shared GPU lock.

The score measures script intelligibility, never speaker identity or translation quality.
No publishing, downloads, workers or GPU locks are started here.
"""
from __future__ import annotations
import copy
import gc
import hashlib
import json
import re
import subprocess
import unicodedata
from pathlib import Path


def words(text):
    return re.findall(r'[^\W_]+', unicodedata.normalize('NFC', text).casefold(), re.UNICODE)


def score(reference, hypothesis):
    expected, actual = words(reference), words(hypothesis)
    if not expected:
        raise ValueError('EMPTY_REFERENCE_SCRIPT')
    row = list(range(len(actual) + 1))
    for i, word in enumerate(expected, 1):
        nxt = [i]
        for j, other in enumerate(actual, 1):
            nxt.append(min(nxt[-1] + 1, row[j] + 1, row[j-1] + (word != other)))
        row = nxt
    wer = row[-1] / len(expected)
    return dict(accuracy=max(0.0, 1.0 - wer), wer=wer, errors=row[-1], words=len(expected))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def transcribe(path):
    from faster_whisper import WhisperModel
    model = WhisperModel('large-v3', device='cuda', compute_type='float16')
    try:
        segments, _ = model.transcribe(str(path), language='vi', beam_size=5,
            condition_on_previous_text=False, vad_filter=True, word_timestamps=True,
            temperature=0.0)
        return [dict(start=s.start, end=s.end, text=s.text.strip()) for s in segments]
    finally:
        del model
        gc.collect()
        import torch
        torch.cuda.empty_cache()


def write_srt(rows, path):
    def stamp(value):
        total = round(float(value) * 1000)
        h, total = divmod(total, 3600000)
        m, total = divmod(total, 60000)
        s, ms = divmod(total, 1000)
        return f'{h:02}:{m:02}:{s:02},{ms:03}'
    Path(path).write_text('\n\n'.join(
        f"{i}\n{stamp(r['start'])} --> {stamp(r['end'])}\n{r['text']}"
        for i, r in enumerate(rows, 1)) + '\n', encoding='utf-8')


def export_mp3(wav, mp3):
    try:
        from .video_merger import _ffmpeg_executable
    except ImportError:
        from video_merger import _ffmpeg_executable
    subprocess.run([_ffmpeg_executable(), '-nostdin', '-v', 'error', '-y',
        '-i', str(wav), '-vn', '-c:a', 'libmp3lame', '-b:a', '192k', str(mp3)],
        check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def aligned_srt_for_voice(voice, original_srt):
    """Use actual fitted cue positions for burnt subtitles, preserving every word."""
    try:
        from . import sub_processor
    except ImportError:
        import sub_processor
    original = sub_processor.parse_srt_to_segments(str(original_srt))
    voice = Path(voice)
    report = json.loads(voice.with_name(voice.stem+'_voice_report.json').read_text(encoding='utf-8'))
    if report.get('output_sha256') != digest(voice):
        raise RuntimeError('VOICE_TIMELINE_REPORT_STALE')
    rows = [dict(start=c['start'], end=c['spoken_end'], text=c['text']) for c in report['cues']]
    if [words(c['text']) for c in rows] != [words(s.text) for s in original]:
        raise RuntimeError('VOICE_TIMELINE_SCRIPT_MISMATCH')
    if any(c['end'] <= c['start'] for c in rows) or any(
            a['end'] > b['start'] + .001 for a,b in zip(rows,rows[1:])):
        raise RuntimeError('VOICE_TIMELINE_OVERLAP')
    target = voice.with_name(voice.stem+'_aligned.srt')
    write_srt(rows,target)
    return str(target)


def regenerate(srt, output, cfg, speed, duration):
    try:
        from . import sub_processor
    except ImportError:
        import sub_processor
    profile = copy.deepcopy(cfg['_voice_profile'])
    profile.update(engine='omnivoice', require_clone=True, fallback_voice=None,
                   allow_backend_switch=False, pitch='+0Hz')
    # Bind conditioning text to the spoken reference, not an unverified label.
    ref = profile.get('ref_audio') or (profile.get('reference') or {}).get('audio')
    if ref:
        try:
            from . import voice_router
        except ImportError:
            import voice_router
        reference = voice_router._reference_from_config(Path(srt), profile)
        rows = transcribe(reference.audio)
        text = ' '.join(r['text'] for r in rows)
        if not text.strip():
            raise RuntimeError('EMPTY_CLONE_REFERENCE_TRANSCRIPT')
        profile['ref_audio'], profile['ref_text'] = str(reference.audio), text
        profile['reference'] = dict(audio=str(reference.audio), text=text)
    profile['duration_match'] = copy.deepcopy(cfg['_voice_profile'].get('duration_match') or
        dict(adaptive=False, max_speedup=1.8, minimum_gap_sec=0.05))
    profile['synthesis_speed'] = float(cfg.get('synthesis_speed', 0.9))
    profile['playback_speed'] = float(cfg.get('speed', 1.4))
    profile['accuracy_attempt'] = Path(output).stem
    sub_processor._cached_transcriber = None
    gc.collect()
    import torch
    torch.cuda.empty_cache()
    segments = sub_processor.parse_srt_to_segments(str(srt))
    sub_processor.generate_dubbed_audio(segments, str(output), voice=cfg['voice'],
        speed=speed, total_duration_sec=duration, voice_profile=profile, force=True)


def verify_or_repair(voice, srt, cfg, duration):
    gate = cfg.get('voice_accuracy') or {}
    if not gate.get('enabled'):
        return str(voice)
    if not srt or not Path(srt).is_file():
        raise RuntimeError('DUB_QC_REQUIRES_APPROVED_SRT')
    try:
        from . import sub_processor
    except ImportError:
        import sub_processor
    expected = sub_processor.parse_srt_to_segments(str(srt))
    script = ' '.join(s.text for s in expected)
    root = Path(voice).parent / (Path(voice).stem + '_accuracy')
    root.mkdir(exist_ok=True)
    binding = dict(voice_sha256=digest(voice), srt_sha256=digest(srt),
                   playback_speed=cfg.get('speed'), synthesis_speed=cfg.get('synthesis_speed'),
                   voice_profile=cfg.get('_voice_profile'), gate=gate, duration=duration)
    fingerprint = hashlib.sha256(json.dumps(binding, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    report_path = root / 'report.json'
    if report_path.exists():
        old = json.loads(report_path.read_text(encoding='utf-8'))
        if (old.get('binding') == fingerprint and old.get('passed')
                and Path(old['approved_wav']).is_file()
                and digest(old['approved_wav']) == old['approved_sha256']
                and Path(old['approved_mp3']).is_file()
                and digest(old['approved_mp3']) == old['approved_mp3_sha256']):
            return old['approved_wav']
    threshold = max(0.95, float(gate.get('min_accuracy', 0.95)))
    attempts = []
    # Bounded automatic repair; on exhaustion keep evidence and block video output.
    # Retry synthesis at the requested playback rate; never approve a slower final MP3.
    speeds = [None] + [float(cfg.get('speed', 1.4))] * (max(1, min(4, int(gate.get('max_attempts', 4))))-1)
    for attempt, speed in enumerate(speeds):
        wav = Path(voice) if speed is None else root / f'attempt_{attempt}_speed_{speed}.wav'
        if speed is not None:
            regenerate(srt, wav, cfg, speed, duration)
        mp3 = root / f'attempt_{attempt}.mp3'
        export_mp3(wav, mp3)
        rows = transcribe(mp3)  # No initial prompt or supplied script to bias recognition.
        write_srt(rows, root / f'attempt_{attempt}_recognized.srt')
        result = score(script, ' '.join(r['text'] for r in rows))
        attempts.append(dict(attempt=attempt, speed=speed or cfg.get('speed'), **result))
        passed = result['accuracy'] > threshold
        report = dict(binding=fingerprint, metric='1-word_error_rate', threshold=threshold,
            passed=passed, attempts=attempts, publish_permission='NONE',
            approved_wav=str(wav) if passed else None, approved_mp3=str(mp3) if passed else None,
            approved_sha256=digest(wav) if passed else None,
            approved_mp3_sha256=digest(mp3) if passed else None)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        if passed:
            return str(wav)
    raise RuntimeError(f'DUB_ACCURACY_BELOW_THRESHOLD: see {report_path}')
