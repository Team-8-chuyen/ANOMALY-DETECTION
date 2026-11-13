from copy import deepcopy
import json

import numpy as np
import pytest

from itd.data.sequence_dataset import CATEGORICAL_FIELDS, NUMERIC_FIELDS
from itd.data.sequence_preprocessing import SequencePreprocessor
from pilot_fixtures import sequence_day


def test_train_only_standardization_and_empty_string_category():
    day = sequence_day(length=2)
    for field in NUMERIC_FIELDS:
        day.rows[0][field], day.rows[1][field] = 1.0, 3.0
    day.rows[0]['file_extension_id'] = ''
    processor = SequencePreprocessor().fit([day])
    transformed = processor.transform(day)
    np.testing.assert_allclose(transformed.numeric[0], -1)
    np.testing.assert_allclose(transformed.numeric[1], 1)
    assert transformed.cat[0, CATEGORICAL_FIELDS.index('file_extension_id')] == 2
    assert processor.vocab_sizes[CATEGORICAL_FIELDS.index('file_extension_id')] == 4
    assert processor.to_dict()['fit_start'] == day.day


def test_constant_numeric_field_has_unit_scale():
    day = sequence_day(length=1)
    processor = SequencePreprocessor().fit([day])
    assert processor.to_dict()['scales'] == [1.0] * 13
    np.testing.assert_array_equal(processor.transform(day).numeric, np.zeros((1, 13)))


def test_literal_reserved_token_names_are_observed_categories_not_special_ids():
    day = sequence_day(length=2)
    day.rows[0]['event_token'], day.rows[1]['event_token'] = '<PAD>', '<UNK>'
    encoded = SequencePreprocessor().fit([day]).transform(day)
    assert encoded.cat[:, 0].tolist() == [2, 3]


def test_unseen_validation_category_maps_to_unk_without_mutating_state():
    day = sequence_day(length=2)
    processor = SequencePreprocessor().fit([day])
    before = processor.to_dict()
    validation = sequence_day(day='2010-01-23', length=1)
    validation.rows[0]['event_token'] = 'never_seen'
    validation.rows[0]['gap_log1p'] = 10000.0
    output = processor.transform(validation)
    assert output.cat[0, 0] == 1
    assert output.unseen_counts['event_token'] == 1
    assert processor.to_dict() == before


def test_inactive_payloads_are_ignored_before_any_coercion():
    day = sequence_day(length=2)
    mask = [True] * 24
    for j in (0, 1, 11):
        mask[j] = False
    day.rows[1]['attribute_mask'] = json.dumps(mask)
    day.rows[1]['event_token'] = None
    day.rows[1]['time_sin'] = float('nan')
    day.rows[1]['extension_present'] = 'hidden'
    processor = SequencePreprocessor().fit([day])
    output = processor.transform(day)
    assert output.cat[1, 0] == 0
    assert output.numeric[1, 0] == 0
    assert output.boolean[1, 0] == 0
    changed = deepcopy(day)
    changed.rows[1].update(event_token=123, time_sin='hidden', extension_present=None)
    np.testing.assert_array_equal(output.cat, processor.transform(changed).cat)
    np.testing.assert_array_equal(output.numeric, processor.transform(changed).numeric)
    assert processor.to_dict() == SequencePreprocessor().fit([changed]).to_dict()


@pytest.mark.parametrize('mask', ['invalid', '{}', '[true]', json.dumps([1] * 24), json.dumps([False] * 24), [True] * 24])
def test_invalid_masks_are_rejected(mask):
    day = sequence_day(length=1)
    day.rows[0]['attribute_mask'] = mask
    with pytest.raises(ValueError, match='attribute|active'):
        SequencePreprocessor().fit([day])


@pytest.mark.parametrize('field,value', [('gap_bucket', True), ('event_token', None),
                                       ('extension_present', 1), ('gap_log1p', float('inf'))])
def test_active_attributes_are_strictly_typed(field, value):
    day = sequence_day(length=1)
    day.rows[0][field] = value
    with pytest.raises(ValueError, match=field):
        SequencePreprocessor().fit([day])


def test_no_active_fit_field_is_an_error():
    day = sequence_day(length=2)
    mask = [True] * 24
    mask[9] = False
    for row in day.rows:
        row['attribute_mask'] = json.dumps(mask)
    with pytest.raises(ValueError, match='no active fit.*file_extension_id'):
        SequencePreprocessor().fit([day])


def test_serialization_roundtrip_preserves_all_encoded_values():
    day = sequence_day(length=3)
    original = SequencePreprocessor().fit([day])
    loaded = SequencePreprocessor.from_dict(original.to_dict())
    assert original.to_dict() == loaded.to_dict()
    for field in ('cat', 'numeric', 'boolean', 'attribute_mask'):
        np.testing.assert_array_equal(getattr(original.transform(day), field),
                                      getattr(loaded.transform(day), field))


@pytest.mark.parametrize('key,value', [('fields', []), ('scales', [0.0] * 13),
                                      ('counts', [False] * 24), ('version', True),
                                      ('fit_start', '2010-02-01'), ('cohort_sha256', 'invalid')])
def test_invalid_serialized_sequence_state_is_rejected(key, value):
    state = SequencePreprocessor().fit([sequence_day()]).to_dict()
    state[key] = value
    with pytest.raises(ValueError):
        SequencePreprocessor.from_dict(state)
