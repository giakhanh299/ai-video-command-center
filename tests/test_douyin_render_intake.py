import hashlib
import importlib.util
import json
import sqlite3
from types import SimpleNamespace
from pathlib import Path

import pytest

SPEC=importlib.util.spec_from_file_location('douyin_render',Path(__file__).parents[1]/'tools/render_douyin_intake.py')
render=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(render)

@pytest.fixture
def setup_job(tmp_path,monkeypatch):
    runtime=tmp_path/'runtime';runtime.mkdir()
    fb=tmp_path/'fb';(fb/'config').mkdir(parents=True)
    root=tmp_path/'KENH_008_ChiDepDiCau';raw=root/'01_CHUA_RENDER';raw.mkdir(parents=True)
    vid='7696860867774116729';source=raw/('douyin_'+vid+'.mp4');source.write_bytes(b'original video')
    source.with_suffix('.douyin.json').write_text(json.dumps({'duration':30,'title':'title'}),encoding='utf-8')
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    (fb/'config/channels.json').write_text(json.dumps([{'channel_id':'KENH_008','workspace_root':str(root)}]),encoding='utf-8')
    with sqlite3.connect(runtime/'history.sqlite') as db:
        db.execute('CREATE TABLE items(id TEXT,channel TEXT,path TEXT,sha256 TEXT,state TEXT)')
        db.execute('INSERT INTO items VALUES(?,?,?,?,?)',(vid,'KENH_008',str(source),sha,'DOWNLOADED'))
    work=tmp_path/'work';cfg={'workflow':'gaidep_cauca','voice':'omni_nu_cute'}
    for key,value in [('RUNTIME',runtime),('FB',fb),('ROOT',tmp_path),('WORK',work)]:monkeypatch.setattr(render,key,value)
    monkeypatch.setattr(render,'resolve_config',lambda _:cfg)
    monkeypatch.setattr(render,'probe',lambda _:30)
    return runtime,root,vid,sha,work

def worker_result(monkeypatch,root,wrong_channel=False):
    class Process:
        returncode=0
        def __init__(self,args,**kwargs):
            job_path=Path(args[-1]);job=json.loads(job_path.read_text(encoding='utf-8'))
            final=root/'02_MOI_RENDER_CHO_XAC_NHAN'/'output.mp4';final.parent.mkdir(exist_ok=True);final.write_bytes(b'rendered')
            receipt={'status':'RENDERED_PENDING_REVIEW','id':job['id'],'channel':'KENH_001' if wrong_channel else job['channel'],
                'input_sha256':job['input_sha256'],'config_sha256':job['config_sha256'],'publish_permission':'NONE',
                'path':str(final),'output_sha256':render.digest(final)}
            (job_path.parent/'result.json').write_text(json.dumps(receipt),encoding='utf-8')
        def wait(self,**kwargs):return 0
    monkeypatch.setattr(render.subprocess,'Popen',Process)

def test_completed_render_is_not_replayed(setup_job,monkeypatch):
    runtime,root,vid,sha,work=setup_job
    worker_result(monkeypatch,root)
    first=render.run()
    assert len(first['completed'])==1 and not first['failed']
    monkeypatch.setattr(render.subprocess,'Popen',lambda *a,**k:pytest.fail('completed render was replayed'))
    second=render.run()
    assert not second['completed'] and second['skipped'][0]['state']=='COMPLETED'

def test_mismatched_receipt_is_rejected(setup_job,monkeypatch):
    runtime,root,vid,sha,work=setup_job
    worker_result(monkeypatch,root,wrong_channel=True)
    result=render.run()
    assert not result['completed'] and len(result['failed'])==1
    with sqlite3.connect(runtime/'renders.sqlite') as db:
        assert db.execute('SELECT state FROM renders WHERE id=?',(vid,)).fetchone()[0]=='FAILED'

def test_retry_refuses_partial_media(setup_job,monkeypatch):
    runtime,root,vid,sha,work=setup_job
    worker_result(monkeypatch,root,wrong_channel=True)
    render.run()
    folder=next(work.iterdir());(folder/'result.json').unlink();(folder/'output.mp4').write_bytes(b'uncertain')
    monkeypatch.setattr(render.subprocess,'Popen',lambda *a,**k:pytest.fail('uncertain media was replayed'))
    result=render.run(retry_failed=True)
    assert not result['completed'] and result['skipped'][0]['state']=='ARTIFACT_RECONCILIATION_REQUIRED'

