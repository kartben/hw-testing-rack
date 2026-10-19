/*
 * Copyright (c) 2025 Franz Parzer <Franz.Parzer@htl-steyr.ac.at>
 * Copyright (c) 2026 The hw-testing-rack authors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#define DT_DRV_COMPAT diodes_ap33772s

#include <errno.h>
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/gpio/gpio_utils.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/mfd/ap33772s.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/util.h>

LOG_MODULE_REGISTER(mfd_ap33772s, CONFIG_MFD_LOG_LEVEL);

#define FAULT_EVENTS                                                                               \
	(BIT(AP33772S_EVENT_UVP) | BIT(AP33772S_EVENT_OVP) | BIT(AP33772S_EVENT_OCP) |             \
	 BIT(AP33772S_EVENT_OTP))
#define ALL_EVENTS (BIT(AP33772S_EVENT_STARTED) | BIT(AP33772S_EVENT_READY) |                     \
		    BIT(AP33772S_EVENT_NEWPDO) | FAULT_EVENTS)

/* PDO fields (2 bytes, little-endian) */
#define PDO_VOLTAGE_MAX(w) ((w) & 0xFF)
#define PDO_VOLTAGE_MIN(w) (((w) >> 8) & 0x03)
#define PDO_CURRENT_MAX(w) (((w) >> 10) & 0x0F)
#define PDO_TYPE_APDO(w)   (((w) >> 14) & 0x01)
#define PDO_DETECT(w)      (((w) >> 15) & 0x01)

struct mfd_ap33772s_config {
	struct i2c_dt_spec i2c;
	struct gpio_dt_spec int_gpio;
	uint16_t poll_interval_ms;
	uint16_t epr_delay_ms;
	uint16_t tr[4];
	/* VSELMIN register value (200 mV/LSB), 0: the chip's default */
	uint8_t vselmin;
};

struct mfd_ap33772s_data {
	const struct device *dev;
	struct k_mutex lock;
	struct gpio_callback int_cb;
	struct k_work status_work;
	struct k_work_delayable epr_work;
	struct k_work_delayable poll_work;
	sys_slist_t callbacks;
	uint16_t raw_pdos[AP33772S_PDO_COUNT];
	uint8_t faults;
};

int mfd_ap33772s_reg_read(const struct device *dev, uint8_t reg, uint8_t *val)
{
	const struct mfd_ap33772s_config *config = dev->config;

	return i2c_reg_read_byte_dt(&config->i2c, reg, val);
}

int mfd_ap33772s_reg_write(const struct device *dev, uint8_t reg, uint8_t val)
{
	const struct mfd_ap33772s_config *config = dev->config;

	return i2c_reg_write_byte_dt(&config->i2c, reg, val);
}

int mfd_ap33772s_burst_read(const struct device *dev, uint8_t reg, void *buf, size_t len)
{
	const struct mfd_ap33772s_config *config = dev->config;

	return i2c_burst_read_dt(&config->i2c, reg, buf, len);
}

int mfd_ap33772s_burst_write(const struct device *dev, uint8_t reg, const void *buf, size_t len)
{
	const struct mfd_ap33772s_config *config = dev->config;

	return i2c_burst_write_dt(&config->i2c, reg, buf, len);
}

static int read_pdos(const struct device *dev, uint16_t raw[AP33772S_PDO_COUNT])
{
	uint8_t buf[AP33772S_PDO_COUNT * 2];
	int ret = mfd_ap33772s_burst_read(dev, AP33772S_REG_SRCPDO, buf, sizeof(buf));

	if (ret != 0) {
		return ret;
	}
	for (int i = 0; i < AP33772S_PDO_COUNT; i++) {
		raw[i] = sys_get_le16(&buf[2 * i]);
	}

	return 0;
}

static void decode_pdo(uint16_t w, int index, struct ap33772s_pdo *pdo)
{
	bool epr = index + 1 >= AP33772S_PDO_FIRST_EPR;
	uint32_t unit = epr ? 200 : 100;
	uint8_t cur = PDO_CURRENT_MAX(w);

	memset(pdo, 0, sizeof(*pdo));
	if (!PDO_DETECT(w)) {
		return;
	}

	pdo->epr = epr;
	pdo->max_mv = PDO_VOLTAGE_MAX(w) * unit;
	/* 0: below 1.24 A, 1-14: 1.0 + 0.25 n A and up, 15: 5 A and more */
	pdo->max_ma = cur == 15 ? 5000 : 1000 + 250 * cur;

	if (!PDO_TYPE_APDO(w)) {
		pdo->type = AP33772S_PDO_FIXED;
		pdo->min_mv = pdo->max_mv;
	} else {
		pdo->type = epr ? AP33772S_PDO_AVS : AP33772S_PDO_PPS;
		/* VOLTAGE_MIN: 1 = 3.3 V (SPR) / 15 V (EPR), 2 = up to 5 V / 20 V */
		if (PDO_VOLTAGE_MIN(w) == 2) {
			pdo->min_mv = epr ? 20000 : 5000;
		} else {
			pdo->min_mv = epr ? 15000 : 3300;
		}
	}
}

