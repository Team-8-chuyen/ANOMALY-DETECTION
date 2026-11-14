"""Frozen, train-only score references for SPEC-005 §3 and §4.2–4.3."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
import math
from numbers import Real

import numpy as np

from .routing import CASES, fit_group_members, group_members_to_json


RAW_SCORE_FIELDS = ('e_feature_raw', 'e_sequence_raw')


def canonical_day(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError('day must use YYYY-MM-DD')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError('day must use YYYY-MM-DD') from error
    if parsed.isoformat() != value:
        raise ValueError('day must use YYYY-MM-DD')
    return value


def finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f'{name} must be a finite real number, not bool or null')
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f'{name} must be finite') from error
    if not math.isfinite(result):
        raise ValueError(f'{name} must be finite')
    return result


def _normalized_key(row: dict) -> tuple[str, str]:
    if not isinstance(row, dict):
        raise ValueError('raw rows must be dictionaries')
    user = row.get('user')
    if not isinstance(user, str) or not user.strip():
        raise ValueError('user must be a non-empty string')
    return user.strip(), canonical_day(row.get('day'))


def validate_raw_rows(rows: list[dict]) -> list[dict]:
    """Copy and validate ISO-day raw records, retaining additional producer columns."""
    if not isinstance(rows, list) or not rows:
        raise ValueError('raw rows must be a non-empty list')
    normalized, seen = [], set()
    for original in rows:
        user, day = _normalized_key(original)
        key = user, day
        if key in seen:
            raise ValueError('duplicate normalized raw user/day')
        seen.add(key)
        row = deepcopy(original)
        row.update(user=user, day=day)
        # Same LDAP contract as pilot_dataset._metadata; blanks are not UNKNOWN.
        for case in CASES:
            value = row.get(case)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{case}: LDAP value must be nonempty')
            value = value.strip()
            missing = row.get(f'{case}_missing')
            if type(missing) is not bool or missing != (value == 'UNKNOWN'):
                raise ValueError(f'{case}_missing: inconsistent LDAP flag')
            row[case] = value
        if row.get('ldap_month') != day[:7]:
            raise ValueError('ldap_month must equal the user-day month')
        for field in RAW_SCORE_FIELDS:
            row[field] = finite_number(row.get(field), field)
        normalized.append(row)
    return sorted(normalized, key=lambda row: (row['day'], row['user']))


def ordered_keys_sha256(rows: list[dict]) -> str:
    """Version-1 newline-delimited canonical [day,user] checksum (§4.7)."""
    if not isinstance(rows, list):
        raise ValueError('key rows must be a list')
    keys = [_normalized_key(row) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate normalized user/day in key checksum')
    digest = hashlib.sha256()
    for user, day in sorted(keys, key=lambda key: (key[1], key[0])):
        encoded = json.dumps([day, user], ensure_ascii=False, separators=(',', ':'))
        digest.update((encoded + '\n').encode('utf-8'))
    return digest.hexdigest()


def raw_rows_sha256(rows: list[dict]) -> str:
    """Bind the values and LDAP metadata that produced train score references."""
    fields = ('user', 'day', 'department', 'role', 'department_missing', 'role_missing',
              'ldap_month', *RAW_SCORE_FIELDS)
    values = [{name: row[name] for name in fields} for row in validate_raw_rows(rows)]
    encoded = json.dumps(values, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def scientific_config(config: dict) -> dict:
    """Validate the accepted scientific constants without binding operational paths."""
    expected = {
        'fusion': {'feature_weight': 0.5, 'sequence_weight': 0.5},
        'normalization': {'method': 'median_iqr', 'quantile_method': 'linear',
                          'epsilon': 1e-6, 'keep_signed': True},
        'routing': {'window_days': 30, 'min_personal_days': 7, 'min_group_users': 2},
    }
    if not isinstance(config, dict):
        raise ValueError('score config must be a dictionary')
    for section, values in expected.items():
        actual = config.get(section)
        if not isinstance(actual, dict) or set(actual) != set(values):
            raise ValueError(f'invalid {section} config keys')
        for name, value in values.items():
            candidate = actual[name]
            if type(value) is bool:
                valid = type(candidate) is bool and candidate == value
            elif type(value) is int:
                valid = type(candidate) is int and candidate == value
            elif isinstance(value, float):
                valid = (not isinstance(candidate, bool) and isinstance(candidate, Real)
                         and math.isfinite(float(candidate)) and candidate == value)
            else:
                valid = type(candidate) is str and candidate == value
            if not valid:
                raise ValueError(f'{section}.{name} differs from accepted SPEC-005')
    return deepcopy(expected)


def robust_reference(values: list[float], epsilon: float) -> dict:
    """Fit signed median/IQR location-scale, with an explicit numerical floor (§4.2)."""
    epsilon = finite_number(epsilon, 'epsilon')
    if epsilon <= 0:
        raise ValueError('epsilon must be positive')
    if not isinstance(values, (list, tuple, np.ndarray)) or len(values) == 0:
        raise ValueError('reference values must be nonempty')
    array = np.asarray([finite_number(value, 'reference value') for value in values],
                       dtype=np.float64)
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            q25, median, q75 = [float(value) for value in
                                np.quantile(array, [0.25, 0.5, 0.75], method='linear')]
    except (FloatingPointError, ValueError) as error:
        raise ValueError('reference quantiles are not finite') from error
    iqr = finite_number(q75 - q25, 'reference IQR')
    if iqr < 0:
        raise ValueError('reference IQR must be nonnegative')
    return {'n_rows': len(array), 'median': median, 'q25': q25, 'q75': q75,
            'iqr': iqr, 'scale': max(iqr, epsilon), 'scale_floored': iqr < epsilon}


def validate_reference(reference: dict, epsilon: float) -> dict:
    """Validate the selected persisted reference; missing references never trigger backoff."""
    if not isinstance(reference, dict):
        raise ValueError('selected score reference must be a dictionary')
    required = {'n_rows', 'median', 'q25', 'q75', 'iqr', 'scale', 'scale_floored'}
    if not required <= set(reference):
        raise ValueError('selected score reference is incomplete')
    if type(reference['n_rows']) is not int or reference['n_rows'] < 1:
        raise ValueError('selected score reference requires positive n_rows')
    numbers = {name: finite_number(reference[name], f'reference {name}')
               for name in ('median', 'q25', 'q75', 'iqr', 'scale')}
    if (not numbers['q25'] <= numbers['median'] <= numbers['q75'] or
            numbers['iqr'] != numbers['q75'] - numbers['q25'] or
            numbers['scale'] != max(numbers['iqr'], epsilon) or
            type(reference['scale_floored']) is not bool or
            reference['scale_floored'] != (numbers['iqr'] < epsilon)):
        raise ValueError('selected reference quantiles/scale are inconsistent')
    return reference


def fuse_raw_scores(row: dict, references: dict) -> dict:
    """Apply the frozen two-branch transform before any tier normalization (§4.2)."""
    try:
        science = scientific_config(references['scientific_config'])
        epsilon = science['normalization']['epsilon']
        result = {}
        for branch in ('feature', 'sequence'):
            reference = validate_reference(references['branches'][branch], epsilon)
            raw = finite_number(row.get(f'e_{branch}_raw'), f'e_{branch}_raw')
            result[f'z_{branch}'] = finite_number(
                (raw - reference['median']) / reference['scale'], f'z_{branch}')
        result['fused_score'] = finite_number(
            science['fusion']['feature_weight'] * result['z_feature'] +
            science['fusion']['sequence_weight'] * result['z_sequence'], 'fused_score')
        return result
    except (KeyError, TypeError, OverflowError, ZeroDivisionError) as error:
        raise ValueError('invalid branch references or nonfinite fused score') from error


def fit_score_references(train_rows: list[dict], config: dict) -> dict:
    """Fit every static reference and membership from precisely the same train rows."""
    train = validate_raw_rows(train_rows)
    science = scientific_config(config)
    epsilon = science['normalization']['epsilon']
    result = {'format_version': 1, 'scientific_config': science,
              'train_keys_sha256': ordered_keys_sha256(train), 'n_train_rows': len(train),
              'train_values_sha256': raw_rows_sha256(train), 'train_last_day': train[-1]['day'],
              'branches': {branch: robust_reference(
                  [row[f'e_{branch}_raw'] for row in train], epsilon)
                  for branch in ('feature', 'sequence')}}
    fused = [fuse_raw_scores(row, result)['fused_score'] for row in train]
    result['global'] = robust_reference(fused, epsilon)
    result['group_members'] = group_members_to_json(fit_group_members(train))
    result['groups'] = {case: {} for case in CASES}
    # SPEC-005 §4.3: each row contributes once; no per-user balancing or UNKNOWN group.
    for case in CASES:
        for group, members in result['group_members'][case].items():
            indices = [i for i, row in enumerate(train) if row[case] == group]
            reference = robust_reference([fused[i] for i in indices], epsilon)
            reference.update(n_distinct_users=len(members),
                             keys_sha256=ordered_keys_sha256([train[i] for i in indices]))
            result['groups'][case][group] = reference
    return result


def references_fingerprint(references: dict, config: dict) -> str:
    """Bind score state to its producer/reference protocol, excluding output locations."""
    science = scientific_config(config)
    if (not isinstance(references, dict) or type(references.get('format_version')) is not int
            or references['format_version'] != 1
            or scientific_config(references.get('scientific_config')) != science):
        raise ValueError('reference version/scientific config mismatch')
    if (config.get('modes') != ['natural', 'monthly_reset'] or
            config.get('reset') != {'calendar': 'gregorian'}):
        raise ValueError('mode/reset config differs from accepted SPEC-005')
    count = references.get('n_train_rows')
    checksum = references.get('train_keys_sha256')
    if (type(count) is not int or count < 1 or not isinstance(checksum, str)
            or len(checksum) != 64 or any(char not in '0123456789abcdef' for char in checksum)):
        raise ValueError('invalid reference train coverage')
    canonical_day(references.get('train_last_day'))
    value_checksum = references.get('train_values_sha256')
    if (not isinstance(value_checksum, str) or len(value_checksum) != 64
            or any(char not in '0123456789abcdef' for char in value_checksum)):
        raise ValueError('invalid reference train-value checksum')
    payload = {'references': references, 'scientific_config': science,
               'modes': config['modes'], 'reset': config['reset']}
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as error:
        raise ValueError('references must contain finite JSON-compatible values') from error
    return hashlib.sha256(encoded).hexdigest()
