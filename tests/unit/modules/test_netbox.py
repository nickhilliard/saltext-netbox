"""
Tests for the netbox execution module.

Ported from Salt 3006 (``tests/unit/modules/test_netbox.py``).

:codeauthor: :email:`Zach Moody <zmoody@do.co>`
"""

import logging
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

import pynetbox
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


def test_redact_headers_hides_the_token_keeps_the_rest():
    headers = {
        "Authorization": f"Token {API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    redacted = netbox._redact_headers(headers)
    assert redacted["Authorization"] == "***redacted***"
    assert redacted["Content-Type"] == "application/json"
    assert redacted["Accept"] == "application/json"
    # the caller's headers are not mutated
    assert headers["Authorization"] == f"Token {API_TOKEN}"


def test_redact_headers_is_case_insensitive_and_handles_none():
    empty = netbox._redact_headers(None)
    assert isinstance(empty, dict)
    assert not empty
    redacted = netbox._redact_headers(
        {"AUTHORIZATION": f"Token {API_TOKEN}", "Cookie": "sessionid=secret"}
    )
    assert redacted["AUTHORIZATION"] == "***redacted***"
    assert redacted["Cookie"] == "***redacted***"


def test_failed_request_logs_redacted_headers(fake_netbox, caplog):
    """
    A NetBox error (here an unknown endpoint, so a 404 on create) logs the
    request headers for debugging, but the Authorization token is redacted.
    """
    with caplog.at_level(logging.DEBUG, logger=netbox.__name__):
        assert netbox._add("dcim", "no-such-endpoint", {"name": "x"}) is False
    assert [r[0] for r in fake_netbox.requests] == ["POST"]
    assert "NetBox request failed: POST" in caplog.text
    assert "404" in caplog.text
    # the headers are logged ...
    assert "headers:" in caplog.text
    assert "authorization" in caplog.text.lower()
    # ... but the token itself is not
    assert API_TOKEN not in caplog.text
    assert "***redacted***" in caplog.text


@pytest.mark.parametrize(
    "call,lookup_fails",
    [
        (lambda: netbox.update_device("minion1", serial="X"), False),
        (lambda: netbox.update_interface("minion1", "lo0", description="x"), False),
        (lambda: netbox.create_device("r1", "router", "MX480", "Juniper", "site1"), True),
    ],
)
def test_update_and_create_errors_redact_the_token(caplog, call, lookup_fails):
    response = MagicMock(status_code=400, url="http://netbox/api/dcim/devices/1/", text="bad")
    response.request.method = "PATCH"
    response.request.headers = {"Authorization": f"Token {API_TOKEN}"}
    response.request.body = b"{}"
    response.json.return_value = {"detail": "bad"}
    error = pynetbox.RequestError(response)
    record = MagicMock()
    record.save.side_effect = error
    lookup = MagicMock(side_effect=error) if lookup_fails else MagicMock(return_value={"id": 1})
    with (
        patch.object(netbox, "_get", MagicMock(return_value=record)),
        patch.object(netbox, "get_", lookup),
    ):
        with caplog.at_level(logging.DEBUG, logger=netbox.__name__):
            assert call() is False
    assert "NetBox request failed" in caplog.text
    assert "***redacted***" in caplog.text
    assert API_TOKEN not in caplog.text


@pytest.fixture(autouse=True)
def _mock_config():
    config = {"url": "http://netbox.invalid", "token": "0123456789abcdef"}
    with patch.object(netbox, "_config", MagicMock(return_value=config)):
        yield config


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


@pytest.mark.parametrize(
    "attrs",
    [
        {"id": "../../users/users/1"},
        {"id": 2},
        {"url": "http://evil.example/"},
        {"endpoint": "x"},
        {"api": "x"},
        {"has_details": True},
        {"default_ret": "x"},
        {"_init_cache": []},
        {"_full_cache": []},
        {"save": "x"},
        {"delete": "x"},
        {"serial": "OK", "id": 3},
    ],
)
def test_update_device_rejects_reserved_attributes(fake_netbox, attrs):
    with pytest.raises(CommandExecutionError, match="reserved"):
        netbox.update_device("minion1", **attrs)
    assert not [r for r in fake_netbox.requests if r[0] == "PATCH"]


def test_update_device_cannot_patch_another_object(fake_netbox):
    """
    End-to-end with real pynetbox: before the fix, this sent
    PATCH /api/dcim/sites/1/.
    """
    with pytest.raises(CommandExecutionError):
        netbox.update_device("minion1", id="../../dcim/sites/1", description="pwned")
    assert not [r for r in fake_netbox.requests if r[0] == "PATCH"]


def test_update_device_regular_fields(fake_netbox):
    ret = netbox.update_device("minion1", serial="XYZ789")
    assert ret == {"dcim": {"devices": {"serial": "XYZ789"}}}
    method, path, _, body = fake_netbox.requests[-1]
    assert (method, path) == ("PATCH", "/api/dcim/devices/1/")
    assert body == {"serial": "XYZ789"}


def test_update_device_allows_related_object_fields(fake_netbox):
    """
    Fields that pynetbox models as related objects on the device class
    (device_type, primary_ip4, ...) must remain updatable.
    """
    ret = netbox.update_device("minion1", device_type=2, primary_ip4=101)
    assert ret
    method, path, _, body = fake_netbox.requests[-1]
    assert (method, path) == ("PATCH", "/api/dcim/devices/1/")
    assert body == {"device_type": 2, "primary_ip4": 101}


def test_update_device_missing_device_returns_false(fake_netbox):
    assert netbox.update_device("no-such-device", serial="X") is False
    assert not [r for r in fake_netbox.requests if r[0] == "PATCH"]


def test_update_interface_rejects_reserved_attributes(fake_netbox):
    with pytest.raises(CommandExecutionError, match="reserved"):
        netbox.update_interface("minion1", "lo0", id="../../users/tokens/1", description="x")
    assert not [r for r in fake_netbox.requests if r[0] == "PATCH"]


@pytest.mark.parametrize(
    "app,endpoint",
    [
        ("users", "tokens"),
        ("users", "users"),
        ("core", "data-sources"),
        ("extras", "config-contexts"),
        ("plugins", "anything"),
        ("secrets", "secrets"),
        ("http_session", "__dict__"),
        ("dcim", "devices/../../users/tokens"),
        ("dcim", "../users"),
        ("dcim", "api"),
        ("dcim", "name"),
        ("dcim", "config"),
        ("dcim", "models"),
        ("dcim", "_setmodel"),
        ("dcim", "Devices"),
        ("dcim", ""),
        ("dcim", None),
        (None, "devices"),
    ],
)
def test_disallowed_apps_and_endpoints(app, endpoint):
    with patch("pynetbox.api", MagicMock()) as mock:
        for call_ in (
            lambda: netbox.get_(app, endpoint, name="x"),
            lambda: netbox.get_(app, endpoint, id=1),
            lambda: netbox.filter_(app, endpoint, name="x"),
            lambda: netbox._add(app, endpoint, {"name": "x"}),
        ):
            with pytest.raises(CommandExecutionError):
                call_()
        # pynetbox.api() may have been called, but nothing was looked up on it
        assert not [c for c in mock.mock_calls if c[0] not in ("", "()")]


@pytest.mark.parametrize(
    "app,endpoint",
    [
        ("dcim", "devices"),
        ("dcim", "inventory-items"),
        ("dcim", "inventory_items"),
        ("ipam", "ip-addresses"),
        ("circuits", "circuit-terminations"),
        ("tenancy", "tenants"),
        ("virtualization", "virtual-machines"),
        ("vpn", "tunnels"),
        ("wireless", "wireless-lans"),
    ],
)
def test_allowed_apps_and_endpoints(app, endpoint):
    with patch("pynetbox.api", MagicMock()) as mock:
        netbox.filter_(app, endpoint, name="x")
        assert mock.mock_calls[1] == getattr(getattr(call(), app), endpoint).filter(name="x")


def test_allowed_apps_can_be_configured(_mock_config):
    _mock_config["allowed_apps"] = ["extras"]
    with patch("pynetbox.api", MagicMock()) as mock:
        netbox.filter_("extras", "tags")
        assert mock.mock_calls[1] == call().extras.tags.filter()
        with pytest.raises(CommandExecutionError):
            netbox.filter_("dcim", "devices")


def test_allowed_apps_must_be_a_list(_mock_config):
    _mock_config["allowed_apps"] = {"dcim": True}
    with pytest.raises(CommandExecutionError, match="allowed_apps"):
        netbox.filter_("dcim", "devices")


def test_endpoint_traversal_does_not_reach_another_path(fake_netbox):
    """
    End-to-end with real pynetbox: before the fix, this fetched
    /api/users/tokens/5/.
    """
    with pytest.raises(CommandExecutionError):
        netbox.get_("dcim", "devices/../../users/tokens", id=5)
    assert not fake_netbox.requests


@pytest.mark.parametrize(
    "func",
    [
        lambda: netbox.get_("dcim", "devices", name="minion1"),
        lambda: netbox.filter_("dcim", "devices", site="site1"),
        lambda: netbox.update_device("minion1", serial="X"),
        lambda: netbox.delete_ipaddress(1),
    ],
)
def test_reads_and_writes_build_the_same_client(_mock_config, func):
    """
    Every call builds the pynetbox client from just the URL and token;
    there is no separate "authenticated" client any more.
    """
    with patch("pynetbox.api", MagicMock()) as mock:
        func()
    assert mock.call_args_list
    for client_call in mock.call_args_list:
        assert client_call.args == (_mock_config["url"],)
        assert client_call.kwargs == {"token": _mock_config["token"]}
