# Phát hiện Insider Threat — Tài liệu BA

Tài liệu sống của project: hệ thống đang làm gì, đã code tới đâu, chạy thế nào, vì sao quyết định như vậy. Cập nhật **mỗi lần code**; mọi thay đổi có một dòng Decision Log.

Bản {YYYY-MM-DD} · Version {X.Y}

## 1. Tổng quan

- **Mục tiêu**: phát hiện insider threat bằng anomaly detection kết hợp 2 luồng (chuỗi + đặc trưng), chuẩn hành vi 3 tầng Personal – Group – Global, ngưỡng thích ứng.
- **Câu hỏi nghiên cứu**: RQ1 · RQ2 · RQ3 (nguyên văn: `.claude/skills/insider-threat-model-dev/references/research-proposal.md`).
- **Dữ liệu**: CERT {rX.Y} — {số user thực} user, {số insider thực} insider, {ngày đầu} → {ngày cuối}.

## 2. Trạng thái thành phần

| Thành phần | Spec | Trạng thái | Test | Run gần nhất |
|---|---|---|---|---|
| C1 Dữ liệu & nhãn | | Chưa làm | | |
| C2 Luồng đặc trưng | | Chưa làm | | |
| C3 Luồng chuỗi | | Chưa làm | | |
| C4 Hợp nhất điểm | | Chưa làm | | |
| C5 Chuẩn 3 tầng | | Chưa làm | | |
| C6 Ngưỡng thích ứng | | Chưa làm | | |
| C7 Đánh giá & ablation | | Chưa làm | | |

Trạng thái: Chưa làm · Spec draft · Spec accepted · Đang code · Xong · Cần sửa.

## 3. Dữ liệu

- Nguồn, đường dẫn, số dòng thực mỗi tệp.
- Chia tập: train {từ–đến}, val {từ–đến}, test {từ–đến}; số user-day, số user-day độc hại mỗi tập.
- Quy tắc lọc user, cách gán nhãn.

## 4. Pipeline

{Sơ đồ text cập nhật theo code thật — không chép model-design.md nếu code đã khác.}

## 5. Thành phần

### C{n} — {Tên}

- **Làm gì**:
- **Vào / ra**:
- **Tệp code**:
- **Tham số chính** (giá trị đang dùng):
- **Spec**: SPEC-{NNN} v{X.Y}

## 6. Tham số đã tinh chỉnh

| Tầng | Tham số | Giá trị | Khoảng tìm | Mục tiêu (val) | Trial | Run |
|---|---|---|---|---|---|---|

## 7. Thí nghiệm & kết quả

| Ngày | Run | Cấu hình | RQ | PR-AUC | Recall@1% | FPR | Ghi chú |
|---|---|---|---|---|---|---|---|

Lần mở test: {N} — xem Decision Log.

## 8. Cách chạy

```bash
# môi trường
# chuẩn bị dữ liệu
# train / tune / evaluate
# test
```

## 9. Open Questions

| # | Câu hỏi | A (đề xuất) | B | C | Chặn |
|---|---|---|---|---|---|

Câu đã trả lời → ghi Decision Log rồi xoá dòng ở đây (không đánh số lại).

## 10. Version History

| Version | Ngày | Thay đổi | Spec / DL |
|---|---|---|---|
| 0.1 | {YYYY-MM-DD} | Khởi tạo tài liệu | — |

## 11. Decision Log

Mỗi thay đổi về thiết kế, tham số, dữ liệu, code, hoặc phạm vi là một dòng. Lý do ghi kèm **phương án bị loại**. Đánh số tăng dần, không dùng lại số.

| # | Liên quan | Quyết định | Lý do | Ngày |
|---|---|---|---|---|
| DL-001 | {SPEC / C / tệp} | **{Quyết định in đậm}** | {Ai chốt, căn cứ. **Phương án bị loại**: … — vì …} | {YYYY-MM-DD} |
