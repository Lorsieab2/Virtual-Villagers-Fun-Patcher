/* VVFP Window Restore -- Fix Vanilla Bugs (all five games): the picture no longer freezes after the game window
   comes back from being minimized as a maximized window or in full screen.

   The owner (2026-11-26): "fix the bug that makes the game appear to freeze when a person goes out of full sceeen
   and back (includes fully maxed window version)" -- "the screen freezes but the game keeps playing. when going back
   to it again it is fixed but not in fullscreen only windowed".

   THE STOCK GAMES.  All five draw through SDL 2.0.3 (SDL2.dll, FileVersion 2.0.3.0, the same file in every game):
   each frame the game copies its picture into one streaming texture and calls SDL_RenderClear, SDL_RenderCopy and
   SDL_RenderPresent (A New Home 0x403830 from the main loop 0x409145; The Lost Children 0x403AC0; The Secret City
   0x4040E0; The Tree of Life 0x4046F0; New Believers 0x404680), whatever the window is doing.  SDL skips all
   drawing while its renderer is marked hidden (SDL_RenderPresent: `if (renderer->hidden) return;`, renderer+0xC0).
   The renderer's window-event watch (SDL2.dll RVA 0xBBD30) marks it hidden on SDL_WINDOWEVENT_MINIMIZED and clears
   the mark ONLY on SDL_WINDOWEVENT_SHOWN or SDL_WINDOWEVENT_RESTORED (RVA 0xBBEC1..0xBBF06).  Windows reports a window
   that comes back from the taskbar as maximized with WM_SIZE / SIZE_MAXIMIZED, which SDL 2.0.3 turns into
   SDL_WINDOWEVENT_MAXIMIZED alone (its WM_SIZE switch, RVA 0xECBF9); and SDL_WINDOWEVENT_MAXIMIZED neither clears
   SDL's own "minimized" flag nor reaches the renderer (RVA 0xEB3B0: when the window already counts as maximized the
   event is dropped).  So after a maximized window is minimized and brought back the renderer stays hidden: the
   picture stops while the game keeps playing.  In full screen ("full screen desktop", 0x1001) SDL 2.0.3 minimizes
   the window as soon as it loses focus (SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS defaults on) and keeps a maximized
   window's WS_MAXIMIZE style in full screen, so a game made full screen from a maximized window freezes on every
   alt-tab and back; and as SDL then believes the window is still minimized, the next alt-tab no longer minimizes it
   and nothing clears the mark while it stays full screen.  Un-maximizing a window (SIZE_RESTORED) is the only stock
   way out -- the owner's "fixed ... only windowed".  Later SDL versions fixed this the same way this companion does:
   on SIZE_MAXIMIZED they send SDL_WINDOWEVENT_RESTORED first, then SDL_WINDOWEVENT_MAXIMIZED.

   WHAT THIS COMPANION DOES.  A message hook on the game's own thread (WH_CALLWNDPROC, installed before the window
   exists) watches the game's SDL window (the window SDL gives its "SDL_WindowData" property).  When that window's
   WM_SIZE says SIZE_MAXIMIZED and its previous WM_SIZE said SIZE_MINIMIZED, the hook first hands SDL's own window
   procedure a WM_SIZE / SIZE_RESTORED with the same size; SDL's own code then marks the window restored, clears its
   minimized and maximized flags, unhides the renderer and, in full screen, puts the window back over the whole
   screen (SDL_OnWindowRestored); then the real SIZE_MAXIMIZED arrives and SDL records the window as maximized as
   before.  Every other message, and every other window, is untouched: a normal window, or a full screen game made
   from one, comes back exactly as before (stock SDL already redraws it).

   ALL OR NONE.  The hook is installed only when SDL2.dll is loaded, reports version 2.0.3, and holds the stock
   bytes of the three places above (its WM_SIZE switch, its SDL_WINDOWEVENT_MAXIMIZED case and the renderer watch's
   MINIMIZED / RESTORED cases); a different SDL2.dll installs nothing.  No byte of the game or of SDL2.dll is written.
   Started by VVFP More Companions.dll (the third word, native/shared/startup_companions_3.h) before WinMain, on the
   game's own thread.  No file, no text, no save data, no debug output.

   It also starts "VVFP Fullscreen Mouse.dll" (the full screen mouse fix, a companion of its own shipped by the same
   Fix Vanilla Bugs rows), whatever SDL2.dll is: that companion makes its own checks; and, in The Secret City, The
   Tree of Life and New Believers, "VVFP Exact Pickups.dll" (each child takes the item it was dropped on), which
   makes its own checks too. */
#include <windows.h>

#include "../shared/patcher_files.h"

#define WR_SDL_PROP L"SDL_WindowData"

typedef struct {
    unsigned char major, minor, patch;
} wr_sdl_version;
typedef void(__cdecl *wr_get_version_fn)(wr_sdl_version *);

