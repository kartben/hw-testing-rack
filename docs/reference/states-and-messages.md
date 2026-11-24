# States and messages

Look up a state or a message that you see on the rack's pages, in a shell or from `bayctl`, and find out what
it means. `<…>` stands for a value filled in at run time.

## A port's states

Each port of a DATA ×6 or a DATA ×4 is in one of these states. The bay's page shows it in words, and
`/api/ports` gives it as `power.state`.

| On the screen | What it means |
|---|---|
| `on`, "5 V on" | the port's switch is on |
| `off`, "5 V off", "Port off" | switched off, or never switched on |
| `waiting`, "Waiting for power" | wanted on, but the bay's grant has no room yet. It goes on by itself when there is room, in turn with the other waiting ports. Every port waits like this when a node starts |
| `shed`, "Shed for power · back once there is room" | the bay went over its grant, and the port switched on last went off. It comes back by itself once there is room |
| `"queued": true`, "Queued · on as soon as the bay has room" | a power-on asked for "as soon as possible", waiting like `waiting`. **Cancel**, `bayctl power B3.2 cancel` or an `off` withdraws it |
| `fault`, "Over-current fault · 5 V latched off" | the port's switch was in current limit for 7.5 ms, then latched off. The next power-on clears it |
| "Reserved by \<address> (\<note>)", "Reserved by you" | an address holds the port: [Reserve a bay](../use/reserve-a-bay.md) |
| "No device", "Nothing on this port" | the port is on, and nothing has enumerated on it |

Source: `port_state()` in `firmware/bay-node/src/web.c`, and `web/index.html`.
[Power budget and queued ports](../use/power-budget.md) explains why a port waits.

## A row's states

Each row of the rack is in one of these states. The hub's `/api/status` gives it as `rows[].state`, and the
rack's page and the hub's shell show it in words.

