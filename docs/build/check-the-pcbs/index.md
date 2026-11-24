# Check each PCB on the bench

Bring-up is one short checklist per PCB, six in all: each takes a PCB from its bag to working, on the bench,
before anything is screwed to a tray.  Do them first: the test pads are on the bottom face of the hub and of
the node, and on the rear face of a DATA board, and a node's are under it once it is on its tray.

:::{status} designed
No PCB has been powered: the five v1.0 PCBs have been at the fab since 2026-11-11.  The expected values are
the design's, so the first PCB of a kind sets the reference for the second.
[What exists today](../../plan/status.md#the-five-pcbs).
:::

The checklists are first-article inspections, written for the first PCBs of a revision: whoever orders v1.0
PCBs today is the first to power them.  They take nothing as tested: every part is looked at, and every rail
measured before anything is plugged in.  A shorter path, for PCBs that someone else has already tested, does
not exist yet.

```{figure} ../../img/pcbs/bay-node-bottom.jpg
:alt: The bottom face of the bay node v1.0, with its named test pads
:width: 70%

KiCad render of the bay node v1.0, bottom face.  Every pad its checklist names is here: the supply row at the
bottom, and at the top TX, RX and GND, the pads of its shell.
```

## The order

| Order | PCB | Needs |
|---|---|---|
| 1 | [Power hub](power-hub.md) | a USB-C PD charger |
| 2 | [Bay node](bay-node.md) | a bench supply, then the hub |
| 3 | [Camera pod](camera-pod.md) | a working node, an Arducam Mega |
| 4 | [DATA ×6](data-x6.md) | a bench supply; a working node (its firmware drives this PCB since 2026-11-11, tested in simulation only) |
| 5 | [DATA ×4](data-x4.md) | a bench supply; a working node |
| 6 | [The rack bus](rack-bus.md) | the hub and two nodes |

The order adds one unknown at a time: the hub needs nothing else, the node runs from a bench supply before it
meets the hub, and the three other PCBs hang off a node that already works.  The two DATA boards come from the
fab without their through-hole connectors: [solder them](../solder-the-connectors.md) first.

## Every PCB, the same five stages

1. **Look.**  Compare the PCB with its render, at the top of its checklist.  Check the pin-1 mark of every
   IC, the stripe of the electrolytic capacitor, the LEDs and the diodes.  Look at the QFN and SOT-23-6 parts
   first, and stop if one is turned: the project's own order had to ask the fab about their rotation.
2. **Measure with no power.**  Ohmmeter between each supply pad and GND, on the labelled test pads.  A reading
   that starts low and climbs is a capacitor charging: fine.  A steady reading under 10 Ω is a short: stop.
   Write the readings down.
3. **First power, current limited.**  Bench supply with the limit the checklist gives, or the source it names.
   Check each rail on its pad before plugging anything else in.
4. **Flash, then ask the firmware.**  The shell and the status page report what the PCB sees.  The hub and
   each node are flashed with [Flash the hub and the nodes](../flash.md), from the images of
   [Build or download the firmware](../get-the-firmware.md), and given their Wi-Fi network.
5. **Load it.**  The checks that need a load, a board or a second PCB.

The hub's and the node's checklists end on a sixth stage, *Last*: it burns the module's one-time fuse, the one
step of these pages [that cannot be undone](../index.md#fuse).

## What you need

```{include} ../../plan/shopping-list.md
:start-after: <!-- site:bench-equipment -->
:end-before: <!-- /site:bench-equipment -->
```

The row cable and the two-wire lead for the bench supply are made on
[Make the row cables](../row-cables.md).  The DATA lead and the camera lead are bought; the same page rings
them out before a PCB sees them.

## The second PCB of a kind, and the rest

Do the whole checklist on the first assembled PCB of a kind before powering the second.  The project's own
order was five PCBs of each kind, two of them assembled: its three bare PCBs serve to compare a doubtful
reading with a PCB that has no parts.

What the third to the twelfth node of a rack go through, once the first two have passed, is not decided: no
shorter checklist is written.  Every node still needs stage 4, its flash over USB, and its Wi-Fi network while
the pads are in reach if the image carries none.  The hub and every node that goes into the rack also get the
module's one-time fuse, at stage 6.

## When to stop

At the first thing that does not match: a part turned at stage 1, a steady reading under 10 Ω at stage 2, a
rail outside the range its checklist gives at stage 3.  Do not go on to the next stage, and leave the second
PCB of that kind in its bag.

v1.0 is frozen ([Revisions at the fab](../../electronics.md#revisions-at-the-fab)): a fault found on the bench
is fixed in the next revision of that PCB, not on this one.
[Report it](../../reference/known-limitations.md#report-a-finding) with the PCB (which one of the two), the
stage, what was found, and what was done on the PCB.  A bodge on a v1.0 PCB is reported the same way.

## More to measure on the first PCBs of a revision

The design reviews left measurements for the first PCBs that work.  They take a scope, a thermal camera or an
electronic load, and serve the next revision: a rack runs without them.

| PCB | Measure |
|---|---|
| Power hub | the negotiation at plug-in on two or three chargers (a 140 W EPR one, a 100 W, a 65 W), which see the hub's ≈ 150 µF on VBUS: a charger that refuses it gets C8, the 100 µF can, left off; the VHV pin of the PD controller, rated 32 V, at plug-in, through the step to 28 V on a build that asks for EPR, and when a loaded row is cut: stay at 20 V if it passes 31 V; the 3.3 V regulator's temperature through a long Wi-Fi transfer in the closed box; the VRACK copper's temperature at the full 5 A, with a thermal camera on the bottom face; a row shorted at the end of its lead: its output not below −0.3 V, the other rows unaffected |
| Bay node | the margin of F1, the camera's fuse, in a warm rack with the camera and its light on; the 3.3 V load step; the I²C rise time with a DATA ×4 on the lead.  Under 300 ns, the bus can be built at 400 kHz ([i2c-400k.overlay](../../../firmware/bay-node/i2c-400k.overlay)); it runs at 100 kHz by default |
| Camera pod, DATA ×6, DATA ×4 | the stage *Later* of each checklist |

The reviews' own lists: [the datasheet audit](../../datasheet-audit.md#bring-up-checks),
[the DATA ×4's audit](../../datasheet-audit-data-x4-v2.md#main-checks-at-bring-up),
[the schematic review](../../schematic-review-2026-10-25.md#bring-up-added), and
[Bring-up measurements](../../electronics.md#bring-up-measurements) of the electronics log, whose DATA rows
describe the design before v1.0.
