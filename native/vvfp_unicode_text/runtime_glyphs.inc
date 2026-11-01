/* runtime_glyphs.inc -- letters made while the game runs, for every character a font does not hold.

   WHERE THEY LIVE.  A font's own letters (and PR #670's Windows-1252 ones) are drawn by the game from
   the font's picture.  Every other unit of text (text_utf8.h: a grapheme cluster, or a shaped run of
   Arabic, Hebrew, an Indic script...) is made once, the first time it is drawn or measured, and put in
   a PAGE: a picture of the same pixel format as the font's, laid out like the font's own (one row per
   line, every letter as tall as the line, standing on the font's baseline), with a glyph table and a
   256-entry index -- the fields of the game's own font object (ldwFontImpl: +4 line height, +8 spacing,
   +0xC picture, +0x10/+0x14 its size, +0x18 table, +0x1C index, +0x41C tinted copies), and the font's
   own class.  A page is drawn and measured by the GAME's own draw and width routines, called with a
   string of slot bytes (1..255 but '\n'): so colour, transparency, clipping and spacing are exactly the
   game's.  A page whose letters change has its tinted copies freed (the game makes them again).

   HOW A UNIT IS MADE.  Windows shapes it (Uniscribe: ScriptItemize, ScriptShape, ScriptPlace,
   ScriptLayout -- joined Arabic letters, Indic reordering, emoji sequences, right-to-left order inside
   the unit), in the first typeface of the chain that has every glyph:
       the font's own style  (Burweed ICG when the player has it, else Comic Sans MS, for ldwBurweed27;
                              Arial for ldwarialbold)  -- or, with "Use Unicode Font", the chosen face;
       Segoe UI, Segoe UI Historic (cuneiform, hieroglyphs, runes...), Segoe UI Symbol, Segoe UI Emoji,
       Yu Gothic, Microsoft YaHei, Malgun Gothic, Nirmala UI, Ebrima, then the Noto fonts if installed.
   Each glyph is drawn by GDI (GetGlyphOutlineW, 65 grey levels) at the size whose capital H is as tall
   as the font's own H, bold, thickened like PR #670's letters; a glyph with colour layers (COLR/CPAL:
   Segoe UI Emoji) is drawn in its colours, on a colour page the game draws untinted.  A unit taller
   than the line is made smaller until it fits.  Nothing is shipped: only the player's own Windows fonts
   are used, and the game's pictures are never changed. */

#define RG_PAGE_W 1024
#define RG_PAGE_ROWS 6
#define RG_SLOTS 254
#define RG_MAX_FONTS 16
#define RG_CACHE 8192
#define RG_MAX_UNIT 1024
#define RG_FACES 24

typedef struct rg_page {
    unsigned char impl[0x420];      /* a font object of the game's own class */
    void *outer[2];                 /* the font handle the draw routines take: +4 = impl */
    void *image[2];                 /* the picture object: +0 SDL_Surface* */
    sdl_surface *surf;
    int (*table)[5];
    int slots;                      /* entries used (entry 0 is a blank) */
    int cx, row;
    int colour;
    struct rg_page *next;
} rg_page;

typedef struct rg_font {
    unsigned char *impl;            /* the game's font object */
    int burweed;
    vg_metrics m;
    long h_total;                   /* the ink of the font's own 'H' (weight to match) */
    int format_bits;
    unsigned int rmask, gmask, bmask, amask;
    unsigned char ashift;
    rg_page *mono, *colour;
} rg_font;

typedef struct rg_entry {
    unsigned int hash;
    rg_font *font;
    unsigned char *bytes;
    int len;
    rg_page *page;
    unsigned char slot;
    int width;                      /* the unit's advance as the width routine measures it (+ spacing) */
} rg_entry;

typedef struct rg_face {
    WCHAR face[64];
    int weight;
    int present;                    /* -1 unknown */
    int bold;                       /* thickening steps */
    int cap_em;                     /* capital height per 1000 em, 0 unknown */
} rg_face;

typedef struct rg_hfont {
    int face;                       /* index into g_faces */
    int ppem;
    HFONT font;
    SCRIPT_CACHE cache;
    WORD missing;                   /* the font's default glyph */
    struct rg_hfont *next;
} rg_hfont;

typedef struct rg_colr {
    int face;
    unsigned char *colr, *cpal;
    DWORD colr_len, cpal_len;
    struct rg_colr *next;
} rg_colr;

