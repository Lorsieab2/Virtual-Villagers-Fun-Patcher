/* The Remembrance Ceremony and The Rumblings (ceremony_core.inc): each game's side.  Included by
   vvfp_more_island_events.c after adv_vv345.inc, adv_vv1.inc and adv_vv2.inc, whose records, random routines and
   calling helpers it uses.  Every address was read in the stock executables (research/stock-executables).

   ---- THE REMEMBRANCE CEREMONY: who goes, where, and the game's own starter --------------------------------------

   Each villager the records hold as living and present is sent on its own, as each game's own Day of Honor starts
   each one -- the stop first, then the action -- so the stock group filters (A New Home's Isola Day starter 0x4457D0
   and The Lost Children's Day of Honor loop 0x433A60 skip anyone who dislikes crowds, and A New Home's skips the
   sick; The Secret City's 0x45DDE0 skips the 14 to 17 year olds, a puzzle's worker +0xF13 and a child holding an
   object +0xF20) leave no one out (the owner: "everyone joins in, even children, nursing mothers. no one is left
   out").  Safe: the same starters already take each of those kinds -- the stock group starters take children and
   adults holding an object, The Tree of Life's and New Believers' take everyone present and alive (babies that are
   records included, 0x4671A0 / 0x470C60 with every filter -1), the stop routine is what the game itself runs when
   the player drags a villager away from any job (a puzzle's worker included: it clears +0xF13), and Custom Island
   Events (Story / Cheat Upgrades) already starts these actions for any living villager.  Babies still being carried
   are not records in any game, so they are not sent.  Never the dead, the absent, The Secret City's stand-in
   records (+0xE94), The Tree of Life's bodies and ghosts (+0x1CC7), New Believers' corpses and spirits (+0x1CE1)
   or Heathens (+0x1CEC).

     A New Home      the cemetery: "Honoring the Dead" 0x4401E0 (its only honoring action; no Reflecting), after
                     the stop 0x439470 (thiscall on the villagers, the index; Isola Day's starter 0x4457D0 runs
                     the same two).  Graves: 0x41CF10 on the world (the 50 grave slots at +0xA340).
     The Lost Children  the memorial: "Honoring the Dead (Day of Honor)" 0x454890 or "Reflecting" 0x4523A0, 50%
                     each (both walk to the memorial; the game's own idle chooser 0x45F1E3 pairs them 50/50), after
                     the stop 0x4492A0 (the Day of Honor's own loop, 0x433A8C / 0x433A98).  Graves: 0x426160 on the
                     world (the Day of Honor's own condition, 0x4347C0).
     The Secret City  the graveyard (no mausoleum): "Honoring the Dead" (action 0xA, 0x447CF0) or "Reflecting"
                     (0x16, 0x447460), 50% each (the everyday chooser 0x45A151 pairs them 50/50), started as the Day
                     of Honor's 0x45DDE0 starts each villager (0x45E082..0x45E09A): stop 0x460F70, do-action
                     0x455570(action, &flag), then 0x461BF0.  Graves: 0x454B10 on 0x5973F0 (the Day of Honor's
                     0x414FC0 asks for 2; the owner: at least 1).
     The Tree of Life  the graveyard only (the owner): "Honoring the Dead" (action 9, 0x452DE0), started as the Day
                     of Honor's 0x4671A0 does (0x467256..0x46726F): stop 0x468C60, 0x45DEC0(9, &flag), 0x46A030.
                     Graves: 0x45D670 on 0x5025C8 (the Day of Honor's 0x414AD0 asks for 2).
     New Believers   "Honoring the Dead" (behaviour 17, the game's own "Honoring the dead", 0x4595B0; never the
                     devotees' separate "Honoring" job: its walks go to area 0x7B, inside the mausoleum's area
                     0x38), started as the Day of Honor's 0x470C60 does (0x470D34..0x470D46): stop 0x473440, then
                     0x465580(17, &flag).  With "Memorial Actions Can Also Occur at the Heathen Hovel" installed
                     (its exact bytes: the two sites and both caves, as scripts/build_vv5_hovel_memorial_actions.py
                     writes them): 50% the mausoleum as above, 50% the hovel, where Honoring the Dead (the patch's own start,
                     past its 25% roll: 0x494B88, so its three grave walks go to the hovel) or Reflecting (the
                     patch's own wrapper past its roll, 0x494B6F, with +0x1D10 = 29 as 0x465580 writes it; its five
                     walks go to the hovel) 50% each.  Without the patch Reflecting is never used (the owner).
                     Graves: 0x464E90 on 0x5481A8 (the Day of Honor's 0x414DB0 asks for 2); The Last Heathen:
                     0x43AE80(25) on 0x51E008 (saved, for good).

   THE FEAST: 10 food for every villager the game counts, never below 0 -- A New Home world+0xA2EC by 0x41CF90 and
   The Lost Children world+0x2EAA4 by 0x425860 (Blessings Day's own direct writes, 0x4280B7 / 0x433C4C), The Secret
   City through 0x4263F0 on 0x582490 by 0x45D460(7, -1, 0) (Blessings Day 0x414D10 exactly), The Tree of Life
   through 0x41D920 on 0x4D6DD0 by 0x467610, New Believers through 0x41EB40 on 0x51D34C by 0x4713F0 (each writer
   stops the store at 0).

   ---- THE RUMBLINGS: the structures and the only states written -----------------------------------------------

   Only structures that are not puzzles (the owner): A New Home's second and third huts (its first is "The Hut"
   puzzle); The Lost Children's three population huts (its Lovely Hut, Hospital and Sewing Hut are puzzles); The
   Secret City's three huts and clothing hut; The Tree of Life's three huts, clothing hut, love shack, nursery school
   and hospital; New Believers' three huts, clothing hut and love shack (its nursery school left out: the owner).
   A damaged structure gets the state a normal construction passes through with that much work done:

     A New Home      hut k (10, 11): flag world+0x9FF0 / +0x9FF8 = 0, progress +0x9FEC / +0x9FF4 = work left in
                     (done at 400 / 600), then the walk grid 0x414590 ([villagers +0x3E014]) and the scene 0x416380
                     ([villagers +0x3E024]) rebuilt, as the hut's own completion (0x43A98E) and Custom Island Events'
                     unsolve do; at 100% progress 0, and the rebuild itself writes the scaffold's 1 at the
                     population that shows it (0x414B0C / 0x414BF1), exactly the new village.
     The Lost Children  hut 24, 25, 26: flag world+0x2E818 / +0x2E820 / +0x2E828 = 0, progress +0x2E814 / ... = the
                     work left in (done at 450 / 700 / 900; hut 24 starts a new village at 205, 0x42517D, so its loss
                     is counted on the work above 205), then 0x418660 ([pool +0xE574D8]) and 0x41C1D0
                     ([pool +0xE574E8]); the scaffold's 1 again written by the refresh itself (0x419702 / 0x41977D).
     The Secret City  hut i (projects 21-24, the manager 0x594620, record +4 + 0x14 i): the loss on the work above
                     the new-village progress (0x4322F0: states 1, 2, 3, 3 -> 1750, 400, 0, 0 of 2000); progress
                     written through 0x435970 (the project table's own setter), the state +4 the new village's,
                     partly damaged: under construction +0 = 1 and the percent base +8 = the new village's work left
                     (as a construction that began there); at 100%: +0 = 0, base 0 -- the new village.  Never the
                     manager's reset (0x435680 -> 0x4322F0 resets all four at once).
     The Tree of Life / New Believers  project 19.. (each building's own object, its project id at +8 checked):
                     its set state (vtable +0x40 / +0x44) with 3 -- progress 0, state 3, base 2000, the site shown
                     where it stands -- then, partly damaged, the progress (0x438A10 on 0x4D8BF8 / 0x43AF50 on
                     0x51E008) and under construction +0x30 = 1 (as the first build trip leaves it, 0x430287);
                     at 100% +0x30 = 0: unbuilt, which the player may move (0x430470 / 0x434FA0: stage 3, not under
                     construction).
     The Secret City, The Tree of Life, New Believers: the building's effect handle (+0xC / +0x3C) is freed in its
                     pool (0x429B00 on 0x58C338, 0x41D6B0 on 0x4D69D0, 0x41E710 on 0x51CF40) and set to -1, as the
                     game's own load does, so the rebuilt building gets its effect back.
     The Tree of Life's nursery school: its teacher is let go (assignment +0x1C54 = 0x10 cleared and the stop
                     0x468C60, as the game does when it replaces a teacher, 0x437688), since teaching goes on with no
                     building check (0x4635F0).

   Over the population limit: every reader of each game's room test (0x43A1A0, 0x44B310, 0x45FE30, 0x468350,
   0x472BD0) only refuses growth -- conceptions, the barrel and potions, a dragged pair; none removes, harms or stops
   anyone, and the births (0x42E900, 0x43BF6E, 0x46034F, 0x4687EF, 0x4730AF) never ask it -- so a village over its
   limit keeps everyone, babies on the way are born, and no new births come until it is rebuilt, as the stock game
   does when it runs out of room. */

