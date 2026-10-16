/*
 * AUX UART (the DUT's console on the AUX connector) <-> raw TCP, one client.
 *
 *   socat -,raw,echo=0 TCP:bay-b3.local:4000
 *   python -m serial.tools.miniterm socket://bay-b3.local:4000
 *
 * Bytes received while nobody is connected are dropped; the receive buffer
 * is flushed when a client connects, so it only sees fresh output.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/net/socket.h>
#include <zephyr/sys/ring_buffer.h>
#include <zephyr/logging/log.h>

#include "bay.h"

LOG_MODULE_REGISTER(aux, CONFIG_BAY_LOG_LEVEL);

#define AUX_UART DEVICE_DT_GET(DT_PHANDLE(DT_NODELABEL(dut_port), uart))

#define AUX_THREAD_STACK_SIZE 2048
#define AUX_THREAD_PRIORITY   K_PRIO_PREEMPT(8)
#define AUX_POLL_MS           10

RING_BUF_DECLARE(aux_rx_ring, CONFIG_BAY_AUX_BUF_SIZE);

static const struct device *const uart = AUX_UART;
static atomic_t rx_bytes;
static atomic_t tx_bytes;
static atomic_t dropped;
static atomic_t client;

static void uart_isr(const struct device *dev, void *user_data)
{
	uint8_t buf[64];

	ARG_UNUSED(user_data);

	uart_irq_update(dev);

	while (uart_irq_rx_ready(dev)) {
		int n = uart_fifo_read(dev, buf, sizeof(buf));
		uint32_t put;

		if (n <= 0) {
			break;
		}
		put = ring_buf_put(&aux_rx_ring, buf, n);
		if (put < (uint32_t)n) {
			atomic_add(&dropped, n - put);
		}
	}
}

static void rx_flush(void)
{
	uart_irq_rx_disable(uart);
	ring_buf_reset(&aux_rx_ring);
	uart_irq_rx_enable(uart);
}

static int send_all(int fd, const uint8_t *buf, size_t len)
{
	while (len > 0) {
		ssize_t n = zsock_send(fd, buf, len, 0);

		if (n < 0) {
			return -errno;
		}
		buf += n;
		len -= n;
	}

	return 0;
}

static void serve_client(int fd)
{
	uint8_t buf[128];

	while (true) {
		struct zsock_pollfd pfd = {.fd = fd, .events = ZSOCK_POLLIN};
		int ret = zsock_poll(&pfd, 1, AUX_POLL_MS);
		uint32_t n;

		if (ret < 0) {
			return;
		}

		if (pfd.revents & ZSOCK_POLLIN) {
			ssize_t len = zsock_recv(fd, buf, sizeof(buf), 0);

			if (len <= 0) {
				return;
			}
			for (ssize_t i = 0; i < len; i++) {
				uart_poll_out(uart, buf[i]);
			}
			atomic_add(&tx_bytes, len);
		} else if (pfd.revents & (ZSOCK_POLLHUP | ZSOCK_POLLERR | ZSOCK_POLLNVAL)) {
			return;
		}

		while ((n = ring_buf_get(&aux_rx_ring, buf, sizeof(buf))) > 0) {
			if (send_all(fd, buf, n) != 0) {
				return;
			}
			atomic_add(&rx_bytes, n);
		}
	}
}

static void aux_thread(void *p1, void *p2, void *p3)
{
	struct net_sockaddr_in addr = {
		.sin_family = NET_AF_INET,
		.sin_port = net_htons(CONFIG_BAY_AUX_TCP_PORT),
		.sin_addr.s_addr = net_htonl(NET_INADDR_ANY),
	};
	int reuse = 1;
	int lfd;

	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	lfd = zsock_socket(NET_AF_INET, NET_SOCK_STREAM, NET_IPPROTO_TCP);
	if (lfd < 0) {
		LOG_ERR("socket() failed: %d", errno);
		return;
	}
	(void)zsock_setsockopt(lfd, ZSOCK_SOL_SOCKET, ZSOCK_SO_REUSEADDR, &reuse, sizeof(reuse));

	if (zsock_bind(lfd, (struct net_sockaddr *)&addr, sizeof(addr)) < 0 ||
	    zsock_listen(lfd, 1) < 0) {
		LOG_ERR("cannot listen on port %d: %d", CONFIG_BAY_AUX_TCP_PORT, errno);
		zsock_close(lfd);
		return;
	}

	LOG_INF("AUX UART on tcp/%d", CONFIG_BAY_AUX_TCP_PORT);

	while (true) {
		struct net_sockaddr_in peer;
		net_socklen_t peer_len = sizeof(peer);
		char peer_str[NET_INET_ADDRSTRLEN];
		int fd = zsock_accept(lfd, (struct net_sockaddr *)&peer, &peer_len);

		if (fd < 0) {
			LOG_ERR("accept() failed: %d", errno);
			k_sleep(K_SECONDS(1));
			continue;
		}

		zsock_inet_ntop(NET_AF_INET, &peer.sin_addr, peer_str, sizeof(peer_str));
		LOG_INF("AUX client %s connected", peer_str);

		rx_flush();
		atomic_set(&client, 1);
		serve_client(fd);
		atomic_set(&client, 0);
		zsock_close(fd);

		LOG_INF("AUX client %s disconnected", peer_str);
	}
}

K_THREAD_STACK_DEFINE(aux_stack, AUX_THREAD_STACK_SIZE);
static struct k_thread aux_thread_data;

int aux_bridge_init(void)
{
	int ret;

	if (!device_is_ready(uart)) {
		return -ENODEV;
	}

	ret = uart_irq_callback_user_data_set(uart, uart_isr, NULL);
	if (ret != 0) {
		return ret;
	}
	uart_irq_rx_enable(uart);

	if (CONFIG_BAY_AUX_TCP_PORT == 0) {
		return 0;
	}

	k_thread_create(&aux_thread_data, aux_stack, K_THREAD_STACK_SIZEOF(aux_stack), aux_thread,
			NULL, NULL, NULL, AUX_THREAD_PRIORITY, 0, K_NO_WAIT);
	k_thread_name_set(&aux_thread_data, "aux_bridge");

	return 0;
}

uint32_t aux_bridge_baudrate(void)
{
	struct uart_config cfg;

	if (uart_config_get(uart, &cfg) != 0) {
		return 0;
	}

	return cfg.baudrate;
}

int aux_bridge_set_baudrate(uint32_t baudrate)
{
	struct uart_config cfg;
	int ret = uart_config_get(uart, &cfg);

	if (ret != 0) {
		return ret;
	}
	cfg.baudrate = baudrate;

	return uart_configure(uart, &cfg);
}

bool aux_bridge_client_connected(void)
{
	return atomic_get(&client) != 0;
}

void aux_bridge_stats(uint32_t *rx, uint32_t *tx, uint32_t *drop)
{
	*rx = (uint32_t)atomic_get(&rx_bytes);
	*tx = (uint32_t)atomic_get(&tx_bytes);
	*drop = (uint32_t)atomic_get(&dropped);
}
