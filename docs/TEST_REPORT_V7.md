# Wuby V7 - test and handoff report

Date: 2026-09-20. Source archive: voice_source_handoff_20260919_2320.zip.
This is the Wuby cartoon dubbing backend, NOT the ReviewSach project.

## Delivered implementation

Native local HTML Canvas2D Studio, three pastel themes, movable safe zones, local
PNG logo/fade/drift, measured Vietnamese captions, modest zoom, actual FFmpeg
preview and MP4 output. No paid Canva SDK, no Revideo/Remotion/npm renderer.
SQLite persistent 100-item queue, single worker with per-job subprocess, dedupe,
snapshots, retries, cancel, restart recovery and reports. SFX/laughter accepts
licensed local audio events, disabled by default and can avoid spoken intervals.

The supplied backend entrypoints are patched, including video_merger's Wuby route;
the handoff did not include the real Telegram bot/main. A standalone Studio and
worker were added; local integration into a different bot caller remains to verify.

## Defects corrected

1. Unknown profile/engine or empty/failing clone could lead to default voice/silence.
   Wuby now requires its chosen reference-conditioned backend; failures stop.
2. Router could drop generation parameters, double-apply speed, or use nested
   asyncio.run. Parameters propagate; event-loop bridge tested.
3. Cache/prompt identity did not fully follow reference content and parameters.
   Cache binds reference bytes, transcript, profile, backend settings and WAV hash.
4. Speech could extend into the next cue, change pitch or be truncated to fit.
   One speech bus, reserved gap, bounded atempo; too-long utterance requires review.
5. Source talking could remain behind new speech; amix normalization could lower it.
   Clone mode mutes original speech, uses a separate instrumental/music input, and
   corrected mixing/ducking. Synthetic distinct frequencies tested this logic.
6. Repeated captions could be mapped to multiple OCR boxes. Wuby V7 uses one
   subtitle region and measured, non-overlapping pages. Intentional repeated words
   in dialogue are not removed merely because they repeat.
7. Existing OCR discarded short text near the bottom. That filter was removed.
   This is not proof of perfect removal on every moving/complex background.
8. Translation could return original Chinese/filler after API failure or corrupt
   structure. Strict ID/count/order/number checks and explicit review/failure now
   replace silent fallback; no claim of fully verified translation semantics.
9. Old diagnostic reported a fallback ready without checking it; it now reports
   prerequisites and NOT_RUN clone status. An old F0 threshold test is retired.
10. During the real queue run a short final subtitle page failed the guard; the
    paginator was corrected to reserve minimum time for every page. Regression
    added; same job rendered successfully after the fix.
11. Dragged titles now render at the configured region's center, not canvas center.

## Actual test results

- pytest -q -ra: **131 passed, 1 skipped** (13.82 seconds on this Linux/CPU runner).
- The skip is the historical local-reference prerequisite test: the WAV is not
  included. It is NOT a passing clone test.
- AST parse: 66 Python files. Native app.js checked with node --check.
- Real FFmpeg tests cover compositing, captions, logo, FPS, decode, speech/music/SFX
  routing, original-speech mute, safe rerender and the patched legacy entrypoint.
- Strict TTS behavior tests inject synthetic waveforms/failing backends. They do
  NOT execute a real clone model. Translation and speech-ASR tests use fake APIs.
- SQLite FIFO/restart/dedupe/capacity tested with 100 jobs and an injected light
  handler. This is NOT 100 downloaded/transcribed/dubbed production videos.
- Separately, one REAL queued subprocess completed a real FFmpeg 20-second MP4.
- Local HTTP routes exercised through actual HTTP requests, including token/host/
  path/range handling. Chromium executes actual HTML/CSS/JS/Canvas offline with
  stub fetch because the environment blocks browser localhost HTTP. No claim of
  complete browser-to-server E2E or Windows GUI verification.

## Drive videos measured and sampled

