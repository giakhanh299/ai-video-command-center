import sys
sys.stdout.reconfigure(encoding='utf-8')
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('D:/02_CONG_CU/youtube-reup-pipeline/secrets/sheet_service_account.json', SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key('13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs')
ws = sheet.worksheet('TIKTOK_CAUHINH_VA_BAO_LOI')
sheet_id = ws.id
print(f"Sheet ID: {sheet_id}")

# 1. Chèn 1 cột mới tại index 6 (Cột G, nằm giữa F và G)
batch_requests = [
    {
        "insertDimension": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": 6,
                "endIndex": 7
            },
            "inheritFromBefore": False
        }
    },
    # 2. Đặt chiều rộng cột G là 190px
    {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": 6,
                "endIndex": 7
            },
            "properties": {
                "pixelSize": 190
            },
            "fields": "pixelSize"
        }
    },
    # 3. Format ô G10: Nền đỏ đậm (#800000 / rgb(0.55, 0.05, 0.05)), chữ trắng đậm căn giữa
    {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 9,
                "endRowIndex": 10,
                "startColumnIndex": 6,
                "endColumnIndex": 7
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": {
                        "red": 0.65,
                        "green": 0.05,
                        "blue": 0.05
                    },
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "WRAP",
                    "textFormat": {
                        "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                        "bold": True,
                        "fontSize": 10
                    }
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)"
        }
    },
    # 4. Data Validation (Dropdown) cho G11:G35
    {
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 10,
                "endRowIndex": 35,
                "startColumnIndex": 6,
                "endColumnIndex": 7
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [
                        {"userEnteredValue": "🟢 Đạt"},
                        {"userEnteredValue": "🔴 Chưa đạt"},
                        {"userEnteredValue": "🟡 Cần chỉnh thêm"},
                        {"userEnteredValue": "⚪ Chưa kiểm tra"}
                    ]
                },
                "showCustomUi": True,
                "strict": False
            }
        }
    },
    # 5. Format căn giữa cho toàn bộ cột G từ dòng 11 đến 35
    {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 10,
                "endRowIndex": 35,
                "startColumnIndex": 6,
                "endColumnIndex": 7
            },
            "cell": {
                "userEnteredFormat": {
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE"
                }
            },
            "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)"
        }
    }
]

res = sheet.batch_update({"requests": batch_requests})
print("Batch update column insert & styling thành công!")

# 6. Ghi nội dung vào cột G
# Ô G10: Tiêu đề
ws.update_acell("G10", "User Kiểm Tra Sau Khi Fix")

# Ô G3 (Phần 1): Ghi Chú Cấu Hình
ws.update_acell("G3", "Ghi Chú")

# Ô G11 (MẪU): 🟢 Đạt
ws.update_acell("G11", "🟢 Đạt")

# Ô G12 đến G15 (4 video vừa fix xong): ⚪ Chưa kiểm tra
for r in range(12, 16):
    ws.update_acell(f"G{r}", "⚪ Chưa kiểm tra")

# Ô G16 đến G31: ⚪ Chưa kiểm tra
for r in range(16, 32):
    ws.update_acell(f"G{r}", "⚪ Chưa kiểm tra")

print("Hoàn tất ghi dữ liệu vào Cột G: 'User Kiểm Tra Sau Khi Fix'!")
