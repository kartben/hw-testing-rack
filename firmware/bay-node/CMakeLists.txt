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
  src/aux_console.c
  src/rfc2217.c
  src/net.c
  src/shell.c
  src/web.c
)

# Status page and the vendored xterm.js, gzipped into the image (served as-is
# with Content-Encoding: gzip)
set(gen_dir ${ZEPHYR_BINARY_DIR}/include/generated)
generate_inc_file_for_target(app web/index.html ${gen_dir}/index.html.gz.inc --gzip)
foreach(file xterm.mjs xterm.css addon-fit.mjs)
  generate_inc_file_for_target(app web/vendor/xterm/${file} ${gen_dir}/${file}.gz.inc --gzip)
endforeach()
generate_inc_file_for_target(app web/vendor/xterm/LICENSE.txt
  ${gen_dir}/xterm-LICENSE.txt.gz.inc --gzip)

# HTTP resources of the bay_http service live in their own iterable section
zephyr_linker_sources(SECTIONS web/sections-rom.ld)
