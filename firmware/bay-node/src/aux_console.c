/*
 * AUX UART (the DUT's console on the AUX connector), shared by:
 *
 *   - web consoles: WebSocket /console/ws/<slot>, binary frames both ways,
 *     the last CONFIG_BAY_AUX_LOG_SIZE bytes replayed on connect, text
 *     frames for control ({"type":"hello"|"config", ...});
 *   - one RFC 2217 client on CONFIG_BAY_RFC2217_PORT (pyserial rfc2217://,
 *     labgrid NetworkSerialPort, esptool): the port settings it asks for
 *     apply while it is connected, the saved ones come back afterwards;
 *   - one raw TCP client on CONFIG_BAY_AUX_TCP_PORT (socat, nc).
 *
 * Everything the DUT sends goes to every client.  Everything a client sends
 * goes to the DUT: with several writers the bytes simply interleave.
 *
 * The UART is interrupt driven: RX lands in a circular log (each client
 * keeps its own read position in it), TX drains a ring buffer.  One thread
 * serves all the sockets.
 *
 * While the DUT is powered off the TX pin is released (high impedance), so
 * the node does not back-power the board through its RX pin; BREAK drives
 * it low.  Both need the pin as a GPIO: the `tx-gpios` of `hwtr,dut-port`.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/pinctrl.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/net/socket.h>
#include <zephyr/net/websocket.h>
#include <zephyr/random/random.h>
#include <zephyr/sys/ring_buffer.h>
#include <zephyr/logging/log.h>

#include "bay.h"
#include "rfc2217.h"

LOG_MODULE_REGISTER(aux, CONFIG_BAY_LOG_LEVEL);

#define DUT_NODE      DT_NODELABEL(dut_port)
#define AUX_UART_NODE DT_PHANDLE(DUT_NODE, uart)

#define LOG_SIZE CONFIG_BAY_AUX_LOG_SIZE
#define LOG_MASK (LOG_SIZE - 1)
BUILD_ASSERT(IS_POWER_OF_TWO(LOG_SIZE), "CONFIG_BAY_AUX_LOG_SIZE must be a power of two");
BUILD_ASSERT(CONFIG_WEBSOCKET_MAX_CONTEXTS >= CONFIG_BAY_CONSOLE_WEB_CLIENTS,
	     "one websocket context per web console");

#define WEB_MAX        CONFIG_BAY_CONSOLE_WEB_CLIENTS
#define CHUNK          256   /* bytes per send to a client */
#define POLL_MS        10    /* RX latency towards the clients */
#define WS_SEND_MS     200   /* a web console slower than that is dropped */
#define DRAIN_MS       200   /* longest wait for TX to empty before a BREAK */
#define HUB_STACK_SIZE 3072
#define HUB_PRIORITY   K_PRIO_PREEMPT(8)

static const struct device *const uart = DEVICE_DT_GET(AUX_UART_NODE);
static const struct gpio_dt_spec tx_line = GPIO_DT_SPEC_GET_OR(DUT_NODE, tx_gpios, {0});

/* The UART's own pin configuration, re-applied when the TX pin goes back to it */
static const pinctrl_soc_pin_t uart_pins[] = Z_PINCTRL_STATE_PINS_INIT(AUX_UART_NODE, pinctrl_0);

/* --- UART: RX log, TX ring ----------------------------------------------- */

static uint8_t rx_log[LOG_SIZE];
static atomic_t rx_head;     /* bytes received since boot (mod 2^32) */
static atomic_t log_full;    /* rx_head went past LOG_SIZE once */
static atomic_t tx_bytes;
static atomic_t dropped;

RING_BUF_DECLARE(tx_ring, CONFIG_BAY_AUX_TX_BUF_SIZE);

