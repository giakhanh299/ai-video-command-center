"""Render helpers extracted without changing legacy behavior; no model or queue imports."""
from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Any

def format_ass_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def parse_srt_file_to_events(srt_path: str) -> list[tuple[float, float, str]]:
    """Parses .srt file into list of (start_sec, end_sec, text)."""
    events = []
    if not os.path.exists(srt_path):
        return events
    try:
        content = Path(srt_path).read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        try:
            content = Path(srt_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return events

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
                        p = re.split('[:,]', t_str.strip())
                        if len(p) == 4:
                            return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2]) + int(p[3]) / 1000.0
                        return 0.0
                    start_s = to_sec(parts[0])
                    end_s = to_sec(parts[1])
                    text = "\\N".join(text_lines)
                    events.append((start_s, end_s, text))
    return events


def _ass_color(value: Any, fallback: str = "&H00FFFFFF") -> str:
    """Convert #RRGGBB / RRGGBB into ASS &HAABBGGRR color."""
    raw = str(value or "").strip()
    if raw.startswith("&H"):
        return raw
    raw = raw.lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{6}", raw):
        rr, gg, bb = raw[0:2], raw[2:4], raw[4:6]
        return f"&H00{bb}{gg}{rr}".upper()
    return fallback


def format_balanced_sub_text(text: str, max_chars: int = 34) -> str:
    """Balances long subtitle lines across 2 lines with \\N to prevent edge clipping."""
    clean = (text or "").strip()
    if not clean or len(clean) <= max_chars or r"\N" in clean or "\n" in clean:
        return clean.replace("\n", r"\N")
    words = clean.split()
    if len(words) <= 3:
        return clean
    mid = len(clean) // 2
    best_idx = len(words) // 2
    best_diff = 999
    cur_pos = 0
    for idx, w in enumerate(words[:-1]):
        cur_pos += len(w) + 1
        diff = abs(cur_pos - mid)
        if diff < best_diff:
            best_diff = diff
            best_idx = idx + 1
    return " ".join(words[:best_idx]) + r"\N" + " ".join(words[best_idx:])


def make_karaoke_ass_text(text: str, duration_sec: float) -> str:
    """
    Format text with {\\kf<cs>} tags for smooth white-to-yellow karaoke effect.
    Supports \\N linebreaks cleanly without breaking karaoke timing.
    """
    lines = text.split(r"\N")
    total_chars = sum(len(w) for line in lines for w in line.split() if w)
    if total_chars == 0 or duration_sec <= 0:
        return text
    total_cs = int(round(duration_sec * 100))
    all_words = []
    for line_idx, line in enumerate(lines):
        words = line.split()
        for w in words:
            all_words.append((line_idx, w))
    if not all_words:
        return text
    allocated_cs = 0
    line_parts = {i: [] for i in range(len(lines))}
    for idx, (l_idx, w) in enumerate(all_words):
        if idx == len(all_words) - 1:
            w_cs = max(1, total_cs - allocated_cs)
        else:
            w_cs = max(1, int(round(total_cs * (len(w) / total_chars))))
            allocated_cs += w_cs
        line_parts[l_idx].append(f"{{\\kf{w_cs}}}{w}")
    return r"\N".join(" ".join(line_parts[i]) for i in range(len(lines)))
