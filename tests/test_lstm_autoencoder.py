from copy import deepcopy
from types import SimpleNamespace

import pytest
import torch

from itd.data.sequence_dataset import BOOLEAN_INDICES, CAT_INDICES, NUMERIC_INDICES
from itd.models.lstm_autoencoder import LSTMAutoencoder


LSTM_CONFIG = {'embedding_dim': 4, 'hidden_size': 32, 'latent_size': 16,
               'num_layers': 1, 'bidirectional': False, 'dropout': 0,
               'decoder_position': 'local_fixed_window'}


@pytest.fixture(autouse=True)
def cpu_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(2)
    yield
    torch.set_num_threads(previous)


def make_batch(lengths=(3, 7), pad_to=None):
    length = max(lengths) if pad_to is None else pad_to
    count = len(lengths)
    time_mask = torch.arange(length)[None, :] < torch.tensor(lengths)[:, None]
    mask = time_mask.unsqueeze(-1).expand(-1, -1, 24).clone()
    cat = torch.full((count, length, 7), 2, dtype=torch.int64)
    numeric = torch.zeros(count, length, 13)
    boolean = torch.zeros(count, length, 4)
    for index in range(count):
        cat[index, :lengths[index]] = 2 + index % 2
        numeric[index, :lengths[index]] = (index % 2) * 0.5 - 0.25
        boolean[index, :lengths[index]] = index % 2
    return SimpleNamespace(cat=cat, numeric=numeric, boolean=boolean,
                           attribute_mask=mask, time_mask=time_mask,
                           lengths=torch.tensor(lengths, dtype=torch.int64),
                           windows=[SimpleNamespace(length=n) for n in lengths])


def make_model():
    torch.manual_seed(0)
    return LSTMAutoencoder([4] * 7, deepcopy(LSTM_CONFIG))


def compare_valid(left, right, lengths):
    for index, length in enumerate(lengths):
        for a, b in zip(left.cat, right.cat):
            torch.testing.assert_close(a[index, :length], b[index, :length], atol=1e-6, rtol=1e-6)
        torch.testing.assert_close(left.numeric[index, :length], right.numeric[index, :length],
                                   atol=1e-6, rtol=1e-6)
        torch.testing.assert_close(left.boolean[index, :length], right.boolean[index, :length],
                                   atol=1e-6, rtol=1e-6)


def test_forward_backward_and_shapes():
    model = make_model()
    batch = make_batch()
    output = model(batch)
    assert len(output.cat) == 7
    assert all(item.shape == (2, 7, 4) for item in output.cat)
    assert output.numeric.shape == (2, 7, 13)
    assert output.boolean.shape == (2, 7, 4)
    output.numeric.square().sum().backward()
    assert model.encoder.weight_ih_l0.grad is not None
    assert model.to_latent.weight.grad is not None
    assert torch.isfinite(model.to_latent.weight.grad).all()
    assert model.encoder.input_size == 69
    assert model.decoder.input_size == 17
    assert model.to_latent.out_features == 16


@pytest.mark.parametrize('length', [1, 3, 7, 128])
def test_boundary_lengths(length):
    assert make_model()(make_batch((length,))).numeric.shape == (1, length, 13)


def test_right_padding_cannot_change_real_predictions():
    model = make_model().eval()
    with torch.no_grad():
        compare_valid(model(make_batch((3, 7))), model(make_batch((3, 7), pad_to=13)), (3, 7))


def test_batch_companion_cannot_change_real_predictions():
    model = make_model().eval()
    with torch.no_grad():
        alone = model(make_batch((3,)))
        together = model(make_batch((3, 7)))
    for a, b in zip(alone.cat, together.cat):
        torch.testing.assert_close(a[0], b[0, :3], atol=1e-6, rtol=1e-6)
    torch.testing.assert_close(alone.numeric[0], together.numeric[0, :3], atol=1e-6, rtol=1e-6)


def test_inactive_and_padding_garbage_never_reaches_encoder():
    batch = make_batch()
    batch.attribute_mask[..., [9, 10, 11]] = False
    clean = deepcopy(batch)
    batch.cat[..., list(CAT_INDICES).index(9)] = -900
    batch.numeric[..., list(NUMERIC_INDICES).index(10)] = float('nan')
    batch.boolean[..., list(BOOLEAN_INDICES).index(11)] = float('nan')
    batch.cat[~batch.time_mask] = 9999
    batch.numeric[~batch.time_mask] = float('inf')
    batch.boolean[~batch.time_mask] = 7
    model = make_model().eval()
    with torch.no_grad():
        compare_valid(model(clean), model(batch), (3, 7))


def test_only_latent_can_carry_encoder_content():
    model = make_model().eval()
    handle = model.to_latent.register_forward_hook(lambda module, args, output: torch.zeros_like(output))
    first, second = make_batch((7,)), make_batch((7,))
    second.numeric += 100
    second.cat[:] = 3
    second.boolean[:] = 1
    with torch.no_grad():
        compare_valid(model(first), model(second), (7,))
    handle.remove()


def test_decoder_position_uses_fixed_window_denominator():
    model = make_model()
    observed = []
    handle = model.decoder.register_forward_pre_hook(lambda module, args: observed.append(args[0].detach()))
    model(make_batch((3,), pad_to=7))
    handle.remove()
    torch.testing.assert_close(observed[0][0, :3, -1], torch.arange(3) / 127)
    assert torch.equal(observed[0][0, 3:], torch.zeros_like(observed[0][0, 3:]))


@pytest.mark.parametrize('mutation', ['nonprefix', 'length', 'float_length', 'category', 'numeric', 'boolean'])
def test_invalid_active_or_length_contract_fails(mutation):
    batch = make_batch()
    if mutation == 'nonprefix':
        batch.time_mask[0, 1] = False
    elif mutation == 'length':
        batch.lengths[0] = 8
    elif mutation == 'float_length':
        batch.lengths = batch.lengths.float()
    elif mutation == 'category':
        batch.cat[0, 0, 0] = 0
    elif mutation == 'numeric':
        batch.numeric[0, 0, 0] = float('nan')
    else:
        batch.boolean[0, 0, 0] = 2
    with pytest.raises(ValueError):
        make_model()(batch)


@pytest.mark.parametrize('key,value', [('num_layers', 2), ('bidirectional', True),
                                       ('dropout', 0.1), ('hidden_size', True),
                                       ('decoder_position', 'batch_length')])
def test_invalid_model_config(key, value):
    config = deepcopy(LSTM_CONFIG)
    config[key] = value
    with pytest.raises(ValueError):
        LSTMAutoencoder([4] * 7, config)


def test_state_dict_roundtrip(tmp_path):
    model = make_model().eval()
    batch = make_batch()
    path = tmp_path / 'model.pt'
    torch.save(model.state_dict(), path)
    restored = make_model().eval()
    restored.load_state_dict(torch.load(path, weights_only=True))
    with torch.no_grad():
        compare_valid(model(batch), restored(batch), (3, 7))
