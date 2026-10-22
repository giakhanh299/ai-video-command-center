"""Inspect/apply the explicitly requested Google Sheets cleanup. Never print credentials."""
import argparse, csv, datetime, json
from pathlib import Path
from urllib.parse import quote
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

ROOT = Path(r'D:/0.1_FACE_BOOK/Lay video tiktok')
SID = '13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs'
BASE = f'https://sheets.googleapis.com/v4/spreadsheets/{SID}'
DELETE = {1519295225:'PRODUCTION_VIDEO_TRACKER_2026',1554596489:'DASHBOARD_100',22194298:'VIDEO_MASTER',1828709799:'POST_QUEUE',865282845:'DAILY_METRICS',624388118:'KENH_NHAN_VAT',1279459694:'queue'}
KEEP = {1668396242:'TIKTOK_RENDER_QUEUE',1278860948:'TIKTOK_CAUHINH_VA_BAO_LOI',1171596520:'CHANNEL_MASTER',945097150:'VOICE_PROFILES',2069274851:'QUAN_LY_DANG_BAI'}
TAB = 'DANH_SACH_KENH_DOUYIN'

def session(auth):
    if auth == 'service':
        c=service_account.Credentials.from_service_account_file(r'D:/02_CONG_CU/youtube-reup-pipeline\secrets\sheet_service_account.json',scopes=['https://www.googleapis.com/auth/spreadsheets'])
        c.refresh(Request()); token=c.token
    else:
        d=json.loads((ROOT/'gdrive_token.json').read_text(encoding='utf-8'))
        r=requests.post('https://oauth2.googleapis.com/token',data={k:d[k] for k in ('client_id','client_secret','refresh_token')} | {'grant_type':'refresh_token'},timeout=60)
        if not r.ok: raise RuntimeError(f'OAuth refresh failed: HTTP {r.status_code}')
        token=r.json()['access_token']
    s=requests.Session();s.headers.update({'Authorization':'Bearer '+token}); return s

def api(s, method, suffix='', **kwargs):
    r=s.request(method,BASE+suffix,timeout=120,**kwargs)
    if not r.ok:
        try: message=r.json().get('error',{}).get('message','')
        except ValueError: message=''
        raise RuntimeError(f'Google Sheets HTTP {r.status_code}: {message}')
    return r.json()

