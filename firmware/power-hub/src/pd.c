/*
 * USB-C PD input (docs/power.md › Negotiation and sequencing).
 *
 * The CH224A runs from VBUS and negotiates by itself: 9 V at plug-in (its
 * CFG1 resistor), and it keeps the contract through controller resets.  The
 * controller watches VBUS on its ADC; once VBUS is up it powers the sink's
 * I2C pull-ups (I2C_PU), initializes the driver (zephyr,deferred-init) as
 * soon as the chip answers, and asks for 28 V EPR when the charger offers it,
 * 20 V otherwise.
 *
 * The chip cannot report the voltage in place: a request counts once the
 * chip says PD, PG is low and VBUS_SENSE reads the voltage asked for.  A
 * 28 V request that VBUS does not follow within CONFIG_HUB_PD_REQUEST_MS
 * falls back to 20 V.  A contract of CONFIG_HUB_ROWS_MIN_MV or more that
 * holds for CONFIG_HUB_CONTRACT_SETTLE_MS is "final": rows.c then turns the
 * rows on; a lower one never is.  PG going high (a renegotiation, a hard
 * reset) makes the contract provisional: rows.c sheds what no longer fits,
 * and turns every row off once VBUS falls under CONFIG_HUB_ROWS_MIN_MV.  PG
 * coming back runs the policy again (the charger may offer something else).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdlib.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/regulator.h>
#include <zephyr/drivers/regulator/ch224a.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/logging/log.h>

#include "hub.h"

LOG_MODULE_REGISTER(pd, CONFIG_HUB_LOG_LEVEL);

#define HUB_NODE DT_NODELABEL(power_hub)
#define REG_NODE DT_PHANDLE(HUB_NODE, pd)

#define POLL_MS     250
#define SINK_EVERY  4 /* polls: the sink's status and current once a second */
#define EPR_MV      28000
#define SPR_MV      20000

static const struct gpio_dt_spec i2c_pu = GPIO_DT_SPEC_GET(HUB_NODE, i2c_pullup_gpios);
static const struct device *const reg = DEVICE_DT_GET(REG_NODE);
static const struct device *const bus = DEVICE_DT_GET(DT_BUS(REG_NODE));
static const struct device *const vbus = DEVICE_DT_GET(DT_PHANDLE(HUB_NODE, vbus_sense));

static K_MUTEX_DEFINE(lock);
static struct hub_pd_status st;
static bool drivers_up;
static int64_t contract_since;
static int64_t asked_at;  /* uptime of the last request, 0 none pending */
static bool spr_failed;   /* 20 V asked and not reached: said once */
static uint32_t polls;

K_THREAD_STACK_DEFINE(pd_stack, 3072);
static struct k_work_q pd_q;

static void policy_handler(struct k_work *work);
static void poll_handler(struct k_work *work);
static void pg_handler(struct k_work *work);
static K_WORK_DEFINE(policy_work, policy_handler);
static K_WORK_DEFINE(pg_work, pg_handler);
static K_WORK_DELAYABLE_DEFINE(poll_work, poll_handler);

static const char *state_str(enum hub_pd_state s)
{
	static const char *const names[] = {"no VBUS", "starting", "SPR", "EPR"};

	return names[s];
}

/* PDO number of a fixed offer at mv, 0 none */
static int fixed_pdo(const struct hub_pd_status *s, uint32_t mv)
{
	for (int i = 0; i < s->npdos; i++) {
		if (s->pdos[i].type == CH224A_PDO_FIXED && s->pdos[i].max_mv == mv) {
			return i + 1;
		}
	}
	return 0;
}

/* VBUS_SENSE within the divider's and the ADC's tolerance of mv */
static bool vbus_at(uint32_t vbus_mv, uint32_t mv)
{
	return abs((int32_t)vbus_mv - (int32_t)mv) <= (int32_t)(mv * 8 / 100);
}

/* Ask for mv (lock held) */
static int ask(uint32_t mv)
{
	int ret = regulator_set_voltage(reg, mv * 1000, mv * 1000);

	if (ret == 0) {
		st.asked_mv = mv;
		asked_at = k_uptime_get();
		spr_failed = false;
	}
	return ret;
}

