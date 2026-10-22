from __future__ import annotations
import json, math, os, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from .common import WubyError, NeedsReview, TimingError, binary, run, sha256, atomic_json
from .captions import validate, cue_hash

def waveform_quality(path:Path,min_rms_db=-60.0)->dict:
    x,sr=sf.read(str(path),dtype='float32',always_2d=True)
    if not len(x) or not np.isfinite(x).all():raise WubyError('AUDIO_EMPTY_OR_NONFINITE')
    peak=float(np.max(np.abs(x)));rms=float(np.sqrt(np.mean(x.astype(np.float64)**2)))
    rms_db=20*math.log10(max(rms,1e-12))
    if len(x)/sr<0.04 or peak<1e-5 or rms_db<min_rms_db: raise WubyError(f'AUDIO_SILENT_OR_TOO_QUIET: {rms_db:.1f}dBFS')
    if float(np.mean(np.abs(x)>=0.999))>.02:raise WubyError('AUDIO_SEVERELY_CLIPPED')
    return {'duration':len(x)/sr,'sample_rate':sr,'peak':peak,'rms_dbfs':rms_db,
            'clipped_fraction':float(np.mean(np.abs(x)>=0.999)),'sha256':sha256(path)}

def trim_silence_wav(input_path: Path, output_path: Path, threshold_ratio: float = 0.015, pad_sec: float = 0.02) -> Path:
    """Trims leading and trailing silence from generated audio chunk with smooth micro-fades."""
    try:
        x, sr = sf.read(str(input_path), dtype='float32', always_2d=True)
        if not len(x) or not np.isfinite(x).all():
            return input_path
        mono = x.mean(axis=1)
        peak = float(np.max(np.abs(mono)))
        if peak < 1e-5:
            return input_path
        thresh = max(peak * threshold_ratio, 1e-4)
        non_sil = np.where(np.abs(mono) > thresh)[0]
        if len(non_sil) == 0:
            return input_path
        pad_samples = int(pad_sec * sr)
        start_idx = max(0, non_sil[0] - pad_samples)
        end_idx = min(len(mono), non_sil[-1] + 1 + pad_samples)
        trimmed = x[start_idx:end_idx]
        fade_len = min(len(trimmed) // 2, int(0.005 * sr))
        if fade_len > 1:
            ramp = np.linspace(0, 1, fade_len, dtype=np.float32).reshape(-1, 1)
            trimmed[:fade_len] *= ramp
            trimmed[-fade_len:] *= ramp[::-1]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), trimmed, sr, subtype='PCM_16')
        return output_path
    except Exception:
        return input_path

def format_atempo_filter(factor: float) -> str:
    """Creates a chained atempo filter string for ffmpeg when factor > 2.0 or < 0.5."""
    filters = []
    curr = float(factor)
    while curr > 2.0:
        filters.append("atempo=2.0")
        curr /= 2.0
    while curr < 0.5:
        filters.append("atempo=0.5")
        curr /= 0.5
    filters.append(f"atempo={curr:.8f}")
    return ",".join(filters)

