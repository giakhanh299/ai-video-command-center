import sys, os, time, requests
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path('D:/0.1_FACE_BOOK/Lay video tiktok')
OUT_C1 = BASE_DIR / 'workspace' / 'video_cauhinh1_wuby_hybrid.mp4'
OUT_C2 = BASE_DIR / 'workspace' / 'video_cauhinh2_blackbar.mp4'

BOT_TOKEN = '8531992939:AAFJmsTA0752eu96oHBa84MfZkjbejKxCe0'
CHAT_ID = '-1004462729383'

# 1. Gửi video lên Telegram
items = [
    {
        'file': OUT_C1,
        'title': 'CẤU HÌNH 1 (WUBY ANIME - ĐÃ FIX AUDIO TIẾNG TRUNG)',
        'caption': (
            '🎬 <b>[ĐÃ FIX AUDIO] CẤU HÌNH 1: WUBY ANIME</b>\n\n'
            '✅ <b>Khắc phục triệt để lỗi tiếng Trung:</b>\n'
            '• <b>Loại bỏ 100% audio tiếng Trung gốc:</b> Không còn trộn âm gốc, giọng Trung hoàn toàn biến mất.\n'
            '• <b>Chỉ phát giọng thuyết minh Wuby clone:</b> Âm thanh trong trẻo, tự nhiên, chuẩn EBU R128 True Peak limiter.\n'
            '• <b>Hình ảnh & Subtitle:</b> Đã xóa sạch cột chữ dọc bên trái, chữ sub Việt căn chỉnh mượt mà.'
        )
    },
    {
        'file': OUT_C2,
        'title': 'CẤU HÌNH 2 (REVIEW PHIM - ĐÃ FIX AUDIO TIẾNG TRUNG)',
        'caption': (
            '🎬 <b>[ĐÃ FIX AUDIO] CẤU HÌNH 2: REVIEW PHIM ĐIỆN ẢNH</b>\n\n'
            '✅ <b>Khắc phục triệt để lỗi tiếng Trung:</b>\n'
            '• <b>Tắt triệt để âm thanh gốc:</b> Không còn tiếng Trung của nhân vật/người dẫn gốc.\n'
            '• <b>Chỉ phát giọng đọc Nữ trầm ấm:</b> Giọng thuyết minh chuẩn, rõ ràng, không clipping.\n'
            '• <b>Hình ảnh & Dải đen:</b> Dải đen ôm sát chữ Trung gốc (bot_h=744px), Title điện ảnh fade out đúng 6s.'
        )
    }
]

for item in items:
    fpath = item['file']
    print(f"Đang gửi {item['title']} ({os.path.getsize(fpath)/(1024*1024):.2f} MB)...")
    with open(fpath, 'rb') as vf:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
            data={
                'chat_id': CHAT_ID,
                'caption': item['caption'],
                'parse_mode': 'HTML',
                'supports_streaming': True
            },
            files={'video': (fpath.name, vf, 'video/mp4')},
            timeout=180
        ).json()
    print(f"  -> Telegram API response: ok={resp.get('ok')}")

# 2. Cập nhật Google Sheet (Chỉ cột I, J, K dòng 16 & 17)
creds = service_account.Credentials.from_service_account_file(
    r'D:/02_CONG_CU/youtube-reup-pipeline\secrets\sheet_service_account.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)
service = build('sheets', 'v4', credentials=creds)
sheet_id = '13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs'

now_str = time.strftime('%Y-%m-%d %H:%M')
updates = [
    {
        'range': 'TIKTOK_CAUHINH_VA_BAO_LOI!I16:K16',
        'values': [[
            '🟢 Đã fix xong',
            'Đã tách và loại bỏ 100% audio tiếng Trung gốc; sử dụng độc quyền track thuyết minh Wuby clone chuẩn qua bộ lọc EBU R128 True Peak limiter, âm thanh trong trẻo không còn tiếng Trung lọt vào.',
            now_str
        ]]
    },
    {
        'range': 'TIKTOK_CAUHINH_VA_BAO_LOI!I17:K17',
        'values': [[
            '🟢 Đã fix xong',
            'Đã tắt keep_bg_audio=False và bg_volume=0.0; triệt tiêu hoàn toàn âm thanh gốc của nhân vật Trung Quốc, chỉ phát giọng thuyết minh Nữ trầm ấm chuẩn qua bộ lọc EBU R128.',
            now_str
        ]]
    }
]

for u in updates:
    res = service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=u['range'],
        valueInputOption='USER_ENTERED',
        body={'values': u['values']}
    ).execute()
    print(f"Updated {u['range']}: updatedCells={res.get('updatedCells')}")

print('ALL DONE SUCCESSFULLY!')
