/*
 * hw-testing-rack bay node: shared declarations.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef BAY_H_
#define BAY_H_

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/kernel.h>

/* --- DUT power, fault, RESET/BOOT (dut.c) --------------------------------- */

struct dut_power_reading {
	int32_t bus_mv;
	int32_t current_ma;
	int32_t power_mw;
};

int dut_init(void);
int dut_power_set(bool on);
bool dut_power_get(void);
int dut_power_cycle(k_timeout_t off_time);
/* FAULT pin as it is right now (current limit / thermal shutdown) */
bool dut_fault_active(void);
/* Power was cut by the firmware after a persistent fault */
bool dut_fault_latched(void);
uint32_t dut_fault_count(void);
int dut_reset_set(bool asserted);
int dut_reset_pulse(k_timeout_t width);
int dut_boot_set(bool asserted);
/* BOOT held, RESET pulsed, BOOT released: most MCUs start their ROM loader */
int dut_enter_bootloader(void);
int dut_power_read(struct dut_power_reading *r);

/* --- USB data path (usb_mux.c) -------------------------------------------- */

enum bay_data_path {
	BAY_PATH_USBIP,   /* DUT <-> ESP32-S3 USB OTG, exported over USB/IP */
	BAY_PATH_CLASSIC, /* DUT <-> front PC port (laptop plugged or forced) */
	BAY_PATH_SERVICE, /* front PC port <-> ESP32-S3, DUT data disconnected */
};

int usb_mux_init(bool force_pc);
bool usb_mux_service(void);
bool usb_mux_pc_detected(void);
bool usb_mux_force_pc_get(void);
int usb_mux_force_pc_set(bool force);
enum bay_data_path usb_mux_path(void);
const char *bay_data_path_str(enum bay_data_path path);

/* --- USB host / USB/IP (usb_host.c) --------------------------------------- */

/* Devices enumerated on the DUT port (0 or 1 without a hub) */
int usb_host_device_count(void);
/* Open TCP sessions on the USB/IP port (an attached client keeps one) */
int usb_host_usbip_sessions(void);
bool usb_host_running(void);
/* SERVICE mode: stop the host and route the PHY to USB-Serial-JTAG */
int usb_host_release_phy(void);
/* Back from SERVICE mode: take the PHY and start the host again */
int usb_host_claim_phy(void);

/* --- Status LED (status_led.c) -------------------------------------------- */

int status_led_init(void);
void status_led_update(void);

/* --- AUX UART <-> TCP (aux_bridge.c) -------------------------------------- */

int aux_bridge_init(void);
uint32_t aux_bridge_baudrate(void);
int aux_bridge_set_baudrate(uint32_t baudrate);
bool aux_bridge_client_connected(void);
void aux_bridge_stats(uint32_t *rx_bytes, uint32_t *tx_bytes, uint32_t *dropped);

/* --- Network, identity (net.c) -------------------------------------------- */

#define BAY_ID_MAX_LEN 15

int bay_net_init(const char *id);
bool bay_net_connected(void);
/* IPv4 address as a string, "" when there is none */
const char *bay_net_addr(void);
const char *bay_id(void);
int bay_id_set(const char *id);

/* --- Web page, JSON API, /metrics (web.c) --------------------------------- */

int web_init(void);

/* --- Settings (main.c) ---------------------------------------------------- */

int bay_settings_save_force_pc(bool force);
int bay_settings_save_id(const char *id);

#endif /* BAY_H_ */
