from pathlib import Path
import re,json,ast,hashlib,zipfile,shutil,datetime
ROOT=Path(r'D:/0.1_FACE_BOOK/Lay video tiktok'); OUT=Path(__file__).resolve().parent; STAGE=OUT/'source_handoff'
if STAGE.exists():shutil.rmtree(STAGE)
STAGE.mkdir(parents=True,exist_ok=True)
# Read sensitive values only in memory for redaction; never emit or include originals.
known=set()
for p in [ROOT/'backend/.env',ROOT/'gdrive_token.json']:
 if not p.exists():continue
 text=p.read_text(encoding='utf-8-sig',errors='replace')
 if p.suffix=='.json':
  def collect(x):
   if isinstance(x,dict):
    for k,v in x.items():
     if re.search(r'token|secret|password|api.?key|credential|private.?key',k,re.I) and isinstance(v,str) and len(v)>7:known.add(v)
     else:collect(v)
   elif isinstance(x,list):
    for v in x:collect(v)
  collect(json.loads(text))
 else:
  for line in text.splitlines():
   if '=' in line:
    k,v=line.split('=',1);v=v.strip().strip('\"\'')
    if re.search(r'token|secret|password|api.?key|credential',k,re.I) and len(v)>7:known.add(v)
patterns=[r'\b\d{8,12}:[A-Za-z0-9_-]{30,}\b',r'\b(?:sk-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b',r'(?i)https?://[^\s/\"\']+:[^\s/@\"\']+@[^\s\"\']+',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
counts={}
def clean(s):
 for v in sorted(known,key=len,reverse=True):s=s.replace(v,'REDACTED')
 for pattern in patterns:s=re.sub(pattern,'REDACTED',s)
 # Hardcoded sensitive assignments; environment variable names stay intact.
 s=re.sub(r'(?im)(\b(?:[A-Z_]*(?:TOKEN|SECRET|PASSWORD|API_KEY|CREDENTIAL)[A-Z_]*)\s*=\s*)([\"\'])([^\r\n]*?)\2',lambda m:m[1]+m[2]+'REDACTED'+m[2],s)
 return s
sensitive=re.compile(r'token|secret|password|api.?key|credential|authorization|cookie|private.?key',re.I)
def sanitize(x):
 if isinstance(x,dict):return {k:('REDACTED' if sensitive.search(k) else sanitize(v)) for k,v in x.items()}
 if isinstance(x,list):return [sanitize(v) for v in x]
 if isinstance(x,str):return clean(x)
 return x
files=['backend/'+n+'.py' for n in ['audio_processor','omnivoice_service','voice_router','zerotts_voice','sub_processor','video_merger','channel_manager','wuby_config','wuby_ocr_overlay','asset_manager','film_bars','scene_detector']]
files+=['test_voice_clone.py','test_ab_voice_clone.py','inspect_voice_reference.py','check_voice_backends.py']
files += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'backend/tests').glob('test_*.py')]
files += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'tests').glob('test_*.py')]
# Bundle inference source only, not training/evaluation/models weights/dependencies.
files += [str(p.relative_to(ROOT)).replace('\\','/') for base in ['OmniVoice/omnivoice/models','OmniVoice/omnivoice/utils'] for p in (ROOT/base).glob('*.py')]
files += ['OmniVoice/omnivoice/__init__.py']
manifest=[]
for f in files:
 p=ROOT/f; original=p.read_text(encoding='utf-8-sig');text=clean(original);ast.parse(text)
 dst=STAGE/f;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(text,encoding='utf-8')
 manifest.append({'file':f,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sanitized':text!=original})
config=sanitize(json.loads((ROOT/'backend/channels_config.json').read_text(encoding='utf-8-sig')))
(STAGE/'backend/channels_config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ['diagnose.py','ISSUE_VI.md','measurements.json','logic.json','runs.json','additional_results.json']:
 p=OUT/name
 if p.exists():(STAGE/name).write_text(clean(p.read_text(encoding='utf-8')),encoding='utf-8')
(STAGE/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
# Every text file scanned after sanitization, including copied tests and Python.
scanned=[]
for p in STAGE.rglob('*'):
 if not p.is_file():continue
 text=p.read_text(encoding='utf-8')
 assert not any(v in text for v in known),(p.name,'known credential remains')
 assert not any(re.search(pat,text) for pat in patterns),(p.name,'secret pattern remains')
 if p.suffix=='.py':ast.parse(text)
 scanned.append(str(p.relative_to(STAGE)))
(STAGE/'SECURITY_SCAN.json').write_text(json.dumps({'all_text_files_scanned':scanned,'known_secret_and_pattern_hits_after_redaction':0,'recursive_config_sanitization':True,'excluded':['.env','credentials','tokens','logs','media','weights','dependencies','cache'],'note':'Automated scan plus narrow source allowlist; no original logs bundled.'},indent=2),encoding='utf-8')
# Scan the scan record too.
scantext=(STAGE/'SECURITY_SCAN.json').read_text();assert not any(v in scantext for v in known);assert not any(re.search(p,scantext) for p in patterns)
zpath=OUT/'voice_source_handoff_20260919_2320.zip'
if zpath.exists():zpath.unlink()
with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in sorted(STAGE.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(STAGE).as_posix())
with zipfile.ZipFile(zpath) as z:
 assert z.testzip() is None
 assert all('backend/'+x+'.py' in z.namelist() for x in ['audio_processor','omnivoice_service','voice_router','zerotts_voice','sub_processor','video_merger','channel_manager','wuby_config'])
 listing=[{'file':i.filename,'bytes':i.file_size,'compressed':i.compress_size} for i in z.infolist()]
assert zpath.stat().st_size<2000000
result={'path':str(zpath),'bytes':zpath.stat().st_size,'crc':'PASS','sha256':hashlib.sha256(zpath.read_bytes()).hexdigest(),'contents':listing}
(OUT/'ZIP_VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
copy=Path(r'C:\Users\w\.openclaw\workspace')/zpath.name
if copy.exists():copy.unlink()
shutil.copy2(zpath,copy);assert copy.read_bytes()==zpath.read_bytes()
print(json.dumps(result,ensure_ascii=False,indent=2))
