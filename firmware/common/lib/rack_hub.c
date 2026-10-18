/*
 * Rack bus, the hub's side (docs/rack-protocol.md › Enumeration).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <hwtr/rack_hub.h>

#define AFTER(now, t) ((int32_t)((now) - (t)) >= 0)

static void emit(struct rack_hub *h, enum rack_hub_event ev, uint8_t node, const void *arg)
{
	if (h->ops->event != NULL) {
		h->ops->event(h->ctx, ev, node, arg);
	}
}

static void send(struct rack_hub *h, const struct rack_frame *f)
{
	(void)h->ops->send(h->ctx, f);
}

void rack_hub_init(struct rack_hub *h, const struct rack_hub_ops *ops, void *ctx)
{
	memset(h, 0, sizeof(*h));
	h->ops = ops;
	h->ctx = ctx;
	for (int r = 0; r < RACK_ROWS; r++) {
		ops->set_pos(ctx, r, false);
	}
}

struct rack_hub_node *rack_hub_node(struct rack_hub *h, uint8_t id)
{
	return RACK_NODE_VALID(id) ? &h->nodes[RACK_NODE_ROW(id)][RACK_NODE_POS(id)] : NULL;
}

int rack_hub_count(const struct rack_hub *h)
{
	int n = 0;

	for (int r = 0; r < RACK_ROWS; r++) {
		for (int p = 1; p <= RACK_POSITIONS; p++) {
			n += h->nodes[r][p].state == RACK_NODE_OK || h->nodes[r][p].state == RACK_NODE_LOST;
		}
	}

	return n;
}

static void forget_row(struct rack_hub *h, int row)
{
	memset(h->nodes[row], 0, sizeof(h->nodes[row]));
	h->count[row] = 0;
}

void rack_hub_row_off(struct rack_hub *h, int row)
{
	h->ops->set_pos(h->ctx, row, false);
	forget_row(h, row);
	h->rows &= ~(1U << row);
	/* Enumerating that row right now: move on */
	if (h->phase != RACK_HUB_IDLE && h->phase != RACK_HUB_RESET && h->row == row) {
		h->deadline = 0;
		h->phase = RACK_HUB_WAIT_REQ;
		h->polled = true;
	}
}

void rack_hub_enumerate(struct rack_hub *h, uint8_t rows, uint32_t settle_ms, uint32_t now)
{
	struct rack_frame f;

	for (int r = 0; r < RACK_ROWS; r++) {
		h->ops->set_pos(h->ctx, r, false);
		forget_row(h, r);
	}
	rack_enc_bcast(&f, RACK_BCAST_ADDR_RESET);
	send(h, &f);

	h->rows = rows;
	h->row = -1;
	h->reenum = false;
	h->phase = RACK_HUB_RESET;
	h->deadline = now + (settle_ms > RACK_HUB_RESET_MS ? settle_ms : RACK_HUB_RESET_MS);
	h->enumerations++;
	emit(h, RACK_HUB_EV_ENUM_START, 0, NULL);
}

static void next_row(struct rack_hub *h, uint32_t now)
{
	do {
		h->row++;
	} while (h->row < RACK_ROWS && !(h->rows & (1U << h->row)));

	if (h->row >= RACK_ROWS) {
		/* Done: POS up on every enumerated row, so a node that reboots can ask */
		for (int r = 0; r < RACK_ROWS; r++) {
			if (h->rows & (1U << r)) {
				h->ops->set_pos(h->ctx, r, true);
			}
		}
		h->phase = RACK_HUB_IDLE;
		h->enumerated_ms = now;
		emit(h, RACK_HUB_EV_ENUM_DONE, (uint8_t)rack_hub_count(h), NULL);
		return;
	}

	/* One row at a time: two unaddressed nodes never ask at once */
	for (int r = 0; r < RACK_ROWS; r++) {
		h->ops->set_pos(h->ctx, r, r == h->row);
	}
	h->pos = 1;
	h->polled = false;
	h->phase = RACK_HUB_WAIT_REQ;
	h->deadline = now + RACK_HUB_REQ_MS;
}

