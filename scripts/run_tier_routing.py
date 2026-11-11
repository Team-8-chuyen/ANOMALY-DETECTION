"""Route paired Department/Role cases; optionally attach external scores (SPEC-002 §14)."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from itd.scoring.routing import RoutingConfig, fit_group_members, init_routing_history, route_days
from itd.scoring.score_input import attach_selected_scores

CASES = ('department', 'role')
PROJECTION = {'user': pa.string(), 'day': pa.timestamp('ns'), 'role': pa.string(),
              'department': pa.string(), 'role_missing': pa.bool_(), 'department_missing': pa.bool_()}
SCORE_COLUMNS = ['user', 'day', 'group_key', 'selected_tier', 'score']


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'{path.name}: duplicate JSON key {key}')
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError('non-finite JSON value')

    result = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique, parse_constant=nonfinite)
    if not isinstance(result, dict):
        raise ValueError('config must be an object')
    return result


def iso_day(value: str) -> str:
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError('dates must use YYYY-MM-DD')
    return value


def resolve_configs(paths: list[Path]) -> list[dict]:
    if len(paths) != 2:
        raise ValueError('provide exactly two case configs')
    resolved = []
    for path in paths:
        overlay = load_json(path)
        if set(overlay) != {'extends', 'group_key'} or overlay['group_key'] not in CASES:
            raise ValueError('case config requires only extends and group_key')
        if not isinstance(overlay['extends'], str) or not overlay['extends'].strip():
            raise ValueError('invalid extends')
        common = load_json(path.parent / overlay['extends'])
        if set(common) != {'paths', 'split', 'routing', 'batch_rows'} or set(common['paths']) != {'feature_dir'}:
            raise ValueError('invalid common config schema')
        if set(common['split']) != {'train', 'calibration'}:
            raise ValueError('only train and calibration splits supported')
        for name in ('train', 'calibration'):
            span = common['split'][name]
            if set(span) != {'start', 'end'} or iso_day(span['start']) > iso_day(span['end']):
                raise ValueError('invalid split range')
        if common['split']['train']['end'] >= common['split']['calibration']['start']:
            raise ValueError('splits must be ordered and disjoint')
        RoutingConfig(**common['routing'])
        if type(common['batch_rows']) is not int or common['batch_rows'] < 1:
            raise ValueError('batch_rows must be a positive integer')
        feature_dir = common['paths']['feature_dir']
        if not isinstance(feature_dir, str) or not feature_dir.strip():
            raise ValueError('invalid feature_dir')
        common['paths']['feature_dir'] = str((ROOT / feature_dir).resolve())
        resolved.append({**common, 'group_key': overlay['group_key']})
    if {c['group_key'] for c in resolved} != set(CASES):
        raise ValueError('one config for each case is required')
    shared = [{k: v for k, v in c.items() if k != 'group_key'} for c in resolved]
    if shared[0] != shared[1]:
        raise ValueError('paired cases must have identical common config')
    return sorted(resolved, key=lambda c: c['group_key'])


def read_metadata(config: dict) -> tuple[dict, dict]:
    directory = Path(config['paths']['feature_dir'])
    files = sorted(directory.glob('*.parquet'))
    if not files:
        raise ValueError('no feature Parquet files')
    splits = {'train': [], 'calibration': []}
    manifest = {'projection': {k: str(v) for k, v in PROJECTION.items()}, 'files': {},
                'outside_split_rows': 0, 'input_rows': 0, 'test_evaluation': 'deferred'}
    expected_schema = None
    for path in files:
        if path.is_symlink() or directory.resolve() not in path.resolve().parents:
            raise ValueError('input file escapes feature_dir')
        original_hash = hash_file(path)
        with pq.ParquetFile(path) as reader:
            schema = reader.schema_arrow
            if len(schema.names) != len(set(schema.names)) or any(
                    n not in schema.names or schema.field(n).type != t for n, t in PROJECTION.items()):
                raise ValueError(f'{path.name}: invalid metadata projection schema')
            projected = pa.schema([schema.field(n) for n in PROJECTION])
            if expected_schema is not None and not projected.equals(expected_schema, check_metadata=False):
                raise ValueError('metadata schema differs between buckets')
            expected_schema = projected
            count = 0
            for batch in reader.iter_batches(batch_size=config['batch_rows'], columns=list(PROJECTION)):
                if batch.column('day').null_count:
                    raise ValueError('null day cannot be assigned to a split')
                days = batch.column('day')
                if pc.any(pc.not_equal(days, pc.cast(pc.cast(days, pa.date32()), days.type))).as_py():
                    raise ValueError('day must be midnight')
                values = {n: batch.column(n).to_pylist() for n in PROJECTION if n != 'day'}
                # Convert the date column with Arrow, without constructing Python timestamps.
                values['day'] = pc.cast(pc.cast(days, pa.date32()), pa.string()).to_pylist()
                for i, day in enumerate(values['day']):
                    selected = next((name for name, span in config['split'].items()
                                     if span['start'] <= day <= span['end']), None)
                    if selected is None:
                        manifest['outside_split_rows'] += 1
                    else:
                        splits[selected].append({n: values[n][i] for n in PROJECTION})
                count += batch.num_rows
        if original_hash != hash_file(path):
            raise ValueError('input changed during reading')
        manifest['files'][path.name] = {'rows': count, 'sha256': original_hash}
        manifest['input_rows'] += count
    for name, rows in splits.items():
        if not rows:
            raise ValueError(f'{name} is empty')
        rows.sort(key=lambda r: (r['day'], str(r['user']).strip()))
    return splits, manifest


def read_scores(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) != set(SCORE_COLUMNS):
            raise ValueError('score CSV schema mismatch')
        rows = []
        for line, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'score CSV line {line}: malformed row')
            row['score'] = float(row['score'])
            rows.append(row)
        return rows


def run_tier_routing(config_paths: list[Path], run_dir: Path, scores_path: Path | None = None) -> dict:
    start = time.perf_counter()
    configs = resolve_configs(config_paths)
    config = configs[0]
    output = run_dir.resolve()
    source = Path(config['paths']['feature_dir'])
    if output == source or source in output.parents or output in source.parents:
        raise ValueError('run directory must not overlap source data')
    if scores_path is not None:
        score_source = scores_path.resolve()
        if score_source == output or output in score_source.parents:
            raise ValueError('run directory must not contain score input')
    if output.exists():
        raise FileExistsError('run directory already exists')
    splits, manifest = read_metadata(config)
    settings = RoutingConfig(**config['routing'])
    groups = fit_group_members(splits['train'])
    history = init_routing_history(splits['train'], date.fromisoformat(splits['calibration'][0]['day']), settings)
    routes, history_after = route_days(splits['calibration'], groups, history, settings)
    score_hash = None
    if scores_path is not None:
        score_hash = hash_file(scores_path)
        routes = attach_selected_scores(routes, read_scores(scores_path))
        if score_hash != hash_file(scores_path):
            raise ValueError('score input changed during reading')
    shared = {k: v for k, v in config.items() if k != 'group_key'}
    manifest['shared_config_fingerprint'] = hashlib.sha256(json_text(shared).encode()).hexdigest()
    manifest['score_input_sha256'] = score_hash
    manifest['splits'] = {name: {'count': len(rows), 'start': rows[0]['day'], 'end': rows[-1]['day']}
                          for name, rows in splits.items()}
    counts = {}
    for case in CASES:
        subset = [r for r in routes if r['group_key'] == case]
        tiers = {t: sum(r['selected_tier'] == t for r in subset) for t in ('personal', 'group', 'global')}
        cold = [r for r in subset if r['n_personal_days'] < settings.min_personal_days]
        counts[case] = {'rows': len(subset), 'tier_counts': tiers,
                        'tier_fractions': {t: n/len(subset) for t, n in tiers.items()},
                        'fallback_reasons': dict(Counter(r['fallback_reason'] for r in subset)),
                        'cold_start_rows': len(cold),
                        'cold_start_tiers': dict(Counter(r['selected_tier'] for r in cold)),
                        'missing_metadata_rows': sum(r[case + '_missing'] for r in splits['calibration'])}
    keys = [[r['user'].strip(), r['day']] for r in splits['calibration']]
    manifest['calibration_user_day_sha256'] = hashlib.sha256(json_text(keys).encode()).hexdigest()
    metrics = {'mode': 'external_scores' if scores_path is not None else 'routing_only', 'cases': counts,
               'score_status': 'provided' if scores_path is not None else 'awaiting_external_score',
               'test_evaluation': 'deferred', 'elapsed_seconds': round(time.perf_counter()-start, 6)}
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f'.{output.name}-', dir=output.parent)).resolve()
    try:
        artifacts = {'config.json': configs, 'manifest.json': manifest, 'metrics.json': metrics,
                     'history_after_calibration.json': history_after,
                     'group_members.json': {case: {group: sorted(users) for group, users in sorted(mapping.items())}
                                            for case, mapping in sorted(groups.items())}}
        for name, value in artifacts.items():
            (staging/name).write_text(json_text(value)+'\n', encoding='utf-8')
        for case in CASES:
            directory = staging/case
            directory.mkdir()
            subset = [r for r in routes if r['group_key'] == case]
            with (directory/'routes.csv').open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(subset[0]))
                writer.writeheader()
                writer.writerows(subset)
        (staging/'env.txt').write_text(f'Python {platform.python_version()}\nPyArrow {pa.__version__}\n', encoding='utf-8')
        status = subprocess.run(['git', 'status', '--short'], cwd=ROOT, capture_output=True, text=True)
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
        (staging/'git.txt').write_text(head.stdout+status.stdout, encoding='utf-8')
        metrics['elapsed_seconds'] = round(time.perf_counter()-start, 6)
        (staging/'metrics.json').write_text(json_text(metrics)+'\n', encoding='utf-8')
        (staging/'log.txt').write_text('SPEC-002 v1.2 routing completed; no score fitting or research evaluation.\n'+json_text(metrics), encoding='utf-8')
        staging.rename(output)
    except BaseException:
        if staging.parent == output.parent and staging.name.startswith(f'.{output.name}-') and staging.exists():
            shutil.rmtree(staging)
        raise
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, action='append', required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--scores', type=Path)
    args = parser.parse_args()
    try:
        print(json_text(run_tier_routing(args.config, args.run_dir, args.scores)))
    except (ValueError, TypeError, KeyError, OSError, csv.Error) as error:
        parser.exit(1, f'Error: {error}\n')


if __name__ == '__main__':
    main()
