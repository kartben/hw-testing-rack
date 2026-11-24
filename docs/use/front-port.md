# A laptop on the front port: classic mode

A laptop plugged into the USB-C port on a bay's front takes the bay's boards off the network and sees them
as if they were on its own desk, while the rack goes on powering and measuring them. It is the designed
answer for macOS and Windows, and for a bench with no network.

:::{status} written
The mode logic is in the firmware and the two USB switches are on the v1.0 bay node. No bench stand-in has
the switches, so classic mode has never run; on the stand-ins SERVICE is a jumper. See
[What exists today](../plan/status.md).
:::

## Three modes

Two analog USB switches on the bay node decide where the bay's USB goes. They follow two inputs, with no
firmware in between: the SERVICE slide switch, and the 5 V of a laptop on the front port, marked PC.

| SERVICE | Laptop on the PC port | The boards' USB goes to | The bay's LED |
|---|---|---|---|
| off | no | the bay node, which exports it over the network: **USB/IP** | dim blue, blue or green |
| off | yes | the laptop: **classic** | magenta |
| on | either | nowhere; the laptop talks to the node's own USB: **SERVICE** | yellow |

In all three the node keeps the boards' power: it switches each port, measures it and cuts it on a fault.
A DATA ×4's reset and boot lines and the node's AUX UART work in all three as well
([Power-cycle or reset a board](power-and-reset.md#reset-and-bootloader)). The laptop's 5 V is only sensed,
never used. Where the port, the switch and the LED are:
[What a bay can do](index.md#a-bay-from-the-front); every colour:
[LEDs, buttons and switches](../reference/leds-and-buttons.md).

## Plug a laptop into the front port

```{figure} ../img/photo-desk.jpg
:alt: Render of a two-row rack on a desk, a laptop beside it with a cable to the front port of bay B4

Render of the earlier two-row layout: a laptop on the front port of B4, the bay that the example rack keeps
for classic mode. The screens on the drawer fronts are not on a v1.0 bay.
```

Plug a USB-C cable from the laptop into the PC port. The switches turn at once, the LED goes magenta, and
the laptop enumerates the DATA board's USB hub with every board of the bay behind it: classic mode moves
the whole bay, not one board. Flash and debug with the tools you would use on a desk. Unplug, and the
boards are back on USB/IP. To take one board to the laptop on its own, unplug its short cable from the DATA
port and use your own cable: the rack then no longer powers or measures it.

The path is analog and passes high speed, 480 Mbit/s, where USB/IP is held to full speed by the node's USB
controller. By design none of the limits listed on [USB/IP and flashing](usb-and-flashing.md) applies to
it; no board has been tried on it.

The node's firmware must be running. The switches work without it, but the DATA lead is off until the
firmware turns it on, so on a blank or broken node the DATA board, its hub and the boards have no power and
the laptop sees nothing. Older text that promises classic mode "even with no firmware" predates node v1.0
([Known issues, and what will not work](../reference/known-limitations.md)).

While the laptop is plugged, the bay exports nothing: `usbip list` is empty for it, and a twister run that
reaches the bay fails when `bayctl prepare` gives up, `no USB device enumerated on the DUT port after 30 s`.
Keep a bay used this way out of twister's map ([Board targets](board-targets.md)). What a client already
attached over USB/IP sees at the moment the laptop is plugged is not known: nothing in the sources says, and
nobody has tried.

For a laptop that stays beside the rack, use a cable with a right-angle plug and run it along the tray's
front to a cable tie round the nearest side ladder's front post, then down the rack's side: nothing hangs
in front of the drawer below, which still opens.

## Force classic mode

The node can hold the switches in classic with no laptop detected, and remembers it across restarts. On the
bay's page it is the **USB/IP · Classic** choice of the **USB** card, whose *Data path* and *Front port*
lines say what the node sees (front port free, laptop plugged, or service).

With `bayctl`, and back:

```console
$ python tools/bayctl.py mode B3 classic
$ python tools/bayctl.py mode B3 usbip
```

The mode is the bay's: `bayctl mode B3.2 classic` does the same as `mode B3`. Going back to `usbip`
releases the switches; with a laptop still plugged the bay stays in classic.

Over HTTP, where `/api/status` reports the result as `path`, `force_classic`, `pc_detected` and `service`
([Bay node HTTP API](../reference/node-api.md)):

```console
$ curl -s -X POST bay-b3.local/api/mode -d '{"mode":"classic"}'
```

In the node's shell, where `bay mode` alone prints the path in use, whether classic is forced, and the state
of SERVICE and of the PC port:

```console
uart:~$ bay mode classic
uart:~$ bay mode
```

## SERVICE is for the node itself

With the SERVICE switch on, the PC port reaches the bay node's own USB, to flash or debug the node
([Flash the hub and the nodes](../build/flash.md)). The boards' USB goes nowhere: the node stops its USB
host and exports nothing while the switch is on, and a laptop on the port sees the node and none of the
boards. The boards stay powered. Slide SERVICE off and the node's USB host restarts with the boards back
on USB/IP.

A bay whose LED is yellow and whose boards have vanished from `usbip list` has its SERVICE switch on.
