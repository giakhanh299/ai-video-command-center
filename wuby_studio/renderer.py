from __future__ import annotations
from dataclasses import asdict
import json, math, os, shutil, sys, tempfile, time
from fractions import Fraction
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .common import ROOT, WubyError, NeedsReview, ConfigError, atomic_json, sha256, binary, resolve, run
from .config import validate as validate_config, THEMES
from .captions import Cue, validate as validate_cues, wrap, paginate, cue_hash
from .media import probe, frame_rate, snapshot
from .audio import require_voice_report

def load_font(cfg,size):
    root=Path(cfg.get('_root') or ROOT)
    paths=[]
    if cfg.get('font_path'):paths.append(resolve(cfg['font_path'],root))
    paths += [root/'assets/fonts/BeVietnamPro-Bold.ttf',Path('C:/Windows/Fonts/arialbd.ttf'),
              Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')]
    for p in paths:
        if p.is_file():return ImageFont.truetype(str(p),size),p
    raise ConfigError('NO_VIETNAMESE_FONT: run tools/install_free_assets.py --font or configure font_path')

def pixel_rect(cfg,key):
    x,y,w,h=cfg['layout'][key];W,H=cfg['width'],cfg['height']
    return round(x*W),round(y*H),max(2,round(w*W/2)*2),max(2,round(h*H/2)*2)

def graphics(cfg,title,work):
    W,H=cfg['width'],cfg['height'];pal=THEMES[cfg['theme']]
    bg=Image.new('RGB',(W,H),pal['bg']);d=ImageDraw.Draw(bg)
    # Restrained, reusable cartoon editorial system. The source remains the hero.
    for x,y,r in [(-.12,.37,.25),(.87,.62,.19),(.78,-.03,.18)]:
        d.ellipse((int((x-r)*W),int(y*H-r*W),int((x+r)*W),int(y*H+r*W)),fill=pal['soft'])
    small,_=load_font(cfg,max(12,round(W*.020)))
    label=str(cfg['label'])[:65]
    if small.getlength(label)>W*.82:raise NeedsReview('CHANNEL_LABEL_TOO_WIDE')
    d.text((W/2,H*.028),label,font=small,fill=pal['muted'],anchor='mm')
    # Subtle pill separators, no stock stickers masking the character.
    d.rounded_rectangle((W*.44,H*.203,W*.56,H*.207),radius=max(2,int(W*.002)),fill=pal['accent'])
    x,y,w,h=pixel_rect(cfg,'video');pad=max(3,round(W*.009))
    d.rounded_rectangle((x-pad,y-pad+pad,w+x+pad,h+y+pad*2),radius=W*.034,fill=pal['soft'])
    d.rounded_rectangle((x-pad,y-pad,w+x+pad,h+y+pad),radius=W*.031,fill=pal['card'])
    if cfg['subtitle']['enabled']:
        x,y,w,h=pixel_rect(cfg,'subtitle')
        d.rounded_rectangle((x-8,y-5,x+w+8,y+h+5),radius=W*.035,fill=pal['card'])
        # Three small pacing dots are decorative, not additional captions.
        for j in range(3):
            cx=W*(.485+j*.015);rr=max(2,W*.003)
            d.ellipse((cx-rr,H*.765-rr,cx+rr,H*.765+rr),fill=pal['accent'] if j==1 else pal['soft'])
    bg.save(work/'background.png')
    overlay=Image.new('RGBA',(W,H),(0,0,0,0));td=ImageDraw.Draw(overlay)
    x,y,w,h=pixel_rect(cfg,'title');font,fp=load_font(cfg,max(16,round(W*cfg['title']['font_ratio'])))
    lines=wrap(title,font,w) if title else []
    if len(lines)>int(cfg['title']['max_lines']):raise NeedsReview('TITLE_TOO_LONG: shorten title or increase title region')
    leading=font.size*1.32
    if len(lines)*leading>h:raise NeedsReview('TITLE_OUTSIDE_SAFE_REGION')
    for i,line in enumerate(lines):
        yy=y+(h-len(lines)*leading)/2+i*leading
        td.text((x+w/2,yy),line,font=font,fill=pal['ink'],anchor='mt')
    overlay.save(work/'title.png')
    return {'font_path':str(fp),'title_lines':lines}

def _ass_time(t):
    n=max(0,round(t*100));s,c=divmod(n,100);m,s=divmod(s,60);h,m=divmod(m,60)
    return f'{h}:{m:02}:{s:02}.{c:02}'

def _ass_text(text):
    return str(text).replace('\\','\uff3c').replace('{','\uff5b').replace('}','\uff5d').replace('\n',' ')

def make_ass(cues,cfg,work):
    font,fp=load_font(cfg,max(14,round(cfg['width']*cfg['subtitle']['font_ratio'])))
    x,y,w,h=pixel_rect(cfg,'subtitle');family=font.getname()[0]
    pages=paginate(cues,font,w*.90,int(cfg['subtitle']['max_lines']),float(cfg['subtitle']['min_page_sec'])) if cfg['subtitle']['enabled'] else []
    leading=font.size*1.32
    if max((len(p['lines']) for p in pages),default=0)*leading>h:raise NeedsReview('SUBTITLE_OUTSIDE_SAFE_REGION')
    pal=THEMES[cfg['theme']];hexcol=pal['ink'].lstrip('#');color='&H00'+hexcol[4:6]+hexcol[2:4]+hexcol[0:2]
    # Explicit line breaking from measured glyph widths; no double text layers.
    header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {cfg['width']}
PlayResY: {cfg['height']}
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dialogue,{family},{font.size},{color},{color},&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    lines=[]
    for p in pages:
        txt=r'\N'.join(_ass_text(s) for s in p['lines'])
        lines.append(f'Dialogue: 1,{_ass_time(p["start"])},{_ass_time(p["end"])},Dialogue,,0,0,0,,{{\\an5\\pos({x+w/2:.1f},{y+h/2:.1f})\\q2\\fad(50,50)}}'+txt)
    path=work/'captions.ass';path.write_text(header+'\n'.join(lines)+'\n',encoding='utf-8')
    return path,pages,fp

def crop_rect(cleanup,meta):
    crop=cleanup.get('crop');v=meta['video'];W,H=v['width'],v['height']
    if crop is None:return (0,0,W//2*2,H//2*2)
    if len(crop)!=4:raise ConfigError('Crop must be [x,y,w,h] normalized to source')
    x,y,w,h=map(float,crop)
    if not all(math.isfinite(a) for a in (x,y,w,h)) or x<0 or y<0 or w<=0 or h<=0 or x+w>1.00001 or y+h>1.00001:raise ConfigError('Invalid source crop')
    return (int(x*W)//2*2,int(y*H)//2*2,max(2,int(w*W)//2*2),max(2,int(h*H)//2*2))

def filter_path(path:Path):
    return str(path.resolve()).replace('\\','/').replace(':','\\:').replace("'",r"\' ").strip()

def prepare_source(source:Path,cfg,work,notes):
    cc=cfg['cleanup']
    if cc.get('input_already_rendered') and not cc.get('crop') and not cc.get('masks'):
        if cc['mode']!='none' or cfg['subtitle']['enabled']:
            raise NeedsReview('ALREADY_BURNED_INPUT: disable cleanup and new subtitles, or provide reviewed crop/masks')
        notes.append({'type':'preprocessed_input_passthrough',
                      'message':'Existing video/audio retained; upstream OCR and clone require separate review'})
    if cc['mode']=='ocr':
        backend=Path(cfg.get('_root') or ROOT)/'backend'
        if str(backend) not in sys.path:sys.path.insert(0,str(backend))
        from backend import wuby_ocr_overlay
        # OCR is a production option, not a claim that all text was detected.
        events=wuby_ocr_overlay.scan_video_text_events(str(source),sample_fps=float(cc['sample_fps']))
        cleaned=wuby_ocr_overlay.clean_video_ocr_backgrounds(str(source),str(work/'ocr_clean.mp4'),events)
        atomic_json(work/'ocr_tracks.json',events)
        notes.append({'type':'ocr_unverified','tracks':len(events),'message':'Review moving/residual text; no automatic visual PASS'})
        return Path(cleaned)
    if cc['mode']=='none' and not cc.get('input_already_rendered'):
        notes.append({'type':'source_text_not_removed','message':'Only use for text-free sources or reviewed crop'})
    return source

def render(source:str|Path,output:str|Path,cues, title:str, config:dict, voice_audio:str|Path|None=None,
           write_review_artifacts:bool=True)->str:
    cfg=validate_config(config);root=Path(cfg.get('_root') or ROOT)
    source=resolve(source,root);out=resolve(output,root)
    if source==out:raise ConfigError('Never overwrite source media')
    out.parent.mkdir(parents=True,exist_ok=True)
    meta=probe(source)
    if not meta['video']:raise ConfigError('Input has no video')
    duration=meta['duration'];fps=frame_rate(meta,cfg['fps']);fps_n=float(Fraction(fps))
    cues,notes=validate_cues(cues,duration)
    if cfg['cleanup'].get('input_already_rendered') and cues:
        raise NeedsReview('ALREADY_BURNED_INPUT: do not supply a second caption track')
    voice=resolve(voice_audio,root) if voice_audio else None
    mode=cfg['audio']['mode'];voice_report=None
    if mode=='clone':
        if not voice or not voice.is_file():raise NeedsReview('CLONE_AUDIO_REQUIRED')
        if cfg['audio'].get('accept_legacy_clone', False):
            voice_report={'schema':7,'legacy_clone_audio':True,'path':str(voice)}
        else:
            voice_report=require_voice_report(voice,cues,True)
            from .speech_qc import verify
            voice_report['speech_qc']=verify(voice,cues,cfg)
        if probe(voice)['duration']>duration+1/fps_n:raise NeedsReview('VOICE_LONGER_THAN_VIDEO')
    elif voice is not None:raise ConfigError('Unexpected voice file in preserve/silent mode')
    ts=time.monotonic()
    with tempfile.TemporaryDirectory(prefix=out.stem+'_render_',dir=out.parent) as tmp:
        work=Path(tmp);clean_source=prepare_source(source,cfg,work,notes)
        graphic=graphics(cfg,title,work);ass,pages,font_path=make_ass(cues,cfg,work)
        if any(p['end']<=p['start'] for p in pages):raise WubyError('Invalid caption page')
        W,H=cfg['width'],cfg['height'];x,y,w,h=pixel_rect(cfg,'video')
        srcmeta=probe(clean_source);cx,cy,cw,ch=crop_rect(cfg['cleanup'],srcmeta)
        inputs=['-i',str(clean_source),'-loop','1','-framerate',fps,'-i',str(work/'background.png'),
                '-loop','1','-framerate',fps,'-i',str(work/'title.png')]
        count=3;f=[]
        # Masks are applied in SOURCE coordinates/time, before reframing and zoom.
        src='[0:v]';source_filters=[]
        for i,mask in enumerate(cfg['cleanup'].get('masks') or []):
            rx,ry,rw,rh=crop_rect({'crop':mask['rect']},srcmeta)
            start=float(mask.get('start',0));end=float(mask.get('end',duration));color=str(mask.get('color','#FFFFFF'))
            if not 0<=start<end<=duration+.05:raise ConfigError('Mask outside source timeline')
            import re
            if not re.fullmatch(r'#[0-9A-Fa-f]{6}',color):raise ConfigError('Mask requires a hex color')
            source_filters.append(f"drawbox=x={rx}:y={ry}:w={rw}:h={rh}:color={color}:t=fill:enable='gte(t,{start:.6f})*lt(t,{end:.6f})'")
        pal=THEMES[cfg['theme']]
        source_filters += [f'fps={fps}','setpts=PTS-STARTPTS',f'crop={cw}:{ch}:{cx}:{cy}',
                           f'scale={w}:{h}:force_original_aspect_ratio=decrease',
                           f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={pal["card"]}','setsar=1']
        zoom=float(cfg['motion']['zoom'])
        if zoom>1.0001:
            source_filters.append(f"zoompan=z='1+({zoom}-1)*(1-cos(2*PI*on/({fps_n:.8f}*6)))/2':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps={fps}")
        f.append(src+','.join(source_filters)+'[source]')
        f.append('[1:v]setsar=1,setpts=PTS-STARTPTS[bg]')
        f.append(f'[bg][source]overlay={x}:{y}:shortest=1[v0]');v='[v0]'
        if title and cfg['title']['enabled']:
            until=min(duration,float(cfg['title']['duration']));fade=max(0,until-.18)
            f.append(f'[2:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st={fade:.6f}:d=0.18:alpha=1[title]')
            import re
            normal=lambda s:re.sub(r'[^\w]+','',s,flags=re.UNICODE).casefold()
            nt=normal(title);hidden=[c for c in cues if nt and nt==normal(c.text)]
            gate='*'.join(f'not(gte(t,{c.start:.6f})*lt(t,{c.end:.6f}))' for c in hidden)
            enable=f'lt(t,{until:.6f})'+('*'+gate if gate else '')
            if hidden:notes.append({'type':'duplicate_title_hidden_during_caption','intervals':[[c.start,c.end] for c in hidden]})
            f.append(f"{v}[title]overlay=0:0:enable='{enable}'[vt]");v='[vt]'
        # An unused image input is allowed; no unused filter output is created.
        if pages:
            font_dir=work/'fonts';font_dir.mkdir()
            shutil.copyfile(font_path,font_dir/font_path.name)
            f.append(f"{v}subtitles=filename=captions.ass:fontsdir=fonts[vs]");v='[vs]'
        logo_path=resolve(cfg['logo']['path'],root) if cfg['logo'].get('path') else None
        if cfg['logo']['enabled'] and logo_path and logo_path.is_file():
            if logo_path.suffix.lower()!='.png':raise ConfigError('V7 logo must be a PNG')
            lx,ly,lw,lh=pixel_rect(cfg,'logo');cycle=float(cfg['logo']['cycle_sec']);alpha=float(cfg['logo']['opacity'])
            # Preserve aspect inside reserved region; drift stays inside that region.
            inputs += ['-loop','1','-framerate',fps,'-i',str(logo_path)];idx=count;count+=1
            drift=min(float(cfg['logo']['drift_ratio'])*W,lw*.12)
            f.append(f'[{idx}:v]scale={int(lw-2*drift)}:{lh}:force_original_aspect_ratio=decrease,format=rgba,colorchannelmixer=aa={alpha}[logo]')
            if cfg['logo']['mode']=='drift_fade':
                # Alpha fade follows the global clock, not individual scenes.
                f[-1]=f[-1][:-6]+f",geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*(0.35+0.65*(1-cos(2*PI*T/{cycle}))/2)'[logo]"
                xx=f'{lx}+({lw}-w)/2+{drift:.3f}*sin(2*PI*t/{cycle})'
            else:xx=f'{lx}+({lw}-w)/2'
            f.append(f"{v}[logo]overlay=x='{xx}':y='{ly}+({lh}-h)/2'[vl]");v='[vl]'
        elif cfg['logo']['enabled']:notes.append({'type':'logo_missing','message':'No default-channel logo substituted'})
        audio_label=None;audio_inputs=[]
        if mode=='clone':
            inputs+=['-i',str(voice)];vi=count;count+=1
            norm='loudnorm=I=-16:TP=-1.5:LRA=11,' if cfg['audio']['normalize_voice'] else ''
            f.append(f'[{vi}:a]{norm}aresample=48000,apad,atrim=duration={duration:.8f},asetpts=PTS-STARTPTS[voice]')
            audio_inputs=['[voice]']

            diag_cfg = cfg.get('dialogue_replace') or cfg.get('audio', {}).get('dialogue_replace', {})
            if diag_cfg.get('enabled', False) and srcmeta['audio']:
                try:
                    from dialogue_replace import prepare_dialogue_replacement
                except ImportError:
                    from backend.dialogue_replace import prepare_dialogue_replacement
                try:
                    stems = prepare_dialogue_replacement(
                        video_path=source,
                        cache_root=diag_cfg.get("cache_dir", r"cache\audio_stems"),
                        model_filename=diag_cfg.get("model_filename", "UVR-MDX-NET-Inst_HQ_3.onnx"),
                        model_dir=diag_cfg.get("model_file_dir", r"D:/0.1_FACE_BOOK/Lay video tiktok/MODELS/audio_separator"),
                        audio_sep_python=diag_cfg.get("separator_python", r"D:/0.1_FACE_BOOK/Lay video tiktok/MOI_TRUONG/audio_sep_env\Scripts\python.exe"),
                        require_cuda=bool(diag_cfg.get("require_cuda", True)),
                    )
                    inst_path = stems['instrumental']
                    inputs += ['-i', str(inst_path)]
                    ii = count; count += 1
                    inst_vol = float(diag_cfg.get('instrumental_volume', 0.8))
                    f.append(f'[{ii}:a]volume={inst_vol},aresample=48000,apad,atrim=duration={duration:.8f},asetpts=PTS-STARTPTS[inst_clean]')
                    audio_inputs.append('[inst_clean]')
                    notes.append({'type':'dialogue_hard_replace','instrumental':inst_path,'volume':inst_vol})
                except Exception as exc:
                    if diag_cfg.get('hard_replace', True):
                        raise RuntimeError(f"[Wuby FATAL] Separator failed (hard_replace=True). Dừng render để không lọt tiếng gốc: {exc}") from exc
                    print(f"[Wuby] Separator failed, fallback: {exc}")
            elif srcmeta['audio'] and cfg['audio'].get('keep_original_outside_subtitles', True):
                pad=float(cfg['audio'].get('subtitle_mute_pad_sec',0.04))
                mute_expr='+'.join(
                    f'between(t,{max(0,c.start-pad):.6f},{min(duration,c.end+pad):.6f})'
                    for c in cues
                ) or '0'
                # Keep source/BGM/SFX outside translated subtitle windows, mute it while clone voice reads.
                f.append(f"[0:a]aresample=48000,apad,atrim=duration={duration:.8f},asetpts=PTS-STARTPTS,volume=0:enable='{mute_expr}'[original_gated]")
                audio_inputs.append('[original_gated]')
                notes.append({'type':'original_audio_gated_by_subtitles','subtitle_windows':len(cues),'pad_sec':pad})
        elif mode=='preserve' and srcmeta['audio']:
            f.append(f'[0:a]aresample=48000,apad,atrim=duration={duration:.8f},asetpts=PTS-STARTPTS[original]');audio_inputs=['[original]']
            notes.append({'type':'existing_audio_preserved','message':'This is not a newly tested voice clone'})
        bg_path=cfg['audio'].get('background_path')
        if bg_path:
            bp=resolve(bg_path,root)
            if not bp.is_file():raise ConfigError('Background audio missing')
            inputs+=['-stream_loop','-1','-i',str(bp)];bi=count;count+=1
            gain=float(cfg['audio']['background_gain'])
            if not 0<=gain<=.5:raise ConfigError('background_gain must be 0..0.5')
            f.append(f'[{bi}:a]volume={gain},aresample=48000,atrim=duration={duration:.8f},asetpts=PTS-STARTPTS[music]')
            if mode=='clone':
                f.append('[voice]asplit=2[vdry][vside]');audio_inputs=['[vdry]']
                f.append('[music][vside]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=250[ducked]');audio_inputs+=['[ducked]']
            else:audio_inputs+=['[music]']
        sfx_report=[]
        if cfg['sfx']['enabled']:
            for ev in cfg['sfx']['events']:
                p=resolve(ev['path'],root);start=float(ev['start']);em=probe(p);length=em['duration'];gain=float(ev.get('gain',.12))
                if not 0<=gain<=float(cfg['sfx']['max_gain']) or not 0<=start<duration or start+length>duration:
                    raise ConfigError('SFX gain/time outside limits')
                collision=any(min(c.end,start+length)>max(c.start,start) for c in cues)
                if collision and cfg['sfx']['avoid_speech']:
                    sfx_report.append({'start':start,'status':'skipped_over_speech'});continue
                inputs+=['-i',str(p)];ei=count;count+=1;tag=f'[sfx{ei}]'
                f.append(f'[{ei}:a]volume={gain},aresample=48000,adelay={round(start*1000)}:all=1,apad,atrim=duration={duration:.8f}{tag}')
                audio_inputs.append(tag);sfx_report.append({'start':start,'status':'mixed','path':str(p),'gain':gain})
        if audio_inputs:
            if len(audio_inputs)>1:
                f.append(''.join(audio_inputs)+f'amix=inputs={len(audio_inputs)}:duration=longest:normalize=0,alimiter=limit=0.95:level=0,atrim=duration={duration:.8f}[aout]')
                audio_label='[aout]'
            else:audio_label=audio_inputs[0]
        f.append(v+f'fps={fps},setsar=1,format=yuv420p[vout]')
        output_tmp=work/'result.mp4'
        def cmd(codec):
            args=[binary('ffmpeg'),'-y','-v','error','-filter_complex_threads','1',*inputs,'-filter_complex',';'.join(f),'-map','[vout]']
            if audio_label:args+=['-map',audio_label,'-c:a','aac','-b:a',str(cfg['audio'].get('bitrate','96k')),'-ar','48000']
            else:args+=['-an']
            if codec=='h264_nvenc':args+=['-c:v',codec,'-preset','p4','-cq',str(cfg['crf']),'-b:v','0']
            else:args+=['-c:v','libx264','-crf',str(cfg['crf']),'-preset','veryfast']
            args+=['-threads',str(cfg['threads']),'-t',f'{duration:.8f}','-fps_mode','cfr','-movflags','+faststart',str(output_tmp)]
            return args
        codec=cfg['encoder']
        try:run(cmd(codec),timeout=max(180,float(cfg['queue']['timeout_sec'])),cwd=work)
        except WubyError:
            if codec!='h264_nvenc':raise
            notes.append({'type':'nvenc_failed_cpu_used'});codec='libx264';run(cmd(codec),cwd=work)
        measured=probe(output_tmp);mv=measured['video'];measured_fps=frame_rate(measured)
        if abs(measured['duration']-duration)>1/fps_n+.01:raise WubyError('OUTPUT_DURATION_MISMATCH')
        if Fraction(measured_fps)!=Fraction(fps) or mv['width']!=W or mv['height']!=H:raise WubyError('OUTPUT_GEOMETRY_OR_FPS_MISMATCH')
        os.replace(output_tmp,out)
        
        # Thêm ngẫu nhiên 16 bytes vào cuối file để thay đổi MD5
        try:
            with open(out, 'ab') as f:
                f.write(os.urandom(16))
        except Exception:
            pass
            
        report={'schema':7,'source':str(source),'source_sha256':sha256(source),'source_fps':meta['video'].get('avg_frame_rate'),
                'output':str(out),'output_sha256':sha256(out),'fps':fps,'width':W,'height':H,'duration':measured['duration'],
                'encoder_used':codec,'wall_seconds':round(time.monotonic()-ts,2),'caption_page_count':len(pages),
                'cue_hash':cue_hash(cues),'layout_collisions':0,'caption_time_overlaps':0,
                'residual_source_text_verified':bool(cfg['cleanup']['reviewed']),
                'residual_check_method':'manual_config_acknowledgement' if cfg['cleanup']['reviewed'] else 'not_verified',
                'speaker_identity_verified':False,'clone_conditioned':bool((voice_report or {}).get('clone_conditioned')),
                'speech_qc':(voice_report or {}).get('speech_qc',{'status':'not_run'}),
                'audio_mode':mode,'voice_audio_sha256':sha256(voice) if voice else None,
                'sfx':sfx_report,'notes':notes,'graphics':graphic,
                'status':'needs_review' if cfg['quality']['require_visual_review'] else 'rendered_unreviewed'}
        if write_review_artifacts:
            atomic_json(out.with_name(out.stem+'_render_report.json'),report)
            # Re-render this packet to change visual settings without calling translation/TTS.
            packet={'schema':7,'source':str(source),'source_sha256':sha256(source),'voice_audio':str(voice) if voice else None,
                    'voice_sha256':sha256(voice) if voice else None,'cues':[asdict(c) for c in cues],
                    'title':title,'config':cfg,'output':str(out),'report':str(out.with_name(out.stem+'_render_report.json'))}
            atomic_json(out.with_name(out.stem+'_visual_packet.json'),packet)
            shutil.copy2(ass,out.with_name(out.stem+'_captions.ass'))
            # Sample actual rendered frames, including endpoints. These are not exhaustive OCR checks.
            evidence=out.parent/(out.stem+'_frames');evidence.mkdir(exist_ok=True)
            for i,t in enumerate([.1,min(duration-.1,1.5),duration*.45,duration*.72,max(.0,duration-.1)]):
                snapshot(out,evidence/f'{i+1}.jpg',t,width=min(540,W))
    return str(out)

def rerender(packet_path:Path,output:Path,overrides:dict|None=None):
    from .config import merge
    p=json.loads(packet_path.read_text(encoding='utf-8'))
    if p.get('schema')!=7 or sha256(p['source'])!=p['source_sha256']:raise NeedsReview('SOURCE_CHANGED_SINCE_PACKET')
    if p.get('voice_audio') and sha256(p['voice_audio'])!=p['voice_sha256']:raise NeedsReview('VOICE_CHANGED_SINCE_PACKET')
    cfg=merge(p['config'],overrides or {})
    if cfg['audio']!=p['config']['audio']:raise ConfigError('Visual re-render cannot modify audio config')
    return render(p['source'],output,p['cues'],p['title'],cfg,p.get('voice_audio'))
