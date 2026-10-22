# Wuby Preflight - phan tich truoc khi render

Cau hinh Wuby khong render ngay sau Whisper nua. Thu tu moi:

1. Whisper tach moc thoai.
2. Preflight do video goc: resolution, FPS, aspect ratio, do sang, contrast, do net, motion va letterbox.
3. Tach scene de OCR/text track khong bi keo qua cut.
4. OCR chu Trung theo mat do tu dong dua tren motion; track chu co keyframe va phat hien MOVE/STATIC.
5. Khop OCR track voi cue thoai; QC do ty le phu subtitle va mask bat thuong.
6. Do F0 tung doan Whisper, so voi voice bank that trong `voice_samples/`, dung hysteresis + island smoothing de tranh doi giong do ngu dieu ngan.
7. Tao `*_wuby_preflight.json` va render plan.
8. TTS theo voice assignment cua preflight.
9. Renderer tai su dung chinh OCR events da phan tich, khong quet lai.
10. Xoa chu goc, chen chu Viet theo chuyen dong, ghep voice va render.
11. Hybrid frame chi duoc phep voi portrait/square; landscape giu khung goc de tranh crop sai.

## Thu nhanh khong render

Keo video vao `TEST_WUBY_PREFLIGHT.bat`.

Bao cao JSON se nam canh video nguon voi duoi `.wuby_preflight.json` va cho biet:
- khung hinh/FPS/orientation;
- motion class va OCR fps da chon;
- so scene;
- so OCR track va coverage;
- F0 coverage va cac voice duoc chon;
- QC warning;
- co duoc ap dung hybrid frame hay khong.

Production Telegram/Drive se tu dong chay preflight. Neu preflight loi do model/OCR/moi truong, Wuby fail-soft ve pipeline cu thay vi lam chet job.
