/* A New Home's Tech screen counter (and the drawing The Lost Children's counter shares: counter_vv2.inc).

   THE SCREEN.  The Tech screen's draw is 0x433B20 (thiscall, the screen in ecx, no arguments): tech_bg.png at
   (0, 0), then the six technologies' cells (x 0x62 / 0x1A0, y 0x36 / 0xBF / 0x148), each at the screen's fade alpha
   ([screen+0x20], a float) while it fades in ([screen+0x1C] <= 3).  Both paths (fading and settled) meet at
   0x43401B, where the screen's seven text widgets are drawn ([screen+0x124] .. [screen+0x13C], vtable slot 0x18,
   no arguments, the last one a tail jump): +0x124 the bottom strip's label at (0x24C, 0x23C), the others the six
   technologies' bars under their pictures.  The Back button is at (5, 0x233) in the bottom strip.

   THE SPOT.  The tan banner across the top of tech_bg.png (about x 45..745, y 3..33) holds nothing: no widget, no
   cell and no button is drawn there (the cells start at y 0x36, the labels and buttons are in the bars and the
   bottom strip).  The counter is centred on the screen's middle (x 400) and on the banner's middle (y 18).

   THE TEXT.  Drawn as the screen's own labels draw theirs: the game's centred text routine 0x4094C0 (thiscall on
   the graphics wrapper [screen+8]: text, centre x, y, colour, font; ret 0x14), in the font of the screen's bottom
   label (the first dword of the resource object [screen+0x18]: A New Home's UI font, the message bar's), white
   (0xFFFFFFFF, the labels' colour), at the screen's fade alpha while it fades in.

   TOO WIDE (the owner's rule: never off the screen).  The text is measured with the game's own measure 0x402160
   (font; text, scale 1.0; ret 8).  Wider than SOL12_MAX_WIDTH (760: 20 pixels in from each edge of the 800-pixel
   screen) it wraps at spaces onto more lines (each centred, one line height 0x402100(font; NULL) apart, the block
   centred on the banner, never above y 2); a single word wider than that is cut to fit; at most SOL12_MAX_LINES
   lines (anything after them is not drawn).  Below the banner is fine (out of a box), off the screen never.

   THE SPLICE.  0x43401B: "mov ecx, [esi+0x124]" (8B 8E 24 01 00 00), the first widget's draw, reached by both
   paths (0x433DA8 jle, 0x433FFD jl and the fall-through).  It becomes a jump to the stub, which draws the counter
   (every register and the flags kept), runs the six stock bytes and goes on at 0x434021.  The three routines it
   calls are checked too (their first 16 bytes the stock ones): a different build of the game installs nothing. */

#define SOL12_MAX_WIDTH 760
#define SOL12_MAX_LINES 4
#define SOL12_LINE_CAP 160
#define SOL12_CENTRE_X 400
#define SOL12_BANNER_MID_Y 18
#define SOL12_TOP_Y 2
#define SOL12_COLOUR 0xFFFFFFFFu

typedef void (__fastcall *sol12_text_fn)(void *wrapper, void *unused, const char *text, int centre_x, int y,
                                         unsigned int colour, void *font);
typedef int (__fastcall *sol12_width_fn)(void *font, void *unused, const char *text, float scale);
typedef int (__fastcall *sol12_height_fn)(void *font, void *unused, const char *text);

typedef struct {
    unsigned int text_centred;          /* thiscall(wrapper; text, centre x, y, colour, font), ret 0x14 */
    unsigned int text_width;            /* thiscall(font; text, scale), ret 8 */
    unsigned int line_height;           /* thiscall(font; text), ret 4: NULL -> one line's height */
} sol12_game;

/* The stock first bytes of the three routines (the same in both games). */
static const unsigned char SOL12_TEXT_STOCK[16] = { 0x53, 0x8B, 0x19, 0x56, 0x8B, 0x74, 0x24, 0x1C, 0x85, 0xF6,
                                                    0x75, 0x07, 0x8B, 0x73, 0x5C, 0x85 };
