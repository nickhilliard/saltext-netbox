import pytest

pytestmark = [
    pytest.mark.requires_salt_modules("netbox.example_function"),
]


@pytest.fixture
def netbox(modules):
    return modules.netbox


def test_replace_this_this_with_something_meaningful(netbox):
    echo_str = "Echoed!"
    res = netbox.example_function(echo_str)
    assert res == echo_str
