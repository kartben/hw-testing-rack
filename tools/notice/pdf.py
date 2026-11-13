"""The notice as one PDF: the built pages (pages.py build), in the canvas's order, with the
drawings from mechanical/build/notice/out instead of their canvas addresses.

    python tools/notice/pdf.py [out.pdf]       # default <build>/<name>.pdf (notice.yaml › name)

The pages' markup is expanded here (the {{…}} holes, <sc-for>, <sc-if> they use), then Edge or
Chrome prints it headless, one A4 page per artboard (794 × 1123 px).  See README.md.
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from pages import ASSETS, BUILD, OUT, SPEC, _vals, build, sha

FETCHED = BUILD / "fetched"
BROWSERS = [os.environ.get("BROWSER", ""),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "chromium", "google-chrome", "msedge"]
TAG = re.compile(r"<(sc-for|sc-if)\b([^>]*)>")
HOLE = re.compile(r"\{\{([\w.$]+)\}\}")


def lookup(ctx: dict, path: str):
    v = ctx
    for k in path.split("."):
        if not isinstance(v, dict) or k not in v:
            return ""
        v = v[k]
    return v


def fill(src: str, ctx: dict) -> str:
    return HOLE.sub(lambda m: html.escape(str(lookup(ctx, m.group(1)))), src)


def expand(src: str, ctx: dict) -> str:
    """The page's markup with its loops and branches run against renderVals()' data."""
    out, i = [], 0
    while m := TAG.search(src, i):
        out.append(fill(src[i:m.start()], ctx))
        tag, depth, j = m.group(1), 1, m.end()
        pair = re.compile(rf"<{tag}\b[^>]*>|</{tag}>")
        while depth:
            n = pair.search(src, j)
            depth += -1 if n.group(0).startswith("</") else 1
            j = n.end()
        body, attrs = src[m.end():n.start()], dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(2)))
        if tag == "sc-for":
            for item in lookup(ctx, attrs["list"].strip("{}")) or []:
                out.append(expand(body, {**ctx, attrs["as"]: item}))
        elif lookup(ctx, attrs["value"].strip("{}")):
            out.append(expand(body, ctx))
        i = j
    out.append(fill(src[i:], ctx))
    return "".join(out)


def page(src: str, local: dict) -> str:
    body = re.search(r"<x-dc>(.*)</x-dc>", src, re.S).group(1)
    body = re.sub(r"<helmet>.*?</helmet>", "", body, flags=re.S)
    body = expand(body, _vals(src))
    return re.sub(r"/_blob/[0-9a-f]+", lambda m: local.get(m.group(0), m.group(0)), body)


def browser() -> str:
    for b in BROWSERS:
        if b and (Path(b).exists() or shutil.which(b)):
            return b
    sys.exit("no Edge or Chrome: set BROWSER")


def main(argv) -> int:
    dst = Path(argv[0]) if argv else BUILD / f"{SPEC['name']}.pdf"
    build(BUILD / "canvas")
    project = BUILD / "canvas" / "project"
    order = json.loads((project / "canvas.json").read_text(encoding="utf-8"))["order"]
    # Each drawing as the canvas has it: out/ when it is the file uploaded, else a copy fetched
    # from the canvas (Artifact read, path = the asset's id, into <build>/fetched), else out/ as is
    local, notes = {}, []
    for n, a in json.loads(ASSETS.read_text(encoding="utf-8")).items():
        mine, fetched = OUT / f"{n}.svg", FETCHED / f"{a['url'].rsplit('/', 1)[1]}.svg"
        if mine.exists() and sha(mine) == a["sha256"]:
            local[a["url"]] = mine.resolve().as_uri()
        elif fetched.exists():
            local[a["url"]] = fetched.resolve().as_uri()
        elif mine.exists():
            local[a["url"]] = mine.resolve().as_uri()
            notes.append(f"{n} (not uploaded yet)")
    srcs = [(project / f).read_text(encoding="utf-8") for f in order]
    used = {u for s in srcs for u in re.findall(r"/_blob/[0-9a-f]+", s)}
    names = {a["url"]: n for n, a in json.loads(ASSETS.read_text(encoding="utf-8")).items()}
    notes += [f"{names.get(u, u)} (missing: fetch it from the canvas into {FETCHED})" for u in sorted(used - set(local))]
    if notes:
        print("drawings:", ", ".join(notes))
    pages = [page(s, local) for s in srcs]
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(SPEC['name'])}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;700;800&display=swap">
<style>
@page{{size:794px 1123px;margin:0}}
html,body{{margin:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
a{{color:#111}}
.pg{{width:794px;height:1123px;overflow:hidden}}
.pg+.pg{{break-before:page}}
</style>
</head>
<body>
""" + "".join(f'<div class="pg">{p}</div>\n' for p in pages) + "</body>\n</html>\n"
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        src = Path(tmp) / "notice.html"
        src.write_text(doc, encoding="utf-8")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.unlink(missing_ok=True)
        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--allow-file-access-from-files", "--run-all-compositor-stages-before-draw",
                        "--virtual-time-budget=20000", f"--user-data-dir={Path(tmp) / 'profile'}",
                        f"--print-to-pdf={dst.resolve()}", src.resolve().as_uri()],
                       check=True, capture_output=True)
        # Edge on Windows returns before its browser process has written the file: wait for it
        size, deadline = -1, time.time() + 180
        while not (size > 0 and dst.exists() and dst.stat().st_size == size):
            if time.time() > deadline:
                sys.exit(f"no PDF from {browser()}")
            size = dst.stat().st_size if dst.exists() else -1
            time.sleep(2)
    print(f"{dst}: {len(pages)} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
