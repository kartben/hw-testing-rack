/*
 * Rows A-D: TPS26600 eFuses (enable, fault, current monitor), sequencing
 * and shedding (docs/power.md).
 *
 *  - Rows stay off until the PD contract is final (CONFIG_HUB_ROWS_MIN_MV
 *    or more), then come on one after the other
 *    (CONFIG_HUB_ROW_STAGGER_MS), and the rack bus is enumerated
 *    once the nodes have booted (CONFIG_HUB_ROW_BOOT_MS).
 *  - The enables are held across a controller reset (pad hold): a reboot of
 *    the hub does not power-cycle the rack.
 *  - Shedding follows what the rows really draw (IMON) against the
 *    charger's contract (budget.c): over the budget, the next row in the
 *    shed order goes off; it comes back once the budget has room for it
 *    again.  No contract at all: every row off.
 *  - FLT counts only while the row is on and past its soft start
 *    (CONFIG_HUB_ROW_FLT_BLANK_MS): the TPS2660 also asserts it in
 *    shutdown and while it starts (datasheet 9.3.5.3).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/logging/log.h>

#if defined(CONFIG_SOC_SERIES_ESP32S3)
#include <hal/gpio_ll.h>
#include <soc/rtc_cntl_reg.h>
#include <soc/soc.h>
#endif

#include "budget.h"
#include "hub.h"

LOG_MODULE_REGISTER(rows, CONFIG_HUB_LOG_LEVEL);

#define ROWS_NODE DT_NODELABEL(rack_rows)
#define SAMPLE_MS 250

BUILD_ASSERT(HUB_ROWS == BUDGET_ROWS);

struct row_cfg {
	struct gpio_dt_spec en;
	struct gpio_dt_spec flt;
	struct gpio_dt_spec pos;
	const struct device *imon;
};

#define ROW_CFG(node)                                                                              \
	[DT_REG_ADDR(node)] = {                                                                    \
		.en = GPIO_DT_SPEC_GET(node, enable_gpios),                                        \
		.flt = GPIO_DT_SPEC_GET(node, fault_gpios),                                        \
		.pos = GPIO_DT_SPEC_GET(node, pos_gpios),                                          \
		.imon = COND_CODE_1(DT_NODE_HAS_PROP(node, current_sense),                        \
				    (DEVICE_DT_GET(DT_PHANDLE(node, current_sense))), (NULL)),     \
	},

static const struct row_cfg cfg[HUB_ROWS] = {DT_FOREACH_CHILD_STATUS_OKAY(ROWS_NODE, ROW_CFG)};

/* A row the board wires (a bench stand-in may have only some: the others are disabled) */
static bool wired(int row)
{
	return cfg[row].en.port != NULL;
}

struct row {
	enum hub_row_state state;
	bool fault;
	uint32_t faults;
	int32_t ma;
	int64_t flt_from;   /* uptime from which FLT means a fault (on, soft start over) */
	struct gpio_callback flt_cb;
	struct k_work_delayable cycle_work;
};

static struct row rows[HUB_ROWS];
static uint8_t wanted;
static char shed_order[HUB_ROWS + 1] = "DCBA";
static K_MUTEX_DEFINE(lock);

static bool contract_final;
static struct budget budget;
static uint32_t sheds;

static void sample_handler(struct k_work *work);
static void stagger_handler(struct k_work *work);
static void fault_handler(struct k_work *work);
static K_WORK_DELAYABLE_DEFINE(sample_work, sample_handler);
static K_WORK_DELAYABLE_DEFINE(stagger_work, stagger_handler);
static K_WORK_DELAYABLE_DEFINE(fault_work, fault_handler);

const char *rows_state_str(enum hub_row_state state)
{
	static const char *const names[] = {"off", "waiting", "on", "shed", "cycling"};

	return names[state];
}

/* --- Enable with pad hold ---------------------------------------------------- */

#if defined(CONFIG_SOC_SERIES_ESP32S3)
/*
 * IO0-21 are RTC pads on the ESP32-S3: their hold bit is bit n of
 * RTC_CNTL_PAD_HOLD_REG.  The RTC domain survives a CPU or system reset,
 * so a held enable keeps its level while the controller reboots.
 */
static int pad(const struct gpio_dt_spec *g)
{
	return g->pin + (g->port == DEVICE_DT_GET(DT_NODELABEL(gpio1)) ? 32 : 0);
}

