"""Tables read from the generated bill of materials, so that no page retypes a count or a price.

* ``bom-table``: lines of bom/rack-bom.csv (written by tools/bom.py), chosen by category, group or text::

      ```{bom-table}
      :category: Fasteners, Motion
      :exclude: front display
      :columns: item, qty, source
      ```

  With ``:size: 2x2`` (columns × rows) and/or ``:plain:`` (no board in any bay) the lines are computed by
  tools/bom.py's own functions for that rack instead of read from the file; the PCBs' components are then
  left out (they do not depend on the size, the number of PCBs does).

* ``printed-parts``: the printed parts and their counts, for the rack of config/rack.yaml or for another size::

      ```{printed-parts}
      :size: 2x2
      :plain:
      ```

  The bays' labels (two STL files a bay) are counted on one line unless ``:labels:`` is given.
"""

from __future__ import annotations

import copy
import csv
import re
import sys
from functools import lru_cache
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

log = logging.getLogger(__name__)

COLUMNS = {
    "category": ("Category", False),
    "group": ("PCB", False),
    "item": ("Item", False),
    "qty": ("Qty", True),
    "unit_eur": ("Each, €", True),
    "ext_eur": ("Total, €", True),
    "source": ("Source", False),
    "mpn": ("Part number", False),
    "ref": ("Ref.", False),
    "notes": ("Notes", False),
}


def _repo(env) -> Path:
    return Path(env.srcdir).resolve().parent


@lru_cache(maxsize=None)
def _csv_rows(path: str) -> tuple:
    with open(path, newline="", encoding="utf-8") as f:
        return tuple(csv.DictReader(f))


