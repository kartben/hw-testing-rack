# Printed parts: FDM printability review

**Status (2026-10-21): findings only; nothing applied — each item below is a yes/no for the user, Mechanics
implements the yeses.  Covers the covers too (cover_lid1, cover_box4, and the pockets they click into in the
drawer and the port block): sliced from the STLs of the commit that added them.**  Companion to
[printed-parts-review.md](printed-parts-review.md) (design review): this
one asks what the printer will make of each part.  Every STL of `main` (30 parts, in the orientation
`tools/build.py` writes them) went through Bambu Studio's CLI as the H2D prints them — 0.4 mm nozzle, "0.20mm
Standard @BBL H2D", Bambu PETG Basic, textured PEI plate — three ways: as designed without supports, as designed
with tree supports (auto, 30°), and auto-oriented; plus one pass with the repo's print spec (3 walls, 15 %
gyroid, elephant-foot compensation 0.15) for the times and grams.  Read from each run: the slicer's verdict
and message, time, grams, the G-code's feature breakdown (overhang wall, bridge, support interface, gap
fill, brim) clustered by layer band and 15 mm cell so each feature has a place, and the transform the
auto-orient applied.  Then the part geometry against the usual FDM rules: layer direction versus load,
overhangs past 45°, horizontal holes, bridges over pockets, insert and sliding clearances, elephant's foot,
wall widths, text depth, warping.  The slicer settings used, the per-run results, the cluster analysis and
the close-ups are in the review session's notes (not in the repo: 160 MB of G-code).

What the slicer says, in one line: **every designed orientation is the one the auto-orient picks**, gap fill
is zero everywhere (Arachne walls: no wall is a bad multiple of the line width), and **three parts get a
"floating cantilever"** — the tray, the floor plate and the cap plate, all for the same feature (the runner),
plus the DATA ×4 cradle for its base.  Everything else slices clean without supports.

## Per part (spec profile: 3 walls, 15 % gyroid; default profile: 2 walls, 15 % grid)

