"""Bounded followed-author intake. No login cookies, rendering or publishing.

The scheduler calls this every six hours. Durable due checks and a process lock
also make duplicate invocations harmless. Only source timestamps decide age.
"""
from __future__ import annotations
import argparse,contextlib,datetime,hashlib,io,json,os,re,shutil,sqlite3,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FB=Path(r'D:\0.1_FACE_BOOK\fanpage-control-center-v2.0')
CONFIG=ROOT/'backend/douyin_sources.json'
RUNTIME=ROOT/'outputs/douyin_intake'
sys.path.insert(0,str(FB))
from autopilot.douyin_feed_provider import fetch_author_page
from autopilot.douyin_scanner import filter_lookback_72h
from autopilot.locks import CrossProcessFileLock

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def select_items(items,seen,now,limit,lookback=72):
    filtered=filter_lookback_72h(items,reference_time_epoch=now,lookback_hours=lookback)
    out=[];ids=set(seen)
    for item in sorted(filtered['eligible'],key=lambda i:i['timestamp_epoch'],reverse=True):
        identity=item.get('aweme_id')
        if not isinstance(identity,str) or not identity.isascii() or not identity.isdigit() or identity in ids:continue
        ids.add(identity);out.append(item)
        if len(out)>=limit:break
    return out,{'expired':len(filtered['expired']),'unverified_time':len(filtered['quarantined'])}

def probe(path):
    binary=ROOT/'tools/bin/ffprobe.exe'
    binary=str(binary) if binary.is_file() else shutil.which('ffprobe')
    if not binary:raise RuntimeError('MEDIA_PROBE_UNAVAILABLE')
    p=subprocess.run([binary,'-v','error','-show_entries','format=duration:stream=codec_type','-of','json',str(path)],capture_output=True,timeout=30,check=True)
    data=json.loads(p.stdout)
    duration=float(data.get('format',{}).get('duration',0))
    if not duration>0 or not any(s.get('codec_type')=='video' for s in data.get('streams',[])):raise RuntimeError('INVALID_VIDEO')
    return duration

def download_worker(identity,path):
    if not re.fullmatch(r'\d{15,24}',identity):raise ValueError('INVALID_VIDEO_ID')
    sys.path.insert(0,str(ROOT/'backend'))
    with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
        from downloader import TIKHUB_API_TOKEN
    import requests
    response=requests.get('https://api.tikhub.io/api/v1/douyin/web/fetch_one_video',
        headers={'Authorization':'Bearer '+TIKHUB_API_TOKEN},params={'aweme_id':identity},timeout=(10,25))
    response.raise_for_status()
    detail=response.json().get('data',{}).get('aweme_detail',{})
    if str(detail.get('aweme_id'))!=identity:raise RuntimeError('VIDEO_BINDING_MISMATCH')
    video=detail.get('video',{})
    address=video.get('play_addr_h264',{}) or video.get('play_addr',{}) or video.get('download_addr',{})
    urls=list(dict.fromkeys(address.get('url_list',[])))[:3]
    title=detail.get('desc','')
    for url in urls:
        if not isinstance(url,str) or not url.startswith(('https://','http://')):continue
        deadline=time.monotonic()+120
        try:
            with requests.get(url,headers={'Referer':'https://www.douyin.com/'},stream=True,timeout=(10,25)) as stream:
                stream.raise_for_status()
                with Path(path).open('wb') as output:
                    for chunk in stream.iter_content(1024*1024):
                        if time.monotonic()>deadline:raise TimeoutError('STREAM_DEADLINE')
                        if chunk:output.write(chunk)
            probe(path)
            break
        except (requests.RequestException,OSError,ValueError,RuntimeError,subprocess.SubprocessError):
            Path(path).unlink(missing_ok=True)
    else:raise RuntimeError('ALL_VIDEO_STREAMS_FAILED')
    print(json.dumps({'title':str(title or '')[:2000]},ensure_ascii=False))

def save_report(report):
    RUNTIME.mkdir(parents=True,exist_ok=True)
    temp=RUNTIME/'latest_report.json.tmp'
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temp,RUNTIME/'latest_report.json')

