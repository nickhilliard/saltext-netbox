"""
Tests for netbox.create_circuit_provider on NetBox 4.
"""

from unittest.mock import patch

import pytest
from salt.exceptions import CommandExecutionError

from saltext.netbox.modules import netbox

pytest.importorskip("pynetbox")


@pytest.fixture
def configure_loader_modules():
    return {netbox: {}}


NAME = "Blackhole Networks Inc"
SLUG = "blackhole-networks-inc"
ASN_64512 = {"id": 7, "asn": 64512}
OTHER_NAME = "Packet Drops 4U Co."
ASN_65500 = {"id": 8, "asn": 65500}


def _lookup(provider=None, asn=True):
    """
    ``asn=True`` means ASN 64512 is in NetBox, ``asn=None`` that it is not.
    """

    def lookup(_app, endpoint, **_kwargs):
        return {"asns": ASN_64512 if asn else None, "providers": provider}[endpoint]

    return lookup


def test_new_provider_is_created_with_the_asn_object():
    with (
        patch.object(netbox, "get_", side_effect=_lookup()) as get,
        patch.object(netbox, "_add", return_value={"id": 3}) as add,
    ):
        ret = netbox.create_circuit_provider(NAME, 64512)
    get.assert_any_call("ipam", "asns", asn=64512)
    payload = {"name": NAME, "slug": SLUG, "asns": [7]}
    add.assert_called_once_with("circuits", "providers", payload)
    assert ret == {"circuits": {"providers": {3: payload}}}


def test_new_provider_without_asn():
    with (
        patch.object(netbox, "get_", side_effect=_lookup()),
        patch.object(netbox, "_add", return_value={"id": 3}) as add,
    ):
        netbox.create_circuit_provider(NAME)
    add.assert_called_once_with("circuits", "providers", {"name": NAME, "slug": SLUG})


def test_unknown_asn_is_refused():
    with (
        patch.object(netbox, "get_", side_effect=_lookup(asn=None)),
        patch.object(netbox, "_add") as add,
        patch.object(netbox.log, "error") as fake_error,
    ):
        assert netbox.create_circuit_provider(NAME, 64512) is False
    add.assert_not_called()
    assert "is not in NetBox" in fake_error.call_args.args[0]


@pytest.mark.parametrize("asn", [64512, None])
def test_existing_provider_with_that_asn_is_left_alone(asn):
    provider = {"id": 3, "name": NAME, "asns": [{"id": 7, "asn": 64512}]}
    with (
        patch.object(netbox, "get_", side_effect=_lookup(provider=provider)),
        patch.object(netbox, "_add") as add,
    ):
        assert netbox.create_circuit_provider(NAME, asn) is False
    add.assert_not_called()


@pytest.mark.parametrize("asns", [[], [ASN_65500]])
def test_existing_provider_with_other_asns_raises(asns):
    provider = {"id": 4, "name": OTHER_NAME, "asns": asns}
    with (
        patch.object(netbox, "get_", side_effect=_lookup(provider=provider)),
        patch.object(netbox, "_add") as add,
    ):
        with pytest.raises(CommandExecutionError, match="Duplicate provider"):
            netbox.create_circuit_provider(OTHER_NAME, 64512)
    add.assert_not_called()
