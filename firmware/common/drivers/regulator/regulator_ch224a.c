/*
 * Copyright (c) 2026 The hw-testing-rack authors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The USB PD contract of a WCH CH224A sink as a regulator.
 *
 * The chip negotiates by itself: at plug-in it asks for the voltage its CFG1
 * resistor selects (startup-microvolt), and keeps the contract, EPR's
 * keep-alive included, with nobody talking to it.  Over I2C (on in the
 * one-resistor mode) the controller asks for another voltage: 5, 9, 12, 15,
 * 20 or 28 V, or a PPS / AVS voltage in 100 mV steps.  The chip cannot
 * report the voltage in place: get_voltage() is the one asked for, while the
 * protocol status says PD.  PG (open drain) is the only interrupt: it follows
 * the contract, and drives the regulator callback.  No switch: enable and
 * disable are not offered (always on).
 */

#define DT_DRV_COMPAT wch_ch224a

#include <errno.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/regulator.h>
#include <zephyr/drivers/regulator/ch224a.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/util.h>

LOG_MODULE_REGISTER(regulator_ch224a, CONFIG_REGULATOR_LOG_LEVEL);

#define MODE_UNKNOWN 0xFF
#define STEP_UV      100000 /* PPS and AVS requests */

/* Index: the VOLTAGE register's value */
static const int32_t fixed_uv[] = {5000000, 9000000, 12000000, 15000000, 20000000, 28000000};

/* Message types in the header (USB PD 3.2, 6.2.1.1.2) */
#define MSG_SOURCE_CAPABILITIES     0x01 /* data message */
#define MSG_EPR_SOURCE_CAPABILITIES 0x11 /* extended message */

struct regulator_ch224a_config {
	struct regulator_common_config common;
	struct i2c_dt_spec i2c;
	struct gpio_dt_spec pg;
	int32_t startup_uv;
};

struct regulator_ch224a_data {
	struct regulator_common_data common;
	const struct device *dev;
	struct k_mutex lock;
	struct gpio_callback pg_cb;
	struct k_work pg_work;
	int32_t req_uv; /* asked for: startup-microvolt until set_voltage() */
	uint8_t mode;   /* the VOLTAGE register's last value */
	int good;       /* PG as last reported, -1 not yet */
	regulator_callback_t cb;
	const void *cb_data;
};

static int reg_read(const struct device *dev, uint8_t reg, uint8_t *val)
{
	const struct regulator_ch224a_config *config = dev->config;

	return i2c_reg_read_byte_dt(&config->i2c, reg, val);
}

static int reg_write(const struct device *dev, uint8_t reg, uint8_t val)
{
	const struct regulator_ch224a_config *config = dev->config;

	return i2c_reg_write_byte_dt(&config->i2c, reg, val);
}

int regulator_ch224a_get_status(const struct device *dev, uint8_t *status)
{
	const struct regulator_ch224a_config *config = dev->config;
	struct regulator_ch224a_data *data = dev->data;
	int ret = reg_read(dev, CH224A_REG_STATUS, status);

	if (ret != 0) {
		/* It runs from VBUS: once back, it starts again from CFG1 */
		k_mutex_lock(&data->lock, K_FOREVER);
		data->req_uv = config->startup_uv;
		data->mode = MODE_UNKNOWN;
		k_mutex_unlock(&data->lock);
	}

	return ret;
}

int regulator_ch224a_power_good(const struct device *dev)
{
	const struct regulator_ch224a_config *config = dev->config;

	if (config->pg.port == NULL) {
		return -ENOTSUP;
	}

	return gpio_pin_get_dt(&config->pg);
}

