"""
Tests for netbox.create_interface_connection on NetBox 4.
"""

from unittest.mock import patch

import pytest
from salt.exceptions import CommandExecutionError

from saltext.netbox.modules import netbox

pytest.importorskip("pynetbox")


@pytest.fixture
def configure_loader_modules():
    return {netbox: {}}


def test_creates_a_cable_between_the_interfaces():
    with patch.object(netbox, "_add", return_value={"id": 7}) as add:
        ret = netbox.create_interface_connection(123, "456")
    payload = {
        "a_terminations": [{"object_type": "dcim.interface", "object_id": 123}],
        "b_terminations": [{"object_type": "dcim.interface", "object_id": 456}],
    }
    add.assert_called_once_with("dcim", "cables", payload)
    assert ret == {"dcim": {"cables": {7: payload}}}


def test_returns_false_if_netbox_refuses():
    with patch.object(netbox, "_add", return_value=False):
        assert netbox.create_interface_connection(1, 2) is False


@pytest.mark.parametrize("bad", ["../1", "1/../2", "abc", 0, -1, None])
def test_rejects_invalid_interface_ids(bad):
    with patch.object(netbox, "_add") as add:
        with pytest.raises(CommandExecutionError):
            netbox.create_interface_connection(bad, 2)
        with pytest.raises(CommandExecutionError):
            netbox.create_interface_connection(1, bad)
    add.assert_not_called()
