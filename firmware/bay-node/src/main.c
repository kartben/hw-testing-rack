/*
 * hw-testing-rack bay node.
 *
 * The USB/IP service (CONFIG_USBIP) starts by itself before main() and
 * exports whatever enumerates on the DUT port.  main() brings up the rest:
 * access control, DUT power and fault handling, the data-path muxes, the AUX
 * UART bridge, Wi-Fi, the web server, and then drives the status LED.  Built
 * with MCUboot (sysbuild), it also takes firmware updates over the network
 * (firmware/common/lib/update.c).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/input/input.h>
#include <zephyr/settings/settings.h>
#include <zephyr/logging/log.h>

#include <hwtr/update.h>

#include "bay.h"

LOG_MODULE_REGISTER(bay, CONFIG_BAY_LOG_LEVEL);

/* --- Persistent settings: "bay/id", "bay/force_pc", "bay/aux", "bay/racked" - */

static char stored_id[BAY_ID_MAX_LEN + 1];
static bool stored_force_pc;
static struct aux_config stored_aux;
static bool have_stored_aux;
static bool stored_racked; /* a hub gave it a rack address once */

static int bay_settings_set(const char *key, size_t len, settings_read_cb read_cb, void *cb_arg)
{
	ssize_t n;

	if (settings_name_steq(key, "id", NULL)) {
		if (len > BAY_ID_MAX_LEN) {
			return -EINVAL;
		}
		n = read_cb(cb_arg, stored_id, len);
		if (n < 0) {
			return (int)n;
		}
		stored_id[n] = '\0';
		return 0;
	}

	if (settings_name_steq(key, "force_pc", NULL)) {
		n = read_cb(cb_arg, &stored_force_pc, sizeof(stored_force_pc));
		return n < 0 ? (int)n : 0;
	}

	if (settings_name_steq(key, "racked", NULL)) {
		n = read_cb(cb_arg, &stored_racked, sizeof(stored_racked));
		return n < 0 ? (int)n : 0;
	}

	if (settings_name_steq(key, "aux", NULL)) {
		/* A record from another firmware layout is ignored */
		if (len != sizeof(stored_aux)) {
			return 0;
		}
		n = read_cb(cb_arg, &stored_aux, sizeof(stored_aux));
		have_stored_aux = n == sizeof(stored_aux);
		return n < 0 ? (int)n : 0;
	}

	return -ENOENT;
}

SETTINGS_STATIC_HANDLER_DEFINE(bay, "bay", NULL, bay_settings_set, NULL, NULL);

int bay_settings_save_force_pc(bool force)
{
	return settings_save_one("bay/force_pc", &force, sizeof(force));
}

int bay_settings_save_id(const char *id)
{
	return settings_save_one("bay/id", id, strlen(id));
}

bool bay_settings_racked(void)
{
	return stored_racked;
}

int bay_settings_save_racked(void)
{
	if (stored_racked) {
		return 0;
	}
	stored_racked = true;
	return settings_save_one("bay/racked", &stored_racked, sizeof(stored_racked));
}

int bay_settings_save_aux(const struct aux_config *cfg)
{
	return settings_save_one("bay/aux", cfg, sizeof(*cfg));
}

/*
 * --- BOOT button -----------------------------------------------------------
 *
 *   short press      confirms a pending access claim (physical presence)
 *   1 s or more      power-cycles the DUT
 *   10 s or more     access control back to an unclaimed, open node
 */

#define LONG_PRESS_MS 1000

static void power_cycle_handler(struct k_work *work)
{
	ARG_UNUSED(work);
	LOG_INF("BOOT button: DUT power cycle");
	dut_power_cycle(K_MSEC(CONFIG_BAY_POWER_CYCLE_MS));
}

static K_WORK_DEFINE(power_cycle_work, power_cycle_handler);

static void claim_handler(struct k_work *work)
{
	ARG_UNUSED(work);
	if (access_claim_confirm() == 0) {
		LOG_INF("BOOT button: claim confirmed");
	}
}

static K_WORK_DEFINE(claim_work, claim_handler);

static void access_reset_handler(struct k_work *work)
{
	ARG_UNUSED(work);
	LOG_WRN("BOOT button held: access reset");
	(void)access_reset();
}

static K_WORK_DEFINE(access_reset_work, access_reset_handler);

