---
name: insider-threat-model-dev
description: Code framework và mô hình phát hiện insider threat theo đề cương nghiên cứu của người dùng (anomaly detection trên CERT, 2 luồng chuỗi hành vi + đặc trưng hành vi, chuẩn hành vi 3 tầng Personal–Group–Global, ngưỡng thích ứng, RQ1–RQ3) theo quy trình spec → người dùng duyệt → code → tài liệu BA + Decision Log, có review 3 vòng mức ready-to-dev và luôn hỏi lại kèm 3 đề xuất thay vì tự quyết; code xong thì cập nhật Google Doc "Luồng hoạt động" bằng ngôn ngữ BA dễ hiểu. Dùng skill này mỗi khi người dùng muốn code, sửa, refactor, train, tune tham số (Optuna), chạy thí nghiệm / ablation, đánh giá, hay viết spec cho bất kỳ phần nào của mô hình hoặc pipeline insider threat — kể cả khi chỉ nói ngắn như "code luồng chuỗi", "train lại feature AE", "tinh chỉnh k_P", "chạy ablation RQ2", "sửa ngưỡng", "xử lý dữ liệu CERT", "làm tiếp model", "fix bug train". Không dùng để viết văn bản paper (lit review, introduction) không kèm code.
---

# Insider Threat Model Dev

Skill này biến đề cương nghiên cứu thành code chạy được, chuẩn khoa học, và luôn có tài liệu đi kèm. Ba lời hứa với người dùng:

1. **Không code khi chưa có spec được duyệt.** Người dùng là người chịu trách nhiệm kết quả nghiên cứu; một quyết định thiết kế lọt vào code mà họ không biết có thể làm sai kết luận của cả paper.
2. **Không tự quyết thay người dùng.** Gặp chỗ phải chọn hướng thì hỏi, kèm **3 phương án** và một khuyến nghị có lý do.
3. **Mọi thay đổi đều để lại dấu vết** trong tài liệu BA và Decision Log, để sau này viết phần Method / bảo vệ được từng lựa chọn.

## Tài nguyên

| Tệp | Đọc khi |
|---|---|
| [references/research-proposal.md](references/research-proposal.md) | Lần đầu kích hoạt trong phiên; khi viết mục Mục tiêu của spec |
| [references/model-design.md](references/model-design.md) | Viết spec cho bất kỳ thành phần C1–C7; có bảng quyết định D-01 → D-12 cần hỏi |
| [references/cert-dataset.md](references/cert-dataset.md) | Spec / code chạm dữ liệu, nhãn, chia tập; bẫy leakage L1–L8 |
| [references/tuning-protocol.md](references/tuning-protocol.md) | Spec / code có train, tune, chọn α, k, p, W |
| [references/engineering-standards.md](references/engineering-standards.md) | Trước khi code: cấu trúc project, config, test bắt buộc, môi trường |
| [references/review-rounds.md](references/review-rounds.md) | Review 3 vòng (chế độ spec và chế độ code) |
| [templates/spec-template.md](templates/spec-template.md) | Tạo spec mới |
| [templates/ba-doc-template.md](templates/ba-doc-template.md) | Tạo tài liệu BA lần đầu |
| [references/ba-writing-style.md](references/ba-writing-style.md) | Viết tài liệu BA và Google Doc (Bước 7, 8) — văn phong BA rút từ skill `ba-prd` |
| [templates/google-doc-template.md](templates/google-doc-template.md) | Dựng nội dung Google Doc "Luồng hoạt động" (Bước 8) |
| [references/gdoc-setup.md](references/gdoc-setup.md) · `scripts/push_gdoc.py` · `scripts/gdoc_webapp.gs` | Đẩy Google Doc qua Apps Script (Bước 8): thiết lập một lần, lệnh đẩy, lỗi thường gặp |

