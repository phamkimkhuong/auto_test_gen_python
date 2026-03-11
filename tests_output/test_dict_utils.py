import pytest
from demo_inputs.dict_utils import get_value

@pytest.mark.parametrize("d, key", [({}, ''), ({'test': 1}, 'test'), ({}, ' '), ({'test': 1}, 'Tiếng Việt')])
def test_get_value_boundary(d, key):
    result = get_value(d, key)
    assert isinstance(result, int)

