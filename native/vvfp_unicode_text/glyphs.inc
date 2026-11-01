/* glyphs.inc -- the missing letters of one game font, made the way src/vv_font_glyphs.py makes them.

   Every step here is the Python module's, in the same order and with the same whole-number arithmetic,
   so the in-game letters and the Picture Studio's are the same pixels (tests/test_unicode_text.py runs
   this file in a harness and compares).  Read the module's docstring for the rules; the comments here
   only name the Python function each part follows.

   Included by vvfp_unicode_text.c and by glyph_harness.c.  Needs <windows.h> (GDI, the registry and the
   file API) and unicode_text_tables.h. */

#define VG_INK 32
#define VG_ACCENT_GAP 1
#define VG_MAX_FACES 8
#define VG_MAX_FONTS 64

typedef struct vg_mask { int w, h; unsigned char *px; } vg_mask;

static void *vg_alloc(size_t n) {
    return HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, n ? n : 1);
}

static void vg_free(void *p) {
    if (p != NULL) {
        HeapFree(GetProcessHeap(), 0, p);
    }
}

static int vg_blank(vg_mask *m, int w, int h) {
    m->w = w;
    m->h = h;
    m->px = (unsigned char *)vg_alloc((size_t)(w > 0 ? w : 1) * (size_t)(h > 0 ? h : 1));
    return m->px != NULL;
}

static int vg_at(const vg_mask *m, int x, int y) {
    return (x >= 0 && x < m->w && y >= 0 && y < m->h) ? m->px[y * m->w + x] : 0;
}

/* Mask.ink: 0 when empty. */
static int vg_ink(const vg_mask *m, int *l, int *t, int *r, int *b) {
    int x, y, any = 0;
    *l = m->w; *t = m->h; *r = -1; *b = -1;
    for (y = 0; y < m->h; ++y) {
        for (x = 0; x < m->w; ++x) {
            if (m->px[y * m->w + x] >= VG_INK) {
                any = 1;
                if (x < *l) *l = x;
                if (x > *r) *r = x;
                if (y < *t) *t = y;
                if (y > *b) *b = y;
            }
        }
    }
    return any;
}

static int vg_crop(vg_mask *out, const vg_mask *m, int l, int t, int r, int b) {
    int x, y;
    if (!vg_blank(out, r - l + 1, b - t + 1)) {
        return 0;
    }
    for (y = 0; y < out->h; ++y) {
        for (x = 0; x < out->w; ++x) {
            out->px[y * out->w + x] = (unsigned char)vg_at(m, l + x, t + y);
        }
    }
    return 1;
}

static long vg_total(const vg_mask *m) {
    long t = 0;
    int i;
    for (i = 0; i < m->w * m->h; ++i) {
        t += m->px[i];
    }
    return t;
}

/* ---- The sheet and its metrics (Sheet, _measure) --------------------------------------------- */

typedef struct vg_sheet {
    const unsigned char *alpha;     /* sheet alpha, row-major, sw x sh */
    int sw, sh;
    const int (*ent)[5];            /* the font's entries after the constructor's wrap */
    int n;
} vg_sheet;

static int vg_entry(const vg_sheet *s, int code) {
    int i;
    for (i = 0; i < s->n; ++i) {
        if ((s->ent[i][0] & 0xFF) == code) {
            return i;
        }
    }
    return -1;
}

static int vg_box(vg_mask *out, const vg_sheet *s, int code) {
    int i = vg_entry(s, code), x, y;
    const int *e;
    if (i < 0) {
        return 0;
    }
    e = s->ent[i];
    if (!vg_blank(out, e[3] - e[1], e[4] - e[2])) {
        return 0;
    }
    for (y = 0; y < out->h; ++y) {
        for (x = 0; x < out->w; ++x) {
            int sx = e[1] + x, sy = e[2] + y;
            out->px[y * out->w + x] = (sx >= 0 && sx < s->sw && sy >= 0 && sy < s->sh)
                                          ? s->alpha[sy * s->sw + sx] : 0;
        }
    }
    return 1;
}

typedef struct vg_metrics { int line, baseline, cap_top, x_top, left, right, spacing; } vg_metrics;

