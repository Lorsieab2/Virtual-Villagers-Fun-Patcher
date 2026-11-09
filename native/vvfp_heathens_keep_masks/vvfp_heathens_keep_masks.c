/* VVFP Heathens Keep Masks -- "Heathens Keep Their Masks When Converted", New Believers.

   The owner (2026-11-08): "Heathens keep their masks when converted -- when a heathen converts their mask stays
   on their head (as if the player manually set it using Change Appearance)."  "Oh and the player can always
   Change Appearance to change it or take it off if they want to."  And: "Reset to original" gives the Heathen
   mask back -- a convert's original look is the head and body they had with the mask they wore.

   THE STOCK GAME.  A Heathen joins the tribe through the conversion 0x4668B0 (what SetFaith 0x467F90 calls when
   a Heathen's Faith rises above 0 -- preaching, Spreading the Word, the Earthquake, the puzzle rewards, island
   events -- and what the Story / Cheat Upgrades' Custom Island Event "Becomes a believer" calls).  It clears the
   role +0x1CFC unless it is 13, the Heathen Chief's (0x466966; he stays the tribe's Retired Chief), then the
   faction byte +0x1CEC (0x46697D, through the setter 0x466880(0)).  The game draws a Heathen's mask only while
   that byte is set (0x4728C6), so the mask is gone.  The one other way a Heathen becomes a believer is The
   Defector's "welcome" (0x416970): SetFaith(+20) -- which converts through 0x4668B0 when the Faith rises above
   0 -- and then the setter 0x466880(0) directly (0x41699F), which makes a Heathen whose Faith stayed at 0 or
   below a believer without the conversion.

   THE MASK THEY WORE is the game's own choice (0x4728C6, native/shared/former_heathens.h vv_former_kind_of):
   purple for the roles 12 and 14-16 (the Heathen Doctor and the three Masters), the Chief's for role 13, else
   orange (+0x1CED), red (+0x1CEE) or blue.

   WHAT THIS COMPANION DOES.  At both places -- inside the conversion just before the role is cleared
   (0x466966, the `cmp dword [esi+0x1CFC], 13`), and at The Defector's direct call of the setter (0x41699F) --
   while the record is still a Heathen:
     * the mask they wear (1 Blue, 2 Orange, 3 Red, 4 Purple, 5 the Tribal Chief's) is handed to the Origins
       companion's VvfpMaskKeep, which puts it in the store Change Appearance keeps a believer's mask in (its
       mask table and Village Masks file) -- at once, or, while that slot's file has not loaded yet (held by
       another program a moment), as soon as the load settles.  So the convert is drawn with the mask exactly as
       a believer whose mask the player chose (the Origins render, 0x472481), Change Appearance shows it as
       their mask, and the player can change it or take it off as with any other;
     * "VVFP Original Look.dll" is told (VvfpOriginalLookConverted): their original look, kept while they were a
       Heathen with no mask, takes the mask, so Reset to original gives it back (original_look_store.inc
       ol_converted has the rule).  Without that companion nothing is told: Reset to original then has the
       original it has.
   Nothing is charged and no "Appearance changed" is logged: the villager's look did not change.

   ONLY WITH THE ORIGINS COMPANION.  The store belongs to "VVFP Origins Icons.dll" (Enable Origins-Exclusive
   Features, this row's dependency).  When it is not loaded or has no VvfpMaskKeep, nothing is kept: the convert
   loses the mask as in the stock game.

   HOW.  Both sites are spliced at run time, after their stock bytes are checked, all or none
   (native/shared/install_sites.h); no executable byte is patched.  The splice saves every register and flag,
   does the above under structured exception handling (a fault keeps nothing and the conversion goes on), then
   makes the very instruction it replaced and goes on where the game would.  Started by VVFP Startup.dll (its
   second word, native/shared/startup_companions_2.h).  No debug output, no text shown. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/former_heathens.h"
#include "../shared/original_look.h"

#define HK_GAME 5
#define HK_ORIGINS "VVFP Origins Icons.dll"

/* The conversion's role test: cmp dword [esi+0x1CFC], 0xD -- then je 0x466979. */
#define HK_CONVERT_SITE 0x466966u
#define HK_CONVERT_NEXT 0x46696Du
/* The Defector's call of the setter with 0: call 0x466880, returning to 0x4169A4. */
#define HK_DEFECTOR_SITE 0x41699Fu
#define HK_DEFECTOR_NEXT 0x4169A4u
#define HK_FACTION_SETTER 0x466880u

