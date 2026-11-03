/*
 * The DATA x4's pin matrix (src/wires.c) with src/ports.c, the expander's and
 * the crosspoints' drivers, on the emulated board: what each pin does to the
 * emulated CH446Q (chip, X, Y), break-before-make, a port's pins open while
 * it is off, the chips set up again after DUT_5V, MARK in the middle of a
 * change, and POST /api/wires's body.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/ztest.h>

#include "bay.h"
#include "emul.h"

#define NONE (-1)

static bool dut_on = true;

/* --- What ports.c needs from the rest of the node --------------------------- */

bool dut_power_get(void)
{
	return dut_on;
}

void dut_lead_lost(enum dut_lead why)
{
	ARG_UNUSED(why);
	ztest_test_fail();
}

bool bay_rack_grant(struct rack_grant *g)
{
	ARG_UNUSED(g);
	ztest_test_fail();
	return false;
}

int usb_host_port_device(uint8_t hub_port, uint16_t *vid, uint16_t *pid)
{
	ARG_UNUSED(hub_port);
	ARG_UNUSED(vid);
	ARG_UNUSED(pid);
	return -ENODEV;
}

/* --- The board's wiring (data-x4.dtsi): which switch a pin and a bus close ----- */

/* The X line of P1-P8: ports 1 and 3, then 2 and 4 (port_pins) */
static const uint8_t pin_x[2][8] = {{15, 7, 9, 11, 14, 6, 8, 10}, {12, 4, 2, 0, 13, 5, 3, 1}};
/* Buses A-H on the Y lines: Y0-Y7 are D C B A E F G H */
static const uint8_t bus_y[8] = {3, 2, 1, 0, 4, 5, 6, 7};

static struct emul_xp_event sw(int port, int pin, char bus, bool on)
{
	return (struct emul_xp_event){(port - 1) / 2, pin_x[(port - 1) % 2][pin - 1], bus_y[bus - 'A'],
				      on};
}

static void want(int8_t w[WIRES_PINS], int port, int pin, char bus)
{
	w[(port - 1) * WIRES_PORT_PINS + pin - 1] = bus == 0 ? NONE : bus - 'A';
}

static void none(int8_t w[WIRES_PINS])
{
	memset(w, NONE, WIRES_PINS);
}

/* The emulated chips hold exactly what w asks for, every port being on */
static void chips_hold(const int8_t w[WIRES_PINS])
{
	uint8_t y[2][16] = {0};

	for (int p = 0; p < WIRES_PINS; p++) {
		if (w[p] != NONE) {
			struct emul_xp_event e = sw(p / 8 + 1, p % 8 + 1, 'A' + w[p], true);

			y[e.chip][e.x] |= BIT(e.y);
		}
	}
	for (int c = 0; c < 2; c++) {
		for (int x = 0; x < 16; x++) {
			zassert_equal(emul_xp_y(c, x), y[c][x], "chip %d X%d: 0x%02x, not 0x%02x", c, x,
				      emul_xp_y(c, x), y[c][x]);
		}
	}
}

static bool same(struct emul_xp_event a, struct emul_xp_event b)
{
	return a.chip == b.chip && a.x == b.x && a.y == b.y && a.on == b.on;
}

static int ports_on(void)
{
	struct port_info pi;
	int n = 0;

	for (int i = 1; i <= 4; i++) {
		n += ports_info(i, &pi) == 0 && pi.on;
	}
	return n;
}

static void *suite_setup(void)
{
	zassert_ok(ports_init());
	k_sleep(K_MSEC(1500));
	return NULL;
}

static void before(void *f)
{
	struct emul_xp_event log[64];
	int8_t w[WIRES_PINS];

	ARG_UNUSED(f);

	emul_power(true);
	emul_meter(true);
	emul_alert(true);
	emul_board_ma(300);
	dut_on = true;
	for (int io = 0; io < 2; io++) {
		for (int pin = 0; pin < 8; pin++) {
			emul_io_pin(io, pin, true);
		}
	}
	for (int i = 1; i <= 4; i++) {
		emul_port_vbus(i, 0, 0);
		(void)ports_power(i, true, NULL);
	}
	zassert_true(ports_on() == 4, "%d ports on", ports_on());
	none(w);
	zassert_true(wires_set(w) >= 0);
	(void)emul_xp_log(log, ARRAY_SIZE(log));
}

/* --- Tests ------------------------------------------------------------------ */

