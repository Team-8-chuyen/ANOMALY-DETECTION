import importlib.util
import json
from pathlib import Path
import shutil

import pyarrow.parquet as pq

from itd.training.pilot_config import ROOT
from pilot_cli_fixtures import complete_config


def cli(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('pilot_cli_under_test', ROOT / 'scripts/run_if_lstm_pilot.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    shutil.copyfile(ROOT / 'requirements-models-cpu.txt', tmp_path / 'requirements-models-cpu.txt')
    monkeypatch.setattr('itd.training.pilot_benchmark._environment', lambda: 'synthetic test\n')
    return module


def test_cli_complete_outputs_and_refuses_overwrite(tmp_path, monkeypatch):
    config = complete_config(tmp_path)
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    module = cli(tmp_path, monkeypatch)
    run = tmp_path / 'runs/pilot'
    args = ['--config', str(path), '--run-dir', str(run)]
    assert module.main(args) == 0
    assert len(pq.read_table(run / 'validation_scores.parquet')) == 3
    before = (run / 'metrics.json').read_bytes()
    assert module.main(args) == 1
    assert (run / 'metrics.json').read_bytes() == before


def test_cli_provenance_failure_keeps_only_diagnostics(tmp_path, monkeypatch):
    config = complete_config(tmp_path)
    Path(config['paths']['source_prepare_manifest']).write_text('{}')
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    module = cli(tmp_path, monkeypatch)
    run = tmp_path / 'runs/not-published'
    assert module.main(['--config', str(path), '--run-dir', str(run)]) == 1
    assert not run.exists()
    staging = list(run.parent.glob('not-published-staging-*'))
    assert len(staging) == 1
    assert json.loads((staging[0] / 'metrics.json').read_text())['status'] == 'failed'


def test_cli_rejects_run_outside_runs_before_writing(tmp_path, monkeypatch):
    config = complete_config(tmp_path)
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    module = cli(tmp_path, monkeypatch)
    target = tmp_path / 'outside'
    assert module.main(['--config', str(path), '--run-dir', str(target)]) == 1
    assert not target.exists()
