# States, events and error messages

The firmware names each state of a port, a row, a bay and the charger with one word, and each refusal with one
text. They are quoted here as the code prints them, `<…>` standing for a value filled in at run time.

:::{status} simulated
The texts are the code's. The states have been reached on native_sim and on the simulated node and hub, not on
a v1.0 PCB. The hub's simulator, whose screenshots show the rack's page elsewhere on this site, words its events
otherwise: the firmware's texts are below. See [What exists today](../plan/status.md#status-rack-page).
:::

## A port's states

A port of a DATA ×6 or a DATA ×4, as `/api/ports` gives it (`power.state`) and as the bay's page writes it.

| On the screen | What it means, what to do |
|---|---|
| `on`, "5 V on" | the port's switch is on |
| `off`, "5 V off", "Port off" | switched off, by hand or never on |
| `waiting`, "Waiting for power" | wanted on, and the bay's share of the charger has no room yet. It goes on by itself, in turn with the other waiting ports, once there is room. Every port waits like this for its turn when a node starts |
| `shed`, "Shed for power · back once there is room" | it was on, and the bay went over its share: the port switched on last went off. It comes back by itself once there is room for what it drew |
| `"queued": true`, "Queued · on as soon as the bay has room" | a power-on asked "as soon as possible": it waits as `waiting` does. **Cancel**, `bayctl power B3.2 cancel` or an `off` withdraws it |
| `fault`, "Over-current fault · 5 V latched off" | the port's switch limited for 7.5 ms and latched off. The next power-on clears it |
| "Reserved by <address> (<note>)", "Reserved by you" | another address, or yours, holds the port: [Reserve a bay](../use/reserve-a-bay.md) |
| "No device", "Nothing on this port" | the port is on and nothing enumerated on it |

Read from `firmware/bay-node/src/web.c` (`port_state()`) and `web/index.html` (`portBar()`, `emptyRow()`). Why
a port waits and how much a bay may draw: [Power budget and queued ports](../use/power-budget.md).

## A row's states

A row of the rack as the hub's `/api/status` gives it (`rows[].state`), the hub's page and the shell.

