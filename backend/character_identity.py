from __future__ import annotations

"""Character identity resolver for long-form Chinese-source dubbing.

Identity and voice style are intentionally separate concerns:
- speaker identity comes from speaker diarization / embeddings (WeSpeaker), not F0.
- Light-ASD is only an ambiguity verifier and is never required for every frame.
- a lightweight spectral embedding fallback keeps old installs functional when the
  optional models have not been installed yet.

The returned ``speaker_id`` is stable for the whole input video as far as the
primary diarizer can determine. It is safe to use it as the key that pins one
Vietnamese TTS profile to one character.
"""

import math
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any, Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
_WESPEAKER_CACHE: dict[tuple[str, str], Any] = {}


def _prepare_torchaudio_compat() -> None:
    """Provide removed no-op/optional APIs needed while importing s3prl / wespeaker."""
    try:
        from .torchaudio_compat import apply_torchaudio_compat
    except ImportError:
        try:
            from torchaudio_compat import apply_torchaudio_compat
        except ImportError:
            apply_torchaudio_compat = None
    if apply_torchaudio_compat:
        apply_torchaudio_compat()


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


def _extract_pcm16_wav(video_path: str, out_wav: Path, sr: int = 16000) -> None:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            _ffmpeg(), "-y", "-v", "error", "-i", str(video_path), "-vn",
            "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", str(out_wav),
        ],
        check=True,
    )


def _read_pcm16_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        channels = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        x = x.reshape(-1, channels).mean(axis=1)
    return x, int(sr)


def _load_wespeaker(cfg: dict[str, Any]):
    model_name = str(cfg.get("model") or cfg.get("language") or "chinese")
    device = str(cfg.get("device") or "cuda:0")
    key = (model_name, device)
    if key in _WESPEAKER_CACHE:
        return _WESPEAKER_CACHE[key]
    try:
        _prepare_torchaudio_compat()
        import wespeaker  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"WESPEAKER_IMPORT_FAILED:{type(exc).__name__}:{exc}") from exc
    model = wespeaker.load_model(model_name)
    try:
        model.set_device(device)
    except Exception:
        if bool(cfg.get("allow_cpu_fallback", True)):
            model.set_device("cpu")
            device = "cpu"
        else:
            raise
    _WESPEAKER_CACHE[(model_name, device)] = model
    _WESPEAKER_CACHE[key] = model
    return model


def _flatten_diarization(raw: Any) -> list[dict[str, Any]]:
    """Normalize WeSpeaker diarization variants to start/end/label rows."""
    out: list[dict[str, Any]] = []

    def visit(obj: Any) -> None:
        if obj is None:
            return
        if isinstance(obj, dict):
            if {"start", "end"}.issubset(obj):
                try:
                    st, en = float(obj["start"]), float(obj["end"])
                    label = obj.get("label", obj.get("speaker", obj.get("speaker_id", "spk0")))
                    if en > st:
                        out.append({"start": st, "end": en, "label": str(label)})
                except Exception:
                    pass
                return
            for value in obj.values():
                visit(value)
            return
        if isinstance(obj, (list, tuple)):
            # Current WeSpeaker format: (utt, begin, end, label)
            if len(obj) >= 4:
                try:
                    st, en = float(obj[-3]), float(obj[-2])
                    label = str(obj[-1])
                    if en > st:
                        out.append({"start": st, "end": en, "label": label})
                        return
                except Exception:
                    pass
            # Common compact format: (begin, end, label)
            if len(obj) == 3:
                try:
                    st, en = float(obj[0]), float(obj[1])
                    if en > st:
                        out.append({"start": st, "end": en, "label": str(obj[2])})
                        return
                except Exception:
                    pass
            for value in obj:
                visit(value)

    visit(raw)
    out.sort(key=lambda x: (x["start"], x["end"], x["label"]))
    return out


