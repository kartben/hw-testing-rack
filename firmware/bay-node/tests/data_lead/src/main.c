/*
 * Node v1.0's DATA lead (src/dut.c, src/ports.c) against the emulated
 * DATA x4, powered by the eFuse's enable: the power-on rule of
 * docs/firmware.md.  Off at boot; on only with SCL and SDA high and the
 * node's INA226 answering; ~FLT ignored while the eFuse ramps; off again on a
 * short; the board must answer within a second; off for good on a ~FLT or a
 * board that stops answering, until the next power on.  Then the ports'
 * budget in mW on DATA_VIN: the hub's grant admits them, a lower grant sheds
 * the last ones switched on, without a grant the bay's own limit; a refused
 * request is not queued unless it asked to be (on as soon as there is room).
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
static int count_at_boot = -1, offline_at_boot = -1;
static int grant_mw = -1; /* the hub's grant, -1 none */

/* --- What dut.c and ports.c need from the rest of the node ------------------ */

void aux_dut_power(bool on)
{
	ARG_UNUSED(on);
}

bool bay_rack_grant(struct rack_grant *g)
{
	if (grant_mw < 0) {
		return false;
	}
	*g = (struct rack_grant){.mw = (uint16_t)grant_mw, .flags = RACK_GRANT_ROW};
	return true;
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

/* The ports' INA226s (data-x4.dtsi) */
static const uint8_t ina[4] = {0x41, 0x43, 0x44, 0x45};

static void ports_draw(int ma)
{
	for (int i = 0; i < 4; i++) {
		emul_ina_ma(ina[i], ma);
	}
}

static bool port_on_slot(int slot)
{
	struct port_info pi;

	return ports_info(slot, &pi) == 0 && pi.on;
}

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
	/* What ports.c did after its first set-up delay, DATA_VIN still off */
	k_sleep(K_MSEC(100));
	count_at_boot = ports_count();
	offline_at_boot = emul_offline();
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
	emul_board_kind(4);
	emul_meter(true);
	emul_board_ma(300);
	grant_mw = -1;
	for (int io = 0; io < 2; io++) {
		for (int pin = 0; pin < 8; pin++) {
			emul_io_pin(io, pin, true);
		}
	}
	for (int i = 0; i < 4; i++) {
		emul_ina_ma(ina[i], 0);
	}
	k_sleep(K_MSEC(50));
}

/* --- Tests ------------------------------------------------------------------ */

ZTEST(data_lead, test_01_off_at_boot)
{
	zassert_true(off_at_boot, "the eFuse stays off until the checks pass");
	zassert_equal(count_at_boot, 0, "no board set up while DATA_VIN is off");
	zassert_equal(offline_at_boot, 0, "no I2C to an unpowered board");
}

ZTEST(data_lead, test_02_on)
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

ZTEST(data_lead, test_03_lead_reversed)
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

ZTEST(data_lead, test_04_meter_missing)
{
	emul_meter(false);
	zassert_equal(dut_power_set(true), -ENODEV);
	zassert_false(lead_on());
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_METER);
}

ZTEST(data_lead, test_05_short)
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

ZTEST(data_lead, test_06_flt_blanked_while_ramping)
{
	/* ~FLT low while the eFuse is off, high 5 ms after it ramps: ignored */
	flt_set(true);
	k_work_reschedule(&flt_release, K_MSEC(5));
	zassert_ok(dut_power_set(true));
	zassert_true(lead_on());
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_OK);
	zassert_false(dut_fault_active());
}

ZTEST(data_lead, test_07_flt_while_on)
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

ZTEST(data_lead, test_08_no_board)
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

ZTEST(data_lead, test_09_board_gone)
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

/*
 * The budget in watts on DATA_VIN (20 V here; the board's 5 V at 88 %): the
 * board alone 1.7 W, each port drawing 200 mA at 5 V about 1.14 W more
 * (2.84, 3.96, 5.1, 6.24 W with one to four on); 0.6 W kept for a start.
 */

