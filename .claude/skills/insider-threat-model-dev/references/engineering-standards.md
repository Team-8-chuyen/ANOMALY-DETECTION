# Chuẩn kỹ thuật khi code

## 1. Cấu trúc project (mặc định, chốt ở spec đầu tiên)

```
D:\AI for BA\MW\Framework-rework\
├── CLAUDE.md
├── pyproject.toml            # hoặc requirements.txt có pin version
├── configs/
│   ├── base.yaml             # mọi tham số; code không hard-code số
│   └── experiments/          # rq1_*.yaml, rq2_*.yaml, rq3_*.yaml — chỉ ghi phần khác base
├── data/                     # gitignore
│   ├── raw/cert-r4.2/        # csv gốc + answers/
│   ├── interim/              # sự kiện chuẩn hoá, parquet theo tháng
│   └── processed/            # x_f, chuỗi token, nhãn user-day, split
├── src/itd/
│   ├── data/                 # load_cert.py, labels.py, split.py, ldap.py
│   ├── features/             # count_features.py, sequence_tokens.py
│   ├── models/               # feature_ae.py, seq_transformer.py
│   ├── scoring/              # fusion.py, tiers.py, threshold.py
│   ├── training/             # trainer.py, tune.py
│   ├── evaluation/           # metrics.py, ablation.py, report.py
│   └── utils/                # config.py, seed.py, io.py, logging.py
├── scripts/                  # CLI mỏng gọi vào src: prepare_data, train, tune, score, evaluate, run_ablation
├── tests/                    # pytest, dữ liệu giả nhỏ trong tests/fixtures/
├── specs/                    # SPEC-001-*.md …
├── docs/BA-insider-threat-detection.md   # tài liệu BA sống + Decision Log
├── runs/                     # gitignore — mỗi lần chạy một thư mục
└── reports/                  # bảng/hình cho paper (sinh tự động từ runs/)
```

## 2. Cấu hình

- YAML + dataclass có kiểu (hoặc pydantic). Mọi tham số mô hình, đường dẫn, khung giờ, seed nằm trong config.
- Script nhận `--config configs/experiments/x.yaml` và `--override key=value`; config cuối cùng (đã gộp) được ghi ra `runs/<id>/config.yaml`.
- Tên khoá config trùng tên tham số trong spec (để truy vết spec ↔ code ↔ BA doc).

## 3. Thư mục chạy và tái lập

- `runs/<YYYYMMDD-HHMM>-<slug>/` chứa: `config.yaml`, `env.txt` (python, torch, cuda, GPU), `git.txt` (commit + diff nếu có), `metrics.json`, `scores.parquet` (user, day, e_f, e_s, s, a, τ, label), `model.pt`, `log.txt`.
- `seed_everything(seed)`: `random`, `numpy`, `torch`, `torch.cuda`; `torch.backends.cudnn.deterministic=True`, `benchmark=False`; DataLoader `worker_init_fn` + `generator` có seed.
- Không ghi đè run cũ. Báo cáo trong BA doc trỏ tới `runs/<id>`.

## 4. Dữ liệu lớn

- `http.csv` hàng chục GB: `pd.read_csv(chunksize=…, usecols=…)` hoặc `pyarrow`/`polars` lazy; ghi parquet theo tháng; bước sau đọc parquet.
- Không giới hạn số dòng đọc (bẫy L6). In và ghi log số dòng mỗi tệp.
- Bước chuẩn bị dữ liệu idempotent: chạy lại cho cùng kết quả; có cờ `--force` để làm lại.

## 5. Code

- Python 3.11/3.12, type hints, hàm nhỏ thuần (input → output) cho phần tính toán để test được; I/O nằm ở rìa.
- Mô hình PyTorch: `nn.Module` không biết gì về file/đường dẫn; trainer tách riêng; early stopping + lưu checkpoint tốt nhất theo loss val.
- Tính toán theo lô có mask cho padding; kiểm `nan/inf` sau mỗi epoch, dừng sớm có thông báo rõ.
- Không dùng notebook cho logic lõi; notebook (nếu có) chỉ đọc `runs/` để vẽ.
- Comment ngắn, chỉ giải thích *vì sao*; công thức trong code ghi kèm mã mục spec (ví dụ `# SPEC-003 §4.2`).

## 6. Test bắt buộc

| Loại | Ví dụ |
|---|---|
| Đơn vị | đếm đặc trưng đúng trên fixture 2 user × 3 ngày; token hoá đúng thứ tự; chuẩn hoá robust z đúng |
| Leakage (L1, L2) | scaler/vocab chỉ thấy ngày train; đổi dữ liệu sau ngày t không đổi `a_u,t`, `τ_u,t` |
| Hình dạng | forward/backward hai mô hình với batch giả, mask padding không ảnh hưởng loss |
| Overfit một lô | mỗi mô hình về loss ≈ 0 trên 1 batch nhỏ sau N bước (bắt lỗi pipeline) |
| Trọng số tầng | `w_P + w_G + w_O = 1`; user mới → `w_P = 0`; nhóm nhỏ hơn ngưỡng → `w_G = 0` |
| Ngưỡng | ngân sách B được thoả trên dữ liệu giả; τ cập nhật đúng chu kỳ R |
| Chỉ số | PR-AUC, Recall@k khớp sklearn trên ví dụ tay |
| Smoke | pipeline đầu-cuối trên tập con (≤ 20 user, ≤ 30 ngày) chạy < 5 phút, ra đủ tệp trong `runs/` |

## 7. Môi trường

Máy hiện tại (đo 01/11/2026): Python **3.14**, torch **2.13 bản CPU** (`cuda False`), GPU RTX 3050 Laptop 4GB, chưa có `optuna`, `scikit-learn`. Vì vậy trước lần code đầu tiên phải hỏi D-12 (môi trường) — **không tự cài đặt**. Sau khi chốt, ghi lệnh tạo venv và cài đặt vào BA doc § Cách chạy, và kiểm `torch.cuda.is_available()` trước khi train.
