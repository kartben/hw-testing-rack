/*
 * hw-testing-rack power hub: the rack controller.
 *
 * USB-C PD input (pd.c), the four eFused rows (rows.c), the rack bus master
 * (bus.c), Wi-Fi and the web page (web.c), the "hub" shell (shell.c).
 * main() brings them up in that order and then drives the CTL LED.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/led.h>
#include <zephyr/settings/settings.h>
#include <zephyr/logging/log.h>

#include <hwtr/net.h>

#include "hub.h"

LOG_MODULE_REGISTER(hub, CONFIG_HUB_LOG_LEVEL);

/* --- Settings: "hub/id", "hub/epr", "hub/rows", "hub/shed" ------------------- */

static char stored_id[HWTR_ID_MAX_LEN + 1];
static bool stored_epr = IS_ENABLED(CONFIG_HUB_PD_EPR);
static uint8_t stored_rows = BIT_MASK(HUB_ROWS);
static char stored_shed[HUB_ROWS + 1];

static int hub_settings_set(const char *key, size_t len, settings_read_cb read_cb, void *cb_arg)
{
	ssize_t n;

	if (settings_name_steq(key, "id", NULL)) {
		if (len > HWTR_ID_MAX_LEN) {
			return -EINVAL;
		}
		n = read_cb(cb_arg, stored_id, len);
		if (n >= 0) {
			stored_id[n] = '\0';
		}
		return n < 0 ? (int)n : 0;
	}
	if (settings_name_steq(key, "epr", NULL)) {
		n = read_cb(cb_arg, &stored_epr, sizeof(stored_epr));
		return n < 0 ? (int)n : 0;
	}
	if (settings_name_steq(key, "rows", NULL)) {
		n = read_cb(cb_arg, &stored_rows, sizeof(stored_rows));
		return n < 0 ? (int)n : 0;
	}
	if (settings_name_steq(key, "shed", NULL)) {
		if (len != HUB_ROWS) {
			return 0;
		}
		n = read_cb(cb_arg, stored_shed, HUB_ROWS);
		return n < 0 ? (int)n : 0;
	}

	return -ENOENT;
}

SETTINGS_STATIC_HANDLER_DEFINE(hub, "hub", NULL, hub_settings_set, NULL, NULL);

int hub_settings_save_id(const char *id)
{
	return settings_save_one("hub/id", id, strlen(id));
}

int hub_settings_save_epr(bool epr)
{
	return settings_save_one("hub/epr", &epr, sizeof(epr));
}

int hub_settings_save_rows(uint8_t wanted)
{
	return settings_save_one("hub/rows", &wanted, sizeof(wanted));
}

int hub_settings_save_shed(const char *order)
{
	return settings_save_one("hub/shed", order, HUB_ROWS);
}

/* --- CTL LED -------------------------------------------------------------- */

static const struct led_dt_spec ctl = LED_DT_SPEC_GET(DT_NODELABEL(ctl_led));

/*
 * on                 contract, rows as wanted, no fault
 * slow blink         no PD charger (console USB only), or contract not final yet
 * double blink       rows shed for lack of power
 * fast blink         a row in fault
 */
static bool led_level(uint32_t tick)
{
	struct hub_pd_status pd;

	pd_status(&pd);
	if (rows_fault_mask() != 0) {
		return tick & 1;
	}
	if (rows_shed_mask() != 0 && pd.final) {
		return (tick % 8) == 0 || (tick % 8) == 2;
	}
	if (!pd.final) {
		return (tick & 4) != 0;
	}
	return true;
}

int main(void)
{
	uint32_t tick = 0;
	int ret;

	LOG_INF("hw-testing-rack power hub");

	ret = settings_subsys_init();
	if (ret == 0) {
		ret = settings_load();
	}
	if (ret != 0) {
		LOG_ERR("settings unavailable (%d): defaults only%s", ret,
			ret == -EDEADLK ? "; storage partition not NVS: west flash --erase" : "");
	}

	/* First: the rows keep what they were doing across a controller reset */
	ret = rows_init(stored_rows, stored_shed[0] ? stored_shed : NULL);
	if (ret != 0) {
		LOG_ERR("rows init failed: %d", ret);
	}

	ret = bus_init();
	if (ret != 0) {
		LOG_ERR("rack bus init failed: %d", ret);
	} else if (rows_on_mask() != 0) {
		bus_enumerate(0);
	}

	ret = pd_init(stored_epr);
	if (ret != 0) {
		LOG_ERR("PD init failed: %d", ret);
	}

	ret = hwtr_net_init("rack", stored_id, NULL);
	if (ret != 0) {
		LOG_ERR("network init failed: %d", ret);
	}

	ret = web_init();
	if (ret != 0) {
		LOG_ERR("web server init failed: %d", ret);
	}

	while (true) {
		if (led_is_ready_dt(&ctl)) {
			(void)(led_level(tick) ? led_on_dt(&ctl) : led_off_dt(&ctl));
		}
		tick++;
		k_sleep(K_MSEC(125));
	}

	return 0;
}
