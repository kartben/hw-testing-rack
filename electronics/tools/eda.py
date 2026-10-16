"""Schematic-as-code for the test-rack boards.

A board is described in Python (see `electronics/<board>/design.py`): parts,
the nets their pins connect to, BOM fields and PCB placement hints.  From that
single description this module writes a real, hierarchical KiCad schematic
(`.kicad_sch`, one sheet per functional block, label-based connections), and
`pcbgen.py` builds the matching `.kicad_pcb`.  KiCad's ERC/DRC (with schematic
parity) then validate that both views agree.

The generated schematics are meant to be read and reviewed in KiCad.  Edit
the Python description and regenerate rather than editing the outputs.
"""

from __future__ import annotations

import copy
import json
import math
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sexp import S, Sym, dumps, find, find_all, loads, yes

GRID = 1.27
KICAD_SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
REPO = Path(__file__).resolve().parents[2]
PROJECT_LIB_DIR = REPO / "electronics" / "lib"
NS = uuid.UUID("6f1c2a3e-6b1d-4c55-9a43-7d0d2b5b1e10")

# Nets that get a KiCad power symbol instead of a label.
POWER_SYMBOLS = {
    "GND": "power:GND",
    "+3V3": "power:+3V3",
    "+5V": "power:+5V",
    "+24V": "power:+24V",
}


def snap(v: float) -> float:
    return round(round(v / GRID) * GRID, 4)


