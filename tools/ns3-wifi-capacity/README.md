# ns-3 model of one rack's Wi-Fi

The study and its results: [docs/wifi-capacity-ns3.md](../../docs/wifi-capacity-ns3.md).

| File | |
|---|---|
| `rack-wifi.cc` | the scenario: the rack's BSS, the lab PC behind the AP, the traffic, the metrics; one run prints one CSV line (`--header` for the columns, `--debug=1` for per-bay details on stderr) |
| `sweep.py` | the sweeps, one line of arguments per run (`python3 sweep.py --list`) |
| `run.sh` | builds the scenario into an ns-3 tree and runs a sweep in parallel into `results/<sweep>.csv` |
| `summarize.py` | means over seeds into `results/summary.md` and `results/summary.json` |
| `results/` | the CSVs of the study's runs |

ns-3.49 with the modules wifi, applications, internet, internet-apps, mobility, point-to-point and
propagation.  CMake and Ninja can come from a Python venv (`pip install cmake ninja`):

```bash
git clone --depth 1 --branch ns-3.49 https://gitlab.com/nsnam/ns-3-dev.git ns-3.49
NS3_DIR=$PWD/ns-3.49 bash tools/ns3-wifi-capacity/run.sh all 10
python3 tools/ns3-wifi-capacity/summarize.py
```

`run.sh` configures the tree itself (optimized, those modules only) the first time.  The whole study
is 803 runs; 10–11 parallel jobs on a 12-core Mac take about 13 minutes per 200–400 runs.

One run by hand:

```bash
ns-3.49/build/scratch/ns3.49-rack-wifi-optimized --scenario=ci --active=8 --cams=2 --txPower=11 --apDist=2 --seed=1
```

Scenarios: `idle` (background only), `ci` (`--active` nodes in USB/IP, `--cams` camera streams),
`harsh` (`ci` plus DUT Wi-Fi on the same channel and a neighbouring BSS; `--rackChannel`, `--dutChannel`
and `--neighbourChannel` move them apart, on the spectrum PHY; `--nearLoss` and `--dutCm` give the
near-field pass).  `--standard=ax` makes the rack BSS 802.11ax HE20, `--standard=axmu` adds DL and UL
OFDMA (ns-3's round-robin MU scheduler, spectrum PHY), `--heMcs` fixes the HE MCS.  The other options
are in `--help`.
