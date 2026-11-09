---
id: SPEC-001
title: Tiền xử lý CERT r4.2 cho hai nhánh Behaviour và Sequence
status: Implemented
version: 1.1
date: 2026-11-09
rq: [RQ1]
components: [C1, C2, C3]
decisions: [DL-001, DL-002, DL-007, DL-008, DL-009, DL-011, DL-012, DL-013]
supersedes: null
---

# SPEC-001 — Tiền xử lý CERT r4.2 cho hai nhánh Behaviour và Sequence

## 1. Mục tiêu

Chuẩn hóa toàn bộ log CERT r4.2 thành bảng sự kiện theo `user-day`, sau đó tạo hai biểu diễn độc lập phục vụ RQ1/Gap 1: (1) nhánh Behaviour gồm đúng 100 đặc trưng thống kê theo ngày và (2) nhánh Sequence gồm 24 trường logic trên mỗi sự kiện đã sắp thứ tự. Hai nhánh không dùng nội dung văn bản và không dùng thông tin tương lai. SPEC này chỉ tạo dữ liệu đầu vào; chưa huấn luyện Feature AE hay TCN–Transformer.

## 2. Phạm vi

- Đọc đủ `logon.csv`, `device.csv`, `file.csv`, `http.csv`, `email.csv`, `psychometric.csv` và các snapshot `LDAP/*.csv` theo chunk; tuyệt đối không giới hạn tổng số dòng.
- Chuẩn hóa năm nguồn log thành Parquet phân vùng theo `source/year_month`.
- Gắn LDAP theo snapshot tháng tương ứng; suy ra `pc_context` từ lịch sử quá khứ.
- Tạo 100 đặc trưng Behaviour, giá trị validity mask và phiên bản ablation thêm OCEAN.
- Tạo chuỗi 24 trường logic; nén run liên tiếp cùng token và PC với khoảng cách không quá 5 phút.
- Sinh manifest, thống kê chất lượng và phân vị độ dài chuỗi sau nén.
- Nếu có `answers/`, tạo nhãn theo event ID; nếu thiếu thì hoàn thành dữ liệu không nhãn và ghi `labels_available=false`.
- Không chia train/validation/test trong SPEC này; D-02 và D-03 vẫn để cấu hình `null` theo DL-009.
- Không chọn `max_len`, mục tiêu học Sequence, scaler/vocab, mô hình, score, threshold hoặc metric đánh giá.

## 3. Dữ liệu vào / ra

| Đối tượng | Nguồn / đích | Schema / shape | Ghi chú |
|---|---|---|---|
| Raw log | `data/raw/cert-r4.2/{logon,device,file,http,email}.csv` | Schema CERT r4.2 | `date` parse đúng `%m/%d/%Y %H:%M:%S` |
| LDAP | `data/raw/cert-r4.2/LDAP/YYYY-MM.csv` | user, role và đơn vị tổ chức | As-of theo tháng sự kiện |
| OCEAN | `data/raw/cert-r4.2/psychometric.csv` | `user_id,O,C,E,A,N` | Chỉ ablation |
| Canonical events | `data/interim/canonical_events/source=<s>/year_month=<m>/*.parquet` | §4.1 | Không giữ `content` |
| Behaviour | `data/processed/user_day_features/*.parquet` | `(user, day, f001..f100, m001..m100)` | Một dòng/user-day |
| OCEAN ablation | `data/processed/user_day_features_ocean/*.parquet` | Behaviour100 + O,C,E,A,N | Không phải đầu vào chính |
| Sequence | `data/processed/user_day_sequences/*.parquet` | `(user,day,event_index,S01..S24,attribute_mask)` | Dạng dài, chưa pad/cắt |
| Sequence stats | `data/artifacts/reports/sequence_length_stats.json` | phân vị theo nguồn và tổng | Dùng spec mô hình chọn `max_len` trên train |
| Manifest | `data/artifacts/manifests/prepare_data.json` | row count, min/max date, hash config, lỗi | Bằng chứng L6 |
| Labels | `data/processed/labels/user_day_labels.parquet` | user, day, label, scenario | Chỉ tạo khi có answers |

### 3.1 Canonical event schema

