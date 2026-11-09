# Phát hiện Insider Threat — Tài liệu BA

Tài liệu sống của project: hệ thống đang làm gì, đã code tới đâu, chạy thế nào, vì sao quyết định như vậy. Cập nhật **mỗi lần code**; mọi thay đổi có một dòng Decision Log.

Bản 2026-11-09 · Version 0.26

## 1. Tổng quan

**Phạm vi nhiệm vụ hiện tại (DL-041): chỉ kiến trúc ba tầng theo SPEC-002.** Hai case Global–Department–Personal và Global–Role–Personal; Personal 30 ngày, Adaptive Backoff, Final Anomaly Score, một threshold cuối hiệu chỉnh trên Calibration mỗi case. Hai case chung dữ liệu, feature, temporal split và nguyên tắc hiệu chỉnh. SPEC-001 là hồ sơ hỗ trợ đã làm; SPEC-003 đã rút, không mở rộng feature hoặc triển khai toàn bộ framework. Các mục RQ1–RQ3/C1–C7 bên dưới là bối cảnh nghiên cứu rộng hơn, không phải nhiệm vụ tiếp theo.

- **Mục tiêu**: phát hiện insider threat bằng anomaly detection kết hợp 2 luồng (chuỗi + đặc trưng), chuẩn hành vi 3 tầng Personal – Group – Global, ngưỡng thích ứng.
- **Câu hỏi nghiên cứu**: RQ1 · RQ2 · RQ3 (nguyên văn: `references/research-proposal.md` của skill `insider-threat-model-dev`).
- **Dữ liệu**: CERT r4.2 (DL-007). Số user, số insider, khoảng ngày ghi sau khi đếm từ dữ liệu thật.
- **Nơi code**: `D:\AI for BA\MW\Framework-rework` (DL-005). Cấu trúc thư mục: `README.md` § Cấu trúc.

## 2. Trạng thái thành phần

| Thành phần | Spec | Trạng thái | Test | Run gần nhất |
|---|---|---|---|---|
| C1 Dữ liệu & nhãn | SPEC-001 v1.0 (một phần) | Xong ghép Role/validation; phần nhãn chưa nghiệm thu | 61 test toàn phạm vi | 20261106-spec001-validation |
| C2 Luồng đặc trưng | | Chưa làm | | |
| C3 Luồng chuỗi | | Chưa làm | | |
| C4 Hợp nhất điểm | | Chưa làm | | |
| C5 Chuẩn 3 tầng | SPEC-002 v1.0 | Hai case đã đánh giá test lần 1 với baseline và tham số cố định | 101 test phần mềm đã qua; metric được đối soát | 20261107-cert-test-open-1 |
| C6 Ngưỡng thích ứng | SPEC-002 v1.0 | Đã lưu p99 Calibration cho hai case; ngưỡng cập nhật thời gian RQ3 còn ở bước sau | Kiểm lại p99 và score hữu hạn đạt | 20261107-cert-first-calibration/result |
| C7 Đánh giá & ablation | SPEC-002 · test lần 1 | Đã đối chiếu hai case trên test cố định; module đánh giá tổng quát chưa đóng gói | Metric đối soát đạt | 20261107-cert-test-open-1 |

Trạng thái: Chưa làm · Spec draft · Spec accepted · Đang code · Xong · Cần sửa.

## 3. Dữ liệu

Kiểm kê ngày 2026-11-07 tại `D:\CERT_r4.2`: 330.452 user-day, 1.000 user, 2010-01-02 → 2011-05-17. Train 105.171 dòng, Calibration 84.066, Test 141.215; ba split không giao nhau và hợp khớp bảng tổng. Đây là split prototype hiện có, OQ-02 chưa được chốt. Chưa tìm thấy nguồn nhãn ở các vị trí kiểm tra; chưa xác định số insider/ngày độc hại. Chi tiết và giới hạn: `docs/cert-data-inventory.md`; bằng chứng: `runs/20261107-cert-inventory/inventory.json`.

## 4. Pipeline

Audit mới nhất DL-038 đã giải quyết giới hạn đối soát event ID: 7.323 sự kiện đáp án khớp raw, sáu count khớp toàn bộ processed, score/metric được tính lại độc lập. Kết quả và giới hạn còn lại: `docs/label-pipeline-audit.md`. Các ghi chú chưa đối soát ID ở các lần ghi trước mô tả trạng thái lịch sử.

Cập nhật dữ liệu sau kiểm kê: đã có đáp án CMU, 986 user-day có sự kiện độc hại theo file sự kiện r4.2 (train 0, Calibration 471, test dự kiến 515). Đã khớp khóa user-day, chưa đối soát raw event ID. Split đã chốt theo DL-033; chính sách train theo DL-034. Kết quả chạy thật và giới hạn: `docs/cert-first-calibration-results.md`.

Pipeline SPEC-002 đã kiểm chứng fixture: feature CSV đã chia tập → ghép Role và Department đúng tháng → fit Global/Group từ train → chấm Calibration với Personal 30 ngày → tính threshold p99 mỗi case → chấm test fixture với threshold cố định. Các script tổng hợp log/chia tập thật còn ở dạng prototype; hai mô hình tái tạo chưa triển khai.

