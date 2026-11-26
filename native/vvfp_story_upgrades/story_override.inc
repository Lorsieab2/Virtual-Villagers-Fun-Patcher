/* Pick Island Event: the override.  Included by vvfp_story_upgrades.c before story_outcomes_ui.inc.

   The owner (2026-11-25, all five games): "would be nice to have an override toggle" -- "just put a warning
   message for the override toggle/button" -- "it safely uses the available people in the village/game etc" --
   "none of the usual requirements should apply, unless it's literally technically impossible (population counter
   above the max 90-whatever regardless of population huts etc)".

   THE TOGGLE.  The picker (story_outcomes_ui.inc) has an "Override" checkbox, off each time it opens; ticking it
   asks first (a warning, Cancel the default).  With it ticked, an event whose own condition fails can be picked when
   its override entry (story_tables.h VV<N>_OV_EVENTS, from scripts/story_island_outcomes.py OVERRIDE) allows it and
   what is technically needed is there; the list marks it "(only with the override)".  Everything else is as
   without the toggle.

   WHAT AN ENTRY DOES.
   * pass (A New Home, The Lost Children): the event's own condition is passed for its one roll, as an unlock is
     (story_vv1.inc vv1_event_roll, story_vv2.inc vv2_event_roll).  What every island event needs -- a living adult,
     and a new village's first island event being an encounter / a two-choice event -- still holds; so does any
     villager the event's own code looks for (those events have no entry).
   * cast (The Secret City, The Tree of Life, New Believers): the event's own condition still runs first
     (choose_from_table) and every villager it picks is kept.  A field it left empty -- +4 the villager the event is
     about, +0xC its second villager -- is filled with a living villager of the kind that condition picks, or, when
     the village has none of that kind, the nearest kind it has (OV_FALLBACK; a role the event's text gives a sex or
     an adult's part never falls back to another sex or to a child).  Never a dead, absent or (New Believers)
     Heathen villager, except in a part the event itself gives a Heathen -- and then only an ordinary Heathen (never
     a puzzle's, never sick).  The two parts are never the same villager.
   * flag: the condition's own roll of the event's variant (+0x10), made by the companion when the condition failed
     before making it.
   * room: the villager records the event can fill.  The game's room test (its population cap and the housing /
     collection gates) is not asked: the village's free records -- the real limit -- must hold that many.
   * refuse: the event can not be forced safely; the picker says why.

   Nothing here runs unless the player ticked the override and bought the event with it: pick_override_event is
   that pick's event, cleared when the pick is taken. */

enum { OV_ANY = 1, OV_ADULT, OV_CHILD, OV_WOMAN, OV_MAN, OV_FEMALE, OV_MALE, OV_HEATHEN, OV_HEATHEN_CHILD,
       OV_HEATHEN_MAN };
#define OV_KIND_COUNT 11
#define OV_FLAG_UNSET 0xFFFFFFFFu        /* +0x10 before the condition runs: still this, it made no variant */

/* New Believers' record fields (as story_heathen_stock.inc HV_*). */
#define OV_VV5_FACTION 0x1CECu
#define OV_VV5_ROLE 0x1CFCu
#define OV_VV5_SICK 0x1C48u

/* Each kind, then the kinds tried after it when the village has none (0 ends). */
static const unsigned char OV_FALLBACK[OV_KIND_COUNT][3] = {
    { 0 },
    { OV_ANY, 0 },
    { OV_ADULT, 0 },
    { OV_CHILD, OV_ANY, 0 },
    { OV_WOMAN, 0 },
    { OV_MAN, 0 },
    { OV_FEMALE, 0 },
    { OV_MALE, 0 },
    { OV_HEATHEN, 0 },
    { OV_HEATHEN_CHILD, OV_HEATHEN, 0 },
    { OV_HEATHEN_MAN, OV_HEATHEN, 0 },
};

static const ov_event *const OV_TABLES[6] = {
    NULL, VV1_OV_EVENTS, VV2_OV_EVENTS, VV3_OV_EVENTS, VV4_OV_EVENTS, VV5_OV_EVENTS,
};
static const int OV_COUNTS[6] = {
    0, VV1_OV_EVENT_COUNT, VV2_OV_EVENT_COUNT, VV3_OV_EVENT_COUNT, VV4_OV_EVENT_COUNT, VV5_OV_EVENT_COUNT,
};

static const ov_event *ov_find(int game, int slot) {
    int i;
    if (game < 1 || game > 5) {
        return NULL;
    }
    for (i = 0; i < OV_COUNTS[game]; ++i) {
        if (OV_TABLES[game][i].slot == slot) {
            return &OV_TABLES[game][i];
        }
    }
    return NULL;
}

