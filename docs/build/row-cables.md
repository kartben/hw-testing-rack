# Make the row cables

A row cable is six single 24 AWG leads clicked into two JST PH housings, a red one and a black one. The default
rack takes twelve, all wired the same way: nine jumpers from node to node and three feeds from the power box.

:::{status} designed
The parts were chosen on 2026-10-21 and are in the bill of materials. No row cable has been made, and none
has carried a row's power or the rack bus. [What exists today](../plan/status.md).
:::

Make them while the PCBs are on their way: a meter is all a cable needs to be tested, and the checklists use
one at stage 5 of [the hub's](check-the-pcbs/power-hub.md) and of [the node's](check-the-pcbs/bay-node.md),
then at the first step of [the hub and two nodes](check-the-pcbs/rack-bus.md).

## What a row cable is

Six pins of JST PH, 2.0 mm pitch, carry a row's power (VRACK, 20 or 28 V), the rack's CAN bus and the position wire
(POS). Every output has the input's pinout mirrored, so one cable does for every link: pin n at one end meets
pin 7 − n at the other.

```{include} ../can.md
:start-after: <!-- site:row-pinout -->
:end-before: <!-- /site:row-pinout -->
```

The red housing (PHR-6-R) is the IN end: it goes into a node's J1, on the node's left edge, and its position n
is J1's pin n. The black housing (PHR-6-BK) is the OUT end: a node's J2, on its right edge, or a row output of
the hub. The cable works either way round; the colours only make it readable. The rack's other leads are on
[Cables and pinouts](../reference/cables.md).

A jumper and a feed differ only in length:

```{include} ../reference/cables.md
:start-after: <!-- site:row-cable-lengths -->
:end-before: <!-- /site:row-cable-lengths -->
```

The jumpers are routed on [Add a bay, then a row](add-a-bay.md), the feeds on
[Power box and charger](power-box.md#now-the-row-feeds). Once the rack runs, switch a row off at the hub
before you plug or unplug one of its cables. On paper, a node plugged into a live row of one or two nodes
pulls the row down far enough to cut their boards' power (finding BN-04 of the
[review of 2026-11-09](../pcb-review-2026-11-09.md), computed, not measured).

## Parts and tools

```{bom-table}
:category: Cables
:match: row cable|crimp contact|crimped feeds
:columns: item, qty, source
```

The counts are for the default 4 × 3 rack: a rack of c columns and r rows takes r × (c − 1) jumpers and r
feeds, six leads each. Spares are counted in: four 152 mm leads, two 305 mm leads, two housings of each
colour, and as many contacts again as the two crimped feeds take. Where to order: the
[Shopping list](../plan/shopping-list.md).

Beside the parts, a multimeter with a continuity beeper and a few small cable ties for each cable's six leads.
The bill counts only the two ties that hold each jumper to its tray.

## Make a jumper

A pre-crimped lead clicks into a housing with no tool.

:::{build-step} 1
:name: jumper-1
:parts: 152 mm lead (ASPHSPH24K152)=6, red housing PHR-6-R=1, black housing PHR-6-BK=1

Hold both housings the same way: latch up, mating faces away from you, the red one on the left.
:::

:::{build-step} 2
:name: jumper-2

Push one end of a lead into the **outermost left** position of the red housing until it clicks, then tug it.
Its other end goes into the **outermost right** position of the black housing. The five other leads follow,
working inwards, each from a position of the red housing to the mirrored one of the black. Tug every contact.
:::

:::{build-step} 3
:name: jumper-3
:drawing: hw_jumper
:alt: A six-wire lead lying flat, a plug at each end, both plugs the same face up

Lay the cable straight on the table. It lies flat with no twist, and both plugs show the same face. Hold the
six leads together with a few small cable ties.
:::

The leads are all black. To tell them apart later, plug the red end into a node's J1 and put a red stripe
(marker or heat-shrink) at both ends of the lead on J1's pin 1, VRACK. At 120 mm routed, a jumper's CAN pair
needs no twist.

## Make the feeds