| File | Resolution | FPS | Video duration |
|---|---|---|---|
| anh_cu_ban_di_mac_ke_em_wuby.mp4 | 1080x1920 | 24/1 | 8.541016 s |
| van_may_cu_the_xoay_quanh_em.mp4 | 1080x1920 | 24/1 | 20.000000 s |
| hai_nhan_cach_vat_lon_vi_cong_viec.mp4 | 1080x1920 | 24/1 | 22.166016 s |

Only these THREE downloaded samples were inspected, not every file in the folder.
The Van May source shows tiny Vietnamese text overlapping the headline plus
remaining Chinese lower captions; Hai Nhan Cach repeats one line in several
positions. These are source observations from sampled frames, not exhaustive OCR.
Measurements and hashes are in input_video_measurements.json.

FPS recommendation for THESE sources: preserve 24 FPS, CFR output. Do not force
60 FPS to hide layout or timing defects. Other clips retain their measured rational
source rate by default; choosing a different FPS is explicit, not frame interpolation.

## Real demo output

WUBY_V7_DEMO_1080x1920_24FPS.mp4, 20.000 s, 1080x1920, 24/1 FPS, libx264/AAC.
14 caption pages; programmatic layout collisions=0 and caption time overlaps=0.
Selected actual output frames visually inspected; full file decoded successfully.
CPU render time recorded: 12.32 s for THIS clip/runner, excluding TTS/ASR/network.
This is not a speed promise for the user's GPU/Windows or longer videos.

IMPORTANT: audio_mode=preserve, clone_conditioned=false,
speaker_identity_verified=false, speech_qc=not_run.
The demo retains the user's existing audio (AAC re-encode), not a new clone.
Input SRT was kept as supplied; awkward/incorrect later lines were not silently
rewritten without a verified original-language transcript. This demo proves the
new visual renderer, not semantic translation accuracy or new voice identity.

Because this Drive input was ALREADY burned-in, a manually chosen source crop
[0, 520/1920, 1, 860/1920] removed the top/lower bands for this demo. It changes the
framing and is not an automatic inpainting success claim. Use original clean source
for normal processing. Residual source text remains unverified in the report;
keep human visual review for new content and fast moving captions.

## Real clone attempt and prerequisites

Ran: python -m wuby_studio.cli test-voice --channel wuby
Result: exit 2, REFERENCE_AUDIO_MISSING: wuby_character_tuned.wav.
No new reference-conditioned sample was produced. The handoff contains no actual
voice recording/model weights; this runner has CPU Torch and no CUDA GPU.
No provider keys were used for real paid API requests. EasyOCR/faster-whisper
models, live download adapters and Windows model environment are untested here.

F0 > 300 Hz does NOT prove a correct voice. WAV creation, reference existence or
ASR word match do NOT prove speaker identity either. A local model audition and
user listening comparison are mandatory before batch clone jobs. Per-job spoken
text QC then checks repetition/omission risk but can itself make ASR errors.
All finished outputs enter REVIEW; no automatic publishing is included.

## Installation evidence

See installer_actual.json for real dry-run/apply/second-apply/rollback against a
copy of the actual supplied handoff. Config merging preserves model/reference/
transcript/keys and other channels while enforcing Wuby no-fallback safety.
Separate unit tests cover local drift, tampered bundle, nested target and later
edits during rollback. No user's remote project was modified.

## Evidence / exclusions

final_render_report.json, final_probe.json, tests_full.log, syntax.json,
actual_clone_attempt.log, doctor.log, input_video_measurements.json,
installer_actual.json. Comparison images and demo MP4 are included under preview/.
The Studio screenshot is offline UI rendering with the actual source frame; it is
not a claim of browser HTTP E2E. No fonts, API keys, venv, caches, database, model
weights or voice sample files are included. Do not publish private backups.

No automatic Drive watching, background follow-up, upload or source-folder changes
were performed. Re-run the supplied local tools on new jobs to obtain new reports.