static rg_font g_fonts[RG_MAX_FONTS];
static int g_font_count;
static rg_entry *g_cache;
static int g_cache_used;
static rg_face g_faces[RG_FACES];
static int g_face_count;
static rg_hfont *g_hfonts;
static rg_colr *g_colrs;
static HDC g_dc;
static WCHAR g_override_face[64];   /* "Use Unicode Font": the chosen face ("" = Segoe UI) */
static int g_override;
static volatile LONG g_units_made;  /* for the tests */

static const WCHAR *const RG_CHAIN[] = {
    L"Segoe UI", L"Segoe UI Historic", L"Segoe UI Symbol", L"Segoe UI Emoji", L"Yu Gothic", L"Microsoft YaHei",
    L"Malgun Gothic", L"Nirmala UI", L"Ebrima", L"Noto Sans", L"Noto Sans CJK JP", L"Noto Sans Symbols 2",
    L"Noto Sans Cuneiform", L"Noto Color Emoji", NULL
};

static int rg_face_index(const WCHAR *face, int weight) {
    int i;
    for (i = 0; i < g_face_count; ++i) {
        if (g_faces[i].weight == weight && lstrcmpiW(g_faces[i].face, face) == 0) {
            return i;
        }
    }
    if (g_face_count >= RG_FACES) {
        return -1;
    }
    lstrcpynW(g_faces[g_face_count].face, face, 64);
    g_faces[g_face_count].weight = weight;
    g_faces[g_face_count].present = -1;
    g_faces[g_face_count].bold = -1;
    return g_face_count++;
}

static HFONT rg_make_font(int face, int ppem) {
    return CreateFontW(-ppem, 0, 0, 0, g_faces[face].weight, 0, 0, 0, DEFAULT_CHARSET, 0, 0,
                       ANTIALIASED_QUALITY, 0, g_faces[face].face);
}

/* The face is installed (Windows did not substitute another). */
static int rg_present(int face) {
    if (g_faces[face].present < 0) {
        WCHAR got[64];
        HFONT f = rg_make_font(face, 20);
        got[0] = 0;
        if (f != NULL) {
            HGDIOBJ old = SelectObject(g_dc, f);
            GetTextFaceW(g_dc, 64, got);
            SelectObject(g_dc, old);
            DeleteObject(f);
        }
        g_faces[face].present = lstrcmpiW(got, g_faces[face].face) == 0;
    }
    return g_faces[face].present;
}

static rg_hfont *rg_font_at(int face, int ppem) {
    rg_hfont *h;
    SCRIPT_FONTPROPERTIES props;
    for (h = g_hfonts; h != NULL; h = h->next) {
        if (h->face == face && h->ppem == ppem) {
            SelectObject(g_dc, h->font);
            return h;
        }
    }
    h = (rg_hfont *)vg_alloc(sizeof *h);
    if (h == NULL) {
        return NULL;
    }
    ZeroMemory(h, sizeof *h);
    h->face = face;
    h->ppem = ppem;
    h->font = rg_make_font(face, ppem);
    if (h->font == NULL) {
        vg_free(h);
        return NULL;
    }
    SelectObject(g_dc, h->font);
    ZeroMemory(&props, sizeof props);
    props.cBytes = sizeof props;
    h->missing = ScriptGetFontProperties(g_dc, &h->cache, &props) == S_OK ? props.wgDefault : 0;
    h->next = g_hfonts;
    g_hfonts = h;
    return h;
}

/* A glyph's grey coverage (0..255), its box and origin; 0 when it has no ink. */
static int rg_raster(WORD glyph, unsigned char **px, int *w, int *h, int *ox, int *oy) {
    GLYPHMETRICS gm;
    MAT2 mat;
    DWORD size;
    unsigned char *buf;
    int x, y, pitch;
    ZeroMemory(&mat, sizeof mat);
    mat.eM11.value = 1;
    mat.eM22.value = 1;
    *px = NULL;
    size = GetGlyphOutlineW(g_dc, glyph, GGO_GRAY8_BITMAP | GGO_GLYPH_INDEX, &gm, 0, NULL, &mat);
    if (size == 0 || size == GDI_ERROR) {
        return 0;
    }
    buf = (unsigned char *)vg_alloc(size);
    if (buf == NULL) {
        return 0;
    }
    if (GetGlyphOutlineW(g_dc, glyph, GGO_GRAY8_BITMAP | GGO_GLYPH_INDEX, &gm, size, buf, &mat) == GDI_ERROR) {
        vg_free(buf);
        return 0;
    }
    *w = (int)gm.gmBlackBoxX;
    *h = (int)gm.gmBlackBoxY;
    *ox = gm.gmptGlyphOrigin.x;
    *oy = gm.gmptGlyphOrigin.y;
    pitch = (*w + 3) & ~3;
    *px = (unsigned char *)vg_alloc((size_t)(*w) * (size_t)(*h) + 1);
    if (*px == NULL) {
        vg_free(buf);
        return 0;
    }
    for (y = 0; y < *h; ++y) {
        for (x = 0; x < *w; ++x) {
            int v = buf[y * pitch + x];
            (*px)[y * (*w) + x] = (unsigned char)(v < 64 ? (v * 255 + 32) / 64 : 255);
        }
    }
    vg_free(buf);
    return 1;
}

