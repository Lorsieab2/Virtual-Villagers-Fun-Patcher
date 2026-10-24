/* VVFP VV1 Number Keys -- zip around the island with the numeric keys,
   exactly the way The Lost Children does it.

   The later games let the number keys glide the view to one of nine sections
   of the map, laid out like a numeric keypad:

       7 8 9        top row
       4 5 6        middle
       1 2 3        bottom row

   A New Home never had it.  This companion gives it the Lost Children's own
   code, rebuilt around A New Home's village screen, which is the same class
   one game earlier (same handlers in the same vtable slots, the same edge
   scroll, the same map drag, the same clamp) minus the two fields The Lost
   Children added for the glide.

   HOW THE LOST CHILDREN DOES IT (stock 0x429E70 / 0x42F814 / 0x4308F2).
     * The village screen's text-character handler (vtable slot 2, 0x429E70)
       turns '1'..'9' into a target point in two screen fields, +0x230/+0x234,
       and returns 0.  (0, 0) means "no glide".  Another key overwrites the
       target: a retarget, from wherever the view is.
     * The village update (vtable slot 8, 0x42E990) runs the glide at
       0x42F814, between the follow-the-selected-villager edge velocities and
       the edge scroll, with nothing before it that can skip it: while a
       target is set it zeroes the edge velocities, moves each axis by
       (target - scroll) / 10 truncated toward zero, refreshes a carried
       villager (0x449220), clamps -- and an axis that hits the clamp has its
       target zeroed -- and once both remaining distances divided by ten are
       zero it clears the target.  No minimum step, no final snap.
     * Dragging the map (0x431758) moves the scroll by the pointer's motion
       and leaves the target alone, so the glide keeps pulling while the
       button is held; releasing the button (0x4308F2, the mouse-up branch)
       clears the target along with the edge velocities.  That is how a drag
       wins.  The Secret City, Tree of Life and New Believers clear it on the
       first drag motion as well (their camera's pan, 0x423950 / 0x4708B0 /
       0x47B830, starts with the clear); The Lost Children, A New Home's
       sibling, is the one followed here.
     * The screen buttons that leave the village view (3, 5, 6 and 7:
       0x42A78F, 0x42AA35, 0x42AABA, 0x42AB9C) clear the target with the
       edge velocities, and the constructor (0x42D361) starts it at zero.

   THE SAME IN A NEW HOME.  The glide target lives here instead of in the
   screen (A New Home's screen has no spare fields), and six of A New Home's
   own instructions are detoured, at run time, after their bytes are checked
   against the stock game, to the code below:

       0x41FE04  the text-character handler 0x41FDF0, right after its
                 "is this a character" test: '1'..'9' set the target and
                 return 0 (0x41FFB1, the handler's own "not mine" exit);
                 every other character goes on to the stock jump table.
       0x424F12  the mouse-up branch of 0x424EF0: clears the target.
       0x4208CC, 0x420932, 0x420998
                 the edge-velocity clears of screen buttons 5, 6 and 3/7 in
                 0x420610 (button 4 clears nothing, as in The Lost
                 Children): clear the target too.
       0x422555  the screen constructor's edge-velocity clear: also clears it.

   The glide itself runs from the Origins companion's existing native hook
   in the village update (0x423F89, the exact spot The Lost Children's glide
   occupies), which calls Vv1NumberKeysUpdate with the screen.  It returns 1
   while a target is set, and the hook then goes on to A New Home's own
   carry refresh (0x439410) and clamp, as The Lost Children's glide does.

   The keys therefore arrive the way they do in every later game: as text
   characters through the game's own event loop (0x403BB4 turns a one-
   character SDL_TEXTINPUT into a type-5 event for the screen).  Holding a
   key repeats it, as there; the keypad counts when it types digits
   (NumLock on), as there; a digit typed on another screen goes to that
   screen, as there.

   Nothing runs from DllMain: VVFP Startup.dll calls VvfpStartup at game
   start, and the per-frame exports install too (idempotent), all outside
   the loader lock.  If any site does not hold the stock bytes, nothing is
   installed and the game simply has no number keys. */
#include <windows.h>
#include <string.h>
#include <stdint.h>

