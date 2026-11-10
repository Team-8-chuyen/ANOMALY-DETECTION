"""Masked Behaviour autoencoder (SPEC-002 §5)."""
from __future__ import annotations

import torch
from torch import nn


class FeatureAutoencoder(nn.Module):
    def __init__(self, feature_dim: int = 100, hidden=(128, 64), latent: int = 32, dropout: float = 0.1):
        super().__init__()
        widths = [feature_dim * 2, *hidden, latent]
        encoder: list[nn.Module] = []
        for left, right in zip(widths, widths[1:]):
            encoder.extend([nn.Linear(left, right), nn.GELU(), nn.Dropout(dropout)])
        self.encoder = nn.Sequential(*encoder)
        decoder_widths = [latent, *reversed(hidden), feature_dim]
        decoder: list[nn.Module] = []
        for index, (left, right) in enumerate(zip(decoder_widths, decoder_widths[1:])):
            decoder.append(nn.Linear(left, right))
            if index < len(decoder_widths) - 2:
                decoder.extend([nn.GELU(), nn.Dropout(dropout)])
        self.decoder = nn.Sequential(*decoder)

    def forward(self, values: torch.Tensor, masks: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(torch.cat((values, masks), dim=-1)))

    def loss_per_sample(self, values: torch.Tensor, masks: torch.Tensor) -> torch.Tensor:
        reconstructed = self(values, masks)
        numerator = ((reconstructed - values).square() * masks).sum(dim=-1)
        return numerator / masks.sum(dim=-1).clamp_min(1.0)
