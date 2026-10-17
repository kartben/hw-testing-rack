/*
 * Telnet + RFC 2217 server side, see rfc2217.h.
 *
 * Negotiation follows pyserial's reference PortManager: the server offers
 * WILL ECHO, WILL SGA, DO BINARY and WILL COM-PORT-OPTION, accepts the
 * client's requests for those options and refuses everything else.  Every
 * Com Port Control request is answered (pyserial waits for the answers).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include "rfc2217.h"

#define IAC  255
#define DONT 254
#define DO   253
#define WONT 252
#define WILL 251
#define SB   250
#define SE   240

#define OPT_BINARY   0
#define OPT_ECHO     1
#define OPT_SGA      3
#define OPT_COM_PORT 44

/* Com Port Control commands, client -> server (server answers + 100) */
#define CPC_SIGNATURE          0
#define CPC_SET_BAUDRATE       1
#define CPC_SET_DATASIZE       2
#define CPC_SET_PARITY         3
#define CPC_SET_STOPSIZE       4
#define CPC_SET_CONTROL        5
#define CPC_NOTIFY_LINESTATE   6
#define CPC_NOTIFY_MODEMSTATE  7
#define CPC_FLOWCONTROL_SUSPEND 8
#define CPC_FLOWCONTROL_RESUME 9
#define CPC_SET_LINESTATE_MASK 10
#define CPC_SET_MODEMSTATE_MASK 11
#define CPC_PURGE_DATA         12
#define CPC_SERVER_OFFSET      100

/* No modem lines on the AUX connector: report CTS, DSR and CD as present */
#define MODEMSTATE_LINES_UP 0xb0

#define SIGNATURE "hw-testing-rack bay node"

enum state {
	S_DATA,
	S_IAC,
	S_VERB,
	S_SB,
	S_SB_IAC,
};

/* One bit per option we know about */
static int opt_bit(uint8_t opt)
{
	switch (opt) {
	case OPT_BINARY:
		return 1 << 0;
	case OPT_ECHO:
		return 1 << 1;
	case OPT_SGA:
		return 1 << 2;
	case OPT_COM_PORT:
		return 1 << 3;
	default:
		return 0;
	}
}

/* Options the server performs itself (WILL) / lets the client perform (DO) */
#define WE_OK   (opt_bit(OPT_BINARY) | opt_bit(OPT_ECHO) | opt_bit(OPT_SGA) | opt_bit(OPT_COM_PORT))
#define THEY_OK (opt_bit(OPT_BINARY) | opt_bit(OPT_SGA) | opt_bit(OPT_COM_PORT))

static void send_option(struct rfc2217 *t, uint8_t verb, uint8_t opt)
{
	const uint8_t msg[3] = {IAC, verb, opt};

	t->ops->reply(t->ctx, msg, sizeof(msg));
}

static void send_sb(struct rfc2217 *t, uint8_t cmd, const uint8_t *val, size_t len)
{
	uint8_t msg[4 + 2 * sizeof(t->sb) + 2];
	size_t n = 0;

	msg[n++] = IAC;
	msg[n++] = SB;
	msg[n++] = OPT_COM_PORT;
	msg[n++] = cmd + CPC_SERVER_OFFSET;
	for (size_t i = 0; i < len && i < sizeof(t->sb); i++) {
		msg[n++] = val[i];
		if (val[i] == IAC) {
			msg[n++] = IAC;
		}
	}
	msg[n++] = IAC;
	msg[n++] = SE;

	t->ops->reply(t->ctx, msg, n);
}

static void send_sb_byte(struct rfc2217 *t, uint8_t cmd, uint8_t val)
{
	send_sb(t, cmd, &val, 1);
}

void rfc2217_start(struct rfc2217 *t, const struct rfc2217_ops *ops, void *ctx)
{
	memset(t, 0, sizeof(*t));
	t->ops = ops;
	t->ctx = ctx;
	t->state = S_DATA;

	t->we_asked = opt_bit(OPT_ECHO) | opt_bit(OPT_SGA) | opt_bit(OPT_COM_PORT);
	t->they_asked = opt_bit(OPT_BINARY);
	send_option(t, WILL, OPT_ECHO);
	send_option(t, WILL, OPT_SGA);
	send_option(t, DO, OPT_BINARY);
	send_option(t, WILL, OPT_COM_PORT);
}

bool rfc2217_active(const struct rfc2217 *t)
{
	return (t->we & opt_bit(OPT_COM_PORT)) || (t->they & opt_bit(OPT_COM_PORT));
}

/* DO/DONT are about our side, WILL/WONT about the client's side */
static void negotiate(struct rfc2217 *t, uint8_t verb, uint8_t opt)
{
	int bit = opt_bit(opt);
	bool ours = verb == DO || verb == DONT;
	bool yes = verb == DO || verb == WILL;
	uint8_t *state = ours ? &t->we : &t->they;
	uint8_t *asked = ours ? &t->we_asked : &t->they_asked;
	int ok = ours ? WE_OK : THEY_OK;
	uint8_t send_yes = ours ? WILL : DO;
	uint8_t send_no = ours ? WONT : DONT;

	if (yes) {
		if (!(bit & ok)) {
			send_option(t, send_no, opt);
			return;
		}
		if (!(*state & bit) && !(*asked & bit)) {
			send_option(t, send_yes, opt);
		}
		*state |= bit;
		*asked &= ~bit;
	} else {
		if (*state & bit) {
			send_option(t, send_no, opt);
		}
		*state &= ~bit;
		*asked &= ~bit;
	}
}

