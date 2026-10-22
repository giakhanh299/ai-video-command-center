from __future__ import annotations
from dataclasses import asdict
import copy,json,re,sys
from pathlib import Path
from .common import ROOT, ConfigError, NeedsReview, WubyError, atomic_json, inside, sha256
from .config import validate
from .captions import parse_srt, write_srt, validate as validate_cues
from .queue import canonical_url
from .media import probe
from .renderer import render
from .voice_pipeline import check_approval

def channel_profile(channel='wuby'):
    p=ROOT/'backend'
    if str(p) not in sys.path:sys.path.insert(0,str(p))
    from backend import channel_manager
    db=channel_manager.load_channels_config(force_reload=True)
    if channel not in db.get('presets',{}) and channel not in db.get('channels',{}):raise ConfigError('Unknown channel id: '+channel)
    key,cfg=channel_manager.get_channel_config(channel)
    profile=copy.deepcopy(cfg['_voice_profile']);profile['project_root']=str(ROOT)
    if cfg.get('workflow')!='wuby':raise ConfigError('This queue is for Wuby; film/book profiles must use their own worker')
    if not profile.get('require_clone') or profile.get('engine') not in ('router','omnivoice','khanh_omnivoice','khanhtts','vieneu'):
        raise ConfigError('WUBY_PROFILE_MUST_REQUIRE_CLONE')
    return profile,cfg

def download(url,work):
    url=canonical_url(url)
    if url.startswith('upload:'):return inside(ROOT/'workspace/uploads',url[7:])
    if 'drive.google.com' in url:
        from urllib.parse import urlsplit,parse_qs
        import gdown
        m=re.search(r'/d/([A-Za-z0-9_-]+)',url)
        fid=m.group(1) if m else (parse_qs(urlsplit(url).query).get('id') or [None])[0]
        if not fid:raise ConfigError('Direct Drive file link required')
        target=work/'download.mp4'
        res=gdown.download(id=fid,output=str(target),quiet=True)
        if not res:raise WubyError('DRIVE_DOWNLOAD_FAILED: grant your machine access or upload the file locally')
        return target
    import yt_dlp
    opts={'outtmpl':str(work/'source.%(ext)s'),'noplaylist':True,'max_downloads':1,
          'max_filesize':500*1024*1024,'socket_timeout':30,'retries':2,'quiet':True,
          'format':'bv*[height<=1920]+ba/b[height<=1920]/best','merge_output_format':'mp4',
          'restrictfilenames':True,'overwrites':False,'writethumbnail':False}
    import shutil
    if shutil.which('node'):opts['js_runtimes']={'node':{}}
    elif shutil.which('deno'):opts['js_runtimes']={'deno':{}}
    with yt_dlp.YoutubeDL(opts) as dl:
        info=dl.extract_info(url,download=True)
        if not info or info.get('_type')=='playlist':raise ConfigError('Playlist is not one video')
    matches=[p for p in work.glob('source.*') if p.suffix.lower() in ('.mp4','.mkv','.webm','.mov')]
    if len(matches)!=1:raise WubyError('DOWNLOADED_VIDEO_NOT_FOUND')
    return matches[0]

def execute(job_path:Path):
    job=json.loads(job_path.read_text(encoding='utf-8'));work=job_path.parent;cfg=validate(json.loads(job['config']))
    try:
        for asset,expected in cfg.get('_asset_hashes',{}).items():
            if not Path(asset).is_file() or sha256(Path(asset))!=expected:raise NeedsReview('QUEUED_ASSET_CHANGED: re-enqueue with reviewed settings')
        profile,channel=channel_profile(cfg['channel_id'])
        from backend import sub_processor,voice_router
        profile_snapshot=cfg.get('_voice_profile_snapshot')
        if profile_snapshot:
            profile=copy.deepcopy(profile_snapshot)
        # Check reference/approval BEFORE downloading 100 clips or consuming API budget.
        if cfg['audio']['mode']=='clone':
            ref=voice_router._reference_from_config(work/'source.srt',profile)
            voice_router._validate_reference(ref,profile)
            from .voice_pipeline import reference_fingerprint
            if cfg.get('_reference_fingerprint') and reference_fingerprint(ref)!=cfg['_reference_fingerprint']:raise NeedsReview('QUEUED_REFERENCE_CHANGED: audition again and re-enqueue')
            if cfg['quality']['require_listening_approval']:check_approval(profile,ref)
        source=download(job['url'],work)
        meta=probe(source)
        if meta['duration']>3600:raise NeedsReview('Input is longer than 1 hour; reject accidental live/playlist URL')
        existing=cfg['source'].get('srt_path')
        if existing:
            p=Path(existing);p=p if p.is_absolute() else ROOT/p;cues=parse_srt(p)
        elif cfg['audio']['mode']!='clone':
            cues=[]
        else:
            srt,segs=sub_processor.generate_vietnamese_subtitles(str(source),str(work/'translated.srt'),force=True)
            cues,_=validate_cues(segs,meta['duration'])
        cues,notes=validate_cues(cues,meta['duration'])
        atomic_json(work/'approved_input.json',{'cues':[asdict(c) for c in cues],'warnings':notes,'semantic_accuracy_verified':False})
        if any(n.get('characters_per_second',0)>40 for n in notes):
            raise NeedsReview('TRANSLATION_TOO_DENSE: review transcript/lyrics rather than force fast speech')
        title=cfg['source'].get('title') or channel.get('title') or ''
        if not title and cues:
            from .renderer import load_font, pixel_rect
            from .captions import wrap
            font,_=load_font(cfg,round(cfg['width']*cfg['title']['font_ratio']))
            width=pixel_rect(cfg,'title')[2]
            lines=wrap(cues[0].text,font,width)
            title=' '.join(lines[:2]) if len(lines)<=2 else ' '.join(lines[:1])
        audio=None
        if cfg['audio']['mode']=='clone':
            audio=work/'voice.wav'
            profile['duration_match']={'max_speedup':cfg['audio']['max_speedup'],'minimum_gap_sec':cfg['audio']['minimum_gap_sec']}
            sub_processor.generate_dubbed_audio(cues,str(audio),voice=channel['voice'],speed=profile.get('speed',1.0),
                                               total_duration_sec=meta['duration'],voice_profile=profile)
        cfg['_root']=str(ROOT)
        out=work/'output.mp4';render(source,out,cues,title,cfg,audio)
        result={'state':'review','output':str(out),'error':'Review video/translation/voice before publishing'}
    except Exception as e:
        message=f'{type(e).__name__}: {e}'
        pause=any(s in message for s in ('REFERENCE_AUDIO_MISSING','VOICE_LISTENING_APPROVAL_REQUIRED','NO_VIETNAMESE_FONT','REFERENCE_TRANSCRIPT_REQUIRED','QUEUED_REFERENCE_CHANGED','APPROVED_SAMPLE_MISSING_OR_CHANGED','ASR_QC_MODEL_UNAVAILABLE')) or isinstance(e,ModuleNotFoundError)
        transient=any(s in type(e).__name__ for s in ('ConnectionError','TimeoutError','ReadTimeout'))
        result={'state':'needs_attention' if isinstance(e,(NeedsReview,ConfigError)) or pause else 'failed',
                'error':message,'pause_queue':pause,'transient':transient}
    atomic_json(work/'result.json',result)
    return result
