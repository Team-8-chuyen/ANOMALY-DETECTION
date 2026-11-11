# Specs

Mỗi spec là một tệp `SPEC-NNN-<slug>.md`, tạo từ `templates/spec-template.md` của skill `insider-threat-model-dev`. NNN tăng dần, không dùng lại số. Chỉ code khi spec có `status: Accepted`.

## Danh mục

| Spec | Thành phần | Trạng thái | Version |
|---|---|---|---|
| [SPEC-001](SPEC-001-role-baseline-validation.md) | Ghép LDAP vào feature/sequence Parquet; giữ lịch sử v1.0 | Implemented — 21 test qua; toàn bộ output đọc lại khớp | 1.1 |
| [SPEC-002](SPEC-002-three-tier-group-ablation.md) | Chọn một tầng Department/Role và giao diện nhận điểm ngoài | Implemented — 151 test qua; routing thật, score chờ cung cấp | 1.2 |

SPEC-003 đã bỏ theo yêu cầu người dùng. Nhiệm vụ hiện tại: sửa phương pháp chọn tầng và ghép LDAP vào bộ dữ liệu đã tiền xử lý; không mở rộng thành toàn bộ mô hình feature/sequence. Chi tiết yêu cầu đang làm rõ: [three-tier-routing-change.md](../docs/three-tier-routing-change.md).

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
