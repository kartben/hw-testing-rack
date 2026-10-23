/*
 * The node's DATA x4 ports (src/ports.c) against an emulated board: the
 * start one port at a time, the admission rule on the node's meter, a
 * latched fault, DUT_5V off and on (no I2C while off, the chips set up
 * again), RESET/BOOT (held while a port is off), a board that stops
 * answering and comes back, the shedding on the meter's ALERT or the poll,
 * the budget without a meter, and a port's VBUS while it is off.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/ztest.h>

#include "bay.h"
#include "emul.h"

/* io 0 (0x20): port 1 RST 0, BOOT 1, EN 2, FLT 3; port 2 EN 4, FLT 5, BOOT 6, RST 7; io 1 the same */
#define EN_A  BIT(2)
#define EN_B  BIT(4)
#define FLT_A 3
#define LINES (BIT(0) | BIT(1) | BIT(6) | BIT(7))
/* Both ports off: EN, RESET and BOOT outputs, low */
#define HELD  ((uint8_t)~(EN_A | EN_B | LINES))

static bool dut_on = true;
static int on_after_150ms, on_after_450ms;

/* --- What ports.c needs from the rest of the node --------------------------- */

bool dut_power_get(void)
{
	return dut_on;
}

int usb_host_port_device(uint8_t hub_port, uint16_t *vid, uint16_t *pid)
{
	ARG_UNUSED(hub_port);
	ARG_UNUSED(vid);
	ARG_UNUSED(pid);
	return -ENODEV;
}

/* --- Helpers ---------------------------------------------------------------- */

static int ports_on(void)
{
	struct port_info pi;
	int n = 0;

	for (int i = 1; i <= 4; i++) {
		if (ports_info(i, &pi) == 0 && pi.on) {
			n++;
		}
	}
	return n;
}

static bool port_on(int slot)
{
	struct port_info pi;

	return ports_info(slot, &pi) == 0 && pi.on;
}

static void *suite_setup(void)
{
	zassert_ok(ports_init());
	/* Set up 5 ms after init, then one port every 300 ms */
	k_sleep(K_MSEC(150));
	on_after_150ms = ports_on();
	k_sleep(K_MSEC(300));
	on_after_450ms = ports_on();
	k_sleep(K_MSEC(1000));
	return NULL;
}

static void before(void *f)
{
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
	}
	for (uint8_t a = 0x41; a <= 0x45; a++) {
		if (a != 0x42) {
			emul_ina_ma(a, 0);
		}
	}
	for (int i = 1; i <= 4; i++) {
		(void)ports_power(i, true, NULL);
	}
}

/* --- Tests ------------------------------------------------------------------ */

ZTEST(ports, test_1_start)
{
	zassert_equal(ports_count(), 4);
	zassert_equal(on_after_150ms, 1, "one port at a time: %d on after 150 ms", on_after_150ms);
	zassert_equal(on_after_450ms, 2, "%d on after 450 ms", on_after_450ms);
	zassert_equal(ports_on(), 4);
	/* EN outputs, high; everything else an input (RESET, BOOT released) */
	for (int io = 0; io < 2; io++) {
		zassert_equal(emul_io_reg(io, 3), (uint8_t)~(EN_A | EN_B));
		zassert_equal(emul_io_reg(io, 1) & (EN_A | EN_B), EN_A | EN_B);
	}
	zassert_equal(emul_ina_config(0x41), 0x4527, "INA226 averaging set");
	zassert_equal(emul_ina_config(0x45), 0x4527);
	/* The v2's MARK (TCA9534A P7) an output, low; the other pins left inputs */
	zassert_equal(emul_io_reg(2, 3), 0x7F);
	zassert_equal(emul_io_reg(2, 1) & BIT(7), 0);
	/* The node's ALERT on its shunt over 1250 mA: 62.5 mV across 50 mOhm, 2.5 uV/LSB */
	zassert_equal(emul_ina_reg(0x40, 0x07), 25000);
	zassert_equal(emul_ina_reg(0x40, 0x06), 0x8000, "SOL, not latched");
}

ZTEST(ports, test_2_admission)
{
	struct port_info pi;
	int32_t others = 0;

	zassert_ok(ports_power(2, false, NULL));
	zassert_equal(emul_io_reg(0, 1) & EN_B, 0);
	/* Off: its RESET (7) and BOOT (6) outputs, low */
	zassert_equal(emul_io_reg(0, 3) & (BIT(6) | BIT(7)), 0);
	zassert_equal(emul_io_reg(0, 1) & (BIT(6) | BIT(7)), 0);

	/* The board 300 mA, ports 1 and 3 800 mA: with 100 mA kept for a start, past 1150 */
	emul_ina_ma(0x41, 400);
	emul_ina_ma(0x44, 400);
	zassert_equal(ports_power(2, true, &others), -EBUSY);
	zassert_equal(others, 1100, "the bay draws %d mA", others);
	zassert_equal(emul_io_reg(0, 1) & EN_B, 0, "refused: EN stays low");
	zassert_ok(ports_info(2, &pi));
	zassert_false(pi.on);
	zassert_false(pi.wanted, "a refused port does not come on later by itself");

	emul_ina_ma(0x41, 100);
	zassert_ok(ports_power(2, true, &others));
	zassert_equal(emul_io_reg(0, 1) & EN_B, EN_B);
	zassert_equal(emul_io_reg(0, 3) & (BIT(6) | BIT(7)), BIT(6) | BIT(7), "lines released");
}

