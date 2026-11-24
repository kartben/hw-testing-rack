# SPDX-License-Identifier: Apache-2.0
#
# Sysbuild part shared by the bay node and the power hub (each application's
# sysbuild.cmake includes it): MCUboot in front of the application, the
# image id that an update over the network must carry, and a loud warning
# when the image is signed with MCUboot's public test key.
#
# The image id is "<application>/<board>" (bay-node/bay_node,
# power-hub/power_hub): imgtool writes it into the signed image as a
# protected TLV (0xa0, covered by the signature), and the firmware refuses
# an update whose id is not its own (firmware/common/lib/update.c).

if(NOT SB_CONFIG_BOOTLOADER_MCUBOOT)
  return()
endif()

set(hwtr_image_id "${DEFAULT_IMAGE}/${BOARD}")
set_config_string(${DEFAULT_IMAGE} CONFIG_HWTR_UPDATE_ID "${hwtr_image_id}")
set_config_string(${DEFAULT_IMAGE} CONFIG_MCUBOOT_EXTRA_IMGTOOL_ARGS
  "--custom-tlv 0xa0 ${hwtr_image_id}")

# The signing key: HWTR_SIGNING_KEY (firmware/common/Kconfig.sysbuild),
# or -DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE=...; MCUboot's own root-*.pem
# otherwise, which anyone can sign with
get_filename_component(hwtr_key_dir "${SB_CONFIG_BOOT_SIGNATURE_KEY_FILE}" DIRECTORY)
file(REAL_PATH "${hwtr_key_dir}" hwtr_key_dir)
file(REAL_PATH "${ZEPHYR_MCUBOOT_MODULE_DIR}" hwtr_mcuboot_dir)
if(hwtr_key_dir STREQUAL hwtr_mcuboot_dir)
  message(WARNING "${DEFAULT_IMAGE}: signed with MCUboot's public test key "
    "(${SB_CONFIG_BOOT_SIGNATURE_KEY_FILE}): any image signed with it boots.  "
    "Fine on a desk; for a rack set HWTR_SIGNING_KEY to your own key "
    "(docs/firmware.md, Signing key) and build pristine.")
  set_config_bool(${DEFAULT_IMAGE} CONFIG_HWTR_UPDATE_TEST_KEY y)
else()
  set_config_bool(${DEFAULT_IMAGE} CONFIG_HWTR_UPDATE_TEST_KEY n)
endif()
