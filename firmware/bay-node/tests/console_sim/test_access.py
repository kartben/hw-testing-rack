"""Access control of the bay node on native_sim: the real access.c, web.c and aux_console.c.

Linux only (native_sim, host sockets); in the Zephyr build image:

    python3 test_access.py [--workspace /ws] [--build /build] [--exe zephyr.exe]

Builds the node (as run.py does) unless --exe is given, then starts it with a
fresh simulated flash and talks to it from two addresses of the loopback
network: 127.0.0.1 (the admin's laptop) and 127.0.0.2 (another host);
127.0.0.3 plays a CI runner, 127.0.0.4 a desk with the console.  The node's local shell is its stdin, which is
how the BOOT press of a claim is simulated ("bay access claim").

What this cannot cover: the packet filter (host sockets bypass Zephyr's IP
stack, so the TCP ports are checked at accept() here), USB/IP and telnet.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADMIN, OTHER, CI, DESK = "127.0.0.1", "127.0.0.2", "127.0.0.3", "127.0.0.4"
KEY = os.urandom(32)                  # a test key, made up for this run

ARGS: argparse.Namespace


class Node:
    """The simulated node: its console on a pipe, the flash in a temporary file."""

    def __init__(self, exe: Path, flash: Path):
        self.proc = subprocess.Popen([str(exe), "--uart_stdinout", f"--flash={flash}"],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        self.out = b""
        self.lock = threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()
        self.wait_for(b"SIM: ready", 20)

    def _read(self) -> None:
        while data := os.read(self.proc.stdout.fileno(), 4096):
            with self.lock:
                self.out += data

    def wait_for(self, text: bytes, timeout: float = 5) -> None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.lock:
                if text in self.out:
                    return
            time.sleep(0.05)
        raise AssertionError(f"node never printed {text!r}; output:\n{self.out[-2000:].decode(errors='replace')}")

    def shell(self, command: str, expect: str) -> str:
        with self.lock:
            start = len(self.out)
        self.proc.stdin.write(command.encode() + b"\r")
        end = time.monotonic() + 5
        while time.monotonic() < end:
            with self.lock:
                got = self.out[start:].decode(errors="replace")
            if expect in got:
                return got
            time.sleep(0.05)
        raise AssertionError(f"{command!r}: no {expect!r} in:\n{got}")

    def stop(self) -> None:
        self.proc.kill()
        self.proc.wait()
        self.proc.stdin.close()
        self.proc.stdout.close()


def request(src: str, method: str, path: str, body: dict | None = None,
            headers: dict | None = None, raw: bytes | None = None) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", 80, timeout=10, source_address=(src, 0))
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
    conn.request(method, path, body=data, headers={"Content-Type": "application/json", **(headers or {})})
    r = conn.getresponse()
    text = r.read()
    conn.close()
    try:
        return r.status, json.loads(text)
    except json.JSONDecodeError:
        return r.status, {"text": text.decode(errors="replace")}


def get(src: str, path: str, **kw) -> tuple[int, dict]:
    return request(src, "GET", path, **kw)


def post(src: str, path: str, body: dict, **kw) -> tuple[int, dict]:
    return request(src, "POST", path, body, **kw)


def signed(src: str, method: str, path: str, body: dict | None = None, key: bytes = KEY) -> tuple[int, dict]:
    _, n = get(src, "/api/access/nonce")
    raw = b"" if body is None else json.dumps(body).encode()
    mac = hmac.new(key, f"{n['nonce']}\n{method}\n{path}\n".encode() + raw, hashlib.sha256).hexdigest()
    return request(src, method, path, headers={"X-Bay-Auth": f"{n['nonce']}:{mac}"},
                   raw=raw if body is not None else None)


def tcp(src: str, port: int) -> socket.socket:
    s = socket.create_connection(("127.0.0.1", port), timeout=5, source_address=(src, 0))
    return s


def closed_soon(s: socket.socket, timeout: float = 2, keep: bool = False) -> bool:
    """True when the node closes the connection within the timeout (keep: leave it open)."""
    s.settimeout(timeout)
    try:
        closed = s.recv(256) == b""
    except socket.timeout:
        closed = False
    except OSError:
        closed = True
    if closed or not keep:
        s.close()
    return closed


def websocket(src: str, path: str) -> int:
    """HTTP status of a WebSocket upgrade."""
    s = tcp(src, 80)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall(f"GET {path} HTTP/1.1\r\nHost: node\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
              f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
    s.settimeout(5)
    head = b""
    try:
        while b"\r\n" not in head:
            chunk = s.recv(256)
            if not chunk:
                break
            head += chunk
        # A refused upgrade: the node switches protocols, then closes without a hello
        if head.startswith(b"HTTP/1.1 101"):
            data = head.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in head else b""
            while b"hello" not in data:
                chunk = s.recv(512)
                if not chunk:
                    return 403
                data += chunk
            return 101
        return int(head.split()[1]) if head else 0
    finally:
        s.close()


class AccessSim(unittest.TestCase):
    node: Node
    flash: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.flash = Path(cls.tmp.name) / "flash.bin"
        cls.node = Node(ARGS.exe, cls.flash)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.node.stop()
        cls.tmp.cleanup()

    def test_access(self) -> None:
        node = self.node

        # --- An unclaimed node is open, as before -----------------------------
        code, s = get(OTHER, "/api/status")
        self.assertEqual(code, 200)
        self.assertEqual(s["access"], {"enabled": False, "claimed": False, "you": OTHER,
                                       "allow": ["status", "control", "console", "usbip", "shell", "camera"],
                                       "refused": 0, "lease": {"holder": "", "note": "", "remaining_s": 0,
                                                               "yours": False}})
        self.assertEqual(post(OTHER, "/api/reset", {"ms": 10})[0], 200)
        self.assertEqual(get(ADMIN, "/api/access")[1]["claim"], "none")
        # Rules need the key
        self.assertEqual(post(ADMIN, "/api/access/rules", {"enabled": True})[0], 403)

        # --- Claim: started from the network, confirmed on the node --------------
        code, c = post(ADMIN, "/api/access/claim", {"key": KEY.hex()})
        self.assertEqual(code, 200, c)
        self.assertEqual(c["state"], "pending")
        self.assertEqual(post(ADMIN, "/api/access/claim", {"ticket": c["ticket"]})[1]["state"], "pending")
        self.assertEqual(post(OTHER, "/api/access/claim", {"ticket": c["ticket"]})[0], 404)   # not its claim
        node.shell("bay access claim", "claimed")
        code, d = post(ADMIN, "/api/access/claim", {"ticket": c["ticket"]})
        self.assertEqual((code, d["state"], d["key"]), (200, "done", KEY.hex()))
        self.assertEqual(post(ADMIN, "/api/access/claim", {"ticket": c["ticket"]})[0], 404)   # once
        self.assertEqual(post(OTHER, "/api/access/claim", {})[0], 409)                        # claimed

        # --- Signed requests ----------------------------------------------------
        code, d = signed(ADMIN, "GET", "/api/access")
        self.assertEqual(code, 200, d)
        self.assertTrue(d["admin"])
        self.assertEqual(d["rules"], {"everyone": ["status"], "sources": []})
        self.assertEqual(signed(ADMIN, "GET", "/api/access", key=os.urandom(32))[0], 403)
        _, n = get(ADMIN, "/api/access/nonce")
        mac = hmac.new(KEY, f"{n['nonce']}\nGET\n/api/access\n".encode(), hashlib.sha256).hexdigest()
        hdr = {"X-Bay-Auth": f"{n['nonce']}:{mac}"}
        self.assertEqual(get(ADMIN, "/api/access", headers=hdr)[0], 200)
        self.assertEqual(get(ADMIN, "/api/access", headers=hdr)[0], 403)                     # nonce used up
        # The signature covers the body
        _, n = get(ADMIN, "/api/access/nonce")
        mac = hmac.new(KEY, f"{n['nonce']}\nPOST\n/api/access/rules\n{{}}".encode(), hashlib.sha256).hexdigest()
        self.assertEqual(request(ADMIN, "POST", "/api/access/rules", raw=b'{"enabled":false}',
                                 headers={"X-Bay-Auth": f"{n['nonce']}:{mac}"})[0], 403)

        # --- Rules ----------------------------------------------------------------
        rules = {"enabled": True, "everyone": ["status"], "sources": [
            {"name": "admin-laptop", "cidr": ADMIN, "allow": ["all"]},
            {"name": "ci-runner", "cidr": CI + "/32", "allow": ["status", "control", "console", "usbip"]},
            {"name": "desk", "cidr": DESK, "allow": ["status", "console"]},
        ]}
        code, d = signed(ADMIN, "POST", "/api/access/rules", rules)
        self.assertEqual(code, 200, d)
        self.assertEqual(d["rules"]["sources"][1], {"name": "ci-runner", "cidr": CI,
                                                    "allow": ["status", "control", "console", "usbip"]})
        self.assertEqual(d["source"], "admin-laptop")
        bad = {"sources": [{"name": "bad name", "cidr": "1.2.3.4", "allow": ["all"]}]}
        self.assertEqual(signed(ADMIN, "POST", "/api/access/rules", bad)[0], 400)
        bad = {"sources": [{"name": "x", "cidr": "1.2.3.300", "allow": ["all"]}]}
        self.assertEqual(signed(ADMIN, "POST", "/api/access/rules", bad)[0], 400)
        bad = {"everyone": ["web"]}
        self.assertEqual(signed(ADMIN, "POST", "/api/access/rules", bad)[0], 400)

        # Another host: status yes, the rest no
        code, s = get(OTHER, "/api/status")
        self.assertEqual((code, s["access"]["allow"]), (200, ["status"]))
        code, e = post(OTHER, "/api/power", {"action": "cycle", "ms": 10})
        self.assertEqual((code, e["reason"], e["service"], e["you"]), (403, "not_allowed", "control", OTHER))
        self.assertEqual(post(OTHER, "/api/aux", {"baud": 9600})[0], 403)                   # console's
        self.assertEqual(post(OTHER, "/api/console/ticket", {})[0], 403)
        self.assertEqual(post(OTHER, "/api/lease", {"ttl_s": 60})[0], 403)
        self.assertEqual(websocket(OTHER, "/console/ws/0"), 403)                             # no ticket
        self.assertTrue(closed_soon(tcp(OTHER, 4001)))                                       # RFC 2217
        self.assertTrue(closed_soon(tcp(OTHER, 4000)))                                       # raw
        self.assertEqual(post(ADMIN, "/api/power", {"action": "on"})[0], 200)

        # The web console needs a ticket from an address with the console right
        _, t = post(ADMIN, "/api/console/ticket", {})
        self.assertEqual(websocket(ADMIN, f"/console/ws/0?t={t['ticket']}"), 101)
        self.assertEqual(websocket(ADMIN, f"/console/ws/1?t={t['ticket']}"), 403)            # single use

        # --- Connections and kick -------------------------------------------------
        rfc = tcp(ADMIN, 4001)
        self.assertFalse(closed_soon(rfc, 0.5, keep=True))
        _, d = get(ADMIN, "/api/access")
        conn = next(c for c in d["connections"] if c["id"] == "rfc2217")
        self.assertEqual((conn["label"], conn["peer"]), ("RFC 2217", ADMIN))
        self.assertEqual(post(ADMIN, "/api/access/kick", {"id": "rfc2217"})[0], 403)        # admin only
        self.assertEqual(signed(OTHER, "POST", "/api/access/kick", {"id": "rfc2217"})[0], 200)   # the key, anywhere
        self.assertTrue(closed_soon(rfc))
        self.assertTrue(closed_soon(tcp(ADMIN, 4001)))                                       # a minute off
        self.assertEqual(signed(ADMIN, "POST", "/api/access/kick", {"id": "rfc2217"})[0], 404)
        _, d = signed(ADMIN, "GET", "/api/access")
        reasons = {(r["ip"], r["service"], r["reason"]) for r in d["refused"]}
        self.assertIn((OTHER, "control", "not_allowed"), reasons)
        self.assertIn((OTHER, "console", "not_allowed"), reasons)
        self.assertIn((ADMIN, "console", "kicked"), reasons)

        # --- Lease ------------------------------------------------------------------
        raw = tcp(DESK, 4000)                        # a raw console client, before the lease
        self.assertFalse(closed_soon(raw, 0.3, keep=True))
        code, d = post(CI, "/api/lease", {"ttl_s": 60, "note": "twister job 8812"})
        self.assertEqual(code, 200, d)
        self.assertEqual(d["lease"], {"holder": CI, "note": "twister job 8812", "remaining_s": 60, "yours": True})
        self.assertTrue(closed_soon(raw))            # everyone else's sessions go
        code, e = post(ADMIN, "/api/power", {"action": "cycle", "ms": 10})
        self.assertEqual((code, e["reason"]), (423, "reserved"))
        self.assertIn("twister job 8812", e["error"])
        self.assertEqual(get(ADMIN, "/api/status")[1]["access"]["lease"]["holder"], CI)
        self.assertEqual(post(CI, "/api/power", {"action": "cycle", "ms": 10})[0], 200)
        self.assertEqual(post(ADMIN, "/api/lease", {"ttl_s": 60})[0], 423)
        self.assertEqual(post(ADMIN, "/api/lease", {"release": True})[0], 403)              # not the holder
        self.assertEqual(post(CI, "/api/lease", {"ttl_s": 5})[0], 400)
        self.assertEqual(signed(ADMIN, "POST", "/api/lease", {"release": True})[0], 200)    # admin breaks it
        self.assertEqual(post(ADMIN, "/api/power", {"action": "on"})[0], 200)

        # --- /metrics, the local shell ----------------------------------------------
        conn = http.client.HTTPConnection("127.0.0.1", 80, timeout=5, source_address=(ADMIN, 0))
        conn.request("GET", "/metrics")
        metrics = conn.getresponse().read().decode()
        conn.close()
        self.assertIn('bay_access_refused_total{bay="b3"}', metrics)
        out = node.shell("bay access", "refused:")
        self.assertIn("rules:     on, 3 source(s)", out)
        self.assertIn("ci-runner 127.0.0.3", out)

        # --- Persistence: rules and key survive a restart -----------------------------
        node.stop()
        AccessSim.node = node = Node(ARGS.exe, self.flash)
        code, s = get(OTHER, "/api/status")
        self.assertEqual((s["access"]["claimed"], s["access"]["enabled"], s["access"]["allow"]),
                         (True, True, ["status"]))
        self.assertEqual(signed(ADMIN, "GET", "/api/access")[1]["rules"]["sources"][0]["name"], "admin-laptop")

        # --- Local recovery ---------------------------------------------------------
        node.shell("bay access reset", "open until claimed")
        code, s = get(OTHER, "/api/status")
        self.assertEqual((s["access"]["claimed"], s["access"]["enabled"]), (False, False))
        self.assertEqual(post(OTHER, "/api/reset", {"ms": 10})[0], 200)


def build(workspace: Path, out: Path) -> Path:
    subprocess.run(["west", "build", "-b", "native_sim/native/64", "-d", str(out), "-p", "auto", str(HERE)],
                   cwd=workspace, check=True)
    return out / "zephyr" / "zephyr.exe"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workspace", type=Path, default=Path("/ws"), help="west workspace")
    ap.add_argument("--build", type=Path, default=Path("/build"), help="build directories")
    ap.add_argument("--exe", type=Path, help="an already built node (zephyr.exe)")
    ARGS, rest = ap.parse_known_args()
    if ARGS.exe is None:
        ARGS.exe = build(ARGS.workspace, ARGS.build / "sim")
    unittest.main(argv=[sys.argv[0], *rest], verbosity=2)
