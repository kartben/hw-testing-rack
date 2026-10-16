# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

# The bay node board and its devicetree bindings live in firmware/, next to
# this application, so it builds from any Zephyr workspace.
list(APPEND BOARD_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/..)
list(APPEND DTS_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(bay_node)

target_sources(app PRIVATE
  src/main.c
  src/dut.c
  src/usb_mux.c
  src/usb_host.c
  src/status_led.c
  src/aux_bridge.c
  src/net.c
  src/shell.c
)
