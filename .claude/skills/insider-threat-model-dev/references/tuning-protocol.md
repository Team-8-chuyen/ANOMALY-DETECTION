# Protocol tinh chỉnh tham số

Đã chốt: **Optuna (TPE) + early stopping, tối ưu trên tập validation không dùng nhãn; nhãn chỉ dùng ở lần đánh giá test cuối cùng.** Lý do: bài toán là anomaly detection không giám sát, dùng nhãn để tune là rò rỉ và khó bảo vệ trong paper.

## 1. Nguyên tắc

1. **Ba giai đoạn thời gian**: train (fit mô hình) → val (chọn tham số, early stop, chọn p theo ngân sách) → test (báo cáo, mở một lần).
2. **Tune từng tầng một, từ dưới lên**: Feature AE → Seq Transformer → C4 (α nếu D-06 cho phép) → C5 (W, k_P, k_G) → C6 (p, R). Tầng trên tune với tầng dưới đã cố định ở tham số tốt nhất.
3. **Mỗi tầng một mục tiêu không nhãn** (bảng §3). Không gộp các mục tiêu thành một số.
4. **Không nhìn nhãn val khi tune.** Có thể *báo cáo* chỉ số có nhãn trên val để kiểm tra hợp lý, nhưng không đưa vào hàm mục tiêu, và phải ghi rõ trong BA doc.
5. **Mở test là một sự kiện**: trước khi chạy đánh giá test cuối, hỏi người dùng xác nhận; ghi Decision Log "mở test lần N, cấu hình X". Sau khi mở test mà sửa thiết kế thì kết quả mới phải ghi rõ là lần mở thứ N+1.
6. **Tái lập**: sampler TPE có seed; lưu `study.db` (SQLite) của Optuna trong `runs/`; lưu best params ra YAML để cấu hình cuối chỉ đọc YAML.

## 2. Ngân sách và phần cứng

Máy hiện tại: RTX 3050 Laptop 4GB VRAM. Mặc định:

- AMP fp16 (`torch.autocast`) cho Transformer; batch giảm khi OOM, bù bằng gradient accumulation.
- `n_trials` 30–40 mỗi mô hình, `MedianPruner(n_warmup_steps=5)`, epoch tối đa trong trial nhỏ hơn lần train cuối (ví dụ 30 vs 200).
- Tune trên **mẫu con user** (ví dụ 30% user, chọn ngẫu nhiên có seed, ghi danh sách) nếu một trial > 10 phút; train cuối dùng đủ user.
- Trước khi chạy tune dài: ước lượng thời gian bằng 1–2 trial, báo người dùng và hỏi trước khi chạy hết (chạy nền).

## 3. Không gian tìm kiếm và mục tiêu

| Tầng | Tham số | Khoảng | Mục tiêu (minimize trên val) |
|---|---|---|---|
| Feature AE | latent | {8, 16, 32} | MSE tái tạo val |
| | số lớp ẩn | 1–3 | |
| | độ rộng | {64, 128, 256} | |
| | dropout | [0.0, 0.3] | |
| | lr | log [1e-4, 3e-3] | |
| | weight_decay | log [1e-6, 1e-3] | |
| | batch | {256, 512, 1024} | |
| Seq Transformer | d_model | {32, 64, 128} | NLL token bị mask trên val (seed mask cố định) |
| | layers | 1–4 | |
| | heads | {2, 4} (chia hết d_model) | |
| | ff_mult | {2, 4} | |
| | dropout | [0.0, 0.3] | |
| | lr | log [1e-4, 1e-3] | |
| | mask_ratio | [0.10, 0.30] | |
| | max_len | {64, 128, 256} (≥ p90 độ dài) | |
| C5 tầng | W | {30, 60, 90} ngày | Độ ổn định: phương sai điểm `a` theo ngày trên val (thấp hơn tốt) + ràng buộc phân phối `a` ≈ chuẩn tắc |
| | k_P | [7, 60] ngày | |
| | k_G | [3, 30] người | |
| | min_group_size | {2, 3, 5} | |
| C6 ngưỡng | p | [0.90, 0.999] | Chọn p nhỏ nhất thoả ngân sách B cảnh báo/ngày/1000 user trên val (không phải tối ưu hoá, là giải ràng buộc) |
| | R | {1, 7, 14} ngày | |

Lưu ý mục tiêu C5: loss tái tạo không áp được cho tầng chuẩn hoá. Mục tiêu "độ ổn định" là mặc định đề xuất; nếu người dùng muốn mục tiêu khác (ví dụ tối thiểu số cảnh báo ở ngân sách cố định), đó là một câu hỏi phải hỏi kèm 3 phương án và ghi Decision Log.

## 4. Sau khi tune

1. Train lại mô hình với best params trên train (giữ val cho early stop), **5 seed** (0–4).
2. Lưu bảng best params vào tài liệu BA § Tham số đã tinh chỉnh: tham số, giá trị, khoảng tìm, mục tiêu, giá trị mục tiêu, `runs/<id>`, số trial.
3. Vẽ / lưu importance (`optuna.importance`) và lịch sử trial để dán phụ lục.
4. Ghi Decision Log một dòng cho mỗi tầng đã tune: giá trị chốt, lý do, phương án thứ hai gần nhất.

## 5. Phân tích độ nhạy (cho paper)

Với α, k_P, k_G, W, p: quét lưới thô quanh giá trị chốt, báo cáo PR-AUC/FPR trên **test** sau khi đã chốt — đây là phân tích độ nhạy, không dùng để chọn lại tham số. Nếu có ý định chọn lại sau khi xem, phải hỏi người dùng và ghi Decision Log (theo nguyên tắc 5).
