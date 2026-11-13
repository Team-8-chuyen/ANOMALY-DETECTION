---
id: SPEC-004
title: Isolation Forest + LSTM Autoencoder — pilot hai nhánh trên CPU
status: Implemented
version: 1.0
date: 2026-11-12
rq: [RQ1, RQ2]
components: [C2, C3]
decisions: [DL-033, DL-034, DL-046, DL-053, DL-054, DL-055, DL-063, DL-065, DL-066, DL-067, DL-068, DL-069]
supersedes: null
---

# SPEC-004 — Isolation Forest + LSTM Autoencoder trên CPU

## 1. Mục tiêu

Xây hai bộ sinh điểm độc lập: Isolation Forest cho 100 feature theo ngày và LSTM Autoencoder cho Sequence24. Thử trên cùng 20 nhân viên, đo thời gian fit/chấm điểm IF và **đúng một epoch LSTM** để cập nhật dự toán chạy đầy đủ. Đầu ra là hai điểm thô/user-day, chuẩn bị cho hai case Department/Role của SPEC-002 v1.2.

Truy vết: đề cương của skill, Gap 1/RQ1 về thông tin feature và chuỗi, Gap 2/RQ2 về ngữ cảnh nhóm. DL-067/068 thay hướng TCN đơn ở bản Draft 0.1. IF dùng isolation score, LSTM dùng reconstruction error; tài liệu Method phải mô tả đúng khác biệt này. Đây là pilot kỹ thuật, chưa trả lời RQ hoặc chứng minh case nào tốt hơn. SPEC-003 đã rút; ID004 tiếp tục với phiên bản0.2, đổi tên file theo phạm vi mới.

**Đã chốt qua câu trả lời:** IF + LSTM AE; tái tạo cả 24 thuộc tính sequence với typed loss/mask; CPU tối đa 20 nhân viên, fit 02–22/01/2010 và validation 23–31/01; đo một epoch trước. Feature dùng median fit để điền ô mask=false và nối 100 cờ mask, tổng 200 đầu vào (DL-069). Kiến trúc/tham số cụ thể và protocol đo dưới đây là **đề xuất của bản sửa này**, chỉ thành cấu hình được duyệt khi người dùng accept SPEC-004 v0.2.

## 2. Phạm vi

- Đọc Feature và Sequence đã ghép LDAP, bảo đảm cùng khóa/cohort/split và transform fit-only.
- Fit một IF chung; train một LSTM encoder/decoder chung qua bottleneck; xuất hai điểm thô trên validation.
- Đo runtime theo từng giai đoạn, lưu artifact và ngoại suy thời gian có công bố giả định.
- Test dữ liệu, leakage, mask/padding, overfit một batch synthetic và pilot thật sau duyệt.
- Hướng dẫn sử dụng, BA/Decision Log và bản Luồng hoạt động sau khi code được kiểm chứng.

Hai case Department/Role dùng chung hai bộ sinh điểm này. Hợp nhất hai nhánh, chuẩn hóa theo tầng được chọn và threshold cuối trên Calibration cần thiết kế nối tiếp; adapter hiện tại chỉ nhận selected-layer score. Pilot không sinh score hợp nhất, xác suất độc hại hoặc cảnh báo. Không có TCN/Transformer/Feature AE, Optuna, full training hoặc mở test trong đợt này, theo DL-055/067/068.

## 3. Dữ liệu vào / ra

Nguồn dưới `data/processed/CERT-r4.2-processed-two-branch-v1-ldap/`: Feature=`user_day_features/`, Sequence=`user_day_sequences/`. Không dùng Feature+OCEAN. Giữ nguyên nguồn; code trong package dataset chỉ đối chiếu schema, không import/chạy thay code project.

| Đối tượng | Schema / ý nghĩa |
|---|---|
| Khóa | `user:string`, `day:timestamp[ns]` chuẩn ngày, `event_index:int64` bắt đầu 0, liên tiếp trong user-day |
| Feature nguồn | Một row/user-day: `f001..f100:float64`, `m001..m100:bool`, cùng metadata LDAP |
| IF input | `float32[N,200]`:100 feature đã điền median, sau đó100 cờ mask; không thêm LDAP/ID/OCEAN |
| Thuộc tính | 24 trường theo đúng thứ tự bên dưới; 7 categorical, 13 numeric, 4 boolean |
| Mask nguồn | `attribute_mask:string`, JSON đúng 24 boolean; xác định thuộc tính áp dụng cho loại sự kiện |
| Metadata | `role`, `department`, `role_missing`, `department_missing`, `ldap_month`; giữ để đối chiếu, không đưa vào mô hình |
| Batch | `cat:int64[B,L,7]`, `numeric:float32[B,L,13]`, `boolean:float32[B,L,4]`, `attribute_mask:bool[B,L,24]`, `time_mask:bool[B,L]` |
| Đầu ra model | 7 tensor categorical logits `[B,L,K_j]`, numeric `[B,L,13]`, boolean logits `[B,L,4]` |
| Raw score | `validation_scores.parquet`: đúng một row/user-day, khóa/metadata LDAP, `e_feature_raw:float64`, `e_sequence_raw:float64`, `loss_sum:float64`, `n_valid_attributes:int64`, `n_sequence_rows:int64`, `n_windows:int64` |

Thứ tự 24 trường, bất biến giữa mask, tensor và checkpoint:

| Index | Trường | Kiểu học |
|---|---|---|
| 0 | event_token | categorical |
| 1–3 | time_sin, time_cos, gap_log1p | numeric |
| 4 | gap_bucket | categorical, dù kiểu Parquet là int64 |
| 5–6 | calendar_context, pc_context | categorical |
| 7–8 | run_count_log1p, run_span_log1p | numeric |
| 9 | file_extension_id | categorical string |
| 10 | filename_length_log1p | numeric |
| 11–12 | extension_present, multi_dot | boolean |
| 13 | url_scheme_id | categorical string |
| 14–16 | hostname_length_log1p, url_length_log1p, path_depth_log1p | numeric |
| 17 | query_present | boolean |
| 18–19 | recipient_count_log1p, external_recipient_ratio | numeric |
| 20 | bcc_present | boolean |
| 21–22 | attachment_count_log1p, email_size_log1p | numeric |
| 23 | sender_context | categorical |

Một row là **một run đã nén**, không phải một raw event. Không giải nén hoặc nhân trọng số bằng `run_count_log1p`. Mask chỉ là applicability: common index 0–8; file thêm 9–12; http thêm 13–17; email thêm 18–23. Giá trị 0, chuỗi rỗng hoặc `MISSING` trên một thuộc tính active vẫn là target hợp lệ; không suy mask từ giá trị.

## 4. Thiết kế

### 4.1 Cohort và thời gian

1. Chỉ đọc record có ngày thuộc tháng 01/2010 cho pilot; scanner filter trước khi lấy dữ liệu/tính transform. Không đọc cột nhãn validation, không đọc record Calibration/test. Footer/hash có thể bao phủ một file chứa tháng khác; không dùng nội dung các record ngoài khoảng ngày.
2. Dùng chính sách train sạch DL-034: loại **user-day độc hại**, không loại cả nhân viên. Audit `runs/20261107-cert-label-audit/summary.json` ghi 0 malicious user-day trong train 02/01–31/05/2010; `runs/20261107-label-pipeline-audit/raw-audit.json` đối chiếu answer event với raw không có missing/trùng/sai user-timestamp. Pilot chỉ lấy trường tổng hợp `splits.train`, không tải lại hoặc dùng nhãn validation/Calibration/test để chọn thiết kế. Lưu checksum hai audit, archive metadata `data/raw/cert-answers/download-manifest.json`, manifest gói nguồn và bằng chứng bảo toàn của SPEC-001 v1.1. Giả định được công bố: gói người dùng bàn giao là CERT r4.2 của cùng nguồn; chưa có liên kết hash ở cấp event từ answer archive sang row sequence nén. Nếu nguồn/manifest khác hoặc không có audit, dừng trước training để xác minh riêng train, không tự mặc định mọi row bình thường.
3. Pass đầu chỉ projection user/day để đối soát set khóa hai nhánh trong fit và chọn user; không materialize24 thuộc tính của mọi nhân viên. Khóa phải khớp trước chọn cohort, không inner join âm thầm mất ngày. Từ user có fit row hợp lệ ngày02–22/01, xếp theo `(SHA256(UTF8(str(seed)+"|"+user)), user)`, lấy tối đa20. Pass sau filter ngày+cohort mới lấy feature/Sequence24. Validation dùng đúng cohort đó và phải khớp khóa giữa nhánh. Không chọn theo loss, nhãn hoặc sự hiện diện tương lai; ngày không hoạt động không sinh row. Manifest ghi user không có validation nếu có.
4. Fit: `[2010-01-02,2010-01-23)`; validation: `[2010-01-23,2010-02-01)`. Không xáo trộn ngày giữa tập; shuffle minibatch chỉ trong fit. Các mốc nghiên cứu ngoài pilot giữ nguyên: train 01–05/2010, Calibration 06–09/2010, test 10/2010–05/2011.

Kiểm kê read-only ngày12/11/2026:20 user; fit **305 feature row và12.159 sequence row/305 user-day**; validation **103 user-day/4.052 sequence row**. Độ dài fit 7–73, validation 2–64. Cả24 thuộc tính có cell active trong fit, nhưng chỉ111 row file. Feature có76 trường luôn active,24 trường có ô không áp dụng, không trường nào hoàn toàn inactive. Evidence cohort/sequence: `runs/20261112-tcn-spec-evidence/pilot-inventory.json` (tên thư mục từ bản draft trước). Đây chưa phải training và không đại diện đủ mọi hành vi.

### 4.2 Đọc, kiểm và chuẩn hóa

- Feature: mỗi f_j được kiểm cùng mask m_j; active phải numeric hữu hạn (không bool), mask phải bool. Fit median_j chỉ trên active fit cells. Điền median_j vào inactive, sau đó nối100 mask dạng0/1 theo thứ tự100 feature rồi100 mask. Không log1p/scaler/PCA thêm cho IF. Payload inactive không được vào median hoặc model; active0 là giá trị thật. Nếu không có active fit cell cho một feature, báo lỗi dữ liệu thay vì tự bỏ cột/fit trên validation. Lưu median/count/column order trong `feature_preprocessor.json`.
- Dùng PyArrow projection, filter theo ngày/cohort; ghép user-day xuyên ranh giới file, sort theo `day,user,event_index`. Kiểm trùng/thiếu index, ngày không chuẩn, khóa trống, mask sai kiểu/chiều, metadata không nhất quán trong ngày. Dữ liệu sai phải báo lỗi có khóa/file, không âm thầm drop hoặc sửa thứ tự sự kiện.
- Fit vocab **riêng từng categorical** trên các cell active của fit. PAD=0, UNK=1, observed categories từ 2; string sort Unicode, gap_bucket sort số nguyên. PAD/UNK là ID riêng, không chiếm literal string. `""` active có ID quan sát bình thường. `K_j=2+số category quan sát fit` gồm cả PAD/UNK; embedding dùng padding_idx=0, vector PAD bằng zero. Target PAD chỉ nằm ngoài loss mask; UNK active vẫn tính CE. Validation giữ nguyên vocab, unseen→UNK, ghi số lượng unseen theo trường.
- Numeric dùng standardization riêng trường: `z=(x-mean_fit)/scale_fit`, population std (`ddof=0`) trên cell active fit; `scale=std` nếu `std>=1e-6`, ngược lại 1. Fit/tổng hợp bằng float64, tensor float32. Không log1p thêm, clipping hoặc fit lại trên validation. Mỗi trường phải có ít nhất một active fit cell; thiếu thì báo lỗi dữ liệu, không tự bỏ head.
- Boolean active phải là bool thật; numeric active phải hữu hạn, categorical active phải đúng kiểu; inactive cell được thay an toàn bằng PAD/0 **trước** mọi phép tính. Không dùng `NaN*0` để che lỗi. Giá trị hidden dưới mask không được ảnh hưởng prediction/loss hoặc vocab/scaler.
- `user`, LDAP, ngày như ID, label và OCEAN không là input học. Chỉ các time/context đã có trong 24 trường là input. Lưu `sequence_preprocessor.json` gồm field order/type, vocab, mean/scale/count, fit bounds và cohort hash; checkpoint phải khớp fingerprint này.

