# Stability: can the rack tip over? (study, 2026-10-25)

The user asked whether the rack is stable.  A study, no change to the parts.

## Verdict

- **Yes, it can tip forwards, and fairly easily.**  The rack is light (3.7 kg with 2 rows, 6.6 kg with
  4) on a 201 mm deep footprint.
  - A horizontal pull of **8–13 N** at the top row's drawer fronts tips it forwards: 2 rows or 4.
  - So does a **16–24 N** downward push on the front of an open top-row drawer (2 rows), e.g. plugging
    a cable into a DUT.
  - Unplugging a USB-C takes 8–20 N, and pulling a drawer against its detent a few N more.
- **Backwards and sideways are less likely.**  Backwards takes 11–24 N at the top.  Sideways takes
  33–38 N.  A pull on the charger's cable at the rear slides the rack (≈ 13 N) long before it tips it
  (≈ 150 N).
- **The fix: screw the four floor plates to the bench**, one wood screw at the front and one at the
  rear of each, through a boss's Ø4 hole.
  - No printed part changes; about €1 of screws.
  - It holds 120 N at the top of a 4-row rack and 245 N on a 2-row one.  That is 6× and 12× the 20 N
    target, against the 2× asked for.
- **Where the bench can't be drilled**, two options:
  - an MDF board, at least 500 mm deep, under the rack, screwed the same way: 2.1× (4 rows) to 3.2×
    (2 rows);
  - two furniture anti-tip straps from the top ladders to a wall.
- **Not enough on their own:** printed outrigger feet (they would have to reach 27–31 cm), a ballast
  (10–20 kg), joining racks side by side (≈ 16 N).

## Method

- **Every part where the viewer places it:** `site/assets/rack.json`, drawers closed.
  - Each printed part's volume and centroid come from its STL in assembly orientation (webscene's
    wrappers).
  - Mass: PETG at 1.27 g/cm³ × 0.55, the BOM's walls-and-infill factor (`tools/bom.py` PRINT_FILL).
    The thin parts likely print denser.  With 0.8 every force below rises about 35 %, and the verdict
    holds.
- **The rest as point masses:**

  | What | Mass |
  |---|---|
  | node | 35 g |
  | DATA port board | 6 g |
  | DATA ×4 v2 | 35–40 g |
  | hub, with its spacers | 55 g |
  | camera pod, with the Mega | 30 g |
  | chain | 10 g a bay |
  | inserts and screws | 10 g a tray, 20 g the box |
  | cables, by length | USB 30 g/m, DATA lead 12 g/m, row-cable wire 4 g/m |

  The charger's and the PC's cables lie on the bench, so they don't count.
- **DUTs, two cases:**
  - *light*: today's boards at 0.5 g/cm²;
  - *heavy*: 160 g in every drawer (4 × 40 g).
- **4 rows:** row B repeated as C and D, the cap moved up.
- **Floor contacts** (from the meshes):
  - the base ladders' bottom edges and the floor plates, y 20.0–220.6, x 0–670.6;
  - these are the tipping edges.  Nothing else touches the bench.
- **Friction** (PETG on wood or laminate): μ ≈ 0.35, an assumption.
- **Force heights:**
  - a horizontal force tips the rack at F = W · lever / h, whatever its y;
  - h is the top of the drawer's front, closed: z 295 (row B), 625 (row D);
  - a top-row DUT's plug, drawer closed, is 3 % higher (z 304 / 634).

## Mass and centre of gravity

| | 2 rows (8 bays) | 4 rows (16 bays) |
|---|---|---|
| Printed parts | 2.71 kg | 4.74 kg |
| Boards (no DUTs) | 0.48 kg | 0.93 kg |
| DUTs, light / heavy | 0.21 / 1.28 kg | 0.38 / 2.56 kg |
| Cables, chains, hardware | 0.26 kg | 0.52 kg |
| **Total, light / heavy** | **3.66 / 4.73 kg** | **6.57 / 8.75 kg** |
| CG, closed, light (x, y, z) | 314, 111, 219 | 318, 111, 382 |
| Lever to the front edge / to the rear edge | 91 / 110 mm | 91 / 110 mm |

- The power box in its base cell weighs 0.13 kg.  It moves every force below by less than 0.5 N.

## Forces that tip it

