/*
 * The DATA x4's pin matrix (docs/multi-dut-node.md, rules for the pin
 * matrix): any of the 32 port pins (P1-P8 of the four ports) on any of the
 * eight buses A-H, which boards share as wires and the co-processor's
 * analyzer reads (CH1-8).  Two CH446Q crosspoints through their mux driver
 * (port_pins in data-x4.dtsi), behind the board's TCA9534A and its driver
 * (src/ports.c starts it).  A pin is on one bus at most.
 *
 * What is asked (wanted) is kept apart from what the switches are (closed):
 *  - a port's pins stay open while it is off, or while its VREF reads under
 *    0.65 V, and close once it is on again;
 *  - a change opens every switch that has to open, on both chips, before it
 *    closes any (break-before-make);
 *  - the chips forget their switches when DUT_5V goes off: once the board
 *    is set up again the driver's copy is cleared (opening what it holds
 *    closed: the chips already are) and the wanted pins close as their
 *    ports come on.
 *
 * src/ports.c calls wires_matrix() and wires_port() with its own lock held:
 * this file never calls into it.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/data/json.h>
#include <zephyr/drivers/mux.h>
#include <zephyr/logging/log.h>

#include "bay.h"

LOG_MODULE_REGISTER(wires, CONFIG_BAY_LOG_LEVEL);

#define PINS_NODE   DT_NODELABEL(port_pins)
#define NONE        (-1)
#define VREF_MIN_MV 650

BUILD_ASSERT(DT_PROP_LEN(PINS_NODE, mux_controls) == WIRES_PINS, "port_pins: 4 ports x 8 pins");

#define PIN_CTRL(node, prop, idx) MUX_CONTROL_DT_SPEC_DEFINE_BY_IDX(node, idx);
DT_FOREACH_PROP_ELEM(PINS_NODE, mux_controls, PIN_CTRL)

#define PIN_ENTRY(node, prop, idx)                                                                 \
	{DEVICE_DT_GET(DT_PHANDLE_BY_IDX(node, prop, idx)), MUX_CONTROL_DT_GET_BY_IDX(node, idx)},

/* Pin p is P(p % 8 + 1) of port p / 8 + 1 */
static const struct {
	const struct device *dev;
	const struct mux_control *ctl;
} pin[WIRES_PINS] = {DT_FOREACH_PROP_ELEM(PINS_NODE, mux_controls, PIN_ENTRY)};

/* The buses' Y lines, on both chips (data-x4.dtsi): Y0-Y7 are buses D C B A E F G H */
static const uint8_t bus_y[WIRES_BUSES] = {3, 2, 1, 0, 4, 5, 6, 7};

static K_MUTEX_DEFINE(lock);

static struct {
	bool up;                     /* the chips answer, their driver started */
	bool on[WIRES_PORTS];        /* the port is on (ports.c) */
	int8_t wanted[WIRES_PINS];   /* bus 0-7 (A-H), or NONE */
	int8_t closed[WIRES_PINS];   /* as the driver last wrote the switches */
	const char *error;
} w = {
	.wanted = {[0 ... WIRES_PINS - 1] = NONE},
	.closed = {[0 ... WIRES_PINS - 1] = NONE},
};

/* A name for each bus, what it carries; the CPU only reads them: PSRAM */
static BAY_EXT_RAM char names[WIRES_BUSES][WIRES_NAME_LEN];

/*
 * Each port's VREF in mV, -1 without a reading.  Only the co-processor's ADC
 * sees it (GPIO40-43), and gusmanb's analyzer, which it runs, does not report
 * it: no reading yet, the port's power alone decides.
 */
static const int16_t vref_mv[WIRES_PORTS] = {-1, -1, -1, -1};

static bool may_wire(int port)
{
	return w.on[port] && (vref_mv[port] < 0 || vref_mv[port] >= VREF_MIN_MV);
}

static int set_pin(int p, int bus)
{
	return mux_control_set(pin[p].dev, pin[p].ctl, bus == NONE ? 0 : BIT(bus_y[bus]));
}

