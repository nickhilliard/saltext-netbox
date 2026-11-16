"""
Tests for netbox.create_circuit_termination on NetBox 4.
"""

from unittest.mock import patch

import pytest

from saltext.netbox.modules import netbox

pytest.importorskip("pynetbox")


@pytest.fixture
def configure_loader_modules():
    return {netbox: {}}


DEVICE = {"id": 1, "name": "myminion", "site": {"id": 8, "name": "BRU"}}
INTERFACE = {"id": 13, "name": "xe-0/0/1"}
CIRCUIT = {"id": 21, "cid": "NEW_CIRCUIT_01"}


def _lookup(existing=None, **missing):
    def lookup(_app, endpoint, **_kwargs):
        if endpoint in missing:
            return None
        return {
            "devices": DEVICE,
            "interfaces": INTERFACE,
            "circuits": CIRCUIT,
            "circuit-terminations": existing,
        }[endpoint]

    return lookup


def _add(_app, endpoint, _payload):
    return {"circuit-terminations": {"id": 30}, "cables": {"id": 40}}[endpoint]


def test_terminates_at_the_device_site_and_cables_to_the_interface():
    with (
        patch.object(netbox, "get_", side_effect=_lookup()) as get,
        patch.object(netbox, "_add", side_effect=_add) as add,
    ):
        ret = netbox.create_circuit_termination(
            "NEW_CIRCUIT_01", "xe-0/0/1", "myminion", 10000, xconnect_id="XCON01", term_side="Z"
        )
    termination = {
        "circuit": 21,
        "termination_type": "dcim.site",
        "termination_id": 8,
        "port_speed": 10000,
        "term_side": "Z",
        "xconnect_id": "XCON01",
    }
    cable = {
        "a_terminations": [{"object_type": "circuits.circuittermination", "object_id": 30}],
        "b_terminations": [{"object_type": "dcim.interface", "object_id": 13}],
    }
    assert add.call_args_list[0].args == ("circuits", "circuit-terminations", termination)
    assert add.call_args_list[1].args == ("dcim", "cables", cable)
    assert ret == {
        "circuits": {"circuit-terminations": {30: termination}},
        "dcim": {"cables": {40: cable}},
    }
    # the existing termination is looked up for this circuit and side only
    get.assert_any_call("circuits", "circuit-terminations", circuit_id=21, term_side="Z")


def test_existing_termination_on_that_side_is_not_duplicated():
    with (
        patch.object(netbox, "get_", side_effect=_lookup(existing={"id": 30})),
        patch.object(netbox, "_add") as add,
    ):
        assert (
            netbox.create_circuit_termination("NEW_CIRCUIT_01", "xe-0/0/1", "myminion", 1) is False
        )
    add.assert_not_called()


@pytest.mark.parametrize("missing", ["devices", "interfaces", "circuits"])
def test_missing_objects_return_false(missing):
    with (
        patch.object(netbox, "get_", side_effect=_lookup(**{missing: True})),
        patch.object(netbox, "_add") as add,
    ):
        assert (
            netbox.create_circuit_termination("NEW_CIRCUIT_01", "xe-0/0/1", "myminion", 1) is False
        )
    add.assert_not_called()


def test_failed_cable_is_logged_and_returns_false():
    with (
        patch.object(netbox, "get_", side_effect=_lookup()),
        patch.object(
            netbox,
            "_add",
            side_effect=lambda _app, ep, _payload: {"id": 30} if ep != "cables" else False,
        ),
        patch.object(netbox.log, "error") as fake_error,
    ):
        assert (
            netbox.create_circuit_termination("NEW_CIRCUIT_01", "xe-0/0/1", "myminion", 1) is False
        )
    assert "could not connect" in fake_error.call_args.args[0]
