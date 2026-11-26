/* window_restore_harness -- the frozen-picture bug and its fix, with the games' own SDL2.dll (2.0.3).

   usage: window_restore_harness.exe <folder holding SDL2.dll> stock|fixed|refused [companion DLL]

   It makes an SDL window and renderer exactly as the five games do (SDL_CreateWindow(..., SDL_WINDOW_RESIZABLE),
   SDL_CreateRenderer(window, -1, 0), full screen with SDL_SetWindowFullscreen(window, 0x1001)), on a private desktop
   of its own that the person at the computer never sees, and drives the window through the real window manager:
   ShowWindow minimize / maximize, WM_ACTIVATE as alt-tab sends it (SDL 2.0.3 minimizes a full screen window when it
   loses focus), WM_SYSCOMMAND / SC_RESTORE as a taskbar click or alt-tab sends it to a minimized window.  After each
   step it reads what decides whether the game's frames reach the screen: the renderer's `hidden` mark (renderer+0xC0;
   SDL_RenderPresent returns without drawing while it is set), SDL's own window flags (SDL_GetWindowFlags) and the
   window's real state.  The software renderer is used: the `hidden` gate is SDL's renderer-independent layer
   (render.c), the same for the games' Direct3D renderer.

     stock    no companion: the maximized window and the full screen window made from a maximized window stay frozen.
     fixed    the companion (its test build) started first, as VVFP More Companions.dll starts it: nothing freezes.
     refused  the companion started with an SDL2.dll whose WM_SIZE switch differs by one byte: it installs nothing.

   Prints "ok <check>" / "FAIL <check>" and "== N check(s), M failure(s) ==".  Exit code 0 only with no failure. */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "../shared/harness_redirect_documents.h"

typedef int(__cdecl *init_fn)(unsigned int);
typedef void *(__cdecl *create_window_fn)(const char *, int, int, int, int, unsigned int);
typedef void *(__cdecl *create_renderer_fn)(void *, int, unsigned int);
typedef int(__cdecl *fullscreen_fn)(void *, unsigned int);
typedef unsigned int(__cdecl *flags_fn)(void *);
typedef int(__cdecl *poll_fn)(void *);
typedef int(__cdecl *hint_fn)(const char *, const char *);
typedef int(__cdecl *wm_info_fn)(void *, void *);
typedef void(__cdecl *quit_fn)(void);
typedef int(__cdecl *bounds_fn)(int, void *);
typedef void(__stdcall *startup_fn)(int, unsigned int);
typedef int(__stdcall *installed_fn)(void);

#define SDL_WINDOW_FULLSCREEN 0x1u
#define SDL_WINDOW_MINIMIZED 0x40u
#define SDL_WINDOW_MAXIMIZED 0x80u
#define SDL_FULLSCREEN_DESKTOP 0x1001u
#define RENDERER_HIDDEN 0xC0

static poll_fn s_poll;
static flags_fn s_flags;
static fullscreen_fn s_fullscreen;
static void *g_window, *g_renderer;
static HWND g_hwnd;
static RECT g_monitor;
static int g_checks, g_failures;
static volatile LONG *g_resyncs;

static void pump(void) {
    unsigned char event[64];
    MSG message;
    int i, quiet = 0;
    /* Until three rounds in a row find nothing to do (the window manager's messages to the window are sent, not
       posted, so they are handled before the call that caused them returns; this catches the posted ones). */
    for (i = 0; i < 40 && quiet < 3; ++i) {
        int busy = 0;
        while (PeekMessageW(&message, NULL, 0, 0, PM_REMOVE)) {
            TranslateMessage(&message);
            DispatchMessageW(&message);
            busy = 1;
        }
        while (s_poll(event)) {
            busy = 1;
        }
        quiet = busy ? 0 : quiet + 1;
        Sleep(1);
    }
}

typedef struct {
    int hidden, sdl_minimized, sdl_maximized, sdl_fullscreen, iconic, zoomed;
    RECT rect;
} state;

