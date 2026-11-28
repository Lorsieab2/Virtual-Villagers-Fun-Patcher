/* VVFP Fullscreen Mouse -- Fix Vanilla Bugs (all five games): in full screen, or in any game window that is not
   exactly the game's own size, the mouse acts where the pointer is.

   THE STOCK GAMES.  All five draw at a fixed size (A New Home, The Lost Children, The Secret City and The Tree of
   Life 800x600, New Believers 1024x768) and let SDL 2.0.3 stretch that picture over the window
   (SDL_RenderSetLogicalSize), with black bars at the sides when the window is wider than 4:3 -- full screen ("full
   screen desktop", the whole monitor), a maximized window, a window dragged bigger.  SDL also converts the
   coordinates in its mouse EVENTS to the game's own pixels (its renderer's event watch, SDL2.dll RVA 0xBBF0B:
   x = (x - viewport.x) / scale.x).  But the games do not read the events' coordinates: on every mouse move, button
   press and release their event pump asks SDL_GetMouseState (A New Home 0x403BFC / 0x403C2B / 0x403C53, The Lost
   Children 0x403E8C..., The Secret City 0x4044AC..., The Tree of Life 0x404A90..., New Believers 0x404A20 /
   0x404A4F / 0x404A77), and SDL 2.0.3 answers that in WINDOW pixels, not converted.  So whenever the window is
   bigger than the game's picture, the game believes the mouse is further right and further down than it is: on a
   1920x1080 full screen New Believers reads (960, 540) for the middle of the screen, which is (512, 384) in its
   own picture -- its pointer runs ahead of the hand and leaves the picture at the right and bottom edges, and
   clicks land on the wrong things.  A window of exactly the game's size (scale 1, no bars) is the only case that
   works.

   WHAT THIS COMPANION DOES.  It replaces three of the game's own imports from SDL2.dll (its import table entries;
   no byte of the game's code or of SDL2.dll is written):
     SDL_CreateRenderer     -- unchanged, but remembers the renderer the game makes;
     SDL_GetMouseState      -- converts SDL's answer exactly as SDL converts its own events (the renderer's viewport
                               and scale), then keeps it inside the game's picture (the bars count as its nearest
                               edge, as the edge of the window always did); buttons unchanged;
     SDL_WarpMouseInWindow  -- the reverse: the game moves the pointer (60 frames after the full screen key, back to
                               where it was) in its own pixels, so the pointer lands on the same spot of the picture.
   A window of the game's own size converts to the same numbers, so nothing changes there.  Companions that ask
   SDL2.dll directly still get window pixels; one that wants the game's numbers reads them through the game's own
   import (VVFP VV1 Parentage.dll does), so nothing is converted twice.

   ALL OR NONE.  Installed only when SDL2.dll is loaded, reports version 2.0.3 and holds the stock bytes of the event
   watch's mouse-motion conversion (the viewport and scale it reads are the ones this companion reads); and the
   game's three SDL_GetMouseState calls in its event pump are calls of its own import of that name, every one of
   the three imports still holds SDL2.dll's own address.  Otherwise nothing is changed.  Started by "VVFP Window
   Restore.dll" (the Fix Vanilla Bugs rows ship both), before WinMain, on the game's own thread.  No file, no text,
   no save data, no debug output. */
#include <windows.h>
#include <math.h>

typedef struct {
    unsigned char major, minor, patch;
} fm_sdl_version;
typedef void(__cdecl *fm_get_version_fn)(fm_sdl_version *);
typedef void *(__cdecl *fm_create_renderer_fn)(void *, int, unsigned int);
typedef unsigned int(__cdecl *fm_mouse_state_fn)(int *, int *);
typedef void(__cdecl *fm_warp_fn)(void *, int, int);
typedef void *(__cdecl *fm_get_renderer_fn)(void *);
typedef void(__cdecl *fm_logical_size_fn)(void *, int *, int *);

/* SDL_Renderer (2.0.3): logical_w, the viewport (x, y in window pixels) and the scale, as the event watch reads
   them (pinned by FM_WATCH below). */
#define FM_LOGICAL_W 0xC4
#define FM_VIEWPORT_X 0xD4
#define FM_VIEWPORT_Y 0xD8
#define FM_SCALE_X 0x114
#define FM_SCALE_Y 0x118

/* SDL_RendererEventWatch, case SDL_MOUSEMOTION (RVA 0xBBF0B): with a logical size, x -= viewport.x (+0xD4),
   y -= viewport.y (+0xD8), x /= scale.x (+0x114), y /= scale.y (+0x118), each truncated. */
