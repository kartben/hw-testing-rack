#!/usr/bin/env bash
# Build rack-wifi.cc into an ns-3.49 tree and run one sweep of sweep.py (docs/wifi-capacity-ns3.md).
#
#   NS3_DIR=~/ns-3.49 bash tools/ns3-wifi-capacity/run.sh ci_n 10     # sweep, parallel jobs
#
# Writes results/<sweep>.csv (one line per run, the header first).  The ns-3 tree needs the
# modules wifi, applications, internet, internet-apps, mobility, point-to-point, propagation.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
ns3=${NS3_DIR:?set NS3_DIR to an ns-3.49 tree}
sweep=${1:-ci_n}
jobs=${2:-8}

cp "$here/rack-wifi.cc" "$ns3/scratch/rack-wifi.cc"
(
    cd "$ns3"
    if [ ! -d cmake-cache ] || ! grep -q "internet-apps" cmake-cache/CMakeCache.txt; then
        ./ns3 configure -G Ninja --build-profile=optimized --disable-examples --disable-tests \
            --disable-python \
            --enable-modules=wifi,applications,internet,internet-apps,mobility,point-to-point,propagation,flow-monitor
    fi
    ./ns3 build rack-wifi
)
bin=$(ls "$ns3"/build/scratch/ns3.*-rack-wifi-* | head -1)

mkdir -p "$here/results"
names=$sweep
[ "$sweep" = all ] && names=$(python3 "$here/sweep.py" --list)
for s in $names; do
    out="$here/results/$s.csv"
    "$bin" --header > "$out"
    # a run that ns-3 aborts (the spectrum PHY's intermittent "Invalid WifiPhy state RX") leaves
    # no line, and the others go on
    python3 "$here/sweep.py" "$s" | xargs -P "$jobs" -L 1 sh -c '"$0" "$@" || true' "$bin" >> "$out"
    echo "$(($(wc -l < "$out") - 1)) runs in $out"
done
