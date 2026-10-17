"""Tests for tools/bayctl.py, against the repository's rack and the firmware's simulated node.

    python -m unittest discover -s tools/tests -v

No rack needed: the node API is firmware/bay-node/web/dev_server.py (same endpoints and JSON
as the firmware), the AUX UART a local echo server.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

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

    def test_hwmap_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries, _ = bayctl.hwmap(self.bays, Path(tmp), "python3", "/opt/rack/tools/bayctl.py", None,
                                      lease_for="30m")
            a1 = next(e for e in entries if e["fixtures"][0] == "bay:A1")
            self.assertIn("prepare A1 --lease 30m", Path(a1["pre_script"]).read_text())
            self.assertIn("release A1", Path(a1["post_script"]).read_text())

    def test_duration(self):
        self.assertEqual([bayctl.duration(x) for x in ("90", "90s", "15m", "2h")], [90, 90, 900, 7200])
        with self.assertRaises(bayctl.BayError):
            bayctl.duration("soon")


class AccessConfig(unittest.TestCase):
    """The `access:` section of config/lab.yaml, as the nodes get it."""

    def lab(self, doc: dict) -> Path:
        path = Path(tempfile.mkdtemp()) / "lab.yaml"
        path.write_text(json.dumps(doc))
        return path

    def test_example(self):
        rules = bayctl.access_rules(LAB_EXAMPLE, "B3")
        self.assertTrue(rules["enabled"])
        self.assertEqual(rules["everyone"], ["status"])
        ci = next(s for s in rules["sources"] if s["name"] == "ci-runners")
        self.assertEqual(ci["cidr"], "192.168.1.40/30")

    def test_merge(self):
        lab = self.lab({"access": {"everyone": [], "sources": {
                            "ci": {"cidr": "10.0.4.3/28", "allow": ["status", "control"]},
                            "me": {"cidr": "10.0.1.23", "allow": "all"}}},
                        "bays": {"C1": {"access": {"sources": {"desk": {"cidr": "10.0.1.66/32", "allow": ["all"]},
                                                              "ci": {"cidr": "10.0.4.0/28", "allow": ["status"]}}}}}})
        rules = bayctl.access_rules(lab, "C1")
        by = {s["name"]: s for s in rules["sources"]}
        self.assertEqual(rules["everyone"], [])
        self.assertEqual(by["ci"], {"name": "ci", "cidr": "10.0.4.0/28", "allow": ["status"]})   # replaced
        self.assertEqual(by["desk"]["cidr"], "10.0.1.66")                                       # added
        self.assertEqual(by["me"]["allow"], ["all"])
        a1 = bayctl.access_rules(lab, "A1")
        self.assertEqual(len(a1["sources"]), 2)
        self.assertEqual(a1["sources"][0]["cidr"], "10.0.4.0/28")                               # host bits cleared

    def test_none_and_errors(self):
        self.assertIsNone(bayctl.access_rules(self.lab({"bays": {}}), "A1"))
        for bad in [{"sources": {"bad name": {"cidr": "1.2.3.4", "allow": ["all"]}}},
                    {"sources": {"x": {"cidr": "1.2.3.400", "allow": ["all"]}}},
                    {"sources": {"x": {"cidr": "1.2.3.4", "allow": ["web"]}}},
                    {"sources": {f"h{i}": {"cidr": f"10.0.0.{i}", "allow": ["all"]} for i in range(9)}}]:
            with self.assertRaises(bayctl.BayError, msg=bad):
                bayctl.access_rules(self.lab({"access": bad}), "A1")

    def test_key(self):
        with mock.patch.dict(os.environ, {"BAYCTL_KEY": ""}):
            with self.assertRaises(bayctl.BayError):
                bayctl.admin_key()
        with mock.patch.dict(os.environ, {"BAYCTL_KEY": "ab" * 31}):
            with self.assertRaises(bayctl.BayError):
                bayctl.admin_key()
        with mock.patch.dict(os.environ, {"BAYCTL_KEY": "AB" * 32}):
            self.assertEqual(bayctl.admin_key(), bytes([0xAB] * 32))


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


class AccessApi(unittest.TestCase):
    """Claim, rules, lease and kicks against the simulated node (its own instance: it changes the rules)."""

    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        cls.proc = subprocess.Popen([sys.executable, str(DEV_SERVER), str(cls.port)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.bay = bayctl.Bay(id="B3", board="rpi-pico2", host="127.0.0.1", http_port=cls.port)
        cls.key = os.urandom(32)            # a test key, made up for this run
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

    def dev(self, path: str) -> dict:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as r:
            return json.loads(r.read())

    def as_peer(self, ip: str) -> None:
        self.dev(f"/dev/peer?ip={ip}" if ip else "/dev/peer")

    def test_flow(self):
        bay, key = self.bay, self.key
        # Claim: someone presses BOOT while bayctl waits
        threading.Timer(1.5, lambda: self.dev("/dev/boot")).start()
        bayctl.access_claim(bay, key, timeout=10, say=lambda *_: None)
        with self.assertRaises(bayctl.BayError):                    # claimed already
            bayctl.access_claim(bay, key, timeout=1, say=lambda *_: None)
        rules = {"enabled": True, "everyone": ["status"], "sources": [
            {"name": "me", "cidr": "127.0.0.1", "allow": ["all"]},
            {"name": "ci", "cidr": "192.168.1.40/30", "allow": ["status", "control", "console", "usbip"]}]}
        self.assertEqual(bayctl.access_push(bay, rules, key), "updated")
        self.assertEqual(bayctl.access_push(bay, rules, key), "unchanged")
        with self.assertRaises(bayctl.BayError):                    # a wrong key
            bayctl.access_push(bay, {**rules, "enabled": False}, os.urandom(32))
        doc = bayctl.api(bay, "/api/access", key=key)
        self.assertTrue(doc["admin"])
        self.assertEqual(doc["source"], "me")

        # Another host: read-only
        self.as_peer("192.168.1.77")
        try:
            self.assertEqual(bayctl.api(bay, "/api/status")["access"]["allow"], ["status"])
            with self.assertRaisesRegex(bayctl.BayError, "403"):
                bayctl.api(bay, "/api/power", {"action": "on"})
        finally:
            self.as_peer("")

        # A CI runner reserves the bay; the others get 423 until it is released
        self.as_peer("192.168.1.41")
        try:
            self.assertTrue(bayctl.lease(bay, 600, "twister job 8812")["lease"]["yours"])
        finally:
            self.as_peer("")
        with self.assertRaisesRegex(bayctl.BayError, "423 reserved by 192.168.1.41"):
            bayctl.api(bay, "/api/power", {"action": "on"})
        with self.assertRaisesRegex(bayctl.BayError, "403"):        # not the holder, no key
            bayctl.release(bay)
        with mock.patch.dict(os.environ, {"BAYCTL_KEY": key.hex()}):
            bayctl.release(bay, force=True)
        bayctl.api(bay, "/api/power", {"action": "on"})

        # Kick a (simulated) RFC 2217 client
        self.dev("/dev/rfc2217")
        self.assertIn("rfc2217", [c["id"] for c in bayctl.api(bay, "/api/access")["connections"]])
        bayctl.api(bay, "/api/access/kick", {"id": "rfc2217"}, key=key)
        self.assertNotIn("rfc2217", [c["id"] for c in bayctl.api(bay, "/api/access")["connections"]])
        refused = bayctl.api(bay, "/api/access", key=key)["refused"]
        self.assertIn(("192.168.1.77", "control", "not_allowed"),
                      {(r["ip"], r["service"], r["reason"]) for r in refused})

    def test_cli_show_and_keygen(self):
        lab = Path(tempfile.mkdtemp()) / "lab.yaml"
        lab.write_text(json.dumps({"bays": {"B3": {"host": "127.0.0.1", "http_port": self.port}}}))
        tool = [sys.executable, str(REPO / "tools" / "bayctl.py"), "--lab", str(lab)]
        r = subprocess.run([*tool, "access", "keygen"], capture_output=True, text=True, timeout=30)
        self.assertRegex(r.stdout.strip(), r"^[0-9a-f]{64}$")
        env = {k: v for k, v in os.environ.items() if k != "BAYCTL_KEY"}
        r = subprocess.run([*tool, "access", "show", "B3"], capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("you 127.0.0.1", r.stdout)
        r = subprocess.run([*tool, "access", "push"], capture_output=True, text=True, timeout=30, env=env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("BAYCTL_KEY", r.stderr)


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
