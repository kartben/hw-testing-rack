/*
 * Rack bus client (docs/rack-protocol.md): the node's side of the CAN bus
 * and of the POS addressing token, on firmware/common's rack_node.
 *
 * One thread runs it: frames from the TWAI's message queue, a tick every
 * 5 ms (POS_IN, heartbeat, DUT fault edges for ALERT).  The hub's commands
 * act on the DUT like the shell does; while the bay is reserved (access
 * lease) the ones that disturb the board are refused.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <ctype.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/can.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/sys/reboot.h>
#include <zephyr/logging/log.h>
#include <zephyr/app_version.h>

#include <hwtr/net.h>
#include <hwtr/rack_node.h>

#include "bay.h"

LOG_MODULE_REGISTER(rack, CONFIG_BAY_LOG_LEVEL);

#define RACK_NODE DT_NODELABEL(rack_bus)

#if DT_NODE_HAS_STATUS_OKAY(RACK_NODE)

#define TICK_MS       5
#define HUB_STALE_MS  3000
#define STACK_SIZE    2048
#define PRIORITY      K_PRIO_PREEMPT(7)

static const struct device *const can = DEVICE_DT_GET(DT_PHANDLE(RACK_NODE, can));
static const struct gpio_dt_spec pos_in = GPIO_DT_SPEC_GET(RACK_NODE, pos_in_gpios);
static const struct gpio_dt_spec pos_out = GPIO_DT_SPEC_GET(RACK_NODE, pos_out_gpios);

CAN_MSGQ_DEFINE(rx_msgq, 8);

static struct rack_node node;
static K_MUTEX_DEFINE(node_lock);
static uint8_t node_id;
static char position[4] = "";
static int64_t identify_until;
static int64_t hub_seen;
static struct rack_hub_state hub;
static bool info_pending;

static void reboot_handler(struct k_work *work)
{
	ARG_UNUSED(work);
	sys_reboot(SYS_REBOOT_COLD);
}

static K_WORK_DELAYABLE_DEFINE(reboot_work, reboot_handler);

/* --- rack_node I/O ---------------------------------------------------------- */

static int bus_send(void *ctx, const struct rack_frame *f)
{
	struct can_frame cf = {.id = f->id, .dlc = f->len};

	ARG_UNUSED(ctx);
	memcpy(cf.data, f->data, f->len);

	return can_send(can, &cf, K_MSEC(10), NULL, NULL);
}

static bool get_pos_in(void *ctx)
{
	ARG_UNUSED(ctx);
	return gpio_pin_get_dt(&pos_in) > 0;
}

static void set_pos_out(void *ctx, bool high)
{
	ARG_UNUSED(ctx);
	(void)gpio_pin_set_dt(&pos_out, high);
}

static void on_address(void *ctx, uint8_t id)
{
	char lower[sizeof(position)];

	ARG_UNUSED(ctx);

	node_id = id;
	if (id == 0) {
		position[0] = '\0';
		LOG_INF("rack position lost");
		return;
	}
	rack_node_name(id, position);
	LOG_INF("rack position %s (node 0x%02x)", position, id);

	/* Without a bay id the node is named after its place: bay-c3.local */
	for (size_t i = 0; i < sizeof(lower); i++) {
		lower[i] = (char)tolower((unsigned char)position[i]);
	}
	(void)hwtr_net_fallback_id(lower);
}

