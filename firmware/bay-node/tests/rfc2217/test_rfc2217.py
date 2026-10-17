"""Host test of the bay node's RFC 2217 server (src/rfc2217.c) against pyserial's client.

    pip install pyserial
    python firmware/bay-node/tests/rfc2217/test_rfc2217.py     # CC=gcc by default

rfc2217.c is built into a shared library with a small shim (shim.c) and
driven from a local TCP server whose "UART" is looped back: every byte the
client writes comes back to it, as with TX wired to RX on the AUX connector.
"""

from __future__ import annotations

import ctypes
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import serial

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"

BYTES_CB = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t)
SETTING_CB = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)


def build_shim(outdir: Path) -> ctypes.CDLL:
    lib = outdir / ("rfc2217_shim.dll" if os.name == "nt" else "librfc2217_shim.so")
    cc = os.environ.get("CC", "gcc")
    subprocess.run([cc, "-shared", "-fPIC", "-O1", "-Wall", "-Wextra", "-Wno-unused-parameter",
                    "-Werror", "-I", str(SRC), str(HERE / "shim.c"), str(SRC / "rfc2217.c"),
                    "-o", str(lib)], check=True)
    return ctypes.CDLL(str(lib))


class LoopbackNode:
    """A bay node whose AUX TX is wired to its RX, behind the RFC 2217 server."""

    def __init__(self, lib: ctypes.CDLL):
        self.lib = lib
        self.port = {"baud": 115200, "datasize": 8, "parity": 1, "stopsize": 1}
        self.controls: list[int] = []
        self.purges: list[int] = []
        self.conn: socket.socket | None = None
        self._bytes_cb = BYTES_CB(self._on_bytes)
        self._setting_cb = SETTING_CB(self._on_setting)
        lib.shim_start.argtypes = [BYTES_CB, SETTING_CB]
        lib.shim_input.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        lib.shim_escape.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p,
                                    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        lib.shim_escape.restype = ctypes.c_size_t
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.addr = self.listener.getsockname()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            conn, _ = self.listener.accept()
            self.conn = conn
            self.lib.shim_start(self._bytes_cb, self._setting_cb)
            while True:
                try:
                    data = conn.recv(1024)
                except OSError:
                    break
                if not data:
                    break
                self.lib.shim_input(data, len(data))
            conn.close()

    def _on_bytes(self, kind: int, buf, length: int) -> None:
        data = ctypes.string_at(buf, length)
        if kind == 1:
            self.conn.sendall(data)
            return
        # UART TX looped to RX: escape for telnet and send back
        out = ctypes.create_string_buffer(2 * length + 1)
        used = ctypes.c_size_t()
        n = self.lib.shim_escape(data, length, out, len(out), ctypes.byref(used))
        assert used.value == length
        self.conn.sendall(out.raw[:n])

    def _on_setting(self, what: int, value: int) -> int:
        if what == 0:
            if 300 <= value <= 5_000_000:
                self.port["baud"] = value
            return self.port["baud"]
        if what == 1:
            if 5 <= value <= 8:
                self.port["datasize"] = value
            return self.port["datasize"]
        if what == 2:
            if value in (1, 2, 3):      # none, odd, even; mark/space refused
                self.port["parity"] = value
            return self.port["parity"]
        if what == 3:
            if value in (1, 2):         # 1.5 stop bits refused
                self.port["stopsize"] = value
            return self.port["stopsize"]
        if what == 4:
            self.controls.append(value)
            return value
        if what == 5:
            self.purges.append(value)
        return 0


class Rfc2217Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # a loaded DLL stays locked on Windows
        cls.node = LoopbackNode(build_shim(Path(cls.tmp.name)))
        host, port = cls.node.addr
        cls.url = f"rfc2217://{host}:{port}"

    def open(self, **kw) -> serial.Serial:
        return serial.serial_for_url(self.url, timeout=1, **kw)

    def test_open_sets_the_port(self) -> None:
        with self.open(baudrate=9600):
            self.assertEqual(self.node.port["baud"], 9600)
            self.assertEqual(self.node.port["datasize"], 8)
            self.assertEqual(self.node.port["parity"], 1)
            self.assertIn(1, self.node.controls)  # no flow control

    def test_loopback_all_byte_values(self) -> None:
        payload = bytes(range(256)) * 4      # includes 0xFF (IAC) and CR NUL
        with self.open(baudrate=115200) as s:
            s.write(payload)
            got = b""
            deadline = time.monotonic() + 3
            while len(got) < len(payload) and time.monotonic() < deadline:
                got += s.read(len(payload) - len(got))
            self.assertEqual(got, payload)

    def test_runtime_reconfigure(self) -> None:
        with self.open(baudrate=115200) as s:
            s.baudrate = 921600
            s.bytesize = serial.SEVENBITS
            s.parity = serial.PARITY_EVEN
            s.stopbits = serial.STOPBITS_TWO
            self.assertEqual(self.node.port, {"baud": 921600, "datasize": 7, "parity": 3,
                                              "stopsize": 2})

    def test_unsupported_setting_is_rejected(self) -> None:
        with self.open(baudrate=115200) as s:
            with self.assertRaises((ValueError, serial.SerialException)):
                s.parity = serial.PARITY_MARK

    def test_break_dtr_rts_purge(self) -> None:
        with self.open(baudrate=115200) as s:
            self.node.controls.clear()
            self.node.purges.clear()
            s.send_break(0.05)
            s.dtr = False
            s.rts = False
            s.dtr = True
            s.reset_input_buffer()
            self.assertEqual(self.node.controls, [5, 6, 9, 12, 8])
            self.assertEqual(self.node.purges, [1])


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
