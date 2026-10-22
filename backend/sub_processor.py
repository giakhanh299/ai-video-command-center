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
import sys as _v7_sys
_v7_project = str(Path(__file__).resolve().parents[1])
if _v7_project not in _v7_sys.path:
    _v7_sys.path.insert(0, _v7_project)
from dataclasses import dataclass

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

import asyncio
from pydub import AudioSegment
from dotenv import load_dotenv
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # Content APIs are optional for prepared local render/voice tests.

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()

@dataclass
class SubtitleSegment:
    start: float
    end: float
    text: str
    speaker: str = "wuby"

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

_RE_NON_SPEECH_TAGS = re.compile(
    r"^[\(\[\{（【]?(?:music|bgm|applause|laughter|screaming|cheering|gasp|sigh|groan|chuckle|snicker|crying|whispering|cough|throat-clearing|instrumental|sound effect|sfx|nhạc|âm nhạc|tiếng nhạc|âm thanh|tiếng cười|tiếng vỗ tay|音乐|音樂|背景音乐|掌声|笑声|喘息|叹气|欢呼)[\)\]\}）】]?$",
    re.IGNORECASE
)
_RE_ISOLATED_MUSIC = re.compile(r"^(?:nhạc|âm nhạc|tiếng nhạc|music|bgm|sfx|音乐|音樂)$", re.IGNORECASE)

_HALLUCINATION_KEYWORDS = [
    # English
    "thanks for watching", "thank you for watching", "please subscribe", "like and subscribe",
    "subscribe to my channel", "don't forget to subscribe", "subtitles by", "closed captions by",
    "thank you for joining us", "thanks for joining us",
    # Chinese
    "明镜需要您的支持", "欢迎收看订阅明镜", "欢迎收看", "欢迎订阅", "歡迎訂閱", "謝謝觀看", "谢谢观看",
    "谢谢收看", "謝謝收看", "请订阅", "請訂閱", "点赞关注", "點贊關注", "感谢您的收看", "字幕志愿者",
    # Vietnamese
    "cảm ơn đã xem", "cảm ơn các bạn đã xem", "cảm ơn bạn đã xem", "cảm ơn mọi người đã xem",
    "cảm ơn đã theo dõi", "cảm ơn bạn đã theo dõi", "cảm ơn các bạn đã theo dõi", "cảm ơn mọi người đã theo dõi",
    "cảm ơn bạn rất nhiều vì đã tham gia", "cảm ơn các bạn đã tham gia", "cảm ơn đã tham gia",
    "tham gia cùng chúng tôi", "hẹn gặp lại ở video tiếp theo", "hẹn gặp lại các bạn",
    "hãy like và subscribe", "đăng ký kênh", "phụ đề bởi", "thuyết minh bởi", "tình nguyện viên phụ đề",
    "người dịch:", "phụ đề:", "dịch thuật bởi",
    # Korean & Indonesian / other
    "자막은 설정", "시청해 주셔서", "구독과 좋아요", "jangan lupa subscribe", "jangan lupa like"
]

_RE_REPETITIVE_ONOMATOPOEIA = re.compile(
    r"^(?:[wW]oo[! ]*|[aA]hh?[! ]*|[oO]hh?[! ]*|[uU]hh?[! ]*|[hH]mm?[! ]*|[yY]eah[! ]*|[nN]o[! ]*|[lLaA]{2,}[! ]*)+$"
)
_RE_LAUGHTER = re.compile(
    r"^(?:[hH][aAeEiIoOuU][,.\s!?-]*|[hH][iI][,.\s!?-]*|[hH][eE][,.\s!?-]*|[hH][oO][,.\s!?-]*|[hH][uU][,.\s!?-]*|[aA][,.\s!?-]*|[aA][hH][,.\s!?-]*|[oO][hH][,.\s!?-]*)+$",
    re.IGNORECASE
)
_LAUGHTER_WORDS = {
    "ha", "haha", "hahaha", "hahahaha", "hic", "hi", "hihi", "hihihi",
    "he", "hehe", "hehehe", "ho", "hoho", "hohoho", "hu", "huhu", "huhuhu",
    "a", "ah", "aha", "uh", "oh", "cuoi", "tieng", "nhac"
}

def is_whisper_hallucination(text: str, duration: float = 0.0, lang_prob: float = 1.0, lang: str = "") -> bool:
    clean = (text or "").strip().lower()
    if not clean:
        return True
    
    # 1. Non-speech, music tags, or pure laughter
    if _RE_NON_SPEECH_TAGS.match(clean) or _RE_ISOLATED_MUSIC.match(clean) or _RE_LAUGHTER.match(clean):
        return True
    
    clean_no_punct = re.sub(r'[^\w\s\u4e00-\u9fff\uac00-\ud7af\u00C0-\u1EF9]', '', clean).strip()
    words_lp = clean_no_punct.split()
    if words_lp and all(
        w in _LAUGHTER_WORDS or
        bool(re.fullmatch(r"^(?:ha+|he+|hi+|ho+|hu+|hic+|a+|ah+|oh+|uh+|haha+|hehe+|hihi+|hoho+|huhu+)+$", w, re.IGNORECASE))
        for w in words_lp
    ):
        return True
    for kw in _HALLUCINATION_KEYWORDS:
        kw_l = kw.lower()
        if kw_l in clean:
            return True
        kw_clean = re.sub(r'[^\w\s\u4e00-\u9fff\uac00-\ud7af\u00C0-\u1EF9]', '', kw_l).strip()
        if kw_clean and kw_clean in clean_no_punct:
            return True

    # 3. Repetitive onomatopoeia/sound words (e.g. "Woo! Woo! Woo!")
    if _RE_REPETITIVE_ONOMATOPOEIA.match(clean):
        return True

    # 4. Low language probability combined with long duration single segment (characteristic of hallucination)
    if lang_prob < 0.40 and duration > 5.0 and len(clean.split()) <= 8:
        return True

    # 5. Low-entropy stutter on long duration (e.g. "đó là bởi vì bởi vì" over 4+ seconds)
    words = clean.split()
    if len(words) >= 4:
        if words[-1] == words[-3] and words[-2] == words[-4]:
            if duration > 4.0 and len(words) <= 8:
                return True
    if len(words) <= 4 and duration > 6.0:
        return True

    return False


