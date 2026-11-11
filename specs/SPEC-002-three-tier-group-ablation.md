---
id: SPEC-002
title: Chọn một tầng và giao diện nhận điểm, Department/Role
status: Implemented
version: 1.2
date: 2026-11-11
rq: [RQ2]
components: [C5, C6]
decisions: [DL-020, DL-021, DL-022, DL-023, DL-024, DL-025, DL-026, DL-027, DL-046, DL-053, DL-054, DL-055]
supersedes: null
---

# SPEC-002 — Ba tầng thống kê với hai định nghĩa Group

> **Implemented v1.2:** §1–13 giữ lịch sử implementation trộn điểm v1.0. §14 hiện hành triển khai bộ chọn duy nhất một tầng và giao diện nhận điểm ngoài, được người dùng accept trước khi code. Chưa có điểm mô hình, threshold mới hoặc kết luận case nào tốt hơn.

> **Yêu cầu thay đổi ngày 2026-11-10:** người dùng xác nhận phương pháp nhóm là chọn duy nhất một tầng: đủ lịch sử Personal thì chỉ chấm Personal; nếu thiếu thì xét Group; nếu Group không đủ thì dùng Global. Không trộn ba score. Nội dung v1.0 bên dưới mô tả implementation cũ và không phải thiết kế đích mới. Điều kiện đủ dữ liệu và hợp đồng score đang chờ chốt tại docs/three-tier-routing-change.md; chưa triển khai thay đổi thuật toán.

> **Phạm vi được xác nhận lại ngày 2026-11-09 (DL-041):** đây là spec chính cho nhiệm vụ hiện tại: Global–Department–Personal và Global–Role–Personal, Personal 30 ngày, Adaptive Backoff, score cuối và một threshold Calibration riêng mỗi case. Hai case chung dữ liệu, feature, temporal split và quy tắc hiệu chỉnh. Không mở rộng preprocessing/feature hoặc triển khai toàn bộ framework.

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

Lệnh sau triển khai: `.\.venv-validation311\Scripts\python.exe -m pytest -q`; CLI `.\.venv-validation311\Scripts\python.exe scripts/run_group_ablation.py --config <fixture-department.json> --config <fixture-role.json> --run-dir <new-run-dir>`. Thêm --include-test chỉ cho fixture trong đợt triển khai này. Thứ tự code: LDAP join → tiers/history → threshold → runner/config → test/smoke. Không cần cài thư viện.

Ước tính smoke dưới 1 phút trên CPU, VRAM=0; chưa đo. Quy mô CERT thật phải đo riêng, không tự chạy. Google Doc chỉ cập nhật khi code xong theo skill; bước thiết kế này không đẩy.

## 11. Rủi ro

Mean/std nhạy outlier; floor=1 là lựa chọn khởi đầu theo DL-025, chưa được tune. Personal cập nhật mọi quan sát có thể học dần hành vi độc hại; đây là protocol đã nêu để so sánh hai Group nhất quán, không khẳng định chống nhiễm bẩn. Global/Group cố định không theo concept drift; đây là 09A. Thiếu nhãn và split thật chưa chốt khiến chưa thể báo kết quả nghiên cứu.

## 12. Open Questions

Người dùng accept SPEC-002 ngày 2026-11-07, chuyển v1.0 theo DL-027. OQ-11→DL-025, OQ-12→DL-026. Các bộ số là khởi đầu, chưa tối ưu. Sau triển khai fixture, người dùng đã chốt OQ-02/OQ-03 theo DL-033/DL-034; lần chạy train/Calibration thật hoàn thành theo DL-035, kết quả trong docs/cert-first-calibration-results.md. Test đánh giá vẫn deferred.

## 13. Review readiness

Đã đọc lại file riêng cho từng vòng; chỉ review thiết kế, chưa chạy code SPEC-002.

| Vòng | Kết quả |
|---|---|
| 1 — Đầy đủ & truy vết | Đạt: lựa chọn 07A–12A truy tới DL-021–DL-026; có schema, công thức, tham số và 10 AC |
| 2 — Đúng đắn khoa học | Đã mô tả cửa sổ nhân quả, frozen train, nối split và p99 không nhãn; cùng mẫu và config giữa case; không tuyên bố FPR test hay hiệu quả nghiên cứu |
| 3 — Sẵn sàng dev | Đạt cho triển khai fixture: state/history, API, config kế thừa, artifact, lệnh và dependency đã rõ |

