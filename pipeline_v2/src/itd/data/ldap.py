from __future__ import annotations

from pathlib import Path
import pandas as pd


def load_ldap_snapshots(path: Path) -> pd.DataFrame:
    frames = []
    for file in sorted(path.glob("*.csv")):
        df = pd.read_csv(file, dtype=str)
        df["snapshot_month"] = pd.Period(file.stem, freq="M").to_timestamp()
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def role_days_asof(users_days: pd.DataFrame, ldap: pd.DataFrame) -> pd.Series:
    """Past-only consecutive days in current LDAP role (SPEC-001 §4.3)."""
    if ldap.empty:
        return pd.Series(0.0, index=users_days.index)
    histories = {u: g.sort_values("snapshot_month") for u, g in ldap.groupby("user_id")}
    values = []
    for row in users_days.itertuples():
        hist = histories.get(row.user)
        if hist is None:
            values.append(0.0); continue
        eligible = hist[hist["snapshot_month"] <= pd.Timestamp(row.day)]
        if eligible.empty:
            values.append(0.0); continue
        role = eligible.iloc[-1]["role"]
        same = eligible[eligible["role"] == role]
        values.append(float((pd.Timestamp(row.day) - same.iloc[0]["snapshot_month"]).days + 1))
    return pd.Series(values, index=users_days.index)
