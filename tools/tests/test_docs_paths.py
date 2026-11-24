"""Paths to the documentation: every `docs/<...>.md` that the repository's own files name must exist.

The documentation was split into the pages of a site (docs/plan, docs/build, docs/use, ...), and code comments,
YAML, SCAD files and the notes still name the documents they rely on.  A path to a page that moved or was
removed fails here, with the file and line that names it.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# the repository's own sources: code, configuration, SCAD, the documentation
SUFFIXES = {".py", ".pyi", ".c", ".h", ".cc", ".cpp", ".js", ".mjs", ".ts", ".html", ".css", ".sh", ".cmake",
            ".conf", ".overlay", ".dts", ".dtsi", ".yaml", ".yml", ".toml", ".scad", ".md", ".txt", ".json"}
NAMES = {"Kconfig", "Kconfig.sysbuild", "Kconfig.defconfig", "CMakeLists.txt", "Makefile"}
# not ours, or not sources: git's own data, build outputs, third-party trees, other checkouts of a west workspace
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "_build", ".cache", "vendor"}
SKIP_TOP = {"zephyr", "modules", "bootloader", "mechanical/build"}

# docs/<...>.md at the start of a path: alone, after ./ or ../, never inside another directory's docs/
PATH = re.compile(r"(?<![\w.\-/])(?:\./|(?:\.\./)+)?docs/([\w.\-/]+?\.md)\b")


def own_files() -> list[Path]:
    """The files git tracks, and the new ones it does not ignore; a walk of the tree without git."""
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                             capture_output=True, check=True).stdout.decode("utf-8", "replace")
        rels = sorted({p for p in out.split("\0") if p})
    except (OSError, subprocess.CalledProcessError):
        rels = []
        for d, dirs, files in os.walk(ROOT):
            # build/ is an output everywhere but in docs/, where it is the site's Build section
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS and (x != "build" or Path(d) == ROOT / "docs")]
            rels += [os.path.relpath(os.path.join(d, f), ROOT) for f in files]
    keep = []
    for rel in rels:
        parts = Path(rel).parts
        if any(p in SKIP_DIRS for p in parts[:-1]) or any(rel.startswith(t + "/") for t in SKIP_TOP):
            continue
        if Path(rel).suffix in SUFFIXES or parts[-1] in NAMES:
            if (ROOT / rel).is_file():
                keep.append(ROOT / rel)
    return keep


def missing_paths() -> list[str]:
    found = []
    for f in own_files():
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "docs/" not in text:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for m in PATH.finditer(line):
                if not (ROOT / "docs" / m.group(1)).is_file():
                    found.append(f"{f.relative_to(ROOT)}:{n}: docs/{m.group(1)}")
    return found


class DocsPaths(unittest.TestCase):
    def test_every_named_document_exists(self):
        found = missing_paths()
        self.assertEqual(found, [], "these name a document that does not exist:\n" + "\n".join(found))

    def test_the_pattern(self):
        names = [m.group(1) for m in PATH.finditer(
            "docs/power.md (../docs/can.md) [x](../../docs/use/wifi.md#where) `docs/a b.md` docs/<pcb>.md "
            "electronics/bay-node/docs/notes.md docs/*.md")]
        self.assertEqual(names, ["power.md", "can.md", "use/wifi.md"])

    def test_it_reads_the_sources(self):
        files = {f.relative_to(ROOT).as_posix() for f in own_files()}
        for rel in ("tools/bom.py", "config/rack.yaml", "mechanical/parts/standalone.scad", "README.md"):
            self.assertIn(rel, files)


if __name__ == "__main__":
    unittest.main()
