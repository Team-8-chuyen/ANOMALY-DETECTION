# Kiểm kê CERT r4.2 — 2026-11-07

**Cập nhật nguồn nhãn:** sau kiểm kê ban đầu, đã tải gói đáp án chính thức từ CMU KiltHub về `data/raw/cert-answers/answers.tar.bz2` và giải nén an toàn. MD5 khớp metadata chính thức. Có `answers/insiders.csv` và ba thư mục `answers/r4.2-1`, `answers/r4.2-2`, `answers/r4.2-3`. Manifest tải: `data/raw/cert-answers/download-manifest.json`. Các ghi chú chưa tìm thấy nhãn bên dưới mô tả thời điểm trước lần tải này; chưa dùng nhãn mới để scoring/tune hoặc đánh giá test.

Nguồn: `D:\CERT_r4.2`. Bằng chứng chi tiết: `runs/20261107-cert-inventory/inventory.json`. Phạm vi chỉ kiểm kê, không fit baseline, tính score, hiệu chỉnh threshold hoặc đánh giá test.

## 1. Dữ liệu processed hiện có

| Tập | User-day | Người dùng | Khoảng ngày thực | Ngày có hoạt động |
|---|---:|---:|---|---:|
| Toàn bộ feature | 330.452 | 1.000 | 2010-01-02 → 2011-05-17 | 501 |
| Train | 105.171 | 1.000 | 2010-01-02 → 2010-05-31 | 150 |
| Calibration | 84.066 | 975 | 2010-06-01 → 2010-09-30 | 122 |
| Test | 141.215 | 934 | 2010-10-01 → 2011-05-17 | 229 |

Các mốc trên là hiện trạng script prototype, chưa phải quyết định chốt OQ-02. Train/Calibration/Test tương ứng 5/4/8 tháng lịch có dữ liệu. Số người dùng mỗi tập khác nhau phản ánh dữ liệu thực; kiểm kê chưa áp dụng lọc người dùng.

## 2. Kiểm tra tính nhất quán đã hoàn thành

- Bảng feature có sáu count đúng hợp đồng SPEC-001; không phát hiện dòng sai số cột, ngày sai, user rỗng, trùng user-day, count âm hoặc NaN/Inf.
- Ba split không giao nhau theo user-day; hợp ba split khớp toàn bộ user_day_features.csv. Không có dòng bị bỏ ngoài split trong dữ liệu processed hiện tại.
- Giá trị sáu feature trong mỗi split khớp dòng tương ứng của bảng tổng, số mismatch=0.
- Các file with_roles có cùng tập khóa với file features tương ứng; stored Role khớp LDAP cùng tháng, số mismatch=0.
- personal_baseline_train.csv có đủ 105.171 khóa train. Đợt kiểm kê này chưa tái tính hoặc xác minh các giá trị Personal trong file cũ; runner SPEC-002 tự xây lịch sử từ feature train.

## 3. LDAP và tỷ lệ thiếu metadata

| Tập | User-day thiếu Role | User-day thiếu Department |
|---|---:|---:|
| Train | 325 | 1.781 |
| Calibration | 461 | 1.665 |
| Test | 1.007 | 3.191 |
| Tổng | 1.793 | 6.637 |

- Có 18 file LDAP từ 2009-12 đến 2011-05, tổng 16.743 dòng; không phát hiện khóa user trùng trong cùng tháng.
- Tổng 252 dòng LDAP có department rỗng. Các số thiếu theo user-day gồm cả ô rỗng và không tìm thấy user-tháng.
- Train có 42 Role, trong đó 5 Role chỉ có 1 user; cỡ nhóm 1–180 người. Theo tham số đã duyệt, các nhóm một người phải backoff.
- Train có 22 Department; cỡ nhóm 4–188 người. Group size đếm user riêng biệt toàn train, không phải số người tại một thời điểm.
- Hai case giữ nguyên tập mẫu và dùng fallback khi metadata thiếu. Chưa có cơ sở kết luận case nào phát hiện tốt hơn.

## 4. File gốc và nguồn nhãn

| Nguồn | Tình trạng |
|---|---|
| logon, device, file, email, http | Có đủ năm CSV; đã đọc header, chưa đếm toàn bộ dòng gốc |
| http.csv | 14.536.257.467 byte; chưa quét lại toàn bộ nội dung |
| psychometric.csv | Có; không nằm trong sáu feature hiện tại |
| answers/insiders.csv và nhãn sự kiện | Chưa tìm thấy trong thư mục dataset, D:/answers và các vị trí kiểm tra |
| Cột label/malicious/scenario/insider trong processed | Chưa có |

Đã kiểm tra tên file phù hợp ở mức đầu của ổ D: và Downloads, chưa thấy gói đáp án; đây không phải tìm kiếm toàn bộ máy. Không kết luận người dùng chưa có nhãn ở nơi khác. Header/file hiện có chưa chứng minh processed đã bao phủ đầy đủ mọi sự kiện gốc; cần đối soát event counts ở bước chuẩn bị dữ liệu nếu muốn xác nhận toàn vẹn raw→feature.

## 5. Bước cần chốt trước chạy dữ liệu thật

1. Xác định nguồn đáp án để kiểm kê số insider, ngày độc hại và khả năng nhiễm train; không lựa chọn theo kết quả mô hình.
2. Chốt OQ-02: giữ split hiện tại hay chọn phương án khác.
3. Chốt OQ-03: loại ngày độc hại, giữ nguyên train hoặc loại insider user. Hai lựa chọn loại mẫu cần nguồn nhãn đã xác minh.
4. Điền config hai case cùng đường dẫn feature gốc và LDAP; runner tự ghép metadata. Chỉ fit train và Calibration trước, mở test đánh giá bằng quyết định riêng.

Đợt này không thay đổi dữ liệu nguồn, split hoặc config thực thi. Lần mở test đánh giá nghiên cứu vẫn là 0; chỉ đã đọc dữ liệu để đếm và kiểm tra tính nhất quán theo yêu cầu kiểm kê.