static const unsigned char FM_WATCH[] = {
    0x8B, 0x4D, 0x0C, 0x81, 0x39, 0x00, 0x04, 0x00, 0x00, 0x0F, 0x85, 0xA3, 0x01, 0x00, 0x00, 0x8B, 0x55, 0xFC,
    0x83, 0xBA, 0xC4, 0x00, 0x00, 0x00, 0x00, 0x0F, 0x84, 0x8E, 0x01, 0x00, 0x00, 0x8B, 0x45, 0x0C, 0x8B, 0x4D,
    0xFC, 0x8B, 0x50, 0x14, 0x2B, 0x91, 0xD4, 0x00, 0x00, 0x00, 0x8B, 0x45, 0x0C, 0x89, 0x50, 0x14, 0x8B, 0x4D,
    0x0C, 0x8B, 0x55, 0xFC, 0x8B, 0x41, 0x18, 0x2B, 0x82, 0xD8, 0x00, 0x00, 0x00, 0x8B, 0x4D, 0x0C, 0x89, 0x41,
    0x18, 0x8B, 0x55, 0x0C, 0xDB, 0x42, 0x14, 0x8B, 0x45, 0xFC, 0xD8, 0xB0, 0x14, 0x01, 0x00, 0x00,
};
#define FM_WATCH_RVA 0xBBF0Bu
#define FM_WATCH_Y_RVA 0xBBF6Eu   /* fild [edx+0x18]; fdiv [eax+0x118] */
static const unsigned char FM_WATCH_Y[] = {
    0x8B, 0x55, 0x0C, 0xDB, 0x42, 0x18, 0x8B, 0x45, 0xFC, 0xD8, 0xB0, 0x18, 0x01, 0x00, 0x00,
};

/* The event pump's three SDL_GetMouseState calls (motion, button down, button up), per game. */
static const unsigned int FM_PUMP_CALLS[5][3] = {
    {0x403BFC, 0x403C2B, 0x403C53}, /* A New Home */
    {0x403E8C, 0x403EBB, 0x403EE3}, /* The Lost Children */
    {0x4044AC, 0x4044DB, 0x404503}, /* The Secret City */
    {0x404A90, 0x404ABF, 0x404AE7}, /* The Tree of Life */
    {0x404A20, 0x404A4F, 0x404A77}, /* New Believers */
};

static fm_create_renderer_fn g_create_renderer;
static fm_mouse_state_fn g_mouse_state;
static fm_warp_fn g_warp;
static fm_get_renderer_fn g_get_renderer;
static fm_logical_size_fn g_logical_size;
static void *volatile g_renderer;
static int g_installed;
#ifdef VVFP_TEST
static HMODULE g_test_module;   /* the harness's copy of the game, instead of this process's executable */
#endif

/* 1 when the SDL2.dll in this process is 2.0.3 with the stock event watch bytes. */
static HMODULE fm_sdl(void) {
    HMODULE sdl = GetModuleHandleA("SDL2.dll");
    const unsigned char *base;
    const IMAGE_NT_HEADERS *nt;
    fm_get_version_fn get_version;
    fm_sdl_version version;
    unsigned int i;
    if (sdl == NULL) {
        return NULL;
    }
    get_version = (fm_get_version_fn)GetProcAddress(sdl, "SDL_GetVersion");
    if (get_version == NULL) {
        return NULL;
    }
    version.major = version.minor = version.patch = 0;
    get_version(&version);
    if (version.major != 2 || version.minor != 0 || version.patch != 3) {
        return NULL;
    }
    base = (const unsigned char *)sdl;
    if (((const IMAGE_DOS_HEADER *)base)->e_magic != IMAGE_DOS_SIGNATURE) {
        return NULL;
    }
    nt = (const IMAGE_NT_HEADERS *)(base + ((const IMAGE_DOS_HEADER *)base)->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || FM_WATCH_RVA + sizeof FM_WATCH > nt->OptionalHeader.SizeOfImage ||
        FM_WATCH_Y_RVA + sizeof FM_WATCH_Y > nt->OptionalHeader.SizeOfImage) {
        return NULL;
    }
    for (i = 0; i < sizeof FM_WATCH; ++i) {
        if (base[FM_WATCH_RVA + i] != FM_WATCH[i]) {
            return NULL;
        }
    }
    for (i = 0; i < sizeof FM_WATCH_Y; ++i) {
        if (base[FM_WATCH_Y_RVA + i] != FM_WATCH_Y[i]) {
            return NULL;
        }
    }
    return sdl;
}

