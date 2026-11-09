"""Crash-safe checkpoint and single-run lock for SPEC-001 v1.1."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from itd.utils.io import atomic_json


@dataclass
class BucketCheckpoint:
    path: Path
    completed: set[int]

    @classmethod
    def load(cls, path: Path) -> "BucketCheckpoint":
        if not path.exists():
            return cls(path, set())
        raw=json.loads(path.read_text(encoding="utf-8"))
        return cls(path,{int(x) for x in raw.get("completed_buckets",[])})

    def mark_complete(self,bucket:int)->None:
        self.completed.add(int(bucket))
        atomic_json(self.path,{"spec":"SPEC-001-v1.1","completed_buckets":sorted(self.completed),"updated_at":datetime.now(timezone.utc).isoformat()})

    def is_complete(self,bucket:int,required_outputs:list[Path])->bool:
        return int(bucket) in self.completed and all(p.is_file() and p.stat().st_size>0 for p in required_outputs)


class ProcessLock:
    def __init__(self,path:Path): self.path=path; self.acquired=False
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        try:
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError as exc:
            owner=self.path.read_text(encoding="utf-8",errors="replace") if self.path.exists() else "unknown"
            raise RuntimeError(f"Another prepare_data process owns {self.path}: {owner}") from exc
        with os.fdopen(fd,"w",encoding="utf-8") as f: f.write(f"pid={os.getpid()}\n")
        self.acquired=True; return self
    def __exit__(self,exc_type,exc,tb):
        if self.acquired:
            self.path.unlink(missing_ok=True); self.acquired=False
