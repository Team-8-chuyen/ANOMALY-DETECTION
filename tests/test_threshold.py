import numpy as np
import pytest
from itd.scoring.threshold import apply_threshold, calibrate_threshold


def test_p99_and_strict_comparison():
    values = np.array([0., 1., 2., 3.])
    tau = calibrate_threshold(values, 0.99)
    assert tau == pytest.approx(2.97)
    np.testing.assert_array_equal(apply_threshold(np.array([tau, tau + 1]), tau), [False, True])
    assert not apply_threshold(np.zeros(5), calibrate_threshold(np.zeros(5), 0.99)).any()


@pytest.mark.parametrize("values", [[], [[1]], [np.nan], [np.inf]])
def test_invalid_values(values):
    with pytest.raises(ValueError):
        calibrate_threshold(values, 0.99)


@pytest.mark.parametrize("p", [0, 1, -1, np.nan, np.inf, True])
def test_invalid_probability(p):
    with pytest.raises(ValueError):
        calibrate_threshold([1, 2], p)


def test_invalid_threshold():
    with pytest.raises(ValueError):
        apply_threshold([1, 2], np.nan)
