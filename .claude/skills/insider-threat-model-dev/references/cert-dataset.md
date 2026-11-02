# CERT Insider Threat Dataset — ghi chú cho code

Con số dưới đây là giá trị thường gặp trong tài liệu; khi code luôn **đếm lại từ dữ liệu thật** (số user, số insider, khoảng ngày) và ghi con số thực vào tài liệu BA. Lệch so với bảng này thì tin dữ liệu, ghi chú lại.

## Phiên bản

| Bản | Quy mô (tham khảo) | Ghi chú |
|---|---|---|
| r4.2 | ~1000 user, ~70 insider, kịch bản 1–3, ~17 tháng | Bản được dùng nhiều nhất trong paper — dễ so sánh |
| r5.2 | ~2000 user, kịch bản 1–4 | Có thêm cột hoạt động ở một số tệp |
| r6.2 | ~4000 user, rất ít insider (mỗi kịch bản 1 người) | Có `activity`, `to_removable_media`… ở file/email/http |

## Tệp và cột chính (r4.2)

| Tệp | Cột | Lưu ý |
|---|---|---|
| `logon.csv` | id, date, user, pc, activity (Logon/Logoff) | |
| `device.csv` | id, date, user, pc, activity (Connect/Disconnect) | |
| `file.csv` | id, date, user, pc, filename, content | r4.2 không có cột activity; đuôi file lấy từ `filename` |
| `email.csv` | id, date, user, pc, to, cc, bcc, from, size, attachments, content | external = domain người nhận khác domain tổ chức |
| `http.csv` | id, date, user, pc, url, content | **Rất lớn (cỡ chục GB)** — đọc theo chunk, chỉ giữ cột cần, ghi parquet |
| `psychometric.csv` | employee_name, user_id, O, C, E, A, N | Chỉ dùng nếu spec chọn |
| `LDAP/YYYY-MM.csv` | employee_name, user_id, email, role, business_unit, functional_unit, department, team, supervisor | Ảnh chụp theo tháng → lấy nhóm theo tháng tương ứng |
| `answers/insiders.csv` | dataset, scenario, details, user, start, end | Bộ đáp án tải riêng |
| `answers/r4.2-<k>/*.csv` | các dòng log độc hại của từng insider | Nhãn user-day lấy từ đây (khớp theo `id` sự kiện) |

`date` dạng `MM/DD/YYYY HH:MM:SS` — parse với format tường minh, không để pandas đoán.

## Kịch bản r4.2 (tóm tắt)

1. User trước đó không dùng USB, không làm ngoài giờ, bắt đầu logon ngoài giờ, dùng USB, tải dữ liệu lên wikileaks, rồi nghỉ việc. → bất thường về **trình tự / ngữ cảnh** (luồng chuỗi).
2. User lướt các trang tuyển dụng, liên hệ đối thủ; trước khi nghỉ dùng USB với tần suất cao hơn hẳn trước đó để lấy dữ liệu. → bất thường về **cường độ** (luồng đặc trưng, chuẩn cá nhân).
3. Quản trị hệ thống bất mãn tải keylogger, dùng USB chép sang máy cấp trên, hôm sau đăng nhập bằng tài khoản cấp trên gửi email gây hoảng loạn, rồi nghỉ. → **vai trò đặc thù** (tầng Group), logon vào PC lạ.

Recall theo từng kịch bản phải báo cáo riêng.

## Bẫy leakage — kiểm từng mục trong spec và trong test

| # | Bẫy | Cách chặn |
|---|---|---|
| L1 | Scaler / vocab / median-IQR fit trên toàn bộ dữ liệu | Fit chỉ trên train; test unit kiểm đối tượng fit chỉ thấy ngày train |
| L2 | Chuẩn cá nhân / nhóm dùng ngày tương lai | Cửa sổ `[t−W, t)`; test: đổi dữ liệu sau t không làm đổi điểm tại t |
| L3 | Dùng việc user biến mất khỏi LDAP (nghỉ việc) làm đặc trưng | Insider ở cả 3 kịch bản đều nghỉ sau sự cố → lộ nhãn. Cấm đặc trưng "sắp nghỉ", "số ngày còn lại" |
| L4 | Chia ngẫu nhiên theo user-day | Chia theo thời gian; ngày liền kề rò rỉ thông tin qua cửa sổ |
| L5 | Chọn α, p, k, ngưỡng bằng nhãn test | Mọi tham số chọn trên val không nhãn (xem tuning-protocol.md); test chỉ mở một lần |
| L6 | Đọc giới hạn số dòng (v1: 200k) | Đọc đủ, theo chunk; ghi số dòng thực đã đọc vào log |
| L7 | Từ khoá domain nguy hiểm chọn bằng cách nhìn log của insider | Danh sách domain/từ khoá phải lập trước, từ mô tả kịch bản công khai, ghi vào Decision Log |
| L8 | Lọc user ít log chỉ ở test | Quy tắc lọc áp như nhau cho mọi tập, ghi số user bị loại |
