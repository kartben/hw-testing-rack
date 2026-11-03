# SPDX-License-Identifier: Apache-2.0
#
# The logic analyzer relay (src/analyzer.c) on native_sim, against gusmanb's
# analyzer emulated on Zephyr's virtual USB bus (src/cdc_emu.c): ztest.

cmake_minimum_required(VERSION 3.20.0)

set(BAY ${CMAKE_CURRENT_SOURCE_DIR}/../..)
# Same Kconfig options and devicetree bindings as the real application
set(KCONFIG_ROOT ${BAY}/Kconfig)
list(APPEND ZEPHYR_EXTRA_MODULES ${BAY}/../..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(bay_analyzer)

target_include_directories(app PRIVATE ${BAY}/src ${BAY}/../common/include
  ${ZEPHYR_BASE}/subsys/usb/host)
target_sources(app PRIVATE
  src/main.c
  src/cdc_emu.c
  ${BAY}/src/analyzer.c
  ${BAY}/../common/lib/acl.c
)
