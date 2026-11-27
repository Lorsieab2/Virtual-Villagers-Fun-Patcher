/* fullscreen_mouse_harness -- the games' own event pump, the games' own SDL2.dll, a real window: where the game
   thinks the mouse is, stock and with "VVFP Fullscreen Mouse.dll".

   usage: fullscreen_mouse_harness.exe <SDL2.dll folder> <game exe> <game 1-5> stock|fixed|refused [companion DLL]

   The game's executable (a stock copy) is mapped into this process at its own base, 0x400000, as Windows would map
   it; its SDL2.dll imports are bound to the real SDL2.dll (anything else it imports would stop the run).  Its OWN
   event pump (A New Home 0x403970 ... New Believers 0x4047C0) is then run, unchanged, as machine code, with one
   difference: the routine that hands the pump the game's input manager (A New Home 0x401F60 ... New Believers
   0x402200) answers with a stand-in manager whose listener writes down what the game receives -- (kind, x, y),
   kind 1 a move, 2 a left button press, 3 a release -- through the game's own dispatch routine.

   A window is made as the games make it (SDL_CreateWindow resizable, SDL_CreateRenderer(-1, 0) -- through the
   mapped game's import, so the companion sees it -- an ARGB8888 texture, the "linear" hint, the logical size of
   the game's picture), on a private desktop of its own that nobody sees (the software renderer: Direct3D does not
   start there; SDL's logical-size arithmetic is the same for every renderer).  For each window size it sends
   WM_MOUSEMOVE / WM_LBUTTONDOWN / WM_LBUTTONUP at chosen window pixels, runs the game's pump, and compares what
   the game received with where that pixel is in the game's picture -- what SDL's own mouse event says (SDL
   converts its events; the harness reads them on their way to the pump).

     stock    no companion: in a window of the picture's own size the game is right; in any bigger window and in
              full screen it reads window pixels -- the offsets are printed.
     fixed    the companion (its test build) started first: the game receives the picture's pixel every time (the
              black bars count as the picture's nearest edge); its reverse conversion (the pointer warp) is exact.
     refused  the companion with an SDL2.dll whose event watch differs by one byte: it installs nothing (stock).

   Prints "ok <check>" / "FAIL <check>", "offset ..." lines and "== N check(s), M failure(s) ==".  Exit code 0 only
   with no failure. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../shared/harness_redirect_documents.h"

typedef int(__cdecl *init_fn)(unsigned int);
typedef void *(__cdecl *create_window_fn)(const char *, int, int, int, int, unsigned int);
typedef void *(__cdecl *create_renderer_fn)(void *, int, unsigned int);
typedef void *(__cdecl *create_texture_fn)(void *, unsigned int, int, int, int);
typedef int(__cdecl *hint_fn)(const char *, const char *);
typedef int(__cdecl *logical_fn)(void *, int, int);
typedef void(__cdecl *window_size_fn)(void *, int, int);
typedef void(__cdecl *get_window_size_fn)(void *, int *, int *);
typedef int(__cdecl *fullscreen_fn)(void *, unsigned int);
typedef int(__cdecl *poll_fn)(void *);
typedef int(__cdecl *wm_info_fn)(void *, void *);
typedef int(__cdecl *int_ptr_fn)(void *);
typedef void(__cdecl *quit_fn)(void);
typedef void(__stdcall *startup_fn)(int, unsigned int);
typedef int(__stdcall *installed_fn)(void);
typedef void(__stdcall *use_module_fn)(HMODULE);
typedef void(__stdcall *convert_fn)(int, int *, int *);

/* Per game: frame size, the event pump, the routine that hands it the input manager. */
static const struct {
    int w, h;
    unsigned int pump, manager;
} GAMES[5] = {
    {800, 600, 0x403970, 0x401F60},  /* A New Home */
    {800, 600, 0x403C00, 0x401FF0},  /* The Lost Children */
    {800, 600, 0x404220, 0x402020},  /* The Secret City */
    {800, 600, 0x404830, 0x402250},  /* The Tree of Life */
    {1024, 768, 0x4047C0, 0x402200}, /* New Believers */
};

static HMODULE g_sdl;
static unsigned char *g_image;
static poll_fn s_poll;
static int g_checks, g_failures;
static convert_fn g_convert;

/* What the game received (the stand-in listener) and what SDL's events said (on their way to the pump). */
#define LOG_MAX 64
static int g_got[LOG_MAX][3], g_got_n;
static int g_said[LOG_MAX][3], g_said_n;

