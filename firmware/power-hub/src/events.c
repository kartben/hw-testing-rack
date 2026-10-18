/*
 * The hub's event log: contract changes, row faults and sequencing,
 * enumerations, node replies.  A ring in RAM, newest first, also logged.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdarg.h>
#include <stdio.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "hub.h"

LOG_MODULE_REGISTER(events, CONFIG_HUB_LOG_LEVEL);

static struct hub_event ring[CONFIG_HUB_EVENTS];
static uint32_t count;
static K_MUTEX_DEFINE(lock);

static const char *const kinds[] = {
	[HUB_EV_PD] = "pd", [HUB_EV_ROW] = "row", [HUB_EV_FAULT] = "fault",
	[HUB_EV_CAN] = "can", [HUB_EV_NODE] = "node",
};

const char *hub_ev_kind_str(uint8_t kind)
{
	return kind < ARRAY_SIZE(kinds) ? kinds[kind] : "?";
}

void hub_event(enum hub_ev_kind kind, const char *fmt, ...)
{
	struct hub_event *e;
	va_list ap;

	k_mutex_lock(&lock, K_FOREVER);
	e = &ring[count % CONFIG_HUB_EVENTS];
	e->t_ms = k_uptime_get();
	e->kind = kind;
	va_start(ap, fmt);
	vsnprintf(e->text, sizeof(e->text), fmt, ap);
	va_end(ap);
	count++;
	k_mutex_unlock(&lock);

	if (kind == HUB_EV_FAULT) {
		LOG_WRN("%s", e->text);
	} else {
		LOG_INF("%s: %s", hub_ev_kind_str(kind), e->text);
	}
}

int hub_events_get(struct hub_event *out, int max)
{
	int n;

	k_mutex_lock(&lock, K_FOREVER);
	n = MIN((uint32_t)max, MIN(count, CONFIG_HUB_EVENTS));
	for (int i = 0; i < n; i++) {
		out[i] = ring[(count - 1 - i) % CONFIG_HUB_EVENTS];
	}
	k_mutex_unlock(&lock);

	return n;
}