def _speaker_rows_from_diarization(
    segments: list[Any], diar: list[dict[str, Any]], cfg: dict[str, Any]
) -> list[dict[str, Any]]:
    min_overlap = float(cfg.get("min_overlap_ratio", 0.52))
    ambiguity_margin = float(cfg.get("ambiguity_margin_ratio", 0.16))
    nearest_gap = float(cfg.get("nearest_gap_sec", 0.8))

    # IDs are assigned in first-appearance order, not arbitrary HDBSCAN label order.
    first_seen: dict[str, float] = {}
    for d in diar:
        first_seen.setdefault(str(d["label"]), float(d["start"]))
    ordered_labels = sorted(first_seen, key=lambda k: first_seen[k])
    label_to_id = {label: i for i, label in enumerate(ordered_labels)}

    rows: list[dict[str, Any]] = []
    previous_label: str | None = None
    previous_end = -1.0
    sticky_gap = float(cfg.get("sticky_gap_sec", 1.2))

    for idx, seg in enumerate(segments):
        times = _seg_times(seg)
        if not times:
            continue
        st, en = times
        dur = max(1e-6, en - st)
        by_label: dict[str, float] = {}
        for d in diar:
            if d["end"] <= st:
                continue
            if d["start"] >= en:
                break
            ov = max(0.0, min(en, float(d["end"])) - max(st, float(d["start"])))
            if ov > 0:
                by_label[str(d["label"])] = by_label.get(str(d["label"]), 0.0) + ov

        ranked = sorted(by_label.items(), key=lambda x: x[1], reverse=True)
        method = "wespeaker_overlap"
        if ranked:
            label, best = ranked[0]
            second = ranked[1][1] if len(ranked) > 1 else 0.0
            coverage = min(1.0, best / dur)
            margin = max(0.0, (best - second) / dur)
            ambiguous = coverage < min_overlap or (len(ranked) > 1 and margin < ambiguity_margin)
        else:
            mid = (st + en) / 2.0
            nearest = None
            nearest_dist = float("inf")
            for d in diar:
                if d["start"] <= mid <= d["end"]:
                    dist = 0.0
                else:
                    dist = min(abs(mid - float(d["start"])), abs(mid - float(d["end"])))
                if dist < nearest_dist:
                    nearest_dist, nearest = dist, d
            if nearest is not None and nearest_dist <= nearest_gap:
                label = str(nearest["label"])
                coverage = 0.0
                margin = 0.0
                ambiguous = True
                method = "wespeaker_nearest"
            elif previous_label is not None and st - previous_end <= sticky_gap:
                label = previous_label
                coverage = 0.0
                margin = 0.0
                ambiguous = True
                method = "wespeaker_continuity"
            else:
                label = f"unresolved_{idx}"
                if label not in label_to_id:
                    label_to_id[label] = len(label_to_id)
                coverage = 0.0
                margin = 0.0
                ambiguous = True
                method = "wespeaker_unresolved"

        if label not in label_to_id:
            label_to_id[label] = len(label_to_id)
        rows.append({
            "index": idx,
            "start": round(st, 3),
            "end": round(en, 3),
            "speaker_label": label,
            "speaker_id": int(label_to_id[label]),
            "speaker_confidence": round(float(coverage), 4),
            "speaker_margin": round(float(margin), 4),
            "ambiguous": bool(ambiguous),
            "identity_method": method,
        })
        previous_label, previous_end = label, en
    return rows


def _spectral_embedding(audio: np.ndarray, sr: int, start: float, end: float) -> np.ndarray | None:
    """Fallback timbre embedding. It intentionally does not estimate pitch/F0."""
    a = max(0, int(start * sr))
    b = min(len(audio), int(end * sr))
    x = np.asarray(audio[a:b], dtype=np.float32)
    frame_len = max(400, int(0.050 * sr))
    hop = max(200, int(0.025 * sr))
    if len(x) < frame_len * 3:
        return None
    win = np.hanning(frame_len).astype(np.float32)
    freqs = np.fft.rfftfreq(frame_len, d=1.0 / sr)
    edges = np.geomspace(90.0, min(6500.0, sr * 0.47), 33)
    vectors: list[list[float]] = []
    rms_values: list[float] = []
    frames: list[np.ndarray] = []
    for pos in range(0, len(x) - frame_len + 1, hop):
        fr = x[pos:pos + frame_len]
        frames.append(fr)
        rms_values.append(float(np.sqrt(np.mean(fr.astype(np.float64) ** 2))))
    if not frames:
        return None
    gate = max(1e-4, float(np.percentile(np.asarray(rms_values), 50)))
    for fr, rms in zip(frames, rms_values):
        if rms < gate:
            continue
        spec = np.abs(np.fft.rfft(fr * win)) ** 2
        total = float(np.sum(spec)) + 1e-12
        bands = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            mask = (freqs >= lo) & (freqs < hi)
            bands.append(math.log1p(float(np.sum(spec[mask])) / total) if np.any(mask) else 0.0)
        vectors.append(bands)
    if len(vectors) < 3:
        return None
    v = np.median(np.asarray(vectors, dtype=np.float64), axis=0)
    v -= np.mean(v)
    norm = float(np.linalg.norm(v))
    return (v / norm).astype(np.float32) if norm > 1e-9 else None


