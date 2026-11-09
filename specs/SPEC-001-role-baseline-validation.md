---
id: SPEC-001
title: Ghép Role và validation baseline
status: Implemented
version: 1.0
date: 2026-11-06
rq: [RQ2]
components: [C1, C5]
decisions: [DL-007, DL-008, DL-009, DL-011, DL-012, DL-013]
supersedes: null
---

# SPEC-001 — Ghép Role và validation baseline

> **Phạm vi hiện tại ngày 2026-11-09 (DL-041):** nhiệm vụ người dùng là SPEC-002 — hai cấu hình ba tầng. SPEC-001 giữ lại như hồ sơ phần hỗ trợ ghép LDAP/validation đã triển khai; không phải một hạng mục riêng cần tiếp tục phát triển. Code hỗ trợ đang được pipeline dùng vẫn được giữ.

## 1. Mục tiêu

Ổn định bước ghép LDAP và hợp đồng đầu vào của baseline đang có. Phục vụ tiền đề cho chuẩn hành vi phân tầng trong Gap 2 / RQ2 của `research-proposal.md` thuộc skill; chưa phải triển khai hoàn chỉnh C1 hoặc C5. CERT r4.2 theo DL-007; lựa chọn thực hiện từng bước nhỏ theo DL-011.

## 2. Phạm vi

- Sửa lỗi thụt lề ghép Role; bỏ phép đọc department chưa được sử dụng.
- Tách logic ghép Role khỏi I/O để kiểm thử trên fixture, script chỉ chạy trong `main()`.
- Kiểm tra schema, ngày, khóa user-day và đầu vào thống kê: dừng và báo lỗi, không tự loại/impute (DL-012).
- Giữ nguyên mean/std với `ddof=0`, danh sách feature, tên cột và chữ ký hai hàm baseline hiện có.
- D-07/D-08 chưa được chốt: giữ Role của prototype, không coi đây là quyết định chọn Group cuối cùng.

## 3. Dữ liệu vào / ra

| Đối tượng | Schema / shape | Kết quả |
|---|---|---|
| LDAP từng tháng | tên file YYYY-MM.csv, cột user_id, role | mapping (month, user_id) → role |
| Feature CSV | user_id, date ISO YYYY-MM-DD và các cột gốc | giữ cột gốc; thêm role và role_missing |
| X_train | số thực hữu hạn, shape (N,D), N>0, D>0 | mean/std shape (D,) |
| roles | vector chuỗi shape (N,) | dict Role → mean, std, n_samples |

Role rỗng hoặc không tìm thấy giữ quy tắc hiện có: UNKNOWN, role_missing=1; không dùng cờ này làm feature. UNKNOWN không tạo baseline Role. Mọi dòng hợp lệ được giữ nguyên số lượng/thứ tự; không suy diễn Role từ tháng tương lai.

## 4. Thiết kế

### 4.1 Ghép Role

Parse ngày tường minh, lấy tháng tương ứng; chỉ tra đúng (month, user_id). Chuẩn hóa khoảng trắng ở user_id và role khi tra cứu; user_id rỗng là lỗi. LDAP có khóa trùng hoặc feature có khóa (user_id,date) trùng phải dừng bằng ValueError, kể cả hai dòng giống nhau; không ghi đè im lặng. File thiếu cột, ngày không hợp lệ hoặc danh sách LDAP rỗng phải báo lỗi rõ. Feature CSV yêu cầu user_id/date và sáu cột logon_count, logoff_count, device_count, file_count, email_count, http_count; các count phải là số hữu hạn không âm. Header trùng, dòng lệch số cột, file chỉ có header hoặc đã chứa role/role_missing đều bị từ chối. LDAP phải có ít nhất một dòng; tên tháng phải hợp lệ. File không tồn tại báo FileNotFoundError.

Đọc và kiểm tra xong một input trước khi xuất output, nhằm tránh output dở do lỗi dữ liệu. Lỗi bao gồm tên nguồn, số dòng và tên cột/khóa; không in toàn bộ nội dung nhân viên. Không sửa input.

Input và output resolve về cùng file phải bị từ chối, kể cả --overwrite. Giữ user_id gốc khi xuất, chuẩn hóa chỉ dùng cho khóa tra/trùng. Ghi file tạm cùng thư mục output và chỉ thay output sau khi ghi thành công; dọn file tạm khi lỗi. --overwrite chỉ cho phép thay output cũ, không cho phép thay input. Logic thuần không nhận đường dẫn nên báo chỉ số dòng; lớp I/O bổ sung tên nguồn.

### 4.2 Validation baseline