def main():
    p=argparse.ArgumentParser();p.add_argument('--auth',choices=['service','oauth'],default='service');p.add_argument('--apply',action='store_true');a=p.parse_args()
    s=session(a.auth); meta=api(s,'GET',params={'fields':'spreadsheetId,properties,sheets.properties'})
    print(json.dumps({'title':meta['properties']['title'],'sheets':[x['properties'] for x in meta['sheets']]},ensure_ascii=False))
    rows=list(csv.reader((ROOT/'DANH_SACH_KENH_DOUYIN_INPUT_OUTPUT.csv').open(encoding='utf-8-sig',newline='')))
    assert len(rows)>1 and all(len(r)==16 for r in rows),'CSV must have 16 columns'
    fb=json.loads(Path(r'D:\0.1_FACE_BOOK\fanpage-control-center-v2.0\config\channels.json').read_text(encoding='utf-8-sig'))
    destinations={Path(c['workspace_root']).name:Path(c['workspace_root'])/'02_MOI_RENDER_CHO_XAC_NHAN' for c in fb}
    for row in rows[1:]:
        if row[1].startswith('KENH_'):
            assert row[1] in destinations, 'Missing Facebook channel: '+row[1]
            assert destinations[row[1]].is_dir(),'Missing review directory'
            row[6]=destinations[row[1]].as_posix()
    sheets={x['properties']['sheetId']:x['properties'] for x in meta['sheets']}
    for i,name in KEEP.items(): assert sheets.get(i,{}).get('title')==name,f'Required tab mismatch: {name}'
    for i,name in DELETE.items():
        if i in sheets: assert sheets[i]['title']==name,f'Deletion ID/name mismatch: {i}'
    if not a.apply: return
    out=ROOT/'backups'/('sheet_cleanup_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));out.mkdir(parents=True,exist_ok=False)
    backup=api(s,'GET',params={'includeGridData':'true'})
    (out/'spreadsheet_before.json').write_text(json.dumps(backup,ensure_ascii=False),encoding='utf-8')
    with (out/'imported_channels.csv').open('w',encoding='utf-8-sig',newline='') as f:
        csv.writer(f).writerows(rows)
    existing=next((p for p in sheets.values() if p['title']==TAB),None)
    if existing:
        old=api(s,'GET','/values/'+quote("'"+TAB+"'",safe='')).get('values',[])
        normalized=[[str(v) for v in r]+['']*(16-len(r)) for r in old]
        assert not old or normalized==rows,'Existing destination differs; refusing to overwrite'
        tid=existing['sheetId']
    else:
        res=api(s,'POST',':batchUpdate',json={'requests':[{'addSheet':{'properties':{'title':TAB,'gridProperties':{'rowCount':max(100,len(rows)),'columnCount':16,'frozenRowCount':1,'frozenColumnCount':3}}}}]})
        tid=res['replies'][0]['addSheet']['properties']['sheetId']
    target=quote(f"'{TAB}'!A1:P{len(rows)}",safe='')
    api(s,'PUT','/values/'+target,params={'valueInputOption':'RAW'},json={'values':rows})
    actual=api(s,'GET','/values/'+target).get('values',[])
    assert [[str(v) for v in r]+['']*(16-len(r)) for r in actual]==rows,'Imported cells differ from CSV'
    rg={'sheetId':tid,'startRowIndex':0,'endRowIndex':len(rows),'startColumnIndex':0,'endColumnIndex':16}
    requests_=[{'repeatCell':{'range':rg,'cell':{'userEnteredFormat':{'wrapStrategy':'WRAP','verticalAlignment':'TOP','textFormat':{'fontFamily':'Arial','fontSize':10}}},'fields':'userEnteredFormat'}}, {'repeatCell':{'range':dict(rg,endRowIndex=1),'cell':{'userEnteredFormat':{'backgroundColor':{'red':0.12,'green':0.25,'blue':0.38},'textFormat':{'bold':True,'foregroundColor':{'red':1,'green':1,'blue':1}}}},'fields':'userEnteredFormat.backgroundColor,userEnteredFormat.textFormat'}}, {'setBasicFilter':{'filter':{'range':rg}}}, {'updateDimensionProperties':{'range':{'sheetId':tid,'dimension':'COLUMNS','startIndex':0,'endIndex':16},'properties':{'pixelSize':230},'fields':'pixelSize'}}, {'updateDimensionProperties':{'range':{'sheetId':tid,'dimension':'COLUMNS','startIndex':0,'endIndex':1},'properties':{'pixelSize':55},'fields':'pixelSize'}}, {'autoResizeDimensions':{'dimensions':{'sheetId':tid,'dimension':'ROWS','startIndex':0,'endIndex':len(rows)}}}]
    api(s,'POST',':batchUpdate',json={'requests':requests_})
    to_delete=[{'deleteSheet':{'sheetId':i}} for i in DELETE if i in sheets]
    if to_delete: api(s,'POST',':batchUpdate',json={'requests':to_delete})
    after=api(s,'GET',params={'fields':'spreadsheetId,properties.title,sheets.properties'})
    remaining={x['properties']['sheetId']:x['properties']['title'] for x in after['sheets']}
    assert not set(DELETE)&set(remaining)
    assert all(remaining.get(i)==name for i,name in KEEP.items())
    assert set(sheets)-set(DELETE) <= set(remaining),'Unrequested tab removed'
    report={'auth':a.auth,'backup':str(out),'new_sheet_id':tid,'data_rows':len(rows)-1,'columns':16,'deleted':[DELETE[i] for i in DELETE if i in sheets],'remaining':remaining}
    (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('RESULT '+json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