typedef struct {
    unsigned int rva;
    unsigned int length;
    const unsigned char *stock;
} wr_check;

/* SDL 2.0.3's WIN_WindowProc, case WM_SIZE (RVA 0xECBF9): SIZE_MINIMIZED -> SDL_WINDOWEVENT_MINIMIZED (7),
   SIZE_MAXIMIZED -> SDL_WINDOWEVENT_MAXIMIZED (8), anything else -> SDL_WINDOWEVENT_RESTORED (9). */
static const unsigned char WR_WM_SIZE[] = {
    0x8B, 0x4D, 0x10, 0x89, 0x8D, 0xA8, 0xFD, 0xFF, 0xFF, 0x83, 0xBD, 0xA8, 0xFD, 0xFF, 0xFF, 0x01, 0x74, 0x21, 0x83,
    0xBD, 0xA8, 0xFD, 0xFF, 0xFF, 0x02, 0x74, 0x02, 0xEB, 0x2C, 0x6A, 0x00, 0x6A, 0x00, 0x6A, 0x08, 0x8B, 0x55, 0xF8,
    0x8B, 0x02, 0x50, 0xE8, 0xC9, 0xE5, 0xFF, 0xFF, 0x83, 0xC4, 0x10, 0xEB, 0x2A, 0x6A, 0x00, 0x6A, 0x00, 0x6A, 0x07,
    0x8B, 0x4D, 0xF8, 0x8B, 0x11, 0x52, 0xE8, 0xB3, 0xE5, 0xFF, 0xFF, 0x83, 0xC4, 0x10, 0xEB, 0x14, 0x6A, 0x00, 0x6A,
    0x00, 0x6A, 0x09, 0x8B, 0x45, 0xF8, 0x8B, 0x08, 0x51, 0xE8, 0x9D, 0xE5, 0xFF, 0xFF, 0x83, 0xC4, 0x10,
};
/* SDL_SendWindowEvent, case SDL_WINDOWEVENT_MAXIMIZED (RVA 0xEB3B0): dropped when the window is already maximized,
   else only `flags |= SDL_WINDOW_MAXIMIZED` -- SDL_WINDOW_MINIMIZED stays set. */
static const unsigned char WR_MAXIMIZED[] = {
    0x8B, 0x4D, 0x08, 0x8B, 0x51, 0x30, 0x81, 0xE2, 0x80, 0x00, 0x00, 0x00, 0x74, 0x07, 0x33, 0xC0, 0xE9, 0xF0, 0x01,
    0x00, 0x00, 0x8B, 0x45, 0x08, 0x8B, 0x48, 0x30, 0x81, 0xC9, 0x80, 0x00, 0x00, 0x00, 0x8B, 0x55, 0x08, 0x89, 0x4A,
    0x30, 0xE9, 0x08, 0x01, 0x00, 0x00,
};
/* SDL_RendererEventWatch (RVA 0xBBEC1): MINIMIZED sets renderer->hidden (+0xC0); only RESTORED (not hidden) clears it. */
static const unsigned char WR_RENDER_WATCH[] = {
    0x8B, 0x45, 0x0C, 0x0F, 0xB6, 0x48, 0x0C, 0x83, 0xF9, 0x07, 0x75, 0x0F, 0x8B, 0x55, 0xFC, 0xC7, 0x82, 0xC0, 0x00,
    0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0xEB, 0x2A, 0x8B, 0x45, 0x0C, 0x0F, 0xB6, 0x48, 0x0C, 0x83, 0xF9, 0x09, 0x75,
    0x1E, 0x8B, 0x55, 0xF8, 0x52, 0xE8, 0xFF, 0xA9, 0x02, 0x00, 0x83, 0xC4, 0x04, 0x83, 0xE0, 0x08, 0x75, 0x0D, 0x8B,
    0x45, 0xFC, 0xC7, 0x80, 0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
};

static const wr_check WR_CHECKS[] = {
    {0xECBF9u, (unsigned int)sizeof WR_WM_SIZE, WR_WM_SIZE},
    {0xEB3B0u, (unsigned int)sizeof WR_MAXIMIZED, WR_MAXIMIZED},
    {0xBBEC1u, (unsigned int)sizeof WR_RENDER_WATCH, WR_RENDER_WATCH},
};

static HHOOK g_hook;
static HWND g_minimized;   /* the SDL window whose last WM_SIZE said SIZE_MINIMIZED, else NULL */
static int g_inside;       /* our own WM_SIZE / SIZE_RESTORED is being delivered */
static int g_installed;
#ifdef VVFP_TEST
LONG VvfpWindowRestoreResyncs;   /* WM_SIZE / SIZE_RESTORED messages handed to SDL (the tests read it) */
#endif

