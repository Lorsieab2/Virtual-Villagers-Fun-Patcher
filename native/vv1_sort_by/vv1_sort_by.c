/* VVFP VV1 Sort By -- "Sort by Age/Skill/Health in Details Screen" for A New
   Home, the way The Lost Children and the later games do it.

   THE LATER GAMES' RULE, measured live in The Secret City (86 villagers, every
   arrow step read back from the game's own selection field):

     * Three orders, each ASCENDING by one key -- Age: the age field; Skill:
       the villager's HIGHEST skill; Health: the health field -- with the
       record index as the tie-break.
     * The game keeps a POSITION in that list.  A right arrow moves the
       position up one (wrapping), a left arrow down one, and the villager at
       the new position is selected.  Changing the sort rebuilds the list but
       keeps the position, so the next arrow press shows the villager at
       position+1 of the NEW list -- that is the observed behaviour, not a
       guess, and it is reproduced here rather than "improved".
     * When the selection is changed by something else (the player clicks a
       villager in the strip, or opens Details on one), the position is that
       villager's place in the current list.
     * Only living villagers are listed: occupied records with health > 0,
       the same test the stock arrows use.
     * Age is the default order.

   THE CLEARED SELECTION.  Just before the store the hook replaces, the stock
   arrow calls 0x4393E0, which writes -1 into the selection field; so at the
   hook the field no longer says where the player was.  The draw hook, which
   runs every rendered Details frame, remembers the selection it saw, and
   the step falls back to that whenever the field reads -1.

   HOW IT IS WIRED.  The stock right/left arrows (the Details screen's button
   handler, 0x44A76E / 0x44A824) walk the record array for the next living
   villager and store it at state+0xAD34.  The Origins row splices exactly
   those two stores (0x44A7FF and 0x44A8B4, `mov [eax+0xAD34], edi`) through
   stubs that hand the game's own candidate and the direction to the Origins
   companion's Vv1SortStep, which forwards here (Vv1SortByStep); the value
   returned is what gets stored.  The buttons are drawn from the Origins
   companion's Details portrait hook (once per rendered Details frame) and
   their clicks are seen through an SDL event watch on the game's own SDL2,
   like the number-keys companion.  No sidecar: the chosen order is a session
   setting, as in the later games.

   ART.  The owner's own: Images/vvfp_sort_band.png is the band they painted
   into the Details background -- the "Sort By:" plate, the Age, Skill and
   Health plates with their words, and an empty radio holder on each -- cut
   from their VD_BG.png at (8, 475), 258x40, and drawn back there 1:1 every
   Details frame through the engine's own draw (0x409410), so the stock
   background file is never replaced.  Images/vvfp_sort_radio.png is The
   Lost Children's detailradiobtn.png at 16 px (a sheet of three 16x16
   cells: 0 blank, 1 selected); the holders in the band ARE its blank cell,
   so the chosen order's radio is the selected cell drawn 1:1, 16x16, over
   the holder.  No words are drawn: they are in the art. */
#include <windows.h>
#include <string.h>

#define VV1_VILLAGE_STATE_PTR  (*(unsigned char **)0x0048AEDCu)
/* The villager manager: the lazy getter at 0x43DA37 allocates 0x3E034 bytes
   (256 records of 0x3D8 plus the manager trailer) and stores the result
   here; the village state keeps the same pointer at +0xADE8 (equal in every
   full dump checked), and record 0 is the allocation itself.  Not a Golden
   Child pointer, whatever an older comment elsewhere calls it. */
#define VV1_VILLAGERS_PTR      (*(unsigned char **)0x0048B614u)   /* record 0 is the allocation itself */
#define VV1_SELECTED_OFFSET    0xAD34u      /* state: the Details screen's selected record index, -1 = none */
#define VV1_RECORD_STRIDE      0x3D8u
#define VV1_RECORD_COUNT       256
#define VV1_OCCUPIED_OFFSET    0x28u        /* u8 */
#define VV1_HEALTH_OFFSET      0x344u       /* i32; the arrows skip <= 0 */
#define VV1_AGE_OFFSET         0x348u       /* i32 */
#define VV1_SKILLS_OFFSET      0x3BCu       /* 5 x i32: farming, building, research, healing, breeding */
#define VV1_SKILL_COUNT        5