def prune_intersegment_repetition_loops(segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
    """
    Detects and prunes consecutive segment repetition loops produced by Whisper
    during music/silence/low SNR (e.g. 7 consecutive segments saying 'Tôi là' or '我是').
    If a short phrase (<= 3 words or <= 12 characters) repeats consecutively 3 or more times,
    the repeating hallucinated loop segments are removed.
    """
    if len(segments) < 3:
        return segments

    cleaned: list[SubtitleSegment] = []
    i = 0
    while i < len(segments):
        txt_i = re.sub(r'[^\w\s\u4e00-\u9fff\u00C0-\u1EF9]', '', segments[i].text.lower()).strip()
        words_i = txt_i.split()
        
        # Check if segment text is short and repeats consecutively
        if len(words_i) <= 3 or len(txt_i) <= 12:
            j = i + 1
            while j < len(segments):
                txt_j = re.sub(r'[^\w\s\u4e00-\u9fff\u00C0-\u1EF9]', '', segments[j].text.lower()).strip()
                if txt_j == txt_i:
                    j += 1
                else:
                    break
            run_length = j - i
            if run_length >= 3:
                print(f"[Whisper] Phát hiện và loại bỏ vòng lặp ảo giác ({run_length} lần): '{segments[i].text}'")
                i = j  # Skip all looping hallucination segments
                continue

        cleaned.append(segments[i])
        i += 1
    return cleaned


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
        try:
            segments, info = self.model.transcribe(
                str(audio_path),
                beam_size=5,
                temperature=[0.0, 0.2, 0.4],
                condition_on_previous_text=False,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300)
            )
        except (ValueError, Exception) as vad_err:
            if "empty sequence" in str(vad_err) or "No active speech" in str(vad_err):
                print(f"[Whisper] VAD: Không phát hiện đoạn thoại nào trong audio ({vad_err}).")
                return []
            raise
        print(f"[Whisper] Detected language: {info.language} (probability: {info.language_probability:.2f})")
        
        punct = {',', '，', '。', '.', '!', '！', '?', '？', ';', '；', '\n'}
        results: list[SubtitleSegment] = []
        for seg in segments:
            words = getattr(seg, 'words', [])
            dur_seg = float(seg.end) - float(seg.start)
            if not words:
                text = seg.text.strip()
                if text and not is_whisper_hallucination(text, duration=dur_seg, lang_prob=info.language_probability, lang=info.language):
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
                cur_chars = sum(len(w) for w in cur_words)
                if is_last or (has_punct and dur >= 0.8) or (pause >= 0.25 and dur >= 1.0) or (dur >= 2.5 and pause >= 0.15) or dur >= 3.2 or cur_chars >= 14:
                    txt = "".join(cur_words).strip()
                    clean_txt = txt.strip("，,。 .!！？?;\n")
                    if clean_txt and not is_whisper_hallucination(clean_txt, duration=dur, lang_prob=info.language_probability, lang=info.language):
                        results.append(SubtitleSegment(float(seg_start), float(w.end), clean_txt))
                    if not is_last:
                        seg_start = words[i + 1].start
                        cur_words = []

        results = prune_intersegment_repetition_loops(results)
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

def split_long_segments(segments: list[SubtitleSegment], max_words: int = 12, max_chars: int = 44) -> list[SubtitleSegment]:
    """
    Splits any excessively long subtitle segment into two (or more) balanced, natural clauses.
    Interpolates timestamps proportionally to text length so voiceover pacing remains perfectly synchronized.
    """
    out: list[SubtitleSegment] = []
    for seg in segments:
        text = (seg.text or "").strip()
        words = text.split()
        dur = float(seg.end) - float(seg.start)
        
        # If segment is within comfortable length or too short in time to split, keep as is
        if (len(words) <= max_words and len(text) <= max_chars) or dur < 1.4:
            out.append(seg)
            continue

        # Find best natural split point near the middle
        split_idx = -1
        mid_word = len(words) // 2
        
        # 1. Look for punctuation near center (+- 3 words): comma, semicolon, dash
        best_punct_dist = 999
        for idx in range(max(1, mid_word - 3), min(len(words) - 1, mid_word + 4)):
            if any(p in words[idx] for p in [',', ';', '–', '—', '-', ':', '...']):
                dist = abs(idx - mid_word)
                if dist < best_punct_dist:
                    best_punct_dist = dist
                    split_idx = idx + 1
                    
        # 2. If no punctuation, check for natural conjunctions/prepositions
        if split_idx < 0:
            conjunctions = {'nhưng', 'và', 'mà', 'thì', 'để', 'khi', 'bởi', 'vì', 'rồi', 'nên', 'nếu', 'hoặc', 'hay', 'với', 'trong', 'ngay'}
            best_conj_dist = 999
            for idx in range(max(1, mid_word - 2), min(len(words) - 1, mid_word + 3)):
                w_clean = words[idx].lower().strip(',.!?–—')
                if w_clean in conjunctions:
                    dist = abs(idx - mid_word)
                    if dist < best_conj_dist:
                        best_conj_dist = dist
                        split_idx = idx
                        
        # 3. Fallback: split at exact mid_word
        if split_idx <= 0 or split_idx >= len(words):
            split_idx = mid_word

        part1_words = words[:split_idx]
        part2_words = words[split_idx:]
        t1 = " ".join(part1_words).rstrip(',;:- ')
        t2 = " ".join(part2_words).lstrip(',;:- ')
        
        len1 = max(1, len(t1))
        len2 = max(1, len(t2))
        total_len = len1 + len2
        
        # Proportional timestamp split with at least 0.5s per sub-segment
        split_time = seg.start + (dur * (len1 / total_len))
        split_time = round(max(seg.start + 0.5, min(seg.end - 0.5, split_time)), 3)
        
        out.append(SubtitleSegment(seg.start, split_time, t1))
        out.append(SubtitleSegment(split_time, seg.end, t2))
    return out

def merge_adjacent_micro_segments(
    segments: list[SubtitleSegment],
    min_dur: float = 1.1,
    max_gap: float = 0.45,
    max_combined_words: int = 12
) -> list[SubtitleSegment]:
    """
    Gộp các câu/cụm từ siêu ngắn sát nhau (gap <= max_gap) thành một câu hoàn chỉnh.
    Khắc phục triệt để lỗi tách từ cụt ngủn như 'ngủ ngon' (0.5s) và 'vợ đẹp' (2.8s) đứng sát nhau.
    """
    if len(segments) < 2:
        return segments

    merged: list[SubtitleSegment] = []
    i = 0
    while i < len(segments):
        curr = segments[i]
        if i + 1 < len(segments):
            nxt = segments[i + 1]
            gap = float(nxt.start) - float(curr.end)
            curr_dur = float(curr.end) - float(curr.start)
            nxt_dur = float(nxt.end) - float(nxt.start)
            curr_words = len(curr.text.split())
            nxt_words = len(nxt.text.split())
            combined_words = curr_words + nxt_words

            if gap <= max_gap and (curr_dur < min_dur or curr_words <= 2 or nxt_dur < min_dur or nxt_words <= 2) and combined_words <= max_combined_words:
                sep = ", " if not curr.text.endswith((",", ".", "!", "?", "…")) else " "
                combined_text = f"{curr.text.rstrip(' ,.!?')}{sep}{nxt.text.lstrip()}"
                merged.append(SubtitleSegment(float(curr.start), float(nxt.end), combined_text))
                i += 2
                continue

        merged.append(curr)
        i += 1
    return merged

