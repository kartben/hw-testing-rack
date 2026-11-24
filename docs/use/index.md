# What a bay can do

A bay is one drawer of boards and the bay node under it. The node switches and measures each board's power,
puts its USB on the network, and serves a page at `http://bay-b3.local/` from which all of it is driven.
If you did not build the rack in front of you, start with
[Take over a rack you did not build](take-over-a-rack.md); what is inside a bay, a row and the power path
is on [How it works](../plan/index.md).

:::{status} bench
The bay's page loads whole from a XIAO ESP32-S3 stand-in over Wi-Fi; the cards of a bay with several ports
ran against the simulated node only. Nothing has run on the v1.0 PCBs. Each feature's level is in the table
below. See [What exists today](../plan/status.md#status-bay-page).
:::

## A bay from the front

```{figure} ../img/viewer/b3-drawer-out.jpg
:alt: The 3D model: bay B3's drawer pulled out, four boards on its plate, a DATA ×4 standing at its back

The 3D model, bay B3 with its drawer out: two XIAOs and two Pico 2s on the plate, the DATA ×4 at the back
with its four USB-C ports and their pin headers. The screens the model draws on the drawer fronts are a
study: a v1.0 bay has none.
```

| Part | What it does |
|---|---|
| The drawer | holds the boards, on a plate with pegs or on edge in a slot bin. It pulls out 140 mm on a drag chain and everything stays plugged ([Put a board in a bay](mount-a-board.md)) |
| The DATA board | stands at the back of the drawer: a DATA ×6 with six USB-C ports, or a DATA ×4 with four and a pin header over each. A board's cable goes there, and `B3.2` is the board on port 2 ([Bays, ports and addresses](names.md)) |
| The status LED | on the node's front, under the drawer: {led}`green` green with a USB/IP client attached, {led}`blue` blue with a board ready to attach, {led}`red blink` blinking red after a fault ([LEDs, buttons and switches](../reference/leds-and-buttons.md), [Troubleshooting](troubleshooting.md)) |
| The PC port and the SERVICE switch | beside the LED. A laptop on the PC port sees the bay's boards directly; SERVICE hands that port to the node itself ([Front port and classic mode](front-port.md)) |
| BOOT and RESET | the node's two buttons, under the drawer, reached with a pin through two holes in the drawer's floor and the board plate |

## Before you touch it

- The rack must be screwed to the bench before a drawer of the top row is pulled:
  [Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md).
- Nothing but a row cable goes into a node's ROW OUT socket, and the DATA lead is never plugged or unplugged
  under power: [Take out a tray, a node or a DATA board](service-a-bay.md).
- No board with a battery goes in a bay: [Put a board in a bay](mount-a-board.md).
- The node's BOOT button held for a second power-cycles every board of the bay:
  [Power-cycle or reset a board](power-and-reset.md).
- The same button held for ten seconds makes the node forget its admin key:
  [LEDs, buttons and switches](../reference/leds-and-buttons.md).
- `west flash --erase` on a node wipes everything it remembers:
  [Recover a node or a hub](recover.md).

## The bay's page, card by card

```{figure} ../img/web-ui-ports-attach.png
:class: bb-screenshot
:alt: Two rows of the USB devices card: B3.1 attached by 192.168.1.41, B3.2 ready to attach, each with Reset, Bootloader, Cycle and Off

Simulated node, the first two rows of a DATA ×4 bay's *USB devices* card: per port the device, its busid
under the port's name, who has attached it, its current, its board target and its buttons.
```

The page needs no login, follows the browser's light or dark theme and refreshes every 2 s. Until someone
claims the node and switches its rules on, anyone on the network can do everything on it
([Access rules and security](access.md)).

| Card | What it shows and does | More |
|---|---|---|
| Header | the bay's name, host name and address; a badge for the DATA board (DATA ×6, DATA ×4, or a red *Unknown DATA board*), one for access, one for the bay's state | |
| Power | volts, amps and watts of the whole bay, the hub's grant; On, Off and Cycle for every port at once | [Power-cycle or reset a board](power-and-reset.md), [Power budget and queued ports](power-budget.md) |
| USB | USB/IP or Classic; whether a laptop is on the front port; how many clients are attached | [Front port and classic mode](front-port.md) |
| Access | who you are to the node, the reservation, the connections; Reserve and Manage access | [Reserve a bay](reserve-a-bay.md), [Access rules and security](access.md) |
| USB devices | per port: the device, its busid, who attached it, its current, its board target, and the port's buttons | [USB/IP and flashing](usb-and-flashing.md), [Board targets](board-targets.md) |
| Camera | live view, snapshot and light, when the bay has a camera pod | [Camera](camera.md) |
| Console | the bay's AUX UART, on a bay with one board only: the page hides it on a bay with several ports; never the console of a board on a DATA port | [Serial console](serial-console.md) |
| Wires, Logic analyzer | on a DATA ×4 only | [Wires between boards](wires.md), [Logic analyzer](logic-analyzer.md) |

The foot of the page gives the uptime, the firmware version and links to `/metrics` and `/api/status`.

```{figure} ../img/web-ui-dark.png
:class: bb-screenshot
:alt: The whole page of a bay, dark theme: Power, USB and Access cards in a row, then USB devices, Camera and Console
:width: 70%

Simulated node started without `--ports`, in the one-board form of the bench stand-ins: 5 V, one device,
busid `1-1`, an AUX console. Most screenshots and much older text show this form, and no v1.0 bay looks like
it: there the Power card reads the 20 V of the DATA lead and loses its Reset and Boot buttons, the USB
devices card has a row per port, and the Console card is not shown
([A bay that holds one board](names.md#a-bay-that-holds-one-board)).
```

## Features, what each needs, how far it is tested

<!-- site:feature-table -->
| Feature | Needs | How far it is tested |
|---|---|---|
| [USB/IP](usb-and-flashing.md), a board's USB on a Linux machine | either DATA board | [bench](../plan/status.md#status-usbip): a XIAO ESP32-S3 stand-in, never through a DATA board |
| [Power per port](power-and-reset.md): on, off, cycle, current, over-current | either DATA board | [simulated](../plan/status.md#status-power): native_sim, against emulated DATA boards |
| The [power budget](power-budget.md): the hub's grant, ports that wait | either DATA board and the hub | [simulated](../plan/status.md#status-budget): native_sim, with no charger behind it |
| The [RESET and BOOT lines](power-and-reset.md#reset-and-bootloader) of a port | a DATA ×4, with jumpers to the board | [simulated](../plan/status.md#status-power): native_sim |
| The [serial console](serial-console.md): the board's own USB serial, or the bay's AUX UART for one board wired by hand | | [simulated](../plan/status.md#status-console): native_sim; the page's console seen on a XIAO stand-in |
| [Wires between boards](wires.md) | a DATA ×4 | [simulated](../plan/status.md#status-wires): native_sim, against emulated chips |
| The [logic analyzer](logic-analyzer.md) | a DATA ×4 whose analyzer image has been loaded once | [bench](../plan/status.md#status-analyzer): a XIAO stand-in with a Pico 2; the capture from a reset in simulation only |
| The [camera](camera.md) | a camera pod on the bay | [simulated](../plan/status.md#status-camera): the simulated node; no camera has been on a node |
| [Board targets](board-targets.md) and [twister's hardware map](twister.md) | a Linux host for twister | [simulated](../plan/status.md#status-twister): the simulated node; twister has never run against a rack |
| [Access rules](access.md) and [reservations](reserve-a-bay.md) | any bay | [simulated](../plan/status.md#status-access): native_sim and the simulated node |
| [Firmware updates](update-firmware.md) over the network | the admin key | [bench](../plan/status.md#status-update): update and rollback on a XIAO stand-in, 2026-11-03 |
| [Classic mode](front-port.md), a laptop on the bay's front port | either DATA board | [written](../plan/status.md#status-modes): no stand-in has the USB switches, so it has never run |
<!-- /site:feature-table -->

## Four ways to drive it

Nearly every action exists four times; [Every action, four ways](../reference/index.md) sets them side by
side.

| Interface | Where it is | Described on |
|---|---|---|
| The bay's page | `http://bay-b3.local/` in a browser | this page |
| `bayctl` | `python tools/bayctl.py` on a laptop or a CI host; it names boards by place, `B3.2` | [Set up bayctl and usbip](set-up-your-machine.md) |
| HTTP and JSON | port 80 of the node; what the page and `bayctl` call | [Bay node HTTP API](../reference/node-api.md) |
| The node's shell | telnet on port 23, or the node's UART pads | [Bay node shell](../reference/node-shell.md) |

`bayctl` prints text for a person; a script that needs values calls the HTTP API. The hub has a page of its
own, which switches rows and reaches a bay that has lost its Wi-Fi
([Rows and the rack's page](rack-page.md)). [A first session with a bay](first-session.md) takes one board from the
drawer to its console with the page and `bayctl`.

## With a DATA ×6, with a DATA ×4

The same node and the same firmware drive both; the node tells them apart each time it powers the DATA
lead. A bay changes kind by swapping the board ([Take out a tray, a node or a DATA board](service-a-bay.md)).

| | DATA ×6 | DATA ×4 |
|---|---|---|
| Ports | 6 | 4 |
| Boards | up to six, on edge in a slot bin | up to four, flat on a plate |
| Switch and current meter per port | yes; `bayctl` and the per-port API: ports 1 to 4 on firmware 0.5 | yes |
| RESET and BOOT lines | no | yes |
| Wires between boards, logic analyzer | no | yes |
| On the page | no Wires card, no Logic analyzer card, no Reset or Bootloader buttons | every card |
| busid of port 1 | `1-1.6` | `1-1.1` |

A DATA ×4 also exists in a base assembly, with the RESET and BOOT lines and without the wires and the
analyzer ([DATA ×4](../reference/pcbs/data-x4.md)).