ZTEST(wires, test_1_start)
{
	static char json[1024];

	/* The crosspoints' driver started with the board: RST pulsed, every switch open */
	zassert_true(emul_xp_resets() >= 1);
	for (int c = 0; c < 2; c++) {
		for (int x = 0; x < 16; x++) {
			zassert_equal(emul_xp_y(c, x), 0);
		}
	}
	zassert_true(wires_json(json, sizeof(json), -1) > 0);
	zassert_not_null(strstr(json, "\"matrix\":true,\"error\":null,"), "%s", json);
	zassert_not_null(strstr(json, "{\"port\":4,\"on\":true,\"vref_mv\":null,\"held\":false}"),
			 "%s", json);
}

ZTEST(wires, test_2_wire_then_move)
{
	struct emul_xp_event log[64];
	int8_t w[WIRES_PINS];
	int n;

	/* A UART from B3.2's P1 to B3.3's P2 on bus A */
	none(w);
	want(w, 2, 1, 'A');
	want(w, 3, 2, 'A');
	zassert_equal(wires_set(w), 2);
	n = emul_xp_log(log, ARRAY_SIZE(log));
	zassert_equal(n, 2);
	zassert_true(same(log[0], sw(2, 1, 'A', true)), "U7 X12 Y3");
	zassert_true(same(log[1], sw(3, 2, 'A', true)), "U8 X7 Y3");
	chips_hold(w);

	/* Both moved to bus B: every switch opens before any closes */
	want(w, 2, 1, 'B');
	want(w, 3, 2, 'B');
	zassert_equal(wires_set(w), 4);
	n = emul_xp_log(log, ARRAY_SIZE(log));
	zassert_equal(n, 4);
	zassert_true(same(log[0], sw(2, 1, 'A', false)));
	zassert_true(same(log[1], sw(3, 2, 'A', false)));
	zassert_true(same(log[2], sw(2, 1, 'B', true)));
	zassert_true(same(log[3], sw(3, 2, 'B', true)));
	chips_hold(w);

	/* The same again: nothing to write */
	zassert_equal(wires_set(w), 0);
	zassert_equal(emul_xp_log(log, ARRAY_SIZE(log)), 0);
	zassert_equal(emul_xp_glitches(), 0);
}

ZTEST(wires, test_3_port_off)
{
	struct emul_xp_event log[64];
	int8_t w[WIRES_PINS], closed[WIRES_PINS];
	static char json[1024];

	none(w);
	want(w, 2, 1, 'A');
	want(w, 3, 2, 'A');
	zassert_equal(wires_set(w), 2);
	(void)emul_xp_log(log, ARRAY_SIZE(log));

	/* B3.2 off: its pin opens first, stays asked for */
	zassert_ok(ports_power(2, false, NULL));
	zassert_equal(emul_xp_log(log, ARRAY_SIZE(log)), 1);
	zassert_true(same(log[0], sw(2, 1, 'A', false)));
	wires_get(NULL, closed);
	zassert_equal(closed[8], NONE);
	zassert_equal(closed[16 + 1], 0);
	zassert_true(wires_json(json, sizeof(json), -1) > 0);
	zassert_not_null(strstr(json, "{\"port\":2,\"pin\":1,\"bus\":\"A\",\"closed\":false}"), "%s",
			 json);
	zassert_not_null(strstr(json, "{\"port\":2,\"on\":false,\"vref_mv\":null,\"held\":true}"),
			 "%s", json);

	/* Back on: back on bus A */
	zassert_ok(ports_power(2, true, NULL));
	zassert_equal(emul_xp_log(log, ARRAY_SIZE(log)), 1);
	zassert_true(same(log[0], sw(2, 1, 'A', true)));
	chips_hold(w);
}

ZTEST(wires, test_4_dut5v_cycle)
{
	struct emul_xp_event log[64];
	int8_t w[WIRES_PINS];
	int before_off;

	none(w);
	want(w, 1, 3, 'C');
	want(w, 4, 3, 'C');
	want(w, 1, 4, 'D');
	want(w, 4, 4, 'D');
	zassert_equal(wires_set(w), 4);
	(void)emul_xp_log(log, ARRAY_SIZE(log));

	/* DUT_5V going off: every switch opens while the chips still answer */
	ports_dut_power(false);
	zassert_equal(emul_xp_log(log, ARRAY_SIZE(log)), 4);
	for (int i = 0; i < 4; i++) {
		zassert_false(log[i].on);
	}
	dut_on = false;
	emul_power(false);
	before_off = emul_offline();
	k_sleep(K_MSEC(500));
	zassert_equal(emul_offline(), before_off, "no I2C to the unpowered board");

	/* Back: the expander written back, the driver's copy cleared, the pins back as the ports come on */
	emul_power(true);
	dut_on = true;
	ports_dut_power(true);
	k_sleep(K_MSEC(1500));
	zassert_equal(ports_on(), 4);
	chips_hold(w);
	zassert_equal(emul_xp_glitches(), 0);
}

