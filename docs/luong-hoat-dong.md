# Phát hiện Insider Threat — Luồng hoạt động của hệ thống

Cập nhật 2026-11-02 · Bản 0.2 · Chưa code bước nào

## 1. Tổng quan

Hệ thống phát hiện nhân viên nội bộ có hành vi bất thường (insider threat) từ nhật ký hoạt động trên máy tính. Đầu vào là log đăng nhập, USB, file, email và web của bộ dữ liệu CERT bản r4.2. Đầu ra là danh sách cảnh báo theo từng người dùng, từng ngày. Hệ thống chấm điểm mỗi ngày bằng hai mô hình: một mô hình đếm khối lượng thao tác, một mô hình đọc thứ tự thao tác. Điểm được so với thói quen của chính người đó, của nhóm cùng vai trò và của toàn công ty. Mỗi người có ngưỡng cảnh báo riêng. Hệ thống trả lời ba câu hỏi nghiên cứu RQ1, RQ2, RQ3. Đã dựng khung thư mục project tại `Framework-rework`; đã code 0/7 bước.

## 2. Luồng tổng

Đã code 0/7 bước. Bước kế tiếp là bước 1 — chuẩn bị dữ liệu CERT r4.2 và gán nhãn từng user-day (SPEC-001, chưa viết).

## 3. Tham số đang dùng

| Tham số (tên dễ hiểu) | Khoá config | Giá trị | Ý nghĩa | Cách chọn |
|---|---|---|---|---|
| Phiên bản bộ dữ liệu CERT | `data.cert_version` | r4.2 | Hệ thống đọc log và đáp án insider của bản r4.2 | Người dùng chốt (→ DL-007) |

## 4. Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| Insider threat | Rủi ro do người trong tổ chức có quyền truy cập hợp pháp gây ra, cố ý hoặc vô ý |
| Anomaly detection | Cách phát hiện bằng việc học hành vi bình thường rồi đánh dấu ngày lệch khỏi nó, không cần nhiều ví dụ tấn công |
| CERT r4.2 | Bộ dữ liệu log mô phỏng một công ty khoảng 1000 nhân viên, có đánh dấu sẵn các insider theo 3 kịch bản |
| User-day | Một người dùng trong một ngày; là đơn vị hệ thống chấm điểm và cảnh báo |
| Optuna | Thư viện tự thử nhiều bộ tham số và giữ bộ cho kết quả tốt nhất |
| Tập validation | Phần dữ liệu ở giữa giai đoạn, chỉ dùng để chọn tham số, không dùng để báo cáo kết quả |
| Rò rỉ dữ liệu (leakage) | Thông tin của phần dùng để đánh giá lọt vào lúc học hoặc lúc chọn tham số, làm kết quả đẹp hơn thực tế |
| venv | Môi trường Python riêng của project, giữ đúng phiên bản thư viện để chạy lại ra cùng kết quả |
| CUDA | Phần mềm của NVIDIA cho phép PyTorch huấn luyện mô hình trên card đồ hoạ thay vì CPU |

## 5. Decision Log

