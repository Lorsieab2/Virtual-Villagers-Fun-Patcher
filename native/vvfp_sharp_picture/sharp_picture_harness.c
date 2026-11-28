/* sharp_picture_harness -- "VVFP Sharp Picture.dll" (the 4K filter) with a game's own frame routine, the games'
   own SDL2.dll and Direct3D, before any live test.

   usage: sharp_picture_harness.exe <SDL2.dll folder> <game exe> <game 1-5> <companion test DLL> <frame.argb>
                                    <out prefix> fixed|refused [stretch]

   The game's executable (a stock copy) is mapped at its own base, 0x400000; its SDL2.dll imports are bound to the
   real SDL2.dll.  The companion's test build is started as VVFP More Companions.dll starts it.  A window is made
   through the game's own SDL_CreateWindow import (HIDDEN: nobody sees it; Direct3D draws to a hidden window as to
   a shown one), with the renderer, the ARGB8888 texture, the hint and the logical size as the game makes them.
   Then the game's OWN frame routine (New Believers 0x404680) runs, unchanged, as machine code, with a stand-in for
   the game's window object and a surface holding <frame.argb> -- so SDL_UpdateTexture, SDL_RenderClear,
   SDL_RenderCopy and SDL_RenderPresent are the game's own calls through its imports.

     fixed    installed; the window opens at 1024x768 times the Windows scaling; the picture the companion drew (its
              test build keeps a copy) is compared with the CPU reference of the same filter (native/vvfp_4k_filter)
              in a window and in full screen; the picture's rectangle; a click on a black bar is dropped and one on
              the picture is not.  The pictures are written to <out prefix>.<state>.argb.
     refused  the frame routine of the mapped copy changed by one byte: nothing installed.
   With "stretch", "VVFP Sharp Picture.txt" (stretch) is written beside this harness's patcher folder first.

   Prints "ok <check>" / "FAIL <check>" and "== N check(s), M failure(s) ==".  Exit code 0 only with no failure. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../shared/harness_redirect_documents.h"
#include "../vvfp_4k_filter/vv4k_filters.h"

typedef int(__cdecl *init_fn)(unsigned int);
typedef void *(__cdecl *create_window_fn)(const char *, int, int, int, int, unsigned int);
typedef void *(__cdecl *create_renderer_fn)(void *, int, unsigned int);
typedef void *(__cdecl *create_texture_fn)(void *, unsigned int, int, int, int);
typedef int(__cdecl *hint_fn)(const char *, const char *);
typedef int(__cdecl *logical_fn)(void *, int, int);
typedef int(__cdecl *poll_fn)(void *);
typedef int(__cdecl *wm_info_fn)(void *, void *);
typedef void(__cdecl *quit_fn)(void);
typedef void(__stdcall *startup_fn)(int, unsigned int);
typedef int(__stdcall *installed_fn)(void);
typedef void(__stdcall *use_module_fn)(HMODULE);
typedef int(__stdcall *rect_fn)(int *, int *, int *, int *);
typedef int(__stdcall *picture_fn)(unsigned int *, int, int *, int *, int *);

static const struct {
    unsigned int frame;
    int w, h;
} GAMES[5] = {
    {0x403830, 800, 600}, {0x403AC0, 800, 600}, {0x4040E0, 800, 600}, {0x4046F0, 800, 600}, {0x404680, 1024, 768},
};

static HMODULE g_sdl;
static unsigned char *g_image;
static int g_checks, g_failures;

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
        printf("FAIL the game's base is taken in this process\n");
        return 0;
    }
    memcpy(g_image, raw, nt->OptionalHeader.SizeOfHeaders);
    section = IMAGE_FIRST_SECTION(nt);
    for (i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        memcpy(g_image + section[i].VirtualAddress, raw + section[i].PointerToRawData,
               min(section[i].SizeOfRawData,
                   section[i].Misc.VirtualSize ? section[i].Misc.VirtualSize : section[i].SizeOfRawData));
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

/* The game's frame routine: thiscall, one argument (the game's picture surface), ret 4. */
static void run_frame(unsigned int frame, void *self, void *surface) {
    __asm {
        push surface
        mov ecx, self
        call frame
    }
}

static unsigned char g_object[0x100];   /* the game's window object, as far as the frame routine looks */
static unsigned char g_surface[0x40];   /* an SDL_Surface: +0x10 pitch, +0x14 pixels */
static poll_fn s_poll;
static HWND g_hwnd;

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

