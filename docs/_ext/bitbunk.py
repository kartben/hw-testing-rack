"""Sphinx helpers of the BitBunk documentation.

* A link from a page to a file of the repository that is not a page of the site (``../tools/bayctl.py``,
  ``../../firmware/``) becomes a link to that file on GitHub.  The Markdown keeps its relative link, which
  also works when the file is read on GitHub.  A link to ``/viewer/...``, ``/analyzer/...`` or ``/downloads/...``
  (the parts of the published site that Sphinx does not build) is kept, relative to the page.
* ``build-step``: one step of an assembly sequence: its number, its text, the drawing of the assembly notice and
  what the step takes (parts and hardware, named as tools/notice/notice.yaml names them).
* ``status``: how far a feature or a part has been tested, said the same way on every page.
* ``tool-help``: a command-line tool's own ``--help`` text, run when the site is built.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml
from docutils import nodes
from docutils.parsers.rst import directives
from sphinx import addnodes
from sphinx.application import Sphinx
from sphinx.transforms import SphinxTransform
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------------------------------------------
# Links to the repository's files


def _github_url(config, rel: str, is_dir: bool, anchor: str) -> str:
    if rel in ("", "."):
        return config.bitbunk_repo_url                      # the repository itself
    kind = "tree" if is_dir else "blob"
    url = f"{config.bitbunk_repo_url}/{kind}/{config.bitbunk_repo_branch}/{rel}"
    return url + (f"#{anchor}" if anchor else "")


class RepoLinks(SphinxTransform):
    """Relative links that leave the documentation's sources, or name a directory, point at GitHub instead.

    MyST has already sorted a Markdown link into one of three nodes: a reference to a document (its target
    a docname, relative to the sources), a download (a file that is not a document, relative to the page),
    or an unresolved reference (anything else, as written).
    """

    default_priority = 5

    def apply(self, **kwargs) -> None:
        srcdir = Path(self.env.srcdir).resolve()
        repo = srcdir.parent
        docdir = Path(self.env.doc2path(self.env.docname)).resolve().parent
        wanted = (addnodes.pending_xref, addnodes.download_reference)
        for node in list(self.document.findall(lambda n: isinstance(n, wanted))):
            if node.get("reftype") != "myst":
                continue
            target = node.get("reftarget") or ""
            if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            extra = re.match(r"^/(%s)(/.*)?$" % "|".join(map(re.escape, self.config.bitbunk_site_extras)), target)
            if extra:
                # /viewer/?bay=B3: a part of the published site that Sphinx does not build
                up = "../" * self.env.docname.count("/")
                ref = nodes.reference("", "", refuri=up + target.lstrip("/"), classes=["bb-site-link"])
                ref += node.children
                node.replace_self(ref)
                continue
            path, _, anchor = target.partition("#")
            if isinstance(node, addnodes.pending_xref) and node.get("refdomain") == "doc":
                if path in self.env.found_docs:
                    continue                                # a page of the site
                anchor = node.get("reftargetid") or anchor
                full = next((f for f in (srcdir / (path + suffix) for suffix in self.config.source_suffix)
                             if f.exists()), None)
                if full is None:
                    continue
            else:
                full = (srcdir / path.lstrip("/")) if path.startswith("/") else (docdir / path)
            full = Path(os.path.normpath(full))
            try:
                rel = full.relative_to(repo)
            except ValueError:
                continue
            if not full.exists():
                continue                                    # MyST reports it
            inside_docs = srcdir == full or srcdir in full.parents
            if inside_docs and not full.is_dir():
                continue                                    # an image or a download of the site
            ref = nodes.reference("", "", refuri=_github_url(self.config, rel.as_posix(), full.is_dir(), anchor),
                                  classes=["bb-repo-link"])
            ref += node.children
            if not ref.children:
                ref += nodes.Text(rel.as_posix())
            node.replace_self(ref)


# ---------------------------------------------------------------------------------------------------------------
# Assembly steps


def _notice(app: Sphinx) -> dict:
    """tools/notice/notice.yaml's names: {"parts": {key: name}, "hardware": {key: {"name", "icon"}}}."""
    cached = getattr(app, "_bitbunk_notice", None)
    if cached is None:
        path = (Path(app.srcdir) / app.config.bitbunk_notice).resolve()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
        cached = {"parts": data.get("parts") or {}, "hardware": data.get("hardware") or {}}
        app._bitbunk_notice = cached
    return cached


