from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np

_REF_MEASURE_CACHE: dict[tuple[str, int, int], dict[str, Any] | None] = {}

try:
    from . import asset_manager, character_identity
    from .pitch_voice_selector import _autocorr_f0
    from .scene_detector import detect_scene_ranges, scene_for_time
except ImportError:
    import asset_manager
    import character_identity
    from pitch_voice_selector import _autocorr_f0
    from scene_detector import detect_scene_ranges, scene_for_time


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("FFMPEG_NOT_FOUND")
    return exe


def _seg_times(seg: Any) -> tuple[float, float] | None:
    try:
        if isinstance(seg, dict):
            st, en = float(seg.get("start", 0)), float(seg.get("end", 0))
        else:
            st, en = float(getattr(seg, "start")), float(getattr(seg, "end"))
        if en > st >= 0:
            return st, en
    except Exception:
        pass
    return None


def _seg_text(seg: Any) -> str:
    if isinstance(seg, dict):
        return str(seg.get("text") or "")
    return str(getattr(seg, "text", "") or "")


def _extract_mono(video_path: str, sr: int = 16000) -> np.ndarray:
    with tempfile.TemporaryDirectory(prefix="movie_voice_match_") as td:
        raw = Path(td) / "source.f32"
        subprocess.run([
            _ffmpeg(), "-y", "-v", "error", "-i", str(video_path),
            "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", str(raw)
        ], check=True)
        return np.fromfile(raw, dtype=np.float32)


def _measure_window(
    audio: np.ndarray,
    sr: int,
    start: float,
    end: float,
    *,
    fmin_hz: float = 70.0,
    fmax_hz: float = 420.0,
) -> dict[str, Any] | None:
    a = max(0, int(start * sr))
    b = min(len(audio), int(end * sr))
    frame_len = max(320, int(0.040 * sr))
    hop = max(160, int(0.020 * sr))
    if b - a < frame_len:
        return None

    f0s: list[float] = []
    for pos in range(a, b - frame_len + 1, hop):
        f0, _ = _autocorr_f0(np.asarray(audio[pos:pos + frame_len]), sr, fmin_hz, fmax_hz)
        if f0 is not None:
            f0s.append(float(f0))
    if len(f0s) < 6:
        return None

    arr = np.asarray(f0s, dtype=np.float64)
    q1, q3 = np.percentile(arr, [20, 80])
    trimmed = arr[(arr >= q1) & (arr <= q3)]
    if len(trimmed) < 4:
        trimmed = arr
    return {
        "median_f0_hz": round(float(np.median(trimmed)), 2),
        "p20_hz": round(float(np.percentile(arr, 20)), 2),
        "p80_hz": round(float(np.percentile(arr, 80)), 2),
        "voiced_frames": int(len(arr)),
        "duration": round(float(end - start), 3),
    }


def _measure_reference(path: Path, cfg: dict[str, Any]) -> dict[str, Any] | None:
    st = path.stat()
    key = (str(path.resolve()), int(st.st_size), int(st.st_mtime_ns))
    if key in _REF_MEASURE_CACHE:
        return _REF_MEASURE_CACHE[key]
    sr = int(cfg.get("sample_rate", 16000))
    audio = _extract_mono(str(path), sr=sr)
    duration = len(audio) / float(sr)
    measured = _measure_window(
        audio, sr, 0.0, duration,
        fmin_hz=float(cfg.get("f0_min_hz", 70.0)),
        fmax_hz=float(cfg.get("f0_max_hz", 420.0)),
    )
    _REF_MEASURE_CACHE[key] = measured
    return measured


