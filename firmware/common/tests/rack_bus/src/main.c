/*
 * The rack bus protocol on a simulated rack: one hub, nodes in rows, every
 * frame delivered to every other participant, the POS token wired from the
 * hub through each row's nodes (docs/rack-protocol.md).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/ztest.h>

#include <hwtr/rack_hub.h>
#include <hwtr/rack_node.h>

#define MAX_NODES 16
#define QUEUE_LEN 256
#define HUB       (-1)

struct sim_node {
	bool present;  /* plugged in and powered */
	bool firmware; /* runs the rack bus (else: holds POS_OUT low, says nothing) */
	bool mute;     /* its frames get lost */
	int row;
	int pos;
	bool pos_out;
	struct rack_node rn;
	int executed;
	uint8_t id_seen;
};

static struct {
	uint32_t now;
	bool hub_pos[RACK_ROWS];
	struct rack_hub hub;
	struct sim_node nodes[MAX_NODES];
	struct {
		int from;
		struct rack_frame f;
	} queue[QUEUE_LEN];
	int head, tail;
	int drop_next_hello;
	int drop_next_reply;
	int events[RACK_HUB_EV_NO_REPLY + 1];
} sim;

static void enqueue(int from, const struct rack_frame *f)
{
	zassert_true(((sim.tail + 1) % QUEUE_LEN) != sim.head, "bus queue overflow");
	sim.queue[sim.tail].from = from;
	sim.queue[sim.tail].f = *f;
	sim.tail = (sim.tail + 1) % QUEUE_LEN;
}

/* --- Hub I/O ------------------------------------------------------------ */

static int hub_send(void *ctx, const struct rack_frame *f)
{
	ARG_UNUSED(ctx);
	enqueue(HUB, f);
	return 0;
}

static void hub_set_pos(void *ctx, int row, bool high)
{
	ARG_UNUSED(ctx);
	sim.hub_pos[row] = high;
}

static void hub_event(void *ctx, enum rack_hub_event ev, uint8_t node, const void *arg)
{
	ARG_UNUSED(ctx);
	ARG_UNUSED(node);
	ARG_UNUSED(arg);
	sim.events[ev]++;
}

static const struct rack_hub_ops hub_ops = {
	.send = hub_send, .set_pos = hub_set_pos, .event = hub_event,
};

/* --- Node I/O ------------------------------------------------------------ */

static struct sim_node *at(int row, int pos)
{
	for (int i = 0; i < MAX_NODES; i++) {
		if (sim.nodes[i].present && sim.nodes[i].row == row && sim.nodes[i].pos == pos) {
			return &sim.nodes[i];
		}
	}
	return NULL;
}

static int node_send(void *ctx, const struct rack_frame *f)
{
	struct sim_node *n = ctx;
	uint8_t node, mac[6], proto;
	struct rack_reply r;

	if (n->mute) {
		return 0;
	}
	if (sim.drop_next_hello > 0 && rack_dec_hello(f, &node, mac, &proto) == 0) {
		sim.drop_next_hello--;
		return 0;
	}
	if (sim.drop_next_reply > 0 && rack_dec_reply(f, &node, &r) == 0) {
		sim.drop_next_reply--;
		return 0;
	}
	enqueue((int)(n - sim.nodes), f);
	return 0;
}

static bool node_pos_in(void *ctx)
{
	struct sim_node *n = ctx;
	struct sim_node *prev;

	if (n->pos == 1) {
		return sim.hub_pos[n->row];
	}
	prev = at(n->row, n->pos - 1);
	return prev != NULL && prev->pos_out;
}

static void node_set_pos_out(void *ctx, bool high)
{
	struct sim_node *n = ctx;

	n->pos_out = high;
}

static void node_address(void *ctx, uint8_t id)
{
	struct sim_node *n = ctx;

	n->id_seen = id;
}

static void node_status(void *ctx, struct rack_status *st)
{
	ARG_UNUSED(ctx);
	st->flags = RACK_ST_DUT_ON | RACK_ST_NET;
	st->dut_mv = 5050;
	st->dut_ma = 120;
}