#define VV1_ADDR_OPERATOR_NEW  0x0044AF03u  /* cdecl(size) */
/* The click.  The Details screen's own checkboxes play sound 0x40 through the
   sound manager (0x4497F5..0x4497FA: thiscall 0x431470(manager; id)); the
   manager is the singleton 0x430BC0 keeps at 0x48B5E8.  The radios play the
   same click, the way the later games' radios click. */
#define VV1_SOUND_MANAGER_PTR  (*(void **)0x0048B5E8u)
#define VV1_ADDR_PLAY_SOUND    0x00431470u  /* thiscall(manager; id) ret 4 */
#define VV1_SOUND_CLICK        0x40
#define VV1_ADDR_SPRITE_CTOR   0x0040A070u  /* thiscall(this; file, cols, rows) ret 0xC */
#define VV1_SPRITE_OBJECT_SIZE 0x34
#define VV1_ADDR_SCALED_DRAW   0x00409410u  /* thiscall(wrapper; atlas, x, y, row, col, scale, flag) ret 0x1C */

/* The band (logical 800x600 pixels), measured from the owner's art: the
   strip they changed in the Details background is x 8..265, y 475..514;
   the three plates (each with its radio holder) span x 8..89, 95..176 and
   184..265 at y 496..514, and the holders are the radio sheet's blank cell
   at (62, 498), (148, 498) and (240, 498), 16x16 each (template-matched). */
#define SORT_BAND_X            8
#define SORT_BAND_Y            475
#define SORT_PLATE_Y0          496          /* the plates' rows: [Y0, Y1) */
#define SORT_PLATE_Y1          515
#define SORT_RADIO_Y           498          /* the holders' top */
#define SORT_RADIO_SIZE        16           /* the sheet's cells: 16x16 */
#define SORT_MODES             3

typedef unsigned int (__cdecl *sdl_add_event_watch_t)(void *filter, void *userdata);
typedef void *(__cdecl *sdl_get_mouse_focus_t)(void);
typedef void *(__cdecl *sdl_gl_get_current_window_t)(void);
typedef void *(__cdecl *sdl_get_renderer_t)(void *window);
typedef void (__cdecl *sdl_render_get_scale_t)(void *renderer, float *sx, float *sy);
typedef void (__cdecl *sdl_render_get_viewport_t)(void *renderer, int *rect);

static int g_mode;                        /* 0 age, 1 skill, 2 health */
static int g_position = -1;               /* position in the current list, -1 = unknown */
static int g_last_selected = -1;          /* the index this companion last handed the game */
static int g_list[VV1_RECORD_COUNT];
static int g_count;
static DWORD g_last_draw_tick;            /* when the Details band was last drawn */
static int g_seen_selection = -1;         /* the selection as of the last drawn Details frame */
static int g_watch_installed;             /* 0 no, 1 yes, -1 failed */
static void *g_band_sprite;               /* 0 untried, 1 failed, else sprite */
static void *g_radio_sprite;
static const int SORT_PLATE_X0[SORT_MODES] = { 8, 95, 184 };     /* each plate's columns: [X0, X1) */
static const int SORT_PLATE_X1[SORT_MODES] = { 90, 177, 266 };
static const int SORT_RADIO_X[SORT_MODES]  = { 62, 148, 240 };   /* each holder's left edge */


/* ---- the rule --------------------------------------------------------- */

static int vv1_key(const unsigned char *rec, int mode) {
    int k, best;
    switch (mode) {
    case 1:
        best = *(const int *)(rec + VV1_SKILLS_OFFSET);
        for (k = 1; k < VV1_SKILL_COUNT; ++k) {
            int v = *(const int *)(rec + VV1_SKILLS_OFFSET + 4u * (unsigned int)k);
            if (v > best) {
                best = v;
            }
        }
        return best;
    case 2:
        return *(const int *)(rec + VV1_HEALTH_OFFSET);
    default:
        return *(const int *)(rec + VV1_AGE_OFFSET);
    }
}

/* The living villagers in the current order: key ascending, index ascending.
   Insertion sort over at most 256 entries, once per arrow press. */
static int vv1_build_list(const unsigned char *records, int mode, int *out) {
    int keys[VV1_RECORD_COUNT];
    int n = 0, i, j;
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        const unsigned char *rec = records + (unsigned int)i * VV1_RECORD_STRIDE;
        int key;
        if (!rec[VV1_OCCUPIED_OFFSET] || *(const int *)(rec + VV1_HEALTH_OFFSET) <= 0) {
            continue;
        }
        key = vv1_key(rec, mode);
        j = n;
        while (j > 0 && keys[j - 1] > key) {   /* equal keys keep index order: i grows */
            keys[j] = keys[j - 1];
            out[j] = out[j - 1];
            --j;
        }
        keys[j] = key;
        out[j] = i;
        ++n;
    }
    return n;
}

