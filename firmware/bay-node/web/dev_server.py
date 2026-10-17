"""Serve the bay node web page with a simulated node, to work on the UI without one.

    python firmware/bay-node/web/dev_server.py [port]      # then open http://localhost:8766

Same endpoints and JSON as src/web.c, the web console's WebSockets
(/console/ws/<n>) and access control included.  The "node" is a dict the
POSTs change; its DUT is a fake Zephyr board that boots, logs in colour and
runs a tiny shell on the console.  Test hooks:

    /dev/fault            trip a fake over-current
    /dev/attach           toggle a fake USB/IP client (192.168.1.41)
    /dev/rfc2217          toggle a fake RFC 2217 client (192.168.1.41)
    /dev/boot             a short press on BOOT: confirms a pending claim
    /dev/peer?ip=a.b.c.d  requests from this machine look like they come from
                          that address (no ip: back to the real one)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import math
import os
import random
import re
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

WEB = Path(__file__).resolve().parent
STATIC = {
    "/": (WEB / "index.html", "text/html"),
    "/xterm.mjs": (WEB / "vendor/xterm/xterm.mjs", "text/javascript"),
    "/addon-fit.mjs": (WEB / "vendor/xterm/addon-fit.mjs", "text/javascript"),
    "/xterm.css": (WEB / "vendor/xterm/xterm.css", "text/css"),
    "/xterm-LICENSE.txt": (WEB / "vendor/xterm/LICENSE.txt", "text/plain"),
}
START = time.monotonic() - 3 * 3600 - 17 * 60
WEB_SLOTS = 2
LOG_WINDOW = 16384 - 512

node = {
    "id": "b3", "hostname": "bay-b3", "ip": "192.168.1.53", "version": "4.5.0-rc2",
    "path": "usbip", "service": False, "pc_detected": False, "force_classic": False,
    "usb": {"running": True, "devices": 1, "sessions": 0},
    "dut": {"on": True, "fault": False, "latched": False, "faults": 0, "meter": True,
            "mv": 0, "ma": 0, "mw": 0},
}
aux = {"baud": 115200, "data_bits": 8, "parity": "none", "stop_bits": 1, "enter": "cr",
       "echo": False, "esptool_reset": False}


def dut_current_ma(t: float) -> int:
    """A board idling at ~90 mA with a radio burst every 8 s."""
    burst = 42 if t % 8 < 1.6 else 0
    return 90 + burst + int(6 * math.sin(t / 3)) + random.randint(-3, 3)


# --- The fake DUT console ---------------------------------------------------

class Console:
    """UART log of the fake board, shared by the WebSocket clients."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.log = bytearray()      # everything since "boot"; positions index it
        self.tx = 0
        self.boot = random.randrange(1 << 31)
        self.clients: dict[int, socket.socket] = {}
        self.info: dict[int, tuple[int, float]] = {}   # slot -> peer, since
        self.line = ""
        self.booted_at = time.monotonic()

    def emit(self, text: str) -> None:
        data = text.encode()
        with self.lock:
            self.log += data
            dead = []
            for slot, sock in self.clients.items():
                try:
                    sock.sendall(ws_frame(2, data))
                except OSError:
                    dead.append(slot)
            for slot in dead:
                self.clients.pop(slot, None)
                self.info.pop(slot, None)

    def kick(self, slot: int) -> None:
        with self.lock:
            sock = self.clients.pop(slot, None)
            self.info.pop(slot, None)
        if sock is not None:
            try:
                sock.sendall(ws_frame(8, b""))
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def broadcast_config(self) -> None:
        msg = ws_frame(1, json.dumps({"type": "config", **aux}).encode())
        with self.lock:
            for sock in list(self.clients.values()):
                try:
                    sock.sendall(msg)
                except OSError:
                    pass

    def stamp(self) -> str:
        t = time.monotonic() - self.booted_at
        return f"[{int(t // 3600):02}:{int(t // 60) % 60:02}:{t % 60:06.3f},000]"

    def boot_banner(self) -> None:
        self.booted_at = time.monotonic()
        self.emit("\r\nESP-ROM:esp32c6-20220919\r\nBuild:Sep 19 2022\r\n"
                  "rst:0x1 (POWERON),boot:0x6c (SPI_FAST_FLASH_BOOT)\r\n")
        self.emit("*** Booting Zephyr OS build v4.5.0-rc2-317-g3f7ae83e0e7c ***\r\n")
        self.emit(f"\x1b[1;32m{self.stamp()} <inf> main: blinky-ble ready on "
                  "esp32c6_devkitc/esp32c6/hpcore\x1b[0m\r\n")
        self.emit(f"{self.stamp()} <inf> bt_hci_core: HCI transport: ESP BT HCI\r\n")
        self.emit("\r\nuart:~$ ")

    def background(self) -> None:
        """Periodic log lines while the board is powered."""
        messages = [
            ("", "<inf> sensor: temp 23.{} C, rh 41 %"),
            ("", "<inf> app: advertising, 0 connections"),
            ("\x1b[1;33m", "<wrn> wifi: beacon timeout, rssi -71 dBm"),
            ("", "<dbg> ble: conn param update 30 ms"),
            ("\x1b[1;31m", "<err> i2c: transfer failed: -5 (addr 0x44)"),
        ]
        n = 0
        while True:
            time.sleep(3)
            if not node["dut"]["on"]:
                continue
            color, text = messages[n % len(messages)]
            n += 1
            reset = "\x1b[0m" if color else ""
            self.emit(f"\r\x1b[K{color}{self.stamp()} {text.format(n % 10)}{reset}\r\n"
                      f"uart:~$ {self.line}")

    def type(self, data: bytes) -> None:
        """Bytes from a web console: the fake shell echoes and runs commands."""
        self.tx += len(data)
        if not node["dut"]["on"]:
            return
        for ch in data.decode(errors="replace"):
            if ch in "\r\n":
                cmd, self.line = self.line.strip(), ""
                self.emit("\r\n" + self.run(cmd) + "uart:~$ ")
            elif ch in "\x7f\b":
                if self.line:
                    self.line = self.line[:-1]
                    self.emit("\b \b")
            elif ch == "\x03":
                self.line = ""
                self.emit("^C\r\nuart:~$ ")
            elif ch.isprintable():
                self.line += ch
                self.emit(ch)

    def run(self, cmd: str) -> str:
        if not cmd:
            return ""
        if cmd == "help":
            return ("Available commands:\r\n  help    kernel  led     reboot  sensor\r\n")
        if cmd == "kernel uptime":
            return f"Uptime: {int((time.monotonic() - self.booted_at) * 1000)} ms\r\n"
        if cmd.startswith("led"):
            return "\x1b[32mled0 on\x1b[0m\r\n"
        if cmd == "sensor get":
            return "temp: 23.4 C\r\nrh:   41.0 %\r\nunicode: µA ✓ 日本\r\n"
        if cmd == "reboot":
            threading.Timer(0.2, self.boot_banner).start()
            return ""
        return f"{cmd.split()[0]}: command not found\r\n"


