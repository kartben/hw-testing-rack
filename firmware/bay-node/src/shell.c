/*
 * "bay" shell commands, on the UART test pads and over telnet (port 23).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/net/hostname.h>
#include <zephyr/shell/shell.h>
#if defined(CONFIG_SHELL_BACKEND_TELNET)
#include <zephyr/shell/shell_telnet.h>
#endif

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

static char parity_char(uint8_t parity)
{
	return parity == AUX_PARITY_ODD ? 'O' : parity == AUX_PARITY_EVEN ? 'E' : 'N';
}

static void print_aux(const struct shell *sh)
{
	struct aux_config cfg;
	struct aux_stats st;

	aux_config_get(&cfg, false);
	aux_stats_get(&st);
	shell_print(sh, "AUX UART:  %u %u%c%u, Enter %s, echo %s, esptool reset %s", cfg.baud,
		    cfg.data_bits, parity_char(cfg.parity), cfg.stop_bits, aux_enter_str(cfg.enter),
		    cfg.echo ? "on" : "off", cfg.esptool_reset ? "on" : "off");
	shell_print(sh, "           %u web console(s), RFC 2217 tcp/%d %s, raw tcp/%d %s",
		    st.web_clients, CONFIG_BAY_RFC2217_PORT, st.rfc2217_client ? "in use" : "free",
		    CONFIG_BAY_AUX_TCP_PORT, st.raw_client ? "in use" : "free");
	shell_print(sh, "           rx %u tx %u dropped %u%s", st.rx, st.tx, st.dropped,
		    aux_loopback_get() ? ", loopback (test)" : "");
}

static void print_rack(const struct shell *sh)
{
	struct rack_hub_state hub;

	if (bay_rack_id() == 0) {
		shell_print(sh, "rack:      no position (not enumerated by the hub)");
		return;
	}
	if (bay_rack_hub(&hub)) {
		shell_print(sh, "rack:      %s (node 0x%02x), hub: %u.%u V%s, rows on 0x%x",
			    bay_rack_position(), bay_rack_id(), hub.mv / 1000, hub.mv % 1000 / 100,
			    (hub.flags & RACK_HUB_EPR) ? " EPR" : "", hub.rows_on);
	} else {
		shell_print(sh, "rack:      %s (node 0x%02x), hub silent", bay_rack_position(),
			    bay_rack_id());
	}
}

static int cmd_status(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	shell_print(sh, "bay id:    %s (%s.local)", bay_id()[0] ? bay_id() : "(unset)",
		    net_hostname_get());
	shell_print(sh, "network:   %s", bay_net_connected() ? bay_net_addr() : "down");
	print_rack(sh);
	shell_print(sh, "data path: %s (SERVICE %s, PC %s, classic %s)",
		    bay_data_path_str(usb_mux_path()), usb_mux_service() ? "on" : "off",
		    usb_mux_pc_detected() ? "plugged" : "absent",
		    usb_mux_force_pc_get() ? "forced" : "auto");
	shell_print(sh, "USB host:  %s, %d device(s), %d USB/IP session(s)",
		    usb_host_running() ? "running" : "stopped", usb_host_device_count(),
		    usb_host_usbip_sessions());
	print_power(sh);
	shell_print(sh, "faults:    %u since boot", dut_fault_count());
	print_aux(sh);
#if defined(CONFIG_BAY_CAMERA)
	{
		struct camera_status cam;

		camera_status(&cam);
		if (cam.present) {
			shell_print(sh, "camera:    %s, %s %s, port %u, %u client(s), %u frame(s), "
				    "%u error(s)", cam.model, cam.resolution, cam.quality, cam.port,
				    cam.clients, cam.frames, cam.errors);
		} else {
			shell_print(sh, "camera:    none");
		}
	}
#endif

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

/* "8N1", "7E2", ... */
static int parse_format(const char *fmt, struct aux_config *cfg)
{
	const char *parities = "NOE";
	const char *p;

	if (strlen(fmt) != 3 || fmt[0] < '5' || fmt[0] > '8' || (fmt[2] != '1' && fmt[2] != '2')) {
		return -EINVAL;
	}
	p = strchr(parities, fmt[1] & ~0x20);
	if (p == NULL || *p == '\0') {
		return -EINVAL;
	}

	cfg->data_bits = fmt[0] - '0';
	cfg->parity = p - parities;
	cfg->stop_bits = fmt[2] - '0';

	return 0;
}

