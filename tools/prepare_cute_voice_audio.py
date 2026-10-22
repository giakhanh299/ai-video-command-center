"""One audio-only job: acquire the existing GPU lock, clone, export MP3, verify ASR."""
import sys
import json
import gc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'backend'), str(ROOT/'tools'),
               r'D:\0.1_FACE_BOOK\fanpage-control-center-v2.0']
from autopilot.locks import CrossProcessFileLock
from backend import channel_manager, sub_processor
from backend.dub_accuracy import verify_or_repair
from tools.render_douyin_intake import prepare_voice_reference


def main():
    work = ROOT/'outputs/cute_voice_7453165172010650938'
    work.mkdir(exist_ok=True)
    status = work/'status.json'
    def save(value, **kw):
        status.write_text(json.dumps(dict(status=value, publish_permission='NONE', **kw),
                                    ensure_ascii=False, indent=2), encoding='utf-8')
    save('WAITING_SHARED_GPU_LOCK')
    try:
        with CrossProcessFileLock(Path(r'D:\0.1_FACE_BOOK\fanpage-control-center-v2.0\runtime/locks/gpu_renderer.lock'), timeout_seconds=7200):
            save('GENERATING_AUDIO_ONLY')
            _, cfg = channel_manager.get_channel_config('KENH_008_ChiDepDiCau')
            cfg = channel_manager.apply_job_preset(cfg, 'chidepdicau')
            profile = prepare_voice_reference(cfg['_voice_profile'], work)
            cfg['_voice_profile'] = profile
            original = ROOT/'outputs/audio_audit_7453165172010650938/original_chinese.srt'
            duration = max(s.end for s in sub_processor.parse_srt_to_segments(str(original)))
            srt = work/'translated_for_1.4x.srt'
            save('TRANSLATING_FOR_TIMELINE')
            segments = sub_processor.translate_srt_to_vietnamese_srt(str(original), str(srt),
                video_dur=duration, dubbing_speed=cfg['speed'])
            voice = work/'voice.wav'
            if voice.exists():
                raise RuntimeError('EXISTING_AUDIO_JOB_REQUIRES_RECONCILIATION')
            sub_processor._cached_transcriber = None
            gc.collect()
            import torch
            torch.cuda.empty_cache()
            sub_processor.generate_dubbed_audio(segments, str(voice), voice=cfg['voice'],
                speed=cfg['speed'], total_duration_sec=duration, voice_profile=profile)
            save('ASR_VERIFICATION_AND_REPAIR')
            approved = verify_or_repair(voice, srt, cfg, duration)
            save('PASSED_AUDIO_ONLY', approved_wav=approved,
                 report=str(work/'voice_accuracy/report.json'))
    except Exception as exc:
        save('FAILED_REQUIRES_REVIEW', error_type=type(exc).__name__,
             message=str(exc)[:1200])
        raise


if __name__ == '__main__':
    main()
