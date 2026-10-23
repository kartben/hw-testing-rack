# SPDX-License-Identifier: Apache-2.0
#
# DNS-SD (lib/dnssd.c) on native_sim: the records handed to the mDNS
# responder, checked with Zephyr's own validity rules; a change only when
# something changed; the refresh following the application's description.

cmake_minimum_required(VERSION 3.20.0)

list(APPEND ZEPHYR_EXTRA_MODULES ${CMAKE_CURRENT_SOURCE_DIR}/../../../..)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(dnssd)

# dns_sd_rec_is_valid(): what the responder applies to every record
target_include_directories(app PRIVATE ${ZEPHYR_BASE}/subsys/net/lib/dns)
target_sources(app PRIVATE src/main.c)