Vị trí trong project (gốc `D:\AI for BA\MW\Framework-rework\`): spec ở `specs/SPEC-NNN-<slug>.md`, tài liệu BA ở `docs/BA-insider-threat-detection.md`.

Mọi tin nhắn cho người dùng viết **tiếng Việt có dấu**; thuật ngữ, ID, tên tham số giữ nguyên.

## Quy trình

### Bước 0 — Nạp bối cảnh

1. Đọc `docs/BA-insider-threat-detection.md`. **Chưa có thì tạo ngay** từ template (đây là tài liệu, không phải code, nên không cần chờ duyệt), điền phần đã biết, ghi Version History 0.1.
2. Đọc Decision Log và Open Questions trong tài liệu BA — quyết định đã chốt ở đó **ghi đè** mặc định trong `model-design.md`; không hỏi lại điều đã chốt.
3. Đọc các spec liên quan và code hiện có của thành phần sắp làm.
4. Phân loại yêu cầu:

| Loại | Ví dụ | Đi tiếp |
|---|---|---|
| A. Thành phần / tính năng mới, đổi thiết kế, đổi tham số, đổi dữ liệu / chỉ số | "code luồng chuỗi", "thêm tầng Group", "đổi W thành 30" | Bước 1 → 7 đầy đủ |
| B. Sửa lỗi đưa code về đúng spec đã duyệt, không đổi hành vi đã định | test hỏng, crash, sai shape | **Spec rút gọn** trong chat (lỗi gì, sửa ở đâu, ảnh hưởng gì, test nào chứng minh) → chờ duyệt → Bước 5–7 |
| C. Hỏi / giải thích / đọc kết quả | "vì sao FPR cao?" | Trả lời; nếu câu trả lời dẫn tới việc phải sửa thì chuyển sang A hoặc B |

Chạy tune dài, mở test, cài thư viện, xoá dữ liệu cũng là hành động phải hỏi trước dù thuộc loại nào.

### Bước 1 — Chốt câu hỏi mở trước khi viết spec

Liệt kê những quyết định spec cần mà chưa có trong Decision Log (lấy từ bảng D-xx của `model-design.md` và từ những gì người dùng chưa nói). Hỏi theo **mẫu hỏi** bên dưới, chờ trả lời, rồi ghi mỗi câu trả lời thành một dòng Decision Log.

Câu nhỏ không ảnh hưởng kết quả (tên biến nội bộ, cách tách hàm) thì tự chọn theo `engineering-standards.md`, không hỏi. Ranh giới: nếu lựa chọn có thể làm đổi một con số trong bảng kết quả, hoặc đổi điều người đọc paper hiểu về phương pháp → phải hỏi.

### Bước 2 — Viết spec

Tạo `specs/SPEC-NNN-<slug>.md` từ template (NNN tăng dần, không dùng lại). Viết đủ để một người không đọc cuộc trò chuyện vẫn code đúng: công thức, shape, khoá config, chữ ký hàm, AC kiểm được, lệnh chạy, ước tính thời gian trên RTX 3050 4GB. Mỗi thành phần trích dẫn về đề cương và về D-xx / DL-xxx tương ứng.

Spec cho một thành phần nên vừa một lần duyệt (thường 1–2 thành phần C*). Việc lớn (ví dụ "code cả framework") thì đề xuất chia nhiều spec theo thứ tự phụ thuộc C1 → C7, hỏi người dùng thứ tự, rồi làm từng spec.

### Bước 3 — Review 3 vòng (chế độ spec)

Theo `references/review-rounds.md`: Vòng 1 đầy đủ & truy vết → Vòng 2 đúng đắn khoa học → Vòng 3 sẵn sàng dev. Mỗi vòng đọc lại tệp từ đĩa, chỉ dùng lăng kính của vòng đó.

- Phát hiện sửa cơ học → sửa ngay, ghi "đã sửa".
- Phát hiện cần chọn hướng → **không tự sửa**, thành Open Question kèm 3 phương án.

Ghi bảng kết quả + kết luận READY / READY có điều kiện / NOT READY vào § 13 của spec.

### Bước 4 — Trình spec và dừng

Gửi người dùng:

1. Đường dẫn spec (link markdown).
2. Tóm tắt 5–10 dòng: làm gì, thiết kế chính, tham số chính, tệp sẽ tạo, AC.
3. Bảng review 3 vòng và kết luận.
4. Open Questions còn mở — hỏi theo mẫu hỏi.
5. Câu chốt: *"Bạn duyệt spec này (accept) thì tôi mới bắt đầu code."*

**Dừng ở đây.** Chỉ coi là duyệt khi người dùng nói rõ (accept, duyệt, ok code đi, triển khai đi…). Im lặng, khen, hay hỏi thêm không phải là duyệt. Người dùng góp ý → sửa spec, tăng version (0.1 → 0.2), chạy lại ít nhất các vòng review bị ảnh hưởng, trình lại.

Khi duyệt: đổi `status: Accepted`, `version: 1.0`; ghi Decision Log `Duyệt SPEC-NNN v1.0`; cập nhật bảng Trạng thái thành phần.

### Bước 5 — Code

Chỉ code đúng phạm vi spec đã duyệt, theo `engineering-standards.md`:

- Mọi tham số qua config; code trích mục spec ở chỗ cài công thức (`# SPEC-003 §4.2`).
- Viết test cùng lúc với code: test của AC, test leakage nếu chạm dữ liệu / chuẩn / ngưỡng, test overfit một lô cho mô hình.
- Chạy `pytest` và smoke trên tập con; đọc kết quả thật, không đoán.

**Nếu trong lúc code phát hiện spec sai, thiếu, hay không khả thi** (shape không khớp, VRAM không đủ, dữ liệu khác mô tả): dừng phần bị ảnh hưởng, hỏi người dùng theo mẫu hỏi, cập nhật spec (version phụ, ví dụ 1.1) + Decision Log sau khi có câu trả lời. Không lách bằng một giải pháp tự chọn rồi báo sau — đó chính là kiểu quyết định ngầm làm lệch kết quả nghiên cứu mà skill này tồn tại để ngăn.

### Bước 6 — Review 3 vòng (chế độ code)

Theo `references/review-rounds.md`: khớp spec → đúng đắn → chạy được & bàn giao. Dán số liệu thật (số test qua, thời gian smoke, metrics của run).

### Bước 7 — Cập nhật tài liệu BA

Mỗi lần code xong (kể cả sửa lỗi loại B), viết theo [references/ba-writing-style.md](references/ba-writing-style.md):

- § Trạng thái thành phần, § Thành phần (tệp, tham số đang dùng), § Cách chạy (lệnh đã chạy được), § Thí nghiệm & kết quả (nếu có run).
- **Decision Log**: một dòng cho mỗi thay đổi — quyết định in đậm, lý do, phương án bị loại, ngày. Sửa lỗi cũng ghi (lỗi gì, vì sao sửa cách này).
- Version History: tăng version, một dòng tóm tắt, trỏ SPEC / DL.
- Open Questions đã trả lời → chuyển vào Decision Log rồi **xoá dòng** khỏi bảng (sửa chỗ trỏ tới nó trước; không đánh số lại các câu còn lại).

### Bước 8 — Cập nhật Google Doc "Luồng hoạt động"

**Chỉ chạy khi code đã hoàn thành**: review chế độ code ở Bước 6 ra READY và Bước 7 xong. Không đẩy khi đang viết spec, đang code dở, hay test còn fail.

1. **Viết bản local trước**: `docs/luong-hoat-dong.md`, dựng theo [templates/google-doc-template.md](templates/google-doc-template.md) và [references/ba-writing-style.md](references/ba-writing-style.md). Mô tả theo code thật và run thật, không chép từ spec; mọi con số lấy từ `configs/` và `runs/<id>/metrics.json`. Chạy § 10 Tự kiểm của văn phong.
2. **Đọc comment trước khi đẩy**: Drive `read_file_content` (doc ID ở dòng `Google Doc` trong `CLAUDE.md`, `includeComments: true`). Lần đẩy ghi đè cả tab đầu tiên nên comment sẽ mất neo — liệt kê mọi comment cho người dùng như góp ý, không tự sửa theo.
3. **Đẩy** từ gốc project: `python .claude/skills/insider-threat-model-dev/scripts/push_gdoc.py docs/luong-hoat-dong.md`. Script đọc `.env` (`GDOC_WEBAPP_URL`, `GDOC_SECRET`), gửi lên Apps Script web app gắn vào Doc, web app ghi đè tab đầu tiên; link Doc giữ nguyên. Thiết lập và lỗi thường gặp: [references/gdoc-setup.md](references/gdoc-setup.md).
   - Thiếu `.env` / `GDOC_WEBAPP_URL`, hoặc `--ping` không ra `ok` → **dừng và hỏi**: A người dùng thiết lập Apps Script theo `gdoc-setup.md` (khuyến nghị) · B bật connector Google Docs và sửa Doc qua connector (nạp skill `anthropic-skills:google-workspace` trước) · C để lần sau, chỉ giữ bản local.
4. **Kiểm lại**: đọc lại Doc bằng Drive `read_file_content`, đối chiếu tiêu đề các mục và các con số với `docs/luong-hoat-dong.md`. Script trả `ok` chưa đủ để báo xong.
5. Ghi một dòng Version History trong tài liệu BA: "Đẩy Google Doc bản X.Y".

Báo cáo cuối cho người dùng: đã làm gì, tệp nào, kết quả test / run (số thật), DL mới, link Google Doc + mục đã cập nhật, việc còn mở, đề xuất bước kế tiếp (kèm 3 phương án nếu có nhiều hướng).

## Mẫu hỏi

Mỗi câu hỏi là **một mục riêng** — không gộp nhiều quyết định vào một câu. Mỗi câu có đúng 3 phương án, phương án khuyến nghị đứng đầu.

Có công cụ `AskUserQuestion` thì dùng nó (tối đa 4 câu mỗi lần, mỗi câu 3 option, option đầu gắn "(Recommended)", mô tả nêu hệ quả). Không có thì viết:

```markdown
**OQ-07 — Cách chọn α khi hợp nhất hai luồng** (chặn: SPEC-004 §4.1)
Bối cảnh: e_f và e_s đã chuẩn hoá robust z trên train; α quyết định luồng nào nặng hơn.

| | Phương án | Được | Mất |
|---|---|---|---|
| **A (khuyến nghị)** | Cố định 0.5 + phân tích độ nhạy α | Đơn giản, dễ bảo vệ, không dùng nhãn | Có thể không tối ưu |
| B | Cân phương sai hai luồng trên val | Không nhãn, thích ứng dữ liệu | Thêm một bước phải giải thích |
| C | Gating học được | Linh hoạt nhất | Khó huấn luyện không nhãn, dễ suy biến |

Khuyến nghị A vì …
```

Đánh số OQ liên tục trong toàn project (theo bảng Open Questions của tài liệu BA), không bắt đầu lại ở mỗi spec.

## Những điều dễ sai

- Coi "người dùng chưa phản đối" là duyệt → code sớm. Chỉ duyệt khi có lời rõ ràng.
- Tự điền một mặc định "hợp lý" cho D-xx chưa chốt mà không hỏi. Mặc định trong `model-design.md` là **đề xuất để hỏi**, không phải quyết định.
- Quên Decision Log khi sửa nhỏ. Mọi thay đổi code đều có một dòng.
- Báo "đã chạy ổn" mà không có số liệu. Luôn dán kết quả thật; test fail thì nói fail kèm output.
- Mở test để "xem thử" rồi chỉnh tham số — làm mất giá trị kết quả. Mở test là sự kiện phải hỏi và ghi lại (`tuning-protocol.md` §1.5).
- Google Doc viết như spec kỹ thuật (shape tensor, tên hàm, công thức dày đặc). Người đọc Doc không đọc code: viết hệ thống làm gì, có số liệu, trỏ `SPEC-NNN` cho chi tiết.
