"""Chronological split utilities for SPEC-002."""
from __future__ import annotations

from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class SplitBoundaries:
    train_end: pd.Timestamp
    validation_end: pd.Timestamp


def chronological_split(days: pd.Series, ratios=(0.60, 0.15, 0.25)) -> tuple[pd.Series, SplitBoundaries]:
    if len(ratios) != 3 or abs(sum(ratios) - 1.0) > 1e-9:
        raise ValueError("split ratios must contain three values summing to 1")
    normalized = pd.to_datetime(days).dt.normalize()
    unique = pd.Index(sorted(normalized.dropna().unique()))
    if len(unique) < 3:
        raise ValueError("at least three distinct days are required")
    train_pos = min(max(int(len(unique) * ratios[0]), 1), len(unique) - 2)
    val_pos = min(max(int(len(unique) * (ratios[0] + ratios[1])), train_pos + 1), len(unique) - 1)
    bounds = SplitBoundaries(pd.Timestamp(unique[train_pos]), pd.Timestamp(unique[val_pos]))
    labels = pd.Series("test", index=days.index, dtype="string")
    labels.loc[normalized < bounds.validation_end] = "validation"
    labels.loc[normalized < bounds.train_end] = "train"
    return labels, bounds


def assert_no_temporal_overlap(frame: pd.DataFrame) -> None:
    extrema = frame.groupby("split")["day"].agg(["min", "max"])
    if not (extrema.loc["train", "max"] < extrema.loc["validation", "min"] < extrema.loc["test", "min"]):
        raise ValueError("chronological split overlap detected")
