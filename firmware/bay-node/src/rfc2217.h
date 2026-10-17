/*
 * Telnet + RFC 2217 (Com Port Control Option) server side.
 *
 * Plain C, no Zephyr dependency: the bay node feeds it the bytes of one TCP
 * connection, it hands back serial data, telnet replies and port settings
 * through callbacks.  The same file is compiled on the host by
 * firmware/bay-node/tests/rfc2217/ to test it against pyserial's client.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef RFC2217_H_
#define RFC2217_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* RFC 2217 parity and stop-size codes */
enum rfc2217_parity {
	RFC2217_PARITY_NONE = 1,
	RFC2217_PARITY_ODD = 2,
	RFC2217_PARITY_EVEN = 3,
	RFC2217_PARITY_MARK = 4,
	RFC2217_PARITY_SPACE = 5,
};

enum rfc2217_stopsize {
	RFC2217_STOP_1 = 1,
	RFC2217_STOP_2 = 2,
	RFC2217_STOP_1_5 = 3,
};

/* SET-CONTROL values handled by the server */
enum rfc2217_control {
	RFC2217_CTL_NO_FLOW = 1,
	RFC2217_CTL_BREAK_ON = 5,
	RFC2217_CTL_BREAK_OFF = 6,
	RFC2217_CTL_DTR_ON = 8,
	RFC2217_CTL_DTR_OFF = 9,
	RFC2217_CTL_RTS_ON = 11,
	RFC2217_CTL_RTS_OFF = 12,
};

struct rfc2217_ops {
	/* Serial data from the client (telnet escapes removed) */
	void (*data)(void *ctx, const uint8_t *buf, size_t len);
	/* Telnet bytes to send back to the client */
	void (*reply)(void *ctx, const uint8_t *buf, size_t len);
	/*
	 * Port settings.  0 queries the current value; otherwise the server
	 * tries to apply it.  Each returns the value now in effect, which is
	 * what the client gets back (a client treats a different value as a
	 * rejection).
	 */
	uint32_t (*baudrate)(void *ctx, uint32_t baud);
	uint8_t (*datasize)(void *ctx, uint8_t bits);
	uint8_t (*parity)(void *ctx, uint8_t parity);
	uint8_t (*stopsize)(void *ctx, uint8_t stop);
	/* SET-CONTROL: flow control, BREAK, DTR, RTS (returns the answer) */
	uint8_t (*control)(void *ctx, uint8_t value);
	/* PURGE-DATA: 1 receive, 2 transmit, 3 both */
	void (*purge)(void *ctx, uint8_t what);
};

struct rfc2217 {
	const struct rfc2217_ops *ops;
	void *ctx;
	uint8_t state;
	uint8_t verb;
	uint8_t sb[16];
	uint8_t sb_len;
	bool sb_overflow;
	bool cr;
	/* Option states, bit per telnet option we handle (see rfc2217.c) */
	uint8_t we;
	uint8_t they;
	uint8_t we_asked;
	uint8_t they_asked;
};

/* Reset the parser and send the server's opening negotiation */
void rfc2217_start(struct rfc2217 *t, const struct rfc2217_ops *ops, void *ctx);

/* Bytes received from the client */
void rfc2217_input(struct rfc2217 *t, const uint8_t *buf, size_t len);

/* Client agreed to the Com Port Control option (RFC 2217 active) */
bool rfc2217_active(const struct rfc2217 *t);

/*
 * Serial data to the client: copy `in` to `out` doubling 0xFF (IAC).
 * Stops when `out` is full; returns the bytes written and stores the input
 * bytes consumed in *consumed.
 */
size_t rfc2217_escape(const uint8_t *in, size_t in_len, uint8_t *out, size_t out_size,
		      size_t *consumed);

#endif /* RFC2217_H_ */