static void policy_handler(struct k_work *work)
{
	struct ch224a_pdo pdos[CH224A_PDO_COUNT];
	bool epr_offered;
	uint32_t want;
	int n, ret;

	ARG_UNUSED(work);

	if (!drivers_up) {
		return;
	}

	/* The offers, when the chip shows them; else 28 V is tried and checked */
	n = regulator_ch224a_get_pdos(reg, pdos);

	k_mutex_lock(&lock, K_FOREVER);
	if (n >= 0) {
		memcpy(st.pdos, pdos, sizeof(st.pdos));
		st.npdos = n;
	} else {
		memset(st.pdos, 0, sizeof(st.pdos));
		st.npdos = 0;
	}
	epr_offered = st.npdos == 0 || (st.pdos[0].raw & CH224A_PDO1_EPR_CAPABLE) != 0U ||
		      fixed_pdo(&st, EPR_MV) != 0;
	want = st.epr_pref && epr_offered && !st.epr_refused ? EPR_MV : SPR_MV;
	/* The same request already on its way: let it finish */
	ret = want == st.asked_mv && asked_at != 0 ? -EINPROGRESS : ask(want);
	k_mutex_unlock(&lock);

	if (n < 0 && n != -ENODATA) {
		LOG_WRN("cannot read the charger's offers (%d)", n);
	}
	if (ret == -EINPROGRESS) {
		LOG_DBG("%u V already asked for", want / 1000);
	} else if (ret != 0) {
		LOG_WRN("%u V request failed (%d)", want / 1000, ret);
	} else {
		LOG_INF("asked for %u V", want / 1000);
	}
}

/* The regulator callback: PG changed (the driver's work queue) */
static void pg_changed(const struct device *dev, const struct regulator_event *const evt,
		       const void *const user_data)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(user_data);

	k_mutex_lock(&lock, K_FOREVER);
	st.power_good = evt->type == REGULATOR_VOLTAGE_DETECTED;
	k_mutex_unlock(&lock);
	k_work_submit_to_queue(&pd_q, &pg_work);
}

static void pg_handler(struct k_work *work)
{
	bool good, ours;

	ARG_UNUSED(work);

	k_mutex_lock(&lock, K_FOREVER);
	good = st.power_good;
	/* Our own request may drop PG while the charger moves */
	ours = asked_at != 0 && k_uptime_get() - asked_at < CONFIG_HUB_PD_REQUEST_MS;
	if (!good) {
		st.final = false;
	}
	k_mutex_unlock(&lock);

	if (good) {
		LOG_INF("PG: contract in place");
		if (!ours) {
			/* After a renegotiation: the charger may offer something else */
			k_work_submit_to_queue(&pd_q, &policy_work);
		}
	} else if (!ours) {
		hub_event(HUB_EV_PD, "contract lost (PG): the charger renegotiates");
	}
}

static int drivers_start(void)
{
	uint8_t status;
	int ret;

	/* A deferred init that fails stays failed: wait until the chip answers */
	ret = i2c_reg_read_byte(bus, DT_REG_ADDR(REG_NODE), CH224A_REG_STATUS, &status);
	if (ret != 0) {
		return ret;
	}
	ret = device_init(reg);
	if (ret != 0 && ret != -EALREADY) {
		return ret;
	}
	ret = regulator_set_callback(reg, pg_changed, NULL);
	if (ret != 0 && ret != -ENOSYS) {
		return ret;
	}
	drivers_up = true;

	return 0;
}

static uint32_t read_vbus(void)
{
	struct sensor_value v;

	if (sensor_sample_fetch(vbus) != 0 ||
	    sensor_channel_get(vbus, SENSOR_CHAN_VOLTAGE, &v) != 0) {
		return 0;
	}
	return (uint32_t)MAX(sensor_value_to_milli(&v), 0);
}

