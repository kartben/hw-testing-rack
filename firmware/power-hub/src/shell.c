/*
 * "hub" shell commands (console USB-C and telnet).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdlib.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/net/hostname.h>
#include <zephyr/shell/shell.h>

#include <hwtr/admin.h>
#include <hwtr/net.h>

#include "hub.h"

static int parse_row(const struct shell *sh, const char *arg)
{
	int row = (strlen(arg) == 1) ? (arg[0] & ~0x20) - 'A' : -1;

	if (row < 0 || row >= HUB_ROWS) {
		shell_error(sh, "row: A-D");
		return -EINVAL;
	}
	return row;
}

/* "C3" or "0x23" */
static int parse_node(const char *arg)
{
	char *end;
	long id;

	if (strlen(arg) >= 2 && (arg[0] & ~0x20) >= 'A' && (arg[0] & ~0x20) <= 'D' &&
	    arg[1] >= '1' && arg[1] <= '9') {
		id = RACK_NODE_ID((arg[0] & ~0x20) - 'A', strtol(arg + 1, &end, 10));
	} else {
		id = strtol(arg, &end, 0);
	}
	return (*end == '\0' && RACK_NODE_VALID(id)) ? (int)id : -EINVAL;
}

static void print_pd(const struct shell *sh)
{
	struct hub_pd_status pd;

	pd_status(&pd);
	if (pd.contract_mv != 0) {
		shell_print(sh, "PD:        %u.%u V / %u.%02u A %s (PDO %d)%s, VBUS %u mV",
			    pd.contract_mv / 1000, pd.contract_mv % 1000 / 100, pd.contract_ma / 1000,
			    pd.contract_ma % 1000 / 10, pd_state_str(pd.state), pd.selected,
			    pd.final ? "" : ", settling", pd.vbus_mv);
	} else {
		shell_print(sh, "PD:        %s, VBUS %u mV", pd_state_str(pd.state), pd.vbus_mv);
	}
	shell_print(sh, "           sink: status 0x%02x, PG %s, asked %u mV, granted %u mA",
		    pd.protocol, pd.power_good ? "low (good)" : "high", pd.asked_mv, pd.granted_ma);
	shell_print(sh, "           asks for %s%s", pd.epr_pref ? "28 V EPR when offered" : "20 V",
		    pd.epr_refused ? " (28 V refused: 20 V)" : "");
}

static void print_rows(const struct shell *sh)
{
	for (int r = 0; r < HUB_ROWS; r++) {
		struct rack_hub_node nodes[RACK_POSITIONS + 1];
		struct hub_row_status st;
		int n;

		rows_status(r, &st);
		n = bus_row_nodes(r, nodes);
		shell_print(sh, "row %c:     %-8s %4d mA  %d node(s)%s%s, %u fault(s)", 'A' + r,
			    rows_state_str(st.state), st.ma, n, st.fault ? ", FAULT" : "",
			    st.wanted ? "" : ", off by hand", st.faults);
	}
	shell_print(sh, "shed order: %s", rows_shed_order());
}

static int cmd_status(const struct shell *sh, size_t argc, char **argv)
{
	struct hub_bus_status bus;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	shell_print(sh, "rack:      %s.local, %s", net_hostname_get(),
		    hwtr_net_connected() ? hwtr_net_addr() : "network down");
	print_pd(sh);
	print_rows(sh);
	bus_status(&bus);
	shell_print(sh, "rack bus:  %d node(s), %d lost, %u frames/s, %u bus-off, %u enumeration(s)%s",
		    bus.nodes, bus.lost, bus.rx_fps, bus.bus_off, bus.enumerations,
		    bus.enumerating ? " (enumerating)" : "");

	return 0;
}

static int cmd_row(const struct shell *sh, size_t argc, char **argv)
{
	int row = parse_row(sh, argv[1]);
	int ret;

	if (row < 0) {
		return row;
	}
	if (strcmp(argv[2], "on") == 0) {
		ret = rows_set(row, true);
	} else if (strcmp(argv[2], "off") == 0) {
		ret = rows_set(row, false);
	} else if (strcmp(argv[2], "cycle") == 0) {
		ret = rows_cycle(row, argc > 3 ? strtoul(argv[3], NULL, 10) : 0);
	} else {
		shell_error(sh, "usage: hub row <A-D> on|off|cycle [ms]");
		return -EINVAL;
	}
	if (ret != 0) {
		shell_error(sh, "failed (%d)", ret);
	}
	return ret;
}

