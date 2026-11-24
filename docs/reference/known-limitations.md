# Limitations

This page lists what a BitBunk rack cannot do, and how to work around it where you can.

## USB over the network

A board's USB reaches your machine through its bay node and the Wi-Fi network. These do not pass:

| What | Why |
|---|---|
| High speed | The bay node has one full-speed USB port, 12 Mbit/s for the whole bay |
| A CMSIS-DAP v1 probe (HID), such as the UNO R4 WiFi's | It needs interrupt OUT transfers |
| Audio and video devices | The node does no isochronous transfers |
| A low-speed device, such as a keyboard | The node does not handle low speed behind a hub |
| A seventh device on one bay node | A node serves six USB/IP sessions |
| A second machine on a board | A device takes one client |
| A session across a board's reset | It ends when the board leaves the bus. `bayctl attach --follow` attaches it again |
| A continuous 921600 Bd stream through a USB-serial bridge | The bridge overflows. Use 115200 or 230400 Bd |

`usbip` needs a Linux kernel: see [On macOS or Windows](../use/usb-and-flashing.md#on-macos-or-windows).
[USB/IP and flashing](../use/usb-and-flashing.md#which-probes-and-devices-work) lists the probes that work.

None of this applies to a laptop on the bay's front port. In classic mode, the laptop's own USB connects to
the DATA board at 480 Mbit/s ([Front port and classic mode](../use/front-port.md)). Classic mode needs the bay
node's firmware running.

## Network and access

| Limit | What it means |
|---|---|
| Wi-Fi only | A bay node and the hub have no Ethernet |
| IPv4 only | IPv6 is off in both firmwares |
| No TLS, no login | Rights go by source address. The node's telnet shell has no login. The admin key crosses the network in clear once, when you claim a node or the hub |
| A refused connection is dropped | The node does not reset it, so `usbip attach` from a machine without the right waits until it times out |
| The hub has no access rules | Anyone on the network can read the rack's page, status, events and metrics. Actions need the admin key |
| One client on each AUX port | TCP 4000 (raw) and TCP 4001 (RFC 2217) take one client each |
| Reservations live in RAM | A bay node that restarts forgets its reservation |

Keep the rack on a lab network or behind a VPN. [Control who can use the rack](../use/access.md) explains
what the access rules protect.

## Mechanics and power

| Limit | What it means |
|---|---|
| One bay wide | A board must fit one plate, 134.5 × 159.4 mm, with its plug and cable behind it ([What fits in a bay](board-library.md#what-fits-in-a-bay)) |
| Four rows, 165 mm high at most | The hub has four row outputs. A row's ladder must fit a 256 mm print bed |
| Slot bins take thin boards | Up to 19.8 mm thick, 86.5 mm long and 82 mm tall, and no jumper wires |
| Every bay needs a DATA board | A bay node powers nothing until a DATA board answers, even for a single board ([A bay that holds one board](../use/names.md#a-bay-that-holds-one-board)) |
| No pins on a DATA ×6 | It has no RESET or BOOT line and no wires. Use a DATA ×4 for those |
| No battery on a board | A board that charges a LiPo draws 0.6 to 1.2 A, and a cell charging in a closed drawer is a fire risk ([Put a board in a bay](../use/mount-a-board.md)) |
| 20 V only | The hub does not use 28 V, even when you choose *28 V EPR when offered* on the rack's page. A 140 W charger gives no more power than a 100 W one |
| No ride-through | The charger's output is the rack's supply. A charger that cuts out or resets restarts every bay |
| A rack standing free tips over | A pull of 8 to 13 N at the top row is enough: [Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md) |
| No camera on a bay on a desk | The Quad, the box for one bay on a desk, has no mount for a camera ([One bay on a desk](../build/one-bay-on-a-desk.md)) |

[Specifications](specifications.md) gives every current and voltage.

## The PCBs

These limits come from the PCBs themselves. [The five PCBs](pcbs/index.md) has a page for each PCB, with
the details and the points to check while you assemble it.

### Plugging and unplugging

- Switch a row off at the hub before you plug or unplug a row cable. A node plugged into a live row pulls
  the row's voltage down, and its neighbours may restart.
- Switch a bay's power off before you plug or unplug its DATA lead. The connector has no ground pin that
  mates first, so the lead's 20 V can reach the signal wires. It can destroy the node's I²C pins, its meter
  or the DATA board's USB hub.
- Do not plug the AUX lead into ROW OUT. The two connectors take the same plug and sit 22 mm apart. On the
  last node of a row, ROW OUT is free. An AUX lead plugged there puts VRACK on its BOOT wire and into your
  board. AUX is 3.3 V, with no level shifting and no ESD protection.
- After you unplug the charger, wait a few seconds before you plug it back in. The hub's supply takes 2 to 6 s
  to drain, and a charger plugged back in sooner may refuse the hub.
- Connect the hub's console port with a USB-C to USB-C cable. A live USB-A port can overstress the hub's
  3.3 V regulator as it is plugged in.

### Power and faults

- A short on a DATA lead can restart the whole row. The lead's limit, 1.76 A, is above the row's, 1.6 A,
  so the hub's limit acts first. The row's voltage drops until the node cuts the lead, and the other bays of
  the row restart.
- A DATA lead shorted while powered can destroy the node's meter. The node then never powers the lead
  again, and the bay stays out of service.
- After a power cut of a few seconds, ports that were on may come back on by themselves before the node
  takes over. On a DATA ×4 a board may also see a reset pulse.
- A port of a DATA ×4 keeps its VBUS near 2.5 V for many seconds after it is switched off. A board with no
  brown-out detection may start badly after a short power cycle.
- On a DATA ×6, a board with two USB cables needs both in ports 1 to 3, or both in ports 4 to 6. If they are
  split across the two groups, a port's switch latches off.

### Wires and camera

- On a DATA ×4, wire a port's VREF before you close one of its switches. Without VREF the port is not
  isolated: low levels pass and high levels are clamped near 0.4 V. Nothing is damaged.
- An idle bus of the DATA ×4 sits at 2.1 to 2.8 V until the analyzer image is loaded. A signal pulled up only
  by the bus may not reach a 3.3 V board's high level. Push-pull signals and I²C with pull-ups on
  the boards work.
- For I²C at 1.8 V over a wire, leave the bus's 2.2 kΩ pull-ups off.
- A camera that hangs comes back only when its row is power-cycled. The camera has no reset line, and the
  node cannot switch its 5 V.
- While the camera's light is dimmed, a picture is corrupted now and then. With the light fully on or off,
  pictures are fine.

## The firmware

| Limit | What it means |
|---|---|
| A reservation of one port does not guard its USB | Another machine can still attach the board. Reserve the whole bay ([Reserve a bay](../use/reserve-a-bay.md)) |
| Ports 5 and 6 of a DATA ×6 have no routes of their own over HTTP | `/api/ports/<n>/power`, `/reset`, `/boot` and `/board` take n from 1 to 4, so `bayctl power B3.5` fails. Switch ports 5 and 6 from the bay's page or with `POST /api/power` and `"port"`, and give their board targets in [config/lab.yaml](lab-yaml.md) |
| The co-processor of a DATA ×4 does not restart alone | A new analyzer image runs from the next power-up of the whole DATA ×4, its boards included |
| The hub switches a bay as a whole | A command from the rack's page or over the rack bus acts on every board of the bay |
| The hub's budget is set in its shell only | The margin, the cap and the order in which rows are shed have no API route, no control on the page and no `bayctl` command ([Power hub shell](hub-shell.md)) |
| Nothing limits how many boards flash at once | Keep to eight per Wi-Fi channel yourself ([Wi-Fi for the rack](../use/wifi.md#how-many-boards-may-flash-at-once)) |
| No figure per port in the metrics | Every bay node metric has one label, `bay` |
| No shell on the front port | In SERVICE mode the front port flashes the bay node. Its shell is on the UART test pads and over telnet |
| RFC 2217 reports no line state | The AUX port answers CTS, DSR and CD up, whatever the lines do |

## Report a problem

If something on this site is wrong, or a part or a step does not work for you, open an issue on
{{ '[the project\'s issue tracker]({}/issues)'.format(repo_url) }}. Give:

- which PCB or printed part, and for a printed part your printer and filament;
- the page and the step where you found it;
- what you found, with the reading or the message;
- anything you changed on the PCB, such as a bodge wire or a new value;
- for a rack that runs: the firmware's version, the bay's `/api/status` and the hub's events.
