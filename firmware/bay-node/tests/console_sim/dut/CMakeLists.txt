# SPDX-License-Identifier: Apache-2.0
#
# The fake DUT of the console simulation: Zephyr's shell sample
# (samples/subsys/shell/shell_module), with its boot banner on so that a
# RESET from the console page shows.

cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(fake_dut)

set(SAMPLE ${ZEPHYR_BASE}/samples/subsys/shell/shell_module)
target_sources(app PRIVATE ${SAMPLE}/src/main.c ${SAMPLE}/src/test_module.c)
target_sources_ifdef(CONFIG_SHELL_DYNAMIC_CMDS app PRIVATE ${SAMPLE}/src/dynamic_cmd.c)
target_sources_ifdef(CONFIG_SHELL_BACKEND_SERIAL app PRIVATE ${SAMPLE}/src/uart_reinit.c)
