from copy import deepcopy
from datetime import date

import numpy as np
import pytest

from itd.scoring.score_input import attach_selected_scores


def paired_routes(tiers=('personal', 'personal')):
    # Reverse lexical case order to prove output follows caller order, not score order.
    return [
        {'user': ' U1 ', 'day': '2020-02-01', 'group_key': case, 'selected_tier': tier,
         'fallback_reason': 'fixture', 'n_personal_days': 7, 'n_group_users': None,
         'group_value': 'Example', 'score': None, 'score_status': 'awaiting_external_score'}
        for case, tier in zip(('role', 'department'), tiers)
    ]


def selected_scores(routes, values=(1.25, 1.25)):
    return [
        {'user': row['user'].strip(), 'day': row['day'], 'group_key': row['group_key'],
         'selected_tier': row['selected_tier'], 'score': value}
        for row, value in zip(routes, values)
    ]


@pytest.mark.parametrize('value', [0, -2, 0.0, -0.0, -2.75, 4.5, np.float32(-1.5), np.float64(3.25), np.int64(2)])
def test_passthrough_preserves_values_order_fields_and_inputs(value):
    routes = paired_routes()
    routes[0]['details'] = {'notes': ['original']}
    scores = list(reversed(selected_scores(routes, (value, value))))
    before_routes, before_scores = deepcopy(routes), deepcopy(scores)
    output = attach_selected_scores(routes, scores)
    assert output is not routes and all(a is not b for a, b in zip(output, routes))
    assert [row['group_key'] for row in output] == ['role', 'department']
    assert [row['user'] for row in output] == [' U1 ', ' U1 ']
    assert all(row['score'] is value for row in output)
    assert all(row['score_status'] == 'provided' for row in output)
    for old, new in zip(before_routes, output):
        assert {k: v for k, v in new.items() if k not in {'score', 'score_status'}} == {
            k: v for k, v in old.items() if k not in {'score', 'score_status'}}
    assert routes == before_routes and scores == before_scores
    output[0]['details']['notes'].append('new')
    assert routes[0]['details']['notes'] == ['original']


@pytest.mark.parametrize('value', [True, False, np.bool_(True), None, '', '1.5', complex(1, 0),
                                  float('nan'), float('inf'), -float('inf')])
def test_rejects_non_real_nonfinite_bool_or_null_scores(value):
    routes = paired_routes()
    scores = selected_scores(routes, (value, value))
    with pytest.raises(ValueError, match='score'):
        attach_selected_scores(routes, scores)
    assert all(row['score'] is None for row in routes)


@pytest.mark.parametrize('kind', ['missing', 'empty', 'extra', 'duplicate', 'normalized_duplicate', 'wrong_tier',
                                  'extra_column', 'missing_column', 'not_dict', 'wrong_user', 'wrong_case'])
def test_rejects_invalid_score_coverage_and_schema_without_rerouting(kind):
    routes = paired_routes()
    before = deepcopy(routes)
    scores = selected_scores(routes)
    if kind == 'missing':
        scores.pop()
    elif kind == 'empty':
        scores = []
    elif kind == 'extra':
        scores.append({**scores[0], 'day': '2020-02-02'})
    elif kind == 'duplicate':
        scores.append(dict(scores[0]))
    elif kind == 'normalized_duplicate':
        scores.append({**scores[0], 'user': ' U1 '})
    elif kind == 'wrong_tier':
        scores[0]['selected_tier'] = 'group'
    elif kind == 'extra_column':
        scores[0]['threshold'] = 0
    elif kind == 'missing_column':
        del scores[0]['score']
    elif kind == 'not_dict':
        scores[0] = []
    elif kind == 'wrong_user':
        scores[0]['user'] = 'U2'
    else:
        scores[0]['group_key'] = 'team'
    with pytest.raises(ValueError):
        attach_selected_scores(routes, scores)
    assert routes == before


@pytest.mark.parametrize('field,value', [
    ('user', ''), ('user', '  '), ('user', None), ('user', 7),
    ('day', '20200201'), ('day', '2020-2-1'), ('day', '2020-02-30'),
    ('day', '2020-02-01T00:00:00'), ('day', date(2020, 2, 1)), ('day', None),
    ('group_key', 'Department'), ('group_key', None), ('group_key', []),
    ('selected_tier', 'unknown'), ('selected_tier', None), ('selected_tier', []),
])
@pytest.mark.parametrize('source', ['routes', 'scores'])
def test_rejects_invalid_identifiers_or_tier(source, field, value):
    routes = paired_routes()
    scores = selected_scores(routes)
    target = routes if source == 'routes' else scores
    target[0][field] = value
    with pytest.raises(ValueError):
        attach_selected_scores(routes, scores)


@pytest.mark.parametrize('kind', ['duplicate', 'normalized_duplicate', 'incomplete_pair', 'empty', 'not_list', 'bad_row'])
def test_rejects_invalid_route_pairs(kind):
    routes = paired_routes()
    scores = selected_scores(routes)
    if kind == 'duplicate':
        routes.append(dict(routes[0]))
    elif kind == 'normalized_duplicate':
        routes.append({**routes[0], 'user': 'U1'})
    elif kind == 'incomplete_pair':
        routes.pop()
    elif kind == 'empty':
        routes = []
    elif kind == 'not_list':
        routes = tuple(routes)
    else:
        routes[0] = None
    with pytest.raises(ValueError):
        attach_selected_scores(routes, scores)


@pytest.mark.parametrize('tier', ['personal', 'global'])
def test_shared_personal_and_global_scores_must_match(tier):
    routes = paired_routes((tier, tier))
    with pytest.raises(ValueError, match='differ'):
        attach_selected_scores(routes, selected_scores(routes, (-1.0, 2.0)))
    # Equality is exact: do not silently introduce a tolerance/score transformation.
    with pytest.raises(ValueError, match='differ'):
        attach_selected_scores(routes, selected_scores(routes, (1.0, np.nextafter(1.0, 2.0))))


@pytest.mark.parametrize('tiers', [('group', 'group'), ('personal', 'group'), ('global', 'group'), ('personal', 'global')])
def test_group_or_different_selected_tiers_can_have_different_scores(tiers):
    routes = paired_routes(tiers)
    output = attach_selected_scores(routes, selected_scores(routes, (-4.0, 2.0)))
    assert [row['score'] for row in output] == [-4.0, 2.0]
    assert [row['selected_tier'] for row in output] == list(tiers)


def test_pair_checks_are_per_user_day_not_across_different_days_or_users():
    first = paired_routes()
    next_day = [{**r, 'day': '2020-02-02'} for r in paired_routes()]
    other_user = [{**r, 'user': 'U2'} for r in paired_routes(('global', 'global'))]
    routes = first + next_day + other_user
    scores = selected_scores(first, (1.0, 1.0)) + selected_scores(next_day, (2.0, 2.0)) + selected_scores(other_user, (-3.0, -3.0))
    assert [r['score'] for r in attach_selected_scores(routes, list(reversed(scores)))] == [1., 1., 2., 2., -3., -3.]
