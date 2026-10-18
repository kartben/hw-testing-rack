#!/usr/bin/env python3
"""The notice's canvas pages, from notice.yaml and the drawings uploaded to the canvas.

    python tools/notice/pages.py plan              # drawings to upload: new, or changed since assets.json
    python tools/notice/pages.py record <file>     # their new addresses (the upload's result) -> assets.json
    python tools/notice/pages.py build [dir]       # every page -> <dir>/project/*.dc.html (default <build>/canvas)
    python tools/notice/pages.py check <dir>       # same pages as <dir>/project? (a copy read from the canvas)

The canvas (notice.yaml `canvas`) serves each drawing from its asset store at an address like
/_blob/<id>; assets.json keeps, per drawing, that address and the SHA-256 of the SVG it holds, so
`plan` only lists what changed.  Uploading and publishing go through Claude's Artifact tool, not a
command line: see README.md.  <build> is mechanical/build/notice.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
BUILD = HERE.parents[1] / "mechanical" / "build" / "notice"
OUT = BUILD / "out"
ASSETS = HERE / "assets.json"
SPEC = yaml.safe_load((HERE / "notice.yaml").read_text(encoding="utf-8"))
UPLOAD_MAX = 25                       # files per Artifact upload call


# ------------------------------------------------------------------ the drawings a notice needs
def hw_icon(k: str) -> str:
    """The icon drawing of a hardware item: hw_<key>, or hw_<icon> when several share one."""
    return "hw_" + SPEC["hardware"][k].get("icon", k)


def drawings() -> list[str]:
    need = []

    def add(n):
        if n and n not in need:
            need.append(n)
    for pg in SPEC["pages"]:
        kind = pg["kind"]
        if kind == "cover":
            add(pg["drawing"])
        elif kind == "parts":
            for k in pg["parts"]:
                add(f"card_{k}")
            for k in pg["hardware"]:
                add(hw_icon(k))
        elif kind in ("steps", "last"):
            for st in pg.get("steps", [pg.get("step")]):
                add(st["drawing"])
                add(st.get("detail"))
                for k in st.get("parts", {}):
                    add(f"chip_{k}")
                for k in list(st.get("hardware", {})) + list(st.get("cables", {})):
                    add(hw_icon(k))
            if kind == "last":
                add(pg["finished"]["drawing"])
        elif kind == "done":
            add(pg["drawing"])
    return need


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_assets() -> dict:
    return json.loads(ASSETS.read_text(encoding="utf-8")) if ASSETS.exists() else {}


def plan() -> list[Path]:
    """The drawings whose SVG is not on the canvas yet (new, or changed since it was uploaded)."""
    assets, todo, absent = load_assets(), [], []
    for n in drawings():
        svg = OUT / f"{n}.svg"
        if not svg.exists():
            absent.append(n)
        elif assets.get(n, {}).get("sha256") != sha(svg):
            todo.append(svg)
    if absent:
        print("not drawn yet (python tools/notice/run.py):", " ".join(absent))
    if not todo:
        print("the canvas has every drawing: nothing to upload")
    for i in range(0, len(todo), UPLOAD_MAX):
        print(f"upload {i // UPLOAD_MAX + 1}: asset=true, url={SPEC['canvas']}, file_paths=")
        print(json.dumps([str(p) for p in todo[i:i + UPLOAD_MAX]], indent=1))
    (BUILD / "upload.json").write_text(json.dumps([str(p) for p in todo], indent=1), encoding="utf-8")
    return todo


def record(result: Path) -> None:
    """Store the uploaded drawings' addresses.  `result` maps each uploaded file (path or name,
    with or without .svg) to its address, as the upload returned it: {"a3.svg": "/_blob/…", …}."""
    assets = load_assets()
    for f, url in json.loads(result.read_text(encoding="utf-8")).items():
        n = Path(f).name.removesuffix(".svg")
        if not re.fullmatch(r"/_blob/[0-9a-f]{32}", url):
            sys.exit(f"{f}: not an asset address: {url}")
        assets[n] = {"url": url, "sha256": sha(OUT / f"{n}.svg")}
    ASSETS.write_text(json.dumps(dict(sorted(assets.items())), indent=1) + "\n", encoding="utf-8")
    print(f"{ASSETS.name}: {len(assets)} drawings")


# ------------------------------------------------------------------ page markup
HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;700;800&display=swap">
<style>
body{{margin:0}}
a{{color:#111}}a:hover{{color:#444}}
</style>
</helmet>
"""
FONT = "background: #ffffff; color: #111111; font-family: 'Noto Sans', 'Segoe UI', sans-serif;"
TAIL = """</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":794,"height":1123}}}}'>
class Component extends DCLogic {{
renderVals() {{
return {vals};
}}
}}
</script>
</body>
</html>
"""
CHECK = ('<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.6" stroke-linecap="round" '
         'stroke-linejoin="round" role="img" aria-label="Done"><circle cx="12" cy="12" r="10"></circle><path d="M7 12.5l3.2 3.2L17 9"></path></svg>')
