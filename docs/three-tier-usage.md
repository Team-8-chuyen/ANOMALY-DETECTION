# Chạy kiến trúc ba tầng — SPEC-002

Bản đối chiếu yêu cầu, sơ đồ và bằng chứng kiểm chứng: [Nghiệm thu kỹ thuật SPEC-002](spec002-acceptance.md).

Hướng dẫn đọc từng cột và ví dụ từ output thực tế: [Cách đọc kết quả ba tầng](three-tier-output-guide.md).

Phạm vi: dữ liệu user-day đã có → Global/Group/Personal → Adaptive Backoff → score cuối → threshold Calibration. Không cần chạy lại các script preprocessing để sử dụng các file feature đã chuẩn bị.

## Hai cấu hình

| Case | File | Group |
|---|---|---|
| Global–Department–Personal | configs/experiments/group_department.json | department trong LDAP đúng tháng |
| Global–Role–Personal | configs/experiments/group_role.json | role trong LDAP đúng tháng |

Cả hai kế thừa `configs/experiments/group_ablation_common.json`, chỉ khác group_key. Common đã điền đường dẫn CERT trên máy hiện tại theo cấu hình từng chạy thành công. Khi chuyển máy, sửa paths trong common.

Đầu vào gồm user_id, date và sáu count: logon_count, logoff_count, device_count, file_count, email_count, http_count. LDAP theo tháng có user_id, department, role. Đầu vào phải là dữ liệu đã chuẩn bị; runner không trích xuất raw log và không tự lọc nhãn độc hại. Chính sách train sạch đã được kiểm ở lần chạy CERT hiện tại: không có user-day độc hại trong train.

## Logic đang dùng

- Global và Group: mean/std từ train, giữ cố định.
- Personal: mean/std từ lịch sử [t−30 ngày,t); chấm ngày t trước khi thêm ngày t vào lịch sử. Không thêm ngày không hoạt động thành dòng zero.
- Mỗi tầng: trung bình phần dương của `(count−mean)/max(std,1)`.
- Personal có n ngày: wP=n/(n+7) khi n≥2; ngược lại 0.
- Group có m nhân viên riêng biệt trong train: rG=m/(m+3) khi nhóm hợp lệ và m≥2; ngược lại 0.
- wG=(1−wP)rG; wGlobal=1−wP−wG. Score cuối là tổng score tầng nhân trọng số tương ứng.
- Mỗi case có threshold riêng bằng p99 linear của score Calibration; cảnh báo khi score > threshold. Đây là cùng quy tắc hiệu chỉnh, không buộc hai case có cùng giá trị threshold.

## Chạy train và Calibration

Từ thư mục gốc project, dùng run-dir mới chưa tồn tại:

```powershell
.\.venv-validation311\Scripts\python.exe scripts/run_group_ablation.py --config configs/experiments/group_department.json --config configs/experiments/group_role.json --run-dir runs/20261109-three-tier-calibration
```

Mặc định không đọc hoặc chấm test. Không thêm `--include-test` khi chưa có yêu cầu đánh giá test mới. Split đã chốt: train 01–05/2010, Calibration 06–09/2010, test 10/2010–05/2011. Runner kiểm thứ tự và không giao nhau; đường dẫn phải trỏ đúng các split đã chuẩn bị.

Output có hai thư mục department/role, mỗi thư mục lưu baselines.json, calibration_scores.csv, threshold.json và history_after_calibration.json. Run chung lưu config/manifest, hash đầu vào, môi trường, log và metric. Không ghi đè run cũ.

Đổi dữ liệu/feature sau này cần fit lại baseline, lịch sử và Calibration trong run mới. Không tái sử dụng threshold cũ cho dữ liệu đã thay đổi.

## Kiểm thử phần mềm

```powershell
.\.venv-validation311\Scripts\python.exe -m pytest -q
```

Code chính: src/itd/scoring/tiers.py, src/itd/scoring/threshold.py và scripts/run_group_ablation.py. Ghép LDAP/validation là code hỗ trợ. SPEC-003 đã rút khỏi phạm vi; không cần triển khai để chạy hai case.
