"""Serve the bay node web page with a simulated node, to work on the UI without one.

    python firmware/bay-node/web/dev_server.py [port] [--ports 4]    # then open http://localhost:8766

Same endpoints and JSON as src/web.c, the web console's WebSockets
(/console/ws/<n>) and access control included, and the camera's port
(src/camera.c) on the next port: /snapshot.jpg and /stream.mjpg, B2's camera
as the viewer (site/) renders it, the GIGA's screen playing, the light on or
off (frames in camera/, grabbed by grab_camera.py; Pillow brings them to the
other resolutions and applies the image settings, without it they go as
grabbed).  The "node" is a dict the
POSTs change; its DUT is a fake Zephyr board that boots, logs in colour and
runs a tiny shell on the console.  With --ports 4 it is a bay with a DATA ×4
board (docs/multi-dut-node.md): four boards, sub-slots B3.1 to B3.4, served by
/api/ports and /api/ports/<n>/{power,reset,boot}, leased one by one.  Test hooks:

    /dev/fault[?port=n]   trip a fake over-current (the DUT, or port n)
    /dev/draw?port=n&ma=900   port n's board draws this much (ma=0: its usual), for the admission rule
    /dev/attach[?port=n]  toggle a fake USB/IP client (192.168.1.41; on port n's board)
    /dev/rfc2217          toggle a fake RFC 2217 client (192.168.1.41)
    /dev/boot             a short press on BOOT: confirms a pending claim
    /dev/peer?ip=a.b.c.d  requests from this machine look like they come from
                          that address (no ip: back to the real one)
    /dev/rollback         the next firmware update does not confirm itself (MCUboot goes back)
    /dev/image?version=0.6.0[&id=power-hub/power_hub]   an image to upload (unsigned, laid
                          out as zephyr.signed.bin; the bay's own id by default)
    /dev/camera           unplug or plug the camera
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
sys.path.insert(0, str(WEB.parents[1] / "common" / "web"))
from devserver import COMMON_STATIC, XTERM_STATIC, Firmware, make_image, ws_frame, ws_read  # noqa: E402

# The page, and what firmware/common serves on the node too (/rack.css, xterm.js)
STATIC = {"/": (WEB / "index.html", "text/html"), **COMMON_STATIC, **XTERM_STATIC}
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


# --- Ports: a bay with a DATA ×4 board (--ports 4) ---------------------------

PORTS = 1           # the boards the node serves; 1: today's one DUT (node["dut"])
ports: list[dict] = []
UP_S = 0.8          # a board's USB enumeration after power on or reset
# The admission rule (docs/multi-dut-node.md, Power budget): a port goes on only if the ports' INA226
# plus a reserve for its inrush stay within what the node's TPS2553 (1.34-1.52 A) is trusted with
BAY_LIMIT_MA = 1250
RESERVE_MA = 250
STAGGER_S = 0.3     # the ports' start, one after the other


def set_ports(n: int) -> None:
    """Port n is the hub's port n (DATA x4: USB-C n), so its busid is 1-1.<n> (A1.2 -> 1-1.2).
    DATA x4's ports come up off (EN pulled down): the firmware switches them on one by one, each
    through the admission rule."""
    global PORTS
    PORTS = n
    ports[:] = [{"port": i, "hub_port": i, "on": False, "latched": False, "faults": 0, "up_at": 0.0,
                 "client": None, "lease": None, "draw": 0,
                 "usb": dict(USB_PRESETS[X4_PRESETS[i - 1]])}
                for i in range(1, n + 1)] if n > 1 else []
    start = time.monotonic()
    for k, pt in enumerate(ports):
        if admission(pt) is None:
            pt["on"], pt["up_at"] = True, start + k * STAGGER_S + UP_S


def port_ma(pt: dict, now: float) -> int:
    """What a port's board draws (its INA226)."""
    if not pt["on"]:
        return 0
    return pt["draw"] or dut_current_ma(now + 2.1 * pt["port"])


def admission(pt: dict) -> str | None:
    """Why the port may not go on now (the other ports' draw), or None."""
    others = sum(port_ma(q, time.monotonic()) for q in ports if q is not pt)
    if others + RESERVE_MA > BAY_LIMIT_MA:
        return (f"no room in the bay's budget: the other ports draw {others} mA, "
                f"{RESERVE_MA} mA kept for a start, {BAY_LIMIT_MA} mA in all")
    return None


def multi() -> bool:
    return PORTS > 1


def slot_name(n: int) -> str:
    return f"{node['id'].upper()}.{n}" if multi() else node["id"].upper()


def port_lease_active(pt: dict) -> bool:
    return pt["lease"] is not None and time.monotonic() < pt["lease"]["until"]


def port_reserved(pt: dict, ip: int) -> bool:
    return port_lease_active(pt) and pt["lease"]["holder"] != ip


