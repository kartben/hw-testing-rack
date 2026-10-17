# SPDX-License-Identifier: Apache-2.0
#
# The bay node's serial console, web server, RFC 2217 and access-control code
# on native_sim, with the hardware stubbed (src/sim.c): run.py wires its AUX
# UART (a PTY) to a second native_sim running a Zephyr shell, the "DUT".  Used
# to record the console screencast (web/screencast.py) and by test_access.py,
# without a board.  The node's "bay" shell is on its console (stdin/stdout).

cmake_minimum_required(VERSION 3.20.0)

set(BAY ${CMAKE_CURRENT_SOURCE_DIR}/../..)
# Same Kconfig options and devicetree bindings as the real application
set(KCONFIG_ROOT ${BAY}/Kconfig)
list(APPEND DTS_ROOT ${BAY}/..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(bay_console_sim)

target_include_directories(app PRIVATE ${BAY}/src)
target_sources(app PRIVATE
  src/sim.c
  ${BAY}/src/aux_console.c
  ${BAY}/src/rfc2217.c
  ${BAY}/src/web.c
  ${BAY}/src/acl.c
  ${BAY}/src/access.c
  ${BAY}/src/shell.c
)

set(gen_dir ${ZEPHYR_BINARY_DIR}/include/generated)
generate_inc_file_for_target(app ${BAY}/web/index.html ${gen_dir}/index.html.gz.inc --gzip)
foreach(file xterm.mjs xterm.css addon-fit.mjs)
  generate_inc_file_for_target(app ${BAY}/web/vendor/xterm/${file} ${gen_dir}/${file}.gz.inc --gzip)
endforeach()
generate_inc_file_for_target(app ${BAY}/web/vendor/xterm/LICENSE.txt
  ${gen_dir}/xterm-LICENSE.txt.gz.inc --gzip)

zephyr_linker_sources(SECTIONS ${BAY}/web/sections-rom.ld)
