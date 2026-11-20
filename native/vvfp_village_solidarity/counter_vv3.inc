/* The Tech screen counter and its "?" button of The Secret City, The Tree of Life and New Believers (one engine
   family), and the helper counter_vv4.inc and counter_vv5.inc share (sol345_*).

   THE COUNTER.  Each game's Tech screen draw (VV3 0x4649C0, VV4 0x43E640, VV5 0x440F80) draws the screen's picture,
   the technologies' bars and the sunbeam / particles, then sets its bottom label's text and returns.  The counter
   splices that function's own epilogue (its pops, `add esp` and `ret`, which nothing branches into) with a jump to a
   stub here: the stub draws the counter, then runs the same epilogue.  So it is drawn every time the Tech screen is,
   over its picture, before its controls (the buttons draw themselves after the screen).

   THE FONT (the owner, 2026-11-18: "the same in-game font the Tech screen itself uses for its own text"): the
   screen's title ("Technologies") and its labels are made with no font of their own (font argument 0), so they draw
   in the draw context's current font, [ctx+0x5C] -- ldwBurweed27 in all three games.  The counter is drawn in that
   font by the game's own one-line draw wrapper (VV3 0x40A060, VV4 0x409BD0, VV5 0x409EA0: `mov ecx, [ecx]; jmp
   <draw>`, thiscall(wrapper; text, x, y, ARGB colour, font) ret 0x14) on the wrapper the renderer getter returns
   (VV3 0x408940, VV4 0x408130, VV5 0x4080C0), measured with the game's width and line-height routines, and resized
   to fit its spot (the owner allows it: sol_draw_scaled).  The colour is the screen's own for text on that
   background: the title's dark blue (0xFF002245) on The Secret City's sand banner, the bottom label's (white) on
   the dark carved frame of the other two.

   THE "?" BUTTON is the technologies' own: the same picture (VV3 image 0x5A "info_button.png", VV4 0xEB
   "tech_info_btn.png", VV5 0xCD "btn_tech_question.png", fetched from the game's image manager as the screen fetches
   them), the same constructor, the same "?" label in the same three colours, attached to the screen as they are --
   made once in the screen's constructor (a splice before its technologies' loop, or after it where the Origins
   companion returns to the stock code), so the game draws it, gives it its hover look and sends its click to the
   screen's slot 3 like theirs.  It stands at the right end of the counter's strip; the counter is centred in the
   rest.  Its click (id SOL345_BUTTON_ID) shows the help in the same message box the technologies' "?" open
   (constructor (text, 0, 0), the modal loop (screen, 0), the destructor; their sound first), so its OK returns to the
   Tech screen exactly as theirs does.  The box does not wrap, so the help is wrapped here in the box's own font (the
   resource singleton's first font) to SOL345_POPUP_WIDTH pixels; Scrolling Popups (when ticked) scrolls a box taller
   than the screen, and without it the box is cut to SOL345_POPUP_LINES lines.

   THE SLOT.  The screen's vtable slot 3 is replaced (a pointer in the table, written like a site): our "?" shows the
   help and returns as a stock "?" does (al 0, ret 8); every other message goes on to the stock handler's address --
   through the Origins companion's jump at its start when that is there.

   SAFETY.  Every site (the epilogue, the constructor point, the slot) is written only when each holds its stock bytes
   and every routine called holds its own (all or nothing).  The draw and width routines are not byte-checked: the
   Unicode Text patch may have spliced them; they are reached through the checked wrapper or called as they are.  No
   debug output. */

