"""TCN–Transformer sequence autoencoder (SPEC-002 §6)."""
from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F


class ResidualTCNBlock(nn.Module):
    def __init__(self, width: int, dilation: int, dropout: float):
        super().__init__()
        self.conv = nn.Conv1d(width, width, 3, padding=dilation, dilation=dilation)
        self.norm = nn.LayerNorm(width)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = self.conv(x.transpose(1, 2)).transpose(1, 2)
        return self.norm(x + self.dropout(F.gelu(y)))


class TCNTransformerAutoencoder(nn.Module):
    def __init__(self, vocab_size: int, continuous_dim: int, d_model: int = 64,
                 dilations=(1, 2, 4), n_layers: int = 2, n_heads: int = 4,
                 ff_mult: int = 2, dropout: float = 0.1, max_len: int = 256):
        super().__init__()
        self.token_embedding = nn.Embedding(vocab_size, d_model, padding_idx=0)
        self.continuous_projection = nn.Linear(continuous_dim, d_model)
        self.position = nn.Parameter(torch.zeros(1, max_len, d_model))
        self.tcn = nn.ModuleList(ResidualTCNBlock(d_model, d, dropout) for d in dilations)
        layer = nn.TransformerEncoderLayer(d_model, n_heads, d_model * ff_mult, dropout,
                                           activation="gelu", batch_first=True, norm_first=True)
        self.transformer = nn.TransformerEncoder(layer, n_layers)
        self.token_head = nn.Linear(d_model, vocab_size)
        self.continuous_head = nn.Linear(d_model, continuous_dim)

    def forward(self, tokens: torch.Tensor, continuous: torch.Tensor, padding_mask: torch.Tensor):
        length = tokens.shape[1]
        x = self.token_embedding(tokens) + self.continuous_projection(continuous) + self.position[:, :length]
        for block in self.tcn:
            x = block(x)
        encoded = self.transformer(x, src_key_padding_mask=padding_mask)
        return self.token_head(encoded), self.continuous_head(encoded)

    def loss_per_sample(self, tokens: torch.Tensor, continuous: torch.Tensor,
                        padding_mask: torch.Tensor, attribute_mask: torch.Tensor | None = None):
        token_logits, continuous_hat = self(tokens, continuous, padding_mask)
        valid = ~padding_mask
        token_loss = F.cross_entropy(token_logits.transpose(1, 2), tokens, reduction="none")
        token_loss = (token_loss * valid).sum(1) / valid.sum(1).clamp_min(1)
        cont_valid = valid.unsqueeze(-1).expand_as(continuous)
        if attribute_mask is not None:
            cont_valid = cont_valid & attribute_mask.bool()
        cont_loss = ((continuous_hat - continuous).square() * cont_valid).sum((1, 2))
        cont_loss = cont_loss / cont_valid.sum((1, 2)).clamp_min(1)
        return token_loss + cont_loss