## 5. Thành phần

- **Ghép Role**: `src/itd/data/ldap.py`, CLI `scripts/attach_roles.py`. Hệ thống lấy chức vụ đúng tháng và trả UNKNOWN khi thiếu thông tin.
- **Validation baseline**: `src/itd/scoring/baseline.py`. Hai hàm Global/Role chặn dữ liệu sai shape hoặc NaN/Inf; thống kê mean/std giữ ddof=0.
- **Kiểm chứng**: SPEC-001 v1.0; fixture và test ở `tests/test_ldap.py`, `tests/test_baseline.py`. Môi trường `.venv-validation311`: Python 3.11.9, NumPy 1.26.4, pytest 8.3.5.
- **Hai case Group**: `load_monthly_groups` và `join_groups` ở `src/itd/data/ldap.py` giữ nguyên dân số user-day cho Department/Role.
- **Score ba tầng**: `src/itd/scoring/tiers.py` dùng mean positive z, raw count, scale floor=1. Personal dùng [t-30,t); k_P=7, k_G=3; tối thiểu 2 ngày Personal/2 người Group. Global/Group cố định sau train.
- **Threshold**: `src/itd/scoring/threshold.py` lấy p99 linear từ Calibration; cảnh báo khi score>threshold. Mỗi case lưu threshold riêng, giữ nguyên khi chấm test.
- **Runner**: `scripts/run_group_ablation.py`; hai config kế thừa `configs/experiments/group_ablation_common.json`, chỉ đổi group_key. Paths template để null, dataset_kind=cert bị chặn khi OQ-02/OQ-03 chưa chốt.

## 6. Tham số đã tinh chỉnh

SPEC-002 dùng bộ tham số khởi đầu đã duyệt, chưa tune. Kết quả CERT train/Calibration: Department tau=0.8423588864100263; Role tau=0.8115505803240236. Mỗi case có 841/84.066 cảnh báo Calibration; không phải FPR. Run `runs/20261107-cert-first-calibration/result`; kiểm tra score hữu hạn, tổng trọng số và cùng user-day đã qua.

| Tầng | Tham số | Giá trị | Khoảng tìm | Mục tiêu (val) | Trial | Run |
|---|---|---|---|---|---|---|

## 7. Thí nghiệm & kết quả

Nghiệm thu kỹ thuật phạm vi SPEC-002 ngày 2026-11-09: [spec002-acceptance.md](spec002-acceptance.md). 101 test qua trong 3.59s, JUnit lưu tại runs/20261109-spec002-acceptance/pytest.xml. Kiểm lại artifact Calibration hai case: cùng 84.066 khóa theo thứ tự, score/weights hữu hạn, weights không âm/tổng 1, p99 và cờ cảnh báo đúng; verification.json cùng thư mục lưu bằng chứng và hash source. Chỉ đọc lại Calibration đã lưu, không mở test mới. Chờ người dùng review nghiệm thu, không ghi nhận thay người dùng đã chấp nhận.

| Ngày | Run | Cấu hình | RQ | PR-AUC | Recall@1% | FPR | Ghi chú |
|---|---|---|---|---|---|---|---|

Lần mở test: 1 (DL-036). Test 141.215 user-day, 515 dương. Department: AP=0.039175, Recall=16.3107%, Precision=6.1314%, FPR=0.9140%. Role: AP=0.075425, Recall=24.2718%, Precision=9.6824%, FPR=0.8287%. Dùng baseline/history/threshold Calibration đã lưu, không refit/tune. Báo cáo đầy đủ: `docs/cert-test-open-1-results.md`; bằng chứng `runs/20261107-cert-test-open-1`.

Kiểm chứng kỹ thuật ngày 2026-11-06: 61 test qua trong 0.94 giây. Smoke 3 dòng giả chạy hai lần trong 0.2188 giây, output giống nhau; 1 dòng có Role, 2 dòng UNKNOWN. Bằng chứng: `runs/20261106-spec001-validation/{pytest.xml,metrics.json,log.txt,env.txt,config.json,git.txt}`. Đây là kiểm thử phần mềm, không phải chỉ số phát hiện insider.

Kiểm chứng SPEC-002 ngày 2026-11-07: toàn project 101 test qua trong 2.68 giây. Smoke hai lần có kết quả xác định giống nhau (thời gian 0.029270 và 0.021692 giây; không yêu cầu thời gian giống nhau). Mỗi case dùng 5 dòng train, 4 dòng Calibration và 2 dòng test giả. Department threshold=0.7714150071929214; Role threshold=1.5278060653061314; mỗi case cảnh báo 1/2 dòng test giả. Các số này không phải hiệu quả trên CERT, không dùng để chọn case. Bằng chứng: `runs/20261107-spec002-smoke/{verification.json,pytest.xml}` và các artifact trong run1/run2.

## 8. Cách chạy

Hướng dẫn bàn giao phạm vi ba tầng: [three-tier-usage.md](three-tier-usage.md). Common config trong configs/experiments đã điền đường dẫn CERT và chính sách train/split theo DL-033/DL-034; hai overlay Department/Role giữ nguyên. Kiểm thử ngày 2026-11-09: 101 test qua trong 2.84s. Fixture tự đặt trạng thái policy chưa xác nhận để kiểm tra guard độc lập với cấu hình chạy thật.