def lease_doc(lease: dict | None, ip: int, now: float) -> dict | None:
    if lease is None or now >= lease["until"]:
        return None
    return {"holder": ip_str(lease["holder"]), "note": lease["note"],
            "remaining_s": math.ceil(lease["until"] - now), "yours": lease["holder"] == ip}


def port_doc(pt: dict, ip: int = 0) -> dict:
    """One object of GET /api/ports."""
    now = time.monotonic()
    ma = port_ma(pt, now)
    mv = 5080 - ma // 10 if pt["on"] else 0
    usb = {**pt["usb"], "busid": f"1-1.{pt['hub_port']}"} if pt["on"] and now >= pt["up_at"] else None
    return {"slot": slot_name(pt["port"]), "port": pt["port"], "hub_port": pt["hub_port"],
            "power": {"on": pt["on"], "mv": mv, "ma": ma, "mw": ma * mv // 1000, "faults": pt["faults"]},
            "fault": pt["latched"], "usb": usb,
            "usbip": {"client": ip_str(pt["client"])} if pt["client"] and usb else None,
            "lease": lease_doc(pt["lease"], ip, now)}


def one_port_doc(s: dict) -> dict:
    """A one-port node's DUT as port 1 (no hub: busid 1-1)."""
    dut, lease = s["dut"], s["access"]["lease"]
    client = next((c for c in access.fake if c["service"] == "usbip"), None)
    usb = ({"vid": "2fe3", "pid": "0004", "product": "USB-DEV", "serial": "005EC0A1", "busid": "1-1"}
           if dut["on"] and s["usb"]["devices"] else None)
    return {"slot": slot_name(1), "port": 1, "hub_port": None,
            "power": {k: dut[k] for k in ("on", "mv", "ma", "mw", "faults")}, "fault": dut["latched"],
            "usb": usb, "usbip": {"client": ip_str(client["peer"])} if client and usb else None,
            "lease": lease if lease["remaining_s"] else None}


def short_port(d: dict) -> dict:
    """The same object, shorter: /api/status's `ports`."""
    return {"slot": d["slot"], "port": d["port"], "power": {"on": d["power"]["on"], "ma": d["power"]["ma"]},
            "fault": d["fault"], "usb": {"busid": d["usb"]["busid"]} if d["usb"] else None,
            "usbip": d["usbip"], "lease": d["lease"]}


def ports_doc(ip: int = 0) -> list[dict]:
    return [port_doc(pt, ip) for pt in ports] if multi() else [one_port_doc(status(ip))]


# --- USB devices (/api/usb): what the node's USB host enumerated --------------

# Read once at enumeration: the device descriptor, the class of each interface
# (CMSIS-DAP by its interface string) and the three strings.  The name is
# iProduct, else the node's table of known IDs, else vid:pid.
USB_PRESETS = {
    "nucleo": {"vid": "0483", "pid": "374b", "manufacturer": "STMicroelectronics",
               "product": "STM32 STLink", "serial": "066DFF495150898367102236", "speed": "full",
               "classes": ["Debug probe", "CDC ACM", "Mass storage"], "serial_bridge": False},
    "mculink": {"vid": "1fc9", "pid": "0143", "manufacturer": "NXP Semiconductors",
                "product": "MCU-LINK on-board (r0E7) CMSIS-DAP V3.172", "serial": "3ZQ1J4ZBMTNKS",
                "speed": "full", "classes": ["CMSIS-DAP", "CDC ACM", "HID"], "serial_bridge": False},
    "ft232": {"vid": "0403", "pid": "6001", "manufacturer": "FTDI", "product": "FT232R USB UART",
              "serial": "A50285BI", "speed": "full", "classes": ["Serial (FTDI)"], "serial_bridge": True},
    "ch340": {"vid": "1a86", "pid": "7523", "manufacturer": None, "product": None, "serial": None,
              "speed": "full", "classes": ["Serial (CH34x)"], "serial_bridge": True},
    "pico": {"vid": "2e8a", "pid": "0003", "manufacturer": "Raspberry Pi", "product": "RP2 Boot",
             "serial": "E0C9125B0D9B", "speed": "full", "classes": ["Mass storage", "Vendor"],
             "serial_bridge": False},
    "unknown": {"vid": "1209", "pid": "c0de", "manufacturer": None, "product": None, "serial": None,
                "speed": "full", "classes": ["Vendor"], "serial_bridge": False},
}
# The node's table of known IDs (src/usb_names.c): names for devices without iProduct
USB_KNOWN = {("1a86", "7523"): "CH340 serial adapter", ("0403", "6001"): "FT232 serial adapter",
             ("2e8a", "0003"): "RP2040 in BOOTSEL", ("1fc9", "0143"): "MCU-Link",
             ("0483", "374b"): "ST-LINK/V2-1"}
X4_PRESETS = ["mculink", "ft232", "pico", "ch340"]   # DATA x4 ports 1..4
usb_one = "nucleo"                                      # a one-port bay's DUT: /dev/usb?preset=
USB_SINCE = {}                                          # busid -> when its USB/IP client attached
HUB = {"vid": "0424", "pid": "2517", "name": "USB2517 hub", "data_x4": True}


def usb_dev_doc(dev: dict, busid: str, slot: str, hub_port, client: int | None, ma) -> dict:
    """One object of GET /api/usb's devices."""
    name, source = dev["product"], "product"
    if not name:
        name, source = USB_KNOWN.get((dev["vid"], dev["pid"])), "table"
    if not name:
        name, source = f"{dev['vid']}:{dev['pid']}", "ids"
    now = time.monotonic()
    if client:
        USB_SINCE.setdefault(busid, now - 754)
    else:
        USB_SINCE.pop(busid, None)
    return {"busid": busid, "slot": slot, "hub_port": hub_port, "vid": dev["vid"], "pid": dev["pid"],
            "name": name, "name_from": source, "manufacturer": dev["manufacturer"], "serial": dev["serial"],
            "strings": True, "speed": dev["speed"], "classes": dev["classes"],
            "usbip": {"client": ip_str(client) if client else None,
                      "since_s": int(now - USB_SINCE[busid]) if client else None,
                      "offered": True, "read_ahead": dev["serial_bridge"]},
            "ma": ma}


def usb_doc() -> dict:
    s = status()
    if multi():
        devs = []
        for d in ports_doc():
            if d["usb"]:
                pt = ports[d["port"] - 1]
                devs.append(usb_dev_doc(pt["usb"], d["usb"]["busid"], d["slot"], d["hub_port"],
                                        pt["client"], d["power"]["ma"]))
        return {"hub": HUB, "devices": devs}
    d = one_port_doc(s)
    client = next((c["peer"] for c in access.fake if c["service"] == "usbip"), None)
    devs = [usb_dev_doc(USB_PRESETS[usb_one], "1-1", d["slot"], None, client, None)] if d["usb"] else []
    return {"hub": None, "devices": devs}


def port_act(pt: dict, what: str, body: dict) -> tuple[int, str] | None:
    """Power, reset or boot one port, as the node's dut.c does for its one DUT; (status, error), or None."""
    if what == "power":
        action = body.get("action")
        if action not in ("on", "off", "cycle"):
            return 400, "action must be on, off or cycle"
        if action != "off":
            was = pt["on"]
            pt["on"] = False                  # its own draw does not count against it
            refused = admission(pt)
            pt["on"] = was
            if refused is not None:
                return 409, refused
        if action == "cycle":
            time.sleep(min(int(body.get("ms", 1000)), 2000) / 1000)
        was_on = pt["on"]
        pt["on"] = action != "off"
        if pt["on"]:
            pt["latched"] = False
        if not pt["on"] or action == "cycle" or not was_on:
            pt["client"] = None           # the board left the bus: its USB/IP session ends
            pt["up_at"] = time.monotonic() + UP_S
    elif what == "boot" and body.get("power_cycle"):
        was = pt["on"]
        pt["on"] = False                  # back on through the admission rule, as any power on
        refused = admission(pt)
        pt["on"] = was
        if refused is not None:
            return 409, refused
        time.sleep(1.0)                   # BOOT held across a power cycle of the port: the board comes up in its ROM
        pt["on"], pt["latched"], pt["client"] = True, False, None
        pt["up_at"] = time.monotonic() + UP_S
    else:
        time.sleep(0.3 if what == "boot" else min(int(body.get("ms", 100)), 500) / 1000)
        if pt["on"]:
            pt["client"] = None           # a reset re-enumerates the board, under the same busid
            pt["up_at"] = time.monotonic() + UP_S
    return None


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

SERVICES = ["status", "control", "console", "usbip", "shell", "camera"]
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
                    return "everyone: services are status, control, console, usbip, shell, camera or all"
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
                        return "source allow: status, control, console, usbip, shell, camera, all"
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
        with camera.lock:
            for slot, c in camera.clients.items():
                out.append({"id": f"cam{slot}", "service": "camera",
                            "label": "camera stream" if c["stream"] else "snapshot",
                            "peer": c["ip"], "port": c["port"], "since": c["since"]})
        return out + [dict(c) for c in self.fake]

    def close(self, conn: dict) -> None:
        if conn["id"].startswith("web"):
            console.kick(int(conn["id"][3:]))
        elif conn["id"].startswith("cam"):
            camera.kick(int(conn["id"][3:]))
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


firmware = Firmware("0.5.0", "bay-node/bay_node")


# --- The fake camera: an Arducam Mega looking down at the drawer -------------

CAM_RESOLUTIONS = ["320x240", "640x480", "1280x720", "1600x1200", "1920x1080"]
CAM_QUALITIES = {"high": 90, "default": 75, "low": 50}
# White balance presets as a colour cast (red, green, blue gains)
CAM_WB = {"auto": (1, 1, 1), "sunny": (1.06, 1.0, 0.92), "office": (0.96, 1.03, 1.05),
          "cloudy": (1.1, 1.0, 0.86), "home": (1.16, 1.0, 0.8)}
CAM_IMAGE_DEFAULTS = {"exposure": "auto", "exposure_value": 1000, "gain": "auto", "gain_value": 64,
                      "white_balance": "auto", "brightness": 0, "contrast": 0, "saturation": 0,
                      "sharpness": "auto"}
CAM_CHOICES = {"resolutions": CAM_RESOLUTIONS, "qualities": list(CAM_QUALITIES),
               "white_balances": list(CAM_WB), "exposure_value": [0, 30000], "gain_value": [0, 1023],
               "brightness": [-4, 4], "contrast": [-3, 3], "saturation": [-3, 3], "sharpness": [1, 8],
               "rotation": [0, 90, 180, 270]}


def cam_int(value, lo: int, hi: int) -> int | None:
    """Like parse_int() in camera.c: a whole number in [lo, hi], given as a number or text."""
    try:
        v = int(str(value), 10)
    except ValueError:
        return None
    return v if lo <= v <= hi else None


def cam_set_one(c: dict, name: str, value) -> str | None:
    """set_one() in camera.c: one setting by name into c, or the error."""
    v = str(value)
    if name == "resolution":
        if v not in CAM_RESOLUTIONS:
            return "resolution: 320x240, 640x480, 1280x720, 1600x1200 or 1920x1080"
        c[name] = v
    elif name == "quality":
        if v not in CAM_QUALITIES:
            return "quality: high, default or low"
        c[name] = v
    elif name == "light":
        if v not in ("on", "off"):
            return "light: on or off"
        c[name] = v
    elif name in ("exposure", "gain"):
        hi = 30000 if name == "exposure" else 1023
        if v in ("auto", "manual"):
            c[name] = v
        elif (n := cam_int(v, 0, hi)) is not None:
            c[name], c[name + "_value"] = "manual", n
        else:
            return f"{name}: auto, manual or 0-{hi}"
    elif name in ("exposure_value", "gain_value"):
        hi = 30000 if name == "exposure_value" else 1023
        if (n := cam_int(v, 0, hi)) is None:
            return f"{name}: 0-{hi}"
        c[name] = n
    elif name == "white_balance":
        if v not in CAM_WB:
            return "white_balance: auto, sunny, office, cloudy or home"
        c[name] = v
    elif name in ("brightness", "contrast", "saturation"):
        lim = 4 if name == "brightness" else 3
        if (n := cam_int(v, -lim, lim)) is None:
            return f"{name}: -{lim} to {lim}"
        c[name] = n
    elif name == "sharpness":
        if v == "auto":
            c[name] = "auto"
        elif (n := cam_int(v, 1, 8)) is not None:
            c[name] = n
        else:
            return "sharpness: auto or 1-8"
    elif name == "rotation":
        if (n := cam_int(v, 0, 270)) is None or n % 90:
            return "rotation: 0, 90, 180 or 270"
        c[name] = n
    else:
        return "unknown setting"
    return None
CAM_SLOTS = 3
CAM_FPS = 5
CAM_SETTLE_S = 0.3
# B2's camera as the viewer (site/) renders it, grabbed by grab_camera.py at these
# resolutions, frames 300 ms apart (the GIGA's screen plays), the light on and off
CAM_FRAMES = WEB / "camera"
CAM_GRABBED = ((640, 480), (1600, 1200))
CAM_FRAME_S = 0.3


def cam_frames() -> dict[tuple[int, int, str], list[bytes]]:
    """The grabbed frames: {(width, height, "on" or "off"): [JPEG, ...]}."""
    frames: dict[tuple[int, int, str], list[bytes]] = {}
    for path in sorted(CAM_FRAMES.glob("b2-*.jpg")):
        if m := re.fullmatch(r"b2-(\d+)x(\d+)-(on|off)-\d+\.jpg", path.name):
            frames.setdefault((int(m[1]), int(m[2]), m[3]), []).append(path.read_bytes())
    return frames


def cam_process(data: bytes, w: int, h: int, c: dict) -> bytes:
    """What the Mega's image processor would do to a grabbed frame, roughly (needs Pillow):
    the resolution (16:9 cut from the middle of the 4:3 frame), a manual exposure or gain,
    the image settings, the JPEG quality."""
    from io import BytesIO

    from PIL import Image, ImageEnhance

    img = Image.open(BytesIO(data)).convert("RGB")
    if w * 3 != h * 4:
        ch = img.width * h // w
        top = (img.height - ch) // 2
        img = img.crop((0, top, img.width, top + ch))
    if img.size != (w, h):
        img = img.resize((w, h), Image.LANCZOS)
    level = 1.0
    if c["exposure"] == "manual":
        level *= min(3.0, max(0.05, c["exposure_value"] / 1000))
    if c["gain"] == "manual":
        level *= min(3.0, max(0.2, (c["gain_value"] / 64) ** 0.5))
    img = ImageEnhance.Brightness(img).enhance(level * (1 + 0.12 * c["brightness"]))
    img = ImageEnhance.Contrast(img).enhance(1 + 0.2 * c["contrast"])
    img = ImageEnhance.Color(img).enhance(max(0.0, 1 + 0.3 * c["saturation"]))
    if c["sharpness"] != "auto":
        img = ImageEnhance.Sharpness(img).enhance(0.25 * c["sharpness"])
    if c["white_balance"] != "auto":
        gains = CAM_WB[c["white_balance"]]
        img = Image.merge("RGB", [band.point(lambda v, g=g: min(255, int(v * g)))
                                  for band, g in zip(img.split(), gains)])
    out = BytesIO()
    img.save(out, "JPEG", quality=CAM_QUALITIES[c["quality"]])
    return out.getvalue()


class Camera:
    """src/camera.c: the settings, the clients, the frames."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.present = True
        self.port = 0
        self.cfg = {"resolution": "640x480", "quality": "default", "light": "on", "rotation": 0,
                    **CAM_IMAGE_DEFAULTS}
        self.clients: dict[int, dict] = {}   # slot -> stream, ip, port, since, light, kicked
        self.frames = self.errors = self.last_bytes = self.last_ms = 0
        self.stamps: list[float] = []
        self.grabbed: dict[tuple[int, int, str], list[bytes]] | None = None

    def lit(self) -> bool:
        """Like want_light(): during a lease only the holder's wish counts."""
        holder = access.lease["holder"] if access.lease_active() else None
        return any((c["light"] or self.cfg["light"]) == "on" for c in self.clients.values()
                   if holder is None or c["ip"] == holder)

    def doc(self, full: bool = False) -> dict:
        """The camera object of /api/status; with full, GET /api/camera's."""
        with self.lock:
            streams = sum(c["stream"] for c in self.clients.values())
            now = time.monotonic()
            recent = [t for t in self.stamps if now - t < 5]
            cfg = dict(self.cfg)
            d = {"present": self.present, "model": "Arducam Mega 3MP" if self.present else "",
                 "port": self.port, "resolution": cfg["resolution"], "quality": cfg["quality"],
                 "light": cfg["light"], "rotation": cfg["rotation"],
                 "lit": bool(self.clients) and self.lit(),
                 "clients": len(self.clients), "streams": streams, "slots": CAM_SLOTS,
                 "frames": self.frames, "errors": self.errors, "last_bytes": self.last_bytes,
                 "last_ms": self.last_ms, "fps": round(len(recent) / 5, 1) if streams else 0}
        if full:
            d.update(settings=cfg, choices=CAM_CHOICES)
        return d

    def configure(self, body: dict) -> str | None:
        """camera_configure(): all or nothing; "reset": true, the image settings to auto first."""
        with self.lock:
            c = dict(self.cfg)
        if body.get("reset") is True:
            c.update(CAM_IMAGE_DEFAULTS)
        for name, value in body.items():
            if name != "reset" and (err := cam_set_one(c, name, value)) is not None:
                return err
        with self.lock:
            self.cfg = c
        return None

    def frame(self) -> bytes:
        """A JPEG at the set resolution and quality: a grabbed frame, the light on or off, the
        next one every CAM_FRAME_S.  Pillow brings it to the other resolutions and applies the
        image settings; without it, the frame goes as grabbed."""
        t0 = time.monotonic()
        with self.lock:
            if self.grabbed is None:
                self.grabbed = cam_frames()
            lit = self.lit()
            c = dict(self.cfg)
        w, h = map(int, c["resolution"].split("x"))
        # the grab at this resolution, or the smallest one at least as wide
        gw, gh = next(((gw, gh) for gw, gh in CAM_GRABBED if gw >= w), CAM_GRABBED[-1])
        shots = self.grabbed[(gw, gh, "on" if lit else "off")]
        data = shots[int(t0 / CAM_FRAME_S) % len(shots)]
        if (gw, gh) != (w, h) or c["quality"] != "default" or any(
                c[k] != v for k, v in CAM_IMAGE_DEFAULTS.items()):
            try:
                data = cam_process(data, w, h, c)
            except ImportError:
                pass
        with self.lock:
            self.frames += 1
            self.last_bytes = len(data)
            self.last_ms = int((time.monotonic() - t0) * 1000) + 40
            self.stamps = [t for t in self.stamps if time.monotonic() - t < 5] + [time.monotonic()]
        return data

    def kick(self, slot: int) -> None:
        with self.lock:
            if slot in self.clients:
                self.clients[slot]["kicked"] = True


camera = Camera()


class CameraHandler(BaseHTTPRequestHandler):
    """The camera's port: GET /snapshot.jpg, /stream.mjpg [?light=on|off|auto]."""

    def text(self, code: int, msg: str) -> None:
        body = (msg + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        real = self.client_address[0]
        ip = ip_int(PEER_OVERRIDE.get(real, real))
        if access.check("camera", ip) != "ok":
            self.close_connection = True   # the node closes a refused connection at once
            return
        url = urlsplit(self.path)
        light = parse_qs(url.query).get("light", ["auto"])[0]
        if url.path not in ("/snapshot.jpg", "/stream.mjpg"):
            return self.text(404, "GET /snapshot.jpg or /stream.mjpg [?light=on|off|auto]")
        if not camera.present:
            return self.text(503, "no camera on this bay")
        stream = url.path == "/stream.mjpg"
        with camera.lock:
            free = [s for s in range(CAM_SLOTS) if s not in camera.clients]
            if not free:
                return self.text(503, "camera busy: too many clients")
            slot = free[0]
            was_lit = bool(camera.clients) and camera.lit()
            me = camera.clients[slot] = {"stream": stream, "ip": ip, "port": self.client_address[1],
                                        "since": time.monotonic(), "kicked": False,
                                        "light": light if light in ("on", "off") else None}
            now_lit = camera.lit()
        try:
            if now_lit and not was_lit:
                time.sleep(CAM_SETTLE_S)
            if not stream:
                data = camera.frame()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            while not me["kicked"]:
                t = time.monotonic()
                data = camera.frame()
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                 + f"Content-Length: {len(data)}\r\n\r\n".encode() + data + b"\r\n")
                self.wfile.flush()
                time.sleep(max(0.0, 1 / CAM_FPS - (time.monotonic() - t)))
        except OSError:
            pass
        finally:
            with camera.lock:
                camera.clients.pop(slot, None)
            self.close_connection = True

    def log_message(self, fmt: str, *args) -> None:
        pass


def status(ip: int = 0) -> dict:
    dut = node["dut"]
    ma = dut_current_ma(time.monotonic()) if dut["on"] else 0
    mv = (5080 - ma // 10) if dut["on"] else 0
    dut.update(ma=ma, mv=mv, mw=ma * mv // 1000)
    node["path"] = "classic" if node["force_classic"] else "usbip"
    docs = [port_doc(pt, ip) for pt in ports]
    if docs:                            # the node's totals: the sum of the currents, flags ORed
        dut.update(on=any(d["power"]["on"] for d in docs), latched=any(d["fault"] for d in docs),
                   faults=sum(d["power"]["faults"] for d in docs), ma=sum(d["power"]["ma"] for d in docs),
                   mv=max(d["power"]["mv"] for d in docs), mw=sum(d["power"]["mw"] for d in docs))
        node["usb"]["devices"] = sum(d["usb"] is not None for d in docs)
        node["usb"]["sessions"] = (sum(d["usbip"] is not None for d in docs)
                                   + sum(c["service"] == "usbip" for c in access.fake))
    fmt = f"{aux['data_bits']}{aux['parity'][0].upper()}{aux['stop_bits']}"
    s = {**node, "uptime_s": int(time.monotonic() - START),
            "aux": {"baud": aux["baud"], "format": fmt, "port": 4000, "rfc2217_port": 4001,
                    "web_clients": len(console.clients),
                    "rfc2217": any(c["id"] == "rfc2217" for c in access.fake), "raw": False,
                    "rx": len(console.log), "tx": console.tx, "dropped": 0},
            "access": access.summary(ip), "firmware": firmware.doc(), "camera": camera.doc()}
    s["ports"] = [short_port(d) for d in docs or [one_port_doc(s)]]
    return s


def aux_doc() -> dict:
    return {"type": "aux", **aux, "web_clients": len(console.clients), "web_slots": WEB_SLOTS,
            "rfc2217": False, "rfc2217_port": 4001, "raw": False, "raw_port": 4000,
            "rx": len(console.log), "tx": console.tx, "dropped": 0}


def metrics() -> str:
    s = status()
    dut, usb, a = s["dut"], s["usb"], s["aux"]
    bay = f'bay="{s["id"]}"'
    # The DUT metrics: the one DUT's, or each port's, labelled port="B3.2"
    duts = ([(f'{bay},port="{d["slot"]}"', d["power"], d["fault"]) for d in ports_doc()] if multi()
            else [(bay, dut, dut["fault"] or dut["latched"])])
    rows = [
        ("bay_dut_vbus_volts", "gauge", [(lb, pw["mv"] / 1000) for lb, pw, _ in duts]),
        ("bay_dut_current_amperes", "gauge", [(lb, pw["ma"] / 1000) for lb, pw, _ in duts]),
        ("bay_dut_power_watts", "gauge", [(lb, pw["mw"] / 1000) for lb, pw, _ in duts]),
        ("bay_dut_power_on", "gauge", [(lb, int(pw["on"])) for lb, pw, _ in duts]),
        ("bay_dut_fault", "gauge", [(lb, int(f)) for lb, _, f in duts]),
        ("bay_dut_faults_total", "counter", [(lb, pw["faults"]) for lb, pw, _ in duts]),
        ("bay_usb_devices", "gauge", [(bay, usb["devices"])]),
        ("bay_usbip_sessions", "gauge", [(bay, usb["sessions"])]),
        ("bay_aux_rx_bytes_total", "counter", [(bay, a["rx"])]),
        ("bay_aux_tx_bytes_total", "counter", [(bay, a["tx"])]),
        ("bay_access_refused_total", "counter", [(bay, access.refused_total)]),
    ]
    out = []
    for name, kind, values in rows:
        out.append(f"# TYPE {name} {kind}")
        out += [f"{name}{{{lb}}} {value:f}" for lb, value in values]
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
        if firmware.down() and not path.startswith("/dev/"):
            self.json(503, {"error": "restarting"})
        elif path in STATIC:
            file, ctype = STATIC[path]
            self.send(200, file.read_bytes(), ctype)
        elif path.startswith("/console/ws/"):
            self.websocket(int(path.rsplit("/", 1)[1]), query.get("t", [""])[0])
        elif path == "/api/status":
            if not self.refused("status"):
                self.json(200, status(self.peer()))
        elif path == "/api/ports":
            if not self.refused("status"):
                self.json(200, ports_doc(self.peer()))
        elif path == "/api/aux":
            if not self.refused("status"):
                self.json(200, aux_doc())
        elif path == "/api/usb":
            if not self.refused("status"):
                self.json(200, usb_doc())
        elif path == "/dev/usb":
            global usb_one
            preset = query.get("preset", ["nucleo"])[0]
            if preset not in USB_PRESETS:
                return self.json(404, {"error": f"presets: {', '.join(USB_PRESETS)}"})
            if "port" in query and multi():
                ports[int(query["port"][0]) - 1]["usb"] = dict(USB_PRESETS[preset])
            else:
                usb_one = preset
            self.json(200, usb_doc())
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
        elif path == "/api/update":
            self.json(200, firmware.doc())
        elif path == "/api/camera":
            if not self.refused("status"):
                self.json(200, camera.doc(full=True))
        elif path == "/dev/camera":
            camera.present = not camera.present
            self.json(200, camera.doc())
        elif path == "/dev/rollback":
            firmware.rollback()
            self.json(200, {"rollback": True})
        elif path == "/dev/image":
            self.send(200, make_image(query.get("version", ["0.6.0"])[0],
                                      query.get("id", [firmware.image_id])[0]), "application/octet-stream")
        elif path == "/dev/draw" and "port" in query and multi():
            pt = next((x for x in ports if str(x["port"]) == query["port"][0]), None)
            if pt is None:
                return self.json(404, {"error": f"no port {query['port'][0]} (1..{PORTS})"})
            pt["draw"] = max(0, int(query.get("ma", ["0"])[0]))
            self.json(200, port_doc(pt))
        elif path in ("/dev/fault", "/dev/attach") and "port" in query and multi():
            pt = next((x for x in ports if str(x["port"]) == query["port"][0]), None)
            if pt is None:
                return self.json(404, {"error": f"no port {query['port'][0]} (1..{PORTS})"})
            if path == "/dev/fault":
                pt.update(on=False, latched=True, faults=pt["faults"] + 1, client=None)
            else:
                pt["client"] = None if pt["client"] else ip_int("192.168.1.41")
            self.json(200, port_doc(pt))
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
        url = urlsplit(self.path)
        if firmware.down():
            return self.json(503, {"error": "restarting"})
        if url.path == "/api/update":
            ticket = parse_qs(url.query).get("ticket", [""])[0]
            return self.json(*firmware.upload(self.client_address[0], ticket, raw))
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self.json(400, {"error": "bad JSON"})
        path = urlsplit(self.path).path
        if path == "/api/update/begin":
            if not access.admin(self.headers.get("X-Bay-Auth", ""), "POST", path, raw):
                return self.json(403, {"error": "admin only: unlock with the admin key"})
            firmware.busy = None
            if access.lease_active():
                lease = access.lease
                firmware.busy = (f"reserved by {ip_str(lease['holder'])} for "
                                 f"{math.ceil((lease['until'] - time.monotonic()) / 60)} min more: "
                                 "force to update anyway")
            return self.json(*firmware.begin(self.client_address[0], body))
        if path.startswith("/api/access/") or path in ("/api/lease", "/api/console/ticket"):
            return self.access_post(path, raw, body)
        if path == "/api/camera":
            if self.refused("control"):
                return
            if not camera.present:
                return self.json(404, {"error": "no camera on this bay"})
            if (err := camera.configure(body)) is not None:
                return self.json(400, {"error": err})
            return self.json(200, camera.doc(full=True))
        if self.refused("console" if path in ("/api/aux", "/api/aux/break") else "control"):
            return
        m = re.fullmatch(r"/api/ports/(\d+)/(power|reset|boot)", path)
        if m:
            return self.port_post(int(m[1]), m[2], body, port_reply=True)
        if multi() and path in ("/api/power", "/api/reset", "/api/boot"):
            if "port" not in body:
                return self.json(409, {"error": f"this node serves {PORTS} boards: say which "
                                                f"(\"port\": 1..{PORTS}, or /api/ports/<n>{path[4:]})"})
            return self.port_post(body["port"], path[5:], body, port_reply=False)
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

    def port_post(self, n, what: str, body: dict, port_reply: bool) -> None:
        """POST /api/ports/<n>/<what>, or /api/<what> with "port": n: the port's object, or the status."""
        pt = next((x for x in ports if x["port"] == n), None) if multi() else None
        if pt is None:
            return self.json(404, {"error": f"no port {n} on this node" + (f" (1..{PORTS})" if multi() else "")})
        ip = self.peer()
        if port_reserved(pt, ip):
            lease = pt["lease"]
            note = f" ({lease['note']})" if lease["note"] else ""
            left = math.ceil((lease["until"] - time.monotonic()) / 60)
            return self.json(423, {"error": f"{slot_name(n)} reserved by {ip_str(lease['holder'])}{note}, "
                                            f"{left} min left", "reason": "reserved", "service": "control",
                                   "you": ip_str(ip)})
        if (err := port_act(pt, what, body)) is not None:
            return self.json(err[0], {"error": err[1]})
        self.json(200, port_doc(pt, ip) if port_reply else status(ip))

    def port_lease(self, ip: int, admin: bool, body: dict) -> bool:
        """A lease on sub-slots, {"ttl_s": 3600, "ports": ["B3.2"]}, or its release; True once answered with an error."""
        names = body["ports"]
        if not multi():
            self.json(400, {"error": "this node serves one board: lease the bay (no \"ports\")"})
            return True
        by_name = {slot_name(pt["port"]): pt for pt in ports}
        if not isinstance(names, list) or not names or any(str(x).upper() not in by_name for x in names):
            self.json(400, {"error": f"ports: a list of {', '.join(by_name)}"})
            return True
        chosen = [by_name[str(x).upper()] for x in names]
        with access.lock:
            if body.get("release"):
                if not admin and any(port_lease_active(pt) and pt["lease"]["holder"] != ip for pt in chosen):
                    self.json(403, {"error": "only its holder or an admin may release it"})
                    return True
                for pt in chosen:
                    pt["lease"] = None
                return False
            ttl = int(body.get("ttl_s", LEASE_DEFAULT_S))
            if not 10 <= ttl <= 86400:
                self.json(400, {"error": "ttl_s must be 10..86400"})
                return True
            taken = next((pt for pt in chosen if port_reserved(pt, ip)), None)
            if taken is not None:
                self.json(423, {"error": f"{slot_name(taken['port'])} reserved by "
                                         f"{ip_str(taken['lease']['holder'])}", "reason": "reserved"})
                return True
            for pt in chosen:
                pt["lease"] = {"holder": ip, "until": time.monotonic() + ttl,
                               "note": clean_note(str(body.get("note", "")))}
                if pt["client"] not in (None, ip):
                    pt["client"] = None   # its USB/IP import belongs to the holder now
        return False

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
        elif path == "/api/lease" and "ports" in body:
            if not body.get("release") and self.refused("control"):
                return
            if self.port_lease(ip, admin, body):
                return
        elif path == "/api/lease":
            if body.get("release"):
                with access.lock:
                    if access.lease_active() and not admin and access.lease["holder"] != ip:
                        return self.json(403, {"error": "only its holder or an admin may release it"})
                    access.lease = None
            else:
                if self.refused("control"):
                    return
                taken = next((pt for pt in ports if port_reserved(pt, ip)), None)
                if taken is not None:
                    return self.json(423, {"error": f"{slot_name(taken['port'])} reserved by "
                                                    f"{ip_str(taken['lease']['holder'])}", "reason": "reserved"})
                if (err := access.take(ip, int(body.get("ttl_s", LEASE_DEFAULT_S)), str(body.get("note", "")))):
                    return self.json(400, {"error": err})
        else:
            return self.json(404, {"error": "not found"})
        d = access.doc(ip, admin)
        if path == "/api/lease" and multi():
            d["ports"] = [short_port(port_doc(pt, ip)) for pt in ports]
        self.json(200, d)

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
    # The camera on the next port, as the node has it on its own (8081)
    cam_server = ThreadingHTTPServer(("127.0.0.1", port + 1 if port else 0), CameraHandler)
    camera.port = cam_server.server_address[1]
    cam_server.daemon_threads = True
    threading.Thread(target=cam_server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="The bay node's web page and API, on a simulated node.")
    ap.add_argument("port", type=int, nargs="?", default=8766)
    ap.add_argument("--ports", type=int, default=1, choices=range(1, 5),
                    help="boards the node serves: 4 for a bay with a DATA ×4 board (docs/multi-dut-node.md)")
    a = ap.parse_args()
    set_ports(a.ports)
    print(f"bay node mock on http://localhost:{a.port} (camera on port {a.port + 1})"
          + (f", {a.ports} ports" if a.ports > 1 else ""))
    serve(a.port).serve_forever()
