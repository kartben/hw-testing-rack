# Power box and charger

The power hub sits in a printed box in the base cell under A1. One USB-C PD charger, outside the rack, plugs
into the box's rear wall, and one feed per row leaves its left wall for the row's first node.

:::{status} designed
The box has not been printed, and no charger has been tried on a hub. What each LED shows below is read from
the hub's schematic and from its firmware, which builds and has not run on a hub.
[What exists today](../plan/status.md#status-pd).
:::

```{figure} ../img/viewer/power-box-under-a1.jpg
:alt: The power box in the base cell under bay A1, seen from the front left, with three cables climbing the rack's left side
:width: 90%

The 3D model. On the box's front wall: an ON and a FAULT LED over each row's letter, PD, then CTL beside the
console USB-C. The row feeds leave the left wall through the base ladder's window and climb the rack's left
side; the charger's cable leaves at the rear.
```

## What you need

- The power hub, after [its checklist](check-the-pcbs/power-hub.md): flashed, its Wi-Fi network typed at
  stage 4, its module's one-time fuse burnt at the last stage. Leave the hub unnamed unless you run several
  racks on one network: [Bays, ports and addresses](../use/names.md) says what `hub id` changes.
- The printed base and lid (`power_box_base`, `power_box_lid`).
- 4 M3 heat-set inserts, 4 M3 × 12 male-female hex spacers, 4 M3 × 8 pan head screws.
- The charger and its cable ([below](#charger-and-cable)).
- The row feeds, made and rung out on [Make the row cables](row-cables.md): three for the default rack.
- An insert iron if the four inserts are not in yet, a Phillips screwdriver, pliers for the spacers.

## The hub into its box

:::{build-step} 1
:drawing: c0
:alt: The empty box seen from above, an insert over each of its four standoffs
:parts: pb=1
:hardware: insert=4

Heat-set the 4 inserts into the hub's standoffs, from above, if
[Inserts and square nuts](../print/inserts-and-nuts.md) did not already. The box is open: the iron reaches
each standoff, 13.6 mm down and 4.7 mm or more from the walls.
:::

:::{build-step} 2
:drawing: c1
:alt: The hub lowered into the box, a hex spacer over each of its four holes
:parts: hb=1
:hardware: sp12=4

Lower the **hub** straight in, its USB-C PD input towards the rear wall, its four row sockets towards the
windows of the left wall. Screw the 4 hex spacers through its holes into the inserts, by hand or with pliers:
the row connector next to the front-left hole leaves no room for a 5.5 mm socket.
:::

:::{build-step} 3
:drawing: c2
:alt: The lid coming down on the box, four screws over the spacers
:parts: pl=1
:hardware: m3x8=4

**Lid** on, its rim inside the walls: 4 × M3 × 8 into the tops of the spacers. Its two pin holes, RST and
BOOT, stand over the hub's two buttons.
:::

## The box under A1

:::{build-step} 4
:drawing: c3
:alt: The closed box sliding into the base cell under the first bay, its four row windows towards the left ladder

Lift the box over the floor plate's front lip under A1 and let its sockets drop over the bosses. It sits
against the cell's left side and locates without screws; an M3 through each socket screws it down if wanted.
:::

Once it is in:

| Wall | What |
|---|---|
| Left | the windows of the four row outputs, the row's letter (A to D) above each, reached from the rack's left side through the base ladder's window |
| Front | an ON and a FAULT LED per row with the row's letter under them, the PD LED, then the CTL LED and the console USB-C over the label CTL |
| Rear | the USB-C PD input (PD IN) and vents |
| Lid | vents, and the two pin holes RST and BOOT |

The console USB-C is the hub's shell and its flashing port; it stays in reach with the box closed
([Power hub shell](../reference/hub-shell.md)).

## Charger and cable

```{include} ../reference/specifications.md
:start-after: <!-- site:charger-table -->
:end-before: <!-- /site:charger-table -->
```

Buy the default: a 140 W charger brings nothing more today, since the hub's default build never asks for 28 V.

:::{build-step} 5
:drawing: c4
:alt: Rear view of the base cell: the charger's cable passing through the base brace into the box's rear port
:parts: ch=1
:hardware: usbc=1

The charger's 5 A e-marked **USB-C cable** into PD IN, on the box's rear wall, out of the back through the
base brace. Do not plug the charger into the mains yet.
:::

## First plug-in, rows unplugged

Leave the row windows empty, plug the charger in and watch the front wall.

1. The hub's PD sink asks the charger for 9 V by itself. **PD** lights. It is on while the sink reports a good
   contract, with or without firmware.
2. The firmware asks for 20 V. **CTL** blinks slowly, once a second, until that contract is final.
3. Once the 20 V contract has held half a second, the rows come on one after the other, 0.3 s apart: the green
   **ON** LED lights over A, B, C, then D. The hub has four outputs and switches all four; the default rack
   leaves D empty.
4. **CTL** goes steady.

Before a row is connected the box must show PD on, the four ON LEDs on, no red FAULT LED and CTL steady.
Every pattern, from [LEDs, buttons and switches](../reference/leds-and-buttons.md):

```{include} ../reference/leds-and-buttons.md
:start-after: <!-- site:power-box-leds -->
:end-before: <!-- /site:power-box-leds -->
```

If PD stays dark, the charger made no PD contract: try another charger before suspecting the hub. If PD is
on and no ON LED lights, the hub has no firmware or a contract under 15 V, and the rows stay off; `hub status`
and `hub pd`, on the console USB-C, show the contract and what the charger offers. A 3 A cable changes no LED:
the contract is 20 V × 3 A, and `hub pd` is where it shows.

## Now the row feeds

Unplug the charger first. A row cable is plugged with its row off (finding BN-04 of the
[review of 2026-11-09](../pcb-review-2026-11-09.md), computed, not measured).

:::{build-step} 6
:drawing: c5
:alt: A six-wire cable from a window in the box's left side, through the base ladder, up to the node of the bay above
:hardware: feed=3

One **feed** per row. Its black end goes into the row's window in the box's left wall, through the left base
ladder's window; the letter is above each window. The feed runs forward along that ladder's outer face,
climbs the rack's left side tied to the ladders, and enters the row's first bay through its left window. Its
red end goes into that node's J1 (ROW IN).
:::

Out to the left and back in from the left, a feed takes a half turn along the way: let the bundle turn as
one. Row A takes the feed of 305 mm leads, row B the 60 cm one, row C the 80 cm one. The bill counts no cable
tie for the feeds and no source places them: the route is the one [the 3D model](/viewer/) draws.

Plug the charger in again. Each row comes up through its eFuse's soft start, and each node sees one clean
power-up.

## Check before you go on

- [ ] PD on, CTL steady, no red FAULT LED.
- [ ] The ON LED of every row lit.
- [ ] The LED of every bay lit, on the left of its fascia. A dark one has no power or no firmware.

A red FAULT LED or a CTL that blinks: [Troubleshooting](../use/troubleshooting.md).

Found a step that is wrong? [Report a finding](../reference/known-limitations.md#report-a-finding).
