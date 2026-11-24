# Writing the BitBunk documentation

The rules the pages of the site (`docs/plan`, `print`, `build`, `use`, `reference`, `engineering`) were written by. This file is not a page of the site.

Read this before writing or reviewing a page. It is short on purpose.

## Who reads these pages

Someone who is about to build a BitBunk or who has one on the desk. They print parts, order boards, hold a
screwdriver, type commands. They are competent (they solder, they know what a UART is) and they are in the
middle of doing something. They want the fact, the step or the command, in the order they need it.

## The voice

The existing documents (`docs/*.md`, the READMEs) are the voice to keep: written by the person who designed
the thing, for a peer. Plain, exact, a little dry. Three samples of it:

> Two **base ladders** upright; the **floor plate** slides in from the front, into their bottom grooves.

> Each diagonal is 0.25 mm short: the X is taut once the fourth screw is in.

> Once the tray is in, no screwdriver reaches the guide lips' screws: they sit 5 mm from the side ladder and
> 2.6 mm from the drawer's wall. To convert a bay later, take its tray out first.

What these have in common, and what every new sentence must have:

* It starts with the thing. No run-up. The first sentence of a page states the central fact or what the
  reader ends up with. Never "This page describes", "In this guide", "Welcome", "Let's".
* It carries a number, a part name, a pin, a command, or a consequence. A sentence with none of these is
  probably padding: delete it.
* It says why when the why changes what the reader does ("...: they sit 5 mm from the side ladder"), and
  not otherwise.
* Steps are imperatives ("Slide the tray in until the barbs click"). Behaviour is in the present tense
  ("The node cuts VBUS after 1 s in current limit").
* The reader is "you". Avoid "we". The hardware is the subject of most sentences.
* British spelling, as in the sources: colour, aluminium, centre, neighbouring.
* Numbers with units, a space between them: 5 V, 140 mm, 20°, 4 × 3 (the × sign, not the letter x).

When an existing passage already says what the page needs, move it and keep its wording. Rewrite only to put
things in the reader's order, to fill a gap, or to cut design history out of a procedure. Do not paraphrase
good text into blander text.

## What gives a page away as machine-written (never do these)

* Em dashes. Use a colon, a comma, parentheses or a full stop.
* Openers and closers: an introduction that announces the page, a closing paragraph that sums it up, "In
  summary", "That's it", "Now you have", "Happy building", a "Next steps" section that only repeats the
  navigation, a "Conclusion".
* Headings named Overview, Introduction, Getting started, Prerequisites, Key features, Best practices,
  Tips and tricks, Advanced topics, Wrapping up, FAQ. A heading names its content: "The charger", "What a
  bay can supply", "Fit the node".
* Title Case Headings, headings with a colon and a subtitle, headings that are questions, emoji anywhere.
* The words: seamless, robust, powerful, leverage, utilize, delve, dive, comprehensive, ensure, streamline,
  cutting-edge, state-of-the-art, effortless, simply, just (as in "just run"), easy, easily, straightforward,
  intuitive, user-friendly, crucial, essential, vital, key (adjective), various, a wide range of, a variety of,
  unlock, empower, harness, elevate, foster, facilitate, journey, landscape, realm, testament, navigate (as
  metaphor), in order to, it is worth noting, note that, keep in mind, importantly, additionally, furthermore,
  moreover, overall, whether you are ... or ..., not only ... but also, feel free, exciting, enjoy.
* Triplets for rhythm ("fast, simple and reliable"), and sentences that balance two halves for effect ("It
  is not X, it is Y").
* Bulleted lists where every item starts with a bold label and a colon. Use a list when the content is a
  list, a table when it has columns, a paragraph otherwise.
* The same skeleton on every page. A page has the sections its content needs, in the order the reader
  needs them. Two pages of the same kind may share a shape when that helps lookup (two reference pages),
  never because a template said so.
* Hedging and reassurance: "may potentially", "should generally", "don't worry", "as you can see".
* Explaining what the reader knows (what USB is, what a pull request is).
* Admonitions as decoration. A `warning` is for what breaks hardware or loses data. A `note` is for a real
  aside. At most two on a page, never two in a row.
* Exclamation marks.

## Truth

* Nothing has been built yet. The frame is v0.2 and has not been printed as a whole; the five boards are
  v1.0, at the fab since 2026-11-11, none on a bench; the firmware runs on native_sim and on bench stand-ins
  (M5Stack CoreS3, XIAO ESP32-S3). Never write as if someone has used the finished rack ("in practice",
  "users find"). Say what was checked and on what.
* Put a `status` block (below) near the top of every page about something that has not been verified on the
  real boards or in a real print, and say exactly what has been done. One per page, not one per section.
* Every number, command, option, path, pin, colour, file name and message in a page comes from the
  repository: the code, the configuration, an existing document. If you cannot point at the source, leave
  it out. When two sources disagree, the code and `config/rack.yaml` win over prose, and newer prose over
  older; list the disagreement in your report.
* A command is complete and real: someone can paste it. Show output only if you can show the real one (the
  format string is in the code, or an existing document shows it); otherwise show none.
* Do not invent troubleshooting. A symptom and its cure come from the sources or from the code's own error
  paths.

## Names

BitBunk (the product). The repository is still `hw-testing-rack`; do not write its name in prose, link to
files with relative links instead. Bays are A1 ... C4 (row letter, column number); a sub-slot is B3.2.
Use the project's own terms and spell them one way: bay node, power hub, power box, DATA ×6, DATA ×4 (with
the × sign), camera pod, ladder, tray, drawer, board plate, peg, drag chain, row cable, VRACK, AUX,
`bayctl`. Explain a term the first time a page uses it, in a clause, or link to the glossary.

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

