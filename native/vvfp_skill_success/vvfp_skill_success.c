/* VVFP Skill Success -- "Skill Practice Success Chance" (all five games; the owner, 2026-11-17).

   WHAT.  Each work-task skill roll -- the one "Learning Skills Never Fails" makes always pass -- passes N times as
   often (all of the time once that reaches it), N the patcher window's slider (0.1 to 10, 1 unless moved), read at
   start from "VVFP Skill Success.txt" in the patcher's folder (native/shared/slider_scale.h).  What a passed roll
   gives (the game's own skill gain, caps and everything after it) is unchanged; "Learning Skills Never Fails" is still
   the way to make every roll pass, and with it ticked this slider changes nothing.

   HOW.  Every such roll is `push 100; call rand; ...; cmp eax, skill + bonus; jle passed` -- it passes when rand(100)
   is at most the villager's skill plus the game's own bonus (30 in A New Home; the game's own term in the others).
   The `call rand` of each becomes a call of this companion's stub, which calls the game's own rand(100) exactly once
   and hands back the roll scaled (ss_roll_low): the threshold, so the villager's skill and every bonus, is the
   game's own.  The sites (the same rolls as "Learning Skills Never Fails"):

     A New Home         0x43D470 0x43D5D3 0x43D71D 0x43D7EB 0x43D89F          Farming, Building, Research,
     The Lost Children  0x44E1D0 0x44E36B 0x44E4D2 0x44E5D5 0x44E6DA          Healing, Parenting
     The Secret City    0x45A342 0x45A4F1 0x45A673 0x45A78D 0x45A897
     The Tree of Life   0x462B15 0x462D93 0x462F9E 0x46312A 0x4632A3
     New Believers      0x46B305 0x46B4D1 0x46B6BB 0x46B847 0x46B9C0 0x46BB73 and Devotion (believers only)

   After each compare the roll is not read again (the paths after it write eax first or return a bool in al).  The
   stub keeps ecx and edx as the game's rand left them; the instruction after each call sets the flags anew.

   SAFETY.  At 1x, or with no setting file, nothing is installed.  Every site is checked to hold exactly its stock
   call first (all of them, or none).  Nothing is written to a save, a villager record or a file; no text is shown.
   No debug output. */
#include <windows.h>
#include "../shared/slider_scale.h"

#define SK_CHOICE_FILE "VVFP Skill Success.txt"
#define SK_MAX_SITES 6

typedef struct {
    int game;
    unsigned int rand_fn;
    int count;
    vvfp_call_site sites[SK_MAX_SITES];
} sk_game;

static const sk_game SK_GAMES[] = {
    { 1, 0x402F10u, 5, { { 0x43D470u, 0 }, { 0x43D5D3u, 0 }, { 0x43D71Du, 0 }, { 0x43D7EBu, 0 }, { 0x43D89Fu, 0 } } },
    { 2, 0x4031A0u, 5, { { 0x44E1D0u, 0 }, { 0x44E36Bu, 0 }, { 0x44E4D2u, 0 }, { 0x44E5D5u, 0 }, { 0x44E6DAu, 0 } } },
    { 3, 0x4032D0u, 5, { { 0x45A342u, 0 }, { 0x45A4F1u, 0 }, { 0x45A673u, 0 }, { 0x45A78Du, 0 }, { 0x45A897u, 0 } } },
    { 4, 0x4036D0u, 5, { { 0x462B15u, 0 }, { 0x462D93u, 0 }, { 0x462F9Eu, 0 }, { 0x46312Au, 0 }, { 0x4632A3u, 0 } } },
    { 5, 0x403660u, 6, { { 0x46B305u, 0 }, { 0x46B4D1u, 0 }, { 0x46B6BBu, 0 }, { 0x46B847u, 0 }, { 0x46B9C0u, 0 },
                         { 0x46BB73u, 0 } } },
};

static unsigned int g_rand;
static int g_installed;

/* [esp] the site + 5, [esp + 4] 100 (the game's push): eax the game's rand(100), scaled. */
__declspec(naked) static void roll_stub(void) {
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

/* 1 when every site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpSkillSuccessInstalled(void) {
    return g_installed;
}

/* N in tenths, as read at start (for the tests' emulation). */
int __stdcall VvfpSkillSuccessTenths(void) {
    return (int)g_ss_tenths;
}

/* Called once by VVFP More Companions.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    const sk_game *g = NULL;
    int i;
    (void)shipped;
    if (g_installed) {
        return;
    }
    for (i = 0; i < (int)(sizeof SK_GAMES / sizeof SK_GAMES[0]); ++i) {
        if (SK_GAMES[i].game == game) {
            g = &SK_GAMES[i];
        }
    }
    if (g == NULL || !ss_start(SK_CHOICE_FILE)) {
        return;
    }
    g_rand = g->rand_fn;
    if (vvfp_call_retarget(g->sites, g->count, g->rand_fn, (const void *)roll_stub, NULL)) {
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
