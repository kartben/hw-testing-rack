/*
 * Wi-Fi station, hostname (<prefix>-<id>.local over mDNS) and reconnection,
 * shared by the bay node and the power hub.
 *
 * Credentials come from the Wi-Fi credentials library: stored with
 * "wifi cred add" (settings) or built in with CONFIG_WIFI_CREDENTIALS_STATIC.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HWTR_NET_H_
#define HWTR_NET_H_

#include <stdbool.h>
#include <stdint.h>

#define HWTR_ID_MAX_LEN 15

/* Called with the IPv4 address as a string when the interface gets one */
typedef void (*hwtr_net_addr_cb_t)(const char *addr);

/*
 * prefix: "bay", "rack"; id: the stored id ("" keeps CONFIG_NET_HOSTNAME,
 * unique per MAC).  Starts connecting with the stored credentials.
 */
int hwtr_net_init(const char *prefix, const char *id, hwtr_net_addr_cb_t on_addr);

bool hwtr_net_connected(void);
/* IPv4 address as a string, "" when there is none */
const char *hwtr_net_addr(void);
const char *hwtr_net_id(void);
/* 1-15 letters, digits and '-'; sets the hostname (the caller stores it) */
int hwtr_net_id_set(const char *id);
/*
 * The name to use while no id is set (a bay's rack position, "c3"): the
 * hostname becomes <prefix>-<name>, not stored; an id set by hand wins.
 */
int hwtr_net_fallback_id(const char *name);
/* The interface's MAC address (6 bytes); 0 if there is one */
int hwtr_net_mac(uint8_t mac[6]);

#endif /* HWTR_NET_H_ */
