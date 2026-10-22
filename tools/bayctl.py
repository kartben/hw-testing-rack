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
    python tools/bayctl.py hwmap -o rack-map.yaml       Zephyr twister hardware map + per-bay pre-scripts
    python tools/bayctl.py export labgrid|pdudaemon     configuration for labgrid / LAVA's PDUDaemon
    python tools/bayctl.py lease B3 [--for 1h] [--note TEXT]    reserve the bay for this host
    python tools/bayctl.py release B3 [--force]         end the reservation (--force: someone else's, admin)
    python tools/bayctl.py access show B3               rights, reservation, connections (admin: rules, refusals)
    python tools/bayctl.py access push [B3 ...]         the `access:` rules of config/lab.yaml to the nodes
    python tools/bayctl.py access claim B3 [...]        give the nodes the rack's admin key (press BOOT on each)
    python tools/bayctl.py access kick B3 usbip:51234   close a connection, refuse its address for a minute
    python tools/bayctl.py access keygen                a new random admin key
    python tools/bayctl.py update IMAGE B3 [...]        firmware over the network (zephyr.signed.bin)
    python tools/bayctl.py update IMAGE --all           every bay node the hub lists, one after the other
    python tools/bayctl.py update IMAGE --hub           the power hub itself (lab.yaml `hub:`, or rack.local)

A bay with a DATA ×4 board holds up to four boards, sub-slots B3.1 to B3.4 (docs/multi-dut-node.md):
name one (`power B3.2 cycle`, `attach B3.2 --follow`, `prepare B3.2`, `lease B3.2`) or the whole bay
(`power B3 off`: every port).  The node's own commands (status, mode, access, update) take either.
A sub-slot with `role: analyzer` holds the bay's logic analyzer, not a board under test: `list` shows
it, `hwmap` leaves it out, and the whole bay's reset, boot, attach and detach pass it by (name it:
`attach B3.3`; `boot B3.3 --power-cycle` puts it in BOOTSEL through the BOOT wire on its BOOTSEL pad).

Where the data comes from:
  * config/rack.yaml `population`: which board family sits in which bay, or `boards:` per sub-slot;
  * mechanical/boards/boards.yaml `zephyr:`: each family's Zephyr target, west runner and console;
  * config/lab.yaml (per installation, git-ignored; see config/lab.example.yaml): probe serial
    numbers, console device paths, bay hosts and any override.

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


class BayError(Exception):
    pass


# ------------------------------------------------------------------------- configuration

@dataclass
class Bay:
    id: str
    board: str                      # board family id (boards.yaml)
    name: str = ""                  # human name of the board
    platform: str | None = None     # Zephyr target, as twister names it
    runner: str | None = None       # west runner
    probe_id: str | None = None     # west flash --dev-id (probe serial number, or the esp32 port)
    console: str = "usb"            # "usb": the DUT's USB VCOM (needs `serial`), "aux": the AUX UART
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

    @property
    def node_id(self) -> str:
        return self.node or self.id

    @property
    def url(self) -> str:
        return f"http://{self.host}" + ("" if self.http_port == 80 else f":{self.http_port}")


def _yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


NODE_KEYS = ("host", "http_port", "aux_port", "rfc2217_port")     # lab keys a bay's sub-slots share


def _bay_key(bid: str):
    bay, n = rackcfg.split_slot(bid)
    return bay[0], int(bay[1:]) if bay[1:].isdigit() else 0, n or 0


