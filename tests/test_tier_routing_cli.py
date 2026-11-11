import csv
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('tier_cli', ROOT/'scripts/run_tier_routing.py')
RUNNER = importlib.util.module_from_spec(SPEC)


def load_runner():
    if not hasattr(RUNNER, 'run_tier_routing'):
        SPEC.loader.exec_module(RUNNER)
    return RUNNER


def make_fixture(tmp_path):
    source = tmp_path/'features'
    source.mkdir()
    rows = []

    def row(user, day, role='R1', department='D'):
        return {'user': user, 'day': datetime.fromisoformat(day), 'role': role, 'department': department,
                'role_missing': role == 'UNKNOWN', 'department_missing': department == 'UNKNOWN'}

    for day in range(24, 32):
        rows.append(row('U1', f'2020-01-{day}'))
    rows.append(row('U2', '2020-01-31', role='R2'))
    for day in ('2020-02-01', '2020-02-02'):
        rows.extend([row('U1', day), row('U2', day, role='R2'), row('U3', day, role='UNKNOWN', department='UNKNOWN')])
    rows.append(row('future', '2020-03-01'))
    table = pa.Table.from_pylist(rows)
    table = table.set_column(table.schema.get_field_index('day'), 'day', table['day'].cast(pa.timestamp('ns')))
    # Extra feature column exists, but the router must never require/use its values.
    table = table.append_column('f001', pa.array(['unrelated']*len(rows)))
    pq.write_table(table, source/'bucket-000.parquet')
    common = {'paths': {'feature_dir': str(source)},
              'split': {'train': {'start': '2020-01-01', 'end': '2020-01-31'},
                        'calibration': {'start': '2020-02-01', 'end': '2020-02-02'}},
              'routing': {'window_days': 30, 'min_personal_days': 7, 'min_group_users': 2}, 'batch_rows': 2}
    common_path = tmp_path/'common.json'
    common_path.write_text(json.dumps(common))
    configs = []
    for case in ('department', 'role'):
        path = tmp_path/f'{case}.json'
        path.write_text(json.dumps({'extends': 'common.json', 'group_key': case}))
        configs.append(path)
    return configs, common_path, source


def output_rows(directory):
    rows = []
    for case in ('department', 'role'):
        with (directory/case/'routes.csv').open(encoding='utf-8', newline='') as stream:
            rows.extend(csv.DictReader(stream))
    return rows


def test_cli_route_only_repeatability_and_projection(tmp_path):
    runner = load_runner()
    configs, _, _ = make_fixture(tmp_path)
    first = tmp_path/'first'
    metrics = runner.run_tier_routing(configs, first)
    runner.run_tier_routing(configs[::-1], tmp_path/'second')
    assert metrics['mode'] == 'routing_only'
    assert metrics['cases']['department']['tier_counts'] == {'personal': 2, 'group': 2, 'global': 2}
    assert metrics['cases']['role']['tier_counts'] == {'personal': 2, 'group': 0, 'global': 4}
    for case in ('department', 'role'):
        assert (first/case/'routes.csv').read_bytes() == (tmp_path/'second'/case/'routes.csv').read_bytes()
    rows = output_rows(first)
    assert len(rows) == 12
    assert all(r['score'] == '' and r['score_status'] == 'awaiting_external_score' for r in rows)
    assert all('threshold' not in r and 'is_alert' not in r for r in rows)
    manifest = json.loads((first/'manifest.json').read_text())
    assert manifest['outside_split_rows'] == 1 and manifest['input_rows'] == 16
    assert list(manifest['projection']) == sorted(runner.PROJECTION)
    assert not list(first.rglob('threshold.json'))


def test_scores_end_to_end_preserve_and_missing_never_fallback(tmp_path):
    runner = load_runner()
    configs, _, _ = make_fixture(tmp_path)
    original = tmp_path/'routes'
    runner.run_tier_routing(configs, original)
    expected = output_rows(original)
    score_path = tmp_path/'scores.csv'
    supplied = []
    with score_path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=runner.SCORE_COLUMNS)
        writer.writeheader()
        for row in expected:
            score = -2.5 if row['selected_tier'] == 'personal' else 0.0
            item = {k: row[k] for k in runner.SCORE_COLUMNS if k != 'score'}
            item['score'] = score
            supplied.append(item)
            writer.writerow(item)
    out = tmp_path/'scored'
    result = runner.run_tier_routing(configs, out, score_path)
    assert result['mode'] == 'external_scores'
    actual = output_rows(out)
    assert all(r['score_status'] == 'provided' for r in actual)
    assert [(r['user'], r['day'], r['selected_tier']) for r in actual] == [(r['user'], r['day'], r['selected_tier']) for r in expected]
    assert [float(r['score']) for r in actual] == [r['score'] for r in supplied]
    with score_path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=runner.SCORE_COLUMNS)
        writer.writeheader()
        writer.writerows(supplied[:-1])
    with pytest.raises(ValueError):
        runner.run_tier_routing(configs, tmp_path/'incomplete', score_path)
    assert not (tmp_path/'incomplete').exists()


