from __future__ import annotations
import json,os,signal,subprocess,sys,time,uuid
from pathlib import Path
from filelock import FileLock, Timeout
from .common import ROOT, atomic_json, NeedsReview
from .queue import Queue

def stop_process(p):
    if p.poll() is not None:return
    if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
    else:
        try:os.killpg(p.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    try:p.wait(timeout=8)
    except subprocess.TimeoutExpired:
        if os.name!='nt':
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        else:p.kill()
        p.wait(timeout=8)

def loop(queue:Queue,root:Path=ROOT,once=False,handler=None):
    owner=uuid.uuid4().hex
    with FileLock(str(queue.path.with_suffix('.worker.lock')),timeout=0):
        if any(j['state']=='running' for j in queue.jobs(1000)):
            raise NeedsReview('INTERRUPTED_JOB: stop orphan process, recover, retry; no new GPU worker started')
        while True:
            job=queue.claim(owner)
            if not job:break
            cfg=json.loads(job['config']);work=root/'workspace'/'queue_jobs'/job['id'];work.mkdir(parents=True,exist_ok=True)
            atomic_json(work/'job.json',job);result=None;p=None
            try:
                if handler is not None:
                    result=handler(job,work)
                else:
                    kw={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
                    with (work/'worker.log').open('wb') as log:
                        p=subprocess.Popen([sys.executable,'-m','wuby_studio.cli','_job','--job',str(work/'job.json')],cwd=root,stdout=log,stderr=subprocess.STDOUT,**kw)
                        start=time.monotonic()
                        while p.poll() is None:
                            if queue.get(job['id'])['cancel_requested']:
                                stop_process(p);result={'state':'cancelled','error':'Cancelled by user'};break
                            if time.monotonic()-start>float(cfg['queue']['timeout_sec']):
                                stop_process(p);result={'state':'failed','error':'JOB_TIMEOUT: process tree stopped'};break
                            queue.beat(job['id'],owner);time.sleep(.5)
                    rp=work/'result.json'
                    if result is None:result=json.loads(rp.read_text()) if rp.exists() else {'state':'failed','error':'Worker exited without result'}
                state=result.get('state','failed')
                if result.get('transient') and job['attempts']<int(cfg['queue']['max_attempts']):state='retry'
                queue.finish(job['id'],owner,state,result.get('output'),result.get('error'))
                if result.get('pause_queue'):queue.pause(True)
            except BaseException as e:
                if p:stop_process(p)
                queue.finish(job['id'],owner,'cancelled' if isinstance(e,KeyboardInterrupt) else 'failed',error=str(e))
                if isinstance(e,(KeyboardInterrupt,SystemExit)):raise
            if once:break
    return queue.jobs()
