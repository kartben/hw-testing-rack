/*
 * Rack bus protocol: the frames the power hub and the bay nodes exchange on
 * the rack's CAN bus.  The specification is docs/rack-protocol.md; keep the
 * two in step (RACK_PROTO_VERSION).
 *
 * Plain C, no Zephyr dependency, so that the host tests use it as is.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HWTR_RACK_PROTO_H_
#define HWTR_RACK_PROTO_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RACK_PROTO_VERSION 1
#define RACK_BITRATE       250000

/* --- Addresses -------------------------------------------------------------- */

#define RACK_ROWS      4  /* A-D */
#define RACK_POSITIONS 15 /* 1-15 per row */
#define RACK_HUB_ID    0x00

/* node id = row x 16 + position: C3 -> 0x23 */
#define RACK_NODE_ID(row, pos) ((uint8_t)(((row) << 4) | (pos)))
#define RACK_NODE_ROW(id)      ((id) >> 4)
#define RACK_NODE_POS(id)      ((id) & 0x0F)
#define RACK_NODE_VALID(id)                                                                        \
	(RACK_NODE_ROW(id) < RACK_ROWS && RACK_NODE_POS(id) >= 1 && RACK_NODE_POS(id) <= RACK_POSITIONS)

/* --- Identifiers: function << 7 | node id ----------------------------------- */

enum rack_fn {
	RACK_FN_BCAST = 0x0,  /* 0x000: hub -> all */
	RACK_FN_ALERT = 0x1,  /* 0x080 + id: node -> hub, DUT fault */
	RACK_FN_CMD = 0x2,    /* 0x100 + id: hub -> node */
	RACK_FN_REPLY = 0x3,  /* 0x180 + id: node -> hub */
	RACK_FN_RACK = 0x4,   /* 0x200: hub -> all, every second */
	RACK_FN_STATUS = 0x5, /* 0x280 + id: node -> hub, every second */
	RACK_FN_INFO = 0x6,   /* 0x300 + id: node -> hub */
	RACK_FN_REQ = 0xE,    /* 0x700 + MAC hash: ENUM_REQ, node without an address */
	RACK_FN_ENUM = 0xF,   /* 0x780 + id: HELLO; 0x7F0: ENUM_ASSIGN */
};

#define RACK_CAN_ID(fn, low)  ((uint16_t)(((fn) << 7) | ((low) & 0x7F)))
#define RACK_ID_FN(can_id)    (((can_id) >> 7) & 0x0F)
#define RACK_ID_LOW(can_id)   ((can_id) & 0x7F)
#define RACK_ID_BCAST         RACK_CAN_ID(RACK_FN_BCAST, 0)
#define RACK_ID_RACK          RACK_CAN_ID(RACK_FN_RACK, 0)
#define RACK_ID_ENUM_ASSIGN   0x7F0

/* --- Frames ----------------------------------------------------------------- */

/* A classic CAN frame with an 11-bit identifier; the glue converts it */
struct rack_frame {
	uint16_t id;
	uint8_t len;
	uint8_t data[8];
};

enum rack_bcast_op {
	RACK_BCAST_ADDR_RESET = 0x01, /* forget your address, POS_OUT low */
	RACK_BCAST_ENUM_POLL = 0x02,  /* POS_IN high and no address: ask now */
};

enum rack_req_why {
	RACK_WHY_POS = 0,   /* POS_IN rose */
	RACK_WHY_BOOT = 1,  /* POS_IN already high at boot */
	RACK_WHY_POLL = 2,  /* ENUM_POLL */
	RACK_WHY_RETRY = 3, /* no answer yet */
};

/* STATUS byte 0 */
#define RACK_ST_DUT_ON     (1U << 0)
#define RACK_ST_DUT_FAULT  (1U << 1)
#define RACK_ST_SERVICE    (1U << 2)
#define RACK_ST_CLASSIC    (1U << 3)
#define RACK_ST_USB_DEVICE (1U << 4)
#define RACK_ST_USBIP      (1U << 5)
#define RACK_ST_NET        (1U << 6)
#define RACK_ST_CONSOLE    (1U << 7)
/* STATUS byte 6 */
#define RACK_ST2_RESERVED  (1U << 0)
#define RACK_ST2_CAMERA    (1U << 1) /* a camera on the bay */
#define RACK_ST2_CAMERA_ON (1U << 2) /* someone is watching it */

#define RACK_NO_READING 0xFFFF

