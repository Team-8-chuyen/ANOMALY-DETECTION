# Phát hiện Insider Threat — Luồng hoạt động của hệ thống

Cập nhật 2026-11-12 · Bản 0.31 · Bộ chọn một tầng và pilot Isolation Forest + LSTM đã triển khai

## 1. Tổng quan

**Hiện trạng:** dữ liệu đã ghép LDAP tại §12, bộ chọn Personal → Group → Global tại §13 và pilot Feature Isolation Forest / Sequence LSTM Autoencoder tại §14. Pilot tạo hai điểm thô riêng trên cùng mẫu validation. Hợp nhất/chuẩn tầng/threshold và đánh giá hai case là bước phát triển tiếp theo.

Phạm vi hiện tại gồm SPEC-001/002 và pilot hai model theo SPEC-004 được người dùng duyệt. Department và Role tiếp tục là hai định nghĩa thay thế của cùng tầng Group. Các mục2–11 lưu lịch sử thiết kế thống kê cũ; người đọc dùng §12–14 cho code hiện hành.

Lịch sử: phiên bản thống kê cũ từng chạy train/Calibration/test với score trộn và ngưỡng Calibration đóng băng. Kết quả đó thuộc phương pháp cũ, được lưu cùng các mục2–11; kết quả pilot hai model mới nằm ở §14.

## 2. Hệ thống ghép chức vụ trước khi tính thống kê

| Tầng hoặc bước | Case 1 | Case 2 |
|---|---|---|
| Global | Thống kê hành vi toàn tổ chức từ train | Giống Case 1 |
| Group | Thống kê theo department trong LDAP | Thống kê theo role trong LDAP |
| Personal | Lịch sử hành vi riêng của từng người | Giống Case 1 |
| Kết hợp | Adaptive Backoff tạo một score cuối | Cùng công thức và tham số |
| Ngưỡng | Một threshold từ score Calibration của Case 1 | Một threshold từ score Calibration của Case 2 |

Role và Department là hai định nghĩa thay thế của tầng Group. Hai case có cùng dữ liệu, feature và mốc chia tập.

| Bước | Hệ thống làm gì | Đầu vào | Đầu ra | Tệp code |
|---|---|---|---|---|
| 1 | Hệ thống kiểm tra bảng nhân sự từng tháng và bảng sáu đặc trưng của từng người mỗi ngày. | LDAP và feature CSV | Các dòng hợp lệ hoặc thông báo lỗi | src/itd/data/ldap.py |
| 2 | Hệ thống gắn chức vụ đúng tháng cho từng dòng hoạt động. | Dữ liệu hợp lệ | CSV thêm role và role_missing | scripts/attach_roles.py |
| 3 | Hàm thống kê kiểm tra đầu vào rồi tính trung bình và độ lệch chuẩn cho toàn tổ chức hoặc từng chức vụ. | Ma trận và chức vụ | Mean/std cho mỗi đặc trưng | src/itd/scoring/baseline.py |
| 4 | Hệ thống ghép cả phòng ban và chức vụ theo tháng, giữ nguyên các dòng thiếu thông tin nhóm. | Feature CSV và LDAP | Hai trường nhóm và cờ thiếu | src/itd/data/ldap.py |
| 5 | Hệ thống tính score so với toàn tổ chức, nhóm và lịch sử riêng, rồi kết hợp theo độ tin cậy. | Train và từng ngày cần chấm | Score tầng, trọng số và score cuối | src/itd/scoring/tiers.py |
| 6 | Hệ thống lấy phân vị Calibration để tạo ngưỡng cuối riêng cho từng cấu hình. | Score Calibration | Threshold và cờ cảnh báo | src/itd/scoring/threshold.py |
| 7 | Runner kiểm tra hai cấu hình dùng chung dữ liệu và lưu kết quả vào hai thư mục riêng. | Config Department/Role | Artifact của từng case | scripts/run_group_ablation.py |

## 3. Hệ thống dừng khi dữ liệu không đáp ứng hợp đồng