typedef struct {
    unsigned int site;              /* the draw's epilogue spliced */
    int site_len;
    const unsigned char *site_stock;
    unsigned int renderer_get;      /* cdecl: the draw wrapper ([0] = the draw context) */
    const unsigned char *renderer_stock;
    unsigned int resources_get;     /* cdecl: the resource singleton; +0 the UI font (the message box's) */
    const unsigned char *resources_stock;
    unsigned int draw_left;         /* thiscall(wrapper; text, x, y, ARGB, font) ret 0x14 */
    const unsigned char *draw_left_stock;
    unsigned int width;             /* thiscall(font; text, float scale) ret 8 -> pixels */
    unsigned int line_height;       /* thiscall(font; text) ret 4 -> pixels */
    const unsigned char *line_height_stock;
    unsigned int colour_va;         /* the colour global, or 0: `colour` */
    unsigned int colour;
    int left, right, y;             /* the counter's strip: x from left to right, its middle at y */
    int screen_w, screen_h;
    /* The "?" button, as the screen makes its technologies' own. */
    unsigned int op_new;            /* cdecl(size) */
    unsigned int images_get;        /* cdecl: the image manager */
    unsigned int image_get;         /* thiscall(manager; id) -> the picture */
    int image_id;
    int button_w, button_h;         /* the picture's frame */
    unsigned int button_new;        /* thiscall(button; id, picture, x, y, parent, 0) ret 0x18 */
    unsigned int button_label;      /* thiscall(button; text, colour, hover, pressed, 0) ret 0x14 */
    unsigned int label_colours;     /* three globals: colour, hover, pressed */
    unsigned int question_mark;     /* the screen's own "?" string */
    unsigned int button_extra;      /* thiscall(button; 3, 1) ret 8 as The Tree of Life makes its own, or 0 */
    unsigned int add_child;         /* thiscall(screen; child) ret 4 */
    /* The help: the technologies' message box and its sound. */
    unsigned int box_new;           /* thiscall(box; text, 0, 0) ret 0xC */
    unsigned int box_run;           /* thiscall(box; parent, 0) ret 8 */
    unsigned int box_free;          /* thiscall(box) */
    unsigned int sound;             /* thiscall(sounds; id) ret 4 */
    unsigned int sounds;            /* the sound player */
    int sound_id;
    /* The constructor point and the slot. */
    unsigned int make_site;
    int make_len;
    const unsigned char *make_stock;
    unsigned int slot;              /* the vtable entry */
    unsigned int handler;           /* its stock value */
} sol345_game;

#define SOL345_TEXT_CAP 256
#define SOL345_BUTTON_ID 0x534F     /* the "?" beside the counter (stock ids are small; Origins' is 13) */
#define SOL345_BUTTON_GAP 6
#define SOL345_STRIP_HEIGHT 26      /* the counter's text, pixels tall at most */
#define SOL345_POPUP_LINES 24
#define SOL345_POPUP_BYTES 4096

typedef void *(__cdecl *sol345_get_fn)(void);
typedef void (__fastcall *sol345_draw_fn)(void *wrapper, void *edx, const char *text, int x, int y,
                                          unsigned int argb, void *font);
typedef int (__fastcall *sol345_width_fn)(void *font, void *edx, const char *text, float scale);
typedef int (__fastcall *sol345_height_fn)(void *font, void *edx, const char *text);
typedef void *(__cdecl *sol345_new_fn)(unsigned int size);
typedef void *(__fastcall *sol345_image_fn)(void *manager, void *edx, int id);
typedef void *(__fastcall *sol345_button_fn)(void *button, void *edx, int id, void *picture, int x, int y,
                                             void *parent, int zero);
typedef void (__fastcall *sol345_label_fn)(void *button, void *edx, const char *text, unsigned int colour,
                                           unsigned int hover, unsigned int pressed, int zero);
typedef void (__fastcall *sol345_extra_fn)(void *button, void *edx, int a, int b);
typedef void (__fastcall *sol345_child_fn)(void *screen, void *edx, void *child);
typedef void *(__fastcall *sol345_box_fn)(void *box, void *edx, const char *text, int a, int b);
typedef void (__fastcall *sol345_run_fn)(void *box, void *edx, void *parent, int zero);
typedef void (__fastcall *sol345_free_fn)(void *box, void *edx);
typedef void (__fastcall *sol345_sound_fn)(void *sounds, void *edx, int id);

static int sol345_width(const sol345_game *g, void *font, const char *text) {
    return ((sol345_width_fn)(UINT_PTR)g->width)(font, NULL, text, 1.0f);
}

static int sol345_height(const sol345_game *g, void *font) {
    int h = ((sol345_height_fn)(UINT_PTR)g->line_height)(font, NULL, NULL);
    return h <= 0 || h > 100 ? 20 : h;
}

/* A usable font: one with its glyphs loaded. */
static int sol345_font_ok(void *font) {
    return font != NULL && *(void **)((unsigned char *)font + 4) != NULL;
}

/* The "?" button's spot: the right end of the strip, centred on its middle. */
static void sol345_button_spot(const sol345_game *g, int *x, int *y) {
    *x = g->right - g->button_w;
    *y = g->y - g->button_h / 2;
    if (*y < 0) {
        *y = 0;
    }
}

