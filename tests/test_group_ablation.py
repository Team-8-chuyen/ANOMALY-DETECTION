import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("group_runner", ROOT / "scripts/run_group_ablation.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def make_fixture(directory: Path, same_groups=False):
    directory.mkdir(parents=True, exist_ok=True)
    common = json.loads((ROOT / "configs/experiments/group_ablation_common.json").read_text())
    common.update(dataset_kind="synthetic")
    # Fixture approval state is independent of the local CERT run configuration.
    common["data_policy"] = {"split_confirmed": False, "malicious_in_train": None}
    common["paths"] = {"train": "train.csv", "calibration": "calibration.csv", "test": "test.csv", "ldap_dir": "LDAP"}
    (directory / "common.json").write_text(json.dumps(common))
    configs = []
    for key in ("department", "role"):
        config = directory / f"{key}.json"
        config.write_text(json.dumps({"extends": "common.json", "group_key": key}))
        configs.append(config)
    ldap = directory / "LDAP"
    ldap.mkdir(exist_ok=True)
    metadata = "user_id,role,department\nU1,A,D\nU2,A,D\nU3,B,D\n"
    if same_groups:
        metadata = "user_id,role,department\nU1,A,A\nU2,A,A\nU3,B,B\n"
    for month in ("2020-01", "2020-02"):
        (ldap / f"{month}.csv").write_text(metadata)
    header = ["user_id", "date", *RUNNER.FEATURES]
    data = {"train": [("2020-01-30", "U1", 1), ("2020-01-30", "U2", 3),
                       ("2020-01-31", "U1", 2), ("2020-01-31", "U2", 4), ("2020-01-31", "U3", 20)],
            "calibration": [("2020-02-01", "U1", 5), ("2020-02-01", "U3", 8),
                            ("2020-02-02", "U2", 6), ("2020-02-02", "NEW", 10)],
            "test": [("2020-02-03", "U1", 50), ("2020-02-03", "NEW", 2)]}
    for split, records in data.items():
        with (directory / f"{split}.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows([[user, day, *([value] * 6)] for day, user, value in records])
    return configs


def read_scores(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def test_paired_cli_repeatability_and_artifacts(tmp_path):
    configs = make_fixture(tmp_path / "data")
    command = [sys.executable, str(ROOT / "scripts/run_group_ablation.py"),
               "--config", str(configs[0]), "--config", str(configs[1]), "--include-test"]
    for index in (1, 2):
        result = subprocess.run(command + ["--run-dir", str(tmp_path / f"run{index}")], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    for key in ("department", "role"):
        a, b = tmp_path / "run1" / key, tmp_path / "run2" / key
        for name in ("calibration_scores.csv", "test_scores.csv", "threshold.json", "baselines.json"):
            assert (a / name).read_bytes() == (b / name).read_bytes()
        cal = read_scores(a / "calibration_scores.csv")
        test = read_scores(a / "test_scores.csv")
        assert len(cal) == 4 and len(test) == 2
        tau = json.loads((a / "threshold.json").read_text())["threshold"]
        assert tau == pytest.approx(np.quantile([float(row["score"]) for row in cal], 0.99))
        assert all(float(row["threshold"]) == tau for row in test)
        assert next(row for row in cal if row["user_id"] == "NEW")["w_global"] == "1.0"
    assert subprocess.run(command + ["--run-dir", str(tmp_path / "run1")], capture_output=True).returncode != 0
    dep = read_scores(tmp_path / "run1/department/calibration_scores.csv")
    role = read_scores(tmp_path / "run1/role/calibration_scores.csv")
    assert [(row["user_id"], row["date"]) for row in dep] == [(row["user_id"], row["date"]) for row in role]


def test_identical_group_partition_means_identical_scores(tmp_path):
    configs = make_fixture(tmp_path / "data", same_groups=True)
    RUNNER.run_ablation(configs, tmp_path / "run", True)
    dep = read_scores(tmp_path / "run/department/test_scores.csv")
    role = read_scores(tmp_path / "run/role/test_scores.csv")
    assert [row["score"] for row in dep] == [row["score"] for row in role]


def test_deferred_test_is_never_opened(tmp_path, monkeypatch):
    configs = make_fixture(tmp_path / "data")
    (tmp_path / "data/test.csv").unlink()
    original = Path.open
    def checked(path, *args, **kwargs):
        assert path.name != "test.csv", "deferred test was opened"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", checked)
    RUNNER.run_ablation(configs, tmp_path / "run")
    manifest = json.loads((tmp_path / "run/manifest.json").read_text())
    assert manifest["splits"]["test"] == "deferred"
    assert not (tmp_path / "run/role/test_scores.csv").exists()


def test_frozen_baselines_and_threshold_ignore_future_test_changes(tmp_path):
    configs = make_fixture(tmp_path / "data")
    RUNNER.run_ablation(configs, tmp_path / "run1", True)
    test_file = tmp_path / "data/test.csv"
    test_file.write_text(test_file.read_text().replace("50", "50000"))
    RUNNER.run_ablation(configs, tmp_path / "run2", True)
    for key in ("department", "role"):
        for name in ("baselines.json", "calibration_scores.csv", "threshold.json", "history_after_calibration.json"):
            assert (tmp_path / "run1" / key / name).read_bytes() == (tmp_path / "run2" / key / name).read_bytes()


@pytest.mark.parametrize("kind", ["shared_mismatch", "overlay_override", "duplicate_case", "overlap", "cert_unconfirmed", "nan"])
def test_runner_rejects_invalid_setup(tmp_path, kind):
    configs = make_fixture(tmp_path / "data")
    common_path = tmp_path / "data/common.json"
    common = json.loads(common_path.read_text())
    if kind == "shared_mismatch":
        other = dict(common, personal={"window_days": 10})
        (tmp_path / "data/other.json").write_text(json.dumps(other))
        configs[1].write_text(json.dumps({"extends": "other.json", "group_key": "role"}))
    elif kind == "overlay_override":
        configs[1].write_text(json.dumps({"extends": "common.json", "group_key": "role", "features": []}))
    elif kind == "duplicate_case":
        configs[1] = configs[0]
    elif kind == "overlap":
        path = tmp_path / "data/calibration.csv"
        path.write_text(path.read_text().replace("2020-02-01", "2020-01-31"))
    elif kind == "cert_unconfirmed":
        common["dataset_kind"] = "cert"
        common_path.write_text(json.dumps(common))
    else:
        common["backoff"]["k_P"] = float("nan")
        common_path.write_text(json.dumps(common))
    with pytest.raises((ValueError, FileExistsError)):
        RUNNER.run_ablation(configs, tmp_path / "run")
    assert not (tmp_path / "run").exists()
