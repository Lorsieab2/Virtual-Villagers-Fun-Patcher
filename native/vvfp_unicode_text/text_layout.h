/* text_layout.h -- laying text out by the shared spec's rules (docs/UNICODE_SPEC.md row 3).  Header-only,
   file-static, no CRT; included after text_utf8.h.

   FITTING (tl_fit_ellipsis).  The longest start of whole units of a text whose width with "…" after it is at most
   a room, trailing spaces dropped, then "…" (U+2026; byte 0x85 in a text of one byte per character). */
#ifndef VVFP_TEXT_LAYOUT_H
#define VVFP_TEXT_LAYOUT_H

#include "text_utf8.h"

/* ---- Fitting with "…" ------------------------------------------------------------------------- */

typedef int (*tl_width_fn)(void *state, const unsigned char *s, int len);

/* text[0..len) fitted to `room` pixels (measured by width): the text itself when it fits (returns len and out
   untouched), else its longest start of whole units whose width with "…" is at most room (at least nothing),
   trailing spaces dropped, then "…" -- written to out (cap bytes, with its NUL); returns the bytes written. */
static int tl_fit_ellipsis(const unsigned char *text, int len, int room, tl_width_fn width, void *state,
                           unsigned char *out, int cap) {
    unsigned char mark[4];
    int nm, best = 0, at = 0, one_byte = !ut_has_utf8(text, text + len);
    const unsigned char *s = text, *end = text + len;
    if (width(state, text, len) <= room) {
        return len;
    }
    if (one_byte) {
        mark[0] = 0x85;
        nm = 1;
    } else {
        nm = ut_encode(0x2026, mark);
    }
    while (s < end) {
        ut_unit_t u;
        int keep;
        ut_unit(s, end, &u);
        if (u.len <= 0 || at + u.len + nm >= cap) {
            break;
        }
        if (u.kind == UT_RUN) {
            /* a shaped run is tried cluster by cluster */
            const unsigned char *p = s, *q = s + u.len;
            int stop = 0;
            while (p < q) {
                unsigned int lastcp;
                int k = ut_grapheme(p, q, &lastcp);
                if (k <= 0) {
                    break;
                }
                keep = (int)(p - text) + k;
                while (keep > 0 && text[keep - 1] == ' ') --keep;
                CopyMemory(out, text, (size_t)keep);
                CopyMemory(out + keep, mark, (size_t)nm);
                if (width(state, out, keep + nm) > room) {
                    stop = 1;
                    break;
                }
                best = keep;
                p += k;
            }
            if (stop) {
                break;
            }
        } else {
            keep = at + u.len;
            while (keep > 0 && text[keep - 1] == ' ') --keep;
            CopyMemory(out, text, (size_t)keep);
            CopyMemory(out + keep, mark, (size_t)nm);
            if (width(state, out, keep + nm) > room) {
                break;
            }
            best = keep;
        }
        s += u.len;
        at += u.len;
    }
    CopyMemory(out, text, (size_t)best);
    CopyMemory(out + best, mark, (size_t)nm);
    out[best + nm] = 0;
    return best + nm;
}

#endif /* VVFP_TEXT_LAYOUT_H */
