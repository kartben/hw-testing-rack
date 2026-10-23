"""Tests for tools/bayctl.py, against the repository's example lab file and the firmware's simulated node.

    python -m unittest discover -s tools/tests -v

No rack needed: the node API is firmware/bay-node/web/dev_server.py (same endpoints and JSON
as the firmware), the power hub's list of nodes a small server here, the AUX UART a local echo
server.  BAYCTL_HUB=none for every test that does not set its own: no lookup of a real rack.local.
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
BAYCTL = REPO / "tools" / "bayctl.py"

_env = mock.patch.dict(os.environ, {"BAYCTL_HUB": "none"})


def setUpModule():
    _env.start()


def tearDownModule():
    _env.stop()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def lab_file(doc: dict) -> Path:
    path = Path(tempfile.mkdtemp()) / "lab.yaml"
    path.write_text(json.dumps(doc))                    # JSON is YAML
    return path


def start_node(*args: str) -> tuple[subprocess.Popen, int]:
    """The simulated node on a free port, once it answers."""
    port = free_port()
    proc = subprocess.Popen([sys.executable, str(DEV_SERVER), str(port), *args],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    node = bayctl.Bay(id="B3", board="bay-node", host="127.0.0.1", http_port=port)
    deadline = time.monotonic() + 10
    while True:
        try:
            bayctl.api(node, "/api/status", timeout=1)
            return proc, port
        except bayctl.BayError:
            if time.monotonic() > deadline:
                proc.kill()
                raise
            time.sleep(0.2)


class FakeHub:
    """The power hub's GET /api/status, as much of it as bayctl reads: rows[].nodes[] (position, address, state)."""

    def __init__(self, nodes: list[dict]):
        hub = self
        self.nodes = nodes

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                ok = self.path == "/api/status"
                body = json.dumps({"hostname": "rack", "rows": [{"name": "B", "state": "on", "nodes": hub.nodes}]}
                                  if ok else {"error": "not found"}).encode()
                self.send_response(200 if ok else 404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.address = f"127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


# ------------------------------------------------------------------------- console names

MCULINK = {"vid": "1fc9", "pid": "0143", "manufacturer": "NXP Semiconductors",
           "product": "MCU-LINK on-board (r0E7) CMSIS-DAP V3.172", "serial": "3ZQ1J4ZBMTNKS", "ttys": [{"if": "01"}]}


class ByIdName(unittest.TestCase):
    """/dev/serial/by-id names as udev makes them (60-serial.rules, the usb_id builtin)."""

    def name(self, manufacturer, product, serial, vid="0000", pid="0000", nn="00", port=None) -> str:
        tty = {"if": nn} if port is None else {"if": nn, "port": port}
        return bayctl.by_id_name({"vid": vid, "pid": pid, "manufacturer": manufacturer, "product": product,
                                  "serial": serial}, tty)

    def test_examples(self):
        self.assertEqual(self.name("STMicroelectronics", "STM32 STLink", "066DFF495150898367102236", nn="02"),
                         "usb-STMicroelectronics_STM32_STLink_066DFF495150898367102236-if02")
        self.assertEqual(self.name("NXP Semiconductors", "MCU-LINK on-board (r0E7) CMSIS-DAP V3.172", "3ZQ1J4ZBMTNKS",
                                   nn="01"),
                         "usb-NXP_Semiconductors_MCU-LINK_on-board__r0E7__CMSIS-DAP_V3.172_3ZQ1J4ZBMTNKS-if01")
        self.assertEqual(self.name("FTDI", "FT232R USB UART", "A50285BI", port=0),
                         "usb-FTDI_FT232R_USB_UART_A50285BI-if00-port0")
        self.assertEqual(self.name(None, None, None, vid="1a86", pid="7523", port=0), "usb-1a86_7523-if00-port0")
        self.assertEqual(self.name("Espressif", "USB JTAG/serial debug unit", "34:85:18:9A:3C:10"),
                         "usb-Espressif_USB_JTAG_serial_debug_unit_34:85:18:9A:3C:10-if00")

    def test_udev_cleaning(self):
        # Runs of whitespace: one "_", none at the ends; a comma in the serial: no serial
        self.assertEqual(bayctl.usb_serial_id({"manufacturer": "  Acme \t  Corp ", "product": "Widget (v2)",
                                               "serial": "A,B", "vid": "1234", "pid": "abcd"}),
                         "Acme_Corp_Widget__v2_")
        # Valid UTF-8 kept, a control byte replaced, a non-ASCII serial dropped
        self.assertEqual(bayctl.usb_serial_id({"manufacturer": "Café", "product": "x\x01y", "serial": "Ä1"}),
                         "Café_x_y")
        # No strings: the ids, 4 hex digits
        self.assertEqual(bayctl.usb_serial_id({"manufacturer": "", "product": None, "serial": " 12 34 ",
                                               "vid": "0x2E8A", "pid": "3"}), "2e8a_0003_12_34")
        # udev reads at most 63 bytes of a manufacturer or product string
        self.assertEqual(bayctl.usb_serial_id({"manufacturer": "A" * 80, "product": "B", "serial": None}),
                         "A" * 63 + "_B")
        self.assertEqual(self.name("X", "Y", None, nn=2), "usb-X_Y-if02")

    def test_console_path(self):
        path = bayctl.console_path("usb", MCULINK)
        self.assertEqual(path, "/dev/serial/by-id/usb-NXP_Semiconductors_MCU-LINK_on-board__r0E7__CMSIS-DAP_V3.172_"
                               "3ZQ1J4ZBMTNKS-if01")
        two = {**MCULINK, "ttys": [{"if": "00"}, {"if": "02"}]}
        self.assertTrue(bayctl.console_path("usb", two).endswith("-if00"))
        self.assertTrue(bayctl.console_path("usb:02", two).endswith("-if02"))
        self.assertIsNone(bayctl.console_path("usb:03", two))
        self.assertIsNone(bayctl.console_path("aux", two))
        self.assertIsNone(bayctl.console_path("usb", None))
        self.assertIsNone(bayctl.console_path("usb", {**MCULINK, "strings": False}))   # not read yet

    def test_family(self):
        families = yaml.safe_load(bayctl.BOARDS_YAML.read_text(encoding="utf-8"))["boards"]
        self.assertEqual(bayctl.family_of("nucleo_g474re", None, families), "nucleo-64")          # its choices
        self.assertEqual(bayctl.family_of("xiao_esp32c6/esp32c6/hpcore", None, families), "xiao")
        self.assertEqual(bayctl.family_of("rpi_pico2/rp2350a/m33", None, families), "rpi-pico2")  # the same board
        self.assertEqual(bayctl.family_of("frdm_mcxn947/mcxn947/cpu0", MCULINK, families), "frdm-mcxn947")
        self.assertIsNone(bayctl.family_of("qemu_x86", None, families))


# ------------------------------------------------------------------------- the lab file alone

class Config(unittest.TestCase):
    """config/lab.example.yaml with no rack (BAYCTL_HUB=none): its entries stand alone."""

    def setUp(self):
        self.bays = bayctl.load_bays(lab_yaml=LAB_EXAMPLE)

    def test_defaults_and_overrides(self):
        b = self.bays
        self.assertEqual(b["A1"].platform, "nucleo_g474re")             # the lab file's target
        self.assertEqual((b["A1"].board, b["A1"].runner), ("nucleo-64", "stm32cubeprogrammer"))   # its family's
        self.assertIsNone(b["A2"].platform)                             # family named, target left open
        self.assertIn("nucleo_h743zi", b["A2"].choices)
        self.assertEqual(b["A4"].platform, "wio_terminal")              # from boards.yaml
        self.assertEqual(b["A4"].runner, "bossac")
        self.assertEqual(b["A3"].platform, "beagleplay/cc1352p7")       # a family, the lab file says which core
        self.assertFalse(b["A3"].ci)                                    # flashed from its own Linux
        self.assertEqual(b["B2"].console, "aux")
        self.assertFalse(b["B4"].ci)
        self.assertEqual(b["B2"].host, "bay-b2.local")
        self.assertEqual(b["B2"].url, "http://bay-b2.local")
        self.assertTrue(all(x.reported is None for x in b.values()))   # nothing from a node

    def test_example_bay(self):
        b = self.bays                                                   # B3: four boards, by the lab's sub-slots
        self.assertNotIn("B3", b)
        self.assertEqual([k for k in b if k.startswith("B3")], ["B3.1", "B3.2", "B3.3", "B3.4"])
        self.assertEqual(b["B3.1"].platform, "xiao_esp32c3")           # the lab file, per sub-slot
        self.assertEqual(b["B3.2"].platform, "rpi_pico2/rp2350a/m33_0")
        self.assertEqual(b["B3.2"].console, "usb")                     # boards.yaml says aux: no AUX on a sub-slot
        self.assertFalse(b["B3.4"].ci)
        b33 = b["B3.3"]                                                 # the bay's logic analyzer (`role:`)
        self.assertEqual((b33.role, b33.ci, b33.platform, b33.runner), ("analyzer", False, None, None))
        self.assertTrue(b33.serial.startswith("/dev/serial/by-id/usb-Dr._Gusman_LogicAnalyzer_"))
        self.assertEqual([x.id for x in bayctl.dut_targets(b, "B3")], ["B3.1", "B3.2", "B3.4"])
        self.assertEqual(len(bayctl.dut_targets(b, "B3", analyzers=True)), 4)   # its power is the bay's
        self.assertEqual([x.id for x in bayctl.dut_targets(b, "B3.3")], ["B3.3"])  # named, it is there
        self.assertEqual(list(b).index("B3.1"), list(b).index("B2") + 1)         # rack order

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
            self.assertEqual(by["bay:B3.1"]["id"], by["bay:B3.1"]["serial"])   # esp32: the board by its port
            self.assertEqual(by["bay:B3.2"]["fixtures"][:2], ["bay:B3.2", "node:B3"])
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
        self.assertEqual(lg["targets"]["bay-b3-2"]["resources"], {})   # a sub-slot: power, no AUX UART
        pdu = bayctl.export_pdudaemon(self.bays, "python3", "bayctl.py")
        cmd = pdu["pdus"]["hw-testing-rack"]["cmd_on"]
        self.assertEqual(cmd % 3, "python3 bayctl.py power-port 3 on")   # PDUDaemon formats with %
        self.assertEqual(pdu["_ports"][1], "A1")
        self.assertEqual(pdu["_ports"][5], "B1.2")
        self.assertEqual(bayctl.export_lab(self.bays), {"bays": {}})   # nothing read from a node

    def test_unknown_bay(self):
        with self.assertRaises(bayctl.BayError):
            bayctl.get_bay(self.bays, "Z9")

    def test_named(self):
        """A command's bays: their nodes only, and a bay nobody lists by its mDNS name."""
        b = bayctl.load_bays(lab_yaml=LAB_EXAMPLE, names=["B3.2"])
        self.assertEqual(list(b), ["B3.1", "B3.2", "B3.3", "B3.4"])
        c = bayctl.load_bays(lab_yaml=LAB_EXAMPLE, names=["C2"])
        self.assertEqual((list(c), c["C2"].host, c["C2"].slot), (["C2"], "bay-c2.local", None))
        self.assertEqual(bayctl.load_bays(lab_yaml=LAB_EXAMPLE, names=["nonsense"]), {})

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


class LabOnly(unittest.TestCase):
    """A DATA ×4 bay described by the lab file alone (its node offline): sub-slots B3.1 to B3.4."""

    def load(self, bays: dict):
        return bayctl.load_bays(lab_yaml=lab_file({"bays": bays}), live=False)

    def test_sub_slots(self):
        b = self.load({"B3": {"host": "10.0.0.3", "http_port": 8080}, "B3.1": {"platform": "xiao_esp32c3"},
                       "B3.2": {"board": "rpi-pico2"}, "B3.4": {}, "A1": {"platform": "nucleo_g474re"}})
        self.assertNotIn("B3", b)
        self.assertEqual(list(b), ["A1", "B3.1", "B3.2", "B3.4"])
        b32 = b["B3.2"]
        self.assertEqual((b32.board, b32.node, b32.slot, b32.multi), ("rpi-pico2", "B3", 2, True))
        self.assertEqual(b32.platform, "rpi_pico2/rp2350a/m33_0")      # from boards.yaml
        self.assertEqual(b32.console, "usb")                           # boards.yaml says aux: no AUX on a sub-slot
        self.assertEqual((b["B3.4"].host, b["B3.4"].http_port), ("10.0.0.3", 8080))   # the node's, inherited
        self.assertEqual(b["B3.1"].runner, "esp32")                    # the xiao family's, for that target
        self.assertIsNone(b["A1"].slot)
        self.assertEqual([x.id for x in bayctl.dut_targets(b, "b3")], ["B3.1", "B3.2", "B3.4"])
        node = bayctl.node_bay(b, "B3.4")
        self.assertEqual((node.id, node.slot, node.host), ("B3", None, "10.0.0.3"))
        self.assertEqual([n.id for n in bayctl.nodes_of(b, ["B3.1", "b3", "A1"])], ["B3", "A1"])
        self.assertEqual(len(bayctl.nodes_of(b, [])), 2)                # every node once
        with self.assertRaisesRegex(bayctl.BayError, "several boards"):
            bayctl.get_bay(b, "B3")                                     # a DATA ×4 bay: say which board
        with self.assertRaises(bayctl.BayError):
            bayctl.get_bay(b, "B3.3")

    def test_errors(self):
        for bad, msg in [({"B3.5": {}}, "a sub-slot is"), ({"A1": {"platform": "x"}, "A1.1": {}}, "holds one board"),
                         ({"B3.2": {"console": "aux"}}, "no AUX UART"), ({"B3.x": {}}, "sub-slot"),
                         ({"A1": {"console": "serial"}}, "console must be")]:
            with self.assertRaisesRegex(bayctl.BayError, msg, msg=bad):
                self.load(bad)

    def test_hwmap_and_exports(self):
        b = self.load({"B3.1": {"platform": "xiao_esp32c3", "runner": "esp32", "serial": "/dev/ttyACM7"},
                       "B3.2": {"board": "rpi-pico2", "serial": "/dev/serial/by-id/usb-ZEPHYR_USB-DEV_9F2D-if00"},
                       "B3.3": {"board": "rpi-pico2"}, "B3.4": {"board": "xiao", "ci": False},
                       "A1": {"platform": "nucleo_g474re", "console": "none"}})
        with tempfile.TemporaryDirectory() as tmp:
            entries, warnings = bayctl.hwmap(b, Path(tmp), "python3", "/opt/rack/tools/bayctl.py", None)
            by = {e["fixtures"][0]: e for e in entries}
            self.assertIn("B3.2, B3.3 use uf2 without a probe id", " | ".join(warnings))   # two Pico 2
            b32 = by["bay:B3.2"]                                        # one entry per board
            self.assertEqual(b32["fixtures"][:2], ["bay:B3.2", "node:B3"])
            self.assertEqual(b32["serial"], "/dev/serial/by-id/usb-ZEPHYR_USB-DEV_9F2D-if00")
            self.assertNotIn("serial_pty", b32)
            self.assertTrue(b32["pre_script"].endswith("bay-b3-2-pre.sh"))
            self.assertIn("prepare B3.2", Path(b32["pre_script"]).read_text())
            self.assertEqual(by["bay:B3.1"]["id"], "/dev/ttyACM7")     # esp32: the board by its serial port
            self.assertNotIn("bay:B3.4", by)                            # ci: false
            self.assertFalse(by["bay:A1"]["connected"])                 # console none
            self.assertIn("bay A1: console none", " | ".join(warnings))
        t = bayctl.export_labgrid(b, "python3", "bayctl.py")["targets"]["bay-b3-2"]
        self.assertEqual(t["resources"], {})                            # power, no AUX UART
        self.assertNotIn("SerialDriver", t["drivers"])
        self.assertEqual(t["drivers"]["ExternalPowerDriver"]["cmd_cycle"], "python3 bayctl.py power B3.2 cycle")
        pdu = bayctl.export_pdudaemon(b, "python3", "bayctl.py")
        self.assertEqual(pdu["_ports"][3], "B3.2")                      # a port per board under test, rack order

    def test_analyzer(self):
        b = self.load({"B3.3": {"role": "analyzer", "ci": True, "serial": "/dev/ttyACM9"}, "B3.1": {}})
        self.assertEqual(b["B3.3"].role, "analyzer")
        self.assertIsNone(b["B3.3"].platform)                           # no Zephyr target
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


class HubLookup(unittest.TestCase):
    """Where the hub is, and what bayctl does when it does not answer."""

    def test_address(self):
        plain = lab_file({})
        with mock.patch.dict(os.environ, {"BAYCTL_HUB": "10.0.0.9:8080"}):
            self.assertEqual(bayctl.hub_address(lab_file({"hub": "rack.lan"})), "10.0.0.9:8080")   # first
            hub = bayctl.hub_device(plain)
            self.assertEqual((hub.host, hub.http_port), ("10.0.0.9", 8080))
        with mock.patch.dict(os.environ, {"BAYCTL_HUB": ""}):
            self.assertEqual(bayctl.hub_address(lab_file({"hub": "rack.lan"})), "rack.lan")
            self.assertEqual(bayctl.hub_address(lab_file({"domain": "lab"})), "rack.lab")
            self.assertEqual(bayctl.hub_address(plain), "rack.local")
            self.assertIsNone(bayctl.hub_address(lab_file({"hub": False})))
        self.assertIsNone(bayctl.hub_address(plain))                   # BAYCTL_HUB=none
        with self.assertRaisesRegex(bayctl.BayError, "no hub"):
            bayctl.hub_device(plain)

    def test_offline(self):
        """No hub at that address: a warning within seconds, and the lab file's entries."""
        dead = f"127.0.0.1:{free_port()}"
        warnings: list[str] = []
        with mock.patch.dict(os.environ, {"BAYCTL_HUB": dead}):
            b = bayctl.load_bays(lab_yaml=LAB_EXAMPLE, warnings=warnings)
        self.assertIn("A1", b)
        self.assertTrue(any("hub: cannot reach" in w and "config/lab.yaml" in w for w in warnings), warnings)
        with tempfile.TemporaryDirectory() as tmp:
            t0 = time.monotonic()
            r = subprocess.run([sys.executable, str(BAYCTL), "--lab", str(LAB_EXAMPLE), "hwmap",
                                "-o", str(Path(tmp) / "map.yaml"), "--python", "python3"],
                               capture_output=True, text=True, timeout=60, env={**os.environ, "BAYCTL_HUB": dead})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertLess(time.monotonic() - t0, 20)
            self.assertIn("warning: hub: cannot reach", r.stderr)
            self.assertIn("(7 boards)", r.stdout)

    def test_strings_retry(self):
        """A device just enumerated, its strings not read yet: one more look a second later, then a warning."""
        dev = {**MCULINK, "busid": "1-1.1"}
        slot = {"slot": "B3.1", "port": 1, "board": "frdm_mcxn947/mcxn947/cpu0", "console": "usb", "map": True}
        early, late = [{**slot, "device": {**dev, "strings": False}}], [{**slot, "device": {**dev, "strings": True}}]
        node = bayctl.Bay(id="B3", board="bay-node", host="127.0.0.1")
        lab = bayctl.Lab(lab_file({}))
        with mock.patch.object(bayctl, "node_slots", side_effect=[early, late]) as ns, \
                mock.patch.object(bayctl.time, "sleep") as sleep:
            self.assertEqual(bayctl._read_slots(node, lab), late)
        self.assertEqual((ns.call_count, sleep.call_args[0][0], lab.warnings), (2, bayctl.STRINGS_WAIT_S, []))
        with mock.patch.object(bayctl, "node_slots", side_effect=[early, early]), \
                mock.patch.object(bayctl.time, "sleep"):
            self.assertEqual(bayctl._read_slots(node, lab), early)
        self.assertIn("not read its device's USB strings yet", lab.warnings[0])


class AccessConfig(unittest.TestCase):
    """The `access:` section of config/lab.yaml, as the nodes get it."""

    def lab(self, doc: dict) -> Path:
        return lab_file(doc)

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


CONVERTED = [("xiao", "c-to-c"), ("rpi-pico2", "c-to-micro-b"), ("rpi-pico2", "c-to-micro-b"), ("xiao", "c-to-c")]


class Slots(unittest.TestCase):
    """config/rack.yaml › population (the mechanical side: tools/rackcfg.py): a bay's one board, or a
    converted bay's boards on one plate.  bayctl does not read it."""

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


# ------------------------------------------------------------------------- the simulated node

class NodeApi(unittest.TestCase):
    """bayctl against the firmware's simulated node (web/dev_server.py)."""

    @classmethod
    def setUpClass(cls):
        cls.proc, cls.port = start_node()
        cls.bay = bayctl.Bay(id="B3", board="rpi-pico2", host="127.0.0.1", http_port=cls.port)

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
        lab = lab_file({"bays": {"A1": {"host": "127.0.0.1", "http_port": self.port}}})
        r = subprocess.run([sys.executable, str(BAYCTL), "--lab", str(lab), "power", "a1", "cycle",
                            "--ms", "10"], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("VBUS on", r.stdout)

    def test_one_board(self):
        """A one-board node: one slot, named by the bay's position (here A1, whatever the node calls itself)."""
        b = bayctl.load_bays(lab_yaml=lab_file({"bays": {"A1": {"host": "127.0.0.1", "http_port": self.port}}}))
        a1 = b["A1"]
        self.assertEqual((list(b), a1.slot, a1.multi, a1.reported["port"]), (["A1"], None, False, 1))
        self.assertEqual(a1.device["vid"], "0483")                      # dev_server's NUCLEO's ST-LINK

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
    """A DATA ×4 bay against the simulated node with four ports (dev_server.py --ports 4): its sub-slots from
    the node itself (the lab file only gives its host)."""

    @classmethod
    def setUpClass(cls):
        cls.proc, cls.port = start_node("--ports", "4")
        cls.lab = lab_file({"bays": {"B3": {"host": "127.0.0.1", "http_port": cls.port}}})
        cls.bays = bayctl.load_bays(lab_yaml=cls.lab)
        cls.node = bayctl.node_bay(cls.bays, "B3")
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
        r = subprocess.run([sys.executable, str(BAYCTL), "--lab", str(self.lab), *args],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_ports(self):
        self.assertEqual([k for k in self.bays], ["B3.1", "B3.2", "B3.3", "B3.4"])   # the node's ports
        self.assertTrue(self.bays["B3.2"].multi)
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
        r = subprocess.run([sys.executable, str(BAYCTL), "--lab", str(self.lab), "boot", "A1", "--power-cycle"],
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
            with self.assertRaisesRegex(bayctl.BayError, "423"):              # its target too
                bayctl.api(b2, "/api/ports/2/board", {"board": "rpi_pico2/rp2350a/m33"}, method="PUT")
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


class LiveRack(unittest.TestCase):
    """The hardware map from the rack: a hub listing B3, the simulated DATA ×4 node there (dev_server.py
    --ports 4), each port's target set on the node (PUT /api/ports/<n>/board), the lab file over it."""

    TARGETS = {1: {"board": "frdm_mcxn947/mcxn947/cpu0", "runner": "linkserver", "console": "usb"},   # MCU-Link
               2: {"board": "nucleo_g474re", "console": "usb:00", "probe_id": "066DFF495150898367102236"},   # FT232
               3: {"board": "rpi_pico2/rp2350a/m33_0", "runner": "uf2"}}                             # Pico in BOOTSEL
    NXP = "/dev/serial/by-id/usb-NXP_Semiconductors_MCU-LINK_on-board__r0E7__CMSIS-DAP_V3.172_3ZQ1J4ZBMTNKS-if01"
    FTDI = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A50285BI-if00-port0"

    @classmethod
    def setUpClass(cls):
        cls.proc, cls.port = start_node("--ports", "4")
        cls.hub = FakeHub([{"id": 0x13, "pos": "B3", "ip": "127.0.0.1", "state": "ok", "dut_ma": 90},
                           {"id": 0x14, "pos": "B4", "ip": "0.0.0.0", "state": "lost"}])      # not on the rack now
        cls.env = mock.patch.dict(os.environ, {"BAYCTL_HUB": cls.hub.address})
        cls.env.start()
        cls.node = bayctl.Bay(id="B3", board="bay-node", host="127.0.0.1", http_port=cls.port)
        try:
            cls.wait_enumerated()
            for n, body in cls.TARGETS.items():
                cls.put(n, body)
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.hub.close()
        cls.proc.terminate()
        cls.proc.wait(5)

    @classmethod
    def wait_enumerated(cls):
        deadline = time.monotonic() + 10
        while not all(p["usb"] for p in bayctl.node_ports(cls.node)):
            if time.monotonic() > deadline:
                raise AssertionError("the boards never enumerated")
            time.sleep(0.1)

    @classmethod
    def put(cls, n: int, body: dict) -> dict:
        return bayctl.api(cls.node, f"/api/ports/{n}/board", body, method="PUT")

    def dev(self, path: str) -> None:
        urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}").read()

    def load(self, bays: dict | None = None, warnings: list | None = None) -> dict:
        lab = lab_file({"http_port": self.port, "bays": bays or {}})   # the hub gives no port: the lab's
        return bayctl.load_bays(lab_yaml=lab, warnings=warnings)

    def hwmap(self, bays: dict) -> tuple[dict, list[str]]:
        with tempfile.TemporaryDirectory() as tmp:
            entries, warnings = bayctl.hwmap(bays, Path(tmp), "python3", "/opt/rack/tools/bayctl.py", None)
        return {e["fixtures"][0]: e for e in entries}, warnings

    def cli(self, lab: Path, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(BAYCTL), "--lab", str(lab), *args],
                              capture_output=True, text=True, timeout=60)

    def test_hwmap_from_rack(self):
        b = self.load()
        self.assertEqual(list(b), ["B3.1", "B3.2", "B3.3", "B3.4"])  # B3 from the hub, its ports from the node
        self.assertEqual((b["B3.1"].host, b["B3.1"].board, b["B3.2"].board), ("127.0.0.1", "frdm-mcxn947", "nucleo-64"))
        by, warnings = self.hwmap(b)
        b31 = by["bay:B3.1"]
        self.assertEqual((b31["platform"], b31["runner"], b31["serial"]),
                         ("frdm_mcxn947/mcxn947/cpu0", "linkserver", self.NXP))
        self.assertEqual(b31["id"], "3ZQ1J4ZBMTNKS")                   # the device's USB serial
        self.assertEqual(b31["fixtures"], ["bay:B3.1", "node:B3"])
        b32 = by["bay:B3.2"]                                           # an FT232: a usb-serial bridge's -port0
        self.assertEqual((b32["serial"], b32["id"]), (self.FTDI, "066DFF495150898367102236"))
        self.assertEqual(b32["runner"], "stm32cubeprogrammer")         # none on the node: its family's
        b33 = by["bay:B3.3"]                                           # in BOOTSEL: no serial port
        self.assertFalse(b33["connected"])
        self.assertEqual(b33["id"], "E0C9125B0D9B")
        text = " | ".join(warnings)
        self.assertIn("bay B3.3: 2e8a:0003 RP2 Boot has no serial port", text)
        self.assertNotIn("bay:B3.4", by)                               # a CH340 but no target yet
        self.assertIn("bay B3.4 (1a86:7523): no board target: set its board target on the node's page", text)
        self.assertNotIn("B4", " ".join(b))                            # the hub lost it

    def test_lab_overrides(self):
        b = self.load({"B3.1": {"serial": "/dev/ttyACM3", "id": "X1", "fixtures": ["can"], "product": "MCU-Link"},
                       "B3.2": {"ci": False}, "B3.3": {"role": "analyzer"},
                       "B3.4": {"platform": "bbc_microbit_v2", "runner": "pyocd", "serial": "/dev/ttyUSB0"},
                       "A1": {"platform": "nucleo_g474re", "serial": "/dev/ttyACM9"}})
        self.assertEqual(list(b), ["A1", "B3.1", "B3.2", "B3.3", "B3.4"])
        self.assertIsNone(b["A1"].reported)                            # not on the rack: the lab's entry alone
        by, warnings = self.hwmap(b)
        b31 = by["bay:B3.1"]
        self.assertEqual((b31["serial"], b31["id"], b31["product"], b31["fixtures"]),
                         ("/dev/ttyACM3", "X1", "MCU-Link", ["bay:B3.1", "node:B3", "can"]))
        self.assertEqual(b31["platform"], "frdm_mcxn947/mcxn947/cpu0")   # still the node's
        self.assertNotIn("bay:B3.2", by)                               # ci: false
        self.assertNotIn("bay:B3.3", by)                               # an analyzer, by the lab file
        self.assertEqual((by["bay:B3.4"]["platform"], by["bay:B3.4"]["serial"]), ("bbc_microbit_v2", "/dev/ttyUSB0"))
        self.assertEqual((by["bay:A1"]["serial"], by["bay:A1"]["runner"]), ("/dev/ttyACM9", "stm32cubeprogrammer"))
        self.assertFalse(any("B3.4" in w for w in warnings))
        self.assertEqual([x.id for x in bayctl.dut_targets(b, "B3")], ["B3.1", "B3.2", "B3.4"])

    def test_mismatch_map_and_vacant(self):
        self.dev("/dev/usb?preset=ch340&port=2")                       # another board in port 2
        self.put(3, {**self.TARGETS[3], "map": False})                 # port 3 out of the map, on the node
        bayctl.api(self.node, "/api/ports/4/power", {"action": "off"})   # port 4: nothing in it, no target
        try:
            b = self.load()
            self.assertTrue(b["B3.2"].mismatch)
            self.assertTrue(b["B3.4"].vacant)
            by, warnings = self.hwmap(b)
            self.assertEqual(by["bay:B3.2"]["serial"], "/dev/serial/by-id/usb-1a86_7523-if00-port0")   # still written
            self.assertIn("bay B3.2: 1a86:7523 S/N - is not the board its target was saved for (0403:6001 S/N "
                          "A50285BI)", " | ".join(warnings))
            self.assertNotIn("bay:B3.3", by)                           # map: false
            self.assertFalse(any("B3.4" in w for w in warnings))       # an empty port: nothing to say
            self.assertEqual([x.id for x in bayctl.dut_targets(b, "B3")], ["B3.1", "B3.2", "B3.3"])
            self.assertEqual(len(bayctl.dut_targets(b, "B3", analyzers=True)), 4)   # its power: every port
            self.assertNotIn("B3.4", bayctl.export_pdudaemon(b, "python3", "bayctl.py")["_ports"].values())
            r = self.cli(lab_file({"http_port": self.port}), "list")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertRegex(r.stdout, r"B3\.4 +- +\(empty port\)")
            self.assertIn("[not the board its target was saved for]", r.stdout)
        finally:
            self.dev("/dev/usb?preset=ft232&port=2")
            self.put(3, self.TARGETS[3])
            bayctl.api(self.node, "/api/ports/4/power", {"action": "on"})
            self.wait_enumerated()

    def test_export_import(self):
        """export lab saves the targets with their pins; import lab writes them back, pins kept."""
        before = bayctl.api(self.node, "/api/boards")["slots"]
        doc = bayctl.export_lab(self.load())
        self.assertEqual(doc["bays"]["B3.1"], {"platform": "frdm_mcxn947/mcxn947/cpu0", "runner": "linkserver",
                                               "pin": {"vid": "1fc9", "pid": "0143", "serial": "3ZQ1J4ZBMTNKS"}})
        self.assertEqual(doc["bays"]["B3.2"]["console"], "usb:00")
        self.assertEqual(doc["bays"]["B3.2"]["id"], "066DFF495150898367102236")
        self.assertNotIn("B3.4", doc["bays"])                          # no target
        lab = lab_file({"http_port": self.port})
        backup = Path(tempfile.mkdtemp()) / "targets.yaml"
        r = self.cli(lab, "export", "lab", "-o", str(backup))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("(3 slots)", r.stdout)
        self.assertEqual(yaml.safe_load(backup.read_text(encoding="utf-8")), doc)
        try:
            for n in (1, 2, 3):
                self.put(n, {"board": None})                           # wiped (a node replaced, NVS erased)
            self.dev("/dev/usb?preset=xiao&port=1")                    # and another board in port 1 meanwhile
            r = self.cli(lab, "import", "lab", str(backup), "B3.2")    # one slot
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("B3.2: nucleo_g474re, pinned to 0403:6001 S/N A50285BI", r.stdout)
            self.assertIsNone(bayctl.api(self.node, "/api/ports/1/board")["board"])
            r = self.cli(lab, "import", "lab", str(backup))             # all of them
            self.assertEqual(r.returncode, 0, r.stderr)
            p1 = bayctl.api(self.node, "/api/ports/1/board")
            self.assertEqual(p1["pinned"], {"vid": "1fc9", "pid": "0143", "serial": "3ZQ1J4ZBMTNKS"})   # the pin kept
            self.assertTrue(p1["mismatch"])                            # the XIAO is not that board
        finally:
            self.dev("/dev/usb?preset=mculink&port=1")
        after = bayctl.api(self.node, "/api/boards")["slots"]
        keys = ("board", "runner", "probe_id", "console", "map", "pinned", "mismatch")
        self.assertEqual([{k: s[k] for k in keys} for s in after], [{k: s[k] for k in keys} for s in before])
        r = self.cli(lab, "import", "lab", str(backup), "C1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no entry for C1", r.stderr)

    def test_cli(self):
        lab = lab_file({"http_port": self.port})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rack-map.yaml"
            r = self.cli(lab, "hwmap", "-o", str(out), "--python", "python3")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("(3 boards)", r.stdout)
            entries = yaml.safe_load(out.read_text(encoding="utf-8"))
            self.assertEqual(entries[0]["serial"], self.NXP)
        r = self.cli(lab, "power", "B3", "off")                        # the node's ports, no lab entry for B3
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(any(p["power"]["on"] for p in bayctl.node_ports(self.node)))
        r = self.cli(lab, "power", "B3", "on")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.wait_enumerated()


class AccessApi(unittest.TestCase):
    """Claim, rules, lease and kicks against the simulated node (its own instance: it changes the rules)."""

    @classmethod
    def setUpClass(cls):
        cls.proc, cls.port = start_node()
        cls.bay = bayctl.Bay(id="B3", board="rpi-pico2", host="127.0.0.1", http_port=cls.port)
        cls.key = os.urandom(32)            # a test key, made up for this run

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
            with self.assertRaisesRegex(bayctl.BayError, "403"):    # a board target needs control
                bayctl.api(bay, "/api/ports/1/board", {"board": "nucleo_g474re"}, method="PUT")
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
        lab = lab_file({"bays": {"B3": {"host": "127.0.0.1", "http_port": self.port}}})
        tool = [sys.executable, str(BAYCTL), "--lab", str(lab)]
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
        lab = lab_file({"bays": {"A1": {"host": "127.0.0.1", "aux_port": port}}})
        p = subprocess.Popen([sys.executable, str(BAYCTL), "--lab", str(lab), "pty", "A1"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
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

        lab = lab_file({"hub": f"127.0.0.1:{self.port}"})              # the lab file's `hub:` (no BAYCTL_HUB)
        env = {**{k: v for k, v in os.environ.items() if k != "BAYCTL_HUB"}, "BAYCTL_KEY": self.key.hex()}

        def cli(*args: str) -> str:
            r = subprocess.run([sys.executable, str(BAYCTL), "--lab", str(lab), *args],
                               capture_output=True, text=True, timeout=30, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout

        out = cli("hub", "status")
        self.assertIn("PD 20.0 V / 5.00 A", out)    # 28 V EPR is opt-in (CONFIG_HUB_PD_EPR)
        self.assertIn("row A  ON", out)
        self.assertIn("row C  not fitted", out)
        self.assertIn("row D  not fitted", out)

        out = cli("row", "B", "off")
        self.assertIn("row B  OFF", out)
        out = cli("row", "B", "on")
        self.assertIn("row B  ON", out)

        # A row the hub does not have (power_hub.dtsi: rows C and D are not fitted)
        r = subprocess.run([sys.executable, str(BAYCTL), "--lab", str(lab), "row", "D", "on"],
                           capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("row not fitted", r.stderr)

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
        self.assertIn("row B on", out)


if __name__ == "__main__":
    unittest.main()
