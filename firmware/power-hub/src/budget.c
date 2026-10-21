/*
 * The rows' power budget: see budget.h and docs/power.md.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <string.h>

#include <zephyr/sys/util.h>

#include "budget.h"

#define HOLD_MS     ((uint32_t)CONFIG_HUB_RESTORE_HOLD_S * 1000U)
#define HOLD_MAX_MS ((uint32_t)CONFIG_HUB_RESTORE_HOLD_MAX_S * 1000U)
#define FLAP_MS     ((int64_t)CONFIG_HUB_RESTORE_FLAP_S * 1000U)
#define MARGIN_MAX  50

void budget_init(struct budget *b, uint8_t margin_pct, uint32_t cap_mw)
{
	memset(b, 0, sizeof(*b));
	b->margin_pct = MIN(margin_pct, MARGIN_MAX);
	b->cap_mw = cap_mw;
	for (int r = 0; r < BUDGET_ROWS; r++) {
		b->hold_ms[r] = HOLD_MS;
	}
}

void budget_contract(struct budget *b, bool final, uint32_t mv, uint32_t ma)
{
	if (mv != b->contract_mv || ma != b->contract_ma) {
		/* Room is measured against the new limit from now on */
		b->room_since = 0;
	}
	b->final = final;
	b->contract_mv = mv;
	b->contract_ma = ma;
}

int budget_set_margin(struct budget *b, int margin_pct)
{
	if (margin_pct < 0 || margin_pct > MARGIN_MAX) {
		return -EINVAL;
	}
	b->margin_pct = (uint8_t)margin_pct;
	b->room_since = 0;
	return 0;
}

void budget_set_cap(struct budget *b, uint32_t cap_mw)
{
	b->cap_mw = cap_mw;
	b->room_since = 0;
}

uint32_t budget_base_ma(const struct budget *b)
{
	uint32_t base = b->contract_ma;

	if (base == 0 || b->contract_mv == 0) {
		return 0;
	}
	if (b->cap_mw != 0) {
		/* A cap in watts: its current follows the contract's voltage */
		base = MIN(base, (uint32_t)((uint64_t)b->cap_mw * 1000U / b->contract_mv));
	}
	return base;
}

uint32_t budget_limit_ma(const struct budget *b)
{
	return budget_base_ma(b) * (100U - b->margin_pct) / 100U;
}

/* The next row to shed: the first one on in the shed order, -1 none */
static int shed_candidate(const struct budget_rows *rows)
{
	for (const char *c = rows->order; *c != '\0'; c++) {
		int r = *c - 'A';

		if (r >= 0 && r < BUDGET_ROWS && (rows->on & BIT(r))) {
			return r;
		}
	}
	return -1;
}

/* The next row to bring back: the last shed one in the shed order, -1 none */
static int restore_candidate(const struct budget_rows *rows)
{
	for (int i = (int)strlen(rows->order) - 1; i >= 0; i--) {
		int r = rows->order[i] - 'A';

		if (r >= 0 && r < BUDGET_ROWS && (rows->shed & BIT(r))) {
			return r;
		}
	}
	return -1;
}

enum budget_act budget_step(struct budget *b, int64_t now, const struct budget_rows *rows,
			    int *row)
{
	int32_t base = (int32_t)budget_base_ma(b);
	int32_t limit = (int32_t)budget_limit_ma(b);
	int32_t total = 0;
	bool due;
	int r;

	for (r = 0; r < BUDGET_ROWS; r++) {
		if (rows->on & BIT(r)) {
			total += MAX(rows->ma[r], 0);
			b->peak_ma[r] = MAX(b->peak_ma[r], rows->ma[r]);
		} else {
			b->peak_ma[r] = 0;
		}
	}

	if (base == 0) {
		/* No contract: rows.c has turned everything off */
		b->over_since = 0;
		b->base_since = 0;
		b->room_since = 0;
		return BUDGET_KEEP;
	}

	if (total > base) {
		b->base_since = b->base_since ? b->base_since : now;
	} else {
		b->base_since = 0;
	}

	if (total > limit) {
		b->over_since = b->over_since ? b->over_since : now;
		b->room_since = 0;
		due = (b->base_since && now - b->base_since >= CONFIG_HUB_SHED_FAST_MS) ||
		      now - b->over_since >= CONFIG_HUB_SHED_HOLD_MS;
		r = due ? shed_candidate(rows) : -1;
		if (r < 0) {
			return BUDGET_KEEP;
		}

		b->need_ma[r] = MAX(b->peak_ma[r], rows->ma[r]);
		b->peak_ma[r] = 0;
		/* Back and shed again soon after: it waits longer next time */
		if (b->back_at[r] != 0 && now - b->back_at[r] < FLAP_MS) {
			b->hold_ms[r] = MIN(b->hold_ms[r] * 2U, HOLD_MAX_MS);
		} else {
			b->hold_ms[r] = HOLD_MS;
		}
		/* The next one waits for what the rows draw without this one */
		b->over_since = 0;
		b->base_since = 0;
		*row = r;
		return BUDGET_SHED;
	}
	b->over_since = 0;

	/* Within the limit: bring a row back once there is room for it */
	r = b->final ? restore_candidate(rows) : -1;
	if (r < 0 || limit - total <= b->need_ma[r] + CONFIG_HUB_RESTORE_MARGIN_MA) {
		b->room_since = 0;
		return BUDGET_KEEP;
	}
	if (b->room_since == 0) {
		b->room_since = now;
		return BUDGET_KEEP;
	}
	if (now - b->room_since < (int64_t)b->hold_ms[r]) {
		return BUDGET_KEEP;
	}

	b->room_since = 0;
	b->back_at[r] = now;
	*row = r;
	return BUDGET_RESTORE;
}
