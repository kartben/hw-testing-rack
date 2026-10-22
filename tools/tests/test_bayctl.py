"""Tests for tools/bayctl.py, against the repository's rack and the firmware's simulated node.

    python -m unittest discover -s tools/tests -v

No rack needed: the node API is firmware/bay-node/web/dev_server.py (same endpoints and JSON
as the firmware), the AUX UART a local echo server.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import os
import re
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

import yaml  # noqa: E402

import bayctl  # noqa: E402
import rackcfg  # noqa: E402

LAB_EXAMPLE = REPO / "config" / "lab.example.yaml"
DEV_SERVER = REPO / "firmware" / "bay-node" / "web" / "dev_server.py"
HUB_DEV_SERVER = REPO / "firmware" / "power-hub" / "web" / "dev_server.py"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Config(unittest.TestCase):
    def setUp(self):
        self.bays = bayctl.load_bays(lab_yaml=LAB_EXAMPLE)

    def test_defaults_and_overrides(self):
        b = self.bays
        self.assertEqual(b["A1"].platform, "nucleo_g474re")             # family resolved by the lab file
        self.assertIsNone(b["A2"].platform)                             # family left open
        self.assertIn("nucleo_h743zi", b["A2"].choices)
        self.assertEqual(b["A4"].platform, "wio_terminal")              # from boards.yaml
        self.assertEqual(b["A4"].runner, "bossac")
        self.assertEqual(b["A3"].platform, "beagleplay/cc1352p7")       # a family, the lab file says which core
        self.assertFalse(b["A3"].ci)                                    # flashed from its own Linux
        self.assertEqual(b["B2"].console, "aux")
        self.assertFalse(b["B4"].ci)
        self.assertEqual(b["B2"].host, "bay-b2.local")
        self.assertEqual(b["B2"].url, "http://bay-b2.local")

    def test_example_bay(self):
        b = self.bays                                                   # config/rack.yaml's B3: four boards
        self.assertNotIn("B3", b)
        self.assertEqual([k for k in b if k.startswith("B3")], ["B3.1", "B3.2", "B3.3", "B3.4"])
        self.assertEqual(b["B3.1"].platform, "xiao_esp32c3")           # the lab file, per sub-slot
        self.assertEqual(b["B3.2"].platform, "rpi_pico2/rp2350a/m33_0")
        self.assertFalse(b["B3.4"].ci)
        b33 = b["B3.3"]                                                 # the bay's logic analyzer (`role:`)
        self.assertEqual((b33.role, b33.ci, b33.platform, b33.runner), ("analyzer", False, None, None))
        self.assertTrue(b33.serial.startswith("/dev/serial/by-id/usb-Dr._Gusman_LogicAnalyzer_"))
        self.assertEqual([x.id for x in bayctl.dut_targets(b, "B3")], ["B3.1", "B3.2", "B3.4"])
        self.assertEqual(len(bayctl.dut_targets(b, "B3", analyzers=True)), 4)   # its power is the bay's
        self.assertEqual([x.id for x in bayctl.dut_targets(b, "B3.3")], ["B3.3"])  # named, it is there

    def test_example_analyzer(self):
        la = bayctl.analyzer_info()                                     # config/rack.yaml › analyzer
        self.assertEqual(la["app"], "6.0.0.1")
        fw = la["firmware"]["rpi-pico2"]
        self.assertEqual((fw["release"], fw["asset"]), ("v6.0.0.0", "logic-analyzer-firmware_v6.0.0_BOARD_PICO_2.zip"))
        self.assertEqual(bayctl.analyzer_state({"vid": "1209", "pid": "3020"}, la), "LogicAnalyzer")
        self.assertEqual(bayctl.analyzer_state({"vid": "0x2E8A", "pid": "0x000F"}, la), "BOOTSEL")
        self.assertIn("not the analyzer's firmware", bayctl.analyzer_state({"vid": "2fe3", "pid": "0004"}, la))
        self.assertEqual(bayctl.analyzer_state(None, la), "no USB device")

    def test_hwmap(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries, warnings = bayctl.hwmap(self.bays, Path(tmp), "python3", "/opt/rack/tools/bayctl.py", None)
            by = {e["fixtures"][0]: e for e in entries}
            self.assertNotIn("bay:B4", by)                              # ci: false
            self.assertNotIn("bay:A3", by)
            self.assertNotIn("bay:A2", by)                              # no platform: left out, with a warning
            self.assertTrue(any("bays.A2.platform" in w for w in warnings))
            a1 = by["bay:A1"]
            self.assertTrue(a1["connected"])
            self.assertEqual(a1["id"], "003A00283133510837363734")
            self.assertTrue(a1["serial"].startswith("/dev/serial/by-id/"))
            b2 = by["bay:B2"]                                           # GIGA R1: dfu-util, AUX console
            self.assertEqual(b2["runner"], "dfu-util")
            self.assertIn("serial_pty", b2)
            self.assertEqual(b2["serial_pty"], "python3 /opt/rack/tools/bayctl.py pty B2")   # AUX console
            self.assertNotIn("serial", b2)
            a4 = by["bay:A4"]                                           # no console path yet
            self.assertFalse(a4["connected"])
            self.assertNotIn("bay:B3.3", by)                            # the analyzer: no test target
            self.assertFalse(any("B3.3" in w for w in warnings))
            self.assertEqual([w for w in warnings if "without a probe id" in w], [])   # one board per runner
            pre = Path(a1["pre_script"]).read_text()
            self.assertIn("prepare A1", pre)
            self.assertTrue(pre.startswith("#!/bin/sh"))

    def test_exports(self):
        lg = bayctl.export_labgrid(self.bays, "python3", "bayctl.py")
        t = lg["targets"]["bay-b2"]
        self.assertEqual(t["resources"]["NetworkSerialPort"],
                         {"host": "bay-b2.local", "port": 4001, "speed": 115200, "protocol": "rfc2217"})
        self.assertEqual(t["drivers"]["ExternalPowerDriver"]["cmd_cycle"], "python3 bayctl.py power B2 cycle")
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


def lab_file(doc: dict) -> Path:
    path = Path(tempfile.mkdtemp()) / "lab.yaml"
    path.write_text(json.dumps(doc))                    # JSON is YAML
    return path


CONVERTED = [("xiao", "c-to-c"), ("rpi-pico2", "c-to-micro-b"), ("rpi-pico2", "c-to-micro-b"), ("xiao", "c-to-c")]


def converted_rack() -> Path:
    """config/rack.yaml with bay B3 converted (docs/multi-dut-node.md): four boards on a DATA ×4."""
    raw = yaml.safe_load((REPO / "config" / "rack.yaml").read_text(encoding="utf-8"))
    raw["population"]["B3"] = {"boards": [{"board": b, "cable": c} for b, c in CONVERTED]}
    path = Path(tempfile.mkdtemp()) / "rack.yaml"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


class ConvertedConfig(unittest.TestCase):
    """A converted bay's boards, by sub-slot: B3.1 to B3.4."""

    @classmethod
    def setUpClass(cls):
        cls.rack = converted_rack()

    def load(self, bays: dict):
        return bayctl.load_bays(rack_yaml=self.rack, lab_yaml=lab_file({"bays": bays}))

    def test_sub_slots(self):
        b = self.load({"B3.1": {"platform": "xiao_esp32c3"}})
        self.assertNotIn("B3", b)
        self.assertEqual([k for k in b if k.startswith("B3")], ["B3.1", "B3.2", "B3.3", "B3.4"])
        self.assertEqual(list(b).index("B3.1"), list(b).index("B2") + 1)   # rack order
        b32 = b["B3.2"]
        self.assertEqual((b32.board, b32.node, b32.slot, b32.multi), ("rpi-pico2", "B3", 2, True))
        self.assertEqual(b32.platform, "rpi_pico2/rp2350a/m33_0")      # from boards.yaml
        self.assertEqual(b32.console, "usb")                           # boards.yaml says aux: no AUX on a sub-slot
        self.assertEqual(b32.url, "http://bay-b3.local")               # the node's
        self.assertEqual(b["B3.1"].platform, "xiao_esp32c3")           # the lab file, per sub-slot
        self.assertIsNone(b["A1"].slot)
        self.assertEqual([x.id for x in bayctl.dut_targets(b, "b3")], ["B3.1", "B3.2", "B3.3", "B3.4"])
        self.assertEqual([x.id for x in bayctl.dut_targets(b, "B3.2")], ["B3.2"])
        node = bayctl.node_bay(b, "B3.3")
        self.assertEqual((node.id, node.slot, node.host), ("B3", None, "bay-b3.local"))
        self.assertEqual([n.id for n in bayctl.nodes_of(b, ["B3.1", "b3", "A1"])], ["B3", "A1"])
        self.assertEqual(len(bayctl.nodes_of(b, [])), 8)                # every node once
        with self.assertRaisesRegex(bayctl.BayError, "several boards"):
            bayctl.get_bay(b, "B3")                                     # a converted bay: say which board
        with self.assertRaises(bayctl.BayError):
            bayctl.get_bay(b, "B3.5")

    def test_lab(self):
        b = self.load({"B3": {"host": "10.0.0.3", "http_port": 8080}, "B3.2": {"platform": "rpi_pico2/rp2350b/m33"}})
        self.assertEqual((b["B3.4"].host, b["B3.4"].http_port), ("10.0.0.3", 8080))   # the node's, inherited
        self.assertEqual(b["B3.2"].platform, "rpi_pico2/rp2350b/m33")
        for bad, msg in [({"B3.5": {}}, "no such sub-slot"), ({"A1.1": {}}, "one board"),
                         ({"B3.2": {"console": "aux"}}, "no AUX UART"), ({"B3.x": {}}, "sub-slot")]:
            with self.assertRaisesRegex(bayctl.BayError, msg):
                self.load(bad)

    def test_hwmap_and_exports(self):
        b = self.load({"B3.1": {"platform": "xiao_esp32c3", "runner": "esp32", "serial": "/dev/ttyACM7"},
                       "B3.2": {"serial": "/dev/serial/by-id/usb-ZEPHYR_USB-DEV_9F2D-if00"},
                       "B3.4": {"ci": False}})
        with tempfile.TemporaryDirectory() as tmp:
            entries, warnings = bayctl.hwmap(b, Path(tmp), "python3", "/opt/rack/tools/bayctl.py", None)
            by = {e["fixtures"][0]: e for e in entries}
            self.assertIn("B3.2, B3.3 use uf2 without a probe id", " | ".join(warnings))   # two Pico 2 (B1.2's too)
            b32 = by["bay:B3.2"]                                        # one entry per board
            self.assertEqual(b32["fixtures"][:2], ["bay:B3.2", "node:B3"])
            self.assertEqual(b32["serial"], "/dev/serial/by-id/usb-ZEPHYR_USB-DEV_9F2D-if00")
            self.assertNotIn("serial_pty", b32)
            self.assertTrue(b32["pre_script"].endswith("bay-b3-2-pre.sh"))
            self.assertIn("prepare B3.2", Path(b32["pre_script"]).read_text())
            self.assertEqual(by["bay:B3.1"]["id"], "/dev/ttyACM7")     # esp32: the board by its serial port
            self.assertNotIn("bay:B3.4", by)                            # ci: false
        t = bayctl.export_labgrid(b, "python3", "bayctl.py")["targets"]["bay-b3-2"]
        self.assertEqual(t["resources"], {})                            # power, no AUX UART
        self.assertNotIn("SerialDriver", t["drivers"])
        self.assertEqual(t["drivers"]["ExternalPowerDriver"]["cmd_cycle"], "python3 bayctl.py power B3.2 cycle")
        pdu = bayctl.export_pdudaemon(b, "python3", "bayctl.py")
        self.assertEqual(pdu["_ports"][9], "B3.2")                      # a port per board under test (B1's two first)

    def test_analyzer(self):
        b = self.load({"B3.3": {"role": "analyzer", "ci": True, "serial": "/dev/ttyACM9"}})   # your own rack
        self.assertEqual(b["B3.3"].role, "analyzer")
        self.assertIsNone(b["B3.3"].platform)                           # no Zephyr target from boards.yaml
        with tempfile.TemporaryDirectory() as tmp:
            entries, _ = bayctl.hwmap(b, Path(tmp), "python3", "bayctl.py", None)
            self.assertNotIn("bay:B3.3", [e["fixtures"][0] for e in entries])   # whatever its `ci`
        self.assertIn("B3.3", bayctl.export_pdudaemon(b, "python3", "bayctl.py")["_ports"].values())   # its power
        for bad, msg in [({"B3.3": {"role": "scope"}}, "role 'scope'"), ({"A1": {"role": "analyzer"}}, "sub-slot's")]:
            with self.assertRaisesRegex(bayctl.BayError, msg):
                self.load(bad)
        only = {f"B3.{n}": {"role": "analyzer"} for n in (1, 2, 3, 4)}
        with self.assertRaisesRegex(bayctl.BayError, "only its analyzer"):
            bayctl.dut_targets(self.load(only), "B3")


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


