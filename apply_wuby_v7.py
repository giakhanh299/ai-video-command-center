"""Transactional patch of the supplied backend handoff. Default is DRY RUN.
No installer can stop a model already running in another process: stop workers first.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,os,shutil,sys,tempfile,time
from pathlib import Path
BUNDLE=Path(__file__).resolve().parent
CONFIG='backend/channels_config.json'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

def safe(root,rel):
    p=(root/rel).resolve()
    if not p.is_relative_to(root.resolve()):raise RuntimeError('Path traversal in manifest')
    return p

def atomic_bytes(p,b):
    p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=p.name,suffix='.tmp',dir=p.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:Path(tmp).unlink(missing_ok=True)

def merged_config(raw):
    d=json.loads(raw.decode('utf-8-sig'))
    # Only Wuby opts into V7. Preserve keys, chat ids, references, TTS model/settings,
    # other channel workflows, logos and caller's existing render settings.
    for name,obj in d.get('presets',{}).items():
        if name=='wuby' or obj.get('workflow')=='wuby':
            visual=obj.setdefault('wuby_studio',{})
            visual.setdefault('enabled',True);visual.setdefault('channel_id',name)
    for name,obj in d.get('voice_profiles',{}).items():
        if name=='wuby_clone':
            obj['require_clone']=True;obj['allow_backend_switch']=False;obj['fallback_voice']=None
            obj.setdefault('duration_match',{'max_speedup':1.20,'minimum_gap_sec':.06})
    return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()

def plan(target:Path,bundle:Path=BUNDLE):
    target=target.resolve();bundle=bundle.resolve()
    if target==bundle or target.is_relative_to(bundle) or bundle.is_relative_to(target):
        raise RuntimeError('Extract patch OUTSIDE the live project. No nested source/target.')
    if not (target/'backend').is_dir():raise RuntimeError('Select PROJECT ROOT containing backend/, not backend itself')
    manifest=json.loads((bundle/'PATCH_MANIFEST_V7.json').read_text())
    changes=[];conflicts=[]
    for rel,item in manifest['files'].items():
        source=safe(bundle,rel);dest=safe(target,rel)
        if sha(source)!=item['new_sha256']:raise RuntimeError('Bundle changed after packaging: '+rel)
        old=sha(dest)
        if rel==CONFIG:
            if dest.is_file():content=merged_config(dest.read_bytes())
            else:conflicts.append(rel+' is missing; refusing to invent live configuration');continue
            if content!=dest.read_bytes():changes.append((rel,content))
        elif old==item['new_sha256']:continue
        elif old is None or old==item.get('base_sha256'):
            changes.append((rel,source.read_bytes()))
        else:conflicts.append(rel+' differs from the supplied handoff; merge manually with Anti')
    return changes,conflicts

def rollback(backup:Path,target:Path):
    record=json.loads((backup/'rollback.json').read_text())
    if Path(record['target']).resolve()!=target.resolve():raise RuntimeError('Rollback target mismatch')
    # Do not erase later work unknowingly.
    for item in record['files']:
        dest=safe(target,item['path'])
        if sha(dest)!=item['installed_sha256']:
            raise RuntimeError('File changed after patch; manual recovery needed: '+item['path'])
    for item in reversed(record['files']):
        dest=safe(target,item['path'])
        if item['existed']:atomic_bytes(dest,safe(backup/'originals',item['path']).read_bytes())
        else:dest.unlink(missing_ok=True)
    return len(record['files'])

def install(target:Path,bundle=BUNDLE,apply=False):
    changes,conflicts=plan(target,bundle)
    if conflicts:raise RuntimeError('CONFLICTS; no files written:\n'+'\n'.join(conflicts))
    result={'mode':'apply' if apply else 'dry_run','files':[r for r,_ in changes],'count':len(changes)}
    if not apply or not changes:return result
    backup=target/'backups'/('wuby_v7_'+str(time.time_ns()));backup.mkdir(parents=True)
    record={'target':str(target.resolve()),'files':[]}
    # Back up every byte BEFORE any replacement.
    for rel,content in changes:
        dest=safe(target,rel);existed=dest.is_file()
        if existed:atomic_bytes(safe(backup/'originals',rel),dest.read_bytes())
        record['files'].append({'path':rel,'existed':existed,'installed_sha256':hashlib.sha256(content).hexdigest()})
    atomic_bytes(backup/'rollback.json',json.dumps(record,indent=2).encode())
    applied=[]
    try:
        for rel,content in changes:atomic_bytes(safe(target,rel),content);applied.append(rel)
    except BaseException:
        for item in reversed(record['files']):
            if item['path'] not in applied:continue
            dest=safe(target,item['path'])
            if item['existed']:atomic_bytes(dest,safe(backup/'originals',item['path']).read_bytes())
            else:dest.unlink(missing_ok=True)
        raise
    result['backup']=str(backup);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--target',required=True,type=Path);p.add_argument('--apply',action='store_true');p.add_argument('--rollback',type=Path)
    a=p.parse_args()
    try:
        r=rollback(a.rollback,a.target) if a.rollback else install(a.target,apply=a.apply)
        print(json.dumps(r,ensure_ascii=False,indent=2));return 0
    except Exception as e:print(str(e),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