#define VV1_GAME 1
#define VV1_VILLAGE_STATE_PTR (*(unsigned char **)0x0048AEDCu)  /* what 0x41D500 returns */
#define VV1_SCROLL_X_OFFSET 0x8u
#define VV1_SCROLL_Y_OFFSET 0xCu
#define VV1_EDGE_X_OFFSET 0x2D8u          /* edge velocities (VV2 +0x228/+0x22C) */
#define VV1_EDGE_Y_OFFSET 0x2DCu
#define VV1_MARGIN_LEFT_OFFSET 0x298u     /* the clamp's four screen margins */
#define VV1_MARGIN_TOP_OFFSET 0x29Cu      /* (VV2 +0x1E8/+0x1EC/+0x1F0/+0x1F4) */
#define VV1_MARGIN_RIGHT_OFFSET 0x2A0u
#define VV1_MARGIN_BOTTOM_OFFSET 0x2A4u
#define VV1_MAP_SPAN 0x690                /* 1680: both games' clamp constant */
#define VV1_PAN_DIVISOR 10                /* a tenth of the remaining distance per update */

/* The glide target: The Lost Children's +0x230/+0x234.  (0, 0) = no glide. */
static int vv1_target_x, vv1_target_y;

/* The Lost Children's nine targets (0x429E9E..0x429F78), keypad layout. */
static const int vv1_target_xs[9] = {
    -150, 300, 850,
    -150, 300, 850,
    -150, 300, 850
};
static const int vv1_target_ys[9] = {
    1200, 1200, 1200,
    500, 570, 500,
    0, 0, 0
};

/* ---- the glide, The Lost Children's 0x42F814..0x42F943 ------------------- */

static int vv1_glide_step(int cur, int target) {
    return cur + (target - cur) / VV1_PAN_DIVISOR;   /* C truncation = the game's idiv-by-multiply */
}

/* One village update.  Returns 1 while a target is set (the hook then runs
   the stock carry refresh and clamp, 0x423FAE), else 0 (the stock edge
   scroll).  The clamp is the stock one at 0x423FD6 -- identical to The Lost
   Children's 0x42F89F -- so this only predicts it, to zero an axis's target
   the way 0x42F8C5 / 0x42F8F6 do and to test arrival on the clamped view
   (0x42F8FF); the hook's own clamp then writes the clamped values. */
static int vv1_glide_update(unsigned char *screen) {
    unsigned char *state;
    int x, y, lo, hi;
    if (vv1_target_x == 0 && vv1_target_y == 0) {
        return 0;
    }
    if (screen == NULL) {
        return 0;
    }
    state = *(unsigned char **)(screen + 0x10);
    if (state == NULL || state != VV1_VILLAGE_STATE_PTR) {
        return 0;             /* not the live village: leave everything native */
    }
    *(int *)(screen + VV1_EDGE_X_OFFSET) = 0;
    *(int *)(screen + VV1_EDGE_Y_OFFSET) = 0;
    x = vv1_glide_step(*(int *)(state + VV1_SCROLL_X_OFFSET), vv1_target_x);
    y = vv1_glide_step(*(int *)(state + VV1_SCROLL_Y_OFFSET), vv1_target_y);
    *(int *)(state + VV1_SCROLL_X_OFFSET) = x;
    *(int *)(state + VV1_SCROLL_Y_OFFSET) = y;

    lo = -*(int *)(screen + VV1_MARGIN_LEFT_OFFSET);
    hi = VV1_MAP_SPAN - *(int *)(screen + VV1_MARGIN_RIGHT_OFFSET);
    if (x < lo) {
        x = lo;
        vv1_target_x = 0;
    } else if (x > hi) {
        x = hi;
        vv1_target_x = 0;
    }
    lo = -*(int *)(screen + VV1_MARGIN_TOP_OFFSET);
    hi = *(int *)(screen + VV1_MARGIN_TOP_OFFSET) - *(int *)(screen + VV1_MARGIN_BOTTOM_OFFSET) + VV1_MAP_SPAN;
    if (y < lo) {
        y = lo;
        vv1_target_y = 0;
    } else if (y > hi) {
        y = hi;
        vv1_target_y = 0;
    }
    if ((vv1_target_x - x) / VV1_PAN_DIVISOR == 0 && (vv1_target_y - y) / VV1_PAN_DIVISOR == 0) {
        vv1_target_x = 0;
        vv1_target_y = 0;
    }
    return 1;
}

/* ---- the six detours ------------------------------------------------------ */

