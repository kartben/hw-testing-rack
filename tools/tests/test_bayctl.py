"""Tests for tools/bayctl.py, against the repository's rack and the firmware's simulated node.

    python -m unittest discover -s tools/tests -v

No rack needed: the node API is firmware/bay-node/web/dev_server.py (same endpoints and JSON
as the firmware), the AUX UART a local echo server.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools"))

import bayctl  # noqa: E402

LAB_EXAMPLE = REPO / "config" / "lab.example.yaml"
DEV_SERVER = REPO / "firmware" / "bay-node" / "web" / "dev_server.py"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Config(unittest.TestCase):
    def setUp(self):
        self.bays = bayctl.load_bays(lab_yaml=LAB_EXAMPLE)

    def test_defaults_and_overrides(self):
        b = self.bays
        self.assertEqual(b["A1"].platform, "nucleo_f401re")             # family resolved by the lab file
        self.assertIsNone(b["A2"].platform)                             # family left open
        self.assertIn("nucleo_h743zi", b["A2"].choices)
        self.assertEqual(b["A3"].platform, "nrf52840dk/nrf52840")      # from boards.yaml
        self.assertEqual(b["A3"].runner, "nrfutil")
        self.assertEqual(b["B3"].console, "aux")
        self.assertFalse(b["C4"].ci)
        self.assertEqual(b["D2"].host, "bay-d2.local")
        self.assertEqual(b["D2"].url, "http://bay-d2.local")

    def test_hwmap(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries, warnings = bayctl.hwmap(self.bays, Path(tmp), "python3", "/opt/rack/tools/bayctl.py", None)
            by = {e["fixtures"][0]: e for e in entries}
            self.assertNotIn("bay:C4", by)                              # ci: false
            self.assertNotIn("bay:A2", by)                              # no platform: left out, with a warning
            self.assertTrue(any("bays.A2.platform" in w for w in warnings))
            a1 = by["bay:A1"]
            self.assertTrue(a1["connected"])
            self.assertEqual(a1["id"], "066DFF515251717867193542")
            self.assertTrue(a1["serial"].startswith("/dev/serial/by-id/"))
            b2 = by["bay:B2"]                                           # esp32: the port is the probe id
            self.assertEqual(b2["id"], b2["serial"])
            b3 = by["bay:B3"]                                           # AUX console through serial_pty
            self.assertEqual(b3["serial_pty"], "python3 /opt/rack/tools/bayctl.py pty B3")
            self.assertNotIn("serial", b3)
            a4 = by["bay:A4"]                                           # no console path yet
            self.assertFalse(a4["connected"])
            self.assertTrue(any("A4" in w and "nrfutil" in w for w in warnings))   # A4 and C2: two nrfutil, no id
            pre = Path(a1["pre_script"]).read_text()
            self.assertIn("prepare A1", pre)
            self.assertTrue(pre.startswith("#!/bin/sh"))

    def test_exports(self):
        lg = bayctl.export_labgrid(self.bays, "python3", "bayctl.py")
        t = lg["targets"]["bay-b3"]
        self.assertEqual(t["resources"]["NetworkSerialPort"],
                         {"host": "bay-b3.local", "port": 4001, "speed": 115200, "protocol": "rfc2217"})
        self.assertEqual(t["drivers"]["ExternalPowerDriver"]["cmd_cycle"], "python3 bayctl.py power B3 cycle")
        pdu = bayctl.export_pdudaemon(self.bays, "python3", "bayctl.py")
        cmd = pdu["pdus"]["hw-testing-rack"]["cmd_on"]
        self.assertEqual(cmd % 3, "python3 bayctl.py power-port 3 on")   # PDUDaemon formats with %
        self.assertEqual(pdu["_ports"][1], "A1")

    def test_unknown_bay(self):
        with self.assertRaises(bayctl.BayError):
            bayctl.get_bay(self.bays, "Z9")


class Usbip(unittest.TestCase):
    def test_list(self):
        out = ("Exportable USB devices\n======================\n - bay-b3.local\n"
               "        1-1: SEGGER : J-Link (1366:1015)\n           : /sys/devices/platform/1-1\n"
               "           : Miscellaneous Device / ? / Interface Association (ef/02/01)\n")
        self.assertEqual(bayctl.parse_usbip_list(out), [("1-1", "SEGGER : J-Link (1366:1015)")])

    def test_port(self):
        out = ("Imported USB devices\n====================\nPort 00: <Port in Use> at Full Speed(12Mbps)\n"
               "       SEGGER : J-Link (1366:1015)\n       3-1 -> usbip://bay-b3.local:3240/1-1\n"
               "           -> remote bus/dev 001/002\n")
        self.assertEqual(bayctl.parse_usbip_port(out), [("00", "bay-b3.local", "1-1")])


class NodeApi(unittest.TestCase):
    """bayctl against the firmware's simulated node (web/dev_server.py)."""

    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        cls.proc = subprocess.Popen([sys.executable, str(DEV_SERVER), str(cls.port)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.bay = bayctl.Bay(id="B3", board="rpi-pico2", host="127.0.0.1", http_port=cls.port)
        deadline = time.monotonic() + 10
        while True:
            try:
                bayctl.api(cls.bay, "/api/status", timeout=1)
                break
            except bayctl.BayError:
                if time.monotonic() > deadline:
                    cls.proc.kill()
                    raise
                time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(5)

    def test_power(self):
        s = bayctl.api(self.bay, "/api/power", {"action": "off"})
        self.assertFalse(s["dut"]["on"])
        s = bayctl.api(self.bay, "/api/power", {"action": "on"})
        self.assertTrue(s["dut"]["on"])

    def test_mode_reset_boot(self):
        self.assertEqual(bayctl.api(self.bay, "/api/mode", {"mode": "classic"})["path"], "classic")
        self.assertEqual(bayctl.api(self.bay, "/api/mode", {"mode": "usbip"})["path"], "usbip")
        bayctl.api(self.bay, "/api/reset", {"ms": 50})
        bayctl.api(self.bay, "/api/boot", {})

    def test_cli(self):
        lab = Path(tempfile.mkdtemp()) / "lab.yaml"
        lab.write_text(json.dumps({"bays": {"B3": {"host": "127.0.0.1", "http_port": self.port}}}))
        r = subprocess.run([sys.executable, str(REPO / "tools" / "bayctl.py"), "--lab", str(lab), "power", "b3", "cycle",
                            "--ms", "10"], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("VBUS on", r.stdout)

    def test_unreachable(self):
        bay = bayctl.Bay(id="X1", board="x", host="127.0.0.1", http_port=free_port())
        with self.assertRaises(bayctl.BayError):
            bayctl.api(bay, "/api/status", timeout=1)


class Pty(unittest.TestCase):
    """`bayctl pty` bridges stdin/stdout to the node's raw AUX port (here: an echo server)."""

    def test_bridge(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        def echo():
            conn, _ = srv.accept()
            with conn:
                try:
                    while data := conn.recv(1024):
                        conn.sendall(data.upper())
                except OSError:
                    pass                    # the bridge is killed at the end of the test
        threading.Thread(target=echo, daemon=True).start()
        lab = Path(tempfile.mkdtemp()) / "lab.yaml"
        lab.write_text(json.dumps({"bays": {"B3": {"host": "127.0.0.1", "aux_port": port}}}))
        p = subprocess.Popen([sys.executable, str(REPO / "tools" / "bayctl.py"), "--lab", str(lab), "pty", "B3"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            p.stdin.write(b"uart:~$ kernel version\r\n")
            p.stdin.flush()
            got = b""
            deadline = time.monotonic() + 10
            while b"VERSION" not in got and time.monotonic() < deadline:
                got += p.stdout.read1(1024) if hasattr(p.stdout, "read1") else p.stdout.read(1)
            self.assertIn(b"UART:~$ KERNEL VERSION", got)
        finally:
            p.kill()
            p.wait(5)
            p.stdin.close()
            p.stdout.close()
            srv.close()


if __name__ == "__main__":
    unittest.main()