```powershell
# Đã chạy trên fixture; thêm --overwrite để chủ động thay output cũ.
.\.venv-validation311\Scripts\python.exe scripts/attach_roles.py --ldap-dir runs/20261106-spec001-validation/LDAP --input runs/20261106-spec001-validation/features.csv --output runs/20261106-spec001-validation/roles.csv --overwrite
.\.venv-validation311\Scripts\python.exe -m pytest -q
```

CLI SPEC-002 dùng hai file case và run-dir mới. Thêm --include-test chỉ cho fixture hoặc khi đã chốt mở test thật:

```powershell
.\.venv-validation311\Scripts\python.exe scripts/run_group_ablation.py --config runs/20261107-spec002-smoke/fixture/department.json --config runs/20261107-spec002-smoke/fixture/role.json --run-dir runs/20261107-spec002-smoke/manual-run --include-test
```

Output lưu riêng department/role với calibration_scores.csv, threshold.json, baselines.json, history và test_scores.csv khi bật test. Mỗi lần chạy chọn run-dir chưa tồn tại. Kiểm chứng chưa dùng dữ liệu thật hoặc nhãn nghiên cứu; lần mở test nghiên cứu vẫn là 0.

Python 3.11.9 đã cài cho tài khoản hiện tại sau khi xác minh chữ ký installer. `.venv` prototype được giữ nguyên. Đợt này cài dependency theo `requirements-validation.txt`; PyTorch CUDA và môi trường train theo DL-008 còn ở bước sau.

## 9. Open Questions

OQ-02/OQ-03 đã chốt theo DL-033/DL-034. Chạy train/Calibration thật theo DL-035; test lần 1 đã được người dùng duyệt theo DL-036 và hoàn thành. Các D-xx còn lại hỏi khi spec chạm tới.

| # | Câu hỏi | A (đề xuất) | B | C | Chặn |
|---|---|---|---|---|---|

OQ-13/OQ-14 đóng do SPEC-003 ngoài phạm vi theo DL-041; không chọn gói feature hoặc khung giờ nào. Không còn câu hỏi mở chặn phạm vi SPEC-002 hiện tại.

Câu đã trả lời → ghi Decision Log rồi xoá dòng ở đây (không đánh số lại).

## 10. Version History

