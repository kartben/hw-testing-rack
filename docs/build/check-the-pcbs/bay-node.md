# Bay node checklist

One per bay: it runs from the row's 20 V, carries the ESP32-S3, the USB path to the boards, the
DATA lead's supply and the camera's.  Test pad names are the ones printed on the bottom face; every
connector and pad is listed on [the bay node's PCB page](../../reference/pcbs/bay-node.md).

:::{status} designed
No bay node v1.0 has been powered or measured: the expected values are the design's.
[What exists today](../../plan/status.md#status-bay-node).
:::

## 1. Look

```{figure} ../../img/pcbs/bay-node-top.jpg
:alt: The top face of the bay node v1.0
:width: 70%

KiCad render of the bay node v1.0, top face.  J1 (ROW IN) is at the lower left, J3 (PC) and the SERVICE switch
on the front edge at the bottom; J7 (DATA), J5 (AUX) and J2 (ROW OUT) run down the right edge, J6 (CAM) stands
at the upper right.
```

- [ ] The pin-1 marks of U1 (the 5 V buck), U5 and U6 (the USB muxes), U7 (the OR gate), U9 (the
  DATA lead's eFuse), U10 (the INA226 current monitor), U11 (the CAN transceiver) and the four
  USBLC6 (U4, U8, U12, U13).  U2 (the 3.3 V regulator) and Q1 (the reverse-polarity FET) only fit one way.
- [ ] C1, the tall 100 µF can: its black mark is the minus side.  D2, the big diode beside it: its
  bar is on the VIN side.
- [ ] R35 is not fitted: its footprint stays empty.
- [ ] The SERVICE switch (SW3) sits on its two pegs.

## 2. No power

```{figure} ../../img/pcbs/bay-node-bottom.jpg
:alt: The bottom face of the bay node v1.0, with its named test pads
:width: 70%

KiCad render of the bottom face.  The supply row is at the bottom: CAM 5V, DATA VIN, 3V3, 5V, VIN, GND.  TX, RX
and GND, the shell's pads, are at the top.
```

| Ohmmeter between GND and | Expect |
|---|---|
| VIN, 5V, 3V3, DATA VIN, CAM 5V | no short: the reading climbs, or stays above ≈ 100 Ω |

## 3. First power

The node runs from its row socket, never from the USB port.  Bench supply at 20 V, limit 0.2 A,
on J1 (ROW IN): pin 1 is +, pins 2 and 5 are GND.  The
[two-wire lead for the bench](../row-cables.md#a-two-wire-lead-for-the-bench) plugs in there.  Raise the
voltage from 0.

| Check | Expect |
|---|---|
| Under ≈ 13.5 V | 5V at 0 V: the buck waits for the row to be up |
| At 20 V: VIN | the supply's voltage, a few tens of millivolts lower |
| 5V | 5.24 V (5.1–5.4 V) |
| 3V3 | 3.3 V (3.2–3.4 V) |
| CAM 5V | as 5V (it comes through a resettable fuse) |
| DATA VIN | 0 V: the DATA lead's eFuse is off without firmware |
| The supply's current | well under the 0.2 A limit: write it down |

Optional: the supply reversed, limit 50 mA.  No current flows and VIN stays at 0 V.

## 4. Flash and ask

Node powered from J1.  Slide SERVICE on, laptop on the front PC port (J3).  The switch, the port and the
image: [Flash a node](../flash.md#flash-a-node).

```console
$ west flash -d build-bay
```

SERVICE off.  The node joins the Wi-Fi of `wifi.conf` and answers at `http://bay<MAC>.local/`
and over telnet.  Without Wi-Fi: a 3.3 V USB-UART on the TX, RX and GND pads, 115200.

An image built without `wifi.conf`, or taken from CI, carries no network.  Type it on those pads now:
they are under the node [once it is on its tray](../index.md#wifi).  Which network:
[Wi-Fi in the rack](../../use/wifi.md).

```console
uart:~$ wifi cred add -s <ssid> -k 1 -p <password>
uart:~$ wifi cred auto_connect
```

| Check | Expect |
|---|---|
| `bay status` | an IP address, power off, 0 mA, no fault |
| SERVICE on | the status LED turns yellow; off again, it leaves yellow ([the LED's colours](../../reference/leds-and-buttons.md)) |
| RESET (SW1) | the node restarts and comes back on the network |
| `bay power on`, nothing on J7 | DATA VIN rises to VIN for under a second, then the node switches it off and says no board answered |
| J5 pins 3 and 4 joined with a wire, `bay aux send hello`, `bay aux` | the receive counter grows by what was sent |
| A laptop on the PC port, SERVICE off | `bay status` shows the classic data path |

Every command of this shell: [Bay node shell](../../reference/node-shell.md).

## 5. On the hub

A [row lead](../row-cables.md) from one of the hub's rows to J1.  The node starts when the hub turns the row
on, takes its position from the hub and shows it in `bay status`.  The bus itself, with two nodes:
[the rack bus checklist](rack-bus.md).

Then the PCBs that hang off the node: [the camera pod](camera-pod.md),
[the DATA ×6](data-x6.md), [the DATA ×4](data-x4.md).

## 6. Last

- [ ] The module's one-time fuse (`DIS_USB_OTG_DOWNLOAD_MODE`), once everything above passed, and only on
  a node that goes into the rack.  It [cannot be undone](../index.md#fuse); the command is on
  [Flash the hub and the nodes](../flash.md#the-modules-one-time-fuse).
- [ ] On the first node of a revision, the measurements the reviews left for it (F1's margin, the 3.3 V load
  step, the I²C rise time): [More to measure](index.md#more-to-measure-on-the-first-pcbs-of-a-revision).

A node that passed goes on its tray: [Fit out a tray](../fit-out-a-tray.md).  A reading that does not match:
[report it](../../reference/known-limitations.md#report-a-finding).
