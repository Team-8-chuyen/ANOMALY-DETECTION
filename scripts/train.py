from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import torch
import pandas as pd
from torch.utils.data import DataLoader

from itd.models.feature_ae import FeatureAutoencoder
from itd.models.tcn_transformer_ae import TCNTransformerAutoencoder
from itd.training.loaders import behaviour_datasets, sequence_datasets
from itd.training.trainer import fit_reconstruction, reconstruction_scores, seed_everything
from itd.utils.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Train an unsupervised SPEC-002 branch")
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--branch", choices=("behaviour", "sequence"), required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    seed = int(config.raw["seed"])
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    run_id = args.run_id or f"{datetime.now():%Y%m%d-%H%M}-{args.branch}"
    run_dir = config.paths.runs / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if args.branch == "behaviour":
        section = config.raw["feature_ae"]
        datasets, _, keys = behaviour_datasets(config.paths.processed / "model_windows" / "behaviour.parquet")
        model = FeatureAutoencoder(100, tuple(section["hidden"]), section["latent"], section["dropout"])
        accumulation = 1
    else:
        section = config.raw["seq_transformer"]
        manifest = __import__("json").loads((config.paths.processed / "model_windows" / "manifest.json").read_text())
        datasets, encoding = sequence_datasets(config.paths.processed,
                                               config.paths.processed / "model_windows" / "split.parquet",
                                               int(manifest["max_len"]))
        model = TCNTransformerAutoencoder(len(encoding.token_vocab), len(encoding.continuous_columns),
                                          section["d_model"], tuple(section["tcn_dilations"]),
                                          section["n_layers"], section["n_heads"], section["ff_mult"],
                                          section["dropout"], int(manifest["max_len"]))
        accumulation = max(1, int(section["effective_batch_size"]) // int(section["batch_size"]))
        keys = {name: pd.DataFrame(dataset.keys, columns=["user", "day"])
                for name, dataset in datasets.items()}
    if args.smoke:
        section = dict(section); section["max_epochs"] = 2; section["patience"] = 2
    train_loader = DataLoader(datasets["train"], batch_size=int(section["batch_size"]), shuffle=True)
    validation_loader = DataLoader(datasets["validation"], batch_size=int(section["batch_size"]), shuffle=False)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(section["lr"]),
                                  weight_decay=float(section["weight_decay"]))
    result = fit_reconstruction(model, train_loader, validation_loader, optimizer,
                                run_dir / f"{args.branch}.pt", int(section["max_epochs"]),
                                int(section["patience"]), device, accumulation, args.resume)
    print(result)
    best = torch.load(run_dir / f"{args.branch}.best.pt", map_location=device, weights_only=False)
    model.load_state_dict(best["model"])
    score_parts = []
    for split in ("train", "validation", "test"):
        loader = DataLoader(datasets[split], batch_size=int(section["batch_size"]), shuffle=False)
        scores = reconstruction_scores(model, loader, device)
        part = keys[split].copy(); part["split"] = split; part[f"e_{args.branch}"] = scores
        if args.branch == "sequence":
            part = part.groupby(["user", "day", "split"], as_index=False)[f"e_{args.branch}"].mean()
        score_parts.append(part)
    pd.concat(score_parts, ignore_index=True).to_parquet(run_dir / f"{args.branch}_scores.parquet", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