/* The sink's status, PG and granted current */
static void read_sink(void)
{
	int32_t ua = 0;
	uint8_t status = 0;
	int good = regulator_ch224a_power_good(reg);

	if (regulator_ch224a_get_status(reg, &status) != 0) {
		status = 0;
	}
	if ((status & CH224A_STATUS_PD) == 0U || regulator_get_current_limit(reg, &ua) != 0) {
		ua = 0;
	}

	k_mutex_lock(&lock, K_FOREVER);
	st.protocol = status;
	st.power_good = good < 0 ? (status & CH224A_STATUS_PD) != 0U : good > 0;
	st.granted_ma = ua / 1000;
	k_mutex_unlock(&lock);
}

static void vbus_lost(void)
{
	(void)gpio_pin_set_dt(&i2c_pu, 0);
	k_mutex_lock(&lock, K_FOREVER);
	st.state = HUB_PD_NONE;
	st.final = false;
	st.power_good = false;
	st.protocol = 0;
	st.asked_mv = 0;
	st.contract_mv = 0;
	st.contract_ma = 0;
	st.granted_ma = 0;
	st.selected = 0;
	st.epr_refused = false;
	st.npdos = 0;
	memset(st.pdos, 0, sizeof(st.pdos));
	asked_at = 0;
	k_mutex_unlock(&lock);
	hub_event(HUB_EV_PD, "VBUS gone: no PD charger (running from the console USB-C)");
	rows_contract(false, 0, 0);
}

/*
 * Compare what was asked with what VBUS reads: the contract, its settling,
 * the 28 V fallback.  Called every poll once the sink answers.
 */
static void check_contract(uint32_t mv)
{
	int64_t now = k_uptime_get();
	bool changed = false, final_now = false, fallback = false, spr_low = false;
	uint32_t cmv, cma, expect;
	bool pd, at;

	k_mutex_lock(&lock, K_FOREVER);
	pd = (st.protocol & CH224A_STATUS_PD) != 0U;
	/* Nothing asked yet: the chip's own request (CFG1) */
	expect = st.asked_mv != 0 ? st.asked_mv : DT_PROP(REG_NODE, startup_microvolt) / 1000;
	at = pd && st.power_good && vbus_at(mv, expect);

	if (at) {
		asked_at = 0;
		if (st.contract_mv != expect || st.contract_ma != st.granted_ma) {
			st.contract_mv = expect;
			st.contract_ma = st.granted_ma;
			st.state = expect > SPR_MV ? HUB_PD_EPR : HUB_PD_SPR;
			st.selected = fixed_pdo(&st, expect);
			st.final = false;
			contract_since = now;
			changed = true;
		} else if (!st.final && expect >= CONFIG_HUB_ROWS_MIN_MV &&
			   now - contract_since >= CONFIG_HUB_CONTRACT_SETTLE_MS) {
			st.final = true;
			final_now = true;
		}
	} else {
		/* Not (or no longer) at the voltage asked for: provisional */
		st.final = false;
		contract_since = now;
		if (!pd) {
			st.state = HUB_PD_STARTING;
		}
		if (asked_at != 0 && now - asked_at >= CONFIG_HUB_PD_REQUEST_MS) {
			asked_at = 0;
			if (st.asked_mv == EPR_MV) {
				st.epr_refused = true;
				fallback = true;
			} else if (!spr_failed) {
				spr_failed = true;
				spr_low = true;
			}
		}
	}
	cmv = st.contract_mv;
	cma = st.contract_ma;
	k_mutex_unlock(&lock);

	if (changed) {
		hub_event(HUB_EV_PD, "contract: %u V / %u.%02u A%s (%u W)%s", cmv / 1000, cma / 1000,
			  cma % 1000 / 10, cmv > SPR_MV ? " EPR" : "", cmv * cma / 1000000,
			  cmv < CONFIG_HUB_ROWS_MIN_MV ? ", too low for the rows" : "");
	}
	if (fallback) {
		hub_event(HUB_EV_PD, "28 V asked, VBUS stays at %u.%u V: asking for 20 V", mv / 1000,
			  mv % 1000 / 100);
		k_work_submit_to_queue(&pd_q, &policy_work);
	}
	if (spr_low) {
		hub_event(HUB_EV_PD, "20 V asked, VBUS stays at %u.%u V: the rows stay off", mv / 1000,
			  mv % 1000 / 100);
	}

	if (final_now) {
		LOG_INF("contract final: %u mV, %u mA", cmv, cma);
		rows_contract(true, cmv, cma);
	} else if (!at || changed) {
		/* rows.c keeps what is on, sheds what no longer fits, all off below the minimum */
		rows_contract(false, at ? cmv : mv, cma);
	}
}