static void uart_isr(const struct device *dev, void *user_data)
{
	ARG_UNUSED(user_data);

	uart_irq_update(dev);

	if (uart_irq_rx_ready(dev)) {
		uint32_t head = (uint32_t)atomic_get(&rx_head);
		uint8_t buf[32];
		int n;

		while ((n = uart_fifo_read(dev, buf, sizeof(buf))) > 0) {
			for (int i = 0; i < n; i++) {
				rx_log[(head + i) & LOG_MASK] = buf[i];
			}
			head += n;
		}
		if (head >= LOG_SIZE) {
			atomic_set(&log_full, 1);
		}
		atomic_set(&rx_head, (atomic_val_t)head);
	}

	if (uart_irq_tx_ready(dev)) {
		uint8_t *data;
		uint32_t len = ring_buf_get_ptr(&tx_ring, &data, 0);

		if (len == 0) {
			uart_irq_tx_disable(dev);
		} else {
			int sent = uart_fifo_fill(dev, data, MIN(len, 64U));

			if (sent > 0) {
				ring_buf_consume(&tx_ring, sent);
				atomic_add(&tx_bytes, sent);
			}
		}
	}
}

/* Queue bytes for the DUT; returns how many fit */
static size_t tx_write(const uint8_t *buf, size_t len)
{
	uint32_t put = ring_buf_put(&tx_ring, buf, len);

	if (put < len) {
		atomic_add(&dropped, len - put);
	}
	if (put > 0) {
		uart_irq_tx_enable(uart);
	}

	return put;
}

/*
 * Oldest position a client can still read safely: the ISR keeps writing
 * while a client copies, so stay a chunk away from being overwritten.
 */
#define LOG_WINDOW (LOG_SIZE - CHUNK)

static uint32_t log_start(void)
{
	uint32_t head = (uint32_t)atomic_get(&rx_head);

	return (atomic_get(&log_full) || head > LOG_WINDOW) ? head - LOG_WINDOW : 0;
}

/* --- TX line: released while the DUT is off, low during a BREAK ------------ */

static K_MUTEX_DEFINE(line_lock);
static bool dut_on = true;
static bool in_break;

static void line_to_uart(void)
{
	(void)pinctrl_configure_pins(uart_pins, ARRAY_SIZE(uart_pins), PINCTRL_REG_NONE);
}

static void tx_drain(void)
{
	int64_t end = k_uptime_get() + DRAIN_MS;

	while ((!ring_buf_is_empty(&tx_ring) || uart_irq_tx_complete(uart) == 0) &&
	       k_uptime_get() < end) {
		k_msleep(1);
	}
}

static int line_break(bool on)
{
	int ret = 0;

	if (tx_line.port == NULL) {
		return -ENOTSUP;
	}

	k_mutex_lock(&line_lock, K_FOREVER);
	if (!dut_on) {
		ret = -EIO;
	} else if (on && !in_break) {
		tx_drain();
		ret = gpio_pin_configure_dt(&tx_line, GPIO_OUTPUT_LOW);
		in_break = ret == 0;
	} else if (!on && in_break) {
		line_to_uart();
		in_break = false;
	}
	k_mutex_unlock(&line_lock);

	return ret;
}

void aux_dut_power(bool on)
{
	if (tx_line.port == NULL) {
		return;
	}

	k_mutex_lock(&line_lock, K_FOREVER);
	if (on != dut_on) {
		if (on) {
			line_to_uart();
		} else {
			/* Input only: no current into the unpowered DUT */
			(void)gpio_pin_configure_dt(&tx_line, GPIO_INPUT);
		}
		dut_on = on;
		in_break = false;
	}
	k_mutex_unlock(&line_lock);
}

int aux_break(uint32_t ms)
{
	int ret = line_break(true);

	if (ret != 0) {
		return ret;
	}
	k_msleep(ms);

	return line_break(false);
}

/* --- Port settings --------------------------------------------------------- */

static K_MUTEX_DEFINE(cfg_lock);
static struct aux_config saved = AUX_CONFIG_DEFAULT;
static struct aux_config current = AUX_CONFIG_DEFAULT;
static atomic_t cfg_seq = ATOMIC_INIT(1);