static void check(int condition, const char *name) {
    ++g_checks;
    if (!condition) {
        ++g_failures;
    }
    printf("%s %s\n", condition ? "ok" : "FAIL", name);
}

static void __stdcall unexpected_import(void) {
    printf("FAIL the game's code called an import other than SDL2.dll's\n");
    ExitProcess(20);
}

/* The listener's method (thiscall, three arguments, callee pops): the game's dispatch calls it. */
static void __fastcall listener_event(void *self, void *unused, int kind, int x, int y) {
    (void)self;
    (void)unused;
    if (g_got_n < LOG_MAX) {
        g_got[g_got_n][0] = kind;
        g_got[g_got_n][1] = x;
        g_got[g_got_n][2] = y;
        ++g_got_n;
    }
}

/* The game's import of SDL_PollEvent, through here: SDL's own converted coordinates written down. */
static int __cdecl poll_through(void *event) {
    int got = s_poll(event);
    if (got) {
        unsigned int type = *(unsigned int *)event;
        unsigned char button = ((unsigned char *)event)[16];
        if ((type == 0x400 || ((type == 0x401 || type == 0x402) && button == 1)) && g_said_n < LOG_MAX) {
            g_said[g_said_n][0] = type == 0x400 ? 1 : (type == 0x401 ? 2 : 3);
            g_said[g_said_n][1] = *(int *)((unsigned char *)event + 20);
            g_said[g_said_n][2] = *(int *)((unsigned char *)event + 24);
            ++g_said_n;
        }
    }
    return got;
}

/* The stand-in input manager: manager -> { list, listener, flag }, listener -> vtable -> { -, event }. */
static void *g_vtable[2] = {NULL, (void *)listener_event};
static void *g_listener[1] = {g_vtable};
static unsigned char g_manager[64];
static void *g_holder[1] = {g_manager};

