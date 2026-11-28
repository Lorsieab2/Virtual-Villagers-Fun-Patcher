/* VVFP Food Gain -- "Food Gained per Food Source" (all five games; the owner, 2026-11-17).

   WHAT.  The food a food source gives each time -- a pick, a harvest, a catch, a mushroom -- comes N times (on
   average: the rest of a whole food is a chance), N the patcher window's slider (0.1 to 10, 1 unless moved), read at
   start from "VVFP Food Gain.txt" in the patcher's folder.  What the source itself loses is the game's own (a bush
   still loses what it would have given), and so is every gain that is not a food source: island events, the
   puzzles' and dialogs' rewards, purchases and cheats, a new village's food, meals.  The Golden Child's +150 food
   (A New Home) and the chief's food grant (The Secret City) are scaled too (the owner, 2026-11-18, as the Origins
   Food Doubler doubles them).

   HOW (native/shared/gain_sites.h).  The calls of each game's food writer that pay a food source, in play and while
   the game catches up (the same calls):

     A New Home (writer 0x41D140)  0x43AD8C berries, 0x43AECD crops, 0x43AF3C fish, 0x43AF8E crab, 0x43AFF7 mushroom,
                                   0x43B09B the Golden Child's +150 food
     The Lost Children (0x4262B0)  0x463198 coconuts, 0x463259 crops, 0x463312 fish, 0x463364 big catch,
                                   0x4633CD mushroom (optional: the Golden Mushroom row owns it; then the jump
                                   0x473E1B at the end of that row's code, below)
     The Secret City (0x4263F0)    0x434AEC fruit, 0x434B15 the chief's fruit bonus, 0x431C2A honey, 0x431C4C the
                                   chief's honey bonus, 0x458EE5 fish, 0x458FE1 crab, 0x42E079 mushroom,
                                   0x459068 the chief's food grant; the rain
                                   lift's and the cliff top's fruit 0x434C06 / 0x434D7F, or 0x434C77 with "Fruit is
                                   harvested at the food bin" (all three optional)
     The Tree of Life (0x41D920)   0x464492 berries, 0x46450B harvest, 0x464573 yellow fruit, 0x4645B0 fish, 0x4645FB
                                   golden fish, 0x464A46 crab, 0x436F15 Mossy Rocks crab, 0x468AB2 the Cooking Pit's
                                   catch-up bonus, 0x414660 mushroom, 0x464433 the inherited fish event; the yellow
                                   fruit and Cooking Pit calls optional ("Yellow Fruit Trees are No Longer Unlimited"
                                   owns them)
     New Believers (0x41EB40)      0x46CFFB noni, 0x46D10E crops, 0x46D79C lake fish, 0x41496B mushroom, and the
                                   inherited food events 0x46CF9C 0x46D074 0x46D75F 0x46D7D9 0x46DB20

   Farming levels, skills, speed and catch-up's fixed yields come before the call, so they still count; The Tree of
   Life's and New Believers' Food Mastery is applied inside the writer, after the scale (mastery of N x A instead of
   N x mastery of A: at most one food apart).  "Food Gains are Flat like VV1-3" keeps these calls.

   SAFETY.  At 1x, or with no setting file, nothing is installed.  Every required site is checked to hold exactly
   its stock call first (all of them, or none).  Nothing is written to a save, a villager record or a file; no text
   is shown.  No debug output. */
#include <windows.h>
#include "../shared/gain_sites.h"

#define FG_CHOICE_FILE "VVFP Food Gain.txt"

static const gs_game FG_GAMES[] = {
    { 1, 0x41D140u, 6, { { 0x43AD8Cu, 0 }, { 0x43AECDu, 0 }, { 0x43AF3Cu, 0 }, { 0x43AF8Eu, 0 }, { 0x43AFF7u, 0 },
                         { 0x43B09Bu, 0 } } },
    { 2, 0x4262B0u, 5, { { 0x463198u, 0 }, { 0x463259u, 0 }, { 0x463312u, 0 }, { 0x463364u, 0 }, { 0x4633CDu, 1 } } },
    { 3, 0x4263F0u, 11, { { 0x434AECu, 0 }, { 0x434B15u, 0 }, { 0x431C2Au, 0 }, { 0x431C4Cu, 0 }, { 0x458EE5u, 0 },
                          { 0x458FE1u, 0 }, { 0x42E079u, 0 }, { 0x434C06u, 1 }, { 0x434D7Fu, 1 }, { 0x434C77u, 1 },
                          { 0x459068u, 0 } } },
    { 4, 0x41D920u, 10, { { 0x464492u, 0 }, { 0x46450Bu, 0 }, { 0x464573u, 1 }, { 0x4645B0u, 0 }, { 0x4645FBu, 0 },
                          { 0x464A46u, 0 }, { 0x436F15u, 0 }, { 0x468AB2u, 1 }, { 0x414660u, 0 }, { 0x464433u, 0 } } },
    { 5, 0x41EB40u, 9, { { 0x46CFFBu, 0 }, { 0x46D10Eu, 0 }, { 0x46D79Cu, 0 }, { 0x41496Bu, 0 }, { 0x46CF9Cu, 0 },
                         { 0x46D074u, 0 }, { 0x46D75Fu, 0 }, { 0x46D7D9u, 0 }, { 0x46DB20u, 0 } } },
};

