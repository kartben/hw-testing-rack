/*
 * DNS-SD (lib/dnssd.c) on native_sim: the records the mDNS responder gets,
 * valid by its own rules (dns_sd_rec_is_valid); new records only when
 * something changed; the periodic refresh following the application.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/net/hostname.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/ztest.h>

#include <hwtr/dnssd.h>

#include "dns_sd.h"

/* What the "application" listens on, for fill() */
static uint16_t usbip_port;
static const char *mode = "usbip";
static int fills;

static void fill(struct hwtr_dnssd_desc *d)
{
	fills++;
	hwtr_dnssd_service(d, "_http", 80);
	hwtr_dnssd_service(d, "_usbip", usbip_port);
	hwtr_dnssd_txt(d, "id", "b3");
	hwtr_dnssd_txt(d, "mode", mode);
}

static const struct dns_sd_rec *find(const char *service)
{
	const struct dns_sd_rec *recs;
	int n = hwtr_dnssd_records(&recs);

	for (int i = 0; i < n; i++) {
		if (strcmp(recs[i].service, service) == 0) {
			return &recs[i];
		}
	}
	return NULL;
}

ZTEST(dnssd, test_1_txt)
{
	struct hwtr_dnssd_desc d = {0};
	char big[300];

	hwtr_dnssd_txt(&d, "id", "b3");
	hwtr_dnssd_txt(&d, "pos", "");   /* left out */
	hwtr_dnssd_txt(&d, "fw", NULL);  /* left out */
	hwtr_dnssd_txt(&d, "fw", "0.5.0");
	zassert_equal(d.txt_len, 1 + 5 + 1 + 8);
	zassert_mem_equal(d.txt, "\x05id=b3\x08" "fw=0.5.0", d.txt_len);

	/* Over 255 bytes, or past the buffer: left out */
	memset(big, 'x', sizeof(big) - 1);
	big[sizeof(big) - 1] = '\0';
	hwtr_dnssd_txt(&d, "big", big);
	zassert_equal(d.txt_len, 15);
	big[100] = '\0';
	hwtr_dnssd_txt(&d, "a", big);
	hwtr_dnssd_txt(&d, "b", big);
	zassert_equal(d.txt_len, 15 + 103, "the second 102-byte entry does not fit");
}

ZTEST(dnssd, test_2_apply)
{
	struct hwtr_dnssd_desc d = {0};
	const struct dns_sd_rec *recs, *first;

	hwtr_dnssd_service(&d, "_http", 80);
	hwtr_dnssd_service(&d, "_usbip", 0); /* not listening */
	hwtr_dnssd_service(&d, "_rfc2217", 4001);
	hwtr_dnssd_txt(&d, "id", "b3");
	zassert_equal(hwtr_dnssd_apply(&d), 1);
	zassert_equal(hwtr_dnssd_records(&recs), 2, "port 0 is not advertised");
	for (int i = 0; i < 2; i++) {
		zassert_true(dns_sd_rec_is_valid(&recs[i]), "record %d valid", i);
		zassert_str_equal(recs[i].instance, "bay-b3");
		zassert_str_equal(recs[i].proto, "_tcp");
		zassert_str_equal(recs[i].domain, "local");
		zassert_equal(dns_sd_txt_size(&recs[i]), 6);
		zassert_mem_equal(recs[i].text, "\x05id=b3", 6);
	}
	zassert_str_equal(recs[0].service, "_http");
	zassert_equal(sys_be16_to_cpu(*recs[0].port), 80);
	zassert_str_equal(recs[1].service, "_rfc2217");
	zassert_equal(sys_be16_to_cpu(*recs[1].port), 4001);
	first = recs;

	/* The same again: nothing to hand over */
	zassert_equal(hwtr_dnssd_apply(&d), 0);
	(void)hwtr_dnssd_records(&recs);
	zassert_equal_ptr(recs, first, "the same table");

	/* A TXT value, then the hostname: new records, in the other table */
	d.txt_len = 0;
	hwtr_dnssd_txt(&d, "id", "b4");
	zassert_equal(hwtr_dnssd_apply(&d), 1);
	(void)hwtr_dnssd_records(&recs);
	zassert_true(recs != first, "the other table");
	zassert_mem_equal(recs[0].text, "\x05id=b4", 6);
	zassert_ok(net_hostname_set("bay-c1", strlen("bay-c1")));
	zassert_equal(hwtr_dnssd_apply(&d), 1);
	zassert_equal(hwtr_dnssd_records(&recs), 2);
	zassert_str_equal(recs[0].instance, "bay-c1");
	zassert_ok(net_hostname_set("bay-b3", strlen("bay-b3")));

	/* Nothing listening: no records */
	d = (struct hwtr_dnssd_desc){0};
	zassert_equal(hwtr_dnssd_apply(&d), 1);
	zassert_equal(hwtr_dnssd_records(&recs), 0);
	zassert_is_null(recs);
}

ZTEST(dnssd, test_3_refresh)
{
	const struct dns_sd_rec *rec;
	int before;

	usbip_port = 0;
	zassert_ok(hwtr_dnssd_start(fill));
	k_sleep(K_MSEC(20));
	zassert_not_null(find("_http"));
	zassert_is_null(find("_usbip"), "not listening yet");

	/* USB/IP back: within a refresh period */
	usbip_port = 3240;
	k_sleep(K_MSEC(150));
	rec = find("_usbip");
	zassert_not_null(rec);
	zassert_equal(sys_be16_to_cpu(*rec->port), 3240);
	zassert_mem_equal(rec->text, "\x05id=b3\x0a" "mode=usbip", 17);

	/* A refresh asked for: at once, not at the next period */
	mode = "classic";
	usbip_port = 0;
	before = fills;
	hwtr_dnssd_refresh();
	k_sleep(K_MSEC(5));
	zassert_true(fills > before);
	zassert_is_null(find("_usbip"), "classic mode: no USB/IP");
	zassert_mem_equal(find("_http")->text, "\x05id=b3\x0c" "mode=classic", 19);
}

ZTEST_SUITE(dnssd, NULL, NULL, NULL, NULL, NULL);