static bool config_valid(const struct aux_config *c)
{
	return c->baud >= 300 && c->baud <= 5000000 && c->data_bits >= 5 && c->data_bits <= 8 &&
	       c->parity <= AUX_PARITY_EVEN && (c->stop_bits == 1 || c->stop_bits == 2) &&
	       c->enter <= AUX_ENTER_CRLF;
}

static int uart_apply(const struct aux_config *c)
{
	static const uint8_t parity[] = {
		[AUX_PARITY_NONE] = UART_CFG_PARITY_NONE,
		[AUX_PARITY_ODD] = UART_CFG_PARITY_ODD,
		[AUX_PARITY_EVEN] = UART_CFG_PARITY_EVEN,
	};
	const struct uart_config u = {
		.baudrate = c->baud,
		.parity = parity[c->parity],
		.stop_bits = c->stop_bits == 2 ? UART_CFG_STOP_BITS_2 : UART_CFG_STOP_BITS_1,
		.data_bits = UART_CFG_DATA_BITS_5 + (c->data_bits - 5),
		.flow_ctrl = UART_CFG_FLOW_CTRL_NONE,
	};
	int ret = uart_configure(uart, &u);

	uart_irq_rx_enable(uart);
	if (!ring_buf_is_empty(&tx_ring)) {
		uart_irq_tx_enable(uart);
	}

	return ret;
}

int aux_config_set(const struct aux_config *cfg, bool persist)
{
	int ret;

	if (!config_valid(cfg)) {
		return -EINVAL;
	}

	k_mutex_lock(&cfg_lock, K_FOREVER);
	ret = uart_apply(cfg);
	if (ret == 0) {
		current = *cfg;
		if (persist) {
			saved = *cfg;
			ret = bay_settings_save_aux(cfg);
		}
		atomic_inc(&cfg_seq);
	} else {
		(void)uart_apply(&current);
	}
	k_mutex_unlock(&cfg_lock);

	return ret;
}

void aux_config_get(struct aux_config *cfg, bool from_flash)
{
	k_mutex_lock(&cfg_lock, K_FOREVER);
	*cfg = from_flash ? saved : current;
	k_mutex_unlock(&cfg_lock);
}

const char *aux_parity_str(uint8_t parity)
{
	switch (parity) {
	case AUX_PARITY_ODD:
		return "odd";
	case AUX_PARITY_EVEN:
		return "even";
	default:
		return "none";
	}
}

const char *aux_enter_str(uint8_t enter)
{
	switch (enter) {
	case AUX_ENTER_LF:
		return "lf";
	case AUX_ENTER_CRLF:
		return "crlf";
	default:
		return "cr";
	}
}

int aux_config_json(char *buf, size_t len, const char *type)
{
	struct aux_config c;

	aux_config_get(&c, false);

	return snprintf(buf, len,
			"{\"type\":\"%s\",\"baud\":%u,\"data_bits\":%u,\"parity\":\"%s\","
			"\"stop_bits\":%u,\"enter\":\"%s\",\"echo\":%s,\"esptool_reset\":%s}",
			type, c.baud, c.data_bits, aux_parity_str(c.parity), c.stop_bits,
			aux_enter_str(c.enter), c.echo ? "true" : "false",
			c.esptool_reset ? "true" : "false");
}

/* --- Clients ----------------------------------------------------------------- */

struct client {
	int fd;           /* -1: free */
	uint32_t pos;     /* next log byte this client gets */
	atomic_val_t seq; /* web: last config sent */
	uint8_t *out;     /* TCP: bytes waiting for the socket */
	size_t out_len;
	size_t out_off;
};

static uint8_t raw_out[CHUNK];
static uint8_t rfc_out[2 * CHUNK];

static struct client raw = {.fd = -1, .out = raw_out};
static struct client rfc = {.fd = -1, .out = rfc_out};
static struct client web[WEB_MAX] = {[0 ... WEB_MAX - 1] = {.fd = -1}};

static K_MUTEX_DEFINE(clients_lock);

static struct rfc2217 telnet;
static bool rfc_dtr;
static bool rfc_rts;