static int vv1_position_of(const int *list, int n, int index) {
    int p;
    for (p = 0; p < n; ++p) {
        if (list[p] == index) {
            return p;
        }
    }
    return -1;
}

/* One arrow press: direction +1 (right) or -1 (left).  `current` is the
   selection before the press, `candidate` what the stock arrow chose (the
   answer when nothing can be listed).  Returns the record index to select. */
static int vv1_step(const unsigned char *records, int current, int candidate, int direction) {
    int n = vv1_build_list(records, g_mode, g_list);
    int p;
    g_count = n;
    if (n <= 0) {
        return candidate;
    }
    if (current != g_last_selected || g_position < 0 || g_position >= n) {
        /* the selection was changed by something other than these arrows (or
           the list shrank under the position): start from where the current
           villager stands in the order */
        p = vv1_position_of(g_list, n, current);
        if (p < 0) {
            p = direction > 0 ? n - 1 : 0;   /* not listed: the press lands on an end */
        }
    } else {
        p = g_position;
    }
    p = (p + (direction > 0 ? 1 : n - 1)) % n;
    g_position = p;
    g_last_selected = g_list[p];
    return g_list[p];
}

/* ---- drawing through the engine ---------------------------------------- */

typedef void *(__cdecl *vv1_new_t)(unsigned int size);

static void *vv1_sprite(void **cache, const char *file, int cols, int rows) {
    void *obj, *built = NULL;
    unsigned int f_ctor = VV1_ADDR_SPRITE_CTOR;
    if (*cache != NULL) {
        return *cache == (void *)1 ? NULL : *cache;
    }
    obj = ((vv1_new_t)VV1_ADDR_OPERATOR_NEW)(VV1_SPRITE_OBJECT_SIZE);
    if (obj == NULL) {
        *cache = (void *)1;
        return NULL;
    }
    __asm {
        push rows
        push cols
        push file
        mov  ecx, obj
        call f_ctor
        mov  built, eax
    }
    *cache = built ? built : (void *)1;
    return built;
}

static void vv1_draw_cell(void *wrapper, void *atlas, int x, int y, int row, int col, int scale) {
    unsigned int f_draw = VV1_ADDR_SCALED_DRAW;
    int flag = 1;
    if (wrapper == NULL || atlas == NULL) {
        return;
    }
    __asm {
        mov  ecx, wrapper
        push flag
        push scale
        push col
        push row
        push y
        push x
        push atlas
        call f_draw
    }
}

/* The band, then the chosen order's radio: the sheet's selected cell,
   16x16, 1:1, exactly over the holder the art carries. */
static void vv1_draw_band(void *wrapper) {
    void *band = vv1_sprite(&g_band_sprite, "vvfp_sort_band.png", 1, 1);
    void *radios = vv1_sprite(&g_radio_sprite, "vvfp_sort_radio.png", 3, 1);
    if (band != NULL) {
        vv1_draw_cell(wrapper, band, SORT_BAND_X, SORT_BAND_Y, 0, 0, 100);
    }
    if (radios != NULL && g_mode >= 0 && g_mode < SORT_MODES) {
        vv1_draw_cell(wrapper, radios, SORT_RADIO_X[g_mode], SORT_RADIO_Y, 0, 1, 100);
    }
}

/* ---- clicks ------------------------------------------------------------ */

static void vv1_play_click(void) {
    void *manager = VV1_SOUND_MANAGER_PTR;
    unsigned int f_play = VV1_ADDR_PLAY_SOUND;
    int id = VV1_SOUND_CLICK;
    if (manager == NULL) {
        return;
    }
    __asm {
        mov  ecx, manager
        push id
        call f_play
    }
}

static int vv1_hit(int x, int y) {
    int m;
    if (y < SORT_PLATE_Y0 || y >= SORT_PLATE_Y1) {
        return -1;
    }
    for (m = 0; m < SORT_MODES; ++m) {
        if (x >= SORT_PLATE_X0[m] && x < SORT_PLATE_X1[m]) {
            return m;               /* the plate, its word or its radio */
        }
    }
    return -1;
}

