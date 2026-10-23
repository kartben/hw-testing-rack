/*
 * Wi-Fi station and hostname bay-<id>.local: firmware/common's hwtr_net
 * (shared with the power hub), plus the bay id in the settings, and the
 * services DNS-SD advertises under that name.
 *
 * Credentials come from the Wi-Fi credentials library: stored with
 * "wifi cred add" (settings) or built in with CONFIG_WIFI_CREDENTIALS_STATIC
 * (see wifi.conf.example).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>

#include <zephyr/app_version.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <hwtr/dnssd.h>
#include <hwtr/net.h>

#include "bay.h"

LOG_MODULE_REGISTER(bay_net, CONFIG_BAY_LOG_LEVEL);

BUILD_ASSERT(BAY_ID_MAX_LEN == HWTR_ID_MAX_LEN);

static void on_addr(const char *addr)
{
	LOG_INF("usbip attach -r %s -b 1-1", addr);
	bay_rack_info_changed();
}

#if defined(CONFIG_HWTR_DNSSD)
/*
 * What listens right now: the page, USB/IP while the DUT (or the DATA x4's
 * hub) is on the S3's USB, RFC 2217 while its listener is open.  TXT: the
 * bay's id, its rack position, the firmware, the data path and, with a
 * DATA x4, its slots.
 */
static void dnssd_fill(struct hwtr_dnssd_desc *d)
{
	enum bay_data_path path = usb_mux_path();
	char slots[4];

	hwtr_dnssd_service(d, "_http", CONFIG_BAY_HTTP_PORT);
#if defined(CONFIG_USBIP)
	hwtr_dnssd_service(d, "_usbip", path == BAY_PATH_USBIP ? CONFIG_USBIP_SERVICE_PORT : 0);
#endif
	hwtr_dnssd_service(d, "_rfc2217", aux_rfc2217_port());

	hwtr_dnssd_txt(d, "id", bay_id());
	hwtr_dnssd_txt(d, "pos", bay_rack_position());
	hwtr_dnssd_txt(d, "fw", APP_VERSION_STRING);
	hwtr_dnssd_txt(d, "mode", bay_data_path_str(path));
	if (ports_count() > 0) {
		snprintf(slots, sizeof(slots), "%d", ports_count());
		hwtr_dnssd_txt(d, "slots", slots);
	}
}
#endif

int bay_net_init(const char *stored_id)
{
	int ret = hwtr_net_init("bay", stored_id, on_addr);

#if defined(CONFIG_HWTR_DNSSD)
	if (ret == 0) {
		ret = hwtr_dnssd_start(dnssd_fill);
	}
#endif
	return ret;
}

bool bay_net_connected(void)
{
	return hwtr_net_connected();
}

const char *bay_net_addr(void)
{
	return hwtr_net_addr();
}

const char *bay_id(void)
{
	return hwtr_net_id();
}

int bay_id_set(const char *new_id)
{
	int ret = hwtr_net_id_set(new_id);

	if (ret != 0) {
		return ret;
	}
#if defined(CONFIG_HWTR_DNSSD)
	hwtr_dnssd_refresh();
#endif
	return bay_settings_save_id(new_id);
}
