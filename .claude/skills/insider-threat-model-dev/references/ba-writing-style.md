# Văn phong BA cho tài liệu luồng hoạt động

Áp cho Google Doc "Luồng hoạt động" (Bước 8) và cho tài liệu BA local. Rút từ chuẩn viết của skill `ba-prd` (`references/prd-format.md` § Writing Quality Standard, § Writing Style; `quality-standard.md` QS-STY), chỉnh cho việc mô tả **code đang làm gì** thay vì mô tả tính năng sẽ build.

## 1. Hợp đồng người đọc

| Người đọc | Lấy gì ra | Ràng buộc lên cách viết |
|---|---|---|
| **Người không đọc code** *(chính)* — giảng viên hướng dẫn, hội đồng, thành viên nhóm | Hệ thống làm gì, theo thứ tự nào, dựa trên số liệu nào | Mỗi bước hiểu được mà không cần mở code. Thuật ngữ kỹ thuật giải thích một lần ở § Thuật ngữ |
| **Người viết paper** (chính bạn) | Mô tả phương pháp chép được sang phần Method | Có số liệu thật: tham số, số user, kết quả |
| **Người sửa code sau này** | Bước nào nằm ở tệp nào | Mỗi bước có cột tệp code; chi tiết kỹ thuật ở spec, chỉ trỏ tới |

Khi phải chọn giữa "đủ chi tiết kỹ thuật" và "dễ hiểu cho người không đọc code" → **chọn dễ hiểu**. Chi tiết kỹ thuật đã có ở spec; Google Doc trỏ `SPEC-NNN` thay vì chép lại.

## 2. Mỗi dòng là một câu đầy đủ

Một dòng mô tả bước hoặc quy tắc xử lý phải tự đứng được, gồm:

1. **Chủ ngữ cụ thể** — `Hệ thống`, tên bước, tên mô hình, tên tệp dữ liệu.
2. **Hành động** — đọc, đếm, tính, so sánh, gắn cờ.
3. **Kết quả có số** — ngưỡng, số ngày, số đặc trưng, giá trị tham số đang dùng.
4. **Điều kiện** (nếu có) — khi nào quy tắc áp dụng.

| ❌ Cụt / mơ hồ | ✅ Đủ ý |
|---|---|
| "Chuẩn hoá dữ liệu." | "Hệ thống gom log của 5 nguồn (đăng nhập, USB, file, email, web) thành một bảng sự kiện, mỗi dòng là một thao tác của một người dùng." |
| "Tính điểm bất thường." | "Mỗi người dùng mỗi ngày nhận một điểm bất thường; điểm càng cao thì hành vi ngày đó càng khác thói quen." |
| "Dùng ngưỡng thích ứng." | "Hệ thống cảnh báo khi điểm của một ngày vượt ngưỡng riêng của người đó; ngưỡng tính lại mỗi 7 ngày từ 60 ngày gần nhất." |
| "Trọng số tầng tự điều chỉnh." | "Người dùng có dưới 10 ngày lịch sử được so chủ yếu với nhóm cùng vai trò; càng nhiều ngày lịch sử, hệ thống càng dựa vào thói quen của chính người đó." |

## 3. Trần độ dài

- **1 dòng = 1 ý.** Hai việc độc lập → hai dòng.
- **≤ 2 câu một dòng, mỗi câu ≤ ~25 từ**, không lồng quá một mệnh đề phụ.
- **Tổng quan ≤ ~150 từ.** Ngoài Tổng quan → bảng hoặc bullet, không đoạn văn.
- Không câu dẫn trước bảng ("Dưới đây là…", "Phần này mô tả…"). Không viết lại bằng lời điều bảng đã nói.
- Ngoại lệ: danh sách giá trị, thứ tự bước được dài hơn trần.

## 4. Quy tắc ≠ lý do — phép thử xóa câu

Mô tả luồng nói **hệ thống làm gì**. Lý do vì sao chọn cách đó thuộc **Decision Log**.

