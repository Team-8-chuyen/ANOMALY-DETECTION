from copy import deepcopy
from datetime import date, timedelta

import pytest

from itd.scoring import profile_scoring as module
from itd.scoring.profile_scoring import init_profile_state, score_profile_days
from itd.scoring.score_input import attach_selected_scores
from itd.scoring.score_reference import fit_score_references, fuse_raw_scores
from test_score_reference import raw, score_config, train_rows


def setup(mode='natural', start='2010-01-11', train=None):
    config = score_config()
    train = train_rows() if train is None else train
    refs = fit_score_references(train, config)
    state = init_profile_state(train, start, mode, refs, config)
    return config, refs, state


def days(start, count, users=('U1',)):
    rows = []
    for offset in range(count):
        day = (date.fromisoformat(start) + timedelta(days=offset)).isoformat()
        rows.extend(raw(user, day, 20 + offset, 30 + offset,
                        'D2' if user == 'U3' else 'D1', 'R1' if user == 'U1' else 'R2')
                    for user in users)
    return rows


def test_natural_uses_personal_with_exact_shared_score_and_adapter_contract(monkeypatch):
    config, refs, state = setup()
    def forbidden(*args, **kwargs):
        raise AssertionError('Personal must not look up Group membership')
    monkeypatch.setattr(module, '_members_for_group', forbidden)
    tiers = []
    original = module._selected_reference
    def spy(*args, **kwargs):
        tiers.append(args[3])
        return original(*args, **kwargs)
    monkeypatch.setattr(module, '_selected_reference', spy)
    before = deepcopy(state)
    diagnostics, after = score_profile_days(days('2010-01-11', 1), refs, state, config)
    assert state == before
    assert tiers == ['personal']
    assert [row['selected_tier'] for row in diagnostics] == ['personal', 'personal']
    assert diagnostics[0]['score'] == diagnostics[1]['score']
    assert diagnostics[0]['n_personal_days'] == 10
    assert all(row['n_group_users'] is None for row in diagnostics)
    assert len(after['users']['U1']) == 11
    scores = [{name: row[name] for name in
               ('user', 'day', 'group_key', 'selected_tier', 'score')} for row in diagnostics]
    assert len(attach_selected_scores(diagnostics, scores)) == 2


def test_monthly_empty_profile_selects_department_group_and_role_global():
    config, refs, state = setup('monthly_reset')
    diagnostics, after = score_profile_days(days('2010-01-11', 1), refs, state, config)
    d, r = diagnostics
    assert (d['selected_tier'], r['selected_tier']) == ('group', 'global')
    assert d['n_group_users'] == 2 and r['n_group_users'] == 1
    assert all(row['cold_profile'] and row['n_personal_days'] == 0 for row in diagnostics)
    assert after['reset_period'] == '2010-01'
    assert len(after['users']['U1']) == 1
    assert not state['users']


def test_six_days_backoff_seven_days_personal_and_append_once_per_day():
    config, refs, state = setup('monthly_reset')
    rows = days('2010-01-11', 8, users=('U1', 'U2'))
    diagnostics, after = score_profile_days(list(reversed(rows)), refs, state, config)
    first_user = [row for row in diagnostics if row['user'] == 'U1' and row['group_key'] == 'department']
    assert [row['n_personal_days'] for row in first_user] == list(range(8))
    assert [row['selected_tier'] for row in first_user] == ['group'] * 7 + ['personal']
    assert len(after['users']['U1']) == len(after['users']['U2']) == 8
    assert all(row['n_personal_days'] == 0 for row in diagnostics if row['day'] == '2010-01-11')


def test_window_retains_exact_t_minus_30_excludes_t_minus_31_and_current_day():
    train = train_rows(start='2010-01-10', n_days=8)
    config, refs, state = setup(start='2010-02-10', train=train)
    diagnostics, _ = score_profile_days(days('2010-02-10', 1), refs, state, config)
    assert all(row['n_personal_days'] == 7 and row['selected_tier'] == 'personal'
               for row in diagnostics)
    config, refs, state = setup(start='2010-02-11', train=train)
    diagnostics, _ = score_profile_days(days('2010-02-11', 1), refs, state, config)
    assert diagnostics[0]['n_personal_days'] == 6
    assert diagnostics[0]['selected_tier'] == 'group'


