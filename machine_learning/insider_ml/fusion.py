"""Versioned fusion of calibrated Feature and Sequence anomaly percentiles."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

FUSION_METHOD_WEIGHTED_MEAN_V1 = "weighted_mean.v1"
FUSION_METHOD_NOISY_OR_V1 = "noisy_or.v1"
SUPPORTED_FUSION_METHODS = frozenset(
    {FUSION_METHOD_WEIGHTED_MEAN_V1, FUSION_METHOD_NOISY_OR_V1}
)


@dataclass(frozen=True, slots=True)
class CalibratedFusion:
    risk: float | None
    feature_weight: float
    sequence_weight: float
    method: str


def _score(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric or None")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return result


def _weight(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return result


def _method(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("fusion method must be a string")
    if value not in SUPPORTED_FUSION_METHODS:
        supported = ", ".join(sorted(SUPPORTED_FUSION_METHODS))
        raise ValueError(
            f"unsupported fusion method {value!r}; expected one of {supported}"
        )
    return value


def fuse_calibrated_scores(
    *,
    q_feature: float | None,
    q_sequence: float | None,
    method: str = FUSION_METHOD_WEIGHTED_MEAN_V1,
    feature_weight: float = 0.5,
    sequence_weight: float = 0.5,
) -> CalibratedFusion:
    """Fuse independently calibrated anomaly percentiles.

    A missing branch contributes neither score nor weight. With one available
    branch the result is exactly that branch percentile. ``noisy_or.v1`` is
    deliberately limited to equal weights because a weighted nonlinear OR
    requires a separately reviewed statistical contract.
    """

    resolved_method = _method(method)
    q_f = _score(q_feature, "q_feature")
    q_s = _score(q_sequence, "q_sequence")
    w_f = _weight(feature_weight, "feature_weight")
    w_s = _weight(sequence_weight, "sequence_weight")

    if q_f is None and q_s is None:
        return CalibratedFusion(
            risk=None,
            feature_weight=0.0,
            sequence_weight=0.0,
            method=resolved_method,
        )

    available_f = w_f if q_f is not None else 0.0
    available_s = w_s if q_s is not None else 0.0
    total = available_f + available_s
    if total <= 0.0:
        raise ValueError("at least one available branch must have positive weight")

    normalized_f = available_f / total
    normalized_s = available_s / total

    if q_f is None:
        risk = q_s
    elif q_s is None:
        risk = q_f
    elif resolved_method == FUSION_METHOD_WEIGHTED_MEAN_V1:
        risk = q_f * normalized_f + q_s * normalized_s
    else:
        if not math.isclose(
            normalized_f,
            normalized_s,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "noisy_or.v1 requires equal feature and sequence weights"
            )
        risk = 1.0 - (1.0 - q_f) * (1.0 - q_s)

    return CalibratedFusion(
        risk=risk,
        feature_weight=normalized_f,
        sequence_weight=normalized_s,
        method=resolved_method,
    )