class Slots(unittest.TestCase):
    """config/rack.yaml › population: a bay's one board, or a converted bay's boards on one plate."""

    PACKED = [("xiao", (19.42, 112.44)), ("rpi-pico2", (44.2, 82.4)), ("rpi-pico2", (72.2, 82.4)),
              ("xiao", (100.2, 112.44))]
    EXAMPLE = [("xiao", (8.7, 30.0)), ("rpi-pico2", (41.7, 16.0)), ("rpi-pico2", (74.7, 16.0)),
               ("xiao", (107.7, 30.0))]

    def test_one_board(self):
        self.assertEqual(rackcfg.dut_slots("A1", {"board": "nucleo-64", "cable": "c-to-micro-b"}),
                         [rackcfg.Slot("A1", "A1", None, "nucleo-64", "c-to-micro-b")])
        self.assertEqual(rackcfg.dut_slots("A1", None), [])

    def test_boards(self):
        sl = rackcfg.dut_slots("C1", {"boards": [{"board": "xiao"},
                                                 {"board": "rpi-pico2", "slot": 4, "at": [1, 2], "orient": "side"}]})
        self.assertEqual([(s.id, s.slot, s.board) for s in sl], [("C1.1", 1, "xiao"), ("C1.4", 4, "rpi-pico2")])
        self.assertEqual((sl[1].at, sl[1].orient, sl[1].role), ([1.0, 2.0], "side", None))
        self.assertEqual(rackcfg.dut_slots("C1", {"boards": [{"board": "rpi-pico2", "role": "analyzer"}]})[0].role,
                         "analyzer")
        self.assertEqual(rackcfg.split_slot("b3.2"), ("B3", 2))
        self.assertEqual(rackcfg.split_slot("B3"), ("B3", None))
        with self.assertRaises(ValueError):
            rackcfg.split_slot("B3.x")

    def test_errors(self):
        for entry, msg in [({"board": "xiao", "boards": [{"board": "xiao"}]}, "both"),
                           ({"boards": []}, "1 to 4"),
                           ({"boards": [{"board": "xiao"}] * 5}, "1 to 4"),
                           ({"boards": [{"board": "xiao"}, {"board": "xiao", "slot": 1}]}, "two boards on slot 1"),
                           ({"boards": [{"board": "xiao", "slot": 5}]}, "ports are 1 to 4"),
                           ({"boards": [{"cable": "c-to-c"}]}, "no `board`"),
                           ({"boards": [{"board": "xiao", "at": [1]}]}, "`at`"),
                           ({"boards": [{"board": "xiao", "orient": "left"}]}, "rear or side"),
                           ({"boards": [{"board": "xiao", "role": "scope"}]}, "role 'scope'"),
                           ({"board": "rpi-pico2", "role": "analyzer"}, "sub-slot's")]:
            with self.assertRaisesRegex(ValueError, msg, msg=entry):
                rackcfg.dut_slots("C1", entry)

    def test_example_plate(self):
        rack = rackcfg.load()                                           # config/rack.yaml's B1 and B3
        self.assertEqual(rack.multi_bays(), ["B1", "B3"])
        self.assertEqual(rack.bay_boards("B3"), self.EXAMPLE)
        # B3 is on the honeycomb plate: its pegs are tools/plate_layout.py's to check (test_plate_layout)
        self.assertEqual(rack.plate_kind("B3"), "pegs")

    def test_plate(self):
        rack = rackcfg.load()
        self.assertEqual([round(v, 3) for v in rack.plate_size], [137.4, 159.4])
        self.assertEqual([(round(x, 3), round(y, 3)) for x, y in rack.plate_buttons()], [(1.2, 67.2), (9.2, 67.2)])

    def test_packing_and_checks(self):
        rack = rackcfg.load()
        boards = [{"board": b} for b, _ in CONVERTED]
        rack.raw["population"]["B3"] = {"boards": boards}
        self.assertEqual(rack.multi_bays(), ["B1", "B3"])
        self.assertEqual(rack.bay_boards("B3"), self.PACKED)               # packed in a row, centred
        self.assertEqual(rack.check_bay_plate("B3"), [])
        o = rack.bay_layout("B3")[1]["o"]                                # the Pico 2 turned USB to the port wall
        self.assertEqual((o["w"], o["l"], o["usb_side"]), (21.0, 51.0, False))
        boards[1]["at"] = [10, 60]
        problems = " | ".join(rack.check_bay_plate("B3"))
        for what in ("B3.2: over the plate's finger slot", "B3.2: -1.6 mm from a RESET/BOOT pin hole",
                     "B3.1 and B3.2 overlap"):
            self.assertIn(what, problems)
        boards[1]["at"] = [120, 10]
        self.assertIn("B3.2: off the plate", " | ".join(rack.check_bay_plate("B3")))

    def test_node_buttons(self):
        scad = (REPO / "mechanical" / "lib" / "carrier.scad").read_text(encoding="utf-8")
        found = tuple(tuple(float(v) for v in re.search(rf"{k} = \[([\d.]+), ([\d.]+)\]", scad).groups())
                      for k in ("NODE_RESET", "NODE_BOOT"))
        self.assertEqual(rackcfg.NODE_BUTTONS, found)

    def test_generated_bay_plates(self):
        spec = importlib.util.spec_from_file_location("rack_build", REPO / "tools" / "build.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        committed = (REPO / "mechanical" / "generated" / "boards.scad").read_text(encoding="utf-8")
        self.assertEqual(committed.replace("\r\n", "\n"), build.boards_scad(rackcfg.load_boards(), rackcfg.load()),
                         "stale: run python tools/build.py config")
        rack = rackcfg.load()
        rack.raw["population"]["B3"] = {"boards": [{"board": b} for b, _ in CONVERTED]}
        self.assertIn("BAY_PLATES = [];", build.boards_scad(rackcfg.load_boards(), rack))   # the honeycomb plate
        self.assertNotIn(("plate_bay_b3", "parts/board_plate.scad", {"BAY": "B3"}), build.part_jobs(rack))
        rack.raw["population"]["B3"]["plate"] = "boards"                                  # its own plate
        self.assertIn('["B3", "boards", [[1, [19.42, 112.44], ["xiao", "XIAO", [17.78, 20.96]',
                      build.boards_scad(rackcfg.load_boards(), rack))
        self.assertIn(("plate_bay_b3", "parts/board_plate.scad", {"BAY": "B3"}), build.part_jobs(rack))
        rack.raw["population"]["B3"]["boards"][1]["at"] = [10, 60]
        with self.assertRaisesRegex(SystemExit, "B3.2: over the plate's finger slot"):
            build.boards_scad(rackcfg.load_boards(), rack)


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
        lab.write_text(json.dumps({"bays": {"A1": {"host": "127.0.0.1", "http_port": self.port}}}))
        r = subprocess.run([sys.executable, str(REPO / "tools" / "bayctl.py"), "--lab", str(lab), "power", "a1", "cycle",
                            "--ms", "10"], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("VBUS on", r.stdout)

    def test_unreachable(self):
        bay = bayctl.Bay(id="X1", board="x", host="127.0.0.1", http_port=free_port())
        with self.assertRaises(bayctl.BayError):
            bayctl.api(bay, "/api/status", timeout=1)

    def test_one_port(self):
        ports = bayctl.node_ports(self.bay)                             # a one-port node: its DUT is port 1
        self.assertEqual([(p["slot"], p["port"], p["hub_port"]) for p in ports], [("B3", 1, None)])
        self.assertEqual(bayctl.port_busid(ports[0]), "1-1")
        self.assertEqual(len(bayctl.api(self.bay, "/api/status")["ports"]), 1)


class MultiNodeApi(unittest.TestCase):
    """A converted bay against the simulated node with four ports (dev_server.py --ports 4)."""

    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        cls.proc = subprocess.Popen([sys.executable, str(DEV_SERVER), str(cls.port), "--ports", "4"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.lab = Path(tempfile.mkdtemp()) / "lab.yaml"
        cls.lab.write_text(json.dumps({"bays": {"B3": {"host": "127.0.0.1", "http_port": cls.port}}}))
        cls.rack = converted_rack()
        cls.bays = bayctl.load_bays(rack_yaml=cls.rack, lab_yaml=cls.lab)
        cls.node = bayctl.node_bay(cls.bays, "B3")
        deadline = time.monotonic() + 10
        while True:
            try:
                bayctl.api(cls.node, "/api/status", timeout=1)
                break
            except bayctl.BayError:
                if time.monotonic() > deadline:
                    cls.proc.kill()
                    raise
                time.sleep(0.2)
        try:
            cls.wait_enumerated()
        except AssertionError:
            cls.proc.kill()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(5)

    @classmethod
    def wait_enumerated(cls):
        """The boards enumerate UP_S after their power on, one after the other (dev_server.py)."""
        deadline = time.monotonic() + 10
        while not all(p["usb"] for p in bayctl.node_ports(cls.node)):
            if time.monotonic() > deadline:
                raise AssertionError("the boards never enumerated")
            time.sleep(0.1)

    def cli(self, *args) -> str:
        r = subprocess.run([sys.executable, str(REPO / "tools" / "bayctl.py"), "--lab", str(self.lab),
                            "--rack", str(self.rack), *args],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_ports(self):
        ports = bayctl.node_ports(self.node)
        self.assertEqual([p["slot"] for p in ports], ["B3.1", "B3.2", "B3.3", "B3.4"])
        self.assertEqual(bayctl.port_busid(bayctl.port_doc(self.bays["B3.2"])), "1-1.2")   # hub port n = USB-C n
        self.assertEqual(len(bayctl.api(self.node, "/api/status")["ports"]), 4)
        metrics = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/metrics").read().decode()
        self.assertIn('bay_dut_power_on{bay="b3",port="B3.2"}', metrics)

    def test_power_needs_a_port(self):
        with self.assertRaisesRegex(bayctl.BayError, "409"):
            bayctl.api(self.node, "/api/power", {"action": "on"})
        s = bayctl.api(self.node, "/api/power", {"action": "on", "port": 4})
        self.assertTrue(s["ports"][3]["power"]["on"])

    def test_power_and_reset(self):
        b = self.bays["B3.3"]
        p = bayctl.control(b, "power", {"action": "off"})
        self.assertFalse(p["power"]["on"])
        self.assertIsNone(p["usb"])
        self.assertTrue(bayctl.api(self.node, "/api/status")["dut"]["on"])     # the other boards still on
        bayctl.control(b, "power", {"action": "on"})
        self.assertTrue(bayctl.wait_for(lambda: bayctl.port_doc(b)["usb"] is not None, 5))
        self.assertIsNone(bayctl.control(b, "reset", {"ms": 20})["usb"])       # it re-enumerates...
        self.assertTrue(bayctl.wait_for(lambda: bayctl.port_doc(b)["usb"] is not None, 5))
        self.assertEqual(bayctl.port_busid(bayctl.port_doc(b)), "1-1.3")      # ...under the same busid

    def test_admission(self):
        """DATA x4's ports come up off; the node switches them on within the bay's budget, and so does a
        power on: 409 when the other ports leave no room (docs/multi-dut-node.md, Power budget)."""
        b1, b2 = self.bays["B3.1"], self.bays["B3.2"]
        self.assertTrue(all(p["power"]["on"] for p in bayctl.node_ports(self.node)))   # admitted one by one
        bayctl.control(b2, "power", {"action": "off"})
        urllib.request.urlopen(f"http://127.0.0.1:{self.port}/dev/draw?port=1&ma=900").read()
        try:
            with self.assertRaisesRegex(bayctl.BayError, "409.*no room in the bay's budget"):
                bayctl.control(b2, "power", {"action": "on"})
            with self.assertRaisesRegex(bayctl.BayError, "409"):
                bayctl.control(b2, "boot", {"power_cycle": True})
            self.assertTrue(bayctl.control(b1, "power", {"action": "cycle", "ms": 10})["power"]["on"])
        finally:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/dev/draw?port=1&ma=0").read()
        self.assertTrue(bayctl.control(b2, "power", {"action": "on"})["power"]["on"])

    def test_boot_power_cycle(self):
        b = self.bays["B3.3"]
        self.assertIsNone(bayctl.control(b, "boot", {"power_cycle": True})["usb"])   # BOOT across a power cycle
        self.assertTrue(bayctl.wait_for(lambda: bayctl.port_doc(b)["usb"] is not None, 5))
        self.assertIn("B3.3", self.cli("boot", "B3.3", "--power-cycle"))
        # leave the shared node as found: the next test lists B3.3's busid (a slow CI runner got there first)
        self.assertTrue(bayctl.wait_for(lambda: bayctl.port_doc(b)["usb"] is not None, 5))
        r = subprocess.run([sys.executable, str(REPO / "tools" / "bayctl.py"), "--lab", str(self.lab),
                            "--rack", str(self.rack), "boot", "A1", "--power-cycle"],
                           capture_output=True, text=True, timeout=30)
        self.assertNotEqual(r.returncode, 0)                            # a bay's one DUT: its AUX RESET
        self.assertIn("sub-slot's", r.stderr)

    def test_lease(self):
        b1, b2 = self.bays["B3.1"], self.bays["B3.2"]
        self.assertGreater(bayctl.lease_left(b2, bayctl.lease(b2, 600, "t")), 590)
        urllib.request.urlopen(f"http://127.0.0.1:{self.port}/dev/peer?ip=192.168.1.99").read()   # another host
        try:
            with self.assertRaisesRegex(bayctl.BayError, "423"):
                bayctl.control(b2, "power", {"action": "on"})
            bayctl.control(b1, "power", {"action": "on"})                      # the other boards stay free
            with self.assertRaisesRegex(bayctl.BayError, "423"):
                bayctl.lease(self.node, 60)                                     # the whole bay: B3.2 is taken
        finally:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/dev/peer").read()
        self.assertEqual(bayctl.lease_left(b2, bayctl.release(b2)), 0)

    def test_attach_detach(self):
        listing = "".join(f"        1-1.{h}: Zephyr : USB-DEV (2fe3:0004)\n" for h in (1, 2, 3, 4))
        imported = ("Port 00: <Port in Use> at Full Speed(12Mbps)\n       3-1 -> usbip://127.0.0.1:3240/1-1.1\n"
                    "Port 01: <Port in Use> at Full Speed(12Mbps)\n       3-2 -> usbip://127.0.0.1:3240/1-1.2\n")
        calls, state = [], {"port": ""}

        def run(cmd, check=True):
            calls.append(cmd)
            return {"list": listing, "port": state["port"]}.get(cmd[len(bayctl._usbip_cmd())], "")

        ids = itertools.chain([set()], itertools.repeat({"usb-ZEPHYR_USB-DEV_9F2D-if00"}))
        with mock.patch.object(bayctl, "_run", run), mock.patch.object(bayctl, "serial_ids", lambda: next(ids)), \
                mock.patch.object(bayctl.time, "sleep"):
            self.assertEqual(bayctl.attach(self.bays["B3.2"]), [str(bayctl.SERIAL_BY_ID / "usb-ZEPHYR_USB-DEV_9F2D-if00")])
            self.assertEqual(calls[-1][-5:], ["attach", "-r", "127.0.0.1", "-b", "1-1.2"])
            state["port"] = imported
            self.assertEqual(bayctl.attach(self.bays["B3.2"]), [])            # already attached
            calls.clear()
            self.assertEqual(bayctl.detach(self.bays["B3.2"]), 1)              # its busid only
            self.assertEqual(calls[-1][-3:], ["detach", "-p", "01"])

    def test_follow(self):
        stop, said = threading.Event(), []
        results = iter([bayctl.BayError("not back yet"), ["/dev/serial/by-id/x"]])

        def attach(bay):
            r = next(results, [])
            if isinstance(r, Exception):
                raise r
            return r

        with mock.patch.object(bayctl, "attach", attach):
            bayctl.follow([self.bays["B3.1"]], step=0.01, say=lambda m: (said.append(m), stop.set()), stop=stop)
        self.assertEqual(said, ["B3.1: attached, /dev/serial/by-id/x"])

    def test_cli(self):
        out = self.cli("ports", "b3")
        for busid in ("1-1.1", "1-1.2", "1-1.3", "1-1.4"):
            self.assertIn(f"busid {busid}", out)
        self.cli("power", "B3", "off")                                          # the whole bay: every board
        self.assertFalse(any(p["power"]["on"] for p in bayctl.node_ports(self.node)))
        self.assertIn("VBUS on", self.cli("power", "B3.2", "on"))
        self.cli("power", "B3", "on")
        self.assertIn("B3.4 reserved for 127.0.0.1, 600 s", self.cli("lease", "B3.4", "--for", "10m"))
        self.assertIn("B3.4 released", self.cli("release", "B3.4"))
        self.wait_enumerated()
        out = self.cli("status", "B3.4")
        self.assertIn("B3", out)
        # The USB devices behind the DATA x4 hub, by name (GET /api/usb)
        self.assertIn("USB hub 0424:2517 USB2517 hub", out)
        self.assertIn("1-1.1    B3.1   1fc9:0143  MCU-LINK on-board (r0E7) CMSIS-DAP V3.172 (NXP Semiconductors)", out)
        self.assertIn("1a86:7523  CH340 serial adapter", out)


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
        lab.write_text(json.dumps({"bays": {"A1": {"host": "127.0.0.1", "aux_port": port}}}))
        p = subprocess.Popen([sys.executable, str(REPO / "tools" / "bayctl.py"), "--lab", str(lab), "pty", "A1"],
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


class Update(unittest.TestCase):
    """Firmware updates against the simulated hub (firmware/power-hub/web/dev_server.py)."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(REPO / "firmware" / "common" / "web"))
        import devserver
        cls.make_image = staticmethod(devserver.make_image)
        cls.port = free_port()
        env = {**os.environ, "HWTR_SIM_RESTART_S": "1", "HWTR_SIM_TRIAL_S": "2"}
        cls.proc = subprocess.Popen([sys.executable, str(HUB_DEV_SERVER), str(cls.port)], env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.hub = bayctl.Bay(id="hub", board="power-hub", host="127.0.0.1", http_port=cls.port)
        cls.key = os.urandom(32)
        deadline = time.monotonic() + 10
        while True:
            try:
                bayctl.api(cls.hub, "/api/status", timeout=1)
                break
            except bayctl.BayError:
                if time.monotonic() > deadline:
                    cls.proc.kill()
                    raise
                time.sleep(0.2)
        # Claimed with the test key: someone presses BOOT
        threading.Timer(1.0, lambda: urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/dev/boot")).start()
        bayctl.access_claim(cls.hub, cls.key, say=lambda *_: None)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(5)

    def update(self, image: bytes) -> str:
        return bayctl.update_device(self.hub, image, self.key, timeout=30, say=lambda *_: None, step=0.3)

    def test_image_info(self):
        info = bayctl.image_info(self.make_image("1.2.3", "power-hub/power_hub", 1000))
        self.assertEqual(info, {"version": "1.2.3", "id": "power-hub/power_hub"})
        for bad in (b"PK\x03\x04" + bytes(100), self.make_image("1.2.3", "x/y", 1000)[:-1]):
            with self.assertRaises(bayctl.BayError):
                bayctl.image_info(bad)

    def test_update_then_rollback(self):
        self.assertEqual(self.update(self.make_image("0.6.0", "power-hub/power_hub")), "confirmed")
        s = bayctl.api(self.hub, "/api/status")
        self.assertEqual((s["version"], s["firmware"]["last"]["result"]), ("0.6.0", "confirmed"))

        # Another board's image: refused before anything is sent
        with self.assertRaisesRegex(bayctl.BayError, "this image is for bay-node/bay_node"):
            self.update(self.make_image("0.7.0", "bay-node/bay_node"))

        # A firmware that does not confirm itself: MCUboot goes back
        urllib.request.urlopen(f"http://127.0.0.1:{self.port}/dev/rollback").read()
        with self.assertRaisesRegex(bayctl.BayError, "did not stay"):
            self.update(self.make_image("0.7.0", "power-hub/power_hub"))
        self.assertTrue(bayctl.wait_for(lambda: bayctl.api(self.hub, "/api/update", timeout=1)["version"] == "0.6.0",
                                        10))

    def test_wrong_key(self):
        with self.assertRaisesRegex(bayctl.BayError, "403"):
            bayctl.update_device(self.hub, self.make_image("0.8.0", "power-hub/power_hub"), os.urandom(32),
                                 timeout=5, say=lambda *_: None)

    def test_rack_nodes(self):
        nodes = bayctl.rack_nodes(self.hub)
        self.assertEqual([n.id for n in nodes][:3], ["A1", "A2", "A3"])
        self.assertTrue(all(n.host.startswith("192.168.1.") for n in nodes))

    def test_hub_and_row_cli(self):
        self.assertEqual(bayctl.hub_node_id("A1"), 0x01)
        self.assertEqual(bayctl.hub_node_id("c3"), 0x23)
        self.assertEqual(bayctl.hub_node_id("0x12"), 0x12)
        for bad in ("E1", "A0", "A16", "0x10", "0x41", "nope"):
            with self.assertRaises(bayctl.BayError, msg=bad):
                bayctl.hub_node_id(bad)

        lab = Path(tempfile.mkdtemp()) / "lab.yaml"
        lab.write_text(json.dumps({"hub": f"127.0.0.1:{self.port}"}))
        env = {**os.environ, "BAYCTL_KEY": self.key.hex()}

        def cli(*args: str) -> str:
            r = subprocess.run([sys.executable, str(REPO / "tools" / "bayctl.py"), "--lab", str(lab), *args],
                               capture_output=True, text=True, timeout=30, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout

        out = cli("hub", "status")
        self.assertIn("PD 28.0 V / 5.00 A EPR", out)
        self.assertIn("row A  ON", out)
        self.assertIn("row D  OFF", out)

        out = cli("row", "D", "on")
        self.assertIn("row D  ON", out)
        out = cli("row", "D", "off")
        self.assertIn("row D  OFF", out)

        out = cli("hub", "pd", "20v")
        self.assertIn("PD 20.0 V / 5.00 A", out)
        out = cli("hub", "pd", "epr")
        self.assertIn("PD 28.0 V / 5.00 A EPR", out)

        out = cli("hub", "enumerate")
        self.assertIn("CAN", out)

        out = cli("hub", "node", "B2", "power-on")
        self.assertIn("node 0x12 (B2): power-on", out)
        out = cli("hub", "node", "0x12", "power-off")
        self.assertIn("node 0x12 (B2): power-off", out)

        out = cli("hub", "events")
        self.assertIn("node 0x12: power-off", out)
        self.assertIn("row D on", out)


if __name__ == "__main__":
    unittest.main()
