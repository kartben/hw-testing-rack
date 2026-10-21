/*
 * Wi-Fi station, hostname and reconnection (see hwtr/net.h).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/net/hostname.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/net/wifi_credentials.h>
#include <zephyr/logging/log.h>
#include <zephyr/settings/settings.h>
#include <zephyr/shell/shell.h>

#if defined(CONFIG_WIFI_ESP32)
#include <esp_wifi.h>
#endif

#include <hwtr/net.h>

LOG_MODULE_REGISTER(hwtr_net, CONFIG_HWTR_RACK_LOG_LEVEL);

#define RECONNECT_DELAY K_SECONDS(10)

#define NET_THREAD_STACK_SIZE 4096
#define NET_THREAD_PRIORITY   K_PRIO_PREEMPT(10)

static const char *prefix = "";
static char id[HWTR_ID_MAX_LEN + 1];
static char fallback[HWTR_ID_MAX_LEN + 1];
static char addr_str[NET_IPV4_ADDR_LEN];
static atomic_t has_addr;
static atomic_t wifi_up;
static hwtr_net_addr_cb_t addr_cb;

static struct net_mgmt_event_callback wifi_cb;
static struct net_mgmt_event_callback ipv4_cb;
static K_SEM_DEFINE(connect_sem, 0, 1);

static void reconnect_handler(struct k_work *work)
{
	ARG_UNUSED(work);
	k_sem_give(&connect_sem);
}

static K_WORK_DELAYABLE_DEFINE(reconnect_work, reconnect_handler);

/* --- Radio: TX power ceiling and 20 MHz channels ----------------------------- */

static int8_t tx_power_dbm = CONFIG_HWTR_NET_TX_POWER_DBM;

static void tx_power_apply(void)
{
#if defined(CONFIG_WIFI_ESP32)
	esp_err_t err = esp_wifi_set_max_tx_power(tx_power_dbm * 4);

	if (err != ESP_OK) {
		LOG_WRN("cannot set the TX power to %d dBm (%d)", tx_power_dbm, err);
	}
#endif
}

/*
 * Before every connection: a rack's nodes share one 2.4 GHz channel with the
 * DUTs' radios a few cm away, so no 40 MHz channel spilling onto the next one
 * and no more power than the AP 1-3 m away needs.
 */
static void radio_apply(void)
{
#if defined(CONFIG_WIFI_ESP32)
	wifi_mode_t mode;
	esp_err_t err;

	/* The bandwidth belongs to the station interface: it must exist */
	if (esp_wifi_get_mode(&mode) == ESP_OK && mode == ESP32_WIFI_MODE_NULL) {
		(void)esp_wifi_set_mode(ESP32_WIFI_MODE_STA);
	}
	err = esp_wifi_set_bandwidth(WIFI_IF_STA, WIFI_BW20);
	if (err != ESP_OK) {
		LOG_WRN("cannot set 20 MHz channels (%d)", err);
	}
#endif
	tx_power_apply();
}

#if defined(CONFIG_SETTINGS)
static int radio_settings_set(const char *key, size_t len, settings_read_cb read_cb,
			      void *cb_arg)
{
	int8_t dbm;

	if (!settings_name_steq(key, "txpower", NULL)) {
		return -ENOENT;
	}
	if (len != sizeof(dbm) || read_cb(cb_arg, &dbm, sizeof(dbm)) != sizeof(dbm)) {
		return -EINVAL;
	}
	if (dbm >= 2 && dbm <= 20) {
		tx_power_dbm = dbm;
	}

	return 0;
}

SETTINGS_STATIC_HANDLER_DEFINE(hwtr_radio, "radio", NULL, radio_settings_set, NULL, NULL);
#endif

#if defined(CONFIG_SHELL)
static int cmd_radio(const struct shell *sh, size_t argc, char **argv)
{
	if (argc > 1) {
		char *end;
		long dbm = strtol(argv[1], &end, 10);

		if (*end != '\0' || dbm < 2 || dbm > 20) {
			shell_error(sh, "TX power: 2 to 20 dBm");
			return -EINVAL;
		}
		tx_power_dbm = (int8_t)dbm;
		tx_power_apply();
#if defined(CONFIG_SETTINGS)
		(void)settings_save_one("radio/txpower", &tx_power_dbm, sizeof(tx_power_dbm));
#endif
	}

#if defined(CONFIG_WIFI_ESP32)
	int8_t quarter = 0;
	wifi_bandwidth_t bw = 0;

	(void)esp_wifi_get_max_tx_power(&quarter);
	(void)esp_wifi_get_bandwidth(WIFI_IF_STA, &bw);
	shell_print(sh, "TX power: %d dBm asked, %d.%02d dBm in the radio; %s MHz channels",
		    tx_power_dbm, quarter / 4, quarter % 4 * 25, bw == WIFI_BW40 ? "40" : "20");
#else
	shell_print(sh, "TX power: %d dBm asked", tx_power_dbm);
#endif

	return 0;
}

SHELL_CMD_ARG_REGISTER(radio, NULL, "Wi-Fi TX power: [<dBm>] 2-20 (persistent)", cmd_radio, 1, 1);
#endif

static void wifi_event_handler(struct net_mgmt_event_callback *cb, uint64_t event,
			       struct net_if *iface)
{
	const struct wifi_status *status = cb->info;

	ARG_UNUSED(iface);

