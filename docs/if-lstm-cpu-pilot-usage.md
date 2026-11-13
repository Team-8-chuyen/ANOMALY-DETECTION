# Pilot Isolation Forest và LSTM Autoencoder trên CPU

SPEC-004 v1.0 triển khai hai model dùng chung cho mọi nhân viên: Isolation Forest chấm Feature, LSTM Autoencoder chấm Sequence24. Pilot ngày 12/11/2026 đã hoàn tất đúng một epoch LSTM trên cùng 20 nhân viên.

| Tập | Thời gian | Feature row / user-day | Sequence row nén |
|---|---|---:|---:|
| Fit | 02–22/01/2010 | 305 | 12.159 |
| Validation | 23–31/01/2010 | 103 | 4.052 |

Một user-day là một nhân viên trong một ngày. Các row sequence là những run thao tác đã nén của ngày đó. Hai nhánh phải có cùng khóa; hệ thống báo lỗi nếu thiếu hoặc trùng ngày.

## Hai model học hai loại thông tin

| Nhánh | Hệ thống xử lý | Model và điểm đầu ra |
|---|---|---|
| Feature | Hệ thống tính median trên ô active của fit, điền vào ô mask=false rồi nối 100 cờ mask. | IF có 100 cây, tối đa 256 mẫu/cây, 200 đầu vào; điểm `e_feature_raw=-score_samples`. |
| Sequence | Hệ thống học vocab/scaler từ fit, mã hóa 7 trường phân loại, 13 trường số và 4 trường boolean. | LSTM encoder/decoder một lớp, hidden 32, latent 16; điểm `e_sequence_raw` là lỗi tái tạo trung bình trên cell hợp lệ. |

LSTM dùng cả applicability mask và padding mask. Hệ thống giữ thứ tự thao tác, lấy hidden state của bước thật cuối và chia ngày dài thành window liên tiếp tối đa 128 bước. Mỗi ngày chỉ nhận một điểm từ tổng loss chia tổng số cell hợp lệ.

Warmup chạy ba bước optimizer trên model tạm. Hệ thống bỏ model tạm và khởi tạo lại seed/model/optimizer trước khi đo epoch thật. Batch size là 64, CPU dùng hai thread. Cả hai nhánh dùng dữ liệu đã ghép LDAP; chức vụ/phòng ban chỉ là metadata đối chiếu.

## Lệnh đã chạy và môi trường

```powershell
.\.venv-validation311\Scripts\python.exe scripts/run_if_lstm_pilot.py --config configs/experiments/if_lstm_cpu_pilot.json --run-dir runs/20261112-if-lstm-cpu-pilot-01
```

Lần chạy tiếp theo cần run ID mới, ví dụ suffix `-02`. CLI giữ nguyên run cũ và giữ staging chẩn đoán khi thất bại hoặc hết ngân sách trước khi hoàn tất.

Python 3.11.9, torch 2.9.1+cpu, scikit-learn 1.7.2, NumPy 1.26.4, SciPy 1.15.3 và PyArrow 19.0.1 đã cài trong venv. Toàn bộ pin nằm ở `requirements-models-cpu.txt`. Khi dựng môi trường khác:

```powershell
python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.9.1+cpu
python -m pip install -r requirements-models-cpu.txt
```

Các path nguồn, audit và LDAP nằm trong config. CLI đối soát hash dữ liệu nguồn/output, audit train sạch và domain ở snapshot LDAP 12/2009–01/2010 trước khi train.

## Số đo thật của pilot

Run: `runs/20261112-if-lstm-cpu-pilot-01`. Các giá trị từ `metrics.json`; thời gian được làm tròn trong bảng.

