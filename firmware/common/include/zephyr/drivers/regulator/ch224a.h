/*
 * Copyright (c) 2026 The hw-testing-rack authors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief WCH CH224A USB PD 3.2 sink controller, as a regulator: extras.
 *
 * The regulator API covers the contract: set_voltage() asks for a voltage,
 * get_voltage() is the voltage asked for (the chip cannot report the one in
 * place), get_current_limit() the current the charger grants, and the
 * callback follows PG (REGULATOR_VOLTAGE_DETECTED once the contract is in
 * place, REGULATOR_VOLTAGE_REMOVED when it is lost).  This header adds what
 * the regulator API has no call for: the protocol status and the charger's
 * offers.  Register map from the WCH CH224 datasheet (manual 1, v2.1, 5.2.3).
 */

#ifndef ZEPHYR_INCLUDE_DRIVERS_REGULATOR_CH224A_H_
#define ZEPHYR_INCLUDE_DRIVERS_REGULATOR_CH224A_H_

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/sys/util.h>

#ifdef __cplusplus
extern "C" {
#endif

/** @name Registers */
/** @{ */
#define CH224A_REG_STATUS  0x09 /**< protocol status, read only */
#define CH224A_REG_VOLTAGE 0x0A /**< voltage request, write only (CH224A_VOLTAGE_*) */
#define CH224A_REG_CURRENT 0x50 /**< current the charger grants, 50 mA/LSB, valid with PD */
#define CH224A_REG_AVS_H   0x51 /**< AVS request bits 14:8, bit 7: enable; written second */
#define CH224A_REG_AVS_L   0x52 /**< AVS request bits 7:0, 100 mV/LSB; written first */
#define CH224A_REG_PPS     0x53 /**< PPS request, 100 mV/LSB */
#define CH224A_REG_SRCCAP  0x60 /**< 0x60-0x8F: the charger's (EPR_)Source_Capabilities */
#define CH224A_SRCCAP_LEN  48
/** @} */

/** @name STATUS bits: the protocol in place */
/** @{ */
#define CH224A_STATUS_BC  BIT(0)
#define CH224A_STATUS_QC2 BIT(1)
#define CH224A_STATUS_QC3 BIT(2)
#define CH224A_STATUS_PD  BIT(3)
#define CH224A_STATUS_EPR BIT(4)
/** @} */

/** @name VOLTAGE register values */
/** @{ */
#define CH224A_VOLTAGE_5V  0
#define CH224A_VOLTAGE_9V  1
#define CH224A_VOLTAGE_12V 2
#define CH224A_VOLTAGE_15V 3
#define CH224A_VOLTAGE_20V 4
#define CH224A_VOLTAGE_28V 5
#define CH224A_VOLTAGE_PPS 6
#define CH224A_VOLTAGE_AVS 7
/** @} */

/** PDO positions: an SPR message holds up to 7; an EPR one 7 SPR (unused ones zero) then 4 EPR */
#define CH224A_PDO_COUNT     11
#define CH224A_PDO_FIRST_EPR 8

/** PDO 1's "EPR Mode Capable" bit (USB PD 3.2, 6.4.1.2.1) */
#define CH224A_PDO1_EPR_CAPABLE BIT(23)

enum ch224a_pdo_type {
	CH224A_PDO_NONE = 0, /**< not offered, or an unused SPR position of an EPR message */
	CH224A_PDO_FIXED,
	CH224A_PDO_PPS,      /**< SPR programmable */
	CH224A_PDO_AVS,      /**< EPR adjustable */
	CH224A_PDO_OTHER,    /**< battery, variable, or an APDO this driver does not use */
};

/** A source capability, decoded */
struct ch224a_pdo {
	enum ch224a_pdo_type type;
	bool epr;        /**< position CH224A_PDO_FIRST_EPR or later */
	uint32_t min_mv; /**< == max_mv for a fixed PDO */
	uint32_t max_mv;
	uint32_t max_ma; /**< 0 for AVS (see pdp_w) */
	uint16_t pdp_w;  /**< AVS: the source's power, W */
	uint32_t raw;
};

/**
 * @brief The protocol status (CH224A_STATUS_*).
 *
 * @return 0, or a negative errno (no answer: VBUS off?)
 */
int regulator_ch224a_get_status(const struct device *dev, uint8_t *status);

/**
 * @brief PG: whether a contract is in place.
 *
 * @return 1 power good, 0 not, -ENOTSUP without pg-gpios
 */
int regulator_ch224a_power_good(const struct device *dev);

/**
 * @brief The charger's offers, decoded.
 *
 * The chip keeps the last Source_Capabilities message: in EPR mode the
 * EPR_Source_Capabilities, otherwise the SPR one (the datasheet promises
 * it only from chargers under 100 W).  pdos[i] is PDO position i + 1.
 *
 * @return the number of positions, -ENODATA when the chip holds no
 *         message, or a negative errno
 */
int regulator_ch224a_get_pdos(const struct device *dev, struct ch224a_pdo pdos[CH224A_PDO_COUNT]);

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_INCLUDE_DRIVERS_REGULATOR_CH224A_H_ */
