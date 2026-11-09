# CERT r4.2 processed — Behaviour100 + Sequence24

Gói dữ liệu để chuyển sang máy train khác. Ngày tạo: 2026-11-09.

## Nội dung

- `data/processed/user_day_features/`: 64 Parquet, 330.452 user-day, 100 feature + 100 mask.
- `data/processed/user_day_features_ocean/`: Behaviour100 + OCEAN5 phục vụ ablation.
- `data/processed/user_day_sequences/`: 64 Parquet, 12.523.202 dòng Sequence, 24 trường nghiệp vụ.
- `data/artifacts/`: manifest, checkpoint và thống kê độ dài chuỗi.
- `configs/`, `src/`, `scripts/`, `pyproject.toml`: cấu hình và code đọc dữ liệu.

Không gồm CSV raw và canonical events trung gian. Tổng `run_count` trong Sequence khôi phục đúng 32.770.222 sự kiện raw.

## Kiểm tra nhanh trên máy nhận

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -c "import polars as pl; print(pl.scan_parquet('data/processed/user_day_features/bucket-*.parquet').select(pl.len()).collect())"
```

Kết quả Behaviour phải là `330452`; Sequence phải là `12523202`. Hai nhánh nối bằng khóa `(user, day)`.

## Lưu ý

- Bucket là phân vùng theo user, không phải Train/Validation/Test.
- Chưa có nhãn độc hại vì nguồn hiện tại thiếu thư mục `answers/`.
- Phải chia Train/Validation/Test theo thời gian sau khi giải nén.
