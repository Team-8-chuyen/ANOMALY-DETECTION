"""Synthetic paired source rows; no CERT records or labels are embedded here."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from itd.data.feature_preprocessing import FEATURE_FIELDS, MASK_FIELDS
from itd.data.sequence_dataset import (SequenceDay, SEQUENCE_FIELDS, CATEGORICAL_FIELDS,
                                       BOOLEAN_FIELDS)


def metadata(day: str = '2010-01-02', role: str = 'Engineer', department: str = 'Research') -> dict:
    return {'role': role, 'department': department, 'role_missing': role == 'UNKNOWN',
            'department_missing': department == 'UNKNOWN', 'ldap_month': day[:7]}


def feature_row(user: str = 'U1', day: str = '2010-01-02', value: float = 1.0) -> dict:
    row = {'user': user, 'day': datetime.fromisoformat(day), **metadata(day)}
    row.update({field: float(value) for field in FEATURE_FIELDS})
    row.update({field: True for field in MASK_FIELDS})
    return row


def sequence_row(user: str = 'U1', day: str = '2010-01-02', index: int = 0,
                 value: float = 1.0) -> dict:
    row = {'user': user, 'day': datetime.fromisoformat(day), 'event_index': index,
           'attribute_mask': json.dumps([True] * 24), **metadata(day)}
    for field in SEQUENCE_FIELDS:
        row[field] = (int(index % 3) if field == 'gap_bucket' else 'sample'
                      if field in CATEGORICAL_FIELDS else bool(index % 2)
                      if field in BOOLEAN_FIELDS else float(value))
    return row


def sequence_day(user: str = 'U1', day: str = '2010-01-02', length: int = 3) -> SequenceDay:
    return SequenceDay(user, day, [sequence_row(user, day, i, float(i + 1)) for i in range(length)],
                       metadata(day))


def write_pilot_fixture(root: Path, feature_rows: list[dict] | None = None,
                        sequence_rows: list[dict] | None = None,
                        seed: int = 0, max_users: int = 20) -> dict:
    if feature_rows is None:
        feature_rows = [feature_row(user, day, value=float(i + 1))
                        for i, user in enumerate(('U1', 'U2', 'U3'))
                        for day in ('2010-01-02', '2010-01-10', '2010-01-23')]
    if sequence_rows is None:
        sequence_rows = [sequence_row(row['user'], row['day'].date().isoformat(), i, float(i + 1))
                         for row in feature_rows for i in range(3)]
    paths = {}
    for branch, rows, template in [('feature', feature_rows, feature_row()),
                                    ('sequence', sequence_rows, sequence_row())]:
        directory = root / branch
        directory.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pylist(rows or [template])
        table = table.set_column(table.schema.get_field_index('day'), 'day',
                                 table.column('day').cast(pa.timestamp('ns')))
        if not rows:
            table = table.slice(0, 0)
        # Alternate rows force sequence-day assembly across file boundaries.
        for part in range(2):
            indices = pa.array(list(range(part, len(table), 2)), type=pa.int64())
            pq.write_table(table.take(indices), directory / f'part-{part}.parquet')
        paths[f'{branch}_dir'] = str(directory)
    return {'paths': paths,
            'split': {'fit_start': '2010-01-02', 'fit_end': '2010-01-22',
                      'validation_start': '2010-01-23', 'validation_end': '2010-01-31'},
            'data': {'seed': seed, 'max_users': max_users, 'batch_rows': 2, 'window_length': 128}}