static uint32_t be32(const uint8_t *p)
{
	return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}

static void com_port_command(struct rfc2217 *t, uint8_t cmd, const uint8_t *val, size_t len)
{
	const struct rfc2217_ops *ops = t->ops;
	uint8_t out[4];

	switch (cmd) {
	case CPC_SIGNATURE:
		send_sb(t, cmd, (const uint8_t *)SIGNATURE, sizeof(SIGNATURE) - 1);
		break;
	case CPC_SET_BAUDRATE: {
		uint32_t baud = ops->baudrate(t->ctx, len >= 4 ? be32(val) : 0);

		out[0] = baud >> 24;
		out[1] = baud >> 16;
		out[2] = baud >> 8;
		out[3] = baud;
		send_sb(t, cmd, out, 4);
		break;
	}
	case CPC_SET_DATASIZE:
		send_sb_byte(t, cmd, ops->datasize(t->ctx, len ? val[0] : 0));
		break;
	case CPC_SET_PARITY:
		send_sb_byte(t, cmd, ops->parity(t->ctx, len ? val[0] : 0));
		break;
	case CPC_SET_STOPSIZE:
		send_sb_byte(t, cmd, ops->stopsize(t->ctx, len ? val[0] : 0));
		break;
	case CPC_SET_CONTROL:
		send_sb_byte(t, cmd, ops->control(t->ctx, len ? val[0] : 0));
		break;
	case CPC_NOTIFY_MODEMSTATE:
		/* A client polling the modem lines */
		send_sb_byte(t, cmd, MODEMSTATE_LINES_UP);
		break;
	case CPC_SET_LINESTATE_MASK:
	case CPC_SET_MODEMSTATE_MASK:
		send_sb_byte(t, cmd, len ? val[0] : 0);
		break;
	case CPC_PURGE_DATA:
		if (len && ops->purge != NULL) {
			ops->purge(t->ctx, val[0]);
		}
		send_sb_byte(t, cmd, len ? val[0] : 0);
		break;
	case CPC_NOTIFY_LINESTATE:
	case CPC_FLOWCONTROL_SUSPEND:
	case CPC_FLOWCONTROL_RESUME:
	default:
		/* Nothing to answer */
		break;
	}
}

static void subnegotiation_end(struct rfc2217 *t)
{
	if (t->sb_overflow || t->sb_len < 2 || t->sb[0] != OPT_COM_PORT) {
		return;
	}

	com_port_command(t, t->sb[1], &t->sb[2], t->sb_len - 2);
}

static void sb_byte(struct rfc2217 *t, uint8_t c)
{
	if (t->sb_len < sizeof(t->sb)) {
		t->sb[t->sb_len++] = c;
	} else {
		t->sb_overflow = true;
	}
}

void rfc2217_input(struct rfc2217 *t, const uint8_t *buf, size_t len)
{
	size_t run = 0; /* start of the pending run of plain data */

	for (size_t i = 0; i < len; i++) {
		uint8_t c = buf[i];

		switch (t->state) {
		case S_DATA:
			if (c == IAC) {
				if (i > run) {
					t->ops->data(t->ctx, &buf[run], i - run);
				}
				t->state = S_IAC;
			} else if (c == 0 && t->cr && !(t->they & opt_bit(OPT_BINARY))) {
				/* NVT: CR NUL is a bare CR */
				if (i > run) {
					t->ops->data(t->ctx, &buf[run], i - run);
				}
				run = i + 1;
			}
			t->cr = c == '\r';
			continue;
		case S_IAC:
			switch (c) {
			case IAC:
				/* Escaped 0xFF data byte */
				t->ops->data(t->ctx, &c, 1);
				t->state = S_DATA;
				break;
			case WILL:
			case WONT:
			case DO:
			case DONT:
				t->verb = c;
				t->state = S_VERB;
				break;
			case SB:
				t->sb_len = 0;
				t->sb_overflow = false;
				t->state = S_SB;
				break;
			default:
				/* NOP, GA, AYT, ...: ignored */
				t->state = S_DATA;
				break;
			}
			break;
		case S_VERB:
			negotiate(t, t->verb, c);
			t->state = S_DATA;
			break;
		case S_SB:
			if (c == IAC) {
				t->state = S_SB_IAC;
			} else {
				sb_byte(t, c);
			}
			break;
		case S_SB_IAC:
			if (c == SE) {
				subnegotiation_end(t);
				t->state = S_DATA;
			} else {
				/* IAC IAC: an escaped 0xFF inside the subnegotiation */
				sb_byte(t, c);
				t->state = S_SB;
			}
			break;
		default:
			t->state = S_DATA;
			break;
		}
		run = i + 1;
	}

	if (t->state == S_DATA && len > run) {
		t->ops->data(t->ctx, &buf[run], len - run);
	}
}

size_t rfc2217_escape(const uint8_t *in, size_t in_len, uint8_t *out, size_t out_size,
		      size_t *consumed)
{
	size_t i = 0;
	size_t n = 0;

	for (; i < in_len; i++) {
		size_t need = in[i] == IAC ? 2 : 1;

		if (n + need > out_size) {
			break;
		}
		out[n++] = in[i];
		if (in[i] == IAC) {
			out[n++] = IAC;
		}
	}

	*consumed = i;

	return n;
}
