"""Chunked CERT r4.2 canonicalization (SPEC-001 §4.1)."""
from __future__ import annotations

import hashlib
import re
import zlib
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import numpy as np
import pandas as pd

from itd.utils.config import AppConfig
from itd.utils.io import atomic_json, write_parquet

SOURCES = ("logon", "device", "file", "http", "email")
USECOLS = {
    "logon": ["id", "date", "user", "pc", "activity"],
    "device": ["id", "date", "user", "pc", "activity"],
    "file": ["id", "date", "user", "pc", "filename"],
    "http": ["id", "date", "user", "pc", "url"],
    "email": ["id", "date", "user", "pc", "to", "cc", "bcc", "from", "size", "attachments"],
}


def _bucket(user: str, count: int) -> int:
    return zlib.crc32(str(user).encode("utf-8")) % count


def _calendar(ts: pd.Series, work_hours: tuple[str, str]) -> pd.Series:
    start = int(work_hours[0][:2]) * 60 + int(work_hours[0][3:])
    end = int(work_hours[1][:2]) * 60 + int(work_hours[1][3:])
    minute = ts.dt.hour * 60 + ts.dt.minute
    return pd.Series(np.where(ts.dt.dayofweek >= 5, "WEEKEND", np.where((minute >= start) & (minute < end), "WORK_HOUR", "AFTER_HOUR")), index=ts.index)


def _split_people(value: object) -> list[str]:
    if pd.isna(value) or not str(value).strip():
        return []
    return [x.strip().lower() for x in re.split(r"[;,]", str(value)) if x.strip()]


def normalize_chunk(frame: pd.DataFrame, source: str, config: AppConfig, internal_domain: str | None = None) -> pd.DataFrame:
    """Normalize one raw chunk without retaining content or raw identifiers downstream."""
    out = pd.DataFrame()
    out["event_id"] = frame["id"].astype("string")
    out["timestamp"] = pd.to_datetime(frame["date"], format=config.data.datetime_format, errors="raise")
    out["day"] = out["timestamp"].dt.normalize()
    out["year_month"] = out["timestamp"].dt.strftime("%Y-%m")
    out["user"] = frame["user"].astype("string")
    out["pc"] = frame["pc"].astype("string").fillna("")
    out["source"] = source
    if source in ("logon", "device"):
        prefix = "DEVICE_" if source == "device" else ""
        out["event_token"] = prefix + frame["activity"].astype(str).str.upper()
    else:
        out["event_token"] = source.upper()
    out["calendar_context"] = _calendar(out["timestamp"], config.data.work_hours)
    out["user_bucket"] = out["user"].map(lambda x: _bucket(x, config.data.user_buckets)).astype("uint16")

    if source == "file":
        name = frame["filename"].fillna("").astype(str).map(lambda x: Path(x).name)
        suffix = name.map(lambda x: Path(x).suffix.lower().lstrip(".") if not x.startswith(".") else "")
        out["filename_hash"] = name.map(lambda x: hashlib.sha256(x.lower().encode()).hexdigest()[:16] if x else "")
        out["file_extension"] = suffix
        out["filename_length"] = name.str.len().astype("int32")
        out["multi_dot"] = name.str.count(r"\.").gt(1)
    elif source == "http":
        urls = frame["url"].fillna("").astype(str)
        parsed = urls.map(lambda x: urlsplit(x if "://" in x else "//" + x))
        out["url_hash"] = urls.map(lambda x: hashlib.sha256(x.encode()).hexdigest()[:16] if x else "")
        out["url_scheme"] = parsed.map(lambda x: x.scheme.lower())
        out["url_hostname"] = parsed.map(lambda x: (x.hostname or "").lower().rstrip("."))
        out["url_path_hash"] = parsed.map(lambda x: hashlib.sha256(x.path.encode()).hexdigest()[:16] if x.path else "")
        out["url_query_keys"] = parsed.map(lambda x: ";".join(sorted({k.lower() for k, _ in parse_qsl(x.query, keep_blank_values=True)})))
        out["hostname_length"] = out["url_hostname"].str.len().astype("int32")
        out["url_length"] = urls.str.len().astype("int32")
        out["path_depth"] = parsed.map(lambda x: len([p for p in x.path.split("/") if p])).astype("int16")
        out["query_present"] = parsed.map(lambda x: bool(x.query))
        out["https"] = out["url_scheme"].eq("https")
    elif source == "email":
        cols = {c: frame[c].map(_split_people) for c in ("to", "cc", "bcc")}
        recipients = pd.Series([a + b + c for a, b, c in zip(cols["to"], cols["cc"], cols["bcc"])], index=frame.index)
        domains = recipients.map(lambda xs: [x.rsplit("@", 1)[-1] for x in xs if "@" in x])
        out["to_count"] = cols["to"].str.len().astype("int16")
        out["cc_count"] = cols["cc"].str.len().astype("int16")
        out["bcc_count"] = cols["bcc"].str.len().astype("int16")
        out["recipient_count"] = recipients.str.len().astype("int16")
        out["recipient_hashes"] = recipients.map(lambda xs: ";".join(hashlib.sha256(x.encode()).hexdigest()[:16] for x in xs))
        out["external_count"] = domains.map(lambda xs: sum(d != internal_domain for d in xs) if internal_domain else 0).astype("int16")
        out["external_hashes"] = recipients.map(lambda xs: ";".join(hashlib.sha256(x.encode()).hexdigest()[:16] for x in xs if internal_domain and x.rsplit("@", 1)[-1] != internal_domain))
        attach = frame["attachments"].fillna("").astype(str).map(lambda x: [p for p in re.split(r"[;,]", x) if p.strip()])
        out["attachment_count"] = attach.str.len().astype("int16")
        out["email_size"] = pd.to_numeric(frame["size"], errors="coerce").fillna(0).astype("int64")
        sender = frame["from"].fillna("").astype(str).str.lower()
        out["sender_context"] = np.where(sender.eq(""), "MISSING", np.where(sender.str.endswith("@" + internal_domain) if internal_domain else False, "INTERNAL", "EXTERNAL"))
    return out


