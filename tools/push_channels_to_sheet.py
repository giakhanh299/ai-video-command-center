"""
push_channels_to_sheet.py
--------------------------
Đẩy toàn bộ danh sách cấu hình kênh, thư mục đầu vào, thư mục đầu ra
và link kênh Douyin nguồn lên Google Sheet tab "DANH_SACH_KENH_DOUYIN".

Spreadsheet ID: 13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs
"""

import sys
import io
import json
import time
from pathlib import Path
from channel_output_paths import channel_review_path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path("D:/0.1_FACE_BOOK/Lay video tiktok")
CREDS_FILE = Path(r"D:/02_CONG_CU/youtube-reup-pipeline\secrets\sheet_service_account.json")
SPREADSHEET_ID = "13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs"
TAB_NAME = "DANH_SACH_KENH_DOUYIN"

CHANNEL_METADATA = {
    "KENH_001_TienVaDoi": {
        "theme": "Triết lý tài chính, kiếm tiền, kinh doanh, đối nhân xử thế Douyin",
        "douyin_sample_link": "https://www.douyin.com/user/MS4wLjABAAAA...",
        "input_folder": "inputs/KENH_001_TienVaDoi",
        "output_base": "outputs/KENH_001_TienVaDoi",
        "status": "Đang hoạt động",
        "note": "Black bar trên/dưới điện ảnh, voice Tài Chính trầm ấm"
    },
    "KENH_002_BatPhimLen": {
        "theme": "Review phim điện ảnh, phim ngắn Trung Quốc hot Douyin",
        "douyin_sample_link": "https://www.douyin.com/user/MS4wLjABAAAA...",
        "input_folder": "inputs/KENH_002_BatPhimLen",
        "output_base": "outputs/KENH_002_BatPhimLen",
        "status": "Đang hoạt động",
        "note": "Title 6s fade-out biến mất, sub vàng/trắng sắc nét"
    },
    "KENH_003_ReviewSachCoTam": {
        "theme": "Tóm tắt sách hay, phát triển bản thân, bài học cuộc sống",
        "douyin_sample_link": "https://www.douyin.com/user/MS4wLjABAAAA...",
        "input_folder": "inputs/KENH_003_ReviewSachCoTam",
        "output_base": "outputs/KENH_003_ReviewSachCoTam",
        "status": "Đang hoạt động",
        "note": "Clean sub, voice Better Version truyền cảm hứng"
    },
    "KENH_004_BoxmanKeChuyen": {
        "theme": "Kể chuyện kinh dị, trinh thám, vụ án bí ẩn Douyin",
        "douyin_sample_link": "https://www.douyin.com/user/MS4wLjABAAAA...",
        "input_folder": "inputs/KENH_004_BoxmanKeChuyen",
        "output_base": "outputs/KENH_004_BoxmanKeChuyen",
        "status": "Đang hoạt động",
        "note": "Giọng Nam Minh 1.3x hào sảng, che đen đáy"
    },
    "KENH_005_VuTruCayPhim": {
        "theme": "Phim bộ ngắn nhiều tập, tổng tài, cổ trang Trung Quốc",
        "douyin_sample_link": "https://www.douyin.com/user/MS4wLjABAAAA...",
        "input_folder": "inputs/KENH_005_VuTruCayPhim",
        "output_base": "outputs/KENH_005_VuTruCayPhim",
        "status": "Đang hoạt động",
        "note": "Clone phim đa nhân vật (F0 Whisper + Pyannote Diarization)"
    },
    "KENH_006_TieuWuby": {
        "theme": "Hoạt hình 2D/3D anime, hoạt họa vui nhộn, meme hài",
        "douyin_sample_link": "https://www.douyin.com/user/MS4wLjABAAAA...",
        "input_folder": "inputs/KENH_006",
        "output_base": "outputs/KENH_006",
        "status": "Đang hoạt động",
        "note": "Overlay trực tiếp lên video gốc, font hoạt hình, voice Wuby Clone cute"
    },
    "KENH_007_Song1MinhCoGiVui": {
        "theme": "Vlog đời sống độc thân, nấu ăn chill, không gian sống Douyin",
        "douyin_sample_link": "https://www.douyin.com/user/MS4wLjABAAAA...",
        "input_folder": "inputs/KENH_007",
        "output_base": "outputs/KENH_007",
        "status": "Đang hoạt động",
        "note": "Wuby overlay, voice Wuby Clone nhẹ nhàng 1.0x"
    },
    "KENH_008_ChiDepDiCau": {
        "theme": "Gái đẹp đi câu, dã ngoại ngoài trời, săn bắt dân dã",
        "douyin_sample_link": "https://www.douyin.com/user/MS4wLjABAAAA...",
        "input_folder": "inputs/KENH_008",
        "output_base": "outputs/KENH_008",
        "status": "Đang hoạt động",
        "note": "Làm mờ kính frosted glass che sub Trung, voice Nữ Cute 1.45x"
    },
    "-1004462729383": {
        "theme": "Nhóm Telegram Quản Trị & Test Render Toàn Hệ Thống",
        "douyin_sample_link": "Nhận trực tiếp từ tin nhắn Telegram (https://v.douyin.com/...)",
        "input_folder": "workspace",
        "output_base": "workspace / outputs",
        "status": "Control Bot",
        "note": "Hỗ trợ test nhanh các preset và nhận video trực tiếp"
    }
}


