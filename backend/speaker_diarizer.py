import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import torch
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / "backend" / ".env")

_PIPELINE = None


def get_diarization_pipeline(token: Optional[str] = None, device: Optional[str] = None) -> Any:
    """Khởi tạo và cache pipeline pyannote/speaker-diarization-3.1 chuẩn Hugging Face.
    
    Yêu cầu quyền truy cập trên Hugging Face:
    1. https://huggingface.co/pyannote/speaker-diarization-3.1
    2. https://huggingface.co/pyannote/segmentation-3.0
    """
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE

    hf_token = token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if not hf_token:
        raise ValueError(
            "Chưa có Hugging Face Token! Vui lòng thiết lập HF_TOKEN trong backend/.env\n"
            "Lưu ý: Cần chấp nhận điều khoản tại:\n"
            "  1. https://huggingface.co/pyannote/speaker-diarization-3.1\n"
            "  2. https://huggingface.co/pyannote/segmentation-3.0"
        )

    from pyannote.audio import Pipeline

    print("[SpeakerDiarizer] Đang tải mô hình pyannote/speaker-diarization-3.1 từ HuggingFace...")
    # Mã nguồn chuẩn từ Hugging Face:
    try:
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=hf_token)
    except TypeError:
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=hf_token)

    if pipeline is None:
        raise RuntimeError(
            "Không thể tải pipeline pyannote/speaker-diarization-3.1. "
            "Vui lòng kiểm tra quyền truy cập (gated model) và token trên HuggingFace."
        )

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    pipeline.to(torch.device(device))
    print(f"[SpeakerDiarizer] Pipeline đã sẵn sàng trên thiết bị: {device.upper()}")
    _PIPELINE = pipeline
    return _PIPELINE


def diarize_audio(
    audio_path: str,
    token: Optional[str] = None,
    num_speakers: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Phân tách người nói trong file âm thanh theo chuẩn mã nguồn Hugging Face.
    
    Tài liệu chính thức: https://huggingface.co/pyannote/speaker-diarization-3.1
    
    Returns:
        List[dict]: Danh sách các đoạn thoại [{'start': float, 'end': float, 'speaker': str}, ...]
    """
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file âm thanh: {audio_path}")

    pipeline = get_diarization_pipeline(token=token)

    # Cấu hình số lượng speaker nếu được chỉ định (theo chuẩn Hugging Face)
    params: Dict[str, Any] = {}
    if num_speakers is not None:
        params["num_speakers"] = int(num_speakers)
    if min_speakers is not None:
        params["min_speakers"] = int(min_speakers)
    if max_speakers is not None:
        params["max_speakers"] = int(max_speakers)

    print(f"[SpeakerDiarizer] Đang phân đoạn người nói cho: {audio_file.name}...")

    # Gọi trực tiếp bằng đường dẫn file âm thanh theo chuẩn gốc Hugging Face: diarization = pipeline("audio.wav")
    try:
        diarization = pipeline(str(audio_file), **params)
    except Exception as e:
        # Fallback đọc waveform vào bộ nhớ nếu hệ thống Windows thiếu audio backend
        print(f"[SpeakerDiarizer] Fallback sang bộ nhớ (do backend audio báo lỗi: {e})")
        import soundfile as sf
        import torchaudio

        data, sample_rate = sf.read(str(audio_file), dtype="float32")
        if data.ndim == 1:
            waveform = torch.from_numpy(data).unsqueeze(0)
        else:
            mono = data.mean(axis=1)
            waveform = torch.from_numpy(mono).unsqueeze(0)

        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
            waveform = resampler(waveform)
            sample_rate = 16000

        audio_dict = {"waveform": waveform, "sample_rate": sample_rate}
        diarization = pipeline(audio_dict, **params)

    results = []
    annotation = getattr(diarization, "speaker_diarization", diarization)
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        results.append({
            "start": round(float(turn.start), 3),
            "end": round(float(turn.end), 3),
            "speaker": str(speaker),
        })

    print(f"[SpeakerDiarizer] Hoàn tất: phát hiện {len(results)} đoạn nói của {len(set(r['speaker'] for r in results))} người nói.")
    return results


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        segments = diarize_audio(test_file)
        for s in segments[:10]:
            print(f"[{s['start']:.2f}s -> {s['end']:.2f}s] {s['speaker']}")
    else:
        print("Sử dụng: python backend/speaker_diarizer.py <path_to_audio.wav>")

