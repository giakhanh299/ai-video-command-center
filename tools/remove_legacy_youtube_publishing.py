"""Remove legacy YouTube publishing code; archive originals and preserve import compatibility."""
import ast,datetime,hashlib,json,zipfile
from pathlib import Path

ROOT=Path(r'D:/0.1_FACE_BOOK/Lay video tiktok')
OUT=ROOT/'backups'/('youtube_publishing_removed_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
OUT.mkdir(parents=True,exist_ok=False)
entries=[
 Path(r'D:/02_CONG_CU/youtube-reup-pipeline')/'scripts'/n for n in
 ('upload_local_folders_to_youtube.py','upload_from_sheet.py','test_youtube_upload.py','run_pending_upload_queue.py','run_daily_upload.py','publish_private_videos.py')
]
entries += [Path(r'D:/02_CONG_CU/youtube-Thread\test_upload.py')]
edits={
 Path(r'D:/02_CONG_CU/youtube-reup-pipeline\integrations\youtube\youtube_api_uploader.py'): {'upload','_upload_once'},
 Path(r'D:/02_CONG_CU/youtube-reup-pipeline\services\intelligent_publisher.py'): {'publish_private_videos'},
 Path(r'D:/02_CONG_CU/youtube-Thread\services\youtube_uploader.py'): {'upload_video'},
 Path(r'D:/02_CONG_CU/youtube-token-tool\src\utils\youtube_uploader.py'): {'upload_video','do_youtube_upload'},
}
batch=Path(r'D:/02_CONG_CU/youtube-token-tool\src\batch_uploader.py')
ui=Path(r'D:\0.1_FACE_BOOK\fanpage-control-center-v2.0\Fanpage-Studio\ui\sheet-views.js')
worker=ui.parent.parent/'worker/api.js'
paths=[p for p in entries if p.is_file()]+list(edits)+[batch,ui,worker]
for path in paths:
 assert path.is_file(),path
 assert any(path.resolve().is_relative_to(Path(r).resolve()) for r in (r'D:/02_CONG_CU/youtube-reup-pipeline',r'D:/02_CONG_CU/youtube-Thread',r'D:/02_CONG_CU/youtube-token-tool',r'D:\0.1_FACE_BOOK')),path
(OUT/'PLAN.md').write_text('Authorized scope: user requested removal of old YouTube publishing only. Archive and remove standalone YouTube upload/publish launchers. Remove upload/publish function bodies, retaining import names that fail explicitly. Preserve rendering and Facebook/TikTok upload implementations. Update local Facebook sheet views for the requested tab cleanup. Rollback: restore original files from originals.zip. No deployment or credentials changes.\n',encoding='utf-8')
with zipfile.ZipFile(OUT/'originals.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
 for p in paths: z.write(p,p.drive.replace(':','')+'/'+p.relative_to(p.anchor).as_posix())
manifest={'deleted':[],'changed':[],'backup':str(OUT)}
for path,names in edits.items():
 text=path.read_text(encoding='utf-8-sig'); lines=text.splitlines(keepends=True)
 tree=ast.parse(text); found=set()
 targets=[]
 for node in ast.walk(tree):
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names:
   found.add(node.name); targets.append(node)
 assert found==names,(path,found,names)
 for node in sorted(targets,key=lambda n:n.lineno,reverse=True):
  start=node.body[0].lineno-1; end=node.end_lineno
  indent=' '*(node.col_offset+4)
  lines[start:end]=[indent+'raise RuntimeError("Legacy YouTube publishing was removed at the owner\'s request; use render output folders.")\n']
 result=''.join(lines);ast.parse(result);path.write_text(result,encoding='utf-8');manifest['changed'].append(str(path))
text=batch.read_text(encoding='utf-8-sig')
text=text.replace('from src.utils.youtube_uploader import do_youtube_upload\n','')
start=text.index('        # 1. Upload YouTube');end=text.index('        # 2. Upload Facebook',start)
text=text[:start]+text[end:];text=text.replace('[2/3]','[1/2]').replace('[3/3]','[2/2]')
ast.parse(text);batch.write_text(text,encoding='utf-8');manifest['changed'].append(str(batch))
for path in entries:
 if path.is_file(): path.unlink();manifest['deleted'].append(str(path))
text=worker.read_text(encoding='utf-8')
text=text.replace("'PRODUCTION_VIDEO_TRACKER_2026'","'CHANNEL_MASTER','DANH_SACH_KENH_DOUYIN'").replace(",'YOUTUBE_DAILY_UPLOADS'",'')
worker.write_text(text,encoding='utf-8');manifest['changed'].append(str(worker))
text=ui.read_text(encoding='utf-8')
text=text.replace("PRODUCTION_VIDEO_TRACKER_2026:{title:'Theo dõi sản xuất',cols:['A','B','C','F','G','H','L','M']}","CHANNEL_MASTER:{title:'Danh sách kênh',cols:['A','B','C','D','E','M','N']},DANH_SACH_KENH_DOUYIN:{title:'Kênh Douyin và thư mục Facebook',cols:['A','B','C','E','F','G','J','K','L','O']}")
text=text.replace(",YOUTUBE_DAILY_UPLOADS:{title:'Đăng YouTube hằng ngày',cols:['B','D','G','H','M','N']}",'')
text=text.replace("let current='QUAN_LY_DANG_BAI'","for(const key of Object.keys(definitions)){data[key] ||= {header:{},rows:[]};}\nlet current='QUAN_LY_DANG_BAI'")
ui.write_text(text,encoding='utf-8');manifest['changed'].append(str(ui))
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
