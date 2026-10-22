import json
import requests
from pathlib import Path

TOKEN_PATH = Path("gdrive_token.json")
token_data = json.load(open(TOKEN_PATH, encoding="utf-8"))

r = requests.post(
    "https://oauth2.googleapis.com/token",
    data={
        "client_id": token_data["client_id"],
        "client_secret": token_data["client_secret"],
        "refresh_token": token_data["refresh_token"],
        "grant_type": "refresh_token",
    },
).json()

access_token = r.get("access_token")
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}

SPREADSHEET_ID = "13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs"

# Thử đổi tên tab 'queue' (ID: 1279459694) thành 'DANH_SACH_KENH_DOUYIN'
body = {
    "requests": [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": 1279459694,
                    "title": "DANH_SACH_KENH_DOUYIN",
                },
                "fields": "title",
            }
        }
    ]
}

res = requests.post(
    f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}:batchUpdate",
    headers=headers,
    json=body,
)

print("Status:", res.status_code)
print("Response:", res.text)
