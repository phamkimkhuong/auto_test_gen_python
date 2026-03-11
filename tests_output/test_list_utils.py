import pytest
from demo_inputs.list_utils import get_first

@pytest.mark.parametrize("items", [[], [1, 2, 3]])
def test_get_first_boundary(items):
    result = get_first(items)
    assert isinstance(result, int)

