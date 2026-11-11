# Kiểm kê Parquet và chuẩn bị ghép LDAP

Ngày 2026-11-11. Chỉ kiểm kê dữ liệu và chuẩn bị thiết kế; chưa sinh dataset đã ghép LDAP, chưa chạy mô hình/chấm score hoặc dùng nhãn đánh giá.

Nguồn: `data/processed/CERT-r4.2-processed-two-branch-v1/`. LDAP tham chiếu: `D:/CERT_r4.2/LDAP/`. Đã cài PyArrow19.0.1 trong môi trường kiểm tra Python3.11 sau approval công cụ; không chạy code đóng gói trong dataset.

## Kết quả đọc toàn bộ dữ liệu

| Nhánh | File Parquet | Số dòng | Khóa user/day riêng biệt |
|---|---:|---:|---:|
| user_day_features | 64 | 330.452 | 330.452 |
| user_day_features_ocean | 64 | 330.452 | 330.452 |
| user_day_sequences | 64 | 12.523.202 | 330.452 |

Ba nhánh cùng tập khóa, không có khóa thừa/thiếu giữa nhánh; 1.000 nhân viên, từ 2010-01-02 đến 2011-05-17. Với mốc split đã dùng trước đây, số user-day là train 105.171, Calibration 84.066, test 141.215. Đây là đếm theo ngày, chưa ghi file split mới.

Feature: user:string, day:timestamp[ns], f001–f100:double, m001–m100:bool. Biến thể OCEAN thêm O/C/E/A/N:int64. Sequence: user/day/event_index cùng 24 thuộc tính và attribute_mask:string. Chưa có role/department trong schema các nhánh.

Đã quét đầy đủ các cột: không có null hoặc giá trị float NaN/Inf. Schema nhất quán giữa các bucket trong từng nhánh. Không có user rỗng/thừa khoảng trắng, ngày khác mốc 00:00:00, feature key trùng. Sequence user-day không xuất hiện thành nhiều đoạn/bucket; event_index bắt đầu 0 và liên tục theo thứ tự vật lý.

`f100` có giá trị khác 0 ở toàn bộ 330.452 dòng; m100 đều true trong cả hai bảng feature. Điều này xác nhận dữ liệu có giá trị cho cột, không xác nhận công thức days_in_current_role đúng với lịch sử nhân sự. Bước join mới bảo toàn cột này.

## Độ phủ LDAP

18 file tháng, 16.743 khóa user/tháng; không có khóa trùng sau strip. Số thiếu bên dưới đếm theo unique user-day, giống nhau ở ba nhánh; không phải số row sequence:

| Metadata | User-day thiếu/rỗng/UNKNOWN khi tra đúng tháng |
|---|---:|
| role | 1.793 |
| department | 6.637 |

Đề xuất theo quy tắc join đã dùng: giữ row, ghi UNKNOWN và cờ missing riêng mỗi trường, không lấy thông tin tháng khác. Metadata nằm ngoài feature/token; không dùng các cờ thiếu như tín hiệu insider.

## Bằng chứng và giới hạn

Script kiểm kê và JSON chứa schema, SHA-256 từng Parquet, row/key/null/nonfinite/index/mask counts và LDAP coverage: `runs/20261111-parquet-inventory/audit.py`, `inventory.json`. Lượt quét Arrow hoàn tất trong 122.300771 giây; lượt đầu chuyển nhiều dữ liệu sang Python chậm đã dừng và thay bằng lượt kiểm đầy đủ tối ưu này.

Kiểm kê này không xác minh lại logic sinh 100 feature, giá trị token, nội dung JSON attribute_mask, tính đúng lịch sử của f100 hoặc toàn bộ preprocessing so với raw. Không kiểm nhãn, không chọn model/threshold. Chưa đối chiếu từng giá trị chung giữa bảng feature và OCEAN; bước ghép sẽ kiểm bảo toàn từng nguồn riêng.

## Thiết kế cần duyệt

[SPEC-001 v1.1 §14](../specs/SPEC-001-role-baseline-validation.md) đề xuất thêm role, department, role_missing, department_missing và ldap_month vào cả ba nhánh, output mới có hậu tố -ldap; giữ nguyên số dòng, thứ tự, kiểu dữ liệu và giá trị gốc, đọc lại để đối soát trước công bố output. Chưa có code join Parquet hoặc output mới. Việc chọn tầng và cách tính score thuộc SPEC-002, không chặn thiết kế metadata này.
