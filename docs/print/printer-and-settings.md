# Printer, filament and settings

Every part prints in PETG with a 0.4 mm nozzle, 0.2 mm layers and no supports. Each STL file already lies
the way it prints: keep it that way up.

## Bed size

| Your bed | What fits |
|---|---|
| 250 × 250 mm or more | everything. The Bambu Lab X1, P1 and A1 have 256 × 256 mm |
| 250 × 210 mm | everything, each part with its long side along the 250 mm |
| 220 × 220 mm | everything but the row ladders of 165 mm rows |
| 180 × 180 mm | not the ladders, the trays, the drawers, the floor and cap plates or the desk frame (`standalone_desk_frame`) |

The largest parts, as they lie on the bed:

| Part | Size on the bed, mm |
|---|---|
| Row ladder of a 165 mm row (`ladder_a`, `ladder_b`) | 203.3 × 238.8 |
| Row ladder of a 120 mm row (`ladder_c`) | 203.3 × 193.8 |
| Base ladder (`ladder_base`) | 203.3 × 152.9 |
| Tray, cap plate | 165.0 × 210.0 |
| Floor plate | 165.0 × 200.3 |
| Drawer | 148.0 × 204.0 |

A row ladder is longer when its row is taller (`rows[].height` in
[config/rack.yaml](../reference/rack-yaml.md)). These sizes are the outlines of the parts. Leave room for a
skirt, a brim and the margins of your bed.

## Filament and print time

<!-- site:filament -->
Use PETG: the clips and snaps are sized for it. PLA creeps under the load of the drawer.

How much you print depends on the size of your rack:

| Rack | PETG | Print time |
|---|---|---|
| The 4 × 3 example, 12 bays | 5.1 kg: six 1 kg spools | about 190 hours |
| A plain 2 × 2, 4 bays | 1.9 kg: two 1 kg spools | about 70 hours |
| One bay in its frame | 0.7 kg: one 1 kg spool | about 25 hours |
| Another size | the grams of its parts, plus 30 % | the sum of the times of its parts |

[Parts to print](../print/parts-list.md) gives the grams and the print time of each part, and the counts
for any size. Its grams are estimated from the volume of each file. The slicer uses about 30 % more, so the
PETG above is those grams plus 30 %. The optional rear-bay covers (`cover_box4`) are not included: for those,
add their grams plus 30 %.

The print times are Bambu Studio's for a Bambu Lab H2D, with the settings below. A slower printer takes
longer.

You can print nearly everything in one colour. Print the camera pod in a dark, opaque PETG and its diffuser
in white. Print the inlays of the labels in a light colour
([Colours and two-colour parts](../print/printer-and-settings.md#colours-and-two-colour-parts)).
<!-- /site:filament -->

## Slicer settings

These settings start from the "0.20mm Standard @BBL H2D" profile of Bambu Studio, with Bambu PETG Basic on a
textured PEI plate and the bed at 70 °C.

| Setting | Value |
|---|---|
| Nozzle | 0.4 mm |
| Layer height | 0.2 mm |
| Walls | 3 |
| Infill | 15 % gyroid |
| Supports | off |
| Brim | automatic: keep it on the pegs |
| Elephant-foot compensation (`elefant_foot_compensation`) | 0.15 mm |
| X-Y hole compensation (`xy_hole_compensation`) | 0.1 mm |
| Longest bridge without support (`max_bridge_length`) | 30 mm |

The last three rows differ from the stock profile. Without the hole compensation, holes that face the bed
come out 0.1 to 0.2 mm tight, and an insert can split its boss. With the stock bridge length of 10 mm, the
slicer adds supports under the lips of the tray and over the windows of the power box.

In another slicer, such as PrusaSlicer or OrcaSlicer, set the same values under its own names. The
repository has no slicer profile or project file.

Change the profile for four parts:

| Part | Change |
|---|---|
| Braces | 100 % infill |
| Board plate (`plate`) | 2 or 3 walls |
| Slot bin | 2 walls |
| Power box base, printed in one colour | 0.12 to 0.16 mm layers, so that its engraved lettering comes out sharp |

## Print without supports

Turn supports off for every part. On the ladders and the cap strips, the slicer would put supports inside
the grooves, and the grooves print well without them.

The parts are designed to need none. Watch these bridges and overhangs:

- The tray's left ledge bridges 38 mm over the window for the row cable. The test tray checks it
  ([Print one tray and one ladder first](index.md#print-one-tray-and-one-ladder-first)).
- The DATA board's cradle bridges up to 16 mm between its feet.
- The power box base bridges up to 12 mm over the windows of the row outputs.
- In the drawer front, two bars bridge across the window on the right.
- The runners along the sides of the tray and the plates slope at 45° underneath.

## Colours and two-colour parts

Two objects print from two files each, one file per colour:

- A bay's label: `bay_label_<bay>` and `bay_label_<bay>_inlay`. The bay's name is sunk 0.8 mm into the
  front face of the label, and the inlay fills it flush. The front face prints on the bed.
- The power box: `power_box_base` and `power_box_labels`. The second file fills the lettering engraved in
  the walls.

In Bambu Studio, load both files at once. When it asks whether to load them as one object with multiple
parts, answer yes. Give the inlay the light filament.

If you print in one colour only, print the label's body alone: you can still read the sunk name. You can
also stick 12 mm label tape in the recess of the drawer front instead of a printed label. Print the power
box base alone, with the finer layers given above. Its lettering is 0.8 mm deep and shows when light falls
across it.
