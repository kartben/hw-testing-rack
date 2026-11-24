# Fit out a tray

A tray is fitted at the bench, out of the frame: the node, the drag chain with the DATA lead laid in it, then
the drawer with its front and its DATA board.  Once the tray is in the frame, no screwdriver reaches the guide
lips' screws (the stop screw, a sled bay's locks): they sit 5 mm from the side ladder and 2.6 mm from the
drawer's wall.  The default rack takes twelve trays.

:::{status} designed
One assembled bay was checked for clashes on exact solids, the chain over the drawer's whole 140 mm stroke.
No tray has been printed, and no node or DATA board has been in one.
[What exists today](../plan/status.md#status-bay).
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

[The 3D model](/viewer/?bay=B3&openbay=1) shows each kind in its place.

One drawer bay takes:

* a tray, a drawer and its front, a chain anchor, a chain foot, a cradle (`x4_cradle`) and its strip
  (`x4_strip`), printed ([Parts and quantities](../print/parts-list.md)), with their inserts in: four in the
  tray's node standoffs, two where the anchor goes, three in the drawer's bosses, and on a tray of row B or C four
  underneath, the mount of a camera pod in the bay below ([Inserts and square nuts](../print/inserts-and-nuts.md));
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
:drawing: d1
:alt: The front coming onto the drawer's walls, a screw behind the post at the front end of each side wall
:parts: Drawer=1, Drawer front=1
:hardware: pt23x8=2

**Front** against the drawer's walls: a PT 2.3 × 8 either side, from inside the drawer, through the post at the
front end of each side wall into the front.  Each screw pulls the front onto the ends of the walls and of the
floor.

The window on the front's right is for a 1.9″ display.  Node v1.0 has no connector for one
([Front display (study)](../firmware.md#front-display-study)): leave the window empty.  No blank
exists for it, and the 48 M2 × 5 screws the bill counts are the display's.
:::

The drawer's detent is printed (a tab in the tray's left ledge, a notch under the drawer): nothing to fit.  If
you chose `drawer.detent: magnet`, glue the two magnets now and let the glue set
before step 9 ([magnets for the detent](first-bay.md#a-rear-cover-and-detent-magnets-both-optional)).

:::{build-step} 6
:drawing: d2
:alt: The cradle coming down onto the three bosses of the drawer's rear bay, a screw over each boss
:parts: Cradle (x4_cradle)=1
:hardware: m3x8=3

**Cradle** onto the three bosses at the back of the drawer, three M3 × 8 into their inserts.
:::

:::{build-step} 7
:drawing: d3
:detail: latch
:alt: The lead coming up through the window at the rear right into J1 on the DATA ×6's rear face, the board going down into the cradle; in the circle, a latch over the board's top edge
:parts: DATA ×6 or DATA ×4=1

The DATA lead first.  Out of the chain's moving end it goes forwards and turns back at once in a flat U,
between the chain's two runs: raise the U's front about 4 mm, so that with the drawer out it passes over the
jumper lying on its tie anchors.  Then it runs back low over the tray's floor, up through the cable window at
the drawer's rear right, and into the socket on the **DATA board**'s rear face (J1).  Then slide the board down into the cradle's slots,
its receptacles towards the port wall, until both latches click over its top edge.  The receptacles drop into
the U's of the cradle's comb.
:::

:::{build-step} 8
:drawing: d4
:alt: The strip coming down onto the comb in front of the DATA ×6, five screws over it, the screwdriver on the right-hand one
:parts: Strip (x4_strip)=1
:hardware: pt23x8=5

**Strip** on the comb, its tongues in the U's, and five PT 2.3 × 8 from above with the long screwdriver,
between the port wall and the board.  The strip closes the U's over the receptacles: a cable pulled any way
then bears on the cradle, not on the receptacles' solder joints.
:::

A DATA ×4 goes in by steps 6 to 8 unchanged: its four ports stand in slots 2 to 5 of the wall's six, its pin
headers pointing forwards over the port wall for [the jumper wires](../use/wires.md).

## The drawer onto the tray

:::{build-step} 9
:drawing: t3
:alt: The drawer, its front on and the DATA board standing in its cradle, sliding onto the tray's ledges from the front, a screw at the chain foot
:hardware: pt23x8=1

Slide the **drawer** in from the front onto the tray's ledges, its rear flange under the guide lips.  The chain
foot goes into the groove at the drawer's rear: lock it with one PT 2.3 × 8 from inside the rear bay.
:::

:::{build-step} 10
:hardware: pt23x8=1

**Stop screw**: one PT 2.3 × 8 down through the left guide lip.  Pulled out 140 mm, the drawer rests on it,
its flange still under the lips.
:::

To carry a fitted tray with its drawer shut, two more PT 2.3 × 8 (the bill does not count them) go down
through the guide lips at the holes a sled bay's port block takes, level with the closed drawer's rear
flange.  Like the stop screw, they are out of reach once the tray is in the frame.

The bay's printed label, or 12 mm label tape, goes in the recess on the front's left once you know which place
the tray takes.  The label is 12 × 1.0 mm in a recess 12.4 mm tall and 0.9 mm deep; nothing in the design
holds it there, and no source says what should.

```{figure} ../img/viewer/a4-fitted-tray.jpg
:width: 70%
:alt: Bay A4 of the 3D model, its drawer pulled out: the DATA ×6 standing in its cradle behind the port wall, the drawer's floor empty, the front's window empty

The 3D model, bay A4 pulled out: a fitted tray once it is in the frame.  The DATA ×6 stands in its cradle, the
strip across its six receptacles, and the node lies under the drawer's rear.  No plate, no board, nothing in
the front's window.
```

## A slot bin in the plate's place

A dense bay (`plate: slots`; C1 to C4 of the example, the 120 mm row) is a drawer bay with a DATA ×6, fitted as
above.  Its slot bin takes the board plate's place and goes in with the boards, once the rack answers
([On edge in a slot bin](../use/mount-a-board.md#on-edge-in-a-slot-bin-with-a-data-6)).  It drops onto the
drawer's floor over the drawer's two locating pins, its 12 mm front stop towards the drawer's front and the
recesses of its rear edge under the port wall's slots; it does not turn round.  This is worked out from
[mechanical/parts/slot_bin.scad](../../mechanical/parts/slot_bin.scad); nobody has done it yet.

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

- [ ] The node's four screws are in, the two left ones through the guide's holes.
- [ ] The lead's plug is in J7 (DATA), not in J6 (CAM).
- [ ] Both latches of the cradle are over the DATA board's top edge, and the strip's five screws are in.
- [ ] The drawer runs 140 mm and stops on its screw.  The chain's U-bend rolls forward 70 mm, and the lead
      does not drag, kink or snag.
- [ ] Closed, the drawer is held by its detent (about 3 N).
- [ ] The lead's spare is beside the node, not in front of the chain's moving end.
- [ ] Every screw of the guide lips is in: the stop screw; in a sled bay, the block's two locks as well.

A step that is wrong: [report it](../reference/known-limitations.md#report-a-finding).
