/* Runtime harness for "VVFP VV1 Number Keys.dll".  32-bit only.

   Runs the companion instead of reading it: the DLL is loaded, the game's
   own SDL2.dll is initialised for events, Vv1NumberKeysInstall registers the
   watch, and synthetic key events are pushed through SDL_PushEvent -- which
   runs event watches synchronously -- while a fake village state sits at the
   address the game keeps its pointer, 0x0048AEDC (a 64 KiB block reserved at
   0x00480000, which a small harness executable leaves free).

   Usage:  vv1_number_keys_harness.exe "<path to VVFP VV1 Number Keys.dll>" "<path to SDL2.dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

typedef int (__stdcall *install_t)(void);
typedef int (__stdcall *probe_t)(const void *);
typedef int (__stdcall *update_t)(void *screen);
typedef int (__cdecl *sdl_init_t)(unsigned int);
typedef int (__cdecl *sdl_push_t)(void *);
typedef void (__cdecl *sdl_quit_t)(void);

/* Where a glide actually comes to rest.

   The measured VV2 recurrence is cur + (target - cur) / 10 with no forced
   minimum step and no final snap, and it deactivates once each remaining
   delta divided by 10 truncates to zero.  So a glide STOPS SHORT of its
   target -- by up to 9 units per axis -- and never reports the target's own
   coordinates.  Waiting for exact equality spins forever.

   That residual is the behaviour VV2 was measured to have, so the harness
   checks the documented stop condition rather than asserting an arrival the
   implementation is not supposed to make. */
static int vv1_pan_settled(int cur, int target) {
    return (target - cur) / 10 == 0;
}

/* The glide's terminal coordinate for one axis, for an exact check. */
static int vv1_pan_rest(int start, int target) {
    int cur = start;
    int guard = 0;
    while (!vv1_pan_settled(cur, target) && guard++ < 1000) {
        cur = cur + (target - cur) / 10;
    }
    return cur;
}

static void key_event(unsigned char *e, unsigned int type, int sym, unsigned char repeat, unsigned short mod) {
    memset(e, 0, 56);
    *(unsigned int *)(e + 0) = type;
    e[12] = 1;                      /* state: pressed */
    e[13] = repeat;
    *(int *)(e + 20) = sym;
    *(unsigned short *)(e + 24) = mod;
}

