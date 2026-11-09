# Cách đọc kết quả ba tầng

Các ví dụ dưới đây lấy từ `runs/20261109-three-tier-calibration`, không chạy hoặc đánh giá test mới. Chọn dòng đầu theo ngày/nhân viên thỏa điều kiện cả hai case không cảnh báo, rồi dòng đầu cả hai case cảnh báo. Đây là ví dụ giải thích cách tính, không phải cách chọn case tốt hơn.

## 1. Mở file nào?

Trong thư mục run, mở `department/calibration_scores.csv` và `role/calibration_scores.csv`. Mỗi dòng là một nhân viên trong một ngày. Hai file cùng tập user-day; so sánh bằng user_id và date.

| Cột | Ý nghĩa |
|---|---|
| user_id, date | Nhân viên và ngày được chấm |
| group_key, group_value | Định nghĩa Group và nhóm thực tế trong tháng đó |
| n_history | Số ngày hoạt động trước ngày đang chấm, nằm trong cửa sổ 30 ngày |
| n_group_users | Số nhân viên riêng biệt thuộc nhóm trong train |
| s_global, s_group, s_personal | Mức lệch tăng hoạt động so với từng chuẩn; lớn hơn là lệch nhiều hơn |
| w_global, w_group, w_personal | Trọng số kết hợp; tổng bằng 1 |
| score | Score cuối sau kết hợp |
| threshold | Ngưỡng cuối của case, hiệu chỉnh từ Calibration |
| is_alert | 1 khi score > threshold; 0 khi không vượt ngưỡng |

Score không phải xác suất độc hại và không bị giới hạn ở 1. is_alert=1 là tín hiệu cần xem xét, không phải nhãn xác nhận insider. is_alert=0 cũng không chứng minh ngày đó an toàn.

## 2. Ví dụ không vượt ngưỡng

Nhân viên **AAE0190**, ngày **2010-06-01**. Các số hiển thị làm tròn; file CSV giữ đầy đủ độ chính xác.

| Giá trị | Department | Role |
|---|---:|---:|
| Nhóm | 1 - Purchasing | Manager |
| n_history | 20 | 20 |
| n_group_users | 6 | 24 |
| s_global | 0.358771 | 0.358771 |
| s_group | 0.672295 | 0.057572 |
| s_personal | 0.057591 | 0.057591 |
| w_global | 0.086420 | 0.028807 |
| w_group | 0.172840 | 0.230453 |
| w_personal | 0.740741 | 0.740741 |
| score | 0.189864 | 0.066263 |
| threshold | 0.842359 | 0.811551 |
| is_alert | 0 | 0 |

Với Department, nhân viên có 20 ngày lịch sử nên wPersonal=20/(20+7)=0.740741. Nhóm có 6 người nên độ tin cậy nhóm rGroup=6/(6+3)=0.666667. Phần trọng số còn lại sau Personal phân cho Group và Global:

```text
wGroup  = (1 − 0.740741) × 0.666667 ≈ 0.172840
wGlobal = 1 − wPersonal − wGroup ≈ 0.086420
score   = wGlobal × sGlobal + wGroup × sGroup + wPersonal × sPersonal
        ≈ 0.189864 < 0.842359 → không cảnh báo
```

Global và Personal giống nhau giữa hai case vì cùng dữ liệu và cùng nhân viên. Group khác nhau nên score Group, cỡ nhóm và phân bổ phần trọng số còn lại khác nhau. Hai threshold cũng có thể khác vì được hiệu chỉnh riêng trên phân phối score Calibration mỗi case.

## 3. Ví dụ vượt ngưỡng

Nhân viên **BJM0111**, ngày **2010-06-01**:

| Giá trị | Department | Role |
|---|---:|---:|
| Nhóm | 3 - Engineering | Technician |
| n_history | 25 | 25 |
| n_group_users | 129 | 157 |
| s_global | 1.740509 | 1.740509 |
| s_group | 1.628323 | 2.089306 |
| s_personal | 0.718728 | 0.718728 |
| w_global | 0.004972 | 0.004102 |
| w_group | 0.213778 | 0.214648 |
| w_personal | 0.781250 | 0.781250 |
| score | 0.918259 | 1.017111 |
| threshold | 0.842359 | 0.811551 |
| is_alert | 1 | 1 |

Cả hai case cảnh báo vì score cuối vượt threshold tương ứng. Không cần từng score tầng cùng vượt một ngưỡng; hệ thống chỉ ra quyết định sau kết hợp. Ví dụ này không đối chiếu nhãn độc hại, không kết luận nhân viên là insider.

## 4. Đọc các trường hợp ít dữ liệu

Các tình huống sau giải thích quy tắc, không phải dòng ví dụ đã trích ở trên:

- Personal dưới 2 ngày: w_personal=0, s_personal để trống; Group/Global đảm nhận phần kết hợp.
- Group không có baseline train hoặc dưới 2 người: w_group=0, s_group để trống; Personal/Global tiếp tục chấm.
- Cả Personal và Group không đủ dữ liệu: w_global=1, score=s_global.
- Nhân viên đổi phòng ban/chức vụ: dùng Group đúng tháng hiện tại, vẫn giữ lịch sử Personal của chính người đó.

Ô trống của score tầng không khả dụng không có nghĩa score bằng 0. Cờ thiếu Group không làm loại dòng khỏi phép so sánh hai case.

## 5. Đọc Calibration đúng mục đích

Threshold mỗi case là p99 linear trên toàn bộ score Calibration. Cờ cảnh báo trong calibration_scores.csv được thêm sau khi đã tính threshold, là kết quả nhìn lại Calibration. 841 cảnh báo trên 84.066 dòng mỗi case không phải số false positive; muốn xác định đúng/sai phải đối chiếu nhãn trong protocol đánh giá đã duyệt.

Giá trị ở đây giải thích hành vi phiên bản sáu count hiện tại. Không dùng hai dòng minh họa để chọn case hoặc đổi threshold. Xem [hướng dẫn chạy](three-tier-usage.md) và [bản nghiệm thu kỹ thuật](spec002-acceptance.md) để đối chiếu phạm vi, test và giới hạn.
