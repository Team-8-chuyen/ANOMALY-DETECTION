"""Feature isolation scores for the CPU pilot (SPEC-004 sections 4.2 and 4.4)."""
from __future__ import annotations

from numbers import Real
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.utils.validation import check_is_fitted


N_FEATURES = 200
CONFIG_KEYS = frozenset({
    'n_estimators', 'max_samples', 'max_features', 'bootstrap',
    'contamination', 'n_jobs',
})


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer, not bool')
    return value


def _matrix(X: np.ndarray) -> np.ndarray:
    """Validate before casting: object/bool values must not become real features."""
    if not isinstance(X, np.ndarray):
        raise ValueError('feature input must be a NumPy array')
    if X.ndim != 2 or X.shape[0] < 1 or X.shape[1] != N_FEATURES:
        raise ValueError(f'feature input must have shape (N, {N_FEATURES}) with N >= 1')
    if X.dtype.kind not in 'fiu':
        raise ValueError('feature input must have real numeric dtype, not bool or object')
    if not np.isfinite(X).all():
        raise ValueError('feature input must contain only finite values')
    with np.errstate(over='ignore', invalid='ignore'):
        result = np.ascontiguousarray(X, dtype=np.float32)
    if not np.isfinite(result).all():
        raise ValueError('feature input must remain finite after float32 conversion')
    return result


def fit_feature_if(X: np.ndarray, config: dict, seed: int) -> IsolationForest:
    """Fit one shared IF on already transformed training rows only."""
    matrix = _matrix(X)
    if not isinstance(config, dict) or set(config) != CONFIG_KEYS:
        raise ValueError(f'isolation_forest config requires exactly {sorted(CONFIG_KEYS)}')
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError('seed must be an integer in [0, 2**32), not bool')
    n_estimators = _positive_int(config['n_estimators'], 'n_estimators')
    max_samples = _positive_int(config['max_samples'], 'max_samples')
    n_jobs = _positive_int(config['n_jobs'], 'n_jobs')
    max_features = config['max_features']
    if (isinstance(max_features, bool) or not isinstance(max_features, Real)
            or not np.isfinite(max_features) or not 0 < max_features <= 1):
        raise ValueError('max_features must be a finite fraction in (0, 1]')
    if not isinstance(config['bootstrap'], bool):
        raise ValueError('bootstrap must be bool')
    if config['contamination'] != 'auto':
        raise ValueError('the pilot requires contamination="auto" and exports no IF cutoff')

    # SPEC-004 section 4.4: cap per-tree sampling without using validation rows.
    model = IsolationForest(
        n_estimators=n_estimators,
        max_samples=min(max_samples, matrix.shape[0]),
        max_features=float(max_features),
        bootstrap=config['bootstrap'],
        contamination='auto',
        random_state=seed,
        n_jobs=n_jobs,
    )
    return model.fit(matrix)


def score_feature_if(model: IsolationForest, X: np.ndarray) -> np.ndarray:
    """Return raw scores with larger values meaning more anomalous behavior."""
    matrix = _matrix(X)
    if not isinstance(model, IsolationForest):
        raise ValueError('model must be a fitted IsolationForest')
    check_is_fitted(model)
    if model.n_features_in_ != N_FEATURES:
        raise ValueError(f'model must have been fit with {N_FEATURES} input columns')
    # SPEC-004 section 4.4: no predict(), contamination threshold or refitting.
    result = -np.asarray(model.score_samples(matrix), dtype=np.float64)
    if result.shape != (matrix.shape[0],) or not np.isfinite(result).all():
        raise ValueError('Isolation Forest returned invalid raw scores')
    return result
