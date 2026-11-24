# Add a column or a row

Once the first bay stands, you build the rest of the rack from it: more columns to the right, more rows on
top. You choose how far: up to four rows, and as many columns as the power allows
([Choose your rack's size](../plan/choose-your-rack.md)). You can also add bays later, to a rack that is
already running.

## Build the rest of the rack in this order

1. Put up the base of each further column, from left to right (steps 1 to 3).
2. Fill row A from left to right. Each bay takes its row ladder, its tray and its brace (steps 4 to 6). Then
   fit the jumper from the bay on its left (steps 7 and 8).
3. Fill each further row in the same way, from the bottom up. Fit a row's jumpers before you put up the row
   above it.
4. Close the top of the rack: a cap strip on every top ladder, then a cap plate over each top bay (step 9).
5. Fit the cameras, if you have any ([Add a camera](camera.md)), then the power box
   ([Power box and charger](power-box.md)).

Always build to the right. Power and the rack bus enter each row at its left end, and each node passes them on
through its right edge.

For a rack of two columns and two rows, the order is:

| Order | What you put up | Steps |
|---|---|---|
| 1 | Bay A1, without its cap | [Build the first bay](first-bay.md) |
| 2 | The base of column 2: a base ladder, a floor plate, a base brace, two bench screws | 1 to 3 |
| 3 | Bay A2: a row ladder (`ladder_a`), its tray and its brace, then the jumper from A1 | 4 to 8 |
| 4 | Bay B1: two row ladders (`ladder_b`), its tray and its brace | 4 to 6 |
| 5 | Bay B2: a row ladder (`ladder_b`), its tray and its brace, then the jumper from B1 | 4 to 8 |
| 6 | The top: three cap strips, then two cap plates | 9 |

## What each new bay takes

Two neighbouring bays share the ladder between them. Each bay after the first takes:

* a fitted tray ([Fit out a tray](fit-out-a-tray.md));
* its row's ladder (`ladder_a` in row A, `ladder_b` in row B), or two for the first bay of a row;
* its row's brace (`brace_a` in row A, `brace_b` in row B) and four M3 × 8;
* unless it is the first bay of its row, a jumper that you have rung out ([Make the row cables](row-cables.md))
  and two cable ties of 2.5 × 100 mm.

Each column after the first also takes a base ladder (`ladder_base`), a floor plate, a base brace
(`brace_base`), four M3 × 8 and two bench screws. The top of the rack takes a cap strip (`ladder_cap`) on
every top ladder and a cap plate over each top bay. [Parts to print](../print/parts-list.md) counts the printed
parts for a rack of any size.

## Put up the base of a column

:::{build-step} 1
:drawing: b1
:alt: A base ladder standing to the right of the first bay, the floor plate sliding in between
:parts: lb=1, fp=1
:click:

Stand a **base ladder** (`ladder_base`) to the right of the rack. Slide a **floor plate** in from the front,
between the new ladder and the rack's right-hand ladder, which the two columns now share.
:::

:::{build-step} 2
:drawing: b2
:detail: pin_b
:alt: Rear view: the new base brace beside the first one, both screwed to the shared ladder
:parts: bb=1
:hardware: m3x8=4

Screw on the **base brace** (`brace_base`) with four M3 × 8. Counting from the bottom, use the 1st and 3rd
nuts of the shared ladder and the 2nd and 4th of the new one.
:::

:::{build-step} 3
:hardware: Wood screw 3.5 × 16 pan head=2, M4 washer=2

Screw the new floor plate to the bench with two **bench screws**
([Screw the rack to the bench](screw-the-rack-to-the-bench.md)).
:::

## Add a bay to a row

:::{build-step} 4
:drawing: b3r
:alt: A row ladder coming down onto the ladder below it
:parts: la=1
:click:

Press a **row ladder** onto the ladder below, on the right of the new bay, until it clicks. The first bay of a
row takes two, one on each side. Do it as for [the first bay](first-bay.md#add-the-row-ladders).
:::

:::{build-step} 5
:drawing: b3t
:alt: The new bay's fitted tray sliding into the grooves from the front
:parts: tr=1
:click:

Slide the fitted **tray** in until both barbs click.
:::

:::{build-step} 6
:drawing: a6
:alt: Rear view: a row brace and its four screws, above the brace of the row below
:parts: bb=1
:hardware: m3x8=4

Screw on the **row brace** with four M3 × 8. Use the 1st and 3rd nuts of the ladder on the left and the 2nd
and 4th of the one on the right, as in step 2.
:::

## Fit the jumper between two nodes

The jumper is the short row cable that joins two neighbouring nodes. Fit it as soon as the trays on both sides
are in. It works either way round, but the colours make it easier to follow: the black housing goes at the OUT
end, the red one at the IN end.

:::{build-step} 7
:drawing: b4
:alt: Top view of two neighbouring trays, drawers out: the jumper from the left node across the front of its tray to the right node
:hardware: jumper=1, tie=2

Pull both drawers out. Plug the **black** housing into ROW OUT of the left node (J2, on its right edge). Run
the jumper across the front right corner of the tray, no more than 9 mm from the front. Tie it through the
two anchors on the floor there.
:::

:::{build-step} 8

Pass the jumper through the windows in the tray's wall, in the shared ladder and in the next tray's wall. Turn
it up inside the ladder. Plug the **red** housing into ROW IN of the right node (J1, on its left edge), with no
twist in the cable.
:::

Do not leave out the ties: a drawer pulled right out stops on a loose jumper.

:::{warning}
ROW OUT and AUX (J5) take the same plug, and they sit 22 mm apart on the same edge of the node. Plug nothing
but a row cable into ROW OUT: its pin 6 carries the row's 20 V whenever the row is on. An AUX lead
plugged into ROW OUT puts that voltage on your board's BOOT pin. A row cable plugged into AUX trips the row's
eFuse. The last ROW OUT of each row stays empty and uncovered, so take most care there.
:::

## Close the top of the rack

:::{build-step} 9
:drawing: a7
:alt: Two cap strips coming down onto the top ladders, the cap plate sliding into them from the front
:parts: lc, cp
:click:

Once the last row is up, press a **cap strip** (`ladder_cap`) onto every top ladder until its hooks click.
Then slide a **cap plate** into each top bay from the front. Its four inserts hold a camera for the bay below
([Add a camera](camera.md)).
:::

## Grow a finished rack

A finished rack has its caps on. You can still add a column or a row. If the rack is running, read
[Add bays to a running rack](#add-bays-to-a-running-rack) first.

### Add a column

Put up its base (steps 1 to 3). Then, from row A upwards, add its bay in each row (steps 4 to 6) and fit that
row's jumper (steps 7 and 8). Then fit its cap strip and its cap plate (step 9).

### Add a row

Add the row to `config/rack.yaml` first ([Choose your rack's size](../plan/choose-your-rack.md)). Each row has
its own ladder and brace files to print: `ladder_b` and `brace_b` for row B.

Take the caps off: push the barb of each hook back through its window. Fill the new row from left to right
(steps 4 to 8), then close the top again (step 9).

Each row has its own feed from [the power box](power-box.md), so make one for the new row
([Make the row cables](row-cables.md)). The hub has four row outputs, so a rack has four rows at most.

## Add bays to a running rack

Switch the row off before you plug or unplug a row cable. A node plugged into a live row pulls down its
neighbours' supply, and their DATA boards drop out. Switch the row off on [the rack's page](../use/rack-page.md),
or in the hub's shell:

```console
uart:~$ hub row B off
```

Add the bay and plug in its jumper. Then switch the row back on and list the nodes:

```console
uart:~$ hub row B on
uart:~$ hub nodes
```

The hub finds the new node by itself. To make it look again, run `hub enumerate`. The new bay is named after
its place: the third bay of row B is B3, at `bay-b3.local`. Each bay you add to a row leaves a little less
power for the others ([Power budget and queued ports](../use/power-budget.md)).

## Check before you go on

- [ ] Every brace is taut on its four screws, and each floor plate has its two bench screws.
- [ ] Every jumper runs from a ROW OUT (J2, right edge) to the next node's ROW IN (J1, left edge).
- [ ] Every jumper is tied to both anchors at its tray's front right, and a drawer pulled right out passes
      over it.
- [ ] Nothing but a row cable is plugged into a ROW OUT, and each row's last ROW OUT is empty.
- [ ] Both hooks of every cap strip are in their windows.
