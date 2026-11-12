import pytest
import salt.modules.test as testmod

import saltext.netbox.modules.netbox as netbox_module


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "__salt__": {"test.echo": testmod.echo},
    }
    return {
        netbox_module: module_globals,
    }


def test_replace_this_this_with_something_meaningful():
    echo_str = "Echoed!"
    assert netbox_module.example_function(echo_str) == echo_str
