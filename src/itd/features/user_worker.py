"""Pickle-safe per-user worker used by Windows multiprocessing."""
from __future__ import annotations
from pathlib import Path
import pandas as pd

from itd.data.ldap import role_days_asof
from itd.features.count_features import build_behaviour_features
from itd.features.sequence_tokens import build_sequence_fields_polars
from itd.utils.io import write_parquet


def process_user(user_events: pd.DataFrame, ldap: pd.DataFrame, cfg, feature_path: Path, sequence_path: Path) -> str:
    if feature_path.is_file() and sequence_path.is_file():
        return "skipped"
    keys=user_events[["user","day"]].drop_duplicates().sort_values(["user","day"]).reset_index(drop=True)
    features=build_behaviour_features(user_events,role_days_asof(keys,ldap))
    sequence=build_sequence_fields_polars(user_events,cfg.sequence.gap_bucket_minutes,cfg.sequence.run_gap_minutes)
    write_parquet(features,feature_path); write_parquet(sequence,sequence_path)
    return "created"