| Version | Ngày | Thay đổi | Spec / DL |
|---|---|---|---|
| 0.1 | 2026-11-02 | Khởi tạo tài liệu; dựng khung thư mục project tại Framework-rework | DL-001 → DL-006 |
| 0.2 | 2026-11-02 | Chốt CERT r4.2 và môi trường Python 3.11 + CUDA; hoãn chia tập và xử lý ngày độc hại trong train tới sau khi code C1 | DL-007 → DL-009 |
| 0.3 | 2026-11-02 | Đẩy Google Doc bản 0.2 (thêm DL-005 → DL-009, tham số CERT r4.2, 4 thuật ngữ); người dùng yêu cầu đẩy trước khi code | — |
| 0.4 | 2026-11-02 | Đưa project + skill lên GitHub nhánh `master`, thay toàn bộ framework cũ | DL-010 |
| 0.5 | 2026-11-06 | Chọn sửa nền tảng trước; tạo SPEC-001 Draft, chờ OQ-05/OQ-06. Code prototype đã có nhưng chưa nghiệm thu; các trạng thái Chưa làm phía trên là trạng thái tài liệu cũ, chưa phản ánh đầy đủ prototype | DL-011 · SPEC-001 |
| 0.6 | 2026-11-06 | Chốt 05A/06A, chuyển câu trả lời sang Decision Log; SPEC-001 v0.2 READY ở mức spec, chờ duyệt; chưa sửa code/cài thư viện | DL-012, DL-013 · SPEC-001 |
| 0.7 | 2026-11-06 | Duyệt và triển khai SPEC-001 v1.0; 61 test qua, smoke fixture tái lập; cập nhật bản Luồng hoạt động local. Google Doc chưa đẩy vì thiếu .env | DL-014 → DL-017 · SPEC-001 |
| 0.8 | 2026-11-06 | Chuẩn bị .env và apps-script/Code.gs; chờ người dùng deploy Web App và cung cấp URL /exec. Chưa đẩy Google Doc | DL-018 |
| 0.9 | 2026-11-07 | Ghi nhận hai case Department/Role cùng tầng Group, Personal 30 ngày; chờ làm rõ công thức | DL-020 · docs/three-tier-ablation-requirements.md |
| 0.10 | 2026-11-07 | Chốt 07A–10A, tạo SPEC-002 Draft; chờ scale floor và tham số độ tin cậy | DL-021 → DL-024 · SPEC-002 |
| 0.11 | 2026-11-07 | Chốt 11A/12A, hoàn thiện SPEC-002 v0.2; chờ duyệt triển khai fixture, chưa sửa code | DL-025, DL-026 · SPEC-002 |
| 0.12 | 2026-11-07 | Duyệt và triển khai SPEC-002 v1.0; 101 test qua, hai case chạy fixture tái lập; cập nhật tài liệu local, Google Doc chưa đồng bộ | DL-027 → DL-030 · SPEC-002 |
| 0.13 | 2026-11-07 | Kiểm kê processed/LDAP và vị trí nhãn CERT; chưa chạy scoring/Calibration hoặc đánh giá test thật | DL-031 · docs/cert-data-inventory.md |
| 0.14 | 2026-11-07 | Tải và xác minh gói đáp án chính thức CMU; đã có insiders.csv và r4.2-1/2/3 local; chưa dùng nhãn để chạy mô hình | DL-032 |
| 0.15 | 2026-11-07 | Chốt split và chính sách train, kiểm kê nhãn user-day; hai case chạy CERT train/Calibration thành công; test đánh giá chưa mở | DL-033 → DL-035 · docs/cert-first-calibration-results.md |
| 0.16 | 2026-11-07 | Mở test lần 1 với cấu hình đóng băng, lưu score và đối soát AP/ROC-AUC/confusion metrics cho hai case; chưa tune theo test | DL-036, DL-037 · docs/cert-test-open-1-results.md |
| 0.17 | 2026-11-07 | Audit 7.323 sự kiện nhãn với raw; sáu feature khớp toàn bộ 330.452 user-day; đối soát 450.562 dòng score và metric, không có sai lệch ngoài sai số số thực | DL-038 · docs/label-pipeline-audit.md |
| 0.18 | 2026-11-07 | Chuẩn bị đề xuất SPEC-003 preprocessing ngữ cảnh sau yêu cầu tiếp tục; chưa chốt gói feature/khung giờ, chưa đổi code | SPEC-003 Draft · OQ-13/OQ-14 |
| 0.19 | 2026-11-07 | Hoàn thiện tài liệu bàn giao ba tầng; xuất DOCX với bảng và tiêu đề, kiểm ZIP/XML đạt; chưa upload Google Doc | DL-039 · reports/three-tier-architecture-v0.19.docx |
| 0.20 | 2026-11-07 | Đẩy Google Doc bản 0.19 theo yêu cầu cập nhật trực tiếp; máy chủ trả ok=true, 41 blocks. Chưa đọc lại nội dung/comment vì chưa có kênh truy cập | DL-040 |
| 0.21 | 2026-11-07 | Hoàn thiện SPEC-003 v0.2 đề xuất 13A/14A: API, schema, bảo vệ output, test và lệnh chạy. OQ-13/OQ-14 vẫn chờ duyệt; chưa đổi code, dữ liệu hoặc Google Doc | SPEC-003 §6/10/13 |
| 0.22 | 2026-11-09 | Xác nhận chỉ triển khai SPEC-002; rút SPEC-003, đóng OQ-13/OQ-14 vì ngoài phạm vi; SPEC-001 giữ làm hồ sơ hỗ trợ. Không đổi thuật toán hoặc kết quả đã lưu | DL-041 |
| 0.23 | 2026-11-09 | Bàn giao config dùng trực tiếp theo dữ liệu/chính sách đã chốt, hướng dẫn hai case và cập nhật README; 101 test qua. Không thay công thức hoặc mở test mới | DL-042 |
| 0.24 | 2026-11-09 | Lập bản nghiệm thu kỹ thuật SPEC-002 theo lựa chọn A: sơ đồ, đối chiếu yêu cầu/code/test, giới hạn; 101 test qua, đối soát artifact Calibration. Không đổi code hoặc đánh giá test mới | DL-043 |
| 0.25 | 2026-11-09 | Hoàn thành bước B: hướng dẫn đọc output bằng hai user-day Calibration thực tế, giải thích backoff, fallback và giới hạn diễn giải. Không đổi code, không chạy lại mô hình/test nghiên cứu | DL-044 |
| 0.26 | 2026-11-09 | Đẩy Google Doc bản 0.26: phạm vi SPEC-002, nghiệm thu và ví dụ đọc output. Máy chủ xác nhận 52 blocks; chưa đọc lại nội dung/bình luận online | DL-045 |

## 11. Decision Log

Mỗi thay đổi về thiết kế, tham số, dữ liệu, code, hoặc phạm vi là một dòng. Lý do ghi kèm **phương án bị loại**. Đánh số tăng dần, không dùng lại số.

