from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json

import numpy as np
import pytest

from itd.scoring.score_reference import (
    fit_score_references, fuse_raw_scores, ordered_keys_sha256, references_fingerprint,
    robust_reference, validate_raw_rows,
)


def score_config():
    return {
        'fusion': {'feature_weight': 0.5, 'sequence_weight': 0.5},
        'normalization': {'method': 'median_iqr', 'quantile_method': 'linear',
                          'epsilon': 1e-6, 'keep_signed': True},
        'routing': {'window_days': 30, 'min_personal_days': 7, 'min_group_users': 2},
        'modes': ['natural', 'monthly_reset'], 'reset': {'calendar': 'gregorian'},
    }


def raw(user='U1', day='2010-01-01', feature=1.0, sequence=2.0,
        department='D1', role='R1'):
    return {'user': user, 'day': day, 'e_feature_raw': feature, 'e_sequence_raw': sequence,
            'department': department, 'role': role, 'department_missing': department == 'UNKNOWN',
            'role_missing': role == 'UNKNOWN', 'ldap_month': day[:7]}


def train_rows(start='2010-01-01', n_days=10):
    result = []
    for offset in range(n_days):
        day = (date.fromisoformat(start) + timedelta(days=offset)).isoformat()
        result.extend([
            raw('U1', day, offset + 1, 2 * offset + 1, 'D1', 'R1'),
            raw('U2', day, offset + 3, 3 * offset + 2, 'D1', 'R2'),
            raw('U3', day, offset + 7, offset + 4, 'D2', 'R2'),
        ])
    return result


def test_linear_quantiles_signed_fusion_and_final_reference_manual():
    config = score_config()
    rows = [raw('U1', f'2010-01-0{i+1}', float(i), 10.0 * i) for i in range(4)]
    refs = fit_score_references(rows, config)
    assert refs['branches']['feature'] == {
        'n_rows': 4, 'median': 1.5, 'q25': 0.75, 'q75': 2.25,
        'iqr': 1.5, 'scale': 1.5, 'scale_floored': False}
    assert refs['branches']['sequence']['median'] == 15.0
    assert refs['branches']['sequence']['iqr'] == 15.0
    # Both standardized branches equal -1 at the first observation; no positive clipping.
    assert fuse_raw_scores(rows[0], refs) == {
        'z_feature': -1.0, 'z_sequence': -1.0, 'fused_score': -1.0}
    assert refs['global']['median'] == 0.0
    assert refs['global']['iqr'] == 1.0


def test_tied_reference_uses_epsilon_and_is_finite():
    reference = robust_reference([4.0] * 7, 1e-6)
    assert reference['iqr'] == 0.0
    assert reference['scale'] == 1e-6
    assert reference['scale_floored'] is True
    refs = fit_score_references([raw(feature=4.0, sequence=9.0)], score_config())
    assert fuse_raw_scores(raw(feature=4.0, sequence=9.0), refs)['fused_score'] == 0
    assert fuse_raw_scores(raw(feature=5.0, sequence=10.0), refs)['fused_score'] == 1e6


def test_group_membership_and_score_distribution_share_exact_train_rows():
    config = score_config()
    rows = train_rows(n_days=3)
    rows.append(raw('U4', '2010-01-04', 20, 10, 'UNKNOWN', 'UNKNOWN'))
    refs = fit_score_references(rows, config)
    assert refs['n_train_rows'] == refs['global']['n_rows'] == 10
    assert refs['group_members'] == {
        'department': {'D1': ['U1', 'U2'], 'D2': ['U3']},
        'role': {'R1': ['U1'], 'R2': ['U2', 'U3']}}
    d1 = [row for row in rows if row['department'] == 'D1']
    expected_values = [fuse_raw_scores(row, refs)['fused_score'] for row in d1]
    expected = robust_reference(expected_values, 1e-6)
    assert refs['groups']['department']['D1'] == {
        **expected, 'n_distinct_users': 2, 'keys_sha256': ordered_keys_sha256(d1)}
    assert 'UNKNOWN' not in refs['groups']['department']


def test_train_reference_is_not_affected_by_evaluation_and_does_not_mutate():
    rows, config = train_rows(), score_config()
    before = deepcopy(rows)
    refs = fit_score_references(rows, config)
    evaluation = raw('U9', '2010-01-11', feature=1e9, sequence=-1e9)
    fuse_raw_scores(evaluation, refs)
    assert refs == fit_score_references(rows, config)
    assert rows == before


