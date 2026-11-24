# Power-cycle or reset a board

Every board in a bay hangs on a switch of its own: the bay node turns each port's 5 V on and off, measures
its current and, on a DATA ×4, pulls the port's RESET and BOOT lines. The examples act on B3.2, port 2 of
bay B3.

:::{status} simulated
The port logic is tested on native_sim against emulated DATA boards, and `bayctl` against the simulated node.
The bench plan for the M5Stack CoreS3 stand-in switches one board's 5 V; no result is written down. No DATA ×6
or DATA ×4 has been on a node. See [What exists today](../plan/status.md).
:::

Needs: a DATA ×6 or a DATA ×4 in the bay, since a v1.0 node powers nothing without one
([Bays, ports and addresses](names.md)); for `bayctl`, a machine set up as on
[Set up bayctl and usbip](set-up-your-machine.md).

## In the browser

Open `http://bay-b3.local/`. The **USB devices** card has one row per port.

```{figure} ../img/web-ui-ports.png
:class: bb-screenshot
:alt: The USB devices card of bay B3: four port rows, each ending with its buttons

Simulated node, a DATA ×4 bay. B3.3 is reserved by another address, so its buttons are greyed; B3.4 is off,
with a power-on queued.
```

A port that is on has **Cycle** and **Off**; **Off** asks before it cuts the 5 V. A port that is off has
**Power on**, and an **As soon as possible** box that queues the request when the bay's power share has no
room ([Power budget and queued ports](power-budget.md)). On a DATA ×4 a row also has **Reset** and
**Bootloader**. The **Power** card above shows the volts, amps and watts of the whole DATA lead with the
hub's grant under them, and its **On**, **Off** and **Cycle** act on every port of the bay.

## With bayctl

```console
$ python tools/bayctl.py power B3.2 cycle
B3.2   port 2  VBUS on 139 mA  no USB device
```

The line is the port as the node reports it when the cycle ends: powered again, not yet enumerated.
`power B3.2 off` and `power B3.2 on` switch it; `cycle --ms 2000` keeps it off for at least two seconds,
where the default is 1000 ms. A power-on that the bay's share has no room for fails with 409;
`--when available`, `--wait SECONDS` and `power B3.2 cancel` are on
[Power budget and queued ports](power-budget.md). Every option: [bayctl](../reference/bayctl.md).

On a DATA ×6, `bayctl` reaches ports 1 to 4 only, for the reason given under the next heading.

## Over HTTP

```console
$ curl -s -X POST bay-b3.local/api/ports/2/power -d '{"action":"cycle"}'
```

The answer is the port's object. `action` is `on`, `off` or `cycle`. A cycle has no fixed length: the port
stays off until its VBUS reads under 1 V, and 2 s at most, because the port's switch does not discharge
its output and only the board on it does. `"ms": 2000` beside the action sets a shortest off time, from 1
to 10000.

Firmware 0.5 registers `/api/ports/<n>/power`, `/reset` and `/boot` for ports 1 to 4
([web.c](../../firmware/bay-node/src/web.c)). Ports 5 and 6 of a DATA ×6 answer to `/api/power` with a port
number, which is what the bay's page sends for every port; the answer is then the whole status document:

```console
$ curl -s -X POST bay-c2.local/api/power -d '{"action":"cycle","port":5}'
```

The simulated node accepts `/api/ports/5/power` and hides the difference. Status codes and JSON:
[Bay node HTTP API](../reference/node-api.md).

## In the node's shell

The shell is on the node's UART pads and, once the node is on the network, on telnet (`telnet bay-b3.local`).

```console
uart:~$ bay port
uart:~$ bay port 2 cycle
uart:~$ bay port 2 off
```

`bay port` alone names the DATA board and prints one line per port, with its busid, its state, its current
and its USB device. A duration after `cycle` goes from 1 to 60000 ms. Every command and every field:
[Bay node shell](../reference/node-shell.md).

## Reset and bootloader

A DATA ×4 has a RESET and a BOOT line per port, open drain through 1 kΩ, on the port's 2 × 6 header
([DATA ×4](../reference/pcbs/data-x4.md)). They act once a jumper joins each to the board's own reset and
boot pins.

| | Reset | Bootloader | Bootloader, through the power |
|---|---|---|---|
| The bay's page | **Reset** | **Bootloader** | **Bootloader** on a port that is off |
| `bayctl` | `reset B3.2` | `boot B3.2` | `boot B3.2 --power-cycle` |
| HTTP, `POST` | `/api/ports/2/reset` | `/api/ports/2/boot` | the same, with `{"power_cycle": true}` |
| The node's shell | `bay port 2 reset` | `bay port 2 boot` | `bay port 2 boot cycle` |

Reset holds RESET low for 100 ms (`reset B3.2 --ms 250`, or `{"ms": 250}`, for another length). Bootloader
holds BOOT low, pulses RESET and releases BOOT 200 ms later: the ROM bootloader on most MCUs. The third
column is for a board whose reset pin is not wired: BOOT is held across a power cycle of the port instead.

While a port is off the node holds both lines low, so that their pull-ups put no voltage on an unpowered
board; a reset asked of a port that is off is refused (503). When the port goes on, the node releases BOOT,
then RESET, 5 ms after its switch.

A DATA ×6 has neither line. Its rows have no such buttons, and the request is refused; to restart a board on
a DATA ×6, cycle its port.

```console
$ python tools/bayctl.py reset C2.1
bayctl: C2.1: /api/ports/1/reset: 400 this port has no such line
```

## A whole bay at once, and the BOOT button

Naming the bay instead of a port switches every port of it, the analyzer's and the empty ones included:

