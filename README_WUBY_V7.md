# WUBY V7 - Logo, Canvas, Queue 100, Safe Voice

BAN SUA DANH RIENG CHO WUBY, KHONG PHAI DU AN REVIEWSACH.
Input: voice_source_handoff_20260919_2320.zip. Nhanh nang cap: 20/09/2026.

## Doc truoc khi cai

Goi goc chi la backend handoff, KHONG kem bot/main dang chay, giuong mau WAV,
model weights hay moi truong CUDA. V7 them Studio va hang cho doc lap, dong thoi
noi vao backend.video_merger / sub_processor duoc cung cap. Khong khang dinh
Telegram local da duoc cap nhat: Anti phai kiem tra duong goi that.

Video demo la test HINH ANH, GIU AUDIO CO SAN. Khong phai demo clone moi.
Khong the bao dam danh tinh giong bang FPS, cao do F0 hay mot unit test.
Xem docs/TEST_REPORT_V7.md va HUONG_DAN_ANTI_WUBY_V7.txt.
Cac ISSUE_VI.md, measurements.json, runs.json, logic.json o root la lich su
handoff cu; KHONG dung chung lam ket luan test V7.

## Cai vao project cu

1. Dung bot, worker va render dang chay. Sao luu project.
2. Giai nen ban va vao thu muc RIENG ben ngoai project cu.
3. Chay CAP_NHAT_WUBY_V7.bat. Chon project ROOT co backend/, va Python cua
   dung venv dang dung. Xem dry-run; chi go APPLY khi khong co xung dot.
4. Trong project da cap nhat, chay CAI_WUBY_V7.bat. Bo cai chi cai package
   co ban CON THIEU, khong chu dong nang cap Torch/CUDA/model clone.
5. Lam theo docs/LOCAL_MODEL_SETUP.md de kiem tra model clone, EasyOCR,
   faster-whisper va tai weights bang lenh ro rang neu can.
6. Chay MO_WUBY_STUDIO.bat, thu mot video ngan truoc khi xep 100 link.

KHONG chep settings/channels_config mau de len file that.
Installer giu key, chat id, duong dan, ref_text va model rieng cua ban; chi bat
cac co an toan Wuby. Neu file local da khac handoff, installer DUNG de Anti merge.
Rollback: python apply_wuby_v7.py --target "D:\Project" --rollback "D:\Project\backups\wuby_v7_..."
Backup co the chua secrets cua ban: khong chia se backup.

## Mot lan duyet giong truoc hang cho

Trong terminal da kich hoat dung venv, tai project root:

    python -m wuby_studio.cli doctor
    python -m wuby_studio.cli test-voice --channel wuby

Doc duong dan audition.wav ma lenh in ra. Nghe so voi mau goc; kiem tra ref_text
KHOP NOI DUNG mau. Khi DA NGHE va dung giong:

    python -m wuby_studio.cli approve-voice --sample "DUONG_DAN\audition.wav" --listened

Doi model, file mau, ref_text hay tham so giong thi can test/duyet lai.
Mot audition duoc duyet KHONG bao dam moi cau sau nay deu hoan hao. Moi job co
speech QC doi chieu loi doc; ket qua van o trang thai REVIEW, khong tu dang.
Clone loi -> needs_attention/failed, khong doi ngam sang Hoai My.

## Studio va hang cho

MO_WUBY_STUDIO.bat mo http://127.0.0.1:8767 tren may ban.
Co 3 theme peach/mint/lavender, keo vung title/video/subtitle/logo, font size,
crop, opacity, zoom nhe; logo PNG rieng; xem Canvas + xuat MP4 preview that.
Canvas la ban xem truoc bo cuc, KHONG phai Canva Pro hay trinh edit tu do day du.
MP4 FFmpeg la ban kiem tra cuoi; browser va FFmpeg co the khac font metrics.

Dan 1 link/video, moi dong mot link, toi da 100 link dang cho/chay.
Ho tro public Google Drive file, YouTube, TikTok/Douyin qua adapter yt-dlp,
va upload local. Link folder Drive/playlist khong duoc coi la mot video.
Quyen truy cap, cookies/geo restrictions va extractor cua tung site van co the loi.
Khong vong key/proxy de vuot han muc. Khong su dung connector dang nhap ChatGPT
tren may ban: Drive rieng tu nen tai ve bang tai khoan cua ban roi upload local.

Chay CHAY_HANG_CHO.bat hoac nut worker tren Studio. Moi lan CHI 1 worker va
1 model/render job, KHONG chay 100 GPU job dong thoi. SQLite luu queue qua
khoi dong lai. Co pause, cancel, retry, log tung job, output/report.
Neu may bi tat khi dang render: dung tien trinh mo coi con sot truoc, roi:

    python -m wuby_studio.cli recover --processes-stopped
    python -m wuby_studio.cli retry JOB_ID

Khong resume mu audio dang viet do. Retry an toan va kiem tra cache/hash.
Mot SRT duyet san chi dung cho DUNG video do; khong gan mot SRT cho ca 100 link.

## Loi doc, chu va FPS

- 3 video Drive da khao sat: 1080x1920, 24/1 FPS. Mac dinh fps="source".
- Giu phan so nhu 30000/1001; xuat CFR. Khong tu bien 24 thanh 60 de gia muot.
- Tieu de, nhan vat, subtitle, logo co vung rieng; collision thi chan.
- Subtitle toi da 2 dong; wrap theo pixel; chia trang; khong nhan cung cau len
  moi o OCR. Lap co chu y "ha ha" trong noi dung van duoc giu.
- OCR xoa/che chu cu khong phai chung nhan xoa 100%; chu chay nhanh/nen phuc tap
  can manual mask/crop va duyet hinh. Video da render/burned-in khong nen lai
  them subtitle lan hai. Uu tien SOURCE GOC sach.
- Clone bus chi 1 cau tai 1 thoi diem; chua gap, atempo gioi han 1.20; cau qua
  dai -> review, khong cat chu va khong de len cau sau. Audio goc co tieng noi
  bi tat trong clone mode. Nen nhac phai la file instrumental rieng.
- speech_qc dung ASR local: do loi doc, khong xac minh ai dang noi. ASR cung co
  the sai. Dung nghe so sanh thay vi ep nguong de lay PASS.

## Logo / am thanh hai huoc

Dat logo vao channel_assets/wuby/logo.png hoac upload PNG qua Studio.
Logo nho, mo, drift/fade; khong muon thi tat. Khong lay logo kenh khac thay the.
SFX local/laughter co schema trong examples/sfx_later.json, tat mac dinh.
Chi them file ban co quyen dung, event start/gain; avoid_speech chan de tieng.
Chua co AI tu tao giong cuoi hoac tu chon punchline.

## Render lai khong tao giong lai

Moi output luu visual_packet.json + render_report.json + ASS + anh snapshot.

    python -m wuby_studio.cli rerender --packet "...\visual_packet.json" --config "theme.json" --output "new.mp4"

Doi hinh/logo/theme khong goi TTS/dich. Source/audio phai khop hash.

## Kiem thu / gioi han

    TEST_WUBY_V7.bat

131 passed, 1 skipped o moi truong Linux/CPU cua lan ban giao; test browser
co the skip neu may ban khong co Playwright/Chromium. Real FFmpeg da chay,
real clone/TTS/OCR/ASR/API chua chay do thieu reference/weights/network.
Goi khong kem fonts, model, node_modules, venv, key, workspace hay DB cua ban.
Khong tu upload, khong tu theo doi Drive lien tuc sau khi chat ket thuc.
