/*
 * Copyright (c) 2026 The hw-testing-rack authors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The USB PD contract of an AP33772S sink as a regulator.
 *
 * Voltages are the source's fixed PDOs; set_voltage() requests the lowest
 * fixed PDO inside the range, or a PPS/AVS voltage when no fixed one fits.
 * The current limit is the operating current requested along with it.
 * enable/disable drive the output switch (VOUTCTL auto / forced off).
 */

#define DT_DRV_COMPAT diodes_ap33772s_regulator

#include <errno.h>

#include <zephyr/device.h>
#include <zephyr/drivers/mfd/ap33772s.h>
#include <zephyr/drivers/regulator.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/util.h>

LOG_MODULE_REGISTER(regulator_ap33772s, CONFIG_REGULATOR_LOG_LEVEL);

#define REQUEST_TIMEOUT_MS 500
#define POLL_MS            10

struct regulator_ap33772s_config {
	struct regulator_common_config common;
	const struct device *mfd;
};

struct regulator_ap33772s_data {
	struct regulator_common_data common;
	const struct device *dev;
	struct gpio_callback mfd_cb;
	struct k_sem ready;
	uint32_t op_ma;          /* operating current to request */
	uint8_t pdo;             /* PDO of the last successful request, 0 none */
	regulator_callback_t cb;
	const void *cb_data;
};

/* CURRENT_SEL: 1.00 A + 0.25 A per step, 15 = the PDO's maximum */
static uint8_t current_code(uint32_t ma)
{
	if (ma >= 4750) {
		return 15;
	}
	return ma <= 1000 ? 0 : (ma - 1000) / 250;
}

static void notify(struct regulator_ap33772s_data *data, enum regulator_event_type type)
{
	const struct regulator_event evt = {.type = type};

	if (data->cb != NULL) {
		data->cb(data->dev, &evt, data->cb_data);
	}
}

static void mfd_event(const struct device *mfd, struct gpio_callback *cb, gpio_port_pins_t events)
{
	struct regulator_ap33772s_data *data =
		CONTAINER_OF(cb, struct regulator_ap33772s_data, mfd_cb);

	ARG_UNUSED(mfd);

	if (events & BIT(AP33772S_EVENT_READY)) {
		k_sem_give(&data->ready);
		notify(data, REGULATOR_VOLTAGE_DETECTED);
	}
	if (events & (BIT(AP33772S_EVENT_STARTED) | BIT(AP33772S_EVENT_UVP) |
		      BIT(AP33772S_EVENT_OVP) | BIT(AP33772S_EVENT_OCP) | BIT(AP33772S_EVENT_OTP))) {
		data->pdo = 0;
		notify(data, REGULATOR_VOLTAGE_REMOVED);
	}
}

/* Send a request and wait for the chip's answer */
static int request(const struct device *dev, uint8_t pdo, const struct ap33772s_pdo *cap,
		   uint32_t mv)
{
	const struct regulator_ap33772s_config *config = dev->config;
	struct regulator_ap33772s_data *data = dev->data;
	uint32_t unit = cap->epr ? 200 : 100;
	uint32_t ma = MIN(data->op_ma, cap->max_ma);
	uint16_t rdo = FIELD_PREP(GENMASK(7, 0), mv / unit) |
		       FIELD_PREP(GENMASK(11, 8), current_code(ma)) |
		       FIELD_PREP(GENMASK(15, 12), pdo);
	uint8_t buf[2];
	uint8_t result;
	int ret;

	k_sem_reset(&data->ready);
	sys_put_le16(rdo, buf);
	ret = mfd_ap33772s_burst_write(config->mfd, AP33772S_REG_PD_REQMSG, buf, sizeof(buf));
	if (ret != 0) {
		return ret;
	}

	/* Poll as well: the caller may be the work queue that would handle INT */
	for (int t = 0; t < REQUEST_TIMEOUT_MS; t += POLL_MS) {
		if (k_sem_take(&data->ready, K_MSEC(POLL_MS)) == 0) {
			break;
		}
		(void)mfd_ap33772s_poll(config->mfd);
		if (k_sem_count_get(&data->ready) > 0) {
			break;
		}
		if (t + POLL_MS >= REQUEST_TIMEOUT_MS) {
			return -ETIMEDOUT;
		}
	}

	ret = mfd_ap33772s_reg_read(config->mfd, AP33772S_REG_PD_MSGRLT, &result);
	if (ret != 0) {
		return ret;
	}
	if (result != AP33772S_MSGRLT_SUCCESS) {
		LOG_WRN("PDO %u at %u mV refused (%u)", pdo, mv, result);
		return -EIO;
	}

	data->pdo = pdo;
	LOG_INF("contract: PDO %u, %u mV, %u mA", pdo, mv, ma);

	return 0;
}