static void node_info(void *ctx, struct rack_info *info)
{
	struct sim_node *n = ctx;

	info->ipv4[0] = 192;
	info->ipv4[1] = 168;
	info->ipv4[2] = 1;
	info->ipv4[3] = (uint8_t)(100 + (n - sim.nodes));
	info->fw[0] = 0;
	info->fw[1] = 5;
}

static uint8_t node_command(void *ctx, const struct rack_cmd *cmd, uint16_t *err)
{
	struct sim_node *n = ctx;

	ARG_UNUSED(err);
	if (cmd->op != RACK_CMD_IDENTIFY && cmd->op != RACK_CMD_POWER) {
		return RACK_UNKNOWN;
	}
	n->executed++;
	return RACK_OK;
}

static const struct rack_node_ops node_ops = {
	.send = node_send, .pos_in = node_pos_in, .set_pos_out = node_set_pos_out,
	.address = node_address, .status = node_status, .info = node_info,
	.command = node_command,
};

/* --- Simulation ---------------------------------------------------------- */

static struct sim_node *plug(int row, int pos, bool firmware)
{
	for (int i = 0; i < MAX_NODES; i++) {
		struct sim_node *n = &sim.nodes[i];

		if (!n->present) {
			uint8_t mac[6] = {0x34, 0xB7, 0xDA, (uint8_t)row, (uint8_t)pos, (uint8_t)(i * 37)};

			memset(n, 0, sizeof(*n));
			n->present = true;
			n->firmware = firmware;
			n->row = row;
			n->pos = pos;
			if (firmware) {
				rack_node_init(&n->rn, &node_ops, n, mac, sim.now);
			}
			return n;
		}
	}
	zassert_unreachable("too many nodes");
	return NULL;
}

/* A node reboots: firmware restarts, POS_OUT low, no address */
static void reboot(struct sim_node *n)
{
	uint8_t mac[6];

	memcpy(mac, n->rn.mac, 6);
	n->pos_out = false;
	n->id_seen = 0;
	rack_node_init(&n->rn, &node_ops, n, mac, sim.now);
}

static void deliver(void)
{
	while (sim.head != sim.tail) {
		int from = sim.queue[sim.head].from;
		struct rack_frame f = sim.queue[sim.head].f;

		sim.head = (sim.head + 1) % QUEUE_LEN;
		if (from != HUB) {
			rack_hub_rx(&sim.hub, &f, sim.now);
		}
		for (int i = 0; i < MAX_NODES; i++) {
			if (i != from && sim.nodes[i].present && sim.nodes[i].firmware) {
				rack_node_rx(&sim.nodes[i].rn, &f, sim.now);
			}
		}
	}
}

static void run(uint32_t ms)
{
	for (uint32_t t = 0; t < ms; t++) {
		sim.now++;
		rack_hub_tick(&sim.hub, sim.now);
		deliver();
		for (int i = 0; i < MAX_NODES; i++) {
			if (sim.nodes[i].present && sim.nodes[i].firmware) {
				rack_node_tick(&sim.nodes[i].rn, sim.now);
			}
		}
		deliver();
	}
}

static uint8_t rows_mask(void)
{
	uint8_t mask = 0;

	for (int i = 0; i < MAX_NODES; i++) {
		if (sim.nodes[i].present) {
			mask |= 1U << sim.nodes[i].row;
		}
	}
	return mask;
}

static void before(void *fixture)
{
	ARG_UNUSED(fixture);
	memset(&sim, 0, sizeof(sim));
	sim.now = 100000;
	rack_hub_init(&sim.hub, &hub_ops, NULL);
}

static void assert_ids(void)
{
	for (int i = 0; i < MAX_NODES; i++) {
		struct sim_node *n = &sim.nodes[i];

		if (n->present && n->firmware) {
			zassert_equal(n->rn.id, RACK_NODE_ID(n->row, n->pos), "node %c%d has id 0x%02x",
				      'A' + n->row, n->pos, n->rn.id);
			zassert_true(n->pos_out, "node %c%d holds POS_OUT low", 'A' + n->row, n->pos);
		}
	}
}

/* --- Tests ---------------------------------------------------------------- */

