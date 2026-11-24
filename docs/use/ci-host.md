# Set up a CI host

A CI runner uses the rack through `bayctl`, the same way a laptop does. This page lists what the runner needs
and gives a job script to start from. `bayctl` also writes the configuration for
[twister](twister.md) and for [labgrid and LAVA](labgrid-and-lava.md).

## What the runner needs

- Everything on [Set up your machine](set-up-your-machine.md): a checkout of this repository, a virtual
  environment with PyYAML, `usbip` and its kernel module, and the flashing tools. The sudo rule is for the
  user that runs twister: the pre-scripts run `sudo -n usbip` as that user.
- `BAYCTL_HUB` in the environment of every step of the job, unless `rack.local` resolves on the runner or the
  lab file sets `hub:`. The pre-scripts read it again before each test.
- No admin key. A test job sends no signed request, so keep `BAYCTL_KEY` off the runner.
- If the nodes have access rules, the status, control, console and usbip services for the runner's address
  ([Control who can use the rack](access.md)).
- A board target on every port the jobs test ([Board targets](board-targets.md)).

## Which boards a job can use

A job powers each board, attaches its USB device over USB/IP and reads its console on the board's own USB
serial port. These limits apply:

- On a DATA ×6, `bayctl` switches ports 1 to 4 only. Put the boards a job must power in those ports
  ([Limitations](../reference/known-limitations.md#the-firmware)).
- A bay may not have enough power for all its boards at once. Its share of the charger depends on how many
  columns your rack has. `prepare` does not wait for power, so the job below runs `power on --wait` first
  ([Power budget and queued ports](power-budget.md)).
- Leave out of CI any board flashed with `uf2`, such as a Pico 2, until you can flash it by hand through the
  rack. It needs the drive of its bootloader mounted on the runner, and its BOOT line wired
  ([UF2 boards and ESP32 boards](usb-and-flashing.md#uf2-boards-and-esp32-boards)).

### How many boards one host can attach

Each board a job attaches takes a port of the runner's virtual USB controller, `vhci-hcd`. With the Linux
kernel's default settings, one host attaches 8 boards at a time. Half of the controller's ports are for USB 3
devices, which a bay does not have. So to check yours, halve the number that this prints:

```console
$ cat /sys/devices/platform/vhci_hcd.0/nports
```

Twister keeps each board attached after its test. So list at most that many ports in one job. For more boards,
run one job per bay and detach the boards between jobs, or spread the bays over several runners.

## A job, from checkout to results

This script tests the XIAO ESP32-C3 on B3.1. Run it in the `zephyr` directory of the runner's west workspace,
with the workspace's virtual environment active: it has west, twister and PyYAML. `RACK` is a checkout of this
repository. The hub has the id `lab1`, so its name is `rack-lab1.local` ([Bays, ports and addresses](names.md)).
`PORTS` lists the ports the job tests, and the job reserves their bays.

```{code-block} sh
:caption: the job's script
set -eu
export BAYCTL_HUB=rack-lab1.local
bayctl() { python "$RACK/tools/bayctl.py" "$@"; }
PORTS="B3.1"
BAYS=$(for p in $PORTS; do echo "${p%%.*}"; done | sort -u)

# Set-up: hold the bays; power, enumerate and attach each port
for b in $BAYS; do
    bayctl lease "$b" --for 2h --note "job ${CI_JOB_ID:-}"
done
hand_back() {
    for b in $BAYS; do
        bayctl detach "$b" || true
        bayctl release "$b" || true
    done
}
trap hand_back EXIT
bayctl list --probe
for p in $PORTS; do
    bayctl power "$p" on --wait 300
    bayctl prepare "$p"
done

# The map: only the ports under test, each one connected
bayctl hwmap -o rack-map.yaml
python - rack-map.yaml $PORTS <<'EOF'
import sys, yaml
path, ports = sys.argv[1], sys.argv[2:]
want = {f"bay:{p}" for p in ports}
keep = [e for e in yaml.safe_load(open(path)) or []
        if want & set(e["fixtures"])]
up = {f[4:] for e in keep if e["connected"]
      for f in e["fixtures"] if f in want}
missing = sorted(set(ports) - up)
if missing:
    sys.exit(f"not connected in the map: {' '.join(missing)}")
yaml.safe_dump(keep, open(path, "w"), sort_keys=False)
EOF

west twister --device-testing --hardware-map rack-map.yaml \
    -p xiao_esp32c3 -T samples/hello_world
```

The job must fail when the rack gives it nothing to test. `hwmap` and `list --probe` exit 0 whatever they
find, so the script checks for itself:

1. `power on --wait 300` waits until the bay has room for the port. After 300 s it gives up and stops the job.
2. `prepare` stops the job when the node does not answer, no device enumerates within 30 s, or the attach or
   the console fails.
   [What the pre-script does, and when it fails](twister.md#what-the-pre-script-does-and-when-it-fails) lists
   its messages.
3. The Python step cuts the map down to the ports in `PORTS`, and fails if one of them is missing or not
   connected. The map then holds only the boards this job reserved, so twister cannot pick another one.

`hwmap` writes absolute paths into the map and its scripts. Run it in the job, on the runner, as the user
that runs twister.

## What a job leaves behind

Twister leaves every board it tested powered and attached to the runner. A node serves each USB device to one
client at a time, so nobody else can attach the board until the runner detaches it. The job above detaches
the boards and releases the bays in its `trap`.

To hand the boards back by hand, detach them:

```console
$ python tools/bayctl.py detach B3
```

Do not power them off if another job may use them: `hwmap` writes a board that is off as `connected: false`.

`prepare` switches a bay in classic mode back to USB/IP. If you use a bay from its front port, keep it out of
the map ([Front port and classic mode](front-port.md)).

## Share the rack between hosts

A reservation keeps two jobs, or a job and a person, off the same board ([Reserve a bay](reserve-a-bay.md)).
Reserve whole bays, as the job above does: a reservation of one port leaves the board's USB open to other
hosts. A reservation lasts 24 h at most: run `lease` again to renew it.

One Wi-Fi channel carries 8 boards flashing at once at full speed
([How many boards may flash at once](wifi.md#how-many-boards-may-flash-at-once)). `bayctl` does not count
flashes, so limit the number of parallel jobs in your CI.

Update the nodes between jobs. A node that restarts ends its reservations and its USB/IP sessions.
