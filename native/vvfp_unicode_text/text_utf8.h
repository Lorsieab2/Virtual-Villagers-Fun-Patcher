/* text_utf8.h -- the games' text rule and the units text is drawn, measured, broken and erased in.

   THE RULE (the same as src/vv_game_text.py).  A name or any other game text is bytes.  Each well-formed
   UTF-8 sequence (Unicode Table 3-7: no overlong form, no surrogate, nothing past U+10FFFF) is its
   character; every other byte is its Windows-1252 character (the five bytes Windows-1252 leaves undefined
   as the Latin-1 character of the same number).  So every name the base game, an older patcher or PR #670
   wrote reads exactly as before, and a UTF-8 name reads as typed.

   WRITING (ut_append).  A character Windows-1252 has is written as its one byte -- as short as it can be,
   and what an unpatched game or older patcher reads as the same letter -- unless that byte would join the
   bytes before it into a different UTF-8 character (a Windows-1252 "\xC3" followed by "\xA9" would read
   as one "e acute"), when it is written as UTF-8.  Every other character is written as UTF-8.

   UNITS (ut_unit).  Text is cut, measured and drawn in whole units, never inside one:
     - a newline, a space;
     - an extended grapheme cluster by UAX #29 as of Unicode 18.0 (ut_grapheme; ucd18_tables.h, generated
       from the 18.0 UCD): a character with every combining mark, variation selector, emoji modifier, tag
       and zero-width-joined emoji after it, a Hangul syllable of jamo, an Indic conjunct, a flag;
     - a run of a script that needs shaping (Arabic, Hebrew, Syriac, Thaana, N'Ko, the Indic scripts,
       Thai, Lao, Tibetan, Myanmar, Khmer, Mongolian), its marks, joiners and the spaces between its
       words: Windows shapes and orders the whole run (src: runtime_glyphs.inc).  A run is cut and erased
       between its grapheme clusters.
   Header-only, file-static, no CRT. */
#ifndef VVFP_TEXT_UTF8_H
#define VVFP_TEXT_UTF8_H

#include "unicode_text_tables.h"
#include "ucd18_tables.h"

/* The length of the well-formed UTF-8 sequence at s (s < end), 0 when there is none. */
static int ut_seq(const unsigned char *s, const unsigned char *end, unsigned int *cp) {
    unsigned int b = s[0], lo = 0x80, hi = 0xBF;
    int n, i;
    if (b < 0x80) {
        *cp = b;
        return 1;
    }
    if (b >= 0xC2 && b <= 0xDF) {
        n = 2;
        *cp = b & 0x1F;
    } else if (b >= 0xE0 && b <= 0xEF) {
        n = 3;
        *cp = b & 0x0F;
        if (b == 0xE0) lo = 0xA0;
        if (b == 0xED) hi = 0x9F;
    } else if (b >= 0xF0 && b <= 0xF4) {
        n = 4;
        *cp = b & 0x07;
        if (b == 0xF0) lo = 0x90;
        if (b == 0xF4) hi = 0x8F;
    } else {
        return 0;
    }
    if (end - s < n) {
        return 0;
    }
    if (s[1] < lo || s[1] > hi) {
        return 0;
    }
    *cp = (*cp << 6) | (s[1] & 0x3Fu);
    for (i = 2; i < n; ++i) {
        if ((s[i] & 0xC0) != 0x80) {
            return 0;
        }
        *cp = (*cp << 6) | (s[i] & 0x3Fu);
    }
    return n;
}

/* The character at s by the games' rule; returns its byte length (1..4). */
static int ut_next(const unsigned char *s, const unsigned char *end, unsigned int *cp) {
    int n = ut_seq(s, end, cp);
    if (n > 0) {
        return n;
    }
    *cp = VG_CP1252[s[0]] ? VG_CP1252[s[0]] : s[0];
    return 1;
}

static const unsigned char *ut_end(const unsigned char *s) {
    while (*s) {
        ++s;
    }
    return s;
}

/* 1 when the text holds a well-formed multi-byte UTF-8 sequence (it then needs the companion's own
   drawing; any other text is one Windows-1252 byte per character, which the game's fonts draw). */
static int ut_has_utf8(const unsigned char *s, const unsigned char *end) {
    unsigned int cp;
    for (; s < end; ++s) {
        if (*s >= 0xC2 && ut_seq(s, end, &cp) > 1) {
            return 1;
        }
    }
    return 0;
}

