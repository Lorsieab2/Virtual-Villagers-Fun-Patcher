/* VVFP VV1 Number Keys -- zip around the island with the numeric keys.

   The later games let the number keys jump the view to one of nine sections
   of the map, laid out like a numeric keypad:

       7 8 9        top row
       4 5 6        middle
       1 2 3        bottom row

   A New Home never had it. This companion supplies the key watch and glide;
   the Origins companion adds the narrow native-update hook that invokes it.
   The Origins companion loads this DLL once and calls
   Vv1NumberKeysInstall; if this file is not beside the executable, the game
   simply has no number keys, exactly as before.

   HOW THE VIEW IS MOVED.  The village state object (the one 0x41D500
   returns, cached at 0x0048AEDC) keeps the scroll position at +8/+0xC.  The
   native village screen object carries that state pointer at +0x10.  The
   native update hook passes this screen object here once per update, after the
   screen's edge velocities at +0x2D8/+0x2DC have been computed.  The game's
   own map-screen click handler at 0x429BA0 writes them directly and then
   clamps:

       0x429C8E  cmp ecx, -205   ...   0x429C9F  cmp ecx, 885     (x)
       0x429CB4  cmp eax, -5     ...   0x429CC8  cmp eax, 1205    (y)

   Those four numbers are VV1's native clamp extrema.  The nine numeric-glide
   targets below are explicitly ported from the measured VV2 capture and are
   intentionally not described as native VV1 keyboard targets.

   HOW THE VIEW GETS THERE.  The later games glide rather than jump: the
   measured VV2 update moved by truncating one tenth of the remaining distance.
   The port uses C's signed integer division exactly: no minimum-one step and
   no final snap.  It stops after a step when both post-step remaining deltas
   divided by ten are zero.  While active, native edge velocities are cleared
   and the game's own held-record refresh/carry block runs immediately
   afterward.  A key press wins, and another key press retargets.

   HOW THE KEYS ARE SEEN.  The game reads input through SDL_PollEvent, and
   its event loop (0x403983) translates only ESC, TAB, ENTER, F-keys and the
   arrows; digits reach it as text and are dropped.  Rather than splice that
   loop, SDL_AddEventWatch registers a callback SDL runs for every event it
   queues, from inside the game's own SDL_PollEvent on the main thread, so
   the event watch only records a target; the native update performs the write
   on the thread that owns the state.  SDL
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

/* The glide in progress: where it is heading.

   Nothing tracks where the last tick left the scroll.  It used to, so a
   scroll that moved between ticks could cancel the glide as "the player
   is scrolling by hand" -- but dragging a villager auto-scrolls the view
   toward the pointer, which is indistinguishable from a hand scroll in
   the state (measured: picking a villager up moves the scroll pair and
   changes nothing else), so the glide died exactly when the player was
   carrying someone and wanted to travel.  A number key now wins; another
   number key retargets. */
static int vv1_pan_active;
static int vv1_pan_target_x, vv1_pan_target_y;
#define VV1_PAN_DIVISOR 10   /* a tenth of the remaining distance per frame */

/* These are the nine measured VV2 targets ported into VV1's 1680-unit map.
   They are feature targets, not VV1's native keyboard coordinates. */
static const int vv1_pan_target_xs[9] = {
    -150, 300, 850,
    -150, 300, 850,
    -150, 300, 850
};
static const int vv1_pan_target_ys[9] = {
    1200, 1200, 1200,
    500, 570, 500,
    0, 0, 0
};

/* Start gliding the view to section `digit` (1..9, keypad layout).  The
   event watch only records the feature target; the native update validates the
   live screen/state before it writes anything. */
static int vv1_numkeys_jump(int digit) {
    if (VV1_VILLAGE_STATE_PTR == NULL || digit < 1 || digit > 9) {
        return 0;
    }
    vv1_pan_target_x = vv1_pan_target_xs[digit - 1];
    vv1_pan_target_y = vv1_pan_target_ys[digit - 1];
    vv1_pan_active = 1;
    return 1;
}

/* One glide step toward `target` from `cur`: C's signed truncating division.
   Deliberately no minimum-one step and no snap to the target. */
static int vv1_pan_step(int cur, int target) {
    return cur + (target - cur) / VV1_PAN_DIVISOR;
}

/* Consume one native village update.  The return value remains 1 on the
   completion tick, including a zero-axis step, so the caller takes the native
   held-record refresh/carry path exactly once before edge scrolling resumes. */
static int vv1_pan_update(void *screen) {
    unsigned char *screen_bytes = (unsigned char *)screen;
    unsigned char *state;
    int *x;
    int *y;
    if (!vv1_pan_active) {
        return 0;
    }
    if (screen_bytes == NULL) {
        vv1_pan_active = 0;
        return 0;
    }
    state = *(unsigned char **)(screen_bytes + 0x10);
    if (state == NULL || state != VV1_VILLAGE_STATE_PTR) {
        vv1_pan_active = 0;     /* no current village: nothing to move */
        return 0;
    }
    x = (int *)(state + VV1_SCROLL_X_OFFSET);
    y = (int *)(state + VV1_SCROLL_Y_OFFSET);
    *x = vv1_pan_step(*x, vv1_pan_target_x);
    *y = vv1_pan_step(*y, vv1_pan_target_y);
    *(int *)(screen_bytes + 0x2D8) = 0;
    *(int *)(screen_bytes + 0x2DC) = 0;
    if ((vv1_pan_target_x - *x) / VV1_PAN_DIVISOR == 0
        && (vv1_pan_target_y - *y) / VV1_PAN_DIVISOR == 0) {
        vv1_pan_active = 0;
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

/* Render cadence is installation-only.  Camera advancement is driven by the
   native village update export below, never from this render tick. */
__declspec(dllexport) int __stdcall Vv1NumberKeysTick(void) {
    return Vv1NumberKeysInstall();
}

/* Called by the exact VV1 native village update hook.  Installing here is
   safe even when this is the first call, before the first render tick. */
__declspec(dllexport) int __stdcall Vv1NumberKeysUpdate(void *screen) {
    Vv1NumberKeysInstall();
    return vv1_pan_update(screen);
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