Các cột chung: `event_id:string`, `timestamp:datetime64[ns]`, `day:date`, `year_month:string`, `user:string`, `pc:string`, `source:category`, `event_token:category`, `calendar_context:uint8`, `pc_context:uint8`. Cột riêng nullable: `filename`, `file_extension`, `url_scheme`, `url_hostname`, `url_path`, `url_query_keys`, `email_to_count`, `email_cc_count`, `email_bcc_count`, `email_external_count`, `email_attachment_count`, `email_size`, `email_sender_context`. Không ghi `content`, địa chỉ email thô, URL thô hoặc tên file thô sang dữ liệu processed.

## 4. Thiết kế

### 4.1 Chuẩn hóa sự kiện

Token nghiệp vụ: `LOGON`, `LOGOFF`, `DEVICE_CONNECT`, `DEVICE_DISCONNECT`, `FILE`, `HTTP`, `EMAIL`. Sắp xếp ổn định theo `(user, timestamp, source_priority, event_id)`, trong đó thứ tự nguồn chỉ phá hòa timestamp và được cấu hình. `day` là ngày lịch địa phương của timestamp CERT.

`calendar_context ∈ {WORK_HOUR, AFTER_HOUR, WEEKEND}`. Mặc định ngày làm việc Thứ Hai–Thứ Sáu, 07:00–19:00; đây chỉ là ngữ cảnh mô tả, không gắn nhãn độc hại.

`pc_context ∈ {OWN, SHARED, FOREIGN, MISSING}` được xác định chỉ bằng dữ liệu trước ngày D:

- OWN: PC có số ngày logon của user lớn nhất trong cửa sổ 30 ngày trước D và có tối thiểu 3 ngày.
- SHARED: PC xuất hiện với ít nhất 2 user trong 30 ngày trước D.
- FOREIGN: có PC nhưng không thuộc hai nhóm trên.
- MISSING: sự kiện không có PC.

Không dùng dữ liệu ngày D hoặc tương lai để suy ra context. LDAP ghép theo snapshot có tháng lớn nhất không vượt quá tháng sự kiện; không tạo đặc trưng “sắp nghỉ” hay “số ngày còn lại”.

### 4.2 Quy ước thời gian và baseline

Với timestamp `t`, phút trong ngày `q=60·hour+minute`, đặt `time_sin=sin(2πq/1440)` và `time_cos=cos(2πq/1440)`. Khoảng cách sự kiện `gap_minutes=max(0,(t_i-t_{i-1})/60s)` trong cùng user-day; sự kiện đầu ngày có gap 0 và mask gap=false.

Mọi baseline lịch sử của ngày D chỉ dùng `[D-W,D)`, mặc định `W=30`. Độ lệch thời gian dạng vòng tròn là khoảng cách ngắn nhất trên chu kỳ 1440 phút đến median tròn lịch sử. `new_*_30d` nghĩa là thực thể xuất hiện trong D nhưng không xuất hiện ở `[D-30,D)`.

### 4.3 Nhánh Behaviour — đúng 100 đặc trưng

Mỗi đặc trưng có một validity mask. Count không có sự kiện nhận 0 và mask=true; ratio/statistic không có mẫu hoặc không có baseline nhận 0 và mask=false. Entropy dùng Shannon tự nhiên `-Σp ln p`. `burst_count_5m` là số cụm cực đại có ít nhất 2 sự kiện, các gap liên tiếp ≤5 phút.

#### Logon — L01–L16

1. `logon_count`; 2. `logoff_count`; 3. `distinct_logon_pc_count`; 4. `own_pc_logon_count`; 5. `shared_pc_logon_count`; 6. `foreign_pc_logon_count`; 7. `foreign_pc_logon_ratio`; 8. `weekend_logon_count`; 9. `first_logon_time_deviation`; 10. `last_logoff_time_deviation`; 11. `work_span_minutes`; 12. `matched_session_count`; 13. `total_session_minutes`; 14. `max_session_minutes`; 15. `unmatched_logon_count`; 16. `unmatched_logoff_count`.

Session được ghép FIFO theo `(user,pc,day)`; chỉ cặp Logon→Logoff có thời gian không âm. `work_span` là từ logon đầu đến logoff cuối hợp lệ.

#### Device — D01–D16

