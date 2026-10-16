"""Minimal S-expression reader/writer for KiCad files.

Parsed lists are plain Python lists; atoms are `Sym` (bare words) or `str`
(quoted strings) or `float`/`int` (numbers).  The writer emits KiCad's
tab-indented layout so generated files diff nicely against files saved by
KiCad itself.
"""

from __future__ import annotations

import re


class Sym(str):
    """A bare (unquoted) atom such as `symbol`, `yes`, `input`."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Sym({str(self)})"


_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)
_NUM = re.compile(r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$")


def loads(text: str):
    """Parse one S-expression (the first top-level list) from text."""
    stack: list[list] = []
    result = None
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError(f"bad token at {pos}: {text[pos:pos + 40]!r}")
        pos = m.end()
        lpar, rpar, qstr, atom = m.groups()
        if lpar:
            stack.append([])
        elif rpar:
            done = stack.pop()
            if stack:
                stack[-1].append(done)
            else:
                result = done
                break
        elif qstr is not None:
            stack[-1].append(_unescape(qstr))
        elif atom is not None:
            if _NUM.match(atom):
                stack[-1].append(float(atom) if ("." in atom or "e" in atom.lower()) else int(atom))
            else:
                stack[-1].append(Sym(atom))
    return result


def _unescape(s: str) -> str:
    return s.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _fmt_num(v: float | int) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return str(v)
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _atom(v) -> str:
    if isinstance(v, Sym):
        return str(v)
    if isinstance(v, str):
        return f'"{_escape(v)}"'
    if isinstance(v, (int, float)):
        return _fmt_num(v)
    raise TypeError(f"cannot serialise {type(v)}: {v!r}")


def _is_simple(node) -> bool:
    return all(not isinstance(x, list) for x in node)


def dumps(node, indent: int = 0) -> str:
    """Serialise using KiCad's style: short lists inline, nested lists on new lines."""
    if not isinstance(node, list):
        return _atom(node)
    pad = "\t" * indent
    if _is_simple(node):
        return pad + "(" + " ".join(_atom(x) for x in node) + ")"
    head = []
    rest = []
    for i, x in enumerate(node):
        if isinstance(x, list):
            rest = node[i:]
            break
        head.append(x)
    out = pad + "(" + " ".join(_atom(x) for x in head)
    for x in rest:
        if isinstance(x, list):
            out += "\n" + dumps(x, indent + 1)
        else:
            out += "\n" + "\t" * (indent + 1) + _atom(x)
    out += "\n" + pad + ")"
    return out


# ---------------------------------------------------------------- helpers

def find(node, key: str):
    """First child list whose head is `key`."""
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def find_all(node, key: str):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def S(*items):
    """Build a list node; the first str item becomes a bare symbol."""
    items = list(items)
    if items and isinstance(items[0], str) and not isinstance(items[0], Sym):
        items[0] = Sym(items[0])
    return items


def yes(b: bool) -> Sym:
    return Sym("yes" if b else "no")