struct rack_status {
	uint8_t flags;
	uint8_t counter;
	uint16_t dut_mv;
	uint16_t dut_ma;
	uint8_t flags2;
};

struct rack_info {
	uint8_t ipv4[4];
	uint8_t proto;
	uint8_t fw[3];
};

enum rack_alert_code {
	RACK_ALERT_DUT_LIMIT = 0x01, /* DUT in current limit */
	RACK_ALERT_DUT_OFF = 0x02,   /* DUT switched off by a fault */
};

struct rack_alert {
	uint8_t code;
	uint16_t dut_ma;
};

enum rack_cmd_op {
	RACK_CMD_POWER = 0x01,    /* arg0: 0 off, 1 on, 2 cycle; arg1-2: off time, ms */
	RACK_CMD_RESET = 0x02,    /* arg0-1: pulse, ms */
	RACK_CMD_BOOTLOADER = 0x03,
	RACK_CMD_IDENTIFY = 0x04, /* arg0: seconds, 0 stops */
	RACK_CMD_REBOOT = 0x05,
	RACK_CMD_INFO = 0x06,
};

enum rack_result {
	RACK_OK = 0,
	RACK_UNKNOWN = 1,
	RACK_REFUSED = 2,
	RACK_FAILED = 3,
};

struct rack_cmd {
	uint8_t op;
	uint8_t seq;
	uint8_t nargs;
	uint8_t arg[6];
};

struct rack_reply {
	uint8_t op;
	uint8_t seq;
	uint8_t result;
	uint16_t err;
};

/* RACK byte 0 */
#define RACK_HUB_CONTRACT (1U << 0)
#define RACK_HUB_EPR      (1U << 1)
#define RACK_HUB_SHED     (1U << 2)

struct rack_hub_state {
	uint8_t flags;
	uint16_t mv;
	uint16_t ma;
	uint8_t rows_on;
	uint8_t rows_fault;
	uint8_t counter;
};

/* --- Encoding (node is the sender's or the addressee's id) ------------------ */

void rack_enc_bcast(struct rack_frame *f, enum rack_bcast_op op);
void rack_enc_req(struct rack_frame *f, const uint8_t mac[6], enum rack_req_why why);
void rack_enc_assign(struct rack_frame *f, const uint8_t mac[6], uint8_t node);
void rack_enc_hello(struct rack_frame *f, uint8_t node, const uint8_t mac[6]);
void rack_enc_status(struct rack_frame *f, uint8_t node, const struct rack_status *s);
void rack_enc_info(struct rack_frame *f, uint8_t node, const struct rack_info *info);
void rack_enc_alert(struct rack_frame *f, uint8_t node, const struct rack_alert *a);
void rack_enc_cmd(struct rack_frame *f, uint8_t node, const struct rack_cmd *c);
void rack_enc_reply(struct rack_frame *f, uint8_t node, const struct rack_reply *r);
void rack_enc_hub(struct rack_frame *f, const struct rack_hub_state *h);

/* --- Decoding: 0 on success, -1 if the frame is not that message ----------- */

int rack_dec_bcast(const struct rack_frame *f, enum rack_bcast_op *op);
int rack_dec_req(const struct rack_frame *f, uint8_t mac[6], uint8_t *proto, uint8_t *why);
int rack_dec_assign(const struct rack_frame *f, uint8_t mac[6], uint8_t *node);
int rack_dec_hello(const struct rack_frame *f, uint8_t *node, uint8_t mac[6], uint8_t *proto);
int rack_dec_status(const struct rack_frame *f, uint8_t *node, struct rack_status *s);
int rack_dec_info(const struct rack_frame *f, uint8_t *node, struct rack_info *info);
int rack_dec_alert(const struct rack_frame *f, uint8_t *node, struct rack_alert *a);
int rack_dec_cmd(const struct rack_frame *f, uint8_t *node, struct rack_cmd *c);
int rack_dec_reply(const struct rack_frame *f, uint8_t *node, struct rack_reply *r);
int rack_dec_hub(const struct rack_frame *f, struct rack_hub_state *h);

/* "C3" for 0x23 (buf: 4 bytes) */
const char *rack_node_name(uint8_t node, char buf[4]);

/* The low 7 bits of an ENUM_REQ identifier, from the MAC */
uint8_t rack_mac_hash(const uint8_t mac[6]);

#ifdef __cplusplus
}
#endif

#endif /* HWTR_RACK_PROTO_H_ */