static bool pad_held(int n)
{
	return n <= 21 && (REG_READ(RTC_CNTL_PAD_HOLD_REG) & BIT(n));
}

static void pad_hold(int n, bool on)
{
	if (n > 21) {
		return;
	}
	if (on) {
		REG_SET_BIT(RTC_CNTL_PAD_HOLD_REG, BIT(n));
	} else {
		REG_CLR_BIT(RTC_CNTL_PAD_HOLD_REG, BIT(n));
	}
}

static int pad_level(int n)
{
	return gpio_ll_get_level(GPIO_LL_GET_HW(0), n);
}
#else
static int pad(const struct gpio_dt_spec *g)
{
	return g->pin;
}

static bool pad_held(int n)
{
	ARG_UNUSED(n);
	return false;
}

static void pad_hold(int n, bool on)
{
	ARG_UNUSED(n);
	ARG_UNUSED(on);
}

static int pad_level(int n)
{
	ARG_UNUSED(n);
	return 0;
}
#endif

static void enable_write(int row, bool on)
{
	int n = pad(&cfg[row].en);

	if (!wired(row)) {
		return;
	}

	pad_hold(n, false);
	(void)gpio_pin_set_dt(&cfg[row].en, on);
	pad_hold(n, true);
}

/* --- State changes (lock held) ---------------------------------------------- */

static void row_off(int row, enum hub_row_state why)
{
	bool was_on = rows[row].state == HUB_ROW_ON;

	enable_write(row, false);
	if (wired(row)) {
		(void)gpio_pin_set_dt(&cfg[row].pos, 0);
	}
	rows[row].state = why;
	rows[row].fault = false; /* FLT is asserted in shutdown: not a fault */
	if (was_on) {
		bus_row_off(row);
	}
}

static void row_on(int row)
{
	enable_write(row, true);
	rows[row].state = HUB_ROW_ON;
	rows[row].flt_from = k_uptime_get() + CONFIG_HUB_ROW_FLT_BLANK_MS;
}

/* Turn the waiting rows on, one per CONFIG_HUB_ROW_STAGGER_MS */
static void stagger_handler(struct k_work *work)
{
	int next = -1;

	ARG_UNUSED(work);

	k_mutex_lock(&lock, K_FOREVER);
	if (contract_final) {
		for (int r = 0; r < HUB_ROWS; r++) {
			if (wired(r) && rows[r].state == HUB_ROW_WAITING) {
				next = r;
				break;
			}
		}
	}
	if (next >= 0) {
		row_on(next);
	}
	k_mutex_unlock(&lock);

	if (next < 0) {
		return;
	}
	hub_event(HUB_EV_ROW, "row %c on", 'A' + next);
	/* Its FLT, once the soft start is over */
	k_work_schedule(&fault_work, K_MSEC(CONFIG_HUB_ROW_FLT_BLANK_MS + 1));
	/* More to come, or enumerate once they have booted */
	k_work_reschedule(&stagger_work, K_MSEC(CONFIG_HUB_ROW_STAGGER_MS));
	bus_enumerate(CONFIG_HUB_ROW_BOOT_MS);
}

/* --- Faults ----------------------------------------------------------------- */

static void fault_handler(struct k_work *work)
{
	int64_t now = k_uptime_get();
	int64_t next = 0; /* the earliest end of a soft start still running */

	ARG_UNUSED(work);

	for (int r = 0; r < HUB_ROWS; r++) {
		bool flt = wired(r) && gpio_pin_get_dt(&cfg[r].flt) > 0;
		bool rising;

		k_mutex_lock(&lock, K_FOREVER);
		/* The TPS2660 asserts FLT in shutdown and while it starts */
		if (rows[r].state != HUB_ROW_ON) {
			flt = false;
		} else if (now < rows[r].flt_from) {
			flt = false;
			next = next == 0 ? rows[r].flt_from : MIN(next, rows[r].flt_from);
		}
		rising = flt && !rows[r].fault;
		rows[r].fault = flt;
		if (rising) {
			rows[r].faults++;
		}
		k_mutex_unlock(&lock);

		if (rising) {
			hub_event(HUB_EV_FAULT, "row %c: eFuse fault (current limit or over-temperature)",
				  'A' + r);
		}
	}

	if (next != 0) {
		/* Look again once that row's soft start is over */
		k_work_schedule(&fault_work, K_MSEC(next - now + 1));
	}
}

