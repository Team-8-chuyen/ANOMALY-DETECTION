# Thiết lập đẩy Google Doc bằng Apps Script

Làm **một lần** cho mỗi Doc. Sau đó Bước 8 chỉ cần `push_gdoc.py`, không cần connector Google Docs.

## Cách hoạt động

```
docs/luong-hoat-dong.md ─► push_gdoc.py (đổi markdown thành khối: heading, đoạn, bảng, danh sách, in đậm, code, link)
                         ─► POST {secret, blocks} ─► Apps Script web app gắn vào Doc
                         ─► xoá nội dung tab đầu tiên, ghi lại toàn bộ theo khối
```

- Web app chạy bằng quyền của người deploy → Doc có thể để "Bị hạn chế".
- Mỗi lần đẩy **ghi đè toàn bộ tab đầu tiên**: comment đang neo vào chữ cũ sẽ mất neo. Vì vậy Bước 8 đọc và báo comment **trước** khi đẩy.

## Các tệp

| Tệp | Vai trò | Lên git |
|---|---|---|
| `scripts/gdoc_webapp.gs` (trong skill) | Mẫu Apps Script, còn `__DOC_ID__`, `__SECRET__` | Có |
| `scripts/push_gdoc.py` (trong skill) | Đổi markdown → khối, gửi lên web app; `--ping`, `--dry-run`, `--make-gs` | Có |
| `.env` (gốc project) | `GDOC_DOC_ID`, `GDOC_SECRET`, `GDOC_WEBAPP_URL` | **Không** |
| `apps-script/Code.gs` (gốc project) | Bản đã điền, để dán vào Apps Script | **Không** |

## Các bước (người dùng làm)

1. Mở Doc bằng tài khoản **sở hữu** Doc (hoặc một tài khoản có quyền chỉnh sửa).
2. Menu **Tiện ích mở rộng → Apps Script**.
3. Xoá hết code mặc định trong `Code.gs`, dán **toàn bộ** nội dung `apps-script/Code.gs` của project, bấm lưu (Ctrl+S).
4. **Triển khai (Deploy) → Tùy chọn triển khai mới (New deployment)** → biểu tượng bánh răng → **Ứng dụng web (Web app)**:
   - Thực thi dưới dạng (*Execute as*): **Tôi (Me)**
   - Người có quyền truy cập (*Who has access*): **Bất kỳ ai (Anyone)**
5. Bấm **Triển khai** → **Cấp quyền truy cập** → chọn tài khoản. Google báo *"Google chưa xác minh ứng dụng này"* → **Nâng cao** → **Đi tới … (không an toàn)** → **Cho phép**. Đây là script của chính bạn; quyền xin là xem / sửa Google Docs.
6. Sao chép **URL ứng dụng web** (kết thúc bằng `/exec`), gửi cho Claude hoặc dán vào `.env` dòng `GDOC_WEBAPP_URL=`.
7. Chuyển chia sẻ Doc về **Bị hạn chế**, chỉ giữ các thành viên nhóm. Lý do: ai có quyền sửa Doc cũng mở được Apps Script và đọc được mã bí mật.

Tài khoản trường chặn bước 5 → dùng tài khoản Gmail có quyền chỉnh sửa Doc làm lại bước 1–6.

## Kiểm tra và dùng (Claude làm)

```bash
python .claude/skills/insider-threat-model-dev/scripts/push_gdoc.py --ping                        # {"ok": true, "ping": true, "title": "..."}
python .claude/skills/insider-threat-model-dev/scripts/push_gdoc.py docs/luong-hoat-dong.md --dry-run
python .claude/skills/insider-threat-model-dev/scripts/push_gdoc.py docs/luong-hoat-dong.md      # {"ok": true, "blocks": N, ...}
```

## Khi sửa `gdoc_webapp.gs`

Sinh lại bản điền: `push_gdoc.py --make-gs apps-script/Code.gs`, người dùng dán lại, rồi **Deploy → Quản lý tùy chọn triển khai → sửa → Phiên bản: Phiên bản mới**. Làm vậy URL giữ nguyên; tạo deployment mới sẽ ra URL khác.

## Lỗi thường gặp

| Dấu hiệu | Nguyên nhân | Cách xử lý |
|---|---|---|
| "Web app không trả JSON", nội dung là trang đăng nhập Google | Deploy chưa đặt *Anyone* | Sửa deployment, đặt *Who has access: Anyone* |
| `{"ok": false, "error": "unauthorized"}` | `GDOC_SECRET` trong `.env` khác `SECRET` trong Apps Script | Sinh lại `Code.gs`, dán lại, deploy phiên bản mới |
| `Exception: ... openById` | Tài khoản deploy không có quyền sửa Doc | Deploy bằng tài khoản có quyền chỉnh sửa |
| Định dạng lạ ở một đoạn | Markdown ngoài tập hỗ trợ (bảng lồng, HTML thô) | Viết lại đoạn đó bằng heading / bảng / danh sách đơn giản |
