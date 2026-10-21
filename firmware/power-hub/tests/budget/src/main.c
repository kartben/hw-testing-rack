/*
 * The hub's power budget (src/budget.c) with made-up contracts and rows:
 * the budget from the contract (100 W at 20 V, 140 W at 28 V EPR, 60 W with
 * a 3 A cable), a cap in watts, a row shed before the charger's limit (after
 * the hold, or at once past the contract), the shed order, a shed row back
 * only with room to spare and after its hold, a row that flaps waiting
 * longer, nothing back while the contract settles.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>

#include <zephyr/kernel.h>
#include <zephyr/ztest.h>

#include "budget.h"

#define SAMPLE   250 /* rows.c samples the rows every 250 ms */
#define HOLD     CONFIG_HUB_SHED_HOLD_MS
#define FAST     CONFIG_HUB_SHED_FAST_MS
#define BACK     (CONFIG_HUB_RESTORE_HOLD_S * 1000)
#define A        0
#define B        1
#define C        2
#define D        3

static struct budget b;
static int64_t now;

static void contract(bool final, uint32_t mv, uint32_t ma)
{
	budget_contract(&b, final, mv, ma);
}

static void start(uint32_t mv, uint32_t ma, struct budget_rows *in, int32_t each_ma)
{
	budget_init(&b, 10, 0);
	contract(true, mv, ma);
	now = 1000;
	*in = (struct budget_rows){.on = 0xf, .order = "DCBA"};
	for (int r = 0; r < BUDGET_ROWS; r++) {
		in->ma[r] = each_ma;
	}
}

/*
 * Sample every 250 ms for up to ms: the first action, the row in *row and
 * when it came (ms after the call) in *after.  What rows.c does with it is
 * done here too: a shed row off (no current), a row back on (drawing what
 * it drew before; the test changes that if it wants).
 */
static enum budget_act run(struct budget_rows *in, int64_t ms, int *row, int64_t *after)
{
	int64_t from = now;
	static int32_t drew[BUDGET_ROWS];

	while (now - from < ms) {
		enum budget_act act;

		now += SAMPLE;
		act = budget_step(&b, now, in, row);
		if (act == BUDGET_SHED) {
			drew[*row] = in->ma[*row];
			in->on &= ~BIT(*row);
			in->shed |= BIT(*row);
			in->ma[*row] = 0;
		} else if (act == BUDGET_RESTORE) {
			in->shed &= ~BIT(*row);
			in->on |= BIT(*row);
			in->ma[*row] = drew[*row];
		}
		if (act != BUDGET_KEEP) {
			if (after != NULL) {
				*after = now - from;
			}
			return act;
		}
	}
	return BUDGET_KEEP;
}

static int32_t total(const struct budget_rows *in)
{
	int32_t t = 0;

	for (int r = 0; r < BUDGET_ROWS; r++) {
		t += (in->on & BIT(r)) ? in->ma[r] : 0;
	}
	return t;
}

ZTEST(budget, test_budget_from_the_contract)
{
	struct budget_rows in;

	/* 100 W charger: 20 V x 5 A, 10 % kept free */
	start(20000, 5000, &in, 0);
	zassert_equal(budget_base_ma(&b), 5000);
	zassert_equal(budget_limit_ma(&b), 4500);

	/* 140 W EPR: 28 V x 5 A, the same current, 126 W for the rows */
	contract(true, 28000, 5000);
	zassert_equal(budget_limit_ma(&b), 4500);
	zassert_equal(budget_limit_ma(&b) * 28000 / 1000, 126000);

	/* The same charger through a 3 A cable: 60 W */
	contract(true, 20000, 3000);
	zassert_equal(budget_base_ma(&b), 3000);
	zassert_equal(budget_limit_ma(&b), 2700);

	/* No contract: no budget */
	contract(false, 0, 0);
	zassert_equal(budget_limit_ma(&b), 0);

	/* The margin, by hand */
	contract(true, 20000, 5000);
	zassert_equal(budget_set_margin(&b, 51), -EINVAL);
	zassert_equal(budget_set_margin(&b, 0), 0);
	zassert_equal(budget_limit_ma(&b), 5000);
	zassert_equal(budget_set_margin(&b, 20), 0);
	zassert_equal(budget_limit_ma(&b), 4000);
}