/* The import table entry for SDL2.dll's `name` in `module`, or NULL. */
static void **fm_import(HMODULE module, const char *name) {
    const unsigned char *base = (const unsigned char *)module;
    const IMAGE_NT_HEADERS *nt = (const IMAGE_NT_HEADERS *)(base + ((const IMAGE_DOS_HEADER *)base)->e_lfanew);
    const IMAGE_DATA_DIRECTORY *dir = &nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    const IMAGE_IMPORT_DESCRIPTOR *d;
    if (dir->VirtualAddress == 0) {
        return NULL;
    }
    for (d = (const IMAGE_IMPORT_DESCRIPTOR *)(base + dir->VirtualAddress); d->Name != 0; ++d) {
        const IMAGE_THUNK_DATA *names;
        IMAGE_THUNK_DATA *slots;
        if (lstrcmpiA((const char *)(base + d->Name), "SDL2.dll") != 0 || d->OriginalFirstThunk == 0) {
            continue;
        }
        names = (const IMAGE_THUNK_DATA *)(base + d->OriginalFirstThunk);
        slots = (IMAGE_THUNK_DATA *)(base + d->FirstThunk);
        for (; names->u1.AddressOfData != 0; ++names, ++slots) {
            if (IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal)) {
                continue;
            }
            if (lstrcmpA((const char *)((const IMAGE_IMPORT_BY_NAME *)(base + names->u1.AddressOfData))->Name,
                         name) == 0) {
                return (void **)&slots->u1.Function;
            }
        }
    }
    return NULL;
}

/* 1 when `site` is `call <thunk>` and the thunk is `jmp dword ptr [slot]`. */
static int fm_calls_slot(unsigned int site, void **slot) {
    const unsigned char *s = (const unsigned char *)(UINT_PTR)site;
    const unsigned char *thunk;
    if (s[0] != 0xE8) {
        return 0;
    }
    thunk = s + 5 + *(const int *)(s + 1);
    return thunk[0] == 0xFF && thunk[1] == 0x25 && *(void *const *)(thunk + 2) == (void *)slot;
}

static void fm_set(void **slot, void *value) {
    DWORD old;
    if (VirtualProtect(slot, sizeof *slot, PAGE_READWRITE, &old)) {
        *slot = value;
        VirtualProtect(slot, sizeof *slot, old, &old);
    }
}

typedef int(__stdcall *fm_picture_fn)(int *, int *, int *, int *);

/* While "VVFP Sharp Picture.dll" (the 4K filter) draws the game's picture itself, the picture's place in the window
   is its own (black bars or stretched), not SDL's viewport: it says where (x, y, w, h in window pixels). */
static int fm_picture(int *x, int *y, int *w, int *h) {
    static fm_picture_fn picture;
    if (picture == NULL) {
        HMODULE sharp = GetModuleHandleA("VVFP Sharp Picture.dll");   /* only if it is already loaded */
        if (sharp == NULL) {
            return 0;
        }
        picture = (fm_picture_fn)GetProcAddress(sharp, "VvfpSharpPictureRect");
        if (picture == NULL) {
            return 0;
        }
    }
    return picture(x, y, w, h) && *w > 0 && *h > 0;
}

/* The window pixels SDL keeps -> the game's own pixels, exactly as SDL's event watch converts its events; inside
   the game's picture.  Without a logical size (never, in these games) nothing changes. */
static void fm_to_game(int *x, int *y) {
    const unsigned char *r = (const unsigned char *)g_renderer;
    int w = 0, h = 0, px, py, pw, ph;
    float sx, sy;
    if (r == NULL || *(const int *)(r + FM_LOGICAL_W) == 0) {
        return;
    }
    if (fm_picture(&px, &py, &pw, &ph)) {
        g_logical_size(g_renderer, &w, &h);
        if (x != NULL) {
            int v = (int)floor((double)(*x - px) * (double)w / (double)pw);
            *x = v < 0 ? 0 : (v >= w ? w - 1 : v);
        }
        if (y != NULL) {
            int v = (int)floor((double)(*y - py) * (double)h / (double)ph);
            *y = v < 0 ? 0 : (v >= h ? h - 1 : v);
        }
        return;
    }
    sx = *(const float *)(r + FM_SCALE_X);
    sy = *(const float *)(r + FM_SCALE_Y);
    if (!(sx > 0.0f) || !(sy > 0.0f)) {
        return;
    }
    g_logical_size(g_renderer, &w, &h);
    if (x != NULL) {
        int v = (int)((double)(*x - *(const int *)(r + FM_VIEWPORT_X)) / (double)sx);
        *x = v < 0 ? 0 : (v >= w ? w - 1 : v);
    }
    if (y != NULL) {
        int v = (int)((double)(*y - *(const int *)(r + FM_VIEWPORT_Y)) / (double)sy);
        *y = v < 0 ? 0 : (v >= h ? h - 1 : v);
    }
}

