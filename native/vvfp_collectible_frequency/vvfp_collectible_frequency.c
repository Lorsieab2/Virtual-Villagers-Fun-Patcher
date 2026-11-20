/* VVFP Collectible Frequency -- "Collectible and Mushroom Frequency" (all five games; the owner, 2026-11-17).

   WHAT.  Mushrooms and collectibles appear on their own N times as often, N the patcher window's slider (0.1 to 10,
   1 unless moved), read at start from "VVFP Collectible Frequency.txt" in the patcher's folder
   (native/shared/slider_scale.h): each of the game's own appearance rolls passes N times as often (all of the time
   once that reaches it).  What appears, how many may lie out at once, how long they lie, fog, rain and every other
   rule are the game's own.

   HOW.  Each roll is `push M; call rand; ...; cmp eax, T` and the game's test of the result.  The `call rand` of
   each becomes a call of this companion's stub, which calls the game's own rand(M) exactly once (so the game's
   numbers go on as before) and hands back the roll scaled (ss_roll_low / ss_roll_high):

     A New Home         0x423516  rand(120) > 117, every 2-second village step while none is out   (high)
     The Lost Children  0x415FED  rand(100) < Exploration + 4, every 2 seconds                    (low)
     The Secret City    0x42DD72  rand(6000) < 3; 0x42DD8D the second roll above weather 50, < 3   (low)
     The Tree of Life   0x4143AD  rand(6000) < 4 (fog: Wind Flute pieces / 2 x 4); 0x4143C7 < 4   (low)
     New Believers      0x41464B  rand(6000) < 3 (fog 6); 0x414665 the second roll, < 3           (low)

   The thresholds are left alone, so Exploration (The Lost Children), fog's Wind Flutes (The Tree of Life), fog (New
   Believers), heavy weather's second roll and "Collectible Spawn Timing works like VV1-3" (which rewrites The Tree of
   Life's thresholds, other bytes) all still count, multiplied.  After each site's compare the roll is not read again
   (the paths after it write eax first, or return a bool in al, or nothing).  The stub keeps ecx and edx as the
   game's rand left them; the instruction after each call sets the flags anew.

   SAFETY.  At 1x, or with no setting file, nothing is installed.  Every site is checked to hold exactly its stock
   call first (all of them, or none: native/shared/install_sites.h).  Nothing is written to a save, a villager record
   or a file; no text is shown.  No debug output. */
#include <windows.h>
#include "../shared/slider_scale.h"

#define CF_CHOICE_FILE "VVFP Collectible Frequency.txt"
#define CF_MAX_SITES 2

typedef struct {
    int game;
    unsigned int rand_fn;                /* the game's rand(M) (cdecl, M on the stack) */
    int high;                            /* 1: the roll passes when HIGH (A New Home) */
    int count;
    vvfp_call_site sites[CF_MAX_SITES];
} cf_game;

static const cf_game CF_GAMES[] = {
    { 1, 0x402F10u, 1, 1, { { 0x423516u, 0 } } },
    { 2, 0x4031A0u, 0, 1, { { 0x415FEDu, 0 } } },
    { 3, 0x4032D0u, 0, 2, { { 0x42DD72u, 0 }, { 0x42DD8Du, 0 } } },
    { 4, 0x4036D0u, 0, 2, { { 0x4143ADu, 0 }, { 0x4143C7u, 0 } } },
    { 5, 0x403660u, 0, 2, { { 0x41464Bu, 0 }, { 0x414665u, 0 } } },
};

static unsigned int g_rand;
static int g_installed;

/* [esp] the site + 5, [esp + 4] M (the game's push): eax the game's rand(M), scaled. */
__declspec(naked) static void low_stub(void) {
    __asm {
        push dword ptr [esp + 4]
        call dword ptr [g_rand]
        add esp, 4
        push ecx
        push edx
        push eax
        call ss_roll_low
        add esp, 4
        pop edx
        pop ecx
        ret
    }
}

__declspec(naked) static void high_stub(void) {
    __asm {
        push dword ptr [esp + 4]
        call dword ptr [g_rand]
        add esp, 4
        push ecx
        push edx
        push dword ptr [esp + 12]      ; M
        push eax
        call ss_roll_high
        add esp, 8
        pop edx
        pop ecx
        ret
    }
}

/* 1 when every site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpCollectibleFrequencyInstalled(void) {
    return g_installed;
}

/* N in tenths, as read at start (for the tests' emulation). */
int __stdcall VvfpCollectibleFrequencyTenths(void) {
    return (int)g_ss_tenths;
}

/* Called once by VVFP More Companions.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    const cf_game *g = NULL;
    int i;
    (void)shipped;
    if (g_installed) {
        return;
    }
    for (i = 0; i < (int)(sizeof CF_GAMES / sizeof CF_GAMES[0]); ++i) {
        if (CF_GAMES[i].game == game) {
            g = &CF_GAMES[i];
        }
    }
    if (g == NULL || !ss_start(CF_CHOICE_FILE)) {
        return;
    }
    g_rand = g->rand_fn;
    if (vvfp_call_retarget(g->sites, g->count, g->rand_fn, g->high ? (const void *)high_stub : (const void *)low_stub,
                           NULL)) {
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
