# LEDs, buttons and switches

A bay shows its state on one RGB LED behind the fascia, the power box on ten LEDs in its front wall, and each
DATA port on a green LED of its own. The bay node has two buttons and the SERVICE switch; the power hub has two
buttons, reached with a pin through the box's lid.

:::{status} written
The firmware drives every LED and button below; the tables are read from it and from the PCBs' design files.
No colour has been seen on a bay node or a hub. On a XIAO ESP32-S3 stand-in, a press on BOOT confirmed a claim.
See [What exists today](../plan/status.md#status-led).
:::

## The bay's LED

The LED shows one state at a time. The firmware looks down this list every 250 ms and shows the first line
that applies, so a fault hides the USB/IP state under it.

<!-- site:bay-led -->
| Colour | Meaning |
|---|---|
| {led}`off` off | no firmware, or the node is starting |
| {led}`white blink` {led}`blue blink` white and blue in turn, fast | identify: someone asked "which one is it?" from the rack's page or with `hub node … identify`; 10 s |
| {led}`white blink` white, blinking twice a second | a claim waits: press BOOT briefly to confirm it |
| {led}`red blink` red, blinking twice a second | the DATA lead was switched off by a fault: its eFuse tripped, a short at switch-on, or the DATA board stopped answering |
| {led}`yellow` yellow | SERVICE: the front port goes to the node itself |
| {led}`magenta` magenta | classic mode: the boards' USB goes to the front port (a laptop plugged, or forced) |
| {led}`white dim` dim white | the DATA lead is off: no board of the bay has power |
| {led}`orange blink` orange, blinking once every 2 s | USB/IP mode, no network yet |
| {led}`blue dim` dim blue | USB/IP ready, no USB device enumerated on any port |
| {led}`blue` blue | at least one board enumerated and exportable |
| {led}`green` green | at least one USB/IP client attached |
<!-- /site:bay-led -->

Read from `firmware/bay-node/src/status_led.c` (`pick()`) and `src/dut.c`.

On a bay with a DATA board the LED speaks for the whole bay: "dim white" is the DATA lead off, not one port,
and blue or green means one board or more. Red is for the DATA lead itself. A port in over-current does not
turn it red: its 5 V is latched off and the bay's page shows the port in red
([Power-cycle or reset a board](../use/power-and-reset.md#after-an-over-current)). A lead that stays off for
another reason (a reversed lead, no DATA board) shows dim white; the reason is on the bay's page and in
`bay power` ([States and error messages](states-and-messages.md#why-the-data-lead-stays-off)).

```{figure} ../img/photo-detail.jpg
:alt: Two bays of the rack seen from the front, each fascia with its status LED lit

Render of an earlier layout, with a front display that node v1.0 does not have. The status LED is the dot at
the left of each fascia: green at B2, a client attached; blue on the bay at the right edge.
```

## The power box's LEDs

The front wall carries an ON and a FAULT LED for each row, with the row's letter under the pair, then PD and
CTL. The console USB-C sits under the same CTL label.

<!-- site:power-box-leds -->
| LED | Lit when |
|---|---|
| ON, {led}`green` green, one per row | the row's output carries VRACK. Dark while the row is off, shed or cycling, and with no contract |
| FAULT, {led}`red` red, one per row | the row's eFuse reports a fault, current limit or over-temperature, on a row that is switched on. The eFuse holds the row at its limit and retries by itself; the hub does not switch the row off |
| PD, {led}`green` green | the charger and the hub's PD sink hold a contract (the sink's power-good line), with or without firmware: already at the 9 V of plug-in |
| CTL, {led}`green` green | the controller's firmware: the first pattern below that applies |

| CTL | Meaning |
|---|---|
| {led}`green blink` flicker, four times a second | a claim waits for a press on the hub's BOOT |
| {led}`green blink` fast blink, twice a second | a row in fault |
| {led}`green blink` double blink, two short flashes a second | rows shed for lack of power |
| {led}`green blink` slow blink, once a second | no PD charger (the controller runs from the console USB-C), or the contract is not final yet |
| {led}`green` on | contract final, every row as wanted |

ON and FAULT are wired on the hub (`electronics/power-hub/design.py`), CTL is
`led_level()` in `firmware/power-hub/src/main.c`.
<!-- /site:power-box-leds -->

A contract is final once it is of 15 V or more and has held 500 ms; the rows come on after that, 300 ms apart.
What a shed row is: [Power budget and queued ports](../use/power-budget.md#when-the-rack-is-over-the-chargers).

```{figure} ../img/power-box.jpg
:alt: The power box with its lid off, seen from the rear and from the front

Render of hub v0.5 in its box. The front wall, right: the ON and FAULT pair of each row, PD, CTL and the
console USB-C. The v1.0 hub keeps that order.
```

## A DATA port's LED

Each port of a DATA ×6 and of a DATA ×4 has a {led}`green` green LED on its switched 5 V: lit while the port is on. It stays
dark for a port that is off, waiting for power, shed or latched off by an over-current
([States and error messages](states-and-messages.md#a-ports-states)). On the DATA ×4 the LED sits over the west
end of the port's pin header, by the port's number; the rear bay cover has a window in front of each.

The DATA ×4 has one LED more, D1, {led}`green` green, on the co-processor's GPIO25. The image loaded into the co-processor
drives it (the analyzer's, as on a Pico 2), and no document says what its patterns mean.

The camera pod's four {led}`white` white LEDs are the camera's light, switched from the bay's page
([Camera](../use/camera.md)).

## Buttons and the SERVICE switch of a bay node

<!-- site:node-buttons -->
| Control | What it does | Where, and does the bay open |
|---|---|---|
| BOOT (SW2) | short press: confirms a pending claim. Held 1 s or more, then released: power-cycles the DATA lead, every board of the bay, 1 s off. Held 10 s: forgets the admin key, the access rules and the reservation. Held while the node starts: the ESP32's ROM loader | top face, beside RESET. Drawer in: a pin through the hole in the drawer floor and the board plate. Drawer out: BOOT is clear |
| RESET (SW1) | restarts the node (the ESP32's EN). The DATA lead goes off until the restarted firmware has checked it again | the same pin hole, drawer in. Drawer out: it sits partly under the tray's left ledge; a notch in the ledge lets a pin reach it |
| SERVICE (SW3), slide switch | on: the front USB-C goes to the node's own USB, for flashing and its console, and the boards' USB is cut off. The LED turns yellow | the fascia, right of the PC port: the bay stays closed |
<!-- /site:node-buttons -->

Read from `firmware/bay-node/src/main.c` (the BOOT button), `mechanical/parts/drawer.scad` and `tray.scad`
(the pin holes and the notch).

:::{warning}
A long press on BOOT power-cycles every board of the bay, whoever is flashing one, and the release decides:
let go before 1 s to only confirm a claim, and hold past 10 s only to clear the node's access control.
:::

The front port's modes, SERVICE among them, are on [Front port and classic mode](../use/front-port.md);
a claim, and what a cleared node accepts, on [Access rules and security](../use/access.md); BOOT and RESET
together, for a node whose firmware is wedged, on [Recover a node or a hub](../use/recover.md).

## RST and BOOT on the power box

The hub's two buttons sit at the rear left of its PCB, under two holes in the lid marked RST and BOOT. A pin
goes down a guide tube onto each, with the box closed.

<!-- site:hub-buttons -->
| Button | What it does |
|---|---|
| BOOT | short press: confirms a pending claim (CTL flickers while one waits). Held 10 s: forgets the hub's admin key, and the hub can be claimed again. Held while the controller starts: the ESP32's ROM loader |
| RST | restarts the controller. The row enables are held through the restart, so the rows and the bays stay powered (by design; to be checked on the first hub); the hub's events are lost |
<!-- /site:hub-buttons -->

Read from `firmware/power-hub/src/main.c` and `docs/firmware.md`.

The console USB-C flashes the hub whatever its firmware does, so BOOT and RST are the last resort
([Recover a node or a hub](../use/recover.md)). On that console, `hub access claim` does what a short press on
BOOT does, and `hub access reset` what a 10 s press does ([Power hub shell](hub-shell.md)).
