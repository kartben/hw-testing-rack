"""Shared plumbing of the web pages' development servers (bay node, power hub).

Each page has a dev_server.py that simulates its board and serves its page
with the same endpoints and JSON as the firmware; this module has what they
share: the common static files, JSON and file responses, and a minimal
WebSocket (RFC 6455) framing.
"""

from __future__ import annotations

import json
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