def test_month_boundary_missing_day_one_resets_and_same_month_resume_does_not():
    config, refs, state = setup('monthly_reset')
    january, state = score_profile_days(days('2010-01-11', 8), refs, state, config)
    assert january[-1]['selected_tier'] == 'personal'
    february, state = score_profile_days(days('2010-02-02', 1), refs, state, config)
    assert all(row['n_personal_days'] == 0 for row in february)
    assert state['reset_period'] == '2010-02'
    assert [row['day'] for row in state['users']['U1']] == ['2010-02-02']
    next_day, state = score_profile_days(days('2010-02-03', 1), refs, state, config)
    assert all(row['n_personal_days'] == 1 for row in next_day)


def test_month_gap_and_year_boundary_reset():
    config, refs, state = setup('monthly_reset', start='2010-12-23',
                                train=train_rows(start='2010-12-15', n_days=8))
    _, state = score_profile_days(days('2010-12-23', 2), refs, state, config)
    diagnostics, state = score_profile_days(days('2011-02-04', 1), refs, state, config)
    assert diagnostics[0]['n_personal_days'] == 0
    assert state['reset_period'] == '2011-02'


@pytest.mark.parametrize('mode', ['natural', 'monthly_reset'])
def test_chunked_resume_matches_single_pass_and_uses_raw_history(mode):
    config, refs, state = setup(mode)
    rows = days('2010-01-11', 12)
    full, final = score_profile_days(rows, refs, state, config)
    left, middle = score_profile_days(rows[:4], refs, state, config)
    right, resumed = score_profile_days(rows[4:], refs, middle, config)
    assert full == left + right
    assert final == resumed
    assert all(set(entry) == {'day', 'e_feature_raw', 'e_sequence_raw'}
               for entry in final['users']['U1'])


def test_future_score_and_metadata_mutation_cannot_change_past_scores():
    config, refs, state = setup()
    rows = days('2010-01-11', 3)
    before, _ = score_profile_days(rows, refs, state, config)
    rows[-1].update(e_feature_raw=1e7, role='UNKNOWN', role_missing=True)
    after, _ = score_profile_days(rows, refs, state, config)
    assert before[:-2] == after[:-2]


def test_zero_iqr_personal_keeps_personal_instead_of_using_group():
    train = [raw('U1', f'2010-01-0{i}', 1, 2) for i in range(1, 8)]
    config, refs, state = setup(start='2010-01-08', train=train)
    diagnostics, _ = score_profile_days([raw('U1', '2010-01-08', 1, 2)], refs, state, config)
    assert all(row['selected_tier'] == 'personal' for row in diagnostics)
    assert all(row['reference_scale_floored'] for row in diagnostics)
    assert all(row['score'] == 0 for row in diagnostics)


@pytest.mark.parametrize('group,missing', [('UNKNOWN', True), ('UNSEEN', False)])
def test_global_fallback_is_retained_in_common_cold_cohort(group, missing):
    config, refs, state = setup('monthly_reset')
    row = raw('U4', '2010-01-11', 5, 7, group, group)
    diagnostics, _ = score_profile_days([row], refs, state, config)
    assert all(result['selected_tier'] == 'global' and result['cold_profile']
               for result in diagnostics)
    assert diagnostics[0]['score'] == diagnostics[1]['score']
    assert all(result['n_group_users'] == 0 for result in diagnostics)


def test_each_case_keeps_same_cold_cohort_even_with_different_fallbacks():
    config, refs, state = setup('monthly_reset')
    diagnostics, _ = score_profile_days(days('2010-01-11', 1, users=('U1', 'U3')), refs, state, config)
    cohorts = {case: {(row['user'], row['day']) for row in diagnostics
                      if row['group_key'] == case and row['cold_profile']}
               for case in ('department', 'role')}
    assert cohorts['department'] == cohorts['role'] == {('U1', '2010-01-11'), ('U3', '2010-01-11')}
    assert [row['selected_tier'] for row in diagnostics] == ['group', 'global', 'global', 'group']