#define KEY_SITE_VA     0x41FE04u   /* mov eax,[esp+0x24]; add eax,-0x20 */
#define KEY_NOT_MINE_VA 0x41FFB1u   /* pop edi; xor al,al; pop esi; add esp,0x10; ret 0xC */
#define KEY_RESUME_VA   0x41FE0Bu   /* cmp eax, 0x54 */
#define UP_SITE_VA      0x424F12u   /* mov ecx,[esi+0x2F0] */
#define UP_RESUME_VA    0x424F18u
#define BUTTON5_SITE_VA 0x4208CCu   /* mov [esi+0x2D8],ebx; mov [esi+0x2DC],ebx */
#define BUTTON5_RESUME_VA 0x4208D8u
#define BUTTON6_SITE_VA 0x420932u   /* mov [esi+0x2D8],ebx; mov [esi+0x2DC],ebx */
#define BUTTON6_RESUME_VA 0x42093Eu
#define BUTTON37_SITE_VA 0x420998u  /* mov [esi+0x2DC],ebx; mov [esi+0x2D8],ebx */
#define BUTTON37_RESUME_VA 0x4209A4u
#define CTOR_SITE_VA    0x422555u   /* mov [esi+0x2D8],ebx; mov [esi+0x2DC],ebx */
#define CTOR_RESUME_VA  0x422561u

static const unsigned int key_not_mine_va = KEY_NOT_MINE_VA, key_resume_va = KEY_RESUME_VA,
    up_resume_va = UP_RESUME_VA, button5_resume_va = BUTTON5_RESUME_VA,
    button6_resume_va = BUTTON6_RESUME_VA, button37_resume_va = BUTTON37_RESUME_VA,
    ctor_resume_va = CTOR_RESUME_VA;

/* 0x429E70's cases '1'..'9', then "return 0".  ESI = the screen, the
   character is the handler's third argument. */
static __declspec(naked) void key_stub(void) {
    __asm {
        mov eax, dword ptr [esp + 0x24]
        cmp eax, 0x31
        jl not_digit
        cmp eax, 0x39
        jg not_digit
        sub eax, 0x31
        mov ecx, dword ptr vv1_target_xs[eax * 4]
        mov dword ptr [vv1_target_x], ecx
        mov ecx, dword ptr vv1_target_ys[eax * 4]
        mov dword ptr [vv1_target_y], ecx
        jmp dword ptr [key_not_mine_va]
    not_digit:
        add eax, -0x20
        jmp dword ptr [key_resume_va]
    }
}

/* 0x4308F2: the mouse-up branch starts by clearing the glide. */
static __declspec(naked) void up_stub(void) {
    __asm {
        mov dword ptr [vv1_target_x], 0
        mov dword ptr [vv1_target_y], 0
        mov ecx, dword ptr [esi + 0x2F0]
        jmp dword ptr [up_resume_va]
    }
}

/* The edge-velocity clears that The Lost Children pairs with a glide clear
   (EBX = 0 at every one of them). */
static __declspec(naked) void button5_stub(void) {
    __asm {
        mov dword ptr [esi + 0x2D8], ebx
        mov dword ptr [esi + 0x2DC], ebx
        mov dword ptr [vv1_target_x], 0
        mov dword ptr [vv1_target_y], 0
        jmp dword ptr [button5_resume_va]
    }
}

static __declspec(naked) void button6_stub(void) {
    __asm {
        mov dword ptr [esi + 0x2D8], ebx
        mov dword ptr [esi + 0x2DC], ebx
        mov dword ptr [vv1_target_x], 0
        mov dword ptr [vv1_target_y], 0
        jmp dword ptr [button6_resume_va]
    }
}

static __declspec(naked) void button37_stub(void) {
    __asm {
        mov dword ptr [esi + 0x2DC], ebx
        mov dword ptr [esi + 0x2D8], ebx
        mov dword ptr [vv1_target_x], 0
        mov dword ptr [vv1_target_y], 0
        jmp dword ptr [button37_resume_va]
    }
}

static __declspec(naked) void ctor_stub(void) {
    __asm {
        mov dword ptr [esi + 0x2D8], ebx
        mov dword ptr [esi + 0x2DC], ebx
        mov dword ptr [vv1_target_x], 0
        mov dword ptr [vv1_target_y], 0
        jmp dword ptr [ctor_resume_va]
    }
}

struct vv1_site {
    unsigned int va;
    unsigned int length;
    unsigned char stock[12];
    void (*stub)(void);
};