def merge_chinese_orphan_segments(
    segments: list[SubtitleSegment],
    max_gap: float = 0.5
) -> list[SubtitleSegment]:
    """
    Gộp các âm tiết tiếng Trung bị Whisper tách rời rạc (ví dụ 1 chữ Hán đơn lẻ như '妈', '啊', '嗯'
    ngay sau câu trước) để tạo thành từ/câu hoàn chỉnh trước khi gửi qua LLM dịch.
    """
    if len(segments) < 2:
        return segments

    merged: list[SubtitleSegment] = []
    i = 0
    while i < len(segments):
        curr = segments[i]
        if i + 1 < len(segments):
            nxt = segments[i + 1]
            gap = float(nxt.start) - float(curr.end)
            nxt_dur = float(nxt.end) - float(nxt.start)
            nxt_len = len(re.sub(r'[\s,.!?，。！？]', '', nxt.text))
            if gap <= max_gap and (nxt_len <= 2 or nxt_dur < 0.5):
                combined_text = f"{curr.text.strip()}{nxt.text.strip()}"
                merged.append(SubtitleSegment(float(curr.start), float(nxt.end), combined_text))
                i += 2
                continue
        merged.append(curr)
        i += 1
    return merged

def resolve_overlapping_segments(
    segments: list[SubtitleSegment],
    min_gap: float = 0.04
) -> list[SubtitleSegment]:
    """
    Khắc phục triệt để lỗi OVERLAPPING_DIALOGUE.
    Đảm bảo tất cả các câu phụ đề tăng dần theo thời gian và không bị chồng chéo thời gian lên nhau.
    """
    if len(segments) < 2:
        return segments

    # Sắp xếp các câu theo thời gian bắt đầu
    sorted_segs = sorted(segments, key=lambda s: (float(s.start), float(s.end)))
    resolved: list[SubtitleSegment] = []

    for seg in sorted_segs:
        st = float(seg.start)
        et = float(seg.end)
        if et <= st + 0.1:
            et = st + 0.3

        if not resolved:
            resolved.append(SubtitleSegment(round(st, 3), round(et, 3), seg.text, getattr(seg, 'speaker', 'wuby')))
            continue

        prev = resolved[-1]
        prev_st = float(prev.start)
        prev_et = float(prev.end)

        # Kiểm tra va chạm / chồng lấn thời gian
        if st < prev_et + min_gap:
            overlap = (prev_et + min_gap) - st
            prev_dur = prev_et - prev_st
            curr_dur = et - st

            # Trường hợp 1: prev có đủ thời lượng để co lại
            if prev_dur - overlap >= 0.8:
                prev_et = round(st - min_gap, 3)
                resolved[-1] = SubtitleSegment(prev_st, prev_et, prev.text, getattr(prev, 'speaker', 'wuby'))
            # Trường hợp 2: curr có thể lùi start về sau
            elif curr_dur - overlap >= 0.8:
                st = round(prev_et + min_gap, 3)
                if et <= st + 0.2:
                    et = st + 0.5
            # Trường hợp 3: Chia đều điểm giao nhau (midpoint split)
            else:
                mid = (prev_et + st) / 2.0
                prev_et = round(max(prev_st + 0.4, mid - (min_gap / 2.0)), 3)
                st = round(prev_et + min_gap, 3)
                if et <= st + 0.2:
                    et = st + 0.4
                resolved[-1] = SubtitleSegment(prev_st, prev_et, prev.text, getattr(prev, 'speaker', 'wuby'))

        resolved.append(SubtitleSegment(round(st, 3), round(et, 3), seg.text, getattr(seg, 'speaker', 'wuby')))

    return resolved

def rebalance_cue_timings(
    segments: list[SubtitleSegment],
    total_duration: float | None = None,
    min_speech_dur: float = 1.2
) -> list[SubtitleSegment]:
    """
    Điều chỉnh mở rộng timeline cho các câu ngắn vào khoảng lặng trước/sau (silence margin)
    để đảm bảo TTS có đủ không gian phát âm tự nhiên mà không bị ép tốc độ quá mức (VOICE_TOO_LONG).
    """
    if not segments:
        return segments

    rebalanced: list[SubtitleSegment] = []
    total_len = len(segments)

    for i, seg in enumerate(segments):
        st = float(seg.start)
        et = float(seg.end)
        words = len(seg.text.split())
        needed_dur = max(min_speech_dur, min(4.0, words * 0.38))
        curr_dur = et - st

        if curr_dur < needed_dur:
            deficit = needed_dur - curr_dur
            
            # 1. Mở rộng vào khoảng lặng phía sau (downstream silence)
            next_start = float(segments[i + 1].start) if (i + 1 < total_len) else (total_duration if total_duration else et + 5.0)
            avail_after = max(0.0, next_start - et - 0.08)
            extend_after = min(avail_after, deficit)
            et += extend_after
            deficit -= extend_after

            # 2. Nếu vẫn thiếu, mở rộng vào khoảng lặng phía trước (upstream silence)
            if deficit > 0.05:
                prev_end = float(rebalanced[-1].end) if rebalanced else 0.0
                avail_before = max(0.0, st - prev_end - 0.08)
                extend_before = min(avail_before, deficit)
                st -= extend_before

        rebalanced.append(SubtitleSegment(round(st, 3), round(et, 3), seg.text, getattr(seg, 'speaker', 'wuby')))
    return resolve_overlapping_segments(rebalanced)

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
    if not p.exists() or p.stat().st_size < 5:
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

def clean_ai_garbage(text: str) -> str:
    """Loại bỏ chú thích AI trong ngoặc đơn, ngoặc vuông, markdown."""
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"（.*?）", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"【.*?】", "", text)
    text = re.sub(r"\*.*", "", text)
    return text.strip()