static int cmd_aux(const struct shell *sh, size_t argc, char **argv)
{
	struct aux_config cfg;
	uint32_t ms = 250;
	char *end;
	unsigned long baud;
	int ret;

	if (argc == 1) {
		print_aux(sh);
		return 0;
	}

	if (strcmp(argv[1], "break") == 0) {
		if (argc > 2 && parse_ms(sh, argv[2], &ms) != 0) {
			return -EINVAL;
		}
		ret = aux_break(ms);
		if (ret != 0) {
			shell_error(sh, "BREAK failed (%d)%s", ret, ret == -EIO ? ": DUT is off" : "");
		}
		return ret;
	}

	if (strcmp(argv[1], "loopback") == 0) {
		if (argc == 2) {
			shell_print(sh, "loopback %s", aux_loopback_get() ? "on" : "off");
			return 0;
		}
		if (strcmp(argv[2], "on") != 0 && strcmp(argv[2], "off") != 0) {
			shell_error(sh, "usage: bay aux loopback [on|off]");
			return -EINVAL;
		}
		ret = aux_loopback(strcmp(argv[2], "on") == 0);
		if (ret != 0) {
			shell_error(sh, "no UART loopback on this SoC (%d)", ret);
		}
		return ret;
	}

	if (strcmp(argv[1], "send") == 0 && argc == 3) {
		static const char *const enters[] = {"\r", "\n", "\r\n"};
		const char *enter;

		aux_config_get(&cfg, false);
		enter = enters[MIN(cfg.enter, AUX_ENTER_CRLF)];
		aux_send((const uint8_t *)argv[2], strlen(argv[2]));
		aux_send((const uint8_t *)enter, strlen(enter));
		return 0;
	}

	aux_config_get(&cfg, true);
	baud = strtoul(argv[1], &end, 10);
	if (*end != '\0' || (argc > 2 && parse_format(argv[2], &cfg) != 0)) {
		shell_error(sh, "usage: bay aux [<baudrate> [8N1]] | break [ms] | send <text> | "
				"loopback [on|off]");
		return -EINVAL;
	}
	cfg.baud = baud;

	ret = aux_config_set(&cfg, true);
	if (ret != 0) {
		shell_error(sh, "the AUX UART refused %lu %s (%d)", baud, argc > 2 ? argv[2] : "",
			    ret);
	}

	return ret;
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

/* --- bay access ----------------------------------------------------------- */

/* Claims and resets need physical presence: not over the network */
static bool local_shell(const struct shell *sh)
{
#if defined(CONFIG_SHELL_BACKEND_TELNET)
	if (sh == shell_backend_telnet_get_ptr()) {
		shell_error(sh, "only on the node's own console (UART pads), not over telnet");
		return false;
	}
#endif
	return true;
}

static void print_services(const struct shell *sh, const char *what, uint8_t mask)
{
	char buf[48] = "";

	for (int svc = 0; svc < ACL_SERVICES; svc++) {
		if (mask & ACL_BIT(svc)) {
			strcat(buf, buf[0] ? "," : "");
			strcat(buf, acl_service_name(svc));
		}
	}
	shell_print(sh, "  %-24s %s", what, mask == ACL_ALL ? "all" : buf[0] ? buf : "-");
}

static int cmd_access_status(const struct shell *sh, size_t argc, char **argv)
{
	struct access_conn conns[ACCESS_MAX_CONNS];
	struct acl_rules r;
	struct acl_lease lease;
	uint32_t remaining;
	char a[ACL_CIDR_STR_LEN];
	int n;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	access_rules_get(&r);
	shell_print(sh, "admin key: %s", access_claimed() ? "set (claimed)" : "none (not claimed)");
	if (access_claim_pending()) {
		shell_print(sh, "claim:     pending, \"bay access claim\" or a short BOOT press");
	}
	shell_print(sh, "rules:     %s, %u source(s)", r.enabled ? "on" : "off (open)", r.count);
	for (int i = 0; i < r.count; i++) {
		char what[ACL_NAME_LEN + ACL_CIDR_STR_LEN + 2];

		acl_format_cidr(r.src[i].addr, r.src[i].prefix, a);
		snprintf(what, sizeof(what), "%s %s", r.src[i].name, a);
		print_services(sh, what, r.src[i].allow);
	}
	print_services(sh, "everyone else", r.everyone);

	if (access_lease_get(&lease, &remaining)) {
		acl_format_ip(lease.holder, a);
		shell_print(sh, "lease:     %s, %u s left%s%s", a, remaining,
			    lease.note[0] ? ", " : "", lease.note);
	} else {
		shell_print(sh, "lease:     none");
	}

	n = access_connections(conns, ARRAY_SIZE(conns));
	for (int i = 0; i < n; i++) {
		acl_format_ip(conns[i].ip, a);
		shell_print(sh, "  %-12s %-12s %s:%u", conns[i].id, conns[i].label, a,
			    conns[i].port);
	}
	shell_print(sh, "refused:   %u since boot", access_refused_total());

	return 0;
}

static int cmd_access_claim(const struct shell *sh, size_t argc, char **argv)
{
	int ret;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	if (!local_shell(sh)) {
		return -EPERM;
	}
	ret = access_claim_confirm();
	if (ret == -ENOENT) {
		shell_error(sh, "no claim pending: start one from the web page or bayctl");
		return ret;
	}
	shell_print(sh, "claimed: the requester gets the admin key%s",
		    ret == 0 ? "" : " (not saved)");

	return ret;
}

static int cmd_access_onoff(const struct shell *sh, size_t argc, char **argv)
{
	bool on = strcmp(argv[0], "on") == 0;

	ARG_UNUSED(argc);

	if (!on && !local_shell(sh)) {
		return -EPERM;
	}

	return access_set_enabled(on);
}

static int cmd_access_reset(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	if (!local_shell(sh)) {
		return -EPERM;
	}
	shell_print(sh, "no admin key, no rules, no lease: the node is open until claimed again");

	return access_reset();
}

static int cmd_access_release(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	if (access_lease_release(0, true) != 0) {
		shell_print(sh, "no lease");
	}

	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(sub_access,
	SHELL_CMD_ARG(claim, NULL, "Confirm a pending claim (like a short BOOT press)",
		      cmd_access_claim, 1, 0),
	SHELL_CMD_ARG(on, NULL, "Apply the rules", cmd_access_onoff, 1, 0),
	SHELL_CMD_ARG(off, NULL, "Rules off: every address may use everything", cmd_access_onoff,
		      1, 0),
	SHELL_CMD_ARG(release, NULL, "End the lease", cmd_access_release, 1, 0),
	SHELL_CMD_ARG(reset, NULL, "Forget the admin key, the rules and the lease",
		      cmd_access_reset, 1, 0),
	SHELL_SUBCMD_SET_END
);

SHELL_STATIC_SUBCMD_SET_CREATE(sub_bay,
	SHELL_CMD_ARG(status, NULL, "Mode, network, power, USB host and AUX state", cmd_status,
		      1, 0),
	SHELL_CMD_ARG(power, NULL, "DUT VBUS: [on|off|cycle [ms]], no argument = V/I/P", cmd_power,
		      1, 2),
	SHELL_CMD_ARG(reset, NULL, "Pulse the DUT RESET line: [ms|hold|release]", cmd_reset, 1, 1),
	SHELL_CMD_ARG(boot, NULL, "Reset into the DUT's bootloader, or BOOT line [hold|release]",
		      cmd_boot, 1, 1),
	SHELL_CMD_ARG(mode, NULL, "USB data path: [usbip|classic] (persistent)", cmd_mode, 1, 1),
	SHELL_CMD_ARG(aux, NULL,
		      "AUX UART: [<baudrate> [8N1]] (persistent) | break [ms] | send <text> | "
		      "loopback [on|off] (test)",
		      cmd_aux, 1, 2),
	SHELL_CMD_ARG(access, &sub_access, "Access control: rules, lease, admin key",
		      cmd_access_status, 1, 0),
	SHELL_CMD_ARG(id, NULL, "Bay id, sets the hostname bay-<id>: [<id>] (persistent)", cmd_id,
		      1, 1),
	SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(bay, &sub_bay, "hw-testing-rack bay node", NULL);
