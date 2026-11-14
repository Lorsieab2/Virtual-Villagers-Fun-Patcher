/* Pick Island Event (the Story / Cheat Upgrades patch) for More Island Events.  Included by
   vvfp_more_island_events.c after every game's adapter.

   The owner (v1.35.97): Pick Island Event can pick every More Island Events event of the game played, only when this
   patch is installed, each only when its own requirements hold -- and the owner's protected villagers are never
   picked unless the owner made an exception for that event -- or the purchase is refused in plain words ("The Climb
   needs a villager of 18 or more who is at least a Trainee in Research.").  Both rules are the event's own: what it
   needs now is the very test its draw uses (adv_possible, cave_possible, climb_possible, ts_listable, dv_listable,
   each over the game's eligible villagers, adv_is_protected included), plus A New Home's and The Lost Children's
   "never the village's first island events" (adv_vv1.inc v1_choose, adv_vv2.inc v2_keep).

   MIE_PICKS is the registry: ONE LINE PER EVENT, in the order the Pick Island Event list shows them after the game's
   own events.  A new event joins with one line naming its games, its title, its test, what it needs (plain words),
   one sentence for the list, and how its game's draw knows it (its adv_flow for A New Home / The Lost Children /
   two-choice events, its object for The Secret City .. New Believers).

   DELIVERY.  The Story companion arms the pick as for any picked event (the island event due, the same lock, the
   ten-minute lapse) and asks the game's chooser for the family the event is drawn in; each game's draw here then asks
   it which event is due (VvfpStoryMoreEventDue) and takes that one instead of drawing:
     A New Home      the encounter setup's draw (adv_vv1.inc v1_choose): the event begun, the Story told (Done);
     The Lost Children  family A's widened draw (adv_vv2.inc v2_draw): the event's own draw number, once, the Story
                     told; its own keep test still runs;
     The Secret City, The Tree of Life, New Believers  the selector's list (adv_vv345.inc t_list): the event's object
                     in slot 0, which the Story's own pick (slot 0) then presents when the object's condition holds.
   A pick whose event can no longer happen when it is due is refused as any picked event is: the game's own choice
   runs and the next Pick Island Event says why.  No executable byte is written for any of this. */

#define MIE_IN(g) (1u << (g))
#define MIE_ALL_GAMES (MIE_IN(1) | MIE_IN(2) | MIE_IN(3) | MIE_IN(4) | MIE_IN(5))

typedef struct {
    unsigned int games;                        /* MIE_IN(game) for each game it is in */
    const char *key;                           /* its translation rows' stem part */
    void (*title)(char *out, int cap);         /* its title, in the player's language */
    int (*possible)(void);                     /* its own requirements hold now */
    const char *needs;                         /* what it needs, in plain words ("... needs <this>.") */
    const char *description;                   /* one sentence for the list */
    const adv_flow *flow;                      /* A New Home / The Lost Children: its flow in the draw */
    adv_object *object;                        /* The Secret City .. New Believers: its object in slot 0 */
    int cr;                                    /* 1 The Remembrance Ceremony, 2 The Rumblings (ceremony_games.inc):
                                                  single-result events -- A New Home's and The Lost Children's
                                                  island events, not their two-choice ones */
} mie_pick;

static int mp_adventurer(void) { return adv_possible(g_adv_game); }
static int mp_cave(void) { return cave_possible(g_adv_game); }
static int mp_climb(void) { return climb_possible(g_adv_game); }
static void mp_ts_title(char *out, int cap) { ts_piece(out, cap, TS_TITLE, 0); }
static void mp_rc_title(char *out, int cap) { cr_piece(out, cap, RC_TITLE); }
static void mp_rb_title(char *out, int cap) { cr_piece(out, cap, RB_TITLE); }
static int mp_remembrance(void) { return cr_possible_safe(g_cr, CR_REMEMBRANCE); }
static int mp_rumblings(void) { return cr_possible_safe(g_cr, CR_RUMBLINGS); }