17. `connect_count`; 18. `disconnect_count`; 19. `device_session_count`; 20. `unmatched_connect_count`; 21. `unmatched_disconnect_count`; 22. `device_active_minutes_total`; 23. `device_session_minutes_mean`; 24. `device_session_minutes_max`; 25. `device_distinct_pc_count`; 26. `own_pc_connect_count`; 27. `shared_pc_connect_count`; 28. `foreign_pc_connect_count`; 29. `foreign_pc_connect_ratio`; 30. `weekend_connect_count`; 31. `connect_time_deviation_mean`; 32. `connect_time_deviation_max`.

Connect/Disconnect ghép FIFO theo `(user,pc,day)` tương tự session logon.

#### File — F01–F16

33. `file_event_count`; 34. `distinct_filename_count`; 35. `distinct_extension_count`; 36. `extension_entropy`; 37. `repeated_filename_count`; 38. `repeated_extension_count`; 39. `filename_length_mean`; 40. `filename_length_std`; 41. `filename_length_max`; 42. `extension_present_ratio`; 43. `extensionless_file_count`; 44. `multi_dot_filename_count`; 45. `distinct_file_pc_count`; 46. `foreign_pc_file_ratio`; 47. `file_time_deviation_mean`; 48. `file_burst_count_5m`.

`repeated_*_count=Σ max(count(value)-1,0)`. Extension là suffix cuối sau dấu chấm của basename, lowercase; file ẩn/missing không được suy diễn là extension.

#### HTTP — H01–H16

49. `http_request_count`; 50. `distinct_url_count`; 51. `distinct_hostname_count`; 52. `distinct_path_count`; 53. `distinct_scheme_count`; 54. `https_request_ratio`; 55. `query_present_ratio`; 56. `distinct_query_key_count`; 57. `repeated_url_count`; 58. `repeated_hostname_count`; 59. `hostname_length_mean`; 60. `hostname_length_max`; 61. `url_length_mean`; 62. `url_length_max`; 63. `path_depth_mean`; 64. `new_hostname_count_30d`.

URL parse bằng parser chuẩn; hostname lowercase và bỏ dấu chấm cuối; không dùng danh sách domain nguy hiểm hoặc keyword kịch bản.

#### Email — E01–E16

65. `email_sent_count`; 66. `recipient_total_count`; 67. `unique_recipient_count`; 68. `external_recipient_total`; 69. `external_recipient_ratio`; 70. `external_recipient_email_count`; 71. `to_total`; 72. `cc_total`; 73. `bcc_total`; 74. `bcc_email_count`; 75. `attachment_email_count`; 76. `attachment_total_count`; 77. `email_size_mean`; 78. `email_size_max`; 79. `personal_from_email_count`; 80. `new_external_recipient_count_30d`.

Recipient được tách trên `;`, loại rỗng, lowercase. Domain nội bộ được suy ra từ mode domain của LDAP email, không hard-code. `personal_from` là sender khác email LDAP của user; không lưu địa chỉ thô.

#### Cross-source — X01–X12

81. `total_event_count`; 82. `active_source_count`; 83. `weekend_event_ratio`; 84. `own_pc_event_ratio`; 85. `shared_pc_event_ratio`; 86. `foreign_pc_event_ratio`; 87. `distinct_all_pc_count`; 88. `source_transition_count`; 89. `source_transition_entropy`; 90. `multi_source_burst_count_5m`; 91. `inter_event_gap_mean_minutes`; 92. `inter_event_gap_p95_minutes`.

Transition tính trên cặp nguồn liên tiếp sau sắp xếp; chỉ tính khi nguồn thay đổi. Multi-source burst phải chứa ít nhất 2 nguồn.

#### History — P01–P08

93. `active_days_last_7`; 94. `active_days_last_30`; 95. `total_events_mean_7d`; 96. `total_events_mean_30d`; 97. `total_events_std_30d`; 98. `short_long_activity_ratio`; 99. `days_since_last_active_day`; 100. `days_in_current_role`.

`short_long_activity_ratio=(mean_7d+1)/(mean_30d+1)`. `days_in_current_role` tính từ chuỗi snapshot LDAP quá khứ đến D; không nhìn snapshot sau D.

### 4.4 Biến đổi Behaviour

