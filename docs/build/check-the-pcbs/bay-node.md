# Check a bay node

The bay node is the PCB with the ESP32-S3 that runs a bay. It runs from the 20 V of its row and feeds the
bay's USB, DATA lead and camera. Check every node your rack uses.

The pads are named in print on the bottom face. [The bay node's PCB page](../../reference/pcbs/bay-node.md)
lists them all.

## 1. Look it over

```{figure} ../../img/pcbs/bay-node-top.jpg
:alt: The top face of the bay node v1.0
:width: 70%

KiCad render, top face. J1 (ROW IN) is at the lower left. J3 (PC) and SERVICE are on the front edge, at the
bottom. J7 (DATA), J5 (AUX) and J2 (ROW OUT) run down the right edge. J6 (CAM) is at the upper right.
```

- [ ] The pin-1 marks of U1 (the 5 V buck), U5 and U6 (the USB muxes), U7 (the OR gate), U9 (the eFuse of
  the DATA lead), U10 (the INA226 current monitor), U11 (the CAN transceiver) and the four USBLC6 (U4, U8,
  U12, U13). U2 (the 3.3 V regulator) and Q1 (the reverse-polarity FET) only fit one way.
- [ ] C1, the tall 100 µF can: its black mark is the minus side.
- [ ] D2, the big diode beside C1: its bar is on the VIN side.
- [ ] R35 is not fitted: its footprint is empty.
- [ ] The SERVICE switch (SW3) sits on its two pegs.

## 2. Measure for shorts

```{figure} ../../img/pcbs/bay-node-bottom.jpg
:alt: The bottom face of the bay node v1.0, with its named test pads
:width: 70%

KiCad render, bottom face. The supply pads run along the bottom edge. The shell's pads, TX, RX and GND, are
at the top.
```

| Ohmmeter between GND and | Expect |
|---|---|
| VIN, 5V, 3V3, DATA VIN, CAM 5V | no short: the reading climbs, or stays above about 100 Ω |

## 3. Power it on its own

The node runs from its row socket, never from its USB port. Plug the
[two-wire lead for the bench](../row-cables.md#a-two-wire-lead-for-the-bench) into J1 (ROW IN): pin 1 is +,
pins 2 and 5 are GND. Set the bench supply's limit to 0.2 A and raise the voltage from 0 to 20 V.

| Check | Expect |
|---|---|
| 5V, below about 13.5 V | 0 V: the buck waits for the row to be up |
| VIN, at 20 V | the supply's voltage, a few tens of millivolts lower |
| 5V | 5.24 V (5.1 to 5.4 V) |
| 3V3 | 3.3 V (3.2 to 3.4 V) |
| CAM 5V | the same as 5V (it comes through a resettable fuse) |
| DATA VIN | well below VIN: the DATA lead stays off without firmware. Several volts are normal: the eFuse leaks a little |
| The supply's current | well under 0.2 A: write it down |

If you want, test the reverse-polarity protection too. Set the limit to 50 mA and reverse the supply. No
current flows, and VIN stays at 0 V.

## 4. Flash and check

Keep the node powered from J1. Slide SERVICE on: it hands the PC port (J3) to the node itself. Plug the
laptop into the PC port and flash the node ([Flash a node](../flash.md#flash-a-node) has the details):

```console
$ west flash -d build-bay
```

Slide SERVICE off. The node joins the Wi-Fi network in your `wifi.conf` and answers at
`http://bay<MAC>.local/`. Its shell answers over telnet. It also answers on the TX, RX and GND pads, through a
3.3 V USB-UART at 115200 baud.

An image built without `wifi.conf`, or downloaded from CI, has no network in it. In that case, connect the
USB-UART to the pads and type your network now. Once the node is on its tray, the pads are
[underneath it](../index.md#wifi). [Wi-Fi for the rack](../../use/wifi.md) says which network to use.

```console
uart:~$ wifi cred add -s <ssid> -k 1 -p <password>
uart:~$ wifi cred auto_connect
```

| Check | Expect |
|---|---|
| `bay status` | an IP address, power off, 0 mA, no fault |
| SERVICE on, then off | the status LED turns yellow, then changes back ([the LED's colours](../../reference/leds-and-buttons.md)) |
| RESET (SW1) | the node restarts and comes back on the network |
| `bay power on`, nothing on J7 | DATA VIN rises to VIN for about a second. Then the node switches it off and says no DATA board answers |
| J5 pins 3 and 4 joined with a wire, `bay aux send hello`, then `bay aux` | the receive counter grows by what was sent |
| A laptop on the PC port, SERVICE off | `bay status` shows the classic data path: the boards' USB goes to the laptop |

[Bay node shell](../../reference/node-shell.md) lists every command.

## 5. Run it from the hub

Run a [row cable](../row-cables.md) from one of the hub's rows to J1. The node starts when the hub turns the
row on. It gets its position from the hub and shows it in `bay status`.

## 6. Burn the fuse

- [ ] Burn the module's one-time fuse, `DIS_USB_OTG_DOWNLOAD_MODE`, only on a node that goes into the rack.
  It turns off a USB download mode that the rack never uses, and it [cannot be undone](../index.md#fuse).
  [The module's one-time fuse](../flash.md#the-modules-one-time-fuse) gives the command.
