# SPDX-License-Identifier: Apache-2.0
#
# The DATA x4's pin matrix (src/wires.c) on native_sim, with src/ports.c and
# the real expander and crosspoint drivers, against the ports test's emulated
# board and its two emulated CH446Q (tests/ports/src/emul.c): ztest.

cmake_minimum_required(VERSION 3.20.0)

set(BAY ${CMAKE_CURRENT_SOURCE_DIR}/../..)
# Same Kconfig options and devicetree bindings as the real application
set(KCONFIG_ROOT ${BAY}/Kconfig)
list(APPEND ZEPHYR_EXTRA_MODULES ${BAY}/../..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(bay_wires)

target_include_directories(app PRIVATE ${BAY}/src ${BAY}/tests/ports/src)
target_sources(app PRIVATE
  src/main.c
  ${BAY}/tests/ports/src/emul.c
  ${BAY}/src/ports.c
  ${BAY}/src/wires.c
)
