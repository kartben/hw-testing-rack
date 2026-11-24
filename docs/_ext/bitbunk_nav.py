"""The site's navigation, from one file: docs/_toc.yml.

That file lists the top bar's sections, the captions of each section's menu and its pages, in order.  From it:

* the toctrees Sphinx needs are added to the sources as they are read (no page writes one by hand);
* each page gets its section's menu, its breadcrumbs and, on the main line of the build, its "Next" link
  (docs/_templates/layout/default.html, components/breadcrumbs.html, components/navigation.html);
* an engineering note (a design document or a dated study, served as it stands) gets a line under its title
  that says what it is and where today's answer is; the dated ones are left out of the search.

A page of _toc.yml whose file does not exist yet is left out, and comes in when the file appears.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util import logging

log = logging.getLogger(__name__)


class Toc:
    def __init__(self, path: Path):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.root = data.get("root", "index")
        self.sections = data["sections"]
        self.notes = data.get("notes") or {}
        self.info: dict[str, dict] = {}         # docname -> {"section", "nav", "parent"}
        self.children: dict[str, list] = {}     # docname -> [(caption, [entries])], the toctrees it carries
        self.chain: list[str] = data.get("next") or []
        self.children[self.root] = [(None, [{"doc": s["index"], "nav": s["title"]} for s in self.sections])]
        for i, sec in enumerate(self.sections):
            self.info[sec["index"]] = {"section": i, "nav": sec.get("index_nav") or sec["title"], "parent": None}
            self.children[sec["index"]] = [(p.get("caption"), p["pages"]) for p in sec["parts"]]
            for part in sec["parts"]:
                for entry in part["pages"]:
                    self._walk(entry, i, None)

    def _walk(self, entry: dict, section: int, parent: str | None) -> None:
        self.info[entry["doc"]] = {"section": section, "nav": entry.get("nav"), "parent": parent}
        groups = []
        if entry.get("children"):
            groups.append((None, entry["children"]))
        for g in entry.get("groups") or []:
            groups.append((g.get("caption"), g["pages"]))
        if groups:
            self.children[entry["doc"]] = groups
            for _, pages in groups:
                for child in pages:
                    self._walk(child, section, entry["doc"])


def _toc(app: Sphinx) -> Toc:
    toc = getattr(app, "_bitbunk_toc", None)
    if toc is None:
        toc = app._bitbunk_toc = Toc(Path(app.srcdir) / app.config.bitbunk_toc)
    return toc


def _present(app: Sphinx, docname: str) -> bool:
    return docname in app.env.found_docs


def _present_children(app: Sphinx, docname: str) -> tuple:
    return tuple(e["doc"] for _, pages in _toc(app).children.get(docname, []) for e in pages if _present(app, e["doc"]))


def add_toctrees(app: Sphinx, docname: str, source: list[str]) -> None:
    """The hidden toctrees of a page that has children in _toc.yml."""
    toc = _toc(app)
    groups = toc.children.get(docname)
    if not groups:
        return
    app.env.note_dependency(str(Path(app.srcdir) / app.config.bitbunk_toc))
    out = []
    for caption, pages in groups:
        lines = [f"{e['nav']} </{e['doc']}>" if e.get("nav") else f"/{e['doc']}" for e in pages if _present(app, e["doc"])]
        if not lines:
            continue
        head = ["```{toctree}", ":hidden:", ":titlesonly:"] + ([f":caption: {caption}"] if caption else [])
        out.append("\n".join(head + [""] + lines + ["```"]))
    if out:
        source[0] = source[0].rstrip("\n") + "\n\n" + "\n\n".join(out) + "\n"
    if not hasattr(app.env, "bitbunk_toc_seen"):
        app.env.bitbunk_toc_seen = {}
    app.env.bitbunk_toc_seen[docname] = _present_children(app, docname)


def outdated(app: Sphinx, env, added: set, changed: set, removed: set) -> list[str]:
    """A parent is read again when one of its pages appeared or went."""
    seen = getattr(env, "bitbunk_toc_seen", {})
    return [doc for doc in _toc(app).children
            if doc in env.found_docs and doc in seen and seen[doc] != _present_children(app, doc)]


def note_metadata(app: Sphinx, doctree: nodes.document) -> None:
    """A dated note is not indexed by the search; a living design document is."""
    note = _toc(app).notes.get(app.env.docname)
    if note and not note.get("search", True):
        app.env.metadata.setdefault(app.env.docname, {})["nosearch"] = ""


def note_banner(app: Sphinx, doctree: nodes.document, docname: str) -> None:
    toc = _toc(app)
    note = toc.notes.get(docname)
    if not note:
        return
    box = nodes.container(classes=["bb-note-banner"])
    para = nodes.paragraph()
    para += nodes.inline("", note["what"], classes=["bb-note-what"])
    if note.get("standing"):
        para += nodes.Text(" " + note["standing"])
    box += para
    see = [d for d in note.get("see") or [] if _present(app, d)]
    if see:
        line = nodes.paragraph(classes=["bb-note-see"])
        line += nodes.Text(note.get("lead", "To build or use the rack: "))
        for k, doc in enumerate(see):
            if k:
                line += nodes.Text(", ")
            info = toc.info.get(doc, {})
            sec = toc.sections[info["section"]]["title"] if "section" in info else ""
            label = info.get("nav") or doc
            text = label if doc == toc.sections[info.get("section", 0)]["index"] and sec == label else f"{sec} › {label}"
            ref = nodes.reference("", text, refuri=app.builder.get_relative_uri(docname, doc), internal=True)
            line += ref
        line += nodes.Text(".")
        box += line
    for section in doctree.findall(nodes.section):
        index = 1 if section.children and isinstance(section.children[0], nodes.title) else 0
        section.insert(index, box)
        return
    doctree.insert(0, box)


def page_context(app: Sphinx, pagename: str, templatename: str, context: dict, doctree) -> None:
    toc = _toc(app)
    info = toc.info.get(pagename)
    current = info["section"] if info else None
    pathto = context["pathto"]

    def link(doc: str) -> str:
        return pathto(doc)

    context["bb_sections"] = [
        {"title": s["title"], "url": link(s["index"]), "current": i == current, "quiet": bool(s.get("quiet"))}
        for i, s in enumerate(toc.sections) if _present(app, s["index"])]
    context["bb_section"] = toc.sections[current]["title"] if current is not None else None

    if current is None:
        context["bb_nav"] = None
        context["bb_crumbs"] = []
        context["bb_next"] = None
        return

    trail = set()                                   # the page and its ancestors
    doc = pagename
    while doc:
        trail.add(doc)
        doc = toc.info[doc]["parent"]

    def item(entry: dict) -> dict | None:
        if not _present(app, entry["doc"]):
            return None
        groups = []
        for caption, pages in toc.children.get(entry["doc"], []):
            kids = [k for k in (item(e) for e in pages) if k]
            if kids:
                groups.append({"caption": caption, "pages": kids})
        return {"title": entry.get("nav") or app.env.titles[entry["doc"]].astext(), "url": link(entry["doc"]),
                "current": entry["doc"] == pagename, "open": entry["doc"] in trail, "groups": groups}

    sec = toc.sections[current]
    parts = []
    for part in sec["parts"]:
        pages = [k for k in (item(e) for e in part["pages"]) if k]
        if pages:
            parts.append({"caption": part.get("caption"), "pages": pages})
    context["bb_nav"] = {
        "title": sec["title"],
        "index": {"title": sec.get("index_nav") or sec["title"], "url": link(sec["index"]),
                  "current": pagename == sec["index"]},
        "parts": parts,
    }

    crumbs = [{"title": sec["title"], "url": link(sec["index"])}]
    parent = info["parent"]
    chain = []
    while parent:
        chain.append({"title": toc.info[parent]["nav"], "url": link(parent)})
        parent = toc.info[parent]["parent"]
    context["bb_crumbs"] = crumbs + chain[::-1]

    nxt = None
    if pagename in toc.chain:
        for doc in toc.chain[toc.chain.index(pagename) + 1:]:
            if _present(app, doc):
                nxt = {"title": app.env.titles[doc].astext(), "url": link(doc),
                       "section": toc.sections[toc.info[doc]["section"]]["title"]}
                break
    context["bb_next"] = nxt


def setup(app: Sphinx) -> dict:
    app.add_config_value("bitbunk_toc", "_toc.yml", "env")
    app.connect("source-read", add_toctrees)
    app.connect("env-get-outdated", outdated)
    app.connect("doctree-read", note_metadata)
    app.connect("doctree-resolved", note_banner)
    app.connect("html-page-context", page_context)
    return {"version": "1", "parallel_read_safe": True, "parallel_write_safe": True}
