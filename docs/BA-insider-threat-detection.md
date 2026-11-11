# Phát hiện Insider Threat — Tài liệu BA

Tài liệu sống của project: hệ thống đang làm gì, đã code tới đâu, chạy thế nào, vì sao quyết định như vậy. Cập nhật **mỗi lần code**; mọi thay đổi có một dòng Decision Log.

Bản 2026-11-02 · Version 0.4

## 1. Tổng quan

- **Mục tiêu**: phát hiện insider threat bằng anomaly detection kết hợp 2 luồng (chuỗi + đặc trưng), chuẩn hành vi 3 tầng Personal – Group – Global, ngưỡng thích ứng.
- **Câu hỏi nghiên cứu**: RQ1 · RQ2 · RQ3 (nguyên văn: `references/research-proposal.md` của skill `insider-threat-model-dev`).
- **Dữ liệu**: CERT r4.2 (DL-007). Số user, số insider, khoảng ngày ghi sau khi đếm từ dữ liệu thật.
- **Nơi code**: `D:\AI for BA\MW\Framework-rework` (DL-005). Cấu trúc thư mục: `README.md` § Cấu trúc.

## 2. Trạng thái thành phần

| Thành phần | Spec | Trạng thái | Test | Run gần nhất |
|---|---|---|---|---|
| C1 Dữ liệu & nhãn | | Chưa làm | | |
| C2 Luồng đặc trưng | | Chưa làm | | |
| C3 Luồng chuỗi | | Chưa làm | | |
| C4 Hợp nhất điểm | | Chưa làm | | |
| C5 Chuẩn 3 tầng | | Chưa làm | | |
| C6 Ngưỡng thích ứng | | Chưa làm | | |
| C7 Đánh giá & ablation | | Chưa làm | | |

Trạng thái: Chưa làm · Spec draft · Spec accepted · Đang code · Xong · Cần sửa.

## 3. Dữ liệu

Chưa có. Điền khi C1 code xong: nguồn, đường dẫn, số dòng thực mỗi tệp; khoảng ngày train / val / test; số user-day và số user-day độc hại mỗi tập; quy tắc lọc user, cách gán nhãn.

## 4. Pipeline

Chưa code bước nào. Thư mục đã dựng sẵn cho từng thành phần C1–C7 (xem `README.md` § Thành phần ↔ chỗ đặt code).

## 5. Thành phần

Điền khi từng thành phần code xong.

## 6. Tham số đã tinh chỉnh

| Tầng | Tham số | Giá trị | Khoảng tìm | Mục tiêu (val) | Trial | Run |
|---|---|---|---|---|---|---|

## 7. Thí nghiệm & kết quả

| Ngày | Run | Cấu hình | RQ | PR-AUC | Recall@1% | FPR | Ghi chú |
|---|---|---|---|---|---|---|---|

Lần mở test: 0.

## 8. Cách chạy

```bash
# môi trường — venv Python 3.11 + PyTorch CUDA (DL-008); chưa tạo, lệnh ghi ở đây khi SPEC-001 code xong
# chuẩn bị dữ liệu — chưa có
# train / tune / evaluate — chưa có
# test — chưa có
```

## 9. Open Questions

OQ-02 và OQ-03 hoãn tới sau khi code C1 (DL-009): không chặn SPEC C1, nhưng phải chốt trước lần train đầu tiên. Các D-xx còn lại hỏi khi spec chạm tới.

| # | Câu hỏi | A (đề xuất) | B | C | Chặn |
|---|---|---|---|---|---|
| OQ-02 | Tỉ lệ chia thời gian train/val/test (D-02) | ~60/15/25 theo tháng | 50/20/30 | Train cố định N tháng đầu, phần còn lại test theo tuần | Lần train đầu tiên (C2/C3) |
| OQ-03 | Ngày độc hại rơi vào train (D-03) | Loại khỏi train, ghi rõ giả định "baseline sạch" | Giữ nguyên (thuần không giám sát) | Loại toàn bộ user insider khỏi train | Lần train đầu tiên (C2/C3) |

Câu đã trả lời → ghi Decision Log rồi xoá dòng ở đây (không đánh số lại).

## 10. Version History

| Version | Ngày | Thay đổi | Spec / DL |
|---|---|---|---|
| 0.1 | 2026-11-02 | Khởi tạo tài liệu; dựng khung thư mục project tại Framework-rework | DL-001 → DL-006 |
| 0.2 | 2026-11-02 | Chốt CERT r4.2 và môi trường Python 3.11 + CUDA; hoãn chia tập và xử lý ngày độc hại trong train tới sau khi code C1 | DL-007 → DL-009 |
| 0.3 | 2026-11-02 | Đẩy Google Doc bản 0.2 (thêm DL-005 → DL-009, tham số CERT r4.2, 4 thuật ngữ); người dùng yêu cầu đẩy trước khi code | — |
| 0.4 | 2026-11-02 | Đưa project + skill lên GitHub nhánh `master`, thay toàn bộ framework cũ | DL-010 |

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