/* Map the executable at its own base; bind SDL2.dll's imports; trap the others.  0 on failure. */
static int map_game(const char *path) {
    HANDLE file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    DWORD size, got;
    unsigned char *raw;
    IMAGE_NT_HEADERS *nt;
    IMAGE_SECTION_HEADER *section;
    IMAGE_IMPORT_DESCRIPTOR *d;
    int i;
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    size = GetFileSize(file, NULL);
    raw = (unsigned char *)malloc(size);
    if (raw == NULL || !ReadFile(file, raw, size, &got, NULL) || got != size) {
        CloseHandle(file);
        return 0;
    }
    CloseHandle(file);
    nt = (IMAGE_NT_HEADERS *)(raw + ((IMAGE_DOS_HEADER *)raw)->e_lfanew);
    g_image = (unsigned char *)VirtualAlloc((void *)(UINT_PTR)nt->OptionalHeader.ImageBase,
                                            nt->OptionalHeader.SizeOfImage, MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    if (g_image != (unsigned char *)(UINT_PTR)nt->OptionalHeader.ImageBase) {
        printf("FAIL the game's base 0x%lX is taken in this process\n", nt->OptionalHeader.ImageBase);
        return 0;
    }
    memcpy(g_image, raw, nt->OptionalHeader.SizeOfHeaders);
    section = IMAGE_FIRST_SECTION(nt);
    for (i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        memcpy(g_image + section[i].VirtualAddress, raw + section[i].PointerToRawData,
               min(section[i].SizeOfRawData, section[i].Misc.VirtualSize ? section[i].Misc.VirtualSize
                                                                         : section[i].SizeOfRawData));
    }
    free(raw);
    nt = (IMAGE_NT_HEADERS *)(g_image + ((IMAGE_DOS_HEADER *)g_image)->e_lfanew);
    for (d = (IMAGE_IMPORT_DESCRIPTOR *)(g_image +
                                         nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
         d->Name != 0; ++d) {
        int sdl = lstrcmpiA((const char *)(g_image + d->Name), "SDL2.dll") == 0;
        IMAGE_THUNK_DATA *names = (IMAGE_THUNK_DATA *)(g_image + d->OriginalFirstThunk);
        IMAGE_THUNK_DATA *slots = (IMAGE_THUNK_DATA *)(g_image + d->FirstThunk);
        for (; names->u1.AddressOfData != 0; ++names, ++slots) {
            void *target = (void *)unexpected_import;
            if (sdl && !IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal)) {
                const char *name = (const char *)((IMAGE_IMPORT_BY_NAME *)(g_image + names->u1.AddressOfData))->Name;
                target = (void *)GetProcAddress(g_sdl, name);
                if (target == NULL) {
                    printf("FAIL SDL2.dll has no %s\n", name);
                    return 0;
                }
            }
            slots->u1.Function = (DWORD)(UINT_PTR)target;
        }
    }
    return 1;
}

/* The mapped game's import entry for SDL2.dll's `name`. */
static void **game_import(const char *name) {
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(g_image + ((IMAGE_DOS_HEADER *)g_image)->e_lfanew);
    IMAGE_IMPORT_DESCRIPTOR *d;
    for (d = (IMAGE_IMPORT_DESCRIPTOR *)(g_image +
                                         nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
         d->Name != 0; ++d) {
        IMAGE_THUNK_DATA *names = (IMAGE_THUNK_DATA *)(g_image + d->OriginalFirstThunk);
        IMAGE_THUNK_DATA *slots = (IMAGE_THUNK_DATA *)(g_image + d->FirstThunk);
        if (lstrcmpiA((const char *)(g_image + d->Name), "SDL2.dll") != 0) {
            continue;
        }
        for (; names->u1.AddressOfData != 0; ++names, ++slots) {
            if (!IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal) &&
                strcmp((const char *)((IMAGE_IMPORT_BY_NAME *)(g_image + names->u1.AddressOfData))->Name, name) == 0) {
                return (void **)&slots->u1.Function;
            }
        }
    }
    printf("FAIL the game imports no %s\n", name);
    ExitProcess(21);
}

static void run_pump(unsigned int pump, void *self) {
    __asm {
        mov ecx, self
        call pump
    }
}

static unsigned char g_window_object[0x400];   /* the game's window object, as far as the pump looks */
static void *g_window;
static HWND g_hwnd;
static int g_game;

static void drain(void) {
    unsigned char event[64];
    MSG message;
    while (PeekMessageW(&message, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
    while (s_poll(event)) {
    }
}

/* One message at window pixel (x, y), then the game's pump: what the game received for it vs SDL's event. */
static int send_and_pump(UINT message, int x, int y, int *game_x, int *game_y, int *sdl_x, int *sdl_y) {
    int kind = message == WM_MOUSEMOVE ? 1 : (message == WM_LBUTTONDOWN ? 2 : 3);
    int i;
    drain();
    g_got_n = g_said_n = 0;
    SendMessageW(g_hwnd, message, message == WM_LBUTTONDOWN ? MK_LBUTTON : 0, MAKELPARAM(x, y));
    {
        /* Nobody's pointer is on this private desktop's window, so Windows posts WM_MOUSELEAVE at once, and SDL
           would answer it by moving its mouse to the real pointer before the game's pump asks where the mouse is.
           A real pointer over the game sends no such message. */
        MSG leave;
        while (PeekMessageW(&leave, g_hwnd, WM_MOUSELEAVE, WM_MOUSELEAVE, PM_REMOVE)) {
        }
    }
    run_pump(GAMES[g_game - 1].pump, g_window_object);
    /* the first of this kind (a later one can be SDL's answer to the WM_MOUSELEAVE Windows posts) */
    for (i = 0; i < g_said_n && i < g_got_n; ++i) {
        if (g_said[i][0] == kind && g_got[i][0] == kind) {
            *game_x = g_got[i][1];
            *game_y = g_got[i][2];
            *sdl_x = g_said[i][1];
            *sdl_y = g_said[i][2];
            return 1;
        }
    }
    return 0;
}

static int clampi(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

/* One window state: points across it (corners, middle, the bars), moves and a click.  Returns the largest error. */
static void scenario(const char *label, int fixed, int expect_exact_stock) {
    get_window_size_fn size = (get_window_size_fn)GetProcAddress(g_sdl, "SDL_GetWindowSize");
    int ww = 0, wh = 0, fw = GAMES[g_game - 1].w, fh = GAMES[g_game - 1].h;
    int points[9][2];
    int i, worst = 0, received = 0, sdl_matches = 0;
    char name[256];
    size(g_window, &ww, &wh);
    points[0][0] = 0;          points[0][1] = 0;
    points[1][0] = ww / 2;     points[1][1] = wh / 2;
    points[2][0] = ww - 1;     points[2][1] = wh - 1;
    points[3][0] = ww / 4;     points[3][1] = wh / 3;
    points[4][0] = 3 * ww / 4; points[4][1] = 2 * wh / 3;
    points[5][0] = 2;          points[5][1] = wh / 2;       /* in the left bar when there is one */
    points[6][0] = ww - 3;     points[6][1] = wh / 2;       /* in the right bar */
    points[7][0] = ww / 2;     points[7][1] = 2;
    points[8][0] = ww / 3;     points[8][1] = wh - 2;
    printf("-- %s: window %dx%d, the game's picture %dx%d\n", label, ww, wh, fw, fh);
    {
        /* SDL drops a move to where its mouse already is: start each window state from a point none of the
           measured ones is. */
        int a, b, c, d;
        send_and_pump(WM_MOUSEMOVE, ww / 2 + 1, wh / 2 + 1, &a, &b, &c, &d);
    }
    for (i = 0; i < 9; ++i) {
        UINT kinds[3] = {WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP};
        int k;
        for (k = 0; k < 3; ++k) {
            int gx = -1, gy = -1, sx = 0, sy = 0, right_x, right_y, dx, dy;
            if (!send_and_pump(kinds[k], points[i][0], points[i][1], &gx, &gy, &sx, &sy)) {
                continue;
            }
            ++received;
            /* the picture's pixel there: SDL's own conversion, inside the picture (a bar counts as its edge) */
            right_x = clampi(sx, 0, fw - 1);
            right_y = clampi(sy, 0, fh - 1);
            dx = gx - right_x;
            dy = gy - right_y;
            if (abs(dx) > worst) worst = abs(dx);
            if (abs(dy) > worst) worst = abs(dy);
            if (gx == points[i][0] && gy == points[i][1]) {
                ++sdl_matches;   /* the game read the window pixel itself */
            }
            if (k == 1) {
                printf("   offset game %d, %s, window %dx%d: pointer at window (%d,%d) = picture (%d,%d); the game "
                       "reads (%d,%d): off by (%+d,%+d)\n",
                       g_game, label, ww, wh, points[i][0], points[i][1], right_x, right_y, gx, gy, dx, dy);
            }
        }
    }
    sprintf_s(name, sizeof name, "%s: the game's pump received every move, press and release (%d)", label, received);
    check(received == 27, name);
    if (fixed) {
        /* The pointer warp's reverse conversion: every picture pixel on a grid comes back to itself. */
        int x, y, bad = 0;
        sprintf_s(name, sizeof name, "%s: the game reads the picture's pixel under the pointer, exactly", label);
        check(worst == 0, name);
        for (y = 0; y < fh; y += 7) {
            for (x = 0; x < fw; x += 7) {
                int wx = x, wy = y;
                g_convert(0, &wx, &wy);
                g_convert(1, &wx, &wy);
                if (wx != x || wy != y) {
                    if (bad < 3) {
                        int ax = x, ay = y;
                        g_convert(0, &ax, &ay);
                        printf("   the picture's (%d,%d) -> window (%d,%d) -> picture (%d,%d)\n", x, y, ax, ay, wx, wy);
                    }
                    ++bad;
                }
            }
        }
        sprintf_s(name, sizeof name, "%s: the pointer warp lands on the same picture pixel (game -> window -> game)",
                  label);
        check(bad == 0, name);
    } else if (expect_exact_stock) {
        sprintf_s(name, sizeof name, "%s: stock, a window of the picture's own size is right", label);
        check(worst == 0, name);
    } else {
        sprintf_s(name, sizeof name, "%s: stock, the game reads window pixels, off by up to %d picture pixels", label,
                  worst);
        check(worst > 0 && sdl_matches == received, name);
    }
}

static int run(int argc, char **argv) {
    char path[MAX_PATH * 2], desktop_name[64];
    HDESK desktop;
    init_fn s_init;
    create_window_fn s_create_window;
    create_renderer_fn s_create_renderer;
    create_texture_fn s_create_texture;
    hint_fn s_hint;
    logical_fn s_logical;
    window_size_fn s_window_size;
    fullscreen_fn s_fullscreen;
    wm_info_fn s_wm_info;
    int_ptr_fn s_clear, s_present;
    quit_fn s_quit;
    void *renderer;
    unsigned char info[64];
    int stock, fixed, refused, installed = -1, fw, fh;
    HMODULE fix = NULL;
    convert_fn convert = NULL;

    /* The games' base, 0x400000, must be free for the copy of the game (this harness itself is linked at
       0x30000000).  Windows maps its own data into low addresses while a process starts, so the harness starts
       itself again, suspended, holds 0x400000 in that copy before it runs, and passes on its exit code. */
    {
        MEMORY_BASIC_INFORMATION mbi;
        VirtualQuery((void *)0x400000, &mbi, sizeof mbi);
        if (!(mbi.State == MEM_RESERVE && mbi.AllocationBase == (void *)0x400000)) {
            STARTUPINFOW si;
            PROCESS_INFORMATION pi;
            DWORD code = 1;
            if (GetEnvironmentVariableA("VVFP_FULLSCREEN_MOUSE_CHILD", path, sizeof path) != 0) {
                printf("FAIL 0x400000 could not be held for the game\n");
                return 2;
            }
            SetEnvironmentVariableA("VVFP_FULLSCREEN_MOUSE_CHILD", "1");
            memset(&si, 0, sizeof si);
            si.cb = sizeof si;
            si.dwFlags = STARTF_USESTDHANDLES;
            si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
            si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
            si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
            if (!CreateProcessW(NULL, GetCommandLineW(), NULL, NULL, TRUE, CREATE_SUSPENDED, NULL, NULL, &si, &pi)) {
                printf("FAIL start the harness again (%lu)\n", GetLastError());
                return 2;
            }
            if (VirtualAllocEx(pi.hProcess, (void *)0x400000, 0x1000000, MEM_RESERVE, PAGE_EXECUTE_READWRITE) !=
                (void *)0x400000) {
                printf("FAIL hold 0x400000 in the started copy (%lu)\n", GetLastError());
                TerminateProcess(pi.hProcess, 2);
                return 2;
            }
            ResumeThread(pi.hThread);
            WaitForSingleObject(pi.hProcess, INFINITE);
            GetExitCodeProcess(pi.hProcess, &code);
            CloseHandle(pi.hThread);
            CloseHandle(pi.hProcess);
            return (int)code;
        }
    }
    if (argc < 5) {
        printf("usage: fullscreen_mouse_harness <SDL2.dll folder> <game exe> <game 1-5> stock|fixed|refused "
               "[companion]\n");
        return 2;
    }
    g_game = atoi(argv[3]);
    stock = strcmp(argv[4], "stock") == 0;
    fixed = strcmp(argv[4], "fixed") == 0;
    refused = strcmp(argv[4], "refused") == 0;
    if (g_game < 1 || g_game > 5 || (!stock && !fixed && !refused) || (!stock && argc < 6)) {
        return 2;
    }
    fw = GAMES[g_game - 1].w;
    fh = GAMES[g_game - 1].h;

    sprintf_s(desktop_name, sizeof desktop_name, "vvfp_fullscreen_mouse_%lu", GetCurrentProcessId());
    desktop = CreateDesktopA(desktop_name, NULL, NULL, 0, GENERIC_ALL, NULL);
    if (desktop == NULL || !SetThreadDesktop(desktop)) {
        printf("FAIL private desktop (%lu)\n", GetLastError());
        return 3;
    }
    sprintf_s(path, sizeof path, "%s\\SDL2.dll", argv[1]);
    g_sdl = LoadLibraryA(path);
    if (g_sdl == NULL) {
        printf("FAIL load %s (%lu)\n", path, GetLastError());
        return 4;
    }
    if (!map_game(argv[2])) {
        printf("FAIL map %s\n", argv[2]);
        return 5;
    }
    s_poll = (poll_fn)GetProcAddress(g_sdl, "SDL_PollEvent");
    *game_import("SDL_PollEvent") = (void *)poll_through;
    /* The pump gets the stand-in input manager: `mov eax, holder / ret` at the start of the routine that hands
       the game's out (this mapped copy only). */
    {
        unsigned char *at = (unsigned char *)(UINT_PTR)GAMES[g_game - 1].manager;
        if (at[0] != 0x6A || at[1] != 0xFF) {   /* push -1: the stock routine's first instruction */
            printf("FAIL the input manager routine is not where expected\n");
            return 6;
        }
        at[0] = 0xB8;
        *(void **)(at + 1) = (void *)g_holder;
        at[5] = 0xC3;
        *(void **)(g_manager + 4) = (void *)g_listener;
    }
    printf("   game %d (%s): pump 0x%X, picture %dx%d\n", g_game, argv[2], GAMES[g_game - 1].pump, fw, fh);

    if (!stock) {
        startup_fn startup;
        installed_fn is_installed;
        use_module_fn use_module;
        fix = LoadLibraryA(argv[5]);
        if (fix == NULL) {
            printf("FAIL load %s (%lu)\n", argv[5], GetLastError());
            return 7;
        }
        startup = (startup_fn)GetProcAddress(fix, "VvfpStartup");
        is_installed = (installed_fn)GetProcAddress(fix, "VvfpFullscreenMouseInstalled");
        use_module = (use_module_fn)GetProcAddress(fix, "VvfpFullscreenMouseTestUseModule");
        convert = g_convert = (convert_fn)GetProcAddress(fix, "VvfpFullscreenMouseTestConvert");
        if (startup == NULL || is_installed == NULL || use_module == NULL || convert == NULL) {
            printf("FAIL companion exports\n");
            return 8;
        }
        use_module((HMODULE)g_image);
        startup(g_game, 0);
        installed = is_installed();
    }
    check(stock || installed == (fixed ? 1 : 0), fixed ? "companion installed with the stock SDL 2.0.3 and game"
                                                       : (refused ? "companion refuses a changed SDL2.dll"
                                                                  : "no companion"));

    s_init = (init_fn)GetProcAddress(g_sdl, "SDL_Init");
    s_create_window = (create_window_fn)*game_import("SDL_CreateWindow");
    s_create_renderer = (create_renderer_fn)*game_import("SDL_CreateRenderer");
    s_create_texture = (create_texture_fn)*game_import("SDL_CreateTexture");
    s_hint = (hint_fn)*game_import("SDL_SetHint");
    s_logical = (logical_fn)*game_import("SDL_RenderSetLogicalSize");
    s_window_size = (window_size_fn)*game_import("SDL_SetWindowSize");
    s_fullscreen = (fullscreen_fn)*game_import("SDL_SetWindowFullscreen");
    s_clear = (int_ptr_fn)*game_import("SDL_RenderClear");
    s_present = (int_ptr_fn)*game_import("SDL_RenderPresent");
    s_wm_info = (wm_info_fn)GetProcAddress(g_sdl, "SDL_GetWindowWMInfo");
    s_quit = (quit_fn)GetProcAddress(g_sdl, "SDL_Quit");
    ((hint_fn)GetProcAddress(g_sdl, "SDL_SetHint"))("SDL_RENDER_DRIVER", "software");
    if (s_init(0x20u) != 0) {
        printf("FAIL SDL_Init\n");
        return 9;
    }
    /* As the games (New Believers 0x408480): through the game's own imports. */
    g_window = s_create_window("fullscreen_mouse_harness", 0x2FFF0000, 0x2FFF0000, fw, fh, 0x20u);
    renderer = g_window ? s_create_renderer(g_window, -1, 0) : NULL;
    if (renderer == NULL || s_create_texture(renderer, 0x16362004u, 1, fw, fh) == NULL) {
        printf("FAIL SDL window, renderer or texture\n");
        return 10;
    }
    s_hint("SDL_RENDER_SCALE_QUALITY", "linear");
    s_logical(renderer, fw, fh);
    memset(info, 0, sizeof info);
    info[0] = 2;
    info[2] = 3;
    if (!s_wm_info(g_window, info) || (g_hwnd = *(HWND *)(info + 8)) == NULL) {
        printf("FAIL window handle\n");
        return 11;
    }
    s_clear(renderer);
    s_present(renderer);
    drain();

    scenario("A. a window of the picture's own size", fixed, 1);

    s_window_size(g_window, fw * 3 / 2, fh * 3 / 2);
    drain();
    s_clear(renderer);   /* SDL applies a new size at its next drawing call */
    s_present(renderer);
    scenario("B. a window 1.5 times the picture", fixed, 0);

    s_window_size(g_window, fw * 2, fh + fh / 4);
    drain();
    s_clear(renderer);
    s_present(renderer);
    scenario("C. a wide window (black bars at the sides)", fixed, 0);

    s_window_size(g_window, fw, fh);
    drain();
    s_fullscreen(g_window, 0x1001u);
    drain();
    s_clear(renderer);
    s_present(renderer);
    scenario("D. full screen (the game's own full screen, 0x1001)", fixed, 0);


    s_fullscreen(g_window, 0);
    drain();
    s_window_size(g_window, fw, fh);
    drain();
    s_clear(renderer);
    s_present(renderer);
    scenario("E. back to a window of the picture's own size", fixed, 1);

    s_quit();
    printf("== %d check(s), %d failure(s) ==\n", g_checks, g_failures);
    return g_failures ? 1 : 0;
}

int main(int argc, char **argv) {
    /* Never the real Documents (the owner, 2026-10-10): the companion and SDL load into a process whose Documents is
       a throwaway %TEMP% folder -- here and in the copy run() starts, before either loads anything. */
    if (!harness_redirect_documents_process()) return 2;
    return run(argc, argv);
}