def convert_to_million_vnd(text: str, currency_rate: int = 4000) -> str:
    """Chuyển đổi tiền tệ Trung Quốc sang tiếng Việt tự nhiên (theo chuẩn youtube-reup-pipeline)."""
    pattern = r"(\d+(?:\.\d+)?)\s*(nghin|van|nghìn|vạn)?\s*(te|nhan dan te|tệ|nhân dân tệ|¥|元|CNY)"

    def replace_func(match: re.Match[str]) -> str:
        try:
            value = float(match.group(1))
            unit = str(match.group(2) or "").lower()
            if unit in {"van", "vạn"}:
                value *= 10000
            elif unit in {"nghin", "nghìn"}:
                value *= 1000
            total_vnd = int(value * currency_rate)
            millions = total_vnd / 1000000
            if millions >= 1:
                if millions == int(millions):
                    return f"{int(millions)} triệu đồng"
                if (millions * 10) % 10 == 5:
                    return f"{int(millions)} triệu rưỡi"
                return f"{millions:.1f} triệu đồng".replace(".", ",")
            return f"{total_vnd // 1000} nghìn đồng"
        except Exception:
            return match.group(0)

    return re.sub(pattern, replace_func, text, flags=re.IGNORECASE)

def _google_translate_fallback_line(text: str) -> str:
    """Dịch dự phòng từng câu đơn lẻ qua Google Translate nếu DeepSeek bỏ sót dòng."""
    import urllib.request, urllib.parse, json
    clean = re.sub(r'[*_#`~]', '', text).strip()
    if not clean:
        return "..."
    for retry in range(2):
        try:
            q = urllib.parse.quote(clean)
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=vi&dt=t&q={q}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                translated = "".join(part[0] for part in data[0] if part and part[0])
                if translated.strip():
                    return translated.strip()
        except Exception:
            time.sleep(0.3)
    return clean or "..."

class OpenAISubtitleTranslator:
    """
    Bộ dịch phụ đề chuẩn kiến trúc D:\\02_CONG_CU\\youtube-reup-pipeline:
    - Định dạng prompt [ID] Text giúp LLM sinh chuẩn xác 100%, không bao giờ lỗi cú pháp JSON.
    - Regex parser bắt trực tiếp [ID] -> Text dịch.
    - Tự động lọc AI garbage và quy đổi tiền tệ sang VNĐ.
    - Tự động dự phòng per-item nếu thiếu câu, không bao giờ dừng video.
    """
    def __init__(self, api_key: str = DEEPSEEK_API_KEY, base_url: str = "https://api.deepseek.com", model_name: str = None, currency_rate: int = 4000, dubbing_speed: float = None):
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured in backend/.env")
        self.client = OpenAI(api_key=api_key.strip(), base_url=base_url)
        self.model_name = model_name or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.currency_rate = currency_rate
        self.dubbing_speed = dubbing_speed

    def translate_batch(self, batch: list[SubtitleSegment], retry_count: int = 3) -> dict[int, str]:
        prompt_lines = [f"[{i+1}] {item.text}" for i, item in enumerate(batch)]
        prompt_text = "\n".join(prompt_lines)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a professional subtitle translator for high-paced drama/movie video dubbing.\n"
                    "Translate each Chinese dialogue line into concise, natural, spoken Vietnamese.\n"
                    "Keep the exact format: [ID] Translation text\n"
                    "Rules:\n"
                    "1. Return ONLY 100% Vietnamese / Latin characters. Never leave Chinese characters.\n"
                    "2. Do not omit any lines. Keep sentences concise, punchy, and easy to speak.\n"
                    "3. Do not add explanations, notes, or parenthesis."
                )
            },
            {"role": "user", "content": f"Dịch mượt mà, tự nhiên cho từng câu sau:\n{prompt_text}"},
        ]
        if self.dubbing_speed:
            budgets = '\n'.join(f'[{i+1}] {max(0.1, s.end-s.start):.2f} giây; '
                f'mục tiêu khoảng {max(2, int((s.end-s.start)*4.3*self.dubbing_speed))} tiếng Việt'
                for i, s in enumerate(batch))
            messages[0]['content'] += (
                '\nDịch để lồng tiếng, giữ nguyên ID và ý nghĩa từng câu. Ưu tiên lời nói gọn, '
                'tự nhiên, bỏ từ đệm thừa; giữ tên, số liệu, phủ định, quan hệ và sự kiện. '
                'Không lược ý chỉ để ép độ dài, không viết tắt khó đọc. Nhất quán xưng hô theo ngữ cảnh. '
                'Không đưa thời lượng hay giới hạn từ vào bản dịch.\nThời lượng từng câu:\n' + budgets)

        translated: dict[int, str] = {}
        for attempt in range(retry_count):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.3,
                    timeout=60
                )
                result_text = response.choices[0].message.content or ""
                # Parse regex [ID] content - miễn nhiễm hoàn toàn với lỗi ngoặc / format của JSON
                for line_id, content in re.findall(r"\[(\d+)\][:\s]*(.*)", result_text):
                    cleaned = clean_ai_garbage(content)
                    cleaned = convert_to_million_vnd(cleaned, self.currency_rate)
                    cleaned = re.sub(r'[\u3400-\u9fff]+', '', cleaned).strip()
                    if cleaned:
                        translated[int(line_id)] = cleaned

                if len(translated) >= len(batch):
                    break
            except Exception as e:
                print(f"[OpenAISubtitleTranslator] DeepSeek batch attempt {attempt+1}/{retry_count} warning: {e}")
                time.sleep(1.0 * (attempt + 1))

        # Dự phòng từng câu nếu LLM bỏ sót hoặc rớt dòng
        for i, item in enumerate(batch):
            idx = i + 1
            if idx not in translated or not translated[idx].strip():
                try:
                    fb = _google_translate_fallback_line(item.text)
                    translated[idx] = clean_ai_garbage(fb) if fb else item.text
                except Exception:
                    translated[idx] = item.text

        return translated

    def translate_segments(self, segments: list[SubtitleSegment], batch_size: int = 25, progress_callback=None, checkpoint_path: str = None) -> list[SubtitleSegment]:
        if not segments:
            return []
        batch_size = max(5, min(int(batch_size), 35))
        result: list[SubtitleSegment] = []
        total_segments = len(segments)

        for start_idx in range(0, total_segments, batch_size):
            batch = segments[start_idx : start_idx + batch_size]
            current_end = min(start_idx + batch_size, total_segments)
            if progress_callback:
                progress_callback("translating", f"{current_end}/{total_segments}")

            print(f"[OpenAISubtitleTranslator] Dịch câu {start_idx+1} đến {current_end} / tổng {total_segments} câu...")
            batch_trans = self.translate_batch(batch)

            for i, seg in enumerate(batch):
                vi_text = batch_trans.get(i + 1, seg.text)
                result.append(SubtitleSegment(seg.start, seg.end, vi_text))

            # Checkpoint lưu tiến trình ra đĩa ngay sau mỗi batch để không bao giờ mất công dịch khi gián đoạn
            if checkpoint_path:
                try:
                    write_srt(result, checkpoint_path + ".partial.srt")
                except Exception:
                    pass

            time.sleep(0.15)

        return result

SubtitleTranslator = OpenAISubtitleTranslator

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

