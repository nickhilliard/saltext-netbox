"""
Tests for the netbox execution module.

Ported from Salt 3006 (``tests/unit/modules/test_netbox.py``).

:codeauthor: :email:`Zach Moody <zmoody@do.co>`
"""

from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

import pytest
from salt.exceptions import CommandExecutionError

from saltext.netbox.modules import netbox
from tests.support.fake_netbox import API_TOKEN
from tests.support.fake_netbox import FakeNetBox

pytest.importorskip("pynetbox")


NETBOX_RESPONSE_STUB = {
    "device_name": "test1-router1",
    "url": "http://test/",
    "device_role": {"name": "router", "url": "http://test/"},
}


def mocked_clean_kwargs_filter(**kwargs):  # pylint: disable=unused-argument
    """
    Mocked args.clean_kwargs for filter tests
    """
    return {"site": "test"}


def mocked_clean_kwargs_get(**kwargs):  # pylint: disable=unused-argument
    """
    Mocked args.clean_kwargs for get tests
    """
    return {"name": "test"}


@pytest.fixture
def configure_loader_modules():
    return {netbox: {}}


@pytest.fixture(autouse=True)
def _mock_config():
    with patch.object(netbox, "_config", MagicMock()):
        yield


@pytest.fixture(scope="module")
def _fake_netbox_server():
    server = FakeNetBox().start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def fake_netbox(_fake_netbox_server):
    """
    A fake NetBox API server, with the module configured to use it.
    """
    server = _fake_netbox_server
    server.requests.clear()
    config = {"url": server.base[: -len("/api")], "token": API_TOKEN}
    with patch.object(netbox, "_config", MagicMock(return_value=config)):
        yield server


def test_get_by_id():
    with patch("pynetbox.api", MagicMock()) as mock:
        with patch("salt.utils.args.clean_kwargs", mocked_clean_kwargs_get):
            netbox.get_("dcim", "devices", id=1)
            assert mock.mock_calls[1] == call().dcim.devices.get(1)


def test_get_by_name():
    with patch("pynetbox.api", MagicMock()) as mock:
        with patch("salt.utils.args.clean_kwargs", mocked_clean_kwargs_get):
            netbox.get_("dcim", "devices", name="test")
            assert mock.mock_calls[1] == call().dcim.devices.get(name="test")


def test_filter_by_site():
    with patch("pynetbox.api", MagicMock()) as mock:
        with patch("salt.utils.args.clean_kwargs", mocked_clean_kwargs_filter):
            netbox.filter_("dcim", "devices", site="test")
            assert mock.mock_calls[1] == call().dcim.devices.filter(site="test")


def test_filter_url():
    strip_url = netbox._strip_url_field(NETBOX_RESPONSE_STUB)
    assert "url" not in strip_url
    assert "url" not in strip_url["device_role"]


def test_token_present():
    with patch("pynetbox.api", MagicMock()) as mock:
        with patch("salt.utils.args.clean_kwargs", mocked_clean_kwargs_get):
            netbox.get_("dcim", "devices", name="test")
            assert "token" in mock.call_args[1]


@pytest.mark.parametrize("good,expected", [(1, 1), ("42", 42), (" 7 ", 7)])
def test_validate_id_accepts_positive_integers(good, expected):
    assert netbox._validate_id(good) == expected


@pytest.mark.parametrize(
    "bad",
    [
        "../sites/1",
        "1/../../users/tokens/3",
        "1?brief=1",
        "1#x",
        "",
        " ",
        "0",
        0,
        -3,
        True,
        1.5,
        None,
    ],
)
def test_validate_id_rejects_everything_else(bad):
    with pytest.raises(CommandExecutionError):
        netbox._validate_id(bad)


@pytest.mark.parametrize(
    "func,bad_id",
    [
        ("delete_inventory_item", "../sites/1"),
        ("delete_inventory_item", ""),
        ("delete_inventory_item", None),
        ("delete_ipaddress", "../../dcim/devices/12"),
        ("delete_ipaddress", 0),
        ("delete_ipaddress", None),
    ],
)
def test_delete_rejects_invalid_ids_without_calling_netbox(func, bad_id):
    with patch("pynetbox.api", MagicMock()) as mock:
        with pytest.raises(CommandExecutionError):
            getattr(netbox, func)(bad_id)
        mock.assert_not_called()


def test_get_rejects_path_traversal_id():
    with patch("pynetbox.api", MagicMock()) as mock:
        with pytest.raises(CommandExecutionError):
            netbox.get_("dcim", "devices", id="../sites/1")
        mock.return_value.dcim.devices.get.assert_not_called()


def test_delete_inventory_item_missing_returns_false():
    with patch("pynetbox.api", MagicMock()) as mock:
        mock.return_value.dcim.inventory_items = MagicMock()
        getattr(mock.return_value.dcim, "inventory-items").get.return_value = None
        assert netbox.delete_inventory_item(5) is False


def test_path_traversal_does_not_reach_another_object(fake_netbox):
    """
    End-to-end with real pynetbox: before the fix, this deleted site 1.
    """
    with pytest.raises(CommandExecutionError):
        netbox.delete_inventory_item("../sites/1")
    assert not [r for r in fake_netbox.requests if r[0] == "DELETE"]
    assert not any("/sites/" in r[1] for r in fake_netbox.requests)


def test_delete_inventory_item_none_does_not_delete_the_only_item(fake_netbox):
    """
    _get() treats id=None as "no id" and does an unfiltered lookup, which
    returns the object if exactly one exists. delete_inventory_item(None)
    must not delete it.
    """
    fake_netbox.collections["dcim/inventory-items"] = [
        {"id": 9, "url": "{base}/dcim/inventory-items/9/", "name": "only-item"}
    ]
    try:
        with pytest.raises(CommandExecutionError):
            netbox.delete_inventory_item(None)
        assert not fake_netbox.requests
    finally:
        del fake_netbox.collections["dcim/inventory-items"]