/* The village's free villager records: the real limit (150 or 256), whatever the game's population cap says. */
static int ov_spare(int game) {
    switch (game) {
    case 1: return VV1_ARRAY() != NULL ? c1_spare_records() : 0;
    case 2: return VV2_POOL() != NULL ? c2_spare_records() : 0;
    case 3: return C3_COUNT - c3_demand();
    case 4: return C4_COUNT - c4_demand();
    case 5: return C5_COUNT - c5_demand();
    default: return 0;
    }
}

static int ov_heathen(int game, const unsigned char *r) {
    return game == 5 && r[OV_VV5_FACTION] != 0;
}

/* Whether record `r` of `game` is a villager of `kind` the override may cast. */
static int ov_matches(int game, const ce_adapter *a, const unsigned char *r, int kind) {
    int age, sex, adult;
    if (r == NULL || !a->listed(r)) {
        return 0;
    }
    age = *(const int *)(r + a->off_age);
    sex = *(const int *)(r + a->off_sex);
    adult = age >= a->adult_age;
    if (kind >= OV_HEATHEN) {
        int role;
        if (!ov_heathen(game, r)) {
            return 0;
        }
        role = *(const int *)(r + OV_VV5_ROLE);
        if ((role >= 12 && role <= 17) || r[OV_VV5_SICK] != 0) {
            return 0;                   /* a puzzle's Heathen, or a sick one: never */
        }
        return kind == OV_HEATHEN || (kind == OV_HEATHEN_CHILD && !adult)
               || (kind == OV_HEATHEN_MAN && adult && sex == a->sex_male);
    }
    if (ov_heathen(game, r)) {
        return 0;
    }
    switch (kind) {
    case OV_ANY: return 1;
    case OV_ADULT: return adult;
    case OV_CHILD: return !adult;
    case OV_WOMAN: return adult && sex == a->sex_female;
    case OV_MAN: return adult && sex == a->sex_male;
    case OV_FEMALE: return sex == a->sex_female;
    case OV_MALE: return sex == a->sex_male;
    default: return 0;
    }
}

/* A villager of `kind` (or its fallback) other than `not_a` / `not_b`, chosen at random among them; NULL: none.
   `choose` 0 only asks whether there is one. */
static unsigned char *ov_find_villager(int game, int kind, const unsigned char *not_a, const unsigned char *not_b,
                                       int choose) {
    const ce_adapter *a = ce_adapter_for(game);
    int k;
    if (a == NULL || kind <= 0 || kind >= OV_KIND_COUNT) {
        return NULL;
    }
    for (k = 0; k < 3 && OV_FALLBACK[kind][k] != 0; ++k) {
        int want = OV_FALLBACK[kind][k];
        int count = 0;
        int pick;
        int i;
        for (i = 0; i < a->record_count; ++i) {
            const unsigned char *r = a->record(i);
            if (r != not_a && r != not_b && ov_matches(game, a, r, want)) {
                ++count;
            }
        }
        if (count == 0) {
            continue;
        }
        pick = choose && count > 1 ? (a->rand_below != NULL ? a->rand_below(count) : (int)(STORY_TICK() % (DWORD)count))
                                   : 0;
        for (i = 0; i < a->record_count; ++i) {
            unsigned char *r = a->record(i);
            if (r != not_a && r != not_b && ov_matches(game, a, r, want) && pick-- == 0) {
                return r;
            }
        }
    }
    return NULL;
}

/* A villager for the first part (`kind4`) that still leaves a different villager for the second (`kind_c`), so
   two parts whose kinds overlap (e.g. "any" then "man" with one man) never refuse a pair that exists.  The random
   pick (`choose` 1) is tried first; when it takes the only villager the second part could have, every villager of
   the first part's kind (in its fallback order) is tried in turn.  NULL: no such pair. */
static unsigned char *ov_find_first_of_pair(int game, int kind4, int kind_c, int choose) {
    const ce_adapter *a = ce_adapter_for(game);
    unsigned char *first = ov_find_villager(game, kind4, NULL, NULL, choose);
    int k;
    if (first == NULL || kind_c == 0 || ov_find_villager(game, kind_c, first, NULL, 0) != NULL) {
        return first;
    }
    if (a == NULL) {
        return NULL;
    }
    for (k = 0; k < 3 && OV_FALLBACK[kind4][k] != 0; ++k) {
        int want = OV_FALLBACK[kind4][k];
        int found_kind = 0;
        int i;
        for (i = 0; i < a->record_count; ++i) {
            unsigned char *r = a->record(i);
            if (!ov_matches(game, a, r, want)) {
                continue;
            }
            found_kind = 1;
            if (ov_find_villager(game, kind_c, r, NULL, 0) != NULL) {
                return r;
            }
        }
        if (found_kind) {
            break;                      /* ov_find_villager casts only from the first kind the village has */
        }
    }
    return NULL;
}

