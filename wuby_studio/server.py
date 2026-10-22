"""Local-only Studio. Native Canvas 2D; no CDN, cloud renderer or paid SDK."""
from __future__ import annotations
import json,mimetypes,os,secrets,subprocess,sys,threading,time,uuid,webbrowser
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .common import ROOT,ConfigError,atomic_json,inside,sha256
from .config import validate
from .cli import queue_path,get_config,snapshot_config
from .queue import Queue,parse_links

class StudioServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address):
        super().__init__(address,Handler)
        self.token=secrets.token_urlsafe(32);self.worker=None;self.preview_lock=threading.Lock()
        self.preview_state={'state':'idle'};self.preview_dir=ROOT/'workspace/previews'
        self.preview_dir.mkdir(parents=True,exist_ok=True)

class Handler(BaseHTTPRequestHandler):
    server_version='WubyLocal/7'
    def log_message(self,*a):pass
    def safe_host(self):
        host=self.headers.get('Host','').split(':')[0].lower()
        if host not in ('127.0.0.1','localhost'):raise ConfigError('LOCALHOST_ONLY')
    def send(self,code,data,ctype='application/json; charset=utf-8'):
        raw=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode()
        self.send_response(code);self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(raw)));self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Frame-Options','DENY');self.end_headers();self.wfile.write(raw)
    def body(self,max_size=2_000_000):
        n=int(self.headers.get('Content-Length','0'))
        if n<0 or n>max_size:raise ConfigError('REQUEST_TOO_LARGE')
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ConfigError('JSON_REQUIRED')
        return json.loads(self.rfile.read(n))
    def stream_file(self,path):
        if not path.is_file():return self.send(404,{'error':'Not found'})
        size=path.stat().st_size;start=0;end=size-1;code=200
        rng=self.headers.get('Range','')
        if rng:
            import re
            m=re.fullmatch(r'bytes=(\d+)-(\d*)',rng)
            if not m:return self.send(416,{'error':'Invalid range'})
            start=int(m[1]);end=min(end,int(m[2])) if m[2] else end;code=206
            if start>end:return self.send(416,{'error':'Invalid range'})
        self.send_response(code);self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes')
        if code==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
        with path.open('rb') as f:
            f.seek(start);remain=end-start+1
            while remain:
                chunk=f.read(min(remain,256*1024))
                if not chunk:break
                self.wfile.write(chunk);remain-=len(chunk)
    def do_GET(self):
        try:
            self.safe_host();u=urlsplit(self.path);q=parse_qs(u.query)
            if u.path=='/':
                html=(ROOT/'wuby_studio/web/index.html').read_text(encoding='utf-8').replace('__TOKEN__',self.server.token)
                return self.send(200,html.encode(),'text/html; charset=utf-8')
            if u.path in ('/style.css','/app.js'):
                return self.stream_file(ROOT/'wuby_studio/web'/u.path[1:])
            if u.path=='/api/status':
                queue=Queue(queue_path());jobs=queue.jobs()
                for j in jobs:j.pop('config',None)
                return self.send(200,{'jobs':jobs,'paused':queue.paused(),
                     'worker_running':self.server.worker is not None and self.server.worker.poll() is None,
                     'preview':self.server.preview_state,'config':get_config()})
            if u.path=='/api/media':
                category=q.get('kind',[''])[0];name=q.get('name',[''])[0]
                roots={'preview':ROOT/'workspace/previews','upload':ROOT/'workspace/uploads','job':ROOT/'workspace/queue_jobs'}
                if category not in roots:raise ConfigError('Bad media category')
                p=inside(roots[category],name)
                if p.suffix.lower() not in ('.mp4','.png','.jpg','.jpeg','.wav'):raise ConfigError('Not a media file')
                return self.stream_file(p)
            if u.path=='/api/log':
                job=Queue(queue_path()).get(q.get('job',[''])[0]);p=inside(ROOT/'workspace/queue_jobs',job['id']+'/worker.log')
                return self.send(200,{'log':p.read_text(encoding='utf-8',errors='replace')[-18000:] if p.exists() else 'Not started'})
            return self.send(404,{'error':'Not found'})
        except Exception as e:return self.send(400,{'error':str(e)})
    def do_POST(self):
        try:
            self.safe_host()
            if not secrets.compare_digest(self.headers.get('X-Wuby-Token',''),self.server.token):return self.send(403,{'error':'CSRF_TOKEN_REQUIRED'})
            u=urlsplit(self.path)
            if u.path=='/api/upload':return self.upload(u)
            data=self.body();queue=Queue(queue_path())
            if u.path=='/api/settings':
                cfg=validate(data['config']);atomic_json(ROOT/'workspace/studio_settings.json',cfg)
                return self.send(200,{'saved':True})
            if u.path=='/api/enqueue':
                links=parse_links(data['links']);cfg=snapshot_config(data['config'],len(links))
                return self.send(200,queue.add(links,cfg))
            if u.path=='/api/control':
                action=data['action']
                if action=='pause':queue.pause(True)
                elif action=='resume':queue.pause(False)
                elif action=='cancel':queue.cancel(data['id'])
                elif action=='retry':queue.retry(data['id'])
                elif action=='start':
                    if self.server.worker is None or self.server.worker.poll() is not None:
                        logdir=ROOT/'workspace';logdir.mkdir(exist_ok=True)
                        with (logdir/'queue_worker.log').open('ab') as log:
                            self.server.worker=subprocess.Popen([sys.executable,'-m','wuby_studio.cli','worker'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                else:raise ConfigError('Unknown control action')
                return self.send(200,{'ok':True})
            if u.path=='/api/preview':return self.start_preview(data)
            return self.send(404,{'error':'Not found'})
        except Exception as e:return self.send(400,{'error':str(e)})
    def upload(self,u):
        from PIL import Image
        from .media import probe,snapshot
        kind=parse_qs(u.query).get('kind',[''])[0]
        if kind not in ('video','logo','srt'):raise ConfigError('Unsupported upload type')
        name=self.headers.get('X-Filename','file');ext=Path(name).suffix.lower()
        allowed={'video':('.mp4','.mov','.mkv','.webm'),'logo':('.png',),'srt':('.srt',)}
        if ext not in allowed[kind]:raise ConfigError('Invalid file extension')
        size=int(self.headers.get('Content-Length',0));limit=500*1024*1024 if kind=='video' else 5*1024*1024
        if not 0<size<=limit:raise ConfigError('UPLOAD_TOO_LARGE_OR_EMPTY')
        folder=ROOT/'workspace/uploads';folder.mkdir(parents=True,exist_ok=True);p=folder/(uuid.uuid4().hex+ext)
        try:
            with p.open('wb') as f:
                remaining=size
                while remaining:
                    block=self.rfile.read(min(1024*1024,remaining))
                    if not block:raise ConfigError('Incomplete upload')
                    f.write(block);remaining-=len(block)
            result={'path':str(p),'name':p.name}
            if kind=='video':
                m=probe(p)
                if not m['video']:raise ConfigError('No video stream')
                result.update(url='upload:'+p.name,duration=m['duration'],fps=m['video'].get('avg_frame_rate'))
                snapshot(p,p.with_suffix('.jpg'),min(.5,m['duration']/2));result['thumbnail']=p.with_suffix('.jpg').name
            elif kind=='logo':
                with Image.open(p) as img:
                    if img.width>4096 or img.height>4096:raise ConfigError('Logo maximum 4096 pixels')
                    img.verify()
            elif kind=='srt':
                from .captions import parse_srt
                result['cue_count']=len(parse_srt(p))
            self.send(200,result)
        except BaseException:p.unlink(missing_ok=True);raise
    def start_preview(self,data):
        # A real FFmpeg preview, not a screenshot passed off as a render.
        from .renderer import render,rerender
        from .captions import parse_srt
        cfg=validate(data['config']);name=data.get('upload','')
        source=inside(ROOT/'workspace/uploads',name)
        if not source.is_file() or source.suffix.lower() not in ('.mp4','.mov','.webm','.mkv'):raise ConfigError('Upload a local video for preview first')
        if cfg['audio']['mode']=='clone':raise ConfigError('Use clone queue + approved audition for new voices. Visual preview uses explicit preserve/silent mode; never substitutes a preset.')
        if not self.server.preview_lock.acquire(False):raise ConfigError('Preview already rendering')
        jid=uuid.uuid4().hex;output=self.server.preview_dir/(jid+'.mp4');srv=self.server
        srv.preview_state={'state':'running','id':jid}
        def task():
            try:
                cues=parse_srt(Path(cfg['source']['srt_path'])) if cfg['source']['srt_path'] else []
                render(source,output,cues,cfg['source']['title'],cfg)
                srv.preview_state={'state':'review','name':output.name,'id':jid,'note':'Existing audio, not a new clone test'}
            except Exception as e:srv.preview_state={'state':'failed','error':str(e),'id':jid}
            finally:srv.preview_lock.release()
        threading.Thread(target=task,daemon=True).start()
        return self.send(202,srv.preview_state)

def serve(port=8767,open_browser=True):
    srv=StudioServer(('127.0.0.1',port));url=f'http://127.0.0.1:{srv.server_address[1]}'
    print('Wuby Studio:',url,'\nLocal only. Closing this terminal stops Studio, not an independently launched queue worker.')
    if open_browser:webbrowser.open(url)
    try:srv.serve_forever()
    except KeyboardInterrupt:pass
    finally:srv.server_close()
