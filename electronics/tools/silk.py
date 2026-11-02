"""Silkscreen marks the boards share: b.pcb["texts"] entries for design.py, drawn by pcbgen.PcbBuilder.texts().

The silkscreen plan (2026-11-02): every DATA port numbered the same way, a digit knocked out of a filled disc; the
lead's pins named where it plugs in; a title block, the same on every board (title_block(): the logo, the name,
the date, on the rear face).  JLC's limits (jlcpcb.com/capabilities/pcb-capabilities and its
character-design guide): a 0.15 mm line and text 1.0 mm tall (0.8 in its high-precision class); a hollow character
0.2 mm in stroke, 1.5 mm tall, 0.2 mm (0.25 recommended) from the ink round it; for NextPCB's screen printing,
gaps 0.25 mm after a 0.05 mm spread a side (port_mark()).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SILK_TEXT = 0.15        # mm: the least text stroke (the layout review, 2026-11-01)
SILK_RULE = f"""
(rule "silkscreen text: a {SILK_TEXT} mm stroke at least"
	(severity error)
	(layer "?.Silkscreen")
	(constraint text_thickness (min {SILK_TEXT}mm)))
"""

# a port's number: a 1.8 mm digit, 0.35 mm stroke, knocked out of a 3.2 mm disc.  Its gaps (the stroke) 0.35 mm:
# 0.25 even after a screen printer's 0.05 mm spread a side (NextPCB, 2026-11-02: no published rule for negative
# text; another house asks 0.25 mm); its thinnest ink ≈ 0.9 mm
MARK_D, MARK_SIZE, MARK_STROKE = 3.2, 1.8, 0.35
MARK_GAP = 0.25 + 2 * 0.05      # the least stroke: 0.25 mm open after the ink spreads 0.05 mm a side


def port_mark(n, x: float, y: float, layer: str = "F.SilkS", d: float = MARK_D, size: float = MARK_SIZE,
              stroke: float = MARK_STROKE) -> dict:
    """Port n's number at (x, y): the digit (or letter) knocked out of a filled silk disc d mm across."""
    assert size >= 1.5, "a hollow character: 1.5 mm tall at least (JLC)"
    assert stroke >= MARK_GAP - 1e-9, f"a hollow character's gap (its stroke): {MARK_GAP} mm at least"
    assert (d - size) / 2 >= 0.25, "0.25 mm of disc at least round the character"
    return {"text": str(n), "x": x, "y": y, "size": size, "thickness": stroke, "layer": layer, "style": "disc",
            "d": d}


def lead_pin_names(x: float, y_pin1: float, names, pitch: float = 2.0, layer: str = "B.SilkS") -> list[dict]:
    """A PH lead's pin names, 1.0 mm tall, pin 1 at y_pin1 and the pins `pitch` apart up the board (−y), each at
    the same x and right-justified there (on B.SilkS, read from behind, that is against the housing)."""
    return [{"text": nm, "x": x, "y": y_pin1 - pitch * k, "size": 1.0, "thickness": SILK_TEXT, "layer": layer,
             "just": "right"} for k, nm in enumerate(names)]


# The BitBunk logo (bitbunk-logo.svg, the user's, 2026-11-02) is not printable as drawn: the boards on its two
# shelves have pins and chips 1–2 units wide, so its least gap would need it over 100 mm wide.  Its silk variant
# (derive_logo()): each shelf's board a plain convex silhouette; the gaps between the frame, the B and the boards,
# and the i's dot, opened to the wordmark's own tightest letter gap (LOGO_G units; the lettering unchanged); the
# slivers those cuts leave dropped (an opening of LOGO_R units).  Its outlines are bitbunk-logo.silk.json
# (`python3 electronics/tools/silk.py` writes it; shapely, which the KiCad image lacks).
LOGO_SVG = Path(__file__).with_name("bitbunk-logo.svg")
LOGO_SILK = LOGO_SVG.with_suffix(".silk.json")
LOGO_G, LOGO_R = 5.54, 1.7      # SVG units
LOGO_GAP, LOGO_INK = 0.25, 0.15     # mm: its least gap (0.15 left after a 0.05 mm spread a side) and line
LOGO_W = 25.6                   # mm: the narrowest at which its gaps are LOGO_GAP (the same on every board)
TITLE_DATE = "2026-11"          # the boards' revision date (the NextPCB prototypes)


