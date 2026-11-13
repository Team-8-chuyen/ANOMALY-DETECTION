from copy import deepcopy
from datetime import datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from itd.data.pilot_dataset import load_pilot_data, select_pilot_users
from pilot_fixtures import feature_row, sequence_row, write_pilot_fixture


def test_cohort_order_is_seeded_hash_not_input_or_lexical_order():
    assert select_pilot_users(['C', 'A', 'D', 'B', 'B'], 0, 3) == ['B', 'A', 'D']
    assert select_pilot_users(['B', 'D', 'A', 'C'], 1, 3) == ['B', 'A', 'C']


@pytest.mark.parametrize('seed,limit', [(True, 3), (-1, 3), (0, 0), (0, 21), (0, True)])
def test_bad_cohort_configuration_is_rejected(seed, limit):
    with pytest.raises(ValueError):
        select_pilot_users(['A'], seed, limit)


def test_cohort_selection_rejects_single_string_and_empty_user_set():
    with pytest.raises(ValueError):
        select_pilot_users('ABC', 0, 2)
    with pytest.raises(ValueError):
        select_pilot_users([], 0, 2)


def test_paired_loading_orders_keys_and_assembles_days_across_files(tmp_path):
    config = write_pilot_fixture(tmp_path)
    data = load_pilot_data(config)
    assert data.cohort == ['U1', 'U2', 'U3']
    assert len(data.fit_features) == len(data.fit_days) == 6
    assert len(data.validation_features) == len(data.validation_days) == 3
    assert data.provenance['fit_sequence_rows'] == 18
    assert data.provenance['validation_sequence_rows'] == 9
    assert [(row['day'], row['user']) for row in data.fit_features] == sorted(
        (row['day'], row['user']) for row in data.fit_features)
    assert all([row['event_index'] for row in day.rows] == [0, 1, 2] for day in data.fit_days)
    assert [day.day for day in data.validation_days] == ['2010-01-23'] * 3
    assert all(day.metadata['ldap_month'] == '2010-01' for day in data.fit_days)


def test_validation_or_future_payload_does_not_select_cohort(tmp_path):
    features = [feature_row(user, day) for user in ('U1', 'U2', 'U3')
                for day in ('2010-01-02', '2010-01-23')]
    features += [feature_row('VAL_ONLY', '2010-01-23'), feature_row('FUTURE', '2010-06-01')]
    features[-1]['f001'] = float('nan')
    sequences = [sequence_row(row['user'], row['day'].date().isoformat()) for row in features]
    sequences[-1]['attribute_mask'] = 'invalid future mask must never be parsed'
    config = write_pilot_fixture(tmp_path, features, sequences, max_users=2)
    data = load_pilot_data(config)
    assert data.cohort == ['U1', 'U2']
    assert len(data.fit_features) == len(data.validation_features) == 2
    assert all(row['user'] not in ('VAL_ONLY', 'FUTURE') for row in data.fit_features + data.validation_features)


def test_mismatch_fit_keys_is_not_silently_inner_joined(tmp_path):
    features = [feature_row('A'), feature_row('B'), feature_row('A', '2010-01-23')]
    sequences = [sequence_row('A'), sequence_row('A', '2010-01-23')]
    config = write_pilot_fixture(tmp_path, features, sequences, max_users=1)
    with pytest.raises(ValueError, match='fit feature and sequence.*keys'):
        load_pilot_data(config)


def test_mismatch_validation_keys_is_not_silently_inner_joined(tmp_path):
    features = [feature_row(), feature_row(day='2010-01-23')]
    sequences = [sequence_row()]
    config = write_pilot_fixture(tmp_path, features, sequences)
    with pytest.raises(ValueError, match='validation feature and sequence.*keys'):
        load_pilot_data(config)


def test_duplicate_feature_day_across_files_is_rejected(tmp_path):
    row = feature_row()
    config = write_pilot_fixture(tmp_path, [row, deepcopy(row), feature_row(day='2010-01-23')])
    with pytest.raises(ValueError, match='duplicate feature'):
        load_pilot_data(config)


@pytest.mark.parametrize('indices', [[0, 0], [0, 2], [1, 2]])
def test_sequence_indices_must_be_zero_based_contiguous_unique(tmp_path, indices):
    features = [feature_row(), feature_row(day='2010-01-23')]
    sequences = [sequence_row(index=i) for i in indices] + [sequence_row(day='2010-01-23')]
    config = write_pilot_fixture(tmp_path, features, sequences)
    with pytest.raises(ValueError, match='event_index'):
        load_pilot_data(config)


def test_ldap_metadata_cannot_differ_between_branches(tmp_path):
    features = [feature_row(), feature_row(day='2010-01-23')]
    features[0]['role'] = 'OtherRole'
    sequences = [sequence_row(), sequence_row(day='2010-01-23')]
    config = write_pilot_fixture(tmp_path, features, sequences)
    with pytest.raises(ValueError, match='LDAP metadata differ'):
        load_pilot_data(config)


def test_metadata_must_be_constant_within_user_day(tmp_path):
    features = [feature_row(), feature_row(day='2010-01-23')]
    sequences = [sequence_row(index=0), sequence_row(index=1), sequence_row(day='2010-01-23')]
    sequences[1]['department'] = 'OtherDept'
    config = write_pilot_fixture(tmp_path, features, sequences)
    with pytest.raises(ValueError, match='inconsistent LDAP metadata'):
        load_pilot_data(config)


@pytest.mark.parametrize('change', [{'ldap_month': '2010-02'}, {'role_missing': True}])
def test_month_and_missing_flags_are_validated(tmp_path, change):
    features = [feature_row(), feature_row(day='2010-01-23')]
    features[0].update(change)
    config = write_pilot_fixture(tmp_path, features)
    with pytest.raises(ValueError, match='ldap_month|role_missing'):
        load_pilot_data(config)


def test_nonmidnight_timestamp_is_rejected(tmp_path):
    features = [feature_row(), feature_row(day='2010-01-23')]
    features[0]['day'] = datetime(2010, 1, 2, 1)
    config = write_pilot_fixture(tmp_path, features)
    with pytest.raises(ValueError, match='midnight'):
        load_pilot_data(config)


def test_nanosecond_nonmidnight_timestamp_is_not_rounded_away(tmp_path):
    config = write_pilot_fixture(tmp_path)
    path = tmp_path / 'feature' / 'part-0.parquet'
    table = pq.read_table(path)
    values = table['day'].cast(pa.int64()).to_pylist()
    values[0] += 1
    table = table.set_column(table.schema.get_field_index('day'), 'day', pa.array(values, type=pa.timestamp('ns')))
    pq.write_table(table, path)
    with pytest.raises(ValueError, match='midnight'):
        load_pilot_data(config)


def test_source_schema_mismatch_is_rejected(tmp_path):
    config = write_pilot_fixture(tmp_path)
    path = tmp_path / 'feature' / 'part-0.parquet'
    table = pq.read_table(path).drop(['m100'])
    pq.write_table(table, path)
    with pytest.raises(ValueError, match='m100'):
        load_pilot_data(config)


@pytest.mark.parametrize('change', [{'validation_start': '2010-01-22'}, {'fit_start': '2009-12-31'},
                                   {'fit_end': '2010-01-01'}, {'fit_start': '20100102'}])
def test_invalid_or_outside_pilot_split_is_rejected(tmp_path, change):
    config = write_pilot_fixture(tmp_path)
    config['split'].update(change)
    with pytest.raises(ValueError):
        load_pilot_data(config)
