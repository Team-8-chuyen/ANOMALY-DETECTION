---
id: SPEC-002
title: Huấn luyện không giám sát hai nhánh Behaviour và Sequence
status: Accepted
version: 1.0
date: 2026-11-10
rq: [RQ1]
components: [C1, C2, C3, C4]
decisions: [DL-018, DL-019, DL-020, DL-021]
supersedes: null
---

# SPEC-002 — Huấn luyện không giám sát hai nhánh Behaviour và Sequence

## 1. Mục tiêu

Tạo dữ liệu train/validation/test theo thời gian, gắn nhãn CERT r4.2 chỉ để đánh giá, huấn luyện độc lập một Behaviour Autoencoder và một TCN–Transformer Autoencoder, chuẩn hóa hai lỗi tái tạo rồi hợp nhất thành điểm bất thường gốc. SPEC này phục vụ RQ1 và tạo đầu vào cho cơ chế fallback `Personal → Role → Global` ở spec tiếp theo.

Mô hình chính là không giám sát nghiêm ngặt: nhãn không được dùng để lọc train, fit scaler/vocabulary, tối ưu loss, early stopping, chọn siêu tham số hoặc chọn trọng số fusion.

## 2. Phạm vi

- Chỉ đọc đáp án trong `answers/r4.2-1`, `answers/r4.2-2`, `answers/r4.2-3` và các dòng `dataset=4.2` trong `insiders.csv`.
- Tạo nhãn user-day bằng phép OR trên `event_id`; lưu riêng `scenario`, `actor_user` và `event_account` để xử lý kịch bản 3.
- Chia toàn bộ trục ngày liên tiếp theo tỷ lệ xấp xỉ 60/15/25; mọi user dùng chung biên thời gian.
- Giữ nguyên user-day độc hại nếu rơi vào train; code model không được đọc cột nhãn.
- Huấn luyện Behaviour Autoencoder và TCN–Transformer Autoencoder độc lập.
- Hợp nhất ba biến thể RQ1: Behaviour-only, Sequence-only, Behaviour+Sequence late fusion.
- Chưa triển khai tầng fallback, ngưỡng, 18 cấu hình ablation hoặc mở kết quả test cuối.

## 3. Dữ liệu vào và ra

| Đối tượng | Đường dẫn | Schema/shape |
|---|---|---|
| Behaviour | `data/processed/user_day_features/*.parquet` | `user, day, f001..f100, m001..m100` |
| Sequence | `data/processed/user_day_sequences/*.parquet` | một dòng/event đã nén; 24 trường logic + khóa |
| Answers | `data/raw/cert-r4.2/answers/` | chỉ r4.2; định dạng không có header trong tệp scenario |
| Split | `data/processed/model_windows/split.parquet` | `user, day, split, label, scenarios, actor_user, event_account` |
| Behaviour tensors | `data/processed/model_windows/behaviour/*.parquet` | 100 value, 100 mask; scaler train-only |
| Sequence index | `data/processed/model_windows/sequences/*.parquet` | user-day, offset/length, split |
| Model | `runs/<id>/{behaviour_ae.pt,sequence_ae.pt}` | best checkpoint theo validation reconstruction loss |
| Scores | `runs/<id>/scores.parquet` | `user,day,split,e_beh,e_seq,z_beh,z_seq,base_score,label,scenario` |

## 4. Nhãn và chia tập

### 4.1 Nhãn

Parser answer đọc mỗi dòng theo vị trí `source,event_id,date,user,pc,...`; không dùng `pandas.read_csv` với schema cố định vì các source có số trường khác nhau. Chỉ nhận tệp khớp `r4.2-[123]/r4.2-[123]-*.csv`.

`event_day_label=1` khi user-day chứa ít nhất một `event_id` xuất hiện trong answer. `incident_window_label` từ `insiders.csv` được lưu để đánh giá theo khoảng, không thay thế nhãn event-day. Nhãn tuyệt đối không được truyền vào Dataset dùng cho train/validation.

### 4.2 Split

Lấy danh sách ngày lịch duy nhất từ min đến max và chọn hai biên gần nhất với 60% và 75% số ngày:

- train: `[min_day, cut_60)`;
- validation: `[cut_60, cut_75)`;
- test: `[cut_75, max_day]`.

