# Known issues, and what will not work

A board in a bay gets full-speed USB over the network, never high speed, and no new revision changes that:
the sections headed *By design* hold limits of that kind. What is known to be wrong on the v1.0 PCBs and in
firmware 0.5 can be fixed by a next revision or release. What is only untested is on
[What exists today](../plan/status.md).

Nothing on this page was found on a rack: no rack exists. Every line comes from the design, from the code or
from a review of the layout, and a few from the bench stand-ins, where the line says so.

## By design: USB

Over USB/IP a board's USB passes through the bay node's ESP32-S3 and the Wi-Fi network.

| What does not pass | Why |
|---|---|
| High speed | The ESP32-S3 has one full-speed USB port: 12 Mbit/s for the whole bay, shared by its boards |
| A CMSIS-DAP v1 probe (HID), such as the UNO R4 WiFi's own | It needs interrupt OUT transfers. The bay node's USB host does control, bulk and interrupt IN |
| Audio and video devices | No isochronous transfers |
| A low-speed device behind a DATA board, such as a keyboard | The USB host does not handle low speed behind a hub |
| A seventh device on one bay node | Six USB/IP sessions a node: the six boards of a DATA ×6, or the four of a DATA ×4, its co-processor and a spare |
| A second machine on a board that is already attached | A device takes one USB/IP client |
| A session across a reset | The session ends when the board leaves the bus. `bayctl attach --follow` attaches it again |
| A continuous 921600 Bd stream through a USB-serial bridge | The bridge overflows between two reads over Wi-Fi. 115200 Bd passed on a XIAO stand-in (2026-10-22), and the throughput measured there is enough for 230400 Bd. A board's own USB serial holds its data until it is read |

A board that carries a USB hub of its own, behind the DATA board's, has not been tried. The firmware's notes
still say that such a board does not work over USB/IP; that sentence was written before the bay node drove
a hub at all.

