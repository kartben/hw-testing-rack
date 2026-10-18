/*
 * Wi-Fi station and hostname bay-<id>.local: firmware/common's hwtr_net
 * (shared with the power hub), plus the bay id in the settings.
 *
 * Credentials come from the Wi-Fi credentials library: stored with
 * "wifi cred add" (settings) or built in with CONFIG_WIFI_CREDENTIALS_STATIC
 * (see wifi.conf.example).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <hwtr/net.h>

#include "bay.h"

LOG_MODULE_REGISTER(bay_net, CONFIG_BAY_LOG_LEVEL);

BUILD_ASSERT(BAY_ID_MAX_LEN == HWTR_ID_MAX_LEN);

static void on_addr(const char *addr)
{
	LOG_INF("usbip attach -r %s -b 1-1", addr);
	bay_rack_info_changed();
}

int bay_net_init(const char *stored_id)
{
	return hwtr_net_init("bay", stored_id, on_addr);
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

	return ret != 0 ? ret : bay_settings_save_id(new_id);
}
