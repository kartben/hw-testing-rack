"""The dates KiCad writes into Gerber, drill and job files, taken out so the same board gives the same bytes.

build_board.export_gerbers runs every file through undate() before zipping; tools/keep_unchanged.py compares
two zips through it, so a zip from before the change (dates inside) still matches its content.
"""

from __future__ import annotations

import json
import re

_LINES = [
    (re.compile(rb"^%TF\.CreationDate,[^%]*%\r?\n", re.M), b""),                  # Gerber X2 attribute
    (re.compile(rb"^(G04 Created by KiCad \([^)]*\)) date [^*\r\n]*\*", re.M), rb"\1*"),   # Gerber comment
    (re.compile(rb"^(; DRILL file [^\r\n]*?) date \S+", re.M), rb"\1"),             # Excellon header
    (re.compile(rb"^; #@! TF\.CreationDate,[^\r\n]*\r?\n", re.M), b""),             # Excellon X2 comment
]


def undate(name: str, data: bytes) -> bytes:
    """A fab file without its creation date (a .gbrjob loses Header.CreationDate)."""
    if name.endswith(".gbrjob"):
        try:
            job = json.loads(data)
        except ValueError:
            return data
        job.get("Header", {}).pop("CreationDate", None)
        return (json.dumps(job, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    for pat, rep in _LINES:
        data = pat.sub(rep, data)
    return data