static int cmd_pd(const struct shell *sh, size_t argc, char **argv)
{
	struct hub_pd_status pd;

	if (argc > 1) {
		if (strcmp(argv[1], "epr") != 0 && strcmp(argv[1], "20v") != 0) {
			shell_error(sh, "usage: hub pd [epr|20v]");
			return -EINVAL;
		}
		return pd_set_epr(strcmp(argv[1], "epr") == 0);
	}

	print_pd(sh);
	pd_status(&pd);
	if (pd.npdos == 0 && pd.state != HUB_PD_NONE) {
		shell_print(sh, "  the sink shows no offers");
	}
	for (int i = 0; i < CH224A_PDO_COUNT; i++) {
		const struct ch224a_pdo *p = &pd.pdos[i];
		static const char *const types[] = {"", "fixed", "PPS", "AVS", "other"};

		if (p->type == CH224A_PDO_NONE || p->type == CH224A_PDO_OTHER) {
			continue;
		}
		if (p->type == CH224A_PDO_AVS) {
			shell_print(sh, "    PDO %2d EPR AVS %u-%u mV, %u W", i + 1, p->min_mv,
				    p->max_mv, p->pdp_w);
		} else if (p->type == CH224A_PDO_FIXED) {
			shell_print(sh, "  %c PDO %2d %s %s %u mV, %u mA", i + 1 == pd.selected ? '*' : ' ',
				    i + 1, p->epr ? "EPR" : "SPR", types[p->type], p->max_mv, p->max_ma);
		} else {
			shell_print(sh, "  %c PDO %2d %s %s %u-%u mV, %u mA",
				    i + 1 == pd.selected ? '*' : ' ', i + 1, p->epr ? "EPR" : "SPR",
				    types[p->type], p->min_mv, p->max_mv, p->max_ma);
		}
	}
	return 0;
}

static int cmd_nodes(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	for (int r = 0; r < HUB_ROWS; r++) {
		struct rack_hub_node nodes[RACK_POSITIONS + 1];

		(void)bus_row_nodes(r, nodes);
		for (int p = 1; p <= RACK_POSITIONS; p++) {
			const struct rack_hub_node *n = &nodes[p];
			char name[4];

			if (n->state == RACK_NODE_NONE) {
				continue;
			}
			shell_print(sh, "%-3s 0x%02x %02x:%02x:%02x:%02x:%02x:%02x %u.%u.%u.%u "
					"flags 0x%02x DUT %u mA, fw %u.%u.%u, state %u",
				    rack_node_name(RACK_NODE_ID(r, p), name), RACK_NODE_ID(r, p),
				    n->mac[0], n->mac[1], n->mac[2], n->mac[3], n->mac[4], n->mac[5],
				    n->info.ipv4[0], n->info.ipv4[1], n->info.ipv4[2], n->info.ipv4[3],
				    n->status.flags, n->status.dut_ma, n->info.fw[0], n->info.fw[1],
				    n->info.fw[2], n->state);
		}
	}
	return 0;
}

static int cmd_enumerate(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	bus_enumerate(0);
	shell_print(sh, "enumerating the rows that are on (\"hub nodes\" for the result)");
	return 0;
}

static int cmd_node(const struct shell *sh, size_t argc, char **argv)
{
	int id = parse_node(argv[1]);
	uint8_t args[3] = {0};
	uint8_t op, nargs = 0;

	ARG_UNUSED(argc);

	if (id < 0) {
		shell_error(sh, "node: C3 or 0x23");
		return -EINVAL;
	}
	if (strcmp(argv[2], "identify") == 0) {
		op = RACK_CMD_IDENTIFY;
		args[0] = 10;
		nargs = 1;
	} else if (strcmp(argv[2], "reset") == 0) {
		op = RACK_CMD_RESET;
	} else if (strcmp(argv[2], "bootloader") == 0) {
		op = RACK_CMD_BOOTLOADER;
	} else if (strcmp(argv[2], "power-cycle") == 0) {
		op = RACK_CMD_POWER;
		args[0] = 2;
		nargs = 3;
	} else if (strcmp(argv[2], "reboot") == 0) {
		op = RACK_CMD_REBOOT;
	} else {
		shell_error(sh, "action: identify, reset, bootloader, power-cycle, reboot");
		return -EINVAL;
	}

	if (bus_cmd((uint8_t)id, op, args, nargs) < 0) {
		shell_error(sh, "rack bus busy");
		return -EBUSY;
	}
	shell_print(sh, "sent (\"hub events\" for the answer)");
	return 0;
}

