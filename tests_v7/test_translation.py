import json
from types import SimpleNamespace as NS
import pytest
from backend.sub_processor import SubtitleSegment
from wuby_studio.translation import parse_translation,translate
from wuby_studio.common import WubyError

def src():return [SubtitleSegment(0,2,'\u4eca\u5929 10'),SubtitleSegment(2,4,'\u54c8\u54c8\u54c8')]
def data():return {'items':[{'id':1,'text':'Hom nay 10','needs_review':False},{'id':2,'text':'Ha ha ha','needs_review':False}]}
def test_valid_and_deliberate_repeats():
    assert parse_translation(json.dumps(data()),src(),[1,2])==['Hom nay 10','Ha ha ha']
@pytest.mark.parametrize('bad',['not json','{}','{"items":[]}'])
def test_bad_response_rejected(bad):
    with pytest.raises(WubyError):parse_translation(bad,src(),[1,2])
@pytest.mark.parametrize('change',['count','order','number','chinese','empty','review','missing_review'])
def test_structural_and_translation_guards(change):
    d=data()
    if change=='count':d['items'].pop()
    if change=='order':d['items'].reverse()
    if change=='number':d['items'][0]['text']='Hom nay 11'
    if change=='chinese':d['items'][0]['text']='\u4eca\u5929 10'
    if change=='empty':d['items'][0]['text']=' '
    if change=='review':d['items'][0]['needs_review']=True
    if change=='missing_review':d['items'][0].pop('needs_review')
    with pytest.raises(WubyError):parse_translation(json.dumps(d),src(),[1,2])

def test_api_failure_no_source_fallback():
    def fail(**kw):raise RuntimeError('API unavailable')
    t=NS(model_name='fake',client=NS(chat=NS(completions=NS(create=fail))))
    with pytest.raises(WubyError,match='no original-text fallback'):translate(t,src())

def test_context_and_json_request():
    calls=[]
    def call(**kw):
        calls.append(kw);return NS(choices=[NS(finish_reason='stop',message=NS(content=json.dumps(data())))])
    t=NS(model_name='fake',client=NS(chat=NS(completions=NS(create=call))))
    r=translate(t,src());assert len(r)==2 and r[1].text=='Ha ha ha'
    assert calls[0]['response_format']=={'type':'json_object'}

def test_rescue_untranslated_and_empty():
    d={'items':[{'id':1,'text':'Hom nay (今天) 10','needs_review':False},{'id':2,'text':'   ','needs_review':False}]}
    parsed = parse_translation(json.dumps(d),src(),[1,2],allow_usable_review=True,rescue_untranslated=True)
    assert parsed[0] == 'Hom nay 10'
    assert parsed[1] == '...'

def test_translate_auto_rescue_on_attempt_2():
    attempts = []
    bad_data = {'items':[{'id':1,'text':'Hom nay 10','needs_review':False},{'id':2,'text':'妈','needs_review':False}]}
    def call(**kw):
        attempts.append(kw)
        return NS(choices=[NS(finish_reason='stop',message=NS(content=json.dumps(bad_data)))])
    t=NS(model_name='fake',client=NS(chat=NS(completions=NS(create=call))))
    r=translate(t,src())
    assert len(r) == 2
    assert r[0].text == 'Hom nay 10'
    assert r[1].text == '...'
    assert len(attempts) == 3

