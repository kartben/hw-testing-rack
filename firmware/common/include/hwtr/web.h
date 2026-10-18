/*
 * HTTP helpers shared by the bay node and the power hub web servers.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HWTR_WEB_H_
#define HWTR_WEB_H_

#include <zephyr/net/http/server.h>
#include <zephyr/net/http/service.h>
#include <zephyr/sys/util.h>

/* A file gzipped into the image (generate_inc_file_for_target --gzip), served as is */
#define HWTR_WEB_STATIC_GZ(_data, _type)                                                           \
	{                                                                                          \
		.common = {                                                                        \
			.type = HTTP_RESOURCE_TYPE_STATIC,                                         \
			.bitmask_of_supported_http_methods = BIT(HTTP_GET),                        \
			.content_encoding = "gzip",                                                \
			.content_type = _type,                                                     \
		},                                                                                 \
		.static_data = _data,                                                              \
		.static_data_len = sizeof(_data),                                                  \
	}

/* HTTP_RESOURCE_DEFINE with a service name that is itself a macro (expanded first) */
#define HWTR_HTTP_RESOURCE_DEFINE(_name, _service, _resource, _detail)                             \
	HTTP_RESOURCE_DEFINE(_name, _service, _resource, _detail)

#endif /* HWTR_WEB_H_ */
