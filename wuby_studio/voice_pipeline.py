"""Strict orchestration around the supplied local model adapters; no model invented."""
from __future__ import annotations
import copy, json, os
from pathlib import Path
from filelock import FileLock
from .common import ROOT, sha256, digest, atomic_json, WubyError, NeedsReview
from .captions import parse_srt, validate, cue_hash
from .audio import waveform_quality, align_track

# Deliberately excludes quality/timeline display fields but includes ALL generator settings.
def generation_identity(cfg:dict)->dict:
    excluded={'reference','ref_audio','ref_text','output','output_wav','cache_dir','duration_match',
              'quality_gate','_root','project_root','label','quality','approval_path','reference_approval'}
    forbidden=('api_key','token','password','secret')
    def safe(v):
        if isinstance(v,dict):return {k:safe(x) for k,x in v.items() if not any(s in k.lower() for s in forbidden)}
        if isinstance(v,list):return [safe(x) for x in v]
        return v
    return {k:safe(v) for k,v in cfg.items() if k not in excluded and not any(s in k.lower() for s in forbidden)}

def reference_fingerprint(ref)->dict:
    return {'audio_sha256':sha256(ref.audio) if ref.audio else '', 'text':ref.text or ''}

def render(router,srt_path,output_wav,cfg,video_duration=None,cache_dir=None,reference_audio=None,reference_text=None):
    cfg=copy.deepcopy(cfg);cues=parse_srt(Path(srt_path));cues,notes=validate(cues,video_duration)
    if not cues:raise WubyError('EMPTY_SCRIPT: no silence substitute')
    out=Path(output_wav).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    ref=router._reference_from_config(srt_path,cfg,reference_audio,reference_text)
    router._validate_reference(ref,cfg)
    strict=bool(cfg.get('require_clone',False))
    if strict and not ref.audio:raise WubyError('CLONE_REFERENCE_MISSING')
    if strict and ref.audio and not ref.text:raise NeedsReview("REFERENCE_TRANSCRIPT_REQUIRED: use the exact words spoken in the reference, not the Vietnamese target text")
    if ref.audio:waveform_quality(ref.audio)
    candidates=router._backend_candidates(cfg)
    # No per-sentence model changes in a Wuby voice; a failing pinned backend fails the job.
    if strict and not cfg.get('allow_backend_switch',False):candidates=candidates[:1]
    if strict and len(candidates)>1:raise WubyError('Clone backend switching is not allowed within one voice track')
    cfg['engine']='router';cfg['router']={'backends':candidates}
    ident=generation_identity(cfg); ref_id=reference_fingerprint(ref)
    root=Path(cache_dir) if cache_dir else out.parent/'.cache'/'wuby_voice_v7'
    root.mkdir(parents=True,exist_ok=True)
    paths=[];missing={};metas={}
    lock_path=Path(cfg.get('project_root') or ROOT)/'workspace'/'wuby_model.lock'
    lock_path.parent.mkdir(parents=True,exist_ok=True)
    with FileLock(str(lock_path),timeout=600):
        for c in cues:
            key=digest({'schema':7,'text':c.text,'speaker':c.speaker,'generation':ident,'reference':ref_id})
            p=root/(key+'.wav');mp=p.with_suffix('.meta.json');paths.append(p)
            valid=False
            if p.exists() and mp.exists():
                try:
                    m=json.loads(mp.read_text(encoding='utf-8'))
                    valid=(m.get('schema')==7 and m.get('wav_sha256')==sha256(p)
                           and m.get('reference')==ref_id and m.get('generation')==ident
                           and (not strict or m.get('is_clone') is True))
                    if valid:waveform_quality(p);metas[p.name]=m
                except (ValueError,OSError,WubyError):valid=False
            if not valid:missing[str(p)]=(c.text,p)
        attempts=[];used=[]
        if missing:
            texts=[v[0] for v in missing.values()];dst=[v[1] for v in missing.values()]
            used,attempts=router._synthesize_missing(texts,dst,cfg,ref)
            for text,p in zip(texts,dst):
                m=json.loads(p.with_suffix('.meta.json').read_text(encoding='utf-8'))
                if strict and (not m.get('is_clone') or not ref.audio):raise WubyError('PRESET_RETURNED_WHILE_CLONE_REQUIRED')
                m.update(schema=7,reference=ref_id,generation=ident,wav_sha256=sha256(p))
                atomic_json(p.with_suffix('.meta.json'),m);metas[p.name]=m
        for p in paths:
            if p.name not in metas:metas[p.name]=json.loads(p.with_suffix('.meta.json').read_text(encoding='utf-8'))
        real_backends=sorted({metas[p.name]['backend'] for p in paths})
        if strict and len(real_backends)!=1:raise WubyError('MIXED_VOICE_BACKENDS_IN_CACHE')
        timing=cfg.get('duration_match') or {}
        synthesis_speed=float(cfg.get('synthesis_speed',cfg.get('speed',1.0)))
        playback_speed=float(cfg.get('playback_speed',synthesis_speed))
        base_tempo=max(1.0,playback_speed/synthesis_speed)
        report=align_track(cues,paths,out,video_duration,max_speedup=float(timing.get('max_speedup',1.48)),
                           gap_sec=float(timing.get('minimum_gap_sec',.06)),
                           adaptive=bool(timing.get('adaptive', True)),base_tempo=base_tempo,
                           max_early_start=float(timing.get('max_early_start',0.0)))
        report.update(synthesis_speed=synthesis_speed,playback_speed=playback_speed)
        clone=bool(ref.audio and all(metas[p.name].get('is_clone') is True for p in paths))
        report.update(schema=7,reference_audio=str(ref.audio) if ref.audio else None,reference=ref_id,
                      generation=ident,backend=real_backends,final_backend=real_backends[0],
                      final_mode='clone_conditioned' if clone else 'preset_voice',clone_conditioned=clone,
                      clone_success=False,speaker_identity_verified=False,
                      identity_note='Reference conditioning is verified; naturalness/identity require listening. F0 is NOT identity.',
                      cue_count=len(cues),new_cue_count=len(missing),output_sha256=sha256(out),
                      attempts=[a.__dict__ for a in attempts])
        atomic_json(out.with_name(out.stem+'_voice_report.json'),report)
        atomic_json(out.with_name(out.stem+'_report.json'),report)
    print(f'[Voice V7] CLONE_CONDITIONED={clone}; identity_verified=False; {len(cues)} cues; no overlap/truncation')
    return str(out)

def approval_key(profile:dict,ref)->str:
    return digest({'schema':7,'generation':generation_identity(profile),'reference':reference_fingerprint(ref)})

def check_approval(profile:dict,ref,root:Path=ROOT)->dict:
    key=approval_key(profile,ref);p=root/'workspace'/'voice_approvals'/(key+'.json')
    if not p.exists():raise NeedsReview('VOICE_LISTENING_APPROVAL_REQUIRED: run test-voice, listen and approve this reference/profile')
    approval=json.loads(p.read_text(encoding='utf-8'))
    if approval.get('key')!=key or not approval.get('listened'):raise NeedsReview('INVALID_VOICE_APPROVAL')
    sample=Path(approval.get('sample',''))
    if not sample.is_file() or sha256(sample)!=approval.get('sample_sha256'):raise NeedsReview('APPROVED_SAMPLE_MISSING_OR_CHANGED')
    return approval
