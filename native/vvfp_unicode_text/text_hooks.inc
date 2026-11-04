/* text_hooks.inc -- the game's text routines, made to read UTF-8 (text_utf8.h's rule).

   Each detour has the routine's own calling convention (a thiscall routine is a __fastcall function
   whose second register argument is unused) and starts with the same three steps:
     1. a fault anywhere below falls back to the game's own routine with the game's own text;
     2. the text is offered to "VVFP Translations.dll" (VvfpTranslateText, resolved once, absent = the
        text itself), then each long-name short form in it becomes its whole name (long_names.inc);
     3. text with no multi-byte UTF-8 sequence -- every name and string the games have ever had -- goes
        to the game's own routine unchanged (with "Use Unicode Font", all text comes here).
   Text with UTF-8 is cut into units (text_utf8.h) and drawn as RUNS: a run of the font's own letters
   (each character Windows-1252 has, as its byte) or of one page's letters (runtime_glyphs.inc), each
   drawn and measured by the game's own draw and width routines, so colour, transparency, clipping,
   spacing and widths are exactly the game's.  Text boxes: a typed character is stored whole or not at
   all, Backspace erases a whole unit, a box never cuts its text by pixels (which could cut inside a
   character), its byte limit is VV_SHARED_NAME_BYTES, and text leaving a box longer than the field it
   goes to leaves as a short form (long_names.inc). */

typedef int (__fastcall *vt_width_fn)(void *font, void *edx, const unsigned char *s, float scale);
typedef int (__fastcall *vt_draw_fn)(void *ctx, void *edx, const unsigned char *s, int x, int y,
                                     unsigned int colour, void *font);
typedef const unsigned char *(__fastcall *vt_linefit_fn)(void *font, void *edx, const unsigned char *src,
                                                         unsigned char *out, int max_count, int max_width,
                                                         unsigned char *paragraph, int nl_as_space, float scale);
typedef int (__fastcall *vt_nbyte_fn)(void *ctx, void *edx, const unsigned char *s, int max_bytes, int x, int y,
                                      int measure_only, unsigned int colour, void *font);
typedef int (__fastcall *vt_justify_fn)(void *holder, void *edx, const unsigned char *text, int x, int y,
                                        int width, unsigned int colour, void *font, int measure_only);
typedef void (__fastcall *vt_ctldraw_fn)(unsigned char *ctl, void *edx);
typedef int (__fastcall *vt_seteditable_fn)(unsigned char *box, void *edx, int editable, int limit);
typedef int (__fastcall *vt_settext_fn)(unsigned char *box, void *edx, const unsigned char *s);
typedef int (__fastcall *vt_gettext_fn)(unsigned char *wrapper, void *edx, unsigned char *buf, int size);
typedef int (__fastcall *vt_handler_fn)(unsigned char *box, void *edx, int message, int p1, int p2);
typedef int (__fastcall *vt_line_height_fn)(void *font, void *edx, const unsigned char *text);
typedef const char *(__stdcall *vt_translate_fn)(const char *);

#define VT_MARK 0x56000000u          /* a typed text the box takes from the ring: MARK | slot << 8 */
#define VT_RING 16
#define VT_RUN_MAX 2048

static const vt_game *g_vt;
static vt_width_fn g_width;          /* the game's own routines (their trampolines) */
static vt_draw_fn g_draw;
static vt_linefit_fn g_linefit;
static vt_nbyte_fn g_nbyte;
static vt_justify_fn g_justify;
static vt_ctldraw_fn g_ctldraw;
static vt_seteditable_fn g_seteditable;
static vt_settext_fn g_settext;
static vt_gettext_fn g_gettext;
static vt_handler_fn g_handler;      /* the whole character handler (its detoured entry) */
static void *g_chartype_tramp, *g_backspace_back;
static unsigned char g_ring[VT_RING][40];
static int g_ring_next;
static vt_translate_fn g_translate;
static int g_translate_tries;
static volatile LONG g_own_draws;    /* for the tests: texts drawn or measured by the companion */

/* ---- 2. Translations and long names ----------------------------------------------------------- */

static int vt_own_width(void *font, const unsigned char *s, float scale);
static int vt_needs_own(const unsigned char *s, const unsigned char *end);

typedef struct vt_fit { void *font; float scale; } vt_fit;

/* The width of s[0..len) with the glyphs the game will draw: the companion's own units for UTF-8 (or with Use
   Unicode Font), the game's own width routine for any other text. */
static int vt_fit_width(void *state, const unsigned char *s, int len) {
    vt_fit *f = (vt_fit *)state;
    unsigned char buf[VV_SHARED_NAME_BYTES + 8];
    if (len < 0 || len >= (int)sizeof buf) {
        return 0x7FFFFFFF;
    }
    CopyMemory(buf, s, (size_t)len);
    buf[len] = 0;
    return vt_needs_own(buf, buf + len) ? vt_own_width(f->font, buf, f->scale) : g_width(f->font, NULL, buf, f->scale);
}

/* A whole name fitted to the room the game leaves for its field (docs/UNICODE_SPEC.md row 3, "Fit-to-width"):
   the width of as many "W" as the field holds bytes -- the stock layout's own measure (its name boxes are sized
   by a string of W) -- measured in the font it is drawn in.  -1: it fits as it is. */