def _cosine(a: np.ndarray | None, b: np.ndarray | None) -> float:
    if a is None or b is None:
        return -1.0
    den = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / den) if den > 1e-9 else -1.0


def _fallback_spectral_rows(audio: np.ndarray, sr: int, segments: list[Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    threshold = float(cfg.get("fallback_similarity_threshold", 0.80))
    max_speakers = max(1, int(cfg.get("max_speakers", 8)))
    sticky_gap = float(cfg.get("sticky_gap_sec", 1.2))
    clusters: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None

    for idx, seg in enumerate(segments):
        times = _seg_times(seg)
        if not times:
            continue
        st, en = times
        emb = _spectral_embedding(audio, sr, st, en)
        scored = sorted(((_cosine(emb, c.get("centroid")), c) for c in clusters), key=lambda x: x[0], reverse=True)
        chosen = scored[0][1] if scored and scored[0][0] >= threshold else None
        method = "spectral_embedding"
        if chosen is None and previous and st - float(previous["end"]) <= sticky_gap:
            chosen = clusters[int(previous["speaker_id"])]
            method = "spectral_continuity"
        if chosen is None and len(clusters) < max_speakers:
            chosen = {"id": len(clusters), "vectors": [], "centroid": emb.copy() if emb is not None else None}
            clusters.append(chosen)
            method = "spectral_new_cluster"
        elif chosen is None:
            chosen = scored[0][1] if scored else clusters[0]
            method = "spectral_forced_cluster"
        sim = max([s for s, c in scored if c is chosen] or [1.0 if emb is not None else -1.0])
        ambiguous = emb is None or sim < threshold + 0.05
        if emb is not None:
            chosen["vectors"].append(emb)
            centroid = np.mean(np.stack(chosen["vectors"]), axis=0)
            norm = float(np.linalg.norm(centroid))
            chosen["centroid"] = centroid / norm if norm > 1e-9 else centroid
        row = {
            "index": idx, "start": round(st, 3), "end": round(en, 3),
            "speaker_label": f"spectral_{int(chosen['id'])}",
            "speaker_id": int(chosen["id"]),
            "speaker_confidence": round(max(0.0, sim), 4),
            "speaker_margin": 0.0,
            "ambiguous": bool(ambiguous),
            "identity_method": method,
        }
        rows.append(row)
        previous = row
    return rows


def _resolve_existing(path_value: Any, base: Path = ROOT) -> Path | None:
    if not path_value:
        return None
    p = Path(str(path_value)).expanduser()
    if not p.is_absolute():
        p = base / p
    return p.resolve() if p.exists() else None


def _ambiguous_chunks(rows: list[dict[str, Any]], cfg: dict[str, Any]) -> list[tuple[float, float]]:
    padding = float(cfg.get("window_padding_sec", 1.4))
    merge_gap = float(cfg.get("merge_gap_sec", 1.2))
    max_chunk = float(cfg.get("max_chunk_sec", 24.0))
    spans = [(max(0.0, float(r["start"]) - padding), float(r["end"]) + padding) for r in rows if r.get("ambiguous")]
    if not spans:
        return []
    spans.sort()
    merged: list[tuple[float, float]] = []
    for st, en in spans:
        if not merged:
            merged.append((st, en))
            continue
        pst, pen = merged[-1]
        if st - pen <= merge_gap and max(en, pen) - pst <= max_chunk:
            merged[-1] = (pst, max(pen, en))
        else:
            merged.append((st, en))
    return merged[: int(cfg.get("max_chunks", 40))]


def _light_asd_track_scores(
    video_path: str,
    chunk: tuple[float, float],
    cfg: dict[str, Any],
    temp_root: Path,
    chunk_index: int,
) -> dict[str, Any]:
    repo = _resolve_existing(cfg.get("repo_path") or "external/Light-ASD")
    if repo is None or not (repo / "Columbia_test.py").is_file():
        return {"ok": False, "reason": "LIGHT_ASD_REPO_MISSING"}
    model = _resolve_existing(cfg.get("model_path") or "external/Light-ASD/weight/finetuning_TalkSet.model")
    if model is None:
        fallback_model = repo / "weight" / "pretrain_AVA_CVPR.model"
        model = fallback_model if fallback_model.is_file() else None
    if model is None:
        return {"ok": False, "reason": "LIGHT_ASD_MODEL_MISSING"}

    st, en = chunk
    chunk_dir = temp_root / f"asd_{chunk_index:03d}"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    clip = chunk_dir / "clip.mp4"
    subprocess.run([
        _ffmpeg(), "-y", "-v", "error", "-ss", f"{st:.3f}", "-to", f"{en:.3f}",
        "-i", str(video_path), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264",
        "-preset", "ultrafast", "-crf", "24", "-c:a", "aac", "-b:a", "128k", str(clip)
    ], check=True)
    cmd = [
        str(cfg.get("python") or sys.executable), str(repo / "Columbia_test.py"),
        "--videoName", "clip", "--videoFolder", str(chunk_dir),
        "--pretrainModel", str(model),
    ]
    env = os.environ.copy()
    env.setdefault("CUDA_VISIBLE_DEVICES", str(cfg.get("cuda_visible_devices", "0")))
    timeout = float(cfg.get("timeout_sec", 420.0))
    proc = subprocess.run(cmd, cwd=str(repo), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, timeout=timeout)
    if proc.returncode != 0:
        return {"ok": False, "reason": "LIGHT_ASD_FAILED", "log_tail": proc.stdout[-3000:]}
    work = chunk_dir / "clip" / "pywork"
    tracks_path, scores_path = work / "tracks.pckl", work / "scores.pckl"
    if not tracks_path.is_file() or not scores_path.is_file():
        return {"ok": False, "reason": "LIGHT_ASD_OUTPUT_MISSING", "log_tail": proc.stdout[-1500:]}
    with tracks_path.open("rb") as f:
        tracks = pickle.load(f)
    with scores_path.open("rb") as f:
        scores = pickle.load(f)
    parsed: list[dict[str, Any]] = []
    for tidx, track in enumerate(tracks):
        try:
            frames = np.asarray(track["track"]["frame"], dtype=np.int64)
            score = np.asarray(scores[tidx], dtype=np.float32).reshape(-1)
            if frames.size == 0 or score.size == 0:
                continue
            parsed.append({"track_id": int(tidx), "frames": frames, "scores": score})
        except Exception:
            continue
    return {"ok": True, "start": st, "end": en, "tracks": parsed, "log_tail": proc.stdout[-1000:]}


def _attach_light_asd(rows: list[dict[str, Any]], video_path: str, cfg: dict[str, Any]) -> dict[str, Any]:
    if not cfg.get("enabled", False):
        return {"status": "disabled", "chunks": 0, "verified": 0, "overrides": 0}
    chunks = _ambiguous_chunks(rows, cfg)
    if not chunks:
        return {"status": "not_needed", "chunks": 0, "verified": 0, "overrides": 0}

    min_score = float(cfg.get("min_active_score", 0.0))
    min_margin = float(cfg.get("min_track_margin", 0.25))
    results: list[dict[str, Any]] = []
    verified = 0
    overrides = 0
    with tempfile.TemporaryDirectory(prefix="character_asd_") as td:
        root = Path(td)
        for ci, chunk in enumerate(chunks):
            try:
                r = _light_asd_track_scores(video_path, chunk, cfg, root, ci)
            except Exception as exc:
                r = {"ok": False, "reason": f"LIGHT_ASD_EXCEPTION:{type(exc).__name__}:{exc}"}
            results.append({k: v for k, v in r.items() if k != "tracks"})
            if not r.get("ok"):
                continue
            cst = float(r["start"])
            chunk_rows = [x for x in rows if float(x["end"]) > cst and float(x["start"]) < float(r["end"])]
            # First attach an active local face-track id to every speech segment in the chunk.
            for row in chunk_rows:
                fst = int(max(0.0, float(row["start"]) - cst) * 25.0)
                fen = int(max(0.0, float(row["end"]) - cst) * 25.0) + 1
                candidates = []
                for tr in r.get("tracks") or []:
                    frames = tr["frames"]
                    mask_idx = np.where((frames >= fst) & (frames < fen))[0]
                    if mask_idx.size == 0:
                        continue
                    score = tr["scores"]
                    vals = [float(score[min(int(i), len(score) - 1)]) for i in mask_idx]
                    candidates.append((float(np.mean(vals)), int(tr["track_id"])))
                candidates.sort(reverse=True)
                if candidates:
                    best_score, track_id = candidates[0]
                    second = candidates[1][0] if len(candidates) > 1 else -999.0
                    if best_score >= min_score and best_score - second >= min_margin:
                        row["active_track_id"] = f"chunk{ci}:track{track_id}"
                        row["active_track_score"] = round(best_score, 3)
                        verified += 1

            # Learn local face-track -> global audio speaker from confident rows.
            votes: dict[str, dict[int, float]] = {}
            for row in chunk_rows:
                track_id = row.get("active_track_id")
                if not track_id or row.get("ambiguous"):
                    continue
                spk = int(row["speaker_id"])
                weight = max(0.1, float(row.get("speaker_confidence", 0.0))) * max(0.1, float(row["end"]) - float(row["start"]))
                votes.setdefault(str(track_id), {})[spk] = votes.setdefault(str(track_id), {}).get(spk, 0.0) + weight
            track_to_speaker: dict[str, int] = {}
            for track_id, by_spk in votes.items():
                total = sum(by_spk.values())
                spk, weight = max(by_spk.items(), key=lambda x: x[1])
                if total > 0 and weight / total >= float(cfg.get("association_min_share", 0.62)):
                    track_to_speaker[track_id] = int(spk)

            # Only ambiguous rows may be overridden, and only from a locally anchored track.
            for row in chunk_rows:
                if not row.get("ambiguous"):
                    continue
                track_id = row.get("active_track_id")
                if track_id and track_id in track_to_speaker:
                    new_spk = track_to_speaker[track_id]
                    if int(row["speaker_id"]) != new_spk:
                        row["speaker_id"] = new_spk
                        row["identity_method"] = "light_asd_tiebreak"
                        overrides += 1
                    row["ambiguous"] = False
    status = "ok" if any(x.get("ok") for x in results) else "unavailable"
    return {"status": status, "chunks": len(chunks), "verified": verified, "overrides": overrides, "details": results}


def _renumber_by_first_appearance(rows: list[dict[str, Any]]) -> None:
    remap: dict[int, int] = {}
    for row in sorted(rows, key=lambda r: (float(r["start"]), int(r["index"]))):
        old = int(row["speaker_id"])
        if old not in remap:
            remap[old] = len(remap)
        row["speaker_id"] = remap[old]
        row["speaker_label"] = f"CHAR_{remap[old] + 1:02d}"


def resolve_character_identities(
    *,
    video_path: str,
    source_segments: Iterable[Any],
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = dict(cfg or {})
    segments = list(source_segments or [])
    if not segments:
        return {"segments": [], "stats": {"status": "empty", "speaker_count": 0}}
    if not bool(cfg.get("enabled", True)):
        return {"segments": [], "stats": {"status": "disabled", "speaker_count": 0}}

    sr = int(cfg.get("sample_rate", 16000))
    backend = str(cfg.get("backend") or "wespeaker").lower()
    error: str | None = None
    diar_count = 0
    with tempfile.TemporaryDirectory(prefix="character_identity_") as td:
        wav_path = Path(td) / "source.wav"
        _extract_pcm16_wav(video_path, wav_path, sr=sr)
        rows: list[dict[str, Any]] = []
        if backend == "wespeaker":
            try:
                model = _load_wespeaker(cfg)
                raw = model.diarize(str(wav_path), "source")
                diar = _flatten_diarization(raw)
                if not diar:
                    raise RuntimeError("WESPEAKER_EMPTY_DIARIZATION")
                diar_count = len(diar)
                rows = _speaker_rows_from_diarization(segments, diar, cfg)
            except Exception as exc:
                error = f"{type(exc).__name__}:{exc}"
                if not bool(cfg.get("allow_fallback", True)):
                    raise
        if not rows:
            audio, actual_sr = _read_pcm16_wav(wav_path)
            rows = _fallback_spectral_rows(audio, actual_sr, segments, cfg)
            backend = "spectral_fallback"

    asd_cfg = cfg.get("light_asd") if isinstance(cfg.get("light_asd"), dict) else {}
    asd_stats = _attach_light_asd(rows, video_path, asd_cfg)
    _renumber_by_first_appearance(rows)
    count = len({int(r["speaker_id"]) for r in rows})
    ambiguous = sum(1 for r in rows if r.get("ambiguous"))
    return {
        "segments": rows,
        "stats": {
            "status": "ok",
            "backend": backend,
            "backend_error": error,
            "speaker_count": count,
            "segment_count": len(rows),
            "diarization_turn_count": diar_count,
            "ambiguous_count": ambiguous,
            "ambiguous_ratio": round(ambiguous / max(1, len(rows)), 4),
            "light_asd": asd_stats,
            "identity_uses_f0": False,
        },
    }
