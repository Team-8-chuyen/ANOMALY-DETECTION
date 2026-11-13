"""Synthetic lineage for complete CLI tests; no real CERT labels are opened."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pyarrow.parquet as pq

from itd.training.pilot_config import ROOT
from itd.training.pilot_provenance import sha256_file
from pilot_fixtures import write_pilot_fixture


def complete_config(root: Path) -> dict:
    config = json.loads((ROOT / 'configs/experiments/if_lstm_cpu_pilot.json').read_text())
    partial = write_pilot_fixture(root / 'output')
    config['split'], config['data'] = partial['split'], partial['data']
    source = root / 'original'
    output = root / 'output'
    branches = {}
    for key, branch in [('feature_dir', 'user_day_features'), ('sequence_dir', 'user_day_sequences')]:
        old = Path(partial['paths'][key])
        directory = output / branch
        old.rename(directory)
        original = source / branch
        original.mkdir(parents=True)
        entries = {}
        for path in directory.glob('*.parquet'):
            copy = original / path.name
            shutil.copyfile(path, copy)
            entries[path.name] = {'rows': pq.read_metadata(path).num_rows,
                                  'input_sha256': sha256_file(copy), 'output_sha256': sha256_file(path)}
        branches[branch] = {'files': entries}
        config['paths'][key] = str(directory)
    ldap = root / 'ldap'
    ldap.mkdir()
    ldap_hashes = {}
    for month in ('2009-12', '2010-01'):
        path = ldap / f'{month}.csv'
        path.write_text('email\na@unit.test\nb@unit.test\n', encoding='utf-8')
        ldap_hashes[path.name] = sha256_file(path)
    audit = root / 'clean-audit'
    audit.mkdir()
    enrichment = root / 'enrichment'
    enrichment.mkdir()
    sources = {'logon', 'device', 'file', 'http', 'email'}
    def write(path, value):
        path.write_text(json.dumps(value), encoding='utf-8')
        return str(path)
    write(audit / 'summary.json', {'splits': {'train': {'user_days': 105171,
          'malicious_user_days': 0, 'rows_after_excluding_malicious_days': 105171}}})
    config['paths'].update(
        clean_train_audit_dir=str(audit), enrichment_run_dir=str(enrichment), ldap_dir=str(ldap),
        raw_label_audit=write(root / 'raw-audit.json', {'answer_conflicts': 0,
            'raw_label_matching': {name: {'missing_ids': 0, 'duplicate_target_ids': 0,
                'user_or_timestamp_mismatches': 0, 'found_unique': 0,
                'expected_answer_events': 0, 'raw_event_rows': 1} for name in sources}}),
        answers_manifest=write(root / 'answers.json', {'source': 'synthetic fixture', 'sha256': 'a' * 64}),
        source_prepare_manifest=write(root / 'prepare.json', {'feature_count': 100,
            'sequence_fields': 24, 'internal_domain': 'unit.test',
            'sources': {name: {'rows': 1} for name in sources}}))
    write(enrichment / 'manifest.json', {'same_user_days_across_branches': True,
        'config': {'paths': {'input_root': str(source), 'output_root': str(output)}},
        'branches': branches, 'ldap_sha256': ldap_hashes})
    write(enrichment / 'verification.json', {'source_hashes_match_prior_inventory': True,
        'coverage_matches_prior_inventory': True,
        'branches': {name: {'original_values_preserved': True, 'metadata_verified': True,
                            'keys_and_indexes_verified': True} for name in branches}})
    return deepcopy(config)
