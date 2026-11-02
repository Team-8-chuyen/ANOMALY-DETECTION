# Thiết kế mô hình — bản tham chiếu

Bản này dịch đề cương ([research-proposal.md](research-proposal.md)) thành các thành phần code được. Phần lớn là **mặc định đề xuất**, không phải quyết định đã chốt. Mọi mục ghi `D-xx` phải được người dùng chốt (hỏi kèm 3 phương án) trước khi spec đầu tiên chạm tới nó; chốt xong ghi Decision Log của tài liệu BA, từ đó mặc định ở đây coi như bị ghi đè bởi Decision Log.

## Mục lục

1. Đơn vị phân tích và pipeline tổng
2. C1 — Dữ liệu và nhãn
3. C2 — Luồng đặc trưng (feature stream)
4. C3 — Luồng chuỗi (sequence stream)
5. C4 — Hợp nhất điểm hai luồng
6. C5 — Chuẩn hành vi 3 tầng Personal – Group – Global
7. C6 — Ngưỡng thích ứng
8. C7 — Đánh giá, ablation theo RQ1–RQ3
9. Bài học từ bản cert-anomaly-framework-multiview (v1)
10. Bảng quyết định thiết kế D-01 → D-12

---

## 1. Đơn vị phân tích và pipeline tổng

Đơn vị mặc định: **user-day** (một người dùng trong một ngày lịch). Mọi điểm, ngưỡng, nhãn đều ở mức user-day; chỉ số mức user suy ra bằng gộp (một user bị phát hiện nếu có ít nhất một ngày bị cảnh báo trong giai đoạn đánh giá).

```
raw CERT csv ─► C1 chuẩn hoá sự kiện (parquet) ─► user-day
      ├─► C2 vector đặc trưng x_f ─► Feature AE ─► e_f (lỗi tái tạo)
      └─► C3 chuỗi token x_s     ─► Seq Transformer ─► e_s (NLL / lỗi tái tạo)
e_f, e_s ─► C4 chuẩn hoá + hợp nhất ─► s (điểm thô)
s ─► C5 chuẩn 3 tầng (P/G/O, trọng số thích ứng) ─► a (điểm bất thường cuối)
a ─► C6 ngưỡng thích ứng τ_u,t ─► cảnh báo
C7 đánh giá: chỉ số + ablation RQ1/RQ2/RQ3 + phân rã theo kịch bản
```

Hai luồng **tái tạo riêng biệt** (hai mô hình, hai loss) rồi mới hợp nhất ở mức điểm — đây là điểm khác cốt lõi so với ghép đặc trưng (đề cương, Gap 1). Không gộp hai luồng vào một autoencoder chung.

## 2. C1 — Dữ liệu và nhãn

Chi tiết tệp, cột, kịch bản và bẫy leakage: [cert-dataset.md](cert-dataset.md).

- Chuẩn hoá mọi nguồn log về một bảng sự kiện: `user, pc, ts, source, activity, attrs…`; lưu parquet theo tháng.
- Nhãn user-day = 1 nếu ngày đó có ít nhất một sự kiện nằm trong tệp đáp án của insider (`answers/`). Không suy nhãn theo khoảng ngày bắt đầu–kết thúc (D-03).
- Chia tập **theo thời gian**: train → val → test liên tiếp, không xáo trộn ngày. Tỉ lệ và cách xử lý ngày độc hại rơi vào train là D-02, D-03.

## 3. C2 — Luồng đặc trưng

Vector `x_f ∈ R^d` cho mỗi user-day, nhóm theo nguồn × khung giờ:

| Nhóm | Ví dụ đặc trưng (đếm hoặc tổng) |
|---|---|
| logon | số logon, logoff, logon ngoài giờ, logon cuối tuần, số PC khác nhau, logon vào PC không phải PC chính |
| device | số lần cắm USB, cắm USB ngoài giờ, thời lượng kết nối |
| file | số file truy cập, theo đuôi (.doc/.pdf/.zip/.exe…), ngoài giờ (r5+: sang removable) |
| email | số email gửi, email ra ngoài domain, tổng size, số đính kèm, số người nhận ngoài |
| http | số request, theo nhóm domain (job site, cloud storage, wikileaks-like, keylogger-like) |

