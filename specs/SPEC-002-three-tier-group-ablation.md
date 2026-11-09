---
id: SPEC-002
title: Ba tầng Global–Group–Personal, ablation Department/Role
status: Draft
version: 0.1
date: 2026-11-09
rq: [RQ2]
components: [C5, C6]
decisions: [DL-020, DL-021, DL-022, DL-023, DL-024, DL-025, DL-026, DL-027]
supersedes: null
---

# SPEC-002 — Ba tầng thống kê với hai định nghĩa Group

## 1. Mục tiêu

Triển khai phiên bản thống kê feature nhằm so sánh Group theo phòng ban và chức vụ cho RQ2, Gap 2 trong research-proposal.md của skill. Personal lấy lịch sử 30 ngày; Adaptive Backoff hợp nhất score ba tầng. Một threshold cuối của mỗi case là phân vị 99% score Calibration. Đây là phiên bản thống kê đối chứng, chưa phải hai mô hình tái tạo của RQ1 hoặc threshold cập nhật định kỳ của RQ3.

## 2. Phạm vi

- Hai cấu hình kế thừa chung tham số, chỉ khác group_key=department hoặc role.
- Mở rộng ghép LDAP để giữ cả department và role, kèm trạng thái thiếu của từng trường. Giữ CLI ghép Role cũ tương thích.
- Global/Group fit trên train, Personal xử lý theo ngày xuyên Calibration/test, cập nhật sau khi chấm.
- Lưu score thành phần, trọng số, score cuối và artifact threshold; runner kiểm tra hai case dùng cùng dữ liệu/config chung.
- Triển khai và smoke trên fixture trước. Chạy thật phụ thuộc OQ-02/OQ-03 và xác nhận mở test; không tự chạy test nghiên cứu.

## 3. Dữ liệu vào / ra

| Đối tượng | Schema / shape | Quy tắc |
|---|---|---|
| Feature data | user_id, date, sáu count như SPEC-001 | duy nhất user-day, hữu hạn, không âm |
| LDAP | user_id, role, department, từng file YYYY-MM.csv | tra đúng tháng; thiếu giá trị → UNKNOWN, không loại mẫu |
| Train/calibration/test | ba tập tách ngày; max(train)<min(cal)<min(test) | cùng các dòng/thứ tự chuẩn cho hai case |
| Baseline | mean/std shape (6,); n_users Group | ddof=0; thống kê theo user-day |
| scores.csv | user_id,date,group_key,group_value,n_history,n_group_users,s_global,s_group,s_personal,w_global,w_group,w_personal,score,threshold,is_alert | tầng không dùng có score trống và weight=0 |
| threshold.json | case,quantile,method,threshold,calibration_dates,calibration_count | mỗi case một artifact; p=0.99, method=linear |

Thống kê dùng raw count và scale floor=1 theo DL-025. Group trong train được gán theo metadata cùng tháng của dòng train; khi chấm dùng Group hiện tại của tháng tương ứng. Một người có thể đóng góp vào hai Group ở hai giai đoạn khác nhau. n_group_users đếm user riêng biệt trong train của Group, không đếm user-day.

## 4. Thiết kế

### 4.1 Fit train và khởi tạo lịch sử

X_train shape (N,6); Global fit mọi dòng train. Mỗi Group hợp lệ fit các dòng train thuộc Group đó. Không fit lại Global/Group từ Calibration/test. Metadata hai trường dùng chung một bảng; Group thiếu/không xuất hiện trong train backoff về Personal/Global.

Trước Calibration, khởi tạo lịch sử Personal bằng các dòng train trong cửa sổ 30 ngày tương ứng ngày đầu Calibration. Mỗi ngày t loại ngày <t-30; chỉ giữ ngày <t. Ngày không có hoạt động không tự thêm dòng zero. Khoảng trống giữa các split có thể khiến lịch sử rỗng.

### 4.2 Score tầng — đã chọn 07A

Với tầng L có dữ liệu, dùng raw count và floor=1 cho cả sáu feature (DL-025):

```
z_L,j = (x_j - mu_L,j) / max(std_L,j, 1)
s_L = mean_j(max(0, z_L,j))
```

