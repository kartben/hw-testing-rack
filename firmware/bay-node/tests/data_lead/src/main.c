/*
 * Node rev B's DATA lead (src/dut.c, src/ports.c) against the emulated
 * DATA x4, powered by the eFuse's enable: the power-on rule of
 * docs/firmware.md.  Off at boot; on only with SCL and SDA high and the
 * node's INA226 answering; ~FLT ignored while the eFuse ramps; off again on a
 * short; the board must answer within a second; off for good on a ~FLT or a
 * board that stops answering, until the next power on.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/gpio/gpio_emul.h>
#include <zephyr/ztest.h>

#include "bay.h"
#include "emul.h"

#define DUT DT_NODELABEL(dut_port)

static const struct gpio_dt_spec en = GPIO_DT_SPEC_GET(DUT, enable_gpios);
static const struct gpio_dt_spec flt = GPIO_DT_SPEC_GET(DUT, fault_gpios);
static const struct gpio_dt_spec scl = GPIO_DT_SPEC_GET_BY_IDX(DUT, bus_gpios, 0);
static const struct gpio_dt_spec sda = GPIO_DT_SPEC_GET_BY_IDX(DUT, bus_gpios, 1);

static bool off_at_boot;

/* --- What dut.c and ports.c need from the rest of the node ------------------ */

void aux_dut_power(bool on)
{
	ARG_UNUSED(on);
}

int usb_host_port_device(uint8_t hub_port, uint16_t *vid, uint16_t *pid)
{
	ARG_UNUSED(hub_port);
	ARG_UNUSED(vid);
	ARG_UNUSED(pid);
	return -ENODEV;
}

/* --- Helpers ---------------------------------------------------------------- */

static bool lead_on(void)
{
	return gpio_emul_output_get(en.port, en.pin) > 0;
}

/* The eFuse's ~FLT (open drain, pulled up): low in a fault */
static void flt_set(bool fault)
{
	(void)gpio_emul_input_set(flt.port, flt.pin, fault ? 0 : 1);
}

static void flt_release_handler(struct k_work *work)
{
	ARG_UNUSED(work);
	flt_set(false);
}

static K_WORK_DELAYABLE_DEFINE(flt_release, flt_release_handler);

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
	zassert_ok(dut_init());
	off_at_boot = !lead_on() && !dut_power_get();
	zassert_ok(ports_init());
	/* On the node they stay the I2C controller's pins: here plain inputs */
	zassert_ok(gpio_pin_configure_dt(&scl, GPIO_INPUT));
	zassert_ok(gpio_pin_configure_dt(&sda, GPIO_INPUT));
	return NULL;
}

static void before(void *f)
{
	ARG_UNUSED(f);

	(void)dut_power_set(false);
	k_work_cancel_delayable(&flt_release);
	flt_set(false);
	(void)gpio_emul_input_set(scl.port, scl.pin, 1);
	(void)gpio_emul_input_set(sda.port, sda.pin, 1);
	emul_vin(20000);
	emul_lead_short(false);
	emul_board(true);
	emul_meter(true);
	emul_board_ma(300);
	for (int io = 0; io < 2; io++) {
		for (int pin = 0; pin < 8; pin++) {
			emul_io_pin(io, pin, true);
		}
	}
	k_sleep(K_MSEC(50));
}

/* --- Tests ------------------------------------------------------------------ */

ZTEST(data_lead, test_1_off_at_boot)
{
	zassert_true(off_at_boot, "the eFuse stays off until the checks pass");
	zassert_equal(ports_count(), 0, "no I2C to an unpowered board");
	zassert_equal(emul_offline(), 0);
}

ZTEST(data_lead, test_2_on)
{
	zassert_ok(dut_power_set(true));
	zassert_true(lead_on());
	zassert_true(dut_power_get());
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_OK);
	/* The board set up, its ports on one at a time */
	k_sleep(K_MSEC(1500));
	zassert_equal(ports_count(), 4);
	zassert_equal(ports_on(), 4);
	zassert_true(lead_on(), "still on: the board answers");

	zassert_ok(dut_power_set(false));
	zassert_false(lead_on());
	zassert_equal(ports_on(), 0);
}

