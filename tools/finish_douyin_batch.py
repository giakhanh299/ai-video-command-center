"""Finish this bounded render batch and verify its real review artifacts."""
import argparse,json,sqlite3,subprocess,sys,time
from pathlib import Path
import psutil

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from render_douyin_intake import RUNTIME,atomic,digest,probe
from backend.render_storage import render_receipt_path

def finish(pid,created):
    watched={}
    while True:
        try:
            parent=psutil.Process(pid)
            if abs(parent.create_time()-created)>.01:break
            for child in parent.children(recursive=True):
                try:watched[child.pid]=child.create_time()
                except psutil.Error:pass
            if not parent.is_running():break
        except psutil.Error:break
        time.sleep(10)
    live=[]
    for child_pid,child_created in watched.items():
        try:
            p=psutil.Process(child_pid)
            if abs(p.create_time()-child_created)<.01 and p.is_running():live.append(child_pid)
        except psutil.Error:pass
    if live:
        atomic(RUNTIME/'batch_completion.json',{'status':'REQUIRES_PROCESS_RECONCILIATION','live_owned_children':live})
        return
    for attempt in range(2):
        with (RUNTIME/('recovery_'+str(attempt+1)+'.log')).open('wb') as log:
            child=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'tools/render_douyin_intake.py'),'--retry-failed'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            child.wait()
        with sqlite3.connect(RUNTIME/'renders.sqlite') as db:
            failed=db.execute("SELECT count(*) FROM renders WHERE state='FAILED'").fetchone()[0]
        if not failed:break
    rows=[];problems=[]
    with sqlite3.connect(RUNTIME/'renders.sqlite') as db:
        for vid,ch,state,path,error in db.execute('SELECT id,channel,state,path,error FROM renders ORDER BY channel,id'):
            if state!='COMPLETED':problems.append({'id':vid,'channel':ch,'state':state,'error':error});continue
            try:
                p=Path(path);receipt=json.loads(render_receipt_path(p).read_text(encoding='utf-8'))
                assert receipt['id']==vid and receipt['channel']==ch and receipt['output_sha256']==digest(p)
                assert receipt['publish_permission']=='NONE' and probe(p)>0
                rows.append({'id':vid,'channel':ch,'path':str(p),'title':receipt['title'],'duration':receipt['duration']})
            except Exception:problems.append({'id':vid,'channel':ch,'state':'OUTPUT_VERIFICATION_FAILED'})
    with sqlite3.connect(RUNTIME/'history.sqlite') as db:
        downloaded=db.execute("SELECT count(*) FROM items WHERE state='DOWNLOADED'").fetchone()[0]
    report={'status':'COMPLETED' if not problems and len(rows)==downloaded else 'COMPLETED_WITH_ERRORS',
        'downloaded':downloaded,'rendered_verified':len(rows),'channels_with_output':len({r['channel'] for r in rows}),
        'files':rows,'problems':problems,'publish_permission':'NONE','finished':time.time()}
    atomic(RUNTIME/'batch_completion.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True);a=p.parse_args()
    try:created=psutil.Process(a.pid).create_time()
    except psutil.Error:created=0
    finish(a.pid,created)