ZTEST(budget, test_cap_in_watts)
{
	struct budget_rows in;

	start(20000, 5000, &in, 0);

	/* A charger that shares 60 W with other ports */
	budget_set_cap(&b, 60000);
	zassert_equal(budget_base_ma(&b), 3000);

	/* Its current follows the contract's voltage */
	contract(true, 28000, 5000);
	zassert_equal(budget_base_ma(&b), 2142);

	/* Never above the contract */
	budget_set_cap(&b, 200000);
	zassert_equal(budget_base_ma(&b), 5000);
	budget_set_cap(&b, 0);
	zassert_equal(budget_base_ma(&b), 5000);
}

ZTEST(budget, test_sheds_before_the_charger_limit)
{
	struct budget_rows in;
	int64_t after;
	int row;

	/* 100 W: four rows at 1.1 A, 4.4 A of the 4.5 A budget */
	start(20000, 5000, &in, 1100);
	zassert_equal(run(&in, 30000, &row, NULL), BUDGET_KEEP);

	/* D draws more: 4.6 A, over the budget but under the 5 A contract */
	in.ma[D] = 1300;
	zassert_equal(run(&in, 30000, &row, &after), BUDGET_SHED);
	zassert_equal(row, D, "the shed order's first row: D");
	zassert_between_inclusive(after, HOLD, HOLD + SAMPLE,
				  "after the hold: %lld ms", (long long)after);
	zassert_true(total(&in) <= (int32_t)budget_limit_ma(&b));

	/* 3.3 A left: within the budget, and not enough room for D's 1.3 A */
	zassert_equal(run(&in, 60000, &row, NULL), BUDGET_KEEP);
	zassert_equal(in.shed, BIT(D));
}

ZTEST(budget, test_past_the_contract_sheds_at_once)
{
	struct budget_rows in;
	int64_t after;
	int row;

	/* 60 W (3 A cable): four rows at 0.8 A, 3.2 A, past the contract itself */
	start(20000, 3000, &in, 800);
	zassert_equal(run(&in, 30000, &row, &after), BUDGET_SHED);
	zassert_equal(row, D);
	zassert_between_inclusive(after, FAST, FAST + SAMPLE,
				  "at once: %lld ms", (long long)after);
	zassert_true(after < HOLD);
	zassert_equal(total(&in), 2400);
	zassert_equal(run(&in, 60000, &row, NULL), BUDGET_KEEP);
}

ZTEST(budget, test_back_with_hysteresis)
{
	struct budget_rows in;
	int64_t after;
	int row;

	start(20000, 5000, &in, 1100);
	in.ma[D] = 1300;
	zassert_equal(run(&in, 30000, &row, NULL), BUDGET_SHED);

	/* 1.45 A of room: under D's 1.3 A plus the 0.2 A restore margin */
	in.ma[A] = 850;
	zassert_equal(run(&in, 120000, &row, NULL), BUDGET_KEEP);

	/* 1.7 A of room: D comes back, after its hold and not before */
	in.ma[A] = 600;
	zassert_equal(run(&in, 30000, &row, &after), BUDGET_RESTORE);
	zassert_equal(row, D);
	zassert_between_inclusive(after, BACK, BACK + 2 * SAMPLE,
				  "after its hold: %lld ms", (long long)after);
	zassert_equal(total(&in), 600 + 1100 + 1100 + 1300);
	zassert_true(total(&in) < (int32_t)budget_limit_ma(&b));
	zassert_equal(run(&in, 120000, &row, NULL), BUDGET_KEEP, "no flapping");
}