int mfd_ap33772s_get_pdos(const struct device *dev, struct ap33772s_pdo pdos[AP33772S_PDO_COUNT],
			  bool refresh)
{
	struct mfd_ap33772s_data *data = dev->data;
	int n = 0;

	k_mutex_lock(&data->lock, K_FOREVER);
	if (refresh) {
		int ret = read_pdos(dev, data->raw_pdos);

		if (ret != 0) {
			k_mutex_unlock(&data->lock);
			return ret;
		}
	}
	for (int i = 0; i < AP33772S_PDO_COUNT; i++) {
		decode_pdo(data->raw_pdos[i], i, &pdos[i]);
		n += pdos[i].type != AP33772S_PDO_NONE;
	}
	k_mutex_unlock(&data->lock);

	return n;
}

int mfd_ap33772s_configure(const struct device *dev)
{
	const struct mfd_ap33772s_config *config = dev->config;
	struct mfd_ap33772s_data *data = dev->data;
	uint8_t status;
	int ret;

	for (int i = 0; i < ARRAY_SIZE(config->tr); i++) {
		uint8_t buf[2];

		sys_put_le16(config->tr[i], buf);
		ret = mfd_ap33772s_burst_write(dev, AP33772S_REG_TR25 + i, buf, sizeof(buf));
		if (ret != 0) {
			return ret;
		}
	}

	ret = mfd_ap33772s_reg_write(dev, AP33772S_REG_MASK, ALL_EVENTS);
	if (ret != 0) {
		return ret;
	}

	if (config->vselmin != 0) {
		ret = mfd_ap33772s_reg_write(dev, AP33772S_REG_VSELMIN, config->vselmin);
		if (ret != 0) {
			return ret;
		}
	}

	/* Clear what happened before, read the offers */
	ret = mfd_ap33772s_reg_read(dev, AP33772S_REG_STATUS, &status);
	if (ret != 0) {
		return ret;
	}

	k_mutex_lock(&data->lock, K_FOREVER);
	ret = read_pdos(dev, data->raw_pdos);
	k_mutex_unlock(&data->lock);

	return ret;
}

uint8_t mfd_ap33772s_faults(const struct device *dev, bool clear)
{
	struct mfd_ap33772s_data *data = dev->data;
	uint8_t faults = data->faults;

	if (clear) {
		data->faults = 0;
	}

	return faults;
}

int mfd_ap33772s_poll(const struct device *dev)
{
	const struct mfd_ap33772s_config *config = dev->config;
	struct mfd_ap33772s_data *data = dev->data;
	uint8_t status;
	int ret;

	k_mutex_lock(&data->lock, K_FOREVER);
	/* Reading clears it: one reader, under the lock */
	ret = mfd_ap33772s_reg_read(dev, AP33772S_REG_STATUS, &status);
	if (ret == 0 && (status & BIT(AP33772S_EVENT_NEWPDO))) {
		ret = read_pdos(dev, data->raw_pdos);
	}
	k_mutex_unlock(&data->lock);

	if (ret != 0) {
		return ret;
	}
	status &= ALL_EVENTS;
	if (status == 0) {
		return 0;
	}

	LOG_DBG("status 0x%02x", status);
	data->faults |= status & FAULT_EVENTS;

	if (status & BIT(AP33772S_EVENT_STARTED)) {
		/* Back from no VBUS: the chip has its defaults again */
		(void)mfd_ap33772s_configure(dev);
	}
	if (status & BIT(AP33772S_EVENT_NEWPDO)) {
		/*
		 * After the first contract the chip enters EPR mode by itself,
		 * when the source offers it, and stores the EPR PDOs without
		 * telling: look again a little later.
		 */
		k_work_reschedule(&data->epr_work, K_MSEC(config->epr_delay_ms));
	}

	gpio_fire_callbacks(&data->callbacks, dev, status);

	return status;
}

int mfd_ap33772s_add_callback(const struct device *dev, struct gpio_callback *callback)
{
	struct mfd_ap33772s_data *data = dev->data;

	return gpio_manage_callback(&data->callbacks, callback, true);
}

int mfd_ap33772s_remove_callback(const struct device *dev, struct gpio_callback *callback)
{
	struct mfd_ap33772s_data *data = dev->data;

	return gpio_manage_callback(&data->callbacks, callback, false);
}

static void status_work_handler(struct k_work *work)
{
	struct mfd_ap33772s_data *data = CONTAINER_OF(work, struct mfd_ap33772s_data, status_work);
	const struct mfd_ap33772s_config *config = data->dev->config;

	(void)mfd_ap33772s_poll(data->dev);

	/* INT is level: still asserted means more events came in meanwhile */
	if (config->int_gpio.port != NULL && gpio_pin_get_dt(&config->int_gpio) > 0) {
		k_work_submit(&data->status_work);
	}
}