/* A left press and release at window pixel (x, y): 1 when SDL queued the press for the game. */
static int click_reaches_game(int x, int y) {
    unsigned char event[64];
    int pressed = 0;
    drain();
    SendMessageW(g_hwnd, WM_MOUSEMOVE, 0, MAKELPARAM(x, y));
    SendMessageW(g_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, MAKELPARAM(x, y));
    SendMessageW(g_hwnd, WM_LBUTTONUP, 0, MAKELPARAM(x, y));
    while (s_poll(event)) {
        if (*(unsigned int *)event == 0x401u) {
            pressed = 1;
        }
    }
    return pressed;
}

/* Run the game's frame routine a few times; compare the companion's picture with the CPU reference. */
static void compare(const char *label, picture_fn picture, int game, const vv4k_image *frame, const char *prefix,
                    int stretch) {
    static unsigned int buffer[4096 * 2400];
    int w = 0, h = 0, stages = 0, i, worst = 0, cw, ch;
    long long over = 0;
    RECT client;
    vv4k_image reference;
    char name[256], path[MAX_PATH * 2];
    FILE *file;
    for (i = 0; i < 4; ++i) {
        run_frame(GAMES[game - 1].frame, g_object, g_surface);
        drain();
    }
    GetClientRect(g_hwnd, &client);
    cw = client.right;
    ch = client.bottom;
    if (!picture(buffer, (int)(sizeof buffer / sizeof buffer[0]), &w, &h, &stages)) {
        sprintf_s(name, sizeof name, "%s: the companion drew a picture", label);
        check(0, name);
        return;
    }
    sprintf_s(name, sizeof name, "%s: the picture is the window's size (%dx%d, the window %dx%d), %s", label, w, h, cw,
              ch, stages == 2 ? "4x" : "2x");
    check(w == cw && h == ch, name);
    if (vv4k_alloc(&reference, w, h) != 0) {
        return;
    }
    {
        int fx, fy, fw, fh;
        int k;
        for (k = 0; k < w * h; ++k) {
            reference.pixels[k] = 0xFF000000u;
        }
        if (stretch) {
            fx = fy = 0;
            fw = w;
            fh = h;
        } else {
            vv4k_fit_rect(frame->width, frame->height, w, h, &fx, &fy, &fw, &fh);
        }
        if (stages == 2) {
            vv4k_image x2, x4;
            vv4k_edge_directed_2x(frame, &x2);
            vv4k_edge_directed_2x(&x2, &x4);
            vv4k_fit_catmull_rom(&x4, frame->width, frame->height, 4.0, -1.5, &reference, fx, fy, fw, fh);
            vv4k_free(&x2);
            vv4k_free(&x4);
        } else {
            vv4k_image x2;
            vv4k_edge_directed_2x(frame, &x2);
            vv4k_fit_catmull_rom(&x2, frame->width, frame->height, 2.0, -0.5, &reference, fx, fy, fw, fh);
            vv4k_free(&x2);
        }
    }
    for (i = 0; i < w * h; ++i) {
        unsigned int a = buffer[i], b = reference.pixels[i];
        int c, d = 0;
        for (c = 0; c < 24; c += 8) {
            int e = abs((int)((a >> c) & 0xFF) - (int)((b >> c) & 0xFF));
            if (e > d) d = e;
        }
        if (d > worst) worst = d;
        if (d > 2) ++over;
    }
    sprintf_s(name, sizeof name, "%s: the picture is the filter's (largest difference %d/255, %.4f%% of pixels over 2)",
              label, worst, 100.0 * (double)over / ((double)w * h));
    check(worst <= 8 && over * 1000 < (long long)w * h, name);
    sprintf_s(path, sizeof path, "%s.%s.%dx%d.argb", prefix, label, w, h);
    if (fopen_s(&file, path, "wb") == 0 && file != NULL) {
        fwrite(buffer, 4, (size_t)w * h, file);
        fclose(file);
    }
    vv4k_free(&reference);
}