/* The face's capital height per 1000 em, and the thickening that matches the font's own weight. */
static void rg_face_fit(int face, const rg_font *f) {
    rg_hfont *h;
    WORD idx = 0xFFFF;
    unsigned char *px;
    int w, hh, ox, oy;
    if (g_faces[face].bold >= 0) {
        return;
    }
    g_faces[face].bold = 0;
    g_faces[face].cap_em = 700;
    h = rg_font_at(face, 100);
    if (h == NULL) {
        return;
    }
    if (GetGlyphIndicesW(g_dc, L"H", 1, &idx, GGI_MARK_NONEXISTING_GLYPHS) == GDI_ERROR || idx == 0xFFFF) {
        return;
    }
    if (rg_raster(idx, &px, &w, &hh, &ox, &oy)) {
        g_faces[face].cap_em = hh * 10;
        vg_free(px);
    }
    {
        /* Thicken like PR #670's letters: while the H at the font's size is lighter than the font's own. */
        int cap = f->m.baseline - f->m.cap_top, ppem;
        vg_mask r;
        ppem = g_faces[face].cap_em > 0 ? (cap * 1000 + g_faces[face].cap_em / 2) / g_faces[face].cap_em : cap;
        if (ppem < 4) ppem = 4;
        h = rg_font_at(face, ppem);
        if (h != NULL && rg_raster(idx, &px, &w, &hh, &ox, &oy)) {
            r.w = w; r.h = hh; r.px = px;
            while (g_faces[face].bold < 2 && vg_total(&r) * 100 < f->h_total * 85) {
                if (!vg_embolden(&r)) {
                    break;
                }
                ++g_faces[face].bold;
            }
            vg_free(r.px);
        }
    }
}

static int rg_ppem(int face, const rg_font *f) {
    int cap = f->m.baseline - f->m.cap_top, ppem;
    rg_face_fit(face, f);
    ppem = g_faces[face].cap_em > 0 ? (cap * 1000 + g_faces[face].cap_em / 2) / g_faces[face].cap_em : cap;
    return ppem < 4 ? 4 : ppem > 200 ? 200 : ppem;
}

/* ---- COLR/CPAL colour layers ------------------------------------------------------------------ */

static rg_colr *rg_colr_of(int face) {
    rg_colr *c;
    for (c = g_colrs; c != NULL; c = c->next) {
        if (c->face == face) {
            return c->colr != NULL ? c : NULL;
        }
    }
    c = (rg_colr *)vg_alloc(sizeof *c);
    if (c == NULL) {
        return NULL;
    }
    ZeroMemory(c, sizeof *c);
    c->face = face;
    c->next = g_colrs;
    g_colrs = c;
    c->colr_len = GetFontData(g_dc, 0x524C4F43u /* 'COLR' */, 0, NULL, 0);
    c->cpal_len = GetFontData(g_dc, 0x4C415043u /* 'CPAL' */, 0, NULL, 0);
    if (c->colr_len == GDI_ERROR || c->cpal_len == GDI_ERROR || c->colr_len < 14 || c->cpal_len < 12) {
        return NULL;
    }
    c->colr = (unsigned char *)vg_alloc(c->colr_len);
    c->cpal = (unsigned char *)vg_alloc(c->cpal_len);
    if (c->colr == NULL || c->cpal == NULL
        || GetFontData(g_dc, 0x524C4F43u, 0, c->colr, c->colr_len) != c->colr_len
        || GetFontData(g_dc, 0x4C415043u, 0, c->cpal, c->cpal_len) != c->cpal_len) {
        vg_free(c->colr);
        vg_free(c->cpal);
        c->colr = c->cpal = NULL;
        return NULL;
    }
    return c;
}