Tại bước tiền xử lý chỉ ghi giá trị thô. Spec mô hình sau này phải fit train-only: `log1p` cho count/duration/size/gap, giữ ratio trong `[0,1]`, rồi robust-scale bằng train median/IQR. Tensor dự kiến trước mô hình: values `[B,30,100]`, masks `[B,30,100]`; mask không được tính thành đặc trưng nghiệp vụ.

### 4.5 Nhánh Sequence — 24 trường logic

Chín trường chung cho mọi event:

1. `event_token`; 2. `time_sin`; 3. `time_cos`; 4. `gap_log1p`; 5. `gap_bucket`; 6. `calendar_context`; 7. `pc_context`; 8. `run_count_log1p`; 9. `run_span_log1p`.

Bốn trường FILE:

10. `file_extension_id`; 11. `filename_length_log1p`; 12. `extension_present`; 13. `multi_dot`.

Năm trường HTTP:

14. `url_scheme_id`; 15. `hostname_length_log1p`; 16. `url_length_log1p`; 17. `path_depth_log1p`; 18. `query_present`.

Sáu trường EMAIL:

19. `recipient_count_log1p`; 20. `external_recipient_ratio`; 21. `bcc_present`; 22. `attachment_count_log1p`; 23. `email_size_log1p`; 24. `sender_context` (`INTERNAL`, `EXTERNAL`, `MISSING`).

Trường không áp dụng nhận 0/UNK và bit tương ứng trong `attribute_mask` bằng false. `token_mask` và `attribute_mask` là metadata kỹ thuật, không tính vào 24 trường. `gap_bucket` có biên cấu hình `[0,1,5,15,60,240,inf)` phút. Vocabulary extension/scheme chỉ được fit trên train ở spec mô hình; dữ liệu tiền xử lý giữ chuỗi chuẩn hóa, không tạo vocab toàn tập.

### 4.6 Nén chuỗi chống HTTP lấn át

Duyệt từng user-day đã sắp thời gian. Hai event được gộp cùng run khi: cùng `event_token`, cùng `pc`, và gap với event trước ≤5 phút. Run giữ event đầu làm đại diện, `run_count` là số event, `run_span` là phút từ đầu đến cuối. Các thuộc tính số trong run dùng tổng cho count/size và max hoặc last cho context theo bảng mapping được test; thuộc tính categorical giữ giá trị đầu, nếu không đồng nhất dùng `MIXED`.

Không cắt chuỗi trong SPEC này. Xuất phân vị `p50,p75,p90,p95,p99,p99.5,max` độ dài trước/sau nén theo ngày và theo nguồn. `max_len` chỉ được chọn từ train sau khi D-02 được chốt.

### 4.7 Cân bằng hai nhánh

Cân bằng không được suy ra từ số cột thô vì Sequence lặp trường theo sự kiện. SPEC bảo đảm:

- Behaviour có phân bổ đồng đều: 16 đặc trưng cho mỗi nguồn chính, 12 cross-source, 8 history.
- Sequence không dùng token raw định danh và nén run để HTTP không chiếm toàn bộ độ dài.
- Spec mô hình phải đưa hai nhánh về embedding ngày cùng chiều và chuẩn hóa lỗi riêng trước khi hợp nhất; việc đó ngoài phạm vi hiện tại.

### 4.8 OCEAN ablation

Pipeline chính không chứa OCEAN. Bản ablation left-join `O,C,E,A,N` theo user vào Behaviour100, tạo 105 cột và mask riêng. Không đưa OCEAN vào Sequence. Không impute bằng toàn tập; giá trị thiếu có value=0, mask=false.

### 4.9 Nhãn và chống leakage

Nếu answers tồn tại, nhãn event được khớp bằng `event_id`; nhãn user-day là OR của event độc hại và scenario là tập scenario xuất hiện. Answers không được dùng để tạo feature, lọc token, chọn domain, chọn tham số hay quyết định `max_len`. Khi answers thiếu, lệnh vẫn thành công và manifest ghi rõ lý do chưa thể đánh giá.

## 5. Tham số

