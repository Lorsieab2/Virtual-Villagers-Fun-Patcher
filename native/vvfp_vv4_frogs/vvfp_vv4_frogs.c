/* VVFP VV4 Frogs -- part of "Fix Vanilla Bugs" in The Tree of Life (the owner, 2026-11-17: "the frogs patch
   should spawn frogs all along the blue of the river here").

   THE BASE GAME.  After The Frog Rescue (puzzle 5), while the stream flows, every world refresh (0x46D090, its
   frog block 0x46D3BF..0x46D4C5) places 1 to 3 frog leaps on the river round the island: a frog that leaps right
   (effect 0x1B, frogstrip1.png) at x 1029..1182, y 605..636, then two 50-in-100 chances of a frog that leaps left
   (effect 0x1C, frogstrip2.png) at x 950..1133, y 600..629 -- two small fixed boxes on the right of the bottom
   stretch, so the frogs never leap on the rest of the river.  Each leap is a 60 x 35 frame drawn from its top
   left corner (the effect draw 0x41D2B0).

   THE FIX.  The same leaps, the same chances and the same calls to the game's effect maker (0x41CEC0, the same
   arguments), each placed at a corner picked with the game's own rand (0x4036D0) from every corner at which the
   whole leap -- all 12 frames, the frog and its ripple -- lies on the river's blue water as the game draws it for
   the stream's flow (frog_water.h, traced from the game's river and tree pictures by
   scripts/build_vv4_frog_water.py): along the curve on the left, the whole bottom stretch and the pool under the
   waterfall by the ladder, never on rock, grass, the island, the tree, the waterfall or the ladder.  When the
   stream runs low (flow 1, the narrow river) no whole leap fits on its water, and the frogs still leap whenever
   the base game makes them leap (the owner, 2026-11-18): at the corners along the low river where a leap overlaps
   its water the most, partly over the bed's rocky edge as in the base game, never on the tree, the island's grass
   or the ladder.  A flow with no corner at all for a frog uses the base game's own box for that leap.

   SAFETY.  The whole frog block and the gate before it are checked to hold the stock bytes first; then one jump
   at 0x46D3F7 (the block's `push esi`) is written, or nothing (native/shared/install_sites.h).  The block's own
   exit (0x46D4C2: add esp, 8; ret) is where the companion returns.  Nothing is saved.  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "frog_water.h"

#define VV4_GAME 4
#define VV4_GAME_BASE 0x400000u
#define VV4_FROG_SITE 0x46D3F7u
#define VV4_FROG_EXIT 0x46D4C2u
#define VV4_GATE 0x46D3BFu
#define VV4_RAND 0x4036D0u
#define VV4_EFFECT_MAKER 0x41CEC0u
#define VV4_EFFECTS 0x4CE1C0u
#define FROG_RIGHT 0x1B
#define FROG_LEFT 0x1C

/* 0x46D3BF..0x46D4C5: the gate (puzzle 5 solved, not paused?, the stream's flow above 0) and the frog block, as the
   base game has them. */
static const unsigned char FROG_BLOCK[0x46D4C6 - VV4_GATE] = {
    0x6A, 0x05, 0xB9, 0xF8, 0x8B, 0x4D, 0x00, 0xE8, 0x95, 0xB5, 0xFC, 0xFF, 0x84, 0xC0, 0x0F, 0x84,
    0xEF, 0x00, 0x00, 0x00, 0xB9, 0x18, 0x6F, 0x4D, 0x00, 0xE8, 0xE3, 0x07, 0xFB, 0xFF, 0x84, 0xC0,
    0x0F, 0x85, 0xDD, 0x00, 0x00, 0x00, 0xB9, 0xF0, 0x8C, 0x4D, 0x00, 0xE8, 0xF1, 0xC2, 0xFC, 0xFF,
    0x85, 0xC0, 0x0F, 0x8E, 0xCB, 0x00, 0x00, 0x00, 0x56, 0x68, 0x9A, 0x00, 0x00, 0x00, 0xE8, 0xCE,
    0x62, 0xF9, 0xFF, 0x8B, 0xF0, 0x6A, 0x20, 0x81, 0xC6, 0x05, 0x04, 0x00, 0x00, 0xE8, 0xBF, 0x62,
    0xF9, 0xFF, 0x83, 0xC4, 0x08, 0x6A, 0x00, 0x6A, 0x05, 0x6A, 0xFF, 0x6A, 0x00, 0x6A, 0x00, 0x05,
    0x5D, 0x02, 0x00, 0x00, 0x50, 0x56, 0x6A, 0x1B, 0xB9, 0xC0, 0xE1, 0x4C, 0x00, 0xE8, 0x8F, 0xFA,
    0xFA, 0xFF, 0x6A, 0x64, 0xE8, 0x98, 0x62, 0xF9, 0xFF, 0x83, 0xC4, 0x04, 0x83, 0xF8, 0x32, 0x7D,
    0x39, 0x68, 0xB8, 0x00, 0x00, 0x00, 0xE8, 0x86, 0x62, 0xF9, 0xFF, 0x8B, 0xF0, 0x6A, 0x1E, 0x81,
    0xC6, 0xB6, 0x03, 0x00, 0x00, 0xE8, 0x77, 0x62, 0xF9, 0xFF, 0x83, 0xC4, 0x08, 0x6A, 0x00, 0x6A,
    0x05, 0x6A, 0xFF, 0x6A, 0x00, 0x6A, 0x00, 0x05, 0x58, 0x02, 0x00, 0x00, 0x50, 0x56, 0x6A, 0x1C,
    0xB9, 0xC0, 0xE1, 0x4C, 0x00, 0xE8, 0x47, 0xFA, 0xFA, 0xFF, 0x6A, 0x64, 0xE8, 0x50, 0x62, 0xF9,
    0xFF, 0x83, 0xC4, 0x04, 0x83, 0xF8, 0x32, 0x7D, 0x39, 0x68, 0xB8, 0x00, 0x00, 0x00, 0xE8, 0x3E,
    0x62, 0xF9, 0xFF, 0x8B, 0xF0, 0x6A, 0x1E, 0x81, 0xC6, 0xB6, 0x03, 0x00, 0x00, 0xE8, 0x2F, 0x62,
    0xF9, 0xFF, 0x83, 0xC4, 0x08, 0x6A, 0x00, 0x6A, 0x05, 0x6A, 0xFF, 0x6A, 0x00, 0x6A, 0x00, 0x05,
    0x58, 0x02, 0x00, 0x00, 0x50, 0x56, 0x6A, 0x1C, 0xB9, 0xC0, 0xE1, 0x4C, 0x00, 0xE8, 0xFF, 0xF9,
    0xFA, 0xFF, 0x5E, 0x83, 0xC4, 0x08, 0xC3,
};