ZTEST(ports, test_3_fault)
{
	struct port_info pi;

	zassert_equal(emul_io_reg(1, 1) & EN_A, EN_A, "port 3 on");
	emul_io_pin(1, FLT_A, false);
	k_sleep(K_MSEC(250));
	zassert_ok(ports_info(3, &pi));
	zassert_false(pi.on);
	zassert_true(pi.latched);
	zassert_true(pi.faults >= 1);
	zassert_equal(emul_io_reg(1, 1) & EN_A, 0, "EN low after a fault");
	zassert_equal(emul_io_reg(1, 3) & (BIT(0) | BIT(1)), 0, "RESET and BOOT held");

	emul_io_pin(1, FLT_A, true);
	zassert_ok(ports_power(3, true, NULL));
	zassert_ok(ports_info(3, &pi));
	zassert_true(pi.on);
	zassert_false(pi.latched);
}

ZTEST(ports, test_4_dut5v_cycle)
{
	int before_off;

	/* Every EN low while the chips still answer */
	ports_dut_power(false);
	zassert_equal(emul_io_reg(0, 1) & (EN_A | EN_B), 0);
	zassert_equal(emul_io_reg(1, 1) & (EN_A | EN_B), 0);
	dut_on = false;
	emul_power(false);

	/* No I2C to the board while DUT_5V is off */
	before_off = emul_offline();
	k_sleep(K_MSEC(1000));
	zassert_equal(emul_offline(), before_off, "%d transfers to the unpowered board",
		      emul_offline() - before_off);

	/* Back on: the chips at their defaults, set up again, every port off, then one by one */
	emul_power(true);
	dut_on = true;
	ports_dut_power(true);
	k_sleep(K_MSEC(50));
	zassert_equal(emul_ina_config(0x43), 0x4527, "INA226 set up again");
	zassert_equal(emul_io_reg(1, 3), HELD, "ports 3 and 4 off, RESET and BOOT held");
	zassert_equal(emul_io_reg(1, 1), 0);
	zassert_equal(ports_on(), 1, "%d ports on 50 ms after DUT_5V on", ports_on());
	k_sleep(K_MSEC(1200));
	zassert_equal(ports_on(), 4);
}

ZTEST(ports, test_5_reset_boot)
{
	uint8_t log[16];
	int n;

	(void)emul_io_cfg_log(0, log, ARRAY_SIZE(log));

	/* RESET: an output (low) for the pulse, then an input again */
	zassert_ok(ports_reset_pulse(1, K_MSEC(10)));
	n = emul_io_cfg_log(0, log, ARRAY_SIZE(log));
	zassert_equal(n, 2);
	zassert_equal(log[0] & BIT(0), 0, "RESET asserted");
	zassert_equal(log[1] & BIT(0), BIT(0), "RESET released");
	zassert_equal(emul_io_reg(0, 1) & BIT(0), 0, "its output register bit stays 0");

	/* BOOT held across a RESET pulse (port 2: BOOT 6, RESET 7) */
	zassert_ok(ports_boot(2, false, NULL));
	n = emul_io_cfg_log(0, log, ARRAY_SIZE(log));
	zassert_equal(n, 4);
	zassert_equal(log[0] & (BIT(6) | BIT(7)), BIT(7), "BOOT first");
	zassert_equal(log[1] & (BIT(6) | BIT(7)), 0, "then RESET");
	zassert_equal(log[2] & (BIT(6) | BIT(7)), BIT(7), "RESET released");
	zassert_equal(log[3] & (BIT(6) | BIT(7)), BIT(6) | BIT(7), "BOOT released");

	/* BOOT held across a power cycle of the port: off holds both, on releases RESET only */
	zassert_ok(ports_boot(2, true, NULL));
	n = emul_io_cfg_log(0, log, ARRAY_SIZE(log));
	zassert_equal(n, 3);
	zassert_equal(log[0] & (BIT(6) | BIT(7)), 0, "off: both held");
	zassert_equal(log[1] & (BIT(6) | BIT(7)), BIT(7), "on: RESET released, BOOT held");
	zassert_equal(log[2] & (BIT(6) | BIT(7)), BIT(6) | BIT(7), "then BOOT released");
	zassert_equal(emul_io_reg(0, 1) & EN_B, EN_B, "port 2 back on");

	/* Switched on: BOOT released first, then RESET */
	zassert_ok(ports_power(2, false, NULL));
	(void)emul_io_cfg_log(0, log, ARRAY_SIZE(log));
	zassert_ok(ports_power(2, true, NULL));
	n = emul_io_cfg_log(0, log, ARRAY_SIZE(log));
	zassert_equal(n, 2);
	zassert_equal(log[0] & (BIT(6) | BIT(7)), BIT(6), "BOOT first");
	zassert_equal(log[1] & (BIT(6) | BIT(7)), BIT(6) | BIT(7), "then RESET");

	/* An off port's lines stay held */
	zassert_ok(ports_power(2, false, NULL));
	zassert_equal(ports_reset_pulse(2, K_MSEC(10)), -EAGAIN);
	zassert_equal(emul_io_reg(0, 3) & (BIT(6) | BIT(7)), 0);
}

