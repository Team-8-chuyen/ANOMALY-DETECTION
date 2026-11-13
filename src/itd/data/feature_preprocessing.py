"""Train-only active-cell medians and explicit mask inputs (SPEC-004 section 4.2)."""
from __future__ import annotations

from numbers import Real
import math

import numpy as np

FEATURE_FIELDS = tuple(f'f{i:03d}' for i in range(1, 101))
MASK_FIELDS = tuple(f'm{i:03d}' for i in range(1, 101))


def _feature_cells(row: dict) -> tuple[list[float | None], list[bool]]:
    if not isinstance(row, dict):
        raise ValueError('feature row must be a dictionary')
    missing = set(FEATURE_FIELDS + MASK_FIELDS) - row.keys()
    if missing:
        raise ValueError(f'feature row missing columns: {sorted(missing)}')
    values, mask = [], []
    for feature, flag in zip(FEATURE_FIELDS, MASK_FIELDS):
        active = row[flag]
        if type(active) is not bool:
            raise ValueError(f'{flag}: expected bool')
        mask.append(active)
        if not active:
            values.append(None)
            continue
        value = row[feature]
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError(f'{feature}: active value must be a finite number')
        values.append(float(value))
    return values, mask


class FeaturePreprocessor:
    """Inactive values never participate in median fitting or inference."""

    def __init__(self) -> None:
        self.medians: np.ndarray | None = None
        self.counts: np.ndarray | None = None
        self.n_fit_rows = 0

    def fit(self, fit_rows: list[dict]) -> FeaturePreprocessor:
        if not isinstance(fit_rows, list) or not fit_rows:
            raise ValueError('feature fit rows must be nonempty')
        columns: list[list[float]] = [[] for _ in FEATURE_FIELDS]
        for row in fit_rows:
            values, mask = _feature_cells(row)
            for j, active in enumerate(mask):
                if active:
                    columns[j].append(values[j])
        empty = [FEATURE_FIELDS[j] for j, cells in enumerate(columns) if not cells]
        if empty:
            raise ValueError(f'no active fit observations for feature(s): {empty}')
        medians = np.array([np.median(cells) for cells in columns], dtype=np.float64)
        if not np.isfinite(medians).all():
            raise ValueError('non-finite feature fit median')
        self.medians = medians
        self.counts = np.array([len(cells) for cells in columns], dtype=np.int64)
        self.n_fit_rows = len(fit_rows)
        return self

    def transform(self, rows: list[dict]) -> np.ndarray:
        if self.medians is None:
            raise ValueError('feature preprocessor has not been fitted')
        if not isinstance(rows, list):
            raise ValueError('feature rows must be a list')
        output = np.zeros((len(rows), 2 * len(FEATURE_FIELDS)), dtype=np.float32)
        for i, row in enumerate(rows):
            values, mask = _feature_cells(row)
            for j, active in enumerate(mask):
                output[i, j] = values[j] if active else self.medians[j]
            output[i, len(FEATURE_FIELDS):] = mask
        if not np.isfinite(output).all():
            raise ValueError('feature transform overflowed float32')
        return output

    def to_dict(self) -> dict:
        if self.medians is None or self.counts is None:
            raise ValueError('feature preprocessor has not been fitted')
        return {'version': 1, 'fields': list(FEATURE_FIELDS), 'mask_fields': list(MASK_FIELDS),
                'medians': self.medians.tolist(), 'counts': self.counts.tolist(),
                'n_fit_rows': self.n_fit_rows, 'output_order': list(FEATURE_FIELDS + MASK_FIELDS)}

    @classmethod
    def from_dict(cls, state: dict) -> FeaturePreprocessor:
        expected = {'version', 'fields', 'mask_fields', 'medians', 'counts', 'n_fit_rows', 'output_order'}
        if (not isinstance(state, dict) or set(state) != expected
                or type(state['version']) is not int or state['version'] != 1):
            raise ValueError('invalid feature preprocessor state')
        if (state['fields'] != list(FEATURE_FIELDS) or state['mask_fields'] != list(MASK_FIELDS)
                or state['output_order'] != list(FEATURE_FIELDS + MASK_FIELDS)):
            raise ValueError('feature preprocessor column order mismatch')
        if type(state['n_fit_rows']) is not int or state['n_fit_rows'] < 1:
            raise ValueError('invalid feature fit row count')
        medians, counts = state['medians'], state['counts']
        if not isinstance(medians, list) or len(medians) != len(FEATURE_FIELDS):
            raise ValueError('invalid feature medians')
        if any(isinstance(x, bool) or not isinstance(x, Real) or not math.isfinite(x) for x in medians):
            raise ValueError('invalid feature medians')
        if not isinstance(counts, list) or len(counts) != len(FEATURE_FIELDS):
            raise ValueError('invalid feature active counts')
        if any(type(x) is not int or not 1 <= x <= state['n_fit_rows'] for x in counts):
            raise ValueError('invalid feature active counts')
        result = cls()
        result.medians = np.asarray(medians, dtype=np.float64).copy()
        result.counts = np.asarray(counts, dtype=np.int64).copy()
        result.n_fit_rows = state['n_fit_rows']
        return result
