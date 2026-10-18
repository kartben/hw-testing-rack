/*
 * Rack bus, the hub's side: enumeration over the POS tokens, the node
 * table, commands with retries (docs/rack-protocol.md).
 *
 * Plain C driven by the application: it feeds received frames to
 * rack_hub_rx(), calls rack_hub_tick() every few milliseconds, and provides
 * the I/O (send a frame, drive a row's POS).  Times are milliseconds from
 * any free-running clock (wrap-safe).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HWTR_RACK_HUB_H_
#define HWTR_RACK_HUB_H_

#include <hwtr/rack_proto.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RACK_HUB_RESET_MS    20   /* after ADDR_RESET, before the first POS */
#define RACK_HUB_REQ_MS      200  /* wait for a position's ENUM_REQ (twice, with a poll) */
#define RACK_HUB_HELLO_MS    50   /* wait for the HELLO after ENUM_ASSIGN */
#define RACK_HUB_TRIES       3    /* ENUM_ASSIGNs per position */
#define RACK_HUB_LOST_MS     3500 /* no STATUS for that long: lost */
#define RACK_HUB_DEBOUNCE_MS 200  /* unsolicited ENUM_REQ -> re-enumeration */
#define RACK_HUB_CMD_MS      100  /* CMD retry period */
#define RACK_HUB_CMD_TRIES   3
#define RACK_HUB_CMD_SLOTS   8

enum rack_node_state {
	RACK_NODE_NONE = 0,     /* no node known there */
	RACK_NODE_OK,           /* enumerated, sending STATUS */
	RACK_NODE_LOST,         /* enumerated, silent for RACK_HUB_LOST_MS */
	RACK_NODE_FAILED,       /* asked, never confirmed its address: the row stops here */
	RACK_NODE_INCOMPATIBLE, /* speaks a newer protocol version */
};

struct rack_hub_node {
	uint8_t state;
	uint8_t mac[6];
	uint8_t proto;
	bool have_status;
	bool have_info;
	uint32_t seen_ms;
	struct rack_status status;
	struct rack_info info;
};

enum rack_hub_event {
	RACK_HUB_EV_ENUM_START,  /* node: 0 */
	RACK_HUB_EV_ENUM_DONE,   /* node: number of nodes found */
	RACK_HUB_EV_NODE_FOUND,
	RACK_HUB_EV_NODE_FAILED,
	RACK_HUB_EV_NODE_LOST,
	RACK_HUB_EV_NODE_BACK,
	RACK_HUB_EV_UNSOLICITED, /* a node asked outside an enumeration (arg: its MAC) */
	RACK_HUB_EV_ALERT,       /* arg: const struct rack_alert * */
	RACK_HUB_EV_REPLY,       /* arg: const struct rack_reply * */
	RACK_HUB_EV_NO_REPLY,    /* arg: const struct rack_cmd * */
};

struct rack_hub_ops {
	int (*send)(void *ctx, const struct rack_frame *f);
	void (*set_pos)(void *ctx, int row, bool high);
	/* optional */
	void (*event)(void *ctx, enum rack_hub_event ev, uint8_t node, const void *arg);
};

enum rack_hub_phase {
	RACK_HUB_IDLE,
	RACK_HUB_RESET,
	RACK_HUB_WAIT_REQ,
	RACK_HUB_WAIT_HELLO,
};

struct rack_hub_cmd_slot {
	bool busy;
	uint8_t node;
	uint8_t tries;
	uint32_t deadline;
	struct rack_cmd cmd;
};

struct rack_hub {
	const struct rack_hub_ops *ops;
	void *ctx;
	struct rack_hub_node nodes[RACK_ROWS][RACK_POSITIONS + 1]; /* [row][1..15] */
	uint8_t count[RACK_ROWS];
	uint8_t rows;       /* rows being / last enumerated */
	enum rack_hub_phase phase;
	int row;
	int pos;
	int tries;
	bool polled;
	uint8_t mac[6];     /* the node being given an address */
	uint32_t deadline;
	bool reenum;
	uint32_t reenum_at;
	uint32_t enumerated_ms;
	uint32_t enumerations;
	uint8_t seq;
	struct rack_hub_cmd_slot cmds[RACK_HUB_CMD_SLOTS];
};

void rack_hub_init(struct rack_hub *h, const struct rack_hub_ops *ops, void *ctx);

/*
 * Forget every address and enumerate the rows in the mask (bit 0 = A, the
 * powered ones) one after the other, settle_ms from now (the nodes' boot
 * after a row comes on).  POS stays low on the other rows.
 */
void rack_hub_enumerate(struct rack_hub *h, uint8_t rows, uint32_t settle_ms, uint32_t now);

/* A row went off: its nodes are gone, its POS goes low */
void rack_hub_row_off(struct rack_hub *h, int row);

void rack_hub_rx(struct rack_hub *h, const struct rack_frame *f, uint32_t now);
void rack_hub_tick(struct rack_hub *h, uint32_t now);

/* Send a CMD (retried until a REPLY); returns its sequence number, or -1 if all slots are busy */
int rack_hub_cmd(struct rack_hub *h, uint8_t node, uint8_t op, const uint8_t *args, uint8_t nargs,
		 uint32_t now);

/* NULL unless the id is a valid node id */
struct rack_hub_node *rack_hub_node(struct rack_hub *h, uint8_t id);

/* Nodes in state OK or LOST */
int rack_hub_count(const struct rack_hub *h);

#ifdef __cplusplus
}
#endif

#endif /* HWTR_RACK_HUB_H_ */
