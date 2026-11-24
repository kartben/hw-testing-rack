# Power-cycle or reset a board

The bay node switches the 5 V of each port on the DATA board, and measures its current. On a DATA ×4 it can
also reset the board on a port, or start the board's bootloader. The examples act on B3.2, the board on port 2
of bay B3.

## In the browser

Open `http://bay-b3.local/`. The **USB devices** card has one row per port.

```{figure} ../img/web-ui-ports-power.png
:class: bb-screenshot
:alt: Three port rows: B3.2 on with Reset, Bootloader, Cycle and Off; B3.3 reserved, its buttons greyed; B3.4 off with As soon as possible and Power on

A simulated node. B3.2 is on. B3.3 is reserved by someone else, so its buttons are greyed. B3.4 is off.
```

A port that is on has **Cycle** and **Off**. A port that is off has **Power on**. On a DATA ×4, each row also
has **Reset** and **Bootloader**. The **Power** card above acts on every port of the bay at once.

## With bayctl

```console
$ python tools/bayctl.py power B3.2 cycle
B3.2   port 2  VBUS on 139 mA  no USB device
$ python tools/bayctl.py power B3.2 off
$ python tools/bayctl.py power B3.2 on
```

`cycle` keeps the port off for 1000 ms, or for the time you give with `--ms`. The node then waits for the
port's 5 V to fall under 1 V, for 2 s at most, and switches the port back on.

`bayctl` switches ports 1 to 4 only. Switch ports 5 and 6 of a DATA ×6 from the bay's page, or over HTTP with
`"port"` ([Limitations](../reference/known-limitations.md#the-firmware)). Every option:
[bayctl](../reference/bayctl.md#power).

## Over HTTP

```console
$ curl -s -X POST bay-b3.local/api/ports/2/power -d '{"action":"cycle"}'
$ curl -s -X POST bay-c2.local/api/power -d '{"action":"cycle","port":5}'
```

`action` is `on`, `off` or `cycle`. You can add `"ms"`, from 1 to 10000. Ports 5 and 6 of a DATA ×6 have no
address of their own: send the port number to `/api/power`, as in the second line. Every field:
[Bay node HTTP API](../reference/node-api.md).

## In the node's shell

Reach the node's shell with `telnet bay-b3.local`, or on the node's UART pads.

```console
uart:~$ bay port
uart:~$ bay port 2 cycle
uart:~$ bay port 2 off
```

`bay port` alone lists the ports with their state, current and USB device. Every command:
[Bay node shell](../reference/node-shell.md).

## Reset and bootloader

A DATA ×4 has a RESET line and a BOOT line for each port, on the port's pin header. Join them to the board's
reset and boot pins with jumper wires ([Wires between boards](wires.md#plug-the-jumper-wires-once)). A
DATA ×6 has neither line: cycle the port instead.

| | Reset | Bootloader | Bootloader through the power |
|---|---|---|---|
| The bay's page | **Reset** | **Bootloader** | **Bootloader** on a port that is off |
| `bayctl` | `reset B3.2` | `boot B3.2` | `boot B3.2 --power-cycle` |
| HTTP, `POST` | `/api/ports/2/reset` | `/api/ports/2/boot` | `/api/ports/2/boot` with `{"power_cycle": true}` |
| The node's shell | `bay port 2 reset` | `bay port 2 boot` | `bay port 2 boot cycle` |

Reset holds RESET low for 100 ms. `--ms` sets another time.

Bootloader holds BOOT low, pulses RESET, then releases BOOT 200 ms later. This starts the ROM bootloader of
most MCUs. If the board's reset pin is not wired, use the last column: the node holds BOOT low while it cycles
the port's power.

While a port is off, the node holds both lines low, so they put no voltage on the unpowered board.

## Switch a whole bay

To act on every port of a bay, give the bay instead of a port: `bayctl power B3 cycle`. `bayctl reset B3` and
`bayctl boot B3` skip the empty ports and a port that holds a logic analyzer.

In the node's shell, `bay power off`, `bay power on` and `bay power cycle` switch the DATA lead, the cable from
the node to the DATA board. The DATA board and all its boards lose power together. When the lead comes back
on, the ports go on one at a time, 300 ms apart. For a bay that is not on Wi-Fi, use
[the rack's page](rack-page.md#send-a-command-to-a-bay).

:::{warning}
The node's BOOT button, held for a second and released, power-cycles every board in the bay, even one that
someone is flashing. Held for ten seconds, it makes the node forget its admin key and its access rules.
Where the button is: [LEDs, buttons and switches](../reference/leds-and-buttons.md).
:::

## After an over-current

A port's switch cuts its 5 V after 7.5 ms at its current limit. The other ports stay on. The bay's page shows
"Over-current on B3.2: the port's 5 V was switched off.", and `bayctl ports B3` prints `VBUS FAULT`. To clear
the fault, switch the port on again. `bayctl prepare` does this before every test of a twister run.

The DATA lead has its own eFuse on the node. If the eFuse trips, or if the DATA board stops answering, the node
switches the whole lead off. The bay's LED blinks red, and the page shows "DATA lead off:" with the reason. To
switch the lead on again, run `bay power on` in the node's shell, use [the rack's page](rack-page.md), or
restart the node.

## After a power cut or a restart

| What happened | What is lost | What comes back by itself |
|---|---|---|
| The charger is unplugged, or the mains fail | the hub's events, reservations, USB/IP sessions, which ports were off | the rows that were on, then every port |
| A row is switched off or cycled | on that row: reservations, USB/IP sessions, which ports were off | after a cycle, the row and every port on it |
| A node restarts | its reservations, USB/IP sessions, which ports were off, the wires of a DATA ×4 | every port of that bay |
| The hub restarts | its events | nothing needs to: the rows stay on |

A node does not remember which ports were off. Each time it starts, it switches every port on, one at a time,
as long as the bay's power budget has room. So a board you switched off is on again after a firmware update,
and some ports may wait for power ([Power budget and queued ports](power-budget.md)).

A node that restarts also switches its DATA lead off until its firmware has checked the lead again. The bay's
boards have no power while the node restarts.

A USB/IP client sees its board detach. `bayctl attach --follow` attaches it again when it is back
([USB/IP and flashing](usb-and-flashing.md)).

## If it does not work

| What you get | What it means |
|---|---|
| 409, `no room in the bay's budget: …` | The bay's share of the power is used up: [Power budget and queued ports](power-budget.md). |
| 409, `the port's VBUS is up while it is off …` | The board is powered through another connector. The port goes on once that voltage has gone ([Put a board in a bay](mount-a-board.md)). |
| 409, `this node serves 4 boards: say which …` | You sent `/api/power`, `/api/reset` or `/api/boot` without `"port"`. |
| 400, `this port has no such line` | You asked for a reset or the bootloader on a DATA ×6. |
| 503, `the port is off, or the DATA board is not set up (DUT_5V off?)` | You asked for a reset or the bootloader on a port that is off, or the DATA lead is off. |
| 423, `B3.2 reserved by <address> …` | Someone has reserved the port or the bay: [Reserve a bay](reserve-a-bay.md). |
| 403 | Your address does not have the control right: [Control who can use the rack](access.md). |
| `DATA lead off: SCL or SDA held low: DATA lead reversed?` | The lead between the node and the DATA board is the wrong kind: wired 1:1 where it must be "same direction". Before you change it: [Take a bay apart](service-a-bay.md). |
| `DATA lead off: no DATA board answers: none, or the wrong lead in J7` | No DATA board answered within a second of the lead going on. |

Every other message: [States and messages](../reference/states-and-messages.md).
