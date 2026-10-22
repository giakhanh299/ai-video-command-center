"""One source-bound full render for the user's separate love-story project."""
import copy
import gc
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'backend'),str(ROOT/'tools')]
from render_douyin_intake import FB, atomic, digest, probe, prepare_voice_reference
from autopilot.locks import CrossProcessFileLock


def main():
    from backend import channel_manager, sub_processor, wuby_preflight, video_merger, render_storage
    from backend.render_review_policy import review_filename, validate_voice_assignments
    from wuby_studio.hybrid import frame_finished_wuby
    import torch
    root=Path(r'D:\0.1_FACE_BOOK\videos_upload\THU_NGHIEM_ChuyenHaiDua')
    source=root/'01_CHUA_RENDER/douyin_7128319752455327012.mp4'
    recovery=json.loads((source.parent/'source_recovery.json').read_text(encoding='utf-8'))
    if digest(source)!=recovery['sha256']:
        raise ValueError('RECOVERED_SOURCE_CHANGED')
    work=ROOT/'workspace/user_bugfix_20261018/CHUYEN_HAI_DUA'
    work.mkdir(parents=True,exist_ok=True)
    if (work/'result.json').exists():
        raise ValueError('LOVE_REPAIR_ALREADY_COMPLETED')
    _,cfg=channel_manager.get_channel_config('chuyen_hai_dua')
    cfg=copy.deepcopy(cfg);cfg['force_render']=True
    src_srt=ROOT/'workspace/7128319752455327012_vi.orig.srt'
    translated=ROOT/'workspace/7128319752455327012_vi.srt.partial.srt'
    old_review=root/'00_BAN_CU_CAN_RENDER_LAI/phat_hien_anh_ay_ve_som_bat_thuong.srt'
    segments=sub_processor.parse_srt_to_segments(str(translated))
    old_review_segments=sub_processor.parse_srt_to_segments(str(old_review))
    # The working SRT was retimed by a few hundredths of a second after the
    # rejected review. Bind provenance to the actual cue sequence rather than
    # requiring byte identity, while still failing closed on text/count changes
    # or a material timing drift.
    if len(segments)!=len(old_review_segments):
        raise ValueError('TRANSLATION_NOT_BOUND_TO_REJECTED_REVIEW')
    if any(a.text.strip()!=b.text.strip() for a,b in zip(segments,old_review_segments)):
        raise ValueError('TRANSLATION_NOT_BOUND_TO_REJECTED_REVIEW')
    if any(abs(a.start-b.start)>.05 or abs(a.end-b.end)>.05
           for a,b in zip(segments,old_review_segments)):
        raise ValueError('TRANSLATION_NOT_BOUND_TO_REJECTED_REVIEW')
    originals=sub_processor.parse_srt_to_segments(str(src_srt))
    duration=probe(source)
    if not segments or max(s.end for s in segments)>duration+.75:
        raise ValueError('TRANSLATION_DURATION_MISMATCH')
    title='Khi Anh Khác Đi'
    atomic(work/'job.json',dict(source=str(source),source_sha256=recovery['sha256'],
                              translated_sha256=digest(translated),
                              rejected_review_srt_sha256=digest(old_review),
                              translation_binding='same_text_sequence_retimed_max_50ms',config=cfg,
                              publish_permission='NONE'))
    print('FRESH_PREFLIGHT',flush=True)
    report=wuby_preflight.analyze_wuby_preflight(video_path=str(source),source_segments=originals,
        target_segments=segments,srt_path=str(translated),movie_title=title,
        config_data=channel_manager.load_channels_config(),cfg=cfg['wuby_preflight'],
        report_path=str(work/'preflight.json'))
    assignments=report['voice']['match']['target_assignments']
    # The rejected audio had a male narrator despite the source female pitch and
    # newer character report. Keep this known check explicit on this one video.
    if any(a['profile'] not in {'omni_nu_cam_xuc','omni_nu_diu_dang'} for a in assignments[:2]):
        raise ValueError('FEMALE_NARRATOR_PLAN_REQUIRES_REVIEW')
    profile_map={}
    for key in {a['profile'] for a in assignments}:
        profile=channel_manager._resolve_voice_profile(key,channel_manager.load_channels_config(),cfg)
        profile.update(require_clone=True,fallback_voice=None,allow_backend_switch=False,pitch='+0Hz',ref_text='')
        profile.setdefault('reference',{})['text']=''
        profile_map[key]=prepare_voice_reference(profile,work)
    sub_processor._cached_transcriber=None;gc.collect();torch.cuda.empty_cache()
    print('EMOTIONAL_CLONE_TTS',len(segments),flush=True)
    voice=work/'voice.wav'
    sub_processor.generate_dubbed_audio_multivoice(segments,assignments,str(voice),profile_map,
        speed=1.,total_duration_sec=duration,duration_match=cfg['wuby_preflight']['voice_match']['duration_match'],
        progress_callback=lambda stage,detail=None:print(stage,detail or '',flush=True))
    actual=json.loads(voice.with_suffix('.multivoice.json').read_text(encoding='utf-8'))
    validate_voice_assignments(assignments,actual)
    cfg['_wuby_preflight']={'ocr_events':report['ocr']['events'],
        'scene_ranges':report['scenes']['ranges'],'render_plan':report['render_plan'],
        'ocr_matched':True,'report_path':str(work/'preflight.json')}
    output=work/'output.mp4'
    video_merger.process_video_sub_and_mute(str(source),str(output),srt_path=str(translated),
        voice_audio=str(voice),segments=segments,movie_title=None,mask_mode='in_video_overlay',
        channel_cfg=cfg,use_nvenc=True)
    finished=Path(frame_finished_wuby(output,title,cfg))
    if digest(source)!=recovery['sha256'] or abs(probe(finished)-duration)>.75:
        raise ValueError('SOURCE_OUTPUT_VERIFICATION_FAILED')
    destination=render_storage.review_directory(root.parent,cfg['drive_folder'])
    final=render_storage.save_to_review(finished,destination,
        review_filename(title,'7128319752455327012').replace('.mp4','__da_sua_cho_xac_nhan.mp4'),translated)
    result=dict(status='DA_SUA_CHO_XAC_NHAN',project='chuyen_hai_dua',title=title,path=str(final),
        input_sha256=recovery['sha256'],output_sha256=digest(final),duration=probe(final),
        voices=sorted(profile_map),voice_assignments_match_actual=True,
        visual_review='PENDING',audio_review='PENDING',freshness_eligibility='NOT_FOR_PUBLISHING',
        publish_permission='NONE',preflight=str(work/'preflight.json'))
    atomic(final.with_suffix('.render.json'),result);atomic(work/'result.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['WHISPER_DEVICE']='cuda';os.environ['WHISPER_COMPUTE_TYPE']='float16'
    with CrossProcessFileLock(FB/'runtime/locks/gpu_renderer.lock',timeout_seconds=0):
        main()
