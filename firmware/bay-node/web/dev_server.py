"""Serve the bay node web page with a simulated node, to work on the UI without one.

    python firmware/bay-node/web/dev_server.py [port]      # then open http://localhost:8766

Same endpoints and JSON as src/web.c, the web console's WebSockets
(/console/ws/<n>) included.  The "node" is a dict the POSTs change; its DUT
is a fake Zephyr board that boots, logs in colour and runs a tiny shell on
the console.  /dev/fault trips a fake over-current, /dev/attach toggles a
fake USB/IP client.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import random
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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


def status() -> dict:
    dut = node["dut"]
    ma = dut_current_ma(time.monotonic()) if dut["on"] else 0
    mv = (5080 - ma // 10) if dut["on"] else 0
    dut.update(ma=ma, mv=mv, mw=ma * mv // 1000)
    node["path"] = "classic" if node["force_classic"] else "usbip"
    fmt = f"{aux['data_bits']}{aux['parity'][0].upper()}{aux['stop_bits']}"
    return {**node, "uptime_s": int(time.monotonic() - START),
            "aux": {"baud": aux["baud"], "format": fmt, "port": 4000, "rfc2217_port": 4001,
                    "web_clients": len(console.clients), "rfc2217": False, "raw": False,
                    "rx": len(console.log), "tx": console.tx, "dropped": 0}}


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
        if self.path in STATIC:
            path, ctype = STATIC[self.path]
            self.send(200, path.read_bytes(), ctype)
        elif self.path.startswith("/console/ws/"):
            self.websocket(int(self.path.rsplit("/", 1)[1]))
        elif self.path == "/api/status":
            self.json(200, status())
        elif self.path == "/api/aux":
            self.json(200, aux_doc())
        elif self.path == "/metrics":
            self.send(200, metrics().encode(), "text/plain")
        elif self.path == "/dev/fault":
            node["dut"].update(on=False, latched=True, faults=node["dut"]["faults"] + 1)
            self.json(200, status())
        elif self.path == "/dev/attach":
            node["usb"]["sessions"] = 1 - node["usb"]["sessions"]
            self.json(200, status())
        else:
            self.json(404, {"error": "not found"})

    def websocket(self, slot: int) -> None:
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
        try:
            while (frame := ws_read(self.rfile)) is not None:
                opcode, data = frame
                if opcode == 8:
                    break
                if opcode in (1, 2):
                    console.type(data)
        finally:
            with console.lock:
                console.clients.pop(slot, None)
        self.close_connection = True

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
        self.json(200, status())

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
