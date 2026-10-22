"""Specctra DSN text edits, before Freerouting reads the file (plain Python: no pcbnew).

KiCad's exporter writes every copper zone as a `(plane NET (polygon LAYER ...))` and every rule area as a
keep-out.  These helpers work on the file's text by list spans, so whatever they don't touch stays
byte for byte as KiCad wrote it.
"""

from __future__ import annotations

import random
import re

_ATOM = re.compile(r'"(?:[^"\\]|\\.)*"|[^\s()"]+')


def _skip_quoted(text: str, i: int) -> int:
    """Index past the quoted string at text[i]; the parser's own `(string_quote ")` is one character."""
    if text.startswith("string_quote", max(0, i - 13)) and text[i - 13:i].rstrip().endswith("string_quote"):
        return i + 1
    j = text.find('"', i + 1)
    return len(text) if j < 0 else j + 1


def span(text: str, i: int) -> int:
    """Index just past the list that opens at text[i] ("("), quoted strings skipped."""
    depth, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i = _skip_quoted(text, i)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced list")


def children(text: str, start: int, end: int | None = None) -> list[tuple[int, int, str]]:
    """The direct child lists of the list at text[start:end]: (start, end, keyword)."""
    end = span(text, start) if end is None else end
    out, i = [], start + 1
    while i < end - 1:
        c = text[i]
        if c == "(":
            j = span(text, i)
            m = _ATOM.match(text, i + 1)
            out.append((i, j, m.group(0) if m else ""))
            i = j
        elif c == '"':
            i = _skip_quoted(text, i)
        else:
            i += 1
    return out


def find(text: str, *path: str) -> tuple[int, int] | None:
    """Span of the first list reached by following keywords from the top-level (pcb ...) down."""
    s, e = 0, None
    s = text.index("(")
    e = span(text, s)
    for key in path:
        hit = next(((a, b) for a, b, k in children(text, s, e) if k == key), None)
        if hit is None:
            return None
        s, e = hit
    return s, e


def atoms(block: str) -> list[str]:
    """The atoms of a list's head, up to its first child list: "(plane GND (polygon ..." → [plane, GND]."""
    head = block[1:block.find("(", 1) if "(" in block[1:] else len(block) - 1]
    return [a.strip('"') for a in _ATOM.findall(head)]


def shuffle(text: str, seed: int) -> str:
    """The same board with its nets (network) and components (placement) in another order.

    Freerouting numbers nets and items in the order it reads them, and its passes walk them in that order:
    a permutation is another start for the same problem (its "net order"), and stays deterministic."""
    rng = random.Random(seed)
    for path, key in ((("network",), "net"), (("placement",), "component")):
        where = find(text, *path)
        if where is None:
            continue
        kids = [(a, b) for a, b, k in children(text, *where) if k == key]
        if len(kids) < 2:
            continue
        blocks = [text[a:b] for a, b in kids]
        order = blocks[:]
        rng.shuffle(order)
        # the lists sit at the same places, in the new order
        out, last = [], 0
        for (a, b), blk in zip(kids, order):
            out += [text[last:a], blk]
            last = b
        text = "".join(out) + text[last:]
    return text


def _num(v: float) -> str:
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def planes(text: str) -> list[tuple[int, int, str, str]]:
    """The structure's (plane NET (polygon LAYER ...)) entries: (start, end, net token as written, layer)."""
    where = find(text, "structure")
    out = []
    for a, b, k in children(text, *where) if where else []:
        if k != "plane":
            continue
        head = _ATOM.findall(text[a + 1:text.find("(", a + 1)])
        poly = children(text, a, b)
        layer = _ATOM.findall(text[poly[0][0] + 1:poly[0][1] - 1])[1] if poly else ""
        out.append((a, b, head[1] if len(head) > 1 else "", layer))
    return out