**Kết luận review spec: READY** — 0 Blocker, 0 Major mở cho triển khai module và kiểm chứng fixture. Đã bổ sung cơ học: thống nhất tên features_transform, chỉ đọc/hash test khi bật rõ, last_date và quy tắc state xuyên split, metadata thiếu và artifact của từng case. Bản draft v0.2 sau đó được người dùng accept thành v1.0 (DL-027). OQ-02/OQ-03 tiếp tục chặn chạy dữ liệu thật; kết quả triển khai ghi riêng bên dưới.

### Review code — v1.0 — 2026-11-07

| Vòng | Kết quả |
|---|---|
| 1 — Khớp spec | AC-01–AC-10 có kiểm chứng trong test_tiers, test_threshold, test_group_ablation; API Role cũ vẫn qua test |
| 2 — Đúng đắn | Test khớp tính tay, cold start, nhóm một người, biên cửa sổ, future invariance, nối split, đổi Group và frozen train đều qua; sửa cơ học kiểm định dạng ISO trong checkpoint |
| 3 — Chạy được & bàn giao | 101 test qua trong 2.68s; hai smoke giống score/threshold/artifact; mỗi case có 4 dòng Calibration và 2 dòng test giả; BA và tài liệu luồng local cập nhật |

**Code READY trong phạm vi thống kê/fixture SPEC-002.** Không có kết quả nghiên cứu CERT. Run `runs/20261107-spec002-smoke` có verification.json, pytest.xml và hai run độc lập. Google Doc chưa đồng bộ: vẫn thiếu kênh đọc bình luận/đọc lại theo yêu cầu skill, không tuyên bố bước online hoàn thành.

### Các lần chạy CERT sau nghiệm thu code

Sau khi chốt split/chính sách train, chạy train/Calibration tại `runs/20261107-cert-first-calibration/result` (DL-033–DL-035). Người dùng tiếp tục accept mở test lần 1 (DL-036); đã nạp trực tiếp baseline, checkpoint Personal và threshold đã lưu, không refit. Kết quả, phương pháp và giới hạn nhãn: `docs/cert-test-open-1-results.md`. Đây là đánh giá cấu hình đã duyệt, không thay đổi thiết kế spec; mọi chỉnh sửa sau khi xem test cần ghi nhận tính chất exploratory.

## 14. v1.2 — Bộ chọn một tầng và giao diện nhận điểm Department/Role

### 14.1 Phạm vi đã xác nhận

Người dùng yêu cầu giữ hai case và so sánh hiệu quả sau triển khai. Input metadata dùng bộ đã ghép theo SPEC-001 v1.1 tại data/processed/CERT-r4.2-processed-two-branch-v1-ldap/. Feature/sequence/OCEAN đã được bảo toàn; không tự chọn OCEAN làm input mô hình.

Chọn tầng theo dữ liệu quá khứ: Personal có ít nhất 7 ngày hoạt động hợp lệ trong [t−30,t) thì chỉ dùng Personal. Nếu thiếu, Group có ít nhất 2 nhân viên riêng biệt trong train và metadata hợp lệ thì chỉ dùng Group; nếu không dùng Global. Bộ 7 ngày/2 người được chọn sau khi người dùng giao chọn phương án khả thi, chưa phải tham số tối ưu. Không xét score cao/thấp hoặc nhãn để quyết định fallback; không tính/trộn score tầng không được chọn. Ngày hợp lệ cho router được định nghĩa tại §14.5, không phụ thuộc mô hình chưa có.

Hai case chỉ đổi group_key department/role. Output đợt này ghi routing, score tùy chọn và score_status. Threshold/is_alert chỉ bổ sung sau khi có protocol score/Calibration riêng; không tự sửa code v1.0 trước khi duyệt bản sửa đầy đủ.

### 14.2 Nguyên tắc so sánh