static int vt_fit_name(void *state, const unsigned char *whole, int len, int room_bytes, unsigned char *out, int cap) {
    vt_fit *f = (vt_fit *)state;
    unsigned char ws[VV_SHARED_NAME_BYTES + 1];
    int room;
    if (f == NULL || f->font == NULL || room_bytes <= 0 || room_bytes > VV_SHARED_NAME_BYTES) {
        return -1;
    }
    FillMemory(ws, (size_t)room_bytes, 'W');
    ws[room_bytes] = 0;
    room = g_width(f->font, NULL, ws, f->scale);
    if (cap > VV_SHARED_NAME_BYTES + 4) {
        cap = VV_SHARED_NAME_BYTES + 4;
    }
    return tl_fit_ellipsis(whole, len, room, vt_fit_width, f, out, cap);
}

static const unsigned char *vt_source(const unsigned char *s, void *font, float scale) {
    vt_fit fit;
    if (s == NULL) {
        return s;
    }
    if (g_translate == NULL && g_translate_tries < 2000) {
        HMODULE m;
        ++g_translate_tries;
        m = GetModuleHandleW(L"VVFP Translations.dll");
        if (m != NULL) {
            g_translate = (vt_translate_fn)GetProcAddress(m, "VvfpTranslateText");
            if (g_translate == NULL) {
                g_translate_tries = 2000;
            }
        }
    }
    if (g_translate != NULL) {
        const unsigned char *t = (const unsigned char *)g_translate((const char *)s);
        if (t != NULL) {
            s = t;
        }
    }
    if (font == NULL) {
        return ln_expand(s, NULL, NULL, NULL);
    }
    fit.font = font;
    fit.scale = scale;
    /* the cache key: the font and the scale (whole steps in the games) */
    return ln_expand(s, vt_fit_name, &fit, (const void *)((UINT_PTR)font ^ ((UINT_PTR)(scale * 16.0f) << 24)));
}

static int vt_needs_own(const unsigned char *s, const unsigned char *end) {
    return g_override || ut_has_utf8(s, end);
}

/* ---- Runs -------------------------------------------------------------------------------------- */

typedef struct vt_run {
    void *font;                       /* the game's font handle, or a page's */
    int colour_page;
    int n;
    unsigned char b[VT_RUN_MAX + 1];
} vt_run;

static int vt_spacing(void *font) {
    unsigned char *impl = font != NULL ? *(unsigned char **)((unsigned char *)font + 4) : NULL;
    return impl != NULL ? *(int *)(impl + 8) : 0;
}

/* The font's own byte for a one-character unit, or -1 (a page letter is needed). */
static int vt_font_byte(const unsigned char *impl, const unsigned char *u, int len) {
    unsigned int cp;
    int b;
    if (g_override || ut_next(u, u + len, &cp) != len) {
        return -1;
    }
    b = ut_cp1252_byte(cp);
    if (b < 0x20 || b == 0x7F) {
        return -1;
    }
    if (b >= 0x80) {
        const int *index = (const int *)(impl + VT_FONT_INDEX);
        const int (*table)[5] = *(const int (**)[5])(impl + VT_FONT_TABLE);
        if (index[b] == 0 && (table == NULL || table[0][0] != b)) {
            return -1;                /* the font has no letter for it (not extended): a page letter */
        }
    }
    return b;
}

/* Calls `emit` for each run of one line (s..end, no '\n'); 0 when a run could not be built. */
typedef int (*vt_emit_fn)(void *state, vt_run *run);

static int vt_runs(void *font, const unsigned char *s, const unsigned char *end, vt_emit_fn emit, void *state) {
    unsigned char *impl = font != NULL ? *(unsigned char **)((unsigned char *)font + 4) : NULL;
    rg_font *rf = impl != NULL ? rg_font_of(impl) : NULL;
    vt_run run;
    ut_unit_t u;
    run.font = NULL;
    run.n = 0;
    run.colour_page = 0;
    if (impl == NULL) {
        return 0;
    }
    while (s < end) {
        void *target;
        int colour_page = 0, b, ul;
        unsigned char byte, composed[64];
        const unsigned char *us = s;
        ut_unit(s, end, &u);
        if (u.len <= 0) {
            break;
        }
        ul = u.len;
        if (u.kind == UT_CLUSTER && u.len > 1) {
            /* a base letter and its marks as their precomposed letter where one exists (NFC: the font's own é
               for e + U+0301); otherwise the whole cluster */
            int c = tl_compose(s, u.len, composed, (int)sizeof composed);
            if (c > 0) {
                us = composed;
                ul = c;
            }
        }
        b = (u.kind == UT_SPACE && !g_override) ? ' ' : vt_font_byte(impl, us, ul);
        if (b >= 0) {
            target = font;
            byte = (unsigned char)b;
        } else {
            rg_entry *e = rf != NULL ? rg_unit(rf, us, ul) : NULL;
            if (e != NULL) {
                target = e->page->outer;
                colour_page = e->page->colour;
                byte = e->slot;
            } else {
                target = font;        /* no letter could be made: the font's '?' */
                byte = '?';
            }
        }
        if (run.n > 0 && (run.font != target || run.n >= VT_RUN_MAX)) {
            run.b[run.n] = 0;
            if (!emit(state, &run)) {
                return 0;
            }
            run.n = 0;
        }
        run.font = target;
        run.colour_page = colour_page;
        run.b[run.n++] = byte;
        s += u.len;
    }
    if (run.n > 0) {
        run.b[run.n] = 0;
        return emit(state, &run);
    }
    return 1;
}

