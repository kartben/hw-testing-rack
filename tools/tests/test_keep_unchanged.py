"""tools/keep_unchanged.py: which regenerated outputs count as unchanged, and build_board's deterministic zips."""

from __future__ import annotations

import io
import json
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "electronics" / "tools"))

import build_board  # noqa: E402
import keep_unchanged as ku  # noqa: E402
from fab_dates import undate  # noqa: E402

GERBER = (b"%TF.GenerationSoftware,KiCad,Pcbnew,10.0.6*%\n%TF.CreationDate,2026-10-22T16:46:49+00:00*%\n"
          b"G04 Created by KiCad (PCBNEW 10.0.6) date 2026-10-22 16:46:49*\nX0Y0D02*\nM02*\n")
DRILL = b"M48\n; DRILL file KiCad 10.0.6 date 2026-10-22T16:46:51\n; #@! TF.CreationDate,2026-10-22T16:46:51+00:00\nM30\n"
JOB = json.dumps({"Header": {"GenerationSoftware": {"Vendor": "KiCad"}, "CreationDate": "2026-10-22T16:46:49+00:00"},
                  "GeneralSpecs": {"LayerNumber": 4}}, indent=2).encode()


def later(data: bytes) -> bytes:
    return data.replace(b"2026-10-22T16:46:", b"2026-10-23T08:01:").replace(b"2026-10-22 16:46:", b"2026-10-23 08:01:")


def make_zip(members: dict, date=(2026, 10, 22, 16, 46, 48), reverse=False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(members, reverse=reverse):
            z.writestr(zipfile.ZipInfo(name, date_time=date), members[name])
    return buf.getvalue()


class FabDates(unittest.TestCase):
    def test_undate_removes_every_date(self):
        for name, data in (("b-F_Cu.gtl", GERBER), ("b-PTH.drl", DRILL), ("b-job.gbrjob", JOB)):
            self.assertNotIn(b"2026-10-22", undate(name, data), name)
            self.assertEqual(undate(name, data), undate(name, later(data)), name)

    def test_geometry_is_kept(self):
        self.assertIn(b"X0Y0D02*", undate("b-F_Cu.gtl", GERBER))
        self.assertIn(b"G04 Created by KiCad (PCBNEW 10.0.6)*", undate("b-F_Cu.gtl", GERBER))

    def test_write_zip_is_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "b-F_Cu.gtl").write_bytes(GERBER)
            (d / "b-PTH.drl").write_bytes(DRILL)
            build_board.write_zip(d / "one.zip", [d / "b-F_Cu.gtl", d / "b-PTH.drl"])
            (d / "b-F_Cu.gtl").write_bytes(later(GERBER))           # a later run: new dates, same board
            (d / "b-PTH.drl").write_bytes(later(DRILL))
            build_board.write_zip(d / "two.zip", [d / "b-PTH.drl", d / "b-F_Cu.gtl"])
            self.assertEqual((d / "one.zip").read_bytes(), (d / "two.zip").read_bytes())


class Zips(unittest.TestCase):
    def test_dates_and_order_are_ignored(self):
        a = make_zip({"b-F_Cu.gtl": GERBER, "b-PTH.drl": DRILL})
        b = make_zip({"b-F_Cu.gtl": later(GERBER), "b-PTH.drl": later(DRILL)}, date=(2026, 10, 23, 8, 1, 0), reverse=True)
        self.assertTrue(ku.same_zip(a, b))

    def test_a_changed_or_missing_member_counts(self):
        a = make_zip({"b-F_Cu.gtl": GERBER, "b-PTH.drl": DRILL})
        self.assertFalse(ku.same_zip(a, make_zip({"b-F_Cu.gtl": GERBER.replace(b"X0Y0", b"X1Y0"), "b-PTH.drl": DRILL})))
        self.assertFalse(ku.same_zip(a, make_zip({"b-F_Cu.gtl": GERBER})))


class Pdfs(unittest.TestCase):
    PDF = b"%PDF-1.5\n1 0 obj\n<< /Producer (KiCad PDF)\n/CreationDate (D:2026:10:23:08:35:25) >>\nendobj\ntrailer << /ID [<ab><cd>] >>\n"

    def test_dates_and_id_are_ignored(self):
        b = self.PDF.replace(b"08:35:25", b"09:00:00").replace(b"<ab><cd>", b"<12><34>")
        self.assertTrue(ku.same_pdf(self.PDF, b))

    def test_content_counts(self):
        self.assertFalse(ku.same_pdf(self.PDF, self.PDF.replace(b"KiCad PDF", b"KiCad PDF 2")))