static void decode_pdo(uint32_t raw, int index, struct ch224a_pdo *p)
{
	*p = (struct ch224a_pdo){.raw = raw, .epr = index + 1 >= CH224A_PDO_FIRST_EPR};

	if (raw == 0U) {
		p->type = CH224A_PDO_NONE;
		return;
	}

	switch (FIELD_GET(GENMASK(31, 30), raw)) {
	case 0: /* fixed */
		p->type = CH224A_PDO_FIXED;
		p->min_mv = FIELD_GET(GENMASK(19, 10), raw) * 50U;
		p->max_mv = p->min_mv;
		p->max_ma = FIELD_GET(GENMASK(9, 0), raw) * 10U;
		break;
	case 3: /* augmented */
		if (FIELD_GET(GENMASK(29, 28), raw) == 0U) {
			p->type = CH224A_PDO_PPS;
			p->max_mv = FIELD_GET(GENMASK(24, 17), raw) * 100U;
			p->min_mv = FIELD_GET(GENMASK(15, 8), raw) * 100U;
			p->max_ma = FIELD_GET(GENMASK(6, 0), raw) * 50U;
		} else if (FIELD_GET(GENMASK(29, 28), raw) == 1U) {
			p->type = CH224A_PDO_AVS;
			p->max_mv = FIELD_GET(GENMASK(25, 17), raw) * 100U;
			p->min_mv = FIELD_GET(GENMASK(15, 8), raw) * 100U;
			p->pdp_w = FIELD_GET(GENMASK(7, 0), raw);
		} else {
			p->type = CH224A_PDO_OTHER;
		}
		break;
	default: /* battery, variable */
		p->type = CH224A_PDO_OTHER;
		break;
	}
}

int regulator_ch224a_get_pdos(const struct device *dev, struct ch224a_pdo pdos[CH224A_PDO_COUNT])
{
	uint8_t buf[CH224A_SRCCAP_LEN];
	uint16_t header;
	bool extended;
	size_t off;
	int n;

	/* One register per transfer: the datasheet does not say the address increments */
	for (size_t i = 0; i < sizeof(buf); i++) {
		int ret = reg_read(dev, CH224A_REG_SRCCAP + i, &buf[i]);

		if (ret != 0) {
			return ret;
		}
	}

	/*
	 * The whole message as received: its header, for EPR an extended
	 * header (bits 8:0 the data size in bytes), then the PDOs.
	 */
	header = sys_get_le16(&buf[0]);
	if (header == 0U) {
		return -ENODATA;
	}
	extended = (header & BIT(15)) != 0U;
	if (FIELD_GET(GENMASK(4, 0), header) !=
	    (extended ? MSG_EPR_SOURCE_CAPABILITIES : MSG_SOURCE_CAPABILITIES)) {
		LOG_WRN("not a source capabilities message: header 0x%04x", header);
		return -EBADMSG;
	}
	if (extended) {
		n = (sys_get_le16(&buf[2]) & GENMASK(8, 0)) / 4;
		off = 4;
	} else {
		n = FIELD_GET(GENMASK(14, 12), header);
		off = 2;
	}
	n = MIN(n, MIN(CH224A_PDO_COUNT, (int)((sizeof(buf) - off) / 4)));

	for (int i = 0; i < CH224A_PDO_COUNT; i++) {
		decode_pdo(i < n ? sys_get_le32(&buf[off + 4 * i]) : 0U, i, &pdos[i]);
	}

	return n;
}

/* Lock held */
static int request_mode(const struct device *dev, uint8_t mode, int32_t uv)
{
	struct regulator_ch224a_data *data = dev->data;
	int ret = reg_write(dev, CH224A_REG_VOLTAGE, mode);

	if (ret == 0) {
		data->mode = mode;
		data->req_uv = uv;
	}

	return ret;
}

/* A PPS or AVS voltage; lock held */
static int request_programmable(const struct device *dev, enum ch224a_pdo_type type, int32_t uv)
{
	struct regulator_ch224a_data *data = dev->data;
	uint16_t steps = uv / STEP_UV;
	uint8_t mode;
	int ret;

	if (type == CH224A_PDO_PPS) {
		if (steps > UINT8_MAX) {
			return -EINVAL;
		}
		mode = CH224A_VOLTAGE_PPS;
		ret = reg_write(dev, CH224A_REG_PPS, steps);
	} else {
		/* Low byte first, then the high bits with the enable */
		mode = CH224A_VOLTAGE_AVS;
		ret = reg_write(dev, CH224A_REG_AVS_L, steps & 0xFF);
		if (ret == 0) {
			ret = reg_write(dev, CH224A_REG_AVS_H, BIT(7) | ((steps >> 8) & 0x7F));
		}
	}
	if (ret != 0) {
		return ret;
	}

	/* Once in that mode, the chip follows the voltage register alone */
	if (data->mode == mode) {
		data->req_uv = uv;
		return 0;
	}

	return request_mode(dev, mode, uv);
}

