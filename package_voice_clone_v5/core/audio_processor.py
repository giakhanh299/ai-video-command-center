import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

import asyncio
import re
from faster_whisper import WhisperModel
from openai import OpenAI
from dotenv import load_dotenv
import edge_tts
from pydub import AudioSegment
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR.parent / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

def extract_audio(video_path: str, audio_path: str):
    """Extracts audio from video using FFmpeg."""
    command = ['ffmpeg', '-y', '-i', video_path, '-q:a', '0', '-map', 'a', audio_path]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

def transcribe_audio(audio_path: str):
    """Transcribes audio using faster-whisper."""
    model_size = os.getenv("WHISPER_MODEL", "large-v3").strip() or "large-v3"
    device = os.getenv("WHISPER_DEVICE", "cuda").strip().lower()
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "float16" if device == "cuda" else "int8").strip()
    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception as exc:
        err_msg = f"WHISPER_MODEL_LOAD_FAILED: Could not load Whisper model '{model_size}' on {device} ({compute_type}): {exc}"
        print(f"[Whisper] {err_msg}")
        raise RuntimeError(err_msg) from exc
    
    print("Transcribing...")
    segments, info = model.transcribe(audio_path, beam_size=5)
    
    results = []
    for segment in segments:
        results.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text
        })
    return results

def translate_text(text: str) -> str:
    """Translates and rewrites text to Vietnamese naturally using DeepSeek API."""
    load_dotenv()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == "your_deepseek_api_key_here":
        print("Warning: DEEPSEEK_API_KEY not set. Using raw text.")
        return text

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    
    try:
        response = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": "Bạn là một YouTuber chuyên nghiệp. Nhiệm vụ của bạn là dịch văn bản (tiếng Trung/Anh) sang tiếng Việt, và viết lại sao cho giọng văn cực kỳ tự nhiên, mượt mà, phù hợp để lồng tiếng video. Chỉ trả về văn bản đã dịch và viết lại, không thêm bất kỳ bình luận nào khác."},
                {"role": "user", "content": text},
            ],
            stream=False
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"DeepSeek API error: {e}")
        return text

async def generate_tts(text: str, output_path: str, voice: str = 'vi-VN-HoaiMyNeural') -> bool:
    """Generates TTS using edge-tts with cleaning and retry mechanism."""
    clean_text = re.sub(r'[*_#`~]', '', text).strip()
    if not clean_text or len(clean_text) < 2:
        return False
        
    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(clean_text, voice)
            await communicate.save(output_path)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True
        except Exception as e:
            print(f"[Edge-TTS] Attempt {attempt+1} failed ({e}), retrying...")
            await asyncio.sleep(0.6)
            
    return False

async def process_audio_pipeline(video_path: str, output_audio_path: str, voice: str):
    """Main pipeline to extract, transcribe, translate, and generate dubbed audio."""
    job_token = Path(output_audio_path).stem
    temp_audio = WORKSPACE_DIR / f"{job_token}_source.wav"
    extract_audio(video_path, str(temp_audio))
    
    segments = transcribe_audio(str(temp_audio))
    
    final_audio = AudioSegment.silent(duration=0)
    current_time_ms = 0
    
    for i, seg in enumerate(segments):
        raw_text = seg.get("text", "").strip()
        if not raw_text:
            continue
            
        translated = translate_text(raw_text)
        print(f"[{seg['start']:.1f} - {seg['end']:.1f}] {translated}")
        
        tts_output = WORKSPACE_DIR / f"{job_token}_tts_{i}.mp3"
        success = await generate_tts(translated, str(tts_output), voice)
        
        if success and os.path.exists(tts_output):
            try:
                segment_audio = AudioSegment.from_file(str(tts_output))
                start_ms = int(seg["start"] * 1000)
                
                # Add silence if needed
                if start_ms > current_time_ms:
                    final_audio += AudioSegment.silent(duration=start_ms - current_time_ms)
                    current_time_ms = start_ms
                
                final_audio += segment_audio
                current_time_ms += len(segment_audio)
            except Exception as e:
                print(f"[AudioProcessor] Segment audio error: {e}")
            finally:
                if os.path.exists(tts_output):
                    os.remove(tts_output)
                    
    # Ensure audio duration is at least 1 second
    if len(final_audio) < 500:
        final_audio = AudioSegment.silent(duration=1000)
        
    final_audio.export(output_audio_path, format="wav")
    
    if temp_audio.exists():
        try:
            temp_audio.unlink()
        except:
            pass
    
    if temp_audio.exists():
        temp_audio.unlink()
