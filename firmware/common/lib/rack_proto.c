/*
 * Rack bus protocol: frame encoding and decoding (docs/rack-protocol.md).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <hwtr/rack_proto.h>

static void put16(uint8_t *p, uint16_t v)
{
	p[0] = v & 0xFF;
	p[1] = v >> 8;
}

static uint16_t get16(const uint8_t *p)
{
	return (uint16_t)(p[0] | (p[1] << 8));
}

static void frame(struct rack_frame *f, uint16_t id, uint8_t len)
{
	memset(f, 0, sizeof(*f));
	f->id = id;
	f->len = len;
}

/* The frame's function if it is a per-node one from/to a valid node */
static int node_frame(const struct rack_frame *f, enum rack_fn fn, uint8_t min_len, uint8_t *node)
{
	uint8_t id = RACK_ID_LOW(f->id);

	if (RACK_ID_FN(f->id) != fn || f->len < min_len || !RACK_NODE_VALID(id)) {
		return -1;
	}
	*node = id;

	return 0;
}

uint8_t rack_mac_hash(const uint8_t mac[6])
{
	return (mac[3] ^ mac[4] ^ mac[5] ^ (mac[2] >> 1)) & 0x7F;
}

const char *rack_node_name(uint8_t node, char buf[4])
{
	unsigned int pos = RACK_NODE_POS(node);

	if (!RACK_NODE_VALID(node)) {
		buf[0] = '-';
		buf[1] = '\0';
		return buf;
	}
	buf[0] = (char)('A' + RACK_NODE_ROW(node));
	if (pos >= 10) {
		buf[1] = '1';
		buf[2] = (char)('0' + pos - 10);
		buf[3] = '\0';
	} else {
		buf[1] = (char)('0' + pos);
		buf[2] = '\0';
	}

	return buf;
}

void rack_enc_bcast(struct rack_frame *f, enum rack_bcast_op op)
{
	frame(f, RACK_ID_BCAST, 2);
	f->data[0] = op;
}

void rack_enc_req(struct rack_frame *f, const uint8_t mac[6], enum rack_req_why why)
{
	frame(f, RACK_CAN_ID(RACK_FN_REQ, rack_mac_hash(mac)), 8);
	memcpy(f->data, mac, 6);
	f->data[6] = RACK_PROTO_VERSION;
	f->data[7] = why;
}

void rack_enc_assign(struct rack_frame *f, const uint8_t mac[6], uint8_t node)
{
	frame(f, RACK_ID_ENUM_ASSIGN, 8);
	memcpy(f->data, mac, 6);
	f->data[6] = node;
	f->data[7] = RACK_PROTO_VERSION;
}

void rack_enc_hello(struct rack_frame *f, uint8_t node, const uint8_t mac[6])
{
	frame(f, RACK_CAN_ID(RACK_FN_ENUM, node), 8);
	memcpy(f->data, mac, 6);
	f->data[6] = RACK_PROTO_VERSION;
}

void rack_enc_status(struct rack_frame *f, uint8_t node, const struct rack_status *s)
{
	frame(f, RACK_CAN_ID(RACK_FN_STATUS, node), 8);
	f->data[0] = s->flags;
	f->data[1] = s->counter;
	put16(&f->data[2], s->dut_mv);
	put16(&f->data[4], s->dut_ma);
	f->data[6] = s->flags2;
}

void rack_enc_info(struct rack_frame *f, uint8_t node, const struct rack_info *info)
{
	frame(f, RACK_CAN_ID(RACK_FN_INFO, node), 8);
	memcpy(f->data, info->ipv4, 4);
	f->data[4] = info->proto;
	memcpy(&f->data[5], info->fw, 3);
}

void rack_enc_alert(struct rack_frame *f, uint8_t node, const struct rack_alert *a)
{
	frame(f, RACK_CAN_ID(RACK_FN_ALERT, node), 3);
	f->data[0] = a->code;
	put16(&f->data[1], a->dut_ma);
}

void rack_enc_cmd(struct rack_frame *f, uint8_t node, const struct rack_cmd *c)
{
	uint8_t n = c->nargs > 6 ? 6 : c->nargs;

	frame(f, RACK_CAN_ID(RACK_FN_CMD, node), 2 + n);
	f->data[0] = c->op;
	f->data[1] = c->seq;
	memcpy(&f->data[2], c->arg, n);
}