static int regulator_ch224a_set_voltage(const struct device *dev, int32_t min_uv, int32_t max_uv)
{
	const struct regulator_ch224a_config *config = dev->config;
	struct regulator_ch224a_data *data = dev->data;
	struct ch224a_pdo pdos[CH224A_PDO_COUNT];
	int32_t uv;
	int ret = -EINVAL;
	int n;

	min_uv = MAX(min_uv, config->common.min_uv);
	max_uv = MIN(max_uv, config->common.max_uv);

	k_mutex_lock(&data->lock, K_FOREVER);

	/* A fixed voltage: the lowest in the range */
	for (uint8_t i = 0; i < ARRAY_SIZE(fixed_uv); i++) {
		if (fixed_uv[i] >= min_uv && fixed_uv[i] <= max_uv) {
			ret = request_mode(dev, i, fixed_uv[i]);
			goto out;
		}
	}

	/* Otherwise a PPS or AVS voltage, in a range the charger offers */
	uv = DIV_ROUND_UP(min_uv, STEP_UV) * STEP_UV;
	n = uv <= max_uv ? regulator_ch224a_get_pdos(dev, pdos) : 0;
	if (n < 0) {
		ret = n;
	}
	for (int i = 0; i < n; i++) {
		if ((pdos[i].type == CH224A_PDO_PPS || pdos[i].type == CH224A_PDO_AVS) &&
		    uv / 1000 >= pdos[i].min_mv && uv / 1000 <= pdos[i].max_mv) {
			ret = request_programmable(dev, pdos[i].type, uv);
			break;
		}
	}

out:
	k_mutex_unlock(&data->lock);

	return ret;
}

static int regulator_ch224a_get_voltage(const struct device *dev, int32_t *volt_uv)
{
	struct regulator_ch224a_data *data = dev->data;
	uint8_t status;
	int ret = regulator_ch224a_get_status(dev, &status);

	if (ret != 0) {
		return ret;
	}

	/* No PD contract: the source's default 5 V */
	k_mutex_lock(&data->lock, K_FOREVER);
	*volt_uv = (status & CH224A_STATUS_PD) != 0U ? data->req_uv : fixed_uv[0];
	k_mutex_unlock(&data->lock);

	return 0;
}

static unsigned int regulator_ch224a_count_voltages(const struct device *dev)
{
	ARG_UNUSED(dev);

	return ARRAY_SIZE(fixed_uv);
}

static int regulator_ch224a_list_voltage(const struct device *dev, unsigned int idx,
					 int32_t *volt_uv)
{
	ARG_UNUSED(dev);

	if (idx >= ARRAY_SIZE(fixed_uv)) {
		return -EINVAL;
	}
	*volt_uv = fixed_uv[idx];

	return 0;
}

static int regulator_ch224a_get_current_limit(const struct device *dev, int32_t *curr_ua)
{
	uint8_t status, val;
	int ret = regulator_ch224a_get_status(dev, &status);

	if (ret != 0) {
		return ret;
	}
	/* Valid with a PD contract only */
	if ((status & CH224A_STATUS_PD) == 0U) {
		return -ENODATA;
	}
	ret = reg_read(dev, CH224A_REG_CURRENT, &val);
	if (ret != 0) {
		return ret;
	}
	*curr_ua = val * 50000;

	return 0;
}

static int regulator_ch224a_set_callback(const struct device *dev, regulator_callback_t cb,
					 const void *const user_data)
{
	struct regulator_ch224a_data *data = dev->data;

	k_mutex_lock(&data->lock, K_FOREVER);
	data->cb = cb;
	data->cb_data = user_data;
	data->good = -1;
	k_mutex_unlock(&data->lock);

	/* Report the state now, then its changes */
	if (cb != NULL) {
		k_work_submit(&data->pg_work);
	}

	return 0;
}

