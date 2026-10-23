/*
 * The CH446Q MUX driver against emulated chips: each one follows the lines
 * it sees on gpio_emul (address bits on CK's rising edges, AY2 first, the
 * switch state on DAT latched by STB's falling edge, RST high opens every
 * switch), as the datasheet describes it, and counts what the datasheet
 * forbids (DAT changing with a clock edge or during STB).  Port writes and
 * reset pulses are counted too.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/gpio/gpio_emul.h>
#include <zephyr/drivers/mux.h>
#include <zephyr/kernel.h>
#include <zephyr/ztest.h>

#define NUM_X 16
#define NUM_Y 8

#define CHIP_LINES(node)                                                                           \
	.data = GPIO_DT_SPEC_GET(node, data_gpios), .clock = GPIO_DT_SPEC_GET(node, clock_gpios),  \
	.strobe = GPIO_DT_SPEC_GET(node, strobe_gpios),                                            \
	.reset = GPIO_DT_SPEC_GET_OR(node, reset_gpios, {0})

/* A chip as its pins see the lines (an inverted line arrives inverted back) */
struct chip {
	struct gpio_dt_spec data, clock, strobe, reset;
	bool data_was, clock_was, strobe_was, reset_was;
	bool data_strobe; /* DAT when STB rose */
	uint8_t shift;
	uint8_t y_mask[NUM_X];
	int faults;
	int resets;
};

static struct chip chips[] = {
	{CHIP_LINES(DT_NODELABEL(u7))},
	{CHIP_LINES(DT_NODELABEL(u8))},
	{CHIP_LINES(DT_NODELABEL(apart))},
};
static struct chip *const u7_chip = &chips[0];
static struct chip *const u8_chip = &chips[1];
static struct chip *const apart_chip = &chips[2];

static const struct device *const u7 = DEVICE_DT_GET(DT_NODELABEL(u7));
static const struct device *const u8 = DEVICE_DT_GET(DT_NODELABEL(u8));
static const struct device *const apart = DEVICE_DT_GET(DT_NODELABEL(apart));

static const struct device *const ports[] = {
	DEVICE_DT_GET(DT_NODELABEL(mx)),
	DEVICE_DT_GET(DT_NODELABEL(pa)),
	DEVICE_DT_GET(DT_NODELABEL(pb)),
};
static struct gpio_callback cbs[ARRAY_SIZE(ports)];
static int writes[ARRAY_SIZE(ports)];

#define PINS DT_NODELABEL(pins)
MUX_CONTROL_DT_SPEC_DEFINE_BY_NAME(PINS, p1_1);
MUX_CONTROL_DT_SPEC_DEFINE_BY_NAME(PINS, p1_2);
MUX_CONTROL_DT_SPEC_DEFINE_BY_NAME(PINS, p3_1);
MUX_STATE_DT_SPEC_DEFINE(PINS);

static bool level(const struct gpio_dt_spec *spec)
{
	return (gpio_emul_output_get(spec->port, spec->pin) > 0) !=
	       ((spec->dt_flags & GPIO_ACTIVE_LOW) != 0);
}

static void chip_update(struct chip *c)
{
	bool data = level(&c->data), clock = level(&c->clock), strobe = level(&c->strobe);
	bool reset = c->reset.port != NULL && level(&c->reset);

	if (reset) {
		c->resets += !c->reset_was;
		memset(c->y_mask, 0, sizeof(c->y_mask));
	} else {
		if (clock && !c->clock_was) {
			c->faults += data != c->data_was || c->strobe_was;
			c->shift = ((c->shift << 1) | data) & 0x7F;
		}
		if (strobe && !c->strobe_was) {
			c->data_strobe = data;
		} else if (strobe && data != c->data_strobe) {
			c->faults++; /* DAT must hold until STB falls */
		}
		if (!strobe && c->strobe_was) {
			/* Address y * 16 + x */
			WRITE_BIT(c->y_mask[c->shift & 0x0F], c->shift >> 4, c->data_strobe);
		}
	}
	c->data_was = data;
	c->clock_was = clock;
	c->strobe_was = strobe;
	c->reset_was = reset;
}

static void on_write(const struct device *port, struct gpio_callback *cb, gpio_port_pins_t pins)
{
	ARG_UNUSED(cb);
	ARG_UNUSED(pins);

	for (size_t i = 0; i < ARRAY_SIZE(ports); i++) {
		writes[i] += ports[i] == port;
	}
	ARRAY_FOR_EACH_PTR(chips, c) {
		chip_update(c);
	}
}

static void *setup(void)
{
	zassert_true(device_is_ready(u7) && device_is_ready(u8) && device_is_ready(apart));
	for (size_t i = 0; i < ARRAY_SIZE(ports); i++) {
		gpio_init_callback(&cbs[i], on_write, BIT_MASK(8));
		zassert_ok(gpio_add_callback(ports[i], &cbs[i]));
	}
	return NULL;
}