typedef int (__fastcall *cr_tc1r)(void *self, void *unused, int a);
typedef int (__fastcall *cr_tc2r)(void *self, void *unused, int a, int b);
typedef void (__cdecl *cr_cdecl1)(void *a);
#define CR_TC0R(va, self) ((adv_tc0r)(uintptr_t)(va))((void *)(uintptr_t)(self), NULL)
#define CR_TC1R(va, self, a) ((cr_tc1r)(uintptr_t)(va))((void *)(uintptr_t)(self), NULL, (int)(a))

/* ---- A New Home ------------------------------------------------------------------------------------------------ */

static const unsigned int CR_V1_PUZZLES[16] = {
    0x9FA8, 0x9FB0, 0x9FB8, 0x9FC0, 0x9FC8, 0x9FD8, 0x9FE0, 0x9FE8,
    0xA000, 0xA008, 0xA050, 0xA058, 0xA080, 0xA088, 0xA090, 0xA098 };   /* the Puzzles screen's (Statistics 0x4333C0) */

static int cr_v1_graves(void) {
    unsigned char *world = VV1_WORLD();
    return world != NULL ? CR_TC0R(0x41CF10u, world) : 0;
}

static int cr_v1_goes(int index) {
    const unsigned char *r = v1_record(index);
    return r != NULL && r[0x28] == 1 && *(const int *)(r + 0x344) > 0;
}

