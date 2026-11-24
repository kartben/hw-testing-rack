# Bring-up: camera pod v1.0

The small board beside each bay's camera: the lead from the node, the Arducam Mega's header, a
3.3 V regulator and four white LEDs.  Test pad names are the ones printed on the bottom face.
Back to [bring-up.md](../bring-up.md).

## 1. Look

- The four LEDs D1–D4 all turned the same way (the cathode is their large pad).
- U1, the 3.3 V regulator, and the two connectors: J1 (the lead, on the edge) and J2 (the six
  pins named VCC GND SCK MISO MOSI CS).

## 2. No power

| Ohmmeter between GND and | Expect |
|---|---|
| 5V, 3V3 | no short: the reading climbs, or stays above ≈ 100 Ω |

## 3. First power, alone

Bench supply at 5.0 V, limit 0.2 A, on the 5V and GND pads.

| Check | Expect |
|---|---|
| 3V3 | 3.3 V (3.2–3.4 V) |
| The supply's current | a few milliamps |
| The LED pad joined to GND with a wire | the four LEDs light; the supply gives 70–105 mA |
| Across one of the 100 Ω resistors R1–R4, LEDs on | 1.8–2.6 V (18–26 mA in that LED) |

## 4. On a node

A camera lead (JST PH 8, "Same direction") from the node's J6 (CAM) to J1.  Check the lead with
the meter first: pin n goes to pin 9 − n.  The Arducam Mega's own cable goes on J2, wire by
name.  Then power the node.

| Check | Expect |
|---|---|
| 5V and 3V3 pads | 5.24 V from the node, 3.3 V |
| `bay camera` | the camera's model |
| `http://bay-<id>.local:8081/snapshot.jpg` | a picture |
| The same address with `?light=on`, then `?light=off` | the LEDs follow |
| The stream for a few minutes, light on | U1 warm, not too hot to touch |

The camera lead also fits the node's J7 (DATA).  The pinouts were chosen so that this mistake
harms nothing, but the camera does not work there: J6 is the socket marked CAM.

## 5. Later

The 3.3 V rail on a scope while the camera streams, and the regulator's temperature:
[electronics.md › Bring-up measurements](../electronics.md#bring-up-measurements).