/* The switches as they should be now; the number changed, or -errno (lock held) */
static int apply(void)
{
	int8_t target[WIRES_PINS];
	int changed = 0;
	int ret = 0;

	for (int p = 0; p < WIRES_PINS; p++) {
		target[p] = w.up && may_wire(p / WIRES_PORT_PINS) ? w.wanted[p] : NONE;
	}
	/* Break before make: every switch that opens, then every one that closes */
	for (int p = 0; p < WIRES_PINS; p++) {
		if (w.closed[p] != NONE && w.closed[p] != target[p]) {
			int r = set_pin(p, NONE);

			if (r == 0) {
				w.closed[p] = NONE;
				changed++;
			} else {
				ret = r;
			}
		}
	}
	for (int p = 0; p < WIRES_PINS && ret == 0; p++) {
		if (target[p] != NONE && w.closed[p] != target[p]) {
			ret = set_pin(p, target[p]);
			if (ret == 0) {
				w.closed[p] = target[p];
				changed++;
			}
		}
	}
	w.error = ret == 0 ? NULL : "the matrix did not take a change";
	if (ret != 0) {
		LOG_ERR("%s (%d)", w.error, ret);
	}

	return ret == 0 ? changed : ret;
}

void wires_matrix(bool up)
{
	int ret = 0;

	k_mutex_lock(&lock, K_FOREVER);
	if (!up) {
		/* DUT_5V going off (the chips still answer), or the board gone */
		for (int p = 0; p < WIRES_PINS && w.up; p++) {
			if (w.closed[p] != NONE && set_pin(p, NONE) == 0) {
				w.closed[p] = NONE;
			}
		}
		memset(w.on, 0, sizeof(w.on));
		w.up = false;
		k_mutex_unlock(&lock);
		return;
	}

	/* The crosspoints' driver starts with the board (RST: every switch open) */
	for (int p = 0; p < WIRES_PINS && ret == 0; p++) {
		if (!device_is_ready(pin[p].dev)) {
			ret = device_init(pin[p].dev);
		}
	}
	/* Set up again after DUT_5V: the chips are open, the driver's copy is not */
	for (int p = 0; p < WIRES_PINS && ret == 0; p++) {
		if (w.closed[p] != NONE) {
			ret = set_pin(p, NONE);
			if (ret == 0) {
				w.closed[p] = NONE;
			}
		}
	}
	w.up = ret == 0;
	w.error = ret == 0 ? NULL : "the matrix did not start";
	if (ret != 0) {
		LOG_ERR("%s (%d)", w.error, ret);
	} else {
		(void)apply();
	}
	k_mutex_unlock(&lock);
}

void wires_port(int slot, bool on)
{
	if (slot < 1 || slot > WIRES_PORTS) {
		return;
	}
	k_mutex_lock(&lock, K_FOREVER);
	w.on[slot - 1] = on;
	if (w.up) {
		(void)apply();
	}
	k_mutex_unlock(&lock);
}

int wires_set(const int8_t wanted[WIRES_PINS])
{
	int ret;

	for (int p = 0; p < WIRES_PINS; p++) {
		if (wanted[p] < NONE || wanted[p] >= WIRES_BUSES) {
			return -EINVAL;
		}
	}
	k_mutex_lock(&lock, K_FOREVER);
	memcpy(w.wanted, wanted, sizeof(w.wanted));
	ret = w.up ? apply() : 0;
	k_mutex_unlock(&lock);

	return ret;
}

void wires_get(int8_t wanted[WIRES_PINS], int8_t closed[WIRES_PINS])
{
	k_mutex_lock(&lock, K_FOREVER);
	if (wanted != NULL) {
		memcpy(wanted, w.wanted, sizeof(w.wanted));
	}
	if (closed != NULL) {
		memcpy(closed, w.closed, sizeof(w.closed));
	}
	k_mutex_unlock(&lock);
}

void wires_name(int bus, const char *name)
{
	if (bus >= 0 && bus < WIRES_BUSES) {
		k_mutex_lock(&lock, K_FOREVER);
		snprintf(names[bus], sizeof(names[bus]), "%s", name);
		k_mutex_unlock(&lock);
	}
}

/* --- JSON ------------------------------------------------------------------------ */

struct wire_pin {
	int32_t port;
	int32_t pin;
	char *bus;
};

static const struct json_obj_descr pin_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct wire_pin, port, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct wire_pin, pin, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct wire_pin, bus, JSON_TOK_STRING),
};

struct wires_req {
	struct wire_pin pins[WIRES_PINS];
	size_t pins_len;
	char *names[WIRES_BUSES];
	size_t names_len;
};

static const struct json_obj_descr req_descr[] = {
	JSON_OBJ_DESCR_OBJ_ARRAY(struct wires_req, pins, WIRES_PINS, pins_len, pin_descr,
				 ARRAY_SIZE(pin_descr)),
	JSON_OBJ_DESCR_ARRAY(struct wires_req, names, WIRES_BUSES, names_len, JSON_TOK_STRING),
};