	switch (event) {
	case NET_EVENT_WIFI_CONNECT_RESULT:
		if (status != NULL && status->status != 0) {
			LOG_WRN("Wi-Fi connection failed (%d)", status->status);
			k_work_reschedule(&reconnect_work, RECONNECT_DELAY);
		} else {
			atomic_set(&wifi_up, 1);
			LOG_INF("Wi-Fi connected");
		}
		break;
	case NET_EVENT_WIFI_DISCONNECT_RESULT:
		atomic_set(&wifi_up, 0);
		atomic_set(&has_addr, 0);
		LOG_WRN("Wi-Fi disconnected, retrying");
		k_work_reschedule(&reconnect_work, RECONNECT_DELAY);
		break;
	default:
		break;
	}
}

static void ipv4_event_handler(struct net_mgmt_event_callback *cb, uint64_t event,
			       struct net_if *iface)
{
	struct net_in_addr *addr;

	ARG_UNUSED(cb);

	if (event == NET_EVENT_IPV4_ADDR_DEL) {
		atomic_set(&has_addr, 0);
		return;
	}

	addr = net_if_ipv4_get_global_addr(iface, NET_ADDR_PREFERRED);
	if (addr == NULL) {
		return;
	}

	net_addr_ntop(NET_AF_INET, addr, addr_str, sizeof(addr_str));
	atomic_set(&has_addr, 1);
	LOG_INF("%s.local is %s", net_hostname_get(), addr_str);
	if (addr_cb != NULL) {
		addr_cb(addr_str);
	}
}

static void net_thread(void *p1, void *p2, void *p3)
{
	struct net_if *iface = net_if_get_wifi_sta();

	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	if (iface == NULL) {
		LOG_ERR("no Wi-Fi interface");
		return;
	}

	while (true) {
		int ret;

		k_sem_take(&connect_sem, K_FOREVER);

		if (atomic_get(&wifi_up) != 0) {
			continue;
		}

		if (wifi_credentials_is_empty()) {
			LOG_WRN("no Wi-Fi credentials: \"wifi cred add -s <ssid> -k 1 -p <pass>\" "
				"then \"wifi cred auto_connect\"");
			continue;
		}

		radio_apply();
		ret = net_mgmt(NET_REQUEST_WIFI_CONNECT_STORED, iface, NULL, 0);
		if (ret != 0) {
			LOG_WRN("connect to stored networks failed (%d)", ret);
			k_work_reschedule(&reconnect_work, RECONNECT_DELAY);
		}
	}
}

K_THREAD_STACK_DEFINE(net_stack, NET_THREAD_STACK_SIZE);
static struct k_thread net_thread_data;

static void hostname_apply(void)
{
	char name[16 + HWTR_ID_MAX_LEN];
	const char *use = id[0] != '\0' ? id : fallback;
	size_t i;

	if (use[0] == '\0') {
		return;
	}

	snprintf(name, sizeof(name), "%s-%s", prefix, use);
	for (i = 0; name[i] != '\0'; i++) {
		name[i] = tolower((unsigned char)name[i]);
	}

	if (net_hostname_set(name, strlen(name)) != 0) {
		LOG_ERR("cannot set hostname %s", name);
	}
}

int hwtr_net_init(const char *name_prefix, const char *stored_id, hwtr_net_addr_cb_t on_addr)
{
	prefix = name_prefix;
	addr_cb = on_addr;
	strncpy(id, stored_id, sizeof(id) - 1);
	hostname_apply();
	LOG_INF("hostname %s.local", net_hostname_get());

	net_mgmt_init_event_callback(&wifi_cb, wifi_event_handler,
				     NET_EVENT_WIFI_CONNECT_RESULT |
				     NET_EVENT_WIFI_DISCONNECT_RESULT);
	net_mgmt_add_event_callback(&wifi_cb);

	net_mgmt_init_event_callback(&ipv4_cb, ipv4_event_handler,
				     NET_EVENT_IPV4_ADDR_ADD | NET_EVENT_IPV4_ADDR_DEL);
	net_mgmt_add_event_callback(&ipv4_cb);

	k_thread_create(&net_thread_data, net_stack, K_THREAD_STACK_SIZEOF(net_stack), net_thread,
			NULL, NULL, NULL, NET_THREAD_PRIORITY, 0, K_NO_WAIT);
	k_thread_name_set(&net_thread_data, "hwtr_net");

	k_sem_give(&connect_sem);

	return 0;
}

bool hwtr_net_connected(void)
{
	return atomic_get(&has_addr) != 0;
}

const char *hwtr_net_addr(void)
{
	return hwtr_net_connected() ? addr_str : "";
}

const char *hwtr_net_id(void)
{
	return id;
}

int hwtr_net_id_set(const char *new_id)
{
	size_t len = strlen(new_id);

	if (len == 0 || len > HWTR_ID_MAX_LEN) {
		return -EINVAL;
	}
	for (size_t i = 0; i < len; i++) {
		if (!isalnum((unsigned char)new_id[i]) && new_id[i] != '-') {
			return -EINVAL;
		}
	}

	strcpy(id, new_id);
	hostname_apply();

	return 0;
}

int hwtr_net_fallback_id(const char *name)
{
	if (strlen(name) == 0 || strlen(name) > HWTR_ID_MAX_LEN) {
		return -EINVAL;
	}
	if (strcmp(name, fallback) == 0) {
		return 0;
	}
	strcpy(fallback, name);
	if (id[0] == '\0') {
		hostname_apply();
		LOG_INF("hostname %s.local (rack position)", net_hostname_get());
	}

	return 0;
}

int hwtr_net_mac(uint8_t mac[6])
{
	struct net_if *iface = net_if_get_wifi_sta();
	struct net_linkaddr *ll;

	if (iface == NULL) {
		iface = net_if_get_default();
	}
	ll = iface != NULL ? net_if_get_link_addr(iface) : NULL;
	if (ll == NULL || ll->len < 6) {
		return -ENODEV;
	}
	memcpy(mac, ll->addr, 6);

	return 0;
}