| # | Liên quan | Quyết định | Lý do | Ngày |
|---|---|---|---|---|
| DL-001 | Phạm vi project | **Project chỉ gồm pipeline ML nghiên cứu bằng Python/PyTorch**: chuẩn bị dữ liệu, hai mô hình, chuẩn 3 tầng, ngưỡng thích ứng, đánh giá và ablation cho RQ1–RQ3 | Người dùng chốt 01/11/2026. **Phương án bị loại**: thêm demo FastAPI; làm full như bản cũ (ASP.NET + React) — không cần cho việc trả lời câu hỏi nghiên cứu | 2026-11-01 |
| DL-002 | Chọn tham số | **Chọn tham số bằng Optuna trên tập validation không dùng nhãn; nhãn chỉ dùng ở lần đánh giá cuối** | Người dùng chốt 01/11/2026. Dùng nhãn để chọn tham số làm kết quả đẹp giả, khó bảo vệ trong paper. **Phương án bị loại**: Optuna trên validation có nhãn; grid search nhỏ | 2026-11-01 |
| DL-003 | Tài liệu | **Google Doc "Luồng hoạt động" được cập nhật sau mỗi lần code xong, viết bằng ngôn ngữ BA** | Người dùng chốt 02/11/2026. Người đọc Doc không đọc code; chi tiết kỹ thuật nằm ở spec | 2026-11-02 |
| DL-004 | Tài liệu | **Doc được ghi bằng Apps Script gắn vào Doc; mỗi lần cập nhật ghi đè toàn bộ tab đầu tiên** | Người dùng chốt 02/11/2026. Ghi được mà không cần connector và không phụ thuộc tài khoản Drive đang kết nối. Hệ quả: comment trên Doc mất neo sau mỗi lần cập nhật, nên được đọc và báo lại trước khi ghi. **Phương án bị loại**: connector Google Docs (phải bật thêm); Docs API qua service account (phải tạo project Google Cloud) | 2026-11-02 |
| DL-005 | Nơi code | **Code project tại `D:\AI for BA\MW\Framework-rework`** thay cho `D:\Insider-Threat-Research` | Người dùng chốt 02/11/2026. Dùng chung `.env` (Apps Script) và Google Doc với project cũ | 2026-11-02 |
| DL-006 | Cấu trúc project | **Dựng khung thư mục theo chuẩn kỹ thuật §1 của skill, chưa có code**: `configs/`, `data/`, `src/itd/<data, features, models, scoring, training, evaluation, utils>`, `scripts/`, `tests/`, `specs/`, `docs/`, `runs/`, `reports/`. `configs/base.yaml` chỉ có khung khoá, mọi giá trị null; chưa tạo `pyproject.toml` | Người dùng yêu cầu 02/11/2026 "chỉ xây cấu trúc file, chưa code". Giá trị config và phụ thuộc thư viện là quyết định của spec / D-xx nên để trống. **Phương án bị loại**: tạo sẵn tệp `.py` rỗng cho từng module — tên tệp và chữ ký hàm phải chốt ở § 6 của spec | 2026-11-02 |
| DL-007 | D-01 · C1 | **Dùng CERT r4.2** | Người dùng chốt 02/11/2026 (trả lời OQ-01). Bản được dùng nhiều nhất trong paper, nhiều insider, dễ so sánh. **Phương án bị loại**: r5.2; r6.2 — mỗi kịch bản chỉ 1 insider, khó đo recall | 2026-11-02 |
| DL-008 | D-12 · môi trường | **venv Python 3.11 + PyTorch bản CUDA cho RTX 3050 Laptop 4GB** | Người dùng chốt 02/11/2026 (trả lời OQ-04). Hiện trạng đo 02/11/2026: máy chỉ có Python 3.14 và 3.12, chưa có 3.11; driver NVIDIA 566.07 hỗ trợ PyTorch CUDA 12.x. SPEC-001 phải có bước cài Python 3.11 và tạo venv; hỏi trước khi cài. **Phương án bị loại**: Python 3.12 + CUDA; chạy CPU — quá chậm cho train đủ dữ liệu | 2026-11-02 |
| DL-009 | D-02, D-03 · C1 | **Hoãn chọn tỉ lệ chia tập (OQ-02) và cách xử lý ngày độc hại trong train (OQ-03) tới sau khi code C1.** SPEC C1 phải làm cả 3 phương án của mỗi câu thành tuỳ chọn trong config, mặc định để trống; chốt trước lần train đầu tiên | Người dùng chốt 02/11/2026. Cần thấy khoảng ngày và phân bố dữ liệu thật trước khi chọn. Ràng buộc chống leakage (L5): khi chốt chỉ dựa trên khoảng ngày, số user-day, và vị trí ngày độc hại; không chọn theo kết quả mô hình | 2026-11-02 |
| DL-010 | Git · repo | **Đưa Framework-rework và skill `insider-threat-model-dev` lên `github.com/lethanhloi0603/ANOMALY-DETECTION` nhánh `master`**, thay toàn bộ framework cũ (backend FastAPI, migrations, CI) bằng một commit mới (9d62405), không force-push | Người dùng chốt 02/11/2026. Lịch sử cũ giữ nguyên, khôi phục được từ commit b3778f6; nhánh `main` vẫn ở bản cũ. Repo public: người dùng đồng ý công khai đề cương (`research-proposal.md`) và email chủ Google Doc. **Phương án bị loại**: bỏ đề cương khỏi repo; chuyển repo sang private trước khi đẩy | 2026-11-02 |
| DL-011 | Phạm vi sửa sau review | **Chọn phương án A: chuẩn bị spec nhỏ cho ghép Role và validation trước khi phát triển Threshold** | Người dùng trả lời A ngày 06/11/2026. Chưa duyệt nội dung SPEC-001, chính sách dữ liệu lỗi hay thay đổi môi trường. **Phương án chưa chọn cho bước này**: hoàn thiện mô hình thống kê đối chứng ngay; chốt toàn bộ mô hình hai luồng ngay | 2026-11-06 |
| DL-012 | SPEC-001 · OQ-05 | **Dữ liệu lỗi hoặc trùng khóa phải dừng và báo lỗi; không tự loại/impute** | Người dùng chọn 05A. Giữ nguyên tập mẫu và để kiểm tra nguồn. **Phương án bị loại**: bỏ dòng kèm báo cáo; sửa/impute tự động | 2026-11-06 |
| DL-013 | SPEC-001 · OQ-06 | **Dùng Python 3.11 theo DL-008 để kiểm chứng; chuẩn bị NumPy/pytest còn thiếu theo spec sau khi duyệt** | Người dùng chọn 06A. Venv prototype hiện báo Python 3.15.2, chưa có pytest; dùng môi trường riêng để bảo toàn prototype. **Phương án bị loại**: kiểm chứng trên venv 3.15; dùng unittest thay pytest. Lựa chọn này chưa phải duyệt toàn bộ SPEC-001 | 2026-11-06 |
| DL-014 | SPEC-001 | **Duyệt SPEC-001 v1.0** | Người dùng trả lời accept ngày 06/11/2026 cho nội dung draft v0.2; cho phép triển khai ghép Role, validation và môi trường kiểm chứng. **Phương án bị loại**: tiếp tục giữ draft chờ duyệt | 2026-11-06 |
| DL-015 | LDAP · SPEC-001 §4.1 | **Ghép Role đúng tháng, dừng khi dữ liệu sai/trùng, bảo vệ input và output cũ** | Triển khai phạm vi đã duyệt; tách module khỏi CLI để kiểm chứng nhân quả và I/O. **Phương án bị loại**: ghép từ tháng tương lai; ghi đè input; bỏ dòng lỗi im lặng | 2026-11-06 |
| DL-016 | Baseline · SPEC-001 §4.2 | **Global/Role dùng chung validation ma trận; Role yêu cầu vector chuỗi 1D cùng số dòng** | Chặn NaN/Inf, shape rỗng/sai và tên nhóm không hợp lệ trước khi tính; giữ nguyên mean/std. **Phương án bị loại**: ép None/NaN thành tên nhóm; đổi công thức thống kê trong đợt sửa này | 2026-11-06 |
| DL-017 | Môi trường · SPEC-001 §10 | **Cài Python 3.11.9 và tạo .venv-validation311 với dependency đã pin** | Thực hiện DL-013 và spec đã accept; installer từ python.org có chữ ký Python Software Foundation hợp lệ. **Phương án bị loại**: thay/xóa venv prototype; cài PyTorch ngoài phạm vi | 2026-11-06 |
| DL-018 | Google Doc · thiết lập | **Chọn Apps Script; tạo .env và Code.gs local với secret ngẫu nhiên** | Người dùng chọn A. Đã xác minh cả hai tệp được gitignore; URL Web App còn trống. **Phương án chưa chọn**: chuyển sang connector; hoãn thiết lập chỉ giữ tài liệu local. Chưa deploy hoặc ghi nội dung online | 2026-11-06 |

