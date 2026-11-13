"""Validate the deliberately bounded CPU pilot (SPEC-004 sections 4 and 5)."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATH_KEYS = {
    'feature_dir', 'sequence_dir', 'clean_train_audit_dir', 'raw_label_audit',
    'answers_manifest', 'source_prepare_manifest', 'enrichment_run_dir', 'ldap_dir',
}
SCHEMA = {
    'paths': PATH_KEYS,
    'split': {'fit_start', 'fit_end', 'validation_start', 'validation_end'},
    'data': {'max_users', 'seed', 'window_length', 'batch_rows'},
    'feature': {'impute', 'append_mask'},
    'sequence': {'scaler', 'epsilon'},
    'isolation_forest': {'n_estimators', 'max_samples', 'max_features', 'bootstrap',
                         'contamination', 'n_jobs'},
    'lstm': {'embedding_dim', 'hidden_size', 'latent_size', 'num_layers',
             'bidirectional', 'dropout', 'decoder_position'},
    'loss': {'categorical', 'numeric', 'boolean', 'reduction'},
    'train': {'device', 'dtype', 'threads', 'num_workers', 'batch_size', 'epochs',
              'lr', 'weight_decay', 'grad_clip_norm'},
    'benchmark': {'warmup_steps', 'max_seconds', 'reference_train_days',
                  'reference_train_steps', 'reference_epochs'},
}


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)


def read_json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'{path.name}: duplicate JSON key {key}')
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f'{path.name}: non-finite JSON {value}')

    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique,
                       parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError(f'{path.name}: JSON object required')
    return value


def validate_pilot_config(value: dict, root: Path = ROOT) -> dict:
    if not isinstance(value, dict) or set(value) != set(SCHEMA):
        raise ValueError('pilot config: unknown or missing sections')
    config = deepcopy(value)
    for section, keys in SCHEMA.items():
        if not isinstance(config[section], dict) or set(config[section]) != keys:
            raise ValueError(f'{section}: unknown or missing keys')
    for name, path in config['paths'].items():
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f'paths.{name}: non-empty path required')
        candidate = Path(path)
        config['paths'][name] = str((candidate if candidate.is_absolute() else root / candidate).resolve())
    if config['paths']['feature_dir'] == config['paths']['sequence_dir']:
        raise ValueError('feature and sequence paths must differ')

    for key, val in config['split'].items():
        if not isinstance(val, str):
            raise ValueError(f'split.{key}: ISO date required')
        try:
            if date.fromisoformat(val).isoformat() != val:
                raise ValueError()
        except ValueError as error:
            raise ValueError(f'split.{key}: ISO date required') from error
    # The approved scientific dates are fixed; data fixtures use the same bounds.
    expected_dates = dict(fit_start='2010-01-02', fit_end='2010-01-22',
                          validation_start='2010-01-23', validation_end='2010-01-31')
    if config['split'] != expected_dates:
        raise ValueError('split differs from the accepted January pilot')

    def integer(section, key, low, high):
        val = config[section][key]
        if type(val) is not int or not low <= val <= high:
            raise ValueError(f'{section}.{key}: integer in [{low}, {high}] required')

    integer('data', 'max_users', 1, 20)
    integer('data', 'seed', 0, 2**32 - 1)
    integer('data', 'batch_rows', 1, 65536)
    integer('data', 'window_length', 128, 128)
    for section, keys in SCHEMA.items():
        for key in keys - PATH_KEYS:
            val = config[section][key]
            if isinstance(val, (int, float)) and not isinstance(val, bool) and not math.isfinite(val):
                raise ValueError(f'{section}.{key}: non-finite value')

    fixed = {
        'feature': {'impute': 'median', 'append_mask': True},
        'sequence': {'scaler': 'standard', 'epsilon': 1e-6},
        'isolation_forest': {'n_estimators': 100, 'max_samples': 256, 'max_features': 1.0,
                             'bootstrap': False, 'contamination': 'auto', 'n_jobs': 2},
        'lstm': {'embedding_dim': 4, 'hidden_size': 32, 'latent_size': 16,
                 'num_layers': 1, 'bidirectional': False, 'dropout': 0,
                 'decoder_position': 'local_fixed_window'},
        'loss': {'categorical': 'cross_entropy', 'numeric': 'mse', 'boolean': 'bce_logits',
                 'reduction': 'valid_cell_mean'},
        'train': {'device': 'cpu', 'dtype': 'float32', 'threads': 2, 'num_workers': 0,
                  'batch_size': 64, 'epochs': 1, 'lr': 1e-3,
                  'weight_decay': 1e-5, 'grad_clip_norm': 1.0},
        'benchmark': {'warmup_steps': 3, 'reference_train_days': 105171,
                      'reference_train_steps': 3998777, 'reference_epochs': 20},
    }
    for section, expected in fixed.items():
        for key, accepted in expected.items():
            val = config[section][key]
            same_type = (type(val) is bool if type(accepted) is bool else
                         type(val) is int if type(accepted) is int else
                         type(val) in (int, float) if type(accepted) is float else
                         type(val) is str)
            if not same_type or val != accepted:
                raise ValueError(f'{section}.{key}: differs from accepted pilot')
    seconds = config['benchmark']['max_seconds']
    if type(seconds) not in (int, float) or not 0 < seconds <= 300:
        raise ValueError('benchmark.max_seconds: positive and at most 300 required')
    return config