| Quy tắc | Xử lý |
|---|---|
| Nhân sự theo tháng | Hệ thống tra chức vụ theo user và tháng của ngày hoạt động. |
| Thiếu chức vụ | Hệ thống gắn UNKNOWN và role_missing=1 cho dòng thiếu chức vụ. |
| Dữ liệu sai | Hệ thống báo lỗi khi ngày sai, khóa trùng, thiếu cột hoặc giá trị đếm không hữu hạn/âm. |
| Baseline | Hàm tính toán yêu cầu ma trận hai chiều có ít nhất một dòng và một đặc trưng. |
| Nhóm chức vụ | Hàm thống kê bỏ qua chức vụ rỗng và UNKNOWN. |
| Ghi kết quả | CLI kiểm tra dữ liệu trước khi ghi và yêu cầu --overwrite để thay output có sẵn. |
| Lịch sử cá nhân | Hệ thống chỉ dùng các ngày trước ngày đang chấm và cập nhật sau khi chấm xong cả ngày. |
| Backoff | Nhân viên mới hoặc nhóm ít người nhận trọng số lớn hơn từ tầng toàn tổ chức. |
| So sánh hai case | Runner giữ cùng feature, tập mẫu và công thức; hai case chỉ đổi phòng ban thành chức vụ. |
| Test | Runner mặc định chỉ fit train và Calibration; --include-test mới mở tập test. |

Spec: SPEC-001 và SPEC-002 v1.0 · Quyết định triển khai mới: DL-027 → DL-030.

### 3.1. Mỗi ngày nhận một điểm so với từng tầng

| Bước | Quy tắc |
|---|---|
| Đầu vào | Mỗi user-day có số logon, logoff, sự kiện thiết bị, file, email và HTTP. |
| Chuẩn hành vi | Global và Group lưu trung bình, độ lệch chuẩn từ train. Personal tính thống kê từ lịch sử trước ngày đang chấm. |
| Score tầng | Hệ thống chuẩn hóa độ lệch từng feature, giữ phần tăng và lấy trung bình sáu feature. |
| Mẫu số | Hệ thống dùng max(std,1) để xử lý feature hằng hoặc độ lệch chuẩn nhỏ. |
| Score cuối | Hệ thống cộng score ba tầng theo các trọng số không âm có tổng bằng 1. |

### 3.2. Backoff chuyển trọng số về tầng có đủ dữ liệu

| Tình huống | Hệ thống xử lý |
|---|---|
| Personal đủ lịch sử | Trọng số Personal tăng dần theo số ngày hoạt động của người đó. |
| Personal thiếu lịch sử | Hệ thống dành trọng số cho Group và Global. |
| Group đủ người | Trọng số Group tăng theo số user riêng biệt trong train của nhóm hiện tại. |
| Group thiếu hoặc ít người | Hệ thống chuyển phần trọng số Group về Global. |
| Cả Personal và Group thiếu | Hệ thống dùng Global để chấm điểm. |

### 3.3. Calibration tạo ngưỡng trước khi chấm test

| Giai đoạn | Hệ thống xử lý |
|---|---|
| Train | Hệ thống fit Global/Group và khởi tạo lịch sử Personal. |
| Calibration | Hệ thống chấm từng ngày, sau đó tính phân vị score để lưu threshold riêng cho từng case. |
| Test | Hệ thống dùng threshold đã lưu; Personal tiếp tục cập nhật sau khi chấm xong ngày. |
| Quyết định | Hệ thống cảnh báo khi score lớn hơn threshold, không cảnh báo khi score bằng threshold. |

## 4. Tham số vận hành nằm ở CLI và môi trường kiểm chứng

| Tham số | Giá trị | Nguồn |
|---|---|---|
| Đường dẫn nhân sự, input và output | --ldap-dir, --input, --output | Đối số CLI |
| Ghi đè output | Mặc định tắt; bật bằng --overwrite | scripts/attach_roles.py |
| Phép tính độ lệch chuẩn | ddof=0 | src/itd/scoring/baseline.py |
| Môi trường kiểm chứng | Python 3.11.9, NumPy 1.26.4, pytest 8.3.5 | runs/20261106-spec001-validation/env.txt |
| Lịch sử cá nhân | 30 ngày trước ngày chấm | personal.window_days |
| Scale tối thiểu | 1 trên raw count | scoring.scale_floor |
| Độ tin cậy | k_P=7 ngày, k_G=3 người; tối thiểu 2 ngày/2 người | backoff trong common config |
| Hiệu chỉnh ngưỡng | p=0.99, linear, cảnh báo khi score>threshold | threshold trong common config |