def image_bytes(img, fmt="PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


class Images(unittest.TestCase):
    def setUp(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow missing")
        self.Image = Image
        self.base = Image.new("RGB", (200, 150), (60, 80, 60))

    def test_scattered_noise_is_the_same(self):
        noisy = self.base.copy()
        for x, y in ((10, 10), (50, 70), (120, 30), (190, 140)):     # isolated raytracer pixels
            noisy.putpixel((x, y), (200, 200, 200))
        self.assertTrue(ku.same_image(image_bytes(self.base), image_bytes(noisy)))

    def test_a_moved_part_is_a_change(self):
        part = self.base.copy()
        for x in range(100, 106):
            for y in range(60, 66):
                part.putpixel((x, y), (20, 20, 20))
        self.assertFalse(ku.same_image(image_bytes(self.base), image_bytes(part)))

    def test_a_faint_overall_shift_is_a_change(self):
        shifted = self.Image.new("RGB", self.base.size, (62, 82, 62))
        self.assertFalse(ku.same_image(image_bytes(self.base), image_bytes(shifted)))

    def test_jpeg_reencoding_is_the_same(self):
        a = image_bytes(self.base, "JPEG")
        b = image_bytes(self.Image.open(io.BytesIO(a)).convert("RGB"), "JPEG")
        self.assertTrue(ku.same_image(a, b))

    def test_size_counts(self):
        self.assertFalse(ku.same_image(image_bytes(self.base), image_bytes(self.base.resize((201, 150)))))


def glb(doc: str, binary: bytes) -> bytes:
    j = doc.encode()
    j += b" " * (-len(j) % 4)
    binary += b"\0" * (-len(binary) % 4)
    body = struct.pack("<II", len(j), 0x4E4F534A) + j + struct.pack("<II", len(binary), 0x004E4942) + binary
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


class Glbs(unittest.TestCase):
    def test_json_key_order_is_ignored(self):
        a = glb('{"asset": {"version": "2.0"}, "nodes": [{"name": "a"}]}', b"\1\2\3\4")
        b = glb('{"nodes": [{"name": "a"}], "asset": {"version": "2.0"}}', b"\1\2\3\4")
        self.assertTrue(ku.same_glb(a, b))

    def test_content_counts(self):
        a = glb('{"asset": {"version": "2.0"}}', b"\1\2\3\4")
        self.assertFalse(ku.same_glb(a, glb('{"asset": {"version": "2.0"}}', b"\1\2\3\5")))
        self.assertFalse(ku.same_glb(a, glb('{"asset": {"version": "2.1"}}', b"\1\2\3\4")))


def stl_binary(tris) -> bytes:
    out = b"\0" * 80 + struct.pack("<I", len(tris))
    for t in tris:
        out += struct.pack("<12fH", 0, 0, 1, *[c for v in t for c in v], 0)
    return out


def stl_ascii(tris) -> bytes:
    lines = ["solid OpenSCAD_Model"]
    for t in tris:
        lines += ["  facet normal 0 0 1", "    outer loop"] + [f"      vertex {v[0]} {v[1]} {v[2]}" for v in t] + \
                 ["    endloop", "  endfacet"]
    return ("\n".join(lines + ["endsolid OpenSCAD_Model"]) + "\n").encode()


class Stls(unittest.TestCase):
    T1 = ((0, 0, 0), (1, 0, 0), (0, 1, 0))
    T2 = ((1, 0, 0), (1, 1, 0), (0, 1, 0))

    def test_order_and_start_vertex_are_ignored(self):
        turned = (self.T2[1], self.T2[2], self.T2[0])                 # the same triangle, the same winding
        self.assertTrue(ku.same_stl(stl_binary([self.T1, self.T2]), stl_binary([turned, self.T1])))
        self.assertTrue(ku.same_stl(stl_ascii([self.T1, self.T2]), stl_ascii([self.T2, self.T1])))

    def test_zero_area_slivers_are_ignored(self):
        sliver = ((5, 5, 0), (5, 5, 1), (5, 5, 2))                       # three points on a line
        self.assertTrue(ku.same_stl(stl_binary([self.T1, self.T2]), stl_binary([self.T1, sliver, self.T2])))

    def test_geometry_counts(self):
        moved = ((0, 0, 0), (1, 0, 0), (0, 1.01, 0))
        self.assertFalse(ku.same_stl(stl_binary([self.T1, self.T2]), stl_binary([moved, self.T2])))
        flipped = (self.T1[0], self.T1[2], self.T1[1])                # the winding reversed: a flipped face
        self.assertFalse(ku.same_stl(stl_binary([self.T1]), stl_binary([flipped])))


if __name__ == "__main__":
    unittest.main()
