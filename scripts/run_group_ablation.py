"""Run paired Department/Role ablation from a shared config (SPEC-002)."""
import argparse
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from itd.data.ldap import FEATURES, join_groups, load_monthly_groups, read_csv_rows
from itd.scoring.tiers import TierConfig, fit_baselines, init_history, score_days
from itd.scoring.threshold import apply_threshold, calibrate_threshold


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      default=_json_default, indent=2)


def _load(path: Path) -> dict:
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{path}: duplicate config key {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("non-finite config")))


def resolve_config(path: Path) -> dict:
    overlay = _load(path)
    if set(overlay) != {"extends", "group_key"}:
        raise ValueError("case config must contain only extends and group_key")
    if overlay["group_key"] not in {"department", "role"}:
        raise ValueError("invalid group_key")
    common_path = (path.parent / overlay["extends"]).resolve()
    config = _load(common_path)
    if "extends" in config or "group_key" in config:
        raise ValueError("common config cannot extend or define group_key")
    if config["features"] != list(FEATURES) or config["features_transform"] != "identity":
        raise ValueError("feature contract mismatch")
    if config["scoring"]["aggregation"] != "mean_positive_z":
        raise ValueError("unsupported score aggregation")
    if config["baseline"]["update"] != "frozen_train_global_group":
        raise ValueError("unsupported baseline update")
    if config["threshold"] != {"quantile": 0.99, "method": "linear", "comparison": "gt"}:
        raise ValueError("SPEC-002 requires p99 linear and strict > comparison")
    if config["dataset_kind"] not in {"synthetic", "cert"}:
        raise ValueError("invalid dataset_kind")
    if config["dataset_kind"] == "cert":
        policy = config["data_policy"]
        if policy["split_confirmed"] is not True or policy["malicious_in_train"] not in {
            "exclude_malicious_days", "keep_all", "exclude_insider_users"
        }:
            raise ValueError("CERT run requires decisions OQ-02/OQ-03 first")
    config["group_key"] = overlay["group_key"]
    for name in ("train", "calibration", "ldap_dir", "test"):
        value = config["paths"][name]
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"invalid path {name}")
            config["paths"][name] = str((common_path.parent / value).resolve())
        elif name != "test":
            raise ValueError(f"fill paths.{name} before running")
    tier_config(config)
    _json(config)
    return config


def tier_config(config: dict) -> TierConfig:
    return TierConfig(group_key=config["group_key"], window_days=config["personal"]["window_days"],
                      scale_floor=config["scoring"]["scale_floor"], **config["backoff"])


def _fingerprint(config: dict) -> str:
    shared = {key: value for key, value in config.items() if key != "group_key"}
    return hashlib.sha256(_json(shared).encode("utf-8")).hexdigest()


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value) -> None:
    path.write_text(_json(value) + "\n", encoding="utf-8")


def _write_scores(path: Path, rows: list[dict], threshold: float) -> int:
    alerts = apply_threshold(np.array([row["score"] for row in rows]), threshold)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*rows[0], "threshold", "is_alert"])
        writer.writeheader()
        for row, alert in zip(rows, alerts):
            writer.writerow({**row, "threshold": threshold, "is_alert": int(alert)})
    return int(alerts.sum())