int main(int argc, char **argv) {
    HMODULE dll, sdl;
    install_t install;
    probe_t probe;
    sdl_init_t sdl_init;
    sdl_push_t sdl_push;
    sdl_quit_t sdl_quit;
    unsigned char e[56];
    void *block;
    int *state;
    int *x, *y;
    unsigned char screen[0x300];
    if (argc < 3) {
        printf("usage: harness <number keys dll> <SDL2.dll>\n");
        return 2;
    }
    printf("== probe (pure classification, no game state) ==\n");
    dll = LoadLibraryA(argv[1]);
    CHECK(dll != NULL, "DLL loads");
    if (!dll) return 1;
    install = (install_t)GetProcAddress(dll, "Vv1NumberKeysInstall");
    probe = (probe_t)GetProcAddress(dll, "Vv1NumberKeysProbe");
    CHECK(install && probe, "both exports resolve");
    if (!install || !probe) return 1;
    key_event(e, 0x300, '1', 0, 0); CHECK(probe(e) == 1, "'1' -> section 1");
    key_event(e, 0x300, '9', 0, 0); CHECK(probe(e) == 9, "'9' -> section 9");
    key_event(e, 0x300, '5', 0, 0); CHECK(probe(e) == 5, "'5' -> section 5");
    key_event(e, 0x300, 0x40000059, 0, 0); CHECK(probe(e) == 1, "keypad 1 -> section 1");
    key_event(e, 0x300, 0x40000061, 0, 0); CHECK(probe(e) == 9, "keypad 9 -> section 9");
    key_event(e, 0x300, '0', 0, 0); CHECK(probe(e) == 0, "'0' is not a section");
    key_event(e, 0x300, 0x40000062, 0, 0); CHECK(probe(e) == 0, "keypad 0 is not a section");
    key_event(e, 0x300, 'a', 0, 0); CHECK(probe(e) == 0, "a letter is not a section");
    key_event(e, 0x300, '3', 1, 0); CHECK(probe(e) == 0, "auto-repeat of '3' is ignored");
    key_event(e, 0x300, '3', 0, 0x0040); CHECK(probe(e) == 0, "Ctrl+3 is ignored");
    key_event(e, 0x300, '3', 0, 0x0100); CHECK(probe(e) == 0, "Alt+3 is ignored");
    key_event(e, 0x300, '3', 0, 0x0001); CHECK(probe(e) == 3, "Shift+3 still counts (it is the same key)");
    key_event(e, 0x301, '3', 0, 0); CHECK(probe(e) == 0, "KEYUP is ignored");
    key_event(e, 0x303, '3', 0, 0); CHECK(probe(e) == 0, "TEXTINPUT is ignored");
    CHECK(probe(NULL) == 0, "NULL event is ignored");

    printf("== live: watch installed through the game's SDL2.dll, fake village at 0x0048AEDC ==\n");
    block = VirtualAlloc((void *)0x00480000, 0x10000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (block != (void *)0x00480000) {
        MEMORY_BASIC_INFORMATION mbi;
        VirtualQuery((void *)0x0048AEDC, &mbi, sizeof mbi);
        printf("  (VirtualAlloc at 0x00480000 failed, error %lu; 0x0048AEDC is state %#lx protect %#lx base %p)\n",
               GetLastError(), mbi.State, mbi.Protect, mbi.AllocationBase);
        /* Already mapped writable (e.g. inside this harness's own image when
           it is linked at 0x400000): use it in place. */
        if (mbi.State == MEM_COMMIT && (mbi.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE))) {
            block = (void *)0x00480000;
        } else if (mbi.State == MEM_RESERVE) {
            /* Inside somebody's reservation (the CRT heap reserves a large
               range): committing one page of it is enough for a harness. */
            if (VirtualAlloc((void *)0x0048A000, 0x1000, MEM_COMMIT, PAGE_READWRITE) == (void *)0x0048A000) {
                block = (void *)0x00480000;
            }
        }
    }
    CHECK(block == (void *)0x00480000, "a writable dword exists at 0x0048AEDC for the fake pointer slot");
    if (block != (void *)0x00480000) return 1;
    state = (int *)malloc(0x1000);
    memset(state, 0, 0x1000);
    memset(screen, 0, sizeof screen);
    *(void **)(screen + 0x10) = state;
    x = (int *)((unsigned char *)state + 8);
    y = (int *)((unsigned char *)state + 0xC);
    *x = 123; *y = 456;
    sdl = LoadLibraryA(argv[2]);
    CHECK(sdl != NULL, "SDL2.dll loads");
    if (!sdl) return 1;
    sdl_init = (sdl_init_t)GetProcAddress(sdl, "SDL_Init");
    sdl_push = (sdl_push_t)GetProcAddress(sdl, "SDL_PushEvent");
    sdl_quit = (sdl_quit_t)GetProcAddress(sdl, "SDL_Quit");
    CHECK(sdl_init && sdl_push && sdl_quit, "SDL_Init / SDL_PushEvent / SDL_Quit resolve");
    CHECK(sdl_init(0x4000) == 0, "SDL_Init(SDL_INIT_EVENTS)");
    CHECK(install() == 1, "Vv1NumberKeysInstall returns 1 (watch registered)");
    CHECK(install() == 1, "second install is a no-op that still reports 1");

    /* No village yet: the pointer slot is null, a key must not touch memory. */
    *(void **)0x0048AEDC = NULL;
    key_event(e, 0x300, '3', 0, 0); sdl_push(e);
    CHECK(*x == 123 && *y == 456, "no village pointer: nothing written");

    *(void **)0x0048AEDC = state;
    {
        update_t tick = (update_t)GetProcAddress(dll, "Vv1NumberKeysUpdate");
        int n, ok, px, py, first_dx;
        CHECK(tick != NULL, "Vv1NumberKeysUpdate resolves");
        if (!tick) return 1;
        *x = 123; *y = 456;
        tick(screen); tick(screen);
        CHECK(*x == 123 && *y == 456, "ticks with no key pressed move nothing");

        printf("== glide: a key sets a target, ticks ease toward it ==\n");
        key_event(e, 0x300, '3', 0, 0); sdl_push(e);
        CHECK(*x == 123 && *y == 456, "the key press itself moves nothing (the glide does)");
        px = *x; py = *y;
        tick(screen);
        first_dx = *x - px;
        CHECK(first_dx == (850 - 123) / 10, "first tick moves a tenth of the way in x (%d)", first_dx);
        CHECK(*y - py == (1200 - 456) / 10, "first tick moves a tenth of the way in y (%d)", *y - py);
        ok = 1;
        for (n = 0; n < 200 && !(vv1_pan_settled(*x, 850) && vv1_pan_settled(*y, 1200)); ++n) {
            px = *x; py = *y;
            tick(screen);
            if (*x < px || *y < py || *x > 850 || *y > 1200) ok = 0;   /* monotonic, never overshoots */
        }
        CHECK(vv1_pan_settled(*x, 850) && vv1_pan_settled(*y, 1200), "'3' settles within a tick of measured bottom-right (850, 1200), got (%d, %d)", *x, *y);
        CHECK(ok, "the glide is monotonic and never overshoots");
        CHECK(n < 200, "it lands within %d ticks", n + 1);
        px = *x; py = *y; tick(screen);
        CHECK(*x == px && *y == py, "once landed, further ticks move nothing");

        key_event(e, 0x300, '7', 0, 0); sdl_push(e);
        for (n = 0; n < 200 && !(vv1_pan_settled(*x, -150) && vv1_pan_settled(*y, 0)); ++n) tick(screen);
        CHECK(vv1_pan_settled(*x, -150) && vv1_pan_settled(*y, 0), "'7' settles within a tick of measured top-left (-150, 0), got (%d, %d)", *x, *y);
        key_event(e, 0x300, '5', 0, 0); sdl_push(e);
        for (n = 0; n < 200 && !(vv1_pan_settled(*x, 300) && vv1_pan_settled(*y, 570)); ++n) tick(screen);
        CHECK(vv1_pan_settled(*x, 300) && vv1_pan_settled(*y, 570), "'5' settles within a tick of measured centre (300, 570), got (%d, %d)", *x, *y);
        key_event(e, 0x300, 0x40000059, 0, 0); sdl_push(e);
        for (n = 0; n < 200 && !(vv1_pan_settled(*x, -150) && vv1_pan_settled(*y, 1200)); ++n) tick(screen);
        CHECK(vv1_pan_settled(*x, -150) && vv1_pan_settled(*y, 1200), "keypad 1 settles within a tick of measured bottom-left (-150, 1200), got (%d, %d)", *x, *y);

        printf("== an external scroll during the glide does NOT cancel it ==\n");
        /* Dragging a villager auto-scrolls the view, which is indistinguishable
           from a hand scroll in the state; the owner wants a number key to win
           either way, so a perturbed scroll must keep gliding to the target. */
        key_event(e, 0x300, '9', 0, 0); sdl_push(e);
        tick(screen); tick(screen);
        *x -= 40;                /* something else moved the view mid-glide */
        px = *x; py = *y;
        tick(screen); tick(screen);
        CHECK(*x > px, "after an external scroll the glide keeps moving x toward 885 (%d -> %d)", px, *x);
        CHECK(*y < py, "after an external scroll the glide keeps moving y toward -5 (%d -> %d)", py, *y);
        for (n = 0; n < 200 && !(vv1_pan_settled(*x, 850) && vv1_pan_settled(*y, 0)); ++n) tick(screen);
        CHECK(vv1_pan_settled(*x, 850) && vv1_pan_settled(*y, 0), "and still lands at measured top-right (850, 0), got (%d, %d)", *x, *y);

        printf("== a new key mid-glide retargets ==\n");
        key_event(e, 0x300, '1', 0, 0); sdl_push(e);
        tick(screen); tick(screen);
        key_event(e, 0x300, '9', 0, 0); sdl_push(e);
        for (n = 0; n < 200 && !(vv1_pan_settled(*x, 850) && vv1_pan_settled(*y, 0)); ++n) tick(screen);
        CHECK(vv1_pan_settled(*x, 850) && vv1_pan_settled(*y, 0), "'9' after '1' lands at measured top-right (850, 0), got (%d, %d)", *x, *y);

        key_event(e, 0x300, '9', 1, 0); *x = 1; *y = 1; sdl_push(e); tick(screen);
        CHECK(*x == 1 && *y == 1, "repeat of '9' leaves the state alone");
        key_event(e, 0x300, 'q', 0, 0); sdl_push(e); tick(screen);
        CHECK(*x == 1 && *y == 1, "'q' leaves the state alone");
        /* other event types flow through untouched */
        memset(e, 0, sizeof e); *(unsigned int *)e = 0x400; sdl_push(e); tick(screen);
        CHECK(*x == 1 && *y == 1, "a mouse-motion event leaves the state alone");
        /* the village going away mid-glide is harmless */
        key_event(e, 0x300, '5', 0, 0); sdl_push(e); tick(screen);
        *(void **)0x0048AEDC = NULL; tick(screen); tick(screen);
        CHECK(1, "ticks with the village gone do not crash");
    }
    sdl_quit();
    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
