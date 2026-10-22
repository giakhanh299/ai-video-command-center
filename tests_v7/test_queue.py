import concurrent.futures,json
import pytest
from wuby_studio.queue import Queue,canonical_url,parse_links
from wuby_studio.common import ConfigError
from wuby_studio.worker import loop

def links(n,start=0):return [f'https://www.youtube.com/watch?v=clip{i}' for i in range(start,start+n)]
def test_hundred_fifo_persistent(tmp_path,cfg):
    q=Queue(tmp_path/'q.db');r=q.add(links(100),cfg)
    assert len(r['added'])==100
    q=Queue(q.path)
    seen=[]
    def handler(job,work):
        assert sum(x['state']=='running' for x in q.jobs())==1
        seen.append(job['url']);return {'state':'review','output':str(work/'not_a_render_placeholder')}
    result=loop(q,tmp_path,handler=handler)
    assert seen==links(100)
    assert len(result)==100 and all(j['state']=='review' and j['attempts']==1 for j in result)

def test_101_rejected_atomically(tmp_path,cfg):
    q=Queue(tmp_path/'q.db')
    with pytest.raises(ConfigError,match='BATCH_LIMIT'):q.add(links(101),cfg)
    assert not q.jobs()

def test_capacity_across_batches(tmp_path,cfg):
    q=Queue(tmp_path/'q.db');q.add(links(98),cfg)
    with pytest.raises(ConfigError,match='QUEUE_FULL'):q.add(links(3,98),cfg)
    assert len(q.jobs())==98

def test_idempotent_and_config_changes(tmp_path,cfg):
    q=Queue(tmp_path/'q.db');q.add(links(1),cfg)
    assert len(q.add([links(1)[0]+'&utm_source=x'],cfg)['duplicates'])==1
    cfg['theme']='mint';assert len(q.add(links(1),cfg)['added'])==1

def test_snapshot_immutable(tmp_path,cfg):
    q=Queue(tmp_path/'q.db');jid=q.add(links(1),cfg)['added'][0];cfg['theme']='mint'
    assert json.loads(q.get(jid)['config'])['theme']=='peach'

def test_concurrent_claim_one_owner(tmp_path,cfg):
    q=Queue(tmp_path/'q.db');q.add(links(5),cfg)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:r=list(pool.map(lambda i:q.claim(str(i)),range(8)))
    assert sum(x is not None for x in r)==1

def test_pause_resume_cancel_retry(tmp_path,cfg):
    q=Queue(tmp_path/'q.db');jid=q.add(links(1),cfg)['added'][0]
    q.pause();assert q.claim('a') is None;q.pause(False);q.cancel(jid);assert q.get(jid)['state']=='cancelled'
    q.retry(jid);j=q.claim('a');q.cancel(jid);assert q.get(jid)['cancel_requested']==1
    q.finish(jid,'a','cancelled');q.retry(jid);assert q.get(jid)['cancel_requested']==0

def test_stale_worker_and_recovery(tmp_path,cfg):
    q=Queue(tmp_path/'q.db');jid=q.add(links(1),cfg)['added'][0];q.claim('a')
    with pytest.raises(ConfigError,match='STALE_WORKER'):q.finish(jid,'b','completed')
    with pytest.raises(ConfigError):q.recover()
    assert q.recover(True)==1;assert q.get(jid)['state']=='needs_attention'

def test_transient_bounded_retry(tmp_path,cfg):
    q=Queue(tmp_path/'q.db');q.add(links(1),cfg)
    r=loop(q,tmp_path,handler=lambda j,w:{'state':'failed','transient':True,'error':'fake timeout'})
    assert r[0]['attempts']==2 and r[0]['state']=='failed'

def test_systemic_failure_pauses_next_jobs(tmp_path,cfg):
    q=Queue(tmp_path/'q.db');q.add(links(3),cfg)
    r=loop(q,tmp_path,handler=lambda j,w:{'state':'needs_attention','pause_queue':True})
    assert q.paused();assert sum(j['state']=='pending' for j in r)==2

@pytest.mark.parametrize('url',['file:///etc/passwd','http://127.0.0.1/x','https://youtube.com.attacker.example/x','https://user:password@youtube.com/x','https://drive.google.com/drive/folders/xxx','https://youtu.be:8888/x','upload:../../x.mp4'])
def test_unsafe_url_rejected(url):
    with pytest.raises((ConfigError,ValueError)):canonical_url(url)

def test_link_parser_and_upload():
    assert len(parse_links('https://youtu.be/a\nhttps://www.tiktok.com/@a/video/1'))==2
    assert canonical_url('upload:'+'a'*32+'.mp4').startswith('upload:')