def extract_and_transcribe_to_srt(video_path: str, orig_srt_path: str, progress_callback=None, force: bool = False) -> list[SubtitleSegment]:
    """
    Giai đoạn 1 (Kiến trúc youtube-reup-pipeline):
    Tách audio & Whisper nhận diện toàn bộ lời thoại -> Lưu hoàn tất ra file _orig.srt.
    """
    if not force and os.path.exists(orig_srt_path) and os.path.getsize(orig_srt_path) > 100:
        existing = parse_srt_to_segments(orig_srt_path)
        if existing and len(existing) >= 2:
            print(f"[SubProcessor] [GIAI ĐOẠN 1] Tìm thấy file phụ đề gốc Whisper ({len(existing)} câu): {orig_srt_path}. Bỏ qua transcribe!")
            return existing

    temp_audio = str(Path(orig_srt_path).with_suffix(".wav"))
    try:
        if progress_callback:
            progress_callback("extract_audio")
        extract_audio_for_transcription(video_path, temp_audio)

        if progress_callback:
            progress_callback("transcribing")
        transcriber = get_transcriber(DEFAULT_WHISPER_MODEL)
        segments = transcriber.transcribe(temp_audio)

        if not segments:
            print("[SubProcessor] Không phát hiện lời thoại trong video.")
            write_srt([], orig_srt_path)
            raise RuntimeError("NO_SPEECH_DETECTED: review music or source; no blank translation")

        # Gộp các âm tiết tiếng Trung bị Whisper băm rời rạc trước khi lưu file
        segments = merge_chinese_orphan_segments(segments)
        write_srt(segments, orig_srt_path)
        print(f"[SubProcessor] [GIAI ĐOẠN 1 HOÀN TẤT] Đã tách & lưu file SRT gốc ({len(segments)} câu): {orig_srt_path}")
        return segments
    finally:
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except Exception:
                pass

def translate_srt_to_vietnamese_srt(orig_srt_path: str, output_srt_path: str, video_dur: float = 0.0, progress_callback=None, force: bool = False, preserve_1to1: bool = True, dubbing_speed: float = None) -> list[SubtitleSegment]:
    """
    Giai đoạn 2 (Kiến trúc youtube-reup-pipeline):
    Đọc từ file _orig.srt -> Dịch toàn bộ sang tiếng Việt -> Lưu hoàn tất ra file _vi.srt.
    Khi preserve_1to1=True: Bảo toàn chính xác 1:1 số câu và timeline mốc thời gian của từng câu Whisper.
    """
    policy_path = Path(str(output_srt_path) + '.translation_policy.json')
    policy = {'schema': 1, 'dubbing_speed': dubbing_speed,
              'source_sha256': hashlib.sha256(Path(orig_srt_path).read_bytes()).hexdigest()} if dubbing_speed else None
    policy_current = not policy or (policy_path.is_file() and json.loads(policy_path.read_text(encoding='utf-8')) == policy)
    if not force and policy_current and os.path.exists(output_srt_path) and os.path.getsize(output_srt_path) > 100:
        existing_segs = parse_srt_to_segments(output_srt_path)
        if existing_segs and len(existing_segs) >= 2:
            has_chinese = any(re.search(r'[\u3400-\u9fff]', s.text) for s in existing_segs[:10])
            if not has_chinese:
                print(f"[SubProcessor] [GIAI ĐOẠN 2] Tìm thấy file phụ đề tiếng Việt hoàn chỉnh ({len(existing_segs)} câu): {output_srt_path}. Bỏ qua dịch!")
                return existing_segs

    segments = parse_srt_to_segments(orig_srt_path)
    if not segments:
        print(f"[SubProcessor] File phụ đề gốc không có câu thoại nào ({orig_srt_path}). Coi như video không có lời thoại.")
        write_srt([], output_srt_path)
        raise RuntimeError("NO_SPEECH_DETECTED: video không có lời thoại (chỉ có nhạc nền/âm thanh)")

    translator = OpenAISubtitleTranslator(dubbing_speed=dubbing_speed)
    vi_segments = translator.translate_segments(
        segments,
        batch_size=25,
        progress_callback=progress_callback,
        checkpoint_path=(str(output_srt_path) + '.dub_' + hashlib.sha256(
            json.dumps(policy, sort_keys=True).encode()).hexdigest()[:12]) if dubbing_speed else output_srt_path
    )

    cleaned_vi: list[SubtitleSegment] = []
    for seg in vi_segments:
        seg.text = limit_repeated_words(seg.text)
        dur = float(seg.end) - float(seg.start)
        if seg.text and not is_whisper_hallucination(seg.text, duration=dur):
            cleaned_vi.append(seg)
    vi_segments = prune_intersegment_repetition_loops(cleaned_vi)

    if not preserve_1to1:
        # 1. Tách câu quá dài
        vi_segments = split_long_segments(vi_segments, max_words=12, max_chars=44)
        # 2. Gộp câu siêu ngắn sát nhau
        vi_segments = merge_adjacent_micro_segments(vi_segments, min_dur=1.1, max_gap=0.45, max_combined_words=12)
        # 3. Tái cân bằng timeline vào khoảng lặng
        vi_segments = rebalance_cue_timings(vi_segments, total_duration=video_dur if video_dur > 0 else None, min_speech_dur=1.6)

    # 4. Triệt tiêu chồng lấn thời gian
    vi_segments = resolve_overlapping_segments(vi_segments)

    if not vi_segments:
        print("[SubProcessor] All segments were filtered as non-speech/hallucinations.")
        write_srt([], output_srt_path)
        raise RuntimeError("NO_SPEECH_DETECTED: review music or source; no blank translation")

    if policy and not policy_current and Path(output_srt_path).is_file():
        backup = Path(str(output_srt_path) + '.before_timing_policy.srt')
        if not backup.exists():
            with backup.open('xb') as saved:
                saved.write(Path(output_srt_path).read_bytes())
    write_srt(vi_segments, output_srt_path)
    if policy:
        policy_path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[SubProcessor] [GIAI ĐOẠN 2 HOÀN TẤT] Đã dịch & lưu file SRT tiếng Việt ({len(vi_segments)} câu, preserve_1to1={preserve_1to1}): {output_srt_path}")
    return vi_segments


