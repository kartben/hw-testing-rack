# SPDX-License-Identifier: Apache-2.0
#
# Node v1.0's DATA lead (src/dut.c with src/ports.c) on native_sim: the
# eFuse's power-on rule against the emulated DATA x4 of the ports test,
# powered by the eFuse's enable.  ztest.

cmake_minimum_required(VERSION 3.20.0)

set(BAY ${CMAKE_CURRENT_SOURCE_DIR}/../..)
# Same Kconfig options and devicetree bindings as the real application
set(KCONFIG_ROOT ${BAY}/Kconfig)
list(APPEND ZEPHYR_EXTRA_MODULES ${BAY}/../..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(bay_data_lead)

target_include_directories(app PRIVATE ${BAY}/src ${BAY}/tests/ports/src)
target_sources(app PRIVATE
  src/main.c
  ${BAY}/tests/ports/src/emul.c
  ${BAY}/src/dut.c
  ${BAY}/src/ports.c
)
