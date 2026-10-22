"""User-requested source rerender with the current Chuyen Hai Dua preset.

Keeps the K6 review intact. One GPU lock, isolated artifacts, no publisher.
"""
import argparse
import contextlib
import copy
import gc
import hashlib
import io
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'backend'), str(ROOT/'tools')]
from render_douyin_intake import FB, atomic, digest, probe, prepare_voice_reference
from autopilot.locks import CrossProcessFileLock

IDENTITY = '7603615402896163514'
TITLE = 'Sách Không Có Kết Thúc Khác'
PROJECT = Path(r'D:\0.1_FACE_BOOK\videos_upload\THU_NGHIEM_ChuyenHaiDua')
WORK = ROOT/'workspace/user_rerender_20261019/CHUYEN_HAI_DUA_SACH'
PRIOR = Path(r'D:\0.1_FACE_BOOK\videos_upload\KENH_006_TieuWuby\02_MOI_RENDER_CHO_XAC_NHAN\sach_khong_co_ket_thuc_khac.mp4')


def stage(name, detail=None):
    atomic(WORK/'progress.json', {'stage': name, 'detail': str(detail or '')[:160],
        'updated_epoch': time.time(), 'publish_permission': 'NONE'})
    print(name, detail or '', flush=True)


def main(resume_bound_work=False):
    from backend import channel_manager, sub_processor, wuby_preflight, video_merger, render_storage
    from backend.render_review_policy import review_filename, validate_voice_assignments
    from wuby_studio.hybrid import frame_finished_wuby
    import torch

    WORK.mkdir(parents=True, exist_ok=True)
    if (WORK/'result.json').exists():
        raise ValueError('RENDER_ALREADY_COMPLETED')
    _, cfg = channel_manager.get_channel_config('chuyen_hai_dua')
    cfg = copy.deepcopy(cfg)
    atomic(WORK/'config.resolved.json', cfg)
    source = PROJECT/f'01_CHUA_RENDER/douyin_{IDENTITY}.mp4'
    recovery_path = source.with_suffix('.recovery.json')
    if not source.exists():
        stage('RECOVER_ORIGINAL_SOURCE', IDENTITY)
        from scan_followed_douyin import download_worker
        source.parent.mkdir(parents=True, exist_ok=True)
        temp = WORK/'download.partial.mp4'
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(io.StringIO()):
            download_worker(IDENTITY, temp)
        detail = json.loads(captured.getvalue().strip().splitlines()[-1])
        duration = probe(temp)
        prior_report = json.loads((ROOT/f'workspace/{IDENTITY}_wuby_preflight.json').read_text(encoding='utf-8'))
        if abs(duration-prior_report['visual']['duration_sec']) > .75:
            raise ValueError('RECOVERED_SOURCE_DURATION_MISMATCH')
        recovery = {'source_id': IDENTITY, 'source_url': 'https://www.douyin.com/video/'+IDENTITY,
            'source_sha256': digest(temp), 'duration': duration, 'title': detail['title'],
            'identity_verified_by': 'provider_aweme_id_equal',
            'historical_byte_identity': 'NOT_VERIFIED_OLD_RAW_REMOVED', 'publish_permission': 'NONE'}
        with temp.open('rb') as src, source.open('xb') as dst:
            shutil.copyfileobj(src, dst)
        atomic(recovery_path, recovery)
    recovery = json.loads(recovery_path.read_text(encoding='utf-8'))
    source_sha = digest(source)
    if recovery['source_id'] != IDENTITY or recovery['source_sha256'] != source_sha:
        raise ValueError('RECOVERED_SOURCE_BINDING_CHANGED')
    duration = probe(source)
    corrected = json.loads((WORK/'translation.corrected.json').read_text(encoding='utf-8'))
    translated = Path(corrected['translated_srt'])
    original = Path(corrected['original_srt'])
    if (corrected['source_id'] != IDENTITY or corrected['source_sha256'] != source_sha
            or digest(translated) != corrected['translated_srt_sha256']
            or digest(original) != corrected['original_srt_sha256']):
        raise ValueError('CORRECTED_TRANSLATION_SOURCE_BINDING_MISMATCH')
    cues = sub_processor.parse_srt_to_segments(str(translated))
    if not cues or len(cues) != corrected['cue_count']:
        raise ValueError('CORRECTED_TRANSLATION_CUE_COUNT_MISMATCH')
    if max(s.end for s in cues) > duration+.75:
        raise ValueError('SUBTITLE_DURATION_MISMATCH')
    srt = WORK/'translated.srt'
    shutil.copyfile(translated, srt)
    shutil.copyfile(original, srt.with_suffix('.orig.srt'))
    originals = sub_processor.parse_srt_to_segments(str(original))
    config_sha = hashlib.sha256(json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if resume_bound_work:
        previous_job = json.loads((WORK/'job.json').read_text(encoding='utf-8'))
        if (previous_job['source_sha256'] != source_sha
                or previous_job['config_sha256'] != config_sha
                or previous_job['translation_sha256'] != digest(srt)
                or previous_job['original_srt_sha256'] != digest(original)):
            raise ValueError('RESUME_INPUT_CONFIG_OR_TRANSLATION_CHANGED')
    atomic(WORK/'job.json', {'source': str(source), 'source_sha256': source_sha,
        'previous_review': str(PRIOR), 'previous_review_sha256': digest(PRIOR),
        'translation_sha256': digest(srt), 'original_srt_sha256': digest(original),
        'translation_binding': 'fresh_chunked_asr_translation_sha256_bound',
        'preset': 'chuyen_hai_dua', 'config': cfg, 'config_sha256': config_sha,
        'title': TITLE, 'publish_permission': 'NONE'})
    if resume_bound_work:
        stage('RESUME_BOUND_PREFLIGHT')
    else:
        stage('FRESH_PREFLIGHT')
        wuby_preflight.analyze_wuby_preflight(video_path=str(source),
            source_segments=originals, target_segments=cues, srt_path=str(srt), movie_title=TITLE,
            config_data=channel_manager.load_channels_config(), cfg=cfg['wuby_preflight'],
            report_path=str(WORK/'preflight.json'))
    # Preflight persists NumPy values through its JSON serializer. Read that
    # canonical report back before embedding events in another JSON artifact.
    report = json.loads((WORK/'preflight.json').read_text(encoding='utf-8'))
    cached_assignments = report['voice']['match']['target_assignments']
    if (report['video'] != str(source) or len(cached_assignments) != len(cues)
            or any(a['text'].strip() != c.text.strip()
                or abs(a['start']-c.start) > .005 or abs(a['end']-c.end) > .005
                for a, c in zip(cached_assignments, cues))):
        raise ValueError('PREFLIGHT_SOURCE_OR_TARGET_CUES_CHANGED')
    plan = report['render_plan']
    if not plan.get('hybrid_frame_allowed', True):
        cfg['wuby_studio']['hybrid_frame']['enabled'] = False
    assignments = report['voice']['match']['target_assignments']
    if len(assignments) != len(cues):
        raise ValueError('VOICE_ASSIGNMENT_COUNT_MISMATCH')
    profiles = {}
    for key in {a['profile'] for a in assignments}:
        profile = channel_manager._resolve_voice_profile(key, channel_manager.load_channels_config(), cfg)
        profile.update(require_clone=True, fallback_voice=None, allow_backend_switch=False, pitch='+0Hz')
        if profile.get('engine') != 'omnivoice':
            raise ValueError('OMNIVOICE_REQUIRED')
        profiles[key] = prepare_voice_reference(profile, WORK)
    sub_processor._cached_transcriber = None
    wuby_preflight.wuby_ocr_overlay._OCR_READER = None
    gc.collect()
    torch.cuda.empty_cache()
    stage('OMNIVOICE_MULTIVOICE', len(cues))
    voice = WORK/'voice.wav'
    sub_processor.generate_dubbed_audio_multivoice(cues, assignments, str(voice), profiles,
        speed=cfg['speed'], total_duration_sec=duration,
        duration_match=cfg['wuby_preflight']['voice_match']['duration_match'], progress_callback=stage)
    validate_voice_assignments(assignments, json.loads(voice.with_suffix('.multivoice.json').read_text(encoding='utf-8')))
    cfg['_wuby_preflight'] = {'ocr_events': report['ocr']['events'],
        'scene_ranges': report['scenes']['ranges'], 'render_plan': plan,
        'ocr_matched': True, 'report_path': str(WORK/'preflight.json')}
    cfg['ocr_fps'] = plan['ocr_sample_fps']
    atomic(WORK/'config.effective.json', cfg)
    stage('RENDER')
    output = WORK/'output.mp4'
    video_merger.process_video_sub_and_mute(str(source), str(output), srt_path=str(srt),
        voice_audio=str(voice), segments=cues, movie_title=TITLE, mask_mode=cfg['mask_mode'],
        channel_cfg=cfg, keep_bg_audio=cfg['keep_bg_audio'], bg_volume=cfg['bg_volume'], use_nvenc=True)
    finished = Path(frame_finished_wuby(output, TITLE, cfg))
    if digest(source) != source_sha or abs(probe(finished)-duration) > .75:
        raise ValueError('SOURCE_OUTPUT_VERIFICATION_FAILED')
    destination = render_storage.review_directory(PROJECT.parent, cfg['drive_folder'])
    if destination != PROJECT/'02_MOI_RENDER_CHO_XAC_NHAN':
        raise ValueError('WRONG_REVIEW_DESTINATION')
    final = render_storage.save_to_review(finished, destination,
        review_filename(TITLE, IDENTITY).replace('.mp4', '__chuyen_hai_dua.mp4'), srt)
    result = {'status': 'RENDERED_PENDING_REVIEW', 'preset': 'chuyen_hai_dua', 'title': TITLE,
        'source_id': IDENTITY, 'input_sha256': source_sha, 'config_sha256': config_sha,
        'output_sha256': digest(final), 'path': str(final), 'duration': probe(final),
        'voices': sorted(profiles), 'voice_assignments_match_actual': True,
        'hybrid_frame_applied': bool(cfg['wuby_studio']['hybrid_frame']['enabled']),
        'visual_review': 'PENDING', 'audio_review': 'PENDING',
        'speaker_identity_verified': False, 'emotion_accepted': False,
        'output_accepted': False, 'publish_permission': 'NONE'}
    atomic(final.with_suffix('.render.json'), result)
    atomic(WORK/'result.json', result)
    stage('COMPLETED', str(final))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume-bound-work', action='store_true')
    args = parser.parse_args()
    os.environ['PATH'] = str(ROOT/'tools/bin')+os.pathsep+os.environ.get('PATH', '')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['WHISPER_DEVICE'] = 'cuda'
    os.environ['WHISPER_COMPUTE_TYPE'] = 'float16'
    os.environ['DOUYIN_OCR_BATCH_SIZE'] = '8'
    os.environ['DOUYIN_VOICE_BATCH_SIZE'] = '4'
    try:
        with CrossProcessFileLock(FB/'runtime/locks/gpu_renderer.lock', timeout_seconds=0):
            main(args.resume_bound_work)
    except Exception as error:
        stage('FAILED', type(error).__name__)
        atomic(WORK/'failure.json', {'error_type': type(error).__name__,
            'message': str(error) if isinstance(error, (TypeError, KeyError, ValueError)) else 'RENDER_ERROR_REQUIRES_REVIEW',
            'locations': [{'file': t.filename, 'line': t.lineno, 'function': t.name}
                for t in traceback.extract_tb(error.__traceback__)], 'publish_permission': 'NONE'})
        raise SystemExit('RENDER_STOPPED_'+type(error).__name__)
