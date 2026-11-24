# Power hub shell

The hub's shell runs on its console USB-C only, with no telnet and no login: it switches rows,
so it is reached with a cable, and whoever holds the cable is the hub's admin. The header of
`firmware/power-hub/src/shell.c` still says "and telnet"; the hub has none.

:::{status} written
The shell builds with the hub's firmware 0.5.0 and has no test. Its row in
[What exists today](../plan/status.md#status-rack-page) reads simulated for the rack's page and the hub's API,
which ran against the simulated hub; that simulator has no shell, and the bench plan for a XIAO that runs the
hub's firmware records no shell session. No hub has been on a bench.
:::

The console USB-C is in the power box's front wall, under the CTL label, beside the CTL LED. It also powers
the hub's controller, but not the rows, so the shell works on a desk with no charger. It is the
ESP32-S3's own USB serial port: any serial terminal opens it, at any baud rate. The prompt is `uart:~$`.

## The commands

| Command | What it does | Saved |
|---|---|---|
| `hub status` | the hostname and address, the contract, each row, the budget, the rack bus | |
| `hub pd` | the contract, the sink's state, what the hub asks for, and the charger's offers (`*` the one in use) | |
| `hub pd 20v` | ask the charger for 20 V | yes |
| `hub pd epr` | ask for 28 V EPR when offered; refused on a default build (notes) | yes, on a build that allows it |
| `hub row <A-D> on` / `off` | switch a row on or off | yes |
| `hub row <A-D> cycle [ms]` | power-cycle a row that is on; 2000 ms off unless said | no |
| `hub nodes` | one line per bay: place, node id, MAC, IP, flags, DATA lead current, firmware, state | |
| `hub enumerate` | number the rack bus again; the result in `hub nodes` | |
| `hub node <C3\|0x23> identify` | the bay's LED blinks white and blue for 10 s | |
| `hub node <C3\|0x23> reset` / `bootloader` | pulse the node's AUX RESET line, or BOOT across a RESET pulse | |
| `hub node <C3\|0x23> power-cycle` | the bay's DATA lead off 1 s, then on: every board of the bay | |
| `hub node <C3\|0x23> reboot` | restart the bay node | |
| `hub events` | the recent events, oldest first: age, kind, text | |
| `hub shed [DCBA]` | show, or set, the order in which rows are shed, first shed first | yes |
| `hub budget` | the rows' budget: what they draw, the limit, the contract or the cap, the margin, rows shed | |
| `hub budget margin <0-50>` | the share of the contract kept free, in %; 10 by default | yes |
| `hub budget cap <W>` / `cap off` | a limit in watts, 1 to 240, for a charger that cuts below what it offers | yes |
| `hub id [<id>]` | show, or set, the rack id: the hostname becomes `rack-<id>.local` | yes |
| `hub access` | whether the hub has an admin key, and whether a claim waits | |
| `hub access claim` | confirm a pending claim, as a short press on BOOT does | yes: the key |
| `hub access reset` | forget the admin key, as holding BOOT 10 s does | yes |
| `radio [<dBm>]` | show, or set, the Wi-Fi transmit power, 2 to 20 dBm; 11 by default | yes |
| `wifi cred add -s <ssid> -k 1 -p <password>`, `wifi cred auto_connect` | store the network the hub joins | yes |

Read from `firmware/power-hub/src/shell.c`. Everything a hub keeps across
a restart, the rows' on and off included, is listed on
[Recover a node or a hub](../use/recover.md); a row cycle and the events are not kept.

## Notes

A command to a bay leaves on the rack bus and returns at once with `sent ("hub events" for the answer)`. The
bay's answer, or `no answer` after three tries, comes as an event: `hub events` after it. A reserved bay
refuses every command but `identify`. The shell has five actions on a bay; the page, the HTTP API and
`bayctl` have seven, with `power-on` and `power-off`
([Rows and the rack's page](../use/rack-page.md#act-on-a-bay-through-the-hub)).

A bay is named by its place, `C3`, or by its node id, `0x23`: the row's number (A is 0) times 16, plus the
place. On a v1.0 node, reset and bootloader act on the node's own AUX RESET and BOOT lines, not on a DATA ×4
port: a port's reset is on [Power-cycle or reset a board](../use/power-and-reset.md#reset-and-bootloader).

`hub pd epr` answers `28 V EPR is off on this hub (CONFIG_HUB_EPR_ALLOWED: L1 is rated 30 V)`. The 28 V lock
is the build option `CONFIG_HUB_EPR_ALLOWED`, off by default. Its message names the hub's inductor L1, which
has been a 75 V part since 2026-11-01, as every buck inductor on VRACK in the v1.0 bills of materials; the
build option is still off ([Specifications](specifications.md#voltages)).

The budget, the cap and the shed order exist only here: the page, the HTTP API and `bayctl` have no control
for them. What they do: [Power budget and queued ports](../use/power-budget.md#protect-a-row-cap-a-weak-charger).

Without an id the hub is `rack.local`. After `hub id lab1` it is `rack-lab1.local`, and a machine that looked
for `rack.local` no longer finds it ([Bays, ports and addresses](../use/names.md)). The id is 1 to 15 letters,
digits and `-`.

Every refusal of the shell, with its meaning, is on
[States and error messages](states-and-messages.md#messages-of-the-two-shells).

## Examples

The first boot ([stage 4 of the hub's checklist](../build/check-the-pcbs/power-hub.md#4-flash-and-ask)):

```console
uart:~$ wifi cred add -s MyLab -k 1 -p secret
uart:~$ wifi cred auto_connect
uart:~$ hub id lab1
uart:~$ hub status
```

Cycle row B for 5 s, then read what happened:

```console
uart:~$ hub row B cycle 5000
uart:~$ hub events
```

Blink bay C3's LED to find it in the rack:

```console
uart:~$ hub node C3 identify
sent ("hub events" for the answer)
```
