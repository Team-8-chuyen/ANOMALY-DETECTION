# Phát hiện Insider Threat — Tài liệu BA

Tài liệu sống của project: hệ thống đang làm gì, đã code tới đâu, chạy thế nào, vì sao quyết định như vậy. Cập nhật **mỗi lần code**; mọi thay đổi có một dòng Decision Log.

Bản 2026-11-12 · Version 0.31 · LDAP/router và pilot IF + LSTM đã chạy

## 1. Tổng quan

- **Phạm vi đã code**: ghép LDAP, chọn duy nhất Personal/Group/Global, Feature Isolation Forest và Sequence LSTM Autoencoder trên pilot CPU. Hai điểm thô là đầu vào cho bước hợp nhất/chuẩn tầng/threshold được thiết kế nối tiếp.
- **Câu hỏi nghiên cứu**: RQ1 · RQ2 · RQ3 (nguyên văn: `references/research-proposal.md` của skill `insider-threat-model-dev`).
- **Dữ liệu**: CERT r4.2 đã tiền xử lý và ghép LDAP, xem §3.
- **Nơi code hiện tại**: `C:\Users\Admin\Projects\ANOMALY-DETECTION`. Đường dẫn khác trong Decision Log là lịch sử các phiên trước.

## 2. Trạng thái thành phần

| Thành phần | Spec | Trạng thái | Test | Run gần nhất |
|---|---|---|---|---|
| C1 Ghép dữ liệu LDAP | SPEC-001 v1.1 | Xong enrichment và đối soát bảo toàn | test_enrich_ldap.py | 20261111-spec001-ldap-enrichment |
| C2 Feature Isolation Forest | SPEC-004 v1.0 | Xong pilot CPU | test_feature_preprocessing.py, test_feature_isolation_forest.py | 20261112-if-lstm-cpu-pilot-01 |
| C3 Sequence LSTM AE | SPEC-004 v1.0 | Xong pilot CPU một epoch | test_sequence_*.py, test_lstm_autoencoder.py | Cùng pilot IF |
| C4 Hợp nhất điểm | — | Chưa triển khai cho hai raw score | — | — |
| C5 Bộ chọn ba tầng/giao diện điểm | SPEC-002 v1.2 | Xong router một tầng, hai case Department/Role | test_routing.py, test_score_input.py, test_tier_routing_cli.py | 20261111-spec002-tier-routing |
| C6 Threshold cuối | — | Chờ protocol score/Calibration mới | — | — |
| C7 Đánh giá ablation | — | Chưa đánh giá hai model mới | — | — |

Trạng thái: Chưa làm · Spec draft · Spec accepted · Đang code · Xong · Cần sửa.

## 3. Dữ liệu

Nguồn `data/processed/CERT-r4.2-processed-two-branch-v1-ldap/` giữ cùng 330.452 user-day ở Feature, Feature+OCEAN và Sequence. Sequence có 12.523.202 row run nén. LDAP được ghép đúng tháng; role/department thiếu vẫn giữ UNKNOWN và cờ thiếu.

Pilot dùng Feature100+mask100 và Sequence24 trên cùng 20 nhân viên, fit 02–22/01/2010 và validation 23–31/01. Nguồn train nghiên cứu 01–05/2010 có 0 malicious user-day theo audit đã đối chiếu; chính sách loại user-day độc hại giữ nguyên DL-034. Calibration 06–09/2010 và test 10/2010–05/2011 giữ nguyên ngoài pilot.

## 4. Pipeline

Hệ thống kiểm tra provenance và khóa hai nhánh, fit preprocessor từ train rồi chạy IF/LSTM. Mỗi ngày validation có hai điểm thô riêng. Bộ chọn Personal/Group/Global của SPEC-002 tiếp tục hoạt động trên metadata quá khứ; hợp nhất/chuẩn hóa raw score và threshold là bước phát triển sau (→ DL-055/067/070).

## 5. Thành phần

| Thành phần đang dùng | Tệp chính |
|---|---|
| Đọc/chuẩn bị hai nhánh | src/itd/data/pilot_dataset.py, feature_preprocessing.py, sequence_dataset.py, sequence_preprocessing.py |
| Hai model | src/itd/models/feature_isolation_forest.py, lstm_autoencoder.py |
| Training/đo/provenance/config | src/itd/training/sequence_trainer.py, pilot_benchmark.py, pilot_provenance.py, pilot_config.py |
| CLI và hướng dẫn | scripts/run_if_lstm_pilot.py; docs/if-lstm-cpu-pilot-usage.md |

## 6. Cấu hình pilot đã chạy

