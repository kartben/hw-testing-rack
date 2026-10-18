# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

# The repository is a Zephyr module (zephyr/module.yml): the power_hub board, the
# bindings, the AP33772S drivers and the code shared with the bay nodes.
list(APPEND ZEPHYR_EXTRA_MODULES ${CMAKE_CURRENT_SOURCE_DIR}/../..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(power_hub)

target_sources(app PRIVATE
  src/main.c
  src/pd.c
  src/rows.c
  src/bus.c
  src/events.c
  src/web.c
  src/shell.c
)

# Status page and the shared /rack.css, /rack.mjs, gzipped into the image
set(gen_dir ${ZEPHYR_BINARY_DIR}/include/generated)
generate_inc_file_for_target(app web/index.html ${gen_dir}/index.html.gz.inc --gzip)
hwtr_web_assets(hub_http)
# Firmware updates (when built with MCUboot): /api/update, /api/update/begin
hwtr_web_update(hub_http)

# HTTP resources of the hub_http service live in their own iterable section
zephyr_linker_sources(SECTIONS web/sections-rom.ld)