`usbip` and `bayctl attach` need a Linux kernel. What exists for the other systems is on
[USB/IP and flashing](../use/usb-and-flashing.md#on-macos-or-windows).

None of these limits is in the way of a laptop on the bay's front port: classic mode is an analog path to
the laptop's own USB, at 480 Mbit/s ([Front port and classic mode](../use/front-port.md)). It needs the bay
node powered and its firmware running, and it has never been tried.

## By design: network and access

| Limit | What it means |
|---|---|
| Wi-Fi only | A bay node and the hub have no Ethernet. The rack bus carries places, power grants and the hub's commands, never a board's USB |
| IPv4 only | IPv6 is off in both firmwares |
| No TLS, no login | Rights go by source address. A bay node's telnet shell has no login of its own, and the admin key crosses the network in clear once, when a PCB is claimed |
| A refused connection is dropped | It is not reset: `usbip attach` from a machine without the right waits for its timeout |
| The hub has no rules | Anyone on the network reads the rack's page, its status, its events and its metrics. The key guards what acts |
| One client on each AUX port | TCP 4000 (raw) and 4001 (RFC 2217) take one client each. The web console still shows the traffic |
| A reservation is kept in RAM | A bay node that restarts forgets it |

What the access rules protect, and what they leave open: [Access rules and security](../use/access.md).
Keep the rack on a lab network or behind a VPN.

## By design: mechanics and power

| Limit | What it means |
|---|---|
| One bay wide | No double-width bay is designed: a board must fit one board plate, 134.5 × 159.4 mm, with its plug and its cable behind it |
| Rows of 165 mm at most | A taller row is not designed: a 185 mm row would take a 261 mm ladder |
| Four rows | The hub has four row outputs |
| A dense bay takes thin boards | Up to 19.8 mm thick, 86.5 mm long and 82 mm tall, standing on edge, and no jumper wires: a board that needs wires goes to a bay with a plate |
| No battery on a board | A board that charges a LiPo draws 0.6 to 1.2 A by itself, and a cell charging unattended in a closed drawer is a fire risk: [Put a board in a bay](../use/mount-a-board.md) |
| 20 V | 28 V is locked out in firmware 0.5, and the hub never accepts 36 or 48 V. A 140 W charger brings nothing more today: see the open questions |
| No ride-through | The charger's output is the rack's rail. A charger that cuts out, or that renegotiates through a hard reset, restarts every bay |
| It tips | A pull of 8 to 13 N at the top row tips a rack that stands free, by calculation: [Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md) |
| One bay on a desk | No camera mast, and no blank for the pin-header windows of the Quad: [One bay on a desk](../build/one-bay-on-a-desk.md) |

Which board fits which bay is checked case by case by the layout tool and listed in the
[board library](board-library.md). Every current and voltage: [Specifications](specifications.md).

## Known issues of the v1.0 PCBs

They come from the [design review of 2026-11-09](../pcb-review-2026-11-09.md), written in French two days
before the order, less what was fixed before fabrication. The review holds 65 findings: none critical, 4
major, 37 minor, 24 remarks, and no error of pinout, polarity or connection. Each is calculated or read from
the layout. None is measured.

Four fixes went into v1.0 on 2026-11-10: a 1 kΩ resistor on the bay node's fault line (BN-01), copper and
vias under the DATA ×6's 3.3 V regulator (X6-02), the DATA ×6's 5 V set to 5.08 V (X6-07), and ground vias
under the DATA ×4's co-processor (X4B-03). The two other major findings concern an order at JLCPCB only, the
DATA ×6's placement file and a part that was out of stock there: [Order the PCBs](../plan/order-the-pcbs.md#at-jlcpcb-where-nobody-has-ordered).

Each list below is written on the PCB's own page; the codes in brackets are the review's.

### Power hub

```{include} pcbs/power-hub.md
:start-after: <!-- site:known-issues -->
:end-before: <!-- /site:known-issues -->
```

### Bay node

```{include} pcbs/bay-node.md
:start-after: <!-- site:known-issues -->
:end-before: <!-- /site:known-issues -->
```

### Camera pod

```{include} pcbs/camera-pod.md
:start-after: <!-- site:known-issues -->
:end-before: <!-- /site:known-issues -->
```

### DATA ×6

```{include} pcbs/data-x6.md
:start-after: <!-- site:known-issues -->
:end-before: <!-- /site:known-issues -->
```

### DATA ×4

```{include} pcbs/data-x4.md
:start-after: <!-- site:known-issues -->
:end-before: <!-- /site:known-issues -->
```

## Known issues of firmware 0.5

Read from the code of the bay node's and the hub's firmware at version 0.5.0, and from `bayctl`.

| Issue | What it means for you |
|---|---|
| A reservation of one port does not guard its USB/IP | It guards the port's power, its reset lines and its wires. Another machine can still attach the board: reserve the whole bay ([Reserve a bay](../use/reserve-a-bay.md)) |
| The wires of a port with no VREF are not held open | A bay node v1.0 cannot read VREF, so the rule that keeps a port's pins open under 0.65 V does not exist yet. Wire VREF before you close a switch ([Wires between boards](../use/wires.md)) |
| The co-processor cannot be restarted alone | A new analyzer image runs from the next power-up of the whole DATA ×4, its boards included |
| The rack's page offers 28 V and nothing happens | The hub answers the request as done and stays at 20 V. Only its shell says why: `28 V EPR is off on this hub` |
| The hub's budget is set in its shell only | The margin, the cap and the order in which rows are shed have no API route, no control on the page and no `bayctl` command |
| The hub switches a bay as a whole | A command from the rack's page or over the rack bus acts on the bay's DATA lead: every board of the bay |
| The metrics have no figure per port | Every bay node metric carries one label, `bay` |
| No shell on the front port | In SERVICE mode the front port flashes the bay node. Its shell is on the UART test pads and over telnet |
| RFC 2217 reports no line state | The server answers a poll with CTS, DSR and CD up, whatever the lines do |
| Nothing caps the boards flashed at once | The figure of 8 a Wi-Fi channel is for you to keep: `bayctl` does not count ([Wi-Fi in the rack](../use/wifi.md)) |
| The old name shows | The help of the `bay` and `hub` shell commands, the boot log and the PDUDaemon export still say `hw-testing-rack` |

`bayctl`'s own help text and [config/lab.example.yaml](../../config/lab.example.yaml) describe a bay with a
DATA ×4 only. A DATA ×6 bay takes the same commands with ports 1 to 6 on the simulated node (on a bay node, ports 5 and 6:
see the open questions); `reset` and `boot` answer `this port has no such line`, checked against the
simulated node.

## Open questions

Six things the sources do not settle. Where one bites, its page says what the code or the design does
today.

**The Solo with a bay node v1.0.** The Solo box pairs a bay node with the single DATA port PCB, which left
the rack on 2026-10-31. That PCB wires the lead's supply straight to its USB-C and expects 5 V; a bay node
v1.0 puts 20 to 28 V on that wire. Do not build a Solo with a v1.0 bay node:
[One bay on a desk](../build/one-bay-on-a-desk.md).

**The front display.** The drawer's front has a window for a 1.9 inch display, the firmware can drive one
and the 3D model draws it. The bay node v1.0 has no connector for it, and the sources do not say which
revision will.

**Ports 5 and 6 of a DATA ×6 over HTTP.** The bay node serves `/api/ports/<n>/power`, `/reset` and `/boot`
for n from 1 to 4. The bay's page switches ports 5 and 6 through `POST /api/power` with the port in the
body; `bayctl` uses the per-port routes. The simulated node accepts any n, so the gap does not show there.

**The pin headers of a base DATA ×4.** Its design log has the base assembly take two 2 × 1 pieces per
port; its BOM lists the 2 × 6 headers of the full assembly. Either works electrically.

**28 V.** The firmware locks it out because of a 30 V inductor. The review of 2026-11-09 finds that every
inductor on the PCBs is now rated 75 V, and also that the hub has no margin at 28 V. When, and whether, the
lock opens is not decided.

**A bay with one board.** Half the bays of the example rack hold a single board, and a bay node v1.0 powers
nothing unless a DATA board answers. Which DATA board and which port a lone board takes, and what the port
is called: [Bays, ports and addresses](../use/names.md#a-bay-that-holds-one-board).

## Report a finding

A wrong value on a PCB, a part that does not fit, a step of these pages that fails on the bench: open an
issue on {{ '[the project\'s issue tracker]({}/issues)'.format(repo_url) }}. Give:

- what it is about, and which one: the PCB and which of your assembled ones, or the printed part, your
  printer and your filament;
- the page and the step or the stage where it showed;
- what you found, with the reading or the message;
- what you did to the PCB, if anything: a bodge wire, a changed value;
- for a rack that runs: the firmware's version, the bay's `/api/status` and the hub's events.

v1.0 is frozen: a fault found on a v1.0 PCB is fixed in its next revision, and listed above until then.
As of 2026-11-24 nothing has been reported: no PCB has been powered and no part printed. To change the
design yourself: [Contribute](../engineering/contribute.md).