typedef int (__cdecl *game_rand_fn)(int range);
/* The effect maker is a thiscall with eight stack arguments (ret 0x20): called as a fastcall whose second register
   argument is unused. */
typedef int (__fastcall *effect_maker_fn)(void *effects, void *unused, int type, int x, int y, int a4, int a5,
                                          int a6, int a7, int a8);

static unsigned int g_exit = VV4_FROG_EXIT;
static int g_installed;

static const frog_set *frog_set_for(int flow, int frog) {
    int i;
    for (i = 0; i < (int)(sizeof FROG_SETS / sizeof FROG_SETS[0]); ++i) {
        if (FROG_SETS[i].flow == flow && FROG_SETS[i].frog == frog) {
            return &FROG_SETS[i];
        }
    }
    return NULL;
}

/* The effect maker with the base game's own arguments: no follow, -1, 5, not centred. */
static void frog_make(int frog, int x, int y) {
    ((effect_maker_fn)(UINT_PTR)VV4_EFFECT_MAKER)((void *)(UINT_PTR)VV4_EFFECTS, NULL, frog, x, y, 0, 0, -1, 5, 0);
}

/* One leap of `frog` at a corner picked with the game's rand from this flow's set; with no set, in the base game's
   own box, with its two rolls in its order (x, then y). */
static void frog_leap(int flow, int frog) {
    const frog_set *set = frog_set_for(flow, frog);
    game_rand_fn game_rand = (game_rand_fn)(UINT_PTR)VV4_RAND;
    int pick, i;
    if (set == NULL || set->total <= 0) {
        int x, y;
        if (frog == FROG_RIGHT) {
            x = game_rand(0x9A) + 0x405;
            y = game_rand(0x20) + 0x25D;
        } else {
            x = game_rand(0xB8) + 0x3B6;
            y = game_rand(0x1E) + 0x258;
        }
        frog_make(frog, x, y);
        return;
    }
    pick = game_rand(set->total);
    for (i = set->first; i < set->first + set->count; ++i) {
        const frog_run *run = &FROG_RUNS[i];
        int length = run->x1 - run->x0 + 1;
        if (pick < length) {
            frog_make(frog, run->x0 + pick, run->y);
            return;
        }
        pick -= length;
    }
}

/* The frog block's leaps: one leaping right, then two 50-in-100 chances of one leaping left, as the base game. */
static void __cdecl frogs_leap(int flow) {
    game_rand_fn game_rand = (game_rand_fn)(UINT_PTR)VV4_RAND;
    frog_leap(flow, FROG_RIGHT);
    if (game_rand(100) < 50) {
        frog_leap(flow, FROG_LEFT);
    }
    if (game_rand(100) < 50) {
        frog_leap(flow, FROG_LEFT);
    }
}

/* At 0x46D3F7, eax = the stream's flow the gate just read (0x4396E0: 1 or 2).  Every register is kept; the block's
   exit (add esp, 8; ret) follows. */
__declspec(naked) static void frogs_stub(void) {
    __asm {
        pushad
        push eax
        call frogs_leap
        add esp, 4
        popad
        jmp dword ptr [g_exit]
    }
}

/* 1 when the jump went in, 0 when it did not. */
__declspec(dllexport) int __stdcall VvfpVv4FrogsInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w[1];
    const unsigned char *module;
    (void)shipped;
    if (g_installed || game != VV4_GAME) {
        return;
    }
    module = (const unsigned char *)GetModuleHandleA(NULL);
    if (module != NULL && (UINT_PTR)module != VV4_GAME_BASE) {
        return;
    }
    if (!vvfp_site_holds(VV4_GATE, FROG_BLOCK, (int)sizeof FROG_BLOCK)) {
        return;
    }
    vvfp_site_branch(&w[0], VV4_FROG_SITE, 5, FROG_BLOCK + (VV4_FROG_SITE - VV4_GATE), 0xE9,
                     (const void *)frogs_stub);
    if (vvfp_install_sites(w, 1)) {
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
