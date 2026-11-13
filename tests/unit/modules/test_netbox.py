"""
Tests for the netbox execution module.

Ported from Salt 3006 (``tests/unit/modules/test_netbox.py``).

:codeauthor: :email:`Zach Moody <zmoody@do.co>`
"""

from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

import pytest

from saltext.netbox.modules import netbox

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
