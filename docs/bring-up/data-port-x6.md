# Bring-up: DATA ×6 v1.0

The drawer's board: six switched and measured USB-C ports behind a USB hub, fed by the node's
DATA lead (20 V, USB and I²C).  Test pad names are the ones printed on the rear face.  Back to
[bring-up.md](../bring-up.md).

**The node's firmware does not drive this board yet.**  It knows the DATA ×4's chips; the
DATA ×6's description (`data-x6.dtsi`) is still to be written
([multi-dut-node.md](../multi-dut-node.md)).  Stages 1 to 3 need no firmware.  Stage 4 waits for it.

## 0. Solder

J1, the lead's socket (JST PH 8, B8B-PH-K-S), goes on the rear face by hand: the fab does not
fit it.

## 1. Look

- The pin-1 marks of U1 (the USB hub, the large chip), U2 (the port expander), U13 and U14 (the
  two 5 V bucks), and at each port n: Un01 (the power switch), Un02 (the INA226 current monitor)
  and Un03 (the ESD array).
- C60, the electrolytic can: its black mark is the minus side.
- The six USB-C receptacles standing straight, their two pegs in their holes.

## 2. No power

| Ohmmeter between GND and | Expect |
|---|---|
| VIN, +5V_A, +5V_B, +3V3, 1V8 | no short: the reading climbs, or stays above ≈ 100 Ω |
| VBUS1 … VBUS6 | no short |

## 3. First power, alone

Bench supply, limit 0.3 A, on the VIN and GND pads.  Raise the voltage from 0 to 20 V.

| Check | Expect |
|---|---|
| Under ≈ 13.5 V | +5V_A and +5V_B at 0 V |
| At 20 V: +5V_A, +5V_B | 5.08 V (4.94–5.22 V) |
| +3V3 | 3.3 V (3.2–3.4 V) |
| 1V8 | 1.8 V |
| VBUS1 … VBUS6 | 0 V: every port is off until the node enables it |
| FLT1 … FLT6 | 3.3 V |
| The supply's current | well under the limit: write it down |

## 4. On a node (once the firmware knows the board)

A DATA lead (JST PH 8, "Same direction") from the node's J7 (DATA) to J1.  Check the lead with
the meter first: pin n goes to pin 9 − n.

| Check | Expect |
|---|---|
| `bay power on` | DATA VIN at the row's voltage; the board answers; no fault |
| `bay usb` | the board's hub |
| `bay port` | six ports, all off |
| `bay port 1 on` | VBUS1 at 4.94–5.08 V |
| A USB device in port 1, `bay usb` | the device, behind the hub |
| `bay port 1`, device plugged | its voltage and current |
| `bay port 1 off` | VBUS1 back to 0 V, the device gone |

The same on ports 2 to 6.  The chips the node should find on I²C: 0x20 (the expander) and
0x41, 0x43, 0x44, 0x45, 0x47, 0x4C (the six INA226).

## 5. Later

VBUS at each receptacle under load, up to the port's 0.52–0.64 A limit:
[electronics.md › Bring-up measurements](../electronics.md#bring-up-measurements).
