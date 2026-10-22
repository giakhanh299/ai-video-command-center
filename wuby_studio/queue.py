from __future__ import annotations
import contextlib,json,re,sqlite3,time,uuid
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from .common import ConfigError,digest

ACTIVE=('pending','running','retry')
ALLOWED_HOSTS=('youtube.com','youtu.be','tiktok.com','douyin.com','ixigua.com','bilibili.com','b23.tv','drive.google.com')

def canonical_url(value:str)->str:
    value=value.strip()
    if value.startswith('upload:'):
        name=value[7:]
        if not re.fullmatch(r'[a-f0-9]{32}\.(mp4|mov|mkv|webm)',name):raise ConfigError('Invalid uploaded video id')
        return value
    u=urlsplit(value)
    host=(u.hostname or '').lower().rstrip('.')
    if u.scheme not in ('https','http') or u.username or u.password or u.port not in (None,80,443):raise ConfigError('Only public http(s) video links')
    if not any(host==h or host.endswith('.'+h) for h in ALLOWED_HOSTS):raise ConfigError('Unsupported link host: '+host)
    if '/folders/' in u.path:raise ConfigError('A folder is not one video. Import file links, maximum 100.')
    q=[(k,v) for k,v in parse_qsl(u.query,keep_blank_values=True) if not k.startswith('utm_') and k not in ('usp','si','feature')]
    # Keep signatures/content parameters; do not destroy signed media URLs.
    return urlunsplit(('https',host,u.path or '/',urlencode(q),''))

def parse_links(text:str)->list[str]:
    raw=re.findall(r'https?://[^\s<>"\x27]+|upload:[a-f0-9]{32}\.(?:mp4|mov|mkv|webm)',text)
    if not raw and text.strip():raise ConfigError('No supported video URL found')
    return [canonical_url(u.rstrip('.,;)')) for u in raw]

class Queue:
    def __init__(self,path:Path,max_active:int=100):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.max_active=min(100,max(1,int(max_active)))
        with self.db() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS jobs(
             id TEXT PRIMARY KEY,url TEXT NOT NULL,channel TEXT NOT NULL,signature TEXT NOT NULL,
             config TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,
             created REAL NOT NULL,updated REAL NOT NULL,worker TEXT,heartbeat REAL,error TEXT,
             output TEXT,cancel_requested INTEGER NOT NULL DEFAULT 0,
             UNIQUE(url,channel,signature));
            CREATE TABLE IF NOT EXISTS controls(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS queue_pending ON jobs(state,created);
            ''')
    @contextlib.contextmanager
    def db(self):
        c=sqlite3.connect(self.path,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA busy_timeout=30000')
        try:yield c
        finally:c.close()
    @contextlib.contextmanager
    def transaction(self):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            try:yield c;c.execute('COMMIT')
            except BaseException:c.execute('ROLLBACK');raise
    def add(self,links:list[str],config:dict)->dict:
        links=list(dict.fromkeys(canonical_url(u) for u in links))
        if not links:raise ConfigError('Empty batch')
        if len(links)>100:raise ConfigError('BATCH_LIMIT: maximum 100 unique links; nothing added')
        sig=digest(config);channel=str(config.get('channel_id','wuby'));now=time.time();inserted=[];duplicates=[]
        with self.transaction() as c:
            candidates=[]
            for url in links:
                row=c.execute('SELECT id FROM jobs WHERE url=? AND channel=? AND signature=?',(url,channel,sig)).fetchone()
                if row:duplicates.append(row['id'])
                else:candidates.append(url)
            current=c.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('pending','running','retry')").fetchone()[0]
            if current+len(candidates)>self.max_active:raise ConfigError(f'QUEUE_FULL: {current}+{len(candidates)} > {self.max_active}; nothing added')
            for batch_index,url in enumerate(candidates):
                jid=uuid.uuid4().hex
                c.execute('INSERT INTO jobs(id,url,channel,signature,config,created,updated) VALUES(?,?,?,?,?,?,?)',
                          (jid,url,channel,sig,json.dumps(config,ensure_ascii=False),now+batch_index*.00001,now));inserted.append(jid)
        return {'added':inserted,'duplicates':duplicates,'active_limit':self.max_active}
    def jobs(self,limit=200):
        with self.db() as c:return [dict(r) for r in c.execute('SELECT * FROM jobs ORDER BY created DESC LIMIT ?',(min(1000,int(limit)),))]
    def get(self,jid):
        with self.db() as c:
            r=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            if not r:raise ConfigError('Unknown job')
            return dict(r)
    def paused(self):
        with self.db() as c:
            r=c.execute("SELECT value FROM controls WHERE key='paused'").fetchone();return bool(r and r[0]=='1')
    def pause(self,value=True):
        with self.db() as c:c.execute("INSERT INTO controls VALUES('paused',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",('1' if value else '0',))
    def claim(self,worker):
        with self.transaction() as c:
            r=c.execute("SELECT value FROM controls WHERE key='paused'").fetchone()
            if r and r[0]=='1':return None
            if c.execute("SELECT 1 FROM jobs WHERE state='running' LIMIT 1").fetchone():return None
            r=c.execute("SELECT * FROM jobs WHERE state IN ('pending','retry') AND cancel_requested=0 ORDER BY created,id LIMIT 1").fetchone()
            if not r:return None
            now=time.time();c.execute("UPDATE jobs SET state='running',worker=?,attempts=attempts+1,updated=?,heartbeat=? WHERE id=?",(worker,now,now,r['id']))
            r=dict(r);r.update(state='running',worker=worker,attempts=r['attempts']+1);return r
    def beat(self,jid,worker):
        with self.db() as c:c.execute("UPDATE jobs SET heartbeat=? WHERE id=? AND worker=? AND state='running'",(time.time(),jid,worker))
    def finish(self,jid,worker,state,output=None,error=None):
        if state not in ('review','completed','needs_attention','failed','cancelled','retry'):raise ConfigError('Invalid terminal state')
        with self.db() as c:
            n=c.execute("UPDATE jobs SET state=?,updated=?,output=?,error=?,worker=NULL WHERE id=? AND worker=? AND state='running'",(state,time.time(),output,(error or '')[:4000],jid,worker)).rowcount
            if n!=1:raise ConfigError('STALE_WORKER: job is not owned by this worker')
    def cancel(self,jid):
        with self.transaction() as c:
            r=c.execute('SELECT state FROM jobs WHERE id=?',(jid,)).fetchone()
            if not r:raise ConfigError('Unknown job')
            if r[0]=='running':c.execute('UPDATE jobs SET cancel_requested=1 WHERE id=?',(jid,))
            elif r[0] in ('pending','retry','needs_attention'):c.execute("UPDATE jobs SET state='cancelled',updated=? WHERE id=?",(time.time(),jid))
    def retry(self,jid):
        with self.transaction() as c:
            if c.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('pending','running','retry')").fetchone()[0]>=self.max_active:raise ConfigError('QUEUE_FULL')
            n=c.execute("UPDATE jobs SET state='pending',cancel_requested=0,error=NULL,updated=? WHERE id=? AND state IN ('failed','needs_attention','cancelled')",(time.time(),jid)).rowcount
            if not n:raise ConfigError('Only failed/cancelled jobs can be retried')
    def recover(self,acknowledge_stopped=False):
        if not acknowledge_stopped:raise ConfigError('Stop orphan render/model processes first; then acknowledge recovery')
        with self.db() as c:
            return c.execute("UPDATE jobs SET state='needs_attention',worker=NULL,error='Interrupted process; retry manually',updated=? WHERE state='running'",(time.time(),)).rowcount
