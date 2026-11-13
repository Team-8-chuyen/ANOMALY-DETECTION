"""Run SPEC-004's bounded CPU pilot, publishing only complete paired scores."""
from __future__ import annotations

import time

CLI_STARTED = time.perf_counter()

import argparse
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from itd.training.pilot_config import json_text, read_json, validate_pilot_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    staging = None
    try:
        config = validate_pilot_config(read_json(args.config), ROOT)
        target = args.run_dir.resolve()
        if not target.is_relative_to((ROOT / 'runs').resolve()) or target == (ROOT / 'runs').resolve():
            raise ValueError('--run-dir must be a new child directory under project runs/')
        if target.exists():
            raise FileExistsError('run directory already exists; choose a new run ID')
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f'{target.name}-staging-', dir=target.parent))

        # Heavy imports belong to setup, never the measured training epoch.
        from itd.data.pilot_dataset import load_pilot_data
        from itd.training.pilot_benchmark import run_pilot
        from itd.training.pilot_provenance import sha256_file, verify_pilot_provenance

        timings = {'import_setup_seconds': time.perf_counter() - CLI_STARTED}
        mark = time.perf_counter()
        provenance = verify_pilot_provenance(config, ROOT)
        timings['provenance_seconds'] = time.perf_counter() - mark
        mark = time.perf_counter()
        data = load_pilot_data(config)
        timings['data_read_seconds'] = time.perf_counter() - mark
        data.provenance.update(provenance)
        implementation_files = list((ROOT / 'src' / 'itd').rglob('*.py')) + [
            Path(__file__).resolve(), ROOT / 'requirements-models-cpu.txt', args.config.resolve()]
        data.provenance['implementation_sha256'] = {
            str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path): sha256_file(path)
            for path in implementation_files}
        result = run_pilot(data, config, staging, initial_timings=timings, start_time=CLI_STARTED)
        if result.status != 'complete':
            print(json_text({'status': result.status, 'diagnostics': str(staging)}))
            return 2
        if target.exists():
            raise FileExistsError('run target appeared while computing; refusing to overwrite')
        staging.rename(target)
        print(json_text({'status': result.status, 'run_dir': str(target),
                         'n_fit_days': result.metrics['n_fit_days'],
                         'n_validation_days': result.metrics['n_validation_days'],
                         'timings_seconds': result.metrics['timings_seconds'],
                         'runtime_estimate': result.runtime_estimate}))
        return 0
    except Exception as error:
        detail = {'status': 'failed', 'error': f'{type(error).__name__}: {error}'}
        if staging is not None and staging.exists():
            # Retain diagnostics; the intended run target is never published on failure.
            if not (staging / 'metrics.json').exists():
                (staging / 'metrics.json').write_text(json_text(detail) + '\n', encoding='utf-8')
            with (staging / 'log.txt').open('a', encoding='utf-8') as stream:
                stream.write(detail['error'] + '\n')
            detail['diagnostics'] = str(staging)
        print(json_text(detail), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