@pytest.mark.parametrize('kind', ['mismatch', 'duplicate_case', 'overlap', 'overlay_extra', 'bad_flag', 'duplicate_row', 'null_day', 'time', 'no_calibration', 'duplicate_json'])
def test_invalid_setup_does_not_publish(tmp_path, kind):
    runner = load_runner()
    configs, common_path, source = make_fixture(tmp_path)
    common = json.loads(common_path.read_text())
    if kind == 'mismatch':
        common['routing']['min_personal_days'] = 8
        (tmp_path/'other.json').write_text(json.dumps(common))
        configs[1].write_text(json.dumps({'extends': 'other.json', 'group_key': 'role'}))
    elif kind == 'duplicate_case':
        configs[1] = configs[0]
    elif kind == 'overlap':
        common['split']['calibration']['start'] = '2020-01-31'
        common_path.write_text(json.dumps(common))
    elif kind == 'overlay_extra':
        configs[1].write_text(json.dumps({'extends': 'common.json', 'group_key': 'role', 'routing': {}}))
    elif kind == 'no_calibration':
        common['split']['calibration'] = {'start': '2030-01-01', 'end': '2030-02-01'}
        common_path.write_text(json.dumps(common))
    elif kind == 'duplicate_json':
        configs[1].write_text('{"extends":"common.json","group_key":"role","group_key":"role"}')
    else:
        path = source/'bucket-000.parquet'
        table = pq.read_table(path)
        if kind == 'bad_flag':
            table = table.set_column(table.schema.get_field_index('role_missing'), 'role_missing', pa.array([True]*len(table)))
        elif kind == 'duplicate_row':
            table = pa.concat_tables([table, table.slice(0, 1)])
        else:
            days = table['day'].to_pylist()
            days[0] = None if kind == 'null_day' else datetime(2020, 1, 24, 1)
            table = table.set_column(table.schema.get_field_index('day'), 'day', pa.array(days, type=pa.timestamp('ns')))
        pq.write_table(table, path)
    with pytest.raises((ValueError, TypeError)):
        runner.run_tier_routing(configs, tmp_path/'bad-run')
    assert not (tmp_path/'bad-run').exists()


def test_run_guards_and_cli(tmp_path):
    runner = load_runner()
    configs, _, source = make_fixture(tmp_path)
    with pytest.raises(ValueError):
        runner.run_tier_routing(configs, source/'unsafe')
    out = tmp_path/'completed'
    result = subprocess.run([sys.executable, str(ROOT/'scripts/run_tier_routing.py'),
                             '--config', str(configs[0]), '--config', str(configs[1]), '--run-dir', str(out)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    before = (out/'manifest.json').read_bytes()
    with pytest.raises(FileExistsError):
        runner.run_tier_routing(configs, out)
    assert (out/'manifest.json').read_bytes() == before


@pytest.mark.parametrize('kind', ['nan', 'infinity', 'duplicate_header', 'extra_column', 'wrong_tier'])
def test_csv_errors_are_rejected_before_publish(tmp_path, kind):
    runner = load_runner()
    configs, _, _ = make_fixture(tmp_path)
    original = tmp_path/'original'
    runner.run_tier_routing(configs, original)
    rows = [{n: row[n] for n in runner.SCORE_COLUMNS} for row in output_rows(original)]
    for row in rows:
        row['score'] = '0'
    path = tmp_path/'scores.csv'
    columns = list(runner.SCORE_COLUMNS)
    if kind == 'nan':
        rows[0]['score'] = 'NaN'
    elif kind == 'infinity':
        rows[0]['score'] = 'Infinity'
    elif kind == 'duplicate_header':
        columns.append('score')
    elif kind == 'extra_column':
        columns.append('label')
    else:
        rows[0]['selected_tier'] = 'group' if rows[0]['selected_tier'] == 'personal' else 'personal'
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):
        runner.run_tier_routing(configs, tmp_path/'invalid-scores', path)
    assert not (tmp_path/'invalid-scores').exists()


def test_write_failure_cleanup_and_score_path_guard(tmp_path, monkeypatch):
    runner = load_runner()
    configs, _, _ = make_fixture(tmp_path)
    out = tmp_path/'failed-output'
    with pytest.raises(ValueError):
        runner.run_tier_routing(configs, out, out/'scores.csv')
    actual_write = Path.write_text

    def fail_write(path, *args, **kwargs):
        if path.name == 'log.txt':
            raise OSError('injected write failure')
        return actual_write(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'write_text', fail_write)
    with pytest.raises(OSError, match='injected write failure'):
        runner.run_tier_routing(configs, out)
    assert not out.exists()
    assert not list(tmp_path.glob('.failed-output-*'))
