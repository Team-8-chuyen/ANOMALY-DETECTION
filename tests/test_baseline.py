import numpy as np
import pytest
from itd.scoring.baseline import fit_global_baseline, fit_role_baselines


@pytest.mark.parametrize("matrix", [
    1, [1, 2], [], [[]], np.empty((0, 2)), np.empty((2, 0)),
    [[[1]]], [[float("nan")]], [[float("inf")]], [[float("-inf")]],
    [["bad"]], [[1], [2, 3]], [[None]],
])
@pytest.mark.parametrize("kind", ["global", "role"])
def test_invalid_matrix(matrix, kind):
    with pytest.raises(ValueError):
        if kind == "global":
            fit_global_baseline(matrix)
        else:
            fit_role_baselines(matrix, ["A"])


@pytest.mark.parametrize("roles", ["A", [["A"], ["B"]], ["A"], [None, "A"],
                                       [np.nan, "A"], [1, "A"], [["A"], "B"]])
def test_invalid_roles(roles):
    with pytest.raises(ValueError):
        fit_role_baselines([[1, 2], [3, 4]], roles)


def test_statistics_and_role_normalization():
    matrix = [[1, 2], [3, 4]]
    result = fit_global_baseline(matrix)
    np.testing.assert_allclose(result["mean"], [2, 3])
    np.testing.assert_allclose(result["std"], [1, 1])
    role = fit_role_baselines(matrix, [" A ", "A"])["A"]
    assert role["n_samples"] == 2
    np.testing.assert_allclose(role["mean"], result["mean"])
    np.testing.assert_allclose(role["std"], result["std"])


def test_constant_single_sample_and_unknown():
    result = fit_role_baselines([[2, 2], [9, 9], [8, 8]], ["A", "UNKNOWN", " "])
    assert set(result) == {"A"}
    np.testing.assert_allclose(result["A"]["std"], [0, 0])
    np.testing.assert_allclose(fit_global_baseline([[2, 2]])["std"], [0, 0])


def test_input_is_not_modified():
    matrix = np.array([[1., 2.], [3., 4.]])
    original = matrix.copy()
    roles = [" A ", "A"]
    fit_role_baselines(matrix, roles)
    np.testing.assert_array_equal(matrix, original)
    assert roles == [" A ", "A"]
