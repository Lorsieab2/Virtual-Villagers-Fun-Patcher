/* VVFP Appearance Rolls -- part of "Fix Vanilla Bugs" in The Lost Children, The Tree of Life and New
   Believers (the owner, 2026-10-25: "fix the body selector to accept that last body", and every random
   head may spawn too, except the Golden Child's head in A New Home).

   THE STOCK ROLLS.  Every head and body a game hands out at random was traced in the stock executables
   (inputs\vvN-stock-copy; rand(n) is each game's rand() % n, VV1 0x402F10, VV2 0x4031A0, VV3 0x4032D0,
   VV4 0x4036D0, VV5 0x403660).  Each game has 30 heads and 30 bodies per sex (A New Home 20), rows of
   its own pictures.  Two kinds of roll leave the last row out:

     The Lost Children, "A Mysterious Vial" (green), drunk: a man's new head is rand(29), 0 to 28
       (0x4395ED and 0x43968F, push 0x1D), a woman's rand(30) (0x4396BC, 0x4396E9).  Head 29 is an
       ordinary man's head (a newborn boy gets it from the creator's rand(30) and its inheritance clamp),
       so the drink now rolls rand(30) for a man too.
     The Tree of Life and New Believers, the creator's body: rand(29), 0 to 28 (VV4 0x45F2AE, VV5
       0x4685B3, push 0x1D), so body 29 was never given -- to a newborn, a twin (a copy of the first
       baby), a Barrel of Babies baby, an island event's or the canoe's arrival, or a new village's
       villager: every one is made by this creator.  It now rolls rand(30).

   LEFT AS THEY ARE (the owner): The Secret City's body roll rand(29) (0x456520) -- body 29 is the
   Tribal Chief's robe, for both sexes -- and A New Home's boys, whose head and body are rand(19)
   (0x43C61F) and whose "A Mysterious Vial" head is rand(19) (0x42C92D, 0x42C9C9), because row 19 is
   the Golden Child's.  A New Home's girls already roll rand(20), every
   other head roll in every game already reaches row 29 (the creators' rand(30) and their 0..29 clamp,
   VV3's obsidian vial rand(30) at 0x417634), and The Lost Children's bodies are rand(30).

   INSTALLING.  VvfpStartup(game, shipped), called once by VVFP Startup.dll at game start (second
   word, native/shared/startup_companions_2.h), outside DllMain.  Each site is the push's immediate
   with the instructions just before it, checked byte for byte; the game's sites go in together through
   the shared all-or-none writer (native/shared/install_sites.h), or none does.  Only the pushed bound
   changes (0x1D -> 0x1E); the call after it is not touched (the Story / Cheat Upgrades companion may
   replace that call to force a chosen head). */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"

typedef struct roll_site {
    unsigned int va;              /* the first checked byte */
    int length;
    const unsigned char *stock;   /* ends with 6A 1D: push 29 */
} roll_site;

/* The Lost Children: cmp dword ptr [eax+ecx+0x538], 1 (a man); jne; push 0x1D. */
static const unsigned char VV2_VIAL_1[] = {
    0x83, 0xBC, 0x08, 0x38, 0x05, 0x00, 0x00, 0x01, 0x0F, 0x85, 0xFC, 0x00, 0x00, 0x00, 0x6A, 0x1D,
};
/* The same drink's other text (cmp dword ptr [edx+eax+0x538], 1; jne short; push 0x1D). */
static const unsigned char VV2_VIAL_2[] = {
    0x83, 0xBC, 0x02, 0x38, 0x05, 0x00, 0x00, 0x01, 0x75, 0x2D, 0x6A, 0x1D,
};
/* The Tree of Life and New Believers: mov dword ptr [edi+0x2C], 0x1D (the head's clamp); push 0x1D. */
static const unsigned char LATER_BODY[] = { 0xC7, 0x47, 0x2C, 0x1D, 0x00, 0x00, 0x00, 0x6A, 0x1D };

static const roll_site VV2_SITES[] = {
    { 0x4395DFu, (int)sizeof VV2_VIAL_1, VV2_VIAL_1 },
    { 0x439685u, (int)sizeof VV2_VIAL_2, VV2_VIAL_2 },
};
static const roll_site VV4_SITES[] = { { 0x45F2A7u, (int)sizeof LATER_BODY, LATER_BODY } };
static const roll_site VV5_SITES[] = { { 0x4685ACu, (int)sizeof LATER_BODY, LATER_BODY } };

#define MAX_SITES 2

static int installed;

static void install(const roll_site *sites, int count) {
    vvfp_site_write w[MAX_SITES];
    int i;
    if (count <= 0 || count > MAX_SITES) {
        return;
    }
    for (i = 0; i < count; ++i) {
        vvfp_site_bytes(&w[i], sites[i].va, sites[i].length, sites[i].stock, sites[i].stock);
        w[i].bytes[sites[i].length - 1] = 0x1E;          /* push 30: rand(30), rows 0 to 29 */
    }
    if (vvfp_install_sites(w, count)) {
        installed = 1;
    }
}

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (installed) {
        return;
    }
    if (game == 2) {
        install(VV2_SITES, (int)(sizeof VV2_SITES / sizeof VV2_SITES[0]));
    } else if (game == 4) {
        install(VV4_SITES, 1);
    } else if (game == 5) {
        install(VV5_SITES, 1);
    }
}

/* 1 when every site of this game went in, 0 when none did (or this game has none). */
__declspec(dllexport) int __stdcall VvfpAppearanceRollsInstalled(void) {
    return installed;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
