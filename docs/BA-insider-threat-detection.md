# Phát hiện Insider Threat — Tài liệu BA

Tài liệu sống của project: hệ thống đang làm gì, đã code tới đâu, chạy thế nào, vì sao quyết định như vậy. Cập nhật **mỗi lần code**; mọi thay đổi có một dòng Decision Log.

Bản 2026-11-09 · Version 0.9

## 1. Tổng quan

- **Mục tiêu**: phát hiện insider threat bằng anomaly detection kết hợp 2 luồng (chuỗi + đặc trưng), chuẩn hành vi 3 tầng Personal – Group – Global, ngưỡng thích ứng.
- **Câu hỏi nghiên cứu**: RQ1 · RQ2 · RQ3 (nguyên văn: `references/research-proposal.md` của skill `insider-threat-model-dev`).
- **Dữ liệu**: CERT r4.2 (DL-007). Số user, số insider, khoảng ngày ghi sau khi đếm từ dữ liệu thật.
- **Nơi code**: `D:\AI for BA\MW\Framework-rework` (DL-005). Cấu trúc thư mục: `README.md` § Cấu trúc.

## 2. Trạng thái thành phần

| Thành phần | Spec | Trạng thái | Test | Run gần nhất |
|---|---|---|---|---|
| C1 Dữ liệu & nhãn | SPEC-001 v1.1 | Xong code; có resume | 6/6 | smoke hàm |
| C2 Luồng đặc trưng | SPEC-001 v1.1 | Xong code; checkpoint/bucket | 6/6 | smoke hàm |
| C3 Luồng chuỗi | SPEC-001 v1.1 | Xong code; checkpoint/bucket | 6/6 | smoke hàm |
| C4 Hợp nhất điểm | SPEC-002 v1.0 | Xong code; chưa chạy full | 15/15 | synthetic smoke |
| C5 Chuẩn 3 tầng | | Chưa làm | | |
| C6 Ngưỡng thích ứng | | Chưa làm | | |
| C7 Đánh giá & ablation | | Chưa làm | | |

Trạng thái: Chưa làm · Spec draft · Spec accepted · Đang code · Xong · Cần sửa.

## 3. Dữ liệu

Chưa có. Điền khi C1 code xong: nguồn, đường dẫn, số dòng thực mỗi tệp; khoảng ngày train / val / test; số user-day và số user-day độc hại mỗi tập; quy tắc lọc user, cách gán nhãn.

## 4. Pipeline

Đã code tiền xử lý C1–C3 theo SPEC-001: đọc CSV theo chunk, chia 64 bucket user, tạo canonical Parquet, Behaviour100 + mask, OCEAN ablation và Sequence24 có nén run. Chưa chạy full CERT và chưa huấn luyện mô hình.

## 5. Thành phần

- `src/itd/data/`: đọc/chuẩn hóa CERT, LDAP as-of và nhãn tùy chọn.
- `src/itd/features/count_features.py`: registry và công thức 100 đặc trưng.
- `src/itd/features/sequence_tokens.py`: 24 trường chuỗi và nén run 5 phút.
- `scripts/prepare_data.py`: CLI đầu-cuối; không ghi đè nếu thiếu `--force`.

## 6. Tham số đã tinh chỉnh

| Tầng | Tham số | Giá trị | Khoảng tìm | Mục tiêu (val) | Trial | Run |
|---|---|---|---|---|---|---|

## 7. Thí nghiệm & kết quả

| Ngày | Run | Cấu hình | RQ | PR-AUC | Recall@1% | FPR | Ghi chú |
|---|---|---|---|---|---|---|---|

Lần mở test: 0.

## 8. Cách chạy

```bash
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python scripts\prepare_data.py --config configs/base.yaml
# tiếp tục sau khi tắt máy hoặc tiến trình bị dừng
.\.venv\Scripts\python scripts\prepare_data.py --config configs/base.yaml --resume
# chuẩn bị dữ liệu model và huấn luyện không giám sát; chưa tự chạy full
\.venv\Scripts\python scripts\prepare_model_data.py --config configs/base.yaml
\.venv\Scripts\python scripts\train.py --config configs/base.yaml --branch behaviour
\.venv\Scripts\python scripts\train.py --config configs/base.yaml --branch sequence
\.venv\Scripts\python scripts\score.py --behaviour runs/<beh-run>/behaviour_scores.parquet --sequence runs/<seq-run>/sequence_scores.parquet --output runs/<fusion-run>/scores.parquet
# evaluate test — chưa chạy; cần xác nhận riêng trước khi mở test
```