/* The Windows-1252 byte of a character, or -1. */
static int ut_cp1252_byte(unsigned int cp) {
    int i;
    if (cp < 0x80) {
        return (int)cp;
    }
    if (cp < 0xA0 && (cp == 0x81 || cp == 0x8D || cp == 0x8F || cp == 0x90 || cp == 0x9D)) {
        return (int)cp;
    }
    if (cp > 0xFFFF) {
        return -1;
    }
    for (i = 0x80; i < 0x100; ++i) {
        if (VG_CP1252[i] == cp) {
            return i;
        }
    }
    return -1;
}

static int ut_encode(unsigned int cp, unsigned char *out) {
    if (cp < 0x80) {
        out[0] = (unsigned char)cp;
        return 1;
    }
    if (cp < 0x800) {
        out[0] = (unsigned char)(0xC0 | (cp >> 6));
        out[1] = (unsigned char)(0x80 | (cp & 0x3F));
        return 2;
    }
    if (cp < 0x10000) {
        out[0] = (unsigned char)(0xE0 | (cp >> 12));
        out[1] = (unsigned char)(0x80 | ((cp >> 6) & 0x3F));
        out[2] = (unsigned char)(0x80 | (cp & 0x3F));
        return 3;
    }
    out[0] = (unsigned char)(0xF0 | (cp >> 18));
    out[1] = (unsigned char)(0x80 | ((cp >> 12) & 0x3F));
    out[2] = (unsigned char)(0x80 | ((cp >> 6) & 0x3F));
    out[3] = (unsigned char)(0x80 | (cp & 0x3F));
    return 4;
}

/* The number of characters text[0..len) reads as, by the rule. */
static int ut_count(const unsigned char *text, int len) {
    const unsigned char *s = text, *end = text + len;
    unsigned int cp;
    int n = 0;
    while (s < end) {
        s += ut_next(s, end, &cp);
        ++n;
    }
    return n;
}

/* The character text[0..len) ends with, by the rule. */
static unsigned int ut_last(const unsigned char *text, int len) {
    const unsigned char *s = text, *end = text + len;
    unsigned int cp = 0;
    while (s < end) {
        s += ut_next(s, end, &cp);
    }
    return cp;
}

/* The bytes to append for `cp` after text[0..len): 1..4 written to out.  (WRITING, above.) */
static int ut_append(const unsigned char *text, int len, unsigned int cp, unsigned char *out) {
    int b = ut_cp1252_byte(cp);
    if (b >= 0 && (b < 0x80 || cp >= 0xA0 || (b != 0x81 && b != 0x8D && b != 0x8F && b != 0x90 && b != 0x9D))) {
        unsigned char probe[4 + 1200];
        int keep = len > 3 ? 3 : len, before;
        /* Only the last three bytes can join the new one into a sequence. */
        CopyMemory(probe, text + len - keep, (size_t)keep);
        probe[keep] = (unsigned char)b;
        before = ut_count(probe, keep);
        if (ut_count(probe, keep + 1) == before + 1 && ut_last(probe, keep + 1) == cp) {
            /* ... and the bytes before keep their reading (a lone lead byte stays itself). */
            unsigned int c;
            const unsigned char *s = probe, *end = probe + keep + 1;
            int n = 0, same = 1;
            const unsigned char *t = probe;
            while (s < end && n < before) {
                unsigned int c2;
                int k1 = ut_next(s, end, &c), k2 = ut_next(t, probe + keep, &c2);
                if (k1 != k2 || c != c2) {
                    same = 0;
                    break;
                }
                s += k1;
                t += k2;
                ++n;
            }
            if (same) {
                out[0] = (unsigned char)b;
                return 1;
            }
        }
    }
    return ut_encode(cp, out);
}

/* ---- Character classes ------------------------------------------------------------------------ */

static unsigned int ut_gcb(unsigned int cp) {
    return u18_lookup(u18_gcb, U18_GCB_COUNT, cp);
}

/* A spacing mark (Mc) UAX #29 leaves out of GB9a (Myanmar U+102B, ...): the shared cluster rule
   (docs/UNICODE_SPEC.md row 2: every Mn, Mc and Me extends the character before it) joins it too. */
static int ut_mark_joins(unsigned int cp) {
    return u18_lookup(u18_markjoin, U18_MARKJOIN_COUNT, cp) != 0;
}

/* Joins the character before it into one cluster (Grapheme_Cluster_Break Extend, ZWJ or SpacingMark, or any
   other spacing mark). */
