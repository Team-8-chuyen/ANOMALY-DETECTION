"""Validate and attach selected-layer scores without transforming them (SPEC-002 §14.7)."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import math
from numbers import Real


CASES = frozenset({'department', 'role'})
TIERS = frozenset({'personal', 'group', 'global'})
SCORE_COLUMNS = frozenset({'user', 'day', 'group_key', 'selected_tier', 'score'})


def _key(row: dict, source: str) -> tuple[str, str, str]:
    if not isinstance(row, dict):
        raise ValueError(f'{source}: each row must be a dictionary')
    user, day, case = (row.get(name) for name in ('user', 'day', 'group_key'))
    if not isinstance(user, str) or not user.strip():
        raise ValueError(f'{source}: user must be a non-empty string')
    if not isinstance(day, str):
        raise ValueError(f'{source}: day must use YYYY-MM-DD')
    try:
        parsed = date.fromisoformat(day)
    except ValueError as error:
        raise ValueError(f'{source}: day must use YYYY-MM-DD') from error
    if parsed.isoformat() != day:
        raise ValueError(f'{source}: day must use YYYY-MM-DD')
    if not isinstance(case, str) or case not in CASES:
        raise ValueError(f'{source}: group_key must be department or role')
    tier = row.get('selected_tier')
    if not isinstance(tier, str) or tier not in TIERS:
        raise ValueError(f'{source}: invalid selected_tier')
    return user.strip(), day, case


def _finite_score(value: object) -> None:
    # Negative values and numeric zero are valid; neither imply an alert or a probability.
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError('scores: score must be a finite real number, not bool or null')
    try:
        finite = math.isfinite(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError('scores: score must be a finite real number') from error
    if not finite:
        raise ValueError('scores: score must be finite')


def attach_selected_scores(routes: list[dict], scores: list[dict]) -> list[dict]:
    """Return paired routes with externally supplied scores, preserving order and score values.

    The producer must return exactly one score for each selected case/user/day/tier.
    Missing scores are input errors, never reasons to change an already selected tier.
    This validates the paired producer contract; it does not establish score calibration.
    """
    if not isinstance(routes, list) or not routes:
        raise ValueError('routes must be a non-empty list')
    if not isinstance(scores, list):
        raise ValueError('scores must be a list')

    route_by_key: dict[tuple[str, str, str], dict] = {}
    pairs: dict[tuple[str, str], dict[str, dict]] = {}
    for row in routes:
        key = _key(row, 'routes')
        if key in route_by_key:
            raise ValueError('routes: duplicate normalized user/day/case')
        route_by_key[key] = row
        pairs.setdefault(key[:2], {})[key[2]] = row
    if any(set(pair) != CASES for pair in pairs.values()):
        raise ValueError('routes: each user/day requires both Department and Role')

    score_by_key: dict[tuple[str, str, str], dict] = {}
    for row in scores:
        if not isinstance(row, dict) or set(row) != SCORE_COLUMNS:
            raise ValueError('scores: expected exactly user,day,group_key,selected_tier,score')
        key = _key(row, 'scores')
        if key in score_by_key:
            raise ValueError('scores: duplicate normalized user/day/case')
        _finite_score(row['score'])
        if key not in route_by_key:
            raise ValueError('scores: extra user/day/case not present in routes')
        if row['selected_tier'] != route_by_key[key]['selected_tier']:
            raise ValueError('scores: selected_tier does not match routing')
        score_by_key[key] = row
    if score_by_key.keys() != route_by_key.keys():
        raise ValueError('scores: missing selected-layer scores')

    for (user, day), pair in pairs.items():
        tier = pair['department']['selected_tier']
        if tier in {'personal', 'global'} and pair['role']['selected_tier'] == tier:
            left = score_by_key[(user, day, 'department')]['score']
            right = score_by_key[(user, day, 'role')]['score']
            if left != right:
                raise ValueError(f'scores: shared {tier} scores differ between paired cases')

    output = deepcopy(routes)
    for row in output:
        row['score'] = score_by_key[_key(row, 'routes')]['score']
        row['score_status'] = 'provided'
    return output
