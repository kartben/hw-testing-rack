# SPDX-License-Identifier: Apache-2.0
#
# The DATA x4 co-processor's image (src/coproc.c) on native_sim: the upload
# into the coproc partition, on the flash simulator: ztest.

cmake_minimum_required(VERSION 3.20.0)

set(BAY ${CMAKE_CURRENT_SOURCE_DIR}/../..)
# Same Kconfig options and devicetree bindings as the real application
set(KCONFIG_ROOT ${BAY}/Kconfig)
list(APPEND ZEPHYR_EXTRA_MODULES ${BAY}/../..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(bay_coproc)

target_include_directories(app PRIVATE ${BAY}/src ${BAY}/../common/include)
target_sources(app PRIVATE
  src/main.c
  ${BAY}/src/coproc.c
  ${BAY}/../common/lib/acl.c
)
