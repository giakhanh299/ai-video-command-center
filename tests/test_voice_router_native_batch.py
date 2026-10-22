import sys
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0,str(Path(__file__).parents[1]/'backend'))
import voice_router as router

def backend(model):
    instance=router.KhanhOmniVoiceBackend.__new__(router.KhanhOmniVoiceBackend)
    instance.cfg={'language':'Vietnamese','num_step':28,'guidance_scale':2.2,'speed':1.25}
    instance.prompt=object();instance.reference=router.ReferenceVoice(Path('reference.wav'),'Lời mẫu')
    instance.sample_rate=24000;instance.model=model
    instance.release=lambda:None
    return instance

def test_native_batch_keeps_order_reference_and_generation_settings(tmp_path):
    calls=[]
    def generate(**kwargs):
        calls.append(kwargs)
        return [np.full(2400,.1*(i+1),dtype=np.float32) for i in range(len(kwargs['text']))]
    b=backend(SimpleNamespace(generate=generate))
    outputs=[tmp_path/(str(i)+'.wav') for i in range(4)]
    b.synthesize_batch(['Câu đầu','Câu sau','Câu nữa','Câu cuối'],outputs)
    assert len(calls)==1 and calls[0]['voice_clone_prompt'] is b.prompt
    assert calls[0]['num_step']==28 and calls[0]['speed']==1.25 and calls[0]['guidance_scale']==2.2
    for i,p in enumerate(outputs):
        audio,rate=sf.read(p)
        assert rate==24000 and abs(audio[0]-.1*(i+1))<.0001

@pytest.mark.parametrize('batch_fails',[False,True])
def test_each_cue_is_validated_and_batch_failure_uses_same_backend(tmp_path,monkeypatch,batch_fails):
    calls=[]
    def generate(**kwargs):
        texts=kwargs['text'];calls.append(texts)
        if isinstance(texts,list) and batch_fails:raise RuntimeError('simulated memory limit')
        return [np.full(2400,.2,dtype=np.float32) for _ in range(len(texts) if isinstance(texts,list) else 1)]
    b=backend(SimpleNamespace(generate=generate));validated=[]
    monkeypatch.setattr(router,'_backend_candidates',lambda _: [{'id':'khanh_omnivoice'}])
    monkeypatch.setattr(router,'_make_backend',lambda *args:b)
    monkeypatch.setattr(router,'_quality_check',lambda p,text,cfg:validated.append(text))
    monkeypatch.setattr(router,'_empty_cuda_cache',lambda:None)
    paths=[tmp_path/(str(i)+'.wav') for i in range(4)]
    texts=['Câu đầu','Câu sau','Câu nữa','Câu cuối']
    used,_=router._synthesize_missing(texts,paths,{'synthesis_batch_size':4,'require_clone':True},b.reference)
    assert validated==texts and used==['khanh_omnivoice']*4
    assert len(calls)==(5 if batch_fails else 1)
    assert all(p.is_file() and json.loads(p.with_suffix('.meta.json').read_text(encoding='utf-8'))['is_clone'] for p in paths)

def test_transient_quality_failure_retries_same_clone_backend(tmp_path,monkeypatch):
    calls=[]
    def generate(**kwargs):
        calls.append(kwargs['text'])
        texts=kwargs['text']
        count=len(texts) if isinstance(texts,list) else 1
        return [np.full(2400,.2,dtype=np.float32) for _ in range(count)]
    b=backend(SimpleNamespace(generate=generate));checks=[]
    monkeypatch.setattr(router,'_backend_candidates',lambda _: [{'id':'khanh_omnivoice'}])
    monkeypatch.setattr(router,'_make_backend',lambda *args:b)
    monkeypatch.setattr(router,'_empty_cuda_cache',lambda:None)
    def quality(path,text,cfg):
        checks.append(text)
        if len(checks)==1:
            raise router.VoiceQualityError('simulated transient invalid audio')
    monkeypatch.setattr(router,'_quality_check',quality)
    path=tmp_path/'cue.wav'
    used,_=router._synthesize_missing(['Một câu'],[path],{'synthesis_batch_size':1,'require_clone':True},b.reference)
    assert used==['khanh_omnivoice']
    assert checks==['Một câu','Một câu']
    assert len(calls)==2
    assert path.is_file()
