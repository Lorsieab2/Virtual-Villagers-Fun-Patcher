/* colour_fonts.inc -- colour letters in every colour-font format: COLR/CPAL, CBDT/CBLC, sbix and SVG.

   runtime_glyphs.inc draws COLR/CPAL layers itself (rg_colr).  Noto Color Emoji is CBDT (bitmaps), Apple's and
   some others' are sbix, and Twemoji-style fonts are SVG: GDI draws those in one colour.  For a face that holds
   one of these tables the text is drawn by Direct2D and DirectWrite instead, with
   D2D1_DRAW_TEXT_OPTIONS_ENABLE_COLOR_FONT, into a 32-bit DIB, and its pixels are copied into the letter's
   canvas in their own colours with the text's alpha (UNICODE_SPEC section 3, "Colour emoji"; the path the Fish
   and Plant Fun Patcher uses).  Direct2D and DirectWrite are loaded from System32 on first use
   (LOAD_LIBRARY_SEARCH_SYSTEM32); without them (or on any error) cf_draw answers 0 and the letter is drawn as
   before, in one colour by GDI.  The COM objects are called through their vtables, so no Direct2D header or
   library is needed.  Standalone: only <windows.h>. */

typedef struct cf_guid {
    unsigned long a;
    unsigned short b, c;
    unsigned char d[8];
} cf_guid;

static const cf_guid CF_IID_D2D_FACTORY = {0x06152247u, 0x6f50, 0x465a, {0x92, 0x45, 0x11, 0x8b, 0xfd, 0x3b, 0x60, 0x07}};
static const cf_guid CF_IID_DWRITE_FACTORY = {0xb859ee5au, 0xd838, 0x4b5b, {0xa2, 0xe8, 0x1a, 0xdc, 0x7d, 0x93, 0xdb, 0x48}};

typedef struct cf_colour { float r, g, b, a; } cf_colour;
typedef struct cf_point { float x, y; } cf_point;
typedef struct cf_target_props {
    unsigned int type, format, alpha_mode;
    float dpi_x, dpi_y;
    unsigned int usage, min_level;
} cf_target_props;
typedef struct cf_line {
    unsigned int length, trailing, newline;
    float height, baseline;
    BOOL trimmed;
} cf_line;

/* vtable slots (d2d1.h, dwrite.h) */
#define CF_RELEASE 2
#define CF_F_CREATE_DC_TARGET 16          /* ID2D1Factory::CreateDCRenderTarget */
#define CF_RT_CREATE_BRUSH 8              /* ID2D1RenderTarget::CreateSolidColorBrush */
#define CF_RT_DRAW_LAYOUT 28              /* ::DrawTextLayout */
#define CF_RT_TEXT_AA 34                  /* ::SetTextAntialiasMode */
#define CF_RT_CLEAR 47
#define CF_RT_BEGIN 48
#define CF_RT_END 49
#define CF_DCRT_BIND 57                   /* ID2D1DCRenderTarget::BindDC */
#define CF_DW_CREATE_FORMAT 15            /* IDWriteFactory::CreateTextFormat */
#define CF_DW_CREATE_LAYOUT 18            /* ::CreateTextLayout */
#define CF_TL_LINE_METRICS 59             /* IDWriteTextLayout::GetLineMetrics */
#define CF_FORMAT_B8G8R8A8 87
#define CF_ALPHA_PREMULTIPLIED 1
#define CF_TEXT_AA_GRAYSCALE 2
#define CF_ENABLE_COLOR_FONT 4
#define CF_SEARCH_SYSTEM32 0x00000800

#define CF_SLOT(obj, slot) ((*(void ***)(obj))[slot])

typedef HRESULT (WINAPI *cf_d2d_create_fn)(unsigned int, const cf_guid *, const void *, void **);
typedef HRESULT (WINAPI *cf_dw_create_fn)(unsigned int, const cf_guid *, void **);
typedef ULONG (WINAPI *cf_release_fn)(void *);
typedef HRESULT (WINAPI *cf_create_target_fn)(void *, const cf_target_props *, void **);
typedef HRESULT (WINAPI *cf_create_brush_fn)(void *, const cf_colour *, const void *, void **);
typedef void (WINAPI *cf_text_aa_fn)(void *, unsigned int);
typedef HRESULT (WINAPI *cf_bind_fn)(void *, HDC, const RECT *);
typedef void (WINAPI *cf_begin_fn)(void *);
typedef void (WINAPI *cf_clear_fn)(void *, const cf_colour *);
typedef void (WINAPI *cf_draw_layout_fn)(void *, cf_point, void *, void *, unsigned int);
typedef HRESULT (WINAPI *cf_end_fn)(void *, unsigned __int64 *, unsigned __int64 *);
typedef HRESULT (WINAPI *cf_create_format_fn)(void *, const wchar_t *, void *, unsigned int, unsigned int,
                                              unsigned int, float, const wchar_t *, void **);
