from __future__ import annotations
import json, math
from fractions import Fraction
from pathlib import Path
from .common import binary, run, ConfigError

def probe(path: str | Path) -> dict:
    data=json.loads(run([binary('ffprobe'),'-v','error','-show_streams','-show_format','-of','json',str(path)],timeout=60).stdout)
    v=next((s for s in data['streams'] if s['codec_type']=='video'),None)
    a=next((s for s in data['streams'] if s['codec_type']=='audio'),None)
    dur=float((v or {}).get('duration') or data.get('format',{}).get('duration') or 0)
    if not math.isfinite(dur) or dur<=0: raise ConfigError('Invalid media duration')
    return {'video':v,'audio':a,'duration':dur,'format':data.get('format',{})}

def frame_rate(meta:dict, requested='source') -> str:
    v=meta.get('video') or {}
    raw=(v.get('avg_frame_rate') or v.get('r_frame_rate') or '0/0') if requested=='source' else str(requested)
    try: f=Fraction(raw)
    except (ValueError,ZeroDivisionError): raise ConfigError(f'Invalid FPS: {raw}')
    if not 1 <= f <= 60: raise ConfigError(f'Unsupported FPS {f}; explicitly choose 24, 25, 30 or 60')
    # Retain fractional 24000/1001 or 30000/1001 rather than rounding.
    return str(f.numerator)+'/'+str(f.denominator)

def snapshot(path:Path, out:Path, t:float=0.0, width:int=540):
    out.parent.mkdir(parents=True,exist_ok=True)
    # Windows FFmpeg builds may reject MJPEG snapshots from limited-range H.264
    # unless the JPEG pixel format is made explicit.
    run([binary('ffmpeg'),'-y','-v','error','-ss',str(max(0,t)),'-i',str(path),'-frames:v','1','-vf',f'scale={width}:-2','-q:v','2','-pix_fmt','yuvj420p',str(out)],timeout=60)
