# SPDX-License-Identifier: Apache-2.0

zephyr_include_directories(include)

# CH224A USB PD sink, as a regulator (out of tree)
add_subdirectory_ifdef(CONFIG_REGULATOR_CH224A drivers/regulator)

# Rack bus protocol (docs/rack-protocol.md): frames, hub and node state
# machines; Wi-Fi station and hostname; access rules, the admin key;
# firmware updates (MCUboot); the JPEG end finder (bay camera)
if(CONFIG_HWTR_RACK_PROTO OR CONFIG_HWTR_NET OR CONFIG_HWTR_ACL OR CONFIG_HWTR_IMG OR
   CONFIG_HWTR_JPEG)
  zephyr_library_named(hwtr)
  zephyr_library_sources_ifdef(CONFIG_HWTR_RACK_PROTO lib/rack_proto.c)
  zephyr_library_sources_ifdef(CONFIG_HWTR_RACK_HUB lib/rack_hub.c)
  zephyr_library_sources_ifdef(CONFIG_HWTR_RACK_NODE lib/rack_node.c)
  zephyr_library_sources_ifdef(CONFIG_HWTR_NET lib/net.c)
  zephyr_library_sources_ifdef(CONFIG_HWTR_ACL lib/acl.c)
  zephyr_library_sources_ifdef(CONFIG_HWTR_ADMIN lib/admin.c)
  zephyr_library_sources_ifdef(CONFIG_HWTR_IMG lib/mcuboot_img.c)
  zephyr_library_sources_ifdef(CONFIG_HWTR_UPDATE lib/update.c)
  zephyr_library_sources_ifdef(CONFIG_HWTR_JPEG lib/jpeg.c)
endif()

# The web pages' shared assets, gzipped into the image: hwtr_web_assets(<service>)
include(${CMAKE_CURRENT_LIST_DIR}/web/web.cmake)
