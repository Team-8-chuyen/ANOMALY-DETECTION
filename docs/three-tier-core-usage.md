# Code ba tầng Personal → Group → Global

Phần core này nhận hai điểm thô có sẵn cho mỗi nhân viên–ngày, chuẩn hóa/hợp nhất điểm và chấm theo đúng một tầng. Hai case chỉ khác Group theo `department` hoặc `role` trong LDAP. Core dùng Python và NumPy; bên cung cấp điểm chịu trách nhiệm chạy model bên ngoài.

## Các tệp trong bộ bàn giao

| Tệp | Vai trò |
|---|---|
| src/itd/scoring/score_reference.py | Kiểm raw score, fit median/IQR và chuẩn Global/Group từ train |
| src/itd/scoring/profile_scoring.py | Chọn một tầng, chuẩn Personal quá khứ, state và monthly reset |
| configs/experiments/three_tier_core.json | Tham số chung cho hai case và hai chế độ |
| tests/test_score_reference.py, tests/test_profile_scoring.py | Công thức, nhân quả, backoff, reset, state và cặp case |

`routing.py` và `score_input.py` có sẵn trên nhánh, tiếp tục cung cấp bộ chọn tầng và adapter điểm.

## Quy tắc chấm điểm

1. Học median/IQR của hai điểm thô từ train, chuẩn hóa rồi hợp nhất 50/50.
2. Nếu có ít nhất 7 ngày hoạt động trong `[t−30,t)`, chọn Personal và dừng xét tầng.
3. Nếu thiếu Personal, dùng Group hiện tại khi có ít nhất 2 người riêng biệt trong train; còn lại dùng Global.
4. Chuẩn hóa điểm hợp nhất bằng median/IQR của **duy nhất tầng đã chọn**.
5. Chấm xong cả ngày và cả hai case rồi mới thêm điểm ngày đó vào history.

Điểm có thể âm; IQR nhỏ dùng mẫu số tối thiểu `1e-6`, giữ tầng đã chọn và gắn diagnostic. Membership và chuẩn Group/Global lấy từ cùng train, được giữ cố định. Không lấy trung bình ba điểm tầng và không đổi tầng khi thiếu điểm đầu vào hoặc reference sai.

## Dữ liệu vào

Train và evaluation là hai danh sách dict, mỗi danh sách có đúng một row/user-day. Mọi ngày train phải trước evaluation; hai điểm phải cùng chiều “càng cao càng bất thường”.

```json
{
  "user": "U_EXAMPLE",
  "day": "2020-02-01",
  "e_feature_raw": 0.4,
  "e_sequence_raw": 1.2,
  "department": "D_EXAMPLE",
  "role": "R_EXAMPLE",
  "department_missing": false,
  "role_missing": false,
  "ldap_month": "2020-02"
}
```

Ví dụ là dữ liệu giả. Trường nhóm thiếu dùng chuỗi `UNKNOWN` và cờ thiếu tương ứng `true`. Ngày dùng ISO `YYYY-MM-DD`; metadata không được rỗng, tháng phải khớp ngày. Core từ chối khóa trùng, bool thay score, null/NaN/Inf và metadata không nhất quán. Ngày không hoạt động không được thêm thành score 0.

## Gọi API từ thư mục gốc repo

Đầu vào `train_raw.json` và `evaluation_raw.json` là JSON arrays đúng schema trên, do bên cung cấp điểm chuẩn bị.

```python
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path("src").resolve()))
from itd.scoring.score_reference import fit_score_references, validate_raw_rows
from itd.scoring.profile_scoring import init_profile_state, score_profile_days

config = json.loads(Path("configs/experiments/three_tier_core.json").read_text(encoding="utf-8"))
train = validate_raw_rows(json.loads(Path("train_raw.json").read_text(encoding="utf-8")))
evaluation = validate_raw_rows(json.loads(Path("evaluation_raw.json").read_text(encoding="utf-8")))
references = fit_score_references(train, config)

for mode in config["modes"]:
    state = init_profile_state(train, evaluation[0]["day"], mode, references, config)
    diagnostics, state = score_profile_days(evaluation, references, state, config)
    Path(f"scores_{mode}.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    Path(f"state_{mode}.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
```

Lần chấm tiếp theo truyền state đã lưu của đúng mode/reference vào `score_profile_days`, thay vì gọi lại initializer. Ngày mới phải sau `last_processed_day`; đổi chunk cùng tháng không reset lại.

| Mode | Personal history |
|---|---|
| natural | Khởi tạo từ train trong cửa sổ 30 ngày rồi tiếp tục cập nhật |
| monthly_reset | Bắt đầu rỗng, xóa Personal tại ngày quan sát đầu tiên của mỗi tháng mới |

Reset chỉ tác động Personal; hai case cùng dùng một history trong mỗi mode. Đây là mô phỏng mất hồ sơ Personal, không phải người dùng hoàn toàn chưa từng xuất hiện trong train.

## Output và kiểm thử

Mỗi user-day có hai dòng diagnostics, với `group_key` là `department` hoặc `role`. Dòng ghi `selected_tier`, `fallback_reason`, số ngày Personal, số người Group, điểm nhánh/hợp nhất và `score` cuối. Khi cả hai case cùng Personal hoặc cùng Global, điểm phải bằng nhau chính xác. Số người Group để `null` khi Personal đủ nên không tra Group.

Muốn dùng adapter `attach_selected_scores`, project diagnostics về đúng năm cột `user,day,group_key,selected_tier,score` và giữ đủ hai case trong cùng mode.

```powershell
python -m pytest tests/test_score_reference.py tests/test_profile_scoring.py tests/test_routing.py tests/test_score_input.py -q
```

Core cần NumPy 1.26.4; kiểm thử cần pytest 8.3.5. Các dependency này đã có trong `requirements-ldap.txt`. Phần này tạo điểm theo tầng; threshold cuối và Precision/Recall/F1 cần protocol đánh giá riêng.