ZTEST(ports, test_6_board_gone)
{
	/* The lead pulled out with DUT_5V on: three polls without an answer */
	emul_power(false);
	k_sleep(K_MSEC(500));
	zassert_equal(ports_count(), 0, "a one-port node while the board is gone");

	/* Back: found again at the next probe, its ports on one by one */
	emul_power(true);
	k_sleep(K_MSEC(3500));
	zassert_equal(ports_count(), 4);
	zassert_equal(ports_on(), 4);
}

ZTEST(ports, test_7_shed)
{
	struct port_info pi;

	/* Port 2 the last one on; every port 200 mA, the bay 1100 mA */
	zassert_ok(ports_power(2, false, NULL));
	zassert_ok(ports_power(2, true, NULL));
	for (uint8_t a = 0x41; a <= 0x45; a++) {
		if (a != 0x42) {
			emul_ina_ma(a, 200);
		}
	}
	k_sleep(K_MSEC(150));
	zassert_equal(ports_on(), 4);

	/* Port 1 goes to 400 mA: 1300 mA, the meter's ALERT; the last one on goes, not port 1 */
	emul_ina_ma(0x41, 400);
	k_sleep(K_MSEC(5));
	zassert_ok(ports_info(2, &pi));
	zassert_false(pi.on, "shed within ms of the ALERT");
	zassert_true(pi.wanted, "still wanted");
	zassert_true(port_on(1));
	k_sleep(K_MSEC(100));
	zassert_equal(ports_on(), 3, "the bay back under 1250 mA: one port shed");

	/* 1100 mA + the 200 mA it drew: no room yet; port 1 at 100 mA: back */
	k_sleep(K_MSEC(1200));
	zassert_false(port_on(2));
	emul_ina_ma(0x41, 100);
	k_sleep(K_MSEC(1200));
	zassert_true(port_on(2), "back once the budget has room");

	/* No ALERT wired (the stand-ins): the poll sheds */
	emul_alert(false);
	emul_ina_ma(0x41, 400);
	k_sleep(K_MSEC(150));
	zassert_false(port_on(2), "shed by the poll");
	zassert_equal(ports_on(), 3);
}

ZTEST(ports, test_8_no_meter)
{
	int32_t others = 0;

	/* No node meter: the ports' sum plus 500 mA for the board, plus 100 mA, within 1150 */
	emul_meter(false);
	zassert_ok(ports_power(2, false, NULL));
	emul_ina_ma(0x41, 300);
	emul_ina_ma(0x44, 200);
	zassert_ok(ports_power(2, true, &others));

	zassert_ok(ports_power(2, false, NULL));
	emul_ina_ma(0x44, 300);
	zassert_equal(ports_power(2, true, &others), -EBUSY);
	zassert_equal(others, 1100, "300 + 300 mA and the board's 500: %d mA", others);
}

ZTEST(ports, test_9_vbus)
{
	struct port_info pi;
	int64_t t;

	/* A board powered from elsewhere on port 2 (4.4 V): EN refused, the port waits for it to go */
	zassert_ok(ports_power(2, false, NULL));
	emul_port_vbus(2, 4400, 0);
	zassert_equal(ports_power(2, true, NULL), -EALREADY);
	zassert_equal(emul_io_reg(0, 1) & EN_B, 0);
	zassert_ok(ports_info(2, &pi));
	zassert_true(pi.wanted);
	emul_port_vbus(2, 0, 0);
	k_sleep(K_MSEC(1200));
	zassert_true(port_on(2), "on once its VBUS has gone");

	/* The port's own charge, nothing on it (1.8 V): not a source, EN allowed */
	zassert_ok(ports_power(2, false, NULL));
	emul_port_vbus(2, 1800, 0);
	zassert_ok(ports_power(2, true, NULL));

	/* A power cycle waits for VBUS under 1 V: 5 V to 0 in 300 ms, under 1 V after 241 ms */
	emul_port_vbus(2, 0, 300);
	t = k_uptime_get();
	zassert_ok(ports_power_cycle(2, K_NO_WAIT, NULL));
	t = k_uptime_get() - t;
	zassert_true(t >= 220 && t < 600, "off %lld ms", t);
	zassert_true(port_on(2));

	/* Nothing on it to discharge it: the timeout (500 ms here), then back on */
	emul_port_vbus(2, 1800, 0);
	t = k_uptime_get();
	zassert_ok(ports_power_cycle(2, K_NO_WAIT, NULL));
	t = k_uptime_get() - t;
	zassert_true(t >= 500 && t < 900, "off %lld ms", t);
	zassert_true(port_on(2));
}

ZTEST_SUITE(ports, NULL, suite_setup, before, NULL, NULL);