static void fill_status(void *ctx, struct rack_status *st)
{
	struct dut_power_reading r;
	struct aux_stats aux;
	struct acl_lease lease;
	uint32_t remaining;

	ARG_UNUSED(ctx);

	st->flags = (dut_power_get() ? RACK_ST_DUT_ON : 0) |
		    (dut_fault_active() || dut_fault_latched() ? RACK_ST_DUT_FAULT : 0) |
		    (usb_mux_path() == BAY_PATH_SERVICE ? RACK_ST_SERVICE : 0) |
		    (usb_mux_path() == BAY_PATH_CLASSIC ? RACK_ST_CLASSIC : 0) |
		    (usb_host_device_count() > 0 ? RACK_ST_USB_DEVICE : 0) |
		    (usb_host_usbip_sessions() > 0 ? RACK_ST_USBIP : 0) |
		    (bay_net_connected() ? RACK_ST_NET : 0);
	aux_stats_get(&aux);
	if (aux.web_clients > 0 || aux.rfc2217_client || aux.raw_client) {
		st->flags |= RACK_ST_CONSOLE;
	}
	st->flags2 = access_lease_get(&lease, &remaining) ? RACK_ST2_RESERVED : 0;

	if (dut_power_read(&r) == 0) {
		st->dut_mv = (uint16_t)CLAMP(r.bus_mv, 0, 0xFFFE);
		st->dut_ma = (uint16_t)CLAMP(r.current_ma, 0, 0xFFFE);
	}
}

static void fill_info(void *ctx, struct rack_info *info)
{
	struct net_in_addr addr;

	ARG_UNUSED(ctx);

	if (bay_net_connected() && net_addr_pton(NET_AF_INET, bay_net_addr(), &addr) == 0) {
		memcpy(info->ipv4, &addr, 4);
	}
	info->fw[0] = APP_VERSION_MAJOR;
	info->fw[1] = APP_VERSION_MINOR;
	info->fw[2] = APP_PATCHLEVEL;
}

static uint16_t ms_arg(const struct rack_cmd *c, int i)
{
	return (uint16_t)(c->arg[i] | (c->arg[i + 1] << 8));
}

static uint8_t command(void *ctx, const struct rack_cmd *c, uint16_t *err)
{
	struct acl_lease lease;
	uint32_t remaining;
	bool disturbing = c->op != RACK_CMD_IDENTIFY && c->op != RACK_CMD_INFO;
	int ret = 0;

	ARG_UNUSED(ctx);

	if (disturbing && access_lease_get(&lease, &remaining)) {
		LOG_WRN("hub command 0x%02x refused: the bay is reserved", c->op);
		return RACK_REFUSED;
	}

	switch (c->op) {
	case RACK_CMD_POWER:
		if (c->arg[0] == 2) {
			uint16_t ms = ms_arg(c, 1);

			ret = dut_power_cycle(K_MSEC(ms ? ms : CONFIG_BAY_POWER_CYCLE_MS));
		} else if (c->arg[0] <= 1) {
			ret = dut_power_set(c->arg[0] == 1);
		} else {
			return RACK_UNKNOWN;
		}
		break;
	case RACK_CMD_RESET: {
		uint16_t ms = ms_arg(c, 0);

		ret = dut_reset_pulse(K_MSEC(ms ? ms : CONFIG_BAY_RESET_PULSE_MS));
		break;
	}
	case RACK_CMD_BOOTLOADER:
		ret = dut_enter_bootloader();
		break;
	case RACK_CMD_IDENTIFY:
		identify_until = c->arg[0] ? k_uptime_get() + c->arg[0] * MSEC_PER_SEC : 0;
		break;
	case RACK_CMD_REBOOT:
		LOG_WRN("reboot requested by the hub");
		k_work_schedule(&reboot_work, K_MSEC(200));
		break;
	case RACK_CMD_INFO:
		info_pending = true;
		break;
	default:
		return RACK_UNKNOWN;
	}

	LOG_INF("hub command 0x%02x: %d", c->op, ret);
	if (ret != 0) {
		*err = (uint16_t)-ret;
		return RACK_FAILED;
	}

	return RACK_OK;
}

static void on_hub(void *ctx, const struct rack_hub_state *state)
{
	ARG_UNUSED(ctx);
	hub = *state;
	hub_seen = k_uptime_get();
}

static const struct rack_node_ops ops = {
	.send = bus_send,
	.pos_in = get_pos_in,
	.set_pos_out = set_pos_out,
	.address = on_address,
	.status = fill_status,
	.info = fill_info,
	.command = command,
	.hub = on_hub,
};

/* --- Thread --------------------------------------------------------------- */

