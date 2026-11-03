/* text_layout.h -- laying text out by the shared spec's rules (docs/UNICODE_SPEC.md row 3).  Header-only,
   file-static, no CRT; included after text_utf8.h.

   LINE BREAKS (tl_breaks).  A text with a letter of a script written without spaces -- ICU's line-break classes
   ID, SA, H2, H3, JL, JT, JV, CJ, EB and EM, and the CJK punctuation blocks -- or a zero width space may break
   between two whole grapheme clusters next to such a letter (or after the zero width space), where
   ubrk_open(UBRK_LINE) of icu.dll says a line may break.  ICU comes with Windows 10 1903 and later and is loaded
   from System32 only (LOAD_LIBRARY_SEARCH_SYSTEM32); it also knows the Thai, Lao, Khmer and Myanmar words and the
   kinsoku rules (no line starts with 。、」 or a small kana, none ends with 「).  Without it the built-in table
   below decides: next to an ideographic letter, never before a closing mark, never after an opening one.  A
   break after a run of spaces is marked too (every line breaker allows it).

   COMPOSITION (tl_compose).  A cluster of a base letter and combining marks is drawn as its precomposed letter
   when Windows' NormalizeString(NormalizationC) makes one (e + U+0301 is drawn as the font's own é).

   FITTING (tl_fit_ellipsis).  The longest start of whole units of a text whose width with "…" after it is at most
   a room, trailing spaces dropped, then "…" (U+2026; byte 0x85 in a text of one byte per character). */
#ifndef VVFP_TEXT_LAYOUT_H
#define VVFP_TEXT_LAYOUT_H

#include "text_utf8.h"

/* ---- ICU, loaded once, from System32 only ---------------------------------------------------- */

typedef void *(__cdecl *tl_ubrk_open_fn)(int type, const char *locale, const WCHAR *text, int length, int *status);
typedef int (__cdecl *tl_ubrk_step_fn)(void *it);
typedef void (__cdecl *tl_ubrk_close_fn)(void *it);
typedef int (__cdecl *tl_uprop_fn)(unsigned int cp, int which);

#define TL_UBRK_LINE 2
#define TL_UCHAR_LINE_BREAK 0x1008
#define TL_SEARCH_SYSTEM32 0x00000800u

static tl_ubrk_open_fn g_tl_open;
static tl_ubrk_step_fn g_tl_first, g_tl_next;
static tl_ubrk_close_fn g_tl_close;
static tl_uprop_fn g_tl_prop;
static int g_tl_icu_looked;
static int g_tl_icu_off;            /* the layout harness only: decide by the built-in table */

static int tl_icu(void) {
    if (g_tl_icu_off) {
        return 0;
    }
    if (!g_tl_icu_looked) {
        HMODULE m;
        g_tl_icu_looked = 1;
        m = LoadLibraryExW(L"icu.dll", NULL, TL_SEARCH_SYSTEM32);
        if (m != NULL) {
            g_tl_open = (tl_ubrk_open_fn)GetProcAddress(m, "ubrk_open");
            g_tl_first = (tl_ubrk_step_fn)GetProcAddress(m, "ubrk_first");
            g_tl_next = (tl_ubrk_step_fn)GetProcAddress(m, "ubrk_next");
            g_tl_close = (tl_ubrk_close_fn)GetProcAddress(m, "ubrk_close");
            g_tl_prop = (tl_uprop_fn)GetProcAddress(m, "u_getIntPropertyValue");
            if (g_tl_open == NULL || g_tl_first == NULL || g_tl_next == NULL || g_tl_close == NULL || g_tl_prop == NULL) {
                g_tl_open = NULL;
            }
        }
    }
    return g_tl_open != NULL;
}

/* ---- The built-in table (VF1 linebreak.inc; VV's own kinsoku list is part of it) ------------- */

enum { TL_OTHER = 0, TL_IDEOGRAPHIC = 1, TL_CLOSING = 2, TL_OPENING = 3 };

typedef struct tl_range { unsigned int first, last; unsigned char cls; } tl_range;