| Tham số | Khoá config | Mặc định | Khoảng tune | Lý do mặc định |
|---|---|---|---|---|
| Raw root | `paths.raw` | `data/raw/cert-r4.2` | Không | Đường dẫn project thực tế |
| CSV chunk | `data.chunk_rows` | 250000 | Không | Giới hạn RAM, không giới hạn tổng dòng |
| Time format | `data.datetime_format` | `%m/%d/%Y %H:%M:%S` | Không | Schema CERT r4.2 |
| Work hours | `data.work_hours` | `[07:00,19:00]` | Ablation sau | Ngữ cảnh rộng, tránh gắn nhãn thủ công |
| PC history | `features.pc_history_days` | 30 | Không ở C1 | Chỉ dùng quá khứ gần |
| Own PC min days | `features.own_pc_min_days` | 3 | Không ở C1 | Tránh gán OWN từ một lần |
| History window | `features.history_days` | 30 | Không ở C1 | Đồng nhất feature new/baseline |
| Run gap | `sequence.run_gap_minutes` | 5 | D-05 đã chốt | OQ-06 A |
| Gap buckets | `sequence.gap_bucket_minutes` | `[0,1,5,15,60,240]` | Spec mô hình | Phân giải tốt gap ngắn |
| Feature count | `features.count` | 100 | Không | OQ-04 A |
| Psychometric | `features.psychometric_mode` | `ablation_only` | Không | OQ-05 A |
| Split scheme | `split.scheme` | `null` | OQ-02 | DL-009 |
| Malicious train | `split.malicious_in_train` | `null` | OQ-03 | DL-009 |

## 6. Thay đổi code

| Tệp | Tạo / sửa | Lớp / hàm (chữ ký) | Mục spec |
|---|---|---|---|
| `pyproject.toml` | Tạo | dependency + CLI package | §10 |
| `configs/base.yaml` | Sửa | khóa data/features/sequence | §5 |
| `src/itd/utils/config.py` | Tạo | `load_config(path, overrides) -> AppConfig` | §5 |
| `src/itd/data/load_cert.py` | Tạo | `iter_raw_events(path, source, config) -> Iterator[DataFrame]`; `build_canonical_events(config) -> Manifest` | §4.1 |
| `src/itd/data/ldap.py` | Tạo | `load_ldap_snapshots(path) -> DataFrame`; `asof_user_context(events, ldap) -> DataFrame` | §4.1 |
| `src/itd/data/labels.py` | Tạo | `build_user_day_labels(answer_root, events) -> LabelResult` | §4.9 |
| `src/itd/features/contexts.py` | Tạo | `build_past_only_pc_context(events, days, min_days) -> DataFrame` | §4.1 |
| `src/itd/features/count_features.py` | Tạo | `build_behaviour_features(events, ldap, config) -> DataFrame` | §4.3–4.4 |
| `src/itd/features/sequence_tokens.py` | Tạo | `compress_runs(events, gap_minutes) -> DataFrame`; `build_sequence_fields(events, config) -> DataFrame` | §4.5–4.6 |
| `src/itd/utils/io.py` | Tạo | atomic Parquet/JSON writers | §3 |
| `scripts/prepare_data.py` | Tạo | `main() -> int` | §10 |
| `tests/fixtures/cert_small/` | Tạo | CSV giả 2 user × 3 ngày | §9 |
| `tests/test_*.py` | Tạo | unit, schema, leakage, smoke | §8–9 |

## 7. Thí nghiệm & chỉ số

Không huấn luyện hoặc đánh giá mô hình trong SPEC này. Chỉ báo cáo kiểm soát dữ liệu: row count từng nguồn, min/max date, missing rate, duplicate event ID, số user-day, phân vị độ dài chuỗi trước/sau nén, tỷ lệ event theo nguồn và tỷ lệ validity mask. Ablation OCEAN chỉ được tạo dữ liệu, chưa so sánh metric.

## 8. Tiêu chí chấp nhận

