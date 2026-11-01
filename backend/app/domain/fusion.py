"""Calibration-score fusion for independently gated branches."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .readiness import _resolve_config

FUSION_METHOD_WEIGHTED_MEAN_V1 = "weighted_mean.v1"
FUSION_METHOD_NOISY_OR_V1 = "noisy_or.v1"
SUPPORTED_FUSION_METHODS = frozenset(
    {FUSION_METHOD_WEIGHTED_MEAN_V1, FUSION_METHOD_NOISY_OR_V1}
)


@dataclass(frozen=True)
class FusionResult:
    risk: float | None
    feature_weight: float
    sequence_weight: float
    available_branches: tuple[str, ...]
    reason_codes: tuple[str, ...]
    config_version: str
    method: str

    @property
    def can_alert(self) -> bool:
        return self.risk is not None

    @property
    def is_no_score(self) -> bool:
        return self.risk is None


def _validated_score(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number or None")
    score = float(value)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return score


def _validated_weight(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    weight = float(value)
    if not math.isfinite(weight) or weight < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return weight


def _validated_method(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("fusion method must be a string")
    if value not in SUPPORTED_FUSION_METHODS:
        supported = ", ".join(sorted(SUPPORTED_FUSION_METHODS))
        raise ValueError(
            f"unsupported fusion method {value!r}; expected one of {supported}"
        )
    return value


def fuse_scores(
    *,
    q_feature: float | None,
    q_sequence: float | None,
    config: Mapping[str, Any] | None = None,
    config_path: str | Path | None = None,
) -> FusionResult:
    """Fuse calibrated anomaly percentiles using a versioned method.

    ``None`` means that a branch returned ``NO_SCORE``.  When only one branch
    is present its normalized weight is 1.0, so its calibrated percentile is
    preserved exactly.  No alert can be produced when both branches are
    absent. ``noisy_or.v1`` intentionally requires equal configured weights:
    unequal nonlinear weighting needs a separate reviewed contract.
    """

    resolved = _resolve_config(config, config_path)
    method = _validated_method(
        resolved["fusion"].get("method", FUSION_METHOD_WEIGHTED_MEAN_V1)
    )
    q_f = _validated_score(q_feature, "q_feature")
    q_s = _validated_score(q_sequence, "q_sequence")
    feature_weight = _validated_weight(resolved["fusion"]["feature_weight"], "feature_weight")
    sequence_weight = _validated_weight(resolved["fusion"]["sequence_weight"], "sequence_weight")

    if q_f is None and q_s is None:
        return FusionResult(
            risk=None,
            feature_weight=0.0,
            sequence_weight=0.0,
            available_branches=(),
            reason_codes=("FUSION_NO_BRANCH_SCORE",),
            config_version=str(resolved["version"]),
            method=method,
        )

    present_feature_weight = feature_weight if q_f is not None else 0.0
    present_sequence_weight = sequence_weight if q_s is not None else 0.0
    total_weight = present_feature_weight + present_sequence_weight
    if total_weight <= 0.0:
        raise ValueError("At least one available branch must have positive weight")

    normalized_feature_weight = present_feature_weight / total_weight
    normalized_sequence_weight = present_sequence_weight / total_weight
    if q_f is None:
        risk = q_s
    elif q_s is None:
        risk = q_f
    elif method == FUSION_METHOD_WEIGHTED_MEAN_V1:
        risk = (
            q_f * normalized_feature_weight
            + q_s * normalized_sequence_weight
        )
    else:
        if not math.isclose(
            normalized_feature_weight,
            normalized_sequence_weight,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "noisy_or.v1 requires equal feature and sequence weights"
            )
        risk = 1.0 - (1.0 - q_f) * (1.0 - q_s)

    branches: list[str] = []
    reasons: list[str] = []
    if q_f is not None:
        branches.append("FEATURE")
    else:
        reasons.append("FEATURE_NO_SCORE")
    if q_s is not None:
        branches.append("SEQUENCE")
    else:
        reasons.append("SEQUENCE_NO_SCORE")

    return FusionResult(
        risk=risk,
        feature_weight=normalized_feature_weight,
        sequence_weight=normalized_sequence_weight,
        available_branches=tuple(branches),
        reason_codes=tuple(reasons),
        config_version=str(resolved["version"]),
        method=method,
    )
