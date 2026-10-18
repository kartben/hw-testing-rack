/*
 * Where a JPEG image ends, in a byte stream that arrives in pieces.
 *
 * The Arducam Mega hands its FIFO over in buffer-sized chunks with no end
 * of frame mark, and its FIFO length may run past the image: the image is
 * over at its EOI marker (FF D9).  A plain search for FF D9 would stop
 * early in an EXIF thumbnail, so the scanner skips the marker segments by
 * their length and only looks for EOI in the entropy-coded data, where FF is
 * always followed by 00 (stuffing), D0-D7 (restart) or a marker.
 *
 * Plain C, no Zephyr: tested on the host (firmware/bay-node/tests/jpeg).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HWTR_JPEG_H_
#define HWTR_JPEG_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum hwtr_jpeg_state {
	HWTR_JPEG_SOI,       /* looking for FF D8 (bytes before it are skipped) */
	HWTR_JPEG_MARKER,    /* between segments: FF, then a marker */
	HWTR_JPEG_LEN,       /* a segment's length, two bytes */
	HWTR_JPEG_SKIP,      /* inside a segment */
	HWTR_JPEG_SCAN,      /* entropy-coded data after SOS */
	HWTR_JPEG_DONE,      /* FF D9 seen */
	HWTR_JPEG_ERROR,     /* not a JPEG */
};

struct hwtr_jpeg_scan {
	enum hwtr_jpeg_state state;
	bool ff;             /* the previous byte was FF */
	bool sos;            /* the segment being skipped is a SOS header */
	bool lead_ff;        /* SOI straddled two pieces: write one FF before this piece's bytes */
	uint8_t len_hi;
	uint8_t len_got;
	uint32_t skip;       /* bytes left in the segment */
	uint32_t skipped;    /* bytes before SOI */
	uint32_t size;       /* bytes of the image so far, SOI to EOI */
};

void hwtr_jpeg_scan_init(struct hwtr_jpeg_scan *s);

/*
 * The next piece of the stream.  *start: offset in it where the image
 * starts (non-zero only in the piece with SOI).  Returns how many bytes of
 * the piece, from *start, belong to the image: all of them, or up to and
 * including EOI once it is found (s->state == HWTR_JPEG_DONE).
 */
size_t hwtr_jpeg_scan_feed(struct hwtr_jpeg_scan *s, const uint8_t *p, size_t n, size_t *start);

static inline bool hwtr_jpeg_scan_done(const struct hwtr_jpeg_scan *s)
{
	return s->state == HWTR_JPEG_DONE;
}

#endif /* HWTR_JPEG_H_ */