static const mie_pick MIE_PICKS[] = {
    { MIE_ALL_GAMES, "aspiring_adventurer", adv_flow_title, mp_adventurer,
      "two villagers of 14 or more who may go (not nursing a baby, and none the game keeps out of island events)",
      "A villager sees something glinting off the safe path: investigate it or stay on the path.",
      &ADV_FLOW, &g_object },
    { MIE_IN(1), "cave_explorers", cave_flow_title, mp_cave,
      "The Cave puzzle solved, and two villagers of 18 or more, at most 5 years apart, who may go",
      "Two friends wonder what the cave hides, and decide whether to explore it.",
      &CAVE_FLOW, NULL },
    { MIE_IN(2), "the_climb", climb_flow_title, mp_climb,
      "a villager of 18 or more who is at least a Trainee in Research and may go",
      "A villager wants to climb the Great Falls: follow the plan, or the scientists' advice.",
      &CLIMB_FLOW, NULL },
    { MIE_IN(3), "troubling_signs", mp_ts_title, ts_listable,
      "the Tribal Chief wearing the chief's robe, a population of 61 or more, nine other villagers who may be "
      "picked, and a name for the tribe",
      "The Tribal Chief asks one of four advisors what the troubling signs mean.",
      NULL, &g_ts_object },
    { MIE_IN(3), "diving_for_treasure", dv_flow_title, dv_listable,
      "two villagers of 18 or more who may be picked",
      "A villager wants to dive for treasure: swim deeper, or better not.",
      &DV_FLOW, &g_dv_object },
    { MIE_IN(4), "playful_dolphins", dp_flow_title, dp_listable,
      "two villagers of 14 or more who may be picked",
      "A villager sees dolphins playing: swim towards them, or hang back.",
      &DP_FLOW, &g_dp_object },
    { MIE_IN(4), "mysterious_mask", mk_flow_title, mk_listable,
      "a population of 61 or more, two to four children under 14 and five villagers of 18 or more who may be picked",
      "Children find a strange mask, and the village decides what to do about it.",
      &MK_FLOW, &g_mk_object },
    { MIE_IN(1) | MIE_IN(2) | MIE_IN(3) | MIE_IN(4), "remembrance_ceremony", mp_rc_title, mp_remembrance,
      "at least one grave",
      "The whole village honors the dead, and the feast uses food.",
      NULL, &g_cr_objects[CR_REMEMBRANCE], 1 },
    { MIE_IN(5), "remembrance_ceremony_nb", mp_rc_title, mp_remembrance,
      "at least one grave and The Last Heathen achieved (every Heathen converted)",
      "The whole village honors the dead, and the feast uses food.",
      NULL, &g_cr_objects[CR_REMEMBRANCE], 1 },
    { MIE_ALL_GAMES, "the_rumblings", mp_rb_title, mp_rumblings,
      "every puzzle solved and a finished hut",
      "The ground shakes and damages some of the village's huts.",
      NULL, &g_cr_objects[CR_RUMBLINGS], 2 },
};
#define MIE_PICK_COUNT ((int)(sizeof MIE_PICKS / sizeof MIE_PICKS[0]))

/* Whether entry `k` is an event of the installed game. */
static const mie_pick *mp_entry(int k) {
    int game = g_adv_game != NULL ? g_adv_game->game : 0;
    if (k < 0 || k >= MIE_PICK_COUNT || game < 1 || game > 5 || (MIE_PICKS[k].games & MIE_IN(game)) == 0) {
        return NULL;
    }
    return &MIE_PICKS[k];
}

/* A New Home's and The Lost Children's rule for every event of theirs: never the village's first island events. */
static int mp_past_first_events(int game) {
    if (game == 1) {
        return VV1_WORLD() != NULL && *(int *)(VV1_WORLD() + 0x9E40) > 1;
    }
    if (game == 2) {
        return VV2_WORLD() != NULL && *(int *)(VV2_WORLD() + 0x2E51C) > 1;
    }
    return 1;
}

static int mp_possible(const mie_pick *p) {
    int possible = 0;
    __try {
        possible = p != NULL && mp_past_first_events(g_adv_game->game) && p->possible();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        possible = 0;
    }
    return possible;
}

