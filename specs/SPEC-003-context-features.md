---
id: SPEC-003
title: Tiền xử lý feature ngữ cảnh cho hai case ba tầng
status: Withdrawn
version: 0.2
date: 2026-11-07
rq: [RQ2]
components: [C1, C2]
decisions: [DL-020, DL-025, DL-033, DL-034, DL-038]
supersedes: null
---

# SPEC-003 — Tiền xử lý và mở rộng feature ngữ cảnh

> **Rút khỏi phạm vi ngày 2026-11-09 (DL-041).** Người dùng chỉ yêu cầu kiến trúc ba tầng theo SPEC-002. Không triển khai spec này; OQ-13/OQ-14 đóng vì ngoài phạm vi, không phải đã chọn A/B/C. Nội dung bên dưới giữ làm lịch sử đề xuất, không phải kế hoạch thực hiện.

## 1. Mục tiêu

Chuẩn bị bộ feature user-day có thông tin thời gian và thiết bị từ raw CERT r4.2. Phục vụ bước luồng đặc trưng trong model-design.md §3 và hai case Department/Role đã triển khai. Đây là đề xuất bước tiếp theo sau audit; người dùng chưa chọn gói feature hoặc duyệt code spec này.

## 2. Phạm vi

- Dựng bộ trích xuất feature có cấu hình và đầu ra phiên bản mới, giữ nguyên raw/processed/kết quả test cũ.
- Giữ hai định nghĩa Group tại cùng một tầng, dùng cùng feature/split/nguyên tắc Calibration.
- Chuẩn bị khả năng dùng D feature trong data validation, TierConfig, history, baseline và runner thay vì cố định sáu cột.
- Giữ raw count, scale floor=1, backoff 7/3/2/2, Personal 30 ngày, Global/Group cố định train và p99 Calibration theo quyết định hiện có.
- Giữ mốc split DL-033 và chính sách train DL-034. Thay đổi số feature đòi hỏi fit lại baseline/history và Calibration mới sau khi được duyệt.

## 3. Đầu vào và đầu ra

| Đối tượng | Schema / vị trí | Quy tắc |
|---|---|---|
| Raw | logon/device/file/email/http.csv tại D:/CERT_r4.2 | nguồn chỉ đọc, parse ngày tường minh MM/DD/YYYY HH:MM:SS |
| Feature cũ | sáu count SPEC-001 | giữ cùng ý nghĩa; đối soát chính xác với output cũ |
| Feature mới | user_id,date và D count | D phụ thuộc OQ-13; không có label/metadata missing trong vector |
| Output phiên bản mới | data/processed/context-v1/ | tạo mới, từ chối ghi đè |
| Manifest | schema, config, nguồn/hash, số sự kiện, số user-day, split dates | truy vết preprocessing và hai case |

Đọc theo luồng, không giới hạn số dòng. Giữ các ngày có hoạt động từ hợp năm nguồn, không tự thêm các ngày zero hoặc loại user ít log. Timestamp dùng như được ghi trong CERT, không tự đổi sang múi giờ Việt Nam.

## 4. Thiết kế dự thảo

### 4.1 Các gói feature cần chọn

Sáu feature gốc luôn gồm logon_count, logoff_count, device_count, file_count, email_count, http_count. device_count giữ nghĩa cả Connect và Disconnect.

Gói A (14 feature) thêm tám count: logon_offhours_count, logon_weekend_count, device_connect_count, device_disconnect_count, device_connect_offhours_count, file_offhours_count, email_offhours_count, http_offhours_count.

Gói B (18 feature) gồm A và thêm logon_unique_pc_count, file_unique_pc_count, email_unique_pc_count, http_unique_pc_count. Mỗi unique PC là số giá trị pc khác nhau trong cùng user-day, không phải PC mới/lạ so với lịch sử.

Gói C (9 feature) chỉ thêm logon_offhours_count, device_connect_count, device_connect_offhours_count vào sáu feature cũ.

