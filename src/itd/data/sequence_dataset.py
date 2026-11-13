"""Sequence records and loss-safe padding for SPEC-004 sections 3/4.3."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .sequence_preprocessing import SequencePreprocessor

SEQUENCE_FIELDS = (
    'event_token', 'time_sin', 'time_cos', 'gap_log1p', 'gap_bucket',
    'calendar_context', 'pc_context', 'run_count_log1p', 'run_span_log1p',
    'file_extension_id', 'filename_length_log1p', 'extension_present', 'multi_dot',
    'url_scheme_id', 'hostname_length_log1p', 'url_length_log1p', 'path_depth_log1p',
    'query_present', 'recipient_count_log1p', 'external_recipient_ratio', 'bcc_present',
    'attachment_count_log1p', 'email_size_log1p', 'sender_context',
)
CAT_INDICES = (0, 4, 5, 6, 9, 13, 23)
NUMERIC_INDICES = (1, 2, 3, 7, 8, 10, 14, 15, 16, 18, 19, 21, 22)
BOOLEAN_INDICES = (11, 12, 17, 20)
CATEGORICAL_FIELDS = tuple(SEQUENCE_FIELDS[i] for i in CAT_INDICES)
NUMERIC_FIELDS = tuple(SEQUENCE_FIELDS[i] for i in NUMERIC_INDICES)
BOOLEAN_FIELDS = tuple(SEQUENCE_FIELDS[i] for i in BOOLEAN_INDICES)
MAX_WINDOW_LENGTH = 128


@dataclass(frozen=True)
class SequenceSchema:
    fields: tuple[str, ...] = SEQUENCE_FIELDS
    categorical_fields: tuple[str, ...] = CATEGORICAL_FIELDS
    numeric_fields: tuple[str, ...] = NUMERIC_FIELDS
    boolean_fields: tuple[str, ...] = BOOLEAN_FIELDS


@dataclass
class SequenceDay:
    user: str
    day: str
    rows: list[dict]
    metadata: dict


@dataclass
class SequenceWindow:
    user: str
    day: str
    offset: int
    rows: list[dict]
    metadata: dict

    @property
    def length(self) -> int:
        return len(self.rows)


@dataclass
class SequenceBatch:
    cat: Any
    numeric: Any
    boolean: Any
    attribute_mask: Any
    time_mask: Any
    lengths: Any
    windows: list[SequenceWindow]


def window_day(day: SequenceDay, max_len: int) -> list[SequenceWindow]:
    """Keep every compressed row exactly once, resetting at each user-day."""
    if type(max_len) is not int or not 1 <= max_len <= MAX_WINDOW_LENGTH:
        raise ValueError('max_len must be an integer in [1, 128]')
    if not isinstance(day, SequenceDay) or not isinstance(day.rows, list) or not day.rows:
        raise ValueError('a sequence day must contain at least one row')
    return [SequenceWindow(day.user, day.day, offset, day.rows[offset:offset + max_len],
                           dict(day.metadata))
            for offset in range(0, len(day.rows), max_len)]


def collate_windows(windows: list[SequenceWindow], preprocessor: SequencePreprocessor,
                    pad_to: int | None = None) -> SequenceBatch:
    """Pad only at the right; raw hidden values are sanitized by transform first."""
    import torch

    if not isinstance(windows, list) or not windows:
        raise ValueError('cannot collate an empty batch')
    if any(not isinstance(w, SequenceWindow) or not 1 <= w.length <= MAX_WINDOW_LENGTH
           for w in windows):
        raise ValueError('windows must have 1..128 rows')
    lengths = [w.length for w in windows]
    length = max(lengths) if pad_to is None else pad_to
    if type(length) is not int or not max(lengths) <= length <= MAX_WINDOW_LENGTH:
        raise ValueError('pad_to must cover all valid rows and be at most 128')
    size = len(windows)
    cat = np.zeros((size, length, len(CAT_INDICES)), dtype=np.int64)
    numeric = np.zeros((size, length, len(NUMERIC_INDICES)), dtype=np.float32)
    boolean = np.zeros((size, length, len(BOOLEAN_INDICES)), dtype=np.float32)
    attributes = np.zeros((size, length, len(SEQUENCE_FIELDS)), dtype=np.bool_)
    time_mask = np.zeros((size, length), dtype=np.bool_)
    for i, window in enumerate(windows):
        encoded = preprocessor.transform(window)
        n = lengths[i]
        cat[i, :n] = encoded.cat
        numeric[i, :n] = encoded.numeric
        boolean[i, :n] = encoded.boolean
        attributes[i, :n] = encoded.attribute_mask
        time_mask[i, :n] = True
    return SequenceBatch(torch.from_numpy(cat), torch.from_numpy(numeric),
                         torch.from_numpy(boolean), torch.from_numpy(attributes),
                         torch.from_numpy(time_mask), torch.tensor(lengths, dtype=torch.int64),
                         list(windows))
