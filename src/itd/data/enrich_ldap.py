"""Preserve processed Parquet data while adding exact-month LDAP (SPEC-001 §14)."""
from __future__ import annotations

import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import shutil
import tempfile
import time

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

BRANCHES = ('user_day_features', 'user_day_features_ocean', 'user_day_sequences')
ADDED = {'role': pa.string(), 'department': pa.string(), 'role_missing': pa.bool_(),
         'department_missing': pa.bool_(), 'ldap_month': pa.string()}
SEQUENCE = ['event_token', 'time_sin', 'time_cos', 'gap_log1p', 'gap_bucket',
            'calendar_context', 'pc_context', 'run_count_log1p', 'run_span_log1p',
            'file_extension_id', 'filename_length_log1p', 'extension_present', 'multi_dot',
            'url_scheme_id', 'hostname_length_log1p', 'url_length_log1p', 'path_depth_log1p',
            'query_present', 'recipient_count_log1p', 'external_recipient_ratio', 'bcc_present',
            'attachment_count_log1p', 'email_size_log1p', 'sender_context']


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_ldap_metadata(ldap_dir: Path) -> dict[tuple[str, str], dict[str, str]]:
    """SPEC-001 §14.3: no forward lookup, carry-forward or duplicate overwrite."""
    files = sorted(ldap_dir.glob('*.csv'))
    if not files:
        raise ValueError(f'{ldap_dir}: no LDAP CSV files')
    mapping = {}
    for path in files:
        try:
            month = datetime.strptime(path.stem, '%Y-%m').strftime('%Y-%m')
        except ValueError as error:
            raise ValueError(f'{path.name}: expected YYYY-MM.csv') from error
        if month != path.stem:
            raise ValueError(f'{path.name}: expected YYYY-MM.csv')
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames or []
            if len(fields) != len(set(fields)) or not {'user_id', 'role', 'department'} <= set(fields):
                raise ValueError(f'{path.name}: invalid LDAP header')
            count = 0
            for line, row in enumerate(reader, 2):
                if None in row or any(v is None for v in row.values()) or not row['user_id'].strip():
                    raise ValueError(f'{path.name}:{line}: invalid LDAP row')
                key = (row['user_id'].strip(), month)
                if key in mapping:
                    raise ValueError(f'{path.name}:{line}: duplicate user/month')
                mapping[key] = {name: row[name].strip() or 'UNKNOWN' for name in ('role', 'department')}
                count += 1
            if not count:
                raise ValueError(f'{path.name}: no LDAP records')
    return mapping


def _keys(batch: pa.RecordBatch) -> list[tuple[str, str]]:
    users, days = batch.column('user'), batch.column('day')
    if not pa.types.is_string(users.type) or not pa.types.is_timestamp(days.type) or days.type.tz:
        raise ValueError('user must be string and day a timezone-free timestamp')
    if users.null_count or days.null_count:
        raise ValueError('null user/day')
    midnight = pc.cast(pc.cast(days, pa.date32()), days.type)
    if pc.any(pc.not_equal(days, midnight)).as_py():
        raise ValueError('day must be midnight')
    user_values = users.to_pylist()
    if any(not user.strip() for user in user_values):
        raise ValueError('blank user')
    return list(zip((u.strip() for u in user_values),
                    pc.cast(pc.cast(days, pa.date32()), pa.string()).to_pylist()))


def enrich_batch(batch: pa.RecordBatch, metadata: dict) -> pa.RecordBatch:
    if set(batch.schema.names) & set(ADDED):
        raise ValueError('metadata columns already exist')
    keys = _keys(batch)
    # Reuse metadata for repeated sequence events without changing their order.
    lookup = {}
    rows = []
    for user, day in keys:
        key = (user, day[:7])
        if key not in lookup:
            group = metadata.get(key, {})
            values = [(group.get(n, '').strip() or 'UNKNOWN') for n in ('role', 'department')]
            lookup[key] = (*values, values[0] == 'UNKNOWN', values[1] == 'UNKNOWN', key[1])
        rows.append(lookup[key])
    clean = batch.replace_schema_metadata(None)
    table = pa.Table.from_batches([clean])
    for i, (name, dtype) in enumerate(ADDED.items()):
        table = table.append_column(name, pa.array([row[i] for row in rows], type=dtype))
    return table.to_batches()[0]