def main():
    config_path = BASE_DIR / "backend" / "channels_config.json"
    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)

    channels = data.get("channels", {})
    voice_profiles = data.get("voice_profiles", {})
    print(f"[PushChannels] Đã đọc {len(channels)} kênh từ channels_config.json")

    if not CREDS_FILE.exists():
        print(f"[PushChannels] LỖI: Không tìm thấy credentials tại: {CREDS_FILE}")
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
        print(f"[PushChannels] Đã kết nối Google Spreadsheet '{SPREADSHEET_ID}' thành công!")
    except Exception as e:
        print(f"[PushChannels] LỖI kết nối Google Sheets: {e}")
        return

    existing_tabs = [ws.title for ws in sheet.worksheets()]
    if TAB_NAME in existing_tabs:
        ws = sheet.worksheet(TAB_NAME)
        ws.clear()
        time.sleep(1)
        print(f"[PushChannels] Tab '{TAB_NAME}' đã có sẵn -> Đã xóa trắng để cập nhật lại.")
    else:
        ws = sheet.add_worksheet(title=TAB_NAME, rows=50, cols=16)
        time.sleep(1)
        print(f"[PushChannels] Đã tạo mới tab '{TAB_NAME}' thành công!")

    headers = [
        "STT",
        "Mã Kênh Hệ Thống",
        "Tên Kênh Hiển Thị",
        "Chủ Đề Nội Dung Douyin",
        "Link Kênh Douyin Nguồn (Dán link kênh vào đây)",
        "Thư Mục Đầu Vào Cục Bộ (Local Input)",
        "Thư Mục Đầu Ra Render Xong (02_MOI_RENDER)",
        "Cấu Trúc 5 Thư Mục Vòng Đời",
        "Thư Mục Google Drive Đích",
        "Workflow",
        "Render Profile (Kiểu Che Sub)",
        "Giọng Đọc (Voice)",
        "Tốc Độ Đọc",
        "Logo / Watermark",
        "Trạng Thái",
        "Ghi Chú Kỹ Thuật"
    ]

    rows = [headers]
    idx = 1
    for ch_key, ch_val in channels.items():
        name = ch_val.get("name", ch_key)
        workflow = ch_val.get("workflow", "default")
        render_profile = ch_val.get("render_profile", ch_val.get("mask_mode", "auto"))
        voice_key = ch_val.get("voice", "default")
        voice_info = voice_profiles.get(voice_key, {})
        voice_label = voice_info.get("label", voice_key)
        speed = f"{ch_val.get('speed', 1.0)}x"
        drive_folder = ch_val.get("drive_folder", "Chưa gán")
        
        logo_info = ch_val.get("logo", {})
        logo_tag = logo_info.get("tag", ch_val.get("_logo_type", "Chưa có"))

        meta = CHANNEL_METADATA.get(ch_key, {
            "theme": "Kênh tùy biến",
            "douyin_sample_link": "https://www.douyin.com/user/...",
            "input_folder": f"inputs/{ch_key}",
            "output_base": f"outputs/{ch_key}",
            "status": "Đang cấu hình",
            "note": ""
        })

        # Ưu tiên lấy douyin_channel_url nếu đã được khai báo trong channels_config.json
        douyin_url = ch_val.get("douyin_channel_url", meta["douyin_sample_link"])
        input_folder_path = f"D:/0.1_FACE_BOOK/Lay video tiktok/{meta['input_folder']}"
        output_folder_path = f"D:/0.1_FACE_BOOK/Lay video tiktok/{meta['output_base']}/02_MOI_RENDER_CHO_XAC_NHAN"
        output_folder_path = channel_review_path(BASE_DIR, ch_key, ch_val, output_folder_path)
        lifecycle_folders = "01_CHUA_RENDER | 02_MOI_RENDER_CHO_XAC_NHAN | 03_CHUAN_BI_UP | 04_DA_UP | 99_FAILED"

        rows.append([
            idx,
            ch_key,
            name,
            meta["theme"],
            douyin_url,
            input_folder_path,
            output_folder_path,
            lifecycle_folders,
            f"Google Drive: {drive_folder}",
            workflow,
            render_profile,
            voice_label,
            speed,
            logo_tag,
            meta["status"],
            meta["note"]
        ])
        idx += 1

    ws.update("A1:P" + str(len(rows)), rows)
    print(f"[PushChannels] Đã đẩy thành công {len(rows)-1} kênh lên tab '{TAB_NAME}' của Google Sheet!")
    print(f"👉 Link xem Google Sheet: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")


if __name__ == "__main__":
    main()