/* Bytes skipped by a client that fell more than a log behind */
static void catch_up(struct client *c, uint32_t head)
{
	if (head - c->pos > LOG_WINDOW) {
		atomic_add(&dropped, head - c->pos - LOG_WINDOW);
		c->pos = head - LOG_WINDOW;
	}
}

/* Send what is queued for a TCP client; 0 when done, 1 when the socket is full */
static int tcp_flush(struct client *c)
{
	while (c->out_off < c->out_len) {
		ssize_t n = zsock_send(c->fd, &c->out[c->out_off], c->out_len - c->out_off,
				       ZSOCK_MSG_DONTWAIT);

		if (n < 0) {
			return (errno == EAGAIN || errno == EWOULDBLOCK) ? 1 : -errno;
		}
		c->out_off += n;
	}
	c->out_len = 0;
	c->out_off = 0;

	return 0;
}

/* Queue telnet replies behind the pending data, never in the middle of it */
static void tcp_queue(struct client *c, const uint8_t *buf, size_t len, size_t size)
{
	for (int tries = 0; c->out_len + len > size && tries < 100; tries++) {
		if (tcp_flush(c) != 1) {
			break;
		}
		k_msleep(1);
	}
	if (c->out_len + len <= size) {
		memcpy(&c->out[c->out_len], buf, len);
		c->out_len += len;
	} else {
		LOG_WRN("RFC 2217 client not reading: reply dropped");
	}
}

/* New log bytes to a raw or RFC 2217 client */
static int tcp_pump(struct client *c, bool telnet_escape, size_t size)
{
	int ret = tcp_flush(c);

	while (ret == 0) {
		uint32_t head = (uint32_t)atomic_get(&rx_head);
		uint32_t off;
		size_t n;

		catch_up(c, head);
		if (c->pos == head) {
			break;
		}
		off = c->pos & LOG_MASK;
		n = MIN(MIN(head - c->pos, LOG_SIZE - off), (uint32_t)CHUNK);

		if (telnet_escape) {
			size_t used;

			c->out_len = rfc2217_escape(&rx_log[off], n, c->out, size, &used);
			n = used;
		} else {
			memcpy(c->out, &rx_log[off], n);
			c->out_len = n;
		}
		c->out_off = 0;
		c->pos += n;
		ret = tcp_flush(c);
	}

	return ret < 0 ? ret : 0;
}

/* New log bytes and config changes to a web console */
static int web_pump(struct client *c)
{
	atomic_val_t seq = atomic_get(&cfg_seq);
	int ret;

	if (c->seq != seq) {
		static char msg[256];
		int len = aux_config_json(msg, sizeof(msg), "config");

		ret = websocket_send_msg(c->fd, msg, len, WEBSOCKET_OPCODE_DATA_TEXT, false, true,
					 WS_SEND_MS);
		if (ret < 0) {
			return ret;
		}
		c->seq = seq;
	}

	while (true) {
		uint32_t head = (uint32_t)atomic_get(&rx_head);
		uint32_t off;
		size_t n;

		catch_up(c, head);
		if (c->pos == head) {
			return 0;
		}
		off = c->pos & LOG_MASK;
		n = MIN(MIN(head - c->pos, LOG_SIZE - off), (uint32_t)CHUNK);
		ret = websocket_send_msg(c->fd, &rx_log[off], n, WEBSOCKET_OPCODE_DATA_BINARY,
					 false, true, WS_SEND_MS);
		if (ret < 0) {
			return ret;
		}
		c->pos += n;
	}
}

static void client_close(struct client *c, const char *what)
{
	if (c->fd < 0) {
		return;
	}

	if (c == &raw || c == &rfc) {
		zsock_close(c->fd);
	} else {
		(void)websocket_unregister(c->fd);
	}
	c->fd = -1;
	c->out_len = 0;
	c->out_off = 0;
	LOG_INF("%s client disconnected", what);

	if (c == &rfc) {
		struct aux_config cfg;

		/* The RFC 2217 client's settings were for its session only */
		aux_config_get(&cfg, true);
		(void)aux_config_set(&cfg, false);
		(void)line_break(false);
		if (cfg.esptool_reset && (rfc_dtr || rfc_rts)) {
			(void)dut_reset_set(false);
			(void)dut_boot_set(false);
		}
		rfc_dtr = false;
		rfc_rts = false;
	}
}