static const unsigned char SOL12_WIDTH_STOCK[16] = { 0x83, 0xEC, 0x10, 0x55, 0x8B, 0x69, 0x04, 0x56, 0x33, 0xF6,
                                                     0x3B, 0xEE, 0x57, 0x0F, 0x84, 0x9A };
static const unsigned char SOL12_HEIGHT_STOCK[16] = { 0x56, 0x8B, 0x71, 0x04, 0x85, 0xF6, 0x74, 0x2F, 0x8B, 0x06,
                                                      0x8B, 0xCE, 0xFF, 0x10, 0x84, 0xC0 };
/* The site's stock bytes (the same in both games): mov ecx, [esi+0x124]. */
static const unsigned char SOL12_SITE_STOCK[6] = { 0x8B, 0x8E, 0x24, 0x01, 0x00, 0x00 };

/* A routine another companion may have hooked at its start (Render Unicode with In-Game Fonts, started before this
   one, puts a jump over the first bytes of the text and width routines): its stock bytes, or a jump in their
   place, which still answers as the stock routine does (UTF-8 measured and drawn as the game's own text). */
static int sol12_stock_or_hooked(unsigned int va, const unsigned char *stock, int length) {
    static const unsigned char JMP[1] = { 0xE9 };
    return vvfp_site_holds(va, stock, length) || vvfp_site_holds(va, JMP, 1);
}

static int sol12_routines_stock(const sol12_game *g) {
    return sol12_stock_or_hooked(g->text_centred, SOL12_TEXT_STOCK, sizeof SOL12_TEXT_STOCK)
        && sol12_stock_or_hooked(g->text_width, SOL12_WIDTH_STOCK, sizeof SOL12_WIDTH_STOCK)
        && sol12_stock_or_hooked(g->line_height, SOL12_HEIGHT_STOCK, sizeof SOL12_HEIGHT_STOCK);
}

static int sol12_fits(const sol12_game *g, void *font, const char *line) {
    return ((sol12_width_fn)(UINT_PTR)g->text_width)(font, NULL, line, 1.0f) <= SOL12_MAX_WIDTH;
}

/* Splits `text` (no line breaks) into at most SOL12_MAX_LINES lines no wider than SOL12_MAX_WIDTH: at spaces, a
   word too wide alone cut to fit.  The number of lines in `lines`. */
static int sol12_wrap(const sol12_game *g, void *font, const char *text, char lines[][SOL12_LINE_CAP]) {
    int count = 0, i = 0, n = lstrlenA(text);
    while (count < SOL12_MAX_LINES) {
        char *line = lines[count];
        int fit = 0, stop = 0;
        while (i < n && text[i] == ' ') {
            ++i;                                         /* a line never starts with a space */
        }
        if (i >= n) {
            break;
        }
        stop = i;
        for (;;) {                                       /* one more word while the line still fits */
            while (stop < n && text[stop] == ' ') {
                ++stop;
            }
            while (stop < n && text[stop] != ' ') {
                ++stop;
            }
            if (stop - i >= SOL12_LINE_CAP) {
                break;
            }
            memcpy(line, text + i, (size_t)(stop - i));
            line[stop - i] = '\0';
            if (!sol12_fits(g, font, line)) {
                break;
            }
            fit = stop - i;
            if (stop >= n) {
                break;
            }
        }
        if (fit == 0) {
            /* Not even its first word fits: as many of that word's characters as do (at least one). */
            fit = 1;
            while (i + fit < n && text[i + fit] != ' ' && fit + 1 < SOL12_LINE_CAP) {
                memcpy(line, text + i, (size_t)(fit + 1));
                line[fit + 1] = '\0';
                if (!sol12_fits(g, font, line)) {
                    break;
                }
                ++fit;
            }
        }
        memcpy(line, text + i, (size_t)fit);
        line[fit] = '\0';
        i += fit;
        ++count;
    }
    return count;
}

