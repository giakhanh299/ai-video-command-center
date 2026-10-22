"""Optional LOCAL ASR check of spoken words; never substitutes ASR text for the script.
A word match does not establish speaker identity or naturalness. ASR can be wrong.
"""
from __future__ import annotations
import gc,json,re,unicodedata
from pathlib import Path
from .common import NeedsReview,atomic_json,sha256,digest
from .captions import cue_hash

def words(s):return re.findall(r'\w+',unicodedata.normalize('NFC',s).casefold(),flags=re.UNICODE)
def compare(expected,heard,max_wer=.35):
    a=words(expected);b=words(heard)
    if not a:raise NeedsReview('ASR_QC_EMPTY_EXPECTED_TEXT')
    if max(len(a),len(b))>5000:raise NeedsReview('ASR_QC_TEXT_TOO_LONG: review in smaller segments')
    previous=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        row=[i]
        for j,y in enumerate(b,1):row.append(min(row[j-1]+1,previous[j]+1,previous[j-1]+(x!=y)))
        previous=row
    wer=previous[-1]/len(a)
    return {'word_error_rate':wer,'expected_words':len(a),'recognized_words':len(b),'matched':wer<=max_wer,
            'possible_repetition_or_extra_words':len(b)>len(a)*1.30,'expected':expected,'recognized':heard,
            'note':'ASR comparison only; not speaker verification and may require manual listening.'}

def verify(audio:Path,cues,cfg:dict,transcriber=None):
    config=cfg.get('speech_qc') or {}
    if not config.get('enabled',True):return {'status':'not_run','speaker_identity_verified':False}
    expected=' '.join(c.text for c in cues);threshold=float(config.get('max_wer',.35))
    if not 0<=threshold<=1:raise NeedsReview('ASR_QC_INVALID_THRESHOLD')
    signature=digest({'schema':7,'audio':sha256(audio),'cue_hash':cue_hash(cues),'config':config})
    path=audio.with_name(audio.stem+'_speech_qc.json')
    if transcriber is None and path.is_file():
        old=json.loads(path.read_text(encoding='utf-8'))
        if old.get('signature')==signature:
            if not old.get('matched'):raise NeedsReview('SPOKEN_TEXT_MISMATCH: listen and review saved speech QC report')
            return old
    model=None
    try:
        if transcriber is None:
            try:
                from faster_whisper import WhisperModel
                model=WhisperModel(config.get('model','small'),device=config.get('device','cpu'),
                                   compute_type=config.get('compute_type','int8'),local_files_only=bool(config.get('local_files_only',True)))
            except Exception as e:raise NeedsReview('ASR_QC_MODEL_UNAVAILABLE: prepare the local model; no pretend PASS. '+str(e)) from e
            transcriber=model.transcribe
        segments,info=transcriber(str(audio),language='vi',beam_size=5,vad_filter=True,condition_on_previous_text=False,word_timestamps=True)
        segments=list(segments);heard=' '.join(s.text.strip() for s in segments)
        result=compare(expected,heard,threshold)
        result.update(schema=7,signature=signature,audio_sha256=sha256(audio),model=config.get('model','small'),
                      speaker_identity_verified=False,status='matched' if result['matched'] else 'needs_review',
                      segments=[{'start':s.start,'end':s.end,'text':s.text} for s in segments])
        atomic_json(path,result)
    finally:
        if model is not None:del model;gc.collect()
    if not result['matched']:raise NeedsReview(f'SPOKEN_TEXT_MISMATCH: WER={result["word_error_rate"]:.3f}; expected/recognized saved; never alter original script automatically')
    return result