| Điều kiện | Yêu cầu |
|---|---|
| Dữ liệu | Cùng khóa user-day theo thứ tự, dữ liệu/feature hoặc score đầu vào, temporal split, policy train và mask |
| Personal/Global | Cùng lịch sử/chuẩn và quy tắc; Personal đủ dữ liệu phải tạo cùng score giữa hai case |
| Group thiếu | Giữ nguyên mẫu; fallback Global thay vì loại user-day theo từng case |
| Threshold | Một ngưỡng cuối riêng mỗi case; cùng quy tắc p99 Calibration, tính mới cho phương pháp chọn một tầng |
| Toàn tập | Báo hiệu quả cuối pipeline trên cùng tập đánh giá |
| Nhóm cần fallback | Báo thêm trên cùng tập ngày Personal chưa đủ dữ liệu, không dùng hai tập Group-khả-dụng khác nhau |
| Vận hành | Tỷ lệ chọn Personal/Group/Global, metadata thiếu, thời gian và số cảnh báo |

Ngay cả khi score Personal giống nhau, cờ cảnh báo có thể khác vì threshold cuối được Calibration riêng từng case. Không diễn giải mọi khác biệt cảnh báo trên nhóm Personal là tác động trực tiếp của Group.

### 14.3 Đề xuất tiêu chí hiệu quả, chưa chốt protocol cuối

Đề xuất dùng AP (average precision) làm chỉ số chính; báo thêm Precision, Recall, F1, FPR và Recall ở cùng ngân sách điều tra. Không dùng giá trị threshold nhỏ hơn hoặc số cảnh báo Calibration để kết luận tối ưu. Khi kết quả đánh đổi hoặc gần nhau, báo rõ chưa đủ bằng chứng có case tốt hơn.

Phân tích cold-start dùng cùng tập Personal-không-đủ và công bố số mẫu dương; tập con này là chẩn đoán, không thay thế đánh giá toàn tập. Nếu cần độ tin cậy thống kê, protocol phải chỉ rõ phép so sánh ghép cặp phù hợp phụ thuộc theo user/thời gian; không tự tạo nhiều seed cho logic deterministic hoặc tuyên bố ý nghĩa thống kê chỉ từ một run.

Test cũ đã từng được xem. Lần đánh giá phương pháp mới trên cùng test phải ghi exploratory, chỉ mở sau khi cấu hình đóng băng và người dùng xác nhận lần mở mới. Không chỉnh tham số dựa trên nhãn test rồi báo như đánh giá độc lập. Quyết định so sánh hai case không tự động cho phép mở test lúc spec còn draft.

### 14.4 Phạm vi triển khai được người dùng chọn

Người dùng xác nhận chưa có điểm mô hình: trước mắt chỉ làm bộ chọn tầng và giao diện nhận điểm, chưa kết luận case tốt hơn. Vì vậy output ở §14.1 được thu hẹp: ghi routing và score tùy chọn; không sinh threshold/is_alert. Các mục §14.2–14.3 là định hướng cho đợt đánh giá sau, không là lệnh chạy đánh giá lần này.

Không tính mean/std từ f001–f100, không dùng mask làm feature, không đọc sequence/OCEAN để tạo score. Không gọi công thức trộn v1.0 hoặc chuyển tầng khi điểm cao/thấp. Giao diện chỉ tiếp nhận điểm đã được bên cung cấp tính cho tầng được chọn; không tự nhận raw model error rồi đoán phép chuẩn hóa theo tầng.

### 14.5 Input dùng cho bộ chọn tầng

Chỉ đọc các cột user, day, role, department, role_missing, department_missing từ nhánh user_day_features của bộ đã ghép LDAP. Chuẩn hóa user cho khóa, giữ user gốc trong output; day là ngày ISO, không null/giờ khác 00:00. Hai cặp metadata/flag phải nhất quán (UNKNOWN ↔ missing=true). Không sửa giá trị nguồn.

Đầu vào Python API là list[dict] với user/day, hai metadata dạng string và hai cờ bool. Khóa normalized user/day phải duy nhất. Cùng một bảng được dùng cho cả hai case. Dữ liệu train cần ít nhất một user-day; không đọc feature float để suy ngày nào đủ chất lượng.

