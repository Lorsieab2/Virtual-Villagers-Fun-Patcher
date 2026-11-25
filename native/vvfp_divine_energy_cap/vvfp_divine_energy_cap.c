/* VVFP Divine Energy Cap -- "Max Divine Energy Continues to Increase", New Believers.

   The owner (2026-11-25): "removes the hardcoded 1000 max energy to allow it to increase with population and
   collectibles".

   THE STOCK GAME.  Every update of the village (0x4425A3) runs the cap routine 0x425020 on the village manager:
     cap = 5 x (0x4713F0: the living believers + the babies they carry + 2)
         + 50 once the Tribute Statue is at stage 1 or more (0x4271C0), + 50 more at stage 2
         + 100 once The Tribute Statue (puzzle 14, 0x43AE80) is solved
         + 50 at Spirituality (tech 5, 0x423600) 2 or more, + 50 more at 3
         + the first collectible set (ids 0x68.., 0x413F50): 3 for each piece owned, a flat 90 once all 24 are owned;
   then "at most 1,000" (0x4250B4: cmp esi, 1000 / jle / mov esi, 1000), at least 0, stored at +0x17D60; then, when
   the runtime byte +0x17E11 is set, the cap is forced to exactly 1,000 (0x4250D8); then the current Divine Energy
   (+0x17D64) is kept at most the cap through the adder 0x424F80(0).
   The byte +0x17E11 is never set by the game: its only write is the clear in the village reset 0x4246A0 (0x424807,
   run by every new village and every load, 0x4251D3 / 0x4253A5), it lies past the part of the manager a save keeps
   (+8 .. +0x17D80, 0x4245F2 / 0x4256FA) and no code stores a non-zero value there -- a left-over "full energy"
   switch with nothing to turn it on.  The patch keeps it meaning "at least 1,000" instead of "exactly 1,000", so it
   can never take the patch's cap back down.
   The HUD's Divine Energy bar 0x450380 (called only from 0x44321E with x 0x269, y 0xC, the cap, the current Divine
   Energy and the chosen power's cost) clamps the cap to 10..1,000 and draws a frame cap x 372 / 1,000 pixels wide,
   filled current / cap of the frame and the chosen power's cost / cap of it -- but it divides by the CLAMPED cap,
   so above a 1,000 cap the fill would run past the frame.

   WHAT THIS COMPANION DOES (all three sites, or none):
     * 0x4250BA: the "at most 1,000" jle becomes an unconditional jmp: the cap is the formula, uncapped (at least 0
       still); 150 believers with every bonus give 1,150, 256 (256 Villagers) give 1,680;
     * 0x4250D8: the +0x17E11 path stores max(the formula, 1,000) instead of 1,000;
     * 0x44321E: the bar's call goes through the companion: when the cap is above 1,000 the bar is given a cap of
       1,000, the current Divine Energy x 1,000 / cap and the chosen power's cost x 1,000 / cap (at least 1 for a
       chosen power), so a full village fills the whole 372-pixel frame and every part stays in proportion.  A cap
       of 1,000 or less passes unchanged.
   The HUD's numbers (0x442398 / 0x4423CA, "%i"), the powers' unlock tests (cap >= 10..800, 0x440E71, 0x441107,
   0x44147E, 0x441569), the power buttons (0x422E60), Blessings Day's fill to the cap (0x414B58), the adder and
   subtractor (0x424F80 / 0x424FD0) and the low-energy event (0x44E64A) read the whole int32 and need no change.

   HOW.  The sites are written at run time, after their stock bytes are checked (native/shared/install_sites.h); no
   executable byte is patched.  The cap and current Divine Energy are whole int32s in the saved part of the manager
   (save offsets 0x17D70 / 0x17D74), so a save written with a cap above 1,000 loads in any game: without the patch the
   next update clamps the cap to 1,000 and the Divine Energy to it.  Started by VVFP More Companions.dll (the third
   word, native/shared/startup_companions_3.h).  No file, no text, no debug output. */
#include <windows.h>
#include "../shared/install_sites.h"

#define EC_GAME 5

