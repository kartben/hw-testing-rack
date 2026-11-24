# DATA ×6 checklist

The drawer's DATA board: six switched and measured USB-C ports behind a USB hub, fed by the node's
DATA lead (20 V, USB and I²C).  Test pad names are the ones printed on the rear face; the ports, the
addresses and the limits are on [the DATA ×6's PCB page](../../reference/pcbs/data-x6.md).

:::{status} designed
No DATA ×6 v1.0 has been powered or measured: the expected values are the design's.  The node's
firmware has driven this PCB on native_sim only, against an emulated one.
[What exists today](../../plan/status.md#status-data-x6).
:::

## 0. Solder

J1, the lead's socket (JST PH 8, B8B-PH-K-S), goes on the rear face by hand: the fab does not
fit it.  Which face, which way round: [Solder the connectors](../solder-the-connectors.md).

## 1. Look

```{figure} ../../img/pcbs/data-port-x6-top.jpg
:alt: The front face of the DATA ×6 v1.0
:width: 80%

KiCad render of the DATA ×6 v1.0, front face: the six ports with their numbers, U1 in the middle, the two 5 V
bucks in the upper corners.
```

- [ ] The pin-1 marks of U1 (the USB hub, the large chip), U2 (the port expander), U13 and U14 (the
  two 5 V bucks), and at each port n: Un01 (the power switch), Un02 (the INA226 current monitor)
  and Un03 (the ESD array).
- [ ] C60, the electrolytic can: its black mark is the minus side.
- [ ] The six USB-C receptacles standing straight, their two pegs in their holes.

## 2. No power

```{figure} ../../img/pcbs/data-port-x6-bottom.jpg
:alt: The rear face of the DATA ×6 v1.0, with its named test pads
:width: 80%

KiCad render of the rear face: J1 at the left with the names of its eight pins, and the pads of this
checklist.
```

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

## 4. On a node

The node's firmware drives this PCB since 2026-11-11, with the same image as a DATA ×4: it tells the two
apart on I²C ([Which board: DATA ×4 or DATA ×6](../../multi-dut-node.md#which-board-data-4-or-data-6)).
Stages 1 to 3 need no firmware; this stage is the firmware's first run on hardware.

A DATA lead (JST PH 8, "Same direction") from the node's J7 (DATA) to J1.  Check the lead with
the meter first: pin n goes to pin 9 − n.

| Check | Expect |
|---|---|
| `bay power on` | DATA VIN at the row's voltage; the log says "DATA x6: 6 ports, every port off; switching on the wanted ones"; no fault |
| `bay usb` | the DATA board's hub |
| `bay port` | "DATA x6, 6 ports": port 1 on busid 1-1.6, port n on 1-1.(n − 1); each on, one after the other (`CONFIG_BAY_PORTS_ON_AT_BOOT`) |
| `bay port 1 off` | VBUS1 at 0 V |
| `bay port 1 on` | VBUS1 at 4.94–5.08 V |
| A USB device in port 1, `bay usb` | the device on 1-1.6, behind the hub |
| `bay port 1`, device plugged | its voltage and current |
| `bay port 1 reset` | "port 1 has no RESET or BOOT line (a DATA x6)": the PCB was taken for a DATA ×6 |
| The bay page | the header's badge says "DATA ×6" (a red "Unknown DATA board": the node did not take it for one); six ports; no Wires card, no Logic analyzer card |
| `bay port 1 off` | VBUS1 back to 0 V, the device gone |

The same on ports 2 to 6.  The chips the node finds on I²C: 0x20 (the expander) and
0x41, 0x43, 0x44, 0x45, 0x47, 0x4C (the six INA226).  Why port 1 is on busid 1-1.6:
[Bays, ports and addresses](../../use/names.md).

## 5. Later

On the first DATA ×6 of a revision: VBUS at each receptacle under load, up to the port's 0.52–0.64 A limit.
The method is the one [Bring-up measurements](../../electronics.md#bring-up-measurements) gives for a DATA ×4.

A DATA ×6 that passed goes into its drawer on [Fit out a tray](../fit-out-a-tray.md).  A reading that does
not match: [report it](../../reference/known-limitations.md#report-a-finding).
