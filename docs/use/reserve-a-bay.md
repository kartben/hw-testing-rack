# Reserve a bay

A reservation hands a bay, or some of its ports, to one IP address for 10 s to 24 h: while it lasts, the
others can watch the bay but not drive what it covers. The API and `bayctl` call it a lease. It ends when its
holder releases it, when its time runs out, or when the node restarts, since it is kept in RAM only.

:::{status} simulated
Reservations of a bay and of single ports ran on native_sim and against the simulated node, with `bayctl`
and the bay's page. Not on a v1.0 bay node yet. See [What exists today](../plan/status.md#status-reserve).
:::

Needs: the control right from the address that reserves ([Access rules and security](access.md)). A node
that nobody claimed takes reservations too, so CI jobs keep out of each other's way before any rule exists.
For `bayctl`: [Set up bayctl and usbip](set-up-your-machine.md).

## In the browser

On the bay's page, **Reserve…** in the **Access** card. The dialog asks for how long (15 minutes, 1 hour,
4 hours or 24 hours) and for a note of up to 39 characters, shown to everyone else; on a bay with a DATA
board, tick the ports to reserve, or none for the whole bay. The card then shows *Reserved by you* with
**Release**, and renewing gives another hour. Everyone else sees the holder, the note and the minutes left,
and the page is read-only for what the reservation covers.

```{figure} ../img/web-ui-access-readonly.png
:class: bb-screenshot
:alt: Bay B2 seen from another address while a CI job holds it: a Read-only banner with the holder, its note and the time

Simulated node, the one-board form of the stand-ins. Bay B2 from another address while a CI job holds it.
```

## With bayctl, and from twister

```console
$ python tools/bayctl.py lease B3 --for 30m --note "twister job 8812"
$ python tools/bayctl.py release B3
```

`lease` prints the bay, the address that holds it and the seconds left (`B3 reserved for 192.168.1.41, 1800
s`); asked again by the same address, it renews. `--for` takes seconds or `15m`, `2h`, 1 h by default. Name a
port to reserve that port alone: `lease B3.2 --for 30m`. Every option:
[bayctl](../reference/bayctl.md#lease-and-release).

A twister run reserves each board before each test when its hardware map was made with `--lease`:

```console
$ python tools/bayctl.py hwmap -o rack-map.yaml --lease 30m
```

The pre-script then runs `prepare B3.2 --lease 30m`, which renews the reservation at every test, and a
post-script releases it. The duration covers one test, not the run: [Zephyr twister](twister.md). In a labgrid
job, take the reservation before the job acquires its places.

## Over HTTP

```console
$ curl -s -X POST bay-b3.local/api/lease -d '{"ttl_s": 1800, "note": "twister job 8812"}'
$ curl -s -X POST bay-b3.local/api/lease -d '{"ttl_s": 1800, "ports": ["B3.2"]}'
$ curl -s -X POST bay-b3.local/api/lease -d '{"release": true}'
```

`ttl_s` goes from 10 to 86400, 3600 when left out; a value outside answers 400, `ttl_s must be 10..86400`.
`ports` names sub-slots; without it the reservation is the bay's. The answer is the access document of
`GET /api/access`, which shows the reservation; its fields are on [Bay node HTTP API](../reference/node-api.md).

## In the node's shell

`bay access` shows the bay's reservation and each port's, and `bay access release` ends them all, over telnet
as well as on the UART pads.

## What it stops, and what it does not

A reservation of the whole bay:

- Power, reset, boot and mode, the console (web, RFC 2217, raw TCP) and USB/IP answer only the holder.
  Everyone else's sessions on them are closed when it starts.
- Over HTTP the others get 423: `reserved by 192.168.1.41 (twister job 8812), 30 min left`.
- The hub's commands that disturb the board (power, reset, bootloader, reboot) are refused, from the rack's
  page as from `bayctl hub node`; identify is not ([Rows and the rack's page](rack-page.md)).
- A firmware update is refused unless the admin forces it ([Update the firmware](update-firmware.md)).
- Only the holder's request switches the camera's light on.
- It is refused while another address holds one of the bay's ports: 423, `B3.2 reserved by 192.168.1.42`.

A reservation of one port, `B3.2`:

- The port's power, reset and bootloader answer only the holder; the others get 423,
  `B3.2 reserved by 192.168.1.41 (twister job 8812), 30 min left`.
- On a DATA ×4, a change of the wires that touches the port's pins is refused (423)
  ([Wires between boards](wires.md)).
- The bay's other ports stay free.
- USB/IP is not covered. Every board of a bay shares TCP 3240, and the node has no check at import time, so
  another host can still attach `B3.2`. To keep a board's USB/IP to yourself, reserve the whole bay. (The
  design note [One node, several boards](../multi-dut-node.md) describes that check as if it existed; it is
  not written.)

Neither kind outlives a restart of the node: an update, a fatal error, its RESET, a power cut. Afterwards
the bay is free, and whatever the job had switched off is on again
([After a power cut or a restart](power-and-reset.md#after-a-power-cut-or-a-restart)). The refusals and their
texts are on [States and error messages](../reference/states-and-messages.md).

## End someone else's reservation

A reservation that a dead job left lapses when its time is up. Before that, only its holder or an admin ends
it; anyone else gets 403, `only its holder or an admin may release it`. An admin ends it with **Release** in
the Access card, from a browser that holds the admin key, or with `bayctl` and the key in `BAYCTL_KEY`:

```console
$ python tools/bayctl.py release B3 --force
```

(`B3.2` for one port.) In the node's shell, `bay access release` ends the bay's reservation and every port's;
over telnet it needs only the shell right, which is why that right is for admin hosts. Restarting the node
also ends it, and restarts every board of the bay with it.
