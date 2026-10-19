/*
 * USB-C PD input (docs/power.md › Negotiation and sequencing).
 *
 * The AP33772S runs from VBUS and starts on the source's 5 V contract
 * (the FA02 then asks for 20 V by itself, through VSEL; the FA01 waits).
 * The controller watches VBUS on its ADC; once VBUS is up it powers the
 * sink's I2C pull-ups (I2C_PU), initializes the drivers
 * (zephyr,deferred-init) and asks for 28 V EPR when the charger and the
 * cable offer it, 20 V otherwise.  A contract of CONFIG_HUB_ROWS_MIN_MV or
 * more that holds for CONFIG_HUB_CONTRACT_SETTLE_MS is "final": rows.c then
 * turns the rows on; a lower one never is.  New source capabilities (a
 * multi-port charger reallocating power) re-run the policy; rows.c sheds
 * what no longer fits.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/regulator.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/logging/log.h>

#include "hub.h"

LOG_MODULE_REGISTER(pd, CONFIG_HUB_LOG_LEVEL);

#define HUB_NODE  DT_NODELABEL(power_hub)
#define REG_NODE  DT_PHANDLE(HUB_NODE, pd)

#define POLL_MS     250
#define METER_EVERY 4 /* polls: once a second */
#define EPR_MV      28000
#define SPR_MV      20000

static const struct gpio_dt_spec i2c_pu = GPIO_DT_SPEC_GET(HUB_NODE, i2c_pullup_gpios);
static const struct device *const mfd = DEVICE_DT_GET(DT_PARENT(REG_NODE));
static const struct device *const reg = DEVICE_DT_GET(REG_NODE);
static const struct device *const meter = DEVICE_DT_GET(DT_PHANDLE(HUB_NODE, pd_meter));
static const struct device *const vbus = DEVICE_DT_GET(DT_PHANDLE(HUB_NODE, vbus_sense));

static K_MUTEX_DEFINE(lock);
static struct hub_pd_status st;
static bool drivers_up;
static int64_t contract_since;
static uint32_t polls;
static struct gpio_callback mfd_cb;

K_THREAD_STACK_DEFINE(pd_stack, 3072);
static struct k_work_q pd_q;

static void policy_handler(struct k_work *work);
static void poll_handler(struct k_work *work);
static K_WORK_DEFINE(policy_work, policy_handler);
static K_WORK_DELAYABLE_DEFINE(poll_work, poll_handler);

static const char *state_str(enum hub_pd_state s)
{
	static const char *const names[] = {"no VBUS", "starting", "SPR", "EPR"};

	return names[s];
}

static int fixed_pdo(const struct hub_pd_status *s, uint32_t mv, bool epr)
{
	for (int i = 0; i < AP33772S_PDO_COUNT; i++) {
		if (s->pdos[i].type == AP33772S_PDO_FIXED && s->pdos[i].max_mv == mv &&
		    s->pdos[i].epr == epr) {
			return i + 1;
		}
	}
	return 0;
}

/* Contract as the sink reports it */
static void read_contract(void)
{
	int32_t uv = 0, ua = 0;
	uint32_t mv, ma;

	if (regulator_get_voltage(reg, &uv) != 0) {
		uv = 0;
	}
	if (uv == 0 || regulator_get_current_limit(reg, &ua) != 0) {
		ua = 0;
	}
	mv = uv / 1000;
	ma = ua / 1000;

	k_mutex_lock(&lock, K_FOREVER);
	if (mv != st.contract_mv || ma != st.contract_ma) {
		st.contract_mv = mv;
		st.contract_ma = ma;
		st.final = false;
		contract_since = k_uptime_get();
		st.state = mv == 0 ? HUB_PD_STARTING : mv > SPR_MV ? HUB_PD_EPR : HUB_PD_SPR;
		st.selected = mv == 0 ? 0 : fixed_pdo(&st, mv, mv > SPR_MV);
		k_mutex_unlock(&lock);
		if (mv != 0) {
			hub_event(HUB_EV_PD, "contract: %u.%u V / %u.%02u A%s (%u W)%s", mv / 1000,
				  mv % 1000 / 100, ma / 1000, ma % 1000 / 10,
				  mv > SPR_MV ? " EPR" : "", mv * ma / 1000000,
				  mv < CONFIG_HUB_ROWS_MIN_MV ? ", too low for the rows" : "");
		}
		/* Not final yet: rows.c keeps what is on, sheds if it no longer fits */
		rows_contract(false, mv, ma);
		return;
	}
	k_mutex_unlock(&lock);
}

static void policy_handler(struct k_work *work)
{
	struct hub_pd_status s;
	int pdo;
	int ret;

	ARG_UNUSED(work);

	ret = mfd_ap33772s_get_pdos(mfd, s.pdos, true);
	if (ret < 0) {
		LOG_WRN("cannot read the source capabilities (%d)", ret);
		return;
	}

	k_mutex_lock(&lock, K_FOREVER);
	memcpy(st.pdos, s.pdos, sizeof(st.pdos));
	st.npdos = ret;
	s.epr_pref = st.epr_pref;
	k_mutex_unlock(&lock);

	pdo = s.epr_pref ? fixed_pdo(&s, EPR_MV, true) : 0;
	if (pdo != 0) {
		ret = regulator_set_voltage(reg, EPR_MV * 1000, EPR_MV * 1000);
		if (ret == 0) {
			read_contract();
			return;
		}
		hub_event(HUB_EV_PD, "28 V EPR offered but refused (%d): staying at 20 V", ret);
	}

	/* 20 V: from the sink's start (5 V), or leaving EPR by choice */
	ret = regulator_set_voltage(reg, SPR_MV * 1000, SPR_MV * 1000);
	if (ret != 0) {
		LOG_WRN("20 V request failed (%d): keeping the sink's own contract", ret);
	}
	read_contract();
}

