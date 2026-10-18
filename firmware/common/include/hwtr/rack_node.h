/*
 * Rack bus, a node's side: the POS token, the address, the heartbeat and
 * the hub's commands (docs/rack-protocol.md).
 *
 * Plain C driven by the application: it feeds received frames to
 * rack_node_rx(), calls rack_node_tick() every few milliseconds (POS_IN is
 * sampled there), and provides the I/O and the node's state.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HWTR_RACK_NODE_H_
#define HWTR_RACK_NODE_H_

#include <hwtr/rack_proto.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RACK_NODE_DEBOUNCE_MS 2     /* POS_IN must stay high this long */
#define RACK_NODE_RETRY_MS    1000  /* ENUM_REQ repeat, plus a MAC-derived jitter */
#define RACK_NODE_STATUS_MS   1000
#define RACK_NODE_INFO_MS     10000

struct rack_node_ops {
	int (*send)(void *ctx, const struct rack_frame *f);
	bool (*pos_in)(void *ctx);
	void (*set_pos_out)(void *ctx, bool high);
	/* The node got an address (0: it lost it) */
	void (*address)(void *ctx, uint8_t node);
	/* Fill flags, dut_mv, dut_ma, flags2 (the counter is set here) */
	void (*status)(void *ctx, struct rack_status *st);
	/* Fill ipv4 and fw (proto is set here) */
	void (*info)(void *ctx, struct rack_info *info);
	/* Execute a command: RACK_OK, RACK_UNKNOWN, RACK_REFUSED or RACK_FAILED (*err: errno) */
	uint8_t (*command)(void *ctx, const struct rack_cmd *cmd, uint16_t *err);
	/* optional: the hub's RACK frame */
	void (*hub)(void *ctx, const struct rack_hub_state *state);
};

struct rack_node {
	const struct rack_node_ops *ops;
	void *ctx;
	uint8_t mac[6];
	uint8_t id;          /* 0: no address */
	bool booting;        /* no request sent since boot */
	bool armed;          /* POS_IN was low since the address was lost (or since boot) */
	bool asked;          /* ENUM_REQ sent since POS_IN rose */
	bool pos;            /* POS_IN, last sample */
	uint32_t pos_since;
	uint32_t jitter;
	uint32_t next_req;
	uint32_t next_status;
	uint32_t next_info;
	uint8_t counter;
	bool have_reply;
	struct rack_reply reply; /* the last one, sent again for a repeated sequence */
	bool have_hub;
	struct rack_hub_state hub;
};

void rack_node_init(struct rack_node *n, const struct rack_node_ops *ops, void *ctx,
		    const uint8_t mac[6], uint32_t now);
void rack_node_rx(struct rack_node *n, const struct rack_frame *f, uint32_t now);
void rack_node_tick(struct rack_node *n, uint32_t now);

/* Something INFO carries changed (IP address): send it at the next tick */
void rack_node_info_changed(struct rack_node *n, uint32_t now);

/* Report a DUT fault (only once the node has an address) */
void rack_node_alert(struct rack_node *n, const struct rack_alert *a);

#ifdef __cplusplus
}
#endif

#endif /* HWTR_RACK_NODE_H_ */
