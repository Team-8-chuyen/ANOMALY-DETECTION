"""Continuous IF score contract, rather than detection accuracy on a toy sample."""
from __future__ import annotations

import copy

import joblib
import numpy as np
import pytest
from sklearn.ensemble import IsolationForest
from sklearn.exceptions import NotFittedError

from itd.models.feature_isolation_forest import fit_feature_if, score_feature_if


@pytest.fixture
def config():
    return {
        'n_estimators': 100, 'max_samples': 256, 'max_features': 1.0,
        'bootstrap': False, 'contamination': 'auto', 'n_jobs': 2,
    }


@pytest.fixture
def X():
    return np.random.default_rng(3).normal(size=(19, 200)).astype(np.float32)


def test_continuous_score_sign_and_no_predict(config, X, monkeypatch):
    model = fit_feature_if(X, config, seed=0)
    expected = -model.score_samples(X)

    def forbidden(*args, **kwargs):
        raise AssertionError('predict or fit must not be called when scoring')

    monkeypatch.setattr(model, 'predict', forbidden)
    monkeypatch.setattr(model, 'fit', forbidden)
    scores = score_feature_if(model, X)
    np.testing.assert_array_equal(scores, expected)
    assert scores.dtype == np.float64
    assert scores.shape == (len(X),)


def test_fit_caps_sampling_and_preserves_input(config, X):
    before = X.copy()
    config_before = copy.deepcopy(config)
    model = fit_feature_if(X, config, seed=7)
    assert model.max_samples_ == len(X)
    assert model.n_estimators == 100
    assert model.random_state == 7
    assert model.n_jobs == 2
    assert model.max_features == 1.0
    assert model.n_features_in_ == 200
    np.testing.assert_array_equal(X, before)
    assert config == config_before


def test_fit_uses_cap_when_train_larger_than_cap(config):
    matrix = np.zeros((257, 200), dtype=np.float32)
    model = fit_feature_if(matrix, config, seed=0)
    assert model.max_samples_ == 256


def test_reproducible_fit_and_joblib_roundtrip(config, X, tmp_path):
    one = fit_feature_if(X, config, seed=0)
    two = fit_feature_if(X, config, seed=0)
    np.testing.assert_array_equal(score_feature_if(one, X), score_feature_if(two, X))
    path = tmp_path / 'own_if_model.joblib'
    joblib.dump(one, path)
    restored = joblib.load(path)
    np.testing.assert_array_equal(score_feature_if(restored, X), score_feature_if(one, X))


def test_float64_noncontiguous_conversion(config, X):
    matrix = np.tile(X.astype(np.float64), (1, 2))[:, ::2]
    assert not matrix.flags.c_contiguous
    model = fit_feature_if(matrix, config, seed=0)
    np.testing.assert_array_equal(score_feature_if(model, matrix),
                                  -model.score_samples(matrix.astype(np.float32)))


@pytest.mark.parametrize('bad', [
    np.empty((0, 200)), np.ones((2, 100)), np.ones((2, 201)), np.ones(200),
    np.ones((1, 2, 200)), np.ones((2, 200), dtype=bool),
    np.ones((2, 200), dtype=object), np.ones((2, 200), dtype=complex),
    np.full((2, 200), '1'), [[1.0] * 200],
])
def test_invalid_matrix_rejected_before_fit(config, bad):
    with pytest.raises(ValueError, match='feature input'):
        fit_feature_if(bad, config, seed=0)


@pytest.mark.parametrize('value', [np.nan, np.inf, -np.inf, 1e300])
def test_nonfinite_or_overflow_matrix_rejected(config, value):
    bad = np.zeros((2, 200), dtype=np.float64)
    bad[0, 0] = value
    with pytest.raises(ValueError, match='finite'):
        fit_feature_if(bad, config, seed=0)


@pytest.mark.parametrize('field,value', [
    ('n_estimators', True), ('n_estimators', 0), ('max_samples', 'auto'),
    ('max_samples', -1), ('n_jobs', True), ('n_jobs', 0),
    ('max_features', True), ('max_features', 0.0), ('max_features', 1.1),
    ('max_features', np.nan), ('bootstrap', 0), ('contamination', 0.1),
])
def test_invalid_config_value_rejected(config, X, field, value):
    config[field] = value
    with pytest.raises(ValueError):
        fit_feature_if(X, config, seed=0)


@pytest.mark.parametrize('seed', [True, -1, 2**32, 0.0, '0'])
def test_invalid_seed_rejected(config, X, seed):
    with pytest.raises(ValueError, match='seed'):
        fit_feature_if(X, config, seed)


def test_unknown_or_missing_config_key_rejected(config, X):
    with pytest.raises(ValueError, match='exactly'):
        fit_feature_if(X, dict(config, unexpected=True), seed=0)
    del config['max_features']
    with pytest.raises(ValueError, match='exactly'):
        fit_feature_if(X, config, seed=0)


def test_score_rejects_invalid_model_or_input(config, X):
    with pytest.raises(ValueError, match='model'):
        score_feature_if(object(), X)
    with pytest.raises(NotFittedError):
        score_feature_if(IsolationForest(), X)
    model = fit_feature_if(X, config, seed=0)
    with pytest.raises(ValueError, match='finite'):
        score_feature_if(model, np.full((1, 200), np.nan))
    foreign = IsolationForest(n_estimators=2).fit(np.ones((3, 2)))
    with pytest.raises(ValueError, match='200'):
        score_feature_if(foreign, X)


def test_score_rejects_corrupt_estimator_output(config, X, monkeypatch):
    model = fit_feature_if(X, config, seed=0)
    monkeypatch.setattr(model, 'score_samples', lambda _: np.full(len(X), np.nan))
    with pytest.raises(ValueError, match='invalid raw scores'):
        score_feature_if(model, X)
