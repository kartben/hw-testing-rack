/*
 * Rack bus master (docs/rack-protocol.md): the TWAI on the star bus, the
 * POS tokens through rows.c, and firmware/common's rack_hub for the
 * enumeration and the node table.  One thread: frames from the TWAI's
 * message queue, a tick every 5 ms, the RACK frame every second.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/can.h>
#include <zephyr/logging/log.h>

#include "hub.h"

LOG_MODULE_REGISTER(bus, CONFIG_HUB_LOG_LEVEL);

#define HUB_NODE   DT_NODELABEL(power_hub)
#define TICK_MS    5
#define RACK_MS    1000
#define STACK_SIZE 3072
#define PRIORITY   K_PRIO_PREEMPT(7)

static const struct device *const can = DEVICE_DT_GET(DT_PHANDLE(HUB_NODE, can));

CAN_MSGQ_DEFINE(rx_msgq, 32);

static struct rack_hub hub;
static K_MUTEX_DEFINE(lock);
static uint32_t rx_count, tx_count, tx_errors, bus_offs;
static uint32_t rx_fps, rx_last;
static int64_t enumerated_ms;
static uint8_t rack_counter;
static struct can_state_change_callback state_cb;

/* Requests from other threads, run by the bus thread */
static atomic_t enum_req;
static uint32_t enum_settle;

static int bus_send(void *ctx, const struct rack_frame *f)
{
	struct can_frame cf = {.id = f->id, .dlc = f->len};
	int ret;

	ARG_UNUSED(ctx);
	memcpy(cf.data, f->data, f->len);

	ret = can_send(can, &cf, K_MSEC(10), NULL, NULL);
	if (ret == 0) {
		tx_count++;
	} else {
		tx_errors++;
	}

	return ret;
}

static void set_pos(void *ctx, int row, bool high)
{
	ARG_UNUSED(ctx);
	rows_pos(row, high);
}

static void on_event(void *ctx, enum rack_hub_event ev, uint8_t node, const void *arg)
{
	char name[4];

	ARG_UNUSED(ctx);
	rack_node_name(node, name);

	switch (ev) {
	case RACK_HUB_EV_ENUM_DONE:
		enumerated_ms = k_uptime_get();
		hub_event(HUB_EV_CAN, "enumeration: %u node(s)", node);
		break;
	case RACK_HUB_EV_NODE_FAILED:
		hub_event(HUB_EV_CAN, "node %s did not confirm its address: row %c stops there",
			  name, name[0]);
		break;
	case RACK_HUB_EV_NODE_LOST:
		hub_event(HUB_EV_CAN, "node %s (0x%02x) lost: no STATUS for %u s", name, node,
			  RACK_HUB_LOST_MS / 1000);
		break;
	case RACK_HUB_EV_NODE_BACK:
		hub_event(HUB_EV_CAN, "node %s (0x%02x) back", name, node);
		break;
	case RACK_HUB_EV_UNSOLICITED:
		LOG_INF("a node asks for an address: re-enumerating");
		break;
	case RACK_HUB_EV_ALERT: {
		const struct rack_alert *a = arg;

		hub_event(HUB_EV_FAULT, "node %s: DUT %s (%u mA)", name,
			  a->code == RACK_ALERT_DUT_OFF ? "switched off by a fault" : "in current limit",
			  a->dut_ma);
		break;
	}
	case RACK_HUB_EV_REPLY: {
		const struct rack_reply *r = arg;
		static const char *const results[] = {"done", "unknown command", "refused", "failed"};

		hub_event(HUB_EV_NODE, "node %s: command 0x%02x %s", name, r->op,
			  r->result < ARRAY_SIZE(results) ? results[r->result] : "?");
		break;
	}
	case RACK_HUB_EV_NO_REPLY: {
		const struct rack_cmd *c = arg;

		hub_event(HUB_EV_NODE, "node %s: no answer to command 0x%02x", name, c->op);
		break;
	}
	default:
		break;
	}
}

static const struct rack_hub_ops ops = {
	.send = bus_send,
	.set_pos = set_pos,
	.event = on_event,
};

static void send_rack(void)
{
	struct hub_pd_status pd;
	struct rack_hub_state s = {0};
	struct rack_frame f;

	pd_status(&pd);
	s.flags = (pd.contract_mv ? RACK_HUB_CONTRACT : 0) |
		  (pd.state == HUB_PD_EPR ? RACK_HUB_EPR : 0) |
		  (rows_shed_mask() ? RACK_HUB_SHED : 0);
	s.mv = (uint16_t)pd.contract_mv;
	s.ma = (uint16_t)pd.contract_ma;
	s.rows_on = rows_on_mask();
	s.rows_fault = rows_fault_mask();
	s.counter = rack_counter++;
	rack_enc_hub(&f, &s);
	(void)bus_send(NULL, &f);
}