```console
$ python tools/bayctl.py power B3 cycle --ms 2000
B3.1   port 1  VBUS on 131 mA  no USB device
B3.2   port 2  VBUS on 86 mA  no USB device
B3.3   port 3  VBUS on 128 mA  no USB device
B3.4   port 4  VBUS on 94 mA  no USB device
```

`reset B3` and `boot B3` pass by the analyzer and the empty ports. Over HTTP there is no call for the whole
bay: `/api/power`, `/api/reset` and `/api/boot` without `"port"` answer 409.

In the node's shell, `bay power off`, `on` and `cycle [ms]` (1000 ms unless said) switch the DATA lead
itself: the DATA board, its USB hub and every board lose power together. When the lead comes back the ports
are switched on again one at a time, 300 ms apart; a port switched off by hand stays off.
[The rack's page](rack-page.md) power-cycles a bay the same way, through the rack bus, for a node that has
no Wi-Fi.

:::{warning}
BOOT on the node, held for a second or more and released, power-cycles the DATA lead: every board of the bay
restarts, whoever is flashing one. Held for ten seconds it makes the node forget its admin key and its
access rules instead. Where the button is: [LEDs, buttons and switches](../reference/leds-and-buttons.md).
:::

## After an over-current

A port's switch limits the current ([Specifications](../reference/specifications.md)) and latches off after
7.5 ms in limit. The other ports stay on. The page shows a red banner, "Over-current on B3.2: the port's
5 V was switched off.", `bayctl ports B3` prints `VBUS FAULT` for the port, and `/api/ports` gives
`"fault": true`. The next power-on clears the fault: the banner's **Power on**, `bayctl power B3.2 on`,
`{"action":"on"}` or `bay port 2 on`. `bayctl prepare` does it before every test of a twister run.

The DATA lead has a protection of its own, an eFuse on the node. A fault there, or a DATA board that misses
two polls in a row (20 ms apart), switches the whole lead off at once. The bay's LED blinks red, the hub
receives an alert, and the banner reads "DATA lead off:" with the reason. The lead stays off until
`bay power on` in the node's shell, which runs the power-on checks again and prints
`DATA_VIN stays off:` and the reason when one fails.

## After a power cut or a restart

| What happened | What is lost | What comes back by itself |
|---|---|---|
| The charger is unplugged, or the mains fail | the hub's events, every reservation, every USB/IP session, which ports were off | the rows that were on, then every port of every bay |
| A row is switched off, or cycled | on that row: reservations, USB/IP sessions, which ports were off | after a cycle, the row and every port on it |
| A node restarts: an update, a fatal error, its RESET button | its reservations, its USB/IP sessions, which ports were off, the wires of a DATA ×4 | every port of that bay |
| The hub restarts: an update, its RST button | its events | nothing needs to: the rows stay on |

The hub saves a row's on or off; a cycle is not saved and ends with the row on. The hub holds its row enables
across its own restart, so the bays keep running: that is the design, and the hub's notes mark it as to be
checked on the first hub.

A port's on or off is saved nowhere. At each start of a node every port is wanted on, and the ports go on
one at a time, 300 ms apart, each only if the bay's share has room for it. A board switched off on purpose
is therefore on again after a firmware update, and on a DATA ×4 with the hub's usual grant some ports can
come back waiting for power ([Power budget and queued ports](power-budget.md)). A restarting node also cuts
its DATA lead until its firmware has checked the lead again: the bay's boards lose power for the length of
the restart.

A client whose USB/IP session ended sees a detach; `bayctl attach --follow` attaches the board again when it
is back ([USB/IP and flashing](usb-and-flashing.md)). What a node and the hub keep in flash, from the bay's
id to the board targets, is listed on [Recover a node or a hub](recover.md).

## If it does not work

`bayctl` prints the node's refusal after its own prefix, as in the DATA ×6 example above, and exits with 1.

| What you get | What it means |
|---|---|
| 409, `no room in the bay's budget: the bay draws …` | The bay's share of the charger is used up, and a plain power-on is not queued. Queue it, or switch another port off: [Power budget and queued ports](power-budget.md). |
| 409, `the port's VBUS is up while it is off (a board powered from elsewhere): it comes on once that has gone` | The port reads more than 3.5 V while it is off: the board is fed through another connector. The port goes on by itself once that voltage has gone. A board with two USB connectors: [Put a board in a bay](mount-a-board.md). |
| 409, `this node serves 4 boards: say which` | `/api/power`, `/api/reset` or `/api/boot` without `"port"`. |
| 400, `this port has no such line` | Reset or bootloader on a DATA ×6. |
| 503, `the port is off, or the DATA board is not set up (DUT_5V off?)` | Reset or bootloader on a port that is off, or the DATA lead is off. |
| 423, `B3.2 reserved by <address> (<note>), <n> min left` | Someone holds the port or the bay: [Reserve a bay](reserve-a-bay.md). |
| 403, with `reason`, `service` and `you` | The node's access rules do not give your address the control right: [Access rules and security](access.md). |
| `DATA lead off: SCL or SDA held low: DATA lead reversed?` | The lead between the node and the DATA board is of the wrong kind, wired 1:1 where it must be "same direction". Before changing it: [Take out a tray, a node or a DATA board](service-a-bay.md). |
| `DATA lead off: no DATA board answers: none, or the wrong lead in J7` | No DATA ×6 or DATA ×4 answered within a second of the lead going on. |

The four other reasons a DATA lead stays off, and every other message:
[States and error messages](../reference/states-and-messages.md). A bay that does not answer at all:
[Troubleshooting](troubleshooting.md).