ZTEST(data_lead, test_10_grant_admits)
{
	struct ports_budget pb;
	struct port_info pi;

	/* 4 W from the hub: two ports (3.96 W), the third would need 4.56 W */
	grant_mw = 4000;
	ports_draw(200);
	zassert_ok(dut_power_set(true));
	k_sleep(K_MSEC(1500));
	zassert_equal(ports_on(), 2, "%d ports on", ports_on());
	zassert_equal(ports_waiting(), 2);
	zassert_ok(ports_info(3, &pi));
	zassert_true(pi.waiting);
	zassert_false(pi.shed);
	zassert_ok(ports_budget(&pb));
	zassert_true(pb.power);
	zassert_true(pb.granted);
	zassert_equal(pb.limit, 4000);
	zassert_equal(pb.reserve, CONFIG_BAY_PORTS_RESERVE_MW);
	zassert_within(pb.draw, 3960, 50, "the bay draws %d mW", pb.draw);
	zassert_equal(pb.waiting, 2);

	/* The hub grants more: the waiting ports come on, one after the other */
	grant_mw = 8000;
	k_sleep(K_MSEC(2000));
	zassert_equal(ports_on(), 4);
	zassert_equal(ports_waiting(), 0);
}

ZTEST(data_lead, test_11_shed_over_the_grant)
{
	struct ports_budget pb;
	struct port_info pi;
	uint32_t sheds;

	grant_mw = 8000;
	ports_draw(200);
	zassert_ok(dut_power_set(true));
	k_sleep(K_MSEC(1500));
	zassert_equal(ports_on(), 4);
	zassert_ok(ports_budget(&pb));
	sheds = pb.sheds;

	/* The grant drops to 3 W: the last ports switched on go until the bay fits (2.84 W) */
	grant_mw = 3000;
	k_sleep(K_MSEC(300));
	zassert_equal(ports_on(), 1, "%d ports on", ports_on());
	zassert_true(port_on_slot(1), "the first one switched on stays");
	for (int slot = 2; slot <= 4; slot++) {
		zassert_ok(ports_info(slot, &pi));
		zassert_true(pi.shed, "port %d shed", slot);
		zassert_true(pi.waiting && pi.wanted, "port %d wanted back", slot);
	}
	zassert_ok(ports_budget(&pb));
	zassert_equal(pb.sheds - sheds, 3);

	/* No room for what they drew: they stay off */
	k_sleep(K_MSEC(1500));
	zassert_equal(ports_on(), 1);

	/* Room again: back, one after the other */
	grant_mw = 8000;
	k_sleep(K_MSEC(2500));
	zassert_equal(ports_on(), 4);
	zassert_ok(ports_info(4, &pi));
	zassert_false(pi.shed);
}

ZTEST(data_lead, test_12_no_grant)
{
	struct ports_budget pb;
	struct port_info pi;

	/* No hub: the bay's own limit */
	ports_draw(200);
	zassert_ok(dut_power_set(true));
	k_sleep(K_MSEC(1500));
	zassert_equal(ports_on(), 4);
	zassert_ok(ports_budget(&pb));
	zassert_false(pb.granted);
	zassert_equal(pb.limit, CONFIG_BAY_PORTS_LIMIT_MW);

	/*
	 * A request the budget refuses is not queued: off, not wanted, not
	 * waiting.  The ports idle now (the board's 1.7 W), 2 W granted: no room
	 * for a start (0.6 W), nothing to shed either.
	 */
	ports_draw(0);
	zassert_ok(ports_power(4, false, NULL));
	grant_mw = 2000;
	k_sleep(K_MSEC(300));
	zassert_equal(ports_on(), 3, "nothing shed");
	zassert_equal(ports_power(4, true, NULL), -EBUSY);
	zassert_ok(ports_info(4, &pi));
	zassert_false(pi.wanted);
	zassert_false(pi.waiting);
	zassert_equal(ports_waiting(), 0);
}