mu/std fit trên raw count. Trung bình lấy trên đủ sáu feature, không thay số feature giữa case. Personal tính mu/std từ lịch sử hiện có, ddof=0. Thiếu số ngày tối thiểu thì không dùng tầng Personal. Không lấy giá trị tuyệt đối hoặc bình phương z; hoạt động giảm không đóng góp score theo lựa chọn này.

### 4.3 Adaptive Backoff — đã chọn 08A

```
n = số ngày hoạt động riêng biệt trong lịch sử Personal
m = số user riêng biệt của Group trong train
w_P = n/(n+k_P) nếu n >= min_personal_days, ngược lại 0
r_G = m/(m+k_G) nếu Group hợp lệ và m >= min_group_users, ngược lại 0
w_G = (1-w_P)*r_G
w_O = 1-w_P-w_G
score = w_P*s_P + w_G*s_G + w_O*s_O
```

Chỉ cộng score tầng có weight>0; không nhân 0 với NaN. Nếu cả Personal/Group không khả dụng thì w_O=1. Theo DL-026: k_P=7 ngày, k_G=3 người, min_personal_days=2 và min_group_users=2. Hai case luôn dùng cùng bộ giá trị. k_P,k_G phải hữu hạn dương; các cỡ mẫu tối thiểu là số nguyên >=2.

### 4.4 Chấm ngày và nối split — đã chọn 09A

Sắp xếp ngày tăng dần, user_id tăng dần trong ngày. Tính toàn bộ score ngày t trước khi thêm mọi dòng ngày t vào Personal. Cập nhật mọi quan sát hợp lệ, kể cả score cao; không dùng nhãn hoặc threshold để lọc lịch sử. Kết thúc Calibration giữ trạng thái Personal rồi tiếp tục test; không reset hoặc nạp dữ liệu test trước thời điểm chấm. Mỗi lần gọi score_days trả trạng thái mới, không tự sửa trạng thái đầu vào; hai case có state độc lập cùng khởi tạo.

### 4.5 Threshold — đã chọn 10A

Tính tau_case=np.quantile(calibration_scores, 0.99, method='linear') riêng từng case. Calibration phải không rỗng và mọi score hữu hạn. Test cảnh báo khi score>tau_case (không dùng >=). Khi score bằng nhau tại phân vị, tỷ lệ cảnh báo Calibration có thể thấp hơn 1%; test không được bảo đảm FPR=1%.

Giữ threshold cố định suốt test; không fit vào train score hoặc xem nhãn để chọn p. Không tune tham số backoff trong đợt này; cả hai dùng cấu hình đã duyệt giống nhau.

### 4.6 So sánh công bằng và artifacts

Lưu hash nội dung input, khóa user-day, danh sách/thứ tự features, split manifest, config chung và fingerprint config trừ group_key. Mismatch thì dừng trước so sánh. Không xóa riêng dòng UNKNOWN. Lưu artifact từng case trong một run mới, từ chối ghi đè run cũ. Trước khi chạy test thật cần thao tác riêng xác nhận mở test; mặc định runner chỉ fit train và Calibration.

## 5. Tham số

| Khóa config | Giá trị | Tình trạng |
|---|---|---|
| group_key | department / role | DL-020 |
| personal.window_days | 30 | DL-020 |
| scoring.aggregation | mean_positive_z | DL-021 |
| baseline.update | frozen_train_global_group, rolling_personal | DL-023 |
| threshold.quantile / method / comparison | 0.99 / linear / > | p theo DL-024; chi tiết API đề xuất trong spec |
| features_transform / scoring.scale_floor | identity / 1.0 | DL-025 |
| backoff.k_P / k_G / min_personal_days / min_group_users | 7 / 3 / 2 / 2 | DL-026 |
| paths / split manifests | bắt buộc truyền qua config | split thật chờ OQ-02/OQ-03 |

Không tự tune hoặc đưa tham số chưa chốt vào code. Config JSON dùng thư viện chuẩn trong runner, không thêm YAML dependency vào môi trường hiện tại. Config cuối lưu nguyên văn theo run.

## 6. Tệp và hợp đồng hàm dự kiến

