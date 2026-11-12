/* VVFP Scrolling Popups -- "Scrolling Popups" (vv3_scrolling_popups, vv4_scrolling_popups, vv5_scrolling_popups).

   WHAT (the owner, 2026-11-12: "Let the patcher handle it").  A popup whose text is taller than the screen allows,
   or has a line wider than its box (an unbroken long word), gets a vertical and/or a horizontal scrollbar drawn
   with the game's own scrollbar pictures, so the player can read all of it: the mouse wheel, the arrows, dragging
   the knob and clicking the track scroll it.  A popup whose text fits is drawn exactly as the game draws it (the
   same single call, nothing else).  Stage 1: the island-event dialog of The Secret City, The Tree of Life and New
   Believers (native/shared/scroll_popup.h has the rows; more popups and games are rows to add).  The dialog's text
   field keeps the game's 2000-byte size.

   A WORD WIDER THAN THE BOX (a long unbroken word).  The game's justified paragraph never places such a word: it
   backs off to an empty line and tries it again, for ever, so the stock game hangs on it.  The constructor's
   measures of the dialog's texts (scroll_popup.h measure_sites) call the companion too, which gives the paragraph
   the width of the widest word when that is wider than the box; the draw wraps at that same width and the box
   scrolls sideways.

   HOW.  After every site's stock bytes (and the instructions they rely on) are checked -- all of them, or none
   (native/shared/install_sites.h) -- three calls in the game's code call this companion instead:
     * the dialog constructor's `call sizer` (scroll_popup.h size_site): the panel's height is capped to the screen
       less a margin, in the call's argument and in edi, the register the constructor pushed it from and centres the
       panel's contents by (the game then centres the panel and puts the buttons at its bottom, as always);
     * the dialog draw's `call justify` (draw_site): the body text is measured; when it fits the box (the panel's
       bottom less the room the dialog keeps for its buttons) the stock call is made unchanged; otherwise the text
       is drawn under a clip rectangle set to the box (ctx+0x60, restored after), moved by the scroll position, and
       the scrollbars are drawn with the game's own pictures (VerticalScrollTrack tiled under a clip, the knob,
       Up/DownArrowButton; WideSlider2 and sliderhandle for the horizontal bar);
     * the event pump's `call` of the mouse dispatcher (mouse_site): an event on a scrollbar of the dialog drawn this
       moment (or a knob drag in progress) is used here and not passed on; every other event goes to the game's
       dispatcher unchanged, so the dialog's buttons work as before.
   The wheel: an SDL event watch (SDL_AddEventWatch, installed the first time a scrollbar is drawn) counts
   SDL_MOUSEWHEEL; the next draw scrolls the dialog under the mouse.  The scroll position starts at the top and
   starts over whenever the text changes (the result replacing the question).  No keyboard scrolling (Copy and
   Paste owns the key events).

   SAFETY.  Runs on the game's thread inside the game's draw and event code; reads the dialog's own fields, writes
   only the clip rectangle (restored) and its own state; nothing is saved.  A fault falls back to the stock call.
   No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/scroll_popup.h"

#define SP_GAME_BASE 0x400000u
#define SP_MARGIN 16              /* kept free above and below a capped panel */
#define SP_GAP 6                  /* between the text box and the vertical bar */
#define SP_HBAR_GAP 4             /* between the text and the horizontal bar */
#define SP_WHEEL_LINES 3
#define SP_TRACK_CAP 8            /* VerticalScrollTrack's rounded ends, kept at the track's two ends */
#define SP_SLIDER_CAP 16          /* WideSlider2's rounded ends, kept at the bar's two ends */
#define SP_RECENT_MS 500u         /* a dialog drawn this recently takes the mouse */

typedef int (__fastcall *sp_justify_fn)(void *holder, void *edx, const char *text, int x, int y, int width,
                                        unsigned int colour, void *font, int measure_only);
typedef int (__fastcall *sp_nbyte_fn)(void *ctx, void *edx, const char *text, int bytes, int x, int y,
                                      int measure_only, unsigned int colour, void *font);
typedef const unsigned char *(__stdcall *sp_lookup_fn)(unsigned int id);
typedef void *(__fastcall *sp_frame_image_fn)(void *strip, void *edx, const char *file, int columns, int rows);
typedef void (__fastcall *sp_frame_draw_fn)(void *holder, void *edx, void *strip, int x, int y, int frame, float a);
typedef int (__fastcall *sp_vbool_fn)(void *self, void *edx);
typedef int (__fastcall *sp_vint_fn)(void *self, void *edx);
typedef int (__cdecl *sp_add_watch_fn)(void *callback, void *userdata);

