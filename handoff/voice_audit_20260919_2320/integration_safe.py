import diagnose as d
import sys,json,time,subprocess
from pathlib import Path
if len(sys.argv)>1:
 name=sys.argv[1]; p=d.ROOT/'tests'/name
 source=p.read_text(encoding='utf-8')
 # Execute original test logic with output paths redirected to handoff only.
 for basename in ['test_wuby_clone_real.wav','test_pipeline_wuby_dubbed.wav','test_bad_ref.wav']:
  source=source.replace('workspace/'+basename,(d.OUT/basename).as_posix())
 exec(compile(source,str(p),'exec'),{'__name__':'__main__','__file__':str(p)})
else:
 rows=[]
 for name in ['test_wuby_real_model.py','test_sub_processor_wuby.py']:
  start=time.time()
  with (d.OUT/(name+'.log')).open('w',encoding='utf-8') as f:
   try:
    r=subprocess.run([sys.executable,'-B','-X','utf8',__file__,name],cwd=d.ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=110);status='PASS' if r.returncode==0 else 'FAILED'
   except subprocess.TimeoutExpired:status='TIMEOUT'
  rows.append({'test':name,'status':status,'seconds':round(time.time()-start,2),'output_redirected_only':True});print(name,status,flush=True)
 (d.OUT/'additional_results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
