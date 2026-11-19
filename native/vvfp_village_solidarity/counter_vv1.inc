/* A New Home's Tech screen counter and its "?" button (and the code The Lost Children's shares: counter_vv2.inc).

   THE SCREEN.  The Tech screen (vtable 0x4819EC, built once while the game loads: 0x4347E0, called from 0x41B873)
   draws in 0x433B20 (thiscall, the screen in ecx, no arguments): tech_bg.png at (0, 0), then the six technologies'
   cells (x 0x62 / 0x1A0, y 0x36 / 0xBF / 0x148), each at the screen's fade alpha ([screen+0x20], a float) while it
   fades in ([screen+0x1C] <= 3).  Both paths meet at 0x43401B, where its text widgets are drawn ([screen+0x124] ..
   [screen+0x13C]).  Its buttons are children the game draws itself: Back (id 1) at (5, 0x233); the six research
   buttons (ids 3..8); the six technologies' "?" buttons (ids 9..14: 0x4019B0 with "info_button.png", label "?" in
   black with the grey 0x555555 hover colours, 0x4015B0; e.g. (0x11A, 0x8E)); the Origins "Upgrades" button (id 2,
   (138, 563)) when that row is on.  Clicks reach the screen's slot 3, 0x435AB0 (thiscall; 8 = a button, its id;
   ret 8).  A "?" button there calls 0x4345E0, which builds the technology's text and shows the game's own info
   popup: the sound 0x48 (0x431470 on [screen+0x14]), the popup 0x4275B0(text, 0, 0, 0, 0) on a local object, the
   modal loop 0x401AB0(screen, 0), the popup's destructor 0x427050.

   THE FONT AND COLOUR.  The screen's own words -- its title "Technologies" (widget +0x140, string 0x8C, centred on
   x 0x190 at y 6) and the six technologies' labels (+0x128 .. +0x13C) -- are made with no font of their own, so they
   draw in the renderer's current font ([renderer+0x5C], 0x408310: the game's default font).  The counter is drawn
   in that font, in the title's colour (0xFF002245, set by 0x40BB00 at 0x435815), at the font's own size: the
   game's text draw 0x409160 blits every glyph at scale 1.0 (its width routine's scale only scales the measuring),
   so there is no scaled draw to use; a counter too wide wraps instead (below).

   THE SPOT.  The tan banner across the top (about x 45..745, y 3..33), right of the title: the counter is centred
   at x 615 on the banner's middle (y 18), within x 475..755 (seen live 2026-11-18).  The "?" button is the
   technologies' own (the same picture, label, colours, size and hover look, made by the same calls), 6 pixels right
   of the counter's widest line and centred on it (moved there at each draw, as the text is measured then); it would
   go just left of the counter if the right did not fit on the 800-pixel screen (it always does: the counter ends at
   x 755 at most).

   TOO WIDE (the owner's rule: never off the screen).  The counter is measured with the game's own measure 0x402160
   (font; text, scale 1.0; ret 8).  Wider than SOL12_MAX_WIDTH it wraps at spaces onto more lines (one line height
   0x402100(font; NULL) apart, the block centred on the banner, never above y 2); a single word wider than that is
   cut to fit; at most SOL12_MAX_LINES lines.

   THE POPUP.  The "?" shows the core's sol_help_title() and sol_help_text() (translatable) in the same popup the
   technologies' "?" open, exactly as 0x4345E0 opens it (its sound, its popup, its modal loop, its destructor), so
   closing it (its OK) returns to the Tech screen as theirs does.  The popup sizes itself to its text (in the UI font,
   the first dword of the resource object [screen+0x18]) and does not wrap, so the text is wrapped here: at spaces to
   SOL12_POPUP_WIDTH pixels, "\n" kept as a line break (a paragraph break, "\n\n", as one empty line), the title on its
   own line above a blank one.  If the lines are more than SOL12_POPUP_HEIGHT pixels tall, they are shown on more
   pages, one popup after the other, each with the title and the game's OK; the popup is never taller than the
   screen.

   THE SPLICES (all or none; every routine called is checked first, its first bytes the stock ones):
     0x43401B  mov ecx, [esi+0x124] (8B 8E 24 01 00 00): the draw -- the counter drawn, the "?" placed beside it;
               on at 0x434021.
     0x435846  mov ecx, [esi+0x18]; push 0x8D (8B 4E 18 68 8D 00 00 00): in the screen's constructor, after the
               title is attached -- the "?" button made and attached (id SOL12_BUTTON_ID); on at 0x43584E.
     0x4819F8  the screen's vtable slot 3 (B0 5A 43 00 = 0x435AB0): the "?" button's click shows the popup and
               returns as a stock "?" does (al 0, ret 8); every other message goes on to 0x435AB0 unchanged (and
               through Origins' handler when Origins has jumped it).  Nothing else is written. */