static int cr_v1_send(int index) {
    ADV_TC1(0x439470u, VV1_ARRAY(), index);
    ADV_TC1(0x4401E0u, VV1_ARRAY(), index);
    return CR_ACT_HONOR;
}

static int cr_v1_feast(void) {
    unsigned char *world = VV1_WORLD();
    int n = CR_TC0R(0x41CF90u, world), food = *(int *)(world + 0xA2EC), used;
    used = n > 0 ? CR_FOOD_PER_VILLAGER * n : 0;
    if (used > food) {
        used = food > 0 ? food : 0;
    }
    *(int *)(world + 0xA2EC) = food - used < 0 ? 0 : food - used;
    return used;
}

static int cr_v1_puzzles(void) {
    unsigned char *world = VV1_WORLD();
    int k;
    if (world == NULL) {
        return 0;
    }
    for (k = 0; k < 16; ++k) {
        if (world[CR_V1_PUZZLES[k]] == 0) {
            return 0;
        }
    }
    return 1;
}

static int cr_v1_finished(int k) {
    return sd_finished(1, k);
}

static void cr_v1_damage(int k, int loss) {
    sd_damage(1, k, loss, NULL, 0);
}

static const cr_game CR_VV1 = {
    1, v1_count, v1_rand, cr_v1_graves, NULL, cr_v1_goes, cr_v1_send, cr_v1_feast,
    cr_v1_puzzles, 2, SD_V1_NAMES, cr_v1_finished, cr_v1_damage, 40
};

/* ---- The Lost Children ---------------------------------------------------------------------------------------- */

static const unsigned int CR_V2_PUZZLES[16] = {
    0x2E768, 0x2E770, 0x2E778, 0x2E780, 0x2E788, 0x2E790, 0x2E798, 0x2E7A0,
    0x2E7A8, 0x2E7B0, 0x2E7B8, 0x2E7C0, 0x2E7C8, 0x2E7D8, 0x2E7E0, 0x2E7E8 };   /* the Puzzles screen's */

static int cr_v2_graves(void) {
    unsigned char *world = VV2_WORLD();
    return world != NULL ? (CR_TC0R(0x426160u, world) & 0xFF) != 0 : 0;
}

static int cr_v2_goes(int index) {
    const unsigned char *r = v2_record(index);
    return r != NULL && r[0x30] != 0 && *(const int *)(r + 0x52C) > 0;
}

static int cr_v2_send(int index) {
    int honor = v2_rand(100) < CR_HONOR_PERCENT;
    ADV_TC1(0x4492A0u, VV2_POOL(), index);
    ADV_TC1(honor ? 0x454890u : 0x4523A0u, VV2_POOL(), index);
    return honor ? CR_ACT_HONOR : CR_ACT_REFLECT;
}

static int cr_v2_feast(void) {
    unsigned char *world = VV2_WORLD();
    int n = CR_TC0R(0x425860u, world), food = *(int *)(world + 0x2EAA4), used;
    used = n > 0 ? CR_FOOD_PER_VILLAGER * n : 0;
    if (used > food) {
        used = food > 0 ? food : 0;
    }
    *(int *)(world + 0x2EAA4) = food - used < 0 ? 0 : food - used;
    return used;
}

static int cr_v2_puzzles(void) {
    unsigned char *world = VV2_WORLD();
    int k;
    if (world == NULL) {
        return 0;
    }
    for (k = 0; k < 16; ++k) {
        if (world[CR_V2_PUZZLES[k]] == 0) {
            return 0;
        }
    }
    return 1;
}

static int cr_v2_finished(int k) {
    return sd_finished(2, k);
}

static void cr_v2_damage(int k, int loss) {
    sd_damage(2, k, loss, NULL, 0);
}

static const cr_game CR_VV2 = {
    2, v2_count, v2_rand, cr_v2_graves, NULL, cr_v2_goes, cr_v2_send, cr_v2_feast,
    cr_v2_puzzles, 3, SD_V2_NAMES, cr_v2_finished, cr_v2_damage, 40
};

/* ---- The Secret City -------------------------------------------------------------------------------------------- */

static const int CR_V3_PUZZLE_DONE_AT[16] = { 1, 1, 5, 700, 1, 1, 1800, 1400, 2, 1, 1, 6, 1, 1, 1, 1 };
#define CR_V3_PROJECTS 0x594990u

static int cr_v3_graves(void) {
    return CR_TC0R(0x454B10u, 0x5973F0u);
}

static int cr_v3_goes(int index) {
    const unsigned char *r = t_record(index);
    return r != NULL && r[0xF10] != 0 && *(const int *)(r + 0xE78) > 0 && r[0xE94] == 0;
}

static int cr_v3_send(int index) {
    unsigned char *r = t_record(index);
    int flag = 0;
    int honor = t_rand(100) < CR_HONOR_PERCENT;
    ADV_TC1(0x460F70u, r, r);
    ((cr_tc2r)(uintptr_t)0x455570u)(r, NULL, honor ? 0xA : 0x16, (int)(uintptr_t)&flag);
    ADV_TC1(0x461BF0u, r, r);
    return honor ? CR_ACT_HONOR : CR_ACT_REFLECT;
}