static const tl_range TL_FALLBACK[] = {   /* sorted, not overlapping */
    {0x0021, 0x0021, TL_CLOSING}, {0x0028, 0x0028, TL_OPENING}, {0x0029, 0x0029, TL_CLOSING},
    {0x002C, 0x002C, TL_CLOSING}, {0x002E, 0x002E, TL_CLOSING}, {0x003A, 0x003B, TL_CLOSING},
    {0x003F, 0x003F, TL_CLOSING}, {0x005B, 0x005B, TL_OPENING}, {0x005D, 0x005D, TL_CLOSING},
    {0x007B, 0x007B, TL_OPENING}, {0x007D, 0x007D, TL_CLOSING},
    {0x0E00, 0x0EFF, TL_IDEOGRAPHIC}, {0x1000, 0x109F, TL_IDEOGRAPHIC}, {0x1100, 0x115F, TL_IDEOGRAPHIC},
    {0x1780, 0x17FF, TL_IDEOGRAPHIC}, {0x1950, 0x19DF, TL_IDEOGRAPHIC}, {0x1A20, 0x1AAF, TL_IDEOGRAPHIC},
    {0x2018, 0x2018, TL_OPENING}, {0x2019, 0x2019, TL_CLOSING}, {0x201C, 0x201C, TL_OPENING},
    {0x201D, 0x201D, TL_CLOSING}, {0x2E80, 0x2FFF, TL_IDEOGRAPHIC},
    {0x3000, 0x3000, TL_IDEOGRAPHIC}, {0x3001, 0x3002, TL_CLOSING}, {0x3003, 0x3004, TL_IDEOGRAPHIC},
    {0x3005, 0x3005, TL_CLOSING}, {0x3006, 0x3007, TL_IDEOGRAPHIC}, {0x3008, 0x3008, TL_OPENING},
    {0x3009, 0x3009, TL_CLOSING}, {0x300A, 0x300A, TL_OPENING}, {0x300B, 0x300B, TL_CLOSING},
    {0x300C, 0x300C, TL_OPENING}, {0x300D, 0x300D, TL_CLOSING}, {0x300E, 0x300E, TL_OPENING},
    {0x300F, 0x300F, TL_CLOSING}, {0x3010, 0x3010, TL_OPENING}, {0x3011, 0x3011, TL_CLOSING},
    {0x3012, 0x3013, TL_IDEOGRAPHIC}, {0x3014, 0x3014, TL_OPENING}, {0x3015, 0x3015, TL_CLOSING},
    {0x3016, 0x3016, TL_OPENING}, {0x3017, 0x3017, TL_CLOSING}, {0x3018, 0x3018, TL_OPENING},
    {0x3019, 0x3019, TL_CLOSING}, {0x301A, 0x301A, TL_OPENING}, {0x301B, 0x301B, TL_CLOSING},
    {0x301C, 0x301C, TL_CLOSING}, {0x301D, 0x301D, TL_OPENING}, {0x301E, 0x301F, TL_CLOSING},
    {0x3020, 0x303A, TL_IDEOGRAPHIC}, {0x303B, 0x303C, TL_CLOSING}, {0x303D, 0x3040, TL_IDEOGRAPHIC},
    {0x3041, 0x3041, TL_CLOSING}, {0x3042, 0x3042, TL_IDEOGRAPHIC}, {0x3043, 0x3043, TL_CLOSING},
    {0x3044, 0x3044, TL_IDEOGRAPHIC}, {0x3045, 0x3045, TL_CLOSING}, {0x3046, 0x3046, TL_IDEOGRAPHIC},
    {0x3047, 0x3047, TL_CLOSING}, {0x3048, 0x3048, TL_IDEOGRAPHIC}, {0x3049, 0x3049, TL_CLOSING},
    {0x304A, 0x3062, TL_IDEOGRAPHIC}, {0x3063, 0x3063, TL_CLOSING}, {0x3064, 0x3082, TL_IDEOGRAPHIC},
    {0x3083, 0x3083, TL_CLOSING}, {0x3084, 0x3084, TL_IDEOGRAPHIC}, {0x3085, 0x3085, TL_CLOSING},
    {0x3086, 0x3086, TL_IDEOGRAPHIC}, {0x3087, 0x3087, TL_CLOSING}, {0x3088, 0x308D, TL_IDEOGRAPHIC},
    {0x308E, 0x308E, TL_CLOSING}, {0x308F, 0x3094, TL_IDEOGRAPHIC}, {0x3095, 0x3096, TL_CLOSING},
    {0x3097, 0x309A, TL_IDEOGRAPHIC}, {0x309B, 0x309E, TL_CLOSING}, {0x309F, 0x30A0, TL_IDEOGRAPHIC},
    {0x30A1, 0x30A1, TL_CLOSING}, {0x30A2, 0x30A2, TL_IDEOGRAPHIC}, {0x30A3, 0x30A3, TL_CLOSING},
    {0x30A4, 0x30A4, TL_IDEOGRAPHIC}, {0x30A5, 0x30A5, TL_CLOSING}, {0x30A6, 0x30A6, TL_IDEOGRAPHIC},
    {0x30A7, 0x30A7, TL_CLOSING}, {0x30A8, 0x30A8, TL_IDEOGRAPHIC}, {0x30A9, 0x30A9, TL_CLOSING},
    {0x30AA, 0x30C2, TL_IDEOGRAPHIC}, {0x30C3, 0x30C3, TL_CLOSING}, {0x30C4, 0x30E2, TL_IDEOGRAPHIC},
    {0x30E3, 0x30E3, TL_CLOSING}, {0x30E4, 0x30E4, TL_IDEOGRAPHIC}, {0x30E5, 0x30E5, TL_CLOSING},
    {0x30E6, 0x30E6, TL_IDEOGRAPHIC}, {0x30E7, 0x30E7, TL_CLOSING}, {0x30E8, 0x30ED, TL_IDEOGRAPHIC},
    {0x30EE, 0x30EE, TL_CLOSING}, {0x30EF, 0x30F4, TL_IDEOGRAPHIC}, {0x30F5, 0x30F6, TL_CLOSING},
    {0x30F7, 0x30FA, TL_IDEOGRAPHIC}, {0x30FB, 0x30FE, TL_CLOSING}, {0x30FF, 0x31FF, TL_IDEOGRAPHIC},
    {0x3200, 0x4DBF, TL_IDEOGRAPHIC}, {0x4E00, 0x9FFF, TL_IDEOGRAPHIC}, {0xA000, 0xA4CF, TL_IDEOGRAPHIC},
    {0xA960, 0xA97F, TL_IDEOGRAPHIC}, {0xAA60, 0xAADF, TL_IDEOGRAPHIC}, {0xAC00, 0xD7FF, TL_IDEOGRAPHIC},
    {0xF900, 0xFAFF, TL_IDEOGRAPHIC}, {0xFE30, 0xFE4F, TL_IDEOGRAPHIC},
    {0xFF01, 0xFF01, TL_CLOSING}, {0xFF02, 0xFF07, TL_IDEOGRAPHIC}, {0xFF08, 0xFF08, TL_OPENING},
    {0xFF09, 0xFF09, TL_CLOSING}, {0xFF0A, 0xFF0B, TL_IDEOGRAPHIC}, {0xFF0C, 0xFF0C, TL_CLOSING},
    {0xFF0D, 0xFF0D, TL_IDEOGRAPHIC}, {0xFF0E, 0xFF0E, TL_CLOSING}, {0xFF0F, 0xFF19, TL_IDEOGRAPHIC},
    {0xFF1A, 0xFF1B, TL_CLOSING}, {0xFF1C, 0xFF1E, TL_IDEOGRAPHIC}, {0xFF1F, 0xFF1F, TL_CLOSING},
    {0xFF20, 0xFF3A, TL_IDEOGRAPHIC}, {0xFF3B, 0xFF3B, TL_OPENING}, {0xFF3C, 0xFF3C, TL_IDEOGRAPHIC},
    {0xFF3D, 0xFF3D, TL_CLOSING}, {0xFF3E, 0xFF5A, TL_IDEOGRAPHIC}, {0xFF5B, 0xFF5B, TL_OPENING},
    {0xFF5C, 0xFF5C, TL_IDEOGRAPHIC}, {0xFF5D, 0xFF5D, TL_CLOSING}, {0xFF5E, 0xFF60, TL_IDEOGRAPHIC},
    {0xFF61, 0xFF61, TL_CLOSING}, {0xFF62, 0xFF62, TL_OPENING}, {0xFF63, 0xFF64, TL_CLOSING},
    {0xFF65, 0xFFEF, TL_IDEOGRAPHIC},
    {0x16FE0, 0x18AFF, TL_IDEOGRAPHIC}, {0x1B000, 0x1B2FF, TL_IDEOGRAPHIC}, {0x1F000, 0x1FAFF, TL_IDEOGRAPHIC},
    {0x20000, 0x3FFFD, TL_IDEOGRAPHIC},
};

