# Add a camera

A camera pod hangs under a bay's ceiling and looks down at the boards. The ceiling is the tray above the
bay, or the cap plate on the top row. The pod holds an Arducam Mega and a small PCB with four white LEDs. A
lead connects it to the bay node.

Cameras are optional. Every ceiling has the four inserts for a pod, so you can fit a camera in any bay, now
or later.

## What you need

For each camera you fit, buy one of each:

```{bom-table}
:category: Cameras
:columns: item
```

For each camera you also need:

- `camera_pod`, printed in dark, opaque PETG, and `camera_diffuser`, printed in white. Measure your camera
  before you print the pod ([Parts to measure before you print](../print/index.md#parts-to-measure-before-you-print)).
- A camera pod PCB that passed [its checklist](check-the-pcbs/camera-pod.md).
- A 50 cm camera lead. It is the same type as a DATA lead: JST PH 8, sold as "Same direction"
  ([Cables and pinouts](../reference/cables.md)). Ring it out before you plug it in
  ([Ring out every cable](row-cables.md#ring-out-every-cable)).
- 2 M3 × 8 screws.

Swap the Mega's stock lens for the LN018 first. The stock lens is too narrow to see a large board, such as a
NUCLEO-144, whole.

## Assemble the pod

:::{build-step} 1
:drawing: k1
:parts: kp=1, kb=1, kd=1
:hardware: pt26x14=2

Put the **pod PCB** on its two standoffs behind the sleeve, LEDs down. Its LED edge goes against the baffle.
Hold the **diffuser** under it and drive two PT 2.6 × 14 up through the diffuser and the PCB.
:::

```{figure} ../../electronics/camera-pod/docs/camera-pod-top.jpg
:alt: The face of the camera pod PCB that carries its parts
:width: 45%

KiCad render of the pod PCB, LED side. J1, for the lead, is on the right. J2 has its six pins named.
```

## Mount the pod and the camera

:::{build-step} 2
:hardware: m3x8=2

Pull the drawer out to make room for your hand. Screw the **pod** under the ceiling with two M3 × 8, into
the front-left and the rear-right inserts. Fit the screws before the cables, because the cables pass over
them.
:::

:::{build-step} 3
:drawing: k2m
:parts: km=1
:hardware: Cable JST XH 6-pin → Dupont=1
:click:

Plug the Dupont end of the XH-to-Dupont cable onto J2. Put each wire on the pin of the same name. Plug the
XH end into the side of the **Mega**. Push the Mega up into the sleeve, lens down, until it clicks. The
cable goes up through the open side of the sleeve.
:::

## Route the lead

:::{build-step} 4
:drawing: k3
:parts: kl=1
:hardware: tie=4

Plug the **camera lead** into J6 on the node. J6 is the socket marked CAM, at the rear right. Run the lead to
the right first, as far as the right end of the tray's rear slot. Then take it back and out through
that end of the slot, and tie it there. Take it up behind the tray and forward under the ceiling. Tie it
with three ties through the windows in the ceiling, and plug it into J1 on the pod PCB.
:::

Going right first keeps the lead away from the node's antenna. Do not use J7 (DATA): it takes the same
plug, but the camera does not work there.

## Check before you go on

- [ ] The lens looks straight down, its tip about 30 mm under the ceiling.
- [ ] The lead is in J6 at the node and in J1 at the pod.
- [ ] Each wire on J2 is on the pin of its name: VCC, GND, SCK, MISO, MOSI, CS.
- [ ] The drawer opens and closes under the pod with its board in place. Slide it in slowly: each board's
      USB cable must pass under the pod. Keep the cable lower than about 105 mm above the plate
      ([Put a board in a bay](../use/mount-a-board.md#the-cable-to-the-data-board)).

You focus the lens later, once the rack is on: [Focus the camera](bring-the-rack-online.md#focus-the-camera).
