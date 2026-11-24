# Check a camera pod

The camera pod is the small PCB beside a bay's camera. It holds the header for the Arducam Mega camera, a
3.3 V regulator and four white LEDs that light the bay. Check one for each bay that has a camera.

The pads are named in print on the bottom face.
[The camera pod's PCB page](../../reference/pcbs/camera-pod.md) lists its connectors.

## 1. Look it over

```{figure} ../../img/pcbs/camera-pod-top.jpg
:alt: The top face of the camera pod v1.0
:width: 60%

KiCad render, top face: the LEDs along the top, U1 in the middle, J1 on the right edge, J2 at the bottom.
```

- [ ] The four LEDs, D1 to D4, all face the same way. The cathode is the large pad.
- [ ] U1, the 3.3 V regulator, and the two connectors sit flat, with no lifted pin. J1, on the edge, takes
  the camera lead from the node. J2 is the camera's header. Its six pins are marked VCC, GND, SCK, MISO, MOSI
  and CS.

## 2. Measure for shorts

| Ohmmeter between GND and | Expect |
|---|---|
| 5V, 3V3 | no short: the reading climbs, or stays above about 100 Ω |

## 3. Power it on its own

Connect a bench supply to the 5V and GND pads. Set it to 5.0 V with a limit of 0.2 A.

| Check | Expect |
|---|---|
| 3V3 | 3.3 V (3.2 to 3.4 V) |
| The supply's current | a few milliamps |
| The LED pad joined to GND with a wire | the four LEDs light; the supply gives 70 to 105 mA |
| Across one of the 100 Ω resistors R1 to R4, LEDs on | 1.8 to 2.6 V (18 to 26 mA in that LED) |

## 4. Plug it into a node

Check the camera lead (JST PH 8, "Same direction") with the meter first: pin n goes to pin 9 − n. Plug it into
J6 (CAM) on the node and J1 on the pod. Plug the Arducam Mega's own cable into J2, with each wire on the pin of
the same name. The names printed under J2 are wider than the header: count the pins from VCC, at pin 1. Then
power the node.

In the table, `<node>.local` is the name in brackets on the first line of `bay status`.

| Check | Expect |
|---|---|
| 5V and 3V3 pads | 5.24 V from the node, and 3.3 V |
| `bay camera` | the camera's model |
| `http://<node>.local:8081/snapshot.jpg` | a picture |
| The same address with `?light=on`, then `?light=off` | the LEDs follow |
| `/stream.mjpg?light=on` on the same port, for a few minutes | U1 warm, but not too hot to touch |

The camera lead also fits J7 (DATA) on the node, and a DATA lead fits J6. Neither mistake does any harm, but
nothing works in the wrong socket.