def generate_vietnamese_subtitles(video_path: str, output_srt_path: str, progress_callback=None, force: bool = False, dubbing_speed: float = None) -> tuple[str, list[SubtitleSegment]]:
    """
    Quy trình chuẩn hóa theo D:\\02_CONG_CU\\youtube-reup-pipeline:
    1. Tách file SRT gốc xong (_orig.srt)
    2. Dịch toàn bộ sang tiếng Việt xong (_vi.srt)
    3. Trả về file hoàn chỉnh để bước tiếp theo lồng tiếng & ghép video
    """
    video_dur = 0.0
    try:
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
            n_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
            cap.release()
            if fps > 0 and n_frames > 0:
                video_dur = float(n_frames / fps)
    except Exception:
        pass

    orig_srt_path = str(Path(output_srt_path).with_suffix(".orig.srt"))

    # Giai đoạn 1: Tách hoàn chỉnh file SRT gốc
    extract_and_transcribe_to_srt(video_path, orig_srt_path, progress_callback=progress_callback, force=force)

    # Giai đoạn 2: Dịch hoàn chỉnh sang tiếng Việt
    vi_segments = translate_srt_to_vietnamese_srt(orig_srt_path, output_srt_path, video_dur=video_dur, progress_callback=progress_callback, force=force, dubbing_speed=dubbing_speed)

    return output_srt_path, vi_segments

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
    try:
        from .vi_text_normalizer import normalize_vietnamese_text
        clean = normalize_vietnamese_text(clean)
    except Exception:
        try:
            from vi_text_normalizer import normalize_vietnamese_text
            clean = normalize_vietnamese_text(clean)
        except Exception:
            pass
    if not clean:
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

    if engine != "edge":
        raise RuntimeError(f"UNKNOWN_TTS_ENGINE: {engine}")
    import edge_tts
    # Edge-TTS
    voice_name = profile.get("voice", "vi-VN-HoaiMyNeural")
    pitch = profile.get("pitch", "+0Hz")
    pct = int(round((effective_speed - 1.0) * 100))
    rate = f"+{pct}%" if pct >= 0 else f"{pct}%"
    mp3_path = str(Path(out_file).with_suffix(".mp3"))

    for attempt in range(5):
        try:
            comm = edge_tts.Communicate(clean, voice_name, pitch=pitch, rate=rate)
            await comm.save(mp3_path)
            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
                return mp3_path
        except Exception as tts_err:
            await asyncio.sleep(0.8 * (attempt + 1))

    # Tự động fallback sang Google TTS nếu Edge-TTS gặp sự cố mạng
    try:
        print(f"[TTS] Edge-TTS gặp sự cố mạng ({voice_name}), tự động chuyển sang Google TTS cho đoạn này...")
        return await _render_tts_chunk(clean, {"engine": "google"}, out_file, speed=effective_speed)
    except Exception as g_err:
        print(f"[TTS] Google TTS fallback thất bại: {g_err}")
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


