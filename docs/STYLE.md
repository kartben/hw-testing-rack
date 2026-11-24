# Writing the BitBunk documentation

These are the rules for the pages of the documentation site (`docs/index.md` and `docs/plan`, `print`,
`build`, `use`, `reference`). This file is not a page of the site.

## What the site is

A user manual. It tells someone how to build a BitBunk rack and how to use one, and it gives them the facts
they look up while doing it. That is all.

It is not the project's history, its design rationale or its status report. Those stay in the repository
(the design documents and dated notes directly under `docs/`, which the site does not publish). A page does
not say when something was decided, what it replaced, which review found what, or what has or has not been
tested. It describes the rack as it is designed and how to build and use it.

## Who reads it

An embedded developer or a maker. They know what a UART, a USB hub and a slicer are. They have never seen
this project, and they want to get something done: print the parts, assemble a bay, flash a board through
the rack, set up CI. They read on a laptop next to the printer or the bench, sometimes on a phone.

## How to write

Write plain technical English, the way a good product manual does (the Prusa and Raspberry Pi
documentation are good models). British spelling (colour, aluminium, centre).

* **Short sentences, one idea each.** If a sentence carries more than one clause after a comma, split it, or
  drop what the reader does not need.
* **Say what to do.** Address the reader as "you". Steps are imperatives: "Slide the tray in until it
  clicks."
* **Read it aloud.** If a sentence sounds odd spoken to a colleague at the bench, rewrite it.
* **Common words, normal word order.** "The drawer slides out 140 mm", not "the drawer's travel is 140 mm".
  No chains of possessives ("the drawer's front's window"), no piles of nouns.
* **Numbers where the reader needs them to act.** Several figures together go in a table or a list, never
  strung through one sentence.
