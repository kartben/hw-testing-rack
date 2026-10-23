# SPDX-License-Identifier: Apache-2.0
#
# The CH446Q MUX driver (drivers/mux/mux_wch_ch446q.c) on native_sim: two
# chips on one emulated 8-pin expander (gpio_emul), as on the DATA x4 v2,
# and one on lines spread over two ports; each chip is emulated from the
# lines it sees.

cmake_minimum_required(VERSION 3.20.0)

list(APPEND ZEPHYR_EXTRA_MODULES ${CMAKE_CURRENT_SOURCE_DIR}/../../../..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(ch446q)

target_sources(app PRIVATE src/main.c)
