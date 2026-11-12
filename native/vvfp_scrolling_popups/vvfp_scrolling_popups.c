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
static int g_bars = 1;            /* sp_scroll draws the bars (a tombstone's lines after its first: not again) */
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

static int sp_screen_w(void) {
    void *holder = sp_holder();
    unsigned char *ctx = holder != NULL ? *(unsigned char **)holder : NULL;
    int w = ctx != NULL ? *(int *)(ctx + 0x08) : 0;
    return w > 0 && w <= 4096 ? w : g_game->screen_w;
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
    if (art->columns <= 0) {
        return 0;
    }
    if (art->file != NULL) {
        file = art->file;                   /* a picture file by name, loaded by the game's own loader */
    } else {
        if (art->id == 0 || g_game->image_lookup == 0) {
            return 0;
        }
        entry = ((sp_lookup_fn)(UINT_PTR)g_game->image_lookup)(art->id);
        file = entry != NULL ? *(const char *const *)(entry + 4) : NULL;
        if (entry == NULL || *(const unsigned int *)entry != art->id || file == NULL) {
            return 0;
        }
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
        sp_clip_to(clip, old, g_view.vx, ty, g_view.vx + g_view.track_w, tb);     /* a short track cuts the knob */
        sp_picture_at(holder, &g_knob, g_view.vx + (g_view.track_w - g_view.knob_w) / 2, sp_knob_y());
        clip[0] = old[0]; clip[1] = old[1]; clip[2] = old[2]; clip[3] = old[3];
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

/* Draws a popup's text that does not fit, scrolled: `draw` draws it with its top left at (x, y).  The box (bx, by,
   bw, bh) is where the text may show (the horizontal bar, when one is needed, takes its bottom); `ox` is where the
   text's left edge goes when it is no wider than the box (the game's own place for it), else it starts at bx;
   the vertical bar goes right of the box, within `room_r` (the box gives up width for it when it must).  `line` is
   one line's height (an arrow's step; the box shows whole lines).  The scroll position is the popup's while it
   shows the same text (`hash`).  Returns 0 when it cannot (the art is missing, no room): the caller makes the
   stock call. */
typedef void (*sp_draw_cb)(void *holder, void *data, int x, int y);

static int sp_scroll(void *holder, unsigned char *popup, const int *panel, int bx, int by, int bw, int bh, int ox,
                     int room_r, int content_w, int content_h, int line, unsigned int hash, sp_draw_cb draw,
                     void *data) {
    int *clip = sp_clip(holder);
    int old[4], need_v, need_h, vis_h, wheel;
    if (clip == NULL || bw <= 0 || bh <= 0 || !sp_art_ready()) {
        return 0;
    }
    if (line <= 0) {
        line = 16;
    }
    need_h = content_w > bw;
    vis_h = need_h ? bh - SP_HBAR_GAP - sp_hbar_h() : bh;
    need_v = content_h > vis_h;
    if (need_v && bx + bw + SP_GAP + g_track.w > room_r) {
        bw = room_r - g_track.w - SP_GAP - bx;      /* the box gives up width for the vertical bar */
        if (bw <= 0) {
            return 0;
        }
        if (!need_h && content_w > bw) {
            need_h = 1;
            vis_h = bh - SP_HBAR_GAP - sp_hbar_h();
        }
    }
    if (need_v && vis_h > line) {
        vis_h -= vis_h % line;              /* whole lines: none is cut at the box's bottom */
    }
    if (!need_v && content_h < vis_h) {
        vis_h = content_h;                  /* the horizontal bar right below the text */
    }
    if (vis_h < (need_v ? 2 * g_up.h + 6 : line)) {
        return 0;                           /* no room for a bar (or a line): as the game draws it */
    }
    sp_install_watch();
    if (g_state_popup != popup || g_state_hash != hash) {
        g_state_popup = popup;
        g_state_hash = hash;
        g_sx = g_sy = 0;
        g_drag = g_pressed = 0;
    }
    if (need_h) {
        ox = bx;
    }
    g_view.popup = popup;
    g_view.tick = GetTickCount();
    g_view.panel_l = panel[0]; g_view.panel_t = panel[1]; g_view.panel_r = panel[2]; g_view.panel_b = panel[3];
    g_view.box_x = bx; g_view.box_y = by; g_view.box_w = bw; g_view.box_h = vis_h;
    g_view.content_w = content_w; g_view.content_h = content_h;
    g_view.vbar = need_v; g_view.hbar = need_h;
    g_view.arrow_h = g_up.h;
    g_view.track_w = g_track.w;
    g_view.knob_w = g_knob.w; g_view.knob_h = g_knob.h;
    g_view.vx = bx + bw + SP_GAP; g_view.vy = by; g_view.vh = vis_h;
    g_view.handle_w = g_knob.h; g_view.handle_h = g_knob.w;
    g_view.hx = bx; g_view.hy = by + vis_h + SP_HBAR_GAP; g_view.hw = bw;
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
    sp_clip_to(clip, old, bx, by, bx + bw, by + vis_h);
    draw(holder, data, ox - g_sx, by - g_sy);
    clip[0] = old[0]; clip[1] = old[1]; clip[2] = old[2]; clip[3] = old[3];
    if (g_bars) {
        sp_draw_bars(holder, clip, old);
    }
    g_bars = 1;
    clip[0] = old[0]; clip[1] = old[1]; clip[2] = old[2]; clip[3] = old[3];
#ifdef VVFP_TEST
    InterlockedIncrement(&g_scroll_draws);
#endif
    return 1;
}

/* The island-event body: the game's justified paragraph at the content's width. */
typedef struct sp_justify_draw {
    const char *text;
    int width;
    unsigned int colour;
    void *font;
    int result;
} sp_justify_draw;

static void sp_draw_justified(void *holder, void *data, int x, int y) {
    sp_justify_draw *d = (sp_justify_draw *)data;
    d->result = ((sp_justify_fn)(UINT_PTR)g_game->justify)(holder, NULL, d->text, x, y, d->width, d->colour,
                                                            d->font, 0);
}

/* The body text, scrolled when it does not fit; returns what the game's call returns (its height). */
static int sp_body(const sp_class *c, void *holder, const unsigned int *a) {
    const char *text = (const char *)(UINT_PTR)a[0];
    int x = (int)a[1], y = (int)a[2], w = (int)a[3];
    unsigned int colour = a[4];
    void *font = (void *)(UINT_PTR)a[5];
    unsigned char *popup = (unsigned char *)text - c->text;
    const int *panel = (const int *)(popup + c->panel);
    int reserve = sp_reserve(c, popup), box_h, content_h, content_w, line;
    sp_justify_draw d;
    if (reserve < 0 || sp_clip(holder) == NULL || a[6] != 0 || w <= 0) {
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
    line = sp_measure(holder, "X", w, colour, font);
    d.text = text;
    d.width = content_w;
    d.colour = colour;
    d.font = font;
    d.result = -1;
    if (!sp_scroll(holder, popup, panel, x, y, w, box_h, x, panel[2] - 4, content_w, content_h, line, sp_hash(text),
                   sp_draw_justified, &d)) {
        return -1;
    }
    return d.result;
}

/* From the stub at draw_site or a measure site: the return address, the holder (ecx) and the call's seven
   arguments. */
static int __stdcall sp_draw(unsigned int ret, void *holder, const unsigned int *a) {
    const sp_class *c = sp_class_at(ret - 5u, 1);
    int r = -1;
    if (c == NULL && (sp_class_at(ret - 5u, 2) != NULL || ret - 5u == g_game->widen_site)) {
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

/* ---- The panel's size ----------------------------------------------------------------------------------------- */

/* The largest size the 9-slice panel may be asked for along one axis: it rounds the size up to whole cells of its
   picture (the strip's frame width +0x10 or height +0x14), so a size one cell short of the whole cells that fit
   keeps the rounded panel inside `limit`. */
static int sp_cap(int limit, int cell) {
    if (cell > 0 && cell < limit) {
        return (limit / cell) * cell - cell + 1;
    }
    return limit;
}

/* A message box asked for (w_req, h_req): what it was asked for is kept (a few at a time), so its draw knows how
   much of its text the capped panel left out and where the game put the text in it. */
#define SP_ASKED 4
typedef struct sp_asked {
    const unsigned char *popup;
    unsigned int vtable;
    int w_req, h_req;             /* as asked */
    int w_eff, h_eff;             /* as asked, with the room for the bars the capped panel needs */
    int reserve;                  /* SP_SHIFT_MEASURED: the room asked for below the text */
} sp_asked;
static sp_asked g_asked[SP_ASKED];
static int g_asked_next;

static const sp_asked *sp_asked_for(const unsigned char *popup) {
    int i;
    for (i = 0; i < SP_ASKED; ++i) {
        if (g_asked[i].popup == popup && popup != NULL && *(const unsigned int *)popup == g_asked[i].vtable) {
            return &g_asked[i];
        }
    }
    return NULL;
}

static void sp_ask(const unsigned char *popup, int w_req, int h_req) {
    int i, k = -1;
    for (i = 0; i < SP_ASKED; ++i) {
        if (g_asked[i].popup == popup) {
            k = i;
        }
    }
    if (k < 0) {
        k = g_asked_next;
        g_asked_next = (g_asked_next + 1) % SP_ASKED;
    }
    g_asked[k].popup = popup;
    g_asked[k].vtable = *(const unsigned int *)popup;
    g_asked[k].w_req = w_req;
    g_asked[k].h_req = h_req;
}

static int g_asked_reserve(int h_req, int text_top, int height) {
    int r = h_req - text_top - height;
    return r > 0 ? r : 0;
}

/* Caps a size asked for (a[1] width, a[2] height, a[0] the panel picture) to the screen, keeping what was asked:
   a capped height gives the width room for the vertical bar, a capped width gives the height room for the
   horizontal bar (the asked size with that room is kept as w_eff / h_eff). */
static void sp_cap_asked(const unsigned char *popup, unsigned int *a) {
    const unsigned char *pic = (const unsigned char *)(UINT_PTR)a[0];
    int cap_w = sp_cap(sp_screen_w() - 2 * SP_MARGIN, pic != NULL ? *(const int *)(pic + 0x10) : 0);
    int cap_h = sp_cap(sp_screen_h() - 2 * SP_MARGIN, pic != NULL ? *(const int *)(pic + 0x14) : 0);
    sp_asked *k;
    sp_ask(popup, (int)a[1], (int)a[2]);
    k = (sp_asked *)sp_asked_for(popup);
    if (cap_h > 0 && (int)a[2] > cap_h && sp_art_ready()) {
        a[1] += (unsigned int)(SP_GAP + g_track.w);       /* room for the vertical bar */
    }
    if (cap_w > 0 && (int)a[1] > cap_w) {
        if (sp_art_ready()) {
            a[2] += (unsigned int)(SP_HBAR_GAP + sp_hbar_h());   /* room for the horizontal bar */
        }
    }
    if (k != NULL) {
        k->w_eff = (int)a[1];
        k->h_eff = (int)a[2];
    }
    if (cap_w > 0 && (int)a[1] > cap_w) {
        a[1] = (unsigned int)cap_w;
    }
    if (cap_h > 0 && (int)a[2] > cap_h) {
        a[2] = (unsigned int)cap_h;
    }
}

typedef int (__fastcall *sp_height_fn)(void *font, void *edx, const char *text);
typedef int (__fastcall *sp_width_fn)(void *font, void *edx, const char *text, float scale);

/* A measured panel's text shown now, and its font. */
static const char *sp_shown(const sp_shift *s, const unsigned char *dialog, void **font) {
    const unsigned char *manager = *(const unsigned char *const *)(dialog + s->font_mgr);
    *font = manager != NULL ? *(void *const *)manager : NULL;
    return (const char *)(dialog + (s->text_b != 0 && dialog[s->flag] != 0 ? s->text_b : s->text_a));
}

static const sp_shift *sp_shift_at(unsigned int site, unsigned int vtable) {
    int i;
    for (i = 0; i < g_game->shift_count; ++i) {
        const sp_shift *s = &g_game->shifts[i];
        if (site != 0 ? s->size_site == site : s->vtable == vtable) {
            return s;
        }
    }
    return NULL;
}

/* From the stub at a size site: the island-event dialog makes room for a horizontal bar when its text has a word
   wider than its box and caps the height (*set_edi = 1: the constructor centres its contents by edi); the message
   box and the panels scrolled whole (tips) cap the width and the height and keep what they asked for.  Returns the
   sizer to continue to. */
static unsigned int sp_size_common(unsigned int ret, void *popup, unsigned int *a, int *set_edi) {
    const sp_class *c = sp_class_at(ret - 5u, 0);
    *set_edi = 0;
    if (c == NULL) {
        const sp_shift *s = sp_shift_at(ret - 5u, 0);
        if (ret - 5u == g_game->msgbox.size_site || s != NULL) {
            unsigned int vtable = s != NULL ? s->vtable : g_game->msgbox.vtable;
            __try {
                if (*(const unsigned int *)popup == vtable) {
                    if (s != NULL && s->mode == SP_SHIFT_MEASURED && g_game->height_fn != 0) {
                        void *font;
                        const char *text = sp_shown(s, (const unsigned char *)popup, &font);
                        int height = 0, width = 0, asked_h = (int)a[2];
                        sp_asked *k;
                        if (font != NULL) {
                            height = ((sp_height_fn)(UINT_PTR)g_game->height_fn)(font, NULL, text);
                            width = ((sp_width_fn)(UINT_PTR)g_game->width_fn)(font, NULL, text, 1.0f);
                        }
                        if (width > (int)a[1] - 2 * s->side && sp_art_ready()) {
                            a[2] += (unsigned int)(SP_HBAR_GAP + sp_hbar_h());   /* room for the horizontal bar */
                        }
                        sp_cap_asked((const unsigned char *)popup, a);
                        k = (sp_asked *)sp_asked_for((const unsigned char *)popup);
                        if (k != NULL) {
                            k->reserve = g_asked_reserve(asked_h, s->text_top, height);
                        }
                    } else {
                        sp_cap_asked((const unsigned char *)popup, a);
                    }
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
            return s != NULL ? s->sizer : g_game->msgbox.sizer;
        }
        return 0;                           /* never: every size site is a class's */
    }
    *set_edi = 1;
    __try {
        int cell = a[0] != 0 ? *(const int *)((const unsigned char *)(UINT_PTR)a[0] + 0x14) : 0;
        int cap = sp_cap(sp_screen_h() - 2 * SP_MARGIN, cell);
        unsigned char *p = (unsigned char *)popup;
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

/* Returns the sizer in eax and, in edx, 1 when edi takes the (capped) height. */
static unsigned __int64 __stdcall sp_size(unsigned int ret, void *popup, unsigned int *a) {
    int set_edi = 0;
    unsigned int to = sp_size_common(ret, popup, a, &set_edi);
    return ((unsigned __int64)(unsigned int)set_edi << 32) | to;
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
        test edx, edx
        jz keep
        mov edi, dword ptr [esp + 0xC]      /* the height, capped: the constructor centres by edi */
    keep:
        jmp eax
    }
}

/* ---- The message box's text ------------------------------------------------------------------------------------ */

typedef void (__fastcall *sp_text_fn)(void *holder, void *edx, const char *text, int x, int y, unsigned int colour,
                                      void *font);

typedef struct sp_text_draw {
    const char *text;
    unsigned int colour;
    void *font;
} sp_text_draw;

static void sp_draw_text(void *holder, void *data, int x, int y) {
    sp_text_draw *d = (sp_text_draw *)data;
    ((sp_text_fn)(UINT_PTR)g_game->text_draw)(holder, NULL, d->text, x, y, d->colour, d->font);
}

/* The message box's text control (its only one) drawn at (x, y): 1 when drawn scrolled, 0 when the game's call is
   to be made.  The game lays the box out as: the text `SP_MSG_TOP` below the panel's top (plus half of what the
   panel is taller than asked, or less half of what it is shorter), `SP_MSG_SIDE` from each side, and below it the
   room for its buttons -- what was asked for less the text and its top.  Scrolled, the text's room starts
   `SP_MSG_TOP` below the panel's top (the size site gave the panel the horizontal bar's height when it capped the
   width). */
#define SP_MSG_TOP 0x14
#define SP_MSG_SIDE 0x1E
static int sp_message(void *holder, const unsigned char *ctl, const unsigned int *a) {
    const unsigned char *popup = *(const unsigned char *const *)(ctl + 0x18);
    const sp_asked *asked;
    const int *panel, *rect = (const int *)(ctl + 8);
    int x = (int)a[1], y = (int)a[2], lw, lh, top, bottom, left, right, newlines = 0, line;
    const char *text = (const char *)(UINT_PTR)a[0], *p;
    sp_text_draw d;
    if (popup == NULL || text == NULL || *(const unsigned int *)popup != g_game->msgbox.vtable) {
        return 0;
    }
    asked = sp_asked_for(popup);
    if (asked == NULL) {
        return 0;
    }
    panel = (const int *)(popup + 0x14);
    lw = rect[2] - rect[0];
    lh = rect[3] - rect[1];
    top = panel[1] + SP_MSG_TOP;
    bottom = panel[3] - (asked->h_req - lh - SP_MSG_TOP);
    left = panel[0] + SP_MSG_SIDE;
    right = panel[2] - SP_MSG_SIDE;
    if (lw <= 0 || lh <= 0 || (y >= top && y + lh <= bottom && x >= left && x + lw <= right)) {
        if (g_view.popup == popup) {
            g_view.popup = NULL;            /* fits: no bars, the mouse is the game's */
        }
        return 0;
    }
    for (p = text; *p != 0; ++p) {
        newlines += *p == '\n';
    }
    line = lh / (newlines + 1);
    d.text = text;
    d.colour = a[3];
    d.font = (void *)(UINT_PTR)a[4];
    return sp_scroll(holder, (unsigned char *)popup, panel, left, top, right - left, bottom - top,
                     x >= left && x + lw <= right ? x : left, panel[2] - SP_MSG_SIDE / 2, lw, lh, line, sp_hash(text), sp_draw_text,
                     &d);
}

/* ---- The tombstone ---------------------------------------------------------------------------------------------- */

#define SP_TOMB_SIDE 0x10         /* the box: this far in from the panel's sides */
#define SP_TOMB_BUTTON_GAP 0x14   /* the game puts the OK / Done button this far above the panel's bottom */

/* The room the tombstone keeps below its lines: its button, the gap below it and 4 px above it. */
/* The box's top for lines spanning (l, t)-(r, b): the first line's top; when the lines are wider than the box and the
   horizontal bar would not fit between the last line and the button, the lines are lifted (at most to 12 px below
   the panel's top) to make room for it. */
static int sp_tomb_top(const int *panel, int l, int t, int r, int b, int bx, int bw, int bottom) {
    int top = t, need;
    if ((l < bx || r > bx + bw) && sp_art_ready()) {
        need = b + SP_HBAR_GAP + sp_hbar_h() - bottom;
        if (need > 0) {
            top = t - need;
        }
    }
    if (top < panel[1] + 12) {
        top = panel[1] + 12 < t ? panel[1] + 12 : t;
    }
    return top;
}

static int sp_tomb_bottom(const unsigned char *popup) {
    const int *panel = (const int *)(popup + 0x14);
    void *button = *(void *const *)(popup + g_game->tomb_button);
    int h = button != NULL ? sp_vcall_int(button, 0x10) : 0;
    return panel[3] - SP_TOMB_BUTTON_GAP - (h > 0 && h < 200 ? h : 0) - 4;
}

/* The later three: a tombstone line is a text control, drawn by the text control draw.  Every line of the
   tombstone (its window's controls of the same class, visible, not the editable epitaph) is measured as the
   text control draw places it (its font, scale, alignment and the window's origin); when one runs past the panel's
   sides (a long name, a long cause, a translation), each line is drawn moved by the scroll position under a clip
   set to the panel less SP_TOMB_SIDE on each side, above its button, with a horizontal bar below the lines.  The
   editable epitaph (its box cuts its own text) is drawn as the game draws it. */
typedef struct sp_label_draw {
    const char *text;
    int x, y, l, t;               /* where the game draws it; the lines' left and top there */
    unsigned int colour;
    void *font;
} sp_label_draw;

static void sp_draw_label(void *holder, void *data, int x, int y) {
    sp_label_draw *d = (sp_label_draw *)data;
    ((sp_text_fn)(UINT_PTR)g_game->text_draw)(holder, NULL, d->text, d->x + (x - d->l), d->y + (y - d->t), d->colour,
                                               d->font);
}

/* One text control's text extent as the text control draw places it: 1 when measured. */
static int sp_label_extent(const unsigned char *impl, const int *origin, void *font_default, int *l, int *t, int *r,
                           int *b) {
    const char *text = *(const char *const *)(impl + 0x30);
    const int *rect = (const int *)(impl + 8);
    void *font = *(void *const *)(impl + 0x3C);
    float scale = *(const float *)(impl + 0x58);
    int w, h, x;
    if (text == NULL || *text == 0) {
        return 0;
    }
    if (font == NULL) {
        font = font_default;
    }
    if (font == NULL) {
        return -1;
    }
    w = ((sp_width_fn)(UINT_PTR)g_game->width_fn)(font, NULL, text, scale);
    h = (int)((float)((sp_height_fn)(UINT_PTR)g_game->height_fn)(font, NULL, text) * scale);
    switch (*(const int *)(impl + 0x40)) {
    case 0: x = rect[0] + *(const int *)(impl + 0x44); break;
    case 1: x = rect[0] + (rect[2] - rect[0] - w) / 2; break;
    case 2: x = rect[2] - *(const int *)(impl + 0x44) - w; break;
    default: return -1;
    }
    *l = origin[0] + x;
    *r = *l + w;
    *t = origin[1] + rect[1] + *(const int *)(impl + 0x48);
    *b = *t + h;
    return 1;
}

typedef void (__fastcall *sp_rect_fn)(const void *control, void *edx, int *rect);

/* A child control's top, from its vtable+8 (its rectangle on the screen); 0x7FFFFFFF when it cannot be told. */
static int sp_child_top(const unsigned char *wrapper) {
    int rect[4] = {0, 0, 0, 0};
    __try {
        ((sp_rect_fn)(*(void *const *const *)wrapper)[2])(wrapper, NULL, rect);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0x7FFFFFFF;
    }
    return rect[1] > -4096 && rect[1] < 4096 && rect[3] >= rect[1] ? rect[1] : 0x7FFFFFFF;
}

static int sp_is_label_panel(unsigned int vtable) {
    int i;
    for (i = 0; i < g_game->label_panel_count; ++i) {
        if (g_game->label_panels[i] == vtable) {
            return 1;
        }
    }
    return 0;
}

static int sp_label_panel(void *holder, const unsigned char *ctl, const unsigned int *a) {
    const unsigned char *popup = *(const unsigned char *const *)(ctl + 0x18), *node, *n, *first = NULL;
    const int *panel, *origin;
    unsigned char *ctx = *(unsigned char **)holder;
    void *font_default;
    int l = 0x7FFFFFFF, t = 0x7FFFFFFF, r = -0x7FFFFFFF, b = -0x7FFFFFFF, guard = 0, bx, bw, by, bottom, line = 0;
    int ml, mt, mr, mb, here_l = 0, here_t = 0, k, mid, below = 0x7FFFFFFF, top;
    sp_label_draw d;
    if (popup == NULL || ctl[0x24] != 0 || g_game->width_fn == 0
        || !sp_is_label_panel(*(const unsigned int *)popup)) {
        return 0;
    }
    /* The text control draw has set the drawing context's font to the control's own, when it has one: the
       window's default font is then not known here, and every line must have its own or none. */
    font_default = *(void *const *)(ctl + 0x3C) == NULL ? *(void **)(ctx + 0x5C) : NULL;
    node = *(const unsigned char *const *)(popup + 4);
    origin = (const int *)(node + 4);
    if (sp_label_extent(ctl, origin, font_default, &here_l, &here_t, &mr, &mb) != 1 || here_l != (int)a[1]
        || here_t != (int)a[2]) {
        return 0;                           /* not where the game draws it: as the game draws it */
    }
    panel = (const int *)(popup + 0x14);
    mid = (panel[1] + panel[3]) / 2;
    for (n = *(const unsigned char *const *)(node + 0x18); n != NULL && guard < 256; n = *(const unsigned char *const *)(n + 4), ++guard) {
        const unsigned char *wrapper = *(const unsigned char *const *)n, *impl;
        if (wrapper == NULL) {
            continue;
        }
        impl = *(const unsigned char *const *)(wrapper + 0x10);
        if (impl == NULL || *(const unsigned int *)impl != *(const unsigned int *)ctl
            || *(const unsigned char *const *)(impl + 0x18) != popup) {
            top = sp_child_top(wrapper);     /* another control (a button): the lines stay above it */
            if (top >= mid && top < below) {
                below = top;
            }
            continue;
        }
        if (impl[0x24] != 0) {                       /* a text box (the epitaph, a name): drawn as the game draws it */
            top = origin[1] + *(const int *)(impl + 0xC);
            if (top >= mid && top < below) {
                below = top;
            }
            continue;
        }
        if (impl[0x2C] == 0) {
            continue;
        }
        k = sp_label_extent(impl, origin, font_default, &ml, &mt, &mr, &mb);
        if (k < 0) {
            return 0;
        }
        if (k == 0) {
            continue;
        }
        first = impl;                       /* the list runs newest first: the last one met is the first made */
        if (ml < l) l = ml;
        if (mt < t) t = mt;
        if (mr > r) r = mr;
        if (mb > b) b = mb;
        if (line == 0 || mb - mt < line) {
            line = mb - mt;
        }
    }
    bx = panel[0] + SP_TOMB_SIDE;
    bw = panel[2] - panel[0] - 2 * SP_TOMB_SIDE;
    bottom = (below != 0x7FFFFFFF ? below : panel[3] - 0x10) - 4;   /* above the controls in the panel's lower half */
    if (first == NULL || r <= l || (l >= bx && r <= bx + bw && b <= bottom && t >= panel[1])) {
        if (g_view.popup == popup) {
            g_view.popup = NULL;            /* fits: no bars, the mouse is the game's */
        }
        return 0;
    }
    by = sp_tomb_top(panel, l, t, r, b, bx, bw, bottom);
    d.text = (const char *)(UINT_PTR)a[0];
    d.x = (int)a[1];
    d.y = (int)a[2];
    d.l = l;
    d.t = t;
    d.colour = a[3];
    d.font = (void *)(UINT_PTR)a[4];
    g_bars = first == ctl;                  /* the bars once a frame, with the first line */
    k = sp_scroll(holder, (unsigned char *)popup, panel, bx, by, bw, bottom - by, l, panel[2] - SP_TOMB_SIDE / 2,
                  r - l, b - t, line, (unsigned int)(r - l) * 31u + (unsigned int)(b - t), sp_draw_label, &d);
    g_bars = 1;
    return k;
}

/* From the stub at the text control draw's call of the text draw: the holder (ecx), the control (esi) and the
   call's five arguments. */
static void __stdcall sp_control(void *holder, const unsigned char *ctl, const unsigned int *a) {
    int *clip = NULL, old[4] = {0, 0, 0, 0}, done = 0;
    g_bars = 1;
    __try {
        clip = sp_clip(holder);
        if (clip != NULL) {
            old[0] = clip[0]; old[1] = clip[1]; old[2] = clip[2]; old[3] = clip[3];
        }
        done = sp_label_panel(holder, ctl, a);
        if (!done) {
            done = sp_message(holder, ctl, a);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        done = 0;
        if (clip != NULL) {
            __try {
                clip[0] = old[0]; clip[1] = old[1]; clip[2] = old[2]; clip[3] = old[3];
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }
        g_view.popup = NULL;
    }
    if (!done) {
        ((sp_text_fn)(UINT_PTR)g_game->text_draw)(holder, NULL, (const char *)(UINT_PTR)a[0], (int)a[1], (int)a[2],
                                                   a[3], (void *)(UINT_PTR)a[4]);
    }
}

__declspec(naked) static void sp_control_stub(void) {
    __asm {
        lea eax, [esp + 4]
        push eax                            /* the five arguments */
        push esi                            /* the text control */
        push ecx                            /* the holder */
        call sp_control
        ret 0x14
    }
}

/* ---- Panels scrolled whole (tips) ------------------------------------------------------------------------------- */

typedef void (__fastcall *sp_content_fn)(void *dialog, void *edx);

typedef struct sp_shifted {
    unsigned char *dialog;
    sp_content_fn content;
    int bx, by, dx0, dy0;
    unsigned int yfield;          /* moved instead of the panel's top and bottom (0: the panel's) */
} sp_shifted;

/* The dialog's body drawn with its panel rectangle (+0x14..+0x20, which its body draw places everything by) moved
   so the body's top left lands at (x, y), then put back. */
static void sp_draw_shifted(void *holder, void *data, int x, int y) {
    sp_shifted *s = (sp_shifted *)data;
    int *panel = (int *)(s->dialog + 0x14), saved[4], dx = s->dx0 + (x - s->bx), dy = s->dy0 + (y - s->by);
    (void)holder;
    int *yfield = s->yfield != 0 ? (int *)(s->dialog + s->yfield) : NULL, saved_y = yfield != NULL ? *yfield : 0;
    saved[0] = panel[0]; saved[1] = panel[1]; saved[2] = panel[2]; saved[3] = panel[3];
    panel[0] += dx; panel[2] += dx;
    if (yfield != NULL) {
        *yfield += dy;
    } else {
        panel[1] += dy; panel[3] += dy;
    }
    __try {
        s->content(s->dialog, NULL);
    } __finally {
        panel[0] = saved[0]; panel[1] = saved[1]; panel[2] = saved[2]; panel[3] = saved[3];
        if (yfield != NULL) {
            *yfield = saved_y;
        }
    }
}

/* A measured panel (A New Home's and The Lost Children's island events): the text shown now, measured; when it
   does not fit above the room kept for the buttons (the result replacing the question in a panel sized for the
   question, or a text taller than the capped panel) or is wider than the box, it is drawn under the clip with the
   y the constructor keeps (and the panel's sides, for a wide text) moved by the scroll position. */
static int sp_measured_body(const sp_shift *s, const sp_asked *asked, unsigned char *dialog, sp_content_fn content,
                            void *holder) {
    const int *panel = (const int *)(dialog + 0x14);
    int pw = panel[2] - panel[0], top, bottom, bx, bw, by, height, width, line, newlines = 0;
    void *font;
    const char *text = sp_shown(s, dialog, &font), *p;
    sp_shifted d;
    if (font == NULL || g_game->height_fn == 0 || g_game->width_fn == 0) {
        return 0;
    }
    height = ((sp_height_fn)(UINT_PTR)g_game->height_fn)(font, NULL, text);
    width = ((sp_width_fn)(UINT_PTR)g_game->width_fn)(font, NULL, text, 1.0f);
    top = *(const int *)(dialog + s->yfield) + s->text_top;
    bottom = panel[3] - asked->reserve;
    bx = panel[0] + s->side;
    bw = pw - 2 * s->side;
    if (top >= panel[1] && top + height <= bottom && width <= bw) {
        if (g_view.popup == dialog) {
            g_view.popup = NULL;
        }
        return 0;
    }
    by = panel[1] + s->text_top;              /* scrolled: the text from the top of its room */
    for (p = text; *p != 0; ++p) {
        newlines += *p == '\n';
    }
    line = height / (newlines + 1);
    d.dialog = dialog;
    d.content = content;
    d.bx = bx;
    d.by = by;
    d.dx0 = width > bw ? bx - (panel[0] + (pw - width) / 2) : 0;
    d.dy0 = by - top;
    d.yfield = s->yfield;
    return sp_scroll(holder, dialog, panel, bx, by, bw, bottom - by, bx, panel[2] - s->side / 3,
                     width, height, line > 0 ? line : s->line, sp_hash(text), sp_draw_shifted, &d);
}

/* A panel that asked for more than the screen holds: its body is drawn under the clip, moved by the scroll position
   (and by what the capped panel moved it: the game centres a panel's contents by (panel - asked) / 2), with the
   bars.  1 when drawn so. */
static int sp_shift_body(unsigned char *dialog, sp_content_fn content) {
    const sp_shift *s = sp_shift_at(0, *(const unsigned int *)dialog);
    const sp_asked *asked = s != NULL ? sp_asked_for(dialog) : NULL;
    const int *panel = (const int *)(dialog + 0x14);
    void *holder = sp_holder(), *button;
    int pw = panel[2] - panel[0], ph = panel[3] - panel[1], over_x, over_y, reserve = 0, bx, by, bw, bh;
    int content_w, content_h;
    sp_shifted d;
    if (asked == NULL || holder == NULL) {
        return 0;
    }
    if (s->mode == SP_SHIFT_MEASURED) {
        return sp_measured_body(s, asked, dialog, content, holder);
    }
    over_x = asked->w_eff - pw;
    over_y = asked->h_eff - ph;
    if (over_x <= 0 && over_y <= 0) {
        if (g_view.popup == dialog) {
            g_view.popup = NULL;
        }
        return 0;
    }
    button = s->button != 0 ? *(void **)(dialog + s->button) : NULL;
    if (button != NULL) {
        reserve = s->reserve_buttons * sp_vcall_int(button, 0x10);
    }
    bx = panel[0] + s->side;
    bw = pw - 2 * s->side;
    by = panel[1] + s->top;
    bh = panel[3] - reserve - by;
    d.dialog = dialog;
    d.content = content;
    d.bx = bx;
    d.by = by;
    d.yfield = 0;
    d.dx0 = over_x > 0 ? -((pw - asked->w_req) / 2) : 0;
    d.dy0 = over_y > 0 ? -((ph - asked->h_req) / 2) : 0;
    /* The body below the box's top, as the game laid it out for what it asked: down to the room for the buttons,
       moved by half of what the panel is taller than asked when it is. */
    content_h = asked->h_req - reserve - s->top + (over_y > 0 ? 0 : (ph - asked->h_req) / 2);
    content_w = asked->w_req - 2 * s->side;
    return sp_scroll(holder, dialog, panel, bx, by, bw, bh, bx, panel[2] - s->side / 3,
                     content_w > bw || over_x > 0 ? content_w : bw, content_h, s->line,
                     (unsigned int)asked->h_req * 31u + (unsigned int)asked->w_req, sp_draw_shifted, &d);
}

/* A New Home and The Lost Children: the tombstone's body draw draws every line with the centred-block draw, which
   calls the core draw from one place (`centre_site`).  The body is drawn once measuring (that call records each
   line's extent and draws nothing; the clip is empty meanwhile, so nothing else shows), then, when a line runs past
   the panel's sides, drawn with the panel rectangle (which the body draw and Cause of Death's cause line, drawn from
   its hook in that body draw, place everything by) moved by the scroll position, under the clip. */
static volatile LONG g_measuring;
static int g_ext[5];              /* left, top, right, bottom; one line's height */
static unsigned int g_core_draw;

static void __stdcall sp_measured(void *ctx, const unsigned int *a) {
    const char *s = (const char *)(UINT_PTR)a[0];
    void *font = (void *)(UINT_PTR)a[4];
    int w, h, x = (int)a[1], y = (int)a[2];
    __try {
        if (font == NULL && ctx != NULL) {
            font = *(void **)((unsigned char *)ctx + 0x5C);
        }
        if (s == NULL || *s == 0 || font == NULL) {
            return;
        }
        w = ((sp_width_fn)(UINT_PTR)g_game->width_fn)(font, NULL, s, 1.0f);
        h = ((sp_height_fn)(UINT_PTR)g_game->height_fn)(font, NULL, s);
        if (x < g_ext[0]) g_ext[0] = x;
        if (y < g_ext[1]) g_ext[1] = y;
        if (x + w > g_ext[2]) g_ext[2] = x + w;
        if (y + h > g_ext[3]) g_ext[3] = y + h;
        if (g_ext[4] == 0 || (h > 0 && h < g_ext[4])) {
            g_ext[4] = h;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

__declspec(naked) static void sp_centre_stub(void) {
    __asm {
        cmp dword ptr [g_measuring], 0
        jne measure
        jmp dword ptr [g_core_draw]
    measure:
        lea eax, [esp + 4]
        push eax                            /* the five arguments */
        push ecx                            /* the drawing context */
        call sp_measured
        ret 0x14
    }
}

static int sp_tomb_drawn(unsigned char *dialog, sp_content_fn content) {
    const int *panel = (const int *)(dialog + 0x14);
    void *holder = sp_holder();
    int *clip = holder != NULL ? sp_clip(holder) : NULL, old[4], bx, bw, by, bottom;
    sp_shifted d;
    if (clip == NULL || g_game->width_fn == 0 || g_game->height_fn == 0) {
        return 0;
    }
    old[0] = clip[0]; old[1] = clip[1]; old[2] = clip[2]; old[3] = clip[3];
    g_ext[0] = g_ext[1] = 0x7FFFFFFF;
    g_ext[2] = g_ext[3] = -0x7FFFFFFF;
    g_ext[4] = 0;
    clip[0] = old[0]; clip[1] = old[1]; clip[2] = old[0]; clip[3] = old[1];   /* empty: nothing shows */
    InterlockedExchange(&g_measuring, 1);
    __try {
        content(dialog, NULL);
    } __finally {
        InterlockedExchange(&g_measuring, 0);
        clip[0] = old[0]; clip[1] = old[1]; clip[2] = old[2]; clip[3] = old[3];
    }
    bx = panel[0] + SP_TOMB_SIDE;
    bw = panel[2] - panel[0] - 2 * SP_TOMB_SIDE;
    bottom = sp_tomb_bottom(dialog);
    if (g_ext[2] <= g_ext[0] || (g_ext[0] >= bx && g_ext[2] <= bx + bw && g_ext[3] <= bottom)) {
        if (g_view.popup == dialog) {
            g_view.popup = NULL;
        }
        return 0;
    }
    by = sp_tomb_top(panel, g_ext[0], g_ext[1], g_ext[2], g_ext[3], bx, bw, bottom);
    d.dialog = dialog;
    d.content = content;
    d.bx = bx;
    d.by = by;
    d.dx0 = bx - g_ext[0];
    d.dy0 = by - g_ext[1];
    d.yfield = 0;
    return sp_scroll(holder, dialog, panel, bx, by, bw, bottom - by, g_ext[0], panel[2] - SP_TOMB_SIDE / 2,
                     g_ext[2] - g_ext[0], g_ext[3] - g_ext[1], g_ext[4],
                     (unsigned int)(g_ext[2] - g_ext[0]) * 31u + (unsigned int)(g_ext[3] - g_ext[1]), sp_draw_shifted,
                     &d);
}

/* From the stub at the frame draw's tail: the dialog's body (vtable+0x30), as the frame draw's `jmp` called it. */
static void __stdcall sp_content(unsigned char *dialog) {
    sp_content_fn content = (sp_content_fn)(*(void ***)dialog)[0x30 / 4];
    int *clip = NULL, old[4] = {0, 0, 0, 0}, done = 0;
    __try {
        clip = sp_clip(sp_holder());
        if (clip != NULL) {
            old[0] = clip[0]; old[1] = clip[1]; old[2] = clip[2]; old[3] = clip[3];
        }
        if (g_game->centre_site != 0 && *(const unsigned int *)dialog == g_game->tomb_vtable) {
            done = sp_tomb_drawn(dialog, content);
        } else {
            done = sp_shift_body(dialog, content);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        done = 0;
        if (clip != NULL) {
            __try {
                clip[0] = old[0]; clip[1] = old[1]; clip[2] = old[2]; clip[3] = old[3];
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }
        g_view.popup = NULL;
    }
    if (!done) {
        content(dialog, NULL);
    }
}

/* The frame draw's tail, replaced from `mov edx, [esi]` through `jmp [edx+0x30]` (A New Home to The Secret City:
   8B 16 5F 8B CE 5E 5B 83 C4 04 FF 62 30) or `jmp eax` (The Tree of Life, New Believers: 8B 16 8B 42 30 5F 8B CE
   5E 83 C4 04 FF E0): the same pops, then the body through sp_content, returning to the frame draw's caller. */
__declspec(naked) static void sp_tail_stub_5(void) {
    __asm {
        pop edi
        mov ecx, esi
        pop esi
        pop ebx
        add esp, 4
        push ecx
        call sp_content
        ret
    }
}

__declspec(naked) static void sp_tail_stub_4(void) {
    __asm {
        pop edi
        mov ecx, esi
        pop esi
        add esp, 4
        push ecx
        call sp_content
        ret
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
#define SP_MAX_SITES 64
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static vvfp_site_write w[SP_MAX_SITES];
    static unsigned char stock[SP_MAX_SITES][5];
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
    if (g->class_count < 0 || g->class_count > 8 || g->mouse_site == 0 || g->msgbox.size_site == 0) {
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
    /* The message box: its constructor's sizer call (after `push eax; mov ecx, esi`) and the text control draw's
       call of the text draw (esi = the control). */
    if (!vvfp_site_holds(g->msgbox.size_site - 3u, (const unsigned char *)"\x50\x8B\xCE", 3)
        || !vvfp_site_holds(g->ctl_site - 4u, g->ctl_before, 4)) {
        return;
    }
    sp_call_bytes(stock[count], g->msgbox.size_site, g->msgbox.sizer);
    vvfp_site_branch(&w[count], g->msgbox.size_site, 5, stock[count], 0xE8, (const void *)sp_size_stub);
    ++count;
    sp_call_bytes(stock[count], g->ctl_site, g->text_draw);
    vvfp_site_branch(&w[count], g->ctl_site, 5, stock[count], 0xE8, (const void *)sp_control_stub);
    ++count;
    /* The panels scrolled whole (tips): each one's sizer call, and the frame draw's tail that calls every
       dialog's body; a tip's per-line justified paragraph (never stuck on a word wider than its box). */
    for (i = 0; i < g->shift_count; ++i) {
        const sp_shift *s = &g->shifts[i];
        if (!vvfp_site_holds(s->size_site - 3u, s->size_before, 3)) {
            return;
        }
        sp_call_bytes(stock[count], s->size_site, s->sizer);
        vvfp_site_branch(&w[count], s->size_site, 5, stock[count], 0xE8, (const void *)sp_size_stub);
        ++count;
    }
    if (g->shift_count > 0) {
        static const unsigned char tail5[13] = {0x8B, 0x16, 0x5F, 0x8B, 0xCE, 0x5E, 0x5B, 0x83, 0xC4, 0x04,
                                                0xFF, 0x62, 0x30};
        static const unsigned char tail4[14] = {0x8B, 0x16, 0x8B, 0x42, 0x30, 0x5F, 0x8B, 0xCE, 0x5E, 0x83,
                                                0xC4, 0x04, 0xFF, 0xE0};
        int four = g->tail_pops == 4;
        if (!vvfp_site_holds(g->tail_site - 6u, (const unsigned char *)(four ? "\x0F\x8A" : "\x0F\x85"), 2)) {
            return;                         /* jne / jp: the open fade not finished (no body drawn) */
        }
        vvfp_site_branch(&w[count], g->tail_site, four ? 14 : 13, four ? tail4 : tail5, 0xE9,
                         four ? (const void *)sp_tail_stub_4 : (const void *)sp_tail_stub_5);
        ++count;
    }
    /* A New Home, The Lost Children: the centred-block draw's call of the core draw (the tombstone's lines are
       measured there). */
    if (g->centre_site != 0) {
        if (!vvfp_site_holds(g->centre_site - 3u, (const unsigned char *)"\x57\x8B\xCB", 3)) {
            return;                         /* push edi; mov ecx, ebx */
        }
        sp_call_bytes(stock[count], g->centre_site, g->core_draw);
        vvfp_site_branch(&w[count], g->centre_site, 5, stock[count], 0xE8, (const void *)sp_centre_stub);
        ++count;
    }
    if (g->widen_site != 0) {
        sp_call_bytes(stock[count], g->widen_site, g->justify);
        vvfp_site_branch(&w[count], g->widen_site, 5, stock[count], 0xE8, (const void *)sp_draw_stub);
        ++count;
    }
    g_game = g;
    g_game_number = game;
    g_mouse_dispatch = g->mouse_dispatch;
    g_core_draw = g->core_draw;
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