| Tệp | Thay đổi / API |
|---|---|
| src/itd/data/ldap.py | thêm load_monthly_groups(ldap_dir: Path, group_key: str) -> dict; join_groups(rows: list[dict], metadata: dict) -> list[dict]; giữ API Role cũ |
| src/itd/scoring/tiers.py | TierConfig dataclass; fit_baselines(train_rows: list[dict], config: TierConfig) -> dict; score_days(rows: list[dict], baselines: dict, history: dict, config: TierConfig) -> tuple[list[dict],dict] |
| src/itd/scoring/threshold.py | calibrate_threshold(scores: np.ndarray, p: float) -> float; apply_threshold(scores: np.ndarray, threshold: float) -> np.ndarray |
| scripts/run_group_ablation.py | main(); --config; --run-dir; --include-test chỉ chấp nhận sau quyết định mở test, mặc định false |
| configs/experiments/group_ablation_common.json | đường dẫn, features, split manifest và các giá trị được duyệt dùng chung |
| configs/experiments/group_department.json, group_role.json | extends common, chỉ đổi group_key |
| tests/test_tiers.py, test_threshold.py, test_group_ablation.py | unit, leakage, CLI fixture |

### 6.1 State và baseline

TierConfig có các field đúng §5; features luôn là tuple sáu count theo thứ tự SPEC-001. Baseline dict gồm global:{mean,std,n_samples}, groups:{group_value:{mean,std,n_samples,n_users}}, group_key, train_start, train_end, config. mean/std là ndarray float64 shape (6,); serialization đổi sang list, JSON cấm NaN/Inf. Không tạo Group UNKNOWN. Một Group không đủ min_users vẫn có thể lưu thống kê nhưng w_G=0 và s_group trống khi chấm.

History dict gồm last_date (ISO hoặc null), users:{user_id:[(date ISO, sáu giá trị float)]}; record theo ngày tăng, duy nhất user-day. Hàm init_history(train_rows: list[dict], first_day: date, config: TierConfig) -> dict chỉ nhận train_rows trước first_day, giữ cửa sổ tương ứng. score_days yêu cầu ngày đầu >last_date nếu last_date có giá trị; từ chối gọi chồng ngày hoặc record tương lai trong history. Prune trước tính score; lưu raw count trong history. Không dùng train để sinh score nhân quả ngược về các ngày train.

load_monthly_groups trả mapping (month,user_id)→chuỗi của group_key. join_groups nhận metadata dạng {role: mapping, department: mapping}, tạo bản sao row thêm role/department và hai cờ missing. File LDAP thiếu hẳn cột bắt buộc phải báo lỗi; ô rỗng hoặc không tìm thấy user-tháng trả UNKNOWN. Không dùng các cờ missing trong vector features. Giữ các API Role SPEC-001 để test cũ tiếp tục qua.

### 6.2 Config và runner

Common JSON có paths:{train,calibration,test,ldap_dir}, features:[sáu tên], personal:{window_days:30}, scoring:{aggregation:mean_positive_z,scale_floor:1}, backoff:{k_P:7,k_G:3,min_personal_days:2,min_group_users:2}, threshold:{quantile:0.99,method:linear,comparison:gt}, baseline:{update:frozen_train_global_group}, features_transform:identity, dataset_kind:synthetic hoặc cert, data_policy:{split_confirmed:false,malicious_in_train:null}. Các file case có extends là đường dẫn relative tới common và group_key; chỉ cho phép hai key này trong overlay, không kế thừa nhiều cấp. Đường dẫn dữ liệu resolve relative tới file common.

CLI nhận lặp `--config` đúng hai lần, một department và một role. Runner resolve/validate hai config trước mở file dữ liệu, từ chối khác config chung, NaN/Inf tham số hoặc group_key ngoài hai giá trị. Run-dir phải chưa tồn tại. train/calibration bắt buộc không rỗng; test chỉ mở khi --include-test. Mặc định không hash/đọc/stat nội dung test; manifest ghi test là deferred. Khi bật test kiểm tra đủ ngày tách biệt và user-day không trùng. Input CSV dùng validation SPEC-001 trước join; user_id strip cho khóa và giữ lại ID gốc trong output.

Với dataset_kind=cert, phải chốt OQ-02/OQ-03 trước khi chạy fit: split_confirmed=true và malicious_in_train có giá trị đã duyệt; đây là khai báo truy vết, runner không tự sinh nhãn/lọc insiders. Bộ dữ liệu train đã chuẩn bị theo chính sách đó là đầu vào. --include-test với CERT chỉ dùng sau quyết định mở test của người dùng, không được tự chạy trong smoke. Fixture synthetic được phép test end-to-end, dùng chung protocol; không xem đó là mở test nghiên cứu.