def load_bays(rack_yaml: Path = RACK_YAML, boards_yaml: Path = BOARDS_YAML,
              lab_yaml: Path | None = None) -> dict[str, Bay]:
    """Every board under test (a bay's one board, or each sub-slot of a converted bay), defaults from the
    board library, overrides from the lab file (a sub-slot's under its own id, B3.2; the node's under B3)."""
    rack = _yaml(rack_yaml)
    boards = _yaml(boards_yaml).get("boards", {})
    lab = _yaml(lab_yaml if lab_yaml is not None else LAB_YAML)
    domain = lab.get("domain", "local")
    lab_bays = {str(k).upper(): v or {} for k, v in (lab.get("bays") or {}).items()}
    population = {str(k).upper(): v or {} for k, v in (rack.get("population") or {}).items()}
    try:
        lab_nodes = {rackcfg.split_slot(k)[0] for k in lab_bays}
    except ValueError as e:
        raise BayError(f"config/lab.yaml: {e}") from None
    out: dict[str, Bay] = {}
    for bid in sorted(set(population) | lab_nodes, key=_bay_key):
        pop, node_over = population.get(bid, {}), lab_bays.get(bid, {})
        try:
            slots = rackcfg.dut_slots(bid, pop)
        except ValueError as e:
            raise BayError(f"config/rack.yaml population: {e}") from None
        multi = "boards" in pop
        if not slots:
            if not node_over.get("board"):
                raise BayError(f"bay {bid}: no board (config/rack.yaml population or lab bays.{bid}.board)")
            slots = [rackcfg.Slot(bid, bid, None, node_over["board"])]
        known = {sl.id for sl in slots}
        for k in lab_bays:
            if rackcfg.split_slot(k)[0] == bid and k != bid and k not in known:
                raise BayError(f"config/lab.yaml bays.{k}: bay {bid} has no such sub-slot "
                               f"({', '.join(sorted(known)) if multi else 'it holds one board'})")
        for sl in slots:
            if sl.slot is None:
                over = node_over
            else:
                over = {**{k: v for k, v in node_over.items() if k in NODE_KEYS}, **lab_bays.get(sl.id, {})}
            family = over.get("board", sl.board)
            info = boards.get(family, {})
            role = over.get("role", sl.role) or ""
            if role and role not in rackcfg.ROLES:
                raise BayError(f"bay {sl.id}: role {role!r}: {', '.join(rackcfg.ROLES)} (or none: a board under test)")
            if role and not sl.slot:
                raise BayError(f"bay {sl.id}: `role` is a sub-slot's: an analyzer watches its neighbours")
            z = {} if role else info.get("zephyr") or {}    # an analyzer runs gusmanb's firmware, not tests
            bay = Bay(
                id=sl.id, board=family, name=info.get("name", family),
                platform=over.get("platform", z.get("platform")),
                runner=over.get("runner", z.get("runner")),
                probe_id=str(over["id"]) if over.get("id") is not None else None,
                console=over.get("console", "usb" if sl.slot else z.get("console", "usb")),
                serial=over.get("serial"),
                baud=int(over.get("baud", z.get("baud", 115200))),
                host=over.get("host", f"bay-{bid.lower()}.{domain}"),
                http_port=int(over.get("http_port", lab.get("http_port", 80))),
                aux_port=int(over.get("aux_port", lab.get("aux_port", 4000))),
                rfc2217_port=int(over.get("rfc2217_port", lab.get("rfc2217_port", 4001))),
                fixtures=list(over.get("fixtures", [])),
                ci=bool(over.get("ci", not role)),
                choices=list(z.get("choices", [])),
                note=z.get("note", ""),
                product=over.get("product", z.get("product")),
                node=bid if sl.slot else "", slot=sl.slot, multi=multi, role=role,
            )
            if bay.console not in ("usb", "aux"):
                raise BayError(f"bay {sl.id}: console must be usb or aux, not {bay.console!r}")
            if sl.slot and bay.console == "aux":
                raise BayError(f"bay {sl.id}: a sub-slot has no AUX UART: its console is the board's own USB")
            out[sl.id] = bay
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
    """The boards a name covers: a sub-slot, a one-board bay, or every sub-slot of a converted bay (its
    analyzer only with `analyzers`: a whole bay's reset or attach leaves it alone, its power does not)."""
    subs = [x for x in bays.values() if x.node == name.upper()]
    if not subs:
        return [get_bay(bays, name)]
    duts = [x for x in subs if analyzers or not x.role]
    if not duts:
        raise BayError(f"bay {name.upper()} holds only its analyzer: name it ({', '.join(x.id for x in subs)})")
    return duts


def analyzer_info(rack_yaml: Path = RACK_YAML) -> dict:
    """config/rack.yaml › analyzer: the pinned gusmanb release, its firmware per board, its USB id."""
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

def api(bay: Bay, path: str, body: dict | None = None, timeout: float = 15.0, key: bytes | None = None) -> dict:
    """GET (body None) or POST a node endpoint; returns the JSON document.  With a key: signed (admin)."""
    data = None if body is None else json.dumps(body).encode()
    method = "GET" if body is None else "POST"
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
        raise BayError(f"{bay.id}: {path}: {e.code} {msg}") from None
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
    """The power hub, as a Bay for api(): lab.yaml `hub:` (host), else rack.<domain>."""
    lab = _yaml(lab_yaml if lab_yaml is not None else LAB_YAML)
    host = str(lab.get("hub") or f"rack.{lab.get('domain', 'local')}")
    name, _, port = host.partition(":")
    return Bay(id="hub", board="power-hub", host=name, http_port=int(port or 80))