ZTEST(data_lead, test_3_lead_reversed)
{
	/* A lead plugged 1:1 holds SCL near 0.6 V */
	(void)gpio_emul_input_set(scl.port, scl.pin, 0);
	zassert_equal(dut_power_set(true), -EIO);
	zassert_false(lead_on(), "never switched on");
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_BUS);
	zassert_not_null(dut_lead_str(DUT_LEAD_BUS));

	(void)gpio_emul_input_set(scl.port, scl.pin, 1);
	(void)gpio_emul_input_set(sda.port, sda.pin, 0);
	zassert_equal(dut_power_set(true), -EIO);
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_BUS);

	/* Released: on */
	(void)gpio_emul_input_set(sda.port, sda.pin, 1);
	zassert_ok(dut_power_set(true));
	zassert_true(lead_on());
}

ZTEST(data_lead, test_4_meter_missing)
{
	emul_meter(false);
	zassert_equal(dut_power_set(true), -ENODEV);
	zassert_false(lead_on());
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_METER);
}

ZTEST(data_lead, test_5_short)
{
	int32_t mv = -1;

	/* A camera lead in J7: the eFuse limits, ~FLT low, DATA_VIN near 0 */
	emul_lead_short(true);
	flt_set(true);
	zassert_equal(dut_power_set(true), -EIO);
	zassert_false(lead_on(), "off again");
	zassert_equal(dut_lead_state(&mv), DUT_LEAD_SHORT);
	zassert_true(mv < CONFIG_BAY_DATA_VIN_MIN_MV, "%d mV", mv);
	zassert_true(dut_fault_latched());

	/* DATA_VIN too low alone is enough */
	flt_set(false);
	emul_lead_short(false);
	emul_vin(12000);
	zassert_equal(dut_power_set(true), -EIO);
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_SHORT);
}

ZTEST(data_lead, test_6_flt_blanked_while_ramping)
{
	/* ~FLT low while the eFuse is off, high 5 ms after it ramps: ignored */
	flt_set(true);
	k_work_reschedule(&flt_release, K_MSEC(5));
	zassert_ok(dut_power_set(true));
	zassert_true(lead_on());
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_OK);
	zassert_false(dut_fault_active());
}

ZTEST(data_lead, test_7_flt_while_on)
{
	uint32_t faults = dut_fault_count();

	zassert_ok(dut_power_set(true));
	k_sleep(K_MSEC(300));
	zassert_true(ports_on() > 0);

	flt_set(true);
	k_sleep(K_MSEC(10));
	zassert_false(lead_on(), "off at once");
	zassert_false(dut_power_get());
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_FAULT);
	zassert_true(dut_fault_latched());
	zassert_true(dut_fault_count() > faults);
	zassert_equal(ports_on(), 0);

	/* No retry from the firmware, even once ~FLT is high again */
	flt_set(false);
	k_sleep(K_MSEC(300));
	zassert_false(lead_on());

	/* Until the next power on */
	zassert_ok(dut_power_set(true));
	zassert_true(lead_on());
	zassert_false(dut_fault_latched());
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_OK);
}

ZTEST(data_lead, test_8_no_board)
{
	emul_board(false);
	zassert_ok(dut_power_set(true), "DATA_VIN reads right: on");
	zassert_true(lead_on());
	k_sleep(K_MSEC(CONFIG_BAY_DATA_ANSWER_MS / 2));
	zassert_true(lead_on(), "the board still has time to answer");
	k_sleep(K_MSEC(CONFIG_BAY_DATA_ANSWER_MS));
	zassert_false(lead_on(), "nothing answered: off");
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_NO_BOARD);
	zassert_false(dut_fault_latched(), "not a fault");

	/* No probing afterwards: off until the next power on */
	emul_board(true);
	k_sleep(K_MSEC(500));
	zassert_false(lead_on());
	zassert_ok(dut_power_set(true));
	k_sleep(K_MSEC(300));
	zassert_equal(ports_count(), 4);
}

ZTEST(data_lead, test_9_board_gone)
{
	zassert_ok(dut_power_set(true));
	k_sleep(K_MSEC(300));
	zassert_equal(ports_count(), 4);

	/* Two polls without an answer */
	emul_board(false);
	k_sleep(K_MSEC(3 * CONFIG_BAY_PORTS_POLL_MS + 20));
	zassert_false(lead_on(), "off after two missed polls");
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_BOARD_GONE);
	zassert_true(dut_fault_latched());

	/* The lead plugged back into a J7 that stays at 0 V */
	emul_board(true);
	k_sleep(K_MSEC(300));
	zassert_false(lead_on());

	/* Switched off on request: the reason goes */
	zassert_ok(dut_power_set(false));
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_OK);
}

ZTEST_SUITE(data_lead, NULL, suite_setup, before, NULL, NULL);