def replace_planes(text: str, areas: dict[int, list[list[tuple[float, float]]]]) -> str:
    """The text with plane entry i (in planes()' order) replaced by one entry per outline of areas[i]: closed
    point lists in mm, KiCad axes (Y down), written as KiCad's exporter does (µm, Y up).  An empty list drops
    the plane; an index not in areas stays as KiCad wrote it."""
    entries = planes(text)
    out, last = [], 0
    for i, (a, b, net, layer) in enumerate(entries):
        if i not in areas:
            continue
        indent = text[text.rfind("\n", 0, a) + 1:a]
        polys = []
        for pts in areas[i]:
            if pts and pts[0] != pts[-1]:
                pts = pts + pts[:1]
            coords = "  ".join(f"{_num(x * 1000)} {_num(-y * 1000)}" for x, y in pts)
            polys.append(f"(plane {net} (polygon {layer} 0  {coords}))")
        out += [text[last:a], f"\n{indent}".join(polys)]
        last = b
        if not polys:          # drop the line the entry stood on
            out[-2] = out[-2].rstrip(" ")
            last = b + 1 if text[b:b + 1] == "\n" else b
    return "".join(out) + text[last:]


def no_via_at_smd(text: str) -> str:
    """The structure's control set to (via_at_smd off): Freerouting then never drops a via on an SMD pad, where
    an open via drains the solder from a small part's joint (KiCad's export says nothing, and Freerouting
    allows it).  An existing control block is replaced."""
    s, e = find(text, "structure")
    ctl = next(((a, b) for a, b, k in children(text, s, e) if k == "control"), None)
    first = next(iter(children(text, s, e)), None)
    at = ctl[0] if ctl else (first[0] if first else e - 1)
    indent = text[text.rfind("\n", 0, at) + 1:at] if first else "    "
    block = "(control (via_at_smd off))"
    if ctl:
        return text[:ctl[0]] + block + text[ctl[1]:]
    return text[:at] + block + "\n" + indent + text[at:]


def split_planes_as_signals(text: str) -> tuple[str, list[str]]:
    """A power layer that carries the planes of several nets (a split plane) turned into a signal layer that no
    wire may use (a wire_keepout over the board): its nets are routed as signals, pad by pad to the plane's
    area through vias, instead of as plane nets.  Returns the text and the layers changed."""
    where = find(text, "structure")
    nets: dict[str, set[str]] = {}
    for _, _, net, layer in planes(text):
        nets.setdefault(layer, set()).add(net)
    split = []
    edits = []
    for a, b, k in children(text, *where):
        if k != "layer":
            continue
        name = _ATOM.findall(text[a + 1:text.find("(", a + 1)])[1]
        block = text[a:b]
        if "(type power)" in block and len(nets.get(name, ())) > 1:
            split.append(name)
            edits.append((a, b, block.replace("(type power)", "(type signal)")))
    if not split:
        return text, []
    bound = find(text, "structure", "boundary")
    xs, ys = [], []
    nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", text[bound[0]:bound[1]])[1:]]
    xs, ys = nums[0::2], nums[1::2]
    x0, x1, y0, y1 = min(xs) - 1000, max(xs) + 1000, min(ys) - 1000, max(ys) + 1000
    keep = "".join(f'\n    (wire_keepout "split-plane" (polygon {n} 0  {_num(x0)} {_num(y0)}  {_num(x1)} {_num(y0)}  '
                   f'{_num(x1)} {_num(y1)}  {_num(x0)} {_num(y1)}  {_num(x0)} {_num(y0)}))' for n in split)
    out, last = [], 0
    for a, b, new in edits:
        out += [text[last:a], new]
        last = b
    text = "".join(out) + text[last:]
    where = find(text, "structure")
    end = where[1] - 1
    return text[:end].rstrip() + keep + "\n  " + text[end:], split


# the lists whose order KiCad's export doesn't keep from one build of the same board to the next (the
# footprints' UUIDs are new each time): (path to the parent list, keywords of the children sorted together;
# they keep the places such children had, filled in keyword order, then text order)
UNORDERED = ((("structure",), ("plane", "keepout", "wire_keepout", "via_keepout")),
             (("placement",), ("component",)), (("library",), ("image", "padstack")),
             (("network",), ("net",)), (("network",), ("class",)), (("wiring",), ("wire", "via")))


def _sort_children(text: str, path: tuple, keys: tuple) -> str:
    where = find(text, *path)
    if where is None:
        return text
    kids = [(a, b, k) for a, b, k in children(text, *where) if k in keys]
    blocks = sorted(((keys.index(k), text[a:b]) for a, b, k in kids))
    out, last = [], 0
    for (a, b, _), (_, blk) in zip(kids, blocks):
        out += [text[last:a], blk]
        last = b
    return "".join(out) + text[last:]


