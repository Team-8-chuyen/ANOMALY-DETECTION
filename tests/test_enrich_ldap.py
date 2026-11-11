import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from itd.data.enrich_ldap import BRANCHES, SEQUENCE, enrich_batch, enrich_dataset, load_ldap_metadata


def feature_table(ocean=False):
    values = {'user': [' U1 ', 'U2', 'U1'],
              'day': pa.array([datetime(2020, 1, 31), datetime(2020, 1, 31), datetime(2020, 2, 1)], type=pa.timestamp('ns'))}
    values.update({f'f{i:03d}': pa.array([float(i), None if i == 2 else 0., float(i+1)], type=pa.float64()) for i in range(1, 101)})
    values.update({f'm{i:03d}': [True, False, True] for i in range(1, 101)})
    if ocean:
        values.update({name: [1, 2, 3] for name in 'OCEAN'})
    return pa.table(values).replace_schema_metadata({b'pandas': b'old metadata'})


def sequence_table():
    table = feature_table().select(['user', 'day']).take(pa.array([0, 0, 1, 2]))
    values = {'user': table['user'], 'day': table['day'], 'event_index': [0, 1, 0, 0]}
    strings = {'event_token', 'calendar_context', 'pc_context', 'file_extension_id', 'url_scheme_id', 'sender_context'}
    flags = {'extension_present', 'multi_dot', 'query_present', 'bcc_present'}
    values.update({name: ['FILE']*4 if name in strings else [True]*4 if name in flags
                   else [0]*4 if name == 'gap_bucket' else [0.5]*4 for name in SEQUENCE})
    values['attribute_mask'] = [json.dumps([True]*24)]*4
    return pa.table(values)


def setup(tmp_path):
    source, ldap, output = tmp_path/'input', tmp_path/'LDAP', tmp_path/'output'
    ldap.mkdir()
    (ldap/'2020-01.csv').write_text('user_id,role,department\nU1,Engineer,Dev\nU2,,Ops\n', encoding='utf-8')
    (ldap/'2020-02.csv').write_text('user_id,role,department\nU1,Manager,\n', encoding='utf-8')
    for branch in BRANCHES:
        directory = source/branch
        directory.mkdir(parents=True)
        table = sequence_table() if branch == 'user_day_sequences' else feature_table(branch.endswith('ocean'))
        pq.write_table(table, directory/'bucket-000.parquet')
    return {'paths': {'input_root': str(source), 'ldap_dir': str(ldap), 'output_root': str(output)},
            'branches': list(BRANCHES), 'batch_rows': 1, 'compression': 'zstd'}


def test_join_preserves_values_order_masks_f100_ocean_and_boundaries(tmp_path):
    config = setup(tmp_path)
    manifest = enrich_dataset(config)
    assert manifest['same_user_days_across_branches']
    assert manifest['branches']['user_day_sequences']['rows'] == 4
    for branch in BRANCHES:
        relative = Path(branch)/'bucket-000.parquet'
        source = pq.read_table(Path(config['paths']['input_root'])/relative)
        output = pq.read_table(Path(config['paths']['output_root'])/relative)
        assert output.select(source.column_names).equals(source, check_metadata=False)
        assert b'pandas' not in (output.schema.metadata or {})
        assert output['user'].to_pylist()[0] == ' U1 '
        assert output['role'].to_pylist()[0] == 'Engineer'
        assert output['role'].to_pylist()[-1] == 'Manager'
        assert output['department'].to_pylist()[-1] == 'UNKNOWN'
        assert output['department_missing'].to_pylist()[-1] is True
        assert output['ldap_month'].to_pylist()[-1] == '2020-02'
        assert manifest['branches'][branch]['missing_user_days'] == {'role': 1, 'department': 1}


def test_future_snapshot_and_no_carry_forward(tmp_path):
    config = setup(tmp_path)
    metadata = load_ldap_metadata(Path(config['paths']['ldap_dir']))
    batch = feature_table().to_batches()[0]
    initial = enrich_batch(batch, metadata)
    metadata[('U1', '2020-03')] = {'role': 'Future', 'department': 'Future'}
    assert initial.equals(enrich_batch(batch, metadata))
    metadata.pop(('U1', '2020-02'))
    output = enrich_batch(batch, metadata)
    assert output.column('role').to_pylist()[-1] == 'UNKNOWN'
    assert output.column('role_missing').to_pylist()[-1]


