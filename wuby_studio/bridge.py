"""Compatibility hook used by backend.video_merger, not a disconnected demo."""
from pathlib import Path
from .config import from_channel
from .captions import parse_srt
from .renderer import render
from .common import ROOT, NeedsReview

def render_legacy_call(input_video,output_video,srt_path,voice_audio,segments,movie_title,channel_cfg):
    cfg=from_channel(channel_cfg,ROOT)
    # Production Wuby renders must not leak source audio. When a cloned voice file is
    # provided, map only that voice track; source audio is never preserved/mixed here.
    cfg['fps']='12'
    cfg['crf']=28
    cfg.setdefault('audio',{})['bitrate']='96k'
    cfg['audio']['accept_legacy_clone']=True
    if voice_audio:
        cfg['audio']['mode']='clone'
        cfg['audio']['require_clone']=True
    else:
        cfg['audio']['mode']='silent'
    cues=segments or (parse_srt(Path(srt_path)) if srt_path else [])
    return render(input_video,output_video,cues,movie_title or '',cfg,voice_audio)