console = Console()


# --- Access control (src/access.c, src/acl.c), simulated ----------------------

SERVICES = ["status", "control", "console", "usbip", "shell"]
ALL = (1 << len(SERVICES)) - 1
LEASED = 0b01110        # control, console, usbip
LEASE_DEFAULT_S = 3600
CLAIM_S = 60
KICK_S = 60


def bit(name: str) -> int:
    return 1 << SERVICES.index(name)


def mask_names(mask: int) -> list[str]:
    return ["all"] if mask == ALL else [n for i, n in enumerate(SERVICES) if mask & (1 << i)]


def names_mask(names) -> int | None:
    if not isinstance(names, list):
        return None
    mask = 0
    for n in names:
        if n == "all":
            mask |= ALL
        elif n in SERVICES:
            mask |= bit(n)
        else:
            return None
    return mask


def ip_int(text: str) -> int:
    try:
        return int(ipaddress.IPv4Address(text))
    except ValueError:
        return 0


def ip_str(value: int) -> str:
    return str(ipaddress.IPv4Address(value))


NAME_RE = re.compile(r"[A-Za-z0-9._-]{1,15}$")
CIDR_RE = re.compile(r"(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?$")


def clean_note(note: str) -> str:
    return "".join(c if c.isascii() and (c.isalnum() or c in " ._:#/+-") else "_" for c in note)[:39]