/* What the village has none of, in the player's words. */
static const char *ov_kind_words(int kind) {
    switch (kind) {
    case OV_ADULT: return vvfp_tr("vvfp.story/story_override.ov_kind_words.s0", "an adult", 100);
    case OV_WOMAN: return vvfp_tr("vvfp.story/story_override.ov_kind_words.s1", "an adult woman", 100);
    case OV_MAN: return vvfp_tr("vvfp.story/story_override.ov_kind_words.s2", "an adult man", 100);
    case OV_FEMALE: return vvfp_tr("vvfp.story/story_override.ov_kind_words.s3", "a woman or girl", 100);
    case OV_MALE: return vvfp_tr("vvfp.story/story_override.ov_kind_words.s4", "a man or boy", 100);
    case OV_HEATHEN: case OV_HEATHEN_CHILD: case OV_HEATHEN_MAN:
        return vvfp_tr("vvfp.story/story_override.ov_kind_words.s5",
                       "a Heathen who can take part (not a puzzle's Heathen, not sick)", 200);
    default: return vvfp_tr("vvfp.story/story_override.ov_kind_words.s6", "a living villager", 100);
    }
}

/* The Lost Children's Where Are The Infants?: a mother aged 18 or more with an infant (its own condition's villager
   part, story_vv2.inc vv2_possible case 15), which its own code goes on to find. */
static int ov_vv2_mother(void) {
    unsigned char *pool = *(unsigned char **)(uintptr_t)VV2_POOL_GLOBAL;
    return pool != NULL && vv2_any_villager(pool, 0x168, -1, 0, 1);
}

/* Whether the village can have `e` now with the override: NULL, or why not (into `why`, at least 400 bytes). */
static const char *ov_refusal(int game, const ov_event *e, char *why, int cap) {
    unsigned char *first = NULL;
    char stem[80];
    if (e->refuse != NULL) {
        /* the table's n-th text (its only texts are these: scripts/scan_patch_text.py KEY_FAMILIES) */
        int n = 0;
        const ov_event *p;
        for (p = OV_TABLES[game]; p < e; ++p) {
            n += p->refuse != NULL;
        }
        wsprintfA(stem, "vvfp.story/story_tables.VV%d_OV_EVENTS.s%d", game, n);
        wsprintfA(why, vvfp_tr("vvfp.story/story_override.ov_refusal.s0",
                               "it can not be forced safely: it needs %s.", 200),
                  vvfp_tr(stem, e->refuse, 300));
        return why;
    }
    if (e->cast4 != 0) {
        if (ov_find_villager(game, e->cast4, NULL, NULL, 0) == NULL) {
            lstrcpynA(why, ov_kind_words(e->cast4), cap);
            return why;
        }
        first = ov_find_first_of_pair(game, e->cast4, e->cast_c, 0);
        if (first == NULL) {
            first = ov_find_villager(game, e->cast4, NULL, NULL, 0);   /* no pair: the second part says why */
        }
    }
    if (e->cast_c != 0 && ov_find_villager(game, e->cast_c, first, NULL, 0) == NULL) {
        lstrcpynA(why, ov_find_villager(game, e->cast_c, NULL, NULL, 0) != NULL
                           ? vvfp_tr("vvfp.story/story_override.ov_refusal.s1",
                                     "two different villagers for its two parts", 200)
                           : ov_kind_words(e->cast_c), cap);
        return why;
    }
    if (e->room > 0 && ov_spare(game) < e->room) {
        wsprintfA(why, vvfp_tr("vvfp.story/story_override.ov_refusal.s2",
                               "room in the game's villager records for %d more villagers (the village is at the most villagers the game can hold)", 300),
                  (int)e->room);
        return why;
    }
    return NULL;
}

/* The picker: whether `ev` can be picked with the override now (1), and if not, why (into `why`, "" when the
   override does not reach it: its own requirement stands). */