void rack_enc_reply(struct rack_frame *f, uint8_t node, const struct rack_reply *r)
{
	frame(f, RACK_CAN_ID(RACK_FN_REPLY, node), 5);
	f->data[0] = r->op;
	f->data[1] = r->seq;
	f->data[2] = r->result;
	put16(&f->data[3], r->err);
}

void rack_enc_hub(struct rack_frame *f, const struct rack_hub_state *h)
{
	frame(f, RACK_ID_RACK, 8);
	f->data[0] = h->flags;
	put16(&f->data[1], h->mv);
	put16(&f->data[3], h->ma);
	f->data[5] = h->rows_on;
	f->data[6] = h->rows_fault;
	f->data[7] = h->counter;
}

int rack_dec_bcast(const struct rack_frame *f, enum rack_bcast_op *op)
{
	if (f->id != RACK_ID_BCAST || f->len < 1) {
		return -1;
	}
	*op = (enum rack_bcast_op)f->data[0];

	return 0;
}

int rack_dec_req(const struct rack_frame *f, uint8_t mac[6], uint8_t *proto, uint8_t *why)
{
	if (RACK_ID_FN(f->id) != RACK_FN_REQ || f->len < 8) {
		return -1;
	}
	memcpy(mac, f->data, 6);
	*proto = f->data[6];
	*why = f->data[7];

	return 0;
}

int rack_dec_assign(const struct rack_frame *f, uint8_t mac[6], uint8_t *node)
{
	if (f->id != RACK_ID_ENUM_ASSIGN || f->len < 7) {
		return -1;
	}
	memcpy(mac, f->data, 6);
	*node = f->data[6];

	return 0;
}

int rack_dec_hello(const struct rack_frame *f, uint8_t *node, uint8_t mac[6], uint8_t *proto)
{
	if (f->id == RACK_ID_ENUM_ASSIGN || node_frame(f, RACK_FN_ENUM, 7, node) != 0) {
		return -1;
	}
	memcpy(mac, f->data, 6);
	*proto = f->data[6];

	return 0;
}

int rack_dec_status(const struct rack_frame *f, uint8_t *node, struct rack_status *s)
{
	if (node_frame(f, RACK_FN_STATUS, 7, node) != 0) {
		return -1;
	}
	s->flags = f->data[0];
	s->counter = f->data[1];
	s->dut_mv = get16(&f->data[2]);
	s->dut_ma = get16(&f->data[4]);
	s->flags2 = f->data[6];

	return 0;
}

int rack_dec_info(const struct rack_frame *f, uint8_t *node, struct rack_info *info)
{
	if (node_frame(f, RACK_FN_INFO, 8, node) != 0) {
		return -1;
	}
	memcpy(info->ipv4, f->data, 4);
	info->proto = f->data[4];
	memcpy(info->fw, &f->data[5], 3);

	return 0;
}

int rack_dec_alert(const struct rack_frame *f, uint8_t *node, struct rack_alert *a)
{
	if (node_frame(f, RACK_FN_ALERT, 3, node) != 0) {
		return -1;
	}
	a->code = f->data[0];
	a->dut_ma = get16(&f->data[1]);

	return 0;
}

int rack_dec_cmd(const struct rack_frame *f, uint8_t *node, struct rack_cmd *c)
{
	if (node_frame(f, RACK_FN_CMD, 2, node) != 0) {
		return -1;
	}
	c->op = f->data[0];
	c->seq = f->data[1];
	c->nargs = f->len - 2;
	memset(c->arg, 0, sizeof(c->arg));
	memcpy(c->arg, &f->data[2], c->nargs);

	return 0;
}

int rack_dec_reply(const struct rack_frame *f, uint8_t *node, struct rack_reply *r)
{
	if (node_frame(f, RACK_FN_REPLY, 3, node) != 0) {
		return -1;
	}
	r->op = f->data[0];
	r->seq = f->data[1];
	r->result = f->data[2];
	r->err = f->len >= 5 ? get16(&f->data[3]) : 0;

	return 0;
}

int rack_dec_hub(const struct rack_frame *f, struct rack_hub_state *h)
{
	if (f->id != RACK_ID_RACK || f->len < 8) {
		return -1;
	}
	h->flags = f->data[0];
	h->mv = get16(&f->data[1]);
	h->ma = get16(&f->data[3]);
	h->rows_on = f->data[5];
	h->rows_fault = f->data[6];
	h->counter = f->data[7];

	return 0;
}
