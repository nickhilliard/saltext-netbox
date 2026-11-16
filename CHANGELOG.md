The changelog format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

This project uses [Semantic Versioning](https://semver.org/) - MAJOR.MINOR.PATCH

# Changelog

## 0.1.dev4+ge46e1cde0.d20261112 (2026-11-16)

Imported from original salt-3006 code written by Zach Moody <zmoody@do.co>.


## 0.1.0 (2026-11-16)


### Changed

- The pillar now fails closed: if NetBox cannot be queried, the minion's pillar fails to render (and state runs are refused) instead of silently returning partial or empty NetBox data.
- The pillar's `proxy_return` option now defaults to `False`. It requires the netbox-napalm-plugin, and the device's platform and primary IP address must be set in NetBox.
- `netbox.create_circuit_provider` links the provider to an ASN object that must already exist in NetBox, as NetBox 4 requires a RIR for every ASN.
- `netbox.create_interface_connection` creates a cable between the two interfaces, and returns it under `cables`.
- `netbox.create_interface` takes the NetBox interface type in a new `interface_type` argument, which is required unless `lag=True`. The `form_factor` argument is no longer supported and raises an error naming `interface_type`.


### Fixed

- Fixed execution module functions that did not work with NetBox 4: `create_device`, `create_interface`, `create_interface_connection`, `make_interface_lag`, `create_ipaddress`, `create_circuit_termination`, `create_circuit_provider` and `openconfig_interfaces`. Some of them reported success while leaving NetBox unchanged or wrong.
- The pillar no longer crashes for a virtual machine without a site, or when `connected_devices` is set without `interface_ips`.
- The pillar's `interfaces: True` option returns the device's interfaces even when `interface_ips` is not set.
- `netbox.create_circuit_termination` can now add the Z side of a circuit when the A side exists.


### Added

- Initial release of saltext-netbox: the `netbox` execution module and external pillar, which were removed from Salt in 3008, as a Salt extension. Requires NetBox 4.0 or later.
- `netbox.get` and `netbox.filter` only access the NetBox apps listed in the new `netbox:allowed_apps` option (by default `circuits`, `dcim`, `ipam`, `tenancy`, `virtualization`, `vpn` and `wireless`), so callers cannot read API tokens, users or configuration through them.
- With `proxy_return` enabled, the pillar takes the NAPALM driver from the [netbox-napalm-plugin](https://github.com/netbox-community/netbox-napalm-plugin), where NetBox 4 keeps it. If the plugin is not installed, or has no driver for the device's platform, no `proxy` data is returned and an error is logged.


### Security

- The execution module no longer logs the NetBox API token when a request fails; the request headers are logged with the token redacted.
- The execution module validates object IDs, and the fields passed to update functions, before sending them to NetBox, so that crafted arguments cannot reach other API endpoints or modify unintended attributes.
