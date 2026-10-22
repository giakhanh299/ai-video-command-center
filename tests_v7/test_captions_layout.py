import json,math
import pytest
from wuby_studio.captions import Cue,validate,parse_srt,write_srt,wrap,paginate
from wuby_studio.config import validate as validate_config,merge
from wuby_studio.renderer import load_font,make_ass,graphics,pixel_rect,crop_rect
from wuby_studio.common import ConfigError,TimingError,NeedsReview

def test_duplicates_merge_but_deliberate_repeat_kept():
    c=[Cue(0,1,'ha ha ha'),Cue(.2,1.2,'ha ha ha'),Cue(1.2,2,'ha ha ha')]
    v,notes=validate(c);assert len(v)==2 and v[0].end==1.2 and v[1].text=='ha ha ha';assert notes

@pytest.mark.parametrize('b',[.5,.999,0.9999])
def test_overlapping_different_dialogue_fails(b):
    with pytest.raises(TimingError):validate([Cue(0,1,'A'),Cue(b,2,'B')])

@pytest.mark.parametrize('start,end',[(1,1),(-1,1),(0,float('inf')),(float('nan'),1)])
def test_invalid_cue(start,end):
    with pytest.raises(ConfigError):validate([Cue(start,end,'Hi')])

def test_srt_roundtrip_with_utf8(tmp_path):
    p=tmp_path/'test.srt';c=[Cue(0,1.234,'D\u1ec5 th\u01b0\u01a1ng qu\u00e1!')];write_srt(c,p)
    assert parse_srt(p)==c

def test_srt_past_video():
    with pytest.raises(TimingError):validate([Cue(0,4,'x')],3)

def test_unicode_wrap_measured_no_overflow(cfg):
    font,_=load_font(cfg,25);text='H\u00f4m nay em r\u1ea5t vui, ng\u00e0y mai c\u0169ng v\u1eady!'
    lines=wrap(text,font,200);assert len(lines)>1
    assert all(font.getlength(l)<=200 for l in lines)

def test_no_ass_tag_injection(tmp_path,cfg):
    cues=[Cue(0,2,r'{\pos(0,0)} Hi')]
    p,pages,font=make_ass(cues,cfg,tmp_path);text=p.read_text(encoding='utf-8')
    assert r'{\pos(0,0)}' not in text
    assert text.count('Dialogue: 1,')==1

def test_dense_caption_not_silent_crop(tmp_path,cfg):
    with pytest.raises(NeedsReview):make_ass([Cue(0,.5,'this is a long sentence that requires many pages of large readable words')],cfg,tmp_path)

def test_title_overflow_fails(tmp_path,cfg):
    with pytest.raises(NeedsReview):graphics(cfg,'a lot of long title words '*10,tmp_path)

@pytest.mark.parametrize('theme',['peach','mint','lavender'])
def test_theme_renders_png(tmp_path,cfg,theme):
    cfg['theme']=theme;graphics(cfg,'Xin ch\u00e0o',tmp_path)
    assert (tmp_path/'background.png').stat().st_size>100

def test_layout_collision_cannot_save(cfg):
    cfg['layout']['logo']=cfg['layout']['subtitle']
    with pytest.raises(ConfigError,match='COLLISION'):validate_config(cfg)

@pytest.mark.parametrize('field,value',[('opacity',1.1),('opacity',float('nan')),('cycle_sec',0),('drift_ratio',.5)])
def test_invalid_logo_setting(cfg,field,value):
    cfg['logo'][field]=value
    with pytest.raises(ConfigError):validate_config(cfg)

def test_bad_crop_rejected():
    meta={'video':{'width':1080,'height':1920}}
    with pytest.raises(ConfigError):crop_rect({'crop':[0,.8,1,.5]},meta)

def test_repeated_pages_have_exclusive_time(cfg,tmp_path):
    p,pages,_=make_ass([Cue(0,4,'Small choices make a kind and happy day for everyone')],cfg,tmp_path)
    assert all(a['end']<=b['start'] for a,b in zip(pages,pages[1:]))


def test_short_tail_page_keeps_minimum_reading_time(cfg):
    font,_=load_font(cfg,25)
    text='one two three four five six seven eight nine ten small tail'
    pages=paginate([Cue(0,3,text)],font,160,max_lines=2,min_sec=.45)
    assert len(pages)>1
    assert all(p['end']-p['start']>=.45-1e-7 for p in pages)
    assert pages[-1]['end']==3
    assert ' '.join(line for p in pages for line in p['lines'])==text


def test_dragged_title_stays_in_its_horizontal_region(tmp_path,cfg):
    from PIL import Image
    cfg['layout']['title']=[.04,.07,.55,.13]
    graphics(cfg,'Hi',tmp_path)
    box=Image.open(tmp_path/'title.png').getbbox()
    x,y,w,h=pixel_rect(cfg,'title')
    assert box is not None and x<=box[0]<box[2]<=x+w
    assert abs((box[0]+box[2])/2-(x+w/2))<3


def test_other_channel_never_borrows_wuby_logo(tmp_path):
    from wuby_studio.config import from_channel
    cfg=from_channel({'_channel_key':'wuby_second','workflow':'wuby'},tmp_path)
    assert cfg['logo']['path']==str(tmp_path/'channel_assets/wuby_second/logo.png')

def test_resolve_overlapping_segments_fixes_overlapping_dialogue():
    from backend.sub_processor import SubtitleSegment, resolve_overlapping_segments
    segs = [
        SubtitleSegment(33.850, 37.850, 'Câu thoại thứ nhất'),
        SubtitleSegment(37.610, 40.650, 'Câu thoại thứ hai')
    ]
    resolved = resolve_overlapping_segments(segs)
    assert len(resolved) == 2
    assert resolved[0].end <= resolved[1].start
    v, _ = validate(resolved)
    assert len(v) == 2

