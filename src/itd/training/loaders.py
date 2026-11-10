"""Load SPEC-002 model artifacts into PyTorch datasets."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, TensorDataset

from itd.data.datasets import RobustStats, window_slices


FEATURE_COLUMNS = [f"f{i:03d}" for i in range(1, 101)]
MASK_COLUMNS = [f"m{i:03d}" for i in range(1, 101)]
SEQUENCE_EXCLUDE = {"user", "day", "event_index", "event_token", "attribute_mask"}


def behaviour_datasets(path: Path):
    frame = pd.read_parquet(path)
    train = frame.split.eq("train")
    stats = RobustStats.fit(frame.loc[train, FEATURE_COLUMNS].to_numpy(float))
    result = {}; keys = {}
    for split in ("train", "validation", "test"):
        part = frame.loc[frame.split.eq(split)]
        values = torch.from_numpy(stats.transform(part[FEATURE_COLUMNS].to_numpy(float)))
        masks = torch.from_numpy(part[MASK_COLUMNS].to_numpy(np.float32))
        result[split] = TensorDataset(values, masks)
        keys[split] = part[["user", "day"]].reset_index(drop=True)
    return result, stats, keys


@dataclass(frozen=True)
class SequenceEncoding:
    token_vocab: dict[str, int]
    category_vocab: dict[str, dict[str, int]]
    continuous_columns: tuple[str, ...]
    stats: RobustStats


class SequenceWindowDataset(Dataset):
    def __init__(self, tokens: np.ndarray, continuous: np.ndarray, windows: list[tuple[int, int]],
                 keys: list[tuple[str, pd.Timestamp]], max_len: int):
        self.tokens = tokens
        self.continuous = continuous
        self.windows = windows
        self.keys = keys
        self.max_len = max_len

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, index):
        start, stop = self.windows[index]
        length = stop - start
        tokens = np.zeros(self.max_len, dtype=np.int64)
        values = np.zeros((self.max_len, self.continuous.shape[1]), dtype=np.float32)
        padding = np.ones(self.max_len, dtype=bool)
        tokens[:length] = self.tokens[start:stop]
        values[:length] = self.continuous[start:stop]
        padding[:length] = False
        return {"tokens": torch.from_numpy(tokens), "continuous": torch.from_numpy(values),
                "padding_mask": torch.from_numpy(padding)}


def sequence_datasets(processed: Path, split_path: Path, max_len: int):
    index = pd.read_parquet(split_path, columns=["user", "day", "split"])
    index["day"] = pd.to_datetime(index["day"]).dt.normalize()
    frames = []
    for path in sorted((processed / "user_day_sequences").glob("*.parquet")):
        frame = pd.read_parquet(path)
        frame["day"] = pd.to_datetime(frame["day"]).dt.normalize()
        frames.append(frame.merge(index, on=["user", "day"], how="inner"))
    if not frames:
        raise FileNotFoundError("no Sequence parquet files found")
    frame = (pd.concat(frames, ignore_index=True)
             .sort_values(["user", "day", "event_index"])
             .reset_index(drop=True))
    train = frame.split.eq("train")
    token_values = sorted(frame.loc[train, "event_token"].astype(str).unique())
    token_vocab = {"<pad>": 0, "<unk>": 1, **{value: i + 2 for i, value in enumerate(token_values)}}
    category_columns = [column for column in frame.columns
                        if column not in SEQUENCE_EXCLUDE | {"split"}
                        and not pd.api.types.is_numeric_dtype(frame[column])]
    category_vocab = {}
    encoded = frame.copy()
    for column in category_columns:
        values = sorted(encoded.loc[train, column].fillna("").astype(str).unique())
        vocab = {"<unk>": 0, **{value: i + 1 for i, value in enumerate(values)}}
        category_vocab[column] = vocab
        encoded[column] = encoded[column].fillna("").astype(str).map(vocab).fillna(0).astype(float)
    continuous_columns = tuple(column for column in encoded.columns
                               if column not in SEQUENCE_EXCLUDE | {"split"})
    stats = RobustStats.fit(encoded.loc[train, continuous_columns].to_numpy(float))
    continuous = stats.transform(encoded.loc[:, continuous_columns].to_numpy(float))
    tokens = encoded.event_token.astype(str).map(token_vocab).fillna(1).to_numpy(np.int64)
    datasets = {}
    for split in ("train", "validation", "test"):
        windows = []; keys = []
        for key, group in encoded.groupby(["user", "day"], sort=False):
            if group.split.iat[0] != split:
                continue
            start = int(group.index.min())
            for item in window_slices(len(group), max_len):
                windows.append((start + item.start, start + item.stop))
                keys.append((str(key[0]), pd.Timestamp(key[1])))
        datasets[split] = SequenceWindowDataset(tokens, continuous, windows, keys, max_len)
    return datasets, SequenceEncoding(token_vocab, category_vocab, continuous_columns, stats)
