# Ghép LDAP vào dữ liệu feature và sequence đã tiền xử lý

Phạm vi SPEC-001 v1.1: thêm phòng ban/chức vụ đúng tháng vào bộ Parquet; giữ nguyên dữ liệu hành vi. Không tạo feature mới, chia lại split, huấn luyện hoặc tính anomaly score.

## Dữ liệu vào và output

- Input: `data/processed/CERT-r4.2-processed-two-branch-v1/`.
- LDAP: `D:/CERT_r4.2/LDAP/YYYY-MM.csv`.
- Output mới: `data/processed/CERT-r4.2-processed-two-branch-v1-ldap/`.

Output có cùng ba nhánh và tên bucket như input: user_day_features, user_day_features_ocean, user_day_sequences. Mỗi bảng giữ cột gốc theo đúng thứ tự rồi thêm:

| Cột mới | Nội dung |
|---|---|
| role | Chức vụ theo LDAP của đúng tháng day; UNKNOWN nếu thiếu |
| department | Phòng ban theo LDAP của đúng tháng day; UNKNOWN nếu thiếu |
| role_missing | true khi không có chức vụ hợp lệ |
| department_missing | true khi không có phòng ban hợp lệ |
| ldap_month | Tháng tra cứu, dạng YYYY-MM |

Một nhân viên có nhiều sự kiện sequence trong ngày nhận cùng metadata của tháng đó; số dòng và event_index không đổi. Metadata không được thêm vào vector f001–f100 hoặc token như một feature mới. f100 và các mask được giữ nguyên, không tính lại thâm niên chức vụ.

## Cách chạy

Đường dẫn trong config được hiểu từ thư mục chạy; thực hiện tại gốc project. Dùng môi trường Python3.11 với requirements-ldap.txt; không cần cài lại nếu môi trường đã có đủ dependency.

```powershell
.\.venv-validation311\Scripts\python.exe scripts/enrich_preprocessed_ldap.py --config configs/experiments/enrich_ldap.json
```

Pipeline từ chối output đã tồn tại. Để chạy lần khác, sửa paths.output_root thành đường dẫn mới; không xóa hoặc ghi đè dữ liệu đã có. Không chọn output nằm trong input/LDAP hoặc làm thư mục cha của các nguồn này.

## Kiểm chứng

Sau mỗi file ghi, pipeline đọc lại tất cả các cột gốc và so sánh giá trị, dtype, thứ tự, null; kiểm metadata và khóa/index. Trước công bố output hoàn chỉnh, nó kiểm tập user-day của cả ba nhánh giống nhau và hash nguồn/LDAP không thay đổi trong lần chạy.

manifest.json trong output ghi số row/user-day, missing theo row và user-day, schema trước/sau, hash từng file, môi trường và thời gian. Số thiếu ở sequence theo row có thể lớn hơn feature do một user-day có nhiều sự kiện; so độ phủ bằng missing_user_days.

Test:

```powershell
.\.venv-validation311\Scripts\python.exe -m pytest tests/test_enrich_ldap.py -q
```

Implementation ở src/itd/data/enrich_ldap.py; CLI ở scripts/enrich_preprocessed_ldap.py. Code đóng gói bên trong bộ dataset không bị sửa hoặc chạy.

Khi chuyển sang SPEC-002, runner phải nhận dữ liệu đã ghép thay vì ghép metadata thêm lần nữa; bản chọn một tầng Personal → Group → Global vẫn là phần việc riêng chưa hoàn thành trong bước này.

## Lần chạy đã hoàn thành

Ngày 2026-11-11, 21 test qua trong 13.81s. Run thật hoàn tất trong 296.898194s; 64 file mỗi nhánh, tổng 192 Parquet đã đọc lại đối soát.

| Nhánh | Số dòng | Role thiếu theo row | Department thiếu theo row |
|---|---:|---:|---:|
| Feature | 330.452 | 1.793 | 6.637 |
| Feature + OCEAN | 330.452 | 1.793 | 6.637 |
| Sequence | 12.523.202 | 70.165 | 300.323 |

Ba nhánh cùng 330.452 user-day; Role thiếu 1.793, Department thiếu 6.637 user-day. SHA-256 nguồn khớp kiểm kê trước và sau join; các cột gốc không đổi. Manifest nằm trong output. Bằng chứng: runs/20261111-spec001-ldap-enrichment/verification.json và log.txt.
