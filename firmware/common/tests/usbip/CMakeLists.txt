# Zephyr's USB/IP service with the rack's patches (zephyr/patches.yml) on
# native_sim: the virtual USB bus, a device on it with a loopback function, a
# serial converter and a mass-storage-like function, that the shell unplugs
# and plugs again.  The client is test_usbip.py.
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(usbip_sim)

include(${ZEPHYR_BASE}/samples/subsys/usb/common/common.cmake)

target_sources(app PRIVATE src/main.c src/serial_emu.c src/storage_emu.c)
