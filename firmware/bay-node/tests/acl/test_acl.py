"""Host test of the access rules (firmware/common/lib/acl.c): rules, lease, kicks, log, HMAC.

    python firmware/bay-node/tests/acl/test_acl.py      # CC=gcc by default

acl.c has no Zephyr dependency: it is built into a shared library with a
flat shim (shim.c) and driven through ctypes.  SHA-256 and HMAC-SHA256 are
checked against Python's hashlib and hmac.
"""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import os
import random
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMON = HERE.parents[2] / "common"

STATUS, CONTROL, CONSOLE, USBIP, SHELL, CAMERA = range(6)
ALL = 0x3F
OK, NOT_ALLOWED, RESERVED, KICKED = range(4)
EBUSY, EINVAL, ENOENT, EPERM, ENOSPC = 16, 22, 2, 1, 28


def bit(*services: int) -> int:
    return sum(1 << s for s in services)


def build(outdir: Path) -> ctypes.CDLL:
    lib = outdir / ("acl_shim.dll" if os.name == "nt" else "libacl_shim.so")
    cc = os.environ.get("CC", "gcc")
    subprocess.run([cc, "-shared", "-fPIC", "-O1", "-Wall", "-Wextra", "-Werror", "-I", str(COMMON / "include"),
                    str(HERE / "shim.c"), str(COMMON / "lib" / "acl.c"), "-o", str(lib)], check=True)
    dll = ctypes.CDLL(str(lib))
    s, i, ll, u, sz = ctypes.c_char_p, ctypes.c_int, ctypes.c_longlong, ctypes.c_uint, ctypes.c_size_t
    sigs = {
        "shim_reset": ([], None), "shim_rules": ([i, i], None), "shim_add": ([s, s, i], i),
        "shim_rights": ([s], i), "shim_source_of": ([s], i), "shim_check": ([ll, i, s], i),
        "shim_lease_take": ([ll, s, u, s], i), "shim_lease_release": ([ll, s, i], i),
        "shim_lease_note": ([], s), "shim_block": ([ll, s, i, u], None),
        "shim_refused": ([ll, s, i, i], None), "shim_refused_total": ([], u),
        "shim_log": ([i, s, sz], None), "shim_cidr": ([s, s], i), "shim_ip": ([s, s], i),
        "shim_service_mask": ([s], i), "shim_copy_text": ([s, s, sz], None),
        "shim_name_valid": ([s], i), "shim_sha256": ([s, sz, sz, s], None),
        "shim_hmac": ([s, sz, s, sz, s], None), "shim_equal": ([s, s, sz], i),
        "shim_hex_decode": ([s, s, sz], i), "shim_hex_encode": ([s, sz, s], None),
    }
    for name, (args, res) in sigs.items():
        fn = getattr(dll, name)
        fn.argtypes, fn.restype = args, res
    return dll


class Acl:
    """Pythonic wrapper over the shim."""

    def __init__(self, lib: ctypes.CDLL):
        self.lib = lib
        lib.shim_reset()

    def rules(self, enabled: bool, everyone: int = bit(STATUS)) -> None:
        self.lib.shim_rules(int(enabled), everyone)

    def add(self, name: str, cidr: str, allow: int) -> int:
        return self.lib.shim_add(name.encode(), cidr.encode(), allow)

    def check(self, now: int, svc: int, ip: str) -> int:
        return self.lib.shim_check(now, svc, ip.encode())

    def rights(self, ip: str) -> int:
        return self.lib.shim_rights(ip.encode())

    def take(self, now: int, ip: str, ttl: int, note: str = "") -> int:
        return self.lib.shim_lease_take(now, ip.encode(), ttl, note.encode())

    def release(self, now: int, ip: str, force: bool = False) -> int:
        return self.lib.shim_lease_release(now, ip.encode(), int(force))

    def log(self) -> list[str]:
        out = []
        for i in range(16):
            buf = ctypes.create_string_buffer(96)
            self.lib.shim_log(i, buf, len(buf))
            if buf.value:
                out.append(buf.value.decode())
        return out