/* Draws the counter (each game's stub, on the game thread, inside the Tech screen's draw): in the screen's own font,
   resized to fit the strip left of the "?". */
static void sol345_draw(const sol345_game *g) {
    char text[SOL345_TEXT_CAP], *p;
    void *wrapper, *font;
    unsigned char *ctx;
    unsigned int argb;
    int bx, by, room, w, h, sw, sh, x, y;
    float scale;
    if (sol_counter_text(text, sizeof text) <= 0) {
        return;
    }
    for (p = text; *p != '\0'; ++p) {
        if (*p == '\r' || *p == '\n' || *p == '\t') {
            *p = ' ';
        }
    }
    wrapper = ((sol345_get_fn)(UINT_PTR)g->renderer_get)();
    ctx = wrapper != NULL ? *(unsigned char **)wrapper : NULL;
    font = ctx != NULL ? *(void **)(ctx + 0x5C) : NULL;
    if (!sol345_font_ok(font)) {
        return;
    }
    argb = g->colour_va != 0 ? *(const unsigned int *)(UINT_PTR)g->colour_va : g->colour;
    sol345_button_spot(g, &bx, &by);
    room = bx - SOL345_BUTTON_GAP - g->left;
    w = sol345_width(g, font, text);
    h = sol345_height(g, font);
    scale = sol_fit_scale(w, h, room, SOL345_STRIP_HEIGHT);
    sw = (int)((float)w * scale + 0.5f);
    sh = (int)((float)h * scale + 0.5f);
    if (sw > room) {
        /* Even at half size too wide (a long translation): cut at the strip, never past it. */
        sw = room;
    }
    x = g->left + (room - sw) / 2;
    y = g->y - sh / 2;
    if (y < 0) {
        y = 0;
    }
    if (sw < (int)((float)w * scale + 0.5f)) {
        /* The cut: drawn into the strip only (the draw's own clip, put back at once). */
        int clip[4];
        memcpy(clip, ctx + 0x60, sizeof clip);
        ((int *)(ctx + 0x60))[0] = g->left;
        ((int *)(ctx + 0x60))[2] = g->left + room;
        sol_draw_scaled(wrapper, g->draw_left, 0, font, text, w, h, x, y, scale, argb);
        memcpy(ctx + 0x60, clip, sizeof clip);
        return;
    }
    sol_draw_scaled(wrapper, g->draw_left, 0, font, text, w, h, x, y, scale, argb);
}

/* In the screen's constructor: the "?" button, made and attached exactly as the technologies' own. */
static void sol345_make_button(const sol345_game *g, unsigned char *screen) {
    const unsigned int *colours = (const unsigned int *)(UINT_PTR)g->label_colours;
    void *button, *manager, *picture;
    int x, y;
    if (screen == NULL) {
        return;
    }
    button = ((sol345_new_fn)(UINT_PTR)g->op_new)(0x14);
    manager = ((sol345_get_fn)(UINT_PTR)g->images_get)();
    if (button == NULL || manager == NULL) {
        return;
    }
    picture = ((sol345_image_fn)(UINT_PTR)g->image_get)(manager, NULL, g->image_id);
    sol345_button_spot(g, &x, &y);
    button = ((sol345_button_fn)(UINT_PTR)g->button_new)(button, NULL, SOL345_BUTTON_ID, picture, x, y, screen, 0);
    if (button == NULL) {
        return;
    }
    ((sol345_label_fn)(UINT_PTR)g->button_label)(button, NULL, (const char *)(UINT_PTR)g->question_mark, colours[0],
                                                 colours[1], colours[2], 0);
    if (g->button_extra != 0) {
        ((sol345_extra_fn)(UINT_PTR)g->button_extra)(button, NULL, 3, 1);
    }
    ((sol345_child_fn)(UINT_PTR)g->add_child)(screen, NULL, button);
}

/* `text` wrapped at spaces to `width` pixels in `font` into lines joined by "\n" in `out` (`cap` bytes), at most
   `max_lines` lines (the last cut short with "..." when more would follow).  Its line count. */
