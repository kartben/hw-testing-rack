/*
 * A fatal error restarts the node instead of halting it: a bay in the rack
 * has to come back by itself (its console is the USB host's, so nobody sees
 * the panic).  What happened is kept across the restart in RTC memory and
 * reported once the node is up again (the log, "bay status", /api/status's
 * last_fault):
 *  - the reason and the thread;
 *  - the last warnings and errors logged before it (a log backend keeps
 *    their tail), which say what the panic was about ("heap corruption ...
 *    at 0x...", an assertion, an exception).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/fatal.h>
#include <zephyr/init.h>
#include <zephyr/logging/log.h>
#include <zephyr/logging/log_backend.h>
#include <zephyr/logging/log_ctrl.h>
#include <zephyr/logging/log_output.h>
#include <zephyr/sys/reboot.h>

#include "bay.h"

LOG_MODULE_DECLARE(bay, CONFIG_BAY_LOG_LEVEL);

#define FAULT_MAGIC    0xfa017ed5U
#define FAULT_REPORTED UINT32_MAX
#define TAIL_SIZE      400

struct fault_rec {
	uint32_t magic;
	uint32_t reason;
	uint32_t count; /* fatal errors since power-on */
	char thread[24];
	uint16_t tail_len; /* the last warnings and errors, oldest first */
	char tail[TAIL_SIZE];
};

#if defined(CONFIG_SOC_FAMILY_ESPRESSIF_ESP32)
/* RTC slow memory: kept across a software reset, lost at power-on */
static struct fault_rec rec __attribute__((section(".rtc_noinit")));
#else
static struct fault_rec rec __noinit;
#endif

static char last[96];
static char tail[TAIL_SIZE + 1];

/* --- The log's tail: warnings and errors, the last TAIL_SIZE bytes --------- */

static int tail_out(uint8_t *data, size_t length, void *ctx)
{
	ARG_UNUSED(ctx);

	if (rec.magic != FAULT_MAGIC || rec.tail_len > TAIL_SIZE) {
		return (int)length;
	}
	if (length >= TAIL_SIZE) {
		memcpy(rec.tail, data + length - TAIL_SIZE, TAIL_SIZE);
		rec.tail_len = TAIL_SIZE;
		return (int)length;
	}
	if (rec.tail_len + length > TAIL_SIZE) {
		size_t drop = rec.tail_len + length - TAIL_SIZE;

		memmove(rec.tail, rec.tail + drop, rec.tail_len - drop);
		rec.tail_len -= drop;
	}
	memcpy(rec.tail + rec.tail_len, data, length);
	rec.tail_len += length;
	return (int)length;
}

static uint8_t tail_buf[64];
LOG_OUTPUT_DEFINE(tail_output, tail_out, tail_buf, sizeof(tail_buf));

static void tail_process(const struct log_backend *const backend, union log_msg_generic *msg)
{
	ARG_UNUSED(backend);

	if (log_msg_get_level(&msg->log) > LOG_LEVEL_WRN) {
		return;
	}
	log_output_msg_process(&tail_output, &msg->log, LOG_OUTPUT_FLAG_LEVEL);
}

static void tail_panic(const struct log_backend *const backend)
{
	ARG_UNUSED(backend);
	log_output_flush(&tail_output);
}

static const struct log_backend_api tail_api = {
	.process = tail_process,
	.panic = tail_panic,
};

LOG_BACKEND_DEFINE(fault_log_tail, tail_api, true);

/* --- The fatal error --------------------------------------------------------- */

void k_sys_fatal_error_handler(unsigned int reason, const struct arch_esf *esf)
{
	k_tid_t t = k_current_get();
	const char *name = k_thread_name_get(t);

	ARG_UNUSED(esf);

	/* What the log had just before: the reason's own message comes with it */
	LOG_PANIC();

	rec.reason = reason;
	rec.count++;
	if (name != NULL && name[0] != '\0') {
		strncpy(rec.thread, name, sizeof(rec.thread) - 1);
		rec.thread[sizeof(rec.thread) - 1] = '\0';
	} else {
		snprintf(rec.thread, sizeof(rec.thread), "%p", (void *)t);
	}
	sys_reboot(SYS_REBOOT_COLD);
}

/* The last line of the tail (without its newline) */
static const char *last_line(const char *s, size_t *len)
{
	size_t n = strlen(s);
	const char *start;

	while (n > 0 && (s[n - 1] == '\n' || s[n - 1] == '\r')) {
		n--;
	}
	start = s + n;
	while (start > s && start[-1] != '\n') {
		start--;
	}
	*len = (size_t)(s + n - start);
	return start;
}

/*
 * Before the kernel (and the log thread) runs: copy what the last fault left,
 * then start the next tail afresh.  Logged later, from main (fault_init).
 */
static int fault_snapshot(void)
{
	bool fault = rec.magic == FAULT_MAGIC && rec.reason != FAULT_REPORTED &&
		     rec.tail_len <= TAIL_SIZE;

	if (rec.magic != FAULT_MAGIC || rec.tail_len > TAIL_SIZE) {
		/* Power-on: nothing kept */
		memset(&rec, 0, sizeof(rec));
		rec.magic = FAULT_MAGIC;
	} else if (fault) {
		const char *line;
		size_t len;

		memcpy(tail, rec.tail, rec.tail_len);
		tail[rec.tail_len] = '\0';
		rec.thread[sizeof(rec.thread) - 1] = '\0';
		line = last_line(tail, &len);
		snprintf(last, sizeof(last), "fatal error %u in %s%s%.*s", rec.reason, rec.thread,
			 len ? ": " : "", (int)MIN(len, 60), line);
	}
	rec.reason = FAULT_REPORTED;
	rec.tail_len = 0;
	return 0;
}

SYS_INIT(fault_snapshot, PRE_KERNEL_1, 0);

void fault_init(void)
{
	if (last[0] != '\0') {
		LOG_ERR("restarted after a %s (%u since power-on)", last, rec.count);
	}
}

const char *fault_last(void)
{
	return last;
}

const char *fault_tail(void)
{
	return tail;
}

int fault_log_now(char *buf, size_t size)
{
	size_t n = MIN((size_t)rec.tail_len, size - 1);

	memcpy(buf, rec.tail + rec.tail_len - n, n);
	buf[n] = 0;
	return (int)n;
}
