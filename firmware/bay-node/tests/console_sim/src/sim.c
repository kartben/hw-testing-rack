/*
 * The bay node's hardware, simulated: just enough of bay.h for the real
 * aux_console.c and web.c.  DUT power and RESET are printed on the console
 * as "SIM: ..." lines; run.py restarts or stops the fake DUT on them.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include "bay.h"

static bool power_on = true;
static bool force_pc;
static char id[BAY_ID_MAX_LEN + 1] = "b3";

/* --- DUT power, RESET, BOOT ----------------------------------------------- */

int dut_power_set(bool on)
{
	if (!on) {
		aux_dut_power(false);
	}
	power_on = on;
	printk("SIM: dut power %s\n", on ? "on" : "off");
	if (on) {
		aux_dut_power(true);
	}

	return 0;
}

bool dut_power_get(void)
{
	return power_on;
}

int dut_power_cycle(k_timeout_t off_time)
{
	dut_power_set(false);
	k_sleep(off_time);

	return dut_power_set(true);
}

bool dut_fault_active(void)
{
	return false;
}

bool dut_fault_latched(void)
{
	return false;
}

uint32_t dut_fault_count(void)
{
	return 0;
}

int dut_reset_set(bool asserted)
{
	if (asserted) {
		printk("SIM: dut reset\n");
	}

	return 0;
}

int dut_reset_pulse(k_timeout_t width)
{
	dut_reset_set(true);
	k_sleep(width);

	return dut_reset_set(false);
}

int dut_boot_set(bool asserted)
{
	ARG_UNUSED(asserted);

	return 0;
}

int dut_enter_bootloader(void)
{
	return dut_reset_pulse(K_MSEC(CONFIG_BAY_RESET_PULSE_MS));
}

/* A board idling at ~90 mA with a radio burst every 8 s */
int dut_power_read(struct dut_power_reading *r)
{
	int64_t t = k_uptime_get();
	int wobble = (int)((t / 250) % 24) - 12;
	int ma = power_on ? 90 + (t % 8000 < 1600 ? 42 : 0) + (wobble < 0 ? -wobble : wobble) / 2 : 0;

	r->bus_mv = power_on ? 5080 - ma / 10 : 0;
	r->current_ma = ma;
	r->power_mw = r->bus_mv * ma / 1000;

	return 0;
}

/* --- Data path, USB host, network, identity ------------------------------- */

bool usb_mux_service(void)
{
	return false;
}

bool usb_mux_pc_detected(void)
{
	return false;
}

bool usb_mux_force_pc_get(void)
{
	return force_pc;
}

int usb_mux_force_pc_set(bool force)
{
	force_pc = force;

	return 0;
}

enum bay_data_path usb_mux_path(void)
{
	return force_pc ? BAY_PATH_CLASSIC : BAY_PATH_USBIP;
}

const char *bay_data_path_str(enum bay_data_path path)
{
	return path == BAY_PATH_CLASSIC ? "classic" : path == BAY_PATH_SERVICE ? "service" : "usbip";
}

int usb_host_device_count(void)
{
	return 1;
}

int usb_host_usbip_sessions(void)
{
	return 0;
}

bool usb_host_running(void)
{
	return true;
}

bool bay_net_connected(void)
{
	return true;
}

const char *bay_net_addr(void)
{
	return "native_sim";
}

const char *bay_id(void)
{
	return id;
}

int bay_id_set(const char *new_id)
{
	strncpy(id, new_id, sizeof(id) - 1);

	return 0;
}

int bay_settings_save_force_pc(bool force)
{
	ARG_UNUSED(force);

	return 0;
}

int bay_settings_save_id(const char *new_id)
{
	ARG_UNUSED(new_id);

	return 0;
}

int bay_settings_save_aux(const struct aux_config *cfg)
{
	ARG_UNUSED(cfg);

	return 0;
}

int main(void)
{
	int ret = aux_console_init(NULL);

	if (ret == 0) {
		ret = web_init();
	}
	printk("SIM: %s\n", ret == 0 ? "ready" : "init failed");

	return 0;
}