ZTEST(rack_bus, test_frames)
{
	const uint8_t mac[6] = {1, 2, 3, 4, 5, 6};
	struct rack_status st = {.flags = 0xA5, .counter = 7, .dut_mv = 5012, .dut_ma = 1499,
				 .flags2 = RACK_ST2_RESERVED | RACK_ST2_CAMERA};
	struct rack_status st2;
	struct rack_info info;
	struct rack_cmd c ={.op = RACK_CMD_POWER, .seq = 9, .nargs = 3, .arg = {2, 0xE8, 0x03}};
	struct rack_cmd c2;
	struct rack_frame f;
	uint8_t node, mac2[6], proto, why;
	char name[4];

	rack_enc_status(&f, 0x23, &st);
	zassert_equal(f.id, 0x280 + 0x23);
	zassert_ok(rack_dec_status(&f, &node, &st2));
	zassert_equal(node, 0x23);
	zassert_equal(st2.flags, st.flags);
	zassert_equal(st2.counter, st.counter);
	zassert_equal(st2.dut_mv, st.dut_mv);
	zassert_equal(st2.dut_ma, st.dut_ma);
	zassert_equal(st2.flags2, st.flags2);
	zassert_equal(rack_dec_info(&f, &node, &info), -1, "a STATUS is not an INFO");

	rack_enc_cmd(&f, 0x05, &c);
	zassert_equal(f.id, 0x105);
	zassert_equal(f.len, 5);
	zassert_ok(rack_dec_cmd(&f, &node, &c2));
	zassert_equal(c2.arg[1] | (c2.arg[2] << 8), 1000);

	rack_enc_req(&f, mac, RACK_WHY_BOOT);
	zassert_equal(f.id & 0x780, 0x700, "ENUM_REQ in 0x700-0x77F");
	zassert_ok(rack_dec_req(&f, mac2, &proto, &why));
	zassert_mem_equal(mac, mac2, 6);
	zassert_equal(why, RACK_WHY_BOOT);
	zassert_equal(proto, RACK_PROTO_VERSION);

	rack_enc_assign(&f, mac, 0x31);
	zassert_equal(rack_dec_hello(&f, &node, mac2, &proto), -1, "ASSIGN is not a HELLO");

	zassert_str_equal(rack_node_name(0x23, name), "C3");
	zassert_str_equal(rack_node_name(0x0C, name), "A12");
	zassert_str_equal(rack_node_name(0x40, name), "-");
}

ZTEST(rack_bus, test_enumerate)
{
	plug(0, 1, true);
	plug(0, 2, true);
	plug(0, 3, true);
	plug(1, 1, true);
	plug(1, 2, true);
	plug(3, 1, true);

	rack_hub_enumerate(&sim.hub, rows_mask(), 0, sim.now);
	run(2000);

	zassert_equal(sim.hub.phase, RACK_HUB_IDLE);
	zassert_equal(rack_hub_count(&sim.hub), 6);
	zassert_equal(sim.hub.count[0], 3);
	zassert_equal(sim.hub.count[1], 2);
	zassert_equal(sim.hub.count[2], 0);
	zassert_equal(sim.hub.count[3], 1);
	assert_ids();
	zassert_true(sim.hub_pos[0] && sim.hub_pos[1] && sim.hub_pos[3], "POS up on the rows");

	/* STATUS and INFO arrive */
	run(1500);
	zassert_true(rack_hub_node(&sim.hub, 0x12)->have_status);
	zassert_true(rack_hub_node(&sim.hub, 0x12)->have_info);
	zassert_equal(rack_hub_node(&sim.hub, 0x31)->status.dut_ma, 120);
}

ZTEST(rack_bus, test_node_reboot)
{
	struct sim_node *b1;

	plug(0, 1, true);
	b1 = plug(1, 1, true);
	plug(1, 2, true);
	rack_hub_enumerate(&sim.hub, rows_mask(), 0, sim.now);
	run(2000);
	assert_ids();

	/* B1 restarts: it sees POS_IN high at boot and asks; the hub re-enumerates */
	reboot(b1);
	run(3000);

	zassert_equal(sim.events[RACK_HUB_EV_UNSOLICITED] > 0, true);
	zassert_equal(sim.hub.enumerations, 2);
	zassert_equal(rack_hub_count(&sim.hub), 3);
	assert_ids();
}

