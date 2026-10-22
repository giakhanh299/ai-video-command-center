# MULTI-BACKEND VOICE V4

Default priority:

1. `khanh_omnivoice` - model `kjanh/KhanhTTS-OmniVoice`; zero-shot clone from a short reference clip.
2. `vieneu` - VieNeu v3 Turbo; zero-shot clone and optional automatic denoise.
3. `zerotts` - lightweight final fallback, default preset `hamy`.

## Batch naming

For `movie01.mp4`, place these files beside it:

- `movie01.srt` - Vietnamese subtitle/timeline.
- `movie01.ref.wav` - clean 3-10 second voice sample to clone.
- `movie01.ref.txt` - optional transcript of the sample. OmniVoice can auto-transcribe if omitted.

Then run:

```bat
python run_batch.py input_videos output_videos --config config/channels/wibu_cute.json
```

## One voice render

```bat
python render_voice.py sample_data/subtitles_vi.srt output/test.wav --ref sample_data/voice_vi.wav
```

## Extract a reference from a source video

Choose a clean line where only the target character is speaking:

```bat
python extract_voice_ref.py input.mp4 12.5 6.0 input.ref.wav
```

The router does not blindly keep trying a broken CUDA backend. On import/runtime/OOM or technical audio QC failure, it releases the backend, clears CUDA cache, and continues to the next backend. A `_report.json` file records which backend was used.

## Install

Base pipeline:

```bat
pip install -r requirements.txt
```

Primary/secondary clone backends:

```bat
setup_voice_backends.bat
```

or:

```bat
pip install -r requirements_voice.txt
```

Use only reference voices you have permission to clone.
