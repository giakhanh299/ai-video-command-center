// Run deleteUnusedYouTubeTabs as the spreadsheet owner in script.google.com.
// Makes a full Drive copy first; removes only the seven authorized ID/name pairs.
function deleteUnusedYouTubeTabs() {
  const id = '13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs';
  const targets = {
    1519295225: 'PRODUCTION_VIDEO_TRACKER_2026',
    1554596489: 'DASHBOARD_100', 22194298: 'VIDEO_MASTER',
    1828709799: 'POST_QUEUE', 865282845: 'DAILY_METRICS',
    624388118: 'KENH_NHAN_VAT', 1279459694: 'queue'
  };
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const book = SpreadsheetApp.openById(id);
    const before = book.getSheets();
    const remove = before.filter(s => Object.hasOwnProperty.call(targets, s.getSheetId()));
    remove.forEach(s => {
      if (targets[s.getSheetId()] !== s.getName()) throw new Error('ID/title mismatch');
    });
    if (!remove.length) { console.log('No authorized unused tabs remain'); return; }
    const backup = DriveApp.getFileById(id).makeCopy('TAO VIDEO UPLOAD backup ' + new Date().toISOString());
    console.log('Backup: ' + backup.getUrl());
    remove.forEach(s => book.deleteSheet(s));
    const after = book.getSheets().map(s => s.getSheetId());
    if (before.filter(s => !Object.hasOwnProperty.call(targets, s.getSheetId()))
      .some(s => !after.includes(s.getSheetId()))) throw new Error('Preservation check failed');
    console.log('Deleted ' + remove.length + ' authorized tabs');
  } finally { lock.releaseLock(); }
}