typedef HRESULT (WINAPI *cf_create_layout_fn)(void *, const wchar_t *, unsigned int, void *, float, float, void **);
typedef HRESULT (WINAPI *cf_line_metrics_fn)(void *, cf_line *, unsigned int, unsigned int *);

static struct {
    int tried, ready;
    void *dwrite, *target, *brush;
} cf;

static void cf_release(void *obj) {
    if (obj != NULL) {
        ((cf_release_fn)CF_SLOT(obj, CF_RELEASE))(obj);
    }
}

/* Direct2D and DirectWrite, loaded once from System32: 0 when this Windows has not got them. */
static int cf_start(void) {
    HMODULE d2d1, dwrite;
    cf_d2d_create_fn d2d_create;
    cf_dw_create_fn dw_create;
    void *factory = NULL;
    cf_target_props props;
    cf_colour white = {1.0f, 1.0f, 1.0f, 1.0f};
    if (cf.tried) {
        return cf.ready;
    }
    cf.tried = 1;
    d2d1 = LoadLibraryExW(L"d2d1.dll", NULL, CF_SEARCH_SYSTEM32);
    dwrite = LoadLibraryExW(L"dwrite.dll", NULL, CF_SEARCH_SYSTEM32);
    if (d2d1 == NULL || dwrite == NULL) {
        return 0;
    }
    d2d_create = (cf_d2d_create_fn)(UINT_PTR)GetProcAddress(d2d1, "D2D1CreateFactory");
    dw_create = (cf_dw_create_fn)(UINT_PTR)GetProcAddress(dwrite, "DWriteCreateFactory");
    if (d2d_create == NULL || dw_create == NULL) {
        return 0;
    }
    if (d2d_create(0, &CF_IID_D2D_FACTORY, NULL, &factory) < 0 || factory == NULL) {
        return 0;
    }
    if (dw_create(0, &CF_IID_DWRITE_FACTORY, &cf.dwrite) < 0 || cf.dwrite == NULL) {
        cf_release(factory);
        return 0;
    }
    ZeroMemory(&props, sizeof props);
    props.format = CF_FORMAT_B8G8R8A8;
    props.alpha_mode = CF_ALPHA_PREMULTIPLIED;
    props.dpi_x = props.dpi_y = 96.0f;
    if (((cf_create_target_fn)CF_SLOT(factory, CF_F_CREATE_DC_TARGET))(factory, &props, &cf.target) < 0
        || cf.target == NULL) {
        cf_release(factory);
        return 0;
    }
    cf_release(factory);                  /* the target keeps it */
    ((cf_text_aa_fn)CF_SLOT(cf.target, CF_RT_TEXT_AA))(cf.target, CF_TEXT_AA_GRAYSCALE);
    if (((cf_create_brush_fn)CF_SLOT(cf.target, CF_RT_CREATE_BRUSH))(cf.target, &white, NULL, &cf.brush) < 0
        || cf.brush == NULL) {
        return 0;
    }
    cf.ready = 1;
    return 1;
}

/* Does the font selected in `dc` hold a colour table other than COLR: CBDT/CBLC (bitmaps), sbix or SVG? */
static int cf_has_bitmap_colour(HDC dc) {
    static const DWORD TABLES[3] = {0x54444243u /* 'CBDT' */, 0x78696273u /* 'sbix' */, 0x20475653u /* 'SVG ' */};
    int i;
    for (i = 0; i < 3; ++i) {
        if (GetFontData(dc, TABLES[i], 0, NULL, 0) != GDI_ERROR) {
            return 1;
        }
    }
    return 0;
}

/* `text` (n UTF-16 units) drawn in `face` at `ppem` pixels (its em) by Direct2D with colour fonts on, into the
   canvas px (w x h, 0xAARRGGBB straight alpha, the caller cleared it), the pen at column ox and the first line's
   baseline at row `base`.  1 when drawn (*colour: some pixel is not white ink); 0 when nothing could be drawn. */
