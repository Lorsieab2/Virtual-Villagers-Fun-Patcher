/* The Tech screen counter of The Secret City, The Tree of Life and New Believers (one engine family), and the
   helper counter_vv4.inc and counter_vv5.inc share (sol345_*).

   HOW.  Each game's Tech screen draw (VV3 0x4649C0, VV4 0x43E640, VV5 0x440F80) draws the screen's picture, the
   technologies' bars and the sunbeam / particles, then sets its bottom label's text and returns.  The counter
   splices that function's own epilogue (its pops, `add esp` and `ret`, which nothing branches into: checked over
   every rel8 / rel32 branch and absolute pointer of each stock executable) with a jump to a stub here: the stub
   draws the counter, then runs the same epilogue.  So the counter is drawn every time the Tech screen is drawn,
   over its picture, before its controls (the buttons and labels draw themselves after the screen).

   THE TEXT is drawn by the game's own routines, in the game's own font and colour:
     * the draw wrapper the game's own screens use for a line of text (VV3 0x40A060, VV4 0x409BD0, VV5 0x409EA0:
       `mov ecx, [ecx]; jmp <draw>`, thiscall(wrapper; text, x, y, ARGB colour, font) ret 0x14), on the wrapper
       the game's renderer getter returns (VV3 0x408940, VV4 0x408130, VV5 0x4080C0: `mov eax, [global]; ret`);
     * the font is the UI font the Tech screen's own bottom label (its tech points) is built with: the first dword
       of the game's resource singleton (VV3 0x42F740, VV4 0x44DA20, VV5 0x450D40), read exactly as the game's own
       screens read it (`call <getter>; mov eax, [eax]`);
     * the colour is the one the Tech screen's own text uses on that background (each game's sol345_game);
     * the width is measured with the game's width routine (VV3 0x402230, VV4 0x402430, VV5 0x4023E0,
       thiscall(font; text, float scale) ret 8) and the line height read with its line-height routine (VV3
       0x4021C0, VV4 0x402500, VV5 0x4024B0, thiscall(font; text) ret 4; NULL text = one line).  With the Unicode
       Text patch these routines are the patched ones, so a translation in UTF-8 is measured and drawn as the rest
       of the game's text is.

   TOO WIDE (a longer translation).  The counter has its own free strip of the screen (each game's sol345_game).
   Text that fits is centred in it.  Text that does not is wrapped at a space onto a second line just below (which
   may leave the strip's box, never the screen); a part still too wide for the strip is cut at a character and ends
   in "...".  Nothing is ever drawn past the strip's left or right edge, so nothing runs off the screen.

   SAFETY.  One site per game, written only when it and every routine called hold their stock bytes (all or
   nothing).  The draw and width routines themselves are not byte-checked: the Unicode Text patch may have
   spliced them before this companion starts; they are reached through the checked wrapper or called as they are.
   The 256-villager population mode moves the villager tables only, never this code or these globals. */

typedef struct {
    unsigned int site;              /* the epilogue spliced */
    int site_len;
    const unsigned char *site_stock;
    unsigned int renderer_get;      /* cdecl: the draw wrapper ([0] = the draw context) */
    const unsigned char *renderer_stock;
    unsigned int resources_get;     /* cdecl: the resource singleton; +0 the UI font */
    const unsigned char *resources_stock;
    unsigned int draw_left;         /* thiscall(wrapper; text, x, y, ARGB, font) ret 0x14 */
    const unsigned char *draw_left_stock;
    unsigned int width;             /* thiscall(font; text, float scale) ret 8 -> pixels */
    unsigned int line_height;       /* thiscall(font; text) ret 4 -> pixels */
    const unsigned char *line_height_stock;
    unsigned int colour_va;         /* the colour global, or 0: `colour` */
    unsigned int colour;
    int left, right, y;             /* the counter's strip: x from left to right, top at y */
    int screen_h;
} sol345_game;

#define SOL345_TEXT_CAP 256

typedef void *(__cdecl *sol345_get_fn)(void);
typedef void (__fastcall *sol345_draw_fn)(void *wrapper, void *edx, const char *text, int x, int y,
                                          unsigned int argb, void *font);
typedef int (__fastcall *sol345_width_fn)(void *font, void *edx, const char *text, float scale);
typedef int (__fastcall *sol345_height_fn)(void *font, void *edx, const char *text);

static int sol345_width(const sol345_game *g, void *font, const char *text) {
    return ((sol345_width_fn)(UINT_PTR)g->width)(font, NULL, text, 1.0f);
}

/* `text` (len bytes) cut to fit `room` pixels: all of it when it fits, else the longest start that fits with "..."
   after it (never splitting a UTF-8 character), into `out`.  Its width. */
static int sol345_clip(const sol345_game *g, void *font, const char *text, int len, int room, char *out) {
    int w;
    if (len > SOL345_TEXT_CAP - 4) {
        len = SOL345_TEXT_CAP - 4;
    }
    memcpy(out, text, (size_t)len);
    out[len] = '\0';
    w = sol345_width(g, font, out);
    if (w <= room) {
        return w;
    }
    while (len > 0) {
        --len;
        while (len > 0 && ((unsigned char)out[len] & 0xC0) == 0x80) {
            --len;                          /* the rest of a UTF-8 character */
        }
        while (len > 0 && out[len - 1] == ' ') {
            --len;
        }
        lstrcpyA(out + len, "...");
        w = sol345_width(g, font, out);
        if (w <= room) {
            return w;
        }
    }
    out[0] = '\0';
    return 0;
}

