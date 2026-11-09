# Lần chạy train và Calibration CERT đầu tiên — 2026-11-07

Cập nhật sau báo cáo này: người dùng đã duyệt mở test lần 1; kết quả nằm ở `docs/cert-test-open-1-results.md`. Các ghi chú test deferred bên dưới mô tả trạng thái tại lần chạy train/Calibration, không phải trạng thái hiện tại.

## Cấu hình đã được chốt

- Giữ split hiện tại: train 2010-01-01 → 2010-05-31; Calibration 2010-06-01 → 2010-09-30; test dự kiến 2010-10-01 → 2011-05-31.
- Loại user-day độc hại khỏi train theo đáp án. Kiểm kê hiện tại tìm được 0 user-day độc hại trong train, nên giữ nguyên 105.171 dòng.
- Hai case dùng cùng sáu feature raw count, scale floor=1; Global/Group cố định từ train, Personal trượt [t-30,t).
- k_P=7 ngày, k_G=3 người; Personal tối thiểu 2 ngày, Group tối thiểu 2 người; p99 Calibration, linear, cảnh báo khi score>threshold.
- Đây là mô hình thống kê SPEC-002, không phải hai mô hình học sâu của RQ1.

## Kiểm kê nhãn phục vụ chính sách dữ liệu

| Tập | User-day tổng | User-day có sự kiện độc hại trong đáp án |
|---|---:|---:|
| Train | 105.171 | 0 |
| Calibration | 84.066 | 471 |
| Test dự kiến | 141.215 | 515 |

Master insiders.csv ghi 70 incident/70 user cho dataset 4.2. Các file sự kiện chi tiết có 7.323 sự kiện, 986 user-day và 72 tài khoản xuất hiện trong sự kiện. Không đồng nhất 72 tài khoản với 72 insider; một sự kiện có thể mang tài khoản khác người trong master. Đợt này đã kiểm schema và khớp user-day với processed, chưa đối soát ID từng sự kiện với raw log hoặc xây evaluator nhãn. Nhãn Calibration/test chỉ dùng thống kê kiểm kê, không dùng chọn tham số/threshold hay báo metric phát hiện.

Calibration giữ nguyên tất cả các dòng, bao gồm các ngày có sự kiện độc hại. Ngưỡng là phân vị không nhãn theo cấu hình đã chọn; chưa đưa nhãn vào tính score hoặc hiệu chỉnh p.

## Kết quả chạy thật

| Case | Dòng train | Dòng Calibration | Threshold | Cảnh báo Calibration |
|---|---:|---:|---:|---:|
| Global–Department–Personal | 105.171 | 84.066 | 0.8423588864100263 | 841 |
| Global–Role–Personal | 105.171 | 84.066 | 0.8115505803240236 | 841 |

- Thời gian runner: 26.898015 giây, CPU; không dùng GPU hoặc tune.
- Hai config chỉ khác group_key; output chứa cùng user-day theo cùng thứ tự.
- Mọi score và trọng số hữu hạn; tổng trọng số từng dòng bằng 1 trong sai số số thực.
- Threshold kiểm lại khớp NumPy p99 linear. Calibration alerts chỉ là thống kê trên tập dùng hiệu chỉnh, không phải kết quả held-out.
- Test vẫn deferred; không có test_scores.csv và chưa chạy đánh giá nhãn. Chưa kết luận case nào tốt hơn.

## Bằng chứng và lệnh chạy

- Run: `runs/20261107-cert-first-calibration/result/`.
- Kiểm tra kết quả: `runs/20261107-cert-first-calibration/verification.json`.
- Chính sách train: `runs/20261107-cert-first-calibration/train-policy-verification.json`.
- Kiểm kê nhãn: `runs/20261107-cert-label-audit/summary.json`.

```powershell
.\.venv-validation311\Scripts\python.exe scripts/run_group_ablation.py --config runs/20261107-cert-first-calibration/setup/department.json --config runs/20261107-cert-first-calibration/setup/role.json --run-dir runs/20261107-cert-first-calibration/result
```

Lệnh trên đã chạy thành công; khi chạy lại phải đổi run-dir sang thư mục mới. Chưa thêm --include-test. Mỗi case có baselines.json, calibration_scores.csv, threshold.json và history_after_calibration.json để kiểm tra trước bước test.