/* --- RFC 2217 callbacks (hub thread) ----------------------------------------- */

static void rfc_data(void *ctx, const uint8_t *buf, size_t len)
{
	ARG_UNUSED(ctx);
	(void)tx_write(buf, len);
}

static void rfc_reply(void *ctx, const uint8_t *buf, size_t len)
{
	ARG_UNUSED(ctx);
	tcp_queue(&rfc, buf, len, sizeof(rfc_out));
}

/* Apply one field of the port settings for this session; returns what is in effect */
static struct aux_config rfc_try(struct aux_config cfg)
{
	struct aux_config now;

	(void)aux_config_set(&cfg, false);
	aux_config_get(&now, false);

	return now;
}

static uint32_t rfc_baudrate(void *ctx, uint32_t baud)
{
	struct aux_config cfg;

	aux_config_get(&cfg, false);
	if (baud != 0) {
		cfg.baud = baud;
		cfg = rfc_try(cfg);
	}

	return cfg.baud;
}

static uint8_t rfc_datasize(void *ctx, uint8_t bits)
{
	struct aux_config cfg;

	aux_config_get(&cfg, false);
	if (bits != 0) {
		cfg.data_bits = bits;
		cfg = rfc_try(cfg);
	}

	return cfg.data_bits;
}

static uint8_t rfc_parity(void *ctx, uint8_t parity)
{
	static const uint8_t to_rfc[] = {
		[AUX_PARITY_NONE] = RFC2217_PARITY_NONE,
		[AUX_PARITY_ODD] = RFC2217_PARITY_ODD,
		[AUX_PARITY_EVEN] = RFC2217_PARITY_EVEN,
	};
	struct aux_config cfg;

	aux_config_get(&cfg, false);
	if (parity >= RFC2217_PARITY_NONE && parity <= RFC2217_PARITY_EVEN) {
		cfg.parity = parity - RFC2217_PARITY_NONE;
		cfg = rfc_try(cfg);
	}

	/* Mark and space are not supported: the current parity is the answer */
	return to_rfc[cfg.parity];
}

static uint8_t rfc_stopsize(void *ctx, uint8_t stop)
{
	struct aux_config cfg;

	aux_config_get(&cfg, false);
	if (stop == RFC2217_STOP_1 || stop == RFC2217_STOP_2) {
		cfg.stop_bits = stop;
		cfg = rfc_try(cfg);
	}

	return cfg.stop_bits;
}

/*
 * DTR/RTS like the two-transistor auto-reset circuit of ESP32 boards:
 * RESET while RTS && !DTR, BOOT while DTR && !RTS, so esptool can reset the
 * DUT into its ROM loader, and a terminal holding both lines does nothing.
 */
static void rfc_modem_lines(void)
{
	struct aux_config cfg;

	aux_config_get(&cfg, false);
	if (cfg.esptool_reset) {
		(void)dut_reset_set(rfc_rts && !rfc_dtr);
		(void)dut_boot_set(rfc_dtr && !rfc_rts);
	}
}

