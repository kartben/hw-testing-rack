# One bay on a desk

The smallest BitBunk is a single bay that sits on your desk, with no rack and no power hub. It does what a
bay in a rack does, for up to four boards.

Two PCBs sit in a printed box, the Quad: the {term}`bay node`, which runs the bay, and a {term}`DATA ×4`,
which has the USB ports for your boards. Your boards sit on a board plate in front of the box. A USB-C
charger powers the node through a small PD trigger module, which asks the charger for 20 V.

The pin wiring and the logic analyzer need a DATA ×4 with its logic. There is no mount for a camera. The
PCBs are the same as in a rack, so you can move them into a rack later.

| Part | Width × depth × height |
|---|---|
| The Quad | 107 × 95.5 × 96.1 mm |
| The desk frame, with the plate | 142.8 × 190.8 × 8.5 mm |

## What you need

- One bay node and one DATA ×4, with its logic or as the base assembly
  ([Order the PCBs](../plan/order-the-pcbs.md)), and the DATA ×4's loose connectors
  ([Shopping list and tools](../plan/shopping-list.md)).
- A USB-C PD charger that offers 20 V at 30 W or more.
- A PD trigger module (a CH224K board with a DIP switch) and a 1 mm foam pad.
- For the PD lead: a JST PHR-6 housing, two SPH-002T-P0.5S contacts, 15 cm each of red and black 24 AWG
  wire.
- A 15 cm DATA lead (JST PH 8, sold as "Same direction"), 8 M3 heat-set inserts, 8 M3 × 8 screws and 4 rubber bumpers Ø10 × 3 mm.
- A board plate and the pegs for your boards ([Put a board in a bay](../use/mount-a-board.md)).

The prints take about 170 g of PETG. The box and the frame cost about €7 in parts, without the PCBs and the
charger. [bom/README.md](../../bom/README.md) lists the Quad's parts and their prices.

## Order of work

1. Measure your PD trigger module ([Set up the PD trigger module](#set-up-the-pd-trigger-module)).
2. Print `standalone_quad_base` upright, `standalone_quad_lid` top face down, and `standalone_quad_shelf`
   and `standalone_desk_frame` flat. Use PETG, with no supports ([Get the STL files](../print/stl-files.md)).
3. Get the bay node's firmware ([Build or download the firmware](get-the-firmware.md)).
4. [Solder the connectors](solder-the-connectors.md) of the DATA ×4.
5. Check the PCBs. Do steps 1 to 4 of the [bay node's checklist](check-the-pcbs/bay-node.md), then the
   [DATA ×4's](check-the-pcbs/data-x4.md). Skip the node's step 5, which needs a hub. Do not burn the
   node's one-time fuse either: that is only for a node in a rack.
6. Assemble the Quad and name the node, as below.

Some of these steps cannot be undone. Read [Steps you cannot undo](index.md#steps-you-cannot-undo) first.

## Set up the PD trigger module

Set the module's DIP switch to **20 V**. At 15 V the DATA ×4 may stay off, and at 12 V or less the node
does not start. The module feeds the node's J1, where a row cable plugs in when the node is in a rack.

A 30 W charger is enough: the node takes 1.8 W, and it keeps the DATA ×4 under 25 W by itself. A charger
without USB PD, or without 20 V, leaves the node off and does no harm.

The base fits a module up to 30 × 21 × 1.6 mm. Its USB-C must stand 0.6 to 2 mm out from the edge of the module's PCB.
For a larger module, measure it and enter the figures under `standalone.pd_module` in `config/rack.yaml`:

| Key | What to measure | Default |
|---|---|---|
| `size` | the PCB's length, from its USB-C edge, then its width | 30, 21 mm |
| `thickness` | the PCB's thickness | 1.6 mm |
| `usb_axis` | from the PCB's back face to the axis of the USB-C | 3.2 mm |

Then build the base again before you print it:

```console
$ python tools/build.py stl --only standalone_quad_base
```

## Assemble the Quad

:::{build-step} 1
:hardware: insert=8

Heat-set four **inserts** in the shelf's bosses and four in the corner bosses of the base.
:::

:::{build-step} 2
:parts: JST PHR-6 housing=1, SPH-002T-P0.5S contact=2, 24 AWG wire 15 cm=2

Make the **PD lead**. Crimp a contact onto one end of each wire, as for a row feed
([Make the row cables](row-cables.md)). Click the red wire into position 1 of the housing and the black one
into position 2. Solder the red wire to the module's + pad and the black one to its − pad.
:::

On the node's J1, position 1 is VRACK, the supply. It is at the end towards the node's antenna. Position 2 is
GND.

:::{build-step} 3
:parts: PD trigger module=1, Foam pad 1 mm=1

Stand the **PD module** on its long edge against its low wall at the rear left, with the foam pad between its
back face and the wall. Its USB-C
goes into the collar in the rear wall, and its far end goes behind the fence. Its DIP switch faces into the
box, so you can reach it only with the lid off.
:::

:::{build-step} 4
:parts: DATA ×4=1, JST PH 8 lead 15 cm=1

Plug the **DATA lead** into the DATA ×4's J1. Lower the board into its two side slots, USB-C forward.
:::

:::{build-step} 5
:parts: Bay node=1, Quad shelf=1
:hardware: m3x8=4

Screw the **node** onto the shelf with four M3 × 8. Plug the PD lead into J1 and the DATA lead into J7. Lay
the shelf on its ledges.
:::

:::{build-step} 6
:hardware: m3x8=4, Rubber bumper Ø10 × 3=4

Screw the **lid** on with four M3 × 8. Stick the bumpers under the base.
:::

:::{build-step} 7
:parts: Desk frame=1, Board plate=1

Put your boards on the **plate** as you would in a drawer. Drop the plate into the desk frame, over its two
pins. Set the two front feet of the box down through the slots at the back of the frame.
:::

To flash the node later, use the PC port and the SERVICE switch at the top of the front face, as on a tray
([Flash the hub and the nodes](flash.md)). The lid has pin holes over RESET and BOOT.

## Name the node

In a rack, the hub names each node. On a desk, the node answers at `bay<MAC>.local` until you name it.
`bayctl` expects a bay name such as B3, so give the node one in its shell
([Bay node shell](../reference/node-shell.md)):

```console
uart:~$ bay id b3
```

The node keeps the name and answers at `bay-b3.local`. Tell `bayctl` there is no hub:

```{code-block} yaml
:caption: config/lab.yaml
hub: false
bays:
  B3:
    host: bay-b3.local
```

Check that `bayctl` finds the bay:

```console
$ python tools/bayctl.py ports B3
```

Carry on with [A first session with a bay](../use/first-session.md), which uses B3 too.
