"""Check the declared CERT lineage without opening new evaluation labels."""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
from pathlib import Path

from .pilot_config import ROOT, read_json


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _resolve(path: str, root: Path) -> Path:
    value = Path(path)
    return (value if value.is_absolute() else root / value).resolve()


def verify_pilot_provenance(config: dict, root: Path = ROOT) -> dict:
    """SPEC-004 sections 4.1/11: fail closed on changed lineage or missing evidence."""
    paths = config['paths']
    files = {
        'clean_train_audit': Path(paths['clean_train_audit_dir']) / 'summary.json',
        'raw_label_audit': Path(paths['raw_label_audit']),
        'answers_manifest': Path(paths['answers_manifest']),
        'source_prepare_manifest': Path(paths['source_prepare_manifest']),
        'enrichment_manifest': Path(paths['enrichment_run_dir']) / 'manifest.json',
        'enrichment_verification': Path(paths['enrichment_run_dir']) / 'verification.json',
    }
    docs = {key: read_json(path) for key, path in files.items()}
    train = docs['clean_train_audit']['splits']['train']
    if (train['malicious_user_days'] != 0 or
            train['user_days'] != config['benchmark']['reference_train_days'] or
            train['rows_after_excluding_malicious_days'] != train['user_days']):
        raise ValueError('clean train audit does not establish the accepted clean-train cohort')
    raw = docs['raw_label_audit']
    if raw['answer_conflicts'] != 0:
        raise ValueError('raw label audit has answer conflicts')
    prepare = docs['source_prepare_manifest']
    if prepare['feature_count'] != 100 or prepare['sequence_fields'] != 24:
        raise ValueError('source feature/sequence schema changed')
    sources = {'logon', 'device', 'file', 'http', 'email'}
    if set(raw['raw_label_matching']) != sources or set(prepare['sources']) != sources:
        raise ValueError('source audit coverage changed')
    for source in sources:
        audit = raw['raw_label_matching'][source]
        if (any(audit[key] != 0 for key in ('missing_ids', 'duplicate_target_ids',
                                          'user_or_timestamp_mismatches')) or
                audit['found_unique'] != audit['expected_answer_events'] or
                audit['raw_event_rows'] != prepare['sources'][source]['rows']):
            raise ValueError(f'{source}: raw/source audit mismatch')
    manifest = docs['enrichment_manifest']
    verification = docs['enrichment_verification']
    if (manifest['same_user_days_across_branches'] is not True or
            verification['source_hashes_match_prior_inventory'] is not True or
            verification['coverage_matches_prior_inventory'] is not True):
        raise ValueError('enrichment preservation checks are incomplete')
    input_root = _resolve(manifest['config']['paths']['input_root'], root)
    output_root = _resolve(manifest['config']['paths']['output_root'], root)
    data_hashes = {}
    for key, branch in [('feature_dir', 'user_day_features'), ('sequence_dir', 'user_day_sequences')]:
        directory = Path(paths[key]).resolve()
        if directory != output_root / branch:
            raise ValueError(f'{key}: does not match the verified enrichment output')
        branch_verification = verification['branches'][branch]
        if any(branch_verification[name] is not True for name in
               ('original_values_preserved', 'metadata_verified', 'keys_and_indexes_verified')):
            raise ValueError(f'{branch}: original data was not verified')
        entries = manifest['branches'][branch]['files']
        # Match the recursive reader: an unverified nested part must never slip through.
        actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*.parquet')}
        if actual != set(entries):
            raise ValueError(f'{branch}: Parquet file coverage changed')
        for filename, entry in entries.items():
            if Path(filename).name != filename:
                raise ValueError('invalid manifest file name')
            output = directory / filename
            source_path = input_root / branch / filename
            out_hash, in_hash = sha256_file(output), sha256_file(source_path)
            if out_hash != entry['output_sha256'] or in_hash != entry['input_sha256']:
                raise ValueError(f'{branch}/{filename}: data checksum changed')
            data_hashes[f'{branch}/{filename}'] = {'input_sha256': in_hash, 'output_sha256': out_hash}
    # Only the two historical LDAP snapshots are needed to establish the domain.
    domain_checks = {}
    for month in ('2009-12', '2010-01'):
        path = Path(paths['ldap_dir']) / f'{month}.csv'
        digest = sha256_file(path)
        if digest != manifest['ldap_sha256'][path.name]:
            raise ValueError(f'{month}: historical LDAP checksum changed')
        with path.open(encoding='utf-8-sig', newline='') as stream:
            emails = [row['email'].strip().lower() for row in csv.DictReader(stream)]
        if not emails or any('@' not in email for email in emails):
            raise ValueError(f'{month}: cannot establish historical internal domain')
        counts = Counter(email.rsplit('@', 1)[1] for email in emails)
        if len(counts) != 1 or next(iter(counts)) != prepare['internal_domain']:
            raise ValueError(f'{month}: historical domain differs from source preprocessing')
        domain_checks[month] = {'rows': len(emails), 'domain': next(iter(counts)), 'sha256': digest}
    answers = docs['answers_manifest']
    return {
        'clean_train_summary': train,
        'evidence_sha256': {key: sha256_file(path) for key, path in files.items()},
        'data_sha256': data_hashes,
        'historical_domain_checks': domain_checks,
        'answers_archive_declared_sha256': answers['sha256'],
        'source_identity_assumption': 'User-supplied processed CERT r4.2 matches the audited CERT source.',
        'event_to_compressed_sequence_hash_chain_verified': False,
        'new_evaluation_labels_opened': False,
    }
