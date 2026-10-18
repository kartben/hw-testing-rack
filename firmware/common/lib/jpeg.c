/*
 * Where a JPEG image ends, in a byte stream that arrives in pieces
 * (hwtr/jpeg.h).
 *
 *   FF D8                  SOI, the image starts
 *   FF xx LH LL ...        a segment: its length LH LL counts itself
 *   FF DA LH LL ... data   SOS: a header, then entropy-coded data, where FF
 *                          is followed by 00 (a stuffed FF), D0-D7 (restart),
 *                          FF (fill) or a marker
 *   FF D9                  EOI, the image ends
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <hwtr/jpeg.h>

/* Bytes tolerated before SOI */
#define SOI_MAX 1024

void hwtr_jpeg_scan_init(struct hwtr_jpeg_scan *s)
{
	memset(s, 0, sizeof(*s));
	s->state = HWTR_JPEG_SOI;
}

static void segment(struct hwtr_jpeg_scan *s, uint8_t marker)
{
	s->sos = marker == 0xDA;
	s->len_got = 0;
	s->state = HWTR_JPEG_LEN;
}

size_t hwtr_jpeg_scan_feed(struct hwtr_jpeg_scan *s, const uint8_t *p, size_t n, size_t *start)
{
	size_t i;

	*start = 0;
	s->lead_ff = false;

	for (i = 0; i < n; i++) {
		uint8_t b = p[i];

		if (s->state == HWTR_JPEG_DONE || s->state == HWTR_JPEG_ERROR) {
			return 0;
		}
		if (s->state == HWTR_JPEG_SOI) {
			if (s->ff && b == 0xD8) {
				if (i == 0) {
					/* The FF ended the previous piece */
					s->lead_ff = true;
					s->skipped--;
				} else {
					*start = i - 1;
					s->skipped--;
				}
				s->size = 2;
				s->ff = false;
				s->state = HWTR_JPEG_MARKER;
				continue;
			}
			s->ff = b == 0xFF;
			if (++s->skipped > SOI_MAX) {
				s->state = HWTR_JPEG_ERROR;
				return 0;
			}
			continue;
		}

		s->size++;
		switch (s->state) {
		case HWTR_JPEG_MARKER:
			if (!s->ff) {
				if (b != 0xFF) {
					s->state = HWTR_JPEG_ERROR; /* junk between segments */
					return i + 1 - *start;
				}
				s->ff = true;
				break;
			}
			if (b == 0xFF) {
				break; /* fill */
			}
			s->ff = false;
			if (b == 0xD9) {
				s->state = HWTR_JPEG_DONE;
				return i + 1 - *start;
			}
			if (b == 0xD8 || b == 0x00) {
				s->state = HWTR_JPEG_ERROR;
				return i + 1 - *start;
			}
			if (b == 0x01 || (b >= 0xD0 && b <= 0xD7)) {
				break; /* no length */
			}
			segment(s, b);
			break;

		case HWTR_JPEG_LEN:
			if (s->len_got++ == 0) {
				s->len_hi = b;
				break;
			}
			s->skip = ((uint32_t)s->len_hi << 8 | b);
			if (s->skip < 2) {
				s->state = HWTR_JPEG_ERROR;
				return i + 1 - *start;
			}
			s->skip -= 2;
			s->state = s->skip != 0 ? HWTR_JPEG_SKIP
				   : s->sos     ? HWTR_JPEG_SCAN
						: HWTR_JPEG_MARKER;
			break;

		case HWTR_JPEG_SKIP: {
			/* This byte and as many more as the segment holds */
			size_t k = n - i < s->skip ? n - i : s->skip;

			i += k - 1;
			s->size += (uint32_t)(k - 1);
			s->skip -= (uint32_t)k;
			if (s->skip == 0) {
				s->state = s->sos ? HWTR_JPEG_SCAN : HWTR_JPEG_MARKER;
			}
			break;
		}

		case HWTR_JPEG_SCAN:
			if (!s->ff) {
				s->ff = b == 0xFF;
				break;
			}
			if (b == 0xFF) {
				break; /* fill */
			}
			s->ff = false;
			if (b == 0x00 || (b >= 0xD0 && b <= 0xD7)) {
				break; /* a stuffed FF, a restart */
			}
			if (b == 0xD9) {
				s->state = HWTR_JPEG_DONE;
				return i + 1 - *start;
			}
			/* Another table or scan (progressive JPEG) */
			segment(s, b);
			break;

		default:
			break;
		}
	}

	return s->state == HWTR_JPEG_SOI ? 0 : n - *start;
}