Run lưu config.json (hai config đã resolve), manifest.json (hash SHA-256 input đã đọc, khóa user-day theo split, features và fingerprint chung), env.txt, git.txt, log.txt, metrics.json. Mỗi case lưu baselines.json, calibration_scores.csv, threshold.json, history_after_calibration.json; khi có test thêm test_scores.csv và history_after_test.json. Calibration_scores được thêm threshold/is_alert sau khi hoàn thành Calibration; chỉ là chẩn đoán retrospective, không báo như hiệu quả held-out. CSV score tầng không khả dụng ghi ô trống; score cuối và trọng số luôn hữu hạn. metrics.json chỉ chứa số mẫu, số cảnh báo, threshold và thời gian; chưa có metrics nhãn.

Config templates production có paths null để người chạy điền, không đoán đường dẫn D: hay mốc split chưa chốt. Fixture config được test tạo vào tmp_path; tests phải chứng minh overlay chỉ đổi group_key và đường dẫn resolve đúng. init_history đặt last_date=max ngày train nhận vào, kể cả record đã hết cửa sổ; lịch sử chỉ giữ record còn hạn. User chuyển Group vẫn giữ Personal của chính user; mọi nhóm có thể chứa chính user đang chấm nếu user đó thuộc nhóm trong train. Không loại user đó khỏi Group ở thời điểm chấm.

## 7. Thí nghiệm và chỉ số

Đợt đầu chỉ smoke fixture hai case; báo số mẫu, score, weight, threshold, số cảnh báo và tính tái lập, không kết luận case nào tốt hơn. Khi chạy nghiên cứu thật ở spec đánh giá tiếp theo mới báo PR-AUC/FPR/Recall có nhãn và kiểm định. Thuật toán thống kê này deterministic, không tạo seed giả để tuyên bố ý nghĩa thống kê.

## 8. Tiêu chí chấp nhận

| ID | Kiểm chứng |
|---|---|
| AC-01 | Hai config chỉ khác group_key, cùng khóa user-day/features/split |
| AC-02 | LDAP join đúng tháng cho cả hai trường; thiếu một trường không làm mất dòng |
| AC-03 | Mean positive z khớp tính tay và scale floor đã duyệt |
| AC-04 | w_P+w_G+w_O=1; weights hữu hạn không âm; người mới/nhóm nhỏ fallback đúng |
| AC-05 | Personal [t-30,t), ngày hiện tại/ngày tương lai không ảnh hưởng score tại t |
| AC-06 | Sửa Calibration/test không đổi artifact Global/Group train |
| AC-07 | Personal liên tục qua split, hết hạn 30 ngày đúng; thứ tự user cùng ngày không làm đổi score |
| AC-08 | p99 linear khớp NumPy; score=tau không cảnh báo; threshold giữ cố định trên test |
| AC-09 | UNKNOWN không bị loại; finite validation; score tầng thiếu không làm NaN score cuối |
| AC-10 | Chạy fixture hai lần giống score/threshold; artifact có fingerprint và run không ghi đè |

## 9. Kế hoạch test

Fixture ít nhất ba user, hai department và hai role với phân nhóm khác nhau; một người mới, một metadata thiếu, một Group chưa có trong train, một feature hằng. Các ngày gồm đúng t-30, t-31, t, t+1 và khoảng trống split. Test chèn/sửa ngày tương lai, đổi thứ tự user và nối split so với một luồng ngày liên tục. Thử hai metadata giống nhau: output hai case phải giống nhau. Chạy lại toàn bộ test SPEC-001.

## 10. Thực thi dự kiến

Người dùng accept → code → unit/leakage tests → smoke synthetic → BA. Môi trường có sẵn Python 3.11.9, NumPy 1.26.4, pytest 8.3.5; không thêm dependency.

Lệnh sau triển khai: `..\.venv-validation311\Scripts\python.exe -m pytest -q`; CLI `..\.venv-validation311\Scripts\python.exe scripts/run_group_ablation.py --config <fixture-department.json> --config <fixture-role.json> --run-dir <new-run-dir>`. Thêm --include-test chỉ cho fixture trong đợt triển khai này. Thứ tự code: LDAP join → tiers/history → threshold → runner/config → test/smoke. Không cần cài thư viện.