| `state` | The page | What it means |
|---|---|---|
| `on` | on, with its current and power | the row's eFuse is on |
| `off` | off, "VRACK off"; the bays: "row off" | switched off by hand (saved), or never on. The shell adds ", off by hand" when it was switched off |
| `waiting` | waiting, "waiting for PD" | wanted on: it waits for a final contract, or for its turn, 300 ms after the row before |
| `shed` | shed, "shed by budget"; the bays: "off: not enough power" | off for lack of power; it comes back by itself ([When the rack is over the charger's](../use/power-budget.md#when-the-rack-is-over-the-chargers)) |
| `cycling` | cycling | switched off for a power cycle; on again at its end |
| `fault` | fault, the shelf in red | the row's eFuse reports current limit or over-temperature now. The shell writes the state and ", FAULT" |
| `absent` | no shelf | the hub has no such row: B to D on the bench stand-ins. The shell: "not fitted" |

A row that is on with no bay on it reads "no node answered"
([Rows and the rack's page](../use/rack-page.md#row-d-says-no-node-answered)).

Read from `firmware/power-hub/src/hub.h`, `src/rows.c` (`rows_state_str()`), `src/shell.c` and
`web/index.html` (`ROW_LABEL`).

## A bay's states on the rack's page

The hub knows a bay from what its node sends on the rack bus. The first that applies wins.

| `nodes[].state` | The page | What it means |
|---|---|---|
| `lost` | "no answer · <n> s silent", dashed | no STATUS from the node for 3.5 s: power cut, crash or cable. It comes back by itself as soon as the hub hears it again; a node that restarted asks for an address, and the hub numbers the rack again |
| `failed` | "no address" | the node asked for an address and never confirmed it. The row stops there: the bays after it get no address |
| `incompatible` | "newer protocol" | the node speaks a newer major version of the rack bus protocol than the hub: update the hub |
| `fault` | "DUT fault" | the DATA lead was switched off by a fault ([Why the DATA lead stays off](#why-the-data-lead-stays-off)) |
| `service` | "service" | the node's SERVICE switch is on |
| `classic` | "classic" | the boards' USB goes to the front port |
| `off` | "DUT off" | the DATA lead is off |
| `attached` | "USB/IP attached" | a USB/IP client is attached to one of the bay's boards |
| `enumerated` | "device ready" | at least one board enumerated, nobody attached |
| `usbip` | "no device" | nothing enumerated; also a node whose first STATUS has not come yet |

After the label, "<x> of <y> W" is what the DATA lead draws against the hub's grant, and "<n> waiting" the
ports waiting for power. Read from `firmware/power-hub/src/web.c` (`node_state()`) and `web/index.html`
(`NODE_LABEL`, `bayTile()`).

The bay's own page heads with one word of the same family: "fault", "service", "classic", "power off",
"attached", "device ready", "no device", or "offline" when the page lost the node.

## The contract's states

The pill at the top right of the rack's page, first that applies:

| Pill | What it means |
|---|---|
| "row fault" | a row's eFuse reports a fault |
| "no PD charger" | no contract: no charger, or one that has not answered yet |
| "rows shed" | one row or more shed for lack of power |
| "contract settling" | a contract, not final yet: under 15 V, or held less than 500 ms. The rows wait |
| "20 V", "28 V EPR" | the contract is final, and its voltage |
| "offline" | the page cannot reach the hub; it retries |

`pd.state` in `/api/status` is `usb` (no VBUS: the controller runs from its console USB-C), `starting`,
`spr` or `epr`; the shell writes `no VBUS`, `starting`, `SPR`, `EPR`, and ", settling" before a contract is
final. The PD card's sink line reads "asked 9 V (CFG1)" until the firmware has asked for 20 V, then
"asked 20 V · PG good"; "PG high" means no power good, and "28 V refused" that a 28 V request fell back to 20 V.
Read from `firmware/power-hub/web/index.html` (`hubState()`, `renderPd()`), `src/pd.c` and `src/web.c`.

## Why the DATA lead stays off

On a v1.0 node the DATA lead carries VRACK to the DATA board through an eFuse, and the node switches it on
only after the checks of [the DATA lead's power-on rule](../firmware.md#the-data-leads-power-on-rule-node-v10).
When one fails, the reason is one of six texts. The bay's page prints it after "DATA lead off:" in its red
banner and its power card, `bay power` after "DATA lead: off,", and `bay power on` after
"DATA_VIN stays off:".

<!-- site:data-lead-messages -->
| Reason | When, and what it means |
|---|---|
| `SCL or SDA held low: DATA lead reversed?` | before switching on: the lead is wired 1:1 where it must be "same direction". Nothing is harmed; the lead stays off |
| `the node's INA226 does not answer` | before switching on: the node cannot measure its lead, so it does not switch it on |
| `no DATA_VIN after switching on: a short on the lead (a camera lead in J7?)` | 20 ms after switching on, the lead is under 15 V or the eFuse reports a fault. The node switches it off again and marks a fault: LED red, an alert to the hub |
| `the eFuse reported a fault` | while on: the eFuse limited. The lead is off and the fault marked |
| `no DATA board answers: none, or the wrong lead in J7` | no DATA ×6 or DATA ×4 answered within 1 s of switching on |
| `the DATA board stopped answering` | while on: the board missed two polls in a row, 20 ms apart. The lead is off and the fault marked |
<!-- /site:data-lead-messages -->

Read from `firmware/bay-node/src/dut.c` (`dut_lead_str()`).

The lead stays off until it is asked on again, and the checks run again then: `bay power on` in the node's
shell, **Power on the board** on the rack's page, `bayctl hub node B3 power-on`, or BOOT on the node held 1 s.
Which lead goes where: [Cables and pinouts](cables.md).

## Refusals over HTTP

A refusal is `{"error": "<text>"}` with its status code: 403, 409, 423 or 503 below. A bay node adds `reason`,
`service` and `you`, the address it saw, when its access rules refuse you, and to a port's 423.

| Code | Text | What it means |
|---|---|---|
| 403 | `not allowed from this address` | the node's access rules do not give your address this service: [Access rules and security](../use/access.md) |
| 403 | `kicked by an admin: retry in a minute` | an admin closed your connection; your address is refused for a minute |
| 403 | `admin only: sign the request with the key` | an admin request on a node, without `X-Bay-Auth` |
| 403 | `bad or expired admin signature` | wrong key, or a nonce older than 60 s or already used |
| 403 | `admin only: unlock with the hub's admin key` | an action on the hub, unsigned or signed with another key |
| 403 | `admin only: claim the hub first (its BOOT button)` | the hub has no admin key yet |
| 409 | `no room in the bay's budget: the bay draws <n> mW, <r> mW kept for a start, <l> mW in all (the hub's grant)` | a plain power-on with no room: queue it ([Power budget and queued ports](../use/power-budget.md)) |
| 409 | `the port's VBUS is up while it is off (a board powered from elsewhere): it comes on once that has gone` | the board is fed through another connector: [Put a board in a bay](../use/mount-a-board.md) |
| 409 | `this node serves <n> boards: say which ("port": 1..<n>, or /api/ports/<n>/...)` | `/api/power`, `/api/reset` or `/api/boot` without `"port"` |
| 409 | `no queued request on this port` | a `cancel` with nothing queued |
| 409 | `already claimed: unlock with the admin key, or reset the hub` | a claim of a hub that has a key |
| 423 | `reserved by <address> (<note>), <n> min left` | someone holds the bay: [Reserve a bay](../use/reserve-a-bay.md) |
| 423 | `B3.2 reserved by <address> (<note>), <n> min left` | someone holds that port |
| 503 | `the port is off, or the DATA board is not set up (DUT_5V off?)` | reset or bootloader on a port that is off, or with the DATA lead off |

Read from `firmware/bay-node/src/web.c` and `firmware/power-hub/src/web.c`. The rest, codes 400, 404 and 413
included: [Bay node HTTP API](node-api.md), [Power hub HTTP API](hub-api.md#status-codes-and-their-texts).

## Messages of the two shells

The node's shell, on the power of its ports:

| Message | What it means |
|---|---|
| `no room in the budget: the bay draws <n> mA` | the 409 above. On a v1.0 node the figure is in milliwatts although the text says mA |
| `port <n>: VBUS up while off (powered from elsewhere); on once gone` | the 409 above |
| `port <n> has no RESET or BOOT line (a DATA x6)` | reset or bootloader on a DATA ×6 |
| `duration must be 1..60000 ms` | a cycle's length out of range |
| `only on the node's own console (UART pads), not over telnet` | a command refused over telnet |

Every other message of the node's shell: [Bay node shell](node-shell.md). Read from
`firmware/bay-node/src/shell.c`.

The hub's shell:

| Message | What it means |
|---|---|
| `row: A-D` | a row letter other than A to D |
| `row <X> is not fitted` | the hub has no such row (a bench stand-in) |
| `failed (<n>)` | `hub row` refused; for a `cycle`, the row is not on |
| `node: C3 or 0x23` | a bay given in another form |
| `action: identify, reset, bootloader, power-cycle, reboot` | another action; power-on and power-off are not in the shell |
| `rack bus busy` | a command to a bay could not be queued; try again |
| `sent ("hub events" for the answer)` | the command left; the bay's answer comes as an event |
| `28 V EPR is off on this hub (CONFIG_HUB_EPR_ALLOWED: L1 is rated 30 V)` | `hub pd epr` on a default build ([Power hub shell](hub-shell.md#notes)) |
| `shed order: the four rows, first shed first (default DCBA)` | an order that does not name each of A, B, C, D once |
| `margin: 0 to 50 (%)`, `cap: 1 to 240 (W), or off` | values out of range |
| `set, but not saved (<n>)` | applied until the next restart only |
| `id: 1-15 characters, letters, digits and '-'` | a rack id the hub refuses |
| `no pending claim (start one from the web page)` | `hub access claim` with no claim started |

Read from `firmware/power-hub/src/shell.c`.

## Messages of bayctl

`bayctl` prints an error as `bayctl: <message>` on stderr and exits with 1. A refusal of a node or of the hub
reads `bayctl: <bay>: <path>: <code> <text>`, the text one of those above; the hub is named `hub`:

```console
$ python tools/bayctl.py row B cycle
bayctl: hub: /api/row: 400 row is not on
```

| Message | What it means, what to do |
|---|---|
| `warning: hub <host>: no such host (BAYCTL_HUB=host[:port] names it, BAYCTL_HUB=none skips it): config/lab.yaml's bays only` | the hub's name does not resolve: [Set up bayctl and usbip](../use/set-up-your-machine.md#how-it-finds-the-rack) |
| `<bay>: cannot reach <url> (<reason>)` | no answer from that node or from the hub |
| `set BAYCTL_KEY to the rack's admin key (a new one: bayctl access keygen)` | a signed command without the key in the environment |
| `BAYCTL_KEY must be 64 hex digits` | the key is malformed |
| `unknown bay '<x>' (known: <list>)` | a name neither the rack nor the lab file knows |
| `bay B3 holds several boards: say which (B3.1, B3.2, …)` | a command for one board given a bay: [Bays, ports and addresses](../use/names.md) |
| `<bay>: the node has no port <n> (is its DATA ×4 board connected?)` | the node reports fewer ports |
| `<bay>: queued, on as soon as the bay's budget has room` | `--when available` queued it; exit code 0 |
| `<bays>: no room in the bay's budget after <s> s: the queued power on is cancelled` | `--wait` ran out |
| `usbip not found (usbip: install linux-tools-generic / usbip)` | the machine lacks `usbip` |
| `<bay>: <busid> is not exported (is the board powered and enumerated?)` | `attach` found no such device on the node |
| `<bay>: nobody pressed BOOT in time` | a claim not confirmed within its 60 s |

`hwmap` writes its warnings as `warning: …` lines and still exits with 0:

| Warning | What to do |
|---|---|
| `bay <id> (<board>): no board target: …` | set the board's target on the bay's page, or `platform` in the lab file: [Board targets](../use/board-targets.md) |
| `bay <id>: <device> S/N <serial> is not the board its target was saved for (…): check it, then save its target again on the node's page` | another board is in the port |
| `bay <id>: no USB device in the slot now (powered off?): no console path; …` | the board is not enumerated; its entry gets `connected: false` |
| `bay <id>: console none: no console, kept out of the tests (connected: false)` | the lab file says so |
| `bays <ids> use <runner> without a probe id: …, or flashing may hit the wrong board` | give each board its probe id |
| `bay <id>: <note>` | the board library's note on that board |

Read from `tools/bayctl.py`. What the exit codes are: [bayctl](bayctl.md#exit-codes). Running the map:
[Zephyr twister](../use/twister.md).

## The hub's events

The hub keeps its last 32 events in RAM, newest first; a restart of the hub loses them. Each has a kind.

| Kind | Text | When |
|---|---|---|
| `pd` | `VBUS <v> V: PD sink up` | a charger is plugged |
| `pd` | `contract: <v> V / <a> A (<w> W)`, with ` EPR`, and `, too low for the rows` under 15 V | a new contract; the 9 V of plug-in is always "too low for the rows" |
| `pd` | `20 V asked, VBUS stays at <v> V: the rows stay off` | the charger did not follow within 3 s |
| `pd` | `28 V asked, VBUS stays at <v> V: asking for 20 V` | the same for 28 V; only on a build that allows it |
| `pd` | `contract lost (PG high): rows off until it is back` | every row off at once |
| `pd` | `VBUS gone: no PD charger (running from the console USB-C)` | the charger was unplugged |
| `pd` | `contract preference: 20 V` | `hub pd 20v`, the page or the API |
| `pd` | `claimed: admin key set (BOOT pressed)`, `… (local shell)` | a claim confirmed |
| `row` | `row <X> on` | a row comes on in its turn |
| `row` | `row <X> switched on`, `row <X> switched off` | by hand (saved) |
| `row` | `row <X> power cycle (<ms> ms off)` | a cycle |
| `row` | `row <X> shed: <a> A > <b> A budget`, `… contract` | the rows drew more than the budget for 1 s, or than the contract for 250 ms |
| `row` | `row <X> back: the budget has room for it again` | a shed row returns |
| `row` | `budget margin <n> %`, `budget capped at <n> W`, `budget cap off: the contract's` | `hub budget` |
| `row` | `rows kept on across the controller reset: 0x<mask>` | the hub restarted with rows on (bit 0 is A) |
| `fault` | `row <X>: eFuse fault (current limit or over-temperature)` | a row's FLT on a row that is on |
| `fault` | `node <bay>: DUT switched off by a fault (<n> mA)`, `node <bay>: DUT in current limit (<n> mA)` | a node's alert |
| `fault` | `admin key forgotten (BOOT held 10 s): the hub can be claimed again`, `admin key forgotten (local shell)` | BOOT held, or `hub access reset` |
| `can` | `enumeration: <n> node(s)` | the hub numbered the rack bus |
| `can` | `node <bay> did not confirm its address: row <X> stops there` | the bays after it get no address |
| `can` | `node <bay> (0x<id>) lost: no STATUS for 3 s` | silent for 3.5 s; the text rounds it down |
| `can` | `node <bay> (0x<id>) back` | it answers again |
| `node` | `node <bay>: command 0x<op> done`, `refused`, `failed`, `unknown command` | a bay's answer to a command |
| `node` | `node <bay>: no answer to command 0x<op>` | three tries, 100 ms apart, unanswered |
| `firmware` | `firmware <version> confirmed itself` | an update stayed |
| `firmware` | `firmware <version> not healthy after <s> s: rebooting into <version>` | an update failed its trial |
| `firmware` | `update to <version> rolled back: running <version>` | after that restart |

The commands are numbered as on the rack bus: `0x01` power (on, off or cycle), `0x02` reset, `0x03`
bootloader, `0x04` identify, `0x05` reboot. `refused` comes from a reserved bay, which accepts identify only;
`failed` from a bay whose action failed, for instance a power-on whose DATA lead stayed off.

Read from `firmware/power-hub/src/pd.c`, `rows.c`, `bus.c`, `main.c`, `shell.c`,
`firmware/common/lib/update.c` and `firmware/bay-node/src/rack.c`. Where the events are shown:
[Rows and the rack's page](../use/rack-page.md#read-the-events).

## The co-processor's states

A DATA ×4's co-processor runs the logic analyzer from its RAM: the node loads the image at each power-up.
`/api/coproc` gives `load.state`; the analyzer card writes it after the image's name.

| `load.state` | The card | What it means |
|---|---|---|
| `idle` | "waiting for the co-processor" | not seen on USB yet |
| `loading` | "loading…" | the image is being written into its RAM |
| `started` | "starting" | written and started |
| `loaded` | "loaded in <ms> ms" | running |
| `failed` | "not loaded: <error>" | a load failed, for the reason given |
| `left to USB/IP` | "left to USB/IP after failed loads" | two loads failed in a row: the node stops trying and leaves the co-processor's bootloader to USB/IP, like any board |

With no image stored the card reads "No analyzer image on the node: bayctl coproc load", and the bootloader
is left to USB/IP as well. Read from
`firmware/bay-node/src/coproc.c` and `web/analyzer-card.mjs`. Loading an image:
[Logic analyzer](../use/logic-analyzer.md).
