# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

# The repository is a Zephyr module (zephyr/module.yml): the boards, the bindings
# and the code shared with the power hub (firmware/common), so this builds
# from any Zephyr workspace.
list(APPEND ZEPHYR_EXTRA_MODULES ${CMAKE_CURRENT_SOURCE_DIR}/../..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(bay_node)

target_sources(app PRIVATE
  src/main.c
  src/fault.c
  src/dut.c
  src/ports.c
  src/usb_mux.c
  src/usb_host.c
  src/status_led.c
  src/aux_console.c
  src/rfc2217.c
  src/net.c
  src/shell.c
  src/web.c
  src/access.c
  src/boards.c
  src/rack.c
)
target_sources_ifdef(CONFIG_BAY_CAMERA app PRIVATE src/camera.c)
target_sources_ifdef(CONFIG_BAY_DISPLAY app PRIVATE src/display.c)
# The USB devices' strings: read with the host's own control requests
target_sources_ifdef(CONFIG_USBIP app PRIVATE src/usb_info.c)
if(CONFIG_USBIP)
  target_include_directories(app PRIVATE ${ZEPHYR_BASE}/subsys/usb/host)
endif()

# Status page, the shared /rack.css and /rack.mjs, the vendored xterm.js:
# gzipped into the image (served as-is with Content-Encoding: gzip)
set(gen_dir ${ZEPHYR_BINARY_DIR}/include/generated)
generate_inc_file_for_target(app web/index.html ${gen_dir}/index.html.gz.inc --gzip)
set(BAY ${CMAKE_CURRENT_SOURCE_DIR})
# The board targets the page suggests per USB device: a table built from
# mechanical/boards/boards.yaml, gzipped like the page (/board-targets.json)
set(boards_yaml ${BAY}/../../mechanical/boards/boards.yaml)
add_custom_command(
  OUTPUT ${gen_dir}/board-targets.json
  COMMAND ${PYTHON_EXECUTABLE} ${BAY}/web/board_targets.py ${boards_yaml} ${gen_dir}/board-targets.json
  DEPENDS ${BAY}/web/board_targets.py ${boards_yaml}
)
generate_inc_file_for_target(app ${gen_dir}/board-targets.json ${gen_dir}/board-targets.json.gz.inc
  --gzip)
hwtr_web_assets(bay_http)
hwtr_web_xterm(bay_http)
# Firmware updates (when built with MCUboot): /api/update, /api/update/begin
hwtr_web_update(bay_http)

# HTTP resources of the bay_http service live in their own iterable section
zephyr_linker_sources(SECTIONS web/sections-rom.ld)
