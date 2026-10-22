"""
pull_voices_from_sheet.py
--------------------------
Đọc tab VOICE_PROFILES từ Google Sheet và cập nhật voice_bank trong channels_config.json:
  - workflow "wuby"        → voice_bank lấy các giọng có dct_enabled = TRUE
  - workflow "movie_clone" → voice_bank lấy các giọng có p_enabled   = TRUE

Chạy script này sau khi bạn đã chỉnh cột dct_enabled / p_enabled trên GG Sheet.
"""

import sys
import io
import json
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_DIR   = Path(__file__).resolve().parent.parent
CREDS_FILE = Path(r"D:/02_CONG_CU/youtube-reup-pipeline\secrets\sheet_service_account.json")
SPREADSHEET_ID = "13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs"
TAB_NAME   = "VOICE_PROFILES"


def main():
    # 1. Kết nối GG Sheet
    if not CREDS_FILE.exists():
        print(f"[PullVoice] LOI: Khong tim thay credentials: {CREDS_FILE}")
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
        sheet  = client.open_by_key(SPREADSHEET_ID)
        ws     = sheet.worksheet(TAB_NAME)
        print(f"[PullVoice] Da ket noi tab '{TAB_NAME}'")
    except Exception as e:
        print(f"[PullVoice] LOI ket noi: {e}")
        return

    # 2. Đọc dữ liệu sheet
    all_rows = ws.get_all_records()
    print(f"[PullVoice] Doc duoc {len(all_rows)} dong tu sheet")

    # 3. Load channels_config.json
    config_path = BASE_DIR / "backend" / "channels_config.json"
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    voice_profiles = config.get("voice_profiles", {})

    dct_bank = []
    p_bank   = []

    for row in all_rows:
        key     = str(row.get("profile_key", "")).strip()
        dct_on  = str(row.get("dct_enabled", "")).strip().upper()
        p_on    = str(row.get("p_enabled", "")).strip().upper()

        if not key or key not in voice_profiles:
            continue

        hz = voice_profiles[key].get("reference_hz", None)
        if hz is None:
            # Bỏ qua giọng không có reference_hz (edge không cần voice bank)
            continue

        if dct_on == "TRUE":
            dct_bank.append({
                "profile": key,
                "reference_hz": float(hz),
                "enabled": True
            })

        if p_on == "TRUE":
            p_bank.append({
                "profile": key,
                "reference_hz": float(hz),
                "enabled": True
            })

    # Sort theo hz
    dct_bank.sort(key=lambda x: x["reference_hz"])
    p_bank.sort(key=lambda x: x["reference_hz"])

    print(f"\n[PullVoice] Dan Chuong Trinh (dct) voice bank ({len(dct_bank)} giong):")
    for v in dct_bank:
        print(f"  {v['profile']:40s} | {v['reference_hz']}Hz")

    print(f"\n[PullVoice] Phim Clone (p) voice bank ({len(p_bank)} giong):")
    for v in p_bank:
        print(f"  {v['profile']:40s} | {v['reference_hz']}Hz")

    # 4. Cập nhật vào config
    # wuby workflow
    if "workflows" in config and "wuby" in config["workflows"]:
        wuby_vm = config["workflows"]["wuby"]["settings"].get("wuby_preflight", {}).get("voice_match", {})
        if wuby_vm:
            wuby_vm["voice_bank"] = dct_bank
            print(f"\n[PullVoice] Cap nhat voice_bank cho workflow 'wuby': {len(dct_bank)} giong")

    # movie_clone workflow
    if "workflows" in config and "movie_clone" in config["workflows"]:
        movie_vm = config["workflows"]["movie_clone"]["settings"].get("movie_voice_match", {})
        if movie_vm:
            movie_vm["voice_bank"] = p_bank
            print(f"[PullVoice] Cap nhat voice_bank cho workflow 'movie_clone': {len(p_bank)} giong")

    # 5. Ghi lại file
    backup_path = config_path.with_suffix(".json.bak")
    import shutil
    shutil.copy2(config_path, backup_path)
    print(f"[PullVoice] Backup -> {backup_path.name}")

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"\n[PullVoice] XONG! Da cap nhat channels_config.json")
    print(f"[PullVoice]   wuby voice bank:        {len(dct_bank)} giong")
    print(f"[PullVoice]   movie_clone voice bank: {len(p_bank)} giong")


if __name__ == "__main__":
    main()
