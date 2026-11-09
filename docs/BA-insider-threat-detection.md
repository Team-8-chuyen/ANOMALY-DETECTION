# Phát hiện Insider Threat — Tài liệu BA

Tài liệu sống của project: hệ thống đang làm gì, đã code tới đâu, chạy thế nào, vì sao quyết định như vậy. Cập nhật **mỗi lần code**; mọi thay đổi có một dòng Decision Log.

Bản 2026-11-09 · Version 0.5

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
| C5 Chuẩn 3 tầng | SPEC-002 v0.1 | Spec draft chuyển từ repository cha; chờ duyệt | Chưa chạy tại Team-8 | |
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
| 0.5 | 2026-11-09 | Chọn repository Team-8; chuẩn bị SPEC-001/002 kế thừa để duyệt, chưa chuyển code | DL-011 |

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
| DL-011 | Nơi triển khai | **Triển khai ba tầng tại repository Team-8 vừa clone** theo lựa chọn A của người dùng. SPEC-001/002 đang Draft; chưa coi lựa chọn nơi làm việc là duyệt thiết kế | Giữ nguyên công việc tại repository cha. **Phương án bị loại**: làm tại repository cha; đồng bộ cả hai | 2026-11-09 |
