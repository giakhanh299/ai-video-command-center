import glob
from pathlib import Path

def patch_moss():
    patterns = [
        r"D:/0.1_FACE_BOOK/DUNG_CHUNG/MODELS/HF_CACHE\modules\transformers_modules\**\configuration_moss_audio_tokenizer.py",
        str(Path.home() / ".cache" / "huggingface" / "modules" / "**" / "configuration_moss_audio_tokenizer.py")
    ]
    for pattern in patterns:
        for file in glob.glob(pattern, recursive=True):
            p = Path(file)
            s = p.read_text(encoding="utf-8")
            if "sampling_rate: int\n" in s:
                s = (s.replace("sampling_rate: int\n", "sampling_rate: int = 48000\n")
                      .replace("downsample_rate: int\n", "downsample_rate: int = 3840\n")
                      .replace("causal_transformer_context_duration: float\n", "causal_transformer_context_duration: float = 10.0\n")
                      .replace("encoder_kwargs: list[dict[str, Any]]\n", "encoder_kwargs: Any = None\n")
                      .replace("decoder_kwargs: list[dict[str, Any]]\n", "decoder_kwargs: Any = None\n")
                      .replace("number_channels: int\n", "number_channels: int = 2\n")
                      .replace("enable_channel_interleave: bool\n", "enable_channel_interleave: bool = True\n")
                      .replace("attention_implementation: str\n", "attention_implementation: str = 'sdpa'\n")
                      .replace("compute_dtype: str\n", "compute_dtype: str = 'fp32'\n")
                      .replace("quantizer_type: str\n", "quantizer_type: str = 'rlfq'\n")
                      .replace("quantizer_kwargs: dict[str, Any]\n", "quantizer_kwargs: Any = None\n"))
                p.write_text(s, encoding="utf-8")
                print(f"✅ Successfully patched {p}")

if __name__ == "__main__":
    patch_moss()