def infer_internal_domain(raw_root: Path) -> str | None:
    files = sorted((raw_root / "LDAP").glob("*.csv"))
    if not files:
        return None
    values: list[str] = []
    for file in files:
        ldap = pd.read_csv(file, usecols=["email"], dtype=str)
        values.extend(x.rsplit("@", 1)[-1].lower() for x in ldap["email"].dropna() if "@" in x)
    return pd.Series(values).mode().iat[0] if values else None


def build_canonical_events(config: AppConfig, force: bool = False) -> dict:
    root = config.paths.interim / "canonical_events"
    manifest_path = config.root / "data/artifacts/manifests/prepare_data.json"
    if root.exists() and any(root.rglob("*.parquet")) and not force:
        raise FileExistsError(f"Output exists: {root}; use --force")
    root.mkdir(parents=True, exist_ok=True)
    internal_domain = infer_internal_domain(config.paths.raw)
    manifest: dict = {"spec": "SPEC-001", "labels_available": False, "internal_domain": internal_domain, "sources": {}}
    for source in SOURCES:
        path = config.paths.raw / f"{source}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        total, part, min_ts, max_ts = 0, 0, None, None
        for chunk in pd.read_csv(path, usecols=USECOLS[source], chunksize=config.data.chunk_rows, dtype=str, keep_default_na=True):
            normalized = normalize_chunk(chunk, source, config, internal_domain)
            total += len(normalized)
            lo, hi = normalized["timestamp"].min(), normalized["timestamp"].max()
            min_ts = lo if min_ts is None or lo < min_ts else min_ts
            max_ts = hi if max_ts is None or hi > max_ts else max_ts
            for (month, bucket), group in normalized.groupby(["year_month", "user_bucket"], sort=False):
                target = root / f"source={source}" / f"year_month={month}" / f"user_bucket={int(bucket):03d}" / f"part-{part:06d}.parquet"
                write_parquet(group.drop(columns=["year_month", "user_bucket"]), target)
                part += 1
        manifest["sources"][source] = {"rows": total, "min_timestamp": min_ts, "max_timestamp": max_ts, "parts": part}
    atomic_json(manifest_path, manifest)
    return manifest


def load_bucket(interim: Path, bucket: int) -> pd.DataFrame:
    files = list((interim / "canonical_events").glob(f"source=*/year_month=*/user_bucket={bucket:03d}/*.parquet"))
    if not files:
        return pd.DataFrame()
    frame = pd.concat((pd.read_parquet(f) for f in files), ignore_index=True, sort=False)
    frame["source"] = frame["source"].astype(str)
    defaults = {
        "filename_hash":"", "file_extension":"", "filename_length":0, "multi_dot":False,
        "url_hash":"", "url_scheme":"", "url_hostname":"", "url_path_hash":"", "url_query_keys":"",
        "hostname_length":0, "url_length":0, "path_depth":0, "query_present":False, "https":False,
        "to_count":0, "cc_count":0, "bcc_count":0, "recipient_count":0, "recipient_hashes":"",
        "external_count":0, "external_hashes":"", "attachment_count":0, "email_size":0, "sender_context":"MISSING",
    }
    for column, default in defaults.items():
        if column not in frame: frame[column]=default
        else:
            with pd.option_context("future.no_silent_downcasting", True):
                frame[column]=frame[column].fillna(default).infer_objects(copy=False)
    return frame
