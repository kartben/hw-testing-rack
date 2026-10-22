"""Zephyr's USB/IP service with the rack's patches (zephyr/patches.yml), on native_sim.

Linux only (native_sim, host sockets); in the Zephyr build image, in a
workspace where `west patch apply` has run:

    python3 test_usbip.py [--workspace /ws] [--build /build/usbip] [--exe zephyr.exe]

Builds this directory (unless --exe is given) and starts it: the service on
Zephyr's virtual host controller, a device on the virtual bus with a loopback
function, a serial converter (src/serial_emu.c) and a mass-storage-like
function (src/storage_emu.c), the shell on stdin ("dut off" unplugs the
device, "dut on" plugs it back, "ra" sets the read-ahead, "emu" drives the
converter, "msd" the storage function, "sessions" lists the imported
devices).  The tests are a USB/IP client speaking the protocol over TCP
(port 3240), as `usbip list` and `usbip attach` do: the device list, an
import, transfers, the device going away in the middle of a session, a
serial converter read by a client a round trip away, with and without the
read-ahead, and mass storage requests of 120 KB, larger than the service's
buffer pool.

What this cannot cover: a hub (Zephyr has no virtual one), so the bus IDs
behind hub ports ("1-1.3") are not exercised; the timing of a real
controller.
"""

from __future__ import annotations

import argparse
import os
import re
import select
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
CMD_UNLINK, RET_UNLINK = 2, 4
ECONNRESET = 104
DIR_OUT, DIR_IN = 0, 1
DEVICE_SIZE = 312                      # struct usbip_devlist_data
GET_DEVICE_DESCRIPTOR = bytes([0x80, 6, 0, 1, 0, 0, 18, 0])
SET_INTERFACE_0_ALT_1 = bytes([0x01, 11, 1, 0, 0, 0, 0, 0])
GET_CONFIG_DESCRIPTOR = bytes([0x80, 6, 0, 2, 0, 0, 255, 0])
FTDI_SET_LATENCY_4MS = bytes([0x40, 9, 4, 0, 0, 0, 0, 0])
FTDI_PURGE_RX = bytes([0x40, 0, 1, 0, 0, 0, 0, 0])
FTDI_MPS = 64
FTDI_LSR_OVERRUN = 0x02
SERIAL_RATE = 11520                    # bytes/s: 115200 baud, 8N1
MSD_REQUEST = 122880                   # a mass storage request: 120 KB
EPIPE = 32
FAR_RTT = 0.04                         # s: a client across the network

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


def unlink_request(seq: int, victim: int) -> bytes:
    return struct.pack(">IIIIII", CMD_UNLINK, seq, 0x10001, DIR_OUT, 0, victim) + bytes(24)


def reply(s: socket.socket) -> tuple[int, int, int]:
    """The next reply, either kind: command, seqnum, status (IN data skipped)."""
    hdr = recvall(s, 48)
    command, seq, _, direction, _, status, actual = struct.unpack(">IIIIIiI", hdr[:28])
    if command == RET_SUBMIT and direction == DIR_IN and actual:
        recvall(s, actual)
    return command, seq, status


def device_descriptor(s: socket.socket, seq: int) -> bytes:
    submit(s, seq, 0, DIR_IN, 18, GET_DEVICE_DESCRIPTOR)
    rseq, status, data = ret_submit(s)
    assert (rseq, status) == (seq, 0), (rseq, status)
    return data


def serial_ep(s: socket.socket, seq: int) -> int:
    """The bulk IN endpoint of the serial converter (its interface's subclass is 0xFF)."""
    submit(s, seq, 0, DIR_IN, 255, GET_CONFIG_DESCRIPTOR)
    rseq, status, desc = ret_submit(s)
    assert (rseq, status) == (seq, 0), (rseq, status)
    i, serial = 0, False
    while i + 2 < len(desc) and desc[i]:
        if desc[i + 1] == 4:
            serial = desc[i + 6] == 0xFF
        elif desc[i + 1] == 5 and serial and desc[i + 2] & 0x80:
            return desc[i + 2] & 0x0F
        i += desc[i]
    raise AssertionError(f"no serial converter in {desc.hex()}")


