# Power box and charger

The power box holds the power hub, which feeds the whole rack from one USB-C charger. The box sits under bay
A1. The charger plugs into its rear. One cable per row, the {term}`feed`, leaves its left side and runs to
the first bay of that row.

```{figure} ../img/viewer/power-box-under-a1.jpg
:alt: The power box under bay A1, three cables climbing the rack's left side
:width: 90%

The 3D model. The LEDs and the console USB-C are on the front. The row feeds climb the rack's left side.
```

## What you need

- The power hub, flashed and on your Wi-Fi network ([Check the power hub](check-the-pcbs/power-hub.md)).
- The printed `power_box_base` and `power_box_lid`.
- 4 M3 heat-set inserts, 4 M3 × 12 male-female hex spacers, 4 M3 × 8 screws.
- The charger and its cable ([Choose the charger](#choose-the-charger)).
- One feed for each row of your rack ([Make the row cables](row-cables.md)).

## Put the hub in its box

:::{build-step} 1
:drawing: c0
:parts: pb=1
:hardware: insert=4

Heat-set the 4 inserts into the standoffs. Skip this if you did it with the other inserts
([Fit the inserts and nuts](../print/inserts-and-nuts.md)).
:::

:::{build-step} 2
:drawing: c1
:parts: hb=1
:hardware: sp12=4

Lower the **hub** in, with its USB-C input towards the rear wall and its row sockets towards the left wall.
Screw the 4 spacers through its holes into the inserts. Turn them by hand or with pliers: a 5.5 mm socket
does not fit next to the row connector.
:::

:::{build-step} 3
:drawing: c2
:parts: pl=1
:hardware: m3x8=4

Put the **lid** on and drive 4 M3 × 8 into the spacers. Its two pin holes, RST and BOOT, are over the hub's
buttons.
:::

:::{build-step} 4
:drawing: c3

Lift the box over the front lip of the floor plate under A1. Let it drop over the bosses, against the left
side of the space under A1. It needs no screws.
:::

The USB-C port on the front is the hub's console. You use it for the hub's shell and to flash the hub
([Power hub shell](../reference/hub-shell.md)).

## Choose the charger

```{include} ../reference/specifications.md
:start-after: <!-- site:charger-table -->
:end-before: <!-- /site:charger-table -->
```

Buy the default. A 140 W charger gives you nothing more.

## Switch on with no row connected

:::{build-step} 5
:drawing: c4
:parts: ch=1
:hardware: usbc=1

Plug the charger's 5 A e-marked **USB-C cable** into PD IN. Lead it out at the back, through the base brace.
:::

Leave the row outputs empty. Plug the charger into the mains and watch the front of the box:

1. **PD** lights: the charger gives 9 V. This works even without firmware.
2. **CTL** blinks once a second while the hub asks for 20 V.
3. The rows come on one after the other: the green **ON** LEDs light over A, B, C, then D. The hub switches
   all four on, even if your rack has fewer rows.
4. **CTL** stays lit.

```{include} ../reference/leds-and-buttons.md
:start-after: <!-- site:power-box-leds -->
:end-before: <!-- /site:power-box-leds -->
```

If PD stays dark, try another charger. If PD is on but no ON LED lights, either the hub has no firmware or
the charger gives less than 15 V.

To see what the charger offers and what the hub agreed with it, type `hub pd` on the hub's console. A 3 A
cable changes no LED. The `PD:` line then shows `20.0 V / 3.00 A` instead of `5.00 A`.

## Connect the row feeds

Unplug the charger first. Connect a row only while it is off.

:::{build-step} 6
:drawing: c5
:hardware: feed

Plug the black end of the **feed** into the row's output, through the window of the left base
{term}`ladder`. Run the feed forward along the ladder, then up the rack's left side, tied to the ladders.
Bring it into the row's first bay through its left window. Plug the red end into J1 (ROW IN) on the node.
:::

Do the same for each row of your rack. Each row has its own feed:

| Row | Feed length |
|---|---|
| A | 305 mm, made of pre-crimped leads |
| B | 60 cm |
| C | 80 cm |
| D | measure the route on your rack |

Each feed makes a half turn on the way: let the bundle turn as one. [The 3D model](/viewer/) shows the
route.

Plug the charger in again.

## Check before you go on

- [ ] PD on, CTL steady, no red FAULT LED.
- [ ] The ON LED of every row lit.
- [ ] The status LED of every bay lit. It is at the front of the bay, on the left, under the drawer.

If a red FAULT LED lights or CTL blinks, see [Troubleshooting](../use/troubleshooting.md#what-the-lights-say).