| Thành phần | Cấu hình |
|---|---|
| IF | 100 cây, tối đa256 mẫu/cây, median fit +mask thành200 đầu vào |
| LSTM AE | Embedding4, encoder/decoder một lớp hidden32, latent16, window128 |
| Training | CPU2thread, batch64, một epoch, AdamW lr0.001, seed0, ngân sách300s |
| Warmup | Ba bước trên model tạm, bỏ weights và reset RNG trước epoch thật |
| Nguồn cấu hình | configs/experiments/if_lstm_cpu_pilot.json |

Các giá trị là cấu hình pilot đã duyệt, chưa được tune bằng Optuna. Chi tiết và công thức nằm trong SPEC-004 v1.0.

## 7. Thí nghiệm & kết quả

| Run ngày2026-11-12 | Số đo thật |
|---|---|
| 20261112-if-lstm-cpu-pilot-01 | Complete;305 fit và103 validation user-day;12159/4052 sequence row |
| Fit IF / chấm validation | 0,22296s /0,00691s |
| Một epoch LSTM / chấm validation | 1,08128s /0,22207s |
| Đọc dữ liệu / tổng wall | 11,37159s /24,64685s |
| Đầu ra | 103 row hai raw score hữu hạn; LSTM23.443 tham số |
| Ngoại suy theo sequence steps | 355,60s/epoch full train;20epoch giả định1,98giờ |
| Ngoại suy theo user-day | 372,85s/epoch full train;20epoch giả định2,07giờ |

Hai ngoại suy không là CI hoặc cận; chỉ training, chưa đo full IF/full validation/full total. Pilot không mở test nghiên cứu và chưa có chỉ số phát hiện. Kết quả test thống kê cũ thuộc lịch sử SPEC-002.

## 8. Cách chạy

```powershell
.\.venv-validation311\Scripts\python.exe -m pytest -q
.\.venv-validation311\Scripts\python.exe scripts/run_if_lstm_pilot.py --config configs/experiments/if_lstm_cpu_pilot.json --run-dir runs/20261112-if-lstm-cpu-pilot-01
```

Lệnh pilot trên đã chạy; chạy lại dùng run ID mới. Môi trường CPU đã cài pin requirements-models-cpu.txt. Hướng dẫn đầy đủ: docs/if-lstm-cpu-pilot-usage.md; phần LDAP/router: docs/three-tier-usage.md.

## 9. Open Questions

OQ-02/03 đã chốt qua DL-033/034; OQ-17 mask đã chốt DL-069. Không còn câu hỏi chặn SPEC-004 pilot. Protocol hợp nhất điểm, chuẩn tầng và Calibration cần thiết kế riêng khi người dùng yêu cầu bước tiếp theo.

## 10. Version History

| Version | Ngày | Thay đổi | Spec / DL |
|---|---|---|---|
| 0.1 | 2026-11-02 | Khởi tạo tài liệu; dựng khung thư mục project tại Framework-rework | DL-001 → DL-006 |
| 0.2 | 2026-11-02 | Chốt CERT r4.2 và môi trường Python 3.11 + CUDA; hoãn chia tập và xử lý ngày độc hại trong train tới sau khi code C1 | DL-007 → DL-009 |
| 0.3 | 2026-11-02 | Đẩy Google Doc bản 0.2 (thêm DL-005 → DL-009, tham số CERT r4.2, 4 thuật ngữ); người dùng yêu cầu đẩy trước khi code | — |
| 0.4 | 2026-11-02 | Đưa project + skill lên GitHub nhánh `master`, thay toàn bộ framework cũ | DL-010 |
| 0.31 | 2026-11-12 | Hoàn tất code và pilot IF + LSTM CPU; đồng bộ trạng thái hiện hành, kết quả và hướng dẫn | SPEC-004 v1.0, DL-070–072 |

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

## Hướng training mới — 2026-11-12

| ID | Quyết định | Trạng thái |
|---|---|---|
| DL-062 | Người dùng đổi hướng: không dùng hybrid TCN–Transformer Autoencoder; chỉ một mô hình chuỗi, không train Feature AE trong đợt này | Tên TCN Autoencoder hay Transformer Autoencoder còn chờ xác nhận. Không thay code router, chưa cài PyTorch hoặc training |
| DL-063 | Giữ lựa chọn kiểm thử mô hình nhỏ trên CPU trước, training đầy đủ trên GPU sau | Theo câu trả lời trước của người dùng. Kiểm tra môi trường hiện chỉ thấy Intel Iris Xe, PyTorch chưa cài; bằng chứng train-only sequence lengths: runs/20261111-training-feasibility/summary.json |
| DL-064 | Người dùng chọn **TCN Autoencoder đơn**, bản nhỏ kiểm thử CPU | Đã xác nhận tên model, thay trạng thái chờ xác nhận ở DL-062. Không train Feature AE hoặc hybrid TCN–Transformer trong đợt này |
| DL-065 | Người dùng chọn tái tạo **cả 24 thuộc tính sequence**, có mask và loss phù hợp trường dạng chữ/số/đúng-sai | Thay lựa chọn chỉ tái tạo event_token. Thiết kế chi tiết embedding/loss/kiến trúc trong SPEC-004 Draft0.1, chờ duyệt trước code |
| DL-066 | Người dùng chọn pilot **tối đa 20 nhân viên trong 01/2010; fit 02–22/01, validation 23–31/01** | Giữ nguyên Calibration/test nghiên cứu ngoài pilot, không dùng để early stop. Quy tắc chọn cohort có seed và cấu hình training cụ thể đang trình trong SPEC-004 |

