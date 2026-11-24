# Actions and their commands

This page lists what you can do to a board, a bay or the whole rack. For each action it gives the button on
the web page, the `bayctl` command, the HTTP request and the shell command. A dash means that interface
cannot do it. Each cell links to the full entry.

The examples use bay B3, which has a DATA ×4, and B3.2, the board on its port 2. HTTP requests go to
`bay-b3.local`, or to `rack.local` for the rack. `bayctl` prints text meant for people. A script should read
the JSON of the HTTP API instead.

## One board

{.bb-ways-table}
| Action | Bay's page | bayctl | HTTP | Shell |
|---|---|---|---|---|
| Read its port | [its row of **USB devices**](../use/power-and-reset.md) | [`ports B3`](bayctl.md#status-and-ports) | [`GET /api/ports`](node-api.md#ports-of-a-data-board) | [`bay port`](node-shell.md#shell-bay-port) |
| Switch it on or off | [**Power on**, **Off**](../use/power-and-reset.md) | [`power B3.2 on`](bayctl.md#power) | [`POST /api/ports/2/power`](node-api.md#ports-of-a-data-board)<br>`{"action":"on"}` | [`bay port 2 on`](node-shell.md#shell-bay-port) |
| Power-cycle it | [**Cycle**](../use/power-and-reset.md) | [`power B3.2 cycle`](bayctl.md#power) | [`POST /api/ports/2/power`](node-api.md#ports-of-a-data-board)<br>`{"action":"cycle"}` | [`bay port 2 cycle`](node-shell.md#shell-bay-port) |
| Switch it on once the budget has room | [**As soon as possible**, **Power on**](../use/power-budget.md) | [`power B3.2 on --when available`](bayctl.md#power) | [`{"action":"on","when":"available"}`](node-api.md#power-reset-bootloader-and-mode) | – |
| Cancel that request | [**Cancel**](../use/power-budget.md) | [`power B3.2 cancel`](bayctl.md#power) | [`{"action":"cancel"}`](node-api.md#power-reset-bootloader-and-mode) | – |
| Reset it (DATA ×4) | [**Reset**](../use/power-and-reset.md) | [`reset B3.2`](bayctl.md#reset-and-boot) | [`POST /api/ports/2/reset`](node-api.md#power-reset-bootloader-and-mode) | [`bay port 2 reset`](node-shell.md#shell-bay-port) |
| Start its bootloader (DATA ×4) | [**Bootloader**](../use/power-and-reset.md) | [`boot B3.2`](bayctl.md#reset-and-boot) | [`POST /api/ports/2/boot`](node-api.md#power-reset-bootloader-and-mode) | [`bay port 2 boot`](node-shell.md#shell-bay-port) |
| Start its bootloader across a power cycle | [**Bootloader** of a port that is off](../use/power-and-reset.md) | [`boot B3.2 --power-cycle`](bayctl.md#reset-and-boot) | [`{"power_cycle":true}`](node-api.md#power-reset-bootloader-and-mode) | [`bay port 2 boot cycle`](node-shell.md#shell-bay-port) |
| Attach its USB to a Linux machine | [**Copy attach**](../use/usb-and-flashing.md) | [`attach B3.2`](bayctl.md#attach-and-detach) | – | – |
| Detach it | – | [`detach B3.2`](bayctl.md#attach-and-detach) | – | – |
| Set its board target | [**Set board…**](../use/board-targets.md) | [`import lab rack-targets.yaml B3.2`](bayctl.md#export-lab-and-import-lab) | [`PUT /api/ports/2/board`](node-api.md#usb-devices-and-board-targets) | – |

USB/IP does not go through HTTP. It has its own port, TCP 3240. On Linux you can attach a board without
`bayctl` ([USB/IP and flashing](../use/usb-and-flashing.md)):

```console
$ sudo usbip attach -r bay-b3.local -b 1-1.2
```

## One bay

{.bb-ways-table}
| Action | Bay's page | bayctl | HTTP | Shell |
|---|---|---|---|---|
| Read the bay's state | [the whole page](../use/index.md) | [`status B3`](bayctl.md#status-and-ports) | [`GET /api/status`](node-api.md#api-status-field-by-field) | [`bay status`](node-shell.md#shell-bay-status) |
| Power-cycle every board | [**Power** card: **Cycle**](../use/power-and-reset.md) | [`power B3 cycle`](bayctl.md#power) | one [`POST /api/ports/<n>/power`](node-api.md#ports-of-a-data-board) per port | [`bay power cycle`](node-shell.md#shell-bay-power) |
| List the USB devices | [**USB devices**](../use/usb-and-flashing.md) | [`status B3`](bayctl.md#status-and-ports) | [`GET /api/usb`](node-api.md#usb-devices-and-board-targets) | [`bay usb`](node-shell.md#shell-bay-usb) |
| Force classic mode | [**USB** card: **Classic**](../use/front-port.md) | [`mode B3 classic`](bayctl.md#mode) | [`POST /api/mode`](node-api.md#power-reset-bootloader-and-mode)<br>`{"mode":"classic"}` | [`bay mode classic`](node-shell.md#shell-bay-mode) |
| Open the AUX console | – | – | [`GET /console/ws/0?t=…`](node-api.md#console) | – |
| Change the AUX console's baud rate | – | – | [`POST /api/aux`](node-api.md#console)<br>`{"baud":921600}` | [`bay aux 921600`](node-shell.md#shell-bay-aux) |
| Send a BREAK on the AUX console | – | – | [`POST /api/aux/break`](node-api.md#console) | [`bay aux break`](node-shell.md#shell-bay-aux) |
| Join pins (DATA ×4) | [**Wires**: **Apply**](../use/wires.md) | [`wire B3 A=2:P1,3:P2`](bayctl.md#wire) | [`POST /api/wires`](node-api.md#wires-analyzer-and-co-processor) | – |
| Capture (DATA ×4) | [**Logic analyzer**: **Capture**](../use/logic-analyzer.md) | [`capture B3 --ch A`](bayctl.md#capture) | [`GET /analyzer/ws?t=…`](node-api.md#wires-analyzer-and-co-processor) | – |
| Hand the analyzer to USB/IP | [**Logic analyzer**: **USB/IP**](../use/logic-analyzer.md) | – | [`POST /api/analyzer`](node-api.md#wires-analyzer-and-co-processor)<br>`{"owner":"usbip"}` | – |
| Take a snapshot | [**Snapshot**](../use/camera.md) | – | `GET http://bay-b3.local:8081/snapshot.jpg` | – |
| Change a camera setting | [**Camera**: the picture's settings](../use/camera.md) | – | [`POST /api/camera`](node-api.md#camera)<br>`{"white_balance":"cloudy"}` | [`bay camera set white_balance cloudy`](node-shell.md#shell-bay-camera) |

`bay power cycle` switches the whole DATA lead off and on, so every board in the bay restarts at once. The
ports of a DATA ×6 have no RESET or BOOT line.

The bay's page shows no console, because every bay has a DATA board. A board's console is a serial port on
its own USB. To reach the bay's AUX UART, connect to TCP port 4001 with RFC 2217, or to TCP port 4000 for raw
bytes ([Serial console](../use/serial-console.md)).

## The whole rack

{.bb-ways-table}
| Action | Rack's page | bayctl | HTTP, on rack.local | Hub's shell |
|---|---|---|---|---|
| Read the rows and the bays | [`http://rack.local/`](../use/rack-page.md) | [`hub status`](bayctl.md#hub) | [`GET /api/status`](hub-api.md#api-status-field-by-field) | [`hub status`](hub-shell.md) |
| Switch a row off | [the row's **Off**](../use/rack-page.md) | [`row B off`](bayctl.md#row) | [`POST /api/row`](hub-api.md#rows-the-contract-and-the-bays)<br>`{"row":"B","action":"off"}`, signed | [`hub row B off`](hub-shell.md) |
| Power-cycle a row | [the row's **Cycle**](../use/rack-page.md) | [`row B cycle`](bayctl.md#row) | [`POST /api/row`](hub-api.md#rows-the-contract-and-the-bays)<br>`{"row":"B","action":"cycle"}`, signed | [`hub row B cycle`](hub-shell.md) |
| Make a bay's LED blink | [**Identify: blink its LED**](../use/rack-page.md) | [`hub node B3 identify`](bayctl.md#hub) | [`POST /api/node`](hub-api.md#rows-the-contract-and-the-bays)<br>`{"id":19,"action":"identify"}`, signed | [`hub node B3 identify`](hub-shell.md) |
| Power-cycle a bay over the rack bus | [**Power-cycle the board**](../use/rack-page.md) | [`hub node B3 power-cycle`](bayctl.md#hub) | [`POST /api/node`](hub-api.md#rows-the-contract-and-the-bays)<br>`{"id":19,"action":"power-cycle"}`, signed | [`hub node B3 power-cycle`](hub-shell.md) |
| Renumber the bays on the rack bus | [**Re-enumerate**](../use/rack-page.md) | [`hub enumerate`](bayctl.md#hub) | [`POST /api/enumerate`](hub-api.md#rows-the-contract-and-the-bays), signed | [`hub enumerate`](hub-shell.md) |
| Set the shed order, the margin or a power cap | – | – | – | [`hub shed DCBA`, `hub budget cap 60`](hub-shell.md) |

The rack bus is the CAN link in the row cables, between the power hub and the bay nodes. It reaches a bay
even when the bay has no Wi-Fi. A node's id on the bus is 16 times the row's index (A is 0), plus the
column number: B3 is 19 (0x13). While a bay is reserved, its node refuses every command from the hub except
`identify`.

## Access and reservations

{.bb-ways-table}
| Action | Bay's page | bayctl | HTTP | Shell |
|---|---|---|---|---|
| See the rights, the reservation and the connections | [**Access** card](../use/access.md) | [`access show B3`](bayctl.md#access) | [`GET /api/access`](node-api.md#access-and-reservations) | [`bay access`](node-shell.md#shell-bay-access) |
| Reserve the bay | [**Reserve…**](../use/reserve-a-bay.md) | [`lease B3 --for 1h`](bayctl.md#lease-and-release) | [`POST /api/lease`](node-api.md#access-and-reservations)<br>`{"ttl_s":3600}` | – |
| Reserve one board | [**Reserve…**, B3.2 ticked](../use/reserve-a-bay.md) | [`lease B3.2`](bayctl.md#lease-and-release) | [`{"ttl_s":3600,"ports":["B3.2"]}`](node-api.md#access-and-reservations) | – |
| End a reservation | [**Release**](../use/reserve-a-bay.md) | [`release B3`](bayctl.md#lease-and-release) | [`POST /api/lease`](node-api.md#access-and-reservations)<br>`{"release":true}` | [`bay access release`](node-shell.md#shell-bay-access) |
| Close a connection | [**Kick**](../use/access.md) | [`access kick B3 usbip:51234`](bayctl.md#access) | [`POST /api/access/kick`](node-api.md#access-and-reservations), signed | – |
| Give a node the admin key (claim it) | [**Claim this bay…**, then BOOT](../use/access.md) | [`access claim B3`](bayctl.md#access) | [`POST /api/access/claim`](node-api.md#access-and-reservations) | [`bay access claim`](node-shell.md#commands-that-need-the-test-pads), on the test pads |
| Apply the access rules | [**Manage access…**](../use/access.md) | [`access push B3`](bayctl.md#access) | [`POST /api/access/rules`](node-api.md#access-and-reservations), signed | [`bay access on`](node-shell.md#shell-bay-access) |

`bay access on` turns on the rules the node already has. The shell cannot change the rules.

## Firmware and maintenance

{.bb-ways-table}
| Action | Bay's page | bayctl | HTTP | Shell |
|---|---|---|---|---|
| Update a node's firmware | [**Manage access…**: **Update…**](../use/update-firmware.md) | [`update build-bay/bay-node/zephyr/zephyr.signed.bin B3`](bayctl.md#update) | [`POST /api/update/begin`, then `/api/update?ticket=…`](node-api.md#firmware-update) | – |
| Update the hub's firmware | [rack's page: **Update firmware…**](../use/update-firmware.md) | [`update build-hub/power-hub/zephyr/zephyr.signed.bin --hub`](bayctl.md#update) | [the same on rack.local](hub-api.md#firmware-update) | – |
| Store the co-processor's image (DATA ×4) | – | [`coproc load B3 LogicAnalyzer.uf2`](bayctl.md#coproc) | [`POST /api/coproc/begin`](node-api.md#wires-analyzer-and-co-processor) | [`bay coproc`](node-shell.md#shell-bay-coproc), to read it |
| Read the last fatal error | [the foot of the page: `restarted after …`](../use/index.md) | – | [`GET /api/status`, `last_fault`](node-api.md#api-status-field-by-field) | [`bay fault`](node-shell.md#shell-bay-fault) |
| Read the Prometheus metrics | – | – | [`GET /metrics`](network.md#metrics-of-a-bay-node) | – |
| Set the Wi-Fi transmit power | – | – | – | [`radio 11`](node-shell.md#shell-radio) |
| Give the bay an id | – | – | – | [`bay id b3`](node-shell.md#shell-bay-id) |
