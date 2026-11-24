# Using the rack from CI

This document was split into the pages of the documentation site.

- The table of what a bay offers a CI job, and a whole job: [use/ci-host.md](use/ci-host.md).
- Where the data comes from: [reference/bayctl.md › Where the data comes from](reference/bayctl.md#where-the-data-comes-from), with the lab file's keys on [reference/lab-yaml.md](reference/lab-yaml.md).
- CI host setup (Linux): [use/set-up-your-machine.md](use/set-up-your-machine.md) for any machine, [use/ci-host.md](use/ci-host.md) for what a runner adds, [use/board-targets.md](use/board-targets.md) for the targets.
- Backups, export and import: [use/board-targets.md › Back up and restore with bayctl](use/board-targets.md#back-up-and-restore-with-bayctl).
- Zephyr twister: [use/twister.md](use/twister.md).
- labgrid, LAVA (PDUDaemon): [use/labgrid-and-lava.md](use/labgrid-and-lava.md).
- Limits: [reference/known-limitations.md](reference/known-limitations.md), and [use/usb-and-flashing.md](use/usb-and-flashing.md) for the probes that pass.

## Access control

Now on [use/access.md](use/access.md); reservations on [use/reserve-a-bay.md](use/reserve-a-bay.md).

## By hand

Now on [use/power-and-reset.md](use/power-and-reset.md); a power-on that waits for room in the budget (`--when available`, `--wait`, `cancel`) on [use/power-budget.md](use/power-budget.md).
