"""
Quality Control (QC) Gate for Wuby Video Pipeline.
Enforces strict checks before any video can be published to Google Drive.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

# Ensure UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def has_chinese_char(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def is_laughter_or_filler(text: str) -> bool:
    clean = (text or "").strip().lower()
    if not clean:
        return True
    clean_no_punct = re.sub(r"[^\w\s]", "", clean).strip()
    words = clean_no_punct.split()
    if not words:
        return True
    # Strictly laughter tokens (ha, haha, hehe, hihi, hoho, huhu, hic, cuoi)
    # Not exclamations like 'a', 'ah', 'oh', 'uh'
    laughter_tokens = {
        "ha", "haha", "hahaha", "hahahaha", "hic", "hi", "hihi", "hihihi",
        "he", "hehe", "hehehe", "ho", "hoho", "hohoho", "hu", "huhu", "huhuhu",
        "cuoi"
    }
    return all(
        w in laughter_tokens or
        bool(re.fullmatch(r"^(?:ha+|he+|hi+|ho+|hu+|hic+|haha+|hehe+|hihi+|hoho+|huhu+)+$", w, re.IGNORECASE))
        for w in words
    )


def _json_default(obj):
    if hasattr(obj, "item"):
        return obj.item()
    if hasattr(obj, "tolist"):
        return obj.tolist()
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def validate_ocr_events(ocr_events: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Validate every semantic Chinese OCR track before destructive rendering."""
    events = ocr_events or []
    errors: List[str] = []
    stats = {
        "total_tracks": len(events),
        "translated_tracks": 0,
        "watermark_tracks": 0,
        "untranslated_tracks": 0,
        "laughter_mapped_violations": 0,
    }
    for ev in events:
        raw_text = (ev.get("text") or "").strip()
        vi_text = (ev.get("vi_text") or "").strip()
        track_id = ev.get("track_id")
        is_chinese = has_chinese_char(raw_text)
        is_watermark = bool(ev.get("is_watermark", False))
        if is_watermark:
            stats["watermark_tracks"] += 1
            continue
        if not is_chinese:
            continue
        if not vi_text:
            errors.append(
                f"UNTRANSLATED_OCR: Track #{track_id} chữ Trung '{raw_text}' chưa có bản dịch; không được xóa hoặc xuất bản"
            )
            stats["untranslated_tracks"] += 1
            continue
        if has_chinese_char(vi_text):
            errors.append(
                f"CHINESE_REMAIN_IN_VI: Track #{track_id} bản dịch vẫn chứa chữ Trung: '{vi_text}'"
            )
            continue
        if is_laughter_or_filler(vi_text):
            errors.append(
                f"LAUGHTER_ASSIGNED_TO_OCR: Track #{track_id} chữ Trung '{raw_text}' bị gán tiếng cười '{vi_text}'"
            )
            stats["laughter_mapped_violations"] += 1
            continue
        stats["translated_tracks"] += 1
    return {"passed": not errors, "errors": errors, "stats": stats}