Không shuffle ngày. Scaler, vocabulary và thống kê fusion chỉ fit trên train. Validation chỉ dùng reconstruction loss không nhãn. Test không được đọc trước khi người dùng cho phép mở test.

## 5. Behaviour Autoencoder

### 5.1 Biến đổi

- Count/duration/size/gap: `log1p` theo registry SPEC-001.
- Ratio giữ trong `[0,1]`.
- Robust scaling: `(x - median_train)/(IQR_train + eps)` theo từng feature.
- Value thiếu đặt 0 sau scale; mask được nối làm context nhưng không tính là đặc trưng nghiệp vụ.

### 5.2 Kiến trúc

Đầu vào `[B,200] = concat(values[100], masks[100])`. Encoder mặc định `200→128→64→32`; decoder `32→64→128→100`, GELU và dropout 0.1. Decoder chỉ tái tạo 100 values.

Loss có mask:

`L_beh = sum(m * (x - x_hat)^2) / (sum(m) + eps)`.

Điểm `e_beh` là loss theo từng user-day, không phải trung bình batch.

## 6. TCN–Transformer Autoencoder

### 6.1 Tensor hóa

- Categorical vocabulary chỉ fit trên train, có `<pad>` và `<unk>`.
- Continuous fields được robust-scale bằng train.
- `max_len` lấy giá trị nhỏ nhất trong `{64,128,256}` không thấp hơn p99 độ dài chuỗi train sau nén; nếu p99 > 256 thì dùng 256.
- Chuỗi dài được chia thành các cửa sổ không chồng lấn tối đa `max_len`; điểm user-day là trung bình có trọng số theo số token của các cửa sổ.
- Padding mask không đóng góp vào loss.

### 6.2 Kiến trúc

Embedding token/categorical và projection continuous được cộng/ghép rồi chiếu về `d_model=64`. Encoder gồm ba residual TCN block với dilation `1,2,4`, sau đó hai Transformer encoder layer (`n_heads=4`, `ff_mult=2`). Decoder có các head tái tạo token/categorical bằng cross-entropy và continuous bằng masked MSE.

`L_seq = lambda_token * L_CE + lambda_cont * L_MSE`, mặc định hai lambda bằng 1. Điểm `e_seq` là loss tái tạo theo user-day.

## 7. Huấn luyện

- Optimizer AdamW; Behaviour `lr=1e-3`, Sequence `lr=5e-4`, `weight_decay=1e-5`.
- Batch Behaviour 512; Sequence bắt đầu 32 trên RTX 3050 4 GB, AMP fp16 và gradient accumulation để effective batch 128.
- Tối đa 200 epoch; early stop trên validation reconstruction loss với patience 10 (Behaviour) và 7 (Sequence).
- Train chứa mọi mẫu, kể cả ngày độc hại chưa biết; labels không được load trong trainer.
- Seed đầy đủ cho Python, NumPy, Torch và DataLoader.
- Checkpoint atomic sau mỗi epoch tốt nhất; `--resume` tiếp tục optimizer/scheduler/epoch.

## 8. Chuẩn hóa và fusion

Fit median/IQR của `e_beh` và `e_seq` chỉ trên train:

`z_beh=(e_beh-med_train_beh)/(iqr_train_beh+eps)`

`z_seq=(e_seq-med_train_seq)/(iqr_train_seq+eps)`

Ba cấu hình RQ1:

- `B`: `base_score=z_beh`;
- `S`: `base_score=z_seq`;
- `B+S`: `base_score=0.5*z_beh+0.5*z_seq`.

Phân tích độ nhạy alpha `{0.25,0.5,0.75}` chỉ chạy sau khi cấu hình chính đã khóa; không dùng để chọn lại alpha từ nhãn test.

## 9. Config

| Khóa | Mặc định |
|---|---|
| `split.scheme` | `chronological_ratio` |
| `split.ratios` | `[0.60,0.15,0.25]` |
| `split.malicious_in_train` | `keep` |
| `feature_ae.hidden` | `[128,64]` |
| `feature_ae.latent` | `32` |
| `feature_ae.dropout` | `0.1` |
| `feature_ae.batch_size` | `512` |
| `seq_transformer.d_model` | `64` |
| `seq_transformer.tcn_dilations` | `[1,2,4]` |
| `seq_transformer.n_layers` | `2` |
| `seq_transformer.n_heads` | `4` |
| `seq_transformer.batch_size` | `32` |
| `fusion.alpha` | `0.5` |

