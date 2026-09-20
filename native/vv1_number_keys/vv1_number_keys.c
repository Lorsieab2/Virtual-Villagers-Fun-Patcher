/* VVFP VV1 Number Keys -- zip around the island with the numeric keys.

   The later games let the number keys jump the view to one of nine sections
   of the map, laid out like a numeric keypad:

       7 8 9        top row
       4 5 6        middle
       1 2 3        bottom row

   A New Home never had it.  This companion adds it entirely on its own: no
   bytes in the executable, because everything the feature needs already
   exists.  The Origins companion loads this DLL once and calls
   Vv1NumberKeysInstall; if this file is not beside the executable, the game
   simply has no number keys, exactly as before.

   HOW THE VIEW IS MOVED.  The village state object (the one 0x41D500
   returns, cached at 0x0048AEDC -- the same object the doubler flags and the
   tribe name live in) keeps the scroll position as its first two dwords past
   the header: +8 is x, +0xC is y.  They are the first two dwords of the .ldw
   payload too (file 0xC/0x10), which is how they were confirmed against the
   owner's saves.  The game's own map-screen click handler at 0x429BA0 writes
   them directly and then clamps:

       0x429C8E  cmp ecx, -205   ...   0x429C9F  cmp ecx, 885     (x)
       0x429CB4  cmp eax, -5     ...   0x429CC8  cmp eax, 1205    (y)

   so those four numbers are the game's own bounds, and a section is simply
   the corresponding extreme (the midpoint for the middle row or column) --
   what The Lost Children lands on for the same keys: its key 1 reads back
   (x min, y max) and key 9 (x max, y min), measured live.  Writing the pair
   and nothing else is what the game itself does on a map click, so nothing
   else needs refreshing.

   HOW THE VIEW GETS THERE.  The later games glide rather than jump: polled
   live in The Lost Children, the scroll moved by about a tenth of the
   remaining distance each frame (841 -> 742 -> 653 ... on a 982-unit pan),
   an ease-out that settles in well under a second.  The owner asked for the
   same feel, so a key press only sets a TARGET, and Vv1NumberKeysTick --
   which the Origins companion calls once per frame -- moves the pair a tenth
   of the way each call (never less than one unit) until it lands.  If the
   scroll is found somewhere other than where the last tick left it, the
   player is scrolling by hand and the glide is cancelled rather than fought.

   HOW THE KEYS ARE SEEN.  The game reads input through SDL_PollEvent, and
   its event loop (0x403983) translates only ESC, TAB, ENTER, F-keys and the
   arrows; digits reach it as text and are dropped.  Rather than splice that
   loop, SDL_AddEventWatch registers a callback SDL runs for every event it
   queues, from inside the game's own SDL_PollEvent on the main thread, so
   the write to the village state happens on the thread that owns it.  SDL
   2.0.3, the one the game ships, exports it.

   Both the top-row digits and the keypad digits are accepted (the tips in
   the later games say "keypad").  Key auto-repeat is ignored so holding a
   key does not hammer the state, and a digit typed with Ctrl or Alt held is
   left alone.  A key arriving before any village exists (menu, loading)
   finds a null pointer and does nothing.

   Nothing runs from DllMain: SDL is touched only from the export, which the
   Origins companion calls from the game's per-frame tick, outside the loader
   lock. */
#include <windows.h>

#define VV1_VILLAGE_STATE_PTR (*(unsigned char **)0x0048AEDCu)  /* what 0x41D500 returns */
#define VV1_SCROLL_X_OFFSET 0x8u
#define VV1_SCROLL_Y_OFFSET 0xCu
#define VV1_SCROLL_X_MIN (-205)   /* 0x429C8E */
#define VV1_SCROLL_X_MAX 885      /* 0x429C9F */
#define VV1_SCROLL_Y_MIN (-5)     /* 0x429CB4 */
#define VV1_SCROLL_Y_MAX 1205     /* 0x429CC8 */

#define VV1_SDL_KEYDOWN 0x300u
#define VV1_SDLK_KP_1 0x40000059   /* SDL_SCANCODE_KP_1 | SDLK_SCANCODE_MASK */
#define VV1_SDLK_KP_9 0x40000061
#define VV1_KMOD_CTRL 0x00C0u
#define VV1_KMOD_ALT 0x0300u

/* SDL_KeyboardEvent, SDL 2.0.x: type u32 @0, timestamp u32 @4, windowID u32
   @8, state u8 @12, repeat u8 @13, then SDL_Keysym: scancode i32 @16,
   sym i32 @20, mod u16 @24. */
#define VV1_SDL_KEY_REPEAT_OFFSET 13
#define VV1_SDL_KEY_SYM_OFFSET 20
#define VV1_SDL_KEY_MOD_OFFSET 24

typedef int (__cdecl *vv1_sdl_event_filter_t)(void *userdata, void *event);
typedef void (__cdecl *vv1_sdl_add_event_watch_t)(vv1_sdl_event_filter_t filter, void *userdata);

static int vv1_numkeys_installed;

/* The glide in progress: where it is heading, and where the last tick left
   the scroll (so a hand scroll in between is recognised and wins). */
static int vv1_pan_active;
static int vv1_pan_target_x, vv1_pan_target_y;
static int vv1_pan_last_x, vv1_pan_last_y;
#define VV1_PAN_DIVISOR 10   /* a tenth of the remaining distance per frame */

/* Start gliding the view to section `digit` (1..9, keypad layout).  Returns
   1 when a glide was started, 0 when there was no village to move. */
