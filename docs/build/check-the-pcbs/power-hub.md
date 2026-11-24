# Check the power hub

The power hub turns a USB-C PD charger into the rack's supply, VRACK, and switches it to up to four rows.
Check it first: it needs no other PCB.

The pads are named in print on the bottom face. [The hub's PCB page](../../reference/pcbs/power-hub.md) lists
them all.

## 1. Look it over

```{figure} ../../img/pcbs/power-hub-top.jpg
:alt: The top face of the power hub v1.0
:width: 70%

KiCad render, top face. J1 (PD input) is at the upper right and J6 (console) at the lower right. The row
sockets, J2 to J5, are on the left edge.
```

- [ ] The pin-1 marks of U1 (CH224A, the PD controller), U2 (the 5 V buck), U3 (the 3.3 V regulator),
  U6 (the CAN transceiver) and U11 to U14 (the row eFuses).
- [ ] The module's antenna at the edge of the PCB.
- [ ] C8, the tall 100 µF can: its black mark is the minus side.
- [ ] The LEDs, the two USB-C receptacles (J1 and J6) and the four row sockets sit flat, with no lifted pin.

## 2. Measure for shorts

```{figure} ../../img/pcbs/power-hub-bottom.jpg
:alt: The bottom face of the power hub v1.0, with its named test pads
:width: 70%

KiCad render, bottom face, with the names of the pads.
```

| Ohmmeter between GND and | Expect |
|---|---|
| VRACK, VHV, 5V BUCK, 5V, USB 5V, 3V3 | no short: the reading climbs, or stays above about 100 Ω |
| ROW A, ROW B, ROW C, ROW D | no short |

Between CANH and CANL, expect about 56 Ω. Both ends of the CAN bus are terminated on the hub.

## 3. Power it on its own

### From the console port

Plug a laptop into J6 with a USB-C to USB-C cable. Avoid a USB-A port: a live one can push the hub's 3.3 V
regulator to its limit. The console port powers the controller, not the rows.

| Pad | Expect |
|---|---|
| USB 5V | about 5 V |
| 5V | 0.3 to 0.5 V below USB 5V (it comes through a Schottky diode) |
| 3V3 | 3.3 V (3.2 to 3.4 V) |
| VRACK, ROW A to D | 0 V |

The laptop sees a new serial port, even with a blank module.

### From the charger

Unplug the laptop. Plug a PD charger into J1, with nothing on the rows and no firmware yet.

| Pad | Expect |
|---|---|
| VRACK, VHV | 9 V: the CH224A asks for it by itself |
| 5V BUCK | 5.24 V (5.1 to 5.4 V) |
| 3V3 | 3.3 V |
| ROW A to D | 0 V: the rows stay off without firmware |

The PD LED is on ([the hub's LEDs](../../reference/leds-and-buttons.md)). If VRACK stays at 5 V, try another
charger before you suspect the PCB.

After you unplug the charger, wait 6 seconds or more before you plug it in again. VRACK takes 2 to 6 seconds
to fall, and some chargers refuse the hub until it has.

## 4. Flash and check

Plug the laptop back into J6 and leave the charger in J1. Flash the hub
([Flash the hub](../flash.md#flash-the-hub) has the details):

```console
$ west flash -d build-hub
```

Open a terminal on the same serial port at 115200 baud. The hub's firmware never contains a Wi-Fi network, so
type yours. [Wi-Fi for the rack](../../use/wifi.md) says which network to use.

```console
uart:~$ wifi cred add -s <ssid> -k 1 -p <password>
uart:~$ wifi cred auto_connect
```

The hub then answers at `http://rack.local/`. [Power hub shell](../../reference/hub-shell.md) lists every
command.

| Check | Expect |
|---|---|
| `hub pd` | a 20 V contract, and what the charger offers |
| VRACK pad | 20 V; VSNS about 1.8 V |
| The rows, half a second after the contract | ROW A to D at VRACK, one row after the other; EN A to D about 1.65 V; FLT A to D about 3.3 V; no red LED |
| `hub row A off`, then `on`, then `cycle` | ROW A follows; the other rows do not move |
| `west flash -d build-hub` again, rows on | the rows stay on through the flash |

## 5. Put a load on each row

Plug a row cable into the socket of row A, J2. Rows B, C and D are J3, J4 and J5. At the free end of the
cable, the supply is on pin 1 and GND on pins 2 and 5. Check it with the meter: pin 1 rings to the ROW A pad.

Hold the 47 Ω 10 W resistor between pin 1 and GND for a few seconds. It draws 0.43 A and gets hot.

| Check | Expect |
|---|---|
| IMON A pad | about 0.6 V (1.4 V per ampere) |
| `hub status` | about 0.43 A on row A |
| ROW A pad | still at VRACK |

Do the same on rows B, C and D.

## 6. Burn the fuse

- [ ] Burn the module's one-time fuse, `DIS_USB_OTG_DOWNLOAD_MODE`, only on a hub that goes into the rack.
  It turns off a USB download mode that the rack never uses, and it [cannot be undone](../index.md#fuse).
  [The module's one-time fuse](../flash.md#the-modules-one-time-fuse) gives the command.