static int cr_v3_feast(void) {
    int count = 0;
    int food = *t_store(ADV_KIND_FOOD);
    int used;
    ((adv_tc4r)(uintptr_t)0x45D460u)((void *)(uintptr_t)g_manager, NULL, 7, -1, 0, (int)(uintptr_t)&count);
    used = count > 0 ? CR_FOOD_PER_VILLAGER * count : 0;
    ADV_TC1(0x4263F0u, (void *)t_store(ADV_KIND_FOOD), -used);
    return food > used ? used : (food > 0 ? food : 0);
}

static int cr_v3_puzzles(void) {
    int id;
    for (id = 0; id < 16; ++id) {
        if (*(const int *)(uintptr_t)(CR_V3_PROJECTS + 8u * (unsigned int)id) < CR_V3_PUZZLE_DONE_AT[id]) {
            return 0;
        }
    }
    return 1;
}

static int cr_v3_finished(int k) {
    return sd_finished(3, k);
}

static void cr_v3_damage(int k, int loss) {
    sd_damage(3, k, loss, NULL, 0);
}

/* ---- The Tree of Life and New Believers ------------------------------------------------------------------------ */

static const int CR_V5_PUZZLES[11] = { 2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15 };   /* the Puzzles screen's */

static int cr_v45_finished(int k) {
    return sd_finished(g_tg->game, k);
}

static void cr_v45_damage(int k, int loss) {
    sd_damage(g_tg->game, k, loss, t_record, g_records);
}

static int cr_v4_puzzles(void) {
    int id;
    for (id = 0; id < 16; ++id) {
        if (!sd_late_done(&SD_LATE[0], id)) {
            return 0;
        }
    }
    return 1;
}

static int cr_v5_puzzles(void) {
    int k;
    for (k = 0; k < 11; ++k) {
        if (!sd_late_done(&SD_LATE[1], CR_V5_PUZZLES[k])) {
            return 0;
        }
    }
    return 1;
}

static int cr_v4_graves(void) {
    return CR_TC0R(0x45D670u, 0x5025C8u);
}

static int cr_v4_goes(int index) {
    const unsigned char *r = t_record(index);
    return r != NULL && r[0x1CC4] != 0 && r[0x1CC7] == 0 && *(const int *)(r + 0x1C40) > 0;
}

static int cr_v4_send(int index) {
    unsigned char *r = t_record(index);
    int flag = 0;
    ADV_TC0(0x468C60u, r);
    ((cr_tc2r)(uintptr_t)0x45DEC0u)(r, NULL, 9, (int)(uintptr_t)&flag);
    ADV_TC0(0x46A030u, r);
    return CR_ACT_HONOR;
}

static int cr_feast_late(unsigned int count_routine, unsigned int writer) {
    int n = CR_TC0R(count_routine, g_manager);
    int food = *t_store(ADV_KIND_FOOD);
    int used = n > 0 ? CR_FOOD_PER_VILLAGER * n : 0;
    if (used > food) {
        used = food > 0 ? food : 0;
    }
    if (used > 0) {
        ADV_TC1(writer, (void *)t_store(ADV_KIND_FOOD), -used);
    }
    return used;
}

static int cr_v4_feast(void) {
    return cr_feast_late(0x467610u, 0x41D920u);
}

/* New Believers: "Memorial Actions Can Also Occur at the Heathen Hovel" installed -- its exact bytes. */
static const unsigned char CR_HOVEL_REGISTRATION[5] = { 0x68, 0x61, 0x4B, 0x49, 0x00 };
static const unsigned char CR_HOVEL_CHOOSER[5] = { 0xE8, 0x30, 0x9A, 0x02, 0x00 };
static const unsigned char CR_HOVEL_CAVE_A[125] = {
    0x51, 0x6A, 0x19, 0xB9, 0x08, 0xE0, 0x51, 0x00, 0xE8, 0x33, 0x63, 0xFA, 0xFF, 0x84, 0xC0, 0x74, 0x0E, 0x6A, 0x64,
    0xE8, 0x08, 0xEB, 0xF6, 0xFF, 0x59, 0x83, 0xF8, 0x19, 0x0F, 0x9C, 0xC0, 0x59, 0xC3, 0xE8, 0xDA, 0xFF, 0xFF, 0xFF,
    0x84, 0xC0, 0x75, 0x05, 0xE9, 0x21, 0x33, 0xFC, 0xFF, 0xFF, 0x74, 0x24, 0x04, 0xE8, 0x18, 0x33, 0xFC, 0xFF, 0x59,
    0xC3, 0xE8, 0xC1, 0xFF, 0xFF, 0xFF, 0x84, 0xC0, 0x75, 0x05, 0xE9, 0xF8, 0x09, 0xFD, 0xFF, 0xFF, 0x74, 0x24, 0x08,
    0xFF, 0x74, 0x24, 0x08, 0xE8, 0xEB, 0x09, 0xFD, 0xFF, 0xC2, 0x08, 0x00, 0x81, 0x7C, 0x24, 0x2C, 0x95, 0x4B, 0x49,
    0x00, 0x0F, 0x85, 0x1A, 0xF9, 0xFD, 0xFF, 0xE8, 0xF5, 0x01, 0x00, 0x00, 0xFF, 0x74, 0x24, 0x0C, 0xFF, 0x74, 0x24,
    0x0C, 0x52, 0x50, 0xE8, 0xE6, 0xF9, 0xFD, 0xFF, 0xC2, 0x0C, 0x00 };