/* The Lost Children with "Super-Secret Golden Mushroom" (the owner, 2026-11-27: the slider scales its mushrooms too,
   brown, red and golden, exactly as without that row).  That row's call at 0x4633CD goes to its own code at 0x473E05,
   which makes a golden mushroom's food 100 and ends with `jmp 0x4262B0` at 0x473E1B -- the caller's return (0x4633D2)
   and the amount still where the writer finds them.  So while that row's code is there, byte for byte, the mushroom's
   site is that jump: it goes to gain_stub instead, which scales the amount and goes on into the writer.  The return
   the writer sees is the game's own, so the Origins Food Doubler doubles the scaled amount once, as at every other
   site.  The call at 0x4633CD (where "VVFP Golden Mushroom.dll" keeps its finds record) is not touched.  The jump is
   written with the other sites, all of them or none; VvfpFoodGainSite(5) reports it. */
#define FG_V2_GOLDEN_CODE 0x473E05u
#define FG_V2_GOLDEN_JUMP 0x473E1Bu
static const unsigned char FG_V2_GOLDEN_ROW[27] = {
    0x8B, 0x44, 0x24, 0x20,                   /* mov eax, [esp+0x20]           the villager's index */
    0x69, 0xC0, 0x8C, 0xE4, 0x00, 0x00,       /* imul eax, eax, 0xE48C */
    0x83, 0x7C, 0x30, 0x44, 0x50,             /* cmp dword [eax+esi+0x44], 0x50 carrying the golden mushroom */
    0x75, 0x05,                               /* jne the jump */
    0xC6, 0x44, 0x24, 0x04, 0x64,             /* mov byte [esp+4], 100 */
    0xE9, 0x90, 0x24, 0xFB, 0xFF,             /* jmp 0x4262B0 */
};

/* gs_start with The Lost Children's golden jump added to the same all-or-none write. */
static int fg_start(int game) {
    static vvfp_site_write w[GS_MAX_SITES];
    static unsigned char expect[GS_MAX_SITES][5];
    const gs_game *g = NULL;
    int i, n = 0;
    for (i = 0; i < (int)(sizeof FG_GAMES / sizeof FG_GAMES[0]); ++i) {
        if (FG_GAMES[i].game == game) {
            g = &FG_GAMES[i];
        }
    }
    if (g == NULL || !ss_start(FG_CHOICE_FILE)) {
        return 0;
    }
    g_gs_writer = g->writer;
    for (i = 0; i < g->count; ++i) {               /* vvfp_call_retarget's own checks */
        unsigned int rel = g->writer - (g->sites[i].va + 5u);
        g_gs_chosen[i] = 0;
        expect[i][0] = 0xE8;
        memcpy(&expect[i][1], &rel, 4);
        if (!vvfp_site_holds(g->sites[i].va, expect[i], 5)) {
            if (g->sites[i].optional) {
                continue;
            }
            return 0;
        }
        vvfp_site_branch(&w[n++], g->sites[i].va, 5, expect[i], 0xE8, (const void *)gain_stub);
        g_gs_chosen[i] = 1;
    }
    g_gs_chosen[g->count] = 0;
    if (game == 2 && vvfp_site_holds(FG_V2_GOLDEN_CODE, FG_V2_GOLDEN_ROW, (int)sizeof FG_V2_GOLDEN_ROW)) {
        vvfp_site_branch(&w[n++], FG_V2_GOLDEN_JUMP, 5, FG_V2_GOLDEN_ROW + (FG_V2_GOLDEN_JUMP - FG_V2_GOLDEN_CODE),
                         0xE9, (const void *)gain_stub);
        g_gs_chosen[g->count] = 1;
    }
    if (n == 0 || !vvfp_install_sites(w, n)) {
        for (i = 0; i <= g->count; ++i) {
            g_gs_chosen[i] = 0;
        }
        return 0;
    }
    g_gs_installed = 1;
    return 1;
}

/* 1 when installed (for the tests' emulation), else 0. */
int __stdcall VvfpFoodGainInstalled(void) {
    return g_gs_installed;
}

/* N in tenths, as read at start (for the tests' emulation). */
int __stdcall VvfpFoodGainTenths(void) {
    return (int)g_ss_tenths;
}

/* Whether the game's site `index` (of its table) was written (for the tests' emulation). */
int __stdcall VvfpFoodGainSite(int index) {
    return index >= 0 && index < GS_MAX_SITES ? g_gs_chosen[index] : 0;
}

/* Called once by VVFP More Companions.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (!g_gs_installed) {
        fg_start(game);
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
