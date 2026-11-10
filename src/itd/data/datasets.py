"""Train-only preprocessing helpers for SPEC-002."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class RobustStats:
    median: np.ndarray
    iqr: np.ndarray

    @classmethod
    def fit(cls, values: np.ndarray) -> "RobustStats":
        median = np.nanmedian(values, axis=0)
        q25, q75 = np.nanpercentile(values, [25, 75], axis=0)
        iqr = np.where((q75 - q25) > 0, q75 - q25, 1.0)
        return cls(np.nan_to_num(median), np.nan_to_num(iqr, nan=1.0))

    def transform(self, values: np.ndarray) -> np.ndarray:
        return np.nan_to_num((values - self.median) / self.iqr).astype(np.float32)


def choose_max_len(lengths: np.ndarray) -> int:
    if len(lengths) == 0:
        raise ValueError("cannot choose max_len from empty training data")
    p99 = float(np.quantile(lengths, 0.99))
    return next((candidate for candidate in (64, 128, 256) if candidate >= p99), 256)


def window_slices(length: int, max_len: int) -> list[slice]:
    if length <= 0 or max_len <= 0:
        return []
    return [slice(start, min(start + max_len, length)) for start in range(0, length, max_len)]
