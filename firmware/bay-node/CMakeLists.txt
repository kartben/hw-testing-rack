# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

# firmware/ is a Zephyr module (zephyr/module.yml): the boards, the bindings
# and the code shared with the power hub (firmware/common), so this builds
# from any Zephyr workspace.
list(APPEND ZEPHYR_EXTRA_MODULES ${CMAKE_CURRENT_SOURCE_DIR}/..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(bay_node)

target_sources(app PRIVATE
  src/main.c
  src/dut.c
  src/usb_mux.c
  src/usb_host.c
  src/status_led.c
  src/aux_console.c
  src/rfc2217.c
  src/net.c
  src/shell.c
  src/web.c
  src/acl.c
  src/access.c
  src/rack.c
)

# Status page, the shared /rack.css and /rack.mjs, the vendored xterm.js:
# gzipped into the image (served as-is with Content-Encoding: gzip)
set(gen_dir ${ZEPHYR_BINARY_DIR}/include/generated)
generate_inc_file_for_target(app web/index.html ${gen_dir}/index.html.gz.inc --gzip)
hwtr_web_assets(bay_http)
hwtr_web_xterm(bay_http)

# HTTP resources of the bay_http service live in their own iterable section
zephyr_linker_sources(SECTIONS web/sections-rom.ld)
