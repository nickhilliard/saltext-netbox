"""
A tiny, in-process fake of the NetBox REST API, good enough to exercise
``pynetbox`` (execution module) and ``salt.utils.http`` (external pillar)
end-to-end without a real NetBox instance.
"""

import copy
import json
import threading
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs
from urllib.parse import urlparse

API_TOKEN = "0123456789abcdef0123456789abcdef01234567"
API_VERSION = "4.1"

SITE = {
    "id": 1,
    "url": "{base}/dcim/sites/1/",
    "name": "Site 1",
    "slug": "site1",
    "status": {"value": "active", "label": "Active"},
    "description": "First site",
}

PLATFORM = {
    "id": 1,
    "url": "{base}/dcim/platforms/1/",
    "name": "Junos",
    "slug": "junos",
    "napalm_driver": "junos",
}

DEVICE = {
    "id": 1,
    "url": "{base}/dcim/devices/1/",
    "name": "minion1",
    "device_type": {"id": 1, "model": "MX480", "slug": "mx480"},
    "role": {"id": 1, "name": "Router", "slug": "router"},
    "site": {"id": 1, "url": "{base}/dcim/sites/1/", "name": "Site 1", "slug": "site1"},
    "platform": {"id": 1, "url": "{base}/dcim/platforms/1/", "name": "Junos", "slug": "junos"},
    "primary_ip": {"id": 100, "address": "192.0.2.10/24", "family": 4},
    "serial": "ABC123",
    "status": {"value": "active", "label": "Active"},
}

PEER_DEVICE = {
    "id": 2,
    "url": "{base}/dcim/devices/2/",
    "name": "minion2",
    "site": {"id": 1, "name": "Site 1", "slug": "site1"},
    "platform": None,
    "primary_ip": None,
}

INTERFACES = [
    {
        "id": 10,
        "url": "{base}/dcim/interfaces/10/",
        "device": {"id": 1, "name": "minion1"},
        "name": "xe-0/0/0",
        "type": {"value": "10gbase-x-sfpp", "label": "SFP+ (10GE)"},
        "enabled": True,
        "connected_endpoints": [
            {"id": 20, "name": "xe-0/0/1", "device": {"id": 2, "name": "minion2"}}
        ],
    },
    {
        "id": 11,
        "url": "{base}/dcim/interfaces/11/",
        "device": {"id": 1, "name": "minion1"},
        "name": "lo0",
        "type": {"value": "virtual", "label": "Virtual"},
        "enabled": True,
        "connected_endpoints": None,
    },
]

IP_ADDRESSES = [
    {
        "id": 100,
        "url": "{base}/ipam/ip-addresses/100/",
        "address": "192.0.2.10/24",
        "family": {"value": 4, "label": "IPv4"},
        "status": {"value": "active", "label": "Active"},
        "assigned_object_type": "dcim.interface",
        "assigned_object_id": 10,
        "assigned_object": {"id": 10, "name": "xe-0/0/0"},
    }
]

PREFIXES = [
    {
        "id": 1000,
        "url": "{base}/ipam/prefixes/1000/",
        "prefix": "192.0.2.0/24",
        "site": {"id": 1, "name": "Site 1", "slug": "site1"},
        "status": {"value": "active", "label": "Active"},
    }
]


def _render(obj, base):
    if isinstance(obj, dict):
        return {k: _render(v, base) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_render(v, base) for v in obj]
    if isinstance(obj, str):
        return obj.replace("{base}", base)
    return obj


def _matches(obj, params):
    for key, values in params.items():
        if key in ("limit", "offset", "brief"):
            continue
        value = values[0]
        if key == "name":
            if obj.get("name") != value:
                return False
        elif key in ("device_id", "site_id"):
            parent = obj.get(key[:-3]) or {}
            if str(parent.get("id")) != value:
                return False
        elif key == "id":
            if str(obj.get("id")) != value:
                return False
        else:
            # unknown filters never match, like an empty result set
            return False
    return True


class FakeNetBox:
    def __init__(self, device_name="minion1"):
        device = copy.deepcopy(DEVICE)
        device["name"] = device_name
        self.device_name = device_name
        self.devices = [device, copy.deepcopy(PEER_DEVICE)]
        self.collections = {
            "dcim/devices": self.devices,
            "dcim/sites": [copy.deepcopy(SITE)],
            "dcim/platforms": [copy.deepcopy(PLATFORM)],
            "dcim/interfaces": copy.deepcopy(INTERFACES),
            "ipam/ip-addresses": copy.deepcopy(IP_ADDRESSES),
            "ipam/prefixes": copy.deepcopy(PREFIXES),
            "dcim/manufacturers": [],
            "virtualization/virtual-machines": [],
            "virtualization/interfaces": [],
        }
        for ip in self.collections["ipam/ip-addresses"]:
            ip["device"] = {"id": 1}
        self.requests = []
        self._server = None
        self._thread = None

    @property
    def base(self):
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/api"

    def _handle(self, handler):
        url = urlparse(handler.path)
        self.requests.append((handler.command, handler.path, dict(handler.headers)))
        if handler.headers.get("Authorization") != f"Token {API_TOKEN}":
            return 403, {"detail": "Invalid token"}
        path = url.path.rstrip("/")
        if not path.startswith("/api"):
            return 404, {"detail": "Not found."}
        path = path[len("/api") :].lstrip("/")
        if path == "":
            return 200, {
                key.split("/")[0]: f"{self.base}/{key.split('/')[0]}/" for key in self.collections
            }
        if path == "status":
            return 200, {"netbox-version": API_VERSION}
        params = parse_qs(url.query)
        if path in self.collections:
            results = [o for o in self.collections[path] if _matches(o, params)]
            return 200, {"count": len(results), "next": None, "previous": None, "results": results}
        collection, _, obj_id = path.rpartition("/")
        if collection in self.collections and obj_id.isdigit():
            for obj in self.collections[collection]:
                if obj["id"] == int(obj_id):
                    return 200, obj
        return 404, {"detail": "Not found."}

    def _handle_write(self, handler):
        url = urlparse(handler.path)
        length = int(handler.headers.get("Content-Length") or 0)
        body = json.loads(handler.rfile.read(length) or b"{}")
        self.requests.append((handler.command, handler.path, dict(handler.headers), body))
        if handler.headers.get("Authorization") != f"Token {API_TOKEN}":
            return 403, {"detail": "Invalid token"}
        path = url.path.rstrip("/")[len("/api") :].lstrip("/")
        if handler.command == "POST" and path in self.collections:
            collection = self.collections[path]
            obj = dict(body)
            obj["id"] = max((o["id"] for o in collection), default=0) + 1
            obj["url"] = f"{{base}}/{path}/{obj['id']}/"
            collection.append(obj)
            return 201, obj
        collection, _, obj_id = path.rpartition("/")
        if handler.command == "PATCH" and collection in self.collections and obj_id.isdigit():
            for obj in self.collections[collection]:
                if obj["id"] == int(obj_id):
                    obj.update(body)
                    return 200, obj
        return 404, {"detail": "Not found."}

    def start(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # pylint: disable=invalid-name
                self._respond(*fake._handle(self))

            def do_POST(self):  # pylint: disable=invalid-name
                self._respond(*fake._handle_write(self))

            do_PATCH = do_POST

            def _respond(self, status, body):
                payload = json.dumps(_render(body, fake.base)).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("API-Version", API_VERSION)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):  # pylint: disable=arguments-differ
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