| # | Tiêu chí | Cách kiểm |
|---|---|---|
| AC-01 | Đọc đủ số dòng của năm CSV; tổng chunk bằng manifest, không có `max_rows` | fixture + manifest test |
| AC-02 | Canonical schema đúng, timestamp parse tường minh, thứ tự deterministic | schema/order tests |
| AC-03 | Không có `content` hoặc định danh raw nhạy cảm trong processed | forbidden-column test |
| AC-04 | Behaviour có đúng 100 value + 100 mask, đúng thứ tự và công thức fixture | feature registry test |
| AC-05 | Mỗi nhóm Logon/Device/File/HTTP/Email có 16 feature; Cross 12; History 8 | registry count test |
| AC-06 | OCEAN chỉ xuất ở dataset ablation 105 feature | ablation schema test |
| AC-07 | Sequence có đúng 24 field logic và mask trường không áp dụng | sequence schema test |
| AC-08 | Nén chỉ gộp cùng token+PC+gap≤5m; bảo toàn tổng `run_count` | compression property test |
| AC-09 | Thay đổi dữ liệu sau ngày D không đổi feature/context/sequence của D | leakage L2 test |
| AC-10 | Không tạo đặc trưng nghỉ việc/tương lai; LDAP as-of không nhìn snapshot sau | leakage L3 test |
| AC-11 | Thiếu answers không làm pipeline fail và manifest ghi `labels_available=false` | missing-label test |
| AC-12 | Chạy lại cùng input/config cho checksum và output logic giống nhau | idempotence test |
| AC-13 | Smoke ≤20 user, ≤30 ngày hoàn thành dưới 5 phút và sinh đủ artifact | smoke CLI |
| AC-14 | Dữ liệu thật sinh báo cáo phân vị chuỗi; không chọn/cắt `max_len` | integration report check |

## 9. Kế hoạch test

- Unit fixture có logon/logoff lệch cặp, USB session, file nhiều đuôi, URL lỗi, email nhiều To/CC/BCC và run HTTP.
- Property tests cho pairing session, tỷ lệ nằm `[0,1]`, mask undefined, tổng run count và sort ổn định.
- Leakage: thêm event và LDAP snapshot sau D rồi đối chiếu byte-level output của D.
- Schema registry khóa chính xác 100/24 trường để thay đổi vô ý làm test fail.
- Smoke dùng bản sao fixture trong thư mục tạm; không đọc test/answers thật và không ghi vào raw.
- Integration trên dữ liệu thật chỉ chạy sau khi code được duyệt; không mở test model vì chưa có model/split.

## 10. Thực thi

- Thứ tự: validate raw → canonicalize theo nguồn → LDAP/context → Behaviour → Sequence → nhãn nếu có → manifest/report.
- Cài môi trường (người dùng tự chạy sau khi cài Python 3.11):
  - `py -3.11 -m venv .venv`
  - `.\.venv\Scripts\python -m pip install -e ".[dev]"`
- Smoke: `.\.venv\Scripts\python -m pytest -q`
- Chuẩn bị dữ liệu thật: `.\.venv\Scripts\python scripts\prepare_data.py --config configs/base.yaml`
- Chạy lại có chủ đích: thêm `--force`; mặc định từ chối ghi đè output hoàn chỉnh.
- Ước tính: smoke <5 phút, RAM mục tiêu <4 GB; full CERT khoảng 2–8 giờ tùy SSD/CPU. Tiền xử lý dùng CPU, VRAM 0 GB. Thời gian thật phải ghi sau run.

## 11. Rủi ro

| Rủi ro | Dấu hiệu | Cách xử lý |
|---|---|---|
| HTTP 14+ GB | RAM tăng/cạn đĩa | chunk + Parquet partition, không concat toàn bộ |
| Answers chưa có | không sinh label | vẫn hoàn thành unsupervised artifacts; báo blocker đánh giá |
| URL/email lỗi format | parser trả lỗi | parser tolerant, mask=false, đếm parse error |
| PC context cold-start | thiếu 30 ngày lịch sử | `MISSING/FOREIGN` theo quy tắc, mask/báo cáo riêng |
| Chuỗi vẫn dài sau nén | p99 rất lớn | báo phân vị; D-05 spec mô hình quyết định cap, không tự cắt |
| Dung lượng processed lớn | thiếu ổ đĩa | dictionary encoding, compression zstd, ước lượng trước ghi |

## 12. Open Questions

Không còn câu hỏi chặn việc code SPEC-001. OQ-02/OQ-03 vẫn mở nhưng chỉ chặn lần train đầu tiên theo DL-009. D-04 (`sequence objective`) và `max_len` sẽ hỏi trong spec mô hình C3 sau khi có thống kê train.

