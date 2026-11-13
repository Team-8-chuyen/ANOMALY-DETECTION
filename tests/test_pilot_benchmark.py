from copy import deepcopy
import json

import numpy as np
import pyarrow.parquet as pq
import pytest

from itd.data.pilot_dataset import load_pilot_data
from itd.data.sequence_preprocessing import SequencePreprocessor
from itd.training.pilot_benchmark import estimate_runtime, load_lstm_checkpoint, run_pilot
from itd.training.pilot_config import read_json, validate_pilot_config
from itd.training.pilot_provenance import verify_pilot_provenance
from itd.training.sequence_trainer import score_days
from pilot_cli_fixtures import complete_config


def test_extrapolation_scales_training_only_and_is_not_a_confidence_interval():
    result = estimate_runtime({'status': 'complete', 'train_epoch_seconds': 2,
                                'n_fit_days': 10, 'n_fit_valid_steps': 30},
                               {'reference_train_days': 100, 'reference_train_steps': 600,
                                'reference_epochs': 20})
    assert result['scenarios']['valid_steps']['full_train_one_epoch_seconds'] == 40
    assert result['scenarios']['user_days']['full_train_epochs_seconds'] == 400
    assert result['confidence_interval'] is None
    assert result['full_total_wall_seconds'] is None
    assert result['full_if_fit_seconds'] is None


@pytest.mark.parametrize('status', ['incomplete', 'failed'])
def test_partial_run_has_no_extrapolation(status):
    assert estimate_runtime({'status': status}, {})['scenarios'] is None


@pytest.mark.parametrize('seconds', [float('nan'), float('inf'), -1, True])
def test_runtime_rejects_invalid_measured_values(seconds):
    with pytest.raises(ValueError):
        estimate_runtime({'status': 'complete', 'train_epoch_seconds': seconds,
                          'n_fit_days': 1, 'n_fit_valid_steps': 1},
                         {'reference_train_days': 1, 'reference_train_steps': 1, 'reference_epochs': 1})


def test_provenance_accepts_fixture_and_rejects_tampered_or_nested_part(tmp_path):
    config = complete_config(tmp_path)
    evidence = verify_pilot_provenance(config)
    assert evidence['new_evaluation_labels_opened'] is False
    assert evidence['event_to_compressed_sequence_hash_chain_verified'] is False
    directory = tmp_path / 'output/user_day_sequences'
    nested = directory / 'unverified'
    nested.mkdir()
    source = next(directory.glob('*.parquet'))
    (nested / 'extra.parquet').write_bytes(source.read_bytes())
    with pytest.raises(ValueError, match='coverage changed'):
        verify_pilot_provenance(config)
    (nested / 'extra.parquet').unlink()
    source.write_bytes(source.read_bytes() + b'tampered')
    with pytest.raises(ValueError, match='checksum changed'):
        verify_pilot_provenance(config)


def test_provenance_rejects_unclean_audit_and_changed_historical_domain(tmp_path):
    config = complete_config(tmp_path)
    path = tmp_path / 'clean-audit/summary.json'
    old = path.read_text()
    data = json.loads(old)
    data['splits']['train']['malicious_user_days'] = 1
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='clean train audit'):
        verify_pilot_provenance(config)
    path.write_text(old)
    (tmp_path / 'ldap/2009-12.csv').write_text('email\na@future.test\n')
    with pytest.raises(ValueError, match='historical LDAP checksum'):
        verify_pilot_provenance(config)


