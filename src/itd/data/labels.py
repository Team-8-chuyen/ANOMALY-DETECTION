from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

@dataclass
class LabelResult:
    frame: pd.DataFrame
    available: bool

def build_user_day_labels(answer_root: Path, events: pd.DataFrame) -> LabelResult:
    files=list(answer_root.rglob("*.csv")) if answer_root.exists() else []
    if not files: return LabelResult(pd.DataFrame(columns=["user","day","label","scenario"]),False)
    ids=set()
    for file in files:
        df=pd.read_csv(file,dtype=str)
        if "id" in df: ids.update(df.id.dropna())
    hit=events[events.event_id.astype(str).isin(ids)]
    out=hit.groupby(["user","day"]).size().rename("n").reset_index(); out["label"]=1; out["scenario"]="unknown"
    return LabelResult(out.drop(columns="n"),True)