CHIP = """<div style="display: flex; align-items: center; gap: 6px; border: 2px solid #111111; border-radius: 10px; padding: 4px 12px 4px 4px;">
<img src="{img}" alt="{alt}" style="width: 72px; height: 54px; object-fit: contain;">
<span style="font-size: 24px; font-weight: 800;">{q}</span>
</div>
"""
HWCHIP = """<div style="display: flex; align-items: center; gap: 8px; border: 2px solid #111111; border-radius: 10px; padding: 10px 14px; height: 62px; box-sizing: border-box;">
<img src="{img}" alt="{alt}" style="width: 64px; height: 30px; object-fit: contain;">
<span style="font-size: 15px;">{t}</span>
<span style="font-size: 24px; font-weight: 800;">{q}</span>
</div>
"""
CLIC = """<sc-if value="{{s.clic}}" hint-placeholder-val="{{false}}">
<div style="position: absolute; left: 0; bottom: 8px; border: 3px solid #111111; border-radius: 999px; padding: 6px 18px; font-size: 26px; font-weight: 800; background: #ffffff;">click!</div>
</sc-if>
"""
DETAIL = """<sc-if value="{{s.hasDetail}}" hint-placeholder-val="{{false}}">
<div style="position: absolute; right: 0; bottom: 0; width: 230px; height: 230px; border-radius: 50%; border: 3px solid #111111; overflow: hidden; background: #ffffff;">
<img src="{{s.detail}}" alt="Detail" style="width: 100%; height: 100%; object-fit: cover;">
</div>
</sc-if>
"""


