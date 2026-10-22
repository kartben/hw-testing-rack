# Autorouting: a Freerouting portfolio, and three routers on our boards

**Status (2026-10-22): measured; pipeline fixes in, no board re-routed.**  The question was whether a
faster, multi-core autorouter is worth building.  Plan agreed: first run Freerouting as a parallel portfolio
and fix the split-plane bug (step 0), then benchmark open-source routers on our own boards (step 1), then
decide.

**Verdict.**
- **Keep Freerouting, and run it as a portfolio.**
  - On every board the portfolio's best run is complete and clean: 0 unconnected, 0 copper DRC errors.
  - The pipeline's own single run is clean on 4 of 5.  On the hub one link stays open, and only 2 of 17 runs
    are clean.
  - Elsewhere the portfolio gains 0–12 % (copper length plus 2 mm a via): nothing on the DATA ×4 v2, which main
    has just tuned until its own run is clean.
  - It takes 2–5× a single run's wall time on 9 slots.  With as many slots as runs, it would take its slowest
    run, 1.5–2× a single one; a 45 min cap (`--run-timeout`) keeps the grinding ones out.
- **KiCadRoutingTools** (KRT: Python + Rust, MIT) is the strong newcomer.
  - 3–17× faster than Freerouting on our boards (46× against the DATA ×4 v2's 40 min run), deterministic, and
    it reads and writes `.kicad_pcb`.
  - It keeps our locked copper, and its pair router couples the pairs Freerouting routes apart.
  - But on the hub and the DATA ×4 v2 it leaves links open and breaks clearances: it has one clearance for
    every net, and no hole clearance.
- **Topola** routes none of our boards.  It can't read KiCad's fixed vias; past that, it panics or runs without
  end.
- **Don't write a router from scratch** (below: "Our own router?").  Most of what made routing painful was in our
  DSN and pipeline, now fixed generically: overlapping planes, cut-off islands, supply pads over the other net's
  area, a DSN that changed with every build, an optimizer that never ran the same way twice.

**Ranking** (all five boards): 1. Freerouting portfolio, 2. Freerouting single run, 3. KiCadRoutingTools,
4. Topola.

## How it was measured

- **Boards:** data-port (2 layers), camera-pod (2), bay-node (4), power-hub (4), data-port-x4-v2 (6, as on main
  after its tidy pass).  Each is placed as `design.py` places it (`tools/kicad.sh <board> --dsn`), with the
  tracks and vias it draws and locks: the USB High-Speed pairs, the supply feeds, the fan-out vias.
- **One verdict for every router:**
  - Its result goes through the import `tools/kicad.sh --ses` runs (`pcbgen.import_session`: outer pours, GND
    stitching, plane ties, pass-through vias, pair tuning, tidy), then KiCad's DRC.
  - Runs are ranked by unconnected items, then copper DRC errors (silkscreen excluded), then copper length plus
    2 mm per via.
  - `electronics/tools/route_metrics.py` adds vias, length per layer, locked tracks kept, copper on the plane
    layers, and each pair's skew and coupling.
- **Machines:**
  - The Mac: Apple M2 Pro, 12 cores, 32 GB, Java 27; it also ran the KiCad imports, in Docker.
  - zephyrbox: 16 cores, 14 GB, shared with firmware builds; 3 runs at a time at most.
- **"Before"** is the committed board.  All five are clean: 0 unconnected, 0 copper DRC.

## Step 0: `tools/route_farm.py`

```
python tools/route_farm.py bay-node                     # prepare, route the portfolio, score, report
python tools/route_farm.py bay-node --runs single       # only the pipeline's run (kicad.sh --route, FR_OPT_THREADS=1)
python tools/route_farm.py bay-node --apply             # + install the best run in electronics/bay-node
ROUTE_FARM_HOSTS=hosts.json python tools/route_farm.py data-port-x4-v2 --score-on mac
```

- **prepare:** runs `tools/kicad.sh <board> --dsn` (a new mode), then puts the committed board files back.  The
  unrouted project and its DSN go to `build/farm/base`.
- **route:** each of the portfolio's runs is a whole Freerouting job, started on any free slot of the hosts.
  - Hosts are a JSON list: ssh hops, java or Docker, slots, heap.
  - Runs are keyed by DSN and settings: one already done is skipped, one still running on a host is waited for,
    one whose process died is started again.
  - Containers are named `rf-<board>-…`; nothing else on a shared machine is touched.
- **score:** each session is imported into its own copy of the project (`build_board.py --ses --outdir`).
  KiCad's DRC and the metrics land in `runs/<run>/score.json`.  `--score-on HOST` runs the imports there, on a
  copy of the files they need.
- **report:** `build/farm/report.json` and a ranked table; `--apply` copies the best board in.
- **The portfolio** (17 runs):
  - the pipeline's own run;
  - via cost 10 / 150, rip-up cost 30 / 300, plane via cost 50;
  - fan-out off, optimizer off, neck-down off;
  - five net orders (`dsn.shuffle`: nets and components permuted with a seed);
  - three mixes of the above.

Results, on the same placement as the committed board.  Cost = copper length + 2 mm a via.  Portfolio wall
times are for 17 runs on 9 slots (6 on the Mac, 3 on zephyrbox); the single run was timed alone on the Mac.

| Board | Before (committed) | Single run | Portfolio best | Clean runs | Wall: single → portfolio |
|---|---|---|---|---|---|
| data-port | 34 vias, 173.9 mm | 0 open, 33 vias, 175.6 mm | `via150`: 30 vias, 153.7 mm (−12 %) | 16 / 17 | 14 s → 67 s |
| camera-pod | 38 vias, 231.0 mm | 0 open, 33 vias, 235.6 mm | `noneck-order2`: 32 vias, 232.6 mm (−2 %) | 17 / 17 | 4 s → 88 s |
| bay-node | 401 vias, 2269.5 mm | 0 open, 422 vias, 2226.5 mm | `ripup30`: 403 vias, 2216.8 mm (−2 %) | 15 / 17 | 90 s → 361 s |
| power-hub | 433 vias, 3536.8 mm | **1 open**, 455 vias, 3517.9 mm | `via10`: 521 vias, 3460.4 mm | **2 / 17** | 246 s → 842 s |
| DATA ×4 v2 | 810 vias, 4828.3 mm | 0 open, 800 vias, 4781.6 mm | `planevia50`: 799 vias, 4781.6 mm (0 %) | 4 / 17 (7 stopped at 45 min) | 40 min → 90 min |

- **The DATA ×4 v2 before main's tidy-up** (8442861; same portfolio, same scoring): the single run had 4 copper
  DRC errors (3 tracks necked under 0.09 mm, an isolated copper island) and 3 of 17 runs were clean; the best,
  neck-down off, was clean with 800 vias and 4772.8 mm.  Since then its own run is clean.  7 runs went past
  45 min and were stopped: autorouter passes on a board it sees almost complete, or the one-thread optimizer.
- **No setting wins twice.**  The winner is via cost 150 on the data port, rip-up cost 30 on the bay node, via
  cost 10 on the hub, neck-down off or a net order elsewhere.  That is the case for a portfolio.
- **The hub's open link**, in 15 of its runs: the narrow `buck-vin` island (VRACK, F.Cu, 2.2 mm wide) is cut in
  two by another net's track.  Freerouting doesn't treat a pour on a signal layer as an obstacle, and the island
  isn't `exclusive` in `design.py`.  Two runs miss it.
- **Cores.**  Each run uses one core (CPU s ≈ wall s); the portfolio used 9.  The slowest run takes 1.5–2× the
  pipeline's run: that sets the wall time with enough slots.
- **Not applied.**  The portfolio's boards differ from the committed ones in routing only.  Installing one
  (`--apply`) and checking it (`tools/kicad.sh <board> --check --fab`) is left to each board's owner.
- **Looks.**  Each board's signal layers were rendered before / after, side by side.  The portfolio's best reads
  like the committed board: same router, same style.  Where it saves vias, it sometimes takes a longer way on
  B.Cu.

## Freerouting 2.5.0, what the runs showed

- **The autorouter is deterministic per DSN.**  The same DSN gives the same session on the Mac (arm64, Java 27),
  on zephyrbox (x86-64, Java 25 in Docker) and on the PC: same MD5.
- **Its optimizer is not.**  It runs only on a board Freerouting thinks complete, and on several threads by
  default.  Three runs of the camera pod gave three boards; on one thread, three runs give one.
  - On the DATA ×4 v2, now complete for Freerouting, one thread takes 33 min of a 40 min run, for 1.7 mm of
    copper (`noopt`: the same 800 vias, 4783.3 mm, in 8 min).
  - So `tools/kicad.sh --route` keeps Freerouting's default (fast, not repeatable), and `FR_OPT_THREADS=1` makes
    it repeatable.  The farm always uses one thread (its runs must be repeatable) and has its optimizer-off run.
- **The DSN wasn't stable either.**
  - KiCad writes nets, footprints, images and fixed wires in an order that follows the footprints' UUIDs, which
    are new at every build.  It also numbers same-name images (`::1`) in that order.
  - So each regeneration of an unchanged `design.py` was a different routing problem.
  - `dsn.canonical()` now sorts all of it, names those images by a hash of their definition, and rounds their
    coordinates' last digit.  Two builds of one board now give one DSN (checked on data-port, camera-pod,
    power-hub).
  - One exception: on the bay node, its overlapping strips (below) go to +3V3 in one build and +5V in the
    next.  That follows KiCad's own fill, which flips the same way.
