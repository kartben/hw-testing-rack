"""Put back the committed version of a regenerated output whose content didn't change.

    python tools/keep_unchanged.py [--dry-run] [path ...]

A tool that regenerates a binary output (a Gerber zip, a schematic PDF, a render, a GLB, an STL) often writes
new bytes for the same content: a date, a member timestamp, a raytracer's noise.  Committed, each of those is
a new blob that stays in the repository's history.  This script looks at every tracked file under the paths
(the whole repository by default) that differs from HEAD and, when its content is the same, restores HEAD's
bytes, so an output is only committed with the change that alters it.  Same means, by type:

- .zip: the same member names, and the same bytes once the fab files' creation dates are out (fab_dates);
  member timestamps and order are ignored;
- .pdf: equal once /CreationDate, /ModDate and /ID are out;
- .png .jpg .jpeg: the same size, no 3 × 3 patch of pixels that moved by more than 32 levels, and an average
  difference under half a level (a raytraced render's noise is scattered single pixels; a part that moved
  is a patch);
- .glb: equal bytes, or the same JSON chunk (key order ignored) and the same binary chunk;
- .stl: the same triangles, in any order (binary or ASCII), to 0.1 µm, zero-area slivers left out.

tools/kicad.sh runs it on the board's folder after --fab.  Pillow is needed for images (skipped without it).
"""

from __future__ import annotations

import argparse
import io
import json
import re
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "electronics" / "tools"))
from fab_dates import undate  # noqa: E402

PIXEL_STEP = 32           # levels: a pixel that moved more than this counts as changed
PIXEL_MEAN = 0.5          # levels: the whole image's average difference


# ------------------------------------------------------------------ comparisons (bytes -> bytes -> bool)

def same_zip(a: bytes, b: bytes) -> bool:
    try:
        za, zb = zipfile.ZipFile(io.BytesIO(a)), zipfile.ZipFile(io.BytesIO(b))
    except zipfile.BadZipFile:
        return False
    if sorted(za.namelist()) != sorted(zb.namelist()):
        return False
    return all(undate(n, za.read(n)) == undate(n, zb.read(n)) for n in za.namelist())


_PDF_META = re.compile(rb"/(CreationDate|ModDate)\s*\([^)]*\)|/ID\s*\[[^\]]*\]")


def same_pdf(a: bytes, b: bytes) -> bool:
    return _PDF_META.sub(b"", a) == _PDF_META.sub(b"", b)


def same_image(a: bytes, b: bytes) -> bool:
    from PIL import Image, ImageChops, ImageFilter, ImageStat
    ia, ib = Image.open(io.BytesIO(a)), Image.open(io.BytesIO(b))
    if ia.size != ib.size:
        return False
    mode = "RGBA" if "A" in ia.getbands() or "A" in ib.getbands() else "RGB"
    diff = ImageChops.difference(ia.convert(mode), ib.convert(mode))
    if max(ImageStat.Stat(diff).mean) > PIXEL_MEAN:
        return False
    # the largest channel difference per pixel, then the changed pixels; an erosion keeps only 3 × 3 patches
    step = diff.split()[0]
    for band in diff.split()[1:]:
        step = ImageChops.lighter(step, band)
    moved = step.point(lambda v: 255 if v > PIXEL_STEP else 0)
    return moved.filter(ImageFilter.MinFilter(3)).getbbox() is None


def _glb_chunks(data: bytes):
    if len(data) < 12 or data[:4] != b"glTF":
        return None
    out, pos = {}, 12
    while pos + 8 <= len(data):
        size, kind = struct.unpack_from("<II", data, pos)
        out[kind] = data[pos + 8: pos + 8 + size]
        pos += 8 + size
    return out


def same_glb(a: bytes, b: bytes) -> bool:
    if a == b:
        return True
    ca, cb = _glb_chunks(a), _glb_chunks(b)
    if ca is None or cb is None or set(ca) != set(cb):
        return False
    json_kind = 0x4E4F534A
    for kind in ca:
        if kind == json_kind:
            if json.loads(ca[kind].rstrip(b" \0")) != json.loads(cb[kind].rstrip(b" \0")):
                return False
        elif ca[kind] != cb[kind]:
            return False
    return True


def _stl_triangles(data: bytes) -> list | None:
    """The triangles as sorted tuples of rounded vertices, each one turned to start at its smallest vertex
    (its winding kept)."""
    tris = []
    ascii_ = data[:5] == b"solid" and b"facet" in data[:1024]
    if ascii_:
        vs = [tuple(float(x) for x in m.groups()) for m in
              re.finditer(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", data)]
        if len(vs) % 3:
            return None
        raw = [vs[i:i + 3] for i in range(0, len(vs), 3)]
    else:
        if len(data) < 84:
            return None
        n = struct.unpack_from("<I", data, 80)[0]
        if len(data) < 84 + 50 * n:
            return None
        raw = []
        for i in range(n):
            v = struct.unpack_from("<12f", data, 84 + 50 * i)[3:]
            raw.append([v[0:3], v[3:6], v[6:9]])
    for t in raw:
        t = [tuple(round(c, 4) for c in v) for v in t]
        if _area2(t) < 1e-10:           # a zero-area sliver: OpenSCAD triangulates those differently run to run
            continue
        k = t.index(min(t))
        tris.append(tuple(t[k:] + t[:k]))
    return sorted(tris)


def _area2(t) -> float:
    """Twice a triangle's area, squared."""
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
    ux, uy, uz, vx, vy, vz = bx - ax, by - ay, bz - az, cx - ax, cy - ay, cz - az
    return (uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2


def same_stl(a: bytes, b: bytes) -> bool:
    ta, tb = _stl_triangles(a), _stl_triangles(b)
    return ta is not None and ta == tb


CHECKS = {".zip": same_zip, ".pdf": same_pdf, ".png": same_image, ".jpg": same_image, ".jpeg": same_image,
          ".glb": same_glb, ".stl": same_stl}


# ------------------------------------------------------------------ git

def git(*args, data: bool = False):
    p = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, check=True)
    return p.stdout if data else p.stdout.decode("utf-8", "replace")


def changed(paths: list[str]) -> list[str]:
    """Tracked files under the paths that differ from HEAD (staged or not), and still exist."""
    out = git("diff", "--name-only", "--diff-filter=M", "-z", "HEAD", "--", *(paths or ["."]))
    return [f for f in out.split("\0") if f and (REPO / f).exists()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="*", help="files or folders (default: the repository)")
    ap.add_argument("--dry-run", action="store_true", help="only say what would be restored")
    a = ap.parse_args(argv)
    paths = [Path(p).resolve().relative_to(REPO).as_posix() if Path(p).exists() else p for p in a.paths]
    kept, real, skipped = [], [], []
    for f in changed(paths):
        check = CHECKS.get(Path(f).suffix.lower())
        if check is None:
            continue
        try:
            same = check(git("show", f"HEAD:{f}", data=True), (REPO / f).read_bytes())
        except ImportError:
            skipped.append(f)
            continue
        (kept if same else real).append(f)
    if kept and not a.dry_run:
        git("checkout", "HEAD", "--", *kept)
    for f in kept:
        print(f"{'would keep' if a.dry_run else 'kept'} {f} (same content)")
    for f in real:
        print(f"changed   {f}")
    for f in skipped:
        print(f"skipped   {f} (Pillow missing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
