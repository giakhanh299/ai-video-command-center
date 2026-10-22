import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

import time
from pathlib import Path
import soundfile as sf
import numpy as np

print("Loading Vieneu v3turbo...")
from vieneu import Vieneu

tts = Vieneu(mode="v3turbo")
print(f"Backend: {tts.backend}, Sample rate: {tts.sample_rate}")

ref_path = Path("wuby_package/sample_data/character_tuned.ref.wav")
text = "Gửi cho người không để ý đến bạn xem. Em bận thì cứ bận đi."

print(f"Inferring with ref: {ref_path}...")
t0 = time.time()
# denoise=False speeds up reference enrollment significantly
wav = tts.infer(text=text, ref_audio=str(ref_path), denoise=False)
t1 = time.time()
print(f"Infer finished in {t1 - t0:.2f}s! Wav shape: {wav.shape}")

out_p = Path("tests/giai_phap_3_vieneu_v3_turbo.wav")
sf.write(str(out_p), wav, tts.sample_rate, subtype="PCM_16")
print(f"Saved: {out_p}")
