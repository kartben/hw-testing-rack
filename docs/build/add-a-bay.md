# Add a bay, then a row

The bay beside an existing one shares the ladder between them: it takes one more ladder per level, a floor
plate, a cap plate, a brace per level and its tray.  A 6-pin jumper then joins its node to its neighbour's,
through the windows in both tray walls and in the shared ladder.

:::{status} designed
Written from the 3D model.  No two bays have been joined, and no jumper has carried a row's current.
[What exists today](../plan/status.md).
:::

## What the next bay shares

A ladder has tray grooves on both faces and four square nuts in its rear edge, and a brace's holes sit at
different heights on its left and on its right, so two neighbouring braces share a ladder.

```{figure} ../img/notice/done.svg
:class: bb-lineart
:width: 60%
:alt: Line drawing of two bays side by side on three ladders, under one row of cap plates

Two bays on three ladders, as the notice drew them on 2026-10-20: the middle ladder carries a tray on each
face.  The drawers are that date's, with a one-piece front.
```

For one more bay in a one-row rack:

* a base ladder, a row ladder, a cap strip, a floor plate, a cap plate, a base brace and a row brace, the
  nuts and inserts in ([Inserts and square nuts](../print/inserts-and-nuts.md));
* a tray from [Fit out a tray](fit-out-a-tray.md);
* 8 M3 × 8, two bench screws, a jumper that was rung out ([Make the row cables](row-cables.md)) and two
  cable ties of 2.5 × 100 mm.

Columns are added to the right: a row is fed at its left end, and each node passes the row on from its right
edge.

## The next column

:::{build-step} 1
:drawing: b1
:alt: A base ladder standing to the right of the first bay, the floor plate sliding in between
:parts: lb=1, fp=1
:click:

**Base ladder** on the right; the **floor plate** slides in from the front, between it and the shared ladder.
:::

:::{build-step} 2
:drawing: b2
:detail: pin_b
:alt: Rear view: the new base brace beside the first one, both screwed to the shared ladder
:parts: bb=1
:hardware: m3x8=4

**Base brace**: four M3 × 8, into the free nuts of the shared ladder (its 1st and 3rd from the bottom) and
into the 2nd and 4th of the new one.  Then this floor plate's two bench screws
([Screw the rack to the bench](screw-the-rack-to-the-bench.md)).
:::

:::{build-step} 3
:drawing: b3r
:alt: A row ladder coming down onto the new base ladder
:parts: la=1
:click:

