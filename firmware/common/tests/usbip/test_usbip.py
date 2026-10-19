"""Zephyr's USB/IP service with the rack's patches (zephyr/patches.yml), on native_sim.

Linux only (native_sim, host sockets); in the Zephyr build image, in a
workspace where `west patch apply` has run:

    python3 test_usbip.py [--workspace /ws] [--build /build/usbip] [--exe zephyr.exe]

Builds this directory (unless --exe is given) and starts it: the service on
Zephyr's virtual host controller, a loopback device on the virtual bus, the
shell on stdin ("dut off" unplugs the device, "dut on" plugs it back).  The
tests are a USB/IP client speaking the protocol over TCP (port 3240), as
`usbip list` and `usbip attach` do: the device list, an import, transfers,
and the device going away in the middle of a session.

What this cannot cover: a hub (Zephyr has no virtual one), so the bus IDs
behind hub ports ("1-1.3") are not exercised; the timing of a real
controller.
"""

from __future__ import annotations

import argparse
import os
import socket
import struct
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = 3240
VERSION = 0x0111
OP_REQ_DEVLIST, OP_REP_DEVLIST = 0x8005, 0x0005
OP_REQ_IMPORT, OP_REP_IMPORT = 0x8003, 0x0003
CMD_SUBMIT, RET_SUBMIT = 1, 3
DIR_OUT, DIR_IN = 0, 1
DEVICE_SIZE = 312                      # struct usbip_devlist_data
GET_DEVICE_DESCRIPTOR = bytes([0x80, 6, 0, 1, 0, 0, 18, 0])
SET_INTERFACE_0_ALT_1 = bytes([0x01, 11, 1, 0, 0, 0, 0, 0])

ARGS: argparse.Namespace