static void epr_work_handler(struct k_work *work)
{
	struct k_work_delayable *dwork = k_work_delayable_from_work(work);
	struct mfd_ap33772s_data *data = CONTAINER_OF(dwork, struct mfd_ap33772s_data, epr_work);
	uint16_t raw[AP33772S_PDO_COUNT];
	bool changed;

	if (read_pdos(data->dev, raw) != 0) {
		return;
	}

	k_mutex_lock(&data->lock, K_FOREVER);
	changed = memcmp(raw, data->raw_pdos, sizeof(raw)) != 0;
	memcpy(data->raw_pdos, raw, sizeof(raw));
	k_mutex_unlock(&data->lock);

	if (changed) {
		LOG_INF("EPR capabilities");
		gpio_fire_callbacks(&data->callbacks, data->dev, BIT(AP33772S_EVENT_NEWPDO));
	}
}

static void poll_work_handler(struct k_work *work)
{
	struct k_work_delayable *dwork = k_work_delayable_from_work(work);
	struct mfd_ap33772s_data *data = CONTAINER_OF(dwork, struct mfd_ap33772s_data, poll_work);
	const struct mfd_ap33772s_config *config = data->dev->config;

	(void)mfd_ap33772s_poll(data->dev);
	k_work_schedule(&data->poll_work, K_MSEC(config->poll_interval_ms));
}

static void int_isr(const struct device *port, struct gpio_callback *cb, gpio_port_pins_t pins)
{
	struct mfd_ap33772s_data *data = CONTAINER_OF(cb, struct mfd_ap33772s_data, int_cb);

	ARG_UNUSED(port);
	ARG_UNUSED(pins);

	k_work_submit(&data->status_work);
}

static int mfd_ap33772s_init(const struct device *dev)
{
	const struct mfd_ap33772s_config *config = dev->config;
	struct mfd_ap33772s_data *data = dev->data;
	int ret;

	if (!i2c_is_ready_dt(&config->i2c)) {
		return -ENODEV;
	}

	data->dev = dev;
	k_mutex_init(&data->lock);
	k_work_init(&data->status_work, status_work_handler);
	k_work_init_delayable(&data->epr_work, epr_work_handler);
	k_work_init_delayable(&data->poll_work, poll_work_handler);

	ret = mfd_ap33772s_configure(dev);
	if (ret != 0) {
		LOG_ERR("no answer (%d): VBUS off?", ret);
		return ret;
	}

	if (config->int_gpio.port == NULL) {
		k_work_schedule(&data->poll_work, K_MSEC(config->poll_interval_ms));
		return 0;
	}

	if (!gpio_is_ready_dt(&config->int_gpio)) {
		return -ENODEV;
	}
	ret = gpio_pin_configure_dt(&config->int_gpio, GPIO_INPUT);
	if (ret != 0) {
		return ret;
	}
	gpio_init_callback(&data->int_cb, int_isr, BIT(config->int_gpio.pin));
	ret = gpio_add_callback_dt(&config->int_gpio, &data->int_cb);
	if (ret != 0) {
		return ret;
	}
	ret = gpio_pin_interrupt_configure_dt(&config->int_gpio, GPIO_INT_EDGE_TO_ACTIVE);
	if (ret != 0) {
		return ret;
	}
	if (gpio_pin_get_dt(&config->int_gpio) > 0) {
		k_work_submit(&data->status_work);
	}

	return 0;
}

#define MFD_AP33772S_DEFINE(inst)                                                                  \
	static const struct mfd_ap33772s_config mfd_ap33772s_config_##inst = {                     \
		.i2c = I2C_DT_SPEC_INST_GET(inst),                                                 \
		.int_gpio = GPIO_DT_SPEC_INST_GET_OR(inst, int_gpios, {0}),                        \
		.poll_interval_ms = DT_INST_PROP(inst, poll_interval_ms),                          \
		.epr_delay_ms = DT_INST_PROP(inst, epr_delay_ms),                                  \
		.tr = {DT_INST_PROP(inst, tr25), DT_INST_PROP(inst, tr50),                         \
		       DT_INST_PROP(inst, tr75), DT_INST_PROP(inst, tr100)},                       \
		.vselmin = DT_INST_PROP_OR(inst, vselmin_microvolt, 0) / 200000,                   \
	};                                                                                         \
	BUILD_ASSERT(DT_INST_PROP_OR(inst, vselmin_microvolt, 0) / 200000 <= UINT8_MAX,            \
		     "vselmin-microvolt above the register's range");                              \
	static struct mfd_ap33772s_data mfd_ap33772s_data_##inst;                                  \
	DEVICE_DT_INST_DEFINE(inst, mfd_ap33772s_init, NULL, &mfd_ap33772s_data_##inst,            \
			      &mfd_ap33772s_config_##inst, POST_KERNEL,                            \
			      CONFIG_MFD_AP33772S_INIT_PRIORITY, NULL);

DT_INST_FOREACH_STATUS_OKAY(MFD_AP33772S_DEFINE)
