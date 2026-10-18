/*
 * Rack bus, a node's side (docs/rack-protocol.md › Enumeration).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <hwtr/rack_node.h>

#define AFTER(now, t) ((int32_t)((now) - (t)) >= 0)

static void send(struct rack_node *n, const struct rack_frame *f)
{
	(void)n->ops->send(n->ctx, f);
}

static void request(struct rack_node *n, enum rack_req_why why, uint32_t now)
{
	struct rack_frame f;

	rack_enc_req(&f, n->mac, why);
	send(n, &f);
	n->asked = true;
	n->booting = false;
	n->next_req = now + RACK_NODE_RETRY_MS + n->jitter;
}

static void drop_address(struct rack_node *n)
{
	n->ops->set_pos_out(n->ctx, false);
	if (n->id != 0) {
		n->id = 0;
		n->ops->address(n->ctx, 0);
	}
}

void rack_node_init(struct rack_node *n, const struct rack_node_ops *ops, void *ctx,
		    const uint8_t mac[6], uint32_t now)
{
	memset(n, 0, sizeof(*n));
	n->ops = ops;
	n->ctx = ctx;
	memcpy(n->mac, mac, 6);
	n->booting = true;
	n->armed = true;
	n->pos_since = now;
	/* Two nodes retrying at once drift apart */
	n->jitter = (uint32_t)(rack_mac_hash(mac) * 7U) % 250U;
	ops->set_pos_out(ctx, false);
}

static void send_status(struct rack_node *n, uint32_t now)
{
	struct rack_status st = {.dut_mv = RACK_NO_READING, .dut_ma = RACK_NO_READING};
	struct rack_frame f;

	n->ops->status(n->ctx, &st);
	st.counter = n->counter++;
	rack_enc_status(&f, n->id, &st);
	send(n, &f);
	n->next_status = now + RACK_NODE_STATUS_MS;
}

static void send_info(struct rack_node *n, uint32_t now)
{
	struct rack_info info = {0};
	struct rack_frame f;

	n->ops->info(n->ctx, &info);
	info.proto = RACK_PROTO_VERSION;
	rack_enc_info(&f, n->id, &info);
	send(n, &f);
	n->next_info = now + RACK_NODE_INFO_MS;
}

static void on_cmd(struct rack_node *n, const struct rack_cmd *c)
{
	struct rack_frame f;

	/* A retry of the last command: answer again, don't act again */
	if (!n->have_reply || n->reply.seq != c->seq || n->reply.op != c->op) {
		n->reply.op = c->op;
		n->reply.seq = c->seq;
		n->reply.err = 0;
		n->reply.result = n->ops->command(n->ctx, c, &n->reply.err);
		n->have_reply = true;
	}
	rack_enc_reply(&f, n->id, &n->reply);
	send(n, &f);
}

void rack_node_rx(struct rack_node *n, const struct rack_frame *f, uint32_t now)
{
	enum rack_bcast_op op;
	struct rack_cmd cmd;
	struct rack_frame out;
	uint8_t mac[6], node;

	if (rack_dec_bcast(f, &op) == 0) {
		if (op == RACK_BCAST_ADDR_RESET) {
			drop_address(n);
			/* POS_IN must go low before this node asks again */
			n->armed = false;
			n->asked = false;
		} else if (op == RACK_BCAST_ENUM_POLL && n->id == 0 && n->ops->pos_in(n->ctx)) {
			request(n, RACK_WHY_POLL, now);
		}
	} else if (rack_dec_assign(f, mac, &node) == 0) {
		if (memcmp(mac, n->mac, 6) != 0 || !RACK_NODE_VALID(node)) {
			return;
		}
		/* Also when already addressed: the hub did not get the HELLO */
		if (n->id != node) {
			n->id = node;
			n->have_reply = false;
			n->ops->address(n->ctx, node);
		}
		rack_enc_hello(&out, node, n->mac);
		send(n, &out);
		/* The next node in the row may ask now */
		n->ops->set_pos_out(n->ctx, true);
		n->next_status = now;
		n->next_info = now + 50;
	} else if (n->id != 0 && rack_dec_cmd(f, &node, &cmd) == 0) {
		if (node == n->id) {
			on_cmd(n, &cmd);
		}
	} else if (rack_dec_hub(f, &n->hub) == 0) {
		n->have_hub = true;
		if (n->ops->hub != NULL) {
			n->ops->hub(n->ctx, &n->hub);
		}
	}
}

void rack_node_tick(struct rack_node *n, uint32_t now)
{
	bool pos = n->ops->pos_in(n->ctx);

	if (pos != n->pos) {
		n->pos = pos;
		n->pos_since = now;
	}

	if (n->id == 0) {
		if (!pos) {
			n->armed = true;
			n->asked = false;
		} else if (n->armed && AFTER(now, n->pos_since + RACK_NODE_DEBOUNCE_MS)) {
			if (!n->asked) {
				request(n, n->booting ? RACK_WHY_BOOT : RACK_WHY_POS, now);
			} else if (AFTER(now, n->next_req)) {
				request(n, RACK_WHY_RETRY, now);
			}
		}
		return;
	}

	if (AFTER(now, n->next_status)) {
		send_status(n, now);
	}
	if (AFTER(now, n->next_info)) {
		send_info(n, now);
	}
}

void rack_node_info_changed(struct rack_node *n, uint32_t now)
{
	n->next_info = now;
}

void rack_node_alert(struct rack_node *n, const struct rack_alert *a)
{
	struct rack_frame f;

	if (n->id == 0) {
		return;
	}
	rack_enc_alert(&f, n->id, a);
	send(n, &f);
}