typedef struct sp_picture {
    void *image;
    int w, h;                     /* one frame */
    int tx, ty, tw, th;           /* its drawn part (the rest is transparent): left, top, width, height */
    unsigned char strip[0x40];    /* the game's frame strip (0x34 bytes), built here */
} sp_picture;

typedef struct sp_view {         /* the dialog drawn last, where its parts are */
    unsigned char *popup;
    DWORD tick;
    int panel_l, panel_t, panel_r, panel_b;
    int box_x, box_y, box_w, box_h; /* the visible text box */
    int content_w, content_h;
    int vbar, hbar;               /* shown */
    int vx, vy, vh;               /* vertical bar: x, top, height (arrows included) */
    int arrow_h, knob_w, knob_h, track_w;
    int hx, hy, hw, hh;           /* horizontal bar */
    int handle_w, handle_h;
    int line;                     /* one line's height: an arrow's step */
} sp_view;

static const sp_game *g_game;
static int g_game_number;
static int g_installed;
static sp_view g_view;
static int g_sx, g_sy;            /* the scroll position */
static unsigned char *g_state_popup;
static unsigned int g_state_hash;
static int g_mx = -1, g_my = -1;  /* the mouse, as the dispatcher last saw it */
static int g_drag;                /* 0, 1 the vertical knob, 2 the horizontal handle */
static int g_drag_offset;
static int g_pressed;             /* 0, 1 the up arrow, 2 the down arrow (drawn pressed), 3 a track */
static volatile LONG g_wheel;
static int g_watch;               /* 0 not tried, 1 installed, -1 no SDL */
static sp_picture g_up, g_down, g_track, g_knob, g_wide, g_handle;
static int g_art;                 /* 0 not loaded, 1 loaded, -1 missing */
#ifdef VVFP_TEST
static volatile LONG g_scroll_draws;   /* the test build only: dialog bodies drawn scrolled */
#endif

/* ---- The game's helpers ------------------------------------------------------------------------------------ */

static void *sp_holder(void) {
    return *(void **)(UINT_PTR)g_game->ctx_global;
}

static int *sp_clip(void *holder) {
    unsigned char *ctx = holder != NULL ? *(unsigned char **)holder : NULL;
    return ctx != NULL ? (int *)(ctx + 0x60) : NULL;
}

static int sp_screen_h(void) {
    void *holder = sp_holder();
    unsigned char *ctx = holder != NULL ? *(unsigned char **)holder : NULL;
    int h = ctx != NULL ? *(int *)(ctx + 0x0C) : 0;
    return h > 0 && h <= 4096 ? h : g_game->screen_h;
}

static int sp_measure(void *holder, const char *text, int width, unsigned int colour, void *font) {
    return ((sp_justify_fn)(UINT_PTR)g_game->justify)(holder, NULL, text, 0, 0, width, colour, font, 1);
}

/* The widest word of `text` as the game's justified paragraph cuts it into words: spaces and line breaks part
   them, and a word also ends after '.' (not before another '.'), after ',' (not before a digit) and after '?'.
   A line holds one word wider than the box, or words that fit; so the widest line is the box or this. */
static int sp_widest_word(void *holder, const char *text, unsigned int colour, void *font) {
    sp_nbyte_fn nbyte = (sp_nbyte_fn)(UINT_PTR)g_game->nbyte;
    void *ctx = *(void **)holder;
    const char *p = text, *start;
    int widest = 0;
    while (*p != 0) {
        while (*p == ' ' || *p == '\n') {
            ++p;
        }
        if (*p == 0) {
            break;
        }
        start = p;
        for (;;) {
            char c = *p;
            if (c == 0 || c == ' ' || c == '\n') {
                break;
            }
            ++p;
            if ((c == '.' && *p != '.') || (c == ',' && !(*p >= '0' && *p <= '9')) || c == '?') {
                break;
            }
        }
        {
            int w = nbyte(ctx, NULL, start, (int)(p - start), 0, 0, 1, colour, font);
            if (w > widest) {
                widest = w;
            }
        }
    }
    return widest;
}

static unsigned int sp_hash(const char *text) {
    unsigned int h = 2166136261u;
    while (*text != 0) {
        h = (h ^ (unsigned char)*text++) * 16777619u;
    }
    return h;
}

static int sp_vcall_int(void *object, unsigned int slot) {
    void **vtable = *(void ***)object;
    return ((sp_vint_fn)vtable[slot / 4])(object, NULL);
}

