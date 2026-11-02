---
id: SPEC-{NNN}
title: {Tên ngắn}
status: Draft            # Draft → Accepted → Implemented → (Superseded)
version: 0.1             # tăng phần lẻ mỗi lần sửa theo góp ý; lên 1.0 khi Accepted
date: {YYYY-MM-DD}
rq: [RQ1]                # RQ phục vụ
components: [C2]         # theo model-design.md
decisions: [DL-001]      # Decision Log liên quan
supersedes: null
---

# SPEC-{NNN} — {Tên}

## 1. Mục tiêu

{2–4 câu: spec này làm gì, trả lời RQ / Gap nào, trích đoạn nào trong đề cương.}

## 2. Phạm vi

{Danh sách việc trong phạm vi. Việc cố ý không làm và lý do ghi ở Decision Log, không ghi ở đây.}

## 3. Dữ liệu vào / ra

| Đối tượng | Nguồn / đích | Schema / shape | Ghi chú |
|---|---|---|---|

## 4. Thiết kế

{Công thức, thuật toán, sơ đồ luồng. Mỗi mục con đánh số §4.1, §4.2… để code trích dẫn được.}

## 5. Tham số

| Tham số | Khoá config | Mặc định | Khoảng tune | Lý do mặc định |
|---|---|---|---|---|

## 6. Thay đổi code

| Tệp | Tạo / sửa | Lớp / hàm (chữ ký) | Mục spec |
|---|---|---|---|

## 7. Thí nghiệm & chỉ số

{Chỉ khi spec có chạy thí nghiệm: cấu hình, biến thể ablation, chỉ số, số seed, kiểm định. Nếu không có: ghi "Không áp dụng".}

## 8. Tiêu chí chấp nhận

| # | Tiêu chí (kiểm được) | Cách kiểm |
|---|---|---|
| AC-01 | | pytest `tests/test_x.py::test_y` |

## 9. Kế hoạch test

{Test nào, dữ liệu giả nào, kiểm AC nào; test leakage bắt buộc nếu spec chạm dữ liệu / chuẩn / ngưỡng.}

## 10. Thực thi

- Thứ tự bước:
- Lệnh chạy:
- Ước tính thời gian / VRAM trên RTX 3050 4GB:

## 11. Rủi ro

| Rủi ro | Dấu hiệu | Cách xử lý |
|---|---|---|

## 12. Open Questions

{Mỗi câu một dòng, 3 phương án, phương án đề xuất đứng đầu. Câu đã trả lời → chuyển sang Decision Log và xoá khỏi bảng (không đánh số lại).}

| # | Câu hỏi | A (đề xuất) | B | C | Chặn bước nào |
|---|---|---|---|---|---|

## 13. Review readiness

{Dán kết quả 3 vòng theo mẫu trong references/review-rounds.md.}