**Row ladder** onto the new base ladder, as for [the first bay](first-bay.md#the-row-ladders).
:::

:::{build-step} 4
:drawing: b3t
:alt: The second bay's fitted tray sliding into the grooves from the front
:parts: tr=1
:click:

Its fitted **tray** slides in until both barbs click.
:::

:::{build-step} 5
:drawing: b5a
:alt: The second bay's row brace, cap strip and cap plate
:parts: bb=1, lc=1, cp=1
:hardware: m3x8=4
:click:

**Row brace**, four M3 × 8.  On the top row only: the cap strip, then the cap plate.
:::

## The jumper between two nodes

A jumper is a row cable with 152 mm leads for 120 mm of route.  Its red housing marks the IN end and its
black housing the OUT end; the cable works either way round, and the colours only make it readable.

:::{build-step} 6
:drawing: b4
:alt: Top view of two neighbouring trays, drawers out: the jumper from the left node across the front of its tray to the right node
:hardware: jumper=1, tie=2

Both drawers out.  The **black** housing into the left node's ROW OUT (J2, on its right edge).  From there
the jumper heads for the tray's front right and crosses that side within 9 mm of the tray's front: a cable tie
through the tunnel of each of the two anchors on the floor there.
:::

:::{build-step} 7
The jumper passes the windows in the tray's wall, in the shared ladder and in the next tray's wall, and turns
back up inside the ladder to the right node's ROW IN (J1, on its left edge): the **red** housing.  It lies
flat, with no twist.
:::

The drawing shows neither colour.  The ties are not optional: pulled right out, a drawer brings its chain foot
to 12 mm from the front.

:::{warning}
Nothing but a row cable goes into ROW OUT.  AUX (J5) is the same 6-pin socket, on the same edge of the node,
22 mm away, and pin 6 of ROW OUT carries the rack's 20 V.  An AUX lead pushed into ROW OUT puts that voltage
on its BOOT wire and into the board at its end.  A row cable pushed into AUX trips the row's eFuse.
:::

## The next row

A row stacks on the one below as the first row stacked on the base: its ladders snap onto those under them,
ridge into notch, then come its trays and its braces.  Print the files named for the row
(`ladder_b` and `brace_b`, `ladder_c` and `brace_c`): row C is 120 mm high and its ladder is shorter.  The
tray above is the ceiling of the bay below, with the four inserts of a camera's mount.

Jumpers stay inside a row: three for a row of four bays, nine for the default rack.  Each row has its own
feed from the power box into its first bay, three feeds for the default rack, and its own eFuse in the hub
([Power box and charger](power-box.md)).

## The last ROW OUT of each row

The last node of a row has nothing in ROW OUT, and the socket is live: its pin 6 carries VRACK whenever the
row is on.  In the default rack those are A4, B4 and C4.  The
[schematic review of 2026-10-25](../schematic-review-2026-10-25.md) asks for a blanking plug there until a
next revision gives AUX another connector.  No such plug exists yet: no printed part, no line in the bill
([Known issues, and what will not work](../reference/known-limitations.md)).  Nothing closes it, so the
warning above matters most in those three bays, where a free ROW OUT sits 22 mm from AUX.

## The order for twelve bays

*Worked out from the steps of these pages; no source gives an order for a whole rack, and nobody has built
one.*

1. All twelve trays at the bench ([Fit out a tray](fit-out-a-tray.md)).  Nothing in the frame is needed for
   them, and their guide lips' screws are out of reach afterwards.
2. The base, across: five base ladders, four floor plates, four base braces, from the left.  The two bench
   screws of each floor plate go in as its brace goes on.
3. Row A: five `ladder_a`, then each bay's tray and brace, then the row's three jumpers while nothing is above
   the nodes.
4. Row B, then row C, the same way.
5. The caps last: five cap strips, four cap plates.

A camera pod goes under a ceiling once that ceiling is in place ([Add a camera](camera.md)).

## Check before you go on

- [ ] Every brace is taut on its four screws, and each floor plate has its two bench screws.
- [ ] Every jumper runs from a ROW OUT (J2, right edge) to the next node's ROW IN (J1, left edge), flat.
- [ ] Every jumper is tied to both anchors at its tray's front right, and a drawer pulled right out passes
      over it.
- [ ] Nothing is plugged into a ROW OUT but a row cable, and each row's last ROW OUT is empty.

The nodes answer only once the power box is in: [Bring the rack online](bring-the-rack-online.md) lists every
bay by its place.

## On a rack that is already running

*Worked out from the hub's shell and from the [PCB review of 2026-11-09](../pcb-review-2026-11-09.md)
(in French), where the rule below is a calculation; nobody has done it yet.*

Switch the row off at the hub before a row cable is plugged or unplugged.  A node plugged into a live row
shares its neighbours' charge: by the review's figures a 20 V row falls to about 10 V with one node already
on it, 13.3 V with two and 15 V with three; with one or two already on it, the neighbours' DATA boards drop
out.  From the rack's page
([Rows and the rack's page](../use/rack-page.md)), or on the hub's console:

```console
uart:~$ hub row B off
```

Add the column as above, plug the jumper, then:

```console
uart:~$ hub row B on
uart:~$ hub nodes
```

A node that asks for an address makes the hub enumerate the whole rack again; `hub enumerate` asks for it by
hand.  The new bay takes its name from its place: the third bay of row B is B3, `bay-b3.local`, with nothing
to type on the node.  One more bay on a row also shares the row's 1.6 A with its neighbours
([Choose a size, change the layout](../plan/choose-your-rack.md)).

A new row needs its entry in `config/rack.yaml`, its own printed ladders and braces, a free row output on
the hub, which has four, and a feed.  The caps come off first: release each hook by pushing its barb through the window.

Found a step that is wrong?  [Report a finding](../reference/known-limitations.md#report-a-finding).
