# SPDX-License-Identifier: Apache-2.0
#
# The hub's power budget (src/budget.c) on native_sim, with made-up
# contracts and row currents: ztest.

cmake_minimum_required(VERSION 3.20.0)

set(HUB ${CMAKE_CURRENT_SOURCE_DIR}/../..)
# Same Kconfig options as the real application (CONFIG_HUB_*)
set(KCONFIG_ROOT ${HUB}/Kconfig)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(hub_budget)

target_include_directories(app PRIVATE ${HUB}/src)
target_sources(app PRIVATE
  src/main.c
  ${HUB}/src/budget.c
)