def ftdi_split(replies: list[bytes]) -> tuple[bytes, list[bytes]]:
    """Data and status bytes of FTDI replies, checking their framing: packets of 64
    bytes but the last one of a reply, each with two status bytes first."""
    data, statuses = bytearray(), []
    for r in replies:
        for off in range(0, len(r), FTDI_MPS):
            pkt = r[off:off + FTDI_MPS]
            assert len(pkt) >= 2, f"a packet of {len(pkt)} bytes in {r.hex()}"
            assert len(pkt) == FTDI_MPS or off + FTDI_MPS >= len(r), f"a short packet inside {r.hex()}"
            statuses.append(pkt[:2])
            data += pkt[2:]
    return bytes(data), statuses


def storage_eps(s: socket.socket, seq: int) -> tuple[int, int]:
    """The bulk IN and OUT endpoints of the mass storage function (class 8)."""
    submit(s, seq, 0, DIR_IN, 255, GET_CONFIG_DESCRIPTOR)
    rseq, status, desc = ret_submit(s)
    assert (rseq, status) == (seq, 0), (rseq, status)
    i, storage, eps = 0, False, {}
    while i + 2 < len(desc) and desc[i]:
        if desc[i + 1] == 4:
            storage = desc[i + 5] == 0x08
        elif desc[i + 1] == 5 and storage:
            eps[desc[i + 2] & 0x80] = desc[i + 2] & 0x0F
        i += desc[i]
    assert len(eps) == 2, f"no mass storage function in {desc.hex()}"
    return eps[0x80], eps[0]


def storage_pattern(n: int) -> bytes:
    """What the storage function sends and expects: byte i is i ^ i >> 8 ^ i >> 16."""
    return bytes((i ^ i >> 8 ^ i >> 16) & 0xFF for i in range(n))


def missing(data: bytes) -> int:
    """Bytes missing in the converter's counter."""
    return sum((b - a - 1) % 256 for a, b in zip(data, data[1:]))