static void flt_isr(const struct device *port, struct gpio_callback *cb, gpio_port_pins_t pins)
{
	ARG_UNUSED(port);
	ARG_UNUSED(cb);
	ARG_UNUSED(pins);

	k_work_reschedule(&fault_work, K_NO_WAIT);
}

/* --- IMON and the budget ------------------------------------------------------ */

static int32_t read_imon(int row)
{
	struct sensor_value v;

	if (cfg[row].imon == NULL || !device_is_ready(cfg[row].imon) ||
	    sensor_sample_fetch(cfg[row].imon) != 0 ||
	    sensor_channel_get(cfg[row].imon, SENSOR_CHAN_CURRENT, &v) != 0) {
		return -1;
	}
	return MAX(sensor_value_to_milli(&v), 0);
}

static void sample_handler(struct k_work *work)
{
	struct budget_rows in = {.order = shed_order};
	enum budget_act act;
	int32_t total = 0, limit, base;
	int row = -1;

	ARG_UNUSED(work);

	for (int r = 0; r < HUB_ROWS; r++) {
		int32_t ma = rows[r].state == HUB_ROW_ON ? read_imon(r) : 0;

		k_mutex_lock(&lock, K_FOREVER);
		rows[r].ma = MAX(ma, 0);
		k_mutex_unlock(&lock);
		total += MAX(ma, 0);
	}

	k_mutex_lock(&lock, K_FOREVER);
	for (int r = 0; r < HUB_ROWS; r++) {
		in.ma[r] = rows[r].ma;
		in.on |= rows[r].state == HUB_ROW_ON ? BIT(r) : 0;
		in.shed |= rows[r].state == HUB_ROW_SHED && (wanted & BIT(r)) ? BIT(r) : 0;
	}
	act = budget_step(&budget, k_uptime_get(), &in, &row);
	base = (int32_t)budget_base_ma(&budget);
	limit = (int32_t)budget_limit_ma(&budget);
	if (act == BUDGET_SHED) {
		row_off(row, HUB_ROW_SHED);
		sheds++;
	} else if (act == BUDGET_RESTORE) {
		rows[row].state = HUB_ROW_WAITING;
	}
	k_mutex_unlock(&lock);

	if (act == BUDGET_SHED) {
		bool over_base = total > base;

		hub_event(HUB_EV_ROW, "row %c shed: %d.%02d A > %d.%02d A %s", 'A' + row,
			  total / 1000, total % 1000 / 10, (over_base ? base : limit) / 1000,
			  (over_base ? base : limit) % 1000 / 10, over_base ? "contract" : "budget");
	} else if (act == BUDGET_RESTORE) {
		hub_event(HUB_EV_ROW, "row %c back: the budget has room for it again", 'A' + row);
		k_work_reschedule(&stagger_work, K_NO_WAIT);
	}

	k_work_schedule(&sample_work, K_MSEC(SAMPLE_MS));
}

void rows_contract(bool final, uint32_t mv, uint32_t ma)
{
	/* No contract, or one too low for the rows (a sink back at 5 V) */
	bool lost = mv < CONFIG_HUB_ROWS_MIN_MV;
	bool start = false;

	k_mutex_lock(&lock, K_FOREVER);
	if (lost) {
		/* No usable VRACK: everything off, back with the next final contract */
		contract_final = false;
		for (int r = 0; r < HUB_ROWS; r++) {
			if (rows[r].state == HUB_ROW_ON || rows[r].state == HUB_ROW_CYCLING) {
				row_off(r, HUB_ROW_SHED);
			}
		}
	} else if (final && !contract_final) {
		contract_final = true;
		for (int r = 0; r < HUB_ROWS; r++) {
			if (wired(r) && (wanted & BIT(r)) &&
			    (rows[r].state == HUB_ROW_SHED || rows[r].state == HUB_ROW_WAITING)) {
				rows[r].state = HUB_ROW_WAITING;
				start = true;
			}
		}
	}
	budget_contract(&budget, contract_final, mv, lost ? 0 : ma);
	k_mutex_unlock(&lock);

	if (start) {
		k_work_reschedule(&stagger_work, K_NO_WAIT);
	}
}

/* --- The budget, by hand -------------------------------------------------------- */

