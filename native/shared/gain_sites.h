/* gain_sites.h -- the one shape of "Food Gained per Food Source" (native/vvfp_food_gain) and "Tech Point Gain Rate"
   (native/vvfp_tech_gain): chosen calls of the game's own food (or tech point) writer gain N times as much.

   Every food and tech point change of each game goes through one writer per resource, `__thiscall writer(delta)`
   (ecx the store, the signed delta at [esp + 4], `ret 4`).  A companion points only the calls it scales -- the food
   sources' (or research's) -- at gain_stub: their return address stays the game's own, so everything keyed on it
   (the Origins doublers' lists, the statistics) sees the stock caller, and every other call (island events,
   purchases, cheats, meals, duplicate collectibles) never reaches this code.  gain_stub scales a POSITIVE delta
   (ss_scale: N times on average) and goes on into the writer with every register as the game left it; a delta of 0
   or less goes on unchanged.  The writer's own work after that (The Tree of Life and New Believers: Food Mastery;
   the Origins doublers) runs on the scaled amount.

   A GS_GAME table entry gives the writer and its sites (native/shared/slider_scale.h vvfp_call_site: an optional site
   is one another patch may own, left alone when it does not hold the stock call). */
#ifndef VVFP_GAIN_SITES_H
#define VVFP_GAIN_SITES_H

#include <windows.h>
#include "slider_scale.h"

#define GS_MAX_SITES SS_MAX_SITES

typedef struct {
    int game;
    unsigned int writer;
    int count;
    vvfp_call_site sites[GS_MAX_SITES];
} gs_game;

static unsigned int g_gs_writer;
static int g_gs_installed;
static int g_gs_chosen[GS_MAX_SITES];

static int __cdecl gs_scaled(int delta) {
    return delta > 0 ? (int)ss_scale((unsigned int)delta) : delta;
}

/* [esp] the caller's return (the site + 5), [esp + 4] the delta, ecx the store. */
__declspec(naked) static void gain_stub(void) {
    __asm {
        push eax
        push ecx
        push edx
        push dword ptr [esp + 16]
        call gs_scaled
        add esp, 4
        mov dword ptr [esp + 16], eax
        pop edx
        pop ecx
        pop eax
        jmp dword ptr [g_gs_writer]
    }
}

/* Install the table's entry for `game` with the slider read from `choice_file`; 1 when installed. */
static int gs_start(const gs_game *games, int game_count, int game, const char *choice_file) {
    const gs_game *g = NULL;
    int i;
    if (g_gs_installed) {
        return 1;
    }
    for (i = 0; i < game_count; ++i) {
        if (games[i].game == game) {
            g = &games[i];
        }
    }
    if (g == NULL || !ss_start(choice_file)) {
        return 0;
    }
    g_gs_writer = g->writer;
    if (vvfp_call_retarget(g->sites, g->count, g->writer, (const void *)gain_stub, g_gs_chosen)) {
        g_gs_installed = 1;
    }
    return g_gs_installed;
}

#endif /* VVFP_GAIN_SITES_H */
