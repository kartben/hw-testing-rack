"""Serve the power hub web page with a simulated hub, to work on the UI without one.

    python firmware/power-hub/web/dev_server.py [port]      # then open http://localhost:8767

Same endpoints and JSON as src/web.c.  The "hub" is a dict the POSTs change:
a 140 W EPR charger, four rows of bay nodes on the rack bus (CAN), their
currents.  Test hooks:

    /dev/drop             the charger renegotiates down to 20 V / 1.5 A (30 W): row C shed
    /dev/restore          back to the 140 W charger
    /dev/fault?row=C      row C's eFuse trips (current limit), /dev/fault?row=C&off=1 clears it
    /dev/lose?node=0x22   a node stops sending STATUS
    /dev/usb              the controller runs from its console USB-C only (no PD charger)
    /dev/boot             a short press on BOOT: confirms a pending claim
    /dev/rollback         the next firmware update does not confirm itself (MCUboot goes back)
    /dev/image?version=0.6.0[&id=bay-node/bay_node]   an image to upload (unsigned, laid out
                          as zephyr.signed.bin; the hub's own id by default)

The page's actions are admin requests signed with the hub's key, as on the
hub (common/web/devserver.py's Admin): claim it from the page, then /dev/boot.
A firmware update takes any image laid out like zephyr.signed.bin with the
hub's image id (devserver.make_image() writes one): the hub "restarts" for a
few seconds, runs it on trial, then confirms it.
"""

from __future__ import annotations

import math
import random
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common" / "web"))
from devserver import Admin, Firmware, PageHandler, make_image  # noqa: E402

WEB = Path(__file__).resolve().parent
START = time.monotonic() - 2 * 86400 - 5 * 3600
ROWS = "ABCD"
MARGIN_PCT = 10  # CONFIG_HUB_BUDGET_MARGIN_PCT

# What a 140 W EPR charger offers, as the CH224A shows it in EPR mode: positions 1-7 SPR
# (the unused ones empty), 8 and on EPR
CHARGER_140W = [
    {"index": 1, "type": "fixed", "mv": 5000, "ma": 3000}, {"index": 2, "type": "fixed", "mv": 9000, "ma": 3000},
    {"index": 3, "type": "fixed", "mv": 15000, "ma": 3000}, {"index": 4, "type": "fixed", "mv": 20000, "ma": 5000},
    {"index": 5, "type": "pps", "mv_min": 3300, "mv": 21000, "ma": 5000},
    {"index": 8, "type": "fixed", "mv": 28000, "ma": 5000, "epr": True},
    {"index": 9, "type": "avs", "mv_min": 15000, "mv": 28000, "ma": 0, "w": 140, "epr": True},
]
# A multi-port charger sharing its power: 30 W left for the rack
CHARGER_30W = [
    {"index": 1, "type": "fixed", "mv": 5000, "ma": 3000}, {"index": 2, "type": "fixed", "mv": 9000, "ma": 3000},
    {"index": 3, "type": "fixed", "mv": 15000, "ma": 2000}, {"index": 4, "type": "fixed", "mv": 20000, "ma": 1500},
]

# Nodes: (row, position) -> hostname, base DUT current, state
NODES = {
    ("A", 1): ("bay-a1", 180, "attached"), ("A", 2): ("bay-a2", 95, "usbip"),
    ("A", 3): ("bay-a3", 420, "attached"),
    ("B", 1): ("bay-b1", 60, "classic"), ("B", 2): ("bay-b2", 0, "off"),
    ("B", 3): ("bay-b3", 140, "enumerated"),
    ("C", 1): ("bay-c1", 310, "attached"), ("C", 2): ("bay-c2", 75, "service"),
    ("C", 3): ("bay-c3", 210, "enumerated"),
}

# Bays with a camera (node ids: A1, A3, B3, C1), and the one someone is watching
CAMERAS = {0x01, 0x03, 0x13, 0x21}
CAMERAS_ACTIVE = {0x03}

hub = {
    "hostname": "rack", "ip": "192.168.1.40", "version": "0.5.0",
    "charger": CHARGER_140W, "pref": "epr", "usb_only": False,
    "rows": {r: {"on": r != "D", "fault": False, "faults": int(r == "B"), "shed": False, "cycling": 0.0} for r in ROWS},
    "lost": set(),
    "sheds": 0,
    "enumerated_at": time.monotonic() - 754,
    "can": {"tx": 1520331, "rx": 4870112, "errors": 0, "bus_off": 0},
}
events: list[tuple[float, str, str]] = []
admin = Admin()
firmware = Firmware("0.5.0", "power-hub/power_hub", on_event=lambda text: event("firmware", text))
lock = threading.Lock()