- Khung giờ: giờ làm việc vs ngoài giờ là tham số config (`work_hours: [8, 18]`), không hard-code.
- Biến đổi: `log1p` rồi `RobustScaler` **fit trên train**. Không PCA mặc định (v1 dùng PCA-64 + pad 0 làm mất khả năng diễn giải đặc trưng).
- Mô hình: **Feature AE** dạng MLP, `e_f = ||x_f − x̂_f||²/d`.
  - Mặc định: encoder `[d → 128 → 64 → 16]`, decoder đối xứng, ReLU, dropout 0.1, AdamW lr 1e-3, wd 1e-5, batch 512, tối đa 200 epoch, early stop patience 10 trên loss val.
- Danh sách đặc trưng cuối cùng chốt ở spec C2, mỗi đặc trưng một dòng (tên, công thức, nguồn).

## 4. C3 — Luồng chuỗi

Mỗi user-day thành chuỗi token theo thời gian: `token = activity × khung_giờ` (ví dụ `logon_work`, `usb_connect_off`, `file_open_exe_off`, `http_job_work`, `email_send_ext_off`). Kích thước từ vựng khoảng 30–80, xây **chỉ trên train** + token `<unk>`, `<pad>`, `<mask>`, `<bos>`.

- Độ dài: cắt / lấy mẫu về `max_len` (mặc định 128; chọn theo phân vị 95 độ dài chuỗi trên train, ghi giá trị thực vào BA doc). Cách rút gọn chuỗi dài là D-05.
- Mô hình: **Transformer encoder** (attention đa đầu, mã hoá vị trí), huấn luyện tự giám sát. Mục tiêu học là D-04; mặc định đề xuất **masked token prediction** (mask 15%), điểm `e_s` = NLL trung bình trên token bị mask (khi chấm điểm: mask lần lượt hoặc K lần ngẫu nhiên cố định seed).
  - Mặc định: d_model 64, 4 head, 2 layer, ff 128, dropout 0.1, AdamW lr 5e-4, warmup 5% + cosine, batch 128, AMP fp16, early stop patience 5.
- Có thể thêm thông tin thời gian liên tục (phút trong ngày) làm embedding phụ — ghi trong spec nếu dùng.

## 5. C4 — Hợp nhất điểm hai luồng

`e_f`, `e_s` khác thang đo, phải chuẩn hoá trước khi cộng:

```
z_f = (e_f − median_train(e_f)) / (IQR_train(e_f) + ε)
z_s = (e_s − median_train(e_s)) / (IQR_train(e_s) + ε)
s   = α · z_f + (1 − α) · z_s
```

- Thống kê median/IQR lấy trên **train** (hoặc trên cửa sổ lịch sử nếu C5 làm việc đó — tránh chuẩn hoá hai lần trùng nhau, nêu rõ trong spec).
- Cách chọn α là D-06 (cố định 0.5 / chọn không nhãn / học được). Không chọn α bằng nhãn test.
- Phương án đối chứng cho RQ1 (bắt buộc có): F-only (α=1), S-only (α=0), early-fusion (ghép `x_f` vào chuỗi, một mô hình) — xem §8.

## 6. C5 — Chuẩn hành vi 3 tầng

Mỗi user `u` thuộc nhóm `g(u)` (D-07: nhóm theo `role`, `functional_unit` hay `department` trong LDAP). Tại ngày `t`, chỉ dùng lịch sử **trước t** (nhân quả, không nhìn tương lai), cửa sổ trượt `W` ngày.

Vị trí áp chuẩn là D-08; mặc định đề xuất **mức điểm**:

```
z_P = (s_u,t − med(S_P)) / (IQR(S_P) + ε)   S_P = điểm s của chính u trong [t−W, t)
z_G = (s_u,t − med(S_G)) / (IQR(S_G) + ε)   S_G = điểm s của các user cùng g(u) trong [t−W, t)
z_O = (s_u,t − med(S_O)) / (IQR(S_O) + ε)   S_O = điểm s của toàn tổ chức trong [t−W, t)
a_u,t = w_P z_P + w_G z_G + w_O z_O
```

Trọng số thích ứng theo lượng và độ tin cậy dữ liệu (dạng co rút / pseudo-count, D-09):

```
w_P = n_u / (n_u + k_P)                       n_u = số ngày có hoạt động của u trong cửa sổ
w_G = (1 − w_P) · m_g / (m_g + k_G)           m_g = số user đủ dữ liệu trong nhóm g(u)
w_O = 1 − w_P − w_G
```

