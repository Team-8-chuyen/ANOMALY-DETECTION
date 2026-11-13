from copy import deepcopy
import math

import numpy as np
import pytest

from itd.data.feature_preprocessing import FeaturePreprocessor
from pilot_fixtures import feature_row


def test_active_median_imputation_and_mask_column_order():
    rows = [feature_row(value=0), feature_row(value=2), feature_row(value=1000)]
    rows[-1]['m001'] = False
    processor = FeaturePreprocessor().fit(rows)
    transformed = processor.transform(rows)
    assert transformed.shape == (3, 200) and transformed.dtype == np.float32
    assert transformed[:, 0].tolist() == [0, 2, 1]
    assert transformed[:, 100].tolist() == [1, 1, 0]
    assert processor.to_dict()['counts'][0] == 2
    assert processor.to_dict()['medians'][0] == 1


def test_hidden_payload_cannot_change_fit_or_transform():
    row = feature_row(value=10)
    row['m001'] = False
    row['f001'] = float('nan')
    first = [feature_row(value=2), row]
    other = deepcopy(first)
    other[1]['f001'] = 'hidden payload'
    one, two = FeaturePreprocessor().fit(first), FeaturePreprocessor().fit(other)
    assert one.to_dict() == two.to_dict()
    np.testing.assert_array_equal(one.transform(first), two.transform(other))


def test_validation_values_do_not_modify_fitted_statistics():
    processor = FeaturePreprocessor().fit([feature_row(value=1), feature_row(value=3)])
    before = processor.to_dict()
    processor.transform([feature_row(day='2010-01-23', value=10000)])
    assert processor.to_dict() == before
    np.testing.assert_array_equal(processor.transform([feature_row(value=1)]),
                                  FeaturePreprocessor.from_dict(before).transform([feature_row(value=1)]))


@pytest.mark.parametrize('value', [True, None, float('nan'), float('inf'), '3'])
def test_active_feature_must_be_finite_numeric(value):
    row = feature_row()
    row['f001'] = value
    with pytest.raises(ValueError, match='f001'):
        FeaturePreprocessor().fit([row])


@pytest.mark.parametrize('flag', [0, 1, None, 'true'])
def test_mask_must_be_bool(flag):
    row = feature_row()
    row['m001'] = flag
    with pytest.raises(ValueError, match='m001'):
        FeaturePreprocessor().fit([row])


def test_no_active_fit_column_does_not_fall_back_to_validation():
    row = feature_row()
    row['m001'] = False
    with pytest.raises(ValueError, match='no active fit.*f001'):
        FeaturePreprocessor().fit([row])


def test_unfitted_and_empty_fit_are_rejected():
    processor = FeaturePreprocessor()
    with pytest.raises(ValueError):
        processor.fit([])
    with pytest.raises(ValueError):
        processor.transform([feature_row()])
    with pytest.raises(ValueError):
        processor.to_dict()


@pytest.mark.parametrize('key,value', [('fields', ['f100']), ('medians', [math.inf] * 100),
                                      ('counts', [True] * 100), ('n_fit_rows', 0), ('version', True)])
def test_invalid_serialized_feature_state_is_rejected(key, value):
    state = FeaturePreprocessor().fit([feature_row()]).to_dict()
    state[key] = value
    with pytest.raises(ValueError):
        FeaturePreprocessor.from_dict(state)


def test_empty_transform_preserves_matrix_shape():
    assert FeaturePreprocessor().fit([feature_row()]).transform([]).shape == (0, 200)