static int cmd_events(const struct shell *sh, size_t argc, char **argv)
{
	static struct hub_event ev[CONFIG_HUB_EVENTS];
	int64_t now = k_uptime_get();
	int n = hub_events_get(ev, ARRAY_SIZE(ev));

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	for (int i = n - 1; i >= 0; i--) {
		shell_print(sh, "%6u s ago  %-5s %s", (uint32_t)((now - ev[i].t_ms) / 1000),
			    hub_ev_kind_str(ev[i].kind), ev[i].text);
	}
	return 0;
}

static int cmd_shed(const struct shell *sh, size_t argc, char **argv)
{
	if (argc > 1 && rows_set_shed_order(argv[1]) != 0) {
		shell_error(sh, "shed order: the four rows, first shed first (default DCBA)");
		return -EINVAL;
	}
	shell_print(sh, "shed order: %s", rows_shed_order());
	return 0;
}

/* The shell is on the console USB-C only (no telnet): it is physical access */
static int cmd_access(const struct shell *sh, size_t argc, char **argv)
{
	int ret;

	if (argc == 1) {
		shell_print(sh, "admin key: %s%s", hwtr_admin_claimed() ? "set" : "none (unclaimed)",
			    hwtr_admin_claim_pending() ? ", a claim waits for BOOT" : "");
		return 0;
	}
	if (strcmp(argv[1], "claim") == 0) {
		ret = hwtr_admin_claim_confirm();
		if (ret == -ENOENT) {
			shell_error(sh, "no pending claim (start one from the web page)");
		} else if (ret == 0) {
			hub_event(HUB_EV_PD, "claimed: admin key set (local shell)");
			shell_print(sh, "claimed");
		}
		return ret;
	}
	if (strcmp(argv[1], "reset") == 0) {
		ret = hwtr_admin_forget();
		hub_event(HUB_EV_FAULT, "admin key forgotten (local shell)");
		shell_print(sh, "admin key forgotten: the hub can be claimed again");
		return ret;
	}
	shell_error(sh, "usage: hub access [claim|reset]");
	return -EINVAL;
}

static int cmd_id(const struct shell *sh, size_t argc, char **argv)
{
	int ret;

	if (argc == 1) {
		shell_print(sh, "%s", hwtr_net_id()[0] ? hwtr_net_id() : "(unset)");
		return 0;
	}
	ret = hwtr_net_id_set(argv[1]);
	if (ret != 0) {
		shell_error(sh, "id: 1-%d characters, letters, digits and '-'", HWTR_ID_MAX_LEN);
		return ret;
	}
	(void)hub_settings_save_id(argv[1]);
	shell_print(sh, "hostname %s.local", net_hostname_get());
	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(sub_hub,
	SHELL_CMD_ARG(status, NULL, "PD contract, rows, rack bus", cmd_status, 1, 0),
	SHELL_CMD_ARG(pd, NULL, "Contract and the charger's offers; [epr|20v] (persistent)",
		      cmd_pd, 1, 1),
	SHELL_CMD_ARG(row, NULL, "<A-D> on|off|cycle [ms]: row power (on/off persistent)",
		      cmd_row, 3, 1),
	SHELL_CMD_ARG(nodes, NULL, "Nodes on the rack bus", cmd_nodes, 1, 0),
	SHELL_CMD_ARG(enumerate, NULL, "Enumerate the rack bus again", cmd_enumerate, 1, 0),
	SHELL_CMD_ARG(node, NULL, "<C3|0x23> identify|reset|bootloader|power-cycle|reboot",
		      cmd_node, 3, 0),
	SHELL_CMD_ARG(events, NULL, "Recent events", cmd_events, 1, 0),
	SHELL_CMD_ARG(shed, NULL, "[order]: rows shed first to last (persistent), e.g. DCBA",
		      cmd_shed, 1, 1),
	SHELL_CMD_ARG(id, NULL, "Rack id, sets the hostname rack-<id>: [<id>] (persistent)",
		      cmd_id, 1, 1),
	SHELL_CMD_ARG(access, NULL, "Admin key: [claim] confirms a claim, [reset] forgets the key",
		      cmd_access, 1, 1),
	SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(hub, &sub_hub, "hw-testing-rack power hub", NULL);
