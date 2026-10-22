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

res = requests.get(
    f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}",
    headers=headers,
).json()

print("Spreadsheet Title:", res.get("properties", {}).get("title"))
sheets = res.get("sheets", [])
print(f"Total Sheets: {len(sheets)}")
for s in sheets:
    p = s["properties"]
    print(f"ID: {p['sheetId']} | Title: {p['title']}")
