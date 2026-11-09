"""Typed configuration loader for SPEC-001."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PathsConfig:
    raw: Path
    interim: Path
    processed: Path
    runs: Path
    reports: Path


@dataclass(frozen=True)
class DataConfig:
    cert_version: str
    chunk_rows: int
    datetime_format: str
    work_hours: tuple[str, str]
    user_buckets: int
    source_priority: tuple[str, ...]


@dataclass(frozen=True)
class FeatureConfig:
    count: int
    pc_history_days: int
    own_pc_min_days: int
    history_days: int
    psychometric_mode: str


@dataclass(frozen=True)
class SequenceConfig:
    run_gap_minutes: float
    gap_bucket_minutes: tuple[float, ...]
    max_len: int | None
    truncation: str


@dataclass(frozen=True)
class AppConfig:
    root: Path
    paths: PathsConfig
    data: DataConfig
    features: FeatureConfig
    sequence: SequenceConfig
    raw: dict[str, Any]


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        out[key] = _merge(out.get(key, {}), value) if isinstance(value, dict) else value
    return out


def load_config(path: str | Path, overrides: dict[str, Any] | None = None) -> AppConfig:
    config_path = Path(path).resolve()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if overrides:
        raw = _merge(raw, overrides)
    root = config_path.parent.parent
    p = raw["paths"]
    resolve = lambda value: (root / value).resolve() if not Path(value).is_absolute() else Path(value)
    paths = PathsConfig(**{key: resolve(p[key]) for key in ("raw", "interim", "processed", "runs", "reports")})
    d = raw["data"]
    data = DataConfig(
        cert_version=str(d["cert_version"]), chunk_rows=int(d["chunk_rows"]),
        datetime_format=str(d["datetime_format"]), work_hours=tuple(d["work_hours"]),
        user_buckets=int(d["user_buckets"]), source_priority=tuple(d["source_priority"]),
    )
    f = raw["features"]
    features = FeatureConfig(int(f["count"]), int(f["pc_history_days"]), int(f["own_pc_min_days"]), int(f["history_days"]), str(f["psychometric_mode"]))
    s = raw["sequence"]
    sequence = SequenceConfig(float(s["run_gap_minutes"]), tuple(map(float, s["gap_bucket_minutes"])), s.get("max_len"), str(s["truncation"]))
    if features.count != 100:
        raise ValueError("SPEC-001 requires features.count=100")
    if sequence.max_len is not None:
        raise ValueError("SPEC-001 forbids choosing max_len during preprocessing")
    return AppConfig(root, paths, data, features, sequence, raw)