/* The colour layers of `glyph` (COLR version 0 records): count, first layer record offset. */
static int rg_layers(const rg_colr *c, WORD glyph, DWORD *layers_at) {
    unsigned int n = vg_be16(c->colr + 2), lo = 0, hi;
    DWORD base = vg_be32(c->colr + 4), layers = vg_be32(c->colr + 8);
    if (base + n * 6 > c->colr_len) {
        return 0;
    }
    hi = n;
    while (lo < hi) {
        unsigned int mid = (lo + hi) / 2;
        const unsigned char *r = c->colr + base + mid * 6;
        unsigned int g = vg_be16(r);
        if (g == glyph) {
            unsigned int first = vg_be16(r + 2), count = vg_be16(r + 4);
            if (layers + (first + count) * 4 > c->colr_len) {
                return 0;
            }
            *layers_at = layers + first * 4;
            return (int)count;
        }
        if (g < glyph) lo = mid + 1; else hi = mid;
    }
    return 0;
}

/* Palette 0's colour `index` as 0xAARRGGBB; white for the foreground (0xFFFF). */
static unsigned int rg_palette(const rg_colr *c, unsigned int index) {
    unsigned int entries = vg_be16(c->cpal + 2), first;
    DWORD records = vg_be32(c->cpal + 8);
    const unsigned char *bgra;
    if (index == 0xFFFF || index >= entries) {
        return 0xFFFFFFFFu;
    }
    first = vg_be16(c->cpal + 12);
    if (records + (first + index + 1) * 4 > c->cpal_len) {
        return 0xFFFFFFFFu;
    }
    bgra = c->cpal + records + (first + index) * 4;
    return ((unsigned int)bgra[3] << 24) | ((unsigned int)bgra[2] << 16) | ((unsigned int)bgra[1] << 8) | bgra[0];
}

/* ---- Making a unit ---------------------------------------------------------------------------- */

typedef struct rg_canvas {
    int w, h, base;                 /* base: the baseline's row */
    int ox;                         /* the pen's start column */
    unsigned int *px;               /* 0xAARRGGBB, straight alpha */
    int colour;                     /* a layer drew a colour */
} rg_canvas;

static void rg_over(rg_canvas *cv, int x, int y, unsigned int argb, int cover) {
    unsigned int *d;
    unsigned int sa, da, oa, r, g, b;
    if (x < 0 || y < 0 || x >= cv->w || y >= cv->h || cover <= 0) {
        return;
    }
    sa = ((argb >> 24) * (unsigned int)cover + 127) / 255;
    if (sa == 0) {
        return;
    }
    d = &cv->px[y * cv->w + x];
    da = *d >> 24;
    oa = sa + da * (255 - sa) / 255;
    if (oa == 0) {
        return;
    }
    r = (((argb >> 16) & 0xFF) * sa + ((*d >> 16) & 0xFF) * da * (255 - sa) / 255) / oa;
    g = (((argb >> 8) & 0xFF) * sa + ((*d >> 8) & 0xFF) * da * (255 - sa) / 255) / oa;
    b = ((argb & 0xFF) * sa + (*d & 0xFF) * da * (255 - sa) / 255) / oa;
    *d = (oa << 24) | (r << 16) | (g << 8) | b;
}

static void rg_stamp(rg_canvas *cv, int pen, WORD glyph, unsigned int argb, int bold, int dx, int dy) {
    unsigned char *px;
    int w, h, ox, oy, x, y, k;
    if (!rg_raster(glyph, &px, &w, &h, &ox, &oy)) {
        return;
    }
    for (k = 0; k <= bold; ++k) {
        for (y = 0; y < h; ++y) {
            for (x = 0; x < w; ++x) {
                rg_over(cv, cv->ox + pen + dx + ox + x + k, cv->base - oy - dy + y, argb, px[y * w + x]);
            }
        }
    }
    vg_free(px);
}