def _svg_rings(svg: Path) -> list[list[tuple[float, float]]]:
    d = re.search(r' d="([^"]+)"', svg.read_text(encoding="utf-8")).group(1)
    rings, cur = [], []
    for cmd, args in re.findall(r"([MLZ])([^MLZ]*)", d):
        nums = [float(v) for v in re.findall(r"-?\d+\.?\d*", args)]
        if cmd == "M":
            if len(cur) > 2:
                rings.append(cur)
            cur, nums = [tuple(nums[:2])], nums[2:]
        if cmd in "ML":
            cur += [tuple(nums[i:i + 2]) for i in range(0, len(nums), 2)]
        if cmd == "Z":
            if len(cur) > 2:
                rings.append(cur)
            cur = []
    if len(cur) > 2:
        rings.append(cur)
    return rings


def derive_logo(svg: Path = LOGO_SVG):
    """The silk variant of the logo, a shapely MultiPolygon in SVG units (y down, as the board)."""
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    rings = _svg_rings(svg)
    geom = None
    for r in rings:                         # fill-rule evenodd
        p = Polygon(r).buffer(0)
        geom = p if geom is None else geom.symmetric_difference(p)
    # rings 1 and 23: the two shelves' boards, filled whole (their chips and pins are holes in them)
    solid = unary_union([geom, Polygon(rings[1]).buffer(0), Polygon(rings[23]).buffer(0)])

    def part(x0, y0):
        return next(p for p in solid.geoms if abs(p.bounds[0] - x0) < 1 and abs(p.bounds[1] - y0) < 1)
    frame, b, up, low = part(-46.7, -183.4), part(-62.4, -132.2), part(-21.9, -151.6), part(4.7, -76.9)
    frame = frame.difference(b.buffer(LOGO_G))         # the shelves' bars stop LOGO_G short of the B
    up, low = (s.convex_hull.difference(frame.buffer(LOGO_G)).difference(b.buffer(LOGO_G)) for s in (up, low))
    word = geom.difference(box(-70, -190, 90, 0))
    dot = next(p for p in word.geoms if p.bounds[1] < -134 and p.bounds[2] < 192)
    stem = next(p for p in word.geoms if abs(p.bounds[0] - 169.06) < 0.1 and p.bounds[1] > -112)
    word = word.difference(dot).union(dot.difference(stem.buffer(LOGO_G)))
    silk = unary_union([frame, b, up, low, word])
    return silk.buffer(-LOGO_R, quad_segs=8).buffer(LOGO_R, quad_segs=8).union(word)


def write_logo(path: Path = LOGO_SILK):
    """bitbunk-logo.silk.json: the variant's outlines, origin at its top-left corner, in SVG units."""
    silk = derive_logo()
    x0, y0 = silk.bounds[:2]

    def ring(r):
        return [[round(x - x0, 3), round(y - y0, 3)] for x, y in list(r.coords)[:-1]]
    polys = [[ring(p.exterior)] + [ring(h) for h in p.interiors] for p in silk.geoms]
    path.write_text(json.dumps({"source": LOGO_SVG.name, "gap_units": LOGO_G,
                                "size_units": [round(silk.bounds[2] - x0, 3), round(silk.bounds[3] - y0, 3)],
                                "polys": polys}, separators=(",", ":")) + "\n", encoding="utf-8")


def logo(x: float, y: float, w: float = LOGO_W, layer: str = "B.SilkS") -> dict:
    """The logo w mm wide, its top-left corner as read at (x, y): on B.SilkS read from below, so drawn mirrored
    (it runs towards −x).  A b.pcb["texts"] entry of style "poly": filled outlines, holes after each outline."""
    d = json.loads(LOGO_SILK.read_text(encoding="utf-8"))
    k, sx = w / d["size_units"][0], -1 if layer == "B.SilkS" else 1
    polys = [[[(round(x + sx * k * u, 4), round(y + k * v, 4)) for u, v in r] for r in p] for p in d["polys"]]
    return {"style": "poly", "layer": layer, "polys": polys, "w": w, "h": k * d["size_units"][1]}


def title_block(name: str, x: float, y: float, date: str = TITLE_DATE, layer: str = "B.SilkS") -> list[dict]:
    """Every board's title block, the same on all (the user, 2026-11-02): the logo LOGO_W wide, under it the
    board's name and revision at 1.5 mm, then the revision's date (fixed per revision, never the build's) at
    1.0 mm, left-aligned; (x, y) its top-left corner as read, on the rear face read from below."""
    mark = logo(x, y, layer=layer)
    y1 = round(y + mark["h"] + 1.0 + 0.75, 3)          # the name's middle: 1 mm under the logo
    return [mark,
            {"text": name, "x": x, "y": y1, "size": 1.5, "thickness": 0.25, "layer": layer, "just": "left"},
            {"text": date, "x": x, "y": round(y1 + 0.75 + 0.6 + 0.5, 3), "size": 1.0, "thickness": SILK_TEXT,
             "layer": layer, "just": "left"}]


if __name__ == "__main__":
    write_logo()
    print(f"wrote {LOGO_SILK}")