- `k_P` (ngày), `k_G` (người) là tham số; nhóm có `m_g < min_group_size` thì `w_G = 0`, phần đó dồn về Global.
- Độ tin cậy có thể nhân thêm hệ số ổn định của lịch sử (ví dụ nghịch đảo hệ số biến thiên của `S_P`) — chỉ thêm nếu D-09 chọn.
- Đối chứng RQ2 (§8): Global-only, Personal-only, Global–Personal (chuyển cứng theo ngưỡng số ngày như Bamashmoos), Group–Personal, P–G–O trọng số cố định, P–G–O thích ứng (đề xuất).

## 7. C6 — Ngưỡng thích ứng

Dùng cùng trọng số với C5 để thống nhất cơ chế (đề cương, Gap 3):

```
τ_u,t = w_P · Q_p(A_P) + w_G · Q_p(A_G) + w_O · Q_p(A_O)
A_* = phân phối điểm a của tầng tương ứng trong cửa sổ [t−W_τ, t)
cảnh báo nếu a_u,t > τ_u,t
```

- Tính lại mỗi `R` ngày (mặc định 7) — mô phỏng cập nhật định kỳ để theo concept drift.
- Chọn `p` **không dùng nhãn**: theo ngân sách cảnh báo `B` (số cảnh báo / ngày / 1000 user, D-10) trên giai đoạn val.
- Đối chứng RQ3 (§8): ngưỡng cố định toàn cục (một giá trị, chọn trên val), ngưỡng phân vị toàn cục, ngưỡng cá nhân phân vị 95 cố định quy tắc (Bamashmoos) + user mới dùng toàn cục, ngưỡng thích ứng (đề xuất).

## 8. C7 — Đánh giá và ablation

Chỉ số (không dùng accuracy làm chỉ số chính):

| Mức | Chỉ số |
|---|---|
| user-day, không phụ thuộc ngưỡng | PR-AUC (AP) — chỉ số chính; ROC-AUC |
| user-day, tại ngưỡng | Precision, Recall, F1, FPR, số cảnh báo / ngày |
| theo ngân sách điều tra | Recall@k% user-day (k = 0.5, 1, 5) |
| user | tỉ lệ insider bị phát hiện, số user báo sai, độ trễ phát hiện (ngày từ ngày độc hại đầu tiên tới cảnh báo đầu tiên) |
| phân rã | recall theo **từng kịch bản** (đáp lại khoảng trống Tian et al. 2025), FPR theo nhóm vai trò (quản trị hệ thống), theo nhóm nhỏ (≤ 2 người), theo tứ phân vị độ dao động hành vi |

Thống kê: mỗi cấu hình chạy **5 seed**, báo mean ± std; so sánh với đề xuất bằng paired bootstrap CI (1000 lần) trên PR-AUC và Wilcoxon signed-rank theo seed. Bảng kết quả xuất cả CSV lẫn Markdown để dán vào paper.

Ma trận ablation:

| RQ | Biến thể (cố định các thành phần khác ở cấu hình đề xuất) | Chỉ số trọng tâm |
|---|---|---|
| RQ1 | F-only · S-only · early-fusion · late-fusion 2 luồng (đề xuất) | PR-AUC, Recall@k, recall theo kịch bản |
| RQ2 | Global · Personal · Global–Personal · Group–Personal · P–G–O cố định · P–G–O thích ứng (đề xuất) | PR-AUC, FPR tổng, FPR nhóm quản trị, FPR nhóm nhỏ |
| RQ3 | cố định toàn cục · phân vị toàn cục · cá nhân p95 cố định · thích ứng (đề xuất) | F1, FPR, FPR theo tứ phân vị dao động, độ trễ phát hiện |

Có thể thêm baseline ngoài (Isolation Forest, OC-SVM trên `x_f`; LSTM-AE trên chuỗi) nếu người dùng chọn — không bắt buộc.

## 9. Bài học từ bản v1 (cert-anomaly-framework-multiview, 07/2026)

Bản v1 nằm ở `C:\Users\ASUS\Downloads\cert-anomaly-framework-multiview.zip`. Những điểm spec mới phải xử lý rõ (không lặp lại):

