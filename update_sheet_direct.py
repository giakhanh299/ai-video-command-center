import sys
sys.stdout.reconfigure(encoding='utf-8')
import gspread
import time
from oauth2client.service_account import ServiceAccountCredentials

SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('D:/02_CONG_CU/youtube-reup-pipeline/secrets/sheet_service_account.json', SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key('13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs')
ws = sheet.worksheet('TIKTOK_CAUHINH_VA_BAO_LOI')

now_str = time.strftime('%Y-%m-%d %H:%M')

updates = [
    {
        'row': 12,
        'status': '🟢 Đã fix xong',
        'solution': 'Đã thêm detect_vertical_left_watermark xóa sạch cột chữ Trung dọc bên trái; sửa dính từ tại 01:06 và chỉnh câu dịch tại 01:52 mượt mà trong SRT; thêm alimiter 0.92 chống clipping.',
        'completed': now_str
    },
    {
        'row': 13,
        'status': '🟢 Đã fix xong',
        'solution': 'Đã tắt persistent_on_top_bar (Title chỉ hiện 6.0s rồi fade out); dải đen đáy tự động mở rộng bao trọn chữ Trung gốc (bot_h=744px), triệt tiêu hoàn toàn 2 lớp subtitle; thêm alimiter 0.92.',
        'completed': now_str
    },
    {
        'row': 14,
        'status': '🟢 Đã fix xong',
        'solution': 'Mở rộng quét subtitle 45%..90% chiều cao và phân cụm CenterY=1276px; hộp đen chữ nhật ôm khít cụm chữ Trung (+3% trên/dưới), sub Việt đè chính xác lên cụm chữ cũ.',
        'completed': now_str
    },
    {
        'row': 15,
        'status': '🟢 Đã fix xong',
        'solution': 'Bắt chính xác tọa độ CenterY=1276px (+3% trên/dưới); áp dụng hiệu ứng kính mờ frosted glass (gblur sigma=12 + phủ tối 58% + viền kính mỏng 1px); sub Việt lồng chuẩn tâm.',
        'completed': now_str
    }
]

for u in updates:
    r = u['row']
    ws.update(f'H{r}:J{r}', [[u['status'], u['solution'], u['completed']]])
    print(f"Done update row {r}: H={u['status']}, J={u['completed']}")

print("ALL ROWS UPDATED IN GOOGLE SHEET!")