@lru_cache(maxsize=None)
def _variant(repo: str, size: str, plain: bool):
    """(lines, printed parts) of tools/bom.py for another rack: `size` is "<columns>x<rows>" or "" for the
    configured one; `plain` empties every bay."""
    tools = str(Path(repo) / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import bom          # noqa: PLC0415  (tools/bom.py)
    import rackcfg      # noqa: PLC0415

    raw = copy.deepcopy(rackcfg.load().raw)
    if size:
        m = re.fullmatch(r"\s*(\d+)\s*[x×]\s*(\d+)\s*", size)
        if not m:
            raise ValueError(f"size {size!r}: write <columns>x<rows>, as in 2x2")
        cols, rows = int(m.group(1)), int(m.group(2))
        if rows > len(raw["rows"]):
            raise ValueError(f"size {size!r}: config/rack.yaml describes {len(raw['rows'])} rows")
        raw["rows"] = raw["rows"][:rows]
        for row in raw["rows"]:
            row["layout"] = [1] * cols
        ids = {f"{row['id']}{k + 1}" for row in raw["rows"] for k in range(cols)}
        raw["population"] = {k: v for k, v in (raw.get("population") or {}).items() if k in ids}
        raw["cameras"] = [c for c in raw.get("cameras") or [] if c in ids]
    if plain:
        raw["population"] = {}
    rack = rackcfg.Rack(raw)
    lines, prints = bom.printed(rack)
    lines = lines + bom.hardware(rack)
    for r in lines:
        r.setdefault("unit", "pcs")
        r.setdefault("group", "")
        r["ext_eur"] = round(float(r["qty"]) * float(r.get("unit_eur") or 0), 2)
    return tuple(lines), tuple(prints)


def _table(headers: list[tuple[str, bool]], body: list[list], classes: list[str]) -> nodes.table:
    table = nodes.table(classes=classes)
    group = nodes.tgroup(cols=len(headers))
    table += group
    for _ in headers:
        group += nodes.colspec(colwidth=1)
    head = nodes.thead()
    group += head
    row = nodes.row()
    head += row
    for title, right in headers:
        cell = nodes.entry(classes=["text-right"] if right else [])
        cell += nodes.paragraph("", title)
        row += cell
    tbody = nodes.tbody()
    group += tbody
    for line in body:
        row = nodes.row()
        tbody += row
        for (_, right), value in zip(headers, line):
            cell = nodes.entry(classes=["text-right"] if right else [])
            if isinstance(value, nodes.Node):
                para = nodes.paragraph()
                para += value
                cell += para
            else:
                cell += nodes.paragraph("", str(value))
            row += cell
    return table


def _money(value) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return ""


def _source(config, row: dict) -> nodes.Node:
    """Supplier and part number; a part number that is a URL becomes a link."""
    out = nodes.inline()
    supplier = (row.get("supplier") or "").strip()
    part = (row.get("part") or "").strip()
    m = re.match(r"^(.*?)(https?://\S+)\s*$", supplier)
    if m:
        out += nodes.reference("", m.group(1).strip() or "link", refuri=m.group(2))
    elif supplier:
        out += nodes.Text(supplier)
    if part:
        if out.children:
            out += nodes.Text(" ")
        if part.startswith("http"):
            out += nodes.reference("", "link", refuri=part)
        elif re.fullmatch(r"C\d+", part):
            out += nodes.reference("", part, refuri=f"https://www.lcsc.com/product-detail/{part}.html")
        else:
            out += nodes.Text(part)
    return out


def _list(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


class BomTable(SphinxDirective):
    option_spec = {
        "category": directives.unchanged,
        "group": directives.unchanged,
        "match": directives.unchanged,
        "exclude": directives.unchanged,
        "columns": directives.unchanged,
        "size": directives.unchanged,
        "plain": directives.flag,
        "total": directives.flag,
        "class": directives.class_option,
    }

    def run(self) -> list[nodes.Node]:
        repo = _repo(self.env)
        size, plain = self.options.get("size", "").strip(), "plain" in self.options
        self.env.note_dependency(str(repo / "bom" / "rack-bom.csv"))
        try:
            if size or plain:
                for name in ("tools/bom.py", "tools/rackcfg.py", "config/rack.yaml"):
                    self.env.note_dependency(str(repo / name))
                rows = list(_variant(str(repo), size, plain)[0])
            else:
                rows = list(_csv_rows(str(repo / "bom" / "rack-bom.csv")))
        except Exception as exc:  # noqa: BLE001
            log.warning("bom-table: %s", exc, location=self.get_location())
            return []
        cats = [c.lower() for c in _list(self.options.get("category"))]
        groups = [g.lower() for g in _list(self.options.get("group"))]
        if cats:
            rows = [r for r in rows if r["category"].lower() in cats]
        if groups:
            rows = [r for r in rows if (r.get("group") or "").lower() in groups]
        text = lambda r: " ".join(str(r.get(k) or "") for k in ("item", "notes", "supplier", "part"))  # noqa: E731
        if self.options.get("match"):
            pat = re.compile(self.options["match"], re.I)
            rows = [r for r in rows if pat.search(text(r))]
        if self.options.get("exclude"):
            pat = re.compile(self.options["exclude"], re.I)
            rows = [r for r in rows if not pat.search(text(r))]
        if not rows:
            log.warning("bom-table: no line matches", location=self.get_location())
            return []
        cols = _list(self.options.get("columns")) or ["item", "qty", "unit_eur", "ext_eur", "source"]
        bad = [c for c in cols if c not in COLUMNS]
        if bad:
            log.warning("bom-table: unknown column %s (one of %s)", ", ".join(bad), ", ".join(COLUMNS),
                        location=self.get_location())
            cols = [c for c in cols if c in COLUMNS]
        body = []
        for r in rows:
            line = []
            for c in cols:
                if c == "qty":
                    unit = r.get("unit") or "pcs"
                    line.append(f"{r['qty']}" + ("" if unit == "pcs" else f" {unit}"))
                elif c in ("unit_eur", "ext_eur"):
                    line.append(_money(r.get(c)))
                elif c == "source":
                    line.append(_source(self.config, r))
                else:
                    line.append(r.get(c) or "")
            body.append(line)
        if "total" in self.options and "ext_eur" in cols:
            total = sum(float(r.get("ext_eur") or 0) for r in rows)
            line = ["" for _ in cols]
            line[0] = nodes.strong("", "Total")
            line[cols.index("ext_eur")] = nodes.strong("", f"{total:,.2f}")
            body.append(line)
        return [_table([COLUMNS[c] for c in cols], body, ["bb-bom"] + self.options.get("class", []))]


class PrintedParts(SphinxDirective):
    option_spec = {
        "size": directives.unchanged,
        "plain": directives.flag,
        "labels": directives.flag,          # one line per bay label instead of one for them all
        "match": directives.unchanged,
        "exclude": directives.unchanged,
        "class": directives.class_option,
    }

    def run(self) -> list[nodes.Node]:
        repo = _repo(self.env)
        for name in ("tools/bom.py", "tools/rackcfg.py", "config/rack.yaml"):
            self.env.note_dependency(str(repo / name))
        try:
            prints = list(_variant(str(repo), self.options.get("size", "").strip(), "plain" in self.options)[1])
        except Exception as exc:  # noqa: BLE001
            log.warning("printed-parts: %s", exc, location=self.get_location())
            return []
        if self.options.get("match"):
            pat = re.compile(self.options["match"], re.I)
            prints = [p for p in prints if pat.search(p["part"])]
        if self.options.get("exclude"):
            pat = re.compile(self.options["exclude"], re.I)
            prints = [p for p in prints if not pat.search(p["part"])]
        url = f"{self.config.bitbunk_repo_url}/blob/{self.config.bitbunk_repo_branch}/"
        tree = f"{self.config.bitbunk_repo_url}/tree/{self.config.bitbunk_repo_branch}/mechanical/stl"
        grams_of = lambda g: "" if not g else (f"{g:.1f}" if g < 10 else f"{g:,.0f}")  # noqa: E731
        body, parts, grams = [], 0, 0.0
        labels = [p for p in prints if p["part"].startswith("bay_label_")]
        if labels and "labels" not in self.options:
            # one line for the bays' labels: a body and the inlay of its ID for each bay
            prints = [p for p in prints if p not in labels]
            bays = sorted(p["part"][len("bay_label_"):] for p in labels if not p["part"].endswith("_inlay"))
            label = nodes.inline()
            label += nodes.reference("", "", nodes.literal("", "bay_label_<bay>"), refuri=tree)
            label += nodes.Text(" and ")
            label += nodes.literal("", "bay_label_<bay>_inlay")
            label += nodes.Text(f", one pair per bay ({bays[0].upper()} to {bays[-1].upper()})" if bays else "")
            each = sum(p.get("grams_each") or 0 for p in labels) / max(len(bays), 1)
            total_g = sum(p.get("grams_total") or 0 for p in labels)
            parts += sum(p["qty"] for p in labels)
            grams += total_g
            body.append([label, sum(p["qty"] for p in labels), f"{each:.1f} a pair", grams_of(total_g)])
        for p in prints:
            name = nodes.literal("", p["part"])
            stl = repo / p["stl"]
            cell = nodes.reference("", "", name, refuri=url + p["stl"]) if stl.exists() else name
            label = nodes.inline()
            label += cell
            if p.get("optional"):
                label += nodes.Text(" (optional)")
            else:
                parts += p["qty"]
                grams += p.get("grams_total") or 0
            body.append([label, p["qty"], p["grams_each"] if p["grams_each"] is not None else "",
                         grams_of(p.get("grams_total"))])
        total = [nodes.strong("", "Total, without the optional parts"), nodes.strong("", str(parts)), "",
                 nodes.strong("", f"{grams:,.0f}")]
        body.append(total)
        headers = [("Part (its STL file)", False), ("Qty", True), ("g each", True), ("g in all", True)]
        return [_table(headers, body, ["bb-bom", "bb-printed-parts"] + self.options.get("class", []))]


def setup(app: Sphinx) -> dict:
    app.add_directive("bom-table", BomTable)
    app.add_directive("printed-parts", PrintedParts)
    return {"version": "1", "parallel_read_safe": True, "parallel_write_safe": True}