/* The room the class keeps below its text for its buttons; -1 when it cannot be told. */
static int sp_reserve(const sp_class *c, unsigned char *popup) {
    if (c->reserve == SP_RESERVE_EVENT_DIALOG) {
        void *event = *(void **)(popup + c->event);
        void *button;
        if (event == NULL) {
            return -1;
        }
        if ((sp_vcall_int(event, 0x10) & 0xFF) != 0) {
            button = *(void **)(popup + c->choice_button);
            return button != NULL ? 4 * sp_vcall_int(button, 0x10) : -1;
        }
        button = *(void **)(popup + c->ok_button);
        if (button == NULL) {
            return -1;
        }
        {
            int b5 = 5 * sp_vcall_int(button, 0x10);
            return (b5 - (b5 >> 31)) >> 1;          /* the game's (5 x h) / 2: cdq, sub, sar */
        }
    }
    return -1;
}

/* ---- The art ------------------------------------------------------------------------------------------------ */

static int sp_load(sp_picture *pic, const sp_art *art) {
    const unsigned char *entry;
    const char *file;
    void *loaded;
    unsigned char *surface;
    if (art->id == 0 || art->columns <= 0) {
        return 0;                           /* a file beside the companion: a later stage */
    }
    entry = ((sp_lookup_fn)(UINT_PTR)g_game->image_lookup)(art->id);
    file = entry != NULL ? *(const char *const *)(entry + 4) : NULL;
    if (entry == NULL || *(const unsigned int *)entry != art->id || file == NULL) {
        return 0;
    }
    ZeroMemory(pic->strip, sizeof pic->strip);
    ((sp_frame_image_fn)(UINT_PTR)g_game->frame_image)(pic->strip, NULL, file, art->columns, 1);
    loaded = *(void **)(pic->strip + 4);
    surface = loaded != NULL ? *(unsigned char **)loaded : NULL;
    if (surface == NULL) {
        return 0;
    }
    pic->image = pic->strip;
    pic->w = *(int *)(surface + 8) / art->columns;
    pic->h = *(int *)(surface + 0x0C);
    pic->tx = 0; pic->ty = 0; pic->tw = pic->w; pic->th = pic->h;
    if (art->trim[2] > 0 && art->trim[3] > 0 && art->trim[0] + art->trim[2] <= pic->w
        && art->trim[1] + art->trim[3] <= pic->h) {
        pic->tx = art->trim[0]; pic->ty = art->trim[1]; pic->tw = art->trim[2]; pic->th = art->trim[3];
    }
    return pic->w > 0 && pic->h > 0;
}

static int sp_art_ready(void) {
    if (g_art == 0) {
        g_art = -1;
        if (sp_load(&g_up, &g_game->up) && sp_load(&g_down, &g_game->down) && sp_load(&g_track, &g_game->track)
            && sp_load(&g_knob, &g_game->knob) && sp_load(&g_wide, &g_game->wide)
            && sp_load(&g_handle, &g_game->handle)) {
            g_art = 1;
        }
    }
    return g_art == 1;
}

static void sp_picture_at(void *holder, const sp_picture *p, int x, int y) {
    ((sp_frame_draw_fn)(UINT_PTR)g_game->frame_draw)(holder, NULL, p->image, x, y, 0, 1.0f);
}

static void sp_frame_at(void *holder, const sp_picture *p, int x, int y, int frame) {
    ((sp_frame_draw_fn)(UINT_PTR)g_game->frame_draw)(holder, NULL, p->image, x, y, frame, 1.0f);
}

/* Sets the clip to r intersected with the saved clip `old`. */
static void sp_clip_to(int *clip, const int *old, int l, int t, int r, int b) {
    clip[0] = l > old[0] ? l : old[0];
    clip[1] = t > old[1] ? t : old[1];
    clip[2] = r < old[2] ? r : old[2];
    clip[3] = b < old[3] ? b : old[3];
    if (clip[2] < clip[0]) {
        clip[2] = clip[0];
    }
    if (clip[3] < clip[1]) {
        clip[3] = clip[1];
    }
}

static int sp_max_sy(void) {
    int m = g_view.content_h - g_view.box_h;
    return m > 0 ? m : 0;
}

static int sp_max_sx(void) {
    int m = g_view.content_w - g_view.box_w;
    return m > 0 ? m : 0;
}

static void sp_clamp(void) {
    if (g_sy > sp_max_sy()) g_sy = sp_max_sy();
    if (g_sy < 0) g_sy = 0;
    if (g_sx > sp_max_sx()) g_sx = sp_max_sx();
    if (g_sx < 0) g_sx = 0;
}

/* The knob's top for the current position, and the travel it has. */
static int sp_knob_travel(void) {
    int t = g_view.vh - 2 * g_view.arrow_h - g_view.knob_h;
    return t > 0 ? t : 0;
}

static int sp_knob_y(void) {
    int m = sp_max_sy();
    return g_view.vy + g_view.arrow_h + (m > 0 ? (int)((long long)g_sy * sp_knob_travel() / m) : 0);
}