## 9. Open Questions

OQ-02 và OQ-03 hoãn tới sau khi code C1 (DL-009): không chặn SPEC C1, nhưng phải chốt trước lần train đầu tiên. Các D-xx còn lại hỏi khi spec chạm tới.

| # | Câu hỏi | A (đề xuất) | B | C | Chặn |
|---|---|---|---|---|---|

Câu đã trả lời → ghi Decision Log rồi xoá dòng ở đây (không đánh số lại).

## 10. Version History

| Version | Ngày | Thay đổi | Spec / DL |
|---|---|---|---|
| 0.1 | 2026-11-02 | Khởi tạo tài liệu; dựng khung thư mục project tại Framework-rework | DL-001 → DL-006 |
| 0.2 | 2026-11-02 | Chốt CERT r4.2 và môi trường Python 3.11 + CUDA; hoãn chia tập và xử lý ngày độc hại trong train tới sau khi code C1 | DL-007 → DL-009 |
| 0.3 | 2026-11-02 | Đẩy Google Doc bản 0.2 (thêm DL-005 → DL-009, tham số CERT r4.2, 4 thuật ngữ); người dùng yêu cầu đẩy trước khi code | — |
| 0.4 | 2026-11-02 | Đưa project + skill lên GitHub nhánh `master`, thay toàn bộ framework cũ | DL-010 |
| 0.5 | 2026-11-09 | Chốt thiết kế tiền xử lý hai nhánh và tạo SPEC-001 v0.1 để chờ duyệt | DL-011 → DL-013 |
| 0.6 | 2026-11-09 | Người dùng duyệt SPEC-001 v1.0 để bắt đầu triển khai | DL-014 |
| 0.7 | 2026-11-09 | Hoàn thành code SPEC-001; 4/4 test qua; full CERT chưa chạy | DL-015 |
| 0.8 | 2026-11-09 | Duyệt checkpoint theo user bucket và chế độ resume của SPEC-001 v1.1 | DL-016 |
| 0.9 | 2026-11-09 | Hoàn thành checkpoint/resume, process lock và ETA; 6/6 test qua | DL-017 |
| 1.0 | 2026-11-10 | Chốt thiết kế train không giám sát và tạo SPEC-002 v0.1 chờ duyệt | DL-018 → DL-021 |
| 1.1 | 2026-11-10 | Người dùng duyệt SPEC-002 v1.0 và cho phép bắt đầu code model | DL-022 |
| 1.2 | 2026-11-10 | Hoàn thành code hai Autoencoder, trainer, score fusion và 15 test; chưa chạy full training | DL-023 |

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
| DL-011 | OQ-04 · C2 | **Nhánh Behaviour dùng đúng 100 đặc trưng:** mỗi nguồn Logon/Device/File/HTTP/Email có 16, Cross-source 12, History 8 | Người dùng chốt phương án A ngày 09/11/2026. Giữ năm nguồn cân bằng, vẫn có ngữ cảnh và lịch sử. **Phương án bị loại**: 80 đặc trưng — mất tín hiệu; 120 — tăng dư thừa và làm Behaviour quá nặng | 2026-11-09 |
| DL-012 | OQ-05 · C2 | **OCEAN không nằm trong pipeline chính; chỉ tạo ablation Behaviour100 + OCEAN5** | Người dùng chốt phương án A ngày 09/11/2026. OCEAN là hồ sơ tĩnh và không có đối xứng ở Sequence. **Phương án bị loại**: đưa vào Behaviour chính; loại hoàn toàn | 2026-11-09 |
| DL-013 | OQ-06 · D-05 · C3 | **Nén chuỗi bằng cách gộp event liên tiếp cùng token, cùng PC, gap ≤5 phút; giữ `run_count` và `run_span`; chưa cắt `max_len` ở tiền xử lý** | Người dùng chốt phương án A ngày 09/11/2026. Giảm HTTP lấn át mà vẫn giữ cường độ/thời lượng. **Phương án bị loại**: cắt lấy đuôi ngày; chia nhiều cửa sổ lấy max | 2026-11-09 |
| DL-014 | SPEC-001 | **Duyệt SPEC-001 v1.0 và cho phép bắt đầu code tiền xử lý C1–C3** | Người dùng trả lời “ok” sau khi được trình bản spec READY ngày 09/11/2026 | 2026-11-09 |
| DL-015 | SPEC-001 · C1–C3 | **Triển khai tiền xử lý theo bucket user và Parquet nén Zstandard; chưa tự chạy full CERT** | Bucket giữ toàn bộ lịch sử của một user để tính quá khứ đúng nhưng giới hạn RAM. 4/4 test và smoke chuẩn hóa qua. **Phương án bị loại**: nạp toàn bộ log vào RAM; tự chạy full dữ liệu nhiều giờ khi người dùng chưa yêu cầu | 2026-11-09 |
| DL-016 | SPEC-001 v1.1 · vận hành | **Checkpoint và resume theo `user_bucket`; không checkpoint theo ngày hoặc bucket-tháng** | Người dùng duyệt phương án A ngày 09/11/2026. Toàn bộ lịch sử một user nằm cùng bucket nên tắt/mở máy không làm sai đặc trưng 7/30 ngày. Bucket đang dở được làm lại; bucket hoàn thành được giữ nguyên | 2026-11-09 |
| DL-017 | SPEC-001 v1.1 · code | **`--resume` bỏ qua canonical đã đủ năm nguồn, checkpoint sau mỗi bucket và dùng lock chống chạy trùng** | 6/6 test qua. Checkpoint chỉ được ghi sau khi đủ output nên mất điện không đánh dấu nhầm bucket dở. **Phương án bị loại**: tin vào sự tồn tại của một tệp đơn lẻ; cho nhiều pipeline chạy đồng thời | 2026-11-09 |
| DL-018 | D-02 · split | **Chia thời gian train/validation/test xấp xỉ 60/15/25 trên cùng trục ngày** | Người dùng chọn bộ khuyến nghị ngày 10/11/2026. Giữ thứ tự thời gian và dành test đủ dài. **Phương án bị loại**: 50/20/30; đánh giá online theo tuần | 2026-11-10 |
| DL-019 | D-03 · unsupervised | **Giữ nguyên các user-day độc hại nếu rơi vào train; nhãn không được dùng trong huấn luyện hoặc chọn tham số** | Khớp yêu cầu học không giám sát nghiêm ngặt. **Phương án bị loại**: dùng answers làm sạch train; loại toàn bộ insider | 2026-11-10 |
| DL-020 | D-04 · Sequence | **TCN–Transformer Autoencoder tái tạo token và thuộc tính sự kiện** | Khớp nguyên tắc hai nhánh tái tạo độc lập và tạo reconstruction error trực tiếp. **Phương án bị loại**: masked prediction; next-token prediction | 2026-11-10 |
| DL-021 | D-06 · fusion | **Cố định alpha=0.5 sau chuẩn hóa robust riêng từng nhánh; chỉ phân tích độ nhạy alpha** | Cân bằng hai nhánh mà không dùng nhãn. **Phương án bị loại**: cân phương sai trên validation; learned gating | 2026-11-10 |
| DL-022 | SPEC-002 | **Duyệt SPEC-002 v1.0 và bắt đầu triển khai hai model không giám sát** | Người dùng trả lời “sửa code đi” sau khi được trình SPEC-002 READY | 2026-11-10 |
| DL-023 | SPEC-002 · code | **Triển khai Behaviour AE, TCN–Transformer AE, split thời gian, parser nhãn r4.2, trainer checkpoint/resume và late fusion** | 15/15 test qua trên Python 3.11 + PyTorch 2.15 CPU; CLI help chạy được. Chưa chạy chuẩn bị model data hoặc full training để không tự mở test/tốn nhiều giờ. **Phương án bị loại**: tự chạy full ngay; để label đi vào trainer | 2026-11-10 |