static int run(int argc, char **argv) {
    char path[MAX_PATH * 2], desktop_unused[4];
    int game, fixed, stretch, installed, fw, fh, dpi = 96;
    HMODULE fix;
    startup_fn startup;
    installed_fn is_installed;
    use_module_fn use_module;
    rect_fn rect;
    picture_fn picture;
    init_fn s_init;
    void *window, *renderer, *texture;
    unsigned char info[64];
    vv4k_image frame;
    FILE *file;
    (void)desktop_unused;

    {
        MEMORY_BASIC_INFORMATION mbi;
        VirtualQuery((void *)0x400000, &mbi, sizeof mbi);
        if (!(mbi.State == MEM_RESERVE && mbi.AllocationBase == (void *)0x400000)) {
            /* Windows maps its own data into low addresses while a process starts: start again, suspended, with
               0x400000 held for the game's executable, and pass on the exit code. */
            STARTUPINFOW si;
            PROCESS_INFORMATION pi;
            DWORD code = 1;
            if (GetEnvironmentVariableA("VVFP_SHARP_PICTURE_CHILD", path, sizeof path) != 0) {
                printf("FAIL 0x400000 could not be held for the game\n");
                return 2;
            }
            SetEnvironmentVariableA("VVFP_SHARP_PICTURE_CHILD", "1");
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
    if (argc < 8) {
        printf("usage: sharp_picture_harness <SDL2.dll folder> <game exe> <game> <companion> <frame.argb> <out prefix>"
               " fixed|refused [stretch]\n");
        return 2;
    }
    game = atoi(argv[3]);
    fixed = strcmp(argv[7], "fixed") == 0;
    stretch = argc > 8 && strcmp(argv[8], "stretch") == 0;
    if (game < 1 || game > 5) {
        return 2;
    }
    fw = GAMES[game - 1].w;
    fh = GAMES[game - 1].h;
    if (vv4k_alloc(&frame, fw, fh) != 0 || fopen_s(&file, argv[5], "rb") != 0 || file == NULL) {
        printf("FAIL read %s\n", argv[5]);
        return 3;
    }
    fread(frame.pixels, 4, (size_t)fw * fh, file);
    fclose(file);
    {
        /* the patcher's folder beside this harness: the settings file (stretch), or none (black bars) */
        wchar_t folder[MAX_PATH * 2], *slash;
        GetModuleFileNameW(NULL, folder, MAX_PATH);
        slash = wcsrchr(folder, L'\\');
        if (slash != NULL) {
            lstrcpyW(slash + 1, L"Virtual Villagers Fun Patcher Files");
            CreateDirectoryW(folder, NULL);
            lstrcatW(folder, L"\\VVFP Sharp Picture.txt");
            if (stretch) {
                HANDLE h = CreateFileW(folder, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
                DWORD put;
                WriteFile(h, "stretch", 7, &put, NULL);
                CloseHandle(h);
            } else {
                DeleteFileW(folder);
            }
        }
    }
    sprintf_s(path, sizeof path, "%s\\SDL2.dll", argv[1]);
    g_sdl = LoadLibraryA(path);
    if (g_sdl == NULL || !map_game(argv[2])) {
        printf("FAIL load SDL2.dll or map %s\n", argv[2]);
        return 4;
    }
    if (!fixed) {
        /* the frame routine's first call (SDL_UpdateTexture) no longer reaches the import: not the stock game */
        unsigned char *at = (unsigned char *)(UINT_PTR)GAMES[game - 1].frame;
        int i;
        for (i = 0; i < 0x40; ++i) {
            if (at[i] == 0xE8) {
                at[i + 1] ^= 0x01;
                break;
            }
        }
    }
    fix = LoadLibraryA(argv[4]);
    startup = fix ? (startup_fn)GetProcAddress(fix, "VvfpStartup") : NULL;
    is_installed = fix ? (installed_fn)GetProcAddress(fix, "VvfpSharpPictureInstalled") : NULL;
    use_module = fix ? (use_module_fn)GetProcAddress(fix, "VvfpSharpPictureTestUseModule") : NULL;
    rect = fix ? (rect_fn)GetProcAddress(fix, "VvfpSharpPictureRect") : NULL;
    picture = fix ? (picture_fn)GetProcAddress(fix, "VvfpSharpPictureTestPicture") : NULL;
    if (!startup || !is_installed || !use_module || !rect || !picture) {
        printf("FAIL companion exports\n");
        return 5;
    }
    use_module((HMODULE)g_image);
    startup(game, 0);
    installed = is_installed();
    check(installed == fixed, fixed ? "installed with the stock SDL 2.0.3 and game"
                                    : "nothing installed when the frame routine is not the stock one");
    if (!fixed) {
        printf("== %d check(s), %d failure(s) ==\n", g_checks, g_failures);
        return g_failures ? 1 : 0;
    }
    {
        HDC screen = GetDC(NULL);
        dpi = GetDeviceCaps(screen, LOGPIXELSX);
        ReleaseDC(NULL, screen);
    }
    s_poll = (poll_fn)GetProcAddress(g_sdl, "SDL_PollEvent");
    s_init = (init_fn)GetProcAddress(g_sdl, "SDL_Init");
    if (s_init(0x20u) != 0) {
        printf("FAIL SDL_Init\n");
        return 6;
    }
    /* As the games: through the game's own imports (the companion's, now); HIDDEN added so nobody sees it. */
    window = ((create_window_fn)*game_import("SDL_CreateWindow"))("sharp_picture_harness", 0x2FFF0000, 0x2FFF0000, fw,
                                                                  fh, 0x20u | 0x8u);
    renderer = window ? ((create_renderer_fn)*game_import("SDL_CreateRenderer"))(window, -1, 0) : NULL;
    texture = renderer ? ((create_texture_fn)*game_import("SDL_CreateTexture"))(renderer, 0x16362004u, 1, fw, fh)
                       : NULL;
    if (texture == NULL) {
        printf("FAIL SDL window, renderer or texture\n");
        return 7;
    }
    ((hint_fn)*game_import("SDL_SetHint"))("SDL_RENDER_SCALE_QUALITY", "linear");
    ((logical_fn)*game_import("SDL_RenderSetLogicalSize"))(renderer, fw, fh);
    memset(info, 0, sizeof info);
    info[0] = 2;
    info[2] = 3;
    ((wm_info_fn)GetProcAddress(g_sdl, "SDL_GetWindowWMInfo"))(window, info);
    g_hwnd = *(HWND *)(info + 8);
    {
        RECT client;
        char name[160];
        GetClientRect(g_hwnd, &client);
        sprintf_s(name, sizeof name, "the window opens at 1024x768 times the Windows scaling (%d dpi): %ldx%ld", dpi,
                  client.right, client.bottom);
        check(client.right == MulDiv(1024, dpi, 96) && client.bottom == MulDiv(768, dpi, 96), name);
    }
    /* the game's window object and picture surface, as far as the frame routine reads them */
    *(void **)(g_object + 0x34) = renderer;
    *(void **)(g_object + 0x38) = window;
    *(void **)(g_object + 0x3C) = texture;
    *(int *)(g_object + 0x50) = -1;            /* no pointer to put back */
    *(int *)(g_surface + 0x10) = fw * 4;
    *(void **)(g_surface + 0x14) = frame.pixels;

    compare("window", picture, game, &frame, argv[6], stretch);
    {
        int x, y, w, h, cw, ch;
        char name[200];
        RECT client;
        GetClientRect(g_hwnd, &client);
        cw = client.right;
        ch = client.bottom;
        check(rect(&x, &y, &w, &h) && (stretch ? (x == 0 && y == 0 && w == cw && h == ch)
                                               : (h == ch && abs(w * fh - h * fw) <= fh && x == (cw - w) / 2)),
              stretch ? "window: the picture fills the window (stretch)" : "window: the picture's rectangle");
        if (!stretch && x > 2) {
            check(!click_reaches_game(x / 2, ch / 2), "window: a click on a black bar does nothing");
        }
        check(click_reaches_game(cw / 2, ch / 2), "window: a click on the picture reaches the game");
        sprintf_s(name, sizeof name, "window: rectangle %d,%d %dx%d", x, y, w, h);
        printf("   %s\n", name);
    }
    /* Full screen's size: the window made exactly the screen's real pixels, still hidden (the game's full screen
       would show it on the person's screen). */
    ((void(__cdecl *)(void *, int, int))GetProcAddress(g_sdl, "SDL_SetWindowSize"))(
        window, GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN));
    drain();
    compare("screen", picture, game, &frame, argv[6], stretch);
    {
        int x, y, w, h;
        RECT client;
        GetClientRect(g_hwnd, &client);
        check(client.right == GetSystemMetrics(SM_CXSCREEN) && client.bottom > 2 * GetSystemMetrics(SM_CYSCREEN) / 3,
              "screen-size window: as wide as the screen in real pixels (Windows keeps its frame on the screen)");
        if (rect(&x, &y, &w, &h)) {
            printf("   fullscreen: rectangle %d,%d %dx%d of %ldx%ld\n", x, y, w, h, client.right, client.bottom);
            if (!stretch && x > 2) {
                check(!click_reaches_game(x / 2, client.bottom / 2), "screen-size window: a click on a black bar does nothing");
            }
            check(click_reaches_game(client.right / 2, client.bottom / 2),
                  "screen-size window: a click on the picture reaches the game");
        }
    }
    ((quit_fn)GetProcAddress(g_sdl, "SDL_Quit"))();
    printf("== %d check(s), %d failure(s) ==\n", g_checks, g_failures);
    return g_failures ? 1 : 0;
}

int main(int argc, char **argv) {
    /* Never the real Documents (the owner, 2026-10-10): a throwaway %TEMP% Documents, in this process and in the
       copy run() starts, before anything is loaded. */
    if (!harness_redirect_documents_process()) return 2;
    return run(argc, argv);
}