static int tl_fallback_class(unsigned int cp) {
    int lo = 0, hi = (int)(sizeof TL_FALLBACK / sizeof TL_FALLBACK[0]) - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (cp < TL_FALLBACK[mid].first) hi = mid - 1;
        else if (cp > TL_FALLBACK[mid].last) lo = mid + 1;
        else return TL_FALLBACK[mid].cls;
    }
    return TL_OTHER;
}

/* Without ICU: next to an ideographic letter unless the next one closes or the one before opens; after a closing
   mark before an opening one. */
static int tl_fallback_may_break(unsigned int before, unsigned int after) {
    int a = tl_fallback_class(before), b = tl_fallback_class(after);
    if (b == TL_CLOSING || a == TL_OPENING) {
        return 0;
    }
    return a == TL_IDEOGRAPHIC || b == TL_IDEOGRAPHIC || (a == TL_CLOSING && b == TL_OPENING);
}

/* A letter of a script written without spaces: the CJK punctuation blocks, and ICU's line-break classes ID (14),
   SA (24), H2, H3, JL, JT, JV (31-35), CJ (37), EB (40) and EM (41); the built-in ideographic class without ICU. */
static int tl_no_space_letter(unsigned int cp) {
    if ((cp >= 0x3000 && cp <= 0x303F) || (cp >= 0xFE30 && cp <= 0xFE4F) || (cp >= 0xFF00 && cp <= 0xFFEF)) {
        return 1;
    }
    if (tl_icu()) {
        int c = g_tl_prop(cp, TL_UCHAR_LINE_BREAK);
        return c == 14 || c == 24 || (c >= 31 && c <= 35) || c == 37 || c == 40 || c == 41;
    }
    return tl_fallback_class(cp) == TL_IDEOGRAPHIC;
}