**At the top row's drawer front, horizontal.**

| Case | 2 rows: forwards | 2 rows: backwards | 4 rows: forwards | 4 rows: backwards |
|---|---|---|---|---|
| All closed, light | 11.1 N | 13.3 N | 9.3 N | 11.4 N |
| All closed, heavy | 12.9 N | 18.6 N | 11.0 N | 16.6 N |
| One top drawer open, light | 10.5 N | 14.0 N | 9.0 N | 11.7 N |
| All four top drawers open, light | 8.5 N | 15.9 N | 8.1 N | 12.6 N |
| All four top drawers open, heavy | 7.9 N | 23.6 N | 8.6 N | 18.9 N |
| It slides first at | 12.6 N (light), 16.2 N (heavy) | | 22.6 N, 30.0 N | |

- **Each row's drawer front**, closed, light, forwards / backwards:

  | Row | z | 2 rows | 4 rows |
  |---|---|---|---|
  | A | 130 | 25 / 30 N | 45 / 55 N |
  | B | 295 | 11 / 13 N | 20 / 24 N |
  | C | 460 | — | 13 / 15 N |
  | D | 625 | — | 9 / 11 N |

  A force at row A slides the rack before it tips it.
- **A downward push on an open top-row drawer's front** (y −125, 145 mm ahead of the front edge):
  - 2 rows: 21–24 N with one drawer open, 16–17 N with all four (light / heavy DUTs);
  - 4 rows: 35–45 N.
  - This is the likely accident: leaning on a drawer, or pushing a plug into a DUT on it.
- **The charger's cable pulled backwards** at the box's PD input (z 25): it tips at 154 N (2 rows),
  but it slides at 12.6 N.
- **Sideways** at the top: 38 N (2 rows), 33 N (4 rows).

## Mitigation

**The target:** 2 × 20 N = 40 N at the top row's front, in both directions and every case.  That is a
restoring moment of 11.8 N·m with 2 rows and 25 N·m with 4.  Today the worst cases give 2.2 and
5.0 N·m (all four top drawers open, no box).

| Option | 2 rows | 4 rows | Cost | Verdict |
|---|---|---|---|---|
| **Screws into the bench**: 8 × wood screw 3.5 × 16, pan head (M4 washer), one front and one rear per floor plate | 245 N | 120 N | ≈ €1 | **recommended** |
| MDF base board, 18 mm, 670 wide, screwed under the floor plates the same way: 400 / 500 / 600 mm deep | 44 / 63 / 86 N | 29 / 41 / 54 N | ≈ €10–15 | at least 500 deep, where the bench can't be drilled |
| Two anti-tip straps, from the top ladders' rear posts to the wall | ≫ 40 N | ≫ 40 N | ≈ €5–8 | when there is a wall behind it |
| Printed outrigger feet | +266 mm forwards needed | +311 mm needed | – | no: too long |
| Ballast in the base cells | 9.7 kg needed | 20.3 kg needed | – | no |
| Two racks joined side by side | 15 N | 16 N | – | no: the force at one bay stays the same |

**The screws:**
- **Where:** the bosses are on the floor plate's 30 mm grid.
  - The front screws go in the bosses at plate (x 94, y 25.15), frame y 45.
  - The rear screws go at (x 64, y 175.15), frame y 195.
  - In the power box's cell, the front screw lands 3.5 mm right of the box.
- **How it holds:** each boss has a Ø4 hole through it, so the screw's head bears on the boss.  The
  floor plate's runners sit in the base ladders' grooves, so the plates hold the whole rack down.
- **Load:**
  - at 40 N on top of a 4-row rack, each rear screw carries ≈ 29 N (14 N with 2 rows);
  - the margins above count 100 N a screw, a conservative pull-out in particle board.
- **SolidCraft check** (exact solids of the base ladders, floor plates, power box and row A's trays):
  - the screws clear the plates and the box;
  - a Ø8 screwdriver shaft has 70 mm free above each head.  That is 78 mm to row A's tray at the
    front screws and 133 mm at the rear ones.
- **When:** drive them at step 2 of [assembly.md](assembly.md), once the base brace is on.  Later,
  a stubby screwdriver reaches them under row A.
- **Use bosses without inserts.**  An M3 insert would stop the screw.
