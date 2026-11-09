"""Monthly LDAP joins and validation (SPEC-001 §4.1)."""
import csv
import math
from datetime import date
from pathlib import Path

FEATURES = ("logon_count", "logoff_count", "device_count", "file_count", "email_count", "http_count")


def read_csv_rows(path: Path, required: set[str]) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        header = reader.fieldnames
        if not header or len(header) != len(set(header)) or any(not col for col in header):
            raise ValueError(f"{path}: line 1: missing or duplicate header")
        missing = required.difference(header)
        if missing:
            raise ValueError(f"{path}: line 1: missing columns {sorted(missing)}")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path}: line {reader.line_num}: wrong number of columns")
            rows.append(row)
        if not rows:
            raise ValueError(f"{path}: no data rows")
    return header, rows


def load_monthly_roles(ldap_dir: Path) -> dict[tuple[str, str], str]:
    return load_monthly_groups(ldap_dir, "role")


def load_monthly_groups(ldap_dir: Path, group_key: str) -> dict[tuple[str, str], str]:
    """Load one alternative Group definition (SPEC-002 §6.1)."""
    if group_key not in {"role", "department"}:
        raise ValueError("group_key must be role or department")
    if not ldap_dir.is_dir():
        raise FileNotFoundError(f"{ldap_dir}: LDAP directory not found")
    files = sorted(ldap_dir.glob("*.csv"))
    if not files:
        raise ValueError(f"{ldap_dir}: no LDAP CSV files")
    roles = {}
    for path in files:
        month = path.stem
        try:
            if date.fromisoformat(month + "-01").strftime("%Y-%m") != month:
                raise ValueError
        except ValueError as error:
            raise ValueError(f"{path}: invalid YYYY-MM filename") from error
        _, rows = read_csv_rows(path, {"user_id", group_key})
        for line, row in enumerate(rows, start=2):
            user = row["user_id"].strip()
            if not user:
                raise ValueError(f"{path}: line {line}: empty user_id")
            key = (month, user)
            if key in roles:
                raise ValueError(f"{path}: line {line}: duplicate (month, user_id)")
            roles[key] = row[group_key].strip()
    return roles


def attach_roles(rows: list[dict[str, str]], monthly_roles: dict) -> list[dict]:
    if not rows:
        raise ValueError("no feature rows")
    joined, seen = [], set()
    required = {"user_id", "date", *FEATURES}
    for line, row in enumerate(rows, start=2):
        missing = required.difference(row)
        if missing:
            raise ValueError(f"line {line}: missing columns {sorted(missing)}")
        if "role" in row or "role_missing" in row:
            raise ValueError(f"line {line}: role metadata already present")
        if any(not isinstance(row[key], str) for key in required):
            raise ValueError(f"line {line}: required column must contain text")
        user = row["user_id"].strip()
        if not user:
            raise ValueError(f"line {line}: empty user_id")
        try:
            day = date.fromisoformat(row["date"])
            if day.isoformat() != row["date"]:
                raise ValueError
        except ValueError as error:
            raise ValueError(f"line {line}: invalid date, expected YYYY-MM-DD") from error
        key = (user, day)
        if key in seen:
            raise ValueError(f"line {line}: duplicate (user_id, date)")
        seen.add(key)
        for feature in FEATURES:
            try:
                value = float(row[feature])
            except ValueError as error:
                raise ValueError(f"line {line}: {feature} must be numeric") from error
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"line {line}: {feature} must be finite and non-negative")
        role = monthly_roles.get((day.isoformat()[:7], user), "").strip()
        role = role if role and role != "UNKNOWN" else "UNKNOWN"
        joined.append({**row, "role": role, "role_missing": int(role == "UNKNOWN")})
    return joined


def join_groups(rows: list[dict], metadata: dict) -> list[dict]:
    """Keep the same sample population for both Group definitions."""
    if set(metadata) != {"role", "department"}:
        raise ValueError("metadata must contain role and department mappings")
    joined = attach_roles(rows, metadata["role"])
    for row in joined:
        if "department" in row or "department_missing" in row:
            raise ValueError("department metadata already present")
        key = (row["date"][:7], row["user_id"].strip())
        group = metadata["department"].get(key, "").strip() or "UNKNOWN"
        row["department"] = group
        row["department_missing"] = int(group == "UNKNOWN")
    return joined
