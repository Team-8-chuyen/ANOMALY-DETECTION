---
id: SPEC-001
title: Ghép Role và validation baseline
status: Implemented
version: 1.1
date: 2026-11-11
rq: [RQ2]
components: [C1, C5]
decisions: [DL-007, DL-008, DL-009, DL-011, DL-012, DL-013]
supersedes: null
---

# SPEC-001 — Ghép Role và validation baseline

> **Bản sửa 1.1 đã duyệt và triển khai ngày 2026-11-11:** bổ sung ghép LDAP vào Parquet theo §14. Phần §1–13 giữ lịch sử v1.0. Phạm vi ghép mới không phụ thuộc lựa chọn cách tính anomaly score của SPEC-002.

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

CLI thêm project/src vào sys.path. Tham chiếu scripts/fit_baselines.py ở bản v1.0 là script prototype cũ, đã lưu trữ local khi dọn bộ bàn giao mới. Không import script để chạy pipeline trong test.

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

## 14. Bổ sung v1.1 — Ghép LDAP vào feature và sequence Parquet

### 14.1 Mục tiêu và phạm vi

Theo DL-046 và lựa chọn A ngày 2026-11-11, nhận bộ dữ liệu đã tiền xử lý và bổ sung metadata cho hai cấu hình Group của RQ2. Chỉ join metadata, không tái tạo feature, token, mask, không huấn luyện, không tính score và không chia lại temporal split. Không dùng labels hoặc nội dung câu trả lời CERT cho join.

### 14.2 Hợp đồng đầu vào/đầu ra

- Root đầu vào: `data/processed/CERT-r4.2-processed-two-branch-v1/`, chứa `user_day_features/`, `user_day_features_ocean/`, `user_day_sequences/`. Xử lý cả ba để giữ metadata nhất quán; OCEAN chỉ được bảo toàn, không tự chọn dùng cho model.
- LDAP: `D:/CERT_r4.2/LDAP/YYYY-MM.csv`, cần user_id, role, department. Chuẩn hóa khoảng trắng khi tra khóa, duplicate normalized user/month phải lỗi. File/tháng không hợp lệ hoặc không có dữ liệu phải lỗi.
- Feature có khóa user/day duy nhất toàn nhánh, 100 double fNNN và 100 boolean mNNN; OCEAN thêm O,C,E,A,N. Sequence có user/day/event_index, index bắt đầu 0 và tăng 1 trong mỗi user-day. Kiểm schema nhất quán từng nhánh, user không rỗng, day không null và là ngày ở 00:00:00.
- Mỗi nhánh phải cùng tập user-day; số dòng sequence không bằng số user-day vì một ngày có nhiều sự kiện/cụm sự kiện.
- Output mặc định đề xuất: `data/processed/CERT-r4.2-processed-two-branch-v1-ldap/`. Giữ tên nhánh và bucket; chỉ tạo output mới, từ chối thư mục đã tồn tại hoặc output nằm trong input/LDAP.
- Giữ nguyên toàn bộ cột/dtype/giá trị/mask, số dòng và thứ tự vật lý trong từng bucket; thêm cuối schema: role:string, department:string, role_missing:bool, department_missing:bool, ldap_month:string (YYYY-MM theo day).
- Các tên metadata trên đã có trong input thì lỗi, không ghi đè im lặng. Không sao chép hoặc chạy code/config được đóng gói cùng dataset.

### 14.3 Quy tắc join

Từ từng row lấy (strip(user), month(day)), chỉ tra snapshot đúng tháng. Tìm được giá trị chuỗi hợp lệ thì lưu giá trị strip, missing=false. Không có snapshot/user hoặc ô rỗng/literal UNKNOWN thì ghi UNKNOWN và missing=true, không loại row. Không dùng LDAP tháng tương lai hoặc tự carry-forward tháng trước.

Sequence join many-to-one với bảng LDAP đã xác nhận duy nhất; không join trực tiếp bảng feature nhiều cột vào từng event. Không sort lại hay gộp sự kiện. Không chuyển đổi feature hoặc mask thành số khác.