/* Shape `text` in one face; 1 and the canvas drawn when every glyph is in the face. */
static int rg_shape(int face, int ppem, const WCHAR *text, int n, rg_canvas *cv, int *advance) {
    SCRIPT_ITEM items[65];
    int nitems = 0, i, pen = 0, ok = 1;
    BYTE levels[64];
    int order[64];
    WORD glyphs[RG_MAX_UNIT];
    WORD clusters[RG_MAX_UNIT];
    SCRIPT_VISATTR attrs[RG_MAX_UNIT];
    int advances[RG_MAX_UNIT];
    GOFFSET offsets[RG_MAX_UNIT];
    rg_hfont *h = rg_font_at(face, ppem);
    rg_colr *colr;
    if (h == NULL || n <= 0 || n > RG_MAX_UNIT
        || ScriptItemize(text, n, 64, NULL, NULL, items, &nitems) != S_OK || nitems <= 0 || nitems > 64) {
        return 0;
    }
    colr = rg_colr_of(face);
    SelectObject(g_dc, h->font);
    for (i = 0; i < nitems; ++i) {
        levels[i] = (BYTE)items[i].a.s.uBidiLevel;
    }
    if (ScriptLayout(nitems, levels, order, NULL) != S_OK) {
        for (i = 0; i < nitems; ++i) {
            order[i] = i;
        }
    }
    for (i = 0; i < nitems && ok; ++i) {
        SCRIPT_ITEM *it = &items[order[i]];
        int start = it->iCharPos, len = items[order[i] + 1].iCharPos - it->iCharPos, count = 0, j;
        ABC abc;
        HRESULT hr = ScriptShape(g_dc, &h->cache, text + start, len, RG_MAX_UNIT, &it->a, glyphs, clusters,
                                 attrs, &count);
        if (hr != S_OK || count <= 0) {
            ok = 0;
            break;
        }
        for (j = 0; j < count; ++j) {
            if (glyphs[j] == h->missing && !attrs[j].fZeroWidth) {
                /* A space (or another blank) may be the default glyph in no font; anything else is missing. */
                if (!(len == 1 && (text[start] == ' ' || text[start] == 0x3000))) {
                    ok = 0;
                }
            }
        }
        if (!ok) {
            break;
        }
        if (ScriptPlace(g_dc, &h->cache, glyphs, count, attrs, &it->a, advances, offsets, &abc) != S_OK) {
            ok = 0;
            break;
        }
        if (cv != NULL) {
            for (j = 0; j < count; ++j) {
                DWORD at = 0;
                int layers = colr != NULL ? rg_layers(colr, glyphs[j], &at) : 0;
                if (layers > 0) {
                    int k;
                    for (k = 0; k < layers; ++k) {
                        const unsigned char *rec = colr->colr + at + k * 4;
                        unsigned int argb = rg_palette(colr, vg_be16(rec + 2));
                        if ((argb & 0xFFFFFFu) != 0xFFFFFFu) {
                            cv->colour = 1;
                        }
                        rg_stamp(cv, pen, (WORD)vg_be16(rec), argb, 0, offsets[j].du, offsets[j].dv);
                    }
                } else {
                    rg_stamp(cv, pen, glyphs[j], 0xFFFFFFFFu, g_faces[face].bold, offsets[j].du, offsets[j].dv);
                }
                pen += advances[j];
            }
        } else {
            for (j = 0; j < count; ++j) {
                pen += advances[j];
            }
        }
    }
    *advance = pen;
    return ok;
}

static int rg_utf16(const unsigned char *s, int len, WCHAR *out, int cap) {
    const unsigned char *end = s + len;
    int n = 0;
    while (s < end) {
        unsigned int cp;
        s += ut_next(s, end, &cp);
        if (cp >= 0x10000) {
            if (n + 2 > cap) return -1;
            out[n++] = (WCHAR)(0xD800 + ((cp - 0x10000) >> 10));
            out[n++] = (WCHAR)(0xDC00 + ((cp - 0x10000) & 0x3FF));
        } else {
            if (n + 1 > cap) return -1;
            out[n++] = (WCHAR)cp;
        }
    }
    return n;
}

/* An emoji (Extended_Pictographic, keycaps, emoji presentation): Segoe UI Emoji is tried before the
   other Windows faces, so it is drawn in colour (Segoe UI Symbol holds many in black and white). */
static int rg_emoji(const unsigned char *s, int len) {
    const unsigned char *end = s + len;
    while (s < end) {
        unsigned int cp;
        s += ut_next(s, end, &cp);
        if ((cp >= 0x1F000 && cp <= 0x1FAFF) || (cp >= 0x2600 && cp <= 0x27BF) || cp == 0xFE0F || cp == 0x20E3
            || cp == 0x2B50 || cp == 0x2B55 || (cp >= 0x2B1B && cp <= 0x2B1C) || cp == 0x231A || cp == 0x231B
            || (cp >= 0x23E9 && cp <= 0x23FA) || cp == 0x200D) {
            return 1;
        }
    }
    return 0;
}

/* The faces to try for a font, in order. */
static int rg_chain(const rg_font *f, const unsigned char *bytes, int len, int *faces, int cap) {
    int n = 0, i;
    if (g_override) {
        faces[n++] = rg_face_index(g_override_face[0] ? g_override_face : L"Segoe UI", 700);
    } else if (f->burweed) {
        if (g_gdi_state == 1 && g_gdi.burweed[0]) {
            faces[n++] = rg_face_index(g_gdi.burweed, 400);
        }
        faces[n++] = rg_face_index(L"Comic Sans MS", 700);
    } else {
        faces[n++] = rg_face_index(L"Arial", 700);
    }
    if (rg_emoji(bytes, len)) {
        faces[n++] = rg_face_index(L"Segoe UI Emoji", 400);
    }
    for (i = 0; RG_CHAIN[i] != NULL && n < cap; ++i) {
        int weight = lstrcmpW(RG_CHAIN[i], L"Segoe UI Emoji") == 0 || lstrcmpW(RG_CHAIN[i], L"Segoe UI Historic") == 0
                     || lstrcmpW(RG_CHAIN[i], L"Noto Color Emoji") == 0 ? 400 : 700;
        faces[n++] = rg_face_index(RG_CHAIN[i], weight);
    }
    return n;
}