Lịch sử: SPEC-004 Draft0.1 TCN đã trình nhưng chưa được duyệt. Bản đang sửa chuyển sang [SPEC-004 — IF + LSTM CPU pilot](../specs/SPEC-004-if-lstm-cpu-pilot.md), Draft0.2 theo DL-067–069. Kiểm kê read-only theo cohort hash seed0: fit12.159 sequence row/305user-day, validation4.052row/103user-day,20user; chưa training/cài PyTorch. Evidence: runs/20261112-tcn-spec-evidence/pilot-inventory.json. Giữ SPEC-001/002 và Department/Role; SPEC-003 tiếp tục đã rút.

Version History bổ sung: 0.29-draft, 2026-11-12 — DL-062–066, chuẩn bị spec model chuỗi đơn theo yêu cầu mới; chưa cập nhật Google Doc trong giai đoạn spec.

## Đánh giá hướng Isolation Forest + LSTM Autoencoder — 2026-11-12

| ID | Quyết định / yêu cầu | Trạng thái |
|---|---|---|
| DL-067 | Người dùng yêu cầu hướng hai model riêng: **Feature = Isolation Forest; Sequence = LSTM Autoencoder**, trước hết ước tính runtime và nhận xét phương pháp | Thay hướng TCN đơn ở DL-064 cho thiết kế tiếp theo. SPEC-004 TCN hiện vẫn Draft, chưa được accept hoặc triển khai; cần sửa thiết kế trước khi code theo hướng mới. Lần này chỉ kiểm môi trường/dữ liệu và tư vấn, không cài thư viện hoặc training |

Môi trường đọc lại: CPU i5-1135G7 @2.40GHz, 8 logical processor, RAM vật lý khả dụng cho hệ điều hành 11.73 GiB, RAM trống lúc đo 1.42 GiB; Python 3.11.9, chưa có torch hoặc sklearn. Dữ liệu train nghiên cứu có 105.171 user-day, sequence có 3.998.777 row nén, chiều dài tối đa124; pilot tháng01/2010 có305 fit và103 validation user-day. Hai model dùng chung cho các user/case; không dự toán model riêng cho mỗi user/nhóm.

**Ước lượng dự trù, chưa benchmark:** IF100–200 cây, max_samples256, 100 feature gốc và xử lý mask: fit khối lượng train khoảng10–60s, score330.452 user-day khoảng10–120s. LSTM encoder/decoder nhỏ mỗi phía1layer, hidden32–64, batch64, window≤128, đủ Sequence24 typed loss/mask: khoảng2–12phút/epoch ở khối lượng train trên;20epoch khoảng40phút–4giờ chỉ training. Pilot305 fit user-day/5epoch khoảng1–5phút. Dự trù đầu-cuối một lần đầy đủ khoảng1–5giờ gồm I/O/validation/scoring, chưa gồm cài đặt, code/test, Optuna hoặc nhiều seed; có thể lệch vài lần do RAM, padding, backend và kiến trúc. Không có cam kết thời gian trên máy khi chưa đo1epoch thực tế.