## Cập nhật phạm vi 2026-11-10

| ID | Quyết định | Trạng thái |
|---|---|---|
| DL-046 | Chọn duy nhất một tầng Personal rồi Group rồi Global khi thiếu dữ liệu; bỏ SPEC-003, giữ SPEC-001/002. Ghép LDAP vào dữ liệu feature/sequence có sẵn | Theo yêu cầu trực tiếp người dùng; thay phương pháp trộn điểm. Điều kiện đủ dữ liệu và đầu vào score đang chờ chốt. Chưa triển khai/hiệu chỉnh threshold mới; docs/three-tier-routing-change.md ghi kiểm kê ZIP và giới hạn |

## Cập nhật kiểm kê 2026-11-11

| ID | Quyết định / bằng chứng | Trạng thái |
|---|---|---|
| DL-047 | Người dùng chọn A: kiểm dữ liệu và chuẩn bị thiết kế ghép LDAP trước; cài PyArrow19.0.1 theo approval công cụ. Quét đủ ba nhánh, cùng 330.452 user-day; sequence 12.523.202 row. LDAP thiếu Role 1.793, Department 6.637 user-day | Báo cáo docs/preprocessed-ldap-inventory.md; evidence runs/20261111-parquet-inventory/inventory.json. Không sửa source hoặc chấm score |
| DL-048 | Chuẩn bị SPEC-001 v1.1 bổ sung ghép Parquet vào output mới, bảo toàn feature/mask/sequence/OCEAN/f100, exact-month metadata và UNKNOWN khi thiếu | Draft chờ duyệt; chưa code join mới, chưa push hoặc cập nhật Google Doc. SPEC-002 chọn một tầng tiếp tục riêng |
| DL-049 | Người dùng accept SPEC-001 v1.1 ngày 2026-11-11; triển khai ghép LDAP cho ba nhánh Parquet và đối soát toàn bộ output | Đã duyệt phạm vi §14, không thay thuật toán scoring; triển khai đang chạy |

## Bàn giao SPEC-001 v1.1 — 2026-11-11

Đã ghép LDAP vào data/processed/CERT-r4.2-processed-two-branch-v1-ldap/. Code: src/itd/data/enrich_ldap.py; CLI: scripts/enrich_preprocessed_ldap.py; config: configs/experiments/enrich_ldap.json; hướng dẫn: docs/enrich-preprocessed-ldap-usage.md.

| ID | Quyết định / kết quả | Trạng thái |
|---|---|---|
| DL-050 | Triển khai SPEC-001 §14, output mới giữ nguyên feature/mask/f100/OCEAN/sequence. Sửa đóng reader trước cleanup staging khi test làm sai output trên Windows | 21 test qua trong 13.81s; run thật 296.898194s; feature/OCEAN 330.452 dòng mỗi nhánh, sequence 12.523.202; source hash khớp inventory. Evidence runs/20261111-spec001-ldap-enrichment |
| DL-051 | Giữ UNKNOWN và cờ riêng khi thiếu metadata, không loại user-day. Role thiếu 1.793, Department thiếu 6.637 trên cùng 330.452 khóa của ba nhánh | Đã đọc lại toàn bộ cột gốc và metadata, kiểm khóa/index và hash; không training/scoring/threshold mới. SPEC-002 chọn một tầng còn riêng |

Version History bổ sung: bản 0.27, 2026-11-11 — hoàn thành SPEC-001 v1.1, DL-049–051; cập nhật Luồng hoạt động local để đồng bộ Google Doc.
| DL-052 | Đẩy Google Doc bản 0.27 sau khi code SPEC-001 v1.1 READY và BA hoàn tất | Apps Script xác nhận ok=true, blocks=59 lúc 2026-11-11T12:40:06.478Z. Không có document session để đọc bình luận/readback; không tuyên bố đối soát online. Receipt: runs/20261111-spec001-ldap-enrichment/gdoc-upload.json |

## Chuẩn bị sửa SPEC-002 — 2026-11-11

| ID | Quyết định | Trạng thái |
|---|---|---|
| DL-053 | Personal ít nhất 7 ngày hoạt động trong 30 ngày trước; Group ít nhất 2 nhân viên trong train | Theo ủy quyền chọn phương án khả thi của người dùng; bộ khởi đầu chưa tune. Hoàn thiện định nghĩa quan sát hợp lệ sau khi chốt score |
| DL-054 | Giữ cả Department và Role và so sánh hiệu quả sau triển khai phương pháp chọn một tầng | Người dùng xác nhận; cùng data/split/Calibration, báo toàn tập và cold-start chung. SPEC-002 v1.1 §14 ghi đề xuất đánh giá; chưa chốt score, chưa duyệt bản sửa, chưa mở test mới |

