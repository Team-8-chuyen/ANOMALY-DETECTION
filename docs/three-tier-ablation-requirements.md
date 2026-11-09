# Yêu cầu ba tầng và ablation Group — 2026-11-07

Trạng thái: SPEC-002 v1.0 đã duyệt và triển khai theo DL-027–DL-030; 101 test toàn project qua. Dữ liệu thật chờ OQ-02/OQ-03.

| Thành phần | Case 1 | Case 2 |
|---|---|---|
| Global | Toàn tổ chức | Toàn tổ chức |
| Group | LDAP department | LDAP role |
| Personal | Lịch sử riêng [t-30 ngày,t) | Giống Case 1 |
| Backoff | Kết hợp theo độ tin cậy | Cùng công thức và tham số |
| Score | Một score mỗi user-day | Một score mỗi user-day |
| Threshold | Một ngưỡng cuối từ Calibration | Cùng nguyên tắc hiệu chỉnh |

Hai case dùng cùng user-day, features, temporal split và chính sách xử lý dữ liệu. Không loại riêng mẫu thiếu metadata; cần backoff khi Group thiếu. Role và Department thay thế nhau trong cùng tầng Group. Cùng quy tắc Calibration không đòi hỏi cùng giá trị threshold: mỗi case có phân phối score riêng.

Tính xong mọi score ngày t trước khi cập nhật lịch sử ngày t. Calibration không dùng nhãn theo DL-002. Test giữ threshold đã lưu. Nếu tune backoff, phải xác định protocol tách phần tune khỏi Calibration cuối trước khi chạy. OQ-02/OQ-03 còn chặn chạy thật. Hai case phục vụ ablation Group của RQ2; threshold cố định sau Calibration chưa phải ngưỡng cập nhật thời gian của RQ3.

| Tham số | Đã chốt |
|---|---|
| Transformation và scale floor | Raw count, max(std,1) |
| k_P,k_G,min_days,min_users | 7,3,2,2 |

Đã triển khai score mean positive z, pseudo-count, Global/Group cố định và Personal trượt, threshold p99 Calibration. Đây là mô hình thống kê feature, chưa thay thế RQ1 hai luồng. Phân vị 99% không bảo đảm FPR=1% trên test. Artifact và bằng chứng nằm trong runs/20261107-spec002-smoke.
