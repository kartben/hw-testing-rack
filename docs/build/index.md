# Tools, and what cannot be undone

PCBs not ordered yet? [Order the PCBs](../plan/order-the-pcbs.md) first: of the pages in this section, only
[the firmware](get-the-firmware.md) and [the row cables](row-cables.md) can be done without them.  The whole
build in order, from the first parcel to the first board in a bay:
[The build, stage by stage](../plan/stages.md).

:::{status} designed
Nobody has built a BitBunk.  The frame (v0.2) has not been printed as a whole, the five PCBs (v1.0) have been at
the fab since 2026-11-11, and every step in this section is written from the 3D model and the schematics.
[What exists today](../plan/status.md) says what was checked, and on what.
:::

## Tools and bench equipment

```{include} ../plan/shopping-list.md
:start-after: <!-- site:tools -->
:end-before: <!-- /site:tools -->
```

## What cannot be undone

Seven steps of the build have no way back.

| Step | Where it falls | Why it cannot be undone |
|---|---|---|
| [A heat-set insert in the wrong boss]{#insert} | [Inserts and square nuts](../print/inserts-and-nuts.md) | It is melted into the plastic.  In a floor plate's boss that takes a bench screw, it stops the screw. |
| [A connector soldered on the wrong face]{#solder} | [Solder the connectors](solder-the-connectors.md) | Eight through-hole joints for a DATA board's lead socket, twelve for each pin header of a DATA ×4, in a four-layer PCB: check the face and the direction before the first one. |
| [A crimp]{#crimp} | [Make the row cables](row-cables.md) | A crimped contact does not open again; a bad one is cut off with its end of the wire.  The bill buys 50 contacts for the 24 of the two crimped feeds: the first crimps go wrong. |
| [Glued magnets]{#magnets}, with `drawer.detent: magnet` only | [The frame and the first bay](first-bay.md#a-rear-cover-and-detent-magnets-both-optional) | A drop of CA holds each magnet in its pocket, and the two must attract: stack the pair and mark both outer faces before the glue. |
| [The module's one-time fuse]{#fuse}, `DIS_USB_OTG_DOWNLOAD_MODE` | The command: [Flash the hub and the nodes](flash.md).  The moment: "6. Last" of [the hub's](check-the-pcbs/power-hub.md) and [the node's](check-the-pcbs/bay-node.md) checklists | A one-time-programmable bit of the ESP32-S3 module.  Burn it last, on a PCB that passed everything else, and only on a PCB that goes into the rack.  Never burn `STRAP_JTAG_SEL`. |
| [`west flash --erase` on a hub or a node that was set up]{#erase} | [Flash the hub and the nodes](flash.md) | It wipes what the PCB had saved, its Wi-Fi credentials among it ([what a node and a hub remember](../use/recover.md)).  It is for a module that ran other firmware, once. |
| [A node screwed to its tray with no Wi-Fi credentials]{#wifi} | Stage 4 of [the node's checklist](check-the-pcbs/bay-node.md); [Fit out a tray](fit-out-a-tray.md) | An image taken from CI carries none.  They are then typed on the UART pads, which are on the node's bottom face, under it once it is on its standoffs.  The other way back: flash an image built with your own `wifi.conf` through the front port ([Build or download the firmware](get-the-firmware.md)). |

## The drawings

The line drawings beside the steps are the assembly notice's ([tools/notice](../../tools/notice/README.md)),
made from the same 3D models as the printed parts and last drawn on 2026-10-20.  The design has moved since:
the ladders take square nuts where the notice shows inserts, every M3 screw is an M3 × 8 and every PT 2.6 × 8 a
PT 2.3 × 8, the drawer's front is a part of its own, and the DATA board stands in a cradle.  A step shows a
drawing only where it still matches the parts; otherwise it has none, or a still of the 3D model whose caption
says so.  Screw names and counts are the [bill of materials](../reference/bill-of-materials.md)'s, never the
notice's.  The standing of each of the notice's 33 steps is on
[Regenerate the site, the 3D viewer, the renders and the drawings](../engineering/tools.md#the-assembly-drawings-step-by-step).

```{figure} ../img/notice/cover.svg
:class: bb-lineart
:alt: Line drawing of one assembled bay: base ladders, row ladders, a tray with its drawer, the cap plate on top

The notice's cover, as drawn on 2026-10-20.  The frame is today's.  The drawer is not: it has a one-piece
front, and the DATA board of that date lies flat at its back.
```

Found a step that is wrong?  [Report a finding](../reference/known-limitations.md#report-a-finding).