ZTEST(rack_bus, test_late_node)
{
	struct sim_node *a2;

	plug(0, 1, true);
	a2 = plug(0, 2, true);
	/* A2 boots slowly: absent during the enumeration */
	a2->firmware = false;
	rack_hub_enumerate(&sim.hub, rows_mask(), 0, sim.now);
	run(2000);
	zassert_equal(sim.hub.count[0], 1);

	/* It comes up later, sees POS_IN high (A1 is addressed), asks: re-enumeration */
	a2->firmware = true;
	reboot(a2);
	run(3000);
	zassert_equal(sim.hub.count[0], 2);
	assert_ids();
}

ZTEST(rack_bus, test_dead_node)
{
	struct sim_node *a3;

	plug(0, 1, true);
	plug(0, 2, false); /* no rack bus firmware: holds POS_OUT low */
	a3 = plug(0, 3, true);
	plug(1, 1, true);
	rack_hub_enumerate(&sim.hub, rows_mask(), 0, sim.now);
	run(2000);

	zassert_equal(sim.hub.count[0], 1, "row A stops at the dead node");
	zassert_equal(a3->rn.id, 0);
	zassert_equal(sim.hub.count[1], 1, "row B is not affected");
}

ZTEST(rack_bus, test_lost_node)
{
	struct sim_node *a2;

	plug(0, 1, true);
	a2 = plug(0, 2, true);
	rack_hub_enumerate(&sim.hub, rows_mask(), 0, sim.now);
	run(2000);

	a2->mute = true;
	run(RACK_HUB_LOST_MS + 1500);
	zassert_equal(rack_hub_node(&sim.hub, 0x02)->state, RACK_NODE_LOST);
	zassert_equal(sim.events[RACK_HUB_EV_NODE_LOST], 1);

	a2->mute = false;
	run(1500);
	zassert_equal(rack_hub_node(&sim.hub, 0x02)->state, RACK_NODE_OK);
	zassert_equal(sim.events[RACK_HUB_EV_NODE_BACK], 1);
	zassert_equal(sim.hub.enumerations, 1, "no re-enumeration for a lost node");
}

ZTEST(rack_bus, test_hello_lost)
{
	plug(0, 1, true);
	plug(0, 2, true);
	sim.drop_next_hello = 1;
	rack_hub_enumerate(&sim.hub, rows_mask(), 0, sim.now);
	run(2000);

	zassert_equal(sim.hub.count[0], 2, "ENUM_ASSIGN was sent again");
	assert_ids();
}

ZTEST(rack_bus, test_cmd_retry)
{
	struct sim_node *b1;
	uint8_t secs = 5;
	int seq;

	plug(0, 1, true);
	b1 = plug(1, 1, true);
	rack_hub_enumerate(&sim.hub, rows_mask(), 0, sim.now);
	run(2000);

	sim.drop_next_reply = 1;
	seq = rack_hub_cmd(&sim.hub, 0x11, RACK_CMD_IDENTIFY, &secs, 1, sim.now);
	zassert_true(seq > 0);
	run(500);

	zassert_equal(b1->executed, 1, "a retried command runs once");
	zassert_equal(sim.events[RACK_HUB_EV_REPLY], 1);
	zassert_equal(sim.events[RACK_HUB_EV_NO_REPLY], 0);

	/* Nobody there: no reply after the retries */
	seq = rack_hub_cmd(&sim.hub, 0x25, RACK_CMD_IDENTIFY, &secs, 1, sim.now);
	run(500);
	zassert_equal(sim.events[RACK_HUB_EV_NO_REPLY], 1);
}

ZTEST(rack_bus, test_row_off)
{
	plug(0, 1, true);
	plug(1, 1, true);
	rack_hub_enumerate(&sim.hub, rows_mask(), 0, sim.now);
	run(2000);

	/* Row B's eFuse goes off: its nodes disappear, POS goes low */
	rack_hub_row_off(&sim.hub, 1);
	sim.nodes[1].present = false;
	run(5000);
	zassert_false(sim.hub_pos[1]);
	zassert_equal(rack_hub_count(&sim.hub), 1);
	zassert_equal(sim.events[RACK_HUB_EV_NODE_LOST], 0, "a row turned off is not a lost node");
}

ZTEST_SUITE(rack_bus, NULL, NULL, before, NULL, NULL);