static int vv1_numkeys_jump(int digit) {
    static const int xs[3] = { VV1_SCROLL_X_MIN, (VV1_SCROLL_X_MIN + VV1_SCROLL_X_MAX) / 2, VV1_SCROLL_X_MAX };
    static const int ys[3] = { VV1_SCROLL_Y_MAX, (VV1_SCROLL_Y_MIN + VV1_SCROLL_Y_MAX) / 2, VV1_SCROLL_Y_MIN };
    unsigned char *state = VV1_VILLAGE_STATE_PTR;
    int col;
    int row;
    if (state == NULL || digit < 1 || digit > 9) {
        return 0;
    }
    col = (digit - 1) % 3;   /* 1,4,7 left; 2,5,8 middle; 3,6,9 right */
    row = (digit - 1) / 3;   /* 1-3 bottom; 4-6 middle; 7-9 top */
    vv1_pan_target_x = xs[col];
    vv1_pan_target_y = ys[row];
    vv1_pan_last_x = *(int *)(state + VV1_SCROLL_X_OFFSET);
    vv1_pan_last_y = *(int *)(state + VV1_SCROLL_Y_OFFSET);
    vv1_pan_active = 1;
    return 1;
}

/* One glide step toward `target` from `cur`: a tenth of the way, at least
   one unit, and never past the target. */
static int vv1_pan_step(int cur, int target) {
    int delta = target - cur;
    int step;
    if (delta == 0) {
        return cur;
    }
    step = delta / VV1_PAN_DIVISOR;
    if (step == 0) {
        step = delta > 0 ? 1 : -1;
    }
    return cur + step;
}

/* Advance the glide by one frame.  Returns 1 while a glide is in progress
   (after this step), 0 when idle or just finished. */
static int vv1_pan_tick(void) {
    unsigned char *state = VV1_VILLAGE_STATE_PTR;
    int *x;
    int *y;
    if (!vv1_pan_active) {
        return 0;
    }
    if (state == NULL) {
        vv1_pan_active = 0;     /* the village went away: nothing to move */
        return 0;
    }
    x = (int *)(state + VV1_SCROLL_X_OFFSET);
    y = (int *)(state + VV1_SCROLL_Y_OFFSET);
    if (*x != vv1_pan_last_x || *y != vv1_pan_last_y) {
        vv1_pan_active = 0;     /* the player scrolled by hand: they win */
        return 0;
    }
    *x = vv1_pan_step(*x, vv1_pan_target_x);
    *y = vv1_pan_step(*y, vv1_pan_target_y);
    vv1_pan_last_x = *x;
    vv1_pan_last_y = *y;
    if (*x == vv1_pan_target_x && *y == vv1_pan_target_y) {
        vv1_pan_active = 0;
        return 0;
    }
    return 1;
}

/* Which section a key event asks for: 1..9, or 0 for "not a section key". */
static int vv1_numkeys_digit(const unsigned char *e) {
    int sym;
    if (e == NULL || *(const unsigned int *)e != VV1_SDL_KEYDOWN) {
        return 0;
    }
    if (e[VV1_SDL_KEY_REPEAT_OFFSET] != 0) {
        return 0;               /* auto-repeat: the first press already jumped */
    }
    if ((*(const unsigned short *)(e + VV1_SDL_KEY_MOD_OFFSET) & (VV1_KMOD_CTRL | VV1_KMOD_ALT)) != 0) {
        return 0;               /* a chord, not a section key */
    }
    sym = *(const int *)(e + VV1_SDL_KEY_SYM_OFFSET);
    if (sym >= '1' && sym <= '9') {
        return sym - '0';
    }
    if (sym >= VV1_SDLK_KP_1 && sym <= VV1_SDLK_KP_9) {
        return sym - VV1_SDLK_KP_1 + 1;
    }
    return 0;
}

static int __cdecl vv1_numkeys_watch(void *userdata, void *event) {
    int digit = vv1_numkeys_digit((const unsigned char *)event);
    (void)userdata;
    if (digit != 0) {
        vv1_numkeys_jump(digit);
    }
    return 1;                   /* watch results are ignored by SDL anyway */
}

/* Register the SDL event watch.  Idempotent: safe to call every frame, does
   the work once.  Returns 1 once the watch is in place, 0 while SDL2 is not
   loaded yet (call again later) or -1 if this SDL has no event watch (give
   up; the game simply has no number keys).  Fail-open throughout. */
__declspec(dllexport) int __stdcall Vv1NumberKeysInstall(void) {
    HMODULE sdl;
    vv1_sdl_add_event_watch_t add_watch;
    if (vv1_numkeys_installed) {
        return vv1_numkeys_installed;
    }
    sdl = GetModuleHandleA("SDL2.dll");
    if (sdl == NULL) {
        return 0;
    }
    add_watch = (vv1_sdl_add_event_watch_t)GetProcAddress(sdl, "SDL_AddEventWatch");
    if (add_watch == NULL) {
        vv1_numkeys_installed = -1;
        return -1;
    }
    add_watch(vv1_numkeys_watch, NULL);
    vv1_numkeys_installed = 1;
    return 1;
}

/* Per frame, from the Origins companion: make sure the watch is installed,
   then advance any glide.  Returns the install state (1 installed, 0 not
   yet, -1 never) so a caller can log it; the glide result is not reported
   because nothing needs it. */
__declspec(dllexport) int __stdcall Vv1NumberKeysTick(void) {
    int installed = Vv1NumberKeysInstall();
    vv1_pan_tick();
    return installed;
}

/* Test seam: feed one SDL event exactly as the watch would see it and report
   which section it selects (0 = none).  Touches no game state. */
__declspec(dllexport) int __stdcall Vv1NumberKeysProbe(const void *event) {
    return vv1_numkeys_digit((const unsigned char *)event);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