static void button_cb(struct input_event *evt, void *user_data)
{
	static int64_t pressed_at;

	ARG_UNUSED(user_data);

	if (evt->type != INPUT_EV_KEY || evt->code != INPUT_KEY_0) {
		return;
	}

	if (evt->value != 0) {
		pressed_at = k_uptime_get();
	} else if (k_uptime_get() - pressed_at >= CONFIG_BAY_ACCESS_RESET_HOLD_MS) {
		k_work_submit(&access_reset_work);
	} else if (k_uptime_get() - pressed_at >= LONG_PRESS_MS) {
		k_work_submit(&power_cycle_work);
	} else if (access_claim_pending()) {
		k_work_submit(&claim_work);
	}
}

INPUT_CALLBACK_DEFINE(NULL, button_cb, NULL);

#if defined(CONFIG_HWTR_UPDATE)
/* A new firmware on trial confirms itself once these work as they did before */
static uint32_t update_health(void)
{
	struct rack_hub_state hub;

	return (bay_net_connected() ? HWTR_UP_WIFI : 0) |
	       (RACK_NODE_VALID(bay_rack_id()) && bay_rack_hub(&hub) ? HWTR_UP_BUS : 0);
}

/*
 * A test boot with no update record: Wi-Fi, and the rack bus only on a node a
 * hub has addressed before (a standalone bay, on a PD trigger, never has one)
 */
static uint32_t update_expected(void)
{
	return HWTR_UP_WIFI | (bay_settings_racked() ? HWTR_UP_BUS : 0);
}

/* A reserved bay is not updated unless the admin insists */
static const char *update_busy(void)
{
	static char why[96];
	struct acl_lease lease;
	uint32_t remaining;
	char ip[16];

	if (!access_lease_get(&lease, &remaining)) {
		return NULL;
	}
	acl_format_ip(lease.holder, ip);
	snprintf(why, sizeof(why), "reserved by %s for %u min more: force to update anyway", ip,
		 (unsigned int)DIV_ROUND_UP(remaining, 60));
	return why;
}

static const struct hwtr_update_cfg update_cfg = {
	.health = update_health,
	.expected = update_expected,
	.busy = update_busy,
};
#endif

int main(void)
{
	int ret;

	LOG_INF("hw-testing-rack bay node");
	fault_init();

	ret = settings_subsys_init();
	if (ret == 0) {
		ret = settings_load();
	}
	if (ret != 0) {
		/* -EDEADLK: NVS found no usable sector, e.g. another firmware's data */
		LOG_ERR("settings unavailable (%d): defaults only%s", ret,
			ret == -EDEADLK ? "; storage partition not NVS: west flash --erase" : "");
	}

#if defined(CONFIG_HWTR_UPDATE)
	/* A test boot after an update: on trial (and the watchdog on) from here
	 * until Wi-Fi and the rack bus work again
	 */
	(void)hwtr_update_init(&update_cfg);
#endif

	/* Before any server: the rules apply from the first connection */
	ret = access_init();
	if (ret != 0) {
		LOG_ERR("access control init failed: %d", ret);
	}

	ret = dut_init();
	if (ret != 0) {
		LOG_ERR("DUT control init failed: %d", ret);
	}

	/* A DATA x4 in the drawer: its ports, once DUT_5V has settled */
	ret = ports_init();
	if (ret != 0) {
		LOG_ERR("DATA x4 ports init failed: %d", ret);
	}

	ret = usb_mux_init(stored_force_pc);
	if (ret != 0) {
		LOG_ERR("USB mux init failed: %d", ret);
	}

	(void)status_led_init();

	ret = aux_console_init(have_stored_aux ? &stored_aux : NULL);
	if (ret != 0) {
		LOG_ERR("AUX UART init failed: %d", ret);
	}

	ret = bay_net_init(stored_id);
	if (ret != 0) {
		LOG_ERR("network init failed: %d", ret);
	}

	/* After the network: the MAC address names the node on the rack bus */
	ret = bay_rack_init();
	if (ret != 0 && ret != -ENOTSUP) {
		LOG_ERR("rack bus init failed: %d", ret);
	}

	ret = web_init();
	if (ret != 0) {
		LOG_ERR("web server init failed: %d", ret);
	}

#if defined(CONFIG_BAY_CAMERA)
	/* Optional: -ENODEV without a camera on J6 */
	ret = camera_init();
	if (ret != 0 && ret != -ENODEV) {
		LOG_ERR("camera init failed: %d", ret);
	}
#endif

	while (true) {
		status_led_update();
		k_sleep(K_MSEC(250));
	}

	return 0;
}
