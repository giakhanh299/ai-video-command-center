import sys
import os
import re
import requests
from dotenv import load_dotenv
from pathlib import Path
import yt_dlp

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

# Load .env
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

TIKHUB_API_TOKEN = os.getenv("TIKHUB_API_TOKEN", "")

def extract_url(text: str) -> str:
    """Extracts URLs or numeric IDs from text."""
    text_clean = text.strip()
    if text_clean.isdigit() and len(text_clean) >= 15:
        return f"https://www.tiktok.com/@video/video/{text_clean}"
    
    url_pattern = re.compile(r'https?://[^\s]+')
    match = url_pattern.search(text)
    if match:
        url = match.group(0)
        url = re.sub(r'[\u4e00-\u9fff，。！？、…]+$', '', url)
        return url
    return None

def extract_item_id(url: str):
    """Extracts numeric item_id from TikTok or Douyin URLs."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
    }
    try:
        # If it's a short URL, resolve redirect
        if any(domain in url for domain in ['vt.tiktok.com', 'vm.tiktok.com', 'v.douyin.com', 't.tiktok.com']):
            resp = requests.get(url, headers=headers, allow_redirects=False, timeout=10)
            if resp.status_code in [301, 302, 303, 307, 308] and resp.headers.get('Location'):
                url = resp.headers.get('Location')
            else:
                with requests.get(url, headers=headers, allow_redirects=True, stream=True, timeout=10) as r:
                    url = r.url
    except Exception as e:
        print(f"[Downloader] Error resolving redirect URL: {e}")

    # Search for numeric ID (usually 18-21 digits)
    match = re.search(r'(\d{18,21})', url)
    if match:
        return match.group(1), url
    return None, url

def download_file_stream(download_url: str, output_path: str, headers: dict = None) -> str:
    """Downloads a file from direct URL with streaming using ffmpeg or requests."""
    default_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    }
    if headers:
        default_headers.update(headers)

    if not output_path.endswith('.mp4'):
        output_path = output_path.rsplit('.', 1)[0] + '.mp4'

    # Try ffmpeg stream copy first (handles 200MB+ CDN streams reliably)
    ffmpeg_exe = Path(__file__).resolve().parent.parent / "tools" / "bin" / "ffmpeg.exe"
    ffmpeg_bin = str(ffmpeg_exe) if ffmpeg_exe.is_file() else "ffmpeg"
    try:
        import subprocess
        header_lines = "".join(f"{k}: {v}\r\n" for k, v in default_headers.items())
        cmd = [ffmpeg_bin, "-y", "-headers", header_lines, "-i", download_url, "-c", "copy", output_path]
        res = subprocess.run(cmd, capture_output=True, timeout=300)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
            return output_path
    except Exception as ff_err:
        print(f"[Downloader] ffmpeg stream download failed: {ff_err}, fallback to requests...")

    with requests.get(download_url, headers=default_headers, stream=True, timeout=(20, 1800)) as r:
        r.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    return output_path

def download_via_tikhub(item_id: str, output_path: str, is_douyin: bool = False) -> tuple[str, str]:
    """Fetches video from direct TikHub API (api.tikhub.io) without watermark."""
    if not TIKHUB_API_TOKEN:
        raise ValueError("TIKHUB_API_TOKEN is not configured in .env")

    headers = {
        'Authorization': f'Bearer {TIKHUB_API_TOKEN}',
        'Accept': 'application/json'
    }
    
    if is_douyin:
        api_url = "https://api.tikhub.io/api/v1/douyin/web/fetch_one_video"
        print(f"[TikHub] Requesting Douyin video detail for aweme_id={item_id}...")
        resp = requests.get(api_url, headers=headers, params={'aweme_id': item_id}, timeout=20)
        
        if resp.status_code == 200:
            data = resp.json()
            aweme = data.get('data', {}).get('aweme_detail', {})
            desc = str(aweme.get('desc', '') or '').strip()
            video = aweme.get('video', {})
            play_addr = video.get('play_addr_h264', {}) or video.get('play_addr', {}) or video.get('download_addr', {})
            url_list = play_addr.get('url_list', []) if isinstance(play_addr, dict) else []
            
            if url_list:
                print(f"[TikHub] Got Douyin stream URL, downloading...")
                fp = download_file_stream(url_list[0], output_path, headers={'Referer': 'https://www.douyin.com/'})
                return fp, desc
            else:
                raise ValueError("No valid video URL returned from TikHub Douyin API")
        else:
            raise RuntimeError(f"TikHub Douyin API status {resp.status_code}: {resp.text}")
    else:
        # TikTok endpoint
        api_url = "https://api.tikhub.io/api/v1/tiktok/web/fetch_post_detail"
        print(f"[TikHub] Requesting TikTok video detail for itemId={item_id}...")
        resp = requests.get(api_url, headers=headers, params={'itemId': item_id}, timeout=20)
        
        if resp.status_code == 200:
            data = resp.json()
            item_info = data.get('data', {}).get('itemInfo', {}).get('itemStruct', {})
            desc = str(item_info.get('desc', '') or '').strip()
            video_info = item_info.get('video', {})
            play_url = video_info.get('playAddr') or video_info.get('downloadAddr')
            
            if play_url:
                print(f"[TikHub] Got TikTok stream URL, downloading...")
                fp = download_file_stream(play_url, output_path, headers={'Referer': 'https://www.tiktok.com/'})
                return fp, desc
            else:
                raise ValueError("No valid video URL returned from TikHub TikTok API")
        else:
            raise RuntimeError(f"TikHub TikTok API status {resp.status_code}: {resp.text}")

def download_via_tikwm(url: str, output_path: str) -> tuple[str, str] | None:
    """Downloads a video using TikWM API as a fast watermark-free fallback."""
    try:
        print(f"[TikWM] Trying TikWM download for {url}...")
        resp = requests.post('https://www.tikwm.com/api/', data={'url': url, 'hd': 1}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 0:
                d = data.get('data', {})
                desc = str(d.get('title', '') or '').strip()
                play_url = d.get('play') or d.get('hdplay')
                if play_url:
                    if play_url.startswith('/'):
                        play_url = f"https://www.tikwm.com{play_url}"
                    print(f"[TikWM] Successfully resolved download URL!")
                    fp = download_file_stream(play_url, output_path)
                    return fp, desc
    except Exception as e:
        print(f"[TikWM] Download failed: {e}")
    return None

def download_via_ytdlp(url: str, output_path: str) -> tuple[str, str]:
    """Downloads a video using yt-dlp as fallback."""
    print(f"[yt-dlp] Downloading video from {url}...")
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'quiet': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        }
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info_dict)
        desc = str(info_dict.get('title', '') or '').strip()
        if not filepath.endswith('.mp4'):
            filepath = filepath.rsplit('.', 1)[0] + '.mp4'
        return filepath, desc

def download_video_with_title(url: str, output_path: str) -> tuple[str, str]:
    """
    Main download function returning (filepath, raw_title).
    1. Extracts Item ID if it's TikTok/Douyin link and uses direct TikHub API.
    2. Tries TikWM watermark-free API for TikTok.
    3. Falls back to yt-dlp.
    """
    item_id, resolved_url = extract_item_id(url)
    target_url = resolved_url or url
    is_douyin = 'douyin.com' in target_url
    
    # 1. Direct TikHub API
    if item_id and TIKHUB_API_TOKEN:
        try:
            return download_via_tikhub(item_id, output_path, is_douyin=is_douyin)
        except Exception as e:
            print(f"[Downloader] TikHub download failed: {e}. Trying next fallback...")
    
    # 2. Try TikWM for TikTok
    try:
        tikwm_res = download_via_tikwm(target_url, output_path)
        if tikwm_res:
            fp, desc = tikwm_res
            if os.path.exists(fp) and os.path.getsize(fp) > 50000:
                return fp, desc
    except Exception as e:
        print(f"[Downloader] TikWM fallback failed: {e}")
    
    # 3. Fallback to yt-dlp
    return download_via_ytdlp(target_url, output_path)

def download_video(url: str, output_path: str) -> str:
    """Wrapper returning only the downloaded file path for compatibility."""
    filepath, _ = download_video_with_title(url, output_path)
    return filepath


