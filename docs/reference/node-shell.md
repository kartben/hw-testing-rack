# Bay node shell

A bay node's shell takes the `bay` commands, `radio`, and Zephyr's own `wifi` and `net`, on two consoles:
the UART test pads on the bottom side of the board, and telnet on TCP 23 once the node is on the network.

:::{status} bench
The shell ran over telnet on the XIAO ESP32-S3 stand-in, with the one-board commands. `bay port` and the
DATA boards' answers run on native_sim against emulated boards only. No command has run on a v1.0 bay
node. See [What exists today](../plan/status.md#status-bay-page).
:::

## Where the shell is

| Console | How to reach it | Who may use it |
|---|---|---|
| UART0 test pads | TP1 = TXD0, TP2 = RXD0, 115200 8N1, with a 3.3 V USB-UART | whoever holds the node: the pads are on the bottom side |
| telnet, TCP 23 | `telnet bay-b3.local` | one client at a time, no login: the addresses that the access rules give the `shell` right |

The front USB-C port gives no shell: in SERVICE mode it reaches the module's USB-Serial-JTAG, for flashing,
and a shell on it is not written yet. A stand-in (XIAO ESP32-S3, M5Stack CoreS3) has the local shell on its
own USB console instead of the pads. Who gets the `shell` right, and why telnet has no password of its own:
[Access rules and security](../use/access.md).

## The commands

In the order [shell.c](../../firmware/bay-node/src/shell.c) registers them, then those of
[common/lib/net.c](../../firmware/common/lib/net.c) and Zephyr's, typed at the `uart:~$` prompt. A wrong
argument prints the command's usage line.

| Command | What it does | What it can answer |
|---|---|---|
| [`bay fault`]{#shell-bay-fault} | The fatal error that last restarted the node and the log before it, then the warnings and errors since this boot. Gone after a power cut | `no fatal error since power-on` |
| [`bay status`]{#shell-bay-status} | Bay id and host name, address, `restarted: after a …`, the rack position and the hub, the data path, the USB host and its USB/IP sessions, the power and the budget, faults since boot, the AUX UART, the camera | `network: down`; `rack: standalone (no hub has addressed it)`, `rack: no position (not enumerated by the hub)`; `hub silent` |
| [`bay power`]{#shell-bay-power} | The bay's supply: on or off, a fault, mV, mA, mW; why the DATA lead is off; the budget line `Budget: <draw> of <limit> mW (the hub's grant), <n> port(s) waiting, <n> shed since boot` | `DATA lead: off, <reason>` |
| `bay power on` / `off` | Switches the bay's supply: on a v1.0 node the DATA lead's 20 to 28 V, every board of the bay at once. `on` also clears a latched fault | `DATA_VIN stays off: <reason>` |
| `bay power cycle [ms]` | Off, 1000 ms unless `ms`, on | `DATA_VIN stays off: <reason>`; `duration must be 1..60000 ms` |
| [`bay reset [ms]`]{#shell-bay-reset} | Pulses the RESET line of the node's AUX connector low, 100 ms unless `ms`. `hold` and `release` instead hold and let go | `duration must be 1..60000 ms` |
| [`bay boot`]{#shell-bay-boot} | Holds the AUX connector's BOOT line, pulses RESET, lets BOOT go 200 ms later: the ROM bootloader of most MCUs. `hold` and `release` act on BOOT alone | |
| [`bay mode [usbip\|classic]`]{#shell-bay-mode} | Alone: the data path, classic `forced` or `auto`, SERVICE, the front port `plugged` or `absent`. `classic` forces classic mode, `usbip` lets it go; saved | |
| [`bay usb`]{#shell-bay-usb} | Two lines a device: busid, vid:pid, name and maker; hub or device, serial number, `read ahead`, `attached by <address> for <n> s` | `no USB device`; `USB host busy, try again` |
| [`bay port`]{#shell-bay-port} | The DATA board and one line a port: `port 2 (1-1.2): on, <mV> mV <mA> mA, <n> faults, a USB device`, with `(fault)` or `(off by hand)` after `on` or `off` | `no DATA board answering: a one-port node`; `a board answers at 0x20, but neither as a DATA x4 nor as a DATA x6: left alone, its ports off` |
| `bay port <n> on` / `off` | One port. `on` goes through the bay's budget and clears the port's latched fault | `no room in the budget: the bay draws <n> mA`; `port <n>: VBUS up while off (powered from elsewhere); on once gone` |
| `bay port <n> cycle [ms]` | Off, then on. Without `ms` the port stays off until its VBUS reads under 1 V, 2 s at most | the same; `duration must be 1..60000 ms` |
| `bay port <n> reset` | A 100 ms pulse on the port's RESET line | `port <n> has no RESET or BOOT line (a DATA x6)` |
| `bay port <n> boot [cycle]` | BOOT held across a RESET pulse; with `cycle`, across a power cycle of the port | the same; `no room in the budget: …` |
| [`bay aux`]{#shell-bay-aux} | The AUX UART: baud and format, Enter, echo, esptool reset; web consoles connected, RFC 2217 and raw TCP `in use` or `free`; bytes received, sent and dropped | |
| `bay aux <baud> [8N1]` | Sets and saves the baud rate and the format: data bits 5 to 8, `N`, `O` or `E`, stop bits 1 or 2 (`7E1`, `8O2`) | `the AUX UART refused <baud> <format> (<errno>)` |
| `bay aux break [ms]` | Holds the board's RX line low, 250 ms unless `ms` | `BREAK failed (<errno>): DUT is off` |
| `bay aux send <text>` | One line to the board, then the console's Enter. Quote a text with spaces: it is one argument | |
| `bay aux loopback [on\|off]` | A test without a board: the UART loops its TX back to its RX | `no UART loopback on this SoC (<errno>)` |
| [`bay camera`]{#shell-bay-camera} | Model, port, clients, frames, errors, the light, then each setting | `no camera` |
| `bay camera set <name> <value>` | One setting, saved: `exposure auto`, `manual` or 0 to 30000; `gain auto`, `manual` or 0 to 1023; `white_balance auto`, `sunny`, `office`, `cloudy`, `home`; `brightness` −4 to 4; `contrast`, `saturation` −3 to 3; `sharpness auto` or 1 to 8; `rotation 0`, `90`, `180`, `270`; `resolution`; `quality`; `light` | the setting's own text: `brightness: -4 to 4`, `sharpness: not on this camera`, … |
| `bay camera reset` | The image settings back to automatic, saved; resolution, quality, light and rotation stay | |
| [`bay coproc`]{#shell-bay-coproc} | The DATA ×4 co-processor's stored image, its upload and its loads, as the JSON of `GET /api/coproc` | `no room for the state` |
| [`bay access`]{#shell-bay-access} | Admin key `set (claimed)` or `none (not claimed)`, a pending claim, the rules and each source's services, `everyone else`, the bay's reservation and each port's, the connections, refusals since boot | |
| `bay access claim` | Confirms a pending claim, as a short press on BOOT does. Not over telnet | `no claim pending: start one from the web page or bayctl`; `claimed: the requester gets the admin key`, `(not saved)` |
| `bay access on` / `off` | Applies the rules / lets every address use everything. `off` not over telnet | |
| `bay access release` | Ends the bay's reservation and every port's | `no lease` |
| `bay access reset` | Forgets the admin key, the rules and the reservation. Not over telnet | `no admin key, no rules, no lease: the node is open until claimed again` |
| [`bay id [id]`]{#shell-bay-id} | Shows or sets the bay id, saved; the host name becomes `bay-<id>.local` | `hostname bay-b3.local`; `id: 1-15 characters, letters, digits and '-'` |
| [`radio [<dBm>]`]{#shell-radio} | Alone: the TX power asked, the power in the radio, the channel width. With a number, sets and saves it, 2 to 20 dBm; 11 dBm by default | `TX power: 2 to 20 dBm` |
| [`heaps`]{#shell-heaps} | Every heap: address, size, free, used, most used. Built where the board keeps an array of its heaps | |
| [`display`]{#shell-display} | The front display's refresh times. Built only with the front display, which no v1.0 node has a connector for | |
| [`wifi`, `net`]{#shell-wifi} | Zephyr's own: `wifi cred add`, `wifi cred auto_connect`, `wifi status`, `net iface`, … | |

## The DATA lead's reasons

`bay power` and `bay status` print why a v1.0 node keeps its DATA lead off, and `bay power on` fails with
the same text after `DATA_VIN stays off:`. The six texts, from
[dut.c](../../firmware/bay-node/src/dut.c):

- `SCL or SDA held low: DATA lead reversed?`
- `the node's INA226 does not answer`
- `no DATA_VIN after switching on: a short on the lead (a camera lead in J7?)`
- `the eFuse reported a fault`
- `no DATA board answers: none, or the wrong lead in J7`
- `the DATA board stopped answering`

What each one means and what to check: [States and error messages](states-and-messages.md).

## Refused over telnet

`bay access claim`, `bay access off` and `bay access reset` want someone at the node. Over telnet they
answer `only on the node's own console (UART pads), not over telnet`; `bay access on` and `bay access
release` work. Without the pads, BOOT does two of the three: a short press confirms a claim, a press of
10 s or more resets access control. A node whose key is lost: [Recover a node or a hub](../use/recover.md).

## Notes on the commands

- A duration in the shell goes from 1 to 60000 ms. The HTTP API takes 1 to 10000
  ([Bay node HTTP API](node-api.md#power-reset-bootloader-and-mode)).
- On a v1.0 node the budget is counted in mW on the DATA lead, and `no room in the budget: the bay draws <n>
  mA` then gives that number in mW: the text says mA whatever the unit. `bay power` and the HTTP API print
  the right unit.
- `bay power` switches the whole DATA lead. Once the lead is on again, every port that was not switched off
  by hand comes back on, one after the other, 300 ms apart.
- Some help texts carry the project's old name and the first board: `bay` with no command prints
  `hw-testing-rack bay node`, and the help of `bay port` says `DATA x4 ports` though it serves a DATA ×6 too.
- Planned and not written: `radio quiet <s>`, which would quiet the node's radio during a board's RF test,
  and `bay coproc reload`. Neither command exists in firmware 0.5.0.
- `bay mode`, `bay aux <baud>`, `bay camera set`, `bay id`, `radio` and the Wi-Fi credentials are saved in
  the node's flash and survive a restart. What a node remembers and how to erase it:
  [Recover a node or a hub](../use/recover.md).

## Examples

```console
uart:~$ bay port
uart:~$ bay port 2 cycle 2000
uart:~$ bay port 2 boot cycle
uart:~$ bay aux 921600 8N1
uart:~$ bay aux send "kernel version"
uart:~$ bay camera set white_balance cloudy
uart:~$ radio 8
```
