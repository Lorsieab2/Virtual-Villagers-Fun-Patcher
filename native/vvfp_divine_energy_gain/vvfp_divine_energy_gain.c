/* VVFP Divine Energy Gain -- "Divine Energy Gain Rate" (New Believers; the owner, 2026-11-25: "frequency of divine
   energy gain in vv5").

   WHAT.  The Divine Energy the believers earn comes N times as fast (on average: the rest of a whole point is a
   chance), N the patcher window's slider (0.1 to 10, 1 unless moved), read at start from "VVFP Divine Energy
   Gain.txt" in the patcher's folder.  The cap is the game's own, and so is every other Divine Energy change.

   HOW (native/shared/gain_sites.h).  Every Divine Energy change goes through the game's adder 0x424F80
   (`__thiscall`, the amount at [esp + 4], `ret 4`; it keeps the energy within 0 and the cap).  The calls that pay
   the believers' earnings go through the companion:

     0x472D25  each believer, every age unit: +1
     0x472D43  ... at Devotion 50 or more: +3 more
     0x472D61  ... at Devotion 88 or more: +5 more
     0x472DDB  ... +1 more on Hard, or on Medium with 8,000 food or more
     0x46D893  Honoring (a job step): +3
     0x46D8B3  ... at Devotion 50 or more: +4 more
     0x46D8D7  ... at Devotion 88 or more: +5 more
     0x46DA1F  work event 40: +1 (asked for only by "Fix Vanilla Bugs"' Tribute Statue polishing)

   Left as they are (never reach this code): the tutorial's top-up to 10 (0x44E65C), a new village's 50 (0x425DB4),
   the cap's clamp (0x4250F4), a relic found again (10, 50 or 150: 0x41474D, 0x41476E, 0x41478F), the island
   events' +10 (0x4157C8) and -20 (0x415DAB), and "Practicing Devotion Builds Faith and Divine Energy"' +1 (its own
   call).  The God Powers' costs are the game's own.

   SAFETY.  At 1x, or with no setting file, nothing is installed.  Every site is checked to hold exactly its stock
   call first (all of them, or none).  Nothing is written to a save, a villager record or a file; no text is shown.
   No debug output. */
#include <windows.h>
#include "../shared/gain_sites.h"

#define DE_CHOICE_FILE "VVFP Divine Energy Gain.txt"

static const gs_game DE_GAMES[] = {
    { 5, 0x424F80u, 8, { { 0x472D25u, 0 }, { 0x472D43u, 0 }, { 0x472D61u, 0 }, { 0x472DDBu, 0 }, { 0x46D893u, 0 },
                         { 0x46D8B3u, 0 }, { 0x46D8D7u, 0 }, { 0x46DA1Fu, 0 } } },
};

/* 1 when installed (for the tests' emulation), else 0. */
int __stdcall VvfpDivineEnergyGainInstalled(void) {
    return g_gs_installed;
}

/* N in tenths, as read at start (for the tests' emulation). */
int __stdcall VvfpDivineEnergyGainTenths(void) {
    return (int)g_ss_tenths;
}

/* Called once by VVFP More Companions.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    gs_start(DE_GAMES, (int)(sizeof DE_GAMES / sizeof DE_GAMES[0]), game, DE_CHOICE_FILE);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
