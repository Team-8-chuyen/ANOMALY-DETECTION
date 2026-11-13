"""Mixed-type train-only vocabularies/scalers for Sequence24 (SPEC-004 section 4.2)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
from numbers import Integral, Real

import numpy as np

from .sequence_dataset import (SEQUENCE_FIELDS, CATEGORICAL_FIELDS, NUMERIC_FIELDS,
                               BOOLEAN_FIELDS, CAT_INDICES, NUMERIC_INDICES, BOOLEAN_INDICES)


@dataclass
class EncodedDay:
    cat: np.ndarray
    numeric: np.ndarray
    boolean: np.ndarray
    attribute_mask: np.ndarray
    unseen_counts: dict[str, int]


def parse_attribute_mask(value: object) -> list[bool]:
    if not isinstance(value, str):
        raise ValueError('attribute_mask must be a JSON string')
    try:
        mask = json.loads(value)
    except (ValueError, TypeError) as error:
        raise ValueError('attribute_mask must be valid JSON') from error
    if not isinstance(mask, list) or len(mask) != len(SEQUENCE_FIELDS) or any(type(x) is not bool for x in mask):
        raise ValueError('attribute_mask must contain exactly 24 booleans')
    if not any(mask):
        raise ValueError('a sequence row must contain an active attribute')
    return mask


def _category(field: str, value: object) -> str | int:
    if field == 'gap_bucket':
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError(f'{field}: active value must be an integer category')
        return int(value)
    if not isinstance(value, str):
        raise ValueError(f'{field}: active value must be a string category')
    return value


def validated_sequence_row(row: dict) -> tuple[list[bool], dict[str, object]]:
    """Do not even coerce payloads under false applicability masks."""
    if not isinstance(row, dict):
        raise ValueError('sequence row must be a dictionary')
    missing = set(SEQUENCE_FIELDS + ('attribute_mask',)) - row.keys()
    if missing:
        raise ValueError(f'sequence row missing columns: {sorted(missing)}')
    mask = parse_attribute_mask(row['attribute_mask'])
    values: dict[str, object] = {}
    for i, field in enumerate(SEQUENCE_FIELDS):
        if not mask[i]:
            continue
        value = row[field]
        if field in CATEGORICAL_FIELDS:
            values[field] = _category(field, value)
        elif field in BOOLEAN_FIELDS:
            if type(value) is not bool:
                raise ValueError(f'{field}: active value must be bool')
            values[field] = value
        else:
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                raise ValueError(f'{field}: active value must be a finite number')
            values[field] = float(value)
    return mask, values


def _rows(day) -> list[dict]:
    rows = getattr(day, 'rows', None)
    if not isinstance(rows, list) or not rows:
        raise ValueError('a sequence day/window must contain at least one row')
    return rows


class SequencePreprocessor:
    def __init__(self, epsilon: float = 1e-6) -> None:
        if isinstance(epsilon, bool) or not isinstance(epsilon, Real) or not math.isfinite(epsilon) or epsilon <= 0:
            raise ValueError('epsilon must be a finite positive number')
        self.epsilon = float(epsilon)
        self.vocabularies: dict[str, list[str | int]] | None = None
        self.means: np.ndarray | None = None
        self.scales: np.ndarray | None = None
        self.counts: list[int] | None = None
        self.n_fit_rows = 0
        self.fit_start: str | None = None
        self.fit_end: str | None = None
        self.cohort_sha256: str | None = None
        self._category_ids: dict[str, dict[str | int, int]] = {}

    @property
    def vocab_sizes(self) -> list[int]:
        if self.vocabularies is None:
            raise ValueError('sequence preprocessor has not been fitted')
        return [2 + len(self.vocabularies[field]) for field in CATEGORICAL_FIELDS]

    def fit(self, fit_days: list) -> SequencePreprocessor:
        if not isinstance(fit_days, list) or not fit_days:
            raise ValueError('sequence fit days must be nonempty')
        categories = {field: set() for field in CATEGORICAL_FIELDS}
        numeric: dict[str, list[float]] = {field: [] for field in NUMERIC_FIELDS}
        counts = [0] * len(SEQUENCE_FIELDS)
        rows_count = 0
        dates, users = [], set()
        for day in fit_days:
            day_value, user = getattr(day, 'day', None), getattr(day, 'user', None)
            if not isinstance(day_value, str) or date.fromisoformat(day_value).isoformat() != day_value:
                raise ValueError('sequence fit day must use YYYY-MM-DD')
            if not isinstance(user, str) or not user.strip():
                raise ValueError('sequence fit user must be nonempty')
            dates.append(day_value)
            users.add(user)
            for row in _rows(day):
                mask, values = validated_sequence_row(row)
                rows_count += 1
                for j, active in enumerate(mask):
                    counts[j] += int(active)
                for field in CATEGORICAL_FIELDS:
                    if field in values:
                        categories[field].add(values[field])
                for field in NUMERIC_FIELDS:
                    if field in values:
                        numeric[field].append(values[field])
        missing = [field for i, field in enumerate(SEQUENCE_FIELDS) if counts[i] == 0]
        if missing:
            raise ValueError(f'no active fit observations for sequence field(s): {missing}')
        means = np.array([np.mean(numeric[field], dtype=np.float64) for field in NUMERIC_FIELDS])
        std = np.array([np.std(numeric[field], ddof=0, dtype=np.float64) for field in NUMERIC_FIELDS])
        scales = np.where(std >= self.epsilon, std, 1.0)
        if not np.isfinite(means).all() or not np.isfinite(scales).all():
            raise ValueError('non-finite sequence fit statistics')
        self.vocabularies = {field: sorted(categories[field]) for field in CATEGORICAL_FIELDS}
        self._category_ids = {field: {value: i + 2 for i, value in enumerate(vocab)}
                              for field, vocab in self.vocabularies.items()}
        self.means, self.scales, self.counts = means, scales, counts
        self.n_fit_rows = rows_count
        self.fit_start, self.fit_end = min(dates), max(dates)
        self.cohort_sha256 = hashlib.sha256(json.dumps(sorted(users), ensure_ascii=False,
                                                     separators=(',', ':')).encode('utf-8')).hexdigest()
        return self

    def transform(self, day) -> EncodedDay:
        if self.vocabularies is None or self.means is None or self.scales is None:
            raise ValueError('sequence preprocessor has not been fitted')
        rows = _rows(day)
        categorical = np.zeros((len(rows), len(CAT_INDICES)), dtype=np.int64)
        numeric = np.zeros((len(rows), len(NUMERIC_INDICES)), dtype=np.float32)
        boolean = np.zeros((len(rows), len(BOOLEAN_INDICES)), dtype=np.float32)
        masks = np.zeros((len(rows), len(SEQUENCE_FIELDS)), dtype=np.bool_)
        unseen = {field: 0 for field in CATEGORICAL_FIELDS}
        for t, row in enumerate(rows):
            mask, values = validated_sequence_row(row)
            masks[t] = mask
            for j, field in enumerate(CATEGORICAL_FIELDS):
                if field in values:
                    target = self._category_ids[field].get(values[field], 1)
                    categorical[t, j] = target
                    unseen[field] += int(target == 1)
            for j, field in enumerate(NUMERIC_FIELDS):
                if field in values:
                    numeric[t, j] = (values[field] - self.means[j]) / self.scales[j]
            for j, field in enumerate(BOOLEAN_FIELDS):
                if field in values:
                    boolean[t, j] = float(values[field])
        if not np.isfinite(numeric).all():
            raise ValueError('sequence transform overflowed float32')
        return EncodedDay(categorical, numeric, boolean, masks, unseen)

    def to_dict(self) -> dict:
        if self.vocabularies is None or self.means is None or self.scales is None:
            raise ValueError('sequence preprocessor has not been fitted')
        return {'version': 1, 'fields': list(SEQUENCE_FIELDS),
                'categorical_fields': list(CATEGORICAL_FIELDS), 'numeric_fields': list(NUMERIC_FIELDS),
                'boolean_fields': list(BOOLEAN_FIELDS), 'epsilon': self.epsilon,
                'vocabularies': {key: list(value) for key, value in self.vocabularies.items()},
                'means': self.means.tolist(), 'scales': self.scales.tolist(),
                'counts': list(self.counts), 'n_fit_rows': self.n_fit_rows,
                'fit_start': self.fit_start, 'fit_end': self.fit_end, 'cohort_sha256': self.cohort_sha256}

    @classmethod
    def from_dict(cls, state: dict) -> SequencePreprocessor:
        expected = {'version', 'fields', 'categorical_fields', 'numeric_fields', 'boolean_fields',
                    'epsilon', 'vocabularies', 'means', 'scales', 'counts', 'n_fit_rows',
                    'fit_start', 'fit_end', 'cohort_sha256'}
        if not isinstance(state, dict) or set(state) != expected or type(state['version']) is not int or state['version'] != 1:
            raise ValueError('invalid sequence preprocessor state')
        for key, order in [('fields', SEQUENCE_FIELDS), ('categorical_fields', CATEGORICAL_FIELDS),
                           ('numeric_fields', NUMERIC_FIELDS), ('boolean_fields', BOOLEAN_FIELDS)]:
            if state[key] != list(order):
                raise ValueError(f'sequence preprocessor {key} mismatch')
        result = cls(state['epsilon'])
        if not isinstance(state['vocabularies'], dict) or set(state['vocabularies']) != set(CATEGORICAL_FIELDS):
            raise ValueError('invalid sequence vocabularies')
        vocabularies = {}
        for field in CATEGORICAL_FIELDS:
            vocab = state['vocabularies'][field]
            if not isinstance(vocab, list) or not vocab:
                raise ValueError(f'{field}: invalid vocabulary')
            values = [_category(field, value) for value in vocab]
            if values != sorted(set(values)):
                raise ValueError(f'{field}: vocabulary must contain unique sorted categories')
            vocabularies[field] = values
        arrays = []
        for key in ('means', 'scales'):
            values = state[key]
            if (not isinstance(values, list) or len(values) != len(NUMERIC_FIELDS)
                    or any(isinstance(x, bool) or not isinstance(x, Real) or not math.isfinite(x) for x in values)):
                raise ValueError(f'invalid sequence {key}')
            arrays.append(np.asarray(values, dtype=np.float64).copy())
        if np.any(arrays[1] <= 0):
            raise ValueError('sequence scales must be positive')
        n_rows, counts = state['n_fit_rows'], state['counts']
        if type(n_rows) is not int or n_rows < 1:
            raise ValueError('invalid sequence fit row count')
        if (not isinstance(counts, list) or len(counts) != len(SEQUENCE_FIELDS)
                or any(type(n) is not int or not 1 <= n <= n_rows for n in counts)):
            raise ValueError('invalid sequence active counts')
        try:
            fit_start = date.fromisoformat(state['fit_start']).isoformat()
            fit_end = date.fromisoformat(state['fit_end']).isoformat()
        except (ValueError, TypeError) as error:
            raise ValueError('invalid sequence fit bounds') from error
        if fit_start != state['fit_start'] or fit_end != state['fit_end'] or fit_start > fit_end:
            raise ValueError('invalid sequence fit bounds')
        fingerprint = state['cohort_sha256']
        if (not isinstance(fingerprint, str) or len(fingerprint) != 64
                or any(c not in '0123456789abcdef' for c in fingerprint)):
            raise ValueError('invalid sequence cohort hash')
        result.vocabularies = vocabularies
        result._category_ids = {field: {value: i + 2 for i, value in enumerate(vocab)}
                                for field, vocab in vocabularies.items()}
        result.means, result.scales = arrays
        result.counts, result.n_fit_rows = list(counts), n_rows
        result.fit_start, result.fit_end, result.cohort_sha256 = fit_start, fit_end, fingerprint
        return result
