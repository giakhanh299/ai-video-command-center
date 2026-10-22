"""Render verified Douyin downloads with the current per-channel backend.

One shared GPU lock, durable receipts, isolated jobs, and review-folder outputs.
This entrypoint never invokes Telegram, Sheets or any publisher.
"""
from __future__ import annotations
import argparse,copy,gc,hashlib,json,os,sqlite3,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FB=Path(r'D:\0.1_FACE_BOOK\fanpage-control-center-v2.0')
RUNTIME=ROOT/'outputs/douyin_intake'
WORK=ROOT/'workspace/douyin_render_jobs'
sys.path[:0]=[str(ROOT),str(ROOT/'backend'),str(FB),str(ROOT/'tools')]
from scan_followed_douyin import digest,probe
from autopilot.locks import CrossProcessFileLock
from douyin_failed_cleanup import cleanup_failed, remember_tree

def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,path)

def resolve_config(channel_root):
    from backend import channel_manager
    _,cfg=channel_manager.get_channel_config(channel_root)
    cfg=copy.deepcopy(cfg)
    # The project's technical standard requires OmniVoice with natural pitch.
    replacements={'nu_tre':'omni_nu_tre','hoaimy':'omni_nu_tre','nam_minh':'omni_nam_review'}
    if cfg.get('tts_enabled',True):
        cfg['voice']=replacements.get(cfg['voice'],cfg['voice'])
        cfg['_voice_profile']=channel_manager._resolve_voice_profile(cfg['voice'],channel_manager.load_channels_config(),cfg)
        cfg['_voice_profile'].update(require_clone=True,fallback_voice=None,allow_backend_switch=False,pitch='+0Hz')
        if cfg['_voice_profile'].get('engine')!='omnivoice':raise ValueError('OMNIVOICE_REQUIRED')
    return cfg

def prepare_voice_reference(profile,work):
    """Bind clone conditioning text to what is actually spoken in the sample.

    Configured ref_text is metadata, not proof that it matches the waveform.
    OmniVoice conditions on both audio and transcript, so stale ref_text can leak
    unrelated words into generated speech.  Transcribe each distinct reference
    sample once, cache by audio SHA256, and always bind the audio-derived text.
    """
    from backend import voice_router,sub_processor
    profile=copy.deepcopy(profile)
    ref=voice_router._reference_from_config(Path(work)/'translated.srt',profile)
    voice_router._validate_reference(ref,profile)
    if not profile.get('require_clone'):return profile
    audio=Path(ref.audio);audio_sha=digest(audio)
    cached=RUNTIME/'reference_transcripts'/(audio_sha+'_large-v3.json')
    record=json.loads(cached.read_text(encoding='utf-8')) if cached.is_file() else {}
    if record.get('audio_sha256')!=audio_sha or record.get('model')!='large-v3' or not record.get('text','').strip():
        segments=sub_processor.get_transcriber('large-v3').transcribe(str(audio))
        text=' '.join(s.text.strip() for s in segments if s.text.strip())
        if not text:raise ValueError('REFERENCE_TRANSCRIPT_REQUIRED_NO_SPEECH')
        if digest(audio)!=audio_sha:raise ValueError('REFERENCE_CHANGED_DURING_TRANSCRIPTION')
        record={'audio_sha256':audio_sha,'model':'large-v3','text':text}
        atomic(cached,record)
    # Explicitly bind both fields; never substitute configured metadata or the
    # target video script for what the reference audio actually says.
    profile['reference']={**(profile.get('reference') or {}),'audio':str(audio),'text':record['text']}
    profile['ref_audio']=str(audio);profile['ref_text']=record['text']
    profile['reference_transcript_source']='audio_asr_large-v3_sha256_bound'
    return profile

