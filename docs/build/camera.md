# Add a camera

A bay's camera hangs under its ceiling and looks straight down at the board: an Arducam Mega in a printed
pod, a small PCB with four white LEDs behind it, and a lead to the bay's own node.  Any bay takes one: every
ceiling, the tray above or the cap plate, has the four inserts.  A rack without cameras skips this page.

:::{status} designed
The pod was checked on exact solids with a placeholder for the camera's case.  No Arducam Mega has been on a
node or on a stand-in: the camera's firmware has run against a simulated camera only.
[What exists today](../plan/status.md#status-pod).
:::

## Parts for one camera

The bill counts two sets; the example rack shows one camera, in B2.

```{bom-table}
:category: Cameras
:columns: item, qty
```

Each camera also takes:

* a pod and a diffuser, printed: the pod in dark, opaque PETG, the diffuser in white.  The camera's case is a
  placeholder in the model, so measure the first Mega before the pod is printed
  ([Measure before you print](../print/index.md));
* a camera pod PCB that passed [its checklist](check-the-pcbs/camera-pod.md);
* a camera lead: the DATA lead's own type, JST PH 8, 50 cm, "Same direction", rung out
  ([Cables and pinouts](../reference/cables.md));
* 2 M3 × 8.

Fit the LN018 lens (145°) in the Mega first.

## The pod at the bench

:::{build-step} 1
:drawing: k1
:alt: The pod upside up, the pod PCB and the diffuser under it, two long screws coming up through both
:parts: Camera pod=1, kb=1, kd=1
:hardware: pt26x14=2

The **pod PCB** on its two standoffs behind the sleeve, LEDs down, its LED edge against the baffle.  The
**diffuser** under it: two PT 2.6 × 14 up through the diffuser's posts and the PCB.
:::

```{figure} ../../electronics/camera-pod/docs/camera-pod-top.jpg
:alt: The face of the camera pod PCB that carries its parts
:width: 45%

KiCad render of the camera pod v1.0, the face that looks down: the four LEDs along the edge that goes against
the baffle, J1 for the lead on the right edge, and J2 with the name of each of its six pins.
```

## The pod under the ceiling, the camera in its sleeve

:::{build-step} 2
:hardware: m3x8=2

Pull the bay's drawer out: a closed drawer and its board's cable leave no room for a hand.  The **pod** under
the ceiling, two M3 × 8 on a diagonal, into the front-left and the rear-right of the four camera inserts.
:::

Screws first, cables after: the camera's cable sits under the front screw, and the lead lies across the rear
one.

:::{build-step} 3
:drawing: k2m
:alt: The camera in its case going up into the sleeve of the pod, lens down
:parts: km=1
:hardware: Cable JST XH 6-pin → Dupont=1
:click:

The XH → Dupont cable onto J2, each wire on the pin of its name, and its XH plug into the **Mega**'s side.
Push the Mega's case up into the sleeve until the lips click, lens down, the XH plug and its wires up through
the sleeve's open side.
:::

## Route the lead

:::{build-step} 4
:drawing: k3
:alt: Rear view: the lead leaving the tray's rear slot, climbing behind the tray and running forwards under the ceiling to the pod
:parts: kl=1
:hardware: tie=4

Drawer out.  The **camera lead** into the bay's own node: J6, the socket marked CAM, vertical, at the node's
rear right.  From there it goes to the right first, level with the right end of the tray's rear slot, and only
then back along the plenum and out through that slot, with a cable tie there.  Then straight up behind the
tray's rear wall, forwards under the ceiling with three ties through the ceiling's windows, about one every
5 cm, down behind the pod and into J1 from the pod PCB's right.
:::

The detour keeps the lead 30 mm from the node's antenna, which is on the node's rear edge, left of J6; run
straight back, it would pass at 18 mm.  The route takes about 45 cm of the lead's 50.  J7 (DATA), on the
node's right edge, takes the same plug: a camera lead plugged there harms nothing, and the camera does not
answer.

## Check before you go on

- [ ] The lens looks straight down, its tip about 30 mm under the ceiling.
- [ ] The lead is in J6 at the node and in J1 at the pod, and passes the right end of the tray's rear slot.
- [ ] Each wire of the XH → Dupont cable is on the pin of its name: VCC, GND, SCK, MISO, MOSI, CS.
- [ ] The drawer closes and opens under the pod with its board and cable in place.  The pod hangs down to
      120 mm above the row; the cable's arch stays under about 105 mm
      ([Put a board in a bay](../use/mount-a-board.md)).

The lens has no autofocus.  It is focused once, by hand, from the bay page's live view, and that needs the
rack on: it is one of the checks per bay of [Bring the rack online](bring-the-rack-online.md).

A step that is wrong: [report it](../reference/known-limitations.md#report-a-finding).
