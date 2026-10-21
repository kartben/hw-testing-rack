/*
 * The rows' power budget (docs/power.md): what the charger's contract lets
 * the rows draw, and which row to shed or bring back.  Pure logic, no
 * hardware: rows.c feeds it the contract and the rows' IMON every sample, a
 * test feeds it made-up ones (tests/budget).
 *
 * The budget is a current at VRACK, which is VBUS: a fixed PD contract
 * limits the current (20 V x 5 A = 100 W, 28 V x 5 A EPR = 140 W, 20 V x
 * 3 A with a 3 A cable = 60 W), and IMON measures the rows' current.
 *
 *  - base: the contract's current (the CH224A's granted current), or a cap
 *    set by hand in watts (a charger that shares its power between ports)
 *    below it;
 *  - limit: the base less a margin (the hub's own draw, IMON's error);
 *  - above the limit for CONFIG_HUB_SHED_HOLD_MS, or above the base itself
 *    for CONFIG_HUB_SHED_FAST_MS (before the charger's overcurrent
 *    protection cuts the whole rack), the next row in the shed order goes;
 *  - a shed row comes back, the last shed first, once the limit has room
 *    for the most it drew plus CONFIG_HUB_RESTORE_MARGIN_MA, for its
 *    restore hold (CONFIG_HUB_RESTORE_HOLD_S); shed again within
 *    CONFIG_HUB_RESTORE_FLAP_S of coming back, its hold doubles (up to
 *    CONFIG_HUB_RESTORE_HOLD_MAX_S).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef BUDGET_H_
#define BUDGET_H_

#include <stdbool.h>
#include <stdint.h>

#define BUDGET_ROWS 4

struct budget {
	/* Settings */
	uint8_t margin_pct; /* kept free below the base */
	uint32_t cap_mw;    /* a cap set by hand (mW), 0 none */

	/* The contract */
	bool final;
	uint32_t contract_mv;
	uint32_t contract_ma;

	/* Timers (uptime, ms), 0 not running */
	int64_t over_since;  /* above the limit since */
	int64_t base_since;  /* above the base since */
	int64_t room_since;  /* room for the next row to come back since */

	/* Per row */
	int32_t peak_ma[BUDGET_ROWS];       /* the most it drew since it came on */
	int32_t need_ma[BUDGET_ROWS];       /* the most it drew before it was shed */
	int64_t back_at[BUDGET_ROWS];       /* when it last came back, 0 never */
	uint32_t hold_ms[BUDGET_ROWS];      /* its restore hold */
};

/* What the rows do now, for one sample */
struct budget_rows {
	int32_t ma[BUDGET_ROWS]; /* IMON, 0 when off */
	uint8_t on;              /* rows on */
	uint8_t shed;            /* rows shed for lack of power and wanted back */
	const char *order;       /* shed first to last, e.g. "DCBA" */
};

enum budget_act {
	BUDGET_KEEP,
	BUDGET_SHED,    /* turn the row off (shed) */
	BUDGET_RESTORE, /* the row may come back */
};

void budget_init(struct budget *b, uint8_t margin_pct, uint32_t cap_mw);
/* A new or changed contract (final: stable, the rows may be on); 0 mA none */
void budget_contract(struct budget *b, bool final, uint32_t mv, uint32_t ma);
int budget_set_margin(struct budget *b, int margin_pct);
/* A cap in mW, 0 none: the base is never above the contract */
void budget_set_cap(struct budget *b, uint32_t cap_mw);

/* The contract's current, or the cap's at the contract's voltage if lower (mA), 0
 * without a contract
 */
uint32_t budget_base_ma(const struct budget *b);
/* What the rows may draw (mA): the base less the margin */
uint32_t budget_limit_ma(const struct budget *b);

/* One sample at now (ms): what to do, and to which row (*row) */
enum budget_act budget_step(struct budget *b, int64_t now, const struct budget_rows *rows,
			    int *row);

#endif /* BUDGET_H_ */