## 5. Kết quả kiểm chứng gồm dữ liệu giả và CERT thật

| Kiểm chứng | Kết quả | Bằng chứng |
|---|---|---|
| Bộ kiểm thử | 61 test qua trong 0.94 giây | runs/20261106-spec001-validation/pytest.xml |
| Chạy CLI hai lần | 3 dòng, 1 dòng có Role, 2 dòng thiếu Role; output giống nhau | runs/20261106-spec001-validation/metrics.json |
| Thời gian smoke | 0.2188 giây cho hai lần | Cùng metrics.json |
| Bộ kiểm thử mới nhất | 101 test qua trong 2.68 giây | runs/20261107-spec002-smoke/pytest.xml |
| Hai case trên cùng fixture | Mỗi case có 5 dòng train, 4 Calibration và 2 test giả; hai lần chạy cùng score/threshold | runs/20261107-spec002-smoke/verification.json |
| Ngưỡng trên fixture | Department: 0.7714150071929214; Role: 1.5278060653061314 | threshold.json trong run1 của mỗi case |

Các ngưỡng trong bảng trên chỉ thuộc fixture. Các bảng tiếp theo ghi ngưỡng CERT và metric test lần 1.

| Kiểm chứng CERT mới nhất | Kết quả | Bằng chứng |
|---|---|---|
| Fit và Calibration hai case | Mỗi case dùng 105.171 dòng train và 84.066 dòng Calibration; thời gian runner 26.898015 giây | runs/20261107-cert-first-calibration/result/metrics.json |
| Ngưỡng Department | 0.8423588864100263; 841 cảnh báo Calibration | result/department/threshold.json và calibration_scores.csv trong run trên |
| Ngưỡng Role | 0.8115505803240236; 841 cảnh báo Calibration | result/role/threshold.json và calibration_scores.csv trong run trên |
| Đối soát sau chạy | Cùng user-day/config chung; score hữu hạn, tổng trọng số bằng 1; test deferred | runs/20261107-cert-first-calibration/verification.json |

Các cảnh báo Calibration là thống kê trên tập dùng hiệu chỉnh, chưa phải hiệu quả held-out. Chính sách loại ngày độc hại khỏi train hiện giữ nguyên số dòng vì đáp án có 0 ngày độc hại trong train.

| Metric test lần 1 | Department | Role |
|---|---:|---:|
| Số user-day / số dương | 141.215 / 515 | 141.215 / 515 |
| AP | 0.039175 | 0.075425 |
| Precision | 6.13% | 9.68% |
| Recall | 16.31% | 24.27% |
| F1 | 0.089125 | 0.138427 |
| FPR | 0.9140% | 0.8287% |
| Đúng dương / cảnh báo sai | 84 / 1.286 | 125 / 1.166 |

Role có kết quả quan sát cao hơn trên split này; mô hình vẫn bỏ sót nhiều ngày độc hại. Bằng chứng: `runs/20261107-cert-test-open-1/metrics.json` và `metric-checks.json`. Báo cáo giới hạn nhãn và phương pháp: `docs/cert-test-open-1-results.md`.

| Audit sau test | Kết quả |
|---|---|
| Đáp án với raw log | Cả 7.323 sự kiện khớp nguồn, ID, user và timestamp. |
| Raw với feature | Sáu count khớp toàn bộ 330.452 user-day, không có khóa thiếu/thừa. |
| Lịch sử và score | 450.562 dòng Calibration/test của hai case khớp tính lại; sai số score tối đa 8.88e-16. |
| Metric | AP, ROC-AUC và confusion metrics khớp đối soát độc lập. |

Audit chỉ đọc và xác minh kết quả đã lưu. Mô hình, threshold và lần mở test giữ nguyên. Chi tiết: `docs/label-pipeline-audit.md`.

## 6. Người chạy dùng môi trường kiểm chứng riêng

Chạy bộ kiểm thử:

```powershell
.\.venv-validation311\Scripts\python.exe -m pytest -q
```

Chạy lại fixture smoke đã lưu:

```powershell
.\.venv-validation311\Scripts\python.exe scripts/attach_roles.py --ldap-dir runs/20261106-spec001-validation/LDAP --input runs/20261106-spec001-validation/features.csv --output runs/20261106-spec001-validation/roles.csv --overwrite
```

