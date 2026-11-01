from __future__ import annotations

import pytest

from insider_ml.fusion import fuse_calibrated_scores


def test_weighted_mean_v1_remains_backward_compatible() -> None:
    result = fuse_calibrated_scores(
        q_feature=0.97,
        q_sequence=0.93,
    )

    assert result.method == "weighted_mean.v1"
    assert result.risk == pytest.approx(0.95)
    assert result.feature_weight == pytest.approx(0.5)
    assert result.sequence_weight == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("q_feature", "q_sequence", "expected"),
    [
        (0.99, 0.50, 0.995),
        (0.80, 0.20, 0.84),
        (0.00, 0.00, 0.00),
        (1.00, 0.25, 1.00),
    ],
)
def test_noisy_or_v1_preserves_extreme_branch_signal(
    q_feature: float,
    q_sequence: float,
    expected: float,
) -> None:
    result = fuse_calibrated_scores(
        q_feature=q_feature,
        q_sequence=q_sequence,
        method="noisy_or.v1",
    )

    assert result.risk == pytest.approx(expected)


@pytest.mark.parametrize(
    ("q_feature", "q_sequence", "expected", "weights"),
    [
        (0.87, None, 0.87, (1.0, 0.0)),
        (None, 0.76, 0.76, (0.0, 1.0)),
    ],
)
def test_single_branch_is_identity(
    q_feature: float | None,
    q_sequence: float | None,
    expected: float,
    weights: tuple[float, float],
) -> None:
    result = fuse_calibrated_scores(
        q_feature=q_feature,
        q_sequence=q_sequence,
        method="noisy_or.v1",
    )

    assert result.risk == pytest.approx(expected)
    assert (result.feature_weight, result.sequence_weight) == weights


def test_both_missing_produces_no_score() -> None:
    result = fuse_calibrated_scores(
        q_feature=None,
        q_sequence=None,
        method="noisy_or.v1",
    )

    assert result.risk is None
    assert result.feature_weight == 0.0
    assert result.sequence_weight == 0.0


def test_noisy_or_rejects_unequal_weights() -> None:
    with pytest.raises(ValueError, match="requires equal"):
        fuse_calibrated_scores(
            q_feature=0.8,
            q_sequence=0.2,
            method="noisy_or.v1",
            feature_weight=0.75,
            sequence_weight=0.25,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("feature", -0.01),
        ("feature", 1.01),
        ("feature", float("nan")),
        ("sequence", float("inf")),
    ],
)
def test_invalid_calibrated_score_is_rejected(
    field: str,
    value: float,
) -> None:
    values = {"q_feature": 0.5, "q_sequence": 0.5}
    values[f"q_{field}"] = value

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        fuse_calibrated_scores(**values)
