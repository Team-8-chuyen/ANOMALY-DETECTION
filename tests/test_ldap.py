import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
from itd.data.ldap import FEATURES, attach_roles, load_monthly_roles, read_csv_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "attach_roles.py"


def feature(user="U1", day="2010-01-02", **changes):
    return {"user_id": user, "date": day, **dict.fromkeys(FEATURES, "1"), **changes}


def write_csv(path, header, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def ldap(tmp_path):
    directory = tmp_path / "LDAP"
    directory.mkdir()
    write_csv(directory / "2010-01.csv", ["user_id", "role"],
              [{"user_id": " U1 ", "role": " A "}, {"user_id": "U2", "role": ""}])
    write_csv(directory / "2010-02.csv", ["user_id", "role"],
              [{"user_id": "U1", "role": "B"}, {"user_id": "U2", "role": "C"}])
    return directory


def test_exact_month_and_no_future_leakage(ldap):
    rows = [feature(" U1 "), feature(day="2010-02-03"), feature("U2"),
            feature("NEW"), feature(day="2009-12-31")]
    original = [dict(row) for row in rows]
    before = attach_roles(rows, load_monthly_roles(ldap))
    assert [r["role"] for r in before] == ["A", "B", "UNKNOWN", "UNKNOWN", "UNKNOWN"]
    assert [r["role_missing"] for r in before] == [0, 0, 1, 1, 1]
    assert before[0]["user_id"] == " U1 "
    assert rows == original
    write_csv(ldap / "2010-02.csv", ["user_id", "role"], [{"user_id": "U1", "role": "FUTURE"}])
    after = attach_roles(rows, load_monthly_roles(ldap))
    assert [after[i] for i in [0, 2, 3, 4]] == [before[i] for i in [0, 2, 3, 4]]


@pytest.mark.parametrize("changes", [{"user_id": " "}, {"date": "2010-02-30"},
    {"date": "20100102"}, {"logon_count": "nan"}, {"file_count": "inf"},
    {"email_count": "-1"}, {"http_count": "bad"}, {"role": "A"},
    {"role_missing": "0"}, {"user_id": None}])
def test_feature_validation(changes):
    with pytest.raises(ValueError):
        attach_roles([feature(**changes)], {})


def test_empty_missing_columns_and_duplicate_keys():
    for rows in [[], [{}], [feature(), feature(" U1 ")]]:
        with pytest.raises(ValueError):
            attach_roles(rows, {})


@pytest.mark.parametrize("content", ["", "user_id,role\n", "user_id,user_id,role\nU,U,A\n",
    "user_id,role\nU,A,extra\n", "user_id,role\nU\n", "user_id\nU\n",
    "user_id,role\n ,A\n", "user_id,role\nU,A\nU,A\n"])
def test_invalid_ldap(tmp_path, content):
    (tmp_path / "2010-01.csv").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_monthly_roles(tmp_path)


def test_missing_directory_empty_directory_invalid_month(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_monthly_roles(tmp_path / "missing")
    with pytest.raises(ValueError):
        load_monthly_roles(tmp_path)
    (tmp_path / "2010-13.csv").write_text("user_id,role\nU,A\n")
    with pytest.raises(ValueError, match="filename"):
        load_monthly_roles(tmp_path)


def test_import_has_no_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("import performed file I/O")
    monkeypatch.setattr(Path, "open", forbidden)
    spec = importlib.util.spec_from_file_location("attach_roles_cli", SCRIPT)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))


def run_cli(ldap, source, output, *flags):
    return subprocess.run([sys.executable, str(SCRIPT), "--ldap-dir", str(ldap),
                           "--input", str(source), "--output", str(output), *flags],
                          capture_output=True, text=True)


def test_cli_smoke_repeatability_and_output_protection(ldap, tmp_path):
    source = tmp_path / "features.csv"
    rows = [feature(), feature("NEW")]
    write_csv(source, list(rows[0]), rows)
    output = tmp_path / "roles.csv"
    result = run_cli(ldap, source, output)
    assert result.returncode == 0, result.stderr
    assert "Rows: 2; matched: 1; missing: 1" in result.stdout
    first = output.read_bytes()
    assert run_cli(ldap, source, output).returncode != 0
    assert output.read_bytes() == first
    assert run_cli(ldap, source, output, "--overwrite").returncode == 0
    assert output.read_bytes() == first
    header, joined = read_csv_rows(output, {"role", "role_missing"})
    assert header == [*rows[0], "role", "role_missing"]
    assert [row["role"] for row in joined] == ["A", "UNKNOWN"]
    original = source.read_bytes()
    assert run_cli(ldap, source, source, "--overwrite").returncode != 0
    assert source.read_bytes() == original


def test_invalid_input_preserves_output_and_leaves_no_temporary_files(ldap, tmp_path):
    source, output = tmp_path / "bad.csv", tmp_path / "old.csv"
    rows = [feature(), feature()]
    write_csv(source, list(rows[0]), rows)
    output.write_text("previous-output")
    result = run_cli(ldap, source, output, "--overwrite")
    assert result.returncode != 0
    assert "duplicate" in result.stderr and str(source) in result.stderr
    assert output.read_text() == "previous-output"
    assert not list(tmp_path.glob(".attach-roles-*"))


def test_missing_input(ldap, tmp_path):
    result = run_cli(ldap, tmp_path / "missing.csv", tmp_path / "out.csv")
    assert result.returncode != 0
    assert not (tmp_path / "out.csv").exists()
