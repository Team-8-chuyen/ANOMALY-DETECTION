#!/usr/bin/env python3
"""Đẩy một tệp markdown lên Google Doc qua Apps Script web app (scripts/gdoc_webapp.gs).

Chỉ dùng thư viện chuẩn. Đọc GDOC_WEBAPP_URL, GDOC_SECRET, GDOC_DOC_ID từ biến môi trường
hoặc tệp .env (mặc định .env ở thư mục đang đứng).

    python push_gdoc.py docs/luong-hoat-dong.md            # ghi đè tab đầu tiên của Doc
    python push_gdoc.py docs/luong-hoat-dong.md --dry-run  # chỉ in các khối sẽ gửi
    python push_gdoc.py --ping                              # kiểm tra web app đã deploy
    python push_gdoc.py --make-gs apps-script/Code.gs       # sinh Code.gs đã điền DOC_ID, SECRET
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

GS_TEMPLATE = Path(__file__).with_name("gdoc_webapp.gs")

INLINE = re.compile(
    r"\*\*(?P<b>.+?)\*\*"
    r"|`(?P<c>[^`]+)`"
    r"|\[(?P<lt>[^\]]+)\]\((?P<lu>[^)\s]+)\)"
    r"|(?<![\*\w])\*(?P<i>[^*\s][^*]*?)\*(?![\*\w])"
)
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
ORDERED = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")
TABLE_SEP = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
HR = re.compile(r"^(\*{3,}|-{3,}|_{3,})\s*$")


def parse_inline(text: str) -> list[dict]:
    runs: list[dict] = []
    pos = 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            runs.append({"t": text[pos:m.start()]})
        if m.group("b") is not None:
            runs += [dict(r, b=True) for r in parse_inline(m.group("b"))]
        elif m.group("c") is not None:
            runs.append({"t": m.group("c"), "c": True})
        elif m.group("lt") is not None:
            runs.append({"t": m.group("lt"), "u": m.group("lu")})
        else:
            runs += [dict(r, i=True) for r in parse_inline(m.group("i"))]
        pos = m.end()
    if pos < len(text):
        runs.append({"t": text[pos:]})
    for r in runs:
        r["t"] = r["t"].replace("\\|", "|").replace("\\*", "*")
    return runs or [{"t": ""}]


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells, buf, in_code, prev = [], "", False, ""
    for ch in line:
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code and prev != "\\":
            cells.append(buf.strip())
            buf = ""
        else:
            buf += ch
        prev = ch
    cells.append(buf.strip())
    return cells


def parse_markdown(md: str) -> list[dict]:
    lines = md.replace("\r\n", "\n").split("\n")
    if lines and lines[0].strip() == "---":  # bỏ frontmatter
        end = next((k for k in range(1, len(lines)) if lines[k].strip() == "---"), 0)
        lines = lines[end + 1:]

    blocks: list[dict] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            blocks.append({"type": "p", "runs": parse_inline(" ".join(s.strip() for s in para))})
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            blocks.append({"type": "code", "text": "\n".join(code)})
            i += 1
            continue

        if not stripped:
            flush()
            i += 1
            continue

        if m := HEADING.match(stripped):
            flush()
            blocks.append({"type": "h", "level": len(m.group(1)), "runs": parse_inline(m.group(2))})
            i += 1
            continue

        if stripped.startswith("|"):
            flush()
            raw = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw.append(lines[i].strip())
                i += 1
            header = len(raw) > 1 and bool(TABLE_SEP.match(raw[1]))
            rows = [split_row(r) for k, r in enumerate(raw) if not (header and k == 1)]
            blocks.append({"type": "table", "header": header,
                           "rows": [[parse_inline(c) for c in row] for row in rows]})
            continue

        if HR.match(stripped) and not para:
            blocks.append({"type": "hr"})
            i += 1
            continue

        if BULLET.match(line) or ORDERED.match(line):
            flush()
            ordered = bool(ORDERED.match(line))
            pattern = ORDERED if ordered else BULLET
            items = []
            while i < len(lines) and (m := pattern.match(lines[i])):
                items.append({"level": len(m.group(1).replace("\t", "  ")) // 2,
                              "runs": parse_inline(m.group(2))})
                i += 1
            blocks.append({"type": "list", "ordered": ordered, "items": items})
            continue

        if stripped.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append({"type": "p", "quote": True, "runs": parse_inline(" ".join(quote))})
            continue

        para.append(line)
        i += 1

    flush()
    return blocks


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if raw and not raw.startswith("#") and "=" in raw:
                key, value = raw.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("GDOC_WEBAPP_URL", "GDOC_SECRET", "GDOC_DOC_ID"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def call(url: str, payload: dict | None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            text = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        raise SystemExit(f"Web app trả lỗi HTTP {err.code}. Kiểm tra URL deploy và quyền 'Anyone'.")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise SystemExit("Web app không trả JSON (thường do deploy chưa đặt 'Who has access: Anyone' "
                         "hoặc URL sai). 300 ký tự đầu:\n" + text[:300])


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("markdown", nargs="?", type=Path)
    ap.add_argument("--env", type=Path, default=Path(".env"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ping", action="store_true")
    ap.add_argument("--make-gs", type=Path, metavar="OUT")
    args = ap.parse_args()
    env = load_env(args.env)

    if args.make_gs:
        missing = [k for k in ("GDOC_DOC_ID", "GDOC_SECRET") if not env.get(k)]
        if missing:
            raise SystemExit(f"Thiếu {', '.join(missing)} trong {args.env}")
        code = GS_TEMPLATE.read_text(encoding="utf-8")
        code = code.replace("__DOC_ID__", env["GDOC_DOC_ID"]).replace("__SECRET__", env["GDOC_SECRET"])
        args.make_gs.parent.mkdir(parents=True, exist_ok=True)
        args.make_gs.write_text(code, encoding="utf-8", newline="\n")
        print(f"Đã ghi {args.make_gs}")
        return 0

    if args.ping:
        if not env.get("GDOC_WEBAPP_URL"):
            raise SystemExit(f"Thiếu GDOC_WEBAPP_URL trong {args.env}")
        print(json.dumps(call(env["GDOC_WEBAPP_URL"], None), ensure_ascii=False))
        return 0

    if not args.markdown:
        ap.error("cần đường dẫn tệp markdown")
    blocks = parse_markdown(args.markdown.read_text(encoding="utf-8"))
    if args.dry_run:
        counts: dict[str, int] = {}
        for b in blocks:
            counts[b["type"]] = counts.get(b["type"], 0) + 1
        print(json.dumps({"blocks": len(blocks), "by_type": counts}, ensure_ascii=False))
        print(json.dumps(blocks, ensure_ascii=False, indent=1))
        return 0

    missing = [k for k in ("GDOC_WEBAPP_URL", "GDOC_SECRET") if not env.get(k)]
    if missing:
        raise SystemExit(f"Thiếu {', '.join(missing)} trong {args.env}")
    result = call(env["GDOC_WEBAPP_URL"], {"secret": env["GDOC_SECRET"], "blocks": blocks})
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