class Node:
    """The simulated node: its shell on a pipe."""

    def __init__(self, exe: Path):
        self.proc = subprocess.Popen([str(exe), "--uart_stdinout"],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        self.out = b""
        self.lock = threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()
        self.wait_for(b"SIM: ready (0)", 20)

    def _read(self) -> None:
        while data := os.read(self.proc.stdout.fileno(), 4096):
            with self.lock:
                self.out += data

    def wait_for(self, text: bytes, timeout: float = 5, start: int = 0) -> None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.lock:
                if text in self.out[start:]:
                    return
            if self.proc.poll() is not None:
                raise AssertionError(f"the node exited ({self.proc.returncode}) waiting for {text!r}")
            time.sleep(0.05)
        raise AssertionError(f"no {text!r} from the node:\n{self.tail()}")

    def mark(self) -> int:
        with self.lock:
            return len(self.out)

    def cmd(self, line: str) -> None:
        start = self.mark()
        self.proc.stdin.write(line.encode() + b"\n")
        self.wait_for(f"SIM: {line}: 0".encode(), start=start)

    def tail(self, n: int = 3000) -> str:
        with self.lock:
            return self.out[-n:].decode(errors="replace")

    def stop(self) -> None:
        self.proc.kill()
        self.proc.wait()


def recvall(s: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = s.recv(n - len(data))
        if not chunk:
            raise ConnectionError(f"closed after {len(data)} of {n} bytes")
        data += chunk
    return data


def parse_device(d: bytes) -> dict:
    busnum, devnum, speed, vid, pid, bcd, cls, sub, proto, cfg, ncfg, nif = \
        struct.unpack(">IIIHHHBBBBBB", d[288:312])
    return {"path": d[:256].split(b"\0")[0].decode(), "busid": d[256:288].split(b"\0")[0].decode(),
            "busnum": busnum, "devnum": devnum, "vid": vid, "pid": pid, "class": cls,
            "interfaces": nif}


def devlist() -> list[dict]:
    with socket.create_connection(("127.0.0.1", PORT), timeout=5) as s:
        s.sendall(struct.pack(">HHI", VERSION, OP_REQ_DEVLIST, 0))
        _, code, status, ndev = struct.unpack(">HHII", recvall(s, 12))
        assert code == OP_REP_DEVLIST and status == 0, (code, status)
        devs = []
        for _ in range(ndev):
            dev = parse_device(recvall(s, DEVICE_SIZE))
            dev["ifaces"] = [recvall(s, 4) for _ in range(dev["interfaces"])]
            devs.append(dev)
        return devs


def wait_listed(busid: str, timeout: float = 5) -> dict:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        for dev in devlist():
            if dev["busid"] == busid:
                return dev
        time.sleep(0.1)
    raise AssertionError(f"{busid} not listed")


def attach(busid: str) -> socket.socket | None:
    """OP_REQ_IMPORT: the session's socket, or None if refused."""
    s = socket.create_connection(("127.0.0.1", PORT), timeout=5)
    s.sendall(struct.pack(">HHI", VERSION, OP_REQ_IMPORT, 0) + busid.encode().ljust(32, b"\0"))
    _, code, status = struct.unpack(">HHI", recvall(s, 8))
    if status != 0:
        s.close()
        return None
    dev = parse_device(recvall(s, DEVICE_SIZE))
    assert dev["busid"] == busid, dev
    return s


def submit(s: socket.socket, seq: int, ep: int, direction: int, length: int,
           setup: bytes = bytes(8), data: bytes = b"") -> None:
    s.sendall(struct.pack(">IIIII", CMD_SUBMIT, seq, 0x10001, direction, ep)
              + struct.pack(">IIiii", 0, length, 0, 0, 0) + setup + data)


def ret_submit(s: socket.socket) -> tuple[int, int, bytes]:
    """The next RET_SUBMIT: seqnum, status, IN data."""
    hdr = recvall(s, 48)
    command, seq, _, direction, _, status, actual = struct.unpack(">IIIIIiI", hdr[:28])
    assert command == RET_SUBMIT, command
    data = recvall(s, actual) if direction == DIR_IN and actual else b""
    return seq, status, data


def device_descriptor(s: socket.socket, seq: int) -> bytes:
    submit(s, seq, 0, DIR_IN, 18, GET_DEVICE_DESCRIPTOR)
    rseq, status, data = ret_submit(s)
    assert (rseq, status) == (seq, 0), (rseq, status)
    return data


def closed_within(s: socket.socket, timeout: float) -> bool:
    """Whether the node closes the session (whatever completions come first)."""
    s.settimeout(0.2)
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if not s.recv(4096):
                return True
        except socket.timeout:
            continue
        except ConnectionError:
            return True
    return False


class UsbipTest(unittest.TestCase):
    node: Node

    @classmethod
    def setUpClass(cls):
        cls.node = Node(ARGS.exe)
        wait_listed("1-1")

    @classmethod
    def tearDownClass(cls):
        cls.node.stop()

    def tearDown(self):
        self.assertIsNone(self.node.proc.poll(), f"the node died:\n{self.node.tail()}")

    def listed(self, busid: str) -> dict:
        try:
            return wait_listed(busid)
        except AssertionError as e:
            raise AssertionError(f"{e}:\n{self.node.tail()}") from None

    def test_1_list(self):
        devs = devlist()
        self.assertEqual(len(devs), 1, devs)
        dev = devs[0]
        self.assertEqual(dev["busid"], "1-1")
        self.assertEqual(dev["path"], "/sys/bus/usb/devices/usb1/1-1")
        self.assertNotEqual(dev["class"], 0x09)
        self.assertGreaterEqual(dev["interfaces"], 1)

    def test_2_attach_transfer_detach(self):
        dev = self.listed("1-1")
        s = attach("1-1")
        self.assertIsNotNone(s)
        desc = device_descriptor(s, 1)
        self.assertEqual(desc[:2], bytes([18, 1]))
        self.assertEqual(struct.unpack("<H", desc[8:10])[0], dev["vid"])
        # Exported already: a second import is refused
        self.assertIsNone(attach("1-1"))
        # The client goes: the context is free again
        s.close()
        end = time.monotonic() + 5
        while (s2 := attach("1-1")) is None and time.monotonic() < end:
            time.sleep(0.1)
        self.assertIsNotNone(s2, "the context stayed taken after the client left")
        self.assertEqual(device_descriptor(s2, 1)[:2], bytes([18, 1]))
        s2.close()

    def test_3_unplug_during_session(self):
        self.listed("1-1")
        s = attach("1-1")
        self.assertIsNotNone(s)
        device_descriptor(s, 1)
        submit(s, 2, 0, DIR_OUT, 0, SET_INTERFACE_0_ALT_1)
        self.assertEqual(ret_submit(s)[:2], (2, 0))
        # Bulk IN transfers in flight, then the device goes
        for seq in range(3, 11):
            submit(s, seq, 1, DIR_IN, 64)
        self.node.cmd("dut off")
        self.assertTrue(closed_within(s, 5), f"the session outlived its device:\n{self.node.tail()}")
        s.close()
        time.sleep(0.5)
        self.assertEqual(devlist(), [])
        # It comes back under the same bus ID, and works
        self.node.cmd("dut on")
        self.listed("1-1")
        s = attach("1-1")
        self.assertIsNotNone(s)
        self.assertEqual(device_descriptor(s, 1)[:2], bytes([18, 1]))
        s.close()

    def test_4_unplug_without_session(self):
        self.listed("1-1")
        for _ in range(3):
            self.node.cmd("dut off")
            time.sleep(0.3)
            self.assertEqual(devlist(), [])
            self.node.cmd("dut on")
            self.listed("1-1")


def build(workspace: Path, out: Path) -> Path:
    subprocess.run(["west", "build", "-b", "native_sim/native/64", "-d", str(out), "-p", "auto",
                    str(HERE)], cwd=workspace, check=True)
    return out / "zephyr" / "zephyr.exe"


def main() -> None:
    global ARGS
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", type=Path, default=Path("/ws"))
    p.add_argument("--build", type=Path, default=Path("/build/usbip"))
    p.add_argument("--exe", type=Path)
    ARGS, rest = p.parse_known_args()
    if ARGS.exe is None:
        ARGS.exe = build(ARGS.workspace, ARGS.build)
    unittest.main(argv=[sys.argv[0], *rest], verbosity=2)


if __name__ == "__main__":
    main()
