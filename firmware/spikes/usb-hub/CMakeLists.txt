# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

# The repository's Zephyr module: the Wi-Fi station of firmware/common
list(APPEND ZEPHYR_EXTRA_MODULES ${CMAKE_CURRENT_SOURCE_DIR}/../../..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(usb_hub_spike)

target_sources(app PRIVATE src/main.c)
# The hub requests (port power, port status) are the host stack's own, not public API
target_include_directories(app PRIVATE ${ZEPHYR_BASE}/subsys/usb/host)