static void assign(struct rack_hub *h, uint32_t now)
{
	struct rack_frame f;

	rack_enc_assign(&f, h->mac, RACK_NODE_ID(h->row, h->pos));
	send(h, &f);
	h->phase = RACK_HUB_WAIT_HELLO;
	h->deadline = now + RACK_HUB_HELLO_MS;
}

static void on_req(struct rack_hub *h, const uint8_t mac[6], uint32_t now)
{
	if (h->phase == RACK_HUB_WAIT_REQ && h->pos <= RACK_POSITIONS) {
		memcpy(h->mac, mac, 6);
		h->tries = 1;
		assign(h, now);
	} else if (h->phase == RACK_HUB_IDLE) {
		/* A node rebooted, or one was plugged in: enumerate everything again */
		if (!h->reenum) {
			h->reenum = true;
			h->reenum_at = now + RACK_HUB_DEBOUNCE_MS;
		}
		emit(h, RACK_HUB_EV_UNSOLICITED, 0, mac);
	}
	/* RESET, WAIT_HELLO: the node asks again in a second */
}

static void on_hello(struct rack_hub *h, uint8_t node, const uint8_t mac[6], uint8_t proto,
		     uint32_t now)
{
	struct rack_hub_node *n;

	if (h->phase != RACK_HUB_WAIT_HELLO || node != RACK_NODE_ID(h->row, h->pos) ||
	    memcmp(mac, h->mac, 6) != 0) {
		return;
	}

	n = rack_hub_node(h, node);
	memset(n, 0, sizeof(*n));
	memcpy(n->mac, mac, 6);
	n->proto = proto;
	n->seen_ms = now;
	n->state = proto > RACK_PROTO_VERSION ? RACK_NODE_INCOMPATIBLE : RACK_NODE_OK;
	h->count[h->row] = (uint8_t)h->pos;
	emit(h, RACK_HUB_EV_NODE_FOUND, node, NULL);

	h->pos++;
	if (h->pos > RACK_POSITIONS) {
		next_row(h, now);
		return;
	}
	h->polled = false;
	h->phase = RACK_HUB_WAIT_REQ;
	h->deadline = now + RACK_HUB_REQ_MS;
}

static void seen(struct rack_hub *h, struct rack_hub_node *n, uint8_t node, uint32_t now)
{
	n->seen_ms = now;
	if (n->state == RACK_NODE_LOST) {
		n->state = RACK_NODE_OK;
		emit(h, RACK_HUB_EV_NODE_BACK, node, NULL);
	}
}

static bool known(struct rack_hub *h, struct rack_hub_node *n, uint32_t now)
{
	if (n->state == RACK_NODE_NONE || n->state == RACK_NODE_FAILED) {
		/* An address we did not give (the hub rebooted, a node kept it) */
		if (h->phase == RACK_HUB_IDLE && !h->reenum) {
			h->reenum = true;
			h->reenum_at = now + RACK_HUB_DEBOUNCE_MS;
		}
		return false;
	}

	return true;
}

static void on_reply(struct rack_hub *h, uint8_t node, const struct rack_reply *r)
{
	for (int i = 0; i < RACK_HUB_CMD_SLOTS; i++) {
		struct rack_hub_cmd_slot *s = &h->cmds[i];

		if (s->busy && s->node == node && s->cmd.seq == r->seq && s->cmd.op == r->op) {
			s->busy = false;
			emit(h, RACK_HUB_EV_REPLY, node, r);
			return;
		}
	}
}

void rack_hub_rx(struct rack_hub *h, const struct rack_frame *f, uint32_t now)
{
	struct rack_hub_node *n;
	uint8_t mac[6], node, proto, why;
	struct rack_status st;
	struct rack_info info;
	struct rack_alert alert;
	struct rack_reply reply;

	if (rack_dec_req(f, mac, &proto, &why) == 0) {
		on_req(h, mac, now);
	} else if (rack_dec_hello(f, &node, mac, &proto) == 0) {
		on_hello(h, node, mac, proto, now);
	} else if (rack_dec_status(f, &node, &st) == 0) {
		n = rack_hub_node(h, node);
		if (known(h, n, now)) {
			n->status = st;
			n->have_status = true;
			seen(h, n, node, now);
		}
	} else if (rack_dec_info(f, &node, &info) == 0) {
		n = rack_hub_node(h, node);
		if (known(h, n, now)) {
			n->info = info;
			n->have_info = true;
			seen(h, n, node, now);
		}
	} else if (rack_dec_alert(f, &node, &alert) == 0) {
		n = rack_hub_node(h, node);
		if (known(h, n, now)) {
			seen(h, n, node, now);
			emit(h, RACK_HUB_EV_ALERT, node, &alert);
		}
	} else if (rack_dec_reply(f, &node, &reply) == 0) {
		on_reply(h, node, &reply);
	}
}