> Xóa mệnh đề này đi, người đọc có hiểu sai hệ thống đang làm gì không?
> Có → giữ. Không → cắt; nếu lý do sẽ bị hỏi lại (hội đồng, giảng viên) thì ghi Decision Log và gắn `(→ DL-nnn)`.

| ❌ Lẫn lý do | ✅ Chỉ mô tả | → Decision Log |
|---|---|---|
| "Hệ thống chia dữ liệu theo thời gian **vì chia ngẫu nhiên sẽ làm rò rỉ thông tin giữa các ngày liền kề và cho kết quả đẹp giả**." | "Hệ thống chia dữ liệu theo thời gian: 60% số ngày đầu để học, 15% kế tiếp để chọn tham số, 25% cuối để đánh giá (→ DL-004)." | DL-004: chia theo thời gian, loại chia ngẫu nhiên vì rò rỉ giữa ngày liền kề |

## 5. Câu chữ

| Không viết | Viết |
|---|---|
| "Điểm sẽ được tính bởi mô hình…" *(bị động, tương lai)* | "Mô hình tính điểm…" *(chủ động, hiện tại)* |
| "Nó có thể được điều chỉnh" | "Người chạy đổi giá trị này trong `configs/base.yaml`" |
| "Về cơ bản", "Nói cách khác", "Như đã đề cập" | *(bỏ)* |
| "Cần đảm bảo rằng hệ thống thực hiện việc kiểm tra" | "Hệ thống kiểm tra…" |

Chủ ngữ luôn cụ thể; không dùng "nó", "cái này", "họ" khi không rõ trỏ gì.

## 6. Từ ngữ cụ thể, không tự đặt khái niệm

Mỗi danh từ phải chỉ ra được: một bước, một tệp, một mô hình, một tham số, một chỉ số. Không dùng khái niệm tự đặt kiểu "lớp xử lý", "bề mặt dữ liệu", "đường đi tín hiệu" để gộp nhiều thứ — viết thẳng những thứ cụ thể đó.

Thuật ngữ chuyên môn thật (autoencoder, attention, PR-AUC, phân vị) được dùng, nhưng **giải thích một lần** ở § Thuật ngữ bằng một câu đời thường, rồi dùng nguyên văn.

## 7. Không viết dạng phủ định

Mô tả cái hệ thống **làm**. Muốn nói phạm vi thì đóng khung khẳng định: "Hệ thống chỉ dùng 5 nguồn log: …" thay cho liệt kê "không dùng psychometric, không dùng LDAP…". Thứ đã cân nhắc rồi bỏ → Decision Log kèm lý do.

## 8. Tiêu đề là câu khẳng định

Mỗi tiêu đề bước / nhóm là **một câu nói ra điều chính** của phần đó, không phải nhãn cụt, không phải câu hỏi.

| ❌ | ✅ |
|---|---|
| "Bước 3 — Luồng chuỗi" | "Bước 3 — Mô hình chuỗi chấm điểm mức bất thường về trình tự thao tác trong ngày" |
| "Ngưỡng cảnh báo thế nào?" | "Bước 6 — Mỗi người dùng có ngưỡng cảnh báo riêng, cập nhật mỗi 7 ngày" |

## 9. Một sự thật viết một lần

Mỗi giá trị (tham số, số liệu, kết quả) nằm ở đúng một mục; chỗ khác trỏ tới mục đó. Tham số nằm ở § Tham số đang dùng; mô tả bước chỉ nhắc tên tham số dễ hiểu, kèm giá trị khi cần cho câu đủ ý.

## 10. Tự kiểm trước khi đẩy lên Google Doc

1. Người không đọc code đọc riêng từng dòng có hiểu không?
2. Dòng nào thiếu chủ ngữ, hành động hoặc con số?
3. Dòng nào gộp hai ý, hoặc dài quá 2 câu?
4. Mệnh đề nào trượt phép thử xóa câu?
5. Thuật ngữ nào chưa có trong § Thuật ngữ?
6. Mọi con số khớp code và run thật (`configs/`, `runs/<id>/metrics.json`) chưa?