ZTEST(budget, test_nothing_back_until_the_contract_is_final)
{
	struct budget_rows in;
	int row;

	start(20000, 5000, &in, 1100);
	in.ma[D] = 1300;
	zassert_equal(run(&in, 30000, &row, NULL), BUDGET_SHED);
	in.ma[A] = 100;

	contract(false, 20000, 5000);
	zassert_equal(run(&in, 120000, &row, NULL), BUDGET_KEEP);
	contract(true, 20000, 5000);
	zassert_equal(run(&in, 30000, &row, NULL), BUDGET_RESTORE);
	zassert_equal(row, D);
}

ZTEST(budget, test_a_row_that_flaps_waits_longer)
{
	struct budget_rows in;
	int64_t after;
	int row;

	start(20000, 5000, &in, 1100);
	in.ma[D] = 1300;
	zassert_equal(run(&in, 30000, &row, NULL), BUDGET_SHED);
	in.ma[A] = 600;
	zassert_equal(run(&in, 30000, &row, NULL), BUDGET_RESTORE);

	/* Back, A draws again: over the budget, D shed again within the minute */
	in.ma[A] = 1100;
	zassert_equal(run(&in, 30000, &row, NULL), BUDGET_SHED);
	zassert_equal(row, D);

	/* Its hold has doubled */
	in.ma[A] = 600;
	zassert_equal(run(&in, 30000, &row, &after), BUDGET_RESTORE);
	zassert_between_inclusive(after, 2 * BACK, 2 * BACK + 2 * SAMPLE,
				  "%lld ms", (long long)after);

	/* Shed long after it came back: the hold is the usual one again */
	zassert_equal(run(&in, CONFIG_HUB_RESTORE_FLAP_S * 1000 + 1000, &row, NULL), BUDGET_KEEP);
	in.ma[A] = 1100;
	zassert_equal(run(&in, 30000, &row, NULL), BUDGET_SHED);
	in.ma[A] = 600;
	zassert_equal(run(&in, 60000, &row, &after), BUDGET_RESTORE);
	zassert_between_inclusive(after, BACK, BACK + 2 * SAMPLE,
				  "%lld ms", (long long)after);
}

ZTEST(budget, test_shed_order)
{
	struct budget_rows in;
	int row;

	/* A first, then B; back the other way round, B first */
	start(20000, 5000, &in, 1500);
	in.order = "ABCD";
	zassert_equal(run(&in, 30000, &row, NULL), BUDGET_SHED);
	zassert_equal(row, A);
	in.ma[C] = 2000;
	zassert_equal(run(&in, 30000, &row, NULL), BUDGET_SHED);
	zassert_equal(row, B);

	in.ma[C] = 100;
	in.ma[D] = 100;
	zassert_equal(run(&in, 60000, &row, NULL), BUDGET_RESTORE);
	zassert_equal(row, B);
	zassert_equal(run(&in, 60000, &row, NULL), BUDGET_RESTORE);
	zassert_equal(row, A);
}

ZTEST(budget, test_28v_then_20v_with_a_3a_cable)
{
	struct budget_rows in;
	int64_t after;
	int row;

	/* 140 W EPR: three rows at 1.6 A (the eFuse limit), 4.8 A of 4.5 A */
	start(28000, 5000, &in, 1600);
	in.on = BIT(A) | BIT(B) | BIT(C);
	zassert_equal(run(&in, 30000, &row, &after), BUDGET_SHED);
	zassert_equal(row, C, "D is off: C");
	zassert_between_inclusive(after, HOLD, HOLD + SAMPLE);

	/* The charger renegotiates: 20 V through a 3 A cable, 3.2 A > 3 A */
	contract(true, 20000, 3000);
	zassert_equal(run(&in, 30000, &row, &after), BUDGET_SHED);
	zassert_equal(row, B);
	zassert_between_inclusive(after, FAST, FAST + SAMPLE);
	zassert_equal(total(&in), 1600);
}

ZTEST(budget, test_no_contract_no_decision)
{
	struct budget_rows in;
	int row;

	start(20000, 5000, &in, 3000);
	contract(false, 0, 0);
	zassert_equal(run(&in, 30000, &row, NULL), BUDGET_KEEP);
}

ZTEST_SUITE(budget, NULL, NULL, NULL, NULL, NULL);
