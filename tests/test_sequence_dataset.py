import importlib.util

import numpy as np
import pytest

from itd.data.sequence_dataset import (SequenceSchema, window_day, collate_windows,
                                       CATEGORICAL_FIELDS, NUMERIC_FIELDS, BOOLEAN_FIELDS)
from itd.data.sequence_preprocessing import SequencePreprocessor
from pilot_fixtures import sequence_day


def test_schema_has_exact_typed_sequence24_partition():
    schema = SequenceSchema()
    assert len(schema.fields) == 24
    assert len(CATEGORICAL_FIELDS) == 7 and len(NUMERIC_FIELDS) == 13 and len(BOOLEAN_FIELDS) == 4
    assert set(CATEGORICAL_FIELDS + NUMERIC_FIELDS + BOOLEAN_FIELDS) == set(schema.fields)
    assert 'gap_bucket' in CATEGORICAL_FIELDS
    assert 'file_extension_id' in CATEGORICAL_FIELDS


def test_windowing_keeps_long_day_tail_once_without_crossing_day():
    day = sequence_day(length=129)
    windows = window_day(day, 128)
    assert [window.length for window in windows] == [128, 1]
    assert [window.offset for window in windows] == [0, 128]
    assert [row['event_index'] for window in windows for row in window.rows] == list(range(129))
    assert all((w.user, w.day) == (day.user, day.day) for w in windows)
    windows[0].metadata['role'] = 'changed copy'
    assert day.metadata['role'] == 'Engineer'


@pytest.mark.parametrize('length', [0, 129, True, 1.5])
def test_invalid_window_lengths_are_rejected(length):
    with pytest.raises(ValueError):
        window_day(sequence_day(), length)


def test_empty_day_is_rejected():
    with pytest.raises(ValueError):
        window_day(sequence_day(length=0), 128)


@pytest.mark.skipif(importlib.util.find_spec('torch') is None, reason='root installs accepted CPU torch')
def test_collation_uses_prefix_time_mask_and_zero_padding():
    import torch
    days = [sequence_day(length=3), sequence_day(user='U2', length=1)]
    preprocessor = SequencePreprocessor().fit(days)
    windows = [window_day(day, 128)[0] for day in days]
    batch = collate_windows(windows, preprocessor, pad_to=7)
    assert batch.cat.shape == (2, 7, 7)
    assert batch.numeric.shape == (2, 7, 13)
    assert batch.boolean.shape == (2, 7, 4)
    assert batch.attribute_mask.shape == (2, 7, 24)
    assert batch.lengths.dtype == torch.int64 and batch.lengths.device.type == 'cpu'
    assert batch.lengths.tolist() == [3, 1]
    assert batch.time_mask.tolist() == [[True] * 3 + [False] * 4, [True] + [False] * 6]
    assert batch.cat[1, 1:].count_nonzero() == 0
    assert batch.numeric[1, 1:].count_nonzero() == 0
    assert batch.boolean[1, 1:].count_nonzero() == 0
    assert batch.attribute_mask[1, 1:].count_nonzero() == 0
    np.testing.assert_array_equal(batch.cat[0, :3].numpy(), preprocessor.transform(days[0]).cat)


@pytest.mark.skipif(importlib.util.find_spec('torch') is None, reason='root installs accepted CPU torch')
@pytest.mark.parametrize('pad_to', [0, 2, 129, True])
def test_invalid_padding_cap_is_rejected(pad_to):
    day = sequence_day(length=3)
    processor = SequencePreprocessor().fit([day])
    with pytest.raises(ValueError):
        collate_windows(window_day(day, 128), processor, pad_to)