/* One line, centred in the strip. */
static void sol345_line(const sol345_game *g, void *wrapper, void *font, unsigned int argb, const char *text, int w,
                        int y) {
    int x = g->left + (g->right - g->left - w) / 2;
    if (text[0] == '\0') {
        return;
    }
    if (x < g->left) {
        x = g->left;
    }
    ((sol345_draw_fn)(UINT_PTR)g->draw_left)(wrapper, NULL, text, x, y, argb, font);
}

/* Draws the counter (each game's stub, on the game thread, inside the Tech screen's draw). */
static void sol345_draw(const sol345_game *g) {
    char text[SOL345_TEXT_CAP], first[SOL345_TEXT_CAP], second[SOL345_TEXT_CAP];
    void *wrapper, *font, **resources;
    unsigned int argb;
    int len, room = g->right - g->left, w, cut, best = -1, i, lh;
    len = sol_counter_text(text, sizeof text);
    if (len <= 0) {
        return;
    }
    wrapper = ((sol345_get_fn)(UINT_PTR)g->renderer_get)();
    resources = (void **)((sol345_get_fn)(UINT_PTR)g->resources_get)();
    if (wrapper == NULL || resources == NULL || (font = resources[0]) == NULL) {
        return;
    }
    argb = g->colour_va != 0 ? *(const unsigned int *)(UINT_PTR)g->colour_va : g->colour;
    w = sol345_width(g, font, text);
    if (w <= room) {
        sol345_line(g, wrapper, font, argb, text, w, g->y);
        return;
    }
    /* Too wide: break at the last space whose first part fits. */
    for (i = 1; i < len; ++i) {
        if (text[i] == ' ') {
            memcpy(first, text, (size_t)i);
            first[i] = '\0';
            if (sol345_width(g, font, first) > room) {
                break;
            }
            best = i;
        }
    }
    lh = ((sol345_height_fn)(UINT_PTR)g->line_height)(font, NULL, NULL);
    if (best < 0 || lh <= 0 || g->y + 2 * lh > g->screen_h) {
        w = sol345_clip(g, font, text, len, room, first);
        sol345_line(g, wrapper, font, argb, first, w, g->y);
        return;
    }
    memcpy(first, text, (size_t)best);
    first[best] = '\0';
    sol345_line(g, wrapper, font, argb, first, sol345_width(g, font, first), g->y);
    for (cut = best; cut < len && text[cut] == ' '; ++cut) {
    }
    w = sol345_clip(g, font, text + cut, len - cut, room, second);
    sol345_line(g, wrapper, font, argb, second, w, g->y + lh);
}

/* Splices `g`'s epilogue with a jump to `stub` once it and every routine it calls hold their stock bytes. */
static int sol345_install(const sol345_game *g, void *stub) {
    vvfp_site_write site;
    if (!vvfp_site_holds(g->renderer_get, g->renderer_stock, 6)
        || !vvfp_site_holds(g->resources_get, g->resources_stock, 7)
        || !vvfp_site_holds(g->draw_left, g->draw_left_stock, 7)
        || !vvfp_site_holds(g->line_height, g->line_height_stock, 6)) {
        return 0;
    }
    vvfp_site_branch(&site, g->site, g->site_len, g->site_stock, 0xE9, stub);
    return vvfp_install_sites(&site, 1);
}

/* ---- The Secret City ------------------------------------------------------------------------------------------ */

/* 0x464C1D: pop edi / pop esi / add esp, 0x24 / ret -- the Tech screen draw's epilogue, after its bottom label's
   text is set (0x464C14). */
static const unsigned char SOL3_SITE[6] = { 0x5F, 0x5E, 0x83, 0xC4, 0x24, 0xC3 };
static const unsigned char SOL3_RENDERER[6] = { 0xA1, 0xA8, 0x34, 0x4B, 0x00, 0xC3 };      /* mov eax, [0x4B34A8] */
static const unsigned char SOL3_RESOURCES[7] = { 0x6A, 0xFF, 0x68, 0xDB, 0x9C, 0x47, 0x00 };
static const unsigned char SOL3_DRAW[7] = { 0x8B, 0x09, 0xE9, 0x69, 0xFC, 0xFF, 0xFF };     /* jmp 0x409CD0 */
static const unsigned char SOL3_HEIGHT[6] = { 0x56, 0x8B, 0x71, 0x04, 0x85, 0xF6 };

/* The counter: the right part of the top banner (sand), right of the screen's title (string 0xF3, centred at
   x 400, y 6), in the title's colour 0xFF002245. */
static const sol345_game SOL_VV3 = {
    0x464C1Du, 6, SOL3_SITE,
    0x408940u, SOL3_RENDERER,
    0x42F740u, SOL3_RESOURCES,
    0x40A060u, SOL3_DRAW,
    0x402230u,
    0x4021C0u, SOL3_HEIGHT,
    0, 0xFF002245u,
    500, 735, 8,
    600,
};

static void __cdecl sol345_frame_vv3(void) {
    sol345_draw(&SOL_VV3);
}

static __declspec(naked) void sol345_stub_vv3(void) {
    __asm {
        pushad
        call sol345_frame_vv3
        popad
        pop edi
        pop esi
        add esp, 0x24
        ret
    }
}

static int sol_counter_install_vv3(void) {
    return sol345_install(&SOL_VV3, (void *)sol345_stub_vv3);
}