def test_retry_with_no_failed_jobs_has_no_worker(setup_job,monkeypatch):
    monkeypatch.setattr(render.subprocess,'Popen',lambda *a,**k:pytest.fail('retry started a new download'))
    result=render.run(retry_failed=True)
    assert not result['completed'] and result['skipped'][0]['state']=='NOT_FAILED'

def test_clone_transcript_uses_reference_audio_and_hash_cache(tmp_path,monkeypatch):
    from backend import voice_router,sub_processor
    audio=tmp_path/'reference.wav';audio.write_bytes(b'actual voice recording')
    profile={'require_clone':True,'ref_audio':str(audio),'ref_text':''}
    monkeypatch.setattr(render,'RUNTIME',tmp_path/'runtime')
    monkeypatch.setattr(voice_router,'_reference_from_config',lambda *a:SimpleNamespace(audio=audio,text=None))
    monkeypatch.setattr(voice_router,'_validate_reference',lambda *a:None)
    calls=[]
    def transcribe(path):
        calls.append(path);return [SimpleNamespace(text='Words spoken in the reference')]
    monkeypatch.setattr(sub_processor,'get_transcriber',lambda model:SimpleNamespace(transcribe=transcribe) if model=='large-v3' else pytest.fail('wrong model'))
    first=render.prepare_voice_reference(profile,tmp_path)
    second=render.prepare_voice_reference(profile,tmp_path)
    assert calls==[str(audio)]
    assert first['reference']['text']==second['ref_text']=='Words spoken in the reference'
    assert profile['ref_text']==''
    audio.write_bytes(b'changed recording')
    render.prepare_voice_reference(profile,tmp_path)
    assert len(calls)==2

def test_clone_transcript_replaces_incorrect_configured_text(tmp_path,monkeypatch):
    from backend import voice_router,sub_processor
    audio=tmp_path/'reference.wav';audio.write_bytes(b'actual short voice recording')
    profile={'require_clone':True,'ref_audio':str(audio),
             'ref_text':'Configured sentence that is not spoken in this file'}
    monkeypatch.setattr(render,'RUNTIME',tmp_path/'runtime')
    monkeypatch.setattr(voice_router,'_reference_from_config',
                        lambda *a:SimpleNamespace(audio=audio,text=profile['ref_text']))
    monkeypatch.setattr(voice_router,'_validate_reference',lambda *a:None)
    calls=[]
    def transcribe(path):
        calls.append(path);return [SimpleNamespace(text='Actual words in the sample')]
    monkeypatch.setattr(sub_processor,'get_transcriber',
                        lambda model:SimpleNamespace(transcribe=transcribe))
    fixed=render.prepare_voice_reference(profile,tmp_path)
    again=render.prepare_voice_reference(profile,tmp_path)
    assert calls==[str(audio)]
    assert fixed['ref_text']==again['reference']['text']=='Actual words in the sample'
    assert fixed['reference_transcript_source']=='audio_asr_large-v3_sha256_bound'
    assert profile['ref_text']=='Configured sentence that is not spoken in this file'

def test_clone_transcript_empty_audio_is_rejected(tmp_path,monkeypatch):
    from backend import voice_router,sub_processor
    audio=tmp_path/'reference.wav';audio.write_bytes(b'no speech')
    monkeypatch.setattr(render,'RUNTIME',tmp_path/'runtime')
    monkeypatch.setattr(voice_router,'_reference_from_config',lambda *a:SimpleNamespace(audio=audio,text=None))
    monkeypatch.setattr(voice_router,'_validate_reference',lambda *a:None)
    monkeypatch.setattr(sub_processor,'get_transcriber',lambda _:SimpleNamespace(transcribe=lambda _:[]))
    with pytest.raises(ValueError,match='NO_SPEECH'):
        render.prepare_voice_reference({'require_clone':True},tmp_path)