Chạy hai case trên fixture đã lưu; chọn run-dir mới mỗi lần:

```powershell
.\.venv-validation311\Scripts\python.exe scripts/run_group_ablation.py --config runs/20261107-spec002-smoke/fixture/department.json --config runs/20261107-spec002-smoke/fixture/role.json --run-dir runs/20261107-spec002-smoke/manual-run --include-test
```

## 7. Thuật ngữ giúp đọc kết quả

| Thuật ngữ | Nghĩa |
|---|---|
| LDAP | Bảng nhân sự ghi chức vụ của người dùng theo từng tháng. |
| User-day | Một người dùng trong một ngày hoạt động. |
| Baseline | Thống kê hành vi được dùng làm mốc so sánh cho bước phát triển tiếp theo. |
| Smoke | Lần chạy nhỏ để kiểm tra các phần nối được với nhau. |
| NaN/Inf | Giá trị số không hợp lệ hoặc vô hạn. |
| Calibration | Giai đoạn dữ liệu sau train dùng để xác định ngưỡng trước khi chấm test. |
| Threshold | Mốc score dùng để quyết định một ngày có tạo cảnh báo. |
| Adaptive Backoff | Cách phân bổ trọng số dựa trên số ngày lịch sử cá nhân và số người trong nhóm. |
| Precision | Tỷ lệ ngày dương theo đáp án trong các ngày hệ thống cảnh báo. |
| Recall | Tỷ lệ ngày dương theo đáp án được hệ thống cảnh báo. |
| FPR | Tỷ lệ ngày âm theo đáp án bị hệ thống cảnh báo. |
| AP | Chỉ số tóm tắt precision và recall khi thay đổi ngưỡng trên bảng xếp hạng score. |

## 8. Decision Log nằm trong tài liệu BA

| Quyết định | Nội dung |
|---|---|
| DL-014 | Người dùng duyệt SPEC-001 v1.0. |
| DL-015 | Hệ thống ghép Role đúng tháng và bảo vệ file dữ liệu. |
| DL-016 | Global/Role dùng chung kiểm tra đầu vào. |
| DL-017 | Kiểm chứng dùng môi trường Python 3.11 riêng. |
| DL-027 | Người dùng duyệt SPEC-002 v1.0. |
| DL-028 | Hai case dùng chung pipeline ba tầng, chỉ đổi định nghĩa Group. |
| DL-029 | Mỗi case hiệu chỉnh threshold từ Calibration. |
| DL-030 | Runner bảo vệ so sánh công bằng, giữ test mặc định deferred và lưu run riêng. |
| DL-036 | Người dùng duyệt mở test lần 1 với cấu hình và ngưỡng đã lưu. |
| DL-037 | Kết quả test được giữ làm mốc; mô hình giữ nguyên sau khi xem kết quả. |
| DL-038 | Audit raw/nhãn/pipeline đạt trong phạm vi đã kiểm tra; kết quả test giữ nguyên. |

## 9. Lịch sử cập nhật ghi rõ phạm vi đã kiểm chứng

| Bản | Ngày | Thay đổi |
|---|---|---|
| 0.2 | 2026-11-02 | Bản mô tả thiết kế và khung dự án trước triển khai. |
| 0.7 | 2026-11-06 | Cập nhật theo code và kiểm chứng SPEC-001; bản local, chờ đồng bộ Google Doc. |
| 0.12 | 2026-11-07 | Bổ sung hai case ba tầng, score và threshold theo SPEC-002; bản local, Google Doc chưa đồng bộ. |
| 0.15 | 2026-11-07 | Ghi kết quả train/Calibration CERT, split và chính sách train đã chốt; test đánh giá chưa mở, Google Doc chưa đồng bộ. |
| 0.16 | 2026-11-07 | Ghi kết quả test lần 1 và metric đã đối soát; cập nhật local, Google Doc chưa đồng bộ. |
| 0.17 | 2026-11-07 | Ghi kết quả audit raw, nhãn, lịch sử, score và metric; giữ nguyên mô hình; Google Doc chưa đồng bộ. |
| 0.19 | 2026-11-07 | Hoàn thiện tài liệu bàn giao hai case ba tầng, backoff, ngưỡng và kết quả; xuất file Word để đưa lên Google Docs. |
| 0.26 | 2026-11-09 | Bổ sung phạm vi bàn giao, nghiệm thu kỹ thuật và ví dụ đọc output sau lần chạy lại train/Calibration; không đánh giá test mới. |
| 0.27 | 2026-11-11 | Ghép LDAP cho feature/sequence/OCEAN đã tiền xử lý; chưa sửa xong SPEC-002 chọn một tầng. |
| 0.28 | 2026-11-11 | Triển khai SPEC-002 v1.2 chọn một tầng và giao diện điểm ngoài; 151 test qua, routing Calibration 100% Personal. |