ZTEST(data_lead, test_13_queued)
{
	struct port_info pi;

	/* Three ports on and idle (the board's 1.7 W), 2 W granted: no room for the fourth */
	grant_mw = 8000;
	zassert_ok(dut_power_set(true));
	k_sleep(K_MSEC(1500));
	zassert_ok(ports_power(4, false, NULL));
	zassert_equal(ports_on(), 3);
	grant_mw = 2000;
	k_sleep(K_MSEC(300));

	/* Queued: off, wanted, waiting in its turn as the ports wanted at boot */
	zassert_equal(ports_power_wait(4), -EINPROGRESS);
	zassert_ok(ports_info(4, &pi));
	zassert_false(pi.on);
	zassert_true(pi.queued && pi.wanted && pi.waiting);
	zassert_equal(ports_waiting(), 1);
	k_sleep(K_MSEC(500));
	zassert_false(port_on_slot(4), "still no room");

	/* Room: on by itself */
	grant_mw = 8000;
	k_sleep(K_MSEC(1000));
	zassert_true(port_on_slot(4));
	zassert_ok(ports_info(4, &pi));
	zassert_false(pi.queued);
	zassert_equal(ports_waiting(), 0);

	/* Cancelled: off, no longer wanted, never started */
	zassert_ok(ports_power(4, false, NULL));
	grant_mw = 2000;
	k_sleep(K_MSEC(300));
	zassert_equal(ports_power_wait(4), -EINPROGRESS);
	zassert_ok(ports_power_cancel(4));
	zassert_ok(ports_info(4, &pi));
	zassert_false(pi.queued || pi.wanted || pi.waiting);
	zassert_equal(ports_power_cancel(4), -EALREADY, "nothing left to cancel");
	grant_mw = 8000;
	k_sleep(K_MSEC(1000));
	zassert_false(port_on_slot(4));

	/* An explicit off withdraws it too */
	grant_mw = 2000;
	k_sleep(K_MSEC(300));
	zassert_equal(ports_power_wait(4), -EINPROGRESS);
	zassert_ok(ports_power(4, false, NULL));
	zassert_ok(ports_info(4, &pi));
	zassert_false(pi.queued || pi.wanted);
	grant_mw = 8000;
	k_sleep(K_MSEC(1000));
	zassert_false(port_on_slot(4));

	/* With room it goes on at once */
	zassert_ok(ports_power_wait(4));
	zassert_true(port_on_slot(4));
	zassert_ok(ports_info(4, &pi));
	zassert_false(pi.queued);
}

ZTEST(data_lead, test_14_data_x6)
{
	int on = 0;

	/* A DATA x6 on the lead instead: it answers in time, its six ports come on */
	emul_board_kind(6);
	for (int pin = 0; pin < 16; pin++) {
		emul_io_pin(0, pin, true);
	}
	zassert_ok(dut_power_set(true));
	k_sleep(K_MSEC(2500));
	zassert_true(lead_on(), "it answered: DATA_VIN stays on");
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_OK);
	zassert_equal(ports_board(), DATA_X6);
	zassert_equal(ports_count(), 6);
	for (int i = 1; i <= 6; i++) {
		on += port_on_slot(i);
	}
	zassert_equal(on, 6);
	zassert_ok(dut_power_set(false));
}

ZTEST(data_lead, test_15_neither)
{
	/* Something at 0x20 that is neither board: as no board, DATA_VIN off */
	emul_board_kind(1);
	zassert_ok(dut_power_set(true));
	k_sleep(K_MSEC(CONFIG_BAY_DATA_ANSWER_MS + 300));
	zassert_false(lead_on());
	zassert_equal(dut_lead_state(NULL), DUT_LEAD_NO_BOARD);
	zassert_equal(ports_count(), 0);
	zassert_equal(ports_board(), DATA_UNKNOWN, "kept while the lead is off, for the page");
}

ZTEST_SUITE(data_lead, NULL, suite_setup, before, NULL, NULL);