def rack_nodes(hub: Bay) -> list[Bay]:
    """The bay nodes the hub lists on its rack bus (/api/status), addressed by IP, named by position."""
    s = api(hub, "/api/status")
    out = []
    for row in s.get("rows", []):
        for n in row.get("nodes", []):
            if n.get("ip", "0.0.0.0") != "0.0.0.0" and n.get("state") not in ("lost", "failed", "incompatible"):
                out.append(Bay(id=n["pos"], board="bay-node", host=n["ip"]))
    return out


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
    raise BayError(f"bay {bay.id} ({bay.name}): set bays.{bay.id}.platform in config/lab.yaml{hint}")


def hwmap(bays: dict[str, Bay], scripts_dir: Path, python: str, bayctl: str, lab: Path | None,
          power_cycle: bool = False, lease_for: str | None = None) -> tuple[list[dict], list[str]]:
    """Twister hardware map entries (+ writes one pre-script per bay); returns (entries, warnings)."""
    entries, warnings = [], []
    no_id: dict[str, list[str]] = {}            # runner -> bays without a probe id
    scripts_dir.mkdir(parents=True, exist_ok=True)
    lab_arg = f" --lab {shlex.quote(str(lab))}" if lab else ""
    for bay in bays.values():
        if not bay.ci or bay.role:          # an analyzer is no test target, whatever its `ci`
            continue
        try:
            platform = _target_or_error(bay)
        except BayError as e:
            warnings.append(str(e))
            continue
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
        probe_id = bay.probe_id
        if not probe_id and bay.runner == "esp32" and bay.serial:
            probe_id = bay.serial            # the esp32 runner selects the board by its serial port
        if probe_id:
            e["id"] = probe_id
        if bay.console == "aux":
            # twister splits serial_pty on spaces and commas: keep these paths free of both
            e["serial_pty"] = f"{python} {bayctl}{lab_arg} pty {bay.id}"
        elif bay.serial:
            e["serial"] = bay.serial
        else:
            e["connected"] = False
            warnings.append(f"bay {bay.id}: no console path; attach it (`bayctl attach {bay.id} --show`) and set "
                            f"bays.{bay.id}.serial in config/lab.yaml, or console: aux")
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
            warnings.append(f"bays {', '.join(ids)} use {runner} without a probe id: set bays.<id>.id "
                            f"(`bayctl attach <bay> --show`), or flashing may hit the wrong board")
    return entries, warnings


def export_labgrid(bays: dict[str, Bay], python: str, bayctl: str) -> dict:
    targets = {}
    for bay in bays.values():
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
        "_ports": {i + 1: bay.id for i, bay in enumerate(bays.values())},
    }


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
    ap.add_argument("--rack", type=Path, default=RACK_YAML, help=argparse.SUPPRESS)
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
    p.add_argument("what", choices=["labgrid", "pdudaemon"])
    p.add_argument("--python", default="python3")
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
    a = ap.parse_args(argv)

    try:
        bays = load_bays(a.rack, a.boards, a.lab)
        bayctl = str(Path(__file__).resolve())
        if a.cmd == "list":
            ports: dict[str, dict] = {}
            la = analyzer_info(a.rack)
            for b in bays.values():
                target = f"{b.role}: gusmanb {la.get('app', '?')}" if b.role else b.platform or "(set platform)"
                line = (f"{b.id:5} {b.board:18} {target:34} {b.runner or '-':20} "
                        f"{b.console:3}  {b.host}" + ("" if b.ci else f"  [{b.role or 'not in CI'}]"))
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
                order = list(bays.values())
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
            if bay.console == "usb" and bay.serial and not wait_for(lambda: Path(bay.serial).exists(), a.timeout):
                raise BayError(f"{bay.id}: {bay.serial} did not appear")
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
            doc = (export_labgrid if a.what == "labgrid" else export_pdudaemon)(bays, a.python, bayctl)
            if a.what == "pdudaemon":
                ports = doc.pop("_ports")
                print("# PDUDaemon ports: " + ", ".join(f"{p}={b}" for p, b in ports.items()), file=sys.stderr)
                print(json.dumps(doc, indent=2))
            else:
                print(yaml.safe_dump(doc, sort_keys=False), end="")
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


def access_cli(a: argparse.Namespace, bays: dict[str, Bay]) -> int:
    if a.access_cmd == "keygen":
        print(secrets.token_hex(32))
        return 0
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
