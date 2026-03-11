import pytest
from demo_inputs.condition_utils import check_status

@pytest.mark.parametrize("code", [-1, 0, 1, 199, 200, 201, 403, 404, 405])
def test_check_status_boundary(code):
    result = check_status(code)
    assert isinstance(result, str)

