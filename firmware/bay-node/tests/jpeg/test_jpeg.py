"""Host test of the JPEG end finder (firmware/common/lib/jpeg.c) used by the bay camera.

    python firmware/bay-node/tests/jpeg/test_jpeg.py      # CC=gcc by default

The Arducam Mega hands its FIFO over in chunks with no end of frame mark;
the camera code cuts the frame at its EOI.  jpeg.c is plain C: built into a
shared library with a flat shim (shim.c) and fed real JPEGs from docs/img,
cut into pieces of every size, with junk before and after them.
"""

from __future__ import annotations

import ctypes
import os
import random
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMON = HERE.parents[2] / "common"
IMAGES = [HERE.parents[3] / "docs" / "img" / name for name in ("hero.jpg", "photo-boards.jpg")]

SOI, MARKER, LEN, SKIP, SCAN, DONE, ERROR = range(7)


def build(outdir: Path) -> ctypes.CDLL:
    lib = outdir / ("jpeg_shim.dll" if os.name == "nt" else "libjpeg_shim.so")
    cc = os.environ.get("CC", "gcc")
    subprocess.run([cc, "-shared", "-fPIC", "-O1", "-Wall", "-Wextra", "-Werror", "-I", str(COMMON / "include"),
                    str(HERE / "shim.c"), str(COMMON / "lib" / "jpeg.c"), "-o", str(lib)], check=True)
    dll = ctypes.CDLL(str(lib))
    dll.shim_size.restype = ctypes.c_size_t
    dll.shim_feed.restype = ctypes.c_size_t
    dll.shim_feed.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    dll.shim_image_size.restype = ctypes.c_uint
    return dll


class Scanner:
    def __init__(self, dll: ctypes.CDLL):
        self.dll = dll
        self.mem = ctypes.create_string_buffer(dll.shim_size())
        dll.shim_init(self.mem)

    def run(self, stream: bytes, cuts: list[int]) -> tuple[bytes, int]:
        """Feed the stream cut at these offsets; returns (the image found, final state)."""
        out = bytearray()
        bounds = [0, *sorted(set(c for c in cuts if 0 < c < len(stream))), len(stream)]
        for a, b in zip(bounds, bounds[1:]):
            piece = stream[a:b]
            start = ctypes.c_size_t(0)
            n = self.dll.shim_feed(self.mem, piece, len(piece), ctypes.byref(start))
            if self.dll.shim_lead_ff(self.mem):
                out += b"\xff"
            out += piece[start.value:start.value + n]
            if self.dll.shim_state(self.mem) in (DONE, ERROR):
                break
        return bytes(out), self.dll.shim_state(self.mem)


def with_thumbnail(jpeg: bytes) -> bytes:
    """The image with an APP1 segment after SOI holding a whole small JPEG (FF D8 ... FF D9)."""
    thumb = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
    payload = b"Exif\x00\x00" + thumb + b"\xff\xd9" * 3
    app1 = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    return jpeg[:2] + app1 + jpeg[2:]


class JpegScan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # the DLL stays loaded on Windows
        cls.dll = build(Path(cls.tmp.name))
        cls.images = [p.read_bytes() for p in IMAGES]
        for img in cls.images:
            assert img[:2] == b"\xff\xd8" and img.rstrip(b"\x00")[-2:] == b"\xff\xd9"

    @classmethod
    def tearDownClass(cls):
        del cls.dll
        cls.tmp.cleanup()

    def scan(self, stream: bytes, cuts: list[int]):
        return Scanner(self.dll).run(stream, cuts)

    def test_whole_and_every_chunk_size(self):
        rng = random.Random(42)
        for img in self.images:
            for size in (len(img), 4096, 1000, 64, 7, 2, 1):
                with self.subTest(size=size, image=len(img)):
                    out, state = self.scan(img, list(range(size, len(img), size)))
                    self.assertEqual(state, DONE)
                    self.assertEqual(out, img)
            for _ in range(20):
                cuts = rng.sample(range(1, len(img)), 50)
                out, state = self.scan(img, cuts)
                self.assertEqual((out, state), (img, DONE))

    def test_fifo_padding_after_eoi(self):
        img = self.images[0]
        stream = img + b"\x00" * 3000 + b"\xff\xd9" + bytes(range(256))
        out, state = self.scan(stream, list(range(4096, len(stream), 4096)))
        self.assertEqual((out, state), (img, DONE))

    def test_bytes_before_soi(self):
        img = self.images[0]
        for junk in (b"\x00", b"\x00" * 37, b"\xff", b"\x12\xff\xff"):
            for cut in (len(junk), len(junk) + 1, 1):
                with self.subTest(junk=junk, cut=cut):
                    out, state = self.scan(junk + img, [cut, 4096])
                    self.assertEqual((out, state), (img, DONE))

    def test_soi_split_across_pieces(self):
        img = self.images[0]
        stream = b"\x00\x00" + img
        out, state = self.scan(stream, [3])     # ... FF | D8 ...
        self.assertEqual((out, state), (img, DONE))

    def test_eoi_in_a_thumbnail_is_not_the_end(self):
        img = with_thumbnail(self.images[0])
        for size in (len(img), 64, 1):
            out, state = self.scan(img, list(range(size, len(img), size)))
            self.assertEqual((out, state), (img, DONE))

    def test_not_a_jpeg(self):
        out, state = self.scan(bytes(range(256)) * 8, [100, 1000])
        self.assertEqual(state, ERROR)
        out, state = self.scan(b"\xff\xd8\x12\x34", [])
        self.assertEqual(state, ERROR)

    def test_truncated(self):
        img = self.images[0]
        out, state = self.scan(img[:len(img) // 2], [1000])
        self.assertNotIn(state, (DONE, ERROR))
        self.assertEqual(out, img[:len(img) // 2])


if __name__ == "__main__":
    unittest.main()