/* A name the JSON and the page can carry as it is */
static bool name_ok(const char *s)
{
	size_t n = strlen(s);

	if (n >= WIRES_NAME_LEN) {
		return false;
	}
	for (size_t i = 0; i < n; i++) {
		if ((uint8_t)s[i] < ' ' || s[i] == '"' || s[i] == '\\' || s[i] == '<' || s[i] == '>') {
			return false;
		}
	}
	return true;
}

int wires_parse(char *body, size_t len, int8_t wanted[WIRES_PINS], bool *has_pins,
		char names_out[WIRES_BUSES][WIRES_NAME_LEN], bool *has_names, const char **why)
{
	static BAY_EXT_RAM struct wires_req r;
	int64_t fields;

	memset(&r, 0, sizeof(r));
	fields = json_obj_parse(body, len, req_descr, ARRAY_SIZE(req_descr), &r);
	if (fields < 0) {
		*why = "{\"pins\": [{\"port\": 1, \"pin\": 3, \"bus\": \"A\"}, ...], \"names\": [...]}";
		return -EINVAL;
	}
	*has_pins = fields & BIT(0);
	*has_names = fields & BIT(1);
	for (int p = 0; p < WIRES_PINS; p++) {
		wanted[p] = NONE;
	}
	for (size_t i = 0; i < r.pins_len; i++) {
		const struct wire_pin *e = &r.pins[i];
		int p = (e->port - 1) * WIRES_PORT_PINS + (e->pin - 1);

		if (e->port < 1 || e->port > WIRES_PORTS || e->pin < 1 || e->pin > WIRES_PORT_PINS) {
			*why = "port: 1-4, pin: 1-8";
			return -EINVAL;
		}
		if (e->bus == NULL || e->bus[0] < 'A' || e->bus[0] > 'H' || e->bus[1] != '\0') {
			*why = "bus: A-H";
			return -EINVAL;
		}
		if (wanted[p] != NONE) {
			*why = "a pin goes on one bus";
			return -EINVAL;
		}
		wanted[p] = e->bus[0] - 'A';
	}
	if (*has_names && r.names_len != WIRES_BUSES) {
		*why = "names: one per bus, A to H";
		return -EINVAL;
	}
	for (size_t b = 0; *has_names && b < WIRES_BUSES; b++) {
		if (!name_ok(r.names[b])) {
			*why = "a name: under 24 characters, no quotes, backslashes or angle brackets";
			return -EINVAL;
		}
		snprintf(names_out[b], WIRES_NAME_LEN, "%s", r.names[b]);
	}

	return 0;
}

int wires_json(char *buf, size_t size, int changed)
{
	int n;

#define ADD(...)                                                                                   \
	do {                                                                                       \
		if (n >= 0 && (size_t)n < size) {                                                  \
			n += snprintf(buf + n, size - n, __VA_ARGS__);                             \
		}                                                                                  \
	} while (false)

	k_mutex_lock(&lock, K_FOREVER);
	n = snprintf(buf, size, "{\"matrix\":%s,\"error\":%s%s%s,", w.up ? "true" : "false",
		     w.error != NULL ? "\"" : "", w.error != NULL ? w.error : "null",
		     w.error != NULL ? "\"" : "");
	if (changed >= 0) {
		ADD("\"changed\":%d,", changed);
	}
	ADD("\"names\":[");
	for (int b = 0; b < WIRES_BUSES; b++) {
		ADD("%s\"%s\"", b ? "," : "", names[b]);
	}
	ADD("],\"pins\":[");
	for (int p = 0, k = 0; p < WIRES_PINS; p++) {
		if (w.wanted[p] != NONE) {
			ADD("%s{\"port\":%d,\"pin\":%d,\"bus\":\"%c\",\"closed\":%s}", k++ ? "," : "",
			    p / WIRES_PORT_PINS + 1, p % WIRES_PORT_PINS + 1, 'A' + w.wanted[p],
			    w.closed[p] == w.wanted[p] ? "true" : "false");
		}
	}
	ADD("],\"ports\":[");
	for (int i = 0; i < WIRES_PORTS; i++) {
		char vref[8] = "null";

		if (vref_mv[i] >= 0) {
			snprintf(vref, sizeof(vref), "%d", vref_mv[i]);
		}
		ADD("%s{\"port\":%d,\"on\":%s,\"vref_mv\":%s,\"held\":%s}", i ? "," : "", i + 1,
		    w.on[i] ? "true" : "false", vref, may_wire(i) ? "false" : "true");
	}
	ADD("]}");
	k_mutex_unlock(&lock);

#undef ADD
	return n >= 0 && (size_t)n < size ? n : -ENOMEM;
}