#define SOL12_MAX_WIDTH 280            /* x 475..755: right of the centred title (seen live, 2026-11-18) */
#define SOL12_MAX_LINES 4
#define SOL12_LINE_CAP 160
#define SOL12_CENTRE_X 615
#define SOL12_BANNER_MID_Y 18
#define SOL12_TOP_Y 2
#define SOL12_SCREEN_W 800
#define SOL12_SCREEN_MARGIN 4
#define SOL12_BUTTON_GAP 6
#define SOL12_BUTTON_ID 0x534F         /* the "?" beside the counter; stock ids are 1..14, Origins' 2 */
#define SOL12_POPUP_WIDTH 520          /* the popup's text, pixels wide (the popup adds 60) */
#define SOL12_POPUP_HEIGHT 400         /* the popup's text, pixels tall per page (the popup adds its OK and 60) */
#define SOL12_POPUP_LINES 96
#define SOL12_POPUP_BYTES 4096
#define SOL12_COLOUR 0xFF002245u        /* the title's colour (both games) */

typedef void (__fastcall *sol12_text_fn)(void *wrapper, void *unused, const char *text, int centre_x, int y,
                                         unsigned int colour, void *font);
typedef int (__fastcall *sol12_width_fn)(void *font, void *unused, const char *text, float scale);
typedef int (__fastcall *sol12_height_fn)(void *font, void *unused, const char *text);
typedef void *(__cdecl *sol12_new_fn)(unsigned int size);
typedef void *(__fastcall *sol12_button_fn)(void *button, void *unused, int id, const char *picture, int x, int y,
                                            void *parent, int zero);
typedef void (__fastcall *sol12_label_fn)(void *button, void *unused, const char *text, unsigned int colour,
                                          unsigned int hover, unsigned int pressed, int zero);
typedef void (__fastcall *sol12_child_fn)(void *screen, void *unused, void *child);
typedef void *(__fastcall *sol12_popup_fn)(void *popup, void *unused, const char *text, int a, int b, const char *c,
                                           const char *d);
typedef void (__fastcall *sol12_run_fn)(void *popup, void *unused, void *parent, int zero);
typedef void (__fastcall *sol12_free_fn)(void *popup, void *unused);
typedef void (__fastcall *sol12_sound_fn)(void *sounds, void *unused, int id);
typedef void (__fastcall *sol12_place_fn)(void *button, void *unused, int x, int y);
typedef int (__fastcall *sol12_size_fn)(void *button, void *unused);

typedef struct {
    unsigned int text_centred;          /* thiscall(wrapper; text, centre x, y, colour, font), ret 0x14 */
    unsigned int text_width;            /* thiscall(font; text, scale), ret 8 */
    unsigned int line_height;           /* thiscall(font; text), ret 4: NULL -> one line's height */
    unsigned int op_new;                /* cdecl(size): the game's operator new */
    unsigned int button_new;            /* thiscall(button; id, picture, x, y, parent, 0), ret 0x18 */
    unsigned int button_label;          /* thiscall(button; text, colour, hover, pressed, 0), ret 0x14 */
    unsigned int add_child;             /* thiscall(screen; child), ret 4 */
    unsigned int popup_new;             /* thiscall(popup; text, 0, 0, 0, 0), ret 0x14 */
    unsigned int popup_run;             /* thiscall(popup; parent, 0), ret 8: the modal loop */
    unsigned int popup_free;            /* thiscall(popup): its destructor */
    unsigned int sound;                 /* thiscall(sounds; id), ret 4 */
    int sound_id;                       /* the technologies' "?" sound */
    unsigned int picture;               /* "info_button.png" */
    unsigned int label;                 /* "?" */
    unsigned int handler;               /* the screen's stock slot 3 */
} sol12_game;