/* Draws the counter on the Tech screen `screen` (A New Home's or The Lost Children's: the same layout). */
static void sol12_draw(const sol12_game *g, unsigned char *screen) {
    char text[512], lines[SOL12_MAX_LINES][SOL12_LINE_CAP], *p;
    unsigned char *resources;
    void *wrapper, *font = NULL;
    unsigned int colour = SOL12_COLOUR;
    int count, height, y, k;
    if (screen == NULL || sol_counter_text(text, sizeof text) <= 0) {
        return;
    }
    for (p = text; *p != '\0'; ++p) {
        if (*p == '\r' || *p == '\n' || *p == '\t') {
            *p = ' ';                                    /* the line breaks are this code's to make */
        }
    }
    wrapper = *(void **)(screen + 0x08);
    if (wrapper == NULL || *(void **)wrapper == NULL) {
        return;
    }
    resources = *(unsigned char **)(screen + 0x18);
    if (resources != NULL) {
        font = *(void **)resources;
    }
    if (font == NULL) {
        font = *(void **)((unsigned char *)*(void **)wrapper + 0x5C);   /* the renderer's default font */
    }
    if (font == NULL || *(void **)((unsigned char *)font + 4) == NULL) {
        return;
    }
    if (*(const int *)(screen + 0x1C) <= 3) {
        /* Fading in: the screen's own alpha, as its cells are drawn. */
        float alpha = *(const float *)(screen + 0x20);
        int a = alpha >= 1.0f ? 255 : alpha <= 0.0f ? 0 : (int)(alpha * 255.0f);
        if (a <= 0) {
            return;
        }
        colour = (colour & 0x00FFFFFFu) | ((unsigned int)a << 24);
    }
    count = sol12_wrap(g, font, text, lines);
    if (count <= 0) {
        return;
    }
    height = ((sol12_height_fn)(UINT_PTR)g->line_height)(font, NULL, NULL);
    if (height <= 0 || height > 100) {
        height = 20;
    }
    y = SOL12_BANNER_MID_Y - (count * height) / 2;
    if (y < SOL12_TOP_Y) {
        y = SOL12_TOP_Y;
    }
    for (k = 0; k < count; ++k) {
        ((sol12_text_fn)(UINT_PTR)g->text_centred)(wrapper, NULL, lines[k], SOL12_CENTRE_X, y + k * height, colour,
                                                   font);
    }
}

/* ---- A New Home ------------------------------------------------------------------------------------------------ */

#define SOL_VV1_SITE 0x0043401Bu            /* mov ecx, [esi+0x124] (8B 8E 24 01 00 00) */
#define SOL_VV1_RESUME 0x00434021u
static const sol12_game SOL_VV1 = { 0x004094C0u, 0x00402160u, 0x00402100u };

static void __cdecl sol_vv1_draw(unsigned char *screen) {
    sol12_draw(&SOL_VV1, screen);
}

/* At SOL_VV1_SITE: esi = the Tech screen. */
static __declspec(naked) void sol_vv1_stub(void) {
    __asm {
        pushfd
        pushad
        push esi
        call sol_vv1_draw
        add esp, 4
        popad
        popfd
        mov ecx, dword ptr [esi + 0x124]
        push SOL_VV1_RESUME
        ret
    }
}

static int sol_counter_install_vv1(void) {
    vvfp_site_write w[1];
    if (!sol12_routines_stock(&SOL_VV1)) {
        return 0;
    }
    vvfp_site_branch(&w[0], SOL_VV1_SITE, sizeof SOL12_SITE_STOCK, SOL12_SITE_STOCK, 0xE9, (const void *)sol_vv1_stub);
    return vvfp_install_sites(w, 1);
}