def _kit(spec: str) -> list[tuple[str, str]]:
    """"lb=2, fp" -> [("lb", "2"), ("fp", "")]."""
    out = []
    for item in re.split(r"\s*,\s*", (spec or "").strip()):
        if item:
            key, _, qty = item.partition("=")
            out.append((key.strip(), qty.strip()))
    return out


class Step(SphinxDirective):
    """::

        :::{build-step} 3
        :drawing: a3
        :detail: pin
        :parts: bb=1
        :hardware: m3x8=4
        :click:

        **Base brace** at the back: ...
        :::

    ``drawing`` and ``detail`` are keys of the notice's drawings (docs/img/notice/<key>.svg); ``image`` takes
    any other picture instead of a drawing, by its path relative to the page; ``parts`` and
    ``hardware`` take the notice's keys (tools/notice/notice.yaml) or any text, each with a quantity.
    """

    has_content = True
    required_arguments = 1
    final_argument_whitespace = True
    option_spec = {
        "drawing": directives.unchanged,
        "image": directives.unchanged,
        "detail": directives.unchanged,
        "alt": directives.unchanged,
        "parts": directives.unchanged,
        "hardware": directives.unchanged,
        "click": directives.flag,
        "name": directives.unchanged,
    }

    def _image(self, key: str, alt: str, cls: str) -> nodes.image | None:
        rel = f"{self.config.bitbunk_notice_images}/{key}.svg"
        if not (Path(self.env.srcdir) / rel).exists():
            log.warning("build-step: no drawing %s", rel, location=self.get_location())
            return None
        return nodes.image(uri="/" + rel, alt=alt, classes=[cls, "bb-lineart"])

    def _kit_items(self, spec: str, kind: str) -> list[nodes.Node]:
        names = _notice(self.env.app)[kind]
        items = []
        for key, qty in _kit(spec):
            entry = names.get(key)
            if kind == "parts":
                label, icon = (entry, f"chip_{key}") if entry else (key, None)
            else:
                label = (entry or {}).get("label") or (entry or {}).get("name") or key
                icon = f"hw_{(entry or {}).get('icon') or key}" if entry else None
            item = nodes.inline(classes=["bb-kit-item", f"bb-kit-{kind}"])
            rel = f"{self.config.bitbunk_notice_images}/{icon}.svg" if icon else None
            if rel and (Path(self.env.srcdir) / rel).exists():
                item += nodes.image(uri="/" + rel, alt="", classes=["bb-kit-icon", "bb-lineart"])
            if qty:
                item += nodes.inline("", f"{qty} ×", classes=["bb-kit-qty"])
            item += nodes.inline("", label, classes=["bb-kit-name"])
            items.append(item)
        return items

    def run(self) -> list[nodes.Node]:
        number = self.arguments[0].strip()
        step = nodes.container(classes=["bb-step"])
        ident = nodes.make_id(self.options.get("name") or f"step-{number}")
        if ident and ident not in self.state.document.ids:
            step["ids"].append(ident)
            self.state.document.note_explicit_target(step)

        num = nodes.paragraph(classes=["bb-step-num"])
        num += nodes.Text(number)
        step += num

        body = nodes.container(classes=["bb-step-body"])
        self.state.nested_parse(self.content, self.content_offset, body)
        kit = self._kit_items(self.options.get("parts", ""), "parts") + \
            self._kit_items(self.options.get("hardware", ""), "hardware")
        if kit:
            line = nodes.paragraph(classes=["bb-kit"])
            line += kit
            body += line
        step += body

        if self.options.get("drawing") or self.options.get("image"):
            fig = nodes.container(classes=["bb-step-fig"])
            alt = self.options.get("alt", f"Step {number}")
            if self.options.get("image"):
                # any picture of the site (a render, a photo), its path as in a Markdown image
                img = nodes.image(uri=self.options["image"].strip(), alt=alt, classes=["bb-step-drawing"])
            else:
                img = self._image(self.options["drawing"].strip(), alt, "bb-step-drawing")
            if img is not None:
                fig += img
            if self.options.get("detail"):
                det = self._image(self.options["detail"].strip(), "Detail", "bb-step-detail")
                if det is not None:
                    fig += det
            if "click" in self.options:
                fig += nodes.paragraph("", "click!", classes=["bb-step-click"])
            step += fig
        return [step]