def readable(s: socket.socket, timeout: float) -> bool:
    return bool(select.select([s], [], [], timeout)[0])


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

    def sessions(self) -> list[tuple[str, str, int]]:
        """The imported devices, as usbip_get_sessions() gives them: bus ID, client, since."""
        start = self.node.mark()
        self.node.cmd("sessions")
        with self.node.lock:
            out = self.node.out[start:]
        return [(b.decode(), a.decode(), int(t))
                for b, a, t in re.findall(rb"SIM: session (\S+) from (\S+) since (\d+)", out)]

    def test_2a_sessions(self):
        """The application sees the imported device, its client, and when it went."""
        self.listed("1-1")
        self.assertEqual(self.sessions(), [])
        s = attach("1-1")
        self.assertIsNotNone(s)
        self.addCleanup(s.close)
        device_descriptor(s, 1)
        sessions = self.sessions()
        self.assertEqual([(b, a) for b, a, _ in sessions], [("1-1", "127.0.0.1")])
        self.assertGreater(sessions[0][2], 0)
        s.close()
        end = time.monotonic() + 5
        while self.sessions() and time.monotonic() < end:
            time.sleep(0.1)
        self.assertEqual(self.sessions(), [])

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

    def test_5_unlink(self):
        """A URB is answered once: unlinked, or completed then unlinked too late."""
        self.listed("1-1")
        s = attach("1-1")
        self.assertIsNotNone(s)
        submit(s, 1, 0, DIR_OUT, 0, SET_INTERFACE_0_ALT_1)
        self.assertEqual(ret_submit(s)[:2], (1, 0))
        # The device has data for a bulk IN: an unlink sent 0 to 2 ms after
        # it races its completion
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        seq = 2
        outcomes = set()
        for i in range(200):
            urb, unl, check = seq, seq + 1, seq + 2
            seq += 3
            submit(s, urb, 1, DIR_IN, 64)
            time.sleep((i % 100) / 50000)
            s.sendall(unlink_request(unl, urb))
            completed = False
            while True:
                command, rseq, status = reply(s)
                if command == RET_SUBMIT:
                    self.assertEqual(rseq, urb)
                    completed = True
                    continue
                self.assertEqual((command, rseq), (RET_UNLINK, unl))
                break
            # Unlinked: no RET_SUBMIT; completed first: RET_UNLINK status 0
            self.assertEqual(status, 0 if completed else -ECONNRESET, (completed, status))
            outcomes.add(completed)
            # Nothing more comes for the URB
            self.assertEqual(device_descriptor(s, check)[:2], bytes([18, 1]))
        s.close()
        print(f"unlink outcomes seen (completed first?): {sorted(outcomes)}", file=sys.stderr)

    def serial_session(self, mode: str, raw: bool = False) -> tuple[socket.socket, int]:
        """A session on the serial converter, its latency timer at 4 ms, read ahead in
        `mode`: the socket and the endpoint."""
        self.node.cmd("emu reset raw" if raw else "emu reset")
        self.node.cmd(f"ra {mode}")
        self.addCleanup(self.node.cmd, "ra none")
        self.listed("1-1")
        s = attach("1-1")
        self.assertIsNotNone(s)
        self.addCleanup(s.close)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        ep = serial_ep(s, 1)
        submit(s, 2, 0, DIR_OUT, 0, FTDI_SET_LATENCY_4MS)
        self.assertEqual(ret_submit(s)[:2], (2, 0))
        return s, ep

    def emu_stats(self) -> dict[str, int]:
        start = self.node.mark()
        self.node.cmd("emu stats")
        with self.node.lock:
            out = self.node.out[start:]
        m = re.search(rb"SIM: emu made (\d+) dropped (\d+) purged (\d+)", out)
        self.assertIsNotNone(m, out)
        return dict(zip(("made", "dropped", "purged"), map(int, m.groups())))

    def read_far(self, s: socket.socket, ep: int, seconds: float, seq: int,
                 at: tuple = ()) -> list[tuple[float, bytes]]:
        """Read the endpoint as a client a round trip away does: two requests of 512
        bytes, each sent again FAR_RTT after its answer, for `seconds`, with the
        converter's data coming in at SERIAL_RATE once the first requests are sent.
        `at`: (time, action) along the way, a shell command (str) or a control
        request (bytes).  Each request is answered once.  Returns (time, data) of
        the answers."""
        start = time.monotonic()
        actions = sorted(((0.0, f"emu rate {SERIAL_RATE}"), *at))
        waiting, controls, due, replies = set(), set(), [], []
        for _ in range(2):
            submit(s, seq, ep, DIR_IN, 512)
            waiting.add(seq)
            seq += 1
        while True:
            now = time.monotonic() - start
            while actions and actions[0][0] <= now:
                action = actions.pop(0)[1]
                if isinstance(action, str):
                    self.node.cmd(action)
                else:
                    submit(s, seq, 0, DIR_OUT, 0, action)
                    controls.add(seq)
                    seq += 1
            while due and due[0] <= now:
                due.pop(0)
                if now < seconds:
                    submit(s, seq, ep, DIR_IN, 512)
                    waiting.add(seq)
                    seq += 1
            if now >= seconds and not due and not controls:
                self.node.cmd("emu rate 0")
                return replies
            if not readable(s, 0.005):
                continue
            rseq, status, data = ret_submit(s)
            self.assertEqual(status, 0, rseq)
            if rseq in controls:
                controls.remove(rseq)
                continue
            self.assertIn(rseq, waiting, "an answer to no request, or a second one")
            waiting.remove(rseq)
            replies.append((time.monotonic() - start, data))
            due.append(time.monotonic() - start + FAR_RTT)

    def test_6_read_ahead_ftdi(self):
        """An FTDI converter read ahead: nothing lost, framing and line errors kept."""
        s, ep = self.serial_session("ftdi")
        replies = self.read_far(s, ep, 2.0, 10, at=((1.0, f"emu lsr {FTDI_LSR_OVERRUN}"),))
        stats = self.emu_stats()
        data, statuses = ftdi_split([d for _, d in replies])
        self.assertEqual(stats["dropped"], 0, stats)
        self.assertEqual(missing(data), 0)
        self.assertGreater(len(data), SERIAL_RATE * 1.5, stats)
        self.assertTrue(any(st[1] & FTDI_LSR_OVERRUN for st in statuses), "the line error was lost")
        # The 4 ms packets were merged: at most two answers per round trip
        self.assertLessEqual(len(replies), 2 * 2.0 / FAR_RTT + 2)
        print(f"read ahead: {len(data)} bytes in {len(replies)} answers, {stats}", file=sys.stderr)

    def test_7_no_read_ahead(self):
        """The same without the read-ahead: the converter's FIFO overflows."""
        s, ep = self.serial_session("none")
        replies = self.read_far(s, ep, 2.0, 10)
        stats = self.emu_stats()
        data, _ = ftdi_split([d for _, d in replies])
        self.assertGreater(stats["dropped"], 0, stats)
        self.assertGreater(missing(data), 0)
        print(f"no read-ahead: {len(data)} bytes in {len(replies)} answers, {stats}", file=sys.stderr)

    def test_8_read_ahead_stream(self):
        """A converter with no framing, read ahead: nothing lost."""
        s, ep = self.serial_session("stream", raw=True)
        replies = self.read_far(s, ep, 2.0, 10)
        stats = self.emu_stats()
        data = b"".join(d for _, d in replies)
        self.assertEqual(stats["dropped"], 0, stats)
        self.assertEqual(missing(data), 0)
        self.assertGreater(len(data), SERIAL_RATE * 1.5, stats)

    def test_9_read_ahead_idle_unlink_purge(self):
        """Read ahead with no data, a request unlinked while waiting, a purge."""
        s, ep = self.serial_session("ftdi")
        submit(s, 10, ep, DIR_IN, 512)
        submit(s, 11, ep, DIR_IN, 512)
        # The first status comes, then nothing: status packets alone are not kept
        self.assertEqual(ret_submit(s), (10, 0, bytes([0x01, 0x60])))
        self.assertFalse(readable(s, 0.3), "an answer with no data")
        # A new modem status comes
        submit(s, 12, ep, DIR_IN, 512)
        self.node.cmd("emu status 0x11")
        self.assertEqual(ret_submit(s), (11, 0, bytes([0x11, 0x60])))
        # Unlinked while waiting for data: RET_UNLINK only
        s.sendall(unlink_request(13, 12))
        self.assertEqual(reply(s), (RET_UNLINK, 13, -ECONNRESET))
        self.assertFalse(readable(s, 0.2), "an answer to an unlinked request")
        # Reading again, with a purge in the middle
        replies = self.read_far(s, ep, 1.5, 20, at=((0.7, FTDI_PURGE_RX),))
        stats = self.emu_stats()
        data, _ = ftdi_split([d for _, d in replies])
        self.assertEqual(stats["dropped"], 0, stats)
        self.assertGreater(len(data), SERIAL_RATE, stats)
        self.assertTrue(any(t > 0.8 and len(d) > 2 for t, d in replies), "no data after the purge")

    def storage_session(self) -> tuple[socket.socket, int, int]:
        """A session on the mass storage function: the socket, its IN and OUT endpoints."""
        self.node.cmd("msd reset")
        self.addCleanup(self.node.cmd, "msd reset")
        self.listed("1-1")
        s = attach("1-1")
        self.assertIsNotNone(s)
        self.addCleanup(s.close)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return (s, *storage_eps(s, 1))

    def msd_stats(self) -> dict[str, int]:
        start = self.node.mark()
        self.node.cmd("msd stats")
        with self.node.lock:
            out = self.node.out[start:]
        m = re.search(rb"SIM: msd in (\d+) out (\d+) bad (\d+)", out)
        self.assertIsNotNone(m, out)
        return dict(zip(("in", "out", "bad"), map(int, m.groups())))

    def test_9a_large_in(self):
        """Reads of 120 KB, more than the pool: whole, ending short, ending on a ZLP."""
        s, ep_in, _ = self.storage_session()
        for seq, (device_sends, zlp) in enumerate(((MSD_REQUEST, False), (100000, False),
                                                   (8192, True)), 2):
            self.node.cmd(f"msd in {device_sends}" + (" zlp" if zlp else ""))
            submit(s, seq, ep_in, DIR_IN, MSD_REQUEST)
            rseq, status, data = ret_submit(s)
            self.assertEqual((rseq, status, len(data)), (seq, 0, device_sends))
            self.assertEqual(data, storage_pattern(device_sends), "data lost, repeated or moved")

    def test_9b_large_out(self):
        """Writes of 120 KB and of a length that is no multiple of anything."""
        s, _, ep_out = self.storage_session()
        sent = 0
        for seq, n in enumerate((MSD_REQUEST, 10000), 2):
            data = storage_pattern(sent + n)[sent:]
            submit(s, seq, ep_out, DIR_OUT, n, data=data)
            self.assertEqual(ret_submit(s)[:2], (seq, 0))
            sent += n
        self.assertEqual(self.msd_stats(), {"in": 0, "out": sent, "bad": 0})

    def test_9c_large_unlink(self):
        """A 120 KB read, then a write, unlinked half-way: RET_UNLINK only."""
        s, ep_in, ep_out = self.storage_session()
        self.node.cmd("msd rate 1")
        self.node.cmd(f"msd in {MSD_REQUEST}")
        submit(s, 2, ep_in, DIR_IN, MSD_REQUEST)
        submit(s, 3, ep_out, DIR_OUT, MSD_REQUEST, data=storage_pattern(MSD_REQUEST))
        time.sleep(0.5)
        stats = self.msd_stats()
        self.assertTrue(0 < stats["in"] < MSD_REQUEST and 0 < stats["out"] < MSD_REQUEST, stats)
        s.sendall(unlink_request(4, 2) + unlink_request(5, 3))
        self.assertEqual({reply(s), reply(s)},
                         {(RET_UNLINK, 4, -ECONNRESET), (RET_UNLINK, 5, -ECONNRESET)})
        self.assertFalse(readable(s, 0.3), "an answer to an unlinked request")
        # Nothing more goes on either endpoint
        stats = self.msd_stats()
        time.sleep(0.2)
        self.assertEqual(self.msd_stats()["out"], stats["out"])
        self.assertEqual(device_descriptor(s, 6)[:2], bytes([18, 1]))

    def test_9d_large_stall(self):
        """The device halts the endpoint in the third segment: -EPIPE, and the data before."""
        s, ep_in, _ = self.storage_session()
        self.node.cmd("msd stall 10240")
        self.node.cmd(f"msd in {MSD_REQUEST}")
        submit(s, 2, ep_in, DIR_IN, MSD_REQUEST)
        rseq, status, data = ret_submit(s)
        self.assertEqual((rseq, status, len(data)), (2, -EPIPE, 10240))
        self.assertEqual(data, storage_pattern(10240))
        # CLEAR_FEATURE(ENDPOINT_HALT) and the endpoint works again
        submit(s, 3, 0, DIR_OUT, 0, bytes([0x02, 1, 0, 0, 0x80 | ep_in, 0, 0, 0]))
        self.assertEqual(ret_submit(s)[:2], (3, 0))
        self.node.cmd("msd in 5000")
        submit(s, 4, ep_in, DIR_IN, MSD_REQUEST)
        self.assertEqual(ret_submit(s), (4, 0, storage_pattern(5000)))


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
