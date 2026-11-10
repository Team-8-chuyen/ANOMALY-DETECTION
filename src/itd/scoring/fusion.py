"""Train-only robust normalization and late score fusion."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class ScoreStats:
    median: float
    iqr: float

    @classmethod
    def fit(cls, scores) -> "ScoreStats":
        values = np.asarray(scores, dtype=float)
        if values.size == 0:
            raise ValueError("cannot fit score statistics on empty train scores")
        q25, median, q75 = np.quantile(values, [0.25, 0.5, 0.75])
        return cls(float(median), float(q75 - q25) if q75 > q25 else 1.0)

    def transform(self, scores):
        return (np.asarray(scores, dtype=float) - self.median) / self.iqr


def fuse_scores(z_behaviour, z_sequence, alpha: float = 0.5):
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be in [0, 1]")
    return alpha * np.asarray(z_behaviour) + (1.0 - alpha) * np.asarray(z_sequence)
