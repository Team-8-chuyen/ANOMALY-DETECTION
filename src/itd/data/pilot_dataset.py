"""Read paired January pilot rows without fitting on future data (SPEC-004 section 4.1)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from .feature_preprocessing import FEATURE_FIELDS, MASK_FIELDS, _feature_cells
from .sequence_dataset import (SequenceDay, SEQUENCE_FIELDS, CATEGORICAL_FIELDS,
                               BOOLEAN_FIELDS)
from .sequence_preprocessing import validated_sequence_row

ROOT = Path(__file__).resolve().parents[3]
METADATA_FIELDS = ('role', 'department', 'role_missing', 'department_missing', 'ldap_month')


@dataclass
class PilotData:
    fit_features: list[dict]
    validation_features: list[dict]
    fit_days: list[SequenceDay]
    validation_days: list[SequenceDay]
    cohort: list[str]
    provenance: dict


def _user(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('user must be a nonempty string')
    return value.strip()


def _day(value: object) -> str:
    if not isinstance(value, datetime) or value.tzinfo is not None or value.time() != time(0):
        raise ValueError('day must be a timezone-naive midnight timestamp')
    return value.date().isoformat()


def _date(value: object) -> date:
    if not isinstance(value, str):
        raise ValueError('split dates must use YYYY-MM-DD')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError('split dates must use YYYY-MM-DD') from error
    if parsed.isoformat() != value:
        raise ValueError('split dates must use YYYY-MM-DD')
    return parsed


def select_pilot_users(users, seed: int, max_users: int) -> list[str]:
    if type(seed) is not int or seed < 0:
        raise ValueError('seed must be a nonnegative integer')
    if type(max_users) is not int or not 1 <= max_users <= 20:
        raise ValueError('max_users must be an integer in [1, 20]')
    if isinstance(users, (str, bytes)):
        raise ValueError('users must be an iterable of identifiers, not one string')
    try:
        candidates = {_user(user) for user in users}
    except TypeError as error:
        raise ValueError('users must be an iterable of user identifiers') from error
    if not candidates:
        raise ValueError('no eligible fit users')
    return sorted(candidates, key=lambda user: (
        hashlib.sha256(f'{seed}|{user}'.encode('utf-8')).hexdigest(), user))[:max_users]


def _schema(branch: str) -> dict[str, pa.DataType]:
    fields = {'user': pa.string(), 'day': pa.timestamp('ns'),
              'role': pa.string(), 'department': pa.string(),
              'role_missing': pa.bool_(), 'department_missing': pa.bool_(),
              'ldap_month': pa.string()}
    if branch == 'feature':
        fields.update({field: pa.float64() for field in FEATURE_FIELDS})
        fields.update({field: pa.bool_() for field in MASK_FIELDS})
    else:
        fields['event_index'] = pa.int64()
        fields['attribute_mask'] = pa.string()
        for field in SEQUENCE_FIELDS:
            fields[field] = (pa.int64() if field == 'gap_bucket' else pa.string()
                             if field in CATEGORICAL_FIELDS else pa.bool_()
                             if field in BOOLEAN_FIELDS else pa.float64())
    return fields


def _open_dataset(value: object, branch: str):
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ValueError(f'{branch} path must be nonempty')
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    files = sorted(path.rglob('*.parquet')) if path.is_dir() else []
    if not files:
        raise ValueError(f'{path}: no {branch} Parquet files')
    expected = _schema(branch)
    for source in files:
        schema = pq.read_schema(source)
        for name, datatype in expected.items():
            if name not in schema.names or schema.field(name).type != datatype:
                raise ValueError(f'{source}: missing or incompatible {name}; expected {datatype}')
    return ds.dataset([str(file) for file in files], format='parquet'), files


def _filter(start: date, end: date, cohort: list[str] | None = None):
    expression = ((ds.field('day') >= datetime.combine(start, time(0)))
                  & (ds.field('day') < datetime.combine(end + timedelta(days=1), time(0))))
    if cohort is not None:
        expression &= pc.utf8_trim_whitespace(ds.field('user')).isin(cohort)
    return expression


def _records(dataset, columns: list[str], expression, batch_rows: int):
    scanner = dataset.scanner(columns=columns, filter=expression, batch_size=batch_rows,
                              use_threads=False)
    for tagged in scanner.scan_batches():
        batch = tagged.record_batch
        path = tagged.fragment.path
        # Check nanosecond precision before converting Arrow timestamps to Python.
        days = batch.column(batch.schema.get_field_index('day'))
        valid_days = pc.and_(pc.is_valid(days), pc.equal(days, pc.floor_temporal(days, unit='day')))
        if len(days) and not bool(pc.all(pc.fill_null(valid_days, False)).as_py()):
            raise ValueError(f'{path}: day must contain valid midnight timestamps')
        for row in batch.to_pylist():
            row['__source_file__'] = path
            yield row


def _key(row: dict) -> tuple[str, str]:
    return _user(row['user']), _day(row['day'])


def _key_set(dataset, expression, batch_rows: int, unique: bool) -> set[tuple[str, str]]:
    keys = set()
    for row in _records(dataset, ['user', 'day'], expression, batch_rows):
        try:
            key = _key(row)
        except ValueError as error:
            raise ValueError(f"{row['__source_file__']}: {error}") from error
        if unique and key in keys:
            raise ValueError(f"{row['__source_file__']}: duplicate feature user-day {key}")
        keys.add(key)
    return keys


def _metadata(row: dict, day: str) -> dict:
    result = {}
    for field in ('role', 'department'):
        value = row[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{field}: LDAP value must be nonempty')
        value = value.strip()
        missing = row[f'{field}_missing']
        if type(missing) is not bool or missing != (value == 'UNKNOWN'):
            raise ValueError(f'{field}_missing: inconsistent LDAP flag')
        result[field] = value
        result[f'{field}_missing'] = missing
    if row['ldap_month'] != day[:7]:
        raise ValueError('ldap_month must equal the user-day month')
    result['ldap_month'] = row['ldap_month']
    return result


def _read_features(dataset, expression, batch_rows: int) -> dict[tuple[str, str], dict]:
    records = {}
    for row in _records(dataset, list(_schema('feature')), expression, batch_rows):
        try:
            user, day = _key(row)
            key = (user, day)
            if key in records:
                raise ValueError('duplicate feature user-day')
            metadata = _metadata(row, day)
            _feature_cells(row)
            row.update({'user': user, 'day': day, **metadata})
            records[key] = row
        except ValueError as error:
            raise ValueError(f"{row['__source_file__']} user/day={row.get('user')}/{row.get('day')}: {error}") from error
    return records


def _read_sequences(dataset, expression, batch_rows: int) -> dict[tuple[str, str], SequenceDay]:
    grouped: dict[tuple[str, str], SequenceDay] = {}
    for row in _records(dataset, list(_schema('sequence')), expression, batch_rows):
        try:
            user, day = _key(row)
            key = (user, day)
            index = row['event_index']
            if type(index) is not int or index < 0:
                raise ValueError('event_index must be a nonnegative integer')
            metadata = _metadata(row, day)
            validated_sequence_row(row)
            row.update({'user': user, 'day': day, **metadata})
            if key not in grouped:
                grouped[key] = SequenceDay(user, day, [], metadata)
            if grouped[key].metadata != metadata:
                raise ValueError('inconsistent LDAP metadata within sequence day')
            grouped[key].rows.append(row)
        except ValueError as error:
            raise ValueError(f"{row['__source_file__']} user/day={row.get('user')}/{row.get('day')}: {error}") from error
    for key, day in grouped.items():
        day.rows.sort(key=lambda row: row['event_index'])
        if [row['event_index'] for row in day.rows] != list(range(len(day.rows))):
            raise ValueError(f'{key}: event_index must start at zero and be contiguous without duplicates')
    return grouped


def _fingerprint(keys) -> str:
    text = json.dumps(sorted(keys), ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_pilot_data(config: dict) -> PilotData:
    """Project keys first, then materialize values only for the fixed fit cohort."""
    try:
        split = config['split']
        fit_start, fit_end = _date(split['fit_start']), _date(split['fit_end'])
        val_start, val_end = _date(split['validation_start']), _date(split['validation_end'])
        data = config['data']
        batch_rows = data['batch_rows']
        if type(batch_rows) is not int or batch_rows < 1:
            raise ValueError('batch_rows must be a positive integer')
        if not fit_start <= fit_end < val_start <= val_end:
            raise ValueError('fit/validation dates must be ordered and disjoint')
        if any(day.year != 2010 or day.month != 1 for day in (fit_start, fit_end, val_start, val_end)):
            raise ValueError('this pilot is restricted to January 2010')
        feature_ds, feature_files = _open_dataset(config['paths']['feature_dir'], 'feature')
        sequence_ds, sequence_files = _open_dataset(config['paths']['sequence_dir'], 'sequence')
    except (KeyError, TypeError) as error:
        raise ValueError('missing or invalid pilot data configuration') from error
    all_fit_feature_keys = _key_set(feature_ds, _filter(fit_start, fit_end), batch_rows, unique=True)
    all_fit_sequence_keys = _key_set(sequence_ds, _filter(fit_start, fit_end), batch_rows, unique=False)
    if all_fit_feature_keys != all_fit_sequence_keys:
        raise ValueError('fit feature and sequence user-day keys do not match')
    cohort = select_pilot_users((key[0] for key in all_fit_feature_keys), data['seed'], data['max_users'])
    fit_filter, validation_filter = _filter(fit_start, fit_end, cohort), _filter(val_start, val_end, cohort)
    fit_features = _read_features(feature_ds, fit_filter, batch_rows)
    validation_features = _read_features(feature_ds, validation_filter, batch_rows)
    fit_sequences = _read_sequences(sequence_ds, fit_filter, batch_rows)
    validation_sequences = _read_sequences(sequence_ds, validation_filter, batch_rows)
    expected_fit_keys = {key for key in all_fit_feature_keys if key[0] in cohort}
    if set(fit_features) != expected_fit_keys:
        raise ValueError('selected fit user-days were lost during materialization')
    for phase, features, sequences in [('fit', fit_features, fit_sequences),
                                       ('validation', validation_features, validation_sequences)]:
        if set(features) != set(sequences):
            raise ValueError(f'{phase} feature and sequence user-day keys do not match')
        for key, day in sequences.items():
            if day.metadata != {field: features[key][field] for field in METADATA_FIELDS}:
                raise ValueError(f'{phase} {key}: LDAP metadata differ between feature and sequence')
    if not fit_features or not validation_features:
        raise ValueError('pilot requires nonempty fit and validation user-days')
    sort_key = lambda key: (key[1], key[0])
    fit_order, validation_order = sorted(fit_features, key=sort_key), sorted(validation_features, key=sort_key)
    fit_days = [fit_sequences[key] for key in fit_order]
    validation_days = [validation_sequences[key] for key in validation_order]
    provenance = {
        'input_files': {'feature': [str(p) for p in feature_files], 'sequence': [str(p) for p in sequence_files]},
        'all_fit_user_days': len(all_fit_feature_keys), 'all_fit_users': len({key[0] for key in all_fit_feature_keys}),
        'fit_feature_rows': len(fit_features), 'validation_feature_rows': len(validation_features),
        'fit_sequence_rows': sum(len(day.rows) for day in fit_days),
        'validation_sequence_rows': sum(len(day.rows) for day in validation_days),
        'fit_keys_sha256': _fingerprint(fit_order), 'validation_keys_sha256': _fingerprint(validation_order),
        'missing_validation_users': sorted(set(cohort) - {key[0] for key in validation_features}),
    }
    return PilotData([fit_features[key] for key in fit_order],
                     [validation_features[key] for key in validation_order],
                     fit_days, validation_days, cohort, provenance)