static const unsigned char CONVERT_STOCK[7] = { 0x83, 0xBE, 0xFC, 0x1C, 0x00, 0x00, 0x0D };
static const unsigned char DEFECTOR_STOCK[5] = { 0xE8, 0xDC, 0xFE, 0x04, 0x00 };

static int g_installed;
static unsigned int g_kept;             /* masks handed to the store this session (the tests read it) */

typedef int (__stdcall *hk_keep_fn)(void *record, int mask);
typedef int (__stdcall *hk_converted_fn)(int game, const void *record, int mask);

/* The Heathen in `record` is joining the tribe: the mask they wear becomes their Change Appearance mask, and
   part of their original look. */
static void hk_keep(unsigned char *record) {
    HMODULE origins, looks;
    hk_keep_fn keep;
    hk_converted_fn converted;
    int mask;
    if (record == NULL || record[VV5_FACTION] == 0) {
        return;                         /* already a believer: nothing to keep */
    }
    origins = GetModuleHandleA(HK_ORIGINS);
    keep = origins != NULL ? (hk_keep_fn)GetProcAddress(origins, "VvfpMaskKeep") : NULL;
    if (keep == NULL) {
        return;                         /* no New Believers Origins companion: the stock loss */
    }
    mask = vv_former_kind_of(record) + 1;           /* VV_FORMER_BLUE..CHIEF -> 1..5 */
    if (keep(record, mask) <= 0) {
        return;                         /* refused: not a villager record the store knows */
    }
    ++g_kept;
    looks = GetModuleHandleA(VVFP_ORIGINAL_LOOK_DLL);
    converted = looks != NULL ? (hk_converted_fn)GetProcAddress(looks, VVFP_ORIGINAL_LOOK_CONVERTED) : NULL;
    if (converted != NULL) {
        (void)converted(HK_GAME, record, mask);
    }
}

static void __stdcall hk_converting(unsigned char *record) {
    __try {
        hk_keep(record);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* In place of the conversion's role test: esi is the record. */
__declspec(naked) static void hk_convert_stub(void) {
    __asm {
        pushfd
        pushad
        push esi
        call hk_converting
        popad
        popfd
        cmp dword ptr [esi + 0x1CFC], 0x0D
        push HK_CONVERT_NEXT
        ret
    }
}

/* In place of The Defector's `call 0x466880` (its argument 0 already pushed): ecx is the record. */
__declspec(naked) static void hk_defector_stub(void) {
    __asm {
        pushfd
        pushad
        push ecx
        call hk_converting
        popad
        popfd
        push HK_DEFECTOR_NEXT
        push HK_FACTION_SETTER
        ret
    }
}

/* 1 when both sites are installed (for the tests' emulation), else 0. */
int __stdcall VvfpHeathensKeepMasksInstalled(void) {
    return g_installed;
}

/* How many masks were handed to the store this session (for the tests' emulation). */
unsigned int __stdcall VvfpHeathensKeepMasksKept(void) {
    return g_kept;
}

/* Called once by VVFP Startup.dll before WinMain, on the game's own thread. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[2];
    (void)shipped;
    if (g_installed || game != HK_GAME) {
        return;
    }
    vvfp_site_branch(&sites[0], HK_CONVERT_SITE, (int)sizeof CONVERT_STOCK, CONVERT_STOCK, 0xE9,
                     (const void *)hk_convert_stub);
    vvfp_site_branch(&sites[1], HK_DEFECTOR_SITE, (int)sizeof DEFECTOR_STOCK, DEFECTOR_STOCK, 0xE9,
                     (const void *)hk_defector_stub);
    if (vvfp_install_sites(sites, 2)) {
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