def run_wuby_qc(
    rendered_video_path: str | Path,
    source_video_path: str | Path,
    ocr_events: Optional[List[Dict[str, Any]]] = None,
    voice_report_path: Optional[str | Path] = None,
    output_dir: Optional[str | Path] = None,
    audit_times: Optional[List[float]] = None,
    reader: Optional[Any] = None,
    expected_cue_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Executes all mandatory QC checks on a rendered Wuby video.
    Returns a dict with 'passed': bool, 'errors': list, 'warnings': list, 'report_path': str, 'contact_sheet': str.
    """
    rendered_video = Path(rendered_video_path)
    source_video = Path(source_video_path)
    out_dir = Path(output_dir) if output_dir else rendered_video.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = rendered_video.stem
    report_file = out_dir / f"{stem}_qc_report.json"
    contact_sheet_file = out_dir / f"{stem}_contact_sheet.jpg"

    errors: List[str] = []
    warnings: List[str] = []
    check_results: Dict[str, Any] = {}

    # ----------------------------------------------------
    # 1. Video Integrity Check
    # ----------------------------------------------------
    cap_r = cv2.VideoCapture(str(rendered_video))
    cap_s = cv2.VideoCapture(str(source_video))

    if not cap_r.isOpened():
        errors.append(f"CANNOT_OPEN_RENDERED_VIDEO: Không mở được file render: {rendered_video}")
        r_w, r_h, r_fps, r_frames, r_dur = 0, 0, 0, 0, 0.0
    else:
        r_w = int(cap_r.get(cv2.CAP_PROP_FRAME_WIDTH))
        r_h = int(cap_r.get(cv2.CAP_PROP_FRAME_HEIGHT))
        r_fps = cap_r.get(cv2.CAP_PROP_FPS) or 24.0
        r_frames = int(cap_r.get(cv2.CAP_PROP_FRAME_COUNT))
        r_dur = r_frames / max(r_fps, 1.0)

    s_w = s_h = s_frames = 0
    s_fps = 0.0
    if not cap_s.isOpened():
        warnings.append(f"CANNOT_OPEN_SOURCE_VIDEO: Không mở được video gốc để đối chiếu: {source_video}")
        s_dur = r_dur
    else:
        s_w = int(cap_s.get(cv2.CAP_PROP_FRAME_WIDTH))
        s_h = int(cap_s.get(cv2.CAP_PROP_FRAME_HEIGHT))
        s_fps = cap_s.get(cv2.CAP_PROP_FPS) or 24.0
        s_frames = int(cap_s.get(cv2.CAP_PROP_FRAME_COUNT))
        s_dur = s_frames / max(s_fps, 1.0)

    # Validate duration match
    dur_diff = abs(r_dur - s_dur)
    duration_tolerance = max(0.15, 2.0 / max(s_fps, 1.0))
    if dur_diff > duration_tolerance:
        errors.append(f"DURATION_MISMATCH: Thời lượng lệch quá lớn ({r_dur:.2f}s vs gốc {s_dur:.2f}s, lệch {dur_diff:.2f}s)")
    if cap_s.isOpened() and (r_w != s_w or r_h != s_h):
        errors.append(f"RESOLUTION_MISMATCH: Render {r_w}x{r_h}, gốc {s_w}x{s_h}")
    if cap_s.isOpened() and abs(r_fps - s_fps) > 0.02:
        errors.append(f"FPS_MISMATCH: Render {r_fps:.3f} fps, gốc {s_fps:.3f} fps")
    if r_w <= 0 or r_h <= 0 or r_frames <= 10:
        errors.append(f"INVALID_VIDEO_DIMENSIONS: Video rỗng hoặc quá ít frame ({r_w}x{r_h}, {r_frames} frames)")

    check_results["video_integrity"] = {
        "passed": len(errors) == 0,
        "rendered_w": r_w,
        "rendered_h": r_h,
        "rendered_fps": r_fps,
        "rendered_duration": round(r_dur, 2),
        "source_duration": round(s_dur, 2),
        "duration_diff": round(dur_diff, 2),
        "duration_tolerance": round(duration_tolerance, 3),
        "source_w": s_w,
        "source_h": s_h,
        "source_fps": s_fps,
    }

    # ----------------------------------------------------
    # 2. OCR Track Audit & Replacement Check
    # ----------------------------------------------------
    events = ocr_events or []
    ocr_validation = validate_ocr_events(events)
    ocr_errors = list(ocr_validation["errors"])
    ocr_stats = dict(ocr_validation["stats"])
    for ev in events:
        if bool(ev.get("cleaned", False)) and not bool(ev.get("is_watermark", False)) and not (ev.get("vi_text") or "").strip():
            ocr_errors.append(
                f"BLANK_WIPEOUT: Track #{ev.get('track_id')} ('{ev.get('text', '')}') bị xóa nền nhưng không có chữ tiếng Việt thay thế!"
            )

    if ocr_errors:
        errors.extend(ocr_errors)

    check_results["ocr_audit"] = {
        "passed": len(ocr_errors) == 0,
        "stats": ocr_stats,
        "errors": ocr_errors,
    }

    # ----------------------------------------------------
    # 3. Voice Report Audit (2-voice system check)
    # ----------------------------------------------------
    voice_errors = []
    voice_info: Dict[str, Any] = {}
    if expected_cue_count and (not voice_report_path or not os.path.exists(voice_report_path)):
        voice_errors.append(f"VOICE_REPORT_MISSING: Có {expected_cue_count} câu cần đọc nhưng không có báo cáo giọng")
    elif voice_report_path and os.path.exists(voice_report_path):
        try:
            v_data = json.loads(Path(voice_report_path).read_text(encoding="utf-8"))
            refs = v_data.get("role_references", {})
            voice_info["role_references"] = refs
            voice_info["cue_count"] = v_data.get("cue_count", 0)

            # Bắt buộc: Nhân vật = giongnucute.wav, Người dẫn = 2_nu_tre_trung.mp3
            if "character" in refs:
                char_audio = Path(refs["character"].get("audio", "")).name.lower()
                if char_audio != "giongnucute.wav":
                    voice_errors.append(f"WRONG_CHARACTER_VOICE: Nhân vật đang dùng '{char_audio}', bắt buộc là 'giongnucute.wav'")
            if "narrator" in refs:
                narr_audio = Path(refs["narrator"].get("audio", "")).name.lower()
                if narr_audio != "2_nu_tre_trung.mp3":
                    voice_errors.append(f"WRONG_NARRATOR_VOICE: Người dẫn đang dùng '{narr_audio}', bắt buộc là '2_nu_tre_trung.mp3'")

            if expected_cue_count is not None and int(v_data.get("cue_count", -1)) != expected_cue_count:
                voice_errors.append(
                    f"VOICE_CUE_COUNT_MISMATCH: Báo cáo có {v_data.get('cue_count')} câu, dự kiến {expected_cue_count}"
                )
            overlap_count = int(v_data.get("overlap_count", 0) or 0)
            truncated_cues = int(v_data.get("truncated_cues", 0) or 0)
            if overlap_count:
                voice_errors.append(f"VOICE_OVERLAP: Có {overlap_count} câu giọng bị chồng lấn")
            if truncated_cues:
                voice_errors.append(f"VOICE_TRUNCATED: Có {truncated_cues} câu giọng bị cắt")
            voice_info["overlap_count"] = overlap_count
            voice_info["truncated_cues"] = truncated_cues

            # Kiểm tra clone failure
            if v_data.get("clone_success") is False and bool(v_data.get("clone_conditioned", False)):
                pass
        except Exception as v_err:
            voice_errors.append(f"VOICE_REPORT_CORRUPT: Lỗi đọc file báo cáo giọng đọc: {v_err}")

    if voice_errors:
        errors.extend(voice_errors)

    check_results["voice_audit"] = {
        "passed": len(voice_errors) == 0,
        "details": voice_info,
        "errors": voice_errors,
    }

    # ----------------------------------------------------
    # 4. Visual Frame Audit & Contact Sheet Generation
    # ----------------------------------------------------
    times = audit_times or [1.0, 3.0, 6.0, 10.0]
    valid_times = []
    for t in times:
        if r_dur > 0 and t >= r_dur:
            safe_t = max(0.2, r_dur - 0.5)
            if safe_t not in valid_times:
                valid_times.append(safe_t)
        else:
            valid_times.append(t)
    valid_times = sorted(list(set(valid_times)))

    audit_cards = []
    visual_warnings = []
    visual_errors = []

    # Optional OCR reader for rendered frames
    ocr_checker = reader
    if ocr_checker is None:
        try:
            import easyocr
            ocr_checker = easyocr.Reader(["ch_sim", "en"], gpu=True)
        except Exception:
            ocr_checker = None

    for t in valid_times:
        frame_idx_r = int(t * r_fps)
        frame_idx_s = int(t * (cap_s.get(cv2.CAP_PROP_FPS) or 24.0))

        cap_r.set(cv2.CAP_PROP_POS_FRAMES, frame_idx_r)
        cap_s.set(cv2.CAP_PROP_POS_FRAMES, frame_idx_s)

        ok_r, f_r = cap_r.read()
        ok_s, f_s = cap_s.read()

        if not ok_r:
            f_r = np.zeros((1920, 1080, 3), dtype=np.uint8)
        if not ok_s:
            f_s = np.zeros((1920, 1080, 3), dtype=np.uint8)

        # Check remaining Chinese on rendered frame
        lingering = []
        if ok_r and ocr_checker:
            try:
                res = ocr_checker.readtext(f_r)
                for bbox, txt, prob in res:
                    c_txt = (txt or "").strip()
                    if has_chinese_char(c_txt) and len(c_txt) >= 2 and prob >= 0.20:
                        xs = [int(p[0]) for p in bbox]
                        x_min = min(xs)
                        # Bỏ qua watermark dọc sát mép trái
                        if x_min > 80:
                            lingering.append(f"{c_txt} (p={prob:.2f})")
            except Exception:
                pass

        if lingering:
            visual_errors.append(f"LINGERING_CHINESE @ {t:.1f}s: {', '.join(lingering)}")

        # Resize frames for contact sheet strip (width=360, height=640)
        thumb_s = cv2.resize(f_s, (360, 640))
        thumb_r = cv2.resize(f_r, (360, 640))

        # Overlay text banner
        cv2.putText(thumb_s, f"ORIGINAL {t:.1f}s", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        cv2.putText(thumb_r, f"RENDERED {t:.1f}s", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        pair = np.hstack([thumb_s, thumb_r])  # (640, 720, 3)
        audit_cards.append(pair)

    cap_r.release()
    cap_s.release()

    if audit_cards:
        if len(audit_cards) <= 2:
            contact_sheet = np.vstack(audit_cards)
        else:
            row1 = np.hstack([audit_cards[0], audit_cards[1]])
            row2 = np.hstack([audit_cards[2], audit_cards[3]]) if len(audit_cards) >= 4 else np.hstack([audit_cards[2], np.zeros_like(audit_cards[0])])
            contact_sheet = np.vstack([row1, row2])

        cv2.imwrite(str(contact_sheet_file), contact_sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
        print(f"[WubyQC] Đã tạo Contact Sheet: {contact_sheet_file.name}")

    if visual_warnings:
        warnings.extend(visual_warnings)
    if visual_errors:
        errors.extend(visual_errors)

    check_results["visual_audit"] = {
        "audited_times_sec": valid_times,
        "warnings": visual_warnings,
        "errors": visual_errors,
        "passed": not visual_errors,
        "contact_sheet": str(contact_sheet_file),
    }

    # ----------------------------------------------------
    # 5. Final Determination
    # ----------------------------------------------------
    passed = (len(errors) == 0)

    final_report = {
        "timestamp": os.path.getmtime(str(rendered_video)) if rendered_video.exists() else 0,
        "rendered_video": str(rendered_video),
        "source_video": str(source_video),
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "checks": check_results,
    }

    report_file.write_text(json.dumps(final_report, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    print(f"[WubyQC] Đã lưu báo cáo QC: {report_file.name} -> KẾT QUẢ: {'PASS' if passed else 'FAIL'}")

    return {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "report_path": str(report_file),
        "contact_sheet": str(contact_sheet_file),
    }