static unsigned int regulator_ap33772s_count_voltages(const struct device *dev)
{
	const struct regulator_ap33772s_config *config = dev->config;
	struct ap33772s_pdo pdos[AP33772S_PDO_COUNT];
	unsigned int n = 0;

	if (mfd_ap33772s_get_pdos(config->mfd, pdos, false) < 0) {
		return 0;
	}
	for (int i = 0; i < AP33772S_PDO_COUNT; i++) {
		n += pdos[i].type == AP33772S_PDO_FIXED;
	}

	return n;
}

static int regulator_ap33772s_list_voltage(const struct device *dev, unsigned int idx,
					   int32_t *volt_uv)
{
	const struct regulator_ap33772s_config *config = dev->config;
	struct ap33772s_pdo pdos[AP33772S_PDO_COUNT];
	int ret = mfd_ap33772s_get_pdos(config->mfd, pdos, false);

	if (ret < 0) {
		return ret;
	}
	for (int i = 0; i < AP33772S_PDO_COUNT; i++) {
		if (pdos[i].type != AP33772S_PDO_FIXED) {
			continue;
		}
		if (idx-- == 0) {
			*volt_uv = pdos[i].max_mv * 1000;
			return 0;
		}
	}

	return -EINVAL;
}

static int regulator_ap33772s_set_voltage(const struct device *dev, int32_t min_uv,
					  int32_t max_uv)
{
	const struct regulator_ap33772s_config *config = dev->config;
	struct ap33772s_pdo pdos[AP33772S_PDO_COUNT];
	uint32_t min_mv = DIV_ROUND_UP(min_uv, 1000);
	uint32_t max_mv = max_uv / 1000;
	int best = -1;
	uint32_t mv = 0;
	int ret = mfd_ap33772s_get_pdos(config->mfd, pdos, true);

	if (ret < 0) {
		return ret;
	}

	/* The lowest fixed PDO in range */
	for (int i = 0; i < AP33772S_PDO_COUNT; i++) {
		if (pdos[i].type == AP33772S_PDO_FIXED && pdos[i].max_mv >= min_mv &&
		    pdos[i].max_mv <= max_mv && (best < 0 || pdos[i].max_mv < pdos[best].max_mv)) {
			best = i;
			mv = pdos[i].max_mv;
		}
	}

	/*
	 * Else a programmable one covering the range: the voltage is clamped
	 * to the PDO's own minimum and rounded to its step, and must still be
	 * within both the PDO and the range (an RDO below the minimum is
	 * invalid, zephyr#114554 review).
	 */
	for (int i = 0; best < 0 && i < AP33772S_PDO_COUNT; i++) {
		uint32_t unit = pdos[i].epr ? 200 : 100;
		uint32_t want = ROUND_UP(MAX(min_mv, pdos[i].min_mv), unit);

		if ((pdos[i].type == AP33772S_PDO_PPS || pdos[i].type == AP33772S_PDO_AVS) &&
		    want <= pdos[i].max_mv && want <= max_mv) {
			best = i;
			mv = want;
		}
	}

	if (best < 0 || mv > max_mv) {
		return -EINVAL;
	}

	return request(dev, best + 1, &pdos[best], mv);
}

static int regulator_ap33772s_get_voltage(const struct device *dev, int32_t *volt_uv)
{
	const struct regulator_ap33772s_config *config = dev->config;
	uint8_t buf[2];
	int ret = mfd_ap33772s_burst_read(config->mfd, AP33772S_REG_VREQ, buf, sizeof(buf));

	if (ret != 0) {
		return ret;
	}
	*volt_uv = sys_get_le16(buf) * 50000;

	return *volt_uv == 0 ? -ENODATA : 0;
}

static int regulator_ap33772s_set_current_limit(const struct device *dev, int32_t min_ua,
						int32_t max_ua)
{
	const struct regulator_ap33772s_config *config = dev->config;
	struct regulator_ap33772s_data *data = dev->data;
	struct ap33772s_pdo pdos[AP33772S_PDO_COUNT];
	int32_t volt_uv;
	int ret;

	ARG_UNUSED(min_ua);

	data->op_ma = max_ua / 1000;
	if (data->pdo == 0) {
		return 0;
	}

	/* Renegotiate the same PDO with the new current */
	ret = mfd_ap33772s_get_pdos(config->mfd, pdos, false);
	if (ret < 0) {
		return ret;
	}
	ret = regulator_ap33772s_get_voltage(dev, &volt_uv);
	if (ret != 0) {
		return ret;
	}

	return request(dev, data->pdo, &pdos[data->pdo - 1], volt_uv / 1000);
}

static int regulator_ap33772s_get_current_limit(const struct device *dev, int32_t *curr_ua)
{
	const struct regulator_ap33772s_config *config = dev->config;
	uint8_t buf[2];
	int ret = mfd_ap33772s_burst_read(config->mfd, AP33772S_REG_IREQ, buf, sizeof(buf));

	if (ret != 0) {
		return ret;
	}
	*curr_ua = sys_get_le16(buf) * 10000;

	return 0;
}

