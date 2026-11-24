# Set up a CI host

A CI runner drives the rack with the same `bayctl` as a laptop and needs the same Linux set-up first: the
checkout, `usbip` and its kernel module, the sudo rule, the flashing tools, all on
[Set up bayctl and usbip](set-up-your-machine.md). On top of that it needs the hub's address in the job's
environment, the rights of its address on the nodes, and a board target on every port it tests.

:::{status} written
Worked out from `bayctl`'s code and from the repository's own workflow, which builds a hardware map from
the example lab file with no rack. The job's skeleton ran against the simulated node up to its first
`usbip` call. Nobody has set up a CI host for a rack, and twister has never run against one. See
[What exists today](../plan/status.md#status-ci).
:::

## What a bay offers a CI job

| What | How |
|---|---|
| A board's power; on a DATA ×4, its RESET and BOOT lines | the node's HTTP API, port 80 |
| A board's USB device: its debug probe and the probe's serial port | USB/IP, TCP 3240 |
| A board's console | the board's own USB serial, once attached |
| Telemetry | Prometheus, `/metrics` on port 80 |
| Who may use the bay | access rules per node, a reservation per job |

`bayctl` wraps all of it, and writes the configuration of three test frameworks: a hardware map for
[Zephyr twister](twister.md), an environment for labgrid and a PDUDaemon configuration for LAVA
([labgrid and LAVA](labgrid-and-lava.md)).

## How many boards a bay gives a job on firmware 0.5

Two limits of the v1.0 boards and of firmware 0.5 decide what a job can test, before any test is written:

| In the bay | Ports a job can use | Why |
|---|---|---|
| a DATA ×4 | 4, but four boards may not all be on at once | on the default 5.4 W grant the four ports share 2.4 to 3.1 W: about 105 mA each with the DATA ×4 at its worst, 135 mA at its typical draw. A board over that gets 409 from `prepare`, which sends a plain power-on |
| a DATA ×6 | 1 to 4 | the node keeps four board targets and serves `/api/ports/<n>/power` for ports 1 to 4: `bayctl` cannot switch ports 5 and 6, and they hold no target on the node |

The DATA ×4's figures are estimates, nothing has been measured
([Power budget and queued ports](power-budget.md#what-54-w-per-bay-buys)); a rack of fewer columns gives
each bay more. Ports 5 and 6 can enter a map only through a target in the lab file, and their pre-script
then fails each time it has to switch the port. Both limits, with the others of firmware 0.5:
[Known issues, and what will not work](../reference/known-limitations.md).

## What the runner adds to a laptop's set-up

- The sudo rule is for the CI user, because the pre-script runs as the user that runs twister.
- `BAYCTL_HUB` goes in the job's environment, unless `rack.local` resolves on the runner or the lab file
  says `hub:`. The pre-scripts read it again at every test, so they need the same environment as the step
  that made the map.
- `BAYCTL_KEY` stays off the runner: nothing a test job runs is signed (`hwmap`, `prepare`, `lease`,
  `release`, `power`, `attach`).
- Once the nodes are claimed and their rules are on, the runner's address needs the services status,
  control, console and usbip; the shell is for admin hosts ([Access rules and security](access.md)).
- Every port the jobs test has its board target, set once on the bay's page
  ([Board targets](board-targets.md)).

Nobody has tried whether a job inside a container can use `vhci-hcd`, see `/dev/serial/by-id` and run
`sudo -n usbip`, and no source covers it.

## A whole job, from checkout to results

Worked out from [tools/bayctl.py](../../tools/bayctl.py); nobody has run it against a rack yet. It runs
in the `zephyr` directory of the runner's west workspace, with `RACK` set to a checkout of this
repository, against a hub that was given `hub id lab1` ([Bays, ports and addresses](names.md)). It tests
the XIAO ESP32-C3 on B3.1; `PORTS` lists the ports a job tests.

```{code-block} sh
:caption: the job's script
set -eu
pip install pyyaml
export BAYCTL_HUB=rack-lab1.local
bayctl() { python "$RACK/tools/bayctl.py" "$@"; }
PORTS="B3.1"

# Set-up: hold the bay; power, enumerate and attach each port
bayctl lease B3 --for 2h --note "job ${CI_JOB_ID:-}"
trap 'bayctl detach B3 || true; bayctl release B3 || true' EXIT
bayctl list --probe
for p in $PORTS; do bayctl prepare "$p"; done

# The map, and the gate: every port under test is in it, connected
bayctl hwmap -o rack-map.yaml
python - rack-map.yaml $PORTS <<'EOF'
import sys, yaml
up = {f[4:] for e in yaml.safe_load(open(sys.argv[1])) or [] if e["connected"]
      for f in e["fixtures"] if f.startswith("bay:")}
missing = sorted(set(sys.argv[2:]) - up)
sys.exit(f"not connected in the map: {' '.join(missing)}" if missing else 0)
EOF

west twister --device-testing --hardware-map rack-map.yaml \
    -p xiao_esp32c3 -T samples/hello_world
```

The job must fail when the rack gives it nothing to test, and `bayctl` alone does not fail it:

- `hwmap` exits 0 whatever it finds. A board that is off, still enumerating or without a console path is
  written `connected: false` with a warning on stderr, and twister passes over such an entry. An empty port
  is left out with no warning at all.
- `list --probe` prints `unreachable` for a node that does not answer, and exits 0. It is there for the
  job's log.
- `connected: true` proves nothing either: a lab file's `serial:` gives an entry its console path with the
  node off.

So the set-up runs `prepare` on each port first. It exits 1, and stops the job, when the node does not
answer, when the port gets no power (409, the bay's share is used up; 423, someone else holds it), when no
device enumerates within 30 s, or when the attach or the console fails: the six steps and their messages
are on [Zephyr twister](twister.md#what-the-pre-script-does-and-when-it-fails). The gate then checks the
map against `PORTS`. A board powered off at the end of an earlier job is switched on again by `prepare`.

`hwmap` writes `rack-map.yaml` and a folder `rack-scripts` beside it. Both hold absolute paths to the
Python that ran `hwmap`, to `bayctl` and to the lab file, so make them in the job, on the runner, as the
user that runs twister. Twister runs the pre-script before each test, flashes with the runner and the `id`
of the map, and reads the console at `serial`. `bayctl` adds nothing to twister's reports. The map and the
pre-script, field by field: [Zephyr twister](twister.md).

The example is a XIAO ESP32-C3 because its `esp32` runner needs nothing but the serial port. A board
flashed with `uf2`, such as a Pico 2, needs its bootloader's drive mounted on the runner (by udisks or an
fstab entry) and the port's BOOT line wired: leave it out of CI until that works by hand
([USB/IP and flashing](usb-and-flashing.md#uf2-boards-and-esp32-boards)).

## What a job leaves behind

Nothing detaches and nothing is powered off when twister ends; the job above detaches and releases in its
`trap`.

- Every board a test touched stays attached to the runner and powered. A node serves a USB device to one
  USB/IP client at a time, so nobody else can attach the board until the runner detaches it or the port
  is power-cycled.
- A post-script exists only with `hwmap --lease`, and it only releases the reservation. A reservation
  that a dead job left lapses at the end of its duration.
- `prepare` switches a bay that was forced to classic mode back to USB/IP, and the node saves the mode.
  A bay kept for a laptop on its front port belongs out of the map.
- With `hwmap --power-cycle`, every test starts by detaching the board and cycling its port for 1000 ms.
- `rack-map.yaml` and `rack-scripts` stay where `hwmap` wrote them.

To hand the boards back by hand, detach them. `power B3 off` as well only if nobody needs them: the next
job's `prepare` switches them on again, but a `hwmap` run before that writes each one `connected: false`.

```console
$ python tools/bayctl.py detach B3
```

What a power cycle or a restart of a node brings back by itself is on
[Power-cycle or reset a board](power-and-reset.md#after-a-power-cut-or-a-restart).

## Two hosts on one rack

A reservation keeps two jobs, or a job and a person, off the same board: while it lasts, power, reset and
the console answer only its holder. It works on a node nobody has claimed, before any access rule exists.
Only a reservation of the whole bay keeps another host off its boards' USB/IP on firmware 0.5
([Reserve a bay](reserve-a-bay.md)), which is why the job above leases `B3` and runs `hwmap` without
`--lease`: `hwmap --lease` reserves port by port, before each test.

- The pre-scripts then run as the holder of the bay.
- A bay lease is refused (423) while another host holds any of its ports; the runner's own port leases do
  not stand in its way.
- The same `lease` command, from the holder, renews the reservation: a run longer than its duration renews
  it, or takes a longer one, 24 h at most.
- For labgrid, take the reservation in the job before acquiring the places.

One Wi-Fi channel carries 8 USB/IP flashes at full speed, a figure from a simulation
([Specifications](../reference/specifications.md#sessions-clients-and-flashes-at-once)). Nothing in
`bayctl` or in the pre-scripts counts flashes: two hosts that each run twister can go past it.

`bayctl update --all` skips a bay reserved as a whole, unless `--force`; a reservation of one port does not
stop it. Beyond that, nobody knows whether it is safe to update nodes while jobs run: a node that restarts
ends its reservations and its USB/IP sessions
([Known issues, and what will not work](../reference/known-limitations.md)).
