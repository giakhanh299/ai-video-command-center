"""
Posting Manager: Điều phối đăng bài tự động từng Kênh / Fanpage riêng biệt & Quản lý hàng đợi Google Sheet
Tab quản lý: UPLOAD_DANG_BAI
"""

from __future__ import annotations
import os
import sys
import time
from pathlib import Path
from typing import Any
from google.oauth2 import service_account
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "backend"))

from bitbrowser_service import BitBrowserClient
from tiktok_auto_post import TikTokUploader
from facebook_auto_post import FacebookFanpageUploader
from human_simulator import human_delay

SHEET_ID = "15a70VzkW0yDqp-zk3QcjoO4QdHnvJcZ40lGSyxTSmfI"
SHEET_TAB = "UPLOAD_DANG_BAI"
CREDS_FILE = r"D:/02_CONG_CU/youtube-reup-pipeline\secrets\sheet_service_account.json"

class PostingManager:
    def __init__(self, sheet_id: str = SHEET_ID):
        self.sheet_id = sheet_id
        self.bitbrowser = BitBrowserClient()
        self._init_sheet_service()

    def _init_sheet_service(self):
        try:
            creds = service_account.Credentials.from_service_account_file(
                CREDS_FILE,
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            self.service = build("sheets", "v4", credentials=creds)
        except Exception as e:
            print(f"[PostingManager] Không thể kết nối Google Sheets: {e}")
            self.service = None

    def get_sheet_queue(self, status_filter: str = "⚪ Chờ đăng") -> list[dict[str, Any]]:
        """Đọc danh sách hàng đợi các kênh cần đăng từ Google Sheet tab UPLOAD_DANG_BAI."""
        if not self.service:
            return []

        try:
            res = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=f"{SHEET_TAB}!A4:K50"
            ).execute()
            rows = res.get("values", [])
            queue = []
            for idx, r in enumerate(rows, start=4):
                if len(r) < 7:
                    continue
                # Mapping cột mới:
                # A: STT, B: Tên Kênh/Fanpage, C: Nền Tảng, D: Profile, E: Link Gốc, F: File Video, G: Caption, H: Chế Độ, I: Trạng Thái, J: Link Bài Đăng, K: Hoàn Tất
                channel_name = r[1] if len(r) > 1 else ""
                platform = r[2] if len(r) > 2 else "TikTok"
                profile_name = r[3] if len(r) > 3 else "TiêuWuBy"
                source_link = r[4] if len(r) > 4 else ""
                video_file = r[5] if len(r) > 5 else ""
                caption = r[6] if len(r) > 6 else ""
                mode = r[7] if len(r) > 7 else "Đăng ngay"
                status = r[8] if len(r) > 8 else "⚪ Chờ đăng"

                if status_filter and status != status_filter:
                    continue

                queue.append({
                    "row_idx": idx,
                    "channel_name": channel_name,
                    "platform": platform,
                    "profile_name": profile_name,
                    "source_link": source_link,
                    "video_file": video_file,
                    "caption": caption,
                    "mode": mode,
                    "status": status
                })
            return queue
        except Exception as e:
            print(f"[PostingManager] Lỗi đọc hàng đợi từ Sheet: {e}")
            return []

    def update_job_status(self, row_idx: int, status: str, post_link_or_note: str = ""):
        """Cập nhật trạng thái (Cột I), Link bài đăng (Cột J), Thời gian hoàn tất (Cột K)."""
        if not self.service or row_idx <= 0:
            return

        try:
            now_str = time.strftime("%Y-%m-%d %H:%M")
            values = [[status, post_link_or_note, now_str]]
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=f"{SHEET_TAB}!I{row_idx}:K{row_idx}",
                valueInputOption="USER_ENTERED",
                body={"values": values}
            ).execute()
            print(f"[PostingManager] Đã cập nhật dòng {row_idx}: {status} | {post_link_or_note}")
        except Exception as e:
            print(f"[PostingManager] Lỗi cập nhật Google Sheet: {e}")

    def run_queue_from_sheet(self, row_idx_target: int | None = None) -> list[dict[str, Any]]:
        """
        Tự động duyệt hàng đợi trên Google Sheet:
        Mỗi kênh lấy đúng file video, đúng caption, đúng Fanpage/TikTok để đăng!
        """
        all_jobs = self.get_sheet_queue(status_filter="⚪ Chờ đăng")
        if row_idx_target:
            all_jobs = [j for j in all_jobs if j["row_idx"] == row_idx_target]

        if not all_jobs:
            print("[PostingManager] Không có kênh nào đang ở trạng thái '⚪ Chờ đăng' trên Google Sheet.")
            return []

        print(f"\n🚀 BẮT ĐẦU CHẠY HÀNG ĐỢI ĐĂNG BÀI TỪ GOOGLE SHEET ({len(all_jobs)} KÊNH CẦN ĐĂNG):")
        print("=" * 65)

        results = []
        for i, job in enumerate(all_jobs, start=1):
            row_idx = job["row_idx"]
            channel = job["channel_name"]
            platform = job["platform"]
            profile = job["profile_name"]
            rel_vid = job["video_file"].strip()
            caption = job["caption"].strip()

            video_path = (BASE_DIR / rel_vid).resolve() if not os.path.isabs(rel_vid) else Path(rel_vid)

            print(f"\n[{i}/{len(all_jobs)}] Đang xử lý: '{channel}' | Nền tảng: {platform}")
            print(f"  • Video riêng: {video_path.name}")
            print(f"  • Caption riêng: {caption[:60]}...")

            if not video_path.exists():
                err_msg = f"File video không tồn tại: {video_path}"
                print(f"❌ {err_msg}")
                self.update_job_status(row_idx, "🔴 Thất bại", err_msg)
                results.append({"channel": channel, "success": False, "error": err_msg})
                continue

            # Cập nhật trạng thái đang xử lý lên Sheet
            self.update_job_status(row_idx, "⏳ Đang xử lý", f"Đang tải video lên {platform}...")

            success = False
            note = ""

            try:
                with self.bitbrowser.connect_playwright(profile, auto_close=False) as page:
                    if "TikTok" in platform:
                        uploader = TikTokUploader(page)
                        if not uploader.navigate_to_upload_page():
                            raise RuntimeError("Chưa đăng nhập TikTok trong profile BitBrowser.")
                        res = uploader.upload_video(video_path=video_path, caption=caption)
                        success = res.get("success", False)
                        note = "Đăng thành công TikTok Studio" if success else "Chưa nhận diện được thông báo thành công"
                    else:
                        uploader = FacebookFanpageUploader(page)
                        if not uploader.navigate_to_composer():
                            raise RuntimeError("Chưa đăng nhập Facebook trong profile BitBrowser.")
                        # Tách lấy tên Fanpage sạch
                        clean_page_name = channel.split("(")[0].replace("Fanpage", "").strip()
                        res = uploader.upload_reels(
                            video_path=video_path,
                            caption=caption,
                            page_name=clean_page_name,
                            publish_mode=job.get("mode", "Đăng ngay")
                        )
                        success = res.get("success", False)
                        note = f"Đăng thành công lên Fanpage '{channel}'" if success else "Chưa nhận diện được thông báo thành công"

            except Exception as e:
                note = f"Lỗi: {str(e)[:120]}"
                print(f"❌ Lỗi đăng kênh {channel}: {e}")

            # Cập nhật kết quả cuối cùng lên Sheet
            final_status = "🟢 Đã đăng thành công" if success else "🔴 Thất bại"
            self.update_job_status(row_idx, final_status, note)
            results.append({"channel": channel, "success": success, "note": note})

            # Tạm dừng nghỉ an toàn giữa các kênh (20s - 35s)
            if i < len(all_jobs):
                print(f"⏳ Tạm dừng nghỉ giữa các kênh để đảm bảo an toàn...")
                human_delay(20.0, 35.0)

        print("\n" + "=" * 65)
        print("🎉 HOÀN TẤT DUYỆT TOÀN BỘ HÀNG ĐỢI ĐĂNG BÀI!")
        return results
