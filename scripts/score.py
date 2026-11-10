from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from itd.scoring.fusion import ScoreStats, fuse_scores


def main() -> int:
    parser = argparse.ArgumentParser(description="Late-fuse SPEC-002 branch reconstruction scores")
    parser.add_argument("--behaviour", type=Path, required=True)
    parser.add_argument("--sequence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alpha", type=float, default=0.5)
    args = parser.parse_args()
    behaviour = pd.read_parquet(args.behaviour)
    sequence = pd.read_parquet(args.sequence)
    frame = behaviour.merge(sequence, on=["user", "day", "split"], how="inner")
    train = frame.split.eq("train")
    beh_stats = ScoreStats.fit(frame.loc[train, "e_behaviour"])
    seq_stats = ScoreStats.fit(frame.loc[train, "e_sequence"])
    frame["z_behaviour"] = beh_stats.transform(frame.e_behaviour)
    frame["z_sequence"] = seq_stats.transform(frame.e_sequence)
    frame["base_score"] = fuse_scores(frame.z_behaviour, frame.z_sequence, args.alpha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)
    print(f"Wrote {len(frame):,} user-day scores to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
