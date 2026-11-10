from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from itd.data.datasets import RobustStats, choose_max_len, window_slices
from itd.data.labels import read_r42_answer_events
from itd.data.split import chronological_split, assert_no_temporal_overlap
from itd.scoring.fusion import ScoreStats, fuse_scores


def test_chronological_split_has_no_overlap():
    days = pd.Series(pd.date_range("2020-01-01", periods=100, freq="D"))
    split, bounds = chronological_split(days)
    frame = pd.DataFrame({"day": days, "split": split})
    assert_no_temporal_overlap(frame)
    assert (split == "train").sum() == 60
    assert (split == "validation").sum() == 15
    assert bounds.train_end == pd.Timestamp("2020-03-01")


def test_robust_stats_are_train_only_and_stable():
    train = np.array([[0.0, 1.0], [1.0, 1.0], [2.0, 1.0]])
    stats = RobustStats.fit(train)
    before = stats.transform(np.array([[3.0, 1.0]]))
    _future = np.array([[99999.0, -99999.0]])
    after = stats.transform(np.array([[3.0, 1.0]]))
    np.testing.assert_array_equal(before, after)
    assert np.isfinite(after).all()


def test_max_len_and_windows_do_not_drop_tail():
    assert choose_max_len(np.array([10, 20, 70])) == 128
    slices = window_slices(300, 128)
    assert [(item.start, item.stop) for item in slices] == [(0, 128), (128, 256), (256, 300)]


def test_score_fusion_endpoints_and_train_stats():
    stats = ScoreStats.fit([1.0, 2.0, 3.0])
    z_beh = stats.transform([2.0, 3.0])
    z_seq = np.array([9.0, 8.0])
    np.testing.assert_allclose(fuse_scores(z_beh, z_seq, 1.0), z_beh)
    np.testing.assert_allclose(fuse_scores(z_beh, z_seq, 0.0), z_seq)
    with pytest.raises(ValueError):
        fuse_scores(z_beh, z_seq, 1.1)


def test_answer_parser_ignores_other_releases(tmp_path: Path):
    good = tmp_path / "r4.2-1"
    bad = tmp_path / "r5.2-1"
    good.mkdir(); bad.mkdir()
    (good / "r4.2-1-U1.csv").write_text("logon,{ID1},01/01/2010 08:00:00,U1,PC1,Logon\n", encoding="utf-8")
    (bad / "r5.2-1-U2.csv").write_text("logon,{ID2},01/01/2010 08:00:00,U2,PC2,Logon\n", encoding="utf-8")
    result = read_r42_answer_events(tmp_path)
    assert result.event_id.tolist() == ["{ID1}"]


torch = pytest.importorskip("torch")

from itd.models.feature_ae import FeatureAutoencoder
from itd.models.tcn_transformer_ae import TCNTransformerAutoencoder


def test_feature_autoencoder_shape_and_masked_loss():
    model = FeatureAutoencoder(feature_dim=4, hidden=(8,), latent=3, dropout=0.0)
    values = torch.randn(3, 4)
    masks = torch.tensor([[1, 1, 1, 1], [1, 0, 1, 0], [0, 0, 0, 0]], dtype=torch.float32)
    output = model(values, masks)
    loss = model.loss_per_sample(values, masks)
    assert output.shape == values.shape and loss.shape == (3,)
    assert torch.isfinite(loss).all()


def test_sequence_autoencoder_shape_and_padding_loss():
    model = TCNTransformerAutoencoder(12, 5, d_model=8, dilations=(1, 2), n_layers=1,
                                      n_heads=2, max_len=8, dropout=0.0)
    tokens = torch.tensor([[1, 2, 3, 0], [4, 5, 0, 0]])
    continuous = torch.randn(2, 4, 5)
    padding = tokens.eq(0)
    token_hat, continuous_hat = model(tokens, continuous, padding)
    loss = model.loss_per_sample(tokens, continuous, padding)
    assert token_hat.shape == (2, 4, 12)
    assert continuous_hat.shape == continuous.shape
    assert loss.shape == (2,) and torch.isfinite(loss).all()


def test_feature_autoencoder_can_overfit_one_batch():
    torch.manual_seed(1)
    model = FeatureAutoencoder(feature_dim=3, hidden=(8,), latent=4, dropout=0.0)
    values = torch.randn(4, 3)
    masks = torch.ones_like(values)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.03)
    initial = float(model.loss_per_sample(values, masks).mean().detach())
    for _ in range(80):
        loss = model.loss_per_sample(values, masks).mean()
        optimizer.zero_grad(); loss.backward(); optimizer.step()
    final = float(model.loss_per_sample(values, masks).mean().detach())
    assert final < initial * 0.1