def event(kind: str, text: str) -> None:
    events.append((time.time(), kind, text))
    del events[:-50]


def node_id(row: str, pos: int) -> int:
    return ROWS.index(row) * 16 + pos


def contract() -> dict | None:
    if hub["usb_only"]:
        return None
    pdos = hub["charger"]
    epr = [p for p in pdos if p["type"] == "fixed" and p.get("epr") and p["mv"] == 28000]
    if epr and hub["pref"] == "epr":
        return {"mv": 28000, "ma": epr[0]["ma"], "epr": True, "pdo": epr[0]["index"]}
    best = [p for p in pdos if p["type"] == "fixed" and p["mv"] == 20000]
    return {"mv": 20000, "ma": best[0]["ma"], "epr": False, "pdo": best[0]["index"]}


def pdo_list(c: dict | None) -> list[dict]:
    out = []
    for p in hub["charger"]:
        q = dict(p)
        if c and p["index"] == c["pdo"]:
            q["selected"] = True
        elif p["mv"] > 28000:
            q["refused"] = "above 28 V"
        out.append(q)
    return out


def nodes_of(row: str, t: float) -> list[dict]:
    r = hub["rows"][row]
    if not r["on"] or r["shed"]:
        return []
    out = []
    for (rr, pos), (name, base, state) in sorted(NODES.items()):
        if rr != row:
            continue
        nid = node_id(row, pos)
        lost = nid in hub["lost"]
        wobble = 1 + 0.08 * math.sin(t / 7 + nid) + random.uniform(-0.02, 0.02)
        ma = 0 if state == "off" else int(base * wobble)
        out.append({"id": nid, "pos": f"{row}{pos}", "name": "", "ip": f"192.168.1.{60 + nid}",
                    "mac": f"34:b7:da:56:{nid:02x}:{len(name):02x}",
                    "state": "lost" if lost else state,
                    "camera": "active" if nid in CAMERAS_ACTIVE else "ready" if nid in CAMERAS else "none",
                    "dut_ma": ma, "dut_mv": 5060 - ma // 12 if ma else 0,
                    "seen_s": 9.0 if lost else round(random.uniform(0.1, 0.9), 1), "version": "0.5.0"})
        if lost:   # the row stops at a lost node: the ones after it can't get POS
            break
    return out


def row_current(row: str, nodes: list[dict]) -> int:
    """Row current at VRACK: each node ≈ 0.85 W plus its DUT's 5 V, through an ≈ 88 % buck."""
    c = contract()
    if not nodes or not c:
        return 0
    mw = sum(850 + n["dut_ma"] * 5.06 / 0.88 for n in nodes)
    return int(mw / c["mv"] * 1000)