@pytest.mark.parametrize('selected', ['group', 'global'])
def test_missing_selected_reference_is_error_never_fallback(selected):
    config, refs, state = setup('monthly_reset')
    if selected == 'group':
        del refs['groups']['department']['D1']
    else:
        del refs['global']
    # Init again binds this malformed artifact; scoring still rejects its selected reference.
    state = init_profile_state(train_rows(), '2010-01-11', 'monthly_reset', refs, config)
    with pytest.raises(ValueError, match='reference'):
        score_profile_days(days('2010-01-11', 1), refs, state, config)
    assert state['users'] == {}


@pytest.mark.parametrize('mutate', [
    lambda s: s['users']['U1'][0].pop('e_feature_raw'),
    lambda s: s['users']['U1'][0].update(e_sequence_raw=True),
    lambda s: s['users']['U1'][0].update(day='2010-01-12'),
    lambda s: s['users']['U1'].append(deepcopy(s['users']['U1'][0])),
    lambda s: s.update(reference_fingerprint='wrong'),
    lambda s: s.update(format_version=True),
    lambda s: s.update(reset_period='2010-01'),
    lambda s: s.update(last_processed_day='2010-01-11'),
])
def test_invalid_or_replayed_history_rejected_without_mutating(mutate):
    config, refs, state = setup()
    mutate(state)
    before = deepcopy(state)
    with pytest.raises(ValueError):
        score_profile_days(days('2010-01-11', 1), refs, state, config)
    assert state == before


def test_monthly_reset_rejects_wrong_cursor_and_pre_reset_entries():
    config, refs, state = setup('monthly_reset')
    _, state = score_profile_days(days('2010-01-11', 1), refs, state, config)
    state['reset_period'] = '2009-12'
    with pytest.raises(ValueError, match='cursor'):
        score_profile_days(days('2010-01-12', 1), refs, state, config)


def test_monthly_reset_rejects_lost_cursor_after_evaluation_even_if_history_empty():
    config, refs, state = setup('monthly_reset')
    _, state = score_profile_days(days('2010-01-11', 1), refs, state, config)
    state.update(reset_period=None, users={})
    with pytest.raises(ValueError, match='cursor'):
        score_profile_days(days('2010-01-12', 1), refs, state, config)


@pytest.mark.parametrize('field,value', [('e_feature_raw', 900.0), ('department', 'OTHER')])
def test_same_keys_with_changed_train_values_or_metadata_cannot_initialize(field, value):
    config, refs, _ = setup()
    train = train_rows()
    train[0][field] = value
    with pytest.raises(ValueError, match='coverage'):
        init_profile_state(train, '2010-01-11', 'natural', refs, config)


def test_train_overlap_and_reference_wrong_cohort_rejected_at_initialization():
    config, refs, _ = setup()
    with pytest.raises(ValueError, match='precede'):
        init_profile_state(train_rows(), '2010-01-10', 'natural', refs, config)
    with pytest.raises(ValueError, match='coverage'):
        init_profile_state(train_rows()[:-1], '2010-01-11', 'natural', refs, config)


def test_final_score_is_standardized_against_fused_personal_not_previous_tier_scores():
    config, refs, state = setup()
    row = raw('U1', '2010-01-11', 0, 0)
    diagnostics, _ = score_profile_days([row], refs, state, config)
    reference_values = [fuse_raw_scores(entry, refs)['fused_score']
                        for entry in state['users']['U1']]
    import numpy as np
    q25, median, q75 = np.quantile(reference_values, [.25, .5, .75], method='linear')
    expected = (fuse_raw_scores(row, refs)['fused_score'] - median) / max(q75 - q25, 1e-6)
    assert diagnostics[0]['score'] == expected
    assert diagnostics[0]['score'] < 0
