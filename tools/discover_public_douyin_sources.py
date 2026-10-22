"""Verify public source identities and recent posts using existing provider access."""
import datetime,json,sys,time
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,r'D:\0.1_FACE_BOOK\fanpage-control-center-v2.0')
from autopilot.douyin_feed_provider import load_provider_token,fetch_author_page
from autopilot.douyin_scanner import filter_lookback_72h

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    candidates=[
        {'channel':'KENH_001','name':'大睿投资观','sec_user_id':'MS4wLjABAAAAK3iTPS2k6sCzf_VpGBcDY795rLef76Yt51FFGNhGvY8','evidence_url':'https://www.douyin.com/user/MS4wLjABAAAAK3iTPS2k6sCzf_VpGBcDY795rLef76Yt51FFGNhGvY8'},
        {'channel':'KENH_003','sample_video_id':'7568332009655815443','evidence_url':'https://jingxuan.douyin.com/m/video/7568332009655815443'},
        {'channel':'KENH_004','sample_video_id':'7621166123672718643','evidence_url':'https://www.douyin.com/video/7621166123672718643'}
    ]
    token=load_provider_token();out=[]
    for source in candidates:
        if source.get('sample_video_id'):
            res=requests.get('https://api.tikhub.io/api/v1/douyin/web/fetch_one_video',params={'aweme_id':source['sample_video_id']},headers={'Authorization':'Bearer '+token},timeout=(10,30))
            if res.status_code!=200:
                out.append({**source,'status':'DETAIL_HTTP_'+str(res.status_code)});continue
            data=res.json().get('data',{}).get('aweme_detail',{})
            author=data.get('author',{})
            if str(data.get('aweme_id'))!=source['sample_video_id'] or not author.get('sec_uid'):
                out.append({**source,'status':'DETAIL_BINDING_INVALID'});continue
            source.update(name=author.get('nickname'),sec_user_id=author['sec_uid'],sample_description=data.get('desc',''))
        source['url']='https://www.douyin.com/user/'+source['sec_user_id']
        page=fetch_author_page({'id':'discovery_'+source['channel'],'sec_user_id':source['sec_user_id'],'verification_status':'AUTHOR_URL_RESOLVED_FEED_NOT_CONNECTED'})
        source['status']=page['status']
        filtered=filter_lookback_72h(page.get('items',[]),reference_time_epoch=time.time())
        source['recent_items']=sorted(filtered['eligible'],key=lambda i:i['timestamp_epoch'],reverse=True)[:3]
        source['expired_count']=len(filtered['expired'])
        source['verified_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        out.append(source)
    path=ROOT/'outputs/douyin_intake/public_source_discovery.json'
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
