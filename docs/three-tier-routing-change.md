# Thay đổi phương pháp ba tầng và tích hợp dữ liệu đã tiền xử lý

Ngày: 2026-11-10. Trạng thái: làm rõ yêu cầu, chưa duyệt implementation mới. Không tạo lại SPEC-003; giữ SPEC-001 và cập nhật SPEC-002 sau khi chốt hợp đồng dữ liệu/score.

**Cập nhật 2026-11-11:** SPEC-001 v1.1 đã triển khai ghép cả ba nhánh, output có hậu tố -ldap; PyArrow19.0.1 đã cài. Ghi chú chưa có dependency/chưa kiểm schema bên dưới là lịch sử kiểm tra ban đầu. Người dùng xác nhận tiếp tục cả hai case và so sánh hiệu quả; xem SPEC-002 v1.1 §14. Đầu vào score vẫn chưa chốt.

**Lựa chọn mới nhất — DL-055:** chưa có điểm mô hình; chỉ làm bộ chọn tầng và giao diện nhận điểm trước, không kết luận case tốt hơn. Đã cụ thể hóa tại SPEC-002 Draft v1.2 §14: routing-only mặc định, nhận điểm selected-tier tùy chọn, không tự chuẩn hóa hoặc Calibration. Công thức tạo score hoãn, không chặn router-only; chưa code trước duyệt spec mới.

**Đã hoàn thành sau accept — DL-056:** SPEC-002 v1.2 đã triển khai, 151 test qua; run train/Calibration tại runs/20261111-spec002-tier-routing. Tất cả 84.066 row mỗi case chọn Personal do có 19–30 ngày lịch sử; không có score/threshold mới hoặc kết luận tối ưu. Hướng dẫn hiện hành: docs/three-tier-usage.md. Các đoạn chưa code/chưa có schema bên dưới là lịch sử yêu cầu ban đầu.

## Yêu cầu đã xác nhận

Chỉ chọn một tầng theo thứ tự ưu tiên Personal → Group → Global:

```text
Personal đủ lịch sử quá khứ? → Có: chỉ score Personal, dừng lựa chọn tầng
                          → Không: Group đủ dữ liệu? → Có: chỉ score Group
                                                    → Không: chỉ score Global
```

Không dựa vào việc score cao/thấp để chuyển tầng; điều kiện chuyển tầng là tính khả dụng/đủ dữ liệu tham chiếu. Không tính hoặc trộn score của tầng không được chọn. Group vẫn có hai cấu hình thay thế: department hoặc role. Tạm giữ yêu cầu Personal 30 ngày và một threshold cuối mỗi case từ Calibration; cần xác nhận lại spec đầy đủ sau khi chốt đầu vào. Không dùng lại threshold của phương pháp trộn điểm cũ.

Tầng Personal đủ dữ liệu là lịch sử hợp lệ trong cửa sổ đã chọn, không tự suy từ số năm công tác. Ngưỡng đủ Personal/Group đang chờ người dùng chọn. Hai case phải giữ cùng feature, user-day, split và quy tắc Calibration. Output dự kiến ghi selected_tier, lý do fallback, cỡ mẫu tham chiếu và một score duy nhất.

## Dữ liệu tìm thấy trên máy

Gói ZIP: C:/Users/Admin/Downloads/CERT-r4.2-processed-two-branch-v1.zip, 176.078.052 byte. Chỉ đọc danh mục và tài liệu/text trong ZIP, chưa giải nén/ghi đè source.

| Thành phần | Nội dung theo README của gói, chưa kiểm trực tiếp Parquet |
|---|---|
| user_day_features | 64 Parquet; Behaviour100 + 100 mask; 330.452 user-day |
| user_day_features_ocean | Behaviour100 + OCEAN5, phục vụ ablation; chưa chọn làm input |
| user_day_sequences | 64 Parquet; 12.523.202 dòng sequence; 24 trường |
| Khóa nối theo README | user, day |
| Bucket | Phân vùng user; không phải split train/Calibration/test |

Các thư mục Parquet nằm trực tiếp ở root ZIP; README mô tả đường dẫn sau khi bố trí data/processed. Không tự giả định vị trí giải nén.

Gói còn chứa code và config trùng tên với workspace, trong đó src/itd/data/ldap.py có role_days_asof. Không chép đè module hiện tại. Không suy rằng hàm này đã thêm đầy đủ role/department vào output Parquet. Manifest gói ghi spec tên SPEC-001 nhưng đó là định danh của pipeline bên cung cấp, chưa chứng minh cùng tài liệu SPEC-001 của workspace này.

Môi trường .venv-validation311 hiện không có pyarrow/pandas/duckdb. Chưa cài dependency mới, chưa đọc được schema/null/mask/row-key thực tế. Cần kiểm môi trường đọc Parquet có sẵn hoặc chuẩn bị dependency thích hợp trước implementation.

## Kế hoạch ghép LDAP

Sau kiểm schema: lập bảng metadata duy nhất theo user và tháng từ day, ghép role/department đúng tháng; giữ metadata ngoài vector feature/token. Feature không nhân bản user-day; sequence giữ nguyên số dòng, thứ tự sự kiện, run_count và nội dung chuỗi. Không gộp sequence nhiều dòng thành một dòng chỉ để join. Kiểm trùng khóa LDAP trước join để tránh nhân dòng, missing dùng trạng thái rõ ràng, không âm thầm loại mẫu.

Ghi bộ enriched mới; không sửa gói gốc hoặc thay đổi 100 feature/mask/chuỗi. Tính duy nhất, row counts, khóa hai nhánh, loại ngày/timestamp, thứ tự và null phải được đối soát trước/sau. Chưa mặc định toàn bộ 100 cột là count không âm hoặc các giá trị mask là feature chấm score.

## Hai quyết định đang chờ

1. Điều kiện Personal/Group đủ dữ liệu: đề xuất 7 ngày/2 người; thay thế 2 ngày/2 người hoặc thông số do nhóm cung cấp.
2. Đầu vào chấm điểm: vector Behaviour100 thống kê, score user-day từ mô hình bên ngoài, hoặc hợp đồng khác của nhóm. Không tự coi token sequence là feature số để lấy mean/std và không tự train thêm hai mô hình.

Sau khi có câu trả lời và schema thực tế: hoàn thiện bản sửa SPEC-002, review thiết kế ba vòng rồi trình duyệt theo skill. Các artifact/threshold/kết quả của phương pháp trộn cũ giữ làm lịch sử, không báo là kết quả phương pháp chọn một tầng.

## Trạng thái workspace

Lúc kiểm tra workspace ở master commit 1748ea7, chưa có tiers.py của nhánh bàn giao. Đã khôi phục riêng SPEC-001/SPEC-002 bị thiếu từ commit 7331adf; không chuyển nhánh, không ghi đè code người dùng. SPEC-003 không hiện diện ở workspace này; nhánh GitHub từng đẩy vẫn chứa bản Withdrawn cho đến khi có commit xóa trên đúng nhánh. Chưa push thay đổi lần này.