* **One caveat, said once.** Do not stack sources, dates and qualifiers on a fact ("at JLCPCB's prices of
  October 2026, before VAT, by the bill's estimate"). If a caveat matters to the reader, give it plainly in a
  sentence of its own.
* **Headings say what is under them,** in the words a reader would search for: "Print the parts",
  "Measure the drag chain before you print the trays", "Power a board on and off". Sentence case. Not
  clever, not cryptic, not a question.
* **Start each page with one or two plain sentences** that say what the page helps you do or what the thing
  is. Then get on with it. No closing summary.
* **Short pages.** Most pages fit in 300 to 800 words. Cut every paragraph the reader does not need to do
  the task. Background goes, or becomes a link.

### What not to write

Each of these sentences comes from an earlier version of the site. Each was rejected by the project's
owner.

| Rejected | Why | Better |
|---|---|---|
| "A 3D-printed, tilted rack that keeps development boards in sliding drawers, switches and meters each one, and puts its USB, its console, its pins and a camera on the network." | far too many things in one sentence | "A 3D-printed rack that puts your development boards on the network." |
| "Twelve bays in four columns and three rows, 671 × 225 × 619 mm, for about €1,500 in parts at JLCPCB's prices of October 2026, before VAT." | a pile of figures and qualifiers nobody can read | a table: size, number of bays, cost |
| "A change to BitBunk is a change to a source file and to the outputs regenerated from it, committed together." | a clever-sounding definition that says nothing | "After you change `config/rack.yaml`, run `python tools/build.py` and commit the regenerated files with it." |
| "What waits, and for which bought part" (a heading) | cryptic | "Parts to measure before you print" |
| "What exists today" (a section) | project status, not user documentation | nothing |
| "Why it is built this way" (a page) | design rationale, not user documentation | nothing |

Also never: em dashes (use a colon, a comma or a full stop); exclamation marks; marketing words (seamless,
powerful, robust, effortless, easy, simply, just); filler (it is worth noting, note that, in order to,
additionally, furthermore); triplets for rhythm; balanced "not X, but Y" sentences; headings like Overview,
Introduction, Key features, Conclusion; bulleted lists where every item starts with a bold label and a colon;
emoji.

## The size of a rack is the reader's choice

BitBunk is modular. A rack is one to four rows of bays, as many columns as the power allows, and each bay
holds one board or several. A single bay can also stand on a desk without a frame. The reader decides, in
`config/rack.yaml`, and can add bays later.

So never present the 4 × 3 rack of `config/rack.yaml` as "the" rack. It is an example. When a page gives
counts (parts, screws, PCBs, filament), say which size they are for and show how to get them for another
size (the `printed-parts` and `bom-table` directives take a `:size:`).

## Facts

Every number, command, option, file name, pin and message comes from the repository: the code,
`config/rack.yaml`, `bom/rack-bom.csv`, the design files. When two sources disagree, the code and
`config/rack.yaml` win. Do not invent output, durations or troubleshooting. Leave out a command you cannot
show to be right, rather than caveat it.

## Words

BitBunk (the product). Bays are named A1 to C4 (row letter, column number); a board on a DATA board's port is
a sub-slot, B3.2. "Board" alone is the reader's development board. The rack's own boards are "the PCBs": the
bay node, the power hub, the DATA ×6, the DATA ×4 and the camera pod (with the × sign). Other terms, spelt one
way: power box, ladder, tray, drawer, board plate, peg, drag chain, row cable, `bayctl`. Explain a term the
first time a page uses it, in a few words, or link to the glossary.

## Mechanics (MyST Markdown, Sphinx)

One `#` title per page, sentence case. `##` and `###` below; no deeper.

Links. To another page: a relative Markdown link to its file, `[text](../use/power.md#limits)`. To a file or
directory of the repository that is not a page: a relative link too, `[tools/bayctl.py](../../tools/bayctl.py)`;
the build turns it into a GitHub link. To the 3D viewer or the analyzer demo: `/viewer/?bay=B3&openbay=1`,
`/analyzer/`. Link text says where the link goes; never "here" or "this page".

Images. `![alt text](../img/photo-drawer.jpg)` or a figure with a caption:

````
```{figure} ../img/web-ui-ports.png
:class: bb-screenshot
:alt: The bay page's ports card

The ports card of a DATA ×4 bay: one row per board.
```
````

`bb-screenshot` for screenshots (it adds a border), `bb-lineart` for the notice's line drawings. A caption
says what to look at, not what the image is.

Commands and code. Host commands in a `console` block with a `$ ` prompt; the node's or the hub's shell
with its `uart:~$ ` prompt; files in a block of their language with a caption:

````
```console
$ python tools/bayctl.py power B3 cycle --ms 2000
```

```{code-block} yaml
:caption: config/lab.yaml
hub: rack.local
```
````

The same action in several interfaces (the bay's page in a browser, `bayctl`, HTTP, the node's or the hub's
shell): one section per interface, each with its own heading, in that order, leaving out those that do not
exist for the action. Not a tab set: a script author must find the `curl` line with the browser's search, see
it in the page's outline and be able to paste its address into a ticket. Show the common case; every option
links to its row in Reference.

An assembly step, with the notice's drawing and what the step takes:

````
:::{build-step} 3
:drawing: a3
:detail: pin
:parts: bb=1
:hardware: m3x8=4, M3 square nut (DIN 562)=4
:click:

**Base brace** at the back: push an M3 square nut into each pocket first, then four M3 × 8 through the
brace into the nuts.
:::
````

`drawing` and `detail` are keys of `docs/img/notice/<key>.svg` (what each one shows: `tools/notice/notice.yaml`). `parts` takes the
keys of `tools/notice/notice.yaml` (`lb=2`) or free text with a quantity. `hardware` takes free text with a
quantity, named as `bom/rack-bom.csv` names the item (`M3 × 8 pan head=4, M3 square nut (DIN 562)=4`), or
one of the notice's keys that are still right: `m3x8`, `insert`, `pt23x8`, `pt26x14`, `w25`, `sp12`, `tie`,
`jumper`, `feed`, `usbc`. Never `m3x6`, `pt26x8` or `mag`: the design left them behind (the bill of materials is the truth for every screw, nut and count).
`:click:` when the part snaps in. The step's number restarts in each sequence; give `:name:` when two steps
on a page would share a number. Use a drawing only if it still shows the current design; a step without a
drawing is fine. `:image: ../img/plate-pegs.jpg` puts any other picture (a render, a screenshot) in the
drawing's place.

A tool's own help, run at build time (never paste help text by hand):

````
```{tool-help} tools/bayctl.py power
```
````

Checklists (the bench checks) are task lists, `- [ ] VRACK present on J1`: the site keeps the ticks in the browser.

Tables are Markdown pipe tables. Keep them narrow: four columns is a lot on a phone.

## Navigation: nothing to write

The menus, the breadcrumbs and the "Next" link at the foot of a page of the build's main line are drawn from
`docs/_toc.yml`. Do not write a toctree, a "Next" or "Previous" line, a "See also" block, or a list of the
section's pages. A link belongs in the sentence that needs it.

## Facts that live elsewhere: include, do not retype

A table that a tool generates or that a script checks must not be copied into a page. Three ways, in this
order of preference:

1. A directive that reads the generated data (the counts and prices of the bill of materials):

   ````
   ```{bom-table}
   :category: Fasteners, Motion
   :exclude: front display
   :columns: item, qty, source
   :total:
   ```

   ```{printed-parts}
   :size: 2x2
   :plain:
   ```
   ````

   `bom-table` reads `bom/rack-bom.csv`. Options: `category` (Electronics, Cables, Fasteners, Cameras,
   Printed parts, Motion, Analyzer, Power), `group` (for Electronics: `bay-node`, `power-hub`,
   `data-port-x6`, `data-port-x4`, `data-port-x4-base`, `camera-pod`), `match` and `exclude` (regular
   expressions on the line's text, to tell the rack's own lines from those of the example's boards, for
   instance `:exclude: DUT cable|micro-B 90|Pico 2|Dupont`), `columns` (any of `category`, `group`, `item`,
   `qty`, `unit_eur`, `ext_eur`, `source`, `mpn`, `ref`, `notes`), `total`. With `:size: 2x2` (columns ×
   rows, at most the rows of `config/rack.yaml`) and/or `:plain:` (no board in any bay) the lines are computed
   by `tools/bom.py` for that rack; the PCBs' components are then left out. `printed-parts` lists the printed
   parts with their counts and masses, for the configured rack or with the same `size` and `plain`; `match`
   and `exclude` filter on the part's name.

2. An include between two pieces of text of a file that stays in the repository:

   ````
   ```{include} ../../firmware/README.md
   :start-after: <!-- site:pin-map -->
   :end-before: <!-- /site:pin-map -->
   ```
   ````

   You may add such a pair of HTML comments (`<!-- site:NAME -->`, `<!-- /site:NAME -->`, nothing else) to a
   hand-written file that stays: `README.md`, `CONTRIBUTING.md`, the design documents and notes directly
   under `docs/`, `firmware/README.md`, `firmware/power-hub/README.md`, `bom/sourcing.md`, and your own
   pages. Check first that the pair is not already there (another writer may need the same passage). Never
   edit a generated file (`bom/README.md`, `bom/jlc-parts.md`, `bom/rack-bom.csv`): for those, use a
   heading as the boundary (`:start-after: "## Printed parts"`, `:end-before: "## Line items"`) or the
   directives above. If the included passage holds relative links or images, look at the build's warnings
   and at the rendered page: when they break, link to the passage instead of including it.

3. A tool's own help with `tool-help`, and a file's excerpt with `literalinclude` (`:lines:` or
   `:start-after:`), for `config/rack.yaml`, `config/lab.example.yaml`, `mechanical/boards/boards.yaml`.

When none of the three fits, write the table by hand and name under it the file it was read from.

## Pictures

Nothing on the site is a photograph, and a caption never lets a reader believe it is: say "render",
"simulated node" or "KiCad render", with the revision or the layout when the picture is not of the current
design (the large renders of `docs/img/` show the earlier two-row rack; `power-box.jpg` shows hub v0.5).

For a current picture of the rack, a bay or a part, take a still of the project's 3D viewer on the site's
paper colour:

```console
$ python tools/viewer_still.py docs/img/viewer/b3-open.jpg "?bay=B3&openbay=1&view=bay" --w 1400 --h 900
```

Save it under `docs/img/viewer/` with a name that says what it shows, look at it (the first framing is rarely
right: `view=custom&eye=x,y,z&look=x,y,z` places the camera, in millimetres of the rack's frame; `xray` hides
the ladders, `explode=0..1` spreads the parts, `open=0..1` pulls the drawers), and caption it "The 3D model".
Add `--no-display` (no display in the drawers' fronts: a built bay has none) to every still, and `--bare` for a bay
before its boards go in. With `--dark` the same command takes the twin for the dark theme: save it as `docs/_static/viewer-dark/<same name>.jpg`. One good still beats three poor ones; a page of steps does not need one per step.

The assembly steps are carried by the notice's line drawings (`tools/notice/`), one per step. Use a drawing
only when it shows the current design; a step whose drawing is out of date is redrawn with the notice's
pipeline, and has no picture until then. A still of the 3D model is for a part's picture in a list and for
"this is what you now have" after a stage, never with a board or a lit display the text says not to fit.

## Downloads

The published site carries, outside Sphinx: `/downloads/bitbunk-stl.zip` (every committed STL), and one
archive of fabrication files per PCB: `/downloads/power-hub-fab.zip`, `bay-node-fab.zip`, `camera-pod-fab.zip`,
`data-port-x6-fab.zip`, `data-port-x4-fab.zip` (the content of `electronics/<pcb>/fab/`). Link them as
`[the STL files in one archive](/downloads/bitbunk-stl.zip)`. Firmware images are not published there.


## Building the site

```console
$ pip install -r tools/requirements.txt -r docs/requirements.txt
$ sphinx-build -W --keep-going -b html docs docs/_build/html
```

`docs/_toc.yml` is the navigation: add a page there, under its section and caption. The menu shows each
page's title, so keep titles short. `docs/conf.py` and `docs/_ext/` hold the configuration and the
directives; `docs/_static/bitbunk.css` and `docs/_templates/` the theme. CI builds with `-W`: a broken link or
a missing drawing stops the build (`.github/workflows/pages.yml`).
