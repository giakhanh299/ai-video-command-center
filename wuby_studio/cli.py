"""Standalone entrypoint for the backend-only Wuby handoff. No bot is assumed."""
from __future__ import annotations
import argparse,copy,importlib.util,json,os,sys,time
from pathlib import Path
from .common import ROOT,ConfigError,NeedsReview,atomic_json,sha256,binary,run
from .config import DEFAULT,validate,merge
from .queue import Queue,parse_links

def queue_path(): return ROOT/'workspace'/'wuby_queue.sqlite3'
def get_config(path=None):
    path=Path(path) if path else ROOT/'workspace/studio_settings.json'
    cfg=json.loads(path.read_text(encoding='utf-8')) if path.exists() else DEFAULT
    return validate(cfg)

def snapshot_config(cfg,link_count=1):
    from .job_runner import channel_profile
    from .voice_pipeline import reference_fingerprint
    from backend import voice_router
    cfg=validate(cfg);cfg['_root']=str(ROOT)
    if link_count>1 and cfg['source'].get('srt_path'):
        raise ConfigError('One SRT cannot be reused for different videos. Clear source.srt_path for a batch, or submit each prepared video separately.')
    if cfg['audio']['mode']=='clone':
        profile,_=channel_profile(cfg['channel_id'])
        ref=voice_router._reference_from_config(ROOT/'workspace/input.srt',profile)
        voice_router._validate_reference(ref,profile)
        cfg['_voice_profile_snapshot']=profile
        cfg['_reference_fingerprint']=reference_fingerprint(ref)
    cfg['_asset_hashes']={}
    for section,key in [('source','srt_path'),('logo','path'),('audio','background_path')]:
        value=cfg[section].get(key)
        if value:
            from .common import resolve
            p=resolve(value)
            if p.is_file():cfg['_asset_hashes'][str(p)]=sha256(p)
    return cfg

def doctor():
    from .renderer import load_font
    report={'python':sys.version,'root':str(ROOT),'checks':{},'clone_test':'NOT_RUN'}
    for name in ('ffmpeg','ffprobe'):
        try: report['checks'][name]={'ok':True,'path':binary(name)}
        except Exception as e: report['checks'][name]={'ok':False,'error':str(e)}
    for name in ('PIL','numpy','soundfile','scipy','filelock','yt_dlp','gdown','openai','cv2','faster_whisper','easyocr'):
        report['checks'][name]={'installed':importlib.util.find_spec(name) is not None}
    try:
        _,fp=load_font(DEFAULT,48);report['checks']['font']={'ok':True,'path':str(fp)}
    except Exception as e: report['checks']['font']={'ok':False,'error':str(e)}
    try:
        import torch
        report['checks']['torch']={'version':torch.__version__,'cuda_available':torch.cuda.is_available(),
                                   'device':torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}
    except Exception as e:report['checks']['torch']={'ok':False,'error':str(e)}
    try:
        from .job_runner import channel_profile
        from backend import voice_router
        p,c=channel_profile();ref=voice_router._reference_from_config(ROOT/'workspace/test.srt',p)
        voice_router._validate_reference(ref,p)
        report['checks']['wuby_reference']={'ok':True,'audio':str(ref.audio),'has_transcript':bool(ref.text),
                                           'note':'Existence/length do not prove correct transcript or identity'}
    except Exception as e:report['checks']['wuby_reference']={'ok':False,'error':str(e)}
    atomic_json(ROOT/'workspace/doctor.json',report);return report

def test_voice(channel,text=None):
    from .job_runner import channel_profile
    from .captions import Cue
    from .voice_pipeline import approval_key,reference_fingerprint
    from backend import sub_processor,voice_router
    profile,ch=channel_profile(channel)
    ref=voice_router._reference_from_config(ROOT/'workspace/test.srt',profile)
    voice_router._validate_reference(ref,profile)
    folder=ROOT/'workspace/voice_tests'/str(time.time_ns());folder.mkdir(parents=True)
    text=text or 'H\u00f4m nay em mu\u1ed1n k\u1ec3 cho anh nghe m\u1ed9t chuy\u1ec7n th\u1eadt d\u1ec5 th\u01b0\u01a1ng.'
    output=folder/'audition.wav'
    # Deliberately generous slot, no random changes to the selected voice/profile.
    cues=[Cue(0,15,text)]
    sub_processor.generate_dubbed_audio(cues,str(output),voice=ch['voice'],voice_profile=profile,total_duration_sec=15)
    manifest={'schema':7,'key':approval_key(profile,ref),'reference':reference_fingerprint(ref),
              'channel':channel,'sample':str(output),'sample_sha256':sha256(output),'text':text,
              'profile':profile,'listened':False,'speaker_identity_verified':False}
    atomic_json(folder/'audition.json',manifest)
    print('Listen to:',output,'\nCompare with:',ref.audio,'\nNo automatic claim of voice identity.')
    return manifest