def render_one(job_path):
    job=json.loads(Path(job_path).read_text(encoding='utf-8'))
    source=Path(job['source']).resolve();work=Path(job['work']).resolve()
    if work.parent!=WORK.resolve() or source.parent.name!='01_CHUA_RENDER':raise ValueError('INVALID_JOB_PATH')
    if digest(source)!=job['input_sha256']:raise ValueError('INPUT_CHANGED')
    os.environ['PATH']=str(ROOT/'tools/bin')+os.pathsep+os.environ.get('PATH','')
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['WHISPER_MODEL']='large-v3'
    os.environ['WHISPER_DEVICE']='cuda';os.environ['WHISPER_COMPUTE_TYPE']='float16'
    os.environ['DOUYIN_VOICE_BATCH_SIZE']='4'
    os.environ['DOUYIN_OCR_BATCH_SIZE']='8'
    from backend import channel_manager,sub_processor,video_merger,wuby_preflight,render_storage
    from wuby_studio.hybrid import frame_finished_wuby
    cfg=job['config'];duration=probe(source)
    def stage(name,extra=None):
        atomic(work/'progress.json',{'stage':name,'detail':str(extra or '')[:160],'updated':time.time()})
        print(name,extra or '',flush=True)
    stage('ASR_TRANSLATION')
    srt=work/'translated.srt';voice=work/'voice.wav';segments=[]
    try:
        _,segments=sub_processor.generate_vietnamese_subtitles(str(source),str(srt),progress_callback=stage,
            dubbing_speed=cfg.get('speed') if cfg.get('synthesis_speed') else None)
    except RuntimeError as e:
        if 'NO_SPEECH_DETECTED' not in str(e):raise
        stage('NO_SPOKEN_DIALOGUE')
    # Release the ASR model before loading the local voice model on a 16GB GPU.
    sub_processor._cached_transcriber=None;gc.collect()
    import torch
    torch.cuda.empty_cache()
    title,slug=sub_processor.generate_movie_title(raw_title=job['source_title'],segments=segments)
    assignments=None;profile_map={};duration_match={}
    if cfg.get('workflow')=='wuby' and cfg.get('wuby_preflight',{}).get('enabled',True):
        stage('WUBY_PREFLIGHT')
        original=srt.with_suffix('.orig.srt')
        original_segments=sub_processor.parse_srt_to_segments(str(original)) if original.is_file() else []
        pre_cfg=cfg.get('wuby_preflight',{})
        preflight_path=work/'preflight.json';bound_path=work/'preflight_binding.json'
        binding={'input_sha256':job['input_sha256'],'config_sha256':job['config_sha256']}
        if preflight_path.is_file() and bound_path.is_file() and json.loads(bound_path.read_text(encoding='utf-8'))==binding:
            report=json.loads(preflight_path.read_text(encoding='utf-8'))
        else:
            report=wuby_preflight.analyze_wuby_preflight(video_path=str(source),source_segments=original_segments,
                target_segments=segments,srt_path=str(srt) if srt.is_file() else None,movie_title=title,
                config_data=channel_manager.load_channels_config(),cfg=pre_cfg,report_path=str(preflight_path))
            atomic(bound_path,binding)
        plan=report.get('render_plan',{})
        cfg['_wuby_preflight']={'ocr_events':report.get('ocr',{}).get('events',[]),
            'scene_ranges':report.get('scenes',{}).get('ranges',[]),'render_plan':plan,
            'ocr_matched':True,'report_path':str(work/'preflight.json')}
        cfg['ocr_fps']=float(plan.get('ocr_sample_fps') or cfg.get('ocr_fps',24))
        if not plan.get('hybrid_frame_allowed',True):cfg.setdefault('wuby_studio',{}).setdefault('hybrid_frame',{})['enabled']=False
        assignments=((report.get('voice') or {}).get('match') or {}).get('target_assignments') or None
        if assignments:
            for key in {a['profile'] for a in assignments if a.get('profile')}:
                profile_map[key]=channel_manager._resolve_voice_profile(key,channel_manager.load_channels_config(),cfg)
                profile_map[key].update(require_clone=True,fallback_voice=None,allow_backend_switch=False,pitch='+0Hz')
                if profile_map[key].get('engine')!='omnivoice':raise ValueError('OMNIVOICE_REQUIRED')
            duration_match=pre_cfg.get('voice_match',{}).get('duration_match',{})
    tts=cfg.get('tts_enabled',True) and bool(segments)
    if tts:
        cfg['_voice_profile']=prepare_voice_reference(cfg['_voice_profile'],work)
        profile_map={key:prepare_voice_reference(profile,work) for key,profile in profile_map.items()}
        sub_processor._cached_transcriber=None;gc.collect();torch.cuda.empty_cache()
        stage('OMNIVOICE_TTS',len(segments))
        if assignments:
            sub_processor.generate_dubbed_audio_multivoice(segments,assignments,str(voice),profile_map,
                speed=cfg.get('speed',1),total_duration_sec=duration,duration_match=duration_match,progress_callback=stage)
            from backend.render_review_policy import validate_voice_assignments
            validate_voice_assignments(assignments,json.loads(voice.with_suffix('.multivoice.json').read_text(encoding='utf-8')))
        else:
            sub_processor.generate_dubbed_audio(segments,str(voice),voice=cfg['voice'],speed=cfg.get('speed',1),
                total_duration_sec=duration,voice_profile=cfg['_voice_profile'],progress_callback=stage)
    stage('RENDER')
    output=work/'output.mp4'
    video_merger.process_video_sub_and_mute(input_video=str(source),output_video=str(output),
        srt_path=str(srt) if srt.is_file() and cfg.get('burn_sub',True) else None,
        voice_audio=str(voice) if tts else None,keep_bg_audio=cfg.get('keep_bg_audio',False) if tts else True,
        bg_volume=float(cfg.get('bg_volume',.1)) if tts else 1.0,
        blur_sub=cfg.get('mask_mode') in ['blur','black_bar','blur_sub_black'],use_nvenc=True,
        segments=segments,movie_title=title if cfg.get('show_title_card',True) or cfg.get('mask_mode')=='in_video_overlay' else None,
        mask_mode=cfg.get('mask_mode','black_bar'),channel_cfg=cfg)
    finished=Path(frame_finished_wuby(output,title,cfg))
    actual_duration=probe(finished)
    if abs(duration-actual_duration)>max(.75,duration*.02):raise ValueError('DURATION_MISMATCH')
    if digest(source)!=job['input_sha256']:raise ValueError('INPUT_CHANGED_DURING_RENDER')
    stage('DELIVER_REVIEW')
    from backend.render_review_policy import review_filename, require_channel_destination
    destination=render_storage.review_directory(Path(r'D:\0.1_FACE_BOOK\videos_upload'),cfg['drive_folder'])
    channel_roots={c['channel_id']:c['workspace_root'] for c in json.loads((FB/'config/channels.json').read_text(encoding='utf-8-sig'))}
    require_channel_destination(job['channel'],destination,channel_roots)
    # Subtitles are burned into the video. Keep the editable SRT in the job only.
    final=render_storage.save_to_review(finished,destination,review_filename(title,job['id']))
    receipt={'status':'RENDERED_PENDING_REVIEW','id':job['id'],'channel':job['channel'],
        'input_sha256':job['input_sha256'],'config_sha256':job['config_sha256'],'output_sha256':digest(final),
        'path':str(final),'duration':actual_duration,'title':title,'source_url':'https://www.douyin.com/video/'+job['id'],
        'workflow':cfg['workflow'],'voice':cfg['voice'] if tts else 'ORIGINAL_AUDIO',
        'subtitle_count':len(segments),'publish_permission':'NONE','completed':time.time()}
    atomic(render_storage.render_receipt_path(final,for_write=True),receipt);atomic(work/'result.json',receipt);stage('COMPLETED')

