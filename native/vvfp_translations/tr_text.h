/* tr_text.h -- the translation file format, version 1 (docs/translation-file-format.md), as the runtime reads
   it: encodings, the SHA-256 of a key, printf conversions, gender and plural selects, the CLDR plural rules,
   and the row checks that matter at run time.  This is the C twin of src/vv_translation_format.py: every
   function here says which Python function it mirrors, and tests/test_translations_runtime.py compares the
   two on the same rows.

   Text is handled as arrays of Unicode code points (tr_cp), so lengths, positions and the regular
   expressions of the Python module count the same characters.  Nothing here allocates or calls Windows. */
#ifndef TR_TEXT_H
#define TR_TEXT_H

typedef unsigned int tr_cp;

/* "{{" and "}}" while a text is parsed (Python: "\x01" and "\x02"); outside Unicode, so never a real
   character. */
#define TR_LBRACE_MARK 0x110001u
#define TR_RBRACE_MARK 0x110002u

#define TR_MAX_SELECTS 64        /* selects in one text: more is refused (the row stays English) */
#define TR_MAX_BRANCHES 32       /* branches in one select: more is refused */
#define TR_MAX_CONVS 64          /* printf conversions in one text: more is refused */
#define TR_MAX_VARS 64           /* named variables in one text: more is refused */
#define TR_MAX_SUBJECTS 160

/* ---- characters ---------------------------------------------------------------------------------- */

/* Python str.isspace(). */
static int tr_space(tr_cp c) {
    return (c >= 9u && c <= 13u) || (c >= 0x1Cu && c <= 0x20u) || c == 0x85u || c == 0xA0u || c == 0x1680u
        || (c >= 0x2000u && c <= 0x200Au) || c == 0x2028u || c == 0x2029u || c == 0x202Fu || c == 0x205Fu
        || c == 0x3000u;
}

/* Where Python str.splitlines() ends a line. */
static int tr_line_break(tr_cp c) {
    return c == 0x0Au || c == 0x0Du || c == 0x0Bu || c == 0x0Cu || c == 0x1Cu || c == 0x1Du || c == 0x1Eu
        || c == 0x85u || c == 0x2028u || c == 0x2029u;
}

static int tr_digit(tr_cp c) {
    return c >= '0' && c <= '9';
}

static int tr_alpha(tr_cp c) {
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
}

static int tr_ident_start(tr_cp c) {
    return tr_alpha(c) || c == '_';
}

static int tr_ident(tr_cp c) {
    return tr_alpha(c) || tr_digit(c) || c == '_';
}

/* Python's \w beyond ASCII, as far as a select head can tell: a character that is neither a space nor
   punctuation.  (Only a broken select head written with letters outside ASCII depends on it.) */
static int tr_word(tr_cp c) {
    if (c < 0x80u) {
        return tr_ident(c);
    }
    if (tr_space(c) || (c >= 0x80u && c <= 0xBFu && c != 0xAAu && c != 0xB5u && c != 0xBAu && c != 0xB2u
                        && c != 0xB3u && c != 0xB9u && !(c >= 0xBCu && c <= 0xBEu))
        || c == 0xD7u || c == 0xF7u || (c >= 0x2000u && c <= 0x206Fu) || (c >= 0x3000u && c <= 0x303Fu)) {
        return 0;
    }
    return 1;
}

/* Python unicodedata.category(c) == "Cc". */
static int tr_control(tr_cp c) {
    return c < 0x20u || (c >= 0x7Fu && c <= 0x9Fu);
}

/* ---- encodings ----------------------------------------------------------------------------------- */

/* One character of strict UTF-8 (Python's decoder: no overlong forms, no surrogates, nothing past
   U+10FFFF).  1 and the character, or 0 for a byte Python refuses. */
static int tr_utf8_next(const unsigned char *s, unsigned int n, unsigned int *i, tr_cp *out) {
    unsigned int k = *i;
    unsigned char b = s[k];
    tr_cp c;
    int more, j;
    unsigned char lo = 0x80, hi = 0xBF;
    if (b < 0x80u) {
        *out = b;
        *i = k + 1u;
        return 1;
    }
    if (b >= 0xC2u && b <= 0xDFu) {
        more = 1;
        c = b & 0x1Fu;
    } else if (b >= 0xE0u && b <= 0xEFu) {
        more = 2;
        c = b & 0x0Fu;
        if (b == 0xE0u) {
            lo = 0xA0;
        } else if (b == 0xEDu) {
            hi = 0x9F;
        }
    } else if (b >= 0xF0u && b <= 0xF4u) {
        more = 3;
        c = b & 0x07u;
        if (b == 0xF0u) {
            lo = 0x90;
        } else if (b == 0xF4u) {
            hi = 0x8F;
        }
    } else {
        return 0;
    }
    for (j = 1; j <= more; ++j) {
        unsigned char t;
        if (k + (unsigned int)j >= n) {
            return 0;
        }
        t = s[k + (unsigned int)j];
        if (j == 1 ? (t < lo || t > hi) : (t < 0x80u || t > 0xBFu)) {
            return 0;
        }
        c = (c << 6) | (t & 0x3Fu);
    }
    *out = c;
    *i = k + 1u + (unsigned int)more;
    return 1;
}

/* Bytes `c` takes in UTF-8 (the markers are written as the braces they stand for). */
static unsigned int tr_utf8_put(tr_cp c, unsigned char *out) {
    if (c == TR_LBRACE_MARK) {
        c = '{';
    } else if (c == TR_RBRACE_MARK) {
        c = '}';
    }
    if (c < 0x80u) {
        if (out) {
            out[0] = (unsigned char)c;
        }
        return 1;
    }
    if (c < 0x800u) {
        if (out) {
            out[0] = (unsigned char)(0xC0u | (c >> 6));
            out[1] = (unsigned char)(0x80u | (c & 0x3Fu));
        }
        return 2;
    }
    if (c < 0x10000u) {
        if (out) {
            out[0] = (unsigned char)(0xE0u | (c >> 12));
            out[1] = (unsigned char)(0x80u | ((c >> 6) & 0x3Fu));
            out[2] = (unsigned char)(0x80u | (c & 0x3Fu));
        }
        return 3;
    }
    if (out) {
        out[0] = (unsigned char)(0xF0u | (c >> 18));
        out[1] = (unsigned char)(0x80u | ((c >> 12) & 0x3Fu));
        out[2] = (unsigned char)(0x80u | ((c >> 6) & 0x3Fu));
        out[3] = (unsigned char)(0x80u | (c & 0x3Fu));
    }
    return 4;
}