static void alerts(void)
{
	static bool was_limit, was_off;
	bool limit = dut_fault_active();
	bool off = dut_fault_latched();
	struct dut_power_reading r = {0};
	struct rack_alert a = {0};

	if (limit && !was_limit) {
		a.code = RACK_ALERT_DUT_LIMIT;
	} else if (off && !was_off) {
		a.code = RACK_ALERT_DUT_OFF;
	}
	was_limit = limit;
	was_off = off;

	if (a.code != 0) {
		(void)dut_power_read(&r);
		a.dut_ma = (uint16_t)CLAMP(r.current_ma, 0, 0xFFFE);
		rack_node_alert(&node, &a);
	}
}

static void rack_thread(void *p1, void *p2, void *p3)
{
	struct can_frame cf;

	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	while (true) {
		uint32_t now;

		if (k_msgq_get(&rx_msgq, &cf, K_MSEC(TICK_MS)) == 0 && !(cf.flags & CAN_FRAME_IDE)) {
			struct rack_frame f = {.id = (uint16_t)cf.id, .len = MIN(cf.dlc, 8)};

			memcpy(f.data, cf.data, f.len);
			k_mutex_lock(&node_lock, K_FOREVER);
			rack_node_rx(&node, &f, k_uptime_get_32());
			k_mutex_unlock(&node_lock);
		}

		now = k_uptime_get_32();
		k_mutex_lock(&node_lock, K_FOREVER);
		if (info_pending) {
			info_pending = false;
			rack_node_info_changed(&node, now);
		}
		rack_node_tick(&node, now);
		alerts();
		k_mutex_unlock(&node_lock);
	}
}

K_THREAD_STACK_DEFINE(rack_stack, STACK_SIZE);
static struct k_thread rack_thread_data;

int bay_rack_init(void)
{
	const struct can_filter all = {.id = 0, .mask = 0, .flags = 0};
	uint8_t mac[6];
	int ret;

	if (!device_is_ready(can) || !gpio_is_ready_dt(&pos_in) || !gpio_is_ready_dt(&pos_out)) {
		return -ENODEV;
	}

	/* POS_OUT low from reset: the next node waits for this one */
	ret = gpio_pin_configure_dt(&pos_out, GPIO_OUTPUT_INACTIVE);
	if (ret == 0) {
		ret = gpio_pin_configure_dt(&pos_in, GPIO_INPUT);
	}
	if (ret != 0) {
		return ret;
	}

	if (hwtr_net_mac(mac) != 0) {
		LOG_ERR("no MAC address for the rack bus");
		return -ENODEV;
	}

	ret = can_add_rx_filter_msgq(can, &rx_msgq, &all);
	if (ret < 0) {
		return ret;
	}
	ret = can_start(can);
	if (ret != 0 && ret != -EALREADY) {
		return ret;
	}

	rack_node_init(&node, &ops, NULL, mac, k_uptime_get_32());
	k_thread_create(&rack_thread_data, rack_stack, K_THREAD_STACK_SIZEOF(rack_stack),
			rack_thread, NULL, NULL, NULL, PRIORITY, 0, K_NO_WAIT);
	k_thread_name_set(&rack_thread_data, "rack");

	return 0;
}

uint8_t bay_rack_id(void)
{
	return node_id;
}

const char *bay_rack_position(void)
{
	return position;
}

bool bay_rack_hub(struct rack_hub_state *st)
{
	if (hub_seen == 0 || k_uptime_get() - hub_seen > HUB_STALE_MS) {
		return false;
	}
	*st = hub;

	return true;
}

void bay_rack_info_changed(void)
{
	info_pending = true;
}

bool bay_rack_identifying(void)
{
	return identify_until != 0 && k_uptime_get() < identify_until;
}

#else /* no rack-bus node: a board without the row cable */

int bay_rack_init(void)
{
	return -ENOTSUP;
}

uint8_t bay_rack_id(void)
{
	return 0;
}

const char *bay_rack_position(void)
{
	return "";
}

bool bay_rack_hub(struct rack_hub_state *st)
{
	ARG_UNUSED(st);
	return false;
}

void bay_rack_info_changed(void)
{
}

bool bay_rack_identifying(void)
{
	return false;
}

#endif