| `state` | The page | What it means |
|---|---|---|
| `on` | on, with its current and power | the row's eFuse is on |
| `off` | "VRACK off"; on the bays, "row off" | switched off by hand, or never switched on. The hub saves a row's on or off setting. The shell adds ", off by hand" |
| `waiting` | "waiting for PD" | wanted on: it waits for a final contract, or for its turn 300 ms after the row before |
| `shed` | "shed by budget"; on the bays, "off: not enough power" | off for lack of power. It comes back by itself ([When the rack draws more than the charger gives](../use/power-budget.md#when-the-rack-draws-more-than-the-charger-gives)) |
| `cycling` | cycling | off for a power cycle, on again at its end |
| `fault` | fault, the shelf in red | the row's eFuse reports current limit or over-temperature. The shell adds ", FAULT" |
| `absent` | no shelf | the hub has no such row output. The shell says "not fitted" |

A row that is on with no bay on it reads "no node answered"
([Row D says no node answered](../use/rack-page.md#row-d-says-no-node-answered)).

Source: `rows_state_str()` in `firmware/power-hub/src/rows.c`, `src/shell.c` and `web/index.html`.

## A bay's states on the rack's page

The hub knows the state of a bay from what its node sends on the {term}`rack bus`. The rack's page shows the
first state in this table that applies.

| `nodes[].state` | The page | What it means |
|---|---|---|
| `lost` | "no answer · \<n> s silent", dashed | no STATUS from the node for 3.5 s: a power cut, a crash or a cable fault. It comes back as soon as the hub hears the node again |
| `failed` | "no address" | the node asked for an address and never confirmed it. The bays after it in the row get no address |
| `incompatible` | "newer protocol" | the node speaks a newer major version of the rack bus protocol: update the hub |
| `fault` | "DUT fault" | a fault switched the DATA lead off ([Why the DATA lead stays off](#why-the-data-lead-stays-off)) |
| `service` | "service" | the node's SERVICE switch is on |
| `classic` | "classic" | the boards' USB goes to the front port |
| `off` | "DUT off" | the DATA lead is off |
| `attached` | "USB/IP attached" | a USB/IP client is attached to one of the bay's boards |
| `enumerated` | "device ready" | at least one board is enumerated, and nobody is attached |
| `usbip` | "no device" | nothing is enumerated, or the node's first STATUS has not come yet |

After the label, "\<x> of \<y> W" is what the bay draws out of its {term}`grant`, and "\<n> waiting" counts the
ports that wait for power.

The bay's own page shows a similar word at its top: "fault", "service", "classic", "power off", "attached",
"device ready" or "no device". It shows "offline" when it has lost the node.

Source: `node_state()` in `firmware/power-hub/src/web.c`, and `web/index.html`.

## The charger's states

The label at the top right of the rack's page sums up the power from the charger. It shows the first line of
this table that applies:

| Label | What it means |
|---|---|
| "row fault" | a row's eFuse reports a fault |
| "no PD charger" | no contract: no charger, or one that has not answered yet |
| "rows shed" | one row or more is shed for lack of power |
| "contract settling" | a contract that is not final yet: under 15 V, or held for less than 500 ms. The rows wait |
| "20 V", "28 V EPR" | the contract is final, at that voltage |
| "offline" | the page cannot reach the hub. It retries |

The same state appears in other places:

- In `/api/status`, `pd.state` is `usb` (no charger: the hub runs from its console USB-C), `starting`, `spr`
  or `epr`.
- The hub's shell writes `no VBUS`, `starting`, `SPR` or `EPR`, with ", settling" before the contract is
  final.
- On the PD card of the rack's page, the sink line reads "asked 9 V (CFG1)" until the firmware asks for 20 V,
  then "asked 20 V · PG good". "PG high" means no power good.

Source: `firmware/power-hub/web/index.html`, `src/pd.c` and `src/web.c`.

## Why the DATA lead stays off

The {term}`DATA lead` brings {term}`VRACK` from the bay node to the DATA board. The node switches it on only
after a few checks. When a check fails, the node gives the reason:

- on the bay's page, after "DATA lead off:";
- in the output of `bay power`, after "DATA lead: off,";
- in the output of `bay power on`, after "DATA_VIN stays off:".

<!-- site:data-lead-messages -->
| Reason | What it means |
|---|---|
| `SCL or SDA held low: DATA lead reversed?` | before switch-on: the lead is wired 1:1 where it must be "same direction". Nothing is harmed, and the lead stays off |
| `the node's INA226 does not answer` | before switch-on: the node cannot measure its lead, so it does not switch it on |
| `no DATA_VIN after switching on: a short on the lead (a camera lead in J7?)` | 20 ms after switch-on, the lead is under 15 V or the eFuse reports a fault. The node switches it off and marks a fault: the LED turns red and the hub gets an alert |
| `the eFuse reported a fault` | while on: the eFuse flagged a fault. The node switches the lead off and marks a fault |
| `no DATA board answers: none, or the wrong lead in J7` | no DATA ×6 or DATA ×4 answered within 1 s of switch-on |
| `the DATA board stopped answering` | while on: the DATA board missed two polls in a row, 20 ms apart. The node switches the lead off and marks a fault |
<!-- /site:data-lead-messages -->

Source: `dut_lead_str()` in `firmware/bay-node/src/dut.c`.

The lead stays off until you switch it on again. The checks then run again. To switch it on, use one of
these:

- **Power on the board** on the rack's page;
- `bayctl hub node B3 power-on`;
- `bay power on` in the node's shell;
- BOOT on the node, held for 1 s.

[Cables and pinouts](cables.md) shows which lead goes where.

## Refusals over HTTP

When a node or the hub refuses a request, it answers with a status code and `{"error": "<text>"}`. A refusal
by a bay node's access rules, and a 423 on a port, also give `reason`, `service` and `you`. `you` is the
address the node saw.

| Code | Text | What it means |
|---|---|---|
| 403 | `not allowed from this address` | the node's access rules do not give your address this service ([Control who can use the rack](../use/access.md)) |
| 403 | `kicked by an admin: retry in a minute` | an admin closed your connection. Your address is refused for a minute |
| 403 | `admin only: sign the request with the key` | an admin request to a node without `X-Bay-Auth` |
| 403 | `bad or expired admin signature` | the wrong key, or a nonce older than 60 s or already used |
| 403 | `admin only: unlock with the hub's admin key` | an action on the hub, unsigned or signed with another key |
| 403 | `admin only: claim the hub first (its BOOT button)` | the hub has no admin key yet |
| 409 | `no room in the bay's budget: the bay draws <n> mW, <r> mW kept for a start, <l> mW in all (the hub's grant)` | a plain power-on with no room: queue it ([Power budget and queued ports](../use/power-budget.md)) |
| 409 | `the port's VBUS is up while it is off (a board powered from elsewhere): it comes on once that has gone` | the board is fed through another connector ([Put a board in a bay](../use/mount-a-board.md)) |
| 409 | `this node serves <n> boards: say which ("port": 1..<n>, or /api/ports/<n>/...)` | `/api/power`, `/api/reset` or `/api/boot` without `"port"` |
| 409 | `no queued request on this port` | a `cancel` with nothing queued |
| 409 | `already claimed: unlock with the admin key, or reset the hub` | a claim of a hub that has a key |
| 423 | `reserved by <address> (<note>), <n> min left` | someone holds the bay ([Reserve a bay](../use/reserve-a-bay.md)) |
| 423 | `B3.2 reserved by <address> (<note>), <n> min left` | someone holds that port |
| 503 | `the port is off, or the DATA board is not set up (DUT_5V off?)` | reset or bootloader on a port that is off, or with the DATA lead off |

Source: `firmware/bay-node/src/web.c` and `firmware/power-hub/src/web.c`. The other codes are in
[Bay node HTTP API](node-api.md) and [Power hub HTTP API](hub-api.md#status-codes-and-their-texts).

## Shell messages

The node's shell prints these messages about the power of its ports:

| Message | What it means |
|---|---|
| `no room in the budget: the bay draws <n> mA` | the 409 above. The figure is in milliwatts, although the text says mA |
| `port <n>: VBUS up while off (powered from elsewhere); on once gone` | the 409 above |
| `port <n> has no RESET or BOOT line (a DATA x6)` | reset or bootloader on a port of a DATA ×6 |
| `duration must be 1..60000 ms` | a power cycle's length out of range |
| `only on the node's own console (UART pads), not over telnet` | a command refused over telnet |

Source: `firmware/bay-node/src/shell.c`. [Bay node shell](node-shell.md) gives every other message.

The hub's shell prints these:

| Message | What it means |
|---|---|
| `row: A-D` | a row letter other than A to D |
| `row <X> is not fitted` | the hub has no such row output |
| `failed (<n>)` | `hub row` refused. For a `cycle`, the row is not on |
| `node: C3 or 0x23` | a bay given in another form |
| `action: identify, reset, bootloader, power-cycle, reboot` | another action. The shell has no power-on or power-off for a bay |
| `rack bus busy` | a command to a bay could not be queued: try again |
| `sent ("hub events" for the answer)` | the command left. The bay's answer comes as an event |
| `28 V EPR is off on this hub (CONFIG_HUB_EPR_ALLOWED: L1 is rated 30 V)` | `hub pd epr`: the hub stays at 20 V ([Power hub shell](hub-shell.md)) |
| `shed order: the four rows, first shed first (default DCBA)` | an order that does not name each of A, B, C and D once |
| `margin: 0 to 50 (%)`, `cap: 1 to 240 (W), or off` | a value out of range |
| `set, but not saved (<n>)` | applied until the next restart only |
| `id: 1-15 characters, letters, digits and '-'` | a rack id the hub refuses |
| `no pending claim (start one from the web page)` | `hub access claim` with no claim started |

Source: `firmware/power-hub/src/shell.c`.

## bayctl messages

`bayctl` prints an error as `bayctl: <message>` on stderr and exits with 1. A refusal from a node or the hub
reads `bayctl: <bay>: <path>: <code> <text>`, with one of the texts above. From the hub, `<bay>` is `hub`:

```console
$ python tools/bayctl.py row B cycle
bayctl: hub: /api/row: 400 row is not on
```

| Message | What it means |
|---|---|
| `warning: hub <host>: no such host (BAYCTL_HUB=host[:port] names it, BAYCTL_HUB=none skips it): config/lab.yaml's bays only` | the hub's name does not resolve ([How it finds the rack](../use/set-up-your-machine.md#how-it-finds-the-rack)) |
| `<bay>: cannot reach <url> (<reason>)` | no answer from that node or from the hub |
| `set BAYCTL_KEY to the rack's admin key (a new one: bayctl access keygen)` | a signed command without the key in the environment |
| `BAYCTL_KEY must be 64 hex digits` | the key is malformed |
| `unknown bay '<x>' (known: <list>)` | a name that neither the rack nor the lab file knows |
| `bay B3 holds several boards: say which (B3.1, B3.2, …)` | a command for one board, given a bay ([Bays, ports and addresses](../use/names.md)) |
| `<bay>: the node has no port <n> (is its DATA ×4 board connected?)` | the node reports fewer ports |
| `<bay>: queued, on as soon as the bay's budget has room` | `--when available` queued it. The exit code is 0 |
| `<bays>: no room in the bay's budget after <s> s: the queued power on is cancelled` | `--wait` ran out |
| `usbip not found (usbip: install linux-tools-generic / usbip)` | the machine has no `usbip` |
| `<bay>: <busid> is not exported (is the board powered and enumerated?)` | `attach` found no such device on the node |
| `<bay>: nobody pressed BOOT in time` | a claim not confirmed within 60 s |

`hwmap` prints its warnings as `warning: …` lines and still exits with 0:

| Warning | What to do |
|---|---|
| `bay <id> (<board>): no board target: …` | set the board's target on the bay's page, or `platform` in the lab file ([Board targets](../use/board-targets.md)) |
| `bay <id>: <device> S/N <serial> is not the board its target was saved for (…): check it, then save its target again on the node's page` | another board is on the port |
| `bay <id>: no USB device in the slot now (powered off?): no console path; …` | the board is not enumerated. Its entry gets `connected: false` |
| `bay <id>: console none: no console, kept out of the tests (connected: false)` | the lab file says so |
| `bays <ids> use <runner> without a probe id: …, or flashing may hit the wrong board` | give each board its probe id |
| `bay <id>: <note>` | the board library's note on that board |

Source: `tools/bayctl.py`. [bayctl](bayctl.md#exit-codes) lists the exit codes.
[Run twister on the rack](../use/twister.md) explains how to use the map.

## The hub's events

The hub keeps its last 32 events in RAM, newest first. A restart of the hub loses them.

| Kind | Text | When |
|---|---|---|
| `pd` | `VBUS <v> V: PD sink up` | a charger is plugged in |
| `pd` | `contract: <v> V / <a> A (<w> W)`, with ` EPR`, and `, too low for the rows` under 15 V | a new contract. The 9 V of plug-in is always "too low for the rows" |
| `pd` | `20 V asked, VBUS stays at <v> V: the rows stay off` | the charger did not follow within 3 s |
| `pd` | `contract lost (PG high): rows off until it is back` | every row goes off at once |
| `pd` | `VBUS gone: no PD charger (running from the console USB-C)` | the charger was unplugged |
| `pd` | `contract preference: 20 V` | `hub pd 20v`, the page or the API |
| `pd` | `claimed: admin key set (BOOT pressed)`, `… (local shell)` | a claim was confirmed |
| `row` | `row <X> on` | a row comes on in its turn |
| `row` | `row <X> switched on`, `row <X> switched off` | someone switched the row by hand. The hub saves the setting |
| `row` | `row <X> power cycle (<ms> ms off)` | a power cycle |
| `row` | `row <X> shed: <a> A > <b> A budget`, `… contract` | the rows drew more than the budget for 1 s, or more than the contract for 250 ms |
| `row` | `row <X> back: the budget has room for it again` | a shed row returns |
| `row` | `budget margin <n> %`, `budget capped at <n> W`, `budget cap off: the contract's` | `hub budget` |
| `row` | `rows kept on across the controller reset: 0x<mask>` | the hub restarted with rows on (bit 0 is row A) |
| `fault` | `row <X>: eFuse fault (current limit or over-temperature)` | a row's eFuse reports a fault, from 50 ms after the row was switched on |
| `fault` | `node <bay>: DUT switched off by a fault (<n> mA)`, `node <bay>: DUT in current limit (<n> mA)` | an alert from a node |
| `fault` | `admin key forgotten (BOOT held 10 s): the hub can be claimed again`, `admin key forgotten (local shell)` | BOOT held, or `hub access reset` |
| `can` | `enumeration: <n> node(s)` | the hub numbered the rack bus |
| `can` | `node <bay> did not confirm its address: row <X> stops there` | the bays after it get no address |
| `can` | `node <bay> (0x<id>) lost: no STATUS for 3 s` | the node was silent for 3.5 s (the text rounds it down) |
| `can` | `node <bay> (0x<id>) back` | it answers again |
| `node` | `node <bay>: command 0x<op> done`, `refused`, `failed`, `unknown command` | a bay's answer to a command |
| `node` | `node <bay>: no answer to command 0x<op>` | three tries, 100 ms apart, unanswered |
| `firmware` | `firmware <version> confirmed itself` | an update stayed |
| `firmware` | `firmware <version> not healthy after <s> s: rebooting into <version>` | an update failed its trial |
| `firmware` | `update to <version> rolled back: running <version>` | after that restart |

In the `node` events, `0x<op>` is the command:

| `op` | Command |
|---|---|
| `0x01` | power: on, off or cycle |
| `0x02` | reset |
| `0x03` | bootloader |
| `0x04` | identify |
| `0x05` | reboot |

A reserved bay answers `refused` to every command but identify. `failed` means the action failed, for
instance a power-on whose DATA lead stayed off.

Source: `firmware/power-hub/src/` (`pd.c`, `rows.c`, `bus.c`, `main.c`, `shell.c`),
`firmware/common/lib/update.c` and `firmware/bay-node/src/rack.c`.
[Read the events](../use/rack-page.md#read-the-events) shows where to find them.

## The co-processor's states

The {term}`co-processor` of a DATA ×4 runs the logic analyzer from its RAM. The node loads the image at each
power-up. `/api/coproc` gives the state of the load as `load.state`, and the analyzer card shows it after the
image's name.

| `load.state` | The card | What it means |
|---|---|---|
| `idle` | "waiting for the co-processor" | not seen on USB yet |
| `loading` | "loading…" | the image is being written into its RAM |
| `started` | "starting" | written and started |
| `loaded` | "loaded in \<ms> ms" | running |
| `failed` | "not loaded: \<error>" | a load failed, for the reason given |
| `left to USB/IP` | "left to USB/IP after failed loads" | two loads failed in a row. The node stops trying and leaves the co-processor's bootloader to USB/IP, like any board |

With no image stored, the card reads "No analyzer image on the node: bayctl coproc load", and the bootloader
is left to USB/IP too. [Logic analyzer](../use/logic-analyzer.md) explains how to load an image.

Source: `firmware/bay-node/src/coproc.c` and `web/analyzer-card.mjs`.