Offhours của logon chỉ đếm activity Logon; weekend cũng chỉ đếm Logon vào thứ Bảy/Chủ nhật. Device_connect/disconnect đếm từng activity tương ứng; connect_offhours chỉ đếm Connect. Với file/email/http, đếm mọi sự kiện của nguồn vào ngoài giờ. Mọi count cùng ngày có thể liên quan nhau; phiên bản thống kê vẫn lấy mean positive z với trọng số feature bằng nhau. Vì thêm cột làm đổi trọng số tương đối của tín hiệu, phải được duyệt như một thay đổi mô hình.

### 4.2 Khung giờ cần chốt

OQ-14 A đề xuất ngày làm việc thứ Hai–thứ Sáu và giờ [08:00,18:00): 08:00 thuộc trong giờ, 18:00 thuộc ngoài giờ; thứ Bảy/Chủ nhật luôn ngoài giờ. Không tự thêm lịch ngày lễ chưa được cung cấp. OQ-14 B dùng [09:00,17:00) cùng quy tắc ngày. OQ-14 C cần người dùng cung cấp ngày và khoảng giờ cụ thể trước khi hoàn thiện spec.

### 4.3 Feature schema dùng chung

Danh sách và thứ tự feature phải nằm trong manifest/config; hai case phải khớp hoàn toàn. Mặc định API cũ tiếp tục dùng sáu feature để giữ tương thích SPEC-001/SPEC-002. Khi dùng bộ mới, baseline và history phải mang danh sách feature; cấm nạp checkpoint/threshold của schema khác. Không sửa artifact cũ hoặc tự dùng threshold cũ cho D mới.

### 4.4 Chống leakage và bảo toàn tập dữ liệu

Feature của ngày t chỉ dùng sự kiện ngày t; chưa bổ sung profile PC lạ, domain nguy hiểm hay đặc trưng suy từ nhãn. Không mở score test lần 1 để chọn gói hoặc giờ làm việc. Gói/khung giờ được chốt trước khi chạy thí nghiệm mới và áp dụng cùng cách cho mọi split. Metadata Group giữ nguyên join đúng tháng.

## 5. Tham số

| Khóa dự kiến | Giá trị |
|---|---|
| preprocessing.feature_pack | OQ-13 |
| preprocessing.work_days / work_start / work_end | OQ-14 |
| features | danh sách đầy đủ và thứ tự theo gói được chọn |
| paths.raw / paths.output | người chạy cung cấp, output mới |
| split | giữ DL-033 |

Đợt này chưa tune feature weights, backoff hoặc threshold quantile. Transformation identity và floor=1 là lựa chọn kế thừa, không tuyên bố tối ưu cho bộ feature mới.

## 6. Thay đổi code dự kiến

| Tệp | Phạm vi |
|---|---|
| src/itd/features/context_counts.py | config khung giờ, phân loại timestamp, tổng hợp count user-day |
| scripts/prepare_context_features.py | CLI đọc config, chạy preprocessing, ghi manifest/split mới |
| src/itd/data/ldap.py | validator nhận feature schema cấu hình, giữ API sáu feature cũ |
| src/itd/scoring/tiers.py | TierConfig.features và kiểm schema/state D chiều |
| scripts/run_group_ablation.py | nhận schema hợp lệ từ manifest thay vì buộc sáu cột; chống mismatch checkpoint |
| configs/experiments/context_features_common.json | bộ tham số/gói đã được duyệt, các case chỉ đổi group_key |
| tests/test_context_features.py và các test schema | fixture nhỏ, regression baseline cũ, leakage/output protection |

### 6.1 Hợp đồng triển khai đề xuất 13A/14A

Bản v0.2 cụ thể hóa phương án A để người dùng duyệt; chưa ghi nhận OQ-13/OQ-14 là quyết định đã chốt. Phương án B/C tại §12 vẫn là lựa chọn thay thế và cần cập nhật spec nếu được chọn.

