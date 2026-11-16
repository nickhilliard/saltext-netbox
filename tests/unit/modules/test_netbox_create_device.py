"""
Tests for netbox.create_device on NetBox 4.
"""

from unittest.mock import patch

import pytest

from saltext.netbox.modules import netbox

pytest.importorskip("pynetbox")


@pytest.fixture
def configure_loader_modules():
    return {netbox: {}}


LOOKUPS = {
    ("dcim", "device-roles"): {"id": 3, "name": "router"},
    ("dcim", "device-types"): {"id": 4, "model": "MX480"},
    ("dcim", "sites"): {"id": 5, "name": "BRU"},
}


def test_create_device_sends_role_not_device_role():
    with (
        patch.object(netbox, "get_", side_effect=lambda app, ep, **kw: LOOKUPS[(app, ep)]),
        patch.object(netbox, "_add", return_value={"id": 99}) as add,
    ):
        ret = netbox.create_device("edge_router", "router", "MX480", "Juniper", "BRU")
    payload = {"name": "edge_router", "device_type": 4, "role": 3, "site": 5}
    add.assert_called_once_with("dcim", "devices", payload)
    assert ret == {"dcim": {"devices": payload}}


@pytest.mark.parametrize("missing", list(LOOKUPS))
def test_create_device_returns_false_if_a_component_is_missing(missing):
    with (
        patch.object(
            netbox,
            "get_",
            side_effect=lambda app, ep, **kw: None if (app, ep) == missing else LOOKUPS[(app, ep)],
        ),
        patch.object(netbox, "_add") as add,
    ):
        assert netbox.create_device("edge_router", "router", "MX480", "Juniper", "BRU") is False
    add.assert_not_called()


def test_create_device_returns_false_if_netbox_refuses():
    with (
        patch.object(netbox, "get_", side_effect=lambda app, ep, **kw: LOOKUPS[(app, ep)]),
        patch.object(netbox, "_add", return_value=False),
    ):
        assert netbox.create_device("edge_router", "router", "MX480", "Juniper", "BRU") is False