Trong phạm vi router, "ngày hợp lệ" là một user-day tồn tại với user/day hợp lệ trong bảng đã kiểm, không phải điều kiện mask toàn true, score có sẵn hoặc số năm công tác. Một ngày hoạt động được đếm một lần. Đây là routing theo lịch sử hiện có; độ khả dụng score của bên ngoài sẽ được kiểm riêng, không âm thầm đổi tầng nếu thiếu score.

Runner có split tường minh, giữ mốc đã chốt:

- Train: 2010-01-01 đến 2010-05-31, bao gồm hai biên; dữ liệu thực bắt đầu 2010-01-02.
- Calibration: 2010-06-01 đến 2010-09-30.
- Chưa có chế độ xử lý test trong CLI mới. Các file bucket chứa cả các ngày sau Calibration; đọc projection khóa/metadata để lọc theo ngày không phải mở score/nhãn hoặc đánh giá test. Bỏ khỏi input routing các ngày ngoài hai khoảng, ghi số dòng ngoài phạm vi; không tính chúng vào lịch sử hay cỡ nhóm.

Policy train giữ DL-034, train đã chuẩn bị sạch; router không sinh nhãn hoặc tự lọc insider. Hai khoảng ngày phải hợp lệ, không trùng và train kết thúc trước Calibration. Fixture có thể dùng ngày khác theo config.

### 14.6 Thuật toán chọn tầng và trạng thái

1. Từ train, tạo group_train_users riêng cho Department và Role: group hợp lệ → tập user riêng biệt. Nhân viên từng đổi nhóm có thể góp vào nhiều nhóm, đúng metadata của từng dòng train. Nhóm missing không tạo entry.

Membership Group cố định từ train, có tính chính user đang xét nếu từng thuộc nhóm đó trong train. Không loại chính user và không thêm user Calibration vào Group để đạt ngưỡng. Chuẩn hóa khoảng trắng trong user/group; group trống thành UNKNOWN. Trong JSON, sets thành danh sách user đã sort, giữ group/nhánh theo tên đã sort; khi nạp lại validate duy nhất và chuyển về set, không đếm list trùng thành nhiều người.

2. Khởi tạo Personal từ user-day train; trước mỗi ngày Calibration t, loại lịch sử trước t−30, chỉ đếm ngày nhỏ hơn t. Duyệt cả ngày xong mới thêm ngày t. Không tạo ngày zero và không reset khi đổi nhóm; gap split có thể làm lịch sử hết hạn.
3. Nếu n_personal_days≥7, trả personal ngay; không yêu cầu tra cỡ Group hoặc gọi provider Group/Global cho user-day đó.
4. Nếu Personal thiếu, đọc group hiện tại của đúng case: missing → global; chưa có trong train → global; có dưới 2 user riêng biệt → global; còn lại → group.
5. Global là fallback cuối; điều kiện có train không rỗng đã kiểm ở đầu. Không fit baseline số hoặc tính điểm ở bước này.

Trạng thái chứa last_date và lịch sử ngày mỗi user, không chứa feature hoặc score. Input sau phải có min(day)>last_date. Khi prune, giữ đúng [t−30,t); ngày t−30 có tính, t−31 không tính. Không cập nhật từ tương lai; thứ tự user cùng ngày không làm đổi kết quả. Lịch sử chung cả hai case nên n_personal_days luôn giống nhau.

History schema: {last_date: ISO YYYY-MM-DD, users: {normalized_user: [ISO day,...]}}. init_routing_history đặt last_date=max(train.day), từ chối max(train.day)≥first_day, chỉ giữ ngày trong [first_day−window_days,first_day). Mỗi list sort tăng, không trùng. Validate history bắt buộc ISO chuẩn, user không trống, không có ngày>last_date hoặc ≥ngày sắp route; list trùng/không tăng phải lỗi. Giữ last_date dù window rỗng để chặn replay.

Output routing:

| Cột | Hợp đồng |
|---|---|
| user, day, group_key, group_value | Định danh nhân viên/ngày và case; group_value là metadata hiện tại |
| selected_tier | personal, group hoặc global, đúng một giá trị |
| fallback_reason | personal_sufficient; personal_insufficient_group_sufficient; personal_insufficient_group_missing; personal_insufficient_group_unseen; personal_insufficient_group_too_small |
| n_personal_days | Số ngày đã biết trong cửa sổ quá khứ |
| n_group_users | null khi Personal được chọn; nếu đã xét Group thì đếm train, 0 khi missing/unseen |
| score, score_status | Mặc định null và awaiting_external_score; khi nhận điểm hợp lệ là số hữu hạn và provided |

Không có wP/wG/wGlobal hoặc score của tầng không chọn. Không ghi giá trị 0 vào score để thay cho điểm còn thiếu.

### 14.7 Giao diện nhận điểm ngoài

API `attach_selected_scores(routes, scores)` nhận danh sách điểm với schema user,day,group_key,selected_tier,score. Bên cung cấp nhận routing trước và chỉ cần trả một điểm cho tầng đã chọn mỗi case/user-day. Bên cung cấp tự chịu trách nhiệm định nghĩa/chuẩn hóa score theo tầng; bên nhận không học hoặc thay đổi phép biến đổi số.

Hợp đồng cặp case giả định cùng producer, phiên bản và định nghĩa score; chỉ Group khác nhau. API không thể suy ngữ nghĩa score từ số được gửi. Điểm pass-through không chứng minh Personal/Group/Global cùng thang hoặc đủ điều kiện hiệu chỉnh threshold.

- Khóa điểm là (normalized user,day,group_key), duy nhất; selected_tier phải khớp routing. Score là số thực hữu hạn, cho phép âm vì chưa áp đặt công thức; từ chối bool, null, NaN/Inf.
- Khi có nguồn điểm, yêu cầu đủ chính xác toàn bộ routing rows của hai case, không extra/duplicate/missing và không điểm cho tầng khác. Thiếu điểm tầng được chọn là lỗi cần sửa nguồn điểm, không fallback sang tầng khác.
- Score Personal và Global phải giống nhau nếu cùng user-day chọn cùng tầng đó ở cả hai case. Đây là điều kiện contract vì case chỉ khác Group; không so bằng nhau khi hai case chọn hai tầng khác nhau.
- Điểm được gắn nguyên giá trị; output vẫn giữ toàn bộ routing rows theo cùng thứ tự. Không có ngưỡng, nhãn, is_alert, AP hoặc kết luận tối ưu ở bước này.
- CLI nhận điểm từ CSV tùy chọn bằng `--scores <path>` đúng schema trên. Khi không có --scores, chạy routing-only thành công với score trống. Không tự nạp Python provider tùy ý từ config hoặc tự tính score giả trên dữ liệu thật.

Score ngoài lúc này là điểm cho tầng đã chọn, không đồng nghĩa raw error của Feature AE/Sequence model. Khi nhóm có raw model score, phép biến đổi score thành chuẩn từng tầng phải được thiết kế và duyệt ở một bản sửa sau, cùng nguyên tắc Calibration trước khi đánh giá.

### 14.8 API, tệp và config

| Tệp | API / vai trò |
|---|---|
| src/itd/scoring/routing.py | RoutingConfig(window_days=30,min_personal_days=7,min_group_users=2), frozen dataclass, chỉ nhận int hợp lệ, min_personal_days≤window_days |
| cùng module | fit_group_members(train_rows) → dict[case,dict[group,set[user]]]; init_routing_history(train_rows,first_day,config) → dict |
| cùng module | select_tier(n_personal_days,group_value,group_members,config) → dict lựa chọn; điều kiện Personal phải short-circuit |
| cùng module | route_days(rows,group_members,history,config) → (list[dict],new_history); trả đủ hai case, không sửa input/state gốc |
| src/itd/scoring/score_input.py | attach_selected_scores(routes,scores) → list[dict], pure validation/pass-through |
| scripts/run_tier_routing.py | Đọc hai config, Parquet projection, chia train/cal theo ngày, chạy routing; --scores tùy chọn |
| configs/experiments/tier_routing_common.json | Input enriched Feature, ngày train/cal, batch_rows, routing thresholds; paths resolve từ gốc project khi chạy CLI tại root |
| configs/experiments/tier_routing_department.json và tier_routing_role.json | Chỉ extends common và group_key, không override khoa học từng case |
| tests/test_routing.py, tests/test_score_input.py, tests/test_tier_routing_cli.py | Logic, leakage, contract score, end-to-end fixture và bảo vệ output |

