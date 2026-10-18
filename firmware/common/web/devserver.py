"""Shared plumbing of the web pages' development servers (bay node, power hub).

Each page has a dev_server.py that simulates its board and serves its page
with the same endpoints and JSON as the firmware; this module has what they
share: the common static files, JSON and file responses, a minimal
WebSocket (RFC 6455) framing, the admin key's claim and signatures, and the
firmware updates (MCUboot images, the upload, the restart and the trial).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import struct
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path

COMMON = Path(__file__).resolve().parent
VENDOR = COMMON / "vendor"

# Served by both firmwares from firmware/common/web (see common/CMakeLists.txt)
COMMON_STATIC = {
    "/rack.css": (COMMON / "rack.css", "text/css"),
    "/rack.mjs": (COMMON / "rack.mjs", "text/javascript"),
}

XTERM_STATIC = {
    "/xterm.mjs": (VENDOR / "xterm/xterm.mjs", "text/javascript"),
    "/addon-fit.mjs": (VENDOR / "xterm/addon-fit.mjs", "text/javascript"),
    "/xterm.css": (VENDOR / "xterm/xterm.css", "text/css"),
    "/xterm-LICENSE.txt": (VENDOR / "xterm/LICENSE.txt", "text/plain"),
}


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


class PageHandler(BaseHTTPRequestHandler):
    """send/json helpers and the static files: STATIC maps a path to (file, type)."""

    STATIC: dict[str, tuple[Path, str]] = {}

    def send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def json(self, code: int, obj) -> None:
        self.send(code, json.dumps(obj).encode(), "application/json")

    def static(self, path: str) -> bool:
        entry = self.STATIC.get(path) or COMMON_STATIC.get(path)
        if entry is None:
            return False
        file, ctype = entry
        self.send(200, file.read_bytes(), ctype)
        return True

    def body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def log_message(self, fmt: str, *args) -> None:
        pass


class Admin:
    """The admin key of a simulated device, as firmware/common/lib/admin.c.

    Claim: claim(ip, {}) or claim(ip, {"key": hex}), then claim(ip, {"ticket": t})
    until press_boot(); admin requests carry X-Bay-Auth = nonce:HMAC.
    """

    CLAIM_S = 60

    def __init__(self) -> None:
        self.key: bytes | None = None
        self.nonces: dict[str, float] = {}
        self.pending: dict | None = None

    def nonce(self) -> str:
        value = os.urandom(8).hex()
        self.nonces[value] = time.monotonic() + 60
        return value

    def check(self, auth: str, method: str, path: str, body: bytes) -> bool:
        if self.key is None or ":" not in auth:
            return False
        nonce, mac = auth.split(":", 1)
        if self.nonces.pop(nonce, 0) < time.monotonic():
            return False
        msg = f"{nonce}\n{method}\n{path}\n".encode() + body
        return hmac.compare_digest(mac, hmac.new(self.key, msg, hashlib.sha256).hexdigest())

    def claim(self, ip: str, body: dict) -> tuple[int, dict]:
        now = time.monotonic()
        if "ticket" in body:
            c = self.pending
            if not c or c["ip"] != ip or c["ticket"] != body["ticket"]:
                return 404, {"error": "no such claim from this address"}
            if now >= c["until"]:
                self.pending = None
                return 404, {"error": "nobody pressed BOOT in time"}
            if not c["done"]:
                return 200, {"state": "pending", "remaining_s": int(c["until"] - now + 0.999)}
            self.pending = None
            return 200, {"state": "done", "key": c["key"].hex()}
        if self.key is not None:
            return 409, {"error": "already claimed: unlock with the admin key, or reset"}
        offered = body.get("key")
        if offered is not None and (len(offered) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in offered)):
            return 400, {"error": "key: 64 hex digits"}
        self.pending = {"ip": ip, "ticket": os.urandom(8).hex(), "until": now + self.CLAIM_S, "done": False,
                        "key": bytes.fromhex(offered) if offered else None}
        return 200, {"state": "pending", "ticket": self.pending["ticket"], "remaining_s": self.CLAIM_S}

    def claim_pending(self) -> bool:
        return bool(self.pending) and not self.pending["done"] and time.monotonic() < self.pending["until"]

    def press_boot(self) -> bool:
        """A short press on BOOT: confirms a pending claim."""
        if not self.claim_pending():
            return False
        self.key = self.pending["key"] or os.urandom(32)
        self.pending.update(done=True, key=self.key, until=time.monotonic() + self.CLAIM_S)
        return True


# --- Firmware updates (firmware/common/lib/update.c, mcuboot_img.c) -------------------

IMG_MAGIC, TLV_INFO, TLV_PROT_INFO, TLV_ID = 0x96F3B83D, 0x6907, 0x6908, 0x00A0


def image_info(data: bytes) -> dict:
    """Version, image id and size of a signed image, as the firmware reads it; ValueError otherwise."""
    if len(data) < 32 or struct.unpack_from("<I", data)[0] != IMG_MAGIC:
        raise ValueError("not a signed image (upload zephyr.signed.bin from a --sysbuild build)")
    hdr, prot, size = struct.unpack_from("<HHI", data, 8)
    major, minor, rev, build = struct.unpack_from("<BBHI", data, 20)
    tlv = hdr + size + prot
    if tlv + 4 > len(data) or struct.unpack_from("<H", data, tlv)[0] != TLV_INFO:
        raise ValueError("image truncated")
    if tlv + struct.unpack_from("<H", data, tlv + 2)[0] != len(data):
        raise ValueError("image truncated" if tlv + struct.unpack_from("<H", data, tlv + 2)[0] > len(data)
                         else "bytes after the end of the image")
    image_id, o = "", hdr + size + 4
    while prot and o + 4 <= hdr + size + prot:
        kind, n = struct.unpack_from("<HH", data, o)
        if kind == TLV_ID:
            image_id = data[o + 4:o + 4 + n].decode()
        o += 4 + n
    if not image_id:
        raise ValueError("no image id: not built by this repository (firmware/common/sysbuild.cmake)")
    return {"version": f"{major}.{minor}.{rev}" + (f"+{build}" if build else ""), "id": image_id,
            "size": len(data)}


def make_image(version: str, image_id: str, code: int = 300_000) -> bytes:
    """An image laid out as imgtool does (unsigned: enough for the pages and the dev servers)."""
    major, minor, rev = (int(x) for x in version.split("."))
    idb = image_id.encode()
    prot = struct.pack("<HH", TLV_PROT_INFO, 8 + len(idb)) + struct.pack("<HH", TLV_ID, len(idb)) + idb
    body = os.urandom(code)
    tlvs = struct.pack("<HHHH", TLV_INFO, 4 + 4 + 32, 0x10, 32) + hashlib.sha256(body).digest()
    header = struct.pack("<IIHHIIBBHII", IMG_MAGIC, 0, 32, len(prot), code, 0, major, minor, rev, 0, 0)
    return header + body + prot + tlvs


class Firmware:
    """The update endpoints of a simulated device (common/web/update_http.c).

    begin() and upload() check what the firmware checks (ticket, size,
    SHA-256, image id); the device then "restarts" (its API answers 503 for
    restart_s), runs the new firmware on trial (Wi-Fi, then the rack bus),
    and confirms it after trial_s, or, after rollback(), restarts again into
    the previous one.
    """

    def __init__(self, version: str, image_id: str, test_key: bool = True,
                 restart_s: float | None = None, trial_s: float | None = None, on_event=None) -> None:
        self.version, self.image_id, self.test_key = version, image_id, test_key
        self.on_event = on_event or (lambda text: None)
        # The tests make it quicker (HWTR_SIM_RESTART_S, HWTR_SIM_TRIAL_S)
        self.restart_s = restart_s if restart_s is not None else float(os.environ.get("HWTR_SIM_RESTART_S", 6))
        self.trial_s = trial_s if trial_s is not None else float(os.environ.get("HWTR_SIM_TRIAL_S", 9))
        self.ticket: dict | None = None
        self.error: str | None = None
        self.last: dict | None = None
        self.down_until = 0.0
        self.trial: dict | None = None
        self.fail_next = False
        self.busy: str | None = None

    def rollback(self) -> None:
        """The next update does not confirm itself: MCUboot goes back."""
        self.fail_next = True

    def _tick(self) -> None:
        now = time.monotonic()
        t = self.trial
        if t and now >= self.down_until and now - t["start"] >= self.trial_s:
            if t["fail"]:
                self.version = self.last["from"]
                self.last["result"] = "rolled back"
                self.down_until = now + self.restart_s
                self.on_event(f"update to {self.last['to']} rolled back: running {self.version}")
            else:
                self.last["result"] = "confirmed"
                self.on_event(f"firmware {self.version} confirmed itself")
            self.trial = None

    def down(self) -> bool:
        """Restarting: the device does not answer."""
        self._tick()
        return time.monotonic() < self.down_until

    def doc(self) -> dict:
        self._tick()
        t = self.trial
        trial = None
        if t:
            gone = time.monotonic() - t["start"]
            up = ["wifi"] + (["bus"] if gone > self.trial_s * 0.4 and not t["fail"] else [])
            trial = {"left_s": max(0, int(180 - gone)), "need": ["wifi", "bus"], "up": up}
        return {"version": self.version, "id": self.image_id, "test_key": self.test_key, "slot_kb": 3808,
                "state": "receiving" if self.ticket and self.ticket.get("got") else "idle",
                "received": 0, "size": 0, "trial": trial, "last": self.last, "error": self.error}

    def begin(self, ip: str, body: dict) -> tuple[int, dict]:
        self._tick()
        size, sha = body.get("size"), str(body.get("sha256", ""))
        if not isinstance(size, int) or size <= 0 or len(sha) != 64:
            return 400, {"error": "size and sha256 (64 hex digits) needed"}
        if self.trial:
            return 409, {"error": "the running firmware is on trial: wait until it confirms itself"}
        if self.busy and not body.get("force"):
            return 409, {"error": self.busy}
        if size > 3808 * 1024:
            return 413, {"error": "size: larger than the update slot"}
        self.ticket = {"ip": ip, "value": os.urandom(8).hex(), "size": size, "sha": sha.lower(),
                       "until": time.monotonic() + 60}
        return 200, {"ticket": self.ticket["value"], "id": self.image_id}

    def upload(self, ip: str, ticket: str, data: bytes) -> tuple[int, dict]:
        t, self.ticket = self.ticket, None
        if not t or t["ip"] != ip or t["value"] != ticket or time.monotonic() > t["until"]:
            return 403, {"error": "no such ticket: begin again"}
        try:
            if len(data) != t["size"]:
                raise ValueError("fewer bytes than announced" if len(data) < t["size"] else "more bytes than announced")
            if hashlib.sha256(data).hexdigest() != t["sha"]:
                raise ValueError("SHA-256 does not match")
            info = image_info(data)
            if info["id"] != self.image_id:
                raise ValueError(f"image for {info['id']}, this is {self.image_id}")
        except ValueError as e:
            self.error = str(e)
            return 400, {"error": self.error}
        now = time.monotonic()
        self.error = None
        self.last = {"result": "on trial", "to": info["version"], "from": self.version}
        self.version = info["version"]
        self.down_until = now + self.restart_s
        self.trial = {"start": self.down_until, "fail": self.fail_next}
        self.fail_next = False
        return 200, {"state": "rebooting", "version": info["version"], "id": info["id"]}