static uint8_t rfc_control(void *ctx, uint8_t value)
{
	switch (value) {
	case 0: /* flow control? */
	case RFC2217_CTL_NO_FLOW:
		return RFC2217_CTL_NO_FLOW;
	case 4: /* BREAK state? */
		return in_break ? RFC2217_CTL_BREAK_ON : RFC2217_CTL_BREAK_OFF;
	case RFC2217_CTL_BREAK_ON:
	case RFC2217_CTL_BREAK_OFF:
		(void)line_break(value == RFC2217_CTL_BREAK_ON);
		return value;
	case 7: /* DTR state? */
		return rfc_dtr ? RFC2217_CTL_DTR_ON : RFC2217_CTL_DTR_OFF;
	case RFC2217_CTL_DTR_ON:
	case RFC2217_CTL_DTR_OFF:
		rfc_dtr = value == RFC2217_CTL_DTR_ON;
		rfc_modem_lines();
		return value;
	case 10: /* RTS state? */
		return rfc_rts ? RFC2217_CTL_RTS_ON : RFC2217_CTL_RTS_OFF;
	case RFC2217_CTL_RTS_ON:
	case RFC2217_CTL_RTS_OFF:
		rfc_rts = value == RFC2217_CTL_RTS_ON;
		rfc_modem_lines();
		return value;
	default:
		/* XON/XOFF, hardware flow control, ...: not available */
		return RFC2217_CTL_NO_FLOW;
	}
}

static void rfc_purge(void *ctx, uint8_t what)
{
	if (what & 1) {
		/* Receive side: drop what the client has not read yet */
		rfc.pos = (uint32_t)atomic_get(&rx_head);
	}
	if (what & 2) {
		uart_irq_tx_disable(uart);
		ring_buf_reset(&tx_ring);
	}
}

static const struct rfc2217_ops rfc_ops = {
	.data = rfc_data,
	.reply = rfc_reply,
	.baudrate = rfc_baudrate,
	.datasize = rfc_datasize,
	.parity = rfc_parity,
	.stopsize = rfc_stopsize,
	.control = rfc_control,
	.purge = rfc_purge,
};

/* --- Socket service ------------------------------------------------------------ */

static uint8_t rx_buf[256];

static int listen_on(uint16_t port)
{
	struct net_sockaddr_in addr = {
		.sin_family = NET_AF_INET,
		.sin_port = net_htons(port),
		.sin_addr.s_addr = net_htonl(NET_INADDR_ANY),
	};
	int reuse = 1;
	int fd;

	if (port == 0) {
		return -1;
	}

	fd = zsock_socket(NET_AF_INET, NET_SOCK_STREAM, NET_IPPROTO_TCP);
	if (fd < 0) {
		return -1;
	}
	(void)zsock_setsockopt(fd, ZSOCK_SOL_SOCKET, ZSOCK_SO_REUSEADDR, &reuse, sizeof(reuse));
	if (zsock_bind(fd, (struct net_sockaddr *)&addr, sizeof(addr)) < 0 ||
	    zsock_listen(fd, 1) < 0) {
		LOG_ERR("cannot listen on tcp/%u: %d", port, errno);
		zsock_close(fd);
		return -1;
	}

	return fd;
}

/* A new TCP client replaces the previous one (which may be a dead connection) */
static void accept_client(int lfd, struct client *c, const char *what)
{
	int fd = zsock_accept(lfd, NULL, NULL);

	if (fd < 0) {
		return;
	}

	k_mutex_lock(&clients_lock, K_FOREVER);
	if (c->fd >= 0) {
		client_close(c, what);
	}
	c->fd = fd;
	c->pos = (uint32_t)atomic_get(&rx_head);
	c->out_len = 0;
	c->out_off = 0;
	if (c == &rfc) {
		rfc2217_start(&telnet, &rfc_ops, NULL);
	}
	k_mutex_unlock(&clients_lock);

	LOG_INF("%s client connected", what);
}

static int tcp_read(struct client *c, bool is_telnet)
{
	size_t room = MIN(ring_buf_space_get(&tx_ring), sizeof(rx_buf));
	ssize_t n;

	if (room == 0) {
		return 0;
	}
	n = zsock_recv(c->fd, rx_buf, room, ZSOCK_MSG_DONTWAIT);
	if (n == 0) {
		return -ENOTCONN;
	}
	if (n < 0) {
		return (errno == EAGAIN || errno == EWOULDBLOCK) ? 0 : -errno;
	}

	if (is_telnet) {
		rfc2217_input(&telnet, rx_buf, n);
	} else {
		(void)tx_write(rx_buf, n);
	}

	return 0;
}

