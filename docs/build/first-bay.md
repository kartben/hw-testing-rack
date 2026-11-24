# Build the first bay

Every rack starts with one bay, at the bottom left. You build its frame around a fitted tray. The parts slide
into grooves or click together: only the two braces and the bench screws need a screwdriver.

Steps 1 to 5 need no tray, so you can put up the base and the row ladders while the PCBs are on their way.
Once this bay stands, [Add a column or a row](add-a-bay.md) grows the rack to the size you chose. Even a rack
of one bay takes the power box under it ([Power box and charger](power-box.md)). For one bay without a frame,
see [One bay on a desk](one-bay-on-a-desk.md).

## Parts for one bay

* A fitted tray ([Fit out a tray](fit-out-a-tray.md)).
* These printed parts, with the square nuts in the ladders and the four inserts under the cap plate
  ([Fit the inserts and nuts](../print/inserts-and-nuts.md)):
  * two base ladders (`ladder_base`) and two row ladders (`ladder_a`);
  * two cap strips (`ladder_cap`);
  * a floor plate (`floor_plate`) and a cap plate (`cap_plate`);
  * a base brace (`brace_base`) and a row brace (`brace_a`).
* 8 M3 × 8.
* Two wood screws with M4 washers, and a place for the rack. Read [Screw the rack to the bench](screw-the-rack-to-the-bench.md)
  before step 1.

## Put up the base

:::{build-step} 1
:drawing: a1
:alt: Two base ladders standing upright, side by side
:parts: lb=2

Stand two **base ladders** (`ladder_base`) on their long straight edge. Put the low end at the front, so that
the nut pockets run along the tall rear edge. Hold them, or lean them on a box, until the floor plate is in.
:::

:::{build-step} 2
:drawing: a2
:alt: The floor plate sliding between the two base ladders from the front
:parts: fp=1
:click:

Slide the **floor plate** into their bottom grooves from the front, until the barb of each latch arm clicks
into the window in the groove.
:::

:::{build-step} 3
:drawing: a3
:detail: pin
:alt: Rear view: the X-shaped brace and its four screws going into the rear edges of the two ladders
:parts: bb=1
:hardware: m3x8=4

Screw the **base brace** (`brace_base`) to the back of the ladders with four M3 × 8, into the square nuts.
Counting from the bottom, use the 1st and 3rd nuts of the left ladder and the 2nd and 4th of the right one,
left and right as seen from the front. The brace is taut once the fourth screw is in.
:::

If a nut falls out, push it back into its pocket from the open side. You can do this later too: the pockets
stay in reach from the back.

:::{build-step} 4
:hardware: Wood screw 3.5 × 16 pan head=2, M4 washer=2

Drive the two **bench screws** through the floor plate's front and rear bosses, into the bench.
[Screw the rack to the bench](screw-the-rack-to-the-bench.md) shows which bosses to use.
:::

## Add the row ladders

:::{build-step} 5
:drawing: a4
:detail: hook
:alt: Two row ladders coming down onto the base ladders
:parts: la=2
:click:

Set the **row ladders** (`ladder_a`) onto the base ladders, ridge into notch. Each one has its row letter on
the front post, and FRONT with an arrow on the top band. Push down firmly with your palm until both hooks of
each ladder click. To release a hook, push its barb back through its window.
:::

## Slide in the tray

:::{build-step} 6
:drawing: t4
:alt: The fitted tray, its drawer in it, sliding into the grooves of the row ladders from the front
:parts: tr=1
:click:

Slide the fitted **tray** into the grooves of the row ladders from the front, until the barb of each latch
arm clicks into its window. Leave the board plate and your boards out for now. They go in once the rack is
online ([A first session with a bay](../use/first-session.md)).
:::

:::{build-step} 7
:drawing: a6
:alt: Rear view: the row's brace and its four screws, above the base brace
:parts: bb=1
:hardware: m3x8=4

Screw the **row brace** (`brace_a`) to the row ladders with four M3 × 8, as in step 3.
:::

Leave the cables for later. You plug in the row's feed when you fit [the power box](power-box.md), and the
jumper to the next node when you add
[the next bay](add-a-bay.md#fit-the-jumper-between-two-nodes).

## Close the top

Do this step only if your rack has one bay. In a larger rack, leave the top open: you close it once the last
row is up ([Close the top of the rack](add-a-bay.md#close-the-top-of-the-rack)).

:::{build-step} 8
:drawing: a7
:alt: Two cap strips coming down onto the top ladders, the cap plate sliding into them from the front
:parts: lc=2, cp=1
:click:

Press the **cap strips** (`ladder_cap`) onto the top ladders until their hooks click, as in step 5. Then
slide the **cap plate** into their grooves from the front. Its four inserts hold a camera for the bay below
([Add a camera](camera.md)).
:::

## Fit a rear cover, if you want one

A printed cover (`cover_box4`) closes the back of the drawer over the DATA board. Hook its lips over the front
of the port wall, then press the rear edge down until both tabs click. To take it off, lift it by its sides:
the cables can stay plugged in.

## Check before you go on

- [ ] Each brace is taut on its four screws.
- [ ] Both hooks of each row ladder, and of each cap strip, are in their windows.
- [ ] Both barbs of the tray, and of the floor plate, are in their windows.
- [ ] The drawer runs out 140 mm in the frame as it did on the bench, and its detent holds it closed.
- [ ] The floor plate's two bench screws are in.

## If the drawer sticks

| What you see | What to check |
|---|---|
| The tray does not go into the grooves of the ladders | Elephant's foot on the tray's runners, which have only 0.15 mm of play on each side. Set your slicer's elephant-foot compensation to 0.15 mm ([Printer, filament and settings](../print/printer-and-settings.md)). |
| The drawer drags along its whole travel | The ledges it rides on, and the underside of the guide lips. |
| It stops before 140 mm, or pulls on the lead | The drag chain: about 180 mm of the chain you measured before printing ([Parts to measure before you print](../print/index.md#parts-to-measure-before-you-print)). No spare lead in front of its moving end. |
| The drawer moves, the chain does not | The screw that locks the chain foot (step 10 of [Fit out a tray](fit-out-a-tray.md)). |
| It comes right out | The stop screw is missing. Take the tray out to fit it ([Take a tray out](../use/service-a-bay.md#take-a-tray-out)). |
| It does not stay closed | The detent's tab in the tray's left ledge, or [the magnets](fit-out-a-tray.md#glue-the-detent-magnets-if-you-chose-them). |
| It stops near the end of its travel | The ties of the jumper at the tray's front right ([Fit the jumper](add-a-bay.md#fit-the-jumper-between-two-nodes)). |
