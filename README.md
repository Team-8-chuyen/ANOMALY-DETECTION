# Framework-rework — Phát hiện Insider Threat

Phạm vi đang bàn giao: ghép LDAP vào dữ liệu đã tiền xử lý theo SPEC-001 v1.1 và chọn duy nhất Personal → Group → Global theo SPEC-002 v1.2. Hai case dùng Group theo Department hoặc Role; điểm do bên ngoài cung cấp, chưa tạo threshold hoặc đánh giá hiệu quả phát hiện.

Trạng thái: **đã triển khai, 151 test qua**. [Hướng dẫn chạy bộ chọn tầng](docs/three-tier-usage.md) · [Ghép LDAP](docs/enrich-preprocessed-ldap-usage.md). Code hiện tại chỉ cần hai CLI `scripts/enrich_preprocessed_ldap.py` và `scripts/run_tier_routing.py`, bốn config trong `configs/experiments/`, ba module hỗ trợ tương ứng, test và `requirements-ldap.txt`. Các mục C1–C7 bên dưới là cấu trúc nghiên cứu dự kiến, không phải danh sách tính năng đã triển khai.

Môi trường Python, dữ liệu, run artifact và IDE settings được giữ local và loại khỏi Git. Các script prototype/bản xuất cũ không dùng ở lần chạy hiện tại được sao lưu trong `.local-archive/` (gitignored); dùng code/config/test/spec hiện hành để bàn giao.

Các đường dẫn code/báo cáo cũ được nhắc trong phần lịch sử của spec và tài liệu nằm tại [commit 7331adf](https://github.com/Team-8-chuyen/ANOMALY-DETECTION/tree/7331adfe8807a62716f11dc4e920f9b4d20c66a8), không phải thành phần của pipeline hiện tại.

## Cấu trúc

```
Framework-rework/
├── CLAUDE.md                 # quy tắc làm việc cho Claude trong project
├── README.md
├── pyproject.toml            # (chưa tạo) — tạo ở SPEC-001; Python 3.11 + PyTorch CUDA (DL-008)
├── configs/
│   ├── base.yaml             # mọi tham số; code không hard-code số
│   └── experiments/          # rq1_*.yaml, rq2_*.yaml, rq3_*.yaml — chỉ ghi phần khác base
├── data/                     # gitignore
│   ├── raw/cert-r4.2/        # CSV gốc CERT r4.2 + LDAP/ + answers/ (DL-007)
│   ├── interim/              # sự kiện chuẩn hoá, parquet theo tháng
│   └── processed/            # x_f, chuỗi token, nhãn user-day, split
├── src/itd/
│   ├── data/                 # C1 — đọc CERT, LDAP, nhãn, chia tập
│   ├── features/             # C2 đặc trưng x_f · C3 token chuỗi x_s
│   ├── models/               # Feature AE (C2) · Seq Transformer (C3)
│   ├── scoring/              # C4 hợp nhất · C5 chuẩn 3 tầng · C6 ngưỡng
│   ├── training/             # trainer, tune Optuna
│   ├── evaluation/           # C7 chỉ số, ablation, báo cáo
│   └── utils/                # config, seed, io, logging
├── scripts/                  # CLI mỏng gọi vào src: prepare_data, train, tune, score, evaluate, run_ablation
├── tests/                    # pytest; dữ liệu giả nhỏ trong tests/fixtures/
├── specs/                    # SPEC-001-*.md …
├── docs/
│   ├── BA-insider-threat-detection.md   # tài liệu BA sống + Decision Log
│   └── luong-hoat-dong.md               # bản local của Google Doc "Luồng hoạt động"
├── runs/                     # gitignore — mỗi lần chạy một thư mục runs/<YYYYMMDD-HHMM>-<slug>/
└── reports/                  # bảng (tables/) và hình (figures/) cho paper, sinh tự động từ runs/
```

## Thành phần ↔ chỗ đặt code

Tên tệp dưới đây là **dự kiến** theo chuẩn kỹ thuật của skill; tên và chữ ký hàm chốt ở § 6 của từng spec.

| Thành phần | Thư mục | Tệp dự kiến | Script |
|---|---|---|---|
| C1 Dữ liệu & nhãn | `src/itd/data/` | `load_cert.py`, `ldap.py`, `labels.py`, `split.py` | `prepare_data` |
| C2 Luồng đặc trưng | `src/itd/features/`, `src/itd/models/` | `count_features.py`, `feature_ae.py` | `train`, `tune` |
| C3 Luồng chuỗi | `src/itd/features/`, `src/itd/models/` | `sequence_tokens.py`, `seq_transformer.py` | `train`, `tune` |
| C4 Hợp nhất điểm | `src/itd/scoring/` | `fusion.py` | `score` |
| C5 Chuẩn 3 tầng | `src/itd/scoring/` | `tiers.py` | `score` |
| C6 Ngưỡng thích ứng | `src/itd/scoring/` | `threshold.py` | `score` |
| C7 Đánh giá & ablation | `src/itd/evaluation/` | `metrics.py`, `ablation.py`, `report.py` | `evaluate`, `run_ablation` |
| Dùng chung | `src/itd/training/`, `src/itd/utils/` | `trainer.py`, `tune.py`, `config.py`, `seed.py`, `io.py`, `logging.py` | — |

## Quy trình

Mỗi thành phần: viết spec trong `specs/` → review 3 vòng → người dùng duyệt → code + test → cập nhật tài liệu BA và Decision Log → cập nhật Google Doc. Thứ tự làm theo phụ thuộc C1 → C7.