static int web_read(struct client *c)
{
	size_t room = MIN(ring_buf_space_get(&tx_ring), sizeof(rx_buf));
	uint64_t remaining;
	uint32_t type = 0;
	int n;

	if (room == 0) {
		return 0;
	}
	n = websocket_recv_msg(c->fd, rx_buf, room, &type, &remaining, 0);
	if (n == -EAGAIN) {
		return 0;
	}
	if (n < 0) {
		return n;
	}
	if (type & WEBSOCKET_FLAG_CLOSE) {
		return -ENOTCONN;
	}
	if (type & WEBSOCKET_FLAG_PING) {
		return websocket_send_msg(c->fd, rx_buf, n, WEBSOCKET_OPCODE_PONG, false, true,
					  WS_SEND_MS) < 0 ? -EIO : 0;
	}
	if (n > 0 && (type & (WEBSOCKET_FLAG_BINARY | WEBSOCKET_FLAG_TEXT))) {
		(void)tx_write(rx_buf, n);
	}

	return 0;
}

static const char *client_name(const struct client *c)
{
	return c == &raw ? "raw" : c == &rfc ? "RFC 2217" : "web";
}

static void hub_thread(void *p1, void *p2, void *p3)
{
	struct client *const polled[] = {&raw, &rfc};
	int raw_lfd = listen_on(CONFIG_BAY_AUX_TCP_PORT);
	int rfc_lfd = listen_on(CONFIG_BAY_RFC2217_PORT);

	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	LOG_INF("AUX UART: web console /console, RFC 2217 tcp/%d, raw tcp/%d",
		CONFIG_BAY_RFC2217_PORT, CONFIG_BAY_AUX_TCP_PORT);

	while (true) {
		struct zsock_pollfd fds[4 + WEB_MAX];
		struct client *who[ARRAY_SIZE(fds)];
		short in = ring_buf_space_get(&tx_ring) > 0 ? ZSOCK_POLLIN : 0;
		int n = 0;

		if (raw_lfd >= 0) {
			fds[n] = (struct zsock_pollfd){.fd = raw_lfd, .events = ZSOCK_POLLIN};
			who[n++] = NULL;
		}
		if (rfc_lfd >= 0) {
			fds[n] = (struct zsock_pollfd){.fd = rfc_lfd, .events = ZSOCK_POLLIN};
			who[n++] = NULL;
		}

		k_mutex_lock(&clients_lock, K_FOREVER);
		ARRAY_FOR_EACH(polled, i) {
			if (polled[i]->fd >= 0) {
				fds[n] = (struct zsock_pollfd){.fd = polled[i]->fd, .events = in};
				who[n++] = polled[i];
			}
		}
		ARRAY_FOR_EACH(web, i) {
			if (web[i].fd >= 0) {
				fds[n] = (struct zsock_pollfd){.fd = web[i].fd, .events = in};
				who[n++] = &web[i];
			}
		}
		k_mutex_unlock(&clients_lock);

		(void)zsock_poll(fds, n, POLL_MS);

		for (int i = 0; i < n; i++) {
			struct client *c = who[i];
			short ev = fds[i].revents;
			int ret = 0;

			if (c == NULL) {
				if (ev & ZSOCK_POLLIN) {
					accept_client(fds[i].fd, fds[i].fd == raw_lfd ? &raw : &rfc,
						      fds[i].fd == raw_lfd ? "raw" : "RFC 2217");
				}
				continue;
			}

			if (ev & ZSOCK_POLLIN) {
				ret = c == &raw   ? tcp_read(c, false)
				      : c == &rfc ? tcp_read(c, true)
						  : web_read(c);
			} else if (ev & (ZSOCK_POLLHUP | ZSOCK_POLLERR | ZSOCK_POLLNVAL)) {
				ret = -ENOTCONN;
			}

			if (ret < 0) {
				k_mutex_lock(&clients_lock, K_FOREVER);
				client_close(c, client_name(c));
				k_mutex_unlock(&clients_lock);
			}
		}

		/* Everyone gets what the DUT sent */
		k_mutex_lock(&clients_lock, K_FOREVER);
		if (raw.fd >= 0 && tcp_pump(&raw, false, sizeof(raw_out)) < 0) {
			client_close(&raw, client_name(&raw));
		}
		if (rfc.fd >= 0 && tcp_pump(&rfc, true, sizeof(rfc_out)) < 0) {
			client_close(&rfc, client_name(&rfc));
		}
		ARRAY_FOR_EACH(web, i) {
			if (web[i].fd >= 0 && web_pump(&web[i]) < 0) {
				client_close(&web[i], client_name(&web[i]));
			}
		}
		k_mutex_unlock(&clients_lock);
	}
}

