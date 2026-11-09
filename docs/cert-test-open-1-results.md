# Kết quả test lần 1 — hai case ba tầng — 2026-11-07

Cập nhật audit: toàn bộ 7.323 sự kiện đáp án đã khớp raw theo nguồn/ID/user/timestamp; feature, lịch sử, score và metric đã đối soát độc lập. Kết quả test giữ nguyên. Chi tiết: `docs/label-pipeline-audit.md`; các ghi chú chưa đối soát ID bên dưới ghi nhận giới hạn tại thời điểm đánh giá ban đầu, đã được audit này giải quyết.

## Cấu hình đã đóng băng

- Người dùng accept mở test lần 1, ghi DL-036 trước khi chạy.
- Nạp baselines.json và history_after_calibration.json từ `runs/20261107-cert-first-calibration/result`.
- Giữ toàn bộ tham số SPEC-002 và threshold Calibration: Department 0.8423588864100263; Role 0.8115505803240236.
- Không refit Global/Group, không tính lại threshold. Personal tiếp tục cập nhật sau từng ngày theo protocol đã duyệt.
- Test có 141.215 user-day, từ 2010-10-01 đến 2011-05-17: 515 dương và 140.700 âm theo đáp án.

## Kết quả ở mức user-day

| Metric | Global–Department–Personal | Global–Role–Personal |
|---|---:|---:|
| Average Precision (AP, PR-AUC không nội suy hình thang) | 0.039175 | 0.075425 |
| ROC-AUC | 0.897202 | 0.933485 |
| Precision | 6.1314% | 9.6824% |
| Recall | 16.3107% | 24.2718% |
| F1 | 0.089125 | 0.138427 |
| FPR | 0.9140% | 0.8287% |
| TP | 84 | 125 |
| FP | 1.286 | 1.166 |
| FN | 431 | 390 |
| TN | 139.414 | 139.534 |
| Tổng cảnh báo | 1.370 | 1.291 |

Role có metric quan sát tốt hơn Department trên split và cấu hình này. Role vẫn bỏ sót 390/515 user-day dương và có 1.166 cảnh báo sai; đây chưa phải chất lượng phát hiện cao. Chưa có kiểm định thống kê để khái quát rằng định nghĩa Role luôn tốt hơn Department. Thuật toán hiện tại là baseline thống kê feature, chưa phải mô hình hai luồng RQ1.

## Recall theo kịch bản

| Kịch bản | User-day dương trong test | Department phát hiện | Role phát hiện |
|---|---:|---:|---:|
| 1 | 40 | 9 (22.50%) | 10 (25.00%) |
| 2 | 457 | 69 (15.10%) | 109 (23.85%) |
| 3 | 18 | 6 (33.33%) | 6 (33.33%) |

Đơn vị là user-day có sự kiện của kịch bản, không phải số incident hoặc số insider được phát hiện.

## Định nghĩa nhãn và metric

- Nhãn dương khi (user,date) xuất hiện trong ít nhất một sự kiện của các file đáp án r4.2-1/2/3; user lấy từ sự kiện, không gán mọi ngày của insider là dương.
- Các file đáp án đã xác minh checksum và mọi khóa user-day có trong processed; chưa đối soát từng event ID với raw log. Kết quả phụ thuộc tính đúng của processed và cách ánh xạ nhãn này.
- AP tính trên precision/recall tại các ngưỡng score phân biệt; điểm bằng nhau được gộp trước khi tính.
- ROC-AUC được đối soát độc lập bằng đếm cặp positive/negative theo score, cho điểm bằng nhau trọng số 0.5.
- Precision=TP/(TP+FP); Recall=TP/(TP+FN); F1=2TP/(2TP+FP+FN); FPR=FP/(FP+TN).
- Trước chạy đã kiểm công thức ranking bằng ví dụ perfect/reversed/tied. Sau chạy đã đối soát AP, AUC, confusion totals và threshold với output đã lưu.
- Hai case có cùng tập user-day và nhãn; score hữu hạn, tổng trọng số bằng 1. Hash các artifact baseline/history/threshold nguồn không thay đổi.

## Bằng chứng chạy

- Run: `runs/20261107-cert-test-open-1`.
- `metrics.json`: số chính xác và recall từng kịch bản.
- `manifest.json`: cấu hình nguồn, hash input và artifact đóng băng, phương pháp metric, giới hạn nhãn.
- `metric-checks.json`: đối soát tính toán.
- `department/test_scores.csv`, `role/test_scores.csv`: score thành phần, trọng số, threshold, cờ cảnh báo và nhãn từng user-day.
- Thời gian chấm cả hai case và tạo kết quả: 31.522163 giây (không gồm đối soát bổ sung).

Lần mở test nghiên cứu hiện là 1. Kết quả này được giữ nguyên làm mốc; mọi thay đổi thiết kế sau khi xem test phải ghi rõ tính chất exploratory và lần mở test tiếp theo, không coi test này là dữ liệu chưa nhìn thấy.
