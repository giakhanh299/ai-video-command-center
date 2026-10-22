"""Read back sampled speech from the actual MP4, with offline ASR.

Text/timing evidence only: never claims speaker identity, emotion or publishing
approval. A low score is retained as NEEDS_AUDIO_REVIEW, not silently repaired.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'backend'),str(ROOT/'tools')]
from render_douyin_intake import FB, atomic, digest
from autopilot.locks import CrossProcessFileLock


def normalized(text):
    return re.sub(r'[^\w\s]','',text.lower()).split()


def inspect(video,srt,report_path,language='vi',device='cuda'):
    from sub_processor import parse_srt_to_segments
    from faster_whisper import WhisperModel
    import shutil
    video,srt,report_path=Path(video),Path(srt),Path(report_path)
    cues=parse_srt_to_segments(str(srt))
    usable=[c for c in cues if len(c.text.strip())>=8]
    if not usable:
        raise ValueError('NO_REFERENCE_SPEECH')
    selected=[usable[i] for i in sorted({0,len(usable)//2,len(usable)-1})]
    report_path.parent.mkdir(parents=True,exist_ok=True)
    model=WhisperModel('large-v3',device=device,
        compute_type='int8' if device=='cpu' else 'float16',cpu_threads=4,local_files_only=True)
    rows=[]
    for i,cue in enumerate(selected):
        start=max(0.,cue.start-.08);end=min(cue.end+.15,start+12.)
        sample=report_path.parent/(report_path.stem+f'_sample_{i}.wav')
        subprocess.run([shutil.which('ffmpeg'),'-y','-v','error','-ss',str(start),'-i',str(video),
                        '-t',str(end-start),'-vn','-ar','16000','-ac','1',str(sample)],check=True)
        segments,info=model.transcribe(str(sample),beam_size=5,condition_on_previous_text=False,vad_filter=False)
        actual=' '.join(s.text.strip() for s in segments)
        expected=cue.text
        score=SequenceMatcher(None,normalized(expected),normalized(actual),autojunk=False).ratio()
        rows.append(dict(start=start,end=end,expected=expected,actual_asr=actual,
                         detected_language=info.language,language_probability=info.language_probability,
                         token_similarity=round(score,4),sample_sha256=digest(sample),
                         result='MATCH_SAMPLED_TEXT' if score>=.65 and info.language==language else 'NEEDS_AUDIO_REVIEW'))
        print('AUDIO_SAMPLE',i,rows[-1]['result'],flush=True)
    result=dict(video=str(video),video_sha256=digest(video),reference_srt=str(srt),reference_sha256=digest(srt),
                samples=rows,status='SAMPLED_TEXT_MATCH' if all(r['result']=='MATCH_SAMPLED_TEXT' for r in rows) else 'NEEDS_AUDIO_REVIEW',
                asr_model='large-v3',asr_device=device,
                speaker_identity_verified=False,emotion_accepted=False,full_video_listening=False,publish_permission='NONE')
    atomic(report_path,result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--video',required=True);p.add_argument('--srt',required=True)
    p.add_argument('--report',required=True);p.add_argument('--language',default='vi')
    p.add_argument('--device',choices=['cuda','cpu'],default='cuda');a=p.parse_args()
    if a.device=='cpu':
        inspect(a.video,a.srt,a.report,a.language,a.device)
    else:
        with CrossProcessFileLock(FB/'runtime/locks/gpu_renderer.lock',timeout_seconds=0):
            inspect(a.video,a.srt,a.report,a.language,a.device)
