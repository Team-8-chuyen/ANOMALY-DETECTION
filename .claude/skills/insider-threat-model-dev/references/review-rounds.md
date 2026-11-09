# Review 3 vòng — mức sẵn sàng

Hai chế độ:

- **Chế độ spec** (bắt buộc trước khi trình spec): trả lời *"đưa spec này cho dev (hoặc cho chính Claude ở phiên sau) thì code ra đúng mà không phải hỏi thêm không?"*
- **Chế độ code** (bắt buộc sau khi code xong): trả lời *"code này đúng spec, đúng khoa học, chạy được chưa?"*

## Cách chạy mỗi vòng

1. Đọc lại tệp từ đĩa (không dựa vào trí nhớ lúc viết). Mỗi vòng chỉ dùng **một lăng kính** dưới đây, đi hết checklist của vòng đó.
2. Nếu có công cụ Agent, nên giao vòng 2 cho một subagent mới chỉ được đưa spec + `references/` (không đưa lập luận của mình) để có góc nhìn không bị neo. Không có thì tự làm.
3. Phân loại phát hiện:
   - **Blocker** — dev không code được, hoặc code ra sai kết quả nghiên cứu (leakage, sai công thức, thiếu thành phần trả lời RQ).
   - **Major** — dev phải đoán; có thể code ra khác ý đồ.
   - **Minor** — trình bày, đặt tên, thiếu tham chiếu chéo.
4. Xử lý:
   - Sửa **cơ học** (lỗi chính tả, thiếu tham chiếu, đánh số, đơn vị rõ ràng chỉ có một cách hiểu) → sửa ngay, ghi vào bảng review là "đã sửa".
   - Mọi phát hiện cần **chọn hướng** (đổi thiết kế, tham số, phạm vi, chỉ số) → **không tự sửa**; biến thành Open Question với 3 phương án và hỏi người dùng.
5. Vòng sau chạy trên bản đã sửa của vòng trước.

## Chế độ spec

### Vòng 1 — Đầy đủ & truy vết

- [ ] Mục tiêu nêu RQ / Gap nào spec phục vụ; mỗi thành phần truy được về đoạn trong research-proposal.md.
- [ ] Mọi thành phần có: đầu vào (schema, shape, kiểu), đầu ra, công thức / thuật toán, tham số.
- [ ] Mọi tham số có: khoá config, mặc định, khoảng tune (nếu tune), lý do mặc định.
- [ ] Mọi D-xx spec chạm tới đã có trong Decision Log, hoặc nằm trong Open Questions.
- [ ] Tiêu chí chấp nhận (AC) đánh số, mỗi AC kiểm được bằng test hoặc bằng lệnh chạy.
- [ ] Ablation / đối chứng của RQ liên quan có mặt (theo ma trận model-design.md §8).

### Vòng 2 — Đúng đắn khoa học

- [ ] Chia tập theo thời gian; không mục nào fit trên val/test (L1, L4).
- [ ] Chuẩn tầng và ngưỡng chỉ dùng quá khứ `[t−W, t)` (L2).
- [ ] Không đặc trưng nào lộ nhãn (L3, L7); quy tắc lọc user như nhau mọi tập (L8).
- [ ] Mọi tham số được chọn trên val không nhãn (L5, tuning-protocol.md).
- [ ] Chỉ số phù hợp dữ liệu lệch lớp (PR-AUC chính; có Recall@k, FPR; không accuracy).
- [ ] So sánh công bằng: biến thể ablation dùng cùng split, cùng ngân sách tune, cùng seed.
- [ ] Có 5 seed + kiểm định thống kê cho kết luận "tốt hơn".
- [ ] Không lặp lại vấn đề của v1 (model-design.md §9).

### Vòng 3 — Sẵn sàng dev

- [ ] Có danh sách tệp sẽ tạo/sửa, với tên lớp/hàm và chữ ký.
- [ ] Shape tensor nêu rõ ở mỗi ranh giới (batch, seq_len, d).
- [ ] Lệnh chạy cụ thể cho từng bước (prepare / train / tune / evaluate) và thời gian ước tính trên RTX 3050 4GB.
- [ ] Kế hoạch test liệt kê test nào, kiểm AC nào.
- [ ] Phụ thuộc thư viện có version; thứ tự thực hiện rõ (bước nào trước).
- [ ] Không còn Blocker / Major mở; Open Questions còn lại không chặn bước code đầu tiên.

## Chế độ code

### Vòng 1 — Khớp spec
- [ ] Mỗi AC của spec có test hoặc bằng chứng chạy; đánh dấu đạt/không.
- [ ] Khoá config, tên tham số, công thức khớp spec; chỗ lệch đã có Decision Log và đã được người dùng duyệt.

### Vòng 2 — Đúng đắn
- [ ] Test leakage (L1, L2) có và qua; test overfit một lô qua.
- [ ] Không còn số hard-code trong `src/` (trừ hằng toán học).
- [ ] Seed và tái lập: chạy smoke hai lần ra cùng `metrics.json`.

### Vòng 3 — Chạy được & bàn giao
- [ ] `pytest` toàn bộ qua; smoke đầu-cuối qua; dán số liệu thật của lần chạy.
- [ ] Lệnh trong BA doc § Cách chạy chạy được nguyên văn.
- [ ] BA doc, Decision Log, Version History đã cập nhật.

## Chấm mức sẵn sàng

| Kết luận | Điều kiện |
|---|---|
| ✅ **READY** | 0 Blocker, 0 Major mở |
| 🟡 **READY có điều kiện** | 0 Blocker, ≤ 2 Major mở và mỗi Major đã thành Open Question chờ người dùng |
| ❌ **NOT READY** | Còn Blocker, hoặc > 2 Major |

Điểm từng vòng = 10 − 3×Blocker − 1×Major − 0.25×Minor (sàn 0), tính trên phát hiện **còn mở** sau vòng.

## Mẫu ghi kết quả (dán vào cuối spec, § Review readiness, hoặc vào báo cáo code)

```markdown
## Review readiness — v{X.Y} — {ngày}

| Vòng | Lăng kính | Blocker | Major | Minor | Đã sửa cơ học | Điểm |
|---|---|---|---|---|---|---|
| 1 | Đầy đủ & truy vết | 0 | 1 | 2 | 2 | 9.0 |
| 2 | Đúng đắn khoa học | 0 | 0 | 1 | 1 | 10.0 |
| 3 | Sẵn sàng dev | 0 | 0 | 0 | 0 | 10.0 |

**Kết luận: 🟡 READY có điều kiện** — chờ OQ-03.

| # | Vòng | Mức | Phát hiện | Xử lý |
|---|---|---|---|---|
| R1-01 | 1 | Major | §5 thiếu khoảng tune của `k_G` | → OQ-03 |
| R1-02 | 1 | Minor | AC-04 trỏ sai mục | đã sửa |
```