Đổi X sang float; chặn scalar, 1D, 3D, N=0, D=0, NaN/Inf và dữ liệu không chuyển được thành số. roles phải 1D, cùng N và chứa chuỗi; chuỗi được strip trước khi nhóm. Rỗng/UNKNOWN bị bỏ qua như hiện tại. Không tự chuyển None hay NaN thành tên nhóm.

### 4.3 Thống kê

mean_j = sum(x_ij)/N; std_j = sqrt(sum((x_ij-mean_j)^2)/N). Role áp dụng cùng công thức trên các dòng của Role. Feature hằng vẫn có std=0: chưa có phép chia hoặc scale floor trong spec này. Không thay mean/std bằng median/IQR.

## 5. Tham số

Không thêm tham số mô hình hoặc tune. CLI ghép Role nhận đường dẫn bắt buộc `--ldap-dir`, `--input`, `--output`; mỗi lần xử lý một file, giúp không tự mở test thật. `--overwrite` mặc định false; output tồn tại thì từ chối nếu không chỉ định. Các đường dẫn là đối số vận hành, không ghi đường dẫn D: trong logic mới.

## 6. Thay đổi code

| Tệp | Thay đổi / chữ ký |
|---|---|
| src/itd/data/ldap.py | tạo `load_monthly_roles(ldap_dir: Path) -> dict[tuple[str,str],str]`; `attach_roles(rows: list[dict[str,str]], monthly_roles: dict) -> list[dict]` |
| scripts/attach_roles.py | sửa thành `main() -> None`, argparse; I/O gọi module; giữ encoding utf-8-sig khi đọc, utf-8 khi ghi |
| src/itd/scoring/baseline.py | thêm `_validate_matrix(X_train) -> np.ndarray`; giữ `fit_global_baseline(X_train)` và `fit_role_baselines(X_train, roles)` |
| tests/test_ldap.py | tạo unit test, fixture trong tmp_path |
| tests/test_baseline.py | tạo unit test cho hợp đồng và thống kê |
| tests/conftest.py | thêm project/src vào sys.path cho test |
| requirements-validation.txt | tạo pin numpy==1.26.4, pytest==8.3.5 cho Python 3.11 |
| docs/BA-insider-threat-detection.md | cập nhật phạm vi thực tế, kết quả, quyết định sau khi thực hiện |

Import CLI theo cách hiện có của scripts/fit_baselines.py: thêm project/src vào sys.path. Không import script để chạy pipeline trong test.

## 7. Thí nghiệm & chỉ số

Không áp dụng thí nghiệm ML, ablation, seed hay metric có nhãn. Chỉ kiểm chứng tính đúng của xử lý dữ liệu bằng fixture; không mở calibration/test thật.

## 8. Tiêu chí chấp nhận

| ID | Tiêu chí | Kiểm chứng |
|---|---|---|
| AC-01 | script parse được, import không đọc/ghi dữ liệu | AST và import bằng fixture |
| AC-02 | ghép đúng user và tháng, giữ cột/số dòng/thứ tự | test_ldap |
| AC-03 | thiếu Role → UNKNOWN/1, có Role → role/0 | test_ldap |
| AC-04 | dữ liệu lỗi được xử lý đúng chính sách đã chọn, lỗi không làm hỏng output cũ | test_ldap |
| AC-05 | X sai chiều, rỗng, 0 feature, NaN/Inf bị chặn rõ | test_baseline |
| AC-06 | roles sai chiều/số lượng/kiểu bị chặn; UNKNOWN không tạo nhóm | test_baseline |
| AC-07 | X=[[1,2],[3,4]] → mean=[2,3], std=[1,1]; std hằng=0 | test_baseline |
| AC-08 | thêm/sửa LDAP tháng sau không đổi kết quả tháng trước | test_ldap, kiểm L2 |
| AC-09 | CLI chạy fixture thành công, output tồn tại được bảo vệ; lỗi trả exit code khác 0 | subprocess CLI test |

## 9. Kế hoạch test

Fixture LDAP: 2 user × 2 tháng, một user đổi Role; feature có tháng thiếu mapping. Test riêng schema thiếu, ngày lỗi, trùng khóa, user rỗng, file LDAP rỗng. Baseline dùng numpy.testing.assert_allclose, kiểm NaN/Inf, mọi shape bất hợp lệ, role vector lỗi và feature hằng. Smoke subprocess chỉ dùng fixture tạm, không dùng D:/CERT_r4.2. Không cần test overfit vì không có mô hình học.

## 10. Thực thi

Sau khi duyệt spec: chuẩn bị môi trường Python 3.11 theo DL-013 → triển khai → unit test → smoke fixture → review code → BA. Chỉ sau code READY mới thực hiện quy trình cập nhật Google Doc theo skill và khả năng truy cập thực tế.