/* The game's own pixels -> window pixels: the middle of that game pixel on the screen. */
static void fm_to_window(void *renderer, int *x, int *y) {
    const unsigned char *r = (const unsigned char *)renderer;
    float sx, sy;
    int px, py, pw, ph, w = 0, h = 0;
    if (r == NULL || *(const int *)(r + FM_LOGICAL_W) == 0) {
        return;
    }
    if (fm_picture(&px, &py, &pw, &ph)) {
        double ax, ay;
        g_logical_size(renderer, &w, &h);
        if (w <= 0 || h <= 0) {
            return;
        }
        ax = (double)pw / w;
        ay = (double)ph / h;
        *x = px + (int)ceil((double)*x * ax + (ax > 1.0 ? (ax - 1.0) * 0.5 : 0.0));
        *y = py + (int)ceil((double)*y * ay + (ay > 1.0 ? (ay - 1.0) * 0.5 : 0.0));
        return;
    }
    sx = *(const float *)(r + FM_SCALE_X);
    sy = *(const float *)(r + FM_SCALE_Y);
    if (!(sx > 0.0f) || !(sy > 0.0f)) {
        return;
    }
    /* The window pixels of game pixel x are those from x * scale (inclusive) to (x + 1) * scale: the whole one
       nearest their middle (the scale is at least 1 -- the window is never smaller than the game's picture). */
    *x = *(const int *)(r + FM_VIEWPORT_X) + (int)ceil((double)*x * sx + ((double)sx - 1.0) * 0.5);
    *y = *(const int *)(r + FM_VIEWPORT_Y) + (int)ceil((double)*y * sy + ((double)sy - 1.0) * 0.5);
}

static void *__cdecl fm_create_renderer(void *window, int index, unsigned int flags) {
    void *renderer = g_create_renderer(window, index, flags);
    if (renderer != NULL && g_renderer == NULL) {
        g_renderer = renderer;
    }
    return renderer;
}

static unsigned int __cdecl fm_mouse_state(int *x, int *y) {
    unsigned int buttons = g_mouse_state(x, y);
    __try {
        fm_to_game(x, y);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return buttons;
}

static void __cdecl fm_warp(void *window, int x, int y) {
    __try {
        void *renderer = g_get_renderer(window);
        fm_to_window(renderer != NULL ? renderer : g_renderer, &x, &y);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    g_warp(window, x, y);
}

/* 1 when the hooks are installed (for the tests), else 0. */
int __stdcall VvfpFullscreenMouseInstalled(void) {
    return g_installed;
}

#ifdef VVFP_TEST
/* The harness runs a copy of the game's own code mapped into its process: look at that copy's imports. */
void __stdcall VvfpFullscreenMouseTestUseModule(HMODULE module) {
    g_test_module = module;
}

/* The two conversions, for the harness: 1 = window -> game, 0 = game -> window. */
void __stdcall VvfpFullscreenMouseTestConvert(int to_game, int *x, int *y) {
    if (to_game) {
        fm_to_game(x, y);
    } else {
        fm_to_window(g_renderer, x, y);
    }
}
#endif

/* Called by VVFP Window Restore.dll before WinMain, on the game's own thread. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    HMODULE sdl, module;
    void **create_slot, **state_slot, **warp_slot;
    int i;
    (void)shipped;
    if (g_installed || game < 1 || game > 5) {
        return;
    }
    sdl = fm_sdl();
    if (sdl == NULL) {
        return;
    }
    module = GetModuleHandleW(NULL);
#ifdef VVFP_TEST
    if (g_test_module != NULL) {
        module = g_test_module;
    }
#endif
    g_get_renderer = (fm_get_renderer_fn)GetProcAddress(sdl, "SDL_GetRenderer");
    g_logical_size = (fm_logical_size_fn)GetProcAddress(sdl, "SDL_RenderGetLogicalSize");
    create_slot = fm_import(module, "SDL_CreateRenderer");
    state_slot = fm_import(module, "SDL_GetMouseState");
    warp_slot = fm_import(module, "SDL_WarpMouseInWindow");
    if (g_get_renderer == NULL || g_logical_size == NULL || create_slot == NULL || state_slot == NULL ||
        warp_slot == NULL) {
        return;
    }
    if (*create_slot != (void *)GetProcAddress(sdl, "SDL_CreateRenderer") ||
        *state_slot != (void *)GetProcAddress(sdl, "SDL_GetMouseState") ||
        *warp_slot != (void *)GetProcAddress(sdl, "SDL_WarpMouseInWindow")) {
        return;   /* not SDL2.dll's own any more: someone else's hook */
    }
    for (i = 0; i < 3; ++i) {
        if (!fm_calls_slot(FM_PUMP_CALLS[game - 1][i], state_slot)) {
            return;
        }
    }
    g_create_renderer = (fm_create_renderer_fn)*create_slot;
    g_mouse_state = (fm_mouse_state_fn)*state_slot;
    g_warp = (fm_warp_fn)*warp_slot;
    fm_set(create_slot, (void *)fm_create_renderer);
    fm_set(state_slot, (void *)fm_mouse_state);
    fm_set(warp_slot, (void *)fm_warp);
    g_installed = 1;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