/* The stock first bytes of the routines called (the same in both games where noted). */
static const unsigned char SOL12_TEXT_STOCK[16] = { 0x53, 0x8B, 0x19, 0x56, 0x8B, 0x74, 0x24, 0x1C, 0x85, 0xF6,
                                                    0x75, 0x07, 0x8B, 0x73, 0x5C, 0x85 };
static const unsigned char SOL12_WIDTH_STOCK[16] = { 0x83, 0xEC, 0x10, 0x55, 0x8B, 0x69, 0x04, 0x56, 0x33, 0xF6,
                                                     0x3B, 0xEE, 0x57, 0x0F, 0x84, 0x9A };
static const unsigned char SOL12_HEIGHT_STOCK[16] = { 0x56, 0x8B, 0x71, 0x04, 0x85, 0xF6, 0x74, 0x2F, 0x8B, 0x06,
                                                      0x8B, 0xCE, 0xFF, 0x10, 0x84, 0xC0 };
static const unsigned char SOL12_NEW_STOCK[6] = { 0x6A, 0x01, 0xFF, 0x74, 0x24, 0x08 };
static const unsigned char SOL12_LABEL_STOCK[8] = { 0x8B, 0x41, 0x10, 0x8B, 0x54, 0x24, 0x10, 0x89 };
static const unsigned char SOL12_CHILD_STOCK[6] = { 0x56, 0x57, 0x6A, 0x08, 0x8B, 0xF1 };
static const unsigned char SOL12_RUN_STOCK[8] = { 0x53, 0x8A, 0x5C, 0x24, 0x0C, 0x56, 0x57, 0x8B };
static const unsigned char SOL12_SOUND_STOCK[4] = { 0x8B, 0x81, 0x58, 0x06 };       /* A New Home's */
static const unsigned char SOL12_SOUND_STOCK_VV2[4] = { 0x8B, 0x81, 0x5C, 0x06 };   /* The Lost Children's */
static const unsigned char SOL12_SEH_STOCK[3] = { 0x6A, 0xFF, 0x68 };               /* push -1; push <handler> */
static const char SOL12_PICTURE[] = "info_button.png";
static const char SOL12_LABEL[] = "?";
/* The draw site's stock bytes (the same in both games): mov ecx, [esi+0x124]. */
static const unsigned char SOL12_SITE_STOCK[6] = { 0x8B, 0x8E, 0x24, 0x01, 0x00, 0x00 };

static void *g_sol12_screen;            /* the Tech screen the button was made for */
static void *g_sol12_button;            /* its "?" button (the screen owns it, as it owns its own) */
static int g_sol12_button_x = -1, g_sol12_button_y = -1;

/* A routine another companion may have hooked at its start (Render Unicode with In-Game Fonts, started before this
   one, puts a jump over the first bytes of the text and width routines): its stock bytes, or a jump in their
   place, which still answers as the stock routine does (UTF-8 measured and drawn as the game's own text). */
static int sol12_stock_or_hooked(unsigned int va, const unsigned char *stock, int length) {
    static const unsigned char JMP[1] = { 0xE9 };
    return vvfp_site_holds(va, stock, length) || vvfp_site_holds(va, JMP, 1);
}

