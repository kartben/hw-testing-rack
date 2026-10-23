/*
 * DNS-SD (RFC 6763) through the mDNS responder: the services a firmware
 * runs, advertised under its hostname, all with the same TXT record.
 *
 * The application describes what is listening right now (fill); hwtr_dnssd
 * asks it again every CONFIG_HWTR_DNSSD_REFRESH_MS, or at once with
 * hwtr_dnssd_refresh(), and hands the responder new records only when
 * something changed: a service that stops or starts listening, a mode, the
 * hostname, a TXT value.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HWTR_DNSSD_H_
#define HWTR_DNSSD_H_

#include <stddef.h>
#include <stdint.h>

#include <zephyr/net/dns_sd.h>

#define HWTR_DNSSD_SERVICES 4
#define HWTR_DNSSD_TXT_SIZE 160

/* What to advertise; built with the calls below */
struct hwtr_dnssd_desc {
	struct {
		const char *name; /* "_http", "_usbip": TCP */
		uint16_t port;
	} svc[HWTR_DNSSD_SERVICES];
	int nsvc;
	/* TXT: length-prefixed "key=value" strings */
	uint8_t txt[HWTR_DNSSD_TXT_SIZE];
	size_t txt_len;
};

/* A TCP service; port 0 (not listening) is not advertised */
void hwtr_dnssd_service(struct hwtr_dnssd_desc *d, const char *name, uint16_t port);
/* "key=value" in the TXT record; an empty or NULL value is left out */
void hwtr_dnssd_txt(struct hwtr_dnssd_desc *d, const char *key, const char *value);

typedef void (*hwtr_dnssd_fill_t)(struct hwtr_dnssd_desc *d);

/* Advertise what fill() describes, now and every CONFIG_HWTR_DNSSD_REFRESH_MS */
int hwtr_dnssd_start(hwtr_dnssd_fill_t fill);
/* Ask fill() again now: an id, a mode or a listener just changed */
void hwtr_dnssd_refresh(void);
/*
 * Advertise d under the hostname: 1 when the records changed, 0 when they
 * were already these, -E2BIG when d does not fit
 */
int hwtr_dnssd_apply(const struct hwtr_dnssd_desc *d);
/* The records the responder has (until the next change), and how many */
int hwtr_dnssd_records(const struct dns_sd_rec **recs);

#endif /* HWTR_DNSSD_H_ */