def status() -> dict:
    t = time.monotonic()
    c = contract()
    rows, total_ma = [], 0
    for row in ROWS:
        r = hub["rows"][row]
        nodes = nodes_of(row, t)
        ma = row_current(row, nodes)
        total_ma += ma
        state = ("fault" if r["fault"] else "shed" if r["shed"] else
                 "cycling" if r["cycling"] > t else "on" if r["on"] else "off")
        rows.append({"name": row, "state": state, "on": r["on"] and not r["shed"], "fault": r["fault"],
                     "wanted": r["on"], "faults": r["faults"],
                     "ma": ma, "mw": ma * (c["mv"] if c else 0) // 1000, "nodes": nodes})
    vbus = (c["mv"] - total_ma * 12 // 1000) if c else 0
    found = sum(len(r["nodes"]) for r in rows)
    return {
        "hostname": hub["hostname"], "ip": hub["ip"], "version": firmware.version,
        "access": {"claimed": admin.key is not None, "claim_pending": admin.claim_pending()},
        "uptime_s": int(t - START),
        "pd": {
            "state": "usb" if not c else "epr" if c["epr"] else "spr",
            "contract": c, "pref": hub["pref"], "final": c is not None,
            # The CH224A measures nothing: VBUS from the ADC, the current from the rows' IMON
            "vbus_mv": vbus, "rows_ma": total_ma, "asked_mv": c["mv"] if c else 0,
            "granted_ma": c["ma"] if c else 0, "pg": c is not None, "epr_refused": False,
            "pdos": pdo_list(c),
            "max_mw": max((p.get("w", 0) * 1000 or p["mv"] * p["ma"] // 1000 for p in hub["charger"]), default=0),
        },
        "rows": rows,
        "budget": budget_doc(c, rows, total_ma),
        "can": {"state": "error-active", "bitrate": 250000, "nodes": found, "lost": len(hub["lost"]),
                "rx_fps": found + found // 10, "errors": hub["can"]["errors"], "bus_off": hub["can"]["bus_off"],
                "enumerating": False, "enumerated_s": round(t - hub["enumerated_at"]),
                "enumerations": 3},
        "firmware": firmware.doc(),
    }


def budget_doc(c: dict | None, rows: list[dict], total_ma: int) -> dict:
    """src/rows.c's budget: the contract's current less a 10 % margin."""
    limit_ma = c["ma"] * (100 - MARGIN_PCT) // 100 if c else 0
    return {"contract_mw": c["mv"] * c["ma"] // 1000 if c else 0,
            "used_mw": sum(r["mw"] for r in rows),
            "limit_mw": limit_ma * c["mv"] // 1000 if c else 0, "limit_ma": limit_ma,
            "total_ma": total_ma, "margin_pct": MARGIN_PCT, "cap_mw": 0,
            "shed": "".join(r["name"] for r in rows if r["state"] == "shed"),
            "sheds": hub["sheds"], "shed_order": "DCBA"}


def events_doc() -> list[dict]:
    now = time.time()
    return [{"age_s": int(now - ts), "kind": k, "text": x} for ts, k, x in reversed(events)]


def enumerate_rack(why: str) -> None:
    hub["enumerated_at"] = time.monotonic()
    found = sum(len(nodes_of(r, time.monotonic())) for r in ROWS)
    event("can", f"enumeration ({why}): {found} nodes")


def cycle(row: str, ms: int) -> None:
    r = hub["rows"][row]
    r["cycling"] = time.monotonic() + ms / 1000 + 2.5
    event("row", f"row {row} power cycle ({ms} ms off)")
    def back() -> None:
        time.sleep(ms / 1000 + 2.5)
        with lock:
            enumerate_rack(f"row {row} back on")
    threading.Thread(target=back, daemon=True).start()


class Handler(PageHandler):
    STATIC = {"/": (WEB / "index.html", "text/html")}

    def do_GET(self) -> None:  # noqa: N802
        url = urlsplit(self.path)
        path, q = url.path, {k: v[0] for k, v in parse_qs(url.query).items()}
        if self.static(path):
            return
        with lock:
            if firmware.down() and not path.startswith("/dev/"):
                self.json(503, {"error": "restarting"})
            elif path == "/api/status":
                self.json(200, status())
            elif path == "/api/events":
                self.json(200, events_doc())
            elif path == "/dev/drop":
                hub["charger"] = CHARGER_30W
                hub["rows"]["C"]["shed"] = hub["rows"]["C"]["on"]
                hub["sheds"] += 1
                event("pd", "contract: 20.0 V / 1.50 A (30 W)")
                event("row", "row C shed: 1.52 A > 1.35 A budget")
                self.json(200, status())
            elif path == "/dev/restore":
                hub["charger"] = CHARGER_140W
                for r in hub["rows"].values():
                    r["shed"] = False
                event("pd", "contract: 28.0 V / 5.00 A EPR (140 W)")
                event("row", "row C back: the budget has room for it again")
                enumerate_rack("rows back")
                self.json(200, status())
            elif path == "/dev/fault":
                row = q.get("row", "C").upper()
                hub["rows"][row]["fault"] = not q.get("off")
                if hub["rows"][row]["fault"]:
                    hub["rows"][row]["faults"] += 1
                    event("fault", f"row {row}: eFuse in current limit (1.6 A)")
                self.json(200, status())
            elif path == "/dev/lose":
                nid = int(q.get("node", "0x22"), 0)
                hub["lost"] ^= {nid}
                if nid in hub["lost"]:
                    event("can", f"node {ROWS[nid >> 4]}{nid & 15} (0x{nid:02x}) lost: no STATUS for 3.5 s")
                self.json(200, status())
            elif path == "/dev/usb":
                hub["usb_only"] = not hub["usb_only"]
                self.json(200, status())
            elif path == "/api/access/nonce":
                self.json(200, {"nonce": admin.nonce()})
            elif path == "/dev/boot":
                self.json(200, {"claimed": admin.press_boot()})
            elif path == "/api/update":
                self.json(200, firmware.doc())
            elif path == "/dev/rollback":
                firmware.rollback()
                self.json(200, {"rollback": True})
            elif path == "/dev/image":
                self.send(200, make_image(q.get("version", "0.6.0"), q.get("id", firmware.image_id)),
                          "application/octet-stream")
            else:
                self.json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        import json
        url = urlsplit(self.path)
        path = url.path
        raw = self.body()
        if firmware.down():
            self.json(503, {"error": "restarting"})
            return
        if path == "/api/update":
            with lock:
                ticket = parse_qs(url.query).get("ticket", [""])[0]
                self.json(*firmware.upload(self.client_address[0], ticket, raw))
            return
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            self.json(400, {"error": "bad JSON"})
            return
        with lock:
            if path == "/api/access/claim":
                self.json(*admin.claim(self.client_address[0], body))
                return
            if not admin.check(self.headers.get("X-Bay-Auth", ""), "POST", path, raw):
                self.json(403, {"error": "admin only: unlock with the hub's admin key" if admin.key
                                else "admin only: claim the hub first (its BOOT button)"})
                return
            if path == "/api/access/check":
                self.json(200, status())
            elif path == "/api/row":
                row, action = str(body.get("row", "")).upper(), body.get("action")
                if row not in ROWS or action not in ("on", "off", "cycle"):
                    self.json(400, {"error": "row A-D, action on|off|cycle"})
                    return
                r = hub["rows"][row]
                if action == "cycle":
                    cycle(row, int(body.get("ms", 1000)))
                else:
                    r["on"], r["fault"] = action == "on", False
                    event("row", f"row {row} {action}")
                    if r["on"]:
                        enumerate_rack(f"row {row} on")
                self.json(200, status())
            elif path == "/api/pd":
                if body.get("pref") not in ("epr", "20v"):
                    self.json(400, {"error": "pref must be epr or 20v"})
                    return
                hub["pref"] = body["pref"]
                c = contract()
                event("pd", f"contract: {c['mv'] // 1000} V / {c['ma'] / 1000:g} A" + (" EPR" if c["epr"] else ""))
                self.json(200, status())
            elif path == "/api/enumerate":
                enumerate_rack("requested")
                self.json(200, status())
            elif path == "/api/update/begin":
                self.json(*firmware.begin(self.client_address[0], body))
            elif path == "/api/node":
                nid, action = int(body.get("id", 0)), body.get("action")
                if action not in ("identify", "reset", "bootloader", "power-cycle", "power-on", "power-off", "reboot"):
                    self.json(400, {"error": "action identify|reset|bootloader|power-*|reboot"})
                    return
                key = (ROWS[nid >> 4], nid & 15) if (nid >> 4) < len(ROWS) else None
                if key in NODES and action in ("power-on", "power-off"):
                    name, base, st = NODES[key]
                    NODES[key] = (name, base or 110, "enumerated" if action == "power-on" else "off")
                event("node", f"node 0x{nid:02x}: {action}")
                self.json(200, status())
            else:
                self.json(404, {"error": "not found"})


def serve(port: int = 8767) -> ThreadingHTTPServer:
    if not events:
        now = time.time()
        # Power-up with the CH224A: it asks for 9 V by itself (CFG1), the rows wait
        # (their eFuses lock out below 15 V), then pd.c asks for 28 V EPR (20 V
        # without it); the texts are pd.c's
        for dt, kind, text in ((-2 * 86400 - 5 * 3600, "pd", "VBUS 9.0 V: PD sink up"),
                               (-2 * 86400 - 5 * 3600 + 1, "pd",
                                "contract: 9 V / 3.00 A (27 W), too low for the rows"),
                               (-2 * 86400 - 5 * 3600 + 3, "pd", "contract: 28 V / 5.00 A EPR (140 W)"),
                               (-2 * 86400 - 5 * 3600 + 3, "row", "rows A, B, C on (staggered, 300 ms)"),
                               (-3 * 3600, "fault", "row B: eFuse in current limit for 40 ms"),
                               (-754, "can", "enumeration (node 0x21 rebooted): 9 nodes")):
            events.append((now + dt, kind, text))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8767
    print(f"power hub mock on http://localhost:{port}")
    serve(port).serve_forever()