def test_one_epoch_full_pipeline_reproducible_and_checkpoint_fingerprinted(tmp_path, monkeypatch):
    config = complete_config(tmp_path)
    data = load_pilot_data(config)
    monkeypatch.setattr('itd.training.pilot_benchmark._environment', lambda: 'synthetic test\n')
    first = run_pilot(data, config, tmp_path / 'run1')
    second = run_pilot(data, config, tmp_path / 'run2')
    assert first.status == second.status == 'complete'
    assert first.metrics['completed_epochs'] == 1
    assert first.metrics['train']['n_windows'] == 6
    assert first.metrics['train']['valid_steps'] == 18
    assert first.metrics['feature_input_columns'] == 200
    a = pq.read_table(tmp_path / 'run1/validation_scores.parquet')
    b = pq.read_table(tmp_path / 'run2/validation_scores.parquet')
    assert len(a) == 3 and a.schema.field('day').type.unit == 'ns'
    for column in ('e_feature_raw', 'e_sequence_raw'):
        np.testing.assert_allclose(a[column].to_numpy(), b[column].to_numpy(), atol=1e-6, rtol=1e-6)
    assert 'selected_tier' not in a.column_names and 'label' not in a.column_names
    sequence = SequencePreprocessor.from_dict(read_json(tmp_path / 'run1/sequence_preprocessor.json'))
    model = load_lstm_checkpoint(tmp_path / 'run1/lstm_model.pt', config, sequence)
    assert model.training is False
    reloaded = score_days(model, data.validation_days, sequence, config)
    np.testing.assert_allclose([row.e_sequence_raw for row in reloaded],
                               a['e_sequence_raw'].to_numpy(), atol=1e-6, rtol=1e-6)
    changed = deepcopy(config)
    changed['data']['seed'] += 1
    with pytest.raises(ValueError, match='fingerprint'):
        load_lstm_checkpoint(tmp_path / 'run1/lstm_model.pt', changed, sequence)
    with pytest.raises(FileExistsError):
        run_pilot(data, config, tmp_path / 'run1')


def test_warmup_updates_cannot_survive_into_measured_epoch(tmp_path, monkeypatch):
    config = complete_config(tmp_path)
    data = load_pilot_data(config)
    monkeypatch.setattr('itd.training.pilot_benchmark._environment', lambda: 'synthetic test\n')
    run_pilot(data, config, tmp_path / 'warmed')
    # Synthetic control only: the approved real pilot still always has three warmup steps.
    control = deepcopy(config)
    control['benchmark']['warmup_steps'] = 0
    run_pilot(data, control, tmp_path / 'cold')
    for column in ('e_feature_raw', 'e_sequence_raw'):
        warm = pq.read_table(tmp_path / 'warmed/validation_scores.parquet')[column].to_numpy()
        cold = pq.read_table(tmp_path / 'cold/validation_scores.parquet')[column].to_numpy()
        np.testing.assert_allclose(warm, cold, atol=1e-6, rtol=1e-6)


def test_deadline_never_publishes_fake_completed_epoch(tmp_path):
    config = complete_config(tmp_path)
    data = load_pilot_data(config)
    ticks = iter(range(0, 100000, 100))
    result = run_pilot(data, config, tmp_path / 'incomplete', clock=lambda: next(ticks))
    assert result.status == 'incomplete'
    assert result.runtime_estimate['scenarios'] is None
    assert not (tmp_path / 'incomplete/validation_scores.parquet').exists()


def test_artifact_write_failure_clears_completed_runtime_estimate(tmp_path, monkeypatch):
    config = complete_config(tmp_path)
    data = load_pilot_data(config)
    def fail():
        raise OSError('simulated environment write failure')
    monkeypatch.setattr('itd.training.pilot_benchmark._environment', fail)
    with pytest.raises(OSError):
        run_pilot(data, config, tmp_path / 'failed')
    assert read_json(tmp_path / 'failed/metrics.json')['status'] == 'failed'
    assert read_json(tmp_path / 'failed/runtime-estimate.json')['scenarios'] is None


@pytest.mark.parametrize('section,key,value', [
    ('data', 'max_users', True), ('train', 'epochs', 20), ('lstm', 'hidden_size', 64),
    ('split', 'fit_end', '2010-02-01'), ('benchmark', 'max_seconds', float('inf')),
    ('feature', 'append_mask', False), ('data', 'window_length', True),
])
def test_config_rejects_scope_changes(tmp_path, section, key, value):
    config = complete_config(tmp_path)
    config[section][key] = value
    with pytest.raises(ValueError):
        validate_pilot_config(config)


def test_config_rejects_duplicate_and_unknown_keys(tmp_path):
    path = tmp_path / 'duplicate.json'
    path.write_text('{"data": {}, "data": {}}')
    with pytest.raises(ValueError, match='duplicate'):
        read_json(path)
    config = complete_config(tmp_path)
    config['data']['unknown'] = 1
    with pytest.raises(ValueError, match='unknown'):
        validate_pilot_config(config)