static int sol12_routines_stock(const sol12_game *g, const unsigned char *sound_stock) {
    return sol12_stock_or_hooked(g->text_centred, SOL12_TEXT_STOCK, sizeof SOL12_TEXT_STOCK)
        && sol12_stock_or_hooked(g->text_width, SOL12_WIDTH_STOCK, sizeof SOL12_WIDTH_STOCK)
        && sol12_stock_or_hooked(g->line_height, SOL12_HEIGHT_STOCK, sizeof SOL12_HEIGHT_STOCK)
        && vvfp_site_holds(g->op_new, SOL12_NEW_STOCK, sizeof SOL12_NEW_STOCK)
        && vvfp_site_holds(g->button_new, SOL12_SEH_STOCK, sizeof SOL12_SEH_STOCK)
        && sol12_stock_or_hooked(g->button_label, SOL12_LABEL_STOCK, sizeof SOL12_LABEL_STOCK)
        && vvfp_site_holds(g->add_child, SOL12_CHILD_STOCK, sizeof SOL12_CHILD_STOCK)
        && sol12_stock_or_hooked(g->popup_new, SOL12_SEH_STOCK, sizeof SOL12_SEH_STOCK)
        && vvfp_site_holds(g->popup_run, SOL12_RUN_STOCK, sizeof SOL12_RUN_STOCK)
        && vvfp_site_holds(g->popup_free, SOL12_SEH_STOCK, sizeof SOL12_SEH_STOCK)
        && vvfp_site_holds(g->sound, sound_stock, 4)
        && vvfp_site_holds(g->picture, (const unsigned char *)SOL12_PICTURE, sizeof SOL12_PICTURE)
        && vvfp_site_holds(g->label, (const unsigned char *)SOL12_LABEL, sizeof SOL12_LABEL);
}

static int sol12_width(const sol12_game *g, void *font, const char *line) {
    return ((sol12_width_fn)(UINT_PTR)g->text_width)(font, NULL, line, 1.0f);
}

static int sol12_line_height(const sol12_game *g, void *font) {
    int height = ((sol12_height_fn)(UINT_PTR)g->line_height)(font, NULL, NULL);
    return height <= 0 || height > 100 ? 20 : height;
}

/* A usable font: one with its glyphs loaded. */
static int sol12_font_ok(void *font) {
    return font != NULL && *(void **)((unsigned char *)font + 4) != NULL;
}

/* Splits `text` (no line breaks) into at most `max_lines` lines no wider than `width` pixels: at spaces, a word too
   wide alone cut to fit (never inside a UTF-8 character).  The number of lines in `lines`. */
static int sol12_wrap(const sol12_game *g, void *font, const char *text, int width, char lines[][SOL12_LINE_CAP],
                      int max_lines) {
    int count = 0, i = 0, n = lstrlenA(text);
    while (count < max_lines) {
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
            if (sol12_width(g, font, line) > width) {
                break;
            }
            fit = stop - i;
            if (stop >= n) {
                break;
            }
        }
        if (fit == 0) {
            /* Not even its first word fits: as many of that word's characters as do (at least one). */
            int next;
            fit = 1;
            while (fit < SOL12_LINE_CAP - 1 && i + fit < n && ((unsigned char)text[i + fit] & 0xC0) == 0x80) {
                ++fit;                                   /* the rest of a UTF-8 character */
            }
            for (;;) {
                next = fit + 1;
                while (i + next < n && ((unsigned char)text[i + next] & 0xC0) == 0x80) {
                    ++next;
                }
                if (i + fit >= n || text[i + fit] == ' ' || next >= SOL12_LINE_CAP) {
                    break;
                }
                memcpy(line, text + i, (size_t)next);
                line[next] = '\0';
                if (sol12_width(g, font, line) > width) {
                    break;
                }
                fit = next;
            }
        }
        memcpy(line, text + i, (size_t)fit);
        line[fit] = '\0';
        i += fit;
        ++count;
    }
    return count;
}

/* The font the Tech screen's own words are drawn in: the renderer's current font (its title and labels have none
   of their own).  NULL when not usable. */
static void *sol12_screen_font(unsigned char *screen, void **wrapper_out) {
    void *wrapper = screen != NULL ? *(void **)(screen + 0x08) : NULL;
    void *font;
    *wrapper_out = wrapper;
    if (wrapper == NULL || *(void **)wrapper == NULL) {
        return NULL;
    }
    font = *(void **)((unsigned char *)*(void **)wrapper + 0x5C);
    return sol12_font_ok(font) ? font : NULL;
}

