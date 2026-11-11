from copy import deepcopy
from datetime import date, timedelta

import pytest

from itd.scoring.routing import (RoutingConfig, fit_group_members, group_members_from_json,
                                group_members_to_json, init_routing_history, route_days, select_tier)


def row(user, day, department='Dev', role='Engineer'):
    return {'user': user, 'day': day, 'department': department, 'role': role,
            'department_missing': not department.strip() or department.strip() == 'UNKNOWN',
            'role_missing': not role.strip() or role.strip() == 'UNKNOWN'}


def train_fixture():
    return [row('U1', (date(2020, 1, 24)+timedelta(days=i)).isoformat()) for i in range(7)] + [
        row('U2', '2020-01-30'), row('U3', '2020-01-30', 'Solo', 'Technician')]


def test_personal_short_circuit_and_six_seven_boundary():
    class NoLookup(dict):
        def get(self, *args):
            raise AssertionError('must not inspect group')

    config = RoutingConfig()
    assert select_tier(7, None, NoLookup(), config) == {
        'selected_tier': 'personal', 'fallback_reason': 'personal_sufficient', 'n_group_users': None}
    assert select_tier(6, 'Dev', {'Dev': {'U1', 'U2'}}, config)['selected_tier'] == 'group'
    assert select_tier(6, 'Dev', {'Dev': {'U1'}}, config)['selected_tier'] == 'global'


@pytest.mark.parametrize('group,members,reason,count', [
    ('UNKNOWN', {}, 'missing', 0), (' ', {}, 'missing', 0), ('New', {}, 'unseen', 0),
    ('Dev', {'Dev': {'U1'}}, 'too_small', 1), ('Dev', {'Dev': set()}, 'too_small', 0)])
def test_global_reasons(group, members, reason, count):
    result = select_tier(0, group, members, RoutingConfig())
    assert result == {'selected_tier': 'global', 'fallback_reason': f'personal_insufficient_group_{reason}',
                      'n_group_users': count}


def test_membership_distinct_normalized_and_includes_current_user():
    rows = train_fixture()+[row(' U1 ', '2020-01-31', ' Dev ', ' Engineer '),
                           row('U1', '2020-02-01', 'Other', 'UNKNOWN')]
    members = fit_group_members(rows)
    assert members['department']['Dev'] == {'U1', 'U2'}
    assert members['department']['Other'] == {'U1'}
    assert 'UNKNOWN' not in members['role']
    assert select_tier(1, 'Dev', members['department'], RoutingConfig())['selected_tier'] == 'group'
    serialized = group_members_to_json(members)
    assert serialized['department']['Dev'] == ['U1', 'U2']
    assert group_members_from_json(serialized) == members
    serialized['department']['Dev'].append(' U1 ')
    with pytest.raises(ValueError, match='duplicate'):
        group_members_from_json(serialized)


def test_paired_rows_order_counts_and_waiting_score():
    train = train_fixture()
    config = RoutingConfig()
    members = fit_group_members(train)
    history = init_routing_history(train, '2020-02-01', config)
    rows = [row('New', '2020-02-01', 'Dev', 'Technician'),
            row(' U1 ', '2020-02-01', 'UNKNOWN', 'UNKNOWN')]
    saved = deepcopy((rows, members, history))
    output, state = route_days(rows, members, history, config)
    assert (rows, members, history) == saved
    assert [r['group_key'] for r in output] == ['department', 'role', 'department', 'role']
    assert [r['selected_tier'] for r in output] == ['group', 'global', 'personal', 'personal']
    assert [r['n_personal_days'] for r in output] == [0, 0, 7, 7]
    assert output[-1]['user'] == ' U1 '
    assert all(r['score'] is None and r['score_status'] == 'awaiting_external_score' for r in output)
    assert all('threshold' not in r and 'is_alert' not in r and 'w_personal' not in r for r in output)
    assert state['users']['New'] == ['2020-02-01']