static const unsigned char CR_HOVEL_CAVE_B[65] = {
    0x51, 0x6A, 0x61, 0xE8, 0xB8, 0xE8, 0xF6, 0xFF, 0x89, 0x04, 0x24, 0x6A, 0x19, 0xE8, 0xAE, 0xE8, 0xF6, 0xFF, 0x5A,
    0x8D, 0x90, 0x28, 0x06, 0x00, 0x00, 0x58, 0x05, 0x80, 0x08, 0x00, 0x00, 0x59, 0xC3, 0x81, 0x7C, 0x24, 0x1C, 0x78,
    0x4B, 0x49, 0x00, 0x0F, 0x85, 0xD1, 0xF7, 0xFD, 0xFF, 0xE8, 0xCC, 0xFF, 0xFF, 0xFF, 0x89, 0x44, 0x24, 0x04, 0x89,
    0x54, 0x24, 0x08, 0xE9, 0xBF, 0xF7, 0xFD, 0xFF };
#define CR_HOVEL_HONOR 0x494B88u          /* the patch's Honoring the Dead start past its roll (thiscall: 17, &flag) */
#define CR_HOVEL_REFLECT 0x494B6Fu        /* the patch's Reflecting wrapper past its roll (cdecl: the villager) */

static int cr_hovel_patch(void) {
    return vvfp_site_holds(0x46409Eu, CR_HOVEL_REGISTRATION, 5) && vvfp_site_holds(0x46B145u, CR_HOVEL_CHOOSER, 5)
        && vvfp_site_holds(0x494B40u, CR_HOVEL_CAVE_A, (int)sizeof CR_HOVEL_CAVE_A)
        && vvfp_site_holds(0x494DA0u, CR_HOVEL_CAVE_B, (int)sizeof CR_HOVEL_CAVE_B);
}

static int cr_v5_graves(void) {
    return CR_TC0R(0x464E90u, 0x5481A8u);
}

static int cr_v5_heathens_done(void) {
    return (CR_TC1R(0x43AE80u, 0x51E008u, 25) & 0xFF) != 0;
}

static int cr_v5_goes(int index) {
    const unsigned char *r = t_record(index);
    return r != NULL && r[0x1CD4] != 0 && r[0x1CE1] == 0 && *(const int *)(r + 0x1C40) > 0 && r[0x1CEC] == 0;
}

static int cr_v5_send(int index) {
    unsigned char *r = t_record(index);
    int flag = 0;
    ADV_TC0(0x473440u, r);
    if (cr_hovel_patch() && t_rand(100) < CR_HOVEL_PERCENT) {
        if (t_rand(100) < CR_HONOR_PERCENT) {
            ((cr_tc2r)(uintptr_t)CR_HOVEL_HONOR)(r, NULL, 17, (int)(uintptr_t)&flag);
            return CR_ACT_HOVEL_HONOR;
        }
        *(int *)(r + 0x1D10) = 29;
        ((cr_cdecl1)(uintptr_t)CR_HOVEL_REFLECT)(r);
        return CR_ACT_HOVEL_REFLECT;
    }
    ((cr_tc2r)(uintptr_t)0x465580u)(r, NULL, 17, (int)(uintptr_t)&flag);
    return CR_ACT_HONOR;
}

static int cr_v5_feast(void) {
    return cr_feast_late(0x4713F0u, 0x41EB40u);
}

static const cr_game CR_VV3 = {
    3, t_count, t_rand, cr_v3_graves, NULL, cr_v3_goes, cr_v3_send, cr_v3_feast,
    cr_v3_puzzles, 4, SD_V3_NAMES, cr_v3_finished, cr_v3_damage, 0
};
static const cr_game CR_VV4 = {
    4, t_count, t_rand, cr_v4_graves, NULL, cr_v4_goes, cr_v4_send, cr_v4_feast,
    cr_v4_puzzles, 7, SD_V45_NAMES, cr_v45_finished, cr_v45_damage, 0
};
static const cr_game CR_VV5 = {
    5, t_count, t_rand, cr_v5_graves, cr_v5_heathens_done, cr_v5_goes, cr_v5_send, cr_v5_feast,
    cr_v5_puzzles, 5, SD_V45_NAMES, cr_v45_finished, cr_v45_damage, 0
};

static const cr_game *g_cr;              /* the installed game's, NULL when not installed */

