# Reserve a bay

A reservation gives a bay, or some of its ports, to one IP address for 10 s to 24 h. While it lasts, other
people can watch the bay but cannot use it. The API and `bayctl` call it a lease.

A reservation ends when its holder releases it, when its time runs out, or when the node restarts. To reserve,
your address needs the control service ([Control who can use the rack](access.md)).

## In the browser

On the bay's page, press **Reserve…** in the **Access** card. Choose how long, and write a note of up to 39
characters for the others to see. Tick the ports to reserve, or none for the whole bay. The card then shows
*Reserved by you* with **Release**. Everyone else sees who holds the bay, the note and the time left.

```{figure} ../img/web-ui-access-readonly.png
:class: bb-screenshot
:alt: Bay B2 seen from another address while a CI job holds it: a Read-only banner with the holder, its note and the time

Simulated node. Bay B2 from another address while a CI job holds it.
```

## With bayctl

```console
$ python tools/bayctl.py lease B3 --for 30m --note "twister job 8812"
B3 reserved for 192.168.1.41, 1800 s
$ python tools/bayctl.py release B3
```

`--for` takes seconds, or `15m`, `2h`. The default is 1 h. Run `lease` again to renew. To reserve one port
alone, name it: `lease B3.2`. To reserve each board during its twister test, see
[Reserve each board for its test](twister.md#reserve-each-board-for-its-test).

## Over HTTP

```console
$ curl -s -X POST bay-b3.local/api/lease -d '{"ttl_s": 1800, "note": "twister job 8812"}'
$ curl -s -X POST bay-b3.local/api/lease -d '{"ttl_s": 1800, "ports": ["B3.2"]}'
$ curl -s -X POST bay-b3.local/api/lease -d '{"release": true}'
```

`ttl_s` goes from 10 to 86400, and is 3600 when left out. Without `ports`, the reservation is for the whole
bay ([Bay node HTTP API](../reference/node-api.md#access-and-reservations)).

## In the node's shell

`bay access` shows the reservations. `bay access release` ends them all.

## What a reservation blocks

A reservation of the whole bay:

- Power, reset, boot, mode, the console and USB/IP answer only the holder. Other sessions are closed.
- The others get 423: `reserved by 192.168.1.41 (twister job 8812), 30 min left`.
- The hub's power and reset commands for the bay are refused.
- A firmware update is refused, unless the admin forces it.
- Only the holder can switch the camera's light on.
- You cannot take it while another address holds one of the bay's ports: 423, `B3.2 reserved by 192.168.1.42`.

A reservation of one port, for example `B3.2`:

- The port's power, reset and bootloader answer only the holder.
- On a DATA ×4, nobody else can change the wires on the port's pins.
- USB/IP is not covered: another host can still attach the board. To keep a board's USB to yourself, reserve
  the whole bay.

A node keeps its reservations in RAM. When it restarts, the bay is free and every port is on again
([After a power cut or a restart](power-and-reset.md#after-a-power-cut-or-a-restart)).

## End someone else's reservation

A reservation left by a job that died ends when its time is up. Before that, only its holder or an admin can
end it. As an admin, press **Release** in the Access card, or run `bayctl` with the key in `BAYCTL_KEY`:

```console
$ python tools/bayctl.py release B3 --force
```

`bay access release` in the node's shell ends it too.