## 13. Review readiness

### Review readiness — v0.1 — 2026-11-09

| Vòng | Lăng kính | Blocker | Major | Minor | Đã sửa cơ học | Điểm |
|---|---|---:|---:|---:|---:|---:|
| 1 | Đầy đủ & truy vết | 0 | 0 | 2 | 2 | 10.0 |
| 2 | Đúng đắn khoa học | 0 | 0 | 2 | 2 | 10.0 |
| 3 | Sẵn sàng dev | 0 | 0 | 2 | 2 | 10.0 |

**Kết luận: READY** — đủ điều kiện trình người dùng duyệt trước khi code.

| # | Vòng | Mức | Phát hiện | Xử lý |
|---|---|---|---|---|
| R1-01 | 1 | Minor | Chưa phân biệt 24 field với mask kỹ thuật | Đã sửa tại §4.5 |
| R1-02 | 1 | Minor | Chưa nói rõ thiếu answers | Đã sửa tại §2, §4.9, AC-11 |
| R2-01 | 2 | Minor | Vocabulary có nguy cơ fit toàn tập | Đã hoãn vocab đến train-only tại §4.5 |
| R2-02 | 2 | Minor | PC OWN có nguy cơ dùng chính ngày D | Đã khóa cửa sổ trước D tại §4.1 |
| R3-01 | 3 | Minor | Chưa nêu hành vi ghi đè | Đã thêm `--force` tại §10 |
| R3-02 | 3 | Minor | Chưa có AC bảo đảm không tự chọn max_len | Đã thêm AC-14 |

### Code review — v1.0 — 2026-11-09

| Vòng | Kết quả | Bằng chứng |
|---|---|---|
| 1 — Khớp spec | READY | Registry khóa đúng 100 Behaviour và 24 Sequence; config từ §5 |
| 2 — Đúng đắn | READY | 4 unit/leakage tests qua; syntax 18 tệp qua |
| 3 — Chạy được | READY có điều kiện | `pytest`: 4/4 qua; normalize smoke qua. Full CERT chưa chạy nên AC-13/AC-14 chờ người dùng chạy |

Không có Blocker/Major trong code review. Điều kiện còn lại là thời gian chạy full dữ liệu và phân vị chuỗi thực tế, không phải thay đổi thiết kế/code.

## 14. Bổ sung v1.1 — checkpoint và resume

- `--resume` tái sử dụng canonical events khi manifest xác nhận đủ năm nguồn.
- Mỗi `user_bucket` chỉ được đánh dấu hoàn thành sau khi Behaviour, Sequence và OCEAN ablation (nếu có) đã được ghi atomic.
- Trạng thái lưu tại `data/artifacts/manifests/feature_checkpoint.json`; bucket có output thiếu hoặc checkpoint chưa hoàn thành phải chạy lại.
- `prepare_data.lock` được tạo độc quyền để chặn hai pipeline mới chạy đồng thời và luôn được giải phóng trong `finally`.
- Sau mỗi bucket in số bucket hoàn thành, thời gian bucket, tổng thời gian và ETA. Tắt máy giữa bucket chỉ làm lại bucket đó.
- Lệnh tiếp tục: `python scripts/prepare_data.py --config configs/base.yaml --resume`.

### Tiêu chí chấp nhận bổ sung

| # | Tiêu chí | Cách kiểm |
|---|---|---|
| AC-15 | Resume bỏ qua bucket đã hoàn thành và đủ output | unit test checkpoint |
| AC-16 | Bucket thiếu một output không được coi là hoàn thành | unit test checkpoint |
| AC-17 | Checkpoint JSON được ghi atomic sau output | unit test round-trip |
| AC-18 | Lock thứ hai bị từ chối, lock được giải phóng khi lỗi | unit test process lock |

### Code review v1.1

- Vòng 1 — khớp spec: READY; `--resume`, checkpoint output và process lock khớp §14.
- Vòng 2 — đúng đắn: READY; checkpoint chỉ ghi sau ba output atomic, canonical chỉ được bỏ qua khi manifest đủ năm nguồn.
- Vòng 3 — chạy được: READY; `pytest` 6/6 qua. Cảnh báo duy nhất là pytest không ghi được cache, không ảnh hưởng test.
