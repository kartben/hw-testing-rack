/*
 * The logic analyzer relay (src/analyzer.c) against gusmanb's analyzer
 * emulated on the virtual USB bus (cdc_emu.c): the bytes both ways, a long
 * stream to a slow page, what happens with no page, one page at a time, the
 * switch to USB/IP and back (a stand-in class takes the device meanwhile) and
 * an analyzer unplugged under a page.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/usb/usbh.h>
#include <zephyr/ztest.h>

#include <usbh_class.h>

#include "bay.h"
#include "cdc_emu.h"

#define IP1 0x0a000001U
#define IP2 0x0a000002U

USBH_CONTROLLER_DEFINE(test_uhs_ctx, DEVICE_DT_GET(DT_NODELABEL(zephyr_uhc0)));

/* --- USB/IP's stand-in: takes what the analyzer class leaves -------------------- */

static atomic_t usbip_binds;
static atomic_t usbip_removals;

static int usbip_init(struct usbh_class_data *const c_data)
{
	ARG_UNUSED(c_data);

	return 0;
}

static int usbip_probe(struct usbh_class_data *const c_data, struct usb_device *const udev,
		       const uint8_t iface)
{
	ARG_UNUSED(c_data);
	ARG_UNUSED(udev);

	if (iface != USBH_CLASS_IFNUM_DEVICE) {
		return -ENOTSUP;
	}
	atomic_inc(&usbip_binds);

	return 0;
}

static int usbip_removed(struct usbh_class_data *const c_data)
{
	ARG_UNUSED(c_data);
	atomic_inc(&usbip_removals);

	return 0;
}

static struct usbh_class_api usbip_api = {
	.init = usbip_init,
	.probe = usbip_probe,
	.removed = usbip_removed,
};

/* Sorts after "analyzer", as usbip_0... in the node */
USBH_DEFINE_CLASS(usbip_stand_in, &usbip_api, NULL, NULL);

/* --- The DATA board (src/ports.c, not in this test): a DATA x4 unless a test says - */

static enum data_board board = DATA_X4;

enum data_board ports_board(void)
{
	return board;
}

/* --- The page's stand-in ---------------------------------------------------------- */

struct test_page {
	struct analyzer_page page;
	uint8_t got[24576];      /* what the analyzer sent */
	size_t got_len;
	const uint8_t *to_send;  /* what the page sends, handed out once */
	size_t to_send_len;
	int delay_ms;            /* a slow page */
	bool closed;
};

static int page_send(struct analyzer_page *p, const uint8_t *data, size_t len)
{
	struct test_page *t = CONTAINER_OF(p, struct test_page, page);
	size_t n = MIN(len, sizeof(t->got) - t->got_len);

	memcpy(&t->got[t->got_len], data, n);
	t->got_len += n;
	k_msleep(t->delay_ms);

	return len;
}

static int page_recv(struct analyzer_page *p, uint8_t *buf, size_t size)
{
	struct test_page *t = CONTAINER_OF(p, struct test_page, page);
	size_t n = MIN(size, t->to_send_len);

	memcpy(buf, t->to_send, n);
	t->to_send += n;
	t->to_send_len -= n;

	return n;
}

static void page_close(struct analyzer_page *p)
{
	CONTAINER_OF(p, struct test_page, page)->closed = true;
}

static struct test_page pages[3];

static struct test_page *new_page(int i)
{
	pages[i] = (struct test_page){
		.page = {.send = page_send, .recv = page_recv, .close = page_close},
	};

	return &pages[i];
}

/* --- Helpers ------------------------------------------------------------------------ */

#define SOON(cond, ms)                                                                         \
	({                                                                                         \
		int64_t _end = k_uptime_get() + (ms);                                              \
		while (!(cond) && k_uptime_get() < _end) {                                         \
			k_msleep(5);                                                               \
		}                                                                                  \
		(cond);                                                                            \
	})

/* analyzer_json() says this within ms */
static bool json_soon(const char *what, int ms)
{
	static char json[320];

	for (int64_t end = k_uptime_get() + ms; k_uptime_get() <= end; k_msleep(10)) {
		zassert_true(analyzer_json(json, sizeof(json)) > 0);
		if (strstr(json, what) != NULL) {
			return true;
		}
	}
	printk("JSON: %s\n", json);
	return false;
}

/* Plugged in and taken by the relay: DTR and RTS set */
static void plug(uint32_t line_sets)
{
	zassert_ok(cdc_emu_plug());
	zassert_true(SOON(cdc.line_sets == line_sets, 2000), "DTR never set");
	zassert_equal(cdc.line_state, 0x0003, "DTR and RTS");
}

static void *analyzer_setup(void)
{
	zassert_ok(usbh_init(&test_uhs_ctx));
	zassert_ok(usbh_enable(&test_uhs_ctx));
	zassert_ok(cdc_emu_init());

	return NULL;
}

static void analyzer_before(void *fixture)
{
	ARG_UNUSED(fixture);

	/* Whatever the last test left plugged in goes */
	(void)cdc_emu_unplug();
	k_msleep(100);
	cdc_emu_reset();
	zassert_ok(analyzer_set_owner(ANALYZER_PAGE));
	atomic_clear(&usbip_binds);
	atomic_clear(&usbip_removals);
	board = DATA_X4;
}

/* --- Tests ---------------------------------------------------------------------------- */