## 10. Bàn giao và nghiệm thu kỹ thuật

Hai case đã chạy lại train/Calibration ngày 2026-11-09 trong 40.990708 giây, sử dụng cùng dữ liệu và các tham số đã duyệt. Department có threshold 0.8423588864100263; Role có threshold 0.8115505803240236. Mỗi case có 84.066 dòng Calibration, 841 dòng vượt threshold. Kết quả khớp lần Calibration trước.

Kiểm chứng phần mềm gần nhất: 101 test qua trong 3.59 giây. Đối soát từng dòng Calibration xác nhận cùng nhân viên/ngày giữa hai case; score và trọng số hữu hạn; trọng số không âm và tổng bằng 1; threshold khớp p99 linear tính lại; cờ cảnh báo khớp điều kiện score lớn hơn threshold.

Bản nghiệm thu kỹ thuật có sơ đồ và bảng đối chiếu yêu cầu với code/test tại docs/spec002-acceptance.md. Đây là kết quả kiểm chứng kỹ thuật để người dùng review, chưa ghi nhận người dùng đã chính thức duyệt nghiệm thu. Hướng dẫn chạy nằm tại docs/three-tier-usage.md. Run được lưu riêng tại runs/20261109-three-tier-calibration; bằng chứng nghiệm thu tại runs/20261109-spec002-acceptance. Lần này không chấm lại test nghiên cứu.

## 11. Ví dụ đọc kết quả

Các ví dụ lấy từ Calibration đã lưu, không đối chiếu nhãn để chọn ví dụ. Score không phải xác suất độc hại; cảnh báo là tín hiệu cần xem xét, không xác nhận insider.

| Nhân viên/ngày | Case | Score cuối | Threshold | Cảnh báo |
|---|---|---:|---:|---|
| AAE0190 / 2010-06-01 | Department | 0.189864 | 0.842359 | Không |
| AAE0190 / 2010-06-01 | Role | 0.066263 | 0.811551 | Không |
| BJM0111 / 2010-06-01 | Department | 0.918259 | 0.842359 | Có |
| BJM0111 / 2010-06-01 | Role | 1.017111 | 0.811551 | Có |

AAE0190 có 20 ngày lịch sử nên trọng số Personal bằng 20/(20+7), khoảng 74,07%. Với Department, nhóm có 6 người; phần trọng số còn lại phân cho Group khoảng 17,28% và Global khoảng 8,64%. Score cuối là tổng score từng tầng nhân trọng số tương ứng. Hai case giữ cùng Personal và Global; định nghĩa Group khác nhau làm score Group và phần trọng số còn lại khác nhau.

Khi Personal dưới 2 ngày, tầng này không tham gia kết hợp. Khi Group thiếu hoặc dưới 2 người, hệ thống chuyển phần kết hợp về Personal/Global. Nếu cả hai tầng không đủ dữ liệu, dùng Global. Score tầng không khả dụng để trống, không hiểu là score bằng 0.

Hướng dẫn đầy đủ từng cột và cách tính: docs/three-tier-output-guide.md. Cảnh báo trên Calibration là kết quả nhìn lại tập đã dùng hiệu chỉnh threshold, không phải FPR hay hiệu quả trên tập độc lập. Các ví dụ không dùng để chọn case hoặc thay đổi tham số.

## 12. Ghép LDAP cho dữ liệu đã tiền xử lý — SPEC-001 v1.1

Hệ thống đã nhận bộ feature và sequence có sẵn, bổ sung chức vụ và phòng ban đúng tháng cho từng dòng. Bước ghép giữ nguyên feature, mask, OCEAN và thứ tự chuỗi. Output mới nằm tại data/processed/CERT-r4.2-processed-two-branch-v1-ldap/; nguồn không bị sửa.

