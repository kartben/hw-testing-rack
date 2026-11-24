# labgrid and LAVA

`bayctl` writes one file for each framework and stops there: a labgrid environment that holds each board's
power switch, and a PDUDaemon configuration that gives LAVA the same switch. The consoles, the flashing and
the rest of either set-up are left to you.

:::{status} written
`bayctl`'s tests check the shape of the two files. Neither file has been given to labgrid or to PDUDaemon,
and no labgrid or LAVA set-up exists for the rack. See [What exists today](../plan/status.md#status-labgrid).
:::

Needs: a machine set up as on [Set up bayctl and usbip](set-up-your-machine.md), and for a runner
[Set up a CI host](ci-host.md), which also says what a job leaves attached and powered. The paths in the
examples are those of a checkout in `/ci/rack`; every option of the two exports is on
[bayctl](../reference/bayctl.md#export-labgrid-and-export-pdudaemon).

## labgrid

```console
$ python tools/bayctl.py export labgrid > rack-env.yaml
```

```{code-block} yaml
:caption: rack-env.yaml, the target of B3.2
targets:
  bay-b3-2:
    resources: {}
    drivers:
      ExternalPowerDriver:
        cmd_on: python3 /ci/rack/tools/bayctl.py power B3.2 on
        cmd_off: python3 /ci/rack/tools/bayctl.py power B3.2 off
        cmd_cycle: python3 /ci/rack/tools/bayctl.py power B3.2 cycle
```

One target per board the rack reports, `bay-b3-2` for B3.2: the analyzer's port and the boards kept out of
twister's map are in, the empty ports of a DATA board are not. Each target has an
`ExternalPowerDriver` whose three commands are `bayctl power` on that port
([Power-cycle or reset a board](power-and-reset.md)).

A port of a DATA board gets no serial resource, hence `resources: {}`, and on a v1.0 rack that is every
target. Only a node with one board, a stand-in or the simulator, gets its AUX UART as a
`NetworkSerialPort` with a `SerialDriver`: RFC 2217 on port 4001, where labgrid sets the baud rate
([Serial console](serial-console.md)).

Left to you:

- the console of a board on a DATA port: the board's own USB serial, a local device once
  `bayctl attach B3.2` has run on the machine that needs it. The export writes no resource for it;
- USB as a whole. No USB resource is generated: the board's USB device stays with USB/IP, attached on
  the machine that runs the flashing tool;
- the environment of the power commands. They carry no `--lab`, so they read `config/lab.yaml` of the
  checkout, or `BAYCTL_LAB`, and they need `BAYCTL_HUB` wherever `rack.local` does not resolve. `--python`
  changes their `python3`; the path of `bayctl` is the absolute path of the checkout that made the file;
- a reservation, taken in the job before it acquires the places ([Reserve a bay](reserve-a-bay.md));
- the coordinator, the exporter, the places, the flashing and the strategy. The sources hold nothing
  about them.

## LAVA, through PDUDaemon

```console
$ python tools/bayctl.py export pdudaemon > pdudaemon.conf
# PDUDaemon ports: 1=A1, 2=A2, 3=A3, 4=A4, 5=B1.2, 6=B1.4, 7=B2, 8=B3.1, 9=B3.2, 10=B3.3, 11=B3.4, 12=B4
```

The second line is what the command prints on stderr for the example lab file; it is not in the file.

```{code-block} json
:caption: pdudaemon.conf
{
  "daemon": {
    "hostname": "0.0.0.0",
    "port": 16421,
    "listener": "http",
    "logging_level": "INFO"
  },
  "pdus": {
    "hw-testing-rack": {
      "driver": "localcmdline",
      "cmd_on": "python3 /ci/rack/tools/bayctl.py power-port %d on",
      "cmd_off": "python3 /ci/rack/tools/bayctl.py power-port %d off"
    }
  }
}
```

The rack is one PDU with PDUDaemon's `localcmdline` driver, still named `hw-testing-rack` in the export.
Its ports are the boards in rack order, numbered from 1: every board present counts, the analyzer and the
boards out of twister's map included, and the empty ports of a DATA board do not. A LAVA device then uses
the usual command:

```text
pduclient --daemon <host> --hostname hw-testing-rack \
          --port <n> --command on|off|reboot
```

The numbering is written nowhere but on that stderr line. `bayctl power-port <n>` works it out again from
the rack at every call, so a board added or taken away shifts every number after it. When boards move,
run the export again, read the new line and correct the port of each LAVA device.

The export configures on and off only; `bayctl power-port <n> cycle` exists and the file does not use it.
PDUDaemon must run where the checkout is, with `BAYCTL_HUB` in its environment if `rack.local` does not
resolve there.

PDUDaemon covers power and nothing else. A LAVA device dictionary, the command that connects to a board's
console, the place where `usbip attach` runs and the health checks do not exist in the sources.