- **One core.**  The autorouter is single-threaded (CPU s ≈ wall s); the optimizer runs only on a board it sees
  complete (above).
- **Its "unrouted" count isn't KiCad's.**  It counts as open the GND pads on the outer pours, and pads reached by
  a drawn track that doesn't end on the pad's exact centre.  KiCad then finds them connected (main fixed the
  DATA ×4 v2's drawn ends in 8442861).
- **Neck-down goes under the floor.**  `automatic_neckdown` narrows tracks at crowded pads to 0.076 and
  0.063 mm on the DATA ×4 v2, whose floor is 0.09 mm: 1–8 `track_width` errors per run.  The portfolio has
  runs without it.
- **No-ops.**  `--router.autorouter.algorithm=freerouting-router-v19` logs "not supported" and uses the
  default.  `max_passes` 200 instead of 60 changes nothing: it stops after a few passes without gain.
- **Telemetry.**  `-da` (no analytics) is now on every call, `tools/kicad.sh --route` included.

## Step 0: split power planes

The brief: Freerouting takes a plane net's pads as connected through the plane, even over the other net's
area, and never routes them.  Its code (`BatchAutorouter`) and four experiments narrow this down to three
separate faults.  Each now has a generic fix in the pipeline; `PCBGEN_DSN_PLANES=kicad` keeps KiCad's outlines,
to compare.

1. **Overlapping outlines.**  KiCad writes each zone's outline, not what its fill can reach; Freerouting takes
   the whole outline as copper of the net.
   - Freerouting's own check ("overlapping conduction areas") fired on the bay node (+3V3 / +5V), the hub
     (VRACK / +3V3) and the DATA ×4 v2 (+3V3 / +5V).
   - On the bay node these are 0.3 mm strips where an outline's offset points the wrong way: x 22.0–22.3 and
     47.85–48.15 mm along y 34–44.  Both zones have the same priority, so KiCad's fill gives each strip to the
     zone with the larger UUID, which is new at each build.  The DATA ×4 v2 had the same along J1's +5V tab
     (fixed in its `design.py` on main, 8442861).  A `design.py` fix for the bay node is proposed, not made.
   - **Fix** (`pcbgen.plane_areas`, at DSN export): each plane is its outline less every other-net zone that
     wins over it on its layer (priority, then KiCad's tie-break), grown by the clearance.
   - The warning is gone from every run of the three boards.  An island poured over another net's area by
     priority (like the DATA ×4 v2's +3V3_CP island, poured after routing today) would now reach Freerouting as
     KiCad fills it; not tried.
2. **An island counts as the plane.**  An item is "connected to the plane" once its connected set holds *any*
   conduction area of its net.  So an area that nothing ties to the rest of the net makes every pad on it look
   done: the bay node's front +3V3 area, fed only by a drawn B.Cu track.
   - Test, the bay node without that feed, 2 runs per setting.  With KiCad's outlines, Freerouting lists one
     +3V3 link open and treats the front pads as connected; KiCad finds the front group cut off.
   - **Fix** (`plane_areas`): an area that no fixed via, through-hole pad or drawn track ties to the net's main
     area is left out of the DSN.
   - Freerouting then lists the front pads as open (6 links), but still can't route the 25 mm to the main area:
     KiCad finds the same group cut off.  The fault now shows in Freerouting's report; the drawn feed stays the
     way to close it.
3. **A pad over the other net's area.**  This one is not "assumed connected": Freerouting lists it open.  Its
   fan-out drops the pad's via into the wrong area, and with the long way round to its own area it often gives
   up.
   - Test, the DATA ×4 v2 without its four drawn switch feeds (the switches' IN and their 1 µF, over the +3V3
     area): 6 links open after the pipeline's own run, 5 with Freerouting's fan-out off, 1 with plane vias priced
     like signal vias.
   - Routing the split layer's nets as signals instead (`dsn.split_planes_as_signals`: the layer typed signal,
     under a wire keep-out) is far worse: 171–212 links open after 6–8 passes, against 12–14.
   - **Fix** (`pcbgen.fanout_pads`, before routing): a supply pad over another net's area gets its fan-out track
     to its own area, up to 8 mm away, with bends where a straight line doesn't fit (a 0.1 mm-grid search).  It
     is locked like the other fan-outs.
   - The same test with the fix: every supply pad connected in all three runs; the one link left open is a bus
     line (PORT1_B2 or PORT3_B2).  The eight pads get 4.8–6.2 mm feeds with 1–3 bends, the drawn feeds' job.  The
     drawn feeds could go from `design.py` (proposed, not done).
   - On the committed designs it adds three +3V3 feeds on the DATA ×4 v2 and two on the bay node (U2.2, U11.3).
     Freerouting routed those, or the import tied them, before.

`dsn.canonical()` (above) is what makes these A/B tests repeatable.

## Step 1: three routers on our boards

Each router got the same unrouted board and the same scoring.
- **KRT:** github.com/atomic14/KiCadRoutingTools v0.17.7-2-g6ab59a6 (2026-07-11).  Its Rust core was built from
  source (`cargo build --release`, rust:1 in Docker); Python 3.13.
- **Topola:** codeberg.org/mikolaj/topola d832b16 (2026-07-02), `cargo build --release -p topola-cli`.

Cells: open links / copper DRC errors · vias, copper length · wall time.  KRT shows the best of its three setups.

| Board | Freerouting single | Freerouting portfolio | KRT | Topola |
|---|---|---|---|---|
| data-port | 0 / 0 · 33 vias, 176 mm · 14 s | 0 / 0 · 30 vias, 154 mm · 67 s | 0 / 1 · 32 vias, 147 mm · 1 s | panics after 22 s |
| camera-pod | 0 / 0 · 33 vias, 236 mm · 4 s | 0 / 0 · 32 vias, 233 mm · 88 s | 0 / 0 · 39 vias, 258 mm · 1 s | no result in 5 min |
| bay-node | 0 / 0 · 422 vias, 2227 mm · 90 s | 0 / 0 · 403 vias, 2217 mm · 361 s | 0 / 2 · 468 vias, 2238 mm · 29 s | no result in 24 min |
| power-hub | 1 / 0 · 455 vias, 3518 mm · 246 s | 0 / 0 · 521 vias, 3460 mm · 842 s | 3 / 6 · 529 vias, 3359 mm · 56 s | no result in 5 min |
| DATA ×4 v2 | 0 / 0 · 800 vias, 4782 mm · 40 min | 0 / 0 · 799 vias, 4782 mm · 90 min | 2 / 22 · 793 vias, 4826 mm · 52 s | no result in 5 min |

The renders (each board's signal layers: before, the portfolio's best, KRT) are with the session's notes.

**Freerouting 2.5.0.**
- Through the portfolio it is complete and clean on every board.  It is single-core, and takes minutes on the
  4- and 6-layer boards.
- The pairs `design.py` doesn't draw come out uncoupled.  Its lines run side by side over 0–38 % of their
  length: ESP_DP/DN on the bay node, USB_CONN on the hub, the data port's CONN and LEAD.

**KiCadRoutingTools.**
- **Speed.**  The routing itself (`route.py`) takes 0.1–45 s: 0.1 s on the data port, 12 s for the DATA ×4 v2's
  246 nets.  Add 3–9 s per plane net for `route_planes.py`.  One core.
- **Deterministic.**  Two runs give the same copper, segment for segment (checked on the bay node and the
  DATA ×4 v2).
- **Fits the pipeline without a DSN.**  It reads our unrouted `.kicad_pcb` and keeps every locked track and via.
  Its board then goes through `import_session` (`--routed`) like a session.
- **The setup that worked:**
  - `route_planes.py` once per plane net, with `--skip-existing-zones`.  Two nets on one layer make it draw its
    own Voronoi zones over ours (`zones_intersect`).
  - Then `route.py` on the signal layers, with `--power-nets` widths from our netclasses and
    `--no-fix-drc-settings --no-clamp-netclasses`.
  - A `--fab-overrides` file pinning JLC's free 0.5 / 0.3 mm via.  Without it, it escalates to 0.25 / 0.15 mm
    vias near fine-pitch parts.
- **Pairs.**  With `route_diff.py` first, the router-routed pairs run side by side over 84–99 % of their length,
  at the 0.35 mm pitch asked.  Skew stays at 1.5–4.3 mm: that flow does no length matching.
- **Limits seen:**
  - One clearance for every net.  At the board's floor it breaks the USB (0.127 mm) and power (0.15 mm)
    classes; at the largest class clearance it leaves 6–13 links open.
  - No hole clearance: tracks pass 0.21 mm from the USB-C's pegs (rule 0.25).
  - Its own summary says "470/470 pads connected" where KiCad finds 7 links open.
- **Looks.**  Tidy parallel bundles on F.Cu, with B.Cu nearly empty; longer routes on the small boards.

**Topola.**
- Its own test boards route in 0.03 s.  Ours don't.
- KiCad 10's fixed vias (`(net …)(type fix)`) stop its parser.  Without `(type fix)` it parses, then runs with no
  output: 5 min on the data port and the camera pod, 24 min on the bay node.
- Without planes, pre-routes and GND, the data port panics in its navmesh after 22 s.
- Its sessions give every wire width 0.
- Work in progress, as it says; nothing to measure yet.

**Fit with our pipeline.**

| | Input | Output | Planes | Locked copper | Pairs | Cores | Deterministic |
|---|---|---|---|---|---|---|---|
| Freerouting | DSN (with our fixes) | SES | plane layers, with the faults above | kept | single-ended | 1 per run | yes, optimizer on 1 thread |
| KRT | `.kicad_pcb` | `.kicad_pcb` | stitches existing zones | kept | coupled (`route_diff`) | 1 | yes |
| Topola | DSN (KiCad's fails) | SES (0-width wires) | no | — | — | 1 | — |

## The hybrid flow, tried

KRT routes the differential pairs `design.py` doesn't draw (`route_diff.py`, on the unrouted board); those tracks
are locked, the DSN is exported again, and the Freerouting portfolio routes the rest; then the same import and
scoring.  The same runs on both sides.

| Board | Portfolio alone: best · clean runs · pairs | Hybrid: best · clean runs · pairs |
|---|---|---|
| data-port (2 pairs) | 30 vias, 153.7 mm · 16 / 17 · coupled 11 %, 38 %; skew 2.8, 0.7 mm | 31 vias, 158.6 mm (+3 %) · **17 / 17** · coupled **88 %, 84 %**; skew 1.8, 1.5 mm |
| bay-node (ESP pair) | 403 vias, 2216.8 mm · 15 / 17 · coupled 10 %, skew 1.2 mm | 406 vias, 2190.9 mm (−0.7 %) · **17 / 17** · coupled **98 %**, skew 3.6 mm |
| DATA ×4 v2 (6 pairs) | `noopt`: 0 open, 0 DRC, 800 vias, 4783 mm · CP_HUB coupled 45 % | `noopt`: 0 open, **6 DRC**, 828 vias, 4861 mm · CP_HUB coupled 74 % |
| power-hub | — | KRT can't start the USB_CONN pair from the bare board (every cell around the connector's pins blocked) |

- On the simple boards it is a win: every run clean, and the pairs actually coupled (84–98 % of their length side
  by side, against 10–38 %), for ±3 % of copper.  Skew isn't matched by that flow: adding such a pair to
  `b.pcb["match"]` would let `pcbgen.tune_pairs` even it after routing.
- On the dense DATA ×4 v2 it isn't.  At the board's 0.1 mm floor KRT drew the pairs 0.1 mm apart (their class asks
  0.127): 19 clearance errors and two stubs short of the USB-C's A6 pads, in every run.  With the class's
  clearance its pairs are clean, but the rest routes longer (+1.6 %, +28 vias) with neck-down errors; the other
  four runs were still in the one-thread optimizer at the 45 min cap.
- So: worth it where a pair is routed by the router on a roomy board (the bay node's ESP pair, the data port's
  pairs); not on the DATA ×4 v2, whose High-Speed pairs are drawn by hand anyway.

## Our own router?

Not from scratch, and no reverse engineering needed: all three are open source.  Freerouting is GPL-3: read for
ideas, don't copy.  KRT and Topola are MIT.  What each does best is now measured:

- **Freerouting:** completion on dense boards (push-and-shove, rip-up and retry) and a well-understood output.
- **KRT:** speed (a Rust A* on a grid), coupled pairs, `.kicad_pcb` in and out, plane stitching.
- **Ours (`pcbgen`):** everything around the router: planes, fan-outs and feeds, pours and stitching, the tidy
  pass, pair tuning, scoring.

The cheap way to combine them, in order:
1. **A hybrid flow** (tried above).  KRT routes the pairs (coupled); they are locked; the Freerouting portfolio
   routes the rest; `pcbgen` tidies.  It works on the simple boards, not yet on the dense one.
2. **Contribute to KRT** what our boards need: per-netclass clearance, hole clearance, KiCad's connectivity as
   the check.  Then it may finish our dense boards as well as fast.
3. **Our own core**, in Rust, only if 1 and 2 fall short.  It would mean months of work to reach Freerouting's
   completion.

## Reproduce

- `tools/route_farm.py` and `electronics/tools/dsn.py` are in the repo; the tests are `tools/tests/test_dsn.py`.
- KRT, the hybrid flow and Topola ran from scratch scripts (`bench_krt.py`, `hybrid.py`, `topola_variants.py`).
  They are kept with the renders in the session's notes, not in the repo.
