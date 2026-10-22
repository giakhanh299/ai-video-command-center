"""Offline verification. This file never uploads or publishes anything."""
import ast,csv,importlib.util,json,sys,shutil
from pathlib import Path
from unittest.mock import Mock

ROOT=Path(r'D:/0.1_FACE_BOOK/Lay video tiktok')
FB=Path(r'D:\0.1_FACE_BOOK\fanpage-control-center-v2.0')
sys.path.insert(0,str(ROOT/'tools'))
from channel_output_paths import channel_review_path
config=json.loads((ROOT/'backend/channels_config.json').read_text(encoding='utf-8-sig'))
rows=list(csv.reader((ROOT/'handoff/sheet_cleanup_20261017/DANH_SACH_KENH_DOUYIN_FACEBOOK.csv').open(encoding='utf-8-sig',newline='')))
assert len(rows)==10 and all(len(r)==16 for r in rows)
for row in rows[1:]:
 if row[1].startswith('KENH_'):
  assert channel_review_path(ROOT,row[1],config['channels'][row[1]],'')==row[6]
  assert Path(row[6]).is_dir()
sys.path.insert(0,str(FB))
from autopilot.sheet_sync import SheetSynchronizer,SHEETS
assert SHEETS==['CHANNEL_MASTER']
db=Mock();db.list_channels.return_value=[]
system=Mock();system.sheet_sync_enabled=True;system.spreadsheet_id='test'
sync=SheetSynchronizer(db,system)
service=Mock();service.spreadsheets().get().execute.return_value={'sheets':[]}
sync._service=Mock(return_value=service);sync._replace=Mock()
assert sync.sync()=={'channels':0}
assert sync._replace.call_args.args[1]=='CHANNEL_MASTER'
db.list_media.assert_not_called();db.list_posts.assert_not_called();db.list_metrics.assert_not_called()
created=service.spreadsheets().batchUpdate.call_args.kwargs['body']['requests']
assert [r['addSheet']['properties']['title'] for r in created]==['CHANNEL_MASTER']
out=sorted((ROOT/'backups').glob('youtube_publishing_removed_*'))[-1]
manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
for p in manifest['deleted']: assert not Path(p).exists()
for p in manifest['changed']:
 if p.endswith('.py'): ast.parse(Path(p).read_text(encoding='utf-8-sig'))
targets={r'D:/02_CONG_CU/youtube-reup-pipeline\integrations\youtube\youtube_api_uploader.py':{'upload','_upload_once'},r'D:/02_CONG_CU/youtube-reup-pipeline\services\intelligent_publisher.py':{'publish_private_videos'},r'D:/02_CONG_CU/youtube-Thread\services\youtube_uploader.py':{'upload_video'},r'D:/02_CONG_CU/youtube-token-tool\src\utils\youtube_uploader.py':{'upload_video','do_youtube_upload'}}
for p,names in targets.items():
 tree=ast.parse(Path(p).read_text(encoding='utf-8-sig'))
 for node in ast.walk(tree):
  if isinstance(node,ast.FunctionDef) and node.name in names:
   assert len(node.body)==1 and isinstance(node.body[0],ast.Raise)
for file in ('channel_output_paths.py','push_channels_to_sheet.py','export_channels_sheet.py'):
 ast.parse((ROOT/'tools'/file).read_text(encoding='utf-8-sig'))
source=ROOT/'DANH_SACH_KENH_DOUYIN_INPUT_OUTPUT.csv'
shutil.copy2(source,out/source.name)
shutil.copy2(ROOT/'handoff/sheet_cleanup_20261017/DANH_SACH_KENH_DOUYIN_FACEBOOK.csv',source)
report={'result':'PASS','channel_paths_verified':8,'csv_data_rows':9,'csv_columns':16,'youtube_entry_scripts_removed':len(manifest['deleted']),'youtube_upload_functions_cannot_publish':True,'sheet_sync_only_channel_master':True,'google_sheet_status':'UNCHANGED: both supplied credentials return 403 on addSheet','owner_script':str(ROOT/'handoff/sheet_cleanup_20261017/DON_DEP_VIDEO_AI.gs')}
(ROOT/'handoff/sheet_cleanup_20261017/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
