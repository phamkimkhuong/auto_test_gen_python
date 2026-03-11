import pytest
from demo_inputs.math_utils import add, divide

@pytest.mark.parametrize("a, b", [(-1, -1), (0, 0), (1, 1)])
def test_add_boundary(a, b):
    result = add(a, b)
    assert isinstance(result, int)

@pytest.mark.parametrize("a, b", [(-1, -1), (0, 0), (1, 1)])
def test_divide_boundary(a, b):
    result = divide(a, b)
    assert isinstance(result, float)

