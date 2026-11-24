# Use labgrid or LAVA

`bayctl` writes one file for each framework: a labgrid environment with a power switch for each board, and a
PDUDaemon configuration that gives LAVA the same switches. You set up the consoles, the flashing and the rest.

Set up the machine first ([Set up a CI host](ci-host.md)). The examples show a checkout in `/ci/rack`, with its
virtual environment in `/ci/rack/.venv`. The options of both commands are in the
[bayctl reference](../reference/bayctl.md#export-labgrid-and-export-pdudaemon).

Both files call `python3` unless you name another Python. Name the one in your virtual environment, which has
PyYAML: activate the environment and add `--python "$(command -v python)"`, as below.

## labgrid

```console
$ python tools/bayctl.py export labgrid --python "$(command -v python)" > rack-env.yaml
```

```{code-block} yaml
:caption: rack-env.yaml, the target of B3.2
targets:
  bay-b3-2:
    resources: {}
    drivers:
      ExternalPowerDriver:
        cmd_on: /ci/rack/.venv/bin/python /ci/rack/tools/bayctl.py power B3.2 on
        cmd_off: /ci/rack/.venv/bin/python /ci/rack/tools/bayctl.py power B3.2 off
        cmd_cycle: /ci/rack/.venv/bin/python /ci/rack/tools/bayctl.py power B3.2 cycle
```

The file has one target per board, `bay-b3-2` for B3.2. Each target has an `ExternalPowerDriver` that runs
`bayctl power` on its port. You add the rest yourself:

- the board's console: its own USB serial, a local device once `bayctl attach B3.2` has run;
- the board's USB, which stays on USB/IP: attach it on the machine that runs the flashing tool;
- `BAYCTL_HUB` in the environment of the power commands, where `rack.local` does not resolve. They carry no
  `--lab`: set `BAYCTL_LAB` too if your lab file is not the checkout's `config/lab.yaml`;
- a reservation, taken before the job acquires its places ([Reserve a bay](reserve-a-bay.md));
- the coordinator, the exporter, the places and the strategy.

## LAVA, through PDUDaemon

```console
$ python tools/bayctl.py export pdudaemon --python "$(command -v python)" > pdudaemon.conf
# PDUDaemon ports: 1=A1, 2=A2, 3=A3, 4=A4, 5=B1.2, 6=B1.4, 7=B2, 8=B3.1, 9=B3.2, 10=B3.3, 11=B3.4, 12=B4
```

The command prints the second line on stderr. It gives the PDU port of each board, here for the example lab
file. Write these numbers down: the configuration file does not hold them.

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
      "cmd_on": "/ci/rack/.venv/bin/python /ci/rack/tools/bayctl.py power-port %d on",
      "cmd_off": "/ci/rack/.venv/bin/python /ci/rack/tools/bayctl.py power-port %d off"
    }
  }
}
```

The whole rack is one PDU, named `hw-testing-rack`. Its ports are the boards in rack order, numbered from 1. A
LAVA device switches its board with the usual command:

```text
pduclient --daemon <host> --hostname hw-testing-rack \
          --port <n> --command on|off|reboot
```

When you add or remove a board, every number after it shifts. Whenever boards move, run the export again and
correct the port of each LAVA device.

Run PDUDaemon on the machine with the checkout. Set `BAYCTL_HUB` in its environment if `rack.local` does not
resolve there. PDUDaemon covers power only: you write the device dictionaries, the consoles, the
`usbip attach` and the health checks.
