# Check a DATA ×6

The DATA ×6 is a DATA board with six USB-C ports behind a USB hub. The node switches each port on and off and
measures its voltage and current. The node feeds the board through the DATA lead, which carries 20 V, USB and I²C.

The pads are named in print on the rear face. [The DATA ×6's PCB page](../../reference/pcbs/data-x6.md) lists
its ports and its limits.

## 0. Solder the connector

The fab leaves J1 off. J1 is the socket for the DATA lead (JST PH 8, B8B-PH-K-S). Solder it on the rear face
first. [Solder the connectors](../solder-the-connectors.md) shows which face and which way round.

## 1. Look it over

```{figure} ../../img/pcbs/data-port-x6-top.jpg
:alt: The front face of the DATA ×6 v1.0
:width: 80%

KiCad render, front face: the six numbered ports, U1 in the middle, the two 5 V bucks in the upper corners.
```

- [ ] The pin-1 marks of U1 (the USB hub, the large chip), U2 (the port expander) and U13 and U14 (the two
  5 V bucks).
- [ ] At each port n, the pin-1 marks of Un01 (the power switch), Un02 (the INA226 current monitor) and Un03
  (the ESD array).
- [ ] C60, the electrolytic can: its black mark is the minus side.
- [ ] The six USB-C receptacles stand straight, their two pegs in their holes.

## 2. Measure for shorts

```{figure} ../../img/pcbs/data-port-x6-bottom.jpg
:alt: The rear face of the DATA ×6 v1.0, with its named test pads
:width: 80%

KiCad render, rear face, with J1 at the left.
```

| Ohmmeter between GND and | Expect |
|---|---|
| VIN, +5V_A, +5V_B, +3V3, 1V8 | no short: the reading climbs, or stays above about 100 Ω |
| VBUS1 to VBUS6 | no short |

## 3. Power it on its own

Connect a bench supply to the VIN and GND pads, with a limit of 0.3 A. Raise the voltage from 0 to 20 V.

| Check | Expect |
|---|---|
| +5V_A and +5V_B, below about 13.5 V | 0 V |
| +5V_A and +5V_B, at 20 V | 5.08 V (4.94 to 5.22 V) |
| +3V3 | 3.3 V (3.2 to 3.4 V) |
| 1V8 | 1.8 V |
| VBUS1 to VBUS6 | 0 V: every port stays off until the node switches it on |
| FLT1 to FLT6 | 3.3 V |
| The supply's current | well under the limit: write it down |

## 4. Plug it into a node

The node runs the same firmware for a DATA ×6 and a DATA ×4. It tells them apart on I²C.

Check the DATA lead (JST PH 8, "Same direction") with the meter first: pin n goes to pin 9 − n. Type
`bay power off`, then plug the lead into J7 (DATA) on the node and J1 on the DATA ×6. Never plug or unplug a
powered DATA lead: it can destroy the node's I²C pins or this PCB's USB hub.

| Check | Expect |
|---|---|
| `bay power on` | DATA VIN at the row's voltage; the log says "DATA x6: 6 ports, every port off; switching on the wanted ones"; no fault |
| `bay usb` | the DATA board's hub |
| `bay port` | "DATA x6, 6 ports" and one line per port, every port on. Port 1 is on busid 1-1.6, port n on 1-1.(n − 1) |
| `bay port 1 off` | VBUS1 at 0 V |
| `bay port 1 on` | VBUS1 at 4.94 to 5.08 V |
| A USB device in port 1, then `bay usb` | the device on 1-1.6, behind the hub |
| `bay port 1`, device plugged in | its voltage and current |
| `bay port 1 reset` | "port 1 has no RESET or BOOT line (a DATA x6)": the node knows it is a DATA ×6 |
| The bay's page | the badge in the header says "DATA ×6". Six ports, and no Wires or Logic analyzer card. A red "Unknown DATA board" means the node did not recognise the board |
| `bay port 1 off` | VBUS1 back at 0 V, the device gone |

Repeat on ports 2 to 6. On I²C, the node finds 0x20 (the port expander) and 0x41, 0x43, 0x44, 0x45, 0x47 and
0x4C (the six INA226). [Bays, ports and addresses](../../use/names.md) explains why port 1 is on busid 1-1.6.