/* Make a unit into a cell `line` rows tall: its ink on the font's baseline.  out_px: w*line ARGB. */
static int rg_make_cell(const rg_font *f, const unsigned char *bytes, int len, unsigned int **out_px,
                        int *out_w, int *out_colour) {
    WCHAR text[RG_MAX_UNIT];
    int n = rg_utf16(bytes, len, text, RG_MAX_UNIT), faces[RG_FACES], nfaces, i, chosen = -1, advance = 0;
    int line = f->m.line, ppem = 0, tries;
    rg_canvas cv;
    if (n <= 0 || g_dc == NULL) {
        return 0;
    }
    nfaces = rg_chain(f, bytes, len, faces, RG_FACES);
    for (i = 0; i < nfaces && chosen < 0; ++i) {
        if (faces[i] < 0 || !rg_present(faces[i])) {
            continue;
        }
        ppem = rg_ppem(faces[i], f);
        if (rg_shape(faces[i], ppem, text, n, NULL, &advance)) {
            chosen = faces[i];
        }
    }
    if (chosen < 0) {
        /* No face has it: Segoe UI's own "missing" box, so the player sees something is there. */
        chosen = rg_face_index(L"Segoe UI", 700);
        if (chosen < 0 || !rg_present(chosen)) {
            return 0;
        }
        ppem = rg_ppem(chosen, f);
    }
    for (tries = 0; tries < 4; ++tries) {
        int l = 0, t = 0, r = -1, b = -1, x, y, w, shift, cell_left, cell_right;
        ZeroMemory(&cv, sizeof cv);
        cv.h = line * 3;
        cv.base = line + f->m.baseline;
        cv.w = ppem * (n + 2) + 8;
        if (cv.w > 8192) cv.w = 8192;
        cv.px = (unsigned int *)vg_alloc((size_t)cv.w * (size_t)cv.h * 4);
        if (cv.px == NULL) {
            return 0;
        }
        ZeroMemory(cv.px, (size_t)cv.w * (size_t)cv.h * 4);
        /* Draw with the pen 4 pixels in, so ink left of the origin is kept. */
        cv.ox = 4;
        if (!rg_shape(chosen, ppem, text, n, &cv, &advance)) {
            /* Not every glyph is in the face (the last resort): draw what it has anyway. */
            advance = advance > 0 ? advance : ppem / 2;
        }
        for (y = 0; y < cv.h; ++y) {
            for (x = 0; x < cv.w; ++x) {
                if (cv.px[y * cv.w + x] >> 24) {
                    if (r < 0) { l = r = x; t = b = y; }
                    if (x < l) l = x;
                    if (x > r) r = x;
                    if (y < t) t = y;
                    if (y > b) b = y;
                }
            }
        }
        if (r >= 0 && (b - t + 1) > line && ppem > 4) {
            ppem = ppem * line / (b - t + 1);
            if (ppem < 4) ppem = 4;
            vg_free(cv.px);
            continue;
        }
        /* The cell: from the leftmost of origin and ink to the rightmost of advance and ink. */
        cell_left = 4;
        cell_right = 4 + advance;
        if (r >= 0) {
            if (l < cell_left) cell_left = l;
            if (r + 1 > cell_right) cell_right = r + 1;
        }
        w = cell_right - cell_left;
        if (w < 1) w = 1;
        /* Rows: the line [line, 2*line) of the canvas, moved up or down when ink would be cut. */
        shift = 0;
        if (r >= 0) {
            if (t < line) shift = t - line;                       /* ink above the line: move down */
            else if (b >= 2 * line) shift = b - 2 * line + 1;     /* below: move up */
        }
        *out_px = (unsigned int *)vg_alloc((size_t)w * (size_t)line * 4);
        if (*out_px == NULL) {
            vg_free(cv.px);
            return 0;
        }
        for (y = 0; y < line; ++y) {
            int sy = line + y + shift;
            for (x = 0; x < w; ++x) {
                int sx = cell_left + x;
                (*out_px)[y * w + x] = (sy >= 0 && sy < cv.h && sx >= 0 && sx < cv.w) ? cv.px[sy * cv.w + sx] : 0;
            }
        }
        *out_w = w;
        *out_colour = cv.colour;
        vg_free(cv.px);
        InterlockedIncrement(&g_units_made);
        return 1;
    }
    return 0;
}