def _sorted_atoms(block: str, key: str) -> str:
    """A list's (KEY a b c) children with their atoms sorted: a net's pins, a component's places."""
    def fix(m):
        return m.group(1) + " ".join(sorted(m.group(2).split())) + ")"
    return re.sub(r"(\(" + key + r"\s+)([^()]*)\)", fix, block)


def _round_images(text: str) -> str:
    """The library's images with their coordinates to 0.1 µm: KiCad computes them back from each placed
    footprint, and two builds disagree in the last digit (0.01 µm) where the footprints turned."""
    where = find(text, "library")
    if where is None:
        return text
    out, last = [], where[0]
    for a, b, k in children(text, *where):
        if k == "image":
            out += [text[last:a], re.sub(r"(?<=\s)-?\d+\.\d+(?=[\s)])", lambda m: _num(round(float(m.group(0)), 1)),
                                         text[a:b])]
            last = b
    return text[:where[0]] + "".join(out) + text[last:]


def _rename_images(text: str) -> str:
    """KiCad tells apart footprints of one name that differ (a pad's net-tie, a rotation) as NAME::1,
    NAME::2… in the order it meets them: name each by a hash of its own definition instead."""
    import hashlib
    where = find(text, "library")
    if where is None:
        return text
    images = []
    for a, b, k in children(text, *where):
        if k == "image":
            name = _ATOM.findall(text[a + 1:b])[1]
            images.append((name, name.strip('"').split("::")[0], text[a + 1 + text[a + 1:b].index(name) + len(name):b]))
    shared = {base for _, base, _ in images if sum(1 for _, b2, _ in images if b2 == base) > 1}
    names = {}
    for name, base, body in images:
        if base in shared:
            new = f"{base}::{hashlib.sha256(body.encode()).hexdigest()[:8]}"
            names[name] = f'"{new}"' if name.startswith('"') else new
    if not names:
        return text
    pat = re.compile(r"(\((?:image|component)\s+)(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
                     + r")(?=[\s)])")
    return pat.sub(lambda m: m.group(1) + names[m.group(2)], text)


def _split_wires(text: str) -> str:
    """Pre-routed wires one segment each: KiCad joins a fixed track's segments into one path or not
    depending on the order it finds them."""
    where = find(text, "wiring")
    if where is None:
        return text
    pat = re.compile(r"\(wire \(path (\S+) (\S+)((?:\s+-?[\d.]+\s+-?[\d.]+){3,})\)(.*)\)$", re.S)
    out, last = [], where[0]
    for a, b, k in children(text, *where):
        m = pat.match(" ".join(text[a:b].split())) if k == "wire" else None
        if not m:
            continue
        layer, width, coords, rest = m.groups()
        v = coords.split()
        pts = list(zip(v[0::2], v[1::2]))
        indent = text[text.rfind("\n", 0, a) + 1:a]
        segs = [f"(wire (path {layer} {width}  {p[0]} {p[1]}  {q[0]} {q[1]}){rest})" for p, q in zip(pts, pts[1:])]
        out += [text[last:a], f"\n{indent}".join(segs)]
        last = b
    return text[:where[0]] + "".join(out) + text[last:]


def canonical(text: str) -> str:
    """The same board with KiCad's unordered lists sorted: two exports of one design give one DSN, so
    Freerouting (deterministic for a given DSN) routes it the same way every time."""
    text = _split_wires(_rename_images(_round_images(text)))
    for path, keys in UNORDERED:
        text = _sort_children(text, path, keys)
    # inside them: each net's pins, each component's places
    where = find(text, "network")
    if where:
        text = text[:where[0]] + _sorted_atoms(text[where[0]:where[1]], "pins") + text[where[1]:]
    where = find(text, "placement")
    if where:
        for a, b, k in reversed(children(text, *where)):
            if k == "component":
                places = sorted((text[x:y] for x, y, kk in children(text, a, b) if kk == "place"))
                spans = [(x, y) for x, y, kk in children(text, a, b) if kk == "place"]
                out, last = [], a
                for (x, y), blk in zip(spans, places):
                    out += [text[last:x], blk]
                    last = y
                text = text[:a] + "".join(out) + text[last:]
    return text
