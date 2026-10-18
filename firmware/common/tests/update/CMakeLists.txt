# SPDX-License-Identifier: Apache-2.0
#
# Firmware updates on native_sim: the image parser fed chunk by chunk, and the
# update code (upload into slot 1, test boot request, trial, confirmation,
# rollback) against the flash simulator's MCUboot partitions.  No MCUboot
# runs here: the test checks what the application leaves for it.

cmake_minimum_required(VERSION 3.20.0)

list(APPEND ZEPHYR_EXTRA_MODULES ${CMAKE_CURRENT_SOURCE_DIR}/../../../..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(update)

target_sources(app PRIVATE src/main.c)
