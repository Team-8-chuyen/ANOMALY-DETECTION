---
id: SPEC-001
title: Ghép Role và validation baseline
status: Draft
version: 0.1
date: 2026-11-09
rq: [RQ2]
components: [C1, C5]
decisions: [DL-007, DL-008, DL-009, DL-011, DL-012, DL-013]
supersedes: null
---

# SPEC-001 — Ghép Role và validation baseline

## 1. Mục tiêu

Ổn định bước ghép LDAP và hợp đồng đầu vào của baseline đang có. Phục vụ tiền đề cho chuẩn hành vi phân tầng trong Gap 2 / RQ2 của `research-proposal.md` thuộc skill; chưa phải triển khai hoàn chỉnh C1 hoặc C5. CERT r4.2 theo DL-007; lựa chọn thực hiện từng bước nhỏ theo DL-011.

## 2. Phạm vi

- Tiếp nhận module ghép Role đã sửa và kiểm chứng tại nguồn; tạo mới tại Team-8.
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

Import CLI theo cách của nguồn: thêm project/src vào sys.path. Không import script để chạy pipeline trong test.

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

Sau duyệt: chuyển module và CLI nguồn → chạy unit test và smoke fixture → review code → cập nhật BA. Dùng interpreter sẵn có ở repository cha: `..\.venv-validation311\Scripts\python.exe`. Không tạo venv hoặc cài dependency trong đợt chuyển này; kiểm phiên bản trước khi chạy.

Lệnh test từ gốc Team-8: `..\.venv-validation311\Scripts\python.exe -m pytest -q`. CLI: `..\.venv-validation311\Scripts\python.exe scripts/attach_roles.py --ldap-dir <fixture-LDAP> --input <fixture-features.csv> --output <temporary-output.csv>`.

Ước tính dưới 1 phút CPU, VRAM=0; cần đo thực tế. SPEC-002 mở rộng Group trên cùng module. Google Doc theo §14 sau nghiệm thu.

## 11. Rủi ro

| Rủi ro | Xử lý |
|---|---|
| Validation phát hiện dữ liệu thật lỗi | dừng, báo nguồn/dòng; không tự chọn sửa hoặc loại mẫu |
| Prototype chưa có score/threshold | không tuyên bố C5/C6 hoàn thành sau spec này |
| Split, train nhiễm bẩn còn mở | giữ OQ-02/OQ-03; không train/đánh giá trong đợt sửa này |
| Không đủ quyền truy cập Google Doc | báo trạng thái riêng, không coi cập nhật online đã xong |

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