| DL-019 | Google Doc · kết nối | **Lưu URL Web App và xác nhận ping thành công cho Tài liệu Code** | Người dùng cung cấp URL; Web App trả ok=true. Chưa ghi đè vì chưa đọc được bình luận và chưa có kênh đọc lại nội dung. **Phương án chưa thực hiện**: ghi đè trước khi kiểm tra bình luận | 2026-11-06 |
| DL-020 | C5/C6 · ablation Group | **Hai case Global–Department–Personal và Global–Role–Personal; Personal 30 ngày; Adaptive Backoff; score cuối và một threshold cuối từ Calibration mỗi case** | Người dùng yêu cầu 07/11/2026: cùng dữ liệu, feature, temporal split và nguyên tắc Calibration. **Phương án bị loại**: gộp thành bốn tầng; đổi mẫu giữa các case. Chưa duyệt spec hoặc công thức; chưa thay toàn bộ kế hoạch RQ3 | 2026-11-07 |
| DL-021 | OQ-07 · SPEC-002 | **Score tầng là trung bình phần dương của z-score feature** | Người dùng chọn 07A; nhạy tăng hoạt động. **Phương án bị loại cho đợt này**: mean squared z; chờ score hai mô hình C2–C4. Transformation/scale floor chờ OQ-11 | 2026-11-07 |
| DL-022 | OQ-08 · SPEC-002 | **Adaptive Backoff dùng pseudo-count theo số ngày Personal và số user riêng biệt Group** | Người dùng chọn 08A. **Phương án bị loại**: chuyển cứng; thêm hệ số ổn định. Giá trị k và cỡ mẫu tối thiểu chờ OQ-12 | 2026-11-07 |
| DL-023 | OQ-09 · SPEC-002 | **Global/Group cố định từ train; Personal trượt 30 ngày qua Calibration/test** | Người dùng chọn 09A. **Phương án bị loại**: cả ba tầng trượt; cả ba cố định | 2026-11-07 |
| DL-024 | OQ-10 · SPEC-002 | **Threshold cuối là phân vị 99% score Calibration riêng từng case, chung p=0.99** | Người dùng chọn 10A. **Phương án bị loại**: p95; ngân sách B. Không dùng nhãn để chọn ngưỡng; chưa duyệt toàn bộ SPEC-002 | 2026-11-07 |
| DL-025 | OQ-11 · SPEC-002 | **Giữ raw count, chuẩn hóa với mẫu số max(std,1)** | Người dùng chọn 11A. Tránh chia cho 0 và scale quá nhỏ. **Phương án bị loại**: log1p với floor=0.01; dùng scale Global khi std tầng bằng 0 | 2026-11-07 |
| DL-026 | OQ-12 · SPEC-002 | **Backoff k_P=7 ngày, k_G=3 người, Personal tối thiểu 2 ngày, Group tối thiểu 2 người** | Người dùng chọn 12A; chung tham số hai case. Đây là bộ khởi đầu chưa tune. **Phương án bị loại**: 14/5/3/3; 30/10/5/5. Chưa duyệt toàn bộ SPEC-002 | 2026-11-07 |
| DL-027 | SPEC-002 | **Duyệt SPEC-002 v1.0 và triển khai cả hai case bằng fixture trước** | Người dùng accept bản v0.2 ngày 07/11/2026. **Phương án bị loại**: giữ draft, tự chạy dữ liệu CERT/test khi split chưa chốt | 2026-11-07 |
| DL-028 | LDAP/tiers · SPEC-002 | **Một pipeline ba tầng với group_key thay Department/Role; backoff theo ngày và user riêng biệt** | Thực hiện spec đã duyệt; thiếu metadata không loại dòng, Personal chỉ thấy quá khứ. **Phương án bị loại**: bốn tầng; đếm user-day làm cỡ nhóm; reset Personal khi chuyển split/Group | 2026-11-07 |
| DL-029 | Calibration · SPEC-002 | **Mỗi case lưu một threshold p99 linear và cảnh báo bằng >** | Thực hiện DL-024; Calibration không dùng nhãn, test giữ threshold. **Phương án bị loại**: cùng một số threshold bất chấp phân phối; tune bằng test; ngưỡng >= khi bằng phân vị | 2026-11-07 |
| DL-030 | Runner/kiểm chứng · SPEC-002 | **So sánh hai case với cùng input/config chung; test mặc định deferred; run-dir không ghi đè** | Triển khai fairness và tái lập: 101 test qua; chỉ smoke dữ liệu giả. **Phương án bị loại**: tự chạy CERT khi OQ còn mở; ghi đè run; loại mẫu theo metadata từng case | 2026-11-07 |
| DL-031 | Kiểm kê dữ liệu | **Kiểm kê dataset hiện có trước khi chốt split và train nhiễm bẩn** | Người dùng chọn A. Đã đọc processed và LDAP để đếm/đối soát; raw chỉ header/kích thước. Chưa tìm thấy nhãn ở vị trí đã kiểm tra. **Phương án chưa thực hiện**: chạy mô hình/test nghiên cứu ngay; thay split hoặc loại mẫu khi chưa chốt OQ-02/OQ-03 | 2026-11-07 |
| DL-032 | Nguồn đáp án CERT | **Dùng answers.tar.bz2 từ CMU KiltHub, tải vào data/raw/cert-answers và kiểm MD5 trước giải nén** | Người dùng yêu cầu tìm bộ đáp án; metadata https://api.figshare.com/v2/articles/12841247 xác nhận file 24857828, 1.254.678 byte. MD5 c0c96eaa06915e417504f932756f58d8 khớp; đã thấy insiders.csv và ba thư mục r4.2. **Phương án bị loại**: nhãn bên thứ ba chưa kiểm chứng; tải lại toàn bộ log. Chưa dùng nhãn cho tune/đánh giá | 2026-11-07 |
| DL-033 | OQ-02 · split | **Giữ split hiện tại: train 01–05/2010, Calibration 06–09/2010, test 10/2010–05/2011** | Người dùng chọn giữ split trong câu trả lời công cụ. **Phương án bị loại**: chia lại 60/15/25; chia lại 50/20/30. Không chọn dựa kết quả mô hình | 2026-11-07 |
| DL-034 | OQ-03 · train | **Loại user-day độc hại khỏi train, ghi giả định baseline sạch theo đáp án** | Người dùng chọn loại ngày độc hại. Kiểm kê đáp án hiện tại không có ngày độc hại trong train, nên không loại dòng nào; còn 105.171 dòng. **Phương án bị loại**: giữ dữ liệu nhiễm không giám sát; loại toàn bộ user insider | 2026-11-07 |
| DL-035 | Chạy SPEC-002 trên CERT | **Fit Global/Group bằng train, chấm Calibration và lưu p99 cho hai case; test vẫn deferred** | Người dùng yêu cầu tiếp tục và chạy mô hình; OQ-02/OQ-03 đã chốt. Chạy thành công 26.898015s; threshold Department=0.8423588864100263, Role=0.8115505803240236. **Phương án chưa thực hiện**: mở test đánh giá trước khi trình cấu hình và kết quả Calibration | 2026-11-07 |
| DL-036 | Mở test lần 1 · SPEC-002 | **Mở test đánh giá lần 1 cho cả hai case với tham số, baseline, lịch sử Calibration và threshold đã lưu** | Người dùng trả lời accept cho đề nghị mở test; không tune hoặc chọn lại cấu hình bằng kết quả test. **Phương án bị loại**: tự hiệu chỉnh threshold trên test; huấn luyện lại trước lần đánh giá | 2026-11-07 |
| DL-037 | Kết quả test lần 1 | **Giữ nguyên kết quả đánh giá hai case, không tự sửa mô hình sau khi xem test** | Role có Recall/AP cao hơn trên split này nhưng Precision/Recall vẫn thấp; đã lưu đầy đủ output và đối soát công thức. **Phương án bị loại**: dùng test chọn lại p/k hoặc công bố kết luận khái quát khi chưa có kiểm định. Nhãn event→user-day chưa đối soát từng raw event ID | 2026-11-07 |
| DL-038 | Audit nhãn/pipeline | **Đối soát raw, nhãn, lịch sử, score và metric; giữ nguyên mô hình và kết quả test lần 1** | Người dùng chọn A. 7.323 sự kiện đáp án khớp đúng nguồn/ID/user/time; 330.452 user-day khớp sáu count; 450.562 dòng score khớp tính lại trong sai số số thực. **Phương án chưa thực hiện**: đổi nhãn theo actor thay event-account; sửa feature hoặc tham số sau xem test. Không refit và không mở cấu hình test mới | 2026-11-07 |
| DL-039 | Bàn giao Google Docs | **Chuẩn bị bản luồng v0.19 và file DOCX để đưa lên Docs** | Người dùng muốn tải tài liệu phần ba tầng đã xong. Google Drive hiện chưa kết nối; đã xuất 41 khối nội dung và kiểm cấu trúc ZIP/XML. **Phương án chưa thực hiện**: ghi đè Doc trước khi đọc bình luận/không kiểm tra lại nội dung. Chưa upload; DOCX có thể mở bằng Google Docs | 2026-11-07 |
| DL-040 | Google Doc · gửi cập nhật | **Gửi bản luồng v0.19 vào Doc đã cấu hình theo yêu cầu trực tiếp của người dùng** | Người dùng yêu cầu cập nhật vào Doc sau khi được thông báo giới hạn Apps Script. Máy chủ xác nhận ok=true, blocks=41 tại 2026-11-07T02:21:12.857Z. **Giới hạn**: chưa kiểm tra bình luận/đọc lại; thử URL export không truy cập được, không tuyên bố đối soát nội dung online hoàn tất. **Phương án không dùng**: chỉ hướng dẫn upload file Word thủ công | 2026-11-07 |
| DL-041 | Phạm vi nhiệm vụ | **Chỉ kiến trúc ba tầng và hai case theo SPEC-002; rút SPEC-003, giữ SPEC-001 làm hồ sơ hỗ trợ đã triển khai** | Người dùng xác nhận rõ chỉ cần Global–Group–Personal, Personal 30 ngày, Adaptive Backoff, score cuối, threshold Calibration; Group là department hoặc role. Không mở rộng feature/preprocessing/toàn bộ framework. OQ-13/OQ-14 đóng vì ngoài phạm vi, không phê duyệt tham số. Không xóa code phụ thuộc hoặc artifact. Kiểm tra lại tiers/threshold/runner: 40 test qua trong 2.94s; chỉ fixture, không chấm lại CERT | 2026-11-09 |

