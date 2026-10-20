/*
 * The node's DATA x4 ports (src/ports.c) against an emulated board: the
 * start one port at a time, the admission rule, a latched fault, DUT_5V off
 * and on (no I2C while off, the chips set up again), RESET/BOOT, a board
 * that stops answering and comes back.
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
	dut_on = true;
	for (int io = 0; io < 2; io++) {
		for (int pin = 0; pin < 8; pin++) {
			emul_io_pin(io, pin, true);
		}
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
}

ZTEST(ports, test_2_admission)
{
	struct port_info pi;
	int32_t others = 0;

	zassert_ok(ports_power(2, false, NULL));
	zassert_equal(emul_io_reg(0, 1) & EN_B, 0);

	/* Ports 1 and 3 draw 1050 mA: with 250 mA kept for a start, past 1250 */
	emul_ina_ma(0x41, 600);
	emul_ina_ma(0x44, 450);
	zassert_equal(ports_power(2, true, &others), -EBUSY);
	zassert_equal(others, 1050, "the other ports draw %d mA", others);
	zassert_equal(emul_io_reg(0, 1) & EN_B, 0, "refused: EN stays low");
	zassert_ok(ports_info(2, &pi));
	zassert_false(pi.on);
	zassert_false(pi.wanted, "a refused port does not come on later by itself");

	emul_ina_ma(0x41, 100);
	zassert_ok(ports_power(2, true, &others));
	zassert_equal(emul_io_reg(0, 1) & EN_B, EN_B);
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
	zassert_equal(emul_io_reg(1, 3), (uint8_t)~(EN_A | EN_B), "directions set up again");
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

	/* BOOT held across a power cycle of the port */
	zassert_ok(ports_boot(2, true, NULL));
	n = emul_io_cfg_log(0, log, ARRAY_SIZE(log));
	zassert_equal(n, 2);
	zassert_equal(log[0] & BIT(6), 0);
	zassert_equal(log[1] & BIT(6), BIT(6));
	zassert_equal(emul_io_reg(0, 1) & EN_B, EN_B, "port 2 back on");
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

ZTEST_SUITE(ports, NULL, suite_setup, before, NULL, NULL);