#define EC_CLAMP_SITE 0x4250B4u         /* cmp esi, 1000 / jle +7 / mov esi, 1000 */
#define EC_FORCED_SITE 0x4250D8u        /* mov dword ptr [edi + 0x17D60], 1000 (the +0x17E11 path) */
#define EC_FORCED_BACK 0x4250E2u        /* the clamp of the current Divine Energy to the cap */
#define EC_BAR_SITE 0x44321Eu           /* call 0x450380, the Divine Energy bar */
#define EC_BAR 0x450380u
#define EC_STOCK_CAP 1000
#define EC_CAP 0x17D60

static const unsigned char CLAMP_STOCK[13] = {
    0x81, 0xFE, 0xE8, 0x03, 0x00, 0x00, /* cmp esi, 1000 */
    0x7E, 0x07,                         /* jle 0x4250C3 */
    0xBE, 0xE8, 0x03, 0x00, 0x00        /* mov esi, 1000 */
};
static const unsigned char CLAMP_PATCHED[13] = {
    0x81, 0xFE, 0xE8, 0x03, 0x00, 0x00, /* cmp esi, 1000 */
    0xEB, 0x07,                         /* jmp 0x4250C3: never clamped to 1,000 (at least 0 still) */
    0xBE, 0xE8, 0x03, 0x00, 0x00        /* (no longer reached) */
};
static const unsigned char FORCED_STOCK[10] = {
    0xC7, 0x87, 0x60, 0x7D, 0x01, 0x00, 0xE8, 0x03, 0x00, 0x00   /* mov dword ptr [edi + 0x17D60], 1000 */
};
static const unsigned char BAR_STOCK[5] = {
    0xE8, 0x5D, 0xD1, 0x00, 0x00        /* call 0x450380 */
};

static int g_installed;

/* The bar's five arguments, in place: x, y, cap, current, cost. */
static void ec_scale(int *args) {
    int cap = args[2];
    int current = args[3];
    int cost = args[4];
    if (cap <= EC_STOCK_CAP) {
        return;                         /* the stock bar, unchanged */
    }
    if (current > cap) {
        current = cap;
    }
    if (current < 0) {
        current = 0;
    }
    args[3] = (int)(((__int64)current * EC_STOCK_CAP) / cap);
    if (cost > 0) {
        int scaled = (int)(((__int64)(cost > cap ? cap : cost) * EC_STOCK_CAP) / cap);
        args[4] = scaled < 1 ? 1 : scaled;
    }
    args[2] = EC_STOCK_CAP;
}

static void __stdcall ec_bar_args(int *args) {
    __try {
        ec_scale(args);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* In place of the bar's call: [esp] the return to 0x443223, [esp + 4] the five arguments; ecx the bar. */
__declspec(naked) static void ec_bar_stub(void) {
    __asm {
        pushfd
        pushad
        lea eax, [esp + 28h]            /* 0x24 saved + the return address */
        push eax
        call ec_bar_args
        popad
        popfd
        push EC_BAR
        ret
    }
}

/* In place of the +0x17E11 path's store: esi the cap as computed, edi the manager. */
__declspec(naked) static void ec_forced_stub(void) {
    __asm {
        cmp esi, EC_STOCK_CAP
        jge done
        mov dword ptr [edi + EC_CAP], EC_STOCK_CAP
    done:
        push EC_FORCED_BACK
        ret
    }
}

/* 1 when the three sites are installed (for the tests' emulation), else 0. */
int __stdcall VvfpDivineEnergyCapInstalled(void) {
    return g_installed;
}

/* Called once by VVFP More Companions.dll before WinMain, on the game's own thread. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[3];
    (void)shipped;
    if (g_installed || game != EC_GAME) {
        return;
    }
    vvfp_site_bytes(&sites[0], EC_CLAMP_SITE, (int)sizeof CLAMP_STOCK, CLAMP_STOCK, CLAMP_PATCHED);
    vvfp_site_branch(&sites[1], EC_FORCED_SITE, (int)sizeof FORCED_STOCK, FORCED_STOCK, 0xE9,
                     (const void *)ec_forced_stub);
    vvfp_site_branch(&sites[2], EC_BAR_SITE, (int)sizeof BAR_STOCK, BAR_STOCK, 0xE8, (const void *)ec_bar_stub);
    if (vvfp_install_sites(sites, 3)) {
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