/* The counter's lines on `screen` and its widest line's width; the number of lines (0: nothing to show). */
static int sol12_counter_lines(const sol12_game *g, void *font, char lines[][SOL12_LINE_CAP], int *widest) {
    char text[512], *p;
    int count, k;
    *widest = 0;
    if (sol_counter_text(text, sizeof text) <= 0) {
        return 0;
    }
    for (p = text; *p != '\0'; ++p) {
        if (*p == '\r' || *p == '\n' || *p == '\t') {
            *p = ' ';                                    /* the line breaks are this code's to make */
        }
    }
    count = sol12_wrap(g, font, text, SOL12_MAX_WIDTH, lines, SOL12_MAX_LINES);
    for (k = 0; k < count; ++k) {
        int w = sol12_width(g, font, lines[k]);
        if (w > *widest) {
            *widest = w;
        }
    }
    return count;
}

/* The "?" button beside the counter: right of its widest line, centred on its lines; left of it if the right does
   not fit on the screen. */
static void sol12_place_button(unsigned char *screen, int widest, int top, int block_height) {
    void *button = g_sol12_button;
    void **vt;
    int w, h, x, y;
    if (button == NULL || screen != g_sol12_screen) {
        return;
    }
    vt = *(void ***)button;
    w = ((sol12_size_fn)vt[3])(button, NULL);
    h = ((sol12_size_fn)vt[4])(button, NULL);
    if (w <= 0 || w > 200) {
        w = 28;
    }
    if (h <= 0 || h > 200) {
        h = 28;
    }
    x = SOL12_CENTRE_X + (widest + 1) / 2 + SOL12_BUTTON_GAP;
    if (x + w > SOL12_SCREEN_W - SOL12_SCREEN_MARGIN) {
        x = SOL12_CENTRE_X - widest / 2 - SOL12_BUTTON_GAP - w;
    }
    y = top + block_height / 2 - h / 2;
    if (y < 0) {
        y = 0;
    }
    if (x != g_sol12_button_x || y != g_sol12_button_y) {
        ((sol12_place_fn)vt[1])(button, NULL, x, y);
        g_sol12_button_x = x;
        g_sol12_button_y = y;
    }
}

/* Draws the counter on the Tech screen `screen` (A New Home's or The Lost Children's: the same layout) and puts the
   "?" beside it. */
static void sol12_draw(const sol12_game *g, unsigned char *screen) {
    char lines[SOL12_MAX_LINES][SOL12_LINE_CAP];
    void *wrapper, *font;
    unsigned int colour = SOL12_COLOUR;
    int count, height, y, k, widest;
    font = sol12_screen_font(screen, &wrapper);
    if (font == NULL) {
        return;
    }
    count = sol12_counter_lines(g, font, lines, &widest);
    if (count <= 0) {
        return;
    }
    height = sol12_line_height(g, font);
    y = SOL12_BANNER_MID_Y - (count * height) / 2;
    if (y < SOL12_TOP_Y) {
        y = SOL12_TOP_Y;
    }
    sol12_place_button(screen, widest, y, count * height);
    if (*(const int *)(screen + 0x1C) <= 3) {
        /* Fading in: the screen's own alpha, as its cells are drawn. */
        float alpha = *(const float *)(screen + 0x20);
        int a = alpha >= 1.0f ? 255 : alpha <= 0.0f ? 0 : (int)(alpha * 255.0f);
        if (a <= 0) {
            return;
        }
        colour = (colour & 0x00FFFFFFu) | ((unsigned int)a << 24);
    }
    for (k = 0; k < count; ++k) {
        ((sol12_text_fn)(UINT_PTR)g->text_centred)(wrapper, NULL, lines[k], SOL12_CENTRE_X, y + k * height, colour,
                                                   font);
    }
}

/* In the screen's constructor: the "?" button, made and attached exactly as the technologies' own (its picture,
   its "?" in black with the grey hover colours), and placed at the counter's spot until the first draw places it
   beside the counter's text. */
static void sol12_make_button(const sol12_game *g, unsigned char *screen) {
    void *button = ((sol12_new_fn)(UINT_PTR)g->op_new)(0x14);
    if (button == NULL) {
        return;
    }
    button = ((sol12_button_fn)(UINT_PTR)g->button_new)(button, NULL, SOL12_BUTTON_ID, (const char *)(UINT_PTR)g->picture,
                                                         SOL12_CENTRE_X + SOL12_MAX_WIDTH / 2 + SOL12_BUTTON_GAP,
                                                         SOL12_BANNER_MID_Y - 14, screen, 0);
    if (button == NULL) {
        return;
    }
    ((sol12_label_fn)(UINT_PTR)g->button_label)(button, NULL, (const char *)(UINT_PTR)g->label, 0xFF000000u,
                                                0xFF555555u, 0xFF555555u, 0);
    ((sol12_child_fn)(UINT_PTR)g->add_child)(screen, NULL, button);
    g_sol12_screen = screen;
    g_sol12_button = button;
    g_sol12_button_x = -1;
    g_sol12_button_y = -1;
}