/* X's control line, built at run time */
#define X_CONTROL(name, x)                                                                         \
	const uint32_t name##_cell = (x);                                                          \
	const struct mux_control name = {.cells = &name##_cell, .len = 1}

/* The chip and the driver agree on every X; nothing forbidden was seen */
static void check_chip(const struct device *dev, const struct chip *c)
{
	uint32_t state;

	for (uint8_t x = 0; x < NUM_X; x++) {
		X_CONTROL(ctl, x);

		zassert_ok(mux_state_get(dev, &ctl, &state));
		zassert_equal(state, c->y_mask[x], "%s X%u: driver 0x%02x, chip 0x%02x", dev->name,
			      x, state, c->y_mask[x]);
	}
	zassert_equal(c->faults, 0, "%s: %d timing faults", dev->name, c->faults);
}

ZTEST(ch446q, test_1_set)
{
	const struct mux_control *p1_1 = MUX_CONTROL_DT_GET_BY_NAME(PINS, p1_1);
	X_CONTROL(x4, 4);
	uint32_t state;
	int before;

	/* The datasheet's example: Y2-X4, address 24H */
	zassert_ok(mux_control_set(u7, &x4, BIT(2)));
	zassert_equal(u7_chip->y_mask[4], BIT(2));
	zassert_equal(u8_chip->y_mask[4], 0, "U8 saw the address but not its strobe");

	/*
	 * One switch more: 16 port writes (gpio_emul reports a port write when it
	 * changes a line; after a switch CK is high, so each of them does)
	 */
	before = writes[0];
	zassert_ok(mux_control_set(u7, &x4, BIT(2) | BIT(7)));
	zassert_equal(writes[0] - before, 16, "%d port writes for one switch", writes[0] - before);
	zassert_ok(mux_state_get(u7, &x4, &state));
	zassert_equal(state, BIT(2) | BIT(7));

	/* The same mask again: nothing to write */
	before = writes[0];
	zassert_ok(mux_control_set(u7, &x4, BIT(2) | BIT(7)));
	zassert_equal(writes[0], before);

	/* By name, from the devicetree: p1-1 (entry 0) is U7's X15 */
	zassert_equal_ptr(MUX_CONTROL_DT_DEV_GET_BY_IDX(PINS, 0), u7);
	zassert_ok(mux_control_set(MUX_CONTROL_DT_DEV_GET_BY_IDX(PINS, 0), p1_1, 0x81));
	zassert_equal(u7_chip->y_mask[15], 0x81);
	check_chip(u7, u7_chip);
	check_chip(u8, u8_chip);
}

ZTEST(ch446q, test_2_disconnect)
{
	const struct mux_control *p1_2 = MUX_CONTROL_DT_GET_BY_NAME(PINS, p1_2);
	const struct mux_control *p3_1 = MUX_CONTROL_DT_GET_BY_NAME(PINS, p3_1);
	int resets = u7_chip->resets;
	int before;

	zassert_ok(mux_control_set(u7, p1_2, 0xFF));
	zassert_ok(mux_control_set(u8, p3_1, 0x3C));

	/* X7 of U7 opens, switch by switch; U8 keeps its switches, RST never moves */
	before = writes[0];
	zassert_ok(mux_control_disconnect(u7, p1_2));
	zassert_equal(writes[0] - before, 8 * 16);
	zassert_equal(u7_chip->y_mask[7], 0);
	zassert_equal(u8_chip->y_mask[15], 0x3C);
	zassert_equal(u7_chip->resets, resets, "disconnect must not pulse the shared reset");
	check_chip(u7, u7_chip);
	check_chip(u8, u8_chip);
}

ZTEST(ch446q, test_3_every_switch)
{
	for (uint8_t x = 0; x < NUM_X; x++) {
		X_CONTROL(ctl, x);

		zassert_ok(mux_control_set(u8, &ctl, 0xFF));
	}
	for (uint8_t x = 0; x < NUM_X; x++) {
		zassert_equal(u8_chip->y_mask[x], 0xFF, "X%u: 0x%02x", x, u8_chip->y_mask[x]);
	}
	/* A different mask on each X: every address and data bit both ways */
	for (uint8_t x = 0; x < NUM_X; x++) {
		X_CONTROL(ctl, x);

		zassert_ok(mux_control_set(u8, &ctl, (x * 37 + 11) & 0xFF));
	}
	check_chip(u8, u8_chip);
}

ZTEST(ch446q, test_4_state_from_devicetree)
{
	const struct mux_state *st = MUX_STATE_DT_GET(PINS);

	zassert_equal(st->state, 0x09);
	zassert_ok(mux_state_apply(MUX_STATE_DT_DEV_GET(PINS), st));
	zassert_equal(u7_chip->y_mask[15], 0x09);
	check_chip(u7, u7_chip);
}

ZTEST(ch446q, test_5_lines_apart)
{
	X_CONTROL(x15, 15);
	X_CONTROL(x0, 0);
	int before_a = writes[1], before_b = writes[2];

	/* The data line on one port, inverted on the way; clock and strobe on another */
	zassert_ok(mux_control_set(apart, &x15, BIT(7)));
	zassert_equal(apart_chip->y_mask[15], BIT(7));
	zassert_equal(writes[1] - before_a, 8, "DAT: 7 address bits and the state");
	zassert_equal(writes[2] - before_b, 16, "CK: 14 writes, STB: 2");
	zassert_ok(mux_control_set(apart, &x0, 0x55));
	check_chip(apart, apart_chip);

	zassert_ok(mux_control_disconnect(apart, &x0));
	zassert_equal(apart_chip->y_mask[0], 0);
	check_chip(apart, apart_chip);
}

ZTEST(ch446q, test_6_errors)
{
	X_CONTROL(x16, 16);
	X_CONTROL(x1, 1);
	const uint32_t two[] = {1, 2};
	const struct mux_control wide = {.cells = two, .len = 2};
	uint32_t state;

	zassert_equal(mux_control_set(u7, &x16, 1), -EINVAL);
	zassert_equal(mux_control_set(u7, &x1, 0x100), -EINVAL);
	zassert_equal(mux_control_set(u7, &wide, 1), -EINVAL);
	zassert_equal(mux_state_get(u7, &x16, &state), -EINVAL);
	zassert_equal(mux_control_disconnect(u7, &wide), -EINVAL);
	check_chip(u7, u7_chip);
}

ZTEST_SUITE(ch446q, NULL, setup, NULL, NULL, NULL);