static state now(void) {
    state s;
    unsigned int flags = s_flags(g_window);
    s.hidden = *(volatile int *)((char *)g_renderer + RENDERER_HIDDEN);
    s.sdl_minimized = (flags & SDL_WINDOW_MINIMIZED) != 0;
    s.sdl_maximized = (flags & SDL_WINDOW_MAXIMIZED) != 0;
    s.sdl_fullscreen = (flags & SDL_WINDOW_FULLSCREEN) != 0;
    s.iconic = IsIconic(g_hwnd) != 0;
    s.zoomed = IsZoomed(g_hwnd) != 0;
    GetWindowRect(g_hwnd, &s.rect);
    return s;
}

static void show(const char *step) {
    state s = now();
    printf("   %-52s hidden=%d sdl_min=%d sdl_max=%d sdl_full=%d iconic=%d zoomed=%d rect=%ld,%ld,%ld,%ld resyncs=%ld\n",
           step, s.hidden, s.sdl_minimized, s.sdl_maximized, s.sdl_fullscreen, s.iconic, s.zoomed, s.rect.left,
           s.rect.top, s.rect.right, s.rect.bottom, g_resyncs ? *g_resyncs : -1L);
}

static void check(int condition, const char *name) {
    ++g_checks;
    if (!condition) {
        ++g_failures;
    }
    printf("%s %s\n", condition ? "ok" : "FAIL", name);
}

static int drawing(void) {
    state s = now();
    return !s.hidden;
}

static int covers_monitor(void) {
    state s = now();
    return EqualRect(&s.rect, &g_monitor);
}

/* Alt-tab (or a click on another window) away: SDL hears WM_ACTIVATE / WA_INACTIVE. */
static void away(void) {
    SendMessageW(g_hwnd, WM_ACTIVATE, WA_INACTIVE, 0);
    pump();
}

/* Alt-tab or a taskbar click back: a minimized window is restored (SC_RESTORE), then activated. */
static void back(void) {
    if (IsIconic(g_hwnd)) {
        SendMessageW(g_hwnd, WM_SYSCOMMAND, SC_RESTORE, 0);
        pump();
    }
    SendMessageW(g_hwnd, WM_ACTIVATE, WA_ACTIVE, 0);
    pump();
}

/* Back to a plain window, as each scenario starts. */
static void reset_window(void) {
    s_fullscreen(g_window, 0);
    pump();
    if (IsIconic(g_hwnd) || IsZoomed(g_hwnd)) {
        ShowWindow(g_hwnd, SW_RESTORE);
        pump();
    }
    SendMessageW(g_hwnd, WM_ACTIVATE, WA_ACTIVE, 0);
    pump();
}