static int voutctl(const struct device *dev, uint8_t mode)
{
	const struct regulator_ap33772s_config *config = dev->config;
	uint8_t sys;
	int ret = mfd_ap33772s_reg_read(config->mfd, AP33772S_REG_SYSTEM, &sys);

	if (ret != 0) {
		return ret;
	}
	sys = (sys & ~AP33772S_VOUTCTL_MASK) | mode;

	return mfd_ap33772s_reg_write(config->mfd, AP33772S_REG_SYSTEM, sys);
}

static int regulator_ap33772s_enable(const struct device *dev)
{
	/* Auto: the switch is on whenever a contract is in place */
	return voutctl(dev, AP33772S_VOUTCTL_AUTO);
}

static int regulator_ap33772s_disable(const struct device *dev)
{
	return voutctl(dev, AP33772S_VOUTCTL_OFF);
}

static int regulator_ap33772s_get_error_flags(const struct device *dev,
					      regulator_error_flags_t *flags)
{
	const struct regulator_ap33772s_config *config = dev->config;
	uint8_t faults = mfd_ap33772s_faults(config->mfd, true);

	*flags = 0;
	if (faults & BIT(AP33772S_EVENT_OVP)) {
		*flags |= REGULATOR_ERROR_OVER_VOLTAGE;
	}
	if (faults & BIT(AP33772S_EVENT_OCP)) {
		*flags |= REGULATOR_ERROR_OVER_CURRENT;
	}
	if (faults & BIT(AP33772S_EVENT_OTP)) {
		*flags |= REGULATOR_ERROR_OVER_TEMP;
	}

	return 0;
}

static int regulator_ap33772s_set_callback(const struct device *dev, regulator_callback_t cb,
					   const void *const user_data)
{
	struct regulator_ap33772s_data *data = dev->data;

	data->cb = cb;
	data->cb_data = user_data;

	return 0;
}

static DEVICE_API(regulator, regulator_ap33772s_api) = {
	.enable = regulator_ap33772s_enable,
	.disable = regulator_ap33772s_disable,
	.count_voltages = regulator_ap33772s_count_voltages,
	.list_voltage = regulator_ap33772s_list_voltage,
	.set_voltage = regulator_ap33772s_set_voltage,
	.get_voltage = regulator_ap33772s_get_voltage,
	.set_current_limit = regulator_ap33772s_set_current_limit,
	.get_current_limit = regulator_ap33772s_get_current_limit,
	.get_error_flags = regulator_ap33772s_get_error_flags,
	.set_callback = regulator_ap33772s_set_callback,
};

static int regulator_ap33772s_init(const struct device *dev)
{
	const struct regulator_ap33772s_config *config = dev->config;
	struct regulator_ap33772s_data *data = dev->data;
	uint8_t sys;
	int ret;

	if (!device_is_ready(config->mfd)) {
		return -ENODEV;
	}

	data->dev = dev;
	data->op_ma = config->common.max_ua > 0 ? config->common.max_ua / 1000 : 5000;
	k_sem_init(&data->ready, 0, 1);
	regulator_common_data_init(dev);

	gpio_init_callback(&data->mfd_cb, mfd_event,
			   BIT(AP33772S_EVENT_STARTED) | BIT(AP33772S_EVENT_READY) |
			   BIT(AP33772S_EVENT_UVP) | BIT(AP33772S_EVENT_OVP) |
			   BIT(AP33772S_EVENT_OCP) | BIT(AP33772S_EVENT_OTP));
	ret = mfd_ap33772s_add_callback(config->mfd, &data->mfd_cb);
	if (ret != 0) {
		return ret;
	}

	ret = mfd_ap33772s_reg_read(config->mfd, AP33772S_REG_SYSTEM, &sys);
	if (ret != 0) {
		return ret;
	}

	return regulator_common_init(dev, (sys & AP33772S_VOUTCTL_MASK) != AP33772S_VOUTCTL_OFF);
}

#define REGULATOR_AP33772S_DEFINE(inst)                                                            \
	static struct regulator_ap33772s_data regulator_ap33772s_data_##inst;                      \
	static const struct regulator_ap33772s_config regulator_ap33772s_config_##inst = {         \
		.common = REGULATOR_DT_INST_COMMON_CONFIG_INIT(inst),                              \
		.mfd = DEVICE_DT_GET(DT_INST_PARENT(inst)),                                        \
	};                                                                                         \
	DEVICE_DT_INST_DEFINE(inst, regulator_ap33772s_init, NULL,                                 \
			      &regulator_ap33772s_data_##inst, &regulator_ap33772s_config_##inst,  \
			      POST_KERNEL, CONFIG_REGULATOR_AP33772S_INIT_PRIORITY,                \
			      &regulator_ap33772s_api);

DT_INST_FOREACH_STATUS_OKAY(REGULATOR_AP33772S_DEFINE)
