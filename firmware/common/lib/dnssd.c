/*
 * DNS-SD through the mDNS responder (see hwtr/dnssd.h).
 *
 * The responder walks a table of records the application owns
 * (mdns_responder_set_ext_records()).  Two tables: the one it has, and the
 * next one, built aside and handed over in one call; the call returns once
 * no answer in progress still reads the old table, which then becomes the
 * spare.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/dns_sd.h>
#include <zephyr/net/hostname.h>
#include <zephyr/net/mdns_responder.h>
#include <zephyr/sys/byteorder.h>

#include <hwtr/dnssd.h>

LOG_MODULE_REGISTER(hwtr_dnssd, LOG_LEVEL_INF);

struct table {
	struct dns_sd_rec rec[HWTR_DNSSD_SERVICES];
	char instance[DNS_SD_INSTANCE_MAX_SIZE + 1];
	char service[HWTR_DNSSD_SERVICES][DNS_SD_SERVICE_MAX_SIZE + 1];
	uint16_t port[HWTR_DNSSD_SERVICES]; /* network order */
	uint8_t txt[HWTR_DNSSD_TXT_SIZE];
	size_t txt_len;
	int n;
};

static struct table tables[2];
static struct table *live; /* the responder's, NULL before the first */
static hwtr_dnssd_fill_t fill_cb;
static K_MUTEX_DEFINE(lock);

static void refresh_handler(struct k_work *work);
static K_WORK_DELAYABLE_DEFINE(refresh_work, refresh_handler);

void hwtr_dnssd_service(struct hwtr_dnssd_desc *d, const char *name, uint16_t port)
{
	if (port == 0 || d->nsvc >= HWTR_DNSSD_SERVICES) {
		return;
	}
	d->svc[d->nsvc].name = name;
	d->svc[d->nsvc].port = port;
	d->nsvc++;
}

void hwtr_dnssd_txt(struct hwtr_dnssd_desc *d, const char *key, const char *value)
{
	size_t klen = strlen(key);
	size_t vlen = value != NULL ? strlen(value) : 0;
	size_t len = klen + 1 + vlen;

	/* One length byte per string, at most 255 (RFC 6763, 6.1) */
	if (vlen == 0 || len > UINT8_MAX || d->txt_len + 1 + len > sizeof(d->txt)) {
		return;
	}
	d->txt[d->txt_len++] = (uint8_t)len;
	memcpy(&d->txt[d->txt_len], key, klen);
	d->txt[d->txt_len + klen] = '=';
	memcpy(&d->txt[d->txt_len + klen + 1], value, vlen);
	d->txt_len += len;
}

static bool same(const struct table *a, const struct table *b)
{
	if (a == NULL || a->n != b->n || a->txt_len != b->txt_len ||
	    strcmp(a->instance, b->instance) != 0 || memcmp(a->txt, b->txt, a->txt_len) != 0) {
		return false;
	}
	for (int i = 0; i < a->n; i++) {
		if (a->port[i] != b->port[i] || strcmp(a->service[i], b->service[i]) != 0) {
			return false;
		}
	}
	return true;
}

static void log_table(const struct table *t)
{
	char line[96];
	int len = 0;

	for (int i = 0; i < t->n && len < (int)sizeof(line); i++) {
		len += snprintf(&line[len], sizeof(line) - len, " %s._tcp:%u", t->service[i],
				sys_be16_to_cpu(t->port[i]));
	}
	LOG_INF("DNS-SD as %s:%s", t->instance, t->n > 0 ? line : " nothing");
}

int hwtr_dnssd_apply(const struct hwtr_dnssd_desc *d)
{
	struct table *next;
	int ret;

	if (d->nsvc > HWTR_DNSSD_SERVICES || d->txt_len > sizeof(next->txt)) {
		return -E2BIG;
	}

	k_mutex_lock(&lock, K_FOREVER);
	next = live == &tables[0] ? &tables[1] : &tables[0];
	memset(next, 0, sizeof(*next));
	strncpy(next->instance, net_hostname_get(), sizeof(next->instance) - 1);
	for (int i = 0; i < d->nsvc; i++) {
		strncpy(next->service[i], d->svc[i].name, sizeof(next->service[i]) - 1);
		next->port[i] = sys_cpu_to_be16(d->svc[i].port);
		next->rec[i] = (struct dns_sd_rec){
			.instance = next->instance,
			.service = next->service[i],
			.proto = "_tcp",
			.domain = "local",
			.text = (const char *)next->txt,
			.text_size = d->txt_len,
			.port = &next->port[i],
		};
	}
	memcpy(next->txt, d->txt, d->txt_len);
	next->txt_len = d->txt_len;
	next->n = d->nsvc;

	if (same(live, next)) {
		k_mutex_unlock(&lock);
		return 0;
	}
	ret = next->n > 0 ? mdns_responder_set_ext_records(next->rec, next->n)
			  : mdns_responder_set_ext_records(NULL, 0);
	if (ret == 0) {
		live = next;
		log_table(next);
	}
	k_mutex_unlock(&lock);

	return ret == 0 ? 1 : ret;
}

int hwtr_dnssd_records(const struct dns_sd_rec **recs)
{
	int n;

	k_mutex_lock(&lock, K_FOREVER);
	n = live != NULL ? live->n : 0;
	*recs = n > 0 ? live->rec : NULL;
	k_mutex_unlock(&lock);

	return n;
}

static void refresh_handler(struct k_work *work)
{
	struct hwtr_dnssd_desc d = {0};

	ARG_UNUSED(work);

	fill_cb(&d);
	(void)hwtr_dnssd_apply(&d);
	k_work_reschedule(&refresh_work, K_MSEC(CONFIG_HWTR_DNSSD_REFRESH_MS));
}

int hwtr_dnssd_start(hwtr_dnssd_fill_t fill)
{
	if (fill == NULL) {
		return -EINVAL;
	}
	fill_cb = fill;
	k_work_reschedule(&refresh_work, K_NO_WAIT);

	return 0;
}

void hwtr_dnssd_refresh(void)
{
	if (fill_cb != NULL) {
		k_work_reschedule(&refresh_work, K_NO_WAIT);
	}
}
