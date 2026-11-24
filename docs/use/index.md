# What a bay can do

A bay is one drawer of boards with a bay node under it. The node switches each board on and off and shares its
USB over the network. You drive the bay from its web page: `http://bay-b3.local/` for bay B3.

A rack has one bay or many, and every bay works the same way. If someone else built the rack, start with
[Take over a rack](take-over-a-rack.md). To try a bay from start to finish, follow
[A first session with a bay](first-session.md).

```{figure} ../img/viewer/b3-drawer-out.jpg
:alt: The 3D model: bay B3's drawer pulled out, four boards on its plate, a DATA ×4 standing at its back

The 3D model: bay B3 with its drawer out. Each board on the plate has a cable to a port of the DATA ×4 at the
back.
```

## What you can do with a board

| What you can do | What it needs | Page |
|---|---|---|
| Switch a board on, off or cycle it, and read its current | any bay | [Power-cycle or reset a board](power-and-reset.md), [Power budget and queued ports](power-budget.md) |
| Pulse its RESET line, start its bootloader | a DATA ×4 and a jumper wire to the board | [Power-cycle or reset a board](power-and-reset.md#reset-and-bootloader) |
| Use its USB on your machine, to flash and debug it | a Linux machine with `usbip` | [USB/IP and flashing](usb-and-flashing.md) |
| Read its serial console | a Linux machine with `usbip` | [Serial console](serial-console.md) |
| Connect its pins to another board's | a DATA ×4 | [Wires between boards](wires.md) |
| Capture its pins with a logic analyzer | a DATA ×4 | [Logic analyzer](logic-analyzer.md) |
| Watch it with a camera | a camera pod over the bay | [Camera](camera.md) |
| Run twister, labgrid or LAVA on it | a Linux CI host | [Set up a CI host](ci-host.md) |
| Plug a laptop straight into it | any bay | [Front port and classic mode](front-port.md) |
| Share the bay with others | any bay | [Reserve a bay](reserve-a-bay.md), [Control who can use the rack](access.md) |

## Four ways to drive a bay

| Interface | Where | Reference |
|---|---|---|
| The bay's page | `http://bay-b3.local/` in a browser | the pages linked above |
| `bayctl` | `python tools/bayctl.py` on a laptop or a CI host | [bayctl](../reference/bayctl.md) |
| HTTP and JSON | port 80 of the node | [Bay node HTTP API](../reference/node-api.md) |
| The node's shell | telnet on port 23 | [Bay node shell](../reference/node-shell.md) |

`bayctl` is the rack's command-line tool. It names a board by its place in the rack, such as `B3.2`
([Bays, ports and addresses](names.md)). To install it, see [Set up your machine](set-up-your-machine.md).
[Actions and their commands](../reference/index.md) shows each action in all four interfaces.

The power hub feeds the whole rack. Its page, `http://rack.local/`, shows every bay and switches whole rows
([The rack's page](rack-page.md)).

## A bay from the front

| Part | What it does |
|---|---|
| The drawer | Holds the boards. It slides out, and a drag chain keeps every board connected ([Put a board in a bay](mount-a-board.md)). |
| The DATA board | Stands at the back of the drawer. Each board's USB cable goes into one of its ports: six on a DATA ×6, four on a DATA ×4. |
| The status LED | Under the drawer. {led}`blue` Blue: a board is ready to attach. {led}`green` Green: a machine has attached it. {led}`red blink` Blinking red: a port has tripped ([LEDs, buttons and switches](../reference/leds-and-buttons.md)). |
| The PC port and the SERVICE switch | A laptop on the PC port sees the bay's boards directly. With SERVICE on, it reaches the node instead ([Front port and classic mode](front-port.md)). |
| BOOT and RESET | The node's two buttons. Reach them with a pin through the two holes in the drawer floor and the plate. |

## DATA ×6 or DATA ×4

Each bay has one DATA board, of either kind. The same node and firmware drive both. You can swap one for the
other later ([Take a bay apart](service-a-bay.md)).

| | DATA ×6 | DATA ×4 |
|---|---|---|
| Boards | one on the plate, or up to six on edge in a slot bin | up to four on the plate |
| Power switch and current meter per port | yes | yes |
| RESET and BOOT lines per port | no | yes |
| Wires between boards, logic analyzer | no | yes |

A DATA ×4 can also be built without its pin matrix and co-processor (`x4: base` in `config/rack.yaml`). It
keeps the RESET and BOOT lines, but has no wires and no analyzer ([DATA ×4](../reference/pcbs/data-x4.md)).

## Before you touch a bay

- Screw the rack to the bench before you pull out a drawer of the top row
  ([Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md)).
- Do not put a board with a battery in a bay ([Put a board in a bay](mount-a-board.md#no-battery-on-a-board-in-the-rack)).
- Plug nothing but a row cable into a node's ROW OUT socket.
- Never plug or unplug the DATA lead, the cable from the node to the DATA board, while the bay has power
  ([Take a bay apart](service-a-bay.md)).
- Hold the node's BOOT button for 1 s and every board of the bay power-cycles. Hold it for 10 s and the node
  forgets its admin key and its access rules ([LEDs, buttons and switches](../reference/leds-and-buttons.md)).
- `west flash --erase` on a node wipes everything the node has stored ([Recover a node or the hub](recover.md)).