/* ---- A New Home and The Lost Children: the island events' own draw and popup -----------------------------------

   Their single-result island events are drawn by the event's chooser (A New Home 0x428470: rand(15), drawn again
   while the case's condition fails; The Lost Children 0x434570: up to ten draws of rand(28), else Blessings Day),
   called by the event's constructor (0x4286B0 / 0x4348E0), which the trigger calls for that family (A New Home
   0x423A06, type 2; The Lost Children 0x42F0F7, type 2), and the chooser writes the event's text into the event's
   own buffer (+0x277F, 0x270F bytes: the title line, three blank lines, the words) which the game's own popup then
   shows (the game's modal loop, 0x401AB0 / 0x401AD0).

   THE DUE EVENT.  These events never take a share of the chooser's draw (the owner's rule: stock island event
   chances never change): they come only when they are due -- picked with Pick Island Event, or drawn by Story /
   Cheat Upgrades' separate rare roll (story_collection.inc; mie_pick.inc mp_due_cr).  Only then, for that one
   constructor call, the chooser's draw (A New Home 0x4284DB, The Lost Children 0x434607 -- Story / Cheat Upgrades'
   sites too) is pointed here and put back before the constructor returns, chaining onto whatever it held (the
   game's rand, or Story's own roll): its first draw is the due event's case, past the stock cases, and any later
   draw is the inner roll with the stock bound.  With nothing due the chooser runs on the stock bytes.  The case past
   the stock cases reaches the chooser's own "not a case" branch (A New Home 0x4284E7 `cmp edi, 0xE; ja`, The Lost
   Children 0x43462C `ja 0x434824`), which comes here: the event's text is written into the buffer, its effects made
   and its log entry handed over, and the chooser leaves through its own ending (0x428630 / 0x434842), as after a
   case.

   EXE SITES (the minimal redirect, the owner's rule "DLLs and outside files only"): the trigger's one `call` of the
   constructor for this family (5 bytes) and the chooser's one "not a case" branch (5 / 6 bytes).  Story / Cheat
   Upgrades' sites (0x4284DB, 0x4284EC, 0x428777; 0x434607, 0x434617, 0x4349B2) are never written for good: it
   checks their stock bytes when it installs, later, from the Origins companion. */

typedef int (__cdecl *cr_roll_fn)(int bound);

static unsigned int g_cr_draw_site;      /* the chooser's draw call */
static unsigned int g_cr_stock_rand;
static unsigned int g_cr_cases;          /* the stock cases: 15 / 28 */
static cr_roll_fn g_cr_inner;
static int g_cr_can[CR_EVENTS];
static int g_cr_listed;                  /* 1 while the due event's case may be answered, else 0 */
static int g_cr_picked;                  /* Pick Island Event's event: the draw's next answer is its case, once */
static int g_cr_result;

static int __cdecl cr_draw(int bound) {
    cr_roll_fn inner = g_cr_inner != NULL ? g_cr_inner : (cr_roll_fn)(uintptr_t)g_cr_stock_rand;
    if (g_cr_picked) {
        g_cr_picked = 0;                 /* Pick Island Event's: its case, once (mie_pick.inc) */
        return (int)g_cr_cases;
    }
    return inner(bound);
}

static int cr_from_story(unsigned int target) {
    HMODULE story = GetModuleHandleA("VVFP Story Upgrades.dll");
    MEMORY_BASIC_INFORMATION info;
    return story != NULL && VirtualQuery((const void *)(uintptr_t)target, &info, sizeof info) == sizeof info
        && info.AllocationBase == (void *)story;
}

/* The trigger's constructor call: while one of these events is due, the draw redirected for this one call (its
   first answer the due event's case), then put back. */