void rows_budget(struct hub_budget_status *st)
{
	k_mutex_lock(&lock, K_FOREVER);
	st->contract_mv = budget.contract_mv;
	st->contract_ma = budget.contract_ma;
	st->cap_mw = budget.cap_mw;
	st->margin_pct = budget.margin_pct;
	st->base_ma = budget_base_ma(&budget);
	st->limit_ma = budget_limit_ma(&budget);
	st->total_ma = 0;
	st->shed = 0;
	for (int r = 0; r < HUB_ROWS; r++) {
		st->total_ma += rows[r].ma;
		st->shed |= rows[r].state == HUB_ROW_SHED ? BIT(r) : 0;
	}
	st->sheds = sheds;
	k_mutex_unlock(&lock);
}

int rows_set_budget_margin(int margin_pct)
{
	uint32_t cap;
	int ret;

	k_mutex_lock(&lock, K_FOREVER);
	ret = budget_set_margin(&budget, margin_pct);
	cap = budget.cap_mw;
	k_mutex_unlock(&lock);
	if (ret != 0) {
		return ret;
	}
	hub_event(HUB_EV_ROW, "budget margin %d %%", margin_pct);
	return hub_settings_save_budget((uint8_t)margin_pct, cap);
}

int rows_set_budget_cap(uint32_t cap_mw)
{
	uint8_t margin;

	k_mutex_lock(&lock, K_FOREVER);
	budget_set_cap(&budget, cap_mw);
	margin = budget.margin_pct;
	k_mutex_unlock(&lock);
	if (cap_mw != 0) {
		hub_event(HUB_EV_ROW, "budget capped at %u W", cap_mw / 1000);
	} else {
		hub_event(HUB_EV_ROW, "budget cap off: the contract's");
	}
	return hub_settings_save_budget(margin, cap_mw);
}

/* --- By hand ----------------------------------------------------------------- */

int rows_set(int row, bool on)
{
	bool start = false;

	if (row < 0 || row >= HUB_ROWS) {
		return -EINVAL;
	}
	if (!wired(row)) {
		return -ENODEV;
	}

	k_mutex_lock(&lock, K_FOREVER);
	WRITE_BIT(wanted, row, on);
	if (!on) {
		k_work_cancel_delayable(&rows[row].cycle_work);
		row_off(row, HUB_ROW_OFF);
	} else if (rows[row].state != HUB_ROW_ON) {
		rows[row].state = HUB_ROW_WAITING;
		start = contract_final;
	}
	k_mutex_unlock(&lock);

	hub_event(HUB_EV_ROW, "row %c switched %s", 'A' + row, on ? "on" : "off");
	if (start) {
		k_work_reschedule(&stagger_work, K_NO_WAIT);
	}

	(void)hub_settings_save_rows(wanted);

	return 0;
}

static void cycle_handler(struct k_work *work)
{
	struct k_work_delayable *dwork = k_work_delayable_from_work(work);
	struct row *r = CONTAINER_OF(dwork, struct row, cycle_work);
	int row = r - rows;

	k_mutex_lock(&lock, K_FOREVER);
	if (r->state == HUB_ROW_CYCLING) {
		r->state = HUB_ROW_WAITING;
	}
	k_mutex_unlock(&lock);
	k_work_reschedule(&stagger_work, K_NO_WAIT);
	LOG_DBG("row %c: cycle done", 'A' + row);
}

int rows_cycle(int row, uint32_t off_ms)
{
	if (row < 0 || row >= HUB_ROWS) {
		return -EINVAL;
	}

	k_mutex_lock(&lock, K_FOREVER);
	if (rows[row].state != HUB_ROW_ON) {
		k_mutex_unlock(&lock);
		return -EALREADY;
	}
	row_off(row, HUB_ROW_CYCLING);
	k_work_reschedule(&rows[row].cycle_work, K_MSEC(off_ms ? off_ms : CONFIG_HUB_ROW_CYCLE_MS));
	k_mutex_unlock(&lock);

	hub_event(HUB_EV_ROW, "row %c power cycle (%u ms off)", 'A' + row,
		  off_ms ? off_ms : CONFIG_HUB_ROW_CYCLE_MS);

	return 0;
}

int rows_set_shed_order(const char *order)
{
	uint8_t seen = 0;

	if (strlen(order) != HUB_ROWS) {
		return -EINVAL;
	}
	for (int i = 0; i < HUB_ROWS; i++) {
		int r = (order[i] & ~0x20) - 'A';

		if (r < 0 || r >= HUB_ROWS || (seen & BIT(r))) {
			return -EINVAL;
		}
		seen |= BIT(r);
	}

	k_mutex_lock(&lock, K_FOREVER);
	for (int i = 0; i < HUB_ROWS; i++) {
		shed_order[i] = order[i] & ~0x20;
	}
	k_mutex_unlock(&lock);

	return hub_settings_save_shed(shed_order);
}

