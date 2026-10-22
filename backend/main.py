import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uuid
import asyncio
import shutil
from pathlib import Path

from downloader import extract_url, download_video
from audio_processor import process_audio_pipeline
from video_merger import merge_video_audio
import threading

app = FastAPI(title="Video Dubbing API")

# Chỉ khởi động Telegram Bot trong FastAPI nếu có cấu hình RUN_BOT_IN_SERVER=1 (mặc định bot chạy tiến trình riêng qua run_bot.ps1)
if os.getenv("RUN_BOT_IN_SERVER", "0") == "1":
    @app.on_event("startup")
    def startup_telegram_bot():
        try:
            from telegram_bot import start_bot_polling
            bot_thread = threading.Thread(target=start_bot_polling, daemon=True)
            bot_thread.start()
            print("[Server] Telegram Bot đã được khởi động song song!")
        except Exception as e:
            print(f"[Server] Không thể khởi động Telegram Bot: {e}")

# Frontend chạy trên Cloudflare Pages; có thể bổ sung origin bằng biến môi trường
# CORS_ORIGINS (danh sách phân tách bằng dấu phẩy).
default_origins = [
    "https://giakhanh.xyz",
    "https://www.giakhanh.xyz",
    "https://tiktok.giakhanh.xyz",
    "http://localhost:8005",
    "http://127.0.0.1:8005",
]
configured_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=default_origins + configured_origins,
    allow_origin_regex=r"https://[a-z0-9-]+(?:\.[a-z0-9-]+)*\.pages\.dev",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
WORKSPACE_DIR = PROJECT_DIR / "workspace"
OUTPUT_DIR = PROJECT_DIR / "youtube-reup-pipeline"
GOOGLE_DRIVE_DIR = Path(os.getenv("GOOGLE_DRIVE_DIR", "G:/My Drive/Video Douyin"))
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/workspace", StaticFiles(directory=str(WORKSPACE_DIR)), name="workspace")

# In-memory status store
jobs = {}

class ProcessRequest(BaseModel):
    text: str
    voice: str = 'vi-VN-HoaiMyNeural'
    use_nvenc: bool = True
    background_blur: bool = False
    blur_subtitle: bool = True
    blur_subtitle_height_ratio: float = 0.25
    keep_original_audio: bool = True
    original_audio_volume: float = 0.05
    music_volume: float = 0.07

def run_pipeline(job_id: str, request: ProcessRequest):
    jobs[job_id] = {"status": "extracting_url", "progress": 5}
    url = extract_url(request.text)
    
    if not url:
        jobs[job_id] = {"status": "error", "message": "No valid URL found in text"}
        return

    try:
        video_path = WORKSPACE_DIR / f"{job_id}_original.mp4"
        audio_path = WORKSPACE_DIR / f"{job_id}_dubbed.wav"
        output_path = WORKSPACE_DIR / f"{job_id}_final.mp4"
        
        jobs[job_id] = {"status": "downloading_video", "progress": 15}
        downloaded_file = download_video(url, str(video_path))
        
        jobs[job_id] = {"status": "processing_audio", "progress": 40}
        asyncio.run(process_audio_pipeline(downloaded_file, str(audio_path), request.voice))
        
        jobs[job_id] = {"status": "merging_video", "progress": 85}
        channel_cfg = {
            "use_nvenc": request.use_nvenc,
            "background_blur": request.background_blur,
            "blur_subtitle": request.blur_subtitle,
            "blur_subtitle_height_ratio": request.blur_subtitle_height_ratio,
            "keep_original_audio": request.keep_original_audio,
            "original_audio_volume": request.original_audio_volume,
            "tts_audio_volume": 1.0,
            "music_volume": request.music_volume,
            # Link to D:/02_CONG_CU/youtube-reup-pipeline resources if needed
            # "music_path": "D:/02_CONG_CU/youtube-reup-pipeline/some_music.mp3",
            # "logo_path": "D:/02_CONG_CU/youtube-reup-pipeline/LOGO YOUTUBE/logo.png",
            # "burn_subtitles": False
        }
        merge_video_audio(downloaded_file, str(audio_path), str(output_path), channel_cfg)
        
        jobs[job_id] = {
            "status": "completed", 
            "progress": 100, 
            "result_url": f"/workspace/{job_id}_final.mp4"
        }
        
        # Copy to youtube-reup-pipeline folder
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output_path, OUTPUT_DIR / f"{job_id}_final.mp4")

        # Copy to Google Drive folder
        try:
            if GOOGLE_DRIVE_DIR.exists():
                shutil.copy2(output_path, GOOGLE_DRIVE_DIR / f"{job_id}_final.mp4")
                print(f"[Google Drive] Successfully saved copy to {GOOGLE_DRIVE_DIR / f'{job_id}_final.mp4'}")
        except Exception as gd_err:
            print(f"[Google Drive] Auto-copy error: {gd_err}")
        
        # Cleanup temp files
        if os.path.exists(downloaded_file): os.remove(downloaded_file)
        if os.path.exists(audio_path): os.remove(audio_path)
        
    except Exception as e:
        jobs[job_id] = {"status": "error", "message": str(e)}

@app.post("/api/process")
async def start_process(request: ProcessRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "progress": 0}
    
    background_tasks.add_task(run_pipeline, job_id, request)
    
    return {"job_id": job_id}

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/api/health")
async def health():
    return {"status": "ok"}

# Phục vụ giao diện web tĩnh
import os
frontend_path = PROJECT_DIR / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