| Nhánh output | File Parquet | Số dòng | Số nhân viên–ngày |
|---|---:|---:|---:|
| Feature hành vi | 64 | 330.452 | 330.452 |
| Feature hành vi + OCEAN | 64 | 330.452 | 330.452 |
| Sequence | 64 | 12.523.202 | 330.452 |

| Quy tắc | Kết quả |
|---|---|
| Hệ thống tra mã nhân viên và tháng của ngày hoạt động. | Mỗi dòng thêm role, department, hai cờ thiếu và ldap_month. |
| Hệ thống không lấy metadata tháng khác khi thiếu. | Role thiếu ở 1.793 user-day; Department thiếu ở 6.637 user-day; giữ dòng với UNKNOWN. |
| Hệ thống đọc lại output và so toàn bộ cột gốc. | Giá trị, dtype, null, mask và thứ tự khớp; khóa/index được bảo toàn. |
| Hệ thống kiểm hash nguồn và LDAP trong lần chạy. | Nguồn không thay đổi; hash Parquet khớp lần kiểm kê trước. |
| Kiểm thử chạy trên fixture. | 21 test qua trong 13.81 giây; có kiểm đúng tháng, thiếu metadata, dữ liệu lỗi và bảo vệ output. |
| Run dữ liệu thật hoàn tất trên CPU. | 296.898194 giây; không training, score hoặc threshold mới. |

Số thiếu theo row sequence lớn hơn số user-day do một người có nhiều sự kiện trong ngày: 70.165 row thiếu Role, 300.323 row thiếu Department. f100 và các mask không được tính lại khi thêm LDAP.

Hướng dẫn: docs/enrich-preprocessed-ldap-usage.md. Manifest đầy đủ trong output; bằng chứng và log ở runs/20261111-spec001-ldap-enrichment. Bộ chọn tầng và giao diện điểm đã triển khai tại §13; cách tạo điểm/Calibration vẫn là phần việc sau.

## 13. Bộ chọn một tầng — SPEC-002 v1.2

Hệ thống giữ hai case Group theo Department và Role. Mỗi user-day chỉ chọn một tầng theo dữ liệu quá khứ, không trộn điểm.

| Điều kiện | Tầng được chọn |
|---|---|
| Nhân viên có ít nhất 7 ngày hoạt động trong 30 ngày trước ngày đang xét. | Personal; hệ thống dừng xét tầng cho user-day này. |
| Personal thiếu nhưng Group hợp lệ có ít nhất 2 nhân viên riêng biệt trong train. | Group của case Department hoặc Role. |
| Personal thiếu và Group missing, chưa thấy trong train hoặc quá nhỏ. | Global. |

Lịch sử chung giữa hai case chỉ cập nhật sau khi xử lý xong toàn ngày. Group membership giữ cố định từ train. Thiếu điểm ngoài không làm hệ thống chuyển tầng.

| Kết quả Calibration hiện tại | Department | Role |
|---|---:|---:|
| User-day được route | 84.066 | 84.066 |
| Chọn Personal | 84.066 | 84.066 |
| Chọn Group | 0 | 0 |
| Chọn Global | 0 | 0 |

Kiểm độc lập xác nhận mỗi dòng có 19–30 ngày lịch sử, đều đủ Personal. Vì Calibration này không có cold-start cần Group, kết quả không chứng minh Department hoặc Role tốt hơn. Các nhánh Group/Global đã được kiểm trên fixture; không tự đổi điều kiện để ép tạo khác biệt.

Output ghi tầng, lý do và cỡ lịch sử; score để trống, trạng thái awaiting_external_score. Khi bên cung cấp có điểm, CSV phải đúng user/day/case/tầng và đủ toàn bộ row. Hệ thống nhận nguyên giá trị hữu hạn, không tự chuẩn hóa hoặc sinh threshold/cảnh báo. Điểm nhận vào chưa chứng minh cùng thang giữa các tầng.

151 test qua trong 12.91 giây; run routing thật 6.723866 giây. Bằng chứng: runs/20261111-spec002-routing-validation và runs/20261111-spec002-tier-routing. Chỉ đọc metadata train/Calibration, không dùng feature/sequence/nhãn để tạo score và không đánh giá test.