ZTEST(analyzer, test_1_both_ways)
{
	static const uint8_t id_request[] = {0x55, 0xaa, 0x00, 0xaa, 0x55};
	struct test_page *p = new_page(0);

	zassert_equal(analyzer_attach(&p->page, IP1), -ENODEV, "no analyzer yet");
	plug(1);
	zassert_ok(analyzer_attach(&p->page, IP1));
	zassert_true(json_soon("\"owner\":\"page\",\"present\":true,\"busid\":\"1-1\","
			       "\"page\":{\"ip\":\"10.0.0.1\"", 10));

	/* The page asks who it is; the analyzer's answer comes back whole */
	cdc.answer_id = true;
	p->to_send = id_request;
	p->to_send_len = sizeof(id_request);
	zassert_true(SOON(p->got_len == strlen(cdc_emu_id), 2000), "got %u", p->got_len);
	zassert_mem_equal(p->got, cdc_emu_id, strlen(cdc_emu_id));
	zassert_equal(cdc.got_len, sizeof(id_request));
	zassert_mem_equal(cdc.got, id_request, sizeof(id_request));
	zassert_true(json_soon("\"to_device\":5,", 10));
	zassert_false(p->closed);
}

ZTEST(analyzer, test_2_stream_to_a_slow_page)
{
	static uint8_t capture[20000];
	struct test_page *p = new_page(0);

	for (size_t i = 0; i < sizeof(capture); i++) {
		capture[i] = (uint8_t)(i * 7 + (i >> 8));
	}
	plug(1);
	zassert_ok(analyzer_attach(&p->page, IP1));

	/* 2 ms a chunk: the analyzer waits, nothing is lost or reordered */
	p->delay_ms = 2;
	zassert_ok(cdc_emu_send(capture, sizeof(capture)));
	zassert_true(SOON(p->got_len == sizeof(capture), 5000), "got %u", p->got_len);
	zassert_mem_equal(p->got, capture, sizeof(capture));
	zassert_true(cdc_emu_sent());
	zassert_true(json_soon("\"dropped\":0,", 10));
	zassert_false(p->closed);
}

ZTEST(analyzer, test_3_no_page)
{
	static uint8_t data[3000];

	/* Read and dropped: the analyzer is never left waiting */
	plug(1);
	zassert_ok(cdc_emu_send(data, sizeof(data)));
	zassert_true(SOON(cdc_emu_sent(), 2000));
	zassert_true(json_soon("\"page\":null,", 10));
	zassert_true(json_soon("\"dropped\":3000,", 500));
}

ZTEST(analyzer, test_4_one_page_at_a_time)
{
	struct test_page *a = new_page(0), *b = new_page(1), *c = new_page(2);

	plug(1);
	zassert_ok(analyzer_attach(&a->page, IP1));
	/* Another address waits; the same one is the page reloaded */
	zassert_equal(analyzer_attach(&b->page, IP2), -EBUSY);
	zassert_false(a->closed);
	zassert_ok(analyzer_attach(&c->page, IP1));
	zassert_true(a->closed);
	zassert_false(b->closed);
	zassert_false(c->closed);
}

ZTEST(analyzer, test_5_usbip_and_back)
{
	static const uint8_t data[100] = {1, 2, 3};
	struct test_page *p = new_page(0);

	plug(1);
	zassert_ok(analyzer_attach(&p->page, IP1));
	zassert_equal(atomic_get(&usbip_binds), 0, "the relay has it");

	/* To USB/IP: the page is closed, the other class takes the device */
	zassert_ok(analyzer_set_owner(ANALYZER_USBIP));
	zassert_true(SOON(p->closed, 500));
	zassert_equal(atomic_get(&usbip_binds), 1);
	zassert_equal(analyzer_attach(&new_page(1)->page, IP1), -EACCES);
	zassert_true(json_soon("\"owner\":\"usbip\",\"present\":true,", 10));

	/* The relay no longer reads it */
	zassert_ok(cdc_emu_send(data, sizeof(data)));
	k_msleep(200);
	zassert_false(cdc_emu_sent());

	/* Back to the page: taken from USB/IP, DTR set again, read again */
	zassert_ok(analyzer_set_owner(ANALYZER_PAGE));
	zassert_equal(atomic_get(&usbip_removals), 1);
	zassert_true(SOON(cdc.line_sets == 2, 2000));
	zassert_true(SOON(cdc_emu_sent(), 2000));
	zassert_ok(analyzer_attach(&new_page(2)->page, IP1));
}

ZTEST(analyzer, test_6_unplugged)
{
	struct test_page *p = new_page(0);

	plug(1);
	zassert_ok(analyzer_attach(&p->page, IP1));
	zassert_ok(cdc_emu_unplug());
	zassert_true(SOON(p->closed, 1000));
	zassert_true(json_soon("\"present\":false,", 500));
	zassert_equal(analyzer_attach(&new_page(1)->page, IP1), -ENODEV);

	/* Back: taken again */
	plug(2);
	zassert_ok(analyzer_attach(&new_page(2)->page, IP1));
}

ZTEST(analyzer, test_7_data_x6)
{
	/* On a DATA x6 the co-processor's hub port is its USB-C 6: whatever is there is USB/IP's */
	board = DATA_X6;
	zassert_ok(cdc_emu_plug());
	zassert_true(SOON(atomic_get(&usbip_binds) == 1, 2000), "USB/IP never took it");
	zassert_equal(cdc.line_sets, 0, "the relay set its DTR");
	zassert_equal(analyzer_attach(&new_page(0)->page, IP1), -ENODEV);
}

ZTEST_SUITE(analyzer, NULL, analyzer_setup, analyzer_before, NULL, NULL);