static K_THREAD_STACK_DEFINE(marker_stack, 2048);
static struct k_thread marker;
static atomic_t marking;

/* MARK up and down as fast as the node resets B3.1 */
static void marker_fn(void *a, void *b, void *c)
{
	ARG_UNUSED(a);
	ARG_UNUSED(b);
	ARG_UNUSED(c);

	while (atomic_get(&marking)) {
		(void)ports_reset_pulse(1, K_USEC(100));
	}
}

ZTEST(wires, test_5_mark_meanwhile)
{
	struct emul_xp_event log[64];
	int8_t w[WIRES_PINS];
	int n;

	/* Sixteen pins on all eight buses, while MARK moves */
	none(w);
	for (int b = 0; b < 8; b++) {
		want(w, 2, b + 1, 'A' + b);
		want(w, 3, b + 1, 'A' + b);
	}
	atomic_set(&marking, 1);
	k_thread_create(&marker, marker_stack, K_THREAD_STACK_SIZEOF(marker_stack), marker_fn, NULL,
			NULL, NULL, K_PRIO_PREEMPT(5), 0, K_NO_WAIT);
	zassert_equal(wires_set(w), 16);
	n = emul_xp_log(log, ARRAY_SIZE(log));
	atomic_set(&marking, 0);
	k_thread_join(&marker, K_FOREVER);

	/* Exactly the sixteen switches, nothing garbled */
	zassert_equal(n, 16);
	for (int i = 0; i < n; i++) {
		zassert_true(log[i].on);
	}
	chips_hold(w);
	zassert_equal(emul_xp_glitches(), 0);
}

ZTEST(wires, test_6_body)
{
	char names[WIRES_BUSES][WIRES_NAME_LEN];
	int8_t w[WIRES_PINS];
	bool has_pins, has_names;
	const char *why = NULL;
	char body[384];

#define PARSE(s) (strcpy(body, s), wires_parse(body, strlen(body), w, &has_pins, names, &has_names, &why))

	zassert_ok(PARSE("{\"pins\":[{\"port\":2,\"pin\":1,\"bus\":\"A\"},{\"port\":3,\"pin\":8,\"bus\":\"H\"}],"
			 "\"names\":[\"UART\",\"\",\"\",\"\",\"\",\"\",\"\",\"MISO\"]}"));
	zassert_true(has_pins && has_names);
	zassert_equal(w[8], 0);
	zassert_equal(w[23], 7);
	zassert_equal(w[0], NONE);
	zassert_str_equal(names[0], "UART");
	zassert_str_equal(names[7], "MISO");

	/* Open all; names alone */
	zassert_ok(PARSE("{\"pins\":[]}"));
	zassert_true(has_pins && !has_names);
	zassert_equal(w[8], NONE);
	zassert_ok(PARSE("{\"names\":[\"a\",\"b\",\"c\",\"d\",\"e\",\"f\",\"g\",\"h\"]}"));
	zassert_true(!has_pins && has_names);

	/* Refused */
	zassert_equal(PARSE("{\"pins\":[{\"port\":5,\"pin\":1,\"bus\":\"A\"}]}"), -EINVAL);
	zassert_str_equal(why, "port: 1-4, pin: 1-8");
	zassert_equal(PARSE("{\"pins\":[{\"port\":1,\"pin\":1,\"bus\":\"I\"}]}"), -EINVAL);
	zassert_equal(PARSE("{\"pins\":[{\"port\":1,\"pin\":1,\"bus\":\"A\"},{\"port\":1,\"pin\":1,\"bus\":\"B\"}]}"),
		      -EINVAL);
	zassert_str_equal(why, "a pin goes on one bus");
	zassert_equal(PARSE("{\"names\":[\"a\"]}"), -EINVAL);
	zassert_equal(PARSE("{\"names\":[\"<b>\",\"\",\"\",\"\",\"\",\"\",\"\",\"\"]}"), -EINVAL);
#undef PARSE
}

ZTEST_SUITE(wires, NULL, suite_setup, before, NULL, NULL);