def build_voice_bank(config_data: dict[str, Any], bank_spec: list[dict[str, Any]], cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Resolve the real bundled reference samples and measure their actual F0.

    Explicit reference_hz is only a fallback. The real ref_audio wins when available,
    so the bank stays correct when the user replaces a sample file later.
    """
    cfg = cfg or {}
    profiles = config_data.get("voice_profiles", {}) if isinstance(config_data, dict) else {}
    out: list[dict[str, Any]] = []
    for entry in bank_spec or []:
        if not isinstance(entry, dict) or entry.get("enabled", True) is False:
            continue
        key = str(entry.get("profile") or "").strip()
        profile = profiles.get(key) if isinstance(profiles, dict) else None
        if not key or not isinstance(profile, dict):
            continue
        ref = asset_manager.resolve_voice_sample(profile.get("ref_audio"))
        measured = None
        if ref and ref.is_file():
            try:
                measured = _measure_reference(ref, cfg)
            except Exception as exc:
                print(f"[MovieVoiceMatcher] Cannot measure {key}/{ref.name}: {exc}")
        fallback_hz = entry.get("reference_hz", profile.get("reference_hz"))
        try:
            ref_hz = float(measured["median_f0_hz"] if measured else fallback_hz)
        except Exception:
            continue
        if ref_hz <= 0:
            continue
        out.append({
            "profile": key,
            "label": str(profile.get("label") or key),
            "reference_hz": round(ref_hz, 2),
            "reference_audio": str(ref) if ref else None,
            "reference_measurement": measured,
        })
    out.sort(key=lambda x: x["reference_hz"])
    if not out:
        raise RuntimeError("MOVIE_VOICE_BANK_EMPTY")
    return out


def _rank(src_hz: float, bank: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for item in bank:
        ref = float(item["reference_hz"])
        cents = abs(1200.0 * math.log2(src_hz / ref))
        ranked.append({
            "profile": item["profile"],
            "label": item.get("label") or item["profile"],
            "reference_hz": ref,
            "distance_hz": round(abs(src_hz - ref), 2),
            "distance_cents": round(cents, 2),
        })
    ranked.sort(key=lambda x: x["distance_cents"])
    return ranked


def _voiceprint_window(audio: np.ndarray, sr: int, start: float, end: float) -> np.ndarray | None:
    """Lightweight timbre vector for grouping repeated speech from the same voice.

    This is not biometric identity recognition. It is a local acoustic consistency
    feature (spectral envelope) used only to stop one continuous narrator from being
    mapped to different TTS voices because F0 jumps by an octave.
    """
    a = max(0, int(start * sr))
    b = min(len(audio), int(end * sr))
    x = np.asarray(audio[a:b], dtype=np.float32)
    frame_len = max(320, int(0.040 * sr))
    hop = max(160, int(0.020 * sr))
    if len(x) < frame_len * 3:
        return None
    window = np.hanning(frame_len).astype(np.float32)
    specs = []
    rms_values = []
    frames = []
    for pos in range(0, len(x) - frame_len + 1, hop):
        fr = x[pos:pos + frame_len]
        rms = float(np.sqrt(np.mean(fr.astype(np.float64) ** 2)))
        frames.append(fr)
        rms_values.append(rms)
    if not frames:
        return None
    gate = max(1e-4, float(np.percentile(np.asarray(rms_values), 45)))
    freqs = np.fft.rfftfreq(frame_len, d=1.0 / sr)
    edges = np.geomspace(120.0, min(4200.0, sr * 0.45), 25)
    for fr, rms in zip(frames, rms_values):
        if rms < gate:
            continue
        spec = np.abs(np.fft.rfft(fr * window)) ** 2
        bands = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            idx = (freqs >= lo) & (freqs < hi)
            val = float(np.mean(spec[idx])) if np.any(idx) else 0.0
            bands.append(math.log1p(val))
        specs.append(bands)
    if len(specs) < 3:
        return None
    v = np.median(np.asarray(specs, dtype=np.float64), axis=0)
    v = v - np.mean(v)
    norm = float(np.linalg.norm(v))
    if norm <= 1e-9:
        return None
    return (v / norm).astype(np.float32)


def _cosine(a: np.ndarray | None, b: np.ndarray | None) -> float:
    if a is None or b is None:
        return -1.0
    den = float(np.linalg.norm(a) * np.linalg.norm(b))
    if den <= 1e-9:
        return -1.0
    return float(np.dot(a, b) / den)


def _octave_align(value: float, anchor: float, fmin: float, fmax: float) -> float:
    if value <= 0 or anchor <= 0:
        return value
    candidates = [value]
    if value * 0.5 >= fmin:
        candidates.append(value * 0.5)
    if value * 2.0 <= fmax:
        candidates.append(value * 2.0)
    return min(candidates, key=lambda x: abs(1200.0 * math.log2(x / anchor)))


def _canonical_cluster_f0(values: list[float], fmin: float, fmax: float, octave_correction: bool) -> float | None:
    vals = [float(v) for v in values if v and v > 0]
    if not vals:
        return None
    if not octave_correction or len(vals) == 1:
        return float(np.median(vals))
    anchors = []
    for v in vals:
        for mul in (0.5, 1.0, 2.0):
            a = v * mul
            if fmin <= a <= fmax:
                anchors.append(a)
    best_anchor = float(np.median(vals))
    best_cost = float('inf')
    for anchor in anchors:
        cost = 0.0
        for v in vals:
            aligned = _octave_align(v, anchor, fmin, fmax)
            cents = abs(1200.0 * math.log2(aligned / anchor))
            # A small penalty means octave repair is allowed but never preferred casually.
            if abs(aligned - v) > 1e-6:
                cents += 90.0
            cost += cents
        if cost < best_cost:
            best_cost = cost
            best_anchor = anchor
    corrected = [_octave_align(v, best_anchor, fmin, fmax) for v in vals]
    return float(np.median(corrected))


def _cluster_speakers(records: list[dict[str, Any]], cfg: dict[str, Any], fmin: float, fmax: float) -> list[dict[str, Any]]:
    threshold = float(cfg.get('speaker_similarity_threshold', 0.78))
    max_speakers = max(1, int(cfg.get('max_speakers', 4)))
    sticky_gap = float(cfg.get('sticky_gap_sec', 2.5))
    clusters: list[dict[str, Any]] = []
    previous_cluster: int | None = None
    previous_end = -1.0
    previous_scene: int | None = None

    for rec in records:
        emb = rec.get('_voiceprint')
        st = float(rec['start'])
        scene_id = int(rec.get('scene_id', 0))
        scored = []
        for c in clusters:
            sim = _cosine(emb, c.get('centroid'))
            scored.append((sim, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        chosen = scored[0][1] if scored and scored[0][0] >= threshold else None

        # Short/noisy sentence: continuity is safer than inventing a new speaker.
        if chosen is None and previous_cluster is not None and (st - previous_end) <= sticky_gap and scene_id == previous_scene:
            chosen = clusters[previous_cluster]

        if chosen is None and len(clusters) < max_speakers:
            chosen = {'id': len(clusters), 'centroid': emb.copy() if emb is not None else None, 'embeddings': [], 'f0s': [], 'indices': []}
            clusters.append(chosen)
        elif chosen is None and clusters:
            chosen = scored[0][1] if scored else clusters[0]
        elif chosen is None:
            chosen = {'id': 0, 'centroid': emb.copy() if emb is not None else None, 'embeddings': [], 'f0s': [], 'indices': []}
            clusters.append(chosen)

        rec['speaker_id'] = int(chosen['id'])
        rec['speaker_similarity'] = round(max([x[0] for x in scored if x[1] is chosen] or [1.0 if emb is not None else -1.0]), 4)
        chosen['indices'].append(rec['index'])
        if rec.get('source_f0'):
            chosen['f0s'].append(float(rec['source_f0']['median_f0_hz']))
        if emb is not None:
            chosen['embeddings'].append(emb)
            centroid = np.mean(np.stack(chosen['embeddings']), axis=0)
            norm = float(np.linalg.norm(centroid))
            chosen['centroid'] = centroid / norm if norm > 1e-9 else centroid
        previous_cluster = int(chosen['id'])
        previous_end = float(rec['end'])
        previous_scene = scene_id
    return clusters


def _clusters_from_locked_identity(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build speaker groups from externally resolved Character IDs.

    Identity is already fixed by diarization/ASD. F0 values collected here are only
    an optional one-time style hint for choosing a Vietnamese bank voice; they never
    split or merge characters.
    """
    by_id: dict[int, dict[str, Any]] = {}
    for rec in records:
        try:
            sid = int(rec.get("speaker_id"))
        except Exception:
            continue
        c = by_id.setdefault(sid, {
            "id": sid, "centroid": None, "embeddings": [], "f0s": [], "indices": [],
            "ambiguous_count": 0, "identity_methods": set(),
        })
        c["indices"].append(rec["index"])
        if rec.get("source_f0"):
            c["f0s"].append(float(rec["source_f0"]["median_f0_hz"]))
        if rec.get("ambiguous"):
            c["ambiguous_count"] += 1
        if rec.get("identity_method"):
            c["identity_methods"].add(str(rec["identity_method"]))
    return [by_id[k] for k in sorted(by_id)]


def _best_overlap_assignment(target: Any, source_assignments: list[dict[str, Any]], fallback: str) -> dict[str, Any]:
    times = _seg_times(target)
    if not times or not source_assignments:
        return {"profile": fallback, "source_index": None, "method": "fallback"}
    st, en = times
    mid = (st + en) / 2.0
    overlaps = []
    for a in source_assignments:
        ast, aen = float(a["start"]), float(a["end"])
        overlap = max(0.0, min(en, aen) - max(st, ast))
        if overlap > 0:
            overlaps.append((overlap, a))
    if overlaps:
        a = max(overlaps, key=lambda x: x[0])[1]
        return {"profile": a["profile"], "source_index": a["index"], "method": "time_overlap"}
    a = min(source_assignments, key=lambda x: abs(((float(x["start"]) + float(x["end"])) / 2.0) - mid))
    return {"profile": a["profile"], "source_index": a["index"], "method": "nearest_time"}


def classify_character_genders(clusters: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[int, str]:
    """Phân loại giới tính Nam / Nữ cho từng nhân vật dựa trên lời thoại ngữ cảnh và F0."""
    import re
    import json
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    genders: dict[int, str] = {}
    lines_by_char: dict[int, list[str]] = {}
    for r in records:
        sid = r.get("speaker_id")
        if sid is not None and int(sid) >= 0:
            txt = str(r.get("text", "")).strip()
            if txt:
                lines_by_char.setdefault(int(sid), []).append(txt)

    # 1. Thử dùng LLM (DeepSeek) để phân loại ngữ cảnh thông minh nếu có API key
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if deepseek_key and lines_by_char:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
            prompt_lines = []
            for cid in sorted(lines_by_char):
                sample_text = " | ".join(lines_by_char[cid][:10])
                prompt_lines.append(f"CHAR_{cid:02d}: \"{sample_text}\"")

            prompt = (
                "Bạn là chuyên gia đạo diễn lồng tiếng phim. Dựa vào nội dung lời thoại (có thể bằng tiếng Hàn, tiếng Trung hoặc tiếng Việt), "
                "đại từ xưng hô, văn phong giang hồ/học đường/xã hội và ngữ cảnh, "
                "hãy phân loại giới tính của từng nhân vật là 'Nam' hoặc 'Nữ'. "
                "Chỉ trả về JSON định dạng duy nhất: {\"CHAR_00\": \"Nam\", \"CHAR_01\": \"Nam\", ...}\n\n"
                + "\n".join(prompt_lines)
            )
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                timeout=12
            )
            content = resp.choices[0].message.content or ""
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
                for k, v in parsed.items():
                    num_match = re.search(r"\d+", str(k))
                    if num_match:
                        c_num = int(num_match.group(0))
                        g = "female" if "nữ" in str(v).lower() else "male"
                        genders[c_num] = g
                        print(f"[GenderClassifier] LLM phân loại Nhân vật {k} -> {g.upper()} ({v})")
        except Exception as e:
            print(f"[GenderClassifier] LLM phân loại cảnh báo ({e}), dùng heuristic...")

    # 2. Heuristic đại từ xưng hô (Việt + Hàn) + F0 cho các character chưa có gender
    for c in clusters:
        cid = int(c.get("id", 0))
        if cid in genders:
            continue
        all_text = " ".join(lines_by_char.get(cid, [])).lower()
        
        # Tiếng Việt + Tiếng Hàn xưng hô
        male_score = sum(all_text.count(w) for w in [
            "anh", "thằng", "ông", "chú", "cậu", "thầy", "đại ca", "bố", "cha", "con trai", "huynh", "đệ", "hắn", "tao", "mày",
            "새끼", "놈", "형", "오빠", "아저씨", "인마", "자식"
        ])
        female_score = sum(all_text.count(w) for w in [
            "chị", "cô", "mẹ", "em gái", "bà", "nàng", "muội", "tiểu thư", "nữ",
            "언니", "누나", "아줌마", "아가씨", "그녀"
        ])
        
        if male_score > female_score:
            genders[cid] = "male"
        elif female_score > male_score:
            genders[cid] = "female"
        else:
            f0_list = c.get("f0s") or []
            med_f0 = float(np.median(f0_list)) if f0_list else 150.0
            # Giọng nam bị nhân đôi quãng 8 do nhạc nền thường đo được 190Hz - 250Hz (nguyên bản là 95 - 125Hz)
            if med_f0 >= 260.0:
                genders[cid] = "female"
            else:
                genders[cid] = "male"
        print(f"[GenderClassifier] Heuristic phân loại Nhân vật CHAR_{cid:02d} -> {genders[cid].upper()}")
    return genders



def match_whisper_segments(
    video_path: str,
    source_segments: Iterable[Any],
    target_segments: Iterable[Any],
    *,
    config_data: dict[str, Any],
    cfg: dict[str, Any],
    report_path: str | None = None,
) -> dict[str, Any]:
    """Resolve Character ID first, then lock one Vietnamese voice per character with gender classification."""
    source = list(source_segments or [])
    target = list(target_segments or [])
    if not source:
        raise RuntimeError("MOVIE_MATCH_NO_WHISPER_SEGMENTS")

    bank = build_voice_bank(config_data, list(cfg.get("voice_bank") or []), cfg=cfg)
    sr = int(cfg.get("sample_rate", 16000))
    audio = _extract_mono(video_path, sr=sr)
    fmin = float(cfg.get("f0_min_hz", 70.0))
    fmax = float(cfg.get("f0_max_hz", 420.0))
    switch_margin = float(cfg.get("switch_margin_cents", 55.0))
    sticky_gap = float(cfg.get("sticky_gap_sec", 1.8))
    fallback = str(cfg.get("fallback_voice") or bank[0]["profile"])
    identity_cfg = cfg.get("character_identity") if isinstance(cfg.get("character_identity"), dict) else {}
    identity_report: dict[str, Any] | None = None
    identity_by_index: dict[int, dict[str, Any]] = {}
    if identity_cfg.get("enabled", False):
        try:
            identity_report = character_identity.resolve_character_identities(
                video_path=video_path, source_segments=source, cfg=identity_cfg
            )
            identity_by_index = {
                int(r["index"]): r for r in (identity_report.get("segments") or []) if "index" in r
            }
        except Exception as exc:
            print(f"[MovieVoiceMatcher] Character ID fallback: {exc}")
            identity_report = {
                "segments": [],
                "stats": {"status": "failed", "backend_error": f"{type(exc).__name__}:{exc}", "identity_uses_f0": False},
            }

    speaker_lock = bool(identity_by_index) or bool(cfg.get('speaker_lock_enabled', True))
    octave_correction = bool(cfg.get('octave_correction', True))

    scenes = []
    if bool(cfg.get("use_scene_reset", True)):
        try:
            scenes = detect_scene_ranges(video_path)
        except Exception as exc:
            print(f"[MovieVoiceMatcher] Scene detection skipped: {exc}")

    records: list[dict[str, Any]] = []
    for idx, seg in enumerate(source):
        times = _seg_times(seg)
        if not times:
            continue
        st, en = times
        pad = min(0.08, max(0.0, (en - st) * 0.08))
        mst, men = st + pad, en - pad
        if men <= mst:
            mst, men = st, en
        measurement = _measure_window(audio, sr, mst, men, fmin_hz=fmin, fmax_hz=fmax)
        identity_row = identity_by_index.get(idx)
        voiceprint = None if identity_row else _voiceprint_window(audio, sr, mst, men)
        scene_id = int(scene_for_time(scenes, (st + en) / 2.0).get("scene_id", 0)) if scenes else 0
        row = {
            "index": idx, "start": round(st, 3), "end": round(en, 3),
            "text": _seg_text(seg), "scene_id": scene_id,
            "source_f0": measurement, "_voiceprint": voiceprint,
        }
        if identity_row:
            for key in (
                "speaker_id", "speaker_label", "speaker_confidence", "speaker_margin",
                "ambiguous", "identity_method", "active_track_id", "active_track_score",
            ):
                if key in identity_row:
                    row[key] = identity_row[key]
        records.append(row)

    assignments: list[dict[str, Any]] = []
    speaker_profiles: list[dict[str, Any]] = []
    if speaker_lock:
        clusters = _clusters_from_locked_identity(records) if identity_by_index else _cluster_speakers(records, cfg, fmin, fmax)
        by_id = {int(c['id']): c for c in clusters}
        character_genders = classify_character_genders(clusters, records)

        # 1. Gán gender và tính canonical F0 cho từng cluster
        for c in clusters:
            cid = int(c['id'])
            char_gender = character_genders.get(cid, "male")
            c['gender'] = char_gender
            canonical = _canonical_cluster_f0(c.get('f0s') or [], fmin, fmax, octave_correction)
            if char_gender == "male" and canonical and canonical >= 180.0:
                canonical = canonical / 2.0  # Hoàn nguyên tần số quãng tám bị nhân đôi do BGM
            c['canonical_f0_hz'] = round(canonical, 2) if canonical else None

        # 2. Phân bổ giọng đa dạng (Unique Voice): Nhân vật chính nhiều thoại nhất ưu tiên chọn trước
        used_voices_by_gender: dict[str, set[str]] = {"male": set(), "female": set()}
        sorted_clusters = sorted(clusters, key=lambda x: len(x.get('indices') or []), reverse=True)

        for c in sorted_clusters:
            cid = int(c['id'])
            char_gender = c['gender']
            canonical = c.get('canonical_f0_hz')

            # Lọc voice bank theo giới tính đã phân loại
            if char_gender == "male":
                gender_bank = [v for v in bank if not ('nu_' in v['profile'] or 'hoaimy' in v['profile'] or v.get('gender') == 'female')]
            else:
                gender_bank = [v for v in bank if ('nu_' in v['profile'] or 'hoaimy' in v['profile'] or v.get('gender') == 'female')]

            if not gender_bank:
                gender_bank = bank

            ranked = _rank(canonical, gender_bank) if canonical else []
            
            # Ưu tiên chọn voice độc nhất chưa được gán cho nhân vật khác cùng giới tính
            selected = None
            if ranked:
                for candidate in ranked:
                    cand_prof = str(candidate['profile'])
                    if cand_prof not in used_voices_by_gender[char_gender]:
                        selected = cand_prof
                        break
                if not selected:
                    selected = str(ranked[0]['profile'])
            else:
                for cand in gender_bank:
                    cand_prof = str(cand['profile'])
                    if cand_prof not in used_voices_by_gender[char_gender]:
                        selected = cand_prof
                        break
                if not selected:
                    selected = str(gender_bank[0]['profile'])

            used_voices_by_gender[char_gender].add(selected)
            c['profile'] = selected
            c['top3'] = ranked[:3]
            seg_cnt = len(c.get('indices') or [])
            print(f"[MovieVoiceMatcher] Nhân vật CHAR_{cid:02d} ({char_gender.upper()} - {seg_cnt} câu - {canonical}Hz) -> Khóa giọng: {selected}")
            speaker_profiles.append({
                'speaker_id': int(c['id']), 'profile': selected,
                'canonical_f0_hz': c['canonical_f0_hz'],
                'gender': char_gender,
                'segment_count': seg_cnt, 'top3': ranked[:3],
                'ambiguous_count': int(c.get('ambiguous_count', 0)),
                'identity_methods': sorted(c.get('identity_methods') or []),
            })
        for rec in records:
            c = by_id.get(int(rec.get('speaker_id', 0)))
            selected = str(c.get('profile') if c else fallback)
            out = {k: v for k, v in rec.items() if k != '_voiceprint'}
            out.update({
                'profile': selected,
                'method': 'character_identity_locked' if identity_by_index else 'speaker_cluster_locked',
                'top3': list(c.get('top3') or [])[:3] if c else [],
            })
            assignments.append(out)

    else:
        previous_profile: str | None = None
        previous_end = -1.0
        previous_scene: int | None = None
        for rec in records:
            st, en, scene_id = float(rec['start']), float(rec['end']), int(rec.get('scene_id', 0))
            measurement = rec.get('source_f0')
            if not measurement:
                selected = previous_profile or fallback
                ranked = []
                method = 'fallback_no_f0'
            else:
                src_hz = float(measurement['median_f0_hz'])
                ranked = _rank(src_hz, bank)
                best = ranked[0]
                selected = str(best['profile'])
                method = 'nearest_cents'
                if previous_profile and (st - previous_end) <= sticky_gap and scene_id == previous_scene:
                    prev_candidate = next((x for x in ranked if x['profile'] == previous_profile), None)
                    if prev_candidate and float(prev_candidate['distance_cents']) <= float(best['distance_cents']) + switch_margin:
                        selected = previous_profile
                        method = 'sticky_near_best'
            out = {k: v for k, v in rec.items() if k != '_voiceprint'}
            out.update({'profile': selected, 'method': method, 'top3': ranked[:3]})
            assignments.append(out)
            previous_profile, previous_end, previous_scene = selected, en, scene_id

    target_assignments = []
    for idx, seg in enumerate(target):
        m = _best_overlap_assignment(seg, assignments, fallback)
        times = _seg_times(seg) or (0.0, 0.0)
        source_a = next((a for a in assignments if a.get('index') == m.get('source_index')), None)
        target_assignments.append({
            "index": idx, "start": round(times[0], 3), "end": round(times[1], 3),
            "text": _seg_text(seg), **m,
            "speaker_id": source_a.get('speaker_id') if source_a else None,
        })

    coverage = 0.0
    if assignments:
        coverage = sum(1 for a in assignments if a.get("source_f0")) / len(assignments)

    identity_stats = (identity_report or {}).get("stats") or {}
    report = {
        "method": "character_identity_locked_voice" if identity_by_index else "whisper_sentence_measurement_speaker_locked_voice",
        "note": (
            "Character identity is resolved by speaker diarization/embedding and optional Light-ASD, not by F0. "
            "F0 is only an optional one-time hint to choose a bundled Vietnamese voice for each locked character; no pitch shift is applied."
            if identity_by_index else
            "Compatibility fallback: local acoustic speaker clustering is used. F0 never creates a speaker ID; it only chooses a bank voice after a cluster is locked."
        ),
        "identity": identity_report,
        "voice_bank": bank,
        "speaker_profiles": speaker_profiles,
        "source_segments": assignments,
        "target_assignments": target_assignments,
        "stats": {
            "source_segment_count": len(source),
            "matched_segment_count": len(assignments),
            "target_segment_count": len(target),
            "f0_coverage": round(coverage, 4),
            "speaker_cluster_count": len(speaker_profiles) if speaker_lock else None,
            "character_count": int(identity_stats.get("speaker_count", len(speaker_profiles))) if speaker_lock else None,
            "identity_backend": identity_stats.get("backend"),
            "identity_ambiguous_count": identity_stats.get("ambiguous_count"),
            "light_asd": identity_stats.get("light_asd"),
            "identity_uses_f0": bool(identity_stats.get("identity_uses_f0", False)) if identity_report else False,
            "unique_voices": sorted({a["profile"] for a in target_assignments}),
        },
    }
    if report_path:
        p = Path(report_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
