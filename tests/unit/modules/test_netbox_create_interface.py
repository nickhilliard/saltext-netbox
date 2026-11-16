"""
Tests for netbox.create_interface on NetBox 4.
"""

from unittest.mock import patch

import pytest
from salt.exceptions import CommandExecutionError

from saltext.netbox.modules import netbox

pytest.importorskip("pynetbox")


@pytest.fixture
def configure_loader_modules():
    return {netbox: {}}


def _lookup(_app, endpoint, **kwargs):
    if endpoint == "devices":
        return {"id": 1, "name": "edge_router"}
    if kwargs.get("name") == "ae13":  # the LAG parent exists
        return {"id": 50, "name": "ae13"}
    return None  # the interface being created does not exist yet


def _create(**kwargs):
    with (
        patch.object(netbox, "get_", side_effect=_lookup),
        patch.object(netbox, "_add", return_value={"id": 99}) as add,
    ):
        ret = netbox.create_interface("edge_router", "xe-0/0/1", **kwargs)
    payload = add.call_args.args[2] if add.called else None
    return ret, payload


def test_interface_type_is_sent():
    ret, payload = _create(interface_type="1000base-t")
    assert payload["type"] == "1000base-t"
    assert "form_factor" not in payload
    assert ret == {"dcim": {"interfaces": {99: payload}}}


@pytest.mark.parametrize("interface_type", [None, ""])
def test_interface_type_is_required(interface_type):
    with (
        patch.object(netbox, "get_", side_effect=_lookup) as get,
        patch.object(netbox, "_add") as add,
    ):
        with pytest.raises(CommandExecutionError, match="interface_type is required"):
            netbox.create_interface("edge_router", "xe-0/0/1", interface_type=interface_type)
    get.assert_not_called()
    add.assert_not_called()


def test_lag_does_not_need_an_interface_type():
    _, payload = _create(lag=True)
    assert payload["type"] == "lag"


def test_lag_interface_has_type_lag():
    _, payload = _create(lag=True, interface_type="1000base-t")
    assert payload["type"] == "lag"


def test_lag_member_points_to_its_parent():
    _, payload = _create(lag_parent="ae13", interface_type="10gbase-x-sfpp")
    assert payload["lag"] == 50


@pytest.mark.parametrize("form_factor", [1200, 200, "lag"])
def test_form_factor_is_refused(form_factor):
    with patch.object(netbox, "_add") as add:
        with pytest.raises(CommandExecutionError, match="interface_type"):
            netbox.create_interface("edge_router", "xe-0/0/1", form_factor=form_factor)
    add.assert_not_called()