def run(channel_filter=None,metadata_only=False,retry_failed=False,force_once=False):
    cfg=json.loads(CONFIG.read_text(encoding='utf-8'))
    assert cfg['lookback_hours']==72 and cfg['interval_hours']==6 and cfg['max_new_per_channel']==3
    if not cfg.get('enabled'):return {'status':'DISABLED'}
    RUNTIME.mkdir(parents=True,exist_ok=True)
    now=time.time()
    report={'started_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(),'status':'RUNNING','lookback_hours':72,'max_new_per_channel':3,'scope':'FIRST_AUTHOR_PAGE_UP_TO_20_ITEMS_PER_SOURCE','downloaded':0,'channels':{},'publish_permission':'NONE'}
    fbcfg=json.loads((FB/'config/channels.json').read_text(encoding='utf-8-sig'))
    destinations={c['channel_id']:Path(c['workspace_root']) for c in fbcfg}
    allowed=Path(r'D:\0.1_FACE_BOOK\videos_upload').resolve()
    with CrossProcessFileLock(RUNTIME/'scan.lock',timeout_seconds=0),sqlite3.connect(RUNTIME/'history.sqlite') as db:
        db.execute('CREATE TABLE IF NOT EXISTS runs(channel TEXT PRIMARY KEY,last_scan REAL)')
        db.execute('CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY,channel TEXT,author TEXT,published REAL,state TEXT,path TEXT,sha256 TEXT,attempts INTEGER DEFAULT 0,error TEXT,updated REAL)')
        db.commit()
        for channel,spec in cfg['channels'].items():
            if channel_filter and channel!=channel_filter:continue
            result={'downloaded':[],'failed':[],'sources':[]}
            report['channels'][channel]=result
            if not spec.get('sources'):
                result['status']=spec.get('status','SOURCE_REQUIRED');continue
            destination=destinations[channel].resolve()
            if not destination.is_relative_to(allowed) or destination.parent!=allowed:raise ValueError('INVALID_CHANNEL_ROOT')
            inbox=destination/'01_CHUA_RENDER'
            retry_ids={r[0] for r in db.execute("SELECT id FROM items WHERE channel=? AND state='FAILED' AND attempts<3 AND published>=?",(channel,now-72*3600))}
            if retry_failed and not retry_ids:
                result['status']='NO_RECENT_FAILED_ITEMS';continue
            previous=db.execute('SELECT last_scan FROM runs WHERE channel=?',(channel,)).fetchone()
            if previous and now-previous[0]<cfg['interval_hours']*3600 and not metadata_only and not retry_failed and not force_once:
                result['status']='NOT_DUE';continue
            seen={r[0] for r in db.execute("SELECT id FROM items WHERE state IN ('DOWNLOADED','CLAIMED','UNCERTAIN','DUPLICATE_CONTENT') OR attempts>=3")}
            candidates=[]
            for source in spec['sources']:
                sid=source['sec_user_id']
                if not re.fullmatch(r'[A-Za-z0-9_.-]{10,256}',sid):raise ValueError('INVALID_AUTHOR')
                author={'id':channel+'_'+sid,'sec_user_id':sid,'verification_status':'AUTHOR_URL_RESOLVED_FEED_NOT_CONNECTED'}
                page=fetch_author_page(author)
                result['sources'].append({'name':source['name'],'url':'https://www.douyin.com/user/'+sid,'status':page['status']})
                if page['status']!='FETCHED_METADATA_PAGE':continue
                ignored=seen|({i['aweme_id'] for i in page['items'] if i.get('aweme_id') not in retry_ids} if retry_failed else set())
                selected,counts=select_items(page['items'],ignored,now,cfg['max_new_per_channel'],cfg['lookback_hours'])
                result['sources'][-1].update(counts)
                for item in selected:candidates.append({**item,'author_name':source['name']})
            candidates.sort(key=lambda i:i['timestamp_epoch'],reverse=True)
            candidates=candidates[:cfg['max_new_per_channel']]
            result['eligible_new']=len(candidates)
            if metadata_only:
                result['candidates']=[{'id':i['aweme_id'],'published':i['timestamp_epoch'],'url':'https://www.douyin.com/video/'+i['aweme_id']} for i in candidates]
                result['status']='METADATA_ONLY';continue
            inbox.mkdir(parents=True,exist_ok=True)
            for item in candidates:
                identity=item['aweme_id'];final=inbox/('douyin_'+identity+'.mp4');temp=inbox/'.downloads'/final.name
                if final.exists() or temp.exists():
                    result['failed'].append({'id':identity,'code':'EXISTING_FILE_NEEDS_RECONCILIATION'});continue
                temp.parent.mkdir(parents=True,exist_ok=True)
                db.execute("INSERT INTO items(id,channel,author,published,state,attempts,updated) VALUES(?,?,?,?,'CLAIMED',1,?) ON CONFLICT(id) DO UPDATE SET state='CLAIMED',attempts=attempts+1,updated=excluded.updated",(identity,channel,item['sec_user_id'],item['timestamp_epoch'],time.time()));db.commit()
                result['status']='DOWNLOADING';save_report(report)
                try:
                    child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--download-item',identity,'--output',str(temp)],capture_output=True,text=True,encoding='utf-8',timeout=480)
                    if child.returncode:raise RuntimeError('DOWNLOAD_ADAPTER_FAILED')
                    data=json.loads(child.stdout)
                    duration=probe(temp);sha=digest(temp)
                    duplicate=db.execute("SELECT id FROM items WHERE sha256=? AND state='DOWNLOADED'",(sha,)).fetchone()
                    if duplicate:
                        temp.unlink();db.execute("UPDATE items SET state='DUPLICATE_CONTENT',sha256=?,updated=? WHERE id=?",(sha,time.time(),identity));db.commit();continue
                    provenance={'id':identity,'channel':channel,'author':item['sec_user_id'],'author_name':item['author_name'],'source_url':'https://www.douyin.com/video/'+identity,'published_epoch':item['timestamp_epoch'],'downloaded_epoch':time.time(),'sha256':sha,'duration':duration,'title':data['title'],'publish_permission':'NONE'}
                    os.link(temp,final);temp.unlink()
                    final.with_suffix('.douyin.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
                    db.execute("UPDATE items SET state='DOWNLOADED',path=?,sha256=?,error=NULL,updated=? WHERE id=?",(str(final),sha,time.time(),identity));db.commit()
                    result['downloaded'].append({'id':identity,'path':str(final),'duration':round(duration,2),'title':data['title']});report['downloaded']+=1
                    print('DOWNLOADED '+channel+' '+identity,flush=True)
                except Exception as e:
                    code='DOWNLOAD_TIMEOUT' if isinstance(e,subprocess.TimeoutExpired) else 'DOWNLOAD_OR_VALIDATION_FAILED'
                    if temp.exists() and not final.exists():temp.unlink()
                    state='UNCERTAIN' if final.exists() else 'FAILED'
                    db.execute('UPDATE items SET state=?,error=?,updated=? WHERE id=?',(state,code,time.time(),identity));db.commit()
                    result['failed'].append({'id':identity,'code':code})
                save_report(report)
            result['status']='COMPLETED' if not result['failed'] else 'COMPLETED_WITH_ERRORS'
            if not any(s['status']=='FETCHED_METADATA_PAGE' for s in result['sources']):result['status']='PROVIDER_UNAVAILABLE'
            # An explicitly requested early intake does not move the six-hour schedule.
            if not retry_failed and not force_once:db.execute('INSERT OR REPLACE INTO runs VALUES(?,?)',(channel,time.time()))
            db.commit();save_report(report)
    report['status']='COMPLETED';report['finished_at']=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat();save_report(report)
    return report

def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('--channel');p.add_argument('--metadata-only',action='store_true');p.add_argument('--retry-failed',action='store_true');p.add_argument('--force-once',action='store_true',help='Scan now without postponing the normal six-hour schedule');p.add_argument('--download-item');p.add_argument('--output');a=p.parse_args()
    if a.download_item:
        try:download_worker(a.download_item,a.output)
        except Exception:print('DOWNLOAD_FAILED',file=sys.stderr);return 1
        return 0
    try:report=run(a.channel,a.metadata_only,a.retry_failed,a.force_once)
    except TimeoutError:report={'status':'BUSY_ANOTHER_SCAN'}
    print(json.dumps(report,ensure_ascii=False,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