# ---------------------------------------------------------------------------------------------------------------
# Status

STATUS = {
    "hardware": "Verified on the v1.0 boards",
    "bench": "Run on bench stand-ins",
    "simulated": "Tested in simulation",
    "written": "Written, not tested yet",
    "designed": "Designed, not built yet",
    "planned": "Planned",
}


class Status(SphinxDirective):
    """::

        :::{status} simulated
        Tested on native_sim; not run on a v1.0 bay node yet.
        :::
    """

    has_content = True
    required_arguments = 1

    def run(self) -> list[nodes.Node]:
        level = self.arguments[0].strip().lower()
        if level not in STATUS:
            log.warning("status: unknown level %r (one of %s)", level, ", ".join(STATUS),
                        location=self.get_location())
            level = "written"
        box = nodes.container(classes=["bb-status", f"bb-status-{level}"])
        label = nodes.paragraph(classes=["bb-status-label"])
        label += nodes.Text(STATUS[level])
        box += label
        text = nodes.container(classes=["bb-status-text"])
        self.state.nested_parse(self.content, self.content_offset, text)
        box += text
        return [box]


# ---------------------------------------------------------------------------------------------------------------
# A tool's own --help


class ToolHelp(SphinxDirective):
    """::

        ```{tool-help} tools/bayctl.py power
        ```

    runs ``python tools/bayctl.py power --help`` from the repository's root and shows what it prints, so the
    reference cannot drift from the tool.  The first word is the script, relative to the repository.
    """

    required_arguments = 1
    final_argument_whitespace = True
    option_spec = {"flag": directives.unchanged}

    def run(self) -> list[nodes.Node]:
        repo = Path(self.env.srcdir).resolve().parent
        script, *args = self.arguments[0].split()
        flag = self.options.get("flag", "--help")
        self.env.note_dependency(str(repo / script))
        env = dict(os.environ, COLUMNS="96", LINES="50", NO_COLOR="1", PYTHONIOENCODING="utf-8")
        shown = f"python {script} {' '.join(args + [flag])}".replace("  ", " ")
        try:
            done = subprocess.run([sys.executable, str(repo / script), *args, flag], cwd=repo, env=env,
                                  capture_output=True, text=True, timeout=60)
            out = (done.stdout or done.stderr).rstrip()
            # a subcommand hidden with argparse.SUPPRESS still gets a line in the list: leave it out
            out = "\n".join(line for line in out.splitlines() if "==SUPPRESS==" not in line)
            if done.returncode != 0 or not out:
                raise RuntimeError(done.stderr.strip() or f"exit status {done.returncode}")
        except Exception as exc:  # noqa: BLE001
            log.warning("tool-help: %s failed: %s", shown, exc, location=self.get_location())
            out = f"(could not run {shown})"
        block = nodes.literal_block(out, out, language="text", classes=["bb-tool-help"])
        wrapper = nodes.container("", literal_block=True, classes=["literal-block-wrapper", "bb-tool-help-wrapper"])
        caption = nodes.caption("", f"$ {shown}")
        wrapper += caption
        wrapper += block
        return [wrapper]


def setup(app: Sphinx) -> dict:
    app.add_config_value("bitbunk_repo_url", "", "env")
    app.add_config_value("bitbunk_repo_branch", "main", "env")
    app.add_config_value("bitbunk_notice", "../tools/notice/notice.yaml", "env")
    app.add_config_value("bitbunk_notice_images", "img/notice", "env")
    app.add_config_value("bitbunk_site_extras", ["viewer", "analyzer", "downloads"], "env")
    app.add_transform(RepoLinks)
    app.add_directive("build-step", Step)
    app.add_directive("tool-help", ToolHelp)
    app.add_directive("status", Status)
    return {"version": "1", "parallel_read_safe": True, "parallel_write_safe": True}