/* ---- Pages ------------------------------------------------------------------------------------ */

static void rg_flush_tints(rg_page *p) {
    sdl_free_fn release = *(sdl_free_fn *)(UINT_PTR)g_game->sdl_free;
    unsigned int *node = *(unsigned int **)(p->impl + 0x41C);
    while (node != NULL) {
        if (node[1] != 0) {
            release((void *)(UINT_PTR)node[1]);
        }
        node = (unsigned int *)(UINT_PTR)node[2];        /* the game's 12-byte node is left (it is tiny) */
    }
    *(unsigned int **)(p->impl + 0x41C) = NULL;
}

static rg_page *rg_new_page(rg_font *f, int colour) {
    sdl_create_fn create = *(sdl_create_fn *)(UINT_PTR)g_game->sdl_create;
    rg_page *p = (rg_page *)vg_alloc(sizeof *p);
    int h = RG_PAGE_ROWS * (f->m.line + 1);
    if (p == NULL) {
        return NULL;
    }
    ZeroMemory(p, sizeof *p);
    p->table = (int (*)[5])vg_alloc(sizeof(int[5]) * 257);
    p->surf = (sdl_surface *)create(0, RG_PAGE_W, h, f->format_bits, f->rmask, f->gmask, f->bmask, f->amask);
    if (p->table == NULL || p->surf == NULL || p->surf->pixels == NULL) {
        if (p->surf != NULL) {
            (*(sdl_free_fn *)(UINT_PTR)g_game->sdl_free)(p->surf);
        }
        vg_free(p->table);
        vg_free(p);
        return NULL;
    }
    ZeroMemory(p->table, sizeof(int[5]) * 257);
    {
        int y;
        for (y = 0; y < h; ++y) {
            ZeroMemory((unsigned char *)p->surf->pixels + y * p->surf->pitch, (size_t)RG_PAGE_W * 4);
        }
    }
    /* The font object: the game's own (vtable, line height, spacing), with this page's picture. */
    CopyMemory(p->impl, f->impl, sizeof p->impl);
    p->image[0] = p->surf;
    p->image[1] = (void *)1;
    *(void ***)(p->impl + VT_FONT_PICTURE) = p->image;
    *(int *)(p->impl + 0x10) = RG_PAGE_W;
    *(int *)(p->impl + 0x14) = h;
    *(int (**)[5])(p->impl + VT_FONT_TABLE) = p->table;
    ZeroMemory(p->impl + VT_FONT_INDEX, 256 * sizeof(int));
    *(void **)(p->impl + 0x41C) = NULL;
    p->table[0][0] = 1;                         /* entry 0: an empty one-pixel letter */
    p->table[0][1] = 0;
    p->table[0][2] = 0;
    p->table[0][3] = 1;
    p->table[0][4] = f->m.line;
    p->slots = 1;
    p->cx = 1;
    p->row = 0;
    p->colour = colour;
    p->outer[0] = NULL;
    p->outer[1] = p->impl;
    return p;
}

/* Put a cell on a page of the font; the page and slot byte, 0 when there is no room anywhere. */
static int rg_place(rg_font *f, const unsigned int *px, int w, int colour, rg_page **out) {
    rg_page **list = colour ? &f->colour : &f->mono, *p;
    int line = f->m.line, x, y;
    if (w > RG_PAGE_W) {
        w = RG_PAGE_W;
    }
    for (p = *list; p != NULL; p = p->next) {
        if (p->slots < RG_SLOTS + 1) {
            if (p->cx + w > RG_PAGE_W && p->row + 1 < RG_PAGE_ROWS) {
                p->row++;
                p->cx = 0;
            }
            if (p->cx + w <= RG_PAGE_W) {
                break;
            }
        }
    }
    if (p == NULL) {
        p = rg_new_page(f, colour);
        if (p == NULL) {
            return 0;
        }
        p->next = *list;
        *list = p;
    }
    {
        int top = p->row * (line + 1), slot, entry = p->slots;
        sdl_surface *s = p->surf;
        unsigned int white = f->rmask | f->gmask | f->bmask;
        for (y = 0; y < line; ++y) {
            unsigned int *row = (unsigned int *)((unsigned char *)s->pixels + (top + y) * s->pitch);
            for (x = 0; x < w; ++x) {
                unsigned int c = px[y * w + x], a = c >> 24, v;
                if (a == 0) {
                    v = 0;
                } else if (colour) {
                    unsigned int r = (c >> 16) & 0xFF, g = (c >> 8) & 0xFF, b = c & 0xFF;
                    v = ((r * (f->rmask / 255)) & f->rmask) | ((g * (f->gmask / 255)) & f->gmask)
                        | ((b * (f->bmask / 255)) & f->bmask) | ((a << f->ashift) & f->amask);
                } else {
                    v = white | ((a << f->ashift) & f->amask);
                }
                row[p->cx + x] = v;
            }
        }
        /* The slot byte: 1..255, never '\n'. */
        slot = entry < 0x0A ? entry : entry + 1;
        p->table[entry][0] = slot;
        p->table[entry][1] = p->cx;
        p->table[entry][2] = top;
        p->table[entry][3] = p->cx + w;
        p->table[entry][4] = top + line;
        ((int *)(p->impl + VT_FONT_INDEX))[slot] = entry;
        p->slots++;
        p->cx += w + 1;
        ZeroMemory(p->table[p->slots], sizeof(int[5]));
        rg_flush_tints(p);
        *out = p;
        return slot;
    }
}

