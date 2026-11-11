"""Causal single-tier routing shared by Department/Role cases (SPEC-002 §14)."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import groupby

CASES = ('department', 'role')


@dataclass(frozen=True)
class RoutingConfig:
    window_days: int = 30
    min_personal_days: int = 7
    min_group_users: int = 2

    def __post_init__(self):
        if (type(self.window_days) is not int or self.window_days < 1
                or type(self.min_personal_days) is not int
                or not 1 <= self.min_personal_days <= self.window_days
                or type(self.min_group_users) is not int or self.min_group_users < 2):
            raise ValueError('invalid routing window or minimum sample counts')


def _day(value) -> date:
    if not isinstance(value, str):
        raise ValueError('day must use YYYY-MM-DD')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError('day must use YYYY-MM-DD') from error
    if parsed.isoformat() != value:
        raise ValueError('day must use YYYY-MM-DD')
    return parsed


def _user(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('user must be a non-empty string')
    return value.strip()


def _records(rows: list[dict]) -> list[tuple]:
    if not isinstance(rows, list) or not rows:
        raise ValueError('rows must be a non-empty list')
    records, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('each row must be a dictionary')
        try:
            user, day = _user(row['user']), _day(row['day'])
            groups = {}
            for case in CASES:
                raw = row[case]
                missing = row[f'{case}_missing']
                if not isinstance(raw, str) or type(missing) is not bool:
                    raise ValueError('group metadata must be string with boolean missing flag')
                value = raw.strip() or 'UNKNOWN'
                if (value == 'UNKNOWN') != missing:
                    raise ValueError('group and missing flag disagree')
                groups[case] = value
        except KeyError as error:
            raise ValueError(f'missing routing column {error.args[0]}') from error
        if (user, day) in seen:
            raise ValueError('duplicate normalized user/day')
        seen.add((user, day))
        records.append((day, user, row['user'], groups))
    return sorted(records, key=lambda item: (item[0], item[1]))


def _members(group_members: dict, *, serialized: bool = False) -> dict:
    if not isinstance(group_members, dict) or set(group_members) != set(CASES):
        raise ValueError('membership must contain Department and Role cases')
    result = {}
    for case in CASES:
        groups = group_members[case]
        if not isinstance(groups, dict):
            raise ValueError('case membership must be a group mapping')
        result[case] = {}
        for raw_group, raw_users in groups.items():
            if not isinstance(raw_group, str) or not raw_group.strip() or raw_group.strip() == 'UNKNOWN':
                raise ValueError('membership group must be a valid string')
            group = raw_group.strip()
            if group in result[case]:
                raise ValueError('duplicate normalized membership group')
            if type(raw_users) is not (list if serialized else set):
                raise ValueError('membership users must be sets (lists in JSON)')
            users = [_user(user) for user in raw_users]
            if len(users) != len(set(users)):
                raise ValueError('duplicate normalized membership user')
            result[case][group] = set(users)
    return result


def fit_group_members(train_rows: list[dict]) -> dict:
    """Frozen train membership counts distinct users, including the current user."""
    result = {case: {} for case in CASES}
    for _, user, _, groups in _records(train_rows):
        for case in CASES:
            if groups[case] != 'UNKNOWN':
                result[case].setdefault(groups[case], set()).add(user)
    return result


def group_members_to_json(group_members: dict) -> dict:
    """Return deterministic JSON-compatible membership without mutating input."""
    validated = _members(group_members)
    return {case: {group: sorted(users) for group, users in sorted(validated[case].items())}
            for case in CASES}


def group_members_from_json(value: dict) -> dict:
    return _members(value, serialized=True)


def init_routing_history(train_rows: list[dict], first_day: date | str, config: RoutingConfig) -> dict:
    records = _records(train_rows)
    first = _day(first_day) if isinstance(first_day, str) else first_day
    if type(first) is not date:
        raise ValueError('first_day must be a date or YYYY-MM-DD string')
    if records[-1][0] >= first:
        raise ValueError('train must precede routing')
    cutoff = first - timedelta(days=config.window_days)
    users = {}
    for day, user, _, _ in records:
        if day >= cutoff:
            users.setdefault(user, []).append(day.isoformat())
    return {'last_date': records[-1][0].isoformat(), 'users': users}


def _validate_history(history: dict, first_day: date) -> None:
    if not isinstance(history, dict) or set(history) != {'last_date', 'users'}:
        raise ValueError('history must contain last_date and users')
    last = _day(history['last_date'])
    if last >= first_day:
        raise ValueError('routing must start after history last_date')
    if not isinstance(history['users'], dict):
        raise ValueError('history users must be a mapping')
    for user, days in history['users'].items():
        if _user(user) != user or not isinstance(days, list):
            raise ValueError('history requires normalized user and a list of days')
        previous = None
        for value in days:
            day = _day(value)
            if day > last or day >= first_day or (previous is not None and day <= previous):
                raise ValueError('history has future, duplicate or unordered days')
            previous = day


def select_tier(n_personal_days: int, group_value: str, group_members: dict,
                config: RoutingConfig) -> dict:
    if type(n_personal_days) is not int or n_personal_days < 0:
        raise ValueError('n_personal_days must be a non-negative integer')
    # SPEC-002 §14.6: sufficient Personal stops before any Group lookup.
    if n_personal_days >= config.min_personal_days:
        return {'selected_tier': 'personal', 'fallback_reason': 'personal_sufficient',
                'n_group_users': None}
    if not isinstance(group_value, str):
        raise ValueError('group_value must be a string')
    group = group_value.strip() or 'UNKNOWN'
    reason, count = 'missing', 0
    if group != 'UNKNOWN':
        if not isinstance(group_members, dict):
            raise ValueError('group_members must be a mapping')
        users = group_members.get(group)
        reason = 'unseen'
        if users is not None:
            if type(users) is not set:
                raise ValueError('group members must be a set')
            normalized = [_user(user) for user in users]
            if len(normalized) != len(set(normalized)):
                raise ValueError('duplicate normalized group user')
            count = len(normalized)
            if count >= config.min_group_users:
                return {'selected_tier': 'group',
                        'fallback_reason': 'personal_insufficient_group_sufficient',
                        'n_group_users': count}
            reason = 'too_small'
    return {'selected_tier': 'global', 'fallback_reason': f'personal_insufficient_group_{reason}',
            'n_group_users': count}


def route_days(rows: list[dict], group_members: dict, history: dict,
               config: RoutingConfig) -> tuple[list[dict], dict]:
    records = _records(rows)
    validated_members = _members(group_members)
    _validate_history(history, records[0][0])
    state, output = deepcopy(history), []
    for day, daily_records in groupby(records, key=lambda item: item[0]):
        daily = list(daily_records)
        cutoff = (day - timedelta(days=config.window_days)).isoformat()
        state['users'] = {user: [d for d in days if d >= cutoff]
                          for user, days in state['users'].items()}
        state['users'] = {user: days for user, days in state['users'].items() if days}
        for _, user, original_user, groups in daily:
            count = len(state['users'].get(user, []))
            for case in CASES:
                selected = select_tier(count, groups[case], validated_members[case], config)
                output.append({'user': original_user, 'day': day.isoformat(), 'group_key': case,
                               'group_value': groups[case], **selected, 'n_personal_days': count,
                               'score': None, 'score_status': 'awaiting_external_score'})
        # Only after the entire day is routed does it enter shared Personal history.
        for _, user, _, _ in daily:
            state['users'].setdefault(user, []).append(day.isoformat())
        state['last_date'] = day.isoformat()
    return output, state
