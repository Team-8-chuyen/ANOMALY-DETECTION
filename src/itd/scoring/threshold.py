"""Final Calibration threshold (SPEC-002 §4.5)."""
import numpy as np


def _scores(scores: np.ndarray) -> np.ndarray:
    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("scores must be a non-empty finite 1D vector")
    return values


def calibrate_threshold(scores: np.ndarray, p: float) -> float:
    if isinstance(p, bool) or not np.isfinite(p) or not 0 < p < 1:
        raise ValueError("p must be finite and between 0 and 1")
    return float(np.quantile(_scores(scores), p, method="linear"))


def apply_threshold(scores: np.ndarray, threshold: float) -> np.ndarray:
    if not np.isfinite(threshold):
        raise ValueError("threshold must be finite")
    return _scores(scores) > threshold