static rg_font *rg_font_of(const unsigned char *impl) {
    int i;
    for (i = 0; i < g_font_count; ++i) {
        if (g_fonts[i].impl == impl) {
            return &g_fonts[i];
        }
    }
    return NULL;
}

static unsigned int rg_hash(const rg_font *f, const unsigned char *b, int len) {
    unsigned int h = 2166136261u ^ (unsigned int)(UINT_PTR)f;
    int i;
    for (i = 0; i < len; ++i) {
        h = (h ^ b[i]) * 16777619u;
    }
    return h ? h : 1;
}

/* The page letter of a unit, made on first use.  NULL when it cannot be made. */
static rg_entry *rg_unit(rg_font *f, const unsigned char *bytes, int len) {
    unsigned int h, i;
    rg_entry *e;
    unsigned int *px = NULL;
    int w = 0, colour = 0, slot;
    rg_page *page = NULL;
    if (len <= 0 || len > RG_MAX_UNIT) {
        return NULL;
    }
    if (g_cache == NULL) {
        g_cache = (rg_entry *)vg_alloc(sizeof(rg_entry) * RG_CACHE);
        if (g_cache == NULL) {
            return NULL;
        }
        ZeroMemory(g_cache, sizeof(rg_entry) * RG_CACHE);
    }
    h = rg_hash(f, bytes, len);
    for (i = 0; i < RG_CACHE; ++i) {
        e = &g_cache[(h + i) & (RG_CACHE - 1)];
        if (e->hash == 0) {
            break;
        }
        if (e->hash == h && e->font == f && e->len == len && memcmp(e->bytes, bytes, (size_t)len) == 0) {
            return e->page != NULL ? e : NULL;
        }
    }
    if (i == RG_CACHE || g_cache_used >= RG_CACHE * 3 / 4) {
        return NULL;
    }
    e->bytes = (unsigned char *)vg_alloc((size_t)len);
    if (e->bytes == NULL) {
        return NULL;
    }
    CopyMemory(e->bytes, bytes, (size_t)len);
    e->len = len;
    e->font = f;
    e->hash = h;
    ++g_cache_used;
    if (rg_make_cell(f, bytes, len, &px, &w, &colour)) {
        slot = rg_place(f, px, w, colour, &page);
        if (slot > 0) {
            e->page = page;
            e->slot = (unsigned char)slot;
            e->width = w + f->m.spacing;
        }
        vg_free(px);
    }
    return e->page != NULL ? e : NULL;
}

/* Called from the font constructor's detour for each of the two fonts: what pages need of it. */
static void rg_register(unsigned char *impl, int burweed, const vg_font *vf, const sdl_format *fmt) {
    rg_font *f;
    if (g_font_count >= RG_MAX_FONTS || rg_font_of(impl) != NULL) {
        return;
    }
    f = &g_fonts[g_font_count];
    ZeroMemory(f, sizeof *f);
    f->impl = impl;
    f->burweed = burweed;
    f->m = vf->m;
    f->h_total = vg_total(&vf->sheet_h);
    f->format_bits = fmt->bits;
    f->rmask = fmt->rmask;
    f->gmask = fmt->gmask;
    f->bmask = fmt->bmask;
    f->amask = fmt->amask;
    f->ashift = fmt->ashift;
    if (g_dc == NULL) {
        g_dc = CreateCompatibleDC(NULL);
    }
    ++g_font_count;
}