static void vg_sort(int *v, int n) {
    int i, j;
    for (i = 1; i < n; ++i) {
        int k = v[i];
        for (j = i - 1; j >= 0 && v[j] > k; --j) {
            v[j + 1] = v[j];
        }
        v[j + 1] = k;
    }
}

static int vg_measure(vg_metrics *m, const vg_sheet *s, int spacing) {
    static const char LETTERS[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
    int lefts[52], rights[52], n = 0, i, l, t, r, b;
    vg_mask h, x;
    if (!vg_box(&h, s, 'H')) {
        return 0;
    }
    if (!vg_box(&x, s, 'x')) {
        vg_free(h.px);
        return 0;
    }
    if (!vg_ink(&h, &l, &t, &r, &b)) {
        vg_free(h.px); vg_free(x.px);
        return 0;
    }
    m->baseline = b + 1;
    m->cap_top = t;
    if (!vg_ink(&x, &l, &t, &r, &b)) {
        vg_free(h.px); vg_free(x.px);
        return 0;
    }
    m->x_top = t;
    vg_free(h.px);
    vg_free(x.px);
    for (i = 0; LETTERS[i]; ++i) {
        vg_mask g;
        if (!vg_box(&g, s, (unsigned char)LETTERS[i])) {
            continue;
        }
        if (vg_ink(&g, &l, &t, &r, &b)) {
            lefts[n] = l;
            rights[n] = g.w - 1 - r;
            ++n;
        }
        vg_free(g.px);
    }
    vg_sort(lefts, n);
    vg_sort(rights, n);
    m->left = n ? lefts[(n - 1) / 2] : 0;
    m->right = n ? rights[(n - 1) / 2] : 0;
    m->line = s->ent[0][4] - s->ent[0][2];
    m->spacing = spacing;
    return 1;
}

/* ---- Windows' drawing of a typeface (_Gdi) --------------------------------------------------- */

typedef struct vg_gdi_font { WCHAR face[64]; int weight, ppem; HFONT font; } vg_gdi_font;

typedef struct vg_gdi {
    HDC dc;
    vg_gdi_font fonts[VG_MAX_FONTS];
    int font_count;
    WCHAR present_face[VG_MAX_FACES][64];
    int present[VG_MAX_FACES];
    int present_count;
    WCHAR burweed[64];              /* "" when the player has no Burweed */
} vg_gdi;

static int vg_select(vg_gdi *g, const WCHAR *face, int weight, int ppem) {
    int i;
    HFONT font = NULL;
    for (i = 0; i < g->font_count; ++i) {
        if (g->fonts[i].weight == weight && g->fonts[i].ppem == ppem && lstrcmpW(g->fonts[i].face, face) == 0) {
            font = g->fonts[i].font;
            break;
        }
    }
    if (font == NULL) {
        font = CreateFontW(-ppem, 0, 0, 0, weight, 0, 0, 0, 1, 0, 0, 4, 0, face);
        if (font == NULL) {
            return 0;
        }
        if (g->font_count < VG_MAX_FONTS) {
            vg_gdi_font *f = &g->fonts[g->font_count++];
            lstrcpynW(f->face, face, 64);
            f->weight = weight;
            f->ppem = ppem;
            f->font = font;
        } else {
            /* A full cache: drop the oldest (never selected again before it is replaced). */
            DeleteObject(g->fonts[0].font);
            MoveMemory(&g->fonts[0], &g->fonts[1], sizeof g->fonts[0] * (VG_MAX_FONTS - 1));
            lstrcpynW(g->fonts[VG_MAX_FONTS - 1].face, face, 64);
            g->fonts[VG_MAX_FONTS - 1].weight = weight;
            g->fonts[VG_MAX_FONTS - 1].ppem = ppem;
            g->fonts[VG_MAX_FONTS - 1].font = font;
        }
    }
    SelectObject(g->dc, font);
    return 1;
}

static void vg_forget(vg_gdi *g, const WCHAR *face) {
    int i;
    for (i = 0; i < g->present_count; ++i) {
        if (lstrcmpW(g->present_face[i], face) == 0) {
            g->present_face[i][0] = 0;
            g->present[i] = 0;
        }
    }
    for (i = 0; i < g->font_count;) {
        if (lstrcmpW(g->fonts[i].face, face) == 0) {
            DeleteObject(g->fonts[i].font);
            MoveMemory(&g->fonts[i], &g->fonts[i + 1], sizeof g->fonts[0] * (size_t)(g->font_count - i - 1));
            --g->font_count;
        } else {
            ++i;
        }
    }
}

static int vg_has_face(vg_gdi *g, const WCHAR *face, int weight) {
    int i;
    WCHAR got[64];
    for (i = 0; i < g->present_count; ++i) {
        if (g->present_face[i][0] && lstrcmpW(g->present_face[i], face) == 0) {
            return g->present[i];
        }
    }
    got[0] = 0;
    if (vg_select(g, face, weight, 20)) {
        GetTextFaceW(g->dc, 64, got);
    }
    if (g->present_count < VG_MAX_FACES) {
        lstrcpynW(g->present_face[g->present_count], face, 64);
        g->present[g->present_count] = lstrcmpiW(got, face) == 0;
        return g->present[g->present_count++];
    }
    return lstrcmpiW(got, face) == 0;
}

static int vg_has_char(vg_gdi *g, const WCHAR *face, int weight, WCHAR ch) {
    WORD index = 0xFFFF;
    if (!vg_has_face(g, face, weight) || !vg_select(g, face, weight, 20)) {
        return 0;
    }
    if (GetGlyphIndicesW(g->dc, &ch, 1, &index, GGI_MARK_NONEXISTING_GLYPHS) == GDI_ERROR) {
        return 0;
    }
    return index != 0xFFFF;
}

/* _Gdi.raster: the black box's coverage and the rows from its top to the baseline. */
static int vg_raster(vg_gdi *g, const WCHAR *face, int weight, int ppem, WCHAR ch, vg_mask *out, int *above) {
    GLYPHMETRICS gm;
    MAT2 mat;
    DWORD size;
    unsigned char *buf;
    int x, y, pitch;
    ZeroMemory(&mat, sizeof mat);
    mat.eM11.value = 1;
    mat.eM22.value = 1;
    if (!vg_select(g, face, weight, ppem)) {
        return 0;
    }
    size = GetGlyphOutlineW(g->dc, ch, GGO_GRAY8_BITMAP, &gm, 0, NULL, &mat);
    if (size == 0 || size == GDI_ERROR) {
        return 0;
    }
    buf = (unsigned char *)vg_alloc(size);
    if (buf == NULL) {
        return 0;
    }
    if (GetGlyphOutlineW(g->dc, ch, GGO_GRAY8_BITMAP, &gm, size, buf, &mat) == GDI_ERROR
        || !vg_blank(out, (int)gm.gmBlackBoxX, (int)gm.gmBlackBoxY)) {
        vg_free(buf);
        return 0;
    }
    pitch = ((int)gm.gmBlackBoxX + 3) & ~3;
    for (y = 0; y < out->h; ++y) {
        for (x = 0; x < out->w; ++x) {
            int v = buf[y * pitch + x];
            out->px[y * out->w + x] = (unsigned char)(v < 64 ? (v * 255 + 32) / 64 : 255);
        }
    }
    vg_free(buf);
    *above = gm.gmptGlyphOrigin.y;
    return 1;
}

/* ---- Burweed ICG, only when the player has it (_gdi, font_files, ttf_family) --------------------- */

static unsigned int vg_be16(const unsigned char *p) { return ((unsigned int)p[0] << 8) | p[1]; }
static unsigned int vg_be32(const unsigned char *p) {
    return ((unsigned int)p[0] << 24) | ((unsigned int)p[1] << 16) | ((unsigned int)p[2] << 8) | p[3];
}

/* ttf_family: 1 and `out` filled, 0 when the file is not a font. */
static int vg_ttf_family(const unsigned char *d, DWORD n, WCHAR *out, int cap) {
    DWORD base = 0, tables, i;
    int have_w = 0, have_m = 0;
    WCHAR w[64], m[64];
    if (n >= 16 && d[0] == 't' && d[1] == 't' && d[2] == 'c' && d[3] == 'f') {
        base = vg_be32(d + 12);
    }
    if (base + 12 > n) {
        return 0;
    }
    tables = vg_be16(d + base + 4);
    for (i = 0; i < tables; ++i) {
        const unsigned char *rec = d + base + 12 + 16 * i;
        DWORD off, count, strings, k;
        if (base + 12 + 16 * i + 16 > n) {
            return 0;
        }
        if (!(rec[0] == 'n' && rec[1] == 'a' && rec[2] == 'm' && rec[3] == 'e')) {
            continue;
        }
        off = vg_be32(rec + 8);
        if (off + 6 > n) {
            return 0;
        }
        count = vg_be16(d + off + 2);
        strings = vg_be16(d + off + 4);
        for (k = 0; k < count; ++k) {
            const unsigned char *r = d + off + 6 + 12 * k;
            unsigned int pid, eid, lang, nid, len, so, j;
            if (off + 6 + 12 * k + 12 > n) {
                return 0;
            }
            pid = vg_be16(r); eid = vg_be16(r + 2); lang = vg_be16(r + 4); nid = vg_be16(r + 6);
            len = vg_be16(r + 8); so = vg_be16(r + 10);
            if (nid != 1 || off + strings + so + len > n) {
                continue;
            }
            if (pid == 3 && (eid == 0 || eid == 1) && (lang == 0x409 || !have_w)) {
                for (j = 0; j + 1 < len && j / 2 < 63; j += 2) {
                    w[j / 2] = (WCHAR)vg_be16(d + off + strings + so + j);
                }
                w[j / 2] = 0;
                have_w = 1;
            } else if (pid == 1 && eid == 0 && !have_m) {
                for (j = 0; j < len && j < 63; ++j) {
                    m[j] = d[off + strings + so + j];
                }
                m[j] = 0;
                have_m = 1;
            }
        }
        if (have_w) {
            lstrcpynW(out, w, cap);
        } else if (have_m) {
            lstrcpynW(out, m, cap);
        }
        return (have_w || have_m) && out[0] != 0;
    }
    return 0;
}

static int vg_contains_i(const WCHAR *s, const WCHAR *word) {
    int n = lstrlenW(word), i;
    for (i = 0; s[i]; ++i) {
        if (CompareStringOrdinal(s + i, min(n, lstrlenW(s + i)), word, n, TRUE) == CSTR_EQUAL) {
            return 1;
        }
    }
    return 0;
}

static int vg_try_burweed(vg_gdi *g, const WCHAR *path) {
    HANDLE f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    DWORD size, got = 0;
    unsigned char *data;
    WCHAR family[64];
    int ok = 0;
    if (f == INVALID_HANDLE_VALUE) {
        return 0;
    }
    size = GetFileSize(f, NULL);
    data = (size != INVALID_FILE_SIZE && size > 0 && size < 64u * 1024 * 1024) ? (unsigned char *)vg_alloc(size) : NULL;
    if (data != NULL && ReadFile(f, data, size, &got, NULL) && got == size) {
        family[0] = 0;
        ok = vg_ttf_family(data, size, family, 64);
    }
    CloseHandle(f);
    vg_free(data);
    if (!ok) {
        return 0;
    }
    if (!vg_has_face(g, family, 400)) {
        if (AddFontResourceExW(path, FR_PRIVATE, NULL) <= 0) {
            return 0;
        }
        vg_forget(g, family);
    }
    if (vg_has_face(g, family, 400)) {
        lstrcpynW(g->burweed, family, 64);
        return 1;
    }
    return 0;
}

static int vg_try_registry(vg_gdi *g, HKEY hive, const WCHAR *fonts_dir) {
    HKEY key;
    DWORD i;
    if (RegOpenKeyExW(hive, L"Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts", 0, KEY_READ, &key) != ERROR_SUCCESS) {
        return 0;
    }
    for (i = 0;; ++i) {
        WCHAR name[256], value[MAX_PATH], path[MAX_PATH * 2];
        DWORD nlen = 256, vlen = sizeof value - sizeof(WCHAR), type = 0;
        LONG r = RegEnumValueW(key, i, name, &nlen, NULL, &type, (BYTE *)value, &vlen);
        if (r == ERROR_NO_MORE_ITEMS) {
            break;
        }
        if (r != ERROR_SUCCESS || type != REG_SZ || !vg_contains_i(name, L"Burweed")) {
            continue;
        }
        value[vlen / sizeof(WCHAR)] = 0;
        if (value[0] && value[1] == L':') {
            lstrcpynW(path, value, MAX_PATH * 2);
        } else {
            lstrcpynW(path, fonts_dir, MAX_PATH);
            lstrcatW(path, L"\\");
            lstrcatW(path, value);
        }
        if (vg_try_burweed(g, path)) {
            RegCloseKey(key);
            return 1;
        }
    }
    RegCloseKey(key);
    return 0;
}

static int vg_try_folder(vg_gdi *g, const WCHAR *folder) {
    WCHAR pattern[MAX_PATH * 2], path[MAX_PATH * 2];
    WIN32_FIND_DATAW fd;
    HANDLE h;
    if (!folder[0] || lstrlenW(folder) > MAX_PATH) {
        return 0;
    }
    lstrcpyW(pattern, folder);
    lstrcatW(pattern, L"\\*");
    h = FindFirstFileW(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    do {
        int n = lstrlenW(fd.cFileName);
        const WCHAR *ext = n > 4 ? fd.cFileName + n - 4 : L"";
        if ((fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || !vg_contains_i(fd.cFileName, L"Burweed")
            || !(lstrcmpiW(ext, L".ttf") == 0 || lstrcmpiW(ext, L".otf") == 0 || lstrcmpiW(ext, L".ttc") == 0)) {
            continue;
        }
        lstrcpyW(path, folder);
        lstrcatW(path, L"\\");
        lstrcatW(path, fd.cFileName);
        if (vg_try_burweed(g, path)) {
            FindClose(h);
            return 1;
        }
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return 0;
}

static int vg_gdi_open(vg_gdi *g) {
    WCHAR user[MAX_PATH], system[MAX_PATH];
    DWORD n;
    ZeroMemory(g, sizeof *g);
    g->dc = CreateCompatibleDC(NULL);
    if (g->dc == NULL) {
        return 0;
    }
    user[0] = system[0] = 0;
    n = GetEnvironmentVariableW(L"LOCALAPPDATA", user, MAX_PATH - 40);
    if (n > 0 && n < MAX_PATH - 40) {
        lstrcatW(user, L"\\Microsoft\\Windows\\Fonts");
    } else {
        user[0] = 0;
    }
    n = GetEnvironmentVariableW(L"WINDIR", system, MAX_PATH - 10);
    if (n > 0 && n < MAX_PATH - 10) {
        lstrcatW(system, L"\\Fonts");
    } else {
        lstrcpyW(system, L"C:\\Windows\\Fonts");
    }
    if (!vg_try_registry(g, HKEY_CURRENT_USER, system) && !vg_try_registry(g, HKEY_LOCAL_MACHINE, system)
        && !vg_try_folder(g, user)) {
        vg_try_folder(g, system);
    }
    return 1;
}

/* ---- A typeface fitted to a font (_Face) ------------------------------------------------------ */

typedef struct vg_face { WCHAR face[64]; int weight, ppem, bold, tried, ok; } vg_face;

static int vg_embolden(vg_mask *m) {
    vg_mask out;
    int x, y;
    if (!vg_blank(&out, m->w + 1, m->h)) {
        return 0;
    }
    for (y = 0; y < m->h; ++y) {
        for (x = 0; x < out.w; ++x) {
            int a = vg_at(m, x, y), b = vg_at(m, x - 1, y);
            out.px[y * out.w + x] = (unsigned char)(a > b ? a : b);
        }
    }
    vg_free(m->px);
    *m = out;
    return 1;
}

static void vg_face_fit(vg_gdi *g, vg_face *f, const vg_metrics *m, const vg_mask *sheet_h) {
    int cap = m->baseline - m->cap_top, ppem, best_diff = -1, best = 0, above;
    vg_mask r;
    long target;
    f->ppem = 0;
    f->bold = 0;
    for (ppem = 6; ppem <= 80; ++ppem) {
        int diff;
        if (!vg_raster(g, f->face, f->weight, ppem, L'H', &r, &above)) {
            continue;
        }
        diff = r.h > cap ? r.h - cap : cap - r.h;
        if (best_diff < 0 || diff < best_diff) {
            best_diff = diff;
            best = ppem;
        }
        vg_free(r.px);
        if (r.h >= cap) {
            break;
        }
    }
    if (best_diff < 0) {
        return;
    }
    f->ppem = best;
    target = vg_total(sheet_h);
    if (!vg_raster(g, f->face, f->weight, f->ppem, L'H', &r, &above)) {
        f->ppem = 0;
        return;
    }
    while (f->bold < 2 && vg_total(&r) * 100 < target * 85) {
        if (!vg_embolden(&r)) {
            break;
        }
        ++f->bold;
    }
    vg_free(r.px);
}

static int vg_face_draw(vg_gdi *g, const vg_face *f, WCHAR ch, vg_mask *out, int *above) {
    int i;
    if (f->ppem == 0 || !vg_raster(g, f->face, f->weight, f->ppem, ch, out, above)) {
        return 0;
    }
    for (i = 0; i < f->bold; ++i) {
        if (!vg_embolden(out)) {
            vg_free(out->px);
            return 0;
        }
    }
    return 1;
}

/* ---- Placing a letter in its box (_fit, _place) ----------------------------------------------- */

static int vg_fit(vg_mask *out, const vg_mask *canvas, int top, const vg_metrics *m) {
    int line = m->line, base = m->baseline, x, y, r;
    if (!vg_blank(out, canvas->w, line)) {
        return 0;
    }
    if (top >= 0) {
        for (y = 0; y < line; ++y) {
            for (x = 0; x < canvas->w; ++x) {
                out->px[y * canvas->w + x] = (unsigned char)vg_at(canvas, x, y - top);
            }
        }
        return 1;
    }
    {
        int src_rows = base - top;
        for (r = 0; r < base; ++r) {
            int lo = r * src_rows / base;
            int hi = ((r + 1) * src_rows + base - 1) / base;
            if (hi < lo + 1) {
                hi = lo + 1;
            }
            for (x = 0; x < canvas->w; ++x) {
                int v = 0;
                for (y = lo; y < hi; ++y) {
                    int a = vg_at(canvas, x, y);
                    if (a > v) v = a;
                }
                out->px[r * canvas->w + x] = (unsigned char)v;
            }
        }
        for (y = base; y < line; ++y) {
            for (x = 0; x < canvas->w; ++x) {
                out->px[y * canvas->w + x] = (unsigned char)vg_at(canvas, x, y - top);
            }
        }
    }
    return 1;
}

static int vg_place(vg_mask *out, const vg_mask *ink, int top, const vg_metrics *m) {
    vg_mask canvas;
    int x, y, ok;
    if (!vg_blank(&canvas, m->left + ink->w + m->right, ink->h)) {
        return 0;
    }
    for (y = 0; y < ink->h; ++y) {
        for (x = 0; x < ink->w; ++x) {
            canvas.px[y * canvas.w + m->left + x] = ink->px[y * ink->w + x];
        }
    }
    ok = vg_fit(out, &canvas, top, m);
    vg_free(canvas.px);
    return ok;
}

/* ---- One font's letters (FontGlyphs) ----------------------------------------------------------- */

enum { VG_NONE = 0, VG_GAME, VG_ALIAS, VG_TTF, VG_COMPOSED, VG_STAND_IN };

typedef struct vg_font {
    vg_gdi *gdi;
    vg_sheet sheet;
    vg_metrics m;
    int burweed;                    /* 1: ldwBurweed27, 0: ldwarialbold */
    vg_mask sheet_h;
    vg_face faces[VG_MAX_FACES];
    int face_count;
    vg_mask glyph[256];
    unsigned char state[256];       /* 0 not made, 1 making, 2 made */
    unsigned char source[256];      /* VG_* */
    unsigned char alias[256];       /* VG_ALIAS: the code it draws as */
} vg_font;

static vg_face *vg_font_face(vg_font *f, const WCHAR *face, int weight) {
    int i;
    vg_face *x;
    for (i = 0; i < f->face_count; ++i) {
        if (f->faces[i].weight == weight && lstrcmpW(f->faces[i].face, face) == 0) {
            return f->faces[i].ok ? &f->faces[i] : NULL;
        }
    }
    if (f->face_count >= VG_MAX_FACES) {
        return NULL;
    }
    x = &f->faces[f->face_count++];
    lstrcpynW(x->face, face, 64);
    x->weight = weight;
    x->ok = f->gdi != NULL && vg_has_face(f->gdi, face, weight);
    if (x->ok) {
        vg_face_fit(f->gdi, x, &f->m, &f->sheet_h);
    }
    return x->ok ? x : NULL;
}

/* The bitmap's own typeface when the player has it (_true). */
static int vg_true_face(vg_font *f, const WCHAR **face, int *weight) {
    if (f->burweed) {
        if (f->gdi == NULL || !f->gdi->burweed[0]) {
            return 0;
        }
        *face = f->gdi->burweed;
        *weight = 400;
        return 1;
    }
    *face = L"Arial";
    *weight = 700;
    return 1;
}

static void vg_stand_in(const vg_font *f, const WCHAR **face, int *weight) {
    *face = f->burweed ? L"Comic Sans MS" : L"Arial";
    *weight = 700;
}

static int vg_whole(vg_font *f, const WCHAR *face, int weight, WCHAR ch, vg_mask *out) {
    vg_face *x = vg_font_face(f, face, weight);
    vg_mask ink;
    int above, ok;
    if (x == NULL || !vg_has_char(f->gdi, face, weight, ch)) {
        return 0;
    }
    if (!vg_face_draw(f->gdi, x, ch, &ink, &above)) {
        return 0;
    }
    ok = vg_place(out, &ink, f->m.baseline - above, &f->m);
    vg_free(ink.px);
    return ok;
}

static const vg_mask *vg_glyph(vg_font *f, int code);

static int vg_compose(vg_font *f, int code, vg_mask *out) {
    const vg_accent *a = NULL;
    const vg_mask *plain;
    const WCHAR *face;
    int weight, i, l, t, r, b, ml, mt, mr, mb, above, ok;
    int mark_top, mark_left, left_pad, width, top, bottom;
    vg_face *x;
    vg_mask drawn, mark, base, canvas;
    for (i = 0; i < VG_ACCENT_COUNT; ++i) {
        if (VG_ACCENTS[i].code == code) {
            a = &VG_ACCENTS[i];
        }
    }
    if (a == NULL) {
        return 0;
    }
    plain = vg_glyph(f, a->plain);
    if (plain == NULL) {
        return 0;
    }
    if (!vg_true_face(f, &face, &weight)) {
        vg_stand_in(f, &face, &weight);
    }
    x = vg_font_face(f, face, weight);
    if (x == NULL) {
        vg_stand_in(f, &face, &weight);
        x = vg_font_face(f, face, weight);
    }
    if (x == NULL || !vg_has_char(f->gdi, face, weight, (WCHAR)a->mark)) {
        return 0;
    }
    if (!vg_face_draw(f->gdi, x, (WCHAR)a->mark, &drawn, &above)) {
        return 0;
    }
    if (!vg_ink(&drawn, &ml, &mt, &mr, &mb)) {
        vg_free(drawn.px);
        return 0;
    }
    ok = vg_crop(&mark, &drawn, ml, mt, mr, mb);
    vg_free(drawn.px);
    if (!ok) {
        return 0;
    }
    if (!vg_blank(&base, plain->w, plain->h)) {
        vg_free(mark.px);
        return 0;
    }
    CopyMemory(base.px, plain->px, (size_t)plain->w * (size_t)plain->h);
    if (a->plain == 'i' || a->plain == 'j') {
        int y, xx;
        for (y = 0; y < f->m.x_top && y < base.h; ++y) {
            for (xx = 0; xx < base.w; ++xx) {
                base.px[y * base.w + xx] = 0;
            }
        }
    }
    if (!vg_ink(&base, &l, &t, &r, &b)) {
        vg_free(mark.px);
        vg_free(base.px);
        return 0;
    }
    mark_top = a->below ? f->m.baseline : t - VG_ACCENT_GAP - mark.h;
    mark_left = (l + r + 1) / 2 - mark.w / 2;
    left_pad = mark_left < 0 ? -mark_left : 0;
    width = base.w + left_pad;
    if (left_pad + mark_left + mark.w > width) {
        width = left_pad + mark_left + mark.w;
    }
    top = mark_top < 0 ? mark_top : 0;
    bottom = mark_top + mark.h > base.h ? mark_top + mark.h : base.h;
    if (!vg_blank(&canvas, width, bottom - top)) {
        vg_free(mark.px);
        vg_free(base.px);
        return 0;
    }
    {
        int y, xx;
        for (y = 0; y < base.h; ++y) {
            for (xx = 0; xx < base.w; ++xx) {
                canvas.px[(y - top) * width + xx + left_pad] = base.px[y * base.w + xx];
            }
        }
        for (y = 0; y < mark.h; ++y) {
            for (xx = 0; xx < mark.w; ++xx) {
                int k = (mark_top + y - top) * width + mark_left + left_pad + xx;
                unsigned char v = mark.px[y * mark.w + xx];
                if (v > canvas.px[k]) canvas.px[k] = v;
            }
        }
    }
    ok = vg_fit(out, &canvas, top, &f->m);
    vg_free(canvas.px);
    vg_free(mark.px);
    vg_free(base.px);
    return ok;
}

/* FontGlyphs._make */
static int vg_make(vg_font *f, int code) {
    WCHAR ch = (WCHAR)VG_CP1252[code];
    const WCHAR *face;
    int weight;
    vg_mask *out = &f->glyph[code];
    if (ch == 0) {
        return VG_NONE;
    }
    if (vg_box(out, &f->sheet, code)) {
        return VG_GAME;
    }
    if (code == 0xA0 && vg_entry(&f->sheet, 0x20) >= 0) {
        f->alias[code] = 0x20;
        return vg_box(out, &f->sheet, 0x20) ? VG_ALIAS : VG_NONE;
    }
    if (code == 0xAD && vg_entry(&f->sheet, '-') >= 0) {
        f->alias[code] = '-';
        return vg_box(out, &f->sheet, '-') ? VG_ALIAS : VG_NONE;
    }
    if (f->gdi == NULL) {
        return VG_NONE;
    }
    if (vg_true_face(f, &face, &weight) && vg_whole(f, face, weight, ch, out)) {
        return VG_TTF;
    }
    if (vg_compose(f, code, out)) {
        return VG_COMPOSED;
    }
    vg_stand_in(f, &face, &weight);
    if (vg_whole(f, face, weight, ch, out)) {
        return VG_STAND_IN;
    }
    if (vg_whole(f, L"Segoe UI", 700, ch, out) || vg_whole(f, L"Segoe UI Symbol", 400, ch, out)) {
        return VG_STAND_IN;
    }
    return VG_NONE;
}

static const vg_mask *vg_glyph(vg_font *f, int code) {
    if (code < 0 || code > 255) {
        return NULL;
    }
    if (f->state[code] == 0) {
        f->state[code] = 1;
        f->source[code] = (unsigned char)vg_make(f, code);
        f->state[code] = 2;
    }
    return (f->state[code] == 2 && f->source[code] != VG_NONE) ? &f->glyph[code] : NULL;
}

/* 1 when the font is ready to make letters. */
static int vg_font_open(vg_font *f, vg_gdi *gdi, const vg_sheet *sheet, int spacing, int burweed) {
    ZeroMemory(f, sizeof *f);
    f->gdi = gdi;
    f->sheet = *sheet;
    f->burweed = burweed;
    if (!vg_measure(&f->m, sheet, spacing) || !vg_box(&f->sheet_h, sheet, 'H')) {
        return 0;
    }
    return 1;
}

static void vg_font_close(vg_font *f) {
    int i;
    for (i = 0; i < 256; ++i) {
        vg_free(f->glyph[i].px);
        f->glyph[i].px = NULL;
    }
    vg_free(f->sheet_h.px);
}