/* 1 when text[0..n) holds a letter of a script written without spaces or a zero width space (it then breaks by
   tl_breaks; any other text breaks at its spaces only). */
static int tl_needs_breaks(const unsigned char *text, int n) {
    const unsigned char *s = text, *end = text + n;
    while (s < end && *s) {
        unsigned int cp;
        s += ut_next(s, end, &cp);
        if (cp >= 0x80 && (cp == 0x200B || tl_no_space_letter(cp))) {
            return 1;
        }
    }
    return 0;
}

static void *tl_alloc(size_t n) {
    return HeapAlloc(GetProcessHeap(), 0, n);
}

static void tl_free(void *p) {
    if (p != NULL) {
        HeapFree(GetProcessHeap(), 0, p);
    }
}

/* Where text[0..n) may break: out[b] = 1 for 0 < b < n when a line may start at byte b (out holds n + 1 bytes).
   Only between whole grapheme clusters; next to a letter of a script written without spaces (or after a zero
   width space), where UAX #14 allows it; and after a run of spaces.  Returns 0 when the text has no such letter
   (then only the spaces are marked). */
static int tl_breaks(const unsigned char *text, int n, unsigned char *out) {
    const unsigned char *end = text + n;
    int count = 0, i, b, any, units = 0, use_icu = 0;
    int *at = NULL, *unit_cp = NULL;
    unsigned int *cps = NULL;
    unsigned char *icu = NULL;
    WCHAR *u16 = NULL;
    for (b = 0; b <= n; ++b) {
        out[b] = 0;
    }
    for (b = 1; b < n; ++b) {
        if (text[b - 1] == ' ' && text[b] != ' ') {
            out[b] = 1;
        }
    }
    any = tl_needs_breaks(text, n);
    if (!any || n <= 0) {
        return any;
    }
    at = (int *)tl_alloc(sizeof(int) * (size_t)(n + 1));
    cps = (unsigned int *)tl_alloc(sizeof(unsigned int) * (size_t)(n + 1));
    icu = (unsigned char *)tl_alloc((size_t)n + 1);
    u16 = (WCHAR *)tl_alloc(sizeof(WCHAR) * (size_t)(2 * n + 1));
    unit_cp = (int *)tl_alloc(sizeof(int) * (size_t)(2 * n + 1));
    if (at == NULL || cps == NULL || icu == NULL || u16 == NULL || unit_cp == NULL) {
        tl_free(at); tl_free(cps); tl_free(icu); tl_free(u16); tl_free(unit_cp);
        return any;
    }
    /* code points, their byte offsets, the text in UTF-16 and each unit's code point */
    {
        const unsigned char *s = text;
        while (s < end && *s) {
            unsigned int cp;
            at[count] = (int)(s - text);
            s += ut_next(s, end, &cp);
            cps[count] = cp;
            icu[count] = 0;
            unit_cp[units] = count;
            if (cp >= 0x10000) {
                u16[units++] = (WCHAR)(0xD800 + ((cp - 0x10000) >> 10));
                unit_cp[units] = count;
                u16[units++] = (WCHAR)(0xDC00 + ((cp - 0x10000) & 0x3FF));
            } else {
                u16[units++] = (WCHAR)cp;
            }
            ++count;
        }
        at[count] = (int)(s - text);
        icu[count] = 0;
        unit_cp[units] = count;
    }
    if (tl_icu()) {
        int status = 0;
        void *it = g_tl_open(TL_UBRK_LINE, "", u16, units, &status);
        if (it != NULL && status <= 0) {
            use_icu = 1;
            for (b = g_tl_first(it); b >= 0 && b <= units; b = g_tl_next(it)) {
                if (b == 0 || b == units || unit_cp[b - 1] != unit_cp[b]) {
                    icu[unit_cp[b]] = 1;            /* never inside a surrogate pair */
                }
            }
        }
        if (it != NULL) {
            g_tl_close(it);
        }
    }
    /* between whole clusters only */
    {
        int prev = -1;
        i = 0;
        while (i < count) {
            unsigned int lastcp;
            int k = ut_grapheme(text + at[i], end, &lastcp), j = i;
            if (k <= 0) {
                break;
            }
            while (j < count && at[j] < at[i] + k) {
                ++j;
            }
            if (prev >= 0) {
                unsigned int before = cps[prev], after = cps[i], last = cps[i - 1];
                int ok = before != ' ' && before != '\n' && after != ' ' && after != '\n'
                    && (tl_no_space_letter(before) || tl_no_space_letter(after) || last == 0x200B);
                if (ok) {
                    ok = use_icu ? icu[i] != 0 : (last == 0x200B || tl_fallback_may_break(before, after));
                }
                if (ok) {
                    out[at[i]] = 1;
                }
            }
            prev = i;
            i = j;
        }
    }
    tl_free(at); tl_free(cps); tl_free(icu); tl_free(u16); tl_free(unit_cp);
    return any;
}