Hai case bắt buộc đủ role/department, fingerprint common phải giống. Common gồm paths.feature_dir, split.train.start/end, split.calibration.start/end, routing.window_days=30, routing.min_personal_days=7, routing.min_group_users=2, batch_rows=65536; không tune. Dùng Python3.11, PyArrow19.0.1, NumPy1.26.4, pytest8.3.5 đã có; không cài dependency mới.

Trong select_tier, group_members là dict[str,set[str]] của một case, n_personal_days là int không âm (không bool), group_value là chuỗi chuẩn hóa. Config: window_days≥1, 1≤min_personal_days≤window_days, min_group_users≥2. route_days sort theo ngày, normalized user rồi case; CSV mỗi case cùng thứ tự ngày/user. Count sai kiểu hoặc membership user không hợp lệ phải lỗi; input/state gốc không bị sửa.

CLI lặp --config hai lần, --run-dir bắt buộc mới và --scores tùy chọn. Validate toàn bộ và chuẩn bị output trong staging cùng cha; chỉ publish khi cả hai case và score contract đều đạt. Không chạm runner trộn điểm lịch sử trong commit 7331adf hoặc import nó để tạo kết quả mới; nhánh làm việc hiện tại chỉ có enrichment và router mới sẽ dùng tên riêng để tránh gọi nhầm phương pháp cũ.

Artifact: config.json resolved, manifest.json (schema projection, hash Parquet đã đọc, hash score CSV nếu có, user-day count/date range, fingerprint chung, số row ngoài split), metrics.json chỉ có số dòng, số/tỷ lệ tầng, lý do fallback, missing metadata và thời gian; history_after_calibration.json chung; department/routes.csv và role/routes.csv; env.txt, git.txt, log.txt. Không xuất threshold.json hoặc metrics nhãn. Lịch sử nhân viên và artifact không được commit dữ liệu.

### 14.9 AC và kiểm thử bắt buộc

| ID | Kiểm chứng |
|---|---|
| R-01 | Cùng user-day và n_personal_days ở hai case; chỉ Group metadata/membership khác nhau |
| R-02 | Đúng 7 ngày chọn Personal, 6 ngày xét Group; Personal đủ không truy cập Group/provider tầng khác |
| R-03 | Group đúng 2 người dùng được; 1 người/missing/unseen → Global, không mất row |
| R-04 | Biên t−30/t−31, không ngày t/tương lai; sửa ngày sau t không đổi routing tại t |
| R-05 | Đổi thứ tự user, chia luồng thành hai đoạn liên tiếp hoặc đổi Group không làm reset lịch sử; cấm replay/overlap history |
| R-06 | Một selected_tier và một score slot mỗi row; routing-only có null/awaiting, không giả score/threshold |
| R-07 | Điểm ngoài đủ đúng case/user-day/tier và hữu hạn; thiếu/trùng/thừa/sai tầng/NaN/Inf/bool bị chặn, không đổi tầng |
| R-08 | Pass-through không sửa giá trị score; Personal/Global chung phải nhất quán giữa case khi cùng chọn |
| R-09 | Dữ liệu input/history/config sai schema/key/date/flag phải lỗi; input/state không bị sửa |
| R-10 | CLI fixture hai lần cho cùng routing; common mismatch bị chặn, không ghi đè run, lỗi không publish output dở |

Fixture ít nhất 3 user, 2 tháng, nhóm khác nhau, 1 người mới, 1 metadata thiếu, 1 Group train nhỏ. Có từ 6 lên 7 ngày, gap làm lịch sử hết hạn, đổi nhóm, điểm mô phỏng rõ là synthetic. Chạy lại 21 test ghép LDAP của SPEC-001 v1.1 để bảo vệ đường vào; không khôi phục hoặc chạy code test cũ dựa trên trộn điểm như tiêu chí cho router mới.

### 14.10 Lệnh và thứ tự thực hiện sau duyệt