int main(int argc, char **argv) {
    char path[MAX_PATH * 2], desktop_name[64];
    HMODULE sdl, fix = NULL;
    HDESK desktop;
    init_fn s_init;
    create_window_fn s_create_window;
    create_renderer_fn s_create_renderer;
    hint_fn s_hint;
    wm_info_fn s_wm_info;
    quit_fn s_quit;
    bounds_fn s_bounds;
    unsigned char info[64];
    int bounds[4];
    int stock, fixed, refused, installed = -1;

    /* Never the real Documents (the owner, 2026-10-10): the companion and SDL load into a process whose
       Documents is a throwaway %TEMP% folder. */
    if (!harness_redirect_documents_process()) return 2;
    if (argc < 3) {
        printf("usage: window_restore_harness <SDL2.dll folder> stock|fixed|refused [companion]\n");
        return 2;
    }
    stock = strcmp(argv[2], "stock") == 0;
    fixed = strcmp(argv[2], "fixed") == 0;
    refused = strcmp(argv[2], "refused") == 0;
    if (!stock && !fixed && !refused) {
        return 2;
    }
    if (!stock && argc < 4) {
        return 2;
    }

    /* A private desktop: every window of this run is made on it and never shown to the person at the computer. */
    sprintf_s(desktop_name, sizeof desktop_name, "vvfp_window_restore_%lu", GetCurrentProcessId());
    desktop = CreateDesktopA(desktop_name, NULL, NULL, 0, GENERIC_ALL, NULL);
    if (desktop == NULL || !SetThreadDesktop(desktop)) {
        printf("FAIL private desktop (%lu)\n", GetLastError());
        return 3;
    }

    /* The games load SDL2.dll before VVFP Startup.dll runs; the companion finds it by that name. */
    sprintf_s(path, sizeof path, "%s\\SDL2.dll", argv[1]);
    sdl = LoadLibraryA(path);
    if (sdl == NULL) {
        printf("FAIL load %s (%lu)\n", path, GetLastError());
        return 4;
    }
    if (!stock) {
        startup_fn startup;
        installed_fn is_installed;
        fix = LoadLibraryA(argv[3]);
        if (fix == NULL) {
            printf("FAIL load %s (%lu)\n", argv[3], GetLastError());
            return 5;
        }
        startup = (startup_fn)GetProcAddress(fix, "VvfpStartup");
        is_installed = (installed_fn)GetProcAddress(fix, "VvfpWindowRestoreInstalled");
        g_resyncs = (volatile LONG *)GetProcAddress(fix, "VvfpWindowRestoreResyncs");
        if (startup == NULL || is_installed == NULL) {
            printf("FAIL companion exports\n");
            return 6;
        }
        startup(1, 0);
        installed = is_installed();
    }
    check(stock || installed == (fixed ? 1 : 0), fixed ? "companion installed with the stock SDL 2.0.3"
                                                       : (refused ? "companion refuses a changed SDL2.dll"
                                                                  : "no companion"));

    s_init = (init_fn)GetProcAddress(sdl, "SDL_Init");
    s_create_window = (create_window_fn)GetProcAddress(sdl, "SDL_CreateWindow");
    s_create_renderer = (create_renderer_fn)GetProcAddress(sdl, "SDL_CreateRenderer");
    s_fullscreen = (fullscreen_fn)GetProcAddress(sdl, "SDL_SetWindowFullscreen");
    s_flags = (flags_fn)GetProcAddress(sdl, "SDL_GetWindowFlags");
    s_poll = (poll_fn)GetProcAddress(sdl, "SDL_PollEvent");
    s_hint = (hint_fn)GetProcAddress(sdl, "SDL_SetHint");
    s_wm_info = (wm_info_fn)GetProcAddress(sdl, "SDL_GetWindowWMInfo");
    s_quit = (quit_fn)GetProcAddress(sdl, "SDL_Quit");
    s_bounds = (bounds_fn)GetProcAddress(sdl, "SDL_GetDisplayBounds");
    if (!s_bounds || !s_init || !s_create_window || !s_create_renderer || !s_fullscreen || !s_flags || !s_poll || !s_hint ||
        !s_wm_info || !s_quit) {
        printf("FAIL SDL exports\n");
        return 7;
    }
    s_hint("SDL_RENDER_DRIVER", "software");
    if (s_init(0x20u /* SDL_INIT_VIDEO */) != 0) {
        printf("FAIL SDL_Init\n");
        return 8;
    }
    /* As the games: SDL_WINDOWPOS_CENTERED, the window resizable (0x20), renderer -1 / 0. */
    g_window = s_create_window("window_restore_harness", 0x2FFF0000, 0x2FFF0000, 800, 600, 0x20u);
    g_renderer = g_window ? s_create_renderer(g_window, -1, 0) : NULL;
    if (g_window == NULL || g_renderer == NULL) {
        printf("FAIL SDL window or renderer\n");
        return 9;
    }
    memset(info, 0, sizeof info);
    info[0] = 2; /* SDL_VERSION 2.0.3 */
    info[1] = 0;
    info[2] = 3;
    if (!s_wm_info(g_window, info) || (g_hwnd = *(HWND *)(info + 8)) == NULL) {
        printf("FAIL window handle\n");
        return 10;
    }
    /* Full screen is the display' bounds as SDL reads them (SDL_GetDisplayBounds, display 0). */
    if (s_bounds(0, bounds) != 0) {
        printf("FAIL display bounds\n");
        return 11;
    }
    SetRect(&g_monitor, bounds[0], bounds[1], bounds[0] + bounds[2], bounds[1] + bounds[3]);
    printf("   display 0: %ld,%ld,%ld,%ld\n", g_monitor.left, g_monitor.top, g_monitor.right, g_monitor.bottom);
    pump();
    show("made (a window, as the games start)");
    check(drawing(), "a new window draws");

    printf("-- A. a window: minimize, back\n");
    ShowWindow(g_hwnd, SW_MINIMIZE);
    pump();
    show("minimized");
    check(!drawing(), "A. a minimized window does not draw (stock SDL, both runs)");
    back();
    show("back");
    check(drawing(), "A. a window draws again when it comes back");

    printf("-- B. a maximized window: minimize, back\n");
    reset_window();
    ShowWindow(g_hwnd, SW_MAXIMIZE);
    pump();
    show("maximized");
    ShowWindow(g_hwnd, SW_MINIMIZE);
    pump();
    show("minimized");
    back();
    show("back (Windows restores it maximized)");
    if (fixed) {
        state s = now();
        check(drawing(), "B. the maximized window draws again when it comes back");
        check(s.zoomed && s.sdl_maximized && !s.sdl_minimized, "B. SDL counts it maximized, not minimized");
    } else {
        check(!drawing(), "B. stock: the maximized window comes back frozen");
    }
    away();
    back();
    show("clicked away and back");
    check(fixed ? drawing() : !drawing(), fixed ? "B. still drawing after a click away and back"
                                                : "B. stock: still frozen after a click away and back");
    ShowWindow(g_hwnd, SW_RESTORE);
    pump();
    show("Restore Down (no longer maximized)");
    check(drawing(), "B. a window no longer maximized draws (the stock way out)");

    printf("-- C. full screen made from a window: alt-tab away, back, twice\n");
    reset_window();
    s_fullscreen(g_window, SDL_FULLSCREEN_DESKTOP);
    pump();
    show("full screen");
    check(drawing() && covers_monitor(), "C. full screen draws over the whole screen");
    away();
    show("alt-tab away");
    check(IsIconic(g_hwnd) != 0, "C. SDL minimizes the full screen window when it loses focus");
    back();
    show("back");
    check(drawing() && covers_monitor(), "C. back in full screen, drawing (stock SDL, both runs)");
    away();
    back();
    show("away and back again");
    check(drawing() && covers_monitor(), "C. and again");

    printf("-- D. full screen made from a maximized window: alt-tab away, back, twice\n");
    reset_window();
    ShowWindow(g_hwnd, SW_MAXIMIZE);
    pump();
    s_fullscreen(g_window, SDL_FULLSCREEN_DESKTOP);
    pump();
    show("full screen (from maximized)");
    check(drawing() && covers_monitor(), "D. full screen draws over the whole screen");
    away();
    show("alt-tab away");
    check(IsIconic(g_hwnd) != 0, "D. SDL minimizes it when it loses focus");
    back();
    show("back");
    if (fixed) {
        check(drawing(), "D. back in full screen, drawing");
        check(covers_monitor(), "D. back over the whole screen (SDL put full screen back)");
    } else {
        check(!drawing(), "D. stock: back in full screen, frozen");
    }
    away();
    show("alt-tab away again");
    if (fixed) {
        check(IsIconic(g_hwnd) != 0, "D. the next alt-tab minimizes it again");
    } else {
        check(IsIconic(g_hwnd) == 0, "D. stock: SDL thinks it is still minimized, so it is not minimized again");
    }
    back();
    show("back again");
    check(fixed ? (drawing() && covers_monitor()) : !drawing(),
          fixed ? "D. back again, drawing over the whole screen" : "D. stock: still frozen in full screen");
    s_fullscreen(g_window, 0);
    pump();
    show("the game's full screen toggle off");
    if (fixed) {
        state s = now();
        check(drawing() && s.zoomed && !s.sdl_minimized, "D. out of full screen: the maximized window, drawing");
    }
    ShowWindow(g_hwnd, SW_RESTORE);
    pump();
    show("Restore Down");
    check(drawing(), "D. a window no longer maximized draws");

    printf("-- E. full screen made from a window: minimized with Win+M / Win+D, back\n");
    reset_window();
    s_fullscreen(g_window, SDL_FULLSCREEN_DESKTOP);
    pump();
    ShowWindow(g_hwnd, SW_MINIMIZE);
    pump();
    show("minimized");
    back();
    show("back");
    check(drawing() && covers_monitor(), "E. back in full screen, drawing (stock SDL, both runs)");

    if (g_resyncs != NULL) {
        printf("   restores handed to SDL by the companion: %ld\n", *g_resyncs);
        check(*g_resyncs == (fixed ? 3 : 0), fixed ? "only B and D's two returns needed the companion"
                                                    : "the refused companion never acted");
    }
    reset_window();
    s_quit();
    printf("== %d check(s), %d failure(s) ==\n", g_checks, g_failures);
    return g_failures ? 1 : 0;
}