- `ContextConfig(feature_pack="context14", work_days=(0,1,2,3,4), work_start="08:00", work_end="18:00")`: ngày theo `datetime.weekday()`. Chỉ nhận giờ HH:MM hợp lệ, start < end; danh sách ngày không trùng, nằm trong 0–6.
- `aggregate_context_counts(raw_dir: Path, config: ContextConfig) -> tuple[list[dict], dict]`: đọc đủ năm nguồn, trả rows và thống kê sự kiện theo nguồn. Rows gồm `user_id,date` rồi sáu feature gốc theo thứ tự SPEC-001 và tám feature theo thứ tự §4.1 gói A; count là số nguyên không âm, ngày ISO. Sắp xếp tăng theo date/user_id.
- Parse bằng CSV reader, không tách dấu phẩy thủ công; kiểm header bắt buộc `date,user`, thêm `activity` cho logon/device. Sai timestamp, user trống hoặc activity ngoài Logon/Logoff và Connect/Disconnect phải báo nguồn/dòng và dừng. Không bỏ dòng lỗi hoặc tự sửa activity.
- `attach_roles(..., features=FEATURES)` và validator tương ứng nhận schema tùy chọn; mặc định giữ sáu feature. `TierConfig.features` dùng tuple; serialization JSON lưu list theo đúng thứ tự. Tất cả phép tính dùng D từ schema, không cắt/pad vector.
- Baseline/history mới lưu `features`; thiếu schema chỉ được nhận ở chế độ sáu feature legacy. Khác số chiều hoặc thứ tự phải lỗi trước scoring. Threshold mới lưu schema và fingerprint cấu hình; runner không nạp lại threshold sáu feature cho context14.

### 6.2 Config và artifact

`configs/experiments/context_features_common.json` chứa `preprocessing.feature_pack="context14"`, `work_days=[0,1,2,3,4]`, `work_start="08:00"`, `work_end="18:00"`, `paths.raw`, `paths.output`, `paths.reference_features` và split DL-033. Danh sách `features` phải khớp pack tuyệt đối. Hai overlay Department/Role chỉ khác `group_key`, dùng chung dữ liệu chuẩn bị.

Output UTF-8, CSV có header; JSON UTF-8 không NaN/Infinity. Thư mục mới chứa `user_day_features.csv`, `train_features.csv`, `calibration_features.csv`, `test_features.csv`, `manifest.json`. Manifest ghi schema_version, tên/thứ tự feature, config, SHA-256 từng raw input và output, số event từng nguồn, số user-day/split, ngày nhỏ nhất/lớn nhất, kết quả đối soát sáu count cũ. `paths.reference_features` bắt buộc khi chạy CERT thật; mọi key/count gốc phải khớp trước công bố output.

Chia theo ngày DL-033; ngoài khoảng split phải lỗi, không âm thầm bỏ mẫu. Nhãn chỉ dùng ở bước kiểm chính sách train tách biệt, không đi vào hàm tổng hợp. Train vẫn phải đối soát với danh sách ngày độc hại đã xác minh theo DL-034 trước fit. Preprocessing toàn bộ raw để tạo bảng test không đồng nghĩa chấm điểm hoặc đánh giá test.

Ghi vào thư mục tạm cùng cha rồi đổi tên khi validation hoàn tất; từ chối output đã tồn tại và output trùng/nằm trong raw. Lỗi không công bố thư mục output hoàn chỉnh; dọn đúng thư mục tạm do lần chạy tạo. Không sửa source cũ hay artifact của SPEC-002.

## 7. Thí nghiệm và đánh giá

Giữ kết quả test lần 1 làm baseline đóng băng. Triển khai mới kiểm chứng fixture rồi chuẩn bị feature thật; fit train và Calibration sau duyệt. Không tự mở test lần 2. Nếu sau này đánh giá trên test đã xem, phải ghi rõ exploratory; không coi việc đổi feature hoặc chia lại ngày là tạo holdout chưa từng nhìn thấy.

## 8. Tiêu chí chấp nhận dự kiến

| ID | Kiểm chứng |
|---|---|
| AC-01 | Sáu count gốc khớp bộ đã audit, giữ tập user-day/split |
| AC-02 | Các count mới khớp fixture tính tay theo gói |
| AC-03 | Biên giờ bắt đầu/kết thúc và thứ Bảy/Chủ nhật đúng quy tắc |
| AC-04 | Thay sự kiện ngày khác không làm đổi feature ngày t |
| AC-05 | Hai case cùng schema/order và fingerprint, chỉ khác group_key |
| AC-06 | Checkpoint/threshold khác schema bị chặn; API sáu feature cũ vẫn qua test |
| AC-07 | Không ghi đè dữ liệu/run cũ; manifest đủ số sự kiện và schema/config |
| AC-08 | Preprocessing không đọc nhãn để sinh feature; không fit scaler/stat trên tương lai |