const char *rows_shed_order(void)
{
	return shed_order;
}

/* --- Queries ------------------------------------------------------------------ */

void rows_status(int row, struct hub_row_status *st)
{
	k_mutex_lock(&lock, K_FOREVER);
	st->state = rows[row].state;
	st->wanted = (wanted & BIT(row)) != 0;
	st->fault = rows[row].fault;
	st->faults = rows[row].faults;
	st->ma = rows[row].ma;
	k_mutex_unlock(&lock);
}

static uint8_t mask_of(enum hub_row_state state)
{
	uint8_t m = 0;

	for (int r = 0; r < HUB_ROWS; r++) {
		m |= rows[r].state == state ? BIT(r) : 0;
	}
	return m;
}

uint8_t rows_on_mask(void)
{
	return mask_of(HUB_ROW_ON);
}

uint8_t rows_shed_mask(void)
{
	return mask_of(HUB_ROW_SHED);
}

uint8_t rows_fault_mask(void)
{
	uint8_t m = 0;

	for (int r = 0; r < HUB_ROWS; r++) {
		m |= rows[r].fault ? BIT(r) : 0;
	}
	return m;
}

int32_t rows_total_ma(void)
{
	int32_t total = 0;

	for (int r = 0; r < HUB_ROWS; r++) {
		total += rows[r].ma;
	}
	return total;
}

void rows_pos(int row, bool high)
{
	if (wired(row)) {
		(void)gpio_pin_set_dt(&cfg[row].pos, high && rows[row].state == HUB_ROW_ON);
	}
}

/* --- Init -------------------------------------------------------------------- */

int rows_init(uint8_t wanted_rows, const char *order, int margin_pct, uint32_t cap_mw)
{
	uint8_t kept = 0;
	int ret;

	wanted = wanted_rows;
	budget_init(&budget, margin_pct >= 0 ? margin_pct : CONFIG_HUB_BUDGET_MARGIN_PCT, cap_mw);
	if (order != NULL && order[0] != '\0') {
		(void)rows_set_shed_order(order);
	}

	for (int r = 0; r < HUB_ROWS; r++) {
		const struct row_cfg *c = &cfg[r];
		int n = pad(&c->en);
		/* Held across a controller reset: keep the row as it is */
		bool on = pad_held(n) && pad_level(n) != 0;

		if (!wired(r)) {
			rows[r].state = HUB_ROW_OFF;
			k_work_init_delayable(&rows[r].cycle_work, cycle_handler);
			continue;
		}

		if (!gpio_is_ready_dt(&c->en) || !gpio_is_ready_dt(&c->flt) ||
		    !gpio_is_ready_dt(&c->pos)) {
			return -ENODEV;
		}

		/* Same level as now, then hold it (no glitch while held) */
		ret = gpio_pin_configure_dt(&c->en, on ? GPIO_OUTPUT_ACTIVE : GPIO_OUTPUT_INACTIVE);
		if (ret != 0) {
			return ret;
		}
		pad_hold(n, false);
		pad_hold(n, true);

		ret = gpio_pin_configure_dt(&c->pos, GPIO_OUTPUT_INACTIVE);
		if (ret == 0) {
			ret = gpio_pin_configure_dt(&c->flt, GPIO_INPUT);
		}
		if (ret == 0) {
			gpio_init_callback(&rows[r].flt_cb, flt_isr, BIT(c->flt.pin));
			ret = gpio_add_callback_dt(&c->flt, &rows[r].flt_cb);
		}
		if (ret == 0) {
			ret = gpio_pin_interrupt_configure_dt(&c->flt, GPIO_INT_EDGE_BOTH);
		}
		if (ret != 0) {
			return ret;
		}

		k_work_init_delayable(&rows[r].cycle_work, cycle_handler);
		rows[r].state = on ? HUB_ROW_ON : (wanted & BIT(r)) ? HUB_ROW_WAITING : HUB_ROW_OFF;
		kept |= on ? BIT(r) : 0;
	}

	if (kept != 0) {
		/* main() enumerates them once the bus is up */
		hub_event(HUB_EV_ROW, "rows kept on across the controller reset: 0x%x", kept);
	}

	k_work_reschedule(&fault_work, K_NO_WAIT);
	k_work_schedule(&sample_work, K_MSEC(SAMPLE_MS));

	return 0;
}