class Access:
    """The node's rules, lease, kicks, refusal log, admin key and claim."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.enabled = False
        self.everyone = bit("status")
        self.sources: list[dict] = []      # name, addr, prefix, allow
        self.lease: dict | None = None     # holder, until, note
        self.blocks: dict[int, tuple[int, float]] = {}
        self.log: list[dict] = []
        self.refused_total = 0
        self.key: bytes | None = None
        self.nonces: dict[str, float] = {}
        self.claim: dict | None = None
        self.tickets: dict[str, tuple[int, float]] = {}
        self.fake: list[dict] = []         # USB/IP, RFC 2217 clients the simulation makes up

    # Rules -------------------------------------------------------------

    def rights(self, ip: int) -> int:
        if not self.enabled:
            return ALL
        mask = self.everyone
        for s in self.sources:
            net = ipaddress.IPv4Network((s["addr"], s["prefix"]))
            if ip and ipaddress.IPv4Address(ip) in net:
                mask |= s["allow"]
        return mask

    def source_of(self, ip: int) -> str:
        best = None
        for s in self.sources:
            if ip and ipaddress.IPv4Address(ip) in ipaddress.IPv4Network((s["addr"], s["prefix"])):
                if best is None or s["prefix"] > best["prefix"]:
                    best = s
        return best["name"] if best else ""

    def lease_active(self) -> bool:
        return self.lease is not None and time.monotonic() < self.lease["until"]

    def verdict(self, svc: str, ip: int) -> str:
        mask, until = self.blocks.get(ip, (0, 0))
        if mask & bit(svc) and time.monotonic() < until:
            return "kicked"
        if bit(svc) & LEASED and self.lease_active() and ip != self.lease["holder"]:
            return "reserved"
        return "ok" if self.rights(ip) & bit(svc) else "not_allowed"

    def check(self, svc: str, ip: int) -> str:
        with self.lock:
            v = self.verdict(svc, ip)
            if v != "ok":
                self.refused_total += 1
                now = time.monotonic()
                for e in self.log:
                    if (e["ip"], e["service"], e["reason"]) == (ip, svc, v):
                        e["count"] += 1
                        e["last"] = now
                        break
                else:
                    self.log.append({"ip": ip, "service": svc, "reason": v, "count": 1,
                                     "first": now, "last": now})
                    if len(self.log) > 16:
                        self.log.remove(min(self.log, key=lambda e: e["last"]))
            return v

    def allowed(self, ip: int) -> int:
        with self.lock:
            return sum(1 << i for i, s in enumerate(SERVICES) if self.verdict(s, ip) == "ok")

    def set_rules(self, body: dict) -> str | None:
        with self.lock:
            enabled, everyone, sources = self.enabled, self.everyone, list(self.sources)
            if "enabled" in body:
                enabled = bool(body["enabled"])
            if "everyone" in body:
                everyone = names_mask(body["everyone"])
                if everyone is None:
                    return "everyone: services are status, control, console, usbip, shell or all"
            if "sources" in body:
                if not isinstance(body["sources"], list) or len(body["sources"]) > 8:
                    return "bad JSON (at most 8 sources)"
                sources = []
                for s in body["sources"]:
                    if not isinstance(s.get("name"), str) or not NAME_RE.match(s["name"]):
                        return "source name: 1-15 letters, digits, '.', '_' or '-'"
                    try:
                        if not CIDR_RE.match(s.get("cidr", "")):
                            raise ValueError
                        net = ipaddress.IPv4Network(s["cidr"], strict=False)
                    except (ValueError, TypeError):
                        return "source cidr: a.b.c.d or a.b.c.d/n"
                    allow = names_mask(s.get("allow"))
                    if allow is None:
                        return "source allow: status, control, console, usbip, shell, all"
                    sources.append({"name": s["name"], "addr": int(net.network_address),
                                    "prefix": net.prefixlen, "allow": allow})
            self.enabled, self.everyone, self.sources = enabled, everyone, sources
        self.enforce()
        return None

    # Lease -------------------------------------------------------------

    def take(self, ip: int, ttl: int, note: str) -> str | None:
        if not 10 <= ttl <= 86400:
            return "ttl_s must be 10..86400"
        with self.lock:
            renew = self.lease_active() and self.lease["holder"] == ip
            self.lease = {"holder": ip, "until": time.monotonic() + ttl, "note": clean_note(note)}
        if not renew:
            self.enforce()
        return None

    # Admin key ---------------------------------------------------------

    def nonce(self) -> str:
        n = os.urandom(8).hex()
        with self.lock:
            now = time.monotonic()
            self.nonces = {k: t for k, t in self.nonces.items() if t > now}
            self.nonces[n] = now + 60
        return n

    def admin(self, auth: str, method: str, path: str, body: bytes) -> bool:
        if self.key is None or len(auth) != 81 or auth[16] != ":":
            return False
        nonce, mac = auth[:16], auth[17:]
        with self.lock:
            if self.nonces.pop(nonce, 0) <= time.monotonic():
                return False
        want = hmac.new(self.key, f"{nonce}\n{method}\n{path}\n".encode() + body, hashlib.sha256)
        return hmac.compare_digest(want.hexdigest(), mac.lower())

    def press_boot(self) -> bool:
        """A short press on BOOT (or "bay access claim" on the local shell)."""
        with self.lock:
            c = self.claim
            if c is None or c["done"] or time.monotonic() >= c["until"]:
                return False
            self.key = c["key"] or os.urandom(32)
            c.update(done=True, key=self.key, until=time.monotonic() + CLAIM_S)
            return True

    # Connections -------------------------------------------------------

    def connections(self) -> list[dict]:
        out = []
        with console.lock:
            for slot, (ip, since) in console.info.items():
                out.append({"id": f"web{slot}", "service": "console", "label": "web console",
                            "peer": ip, "port": 0, "since": since})
        return out + [dict(c) for c in self.fake]

    def close(self, conn: dict) -> None:
        if conn["id"].startswith("web"):
            console.kick(int(conn["id"][3:]))
        else:
            self.fake = [c for c in self.fake if c["id"] != conn["id"]]
            node["usb"]["sessions"] = sum(c["service"] == "usbip" for c in self.fake)

    def kick(self, cid: str) -> bool:
        for c in self.connections():
            if c["id"] == cid:
                with self.lock:
                    mask, until = self.blocks.get(c["peer"], (0, 0))
                    if until < time.monotonic():
                        mask = 0
                    self.blocks[c["peer"]] = (mask | bit(c["service"]), time.monotonic() + KICK_S)
                self.close(c)
                return True
        return False

    def enforce(self) -> None:
        """After a rules change or a new lease: close what is no longer allowed."""
        for c in self.connections():
            with self.lock:
                v = self.verdict(c["service"], c["peer"])
            if v != "ok":
                self.close(c)

    # Documents ---------------------------------------------------------

    def summary(self, ip: int) -> dict:
        """The "access" object of /api/status."""
        with self.lock:
            lease = {"holder": "", "note": "", "remaining_s": 0, "yours": False}
            if self.lease_active():
                lease = {"holder": ip_str(self.lease["holder"]), "note": self.lease["note"],
                         "remaining_s": math.ceil(self.lease["until"] - time.monotonic()),
                         "yours": self.lease["holder"] == ip}
            allow = self.allowed(ip)
            return {"enabled": self.enabled, "claimed": self.key is not None, "you": ip_str(ip),
                    "allow": [n for i, n in enumerate(SERVICES) if allow & (1 << i)],
                    "refused": self.refused_total, "lease": lease}

    def doc(self, ip: int, admin: bool) -> dict:
        now = time.monotonic()
        with self.lock:
            d = {"enabled": self.enabled, "claimed": self.key is not None, "admin": admin,
                 "you": ip_str(ip), "source": self.source_of(ip), "allow": mask_names(self.allowed(ip)),
                 "lease": None, "connections": [], "refused_total": self.refused_total,
                 "claim": "pending" if self.claim and not self.claim["done"] and now < self.claim["until"] else "none"}
            if self.lease_active():
                d["lease"] = {"holder": ip_str(self.lease["holder"]), "note": self.lease["note"],
                              "remaining_s": math.ceil(self.lease["until"] - now),
                              "yours": self.lease["holder"] == ip}
        for c in self.connections():
            d["connections"].append({"id": c["id"], "service": c["service"], "label": c["label"],
                                     "peer": ip_str(c["peer"]), "port": c["port"],
                                     "since_s": int(now - c["since"])})
        if admin:
            with self.lock:
                d["rules"] = {"everyone": mask_names(self.everyone), "sources": [
                    {"name": s["name"], "cidr": str(ipaddress.IPv4Network((s["addr"], s["prefix"]))).removesuffix("/32"),
                     "allow": mask_names(s["allow"])} for s in self.sources]}
                d["refused"] = [{"ip": ip_str(e["ip"]), "service": e["service"], "reason": e["reason"],
                                 "count": e["count"], "first_s": int(now - e["first"]),
                                 "last_s": int(now - e["last"])}
                                for e in sorted(self.log, key=lambda e: -e["last"])]
        return d


access = Access()


def ws_frame(opcode: int, payload: bytes) -> bytes:
    n = len(payload)
    head = bytes([0x80 | opcode])
    if n < 126:
        head += bytes([n])
    elif n < 1 << 16:
        head += bytes([126]) + n.to_bytes(2, "big")
    else:
        head += bytes([127]) + n.to_bytes(8, "big")
    return head + payload


def ws_read(rfile) -> tuple[int, bytes] | None:
    head = rfile.read(2)
    if len(head) < 2:
        return None
    opcode, n = head[0] & 0x0F, head[1] & 0x7F
    if n == 126:
        n = int.from_bytes(rfile.read(2), "big")
    elif n == 127:
        n = int.from_bytes(rfile.read(8), "big")
    mask = rfile.read(4) if head[1] & 0x80 else b"\0\0\0\0"
    data = bytearray(rfile.read(n))
    for i in range(len(data)):
        data[i] ^= mask[i % 4]
    return opcode, bytes(data)


def status(ip: int = 0) -> dict:
    dut = node["dut"]
    ma = dut_current_ma(time.monotonic()) if dut["on"] else 0
    mv = (5080 - ma // 10) if dut["on"] else 0
    dut.update(ma=ma, mv=mv, mw=ma * mv // 1000)
    node["path"] = "classic" if node["force_classic"] else "usbip"
    fmt = f"{aux['data_bits']}{aux['parity'][0].upper()}{aux['stop_bits']}"
    return {**node, "uptime_s": int(time.monotonic() - START),
            "aux": {"baud": aux["baud"], "format": fmt, "port": 4000, "rfc2217_port": 4001,
                    "web_clients": len(console.clients),
                    "rfc2217": any(c["id"] == "rfc2217" for c in access.fake), "raw": False,
                    "rx": len(console.log), "tx": console.tx, "dropped": 0},
            "access": access.summary(ip)}


def aux_doc() -> dict:
    return {"type": "aux", **aux, "web_clients": len(console.clients), "web_slots": WEB_SLOTS,
            "rfc2217": False, "rfc2217_port": 4001, "raw": False, "raw_port": 4000,
            "rx": len(console.log), "tx": console.tx, "dropped": 0}


def metrics() -> str:
    s = status()
    dut, usb, a = s["dut"], s["usb"], s["aux"]
    rows = [
        ("bay_dut_vbus_volts", "gauge", dut["mv"] / 1000),
        ("bay_dut_current_amperes", "gauge", dut["ma"] / 1000),
        ("bay_dut_power_watts", "gauge", dut["mw"] / 1000),
        ("bay_dut_power_on", "gauge", int(dut["on"])),
        ("bay_dut_fault", "gauge", int(dut["fault"] or dut["latched"])),
        ("bay_dut_faults_total", "counter", dut["faults"]),
        ("bay_usb_devices", "gauge", usb["devices"]),
        ("bay_usbip_sessions", "gauge", usb["sessions"]),
        ("bay_aux_rx_bytes_total", "counter", a["rx"]),
        ("bay_aux_tx_bytes_total", "counter", a["tx"]),
        ("bay_access_refused_total", "counter", access.refused_total),
    ]
    out = []
    for name, kind, value in rows:
        out += [f"# TYPE {name} {kind}", f'{name}{{bay="{s["id"]}"}} {value:f}']
    return "\n".join(out) + "\n"


PEER_OVERRIDE: dict[str, str] = {}


def fake_client(cid: str, service: str, label: str, port: int) -> None:
    """Toggle a made-up client from 192.168.1.41 (the CI runner of the examples)."""
    if any(c["id"] == cid for c in access.fake):
        access.fake = [c for c in access.fake if c["id"] != cid]
    else:
        access.fake.append({"id": cid, "service": service, "label": label,
                            "peer": ip_int("192.168.1.41"), "port": port, "since": time.monotonic()})
    node["usb"]["sessions"] = sum(c["service"] == "usbip" for c in access.fake)


class Handler(BaseHTTPRequestHandler):
    def peer(self) -> int:
        real = self.client_address[0]
        return ip_int(PEER_OVERRIDE.get(real, real))

    def refused(self, svc: str) -> bool:
        """Like web.c's refused(): 403, or 423 with the holder, when the rules say no."""
        ip = self.peer()
        v = access.check(svc, ip)
        if v == "ok":
            return False
        if v == "reserved":
            lease = access.lease
            note = f" ({lease['note']})" if lease["note"] else ""
            left = math.ceil((lease["until"] - time.monotonic()) / 60)
            body = {"error": f"reserved by {ip_str(lease['holder'])}{note}, {left} min left"}
            code = 423
        else:
            body = {"error": "kicked by an admin: retry in a minute" if v == "kicked"
                    else "not allowed from this address"}
            code = 403
        self.json(code, {**body, "reason": v, "service": svc, "you": ip_str(ip)})
        return True

    def send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def json(self, code: int, obj: dict) -> None:
        self.send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self) -> None:  # noqa: N802
        url = urlsplit(self.path)
        path, query = url.path, parse_qs(url.query)
        if path in STATIC:
            file, ctype = STATIC[path]
            self.send(200, file.read_bytes(), ctype)
        elif path.startswith("/console/ws/"):
            self.websocket(int(path.rsplit("/", 1)[1]), query.get("t", [""])[0])
        elif path == "/api/status":
            if not self.refused("status"):
                self.json(200, status(self.peer()))
        elif path == "/api/aux":
            if not self.refused("status"):
                self.json(200, aux_doc())
        elif path == "/metrics":
            if not self.refused("status"):
                self.send(200, metrics().encode(), "text/plain")
        elif path == "/api/access":
            auth = self.headers.get("X-Bay-Auth", "")
            admin = bool(auth) and access.admin(auth, "GET", path, b"")
            if auth and not admin:
                self.json(403, {"error": "bad or expired admin signature"})
            elif admin or not self.refused("status"):
                self.json(200, access.doc(self.peer(), admin))
        elif path == "/api/access/nonce":
            self.json(200, {"nonce": access.nonce()})
        elif path == "/dev/fault":
            node["dut"].update(on=False, latched=True, faults=node["dut"]["faults"] + 1)
            self.json(200, status())
        elif path == "/dev/attach":
            fake_client("usbip:51234", "usbip", "USB/IP", 51234)
            self.json(200, status())
        elif path == "/dev/rfc2217":
            fake_client("rfc2217", "console", "RFC 2217", 40112)
            self.json(200, status())
        elif path == "/dev/boot":
            self.json(200, {"claimed": access.press_boot()})
        elif path == "/dev/peer":
            ip = query.get("ip", [""])[0]
            if ip:
                PEER_OVERRIDE[self.client_address[0]] = ip
            else:
                PEER_OVERRIDE.pop(self.client_address[0], None)
            self.json(200, {"you": ip_str(self.peer())})
        else:
            self.json(404, {"error": "not found"})

    def websocket(self, slot: int, ticket: str) -> None:
        # Like the node: a ticket from POST /api/console/ticket, else no upgrade
        with access.lock:
            ip, until = access.tickets.pop(ticket, (0, 0))
        if until < time.monotonic() or access.check("console", ip) != "ok":
            self.json(403, {"error": "no console ticket"})
            return
        key = self.headers.get("Sec-WebSocket-Key", "")
        accept = base64.b64encode(hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        sock = self.connection
        with console.lock:
            if slot >= WEB_SLOTS or slot in console.clients:
                return  # like the node: busy slot, closed without a hello
            start = max(0, len(console.log) - LOG_WINDOW)
            hello = {"type": "hello", "slot": slot, "boot": console.boot, "pos": start,
                     "config": {"type": "config", **aux}}
            sock.sendall(ws_frame(1, json.dumps(hello).encode()))
            if len(console.log) > start:
                sock.sendall(ws_frame(2, bytes(console.log[start:])))
            console.clients[slot] = sock
            console.info[slot] = (ip, time.monotonic())
        try:
            while (frame := ws_read(self.rfile)) is not None:
                opcode, data = frame
                if opcode == 8:
                    break
                if opcode in (1, 2):
                    console.type(data)
        except OSError:
            pass
        finally:
            with console.lock:
                if console.clients.get(slot) is sock:
                    console.clients.pop(slot, None)
                    console.info.pop(slot, None)
        self.close_connection = True

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self.json(400, {"error": "bad JSON"})
        path = urlsplit(self.path).path
        if path.startswith("/api/access/") or path in ("/api/lease", "/api/console/ticket"):
            return self.access_post(path, raw, body)
        if self.refused("console" if path in ("/api/aux", "/api/aux/break") else "control"):
            return
        dut = node["dut"]
        if self.path == "/api/power":
            action = body.get("action")
            if action not in ("on", "off", "cycle"):
                return self.json(400, {"error": "action must be on, off or cycle"})
            if action == "cycle":
                time.sleep(1)
            was_on = dut["on"]
            dut["on"] = action != "off"
            if dut["on"]:
                dut["latched"] = False
            if dut["on"] and (action == "cycle" or not was_on):
                console.boot_banner()
        elif self.path == "/api/reset":
            time.sleep(0.1)
            if dut["on"]:
                console.boot_banner()
        elif self.path == "/api/boot":
            time.sleep(0.3)
            if dut["on"]:
                console.emit("\r\nESP-ROM:esp32c6-20220919\r\nBuild:Sep 19 2022\r\n"
                             "rst:0x1 (POWERON),boot:0x4 (DOWNLOAD(USB/UART0/SDIO_FEI_FEO))\r\n"
                             "waiting for download\r\n")
        elif self.path == "/api/mode":
            if body.get("mode") not in ("usbip", "classic"):
                return self.json(400, {"error": "mode must be usbip or classic"})
            node["force_classic"] = body["mode"] == "classic"
        elif self.path == "/api/aux":
            new = {**aux, **{k: v for k, v in body.items() if k in aux}}
            if not (300 <= int(new["baud"]) <= 5_000_000 and 5 <= int(new["data_bits"]) <= 8
                    and new["parity"] in ("none", "odd", "even") and new["stop_bits"] in (1, 2)
                    and new["enter"] in ("cr", "lf", "crlf")):
                return self.json(400, {"error": "baud 300..5000000, data bits 5..8, stop bits 1 or 2"})
            aux.update(new)
            console.broadcast_config()
            return self.json(200, aux_doc())
        elif self.path == "/api/aux/break":
            if not dut["on"]:
                return self.json(400, {"error": "the DUT is powered off"})
            console.emit("\r\n\x1b[2m(break)\x1b[0m\r\nuart:~$ ")
        else:
            return self.json(404, {"error": "not found"})
        self.json(200, status(self.peer()))

    def access_post(self, path: str, raw: bytes, body: dict) -> None:
        ip = self.peer()
        auth = self.headers.get("X-Bay-Auth", "")
        admin = bool(auth) and access.admin(auth, "POST", path, raw)
        if auth and not admin:
            return self.json(403, {"error": "bad or expired admin signature"})
        if path in ("/api/access/rules", "/api/access/kick", "/api/access/key") and not admin:
            return self.json(403, {"error": "admin only: sign the request with the key"})

        if path == "/api/access/rules":
            if (err := access.set_rules(body)) is not None:
                return self.json(400, {"error": err})
        elif path == "/api/access/kick":
            if not access.kick(body.get("id", "")):
                return self.json(404, {"error": "no such connection"})
        elif path == "/api/access/key":
            try:
                access.key = bytes.fromhex(body.get("key", ""))
                assert len(access.key) == 32
            except (ValueError, AssertionError):
                return self.json(400, {"error": "key: 64 hex digits"})
            return self.json(200, {"saved": True})
        elif path == "/api/access/claim":
            return self.claim(ip, body)
        elif path == "/api/console/ticket":
            if self.refused("console"):
                return
            ticket = os.urandom(8).hex()
            with access.lock:
                access.tickets[ticket] = (ip, time.monotonic() + 10)
            return self.json(200, {"ticket": ticket})
        elif path == "/api/lease":
            if body.get("release"):
                with access.lock:
                    if access.lease_active() and not admin and access.lease["holder"] != ip:
                        return self.json(403, {"error": "only its holder or an admin may release it"})
                    access.lease = None
            else:
                if self.refused("control"):
                    return
                if (err := access.take(ip, int(body.get("ttl_s", LEASE_DEFAULT_S)), str(body.get("note", "")))):
                    return self.json(400, {"error": err})
        else:
            return self.json(404, {"error": "not found"})
        self.json(200, access.doc(ip, admin))

    def claim(self, ip: int, body: dict) -> None:
        now = time.monotonic()
        with access.lock:
            c = access.claim
            if "ticket" in body:
                if c is None or c["ticket"] != body["ticket"] or c["ip"] != ip:
                    return self.json(404, {"error": "no such claim from this address"})
                if now >= c["until"]:
                    access.claim = None
                    return self.json(404, {"error": "nobody pressed BOOT in time"})
                if not c["done"]:
                    return self.json(200, {"state": "pending", "remaining_s": math.ceil(c["until"] - now)})
                access.claim = None
                return self.json(200, {"state": "done", "key": c["key"].hex()})
            if access.key is not None:
                return self.json(409, {"error": "already claimed: unlock with the admin key, or reset the node"})
            offered = None
            if "key" in body:
                try:
                    offered = bytes.fromhex(body["key"])
                    assert len(offered) == 32
                except (ValueError, AssertionError, TypeError):
                    return self.json(400, {"error": "key: 64 hex digits"})
            access.claim = {"ticket": os.urandom(8).hex(), "ip": ip, "until": now + CLAIM_S,
                            "key": offered, "done": False}
            print(f"claim requested by {ip_str(ip)}: GET /dev/boot to press BOOT", flush=True)
            return self.json(200, {"state": "pending", "ticket": access.claim["ticket"],
                                   "remaining_s": CLAIM_S})

    def log_message(self, fmt: str, *args) -> None:
        pass


def serve(port: int = 8766) -> ThreadingHTTPServer:
    if not console.log:
        console.boot_banner()
        threading.Thread(target=console.background, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    print(f"bay node mock on http://localhost:{port}")
    serve(port).serve_forever()