static void pg_work_handler(struct k_work *work)
{
	struct regulator_ch224a_data *data = CONTAINER_OF(work, struct regulator_ch224a_data,
							  pg_work);
	int good = regulator_ch224a_power_good(data->dev);
	regulator_callback_t cb;
	const void *cb_data;

	if (good < 0) {
		return;
	}

	k_mutex_lock(&data->lock, K_FOREVER);
	cb = good != data->good ? data->cb : NULL;
	cb_data = data->cb_data;
	data->good = good;
	k_mutex_unlock(&data->lock);

	if (cb != NULL) {
		const struct regulator_event evt = {
			.type = good ? REGULATOR_VOLTAGE_DETECTED : REGULATOR_VOLTAGE_REMOVED,
		};

		cb(data->dev, &evt, cb_data);
	}
}

static void pg_isr(const struct device *port, struct gpio_callback *cb, gpio_port_pins_t pins)
{
	struct regulator_ch224a_data *data = CONTAINER_OF(cb, struct regulator_ch224a_data, pg_cb);

	ARG_UNUSED(port);
	ARG_UNUSED(pins);

	k_work_submit(&data->pg_work);
}

static DEVICE_API(regulator, regulator_ch224a_api) = {
	.count_voltages = regulator_ch224a_count_voltages,
	.list_voltage = regulator_ch224a_list_voltage,
	.set_voltage = regulator_ch224a_set_voltage,
	.get_voltage = regulator_ch224a_get_voltage,
	.get_current_limit = regulator_ch224a_get_current_limit,
	.set_callback = regulator_ch224a_set_callback,
};

static int regulator_ch224a_init(const struct device *dev)
{
	const struct regulator_ch224a_config *config = dev->config;
	struct regulator_ch224a_data *data = dev->data;
	uint8_t status;
	int ret;

	if (!i2c_is_ready_dt(&config->i2c)) {
		return -ENODEV;
	}

	data->dev = dev;
	data->req_uv = config->startup_uv;
	data->mode = MODE_UNKNOWN;
	data->good = -1;
	k_mutex_init(&data->lock);
	k_work_init(&data->pg_work, pg_work_handler);
	regulator_common_data_init(dev);

	ret = regulator_ch224a_get_status(dev, &status);
	if (ret != 0) {
		LOG_ERR("no answer (%d): VBUS off?", ret);
		return ret;
	}
	LOG_DBG("status 0x%02x", status);

	if (config->pg.port != NULL) {
		if (!gpio_is_ready_dt(&config->pg)) {
			return -ENODEV;
		}
		ret = gpio_pin_configure_dt(&config->pg, GPIO_INPUT);
		if (ret == 0) {
			gpio_init_callback(&data->pg_cb, pg_isr, BIT(config->pg.pin));
			ret = gpio_add_callback_dt(&config->pg, &data->pg_cb);
		}
		if (ret == 0) {
			ret = gpio_pin_interrupt_configure_dt(&config->pg, GPIO_INT_EDGE_BOTH);
		}
		if (ret != 0) {
			return ret;
		}
	}

	/* No switch: the output is VBUS, on whenever there is one */
	return regulator_common_init(dev, true);
}

#define REGULATOR_CH224A_DEFINE(inst)                                                              \
	static struct regulator_ch224a_data regulator_ch224a_data_##inst;                          \
	static const struct regulator_ch224a_config regulator_ch224a_config_##inst = {             \
		.common = REGULATOR_DT_INST_COMMON_CONFIG_INIT(inst),                              \
		.i2c = I2C_DT_SPEC_INST_GET(inst),                                                 \
		.pg = GPIO_DT_SPEC_INST_GET_OR(inst, pg_gpios, {0}),                               \
		.startup_uv = DT_INST_PROP(inst, startup_microvolt),                               \
	};                                                                                         \
	DEVICE_DT_INST_DEFINE(inst, regulator_ch224a_init, NULL, &regulator_ch224a_data_##inst,    \
			      &regulator_ch224a_config_##inst, POST_KERNEL,                        \
			      CONFIG_REGULATOR_CH224A_INIT_PRIORITY, &regulator_ch224a_api);

DT_INST_FOREACH_STATUS_OKAY(REGULATOR_CH224A_DEFINE)
