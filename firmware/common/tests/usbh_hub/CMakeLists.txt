# Zephyr's USB host hub class with the rack's patches (zephyr/patches.yml) on
# native_sim, against a made-up hub: src/main.c includes usbh_hub.c and fakes
# the class requests, the controller and the devices behind the hub.
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(usbh_hub)

target_sources(app PRIVATE src/main.c)
target_include_directories(app PRIVATE
  ${ZEPHYR_BASE}/subsys/usb/host
  ${ZEPHYR_BASE}/subsys/usb/host/class
)