def _validate_schema(schema: pa.Schema, branch: str) -> None:
    names = schema.names
    if len(names) != len(set(names)) or set(names) & set(ADDED):
        raise ValueError('duplicate or pre-existing metadata columns')
    required = {'user': pa.string(), 'day': pa.timestamp('ns')}
    if branch == 'user_day_sequences':
        strings = {'event_token', 'calendar_context', 'pc_context', 'file_extension_id',
                   'url_scheme_id', 'sender_context'}
        bools = {'extension_present', 'multi_dot', 'query_present', 'bcc_present'}
        required.update({name: pa.string() if name in strings else pa.bool_() if name in bools
                         else pa.int64() if name == 'gap_bucket' else pa.float64()
                         for name in SEQUENCE})
        required.update(event_index=pa.int64(), attribute_mask=pa.string())
    else:
        required.update({f'f{i:03d}': pa.float64() for i in range(1, 101)})
        required.update({f'm{i:03d}': pa.bool_() for i in range(1, 101)})
        if branch == 'user_day_features_ocean':
            required.update({name: pa.int64() for name in 'OCEAN'})
    if set(names) != set(required) or any(schema.field(n).type != t for n, t in required.items()):
        raise ValueError(f'{branch}: input schema mismatch')


class _KeyAudit:
    def __init__(self, sequence: bool):
        self.sequence, self.keys = sequence, set()
        self.previous, self.expected = None, 0

    def add(self, batch: pa.RecordBatch) -> list[tuple[str, str]]:
        keys = _keys(batch)
        indexes = batch.column('event_index').to_pylist() if self.sequence else None
        for i, key in enumerate(keys):
            if not self.sequence or key != self.previous:
                if key in self.keys:
                    raise ValueError('duplicate or non-contiguous user/day')
                self.keys.add(key)
                self.previous, self.expected = key, 0
            if self.sequence:
                if indexes[i] != self.expected:
                    raise ValueError('event_index must start at zero and be contiguous')
                self.expected += 1
        return keys


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def enrich_dataset(config: dict) -> dict:
    start = time.perf_counter()
    source, ldap, output = (Path(config['paths'][n]).resolve() for n in ('input_root', 'ldap_dir', 'output_root'))
    if not source.is_dir() or not ldap.is_dir():
        raise ValueError('input_root and ldap_dir must exist')
    if any(_within(output, p) or _within(p, output) for p in (source, ldap)):
        raise ValueError('output must not overlap input or LDAP')
    if output.exists():
        raise FileExistsError(f'{output}: already exists')
    if config['branches'] != list(BRANCHES):
        raise ValueError('all three branches are required in the specified order')
    size = config['batch_rows']
    if type(size) is not int or size < 1 or config['compression'] != 'zstd':
        raise ValueError('invalid batch_rows or compression')
    ldap_hashes = {p.name: _hash(p) for p in sorted(ldap.glob('*.csv'))}
    metadata = load_ldap_metadata(ldap)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f'.{output.name}-', dir=output.parent)).resolve()
    manifest = {'spec': 'SPEC-001-v1.1', 'config': config, 'environment': {
        'python': platform.python_version(), 'pyarrow': pa.__version__},
        'ldap_sha256': ldap_hashes, 'branches': {}}
    reference = None
    try:
        for branch in BRANCHES:
            files = sorted((source / branch).glob('*.parquet'))
            if not files:
                raise ValueError(f'{branch}: no Parquet files')
            target = staging / branch
            target.mkdir()
            schema = pq.ParquetFile(files[0]).schema_arrow
            _validate_schema(schema, branch)
            before, after = _KeyAudit(branch == 'user_day_sequences'), _KeyAudit(branch == 'user_day_sequences')
            entry = {'rows': 0, 'files': {}, 'schema_before': {f.name: str(f.type) for f in schema},
                     'missing_rows': {'role': 0, 'department': 0}}
            for path in files:
                if not _within(path.resolve(), source) or path.is_symlink():
                    raise ValueError('input file escapes input_root')
                original_hash = _hash(path)
                reader = pq.ParquetFile(path)
                if not schema.equals(reader.schema_arrow, check_metadata=False):
                    raise ValueError(f'{branch}/{path.name}: bucket schema mismatch')
                writer, count = None, 0
                destination = target / path.name
                try:
                    for batch in reader.iter_batches(batch_size=size):
                        if not batch.num_rows:
                            continue
                        before.add(batch)
                        enriched = enrich_batch(batch, metadata)
                        if writer is None:
                            writer = pq.ParquetWriter(destination, enriched.schema, compression='zstd')
                        writer.write_batch(enriched)
                        count += batch.num_rows
                        for name in ('role', 'department'):
                            entry['missing_rows'][name] += pc.sum(enriched.column(f'{name}_missing')).as_py()
                finally:
                    if writer is not None:
                        writer.close()
                if not count:
                    raise ValueError(f'{branch}/{path.name}: empty bucket')
                # SPEC-001 §14.5: read back every original value and every added value.
                with pq.ParquetFile(destination) as verification:
                    original_iter = reader.iter_batches(batch_size=size)
                    written_iter = verification.iter_batches(batch_size=size)
                    try:
                        for original in original_iter:
                            written = next(written_iter, None)
                            if written is None or not pa.Table.from_batches([original]).equals(
                                    pa.Table.from_batches([written]).select(schema.names), check_metadata=False):
                                raise ValueError('readback changed original values or row order')
                            expected = enrich_batch(original, metadata)
                            if not expected.equals(written, check_metadata=False):
                                raise ValueError('metadata readback mismatch')
                            after.add(written)
                        if next(written_iter, None) is not None:
                            raise ValueError('readback contains extra rows')
                    finally:
                        written_iter.close()
                        original_iter.close()
                reader.close()
                if original_hash != _hash(path):
                    raise ValueError('input changed during processing')
                entry['rows'] += count
                entry['files'][path.name] = {'rows': count, 'input_sha256': original_hash,
                                            'output_sha256': _hash(destination)}
                print(f'{branch}/{path.name}: {count} rows verified', flush=True)
            if before.keys != after.keys or (reference is not None and before.keys != reference):
                raise ValueError('user/day key sets do not match')
            reference = before.keys if reference is None else reference
            days = [d for _, d in before.keys]
            entry.update(user_days=len(before.keys), users=len({u for u, _ in before.keys}),
                         start=min(days), end=max(days), original_values_preserved=True,
                         metadata_verified=True, keys_and_indexes_verified=True)
            entry['missing_user_days'] = {name: sum(metadata.get((u, d[:7]), {}).get(name, 'UNKNOWN') == 'UNKNOWN'
                                                   for u, d in before.keys) for name in ('role', 'department')}
            entry['schema_after'] = {**entry['schema_before'], **{n: str(t) for n, t in ADDED.items()}}
            manifest['branches'][branch] = entry
        if ldap_hashes != {p.name: _hash(p) for p in sorted(ldap.glob('*.csv'))}:
            raise ValueError('LDAP changed during processing')
        manifest.update(elapsed_seconds=round(time.perf_counter() - start, 6),
                        same_user_days_across_branches=True)
        (staging / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        staging.rename(output)
    except BaseException:
        # Only remove the fresh task-owned directory, after verifying its parent.
        if staging.parent == output.parent and staging.name.startswith(f'.{output.name}-') and staging.exists():
            shutil.rmtree(staging)
        raise
    return manifest