static int ov_possible(int game, const story_event *ev, char *why, int cap) {
    const ov_event *e = ov_find(game, ev->slot);
    why[0] = '\0';
    if (e == NULL) {
        return 0;
    }
    if (game == 1 && !vv1_base_possible(ev)) {
        return 0;
    }
    if (game == 2 && !vv2_base_possible(ev)) {
        return 0;
    }
    if (game == 2 && ev->slot == 15 && !ov_vv2_mother()) {
        return 0;                       /* Where Are The Infants?: its own code finds the mother and her infant */
    }
    return ov_refusal(game, e, why, cap) == NULL;
}

/* Whether the pick of `slot` armed for `game` was bought with the override. */
static int ov_armed(int game, int slot) {
    return pick_override_event != NULL && pick_event == pick_override_event && pick_game == game
           && pick_slot == slot && ov_find(game, slot) != NULL;
}

/* Before the condition runs for a delivery (choose_from_table): the fields it is to fill are cleared, so only what
   it picks now counts, and the variant is marked unset.  ov_undo puts them back when the event is not delivered. */
static unsigned int ov_saved[3];

static void ov_prepare(int game, int slot, void *object) {
    const ov_event *e = ov_find(game, slot);
    unsigned char *o = (unsigned char *)object;
    if (e == NULL || o == NULL) {
        return;
    }
    ov_saved[0] = *(unsigned int *)(o + 4);
    ov_saved[1] = *(unsigned int *)(o + 0xC);
    ov_saved[2] = *(unsigned int *)(o + 0x10);
    if (e->cast4) {
        *(unsigned int *)(o + 4) = 0;
    }
    if (e->cast_c) {
        *(unsigned int *)(o + 0xC) = 0;
    }
    if (e->flag_count) {
        *(unsigned int *)(o + 0x10) = OV_FLAG_UNSET;
    }
}

static void ov_undo(int game, int slot, void *object) {
    const ov_event *e = ov_find(game, slot);
    unsigned char *o = (unsigned char *)object;
    if (e == NULL || o == NULL) {
        return;
    }
    if (e->cast4) {
        *(unsigned int *)(o + 4) = ov_saved[0];
    }
    if (e->cast_c) {
        *(unsigned int *)(o + 0xC) = ov_saved[1];
    }
    if (e->flag_count) {
        *(unsigned int *)(o + 0x10) = ov_saved[2];
    }
}

/* The event's own condition failed: fill what it left empty.  1 = ready to deliver. */
static int ov_cast(int game, int slot, void *object) {
    const ov_event *e = ov_find(game, slot);
    const ce_adapter *a = ce_adapter_for(game);
    unsigned char *o = (unsigned char *)object;
    unsigned char *first, *second;
    if (e == NULL || a == NULL || o == NULL || e->pass || e->refuse != NULL) {
        return 0;
    }
    if (e->room > 0 && ov_spare(game) < e->room) {
        return 0;
    }
    first = *(unsigned char **)(o + 4);
    second = *(unsigned char **)(o + 0xC);
    if (e->cast4 && first == NULL) {
        first = e->cast_c && second == NULL ? ov_find_first_of_pair(game, e->cast4, e->cast_c, 1)
                                            : ov_find_villager(game, e->cast4, e->cast_c ? second : NULL, NULL, 1);
    }
    if (e->cast_c && (second == NULL || second == first)) {
        second = ov_find_villager(game, e->cast_c, first, NULL, 1);
    }
    if ((e->cast4 && first == NULL) || (e->cast_c && (second == NULL || second == first))) {
        return 0;
    }
    if (e->cast4) {
        *(unsigned char **)(o + 4) = first;
    }
    if (e->cast_c) {
        *(unsigned char **)(o + 0xC) = second;
    }
    if (e->flag_count && *(unsigned int *)(o + 0x10) == OV_FLAG_UNSET) {
        int roll = a->rand_below != NULL ? a->rand_below(e->flag_count) : (int)(STORY_TICK() % e->flag_count);
        *(unsigned int *)(o + 0x10) = (unsigned int)(roll + e->flag_base);
    }
    return 1;
}

/* A New Home / The Lost Children: whether the roll that delivers the pick of `slot` passes the event's own
   condition (story_vv1.inc / story_vv2.inc) because it was bought with the override -- and what it still needs is
   there now. */
static int ov_pass(int game, int slot) {
    const ov_event *e;
    char why[400];
    if (!ov_armed(game, slot)) {
        return 0;
    }
    e = ov_find(game, slot);
    if (!e->pass || ov_refusal(game, e, why, sizeof why) != NULL) {
        return 0;
    }
    return !(game == 2 && slot == 15 && !ov_vv2_mother());
}