/* ---- Composition ----------------------------------------------------------------------------- */

/* The cluster u[0..len) in composed form (NFC) when that changes it: its bytes in out (cap bytes), as the
   characters ut_append would write after nothing; 0 when it is one character already or does not change. */
static int tl_compose(const unsigned char *u, int len, unsigned char *out, int cap) {
    WCHAR in[64], norm[64];
    const unsigned char *s = u, *end = u + len;
    int n = 0, m, i, o = 0, chars = 0;
    while (s < end) {
        unsigned int cp;
        s += ut_next(s, end, &cp);
        if (n + 2 >= 64) {
            return 0;
        }
        if (cp >= 0x10000) {
            in[n++] = (WCHAR)(0xD800 + ((cp - 0x10000) >> 10));
            in[n++] = (WCHAR)(0xDC00 + ((cp - 0x10000) & 0x3FF));
        } else {
            in[n++] = (WCHAR)cp;
        }
        ++chars;
    }
    if (chars < 2) {
        return 0;
    }
    m = NormalizeString(NormalizationC, in, n, norm, 64);
    if (m <= 0 || m > 64 || (m == n && memcmp(in, norm, sizeof(WCHAR) * (size_t)n) == 0)) {
        return 0;
    }
    for (i = 0; i < m; ++i) {
        unsigned int cp = norm[i];
        unsigned char bytes[4];
        int k;
        if (cp >= 0xD800 && cp < 0xDC00 && i + 1 < m && norm[i + 1] >= 0xDC00 && norm[i + 1] < 0xE000) {
            cp = 0x10000u + ((cp - 0xD800u) << 10) + (norm[i + 1] - 0xDC00u);
            ++i;
        }
        k = ut_append(out, o, cp, bytes);
        if (o + k >= cap) {
            return 0;
        }
        CopyMemory(out + o, bytes, (size_t)k);
        o += k;
    }
    out[o] = 0;
    return o;
}

