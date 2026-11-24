# Make the row cables

A row cable carries a row's power and the rack's CAN bus from one bay node to the next. It is six single
24 AWG leads in two JST PH 6-pin housings, a red one and a black one. Make the cables while the PCBs are on
their way: you need them to check the PCBs.

## Jumpers and feeds

All row cables are wired the same way. Pin n at one end meets pin 7 − n at the other, so one cable fits every
link. A jumper links two neighbouring nodes in a row. A feed links the power box to the first node of a row.
For a rack of c columns and r rows, make r × (c − 1) jumpers and r feeds. Only their lengths differ:

```{include} ../reference/cables.md
:start-after: <!-- site:row-cable-lengths -->
:end-before: <!-- /site:row-cable-lengths -->
```

JST sells pre-crimped leads up to 305 mm. That is long enough for every jumper and for the feed to row A, so a
rack of one row needs no crimping. You crimp the feeds to rows B, C and D by hand.

The red housing (PHR-6-R) is the IN end. It plugs into J1, on the left edge of a node. The black housing
(PHR-6-BK) is the OUT end. It plugs into J2, on the right edge of a node, or into a row output of the hub. The
cable works either way round, but the colours make it easier to follow. The pinout is on
[Cables and pinouts](../reference/cables.md).

Once the rack runs, switch a row off at the hub before you plug or unplug one of its cables.

## Parts and tools

Each cable takes six leads, a red housing and a black one. A feed that you crimp takes 12 contacts and wire
instead of ready-made leads. For a rack of two columns and two rows, that is two jumpers and two feeds. With
spares, buy:

```{bom-table}
:category: Cables
:match: row cable|crimp contact|crimped feeds
:columns: item, qty, source
:size: 2x2
```

For another size, count your cables with the rule above. The table has more contacts than the feeds take,
so that you can practise crimping. [Shopping list and tools](../plan/shopping-list.md) gives the counts for the example rack of
`config/rack.yaml`.

You also need a multimeter with a continuity beeper. Cut the heat-shrink tube into 10 mm bands: three for each
cable, plus one for every 15 cm of a feed.

## Make a jumper

Pre-crimped leads click into the housings with no tool.

:::{build-step} 1
:name: jumper-1
:parts: 152 mm lead (ASPHSPH24K152)=6, red housing PHR-6-R=1, black housing PHR-6-BK=1

Hold both housings the same way: latch up, mating faces away from you, the red one on the left.
:::

:::{build-step} 2
:name: jumper-2

Fill the **red** housing. Push one end of each lead into a position until it clicks, then tug it.
:::

:::{build-step} 3
:name: jumper-3
:parts: 10 mm band of 6.4 mm heat-shrink=3

Slip three bands of heat-shrink over the six leads now. They do not fit over a housing, so they must go on
before you fill the black one.
:::

:::{build-step} 4
:name: jumper-4

Fill the **black** housing in mirror order. The lead in the leftmost position of the red housing goes into the
rightmost position of the black one, and so on inwards. Tug every contact.
:::

:::{build-step} 5
:name: jumper-5
:drawing: hw_jumper
:alt: A six-wire lead laid straight, a plug at each end, both plugs the same face up

Lay the cable straight on the table: both plugs show the same face. Shrink one band 2 cm from each housing
and one in the middle. Small cable ties or a turn of tape also work.
:::

The leads are all black, so mark the power lead when your first node arrives. Plug the red end into the
node's J1. Pin 1 is at the end towards the node's antenna, and its lead carries VRACK, the row's power. Put a
red stripe on that lead at both ends.

## Make the feeds

Make row A's feed as a jumper, with six 305 mm leads (ASPHSPH24K305). Twist its CAN pair as in step 5 below
before you fill the black housing.

Crimp the other feeds from wire: 60 cm for row B, 80 cm for row C. Row D's route is longer than row C's, so
measure it on your rack before you cut the wire. The quantities in the steps are for rows B and C.

:::{build-step} 1
:name: feed-1

Check the wire when it arrives. Strip one end, count the strands and measure one. 24 AWG is 7 × 0.20 mm,
11 × 0.16 mm or 19 × 0.12 mm. 7 × 0.16 mm is 26 AWG, which is too thin: the contact is rated 2 A on 24 AWG
only.
:::

:::{build-step} 2
:name: feed-2

Make a few practice crimps with the ratchet crimper. Use them to find the strip length and the die that fit
the contact. [A crimp cannot be undone](index.md#crimp): cut a bad one off with its end of the wire.
:::

:::{build-step} 3
:name: feed-3
:parts: wire of 60 cm=6, wire of 80 cm=6, contact SPH-002T-P0.5S=24

Cut the wires and crimp a contact on both ends of each. A feed takes 12 contacts.
:::

:::{build-step} 4
:name: feed-4
:parts: red housing PHR-6-R=2, black housing PHR-6-BK=2

Fill the red housing as for a jumper.
:::

:::{build-step} 5
:name: feed-5

Twist the two middle leads, the CAN pair, 2 to 3 turns every 10 cm. Then slip on the bands: one for each end
and one for every 15 cm in between.
:::

:::{build-step} 6
:name: feed-6

Fill the black housing in mirror order, as for a jumper. Tug every contact. Shrink one band 2 cm from each
housing and the others about every 15 cm.
:::

## A two-wire lead for the bench

A bay node takes its power only from its row, never from USB. To check a node on the bench, you power it
through J1 from a bench supply. Make this lead when your first node arrives, from a red housing and two spare
leads:

1. Plug the empty red housing into the node's J1. Pin 1 is at the end towards the node's rear edge, where the
   module's antenna is. Mark that end of the housing.
2. Click one lead into position 1, for +, and one into position 2, for GND.
3. Mark the + lead, and take the two free ends to the supply.

If you swap the two wires, the node's reverse-polarity protection blocks the current and nothing is damaged.

## Ring out every cable

Ring every row cable with a meter before you plug it into a PCB. Hold the housings latch up, mating faces away
from you, and count both from the left:

- [ ] Each position of the red housing rings to its mirror in the black one: 1 to 6, 2 to 5, 3 to 4, 4 to 3,
  5 to 2, 6 to 1.
- [ ] No position rings to its neighbour in the same housing.
- [ ] Laid straight, both plugs show the same face.

You buy the DATA leads and the camera leads ready-made (JST PH 8, sold as "Same direction"). Sellers do not all
mean the same thing by that name, so ring them out too:

- [ ] Pin n rings to pin 9 − n: 1 to 8, 2 to 7, and so on.
- [ ] Laid flat, both plugs show the same face.

A wrong cable usually leaves a node, a DATA board or a camera off. A row cable with the row's power on a CAN
wire is worse: it destroys the CAN protection diode of the hub and of every node on the bus. The ring-out
catches it. An AUX lead pushed into a node's ROW OUT (J2) puts the row's power on its BOOT wire, and can
destroy the board at the other end. [Cables and pinouts](../reference/cables.md#what-a-wrong-cable-does) lists every case.
