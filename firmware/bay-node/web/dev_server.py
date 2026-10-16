"""Serve the bay node web page with a simulated API, to work on the UI without a node.

    python firmware/bay-node/web/dev_server.py [port]      # then open http://localhost:8766

Same endpoints and JSON as src/web.c; the "node" is a dict that the POSTs change.
"""

from __future__ import annotations

import json
import random
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGE = Path(__file__).with_name("index.html")
START = time.monotonic() - 3 * 3600 - 17 * 60

node = {
    "id": "b3", "hostname": "bay-b3", "ip": "192.168.1.53", "version": "4.5.0-rc2",
    "path": "usbip", "service": False, "pc_detected": False, "force_classic": False,
    "usb": {"running": True, "devices": 1, "sessions": 0},
    "dut": {"on": True, "fault": False, "latched": False, "faults": 0, "meter": True,
            "mv": 0, "ma": 0, "mw": 0},
    "aux": {"baud": 115200, "port": 4000, "client": False, "rx": 18234, "tx": 312, "dropped": 0},
}


def status() -> dict:
    dut = node["dut"]
    ma = (95 + random.randint(-6, 30)) if dut["on"] else 0
    mv = (5080 - ma // 10) if dut["on"] else 0
    dut.update(ma=ma, mv=mv, mw=ma * mv // 1000)
    if node["force_classic"]:
        node["path"] = "classic"
    else:
        node["path"] = "usbip"
    return {**node, "uptime_s": int(time.monotonic() - START)}


def metrics() -> str:
    s = status()
    dut, usb, aux = s["dut"], s["usb"], s["aux"]
    rows = [
        ("bay_dut_vbus_volts", "gauge", dut["mv"] / 1000),
        ("bay_dut_current_amperes", "gauge", dut["ma"] / 1000),
        ("bay_dut_power_watts", "gauge", dut["mw"] / 1000),
        ("bay_dut_power_on", "gauge", int(dut["on"])),
        ("bay_dut_fault", "gauge", int(dut["fault"] or dut["latched"])),
        ("bay_dut_faults_total", "counter", dut["faults"]),
        ("bay_usb_devices", "gauge", usb["devices"]),
        ("bay_usbip_sessions", "gauge", usb["sessions"]),
        ("bay_aux_rx_bytes_total", "counter", aux["rx"]),
        ("bay_aux_tx_bytes_total", "counter", aux["tx"]),
    ]
    out = []
    for name, kind, value in rows:
        out += [f"# TYPE {name} {kind}", f'{name}{{bay="{s["id"]}"}} {value:f}']
    return "\n".join(out) + "\n"


class Handler(BaseHTTPRequestHandler):
    def send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def json(self, code: int, obj: dict) -> None:
        self.send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send(200, PAGE.read_bytes(), "text/html")
        elif self.path == "/api/status":
            self.json(200, status())
        elif self.path == "/metrics":
            self.send(200, metrics().encode(), "text/plain")
        elif self.path == "/dev/fault":
            # Simulate an over-current trip, to look at the fault state
            node["dut"].update(on=False, latched=True, faults=node["dut"]["faults"] + 1)
            self.json(200, status())
        else:
            self.json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self.json(400, {"error": "bad JSON"})
        dut = node["dut"]
        if self.path == "/api/power":
            action = body.get("action")
            if action not in ("on", "off", "cycle"):
                return self.json(400, {"error": "action must be on, off or cycle"})
            if action == "cycle":
                time.sleep(1)
            dut["on"] = action != "off"
            if dut["on"]:
                dut["latched"] = False
        elif self.path in ("/api/reset", "/api/boot"):
            time.sleep(0.2)
        elif self.path == "/api/mode":
            if body.get("mode") not in ("usbip", "classic"):
                return self.json(400, {"error": "mode must be usbip or classic"})
            node["force_classic"] = body["mode"] == "classic"
        else:
            return self.json(404, {"error": "not found"})
        self.json(200, status())

    def log_message(self, fmt: str, *args) -> None:
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    print(f"bay node mock on http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