class TestAcl(unittest.TestCase):
    lib: ctypes.CDLL

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.lib = build(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls) -> None:
        # The DLL stays loaded on Windows: leave the directory behind there
        try:
            cls.tmp.cleanup()
        except OSError:
            pass

    def setUp(self) -> None:
        self.acl = Acl(self.lib)

    # --- Text -----------------------------------------------------------------

    def test_cidr(self) -> None:
        good = {"192.168.1.23": "192.168.1.23", "192.168.1.23/32": "192.168.1.23",
                "192.168.1.40/30": "192.168.1.40", "192.168.1.43/30": "192.168.1.40/30",
                "10.0.0.0/8": "10.0.0.0/8", "0.0.0.0/0": "0.0.0.0/0", "255.255.255.255": "255.255.255.255"}
        for text, want in good.items():
            out = ctypes.create_string_buffer(20)
            self.assertEqual(self.lib.shim_cidr(text.encode(), out), 0, text)
            if text != "192.168.1.40/30":
                self.assertEqual(out.value.decode(), want, text)
        out = ctypes.create_string_buffer(20)
        self.lib.shim_cidr(b"192.168.1.40/30", out)
        self.assertEqual(out.value, b"192.168.1.40/30")
        for bad in ["", "192.168.1", "192.168.1.256", "192.168.1.1/33", "192.168.01.1", "1.2.3.4/",
                    "1.2.3.4/032", "1.2.3.4 ", " 1.2.3.4", "1.2.3.4.5", "a.b.c.d", "1..2.3", "1.2.3.4/x",
                    "1234.1.1.1"]:
            self.assertEqual(self.lib.shim_cidr(bad.encode(), out), -EINVAL, repr(bad))
        self.assertEqual(self.lib.shim_ip(b"192.168.1.40/30", out), -EINVAL)
        self.assertEqual(self.lib.shim_ip(b"8.8.4.4", out), 0)
        self.assertEqual(out.value, b"8.8.4.4")

    def test_services_and_names(self) -> None:
        for name, svc in [("status", STATUS), ("control", CONTROL), ("console", CONSOLE),
                          ("usbip", USBIP), ("shell", SHELL), ("camera", CAMERA)]:
            self.assertEqual(self.lib.shim_service_mask(name.encode()), bit(svc))
        self.assertEqual(self.lib.shim_service_mask(b"all"), ALL)
        self.assertEqual(self.lib.shim_service_mask(b"web"), 0)
        for good in ["ci-runners", "ben_laptop", "a", "prometheus.lab", "x" * 15]:
            self.assertTrue(self.lib.shim_name_valid(good.encode()), good)
        for bad in ["", "x" * 16, "ben laptop", 'a"b', "café", "a<b"]:
            self.assertFalse(self.lib.shim_name_valid(bad.encode()), bad)
        out = ctypes.create_string_buffer(12)
        self.lib.shim_copy_text('job "8812"\\ok'.encode(), out, len(out))
        self.assertEqual(out.value, b"job _8812__")    # 11 characters kept, quotes replaced

    # --- Rules ----------------------------------------------------------------

    def test_open_until_enabled(self) -> None:
        acl = self.acl
        self.assertEqual(acl.rights("192.168.1.77"), ALL)
        acl.rules(True)
        self.assertEqual(acl.rights("192.168.1.77"), bit(STATUS))
        acl.rules(True, everyone=0)
        self.assertEqual(acl.rights("192.168.1.77"), 0)
        self.assertEqual(acl.check(0, STATUS, "192.168.1.77"), NOT_ALLOWED)

    def test_sources_add_up(self) -> None:
        acl = self.acl
        acl.rules(True)
        self.assertEqual(acl.add("ci-runners", "192.168.1.40/30", bit(STATUS, CONTROL, CONSOLE, USBIP)), 0)
        self.assertEqual(acl.add("ben-laptop", "192.168.1.23", ALL), 0)
        self.assertEqual(acl.add("lab", "192.168.1.0/24", bit(CONSOLE)), 0)
        self.assertEqual(acl.rights("192.168.1.41"), bit(STATUS, CONTROL, CONSOLE, USBIP))
        self.assertEqual(acl.rights("192.168.1.44"), bit(STATUS, CONSOLE))
        self.assertEqual(acl.rights("192.168.1.23"), ALL)
        self.assertEqual(acl.rights("10.0.0.1"), bit(STATUS))
        self.assertEqual(acl.check(0, SHELL, "192.168.1.41"), NOT_ALLOWED)
        self.assertEqual(acl.check(0, SHELL, "192.168.1.23"), OK)
        # The most specific source names the address
        self.assertEqual(self.lib.shim_source_of(b"192.168.1.23"), 1)
        self.assertEqual(self.lib.shim_source_of(b"192.168.1.42"), 0)
        self.assertEqual(self.lib.shim_source_of(b"192.168.1.99"), 2)
        self.assertEqual(self.lib.shim_source_of(b"10.1.1.1"), -1)
        # An unknown peer (0.0.0.0) matches no source, even 0.0.0.0/0
        acl.add("any", "0.0.0.0/0", bit(USBIP))
        self.assertEqual(acl.rights("10.1.1.1"), bit(STATUS, USBIP))
        self.assertEqual(acl.rights("0.0.0.0"), bit(STATUS))

    def test_add_limits(self) -> None:
        acl = self.acl
        self.assertEqual(acl.add("bad name", "1.2.3.4", ALL), -EINVAL)
        self.assertEqual(acl.add("x", "1.2.3.4", ALL + 1), -EINVAL)
        for i in range(8):
            self.assertEqual(acl.add(f"h{i}", f"10.0.0.{i + 1}", ALL), 0)
        self.assertEqual(acl.add("h8", "10.0.0.9", ALL), -ENOSPC)

    def test_bad_service(self) -> None:
        self.assertEqual(self.acl.check(0, CAMERA + 1, "192.168.1.1"), NOT_ALLOWED)

    # --- Lease ----------------------------------------------------------------

    def test_lease(self) -> None:
        acl = self.acl
        acl.rules(True)
        acl.add("ci", "192.168.1.40/30", bit(STATUS, CONTROL, CONSOLE, USBIP))
        acl.add("ben", "192.168.1.23", ALL)
        self.assertEqual(acl.take(1000, "192.168.1.41", 60, "twister job 8812"), 0)
        self.assertEqual(self.lib.shim_lease_note(), b"twister job 8812")
        for svc in (CONTROL, CONSOLE, USBIP):
            self.assertEqual(acl.check(2000, svc, "192.168.1.41"), OK)
            self.assertEqual(acl.check(2000, svc, "192.168.1.42"), RESERVED)
            self.assertEqual(acl.check(2000, svc, "192.168.1.23"), RESERVED)   # admins too
        # Status and the shell are not part of a lease
        self.assertEqual(acl.check(2000, STATUS, "192.168.1.42"), OK)
        self.assertEqual(acl.check(2000, SHELL, "192.168.1.23"), OK)
        # Another host cannot take it; the holder renews it
        self.assertEqual(acl.take(2000, "192.168.1.42", 60), -EBUSY)
        self.assertEqual(acl.take(30000, "192.168.1.41", 60, "renewed"), 0)
        self.assertEqual(acl.check(70000, USBIP, "192.168.1.42"), RESERVED)
        # It lapses by itself
        self.assertEqual(acl.check(90000, USBIP, "192.168.1.42"), OK)
        self.assertEqual(acl.release(90000, "192.168.1.41"), -ENOENT)
        self.assertEqual(acl.take(90000, "192.168.1.42", 60), 0)

    def test_lease_release(self) -> None:
        acl = self.acl
        self.assertEqual(acl.take(0, "192.168.1.41", 600), 0)
        self.assertEqual(acl.release(10, "192.168.1.42"), -EPERM)
        self.assertEqual(acl.release(10, "192.168.1.42", force=True), 0)
        self.assertEqual(acl.check(20, CONTROL, "192.168.1.42"), OK)
        self.assertEqual(acl.take(0, "192.168.1.41", 600), 0)
        self.assertEqual(acl.release(10, "192.168.1.41"), 0)

    def test_lease_on_open_node(self) -> None:
        """A lease works with the rules off: CI gets the bay to itself."""
        acl = self.acl
        self.assertEqual(acl.take(0, "192.168.1.41", 600), 0)
        self.assertEqual(acl.check(1, USBIP, "192.168.1.99"), RESERVED)
        self.assertEqual(acl.check(1, STATUS, "192.168.1.99"), OK)

    def test_lease_bounds(self) -> None:
        acl = self.acl
        self.assertEqual(acl.take(0, "192.168.1.41", 9), -EINVAL)
        self.assertEqual(acl.take(0, "192.168.1.41", 86401), -EINVAL)
        self.assertEqual(acl.take(0, "0.0.0.0", 60), -EINVAL)
        self.assertEqual(acl.take(0, "192.168.1.41", 86400, "x" * 80), 0)
        self.assertEqual(len(self.lib.shim_lease_note()), 39)

    # --- Kicks, log -------------------------------------------------------------

    def test_block(self) -> None:
        acl = self.acl
        self.lib.shim_block(1000, b"192.168.1.41", bit(USBIP), 60000)
        self.assertEqual(acl.check(2000, USBIP, "192.168.1.41"), KICKED)
        self.assertEqual(acl.check(2000, CONSOLE, "192.168.1.41"), OK)
        self.assertEqual(acl.check(2000, USBIP, "192.168.1.42"), OK)
        self.lib.shim_block(3000, b"192.168.1.41", bit(CONSOLE), 60000)   # merged
        self.assertEqual(acl.check(4000, USBIP, "192.168.1.41"), KICKED)
        self.assertEqual(acl.check(4000, CONSOLE, "192.168.1.41"), KICKED)
        self.assertEqual(acl.check(63001, USBIP, "192.168.1.41"), OK)
        # More blocks than slots: the one ending first goes
        for i in range(5):
            self.lib.shim_block(70000 + i, f"10.0.0.{i + 1}".encode(), bit(SHELL), 1000 + i)
        self.assertEqual(acl.check(70100, SHELL, "10.0.0.1"), OK)
        for i in range(1, 5):
            self.assertEqual(acl.check(70100, SHELL, f"10.0.0.{i + 1}"), KICKED, i)

    def test_refused_log(self) -> None:
        acl = self.acl
        for t in range(5):
            self.lib.shim_refused(1000 + t, b"192.168.1.77", USBIP, NOT_ALLOWED)
        self.lib.shim_refused(2000, b"192.168.1.42", CONTROL, RESERVED)
        self.lib.shim_refused(3000, b"192.168.1.77", USBIP, KICKED)
        self.assertEqual(acl.log(), ["192.168.1.77 usbip not_allowed 5 1000 1004",
                                     "192.168.1.42 control reserved 1 2000 2000",
                                     "192.168.1.77 usbip kicked 1 3000 3000"])
        self.assertEqual(self.lib.shim_refused_total(), 7)
        # Full: the entry seen least recently makes room
        for i in range(16):
            self.lib.shim_refused(10000 + i, f"10.0.0.{i + 1}".encode(), SHELL, NOT_ALLOWED)
        log = acl.log()
        self.assertEqual(len(log), 16)
        self.assertFalse(any(e.startswith("192.168.1.") for e in log))
        self.lib.shim_refused(20000, b"10.0.0.16", SHELL, NOT_ALLOWED)
        self.assertIn("10.0.0.16 shell not_allowed 2 10015 20000", acl.log())
        self.lib.shim_refused(20001, b"10.0.0.99", SHELL, NOT_ALLOWED)
        log = acl.log()
        self.assertNotIn("10.0.0.1 shell not_allowed 1 10000 10000", log)
        self.assertIn("10.0.0.99 shell not_allowed 1 20001 20001", log)

    # --- Crypto ---------------------------------------------------------------

    def test_sha256(self) -> None:
        rnd = random.Random(1)
        lengths = [0, 1, 3, 55, 56, 57, 63, 64, 65, 119, 120, 127, 128, 129, 1000]
        lengths += [rnd.randrange(2000) for _ in range(40)]
        for n in lengths:
            data = rnd.randbytes(n)
            for chunk in (1, 7, 64, max(n, 1)):
                out = ctypes.create_string_buffer(32)
                self.lib.shim_sha256(data, n, chunk, out)
                self.assertEqual(out.raw, hashlib.sha256(data).digest(), (n, chunk))

    def test_hmac(self) -> None:
        rnd = random.Random(2)
        cases = [(b"key", b"The quick brown fox jumps over the lazy dog"), (b"", b"")]
        cases += [(rnd.randbytes(k), rnd.randbytes(m)) for k in (16, 32, 63, 64, 65, 200) for m in (0, 10, 300)]
        for key, msg in cases:
            out = ctypes.create_string_buffer(32)
            self.lib.shim_hmac(key, len(key), msg, len(msg), out)
            self.assertEqual(out.raw, hmac.new(key, msg, hashlib.sha256).digest(), (len(key), len(msg)))
        # RFC 4231 test case 2
        out = ctypes.create_string_buffer(32)
        self.lib.shim_hmac(b"Jefe", 4, b"what do ya want for nothing?", 28, out)
        self.assertEqual(out.raw.hex(), "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843")

    def test_equal_and_hex(self) -> None:
        self.assertTrue(self.lib.shim_equal(b"abcd", b"abcd", 4))
        self.assertFalse(self.lib.shim_equal(b"abcd", b"abce", 4))
        data = bytes(range(256))[:32]
        out = ctypes.create_string_buffer(65)
        self.lib.shim_hex_encode(data, 32, out)
        self.assertEqual(out.value.decode(), data.hex())
        back = ctypes.create_string_buffer(32)
        self.assertEqual(self.lib.shim_hex_decode(out.value.upper(), back, 32), 0)
        self.assertEqual(back.raw, data)
        for bad in [data.hex()[:-1], data.hex() + "0", data.hex()[:-1] + "g"]:
            self.assertEqual(self.lib.shim_hex_decode(bad.encode(), back, 32), -EINVAL)


if __name__ == "__main__":
    unittest.main()