### 4.3 Đóng cửa sổ và padding

`window_length=128` row nén; chia user-day dài thành các đoạn liên tiếp **không overlap**, không nối qua ngày/người. Không cắt mất cuối ngày. Pilot đã kiểm kê không có ngày dài hơn 128; test giả vẫn phải bao phủ ngày dài. Mỗi window mang khóa, offset và original length.

Trong minibatch, pad phải đến độ dài lớn nhất batch, tối đa 128. `time_mask` đúng ở các row thật. Mask hiệu lực cho loss là `V[b,t,j]=time_mask[b,t] AND attribute_mask[b,t,j]`. Giữ riêng hai mask để phân biệt padding với thuộc tính không áp dụng. Inference có thể pad nhiều hơn để test tính bất biến.

### 4.4 Hai model đề xuất

**Isolation Forest:** `n_estimators=100`, `max_samples=min(256,n_fit)`, `max_features=1.0`, `bootstrap=false`, `contamination="auto"`, `random_state=seed`, `n_jobs=2`. Fit đúng feature matrix của305 train user-day; không refit validation, không dùng `predict` hoặc cutoff IF để tạo nhãn. Score theo batch bằng `e_feature_raw=-score_samples(X)`, càng lớn càng bất thường. Không coi contamination là tỷ lệ insider đã biết; không xuất cutoff nội bộ thành threshold nghiên cứu. Score mặc định serial để protocol đo rõ; lưu cấu hình thread thực tế. [API scikit-learn1.7](https://scikit-learn.org/1.7/modules/generated/sklearn.ensemble.IsolationForest.html).

**LSTM Autoencoder:** categorical embedding4 chiều mỗi trường, tổng28; nối13 numeric,4 boolean và24 bit applicability thành `D=69`. Zero mọi phần không active và padding. Không dùng feature vector/LDAP/ID làm input sequence.

| Bước | Phép toán | Shape |
|---|---|---|
| Encoder | LSTM input 69, hidden 32, một lớp, một chiều, state ban đầu zero, dropout 0 | Input `[B,L,69]`; h/c `[1,B,32]` |
| Last valid | Pack theo lengths thật, enforce_sorted=false; lấy `h_n[0]`, không lấy output tại indexL_pad−1 | `[B,32]` |
| Bottleneck | `z=tanh(Linear(32,16)(h_n[0]))` | `[B,16]` |
| Decoder input | Mỗi timestep nối z và vị trí local `t/(window_length−1)` với window_length128 cố định | `[B,L,17]` |
| Decoder state | `h0=tanh(Linear(16,32)(z))`, c0 tương tự với Linear riêng | Mỗi state `[1,B,32]` |
| Decoder | LSTM input 17, hidden 32, một lớp, một chiều, dropout 0 | `[B,L,32]` |
| Heads | Linear riêng từng categorical; numeric head 13; boolean logits head 4 | Các shape §3 |

Thông tin chuỗi từ encoder sang decoder chỉ đi qua z; không skip/teacher forcing hoặc truyền trực tiếp encoder c_n. Reset state mỗi window, tái tạo đúng thứ tự event_index tăng dần. Decoder không nhận target. Time mask phải là prefix true liên tục, lengths int64 CPU, `1≤length≤L≤128`; kiểm trước pack để tránh truncation. Decoder dense một chiều được phép: padding sau prefix không ảnh hưởng vị trí thật; zero input/output ở pad. Không normalization qua thời gian. Vị trí dùng mẫu số127 cố định, không phụ thuộc L_pad hoặc batch companion.

Đây là **offline reconstruction trong ngày**, không phải next-event prediction. Test thêm right padding/batch companion phải giữ logits/numeric ở vị trí thật. API [PyTorch2.9 LSTM](https://docs.pytorch.org/docs/2.9/generated/torch.nn.LSTM.html), [pack_padded_sequence](https://docs.pytorch.org/docs/2.9/generated/torch.nn.utils.rnn.pack_padded_sequence.html). Kiến trúc cụ thể là đề xuất cho pilot, không phải cấu hình được paper chứng minh tối ưu trên CERT.

### 4.5 Loss và raw score

Nhánh Feature dùng e_feature_raw của IF ở §4.4; không gán reconstruction loss cho IF. Các công thức dưới chỉ áp nhánh LSTM.

Với cell active: categorical dùng CrossEntropy trên logits và ID target; boolean dùng BCEWithLogits; numeric dùng squared error trên giá trị đã standardize. Tính loss unreduced, chỉ lấy cell V=true; không đưa padding hay inactive vào tử/mẫu số.

Đề xuất **mỗi cell thuộc tính active có trọng số 1**, không cân bằng theo tần suất lớp, không chuẩn CE bằng log(vocab), không thêm hệ số theo loại. Vì các loss khác thang, cấu hình này chỉ là điểm khởi đầu pilot, chưa khẳng định tối ưu; báo cáo loss riêng từng loại/trường để thấy thành phần chi phối.

```text
loss_batch = sum(loss_cell[V]) / count(V)
loss_sum(user,day) = sum(loss_cell[V]) qua tất cả window của ngày
n_valid_attributes(user,day) = tổng count(V) qua các window
e_sequence_raw(user,day) = loss_sum / n_valid_attributes
```

Không trung bình trực tiếp các window mean: window cuối ngắn không được có trọng số bằng window dài. Tổng hợp bằng float64; model float32. Ngày/window có 0 cell active là lỗi. Mỗi run nén có trọng số một lần theo các cell active; không nhân số raw event. Chấm điểm ở eval, no_grad; mỗi user-day có đúng một raw score hữu hạn, không âm.

### 4.6 Pilot, checkpoint và đo thời gian

Một IF và một LSTM cùng các preprocessor dùng chung cho hai case, không model riêng theo user/nhóm. Seed 0 cho Python/NumPy/Torch/DataLoader; LSTM CPU float32,2 thread, worker0, deterministic algorithms; init mặc định PyTorch sau set seed. Fit windows có thứ tự chuẩn trước shuffle, không drop_last; batch 64 nên305 window thành5 batch, batch cuối49. Pilot không có ngày dài hơn128. Ghi phiên bản/backend/thread; không hứa bitwise qua mọi máy.

AdamW lr1e-3, weight_decay1e-5, clip global norm1.0. **Một epoch fit**, sau đó eval/no_grad trên toàn bộ validation cohort. Không early stop/chọn best hoặc tự tăng epoch: checkpoint là model sau epoch 1 hoàn chỉnh. Báo train loss bằng tổng loss/tổng active cell, val mean raw score theo user-day và loss riêng từng trường/type. Val rỗng thì lỗi. Không dùng nhãn hoặc refit val.

Warmup 3 forward/loss/backward/optimizer step trên batch fit đầu với **model/optimizer tạm**; ghi warmup_seconds riêng. Bỏ model tạm, reset seed, khởi tạo lại model/optimizer và DataLoader generator trước epoch được đo; warmup không là checkpoint hay training thật được giữ lại. Không giữ đồng thời hai model để tốn RAM.

Đo bằng perf_counter: import_setup_seconds, provenance_seconds, data_read_seconds, preprocessing_seconds, if_fit_seconds, if_validation_score_seconds, warmup_seconds, lstm_train_epoch_seconds, lstm_validation_seconds, artifact_write_seconds và total_wall_seconds. Các phase chạy tuần tự, CLI bắt đầu clock trước heavy imports. Hash/provenance tách khỏi data read và train. Ghi train/val batch count, windows, valid steps, padded steps=sum(B×L_batch) và active cell counts. Cài dependency/code/test không nằm trong total_wall của CLI.

Ngân sách warmup+IF fit/score+LSTM train/val tối đa300s, kiểm tại biên batch/phase; một call fit IF hoặc I/O đang chạy có thể vượt giới hạn. Nếu không đủ một epoch/validation hoàn chỉnh, ghi incomplete, không giả metric đầy đủ hoặc ngoại suy từ partial run. NaN/Inf loss/gradient/score dừng failed. Lưu state_dict/optimizer/fingerprint vào lstm_model.pt; load nội bộ weights_only=true, kiểm fingerprint. IF lưu if_model.joblib, chỉ load artifact do chính run tạo; không hỗ trợ resume pilot.

### 4.7 Quan hệ với kiến trúc ba tầng

```text
Feature100+mask → một IF chung       → e_feature_raw
Sequence24     → một LSTM AE chung  → e_sequence_raw
                  ↓ thiết kế nối tiếp: cùng chiều/thang và hợp nhất
                  ↓ chuẩn hóa đúng tầng Personal / Group / Global được chọn
                  ↓ một threshold cuối từ Calibration
```

SPEC-002 v1.2 vẫn chọn đúng một tầng: Personal≥7 ngày hoạt động trong30 ngày trước, nếu thiếu thì Group≥2 người train, không đủ thì Global. Hai case chỉ khác Group=Department/Role. Hai raw score không có selected_tier/group_key và không gọi adapter. Chỉ thiết kế chuẩn hóa/hợp nhất/Calibration được duyệt sau mới tạo selected-layer score. Pilot20 user không thay membership hoặc điều kiện router nghiên cứu. Calibration hiện có84.066 user-day/case đều Personal; pilot không so sánh hiệu quả Department/Role.

## 5. Tham số

Tất cả khóa nằm trong `configs/experiments/if_lstm_cpu_pilot.json`, JSON theo CLI hiện tại. Chưa tune; cột giá trị phân biệt quyết định người dùng với cấu hình đề xuất cho lần duyệt này.

| Khóa | Giá trị | Truy vết / lý do |
|---|---|---|
| paths.feature_dir / sequence_dir | Hai nguồn §3 | DL-067 |
| paths.clean_train_audit_dir | runs/20261107-cert-label-audit | DL-034, audit bổ trợ §4.1 |
| paths.raw_label_audit / answers_manifest / source_prepare_manifest / enrichment_run_dir / ldap_dir | Các đường dẫn audit/nguồn/snapshot trong config thực tế | Khai báo I/O tường minh cho kiểm provenance §4.1/11; không đổi policy |
| split.fit_start / fit_end | 2010-01-02 / 2010-01-22, inclusive | DL-066 |
| split.validation_start / validation_end | 2010-01-23 / 2010-01-31, inclusive | DL-066 |
| data.max_users / seed | 20 / 0 | Cohort nhỏ, seed đề xuất |
| data.window_length / batch_rows | 128 / 65536 | Không cắt mất ngày; đọc batch |
| feature.impute / append_mask | median / true | DL-069, đúng200 cột |
| sequence.scaler / epsilon | standard / 1e-6 | Đề xuất fit-only, không log thêm |
| isolation_forest.n_estimators / max_samples | 100 / 256 (cap theo n_fit) | Đề xuất CPU nhỏ |
| isolation_forest.max_features / bootstrap | 1.0 / false | Cấu hình đề xuất |
| isolation_forest.contamination / n_jobs | auto / 2 | Chỉ lấy continuous score, không threshold |
| lstm.embedding_dim / hidden_size / latent_size | 4 / 32 / 16 | Đề xuất mô hình nhỏ |
| lstm.num_layers / bidirectional / dropout | 1 / false / 0 | Packing và decoder một chiều |
| lstm.decoder_position | local_fixed_window | §4.4, t/127 |
| loss.categorical / numeric / boolean | cross_entropy / mse / bce_logits | Typed objective DL-065, loss cụ thể đề xuất |
| loss.reduction | valid_cell_mean | §4.5, mỗi cell trọng số1 |
| train.device / dtype / threads / num_workers | cpu / float32 / 2 / 0 | Môi trường hiện tại |
| train.batch_size / epochs | 64 / 1 | Batch đề xuất; một epoch DL-068 |
| train.lr / weight_decay / grad_clip_norm | 0.001 / 0.00001 / 1.0 | Đề xuất AdamW |
| benchmark.warmup_steps / max_seconds | 3 / 300 | Warmup tạm, giới hạn pilot |
| benchmark.reference_train_days / reference_train_steps | 105171 / 3998777 | Chỉ metadata train-only audit cũ, không đọc full train trong pilot |
| benchmark.reference_epochs | 20 | Chỉ kịch bản dự toán, không chạy20 epoch |

Không có khoảng tune. Reject unknown keys, bool thay int, miền sai, split chồng lấn, schema sai hoặc cấu hình vượt phạm vi pilot. Paths tương đối resolve từ project root. `--run-dir` phải mới dưới runs. Không tự chuyển qua GPU/full data; giá trị làm thay đổi phương pháp phải sửa spec trước.

## 6. Thay đổi code sau duyệt

| Tệp | Tạo / sửa | API / trách nhiệm |
|---|---|---|
| src/itd/data/pilot_dataset.py | Tạo | `select_pilot_users(users,seed,max_users)->list[str]`, `load_pilot_data(config)->PilotData`; đọc hai nhánh, match keys |
| src/itd/data/feature_preprocessing.py | Tạo | `FeaturePreprocessor.fit(fit_rows)->Self`, `transform(rows)->ndarray[N,200]`, `to_dict()/from_dict()` |
| src/itd/data/sequence_dataset.py | Tạo | `SequenceSchema`, `window_day(day,max_len)->list[SequenceWindow]`, `collate_windows(windows,preprocessor)->SequenceBatch` |
| src/itd/data/sequence_preprocessing.py | Tạo | `SequencePreprocessor.fit(fit_days)->Self`, `transform(day)->EncodedDay`, `to_dict()/from_dict()` |
| src/itd/models/feature_isolation_forest.py | Tạo | `fit_feature_if(X,config,seed)->IsolationForest`, `score_feature_if(model,X)->ndarray[N]` |
| src/itd/models/lstm_autoencoder.py | Tạo | `LSTMAutoencoder(vocab_sizes,config)`, `forward(batch)->Reconstruction` |
| src/itd/training/sequence_trainer.py | Tạo | `reconstruction_loss(outputs,batch)->LossStats`; hai API trainer đầy đủ ngay sau bảng |
| src/itd/training/pilot_benchmark.py | Tạo | `run_pilot(data,config,run_dir)->PilotResult`, `estimate_runtime(measurements,reference)->dict` |
| src/itd/training/pilot_config.py, pilot_provenance.py | Tạo | Validation JSON/scope/path và đối soát checksum/audit/domain, tách khỏi benchmark |
| scripts/run_if_lstm_pilot.py | Tạo | CLI mỏng --config, --run-dir; provenance, staging và lỗi |
| configs/experiments/if_lstm_cpu_pilot.json | Tạo | Đủ khóa §5 |
| requirements-models-cpu.txt | Tạo | `-r requirements-ldap.txt`; torch2.9.1+cpu, scikit-learn1.7.2, scipy1.15.3, joblib1.5.2, threadpoolctl3.6.0 |
| tests/test_pilot_dataset.py, test_feature_preprocessing.py, test_sequence_dataset.py, test_sequence_preprocessing.py | Tạo | Cohort, keys, split, mask, transform fit-only |
| tests/test_feature_isolation_forest.py, test_lstm_autoencoder.py, test_sequence_trainer.py | Tạo | Score direction, model/mask/loss/overfit/save-load |
| tests/test_pilot_benchmark.py, test_if_lstm_pilot_cli.py | Tạo | Đồng hồ/extrapolation, fixture end-to-end/atomic output |
| docs/if-lstm-cpu-pilot-usage.md | Tạo | Lệnh, raw score schema, cách đọc dự toán |
| README.md, docs/BA-insider-threat-detection.md, docs/luong-hoat-dong.md | Sửa | Sau code READY: hướng dẫn/trạng thái/kết quả thật/DL |

Kiểu record là dataclass có type hints. PilotData tách fit/validation của cả hai nhánh, cohort/provenance, không có Calibration/test. SequenceDay chứa khóa/metadata và rows tăng theo event_index; SequenceWindow có khóa/offset/length và 24 trường/mask; SequenceBatch có tensors §3/window metadata; Reconstruction chứa ba loại output §3. LossStats có per-cell losses/mask và per-field sum/count; EpochResult có loss/counters của epoch hoàn chỉnh; RawSequenceScore như §3 trừ e_feature_raw. PilotResult có status/timing/artifact paths. NN model không biết file/LDAP. Package __init__ nếu cần là khai báo import tối thiểu, không kéo model dependencies vào CLI LDAP/router.

API trainer (config là dict đã validate theo §5, clock mặc định perf_counter, deadline là mốc tuyệt đối của clock hoặc None):

```text
train_one_epoch(model, windows:list[SequenceWindow], preprocessor:SequencePreprocessor,
                optimizer, config:dict, generator, deadline:float|None=None,
                clock=perf_counter) -> EpochResult
score_days(model, days:list[SequenceDay], preprocessor:SequencePreprocessor,
           config:dict, deadline:float|None=None, clock=perf_counter)
           -> list[RawSequenceScore]
```

Timeout không trả EpochResult/score list trông như hoàn chỉnh; benchmark bắt exception riêng và ghi incomplete. Validation raw scores sort theo day/user và ghép IF bằng exact keys, metadata phải khớp.

## 7. Thí nghiệm, runtime và artifact

Một pilot seed 0, một cohort, hai model và một epoch LSTM. Báo hai phân phối raw score riêng, typed loss/count, unseen counts, số tham số, batch/window/valid/padded steps và các thời gian §4.6. Không có AP/precision/recall/threshold hoặc kết luận case tốt hơn.

Ngoại suy **chỉ khi epoch hoàn chỉnh**: `T_train_full_steps=T_train_pilot×3998777/n_valid_steps_fit`; kịch bản theo ngày `T_train_full_days=T_train_pilot×105171/n_fit_days`. Với dữ liệu hiện tại, hệ số lần lượt328.873838 và344.822951. Đây là hai kịch bản, **không phải cận dưới/trên hoặc confidence interval**. Nhân20 chỉ cho kịch bản20 epoch, không chạy thật. Không nhân thời gian import/warmup/read/validation theo tỷ lệ train. Phân bố length/padding, batch cuối và overhead có thể làm sai số lớn; ghi rõ chưa xác minh trên full data. Full validation/score/total để null khi không có benchmark tương ứng. Không ngoại suy IF fit tuyến tính theo số row vì sampling mỗi cây cap 256; lưu timing pilot và `full_fit_estimate_seconds=null`.

Artifact run mới: config.json, manifest.json (nguồn/hash/cohort/keys/split/counts/domain/label-audit/provenance), feature_preprocessor.json, sequence_preprocessor.json, if_model.joblib, lstm_model.pt, metrics.json, runtime-estimate.json, validation_scores.parquet, env.txt, git.txt, log.txt. Đúng103 validation row với hai score hữu hạn; không score hợp nhất. Status complete/incomplete/failed; thời gian không dùng để đối chiếu deterministic. Run mới publish atomic khi complete; lỗi/incomplete giữ staging chẩn đoán có status, không ghi đè run cũ hoặc giả đủ đầu ra. Data/model/run không commit Git.

## 8. Tiêu chí chấp nhận

| ID | Tiêu chí kiểm được |
|---|---|
| AC-01 | Cả hai nhánh cùng keys/cohort/split; không rơi row do join; audit train sạch truy vết được |
| AC-02 | Feature median active fit-only,200 input đúng thứ tự; đổi inactive payload không đổi median/prediction; đổi mask có thể đổi prediction đúng contract |
| AC-03 | Đổi val/tương lai không đổi cohort, median/vocab/scaler/tensor fit; categorical unseen→UNK; đủ Sequence24 typed/masks |
| AC-04 | Right padding và batch companion không đổi valid logits/numeric/raw sequence score; pack dùng last valid state, không L_pad−1 |
| AC-05 | Forward/backward shape và gradient hữu hạn qua latent 16; không skip/teacher forcing; position t/127 và state reset đúng |
| AC-06 | Typed loss khớp ví dụ tay; user-day=sum loss/sum count qua window, không mean window means; IF score đúng âm score_samples, không gọi predict |
| AC-07 | LSTM overfit synthetic một batch giảm loss≥50% trong≤200 step với preset cố định; không dùng kết quả này chọn model nghiên cứu |
| AC-08 | Warmup được bỏ và reset RNG/model/optimizer trước epoch; checkpoint đúng epoch 1; deadline/nonfinite/save-load/fingerprint có test |
| AC-09 | Hai smoke fixture cùng môi trường/seed cho cùng cohort/transform/2score atol/rtol1e-6; timing tách riêng và không yêu cầu bằng nhau |
| AC-10 | Pilot thật đúng305 fit/103 validation user-day,12159/4052 sequence row;103 row hai score hữu hạn, LSTM score≥0; source đổi thì báo chênh lệch |
| AC-11 | Runtime từng phase đo thật, valid/padded counts đúng; ngoại suy đúng công thức, incomplete không ngoại suy, không gọi kịch bản là CI |
| AC-12 | Tất cả151 test LDAP/router hiện tại vẫn qua; raw scores không vào adapter; không đọc Calibration/test, không threshold/fusion |

## 9. Kế hoạch test

- Dataset≥3 user,≥2file, user-day vắt file, key thiếu giữa hai nhánh, trùng/index lỗi/mask sai/ngày sai, LDAP thiếu và user chỉ có val; AC-01/03/12. Sentinel ngoài split phải không materialize record; không gọi source code trong package dataset.
- Feature median ví dụ tay, active0, inactive NaN/garbage, feature không có fit active, bool giảnumeric/mask sai; transform roundtrip 200 cột. Đổi val không đổi fit; AC-02/03. IF wrapper so âm score_samples chính thư viện, spy chặn predict, save-load; không test giả định mọi outlier phải bị bắt.
- Sequence vocab/scaler chỉ active fit, numeric constant, empty category/UNK/inactive garbage. Model lengths1/3/7/128, unsorted lengths, prefix mask lỗi, pad phải trongcap128, batch companion; so cả logits/numeric, không chỉ loss; AC-03/04/05.
- CE/BCE/MSE ví dụ tay; ngày129 bước thành128+1; aggregation sum/count đúng. Position của valid prefix không đổi theo padding; state độc lập mỗiwindow; AC-05/06.
- Overfit synthetic2sequence length8 đủ field active, seed 0, AdamW lr0.01/wd0,≤200 step; giảm loss≥50%; fail phải tìm lỗi, không tự nới tiêu chí. Đây là unit test riêng, không thêm epoch vào pilot thật; AC-07.
- Fake clock/spy cho thời gian phase, warmup reset, timeout ở giữa epoch/val, nonfinite, serialize/fingerprint; hai fixture smoke seed 0; extrapolation dùng train time riêng, count đúng và incomplete trảnull; AC-08/09/11/12. Real pilot đối soát AC-10, ghi số thật.

## 10. Thực thi sau khi spec được duyệt

Python3.11.9, NumPy1.26.4/PyArrow19.0.1/pytest8.3.5 có trong `.venv-validation311`; chưa có torch/sklearn. Pin pilot: torch2.9.1+cpu, scikit-learn1.7.2, scipy1.15.3, joblib1.5.2, threadpoolctl3.6.0. CPU Torch CPython3.11 Windows x64 có trên [index chính thức](https://download.pytorch.org/whl/cpu/torch/); metadata [scikit-learn1.7.2](https://pypi.org/pypi/scikit-learn/1.7.2/json) hỗ trợ Python3.11/NumPy1.26.4. Chưa cài/chạy ABI; các pin là đề xuất pilot, không khẳng định mới nhất. Lưu pip freeze trong env.txt.

Sau accept: cài dependency trong venv hiện tại → code data/preprocessor/hai model/trainer/benchmark/CLI → test unit và overfit → smoke fixture hai lần → kiểm train-clean/domain provenance → pilot thật một epoch → review code/BA → Google Doc khi READY.

```powershell
.\.venv-validation311\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.9.1+cpu
.\.venv-validation311\Scripts\python.exe -m pip install -r requirements-models-cpu.txt
.\.venv-validation311\Scripts\python.exe -m pytest -q
.\.venv-validation311\Scripts\python.exe scripts/run_if_lstm_pilot.py --config configs/experiments/if_lstm_cpu_pilot.json --run-dir runs/20261112-if-lstm-cpu-pilot-01
```

Cài thư viện cần network approval của môi trường khi thực thi; chưa yêu cầu ở bước viết spec. Nếu run ID ví dụ đã tồn tại, dùng suffix mới, không force. Máy đo gần nhất i5-1135G7/8 logical processor,11.73 GiB RAM,1.42 GiB trống tại thời điểm đo; chỉ thấy Intel Iris Xe, chưa xác minh CUDA. Pilot CPU/float32 không sử dụng VRAM; đọc batch/cohort trước attributes để tiết kiệm RAM. Mục tiêu fixture smoke dưới5 phút, pilot300s các phase có model cộng I/O/setup. Chưa có thời gian đo thực tế, không cam kết tải/install hoặc tổng runtime; không train full ở bước này.

## 11. Rủi ro và provenance

| Rủi ro đã xác định | Kiểm soát / giới hạn |
|---|---|
| Upstream infer domain từ toàn bộ tháng LDAP | Package manifest ghi dtaa.com; read-only snapshot 12/2009 và 01/2010 đều có 1000 email, domain duy nhất dtaa.com, nên cùng giá trị suy được trước fit. Lưu đối chiếu/hash; nếu đối chiếu không khớp thì dừng pilot. Không khẳng định pipeline nguồn tự thân đã fit-only. Cần sửa provenance trước thí nghiệm nghiên cứu đầy đủ |
| Thuộc tính của run là dữ liệu tổng hợp | Source lấy phần lớn attrs từ event đầu, cộng recipient/email-size/attachment; external_recipient_ratio dùng external_count event đầu trên recipient_count cả run. Giữ nguyên payload người dùng cung cấp, ghi limitation này; pilot không xác nhận tính đúng ngữ nghĩa mọi raw-event feature |
| Mask applicability không phải raw missingness | Không tự coi inactive=0 là quan sát thật; active default0/MISSING vẫn dùng theo contract nguồn |
| Ít file event / UNK ở pilot | Báo count và loss riêng; không suy hiệu quả phát hiện hoặc case tối ưu từ 20 user/tháng |
| Feature mask thành tín hiệu thiếu dữ liệu | Median fit và100 mask đúng DL-069; công bố chính sách, không coi maskfalse là giá trị0 thật; không tự thêm LDAP vào model |
| LSTM chưa hội tụ sau một epoch | Latent 16, test overfit/padding; pilot chỉ kiểm pipeline/runtime, không đánh giá hiệu quả. Tuning/full training cần thiết kế sau |
| Torch/sklearn chưa cài, RAM trống thấp | Pin/kiểm import/ABI, projection/filter cohort rồi attributes, bỏ model warmup trước model thật. Incomplete nếu không xong ngân sách; không tự tăng tài nguyên |
| Pilot nhỏ ngoại suy thiếu tin cậy | Lưu thời gian phase/valid/padded/batch counts; công bố hai kịch bản, không CI/khẳng định tối đa. IF full và full total chưa có timing thìnull |
| Điểm thô bị hiểu thành điểm ba tầng hoàn chỉnh | File/schema riêng, không sinh score adapter/threshold; hướng dẫn nối tiếp §4.7 |

## 12. Open Questions

Loại model/pilot/split/Sequence24 và OQ-17 về feature mask đã chốt qua DL-065/066/067/068/069; không hỏi lại. Cấu hình đề xuất §4–5 chờ người dùng duyệt bản sửa. Fusion/chuẩn tầng/Calibration/đánh giá hai case sẽ thiết kế riêng khi nhóm yêu cầu, không chặn pilot hai raw score này.

## 13. Review readiness

Đã đọc lại từ đĩa theo từng vòng; vòng2 do reviewer độc lập chỉ nhận spec và tài liệu tham chiếu. Review bản0.1 không thay cho lần này. Bảng là số lỗi **còn mở** sau sửa, không phải kết quả kiểm thử code.

| Vòng | Lăng kính | Blocker | Major | Minor | Đã làm rõ / sửa cơ học | Điểm |
|---|---|---|---|---|---|---|
| 1 | Đầy đủ & truy vết | 0 | 0 | 0 | Schema hai nhánh/keys; tham số và model một epoch; timing/extrapolation | 10/10 |
| 2 | Khoa học — độc lập | 0 | 0 | 0 | R2-01: thống nhất tên sequence_preprocessor.json giữa §4.2 và artifact §7 | 10/10 |
| 3 | Sẵn sàng dev | 0 | 0 | 0 | API trainer/deadline đầy đủ, warmup reset, tách import/provenance, lệnh và version pin | 10/10 |

Đối chiếu cấu trúc:13mục,12AC liên tiếp; IF đúng policy median+mask và sign, LSTM đúng packing/bottleneck/typed loss; hai nhánh cùng cohort. Không có Open Question chặn pilot. Các câu hỏi fusion/chuẩn tầng/Calibration/đánh giá không là AC của pilot này.

**READY để trình duyệt SPEC-004 Draft v0.2.** Chưa cài thư viện, viết model hoặc training. Chỉ triển khai sau khi người dùng duyệt bản sửa này theo Bước4 của skill; kết quả review thiết kế không là kết quả model đã chạy.

Version history: Draft 0.1 ngày12/11/2026 mô tả TCN đơn, chưa được duyệt; Draft 0.2 cùng ngày thay thành IF+LSTM một epoch theo DL-067–069. Người dùng nói rõ “code đi, accept SPEC-004 v0.2” ngày 2026-11-12: nâng Accepted1.0 theo DL-070. Các ghi chú chờ duyệt bên trên là lịch sử review; đang triển khai, chưa ghi thành đã training.

## 14. Bàn giao code v1.0 — 2026-11-12

Trạng thái **Implemented**: đã triển khai các module/config/CLI/test theo §6, chạy pilot thật và cập nhật hướng dẫn. Các dòng Draft/chờ duyệt/đang triển khai ở §1–13 là lịch sử trước bàn giao. Helper config/provenance và các path evidence được tách để kiểm I/O rõ ràng, không thay thiết kế khoa học.

| Vòng code | Kết quả |
|---|---|
| 1 — Khớp spec | AC-01–12 có test/bằng chứng; đúng hai model, cohort/split, IF median+mask, LSTM latent/typed loss, một epoch và raw score riêng |
| 2 — Đúng đắn, độc lập | READY;0Blocker/0Major. Kiểm fit-only, last-valid/packing, reset warmup, mask/loss float64, sum/count, provenance và ngoại suy. Đã sửa mechanical rglob coverage, thứ tự padded count và reset runtime khi artifact lỗi |
| 3 — Chạy và bàn giao | Toàn suite **330 test qua trong43,91s**; hai fixture smoke tái lập, warmup-control và checkpoint-score parity qua; pilot thật complete, hướng dẫn docs/if-lstm-cpu-pilot-usage.md |

| AC | Bằng chứng |
|---|---|
| 01–03 | tests/test_pilot_dataset.py, test_feature_preprocessing.py, test_sequence_preprocessing.py |
| 04–07 | tests/test_sequence_dataset.py, test_lstm_autoencoder.py, test_sequence_trainer.py, test_feature_isolation_forest.py |
| 08–09 | tests/test_pilot_benchmark.py, test_if_lstm_pilot_cli.py: warmup reset, deadline, save/load score parity, hai smoke |
| 10–11 | runs/20261112-if-lstm-cpu-pilot-01/{metrics.json,runtime-estimate.json,validation_scores.parquet}; readback103 row, finite score |
| 12 | Full pytest JUnit runs/20261112-spec004-validation/pytest.xml;151 regression LDAP/router giữ nguyên |

Pilot:305 fit/103 validation ngày,12159/4052 sequence row,100 cây IF và LSTM23.443 tham số,5 train batch/2validation batch. IF fit0,22296s; LSTM epoch1,08128s; total24,64685s. Ngoại suy train-only hai kịch bản khoảng6phút/epoch,20epoch xấp xỉ2giờ; chưa đo fullrun. Không sinh fusion/threshold hoặc kết luận Department/Role tối ưu. Google Doc delivery được ghi riêng trong BA theo khả năng xác nhận online.