| # | Liên quan | Quyết định | Lý do | Ngày |
|---|---|---|---|---|
| DL-001 | Phạm vi project | **Project chỉ gồm pipeline ML nghiên cứu bằng Python/PyTorch**: chuẩn bị dữ liệu, hai mô hình, chuẩn 3 tầng, ngưỡng thích ứng, đánh giá và ablation cho RQ1–RQ3 | Người dùng chốt 01/11/2026. **Phương án bị loại**: thêm demo FastAPI; làm full như bản cũ (ASP.NET + React) — không cần cho việc trả lời câu hỏi nghiên cứu | 2026-11-01 |
| DL-002 | Chọn tham số | **Chọn tham số bằng Optuna trên tập validation không dùng nhãn; nhãn chỉ dùng ở lần đánh giá cuối** | Người dùng chốt 01/11/2026. Dùng nhãn để chọn tham số làm kết quả đẹp giả, khó bảo vệ trong paper. **Phương án bị loại**: Optuna trên validation có nhãn; grid search nhỏ | 2026-11-01 |
| DL-003 | Tài liệu | **Google Doc này được cập nhật sau mỗi lần code xong, viết bằng ngôn ngữ BA** | Người dùng chốt 02/11/2026. Người đọc Doc không đọc code; chi tiết kỹ thuật nằm ở spec | 2026-11-02 |
| DL-004 | Tài liệu | **Doc được ghi bằng Apps Script gắn vào Doc; mỗi lần cập nhật ghi đè toàn bộ tab đầu tiên** | Người dùng chốt 02/11/2026. Ghi được mà không cần connector và không phụ thuộc tài khoản Drive đang kết nối. Hệ quả: comment trên Doc mất neo sau mỗi lần cập nhật, nên được đọc và báo lại trước khi ghi. **Phương án bị loại**: connector Google Docs (phải bật thêm); Docs API qua service account (phải tạo project Google Cloud) | 2026-11-02 |
| DL-005 | Nơi code | **Code project tại thư mục `D:\AI for BA\MW\Framework-rework`**, thay cho thư mục cũ `D:\Insider-Threat-Research` | Người dùng chốt 02/11/2026. Project mới dùng chung Google Doc này và cấu hình Apps Script với thư mục cũ | 2026-11-02 |
| DL-006 | Cấu trúc project | **Dựng sẵn khung thư mục chuẩn, chưa viết code**: mỗi bước 1–7 có thư mục riêng, cùng thư mục cấu hình, dữ liệu, kiểm thử, spec, tài liệu, kết quả chạy và bảng/hình cho paper. Tệp cấu hình chỉ có tên tham số, chưa có giá trị | Người dùng yêu cầu 02/11/2026. Giá trị tham số và thư viện cần cài do từng spec quyết định. **Phương án bị loại**: tạo sẵn các tệp code rỗng — tên tệp và cách gọi hàm phải chốt trong spec | 2026-11-02 |
| DL-007 | Dữ liệu | **Dùng bộ dữ liệu CERT bản r4.2** | Người dùng chốt 02/11/2026. Bản được dùng nhiều nhất trong các paper, nhiều insider, dễ so sánh kết quả. **Phương án bị loại**: r5.2; r6.2 — mỗi kịch bản chỉ có 1 insider, khó đo tỉ lệ phát hiện | 2026-11-02 |
| DL-008 | Môi trường | **Chạy trên venv Python 3.11, PyTorch bản CUDA, card RTX 3050 Laptop 4GB** | Người dùng chốt 02/11/2026. Máy hiện chỉ có Python 3.14 và 3.12, nên bước 1 có thêm việc cài Python 3.11; việc cài được hỏi người dùng trước. **Phương án bị loại**: Python 3.12 + CUDA; chạy bằng CPU — quá chậm để huấn luyện trên toàn bộ dữ liệu | 2026-11-02 |
| DL-009 | Dữ liệu | **Hoãn hai quyết định tới sau khi code bước 1**: tỉ lệ chia dữ liệu thành phần học / chọn tham số / đánh giá, và cách xử lý ngày có hành vi độc hại rơi vào phần học. Bước 1 cho phép chọn cả 3 phương án của mỗi quyết định trong tệp cấu hình; chốt trước lần huấn luyện đầu tiên | Người dùng chốt 02/11/2026: cần xem khoảng ngày và phân bố dữ liệu thật trước khi chọn. Để tránh rò rỉ dữ liệu, khi chốt chỉ dựa vào khoảng ngày, số user-day và vị trí các ngày độc hại, không dựa vào kết quả mô hình | 2026-11-02 |

## 6. Lịch sử cập nhật

| Bản | Ngày | Thay đổi |
|---|---|---|
| 0.1 | 2026-11-02 | Bản thử: tổng quan, thuật ngữ, 4 quyết định đầu tiên |
| 0.2 | 2026-11-02 | Thêm 5 quyết định DL-005 → DL-009: nơi code, khung thư mục, CERT r4.2, môi trường, hoãn cách chia dữ liệu; chưa code bước nào |
