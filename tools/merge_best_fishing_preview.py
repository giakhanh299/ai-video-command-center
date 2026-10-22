"""User-requested review preview using the disclosed 94.92% audio take.

The exception is this preview only. Future production ASR thresholds stay unchanged.
"""
import sys,json,time,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),r'D:\0.1_FACE_BOOK\fanpage-control-center-v2.0']
from autopilot.locks import CrossProcessFileLock
from dialogue_replace import prepare_dialogue_replacement,final_mix_hard_replace

WORK=ROOT/'outputs/fishing_preview_7453165172010650938'
VIDEO=Path(r'D:\0.1_FACE_BOOK\videos_upload\KENH_008_ChiDepDiCau\02_MOI_RENDER_CHO_XAC_NHAN\xin_com_nha_chu_cau_ca__7453165172010650938.mp4')
TAKE=ROOT/'outputs/cute_voice_7453165172010650938_superseded_20261021_091034/voice_accuracy/attempt_1.mp3'
OUT=WORK/'chi_dep_di_cau_giong_cute_nen50_preview.mp4'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def state(status,**kw):
    WORK.mkdir(exist_ok=True)
    (WORK/'status.json').write_text(json.dumps(dict(status=status,updated=time.time(),
        publish_permission='NONE',**kw),ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    state('WAITING_GPU')
    with CrossProcessFileLock(Path(r'D:\0.1_FACE_BOOK\fanpage-control-center-v2.0\runtime/locks/gpu_renderer.lock'),timeout_seconds=7200):
        if OUT.exists():raise RuntimeError('PREVIEW_ALREADY_EXISTS_CHECK_FIRST')
        source_hash,take_hash=sha(VIDEO),sha(TAKE)
        state('SEPARATING_BACKGROUND')
        stems=prepare_dialogue_replacement(str(VIDEO),cache_root=str(WORK/'stems'),require_cuda=True)
        state('MUXING_PREVIEW')
        temp=WORK/'preview.partial.mp4'
        final_mix_hard_replace(str(VIDEO),stems['instrumental'],str(TAKE),str(temp),instrumental_volume=0.5)
        ffprobe=str(ROOT/'tools/bin/ffprobe.exe')
        durations=[]
        for p in [VIDEO,temp]:
            result=subprocess.run([ffprobe,'-v','error','-show_entries','format=duration:stream=codec_type','-of','json',str(p)],capture_output=True,check=True)
            data=json.loads(result.stdout)
            if p==temp and {'audio','video'}-{s['codec_type'] for s in data['streams']}:raise RuntimeError('MISSING_STREAM')
            durations.append(float(data['format']['duration']))
        if abs(durations[0]-durations[1])>.15:raise RuntimeError('DURATION_MISMATCH')
        if sha(VIDEO)!=source_hash or sha(TAKE)!=take_hash:raise RuntimeError('SOURCE_CHANGED')
        temp.rename(OUT)
        state('COMPLETED_PREVIEW',path=str(OUT),duration=durations[1],output_sha256=sha(OUT),
            source_sha256=source_hash,mp3_sha256=take_hash,background_volume=0.5,
            measured_word_accuracy=0.9492168960607499,production_gate_passed=False,
            note='User requested combining the disclosed best take for review; this is not a >95% production approval.')

if __name__=='__main__':
    try:main()
    except Exception as e:
        state('FAILED',error_type=type(e).__name__)
        raise