static int sol345_wrap(const sol345_game *g, void *font, const char *text, int width, char *out, int cap,
                       int max_lines) {
    char line[SOL345_TEXT_CAP];
    int n = lstrlenA(text), i = 0, used = 0, count = 0;
    out[0] = '\0';
    while (i < n && count < max_lines) {
        int start, stop, fit = 0;
        while (i < n && (text[i] == ' ' || text[i] == '\n' || text[i] == '\r')) {
            ++i;
        }
        if (i >= n) {
            break;
        }
        start = stop = i;
        for (;;) {
            int k;
            while (stop < n && text[stop] == ' ') {
                ++stop;
            }
            while (stop < n && text[stop] != ' ' && text[stop] != '\n') {
                ++stop;
            }
            k = stop - start;
            if (k >= SOL345_TEXT_CAP - 4) {
                break;
            }
            memcpy(line, text + start, (size_t)k);
            line[k] = '\0';
            if (fit > 0 && sol345_width(g, font, line) > width) {
                break;
            }
            fit = k;
            if (stop >= n || text[stop] == '\n') {
                break;
            }
        }
        if (fit == 0) {
            fit = stop - start < SOL345_TEXT_CAP - 4 ? stop - start : SOL345_TEXT_CAP - 4;
        }
        memcpy(line, text + start, (size_t)fit);
        line[fit] = '\0';
        i = start + fit;
        if (count == max_lines - 1 && i < n) {
            lstrcpyA(line + (fit > SOL345_TEXT_CAP - 8 ? SOL345_TEXT_CAP - 8 : fit), "...");
        }
        if (used + lstrlenA(line) + 2 > cap) {
            break;
        }
        if (used > 0) {
            out[used++] = '\n';
        }
        lstrcpyA(out + used, line);
        used += lstrlenA(line);
        ++count;
    }
    return count;
}

/* The "?" clicked: the help in the technologies' own message box, its title above it. */
static void sol345_help(const sol345_game *g, unsigned char *screen) {
    static char body[SOL345_POPUP_BYTES], page[SOL345_POPUP_BYTES + 256];
    /* The box object (at most 0x50 bytes in the three games; the stock code keeps it on its stack): room to spare. */
    __declspec(align(16)) unsigned char box[0x400];
    void **resources = (void **)((sol345_get_fn)(UINT_PTR)g->resources_get)();
    void *font = resources != NULL ? resources[0] : NULL;
    const char *title = sol_help_title(), *text = sol_help_text();
    int width = g->screen_w - 200;
    if (!sol345_font_ok(font) || title == NULL || text == NULL) {
        return;
    }
    sol345_wrap(g, font, text, width, body, sizeof body,
                GetModuleHandleA("VVFP Scrolling Popups.dll") != NULL ? 200 : SOL345_POPUP_LINES);
    lstrcpynA(page, title, 128);
    lstrcatA(page, "\n\n");
    lstrcatA(page, body);
    ((sol345_sound_fn)(UINT_PTR)g->sound)((void *)(UINT_PTR)g->sounds, NULL, g->sound_id);
    memset(box, 0, sizeof box);
    ((sol345_box_fn)(UINT_PTR)g->box_new)(box, NULL, page, 0, 0);
    ((sol345_run_fn)(UINT_PTR)g->box_run)(box, NULL, screen, 0);
    ((sol345_free_fn)(UINT_PTR)g->box_free)(box, NULL);
}

static const unsigned char SOL345_SEH[3] = { 0x6A, 0xFF, 0x68 };            /* push -1; push <handler> */
static const unsigned char SOL345_VTABLE[2] = { 0xC7, 0x01 };              /* the box's destructor: mov [ecx], <vtable> */

/* Splices `g`'s epilogue, constructor point and slot once every one and every routine it calls hold their stock
   bytes. */
static int sol345_install(const sol345_game *g, void *draw_stub, void *make_stub, void *slot_stub) {
    vvfp_site_write w[3];
    unsigned int slot = (unsigned int)(UINT_PTR)slot_stub;
    unsigned char handler[4];
    memcpy(handler, &g->handler, 4);
    if (!vvfp_site_holds(g->renderer_get, g->renderer_stock, 6)
        || !vvfp_site_holds(g->resources_get, g->resources_stock, 7)
        || !vvfp_site_holds(g->draw_left, g->draw_left_stock, 7)
        || !vvfp_site_holds(g->line_height, g->line_height_stock, 6)
        || !vvfp_site_holds(g->button_new, SOL345_SEH, 3)
        || !vvfp_site_holds(g->box_new, SOL345_SEH, 3)
        || !vvfp_site_holds(g->box_free, SOL345_VTABLE, 2)
        || !vvfp_site_holds(g->question_mark, (const unsigned char *)"?", 2)) {
        return 0;
    }
    vvfp_site_branch(&w[0], g->site, g->site_len, g->site_stock, 0xE9, draw_stub);
    vvfp_site_branch(&w[1], g->make_site, g->make_len, g->make_stock, 0xE9, make_stub);
    vvfp_site_bytes(&w[2], g->slot, 4, handler, (const unsigned char *)&slot);
    return vvfp_install_sites(w, 3);
}

