# Framework-rework — Insider Threat Detection

Project code mô hình phát hiện insider threat theo đề cương nghiên cứu (CERT, 2 luồng chuỗi + đặc trưng, chuẩn 3 tầng Personal–Group–Global, ngưỡng thích ứng, RQ1–RQ3). Thay thế nơi code cũ `D:\Insider-Threat-Research` (DL-005).

- Mọi việc code / sửa / train / tune / đánh giá trong project này đi qua skill `insider-threat-model-dev` (cài ở `~/.claude/skills/insider-threat-model-dev`): spec → người dùng duyệt → code → tài liệu BA + Decision Log.
- Tài liệu BA và Decision Log: `docs/BA-insider-threat-detection.md`. Spec: `specs/SPEC-NNN-<slug>.md`.
- Cấu trúc thư mục và chỗ đặt code: `README.md` § Cấu trúc. Chuẩn kỹ thuật: `references/engineering-standards.md` của skill.
- Google Doc "Luồng hoạt động" (cập nhật sau mỗi lần code xong, bản local `docs/luong-hoat-dong.md`): [Tài liệu Code](https://docs.google.com/document/d/1rLFe6HQzlHrnTipuaOe5IsP8uqrMn_xPeig_IXZM7gc/edit) — doc ID `1rLFe6HQzlHrnTipuaOe5IsP8uqrMn_xPeig_IXZM7gc`, chủ sở hữu `thainguyen.31231024537@st.ueh.edu.vn`, ghi đè tab đầu tiên bằng `push_gdoc.py` qua Apps Script web app (cấu hình ở `.env`, hướng dẫn `references/gdoc-setup.md` của skill). Lệnh đẩy chạy từ gốc project này: `python "$HOME/.claude/skills/insider-threat-model-dev/scripts/push_gdoc.py" docs/luong-hoat-dong.md`.
- Môi trường đã chốt: venv Python 3.11 + PyTorch CUDA (DL-008), nhưng chưa tạo; máy chưa có Python 3.11 — hỏi trước khi cài bất cứ thứ gì.
- Dữ liệu: CERT r4.2 (DL-007), đặt ở `data/raw/cert-r4.2/`.
- Trả lời người dùng bằng tiếng Việt có dấu.
