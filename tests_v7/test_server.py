import json,threading,urllib.request,urllib.error
from pathlib import Path
import pytest
from wuby_studio import server,cli

@pytest.fixture
def web(tmp_path,monkeypatch):
    from wuby_studio.common import ROOT
    import shutil
    (tmp_path/'wuby_studio').mkdir()
    shutil.copytree(ROOT/'wuby_studio/web',tmp_path/'wuby_studio/web')
    monkeypatch.setattr(server,'ROOT',tmp_path);monkeypatch.setattr(cli,'ROOT',tmp_path)
    srv=server.StudioServer(('127.0.0.1',0));t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
    yield srv,f'http://127.0.0.1:{srv.server_address[1]}'
    srv.shutdown();srv.server_close();t.join(timeout=3)

def request(url,data=None,headers=None):
    req=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,headers=headers or {})
    return urllib.request.urlopen(req,timeout=5)

def test_home_and_settings_csrf(web,cfg):
    srv,url=web
    assert b'Wuby Studio' in request(url).read()
    with pytest.raises(urllib.error.HTTPError) as err:request(url+'/api/settings',{'config':cfg},{'Content-Type':'application/json'})
    assert err.value.code==403
    headers={'Content-Type':'application/json','X-Wuby-Token':srv.token}
    assert json.loads(request(url+'/api/settings',{'config':cfg},headers).read())['saved']

def test_dns_rebinding_host_rejected(web):
    _,url=web
    with pytest.raises(urllib.error.HTTPError) as err:request(url,headers={'Host':'evil.example'})
    assert err.value.code==400

def test_path_traversal_blocked(web):
    _,url=web
    with pytest.raises(urllib.error.HTTPError):request(url+'/api/media?kind=job&name=../../secret.wav')

def test_uploaded_srt_and_range_media(web,tmp_path):
    srv,url=web
    path=server.ROOT/'workspace/uploads';path.mkdir(parents=True)
    (path/'test.wav').write_bytes(b'abcdef')
    req=urllib.request.Request(url+'/api/media?kind=upload&name=test.wav',headers={'Range':'bytes=1-3'})
    res=urllib.request.urlopen(req);assert res.status==206 and res.read()==b'bcd'

def test_canvas_offline_ui(web,tmp_path):
    sync_playwright=pytest.importorskip("playwright.sync_api").sync_playwright
    import shutil
    chromium=shutil.which('chromium')
    if not chromium:pytest.skip('Browser not installed; HTTP and native JS tests still available')
    _,url=web
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=chromium,headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1450,'height':1100});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        # Browser policy blocks local HTTP in this runner. Exercise real UI JS offline;
        # HTTP handlers are tested separately above, not reported as browser E2E.
        import re
        html=(server.ROOT/'wuby_studio/web/index.html').read_text()
        html=re.sub(r'<link[^>]+>', '', html);html=re.sub(r'<script src="/app.js"></script>', '', html)
        page.set_content(html)
        page.add_style_tag(content=(server.ROOT/'wuby_studio/web/style.css').read_text())
        seed={'jobs':[],'paused':False,'worker_running':False,'preview':{'state':'idle'},'config':cli.get_config()}
        page.evaluate('s=>{window.fixture=s;window.fetch=async (u,o)=>new Response(JSON.stringify(u.includes("settings")?{saved:true}:window.fixture));}',seed)
        page.add_script_tag(content=(server.ROOT/'wuby_studio/web/app.js').read_text())
        page.wait_for_function("document.querySelector('#advanced').value.length>20")
        page.locator('[data-theme="mint"]').click();page.locator('#save').click()
        page.wait_for_timeout(300)
        assert page.locator('[data-theme="mint"]').get_attribute('class').endswith('active')
        assert not errors
        page.screenshot(path=str(tmp_path/'studio.png'),full_page=True)
        browser.close()
