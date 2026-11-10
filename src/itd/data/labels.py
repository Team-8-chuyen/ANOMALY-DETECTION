from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import re

import pandas as pd


@dataclass
class LabelResult:
    frame: pd.DataFrame
    available: bool


_R42_FILE = re.compile(r"r4\.2-([123])-([A-Z0-9]+)\.csv$")


def read_r42_answer_events(answer_root: Path) -> pd.DataFrame:
    """Parse only heterogeneous, headerless CERT r4.2 answer rows."""
    rows: list[dict[str, str]] = []
    if not answer_root.exists():
        return pd.DataFrame(columns=["event_id", "scenario", "actor_user"])
    for folder in ("r4.2-1", "r4.2-2", "r4.2-3"):
        for path in sorted((answer_root / folder).glob("*.csv")):
            match = _R42_FILE.match(path.name)
            if not match:
                continue
            scenario, actor = match.groups()
            with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                for fields in csv.reader(handle):
                    if len(fields) >= 5 and fields[1]:
                        rows.append({"event_id": fields[1], "scenario": scenario, "actor_user": actor})
    return pd.DataFrame(rows, columns=["event_id", "scenario", "actor_user"])


def build_user_day_labels(answer_root: Path, events: pd.DataFrame) -> LabelResult:
    """Build event-day labels without using other CERT releases (SPEC-002 §4.1)."""
    records = read_r42_answer_events(answer_root)
    columns = ["user", "day", "label", "scenario", "actor_user", "event_account"]
    if records.empty:
        return LabelResult(pd.DataFrame(columns=columns), False)
    source = events.copy()
    source["event_id"] = source["event_id"].astype(str)
    hit = source.merge(records.drop_duplicates(), on="event_id", how="inner")
    hit["day"] = pd.to_datetime(hit["day"]).dt.normalize()
    hit["event_account"] = hit["user"].astype(str)
    out = (hit.groupby(["user", "day"], as_index=False)
           .agg(scenario=("scenario", lambda x: "|".join(sorted(set(x)))),
                actor_user=("actor_user", lambda x: "|".join(sorted(set(x)))),
                event_account=("event_account", "first")))
    out["label"] = 1
    return LabelResult(out[columns], True)