/* ---- The Secret City ------------------------------------------------------------------------------------------ */

/* 0x464C1D: pop edi / pop esi / add esp, 0x24 / ret -- the Tech screen draw's epilogue, after its bottom label's
   text is set (0x464C14). */
static const unsigned char SOL3_SITE[6] = { 0x5F, 0x5E, 0x83, 0xC4, 0x24, 0xC3 };
static const unsigned char SOL3_RENDERER[6] = { 0xA1, 0xA8, 0x34, 0x4B, 0x00, 0xC3 };      /* mov eax, [0x4B34A8] */
static const unsigned char SOL3_RESOURCES[7] = { 0x6A, 0xFF, 0x68, 0xDB, 0x9C, 0x47, 0x00 };
static const unsigned char SOL3_DRAW[7] = { 0x8B, 0x09, 0xE9, 0x69, 0xFC, 0xFF, 0xFF };     /* jmp 0x409CD0 */
static const unsigned char SOL3_HEIGHT[6] = { 0x56, 0x8B, 0x71, 0x04, 0x85, 0xF6 };
/* 0x4652A8: mov dword ptr [esp+0x10], 1 -- in the constructor, after the title is attached (0x4652A0), before the
   technologies' loop (the Origins companion's own splice, 0x46547D, returns from the constructor itself). */
static const unsigned char SOL3_MAKE[8] = { 0xC7, 0x44, 0x24, 0x10, 0x01, 0x00, 0x00, 0x00 };

/* The counter: the right part of the top banner (sand), right of the screen's title (string 0xF3, centred at x 400,
   y 6), in the title's colour 0xFF002245. */
static const sol345_game SOL_VV3 = {
    0x464C1Du, 6, SOL3_SITE,
    0x408940u, SOL3_RENDERER,
    0x42F740u, SOL3_RESOURCES,
    0x40A060u, SOL3_DRAW,
    0x402230u,
    0x4021C0u, SOL3_HEIGHT,
    0, 0xFF002245u,
    500, 735, 20,
    800, 600,
    0x46EC93u, 0x42E9D0u, 0x42E8A0u, 0x5A, 37, 28,
    0x4019F0u, 0x401620u, 0x4B1FF8u, 0x47F288u, 0, 0x40C1F0u,
    0x41C7A0u, 0x401AF0u, 0x41C2F0u, 0x424110u, 0x581A38u, 0x64,
    0x4652A8u, 8, SOL3_MAKE,
    0x49E840u, 0x465640u,
};

static void __cdecl sol345_frame_vv3(void) {
    sol345_draw(&SOL_VV3);
}

static void __cdecl sol345_make_vv3(unsigned char *screen) {
    sol345_make_button(&SOL_VV3, screen);
}

static void __cdecl sol345_help_vv3(unsigned char *screen) {
    sol345_help(&SOL_VV3, screen);
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

/* At 0x4652A8: esi = the Tech screen being built. */
static __declspec(naked) void sol345_make_stub_vv3(void) {
    __asm {
        pushfd
        pushad
        push esi
        call sol345_make_vv3
        add esp, 4
        popad
        popfd
        mov dword ptr [esp + 0x10], 1
        push 0x004652B0
        ret
    }
}

static __declspec(naked) void sol345_slot_vv3(void) {
    __asm {
        cmp dword ptr [esp + 4], 8
        jne stock
        cmp dword ptr [esp + 8], SOL345_BUTTON_ID
        jne stock
        pushad
        push ecx
        call sol345_help_vv3
        add esp, 4
        popad
        xor eax, eax
        ret 8
    stock:
        push 0x00465640
        ret
    }
}

static int sol_counter_install_vv3(void) {
    return sol345_install(&SOL_VV3, (void *)sol345_stub_vv3, (void *)sol345_make_stub_vv3, (void *)sol345_slot_vv3);
}