/* The game's own width of Use Unicode Font's reference sentence in a font (rg_fit_em): its width routine, called
   with the font handle whose +4 is the font object, for plain ASCII (so the game's own letters measure it). */
static int vt_reference_width(unsigned char *impl) {
    static const unsigned char REFERENCE[] = "The quick brown fox jumps over the lazy dog 0123456789";
    void *outer[2];
    outer[0] = NULL;
    outer[1] = impl;
    return g_width != NULL ? g_width(outer, NULL, REFERENCE, 1.0f) : 0;
}

typedef struct vt_measure { float scale; int total; int spacing; } vt_measure;

static int vt_measure_run(void *state, vt_run *run) {
    vt_measure *m = (vt_measure *)state;
    m->total += g_width(run->font, NULL, run->b, m->scale) + m->spacing;
    return 1;
}

/* One line's width as the game's width routine measures it (with its trailing spacing). */
static int vt_line_advance(void *font, const unsigned char *s, const unsigned char *end, float scale) {
    vt_measure m;
    m.scale = scale;
    m.total = 0;
    m.spacing = vt_spacing(font);
    vt_runs(font, s, end, vt_measure_run, &m);
    return m.total;
}

static int vt_own_width(void *font, const unsigned char *s, float scale) {
    const unsigned char *end = ut_end(s), *line = s, *p;
    int widest = 0, spacing = vt_spacing(font);
    InterlockedIncrement(&g_own_draws);
    for (p = s; ; ++p) {
        if (p == end || *p == '\n') {
            int w = vt_line_advance(font, line, p, scale);
            if (w > widest) {
                widest = w;
            }
            if (p == end) {
                break;
            }
            line = p + 1;
        }
    }
    return widest > 0 ? widest - spacing : 0;
}

typedef struct vt_drawing { void *ctx; int x, y; unsigned int colour, white; int spacing; } vt_drawing;

static int vt_draw_run(void *state, vt_run *run) {
    vt_drawing *d = (vt_drawing *)state;
    g_draw(d->ctx, NULL, run->b, d->x, d->y, run->colour_page ? d->white : d->colour, run->font);
    d->x += g_width(run->font, NULL, run->b, 1.0f) + d->spacing;
    return 1;
}

static int vt_own_draw(void *ctx, const unsigned char *s, int x, int y, unsigned int colour, void *font) {
    const unsigned char *end = ut_end(s), *line = s, *p;
    vt_drawing d;
    unsigned int alpha = colour >> 24;
    int line_height;
    unsigned char *impl = font != NULL ? *(unsigned char **)((unsigned char *)font + 4) : NULL;
    if (impl == NULL || *(void **)(impl + VT_FONT_PICTURE) == NULL) {
        return 1;                     /* the game draws nothing either */
    }
    InterlockedIncrement(&g_own_draws);
    if (alpha == 0) {
        alpha = (*(unsigned int *)(UINT_PTR)g_vt->default_colour) >> 24;
    }
    line_height = *(int *)(impl + 4);
    d.ctx = ctx;
    d.y = y;
    d.colour = colour;
    d.white = (alpha << 24) | 0xFFFFFFu;
    d.spacing = vt_spacing(font);
    for (p = s; ; ++p) {
        if (p == end || *p == '\n') {
            d.x = x;
            vt_runs(font, line, p, vt_draw_run, &d);
            if (p == end) {
                break;
            }
            d.y += line_height;
            line = p + 1;
        }
    }
    return 1;
}

/* ---- Width and draw ---------------------------------------------------------------------------- */

