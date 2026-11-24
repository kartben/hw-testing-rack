# Front port and classic mode

Plug a laptop into the USB-C port on the front of a bay, and the laptop sees the bay's boards as if they
were on its desk. Use it from macOS, which has no USB/IP client, from Windows without WSL2, or when there is
no network.

## Where the boards' USB goes

Two things decide where the boards' USB goes: a laptop on the front port, marked PC, and the SERVICE slide
switch.

| SERVICE | Laptop on the PC port | The boards' USB goes to | The bay's LED |
|---|---|---|---|
| off | no | the network: **USB/IP** | blue or green |
| off | yes | the laptop: **classic** | magenta |
| on | either | nowhere. The laptop reaches the node itself: **SERVICE** | yellow |

In every mode, the node still switches and measures each port, and the RESET and BOOT lines work. Where the
port and the switch are: [LEDs, buttons and switches](../reference/leds-and-buttons.md).

## Plug a laptop into the front port

```{figure} ../img/viewer/rack.jpg
:alt: The 3D model of a rack of three rows, a laptop beside it with a cable to the front port of bay B4

The 3D model: a laptop on the front port of bay B4.
```

Plug a USB-C cable from the laptop into the PC port. The LED turns magenta, and the laptop finds the DATA
board's USB hub with every board of the bay behind it. Flash and debug with your usual tools, at USB high
speed. Unplug the laptop, and the boards go back to USB/IP.

The node's firmware must be running, since it powers the DATA board.

While the laptop is plugged in, the bay shares nothing over the network. A twister run that uses the bay
fails, so keep the bay out of twister's map ([Board targets](board-targets.md#keep-a-board-out-of-twisters-map)).

For a laptop that stays beside the rack, use a cable with a right-angle plug. Tie it to the front post of the
nearest side ladder and run it down the side of the rack, so that the drawer below still opens.

## Force classic mode

You can keep a bay in classic mode with no laptop plugged in. The node remembers the mode when it restarts.

### In the browser

Choose **Classic** in the **USB** card of the bay's page.

### With bayctl

```console
$ python tools/bayctl.py mode B3 classic
$ python tools/bayctl.py mode B3 usbip
```

While a laptop is plugged in, the bay stays in classic mode even after `mode B3 usbip`. Every option:
[bayctl](../reference/bayctl.md#mode).

### Over HTTP

```console
$ curl -s -X POST bay-b3.local/api/mode -d '{"mode":"classic"}'
```

### In the node's shell

```console
uart:~$ bay mode classic
uart:~$ bay mode
```

`bay mode` alone prints the mode in use, and the state of SERVICE and of the PC port.

## Flash the node with SERVICE on

With the SERVICE switch on, the PC port reaches the bay node's own USB, to flash or debug the node
([Flash the hub and the nodes](../build/flash.md)). A laptop on the port sees none of the boards, but they
stay powered. Slide SERVICE off, and the boards come back on USB/IP.

If a bay's LED is yellow and its boards have gone from `usbip list`, its SERVICE switch is on.
