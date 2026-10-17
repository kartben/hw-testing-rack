/*
 * Host test shim: one rfc2217 instance driven from Python (ctypes).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "rfc2217.h"

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

/* kind: 0 serial data for the UART, 1 telnet reply for the client */
typedef void (*bytes_cb)(int kind, const uint8_t *buf, size_t len);
/* what: 0 baud, 1 datasize, 2 parity, 3 stopsize, 4 control, 5 purge */
typedef uint32_t (*setting_cb)(int what, uint32_t value);

static bytes_cb on_bytes;
static setting_cb on_setting;
static struct rfc2217 t;

static void data(void *ctx, const uint8_t *buf, size_t len)
{
	on_bytes(0, buf, len);
}

static void reply(void *ctx, const uint8_t *buf, size_t len)
{
	on_bytes(1, buf, len);
}

static uint32_t baudrate(void *ctx, uint32_t v)
{
	return on_setting(0, v);
}

static uint8_t datasize(void *ctx, uint8_t v)
{
	return (uint8_t)on_setting(1, v);
}

static uint8_t parity(void *ctx, uint8_t v)
{
	return (uint8_t)on_setting(2, v);
}

static uint8_t stopsize(void *ctx, uint8_t v)
{
	return (uint8_t)on_setting(3, v);
}

static uint8_t control(void *ctx, uint8_t v)
{
	return (uint8_t)on_setting(4, v);
}

static void purge(void *ctx, uint8_t v)
{
	on_setting(5, v);
}

static const struct rfc2217_ops ops = {
	.data = data,
	.reply = reply,
	.baudrate = baudrate,
	.datasize = datasize,
	.parity = parity,
	.stopsize = stopsize,
	.control = control,
	.purge = purge,
};

EXPORT void shim_start(bytes_cb b, setting_cb s)
{
	on_bytes = b;
	on_setting = s;
	rfc2217_start(&t, &ops, NULL);
}

EXPORT void shim_input(const uint8_t *buf, size_t len)
{
	rfc2217_input(&t, buf, len);
}

EXPORT int shim_active(void)
{
	return rfc2217_active(&t);
}

EXPORT size_t shim_escape(const uint8_t *in, size_t in_len, uint8_t *out, size_t out_size,
			  size_t *consumed)
{
	return rfc2217_escape(in, in_len, out, out_size, consumed);
}
