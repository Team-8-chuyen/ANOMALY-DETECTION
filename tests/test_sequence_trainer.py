from copy import deepcopy
import json
import math

import pytest
import torch
from torch import nn

from itd.data.sequence_dataset import (
    BOOLEAN_FIELDS, CATEGORICAL_FIELDS, NUMERIC_FIELDS, SEQUENCE_FIELDS,
    SequenceDay, collate_windows, window_day,
)
from itd.data.sequence_preprocessing import SequencePreprocessor
from itd.models.lstm_autoencoder import LSTMAutoencoder, Reconstruction
from itd.training.sequence_trainer import PilotTimeout, reconstruction_loss, score_days, train_one_epoch
from test_lstm_autoencoder import LSTM_CONFIG, make_batch, make_model


@pytest.fixture(autouse=True)
def cpu_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(2)
    yield
    torch.set_num_threads(previous)


def config(batch_size=64):
    return {'data': {'window_length': 128},
            'train': {'batch_size': batch_size, 'num_workers': 0, 'grad_clip_norm': 1.0}}


def raw_day(user='u', day='2010-01-02', length=8):
    rows = []
    for step in range(length):
        row = {'user': user, 'day': day, 'event_index': step,
               'attribute_mask': json.dumps([True] * len(SEQUENCE_FIELDS))}
        row.update({name: ('A' if name != 'gap_bucket' else 0) for name in CATEGORICAL_FIELDS})
        row.update({name: float(step % 2) for name in NUMERIC_FIELDS})
        row.update({name: bool(step % 2) for name in BOOLEAN_FIELDS})
        rows.append(row)
    return SequenceDay(user, day, rows, {'role': 'R', 'department': 'D'})


def test_typed_loss_matches_hand_example():
    batch = make_batch((1,))
    batch.numeric[:] = 1
    zero = Reconstruction([torch.zeros(1, 1, 4, requires_grad=True) for _ in range(7)],
                          torch.zeros(1, 1, 13, requires_grad=True),
                          torch.zeros(1, 1, 4, requires_grad=True))
    result = reconstruction_loss(zero, batch)
    expected = (7 * math.log(4) + 13 + 4 * math.log(2)) / 24
    assert result.loss.item() == pytest.approx(expected, rel=1e-6)
    assert result.n_valid_attributes == 24
    assert result.field_counts == [1] * 24
    assert result.to_dict()['per_type']['numeric']['mean'] == 1
    result.loss.backward()
    assert torch.isfinite(zero.numeric.grad).all()


def test_loss_ignores_inactive_garbage_and_padding():
    batch = make_batch((1,), pad_to=3)
    batch.attribute_mask[..., 9:13] = False
    prediction = Reconstruction([torch.zeros(1, 3, 4) for _ in range(7)],
                                torch.zeros(1, 3, 13), torch.zeros(1, 3, 4))
    initial = reconstruction_loss(prediction, batch)
    batch.cat[..., 4] = -99  # file_extension_id at Sequence24 index 9
    batch.numeric[..., 5] = float('nan')  # filename_length_log1p at index 10
    batch.boolean[..., :2] = float('nan')
    batch.cat[:, 1:] = -999
    batch.numeric[:, 1:] = float('inf')
    batch.boolean[:, 1:] = -1
    after = reconstruction_loss(prediction, batch)
    assert after.loss_sum == initial.loss_sum
    assert after.n_valid_attributes == 20


def test_loss_rejects_empty_window_and_nonfinite_active_logits():
    batch = make_batch((1,))
    output = make_model()(batch)
    output.cat[0][0, 0, 0] = float('nan')
    with pytest.raises(FloatingPointError):
        reconstruction_loss(output, batch)
    batch.attribute_mask[:] = False
    with pytest.raises(ValueError, match='active attributes'):
        reconstruction_loss(output, batch)


