#!/bin/bash
# The 3D viewer's LVGL screen: LVGL's music and widgets demos for wasm32, freestanding (no libc, no
# emscripten), rendered by LVGL's software renderer into one XRGB8888 frame buffer (main.c), which
# site/screen.js copies into a texture.  Output: site/assets/lvgl/lvgl-demo.wasm (MIT, like LVGL).
#
# Runs in the Zephyr build image (clang + wasm-ld), with LVGL from a Zephyr workspace mounted read-only:
#
#   docker run --rm --entrypoint bash \
#     -v <zephyr workspace>/modules/lib/gui/lvgl:/lvgl:ro -v <repo>/tools/lvgl_wasm:/work -v <repo>/site/assets/lvgl:/out \
#     ghcr.io/zephyrproject-rtos/zephyr-build:v0.29.4 /work/build.sh
#
# Built 2026-10-18 from LVGL d1fe35d (Zephyr main's lvgl module).
set -e
cd /work
OBJ=$(mktemp -d)
CFLAGS="--target=wasm32 -O2 -ffreestanding -nostdlib -fvisibility=hidden -DLV_CONF_INCLUDE_SIMPLE -I/work -I/work/stubs -I/lvgl -I/lvgl/src -w"
SRCS=$(find /lvgl/src /lvgl/demos/music /lvgl/demos/widgets -name '*.c'; echo /lvgl/demos/lv_demos.c; echo /work/main.c)
echo "$SRCS" | xargs -P "$(nproc)" -I{} sh -c 'clang-20 '"$CFLAGS"' -c "{}" -o "'"$OBJ"'/$(echo "{}" | tr / _).o"'
wasm-ld --no-entry --export-dynamic --gc-sections --strip-all -z stack-size=262144 --initial-memory=16777216 \
  "$OBJ"/*.o -o /out/lvgl-demo.wasm
ls -l /out/lvgl-demo.wasm
