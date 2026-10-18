# SPDX-License-Identifier: Apache-2.0
#
# The web pages' shared assets, gzipped into the image and declared as HTTP
# resources of the application's service (served as they are, with
# Content-Encoding: gzip).  The application's own linker file provides the
# service's resource section.

set(HWTR_WEB_DIR ${CMAKE_CURRENT_LIST_DIR} CACHE INTERNAL "firmware/common/web")

# hwtr_web_assets(<service>): /rack.css and /rack.mjs
function(hwtr_web_assets service)
  set(gen_dir ${ZEPHYR_BINARY_DIR}/include/generated)
  foreach(file rack.css rack.mjs)
    generate_inc_file_for_target(app ${HWTR_WEB_DIR}/${file} ${gen_dir}/${file}.gz.inc --gzip)
  endforeach()
  target_sources(app PRIVATE ${HWTR_WEB_DIR}/assets.c)
  set_source_files_properties(${HWTR_WEB_DIR}/assets.c PROPERTIES
    COMPILE_DEFINITIONS HWTR_WEB_SERVICE=${service})
endfunction()

# hwtr_web_update(<service>): GET and POST /api/update, POST /api/update/begin,
# when the application is built with MCUboot (CONFIG_HWTR_UPDATE)
function(hwtr_web_update service)
  if(CONFIG_HWTR_UPDATE)
    target_sources(app PRIVATE ${HWTR_WEB_DIR}/update_http.c)
    set_source_files_properties(${HWTR_WEB_DIR}/update_http.c PROPERTIES
      COMPILE_DEFINITIONS HWTR_WEB_SERVICE=${service})
  endif()
endfunction()

# hwtr_web_xterm(<service>): /xterm.mjs, /xterm.css, /addon-fit.mjs, /xterm-LICENSE.txt
function(hwtr_web_xterm service)
  set(gen_dir ${ZEPHYR_BINARY_DIR}/include/generated)
  foreach(file xterm.mjs xterm.css addon-fit.mjs)
    generate_inc_file_for_target(app ${HWTR_WEB_DIR}/vendor/xterm/${file}
      ${gen_dir}/${file}.gz.inc --gzip)
  endforeach()
  generate_inc_file_for_target(app ${HWTR_WEB_DIR}/vendor/xterm/LICENSE.txt
    ${gen_dir}/xterm-LICENSE.txt.gz.inc --gzip)
  target_sources(app PRIVATE ${HWTR_WEB_DIR}/xterm.c)
  set_source_files_properties(${HWTR_WEB_DIR}/xterm.c PROPERTIES
    COMPILE_DEFINITIONS HWTR_WEB_SERVICE=${service})
endfunction()