def uid(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


# ----------------------------------------------------------------- symbols

@dataclass
class Pin:
    number: str
    name: str
    etype: str
    x: float  # symbol coordinates (y up)
    y: float
    rot: int
    length: float
    hidden: bool = False

    @property
    def outward(self) -> tuple[int, int]:
        """Direction pointing away from the symbol body, in *schematic* coords (y down)."""
        return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[self.rot % 360]


@dataclass
class SymbolDef:
    lib_id: str
    node: list  # flattened symbol, name = lib_id
    pins: list[Pin]
    bbox: tuple[float, float, float, float]  # xmin, ymin, xmax, ymax in schematic coords
    is_power: bool


class SymbolLib:
    def __init__(self):
        self._files: dict[str, list] = {}
        self._cache: dict[str, SymbolDef] = {}

    def _lib(self, lib: str) -> list:
        if lib not in self._files:
            for base in (PROJECT_LIB_DIR, KICAD_SYMBOL_DIR):
                p = base / f"{lib}.kicad_sym"
                if p.exists():
                    self._files[lib] = loads(p.read_text(encoding="utf-8"))
                    break
            else:
                raise FileNotFoundError(f"symbol library {lib} not found")
        return self._files[lib]

    def _raw(self, lib: str, name: str) -> list:
        for s in find_all(self._lib(lib), "symbol"):
            if s[1] == name:
                return s
        raise KeyError(f"symbol {lib}:{name} not found")

    def _flatten(self, lib: str, name: str) -> list:
        raw = copy.deepcopy(self._raw(lib, name))
        ext = find(raw, "extends")
        if not ext:
            return raw
        parent = self._flatten(lib, ext[1])
        pname = parent[1]
        out = [Sym("symbol"), name]
        child_props = {p[1]: p for p in find_all(raw, "property")}
        for item in parent[2:]:
            if isinstance(item, list) and item and item[0] == "property" and item[1] in child_props:
                out.append(child_props.pop(item[1]))
            elif isinstance(item, list) and item and item[0] == "symbol":
                sub = copy.deepcopy(item)
                sub[1] = sub[1].replace(pname, name, 1)
                out.append(sub)
            else:
                out.append(item)
        # child-only properties go right after the inherited ones
        insert_at = max(i for i, x in enumerate(out) if isinstance(x, list) and x[0] == "property") + 1
        for p in child_props.values():
            out.insert(insert_at, p)
            insert_at += 1
        return out

    def get(self, lib_id: str) -> SymbolDef:
        if lib_id in self._cache:
            return self._cache[lib_id]
        lib, name = lib_id.split(":", 1)
        node = self._flatten(lib, name)
        node[1] = lib_id
        pins: list[Pin] = []
        xs, ys = [], []
        for sub in find_all(node, "symbol"):
            suffix = sub[1].rsplit("_", 2)
            unit, style = int(suffix[-2]), int(suffix[-1])
            if unit not in (0, 1) or style not in (0, 1):
                continue
            for item in sub[2:]:
                if not isinstance(item, list):
                    continue
                if item[0] == "pin":
                    at = find(item, "at")
                    ln = find(item, "length")[1]
                    p = Pin(
                        number=str(find(item, "number")[1]),
                        name=str(find(item, "name")[1]),
                        etype=str(item[1]),
                        x=at[1], y=at[2], rot=int(at[3]) if len(at) > 3 else 0,
                        length=ln,
                        hidden=bool(find(item, "hide")) or Sym("hide") in item,
                    )
                    pins.append(p)
                    xs.append(p.x)
                    ys.append(p.y)
                    dx, dy = {0: (1, 0), 180: (-1, 0), 90: (0, 1), 270: (0, -1)}[p.rot % 360]
                    xs.append(p.x + dx * ln)
                    ys.append(p.y + dy * ln)
                elif item[0] in ("rectangle",):
                    for k in ("start", "end"):
                        pt = find(item, k)
                        xs.append(pt[1]); ys.append(pt[2])
                elif item[0] in ("polyline", "bezier"):
                    for pt in find_all(find(item, "pts"), "xy"):
                        xs.append(pt[1]); ys.append(pt[2])
                elif item[0] == "circle":
                    c = find(item, "center"); r = find(item, "radius")[1]
                    xs += [c[1] - r, c[1] + r]; ys += [c[2] - r, c[2] + r]
                elif item[0] == "arc":
                    for k in ("start", "mid", "end"):
                        pt = find(item, k)
                        xs.append(pt[1]); ys.append(pt[2])
        if not xs:
            xs, ys = [0], [0]
        # convert to schematic coords (flip y)
        bbox = (min(xs), -max(ys), max(xs), -min(ys))
        is_power = find(node, "power") is not None
        sd = SymbolDef(lib_id, node, pins, bbox, is_power)
        self._cache[lib_id] = sd
        return sd


LIB = SymbolLib()


# ----------------------------------------------------------------- design model

@dataclass
class Part:
    ref: str
    lib_id: str
    value: str
    footprint: str
    conns: dict[str, str]
    fields: dict[str, str] = field(default_factory=dict)
    description: str = ""
    datasheet: str = ""
    dnp: bool = False
    in_bom: bool = True
    on_board: bool = True
    pcb: dict = field(default_factory=dict)  # placement hints: x, y, rot, side
    sheet: "Sheet | None" = None
    sch_at: tuple[float, float] | None = None

    @property
    def sym(self) -> SymbolDef:
        return LIB.get(self.lib_id)

    def pin_nets(self) -> dict[str, str]:
        """Resolve `conns` (keys = pin number or pin name) to {pin_number: net}."""
        out: dict[str, str] = {}
        pins = self.sym.pins
        by_num = {p.number: p for p in pins}
        for key, net in self.conns.items():
            if net is None:
                continue
            if key in by_num:
                out[key] = net
                continue
            matched = [p for p in pins if p.name == key]
            if not matched:
                raise KeyError(f"{self.ref} ({self.lib_id}): no pin named/numbered {key!r}. "
                               f"Pins: {sorted({p.name for p in pins})}")
            for p in matched:
                out[p.number] = net
        return out


@dataclass
class Sheet:
    name: str
    file: str
    title: str
    board: "Board"
    parts: list[Part] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    blocks: list[tuple[str, list[Part]]] = field(default_factory=list)
    paper: str = "A3"

    def block(self, title: str):
        self.blocks.append((title, []))
        return self

    def add(self, part: Part) -> Part:
        part.sheet = self
        if not self.blocks:
            self.blocks.append(("", []))
        self.blocks[-1][1].append(part)
        self.parts.append(part)
        self.board.register(part)
        return part

    # convenience constructors ---------------------------------------
    def part(self, ref, lib_id, value, footprint, conns, **kw) -> Part:
        return self.add(Part(ref, lib_id, value, footprint, conns, **kw))

    def R(self, ref, value, a, b, size="0603", **kw) -> Part:
        fp = f"Resistor_SMD:R_{size}_{_metric(size)}Metric"
        kw.setdefault("description", f"Resistor {value} {size}")
        return self.part(ref, "Device:R", value, fp, {"1": a, "2": b}, **kw)

    def C(self, ref, value, a, b, size="0603", **kw) -> Part:
        fp = f"Capacitor_SMD:C_{size}_{_metric(size)}Metric"
        kw.setdefault("description", f"Capacitor {value} {size}")
        return self.part(ref, "Device:C", value, fp, {"1": a, "2": b}, **kw)

    def note(self, text: str):
        self.notes.append(text)


def _metric(size: str) -> str:
    return {"0402": "1005", "0603": "1608", "0805": "2012", "1206": "3216", "1210": "3225",
            "2010": "5025", "2512": "6332"}[size]


class Board:
    def __init__(self, name: str, title: str, rev: str, company: str = "hw-testing-rack",
                 comments: list[str] | None = None):
        self.name = name
        self.title = title
        self.rev = rev
        self.company = company
        self.comments = comments or []
        self.sheets: list[Sheet] = []
        self.parts: dict[str, Part] = {}
        self.root_notes: list[str] = []
        self.pcb: dict = {}

    def sheet(self, name: str, file: str, title: str | None = None, paper: str = "A3") -> Sheet:
        sh = Sheet(name, file, title or name, self, paper=paper)
        self.sheets.append(sh)
        return sh

    def register(self, part: Part):
        if part.ref in self.parts:
            raise ValueError(f"duplicate reference {part.ref}")
        self.parts[part.ref] = part

    # -- netlist ------------------------------------------------------
    def nets(self) -> dict[str, list[tuple[str, str]]]:
        nets: dict[str, list[tuple[str, str]]] = {}
        for p in self.parts.values():
            for num, net in p.pin_nets().items():
                nets.setdefault(net, []).append((p.ref, num))
        return nets

    def net_sheets(self) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for p in self.parts.values():
            for net in p.pin_nets().values():
                out.setdefault(net, set()).add(p.sheet.file)
        return out

    def check(self):
        """Fail early on obvious netlist mistakes (single-pin nets)."""
        problems = []
        for net, pins in self.nets().items():
            if len(pins) < 2 and not net.startswith("NC_") and not net.startswith("TP_"):
                problems.append(f"net {net!r} only has one pin: {pins}")
        return problems

    # -- uuids ---------------------------------------------------------
    @property
    def root_uuid(self) -> str:
        return uid(self.name, "root")

    def sheet_uuid(self, sh: Sheet) -> str:
        return uid(self.name, "sheet", sh.file)

    def sym_uuid(self, p: Part) -> str:
        return uid(self.name, "sym", p.ref)

    def pcb_path(self, p: Part) -> str:
        return f"/{self.sheet_uuid(p.sheet)}/{self.sym_uuid(p)}"

    def pcb_net_name(self, net: str) -> str:
        """Net name as KiCad derives it: power symbols and cross-sheet (global) labels keep
        their name, local labels are prefixed with their sheet path."""
        if net in POWER_SYMBOLS:
            return net
        sheets = self.net_sheets().get(net, set())
        if len(sheets) > 1:
            return net
        sh = next(s for s in self.sheets if s.file in sheets)
        return f"/{sh.name}/{net}"


# ----------------------------------------------------------------- writer

def _font(size=1.27, hide=False, justify=None, bold=False):
    eff = S("effects", S("font", S("size", size, size), *( [S("bold", Sym("yes"))] if bold else [])))
    if justify:
        eff.append(S("justify", *[Sym(j) for j in justify.split()]))
    if hide:
        eff.append(S("hide", Sym("yes")))
    return eff


def _prop(name, value, x, y, rot=0, hide=False, justify=None, size=1.27):
    return S("property", name, value, S("at", x, y, rot), _font(size, hide, justify))


def _text_w(s: str, size=1.27) -> float:
    return len(s) * size * 0.75 + 2.0


class SheetWriter:
    STUB = 2.54

    def __init__(self, board: Board, sheet: Sheet, page: int, cross_nets: set[str]):
        self.b = board
        self.sh = sheet
        self.page = page
        self.cross = cross_nets
        self.items: list = []
        self.lib_ids: set[str] = set()
        self.pwr_n = 0

    @property
    def inst_path(self) -> str:
        return f"/{self.b.root_uuid}/{self.b.sheet_uuid(self.sh)}"

    def paper_size(self):
        return {"A4": (297, 210), "A3": (420, 297), "A2": (594, 420), "A1": (841, 594)}[self.sh.paper]

    # layout ------------------------------------------------------------
    def _extent(self, p: Part):
        """Symbol bbox grown by stubs + labels (schematic coords relative to origin)."""
        x0, y0, x1, y1 = p.sym.bbox
        nets = p.pin_nets()
        l = r = t = bt = 0.0
        for pin in p.sym.pins:
            net = nets.get(pin.number)
            w = self.STUB + (_text_w(net) + 3 if net and net not in POWER_SYMBOLS else 5.0)
            dx, dy = pin.outward
            px, py = pin.x, -pin.y
            if dx < 0:
                l = max(l, (x0 - px) + w) if px <= x0 + 0.01 else max(l, w)
            elif dx > 0:
                r = max(r, w)
            elif dy > 0:
                bt = max(bt, w)
            else:
                t = max(t, w)
        return (x0 - l - 2, y0 - max(t, 4) - 2, x1 + r + 2, y1 + max(bt, 4) + 2)

    def layout(self):
        W, H = self.paper_size()
        margin_x, top = 20.0, 30.0
        x, y = margin_x, top
        row_h = 0.0
        for title, parts in self.sh.blocks:
            if not parts:
                continue
            # block header
            if x > margin_x:
                x = margin_x
                y += row_h + 8
                row_h = 0
            if title:
                self.items.append(S("text", title, S("exclude_from_sim", Sym("no")),
                                    S("at", snap(x), snap(y), 0), _font(2.0, justify="left bottom", bold=True),
                                    S("uuid", uid(self.b.name, self.sh.file, "blk", title))))
                y += 6
            for p in parts:
                ex0, ey0, ex1, ey1 = self._extent(p)
                w, h = ex1 - ex0, ey1 - ey0
                if x + w > W - margin_x and x > margin_x:
                    x = margin_x
                    y += row_h + 4
                    row_h = 0
                ox, oy = snap(x - ex0), snap(y - ey0)
                p.sch_at = (ox, oy)
                x += w + 4
                row_h = max(row_h, h)
            x = W  # force new row for next block
        self.used_h = y + row_h

    # emitters ------------------------------------------------------------
    def emit_symbol(self, p: Part):
        sd = p.sym
        self.lib_ids.add(p.lib_id)
        ox, oy = p.sch_at
        x0, y0, x1, y1 = sd.bbox
        props = [
            _prop("Reference", p.ref, snap(ox + x1 + 1.27) if (x1 - x0) < 8 else ox, snap(oy + y0 - 1.27),
                  justify="left" if (x1 - x0) < 8 else None),
            _prop("Value", p.value, snap(ox + x1 + 1.27) if (x1 - x0) < 8 else ox, snap(oy + y1 + 1.27) if (x1 - x0) >= 8 else snap(oy + y0 + 1.27),
                  justify="left" if (x1 - x0) < 8 else None),
            _prop("Footprint", p.footprint, ox, oy, hide=True),
            _prop("Datasheet", p.datasheet, ox, oy, hide=True),
            _prop("Description", p.description, ox, oy, hide=True),
        ]
        for k, v in p.fields.items():
            props.append(_prop(k, v, ox, oy, hide=True))
        node = S("symbol", S("lib_id", p.lib_id), S("at", ox, oy, 0), S("unit", 1),
                 S("exclude_from_sim", Sym("no")), S("in_bom", yes(p.in_bom)), S("on_board", yes(p.on_board)),
                 S("dnp", yes(p.dnp)), S("fields_autoplaced", Sym("yes")),
                 S("uuid", self.b.sym_uuid(p)), *props)
        for pin in sd.pins:
            node.append(S("pin", pin.number, S("uuid", uid(self.b.name, p.ref, "pin", pin.number))))
        node.append(S("instances", S("project", self.b.name,
                                     S("path", f"/{self.b.root_uuid}/{self.b.sheet_uuid(self.sh)}",
                                       S("reference", p.ref), S("unit", 1)))))
        self.items.append(node)
        # connections
        nets = p.pin_nets()
        for pin in sd.pins:
            px, py = snap(ox + pin.x), snap(oy - pin.y)
            net = nets.get(pin.number)
            if net is None:
                if pin.etype != "no_connect" and not pin.hidden:
                    self.items.append(S("no_connect", S("at", px, py), S("uuid", uid(self.b.name, p.ref, "nc", pin.number))))
                continue
            dx, dy = pin.outward
            sx, sy = snap(px + dx * self.STUB), snap(py + dy * self.STUB)
            self.items.append(S("wire", S("pts", S("xy", px, py), S("xy", sx, sy)),
                                S("stroke", S("width", 0), S("type", Sym("default"))),
                                S("uuid", uid(self.b.name, p.ref, "w", pin.number))))
            self.connect(net, sx, sy, (dx, dy), f"{p.ref}.{pin.number}")

    def connect(self, net: str, x: float, y: float, d: tuple[int, int], key: str):
        if net in POWER_SYMBOLS:
            self.power_symbol(POWER_SYMBOLS[net], x, y, d, key)
            return
        angle = {(-1, 0): 180, (1, 0): 0, (0, 1): 270, (0, -1): 90}[d]
        just = {0: "left", 180: "right", 90: "left", 270: "right"}[angle]
        if net in self.cross:
            self.items.append(S("global_label", net, S("shape", Sym("bidirectional")), S("at", x, y, angle),
                                S("fields_autoplaced", Sym("yes")), _font(1.27, justify=just),
                                S("uuid", uid(self.b.name, key, "gl")),
                                _prop("Intersheetrefs", "${INTERSHEET_REFS}", x, y, hide=True, justify=just)))
        else:
            self.items.append(S("label", net, S("at", x, y, angle), S("fields_autoplaced", Sym("yes")),
                                _font(1.27, justify=f"{just} bottom"), S("uuid", uid(self.b.name, key, "lb"))))

    def power_symbol(self, lib_id: str, x: float, y: float, d, key: str):
        self.lib_ids.add(lib_id)
        self.pwr_n += 1
        sd = LIB.get(lib_id)
        name = lib_id.split(":")[1]
        # GND-like symbols hang down, supply symbols point up
        rot = 0
        if name.startswith("GND"):
            rot = {(0, -1): 180}.get(d, 0)
        else:
            rot = {(0, 1): 180}.get(d, 0)
        ref = f"#PWR{self.page:02d}{self.pwr_n:03d}"
        node = S("symbol", S("lib_id", lib_id), S("at", x, y, rot), S("unit", 1),
                 S("exclude_from_sim", Sym("no")), S("in_bom", Sym("yes")), S("on_board", Sym("yes")),
                 S("dnp", Sym("no")), S("fields_autoplaced", Sym("yes")), S("uuid", uid(self.b.name, key, "pwr")),
                 _prop("Reference", ref, x, y, hide=True),
                 _prop("Value", name, x, snap(y + (3.81 if name.startswith("GND") else -3.81)) if rot == 0 else snap(y + (-3.81 if name.startswith("GND") else 3.81))),
                 _prop("Footprint", "", x, y, hide=True),
                 _prop("Datasheet", "", x, y, hide=True),
                 _prop("Description", "", x, y, hide=True))
        for pin in sd.pins:
            node.append(S("pin", pin.number, S("uuid", uid(self.b.name, key, "pwrpin", pin.number))))
        node.append(S("instances", S("project", self.b.name,
                                     S("path", self.inst_path, S("reference", ref), S("unit", 1)))))
        self.items.append(node)

    def emit_notes(self):
        if not self.sh.notes:
            return
        W, H = self.paper_size()
        y = max(self.used_h + 10, 40)
        txt = "\n".join(self.sh.notes)
        self.items.append(S("text_box", txt, S("exclude_from_sim", Sym("no")), S("at", 20, snap(y), 0),
                            S("size", W - 40 - 140, snap(5 + 2.2 * (txt.count("\n") + 1))),
                            S("margins", 1.5, 1.5, 1.5, 1.5),
                            S("stroke", S("width", 0), S("type", Sym("dash"))),
                            S("fill", S("type", Sym("none"))),
                            _font(1.5, justify="left top"),
                            S("uuid", uid(self.b.name, self.sh.file, "notes"))))

    def document(self) -> list:
        self.layout()
        for _, parts in self.sh.blocks:
            for p in parts:
                self.emit_symbol(p)
        self.emit_notes()
        lib_symbols = S("lib_symbols", *[copy.deepcopy(LIB.get(l).node) for l in sorted(self.lib_ids)])
        return S("kicad_sch", S("version", 20250610), S("generator", "hw-testing-rack-eda"),
                 S("generator_version", "10.0"), S("uuid", self.b.sheet_uuid(self.sh)),
                 S("paper", self.sh.paper), _title_block(self.b, self.sh.title),
                 lib_symbols, *self.items, S("embedded_fonts", Sym("no")))


def _title_block(b: Board, title: str):
    tb = S("title_block", S("title", f"{b.title} — {title}"), S("rev", b.rev), S("company", b.company))
    for i, c in enumerate(b.comments[:9], start=1):
        tb.append(S("comment", i, c))
    return tb


def write_root(b: Board, outdir: Path):
    items = []
    x, y = 30.0, 50.0
    for i, sh in enumerate(b.sheets):
        w, h = 60.96, 25.4
        su = b.sheet_uuid(sh)
        items.append(S("sheet", S("at", snap(x), snap(y)), S("size", w, h),
                       S("exclude_from_sim", Sym("no")), S("in_bom", Sym("yes")), S("on_board", Sym("yes")),
                       S("dnp", Sym("no")), S("fields_autoplaced", Sym("yes")),
                       S("stroke", S("width", 0.1524), S("type", Sym("solid"))),
                       S("fill", S("color", 0, 0, 0, 0.0)), S("uuid", su),
                       _prop("Sheetname", sh.name, snap(x), snap(y - 0.7), justify="left bottom"),
                       _prop("Sheetfile", sh.file, snap(x), snap(y + h + 0.6), justify="left top"),
                       S("instances", S("project", b.name, S("path", f"/{b.root_uuid}", S("page", str(i + 2)))))))
        x += w + 25
        if x > 330:
            x = 30.0
            y += h + 25
    if b.root_notes:
        txt = "\n".join(b.root_notes)
        items.append(S("text_box", txt, S("exclude_from_sim", Sym("no")), S("at", 30, snap(y + 50), 0),
                       S("size", 360, snap(6 + 2.2 * (txt.count("\n") + 1))), S("margins", 2, 2, 2, 2),
                       S("stroke", S("width", 0), S("type", Sym("default"))), S("fill", S("type", Sym("none"))),
                       _font(1.6, justify="left top"), S("uuid", uid(b.name, "rootnotes"))))
    doc = S("kicad_sch", S("version", 20250610), S("generator", "hw-testing-rack-eda"),
            S("generator_version", "10.0"), S("uuid", b.root_uuid), S("paper", "A3"),
            _title_block(b, "Overview"), S("lib_symbols"), *items,
            S("sheet_instances", S("path", "/", S("page", "1"))), S("embedded_fonts", Sym("no")))
    (outdir / f"{b.name}.kicad_sch").write_text(dumps(doc) + "\n", encoding="utf-8")


def write_project(b: Board, outdir: Path, netclasses: list[dict] | None = None):
    """Write the generator-owned parts of <board>.kicad_pro (net classes, sheets, REV).

    Everything else — board design rules, rule severities, teardrops, … — is set by
    PcbBuilder and written back by pcbnew.SaveBoard, so an existing file is updated in place
    instead of being reset to KiCad defaults by a schematic-only run."""
    path = outdir / f"{b.name}.kicad_pro"
    classes = [
        {"name": "Default", "clearance": 0.15, "track_width": 0.25, "via_diameter": 0.6,
         "via_drill": 0.3, "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6,
         "bus_width": 12, "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)",
         "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2147483647},
        *({k: v for k, v in nc.items() if k != "_patterns"} for nc in (netclasses or [])),
    ]
    patterns = [{"netclass": nc["name"], "pattern": pat}
                for nc in (netclasses or []) for pat in nc.get("_patterns", [])]
    pro = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "board": {"design_settings": {"defaults": {"board_outline_line_width": 0.1}}}}
    pro["meta"] = {**pro.get("meta", {}), "filename": path.name, "version": 3}
    ns = pro.setdefault("net_settings", {})
    old = {nc.get("name"): nc for nc in ns.get("classes", [])}
    ns["classes"] = [{**old.get(nc["name"], {}), **nc} for nc in classes]
    ns.setdefault("meta", {"version": 4})
    ns["netclass_patterns"] = patterns
    pro["schematic"] = {**pro.get("schematic", {}), "legacy_lib_dir": "", "legacy_lib_list": []}
    pro["sheets"] = [[b.root_uuid, "Root"]] + [[b.sheet_uuid(s), s.name] for s in b.sheets]
    pro["text_variables"] = {**pro.get("text_variables", {}), "REV": b.rev}
    path.write_text(json.dumps(pro, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_lib_tables(outdir: Path):
    rel = os.path.relpath(PROJECT_LIB_DIR, outdir).replace("\\", "/")
    (outdir / "sym-lib-table").write_text(
        "(sym_lib_table\n\t(version 7)\n"
        f'\t(lib (name "bench")(type "KiCad")(uri "${{KIPRJMOD}}/{rel}/bench.kicad_sym")(options "")(descr "hw-testing-rack symbols"))\n)\n',
        encoding="utf-8")
    (outdir / "fp-lib-table").write_text(
        "(fp_lib_table\n\t(version 7)\n"
        f'\t(lib (name "bench")(type "KiCad")(uri "${{KIPRJMOD}}/{rel}/bench.pretty")(options "")(descr "hw-testing-rack footprints"))\n)\n',
        encoding="utf-8")


def generate_schematic(b: Board, outdir: Path, netclasses=None):
    outdir.mkdir(parents=True, exist_ok=True)
    problems = b.check()
    for pr in problems:
        print("WARNING:", pr)
    sheets_of = b.net_sheets()
    cross = {n for n, s in sheets_of.items() if len(s) > 1}
    for i, sh in enumerate(b.sheets):
        w = SheetWriter(b, sh, i + 2, cross)
        doc = w.document()
        (outdir / sh.file).write_text(dumps(doc) + "\n", encoding="utf-8")
    write_root(b, outdir)
    write_project(b, outdir, netclasses)
    write_lib_tables(outdir)
    return problems