Row A's feed is a jumper made of six 305 mm leads (ASPHSPH24K305). JST makes no longer lead, so the feeds to
rows B and C are crimped: six wires of 60 cm for row B, six of 80 cm for row C, a contact at each end.

:::{build-step} 1
:name: feed-1

Check the wire when it arrives: strip one end, count the strands and measure one. 24 AWG is 7 × 0.20 mm,
11 × 0.16 or 19 × 0.12 (≈ 0.21 mm²); 7 × 0.16 is 26 AWG, and JST gives the contact's 2 A on 24 AWG only.
:::

:::{build-step} 2
:name: feed-2

Make a few practice crimps with the ratchet crimper (IWISS SN-28B) before the first real one.
[A crimp cannot be undone](index.md#crimp): a bad one is cut off with its end of the wire. The bill buys 50
contacts for the 24 of the two feeds. How much insulation to strip and which die fits the contact are written
nowhere in this project: the practice crimps settle both.
:::

:::{build-step} 3
:name: feed-3
:parts: wire of 60 cm=6, wire of 80 cm=6, contact SPH-002T-P0.5S=24

Cut the wires and crimp a contact on both ends of each: 12 contacts a feed. The bill's spool counts 4 cm more
a wire than these lengths.
:::

:::{build-step} 4
:name: feed-4
:parts: red housing PHR-6-R=2, black housing PHR-6-BK=2

Insert them as a jumper's leads: outermost left of the red housing to outermost right of the black one, and so
on inwards. Tug every contact.
:::

:::{build-step} 5
:name: feed-5

Twist the two middle leads, the CAN pair, 2 to 3 turns per 10 cm, then hold the six together with cable ties.
On its way up the rack's side a feed takes a half turn: the bundle turns as one, the CAN pair between its GND
leads.
:::

Row D's feed has no measured length (`tools/bom.py` counts row C's 80 cm for it): measure the route on the
rack before cutting.

## A two-wire lead for the bench

A node runs only from its row, never from USB. Stage 3 of [its checklist](check-the-pcbs/bay-node.md) feeds it
from a bench supply through J1: pin 1 is +, pins 2 and 5 are GND. The lead is a red housing with two of the
spare leads in it, and it can wait for the first node to arrive.

1. Plug the empty red housing into the node's J1. J1's pin 1 is the one towards the node's rear edge, the
   edge with the module's antenna: mark that end of the housing.
2. Click one lead into position 1, for +, and one into position 2, for GND.
3. Mark the + lead, and take the two free ends to the supply.

With the two swapped, the node's reverse-polarity FET lets no current flow and nothing is harmed. Worked out
from the node's checklist and the pinout; no source describes this lead, and nobody has made one.

## Ring every cable out, the bought leads too

Ring every row cable with a meter before a PCB sees it:

- [ ] Each position of the red housing rings to its mirror in the black one. Counting both from the left,
  latch up and mating faces away from you: 1 to 6, 2 to 5, 3 to 4, 4 to 3, 5 to 2, 6 to 1.
- [ ] No position rings to its neighbour in the same housing.
- [ ] Laid flat, both plugs show the same face.

The DATA leads and the camera leads are bought ready-made (JST PH 8, 50 cm, sold as "Same direction"), and
sellers do not all use that name the same way. Ring each of them out too:

- [ ] Pin n rings to pin 9 − n on all eight: 1 to 8, 2 to 7, and so on.
- [ ] Laid flat, both plugs show the same face.

## What a wrong cable does

Two mistakes cost parts: a row cable with VRACK on a CAN wire, which the ring-out catches, and an AUX lead
pushed into ROW OUT. Most of the others leave a node, a DATA board or a camera off. All of it is reasoned from
the schematics; none has been tried.

```{include} ../reference/cables.md
:start-after: <!-- site:wrong-cable -->
:end-before: <!-- /site:wrong-cable -->
```

What a missing bay looks like from the hub, once the rack is powered, is on
[Troubleshooting](../use/troubleshooting.md).

A step that is wrong: [report it](../reference/known-limitations.md#report-a-finding).