@pytest.mark.parametrize('kind', ['duplicate', 'invalid_month', 'empty', 'bad_header', 'blank_user', 'bad_row'])
def test_invalid_ldap(tmp_path, kind):
    config = setup(tmp_path)
    ldap = Path(config['paths']['ldap_dir'])
    path = ldap/'2020-01.csv'
    if kind == 'duplicate':
        path.write_text('user_id,role,department\nU1,A,D\n U1 ,A,D\n')
    elif kind == 'invalid_month':
        path.rename(ldap/'2020-13.csv')
    elif kind == 'empty':
        path.write_text('user_id,role,department\n')
    elif kind == 'bad_header':
        path.write_text('user_id,role\nU1,A\n')
    elif kind == 'blank_user':
        path.write_text('user_id,role,department\n ,A,D\n')
    else:
        path.write_text('user_id,role,department\nU1,A\n')
    with pytest.raises(ValueError):
        enrich_dataset(config)
    assert not Path(config['paths']['output_root']).exists()


@pytest.mark.parametrize('kind', ['duplicate_feature', 'bad_index', 'duplicate_sequence', 'null_user', 'time',
                                   'metadata', 'schema', 'keys', 'extra_bucket', 'empty_bucket'])
def test_invalid_parquet_cleans_partial_output(tmp_path, kind):
    config = setup(tmp_path)
    source = Path(config['paths']['input_root'])
    branch = 'user_day_sequences' if kind in ('bad_index', 'duplicate_sequence') else 'user_day_features'
    path = source/branch/'bucket-000.parquet'
    table = pq.read_table(path)
    if kind == 'duplicate_feature':
        table = pa.concat_tables([table, table.slice(0, 1)])
    elif kind == 'bad_index':
        table = table.set_column(table.schema.get_field_index('event_index'), 'event_index', pa.array([0, 2, 0, 0]))
    elif kind == 'duplicate_sequence':
        table = pa.concat_tables([table, table.slice(0, 1)])
    elif kind == 'null_user':
        table = table.set_column(0, 'user', pa.array([None, 'U2', 'U1'], type=pa.string()))
    elif kind == 'time':
        table = table.set_column(1, 'day', pa.array([datetime(2020, 1, 31, 1)]*3, type=pa.timestamp('ns')))
    elif kind == 'metadata':
        table = table.append_column('role', pa.array(['X']*3))
    elif kind == 'schema':
        table = table.drop(['f001'])
    elif kind == 'keys':
        table = table.set_column(0, 'user', pa.array(['other', 'U2', 'U1']))
    elif kind == 'extra_bucket':
        pq.write_table(table.drop(['f001']), path.parent/'bucket-001.parquet')
    else:
        table = table.slice(0, 0)
    pq.write_table(table, path)
    with pytest.raises(ValueError):
        enrich_dataset(config)
    output = Path(config['paths']['output_root'])
    assert not output.exists()
    assert not list(output.parent.glob('.output-*'))


def test_output_guards_and_repeatability(tmp_path):
    config = setup(tmp_path)
    first = enrich_dataset(config)
    out = Path(config['paths']['output_root'])
    marker = (out/'manifest.json').read_bytes()
    with pytest.raises(FileExistsError):
        enrich_dataset(config)
    assert (out/'manifest.json').read_bytes() == marker
    other = copy.deepcopy(config)
    other['paths']['output_root'] = str(out.with_name('second'))
    second = enrich_dataset(other)
    assert first['branches'] == second['branches']
    for unsafe in (config['paths']['input_root'], str(Path(config['paths']['input_root'])/'child'),
                   config['paths']['ldap_dir'], str(tmp_path)):
        other['paths']['output_root'] = unsafe
        with pytest.raises(ValueError):
            enrich_dataset(other)


def test_readback_corruption_is_rejected(tmp_path, monkeypatch):
    import itd.data.enrich_ldap as module
    config = setup(tmp_path)
    actual = module.enrich_batch
    calls = 0

    def corrupt(batch, metadata):
        nonlocal calls
        calls += 1
        result = actual(batch, metadata)
        if calls == 1:
            table = pa.Table.from_batches([result])
            table = table.set_column(table.schema.get_field_index('f100'), 'f100', pa.array([999.]))
            return table.to_batches()[0]
        return result

    monkeypatch.setattr(module, 'enrich_batch', corrupt)
    with pytest.raises(ValueError, match='original values'):
        enrich_dataset(config)
    assert not Path(config['paths']['output_root']).exists()


def test_cli_from_project_root(tmp_path):
    config = setup(tmp_path)
    path = tmp_path/'config.json'
    path.write_text(json.dumps(config))
    cli = Path(__file__).resolve().parents[1]/'scripts/enrich_preprocessed_ldap.py'
    result = subprocess.run([sys.executable, str(cli), '--config', str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (Path(config['paths']['output_root'])/'manifest.json').exists()