def test_loss_reduction_uses_float64_for_large_finite_cells():
    batch = make_batch((7,))
    batch.numeric[:] = 1e19
    zero = Reconstruction([torch.zeros(1, 7, 4) for _ in range(7)],
                          torch.zeros(1, 7, 13), torch.zeros(1, 7, 4))
    stats = reconstruction_loss(zero, batch)
    assert stats.loss.dtype == torch.float64
    assert torch.isfinite(stats.loss)
    assert math.isfinite(stats.loss_sum)


def test_overfit_one_synthetic_batch():
    batch = make_batch((8, 8))
    model = make_model()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=0)
    initial = reconstruction_loss(model(batch), batch).loss.item()
    for _ in range(200):
        optimizer.zero_grad(set_to_none=True)
        stats = reconstruction_loss(model(batch), batch)
        stats.loss.backward()
        optimizer.step()
    final = reconstruction_loss(model(batch), batch).loss.item()
    assert final <= initial * 0.5, (initial, final)


def test_training_epoch_counts_all_windows_and_clips(monkeypatch):
    days = [raw_day(user='a', length=3), raw_day(user='b', length=7), raw_day(user='c', length=2)]
    prep = SequencePreprocessor().fit(days)
    model = LSTMAutoencoder(prep.vocab_sizes, deepcopy(LSTM_CONFIG))
    windows = [window for day in days for window in window_day(day, 128)]
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001)
    clip_calls = []
    original_clip = torch.nn.utils.clip_grad_norm_

    def clip(parameters, max_norm, **kwargs):
        clip_calls.append(max_norm)
        return original_clip(parameters, max_norm, **kwargs)

    monkeypatch.setattr(torch.nn.utils, 'clip_grad_norm_', clip)
    result = train_one_epoch(model, windows, prep, optimizer, config(2), torch.Generator().manual_seed(0))
    assert result.n_windows == 3
    assert result.valid_steps == 12
    assert result.padded_steps >= 12
    assert result.n_batches == 2
    assert result.n_valid_attributes == 12 * 24
    assert result.loss == pytest.approx(result.loss_sum / result.n_valid_attributes)
    assert clip_calls == [1.0, 1.0]
    assert len(result.to_dict()['per_field']) == 24


def test_deadline_never_returns_partial_epoch():
    days = [raw_day()]
    prep = SequencePreprocessor().fit(days)
    model = LSTMAutoencoder(prep.vocab_sizes, deepcopy(LSTM_CONFIG))
    initial = deepcopy(model.state_dict())
    optimizer = torch.optim.AdamW(model.parameters())
    with pytest.raises(PilotTimeout):
        train_one_epoch(model, window_day(days[0], 128), prep, optimizer, config(),
                        torch.Generator(), deadline=5.0, clock=lambda: 5.0)
    assert all(torch.equal(value, initial[name]) for name, value in model.state_dict().items())


def test_validation_deadline_and_duplicate_keys():
    days = [raw_day()]
    prep = SequencePreprocessor().fit(days)
    model = LSTMAutoencoder(prep.vocab_sizes, deepcopy(LSTM_CONFIG))
    with pytest.raises(PilotTimeout):
        score_days(model, days, prep, config(), deadline=1, clock=lambda: 2)
    with pytest.raises(ValueError, match='unique'):
        score_days(model, days * 2, prep, config())


def test_nonfinite_gradient_stops_before_optimizer_step(monkeypatch):
    days = [raw_day()]
    prep = SequencePreprocessor().fit(days)
    model = LSTMAutoencoder(prep.vocab_sizes, deepcopy(LSTM_CONFIG))
    optimizer = torch.optim.AdamW(model.parameters())
    model.to_latent.weight.register_hook(lambda gradient: torch.full_like(gradient, float('nan')))
    steps = []
    monkeypatch.setattr(optimizer, 'step', lambda: steps.append(True))
    with pytest.raises(FloatingPointError, match='gradients'):
        train_one_epoch(model, window_day(days[0], 128), prep, optimizer,
                        config(), torch.Generator().manual_seed(0))
    assert not steps


