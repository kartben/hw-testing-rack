#!/bin/bash
# Inside ghcr.io/zephyrproject-rtos/zephyr-build (x86-64, BabbleSim needs it),
# with /ws a fresh volume and this directory at /coex:
#   - a west workspace on Zephyr at the rack's revision (firmware/west.yml),
#     with what nrf52_bsim needs (hal_nordic, nrf_hw_models) and BabbleSim
#     (the manifest's "babblesim" group);
#   - BabbleSim built (phy, channels, modems, the WLAN activity model);
#   - the DUT app built for nrf52_bsim, copied next to the phy.
# usage: setup.sh <zephyr revision>
set -e
REV=${1:?zephyr revision}
git config --global --add safe.directory "*"
cd /ws
if [ ! -d zephyr/.git ]; then
	git init -q zephyr
	git -C zephyr fetch -q --depth 1 https://github.com/zephyrproject-rtos/zephyr.git "$REV"
	git -C zephyr checkout -q FETCH_HEAD
	west init -l zephyr > /dev/null
	west config manifest.group-filter -- +babblesim
fi
west update --narrow -o=--depth=1 hal_nordic nrf_hw_models cmsis_6 $(west list -f '{name}' | grep '^babblesim') > /ws/update.log 2>&1

export BSIM_OUT_PATH=/ws/tools/bsim BSIM_COMPONENTS_PATH=/ws/tools/bsim/components
# BabbleSim's own manifest copies its top Makefile to the root; Zephyr's does not
cp "$BSIM_COMPONENTS_PATH/common/Makefile" "$BSIM_OUT_PATH/Makefile"
make -C "$BSIM_OUT_PATH" everything -j"$(nproc)" > /ws/bsim-build.log 2>&1

west build -p always -b nrf52_bsim /coex/app -d /ws/build/coex > /ws/app-build.log 2>&1
cp /ws/build/coex/zephyr/zephyr.exe "$BSIM_OUT_PATH/bin/bs_coex_dut"
ls "$BSIM_OUT_PATH/bin"
