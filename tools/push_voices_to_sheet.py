"""
push_voices_to_sheet.py
-----------------------
Đẩy toàn bộ danh sách voice profiles từ channels_config.json lên Google Sheet
tab "VOICE_PROFILES" để user chọn giọng nào dùng cho:
  - dct_ = Dẫn Chương Trình (workflow: wuby / voice_bank wuby)
  - p_   = Phim Clone (workflow: movie_clone / voice_bank movie)

Cột trong sheet:
  A: profile_key      - key trong channels_config (ví dụ: omni_laivansam)
  B: label            - tên hiển thị
  C: gender           - Nam / Nữ / Edge / System
  D: engine           - omnivoice / edge / google
  E: reference_hz     - tần số F0 (Hz)
  F: ref_audio        - file mẫu
  G: dct_enabled      - TRUE/FALSE → dùng cho Dẫn Chương Trình
  H: p_enabled        - TRUE/FALSE → dùng cho Phim Clone
  I: note             - ghi chú thêm

Sau khi chỉnh trong sheet, chạy pull_voices_from_sheet.py để đồng bộ về channels_config.json
"""

import sys
import io
import json
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent
CREDS_FILE = Path(r"D:/02_CONG_CU/youtube-reup-pipeline\secrets\sheet_service_account.json")
SPREADSHEET_ID = "13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs"
TAB_NAME = "VOICE_PROFILES"

# Giọng mặc định bật sẵn cho từng workflow
DCT_DEFAULT = {
    "omni_dan_chuong_trinh_vip",
    "omni_laivansam",
    "omni_nam_review",
    "omni_tauthao",
    "omni_chautinhtri",
    "omni_nu_tram",
    "omni_nu_ngoc_trinh",
    "omni_nu_cute",
    "omni_nu_tre",
    "omni_betterversion",
}

P_DEFAULT = {
    "omni_dan_chuong_trinh_vip",
    "omni_laivansam",
    "omni_nam_review",
    "omni_tauthao",
    "omni_chautinhtri",
    "omni_kienthuc_taichinh",
    "omni_nam_mienBac_lichsu",
    "omni_nu_cam_xuc",
    "omni_nu_diu_dang",
    "omni_nu_cute",
    "omni_nu_ngoc_trinh",
    "omni_nu_tre_trung",
    "omni_huyen_narrator",
}


def detect_gender(key, label, hz):
    key_l = key.lower()
    label_l = label.lower()
    if any(x in key_l for x in ["nu_", "hoaimy", "wuby", "betterversion", "huyen"]):
        return "Nu"
    if any(x in label_l for x in ["nu", "hoai my", "wuby", "better"]):
        return "Nu"
    if any(x in key_l for x in ["nam_", "laivansam", "tauthao", "chautinhtri", "kienthuc", "vip"]):
        return "Nam"
    if any(x in label_l for x in ["nam", "lai van sam", "tao thao", "chau tinh"]):
        return "Nam"
    if hz and hz > 0:
        return "Nu" if hz >= 180 else "Nam"
    return "?"


def main():
    config_path = BASE_DIR / "backend" / "channels_config.json"
    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)

    voice_profiles = data.get("voice_profiles", {})
    print(f"[VoiceSheet] Loaded {len(voice_profiles)} voice profiles")

    if not CREDS_FILE.exists():
        print(f"[VoiceSheet] LOI: Khong tim thay credentials: {CREDS_FILE}")
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
        print(f"[VoiceSheet] Da ket noi spreadsheet OK")
    except Exception as e:
        print(f"[VoiceSheet] LOI ket noi GG Sheet: {e}")
        return

    existing_tabs = [ws.title for ws in sheet.worksheets()]
    if TAB_NAME in existing_tabs:
        ws = sheet.worksheet(TAB_NAME)
        ws.clear()
        time.sleep(1)
        print(f"[VoiceSheet] Tab '{TAB_NAME}' da xoa + ghi lai")
    else:
        ws = sheet.add_worksheet(title=TAB_NAME, rows=100, cols=10)
        time.sleep(1)
        print(f"[VoiceSheet] Tao tab moi: '{TAB_NAME}'")

    headers = [
        "profile_key",
        "label",
        "gender",
        "engine",
        "reference_hz",
        "ref_audio",
        "dct_enabled",
        "p_enabled",
        "note",
    ]

    rows = [headers]

    for key, vp in voice_profiles.items():
        label = vp.get("label", "")
        engine = vp.get("engine", "")
        hz = vp.get("reference_hz", "")
        ref_audio = vp.get("ref_audio", "")
        gender = detect_gender(key, label, float(hz) if hz else 0)

        dct_on = "TRUE" if key in DCT_DEFAULT else "FALSE"
        p_on   = "TRUE" if key in P_DEFAULT   else "FALSE"

        note = ""
        if engine == "edge":
            note = "Edge TTS"
        elif engine == "google":
            note = "Google TTS"

        rows.append([
            key,
            label,
            gender,
            engine,
            str(hz) if hz else "",
            ref_audio,
            dct_on,
            p_on,
            note,
        ])

    ws.update("A1", rows)
    time.sleep(0.5)

    try:
        ws.format("A1:I1", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.8},
        })
        sheet.batch_update({
            "requests": [{
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": ws.id,
                        "gridProperties": {"frozenRowCount": 1}
                    },
                    "fields": "gridProperties.frozenRowCount"
                }
            }]
        })
    except Exception as e:
        print(f"[VoiceSheet] Warning format: {e}")

    print(f"\n[VoiceSheet] XONG! Da push {len(rows)-1} voice profiles len tab '{TAB_NAME}'")
    print(f"[VoiceSheet] URL: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")
    print(f"\n  - Col G (dct_enabled): TRUE = Giong cho Dan Chuong Trinh")
    print(f"  - Col H (p_enabled):   TRUE = Giong cho Phim Clone")
    print(f"  - Chinh xong thi chay: python tools/pull_voices_from_sheet.py")


if __name__ == "__main__":
    main()