/* Windows-1252 0x80..0x9F; the five bytes it leaves undefined stand for the C1 control of the same value,
   as Windows' own conversion does. */
static const unsigned short TR_CP1252_HIGH[32] = {
    0x20AC, 0x0081, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160, 0x2039, 0x0152,
    0x008D, 0x017D, 0x008F, 0x0090, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122,
    0x0161, 0x203A, 0x0153, 0x009D, 0x017E, 0x0178,
};

static tr_cp tr_cp1252_char(unsigned char b) {
    return (b >= 0x80u && b <= 0x9Fu) ? (tr_cp)TR_CP1252_HIGH[b - 0x80u] : (tr_cp)b;
}

/* The Windows-1252 byte for `c`, or '?' when Windows-1252 cannot spell it. */
static unsigned char tr_cp1252_byte(tr_cp c) {
    int k;
    if (c == TR_LBRACE_MARK) {
        return '{';
    }
    if (c == TR_RBRACE_MARK) {
        return '}';
    }
    if (c < 0x80u || (c >= 0xA0u && c <= 0xFFu)) {
        return (unsigned char)c;
    }
    for (k = 0; k < 32; ++k) {
        if (TR_CP1252_HIGH[k] == c) {
            return (unsigned char)(0x80 + k);
        }
    }
    return '?';
}

/* ---- SHA-256 (FIPS 180-4) ------------------------------------------------------------------------- */

typedef struct {
    unsigned int h[8];
    unsigned char block[64];
    unsigned int used;
    unsigned int bits_lo, bits_hi;
} tr_sha256;

static const unsigned int TR_SHA_K[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
    0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u, 0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
    0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u, 0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
    0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u, 0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u, 0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u,
};

