# Audit nhãn và đánh giá — 2026-11-07

## Kết luận

Chưa phát hiện sai lệch trong phạm vi đã đối soát: sự kiện đáp án khớp raw, sáu feature khớp dữ liệu gốc, baseline khớp train, lịch sử Personal và score khớp công thức đã duyệt, metric khớp tính độc lập. Kết quả test lần 1 được giữ nguyên. Audit chỉ đọc nguồn và artifact; không refit, không đổi threshold hoặc lựa chọn mô hình.

## 1. Nhãn đáp án khớp sự kiện gốc

| Nguồn | Dòng sự kiện raw đã quét | Sự kiện đáp án | Khớp ID + user + timestamp đúng nguồn |
|---|---:|---:|---:|
| Logon | 854.859 | 198 | 198 |
| Device | 405.380 | 2.785 | 2.785 |
| File | 445.581 | 10 | 10 |
| Email | 2.629.979 | 470 | 470 |
| HTTP | 28.434.423 | 3.860 | 3.860 |
| Tổng | 32.770.222 | 7.323 | 7.323 |

- Mọi ID đáp án tìm thấy đúng một lần trong nguồn tương ứng; số ID thiếu, ID đích trùng và user/timestamp sai đều bằng 0.
- Không có xung đột tuple user/time giữa các mục đáp án cùng nguồn và ID.
- Đọc prefix sự kiện từ raw theo các trường CSV đầu (id,date,user) để tránh giữ content lớn trong RAM; không có dòng sai định dạng prefix/activity được phát hiện.
- Từ các sự kiện này tạo được 986 user-day dương, trong đó 515 thuộc test. Nhãn đã lưu trong cả hai test_scores.csv khớp ánh xạ này ở mọi dòng, số mismatch=0.
- Master có 70 tài khoản actor; các sự kiện có 72 tài khoản. Hai tài khoản ngoài master xuất hiện trong 50 sự kiện kịch bản 3 (20 logon, 30 email). Giữ nhãn theo tài khoản của sự kiện như protocol hiện tại, không đổi thành tài khoản đứng tên incident.

## 2. Bảng sáu feature khớp raw log

- Tính lại logon_count/logoff_count từ activity tương ứng, device_count từ cả Connect/Disconnect, và file/email/http_count từ số dòng sự kiện.
- Số user-day tính lại: 330.452; khớp đúng 330.452 user-day trong user_day_features.csv.
- Số khóa thiếu/thừa và số user-day khác giá trị đều bằng 0. Mỗi feature có 0 mismatch.
- Điều này xác nhận cách đếm hiện tại, không khẳng định sáu count đủ biểu diễn mọi hành vi độc hại. device_count vẫn mang nghĩa số sự kiện thiết bị, không phải riêng số lần cắm USB.

## 3. Baseline và trạng thái nối Calibration/test khớp nguồn

- Tính lại mean/std Global và từng Group từ 105.171 dòng train cho cả hai case; mọi thống kê khớp artifact đã lưu.
- n_users Group khớp số user riêng biệt, không nhầm với user-day.
- Checkpoint Personal cuối Calibration khớp lịch sử feature nguồn; ngày cuối là 2010-09-30.
- Dựng lịch sử từng user độc lập từ feature train/Calibration/test, không gọi hàm score_days. Kiểm tra cửa sổ trước ngày t, n_history, trọng số và score trên 225.281 user-day Calibration+test, tổng 450.562 dòng output của hai case.
- Không có mismatch ở n_history, trọng số, score tầng, score cuối, threshold, quy tắc cảnh báo hoặc checkpoint cuối test. Chênh lệch số thực tuyệt đối lớn nhất của score là 8.881784197001252e-16.
- Checkpoint cuối ngày có thể chứa cả ngày vừa chấm; khi chấm ngày kế tiếp, cửa sổ được prune trước tính score. Đây là thứ tự đúng theo spec.
- Hash baseline, lịch sử cuối Calibration và threshold nguồn vẫn khớp manifest trước mở test. Không có refit Global/Group hoặc hiệu chỉnh threshold bằng test trong các artifact đã kiểm tra.

## 4. Metric đã được tính lại độc lập

- Đối soát TP/FP/FN/TN, Precision, Recall, F1 và FPR từ cờ cảnh báo/nhãn đã lưu.
- AP gộp các score bằng nhau rồi tính precision theo bước tăng recall; ROC-AUC được tính bằng đếm cặp positive/negative, tie nhận trọng số 0.5.
- Mọi metric khớp kết quả công bố; chênh lệch tối đa là 1.1102230246251565e-16 do số thực.

| Metric giữ nguyên | Department | Role |
|---|---:|---:|
| AP | 0.039175 | 0.075425 |
| Precision | 6.13% | 9.68% |
| Recall | 16.31% | 24.27% |
| FPR | 0.9140% | 0.8287% |

## 5. Những giới hạn còn lại

- Kiểm tra này xác nhận tính nhất quán với đáp án CERT và công thức hiện tại, không chứng minh sự kiện ngoài đáp án đều thực sự lành tính.
- Score chỉ lấy độ lệch tăng của sáu count; mô hình không biểu diễn trực tiếp ngoài giờ, máy lạ, đích email/URL, trình tự hoặc quan hệ ngữ cảnh.
- Mean/std nhạy outlier; Global/Group cố định, Personal cập nhật mọi quan sát theo thiết kế đã duyệt. Đây là lựa chọn mô hình, không phải lỗi phát hiện trong audit.
- Chưa có kiểm định để khẳng định Role luôn tốt hơn Department. Không chọn lại tham số bằng kết quả audit/test.
- Test đã được xem ở lần 1; cải tiến sau đó cần protocol đánh giá được ghi nhận rõ, không xem test này là holdout chưa từng nhìn thấy.

## 6. Bằng chứng

Thư mục `runs/20261107-label-pipeline-audit/`:

- raw-audit.json: đối soát ID, metadata sự kiện và sáu feature.
- baseline-and-label-checks.json: baseline train, Group size, nhãn test và checkpoint Calibration.
- pipeline-audit.json: lịch sử, score, weight và checkpoint cuối trên toàn bộ Calibration/test.
- independent-metric-audit.json: metric tính lại và hash bảng score.
- account-label-audit.json: phân biệt tài khoản actor và tài khoản trong sự kiện.

Quét raw và tính lại feature mất 104.517 giây; đối soát lịch sử/score độc lập mất 132.701 giây. Đây là audit cùng kết quả đóng băng, không phải một lần mở test để thử cấu hình mới. Lần mở test nghiên cứu vẫn là 1.