def run_ablation(config_paths: list[Path], run_dir: Path, include_test: bool = False) -> dict:
    start = time.perf_counter()
    if len(config_paths) != 2:
        raise ValueError("exactly two --config arguments required")
    configs = [resolve_config(path) for path in config_paths]
    if {config["group_key"] for config in configs} != {"role", "department"}:
        raise ValueError("provide one Department and one Role config")
    if _fingerprint(configs[0]) != _fingerprint(configs[1]):
        raise ValueError("paired cases must have identical shared config")
    if run_dir.exists():
        raise FileExistsError(f"{run_dir}: run directory already exists")
    shared = configs[0]
    paths = shared["paths"]
    metadata = {key: load_monthly_groups(Path(paths["ldap_dir"]), key) for key in ("role", "department")}
    splits, manifest = {}, {"shared_config_fingerprint": _fingerprint(shared),
                            "features": list(FEATURES), "splits": {}, "ldap": {}}
    names = ["train", "calibration"] + (["test"] if include_test else [])
    previous_end = None
    for name in names:
        if not paths[name]:
            raise ValueError(f"paths.{name} is required")
        path = Path(paths[name])
        _, rows = read_csv_rows(path, {"user_id", "date", *FEATURES})
        try:
            joined = join_groups(rows, metadata)
        except ValueError as error:
            raise ValueError(f"{path}: {error}") from error
        joined.sort(key=lambda row: (row["date"], row["user_id"].strip()))
        first, last = joined[0]["date"], joined[-1]["date"]
        if previous_end is not None and first <= previous_end:
            raise ValueError("temporal splits overlap or are not strictly ordered")
        previous_end = last
        keys = [(row["user_id"].strip(), row["date"]) for row in joined]
        splits[name] = joined
        manifest["splits"][name] = {"sha256": _hash(path), "count": len(joined),
                                      "start": first, "end": last, "user_days": keys}
    if not include_test:
        manifest["splits"]["test"] = "deferred"
    manifest["ldap"] = {path.name: _hash(path) for path in sorted(Path(paths["ldap_dir"]).glob("*.csv"))}
    # Validate and fit both cases before creating any run artifacts.
    results = []
    for config in sorted(configs, key=lambda item: item["group_key"]):
        tiers = tier_config(config)
        baselines = fit_baselines(splits["train"], tiers)
        history = init_history(splits["train"], date.fromisoformat(splits["calibration"][0]["date"]), tiers)
        calibration, history_cal = score_days(splits["calibration"], baselines, history, tiers)
        threshold = calibrate_threshold(np.array([row["score"] for row in calibration]), 0.99)
        test, history_test = None, None
        if include_test:
            test, history_test = score_days(splits["test"], baselines, history_cal, tiers)
        results.append((config, baselines, calibration, history_cal, threshold, test, history_test))
    run_dir.mkdir(parents=True, exist_ok=False)
    _write_json(run_dir / "config.json", configs)
    _write_json(run_dir / "manifest.json", manifest)
    metrics = {"dataset_kind": shared["dataset_kind"], "include_test": include_test, "cases": {}}
    for config, baselines, calibration, history_cal, threshold, test, history_test in results:
        group = config["group_key"]
        case_dir = run_dir / group
        case_dir.mkdir()
        _write_json(case_dir / "baselines.json", baselines)
        _write_json(case_dir / "history_after_calibration.json", history_cal)
        _write_json(case_dir / "threshold.json", {"case": group, "quantile": 0.99, "method": "linear",
                     "threshold": threshold, "calibration_dates": [calibration[0]["date"], calibration[-1]["date"]],
                     "calibration_count": len(calibration)})
        cal_alerts = _write_scores(case_dir / "calibration_scores.csv", calibration, threshold)
        entry = {"calibration_count": len(calibration), "calibration_alerts": cal_alerts, "threshold": threshold}
        if include_test:
            entry["test_count"] = len(test)
            entry["test_alerts"] = _write_scores(case_dir / "test_scores.csv", test, threshold)
            _write_json(case_dir / "history_after_test.json", history_test)
        metrics["cases"][group] = entry
    metrics["elapsed_seconds"] = round(time.perf_counter() - start, 6)
    _write_json(run_dir / "metrics.json", metrics)
    (run_dir / "env.txt").write_text(f"Python {platform.python_version()}\nNumPy {np.__version__}\n", encoding="utf-8")
    git = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    (run_dir / "git.txt").write_text(head.stdout + git.stdout, encoding="utf-8")
    (run_dir / "log.txt").write_text("SPEC-002 paired run completed.\n" + _json(metrics) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", action="append", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--include-test", action="store_true", help="explicitly open test; CERT requires prior approval")
    args = parser.parse_args()
    try:
        print(_json(run_ablation(args.config, args.run_dir, args.include_test)))
    except (ValueError, TypeError, KeyError, OSError, csv.Error) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
