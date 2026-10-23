#!/usr/bin/env python3
"""bayctl — drive the rack's bays from a CI host or a laptop.

    python tools/bayctl.py list [--probe]               boards under test, their Zephyr target, runner, host
    python tools/bayctl.py status B3                    the node's /api/status
    python tools/bayctl.py ports B3                     the node's ports: board, power, USB device, busid, client
    python tools/bayctl.py power B3 on|off|cycle [--ms 2000]
    python tools/bayctl.py reset B3 [--ms 100]          pulse the DUT's RESET line (AUX)
    python tools/bayctl.py boot B3 [--power-cycle]      DUT into its ROM bootloader (AUX BOOT + RESET, or + power)
    python tools/bayctl.py mode B3 usbip|classic
    python tools/bayctl.py attach B3 [--show] [--follow]   Linux: usbip attach, list the new /dev/serial/by-id
    python tools/bayctl.py detach B3
    python tools/bayctl.py prepare B3 [--power-cycle] [--lease 30m]   what a test runner needs before flashing
    python tools/bayctl.py pty B3                       stdin/stdout <-> the AUX UART (twister serial_pty)
    python tools/bayctl.py hwmap -o rack-map.yaml       Zephyr twister hardware map + per-bay pre-scripts, from the rack
    python tools/bayctl.py export labgrid|pdudaemon     configuration for labgrid / LAVA's PDUDaemon
    python tools/bayctl.py export lab [-o FILE]         the board targets the nodes hold, as lab.yaml entries (backup)
    python tools/bayctl.py import lab FILE [B3 ...]     write such entries back to the nodes (PUT /api/ports/<n>/board)
    python tools/bayctl.py lease B3 [--for 1h] [--note TEXT]    reserve the bay for this host
    python tools/bayctl.py release B3 [--force]         end the reservation (--force: someone else's, admin)
    python tools/bayctl.py access show B3               rights, reservation, connections (admin: rules, refusals)
    python tools/bayctl.py access push [B3 ...]         the `access:` rules of config/lab.yaml to the nodes
    python tools/bayctl.py access claim B3 [...]        give the nodes the rack's admin key (press BOOT on each)
    python tools/bayctl.py access kick B3 usbip:51234   close a connection, refuse its address for a minute
    python tools/bayctl.py access keygen                a new random admin key
    python tools/bayctl.py update IMAGE B3 [...]        firmware over the network (zephyr.signed.bin)
    python tools/bayctl.py update IMAGE --all           every bay node the hub lists, one after the other
    python tools/bayctl.py update IMAGE --hub           the power hub itself (BAYCTL_HUB, lab.yaml `hub:`, or rack.local)
    python tools/bayctl.py row A|B|C|D on|off|cycle [--ms 1000]   switch or cycle a rack row on the power hub
    python tools/bayctl.py hub [status|events|enumerate|pd|node|claim]   inspect or control the power hub

A bay with a DATA ×4 board holds up to four boards, sub-slots B3.1 to B3.4 (docs/multi-dut-node.md):
name one (`power B3.2 cycle`, `attach B3.2 --follow`, `prepare B3.2`, `lease B3.2`) or the whole bay
(`power B3 off`: every port the node has).  The node's own commands (status, mode, access, update) take
either.  A sub-slot given `role: analyzer` in config/lab.yaml holds the bay's logic analyzer, not a board
under test: `list` shows it, `hwmap` leaves it out, and the whole bay's reset, boot, attach and detach pass
it by (name it: `attach B3.3`; `boot B3.3 --power-cycle` puts it in BOOTSEL through the BOOT wire).

Where the data comes from:
  * the rack: the power hub lists its nodes by position and address (GET /api/status; the hub is
    BAYCTL_HUB=host[:port], else lab.yaml `hub:`, else rack.<domain>; BAYCTL_HUB=none: no hub), and each
    node its slots (GET /api/boards): the board target set on the node's page (Zephyr target, runner,
    probe id, console, in the map or not) and the USB device in the slot now, whose descriptor strings
    give the console's /dev/serial/by-id name as udev makes it.  Bay names are positions: "B3.2" is node
    B3's port 2.  The hub lookup gives up within seconds: offline, the lab file's entries stand alone;
  * config/lab.yaml (per installation, git-ignored, optional; see config/lab.example.yaml): overrides,
    per slot (platform, runner, id, serial, console, ci, fixtures, product, baud, role) and per node
    (host, ports), the access rules; its entries also stand in for nodes the rack does not report;
  * mechanical/boards/boards.yaml `zephyr:`: defaults per board family (runner, product, notes), the
    family found from the target, or named by a lab entry's `board:`;
  * config/rack.yaml: only its `analyzer:` section (the logic analyzer's pinned release, USB id), for
    `list` when a slot holds one.
`export lab` saves the nodes' targets (with the device each is pinned to) for a backup; `import lab`
puts them back.

The nodes speak plain HTTP/JSON (firmware/README.md, "Web page and API") and USB/IP on TCP 3240.
Each node only serves the addresses its access rules allow (firmware/README.md, "Access
control"); admin requests (rules, kicks) are signed with the rack's admin key, taken from the
BAYCTL_KEY environment variable, never from a file in the repository.  `attach`/`detach` call
the Linux `usbip` tool (package linux-tools / usbip; needs root, so bayctl prefixes `sudo -n`).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import shlex
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

import rackcfg

REPO = Path(__file__).resolve().parents[1]
RACK_YAML = REPO / "config" / "rack.yaml"
BOARDS_YAML = REPO / "mechanical" / "boards" / "boards.yaml"
LAB_YAML = REPO / "config" / "lab.yaml"
SERIAL_BY_ID = Path("/dev/serial/by-id")
BY_ID = "/dev/serial/by-id"         # the CI host's (Linux) console links, whatever runs bayctl
HUB_TIMEOUT = 3.0                   # the hub lookup gives up fast: offline, bayctl goes on with config/lab.yaml
NODE_TIMEOUT = 5.0                  # a node's /api/boards
STRINGS_WAIT_S = 1.0                # a device's strings are read within a second of its enumeration


class BayError(Exception):
    def __init__(self, msg: str, status: int | None = None):
        super().__init__(msg)
        self.status = status        # the HTTP status of a refused request


# ------------------------------------------------------------------------- console names (udev)

_UDEV_OK = frozenset(b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#+-.:=@_")
_UDEV_SPACE = b" \t\n\v\f\r"


def _udev_whitespace(raw: bytes, size: int) -> bytes:
    """udev_replace_whitespace(): the first `size` bytes, leading and trailing whitespace dropped, each run of
    it inside replaced by one "_"."""
    raw = raw.split(b"\0", 1)[0]
    out, space = bytearray(), False
    i = len(raw) - len(raw.lstrip(_UDEV_SPACE))
    while i < min(len(raw), size) and len(out) < size:
        c = raw[i]
        i += 1
        if c in _UDEV_SPACE:
            space = True
            continue
        if space:
            if len(out) + 1 >= size:
                break
            out.append(0x5F)
            space = False
        out.append(c)
    return bytes(out)


def _utf8_char(raw: bytes, i: int) -> int:
    """The length of the valid multi-byte UTF-8 character at raw[i] (udev's utf8_encoded_valid_unichar), else 0."""
    lead = raw[i]
    n = 2 if 0xC0 <= lead < 0xE0 else 3 if 0xE0 <= lead < 0xF0 else 4 if 0xF0 <= lead < 0xF8 else 0
    try:
        ch = ord(raw[i:i + n].decode("utf-8")) if n else 0     # strict: no overlong form, no surrogate
    except UnicodeDecodeError:
        return 0
    return n if ch and not 0xFDD0 <= ch <= 0xFDEF and ch & 0xFFFE != 0xFFFE else 0


def _udev_chars(raw: bytes) -> bytes:
    """udev_replace_chars(): what a device node name may hold stays (letters, digits, #+-.:=@_, a \\x escape,
    valid UTF-8, kept as udev keeps it), any other byte becomes "_"."""
    out, i = bytearray(), 0
    while i < len(raw):
        if raw[i] in _UDEV_OK:
            out.append(raw[i])
            i += 1
        elif raw[i:i + 2] == b"\\x":
            out += raw[i:i + 2]
            i += 2
        elif (n := _utf8_char(raw, i)) > 1:
            out += raw[i:i + n]
            i += n
        else:
            out.append(0x5F)
            i += 1
    return bytes(out)


def _hex4(value) -> str:
    return f"{int(str(value), 16):04x}" if value not in (None, "") else "0000"


def usb_serial_id(device: dict) -> str:
    """udev's ID_SERIAL (the usb_id builtin): <vendor>_<model>[_<serial>], each a USB string (iManufacturer,
    else the VID; iProduct, else the PID; iSerialNumber, dropped when it holds a control character, a comma or
    a non-ASCII one) cleaned as udev cleans it."""
    def field_(text: str | None, fallback: str, size: int) -> bytes:
        raw = (text or fallback).encode("utf-8", "surrogateescape")
        return _udev_chars(_udev_whitespace(raw, size))
    vendor = field_(device.get("manufacturer"), _hex4(device.get("vid")), 63)
    model = field_(device.get("product"), _hex4(device.get("pid")), 63)
    raw = str(device.get("serial") or "").encode("utf-8", "surrogateescape")
    serial = b"" if any(c < 0x20 or c > 0x7F or c == 0x2C for c in raw) else _udev_chars(_udev_whitespace(raw, 511))
    return (vendor + b"_" + model + (b"_" + serial if serial else b""))[:255].decode("utf-8", "replace")


def by_id_name(device: dict, tty: dict) -> str:
    """The /dev/serial/by-id name 60-serial.rules gives a tty: usb-<ID_SERIAL>-if<NN>, plus -port<P> for a
    usb-serial bridge's (FTDI, CP210x, CH34x, PL2303)."""
    nn = tty.get("if", 0)
    nn = f"{int(nn, 16) if isinstance(nn, str) else int(nn):02x}"
    port = tty.get("port")
    return f"usb-{usb_serial_id(device)}-if{nn}" + ("" if port is None else f"-port{int(port)}")


def console_tty(console: str, device: dict | None) -> dict | None:
    """The tty a slot's console is on: "usb", the device's first; "usb:NN", the one on interface NN."""
    ttys = (device or {}).get("ttys") or []
    if console == "usb":
        return ttys[0] if ttys else None
    if console.startswith("usb:"):
        return next((t for t in ttys if str(t.get("if", "")).lower() == console[4:]), None)
    return None


def console_path(console: str, device: dict | None) -> str | None:
    """The console's /dev/serial/by-id path on the CI host once the device is attached, or None (not a USB
    console, no device in the slot, no such tty, or its strings not read yet)."""
    tty = console_tty(console, device)
    if tty is None or device.get("strings") is False:
        return None
    return f"{BY_ID}/{by_id_name(device, tty)}"


# ------------------------------------------------------------------------- configuration

@dataclass
class Bay:
    id: str
    board: str                      # board family id (boards.yaml), "" when none is known
    name: str = ""                  # human name of the board
    platform: str | None = None     # Zephyr target, as twister names it
    runner: str | None = None       # west runner
    probe_id: str | None = None     # west flash --dev-id (probe serial number, or the esp32 port)
    console: str = "usb"            # "usb" (its USB's first tty), "usb:NN" (interface NN), "aux" (AUX UART), "none"
    serial: str | None = None       # console device on the CI host (stable /dev/serial/by-id/... path)
    baud: int = 115200
    host: str = ""
    http_port: int = 80
    aux_port: int = 4000            # raw AUX UART (twister serial_pty)
    rfc2217_port: int = 4001        # AUX UART with RFC 2217 (pyserial, labgrid, esptool)
    fixtures: list[str] = field(default_factory=list)
    ci: bool = True                 # false: keep this bay out of the hardware map
    choices: list[str] = field(default_factory=list)   # possible targets of a board family
    note: str = ""
    product: str | None = None      # twister `product` (openocd picks the probe by it: "STM32 STLink", ...)
    node: str = ""                  # a sub-slot's bay ("B3" for B3.2): the node that serves it
    slot: int | None = None         # a sub-slot's DATA ×4 port; None: the bay's one board
    multi: bool = False             # the node serves several boards (port-addressed control, /api/ports)
    role: str = ""                  # "": a board under test; "analyzer": the bay's logic analyzer (rackcfg.ROLES)
    reported: dict | None = None    # the slot as its node reports it (GET /api/boards); None: config/lab.yaml's only
    vacant: bool = False            # a DATA ×4 port with nothing known in it: no target, no device, no lab entry

    @property
    def node_id(self) -> str:
        return self.node or self.id

    @property
    def url(self) -> str:
        return f"http://{self.host}" + ("" if self.http_port == 80 else f":{self.http_port}")

    @property
    def device(self) -> dict | None:
        """The USB device in the slot now, as its node reports it."""
        return (self.reported or {}).get("device")

    @property
    def pinned(self) -> dict | None:
        """The device the slot's target was saved for: {vid, pid, serial}."""
        return (self.reported or {}).get("pinned")

    @property
    def mismatch(self) -> bool:
        """The device in the slot is not the one its target was saved for."""
        return bool((self.reported or {}).get("mismatch"))


def _yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


NODE_KEYS = ("host", "http_port", "aux_port", "rfc2217_port")     # lab keys a bay's sub-slots share
SLOT_KEYS = ("board", "platform", "runner", "id", "serial", "console", "baud", "ci", "fixtures", "product", "role")
CONSOLE = re.compile(r"(usb|usb:[0-9a-f]{2}|aux|none)$")
POSITION = re.compile(r"[A-Z][1-9]\d?$")                         # a bay's name: its row and place, B3


def _bay_key(bid: str):
    bay, n = rackcfg.split_slot(bid)
    return bay[0], int(bay[1:]) if bay[1:].isdigit() else 0, n or 0


def _resolves(host: str, timeout: float) -> bool:
    """Whether the name resolves within `timeout`: getaddrinfo has no timeout of its own, and an unanswered
    mDNS name (rack.local off the rack's network) takes it ten seconds."""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    found = threading.Event()

    def look():
        try:
            socket.getaddrinfo(host, None)
            found.set()
        except OSError:
            pass
    t = threading.Thread(target=look, daemon=True)
    t.start()
    t.join(timeout)
    return found.is_set()


def hub_address(lab_yaml: Path | None) -> str | None:
    """The power hub's host[:port]: BAYCTL_HUB, else lab.yaml `hub:`, else rack.<domain>; None for "none"."""
    lab = _yaml(lab_yaml if lab_yaml is not None else LAB_YAML)
    env = os.environ.get("BAYCTL_HUB", "").strip()
    if not env and lab.get("hub") is False:
        return None
    text = env or str(lab.get("hub") or "").strip() or f"rack.{lab.get('domain', 'local')}"
    return None if text.lower() in ("none", "off") else text


class Lab:
    """config/lab.yaml, optional overrides, and where the rack's nodes are (the hub's list, asked once)."""

    def __init__(self, path: Path | None = None, warnings: list[str] | None = None):
        self.path = path if path is not None else LAB_YAML
        self.doc = _yaml(self.path)
        self.domain = self.doc.get("domain", "local")
        self.bays = {str(k).upper(): v or {} for k, v in (self.doc.get("bays") or {}).items()}
        self.warnings = warnings if warnings is not None else []
        self._hub: dict[str, str] | None = None
        try:
            for k in self.bays:
                n = rackcfg.split_slot(k)[1]
                if n is not None and not 1 <= n <= rackcfg.MAX_SLOTS:
                    raise ValueError(f"{k}: a sub-slot is <bay>.<1-{rackcfg.MAX_SLOTS}>, a DATA ×4 port")
        except ValueError as e:
            raise BayError(f"config/lab.yaml: {e}") from None

    def warn(self, text: str) -> None:
        if text not in self.warnings:
            self.warnings.append(text)

    def nodes(self) -> set[str]:
        return {rackcfg.split_slot(k)[0] for k in self.bays}

    def subs(self, pos: str) -> list[str]:
        """The lab's sub-slot entries of a node, B3.1 ..."""
        return sorted((k for k in self.bays if "." in k and rackcfg.split_slot(k)[0] == pos), key=_bay_key)

    def hub_ips(self) -> dict[str, str]:
        """{position: address} of the nodes the hub lists; {} with a warning when it does not answer."""
        if self._hub is None:
            self._hub = {}
            if hub_address(self.path) is not None:
                hub = hub_device(self.path)
                if not _resolves(hub.host, HUB_TIMEOUT):
                    self.warn(f"hub {hub.host}: no such host (BAYCTL_HUB=host[:port] names it, BAYCTL_HUB=none "
                              f"skips it): config/lab.yaml's bays only")
                else:
                    try:
                        self._hub = {n.id.upper(): n.host for n in rack_nodes(hub, timeout=HUB_TIMEOUT)}
                    except BayError as e:
                        self.warn(f"{e}: config/lab.yaml's bays only")
        return self._hub

    def node(self, pos: str, ip: str | None = None) -> Bay:
        """A node, as a Bay for api(): the lab's `host:`, else the hub's address for it, else bay-<id>.<domain>."""
        over = self.bays.get(pos, {})
        return Bay(id=pos, board="bay-node", host=str(over.get("host") or ip or f"bay-{pos.lower()}.{self.domain}"),
                   http_port=int(over.get("http_port", self.doc.get("http_port", 80))),
                   aux_port=int(over.get("aux_port", self.doc.get("aux_port", 4000))),
                   rfc2217_port=int(over.get("rfc2217_port", self.doc.get("rfc2217_port", 4001))))

    def locate(self, pos: str) -> Bay:
        """A node by its position, the hub asked only when the lab gives no host."""
        ip = None if self.bays.get(pos, {}).get("host") else self.hub_ips().get(pos)
        return self.node(pos, ip)


def node_slots(node: Bay, timeout: float = NODE_TIMEOUT) -> list[dict]:
    """GET /api/boards: one record per slot, its target and the device in it.  A node without it (older
    firmware) gives its ports (GET /api/ports), no target."""
    try:
        return api(node, "/api/boards", timeout=timeout).get("slots", [])
    except BayError as e:
        if e.status != 404:
            raise
    return [{"slot": p.get("slot", node.id), "port": p.get("port", 1), "board": None, "console": "usb",
             "map": True, "pinned": None, "device": None, "mismatch": False, "present": bool(p.get("usb"))}
            for p in node_ports(node)]


def _read_slots(node: Bay, lab: Lab) -> list[dict] | None:
    """The node's slots, or None (with a warning) when it does not answer.  A device whose strings the node has
    not read yet (just enumerated) gets one more look a second later: its console's name needs them."""
    try:
        slots = node_slots(node)
        if any((s.get("device") or {}).get("strings") is False for s in slots):
            time.sleep(STRINGS_WAIT_S)
            slots = node_slots(node)
    except BayError as e:
        lab.warn(f"{e}: config/lab.yaml's entries only")
        return None
    for s in slots:
        if (s.get("device") or {}).get("strings") is False:
            lab.warn(f"{node.id}: port {s.get('port')}: the node has not read its device's USB strings yet: "
                     f"no console name (run again)")
    return slots


def _usb_ids(z: dict, platform: str | None) -> list[str]:
    return [*(((z.get("targets") or {}).get(platform) or {}).get("usb") or []), *(z.get("usb") or [])]


def _usb_match(patterns: list[str], device: dict | None) -> bool:
    if not device:
        return False
    vid, pid = _hex4(device.get("vid")), _hex4(device.get("pid"))
    for p in patterns:
        v, _, d = str(p).lower().partition(":")
        if v == vid and d in ("*", pid):
            return True
    return False


def family_of(platform: str | None, device: dict | None, families: dict) -> str | None:
    """The boards.yaml family of a Zephyr target: the one that names it (platform, choices, targets), else one
    with the same board name (nucleo_g474re/stm32g474xx); among several, the one whose `usb` ids the device shows."""
    if not platform:
        return None
    base = re.split(r"[/@]", platform)[0]
    exact, loose = [], []
    for fid, info in families.items():
        z = (info or {}).get("zephyr") or {}
        names = [x for x in (z.get("platform"), *(z.get("choices") or []), *(z.get("targets") or {})) if x]
        if platform in names:
            exact.append(fid)
        elif base in {re.split(r"[/@]", x)[0] for x in names}:
            loose.append(fid)
    found = exact or loose
    by_usb = [f for f in found if _usb_match(_usb_ids((families[f] or {}).get("zephyr") or {}, platform), device)]
    return (by_usb or found or [None])[0]


def _make_bay(sid: str, pos: str, n: int | None, multi: bool, s: dict | None, over: dict, node: Bay,
              families: dict, listed: bool = False) -> Bay:
    """One slot: config/lab.yaml's keys over what its node reports, over its family's defaults (boards.yaml)."""
    rep = s or {}
    role = over.get("role") or ""
    if role and role not in rackcfg.ROLES:
        raise BayError(f"bay {sid}: role {role!r}: {', '.join(rackcfg.ROLES)} (or none: a board under test)")
    if role and n is None:
        raise BayError(f"bay {sid}: `role` is a sub-slot's: an analyzer watches its neighbours")
    device = rep.get("device")
    platform = over.get("platform", rep.get("board"))
    family = over.get("board") or (None if role else family_of(platform, device, families))
    info = families.get(family, {}) if family else {}
    z = {} if role else info.get("zephyr") or {}    # an analyzer runs gusmanb's firmware, not tests
    if platform is None and not role:
        platform = z.get("platform")
    target = (z.get("targets") or {}).get(platform) or {}
    console = str(over.get("console") or rep.get("console") or ("usb" if n else z.get("console", "usb")))
    if not CONSOLE.match(console):
        raise BayError(f"bay {sid}: console must be usb, usb:<interface, 2 hex digits>, aux or none, not {console!r}")
    if n and console == "aux":
        raise BayError(f"bay {sid}: a sub-slot has no AUX UART: its console is the board's own USB")
    probe = over["id"] if over.get("id") is not None else rep.get("probe_id")
    vacant = bool(multi and s is not None and not rep.get("board") and not device and not rep.get("present")
                  and not listed)
    return Bay(
        id=sid, board=family or "", name=info.get("name") or platform or family or sid,
        platform=platform,
        runner=over.get("runner", rep.get("runner") or target.get("runner", z.get("runner"))),
        probe_id=str(probe) if probe is not None else None,
        console=console,
        serial=over.get("serial") or console_path(console, device),
        baud=int(over.get("baud", z.get("baud", 115200))),
        host=str(over.get("host", node.host)),
        http_port=int(over.get("http_port", node.http_port)),
        aux_port=int(over.get("aux_port", node.aux_port)),
        rfc2217_port=int(over.get("rfc2217_port", node.rfc2217_port)),
        fixtures=list(over.get("fixtures", [])),
        ci=bool(over.get("ci", rep.get("map", True) and not role)),
        choices=list(z.get("choices", [])),
        note=z.get("note", ""),
        product=over.get("product", z.get("product")),
        node=pos if n else "", slot=n, multi=multi, role=role, reported=s, vacant=vacant,
    )


def _node_bays(pos: str, node: Bay, slots: list[dict] | None, lab: Lab, families: dict) -> list[Bay]:
    """A node's boards: its slots as it reports them (named by position: B3, or B3.<port>), else the lab's
    entries for it, else one board named like the bay."""
    entry, subs = lab.bays.get(pos, {}), lab.subs(pos)
    own = [k for k in SLOT_KEYS if k in entry]
    if slots is not None:
        multi = len(slots) > 1 or any("." in str(s.get("slot", "")) for s in slots)
        items = {}
        for s in slots:
            n = int(s.get("port") or 1)
            items[f"{pos}.{n}" if multi else pos] = (n if multi else None, s)
        for k in subs:
            if k not in items:
                lab.warn(f"config/lab.yaml bays.{k}: node {pos} " +
                         (f"has no port {rackcfg.split_slot(k)[1]}" if multi else "holds one board") + ": left out")
        if multi and own:
            lab.warn(f"config/lab.yaml bays.{pos}: {pos} holds several boards ({', '.join(items)}): its "
                     f"{', '.join(own)} belong under bays.{pos}.<port>")
    else:
        multi = bool(subs)
        if multi and own:
            raise BayError(f"config/lab.yaml bays.{subs[0]}: bay {pos} holds one board (bays.{pos} sets its "
                           f"{', '.join(own)}): name each board {pos}.<port>, or drop the sub-slot entries")
        items = {k: (rackcfg.split_slot(k)[1], None) for k in subs} if multi else {pos: (None, None)}
    out = []
    for sid, (n, s) in items.items():
        if n is None:
            over = entry
        else:
            over = {**{k: v for k, v in entry.items() if k in NODE_KEYS}, **lab.bays.get(sid, {})}
        out.append(_make_bay(sid, pos, n, multi, s, over, node, families, listed=sid in lab.bays))
    return out


def load_bays(lab_yaml: Path | None = None, boards_yaml: Path = BOARDS_YAML, names: list[str] | None = None,
              live: bool = True, warnings: list[str] | None = None) -> dict[str, Bay]:
    """Every board under test (a node's one board, or each port of a DATA ×4 bay) in rack order: what the
    rack's nodes report (GET /api/boards), config/lab.yaml's keys over it, its family's defaults under it.
    A node is asked when the hub lists it or the lab gives its host; the lab's entries stand alone for the
    others.  `names`: only the nodes these bays are on; `live` False: the lab file alone (no network)."""
    lab = Lab(lab_yaml, warnings)
    families = _yaml(boards_yaml).get("boards", {}) or {}
    wanted = None
    if names is not None:
        try:
            wanted = {rackcfg.split_slot(x)[0] for x in names}
        except ValueError as e:
            raise BayError(str(e)) from None
    hub: dict[str, str] = {}
    if live and (wanted is None or any(not lab.bays.get(w, {}).get("host") for w in wanted)):
        hub = lab.hub_ips()
    known = set(hub) | lab.nodes()
    if wanted is None:
        positions = known
    else:                               # a bay nobody lists: its node by name (bay-<id>.<domain>)
        positions = {w for w in wanted if w in known or POSITION.match(w)}
    out: dict[str, Bay] = {}
    for pos in sorted(positions, key=_bay_key):
        node = lab.node(pos, hub.get(pos))
        slots = None
        if live and (pos in hub or lab.bays.get(pos, {}).get("host")):
            slots = _read_slots(node, lab)
        for b in _node_bays(pos, node, slots, lab, families):
            out[b.id] = b
    return out


SERVICES = ("status", "control", "console", "usbip", "shell", "camera")
SOURCE_NAME = re.compile(r"[A-Za-z0-9._-]{1,15}$")


def _services(value, where: str) -> list[str]:
    names = [value] if isinstance(value, str) else list(value or [])
    for n in names:
        if n != "all" and n not in SERVICES:
            raise BayError(f"{where}: unknown service {n!r} (one of: all, {', '.join(SERVICES)})")
    return names


def access_rules(lab_yaml: Path | None, bay_id: str) -> dict | None:
    """The node rules for a bay from config/lab.yaml `access:` (and `bays.<id>.access:`), or None.

        access:
          everyone: [status]
          sources:
            ci-runners: {cidr: 192.168.1.40/30, allow: [status, control, console, usbip]}
            ben-laptop: {cidr: 192.168.1.23, allow: [all]}
        bays:
          C1:
            access: {sources: {fabio-desk: {cidr: 192.168.1.66, allow: [all]}}}   # added for C1

    A bay's own `access:` adds sources (or replaces one of the same name) and may set
    `everyone` or `enabled`.
    """
    lab = _yaml(lab_yaml if lab_yaml is not None else LAB_YAML)
    rack = lab.get("access")
    bay = ((lab.get("bays") or {}).get(bay_id) or (lab.get("bays") or {}).get(bay_id.lower()) or {}).get("access")
    if rack is None and bay is None:
        return None
    merged = {"enabled": True, "everyone": ["status"], "sources": {}}
    for part, where in ((rack or {}, "access"), (bay or {}, f"bays.{bay_id}.access")):
        if "enabled" in part:
            merged["enabled"] = bool(part["enabled"])
        if "everyone" in part:
            merged["everyone"] = _services(part["everyone"], f"{where}.everyone")
        for name, src in (part.get("sources") or {}).items():
            name = str(name)
            if not SOURCE_NAME.match(name):
                raise BayError(f"{where}.sources: {name!r}: 1-15 letters, digits, '.', '_' or '-'")
            try:
                net = ipaddress.IPv4Network(str(src.get("cidr", "")), strict=False)
            except (ValueError, AttributeError):
                raise BayError(f"{where}.sources.{name}: cidr must be a.b.c.d or a.b.c.d/n") from None
            cidr = str(net.network_address) if net.prefixlen == 32 else str(net)
            merged["sources"][name] = {"name": name, "cidr": cidr,
                                       "allow": _services(src.get("allow", []), f"{where}.sources.{name}.allow")}
    if len(merged["sources"]) > 8:
        raise BayError(f"bay {bay_id}: {len(merged['sources'])} access sources, a node holds 8")
    return {**merged, "sources": list(merged["sources"].values())}


def admin_key() -> bytes:
    """The rack's admin key: BAYCTL_KEY, 64 hex digits (`bayctl access keygen` makes one)."""
    text = os.environ.get("BAYCTL_KEY", "").strip()
    if not text:
        raise BayError("set BAYCTL_KEY to the rack's admin key (a new one: bayctl access keygen)")
    try:
        key = bytes.fromhex(text)
    except ValueError:
        key = b""
    if len(key) != 32:
        raise BayError("BAYCTL_KEY must be 64 hex digits")
    return key


def sign(key: bytes, nonce: str, method: str, path: str, body: bytes) -> str:
    """X-Bay-Auth for an admin request (firmware src/access.c)."""
    mac = hmac.new(key, f"{nonce}\n{method}\n{path}\n".encode() + body, hashlib.sha256)
    return f"{nonce}:{mac.hexdigest()}"


def duration(text: str) -> int:
    """"90", "90s", "15m", "2h" -> seconds."""
    m = re.fullmatch(r"(\d+)\s*([smh]?)", str(text).strip())
    if not m:
        raise BayError(f"duration {text!r}: a number of seconds, or 15m, 2h")
    return int(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]


def get_bay(bays: dict[str, Bay], bid: str) -> Bay:
    """One board under test: a bay's one board ("A1") or a sub-slot ("B3.2")."""
    b = bays.get(bid.upper())
    if b is None:
        subs = [x.id for x in bays.values() if x.node == bid.upper()]
        if subs:
            raise BayError(f"bay {bid.upper()} holds several boards: say which ({', '.join(subs)})")
        raise BayError(f"unknown bay {bid!r} (known: {', '.join(bays)})")
    return b


def dut_targets(bays: dict[str, Bay], name: str, analyzers: bool = False) -> list[Bay]:
    """The boards a name covers: a sub-slot, a one-board bay, or every port of a DATA ×4 bay (with `analyzers`:
    its analyzer and its empty ports too; a whole bay's power is every port, its reset or attach its boards)."""
    subs = [x for x in bays.values() if x.node == name.upper()]
    if not subs:
        return [get_bay(bays, name)]
    if analyzers:
        return subs
    duts = [x for x in subs if not x.role and not x.vacant]
    if not duts:
        if any(x.role for x in subs):
            raise BayError(f"bay {name.upper()} holds only its analyzer: name it ({', '.join(x.id for x in subs)})")
        raise BayError(f"bay {name.upper()}: nothing in its ports (no target, no device): name one "
                       f"({', '.join(x.id for x in subs)})")
    return duts


def analyzer_info(rack_yaml: Path = RACK_YAML) -> dict:
    """config/rack.yaml › analyzer: the pinned gusmanb release, its firmware per board, its USB id.  The one
    section of rack.yaml bayctl reads (project data, as boards.yaml), only when a slot holds an analyzer."""
    return _yaml(rack_yaml).get("analyzer") or {}


def node_bay(bays: dict[str, Bay], name: str) -> Bay:
    """The node of a bay or of a sub-slot, as a Bay for api() (its id is the bay's)."""
    first = dut_targets(bays, rackcfg.split_slot(name)[0], analyzers=True)[0]
    return replace(first, id=first.node_id, node="", slot=None)


def nodes_of(bays: dict[str, Bay], names: list[str]) -> list[Bay]:
    """Each node once, in rack order: for the node's own commands (access, update)."""
    seen: dict[str, Bay] = {}
    for n in names or [b.id for b in bays.values()]:
        nb = node_bay(bays, n)
        seen.setdefault(nb.id, nb)
    return list(seen.values())


# ------------------------------------------------------------------------- node API

def api(bay: Bay, path: str, body: dict | None = None, timeout: float = 15.0, key: bytes | None = None,
        method: str | None = None) -> dict:
    """GET (body None) or POST (or `method`: PUT) a node endpoint; returns the JSON document.  With a key:
    signed (admin)."""
    data = None if body is None else json.dumps(body).encode()
    method = method or ("GET" if body is None else "POST")
    headers = {"Content-Type": "application/json"} if data else {}
    if key is not None:
        nonce = api(bay, "/api/access/nonce", timeout=timeout)["nonce"]
        headers["X-Bay-Auth"] = sign(key, nonce, method, path, data or b"")
    req = urllib.request.Request(bay.url + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error", e.reason)
        except Exception:
            msg = e.reason
        raise BayError(f"{bay.id}: {path}: {e.code} {msg}", e.code) from None
    except (urllib.error.URLError, OSError) as e:
        raise BayError(f"{bay.id}: cannot reach {bay.url} ({getattr(e, 'reason', e)})") from None


def wait_for(cond, timeout: float, step: float = 0.5) -> bool:
    end = time.monotonic() + timeout
    while True:
        if cond():
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(step)


# ------------------------------------------------------------------------- a node's ports

def node_ports(bay: Bay) -> list[dict]:
    """GET /api/ports: one object per port, `slot`, `port`, `hub_port`, `power`, `fault`, `usb`, `usbip`,
    `lease` (docs/multi-dut-node.md); a one-port node lists its DUT as port 1."""
    doc = api(bay, "/api/ports")
    return doc if isinstance(doc, list) else doc.get("ports", [])


def port_doc(bay: Bay) -> dict:
    """A sub-slot's port, from its node's /api/ports."""
    for port in node_ports(bay):
        if port.get("port") == bay.slot:
            return port
    raise BayError(f"{bay.id}: the node has no port {bay.slot} (is its DATA ×4 board connected?)")


def port_busid(port: dict) -> str:
    """The busid USB/IP exports a port's board under: the node's, else its place on the hub (1-1.<hub port>)."""
    usb = port.get("usb") or {}
    return usb.get("busid") or (f"1-1.{port['hub_port']}" if port.get("hub_port") else "1-1")


def control(bay: Bay, what: str, body: dict) -> dict:
    """POST power / reset / boot: a sub-slot's port, or the node's one DUT."""
    if bay.slot:
        return api(bay, f"/api/ports/{bay.slot}/{what}", body)
    return api(bay, f"/api/{what}", body)


# ------------------------------------------------------------------------- USB/IP (Linux)

def _usbip_cmd() -> list[str]:
    base = shlex.split(os.environ.get("BAYCTL_USBIP", "usbip"))
    if hasattr(os, "geteuid") and os.geteuid() != 0 and base[0] != "sudo":
        base = ["sudo", "-n", *base]
    return base


def _run(cmd: list[str], check: bool = True) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise BayError(f"{cmd[0]} not found (usbip: install linux-tools-generic / usbip)") from None
    if check and p.returncode != 0:
        raise BayError(f"{' '.join(cmd)}: {(p.stderr or p.stdout).strip()}")
    return p.stdout


def parse_usbip_list(text: str) -> list[tuple[str, str]]:
    """`usbip list -r host` -> [(busid, description)]."""
    out = []
    for line in text.splitlines():
        m = re.match(r"\s+(\d+-[\d.]+):\s+(.*)$", line)
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out


def parse_usbip_port(text: str) -> list[tuple[str, str, str]]:
    """`usbip port` -> [(port, remote host, remote busid)]."""
    out, port = [], None
    for line in text.splitlines():
        m = re.match(r"Port (\d+):", line.strip())
        if m:
            port = m.group(1)
            continue
        m = re.search(r"usbip://([^:/]+):\d+/(\S+)", line)
        if m and port is not None:
            out.append((port, m.group(1), m.group(2)))
    return out


def _same_host(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return socket.gethostbyname(a) == socket.gethostbyname(b)
    except OSError:
        return False


def imported_ports(bay: Bay, busid: str | None = None) -> list[str]:
    """This host's usbip ports imported from the bay's node (only that busid's, if given)."""
    return [p for p, h, b in parse_usbip_port(_run([*_usbip_cmd(), "port"], check=False))
            if _same_host(h, bay.host) and busid in (None, b)]


def serial_ids() -> set[str]:
    return {p.name for p in SERIAL_BY_ID.iterdir()} if SERIAL_BY_ID.is_dir() else set()


def attach(bay: Bay, wait: float = 10.0) -> list[str]:
    """Attach the board's exported device (a sub-slot's: its port's busid, from /api/ports); returns the
    /dev/serial/by-id entries that appeared."""
    if bay.slot:
        busid = port_busid(port_doc(bay))
        if imported_ports(bay, busid):
            return []
        exported = [b for b, _ in parse_usbip_list(_run([*_usbip_cmd(), "list", "-r", bay.host]))]
        if busid not in exported:
            raise BayError(f"{bay.id}: {busid} is not exported (is the board powered and enumerated?)")
    else:
        if imported_ports(bay):
            return []
        devices = parse_usbip_list(_run([*_usbip_cmd(), "list", "-r", bay.host]))
        if not devices:
            raise BayError(f"{bay.id}: the node exports no USB device (is the DUT powered and enumerated?)")
        busid = devices[0][0]
    before = serial_ids()
    _run([*_usbip_cmd(), "attach", "-r", bay.host, "-b", busid])
    wait_for(lambda: bool(serial_ids() - before), wait)
    time.sleep(1.0)                 # composite probes bring their interfaces up one by one
    return [str(SERIAL_BY_ID / n) for n in sorted(serial_ids() - before)]


def detach(bay: Bay) -> int:
    """Detach what this host imported from the board (a sub-slot: only its busid)."""
    ports = imported_ports(bay, port_busid(port_doc(bay)) if bay.slot else None)
    for p in ports:
        _run([*_usbip_cmd(), "detach", "-p", p])
    return len(ports)


def follow(targets: list[Bay], step: float = 2.0, say=print, stop: threading.Event | None = None) -> None:
    """Keep boards attached: a reset or a power cycle ends their USB/IP session, and each comes back under
    the same busid (docs/multi-dut-node.md); attach it again then.  Until Ctrl-C, or `stop`."""
    while stop is None or not stop.is_set():
        for b in targets:
            try:
                new = attach(b)
            except BayError:
                continue                    # not back yet
            if new:
                say(f"{b.id}: attached, {', '.join(new)}")
        if stop is not None:
            stop.wait(step)
        else:
            time.sleep(step)


# ------------------------------------------------------------------------- consoles

def pty_bridge(bay: Bay) -> None:
    """Copy stdin -> the AUX UART's TCP port and back to stdout, raw bytes (twister `serial_pty`)."""
    sock = socket.create_connection((bay.host, bay.aux_port), timeout=10)
    sock.settimeout(None)
    done = threading.Event()

    def up():
        try:
            while not done.is_set():
                data = os.read(0, 4096)
                if not data:
                    break
                sock.sendall(data)
        except OSError:
            pass
        done.set()

    threading.Thread(target=up, daemon=True).start()
    try:
        while not done.is_set():
            data = sock.recv(4096)
            if not data:
                break
            os.write(1, data)
    except OSError:
        pass
    finally:
        done.set()
        sock.close()


# ------------------------------------------------------------------------- access control

def lease(bay: Bay, seconds: int, note: str = "") -> dict:
    """Reserve (or renew) the bay, or one sub-slot, for this host; BayError (423) while another host holds it."""
    body = {"ttl_s": seconds, "note": note}
    if bay.slot:
        body["ports"] = [bay.id]
    return api(bay, "/api/lease", body)


def release(bay: Bay, force: bool = False) -> dict:
    body = {"release": True}
    if bay.slot:
        body["ports"] = [bay.id]
    return api(bay, "/api/lease", body, key=admin_key() if force else None)


def lease_left(bay: Bay, doc: dict) -> int:
    """Seconds left on the bay's lease, or on the sub-slot's."""
    if bay.slot:
        return next(((p.get("lease") or {}).get("remaining_s", 0) for p in doc.get("ports", [])
                     if p.get("slot") == bay.id), 0)
    return (doc.get("lease") or {}).get("remaining_s", 0)


def access_push(bay: Bay, rules: dict, key: bytes) -> str:
    """Write the rules to a node: "updated", "unchanged" or "not claimed"."""
    doc = api(bay, "/api/access", key=key if _claimed(bay) else None)
    if not doc.get("claimed"):
        return "not claimed"
    current = {"enabled": doc["enabled"], **doc["rules"]}
    if _same_rules(current, rules):
        return "unchanged"
    api(bay, "/api/access/rules", rules, key=key)
    return "updated"


def _claimed(bay: Bay) -> bool:
    return bool(api(bay, "/api/status").get("access", {}).get("claimed"))


def _norm(allow: list[str]) -> list[str]:
    return list(SERVICES) if "all" in allow else sorted(allow, key=SERVICES.index)


def _same_rules(a: dict, b: dict) -> bool:
    def norm(r):
        return (bool(r.get("enabled")), _norm(r.get("everyone", [])),
                sorted((s["name"], s["cidr"], tuple(_norm(s["allow"]))) for s in r.get("sources", [])))
    return norm(a) == norm(b)


def access_claim(bay: Bay, key: bytes, timeout: float = 70.0, say=print) -> None:
    """Give an unclaimed node the rack's key: someone presses its BOOT button."""
    start = api(bay, "/api/access/claim", {"key": key.hex()})
    say(f"{bay.id}: press BOOT on bay {bay.id} (its LED blinks white) within {start['remaining_s']} s")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = api(bay, "/api/access/claim", {"ticket": start["ticket"]})
        if r["state"] == "done":
            return
        time.sleep(1.0)
    raise BayError(f"{bay.id}: nobody pressed BOOT in time")


# ------------------------------------------------------------------------- firmware updates

def image_info(data: bytes) -> dict:
    """Version and image id of a signed image (zephyr.signed.bin), as the firmware reads it
    (firmware/common/lib/mcuboot_img.c); BayError if it is not one."""
    import struct
    if len(data) < 32 or struct.unpack_from("<I", data)[0] != 0x96F3B83D:
        raise BayError("not a signed image: zephyr.signed.bin from a `west build --sysbuild`")
    hdr, prot, size = struct.unpack_from("<HHI", data, 8)
    major, minor, rev, build = struct.unpack_from("<BBHI", data, 20)
    tlv = hdr + size + prot
    if tlv + 4 > len(data) or struct.unpack_from("<H", data, tlv)[0] != 0x6907 \
            or tlv + struct.unpack_from("<H", data, tlv + 2)[0] != len(data):
        raise BayError("image truncated, or bytes after it")
    image_id, o = "", hdr + size + 4
    while prot and o + 4 <= hdr + size + prot:
        kind, n = struct.unpack_from("<HH", data, o)
        if kind == 0xA0:
            image_id = data[o + 4:o + 4 + n].decode()
        o += 4 + n
    if not image_id:
        raise BayError("no image id: not built from this repository (firmware/common/sysbuild.cmake)")
    return {"version": f"{major}.{minor}.{rev}" + (f"+{build}" if build else ""), "id": image_id}


def hub_device(lab_yaml: Path | None) -> Bay:
    """The power hub, as a Bay for api(): BAYCTL_HUB (host or host:port), else lab.yaml `hub:`, else
    rack.<domain>."""
    host = hub_address(lab_yaml)
    if host is None:
        raise BayError("no hub: BAYCTL_HUB (or lab.yaml `hub:`) says none")
    name, _, port = host.partition(":")
    return Bay(id="hub", board="power-hub", host=name, http_port=int(port or 80))


def rack_nodes(hub: Bay, timeout: float = 15.0) -> list[Bay]:
    """The bay nodes the hub lists on its rack bus (/api/status), addressed by IP, named by position."""
    s = api(hub, "/api/status", timeout=timeout)
    out = []
    for row in s.get("rows", []):
        for n in row.get("nodes", []):
            if n.get("ip", "0.0.0.0") != "0.0.0.0" and n.get("state") not in ("lost", "failed", "incompatible"):
                out.append(Bay(id=n["pos"], board="bay-node", host=n["ip"]))
    return out


HUB_NODE_ACTIONS = ("identify", "reset", "bootloader", "power-cycle", "power-on", "power-off", "reboot")


def hub_node_id(target: str) -> int:
    """Resolve a bay position ("A1", "C3") or node address ("0x23", "35") to a CAN node id."""
    text = str(target).strip()
    m = re.fullmatch(r"([A-Da-d])([1-9]\d*)", text)
    if m:
        pos = int(m.group(2))
        if 1 <= pos <= 15:
            return ("ABCD".index(m.group(1).upper()) << 4) | pos
    try:
        nid = int(text, 0)
        if 1 <= nid <= 0x3F and (nid & 0x0F) != 0:
            return nid
    except ValueError:
        pass
    raise BayError(f"node {target!r}: expected a bay position (A1..D15) or node id (0x01..0x3f)")


def _print_hub_row(r: dict) -> None:
    if r.get("state") == "absent":
        print(f"row {r.get('name', '?')}  not fitted")
        return
    state = r.get("state", "on" if r.get("on") else "off").upper()
    nodes = " ".join(f"{n.get('pos', '?')}({n.get('state', '?')} {n.get('dut_ma', 0)}mA)"
                     for n in r.get("nodes", []))
    faults = f" [faults:{r['faults']}]" if r.get("faults") else ""
    print(f"row {r.get('name', '?')}  {state:7}  {r.get('ma', 0):4} mA  {r.get('mw', 0) / 1000:5.1f} W"
          f"{faults}" + (f"  {nodes}" if nodes else ""))


def _print_hub_status(s: dict) -> None:
    pd = s.get("pd") or {}
    c = pd.get("contract")
    budget = s.get("budget") or {}
    can = s.get("can") or {}
    if c:
        pd_str = (f"PD {c.get('mv', 0) / 1000:.1f} V / {c.get('ma', 0) / 1000:.2f} A"
                  + (" EPR" if c.get("epr") else "")
                  + f" (used {budget.get('used_mw', 0) / 1000:.1f} W / {budget.get('limit_mw', 0) / 1000:.1f} W budget)")
    else:
        pd_str = f"PD {pd.get('state', 'usb')} (no contract)"
    shed = f"  SHED:{budget['shed']}" if budget.get("shed") else ""
    print(f"{s.get('hostname', 'hub')}  {s.get('ip', '')}  {pd_str}{shed}  "
          f"CAN {can.get('nodes', 0)} nodes ({can.get('lost', 0)} lost)")
    for r in s.get("rows", []):
        _print_hub_row(r)


def _print_hub_events(events: list[dict]) -> None:
    if not events:
        print("no events")
        return
    for e in events:
        print(f"  {e.get('age_s', 0):5}s  {e.get('kind', '?'):8}  {e.get('text', '')}")


def hub_cli(a: argparse.Namespace) -> int:
    hub = hub_device(a.lab)
    cmd = a.hub_cmd or "status"
    if cmd == "status":
        _print_hub_status(api(hub, "/api/status"))
    elif cmd == "events":
        _print_hub_events(api(hub, "/api/events"))
    elif cmd == "enumerate":
        _print_hub_status(api(hub, "/api/enumerate", {}, key=admin_key()))
    elif cmd == "pd":
        _print_hub_status(api(hub, "/api/pd", {"pref": a.pref}, key=admin_key()))
    elif cmd == "node":
        nid = hub_node_id(a.target)
        api(hub, "/api/node", {"id": nid, "action": a.action}, key=admin_key())
        print(f"hub: node 0x{nid:02x} ({'ABCD'[nid >> 4]}{nid & 15}): {a.action}")
    elif cmd == "claim":
        access_claim(hub, admin_key())
        print("hub: claimed")
    return 0


def _post_image(dev: Bay, ticket: str, data: bytes, timeout: float) -> dict:
    req = urllib.request.Request(f"{dev.url}/api/update?ticket={ticket}", data=data, method="POST",
                                 headers={"Content-Type": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error", e.reason)
        except Exception:
            msg = e.reason
        raise BayError(f"{dev.id}: upload refused: {msg}") from None
    except (urllib.error.URLError, OSError) as e:
        raise BayError(f"{dev.id}: upload cut off ({getattr(e, 'reason', e)})") from None


def update_device(dev: Bay, data: bytes, key: bytes, force: bool = False, timeout: float = 420.0,
                  say=print, step: float = 2.0) -> str:
    """Update one node or the hub: check, send, then follow the restart and the trial.
    Returns "confirmed"; BayError if refused, rolled back or never back."""
    info = image_info(data)
    now = api(dev, "/api/update")
    if now.get("id") != info["id"]:
        raise BayError(f"{dev.id}: this image is for {info['id']}; {dev.id} runs {now.get('id')}")
    if now.get("trial"):
        raise BayError(f"{dev.id}: {now['version']} is on trial: wait until it confirms itself")
    t0 = time.monotonic()
    begun = api(dev, "/api/update/begin", {"size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                                            "force": force}, key=key)
    r = _post_image(dev, begun["ticket"], data, timeout=120)
    say(f"{dev.id}: {now['version']} -> {r['version']}: sent {len(data) // 1024} KB in "
        f"{time.monotonic() - t0:.0f} s, restarting")
    deadline, back, last_note = time.monotonic() + timeout, False, ""
    while time.monotonic() < deadline:
        time.sleep(step)
        try:
            s = api(dev, "/api/update", timeout=4)
        except BayError:
            continue
        if s.get("state") == "rebooting":
            continue
        if not back:
            back = True
            say(f"{dev.id}: back after {time.monotonic() - t0:.0f} s, running {s['version']}")
        t = s.get("trial")
        if t:
            missing = [n for n in t["need"] if n not in t["up"]]
            note = f"on trial, waiting for {' and '.join(missing)}" if missing else "on trial, confirming"
            if note != last_note:
                say(f"{dev.id}: {note} ({t['left_s']} s left)")
                last_note = note
            continue
        result = (s.get("last") or {}).get("result")
        if result == "confirmed":
            say(f"{dev.id}: {s['version']} confirmed itself ({time.monotonic() - t0:.0f} s)")
            return "confirmed"
        raise BayError(f"{dev.id}: {r['version']} did not stay: MCUboot went back, running {s['version']}")
    raise BayError(f"{dev.id}: not back after {timeout:.0f} s: check it (USB console, or the hub's page)")


def update_cli(a: argparse.Namespace, bays: dict[str, Bay]) -> int:
    data = a.image.read_bytes()
    info = image_info(data)
    key = admin_key()
    if a.hub:
        targets = [hub_device(a.lab)]
    elif a.all:
        targets = rack_nodes(hub_device(a.lab))
        if not targets:
            raise BayError("the hub lists no bay node")
    else:
        if not a.bays:
            raise BayError("which bays? (or --all, or --hub)")
        targets = nodes_of(bays, a.bays)
    print(f"{info['id']} {info['version']}: {', '.join(t.id for t in targets)}")
    done, skipped = [], []
    for dev in targets:
        try:
            update_device(dev, data, key, force=a.force, timeout=a.timeout)
            done.append(dev.id)
        except BayError as e:
            msg = str(e)
            if "did not stay" in msg or "not back" in msg:
                # Do not take a firmware that fails on one node to the next ones
                print(f"bayctl: {msg}", file=sys.stderr)
                rest = [t.id for t in targets[targets.index(dev) + 1:]]
                if rest:
                    print(f"bayctl: stopped; not updated: {', '.join(rest)}", file=sys.stderr)
                return 1
            print(f"bayctl: {msg}; skipped", file=sys.stderr)
            skipped.append(dev.id)
    print(f"updated: {', '.join(done) or 'none'}" + (f"; skipped: {', '.join(skipped)}" if skipped else ""))
    return 1 if skipped else 0


def _print_access(d: dict) -> None:
    lease_ = d.get("lease")
    print(f"you {d['you']}{' (' + d['source'] + ')' if d.get('source') else ''}: {', '.join(d['allow']) or 'nothing'}"
          f"{'  [admin]' if d.get('admin') else ''}")
    print(f"claimed: {'yes' if d['claimed'] else 'no'}, rules {'on' if d['enabled'] else 'off'}")
    if "rules" in d:
        for s_ in d["rules"]["sources"]:
            print(f"  {s_['name']:16} {s_['cidr']:19} {', '.join(s_['allow'])}")
        print(f"  {'everyone else':16} {'':19} {', '.join(d['rules']['everyone']) or '-'}")
    print("lease: " + (f"{lease_['holder']}{' (' + lease_['note'] + ')' if lease_['note'] else ''}, "
                       f"{lease_['remaining_s']} s left" if lease_ else "none"))
    for c in d.get("connections", []):
        peer = f"{c['peer']}:{c['port']}" if c["port"] else c["peer"]
        print(f"  {c['id']:14} {c['label']:12} {peer:22} {c['since_s']} s")
    print(f"refused: {d['refused_total']}")
    for r in d.get("refused", []):
        print(f"  {r['ip']:15} {r['service']:8} {r['reason']:12} x{r['count']}, last {r['last_s']} s ago")


# ------------------------------------------------------------------------- test-framework configs

def _target_or_error(bay: Bay) -> str:
    if bay.platform:
        return bay.platform
    hint = f" (one of: {', '.join(bay.choices)})" if bay.choices else ""
    where = f"set its board target on the node's page ({bay.url}/), or " if bay.reported is not None else "set "
    dev = _device_text(bay.device)
    raise BayError(f"bay {bay.id} ({dev or bay.name}): no board target: {where}bays.{bay.id}.platform in "
                   f"config/lab.yaml{hint}")


def _device_text(dev: dict | None) -> str:
    if not dev:
        return ""
    return f"{_hex4(dev.get('vid'))}:{_hex4(dev.get('pid'))}" + (f" {dev['product']}" if dev.get("product") else "")


def flash_id(bay: Bay) -> str | None:
    """twister's `id` (west flash --dev-id, --esp-device, ...): the slot's probe id, else its serial port for the
    esp32 runner, else the USB serial number of the device in the slot (or of the one its target was saved for)."""
    if bay.probe_id:
        return bay.probe_id
    if bay.runner == "esp32":
        return bay.serial
    return (bay.device or {}).get("serial") or (bay.pinned or {}).get("serial") or None


def _no_console(bay: Bay) -> str:
    """Why a USB console has no path, and what to do."""
    fix = f"or set bays.{bay.id}.serial in config/lab.yaml"
    if bay.console == "none":
        return "console none: no console, kept out of the tests (connected: false)"
    if bay.reported is None:
        return (f"no console path; attach it (`bayctl attach {bay.id} --show`) and set bays.{bay.id}.serial in "
                f"config/lab.yaml, or console: aux")
    dev = bay.device
    if not dev:
        return f"no USB device in the slot now (powered off?): no console path; power it on and run hwmap again, {fix}"
    if dev.get("strings") is False:
        return f"the node has not read the strings of {_device_text(dev)} yet: no console path; run hwmap again, {fix}"
    ifs = ", ".join(f"if{t.get('if')}" for t in dev.get("ttys") or [])
    if bay.console == "usb":
        return (f"{_device_text(dev)} has no serial port: pick its console on the node's page (usb:NN, aux, none), "
                f"{fix}")
    return f"{_device_text(dev)} has no serial port on interface {bay.console[4:]} ({ifs or 'none'}), {fix}"


def hwmap(bays: dict[str, Bay], scripts_dir: Path, python: str, bayctl: str, lab: Path | None,
          power_cycle: bool = False, lease_for: str | None = None) -> tuple[list[dict], list[str]]:
    """Twister hardware map entries (+ writes one pre-script per bay); returns (entries, warnings)."""
    entries, warnings = [], []
    no_id: dict[str, list[str]] = {}            # runner -> bays without a probe id
    scripts_dir.mkdir(parents=True, exist_ok=True)
    lab_arg = f" --lab {shlex.quote(str(lab))}" if lab else ""
    for bay in bays.values():
        if not bay.ci or bay.role or bay.vacant:    # an analyzer is no test target, whatever its `ci`
            continue
        try:
            platform = _target_or_error(bay)
        except BayError as e:
            warnings.append(str(e))
            continue
        if bay.mismatch:
            pin = bay.pinned or {}
            warnings.append(f"bay {bay.id}: {_device_text(bay.device)} S/N {(bay.device or {}).get('serial') or '-'} "
                            f"is not the board its target was saved for ({_hex4(pin.get('vid'))}:"
                            f"{_hex4(pin.get('pid'))} S/N {pin.get('serial') or '-'}): check it, then save its target "
                            f"again on the node's page")
        tag = bay.id.lower().replace(".", "-")
        pre = scripts_dir / f"bay-{tag}-pre.sh"
        pre.write_text(
            "#!/bin/sh\n"
            f"# Generated by tools/bayctl.py hwmap: bay {bay.id} ({bay.name}) before each test.\n"
            f"exec {shlex.quote(python)} {shlex.quote(bayctl)}{lab_arg} prepare {bay.id}"
            + (" --power-cycle" if power_cycle else "")
            + (f" --lease {shlex.quote(lease_for)}" if lease_for else "") + "\n",
            encoding="utf-8", newline="\n")
        scripts = [pre]
        if lease_for:
            post = scripts_dir / f"bay-{tag}-post.sh"
            post.write_text(
                "#!/bin/sh\n"
                f"# Generated by tools/bayctl.py hwmap: bay {bay.id} after each test.\n"
                f"exec {shlex.quote(python)} {shlex.quote(bayctl)}{lab_arg} release {bay.id}\n",
                encoding="utf-8", newline="\n")
            scripts.append(post)
        for script in scripts:
            try:
                script.chmod(0o755)
            except OSError:
                pass
        e: dict = {"connected": True, "platform": platform, "product": bay.product or f"{bay.name} (bay {bay.id})"}
        if bay.runner:
            e["runner"] = bay.runner
        probe_id = flash_id(bay)
        if probe_id:
            e["id"] = probe_id
        if bay.console == "aux":
            # twister splits serial_pty on spaces and commas: keep these paths free of both
            e["serial_pty"] = f"{python} {bayctl}{lab_arg} pty {bay.id}"
        elif bay.serial and bay.console != "none":
            e["serial"] = bay.serial
        else:
            e["connected"] = False
            warnings.append(f"bay {bay.id}: {_no_console(bay)}")
        if not probe_id:
            no_id.setdefault(bay.runner or "default", []).append(bay.id)
        e["baud"] = bay.baud
        e["pre_script"] = str(pre)
        if lease_for:
            e["post_script"] = str(scripts[1])
        e["script_param"] = {"pre_script_timeout": 90}
        e["fixtures"] = [f"bay:{bay.id}", *([f"node:{bay.node}"] if bay.slot else []), *bay.fixtures]
        if bay.note:
            warnings.append(f"bay {bay.id}: {bay.note}")
        entries.append(e)
    for runner, ids in no_id.items():
        if len(ids) > 1:            # every bay gets attached to the CI host: the runner must pick one
            warnings.append(f"bays {', '.join(ids)} use {runner} without a probe id: set its probe id on the node's "
                            f"page or bays.<id>.id (`bayctl attach <bay> --show`), or flashing may hit the wrong board")
    return entries, warnings


def pdu_bays(bays: dict[str, Bay]) -> list[Bay]:
    """The boards a PDU port each, in rack order (empty DATA ×4 ports left out): export pdudaemon, power-port."""
    return [b for b in bays.values() if not b.vacant]


def export_labgrid(bays: dict[str, Bay], python: str, bayctl: str) -> dict:
    targets = {}
    for bay in pdu_bays(bays):
        run = f"{python} {bayctl}"
        drivers = {"ExternalPowerDriver": {"cmd_on": f"{run} power {bay.id} on", "cmd_off": f"{run} power {bay.id} off",
                                           "cmd_cycle": f"{run} power {bay.id} cycle"}}
        res = {}
        if not bay.slot:                # a sub-slot has no AUX UART: its console is its own USB, once attached
            res = {"NetworkSerialPort": {"host": bay.host, "port": bay.rfc2217_port, "speed": bay.baud,
                                         "protocol": "rfc2217"}}
            drivers["SerialDriver"] = {}
        targets[f"bay-{bay.id.lower().replace('.', '-')}"] = {"resources": res, "drivers": drivers}
    return {"targets": targets}


def export_pdudaemon(bays: dict[str, Bay], python: str, bayctl: str) -> dict:
    """One PDU, one port per board under test (1-based, in rack order): LAVA addresses a DUT as (pdu, port)."""
    run = f"{python} {bayctl}"
    return {
        "daemon": {"hostname": "0.0.0.0", "port": 16421, "listener": "http", "logging_level": "INFO"},
        "pdus": {"hw-testing-rack": {"driver": "localcmdline",
                                     "cmd_on": f"{run} power-port %d on",
                                     "cmd_off": f"{run} power-port %d off"}},
        "_ports": {i + 1: bay.id for i, bay in enumerate(pdu_bays(bays))},
    }


def export_lab(bays: dict[str, Bay]) -> dict:
    """The board targets the nodes hold, as config/lab.yaml entries (`import lab` puts them back): platform,
    runner, id (the probe id), console, ci: false (out of the map) and the device each is pinned to."""
    out = {}
    for b in bays.values():
        s = b.reported or {}
        if not s.get("board"):
            continue
        e: dict = {"platform": s["board"]}
        if s.get("runner"):
            e["runner"] = s["runner"]
        if s.get("probe_id"):
            e["id"] = str(s["probe_id"])
        if (s.get("console") or "usb") != "usb":
            e["console"] = s["console"]
        if s.get("map") is False:
            e["ci"] = False
        if s.get("pinned"):
            p = s["pinned"]
            e["pin"] = {"vid": _hex4(p.get("vid")), "pid": _hex4(p.get("pid")), "serial": p.get("serial")}
        out[b.id] = e
    return {"bays": out}


def board_body(entry: dict, where: str) -> dict:
    """PUT /api/ports/<n>/board's body from a lab entry (export lab's form).  Without a `pin` the node pins the
    target to the device in the slot now."""
    if not entry.get("platform"):
        raise BayError(f"{where}: no platform: nothing to put on the node")
    body = {"board": str(entry["platform"]), "runner": entry.get("runner") or None,
            "probe_id": str(entry["id"]) if entry.get("id") is not None else None,
            "console": str(entry.get("console") or "usb"), "map": bool(entry.get("ci", True))}
    pin = entry.get("pin")
    if pin:
        if not isinstance(pin, dict) or not pin.get("vid") or not pin.get("pid"):
            raise BayError(f"{where}.pin: {{vid: \"0483\", pid: \"374b\", serial: ...}} (quote the ids)")
        body["pin"] = {"vid": _hex4(pin["vid"]), "pid": _hex4(pin["pid"]),
                       "serial": str(pin["serial"]) if pin.get("serial") is not None else None}
    return body


def import_lab(path: Path, names: list[str], lab: Lab, say=print) -> int:
    """Write a lab file's targets (export lab's, or any lab.yaml with `platform:`) to the nodes; returns how many
    failed.  `names`: only these slots (B3.2) or bays (B3: its slots)."""
    doc = _yaml(path)
    if not doc and not path.exists():
        raise BayError(f"{path}: no such file")
    entries = {str(k).upper(): v or {} for k, v in (doc.get("bays") or {}).items()}
    try:
        wanted = [rackcfg.split_slot(n) for n in names]
        picked = {k: e for k, e in entries.items()
                  if not wanted or any(rackcfg.split_slot(k) == w or (w[1] is None and rackcfg.split_slot(k)[0] == w[0])
                                       for w in wanted)}
    except ValueError as e:
        raise BayError(f"{path}: {e}") from None
    for n in names:
        bay, sub = rackcfg.split_slot(n)
        if not any(k == n.upper() or (sub is None and rackcfg.split_slot(k)[0] == bay) for k in entries):
            raise BayError(f"{path}: no entry for {n.upper()}")
    if not wanted:
        picked = {k: e for k, e in picked.items() if e.get("platform")}    # a lab file's other entries: overrides
    failed = 0
    for sid in sorted(picked, key=_bay_key):
        pos, n = rackcfg.split_slot(sid)
        try:
            body = board_body(picked[sid], f"{path.name} bays.{sid}")
            r = api(lab.locate(pos), f"/api/ports/{n or 1}/board", body, method="PUT")
        except BayError as e:
            say(f"{sid}: {e}")
            failed += 1
            continue
        pin = r.get("pinned") or {}
        say(f"{sid}: {r.get('board')}" + (f" (runner {r['runner']})" if r.get("runner") else "")
            + (f", pinned to {pin.get('vid')}:{pin.get('pid')} S/N {pin.get('serial') or '-'}" if pin else ", no pin"))
    return failed


# ------------------------------------------------------------------------- CLI

def _print_status(s: dict) -> None:
    dut, usb = s.get("dut", {}), s.get("usb", {})
    state = "FAULT" if dut.get("fault") or dut.get("latched") else ("on" if dut.get("on") else "off")
    print(f"{s.get('hostname', '?')}  {s.get('ip', '')}  path {s.get('path', '?')}  "
          f"VBUS {state} {dut.get('mv', 0) / 1000:.2f} V {dut.get('ma', 0)} mA  "
          f"USB devices {usb.get('devices', 0)}, USB/IP sessions {usb.get('sessions', 0)}")


def _print_port(p: dict) -> None:
    pw, usb, client = p.get("power") or {}, p.get("usb"), p.get("usbip")
    state = "FAULT" if p.get("fault") else ("on" if pw.get("on") else "off")
    dev = (f"{usb.get('vid', '?')}:{usb.get('pid', '?')} {usb.get('product', '')}  busid {port_busid(p)}"
           if usb else "no USB device")
    print(f"{p.get('slot', '?'):6} port {p.get('port')}  VBUS {state} {pw.get('ma', 0)} mA  {dev}"
          + (f"  USB/IP {client.get('client')}" if client else ""))


def _print_usb(bay: Bay) -> None:
    """GET /api/usb: one line per USB device, its name, maker, serial and USB/IP client."""
    try:
        doc = api(bay, "/api/usb", timeout=5)
    except BayError:
        return                                  # a node without /api/usb (older firmware)
    hub = doc.get("hub")
    if hub:
        print(f"USB hub {hub.get('vid')}:{hub.get('pid')} {hub.get('name', '')}")
    for d in doc.get("devices", []):
        who = (d.get("usbip") or {}).get("client")
        line = f"  {d.get('busid', '?'):8} {d.get('slot', ''):6} {d.get('vid')}:{d.get('pid')}  {d.get('name', '')}"
        if d.get("manufacturer"):
            line += f" ({d['manufacturer']})"
        if d.get("serial"):
            line += f"  S/N {d['serial']}"
        if d.get("classes"):
            line += f"  [{', '.join(d['classes'])}]"
        print(line + (f"  USB/IP {who}" if who else ""))


def analyzer_state(usb: dict | None, la: dict) -> str:
    """What an analyzer's port holds: gusmanb's firmware, the ROM's BOOTSEL, something else, or nothing."""
    if not usb:
        return "no USB device"
    vid_pid = f"{usb.get('vid', '')}:{usb.get('pid', '')}".lower().replace("0x", "")
    if vid_pid == str(la.get("usb", "1209:3020")).lower():
        return "LogicAnalyzer"
    if vid_pid in ("2e8a:000f", "2e8a:0003"):          # RP2350, RP2040 BOOTSEL: flash it (docs/multi-dut-node.md)
        return "BOOTSEL"
    return f"{vid_pid}: not the analyzer's firmware"


def _print_control(bay: Bay, r: dict) -> None:
    (_print_port if bay.slot else _print_status)(r)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bayctl", description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lab", type=Path, default=Path(os.environ.get("BAYCTL_LAB", LAB_YAML)),
                    help="per-installation file (default config/lab.yaml)")
    ap.add_argument("--rack", type=Path, default=RACK_YAML, help=argparse.SUPPRESS)   # its `analyzer:` only
    ap.add_argument("--boards", type=Path, default=BOARDS_YAML, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("--probe", action="store_true", help="also query every node")
    sub.add_parser("status").add_argument("bay")
    sub.add_parser("ports").add_argument("bay")
    p = sub.add_parser("power")
    p.add_argument("bay")
    p.add_argument("action", choices=["on", "off", "cycle"])
    p.add_argument("--ms", type=int, default=1000)
    p = sub.add_parser("power-port", help=argparse.SUPPRESS)       # PDUDaemon: port number instead of bay id
    p.add_argument("port", type=int)
    p.add_argument("action", choices=["on", "off", "cycle"])
    p = sub.add_parser("reset")
    p.add_argument("bay")
    p.add_argument("--ms", type=int, default=100)
    p = sub.add_parser("boot")
    p.add_argument("bay")
    p.add_argument("--power-cycle", action="store_true",
                   help="a sub-slot: BOOT held across a power cycle of its port instead of a RESET pulse (a "
                        "board whose RESET is not wired: the analyzer's BOOTSEL)")
    p = sub.add_parser("mode")
    p.add_argument("bay")
    p.add_argument("mode", choices=["usbip", "classic"])
    p = sub.add_parser("attach")
    p.add_argument("bay")
    p.add_argument("--show", action="store_true", help="print the serial devices that appeared")
    p.add_argument("--follow", action="store_true", help="stay, and attach again after each reset (Ctrl-C to stop)")
    sub.add_parser("detach").add_argument("bay")
    p = sub.add_parser("prepare")
    p.add_argument("bay")
    p.add_argument("--power-cycle", action="store_true")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--lease", metavar="DURATION", help="reserve (or renew) the bay for this host first: 30m, 2h")
    sub.add_parser("pty").add_argument("bay")
    p = sub.add_parser("hwmap")
    p.add_argument("-o", "--out", type=Path, default=Path("rack-map.yaml"))
    p.add_argument("--scripts", type=Path, default=None, help="pre-script folder (default: next to the map)")
    p.add_argument("--python", default=sys.executable or "python3")
    p.add_argument("--power-cycle", action="store_true", help="power-cycle the DUT before every test")
    p.add_argument("--lease", metavar="DURATION",
                   help="each test reserves its bay for this long (pre-script) and releases it (post-script)")
    p = sub.add_parser("export")
    p.add_argument("what", choices=["labgrid", "pdudaemon", "lab"])
    p.add_argument("--python", default="python3")
    p.add_argument("-o", "--out", type=Path, default=None, help="write it there (default: stdout)")
    p = sub.add_parser("import", help="board targets from a lab-style file (export lab's) to the nodes")
    p.add_argument("what", choices=["lab"])
    p.add_argument("file", type=Path)
    p.add_argument("bays", nargs="*", help="only these slots or bays (default: every entry with a platform)")
    p = sub.add_parser("lease")
    p.add_argument("bay")
    p.add_argument("--for", dest="ttl", default="1h", help="how long: 15m, 2h, 86400 (default 1h)")
    p.add_argument("--note", default="", help="shown on the node's page")
    p = sub.add_parser("release")
    p.add_argument("bay")
    p.add_argument("--force", action="store_true", help="someone else's reservation (admin, BAYCTL_KEY)")
    p = sub.add_parser("access")
    acc = p.add_subparsers(dest="access_cmd", required=True)
    acc.add_parser("show").add_argument("bay")
    acc.add_parser("push").add_argument("bays", nargs="*", help="default: every bay")
    acc.add_parser("claim").add_argument("bays", nargs="+")
    q = acc.add_parser("kick")
    q.add_argument("bay")
    q.add_argument("id", help="connection id, from `access show`: usbip:51234, rfc2217, web0, ...")
    acc.add_parser("keygen")
    p = sub.add_parser("update", help="firmware over the network (MCUboot images)")
    p.add_argument("image", type=Path, help="zephyr.signed.bin from `west build --sysbuild`")
    p.add_argument("bays", nargs="*")
    p.add_argument("--all", action="store_true", help="every bay node the hub lists, one after the other")
    p.add_argument("--hub", action="store_true", help="the power hub itself")
    p.add_argument("--force", action="store_true", help="also reserved bays")
    p.add_argument("--timeout", type=float, default=420.0, help="restart and trial, per device (s)")
    p = sub.add_parser("row", help="switch or power-cycle a rack row (A-D) on the power hub")
    p.add_argument("row", choices=list("ABCDabcd"), metavar="ROW")
    p.add_argument("action", choices=["on", "off", "cycle"])
    p.add_argument("--ms", type=int, default=1000)
    p = sub.add_parser("hub", help="inspect or control the power hub")
    hsub = p.add_subparsers(dest="hub_cmd")
    hsub.add_parser("status")
    hsub.add_parser("events")
    hsub.add_parser("enumerate")
    hp = hsub.add_parser("pd")
    hp.add_argument("pref", choices=["epr", "20v"])
    hn = hsub.add_parser("node")
    hn.add_argument("target", help="bay position (A1..D15) or CAN node id (0x01..0x3f)")
    hn.add_argument("action", choices=list(HUB_NODE_ACTIONS))
    hsub.add_parser("claim")
    a = ap.parse_args(argv)

    warnings: list[str] = []
    try:
        if a.cmd == "hub":
            return hub_cli(a)
        if a.cmd == "row":
            row_name = a.row.upper()
            body = {"row": row_name, "action": a.action}
            if a.action == "cycle":
                body["ms"] = a.ms
            s = api(hub_device(a.lab), "/api/row", body, key=admin_key())
            row_doc = next((r for r in s.get("rows", []) if r.get("name") == row_name), None)
            if row_doc:
                _print_hub_row(row_doc)
            return 0
        if a.cmd == "access" and a.access_cmd == "keygen":
            print(secrets.token_hex(32))
            return 0
        if a.cmd == "import":
            failed = import_lab(a.file, a.bays, Lab(a.lab, warnings))
            _say(warnings)
            return 1 if failed else 0
        if a.cmd == "update" and (a.hub or a.all):
            return update_cli(a, {})
        bays = load_bays(a.lab, a.boards, names=_names(a), warnings=warnings)
        _say(warnings)
        bayctl = str(Path(__file__).resolve())
        if a.cmd == "list":
            ports: dict[str, dict] = {}
            la = analyzer_info(a.rack) if any(b.role for b in bays.values()) else {}
            for b in bays.values():
                if b.vacant:
                    target = "(empty port)"
                elif b.role:
                    target = f"{b.role}: gusmanb {la.get('app', '?')}"
                else:
                    target = b.platform or "(no target)"
                tags = [] if b.ci or b.vacant else [b.role or "not in CI"]
                if b.mismatch:
                    tags.append("not the board its target was saved for")
                line = (f"{b.id:5} {b.board or '-':19} {target:34} {b.runner or '-':20} "
                        f"{b.console:6}  {b.host}" + "".join(f"  [{t}]" for t in tags))
                if a.probe:
                    try:
                        if b.slot:
                            if b.node not in ports:
                                ports[b.node] = {x.get("port"): x for x in node_ports(b)}
                            port = ports[b.node].get(b.slot) or {}
                            pw = port.get("power") or {}
                            line += f"  VBUS {'on' if pw.get('on') else 'off'} {pw.get('ma', 0)} mA"
                            if b.role:
                                line += "  " + analyzer_state(port.get("usb"), la)
                        else:
                            dut = api(b, "/api/status", timeout=3).get("dut", {})
                            line += f"  VBUS {'on' if dut.get('on') else 'off'} {dut.get('ma', 0)} mA"
                    except BayError:
                        line += "  unreachable"
                print(line)
        elif a.cmd == "status":
            node = node_bay(bays, a.bay)
            _print_status(api(node, "/api/status"))
            if node.multi:
                for port in node_ports(node):
                    _print_port(port)
            _print_usb(node)
        elif a.cmd == "ports":
            for port in node_ports(node_bay(bays, a.bay)):
                _print_port(port)
        elif a.cmd in ("power", "power-port"):
            if a.cmd == "power-port":
                order = pdu_bays(bays)
                if not 1 <= a.port <= len(order):
                    raise BayError(f"port {a.port}: the rack has {len(order)} boards under test")
                targets = [order[a.port - 1]]
            else:
                targets = dut_targets(bays, a.bay, analyzers=True)
            body = {"action": a.action}
            if a.action == "cycle":
                body["ms"] = getattr(a, "ms", 1000)
            for bay in targets:
                _print_control(bay, control(bay, "power", body))
        elif a.cmd in ("reset", "boot"):
            for bay in dut_targets(bays, a.bay):
                if a.cmd == "reset":
                    body = {"ms": a.ms}
                elif a.power_cycle and not bay.slot:
                    raise BayError(f"{bay.id}: --power-cycle is a sub-slot's (its port's power); a bay's one DUT "
                                   f"boots through its AUX RESET")
                else:
                    body = {"power_cycle": True} if a.power_cycle else {}
                _print_control(bay, control(bay, a.cmd, body))
        elif a.cmd == "mode":
            _print_status(api(node_bay(bays, a.bay), "/api/mode", {"mode": a.mode}))
        elif a.cmd == "attach":
            targets = dut_targets(bays, a.bay)
            for bay in targets:
                new = attach(bay)
                if a.show:
                    print(f"{bay.id}: " + (", ".join(new) if new else
                                            "no new /dev/serial/by-id entry (already attached, or no tty)"))
            if a.follow:
                try:
                    follow(targets)
                except KeyboardInterrupt:
                    pass
        elif a.cmd == "detach":
            print(f"detached {sum(detach(bay) for bay in dut_targets(bays, a.bay))} device(s)")
        elif a.cmd == "prepare":
            bay = get_bay(bays, a.bay)
            if a.lease:
                lease(bay, duration(a.lease), "bayctl prepare")
            s = api(bay, "/api/status")
            if s.get("path") != "usbip":
                api(bay, "/api/mode", {"mode": "usbip"})
            if bay.slot:
                port = port_doc(bay)
                if a.power_cycle:
                    detach(bay)
                    control(bay, "power", {"action": "cycle", "ms": 1000})
                elif not (port.get("power") or {}).get("on") or port.get("fault"):
                    control(bay, "power", {"action": "on"})
                enumerated = lambda: bool(port_doc(bay).get("usb"))          # noqa: E731
            else:
                if a.power_cycle:
                    detach(bay)
                    s = api(bay, "/api/power", {"action": "cycle", "ms": 1000})
                elif not s.get("dut", {}).get("on") or s.get("dut", {}).get("latched"):
                    s = api(bay, "/api/power", {"action": "on"})
                enumerated = lambda: api(bay, "/api/status").get("usb", {}).get("devices", 0) > 0   # noqa: E731
            if not wait_for(enumerated, a.timeout):
                raise BayError(f"{bay.id}: no USB device enumerated on the DUT port after {a.timeout:.0f} s")
            attach(bay)
            serial = bay.serial
            if not serial and bay.reported is not None and bay.console.startswith("usb"):
                # enumerated only now: its console's name from the device the node sees
                wait_for(lambda: (slot_doc(bay).get("device") or {}).get("strings") is not False, 3)
                serial = console_path(bay.console, slot_doc(bay).get("device"))
            if bay.console.startswith("usb") and serial and not wait_for(lambda: Path(serial).exists(), a.timeout):
                raise BayError(f"{bay.id}: {serial} did not appear")
        elif a.cmd == "pty":
            bay = get_bay(bays, a.bay)
            if bay.slot:
                raise BayError(f"{bay.id}: a sub-slot has no AUX UART: its console is the board's own USB")
            pty_bridge(bay)
        elif a.cmd == "hwmap":
            scripts = a.scripts or a.out.resolve().parent / "rack-scripts"
            lab = a.lab.resolve() if a.lab.exists() else None
            entries, warnings = hwmap(bays, scripts, a.python, bayctl, lab, a.power_cycle, a.lease)
            a.out.write_text("# Generated by tools/bayctl.py hwmap — regenerate rather than edit.\n"
                             + yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")
            for w in warnings:
                print("warning:", w, file=sys.stderr)
            print(f"wrote {a.out} ({len(entries)} boards) and pre-scripts in {scripts}")
        elif a.cmd == "export":
            if a.what == "lab":
                doc = export_lab(bays)
                if not doc["bays"]:
                    raise BayError("no board target read from the rack (no node answered, or none has one)")
                text = (f"# bayctl export lab, {time.strftime('%Y-%m-%d %H:%M')}: the board targets the rack's nodes "
                        f"hold.\n# Put them back with: python tools/bayctl.py import lab FILE [BAY ...]\n"
                        + yaml.safe_dump(doc, sort_keys=False))
            elif a.what == "pdudaemon":
                doc = export_pdudaemon(bays, a.python, bayctl)
                ports = doc.pop("_ports")
                print("# PDUDaemon ports: " + ", ".join(f"{p}={b}" for p, b in ports.items()), file=sys.stderr)
                text = json.dumps(doc, indent=2) + "\n"
            else:
                text = yaml.safe_dump(export_labgrid(bays, a.python, bayctl), sort_keys=False)
            if a.out:
                a.out.write_text(text, encoding="utf-8", newline="\n")
                print(f"wrote {a.out}" + (f" ({len(doc['bays'])} slots)" if a.what == "lab" else ""))
            else:
                print(text, end="")
        elif a.cmd == "lease":
            bay = bays.get(a.bay.upper()) or node_bay(bays, a.bay)
            d = lease(bay, duration(a.ttl), a.note)
            print(f"{bay.id} reserved for {d['you']}, {lease_left(bay, d)} s")
        elif a.cmd == "release":
            bay = bays.get(a.bay.upper()) or node_bay(bays, a.bay)
            release(bay, a.force)
            print(f"{bay.id} released")
        elif a.cmd == "access":
            return access_cli(a, bays)
        elif a.cmd == "update":
            return update_cli(a, bays)
    except BayError as e:
        print(f"bayctl: {e}", file=sys.stderr)
        return 1
    return 0


def _names(a: argparse.Namespace) -> list[str] | None:
    """The bays a command names (their nodes are the ones to ask); None: the whole rack."""
    if a.cmd in ("list", "hwmap", "export", "power-port"):
        return None
    if a.cmd == "access":
        return [a.bay] if a.access_cmd in ("show", "kick") else (a.bays or None)
    if a.cmd == "update":
        return a.bays
    return [a.bay]


def _say(warnings: list[str]) -> None:
    for w in warnings:
        print("warning:", w, file=sys.stderr)
    warnings.clear()


def slot_doc(bay: Bay) -> dict:
    """GET /api/ports/<n>/board: the slot's target and the device in it now ({} if the node does not say)."""
    try:
        return api(bay, f"/api/ports/{bay.slot or 1}/board", timeout=NODE_TIMEOUT)
    except BayError:
        return {}


def access_cli(a: argparse.Namespace, bays: dict[str, Bay]) -> int:
    if a.access_cmd == "show":
        key = admin_key() if os.environ.get("BAYCTL_KEY") else None
        _print_access(api(node_bay(bays, a.bay), "/api/access", key=key))
        return 0
    if a.access_cmd == "kick":
        api(node_bay(bays, a.bay), "/api/access/kick", {"id": a.id}, key=admin_key())
        print(f"{a.bay.upper()}: kicked {a.id}")
        return 0
    key = admin_key()
    if a.access_cmd == "claim":
        for node in nodes_of(bays, a.bays):
            access_claim(node, key)
            print(f"{node.id}: claimed")
        return 0
    # push
    failed = 0
    for bay in nodes_of(bays, a.bays):
        rules = access_rules(a.lab, bay.id)
        if rules is None:
            raise BayError(f"no `access:` section in {a.lab} (see config/lab.example.yaml)")
        try:
            result = access_push(bay, rules, key)
        except BayError as e:
            result, failed = str(e), failed + 1
        if result == "not claimed":
            result += f": bayctl access claim {bay.id}"
            failed += 1
        print(f"{bay.id:4} {result}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