static void poll_handler(struct k_work *work)
{
	uint32_t mv = read_vbus();
	enum hub_pd_state state;
	int ret;

	ARG_UNUSED(work);

	k_mutex_lock(&lock, K_FOREVER);
	st.vbus_mv = mv;
	state = st.state;
	k_mutex_unlock(&lock);

	if (mv < CONFIG_HUB_VBUS_MIN_MV) {
		if (state != HUB_PD_NONE) {
			vbus_lost();
		}
		goto again;
	}

	if (state == HUB_PD_NONE) {
		/* The sink is powered: pull-ups on, give it a moment */
		(void)gpio_pin_set_dt(&i2c_pu, 1);
		k_mutex_lock(&lock, K_FOREVER);
		st.state = HUB_PD_STARTING;
		k_mutex_unlock(&lock);
		hub_event(HUB_EV_PD, "VBUS %u.%u V: PD sink up", mv / 1000, mv % 1000 / 100);
		goto again;
	}

	if (!drivers_up) {
		ret = drivers_start();
		if (ret != 0) {
			LOG_WRN("PD sink not answering (%d)", ret);
			goto again;
		}
	}

	if (state == HUB_PD_STARTING || ++polls % SINK_EVERY == 0) {
		uint8_t before, after;

		k_mutex_lock(&lock, K_FOREVER);
		before = st.protocol;
		k_mutex_unlock(&lock);
		read_sink();
		k_mutex_lock(&lock, K_FOREVER);
		after = st.protocol;
		k_mutex_unlock(&lock);
		/* A PD contract (again): ask for what the policy wants */
		if ((before & CH224A_STATUS_PD) == 0U && (after & CH224A_STATUS_PD) != 0U) {
			k_work_submit_to_queue(&pd_q, &policy_work);
		}
	}

	check_contract(mv);

again:
	k_work_schedule_for_queue(&pd_q, &poll_work, K_MSEC(POLL_MS));
}

int pd_init(bool epr)
{
	int ret;

	if (!gpio_is_ready_dt(&i2c_pu) || !device_is_ready(vbus) || !device_is_ready(bus)) {
		return -ENODEV;
	}
	/* Pull-ups off until VBUS is seen */
	ret = gpio_pin_configure_dt(&i2c_pu, GPIO_OUTPUT_INACTIVE);
	if (ret != 0) {
		return ret;
	}

	st.state = HUB_PD_NONE;
	st.epr_pref = epr;

	k_work_queue_init(&pd_q);
	k_work_queue_start(&pd_q, pd_stack, K_THREAD_STACK_SIZEOF(pd_stack),
			   K_PRIO_PREEMPT(6), &(struct k_work_queue_config){.name = "pd"});
	k_work_schedule_for_queue(&pd_q, &poll_work, K_NO_WAIT);

	return 0;
}

void pd_status(struct hub_pd_status *out)
{
	k_mutex_lock(&lock, K_FOREVER);
	*out = st;
	k_mutex_unlock(&lock);
}

int pd_set_epr(bool epr)
{
	k_mutex_lock(&lock, K_FOREVER);
	st.epr_pref = epr;
	st.epr_refused = false;
	k_mutex_unlock(&lock);

	hub_event(HUB_EV_PD, "contract preference: %s", epr ? "28 V EPR when offered" : "20 V");
	if (drivers_up) {
		k_work_submit_to_queue(&pd_q, &policy_work);
	}

	return hub_settings_save_epr(epr);
}

const char *pd_state_str(enum hub_pd_state s)
{
	return state_str(s);
}
