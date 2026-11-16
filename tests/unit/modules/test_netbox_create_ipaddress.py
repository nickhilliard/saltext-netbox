"""
Tests for netbox.create_ipaddress on NetBox 4.
"""

from unittest.mock import patch

import pytest

from saltext.netbox.modules import netbox

pytest.importorskip("pynetbox")


@pytest.fixture
def configure_loader_modules():
    return {netbox: {}}


def _lookup(_app, endpoint, **_kwargs):
    return {
        "devices": {"id": 1, "name": "edge_router"},
        "interfaces": {"id": 13, "name": "ae13"},
        "ip-addresses": None,  # not assigned yet
    }[endpoint]


def test_assigns_the_address_to_the_interface():
    with (
        patch.object(netbox, "get_", side_effect=_lookup),
        patch.object(netbox, "_add", return_value={"id": 5}) as add,
    ):
        ret = netbox.create_ipaddress("192.168.1.1/24", 4, device="edge_router", interface="ae13")
    payload = add.call_args.args[2]
    assert payload["assigned_object_type"] == "dcim.interface"
    assert payload["assigned_object_id"] == 13
    assert "interface" not in payload
    assert ret == {"ipam": {"ip-addresses": payload}}


def test_without_an_interface_the_address_is_unassigned():
    with patch.object(netbox, "_add", return_value={"id": 5}) as add:
        netbox.create_ipaddress("192.168.1.1/24", 4)
    payload = add.call_args.args[2]
    assert "assigned_object_type" not in payload
    assert "assigned_object_id" not in payload


def test_existing_assignment_is_not_duplicated():
    def lookup(app, endpoint, **kwargs):
        if endpoint == "ip-addresses":
            return {"id": 5, "address": "192.168.1.1/24"}
        return _lookup(app, endpoint, **kwargs)

    with (
        patch.object(netbox, "get_", side_effect=lookup),
        patch.object(netbox, "_add") as add,
    ):
        assert (
            netbox.create_ipaddress("192.168.1.1/24", 4, device="edge_router", interface="ae13")
            is False
        )
    add.assert_not_called()