/* Each site's stock bytes, A New Home 1.0 (research/stock-executables). */
static const struct vv1_site vv1_sites[6] = {
    { KEY_SITE_VA, 7, { 0x8B, 0x44, 0x24, 0x24, 0x83, 0xC0, 0xE0 }, key_stub },
    { UP_SITE_VA, 6, { 0x8B, 0x8E, 0xF0, 0x02, 0x00, 0x00 }, up_stub },
    { BUTTON5_SITE_VA, 12, { 0x89, 0x9E, 0xD8, 0x02, 0x00, 0x00, 0x89, 0x9E, 0xDC, 0x02, 0x00, 0x00 }, button5_stub },
    { BUTTON6_SITE_VA, 12, { 0x89, 0x9E, 0xD8, 0x02, 0x00, 0x00, 0x89, 0x9E, 0xDC, 0x02, 0x00, 0x00 }, button6_stub },
    { BUTTON37_SITE_VA, 12, { 0x89, 0x9E, 0xDC, 0x02, 0x00, 0x00, 0x89, 0x9E, 0xD8, 0x02, 0x00, 0x00 }, button37_stub },
    { CTOR_SITE_VA, 12, { 0x89, 0x9E, 0xD8, 0x02, 0x00, 0x00, 0x89, 0x9E, 0xDC, 0x02, 0x00, 0x00 }, ctor_stub },
};

/* jmp stub, then nops to the end of the displaced instructions. */
static void vv1_site_bytes(const struct vv1_site *site, unsigned char *out) {
    unsigned int rel = (unsigned int)((const unsigned char *)site->stub
                                      - ((const unsigned char *)(uintptr_t)site->va + 5));
    unsigned int i;
    out[0] = 0xE9;
    memcpy(out + 1, &rel, 4);
    for (i = 5; i < site->length; ++i) {
        out[i] = 0x90;
    }
}

static int vv1_site_is_stock(const struct vv1_site *site) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(uintptr_t)site->va;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(at, site->stock, site->length) == 0;
}

static int vv1_numkeys_installed;   /* 0 = not tried, 1 = installed, -1 = not this game */

/* Install every detour or none.  Idempotent; returns 1 once installed. */
__declspec(dllexport) int __stdcall Vv1NumberKeysInstall(void) {
    unsigned char bytes[12];
    unsigned int i;
    DWORD old;
    if (vv1_numkeys_installed != 0) {
        return vv1_numkeys_installed;
    }
    for (i = 0; i < 6; ++i) {
        if (!vv1_site_is_stock(&vv1_sites[i])) {
            vv1_numkeys_installed = -1;   /* another build, or another patch got there */
            return -1;
        }
    }
    for (i = 0; i < 6; ++i) {
        unsigned char *at = (unsigned char *)(uintptr_t)vv1_sites[i].va;
        vv1_site_bytes(&vv1_sites[i], bytes);
        if (!VirtualProtect(at, vv1_sites[i].length, PAGE_EXECUTE_READWRITE, &old)) {
            continue;
        }
        memcpy(at, bytes, vv1_sites[i].length);
        VirtualProtect(at, vv1_sites[i].length, old, &old);
        FlushInstructionCache(GetCurrentProcess(), at, vv1_sites[i].length);
    }
    vv1_target_x = 0;
    vv1_target_y = 0;
    vv1_numkeys_installed = 1;
    return 1;
}

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (game == VV1_GAME) {
        Vv1NumberKeysInstall();
    }
}

/* The Origins companion's render tick: installation only (a no-op once
   VvfpStartup has run). */
__declspec(dllexport) int __stdcall Vv1NumberKeysTick(void) {
    return Vv1NumberKeysInstall();
}

/* Called by the native village-update hook (0x423F89) with the screen. */
__declspec(dllexport) int __stdcall Vv1NumberKeysUpdate(void *screen) {
    if (Vv1NumberKeysInstall() != 1) {
        return 0;
    }
    return vv1_glide_update((unsigned char *)screen);
}

#ifdef VVFP_TEST
/* Test seam, TEST build only (VVFP_TEST, tests/test_dlls/): read the glide
   target, and the site table (va, length, stock bytes, what it becomes). */
__declspec(dllexport) void __stdcall Vv1NumberKeysProbeTarget(int *x, int *y) {
    *x = vv1_target_x;
    *y = vv1_target_y;
}

__declspec(dllexport) int __stdcall Vv1NumberKeysProbeSite(int index, unsigned int *va, unsigned char *stock,
                                                           unsigned char *patched) {
    if (index < 0 || index >= 6) {
        return 0;
    }
    *va = vv1_sites[index].va;
    memcpy(stock, vv1_sites[index].stock, vv1_sites[index].length);
    vv1_site_bytes(&vv1_sites[index], patched);
    return (int)vv1_sites[index].length;
}
#endif /* VVFP_TEST */

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