def run(max_jobs=100,channel_filter=None,retry_failed=False):
    RUNTIME.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    report={'status':'RUNNING','started':time.time(),'completed':[],'failed':[],'skipped':[],'publish_permission':'NONE'}
    channels=json.loads((FB/'config/channels.json').read_text(encoding='utf-8-sig'))
    roots={c['channel_id']:Path(c['workspace_root']) for c in channels}
    with sqlite3.connect(RUNTIME/'history.sqlite') as intake:
        rows=intake.execute("SELECT id,channel,path,sha256 FROM items WHERE state='DOWNLOADED'").fetchall()
    grouped={}
    for vid,ch,path,sha in rows:
        if channel_filter and ch!=channel_filter:continue
        p=Path(path).resolve()
        if p.parent!=roots[ch].resolve()/'01_CHUA_RENDER':raise ValueError('CHANNEL_SOURCE_BINDING_INVALID')
        meta=json.loads(p.with_suffix('.douyin.json').read_text(encoding='utf-8'))
        grouped.setdefault(ch,[]).append((float(meta['duration']),vid,ch,str(p),sha,meta['title']))
    for group in grouped.values():group.sort()
    ordered=[]
    while any(grouped.values()):
        for ch in ['KENH_008','KENH_006','KENH_007','KENH_005','KENH_002','KENH_001','KENH_004','KENH_003']:
            if grouped.get(ch):ordered.append(grouped[ch].pop(0))
    with CrossProcessFileLock(FB/'runtime/locks/gpu_renderer.lock',timeout_seconds=0),sqlite3.connect(RUNTIME/'renders.sqlite') as db:
        db.execute('CREATE TABLE IF NOT EXISTS renders(id TEXT PRIMARY KEY,channel TEXT,input_sha TEXT,config_sha TEXT,state TEXT,pid INTEGER,path TEXT,error TEXT,updated REAL)')
        if 'attempts' not in {x[1] for x in db.execute('PRAGMA table_info(renders)')}:
            db.execute('ALTER TABLE renders ADD COLUMN attempts INTEGER DEFAULT 1')
        db.commit();attempted=0
        report['cleanup']=[cleanup_failed(db,WORK,p) for p in WORK.iterdir() if p.is_dir()]
        for duration,vid,ch,path,sha,title in ordered:
            cfg=resolve_config(roots[ch].name)
            config_sha=hashlib.sha256(json.dumps(cfg,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            prior=db.execute('SELECT state,path,input_sha,config_sha,attempts FROM renders WHERE id=?',(vid,)).fetchone()
            retry=bool(retry_failed and prior and prior[0]=='FAILED' and prior[2]==sha and prior[3]==config_sha and prior[4]<3)
            if (prior and not retry) or (retry_failed and not retry):
                report['skipped'].append({'id':vid,'channel':ch,'state':prior[0] if prior else 'NOT_FAILED'});continue
            if attempted>=max_jobs:break
            attempted+=1
            work=WORK/(ch+'_'+vid+'_'+config_sha[:12])
            if retry:
                # A partial/completed media artifact requires explicit reconciliation.
                if not work.is_dir() or list(work.glob('*.mp4')) or (work/'result.json').exists():
                    report['skipped'].append({'id':vid,'channel':ch,'state':'ARTIFACT_RECONCILIATION_REQUIRED'});continue
            else:work.mkdir(parents=True,exist_ok=False)
            job={'id':vid,'channel':ch,'source':path,'source_title':title,'input_sha256':sha,
                'config_sha256':config_sha,'config':cfg,'work':str(work)}
            atomic(work/'job.json',job)
            if retry:db.execute("UPDATE renders SET state='RUNNING',pid=?,error=NULL,updated=?,attempts=attempts+1 WHERE id=?",(os.getpid(),time.time(),vid))
            else:db.execute('INSERT INTO renders(id,channel,input_sha,config_sha,state,pid,path,error,updated) VALUES(?,?,?,?,?,?,?,?,?)',(vid,ch,sha,config_sha,'RUNNING',os.getpid(),None,None,time.time()))
            db.commit()
            report['current']={'id':vid,'channel':ch,'work':str(work)};atomic(RUNTIME/'render_report.json',report)
            print('RENDER_START',ch,vid,flush=True)
            evidence={'identities':{},'worker_observed':False,'worker_exited':False}
            try:
                with (work/'worker.log').open('ab') as log:
                    child=subprocess.Popen([sys.executable,'-X','utf8',str(Path(__file__).resolve()),'--job',str(work/'job.json')],
                        cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT)
                    try:
                        deadline=time.monotonic()+max(3600,duration*5)
                        while True:
                            if remember_tree(child,evidence['identities']):evidence['worker_observed']=True
                            atomic(work/'process_evidence.json',evidence)
                            try:
                                child.wait(timeout=min(1,max(.01,deadline-time.monotonic())))
                                evidence['worker_exited']=True
                                atomic(work/'process_evidence.json',evidence)
                                break
                            except subprocess.TimeoutExpired:
                                if time.monotonic()>=deadline:raise
                    except subprocess.TimeoutExpired:
                        from wuby_studio.worker import stop_process
                        stop_process(child)
                        evidence['worker_exited']=child.poll() is not None
                        atomic(work/'process_evidence.json',evidence)
                        raise
                if child.returncode or not (work/'result.json').is_file():raise RuntimeError('WORKER_FAILED')
                receipt=json.loads((work/'result.json').read_text(encoding='utf-8'))
                final=Path(receipt.get('path','')).resolve()
                if (receipt.get('status')!='RENDERED_PENDING_REVIEW' or receipt.get('id')!=vid
                        or receipt.get('channel')!=ch or receipt.get('config_sha256')!=config_sha
                        or receipt.get('publish_permission')!='NONE' or receipt.get('input_sha256')!=sha
                        or final.parent!=roots[ch].resolve()/'02_MOI_RENDER_CHO_XAC_NHAN'
                        or digest(path)!=sha or digest(final)!=receipt.get('output_sha256')
                        or probe(final)<=0):raise RuntimeError('RECEIPT_INVALID')
                db.execute("UPDATE renders SET state='COMPLETED',path=?,updated=? WHERE id=?",(receipt['path'],time.time(),vid));db.commit()
                report['completed'].append(receipt);print('RENDER_COMPLETED',ch,vid,flush=True)
            except Exception as e:
                code='WORKER_TIMEOUT' if isinstance(e,subprocess.TimeoutExpired) else 'WORKER_FAILED_REVIEW_LOG'
                db.execute("UPDATE renders SET state='FAILED',error=?,updated=? WHERE id=?",(code,time.time(),vid));db.commit()
                report['failed'].append({'id':vid,'channel':ch,'error':code,'work':str(work)})
                report['cleanup'].append(cleanup_failed(db,WORK,work))
                print('RENDER_FAILED',ch,vid,code,flush=True)
            atomic(RUNTIME/'render_report.json',report)
    report.pop('current',None);report.update(status='COMPLETED',finished=time.time());atomic(RUNTIME/'render_report.json',report)
    return report

def clean_failed_only():
    """Maintenance entrypoint: no downloads, retries, or GPU worker creation."""
    with CrossProcessFileLock(FB/'runtime/locks/gpu_renderer.lock',timeout_seconds=0):
        with sqlite3.connect('file:'+str(RUNTIME/'renders.sqlite')+'?mode=rw',uri=True) as db:
            reports=[cleanup_failed(db,WORK,p) for p in WORK.iterdir() if p.is_dir()]
            result={'status':'COMPLETED','deleted':[f for r in reports for f in r['deleted']],
                    'bytes':sum(r['bytes'] for r in reports),'jobs':reports}
            atomic(RUNTIME/'cleanup_report.json',result)
            return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job');p.add_argument('--cleanup-failed',action='store_true');p.add_argument('--max-jobs',type=int,default=100);p.add_argument('--channel');p.add_argument('--retry-failed',action='store_true');a=p.parse_args()
    if a.job:render_one(a.job)
    else:
        try:result=clean_failed_only() if a.cleanup_failed else run(a.max_jobs,a.channel,a.retry_failed)
        except TimeoutError:result={'status':'GPU_BUSY'}
        print(json.dumps(result,ensure_ascii=False,indent=2))