/* SDL 2.0.3 delivers the mouse-button event already reduced by the renderer's
   own event watcher, which runs before this companion's.  Measured against the
   running game in fullscreen, at a 1707x1068 client area with a logical size
   of 800x600, SDL reported:

       scale            1.78 on both axes
       viewport origin  x = 79, y = 0, in LOGICAL UNITS

   BOTH parts of that matter and the units are the whole point.  The scaled
   content is 800*1.78 x 600*1.78 = 1424x1068, so it fills the height exactly
   and is PILLARBOXED, not letterboxed: the y origin is genuinely 0, and the x
   margin is (1707-1424)/2 = 141.5 WINDOW PIXELS, which is 141.5/1.78 = 79.5
   LOGICAL units.  SDL_RenderGetViewport reports the rect in logical units when
   a logical size is set, which is why 79 and not 141 is what comes back, and
   why it may be added directly to a value that is already in logical space.
   Reading that 79 as window pixels reproduces nothing and sends you looking
   for a bug that is not there.

   A click on a plate arrived at

       event_x = (logical_x - viewport_x) / scale
       event_y = (logical_y - viewport_y) / scale

   so the band, which is drawn in logical 800x600 space, is hit-tested by
   INVERTING that -- multiply by the scale and add the viewport back:

       logical = event * scale + viewport

   Two worked examples, one per axis, because a single Y example proves nothing
   about X: the viewport y is 0, so the y term vanishes and an error in how the
   origin is applied would not show up there.

       y: the band draws at logical 496..515; a real fullscreen click came in
          near event y 283, and 283*1.78 + 0 = 504, back inside the band.
       x: the first plate spans logical 8..90, centre 49.  Its events arrive
          NEGATIVE, because the plate sits left of the pillarbox origin in
          logical terms: (49 - 79.5)/1.78 = -17.1, and -17.1*1.78 + 79.5 = 49.5,
          back on the plate.  Anything here that assumes a non-negative event x
          breaks the leftmost plate specifically.

   Two earlier attempts failed: one used the event coordinates raw (they are not
   in logical space in fullscreen), and one divided by the scale (the wrong
   direction -- the reduction has already happened, so the hook multiplies).
   scale and viewport are read live from SDL so the map follows any resolution;
   if SDL cannot be resolved the event is used as-is, which is correct in a
   plain window where scale is 1 and the viewport origin is 0.

   VERIFIED FULLSCREEN ONLY.  The owner confirmed this by hand in fullscreen at
   1707x1068.  A maximized window is a THIRD case, neither fullscreen nor a
   plain window, and it was never measured: see issue #403. */
static void vv1_event_to_logical(int *x, int *y) {
    HMODULE sdl = GetModuleHandleA("SDL2.dll");
    sdl_get_mouse_focus_t get_focus;
    sdl_gl_get_current_window_t get_current;
    sdl_get_renderer_t get_renderer;
    sdl_render_get_scale_t get_scale;
    sdl_render_get_viewport_t get_viewport;
    void *window, *renderer;
    float sx = 1.0f, sy = 1.0f;
    int viewport[4] = { 0, 0, 0, 0 };
    if (sdl == NULL) {
        return;
    }
    get_focus = (sdl_get_mouse_focus_t)GetProcAddress(sdl, "SDL_GetMouseFocus");
    get_current = (sdl_gl_get_current_window_t)GetProcAddress(sdl, "SDL_GL_GetCurrentWindow");
    get_renderer = (sdl_get_renderer_t)GetProcAddress(sdl, "SDL_GetRenderer");
    get_scale = (sdl_render_get_scale_t)GetProcAddress(sdl, "SDL_RenderGetScale");
    get_viewport = (sdl_render_get_viewport_t)GetProcAddress(sdl, "SDL_RenderGetViewport");
    if (get_renderer == NULL || get_scale == NULL) {
        return;                     /* cannot map: leave the event as-is */
    }
    window = get_focus ? get_focus() : NULL;
    if (window == NULL && get_current != NULL) {
        window = get_current();     /* the cursor may be outside the window */
    }
    if (window == NULL) {
        return;
    }
    renderer = get_renderer(window);
    if (renderer == NULL) {
        return;
    }
    get_scale(renderer, &sx, &sy);
    if (sx <= 0.0f || sy <= 0.0f) {
        return;
    }
    if (get_viewport != NULL) {
        get_viewport(renderer, viewport);
    }
    *x = (int)((float)*x * sx) + viewport[0];
    *y = (int)((float)*y * sy) + viewport[1];
}

