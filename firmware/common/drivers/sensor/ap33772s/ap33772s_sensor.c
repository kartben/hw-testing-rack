/*
 * Copyright (c) 2025 Franz Parzer <Franz.Parzer@htl-steyr.ac.at>
 * Copyright (c) 2026 The hw-testing-rack authors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/* AP33772S measurements: VOUT, current through the sense resistor, NTC temperature */

#define DT_DRV_COMPAT diodes_ap33772s_sensor

#include <errno.h>

#include <zephyr/device.h>
#include <zephyr/drivers/mfd/ap33772s.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/sys/byteorder.h>

struct ap33772s_sensor_config {
	const struct device *mfd;
};

struct ap33772s_sensor_data {
	uint32_t mv;
	uint32_t ma;
	int8_t temp_c;
};

static int ap33772s_sensor_sample_fetch(const struct device *dev, enum sensor_channel chan)
{
	const struct ap33772s_sensor_config *config = dev->config;
	struct ap33772s_sensor_data *data = dev->data;
	uint8_t buf[2];
	uint8_t val;
	int ret;

	if (chan == SENSOR_CHAN_ALL || chan == SENSOR_CHAN_VOLTAGE) {
		ret = mfd_ap33772s_burst_read(config->mfd, AP33772S_REG_VOLTAGE, buf, sizeof(buf));
		if (ret != 0) {
			return ret;
		}
		data->mv = sys_get_le16(buf) * 80;
	}
	if (chan == SENSOR_CHAN_ALL || chan == SENSOR_CHAN_CURRENT) {
		ret = mfd_ap33772s_reg_read(config->mfd, AP33772S_REG_CURRENT, &val);
		if (ret != 0) {
			return ret;
		}
		data->ma = val * 24;
	}
	if (chan == SENSOR_CHAN_ALL || chan == SENSOR_CHAN_DIE_TEMP ||
	    chan == SENSOR_CHAN_AMBIENT_TEMP) {
		ret = mfd_ap33772s_reg_read(config->mfd, AP33772S_REG_TEMP, &val);
		if (ret != 0) {
			return ret;
		}
		data->temp_c = (int8_t)val;
	}

	return 0;
}

static int ap33772s_sensor_channel_get(const struct device *dev, enum sensor_channel chan,
				       struct sensor_value *val)
{
	struct ap33772s_sensor_data *data = dev->data;

	switch (chan) {
	case SENSOR_CHAN_VOLTAGE:
		return sensor_value_from_milli(val, data->mv);
	case SENSOR_CHAN_CURRENT:
		return sensor_value_from_milli(val, data->ma);
	case SENSOR_CHAN_DIE_TEMP:
	case SENSOR_CHAN_AMBIENT_TEMP:
		val->val1 = data->temp_c;
		val->val2 = 0;
		return 0;
	default:
		return -ENOTSUP;
	}
}

static DEVICE_API(sensor, ap33772s_sensor_api) = {
	.sample_fetch = ap33772s_sensor_sample_fetch,
	.channel_get = ap33772s_sensor_channel_get,
};

static int ap33772s_sensor_init(const struct device *dev)
{
	const struct ap33772s_sensor_config *config = dev->config;

	return device_is_ready(config->mfd) ? 0 : -ENODEV;
}

#define AP33772S_SENSOR_DEFINE(inst)                                                               \
	static struct ap33772s_sensor_data ap33772s_sensor_data_##inst;                            \
	static const struct ap33772s_sensor_config ap33772s_sensor_config_##inst = {               \
		.mfd = DEVICE_DT_GET(DT_INST_PARENT(inst)),                                        \
	};                                                                                         \
	SENSOR_DEVICE_DT_INST_DEFINE(inst, ap33772s_sensor_init, NULL,                             \
				     &ap33772s_sensor_data_##inst, &ap33772s_sensor_config_##inst, \
				     POST_KERNEL, CONFIG_SENSOR_INIT_PRIORITY,                     \
				     &ap33772s_sensor_api);

DT_INST_FOREACH_STATUS_OKAY(AP33772S_SENSOR_DEFINE)
