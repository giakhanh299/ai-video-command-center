# Wuby Preflight Patch Report

## Muc tieu
Cau hinh Wuby phai phan tich video truoc khi TTS/render, thay vi dua tren mot preset co dinh.

## Luong moi
Whisper -> Wuby Preflight -> Render Plan -> TTS theo F0 -> OCR cleanup/sub overlay -> final render.

Preflight do:
- source width/height/FPS/aspect/orientation;
- brightness/contrast/sharpness;
- motion va letterbox;
- scene boundaries;
- OCR tracks + moving/static text + subtitle coverage;
- F0 tung Whisper segment va voice-bank match;
- QC warnings truoc render.

## Quyet dinh tu dong
- OCR cadence tang theo motion (toi da 24 fps).
- Reuse dung OCR tracks cua preflight trong renderer, khong scan lai.
- Text moving giu follow-motion.
- F0 voice assignment co hysteresis va island smoothing de tranh doi giong do mot cau len/xuong tong.
- Portrait/square co the dung Wuby hybrid frame; landscape tu tat hybrid frame va giu khung goc.
- Neu preflight loi, production fail-soft ve Wuby pipeline cu.

## Artifacts
Moi job Wuby tao `*_wuby_preflight.json` trong workspace, gom visual analysis, scene ranges, OCR events, voice match, QC va render plan.

## Test
- Wuby/preflight/voice/hybrid/render targeted: 40 passed + 5 subtests.
- Broad suite excluding one unrelated legacy translation-fallback assertion: 167 passed + 5 subtests; one unrelated environment failure remains because `openai` is not installed for `backend/tests/test_wuby_roles.py`.
- The excluded legacy translation test expects hard failure, while current project intentionally performs a fallback translation. This behavior predates the Wuby preflight patch.