static int sp_handle_travel(void) {
    int t = g_view.hw - g_view.handle_w;
    return t > 0 ? t : 0;
}

static int sp_handle_x(void) {
    int m = sp_max_sx();
    return g_view.hx + (m > 0 ? (int)((long long)g_sx * sp_handle_travel() / m) : 0);
}

/* One axis of a picture fitted to [from, to) without scaling it: its two ends (`cap` pixels each) at the two ends,
   and between them its middle -- repeated when the run is longer than the picture, its centre when shorter.  Each
   piece is [lo, hi) with the picture placed at pos.  Returns the pieces. */
#define SP_MAX_PIECES 24
static int sp_pieces(int from, int to, int size, int cap, int *lo, int *hi, int *pos) {
    int len = to - from, n = 0, m, step;
    if (len <= 0 || size <= 0) {
        return 0;
    }
    if (len == size) {
        lo[0] = from; hi[0] = to; pos[0] = from;
        return 1;
    }
    if (2 * cap >= size) {
        cap = (size - 1) / 2;
    }
    if (2 * cap > len) {
        cap = len / 2;
    }
    lo[n] = from; hi[n] = from + cap; pos[n] = from; ++n;                       /* the first end */
    if (len < size) {
        lo[n] = from + cap; hi[n] = to - cap; pos[n] = (from + to) / 2 - size / 2; ++n;   /* the picture's centre */
    } else {
        step = size - 2 * cap;
        hi[0] = from + size - cap < to - cap ? from + size - cap : to - cap;
        for (m = from + size - cap; m < to - cap && n < SP_MAX_PIECES - 1; m += step) {
            lo[n] = m; hi[n] = m + step < to - cap ? m + step : to - cap; pos[n] = m - cap; ++n;   /* the middle */
        }
    }
    lo[n] = to - cap; hi[n] = to; pos[n] = to - size; ++n;                      /* the last end */
    return n;
}

/* A picture's drawn part fitted to the rectangle (x, y, w, h) without scaling it, cut by the clip: its ends kept
   (capx pixels left and right, capy top and bottom), its middle repeated or cut (sp_pieces) along each axis. */
static void sp_draw_fitted(void *holder, int *clip, const int *old, const sp_picture *p, int frame, int x, int y,
                           int w, int h, int capx, int capy) {
    int xl[SP_MAX_PIECES], xh[SP_MAX_PIECES], xp[SP_MAX_PIECES], yl[SP_MAX_PIECES], yh[SP_MAX_PIECES],
        yp[SP_MAX_PIECES];
    int nx = sp_pieces(x, x + w, p->tw, capx, xl, xh, xp), ny = sp_pieces(y, y + h, p->th, capy, yl, yh, yp), i, j;
    for (j = 0; j < ny; ++j) {
        for (i = 0; i < nx; ++i) {
            if (xh[i] > xl[i] && yh[j] > yl[j]) {
                sp_clip_to(clip, old, xl[i], yl[j], xh[i], yh[j]);
                sp_frame_at(holder, p, xp[i] - p->tx, yp[j] - p->ty, frame);
            }
        }
    }
    clip[0] = old[0]; clip[1] = old[1]; clip[2] = old[2]; clip[3] = old[3];
}

static void sp_draw_bars(void *holder, int *clip, const int *old) {
    if (g_view.vbar) {
        int ty = g_view.vy + g_view.arrow_h, tb = g_view.vy + g_view.vh - g_view.arrow_h;
        int hover_up = g_mx >= g_view.vx && g_mx < g_view.vx + g_view.track_w && g_my >= g_view.vy && g_my < ty;
        int hover_down = g_mx >= g_view.vx && g_mx < g_view.vx + g_view.track_w && g_my >= tb
                         && g_my < g_view.vy + g_view.vh;
        sp_draw_fitted(holder, clip, old, &g_track, 0, g_view.vx, ty, g_track.w, tb - ty, 0, SP_TRACK_CAP);
        sp_frame_at(holder, &g_up, g_view.vx, g_view.vy, g_pressed == 1 ? 2 : hover_up ? 1 : 0);
        sp_frame_at(holder, &g_down, g_view.vx, tb, g_pressed == 2 ? 2 : hover_down ? 1 : 0);
        sp_picture_at(holder, &g_knob, g_view.vx + (g_view.track_w - g_view.knob_w) / 2, sp_knob_y());
    }
    if (g_view.hbar) {
        /* The horizontal bar is as thick as the vertical track: WideSlider2 with its rounded ends and its top and
           bottom edges kept, its middle cut; the handle is sliderhandle fitted to the vertical knob's size turned
           sideways (the knob's length along the bar, its width across). */
        sp_draw_fitted(holder, clip, old, &g_wide, 0, g_view.hx, g_view.hy, g_view.hw, g_view.hh, SP_SLIDER_CAP,
                       g_view.hh * 2 / 5);
        sp_draw_fitted(holder, clip, old, &g_handle, 0, sp_handle_x(), g_view.hy + (g_view.hh - g_view.handle_h) / 2,
                       g_view.handle_w, g_view.handle_h, g_handle.tw / 2 - 1, g_view.handle_h / 3);
    }
}

