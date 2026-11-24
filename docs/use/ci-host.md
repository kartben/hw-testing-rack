# Set up a CI host

A CI runner drives the rack with the same `bayctl` as a laptop and needs the same Linux set-up first: the
checkout, `usbip` and its kernel module, the sudo rule, the flashing tools, all on
[Set up bayctl and usbip](set-up-your-machine.md). On top of that it needs the hub's address in the job's
environment, the rights of its address on the nodes, and a board target on every port it tests.

:::{status} written
Worked out from `bayctl`'s code and from the repository's own workflow, which builds a hardware map from
the example lab file with no rack. Nobody has set up a CI host for a rack, and twister has never run
against one. See [What exists today](../plan/status.md#status-ci).
:::

## What a bay offers a CI job

| What | How |
|---|---|
| A board's power; on a DATA ×4, its RESET and BOOT lines | the node's HTTP API, port 80 |
| A board's USB device: its debug probe and the probe's serial port | USB/IP, TCP 3240 |
| A board's console | the board's own USB serial, once attached |
| The bay's one AUX UART | RFC 2217 on TCP 4001, raw bytes on TCP 4000, the page's console |
| Telemetry | Prometheus, `/metrics` on port 80 |
| Who may use the bay | access rules per node, a reservation per job |

`bayctl` wraps all of it, and writes the configuration of three test frameworks: a hardware map for
[Zephyr twister](twister.md), an environment for labgrid and a PDUDaemon configuration for LAVA
([labgrid and LAVA](labgrid-and-lava.md)).

## What the runner adds to a laptop's set-up

On top of a laptop's set-up:

- the sudo rule is for the CI user, because the pre-script runs as the user that runs twister;
- `BAYCTL_HUB` goes in the job's environment, unless `rack.local` resolves on the runner or the lab file
  says `hub:`. The pre-scripts read it again at every test, so they need the same environment as the step
  that made the map;
- `BAYCTL_KEY` stays off the runner: nothing a test job runs is signed (`hwmap`, `prepare`, `lease`,
  `release`, `power`, `attach`);
- once the nodes are claimed and their rules are on, the runner's address needs the services status,
  control, console and usbip; the shell is for admin hosts ([Access rules and security](access.md));
- every port the jobs test has its board target, set once on the bay's page
  ([Board targets](board-targets.md)).

Nobody has tried whether a job inside a container can use `vhci-hcd`, see `/dev/serial/by-id` and run
`sudo -n usbip`, and no source covers it.

## A whole job, from checkout to results

This sequence is worked out from [tools/bayctl.py](../../tools/bayctl.py) and from
[the repository's own workflow](../../.github/workflows/tools.yml); nobody has run it against a rack yet.
It runs in the `zephyr` directory of the runner's west workspace, with `RACK` set to a checkout of this
repository.

```sh
pip install pyyaml
export BAYCTL_HUB=rack-lab1.local
python "$RACK/tools/bayctl.py" list --probe
python "$RACK/tools/bayctl.py" hwmap -o rack-map.yaml --lease 30m
west twister --device-testing --hardware-map rack-map.yaml \
    -p xiao_esp32c3 -p rpi_pico2/rp2350a/m33_0 -T samples/hello_world
```

`list --probe` is there for the job's log: what the rack held and which node did not answer.

`hwmap` writes `rack-map.yaml` and a folder `rack-scripts` beside it. Both hold absolute paths to the
Python that ran `hwmap`, to `bayctl` and to the lab file, so make them in the job, on the runner, as the
user that runs twister. A port left out of the map is a warning on stderr and the exit code stays 0: read
the log. With `--lease 30m` each test reserves its board in the pre-script and releases it in a
post-script.

Twister runs the pre-script before each test, flashes with the runner and the `id` of the map, and reads
the console at `serial`. The `-p` values are the Zephyr boards of your rack's targets. `bayctl` adds
nothing to twister's reports. The map and the pre-script, field by field: [Zephyr twister](twister.md).

## What a job leaves behind

Nothing detaches and nothing is powered off when a run ends.

- Every board a test touched stays attached to the runner and powered. A node serves a USB device to one
  USB/IP client at a time, so nobody else can attach the board until the runner detaches it or the port
  is power-cycled.
- A post-script exists only with `hwmap --lease`, and it only releases the reservation. If a job dies
  between the two scripts, the reservation lapses by itself at the end of its 30 minutes.
- `prepare` switches a bay that was forced to classic mode back to USB/IP, and the node saves the mode.
  A bay kept for a laptop on its front port belongs out of the map.
- With `hwmap --power-cycle`, every test starts by detaching the board and cycling its port for 1000 ms.
- `rack-map.yaml` and `rack-scripts` stay where `hwmap` wrote them.

A job that must hand the boards back does it itself, by board or by bay:

```console
$ python tools/bayctl.py detach B3
$ python tools/bayctl.py power B3 off
```

What a power cycle or a restart of a node brings back by itself is on
[Power-cycle or reset a board](power-and-reset.md#after-a-power-cut-or-a-restart).

## Two hosts on one rack

A reservation keeps two jobs, or a job and a person, off the same board: while it lasts, power, reset and
the console answer only its holder. It works on a node nobody has claimed, before any access rule exists. `hwmap --lease` reserves port by port, and on firmware 0.5
a reservation of one port does not keep another host off that port's USB/IP:
[Reserve a bay](reserve-a-bay.md) says what each kind of reservation stops. For labgrid, take the
reservation in the job before acquiring the places.

One Wi-Fi channel carries 8 USB/IP flashes at full speed, a figure from a simulation
([Specifications](../reference/specifications.md#sessions-clients-and-flashes-at-once); the reason is on
[Wi-Fi in the rack](wifi.md)). Nothing
in `bayctl` or in the pre-scripts counts flashes: two hosts that each run twister can go past it.

`bayctl update --all` skips a bay reserved as a whole, unless `--force`; a reservation of one port, the
kind `hwmap --lease` takes, does not stop it. Beyond that, nobody knows whether it is safe to update nodes
while jobs run: a node that restarts ends its reservations and its USB/IP sessions
([Known issues, and what will not work](../reference/known-limitations.md)).