| DL-055 | Người dùng chọn: chưa có điểm mô hình, trước mắt chỉ làm bộ chọn tầng và giao diện nhận điểm, chưa kết luận case tốt hơn | SPEC-002 Draft v1.2 §14 triển khai routing Personal→Group→Global và score adapter pass-through; không sinh score, threshold hoặc metric nhãn. Cùng hai case Department/Role. Chờ duyệt spec trước code |

Version History bổ sung: SPEC-002 Draft v1.2, 2026-11-11 — thu hẹp phạm vi theo DL-055, hoàn thiện API/state/config/AC router và giao diện nhận điểm; không chạy mô hình/test nghiên cứu hoặc cập nhật Google Doc trong bước thiết kế.
| DL-056 | Người dùng accept SPEC-002 v1.2 và yêu cầu bắt đầu code | Triển khai bộ chọn một tầng và giao diện nhận điểm, hai case Department/Role. Không tự tính score/threshold hoặc đánh giá hiệu quả phát hiện |

## Bàn giao SPEC-002 v1.2 — 2026-11-11

Code: src/itd/scoring/routing.py, score_input.py; runner: scripts/run_tier_routing.py; common và hai overlay configs/experiments/tier_routing_*.json. Hướng dẫn: docs/three-tier-usage.md.

| ID | Quyết định / kết quả | Trạng thái |
|---|---|---|
| DL-057 | Triển khai đúng bộ chọn một tầng và giao diện score ngoài theo bản accept. History 30 ngày, Personal 7 ngày, Group 2 người train; thiếu score không đổi tầng, không trộn hoặc tự tạo score/threshold | 151 test qua trong 12.91s; có review độc lập không phát hiện Blocker/Major. JUnit runs/20261111-spec002-routing-validation/pytest.xml |
| DL-058 | Chạy routing metadata thật train/Calibration, giữ cả hai case và đối soát lịch sử độc lập bằng bisect | 6.723866s, 84.066 row/case đều Personal vì lịch sử 19–30 ngày; Group/Global bằng 0, score trống. Không kết luận case tốt hơn hoặc đổi tham số để tạo khác biệt; không đánh giá test |

Version History bổ sung: bản 0.28, 2026-11-11 — hoàn thành SPEC-002 v1.2 router/interface, DL-056–058; xem verification.json ở runs/20261111-spec002-routing-validation và artifact run thật runs/20261111-spec002-tier-routing.
| DL-059 | Đẩy Google Doc bản 0.28 sau code READY và BA hoàn tất | Máy chủ trả ok=true, 68 blocks tại 2026-11-11T15:16:31.706Z. Không có document session để đọc comment/readback; chỉ xác nhận phản hồi gửi. Receipt runs/20261111-spec002-routing-validation/gdoc-upload.json |

## Dọn bộ bàn giao Git — 2026-11-11

| ID | Thay đổi | Bằng chứng |
|---|---|---|
| DL-060 | Người dùng yêu cầu bỏ file không cần cho lần chạy mới. Gitignore môi trường .venv-validation311, IDE, dataset roots và .local-archive; giữ nguyên dữ liệu/môi trường. Sao lưu rồi bỏ 6 script prototype và 4 bản xuất reports cũ khỏi thư mục làm việc | Backup .local-archive/legacy-before-routing-v1.2-20261111-66c7f465.zip và manifest checksum SHA-256 đã kiểm từng entry. Hai CLI/code/config/test/spec hiện hành giữ nguyên. Không thay logic, commit hoặc push |
Kiểm chứng sau dọn: Changes giảm từ 2.691 xuống 26 file; 151 test qua trong 8.69s. Môi trường Python, dữ liệu nguồn/output và evidence vẫn còn local; không thay lịch sử Git hoặc trạng thái stage.

## Đóng gói PR — 2026-11-11

| ID | Quyết định / kiểm chứng | Trạng thái |
|---|---|---|
| DL-061 | Người dùng yêu cầu push nhánh riêng và tạo PR. Đóng gói latest26 trong checkout riêng từ thanhhuong/three-tier; bỏ 23 file chỉ thuộc implementation cũ, giữ lịch sử commit7331adf | 151 test qua trong 11.29s trên chính checkout đóng gói. Diff mục tiêu vào master là 26 file code/config/test/spec/tài liệu; không chứa dataset, environment, secret hoặc run artifact. Không merge tự động |
