"""Create split and label artifacts without exposing labels to trainers."""
from __future__ import annotations

from pathlib import Path
import csv
import re

import numpy as np
import pandas as pd

from itd.data.datasets import choose_max_len
from itd.data.split import chronological_split, assert_no_temporal_overlap


_ANSWER_NAME = re.compile(r"r4\.2-([123])-([A-Z0-9]+)\.csv$")


def answer_user_days(answer_root: Path) -> pd.DataFrame:
    rows: list[dict] = []
    for folder in ("r4.2-1", "r4.2-2", "r4.2-3"):
        for path in sorted((answer_root / folder).glob("*.csv")):
            match = _ANSWER_NAME.match(path.name)
            if not match:
                continue
            scenario, actor = match.groups()
            with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                for fields in csv.reader(handle):
                    if len(fields) < 5:
                        continue
                    rows.append({"user": fields[3], "day": pd.to_datetime(fields[2], format="%m/%d/%Y %H:%M:%S").normalize(),
                                 "scenario": scenario, "actor_user": actor, "event_account": fields[3]})
    if not rows:
        return pd.DataFrame(columns=["user", "day", "label", "scenario", "actor_user", "event_account"])
    raw = pd.DataFrame(rows)
    out = (raw.groupby(["user", "day"], as_index=False)
           .agg(scenario=("scenario", lambda x: "|".join(sorted(set(x)))),
                actor_user=("actor_user", lambda x: "|".join(sorted(set(x)))),
                event_account=("event_account", "first")))
    out["label"] = np.int8(1)
    return out


def prepare_model_index(processed: Path, answer_root: Path, ratios=(0.60, 0.15, 0.25)) -> dict:
    feature_files = sorted((processed / "user_day_features").glob("*.parquet"))
    if not feature_files:
        raise FileNotFoundError("no Behaviour parquet files found")
    features = pd.concat((pd.read_parquet(path) for path in feature_files), ignore_index=True)
    features["day"] = pd.to_datetime(features["day"]).dt.normalize()
    split, boundaries = chronological_split(features["day"], ratios)
    index = features[["user", "day"]].copy()
    index["split"] = split
    labels = answer_user_days(answer_root)
    index = index.merge(labels, on=["user", "day"], how="left")
    index["label"] = index["label"].fillna(0).astype("int8")
    for column in ("scenario", "actor_user", "event_account"):
        index[column] = index[column].fillna("")
    assert_no_temporal_overlap(index)
    output = processed / "model_windows"
    output.mkdir(parents=True, exist_ok=True)
    index.to_parquet(output / "split.parquet", index=False)
    features.merge(index[["user", "day", "split"]], on=["user", "day"], how="left").to_parquet(
        output / "behaviour.parquet", index=False)
    sequence_files = sorted((processed / "user_day_sequences").glob("*.parquet"))
    lengths = []
    train_keys = set(map(tuple, index.loc[index.split == "train", ["user", "day"]].itertuples(index=False, name=None)))
    for path in sequence_files:
        frame = pd.read_parquet(path, columns=["user", "day", "event_index"])
        frame["day"] = pd.to_datetime(frame["day"]).dt.normalize()
        counts = frame.groupby(["user", "day"]).size()
        lengths.extend(int(value) for key, value in counts.items() if key in train_keys)
    max_len = choose_max_len(np.asarray(lengths))
    return {"train_end": str(boundaries.train_end.date()), "validation_end": str(boundaries.validation_end.date()),
            "rows": len(index), "positive_user_days": int(index.label.sum()), "max_len": max_len}