def test_each_train_day_weighted_once_including_group_change():
    rows = [raw('U1', '2010-01-01', 0, 0, 'D1', 'R1'),
            raw('U1', '2010-02-01', 10, 10, 'D2', 'R2'),
            raw('U2', '2010-02-02', 20, 20, 'D2', 'R2')]
    refs = fit_score_references(rows, score_config())
    assert refs['group_members']['department'] == {'D1': ['U1'], 'D2': ['U1', 'U2']}
    assert refs['groups']['department']['D1']['n_rows'] == 1
    assert refs['groups']['department']['D2']['n_rows'] == 2
    assert refs['branches']['feature']['median'] == 10


def test_ordered_key_checksum_is_versioned_jsonl_and_order_independent():
    rows = [{'user': ' Ué ', 'day': '2010-01-02'}, {'user': 'U1', 'day': '2010-01-01'}]
    text = ''.join(json.dumps(key, ensure_ascii=False, separators=(',', ':')) + '\n'
                   for key in [['2010-01-01', 'U1'], ['2010-01-02', 'Ué']])
    assert ordered_keys_sha256(rows) == hashlib.sha256(text.encode('utf-8')).hexdigest()
    assert ordered_keys_sha256(list(reversed(rows))) == ordered_keys_sha256(rows)
    assert ordered_keys_sha256([]) == hashlib.sha256(b'').hexdigest()


def test_reference_fingerprint_binds_producer_and_excludes_operational_paths():
    config = score_config()
    refs = fit_score_references(train_rows(), config)
    a = references_fingerprint(refs, config)
    config.update(export_run_dir='runs/another', producer_run_dir='runs/source')
    assert references_fingerprint(refs, config) == a
    refs['producer_identity'] = {'file_sha256': {'lstm_model.pt': 'A' * 64}}
    assert references_fingerprint(refs, config) != a


@pytest.mark.parametrize('field,value', [
    ('e_feature_raw', None), ('e_feature_raw', True), ('e_sequence_raw', np.nan),
    ('e_sequence_raw', np.inf), ('day', '2010-01-01T00:00:00'),
    ('day', '20100101'), ('user', ''), ('role', ''), ('role_missing', 0),
    ('role_missing', True), ('ldap_month', '2010-02')])
def test_invalid_raw_records_rejected(field, value):
    row = raw()
    row[field] = value
    with pytest.raises(ValueError):
        validate_raw_rows([row])


def test_raw_validation_copies_normalizes_and_rejects_duplicate_user_day():
    row = raw(user=' U1 ', role=' R1 ')
    actual = validate_raw_rows([row])
    assert actual[0]['user'] == 'U1' and actual[0]['role'] == 'R1'
    assert row['user'] == ' U1 '
    with pytest.raises(ValueError, match='duplicate'):
        validate_raw_rows([row, raw()])


@pytest.mark.parametrize('values,epsilon', [([], 1e-6), ([True], 1e-6),
    ([np.inf], 1e-6), ([1], 0), ([1], -1), ([1], True), ([1], np.nan)])
def test_robust_reference_rejects_invalid_values(values, epsilon):
    with pytest.raises(ValueError):
        robust_reference(values, epsilon)


@pytest.mark.parametrize('section,name,value', [
    ('fusion', 'feature_weight', 1.0), ('normalization', 'epsilon', 1.0),
    ('normalization', 'keep_signed', 1), ('normalization', 'method', 'mean_std'),
    ('routing', 'min_personal_days', True), ('routing', 'min_group_users', 3)])
def test_changed_scientific_config_is_not_silently_accepted(section, name, value):
    config = score_config()
    config[section][name] = value
    with pytest.raises(ValueError, match='SPEC-005'):
        fit_score_references([raw()], config)


def test_invalid_selected_branch_reference_stops_scoring():
    refs = fit_score_references(train_rows(), score_config())
    refs['branches']['feature']['scale'] = 0
    with pytest.raises(ValueError, match='scale'):
        fuse_raw_scores(raw(), refs)


def test_reference_embedded_config_enforces_bool_type_and_frozen_fusion():
    config = score_config()
    refs = fit_score_references(train_rows(), config)
    refs['scientific_config']['normalization']['keep_signed'] = 1
    with pytest.raises(ValueError, match='keep_signed'):
        references_fingerprint(refs, config)
    with pytest.raises(ValueError, match='keep_signed'):
        fuse_raw_scores(raw(), refs)
