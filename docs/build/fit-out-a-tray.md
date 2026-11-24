# Fit out a tray

A tray is the part that slides into the frame for each bay. It carries the bay node, the drag chain and the
drawer. Fit out every tray at the bench: once a tray is in the frame, you cannot reach the screws that go down
through its guide lips.

## Which steps your bay needs

Every bay uses the same tray. What goes into it depends on the kind of bay you chose for that place in
`config/rack.yaml` ([Choose your rack's size](../plan/choose-your-rack.md)).

| Kind of bay | In `config/rack.yaml` | Steps |
|---|---|---|
| A drawer with a DATA ×6 | the default | 1 to 11 |
| A drawer with a DATA ×4 | `boards:` | 1 to 11 |
| A dense bay, boards on edge | `plate: slots` | 1 to 11, then [a slot bin](#a-dense-bay-with-a-slot-bin) later |
| A sled bay, no drag chain | `mount: sled` or `fixed` | 1, then [the sled bay's steps](#a-sled-bay-without-a-chain) |

[The 3D model](/viewer/?bay=B3&openbay=1) shows each kind in its place.

## Parts for one drawer bay

* The printed tray, drawer, drawer front, chain anchor, chain foot, cradle (`x4_cradle`) and strip
  (`x4_strip`), with their threaded inserts fitted ([Fit the inserts and nuts](../print/inserts-and-nuts.md)).
* A bay node that passed [its checks](check-the-pcbs/bay-node.md). Set its Wi-Fi credentials first: after
  step 1 you cannot reach its UART pads.
* A DATA ×6 or a DATA ×4, with its lead socket soldered ([Solder the connectors](solder-the-connectors.md)).
* A DATA lead (JST PH 8, 50 cm) that you have rung out ([Make the row cables](row-cables.md)). Twist its D+
  and D− wires together by hand: pins 3 and 4 at the node end.
* About 180 mm of drag chain, with its two end pieces: the chain you measured before you printed the tray
  ([Parts to measure before you print](../print/index.md#parts-to-measure-before-you-print)).
* 9 M3 × 8, 4 M2.5 washers and 13 PT 2.3 × 8 (thread-forming screws for plastic).
* A magnetic PH1 bit on a shaft no thicker than 5 mm, and a screwdriver with a shaft of 60 mm or more.

The board plate and your boards go in later, once the rack is online
([Put a board in a bay](../use/mount-a-board.md)).

## Fit the node and the drag chain

:::{build-step} 1
:drawing: t1
:alt: The node on the tray's standoffs, a screwdriver through the hole of the left guide
:parts: tr=1, nd=1
:hardware: m3x8=4

Screw the **node** onto the tray's four standoffs with four M3 × 8. The two left screws sit under the left
guide: hold each one on the magnetic bit and drive it through the hole in the guide.
:::

:::{build-step} 2
:drawing: a9b
:alt: The chain's two end pieces screwed to the anchor block and to the foot's fin
:parts: dc=1, an=1, ft=1
:hardware: pt23x8=4, w25=4

Cut the **drag chain** to about 180 mm, end pieces included. Screw the fixed end piece to the chain anchor,
and the moving end piece to the fin of the chain foot. Each takes two PT 2.3 × 8 with washers, the tab
against the flat face of the part.
:::

:::{build-step} 3
:drawing: a10o
:alt: The chain's links open, the lead laid in them, a plug out of each end
:parts: xt=1

Snap open the links of the chain. Lay the **DATA lead** in from end to end, then snap the links shut. Leave
the spare length at the fixed end, never in front of the moving end.
:::

:::{build-step} 4
:drawing: t2
:alt: The anchor screwed to the tray, the chain in a U along its rails, the lead's plug going into the node
:hardware: m3x8=2

Screw the **chain anchor** to the tray with two M3 × 8, the chain lying along the tray's rails. Plug the lead
into J7 (DATA), on the right edge of the node. J6 (CAM), at the rear right, takes the same plug, but the DATA
board gets no power from it.
:::

(the-drawers-front-then-the-data-board)=
## Fit the front and the DATA board

:::{build-step} 5
:drawing: d1
:alt: The front coming onto the drawer's walls, a screw behind the post at the front end of each side wall
:parts: Drawer=1, Drawer front=1
:hardware: pt23x8=2

Screw the **front** onto the drawer with one PT 2.3 × 8 on each side. Drive each screw from inside the
drawer, through the post at the front of the side wall. Leave the window in the front empty.
:::

:::{build-step} 6
:drawing: d2
:alt: The cradle coming down onto the three bosses of the drawer's rear bay, a screw over each boss
:parts: Cradle (x4_cradle)=1
:hardware: m3x8=3

Screw the **cradle** onto the three bosses at the back of the drawer with three M3 × 8.
:::

:::{build-step} 7

Route the **DATA lead**. The drawer is not on the tray yet: it slides on in step 10.

From the moving end of the chain, run the lead forwards. Bend it straight back in a flat U, between the two
runs of the chain. Lift the front of the U by about 4 mm, so that it passes over the row jumper that will
cross the front of the tray. Run the lead back low over the tray's floor and up through the cable window at
the rear right of the drawer.
:::

:::{build-step} 8
:drawing: d3
:detail: latch
:alt: The lead going into J1 on the back of the DATA ×6, the board going down into the cradle; in the circle, a latch over its top edge
:parts: DATA ×6 or DATA ×4=1

Plug the lead into J1 on the back of the **DATA board**. Slide the board down into the cradle, receptacles
towards the port wall, until both latches click.
:::

:::{build-step} 9
:drawing: d4
:alt: The strip coming down onto the comb in front of the DATA ×6, five screws over it
:parts: Strip (x4_strip)=1
:hardware: pt23x8=5

Lay the **strip** on the cradle's comb, over the receptacles. Drive five PT 2.3 × 8 from above, with the long
screwdriver between the port wall and the board. The strip keeps the pull of a cable off the solder joints.
:::

A DATA ×4 goes in the same way. Its four ports sit in slots 2 to 5 of the port wall, and its pin headers face
forwards for the Dupont wires to your boards ([Wires between boards](../use/wires.md)).

## Glue the detent magnets, if you chose them

The drawer is held closed by a detent: a printed tab in the tray's left ledge, which holds with about 3 N. For
a firmer hold, about 10 N, you can use two 6 × 3 mm magnets instead. Set `drawer.detent: magnet` in
`config/rack.yaml`, then regenerate and print the tray and the drawer
([Get the STL files](../print/stl-files.md)). Each of them then has a pocket for one magnet.

Glue the magnets before step 10. Glue cannot be undone, so mark the faces first:

1. Stack the two magnets and mark both outer faces.
2. Glue each magnet into its pocket, marked face down, with a drop of CA gel. The two bare faces must
   attract.
3. Let the glue set.

## Slide the drawer onto the tray

:::{build-step} 10
:drawing: t3
:alt: The drawer sliding onto the tray's ledges from the front, a screw at the chain foot
:hardware: pt23x8=1

Slide the **drawer** onto the tray's ledges from the front. Its rear flange goes under the guide lips, and the
chain foot goes into the groove at the back of the drawer. Lock the foot with one PT 2.3 × 8, driven from
inside the back of the drawer.
:::

:::{build-step} 11
:hardware: pt23x8=1

Drive the **stop screw**, one PT 2.3 × 8, down through the left guide lip. The drawer now stops on it when
you pull it out 140 mm.
:::

Label the drawer once you know which bay it goes in. A printed `bay_label_<bay>`, or a strip of 12 mm label
tape, goes in the recess on the left of the front.

```{figure} ../img/viewer/a4-fitted-tray.jpg
:width: 70%
:alt: A drawer of the 3D model pulled out: the DATA ×6 standing in its cradle behind the port wall, the drawer's floor and the front's window empty

The 3D model: a fitted tray in the frame, its drawer out. The node lies under the back of the drawer.
```

## A dense bay, with a slot bin

A dense bay (`plate: slots`) holds its boards on edge in a slot bin. Fit out its tray as a drawer bay with a
DATA ×6, steps 1 to 11. The slot bin takes the place of the board plate and goes in later, with the boards
([On edge in a slot bin](../use/mount-a-board.md#on-edge-in-a-slot-bin-with-a-data-6)). It drops onto the
drawer's two locating pins, front stop forwards, and fits one way round only.

## A sled bay, without a chain

A sled bay (`mount: sled`) has no drag chain. A port block at the back holds the DATA board and stays locked
in the tray. The sled in front slides out about 110 mm once you unplug the board's cable. Fit the node as in
step 1, then follow these steps in place of steps 2 to 11.

:::{build-step} 1
:name: sled-1
:parts: Port block (drawer_block)=1, Cradle (x4_cradle)=1
:hardware: m3x8=3

Screw the **cradle** onto the three bosses of the port block with three M3 × 8.
:::

:::{build-step} 2
:name: sled-2
:parts: xt=1, DATA ×6 or DATA ×4=1, Strip (x4_strip)=1
:hardware: pt23x8=5

Plug the **DATA lead** into J7 on the node. Run it back along the right side of the node, in the plenum (the
space under the sled). Bring it up through the window in the block and plug it into the socket on the back of the
DATA board. Slide the board into the cradle until both latches click, then screw on the strip with five
PT 2.3 × 8, as in step 9.
:::

:::{build-step} 3
:name: sled-3
:hardware: pt23x8=2

Slide the **block** to the back of the ledges, its flanges under the guide lips. Lock it with two PT 2.3 × 8
down through the guide lips. Coil the spare lead in the plenum.
:::

:::{build-step} 4
:name: sled-4
:parts: Sled (drawer_sled)=1, Drawer front=1
:hardware: pt23x8=3

Screw a drawer front onto the **sled** as in step 5. Slide the sled onto the ledges in front of the block,
then fit the stop screw as in step 11.
:::

A fixed bay (`mount: fixed`) is a sled bay screwed shut. Drive two more PT 2.3 × 8 down through the guide lips
into the sled's flanges. A sled bay takes 10 PT 2.3 × 8 in all, a fixed bay 12.

## Check before you go on

- [ ] The node's four screws are in, the two left ones through the holes in the guide.
- [ ] The lead is plugged into J7 (DATA), not into J6 (CAM).
- [ ] Both latches of the cradle are over the top edge of the DATA board, and the strip's five screws are in.
- [ ] The drawer runs out 140 mm and stops on its screw. The chain's U-bend rolls forward 70 mm, and the lead
      does not drag, kink or snag.
- [ ] The detent holds the drawer closed.
- [ ] The spare lead lies beside the node, not in front of the moving end of the chain.
- [ ] Every screw in the guide lips is in: the stop screw, and in a sled bay the two that lock the block.