| Giai đoạn | Giây |
|---|---:|
| Import và khởi động | 4,164 |
| Kiểm provenance/checksum | 2,461 |
| Đọc dữ liệu | 11,372 |
| Fit preprocessor | 0,744 |
| Fit IF | 0,223 |
| IF chấm 103 user-day validation | 0,0069 |
| Warmup LSTM | 2,981 |
| Một epoch LSTM, 305 user-day | 1,081 |
| LSTM chấm 103 user-day validation | 0,222 |
| Ghi model/artifact | 1,301 |
| Tổng wall time đến lúc ghi bản tổng hợp | 24,647 |

LSTM có 23.443 tham số. Epoch thật có 5 batch, 12.159 bước thật, 20.695 bước tính cả padding và 167.944 cell active. Validation có 2 batch, 4.052 bước thật và 6.528 bước tính cả padding. Có hai file-extension token mới ở validation được ánh xạ sang UNK.

Train reconstruction loss là 1,20747; mean raw score validation theo user-day là 1,22598. Đây là lỗi tái tạo sau một epoch, không phải accuracy hoặc xác suất độc hại.

## Ngoại suy thời gian giữ riêng giả định và số đo

`runtime-estimate.json` dùng thời gian epoch hoàn chỉnh và số lượng train tham chiếu đã kiểm kê: 105.171 user-day, 3.998.777 bước nén.

| Kịch bản | Một epoch train đầy đủ | 20 epoch train, giả định |
|---|---:|---:|
| Nhân theo số bước sequence thật | 355,60 giây, khoảng 5,93 phút | 1,98 giờ |
| Nhân theo số user-day | 372,85 giây, khoảng 6,21 phút | 2,07 giờ |

Hai hàng là hai kịch bản ngoại suy, không phải khoảng tin cậy hoặc cận thời gian. Các dự toán chỉ tính training; setup, đọc dữ liệu, warmup và validation được đo riêng. Khác biệt padding, RAM, cache hoặc cách nạp dữ liệu đầy đủ có thể làm thời gian thực tế thay đổi lớn. Full IF fit/full scoring/full total vẫn là null vì pilot chưa đo chúng.

## Artifact bàn giao

| Tệp trong run | Nội dung |
|---|---|
| config.json, manifest.json | Cấu hình, cohort, khóa, checksum và bằng chứng nguồn |
| feature_preprocessor.json, sequence_preprocessor.json | Median, vocab/scaler và field order fit-only |
| if_model.joblib | Model IF và fingerprint của config/preprocessor |
| lstm_model.pt | Weights/optimizer epoch 1 và fingerprint; helper load kiểm khớp trước dùng |
| validation_scores.parquet | Đúng 103 ngày với hai raw score, metadata LDAP và các count/loss |
| metrics.json, runtime-estimate.json | Kết quả pilot, thời gian thật và kịch bản ngoại suy |
| env.txt, git.txt, log.txt | Phiên bản thư viện, Git và nhật ký |

Hai cột điểm thô càng lớn càng bất thường. Việc chuẩn hóa/hợp nhất hai nhánh, chuẩn theo tầng được chọn và threshold cuối trên Calibration cần một thiết kế nối tiếp. Pilot giữ nguyên bộ chọn Personal/Group/Global của SPEC-002 và hai case Department/Role.

Calibration routing trước đó đều chọn Personal; pilot này không kết luận case Group nào tốt hơn. Dữ liệu và model/run artifact được giữ local, không đưa vào Git.

Giới hạn nguồn được giữ rõ trong spec/manifest: domain upstream từng suy từ mọi tháng LDAP nhưng được đối chứng bằng snapshot trước fit; compressed payload có một số thuộc tính lấy từ event đầu. Pilot kiểm pipeline và runtime, chưa xác nhận lại toàn bộ preprocessing từ raw.

Kiểm thử bàn giao: **330 test qua trong43,91 giây**, gồm regression LDAP/router và kiểm leakage, padding, warmup reset, checkpoint-score parity. JUnit nằm ở runs/20261112-spec004-validation/pytest.xml; review khoa học độc lập không có Blocker/Major.