static void mfd_event(const struct device *dev, struct gpio_callback *cb, gpio_port_pins_t events)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(cb);

	if (events & (BIT(AP33772S_EVENT_OVP) | BIT(AP33772S_EVENT_OCP) | BIT(AP33772S_EVENT_OTP) |
		      BIT(AP33772S_EVENT_UVP))) {
		k_mutex_lock(&lock, K_FOREVER);
		st.faults |= events;
		k_mutex_unlock(&lock);
		hub_event(HUB_EV_FAULT, "PD sink protection:%s%s%s%s",
			  (events & BIT(AP33772S_EVENT_OVP)) ? " over-voltage" : "",
			  (events & BIT(AP33772S_EVENT_OCP)) ? " over-current" : "",
			  (events & BIT(AP33772S_EVENT_OTP)) ? " over-temperature" : "",
			  (events & BIT(AP33772S_EVENT_UVP)) ? " under-voltage" : "");
	}
	if (events & BIT(AP33772S_EVENT_NEWPDO)) {
		k_work_submit_to_queue(&pd_q, &policy_work);
	}
}

static int drivers_start(void)
{
	int ret;

	if (drivers_up) {
		/* VBUS came back: the sink starts from its defaults */
		return mfd_ap33772s_configure(mfd);
	}

	ret = device_init(mfd);
	if (ret != 0 && ret != -EALREADY) {
		return ret;
	}
	ret = device_init(reg);
	if (ret != 0 && ret != -EALREADY) {
		return ret;
	}
	(void)device_init(meter);

	gpio_init_callback(&mfd_cb, mfd_event,
			   BIT(AP33772S_EVENT_NEWPDO) | BIT(AP33772S_EVENT_UVP) |
			   BIT(AP33772S_EVENT_OVP) | BIT(AP33772S_EVENT_OCP) |
			   BIT(AP33772S_EVENT_OTP));
	ret = mfd_ap33772s_add_callback(mfd, &mfd_cb);
	if (ret != 0) {
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

static void read_meter(void)
{
	struct sensor_value v, i, t;

	if (!device_is_ready(meter) || sensor_sample_fetch(meter) != 0) {
		return;
	}
	(void)sensor_channel_get(meter, SENSOR_CHAN_VOLTAGE, &v);
	(void)sensor_channel_get(meter, SENSOR_CHAN_CURRENT, &i);
	(void)sensor_channel_get(meter, SENSOR_CHAN_DIE_TEMP, &t);

	k_mutex_lock(&lock, K_FOREVER);
	st.meter_mv = (uint32_t)sensor_value_to_milli(&v);
	st.meter_ma = (uint32_t)sensor_value_to_milli(&i);
	st.temp_c = t.val1;
	k_mutex_unlock(&lock);
}

static void vbus_lost(void)
{
	(void)gpio_pin_set_dt(&i2c_pu, 0);
	k_mutex_lock(&lock, K_FOREVER);
	st.state = HUB_PD_NONE;
	st.final = false;
	st.contract_mv = 0;
	st.contract_ma = 0;
	st.selected = 0;
	st.npdos = 0;
	memset(st.pdos, 0, sizeof(st.pdos));
	k_mutex_unlock(&lock);
	hub_event(HUB_EV_PD, "VBUS gone: no PD charger (running from the console USB-C)");
	rows_contract(false, 0, 0);
}

static void poll_handler(struct k_work *work)
{
	uint32_t mv = read_vbus();
	enum hub_pd_state state;
	bool final_now = false;
	uint32_t cmv, cma;
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

	if (!drivers_up || state == HUB_PD_STARTING) {
		ret = drivers_start();
		if (ret != 0) {
			LOG_WRN("PD sink not answering (%d)", ret);
			goto again;
		}
		if (state == HUB_PD_STARTING && st.contract_mv == 0) {
			k_work_submit_to_queue(&pd_q, &policy_work);
		}
	}

	if (++polls % METER_EVERY == 0) {
		read_meter();
		read_contract();
	}

	k_mutex_lock(&lock, K_FOREVER);
	if (!st.final && st.contract_mv >= CONFIG_HUB_ROWS_MIN_MV &&
	    k_uptime_get() - contract_since >= CONFIG_HUB_CONTRACT_SETTLE_MS) {
		st.final = true;
		final_now = true;
	}
	cmv = st.contract_mv;
	cma = st.contract_ma;
	k_mutex_unlock(&lock);

	if (final_now) {
		LOG_INF("contract final: %u mV, %u mA", cmv, cma);
		rows_contract(true, cmv, cma);
	}

again:
	k_work_schedule_for_queue(&pd_q, &poll_work, K_MSEC(POLL_MS));
}

int pd_init(bool epr)
{
	int ret;

	if (!gpio_is_ready_dt(&i2c_pu) || !device_is_ready(vbus)) {
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
