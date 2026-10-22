# -*- coding: utf-8 -*-
"""
Backup tool for lay_video_tiktok project.
Creates a complete zip archive of code, configs, assets, and voice samples.
"""
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
zip_filename = f"backup_tiktok_ai_cauhinh4_{timestamp}.zip"
zip_path = BACKUP_DIR / zip_filename

INCLUDE_DIRS = [
    "backend",
    "OmniVoice",
    "wuby_studio",
    "channel_assets",
    "voice_samples",
    "tools",
    "docs",
]

INCLUDE_EXTENSIONS = {
    ".py", ".bat", ".ps1", ".json", ".md", ".txt", ".ini", ".vbs", ".yaml", ".yml", ".wav", ".png", ".jpg"
}

EXCLUDE_PATTERNS = [
    "__pycache__",
    ".pytest_cache",
    ".cache",
    ".git",
    "node_modules",
    "wuby_voice_v7",
]

def should_exclude(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDE_PATTERNS:
            return True
    return False

print(f"[*] Bắt đầu nén Backup dự án vào: {zip_path}")

total_files = 0
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
    # 1. Zip root files
    for item in ROOT_DIR.iterdir():
        if item.is_file():
            if item.suffix.lower() in INCLUDE_EXTENSIONS or item.name in {"requirements.txt", ".gitignore"}:
                zipf.write(item, arcname=item.name)
                total_files += 1

    # 2. Zip selected subdirectories
    for d_name in INCLUDE_DIRS:
        dir_path = ROOT_DIR / d_name
        if not dir_path.exists():
            continue
        for file_path in dir_path.rglob("*"):
            if file_path.is_file() and not should_exclude(file_path):
                # Only include reasonable file sizes (< 50MB) to keep archive fast
                if file_path.stat().st_size < 50 * 1024 * 1024:
                    rel_path = file_path.relative_to(ROOT_DIR)
                    zipf.write(file_path, arcname=str(rel_path))
                    total_files += 1

    # 3. Zip key workspace scripts
    ws_dir = ROOT_DIR / "workspace"
    if ws_dir.exists():
        for ws_file in ws_dir.glob("*.py"):
            rel_path = ws_file.relative_to(ROOT_DIR)
            zipf.write(ws_file, arcname=str(rel_path))
            total_files += 1

file_size_mb = zip_path.stat().st_size / (1024 * 1024)
print(f"[+] BACKUP THÀNH CÔNG!")
print(f"    - File zip: {zip_path}")
print(f"    - Tổng số file: {total_files}")
print(f"    - Dung lượng: {file_size_mb:.2f} MB")
