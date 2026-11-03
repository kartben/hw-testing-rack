# SPDX-License-Identifier: Apache-2.0
#
# The DATA x4 co-processor's image (src/coproc.c) on native_sim: the upload
# into the coproc partition on the flash simulator, and its load into an
# RP2350 bootloader emulated on Zephyr's virtual USB bus (src/picoboot_emu.c):
# ztest.

cmake_minimum_required(VERSION 3.20.0)

set(BAY ${CMAKE_CURRENT_SOURCE_DIR}/../..)
# Same Kconfig options and devicetree bindings as the real application
set(KCONFIG_ROOT ${BAY}/Kconfig)
list(APPEND ZEPHYR_EXTRA_MODULES ${BAY}/../..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(bay_coproc)

target_include_directories(app PRIVATE ${BAY}/src ${BAY}/../common/include
  ${ZEPHYR_BASE}/subsys/usb/host)
target_sources(app PRIVATE
  src/main.c
  src/picoboot_emu.c
  ${BAY}/src/coproc.c
  ${BAY}/../common/lib/acl.c
)
# A stalled load gives up after 1 s; back in the bootloader within 0.5 s: not started
target_compile_definitions(app PRIVATE COPROC_LOAD_TIMEOUT_MS=1000 COPROC_SETTLE_MS=500)