| v1 làm | Vấn đề | Hướng xử lý |
|---|---|---|
| Hai view ghép vào **một** TCN-Transformer AE | Trái Gap 1 (cần tái tạo riêng) | Hai mô hình riêng, hợp nhất ở mức điểm (C4) |
| `score = 0.5·count + 0.5·seq`, chưa chuẩn hoá thang | Luồng có lỗi lớn hơn lấn át | Robust z từng luồng, α theo D-06 |
| Chỉ Global ↔ Personal, chuyển cứng ở mốc 50 log | Thiếu tầng Group; đúng hạn chế đề cương phê phán | C5 trọng số thích ứng P–G–O |
| Personal = train lại riêng mô hình cho từng user | Tốn, không mở rộng 1000+ user | Chuẩn tầng ở mức điểm, một bộ mô hình chung |
| Ngưỡng `quantile 0.995` cố định | Trái Gap 3 | C6 ngưỡng thích ứng |
| `epochs=3`, không tập val, không early stop | Chưa hội tụ, không tune được | Protocol ở [tuning-protocol.md](tuning-protocol.md) |
| Chấm điểm trên chính dữ liệu train | Lạc quan giả | Chia theo thời gian, chấm trên val/test |
| `max_rows_per_file=200_000` khi đọc CSV | Cắt mất phần lớn dữ liệu và insider | Đọc theo chunk, lưu parquet, không cắt |
| PCA-64 + pad 0 | Mất diễn giải đặc trưng, chiều giả | Bỏ PCA mặc định |

## 10. Bảng quyết định thiết kế cần chốt

Mỗi dòng hỏi người dùng **riêng một câu**, kèm 3 phương án (dòng "Đề xuất" là phương án nên ghi đầu và gắn nhãn khuyến nghị). Chỉ hỏi những D-xx mà spec hiện tại chạm tới; D-xx đã có trong Decision Log thì không hỏi lại.

| # | Câu hỏi | Phương án A (đề xuất) | Phương án B | Phương án C |
|---|---|---|---|---|
| D-01 | Phiên bản CERT | r4.2 (phổ biến nhất, nhiều insider, dễ so sánh paper) | r5.2 | r6.2 (ít insider, nhiều kịch bản hơn) |
| D-02 | Tỉ lệ chia thời gian train/val/test | ~60/15/25 theo tháng | 50/20/30 | Train cố định N tháng đầu, phần còn lại test theo tuần (online) |
| D-03 | Ngày độc hại rơi vào train | Loại khỏi train, ghi rõ là giả định "baseline sạch" | Giữ nguyên (thuần không giám sát, nhiễm bẩn) | Loại toàn bộ user insider khỏi train |
| D-04 | Mục tiêu học luồng chuỗi | Masked token prediction | Autoencoder tái tạo chuỗi | Dự đoán token kế tiếp |
| D-05 | Rút gọn chuỗi dài hơn max_len | Gộp token lặp liên tiếp thành token + đếm, rồi cắt | Cắt giữ phần cuối ngày | Chia nhiều cửa sổ, lấy điểm max |
| D-06 | Chọn α hợp nhất | Cố định 0.5 sau chuẩn hoá, kèm phân tích độ nhạy α ∈ {0,…,1} | Chọn α để cân phương sai hai luồng trên val (không nhãn) | Gating học được |
| D-07 | Định nghĩa nhóm (Group) | `role` trong LDAP | `functional_unit` | `department` |
| D-08 | Vị trí áp chuẩn 3 tầng | Mức điểm (C5 như trên) | Mức đặc trưng (độ lệch so với μ trộn 3 tầng làm đầu vào) | Ba mô hình theo tầng rồi trộn điểm |
| D-09 | Dạng trọng số thích ứng | Pseudo-count `n/(n+k)` | Pseudo-count × hệ số ổn định lịch sử | Trọng số học được trên val không nhãn |
| D-10 | Ngân sách cảnh báo chọn `p` | Theo ngân sách B cảnh báo/ngày/1000 user | Phân vị cố định đã tune trên val | Theo FPR mục tiêu trên val |
| D-11 | Cửa sổ lịch sử W, chu kỳ R | W = 60 ngày, R = 7 ngày, tune W ∈ {30, 60, 90} | W = 30, R = 1 | Mở rộng dần (toàn bộ lịch sử) |
| D-12 | Môi trường chạy | venv Python 3.11 + PyTorch bản CUDA cho RTX 3050 4GB | Python 3.12 + CUDA | Chạy CPU (chậm, chỉ hợp tập con) |