static int cf_draw(const WCHAR *face, int weight, int ppem, const WCHAR *text, int n, int w, int h, int ox, int base,
                   unsigned int *px, int *colour) {
    void *format = NULL, *layout = NULL;
    cf_line lines[2];
    unsigned int count = 0;
    cf_colour clear = {0.0f, 0.0f, 0.0f, 0.0f};
    cf_point origin;
    RECT rect;
    BITMAPINFO bi;
    void *bits = NULL;
    HBITMAP bmp;
    HDC dc;
    HGDIOBJ old;
    int x, y, ok = 0;
    if (w <= 0 || h <= 0 || n <= 0 || ppem < 2 || !cf_start()) {
        return 0;
    }
    ZeroMemory(&bi, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = w;
    bi.bmiHeader.biHeight = -h;                       /* top-down */
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    dc = CreateCompatibleDC(NULL);
    if (dc == NULL) {
        return 0;
    }
    bmp = CreateDIBSection(dc, &bi, DIB_RGB_COLORS, &bits, NULL, 0);
    if (bmp == NULL || bits == NULL) {
        if (bmp != NULL) {
            DeleteObject(bmp);
        }
        DeleteDC(dc);
        return 0;
    }
    old = SelectObject(dc, bmp);
    ZeroMemory(bits, (size_t)w * (size_t)h * 4);
    if (((cf_create_format_fn)CF_SLOT(cf.dwrite, CF_DW_CREATE_FORMAT))(
            cf.dwrite, face, NULL, (unsigned int)weight, 0, 5, (float)ppem, L"en-us", &format) >= 0 && format != NULL
        && ((cf_create_layout_fn)CF_SLOT(cf.dwrite, CF_DW_CREATE_LAYOUT))(
               cf.dwrite, text, (unsigned int)n, format, 100000.0f, 100000.0f, &layout) >= 0 && layout != NULL
        && ((cf_line_metrics_fn)CF_SLOT(layout, CF_TL_LINE_METRICS))(layout, lines, 2, &count) >= 0 && count >= 1) {
        rect.left = 0;
        rect.top = 0;
        rect.right = w;
        rect.bottom = h;
        origin.x = (float)ox;
        origin.y = (float)base - lines[0].baseline;
        if (((cf_bind_fn)CF_SLOT(cf.target, CF_DCRT_BIND))(cf.target, dc, &rect) >= 0) {
            ((cf_begin_fn)CF_SLOT(cf.target, CF_RT_BEGIN))(cf.target);
            ((cf_clear_fn)CF_SLOT(cf.target, CF_RT_CLEAR))(cf.target, &clear);
            ((cf_draw_layout_fn)CF_SLOT(cf.target, CF_RT_DRAW_LAYOUT))(cf.target, origin, layout, cf.brush,
                                                                      CF_ENABLE_COLOR_FONT);
            ok = ((cf_end_fn)CF_SLOT(cf.target, CF_RT_END))(cf.target, NULL, NULL) >= 0;
            GdiFlush();
        }
    }
    cf_release(layout);
    cf_release(format);
    if (ok) {
        const unsigned char *src = (const unsigned char *)bits;
        *colour = 0;
        for (y = 0; y < h; ++y) {
            for (x = 0; x < w; ++x) {
                const unsigned char *p = src + ((size_t)y * (size_t)w + (size_t)x) * 4;
                unsigned int a = p[3], r, g, b;
                if (a == 0) {
                    continue;
                }
                /* premultiplied B, G, R, A -> straight 0xAARRGGBB */
                r = (p[2] * 255u + a / 2) / a;
                g = (p[1] * 255u + a / 2) / a;
                b = (p[0] * 255u + a / 2) / a;
                if (r > 255) r = 255;
                if (g > 255) g = 255;
                if (b > 255) b = 255;
                /* white ink has B = G = R = A; any other colour is the font's own */
                if (a >= 16 && (p[0] + 16 < a || p[1] + 16 < a || p[2] + 16 < a)) {
                    *colour = 1;
                }
                px[y * w + x] = (a << 24) | (r << 16) | (g << 8) | b;
            }
        }
    }
    SelectObject(dc, old);
    DeleteObject(bmp);
    DeleteDC(dc);
    return ok;
}