Hướng dẫn chạy và giao diện CSV: docs/three-tier-usage.md. Code: src/itd/scoring/routing.py, score_input.py và scripts/run_tier_routing.py. Bước tiếp theo khi có điểm mô hình là thiết kế Calibration/đánh giá cặp case trên cùng dữ liệu và protocol đã duyệt.

## 14. Hai model chấm điểm hai nhánh trên cùng mẫu thử — SPEC-004 v1.0

Hệ thống đã chạy Isolation Forest cho Feature và LSTM Autoencoder cho Sequence trên CPU. Hai model dùng cùng 20 nhân viên và cùng ngày hoạt động.

| Tập | Khoảng ngày | User-day | Row sequence nén |
|---|---|---:|---:|
| Fit | 02–22/01/2010 | 305 | 12.159 |
| Validation | 23–31/01/2010 | 103 | 4.052 |

| Bước | Hệ thống thực hiện | Kết quả |
|---|---|---|
| 1 | Hệ thống đối soát checksum, audit train sạch và khóa Feature/Sequence. | Hai nhánh cùng cohort và cùng user-day. |
| 2 | Hệ thống học median từ ô feature hợp lệ trong fit, điền ô không áp dụng rồi nối cờ mask. | IF nhận 200 đầu vào từ 100 feature và 100 cờ. |
| 3 | IF xây 100 cây và chấm điểm từng ngày validation. | Mỗi ngày có một điểm bất thường Feature. |
| 4 | Hệ thống học vocab/scaler từ fit và giữ mask cho 24 thuộc tính sequence. | Chuỗi giữ nguyên thứ tự và các vị trí hợp lệ. |
| 5 | Hệ thống warmup bằng model tạm rồi khởi tạo lại model để đo đúng một epoch LSTM. | Một checkpoint sau khi đi qua đủ 305 ngày fit. |
| 6 | LSTM tái tạo chuỗi validation và tổng hợp lỗi trên các thuộc tính hợp lệ. | Mỗi ngày có một điểm bất thường Sequence. |
| 7 | Hệ thống lưu model, preprocessor, số đo runtime và hai điểm riêng. | validation_scores.parquet có 103 row đầy đủ. |

| Thời gian đo thật | Giây |
|---|---:|
| Fit IF | 0,223 |
| IF chấm validation | 0,0069 |
| Một epoch LSTM | 1,081 |
| LSTM chấm validation | 0,222 |
| Đọc dữ liệu | 11,372 |
| Tổng wall time pilot, gồm setup/warmup/đối soát/ghi artifact | 24,647 |

| Kịch bản ngoại suy training | Một epoch trên train đầy đủ | 20 epoch giả định |
|---|---:|---:|
| Nhân theo số bước sequence thật | Khoảng 5,93 phút | Khoảng 1,98 giờ |
| Nhân theo số user-day | Khoảng 6,21 phút | Khoảng 2,07 giờ |

Hai hàng là kịch bản từ mẫu nhỏ, không phải khoảng tin cậy hoặc số đo full run. Dự toán training giữ riêng thời gian đọc dữ liệu, setup và validation.

330 test qua trong 43,91 giây; review khoa học độc lập READY. Checkpoint, raw score và nguồn dữ liệu đã được kiểm tra; đây là pilot kỹ thuật một epoch (→ DL-070–072).

| Thuật ngữ | Nghĩa trong luồng này |
|---|---|
| Isolation Forest | Model dùng cây để tìm những tổ hợp feature dễ bị tách khỏi các ngày khác. |
| LSTM Autoencoder | Model học tái tạo chuỗi thao tác; lỗi tái tạo tạo ra điểm riêng cho nhánh sequence. |
| Epoch | Một lượt học qua toàn bộ dữ liệu fit của mẫu thử. |
| Raw score | Điểm đầu ra riêng từng model, dùng cho bước chuẩn hóa/hợp nhất được thiết kế tiếp theo. |

Hướng dẫn: docs/if-lstm-cpu-pilot-usage.md. Bằng chứng: runs/20261112-if-lstm-cpu-pilot-01 và runs/20261112-spec004-validation. Hai case Department/Role và bộ chọn một tầng giữ nguyên ở §13. Việc chuẩn hóa/hợp nhất hai điểm và hiệu chỉnh threshold cuối trên Calibration là bước tiếp theo.
