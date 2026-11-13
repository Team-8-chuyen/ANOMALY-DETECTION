"""Typed reconstruction loss, one-epoch training and user-day scoring (SPEC-004)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
import math
from time import perf_counter
from typing import Callable

import torch
from torch import Tensor
from torch.nn import functional as F
from torch.utils.data import DataLoader

from itd.data.sequence_dataset import (
    BOOLEAN_INDICES, CAT_INDICES, NUMERIC_INDICES, SEQUENCE_FIELDS,
    SequenceBatch, SequenceDay, SequenceWindow, collate_windows, window_day,
)
from itd.data.sequence_preprocessing import SequencePreprocessor
from itd.models.lstm_autoencoder import Reconstruction


class PilotTimeout(TimeoutError):
    """The bounded pilot did not finish its entire phase."""


def check_deadline(deadline: float | None, clock: Callable[[], float] = perf_counter) -> None:
    if deadline is not None and clock() >= deadline:
        raise PilotTimeout('pilot time budget reached before a complete phase')


def _summaries(sums: list[float], counts: list[int]) -> tuple[dict, dict]:
    fields = {name: {'loss_sum': sums[i], 'count': counts[i],
                     'mean': sums[i] / counts[i] if counts[i] else None}
              for i, name in enumerate(SEQUENCE_FIELDS)}
    types = {}
    for name, indices in [('categorical', CAT_INDICES), ('numeric', NUMERIC_INDICES),
                          ('boolean', BOOLEAN_INDICES)]:
        total = math.fsum(sums[i] for i in indices)
        count = sum(counts[i] for i in indices)
        types[name] = {'loss_sum': total, 'count': count, 'mean': total / count if count else None}
    return fields, types


@dataclass
class LossStats:
    loss: Tensor
    loss_cells: Tensor
    valid_mask: Tensor
    loss_sum: float
    n_valid_attributes: int
    field_loss_sums: list[float]
    field_counts: list[int]

    def to_dict(self) -> dict:
        fields, types = _summaries(self.field_loss_sums, self.field_counts)
        return {'loss': self.loss_sum / self.n_valid_attributes, 'loss_sum': self.loss_sum,
                'n_valid_attributes': self.n_valid_attributes, 'per_field': fields, 'per_type': types}


@dataclass
class EpochResult:
    loss: float
    loss_sum: float
    n_valid_attributes: int
    n_windows: int
    valid_steps: int
    padded_steps: int
    n_batches: int
    per_field: dict
    per_type: dict

    def to_dict(self) -> dict:
        return dict(vars(self))


@dataclass
class RawSequenceScore:
    user: str
    day: str
    metadata: dict
    e_sequence_raw: float
    loss_sum: float
    n_valid_attributes: int
    n_sequence_rows: int
    n_windows: int
    per_field: dict
    per_type: dict

    def to_dict(self) -> dict:
        return {**self.metadata, 'user': self.user, 'day': self.day,
                'e_sequence_raw': self.e_sequence_raw, 'loss_sum': self.loss_sum,
                'n_valid_attributes': self.n_valid_attributes,
                'n_sequence_rows': self.n_sequence_rows, 'n_windows': self.n_windows}


def reconstruction_loss(outputs: Reconstruction, batch: SequenceBatch) -> LossStats:
    """Compute only applicable cells, retaining gradients for the valid-cell mean."""
    if (batch.attribute_mask.dtype != torch.bool or batch.time_mask.dtype != torch.bool
            or batch.attribute_mask.shape != (*batch.time_mask.shape, len(SEQUENCE_FIELDS))):
        raise ValueError('invalid reconstruction masks')
    valid = batch.attribute_mask & batch.time_mask.unsqueeze(-1)
    if bool((valid.sum(dim=(1, 2)) == 0).any()):
        raise ValueError('every reconstruction window needs active attributes')
    shape = batch.time_mask.shape
    if (len(outputs.cat) != len(CAT_INDICES) or outputs.numeric.shape != (*shape, len(NUMERIC_INDICES))
            or outputs.boolean.shape != (*shape, len(BOOLEAN_INDICES))):
        raise ValueError('reconstruction head shapes do not match Sequence24')
    cells: list[Tensor | None] = [None] * len(SEQUENCE_FIELDS)

    def place(index: int, values: Tensor) -> None:
        if not bool(torch.isfinite(values).all()):
            raise FloatingPointError(f'non-finite reconstruction loss: {SEQUENCE_FIELDS[index]}')
        cells[index] = values.new_zeros(shape).masked_scatter(valid[..., index], values)

    for column, index in enumerate(CAT_INDICES):
        logits = outputs.cat[column]
        if logits.ndim != 3 or logits.shape[:2] != shape or logits.shape[-1] < 2:
            raise ValueError('categorical head shape is invalid')
        active = valid[..., index]
        target = batch.cat[..., column][active]
        if target.dtype != torch.int64 or bool(((target < 1) | (target >= logits.shape[-1])).any()):
            raise ValueError('active categorical target is outside its vocabulary')
        selected = logits[active]
        if not bool(torch.isfinite(selected).all()):
            raise FloatingPointError('non-finite active categorical logits')
        place(index, F.cross_entropy(selected, target, reduction='none'))
    for column, index in enumerate(NUMERIC_INDICES):
        active = valid[..., index]
        target = batch.numeric[..., column][active]
        prediction = outputs.numeric[..., column][active]
        if not bool(torch.isfinite(target).all()):
            raise ValueError('active numeric target must be finite')
        place(index, (prediction - target).square())
    for column, index in enumerate(BOOLEAN_INDICES):
        active = valid[..., index]
        target = batch.boolean[..., column][active]
        if not bool(((target == 0) | (target == 1)).all()):
            raise ValueError('active boolean target must be zero or one')
        place(index, F.binary_cross_entropy_with_logits(outputs.boolean[..., column][active],
                                                       target, reduction='none'))
    loss_cells = torch.stack(cells, dim=-1)
    count = int(valid.sum().item())
    sums = loss_cells.detach().double().sum(dim=(0, 1)).tolist()
    counts = valid.sum(dim=(0, 1)).tolist()
    total = math.fsum(sums)
    # SPEC-004 §4.5: one weight for each active attribute, not one weight per window.
    loss = loss_cells.double().sum() / count
    if not bool(torch.isfinite(loss)):
        raise FloatingPointError('non-finite reconstruction mean loss')
    return LossStats(loss, loss_cells, valid, total, count, sums, counts)


def _loader(windows: list[SequenceWindow], preprocessor: SequencePreprocessor, config: dict,
            *, shuffle: bool, generator=None) -> DataLoader:
    batch_size = config['train']['batch_size']
    workers = config['train']['num_workers']
    if type(batch_size) is not int or batch_size < 1 or type(workers) is not int or workers != 0:
        raise ValueError('pilot requires a positive batch size and zero workers')
    if not windows:
        raise ValueError('sequence windows cannot be empty')
    return DataLoader(windows, batch_size=batch_size, shuffle=shuffle, drop_last=False,
                      num_workers=0, generator=generator,
                      collate_fn=partial(collate_windows, preprocessor=preprocessor))


def train_one_epoch(model, windows: list[SequenceWindow], preprocessor: SequencePreprocessor,
                    optimizer, config: dict, generator, deadline: float | None = None,
                    clock: Callable[[], float] = perf_counter) -> EpochResult:
    check_deadline(deadline, clock)
    model.train()
    sums = [0.0] * len(SEQUENCE_FIELDS)
    counts = [0] * len(SEQUENCE_FIELDS)
    n_windows = valid_steps = padded_steps = n_batches = 0
    clip = config['train']['grad_clip_norm']
    if isinstance(clip, bool) or not isinstance(clip, (int, float)) or not math.isfinite(clip) or clip <= 0:
        raise ValueError('gradient clip norm must be finite and positive')
    ordered = sorted(windows, key=lambda window: (window.day, window.user, window.offset))
    for batch in _loader(ordered, preprocessor, config, shuffle=True, generator=generator):
        check_deadline(deadline, clock)
        optimizer.zero_grad(set_to_none=True)
        stats = reconstruction_loss(model(batch), batch)
        stats.loss.backward()
        try:
            torch.nn.utils.clip_grad_norm_(model.parameters(), clip, error_if_nonfinite=True)
        except RuntimeError as error:
            raise FloatingPointError('non-finite gradients') from error
        optimizer.step()
        if any(not bool(torch.isfinite(parameter).all()) for parameter in model.parameters()):
            raise FloatingPointError('non-finite model parameters')
        sums = [a + b for a, b in zip(sums, stats.field_loss_sums)]
        counts = [a + b for a, b in zip(counts, stats.field_counts)]
        n_windows += len(batch.windows)
        valid_steps += int(batch.lengths.sum().item())
        padded_steps += batch.time_mask.numel()
        n_batches += 1
        check_deadline(deadline, clock)
    total, count = math.fsum(sums), sum(counts)
    fields, types = _summaries(sums, counts)
    return EpochResult(total / count, total, count, n_windows, valid_steps, padded_steps,
                       n_batches, fields, types)


def score_days(model, days: list[SequenceDay], preprocessor: SequencePreprocessor,
               config: dict, deadline: float | None = None,
               clock: Callable[[], float] = perf_counter) -> list[RawSequenceScore]:
    check_deadline(deadline, clock)
    keys = [(day.user, day.day) for day in days]
    if not keys or len(set(keys)) != len(keys):
        raise ValueError('validation user-day keys must be nonempty and unique')
    windows = [window for day in sorted(days, key=lambda day: (day.day, day.user))
               for window in window_day(day, config['data']['window_length'])]
    aggregates = {}
    was_training = model.training
    model.eval()
    try:
        with torch.no_grad():
            for batch in _loader(windows, preprocessor, config, shuffle=False):
                check_deadline(deadline, clock)
                stats = reconstruction_loss(model(batch), batch)
                losses = stats.loss_cells.double().sum(dim=1).tolist()
                counts = stats.valid_mask.sum(dim=1).tolist()
                for window, field_sums, field_counts in zip(batch.windows, losses, counts):
                    key = (window.user, window.day)
                    if key not in aggregates:
                        aggregates[key] = {'metadata': window.metadata,
                                           'sums': [0.0] * len(SEQUENCE_FIELDS),
                                           'counts': [0] * len(SEQUENCE_FIELDS),
                                           'rows': 0, 'windows': 0}
                    item = aggregates[key]
                    if item['metadata'] != window.metadata:
                        raise ValueError('metadata must agree across a user-day')
                    item['sums'] = [a + b for a, b in zip(item['sums'], field_sums)]
                    item['counts'] = [a + b for a, b in zip(item['counts'], field_counts)]
                    item['rows'] += window.length
                    item['windows'] += 1
                check_deadline(deadline, clock)
    finally:
        model.train(was_training)
    result = []
    for (user, day), item in sorted(aggregates.items(), key=lambda pair: (pair[0][1], pair[0][0])):
        total, count = math.fsum(item['sums']), sum(item['counts'])
        score = total / count
        if not math.isfinite(score) or score < 0:
            raise FloatingPointError('non-finite or negative user-day reconstruction score')
        fields, types = _summaries(item['sums'], item['counts'])
        result.append(RawSequenceScore(user, day, dict(item['metadata']), score, total, count,
                                       item['rows'], item['windows'], fields, types))
    return result