K_THREAD_STACK_DEFINE(hub_stack, HUB_STACK_SIZE);
static struct k_thread hub_thread_data;

/* Tells a reconnecting web console that the stream positions restarted */
static uint32_t boot_id;

/* Called by the HTTP server thread once /console/ws/<slot> is upgraded */
int aux_console_ws_attach(int slot, int ws_sock)
{
	static char hello[288];
	struct client *c;
	uint32_t start = log_start();
	int len;
	int ret;

	if (slot < 0 || slot >= WEB_MAX) {
		return -EINVAL;
	}
	c = &web[slot];

	k_mutex_lock(&clients_lock, K_FOREVER);
	if (c->fd >= 0) {
		k_mutex_unlock(&clients_lock);
		return -EBUSY;
	}

	/*
	 * The first byte replayed is `pos` in this boot's stream: a page that
	 * reconnects skips what it already has (`boot` tells it the node restarted).
	 */
	len = snprintf(hello, sizeof(hello),
		       "{\"type\":\"hello\",\"slot\":%d,\"boot\":%u,\"pos\":%u,\"config\":", slot,
		       boot_id, start);
	len += aux_config_json(&hello[len], sizeof(hello) - len - 1, "config");
	hello[len++] = '}';
	ret = websocket_send_msg(ws_sock, hello, len, WEBSOCKET_OPCODE_DATA_TEXT, false, true,
				 WS_SEND_MS);
	if (ret >= 0) {
		c->fd = ws_sock;
		c->pos = start;
		c->seq = atomic_get(&cfg_seq);
		LOG_INF("web console %d connected", slot);
	}
	k_mutex_unlock(&clients_lock);

	return ret < 0 ? ret : 0;
}

void aux_stats_get(struct aux_stats *st)
{
	st->rx = (uint32_t)atomic_get(&rx_head);
	st->tx = (uint32_t)atomic_get(&tx_bytes);
	st->dropped = (uint32_t)atomic_get(&dropped);
	st->web_clients = 0;
	ARRAY_FOR_EACH(web, i) {
		st->web_clients += web[i].fd >= 0;
	}
	st->rfc2217_client = rfc.fd >= 0;
	st->raw_client = raw.fd >= 0;
}

int aux_console_init(const struct aux_config *stored)
{
	int ret;

	if (!device_is_ready(uart)) {
		return -ENODEV;
	}

	boot_id = sys_rand32_get() >> 1; /* stays a positive JS number */

	if (stored != NULL && config_valid(stored)) {
		saved = *stored;
		current = *stored;
	}
	ret = uart_apply(&current);
	if (ret != 0) {
		LOG_WRN("AUX UART settings refused (%d), keeping the devicetree ones", ret);
	}

	ret = uart_irq_callback_user_data_set(uart, uart_isr, NULL);
	if (ret != 0) {
		return ret;
	}
	uart_irq_rx_enable(uart);

	k_thread_create(&hub_thread_data, hub_stack, K_THREAD_STACK_SIZEOF(hub_stack), hub_thread,
			NULL, NULL, NULL, HUB_PRIORITY, 0, K_NO_WAIT);
	k_thread_name_set(&hub_thread_data, "aux_console");

	return 0;
}