## 10. Tệp dự kiến tạo/sửa

- `src/itd/data/labels.py`: parser r4.2 có scenario và hai định danh actor/account.
- `src/itd/data/split.py`: chronological split và guard chống leakage.
- `src/itd/data/datasets.py`: Behaviour/Sequence Dataset không nhận label khi train.
- `src/itd/models/feature_ae.py`: `FeatureAutoencoder`.
- `src/itd/models/tcn_transformer_ae.py`: `TCNTransformerAutoencoder`.
- `src/itd/training/trainer.py`: fit/resume/early stopping/AMP.
- `src/itd/scoring/fusion.py`: train-only robust score normalization và ba cấu hình RQ1.
- `scripts/prepare_model_data.py`, `scripts/train.py`, `scripts/score.py`.
- `configs/experiments/rq1_behaviour.yaml`, `rq1_sequence.yaml`, `rq1_late_fusion.yaml`.
- Test tương ứng trong `tests/`.

## 11. Tiêu chí chấp nhận

1. Chỉ 70 tệp answer r4.2 được đọc; r5.2/r6.x không ảnh hưởng nhãn.
2. Split tăng đơn điệu theo thời gian và dùng chung biên cho mọi user.
3. Label không xuất hiện trong tensor, trainer hoặc objective.
4. Scaler/vocabulary/fusion statistics chỉ fit trên train.
5. Behaviour forward/backward đúng shape và padding/mask không làm thay đổi loss phần không hợp lệ.
6. Sequence forward/backward đúng shape; padding không đóng góp loss.
7. Hai model overfit được một batch fixture nhỏ.
8. `alpha=0` khớp Sequence-only; `alpha=1` khớp Behaviour-only sau chuẩn hóa.
9. Resume cho kết quả tương đương run liên tục với cùng seed.
10. Smoke tối đa 20 user × 30 ngày sinh đủ checkpoint và scores trong dưới 5 phút trên chế độ test nhỏ.
11. Không mở hoặc báo cáo metric test khi chưa có xác nhận riêng của người dùng.

## 12. Lệnh dự kiến

```powershell
.\.venv\Scripts\python scripts\prepare_model_data.py --config configs/base.yaml
.\.venv\Scripts\python scripts\train.py --config configs/experiments/rq1_behaviour.yaml
.\.venv\Scripts\python scripts\train.py --config configs/experiments/rq1_sequence.yaml
.\.venv\Scripts\python scripts\score.py --config configs/experiments/rq1_late_fusion.yaml
```

Ước tính RTX 3050 4 GB: chuẩn bị model data 10–30 phút; Behaviour 10–40 phút/seed; Sequence 2–8 giờ/seed. Tune và 5 seed full không tự chạy trong bước code.

## 13. Review readiness — v0.1 — 2026-11-10

| Vòng | Blocker | Major | Minor | Điểm |
|---|---:|---:|---:|---:|
| Đầy đủ & truy vết | 0 | 0 | 1 | 9.75 |
| Đúng đắn khoa học | 0 | 0 | 1 | 9.75 |
| Sẵn sàng dev | 0 | 0 | 1 | 9.75 |

Các minor đã xử lý: khóa phạm vi answer ở r4.2; tách actor khỏi event account; quy định label không được load trong trainer; quy định chia cửa sổ thay vì cắt bỏ chuỗi dài.

**Kết luận: READY** — người dùng duyệt ngày 2026-11-10; được phép bắt đầu code.

## 14. Code review — v1.0 — 2026-11-10

| Vòng | Kết quả | Bằng chứng |
|---|---|---|
| Khớp spec | READY | Split, label parser, hai model, fusion và CLI đã triển khai |
| Đúng đắn | READY | Label không xuất hiện trong trainer; thống kê chỉ fit trên train; mask/padding tests qua |
| Chạy được | READY có điều kiện | `pytest`: 15/15 qua; ba CLI `--help` chạy được; chưa chạy full CERT/training |

Điều kiện còn lại: người dùng chạy `prepare_model_data.py`, sau đó smoke/full training. Tập test chưa được mở và chưa có metric kết quả.