class Page:
    def __init__(self, assets: dict):
        self.assets = assets

    def url(self, n: str) -> str:
        if n not in self.assets:
            sys.exit(f"no address for drawing {n!r}: python tools/notice/pages.py plan, upload, record")
        return self.assets[n]["url"]

    @staticmethod
    def q(n) -> str:
        return f"{n}×"

    @staticmethod
    def js(s: str) -> str:
        return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"

    def footer(self, pg) -> str:
        return pg["footer"].format(name=SPEC["name"])

    def hw_name(self, k) -> str:
        return SPEC["hardware"][k]["name"]

    def hw_label(self, k) -> str:
        return SPEC["hardware"][k].get("label", SPEC["hardware"][k]["name"])

    # -------------------------------------------------------------- kinds
    def cover(self, pg) -> str:
        return HEAD.format(title=pg["title"]) + f"""<div style="width: 794px; height: 1123px; box-sizing: border-box; padding: 64px 64px 48px; display: flex; flex-direction: column; gap: 24px; {FONT}">
<div style="display: flex; flex-direction: column; gap: 6px;">
<h1 style="margin: 0; font-size: 112px; font-weight: 800; letter-spacing: 0.02em; line-height: 1;">{SPEC['name']}</h1>
</div>
<div style="flex: 1 1 0; min-height: 0; display: flex; align-items: center; justify-content: center;">
<img src="{self.url(pg['drawing'])}" alt="{pg['alt']}" style="max-width: 100%; max-height: 100%; object-fit: contain;">
</div>
<div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; border-top: 2px solid #111111; padding-top: 16px;">
<div style="display: flex; gap: 28px; align-items: center;">
<div style="display: flex; align-items: center; gap: 10px;">
<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="5" r="2.5"></circle><path d="M12 8v7M8 11h8M10 22l2-7 2 7"></path></svg>
<span style="font-size: 16px; font-weight: 700;">{self.q(pg['people'])}</span>
</div>
<div style="display: flex; align-items: center; gap: 10px;">
<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 3l7 7-3 3-7-7zM11 6L3 14l3 3 2-2 2 2 2-2-2-2 3-3"></path></svg>
<span style="font-size: 14px;">{pg['tools']}</span>
</div>
</div>
<span style="font-size: 13px; color: #3a3a3a;">{SPEC['credit']}</span>
</div>
</div>
""" + TAIL.format(vals="{}")

    def parts(self, pg) -> str:
        banner = "banner" in pg
        hw = pg["hardware"]
        cols = 3 if banner else 2
        cards = "".join(
            f'<div style="border: 2px solid #111111; border-radius: 12px; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center;{" gap: 8px;" if k == "jumper" else ""}">\n'
            f'<img src="{self.url(hw_icon(k))}" alt="{self.hw_name(k)}" style="width: 64px; height: 30px; object-fit: contain;">\n'
            f'<span style="font-size: 13px; color: #3a3a3a;">{self.hw_name(k)}</span>\n'
            f'<span style="font-size: 26px; font-weight: 800;">{self.q(n)}</span>\n</div>\n' for k, n in hw.items())
        top = ("""<div style="display: flex; gap: 18px; align-items: center; border: 3px solid #111111; border-radius: 12px; padding: 16px 20px;">
<svg width="64" height="48" viewBox="0 0 64 48" fill="none" stroke="#111" stroke-width="2.2" stroke-linejoin="round" aria-hidden="true"><path d="M4 44V10l10-6v34zM28 44V10l10-6v34zM52 44V10l10-6v34z"></path><path d="M14 30h14M38 30h14" stroke-dasharray="3 3"></path></svg>
<p style="margin: 0; font-size: 17px; line-height: 1.45;">""" + pg["banner"] + "</p>\n</div>\n") if banner else ""
        note = ("""<div style="display: flex; gap: 16px; align-items: center; border: 2px dashed #111111; border-radius: 12px; padding: 14px 18px;">
<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20l6-6M10 14l3-3 4 4-3 3zM15 9l3-3"></path><path d="M18 3l3 3"></path></svg>
<p style="margin: 0; font-size: 15px; line-height: 1.45;">""" + pg["note"] + "</p>\n</div>\n") if "note" in pg else ""
        vals = "{\nparts: [\n" + ",\n".join(
            f"{{ img: {self.js(self.url('card_' + k))}, name: {self.js(SPEC['parts'][k])}, q: {self.js(self.q(n))} }}"
            for k, n in pg["parts"].items()) + "\n]\n}"
        return HEAD.format(title=pg["title"]) + f"""<div style="width: 794px; height: 1123px; box-sizing: border-box; padding: 56px 56px 40px; display: flex; flex-direction: column; gap: 22px; {FONT}">
{top}<div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px;">
<sc-for list="{{{{parts}}}}" as="p" hint-placeholder-count="{len(pg['parts'])}">
<div style="border: 2px solid #111111; border-radius: 12px; padding: 12px; display: flex; flex-direction: column; gap: 6px; height: {196 if banner else 214}px; box-sizing: border-box;">
<div style="flex: 1 1 0; min-height: 0; display: flex; align-items: center; justify-content: center;">
<img src="{{{{p.img}}}}" alt="{{{{p.name}}}}" style="max-width: 100%; max-height: 100%; object-fit: contain;">
</div>
<div style="display: flex; justify-content: space-between; align-items: baseline; gap: 8px;">
<span style="font-size: 13px; color: #3a3a3a;">{{{{p.name}}}}</span>
<span style="font-size: 26px; font-weight: 800;">{{{{p.q}}}}</span>
</div>
</div>
</sc-for>
</div>
<div style="display: grid; grid-template-columns: repeat({cols}, minmax(0, 1fr)); gap: 14px;">
{cards}</div>
{note}<div style="margin-top: auto; display: flex; justify-content: space-between; font-size: 13px; color: #3a3a3a;"><span>{self.footer(pg)}</span><span>{pg['page']}</span></div>
</div>
""" + TAIL.format(vals=vals)

    def step_vals(self, st, with_hw, with_cables, with_detail) -> str:
        parts = ", ".join(f"{{ img: {self.js(self.url('chip_' + k))}, alt: {self.js(SPEC['parts'][k])}, q: {self.js(self.q(n))} }}"
                          for k, n in st.get("parts", {}).items())
        out = f"{{ n: {self.js(st['n'])}, img: {self.js(self.url(st['drawing']))}, alt: {self.js(st['alt'])},\n  parts: [{parts}]"
        for key, on in (("cables", with_cables), ("hardware", with_hw)):
            if on:
                items = ", ".join(f"{{ t: {self.js(self.hw_label(k))}, q: {self.js(self.q(n))}, img: {self.js(self.url(hw_icon(k)))} }}"
                                  for k, n in st.get(key, {}).items())
                out += f", {'hw' if key == 'hardware' else 'cables'}: [{items}]"
        out += f", clic: {'true' if st.get('clic') else 'false'}"
        if with_detail:
            out += f", hasDetail: {'true' if st.get('detail') else 'false'}, detail: {self.js(self.url(st['detail']) if st.get('detail') else '')}"
        return out + " }"

    def steps(self, pg) -> str:
        sts = pg["steps"]
        hw = any(s.get("hardware") is not None for s in sts)
        cables = any(s.get("cables") for s in sts)
        detail = any(s.get("detail") for s in sts)
        loop = lambda name, var, key: (f'<sc-for list="{{{{s.{name}}}}}" as="{var}" hint-placeholder-count="0">\n'
                                       + HWCHIP.format(img=f"{{{{{var}.img}}}}", alt="", t=f"{{{{{var}.t}}}}", q=f"{{{{{var}.q}}}}")
                                       + "</sc-for>\n")
        vals = (f"{{\npage: {self.js(pg['page'])},\nsteps: [\n"
                + ",\n".join(self.step_vals(s, hw, cables, detail) for s in sts) + "\n]\n}")
        return HEAD.format(title=pg["title"]) + f"""<div style="width: 794px; height: 1123px; box-sizing: border-box; padding: 48px 56px 40px; display: flex; flex-direction: column; gap: 18px; {FONT}">
<sc-for list="{{{{steps}}}}" as="s" hint-placeholder-count="{len(sts)}">
<section style="flex: 1 1 0; min-height: 0; display: flex; flex-direction: column; gap: 6px;">
<div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;">
<div style="font-size: 72px; font-weight: 800; line-height: 1;">{{{{s.n}}}}</div>
<div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end;{" align-items: center;" if hw or cables else ""}">
<sc-for list="{{{{s.parts}}}}" as="p" hint-placeholder-count="1">
""" + CHIP.format(img="{{p.img}}", alt="{{p.alt}}", q="{{p.q}}") + "</sc-for>\n" \
            + (loop("cables", "c", "cables") if cables else "") + (loop("hw", "h", "hw") if hw else "") + """</div>
</div>
<div style="flex: 1 1 0; min-height: 0; position: relative;">
<img src="{{s.img}}" alt="{{s.alt}}" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain;">
""" + CLIC + (DETAIL if detail else "") + f"""</div>
</section>
</sc-for>
<div style="display: flex; justify-content: space-between; font-size: 13px; color: #3a3a3a;"><span>{self.footer(pg)}</span><span>{{{{page}}}}</span></div>
</div>
""" + TAIL.format(vals=vals)

    def last(self, pg) -> str:
        st, fin = pg["step"], pg["finished"]
        chips = "".join(CHIP.format(img=self.url("chip_" + k), alt=SPEC["parts"][k], q=self.q(n)) for k, n in st.get("parts", {}).items()) \
            + "".join(HWCHIP.format(img=self.url(hw_icon(k)), alt=self.hw_label(k), t=self.hw_label(k), q=self.q(n))
                      for k, n in st.get("hardware", {}).items())
        return HEAD.format(title=pg["title"]) + f"""<div style="width: 794px; height: 1123px; box-sizing: border-box; padding: 48px 56px 40px; display: flex; flex-direction: column; gap: 18px; {FONT}">
<section style="flex: 1 1 0; min-height: 0; display: flex; flex-direction: column; gap: 6px;">
<div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;">
<div style="font-size: 72px; font-weight: 800; line-height: 1;">{st['n']}</div>
<div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; align-items: center;">
{chips}</div>
</div>
<div style="flex: 1 1 0; min-height: 0; position: relative;">
<img src="{self.url(st['drawing'])}" alt="{st['alt']}" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain;">
</div>
</section>
<div style="height: 300px; display: flex; gap: 24px; align-items: center; border-top: 2px solid #111111; padding-top: 18px;">
<div style="flex: 1 1 0; height: 100%; display: flex; align-items: center; justify-content: center;">
<img src="{self.url(fin['drawing'])}" alt="{fin['alt']}" style="max-width: 100%; max-height: 100%; object-fit: contain;">
</div>
{CHECK.format(s=96)}
</div>
<div style="display: flex; justify-content: space-between; font-size: 13px; color: #3a3a3a;"><span>{self.footer(pg)}</span><span>{pg['page']}</span></div>
</div>
""" + TAIL.format(vals="{}")

    def done(self, pg) -> str:
        return HEAD.format(title=pg["title"]) + f"""<div style="width: 794px; height: 1123px; box-sizing: border-box; padding: 56px 56px 40px; display: flex; flex-direction: column; gap: 24px; {FONT}">
<div style="flex: 1 1 0; min-height: 0; display: flex; align-items: center; justify-content: center;">
<img src="{self.url(pg['drawing'])}" alt="{pg['alt']}" style="max-width: 100%; max-height: 100%; object-fit: contain;">
</div>
<div style="display: flex; align-items: center; gap: 20px; border-top: 2px solid #111111; padding-top: 18px;">
{CHECK.format(s=72)}
<p style="margin: 0; font-size: 17px; line-height: 1.45;">{pg['note']}</p>
</div>
<div style="display: flex; justify-content: space-between; font-size: 13px; color: #3a3a3a;"><span>{self.footer(pg)}</span><span>{pg['page']}</span></div>
</div>
""" + TAIL.format(vals="{}")


