"""Shared plumbing of the web pages' development servers (bay node, power hub).

Each page has a dev_server.py that simulates its board and serves its page
with the same endpoints and JSON as the firmware; this module has what they
share: the common static files, JSON and file responses, a minimal
WebSocket (RFC 6455) framing, and the admin key's claim and signatures.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
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
