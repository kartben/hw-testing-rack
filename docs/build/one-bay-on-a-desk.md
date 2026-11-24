# One bay on a desk

One bay can live out of the rack: the bay node and a DATA ×4 in a printed box, the Quad, fed by a USB-C PD
trigger module in place of the power hub, with the rack's board plate in a desk frame in front of it.  It
takes no ladder, no tray, no row cable and no hub, and it uses two of the rack's PCBs: a way to try them before
a rack's worth of everything is bought.

:::{status} designed
The boxes and the frame were checked on exact solids, every PCB in and every plug plugged, and sliced in
Bambu Studio on 2026-10-21.  None has been printed, and no bay node has been powered from a PD trigger
module.  [What exists today](../plan/status.md#status-standalone).
:::

## Which pages of the main line apply

The stages of [The build, stage by stage](../plan/stages.md) hold, with fewer pages:

1. [Order the PCBs](../plan/order-the-pcbs.md): one bay node and one DATA ×4, with its logic or as a base.  No
   power hub, no DATA ×6.  The order of 2026-11-11 was five bare PCBs of each design, two of them assembled:
   an order like it leaves a spare of each.
2. Buy the parts of the tables below, and a USB-C charger that offers 20 V at 30 W or more.
3. [Measure before you print](../print/index.md): the PD trigger module.  Then print
   `standalone_quad_base` upright, `standalone_quad_lid` top face down, `standalone_quad_shelf` and
   `standalone_desk_frame` flat, all in PETG with no supports, and the board plate and the pegs your board
   needs ([Get the STL files](../print/stl-files.md)).
4. [Build or download the firmware](get-the-firmware.md): the bay node's image only.
5. [Solder the connectors](solder-the-connectors.md) of the DATA ×4, then
   [the bay node's checklist](check-the-pcbs/bay-node.md) up to its fourth stage and
   [the DATA ×4's](check-the-pcbs/data-x4.md).  The steps that cannot be undone are those of
   [the table](index.md#what-cannot-be-undone) that fall on these pages.
6. Assemble the Quad, below.

Row cables, trays, the frame, the power box and bringing a rack online do not apply.

## Two boxes and a frame

`mechanical/parts/standalone.scad` draws two boxes and one accessory:

| | PCBs | Outside, W × D × H, on its feet | Printed (Bambu Studio, H2D, 0.20 Standard, PETG, no supports) |
|---|---|---|---|
| **Quad** | the bay node and a DATA ×4 | 107 × 95.5 × 96.1 mm | base, shelf and lid on one plate: 135 g, 5 h 14 |
| **Desk frame** | none: the rack's board plate, the boards on its pegs | 142.8 × 190.8 × 8.5 mm | frame and plate on one plate: 85 g, 4 h 01 |
| **Solo** | the bay node and the single DATA port PCB | 106 × 95.5 × 33.6 mm | [do not build it](#the-solo) |

The print figures are Bambu Studio's of 2026-10-21, before the Quad's front took a window over the DATA ×4's
SWD header on 2026-11-02; the bill of materials below estimates less filament, from the parts' volume.

```{figure} ../../electronics/data-port-x4/docs/data-port-x4-iso.jpg
:alt: KiCad render of the DATA ×4, its four USB-C receptacles along one edge, a pin header above each
:width: 60%

KiCad render of the DATA ×4 v1.0.  In the Quad it stands behind the front face, its four USB-C through the
face and each 2 × 6 header under a window of its own.
```

In the Quad the DATA ×4 stands in two side slots on the floor; a Dupont housing plugs into each header
through its window, and D1 and the SWD header J2 sit behind one more, so a debug probe's lead plugs in from
the front.  Its VBUS LEDs show through windows, and the port numbers 1 to 4 are debossed on the face.  The node lies on a shelf over it, front edge forward: the PC port, SERVICE and the status LED are
at the top of the front face, as on a tray's fascia.  The shelf rests 0.5 mm over the DATA ×4's top edge, so
the board cannot lift out.  The lid has pin holes over RESET and BOOT and a window over J6, the camera's
socket; the right wall has a slot for an AUX lead.  Not drawn: a mast for a camera pod over the desk frame, a
blank for the header windows, and any box for a DATA ×6.

## What to print, buy and order

Besides the PCBs of step 1 above and the DATA ×4's loose connectors
([Shopping list and tools](../plan/shopping-list.md#the-connectors-the-fab-leaves-off)), the bill of materials
lists the Quad's lines, then the desk frame's.  The Quad comes to:

```{include} ../../bom/README.md
:start-after: "**Quad (the node + the DATA ×4 v2)**: "
```

The pegs for your board come out of `tools/plate_layout.py`, as for a drawer:
[Put a board in a bay](../use/mount-a-board.md).

## Power from a PD trigger module

The module is a bought CH224K board with a DIP switch: set the switch to **20 V**.  It feeds the node's J1,
ROW IN, through a two-wire lead that you make (step 2 below).

| J1 pin | Wire | Module |
|---|---|---|
| 1, VRACK | red | + |
| 2, GND | black | − |

The charger must offer 20 V at 30 W or more.  A DATA ×4 with every port at its limit draws 0.92 A at 20 V,
about 18 W; the node draws 1.8 W, and 2.5 W more with a camera.  With no hub to grant it power, the node holds
the DATA lead under 25 W (`CONFIG_BAY_PORTS_LIMIT_MW`)
([Specifications](../reference/specifications.md)).

* 12 V and 9 V do not start the node: its 5 V buck needs 13.5 V.
* 15 V starts the node, and the sources say it works.  On v1.0 that is to be verified: the eFuse on the DATA
  lead locks out under 15 V, and the firmware switches the lead off again when it reads less than 15 V there
  (`CONFIG_BAY_DATA_VIN_MIN_MV`).  At a 15 V contract the DATA ×4 may stay off.
* A charger without PD, or without the voltage asked for: count on the module staying at 5 V, since its
  fallback is not documented.  The node then stays off and nothing is harmed.

The seller gives no size.  The boxes are drawn for the largest board the photos allow, 30 × 21 × 1.6 mm, and a
smaller one fits them as committed, as long as its USB-C stands 0.6 to 2 mm proud of its PCB's edge.  Measure
the module you bought before the base is printed; a larger one goes into `config/rack.yaml` › `standalone.pd_module` (its PCB's length and width, its thickness, the USB-C's
axis off its back face), and the seat and the collar follow ([Measure before you print](../print/index.md)).

## Assemble the Quad

:::{build-step} 1
:hardware: M3 heat-set insert=8

**Inserts**: four in the shelf's bosses, four in the base's corner bosses.
:::

:::{build-step} 2
:parts: JST PHR-6 housing=1, SPH-002T-P0.5S contact=2, 24 AWG wire 15 cm=2

The **PD lead**.  Crimp a contact onto one end of each wire, as for
[the feeds](row-cables.md#make-the-feeds) ([a crimp cannot be undone](index.md#crimp)).  Click the red wire's
contact into position 1 of the housing and the black one's into position 2: position 1 is the end towards
the node's rear edge, the edge with the ESP32-S3 module's antenna, once the housing is in J1
([the bench lead](row-cables.md#a-two-wire-lead-for-the-bench) is made the same way).  Solder the red wire to
the module's + output pad and the black one to its − pad.
:::

:::{build-step} 3
:parts: PD trigger module=1, Foam pad 1 mm=1

**PD module**, its DIP switch at 20 V, on its long edge against its low wall at the rear left, its back face
on the foam pad.  Its USB-C goes into the rear wall's collar, its far end behind the fence.  The DIP switch
faces into the box: it can be changed only while the lid is off.
:::

:::{build-step} 4
:parts: DATA ×4=1, JST PH 8 lead 15 cm=1

The **DATA lead** into the DATA ×4's J1 first, then the board down into its side slots, USB-C forward.  The
lead is the rack's DATA lead at 15 cm, "Same direction": pin n meets pin 9 − n.
:::

:::{build-step} 5
:parts: Bay node=1
:hardware: m3x8=4

**Node** onto the shelf, four M3 × 8.  The PD lead into J1, the DATA lead into J7.  Then the shelf onto its
ledges.
:::

:::{build-step} 6
:hardware: m3x8=4, Rubber bumper Ø10 × 3=4

**Lid** on, four M3 × 8.  The four bumpers into their pockets under the base.
:::

:::{build-step} 7
:parts: Desk frame=1, Board plate=1

The **plate** into the desk frame's pocket, over its two pins, its pegs and your board on it as in a drawer.
Then the box's two front feet down through the slots of the frame's dock, to the desk.  Lift the box to undock
it.
:::

(the-solo)=
## Do not build the Solo with a node v1.0

The Solo pairs the node with the single DATA port PCB, which left the rack on 2026-10-31 and was not among the
PCBs ordered on 2026-11-11.  That PCB wires pin 8 of its lead straight to its USB-C's VBUS and expects 5 V
there.  A node v1.0 puts DATA_VIN, the 20 V of the module, on pin 1 of J7, and a "Same direction" lead lands
pin 1 on pin 8: the board in the Solo would get 20 V on VBUS.  Its old description still calls them "the same
boards", and its STL files are still built.  Until a Solo is redrawn for a DATA board of v1.0, it has no recipe
here ([Known issues, and what will not work](../reference/known-limitations.md#open-questions)).

## Flash and first use

The node is flashed in its box as on the bench, with the module in place of the bench supply: SERVICE on, a
laptop on the PC port, `west flash -d build-bay`, SERVICE off ([Flash a node](flash.md#flash-a-node)).
Stage 5 of the node's checklist needs a hub: skip it.  Leave the module's one-time fuse: the checklist burns it
only on a node that goes into a rack, and a node whose fuse is never burnt is not harmed
([The module's one-time fuse](flash.md#the-modules-one-time-fuse)).

Without a hub, J1's POS pin stays low: the node never takes a rack address and never transmits on CAN.  It
answers as `bay<MAC>.local` until it is given an id, which it keeps:

```console
uart:~$ bay id b3
```

It is then `bay-b3.local`, the name the bay in place B3 of a rack has.  `bayctl` runs without a hub when
`BAYCTL_HUB=none` says so, and then reads the bays from `config/lab.yaml`
([Set up bayctl and usbip](../use/set-up-your-machine.md)).  From there,
[A first session with a bay](../use/first-session.md) follows B3, a DATA ×4 bay like this one.

A step that is wrong: [report it](../reference/known-limitations.md#report-a-finding).