class ZeroModel(nn.Module):
    def __init__(self, vocab_sizes):
        super().__init__()
        self.vocab_sizes = vocab_sizes

    def forward(self, batch):
        shape = batch.time_mask.shape
        return Reconstruction([torch.zeros(*shape, size) for size in self.vocab_sizes],
                              torch.zeros(*shape, 13), torch.zeros(*shape, 4))


def test_user_day_aggregation_weights_short_last_window():
    fit = [raw_day()]
    prep = SequencePreprocessor().fit(fit)
    day = raw_day(day='2010-01-23', length=129)
    for name in NUMERIC_FIELDS:
        day.rows[-1][name] = 30.0
    model = ZeroModel(prep.vocab_sizes)
    windows = window_day(day, 128)
    individual = [reconstruction_loss(model(collate_windows([window], prep)),
                                      collate_windows([window], prep)) for window in windows]
    score = score_days(model, [day], prep, config())[0]
    expected = sum(item.loss_sum for item in individual) / sum(item.n_valid_attributes for item in individual)
    naive = sum(item.loss.item() for item in individual) / 2
    assert score.e_sequence_raw == pytest.approx(expected, rel=1e-6)
    assert score.e_sequence_raw != pytest.approx(naive, rel=0.1)
    assert score.n_sequence_rows == 129
    assert score.n_windows == 2
    assert score.n_valid_attributes == 129 * 24
    assert score.to_dict()['role'] == 'R'
    assert 'per_field' not in score.to_dict()


def test_raw_scores_repeat_and_model_mode_restored():
    days = [raw_day(user='z', day='2010-01-24'), raw_day(user='a', day='2010-01-23')]
    prep = SequencePreprocessor().fit(days)
    model = LSTMAutoencoder(prep.vocab_sizes, deepcopy(LSTM_CONFIG))
    model.train()
    first = score_days(model, days, prep, config())
    second = score_days(model, days, prep, config())
    assert model.training
    assert [(row.day, row.user) for row in first] == [('2010-01-23', 'a'), ('2010-01-24', 'z')]
    assert [row.to_dict() for row in first] == [row.to_dict() for row in second]


def test_raw_scores_do_not_depend_on_batch_partition():
    prep = SequencePreprocessor().fit([raw_day()])
    days = [raw_day(user='z', day='2010-01-24', length=129),
            raw_day(user='a', day='2010-01-23', length=3)]
    model = LSTMAutoencoder(prep.vocab_sizes, deepcopy(LSTM_CONFIG))
    singleton = score_days(model, days, prep, config(1))
    together = score_days(model, days, prep, config(64))
    for left, right in zip(singleton, together):
        assert (left.user, left.day, left.n_sequence_rows, left.n_windows) == (
            right.user, right.day, right.n_sequence_rows, right.n_windows)
        assert left.e_sequence_raw == pytest.approx(right.e_sequence_raw, rel=1e-6, abs=1e-6)


def test_epoch_order_before_shuffle_is_canonical():
    days = [raw_day(user='b'), raw_day(user='a')]
    prep = SequencePreprocessor().fit(days)
    windows = [window for day in days for window in window_day(day, 128)]
    first = LSTMAutoencoder(prep.vocab_sizes, deepcopy(LSTM_CONFIG))
    second = LSTMAutoencoder(prep.vocab_sizes, deepcopy(LSTM_CONFIG))
    second.load_state_dict(first.state_dict())
    a = train_one_epoch(first, windows, prep, torch.optim.AdamW(first.parameters()), config(1),
                        torch.Generator().manual_seed(0))
    b = train_one_epoch(second, list(reversed(windows)), prep, torch.optim.AdamW(second.parameters()),
                        config(1), torch.Generator().manual_seed(0))
    assert a.to_dict() == b.to_dict()
    assert all(torch.equal(tensor, second.state_dict()[name]) for name, tensor in first.state_dict().items())