/* The horizontal bar's thickness: the vertical track's width. */
static int sp_hbar_h(void) {
    return g_track.w;
}

static int __cdecl sp_event_watch(void *userdata, void *event) {
    const unsigned char *e = (const unsigned char *)event;
    (void)userdata;
    if (e != NULL && *(const unsigned int *)e == 0x403u) {
        InterlockedExchangeAdd(&g_wheel, *(const int *)(e + 20));
    }
    return 1;
}

static void sp_install_watch(void) {
    HMODULE sdl;
    sp_add_watch_fn add;
    if (g_watch != 0) {
        return;
    }
    g_watch = -1;
    sdl = GetModuleHandleA("SDL2.dll");
    add = sdl != NULL ? (sp_add_watch_fn)GetProcAddress(sdl, "SDL_AddEventWatch") : NULL;
    if (add != NULL) {
        add((void *)sp_event_watch, NULL);
        g_watch = 1;
    }
}

/* ---- The draw ------------------------------------------------------------------------------------------------ */

/* draw: 1 the draw site, 0 the size site, 2 a measure site. */
static const sp_class *sp_class_at(unsigned int site, int draw) {
    int i, k;
    for (i = 0; i < g_game->class_count; ++i) {
        const sp_class *c = &g_game->classes[i];
        if (draw == 2) {
            for (k = 0; k < 4; ++k) {
                if (c->measure_sites[k] == site) {
                    return c;
                }
            }
        } else if ((draw ? c->draw_site : c->size_site) == site) {
            return c;
        }
    }
    return NULL;
}

/* The body text, scrolled when it does not fit; returns what the game's call returns (its height). */
static int sp_body(const sp_class *c, void *holder, const unsigned int *a) {
    const char *text = (const char *)(UINT_PTR)a[0];
    int x = (int)a[1], y = (int)a[2], w = (int)a[3];
    unsigned int colour = a[4];
    void *font = (void *)(UINT_PTR)a[5];
    unsigned char *popup = (unsigned char *)text - c->text;
    const int *panel = (const int *)(popup + c->panel);
    int reserve = sp_reserve(c, popup), box_h, content_h, content_w, need_v, need_h, vis_h, r, wheel, line;
    int *clip = sp_clip(holder);
    int old[4];
    if (reserve < 0 || clip == NULL || a[6] != 0 || w <= 0) {
        return -1;
    }
    box_h = panel[3] - reserve - y;
    content_w = sp_widest_word(holder, text, colour, font);
    if (content_w < w) {
        content_w = w;
    }
    content_h = sp_measure(holder, text, content_w, colour, font);   /* wrapped at the widest word: never stuck */
    if (box_h <= 0 || (content_h <= box_h && content_w <= w)) {
        if (g_view.popup == popup) {
            g_view.popup = NULL;            /* fits: no bars, the mouse is the game's */
        }
        return -1;
    }
    if (!sp_art_ready()) {
        return -1;
    }
    sp_install_watch();
    line = sp_measure(holder, "X", w, colour, font);
    if (line <= 0) {
        line = 16;
    }
    need_h = content_w > w;
    vis_h = need_h ? box_h - SP_HBAR_GAP - sp_hbar_h() : box_h;
    need_v = content_h > vis_h;
    if (need_v && vis_h > line) {
        vis_h -= vis_h % line;              /* whole lines: none is cut at the box's bottom */
    }
    if (vis_h < 2 * g_up.h + g_knob.h) {
        return -1;                          /* no room for a bar: as the game draws it */
    }
    if (g_state_popup != popup || g_state_hash != sp_hash(text)) {
        g_state_popup = popup;
        g_state_hash = sp_hash(text);
        g_sx = g_sy = 0;
        g_drag = g_pressed = 0;
    }
    g_view.popup = popup;
    g_view.tick = GetTickCount();
    g_view.panel_l = panel[0]; g_view.panel_t = panel[1]; g_view.panel_r = panel[2]; g_view.panel_b = panel[3];
    g_view.box_x = x; g_view.box_y = y; g_view.box_w = w; g_view.box_h = vis_h;
    g_view.content_w = content_w; g_view.content_h = content_h;
    g_view.vbar = need_v; g_view.hbar = need_h;
    g_view.arrow_h = g_up.h;
    g_view.track_w = g_track.w;
    g_view.knob_w = g_knob.w; g_view.knob_h = g_knob.h;
    g_view.vx = x + w + SP_GAP; g_view.vy = y; g_view.vh = vis_h;
    g_view.handle_w = g_knob.h; g_view.handle_h = g_knob.w;
    g_view.hx = x; g_view.hy = y + vis_h + SP_HBAR_GAP; g_view.hw = w;
    g_view.hh = sp_hbar_h();
    g_view.line = line;
    wheel = (int)InterlockedExchange(&g_wheel, 0);
    if (wheel != 0 && g_mx >= g_view.panel_l && g_mx < g_view.panel_r && g_my >= g_view.panel_t
        && g_my < g_view.panel_b) {
        if (need_v) {
            g_sy -= wheel * SP_WHEEL_LINES * g_view.line;
        } else {
            g_sx -= wheel * SP_WHEEL_LINES * g_view.line;
        }
    }
    sp_clamp();
    old[0] = clip[0]; old[1] = clip[1]; old[2] = clip[2]; old[3] = clip[3];
    sp_clip_to(clip, old, x, y, x + w, y + vis_h);
    r = ((sp_justify_fn)(UINT_PTR)g_game->justify)(holder, NULL, text, x - g_sx, y - g_sy, content_w, colour, font,
                                                    0);
    clip[0] = old[0]; clip[1] = old[1]; clip[2] = old[2]; clip[3] = old[3];
    sp_draw_bars(holder, clip, old);
    clip[0] = old[0]; clip[1] = old[1]; clip[2] = old[2]; clip[3] = old[3];
#ifdef VVFP_TEST
    InterlockedIncrement(&g_scroll_draws);
#endif
    return r;
}

