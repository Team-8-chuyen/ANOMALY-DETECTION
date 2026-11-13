"""Packed LSTM reconstruction through one latent vector (SPEC-004 §4.4)."""
from __future__ import annotations

from dataclasses import dataclass
from numbers import Real

import torch
from torch import Tensor, nn
from torch.nn.utils.rnn import pack_padded_sequence

from itd.data.sequence_dataset import (
    BOOLEAN_INDICES, CAT_INDICES, NUMERIC_INDICES, SequenceBatch,
)


@dataclass
class Reconstruction:
    cat: list[Tensor]
    numeric: Tensor
    boolean: Tensor


class LSTMAutoencoder(nn.Module):
    """One shared encoder/decoder; only the bottleneck carries sequence content."""

    def __init__(self, vocab_sizes: list[int], config: dict, *, window_length: int = 128):
        super().__init__()
        required = {'embedding_dim', 'hidden_size', 'latent_size', 'num_layers',
                    'bidirectional', 'dropout', 'decoder_position'}
        if not isinstance(config, dict) or set(config) != required:
            raise ValueError('lstm config requires exactly the approved model keys')
        for key in ('embedding_dim', 'hidden_size', 'latent_size', 'num_layers'):
            if type(config[key]) is not int or config[key] < 1:
                raise ValueError(f'{key} must be a positive integer')
        if config['num_layers'] != 1 or config['bidirectional'] is not False:
            raise ValueError('pilot LSTM must have one unidirectional layer')
        dropout = config['dropout']
        if isinstance(dropout, bool) or not isinstance(dropout, Real) or dropout != 0:
            raise ValueError('pilot dropout must be zero')
        if config['decoder_position'] != 'local_fixed_window':
            raise ValueError('unsupported decoder position policy')
        if type(window_length) is not int or window_length < 2:
            raise ValueError('window_length must be an integer of at least two')
        if (not isinstance(vocab_sizes, list) or len(vocab_sizes) != len(CAT_INDICES)
                or any(type(size) is not int or size < 2 for size in vocab_sizes)):
            raise ValueError('vocab_sizes must contain seven integer sizes including PAD/UNK')
        self.window_length = window_length
        self.vocab_sizes = tuple(vocab_sizes)
        embedding_dim = config['embedding_dim']
        hidden = config['hidden_size']
        latent = config['latent_size']
        self.embeddings = nn.ModuleList(nn.Embedding(size, embedding_dim, padding_idx=0)
                                        for size in vocab_sizes)
        input_size = len(CAT_INDICES) * embedding_dim + len(NUMERIC_INDICES) + len(BOOLEAN_INDICES) + 24
        self.encoder = nn.LSTM(input_size, hidden, num_layers=1, batch_first=True)
        self.to_latent = nn.Linear(hidden, latent)
        self.to_hidden = nn.Linear(latent, hidden)
        self.to_cell = nn.Linear(latent, hidden)
        self.decoder = nn.LSTM(latent + 1, hidden, num_layers=1, batch_first=True)
        self.cat_heads = nn.ModuleList(nn.Linear(hidden, size) for size in vocab_sizes)
        self.numeric_head = nn.Linear(hidden, len(NUMERIC_INDICES))
        self.boolean_head = nn.Linear(hidden, len(BOOLEAN_INDICES))

    def _validate(self, batch: SequenceBatch) -> tuple[int, int, Tensor]:
        if not isinstance(batch.cat, Tensor) or batch.cat.ndim != 3:
            raise ValueError('categorical batch must have shape [B,L,7]')
        batch_size, length, _ = batch.cat.shape
        if batch_size < 1 or not 1 <= length <= self.window_length:
            raise ValueError('batch and sequence lengths must be nonempty and within the window')
        expected = {'cat': (len(CAT_INDICES), torch.int64),
                    'numeric': (len(NUMERIC_INDICES), torch.float32),
                    'boolean': (len(BOOLEAN_INDICES), torch.float32),
                    'attribute_mask': (24, torch.bool)}
        device = batch.cat.device
        for name, (width, dtype) in expected.items():
            value = getattr(batch, name)
            if (not isinstance(value, Tensor) or value.shape != (batch_size, length, width)
                    or value.dtype != dtype or value.device != device):
                raise ValueError(f'{name} has an invalid shape, dtype or device')
        if (not isinstance(batch.time_mask, Tensor) or batch.time_mask.shape != (batch_size, length)
                or batch.time_mask.dtype != torch.bool or batch.time_mask.device != device):
            raise ValueError('time_mask must be a boolean [B,L] tensor')
        if (not isinstance(batch.lengths, Tensor) or batch.lengths.shape != (batch_size,)
                or batch.lengths.dtype != torch.int64 or batch.lengths.device.type != 'cpu'):
            raise ValueError('lengths must be an int64 CPU tensor')
        if bool(((batch.lengths < 1) | (batch.lengths > length)).any()):
            raise ValueError('lengths must be within the padded sequence length')
        prefix = torch.arange(length, device=device)[None, :] < batch.lengths.to(device)[:, None]
        if not torch.equal(prefix, batch.time_mask):
            raise ValueError('time_mask must be a contiguous true prefix matching lengths')
        valid = batch.attribute_mask & prefix.unsqueeze(-1)
        for column, index in enumerate(CAT_INDICES):
            values = batch.cat[..., column][valid[..., index]]
            if bool(((values < 1) | (values >= self.vocab_sizes[column])).any()):
                raise ValueError('active category ID must be UNK or an observed vocabulary entry')
        if not bool(torch.isfinite(batch.numeric[valid[..., list(NUMERIC_INDICES)]]).all()):
            raise ValueError('active numeric values must be finite')
        boolean = batch.boolean[valid[..., list(BOOLEAN_INDICES)]]
        if not bool(((boolean == 0) | (boolean == 1)).all()):
            raise ValueError('active boolean values must be zero or one')
        return batch_size, length, valid

    def forward(self, batch: SequenceBatch) -> Reconstruction:
        _, length, valid = self._validate(batch)
        embedded = []
        for column, index in enumerate(CAT_INDICES):
            active = valid[..., index]
            ids = torch.where(active, batch.cat[..., column], 0)
            embedded.append(self.embeddings[column](ids).masked_fill(~active.unsqueeze(-1), 0))
        # Sanitize before arithmetic: NaN under an inactive mask must never enter the network.
        numeric = torch.where(valid[..., list(NUMERIC_INDICES)], batch.numeric, 0)
        boolean = torch.where(valid[..., list(BOOLEAN_INDICES)], batch.boolean, 0)
        features = torch.cat(embedded + [numeric, boolean, valid.to(numeric.dtype)], dim=-1)
        packed = pack_padded_sequence(features, batch.lengths, batch_first=True, enforce_sorted=False)
        _, (hidden, _) = self.encoder(packed)
        # SPEC-004 §4.4: h_n is the last real step, not the last padding position.
        latent = torch.tanh(self.to_latent(hidden[0]))
        positions = torch.arange(length, device=features.device, dtype=features.dtype)
        positions = positions.div(self.window_length - 1).view(1, length, 1)
        positions = positions.expand(features.shape[0], -1, -1)
        decoder_input = torch.cat((latent.unsqueeze(1).expand(-1, length, -1), positions), dim=-1)
        decoder_input = decoder_input.masked_fill(~batch.time_mask.unsqueeze(-1), 0)
        state = (torch.tanh(self.to_hidden(latent)).unsqueeze(0),
                 torch.tanh(self.to_cell(latent)).unsqueeze(0))
        decoded, _ = self.decoder(decoder_input, state)
        padding = ~batch.time_mask.unsqueeze(-1)
        return Reconstruction(
            [head(decoded).masked_fill(padding, 0) for head in self.cat_heads],
            self.numeric_head(decoded).masked_fill(padding, 0),
            self.boolean_head(decoded).masked_fill(padding, 0),
        )
