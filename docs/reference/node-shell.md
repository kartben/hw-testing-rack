# Bay node shell

Every bay node has a command shell. You reach it over telnet, or through the test pads under the PCB.

## Where to reach it

| Console | How | Who may use it |
|---|---|---|
| telnet, TCP 23 | `telnet bay-b3.local` | the addresses that have the `shell` right in the access rules. One client at a time, no login |
| UART0 test pads | TP1 = TXD0, TP2 = RXD0, on the bottom side of the PCB. 115200 8N1, with a 3.3 V USB-UART adapter | anyone with the node in hand |

The front USB-C port does not give a shell. [Control who can use the rack](../use/access.md) explains who
gets the `shell` right. The prompt is `uart:~$`.

Settings marked *saved* below survive a restart. [Recover a node or the hub](../use/recover.md) says how to
erase them.

## Commands

| Command | What it does | Messages it can print |
|---|---|---|
| [`bay fault`]{#shell-bay-fault} | Shows the fatal error that last restarted the node and the log before it, then the warnings and errors since this boot. A power cut clears it | `no fatal error since power-on` |
| [`bay status`]{#shell-bay-status} | Shows the bay id and host name, address, `restarted: after a …`, the rack position and the hub, the data path, the USB host and its USB/IP sessions, the power and the budget, faults since boot, the AUX UART, the camera | `network: down`; `rack: standalone (no hub has addressed it)`; `rack: no position (not enumerated by the hub)`; `hub silent` |
| [`bay power`]{#shell-bay-power} | Shows the bay's supply: on or off, a fault, mV, mA, mW; why the DATA lead is off; the budget, `Budget: <draw> of <limit> mW (the hub's grant), <n> port(s) waiting, <n> shed since boot` | `DATA lead: off, <reason>` |
| `bay power on` / `off` | Switches the DATA lead, every board of the bay at once. `on` also clears a latched fault, then switches the ports back on one by one, 300 ms apart, except those switched off by hand | `DATA_VIN stays off: <reason>` |
| `bay power cycle [ms]` | Switches the DATA lead off, then on. Off for 1000 ms, or for `ms` | `DATA_VIN stays off: <reason>`; `duration must be 1..60000 ms` |
| [`bay reset [ms]`]{#shell-bay-reset} | Pulses the RESET line of the node's AUX connector low for 100 ms, or for `ms`. `hold` holds it low, `release` lets it go | `duration must be 1..60000 ms` |
| [`bay boot`]{#shell-bay-boot} | Holds the AUX connector's BOOT line, pulses RESET, and lets BOOT go 200 ms later: the ROM bootloader of most MCUs. `hold` and `release` act on BOOT alone | |
| [`bay mode [usbip\|classic]`]{#shell-bay-mode} | Alone, shows the data path, classic `forced` or `auto`, SERVICE, the front port `plugged` or `absent`. `classic` forces classic mode, `usbip` lets it go. Saved | |
| [`bay usb`]{#shell-bay-usb} | Lists the USB devices, two lines per device: busid, vid:pid, name and maker; hub or device, serial number, `read ahead`, `attached by <address> for <n> s` | `no USB device`; `USB host busy, try again` |
| [`bay port`]{#shell-bay-port} | Shows the DATA board, then one line per port: `port 2 (1-1.2): on, <mV> mV <mA> mA, <n> faults, a USB device`, with `(fault)` or `(off by hand)` after `on` or `off` | `no DATA board answering: a one-port node`; `a board answers at 0x20, but neither as a DATA x4 nor as a DATA x6: left alone, its ports off` |
| `bay port <n> on` / `off` | Switches one port on or off. `on` goes through the bay's budget and clears the port's latched fault | `no room in the budget: the bay draws <n> mA` (the number is in mW); `port <n>: VBUS up while off (powered from elsewhere); on once gone` |
| `bay port <n> cycle [ms]` | Switches the port off, then on. Without `ms`, the port stays off until its VBUS reads under 1 V, 2 s at most | the same; `duration must be 1..60000 ms` |
| `bay port <n> reset` | Pulses the port's RESET line for 100 ms | `port <n> has no RESET or BOOT line (a DATA x6)` |
| `bay port <n> boot [cycle]` | Holds BOOT across a RESET pulse. With `cycle`, holds it across a power cycle of the port | the same; `no room in the budget: …` |
| [`bay aux`]{#shell-bay-aux} | Shows the AUX UART: baud and format, Enter, echo, esptool reset; web consoles connected; RFC 2217 and raw TCP `in use` or `free`; bytes received, sent and dropped | |
| `bay aux <baud> [8N1]` | Sets and saves the baud rate and the format: data bits 5 to 8, `N`, `O` or `E`, stop bits 1 or 2 (`7E1`, `8O2`) | `the AUX UART refused <baud> <format> (<errno>)` |
| `bay aux break [ms]` | Holds the board's RX line low for 250 ms, or for `ms` | `BREAK failed (<errno>): DUT is off` |
| `bay aux send <text>` | Sends one line to the board, then the console's Enter. Quote a text with spaces | |
| `bay aux loopback [on\|off]` | Loops the UART's TX back to its RX, to test it without a board | `no UART loopback on this SoC (<errno>)` |
| [`bay camera`]{#shell-bay-camera} | Shows the camera's model, port, clients, frames, errors, the light, then each setting | `no camera` |
| `bay camera set <name> <value>` | Sets and saves one setting: `exposure auto`, `manual` or 0 to 30000; `gain auto`, `manual` or 0 to 1023; `white_balance auto`, `sunny`, `office`, `cloudy`, `home`; `brightness` −4 to 4; `contrast`, `saturation` −3 to 3; `sharpness auto` or 1 to 8; `rotation 0`, `90`, `180`, `270`; `resolution`; `quality`; `light` | the setting's own text: `brightness: -4 to 4`, `sharpness: not on this camera`, … |
| `bay camera reset` | Puts the image settings back to automatic, saved. Resolution, quality, light and rotation stay | |
| [`bay coproc`]{#shell-bay-coproc} | Shows the image stored for the DATA ×4's co-processor, its upload and its loads, as the JSON of `GET /api/coproc` | `no room for the state` |
| [`bay access`]{#shell-bay-access} | Shows the admin key, `set (claimed)` or `none (not claimed)`, a pending claim, the rules and each source's services, `everyone else`, the reservations of the bay and of each port, the connections, refusals since boot | |
| `bay access claim` | Confirms a pending claim, as a short press on BOOT does. Test pads only | `no claim pending: start one from the web page or bayctl`; `claimed: the requester gets the admin key`, `(not saved)` |
| `bay access on` / `off` | Applies the rules, or lets every address use everything. `off`: test pads only | |
| `bay access release` | Ends the reservation of the bay and of every port | `no lease` |
| `bay access reset` | Forgets the admin key, the rules and the reservation. Test pads only | `no admin key, no rules, no lease: the node is open until claimed again` |
| [`bay id [id]`]{#shell-bay-id} | Shows or sets the bay id, saved. The host name becomes `bay-<id>.local` | `hostname bay-b3.local`; `id: 1-15 characters, letters, digits and '-'` |
| [`radio [<dBm>]`]{#shell-radio} | Alone, shows the transmit power asked for, the power in the radio, the channel width. With a number, sets and saves it: 2 to 20 dBm, 11 dBm by default | `TX power: 2 to 20 dBm` |
| [`heaps`]{#shell-heaps} | Shows every heap: address, size, free, used, most used | |
| [`wifi`, `net`]{#shell-wifi} | Zephyr's own commands: `wifi cred add`, `wifi cred auto_connect`, `wifi status`, `net iface`, … ([Wi-Fi](../use/wifi.md)) | |

`bay power`, `bay status` and a failed `bay power on` say why the DATA lead stays off. Each reason is listed
on [Why the DATA lead stays off](states-and-messages.md#why-the-data-lead-stays-off).

## Commands that need the test pads

`bay access claim`, `bay access off` and `bay access reset` refuse to run over telnet. They answer
`only on the node's own console (UART pads), not over telnet`. The node's BOOT
button can do two of them. A short press confirms a claim. A press of 10 s or more resets access control.
If you have lost the key, see [Recover a node or the hub](../use/recover.md).

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
