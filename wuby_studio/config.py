from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from .common import ROOT, ConfigError, finite

DEFAULT = {
 'enabled': True, 'channel_id':'wuby', 'label':'WUBY / CUTE STORIES',
 'theme':'peach', 'width':1080, 'height':1920, 'fps':'12',
 'encoder':'libx264', 'crf':28, 'threads':2,
 'font_path':'', 'font_family':'DejaVu Sans',
 'title':{'enabled':True,'duration':3.0,'font_ratio':0.061,'max_lines':2},
 'subtitle':{'enabled':True,'font_ratio':0.047,'max_lines':2,'min_page_sec':0.45},
 'layout':{'title':[0.075,0.07,0.85,0.13], 'video':[0.045,0.23,0.91,0.52],
           'subtitle':[0.07,0.79,0.86,0.12], 'logo':[0.39,0.932,0.22,0.032]},
 'logo':{'enabled':True,'path':'channel_assets/wuby/logo.png','opacity':0.16,
         'mode':'drift_fade','cycle_sec':8.0,'drift_ratio':0.03},
 'motion':{'zoom':1.02},
 'cleanup':{'mode':'ocr','sample_fps':24.0,'crop':None,'masks':[],
            'input_already_rendered':False,'reviewed':False},
 'audio':{'mode':'clone','require_clone':True,'background_path':'',
          'background_gain':0.08,'normalize_voice':True,'max_speedup':1.65,
          'minimum_gap_sec':0.06,'bitrate':'96k','accept_legacy_clone':True,
          'keep_original_outside_subtitles':True,'mute_original_during_subtitles':True,
          'subtitle_mute_pad_sec':0.04},
 'speech_qc':{'enabled':True,'model':'large-v3','device':'cuda','compute_type':'float16','local_files_only':True,'max_wer':0.35},
 'sfx':{'enabled':False,'events':[],'avoid_speech':True,'max_gain':0.35},
 'quality':{'require_listening_approval':True,'require_visual_review':True},
 'source':{'mode':'auto','srt_path':'','voice_path':'','title':'','allow_music_transcription':False},
 'queue':{'max_active':100,'max_attempts':2,'timeout_sec':3600},
}
THEMES = {
 'peach': {'bg':'#FFF3EB','ink':'#49322F','accent':'#E98587','card':'#FFFCF8','soft':'#F7D9CE','muted':'#A88D85'},
 'mint': {'bg':'#EEF8F2','ink':'#243F39','accent':'#66A99B','card':'#FFFFFF','soft':'#CFE9DD','muted':'#78968B'},
 'lavender': {'bg':'#F4F0FC','ink':'#3D3457','accent':'#A087CD','card':'#FFFDFF','soft':'#E0D4F0','muted':'#9B8BAF'},
}

def merge(base: dict, override: dict | None) -> dict:
    out=deepcopy(base)
    for k,v in (override or {}).items():
        out[k] = merge(out[k], v) if isinstance(out.get(k),dict) and isinstance(v,dict) else deepcopy(v)
    return out

def validate(cfg: dict) -> dict:
    c=merge(DEFAULT,cfg)
    if c['theme'] not in THEMES: raise ConfigError('Unknown theme')
    for key in ('width','height'):
        n=int(c[key]); finite(n,160,3840,key)
        if n%2: raise ConfigError('Video dimensions must be even')
        c[key]=n
    if c['width'] >= c['height']: raise ConfigError('Wuby V7 templates require portrait output')
    finite(c['logo']['opacity'],0,1,'logo.opacity')
    finite(c['logo']['drift_ratio'],0,0.1,'logo.drift_ratio')
    finite(c['logo']['cycle_sec'],1,300,'logo.cycle_sec')
    finite(c['motion']['zoom'],1,1.08,'motion.zoom')
    if c['encoder'] not in ('libx264','h264_nvenc'): raise ConfigError('Invalid encoder')
    if c['cleanup']['mode'] not in ('none','manual','ocr'): raise ConfigError('Invalid cleanup mode')
    if c['audio']['mode'] not in ('clone','preserve','silent'): raise ConfigError('Invalid audio mode')
    if c['audio']['mode']=='clone' and not c['audio']['require_clone']:
        raise ConfigError('Wuby clone mode cannot disable require_clone')
    for key,rect in c['layout'].items():
        if not isinstance(rect,list) or len(rect)!=4: raise ConfigError('Rectangle must be [x,y,w,h]')
        x,y,w,h=[finite(v,0,1,key) for v in rect]
        if w<=0 or h<=0 or x+w>1.000001 or y+h>1.000001: raise ConfigError('Rectangle outside canvas')
    rects=list(c['layout'].items())
    for i,(a,ra) in enumerate(rects):
        for b,rb in rects[i+1:]:
            if intersect(ra,rb): raise ConfigError(f'LAYOUT_COLLISION: {a} / {b}')
    for path in ['queue.max_active']:
        finite(c['queue']['max_active'],1,100,path)
    finite(c['audio']['max_speedup'],1,1.65,'audio.max_speedup')
    finite(c['subtitle']['font_ratio'],0.028,0.085,'subtitle.font_ratio')
    finite(c['title']['font_ratio'],.03,.10,'title.font_ratio')
    finite(c['title']['duration'],.25,120,'title.duration')
    finite(c['cleanup']['sample_fps'],1,60,'cleanup.sample_fps')
    finite(c['threads'],1,32,'threads')
    finite(c['crf'],0,40,'crf')
    finite(c['audio']['minimum_gap_sec'],0,.5,'audio.minimum_gap_sec')
    finite(c['audio'].get('subtitle_mute_pad_sec',0.04),0,.5,'audio.subtitle_mute_pad_sec')
    if str(c['audio'].get('bitrate','96k')).lower() not in ('64k','80k','96k','128k','160k','192k'):
        raise ConfigError('Invalid audio bitrate')
    finite(c['queue']['timeout_sec'],10,86400,'queue.timeout_sec')
    finite(c['queue']['max_attempts'],1,5,'queue.max_attempts')
    if c['logo']['mode'] not in ('static','drift_fade'):raise ConfigError('Unknown logo mode')
    if int(c['subtitle']['max_lines']) not in (1,2):raise ConfigError('Subtitles are limited to one or two lines')
    return c

def intersect(a,b):
    return min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0])+1e-6 and min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1])+1e-6

def from_channel(channel:dict, root:Path=ROOT) -> dict:
    c=merge(DEFAULT,channel.get('wuby_studio',{}))
    c['channel_id']=str(channel.get('_channel_key') or c['channel_id'])
    logo=(channel.get('render') or {}).get('logo') or {}
    assets=channel.get('_assets') or {}
    # Channel-local assets win; never borrow another channel's logo.
    if assets.get('logo_path') or channel.get('logo_path'):
        c['logo']['path']=assets.get('logo_path') or channel.get('logo_path')
    elif 'path' not in (channel.get('wuby_studio',{}).get('logo') or {}):
        from .common import inside
        channel_dir=inside(root/'channel_assets',c['channel_id'])
        c['logo']['path']=str(channel_dir/'logo.png')
    for k in ('opacity','enabled'):
        if k in logo and k not in (channel.get('wuby_studio',{}).get('logo') or {}): c['logo'][k]=logo[k]
    c['_root']=str(root)
    return validate(c)
