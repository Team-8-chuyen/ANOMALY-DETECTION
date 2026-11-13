"""Run the paired, one-epoch pilot and report measured costs (SPEC-004)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import gc
import hashlib
import math
from pathlib import Path
import platform
import random
import subprocess
from time import perf_counter

import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import sklearn
import torch
from threadpoolctl import threadpool_info

from itd.data.feature_preprocessing import FeaturePreprocessor
from itd.data.pilot_dataset import METADATA_FIELDS, PilotData
from itd.data.sequence_dataset import window_day
from itd.data.sequence_preprocessing import SequencePreprocessor
from itd.models.feature_isolation_forest import fit_feature_if, score_feature_if
from itd.models.lstm_autoencoder import LSTMAutoencoder
from .pilot_config import ROOT, json_text
from .sequence_trainer import PilotTimeout, check_deadline, score_days, train_one_epoch


SCORE_SCHEMA = pa.schema([
    ('user', pa.string()), ('day', pa.timestamp('ns')), ('role', pa.string()),
    ('department', pa.string()), ('role_missing', pa.bool_()),
    ('department_missing', pa.bool_()), ('ldap_month', pa.string()),
    ('e_feature_raw', pa.float64()), ('e_sequence_raw', pa.float64()),
    ('loss_sum', pa.float64()), ('n_valid_attributes', pa.int64()),
    ('n_sequence_rows', pa.int64()), ('n_windows', pa.int64()),
])


@dataclass
class PilotResult:
    status: str
    metrics: dict
    runtime_estimate: dict
    artifact_paths: dict


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json_text(value).encode('utf-8')).hexdigest()


def seed_model(config: dict) -> torch.Generator:
    seed = config['data']['seed']
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(config['train']['threads'])
    torch.use_deterministic_algorithms(True)
    return torch.Generator(device='cpu').manual_seed(seed)


def make_model(preprocessor: SequencePreprocessor, config: dict) -> LSTMAutoencoder:
    return LSTMAutoencoder(preprocessor.vocab_sizes, config['lstm'],
                           window_length=config['data']['window_length'])


def make_optimizer(model, config: dict):
    return torch.optim.AdamW(model.parameters(), lr=config['train']['lr'],
                             weight_decay=config['train']['weight_decay'])


def estimate_runtime(measurements: dict, reference: dict) -> dict:
    """Two explicit scenarios; neither is a bound or a measured full run (§7)."""
    result = {
        'method': 'conditional linear scenarios from one complete training epoch',
        'measured_full_run': False, 'confidence_interval': None,
        'full_if_fit_seconds': None, 'full_validation_seconds': None,
        'full_scoring_seconds': None, 'full_total_wall_seconds': None,
        'assumptions': ['same model, batch size, threads and runtime backend',
                        'comparable length and padding distribution; overhead may differ',
                        'setup, warmup and validation are not scaled as training'],
        'scenarios': None,
    }
    if measurements.get('status') != 'complete':
        result['reason'] = 'pilot incomplete; no partial-epoch extrapolation'
        return result
    values = [measurements['train_epoch_seconds'], measurements['n_fit_days'],
              measurements['n_fit_valid_steps'], reference['reference_train_days'],
              reference['reference_train_steps'], reference['reference_epochs']]
    if (any(isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) for value in values)
            or values[0] < 0 or any(value <= 0 for value in values[1:])):
        raise ValueError('runtime estimates need finite nonnegative time and positive counts')
    seconds, days, steps, full_days, full_steps, epochs = values
    scenarios = {}
    for label, factor in [('valid_steps', full_steps / steps), ('user_days', full_days / days)]:
        scenarios[label] = {'scale_factor': factor,
                            'full_train_one_epoch_seconds': seconds * factor,
                            'hypothetical_epochs': epochs,
                            'full_train_epochs_seconds': seconds * factor * epochs}
    result['scenarios'] = scenarios
    result['warning'] = 'Small pilot scenarios can differ substantially from full-run runtime.'
    return result


def load_lstm_checkpoint(path: Path, config: dict, preprocessor: SequencePreprocessor):
    payload = torch.load(path, map_location='cpu', weights_only=True)
    if (payload.get('config_sha256') != fingerprint(config) or
            payload.get('sequence_preprocessor_sha256') != fingerprint(preprocessor.to_dict()) or
            payload.get('epoch') != 1 or payload.get('format_version') != 1):
        raise ValueError('LSTM checkpoint fingerprint/schema does not match this pilot')
    model = make_model(preprocessor, config)
    model.load_state_dict(payload['model_state'], strict=True)
    model.eval()
    return model


def _distribution(values) -> dict:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0 or not np.isfinite(array).all():
        raise ValueError('raw scores must be nonempty and finite')
    return {'count': int(array.size), 'min': float(array.min()), 'max': float(array.max()),
            'mean': float(array.mean()), 'std': float(array.std())}


def _validation_summary(scores) -> dict:
    per_field, per_type = {}, {}
    for attr, destination in [('per_field', per_field), ('per_type', per_type)]:
        for score in scores:
            for name, value in getattr(score, attr).items():
                item = destination.setdefault(name, {'loss_sum': 0.0, 'count': 0})
                item['loss_sum'] += value['loss_sum']
                item['count'] += value['count']
        for item in destination.values():
            item['mean'] = item['loss_sum'] / item['count'] if item['count'] else None
    return {'per_field': per_field, 'per_type': per_type}


def _environment() -> str:
    freeze = subprocess.run([__import__('sys').executable, '-m', 'pip', 'freeze'],
                            capture_output=True, text=True, check=True).stdout
    return json_text({'python': platform.python_version(), 'platform': platform.platform(),
                       'torch': str(torch.__version__), 'sklearn': sklearn.__version__,
                       'numpy': np.__version__, 'pyarrow': pa.__version__, 'device': 'cpu',
                       'cuda_available': torch.cuda.is_available(),
                       'torch_threads': torch.get_num_threads(), 'threadpools': threadpool_info()}) + '\n' + freeze


def run_pilot(data: PilotData, config: dict, run_dir: Path, *, initial_timings: dict | None = None,
              start_time: float | None = None, clock=perf_counter) -> PilotResult:
    run_dir = Path(run_dir)
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError('pilot work directory must be empty')
    run_dir.mkdir(parents=True, exist_ok=True)
    started = clock() if start_time is None else start_time
    timings = dict(initial_timings or {})
    metrics = {'status': 'incomplete', 'spec': 'SPEC-004 v1.0', 'seed': config['data']['seed'],
               'timings_seconds': timings, 'cohort': list(data.cohort),
               'n_fit_days': len(data.fit_days), 'n_validation_days': len(data.validation_days)}
    runtime = estimate_runtime({'status': 'incomplete'}, config['benchmark'])
    artifacts = {}

    def write_json(name: str, value):
        (run_dir / name).write_text(json_text(value) + '\n', encoding='utf-8')
        artifacts[name] = str(run_dir / name)

    def phase(name, action):
        mark = clock()
        try:
            return action()
        finally:
            timings[name] = clock() - mark

    write_json('config.json', config)
    write_json('manifest.json', {**data.provenance, 'cohort': data.cohort, 'split': config['split']})
    try:
        def preprocess():
            feature = FeaturePreprocessor().fit(data.fit_features)
            fit_days = sorted(data.fit_days, key=lambda day: (day.day, day.user))
            sequence = SequencePreprocessor(config['sequence']['epsilon']).fit(fit_days)
            x_fit = feature.transform(data.fit_features)
            x_val = feature.transform(data.validation_features)
            unseen = {name: 0 for name in sequence.vocabularies}
            for day in data.validation_days:
                for name, count in sequence.transform(day).unseen_counts.items():
                    unseen[name] += count
            windows = [window for day in fit_days for window in
                       window_day(day, config['data']['window_length'])]
            return feature, sequence, x_fit, x_val, unseen, windows

        feature, sequence, x_fit, x_val, unseen, windows = phase('preprocessing_seconds', preprocess)
        deadline = clock() + config['benchmark']['max_seconds']
        check_deadline(deadline, clock)
        forest = phase('if_fit_seconds', lambda: fit_feature_if(x_fit, config['isolation_forest'],
                                                               config['data']['seed']))
        check_deadline(deadline, clock)
        feature_scores = phase('if_validation_score_seconds', lambda: score_feature_if(forest, x_val))
        check_deadline(deadline, clock)

        def warmup():
            generator = seed_model(config)
            temporary = make_model(sequence, config)
            optimizer = make_optimizer(temporary, config)
            first = windows[:config['train']['batch_size']]
            for _ in range(config['benchmark']['warmup_steps']):
                train_one_epoch(temporary, first, sequence, optimizer, config, generator,
                                 deadline=deadline, clock=clock)
            del optimizer, temporary
            gc.collect()

        phase('warmup_seconds', warmup)
        # SPEC-004 §4.6: no warmup weights or generator state survive into epoch 1.
        generator = seed_model(config)
        model = make_model(sequence, config)
        optimizer = make_optimizer(model, config)
        epoch = phase('lstm_train_epoch_seconds', lambda: train_one_epoch(
            model, windows, sequence, optimizer, config, generator, deadline=deadline, clock=clock))
        sequence_scores = phase('lstm_validation_seconds', lambda: score_days(
            model, data.validation_days, sequence, config, deadline=deadline, clock=clock))
        feature_by_key = {(row['user'], row['day']): (row, float(value))
                          for row, value in zip(data.validation_features, feature_scores, strict=True)}
        if len(feature_by_key) != len(data.validation_features):
            raise ValueError('duplicate feature score key')
        rows = []
        for score in sequence_scores:
            key = score.user, score.day
            if key not in feature_by_key:
                raise ValueError('sequence/feature score keys differ')
            source, feature_value = feature_by_key.pop(key)
            if any(source[name] != score.metadata[name] for name in METADATA_FIELDS):
                raise ValueError('sequence/feature score metadata differ')
            row = {**score.to_dict(), 'e_feature_raw': feature_value}
            row['day'] = datetime.fromisoformat(row['day'])
            rows.append(row)
        if feature_by_key or len(rows) != len(data.validation_days):
            raise ValueError('raw score coverage is incomplete')
        val_windows = [window for day in sorted(data.validation_days, key=lambda day: (day.day, day.user)) for window in
                       window_day(day, config['data']['window_length'])]
        batch_size = config['train']['batch_size']
        val_padded = sum(len(part) * max(window.length for window in part)
                         for offset in range(0, len(val_windows), batch_size)
                         if (part := val_windows[offset:offset + batch_size]))
        metrics.update(status='complete', completed_epochs=1, train=epoch.to_dict(),
                       validation={'n_windows': len(val_windows),
                                   'n_batches': math.ceil(len(val_windows) / batch_size),
                                   'valid_steps': sum(row['n_sequence_rows'] for row in rows),
                                   'padded_steps': val_padded, **_validation_summary(sequence_scores)},
                       validation_unseen_counts=unseen,
                       model_parameters=sum(parameter.numel() for parameter in model.parameters()),
                       feature_input_columns=int(x_fit.shape[1]),
                       feature_raw_score=_distribution(feature_scores),
                       sequence_raw_score=_distribution([row['e_sequence_raw'] for row in rows]))
        runtime = estimate_runtime({'status': 'complete', 'train_epoch_seconds':
                                     timings['lstm_train_epoch_seconds'],
                                     'n_fit_days': len(data.fit_days),
                                     'n_fit_valid_steps': epoch.valid_steps}, config['benchmark'])
        mark = clock()
        write_json('feature_preprocessor.json', feature.to_dict())
        write_json('sequence_preprocessor.json', sequence.to_dict())
        joblib.dump({'model': forest, 'config_sha256': fingerprint(config),
                      'feature_preprocessor_sha256': fingerprint(feature.to_dict())},
                     run_dir / 'if_model.joblib')
        torch.save({'format_version': 1, 'epoch': 1, 'config_sha256': fingerprint(config),
                     'sequence_preprocessor_sha256': fingerprint(sequence.to_dict()),
                     'model_state': model.state_dict(), 'optimizer_state': optimizer.state_dict()},
                    run_dir / 'lstm_model.pt')
        pq.write_table(pa.Table.from_pylist(rows, schema=SCORE_SCHEMA),
                        run_dir / 'validation_scores.parquet', compression='zstd')
        (run_dir / 'env.txt').write_text(_environment(), encoding='utf-8')
        git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
        diff = subprocess.run(['git', 'diff', '--', 'src', 'scripts', 'configs', 'requirements-models-cpu.txt'],
                              cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        status = subprocess.run(['git', 'status', '--short'], cwd=ROOT, capture_output=True,
                                text=True, encoding='utf-8')
        (run_dir / 'git.txt').write_text(git.stdout + '\n' + status.stdout + '\n' + diff.stdout,
                                         encoding='utf-8')
        timings['artifact_write_seconds'] = clock() - mark
        metrics['timing_note'] = 'Final metrics/log serialization and atomic publication follow the measured artifact phase.'
    except PilotTimeout as error:
        metrics.update(status='incomplete', error=str(error))
        runtime = estimate_runtime({'status': 'incomplete'}, config['benchmark'])
    except Exception as error:
        metrics.update(status='failed', error=f'{type(error).__name__}: {error}')
        runtime = estimate_runtime({'status': 'failed'}, config['benchmark'])
        timings['total_wall_seconds'] = clock() - started
        write_json('metrics.json', metrics)
        write_json('runtime-estimate.json', runtime)
        (run_dir / 'log.txt').write_text(metrics['error'] + '\n', encoding='utf-8')
        raise
    timings['total_wall_seconds'] = clock() - started
    write_json('metrics.json', metrics)
    write_json('runtime-estimate.json', runtime)
    (run_dir / 'log.txt').write_text(json_text({'status': metrics['status'], 'timings_seconds': timings}) + '\n',
                                     encoding='utf-8')
    for path in run_dir.iterdir():
        artifacts[path.name] = str(path)
    return PilotResult(metrics['status'], metrics, runtime, artifacts)