| Part | Spec: time | g | Default: time | g | Slicer message (no supports) | Tree supports would add | Auto-orient |
|---|---:|---:|---:|---:|---|---|---|
| Tray | 3h55 | 108 | 3h58 | 102 | floating cantilever | +12.8 g, +62 min: under the runners (z 8) and the lips (z 20–22), both walls | could not place the 165 × 210 part after rotating: no rotation needed |
| Floor plate | 2h08 | 54 | 2h12 | 51 | floating cantilever | +2.6 g, +13 min: under the runners | as designed |
| Cap plate | 2h11 | 56 | 2h15 | 53 | floating cantilever | +2.7 g, +14 min: under the runners | as designed |
| Drawer (with the cover pockets) | 2h03 | 64 | 2h15 | 59 | — | +0.2 g: the cable window's rear strip, rear right (z 0–4) | as designed |
| Sled | 1h21 | 41 | 1h30 | 37 | — | none | as designed |
| Port block (with the cover pockets) | 0h47 | 24 | 0h49 | 23 | — | none (the pockets' 6 mm ceilings print as short bridges) | as designed |
| Cover: lid (1 board) | 0h29 | 12 | 0h28 | 12 | — | none | as designed (top face down) |
| Cover: box (DATA ×4) | 1h44 | 52 | 1h42 | 51 | — | none; 25 mm of overhang wall = the tops of the five Ø3.5 LED windows | as designed (top face down) |
| Row ladder | 1h40 | 46 | 1h28 | 43 | — | +0.8 g, +5 min: **inside the bed-face grooves** (harmful; they are 5.3 mm bridges and print clean) | as designed |
| Base ladder | 1h29 | 42 | 1h18 | 41 | — | +0.9 g, same | as designed |
| Cap strip | 0h37 | 17 | 0h35 | 16 | — | +1.0 g, same | as designed |
| Row brace / base brace | 0h18 | 8 | 0h17 | 8 | — | none | as designed |
| Honeycomb plate | 3h09 | 56 | 2h59 | 49 | — | none | as designed |
| GIGA plate | 2h11 | 57 | 1h45 | 59 | — | none | as designed |
| Power box base | 1h26 | 50 | 1h40 | 45 | — | +2.1 g, +10 min: the window tops in the left wall (z 26–28, ≤ 12 mm bridges) | as designed |
| Power box lid | 0h41 | 19 | 0h38 | 19 | — | none | as designed |
| DATA ×4 cradle | 1h27 | 11 | 1h29 | 11 | floating cantilever | +2.8 g, +12 min: the base's underside (z 4–6) between its three feet | as designed |
| Camera pod / diffuser | 0h35 / 0h07 | 14 / 1 | 0h32 / 0h07 | 14 / 1 | — | none | as designed |
| Chain foot / anchor / link / bar | 0h12 / 0h13 / 0h10 / 0h01 | 1.7 / 1.7 / 1.2 / 0.1 | — | — | — | ≤ 0.1 g | as designed |
| Pegs: stop / cam base / cam / pin / bobbin | 0h13 / 0h11 / 0h04 / 0h13 / 0h16 | 0.8 / 0.7 / 0.3 / 0.7 / 1.1 | — | — | — | ≤ 0.2 g: the skins' nubs | as designed |
| Bay label (B3) | 0h03 | 1.4 | 0h03 | 1.4 | — | none | as designed |

| Assembly (spec profile, by layer) | Time | g | Plates |
|---|---:|---:|---|
| One drawer bay: tray, drawer, honeycomb plate, chain foot + anchor, label, 4 stops, 2 cam bases, 2 cams | 11h03 | 238 | 2 |
| … with a camera pod and diffuser | 11h46 | 253 | 2 |
| … B3 with the DATA ×4 cradle | 12h30 | 249 | 2 |
| … a validated one-board bay closed with the lid | +0h29 | +12 | — |
| … a validated DATA ×4 bay closed with the box | +1h44 | +52 | +1 (the box stands 72 mm) |
| One column of frame, two rows: 2 base ladders, 4 row ladders, 2 cap strips, floor and cap plates, 3 braces | 16h08 | 436 | 8 |
| Power box, base + lid | 2h07 | 69 | 1 |

The spec profile costs about 5 % more filament than the default (a third wall) for the same time.  "Bridge"
in the feature breakdown is mostly Bambu's internal bridge over sparse infill (the whole tray floor at z 2–4):
not a problem, and not counted below.

## Decisions, ranked by what they buy

Each one is a yes or a no.  "Evidence" is what the slicer or the geometry shows; "gain" is what changes
on the printed part.

**1. Runner underside at 45°, and the ladder grooves' lower edge chamfered to match — yes/no?**
Evidence: the only "floating cantilever" the slicer raises on the three big parts is the runner
(`RUNNER_OUT` 2.3 × 5 mm at z 8, flat underneath, ≈ 200 mm along each wall of the tray and both plates):
2.3 mm is five line widths in the air, and the fit in the groove is 0.15 mm a side, so any droop binds.
With supports it costs 2.6–12.8 g and 13–62 min per part and leaves scars on the sliding face.  Change:
the runner's underside slopes at 45° from its tip to the wall; the groove's lower lip takes the same
chamfer on both faces of every ladder, so the fit is unchanged.  Gain: no overhang on the tray or the
plates, no support, a clean sliding face.  Touches tray, floor plate, cap plate and the ladders in one
change.  Close-up: `runner_chamfer.png`.

**2. Print-profile settings, no geometry: elephant-foot compensation 0.15, `max_bridge_length` 30, hole
compensation 0.1 — yes/no?**
Evidence: the H2D PETG process profile ships with elephant-foot compensation 0 and XY hole compensation 0.
Bed-side holes are therefore 0.1–0.2 mm tight in the first layers (the tray's camera inserts and the
cradle's screw holes open towards the bed), and the spec pass shows the 0.15 compensation costs nothing
(same time, same grams).  `max_bridge_length` 10 is what makes the slicer ask for support under the
tray's lips between the 24 mm gussets (support interface at z 20–22 along both walls) and under the power
box's ≤ 12 mm window tops: PETG bridges 25–30 mm cleanly at this layer height.  Gain: the right hole sizes
without touching the models, and the slicer stops asking for supports the parts do not need.  Goes in
`docs/mechanical.md`'s printing notes; the print plan's profile carries it.

**3. DATA ×4 cradle: two more Ø6 feet under the base — yes/no?**
Evidence: the 4 mm base sits at z 5.3 on two Ø10 feet and one Ø6; the underside between them is bridged
over spans up to 30 mm, the slicer flags a floating cantilever and asks 2.8 g / 12 min of support.
Change: two more Ø6 feet at x 36 and 95 where the drawer floor is bare, so no span exceeds 16 mm.  Gain:
clean underside, no support, +0.3 g.  Close-up: `cradle_feet.png`.

**4. Ladder nut pockets: the retaining rib 0.1 → 0.4 × 0.4 mm — yes/no?**
Evidence: `brace_holes3` leaves a 0.1 mm rib on the pocket's wall to hold the square nut: a quarter of a
line width and half a layer, so the slicer drops it (nothing in the G-code there) and the nut falls out
when the ladder is turned to stand it.  Change: a 0.4 × 0.4 mm rib (one line, two layers) the 5.5 mm
nut (0.2 mm clearance) is pushed past.  Gain: a real detent, the nut stays through assembly.  Close-up:
`nut_rib.png`.

**5. Tray rear service slot: open it to the top edge — yes/no?**
Evidence: the 60 × 15.1 mm slot in the 2 mm rear wall stops 0.5 mm under the wall's top: a 0.5 × 2 mm
strip bridging 60 mm, two layers in the air (238 mm of overhang wall at z 18–20, x 45–60).  The slicer
prints it as a bridge; PETG drops or breaks it, and it is cosmetic either way.  Change: the slot runs to
the top edge, corners R1.5.  Gain: no bridge, nothing to support, and the leads drop in from above
instead of being threaded through.  Close-up: `rear_slot.png`.

**6. Heat-set insert holes 4.0 → 4.1 mm in PETG — yes/no?**
Evidence: `INSERT_M3` is [4.0, 5.7], the M3 × 5.7 insert's nominal hole; FDM holes come out 0.1–0.2 mm
under nominal (the inward bulge of the perimeters), and PETG splits more readily than PLA when the insert
is pushed into a tight hole on a 7.5 mm boss.  Change: 4.1 mm (or 0.1 mm of hole compensation in the
profile, item 2, which covers the drawer and tray bosses, the cradle's holes and the pod's).  Gain: the
insert seats without bulging the boss.  Skip if item 2 is a yes.

**7. Drawer finger pull: its ceiling — yes/no, optional.**
Evidence: 233 mm of overhang wall at z 18–20 (x 75–90, y 0–15): the scoop's ceiling in the front panel.
It prints (an overhang wall, not a floating cantilever) but will show as a rough underside on the most
visible face of the rack.  Change: a 45° ceiling on the scoop, or print the drawer as is and accept it.
Gain: a clean finger pull.

**8. Cover tabs: the 0.6 mm slots round each tab's foot, 0.6 → 0.8 mm — yes/no, moot if item 2 is a yes.**
Evidence: both covers print top face down, so the U-shaped slot that frees each side-hinged tab (`SLOT` 0.6)
lies in the first layers, where the squished first line (0.5 mm wide at 0.2 mm, no elephant-foot
compensation in the profile) takes 0.1–0.2 mm off each side of a gap: 0.6 becomes 0.2–0.4, and a tab
part-welded to the top at its foot is a stiffer hinge than the 1.2 % the design review sized it on.
The slicer raises nothing else on the covers: no support anywhere, the LED windows' tops are 3.5 mm arcs,
the ledges are 45°, the bumps are 45° both ways.  Change: 0.8 mm slots, or the 0.15 compensation of item 2,
which widens a bed-side gap by 0.3.  Gain: the tabs free on the first print.

**9. No change, for the record.**
- Orientation: the slicer agrees with all 30; leave `tools/build.py` as it is.
- Supports: never on the ladders or the cap strips (the trees go inside the bed-face grooves).  Nothing
  else needs them once items 1–3 are in.
- Brim: the auto brim triggers only on the cradle (tall uprights on a small footprint); leave it on
  there.  The ladders and the tray are low-risk on textured PEI at 70 °C in the enclosure.
- Clearances: the runner's 0.15 mm a side is the tight end of what FDM holds in plane (±0.1); print one
  tray and one ladder before changing it.  The drawer's 0.5 × 45° bed chamfer already covers the
  elephant's foot on its front.
- Text: `deboss` at 0.6 mm is three layers, fine; the port numbers at `cap = 5.5` have ≈ 0.8 mm strokes,
  the smallest Arachne renders as two lines — do not go smaller.
- Material: PETG stays.  PLA bridges and overhangs better (items 1 and 5 would matter less) but creeps
  under the drawer's load and softens near the PSU; the clips were sized for PETG.
- Camera pod lips: still rigid 0.8 mm bending across the layers; already decided in the design review
  (side-hinged tab), pending with Mechanics.
- Tray left guide: its gusset is being moved (it hits the node's bulk capacitor); items 1 and 5 are on the
  runner and the rear wall, not the guide, and the tray's numbers above will move by minutes and a gram.