static int ut_extends(unsigned int cp) {
    unsigned int p = ut_gcb(cp);
    return p == U18_GCB_EXTEND || p == U18_GCB_ZWJ || p == U18_GCB_SPACINGMARK || ut_mark_joins(cp);
}

static int ut_regional(unsigned int cp) {
    return cp >= 0x1F1E6 && cp <= 0x1F1FF;
}

/* A script Windows must shape (joined letters, reordered marks, right to left). */
static int ut_complex(unsigned int cp) {
    return (cp >= 0x0590 && cp <= 0x08FF) || (cp >= 0x0900 && cp <= 0x0DFF) || (cp >= 0x0E00 && cp <= 0x0FFF)
        || (cp >= 0x1000 && cp <= 0x109F) || (cp >= 0x1780 && cp <= 0x18AF) || (cp >= 0x1900 && cp <= 0x1AAF)
        || (cp >= 0xA8E0 && cp <= 0xA8FF) || (cp >= 0xA9E0 && cp <= 0xA9FF) || (cp >= 0xAA60 && cp <= 0xAA7F)
        || (cp >= 0xFB1D && cp <= 0xFDFF) || (cp >= 0xFE70 && cp <= 0xFEFF)
        || (cp >= 0x10800 && cp <= 0x10FFF) || (cp >= 0x1E800 && cp <= 0x1EFFF);
}

/* ---- Units ------------------------------------------------------------------------------------ */

enum { UT_END = 0, UT_NEWLINE, UT_SPACE, UT_CLUSTER, UT_RUN };

typedef struct ut_unit_t {
    int kind;
    int len;                    /* bytes */
    unsigned int first, last;   /* the first and last characters (for line breaking) */
} ut_unit_t;

/* The byte length of the extended grapheme cluster at s (UAX #29 as of Unicode 18.0: GB3-GB13 -- CR LF is one
   cluster -- GB9c's Indic conjuncts, GB11's emoji ZWJ sequences, GB12/13's flags), with every spacing mark
   (Mc) joined as the shared cluster rule says.  The same rule as src/vv_game_text.py clusters(). */
static int ut_grapheme(const unsigned char *s, const unsigned char *end, unsigned int *last) {
    const unsigned char *p = s;
    unsigned int cp, prev, incb;
    int ri, emoji, conj, k;
    if (s >= end || *s == 0) {
        return 0;
    }
    k = ut_next(p, end, &cp);
    p += k;
    *last = cp;
    prev = ut_gcb(cp);
    ri = prev == U18_GCB_REGIONAL_INDICATOR;
    emoji = u18_lookup(u18_extpict, U18_EXTPICT_COUNT, cp) ? 1 : 0;
    incb = u18_lookup(u18_incb, U18_INCB_COUNT, cp);
    conj = incb == U18_INCB_CONSONANT ? 1 : incb == U18_INCB_LINKER ? 2 : 0;
    while (p < end && *p) {
        unsigned int next, q, ib;
        int join, pict;
        k = ut_next(p, end, &next);
        q = ut_gcb(next);
        ib = u18_lookup(u18_incb, U18_INCB_COUNT, next);
        pict = u18_lookup(u18_extpict, U18_EXTPICT_COUNT, next) != 0;
        if (prev == U18_GCB_CR && q == U18_GCB_LF) join = 1;                                        /* GB3 */
        else if (prev == U18_GCB_CONTROL || prev == U18_GCB_CR || prev == U18_GCB_LF
                 || q == U18_GCB_CONTROL || q == U18_GCB_CR || q == U18_GCB_LF) join = 0;           /* GB4, GB5 */
        else if (prev == U18_GCB_L && (q == U18_GCB_L || q == U18_GCB_V || q == U18_GCB_LV || q == U18_GCB_LVT))
            join = 1;                                                                                /* GB6 */
        else if ((prev == U18_GCB_LV || prev == U18_GCB_V) && (q == U18_GCB_V || q == U18_GCB_T)) join = 1;  /* GB7 */
        else if ((prev == U18_GCB_LVT || prev == U18_GCB_T) && q == U18_GCB_T) join = 1;           /* GB8 */
        else if (q == U18_GCB_EXTEND || q == U18_GCB_ZWJ || q == U18_GCB_SPACINGMARK) join = 1;    /* GB9, GB9a */
        else if (ut_mark_joins(next)) join = 1;                     /* every Mc (the shared cluster rule) */
        else if (prev == U18_GCB_ZWJ) join = 1;      /* a ZWJ joins the next character (the shared rule, beyond GB11) */
        else if (prev == U18_GCB_PREPEND) join = 1;                                                  /* GB9b */
        else if (conj == 2 && ib == U18_INCB_CONSONANT) join = 1;                                    /* GB9c */
        else if (emoji == 2 && pict) join = 1;                                                       /* GB11 */
        else if (prev == U18_GCB_REGIONAL_INDICATOR && q == U18_GCB_REGIONAL_INDICATOR && (ri & 1)) join = 1;  /* GB12/13 */
        else join = 0;
        if (!join) {
            break;
        }
        p += k;
        *last = next;
        ri = q == U18_GCB_REGIONAL_INDICATOR ? ri + 1 : 0;
        if (pict) emoji = 1;
        else if (emoji == 1 && q == U18_GCB_EXTEND) emoji = 1;
        else if (emoji == 1 && q == U18_GCB_ZWJ) emoji = 2;
        else emoji = 0;
        if (ib == U18_INCB_CONSONANT) conj = 1;
        else if (ib == U18_INCB_LINKER) conj = 2;
        else if (!(conj && ib == U18_INCB_EXTEND)) conj = 0;
        prev = q;
    }
    return (int)(p - s);
}

