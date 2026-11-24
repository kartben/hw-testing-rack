# Fit out a tray

A tray is fitted at the bench, out of the frame: the node, the drag chain with the DATA lead laid in it, then
the drawer with its front and its DATA board.  Once the tray is in the frame, no screwdriver reaches the guide
lips' screws (the stop screw, a sled bay's locks): they sit 5 mm from the side ladder and 2.6 mm from the
drawer's wall.  The default rack takes twelve trays.

:::{status} designed
One assembled bay was checked for clashes on exact solids, the chain over the drawer's whole 140 mm stroke.
No tray has been printed, and no node or DATA board has been in one.
[What exists today](../plan/status.md).
:::

## Which tray for which bay

`config/rack.yaml` fills its twelve bays with an example of every kind.  A plain rack, a DATA ×6 on a drag
chain in every bay, reads the first row only ([Choose a size, change the layout](../plan/choose-your-rack.md)).

| Bays of the example | The tray holds | Read |
|---|---|---|
| A1, A2, A4, B2, B4 | a drawer on a drag chain, a DATA ×6 | the three sections that follow |
| B1, B3 | the same drawer, a DATA ×4 in the cradle | the same three: a DATA ×4 goes in as a DATA ×6 does |
| C1, C2, C3, C4 | the same drawer and DATA ×6; a slot bin where the board plate goes | the same three, then [A slot bin in the plate's place](#a-slot-bin-in-the-plates-place) |
| A3 | no chain: a sled, and the DATA ×6 in a port block | [step 1](#the-node-on-its-standoffs), then [A sled bay, without a chain](#a-sled-bay-without-a-chain) |

```{figure} ../img/viewer/rack.jpg
:alt: The twelve bays of the example rack, each with its label, three drawers pulled out

The 3D model of the example rack: slot bins in row C, a DATA ×4 and its wires in B1 and B3, pulled out.  The
model draws a display in every drawer front; node v1.0 cannot drive one.
```

One drawer bay takes:

* a tray, a drawer and its front, a chain anchor, a chain foot, a cradle (`x4_cradle`) and its strip
  (`x4_strip`), printed ([Parts and quantities](../print/parts-list.md)), with their inserts in: four in the
  tray's node standoffs, two where the anchor goes, three in the drawer's bosses
  ([Inserts and square nuts](../print/inserts-and-nuts.md));
* a bay node that passed [its checklist](check-the-pcbs/bay-node.md) and has its Wi-Fi credentials: its test
  pads and its UART pads are on its bottom face, out of reach from step 1 on
  ([what cannot be undone](index.md#wifi));
* a DATA ×6 or a DATA ×4 with its lead socket soldered ([Solder the connectors](solder-the-connectors.md));
* a DATA lead (JST PH 8, 50 cm) that was rung out ([Make the row cables](row-cables.md)): pin n meets
  pin 9 − n, and a 1:1 lead leaves the DATA board unpowered.  Twist its D+ and D− wires together by hand
  (pins 3 and 4 at the node's end);
* about 180 mm of drag chain with its two end pieces, the chain the tray was printed for
  ([Measure before you print](../print/index.md));
* 9 M3 × 8, 13 PT 2.3 × 8 and 4 M2.5 washers (the counts of [bom/rack-bom.csv](../../bom/rack-bom.csv) for
  one drawer bay);
* a magnetic PH bit on a shaft of Ø 5 mm or less, and a screwdriver with a shaft of 60 mm or more.

The board plate, its pegs, the board and its cable are not part of the tray: they wait until the rack answers
([Put a board in a bay](../use/mount-a-board.md)).

(the-node-on-its-standoffs)=
## The node, the drag chain and the DATA lead

:::{build-step} 1
:drawing: t1
:alt: The node on the tray's standoffs, a screwdriver through the hole of the left guide
:parts: tr=1, nd=1
:hardware: m3x8=4

**Node** onto the tray's four standoffs, four M3 × 8.  Its two left screws sit under the left guide: feed
each one through the guide's hole above it on the magnetic bit and drive it there.
:::

:::{build-step} 2
:drawing: a9b
:alt: The chain's two end pieces screwed to the anchor block and to the foot's fin
:parts: dc=1, an=1, ft=1
:hardware: pt23x8=4, w25=4

Cut the **chain** to about 180 mm, its two end pieces included.  Screw the fixed end piece to the chain anchor
and the moving one to the fin of the chain foot, each with two PT 2.3 × 8 and washers, the tab against the
part's flat face.
:::

:::{build-step} 3
:drawing: a10o
:alt: The chain's links open, the lead laid in them, a plug out of each end
:parts: xt=1

Open the chain's links: their bars snap off on both sides.  Lay the **DATA lead** in from the fixed end's
mouth to the moving end's, then snap the bars back.  Lay it in, don't thread it: its plugs are 12 mm wide and
do not pass a 7 × 7 mm channel.

The route is about 38 cm, plugs included, and the lead is 50 cm.  Leave the 12 cm of spare at the fixed end,
with the 3 cm that reach the node: it makes a wider bend there, where nothing moves.  Never leave it in front of
the chain's moving end.
:::

:::{build-step} 4
:drawing: t2
:alt: The anchor screwed to the tray, the chain in a U along its rails, the lead's plug going into the node
:hardware: m3x8=2

**Anchor** onto the tray, two M3 × 8 into its inserts, the chain along the tray's rails.  Plug the lead into
the node's DATA socket, J7, on its right edge.  J6 (CAM), at the node's rear right, takes the same plug: a lead
in the wrong one harms nothing and does nothing.
:::

## The drawer's front, then the DATA board

:::{build-step} 5
:parts: Drawer=1, Drawer front=1
:hardware: pt23x8=2

**Front** against the drawer's walls: a PT 2.3 × 8 either side, from inside the drawer, through the post at the
front end of each side wall into the front.  Each screw pulls the front onto the ends of the walls and of the
floor.

The window on the front's right is for a 1.9″ display.  Node v1.0 has no connector for one
([firmware/README.md](../../firmware/README.md#front-display-study)): leave the window empty.  No blank
exists for it, and the 48 M2 × 5 screws the bill counts are the display's.
:::

The drawer's detent is printed (a tab in the tray's left ledge, a notch under the drawer): nothing to fit.  If
you chose `drawer.detent: magnet`, glue the two magnets now and let the glue set
before step 9 ([magnets for the detent](first-bay.md#a-rear-cover-and-detent-magnets-both-optional)).

:::{build-step} 6
:parts: Cradle (x4_cradle)=1
:hardware: m3x8=3

**Cradle** onto the three bosses at the back of the drawer, three M3 × 8 into their inserts.
:::

:::{build-step} 7
:parts: DATA ×6 or DATA ×4=1

The DATA lead first: from the chain's moving end up through the cable window at the drawer's rear right, and
into the socket on the **DATA board**'s rear face (J1).  Then slide the board down into the cradle's slots,
its receptacles towards the port wall, until both latches click over its top edge.  The receptacles drop into
the U's of the cradle's comb.
:::

:::{build-step} 8
:parts: Strip (x4_strip)=1
:hardware: pt23x8=5

**Strip** on the comb, its tongues in the U's, and five PT 2.3 × 8 from above with the long screwdriver,
between the port wall and the board.  The strip closes the U's over the receptacles: a cable pulled any way
then bears on the cradle, not on the receptacles' solder joints.
:::

```{figure} ../img/viewer/a4-open-data-x6.jpg
:width: 62%
:alt: A drawer pulled out of the 3D model: the DATA ×6 stands in its dark cradle behind the port wall

The 3D model, bay A4 pulled out, as after step 8: a receptacle of the DATA ×6 in each of the wall's six slots,
the strip across them, the DATA lead coming up behind the board.  The plate and its board come later; the
display in the front is not fitted.
```

A DATA ×4 (B1 and B3 of the example: the base assembly and the one with the pin matrix) goes in by steps 6 to 8
unchanged.  Its four ports stand in slots 2 to 5 of the wall's six, and its pin headers point forwards over the
port wall, for the jumper wires of [Wires between boards](../use/wires.md).  To swap one DATA board for the
other later: [Take out a tray, a node or a DATA board](../use/service-a-bay.md).

## The drawer onto the tray

:::{build-step} 9
:drawing: t3
:alt: The drawer sliding onto the tray's ledges from the front, one screw at the chain foot and one at the left lip
:hardware: pt23x8=1

Slide the **drawer** in from the front onto the tray's ledges, its rear flange under the guide lips.  The chain
foot goes into the groove at the drawer's rear: lock it with one PT 2.3 × 8 from inside the rear bay.

The drawing predates the separate front and the standing DATA board; the slide and the two screws are
today's.
:::

:::{build-step} 10
:hardware: pt23x8=1

**Stop screw**: one PT 2.3 × 8 down through the left guide lip, the other screw of the drawing above.  Pulled
out 140 mm, the drawer rests on it, its flange still under the lips.
:::

The bay's printed label, or 12 mm tape, goes in the recess on the front's left once you know which place the
tray takes.

## A slot bin in the plate's place

*Worked out from [mechanical/parts/slot_bin.scad](../../mechanical/parts/slot_bin.scad) and `drawer.slot_bin`
in [config/rack.yaml](../../config/rack.yaml): no source gives these steps, and nobody has done them yet.*

A dense bay (`plate: slots`; C1 to C4 of the example, the 120 mm row) is a drawer bay with a DATA ×6, fitted as
above.  The slot bin takes the board plate's place, and its boards stand on edge.

```{figure} ../img/viewer/c1-open-slot-bin.jpg
:width: 62%
:alt: A drawer pulled out of the 3D model, six boards on edge between the walls of a slot bin, a short cable from each to the DATA ×6 behind

The 3D model, bay C1 pulled out: six lanes, a board on edge in each, one short cable from each board to the
port straight behind its lane.
```

The bin drops onto the drawer's floor in the plate's footprint, over the drawer's two locating pins, its 12 mm
front stop towards the drawer's front and the recesses of its rear edge under the port wall's slots.  It does
not turn round.

* Six lanes of 21.0 mm run between its walls.  Lane k, counted from the left, goes with the DATA ×6's port k.
* A board stands on the edge nearer its USB connector, the connector towards the port wall.  The rack's tilt
  slides it forwards to the stop, and a thin board leans on a wall.
* A lane takes a board up to 19.8 mm thick with its parts, 86.5 mm long and 82 mm tall, on one straight 15 cm cable.
* These bays have no jumper wires: a board that needs wires goes to a bay with a plate.

The bin was checked for fit on exact solids with the drawer, the cradle, the DATA ×6, six of the largest USB
overmolds and the largest board in every lane; it was not among the parts of the
[slicer review of 2026-10-21](../printed-parts-fdm-review.md).  It goes in with the boards:
[Put a board in a bay](../use/mount-a-board.md).

## A sled bay, without a chain

A sled bay (`mount: sled`; A3 of the example, [in the 3D model](/viewer/?bay=A3&view=bay)) has no drag chain.
Its drawer is cut 1 mm in front of the port wall.  The rear part, the **port block**, holds the DATA board and
stays locked in the tray.  The front part, the **sled**, slides on the same ledges, about 110 mm, once the
board's cable is unplugged.  The tray is the drawer bays' own, without the anchor's two inserts: fit the node
as in step 1, skip the chain, then:

:::{build-step} 1
:name: sled-1
:parts: Port block (drawer_block)=1, Cradle (x4_cradle)=1
:hardware: m3x8=3

**Cradle** onto the port block's three bosses, three M3 × 8 into their inserts, as into a drawer's rear bay.
:::

:::{build-step} 2
:name: sled-2
:parts: xt=1, DATA ×6 or DATA ×4=1, Strip (x4_strip)=1
:hardware: pt23x8=5

The **DATA lead**, the same 50 cm lead: one plug into the node's J7, back along the plenum on the node's right,
up through the block's window and into the DATA board's rear socket.  Then the board down into the cradle until
both latches click, and the strip with its five PT 2.3 × 8.
:::

:::{build-step} 3
:name: sled-3
:hardware: pt23x8=2

Slide the **block** onto the ledges, to the rear, its flanges under the guide lips.  Lock it: two PT 2.3 × 8
down through the guide lips and its flanges into the ledges, at the holes level with them.  The route is about
22 cm of the lead's 50: coil the rest in the plenum.
:::

:::{build-step} 4
:name: sled-4
:parts: Sled (drawer_sled)=1, Drawer front=1
:hardware: pt23x8=3

The **sled**, with the same front as a drawer's on its two PT 2.3 × 8, onto the ledges in front of the block.
Then the stop screw, as in step 10.
:::

A bay screwed shut (`mount: fixed`) is a sled bay with two PT 2.3 × 8 more, through the guide lips into the
sled's flanges.  A sled bay takes 10 PT 2.3 × 8 in all, a fixed one 12.

## Check before you go on

The values are the design's: no tray has been fitted yet.

- [ ] The node's four screws are in, the two left ones through the guide's holes.
- [ ] The lead's plug is in J7 (DATA), not in J6 (CAM).
- [ ] Both latches of the cradle are over the DATA board's top edge, and the strip's five screws are in.
- [ ] The drawer runs 140 mm and stops on its screw.  The chain's U-bend rolls forward 70 mm, and the lead
      does not drag, kink or snag.
- [ ] Closed, the drawer is held by its detent (about 3 N).
- [ ] The lead's spare is beside the node, not in front of the chain's moving end.
- [ ] Every screw of the guide lips is in: the stop screw; in a sled bay, the block's two locks as well.

Found a step that is wrong?  [Report a finding](../reference/known-limitations.md#report-a-finding).
