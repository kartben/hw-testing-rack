"""Sphinx configuration of the BitBunk documentation.

    pip install -r docs/requirements.txt
    sphinx-build -W --keep-going -b html docs docs/_build/html

The repository's name and the site's address are read from the environment when GitHub Actions
builds the site (GITHUB_REPOSITORY, DOCS_BASEURL), so that renaming the repository takes no edit here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE / "_ext"))

# -- Project ----------------------------------------------------------------------------------------------------

project = "BitBunk"
author = "BitBunk contributors"
copyright = "2026, BitBunk contributors. Hardware: CERN-OHL-P-2.0. Software: Apache-2.0"
language = "en"

repo_slug = os.environ.get("GITHUB_REPOSITORY", "kartben/hw-testing-rack")
repo_owner, repo_name = repo_slug.split("/", 1)
repo_branch = os.environ.get("DOCS_BRANCH", "main")
repo_url = f"https://github.com/{repo_slug}"
html_baseurl = os.environ.get("DOCS_BASEURL", f"https://{repo_owner}.github.io/{repo_name}/").rstrip("/") + "/"

# -- General ----------------------------------------------------------------------------------------------------

extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
    "sphinxext.opengraph",
    "sphinx_sitemap",
    "bitbunk",          # docs/_ext: links to the repository, build steps, status, a tool's --help
    "bitbunk_nav",      # docs/_ext: the navigation, from docs/_toc.yml
    "bitbunk_bom",      # docs/_ext: tables read from the generated bill of materials
]

exclude_patterns = [
    "_build", "_ext", "_templates", "_toc.yml", "requirements.txt", "STYLE.md", "Thumbs.db", ".DS_Store",
    # the old addresses of documents that were split into pages: each is a few lines that say where its content
    # went, for links from outside; not a page of the site
    "architecture.md", "assembly.md", "bring-up.md", "cabling.md", "ci.md", "standalone.md",
]
# The design documents and dated notes directly under docs/ stay in the repository for contributors; the site is
# the user's manual and leaves them out.
exclude_patterns += sorted(p.name for p in HERE.glob("*.md") if p.name != "index.md")
exclude_patterns += ["dev"]          # contributor pages (docs/dev), read on GitHub
templates_path = ["_templates"]
nitpicky = False
smartquotes = False          # options such as --help appear in running text
numfig = False

myst_enable_extensions = ["attrs_block", "attrs_inline", "colon_fence", "deflist", "substitution", "tasklist"]
myst_heading_anchors = 4
myst_enable_checkboxes = True
myst_substitutions = {
    "repo_url": repo_url,
    "viewer_url": html_baseurl + "viewer/",
}
suppress_warnings = ["myst.strikethrough"]

# bitbunk extension (docs/_ext/bitbunk.py)
bitbunk_repo_url = repo_url
bitbunk_repo_branch = repo_branch
bitbunk_notice = "../tools/notice/notice.yaml"     # names of the parts and hardware a step lists
bitbunk_notice_images = "img/notice"               # the notice's drawings, <key>.svg

copybutton_prompt_text = r"\$ |uart:~\$ |bay:~\$ |hub:~\$ |>>> "
copybutton_prompt_is_regexp = True
copybutton_only_copy_prompt_lines = True
copybutton_remove_prompts = True

linkcheck_ignore = [
    r"https?://[a-z0-9.-]+\.local(:\d+)?(/.*)?",    # the rack's own mDNS names
    r"https?://localhost(:\d+)?(/.*)?",
    r"https?://192\.168\..*",
]
linkcheck_anchors_ignore_for_url = [r"https://github\.com/.*"]

# -- HTML -------------------------------------------------------------------------------------------------------

html_theme = "shibuya"
html_title = "BitBunk"
html_short_title = "BitBunk"
html_logo = "../electronics/tools/bitbunk-logo.svg"     # copied to _static/; the top bar carries it inline (below)
html_favicon = "_static/favicon.svg"
html_static_path = ["_static"]
html_css_files = ["fonts.css", "bitbunk.css"]
html_js_files = ["bitbunk.js"]
html_search_scorer = str(HERE / "_static" / "search-scorer.js")     # the engineering notes rank below the user pages
html_show_sourcelink = False
html_copy_source = False
html_show_sphinx = False
html_last_updated_fmt = None

# The top bar, the left-hand menu, the breadcrumbs and the Next links all come from docs/_toc.yml
# (docs/_ext/bitbunk_nav.py); the templates under docs/_templates draw them.
bitbunk_toc = "_toc.yml"

html_theme_options = {
    "color_mode": "auto",
    "accent_color": "orange",
    "github_url": repo_url,
    "show_ai_links": False,
    "toctree_maxdepth": 3,
    "toctree_titles_only": True,
    "toctree_includehidden": True,
    "globaltoc_expand_depth": 1,
}

import re  # noqa: E402

# The logo, put into every page's top bar: one path, filled with the text's colour.
_logo = (REPO / "electronics" / "tools" / "bitbunk-logo.svg").read_text(encoding="utf-8")
_logo = re.sub(r"<title>.*?</title>", "", _logo, flags=re.S)
_logo = re.sub(r'\s(width|height)="[^"]*mm"', "", _logo)
_logo = re.sub(r'fill="#0{3,6}"', 'fill="currentColor"', _logo).replace("<svg ", '<svg aria-hidden="true" focusable="false" ', 1)

html_context = {
    "source_type": "github",
    "source_user": repo_owner,
    "source_repo": repo_name,
    "source_version": repo_branch,
    "source_docs_path": "/docs/",
    "bitbunk_repo_url": repo_url,
    "bitbunk_viewer": "viewer/",
    "bitbunk_logo_svg": _logo.strip(),
}

# Shibuya puts these in the right-hand column.
html_sidebars = {"**": ["sidebars/localtoc.html", "sidebars/edit-this-page.html"]}

ogp_site_url = html_baseurl
ogp_site_name = "BitBunk documentation"
ogp_image = html_baseurl + "_static/og.jpg"
ogp_enable_meta_description = True
ogp_social_cards = {"enable": False}

sitemap_url_scheme = "{link}"
sitemap_excludes = ["search.html", "genindex.html"]
