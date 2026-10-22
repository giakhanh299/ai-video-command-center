# Local prerequisites - do not reinstall CUDA blindly

Run every command using the existing interpreter selected by tools/python_env.bat.
Python 3.10+ is required by this patch. The original voice model may impose a
narrower supported Python/Torch/Transformers matrix; keep that existing matrix.

## Required for visual rendering

FFmpeg and ffprobe binaries on PATH, or FFMPEG_BINARY / FFPROBE_BINARY absolute paths.
Check `ffmpeg -filters` includes subtitles/libass, atempo, overlay, fps, sidechaincompress.
Pillow/numpy/scipy/soundfile/filelock and other missing basic packages can be
installed with tools/install_dependencies.py --apply after inspecting the plan.
Be Vietnam Pro is downloaded only by the opt-in font installer on your machine;
otherwise set font_path to a licensed local font that covers Vietnamese.

## Clone model - preserve the user's existing working installation

No model weights, torch build, reference recordings or model license are bundled.
backend/channels_config.json -> voice_profiles.wuby_clone owns the reference,
model and generation settings. Confirm the selected backend's actual signature.
A configured model name is not proof its local installation can generate speech.
Place the reference at its configured absolute path, project-relative path or
voice_samples/ path as resolved by the router; run doctor to see the resolved file.
The supplied Chinese ref_text is historical input, NOT an independently verified
transcript. Listen to the actual sample and correct it before voice testing.

    python -m wuby_studio.cli doctor
    python -m wuby_studio.cli test-voice --channel wuby

Missing reference MUST fail. Compare the new audition with the reference before
calling approve-voice. The approval fingerprints the reference/settings/sample;
it is a user's listening acknowledgement, not biometric proof for every output.

## Local speech check / source ASR

V7 speech_qc defaults to enabled, faster-whisper `small`, CPU, int8, and cached
weights only. This avoids consuming extra GPU memory alongside the voice model.
With Anti, inspect the installed environment before installing a missing package:

    python -m pip install --dry-run faster-whisper
    python -m pip install faster-whisper
    python tools/prepare_optional_models.py --asr small

The last command explicitly downloads the selected ASR weights. Source ASR in the
legacy module may use its own Whisper setting; inspect that local config too.
ASR can confuse Vietnamese words, music/lyrics or high-pitched speech. A mismatch
blocks publishing/requires listening, but never replaces the approved script.

## OCR cleanup

Use an existing compatible EasyOCR installation where possible. Inspect a dry-run
first: EasyOCR depends on Torch and must not replace your working CUDA build.

    python -m pip install --dry-run easyocr
    python tools/prepare_optional_models.py --ocr

Only run the preparation command after EasyOCR is installed compatibly. It fetches
Chinese simplified / English models. Dense 24-FPS OCR can be expensive; test short
clips before a 100-link batch. Lower sampling can miss fast moving text. Cropping
and manual masks are explicit alternatives, not evidence that OCR erased all text.

## Public video downloads

Install missing `yt-dlp[default]` and gdown via the lightweight installer. Existing
packages are not auto-upgraded; inspect them if a platform download fails. Current
yt-dlp YouTube support also uses EJS plus a JavaScript runtime. Its official guide
specifies Node 22+ or Deno 2.3+; the downloader enables an installed node/deno.
Node is NOT required for the HTML Canvas/FFmpeg renderer itself.
Official guide: https://github.com/yt-dlp/yt-dlp/wiki/EJS

Drive download in the standalone app uses public file access with gdown, not your
ChatGPT Drive connection. Upload private videos from your machine if unavailable.
Do not feed a folder URL as one queue item. No login tokens are exported from chat.

## API translation

The existing translator uses its configured OpenAI-compatible API/environment.
No live credentials were used or tested here. JSON/order/count/number validation
is enforced, but correctness still needs source-aware review. Fees/quotas of this
existing API are not eliminated by the free local renderer.

## Browser test distinction

HTTP routes were exercised with real Python HTTP requests. Chromium executed real
HTML/CSS/Canvas/JS OFFLINE with stub fetch because this runner's policy blocks
browser requests to localhost. This is not full browser-to-server E2E on Windows.
The browser test skips when optional Playwright/Chromium is not installed.
