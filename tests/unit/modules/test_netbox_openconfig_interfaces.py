"""
Tests for netbox.openconfig_interfaces on NetBox 4.
"""

from unittest.mock import patch

import pytest

from saltext.netbox.modules import netbox

pytest.importorskip("pynetbox")


@pytest.fixture
def configure_loader_modules():
    return {netbox: {}}


INTERFACES = [
    {"id": 1, "name": "xe-0/0/0", "enabled": True, "description": "uplink", "mtu": 9000},
    {"id": 2, "name": "xe-0/0/0.100", "enabled": True, "description": "", "mtu": None},
    {"id": 3, "name": "lo0", "enabled": True, "description": "", "mtu": None},
]


def _ip(address, family, assigned_name=None, assigned_type="dcim.interface"):
    """
    An IP address as NetBox 4 returns it.
    """
    return {
        "address": address,
        "family": {"value": family, "label": f"IPv{family}"},
        "assigned_object_type": assigned_type if assigned_name else None,
        "assigned_object_id": 1 if assigned_name else None,
        "assigned_object": {"id": 1, "name": assigned_name} if assigned_name else None,
    }


def _openconfig(ipaddresses):
    with (
        patch.object(netbox, "get_interfaces", return_value=INTERFACES),
        patch.object(netbox, "get_ipaddresses", return_value=ipaddresses),
    ):
        return netbox.openconfig_interfaces("edge_router")["interfaces"]["interface"]


def test_addresses_are_placed_on_their_interface_and_family():
    oc_if = _openconfig(
        [
            _ip("192.0.2.1/24", 4, "xe-0/0/0"),
            _ip("2001:db8::1/64", 6, "xe-0/0/0"),
            _ip("198.51.100.1/31", 4, "xe-0/0/0.100"),
        ]
    )
    unit0 = oc_if["xe-0/0/0"]["subinterfaces"]["subinterface"]["0"]
    assert unit0["ipv4"]["addresses"]["address"]["192.0.2.1"] == {
        "config": {"ip": "192.0.2.1", "prefix_length": 24}
    }
    assert unit0["ipv6"]["addresses"]["address"]["2001:db8::1"] == {
        "config": {"ip": "2001:db8::1", "prefix_length": 64}
    }
    unit100 = oc_if["xe-0/0/0"]["subinterfaces"]["subinterface"]["100"]
    assert "198.51.100.1" in unit100["ipv4"]["addresses"]["address"]
    assert oc_if["xe-0/0/0"]["config"] == {
        "name": "xe-0/0/0",
        "enabled": True,
        "description": "uplink",
        "mtu": 9000,
    }


def test_integer_family_still_works():
    address = _ip("192.0.2.1/24", 4, "lo0")
    address["family"] = 4
    oc_if = _openconfig([address])
    assert "ipv4" in oc_if["lo0"]["subinterfaces"]["subinterface"]["0"]


@pytest.mark.parametrize(
    "address",
    [
        _ip("192.0.2.9/32", 4),  # not assigned to anything
        _ip("192.0.2.8/32", 4, "group1", assigned_type="ipam.fhrpgroup"),
    ],
)
def test_addresses_not_on_a_device_interface_are_skipped(address):
    oc_if = _openconfig([address])
    assert "group1" not in oc_if
    for interface in oc_if.values():
        for subif in interface["subinterfaces"]["subinterface"].values():
            assert "ipv4" not in subif


def test_address_on_an_unlisted_interface_does_not_crash():
    oc_if = _openconfig([_ip("192.0.2.7/32", 4, "ae0.0")])
    assert (
        "192.0.2.7"
        in oc_if["ae0"]["subinterfaces"]["subinterface"]["0"]["ipv4"]["addresses"]["address"]
    )
