# Printer, filament, settings

Every part prints in PETG with a 0.4 mm nozzle, 0.2 mm layers and no supports. The largest are the row
ladders of the two 165 mm rows, 203.3 × 238.8 mm on the bed: by bounding box, a 250 × 250 mm bed takes
every part, and so does a 250 × 210 mm one with the ladders turned a quarter turn.

:::{status} designed
Sliced in Bambu Studio for a Bambu Lab H2D: 30 parts in the review of 2026-10-21; the drawer, its front, the
cradle and its strip, changed or drawn after that day, by the mechanical design document. The slot bin has not been
sliced. Nothing has been printed, and no other printer or slicer has been tried.
[What exists today](../plan/status.md#status-frame).
:::

## What fits which bed

The committed STL files, as they lie on the bed:

| Parts | Footprint, mm | Height, mm |
|---|---|---|
| Row ladder of a 165 mm row (`ladder_a`, `ladder_b`) | 203.3 × 238.8 | 7.4 |
| Row ladder of the 120 mm row (`ladder_c`) | 203.3 × 193.8 | 7.4 |
| Base ladder; cap strip | 203.3 × 152.9; 203.3 × 90.6 | 7.4 |
| Tray; cap plate | 165.0 × 210.0 | 30.5; 15.0 |
| Floor plate | 165.0 × 200.3 | 15.0 |
| Drawer; a sled bay's sled; its port block | 148.0 × 204.0; 148.0 × 159.0; 148.0 × 45.0 | 16.0 |
| Braces | 176.6 × 118.9 at most | 3.0 |
| Drawer front | 156.0 × 41.0 | 11.4 |
| Board plate; slot bin | 134.5 × 159.4 | 5.0; 42.4 |
| Every other part of the rack | 142 × 108 at most | 72.5 at most |

A row ladder is as long as its row is high (`rows[].height` in
[`config/rack.yaml`](../reference/rack-yaml.md)).

| Printable area of the bed | What fits |
|---|---|
| 250 × 250 mm or more | Every part. The design plans on 256 × 256 mm: the Bambu Lab X1, P1, A1 and H2D |
| 250 × 210 mm | Every part, each lying with its long side along the 250 mm. `ladder_a` and `ladder_b` then keep 5.6 mm at each end and 3.4 mm at each side. The tray and the cap plate are 210.0 mm long: the other way round they have no margin at all |
| 220 × 220 mm | Every part but `ladder_a` and `ladder_b`: ten parts of the default rack |
| 180 × 180 mm | Not the frame: the ladders, the floor and cap plates, the tray and the drawer are longer |

Both tables go by bounding box. Skirt, brim, purge line and the bed's unusable margin are left out, and only
the H2D's bed has been through the slicer.

## Filament

PETG: the clips and the snaps were sized for it. PLA creeps under the drawer's load and is ruled out; ABS and
ASA have not been assessed. For drawers that slide more smoothly, the design document suggests printing the
trays in a POM-like "igus" filament; nobody has tried it.

<!-- site:filament -->
Buy 5.1 kg of PETG for the default rack, six 1 kg spools, and 0.6 kg more for the twelve optional covers
(52 g each). That is 4.7 kg by the slicer's figures, part by part, and 10 % for waste, as the bill of
materials adds to its own figure. The bill counts 4.3 kg: 3.9 kg from the volume of each STL file, at 55 % of
the solid, and the same 10 %. The slicer, with three walls, gives more for the trays, the drawers and the
plates. All of it can be one colour but the two camera pods (28 g, dark and opaque), the two diffusers
(1 g each) and the inlays, which take a light colour.
<!-- /site:filament -->

Four parts make 0.69 kg of the 0.8 kg between the slicer's 4.7 kg and the bill's 3.9 kg:

| Part | In the rack | Bill's estimate | Slicer | More, in the rack |
|---|---|---|---|---|
| `tray` | 12 | 82.0 g | 108 g | 312 g |
| `drawer` | 11 | 35.6 g | 49 g | 147 g |
| `plate` | 7 | 41.0 g | 56 g | 105 g |
| `floor_plate`, `cap_plate` | 4 each | 38.8 g, 39.9 g | 54 g, 56 g | 125 g |

The 4.7 kg adds up each part's slicer figure on [Parts and quantities](parts-list.md), times its count: the
review's of 2026-10-21, and the design document's for the drawer, its front, the cradle and the strip. The
four slot bins, the five `ladder_c` (shorter than the 165 mm row ladder the review sliced) and the power
box's inlay have no slicer figure and are counted at the bill's estimate, 0.44 kg in all. The whole rack has
never been sliced in one go, and no spool has been weighed after a print.

A smaller rack: [One bay in the frame](parts-list.md#one-bay-in-the-frame) and
[A plain 2 × 2 rack](parts-list.md#plain-2x2) give the bill's grams for each. For a rack that grows, the
design document gives, undated, each bay added beside another about 382 g and each further cell of a large
grid about 217 g (a tray, a drawer and its front, a ladder and a brace: no plate, cradle or peg).

## Slicer settings

The profile is Bambu Studio's "0.20mm Standard @BBL H2D" with Bambu PETG Basic on a textured PEI plate, the
bed at 70 °C in the enclosure, and these values:

| Setting | Value |
|---|---|
| Nozzle | 0.4 mm |
| Layer height | 0.2 mm |
| Walls | 3 |
| Infill | 15 % gyroid |
| Supports | off |
| Brim | automatic: it comes on for the DATA board's cradle only, whose tall uprights stand on a small footprint. Keep it |
| Elephant-foot compensation (`elefant_foot_compensation`) | 0.15 mm |
| X-Y hole compensation (`xy_hole_compensation`) | 0.1 mm |
| Longest bridge printed without support (`max_bridge_length`) | 30 mm |

The last three change the stock profile, which has no elephant-foot or hole compensation. The slicer review of
2026-10-21 expects the holes that open towards the bed (the camera's inserts under the tray, the cradle's
screw holes) to come out 0.1 to 0.2 mm tight in the first layers without them, and the Ø4.0 insert holes to
come out true with them, so that an insert seats without bulging its boss. At the stock bridge length of
10 mm the slicer asks for supports under the tray's lips and over the power box's windows; the review counts
on PETG bridging 25 to 30 mm at this layer height. No part has been printed to check either: the
[test tray](index.md#what-to-check-on-a-test-tray-and-a-test-ladder) does.

No PrusaSlicer or OrcaSlicer profile has been tried: set the same three values, in millimetres, under your
slicer's names for them. The repository holds no profile, no project and no 3MF file.

Each STL file lies the way it prints, and [Parts and quantities](parts-list.md) says which way up. On
2026-10-21 the slicer's automatic orientation picked that same orientation for all 30 parts.

Four parts depart from the profile:

| Part | What differs |
|---|---|
| Braces | 100 % infill: they are mostly perimeter |
| Board plate | 2 or 3 walls; its 2.8 mm webs print solid |
| Slot bin | 2 walls |
| Power box base | 0.2 mm layers when its lettering is inlaid in a second colour; 0.12 to 0.16 mm when it is only engraved, in one colour (a 5.25 mm capital on a vertical wall is then 33 to 44 layers instead of 26) |

## No supports, anywhere

Switch supports off for every part. On a ladder or a cap strip they do harm: tree supports land inside the
grooves of the bed face, 5.3 mm bridges that the slicer's preview of 2026-10-21 prints without them. What the
parts ask of the printer instead:

| Part | Overhang or bridge |
|---|---|
| Tray | the left ledge bridges 38 mm from the fascia to its first gusset, over the row cable's window. The review accepts it with a test print to follow: [Measure before you print](index.md#what-to-check-on-a-test-tray-and-a-test-ladder) |
| Tray, floor plate, cap plate | the runners' underside slopes at 45°; on the tray, the lips' too |
| Drawer front | two bars bridge between the legs of the display's frame, a 0.2 mm skin over each screw hole |
| DATA board's cradle | its base bridges 16 mm at most between its feet |
| Power box base | the tops of the row outputs' windows: bridges of 12 mm at most in the review of 2026-10-21 |
| Pegs | every overhang is 45° or less but the 1 mm rim of the flange |

## Colours and two-colour parts

Three colours are asked for: the camera pod dark and opaque, its diffuser white, the inlays of the bay
labels and of the power box lighter than their body. The rest is your choice; the 3D model shows a dark grey
frame and trays, near-white drawers, blue plates and slot bins and a black power box.

Two objects are made of two files that register, one per colour:

- A bay's label: `bay_label_<bay>` and `bay_label_<bay>_inlay`. The bay's name is debossed 0.8 mm into the
  face that shows, which prints on the bed, and the inlay fills it flush.
- The power box: `power_box_base` and `power_box_labels`, which is exactly the volume of the walls'
  engravings.

In Bambu Studio, load both files at once, answer yes to loading them as one object with multiple parts, and
give the inlay the light filament.

A printer with one nozzle builds the whole rack. Print a label's body alone: its debossed name reads without
the inlay. Or print no label and put 12 mm label tape in the front's recess; nothing in the design holds
either in place ([Fit out a tray](../build/fit-out-a-tray.md)). Print the power box's base alone, at the
finer layers given under [Slicer settings](#slicer-settings): its lettering is engraved 0.8 mm deep and reads
under grazing light.
