# Free/local components and upstream sources

New native Canvas2D UI uses browser APIs, no proprietary Canva SDK or subscription.
New patch source authored for this handoff is provided under MIT; existing user
project source and bundled upstream source retain their original terms.
No third-party binaries, fonts, model weights or sound libraries are distributed
in this ZIP. Installing components may download their own license notices.

- SQLite: public domain, https://www.sqlite.org/copyright.html
- FFmpeg: build-dependent LGPL/GPL, https://ffmpeg.org/legal.html
  Filter reference: https://ffmpeg.org/ffmpeg-filters.html
- Pillow: HPND, https://pillow.readthedocs.io/en/stable/about.html
- yt-dlp: Unlicense / release dependencies have their own terms,
  https://github.com/yt-dlp/yt-dlp
- gdown: MIT, https://github.com/wkentaro/gdown
- faster-whisper: MIT, https://github.com/SYSTRAN/faster-whisper
- EasyOCR: Apache-2.0, https://github.com/JaidedAI/EasyOCR
- Be Vietnam Pro: SIL OFL, downloaded on request on the user's machine,
  https://github.com/google/fonts/tree/main/ofl/bevietnampro
- Canvas API: https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API
- Existing OmniVoice / Khanh model integrations: keep the exact upstream code and
  weights licenses; installing free rendering tools does not license voice/content.

No audio laughter sample, protected logo or stock material is added by default.
Use your own/appropriately licensed assets and authorized voice reference.

## Optional Character ID stack (not bundled)

- WeSpeaker: Apache-2.0, https://github.com/wenet-e2e/wespeaker
- Light-ASD: see upstream repository/license, https://github.com/Junhua-Liao/Light-ASD

The ZIP does not redistribute those repositories or their model weights. The optional
installer downloads them from their upstream sources on the user's machine.