/* Appends `line` and a line break to the page in `out` (`cap` bytes, `*len` used); 0 when it does not fit. */
static int sol12_append(char *out, int cap, int *len, const char *line) {
    int n = lstrlenA(line);
    if (*len + n + 2 > cap) {
        return 0;
    }
    if (*len > 0) {
        out[(*len)++] = '\n';
    }
    memcpy(out + *len, line, (size_t)n);
    *len += n;
    out[*len] = '\0';
    return 1;
}

/* One page of the help in the game's own info popup, as 0x4345E0 shows a technology's. */
static void sol12_show_page(const sol12_game *g, unsigned char *screen, const char *text) {
    /* The popup object (0x54 bytes in both games; the stock code keeps it on its stack): room to spare. */
    __declspec(align(16)) unsigned char popup[0x200];
    memset(popup, 0, sizeof popup);
    ((sol12_popup_fn)(UINT_PTR)g->popup_new)(popup, NULL, text, 0, 0, NULL, NULL);
    ((sol12_run_fn)(UINT_PTR)g->popup_run)(popup, NULL, screen, 0);
    ((sol12_free_fn)(UINT_PTR)g->popup_free)(popup, NULL);
}

/* The "?" clicked: the help, wrapped to the popup and paged to the screen. */
static void sol12_help(const sol12_game *g, unsigned char *screen) {
    static char lines[SOL12_POPUP_LINES][SOL12_LINE_CAP];
    static char page[SOL12_POPUP_BYTES];
    static char paragraph[SOL12_POPUP_BYTES];
    const char *title = sol_help_title(), *body = sol_help_text();
    unsigned char *resources = *(unsigned char **)(screen + 0x18);
    void *font = resources != NULL ? *(void **)resources : NULL;
    void *sounds = *(void **)(screen + 0x14);
    int count = 0, per_page, first, len, height, i;
    if (!sol12_font_ok(font) || title == NULL || body == NULL) {
        return;
    }
    /* The body's lines: each "\n"-separated piece wrapped on its own ("\n\n" leaves one empty line). */
    for (i = 0; body[i] != '\0' && count < SOL12_POPUP_LINES;) {
        int n = 0, got;
        while (body[i] != '\0' && body[i] != '\n' && n < SOL12_POPUP_BYTES - 1) {
            paragraph[n++] = body[i] == '\r' || body[i] == '\t' ? ' ' : body[i];
            ++i;
        }
        paragraph[n] = '\0';
        if (body[i] == '\n') {
            ++i;
        }
        got = sol12_wrap(g, font, paragraph, SOL12_POPUP_WIDTH, lines + count, SOL12_POPUP_LINES - count);
        if (got == 0) {
            lines[count][0] = '\0';
            got = 1;                                     /* an empty piece: an empty line */
        }
        count += got;
    }
    while (count > 0 && lines[count - 1][0] == '\0') {
        --count;
    }
    height = sol12_line_height(g, font);
    per_page = SOL12_POPUP_HEIGHT / height - 2;          /* the title and the blank line under it */
    if (per_page < 1) {
        per_page = 1;
    }
    if (sounds != NULL) {
        ((sol12_sound_fn)(UINT_PTR)g->sound)(sounds, NULL, g->sound_id);
    }
    for (first = 0; first < count || first == 0; first += per_page) {
        char title_lines[2][SOL12_LINE_CAP];
        int k, t = sol12_wrap(g, font, title, SOL12_POPUP_WIDTH, title_lines, 2);
        len = 0;
        page[0] = '\0';
        for (k = 0; k < t; ++k) {
            (void)sol12_append(page, sizeof page, &len, title_lines[k]);
        }
        (void)sol12_append(page, sizeof page, &len, "");
        for (k = first; k < count && k < first + per_page; ++k) {
            if (!sol12_append(page, sizeof page, &len, lines[k])) {
                break;
            }
        }
        sol12_show_page(g, screen, page);
        if (count == 0) {
            break;
        }
    }
}

