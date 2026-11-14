"""Causal, paired selected-tier scoring with optional monthly Personal reset (SPEC-005)."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from itertools import groupby

from .routing import CASES, RoutingConfig, select_tier
from .score_reference import (
    RAW_SCORE_FIELDS, canonical_day, finite_number, fuse_raw_scores, ordered_keys_sha256,
    raw_rows_sha256, references_fingerprint, robust_reference, scientific_config, validate_raw_rows,
    validate_reference,
)


MODES = ('natural', 'monthly_reset')
STATE_FIELDS = {'format_version', 'mode', 'reference_fingerprint', 'last_processed_day',
                'reset_period', 'users'}


def init_profile_state(train_rows: list[dict], first_day: str, mode: str,
                       references: dict, config: dict) -> dict:
    train = validate_raw_rows(train_rows)
    first_day = canonical_day(first_day)
    if mode not in MODES:
        raise ValueError('mode must be natural or monthly_reset')
    fingerprint = references_fingerprint(references, config)
    if (references['train_keys_sha256'] != ordered_keys_sha256(train) or
            references['n_train_rows'] != len(train) or
            references['train_values_sha256'] != raw_rows_sha256(train) or
            references['train_last_day'] != train[-1]['day']):
        raise ValueError('reference and Personal initializer train coverage differ')
    last = train[-1]['day']
    if last >= first_day:
        raise ValueError('all train days must precede evaluation')
    state = {'format_version': 1, 'mode': mode, 'reference_fingerprint': fingerprint,
             'last_processed_day': last, 'reset_period': None, 'users': {}}
    if mode == 'natural':
        cutoff = (date.fromisoformat(first_day) -
                  timedelta(days=config['routing']['window_days'])).isoformat()
        for row in train:
            if row['day'] >= cutoff:
                state['users'].setdefault(row['user'], []).append(_history_entry(row))
    return state


def _history_entry(row: dict) -> dict:
    return {name: row[name] for name in ('day', *RAW_SCORE_FIELDS)}


def _validate_state(state: dict, first_day: str, fingerprint: str, train_last_day: str) -> None:
    if not isinstance(state, dict) or set(state) != STATE_FIELDS:
        raise ValueError('invalid score history state fields')
    if type(state['format_version']) is not int or state['format_version'] != 1:
        raise ValueError('invalid score history state version')
    if state['mode'] not in MODES or state['reference_fingerprint'] != fingerprint:
        raise ValueError('score state mode/reference fingerprint mismatch')
    last = canonical_day(state['last_processed_day'])
    if last < train_last_day:
        raise ValueError('score history cannot precede frozen train end')
    if last >= first_day:
        raise ValueError('evaluation must start after last_processed_day; replay is forbidden')
    period = state['reset_period']
    if state['mode'] == 'natural':
        if period is not None:
            raise ValueError('natural history must not contain a reset period')
    elif period is not None and period != last[:7]:
        raise ValueError('monthly reset cursor must match last_processed_day month')
    elif period is None and last != train_last_day:
        raise ValueError('monthly reset cursor cannot be null after evaluation starts')
    users = state['users']
    if not isinstance(users, dict):
        raise ValueError('score history users must be a dictionary')
    if state['mode'] == 'monthly_reset' and period is None and users:
        raise ValueError('uninitialized monthly-reset history must be empty')
    for user, entries in users.items():
        if (not isinstance(user, str) or not user or user != user.strip()
                or not isinstance(entries, list) or not entries):
            raise ValueError('score history needs normalized users and nonempty entry lists')
        previous = None
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {'day', *RAW_SCORE_FIELDS}:
                raise ValueError('history dates require exactly one pair of raw scores')
            day = canonical_day(entry['day'])
            if day > last or (previous is not None and day <= previous):
                raise ValueError('history contains future, duplicate or unordered days')
            if state['mode'] == 'monthly_reset' and day[:7] != period:
                raise ValueError('monthly-reset history contains pre-reset observations')
            for field in RAW_SCORE_FIELDS:
                finite_number(entry[field], f'history {field}')
            previous = day


def _members_for_group(references: dict, case: str, group: str) -> dict:
    if group == 'UNKNOWN':
        return {}
    try:
        members = references['group_members'][case]
        raw = members.get(group)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('frozen Group membership is missing or invalid') from error
    if raw is None:
        return {}
    if (not isinstance(raw, list) or not raw or any(
            not isinstance(user, str) or not user or user != user.strip() for user in raw)
            or len(raw) != len(set(raw))):
        raise ValueError('frozen Group membership requires unique normalized user lists')
    return {group: set(raw)}


def _selected_reference(references: dict, case: str, group: str, tier: str,
                        personal: list[dict], epsilon: float, n_group_users: int | None) -> dict:
    try:
        if tier == 'personal':
            values = [fuse_raw_scores(entry, references)['fused_score'] for entry in personal]
            return robust_reference(values, epsilon)
        if tier == 'global':
            reference = references['global']
            if reference['n_rows'] != references['n_train_rows']:
                raise ValueError('Global reference and train coverage differ')
        else:
            reference = references['groups'][case][group]
            if (type(reference['n_distinct_users']) is not int or
                    reference['n_distinct_users'] != n_group_users or
                    reference['n_rows'] < n_group_users or
                    not isinstance(reference['keys_sha256'], str) or
                    len(reference['keys_sha256']) != 64 or
                    any(char not in '0123456789abcdef' for char in reference['keys_sha256'])):
                raise ValueError('Group reference and membership coverage differ')
        return validate_reference(reference, epsilon)
    except (KeyError, TypeError, OverflowError) as error:
        raise ValueError(f'selected {tier} reference missing or invalid; no fallback') from error


def score_profile_days(rows: list[dict], references: dict, state: dict,
                       config: dict) -> tuple[list[dict], dict]:
    """Score paired cases before appending a day; return a separate causal state (§4.5)."""
    records = validate_raw_rows(rows)
    science = scientific_config(config)
    fingerprint = references_fingerprint(references, config)
    _validate_state(state, records[0]['day'], fingerprint, references['train_last_day'])
    routing = RoutingConfig(**science['routing'])
    epsilon = science['normalization']['epsilon']
    new_state, output = deepcopy(state), []
    for day, daily_records in groupby(records, key=lambda row: row['day']):
        daily = list(daily_records)
        period = day[:7]
        # SPEC-005 §4.5: reset occurs once at the first observed row of a new month.
        if new_state['mode'] == 'monthly_reset' and new_state['reset_period'] != period:
            new_state['users'] = {}
            new_state['reset_period'] = period
        cutoff = (date.fromisoformat(day) - timedelta(days=routing.window_days)).isoformat()
        new_state['users'] = {
            user: kept for user, entries in new_state['users'].items()
            if (kept := [entry for entry in entries if entry['day'] >= cutoff])
        }
        for row in daily:
            personal = new_state['users'].get(row['user'], [])
            n_personal = len(personal)
            fused = fuse_raw_scores(row, references)
            shared = {}
            for case in CASES:
                group = row[case]
                # Do not look up Group membership/reference once Personal is sufficient.
                members = (None if n_personal >= routing.min_personal_days else
                           _members_for_group(references, case, group))
                selected = select_tier(n_personal, group, members, routing)
                tier = selected['selected_tier']
                if tier in shared:
                    reference, score = shared[tier]
                else:
                    reference = _selected_reference(references, case, group, tier, personal,
                                                    epsilon, selected['n_group_users'])
                    score = finite_number((fused['fused_score'] - reference['median']) /
                                          reference['scale'], 'final score')
                    if tier in {'personal', 'global'}:
                        shared[tier] = reference, score
                output.append({
                    'user': row['user'], 'day': day, 'mode': new_state['mode'],
                    'group_key': case, 'group_value': group, **selected,
                    'n_personal_days': n_personal,
                    'cold_profile': n_personal < routing.min_personal_days,
                    **{field: row[field] for field in RAW_SCORE_FIELDS}, **fused,
                    'reference_n_rows': reference['n_rows'],
                    'reference_median': reference['median'], 'reference_iqr': reference['iqr'],
                    'reference_scale': reference['scale'],
                    'reference_scale_floored': reference['scale_floored'],
                    'feature_scale_floored': references['branches']['feature']['scale_floored'],
                    'sequence_scale_floored': references['branches']['sequence']['scale_floored'],
                    'score': score,
                })
        # One append per user-day only after every user and both cases were scored.
        for row in daily:
            new_state['users'].setdefault(row['user'], []).append(_history_entry(row))
        new_state['last_processed_day'] = day
    return output, new_state