## 9. Kế hoạch test

Fixture ít nhất hai user, hai ngày làm việc và một cuối tuần; có sự kiện ngay trước/đúng biên giờ, Connect/Disconnect, Logon/Logoff. Nếu gói B được chọn, thêm PC lặp và PC khác trong cùng ngày. Regression toàn bộ test cũ; so sánh sáu cột trên raw thật với bảng đã audit. Chưa có mô hình học nên không có overfit test.

## 10. Thực thi dự kiến

Người dùng duyệt bản v0.2 cùng 13A/14A → code/test fixture → preprocessing phiên bản mới → fit train/Calibration cho hai case trong run-dir mới. Không chấm test trong đợt này. Dùng Python 3.11 và requirements-validation.txt đã cài, parser dùng thư viện chuẩn; không cần dependency mới.

Lệnh triển khai dự kiến sau duyệt (chưa có CLI preprocessing trước khi code):

```powershell
.venv-validation311\Scripts\python.exe -m pytest -q
.venv-validation311\Scripts\python.exe scripts/prepare_context_features.py --config configs/experiments/context_features_common.json
```

CLI ghi hai config case trỏ tới các split mới, cùng common config dùng cho runner hiện có; fit/Calibration dùng `scripts/run_group_ablation.py --config <department-config> --config <role-config> --run-dir <new-run-dir>` và không có `--include-test`. Lưu config, env, log, manifest, metric và thời gian thực tế. Ước tính quét raw vài phút trên CPU, chưa đo parser cuối; audit prefix trước đó khoảng 105 giây không phải cam kết runtime mới. Fixture dự kiến dưới một phút, không dùng GPU.

## 11. Rủi ro

Khung giờ chung có thể không phản ánh ca làm việc từng người; phải ghi rõ giả định. Các count liên quan nhau có thể tăng trọng số một nguồn; chưa có cơ sở khẳng định cải thiện. Đếm distinct PC cần bộ nhớ theo user-day nếu chọn B. Test đã được xem nên thí nghiệm mới phải ghi nhận đúng trạng thái đánh giá.

## 12. Open Questions

| ID | Câu hỏi | A (khuyến nghị) | B | C |
|---|---|---|---|---|
| OQ-13 | Gói feature cho bước tiếp theo | 14 count: giữ sáu cũ + ngoài giờ/cuối tuần/Connect/Disconnect | 18 count: thêm độ đa dạng PC theo nguồn | 9 count: chỉ thêm logon ngoài giờ, USB Connect và Connect ngoài giờ |
| OQ-14 | Định nghĩa giờ làm việc | Thứ Hai–thứ Sáu, [08:00,18:00) | Thứ Hai–thứ Sáu, [09:00,17:00) | Người dùng cung cấp khung ngày/giờ riêng |

Đây là đề xuất chưa được chốt. Chưa thay đổi preprocessing, config thực thi hoặc mô hình.

## 13. Review readiness

Đã đọc lại tệp từ đĩa theo từng lăng kính.

| Vòng | Kết quả |
|---|---|
| 1 — Đầy đủ và truy vết | Đã bổ sung hợp đồng 14 feature, API/config/output; giữ truy vết DL-020/025/033/034/038 và 8 AC; chờ duyệt 13A/14A |
| 2 — Đúng đắn khoa học | Dữ liệu ngày t không dùng tương lai/nhãn; giữ cùng mẫu, split và config giữa hai Group; test đã xem chỉ dùng lại dưới nhãn exploratory sau xác nhận |
| 3 — Sẵn sàng dev | Đã bổ sung API, serialization, bảo vệ output, tương thích sáu feature và lệnh chạy; không cần dependency mới. Chờ phê duyệt phương án cụ thể |

**Kết luận: READY có điều kiện cho phương án 13A/14A** — chỉ triển khai sau khi người dùng duyệt rõ bản v0.2 và hai giả định này. Chưa chạy preprocessing mới hoặc thay đổi mô hình. Nếu chọn B/C, phải sửa phần bị ảnh hưởng và review lại.
