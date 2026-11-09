# Specs

Mỗi spec là một tệp `SPEC-NNN-<slug>.md`, tạo từ `templates/spec-template.md` của skill `insider-threat-model-dev`. NNN tăng dần, không dùng lại số. Chỉ code khi spec có `status: Accepted`.

## Danh mục

| Spec | Thành phần | Trạng thái | Version |
|---|---|---|---|
| — | — | Chưa có spec | — |

## Thứ tự dự kiến

Theo phụ thuộc C1 → C7; thứ tự và cách gộp thành phần vào từng spec hỏi người dùng trước khi viết.

| Bước | Thành phần | Quyết định phải chốt trước |
|---|---|---|
| 1 | C1 Dữ liệu & nhãn (+ môi trường, `pyproject.toml`, `utils/`) | D-01 ✔ DL-007, D-12 ✔ DL-008; D-02, D-03 hoãn (DL-009) — C1 làm cả 3 phương án thành tuỳ chọn config, chốt trước lần train đầu |
| 2 | C2 Luồng đặc trưng | danh sách đặc trưng, danh sách domain/từ khoá (bẫy L7) |
| 3 | C3 Luồng chuỗi | D-04, D-05 |
| 4 | C4 Hợp nhất điểm | D-06 |
| 5 | C5 Chuẩn 3 tầng | D-07, D-08, D-09, D-11 |
| 6 | C6 Ngưỡng thích ứng | D-10, D-11 |
| 7 | C7 Đánh giá & ablation | baseline ngoài (tuỳ chọn) |