static void cr_v12_construct(void *event, int type, int magnitude, unsigned int ctor) {
    static vvfp_site_write w;
    unsigned char held[5];
    int widened = 0;
    adv_log_reset();                     /* an island event is drawn: whatever was ours is over */
    g_cr_listed = 0;
    g_cr_picked = 0;
    __try {
        int picked = g_cr != NULL ? mp_due_cr(g_cr->game) : -1;
        if (picked >= 0 && !cr_possible_safe(g_cr, picked)) {
            mp_done(g_cr->game, 0);      /* Pick Island Event's, no longer possible: the game's own draw */
            picked = -1;
        }
        if (g_cr != NULL && picked >= 0) {
            g_cr_can[0] = picked;
            memcpy(held, (const void *)(uintptr_t)g_cr_draw_site, sizeof held);
            if (held[0] == 0xE8) {
                unsigned int target = g_cr_draw_site + 5u + *(const unsigned int *)(held + 1);
                if (target == g_cr_stock_rand || cr_from_story(target)) {
                    g_cr_inner = (cr_roll_fn)(uintptr_t)target;
                    vvfp_site_branch(&w, g_cr_draw_site, 5, held, 0xE8, (const void *)cr_draw);
                    widened = vvfp_install_sites(&w, 1);
                    g_cr_listed = widened;
                    g_cr_picked = widened;
                }
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        widened = 0;
        g_cr_listed = 0;
    }
    ((adv_tc2)(uintptr_t)ctor)(event, NULL, type, magnitude);
    if (widened) {
        __try {
            unsigned char ours[5];
            memcpy(ours, w.bytes, sizeof ours);
            vvfp_site_bytes(&w, g_cr_draw_site, 5, ours, held);
            (void)vvfp_install_sites(&w, 1);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
    g_cr_listed = 0;
}

static void __fastcall cr_v1_construct(void *event, void *unused, int type, int magnitude) {
    (void)unused;
    cr_v12_construct(event, type, magnitude, 0x4286B0u);
}

static void __fastcall cr_v2_construct(void *event, void *unused, int type, int magnitude) {
    (void)unused;
    cr_v12_construct(event, type, magnitude, 0x4348E0u);
}

/* The event's text as A New Home's and The Lost Children's single-result popups show theirs: the title centred by
   spaces, three blank lines, the words broken into lines (the popup breaks only at '\n'). */
static void cr_v12_text(char *out, int cap) {
    static char wrapped[ADV_PAGE_BYTES];
    int pad = (46 - adv_width_of(cr_title_text, adv_len(cr_title_text))) / 2, i;
    out[0] = '\0';
    for (i = 0; i < pad && i < 40; ++i) {
        adv_cat(out, cap, " ");
    }
    adv_cat(out, cap, cr_title_text);
    adv_cat(out, cap, "\n\n\n\n");
    adv_wrap(cr_body_text, g_cr->text_width, wrapped, sizeof wrapped);
    adv_cat(out, cap, wrapped);
    adv_cat(out, cap, "\n");
}

/* A draw past the stock cases: 1 when it was one of ours (the event shown), 0 to draw again. */
static int __cdecl cr_v12_case(int draw, unsigned char *event) {
    int k = draw - (int)g_cr_cases;
    int handled = 0;
    __try {
        if (g_cr != NULL && g_cr_listed > 0 && k >= 0 && k < g_cr_listed && event != NULL) {
            int which = g_cr_can[k];
            g_cr_listed = 0;                 /* drawn: the rest of this run is the stock draw's */
            if (mp_due_cr(g_cr->game) == which) {
                mp_done(g_cr->game, 1);      /* Pick Island Event's: it came */
            }
            cr_happen(g_cr, which);
            cr_v12_text((char *)event + 0x277F, 0x270F);
            handled = 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        handled = 0;
    }
    return handled;
}

/* jmp from A New Home's chooser 0x4284E7 `cmp edi, 0xE; ja 0x4284D6` (edi the draw, ebp the event). */
__declspec(naked) static void cr_v1_case_stub(void) {
    __asm {
        cmp edi, 0xE
        ja past
        push 0x4284EC
        ret
    past:
        pushad
        push ebp
        push edi
        call cr_v12_case
        add esp, 8
        mov dword ptr [g_cr_result], eax
        popad
        cmp dword ptr [g_cr_result], 0
        jne ours
        push 0x4284D6
        ret
    ours:
        push 0x428630
        ret
    }
}

/* jmp from The Lost Children's chooser 0x43462C `ja 0x434824` after `cmp ebp, 0x1B` (ebp the draw, edi the event). */
__declspec(naked) static void cr_v2_case_stub(void) {
    __asm {
        cmp ebp, 0x1B
        ja past
        push 0x434632
        ret
    past:
        pushad
        push edi
        push ebp
        call cr_v12_case
        add esp, 8
        mov dword ptr [g_cr_result], eax
        popad
        cmp dword ptr [g_cr_result], 0
        jne ours
        push 0x434824
        ret
    ours:
        push 0x434842
        ret
    }
}

/* The two sites, written with the Adventurer's (adv_vv1.inc / adv_vv2.inc v1_install / v2_install): all or none. */
static void cr_v1_sites(vvfp_site_write *w) {
    static const unsigned char CALL_STOCK[5] = { 0xE8, 0xA5, 0x4C, 0x00, 0x00 };     /* call 0x4286B0 */
    static const unsigned char CASE_STOCK[5] = { 0x83, 0xFF, 0x0E, 0x77, 0xEA };     /* cmp edi, 0xE; ja 0x4284D6 */
    g_cr_draw_site = 0x4284DBu;
    g_cr_stock_rand = 0x402F10u;
    g_cr_cases = 15;
    vvfp_site_branch(&w[0], 0x423A06u, 5, CALL_STOCK, 0xE8, (const void *)cr_v1_construct);
    vvfp_site_branch(&w[1], 0x4284E7u, 5, CASE_STOCK, 0xE9, (const void *)cr_v1_case_stub);
}

static void cr_v2_sites(vvfp_site_write *w) {
    static const unsigned char CALL_STOCK[5] = { 0xE8, 0xE4, 0x57, 0x00, 0x00 };     /* call 0x4348E0 */
    static const unsigned char CASE_STOCK[6] = { 0x0F, 0x87, 0xF2, 0x01, 0x00, 0x00 }; /* ja 0x434824 */
    g_cr_draw_site = 0x434607u;
    g_cr_stock_rand = 0x4031A0u;
    g_cr_cases = 28;
    vvfp_site_branch(&w[0], 0x42F0F7u, 5, CALL_STOCK, 0xE8, (const void *)cr_v2_construct);
    vvfp_site_branch(&w[1], 0x43462Cu, 6, CASE_STOCK, 0xE9, (const void *)cr_v2_case_stub);
}

/* Every site written: the events exist. */
static void cr_v12_ready(int game) {
    g_cr = game == 1 ? &CR_VV1 : &CR_VV2;
}

/* ---- The Secret City, The Tree of Life, New Believers: an event object of their own ----------------------------

   Each event is one more object in the table's slot 0 (adv_vv345.inc THE EVENT: t_register, its own entry in t_list's
   draw), built from a copy of a stock SIMPLE event's virtual table -- The Secret City's The Fog 0x47E600, The Tree of
   Life's event base 0x48C4EC, New Believers' Blessings Day 0x49762C, as Custom Island Events' plain event is
   (story_objects.inc) -- so the game's own presenter shows it with its one OK: +0x04 the condition, +0x08 the title
   (asked as the dialog is built: the event happens here, once -- only inside the presenter's constructor call, the
   site adv_vv345.inc already holds), +0x0C the words, +0x30 the apply (OK: our strings given back) and +0x38 the
   prepare (nothing), +0x00 the deleter (nothing: the objects are this DLL's). */

static unsigned int g_cr_vtable[17];
static adv_object g_cr_objects[CR_EVENTS];

static int cr_which(const void *self) {
    return self == (const void *)&g_cr_objects[CR_RUMBLINGS] ? CR_RUMBLINGS : CR_REMEMBRANCE;
}

static char __fastcall cr_o_condition(void *self, void *unused) {
    (void)unused;
    return (char)cr_possible_safe(g_cr, cr_which(self));
}

static int __fastcall cr_o_title(void *self, void *unused) {
    (void)unused;
    __try {
        if (g_ctor_dialog != NULL && !g_cr_made && g_cr != NULL) {
            g_cr_made = 1;
            g_ev = NULL;
            cr_happen(g_cr, cr_which(self));
        } else if (cr.g == NULL || cr.which != cr_which(self)) {
            cr_compose(cr_which(self));
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    adv_copy(g_title, sizeof g_title, cr_title_text);
    t_strings_in();
    return g_tg->title_id;
}

static int __fastcall cr_o_body(void *self, void *unused) {
    (void)self; (void)unused;
    return t_text_id(cr_body_text);
}

static void __fastcall cr_o_apply(void *self, void *unused) {
    (void)self; (void)unused;
    t_strings_out();
}

static void __fastcall cr_o_nothing(void *self, void *unused) {
    (void)self; (void)unused;
}

static int cr_remembrance_listable(void) {
    return cr_possible_safe(g_cr, CR_REMEMBRANCE);
}

static int cr_rumblings_listable(void) {
    return cr_possible_safe(g_cr, CR_RUMBLINGS);
}

static void cr_t_install(int game) {
    static const unsigned int SIMPLE[3] = { 0x47E600u, 0x48C4ECu, 0x49762Cu };
    static const int SLOTS[6] = { 0, 1, 2, 3, 12, 14 };
    void *functions[6];
    unsigned int source = SIMPLE[game - 3];
    int i;
    if (!vvfp_site_holds(source - 4u, (const unsigned char *)(uintptr_t)(source - 4u), (int)sizeof g_cr_vtable)) {
        return;
    }
    memcpy(g_cr_vtable, (const void *)(uintptr_t)(source - 4u), sizeof g_cr_vtable);
    functions[0] = (void *)o_delete;
    functions[1] = (void *)cr_o_condition;
    functions[2] = (void *)cr_o_title;
    functions[3] = (void *)cr_o_body;
    functions[4] = (void *)cr_o_apply;
    functions[5] = (void *)cr_o_nothing;
    for (i = 0; i < 6; ++i) {
        g_cr_vtable[1 + SLOTS[i]] = (unsigned int)(uintptr_t)functions[i];
    }
    for (i = 0; i < CR_EVENTS; ++i) {
        memset(&g_cr_objects[i], 0, sizeof g_cr_objects[i]);
        g_cr_objects[i].vtable = &g_cr_vtable[1];
        g_cr_objects[i].amount = -1;
    }
    g_cr = game == 3 ? &CR_VV3 : (game == 4 ? &CR_VV4 : &CR_VV5);
    t_register(&g_cr_objects[CR_REMEMBRANCE], NULL, cr_remembrance_listable, NULL);
    t_register(&g_cr_objects[CR_RUMBLINGS], NULL, cr_rumblings_listable, NULL);
}

/* ---- For the tests ------------------------------------------------------------------------------------------- */

/* Whether `which` (0 The Remembrance Ceremony, 1 The Rumblings) can happen now. */
int __stdcall VvfpCeremonyPossible(int which) {
    return which >= 0 && which < CR_EVENTS ? cr_possible_safe(g_cr, which) : 0;
}

/* The last event's state: out[0] which (-1 none), [1] villagers sent, [2] at the hovel, [3] food used, [4] finished
   structures, [5] one picked because none was drawn, [6] the effects made, [7..14] each structure's loss (0 not
   damaged).  Returns 15. */
int __stdcall VvfpCeremonyState(int *out) {
    int k;
    if (out == NULL) {
        return 0;
    }
    out[0] = cr.g != NULL ? cr.which : -1;
    out[1] = cr.sent; out[2] = cr.hovel; out[3] = cr.food; out[4] = cr.candidates; out[5] = cr.forced;
    out[6] = cr.effects_made;
    for (k = 0; k < CR_MAX_STRUCTURES; ++k) {
        out[7 + k] = cr.damaged[k];
    }
    return 15;
}

/* What record `index` was sent to do (CR_ACT_*: 0 nothing, 1 honoring, 2 reflecting, 3 / 4 the same at the hovel). */
int __stdcall VvfpCeremonyAct(int index) {
    return index >= 0 && index < 256 ? cr.acts[index] : 0;
}

/* The event objects of the later three games (0 / 1), NULL elsewhere. */
void *__stdcall VvfpCeremonyObject(int which) {
    return g_cr != NULL && g_cr->game >= 3 && which >= 0 && which < CR_EVENTS ? (void *)&g_cr_objects[which] : NULL;
}

/* New Believers: whether the hovel patch's bytes are in. */
int __stdcall VvfpCeremonyHovelPatch(void) {
    int in = 0;
    __try {
        in = g_cr != NULL && g_cr->game == 5 && cr_hovel_patch();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        in = 0;
    }
    return in;
}
