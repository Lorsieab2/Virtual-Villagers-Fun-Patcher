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

   ART.  The owner's own, after their mockup: Images/vvfp_sort_title.png (the
   "Sort By:" plate), Images/vvfp_sort_age.png, vvfp_sort_skill.png and
   vvfp_sort_health.png (one plate each, words included), and
   Images/vvfp_sort_radio.png (a sheet of three cells: 0 blank, 1 selected;
   The Lost Children's detailradiobtn.png).  Every image is drawn 1:1 at
   the mockup's spot through the engine's own draw (0x409410), and the
   sizes come from the images themselves (the sprite's cell size), so the
   art can change without touching this code.  The words -- "Sort By:",
   "Age", "Skill", "Health" -- are the game's own font at 70%, centred on
   each plate in the Details labels' brown, so they fit inside the plates
   (the engine's text wrappers only draw at full size; the glyphs are
   blitted here through its scaled blit). */
#include <windows.h>
#include <string.h>

#define VV1_VILLAGE_STATE_PTR  (*(unsigned char **)0x0048AEDCu)
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
/* The pieces of the engine's text draw (0x409160), replayed here at a scale
   the wrappers never expose: the font's implementation object is [font+4],
   its glyph-rect method is vtable slot 1 (thiscall(impl; char, rect*)),
   0x402510 (thiscall(impl; colour)) hands back the glyph sheet tinted to
   the colour, and 0x403D70 is the scaled blit the sprites use. */
#define VV1_RENDERER_FONT      0x5Cu        /* renderer: the default font */
#define VV1_FONT_IMPL          0x4u         /* font: its implementation object */
#define VV1_FONT_IMPL_SURFACE  0xCu         /* impl: the glyph sheet holder, NULL = no glyphs */
#define VV1_ADDR_FONT_SURFACE  0x00402510u  /* thiscall(impl; colour) -> SDL_Surface* */
#define VV1_ADDR_BLIT          0x00403D70u  /* thiscall(renderer; surface, x, y, x1, y1, x2, y2, alpha, scale, flag) ret 0x28 */

/* The band under the Age/Gender boxes and above the villager strip
   (logical 800x600): x 8..280, y 466..521.  Two rows like the owner's mockup:
   "Sort By:" centred above, then plate+radio for each order. */
#define SORT_TITLE_X           85           /* the mockup: title plate top-left */
#define SORT_TITLE_Y           474
#define SORT_ROW_Y             499          /* top of the plates and radios */
#define SORT_FIRST_PLATE_X     6
#define SORT_GROUP_STEP        88           /* plate start to next plate start: 6, 94, 182 */
#define SORT_RADIO_GAP         4            /* plate right edge to radio */
#define SORT_DEFAULT_PLATE_W   60           /* until the art is loaded (the harness) */
#define SORT_DEFAULT_PLATE_H   18
#define SORT_DEFAULT_RADIO_W   32
#define SORT_SPRITE_CELL_W     0x10u        /* sprite object: cell width, height */
#define SORT_SPRITE_CELL_H     0x14u
#define SORT_TEXT_SCALE        70           /* percent of the font's size: fits the plates */
#define SORT_TEXT_COLOUR       0xFF002144u  /* the Details labels' brown (68,33,0): the engine reads the word as A,B,G,R */
#define SORT_TEXT_DY           2            /* the words' top inside a plate */
#define SORT_MODES             3

typedef unsigned int (__cdecl *sdl_add_event_watch_t)(void *filter, void *userdata);

static int g_mode;                        /* 0 age, 1 skill, 2 health */
static int g_position = -1;               /* position in the current list, -1 = unknown */
static int g_last_selected = -1;          /* the index this companion last handed the game */
static int g_list[VV1_RECORD_COUNT];
static int g_count;
static DWORD g_last_draw_tick;            /* when the Details band was last drawn */
static int g_seen_selection = -1;         /* the selection as of the last drawn Details frame */
static int g_watch_installed;             /* 0 no, 1 yes, -1 failed */
static void *g_plate_sprite[SORT_MODES];  /* 0 untried, 1 failed, else sprite */
static void *g_title_sprite;
static void *g_radio_sprite;
static const char *const SORT_PLATE_FILES[SORT_MODES] = { "vvfp_sort_age.png", "vvfp_sort_skill.png", "vvfp_sort_health.png" };
static const char *const SORT_WORDS[SORT_MODES] = { "Age", "Skill", "Health" };


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

/* One glyph through the scaled blit: (x, y) is the top-left of the scaled
   glyph (flag 0: no centring). */
static void vv1_blit_glyph(void *renderer, void *surface, int x, int y, int x1, int y1, int x2, int y2, float scale) {
    unsigned int f_blit = VV1_ADDR_BLIT;
    unsigned int alpha_bits, scale_bits;
    float alpha = 1.0f;
    int flag = 0;
    memcpy(&alpha_bits, &alpha, 4);
    memcpy(&scale_bits, &scale, 4);
    __asm {
        mov  ecx, renderer
        push flag
        push scale_bits
        push alpha_bits
        push y2
        push x2
        push y1
        push x1
        push y
        push x
        push surface
        call f_blit
    }
}

static int vv1_glyph_rect(void *impl, int c, int *rect) {
    void *vt = *(void **)impl;
    unsigned int f = *(unsigned int *)((unsigned char *)vt + 4);
    rect[0] = rect[1] = rect[2] = rect[3] = 0;
    __asm {
        mov  ecx, impl
        push rect
        push c
        call f                 /* thiscall(impl; char, rect*) */
    }
    return rect[2] - rect[0];
}

/* The engine's text draw (0x409160) at a scale: same font, same glyph
   rects, same tinted glyph sheet, each glyph blitted through 0x403D70 with
   our scale instead of the 1.0 the wrappers hardcode.  Centred on
   centre_x; y is the top of the scaled text. */
static void vv1_draw_text_scaled(void *wrapper, const char *text, int centre_x, int y, unsigned int colour, int percent) {
    unsigned char *renderer = *(unsigned char **)wrapper;
    unsigned char *font, *impl;
    void *surface = NULL;
    unsigned int f_surface = VV1_ADDR_FONT_SURFACE;
    float scale = (float)percent / 100.0f;
    int rect[4];
    int width = 0, x;
    const char *s;
    if (renderer == NULL || text == NULL) {
        return;
    }
    font = *(unsigned char **)(renderer + VV1_RENDERER_FONT);
    if (font == NULL) {
        return;
    }
    impl = *(unsigned char **)(font + VV1_FONT_IMPL);
    if (impl == NULL || *(void **)(impl + VV1_FONT_IMPL_SURFACE) == NULL) {
        return;
    }
    __asm {
        mov  ecx, impl
        push colour
        call f_surface         /* thiscall(impl; colour) */
        mov  surface, eax
    }
    if (surface == NULL) {
        return;
    }
    for (s = text; *s; ++s) {
        width += vv1_glyph_rect(impl, (int)(signed char)*s, rect) * percent / 100;
    }
    x = centre_x - width / 2;
    for (s = text; *s; ++s) {
        int w = vv1_glyph_rect(impl, (int)(signed char)*s, rect);
        if (w > 0) {
            vv1_blit_glyph(renderer, surface, x, y, rect[0], rect[1], rect[2], rect[3], scale);
            x += w * percent / 100;
        }
    }
}

static int vv1_sprite_size(void *sprite, int *w, int *h, int default_w, int default_h) {
    if (sprite == NULL) {
        *w = default_w; *h = default_h;
        return 0;
    }
    *w = *(const int *)((unsigned char *)sprite + SORT_SPRITE_CELL_W);
    *h = *(const int *)((unsigned char *)sprite + SORT_SPRITE_CELL_H);
    if (*w <= 0 || *h <= 0 || *w > 400 || *h > 100) {
        *w = default_w; *h = default_h;
    }
    return 1;
}

/* Where each order's plate and radio sit (logical pixels), from the art. */
static void vv1_group_rects(int mode, int *plate_x, int *plate_w, int *plate_h, int *radio_x, int *radio_w) {
    int rh;
    void *plate = (g_plate_sprite[mode] == (void *)1) ? NULL : g_plate_sprite[mode];
    void *radio = (g_radio_sprite == (void *)1) ? NULL : g_radio_sprite;
    vv1_sprite_size(plate, plate_w, plate_h, SORT_DEFAULT_PLATE_W, SORT_DEFAULT_PLATE_H);
    vv1_sprite_size(radio, radio_w, &rh, SORT_DEFAULT_RADIO_W, SORT_DEFAULT_RADIO_W);
    *plate_x = SORT_FIRST_PLATE_X + mode * SORT_GROUP_STEP;
    *radio_x = *plate_x + *plate_w + SORT_RADIO_GAP;
}

static void vv1_draw_band(void *wrapper) {
    void *title = vv1_sprite(&g_title_sprite, "vvfp_sort_title.png", 1, 1);
    void *radios = vv1_sprite(&g_radio_sprite, "vvfp_sort_radio.png", 3, 1);
    int m;
    if (title != NULL) {
        int tw, th;
        vv1_sprite_size(title, &tw, &th, 74, 23);
        vv1_draw_cell(wrapper, title, SORT_TITLE_X, SORT_TITLE_Y, 0, 0, 100);
        vv1_draw_text_scaled(wrapper, "Sort By:", SORT_TITLE_X + tw / 2, SORT_TITLE_Y + SORT_TEXT_DY + 1, SORT_TEXT_COLOUR, SORT_TEXT_SCALE);
    }
    for (m = 0; m < SORT_MODES; ++m) {
        int px, pw, ph, rx, rw;
        void *plate = vv1_sprite(&g_plate_sprite[m], SORT_PLATE_FILES[m], 1, 1);
        vv1_group_rects(m, &px, &pw, &ph, &rx, &rw);
        if (plate != NULL) {
            vv1_draw_cell(wrapper, plate, px, SORT_ROW_Y, 0, 0, 100);
            vv1_draw_text_scaled(wrapper, SORT_WORDS[m], px + pw / 2, SORT_ROW_Y + SORT_TEXT_DY, SORT_TEXT_COLOUR, SORT_TEXT_SCALE);
        }
        if (radios != NULL) {
            vv1_draw_cell(wrapper, radios, rx, SORT_ROW_Y + (ph - rw) / 2, 0, m == g_mode ? 1 : 0, 100);
        }
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
    for (m = 0; m < SORT_MODES; ++m) {
        int px, pw, ph, rx, rw;
        vv1_group_rects(m, &px, &pw, &ph, &rx, &rw);
        if (y >= SORT_ROW_Y - 2 && y < SORT_ROW_Y + ph + 2 && x >= px - 2 && x < rx + rw + 2) {
            return m;
        }
    }
    return -1;
}

/* SDL 2.0.3 SDL_MouseButtonEvent: type +0 (0x401 = SDL_MOUSEBUTTONDOWN),
   button +16 (1 = left), x +20, y +24 -- the same window coordinates the
   game itself uses for its buttons. */
static int __cdecl vv1_event_watch(void *userdata, void *event) {
    const unsigned char *e = (const unsigned char *)event;
    (void)userdata;
    if (e != NULL && *(const unsigned int *)e == 0x401u && e[16] == 1
        && GetTickCount() - g_last_draw_tick < 250u) {
        int hit = vv1_hit(*(const int *)(e + 20), *(const int *)(e + 24));
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
