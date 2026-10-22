import sys
import os
import json
import urllib.parse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv

# Force unbuffered UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace', line_buffering=True)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / "backend" / ".env")

CLIENT_ID = os.getenv("GDRIVE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("GDRIVE_CLIENT_SECRET", "").strip()
SCOPES = ["https://www.googleapis.com/auth/drive"]

CLIENT_CONFIG = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost:8099/"]
    }
}

auth_code = None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h1>🎉 XÁC THỰC THÀNH CÔNG!</h1><p>Bạn có thể đóng tab này và quay lại cửa sổ chat.</p>".encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No code in request")

    def log_message(self, format, *args):
        pass

def get_refresh_token():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("Thiếu GDRIVE_CLIENT_ID/GDRIVE_CLIENT_SECRET trong backend/.env")
    print("=" * 60, flush=True)
    print("🔑 ĐANG KHỞI ĐỘNG XÁC THỰC GOOGLE DRIVE (DESKTOP APP)...", flush=True)
    print("=" * 60, flush=True)

    flow = InstalledAppFlow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri="http://localhost:8099/"
    )

    auth_url, state = flow.authorization_url(prompt='consent', access_type='offline')

    print("\n👉 LINK XÁC THỰC CHÍNH XÁC:", flush=True)
    print(auth_url, flush=True)
    print("\n⏳ Đang lắng nghe phản hồi tại cổng 8099...", flush=True)

    server = HTTPServer(("localhost", 8099), OAuthCallbackHandler)
    while auth_code is None:
        server.handle_request()
    server.server_close()

    print("\n[OAuth] Đã nhận code xác thực, đang lấy Refresh Token...", flush=True)
    flow.fetch_token(code=auth_code)
    creds = flow.credentials

    if creds and creds.refresh_token:
        print("\n" + "=" * 60, flush=True)
        print("🎉 XÁC THỰC THÀNH CÔNG!", flush=True)
        print(f"• Refresh Token: {creds.refresh_token}", flush=True)
        print("=" * 60, flush=True)

        token_info = {
            "refresh_token": creds.refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scopes": SCOPES
        }
        output_file = os.path.join(os.path.dirname(__file__), "gdrive_token.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(token_info, f, indent=2)
        print(f"Đã lưu vào: {output_file}\n", flush=True)
        return creds.refresh_token
    else:
        print("\n⚠️ Không nhận được refresh_token.", flush=True)
        return None

if __name__ == "__main__":
    get_refresh_token()
