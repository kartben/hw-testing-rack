/*
 * "bay" shell commands, on the UART test pads and over telnet (port 23).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdlib.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/net/hostname.h>
#include <zephyr/shell/shell.h>

#include "bay.h"

static int parse_ms(const struct shell *sh, const char *arg, uint32_t *ms)
{
	char *end;
	unsigned long v = strtoul(arg, &end, 10);

	if (*arg == '\0' || *end != '\0' || v == 0 || v > 60000) {
		shell_error(sh, "duration must be 1..60000 ms");
		return -EINVAL;
	}
	*ms = (uint32_t)v;

	return 0;
}

static void print_power(const struct shell *sh)
{
	struct dut_power_reading r;
	int ret;

	shell_print(sh, "DUT VBUS:  %s%s%s", dut_power_get() ? "on" : "off",
		    dut_fault_active() ? ", FAULT (current limit)" : "",
		    dut_fault_latched() ? ", switched off by fault" : "");

	ret = dut_power_read(&r);
	if (ret == 0) {
		shell_print(sh, "           %d mV, %d mA, %d mW", r.bus_mv, r.current_ma, r.power_mw);
	} else {
		shell_print(sh, "           no reading (%d)", ret);
	}
}

static int cmd_status(const struct shell *sh, size_t argc, char **argv)
{
	uint32_t rx, tx, drop;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	shell_print(sh, "bay id:    %s (%s.local)", bay_id()[0] ? bay_id() : "(unset)",
		    net_hostname_get());
	shell_print(sh, "network:   %s", bay_net_connected() ? bay_net_addr() : "down");
	shell_print(sh, "data path: %s (SERVICE %s, PC %s, classic %s)",
		    bay_data_path_str(usb_mux_path()), usb_mux_service() ? "on" : "off",
		    usb_mux_pc_detected() ? "plugged" : "absent",
		    usb_mux_force_pc_get() ? "forced" : "auto");
	shell_print(sh, "USB host:  %s, %d device(s), %d USB/IP session(s)",
		    usb_host_running() ? "running" : "stopped", usb_host_device_count(),
		    usb_host_usbip_sessions());
	print_power(sh);
	shell_print(sh, "faults:    %u since boot", dut_fault_count());
	aux_bridge_stats(&rx, &tx, &drop);
	shell_print(sh, "AUX UART:  %u baud, client %s, rx %u tx %u dropped %u",
		    aux_bridge_baudrate(), aux_bridge_client_connected() ? "connected" : "none",
		    rx, tx, drop);

	return 0;
}

static int cmd_power(const struct shell *sh, size_t argc, char **argv)
{
	uint32_t ms = CONFIG_BAY_POWER_CYCLE_MS;

	if (argc == 1) {
		print_power(sh);
		return 0;
	}

	if (strcmp(argv[1], "on") == 0) {
		return dut_power_set(true);
	}
	if (strcmp(argv[1], "off") == 0) {
		return dut_power_set(false);
	}
	if (strcmp(argv[1], "cycle") == 0) {
		if (argc > 2 && parse_ms(sh, argv[2], &ms) != 0) {
			return -EINVAL;
		}
		return dut_power_cycle(K_MSEC(ms));
	}

	shell_error(sh, "usage: bay power [on|off|cycle [ms]]");

	return -EINVAL;
}

static int cmd_reset(const struct shell *sh, size_t argc, char **argv)
{
	uint32_t ms = CONFIG_BAY_RESET_PULSE_MS;

	if (argc > 1 && strcmp(argv[1], "hold") == 0) {
		return dut_reset_set(true);
	}
	if (argc > 1 && strcmp(argv[1], "release") == 0) {
		return dut_reset_set(false);
	}
	if (argc > 1 && parse_ms(sh, argv[1], &ms) != 0) {
		return -EINVAL;
	}

	return dut_reset_pulse(K_MSEC(ms));
}

static int cmd_boot(const struct shell *sh, size_t argc, char **argv)
{
	if (argc == 1) {
		/* BOOT held across a RESET pulse */
		return dut_enter_bootloader();
	}
	if (strcmp(argv[1], "hold") == 0) {
		return dut_boot_set(true);
	}
	if (strcmp(argv[1], "release") == 0) {
		return dut_boot_set(false);
	}

	shell_error(sh, "usage: bay boot [hold|release]");

	return -EINVAL;
}

static int cmd_mode(const struct shell *sh, size_t argc, char **argv)
{
	if (argc > 1) {
		if (strcmp(argv[1], "classic") == 0) {
			return usb_mux_force_pc_set(true);
		}
		if (strcmp(argv[1], "usbip") == 0) {
			return usb_mux_force_pc_set(false);
		}
		shell_error(sh, "usage: bay mode [usbip|classic]");
		return -EINVAL;
	}

	shell_print(sh, "%s (classic %s, SERVICE %s, PC %s)", bay_data_path_str(usb_mux_path()),
		    usb_mux_force_pc_get() ? "forced" : "auto", usb_mux_service() ? "on" : "off",
		    usb_mux_pc_detected() ? "plugged" : "absent");

	return 0;
}

static int cmd_aux(const struct shell *sh, size_t argc, char **argv)
{
	char *end;
	unsigned long baud;

	if (argc == 1) {
		shell_print(sh, "%u baud, tcp/%d", aux_bridge_baudrate(), CONFIG_BAY_AUX_TCP_PORT);
		return 0;
	}

	baud = strtoul(argv[1], &end, 10);
	if (*end != '\0' || baud < 300 || baud > 5000000) {
		shell_error(sh, "usage: bay aux [<baudrate>]");
		return -EINVAL;
	}

	return aux_bridge_set_baudrate((uint32_t)baud);
}

static int cmd_id(const struct shell *sh, size_t argc, char **argv)
{
	int ret;

	if (argc == 1) {
		shell_print(sh, "%s", bay_id()[0] ? bay_id() : "(unset)");
		return 0;
	}

	ret = bay_id_set(argv[1]);
	if (ret != 0) {
		shell_error(sh, "id: 1-%d characters, letters, digits and '-'", BAY_ID_MAX_LEN);
		return ret;
	}
	shell_print(sh, "hostname %s.local", net_hostname_get());

	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(sub_bay,
	SHELL_CMD_ARG(status, NULL, "Mode, network, power, USB host and AUX state", cmd_status,
		      1, 0),
	SHELL_CMD_ARG(power, NULL, "DUT VBUS: [on|off|cycle [ms]], no argument = V/I/P", cmd_power,
		      1, 2),
	SHELL_CMD_ARG(reset, NULL, "Pulse the DUT RESET line: [ms|hold|release]", cmd_reset, 1, 1),
	SHELL_CMD_ARG(boot, NULL, "Reset into the DUT's bootloader, or BOOT line [hold|release]",
		      cmd_boot, 1, 1),
	SHELL_CMD_ARG(mode, NULL, "USB data path: [usbip|classic] (persistent)", cmd_mode, 1, 1),
	SHELL_CMD_ARG(aux, NULL, "AUX UART: [<baudrate>]", cmd_aux, 1, 1),
	SHELL_CMD_ARG(id, NULL, "Bay id, sets the hostname bay-<id>: [<id>] (persistent)", cmd_id,
		      1, 1),
	SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(bay, &sub_bay, "hw-testing-rack bay node", NULL);
