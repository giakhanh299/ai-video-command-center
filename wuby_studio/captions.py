from __future__ import annotations
from dataclasses import dataclass, asdict
import math,re,unicodedata
from pathlib import Path
from .common import NeedsReview, ConfigError, digest

@dataclass(frozen=True)
class Cue:
    start:float
    end:float
    text:str
    speaker:str='wuby'
    @property
    def duration(self): return self.end-self.start

def clean_text(t:str, *, normalize_speech:bool=True)->str:
    t=unicodedata.normalize('NFC',str(t))
    t=re.sub(r'</?(?:b|i|u|font)(?:\s[^>]*)?>','',t,flags=re.I)
    if normalize_speech:
        try:
            from backend.vi_text_normalizer import normalize_vietnamese_text
            t = normalize_vietnamese_text(t)
        except Exception:
            try:
                from vi_text_normalizer import normalize_vietnamese_text
                t = normalize_vietnamese_text(t)
            except Exception:
                pass
    return re.sub(r'\s+',' ',t).strip()

def validate(cues, duration:float|None=None)->tuple[list[Cue],list[dict]]:
    out=[];notes=[]
    for c in cues:
        if isinstance(c,dict): c=Cue(float(c['start']),float(c['end']),clean_text(c['text']),str(c.get('speaker','wuby')))
        else: c=Cue(float(c.start),float(c.end),clean_text(c.text),str(getattr(c,'speaker','wuby')))
        if not all(math.isfinite(t) for t in (c.start,c.end)) or c.start<0 or c.end<=c.start:
            raise ConfigError('Invalid cue timestamp')
        if not c.text: continue
        if duration is not None and c.end>duration+0.045: raise TimingError(f'SUBTITLE_PAST_VIDEO: {c.end:.3f} > {duration:.3f}')
        out.append(c)
    out.sort(key=lambda c:(c.start,c.end))
    unique=[]
    for c in out:
        if unique and c.text==unique[-1].text and c.speaker==unique[-1].speaker and c.start<unique[-1].end:
            p=unique.pop();unique.append(Cue(p.start,max(p.end,c.end),p.text,p.speaker));notes.append({'type':'duplicate_cue_merged','text':c.text});continue
        if unique and c.start<unique[-1].end-1e-8:
            raise TimingError(f'OVERLAPPING_DIALOGUE: {unique[-1].start:.3f}-{unique[-1].end:.3f} / {c.start:.3f}-{c.end:.3f}')
        unique.append(c)
        cps=len(c.text)/c.duration
        if cps>25: notes.append({'type':'fast_reading','start':c.start,'characters_per_second':round(cps,1)})
    return unique,notes

# Alias avoids accidentally accepting an overlap as an ordinary parsing issue.
from .common import TimingError

def parse_srt(path:Path)->list[Cue]:
    text=path.read_text(encoding='utf-8-sig')
    cues=[]
    def time(s):
        m=re.fullmatch(r'(\d{1,3}):(\d{2}):(\d{2})[,.](\d{3})',s.strip())
        if not m: raise ConfigError('Bad SRT time: '+s)
        h,mi,se,ms=map(int,m.groups())
        if mi>=60 or se>=60: raise ConfigError('SRT time component out of range')
        return h*3600+mi*60+se+ms/1000
    for block in re.split(r'\n\s*\n',text.replace('\r','').strip()):
        if not block.strip():continue
        lines=block.splitlines(); i=next((i for i,s in enumerate(lines) if '-->' in s),None)
        if i is None: raise ConfigError('SRT block missing timecode')
        left,right=lines[i].split('-->',1)
        cues.append(Cue(time(left),time(right),' '.join(lines[i+1:])))
    return validate(cues)[0]

def write_srt(cues:list[Cue],path:Path):
    def ts(t):
        n=round(t*1000);s,ms=divmod(n,1000);m,s=divmod(s,60);h,m=divmod(m,60)
        return f'{h:02}:{m:02}:{s:02},{ms:03}'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('\n\n'.join(f'{i}\n{ts(c.start)} --> {ts(c.end)}\n{c.text}' for i,c in enumerate(cues,1))+'\n',encoding='utf-8')

def cue_hash(cues)->str:
    return digest([asdict(c) for c in validate(cues)[0]])

def wrap(text:str,font,width:float)->list[str]:
    words=clean_text(text).split();lines=[];cur=''
    for word in words:
        if font.getlength(word)>width:raise NeedsReview('WORD_TOO_WIDE: insert a natural break or change font')
        candidate=f'{cur} {word}'.strip()
        if cur and font.getlength(candidate)>width:lines.append(cur);cur=word
        else:cur=candidate
    if cur:lines.append(cur)
    return lines

def paginate(cues:list[Cue],font,width:float,max_lines=2,min_sec=.45):
    pages=[]
    for c in cues:
        lines=wrap(c.text,font,width);groups=[lines[i:i+max_lines] for i in range(0,len(lines),max_lines)]
        if c.duration/len(groups)<min_sec:raise NeedsReview(f'TEXT_TOO_DENSE at {c.start:.2f}s: {len(groups)} pages / {c.duration:.2f}s')
        weights=[len(' '.join(g)) for g in groups];total=sum(weights);t=c.start
        for idx,(group,weight) in enumerate(zip(groups,weights)):
            end=c.end if idx==len(groups)-1 else t+min_sec+(c.duration-len(groups)*min_sec)*weight/total
            if end-t<min_sec-1e-7:raise NeedsReview('CAPTION_PAGE_TOO_SHORT: revise text or timing')
            pages.append({'start':t,'end':end,'lines':group,'source_start':c.start,'speaker':c.speaker});t=end
    return pages