/* ---- The Story companion's side ---------------------------------------------------------------------------- */

typedef int (__stdcall *mp_due_fn)(int game);
typedef void (__stdcall *mp_done_fn)(int game, int delivered);

static FARPROC mp_story(const char *name) {
    HMODULE story = GetModuleHandleA("VVFP Story Upgrades.dll");
    return story != NULL ? GetProcAddress(story, name) : NULL;
}

/* The entry of the event Pick Island Event has due in `game` now, or NULL. */
static const mie_pick *mp_due(int game) {
    mp_due_fn due = (mp_due_fn)(void *)mp_story("VvfpStoryMoreEventDue");
    int k = due != NULL ? due(game) : -1;
    return mp_entry(k);
}

/* Tells the Story companion the due pick was taken: delivered (1) or refused (0). */
static void mp_done(int game, int delivered) {
    mp_done_fn done = (mp_done_fn)(void *)mp_story("VvfpStoryMoreEventDone");
    if (done != NULL) {
        done(game, delivered);
    }
}

static const adv_flow *mp_due_flow(int game) {
    const mie_pick *p = mp_due(game);
    return p != NULL ? p->flow : NULL;
}

static adv_object *mp_due_object(int game) {
    const mie_pick *p = mp_due(game);
    return p != NULL ? p->object : NULL;
}

/* A New Home / The Lost Children: the single-result event due (CR_REMEMBRANCE / CR_RUMBLINGS), or -1. */
static int mp_due_cr(int game) {
    const mie_pick *p = mp_due(game);
    return p != NULL && p->cr > 0 ? p->cr - 1 : -1;
}

/* ---- Exports ------------------------------------------------------------------------------------------------- */

/* "vvfp.more_island_events/mie_pick.<key><field>" (kernel32 only: no wsprintf in this DLL). */
static void mp_stem(char *out, int cap, const char *key, const char *field) {
    lstrcpynA(out, "vvfp.more_island_events/mie_pick.", cap);
    adv_cat(out, cap, key);
    adv_cat(out, cap, field);
}

/* Whether entry `k` is a single-result event (The Remembrance Ceremony, The Rumblings): Pick Island Event steers A
   New Home's and The Lost Children's chooser to their single-result island events for it, not the two-choice ones.
   1 / 0; -1 when it is not an event of the game played. */
int __stdcall VvfpMoreIslandEventsPickSingle(int k) {
    const mie_pick *p = mp_entry(k);
    return p == NULL ? -1 : (p->cr > 0);
}

/* The registry's size (every game's entries; VvfpMoreIslandEventsPickInfo says which are in the game played). */
int __stdcall VvfpMoreIslandEventsPickCount(void) {
    return g_adv_game != NULL ? MIE_PICK_COUNT : 0;
}

/* Entry `k` for the Pick Island Event list: -1 when it is not an event of the game played; otherwise its title,
   one sentence about it and what it needs (each in the player's language, `cap` bytes each), and 1 when it can
   happen now, 0 when not. */
int __stdcall VvfpMoreIslandEventsPickInfo(int k, char *title, char *description, char *needs, int cap) {
    const mie_pick *p = mp_entry(k);
    char stem[96];
    if (p == NULL || title == NULL || description == NULL || needs == NULL || cap <= 0) {
        return -1;
    }
    title[0] = '\0';
    __try {
        p->title(title, cap);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        title[0] = '\0';
    }
    mp_stem(stem, sizeof stem, p->key, ".description");
    lstrcpynA(description, vvfp_tr(stem, p->description, (unsigned int)cap), cap);
    mp_stem(stem, sizeof stem, p->key, ".needs");
    lstrcpynA(needs, vvfp_tr(stem, p->needs, (unsigned int)cap), cap);
    if (!mp_past_first_events(g_adv_game->game)) {
        lstrcpynA(needs,
                  vvfp_tr("vvfp.more_island_events/mie_pick.first_events",
                          "the village's first island events to have happened", (unsigned int)cap),
                  cap);
    }
    return mp_possible(p);
}