| DL-042 | SPEC-002 delivery | **Runnable paired configs and usage guide; unchanged scoring** | Reuse DL-033/DL-034 paths/policy; fixture policy explicitly isolated. 101 tests passed (2.84s). CERT train/Calibration run: runs/20261109-three-tier-calibration, 40.990708s; department threshold 0.8423588864100263, role 0.8115505803240236; 841/84066 alerts each, matching previous calibration. include_test=false. No new feature or model parameters | 2026-11-09 |
| DL-043 | Nghiệm thu SPEC-002 | **Lập bản đối chiếu kỹ thuật theo lựa chọn A, chưa ghi nhận người dùng đã nghiệm thu** | Sơ đồ hai case, đối chiếu yêu cầu/code/test, 101 test qua trong 3.59s; kiểm lại score, trọng số, p99 và cùng khóa Calibration từ artifact đã lưu. Không đổi thuật toán, không chấm test mới, không mở rộng feature. Bằng chứng: runs/20261109-spec002-acceptance | 2026-11-09 |
| DL-044 | Hướng dẫn đọc output | **Thực hiện bước B sau bản nghiệm thu: giải thích output bằng Calibration đã lưu** | Người dùng yêu cầu bước tiếp theo; tài liệu docs/three-tier-output-guide.md giải thích các cột, hai user-day thực tế và fallback. Chỉ đọc output Calibration, không thay tham số, không đối chiếu nhãn để chọn ví dụ và không mở test mới | 2026-11-09 |
| DL-045 | Google Doc bàn giao | **Gửi bản luồng 0.26 theo yêu cầu tiếp tục bước C** | Apps Script trả ok=true, blocks=52 tại 2026-11-09T14:47:28.712Z. Không có document session kết nối để đọc bình luận/nội dung; chưa xác minh readback. Chỉ cập nhật tài liệu, không đổi mô hình hoặc mở test | 2026-11-09 |
