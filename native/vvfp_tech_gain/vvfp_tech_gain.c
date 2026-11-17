/* VVFP Tech Gain -- "Tech Point Gain Rate" (all five games; the owner, 2026-11-17).

   WHAT.  The tech points research brings come N times (on average: the rest of a whole point is a chance), N the
   patcher window's slider (0.1 to 10, 1 unless moved), read at start from "VVFP Tech Gain.txt" in the patcher's
   folder.  Every other tech point gain is the game's own: island events, duplicate collectibles, the puzzles' and
   dialogs' rewards, cheats.  A first collectible pays no tech points in any game (only duplicates do), so research is
   the only tech point income this changes.

   HOW (native/shared/gain_sites.h).  The calls of each game's tech point writer that pay research, in play and while
   the game catches up (the same calls):

     A New Home (writer 0x41D120)  0x43B313 0x43B32E 0x43B34B             research at Science 1, 2, 3
     The Lost Children (0x426290)  0x463737 0x4637C0                      research (Science 3; the others)
                                   0x463809                               the fire's +1
     The Secret City (0x427130)    0x459232 0x4593AA                      research (Science 0 or 4+; 1 to 3)
                                   0x4593D0 0x4593ED 0x45940B             the chief's quarter, Magic's +1, the chief's
                                                                          third or the potion's +1
                                   0x459435                               the fire's +1
     The Tree of Life (0x41E300)   0x464E58 0x464E82 0x464EAB             research, the Lab Equipment bonus, the fire
     New Believers (0x4237B0)      0x46DE48 0x46DE77 0x46DEA0             research, the second set's bonus, the fire

   The Science level, the speed, catch-up's divisors, the Purify Tree's glow, the chief, Magic, the potion, the fire
   and the collections' bonuses are worked out before the call, so they all still count; the Origins Tech Point
   Doubler works on the scaled amount.  The 0.1-100x Tech Cost slider changes prices, not gains: both work together.

   SAFETY.  At 1x, or with no setting file, nothing is installed.  Every site is checked to hold exactly its stock
   call first (all of them, or none).  Nothing is written to a save, a villager record or a file; no text is shown.
   No debug output. */
#include <windows.h>
#include "../shared/gain_sites.h"

#define TG_CHOICE_FILE "VVFP Tech Gain.txt"

static const gs_game TG_GAMES[] = {
    { 1, 0x41D120u, 3, { { 0x43B313u, 0 }, { 0x43B32Eu, 0 }, { 0x43B34Bu, 0 } } },
    { 2, 0x426290u, 3, { { 0x463737u, 0 }, { 0x4637C0u, 0 }, { 0x463809u, 0 } } },
    { 3, 0x427130u, 6, { { 0x459232u, 0 }, { 0x4593AAu, 0 }, { 0x4593D0u, 0 }, { 0x4593EDu, 0 }, { 0x45940Bu, 0 },
                         { 0x459435u, 0 } } },
    { 4, 0x41E300u, 3, { { 0x464E58u, 0 }, { 0x464E82u, 0 }, { 0x464EABu, 0 } } },
    { 5, 0x4237B0u, 3, { { 0x46DE48u, 0 }, { 0x46DE77u, 0 }, { 0x46DEA0u, 0 } } },
};

/* 1 when installed (for the tests' emulation), else 0. */
int __stdcall VvfpTechGainInstalled(void) {
    return g_gs_installed;
}

/* N in tenths, as read at start (for the tests' emulation). */
int __stdcall VvfpTechGainTenths(void) {
    return (int)g_ss_tenths;
}

/* Called once by VVFP More Companions.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    gs_start(TG_GAMES, (int)(sizeof TG_GAMES / sizeof TG_GAMES[0]), game, TG_CHOICE_FILE);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
