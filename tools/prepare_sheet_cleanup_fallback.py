"""Build an owner-run Apps Script with embedded CSV, without any credentials."""
import csv,json
from pathlib import Path

ROOT=Path(r'D:/0.1_FACE_BOOK/Lay video tiktok')
OUT=ROOT/'handoff'/'sheet_cleanup_20261017'
OUT.mkdir(parents=True,exist_ok=True)
rows=list(csv.reader((ROOT/'DANH_SACH_KENH_DOUYIN_INPUT_OUTPUT.csv').open(encoding='utf-8-sig',newline='')))
channels=json.loads(Path(r'D:\0.1_FACE_BOOK\fanpage-control-center-v2.0\config\channels.json').read_text(encoding='utf-8-sig'))
paths={Path(c['workspace_root']).name:(Path(c['workspace_root'])/'02_MOI_RENDER_CHO_XAC_NHAN').as_posix() for c in channels}
for row in rows[1:]:
    if row[1] in paths: row[6]=paths[row[1]]
assert all(len(r)==16 for r in rows)
with (OUT/'DANH_SACH_KENH_DOUYIN_FACEBOOK.csv').open('w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(rows)
data=json.dumps(rows,ensure_ascii=False)
script=r'''/** Run cleanupVideoAiSheet as the spreadsheet owner. No credentials are embedded. */
function cleanupVideoAiSheet() {
  const expectedOwner = 'giakhanh299@gmail.com';
  const user = Session.getEffectiveUser().getEmail();
  if (user !== expectedOwner) throw new Error('Run as '+expectedOwner+'; current user: '+user);
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const id = '13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs';
    const ss = SpreadsheetApp.openById(id);
    const remove = {1519295225:'PRODUCTION_VIDEO_TRACKER_2026',1554596489:'DASHBOARD_100',22194298:'VIDEO_MASTER',1828709799:'POST_QUEUE',865282845:'DAILY_METRICS',624388118:'KENH_NHAN_VAT',1279459694:'queue'};
    const keep = {1668396242:'TIKTOK_RENDER_QUEUE',1278860948:'TIKTOK_CAUHINH_VA_BAO_LOI',1171596520:'CHANNEL_MASTER',945097150:'VOICE_PROFILES',2069274851:'QUAN_LY_DANG_BAI'};
    const byId = Object.fromEntries(ss.getSheets().map(s=>[s.getSheetId(),s]));
    for (const [sid,name] of Object.entries(keep)) if (!byId[sid] || byId[sid].getName()!==name) throw new Error('Keep tab mismatch: '+name);
    for (const [sid,name] of Object.entries(remove)) if (byId[sid] && byId[sid].getName()!==name) throw new Error('Delete ID/name mismatch: '+name);
    const data = __DATA__;
    const title = 'DANH_SACH_KENH_DOUYIN';
    let sheet = ss.getSheetByName(title);
    if (sheet && sheet.getLastRow()>0) {
      const existing=sheet.getDataRange().getDisplayValues();
      if (JSON.stringify(existing)!==JSON.stringify(data)) throw new Error('Destination already contains different data; no changes made.');
    }
    const backup=DriveApp.getFileById(id).makeCopy(ss.getName()+' - BACKUP '+Utilities.formatDate(new Date(),'Asia/Bangkok','yyyyMMdd_HHmmss'));
    console.log('Backup: '+backup.getUrl());
    if (!sheet) sheet=ss.insertSheet(title);
    if (sheet.getMaxColumns()<16) sheet.insertColumnsAfter(sheet.getMaxColumns(),16-sheet.getMaxColumns());
    const range=sheet.getRange(1,1,data.length,16);
    range.setNumberFormat('@').setValues(data).setWrap(true).setVerticalAlignment('top').setFontFamily('Arial').setFontSize(10);
    sheet.getRange(1,1,1,16).setBackground('#1f4061').setFontColor('#ffffff').setFontWeight('bold');
    sheet.setFrozenRows(1);sheet.setFrozenColumns(3);sheet.setColumnWidths(1,16,230);sheet.setColumnWidth(1,55);
    if(!sheet.getFilter()) range.createFilter();
    sheet.autoResizeRows(1,data.length);
    SpreadsheetApp.flush();
    if(JSON.stringify(range.getDisplayValues())!==JSON.stringify(data)) throw new Error('Import verification failed; old tabs kept.');
    for(const sid of Object.keys(remove)) if(byId[sid]) ss.deleteSheet(byId[sid]);
    SpreadsheetApp.flush();
    const final=Object.fromEntries(ss.getSheets().map(s=>[s.getSheetId(),s.getName()]));
    for(const [sid,name] of Object.entries(keep)) if(final[sid]!==name) throw new Error('Keep verification failed');
    for(const sid of Object.keys(remove)) if(final[sid]) throw new Error('Delete verification failed');
    console.log('DONE: '+(data.length-1)+' rows, 16 columns. '+ss.getUrl()+'#gid='+sheet.getSheetId());
  } finally {lock.releaseLock();}
}
'''.replace('__DATA__',data)
(OUT/'DON_DEP_VIDEO_AI.gs').write_text(script,encoding='utf-8')
(OUT/'HUONG_DAN.txt').write_text('API service account và OAuth hiện có đều trả 403 khi tạo tab. Chưa thay đổi Google Sheet.\n\n1. Mở đúng spreadsheet bằng tài khoản giakhanh299@gmail.com.\n2. Extensions > Apps Script.\n3. Dán toàn bộ DON_DEP_VIDEO_AI.gs, lưu và chạy cleanupVideoAiSheet.\n4. Tự cấp quyền Google khi được hỏi. Script sao lưu toàn bộ spreadsheet trước khi nhập bảng và xóa đúng 7 tab.\n\nDữ liệu đã nhúng sẵn, gồm 8 kênh và 1 dòng Telegram quản trị. Cột đầu ra của 8 kênh dùng D:/0.1_FACE_BOOK/videos_upload/<kênh>/02_MOI_RENDER_CHO_XAC_NHAN. Không tự đăng bài.\n',encoding='utf-8')
print(str(OUT))