/* ---- A New Home ------------------------------------------------------------------------------------------------ */

#define SOL_VV1_SITE 0x0043401Bu            /* mov ecx, [esi+0x124] (8B 8E 24 01 00 00) */
#define SOL_VV1_RESUME 0x00434021u
#define SOL_VV1_MAKE_SITE 0x00435846u       /* mov ecx, [esi+0x18]; push 0x8D (8B 4E 18 68 8D 00 00 00) */
#define SOL_VV1_MAKE_RESUME 0x0043584Eu
#define SOL_VV1_SLOT 0x004819F8u            /* the Tech screen's vtable slot 3: 0x435AB0 */
static const unsigned char SOL_VV1_MAKE_STOCK[8] = { 0x8B, 0x4E, 0x18, 0x68, 0x8D, 0x00, 0x00, 0x00 };
static const unsigned char SOL_VV1_SLOT_STOCK[4] = { 0xB0, 0x5A, 0x43, 0x00 };
static const sol12_game SOL_VV1 = {
    0x004094C0u, 0x00402160u, 0x00402100u,              /* text, width, line height */
    0x0044AF03u, 0x004019B0u, 0x004015B0u, 0x0040AB80u, /* new, button, label, attach */
    0x004275B0u, 0x00401AB0u, 0x00427050u,              /* popup, modal loop, destructor */
    0x00431470u, 0x48,                                  /* sound, the "?" sound */
    0x00481A3Cu, 0x00459270u,                           /* "info_button.png", "?" */
    0x00435AB0u,                                        /* the stock slot 3 */
};

static void __cdecl sol_vv1_draw(unsigned char *screen) {
    sol12_draw(&SOL_VV1, screen);
}

static void __cdecl sol_vv1_make(unsigned char *screen) {
    sol12_make_button(&SOL_VV1, screen);
}

static void __cdecl sol_vv1_help(unsigned char *screen) {
    sol12_help(&SOL_VV1, screen);
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

/* At SOL_VV1_MAKE_SITE: esi = the Tech screen being built. */
static __declspec(naked) void sol_vv1_make_stub(void) {
    __asm {
        pushfd
        pushad
        push esi
        call sol_vv1_make
        add esp, 4
        popad
        popfd
        mov ecx, dword ptr [esi + 0x18]
        push 0x8D
        push SOL_VV1_MAKE_RESUME
        ret
    }
}

/* The screen's slot 3 (thiscall: message, id; ret 8): the "?" beside the counter, else the stock handler. */
static __declspec(naked) void sol_vv1_slot(void) {
    __asm {
        cmp dword ptr [esp + 4], 8
        jne stock
        cmp dword ptr [esp + 8], SOL12_BUTTON_ID
        jne stock
        pushad
        push ecx
        call sol_vv1_help
        add esp, 4
        popad
        xor eax, eax
        ret 8
    stock:
        push 0x00435AB0
        ret
    }
}

static int sol_counter_install_vv1(void) {
    vvfp_site_write w[3];
    unsigned int slot = (unsigned int)(UINT_PTR)sol_vv1_slot;
    if (!sol12_routines_stock(&SOL_VV1, SOL12_SOUND_STOCK)) {
        return 0;
    }
    vvfp_site_branch(&w[0], SOL_VV1_SITE, sizeof SOL12_SITE_STOCK, SOL12_SITE_STOCK, 0xE9, (const void *)sol_vv1_stub);
    vvfp_site_branch(&w[1], SOL_VV1_MAKE_SITE, sizeof SOL_VV1_MAKE_STOCK, SOL_VV1_MAKE_STOCK, 0xE9,
                     (const void *)sol_vv1_make_stub);
    vvfp_site_bytes(&w[2], SOL_VV1_SLOT, sizeof SOL_VV1_SLOT_STOCK, SOL_VV1_SLOT_STOCK, (const unsigned char *)&slot);
    return vvfp_install_sites(w, 3);
}
