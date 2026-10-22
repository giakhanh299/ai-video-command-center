# Movie Clone Patch — Test Report

Date: 2026-09-27

## Implemented

- Telegram bot now exposes only two main processing choices: Wuby and Clone phim.
- Removed numbered preset `cauhinh3` and `cauhinh4` from active configuration.
- Replaced old `cauhinh2` with `movie_clone`.
- Preserved the subtitle-position detection strategy from old Cấu hình 4 through `scan_fixed_blur_box()` + fallback detector.
- Added per-Whisper-segment F0 measurement and bundled voice ranking.
- Added multi-voice TTS timeline rendering.
- Added pre-render diagnostic CLI/BAT.

## Voice-bank measurements from bundled samples

- omni_dan_chuong_trinh_vip: 93.02 Hz
- omni_laivansam: 119.40 Hz
- omni_nam_review: 126.98 Hz
- omni_tauthao: 128.00 Hz
- omni_chautinhtri: 148.15 Hz
- omni_nu_tram: 231.88 Hz
- omni_nu_ngoc_trinh: 235.29 Hz
- omni_nu_cute: 238.81 Hz
- omni_nu_tre: 251.98 Hz
- omni_betterversion: 258.06 Hz

## Included-audio matching tests

1. `tests/cue1_trimmed.wav`
   - measured source median F0: 235.29 Hz
   - selected: `omni_nu_ngoc_trinh`
   - bundled reference: 235.29 Hz
   - distance: 0 cents

2. `tests/c2_wuby_raw.wav`
   - measured source median F0: 238.81 Hz
   - selected: `omni_nu_cute`
   - bundled reference: 238.81 Hz
   - distance: 0 cents

## Automated tests

`23 passed` across:

- channel/profile resolution
- subtitle-region geometry
- new movie voice matcher
- film-bar helpers

Python compile checks also passed for modified backend modules and test CLI.

## Whisper runtime note for this sandbox

The project already declares `faster-whisper` in `requirements.txt`, and the active movie pipeline calls the existing `WhisperTranscriber`. The current sandbox does not have `faster-whisper` installed and outbound package/model download is blocked, so an actual Whisper model transcription could not be executed here. Use `TEST_CLONE_PHIM_GIONG.bat <video>` on the project machine to run the real Whisper → F0 → voice ranking test before rendering.