static void tick_enum(struct rack_hub *h, uint32_t now)
{
	struct rack_frame f;

	if (h->phase == RACK_HUB_IDLE || !AFTER(now, h->deadline)) {
		return;
	}

	switch (h->phase) {
	case RACK_HUB_RESET:
		next_row(h, now);
		break;
	case RACK_HUB_WAIT_REQ:
		if (!h->polled) {
			/* Last call for a slow node, then the row ends here */
			rack_enc_bcast(&f, RACK_BCAST_ENUM_POLL);
			send(h, &f);
			h->polled = true;
			h->deadline = now + RACK_HUB_REQ_MS;
		} else {
			next_row(h, now);
		}
		break;
	case RACK_HUB_WAIT_HELLO:
		if (h->tries < RACK_HUB_TRIES) {
			h->tries++;
			assign(h, now);
		} else {
			uint8_t node = RACK_NODE_ID(h->row, h->pos);
			struct rack_hub_node *n = rack_hub_node(h, node);

			memset(n, 0, sizeof(*n));
			memcpy(n->mac, h->mac, 6);
			n->state = RACK_NODE_FAILED;
			emit(h, RACK_HUB_EV_NODE_FAILED, node, NULL);
			next_row(h, now);
		}
		break;
	default:
		break;
	}
}

void rack_hub_tick(struct rack_hub *h, uint32_t now)
{
	tick_enum(h, now);

	if (h->reenum && h->phase == RACK_HUB_IDLE && AFTER(now, h->reenum_at)) {
		rack_hub_enumerate(h, h->rows, 0, now);
	}

	for (int r = 0; r < RACK_ROWS; r++) {
		for (int p = 1; p <= RACK_POSITIONS; p++) {
			struct rack_hub_node *n = &h->nodes[r][p];

			if (n->state == RACK_NODE_OK && AFTER(now, n->seen_ms + RACK_HUB_LOST_MS)) {
				n->state = RACK_NODE_LOST;
				emit(h, RACK_HUB_EV_NODE_LOST, RACK_NODE_ID(r, p), NULL);
			}
		}
	}

	for (int i = 0; i < RACK_HUB_CMD_SLOTS; i++) {
		struct rack_hub_cmd_slot *s = &h->cmds[i];
		struct rack_frame f;

		if (!s->busy || !AFTER(now, s->deadline)) {
			continue;
		}
		if (s->tries < RACK_HUB_CMD_TRIES) {
			/* Same sequence number: the node answers again without acting again */
			rack_enc_cmd(&f, s->node, &s->cmd);
			send(h, &f);
			s->tries++;
			s->deadline = now + RACK_HUB_CMD_MS;
		} else {
			s->busy = false;
			emit(h, RACK_HUB_EV_NO_REPLY, s->node, &s->cmd);
		}
	}
}

int rack_hub_cmd(struct rack_hub *h, uint8_t node, uint8_t op, const uint8_t *args, uint8_t nargs,
		 uint32_t now)
{
	struct rack_frame f;

	if (!RACK_NODE_VALID(node) || nargs > 6) {
		return -1;
	}
	for (int i = 0; i < RACK_HUB_CMD_SLOTS; i++) {
		struct rack_hub_cmd_slot *s = &h->cmds[i];

		if (s->busy) {
			continue;
		}
		memset(s, 0, sizeof(*s));
		s->busy = true;
		s->node = node;
		s->tries = 1;
		s->deadline = now + RACK_HUB_CMD_MS;
		s->cmd.op = op;
		s->cmd.seq = ++h->seq;
		s->cmd.nargs = nargs;
		if (nargs > 0) {
			memcpy(s->cmd.arg, args, nargs);
		}
		rack_enc_cmd(&f, node, &s->cmd);
		send(h, &f);
		return s->cmd.seq;
	}

	return -1;
}
