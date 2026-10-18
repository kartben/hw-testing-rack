/*
 * Copyright (c) 2025 Franz Parzer <Franz.Parzer@htl-steyr.ac.at>
 * Copyright (c) 2026 The hw-testing-rack authors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief Diodes AP33772S USB PD 3.1 EPR sink controller: multi-function device.
 *
 * The MFD owns the I2C access, the status register and its interrupt, and
 * decodes the source's capabilities (PDOs).  Its children use it: the
 * regulator (the contract) and the sensor (VOUT, current, temperature).
 * Register map from the AP33772S datasheet (DS46176) and the sensor driver
 * proposed upstream in zephyrproject-rtos/zephyr#114554, reshaped as an MFD
 * and with that PR's open review points addressed: PDOs and RDOs are
 * (de)serialized with explicit little-endian shifts and masks, not
 * bit-fields; the NTC table registers are written as 16-bit values;
 * I2C errors are returned, not masked by a timeout; polling and the
 * interrupt start only once the device is configured; a PPS/AVS request is
 * clamped into the PDO's range.
 */

#ifndef ZEPHYR_INCLUDE_DRIVERS_MFD_AP33772S_H_
#define ZEPHYR_INCLUDE_DRIVERS_MFD_AP33772S_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>

#ifdef __cplusplus
extern "C" {
#endif

/** @name Registers */
/** @{ */
#define AP33772S_REG_STATUS    0x01 /**< events since the last read (cleared by reading) */
#define AP33772S_REG_MASK      0x02 /**< which events assert INT */
#define AP33772S_REG_OPMODE    0x03
#define AP33772S_REG_CONFIG    0x04
#define AP33772S_REG_PDCONFIG  0x05
#define AP33772S_REG_SYSTEM    0x06 /**< bits 1:0 VOUTCTL */
#define AP33772S_REG_TR25      0x0C /**< NTC resistance at 25 °C, ohms (16 bit) */
#define AP33772S_REG_TR50      0x0D
#define AP33772S_REG_TR75      0x0E
#define AP33772S_REG_TR100     0x0F
#define AP33772S_REG_VOLTAGE   0x11 /**< VOUT, 16 bit, 80 mV/LSB */
#define AP33772S_REG_CURRENT   0x12 /**< current, 8 bit, 24 mA/LSB */
#define AP33772S_REG_TEMP      0x13 /**< temperature, °C */
#define AP33772S_REG_VREQ      0x14 /**< contract voltage, 16 bit, 50 mV/LSB */
#define AP33772S_REG_IREQ      0x15 /**< contract current, 16 bit, 10 mA/LSB */
#define AP33772S_REG_VSELMIN   0x16 /**< minimum voltage for the switch, 200 mV/LSB */
#define AP33772S_REG_SRCPDO    0x20 /**< 13 source PDOs, 2 bytes each */
#define AP33772S_REG_PD_REQMSG 0x31 /**< request: voltage[7:0], current[11:8], PDO[15:12] */
#define AP33772S_REG_PD_CMDMSG 0x32
#define AP33772S_REG_PD_MSGRLT 0x33 /**< result of the last request */
/** @} */

/** SYSTEM.VOUTCTL: the output switch follows the contract / forced off / forced on */
#define AP33772S_VOUTCTL_MASK 0x03
#define AP33772S_VOUTCTL_AUTO 0x00
#define AP33772S_VOUTCTL_OFF  0x01
#define AP33772S_VOUTCTL_ON   0x02

/** PD_MSGRLT values */
#define AP33772S_MSGRLT_SUCCESS 1

/** Events: bits of the STATUS register, used as the callbacks' pin mask */
enum mfd_ap33772s_event {
	AP33772S_EVENT_STARTED = 0, /**< the chip (re)started */
	AP33772S_EVENT_READY = 1,   /**< a negotiation finished (see PD_MSGRLT) */
	AP33772S_EVENT_NEWPDO = 2,  /**< new source capabilities (also: EPR ones appeared) */
	AP33772S_EVENT_UVP = 3,     /**< under-voltage: the switch is off */
	AP33772S_EVENT_OVP = 4,     /**< over-voltage */
	AP33772S_EVENT_OCP = 5,     /**< over-current */
	AP33772S_EVENT_OTP = 6,     /**< over-temperature */
};

/** Number of source PDOs: 1-7 SPR, 8-13 EPR */
#define AP33772S_PDO_COUNT    13
#define AP33772S_PDO_FIRST_EPR 8

enum ap33772s_pdo_type {
	AP33772S_PDO_NONE = 0, /**< not offered */
	AP33772S_PDO_FIXED,
	AP33772S_PDO_PPS,      /**< SPR programmable */
	AP33772S_PDO_AVS,      /**< EPR adjustable */
};

/** A source capability, decoded */
struct ap33772s_pdo {
	enum ap33772s_pdo_type type;
	bool epr;
	uint32_t min_mv; /**< == max_mv for a fixed PDO */
	uint32_t max_mv;
	uint32_t max_ma; /**< lower bound of the advertised current range */
};

/** Read one register */
int mfd_ap33772s_reg_read(const struct device *dev, uint8_t reg, uint8_t *val);

/** Write one register */
int mfd_ap33772s_reg_write(const struct device *dev, uint8_t reg, uint8_t val);

/** Read a multi-byte register (little-endian values) */
int mfd_ap33772s_burst_read(const struct device *dev, uint8_t reg, void *buf, size_t len);

/** Write a multi-byte register */
int mfd_ap33772s_burst_write(const struct device *dev, uint8_t reg, const void *buf, size_t len);

/**
 * @brief The source capabilities, decoded.
 *
 * pdos[i] is PDO number i + 1.  Cached since the last new-PDO event, or read
 * again with refresh.
 *
 * @return number of PDOs offered, or a negative errno
 */
int mfd_ap33772s_get_pdos(const struct device *dev, struct ap33772s_pdo pdos[AP33772S_PDO_COUNT],
			  bool refresh);

/**
 * @brief Read and dispatch the status now (also done on INT or by polling).
 *
 * @return the events read (BIT(enum mfd_ap33772s_event)), or a negative errno
 */
int mfd_ap33772s_poll(const struct device *dev);

/** Over-voltage/current/temperature events seen since the last call with clear */
uint8_t mfd_ap33772s_faults(const struct device *dev, bool clear);

/**
 * @brief Add an event callback.
 *
 * callback->pin_mask selects the events (BIT(enum mfd_ap33772s_event)); the
 * handler gets the events that fired as its pins argument.  Called from the
 * system work queue, or from mfd_ap33772s_poll()'s caller.
 */
int mfd_ap33772s_add_callback(const struct device *dev, struct gpio_callback *callback);

/** Remove an event callback */
int mfd_ap33772s_remove_callback(const struct device *dev, struct gpio_callback *callback);

/**
 * @brief Re-apply the chip's configuration (interrupt mask, NTC table).
 *
 * The chip runs from VBUS: after VBUS comes back it starts with its
 * defaults.  Call this, or let a STARTED event do it.
 */
int mfd_ap33772s_configure(const struct device *dev);

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_INCLUDE_DRIVERS_MFD_AP33772S_H_ */