/* From the stub at draw_site or a measure site: the return address, the holder (ecx) and the call's seven
   arguments. */
static int __stdcall sp_draw(unsigned int ret, void *holder, const unsigned int *a) {
    const sp_class *c = sp_class_at(ret - 5u, 1);
    int r = -1;
    if (c == NULL && sp_class_at(ret - 5u, 2) != NULL) {
        int width = (int)a[3];
        __try {
            int widest = sp_widest_word(holder, (const char *)(UINT_PTR)a[0], a[4], (void *)(UINT_PTR)a[5]);
            if (widest > width) {
                width = widest;             /* the paragraph never gets stuck on a word wider than its box */
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            width = (int)a[3];
        }
        return ((sp_justify_fn)(UINT_PTR)g_game->justify)(holder, NULL, (const char *)(UINT_PTR)a[0], (int)a[1],
                                                           (int)a[2], width, a[4], (void *)(UINT_PTR)a[5], (int)a[6]);
    }
    if (c != NULL) {
        int *clip = NULL, old[4] = {0, 0, 0, 0};
        __try {
            clip = sp_clip(holder);
            if (clip != NULL) {
                old[0] = clip[0]; old[1] = clip[1]; old[2] = clip[2]; old[3] = clip[3];
            }
            r = sp_body(c, holder, a);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            r = -1;
            if (clip != NULL) {
                __try {
                    clip[0] = old[0]; clip[1] = old[1]; clip[2] = old[2]; clip[3] = old[3];
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                }
            }
            g_view.popup = NULL;
        }
        if (r != -1) {
            return r;
        }
    }
    {
        int width = (int)a[3];
        __try {
            int widest = sp_widest_word(holder, (const char *)(UINT_PTR)a[0], a[4], (void *)(UINT_PTR)a[5]);
            if (widest > width) {
                width = widest;             /* never stuck on a word wider than the box */
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            width = (int)a[3];
        }
        return ((sp_justify_fn)(UINT_PTR)g_game->justify)(holder, NULL, (const char *)(UINT_PTR)a[0], (int)a[1],
                                                           (int)a[2], width, a[4], (void *)(UINT_PTR)a[5], (int)a[6]);
    }
}

__declspec(naked) static void sp_draw_stub(void) {
    __asm {
        lea eax, [esp + 4]
        push eax                            /* the seven arguments */
        push ecx                            /* the holder */
        push dword ptr [esp + 8]            /* the return address */
        call sp_draw
        ret 0x1C
    }
}

/* ---- The panel's height --------------------------------------------------------------------------------------- */

/* From the stub at size_site: makes room for a horizontal bar when the text has a word wider than its box, caps
   the height argument; returns the sizer to continue to. */
static unsigned int __stdcall sp_size(unsigned int ret, void *popup, unsigned int *a) {
    const sp_class *c = sp_class_at(ret - 5u, 0);
    if (c == NULL) {
        return 0;                           /* never: every size_site is a class's */
    }
    __try {
        int limit = sp_screen_h() - 2 * SP_MARGIN, cap = limit;
        int cell = a[0] != 0 ? *(const int *)((const unsigned char *)(UINT_PTR)a[0] + 0x14) : 0;
        unsigned char *p = (unsigned char *)popup;
        /* The 9-slice panel rounds the height up to whole cells of its picture (the strip's frame height, +0x14):
           a height one cell short of the whole cells that fit keeps the rounded panel inside the limit. */
        if (cell > 0 && cell < limit) {
            cap = (limit / cell) * cell - cell + 1;
        }
        int box_w = *(int *)(p + c->box + 8);
        void *holder = sp_holder();
        if (holder != NULL && box_w > 0 && sp_art_ready()
            && sp_widest_word(holder, (const char *)(p + c->text), 0, *(void **)(p + c->font)) > box_w) {
            a[2] += (unsigned int)(SP_HBAR_GAP + sp_hbar_h());
        }
        if (cap > 0 && (int)a[2] > cap) {
            a[2] = (unsigned int)cap;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return c->sizer;
}

__declspec(naked) static void sp_size_stub(void) {
    __asm {
        push ecx
        lea eax, [esp + 8]
        push eax                            /* the three arguments */
        push ecx                            /* the popup */
        push dword ptr [esp + 0xC]          /* the return address */
        call sp_size
        pop ecx
        mov edi, dword ptr [esp + 0xC]      /* the height, capped: the constructor centres by edi */
        jmp eax
    }
}

/* ---- The mouse ------------------------------------------------------------------------------------------------- */

static int sp_in(int x, int y, int l, int t, int w, int h) {
    return x >= l && x < l + w && y >= t && y < t + h;
}

static void sp_drag_to(int x, int y) {
    if (g_drag == 1) {
        int travel = sp_knob_travel();
        int top = y - g_drag_offset - (g_view.vy + g_view.arrow_h);
        g_sy = travel > 0 ? (int)((long long)top * sp_max_sy() / travel) : 0;
    } else if (g_drag == 2) {
        int travel = sp_handle_travel();
        int left = x - g_drag_offset - g_view.hx;
        g_sx = travel > 0 ? (int)((long long)left * sp_max_sx() / travel) : 0;
    }
    sp_clamp();
}

/* 1: the event was a scrollbar's (not passed on). */
static int __stdcall sp_mouse(int type, int x, int y) {
    int used = 0;
    __try {
        g_mx = x;
        g_my = y;
        if (g_view.popup == NULL || GetTickCount() - g_view.tick > SP_RECENT_MS) {
            g_drag = g_pressed = 0;
            return 0;
        }
        if (type == 1) {                    /* move */
            if (g_drag != 0) {
                sp_drag_to(x, y);
                used = 1;
            }
        } else if (type == 2) {             /* down */
            if (g_view.vbar && sp_in(x, y, g_view.vx, g_view.vy, g_view.track_w, g_view.vh)) {
                int ky = sp_knob_y();
                used = 1;
                if (y < g_view.vy + g_view.arrow_h) {
                    g_sy -= g_view.line;
                    g_pressed = 1;
                } else if (y >= g_view.vy + g_view.vh - g_view.arrow_h) {
                    g_sy += g_view.line;
                    g_pressed = 2;
                } else if (y >= ky && y < ky + g_view.knob_h) {
                    g_drag = 1;
                    g_drag_offset = y - ky;
                } else {
                    g_sy += (y < ky ? -1 : 1) * (g_view.box_h - g_view.line > g_view.line
                                                 ? g_view.box_h - g_view.line : g_view.line);
                    g_pressed = 3;                  /* the track: its release is the bar's too */
                }
            } else if (g_view.hbar && sp_in(x, y, g_view.hx, g_view.hy, g_view.hw, g_view.hh)) {
                int hx = sp_handle_x();
                used = 1;
                if (x >= hx && x < hx + g_view.handle_w) {
                    g_drag = 2;
                    g_drag_offset = x - hx;
                } else {
                    g_sx += (x < hx ? -1 : 1) * (g_view.box_w * 3 / 4);
                    g_pressed = 3;
                }
            }
            sp_clamp();
        } else if (type == 3) {             /* up */
            if (g_drag != 0 || g_pressed != 0) {
                used = 1;
            }
            g_drag = 0;
            g_pressed = 0;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        used = 0;
    }
    return used;
}

static unsigned int g_mouse_dispatch;

__declspec(naked) static void sp_mouse_stub(void) {
    __asm {
        push ecx
        push dword ptr [esp + 0x10]         /* y */
        push dword ptr [esp + 0x10]         /* x */
        push dword ptr [esp + 0x10]         /* type */
        call sp_mouse
        pop ecx
        test eax, eax
        jnz used
        jmp dword ptr [g_mouse_dispatch]
    used:
        ret 0xC
    }
}

/* ---- Install ----------------------------------------------------------------------------------------------------- */

/* 1 when every site of the game is installed (for the tests' emulation), else 0. */
int __stdcall VvfpScrollingPopupsInstalled(void) {
    return g_installed;
}

#ifdef VVFP_TEST
/* The TEST build only (vvfp_scrolling_popups_test.def, tests\test_dlls): never shipped.
   Dialog bodies drawn scrolled so far. */
int __stdcall VvfpScrollingPopupsTestScrolled(void) {
    return (int)g_scroll_draws;
}

/* The dialog drawn last (for the tests' emulation): 20 ints -- shown (1/0), the box x, y, width, visible height,
   the content's width and height, the bars shown (vertical, horizontal), the vertical bar's x, top, height and
   arrow height, the horizontal bar's x, y, width, height, one line's height, and the scroll position x, y.
   Returns how many it wrote. */
int __stdcall VvfpScrollingPopupsTestView(int *out, int count) {
    int v[20], i;
    v[0] = g_view.popup != NULL;
    v[1] = g_view.box_x; v[2] = g_view.box_y; v[3] = g_view.box_w; v[4] = g_view.box_h;
    v[5] = g_view.content_w; v[6] = g_view.content_h; v[7] = g_view.vbar; v[8] = g_view.hbar;
    v[9] = g_view.vx; v[10] = g_view.vy; v[11] = g_view.vh; v[12] = g_view.arrow_h;
    v[13] = g_view.hx; v[14] = g_view.hy; v[15] = g_view.hw; v[16] = g_view.hh;
    v[17] = g_view.line; v[18] = g_sx; v[19] = g_sy;
    if (out == NULL || count <= 0) {
        return 0;
    }
    if (count > 20) {
        count = 20;
    }
    __try {
        for (i = 0; i < count; ++i) {
            out[i] = v[i];
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
    return count;
}
#endif

static void sp_call_bytes(unsigned char *out, unsigned int site, unsigned int target) {
    unsigned int rel = target - (site + 5u);
    out[0] = 0xE8;
    CopyMemory(out + 1, &rel, 4);
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static vvfp_site_write w[1 + 6 * 8];
    static unsigned char stock[1 + 6 * 8][5];
    const unsigned char *module;
    const sp_game *g;
    int count = 0, i, k;
    (void)shipped;
    if (g_installed || game < 1 || game > 5) {
        return;
    }
    module = (const unsigned char *)GetModuleHandleA(NULL);
    if (module != NULL && (UINT_PTR)module != SP_GAME_BASE) {
        return;                             /* every site is a VA of the games' fixed base */
    }
    g = &SP_GAMES[game];
    if (g->class_count <= 0 || g->class_count > 8) {
        return;
    }
    sp_call_bytes(stock[count], g->mouse_site, g->mouse_dispatch);
    if (!vvfp_site_holds(g->mouse_site - 2u, (const unsigned char *)"\x8B\xC8", 2)) {
        return;                             /* mov ecx, eax: the manager */
    }
    vvfp_site_branch(&w[count], g->mouse_site, 5, stock[count], 0xE8, (const void *)sp_mouse_stub);
    ++count;
    for (i = 0; i < g->class_count; ++i) {
        const sp_class *c = &g->classes[i];
        if (!vvfp_site_holds(c->draw_site - 6u, c->draw_before, 6)
            || !vvfp_site_holds(c->size_push, (const unsigned char *)"W", 1)) {
            return;
        }
        sp_call_bytes(stock[count], c->draw_site, g->justify);
        vvfp_site_branch(&w[count], c->draw_site, 5, stock[count], 0xE8, (const void *)sp_draw_stub);
        ++count;
        sp_call_bytes(stock[count], c->size_site, c->sizer);
        vvfp_site_branch(&w[count], c->size_site, 5, stock[count], 0xE8, (const void *)sp_size_stub);
        ++count;
        for (k = 0; k < 4; ++k) {
            if (c->measure_sites[k] != 0) {
                sp_call_bytes(stock[count], c->measure_sites[k], g->justify);
                vvfp_site_branch(&w[count], c->measure_sites[k], 5, stock[count], 0xE8, (const void *)sp_draw_stub);
                ++count;
            }
        }
    }
    g_game = g;
    g_game_number = game;
    g_mouse_dispatch = g->mouse_dispatch;
    if (vvfp_install_sites(w, count)) {
        g_installed = 1;
    } else {
        g_game = NULL;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