/* 1 when the SDL2.dll in this process is 2.0.3 with the stock bytes at all three places, else 0. */
static int wr_sdl_is_stock(void) {
    HMODULE sdl = GetModuleHandleA("SDL2.dll");
    const unsigned char *base;
    const IMAGE_NT_HEADERS *nt;
    wr_get_version_fn get_version;
    wr_sdl_version version;
    unsigned int i, j;
    if (sdl == NULL) {
        return 0;
    }
    get_version = (wr_get_version_fn)GetProcAddress(sdl, "SDL_GetVersion");
    if (get_version == NULL) {
        return 0;
    }
    version.major = version.minor = version.patch = 0;
    get_version(&version);
    if (version.major != 2 || version.minor != 0 || version.patch != 3) {
        return 0;
    }
    base = (const unsigned char *)sdl;
    if (((const IMAGE_DOS_HEADER *)base)->e_magic != IMAGE_DOS_SIGNATURE) {
        return 0;
    }
    nt = (const IMAGE_NT_HEADERS *)(base + ((const IMAGE_DOS_HEADER *)base)->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) {
        return 0;
    }
    for (i = 0; i < sizeof WR_CHECKS / sizeof WR_CHECKS[0]; ++i) {
        if (WR_CHECKS[i].rva + WR_CHECKS[i].length > nt->OptionalHeader.SizeOfImage) {
            return 0;
        }
        for (j = 0; j < WR_CHECKS[i].length; ++j) {
            if (base[WR_CHECKS[i].rva + j] != WR_CHECKS[i].stock[j]) {
                return 0;
            }
        }
    }
    return 1;
}

static void wr_on_size(HWND window, WPARAM kind, LPARAM size) {
    if (GetPropW(window, WR_SDL_PROP) == NULL) {
        return;                                   /* not SDL's window: a dialog, a companion's own window */
    }
    if (kind == SIZE_MINIMIZED) {
        g_minimized = window;
        return;
    }
    if (kind == SIZE_MAXIMIZED && g_minimized == window && !g_inside) {
        /* Back from the taskbar as a maximized (or full screen, still WS_MAXIMIZE) window: let SDL see the restore
           first, as later SDL versions do; the real SIZE_MAXIMIZED follows. */
        g_minimized = NULL;
        g_inside = 1;
        SendMessageW(window, WM_SIZE, SIZE_RESTORED, size);
        g_inside = 0;
#ifdef VVFP_TEST
        InterlockedIncrement(&VvfpWindowRestoreResyncs);
#endif
        return;
    }
    if (g_minimized == window) {
        g_minimized = NULL;
    }
}

static LRESULT CALLBACK wr_hook(int code, WPARAM wparam, LPARAM lparam) {
    if (code == HC_ACTION && lparam != 0) {
        const CWPSTRUCT *message = (const CWPSTRUCT *)lparam;
        if (message->message == WM_SIZE) {
            __try {
                wr_on_size(message->hwnd, message->wParam, message->lParam);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                g_inside = 0;
            }
        }
    }
    return CallNextHookEx(g_hook, code, wparam, lparam);
}

/* 1 when the hook is installed (for the tests), else 0. */
int __stdcall VvfpWindowRestoreInstalled(void) {
    return g_installed;
}

typedef void(__stdcall *wr_startup_fn)(int, unsigned int);

/* The full screen mouse fix ("VVFP Fullscreen Mouse.dll", its own companion in the same Fix Vanilla Bugs rows):
   started from here, by its full path in the patcher's folder, so it needs no startup word of its own.  Not
   shipped, or a fault in it: nothing. */
static void wr_start_fullscreen_mouse(int game, unsigned int shipped) {
    HMODULE mouse = vvfp_load_patcher_dll("VVFP Fullscreen Mouse.dll");
    wr_startup_fn startup = mouse != NULL ? (wr_startup_fn)GetProcAddress(mouse, "VvfpStartup") : NULL;
    if (startup != NULL) {
        __try {
            startup(game, shipped);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
}

/* The exact pickups fix ("VVFP Exact Pickups.dll", its own companion in The Secret City's, The Tree of Life's and
   New Believers' Fix Vanilla Bugs rows): started the same way; the other two games do not ship it. */
static void wr_start_exact_pickups(int game, unsigned int shipped) {
    HMODULE pickups = vvfp_load_patcher_dll("VVFP Exact Pickups.dll");
    wr_startup_fn startup = pickups != NULL ? (wr_startup_fn)GetProcAddress(pickups, "VvfpStartup") : NULL;
    if (startup != NULL) {
        __try {
            startup(game, shipped);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
}

/* Called once by VVFP More Companions.dll before WinMain, on the game's own thread. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    if (g_installed || game < 1 || game > 5) {
        return;
    }
    wr_start_fullscreen_mouse(game, shipped);
    if (game >= 3) {
        wr_start_exact_pickups(game, shipped);
    }
    if (!wr_sdl_is_stock()) {
        return;
    }
    g_hook = SetWindowsHookExW(WH_CALLWNDPROC, wr_hook, NULL, GetCurrentThreadId());
    if (g_hook != NULL) {
        g_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