Ước tính smoke dưới 1 phút trên CPU, VRAM=0; chưa đo. Quy mô CERT thật phải đo riêng, không tự chạy. Google Doc chỉ cập nhật khi code xong theo skill; bước thiết kế này không đẩy.

## 11. Rủi ro

Mean/std nhạy outlier; floor=1 là lựa chọn khởi đầu theo DL-025, chưa được tune. Personal cập nhật mọi quan sát có thể học dần hành vi độc hại; đây là protocol đã nêu để so sánh hai Group nhất quán, không khẳng định chống nhiễm bẩn. Global/Group cố định không theo concept drift; đây là 09A. Thiếu nhãn và split thật chưa chốt khiến chưa thể báo kết quả nghiên cứu.

## 12. Open Questions

Không còn câu hỏi thiết kế chặn fixture khi kế thừa nguyên trạng phương pháp nguồn. Chờ người dùng duyệt tiếp nhận SPEC-001/002 tại Team-8. OQ-02/OQ-03 ở BA Team-8 tiếp tục chặn dữ liệu CERT thật.

## 13. Review readiness tại Team-8

Đã review riêng ba vòng cho phạm vi chuyển code và fixture ngày 2026-11-09. Chưa chạy test tại Team-8.

| Vòng | Lăng kính | Blocker | Major | Kết quả |
|---|---|---|---|---|
| 1 | Đầy đủ và truy vết | 0 | 0 | Có schema, công thức, API, AC; snapshot DL nguồn tách khỏi DL Team-8 |
| 2 | Đúng đắn khoa học | 0 | 0 | Review độc lập: frozen train, Personal nhân quả, p99 Calibration, so sánh cùng dữ liệu |
| 3 | Sẵn sàng dev | 0 | 0 | Có danh sách tệp, dependency pin, interpreter cha, test và smoke hai lần |

**Kết luận: READY để trình duyệt**, chưa phải code READY. Sửa cơ học: bỏ kết quả run nguồn; sửa đường dẫn interpreter; bỏ bước cài môi trường không cần thiết; chỉ rõ provenance DL. Khi nghiên cứu thật, cần bổ sung các đối chứng RQ2 và xác minh thời điểm snapshot LDAP khả dụng; chưa đưa ra kết luận nghiên cứu trong phạm vi fixture.

## 14. Phạm vi chuyển sang repository Team-8 — 2026-11-09

Đây là bản đề xuất kế thừa thiết kế từ repository cha, chưa phải nghiệm thu code tại Team-8. Các DL của thiết kế nguồn được chụp lại tại docs/design-decisions-source.md, tách khỏi Decision Log của Team-8. Cần người dùng duyệt bản chuyển trước khi code.

Khi được duyệt, chuyển các module, config và test tương ứng từ repository cha; giữ nguyên công thức, API và tham số. Dùng Python có sẵn tại ..\.venv-validation311\Scripts\python.exe, không cài thư viện. Chỉ chạy fixture giả; dữ liệu CERT và kết quả nghiên cứu nguồn không được sao chép hay đánh giá lại.

SPEC-001 là phụ thuộc dữ liệu của SPEC-002. Hai spec được trình như một gói triển khai ba tầng. Các DL dẫn ở trên thuộc tài liệu BA nguồn tại docs/design-decisions-source.md; sẽ ghi quyết định tiếp nhận ở BA Team-8 khi người dùng duyệt. Việc chọn repository A chỉ xác nhận nơi triển khai.

Lệnh test tại gốc Team-8 sau triển khai: `..\.venv-validation311\Scripts\python.exe -m pytest -q`. Runner và config giữ đúng §6/§10. Smoke synthetic chạy hai lần trong run mới; đối chiếu score, threshold và baseline, bỏ qua thời gian chạy khi so sánh. Ước tính dưới 1 phút CPU, VRAM 0; cần đo thực tế.

Google Doc chỉ được cập nhật sau code READY và cập nhật BA; cần đọc comment trước và đọc lại sau khi đẩy. Bản local được viết riêng cho trạng thái Team-8.