static int __fastcall width_hook(void *font, void *edx, const unsigned char *s, float scale) {
    (void)edx;
    __try {
        const unsigned char *t = vt_source(s, font, scale);
        if (t != NULL && font != NULL && vt_needs_own(t, ut_end(t))) {
            return vt_own_width(font, t, scale);
        }
        return g_width(font, NULL, t, scale);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return g_width(font, NULL, s, scale);
}

static int __fastcall draw_hook(void *ctx, void *edx, const unsigned char *s, int x, int y,
                                unsigned int colour, void *font) {
    (void)edx;
    __try {
        void *f = font != NULL ? font : *(void **)((unsigned char *)ctx + 0x5C);
        const unsigned char *t = vt_source(s, f, 1.0f);
        if (g_ln_slot_pending) {
            ln_flush_pending(0);
        }
        if (t != NULL && f != NULL && vt_needs_own(t, ut_end(t))) {
            vt_own_draw(ctx, t, x, y, colour, f);
            return 0;
        }
        return g_draw(ctx, NULL, t, x, y, colour, font);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return g_draw(ctx, NULL, s, x, y, colour, font);
}

/* ---- Line breaking (VV2-VV5) ------------------------------------------------------------------ */

static int vt_unit_advance(void *font, const unsigned char *s, int len, float scale) {
    return vt_line_advance(font, s, s + len, scale);
}

#define VT_BREAK_SPAN 8192            /* the bytes of a text looked at for one line's breaks */

typedef struct vt_breaks { const unsigned char *base; int span; unsigned char *at; } vt_breaks;

/* May a line start at q (text_layout.h tl_breaks: UAX #14 by ICU, or the built-in table)? */
static int vt_may_break(const vt_breaks *b, const unsigned char *q) {
    int i = (int)(q - b->base);
    return b->at != NULL && i > 0 && i < b->span && b->at[i] != 0;
}

/* The width of s[0..len) less its trailing spaces. */
static int vt_trimmed_advance(void *font, const unsigned char *s, int len, float scale) {
    while (len > 0 && s[len - 1] == ' ') {
        --len;
    }
    return len > 0 ? vt_unit_advance(font, s, len, scale) : 0;
}

/* The longest start of the shaped run s[0..len), ending between whole clusters (and, with `need`, where a line
   may break), whose bytes fit `bytes` and whose width, its trailing spaces left out, fits `room`; 0 when none.
   The candidates are measured by halving (a start is never narrower than a shorter one), so a long run is
   shaped only a few times. */
static int vt_run_fit(void *font, const unsigned char *s, int len, int room, int bytes, float scale,
                      const vt_breaks *b, int need) {
    const unsigned char *p = s, *q = s + len;
    int *ends, n = 0, lo, hi, best = 0;
    ends = (int *)tl_alloc(sizeof(int) * (size_t)(len + 1));
    if (ends == NULL) {
        return 0;
    }
    while (p < q) {
        unsigned int lastcp;
        int k = ut_grapheme(p, q, &lastcp);
        if (k <= 0) {
            break;
        }
        p += k;
        if ((int)(p - s) > bytes) {
            break;
        }
        if (!need || vt_may_break(b, p)) {
            ends[n++] = (int)(p - s);
        }
    }
    lo = 0;
    hi = n - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (vt_trimmed_advance(font, s, ends[mid], scale) <= room) {
            best = ends[mid];
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    tl_free(ends);
    return best;
}

/* The game's line fitting, by units (docs/UNICODE_SPEC.md row 3, "Line breaking"): breaks at spaces as the game
   does; between whole clusters next to a letter of a script written without spaces (Chinese, Japanese, Korean,
   Thai, Lao, Khmer, Myanmar, emoji) where UAX #14 allows it -- Windows' ICU, which knows the Thai, Lao, Khmer and
   Myanmar words and the kinsoku rules, or the built-in table (text_layout.h) -- inside a shaped run as well; and
   inside a word only when the word alone is wider than the line: after its longest start of whole clusters that
   fits (at least one).  Never writes more than max_count bytes. */
static const unsigned char *vt_linefit_units(void *font, const unsigned char *src, unsigned char *out, int max_count,
                                             int max_width, unsigned char *paragraph, int nl_as_space, float scale,
                                             const vt_breaks *brk) {
    const unsigned char *p = src, *end = ut_end(src), *break_src = NULL;
    int o = 0, w = 0, break_o = -1, prev_nl = 0;
    ut_unit_t u;
    out[0] = 0;
    if (paragraph != NULL) {
        *paragraph = 0;
    }
    if (max_count < 2) {
        return end;
    }
    for (;;) {
        int space;
        ut_unit(p, end, &u);
        if (u.kind == UT_END) {
            out[o] = 0;
            return p;
        }
        space = u.kind == UT_SPACE;
        if (u.kind == UT_NEWLINE) {
            if (prev_nl) {
                out[o] = 0;
                if (paragraph != NULL) *paragraph = 1;
                return p + 1;
            }
            prev_nl = 1;
            if (o == 0 || out[o - 1] == ' ') {
                ++p;
                continue;
            }
            if (!nl_as_space) {
                out[o] = 0;
                return p + 1;
            }
            space = 1;
        } else {
            prev_nl = 0;
        }
        if (space) {
            int sw;
            if (o == 0 || out[o - 1] == ' ') {
                ++p;
                continue;
            }
            sw = vt_unit_advance(font, (const unsigned char *)" ", 1, scale);
            if (o + 1 >= max_count || w + sw > max_width) {
                out[o] = 0;
                return p + 1;
            }
            out[o++] = ' ';
            w += sw;
            break_o = o;
            break_src = p + 1;
            ++p;
            continue;
        }
        {
            int uw = vt_unit_advance(font, p, u.len, scale);
            if (o > 0 && out[o - 1] != ' ' && vt_may_break(brk, p)) {
                break_o = o;
                break_src = p;
            }
            if (o + u.len >= max_count || w + uw > max_width) {
                if (u.kind == UT_RUN) {
                    /* a shaped run breaks inside where a line may break (a Thai word, a space in it) */
                    int b = vt_run_fit(font, p, u.len, max_width - w, max_count - 1 - o, scale, brk, 1);
                    if (b > 0) {
                        CopyMemory(out + o, p, (size_t)b);
                        o += b;
                        while (o > 0 && out[o - 1] == ' ') {
                            --o;
                        }
                        out[o] = 0;
                        return p + b;
                    }
                }
                if (break_o > 0) {
                    o = break_o;
                    while (o > 0 && out[o - 1] == ' ') {
                        --o;
                    }
                    out[o] = 0;
                    return break_src;
                }
                if (o > 0) {
                    out[o] = 0;
                    return p;
                }
                /* One unit wider than the line: a shaped run is cut after its longest start of whole clusters
                   that fits (at least one); any other unit goes alone (cut between characters when it is longer
                   than the buffer itself). */
                {
                    int n = 0;
                    if (u.kind == UT_RUN) {
                        n = vt_run_fit(font, p, u.len, max_width, max_count - 1, scale, brk, 0);
                        if (n <= 0) {
                            unsigned int lastcp;
                            n = ut_grapheme(p, p + u.len, &lastcp);
                        }
                    }
                    if (n <= 0 || n > max_count - 1) {
                        n = u.len < max_count - 1 ? u.len : ut_fit(p, u.len, max_count - 1);
                    }
                    if (n <= 0) {
                        unsigned int cp;
                        n = ut_next(p, end, &cp);
                        if (n > max_count - 1) {
                            return p + n;           /* cannot be held at all: skipped whole */
                        }
                    }
                    CopyMemory(out, p, (size_t)n);
                    out[n] = 0;
                    return p + n;
                }
            }
            CopyMemory(out + o, p, (size_t)u.len);
            if (u.kind == UT_RUN) {
                /* the run's own last place to break, for a unit after it that does not fit */
                const unsigned char *q;
                for (q = p + u.len - 1; q > p; --q) {
                    if (vt_may_break(brk, q)) {
                        break_o = o + (int)(q - p);
                        break_src = q;
                        break;
                    }
                }
            }
            o += u.len;
            w += uw;
            p += u.len;
        }
    }
}

static const unsigned char *vt_own_linefit(void *font, const unsigned char *src, unsigned char *out, int max_count,
                                           int max_width, unsigned char *paragraph, int nl_as_space, float scale) {
    const unsigned char *next;
    vt_breaks brk;
    InterlockedIncrement(&g_own_draws);
    brk.base = src;
    brk.span = (int)(ut_end(src) - src);
    if (brk.span > max_count + 64) {
        brk.span = max_count + 64;
    }
    if (brk.span > VT_BREAK_SPAN) {
        brk.span = VT_BREAK_SPAN;
    }
    brk.at = (unsigned char *)tl_alloc((size_t)brk.span + 1);
    if (brk.at != NULL) {
        tl_breaks(src, brk.span, brk.at);
    }
    next = vt_linefit_units(font, src, out, max_count, max_width, paragraph, nl_as_space, scale, &brk);
    tl_free(brk.at);
    return next;
}

static const unsigned char *__fastcall linefit_hook(void *font, void *edx, const unsigned char *src, unsigned char *out,
                                                    int max_count, int max_width, unsigned char *paragraph,
                                                    int nl_as_space, float scale) {
    (void)edx;
    __try {
        const unsigned char *t = vt_source(src, font, scale);
        if (t != NULL && out != NULL && font != NULL && vt_needs_own(t, ut_end(t))) {
            return vt_own_linefit(font, t, out, max_count, max_width, paragraph, nl_as_space, scale);
        }
        return g_linefit(font, NULL, t, out, max_count, max_width, paragraph, nl_as_space, scale);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return g_linefit(font, NULL, src, out, max_count, max_width, paragraph, nl_as_space, scale);
}

/* ---- Counted draw and justified paragraphs (VV3-VV5) ------------------------------------------ */

static int __fastcall nbyte_hook(void *ctx, void *edx, const unsigned char *s, int max_bytes, int x, int y,
                                 int measure_only, unsigned int colour, void *font) {
    (void)edx;
    __try {
        unsigned char span[VT_RUN_MAX + 1];
        int n = 0;
        void *f = font != NULL ? font : *(void **)((unsigned char *)ctx + 0x5C);
        if (s != NULL && f != NULL && max_bytes > 0) {
            while (n < max_bytes && n < VT_RUN_MAX && s[n]) {
                ++n;
            }
            span[n] = 0;
            CopyMemory(span, s, (size_t)n);
            if (n < VT_RUN_MAX && vt_needs_own(span, span + n)) {
                int advance = vt_line_advance(f, span, span + n, 1.0f);
                InterlockedIncrement(&g_own_draws);
                if (!measure_only) {
                    vt_own_draw(ctx, span, x, y, colour, f);
                }
                return advance;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return g_nbyte(ctx, NULL, s, max_bytes, x, y, measure_only, colour, font);
}

/* Text the game's justification cannot lay out: a text with a letter of a script written without spaces
   (text_layout.h tl_no_space_letter: Chinese, Japanese, Korean, Thai, ...) or a zero width space, or a word
   wider than the paragraph (the stock routine would never finish such a line). */
static int vt_needs_own_paragraph(void *font, const unsigned char *t, int width) {
    const unsigned char *end = ut_end(t), *p = t, *word = t;
    if (!vt_needs_own(t, end)) {
        return 0;
    }
    while (p < end) {
        unsigned int cp;
        int k = ut_next(p, end, &cp);
        if (cp >= 0x80 && (cp == 0x200B || tl_no_space_letter(cp))) {
            return 1;
        }
        if (cp == ' ' || cp == '\n') {
            if (p > word && vt_line_advance(font, word, p, 1.0f) > width) {
                return 1;
            }
            word = p + k;
        }
        p += k;
    }
    return p > word && vt_line_advance(font, word, p, 1.0f) > width;
}

static int __fastcall justify_hook(void *holder, void *edx, const unsigned char *text, int x, int y, int width,
                                   unsigned int colour, void *font, int measure_only) {
    (void)edx;
    __try {
        void *ctx = holder != NULL ? *(void **)holder : NULL;
        void *f = font != NULL ? font : (ctx != NULL ? *(void **)((unsigned char *)ctx + 0x5C) : NULL);
        const unsigned char *t = vt_source(text, f, 1.0f);
        if (t != NULL && f != NULL && width > 0 && vt_needs_own_paragraph(f, t, width)) {
            /* Lines broken by units, drawn from the left. */
            unsigned char line[4096];
            const unsigned char *p = t;
            unsigned char *impl = *(unsigned char **)((unsigned char *)f + 4);
            int lh = impl != NULL ? *(int *)(impl + 4) : 0, lines = 0, guard = 0;
            while (*p && guard++ < 4000) {
                unsigned char para = 0;
                const unsigned char *next = vt_own_linefit(f, p, line, sizeof line, width, &para, 0, 1.0f);
                if (line[0] && !measure_only) {
                    vt_own_draw(ctx, line, x, y + lines * lh, colour, f);
                }
                ++lines;
                if (next == p) {
                    break;
                }
                p = next;
            }
            return lines * lh;
        }
        return g_justify(holder, NULL, t, x, y, width, colour, font, measure_only);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return g_justify(holder, NULL, text, x, y, width, colour, font, measure_only);
}

/* ---- Text boxes -------------------------------------------------------------------------------- */

/* A box never cuts its own text by pixels (the game's cut removes one byte at a time from the end and
   so could cut inside a character -- and it changes what the box gives back): its flag is off while
   the game draws it, and back on after. */
static void __fastcall ctldraw_hook(unsigned char *ctl, void *edx) {
    unsigned char cut = 0;
    int saved = 0;
    (void)edx;
    __try {
        if (ctl != NULL) {
            cut = ctl[0x24];
            ctl[0x24] = 0;
            saved = 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        saved = 0;
    }
    g_ctldraw(ctl, NULL);
    if (saved) {
        ctl[0x24] = cut;
    }
}

static int __fastcall seteditable_hook(unsigned char *box, void *edx, int editable, int limit) {
    (void)edx;
    __try {
        if (box != NULL && (editable & 0xFF) && limit > 0 && limit < VV_SHARED_NAME_BYTES && box[0x2D] == 0) {
            limit = VV_SHARED_NAME_BYTES;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return g_seteditable(box, NULL, editable, limit);
}

static int __fastcall settext_hook(unsigned char *box, void *edx, const unsigned char *s) {
    const unsigned char *full = NULL;
    (void)edx;
    __try {
        full = ln_full_of(s);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        full = NULL;
    }
    return g_settext(box, NULL, full != NULL ? full : s);
}

static int __fastcall gettext_hook(unsigned char *wrapper, void *edx, unsigned char *buf, int size) {
    (void)edx;
    __try {
        unsigned char *box = wrapper != NULL ? *(unsigned char **)(wrapper + 0x10) : NULL;
        const unsigned char *text = box != NULL ? *(const unsigned char **)(box + 0x30) : NULL;
        if (text != NULL && buf != NULL && size > 1 && ln_len(text) > size - 1) {
            int n;
            ln_shorten(text, buf, size);
            n = ln_len(buf);
            ZeroMemory(buf + n, (size_t)(size - n));       /* as strncpy pads */
            return (int)(UINT_PTR)buf;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return g_gettext(wrapper, NULL, buf, size);
}

/* A typed text from SDL: ASCII of one character is posted as the game posts it; anything else that is
   well-formed UTF-8 goes into the ring and is posted as MARK | slot << 8, which only the box takes. */
static unsigned int g_high_surrogate;   /* the first half of a pair SDL sent on its own */

/* SDL 2.0.3 (the games' SDL2.dll) turns each WM_CHAR into text by itself, so a character above U+FFFF
   (an emoji, a cuneiform sign) typed with the emoji panel arrives as TWO texts: each UTF-16 half
   written as a three-byte sequence (ED A0..AF xx, then ED B0..BF xx), which is not UTF-8.  The halves
   are joined here into the character's own four bytes; a half on its own is dropped. */
static int vt_join_surrogates(const unsigned char *s, unsigned char *out, int cap) {
    const unsigned char *end = ut_end(s), *p = s;
    int n = 0;
    while (p < end) {
        unsigned int cp;
        int k = ut_seq(p, end, &cp);
        if (k == 0 && end - p >= 3 && p[0] == 0xED && p[1] >= 0xA0 && (p[2] & 0xC0) == 0x80) {
            unsigned int half = 0xD000u | ((unsigned int)(p[1] & 0x3F) << 6) | (p[2] & 0x3Fu);
            p += 3;
            if (half < 0xDC00) {
                g_high_surrogate = half;
            } else if (g_high_surrogate != 0) {
                cp = 0x10000u + ((g_high_surrogate - 0xD800u) << 10) + (half - 0xDC00u);
                g_high_surrogate = 0;
                if (n + 4 >= cap) {
                    return -1;
                }
                n += ut_encode(cp, out + n);
            }
            continue;
        }
        if (k == 0) {
            return -1;                  /* malformed: skipped, as the game skipped it */
        }
        g_high_surrogate = 0;
        if (n + k >= cap) {
            return -1;
        }
        CopyMemory(out + n, p, (size_t)k);
        n += k;
        p += k;
    }
    out[n] = 0;
    return n;
}

static int vt_text_key(const unsigned char *s) {
    const unsigned char *end, *p;
    unsigned char joined[sizeof g_ring[0]];
    int printable = 0;
    if (s == NULL || s[0] == 0) {
        return -1;
    }
    if (s[0] < 0x80 && s[1] == 0) {
        g_high_surrogate = 0;
        return s[0];
    }
    if (ut_end(s) - s >= (int)sizeof g_ring[0] || vt_join_surrogates(s, joined, (int)sizeof joined) <= 0) {
        return -1;
    }
    s = joined;
    end = ut_end(s);
    for (p = s; p < end;) {
        unsigned int cp;
        int k = ut_seq(p, end, &cp);
        if (k == 0) {
            return -1;                /* malformed: skipped, as the game skipped it */
        }
        if (cp >= 0x20 && cp != 0x7F && !(cp >= 0x80 && cp < 0xA0)) {
            printable = 1;
        }
        p += k;
    }
    if (!printable) {
        return -1;
    }
    g_ring_next = (g_ring_next + 1) % VT_RING;
    CopyMemory(g_ring[g_ring_next], s, (size_t)(end - s) + 1);
    return (int)(VT_MARK | ((unsigned int)g_ring_next << 8));
}

/* The bytes appending the characters s[0..end) to text[0..len) takes (each as ut_append writes it). */
static int vt_append_size(const unsigned char *text, int len, const unsigned char *s, const unsigned char *end) {
    unsigned char scratch[3 + 4 * 64];
    int keep = len > 3 ? 3 : len, at, need = 0;
    CopyMemory(scratch, text + len - keep, (size_t)keep);
    at = keep;
    while (s < end) {
        unsigned int cp;
        int k = ut_seq(s, end, &cp), n;
        if (k == 0 || at + 4 > (int)sizeof scratch) {
            return 0x7FFFFFFF;
        }
        s += k;
        if (cp < 0x20 || cp == 0x7F || (cp >= 0x80 && cp < 0xA0)) {
            continue;
        }
        n = ut_append(scratch, at, cp, scratch + at);
        at += n;
        need += n;
    }
    return need;
}

/* The box whose last typed character it refused (its limit), and a checksum of the text it held then
   (docs/UNICODE_SPEC.md row 4, from VF2): a mark typed right after belongs to the refused character, so it is
   refused too and never lands on the box's last character.  Any change to the text -- a character the box
   takes, Backspace, a paste -- ends it. */
static unsigned char *g_refused_box;
static unsigned int g_refused_text;

static unsigned int vt_text_sum(const unsigned char *text) {
    unsigned int h = 2166136261u;
    while (*text) {
        h = (h ^ *text++) * 16777619u;
    }
    return h;
}

static void vt_refused(unsigned char *box) {
    const unsigned char *text = *(const unsigned char **)(box + 0x30);
    g_refused_box = text != NULL ? box : NULL;
    g_refused_text = text != NULL ? vt_text_sum(text) : 0;
}

/* The focused box takes a typed text: each grapheme cluster whole (Unicode 18.0, text_utf8.h), as long as
   all of it fits the box's limit -- an emoji sequence or an accented letter is never stored in part. */
static int __cdecl vt_box_insert(unsigned char *box, unsigned int p2) {
    __try {
        const unsigned char *s = g_ring[(p2 >> 8) & (VT_RING - 1)], *end = ut_end(s), *p = s, *cluster_end = s;
        const unsigned char *now = *(const unsigned char **)(box + 0x30);
        if (g_refused_box == box && now != NULL && vt_text_sum(now) == g_refused_text) {
            /* the marks and joiners that would join the character the box refused are refused with it */
            while (p < end) {
                unsigned int cp;
                int k = ut_seq(p, end, &cp);
                if (k == 0 || !ut_extends(cp)) {
                    break;
                }
                p += k;
            }
            cluster_end = p;
        }
        for (; p < end;) {
            unsigned int cp;
            unsigned char bytes[4];
            unsigned char *text = *(unsigned char **)(box + 0x30);
            int k = ut_seq(p, end, &cp), len, n, limit = *(int *)(box + 0x28), i;
            if (k == 0 || text == NULL) {
                break;
            }
            len = ln_len(text);
            if (p >= cluster_end) {
                unsigned int last;
                int g = ut_grapheme(p, end, &last);
                cluster_end = p + (g > 0 ? g : k);
                if (len + vt_append_size(text, len, p, cluster_end) > limit) {
                    vt_refused(box);
                    break;
                }
            }
            p += k;
            if (cp < 0x20 || cp == 0x7F || (cp >= 0x80 && cp < 0xA0)) {
                continue;
            }
            n = ut_append(text, len, cp, bytes);
            if (len + n > limit) {
                vt_refused(box);
                break;
            }
            if (box[0x2D] != 0 || box[0x2F] != 0) {
                break;
            }
            /* All but the last byte straight in; the last through the game's own handler, which checks
               the limit again, stores it and tells the screen the text changed. */
            for (i = 0; i < n - 1; ++i) {
                text[len + i] = bytes[i];
            }
            text[len + n - 1] = 0;
            g_handler(box, NULL, 5, 0, bytes[n - 1]);
            g_refused_box = NULL;
            text = *(unsigned char **)(box + 0x30);
            if (text == NULL || ln_len(text) != len + n) {
                if (text != NULL && ln_len(text) >= len) {
                    text[len] = 0;
                }
                break;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return 1;
}

__declspec(naked) static void chartype_hook(void) {
    __asm {
        cmp     dword ptr [esp + 4], 5
        jne     stock
        mov     eax, dword ptr [esp + 0x0C]
        and     eax, 0xFF0000FF
        cmp     eax, VT_MARK
        jne     stock
        push    ecx
        push    dword ptr [esp + 0x10]      /* p2 */
        push    ecx                         /* the box */
        call    vt_box_insert
        add     esp, 8
        pop     ecx
        mov     eax, 1
        ret     0x0C
    stock:
        jmp     dword ptr [g_chartype_tramp]
    }
}

/* Backspace: the length the text keeps when its last unit is erased. */
static int __cdecl vt_backspace(const unsigned char *text, int len) {
    __try {
        int keep = ut_erase_last(text, len);
        return keep >= 0 && keep < len ? keep : len - 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return len - 1;
}

__declspec(naked) static void backspace_hook(void) {
    __asm {
        push    ecx
        push    eax
        push    dword ptr [ecx + 0x30]
        call    vt_backspace
        add     esp, 8
        pop     ecx
        mov     edx, dword ptr [ecx + 0x30]
        mov     byte ptr [edx + eax], 0
        jmp     dword ptr [g_backspace_back]
    }
}

/* For "VVFP Copy and Paste.dll": put UTF-8 text into a text box (the box object, the one at its
   wrapper's +0x10) exactly as typing does -- each grapheme cluster whole, a Windows-1252 character as its one
   byte, stopping before the first one that does not fit the box's byte limit ([box+0x28]).  Returns the
   number of bytes the box's text grew by; 0 for malformed or empty text. */
int __stdcall VvfpBoxInsertUtf8(unsigned char *box, const char *utf8) {
    __try {
        unsigned char *text;
        int before, key;
        if (box == NULL || utf8 == NULL || g_vt == NULL || (text = *(unsigned char **)(box + 0x30)) == NULL) {
            return 0;
        }
        before = ln_len(text);
        while (*utf8) {
            /* A ring slot holds at most 39 bytes: insert in whole-character chunks. */
            unsigned char chunk[36];
            const unsigned char *s = (const unsigned char *)utf8, *end = ut_end(s);
            int n = 0;
            while (s + n < end) {
                unsigned int last;
                /* Whole grapheme clusters (Unicode 18.0), so the box's limit never splits one between two
                   chunks; a cluster longer than a chunk goes in character by character. */
                int k = ut_grapheme(s + n, end, &last);
                if (k <= 0 || n + k > 32) {
                    if (n > 0) {
                        break;
                    }
                    k = ut_seq(s, end, &last);
                    if (k == 0) {
                        k = 1;              /* a stray byte: read by the rule (Windows-1252) */
                    }
                    n = k;
                    break;
                }
                n += k;
            }
            CopyMemory(chunk, s, (size_t)n);
            chunk[n] = 0;
            utf8 += n;
            g_ring_next = (g_ring_next + 1) % VT_RING;
            {
                /* Stray bytes become their Windows-1252 characters, re-encoded as UTF-8 for the ring. */
                const unsigned char *p = chunk, *e = chunk + n;
                int o = 0;
                while (p < e && o + 4 < (int)sizeof g_ring[0]) {
                    unsigned int cp;
                    p += ut_next(p, e, &cp);
                    o += ut_encode(cp, g_ring[g_ring_next] + o);
                }
                g_ring[g_ring_next][o] = 0;
            }
            key = (int)(VT_MARK | ((unsigned int)g_ring_next << 8));
            vt_box_insert(box, (unsigned int)key);
            text = *(unsigned char **)(box + 0x30);
            if (text == NULL || ln_len(text) - before < 0) {
                break;
            }
            if (*utf8 && ln_len(text) + 1 > *(int *)(box + 0x28)) {
                break;
            }
        }
        text = *(unsigned char **)(box + 0x30);
        return text != NULL ? ln_len(text) - before : 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return 0;
}
