"""
pull_channels_from_sheet.py
----------------------------
Đọc dữ liệu từ tab "DANH_SACH_KENH_DOUYIN" trên Google Sheet và đồng bộ lại vào:
backend/channels_config.json
- Cập nhật douyin_channel_url cho từng kênh
- Cập nhật trạng thái và ghi chú
"""

import sys
import io
import json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path("D:/0.1_FACE_BOOK/Lay video tiktok")
CREDS_FILE = Path(r"D:/02_CONG_CU/youtube-reup-pipeline\secrets\sheet_service_account.json")
SPREADSHEET_ID = "13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs"
TAB_NAME = "DANH_SACH_KENH_DOUYIN"


def main():
    if not CREDS_FILE.exists():
        print(f"[PullChannels] LỖI: Không tìm thấy credentials tại: {CREDS_FILE}")
        return

    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(str(CREDS_FILE), scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID)
        ws = sheet.worksheet(TAB_NAME)
        print(f"[PullChannels] Đã kết nối tab '{TAB_NAME}'")
    except Exception as e:
        print(f"[PullChannels] LỖI kết nối: {e}")
        return

    records = ws.get_all_records()
    print(f"[PullChannels] Đã đọc được {len(records)} dòng từ Google Sheet.")

    config_path = BASE_DIR / "backend" / "channels_config.json"
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    channels = config.get("channels", {})
    updated_count = 0

    for row in records:
        ch_key = str(row.get("Mã Kênh Hệ Thống", "")).strip()
        douyin_url = str(row.get("Link Kênh Douyin Nguồn (Dán link kênh vào đây)", "")).strip()
        if ch_key in channels:
            if douyin_url and "douyin.com" in douyin_url and "MS4wLjABAAAA..." not in douyin_url:
                channels[ch_key]["douyin_channel_url"] = douyin_url
                updated_count += 1
                print(f"  + Cập nhật {ch_key}: {douyin_url}")

    if updated_count > 0:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"[PullChannels] Đã lưu {updated_count} link Douyin mới vào channels_config.json!")
    else:
        print("[PullChannels] Không có link Douyin mới nào cần cập nhật.")


if __name__ == "__main__":
    main()