def test_window_exact_boundary_gap_and_empty_checkpoint():
    config = RoutingConfig()
    train = [row('U1', '2020-01-01'), row('U1', '2020-01-02')]
    history = init_routing_history(train, date(2020, 2, 1), config)
    assert history == {'last_date': '2020-01-02', 'users': {'U1': ['2020-01-02']}}
    output, state = route_days([row('U1', '2020-02-01')], fit_group_members(train), history, config)
    assert output[0]['n_personal_days'] == 1
    later, _ = route_days([row('U1', '2020-04-01')], fit_group_members(train), state, config)
    assert later[0]['n_personal_days'] == 0
    empty = init_routing_history(train, '2020-04-01', config)
    assert empty == {'last_date': '2020-01-02', 'users': {}}


def test_future_invariance_order_split_continuity_and_group_change():
    config = RoutingConfig()
    train = train_fixture()
    members = fit_group_members(train)
    history = init_routing_history(train, '2020-02-01', config)
    rows = [row('U1', '2020-02-01', 'New', 'New'), row('New', '2020-02-01'),
            row('U1', '2020-02-02'), row('New', '2020-02-02')]
    whole, whole_state = route_days(rows, members, history, config)
    assert whole == route_days(list(reversed(rows)), members, history, config)[0]
    first, state = route_days(rows[:2], members, history, config)
    second, last = route_days(rows[2:], members, state, config)
    assert whole == first+second and whole_state == last
    changed = deepcopy(rows)
    changed[-1]['department'] = 'OTHER'
    assert route_days(changed, members, history, config)[0][:4] == first
    personal = next(r for r in first if r['user'] == 'U1')
    assert personal['selected_tier'] == 'personal' and personal['n_personal_days'] == 7
    with pytest.raises(ValueError, match='last_date'):
        route_days(rows, members, state, config)


@pytest.mark.parametrize('kwargs', [
    {'window_days': True}, {'window_days': 0}, {'min_personal_days': 0},
    {'min_personal_days': 31}, {'min_personal_days': 7.0}, {'min_group_users': 1}, {'min_group_users': False}])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        RoutingConfig(**kwargs)


@pytest.mark.parametrize('value', [-1, True, 1.5, None])
def test_invalid_personal_count(value):
    with pytest.raises(ValueError):
        select_tier(value, 'Dev', {}, RoutingConfig())


@pytest.mark.parametrize('kind', ['missing', 'user', 'day', 'flag', 'group_type', 'duplicate'])
def test_invalid_rows(kind):
    rows = [row('U1', '2020-01-01')]
    if kind == 'missing':
        rows[0].pop('role')
    elif kind == 'user':
        rows[0]['user'] = ' '
    elif kind == 'day':
        rows[0]['day'] = '20200101'
    elif kind == 'flag':
        rows[0]['role_missing'] = True
    elif kind == 'group_type':
        rows[0]['department'] = None
    else:
        rows.append(row(' U1 ', '2020-01-01'))
    with pytest.raises(ValueError):
        fit_group_members(rows)


@pytest.mark.parametrize('history', [
    {'last_date': '20200131', 'users': {}},
    {'last_date': '2020-02-01', 'users': {}},
    {'last_date': '2020-01-31', 'users': {'U1': ['2020-02-01']}},
    {'last_date': '2020-01-31', 'users': {'U1': ['2020-01-30', '2020-01-30']}},
    {'last_date': '2020-01-31', 'users': {'U1': ['2020-01-31', '2020-01-30']}},
    {'last_date': '2020-01-31', 'users': {' U1 ': []}},
    {'last_date': '2020-01-31', 'users': {'U1': ['20200130']}},
    {'last_date': '2020-01-31', 'users': []},
])
def test_invalid_history(history):
    with pytest.raises(ValueError):
        route_days([row('U1', '2020-02-01')], fit_group_members(train_fixture()), history, RoutingConfig())


def test_history_train_overlap_and_invalid_membership():
    train = train_fixture()
    with pytest.raises(ValueError, match='precede'):
        init_routing_history(train, '2020-01-30', RoutingConfig())
    history = init_routing_history(train, '2020-02-01', RoutingConfig())
    for members in ({'role': {}}, {'role': {}, 'department': {'Dev': ['U1']}},
                    {'role': {}, 'department': {'Dev': {'U1', ' U1 '}}}):
        with pytest.raises(ValueError):
            route_days([row('U1', '2020-02-01')], members, history, RoutingConfig())