static void state_change(const struct device *dev, struct can_state_change_callback *cb,
			 enum can_state state, struct can_bus_err_cnt err)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(cb);
	ARG_UNUSED(err);

	if (state == CAN_STATE_BUS_OFF) {
		bus_offs++;
	}
}

static void bus_thread(void *p1, void *p2, void *p3)
{
	int64_t next_rack = 0, next_rate = 0;
	struct can_frame cf;

	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	while (true) {
		int64_t now64;
		uint32_t now;

		if (k_msgq_get(&rx_msgq, &cf, K_MSEC(TICK_MS)) == 0 && !(cf.flags & CAN_FRAME_IDE)) {
			struct rack_frame f = {.id = (uint16_t)cf.id, .len = MIN(cf.dlc, 8)};

			memcpy(f.data, cf.data, f.len);
			rx_count++;
			k_mutex_lock(&lock, K_FOREVER);
			rack_hub_rx(&hub, &f, k_uptime_get_32());
			k_mutex_unlock(&lock);
		}

		now64 = k_uptime_get();
		now = (uint32_t)now64;
		k_mutex_lock(&lock, K_FOREVER);
		if (atomic_cas(&enum_req, 1, 0)) {
			rack_hub_enumerate(&hub, rows_on_mask(), enum_settle, now);
		}
		rack_hub_tick(&hub, now);
		k_mutex_unlock(&lock);

		if (now64 >= next_rack) {
			send_rack();
			next_rack = now64 + RACK_MS;
		}
		if (now64 >= next_rate) {
			rx_fps = rx_count - rx_last;
			rx_last = rx_count;
			next_rate = now64 + MSEC_PER_SEC;
		}
	}
}

K_THREAD_STACK_DEFINE(bus_stack, STACK_SIZE);
static struct k_thread bus_thread_data;

int bus_init(void)
{
	const struct can_filter all = {.id = 0, .mask = 0, .flags = 0};
	int ret;

	if (!device_is_ready(can)) {
		return -ENODEV;
	}

	rack_hub_init(&hub, &ops, NULL);

	can_init_state_change_callback(&state_cb, state_change);
	ret = can_add_state_change_callback(can, &state_cb);
	if (ret != 0) {
		return ret;
	}
	ret = can_add_rx_filter_msgq(can, &rx_msgq, &all);
	if (ret < 0) {
		return ret;
	}
	/* Also enables the transceiver (STB low) */
	ret = can_start(can);
	if (ret != 0 && ret != -EALREADY) {
		return ret;
	}

	k_thread_create(&bus_thread_data, bus_stack, K_THREAD_STACK_SIZEOF(bus_stack), bus_thread,
			NULL, NULL, NULL, PRIORITY, 0, K_NO_WAIT);
	k_thread_name_set(&bus_thread_data, "rack_bus");

	return 0;
}

void bus_enumerate(uint32_t settle_ms)
{
	enum_settle = settle_ms;
	atomic_set(&enum_req, 1);
}

void bus_row_off(int row)
{
	k_mutex_lock(&lock, K_FOREVER);
	rack_hub_row_off(&hub, row);
	k_mutex_unlock(&lock);
}

int bus_cmd(uint8_t node, uint8_t op, const uint8_t *args, uint8_t nargs)
{
	int seq;

	k_mutex_lock(&lock, K_FOREVER);
	seq = rack_hub_cmd(&hub, node, op, args, nargs, k_uptime_get_32());
	k_mutex_unlock(&lock);

	return seq < 0 ? -EBUSY : seq;
}

void bus_status(struct hub_bus_status *st)
{
	memset(st, 0, sizeof(*st));
	(void)can_get_state(can, &st->state, &st->err);
	st->rx = rx_count;
	st->tx = tx_count;
	st->tx_errors = tx_errors;
	st->bus_off = bus_offs;
	st->rx_fps = rx_fps;
	st->enumerated_ms = enumerated_ms;

	k_mutex_lock(&lock, K_FOREVER);
	st->enumerating = hub.phase != RACK_HUB_IDLE || atomic_get(&enum_req) != 0;
	st->enumerations = hub.enumerations;
	st->nodes = rack_hub_count(&hub);
	for (int r = 0; r < RACK_ROWS; r++) {
		for (int p = 1; p <= RACK_POSITIONS; p++) {
			st->lost += hub.nodes[r][p].state == RACK_NODE_LOST;
		}
	}
	k_mutex_unlock(&lock);
}

int bus_row_nodes(int row, struct rack_hub_node nodes[RACK_POSITIONS + 1])
{
	int n;

	k_mutex_lock(&lock, K_FOREVER);
	memcpy(nodes, hub.nodes[row], sizeof(hub.nodes[row]));
	n = hub.count[row];
	k_mutex_unlock(&lock);

	return n;
}