#define TR_ROR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static void tr_sha_block(tr_sha256 *s, const unsigned char *p) {
    unsigned int w[64], a, b, c, d, e, f, g, h, t1, t2;
    int i;
    for (i = 0; i < 16; ++i) {
        w[i] = ((unsigned int)p[4 * i] << 24) | ((unsigned int)p[4 * i + 1] << 16)
            | ((unsigned int)p[4 * i + 2] << 8) | (unsigned int)p[4 * i + 3];
    }
    for (i = 16; i < 64; ++i) {
        unsigned int s0 = TR_ROR(w[i - 15], 7) ^ TR_ROR(w[i - 15], 18) ^ (w[i - 15] >> 3);
        unsigned int s1 = TR_ROR(w[i - 2], 17) ^ TR_ROR(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    a = s->h[0]; b = s->h[1]; c = s->h[2]; d = s->h[3];
    e = s->h[4]; f = s->h[5]; g = s->h[6]; h = s->h[7];
    for (i = 0; i < 64; ++i) {
        t1 = h + (TR_ROR(e, 6) ^ TR_ROR(e, 11) ^ TR_ROR(e, 25)) + ((e & f) ^ (~e & g)) + TR_SHA_K[i] + w[i];
        t2 = (TR_ROR(a, 2) ^ TR_ROR(a, 13) ^ TR_ROR(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
        h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    s->h[0] += a; s->h[1] += b; s->h[2] += c; s->h[3] += d;
    s->h[4] += e; s->h[5] += f; s->h[6] += g; s->h[7] += h;
}

static void tr_sha_init(tr_sha256 *s) {
    static const unsigned int H0[8] = {
        0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au, 0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u,
    };
    int i;
    for (i = 0; i < 8; ++i) {
        s->h[i] = H0[i];
    }
    s->used = 0;
    s->bits_lo = s->bits_hi = 0;
}

static void tr_sha_byte(tr_sha256 *s, unsigned char b) {
    s->block[s->used++] = b;
    s->bits_lo += 8u;
    if (s->bits_lo < 8u) {
        ++s->bits_hi;
    }
    if (s->used == 64u) {
        tr_sha_block(s, s->block);
        s->used = 0;
    }
}

/* The first four bytes of the digest (the key's eight hex digits). */
static unsigned int tr_sha_first32(tr_sha256 *s) {
    unsigned int lo = s->bits_lo, hi = s->bits_hi;
    int i;
    s->block[s->used++] = 0x80;
    if (s->used > 56u) {
        while (s->used < 64u) {
            s->block[s->used++] = 0;
        }
        tr_sha_block(s, s->block);
        s->used = 0;
    }
    while (s->used < 56u) {
        s->block[s->used++] = 0;
    }
    for (i = 0; i < 4; ++i) {
        s->block[56 + i] = (unsigned char)(hi >> (24 - 8 * i));
        s->block[60 + i] = (unsigned char)(lo >> (24 - 8 * i));
    }
    tr_sha_block(s, s->block);
    return s->h[0];
}

/* The key hash of code points (UTF-8, Python english_hash). */
static unsigned int tr_hash_cps(const tr_cp *t, int n) {
    tr_sha256 s;
    unsigned char buf[4];
    int i;
    unsigned int k, m;
    tr_sha_init(&s);
    for (i = 0; i < n; ++i) {
        m = tr_utf8_put(t[i], buf);
        for (k = 0; k < m; ++k) {
            tr_sha_byte(&s, buf[k]);
        }
    }
    return tr_sha_first32(&s);
}

/* The key hash of a game's Windows-1252 text, as its UTF-8. */
static unsigned int tr_hash_cp1252(const unsigned char *text) {
    tr_sha256 s;
    unsigned char buf[4];
    unsigned int k, m;
    tr_sha_init(&s);
    for (; *text; ++text) {
        m = tr_utf8_put(tr_cp1252_char(*text), buf);
        for (k = 0; k < m; ++k) {
            tr_sha_byte(&s, buf[k]);
        }
    }
    return tr_sha_first32(&s);
}

/* ---- small text helpers ---------------------------------------------------------------------------- */

typedef struct {
    const tr_cp *p;
    int n;
} tr_span;

static tr_span tr_strip(tr_span s) {
    while (s.n > 0 && tr_space(s.p[0])) {
        ++s.p;
        --s.n;
    }
    while (s.n > 0 && tr_space(s.p[s.n - 1])) {
        --s.n;
    }
    return s;
}

static int tr_span_eq(tr_span a, tr_span b) {
    int i;
    if (a.n != b.n) {
        return 0;
    }
    for (i = 0; i < a.n; ++i) {
        if (a.p[i] != b.p[i]) {
            return 0;
        }
    }
    return 1;
}

static int tr_span_is(tr_span a, const char *ascii) {
    int i;
    for (i = 0; ascii[i]; ++i) {
        if (i >= a.n || a.p[i] != (tr_cp)(unsigned char)ascii[i]) {
            return 0;
        }
    }
    return i == a.n;
}

static int tr_starts(const tr_cp *t, int n, int at, const char *ascii) {
    int i;
    for (i = 0; ascii[i]; ++i) {
        if (at + i >= n || t[at + i] != (tr_cp)(unsigned char)ascii[i]) {
            return 0;
        }
    }
    return 1;
}

/* ---- printf conversions (Python _PRINTF_RE) ------------------------------------------------------- */

typedef struct {
    int start, end;          /* [start, end) in the text */
    int percent;             /* "%%" */
    tr_cp spec;              /* d i o u x X e E f g G c s p */
    int stars;               /* '*' width / precision: an int argument each, before the value */
    int wide;                /* the value takes 8 bytes (ll / I64 integers, every floating conversion) */
    int lenid;               /* the length modifier (hh h ll l L I64 I32 I), -1 for none */
} tr_conv;

static int tr_conv_char(tr_cp c) {
    const char *set = "diouxXeEfgGcsp";
    int i;
    for (i = 0; set[i]; ++i) {
        if (c == (tr_cp)set[i]) {
            return 1;
        }
    }
    return 0;
}

/* The conversion that starts at `at` (a '%'), or 0. */
static int tr_printf_at(const tr_cp *t, int n, int at, tr_conv *c) {
    static const char *const LENGTHS[] = { "hh", "h", "ll", "l", "L", "I64", "I32", "I" };
    int j = at + 1, k, stars = 0, len = -1;
    c->start = at;
    c->percent = 0;
    if (j < n && t[j] == '%') {
        c->end = j + 1;
        c->percent = 1;
        c->spec = '%';
        c->stars = 0;
        c->wide = 0;
        c->lenid = -1;
        return 1;
    }
    while (j < n && (t[j] == '-' || t[j] == '+' || t[j] == ' ' || t[j] == '#' || t[j] == '0')) {
        ++j;
    }
    if (j < n && t[j] == '*') {
        ++stars;
        ++j;
    } else {
        while (j < n && tr_digit(t[j])) {
            ++j;
        }
    }
    if (j < n && t[j] == '.') {
        if (j + 1 < n && t[j + 1] == '*') {
            ++stars;
            j += 2;
        } else if (j + 1 < n && tr_digit(t[j + 1])) {
            j += 2;
            while (j < n && tr_digit(t[j])) {
                ++j;
            }
        } else {
            return 0;
        }
    }
    for (k = 0; k < 8; ++k) {
        int m = 0;
        while (LENGTHS[k][m] && j + m < n && t[j + m] == (tr_cp)LENGTHS[k][m]) {
            ++m;
        }
        if (LENGTHS[k][m] == '\0' && j + m < n && tr_conv_char(t[j + m])) {
            len = k;
            j += m;
            break;
        }
    }
    if (j >= n || !tr_conv_char(t[j])) {
        return 0;
    }
    c->spec = t[j];
    c->end = j + 1;
    c->stars = stars;
    c->lenid = len;
    c->wide = (c->spec == 'e' || c->spec == 'E' || c->spec == 'f' || c->spec == 'g' || c->spec == 'G')
        || ((len == 2 || len == 5) && c->spec != 's' && c->spec != 'p' && c->spec != 'c');
    return 1;
}

/* printf_conversions(): the conversions in order, "%%" left out.  -1 when there are more than `cap`. */
static int tr_conversions(const tr_cp *t, int n, tr_conv *out, int cap) {
    int i = 0, count = 0;
    tr_conv c;
    while (i < n) {
        if (t[i] == '%' && tr_printf_at(t, n, i, &c)) {
            if (!c.percent) {
                if (count >= cap) {
                    return -1;
                }
                out[count++] = c;
            }
            i = c.end;
        } else {
            ++i;
        }
    }
    return count;
}

/* Python _mask_subjects(): a copy of `t` in `out` with the '%' of every "{%N:" select head made '#'. */
static void tr_mask_subjects(const tr_cp *t, int n, tr_cp *out) {
    int i = 0;
    for (i = 0; i < n; ++i) {
        out[i] = t[i];
    }
    i = 0;
    while (i < n) {
        int matched = 0;
        if (t[i] == '{') {
            int j = i + 1, k, tries;
            while (j < n && tr_space(t[j])) {
                ++j;
            }
            if (j + 1 < n && t[j] == '%' && t[j + 1] >= '1' && t[j + 1] <= '9') {
                for (tries = 0; tries < 2 && !matched; ++tries) {
                    k = j + 2;
                    if (tries == 0) {
                        if (!(k < n && tr_digit(t[k]))) {
                            continue;
                        }
                        ++k;
                    }
                    while (k < n && tr_space(t[k])) {
                        ++k;
                    }
                    if (k < n && t[k] == ':') {
                        out[j] = '#';
                        i = k + 1;
                        matched = 1;
                    }
                }
            }
        }
        if (!matched) {
            ++i;
        }
    }
}

/* ---- the "%" rule (Python Source / english_source / translation_tokens / runtime_text) ---------------
   Only the tokens of a line's own English are placeholders: its printf conversions (those without the space
   flag: a "95% of" is a "% o" only to printf) and "%%".  Any other '%' is plain text, so French "50 %" is fine.
   When the line has a placeholder (the program passes it through printf), every plain '%' is written "%%". */

/* Does the conversion at c carry the space flag? */
static int tr_space_flag(const tr_cp *t, const tr_conv *c) {
    int j = c->start + 1;
    while (j < c->end && (t[j] == '-' || t[j] == '+' || t[j] == ' ' || t[j] == '#' || t[j] == '0')) {
        if (t[j] == ' ') {
            return 1;
        }
        ++j;
    }
    return 0;
}

/* Python _small_field(): a changed width or precision is at most 64 (the game prints into fixed-size buffers: a
   "%100000d" or "%.99999s" could overflow one).  A '*' takes its number at run time. */
/* Set by tr_check_row for a row the companion fills itself (tr_fill_pattern: vvfp.* pattern rows, which only know a
   literal %s %d %i %u): its translation keeps the English's own conversions exactly. */
static int g_exact_conversions;

static int tr_small_field(const tr_cp *t, const tr_conv *c) {
    int j = c->start + 1, k;
    while (j < c->end && (t[j] == '-' || t[j] == '+' || t[j] == ' ' || t[j] == '#' || t[j] == '0')) {
        ++j;
    }
    for (k = 0; k < 2; ++k) {
        int value = 0;
        if (k == 1) {
            if (j >= c->end || t[j] != '.') {
                break;
            }
            ++j;
        }
        while (j < c->end && tr_digit(t[j])) {
            value = value * 10 + (int)(t[j] - '0');
            if (value > 64) {
                return 0;
            }
            ++j;
        }
        if (j < c->end && t[j] == '*') {
            ++j;
        }
    }
    return 1;
}

/* Python _signature(): the kind of value (i is d), its size and the arguments it takes. */
static int tr_same_value(const tr_conv *a, const tr_conv *b) {
    tr_cp sa = a->spec == 'i' ? 'd' : a->spec, sb = b->spec == 'i' ? 'd' : b->spec;
    return sa == sb && a->stars == b->stars && a->lenid == b->lenid;
}

/* A line's English: its conversions without the space flag, in order.  *format: the line has a placeholder
   (a conversion, or "%%").  -1 when there are more than `cap`. */
static int tr_source_convs(const tr_cp *en, int n, tr_conv *out, int cap, int *format) {
    int i = 0, count = 0;
    tr_conv c;
    *format = 0;
    while (i < n) {
        if (en[i] == '%' && tr_printf_at(en, n, i, &c)) {
            if (c.percent) {
                *format = 1;
            } else if (!tr_space_flag(en, &c)) {
                if (count >= cap) {
                    return -1;
                }
                out[count++] = c;
                *format = 1;
            }
            i = c.end;
        } else {
            ++i;
        }
    }
    return count;
}

/* Source.token_at(): 2 for "%%", 1 for a placeholder of the English (c is it), 0 for a plain '%'.  `masked` is
   the text with its "{%N:" heads made '#'. */
static int tr_token_at(const tr_cp *masked, int n, int i, const tr_cp *en, const tr_conv *src, int nsrc,
                       tr_conv *c) {
    int k;
    if (!tr_printf_at(masked, n, i, c)) {
        return 0;
    }
    if (c->percent) {
        return 2;
    }
    for (k = 0; k < nsrc; ++k) {
        int len = src[k].end - src[k].start, m;
        if (len == c->end - c->start) {
            for (m = 0; m < len && en[src[k].start + m] == masked[c->start + m]; ++m) {
            }
            if (m == len) {
                return 1;
            }
        }
    }
    if (!g_exact_conversions && !tr_space_flag(masked, c) && tr_small_field(masked, c)) {
        for (k = 0; k < nsrc; ++k) {
            if (tr_same_value(&src[k], c)) {
                return 1;
            }
        }
    }
    return 0;
}

/* translation_tokens(): the placeholders of a translation, in order, "%%" left out.  -1 when more than cap. */
static int tr_translation_tokens(const tr_cp *t, int n, tr_cp *masked, const tr_cp *en, const tr_conv *src,
                                 int nsrc, tr_conv *out, int cap) {
    int i = 0, count = 0;
    tr_conv c;
    tr_mask_subjects(t, n, masked);
    while (i < n) {
        int token;
        if (masked[i] != '%') {
            ++i;
            continue;
        }
        token = tr_token_at(masked, n, i, en, src, nsrc, &c);
        if (token == 0) {
            ++i;
            continue;
        }
        if (token == 1) {
            if (count >= cap) {
                return -1;
            }
            out[count++] = c;
        }
        i = c.end;
    }
    return count;
}

/* runtime_text(): `out` (room for 2n) gets the translation with each plain '%' written "%%"; its length.
   A line with no placeholder in its English is handed on as it is. */
static int tr_escape_percent(const tr_cp *t, int n, tr_cp *masked, const tr_cp *en, const tr_conv *src,
                             int nsrc, int format, tr_cp *out) {
    int i = 0, o = 0;
    tr_conv c;
    tr_mask_subjects(t, n, masked);
    while (i < n) {
        int token;
        if (masked[i] != '%' || !format) {
            out[o++] = t[i++];
            continue;
        }
        token = tr_token_at(masked, n, i, en, src, nsrc, &c);
        if (token == 0) {
            out[o++] = '%';
            out[o++] = '%';
            ++i;
        } else {
            while (i < c.end) {
                out[o++] = t[i++];
            }
        }
    }
    return o;
}

/* A conversion with no space flag in a select branch (a placeholder belongs outside the select). */
static int tr_branch_conversion(const tr_cp *t, int n) {
    int i = 0;
    tr_conv c;
    while (i < n) {
        if (t[i] == '%' && tr_printf_at(t, n, i, &c)) {
            if (!c.percent && !tr_space_flag(t, &c)) {
                return 1;
            }
            i = c.end;
        } else {
            ++i;
        }
    }
    return 0;
}

/* ---- emails (Python EMAIL_RE) --------------------------------------------------------------------- */

static int tr_email_local(tr_cp c) {
    return tr_alpha(c) || tr_digit(c) || c == '.' || c == '_' || c == '%' || c == '+' || c == '-';
}

static int tr_email_domain(tr_cp c) {
    return tr_alpha(c) || tr_digit(c) || c == '-';
}

static int tr_has_email(const tr_cp *t, int n) {
    int at;
    for (at = 0; at < n; ++at) {
        int k, j, groups = 0;
        if (t[at] != '@') {
            continue;
        }
        k = at - 1;
        while (k >= 0 && tr_space(t[k])) {
            --k;
        }
        if (k < 0 || !tr_email_local(t[k])) {
            continue;
        }
        j = at + 1;
        while (j < n && tr_space(t[j])) {
            ++j;
        }
        if (j >= n || !tr_email_domain(t[j])) {
            continue;
        }
        while (j < n && tr_email_domain(t[j])) {
            ++j;
        }
        for (;;) {
            int m = j;
            while (m < n && tr_space(t[m])) {
                ++m;
            }
            if (m >= n || t[m] != '.') {
                break;
            }
            ++m;
            while (m < n && tr_space(t[m])) {
                ++m;
            }
            if (m >= n || !tr_email_domain(t[m])) {
                break;
            }
            while (m < n && tr_email_domain(t[m])) {
                ++m;
            }
            j = m;
            ++groups;
        }
        if (groups > 0) {
            return 1;
        }
    }
    return 0;
}

/* ---- selects (Python parse_selects / _parse_one / choose) ------------------------------------------ */

enum { TR_SUBJ_PCT = 1, TR_SUBJ_NAME, TR_SUBJ_STAR };
enum { TR_KIND_NONE = 0, TR_KIND_PERSON, TR_KIND_NUMBER };
enum { TR_KEY_M = 0, TR_KEY_F, TR_KEY_O, TR_KEY_ZERO, TR_KEY_ONE, TR_KEY_TWO, TR_KEY_FEW, TR_KEY_MANY,
       TR_KEY_OTHER, TR_KEY_EXACT };

static const char *const TR_KEY_NAMES[9] = { "m", "f", "o", "zero", "one", "two", "few", "many", "other" };

typedef struct {
    int key;                 /* TR_KEY_* */
    long exact;              /* =N: N, or -1 when it can never match (a leading zero, or too large) */
    int dstart, dlen;        /* =N: N's digits as written, in the value buffer */
    int start, len;          /* the value, in the select's own value buffer (tr_select.values) */
} tr_branch;

typedef struct {
    int subject;             /* TR_SUBJ_* */
    int pct;                 /* %N: N */
    tr_span name;            /* a named subject */
    int kind;                /* TR_KIND_PERSON when every key is m, f or o, else TR_KIND_NUMBER */
    int start, end;          /* in the brace-stripped text */
    int count;
    tr_branch br[TR_MAX_BRANCHES];
    int order[TR_MAX_BRANCHES];
} tr_select;

/* _SELECT_HEAD_RE at `at`: the head's end (after ':'), or 0.  The subject is returned. */
static int tr_select_head(const tr_cp *t, int n, int at, int *subject, int *pct, tr_span *name) {
    int j = at + 1, k, tries;
    if (at >= n || t[at] != '{') {
        return 0;
    }
    while (j < n && tr_space(t[j])) {
        ++j;
    }
    if (j < n && t[j] == '%') {
        if (j + 1 < n && t[j + 1] >= '1' && t[j + 1] <= '9') {
            for (tries = 0; tries < 2; ++tries) {
                int value = (int)(t[j + 1] - '0');
                k = j + 2;
                if (tries == 0) {
                    if (!(k < n && tr_digit(t[k]))) {
                        continue;
                    }
                    value = value * 10 + (int)(t[k] - '0');
                    ++k;
                }
                while (k < n && tr_space(t[k])) {
                    ++k;
                }
                if (k < n && t[k] == ':') {
                    *subject = TR_SUBJ_PCT;
                    *pct = value;
                    return k + 1;
                }
            }
        }
        return 0;
    }
    if (j < n && tr_ident_start(t[j])) {
        k = j + 1;
        while (k < n && tr_ident(t[k])) {
            ++k;
        }
        name->p = t + j;
        name->n = k - j;
        while (k < n && tr_space(t[k])) {
            ++k;
        }
        if (k < n && t[k] == ':') {
            *subject = TR_SUBJ_NAME;
            return k + 1;
        }
        return 0;
    }
    if (j < n && t[j] == '*') {
        k = j + 1;
        while (k < n && tr_space(t[k])) {
            ++k;
        }
        if (k < n && t[k] == ':') {
            *subject = TR_SUBJ_STAR;
            return k + 1;
        }
    }
    return 0;
}

/* The looser head of parse_selects' unbalanced test: \{\s*(%[1-9][0-9]?|[A-Za-z_]\w*|\*)\s*: anywhere. */
static int tr_loose_head(const tr_cp *t, int n, int at) {
    int j = at + 1, k;
    int subject, pct;
    tr_span name;
    if (tr_select_head(t, n, at, &subject, &pct, &name)) {
        return 1;
    }
    while (j < n && tr_space(t[j])) {
        ++j;
    }
    if (j < n && tr_ident_start(t[j])) {
        k = j + 1;
        while (k < n && tr_word(t[k])) {
            ++k;
        }
        while (k < n && tr_space(t[k])) {
            ++k;
        }
        return k < n && t[k] == ':';
    }
    return 0;
}

/* _strip_escaped_braces(): "{{" then "}}" replaced by the markers; the new length. */
static int tr_strip_braces(const tr_cp *t, int n, tr_cp *out) {
    int i = 0, m = 0, k;
    while (i < n) {
        if (t[i] == '{' && i + 1 < n && t[i + 1] == '{') {
            out[m++] = TR_LBRACE_MARK;
            i += 2;
        } else {
            out[m++] = t[i++];
        }
    }
    i = 0;
    k = 0;
    while (i < m) {
        if (out[i] == '}' && i + 1 < m && out[i + 1] == '}') {
            out[k++] = TR_RBRACE_MARK;
            i += 2;
        } else {
            out[k++] = out[i++];
        }
    }
    return k;
}

typedef struct {
    int start, end, select;
} tr_piece;

/* _split_selects_loose(): pieces of a brace-stripped text; -1 when there are more than `cap`. */
static int tr_split_loose(const tr_cp *t, int n, tr_piece *out, int cap) {
    int i = 0, start = 0, count = 0;
    int subject, pct;
    tr_span name;
    while (i < n) {
        if (t[i] == '{' && tr_select_head(t, n, i, &subject, &pct, &name)) {
            int depth = 0, j = i;
            while (j < n) {
                if (t[j] == '\\' && j + 1 < n) {
                    j += 2;
                    continue;
                }
                if (t[j] == '{') {
                    ++depth;
                } else if (t[j] == '}') {
                    --depth;
                    if (depth == 0) {
                        break;
                    }
                }
                ++j;
            }
            if (j >= n) {
                break;
            }
            if (count + 2 > cap) {
                return -1;
            }
            if (start < i) {
                out[count].start = start;
                out[count].end = i;
                out[count].select = 0;
                ++count;
            }
            out[count].start = i;
            out[count].end = j + 1;
            out[count].select = 1;
            ++count;
            i = j + 1;
            start = i;
            continue;
        }
        ++i;
    }
    if (start < n) {
        if (count + 1 > cap) {
            return -1;
        }
        out[count].start = start;
        out[count].end = n;
        out[count].select = 0;
        ++count;
    }
    return count;
}

/* _parse_one(): one select piece of a brace-stripped text.  The branch values (with "\|" made '|') go to
   `values` (room for the piece's length).  1, or 0 for a malformed select. */
static int tr_parse_one(const tr_cp *t, int start, int end, tr_select *sel, tr_cp *values,
                        tr_cp *scratch) {
    int head, body, body_end, i, part_start, vlen = 0, has_person = 0, has_number = 0;
    head = tr_select_head(t, end, start, &sel->subject, &sel->pct, &sel->name);
    if (!head) {
        return 0;
    }
    sel->start = start;
    sel->end = end;
    sel->count = 0;
    body = head;
    body_end = end - 1;
    /* No select inside a select, anywhere in the body (stricter than the Python module, which looks only
       at the body's first character). */
    for (i = body; i < body_end; ++i) {
        if (t[i] == '{' && tr_loose_head(t, body_end, i)) {
            return 0;
        }
    }
    i = body;
    part_start = 0;
    for (;;) {
        int at_end = i >= body_end;
        if (!at_end && t[i] == '\\' && i + 1 < body_end && t[i + 1] == '|') {
            values[vlen++] = '|';
            i += 2;
            continue;
        }
        if (at_end || t[i] == '|') {
            /* one part: values[part_start, vlen) */
            tr_span part, stripped, key, value;
            int k, eq = -1, keyid = -1;
            long exact = -1;
            int dstart = 0, dlen = 0;
            part.p = values + part_start;
            part.n = vlen - part_start;
            if (tr_strip(part).n == 0) {
                return 0;                                  /* an empty branch */
            }
            stripped = part;
            while (stripped.n > 0 && tr_space(stripped.p[0])) {
                ++stripped.p;
                --stripped.n;
            }
            if (stripped.p[0] == '=') {
                int d = 1, digits = 0;
                long number = 0;
                int overflow = 0, lead_zero = 0;
                while (d < stripped.n && tr_digit(stripped.p[d])) {
                    if (digits == 0 && stripped.p[d] == '0') {
                        lead_zero = 1;
                    }
                    if (number > 99999999L) {
                        overflow = 1;
                    } else {
                        number = number * 10 + (long)(stripped.p[d] - '0');
                    }
                    ++digits;
                    ++d;
                }
                if (digits == 0) {
                    return 0;
                }
                while (d < stripped.n && tr_space(stripped.p[d])) {
                    ++d;
                }
                if (d >= stripped.n || stripped.p[d] != '=') {
                    return 0;                              /* "=N" with no '=' after it */
                }
                keyid = TR_KEY_EXACT;
                exact = (overflow || (lead_zero && digits > 1)) ? -1 : number;
                dstart = (int)(stripped.p + 1 - values);
                dlen = digits;
                value.p = stripped.p + d + 1;
                value.n = stripped.n - d - 1;
            } else {
                for (k = 0; k < stripped.n; ++k) {
                    if (stripped.p[k] == '=') {
                        eq = k;
                        break;
                    }
                }
                if (eq < 0) {
                    return 0;                              /* no '=' */
                }
                key.p = stripped.p;
                key.n = eq;
                key = tr_strip(key);
                for (k = 0; k < 9; ++k) {
                    if (tr_span_is(key, TR_KEY_NAMES[k])) {
                        keyid = k;
                        break;
                    }
                }
                if (keyid < 0) {
                    /* "=N" written as the key itself ("=3 = x" is caught above); a key like "=3" after
                       strip cannot occur here because the part would have started with '='. */
                    return 0;
                }
                value.p = stripped.p + eq + 1;
                value.n = stripped.n - eq - 1;
            }
            for (k = 0; k < sel->count; ++k) {
                if (sel->br[k].key == keyid) {
                    tr_span a, b;
                    if (keyid != TR_KEY_EXACT) {
                        return 0;                          /* the same key twice */
                    }
                    a.p = values + sel->br[k].dstart;
                    a.n = sel->br[k].dlen;
                    b.p = values + dstart;
                    b.n = dlen;
                    if (tr_span_eq(a, b)) {
                        return 0;
                    }
                }
            }
            value = tr_strip(value);
            if (tr_branch_conversion(value.p, value.n)) {
                return 0;                                  /* a conversion inside a branch */
            }
            if (sel->count >= TR_MAX_BRANCHES) {
                return 0;
            }
            sel->br[sel->count].key = keyid;
            sel->br[sel->count].exact = exact;
            sel->br[sel->count].dstart = dstart;
            sel->br[sel->count].dlen = dlen;
            sel->br[sel->count].start = (int)(value.p - values);
            sel->br[sel->count].len = value.n;
            sel->order[sel->count] = sel->count;
            ++sel->count;
            if (keyid <= TR_KEY_O) {
                has_person = 1;
            } else {
                has_number = 1;
            }
            if (at_end) {
                break;
            }
            ++i;
            part_start = vlen;
            continue;
        }
        values[vlen++] = t[i];
        ++i;
    }
    if (has_person && has_number) {
        return 0;
    }
    sel->kind = has_number ? TR_KIND_NUMBER : TR_KIND_PERSON;
    return 1;
}

/* ---- CLDR plural categories (Python PLURAL_RULES / PLURAL_RULE_OF) ------------------------------------ */

enum { TR_R_ONE_OTHER = 0, TR_R_FRENCH, TR_R_EAST_SLAVIC, TR_R_POLISH, TR_R_CZECH, TR_R_SOUTH_SLAVIC,
       TR_R_SLOVENIAN, TR_R_ROMANIAN, TR_R_LITHUANIAN, TR_R_LATVIAN, TR_R_ARABIC, TR_R_HEBREW, TR_R_IRISH,
       TR_R_WELSH, TR_R_ICELANDIC, TR_R_PORTUGUESE, TR_R_OTHER, TR_R_SPANISH_ITALIAN, TR_R_MACEDONIAN,
       TR_R_MALTESE };

typedef struct {
    const char *code;
    int rule;
} tr_rule_of;

static const tr_rule_of TR_RULE_OF[] = {
    { "en", TR_R_ONE_OTHER }, { "de", TR_R_ONE_OTHER }, { "nl", TR_R_ONE_OTHER }, { "sv", TR_R_ONE_OTHER },
    { "da", TR_R_ONE_OTHER }, { "nb", TR_R_ONE_OTHER }, { "nn", TR_R_ONE_OTHER }, { "no", TR_R_ONE_OTHER },
    { "fi", TR_R_ONE_OTHER }, { "et", TR_R_ONE_OTHER }, { "el", TR_R_ONE_OTHER }, { "hu", TR_R_ONE_OTHER },
    { "tr", TR_R_ONE_OTHER }, { "bg", TR_R_ONE_OTHER }, { "af", TR_R_ONE_OTHER }, { "eu", TR_R_ONE_OTHER },
    { "gl", TR_R_ONE_OTHER }, { "ka", TR_R_ONE_OTHER }, { "kk", TR_R_ONE_OTHER }, { "az", TR_R_ONE_OTHER },
    { "sq", TR_R_ONE_OTHER }, { "hy", TR_R_FRENCH }, { "ur", TR_R_ONE_OTHER }, { "sw", TR_R_ONE_OTHER },
    { "ta", TR_R_ONE_OTHER }, { "te", TR_R_ONE_OTHER }, { "ml", TR_R_ONE_OTHER }, { "mn", TR_R_ONE_OTHER },
    { "ne", TR_R_ONE_OTHER }, { "uz", TR_R_ONE_OTHER },
    { "ca", TR_R_SPANISH_ITALIAN }, { "es", TR_R_SPANISH_ITALIAN }, { "it", TR_R_SPANISH_ITALIAN },
    { "fr", TR_R_FRENCH }, { "pt", TR_R_PORTUGUESE }, { "pt-PT", TR_R_SPANISH_ITALIAN },
    { "pt-BR", TR_R_PORTUGUESE },
    { "ru", TR_R_EAST_SLAVIC }, { "uk", TR_R_EAST_SLAVIC }, { "be", TR_R_EAST_SLAVIC },
    { "pl", TR_R_POLISH }, { "cs", TR_R_CZECH }, { "sk", TR_R_CZECH },
    { "hr", TR_R_SOUTH_SLAVIC }, { "sr", TR_R_SOUTH_SLAVIC }, { "bs", TR_R_SOUTH_SLAVIC },
    { "sl", TR_R_SLOVENIAN }, { "mk", TR_R_MACEDONIAN },
    { "ro", TR_R_ROMANIAN }, { "mo", TR_R_ROMANIAN }, { "lt", TR_R_LITHUANIAN }, { "lv", TR_R_LATVIAN },
    { "ar", TR_R_ARABIC }, { "he", TR_R_HEBREW }, { "iw", TR_R_HEBREW }, { "ga", TR_R_IRISH },
    { "cy", TR_R_WELSH }, { "is", TR_R_ICELANDIC }, { "mt", TR_R_MALTESE },
    { "ja", TR_R_OTHER }, { "zh", TR_R_OTHER }, { "zh-Hans", TR_R_OTHER }, { "zh-Hant", TR_R_OTHER },
    { "ko", TR_R_OTHER }, { "th", TR_R_OTHER }, { "vi", TR_R_OTHER }, { "id", TR_R_OTHER },
    { "ms", TR_R_OTHER }, { "lo", TR_R_OTHER }, { "my", TR_R_OTHER }, { "km", TR_R_OTHER },
    { "yo", TR_R_OTHER }, { "jv", TR_R_OTHER },
    { "hi", TR_R_FRENCH }, { "bn", TR_R_FRENCH }, { "fa", TR_R_FRENCH }, { "gu", TR_R_FRENCH },
    { "kn", TR_R_FRENCH }, { "am", TR_R_FRENCH }, { "zu", TR_R_FRENCH },
};

/* plural_rule_name(): `code` is the @code value, stripped. */
static int tr_plural_rule(tr_span code) {
    tr_cp lowered[16];
    tr_span base;
    unsigned int k;
    int i;
    if (code.n == 0) {
        return TR_R_ONE_OTHER;
    }
    for (k = 0; k < sizeof TR_RULE_OF / sizeof TR_RULE_OF[0]; ++k) {
        if (tr_span_is(code, TR_RULE_OF[k].code)) {
            return TR_RULE_OF[k].rule;
        }
    }
    for (i = 0; i < code.n && code.p[i] != '-' && i < 16; ++i) {
        tr_cp c = code.p[i];
        lowered[i] = (c >= 'A' && c <= 'Z') ? c + 32u : c;
    }
    if (i < code.n && code.p[i] != '-') {
        return TR_R_ONE_OTHER;
    }
    base.p = lowered;
    base.n = i;
    for (k = 0; k < sizeof TR_RULE_OF / sizeof TR_RULE_OF[0]; ++k) {
        if (tr_span_is(base, TR_RULE_OF[k].code)) {
            return TR_RULE_OF[k].rule;
        }
    }
    return TR_R_ONE_OTHER;
}

/* The category (TR_KEY_ZERO..TR_KEY_OTHER) of |n| under `rule`. */
static int tr_plural(int rule, unsigned long long n) {
    unsigned int m10 = (unsigned int)(n % 10u), m100 = (unsigned int)(n % 100u);
    unsigned int m1e6 = (unsigned int)(n % 1000000u);
    switch (rule) {
    case TR_R_ONE_OTHER:
        return n == 1u ? TR_KEY_ONE : TR_KEY_OTHER;
    case TR_R_FRENCH:
    case TR_R_PORTUGUESE:
        return n <= 1u ? TR_KEY_ONE : ((n != 0u && m1e6 == 0u) ? TR_KEY_MANY : TR_KEY_OTHER);
    case TR_R_EAST_SLAVIC:
        if (m10 == 1u && m100 != 11u) {
            return TR_KEY_ONE;
        }
        if (m10 >= 2u && m10 <= 4u && !(m100 >= 12u && m100 <= 14u)) {
            return TR_KEY_FEW;
        }
        return TR_KEY_MANY;
    case TR_R_POLISH:
        if (n == 1u) {
            return TR_KEY_ONE;
        }
        if (m10 >= 2u && m10 <= 4u && !(m100 >= 12u && m100 <= 14u)) {
            return TR_KEY_FEW;
        }
        return TR_KEY_MANY;
    case TR_R_CZECH:
        if (n == 1u) {
            return TR_KEY_ONE;
        }
        return (n >= 2u && n <= 4u) ? TR_KEY_FEW : TR_KEY_OTHER;
    case TR_R_SOUTH_SLAVIC:
        if (m10 == 1u && m100 != 11u) {
            return TR_KEY_ONE;
        }
        if (m10 >= 2u && m10 <= 4u && !(m100 >= 12u && m100 <= 14u)) {
            return TR_KEY_FEW;
        }
        return TR_KEY_OTHER;
    case TR_R_SLOVENIAN:
        if (m100 == 1u) {
            return TR_KEY_ONE;
        }
        if (m100 == 2u) {
            return TR_KEY_TWO;
        }
        return (m100 == 3u || m100 == 4u) ? TR_KEY_FEW : TR_KEY_OTHER;
    case TR_R_ROMANIAN:
        if (n == 1u) {
            return TR_KEY_ONE;
        }
        return (n == 0u || (m100 >= 2u && m100 <= 19u)) ? TR_KEY_FEW : TR_KEY_OTHER;
    case TR_R_LITHUANIAN:
        if (m10 == 1u && !(m100 >= 11u && m100 <= 19u)) {
            return TR_KEY_ONE;
        }
        return (m10 >= 2u && m10 <= 9u && !(m100 >= 11u && m100 <= 19u)) ? TR_KEY_FEW : TR_KEY_OTHER;
    case TR_R_LATVIAN:
        if (m10 == 0u || (m100 >= 11u && m100 <= 19u)) {
            return TR_KEY_ZERO;
        }
        return (m10 == 1u && m100 != 11u) ? TR_KEY_ONE : TR_KEY_OTHER;
    case TR_R_ARABIC:
        if (n == 0u) {
            return TR_KEY_ZERO;
        }
        if (n == 1u) {
            return TR_KEY_ONE;
        }
        if (n == 2u) {
            return TR_KEY_TWO;
        }
        if (m100 >= 3u && m100 <= 10u) {
            return TR_KEY_FEW;
        }
        return (m100 >= 11u && m100 <= 99u) ? TR_KEY_MANY : TR_KEY_OTHER;
    case TR_R_HEBREW:
        return n == 1u ? TR_KEY_ONE : (n == 2u ? TR_KEY_TWO : TR_KEY_OTHER);
    case TR_R_IRISH:
        if (n == 1u) {
            return TR_KEY_ONE;
        }
        if (n == 2u) {
            return TR_KEY_TWO;
        }
        if (n >= 3u && n <= 6u) {
            return TR_KEY_FEW;
        }
        return (n >= 7u && n <= 10u) ? TR_KEY_MANY : TR_KEY_OTHER;
    case TR_R_WELSH:
        return n == 0u ? TR_KEY_ZERO : n == 1u ? TR_KEY_ONE : n == 2u ? TR_KEY_TWO : n == 3u ? TR_KEY_FEW
            : n == 6u ? TR_KEY_MANY : TR_KEY_OTHER;
    case TR_R_ICELANDIC:
    case TR_R_MACEDONIAN:
        return (m10 == 1u && m100 != 11u) ? TR_KEY_ONE : TR_KEY_OTHER;
    case TR_R_SPANISH_ITALIAN:
        return n == 1u ? TR_KEY_ONE : ((n != 0u && m1e6 == 0u) ? TR_KEY_MANY : TR_KEY_OTHER);
    case TR_R_MALTESE:
        if (n == 1u) {
            return TR_KEY_ONE;
        }
        if (n == 2u) {
            return TR_KEY_TWO;
        }
        if (n == 0u || (m100 >= 3u && m100 <= 10u)) {
            return TR_KEY_FEW;
        }
        return (m100 >= 11u && m100 <= 19u) ? TR_KEY_MANY : TR_KEY_OTHER;
    default:
        return TR_KEY_OTHER;
    }
}

#endif /* TR_TEXT_H */
