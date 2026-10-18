/*
 * Flat accessors to struct hwtr_jpeg_scan for the ctypes test (test_jpeg.py).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <hwtr/jpeg.h>

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

EXPORT size_t shim_size(void)
{
	return sizeof(struct hwtr_jpeg_scan);
}

EXPORT void shim_init(struct hwtr_jpeg_scan *s)
{
	hwtr_jpeg_scan_init(s);
}

EXPORT size_t shim_feed(struct hwtr_jpeg_scan *s, const uint8_t *p, size_t n, size_t *start)
{
	return hwtr_jpeg_scan_feed(s, p, n, start);
}

EXPORT int shim_state(const struct hwtr_jpeg_scan *s)
{
	return (int)s->state;
}

EXPORT int shim_lead_ff(const struct hwtr_jpeg_scan *s)
{
	return s->lead_ff;
}

EXPORT unsigned int shim_image_size(const struct hwtr_jpeg_scan *s)
{
	return s->size;
}
