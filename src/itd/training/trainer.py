"""Deterministic reconstruction trainer with atomic resume checkpoints."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import random

import numpy as np
import torch


@dataclass(frozen=True)
class TrainResult:
    best_epoch: int
    best_validation_loss: float
    epochs_completed: int


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    if torch.cuda.is_available():
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def atomic_torch_save(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    os.replace(temporary, path)


def _batch_loss(model, batch, device: torch.device) -> torch.Tensor:
    if isinstance(batch, dict):
        inputs = {key: value.to(device) for key, value in batch.items()}
        return model.loss_per_sample(**inputs).mean()
    values, masks = (value.to(device) for value in batch)
    return model.loss_per_sample(values, masks).mean()


def evaluate_reconstruction(model, loader, device: torch.device) -> float:
    model.eval()
    total = 0.0
    count = 0
    with torch.no_grad():
        for batch in loader:
            loss = _batch_loss(model, batch, device)
            if not torch.isfinite(loss):
                raise FloatingPointError("non-finite validation loss")
            batch_size = next(iter(batch.values())).shape[0] if isinstance(batch, dict) else batch[0].shape[0]
            total += float(loss) * batch_size
            count += batch_size
    return total / max(count, 1)


def fit_reconstruction(model, train_loader, validation_loader, optimizer, checkpoint: Path,
                       max_epochs: int, patience: int, device: torch.device,
                       accumulation_steps: int = 1, resume: bool = False) -> TrainResult:
    start_epoch = 0
    best_epoch = -1
    best_loss = float("inf")
    stale = 0
    model.to(device)
    if resume and checkpoint.exists():
        state = torch.load(checkpoint, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        start_epoch = int(state["epoch"]) + 1
        best_epoch = int(state["best_epoch"])
        best_loss = float(state["best_validation_loss"])
    epochs_completed = start_epoch
    for epoch in range(start_epoch, max_epochs):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        for index, batch in enumerate(train_loader):
            loss = _batch_loss(model, batch, device) / accumulation_steps
            if not torch.isfinite(loss):
                raise FloatingPointError("non-finite training loss")
            loss.backward()
            if (index + 1) % accumulation_steps == 0:
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
        validation_loss = evaluate_reconstruction(model, validation_loader, device)
        improved = validation_loss < best_loss
        if improved:
            best_loss = validation_loss
            best_epoch = epoch
            stale = 0
            atomic_torch_save({"epoch": epoch, "model": model.state_dict(),
                               "best_validation_loss": best_loss},
                              checkpoint.with_name(checkpoint.stem + ".best" + checkpoint.suffix))
        else:
            stale += 1
        atomic_torch_save({"epoch": epoch, "best_epoch": best_epoch,
                           "best_validation_loss": best_loss, "model": model.state_dict(),
                           "optimizer": optimizer.state_dict(), "is_best": improved}, checkpoint)
        epochs_completed = epoch + 1
        if stale >= patience:
            break
    return TrainResult(best_epoch, best_loss, epochs_completed)


def reconstruction_scores(model, loader, device: torch.device) -> np.ndarray:
    model.eval()
    values = []
    with torch.no_grad():
        for batch in loader:
            if isinstance(batch, dict):
                inputs = {key: value.to(device) for key, value in batch.items()}
                loss = model.loss_per_sample(**inputs)
            else:
                tensors = [value.to(device) for value in batch]
                loss = model.loss_per_sample(*tensors)
            values.append(loss.detach().cpu().numpy())
    return np.concatenate(values) if values else np.empty(0, dtype=float)
