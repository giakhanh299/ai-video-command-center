# Module và timeline render — DRAFT 0.1.0

Ưu tiên hiện tại: chia module chức năng trong Lay video tiktok, không triển khai công thức chia clip mới.

## Đã xác minh trong dự án ưu tiên

- backend/scene_detector.py: end_frame=b-1 (inclusive), nhưng thời gian start <= t < end.
- wuby_studio/renderer.py: FPS qua Fraction, CFR output; kiểm tra duration/FPS/dimensions;
  chưa thấy kiểm tra liên tục từng frame chỉ từ những điều kiện này.
- wuby_studio/bridge.py: ép fps='12', khác README nói mặc định theo nguồn.
- sub_processor có split/merge/rebalance cue và duration matching TTS;
  không coi split subtitle là chia đoạn video độc lập.
- Visual rerender hiện bảo vệ audio config và source/voice hashes; cần bổ sung chính sách
  FPS/timebase cho hợp đồng rerender trước triển khai, không áp dụng quy tắc ReviewSach sang đây.

## Quy ước hợp đồng đề xuất

Timeline canonical dùng frame index nguyên, khoảng [start_frame,end_frame_exclusive),
FPS rational numerator/denominator; adapter đổi end inclusive legacy thành end+1 tại ranh giới.
Timestamp từ audio/subtitle giữ integer ticks + timebase rational khi cần;
không suy ra số frame VFR bằng duration nhân FPS trung bình.
Mọi chuyển CFR phải ghi rõ policy/output FPS và giữ mapping PTS nguồn.
Đây là đề xuất chưa đổi dữ liệu/hành vi legacy.

Nếu sau này thêm render đoạn, cần chốt: segment size, source PTS/CFR, audio priming/padding,
subtitle xuyên biên, overlap context khác overlap output, tail policy và phép ghép.
Chỉ cho resume đoạn khi chứng minh hash input/config và continuity; không chỉ FFmpeg exit=0.

## Những công thức tìm được ở dự án Motion, KHÔNG áp sang Wuby

worker_runtime/linux.py có 4n+1, snapWindows và SCAIL-2 overlap 5/window 81.
Probe độc lập hàm _scail2_chunks bằng AST, không import runtime/GPU:

| Input frames | Covered end exclusive | Uncovered tail ở hàm chia |
|---:|---:|---:|
| 5 | 0 | 5 |
| 9 | 9 | 0 |
| 81 | 81 | 0 |
| 82 | 81 | 1 |
| 85 | 85 | 0 |
| 297 | 297 | 0 |
| 300 | 297 | 3 |

Không kết luận MP4 cuối mất frame: caller có thể normalize/trim/pad trước/sau hàm.
Không gọi đây là công thức modulo người dùng đã chốt.

## Kiểm thử bắt buộc khi triển khai timeline

Video ngắn hơn một đoạn; chia hết; tail; 24/25/30 và 30000/1001 FPS; biên frame/cue;
VFR có PTS thật; audio dài/ngắn; subtitle xuyên biên; đoạn retry.
Kiểm tra union đúng toàn timeline, output không overlap/gap, frame marker liên tục và audio sync.
Overlap context trong model được loại đúng một lần; không cắt tail để làm test PASS.
Hiện chưa thực hiện các test render timeline này trong đợt tài liệu.
