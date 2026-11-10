from __future__ import annotations

import argparse
import json

from itd.data.model_data import prepare_model_index
from itd.utils.config import load_config
from itd.utils.io import atomic_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare chronological model index for SPEC-002")
    parser.add_argument("--config", default="configs/base.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    ratios = tuple(config.raw["split"]["ratios"])
    result = prepare_model_index(config.paths.processed, config.paths.raw / "answers", ratios)
    destination = config.paths.processed / "model_windows" / "manifest.json"
    atomic_json(destination, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