def generate_dubbed_audio(segments, output_audio_path: str, voice: str = "nu_tre", speed: float | None = None,
                         total_duration_sec: float | None = None, force: bool = False, voice_profile: dict | None = None,
                         progress_callback=None) -> str:
    import copy, tempfile
    from wuby_studio.captions import validate, write_srt
    from wuby_studio.audio import align_track
    from wuby_studio.common import ROOT, WubyError
    try:
        from .vi_text_normalizer import normalize_vietnamese_text
    except Exception:
        try:
            from vi_text_normalizer import normalize_vietnamese_text
        except Exception:
            normalize_vietnamese_text = lambda s: s

    norm_segments = []
    for s in segments:
        norm_text = normalize_vietnamese_text(getattr(s, "text", ""))
        speaker = getattr(s, "speaker", "wuby")
        norm_segments.append(SubtitleSegment(s.start, s.end, norm_text, speaker))
    segments = norm_segments

    profile = copy.deepcopy(voice_profile or VOICE_PROFILES.get(voice) or {})
    if profile.get("role_profiles"):
        from wuby_roles import classify_roles
        roles = classify_roles(segments)
        for i, (segment, role) in enumerate(zip(segments, roles)):
            segments[i] = SubtitleSegment(segment.start, segment.end, segment.text, role)
        role_path = Path(output_audio_path).with_suffix(".roles.json")
        role_path.parent.mkdir(parents=True, exist_ok=True)
        role_path.write_text(json.dumps([{"start": s.start, "end": s.end, "text": s.text,
                                         "role": s.speaker} for s in segments],
                                       ensure_ascii=False, indent=2), encoding="utf-8")
    segments = resolve_overlapping_segments(segments)
    valid, _ = validate(segments, total_duration_sec)
    if not valid:
        raise WubyError("EMPTY_SCRIPT: refusing to export silent TTS")
    # Tự động cân bằng mở rộng timeline cho các câu ngắn trước khi tổng hợp voice
    valid = rebalance_cue_timings(valid, total_duration=total_duration_sec, min_speech_dur=1.6)
    valid = resolve_overlapping_segments(valid)
    if profile.get("role_profiles"):
        from wuby_roles import render_roles
        return render_roles(valid, output_audio_path, profile, total_duration_sec,
                            profile.get("speed", 1.0) if speed is None else speed)
    if len({c.speaker for c in valid}) > 1:
        raise WubyError("MULTI_SPEAKER_REQUIRES_EXPLICIT_TRACKS: one Wuby profile cannot stand in for all roles")
    profile = copy.deepcopy(voice_profile or VOICE_PROFILES.get(voice) or {})
    if not profile:
        raise WubyError(f"UNKNOWN_VOICE_PROFILE: {voice}")
    engine = str(profile.get("engine", "")).lower()
    effective_speed = float(profile.get("speed", 1.0) if speed is None else speed) * float(profile.get("speed_multiplier", 1.0))
    if not 0.5 <= effective_speed <= 2.0: raise WubyError("Invalid voice speed")
    out = Path(output_audio_path); out.parent.mkdir(parents=True, exist_ok=True)
    if engine in {"router", "omnivoice", "khanh_omnivoice", "khanhtts", "vieneu", "zerotts"}:
        try:
            from . import voice_router
        except ImportError:
            import voice_router
        cfg = copy.deepcopy(profile)
        cfg["project_root"] = str(profile.get("project_root") or ROOT)
        cfg["speed"] = effective_speed; cfg.pop("speed_multiplier", None)
        ref_cfg = dict(profile.get("reference") or {})
        if profile.get("ref_audio"): ref_cfg["audio"] = profile["ref_audio"]
        if profile.get("ref_text") is not None: ref_cfg["text"] = profile["ref_text"]
        cfg["reference"] = ref_cfg
        if "duration_match" in profile and isinstance(profile["duration_match"], dict):
            cfg["duration_match"] = copy.deepcopy(profile["duration_match"])
            cfg["duration_match"].setdefault("adaptive", True)
        else:
            cfg.setdefault("duration_match", {"max_speedup": 1.65, "minimum_gap_sec": 0.06, "adaptive": True})
        with tempfile.TemporaryDirectory(prefix="tts_job_", dir=out.parent) as tmp:
            srt=Path(tmp)/"approved.srt";write_srt(valid,srt)
            return voice_router.render_srt_voice_track(srt,out,cfg,video_duration=total_duration_sec)
    if engine not in {"edge","google"} or profile.get("require_clone"):
        raise WubyError("INVALID_PRESET_OR_CLONE_CONFIGURATION")

    # Thư mục cache bền vững cho các đoạn audio đã tải về
    stem = Path(output_audio_path).stem.replace("_voice", "")
    cache_dir = Path(output_audio_path).parent / f"tts_cache_{stem}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    if force:
        for old_chunk in cache_dir.glob("*.mp3"):
            try:
                old_chunk.unlink()
            except Exception:
                pass

    from concurrent.futures import ThreadPoolExecutor
    total_count = len(valid)

    async def create_parallel():
        sem = asyncio.Semaphore(6)
        done_count = 0

        # Chỉ đếm mỗi index một lần; file cache cũ/sai hash không được tái sử dụng ở render_single_chunk.
        cached_indices = set()
        for f in cache_dir.glob("*.mp3"):
            if f.is_file() and f.stat().st_size > 100:
                s_name = f.stem.split("_", 1)[0]
                if s_name.isdigit() and int(s_name) < total_count:
                    cached_indices.add(int(s_name))
        done_count = len(cached_indices)

        if done_count > 0:
            print(f"[TTS Parallel] Đã tìm thấy {done_count}/{total_count} chunks có sẵn trong cache! Bỏ qua các đoạn này.")
            if progress_callback:
                progress_callback("tts_dubbing", f"{done_count}/{total_count}")

        async def render_single_chunk(i, c):
            nonlocal done_count
            p = dict(profile)
            p.pop("speed_multiplier", None)
            cache_identity = {
                "text": c.text,
                "engine": p.get("engine"),
                "voice": p.get("voice"),
                "pitch": p.get("pitch"),
                "rate": p.get("rate"),
                "speed": round(float(effective_speed), 4),
            }
            cache_hash = hashlib.sha256(json.dumps(cache_identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]
            chunk_file = cache_dir / f"{i}_{cache_hash}.mp3"
            if (not force) and chunk_file.exists() and chunk_file.stat().st_size > 100:
                return i, str(chunk_file)

            async with sem:
                actual = await _render_tts_chunk(c.text, p, str(chunk_file), speed=effective_speed)
                if not actual:
                    raise WubyError(f"TTS_CHUNK_FAILED: {i+1}")
                done_count += 1
                if progress_callback and (done_count % 15 == 0 or done_count == total_count):
                    progress_callback("tts_dubbing", f"{done_count}/{total_count}")
                return i, actual

        tasks = [render_single_chunk(i, c) for i, c in enumerate(valid)]
        results = await asyncio.gather(*tasks)
        results.sort(key=lambda x: x[0])
        return [Path(p) for _, p in results]

    def runner():
        return asyncio.run(create_parallel())

    with ThreadPoolExecutor(max_workers=1) as pool:
        paths = pool.submit(runner).result()

    timing = profile.get("duration_match") or {}
    adaptive = bool(timing.get("adaptive", True))
    align_track(valid, paths, out, total_duration_sec,
                max_speedup=float(timing.get("max_speedup", 1.48)),
                gap_sec=float(timing.get("minimum_gap_sec", 0.06)),
                adaptive=adaptive)
    return str(out)



def multivoice_cache_identity(text, profile_key, profile, speed):
    """Bind a cached utterance to the complete clone/reference settings."""
    reference = dict(profile.get('reference') or {})
    ref_audio = str(reference.get('audio') or profile.get('ref_audio') or '')
    ref_hash = hashlib.sha256(Path(ref_audio).read_bytes()).hexdigest() if ref_audio and Path(ref_audio).is_file() else ''
    settings = {key: profile.get(key) for key in (
        'engine','model','mode','language','num_step','guidance_scale','pitch',
        'require_clone','allow_backend_switch','fallback_voice','speed_multiplier')}
    return dict(schema=2,text=text,profile=profile_key,settings=settings,
                ref_hash=ref_hash,ref_text=reference.get('text',profile.get('ref_text')),
                speed=round(float(speed),4))


def generate_dubbed_audio_multivoice(
    segments,
    assignments: list[dict],
    output_audio_path: str,
    profile_map: dict[str, dict],
    speed: float = 1.0,
    total_duration_sec: float | None = None,
    force: bool = False,
    duration_match: dict | None = None,
    progress_callback=None,
) -> str:
    """Render one Vietnamese TTS chunk per translated Whisper segment with its matched voice.

    `assignments` must be aligned to `segments` and contain a `profile` key. The caller
    resolves those profile configs from channels_config so this function stays independent
    of Telegram/channel routing. OmniVoice chunks are intentionally rendered sequentially
    to avoid loading/generating multiple GPU clone jobs at once on a 16GB card.
    """
    import copy
    import tempfile
    from wuby_studio.captions import validate
    from wuby_studio.audio import align_track
    from wuby_studio.common import WubyError

    valid, _ = validate(list(segments or []), total_duration_sec)
    if not valid:
        raise WubyError("EMPTY_SCRIPT: refusing to export silent multi-voice TTS")

    # generate_vietnamese_subtitles() already splits/merges/rebalances cues. Keep that
    # approved timing here so F0 assignments remain aligned to the translated segments.
    valid = resolve_overlapping_segments(valid)
    if not assignments:
        raise WubyError("MULTIVOICE_ASSIGNMENTS_EMPTY")

    def assignment_for(c, idx):
        if idx < len(assignments):
            a = assignments[idx]
            try:
                if abs(float(a.get("start", c.start)) - float(c.start)) <= 0.75:
                    return a
            except Exception:
                pass
        mid = (float(c.start) + float(c.end)) / 2.0
        return min(
            assignments,
            key=lambda a: abs(((float(a.get("start", 0)) + float(a.get("end", 0))) / 2.0) - mid),
        )

    out = Path(output_audio_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = out.parent / f"tts_cache_{out.stem.replace('_voice', '')}_multivoice"
    cache_dir.mkdir(parents=True, exist_ok=True)
    if force:
        for old in cache_dir.glob("*"):
            try:
                if old.is_file():
                    old.unlink()
            except Exception:
                pass

    rendered_paths: list[Path] = []
    render_report: list[dict] = []
    total_count = len(valid)

    for i, cue in enumerate(valid):
        assignment = assignment_for(cue, i)
        profile_key = str(assignment.get("profile") or "").strip()
        profile = copy.deepcopy(profile_map.get(profile_key) or {})
        if not profile:
            raise WubyError(f"UNKNOWN_MULTIVOICE_PROFILE: {profile_key}")

        ref_audio = str(profile.get("ref_audio") or "")
        ref_hash = ""
        if ref_audio and os.path.exists(ref_audio):
            try:
                ref_hash = hashlib.sha256(Path(ref_audio).read_bytes()).hexdigest()[:12]
            except Exception:
                pass
        cache_identity = multivoice_cache_identity(cue.text,profile_key,profile,speed)
        cache_hash = hashlib.sha256(json.dumps(cache_identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        cached = None
        if not force:
            for ext in (".wav", ".mp3", ".m4a"):
                cp = cache_dir / f"{i}_{cache_hash}{ext}"
                if cp.exists() and cp.stat().st_size > 100:
                    cached = cp
                    break

        if cached is None:
            base = cache_dir / f"{i}_{cache_hash}.wav"
            try:
                actual = asyncio.run(_render_tts_chunk(cue.text, profile, str(base), speed=float(speed)))
            except RuntimeError:
                raise
            except Exception as exc:
                raise WubyError(f"MULTIVOICE_TTS_FAILED:{i+1}:{profile_key}:{exc}") from exc
            if not actual or not os.path.exists(actual) or os.path.getsize(actual) <= 100:
                raise WubyError(f"MULTIVOICE_TTS_EMPTY:{i+1}:{profile_key}")
            cached = Path(actual)

        rendered_paths.append(cached)
        render_report.append({
            "index": i,
            "start": round(float(cue.start), 3),
            "end": round(float(cue.end), 3),
            "text": cue.text,
            "profile": profile_key,
            "audio": str(cached),
            "match_method": assignment.get("method"),
            "source_index": assignment.get("source_index"),
        })
        if progress_callback and ((i + 1) % 5 == 0 or i + 1 == total_count):
            progress_callback("tts_dubbing", f"{i+1}/{total_count} · {profile_key}")

    timing = duration_match or {}
    align_track(
        valid,
        rendered_paths,
        out,
        total_duration_sec,
        max_speedup=float(timing.get("max_speedup", 1.65)),
        gap_sec=float(timing.get("minimum_gap_sec", 0.06)),
        adaptive=bool(timing.get("adaptive", True)),
    )
    report_path = out.with_suffix(".multivoice.json")
    report_path.write_text(json.dumps(render_report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)

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
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                messages=[
                    {"role": "system", "content": "Bạn là chuyên gia đặt tên phim ngắn tiếng Việt. Chỉ trả về 1 dòng tên duy nhất."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=100
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
    if re.search(r'[\u4e00-\u9fff]', fallback_title):
        fallback_title = "Bí Mật Động Trời"
    slug = slugify_vietnamese(fallback_title)
    return fallback_title, slug

def generate_movie_caption(
    movie_title: str,
    raw_title: str = "",
    segments: list[SubtitleSegment] | None = None,
    workflow: str = "film_review_black",
    logo_type: str | None = None
) -> str:
    """
    Sinh bài viết (Caption) đăng Facebook Reel / TikTok / Shorts.
    - Cấu hình 1 (Wuby / Hoạt hình): Ngắn gọn, dễ thương, không icon xe tải!
    - Cấu hình 4 (Chị Đẹp Đi Câu / Blog câu cá): Giọng văn dã ngoại, săn cá khủng, đúng chủ đề câu cá.
    - Cấu hình 2 & 3 (Review Phim): Chuẩn mẫu tóm tắt kịch tính, dùng icon điện ảnh, phân biệt Bật Phim Lên / Vũ Trụ Cày Phim.
    """
    title_upper = movie_title.strip().upper()
    is_wuby = (workflow == "wuby" or "wuby" in str(workflow).lower() or "quby" in str(workflow).lower())
    is_cauca = (
        workflow in {"gaidep_cauca", "chidepdicau"}
        or "cauca" in str(workflow).lower()
        or "chidep" in str(workflow).lower()
        or (logo_type and "chidep" in str(logo_type).lower())
    )

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
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
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

    if is_cauca:
        # Cấu hình 4: Blog Câu Cá / Nữ Cần Thủ / Dã Ngoại
        summary_hook = ""
        if DEEPSEEK_API_KEY:
            try:
                prompt = (
                    f"Tiêu đề video câu cá: {movie_title}\n"
                    f"Nội dung/mô tả:\n{dialogue_context or raw_title}\n\n"
                    "Nhiệm vụ: Viết đúng 1-2 câu tóm tắt tình huống đi câu kịch tính hoặc hài hước (cuốn hút, gây tò mò, đậm chất dân câu). "
                    "Tuyệt đối KHÔNG dùng từ 'bộ phim', không dùng từ 'review phim', không dùng icon xem phim hay bắp rang bơ. "
                    "Chỉ trả về đúng 1-2 câu tóm tắt."
                )
                client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
                resp = client.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    messages=[
                        {"role": "system", "content": "Bạn là chuyên gia sáng tạo nội dung video ngắn về câu cá, dã ngoại, giải trí ngoài trời."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.5,
                    max_tokens=150
                )
                summary_hook = resp.choices[0].message.content.strip().replace('"', '').replace("'", "")
            except Exception as e:
                print(f"[CaptionGenerator] Lỗi DeepSeek sinh caption câu cá: {e}")

        if not summary_hook:
            summary_hook = f"Pha câu cá đầy kịch tính và bất ngờ của nữ cần thủ... 🎣 Liệu cô ấy có chinh phục được chú cá khủng này không?"

        caption = (
            f"🎣 {title_upper} 🐟\n"
            f"{summary_hook} Cùng theo dõi hành trình đi câu cực cuốn và những pha kéo cần đỉnh cao nhé! 🌊\n\n"
            f"🎣 Đam mê câu đài, săn hàng khủng cùng Chị Đẹp Đi Câu!\n"
            f"👀 Theo dõi ngay @ChiDepDiCau để xem thêm nhiều video hấp dẫn!\n\n"
            f"#chidepdicau #cauca #caudai #sancakhung #fishing #gaidepcauca #chidep #dicau"
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
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
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

    brand_name = "Bật Phim Lên" if logo_type == "batphimlen" else "Vũ Trụ Cày Phim"
    brand_tag = "#BatPhimLen" if logo_type == "batphimlen" else "#VuTruCayPhim"

    caption = (
        f"🎬 {title_upper} 🔥\n"
        f"{summary_hook} Cùng xem review để khám phá những tình tiết bất ngờ của bộ phim này nhé! 🍿\n\n"
        f"🎬 Phim hay thì kể, phim dở cũng tám!\n"
        f"👀 Vào {brand_name} coi có gì vui!\n\n"
        f"{brand_tag} #MePhim #ReviewPhim #TomTatPhim #PhimHay #PhimDienAnh"
    )
    return caption

