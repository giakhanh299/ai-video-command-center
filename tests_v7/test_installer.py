import json
from pathlib import Path
import pytest
from apply_wuby_v7 import sha,install,rollback

@pytest.fixture
def patch(tmp_path):
    bundle=tmp_path/'bundle';target=tmp_path/'live'
    (bundle/'backend').mkdir(parents=True);(target/'backend').mkdir(parents=True)
    old=b'original source\n';new=b'fixed source\n'
    (target/'backend/core.py').write_bytes(old);(bundle/'backend/core.py').write_bytes(new)
    cfg={'api_key':'TEST_SENTINEL_NOT_A_REAL_KEY','presets':{'wuby':{'workflow':'wuby'},'film':{'voice':'unchanged'}},
         'voice_profiles':{'wuby_clone':{'model':'KEEP_MODEL','ref_audio':'KEEP_PATH.wav','ref_text':'KEEP_TEXT','require_clone':False},'film':{'voice':'KEEP'}}}
    (target/'backend/channels_config.json').write_text(json.dumps(cfg));(bundle/'backend/channels_config.json').write_text(json.dumps(cfg))
    (bundle/'new.py').write_text('new file')
    files={}
    for rel in ('backend/core.py','backend/channels_config.json','new.py'):
        files[rel]={'new_sha256':sha(bundle/rel),'base_sha256':sha(target/rel)}
    (bundle/'PATCH_MANIFEST_V7.json').write_text(json.dumps({'files':files}))
    return bundle,target,cfg

def test_dryrun_apply_preserves_private_config_rollback(patch):
    bundle,target,cfg=patch
    before={str(p.relative_to(target)):p.read_bytes() for p in target.rglob('*') if p.is_file()}
    r=install(target,bundle);assert r['mode']=='dry_run';assert not (target/'new.py').exists()
    r=install(target,bundle,True);d=json.loads((target/'backend/channels_config.json').read_text())
    assert d['api_key']==cfg['api_key'] and d['voice_profiles']['wuby_clone']['ref_audio']=='KEEP_PATH.wav'
    assert d['voice_profiles']['wuby_clone']['model']=='KEEP_MODEL' and d['voice_profiles']['film']==cfg['voice_profiles']['film']
    assert d['voice_profiles']['wuby_clone']['require_clone']
    rollback(Path(r['backup']),target)
    assert not (target/'new.py').exists()
    for rel,content in before.items():assert (target/rel).read_bytes()==content

def test_drift_blocks_all_writes(patch):
    bundle,target,_=patch;(target/'backend/core.py').write_text('local edit')
    with pytest.raises(RuntimeError,match='CONFLICTS'):install(target,bundle,True)
    assert not (target/'new.py').exists()

def test_second_apply_idempotent(patch):
    b,t,_=patch;install(t,b,True);assert install(t,b,True)['count']==0

def test_rollback_does_not_delete_later_edit(patch):
    b,t,_=patch;r=install(t,b,True);(t/'new.py').write_text('later work')
    with pytest.raises(RuntimeError,match='File changed'):rollback(Path(r['backup']),t)
    assert (t/'new.py').read_text()=='later work'

def test_bundle_tamper_detected(patch):
    b,t,_=patch;(b/'new.py').write_text('tampered')
    with pytest.raises(RuntimeError,match='Bundle changed'):install(t,b,True)

def test_nested_target_rejected(patch):
    b,t,_=patch
    with pytest.raises(RuntimeError,match='OUTSIDE'):install(b/'live',b)
