# Chạy bộ chọn một tầng — SPEC-002 v1.2

Phiên bản hiện tại dùng dữ liệu đã ghép LDAP để chọn duy nhất Personal, Group hoặc Global. Hai case chỉ đổi định nghĩa Group: Department/Role. Điểm sẽ do mô hình hoặc bên cung cấp bên ngoài gửi vào; bộ chọn không tự tính score hoặc threshold.

## Quy tắc

```text
Personal có ít nhất 7 ngày hoạt động trong [t−30,t)?
  Có: chọn Personal và dừng.
  Không: Group hợp lệ có ít nhất 2 nhân viên riêng biệt trong train?
    Có: chọn Group.
    Không: chọn Global.
```

Mỗi user-day có một tầng duy nhất. Ngày đang chấm chỉ vào history sau khi xử lý xong toàn ngày; không thêm ngày không hoạt động thành zero. Group membership cố định từ train. Thiếu score của tầng đã chọn không làm đổi tầng.

## Chạy routing-only

Chạy từ thư mục gốc project, chọn run-dir chưa tồn tại:

```powershell
.\.venv-validation311\Scripts\python.exe scripts/run_tier_routing.py --config configs/experiments/tier_routing_department.json --config configs/experiments/tier_routing_role.json --run-dir runs/<new-routing-run>
```

Common config: configs/experiments/tier_routing_common.json. Đầu vào mặc định là nhánh user_day_features của bộ CERT-r4.2-processed-two-branch-v1-ldap. Runner chỉ đọc user/day và bốn trường metadata/flag, không đọc 100 feature, mask, sequence hoặc nhãn.

Train 01–05/2010 để lập membership và khởi tạo history; routing trên Calibration 06–09/2010. Ngày ngoài hai khoảng chỉ được đếm là ngoài phạm vi, không dùng cho routing. File bucket chứa các ngày test nhưng không có xử lý score hoặc đánh giá test trong runner này. Không có cờ --include-test.

## Output

department/routes.csv và role/routes.csv cùng tập user-day theo thứ tự. Các cột:

| Cột | Ý nghĩa |
|---|---|
| user, day | Nhân viên/ngày |
| group_key, group_value | Case và metadata Group của tháng hiện tại |
| selected_tier | personal, group hoặc global |
| fallback_reason | Lý do chọn/dừng/fallback |
| n_personal_days | Số ngày hoạt động trước t trong cửa sổ 30 ngày |
| n_group_users | Số người Group trong train; để trống khi Personal đủ nên không xét Group |
| score | Trống khi chưa có điểm ngoài; không dùng số 0 thay cho điểm thiếu |
| score_status | awaiting_external_score hoặc provided |

Run chung lưu config.json, manifest.json, metrics.json, group_members.json, history_after_calibration.json, env.txt, git.txt và log.txt. Metrics là thống kê chọn tầng, không phải hiệu quả phát hiện. Không có threshold/is_alert trong output này.

## Nhận điểm ngoài khi đã có

Bên cung cấp đọc routing, tính một điểm cho đúng tầng được chọn rồi gửi CSV đúng năm cột:

```csv
user,day,group_key,selected_tier,score
U_EXAMPLE,2020-02-01,department,personal,-0.5
U_EXAMPLE,2020-02-01,role,personal,-0.5
```

Ví dụ trên là synthetic. File thật phải đủ mọi user-day ở cả hai case, không chỉ hai dòng ví dụ. Chạy thêm:

```powershell
.\.venv-validation311\Scripts\python.exe scripts/run_tier_routing.py --config configs/experiments/tier_routing_department.json --config configs/experiments/tier_routing_role.json --run-dir runs/<new-scored-run> --scores <selected-layer-scores.csv>
```

Điểm phải hữu hạn, đúng user/day/case/tầng, không thiếu/trùng/thừa. Personal hoặc Global chung giữa hai case phải có cùng điểm theo hợp đồng cùng producer/phiên bản/định nghĩa. Giá trị được giữ nguyên, không ép vào [0,1] hoặc tự chuẩn hóa. Thiếu điểm báo lỗi và không công bố run dở.

Điểm nhận vào chưa chứng minh cùng thang giữa các tầng hoặc sẵn sàng Calibration. Nếu nhóm cung cấp raw error mô hình, phép chuẩn hóa theo tầng phải được thiết kế riêng trước khi hiệu chỉnh threshold/so sánh hiệu quả.

## Kết quả chạy thật đã kiểm tra

Run: runs/20261111-spec002-tier-routing, 6.723866 giây. Mỗi case có 84.066 user-day Calibration:

| Case | Personal | Group | Global | Thiếu metadata Group |
|---|---:|---:|---:|---:|
| Department | 84.066 | 0 | 0 | 1.665 |
| Role | 84.066 | 0 | 0 | 461 |

Đối soát độc lập bằng đếm ngày với bisect xác nhận mọi row có 19–30 ngày lịch sử, đều vượt điều kiện 7 ngày. Thiếu metadata không ảnh hưởng trường hợp Personal đủ. Tất cả score để trống đúng hợp đồng.

**Calibration hiện tại không có cold-start cần Group/Global, nên không cho phép kết luận Department hay Role tốt hơn.** Các nhánh Group/Global được kiểm bằng fixture, gồm trường hợp cùng user-day Department chọn Group nhưng Role phải về Global. Không tự thay tham số hoặc mở test để tạo khác biệt giữa hai case.

## Kiểm thử và code

```powershell
.\.venv-validation311\Scripts\python.exe -m pytest tests/test_routing.py tests/test_score_input.py tests/test_tier_routing_cli.py tests/test_enrich_ldap.py -q
```

151 test qua trong 12.91 giây, gồm 21 test bảo vệ bước ghép LDAP. Bằng chứng: runs/20261111-spec002-routing-validation/pytest.xml và verification.json. Code chính: src/itd/scoring/routing.py, src/itd/scoring/score_input.py và scripts/run_tier_routing.py.

Phiên bản trộn score cũ tại commit 7331adf và các threshold cũ chỉ là lịch sử, không dùng làm output phương pháp chọn một tầng hiện tại.
