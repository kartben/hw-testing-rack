# BabbleSim: the rack's Wi-Fi against BLE between two DUTs

The simulation behind [docs/wifi-coexistence.md](../../docs/wifi-coexistence.md).
It's a model: use it to compare settings with each other, not to predict the
field.

- `app/`: the two DUTs, built for `nrf52_bsim` with Zephyr's own Bluetooth host
  and controller: a central and a peripheral in a connection with a steady
  flow of notifications, or a discovery loop (scan, connect, disconnect).
- `sweep.py`: starts each scenario on BabbleSim's 2.4 GHz phy, with the
  `multiatt` channel (one attenuation per path, from the rack's geometry) and
  the `BLE_simple` modem.  The rack's Wi-Fi is one `WLAN_actmod` (the BSS:
  the AP, the hub and the nodes as its ports) plus the AP's beacons.  It
  writes one CSV row per scenario.
- `summarize.py`: the doc's tables, from the CSVs.
- `results/`: the CSVs and logs of the last sweep.

BabbleSim needs an x86-64 Linux host.  On any machine with Docker:

```bash
docker volume create bsim-coex-ws
docker run -d --name bsim-coex --entrypoint sleep -v bsim-coex-ws:/ws -v "$PWD:/coex" ghcr.io/zephyrproject-rtos/zephyr-build:v0.29.4 infinity
docker exec -u root bsim-coex bash /coex/setup.sh 3f7ae83e0e7c2f535d89febabf29e11c721fb66d
docker exec -u root bsim-coex bash -c "cd /ws && python3 /coex/sweep.py all --jobs 12 --out /coex/results/all.csv"
python3 summarize.py results/all.csv
```

The commands run from this directory.  `setup.sh` takes the Zephyr revision
from `firmware/west.yml`; a run of `all` (197 scenarios of 60 s simulated)
takes about an hour on 32 threads.