def align_track(cues, raw_paths:list[Path], output:Path, duration:float|None=None,
                max_speedup:float=1.65,gap_sec:float=.06,sample_rate:int=24000,
                adaptive:bool=False,base_tempo:float=1.0,max_early_start:float=0.0)->dict:
    if not math.isfinite(base_tempo) or base_tempo < 1.0 or base_tempo > max_speedup:
        raise TimingError('INVALID_BASE_TEMPO')
    cues,notes=validate(cues,duration)
    if len(cues)!=len(raw_paths) or not cues:raise WubyError('CUE_AUDIO_COUNT_MISMATCH')
    total=float(duration if duration is not None else max(c.end for c in cues))
    if not math.isfinite(total) or total>4*3600:raise WubyError('Invalid timeline duration')
    master=np.zeros(int(math.ceil(total*sample_rate)),dtype=np.float32);items=[];last_end=0
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='align_',dir=output.parent) as tmp:
        for i,(cue,p) in enumerate(zip(cues,raw_paths)):
            trimmed_p = Path(tmp)/f'trim_{i}.wav'
            active_p = trim_silence_wav(p, trimmed_p)
            q = waveform_quality(active_p)
            raw_q = waveform_quality(p)
            limit = min(total, cues[i+1].start-gap_sec) if i+1<len(cues) else total
            available = limit-cue.start
            if available<=0:
                if adaptive:
                    cue_start = max(last_end / sample_rate, 0.0)
                    available = max(0.2, limit - cue_start)
                else:
                    raise TimingError('NO_ROOM_FOR_DIALOGUE')
            else:
                cue_start = cue.start

            # Use only a small preceding silent gap; never overwrite the previous voice.
            if max_early_start > 0 and q['duration']/available > max_speedup:
                earliest = max(0.0, cue.start-max_early_start,
                               last_end/sample_rate + (gap_sec if i else 0.0))
                cue_start = max(earliest, min(cue.start, limit-q['duration']/base_tempo))
                available = limit-cue_start

            # Borrow silence, never another cue's reserved speech interval.
            factor = max(base_tempo, q['duration']/available)
            if factor>max_speedup+1e-6:
                if not adaptive:
                    raise TimingError(f'VOICE_TOO_LONG cue={i+1}: {q["duration"]:.3f}s into {available:.3f}s; '
                                      f'required={factor:.3f} > allowed={max_speedup:.3f}. Review translation; do not truncate or overlap.')
                effective_factor = min(2.5, factor * 1.012)
            else:
                effective_factor = (min(max_speedup, max(base_tempo, q['duration']/available * 1.012))
                                    if base_tempo > 1.0 else min(max_speedup, factor * 1.012))

            fitted = active_p
            if effective_factor>1.001:
                fitted = Path(tmp)/f'{i}.wav'
                af_filter = format_atempo_filter(effective_factor)
                run([binary('ffmpeg'),'-y','-v','error','-i',str(active_p),'-af',af_filter,
                     '-ar',str(sample_rate),'-ac','1',str(fitted)],timeout=180)
            x,sr=sf.read(str(fitted),dtype='float32',always_2d=True);x=x.mean(axis=1)
            if sr!=sample_rate:
                g=math.gcd(sr,sample_rate);x=resample_poly(x,sample_rate//g,sr//g).astype(np.float32)
            start=round(cue_start*sample_rate)
            if adaptive and start < last_end:
                start = last_end
            end=start+len(x)
            max_limit_sample = round(limit*sample_rate)
            if end>max_limit_sample:
                if not adaptive:
                    raise TimingError(f'FITTED_AUDIO_OVERFLOW cue={i+1}, end={end/sample_rate:.4f}, limit={limit:.4f}')
                keep_samples = max(int(0.1 * sample_rate), max_limit_sample - start)
                x = x[:keep_samples]
                end = start + len(x)
            if start<last_end:
                if not adaptive:
                    raise TimingError('VOICE_OVERLAP_DETECTED')
                start = last_end
                end = start + len(x)
            fade=min(len(x)//2,round(.005*sample_rate))
            if fade>1:
                ramp=np.linspace(0,1,fade,dtype=np.float32);x[:fade]*=ramp;x[-fade:]*=ramp[::-1]
            if end > len(master):
                if adaptive:
                    master = np.pad(master, (0, end - len(master)))
                else:
                    end = len(master)
                    x = x[:end-start]
            master[start:end]=x;last_end=end
            items.append({'cue':i+1,'text':cue.text,'speaker':cue.speaker,'start':cue_start,
                          'spoken_end':end/sample_rate,'reserved_end':limit,'atempo':effective_factor,'raw_sha256':raw_q['sha256']})
        peak=float(np.max(np.abs(master)))
        if peak>.97:master*=.97/peak
        temp=Path(tmp)/'final.wav';sf.write(str(temp),master,sample_rate,subtype='PCM_16')
        quality=waveform_quality(temp);os.replace(temp,output)
    return {'cues':items,'timeline_duration':total,'overlap_count':0,'truncated_cues':0,
            'pitch_preserving_time_stretch':True,'base_tempo':base_tempo,
            'cue_hash':cue_hash(cues),'quality':quality,'notes':notes}

def require_voice_report(audio:Path, cues, require_clone=True)->dict:
    path=audio.with_name(audio.stem+'_voice_report.json')
    if not path.exists():raise NeedsReview('VOICE_REPORT_MISSING: regenerate with V7; old WAV is not proof of cloning')
    report=json.loads(path.read_text(encoding='utf-8'))
    if report.get('schema')!=7 or report.get('output_sha256')!=sha256(audio):raise NeedsReview('VOICE_REPORT_STALE_OR_AUDIO_CHANGED')
    if report.get('cue_hash')!=cue_hash(cues):raise NeedsReview('VOICE_SCRIPT_CHANGED')
    if require_clone and not report.get('clone_conditioned'):raise NeedsReview('WRONG_VOICE_BACKEND_OR_REFERENCE')
    if report.get('overlap_count',1)!=0 or report.get('truncated_cues',1)!=0:raise NeedsReview('VOICE_TIMELINE_NOT_SAFE')
    waveform_quality(audio)
    return report