`f100` (days_in_current_role) vẫn giữ nguyên kể cả đang bằng 0; bổ sung role không đồng nghĩa sửa feature này. Việc tính lại f100 hoặc mask là thay đổi preprocessing riêng, cần yêu cầu/thiết kế khác. Không đưa missing flags/metadata vào vector score một cách ngầm định.

### 14.4 API, config và code dự kiến

- Module mới `src/itd/data/enrich_ldap.py`, không thay file cùng tên trong dataset.
- `load_ldap_metadata(ldap_dir: Path) -> dict[tuple[str,str],dict[str,str]]`: mapping (user,month) đến role/department đã kiểm tra.
- `enrich_batch(batch: pyarrow.RecordBatch, metadata: dict) -> pyarrow.RecordBatch`: giữ row order, thêm metadata, không sửa batch gốc.
- `enrich_dataset(config: dict) -> dict`: validate, đọc/ghi batch, đối soát output, trả manifest.
- CLI mới `scripts/enrich_preprocessed_ldap.py --config configs/experiments/enrich_ldap.json`.
- Config: paths.input_root, paths.ldap_dir, paths.output_root; branches=[user_day_features,user_day_features_ocean,user_day_sequences]; batch_rows=65536; compression=zstd. Không có tùy chọn tự drop/impute, overwrite hoặc fallback snapshot.
- Dependency kiểm chứng Python3.11, NumPy1.26.4, PyArrow19.0.1; không cần pandas/polars cho join. PyArrow đã cài để kiểm kê theo approval công cụ.

### 14.5 Ghi file, đối soát và manifest

Đọc tuần tự theo file/batch, xử lý đầy đủ mọi row. Ghi vào thư mục tạm cùng parent output, chỉ publish bằng rename khi kiểm tra thành công; dọn đúng thư mục tạm của lần chạy khi lỗi. Không xóa source hoặc ghi output từng phần vào vị trí hoàn chỉnh.

Manifest JSON ghi config, phiên bản môi trường, schema từng nhánh trước/sau, SHA-256 từng input/LDAP/output, số file/row/user-day/date range; số missing theo nhánh, theo unique user-day và theo row; các kết quả bảo toàn. Không ghi toàn bộ nội dung nhân sự hoặc LDAP vào log.

Sau ghi, đọc lại output, chọn các cột gốc và đối chiếu với input theo từng file/batch, giá trị null phải khớp; đối chiếu schema gốc không gồm metadata và bỏ qua schema metadata pandas không biểu diễn cột mới. Output không được mang pandas schema metadata cũ sai lệch. Kiểm cùng tập khóa giữa nhánh và tính duy nhất/index trước/sau. Hash output dùng truy vết, không yêu cầu bằng input vì đã thêm cột.

### 14.6 Tiêu chí và test

| AC mới | Kiểm chứng |
|---|---|
| P-01 | Đúng user/tháng cho role và department; sửa LDAP tháng tương lai không đổi row tháng trước |
| P-02 | Thiếu một metadata chỉ flag trường đó; không mất row hoặc đổi mask |
| P-03 | Nhiều sequence row cùng user-day không nhân bản/mất/sắp lại row |
| P-04 | Đọc lại output bảo toàn tất cả giá trị/cột/dtype gốc; f100 và OCEAN không bị thay |
| P-05 | Khóa LDAP trùng, input thiếu cột, metadata đã tồn tại, ngày/key lỗi, schema bucket khác nhau phải dừng |
| P-06 | Bảo vệ source/output cũ; lỗi không công bố output hoàn chỉnh |
| P-07 | Manifest/hash/count/missing khớp fixture và run thật; mọi file được xử lý |

Test tại tests/test_enrich_ldap.py: ít nhất 2 tháng, 2 user, một người đổi nhóm, một ô role/department thiếu, sequence nhiều row cùng ngày, boundary batch cắt giữa một user-day, khóa trùng và output tồn tại. Không có test overfit vì không có mô hình học.

### 14.7 Lệnh, thời gian và nghiệm thu

Sau duyệt: triển khai → pytest fixture → chạy join thật vào output mới → đối soát đọc lại → BA và tài liệu. Lệnh dự kiến:

```powershell
.\.venv-validation311\Scripts\python.exe -m pytest tests/test_enrich_ldap.py -q
.\.venv-validation311\Scripts\python.exe scripts/enrich_preprocessed_ldap.py --config configs/experiments/enrich_ldap.json
```

Ước tính fixture dưới 1 phút; run thật có 12,5 triệu sequence row, dự kiến vài phút CPU nhưng phải đo thực tế. GPU/VRAM không dùng. Chưa chạy join thật hoặc đánh giá test; inventory chỉ kiểm cấu trúc/giá trị/metadata, không dùng nhãn hoặc tune.

### 14.8 Review bản sửa

Review riêng cho §14, không thay kết quả review v1.0. Kết quả kiểm kê và các giới hạn sẽ được liên kết trong docs/preprocessed-ldap-inventory.md trước khi trình bản sửa. Code chỉ bắt đầu khi người dùng accept SPEC-001 v1.1.

Kiểm kê đã hoàn tất: docs/preprocessed-ldap-inventory.md, bằng chứng runs/20261111-parquet-inventory/inventory.json. Ba nhánh cùng 330.452 user-day, sequence 12.523.202 row; không lỗi key/index/null/nonfinite trong phạm vi kiểm. Role thiếu 1.793 và Department thiếu 6.637 user-day; giữ quy tắc UNKNOWN đã nêu.

| Vòng review §14 | Kết quả |
|---|---|
| 1 — Đầy đủ và truy vết | Đã đọc lại; có input/output, schema thực tế, API/config, P-01–P-07 và phạm vi DL-046. Bảo toàn cả OCEAN, không tự chọn làm model input |
| 2 — Đúng đắn khoa học | Đã đọc lại; exact-month không carry-forward/future lookup, không fit/tune/labels; không đổi f100/mask, không lọc theo thiếu LDAP. Phân biệt kiểm cấu trúc với xác minh preprocessing |
| 3 — Sẵn sàng dev | Đã đọc lại; dependency đã có, module/CLI/test, output staging và kiểm đọc lại rõ; chưa tạo code/đánh giá test mới |

**READY để trình duyệt phần mở rộng v1.1**, không phải xác nhận đã triển khai. Các kết quả score/threshold cũ không liên quan đến nghiệm thu bước join mới.

### 14.9 Review code và kết quả thực hiện — 2026-11-11

Người dùng accept SPEC-001 v1.1, DL-049. Đã triển khai enrich_ldap.py, CLI enrich_preprocessed_ldap.py, config enrich_ldap.json, requirements-ldap.txt và 21 test trong test_enrich_ldap.py.

| Vòng review code | Kết quả |
|---|---|
| 1 — Khớp spec | P-01–P-07 có test/đối soát; exact-month, UNKNOWN, bảo toàn feature/mask/f100/OCEAN và sequence |
| 2 — Đúng đắn | Kiểm tương lai không ảnh hưởng quá khứ; đọc lại toàn bộ giá trị/metadata/khóa/index. Test làm sai output phát hiện lỗi; đã sửa đóng reader trước dọn staging trên Windows |
| 3 — Chạy và bàn giao | 21 test qua trong 13.81s; run thật 296.898194s, 192 Parquet output; source hashes và missing coverage khớp inventory. Hướng dẫn docs/enrich-preprocessed-ldap-usage.md |

Output: data/processed/CERT-r4.2-processed-two-branch-v1-ldap/. Feature và OCEAN mỗi nhánh 330.452 dòng; sequence 12.523.202 dòng; cùng 330.452 user-day. Role thiếu 1.793, Department thiếu 6.637 user-day; sequence tương ứng 70.165 và 300.323 row. Evidence: runs/20261111-spec001-ldap-enrichment/{manifest.json,verification.json,test-results.json,log.txt,env.txt,config.json,git.txt,source-sha256.json}.

**Code READY trong phạm vi §14**. Không training/scoring/test đánh giá hoặc chia split mới. SPEC-002 chọn một tầng chưa được sửa. Các ghi chú chờ duyệt trước §14.9 mô tả trạng thái trước khi accept.