Status of what the page describes:

````
:::{status} simulated
Tested on native_sim and on a XIAO ESP32-S3 stand-in. Not run on a v1.0 bay node yet.
:::
````

Levels: `hardware` (verified on the v1.0 boards), `bench` (run on bench stand-ins), `simulated` (tests on
native_sim or host tests), `written` (code exists, no test), `designed` (designed, not built: mechanics,
boards before bring-up), `planned`.

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
`jumper`, `feed`, `usbc`. Never `m3x6`, `pt26x8` or `mag`: the design left them behind (the notice was drawn
on 2026-10-20; the bill of materials is the truth for every screw, nut and count).
`:click:` when the part snaps in. The step's number restarts in each sequence; give `:name:` when two steps
on a page would share a number. Use a drawing only if it still shows the current design; a step without a
drawing is fine. `:image: ../img/plate-pegs.jpg` puts any other picture (a render, a screenshot) in the
drawing's place.

A tool's own help, run at build time (never paste help text by hand):

````
```{tool-help} tools/bayctl.py power
```
````

Checklists (bring-up) are task lists, `- [ ] VRACK present on J1`: the site keeps the ticks in the browser.

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
With `--dark` the same command takes the twin for the dark theme: save it as `docs/_static/viewer-dark/<same name>.jpg`. One good still beats three poor ones; a page of steps does not need one per step.

The assembly steps are carried by the notice's line drawings (`tools/notice/`), one per step. Use a drawing
only when it shows the current design; a step whose drawing is out of date is redrawn with the notice's
pipeline, and has no picture until then. A still of the 3D model is for a part's picture in a list and for
"this is what you now have" after a stage, never with a board or a lit display the text says not to fit.

## Downloads

The published site carries, outside Sphinx: `/downloads/bitbunk-stl.zip` (every committed STL), and one
archive of fabrication files per PCB: `/downloads/power-hub-fab.zip`, `bay-node-fab.zip`, `camera-pod-fab.zip`,
`data-port-x6-fab.zip`, `data-port-x4-fab.zip` (the content of `electronics/<pcb>/fab/`). Link them as
`[the STL files in one archive](/downloads/bitbunk-stl.zip)`. Firmware images are not published there.

## Rules that hold on every page

* A page has one job and one reader's question, and the sections its content needs: no *Overview*, no
  *Limits*, no *Next steps*. A heading over less than about 80 words is a row or a paragraph of its neighbour.
* A status line near the top of every page about hardware or firmware (the `status` directive), linked to its
  row of `plan/status.md`, the one table behind them all. Today no page may say *hardware*.
* A procedure that no source holds, worked out from the code or the drawings, says so at the step: "worked
  out from `<file>`; nobody has done it yet".
* No invented time. A duration appears only with its source and its date; arithmetic on dated figures is
  shown, with the words "never run".
* An unknown is said beside its figure, not in a closing section.
* A fact has one home; another page links or includes it (the charger table and every limit:
  `reference/specifications.md`; every pinout: `reference/cables.md`; LEDs and buttons:
  `reference/leds-and-buttons.md`; filament: `print/printer-and-settings.md`; names and addresses:
  `use/names.md`; the status: `plan/status.md`).
* The running example is bay B3 of `config/rack.yaml`, a DATA ×4 bay: B3.1 a XIAO, B3.2 a Pico 2, B3.3 the
  analyzer; `bay-b3.local`, `rack.local`. A bare busid never appears without the DATA board named beside it.
* Words: "board" alone is the reader's development board; the rack's own are the bay node, the power hub,
  the DATA board and the camera pod, together "the PCBs". The page says *reserve*, the API and `bayctl` say
  `lease`: both once, then the page's. "Tools" are hand tools; scripts go by their names.

## Building the site

```console
$ pip install -r tools/requirements.txt -r docs/requirements.txt
$ sphinx-build -W --keep-going -b html docs docs/_build/html
```

`docs/_toc.yml` is the navigation: add a page there, under its section and caption. `docs/conf.py` and
`docs/_ext/` hold the configuration and the directives; `docs/_static/bitbunk.css` and `docs/_templates/`
the theme's layer. CI builds with `-W`: a broken link or a missing drawing stops the build
(`.github/workflows/pages.yml`).
