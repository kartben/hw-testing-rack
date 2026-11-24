# Power hub shell

The power hub's shell is on its console USB-C port, above the CTL label on the front of the power box. Open
it with any serial terminal, at any baud rate. There is no telnet and no login: whoever holds the cable is
the hub's admin.

The console port powers the hub's controller but not the rows. So the shell also works on a desk, with no
charger. The prompt is `uart:~$`.

## Commands

| Command | What it does | Saved |
|---|---|---|
| `hub status` | Shows the host name and address, the contract, each row, the budget and the rack bus | |
| `hub pd` | Shows the contract, the sink's state, what the hub asks for, and the charger's offers (`*` marks the one in use) | |
| `hub pd 20v` | Asks the charger for 20 V | yes |
| `hub pd epr` | Refused: the hub stays at 20 V. It answers `28 V EPR is off on this hub` | |
| `hub row <A-D> on` / `off` | Switches a row on or off | yes |
| `hub row <A-D> cycle [ms]` | Power-cycles a row that is on. The row stays off for 2000 ms, or for `ms` | no |
| `hub nodes` | Shows one line per bay: place, node id, MAC, IP, flags, DATA lead current, firmware, state | |
| `hub enumerate` | Renumbers the bays on the rack bus. See the result with `hub nodes` | |
| `hub node <C3\|0x23> identify` | Makes the bay's LED blink white and blue for 10 s | |
| `hub node <C3\|0x23> reset` / `bootloader` | Pulses the node's AUX RESET line, or holds BOOT across a RESET pulse | |
| `hub node <C3\|0x23> power-cycle` | Switches the bay's DATA lead off for 1 s, then on. Every board in the bay restarts | |
| `hub node <C3\|0x23> reboot` | Restarts the bay node | |
| `hub events` | Shows the recent events, oldest first: age, kind, text | |
| `hub shed [DCBA]` | Shows or sets the order in which rows are shed, first shed first | yes |
| `hub budget` | Shows the rows' budget: what they draw, the limit, the contract or the cap, the margin, the rows shed | |
| `hub budget margin <0-50>` | Sets the share of the contract kept free, in %. 10 by default | yes |
| `hub budget cap <W>` / `cap off` | Sets a limit in watts, 1 to 240, for a charger that cuts out below what it offers | yes |
| `hub id [<id>]` | Shows or sets the rack id. The host name becomes `rack-<id>.local` | yes |
| `hub access` | Shows whether the hub has an admin key, and whether a claim is waiting | |
| `hub access claim` | Confirms a pending claim, as a short press on BOOT does | yes: the key |
| `hub access reset` | Forgets the admin key, as holding BOOT for 10 s does | yes |
| `radio [<dBm>]` | Shows or sets the Wi-Fi transmit power, 2 to 20 dBm. 11 by default | yes |
| `wifi cred add -s <ssid> -k 1 -p <password>`, `wifi cred auto_connect` | Stores the network the hub joins | yes |

Source: [firmware/power-hub/src/shell.c](../../firmware/power-hub/src/shell.c).
[Recover a node or the hub](../use/recover.md) says how to erase what the hub saves.

## Commands to a bay

A `hub node` command returns at once with `sent ("hub events" for the answer)`. The bay's answer, or
`no answer`, comes later. Read it with `hub events`. A reserved bay refuses every command except `identify`.

Name a bay by its place (`C3`) or by its node id (`0x23`). The node id is 16 times the row's index (A is 0),
plus the column number.

`reset` and `bootloader` act on the node's AUX lines, not on a DATA ×4 port. To reset a board on a port, see
[Power-cycle or reset a board](../use/power-and-reset.md).

## Settings only the shell has

You can set the budget margin, the cap and the shed order only in this shell
([Power budget and queued ports](../use/power-budget.md)).

After `hub id lab1`, the hub is `rack-lab1.local`. A machine that looks for `rack.local` no longer finds it
([Bays, ports and addresses](../use/names.md)). An id is 1 to 15 letters, digits and `-`.

[States and messages](states-and-messages.md) explains each message.

## Examples

Set up the hub at its first boot:

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