/* The unit at s.  A shaped run takes spaces only between two of its own words. */
static void ut_unit(const unsigned char *s, const unsigned char *end, ut_unit_t *u) {
    unsigned int cp, next;
    const unsigned char *p = s;
    int n;
    u->kind = UT_END;
    u->len = 0;
    u->first = u->last = 0;
    if (s >= end || *s == 0) {
        return;
    }
    n = ut_next(p, end, &cp);
    u->first = u->last = cp;
    p += n;
    if (cp == '\n') {
        u->kind = UT_NEWLINE;
        u->len = 1;
        return;
    }
    if (cp == ' ' && !(p < end && *p && (ut_next(p, end, &next), ut_extends(next)))) {
        u->kind = UT_SPACE;         /* (a space with a mark on it is a cluster) */
        u->len = 1;
        return;
    }
    if (ut_complex(cp)) {
        u->kind = UT_RUN;
        while (p < end && *p) {
            int k = ut_next(p, end, &next);
            if (ut_complex(next) || ut_extends(next) || (next >= 0x0660 && next <= 0x0669)) {
                p += k;
                u->last = next;
                continue;
            }
            if (next == ' ') {
                /* Spaces join the run only when the run's script goes on after them. */
                const unsigned char *q = p;
                unsigned int after;
                while (q < end && *q == ' ') {
                    ++q;
                }
                if (q < end && *q && (ut_next(q, end, &after), ut_complex(after))) {
                    p = q;
                    continue;
                }
            }
            break;
        }
        u->len = (int)(p - s);
        return;
    }
    u->kind = UT_CLUSTER;
    u->len = ut_grapheme(s, end, &u->last);
}

/* The length text[0..len) keeps when its last unit is erased (Backspace): the last grapheme cluster
   (a shaped run is erased one grapheme cluster at a time). */
static int ut_erase_last(const unsigned char *text, int len) {
    const unsigned char *s = text, *end = text + len;
    int last = 0, at = 0;
    ut_unit_t u;
    while (s < end) {
        ut_unit(s, end, &u);
        if (u.len <= 0) {
            break;
        }
        last = at;
        if (u.kind == UT_RUN) {
            const unsigned char *p = s, *q = s + u.len;
            while (p < q) {
                unsigned int lastcp;
                int k = ut_grapheme(p, q, &lastcp);
                if (k <= 0) {
                    break;
                }
                last = at + (int)(p - s);
                p += k;
            }
        }
        s += u.len;
        at += u.len;
    }
    return last;
}

/* The longest start of text[0..len) of whole units whose bytes fit `cap` (a shaped run may be cut between
   its grapheme clusters, never inside one). */
static int ut_fit(const unsigned char *text, int len, int cap) {
    const unsigned char *s = text, *end = text + len;
    int at = 0;
    ut_unit_t u;
    while (s < end) {
        ut_unit(s, end, &u);
        if (u.len <= 0 || at + u.len > cap) {
            if (u.kind == UT_RUN && at < cap) {
                const unsigned char *p = s, *q = s + u.len;
                while (p < q) {
                    unsigned int lastcp;
                    int k = ut_grapheme(p, q, &lastcp);
                    if (k <= 0 || at + (int)(p - s) + k > cap) {
                        break;
                    }
                    p += k;
                }
                at += (int)(p - s);
            }
            break;
        }
        s += u.len;
        at += u.len;
    }
    return at;
}

#endif /* VVFP_TEXT_UTF8_H */