/* ---- Fitting with "…" ------------------------------------------------------------------------- */

typedef int (*tl_width_fn)(void *state, const unsigned char *s, int len);

/* text[0..len) fitted to `room` pixels (measured by width): the text itself when it fits (returns len and out
   untouched), else its longest start of whole units (a shaped run: of whole clusters) whose width with "…" is at
   most room (at least nothing), trailing spaces dropped, then "…" -- written to out (cap bytes, with its NUL);
   returns the bytes written.  The starts are measured by halving, so a long text is measured only a few times. */
static int tl_fit_ellipsis(const unsigned char *text, int len, int room, tl_width_fn width, void *state,
                           unsigned char *out, int cap) {
    unsigned char mark[4];
    int nm, best = 0, at = 0, n = 0, lo, hi, *ends;
    const unsigned char *s = text, *end = text + len;
    if (width(state, text, len) <= room) {
        return len;
    }
    if (!ut_has_utf8(text, end)) {
        mark[0] = 0x85;
        nm = 1;
    } else {
        nm = ut_encode(0x2026, mark);
    }
    ends = (int *)tl_alloc(sizeof(int) * (size_t)(len + 1));
    if (ends != NULL) {
        /* every start that ends between whole units (inside a shaped run, between whole clusters) */
        while (s < end) {
            ut_unit_t u;
            ut_unit(s, end, &u);
            if (u.len <= 0 || at + u.len + nm >= cap) {
                if (u.len > 0 && u.kind == UT_RUN) {
                    const unsigned char *p = s, *q = s + u.len;
                    while (p < q) {
                        unsigned int lastcp;
                        int k = ut_grapheme(p, q, &lastcp);
                        if (k <= 0 || (int)(p - text) + k + nm >= cap) break;
                        p += k;
                        ends[n++] = (int)(p - text);
                    }
                }
                break;
            }
            if (u.kind == UT_RUN) {
                const unsigned char *p = s, *q = s + u.len;
                while (p < q) {
                    unsigned int lastcp;
                    int k = ut_grapheme(p, q, &lastcp);
                    if (k <= 0) break;
                    p += k;
                    ends[n++] = (int)(p - text);
                }
            } else {
                ends[n++] = at + u.len;
            }
            s += u.len;
            at += u.len;
        }
        lo = 0;
        hi = n - 1;
        while (lo <= hi) {
            int mid = (lo + hi) / 2, keep = ends[mid];
            while (keep > 0 && text[keep - 1] == ' ') --keep;
            CopyMemory(out, text, (size_t)keep);
            CopyMemory(out + keep, mark, (size_t)nm);
            if (width(state, out, keep + nm) <= room) {
                best = keep;
                lo = mid + 1;
            } else {
                hi = mid - 1;
            }
        }
        tl_free(ends);
    }
    CopyMemory(out, text, (size_t)best);
    CopyMemory(out + best, mark, (size_t)nm);
    out[best + nm] = 0;
    return best + nm;
}

#endif /* VVFP_TEXT_LAYOUT_H */
