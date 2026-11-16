"""
Tests for netbox.make_interface_lag on NetBox 4.
"""

from unittest.mock import patch

import pytest

from saltext.netbox.modules import netbox

pytest.importorskip("pynetbox")


@pytest.fixture
def configure_loader_modules():
    return {netbox: {}}


def test_sets_the_interface_type_to_lag():
    with patch.object(netbox, "update_interface", return_value={"ok": True}) as update:
        assert netbox.make_interface_lag("edge_router", "ae13") == {"ok": True}
    update.assert_called_once_with("edge_router", "ae13", type="lag")


def test_type_is_not_a_reserved_record_attribute():
    """
    update_interface refuses reserved pynetbox attributes; "type" must
    get through to NetBox.
    """
    assert netbox._record_updates({"type": "lag"}) == {"type": "lag"}