def approve_voice(sample:Path,listened:bool):
    if not listened:raise NeedsReview('Use --listened only AFTER hearing the generated sample and comparing it with the reference.')
    from .job_runner import channel_profile
    from .voice_pipeline import approval_key
    from backend import voice_router
    sample=sample.resolve();data=json.loads(sample.with_suffix('.json').read_text(encoding='utf-8'))
    report=json.loads(sample.with_name(sample.stem+'_voice_report.json').read_text(encoding='utf-8'))
    p,_=channel_profile(data['channel']);ref=voice_router._reference_from_config(sample.with_suffix('.srt'),p)
    key=approval_key(p,ref)
    if data['key']!=key or data['sample_sha256']!=sha256(sample) or report.get('output_sha256')!=sha256(sample) or not report.get('clone_conditioned'):
        raise NeedsReview('Audition is stale, not clone-conditioned, or reference/profile changed. Test again.')
    result={'key':key,'listened':True,'sample':str(sample),'sample_sha256':sha256(sample),
            'approved_at':time.time(),'note':'User listened to one audition; not a guarantee for every future sentence.'}
    atomic_json(ROOT/'workspace/voice_approvals'/(key+'.json'),result);return result

def main(argv=None):
    ap=argparse.ArgumentParser(description='Wuby V7: strict clone, safe captions, local canvas, 100-link queue')
    sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    p=sub.add_parser('studio');p.add_argument('--port',type=int,default=8767);p.add_argument('--no-browser',action='store_true')
    p=sub.add_parser('test-voice');p.add_argument('--channel',default='wuby');p.add_argument('--text')
    p=sub.add_parser('approve-voice');p.add_argument('--sample',type=Path,required=True);p.add_argument('--listened',action='store_true')
    p=sub.add_parser('enqueue');p.add_argument('--file',type=Path);p.add_argument('--links');p.add_argument('--config',type=Path)
    p=sub.add_parser('worker');p.add_argument('--once',action='store_true')
    p=sub.add_parser('queue');p.add_argument('--limit',type=int,default=100)
    for name in ('pause','resume'):sub.add_parser(name)
    for name in ('cancel','retry'):p=sub.add_parser(name);p.add_argument('job_id')
    p=sub.add_parser('recover');p.add_argument('--processes-stopped',action='store_true')
    p=sub.add_parser('_job');p.add_argument('--job',type=Path,required=True)
    p=sub.add_parser('render');p.add_argument('--source',type=Path,required=True);p.add_argument('--srt',type=Path);p.add_argument('--config',type=Path);p.add_argument('--voice',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--title',default='')
    p=sub.add_parser('rerender');p.add_argument('--packet',type=Path,required=True);p.add_argument('--config',type=Path);p.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(argv)
    try:
        cmd=args.command
        if cmd=='doctor':result=doctor()
        elif cmd=='studio':
            from .server import serve
            return serve(args.port,not args.no_browser)
        elif cmd=='test-voice':result=test_voice(args.channel,args.text)
        elif cmd=='approve-voice':result=approve_voice(args.sample,args.listened)
        elif cmd=='enqueue':
            text=args.file.read_text(encoding='utf-8-sig') if args.file else args.links or ''
            links=parse_links(text);result=Queue(queue_path()).add(links,snapshot_config(get_config(args.config),len(links)))
        elif cmd=='worker':
            from .worker import loop
            result=loop(Queue(queue_path()),once=args.once)
        elif cmd=='queue':result=Queue(queue_path()).jobs(args.limit)
        elif cmd in ('pause','resume'):result=Queue(queue_path()).pause(cmd=='pause')
        elif cmd=='cancel':result=Queue(queue_path()).cancel(args.job_id)
        elif cmd=='retry':result=Queue(queue_path()).retry(args.job_id)
        elif cmd=='recover':result={'recovered':Queue(queue_path()).recover(args.processes_stopped)}
        elif cmd=='_job':
            from .job_runner import execute
            result=execute(args.job)
        elif cmd=='render':
            from .renderer import render
            from .captions import parse_srt
            result=render(args.source,args.output,parse_srt(args.srt) if args.srt else [],args.title,get_config(args.config),args.voice)
        elif cmd=='rerender':
            from .renderer import rerender
            result=rerender(args.packet,args.output,get_config(args.config) if args.config else None)
        print(json.dumps(result,ensure_ascii=False,indent=2,default=str));return 0
    except (Exception,KeyboardInterrupt) as e:
        print(f'{type(e).__name__}: {e}',file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
