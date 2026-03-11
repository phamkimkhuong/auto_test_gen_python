import pytest
from demo_inputs.string_utils import greet, is_palindrome

@pytest.mark.parametrize("name", ['', 'test', ' ', 'Tiếng Việt'])
def test_greet_boundary(name):
    result = greet(name)
    assert isinstance(result, str)

@pytest.mark.parametrize("s", ['', 'test', ' ', 'Tiếng Việt'])
def test_is_palindrome_boundary(s):
    result = is_palindrome(s)
    assert isinstance(result, bool)