```powershell
.\.venv-validation311\Scripts\python.exe -m pytest tests/test_routing.py tests/test_score_input.py tests/test_tier_routing_cli.py tests/test_enrich_ldap.py -q
.\.venv-validation311\Scripts\python.exe scripts/run_tier_routing.py --config configs/experiments/tier_routing_department.json --config configs/experiments/tier_routing_role.json --run-dir runs/<new-routing-run>
```

Khi có điểm ngoài, thêm --scores <selected-layer-scores.csv>. Triển khai thuần router → score adapter → CLI/config → test fixture → routing-only train/Calibration trên metadata thật → BA/tài liệu. Không đọc nhãn, fit score, tạo threshold hoặc đánh giá test. Ước tính fixture dưới một phút và chạy metadata 330k user-day trên CPU dưới vài phút, cần đo thực tế; VRAM=0, không cần seed cho logic deterministic.

### 14.11 Review và trạng thái

Bản v1.2 đã giải quyết lựa chọn phạm vi: bộ chọn tầng và giao diện, chưa có hiệu quả phát hiện để so sánh. Protocol scoring/Calibration/đánh giá sau được tách khỏi AC hiện tại, không chặn router. Chưa code v1.2 hoặc chạy routing thật.

| Vòng | Kết quả |
|---|---|
| 1 — Đầy đủ và truy vết | Đã đọc lại; DL-046/053–055, metadata đã ghép, schema/API/config/artifact và R-01–R-10 đầy đủ cho router-only |
| 2 — Đúng đắn khoa học, review độc lập | Đã đọc lại; không dùng tương lai/nhãn/score để chọn tầng; hai case cùng lịch sử/cohort. Đã bổ sung history chuẩn và frozen membership tính cả chính user; adapter không tự biến đổi score |
| 3 — Sẵn sàng dev | Đã đọc lại; tệp mới, chữ ký, CLI, dependency, lệnh và test rõ; không cần cài thêm. Đã sửa cơ học tiêu đề/đoạn scope và serialization sorted; không còn Blocker/Major trong phạm vi hiện tại |

**READY để trình duyệt SPEC-002 v1.2**. Chỉ triển khai sau khi người dùng accept bản sửa này; lựa chọn phạm vi DL-055 không được ghi thay cho phê duyệt spec cuối. Giới hạn cố ý: chưa có AP/FPR, threshold hoặc kết luận tối ưu vì chưa có hợp đồng score đánh giá.

### 14.12 Review code và bàn giao v1.2 — 2026-11-11

Người dùng accept SPEC-002 v1.2, DL-056. Module routing.py và score_input.py, runner run_tier_routing.py, ba config tier_routing_*.json và ba file test đã triển khai. Các ghi chú Draft/chờ duyệt ở các mục trước là lịch sử review.

| Vòng code | Kết quả |
|---|---|
| 1 — Khớp spec | R-01–R-10 có test; một tầng và một score slot, Personal short-circuit, membership train cố định, history chung và CSV score exact coverage |
| 2 — Đúng đắn, có review độc lập | Không phát hiện Blocker/Major; kiểm ngày/nhóm/thiếu điểm/atomic output. Đối soát count history bằng thuật toán bisect độc lập khớp mọi row thật |
| 3 — Chạy và bàn giao | 151 test qua trong 12.91s, gồm 21 test enrichment; run thật routing-only train/Calibration 6.723866s. Hướng dẫn docs/three-tier-usage.md |

Mỗi case có 84.066 row Calibration, tất cả chọn Personal; số ngày lịch sử nhỏ nhất 19, lớn nhất 30. Group/Global bằng 0 vì dữ liệu Calibration không có user-day dưới 7 ngày. Hai case cùng cohort và lịch sử; score trống/awaiting_external_score; không có threshold/is_alert hoặc metric nhãn. Không kết luận case tối ưu hoặc tự đổi điều kiện để ép sử dụng Group.

Run thật: runs/20261111-spec002-tier-routing. Bằng chứng kiểm thử/đối soát: runs/20261111-spec002-routing-validation/{pytest.xml,verification.json}. **Code READY đúng phạm vi router + giao diện**, chưa phải pipeline score/Calibration/đánh giá hoàn chỉnh.
