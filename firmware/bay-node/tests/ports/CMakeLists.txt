# SPDX-License-Identifier: Apache-2.0
#
# The node's DATA x4 ports (src/ports.c) on native_sim, against an emulated
# board on the emulated I2C bus (src/emul.c): ztest.

cmake_minimum_required(VERSION 3.20.0)

set(BAY ${CMAKE_CURRENT_SOURCE_DIR}/../..)
# Same Kconfig options and devicetree bindings as the real application
set(KCONFIG_ROOT ${BAY}/Kconfig)
list(APPEND ZEPHYR_EXTRA_MODULES ${BAY}/../..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(bay_ports)

target_include_directories(app PRIVATE ${BAY}/src)
target_sources(app PRIVATE
  src/main.c
  src/emul.c
  ${BAY}/src/ports.c
)
