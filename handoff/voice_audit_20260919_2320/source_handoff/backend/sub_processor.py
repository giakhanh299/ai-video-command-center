from __future__ import annotations

import os
import re
import sys
import time
import unicodedata
import subprocess
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

import asyncio
import edge_tts
from pydub import AudioSegment
from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()

@dataclass
class SubtitleSegment:
    start: float
    end: float
    text: str

@dataclass
class SubtitleItem:
    id: str
    time: str
    text: str

def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def extract_audio_for_transcription(video_path: str, output_audio_path: str) -> str:
    """Extracts 16kHz mono audio optimized for Whisper."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video_path),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(output_audio_path)
    ]
    subprocess.run(cmd, check=True)
    return output_audio_path

DEFAULT_WHISPER_MODEL = os.getenv("WHISPER_MODEL", "large-v3").strip()

class WhisperTranscriber:
    def __init__(self, model_size: str = None):
        from faster_whisper import WhisperModel
        if not model_size:
            model_size = os.getenv("WHISPER_MODEL", "large-v3").strip() or "large-v3"
        device = os.getenv("WHISPER_DEVICE", "cuda").strip().lower()
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "float16" if device == "cuda" else "int8").strip()
        print(f"[Whisper] Initializing model '{model_size}' on {device} ({compute_type})...")
        try:
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
            print(f"[Whisper] Loaded '{model_size}' successfully on {device} ({compute_type}).")
        except Exception as exc:
            err_msg = f"WHISPER_MODEL_LOAD_FAILED: Could not load Whisper model '{model_size}' on {device} ({compute_type}): {exc}"
            print(f"[Whisper] {err_msg}")
            raise RuntimeError(err_msg) from exc

    def transcribe(self, audio_path: str) -> list[SubtitleSegment]:
        print(f"[Whisper] Transcribing audio from {audio_path}...")
        # Bắt trọn vẹn 100% lời thoại nói nhanh, phân tách câu tự nhiên theo dấu câu và ngắt nghỉ
        segments, info = self.model.transcribe(
            str(audio_path),
            beam_size=5,
            temperature=[0.0, 0.2, 0.4],
            condition_on_previous_text=False,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300)
        )
        print(f"[Whisper] Detected language: {info.language} (probability: {info.language_probability:.2f})")
        
        punct = {',', '，', '。', '.', '!', '！', '?', '？', ';', '；', '\n'}
        results: list[SubtitleSegment] = []
        for seg in segments:
            words = getattr(seg, 'words', [])
            if not words:
                text = seg.text.strip()
                if text:
                    results.append(SubtitleSegment(float(seg.start), float(seg.end), text))
                continue

            # Phân tách thành từng câu ngắn tự nhiên dựa theo mốc từ và dấu câu
            cur_words = []
            seg_start = words[0].start
            for i, w in enumerate(words):
                cur_words.append(w.word)
                is_last = (i == len(words) - 1)
                has_punct = any(p in w.word for p in punct)
                pause = (words[i + 1].start - w.end) if not is_last else 0.0
                dur = w.end - seg_start
                
                if is_last or (has_punct and dur >= 1.0) or (pause >= 0.35 and dur >= 1.2) or dur >= 4.0:
                    txt = "".join(cur_words).strip()
                    clean_txt = txt.strip("，,。 .!！？?;\n")
                    if clean_txt:
                        results.append(SubtitleSegment(float(seg_start), float(w.end), clean_txt))
                    if not is_last:
                        seg_start = words[i + 1].start
                        cur_words = []

        print(f"[Whisper] Transcription finished. Total segments: {len(results)}")
        return results

def limit_repeated_words(text: str, max_repeat: int = 2) -> str:
    """
    If any word or short phrase repeats 3 or more times consecutively,
    limit it to repeat at most max_repeat (2) times.
    Example:
    - 'ngon ngon ngon ngon' -> 'ngon ngon'
    - 'này này này này mau lại đây' -> 'này này mau lại đây'
    - 'rất, rất, rất, rất là ngon' -> 'rất, rất là ngon'
    - 'aaaaa' -> 'aa'
    """
    if not text:
        return ""

    # 1. Pattern matches a word followed by 2 or more identical words separated by whitespace or punctuation
    pattern_word = re.compile(r'\b([\w\u00C0-\u1EF9]+)(?:[\s,–—\-]+(?:\1\b)){2,}', re.IGNORECASE | re.UNICODE)

    def repl_word(m):
        full = m.group(0)
        base = m.group(1)
        found = re.findall(r'\b' + re.escape(base) + r'\b', full, re.IGNORECASE)
        if len(found) > max_repeat:
            sep = ', ' if ',' in full else ' '
            return sep.join(found[:max_repeat])
        return full

    prev = None
    res = text
    while prev != res:
        prev = res
        res = pattern_word.sub(repl_word, res)

    # 2. Match 2-word phrases repeated 3+ times: e.g. 'ô kìa, ô kìa, ô kìa'
    pattern_phrase = re.compile(r'\b([\w\u00C0-\u1EF9]+\s+[\w\u00C0-\u1EF9]+)(?:[\s,–—\-]+(?:\1\b)){2,}', re.IGNORECASE | re.UNICODE)
    def repl_phrase(m):
        full = m.group(0)
        base = m.group(1)
        sep = ', ' if ',' in full else ' '
        return base + sep + base.lower()

    prev = None
    while prev != res:
        prev = res
        res = pattern_phrase.sub(repl_phrase, res)

    # 3. Clamping repeated letters in a single word: e.g. 'aaaaa' -> 'aa', 'haaaaa' -> 'haa'
    res = re.sub(r'([a-zA-Z\u00C0-\u1EF9])\1{2,}', r'\1\1', res)
    return res.strip()

def clean_ai_text(text: str) -> str:
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\*.*", "", text)
    text = limit_repeated_words(text, max_repeat=2)
    return text.strip()

def convert_currency_to_vnd(text: str, rate: int = 3700) -> str:
    """Converts Chinese Yuan / RMB / tệ to Vietnamese Dong naturally."""
    pattern = r"(\d+(?:\.\d+)?)\s*(nghin|van|nghìn|vạn)?\s*(te|nhan dan te|tệ|nhân dân tệ|¥|元|CNY)"
    def replace_match(m: re.Match) -> str:
        try:
            val = float(m.group(1))
            unit = str(m.group(2) or "").lower()
            if unit in {"van", "vạn"}:
                val *= 10000
            elif unit in {"nghin", "nghìn"}:
                val *= 1000
            vnd = int(val * rate)
            millions = vnd / 1000000
            if millions >= 1:
                if millions == int(millions):
                    return f"{int(millions)} triệu đồng"
                if (millions * 10) % 10 == 5:
                    return f"{int(millions)} triệu rưỡi"
                return f"{millions:.1f} triệu đồng".replace(".", ",")
            return f"{vnd // 1000} nghìn đồng"
        except Exception:
            return m.group(0)
    return re.sub(pattern, replace_match, text, flags=re.IGNORECASE)

def parse_srt_to_segments(srt_path: str) -> list[SubtitleSegment]:
    """Reads existing SRT file back into SubtitleSegment objects for checkpoint resume."""
    p = Path(srt_path)
    if not p.exists() or p.stat().st_size < 50:
        return []
    try:
        content = p.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        content = p.read_text(encoding="utf-8", errors="ignore")
        
    segments = []
    blocks = re.split(r'\n\s*\n', content.strip())
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) >= 2:
            time_line = None
            text_lines = []
            for idx, line in enumerate(lines):
                if '-->' in line:
                    time_line = line
                    text_lines = lines[idx + 1:]
                    break
            if time_line:
                parts = time_line.split('-->')
                if len(parts) == 2:
                    def to_sec(t_str):
                        pts = re.split('[:,]', t_str.strip())
                        if len(pts) == 4:
                            return int(pts[0]) * 3600 + int(pts[1]) * 60 + int(pts[2]) + int(pts[3]) / 1000.0
                        return 0.0
                    st = to_sec(parts[0])
                    et = to_sec(parts[1])
                    text = " ".join(text_lines).strip()
                    if text:
                        segments.append(SubtitleSegment(st, et, text))
    return segments

class SubtitleTranslator:
    def __init__(self, api_key: str = DEEPSEEK_API_KEY, model_name: str = "deepseek-chat"):
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured in backend/.env")
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.model_name = model_name

    def translate_segments(self, segments: list[SubtitleSegment], batch_size: int = 120) -> list[SubtitleSegment]:
        if not segments:
            return []
        
        translated_segments: list[SubtitleSegment] = []
        
        system_prompt = (
            "Bạn là chuyên gia dịch thuật và biên tập phụ đề phim truyện, phim ngắn (TikTok, Douyin) từ tiếng Trung sang tiếng Việt tự nhiên, chuẩn điện ảnh và giàu cảm xúc.\n\n"
            "⚠️ NGUYÊN TẮC TỐI QUAN TRỌNG VỀ ĐẠI TỪ NHÂN XƯNG VÀ GIỚI TÍNH (TRÁNH LỖI ĐỒNG ÂM TĀ / 他 / 她):\n"
            "1. CẢNH BÁO LỖI ĐỒNG ÂM: Trong tiếng Trung, '他' (anh ấy/hắn) và '她' (cô ấy/nàng) phát âm giống hệt nhau là 'tā'. Bản nhận diện âm thanh thường bị gõ nhầm chữ Hán giữa nam và nữ.\n"
            "2. PHÂN BIỆT GIỚI TÍNH THEO HÀNH ĐỘNG VÀ MẠCH PHIM:\n"
            "   - Hãy đọc toàn bộ danh sách câu thoại để xác định rõ nhân vật: ai là NAM, ai là NỮ, mối quan hệ và hành động của họ.\n"
            "   - TUYỆT ĐỐI KHÔNG dịch máy móc chữ '他' thành 'anh ấy' nếu ngữ cảnh thực tế nhân vật hành động là NỮ (ví dụ: người vợ, bạn gái, cô gái đi gặp bạn trai, về nhà chồng/nhà mẹ, mang thai, trang điểm...). BẮT BUỘC dịch đúng là: 'cô ấy / nàng / cô gái / em / bà ấy'.\n"
            "   - Ngược lại, nhân vật NAM phải dịch là: 'anh ấy / chàng / hắn / chàng trai / ông ấy / anh'.\n"
            "   - TUYỆT ĐỐI KHÔNG ĐẢO LỘN CHỦ NGỮ - VỊ NGỮ: Giữ đúng logic quan hệ nhân vật (Ví dụ: 'Cô ấy về nhà anh ấy', 'Anh ấy đưa cô ấy về', không được đảo ngược thành 'Anh ấy về nhà cô ấy' nếu người về là nữ).\n"
            "   - TÍNH NHẤT QUÁN XUYÊN SUỐT: Cùng một nhân vật trong video phải giữ nguyên ngôi xưng từ đầu đến cuối, không được đoạn đầu gọi 'cô ấy' đoạn sau lại gọi 'anh ấy'.\n\n"
            "QUY TẮC XƯNG HÔ ĐỐI THOẠI TRỰC TIẾP:\n"
            "1. Tiếng Trung dùng '你' (nǐ) và '我' (wǒ) chung chung. Tuyệt đối KHÔNG dịch thành 'cậu - tớ' hay 'bạn - tôi'.\n"
            "2. Dùng đại từ tự nhiên:\n"
            "   - Nam nữ / người yêu / vợ chồng: Dùng 'anh - em'.\n"
            "   - Bạn bè thân thiết, trêu đùa: Dùng 'mày - tao' hoặc 'ông - tôi'.\n"
            "   - Gia đình: Dùng đúng vai vế 'bố/mẹ - con', 'anh/chị - em'.\n"
            "   - Thú cưng / linh vật với người nuôi: Dùng 'chủ nhân' hoặc 'anh/chị - em/con'.\n"
            "   - Người dẫn chuyện / Review phim: Dùng 'cô ấy / anh ấy / chàng trai / cô gái' hoặc gọi tên nhân vật (Tiểu Mỹ, Đại Tráng...).\n"
            "3. LƯỢC BỎ đại từ thừa khi tiếng Việt tự nhiên không cần nhắc lại.\n"
            "4. QUY TẮC LẶP TỪ: Nếu có từ lặp liên tiếp từ 3 lần trở lên (như 'a a a a', 'ngon ngon ngon...'), hãy rút gọn chỉ giữ tối đa 2 lần ('a a', 'ngon ngon').\n"
            "5. ĐỊNH DẠNG BẮT BUỘC: Giữ đúng định dạng '[số] nội dung dịch' trên mỗi dòng, không thêm bất kỳ lời giải thích hay ký tự thừa nào."
        )
        
        for i in range(0, len(segments), batch_size):
            batch = segments[i:i + batch_size]
            prompt_lines = [f"[{idx+1}] {seg.text}" for idx, seg in enumerate(batch)]
            prompt_text = "\n".join(prompt_lines)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text}
            ]
            
            try:
                print(f"[Translator] Translating batch {i+1} to {min(i+batch_size, len(segments))} via DeepSeek...")
                resp = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.3
                )
                content = resp.choices[0].message.content or ""
                
                # Parse translations
                translations: dict[int, str] = {}
                for line in content.strip().split("\n"):
                    match = re.match(r"\[(\d+)\][:\s]*(.*)", line.strip())
                    if match:
                        num = int(match.group(1))
                        txt = convert_currency_to_vnd(clean_ai_text(match.group(2)))
                        txt = limit_repeated_words(txt, max_repeat=2)
                        translations[num] = txt
                
                for idx, seg in enumerate(batch):
                    vi_text = translations.get(idx + 1, seg.text)
                    translated_segments.append(SubtitleSegment(seg.start, seg.end, vi_text))
            except Exception as e:
                print(f"[Translator] Translation error on batch: {e}. Fallback to original text.")
                for seg in batch:
                    translated_segments.append(seg)
                    
        return translated_segments

def write_srt(segments: list[SubtitleSegment], output_path: str) -> str:
    """Writes segments to standard SRT format."""
    with open(output_path, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments, start=1):
            start_str = format_timestamp(seg.start)
            end_str = format_timestamp(seg.end)
            f.write(f"{idx}\n{start_str} --> {end_str}\n{seg.text}\n\n")
    return output_path

_cached_transcriber = None

def get_transcriber(model_size: str = DEFAULT_WHISPER_MODEL) -> WhisperTranscriber:
    global _cached_transcriber
    if _cached_transcriber is None or getattr(_cached_transcriber, '_model_size', None) != model_size:
        _cached_transcriber = WhisperTranscriber(model_size=model_size)
        _cached_transcriber._model_size = model_size
    return _cached_transcriber

def generate_vietnamese_subtitles(video_path: str, output_srt_path: str, progress_callback=None, force: bool = False) -> tuple[str, list[SubtitleSegment]]:
    """End-to-end extraction -> transcribe -> translate -> SRT (Hỗ trợ Checkpoint Resume)."""
    # 0. Checkpoint Resume: Nếu đã có file SRT hợp lệ trước đó thì tái sử dụng ngay lập tức
    if not force and os.path.exists(output_srt_path):
        existing_segs = parse_srt_to_segments(output_srt_path)
        if existing_segs:
            print(f"[SubProcessor] [RESUME] Đã tìm thấy file phụ đề SRT hoàn chỉnh ({len(existing_segs)} câu): {output_srt_path}. Bỏ qua Whisper & DeepSeek!")
            return output_srt_path, existing_segs
    temp_audio = str(Path(output_srt_path).with_suffix(".wav"))
    try:
        if progress_callback:
            progress_callback("extract_audio")
        extract_audio_for_transcription(video_path, temp_audio)
        
        if progress_callback:
            progress_callback("transcribing")
        transcriber = get_transcriber(DEFAULT_WHISPER_MODEL)
        segments = transcriber.transcribe(temp_audio)
        
        if not segments:
            print("[SubProcessor] No speech detected in video.")
            write_srt([], output_srt_path)
            return output_srt_path
            
        if progress_callback:
            progress_callback("translating")
        translator = SubtitleTranslator()
        vi_segments = translator.translate_segments(segments)
        
        write_srt(vi_segments, output_srt_path)
        print(f"[SubProcessor] Saved Vietnamese SRT to: {output_srt_path}")
        return output_srt_path, vi_segments
    finally:
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except Exception:
                pass

VOICE_PROFILES = {
    # Backward-compatible built-in profiles. channels_config.json can override/add voices.
    "nu_tre": {"engine": "edge", "voice": "vi-VN-HoaiMyNeural", "pitch": "+8Hz", "rate": "+50%"},
    "nu_tram": {"engine": "edge", "voice": "vi-VN-HoaiMyNeural", "pitch": "-6Hz", "rate": "+20%"},
    "google": {"engine": "google"},
    "hoaimy": {"engine": "edge", "voice": "vi-VN-HoaiMyNeural", "pitch": "+0Hz", "rate": "+50%"},
    "nam_minh": {"engine": "edge", "voice": "vi-VN-NamMinhNeural", "pitch": "+0Hz", "rate": "+50%"},
}


async def _render_tts_chunk(text: str, profile: dict, out_file: str, speed: float = 1.5) -> str | None:
    """Render one TTS chunk and return the actual generated file path."""
    clean = re.sub(r'[*_#`~]', '', text).strip()
    clean = limit_repeated_words(clean, max_repeat=2)
    if not clean or len(clean) < 2:
        return None

    engine = str(profile.get("engine", "edge")).strip().lower()
    effective_speed = max(0.5, min(float(speed or 1.0) * float(profile.get("speed_multiplier", 1.0) or 1.0), 2.5))
    require_clone = bool(profile.get("require_clone", False))

    if engine in {"omnivoice", "khanh_omnivoice", "khanhtts"}:
        try:
            from omnivoice_service import get_omnivoice_service
            service = get_omnivoice_service()
            wav_path = str(Path(out_file).with_suffix(".wav"))
            await asyncio.to_thread(
                service.synthesize,
                clean,
                Path(wav_path),
                profile,
                effective_speed,
            )
            if os.path.exists(wav_path) and os.path.getsize(wav_path) > 100:
                return wav_path
        except Exception as exc:
            print(f"[TTS][OmniVoice] Lỗi clone voice: {exc}")
            if require_clone:
                raise RuntimeError(
                    f"CLONE_FAILED: OmniVoice clone thất bại ({exc}). "
                    "Profile yêu cầu bắt buộc clone (require_clone=True) nên hệ thống dừng, không đổi sang Hoài My."
                ) from exc

        # Fail-soft only when require_clone is False (e.g. preset channels)
        fallback_key = str(profile.get("fallback_voice") or "nu_tre")
        fallback_profile = dict(VOICE_PROFILES.get(fallback_key) or VOICE_PROFILES["nu_tre"])
        fallback_path = str(Path(out_file).with_suffix(".fallback.mp3"))
        print(f"[TTS][OmniVoice] Chuyển sang fallback voice: {fallback_key}")
        return await _render_tts_chunk(clean, fallback_profile, fallback_path, speed=effective_speed)

    if engine == "google":
        import urllib.request
        import urllib.parse
        for attempt in range(3):
            try:
                mp3_path = str(Path(out_file).with_suffix(".mp3"))
                url = "https://translate.google.com/translate_tts?ie=UTF-8&q=" + urllib.parse.quote(clean) + "&tl=vi&client=tw-ob"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = resp.read()

                if abs(effective_speed - 1.0) > 0.001:
                    raw_tmp = mp3_path + ".raw.mp3"
                    with open(raw_tmp, "wb") as f:
                        f.write(data)
                    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", raw_tmp, "-filter:a", f"atempo={effective_speed}", mp3_path]
                    subprocess.run(cmd, check=True)
                    if os.path.exists(raw_tmp):
                        os.remove(raw_tmp)
                else:
                    with open(mp3_path, "wb") as f:
                        f.write(data)

                if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
                    return mp3_path
            except Exception:
                await asyncio.sleep(0.5)
        return None

    if require_clone:
        raise RuntimeError(
            f"CLONE_FAILED: Profile cấu hình require_clone=True nhưng engine '{engine}' không phải engine clone!"
        )

    # Edge-TTS
    voice_name = profile.get("voice", "vi-VN-HoaiMyNeural")
    pitch = profile.get("pitch", "+0Hz")
    pct = int(round((effective_speed - 1.0) * 100))
    rate = f"+{pct}%" if pct >= 0 else f"{pct}%"
    mp3_path = str(Path(out_file).with_suffix(".mp3"))

    for attempt in range(3):
        try:
            comm = edge_tts.Communicate(clean, voice_name, pitch=pitch, rate=rate)
            await comm.save(mp3_path)
            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
                return mp3_path
        except Exception:
            await asyncio.sleep(0.5)
    return None


def _build_audio_manifest(
    segments: list[SubtitleSegment],
    voice: str,
    speed: float,
    profile: dict,
) -> dict[str, Any]:
    ref_audio = str(profile.get("ref_audio") or "")
    ref_hash = ""
    if ref_audio and os.path.exists(ref_audio):
        try:
            ref_hash = hashlib.sha256(Path(ref_audio).read_bytes()).hexdigest()[:16]
        except Exception:
            pass
    seg_summary = "|".join(f"{s.start:.2f}-{s.end:.2f}:{s.text}" for s in segments)
    seg_hash = hashlib.sha256(seg_summary.encode("utf-8")).hexdigest()[:16]
    return {
        "voice": voice,
        "engine": str(profile.get("engine", "edge")),
        "speed": round(float(speed), 3),
        "ref_audio": ref_audio,
        "ref_hash": ref_hash,
        "require_clone": bool(profile.get("require_clone", False)),
        "seg_hash": seg_hash,
    }


def generate_dubbed_audio(
    segments: list[SubtitleSegment],
    output_audio_path: str,
    voice: str = "nu_tre",
    speed: float = 1.0,
    total_duration_sec: float | None = None,
    force: bool = False,
    voice_profile: dict | None = None,
) -> str:
    """
    Generates a synchronized dubbed track with strict validation and no silent fallback.
    """
    profile = dict(voice_profile or VOICE_PROFILES.get(voice) or {})
    if not profile:
        profile = dict(VOICE_PROFILES["nu_tre"])
    engine = str(profile.get("engine", "edge")).strip().lower()
    effective_speed = max(0.5, min(float(speed or 1.0) * float(profile.get("speed_multiplier", 1.0) or 1.0), 2.5))
    manifest_path = Path(output_audio_path).with_suffix(".manifest.json")
    current_manifest = _build_audio_manifest(segments, voice, speed, profile)

    if not force and os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 1000:
        if manifest_path.exists():
            try:
                saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if saved_manifest == current_manifest:
                    print(f"[SubProcessor] [RESUME] File âm thanh khớp chính xác cấu hình & phụ đề: {output_audio_path}. Bỏ qua bước tạo lại!")
                    return output_audio_path
            except Exception:
                pass

    if not segments:
        silent = AudioSegment.silent(duration=int((total_duration_sec or 5) * 1000))
        silent.export(output_audio_path, format="wav")
        return output_audio_path

    # Router / Zero-shot clone flow
    if engine in {"router", "omnivoice", "khanh_omnivoice", "khanhtts", "vieneu"}:
        try:
            from . import voice_router
        except Exception:
            import voice_router

        temp_srt = Path(output_audio_path).with_suffix(".temp_track.srt")
        with open(temp_srt, "w", encoding="utf-8") as f:
            for i, s in enumerate(segments, 1):
                def _fmt(sec):
                    h = int(sec // 3600)
                    m = int((sec % 3600) // 60)
                    s_rem = sec % 60
                    return f"{h:02d}:{m:02d}:{int(s_rem):02d},{int((s_rem - int(s_rem))*1000):03d}"
                f.write(f"{i}\n{_fmt(s.start)} --> {_fmt(s.end)}\n{s.text}\n\n")

        router_cfg = {
            "engine": engine if engine in {"omnivoice", "khanh_omnivoice", "vieneu"} else "router",
            "model": profile.get("model", "kjanh/KhanhTTS-OmniVoice"),
            "speed": effective_speed,
            "require_clone": bool(profile.get("require_clone", False)),
            "reference": {
                "audio": profile.get("ref_audio"),
                "text": profile.get("ref_text"),
            },
            "voice": profile.get("voice", "nu_tre"),
            "duration_match": {
                "enabled": True,
                "target_fill_ratio": 0.95,
                "max_speedup": 1.30,
                "max_slowdown": 1.10,
            }
        }

        try:
            res_wav = voice_router.render_srt_voice_track(
                srt_path=temp_srt,
                output_wav=output_audio_path,
                cfg=router_cfg,
                video_duration=total_duration_sec,
                reference_audio=profile.get("ref_audio"),
                reference_text=profile.get("ref_text"),
            )
            manifest_path.write_text(json.dumps(current_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            return res_wav
        finally:
            if temp_srt.exists():
                try:
                    temp_srt.unlink()
                except Exception:
                    pass

    # Preset / Standard flow (Edge-TTS / Google) with overlap prevention
    max_end = max(seg.end for seg in segments)
    if total_duration_sec and total_duration_sec > max_end:
        max_end = total_duration_sec
    base_track = AudioSegment.silent(duration=int((max_end + 3) * 1000))

    temp_dir = Path(output_audio_path).parent / "tts_chunks"
    temp_dir.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(4)

    async def _worker(idx: int, seg: SubtitleSegment):
        chunk_base = str(temp_dir / f"chunk_{idx}_{int(time.time()*1000)}")
        async with sem:
            actual_file = await _render_tts_chunk(seg.text, profile, chunk_base, speed=effective_speed)
            return idx, seg, actual_file

    async def _process_all():
        tasks = [_worker(idx, seg) for idx, seg in enumerate(segments)]
        return await asyncio.gather(*tasks)

    results = asyncio.run(_process_all())

    for idx, seg, chunk_file in sorted(results, key=lambda r: r[0]):
        if chunk_file and os.path.exists(chunk_file):
            try:
                audio_clip = AudioSegment.from_file(chunk_file)
                clip_dur = len(audio_clip) / 1000.0

                # Check slot to prevent speech overlap
                next_start = segments[idx + 1].start if idx + 1 < len(segments) else (total_duration_sec or (seg.end + 2.0))
                avail_dur = max(seg.end - seg.start, next_start - seg.start - 0.08)

                if clip_dur > avail_dur and avail_dur > 0.1:
                    stretch = min(1.30, clip_dur / avail_dur)
                    audio_clip = audio_clip.speedup(playback_speed=stretch)

                pos_ms = int(seg.start * 1000)
                base_track = base_track.overlay(audio_clip, position=pos_ms)
            except Exception as exc:
                print(f"[TTS] Error overlaying segment {idx}: {exc}")
            finally:
                try:
                    os.remove(chunk_file)
                except Exception:
                    pass

    base_track.export(output_audio_path, format="wav")
    manifest_path.write_text(json.dumps(current_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[TTS] Exported dubbed voice track ({voice}, engine={engine}) to: {output_audio_path}")
    return output_audio_path


def slugify_vietnamese(text: str) -> str:
    """
    Chuyển tên phim / tiêu đề sang dạng không dấu, viết thường, cách nhau dấu gạch dưới '_'.
    Ví dụ: 'Chàng Rể Ma Thần - Tập 1' -> 'chang_re_ma_than_tap_1'
    """
    if not text:
        return f"video_{int(time.time())}"
    # Xử lý đ, Đ trước
    text = text.replace('đ', 'd').replace('Đ', 'd')
    # Chuẩn hoá Unicode tách dấu
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    # Thay thế các ký tự không phải chữ số thành dấu gạch dưới
    text = re.sub(r'[^a-zA-Z0-9]+', '_', text)
    slug = re.sub(r'_+', '_', text).strip('_').lower()
    return slug or f"video_{int(time.time())}"

def generate_movie_title(raw_title: str = "", segments: list[SubtitleSegment] | None = None) -> tuple[str, str]:
    """
    Sử dụng DeepSeek AI để đặt TÊN PHIM tiếng Việt ngắn gọn, hấp dẫn và tạo slug không dấu cách nhau dấu '_'.
    Trả về: (title_vi, slug)
    Ví dụ: ('Chiến Thần Trở Lại Tập 1', 'chien_than_tro_lai_tap_1')
    """
    dialogue_context = ""
    if segments:
        dialogue_context = "\n".join(f"- {s.text}" for s in segments[:10] if getattr(s, 'text', '') and s.text.strip())

    cleaned_raw = re.sub(r'https?://\S+', '', raw_title or '').strip()
    cleaned_raw = re.sub(r'#\S+', '', cleaned_raw).strip()

    if not cleaned_raw and not dialogue_context:
        default_title = "Video Lồng Tiếng"
        return default_title, slugify_vietnamese(default_title)

    prompt = (
        "Bạn là chuyên gia đặt tên phim ngắn và video TikTok/Douyin cuốn hút nhất.\n"
        "Nhiệm vụ: Đặt một TÊN PHIM hoặc TIÊU ĐỀ VIDEO tiếng Việt ngắn gọn (3 đến 7 từ), "
        "chuẩn đúng ngữ cảnh câu chuyện từ các thông tin sau:\n"
    )
    if cleaned_raw:
        prompt += f"Tiêu đề/mô tả gốc: {cleaned_raw}\n"
    if dialogue_context:
        prompt += f"Các câu thoại trong video:\n{dialogue_context}\n"
    prompt += (
        "\nQUY TẮC:\n"
        "1. Đặt tên tiếng Việt tự nhiên, kèm 'Tập X' nếu nhận diện được tập.\n"
        "2. Không hashtag, không icon, không dấu ngoặc kép thừa.\n"
        "3. CHỈ TRẢ VỀ ĐÚNG 1 DÒNG DUY NHẤT LÀ TÊN PHIM/TIÊU ĐỀ."
    )

    try:
        if DEEPSEEK_API_KEY:
            client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Bạn là chuyên gia đặt tên phim ngắn tiếng Việt. Chỉ trả về 1 dòng tên duy nhất."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=60
            )
            title = resp.choices[0].message.content.strip().replace('"', '').replace("'", "")
            title = re.sub(r'^[#*\-•\s]+', '', title).strip()
            if title and len(title) > 2:
                slug = slugify_vietnamese(title)
                # Giới hạn slug tối đa 60 ký tự
                if len(slug) > 60:
                    slug = "_".join(slug[:60].rstrip("_").split("_"))
                return title, slug
    except Exception as e:
        print(f"[TitleGenerator] Lỗi DeepSeek đặt tên phim: {e}")

    fallback_title = cleaned_raw if cleaned_raw else "Video_Vi"
    slug = slugify_vietnamese(fallback_title)
    return fallback_title, slug

def generate_movie_caption(
    movie_title: str,
    raw_title: str = "",
    segments: list[SubtitleSegment] | None = None,
    workflow: str = "film_review_black"
) -> str:
    """
    Sinh bài viết (Caption) đăng Facebook Reel / TikTok / Shorts.
    - Cấu hình 1 (Wuby / Hoạt hình): Ngắn gọn, dễ thương, không icon xe tải!
    - Cấu hình 2 (Review Phim): Chuẩn mẫu tóm tắt kịch tính, dùng icon điện ảnh.
    """
    title_upper = movie_title.strip().upper()
    is_wuby = (workflow == "wuby" or "wuby" in str(workflow).lower() or "quby" in str(workflow).lower())

    dialogue_context = ""
    if segments:
        dialogue_context = "\n".join(f"- {s.text}" for s in segments[:15] if getattr(s, 'text', '') and s.text.strip())

    if is_wuby:
        # Cấu hình Wuby: Ngắn gọn, dễ thương, icon ✨ / 🎀
        summary_hook = ""
        if DEEPSEEK_API_KEY:
            try:
                prompt = (
                    f"Tiêu đề hoạt hình: {movie_title}\n"
                    f"Nội dung/thoại:\n{dialogue_context or raw_title}\n\n"
                    "Nhiệm vụ: Viết đúng 1 câu cực ngắn gọn (dưới 20 từ), hài hước, dễ thương về meme hoạt hình này. "
                    "Không dùng icon xe tải, không viết dài dòng. Chỉ trả về đúng 1 câu duy nhất."
                )
                client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
                resp = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "Bạn là chuyên gia viết caption hoạt hình/meme ngắn gọn, dễ thương, hài hước."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.5,
                    max_tokens=60
                )
                summary_hook = resp.choices[0].message.content.strip().replace('"', '').replace("'", "")
            except Exception as e:
                print(f"[CaptionGenerator] Lỗi DeepSeek sinh caption Wuby: {e}")

        if not summary_hook:
            summary_hook = f"Coi chừng đúng với bạn và đứa bạn thân nha! 😂"

        caption = (
            f"✨ {title_upper} ✨\n"
            f"{summary_hook}\n\n"
            f"#wuby #quby #hoathinh #dangyeu #meme #cute #haihuoc #banthan"
        )
        return caption

    # Cấu hình Review Phim: Dùng icon điện ảnh 🎬 / 🔥 thay cho xe tải 🚚
    summary_hook = ""
    if DEEPSEEK_API_KEY:
        try:
            prompt = (
                f"Tên phim: {movie_title}\n"
                f"Nội dung/thoại của phim:\n{dialogue_context or raw_title}\n\n"
                "Nhiệm vụ: Viết đúng 1-2 câu tóm tắt cốt truyện kịch tính mở đầu (ngắn gọn, cuốn hút, gây tò mò) "
                "kết thúc bằng một câu hỏi gợi mở 'Liệu [ai đó] sẽ làm gì để...'.\n"
                "Quy tắc: Tiếng Việt tự nhiên, không chào hỏi, không thêm hashtag, không dùng icon xe tải, chỉ trả về đúng 1-2 câu tóm tắt."
            )
            client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Bạn là chuyên gia viết caption review phim kịch tính, ngắn gọn, cuốn hút."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=150
            )
            summary_hook = resp.choices[0].message.content.strip().replace('"', '').replace("'", "")
        except Exception as e:
            print(f"[CaptionGenerator] Lỗi DeepSeek sinh caption: {e}")

    if not summary_hook:
        summary_hook = f"Bộ phim ngắn đầy bất ngờ và kịch tính với câu chuyện xoay quanh {movie_title}... 😳 Liệu cái kết sẽ diễn ra như thế nào?"

    caption = (
        f"🎬 {title_upper} 🔥\n"
        f"{summary_hook} Cùng xem review để khám phá những tình tiết bất ngờ của bộ phim này nhé! 🍿\n\n"
        f"🎬 Phim hay thì kể, phim dở cũng tám!\n"
        f"👀 Vào Vũ Trụ Cày Phim coi có gì vui!\n\n"
        f"#VuTruCayPhim #MePhim #ReviewPhim #TomTatPhim #PhimHay #PhimDienAnh"
    )
    return caption