Nhận xét: hai nhánh bổ sung tín hiệu tổ hợp feature và thứ tự trong ngày; cần chuẩn chiều/thang điểm trước hợp nhất và áp chuẩn duy nhất ở tầng được chọn rồi threshold cuối trên Calibration. IF là isolation score, không phải reconstruction error; hướng mới cần mô tả Method tương ứng. Không kết luận hơn TCN hoặc Department/Role. Calibration hiện đều Personal, cần một protocol cold-start riêng được định nghĩa trước khi so sánh Group. Nguồn tham chiếu: [scikit-learn IsolationForest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html), [LSTM encoder-decoder gốc](https://arxiv.org/abs/1607.00148).

| ID | Quyết định | Trạng thái |
|---|---|---|
| DL-068 | Người dùng chọn **A: pilot IF + LSTM AE trên cùng 20 nhân viên, đo một epoch LSTM trước khi dự toán đầy đủ** | Giữ fit 02–22/01/2010, validation 23–31/01, train sạch và Sequence24 typed loss/mask đã chọn. SPEC-004 cần sửa thành Draft0.2; lựa chọn pilot không thay việc duyệt thiết kế mới trước code |
| DL-069 | Người dùng chọn **IF điền median của train vào feature mask=false, ghép100 cờ mask thành200 đầu vào** | Thay lựa chọn điền0 hoặc bỏ mask. Median chỉ fit từ ô active của train; masked payload không là quan sát thật. Kiểm kê305 feature row của pilot:76 feature luôn active,24 feature có ô không áp dụng, không feature nào hoàn toàn inactive |

Đã hoàn thiện [SPEC-004 v0.2 — IF + LSTM CPU pilot](../specs/SPEC-004-if-lstm-cpu-pilot.md): IF100cây/max_samples256, LSTM một lớp hidden32/latent16, batch64, **đúng một epoch** trên cùng20user;305 fit và103 validation user-day. Các tham số là đề xuất trình duyệt, chưa được ghi thành kết quả training. Có12AC, raw score riêng hai nhánh, timing riêng và ngoại suy train dựa epoch hoàn chỉnh, không giả CI hoặc full total đã đo.

Review spec ba vòng READY,0Blocker/0Major còn mở; review khoa học độc lập sửa một tên artifact cho thống nhất. Đổi tên file từ SPEC-004-tcn-autoencoder-cpu.md sang SPEC-004-if-lstm-cpu-pilot.md, giữ ID004 và lịch sử Draft0.1 trong spec/DL. Chưa code/cài dependency/chạy pilot hoặc cập nhật Google Doc. Version History bổ sung:0.30-draft,2026-11-12, DL-067–069, chờ duyệt bản sửa trước triển khai.

| ID | Quyết định | Trạng thái |
|---|---|---|
| DL-070 | Người dùng nói rõ **“code đi, accept SPEC-004 v0.2”** ngày2026-11-12; duyệt thiết kế IF+LSTM CPU pilot thành SPEC-004 Accepted v1.0 | Được triển khai code/tests, cài dependency đã pin, chạy pilot20 nhân viên và một epoch LSTM. Giữ nguyên scope raw score/runtime, không full training/Calibration/test hoặc thay router |

Tại thời điểm DL-070, C2 Feature IF và C3 LSTM AE bắt đầu code theo SPEC-004 v1.0. Các dòng Draft/chưa duyệt ở trên là lịch sử; kết quả bàn giao nằm sau DL-071/072.

## Bàn giao IF + LSTM CPU pilot — 2026-11-12

| ID | Kết quả / quyết định | Bằng chứng |
|---|---|---|
| DL-071 | Triển khai đúng SPEC-004 v1.0; pin dependencies đã cài. Sửa lỗi cơ học trong review: reader/provenance dùng cùng recursive coverage, canonical padded count, reset runtime khi ghi artifact lỗi, ghi hash code chưa tracked | 330 test qua43,91s; có kiểm warmup không giữ weights và score sau load checkpoint khớp; reviewer độc lập READY,0Blocker/0Major. JUnit runs/20261112-spec004-validation/pytest.xml |
| DL-072 | Chạy pilot thật đúng một epoch trên cùng20 nhân viên, output103 row hai raw score. Giữ hai case Department/Role và chuẩn một tầng; ngoại suy từ epoch hoàn chỉnh, không gọi CI hoặc chạy full | Run runs/20261112-if-lstm-cpu-pilot-01 complete trong24,64685s; IFfit0,22296s; LSTMepoch1,08128s. Chi tiết và giới hạn docs/if-lstm-cpu-pilot-usage.md |

**C2/C3 đã xong pilot; SPEC-004 v1.0 Implemented.** README, hướng dẫn sử dụng và Luồng hoạt động local bản0.31 phản ánh code/run thật. Full training, fusion/chuẩn tầng/Calibration và kết luận Group tốt hơn vẫn là bước sau.

| ID | Thay đổi | Kết quả |
|---|---|---|
| DL-073 | Gửi Google Doc bản0.31 sau code READY và BA hoàn tất | Apps Script trả ok=true,78blocks tại2026-11-12T09:23:05.602Z. Không có connected document session; web export không truy cập được. Đã xác nhận gửi nhưng chưa review comment/readback online. Receipt runs/20261112-spec004-validation/gdoc-upload.json |

Google Doc: [Tài liệu Code](https://docs.google.com/document/d/1rLFe6HQzlHrnTipuaOe5IsP8uqrMn_xPeig_IXZM7gc/edit), bổ sung §14 pilot hai model và cập nhật tổng quan; giữ riêng giới hạn xác nhận online.
