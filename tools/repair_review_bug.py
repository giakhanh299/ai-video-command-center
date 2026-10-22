"""Bounded local rerender of the two videos identified in the user's bug files.

Reuses the reviewed translation.  K5 regenerates its voice from the current
audio-bound clone reference; K8 preserves source audio.  No download, Sheet,
Telegram, publishing, worker restart or background loop.
"""
import argparse
import copy
import gc
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'backend'), str(ROOT/'tools')]
from render_douyin_intake import (FB, WORK, atomic, digest, probe,
                                  prepare_voice_reference, resolve_config)
from autopilot.locks import CrossProcessFileLock

JOBS = {'KENH_005': ('7696888633298668836', '946cc029d5f6'),
        'KENH_008': ('7696860867774116729', 'adc89d1c7c83')}


def repair(channel, reuse_geometry=False):
    from backend import render_storage, sub_processor, video_merger
    from backend.render_review_policy import review_filename, require_channel_destination
    vid, suffix = JOBS[channel]
    old = WORK / f'{channel}_{vid}_{suffix}'
    job = json.loads((old/'job.json').read_text(encoding='utf-8'))
    prior = json.loads((old/'result.json').read_text(encoding='utf-8'))
    source = Path(job['source'])
    if digest(source) != job['input_sha256']:
        raise ValueError('SOURCE_HASH_CHANGED')
    work = ROOT / 'workspace/user_bugfix_20261018' / channel
    if (work/'result.json').exists():
        raise ValueError('REPAIR_ALREADY_COMPLETED_RECONCILE_FIRST')
    work.mkdir(parents=True, exist_ok=True)
    roots = {c['channel_id']: Path(c['workspace_root']) for c in
             json.loads((FB/'config/channels.json').read_text(encoding='utf-8-sig'))}
    cfg = resolve_config(roots[channel].name)
    if (cfg.get('subtitle_detection',{}).get('mode') != 'lower_third_precise'
            or cfg['subtitle_detection'].get('allow_estimated_mask') is not False):
        raise ValueError('PRECISE_MASK_CONFIG_REQUIRED')
    cfg = copy.deepcopy(cfg)
    cfg['force_render'] = True
    if reuse_geometry:
        cached_job=json.loads((work/'job.json').read_text(encoding='utf-8'))
        cached_geometry=json.loads((work/'output.subtitle_regions.json').read_text(encoding='utf-8'))
        if (cached_job['source_sha256'] != job['input_sha256']
                or cached_job['config']['subtitle_detection'] != cfg['subtitle_detection']):
            raise ValueError('CACHED_GEOMETRY_NOT_BOUND_TO_CURRENT_JOB')
        cfg['_caption_regions_cache']={'input_sha256':job['input_sha256'],
            'subtitle_detection':cfg['subtitle_detection'],'regions':cached_geometry}
    segments = sub_processor.parse_srt_to_segments(str(old/'translated.srt'))
    voice = None
    voice_reference = None
    if channel == 'KENH_005':
        profile=prepare_voice_reference(cfg['_voice_profile'],old)
        if profile.get('engine')!='omnivoice' or not profile.get('require_clone'):
            raise ValueError('BOUND_OMNIVOICE_CLONE_REQUIRED')
        voice_reference={
            'audio':profile.get('ref_audio'),
            'audio_sha256':digest(profile['ref_audio']),
            'text':profile.get('ref_text'),
            'transcript_source':profile.get('reference_transcript_source'),
        }
        # The ASR model used to verify the reference can occupy most of the GPU.
        # Release it before loading the local clone model.
        sub_processor._cached_transcriber=None;gc.collect()
        import torch
        torch.cuda.empty_cache()
        voice=work/'voice.regenerated.wav'
        sub_processor.generate_dubbed_audio(
            segments,str(voice),voice=cfg['voice'],speed=cfg.get('speed',1),
            total_duration_sec=probe(source),voice_profile=profile)
        if not voice.is_file() or voice.stat().st_size < 1000:
            raise ValueError('REGENERATED_VOICE_MISSING')
    atomic(work/'job.json', dict(source=str(source), source_sha256=job['input_sha256'],
                                 config=cfg, previous_output=prior['path'],
                                 voice_asset=str(voice) if voice else None,
                                 voice_asset_sha256=digest(voice) if voice else None,
                                 voice_reference=voice_reference))
    output = work/'output.mp4'
    video_merger.process_video_sub_and_mute(
        str(source), str(output), srt_path=str(old/'translated.srt'),
        voice_audio=str(voice) if voice else None, segments=segments,
        movie_title=prior['title'], mask_mode=cfg['mask_mode'], channel_cfg=cfg,
        keep_bg_audio=True,
        bg_volume=float(cfg.get('bg_volume',.1)) if voice else 1.0,
        use_nvenc=True)
    duration = probe(output)
    if abs(duration-probe(source)) > .75 or digest(source) != job['input_sha256']:
        raise ValueError('OUTPUT_SOURCE_VERIFICATION_FAILED')
    regions = json.loads(output.with_suffix('.subtitle_regions.json').read_text(encoding='utf-8'))
    if not any(r.get('box') and r.get('status')=='verified' for r in regions):
        raise ValueError('NO_VERIFIED_CAPTION_GEOMETRY')
    if any(r.get('box') and r.get('status') != 'verified' for r in regions):
        raise ValueError('UNVERIFIED_MASK_PRESENT')
    if channel == 'KENH_005':
        # These source-caption/gap timestamps were checked against real frames.
        for ts, expected in ((4.,True),(9.,True),(82.3,True),(178.2,False)):
            region=next((r for r in regions if r['start']<=ts<r['end']),{})
            if bool(region.get('box')) != expected:
                raise ValueError('KNOWN_SOURCE_CAPTION_OR_GAP_NOT_MATCHED')
    if channel == 'KENH_008':
        for ts in (5.,26.,56.):
            if not next((r.get('box') for r in regions if r['start']<=ts<r['end']),None):
                raise ValueError('KNOWN_K8_CAPTION_NOT_COVERED')
    destination = render_storage.review_directory(Path(r'D:\0.1_FACE_BOOK\videos_upload'),cfg['drive_folder'])
    require_channel_destination(channel,destination,roots)
    filename = review_filename(prior['title'],vid).replace('.mp4','__da_sua_cho_xac_nhan.mp4')
    final = render_storage.save_to_review(output,destination,filename,old/'translated.srt')
    result = dict(status='DA_SUA_CHO_XAC_NHAN', channel=channel, id=vid, title=prior['title'],
                  source_path=str(source), input_sha256=job['input_sha256'],
                  config_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                  output_sha256=digest(final), path=str(final), duration=duration,
                  previous_output=prior['path'], publish_permission='NONE',
                  mask_report=str(output.with_suffix('.subtitle_regions.json')),
                  visual_review='PENDING', audio_review='PENDING',
                  voice_changed=(channel=='KENH_005'),
                  voice_asset_sha256=digest(voice) if voice else None,
                  voice_reference=voice_reference,
                  original_audio_preserved=(voice is None))
    atomic(final.with_suffix('.render.json'),result)
    atomic(work/'result.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--channel', choices=list(JOBS), required=True)
    parser.add_argument('--reuse-geometry',action='store_true')
    args=parser.parse_args()
    with CrossProcessFileLock(FB/'runtime/locks/gpu_renderer.lock',timeout_seconds=0):
        repair(args.channel,args.reuse_geometry)