def index() -> dict:
    """The canvas's project/canvas.json: one row of A4 artboards per title note, in page order."""
    ix, rows = SPEC["index"], list(SPEC["index"]["rows"])
    W, H, GAP, ROW = 794, 1123, 80, 1123 + 420
    boards, count = {}, {r: 0 for r in rows}
    for pg in SPEC["pages"]:
        r = pg["board"]["row"]
        boards[pg["file"]] = {"x": count[r] * (W + GAP), "y": rows.index(r) * ROW, "w": W, "h": H,
                              "title": pg["board"]["title"], "print": "flow", "paper": "a4"}
        count[r] += 1
    notes = {r: {"x": 0, "y": rows.index(r) * ROW - 300, "text": t, "kind": "title1", "maxW": count[r] * (W + GAP) - GAP}
             for r, t in ix["rows"].items()}
    return {"v": 3, "createdOnFiles": ix["createdOnFiles"], "title": ix["title"], "launch": {"view": "canvas"},
            "pages": [], "boards": boards, "order": [pg["file"] for pg in SPEC["pages"]], "notes": notes, "designSystems": []}


def build(dst: Path) -> list[Path]:
    page, out = Page(load_assets()), []
    (dst / "project").mkdir(parents=True, exist_ok=True)
    for pg in SPEC["pages"]:
        p = dst / "project" / pg["file"]
        p.write_bytes(getattr(page, pg["kind"])(pg).encode("utf-8"))
        out.append(p)
    (dst / "project" / "canvas.json").write_text(json.dumps(index(), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)} pages and canvas.json in {dst / 'project'}")
    return out