Môi trường riêng `.venv-validation311` giữ nguyên venv prototype hiện có. Dùng Python 3.11 tìm được trên máy để chạy `py -3.11 -m venv .venv-validation311`; nếu launcher không nhận diện thì dùng đường dẫn tuyệt đối tới interpreter đã xác minh `--version`. Nếu chưa có Python 3.11, chuẩn bị cài bản 3.11 trước và dùng cơ chế xin quyền hệ thống khi cần. Không tải/chạy installer trước khi spec được duyệt.

Lệnh dependency: `.\.venv-validation311\Scripts\python.exe -m pip install -r requirements-validation.txt`. Hai pin trên là bộ phiên bản mục tiêu tái lập, không tuyên bố là phiên bản mới nhất; kiểm cài đặt thực tế ở bước triển khai, nếu không khả thi thì dừng báo lại.

Lệnh test: `.\.venv-validation311\Scripts\python.exe -m pytest tests/test_ldap.py tests/test_baseline.py -q`; sau đó chạy toàn bộ `-m pytest -q`.

CLI: `.\.venv-validation311\Scripts\python.exe scripts/attach_roles.py --ldap-dir <fixture-LDAP> --input <fixture-features.csv> --output <temporary-output.csv>`.

Ước tính test/smoke dưới 1 phút trên CPU, không dùng VRAM RTX 3050; chưa đo. Chưa ước tính thời gian tải/cài môi trường do phụ thuộc mạng. Môi trường prototype báo Python 3.15.2, NumPy 2.5.4, thiếu pytest; `py -0p` báo không thấy Python đã đăng ký, chưa chứng minh toàn máy không có Python 3.11. DL-013 chốt Python 3.11 cho kiểm chứng; DL-008 Python 3.11 + CUDA cho ML vẫn giữ nguyên. Đợt này chưa cài PyTorch, chưa train.

## 11. Rủi ro

| Rủi ro | Xử lý |
|---|---|
| Validation phát hiện dữ liệu thật lỗi | dừng, báo nguồn/dòng; không tự chọn sửa hoặc loại mẫu |
| Prototype chưa có score/threshold | không tuyên bố C5/C6 hoàn thành sau spec này |
| Split, train nhiễm bẩn còn mở | giữ OQ-02/OQ-03; không train/đánh giá trong đợt sửa này |
| Không đủ quyền truy cập Google Doc | báo trạng thái riêng, không coi cập nhật online đã xong |

## 12. Open Questions

Không còn câu hỏi chặn phạm vi này. OQ-05 → DL-012, OQ-06 → DL-013. Người dùng accept SPEC-001 ngày 2026-11-06 (DL-014). OQ-02/OQ-03 tiếp tục ở tài liệu BA và không thuộc đợt sửa này.

## 13. Review readiness

Đã đọc lại file riêng cho mỗi vòng. Đây là review spec, không phải kết quả test code.

| Vòng | Kết quả |
|---|---|
| 1 — Đầy đủ & truy vết | Đạt: schema, chữ ký, 9 AC; OQ-05/OQ-06 đã chuyển thành DL-012/DL-013 |
| 2 — Đúng đắn khoa học | Giữ công thức, chỉ dùng fixture; kiểm tra tháng tương ứng và không tra tương lai; chưa xác nhận dữ liệu thật |
| 3 — Sẵn sàng dev | Đạt ở mức spec: pin dependency, lệnh môi trường/test/CLI, thứ tự thực hiện và xử lý output đã rõ; môi trường sẽ chuẩn bị sau duyệt |

**Kết luận spec: READY** — người dùng đã accept, triển khai ở v1.0.

### Review code — 2026-11-06

| Vòng | Kết quả |
|---|---|
| 1 — Khớp spec | AC-01–AC-09 có test trong test_ldap/test_baseline; công thức mean/std giữ nguyên |
| 2 — Đúng đắn | Test exact-month/no-future-leakage, input không bị thay đổi, shape/NaN/Inf và std=0 đều qua; smoke chạy hai lần cùng SHA-256 |
| 3 — Chạy được & bàn giao | Python 3.11.9; toàn bộ 61 test qua trong 0.94s, smoke 3 dòng trong 0.2188s; BA và bản luồng local cập nhật |

**Code READY trong phạm vi SPEC-001**, không xác nhận chất lượng dữ liệu CERT hoặc hiệu quả mô hình. Run: `runs/20261106-spec001-validation`. Google Doc chưa đồng bộ: đã chuẩn bị `.env` và `apps-script/Code.gs` theo DL-018, chờ deploy và URL Web App; không đánh dấu bước online hoàn thành.