static int __cdecl vv1_event_watch(void *userdata, void *event) {
    const unsigned char *e = (const unsigned char *)event;
    (void)userdata;
    if (e != NULL && *(const unsigned int *)e == 0x401u && e[16] == 1
        && GetTickCount() - g_last_draw_tick < 250u) {
        int x = *(const int *)(e + 20);
        int y = *(const int *)(e + 24);
        int hit;
        vv1_event_to_logical(&x, &y);
        hit = vv1_hit(x, y);
        if (hit >= 0) {
            g_mode = hit;              /* the position is kept, as in the later games */
            vv1_play_click();
        }
    }
    return 1;
}

static void vv1_install_watch(void) {
    HMODULE sdl;
    sdl_add_event_watch_t add;
    if (g_watch_installed != 0) {
        return;
    }
    sdl = GetModuleHandleA("SDL2.dll");
    add = sdl ? (sdl_add_event_watch_t)GetProcAddress(sdl, "SDL_AddEventWatch") : NULL;
    if (add == NULL) {
        g_watch_installed = -1;
        return;
    }
    add((void *)vv1_event_watch, NULL);
    g_watch_installed = 1;
}

/* ---- exports (the game) ----------------------------------------------- */

/* From the Origins companion's Vv1SortStep, which the executable's two arrow
   stubs call with the stock candidate and the direction (+1 right, -1 left).
   Returns the record index to select. */
__declspec(dllexport) int __stdcall Vv1SortByStep(int candidate, int direction) {
    unsigned char *state = VV1_VILLAGE_STATE_PTR;
    unsigned char *records = VV1_VILLAGERS_PTR;
    int current;
    if (state == NULL || records == NULL) {
        return candidate;
    }
    /* The stock arrow clears the selection (0x4393E0 writes -1) just before
       the store this hook replaces, so the field no longer says where the
       player was; the draw hook saw it on the last frame. */
    current = *(const int *)(state + VV1_SELECTED_OFFSET);
    if (current < 0) {
        current = g_seen_selection;
    }
    return vv1_step(records, current, candidate, direction);
}

/* From the Origins companion's Details portrait hook, once per rendered
   Details frame.  Draws the band and arms the click watch. */
__declspec(dllexport) int __stdcall Vv1SortByDraw(void *gameobj, void *record, void *draw_wrapper, const int *args) {
    unsigned char *state = VV1_VILLAGE_STATE_PTR;
    (void)gameobj; (void)record; (void)args;
    if (draw_wrapper == NULL) {
        return 0;
    }
    vv1_install_watch();
    g_last_draw_tick = GetTickCount();
    if (state != NULL) {
        g_seen_selection = *(const int *)(state + VV1_SELECTED_OFFSET);
    }
    vv1_draw_band(draw_wrapper);
    return 1;
}

__declspec(dllexport) int __stdcall Vv1SortByMode(void) {
    return g_mode;
}

/* ---- exports (test seams: caller-supplied records, no game globals) ------ */

__declspec(dllexport) int __stdcall Vv1SortByProbeReset(int mode) {
    g_mode = (mode >= 0 && mode < SORT_MODES) ? mode : 0;
    g_position = -1;
    g_last_selected = -1;
    return 1;
}

__declspec(dllexport) int __stdcall Vv1SortByProbeSetMode(int mode) {
    if (mode < 0 || mode >= SORT_MODES) {
        return 0;
    }
    g_mode = mode;             /* the position is kept, as in the later games */
    return 1;
}

__declspec(dllexport) int __stdcall Vv1SortByProbeStep(const void *records, int current, int candidate, int direction) {
    if (records == NULL) {
        return candidate;
    }
    return vv1_step((const unsigned char *)records, current, candidate, direction);
}

/* The whole order for a mode: out[cap], returns the count. */
__declspec(dllexport) int __stdcall Vv1SortByProbeList(const void *records, int mode, int *out, int cap) {
    int list[VV1_RECORD_COUNT];
    int n, i;
    if (records == NULL || out == NULL || mode < 0 || mode >= SORT_MODES) {
        return 0;
    }
    n = vv1_build_list((const unsigned char *)records, mode, list);
    for (i = 0; i < n && i < cap; ++i) {
        out[i] = list[i];
    }
    return n;
}

__declspec(dllexport) int __stdcall Vv1SortByProbeHit(int x, int y) {
    return vv1_hit(x, y);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