# ------------------------------------------------------------------ check against the canvas
def _vals(src: str):
    """renderVals()'s object literal (single-quoted strings, bare keys) as data."""
    body = re.search(r"renderVals\(\) \{\s*return (.*?);\s*\}\s*\}\s*</script>", src, re.S).group(1)
    body = re.sub(r"'((?:[^'\\]|\\.)*)'", lambda m: json.dumps(m.group(1).replace("\\'", "'")), body)
    body = re.sub(r"([{,]\s*)([A-Za-z_$][\w$]*)\s*:", r'\1"\2":', body)
    return json.loads(body)


def check(ref: Path) -> int:
    """Compare the built pages with the canvas's (a copy saved under ref/project): markup outside
    the data identical, data equal.  Returns the number of pages that differ."""
    bad = 0
    for pg in SPEC["pages"]:
        a = (BUILD / "canvas" / "project" / pg["file"]).read_text(encoding="utf-8")
        b = (ref / "project" / pg["file"]).read_text(encoding="utf-8")
        cut = lambda s: s.split('<script type="text/x-dc"')[0]
        same_markup, same_data = cut(a) == cut(b), _vals(a) == _vals(b)
        if not (same_markup and same_data):
            bad += 1
            import difflib
            print(f"{pg['file']}: markup {'same' if same_markup else 'DIFFERS'}, data {'same' if same_data else 'DIFFERS'}")
            if not same_markup:
                print("".join(list(difflib.unified_diff(cut(b).splitlines(True), cut(a).splitlines(True), "canvas", "built", n=1))[:40]))
            if not same_data:
                print(" canvas:", json.dumps(_vals(b), ensure_ascii=False)[:600], "\n built: ", json.dumps(_vals(a), ensure_ascii=False)[:600])
    print(f"{len(SPEC['pages']) - bad}/{len(SPEC['pages'])} pages as on the canvas")
    return bad


def main(argv) -> int:
    cmd = argv[0] if argv else "plan"
    if cmd == "plan":
        plan()
    elif cmd == "record":
        record(Path(argv[1]))
    elif cmd == "build":
        build(Path(argv[1]) if len(argv) > 1 else BUILD / "canvas")
    elif cmd == "check":
        return 1 if check(Path(argv[1])) else 0
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
