# LEDs, buttons and switches

This page says what each light on the rack means and what each button does.

Each bay has one status LED on its {term}`fascia`. The power box has ten LEDs in its front wall. Each port of a
DATA board has a green LED. The bay node has two buttons and a slide switch, and the power hub has two
buttons.

## The bay's LED

The LED shows one state at a time: the first line of this table that applies.

<!-- site:bay-led -->
| Colour | Meaning |
|---|---|
| {led}`off` off | no firmware, or the node is starting |
| {led}`white blink` {led}`blue blink` white and blue in turn, fast | identify: someone asked for this bay to show itself, from the rack's page or with `hub node … identify`. It lasts 10 s |
| {led}`white blink` white, blinking twice a second | a claim is waiting: press BOOT briefly to confirm it |
| {led}`red blink` red, blinking twice a second | a fault switched the DATA lead off: its eFuse tripped, a short at switch-on, or the DATA board stopped answering |
| {led}`yellow` yellow | SERVICE: the front port goes to the node itself |
| {led}`magenta` magenta | classic mode: the boards' USB goes to the front port (a laptop is plugged in, or the mode is forced) |
| {led}`white dim` dim white | the DATA lead is off: no board of the bay has power |
| {led}`orange blink` orange, blinking once every 2 s | USB/IP mode, no network yet |
| {led}`blue dim` dim blue | USB/IP ready, no USB device on any port |
| {led}`blue` blue | at least one board is enumerated and ready to attach |
| {led}`green` green | at least one USB/IP client is attached |
<!-- /site:bay-led -->

Source: `pick()` in `firmware/bay-node/src/status_led.c`.

The LED shows the state of the whole bay. A single port in over-current does not turn it red: the port's 5 V
is latched off, and the bay's page shows that port in red
([After an over-current](../use/power-and-reset.md#after-an-over-current)).

When the {term}`DATA lead` stays off for a reason other than a fault, such as a reversed lead, the LED shows
dim white. The bay's page gives the reason
([Why the DATA lead stays off](states-and-messages.md#why-the-data-lead-stays-off)).

At power-up the LED may show any colour until the firmware sets it.

## The power box's LEDs

The front wall has an ON and a FAULT LED for each row, with the row's letter under the pair. Then come the PD
LED, the CTL LED and the console USB-C. The CTL label is under the CTL LED and the USB-C.

```{figure} ../img/viewer/power-box-front.jpg
:alt: The front of the power box: four pairs of LEDs over the letters A to D, then the PD and CTL LEDs and the console USB-C

The 3D model: the front of the power box. Each pair is ON, then FAULT.
```

<!-- site:power-box-leds -->
| LED | Lit when |
|---|---|
| ON, {led}`green` green, one per row | the row's output carries {term}`VRACK`. Dark while the row is off, shed or cycling, and with no contract |
| FAULT, {led}`red` red, one per row | the row's eFuse reports a fault (current limit or over-temperature) on a row that is on. The eFuse holds the row at its limit and retries by itself. The hub does not switch the row off |
| PD, {led}`green` green | the charger and the hub hold a USB PD contract, with or without firmware. It lights at the 9 V of plug-in |
| CTL, {led}`green` green | the hub's firmware runs: the first pattern below that applies |

| CTL | Meaning |
|---|---|
| {led}`green blink` flicker, four times a second | a claim is waiting for a press on the hub's BOOT |
| {led}`green blink` fast blink, twice a second | a row is in fault |
| {led}`green blink` double blink, two short flashes a second | rows are shed for lack of power |
| {led}`green blink` slow blink, once a second | no PD charger (the hub runs from its console USB-C), or the contract is not final yet |
| {led}`green` on | the contract is final, and every row is as wanted |
<!-- /site:power-box-leds -->

Source: `electronics/power-hub/design.py` for ON, FAULT and PD, `led_level()` in
`firmware/power-hub/src/main.c` for CTL.

The USB PD contract between the charger and the hub is final once it is 15 V or more and has held for
500 ms. The rows then come on, 300 ms apart. A row is {term}`shed` when the rack needs more power than the
charger gives ([Power budget and queued ports](../use/power-budget.md#when-the-rack-draws-more-than-the-charger-gives)).

## The LEDs of a DATA board and a camera pod

Each port of a DATA ×6 or a DATA ×4 has a {led}`green` green LED on its switched 5 V. It is lit while the port
is on, and dark in every other state ([A port's states](states-and-messages.md#a-ports-states)). On the
DATA ×4 the LED sits at the left end of the port's pin header, next to the port's number. The cover of the rear
bay, at the back of the drawer, has a window in front of each LED.

The DATA ×4 has one more green LED, D1. The analyzer image in its co-processor drives it.

The camera pod's four {led}`white` white LEDs are the camera's light. You switch them from the bay's page
([Camera](../use/camera.md)).

## The bay node's buttons and SERVICE switch

The node has two buttons side by side on its top face, BOOT (SW2) and RESET (SW1). The SERVICE slide switch
(SW3) is on the fascia, to the right of the PC port.

<!-- site:node-buttons -->
| Control | What it does |
|---|---|
| BOOT, short press | confirms a waiting claim |
| BOOT, held 1 s or more, then released | power-cycles the DATA lead: every board of the bay goes off for 1 s |
| BOOT, held 10 s | forgets the admin key, the access rules and the reservation |
| BOOT, held while the node starts | starts the ESP32's ROM loader |
| RESET | restarts the node. The DATA lead goes off, and every board of the bay with it, until the firmware has checked it again |
| SERVICE, on | the front USB-C goes to the node's own USB, for flashing it and for its console. The boards' USB is cut off and the LED turns yellow |
<!-- /site:node-buttons -->

To reach BOOT or RESET with the drawer in, push a pin through the hole in the drawer floor and the board
plate. With the drawer out, BOOT is clear, and RESET sits partly under the tray's left ledge, which has a
notch for a pin. You can use SERVICE with the bay closed.

Source: `firmware/bay-node/src/main.c`, and `mechanical/parts/drawer.scad` and `tray.scad` for the holes.

:::{warning}
BOOT acts when you release it. Let go before 1 s to confirm a claim only: a longer press power-cycles every
board of the bay, even one that someone is flashing. Hold it past 10 s only to clear the node's access
control.
:::

[Front port and classic mode](../use/front-port.md) explains the modes of the front port.
[Control who can use the rack](../use/access.md) explains claims and the admin key. To use BOOT and RESET on a
node whose firmware is stuck, see [Recover a node or the hub](../use/recover.md).

## The power hub's buttons

The hub's two buttons sit at the rear left of its PCB, under two holes in the lid marked RST and BOOT. Push a
pin into a hole: a guide tube leads it onto the button, so you can leave the box closed.

<!-- site:hub-buttons -->
| Button | What it does |
|---|---|
| BOOT, short press | confirms a waiting claim. CTL flickers while one waits |
| BOOT, held 10 s | forgets the hub's admin key, so the hub can be claimed again |
| BOOT, held while the hub starts | starts the ESP32's ROM loader |
| RST | restarts the hub's controller. The rows and the bays stay powered. The hub's events are lost |
<!-- /site:hub-buttons -->

Source: `firmware/power-hub/src/main.c`.

The console USB-C can flash the hub whatever its firmware does, so BOOT and RST are a last resort
([Recover a node or the hub](../use/recover.md)). On that console, `hub access claim` does the same as a short
press on BOOT, and `hub access reset` the same as a 10 s press ([Power hub shell](hub-shell.md)).
