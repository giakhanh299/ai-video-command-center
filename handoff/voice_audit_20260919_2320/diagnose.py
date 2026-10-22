from pathlib import Path
import os,sys,json,subprocess,time,math
ROOT=Path(r'D:/0.1_FACE_BOOK/Lay video tiktok'); OUT=Path(__file__).resolve().parent
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'backend'),str(ROOT),str(ROOT/'OmniVoice')]
def deny(*a,**k): raise RuntimeError('HANDOFF_NETWORK_DISABLED')
import socket
_connect=socket.socket.connect
def guarded_connect(self,address):
 if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):return _connect(self,address)
 return deny()
socket.socket.connect=guarded_connect;socket.create_connection=deny

def metrics(p):
 import numpy as np
 probe=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)],capture_output=True,timeout=20)
 if probe.returncode:return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'decode':'invalid/empty'}
 info=json.loads(probe.stdout); streams=[{k:s.get(k) for k in ['index','codec_type','codec_name','sample_rate','channels','duration']} for s in info['streams']]
 r=subprocess.run(['ffmpeg','-v','error','-i',str(p),'-map','0:a:0','-vn','-ac','1','-ar','16000','-f','f32le','pipe:1'],capture_output=True,timeout=35)
 x=np.frombuffer(r.stdout,dtype='<f4'); d={'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'streams':streams,'format_duration':info.get('format',{}).get('duration')}
 if x.size:
  rms=float(np.sqrt(np.mean(x*x))); peak=float(np.max(np.abs(x))); frames=x[:len(x)//320*320].reshape(-1,320)
  d.update(duration_s=len(x)/16000,rms=rms,peak=peak,rms_dbfs=20*math.log10(max(rms,1e-12)),peak_dbfs=20*math.log10(max(peak,1e-12)),silent_frames_pct=float(np.mean(np.sqrt(np.mean(frames*frames,axis=1))<.001)*100),clip_pct=float(np.mean(np.abs(x)>=.995)*100))
 else:d['decode']='no audio decoded'
 return d

def child(mode):
 import numpy as np,soundfile as sf
 if mode=='unit':
  import unittest
  suite=unittest.TestSuite()
  for pattern in ['test_channel_profiles.py','test_film_bars.py','test_ocr_overlap.py']:
   suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'backend/tests'),pattern=pattern))
  result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())
 if mode in ['khanh_original','khanh_tuned','khanh_male','vieneu_original','omni_clone','omni_auto','omni_design']:
  ref=ROOT/'voice_samples'/({'khanh_tuned':'wuby_character_tuned.wav','khanh_male':'giongnamdanchuongtrinh.mp3'}.get(mode,'wuby_character_original.wav'))
  text=None
  for q in [ref.with_suffix('.txt'),ref.with_suffix('.ref.txt')]:
   if q.exists():text=q.read_text(encoding='utf-8-sig').strip();break
  if mode.startswith('omni'):
   from omnivoice_service import OmniVoiceService
   service=OmniVoiceService(model_name='kjanh/KhanhTTS-OmniVoice',local_files_only=True)
   service.synthesize('Trời ơi, chuyện gì đang xảy ra vậy?',OUT/(mode+'.wav'),{'mode':mode.split('_')[1],'ref_audio':str(ref),'ref_text':text,'num_step':16})
  else:
   from test_voice_clone import run_khanhtts_clone,run_vieneu_clone
   fn=run_vieneu_clone if mode.startswith('vieneu') else run_khanhtts_clone
   result=fn(str(ref),text,'Trời ơi, chuyện gì đang xảy ra vậy?',OUT/(mode+'.wav'),device='cuda:0')
   print(json.dumps(result,ensure_ascii=False))
  print(json.dumps(metrics(OUT/(mode+'.wav')),ensure_ascii=False));return
 if mode=='logic':
  import voice_router as vr,sub_processor as sp,audio_processor as ap,asyncio
  from unittest.mock import patch
  rows=[]
  def check(name,fn):
   try:fn();rows.append({'name':name,'status':'PASS'})
   except Exception as e:rows.append({'name':name,'status':'FAIL','error':str(e)})
  def quiet():
   f=OUT/'silence.wav';sf.write(f,np.zeros(24000),24000)
   try:vr._quality_check(f,'test',{})
   except vr.VoiceQualityError:return
   raise AssertionError('silence accepted')
  check('router rejects silent audio',quiet)
  def strict():
   try:vr._backend_candidates({'engine':'zerotts','require_clone':True})
   except vr.VoiceBackendError:return
   raise AssertionError('preset accepted')
  check('require_clone rejects preset',strict)
  def missing():
   try:sp.generate_dubbed_audio([sp.SubtitleSegment(start=0,end=1,text='Xin chào')],str(OUT/'missing.wav'),voice_profile={'engine':'omnivoice','require_clone':True,'ref_audio':str(OUT/'ABSENT.wav')},force=True)
   except (FileNotFoundError,RuntimeError):return
   raise AssertionError('missing ref accepted')
  check('missing reference fails closed',missing)
  async def fail(*a,**k):return None
  with patch.object(sp,'_render_tts_chunk',fail):
   p=sp.generate_dubbed_audio([sp.SubtitleSegment(start=0,end=1,text='Xin chào')],str(OUT/'preset_failed.wav'),voice_profile={'engine':'edge'},force=True,total_duration_sec=2)
   rows.append({'name':'all preset chunks fail','actual':metrics(Path(p)),'status':'BUG_REPRODUCED' if np.max(np.abs(sf.read(p)[0]))==0 else 'UNEXPECTED'})
  with patch.object(ap,'extract_audio'),patch.object(ap,'transcribe_audio',return_value=[{'start':0,'end':1,'text':'Xin chào'}]),patch.object(ap,'translate_text',side_effect=lambda x:x),patch.object(ap,'generate_tts',fail):
   ap.WORKSPACE_DIR=OUT
   asyncio.run(ap.process_audio_pipeline('not_used',str(OUT/'legacy_failed.wav'),'not_used'))
   rows.append({'name':'legacy all TTS fails','actual':metrics(OUT/'legacy_failed.wav'),'status':'BUG_REPRODUCED'})
  # Real ffmpeg default mixing versus explicit normalize=0, synthetic voice only.
  sr=24000;x=.2*np.sin(2*np.pi*440*np.arange(sr)/sr);sf.write(OUT/'tone.wav',x,sr);sf.write(OUT/'zero.wav',np.zeros(sr),sr)
  for norm in ['default','off']:
   filt='[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2'+('' if norm=='default' else ':normalize=0')
   subprocess.run(['ffmpeg','-y','-v','error','-i',str(OUT/'zero.wav'),'-i',str(OUT/'tone.wav'),'-filter_complex',filt,str(OUT/('mix_'+norm+'.wav'))],check=True,timeout=15)
   rows.append({'name':'mix_'+norm,'actual':metrics(OUT/('mix_'+norm+'.wav'))})
  (OUT/'logic.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(rows,ensure_ascii=False));return
if __name__=='__main__':
 if len(sys.argv)>1:child(sys.argv[1]);sys.exit()
 results=[]
 for mode in ['unit','logic','khanh_original','khanh_tuned','khanh_male','vieneu_original','omni_clone','omni_auto','omni_design']:
  started=time.time();log=OUT/(mode+'.log')
  with log.open('w',encoding='utf-8') as f:
   try:
    p=subprocess.run([sys.executable,'-B','-X','utf8',str(Path(__file__)),mode],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=110,env=os.environ.copy());status='PASS' if p.returncode==0 else 'FAILED';code=p.returncode
   except subprocess.TimeoutExpired:status='TIMEOUT';code=None
  results.append({'mode':mode,'status':status,'returncode':code,'seconds':round(time.time()-started,2)})
  (OUT/'runs.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print(mode,status,flush=True)
 files=list((ROOT/'voice_samples').glob('*.wav'))+list((ROOT/'voice_samples').glob('*.mp3'))
 files+=list((ROOT/'workspace').glob('*.wav'))+list((ROOT/'workspace').glob('test_audio*.mp4'))
 files += [ROOT/'workspace/ocr_overlap_20260919/full_after.mp4',ROOT/'workspace/ocr_overlap_20260919/audio_full_clean.mp4',ROOT/'workspace/wuby_v5_cloned_voice_demo.mp4']
 rows=[]
 for p in files:
  try:rows.append(metrics(p))
  except Exception as e:rows.append({'path':str(p.relative_to(ROOT)),'error':type(e).__name__})
 (OUT/'measurements.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 print('MEASURED',len(rows),flush=True)
