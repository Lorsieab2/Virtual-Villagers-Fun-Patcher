/* The Troubling Signs: the owner's island event for The Secret City (2026-11-13).  Included by
   vvfp_more_island_events.c after adv_core.inc and adv_log.inc, whose words, pages, award and log it shares;
   troubling_vv3.inc shows it in The Secret City's island-event dialog, with four answers.

   WHO (the owner, 2026-11-13):
     * the Tribal Chief, wearing the chief's robe (ts_game.chief: The Secret City's chief byte +0xE80 with the robe's
       body +0xDF4 = 29, as its robing 0x45FBC0 writes them, 0x45FBD0 / 0x45FBDE) -- the speaker, never one of the
       nine below;
     * NINE other villagers, all different: four ADVISORS, one for each group the chief may ask (the spiritual
       leaders, the magicians, the naturalists, the scientists and healers), each the "(random name)" of the group's
       page, the same four for the whole event, who stay; and five TRAVELLERS, who leave the village for good;
       each of them 18 or more (360 age units) and not protected (adv_core.inc adv_is_protected: never a villager
       carrying a baby, mother or father, nor the Tribal Chief -- the stock picker's one exclusion; everyone else,
       titles and Esteemed Elders included, is fair game);
     * a population of 61 or more, counted as The Lost Children's own count for its "A Dangerous Mission"
       (0x425860: the living villagers who are not look-alikes, plus the babies being carried; ts_game.population).
   With no robed chief, fewer than nine such villagers, a smaller population or no tribe name to call, the event
   cannot happen.  The nine are drawn at random among every such villager (a partial shuffle with the game's own
   random routine: any nine of them equally likely, in at most 9 draws, bounded for 256 villagers).

   THE ANSWERS and their awards: a NORMAL award each (adv_award_roll x 1: a random amount in The Secret City's stock
   range, then its own two-choice factor), all four rolled when the popup is built so every page can say it:
     "Consult the spiritual leaders"        the village loses food;
     "Ask the magicians for advice"         the village gains tech points;
     "Call the naturalists to a discussion" the village gains food;
     "Talk with the scientists and healers" the village loses tech points.
   The page says the full amount rolled, a loss too (the owner, 2026-11-13); a loss takes at most what is stored, so
   the store stops at 0 (the game's own writers also floor at 0).

   THE PAGES: the question (the opening, then the four answers); then the asked group's advice, the "Hear me" page,
   and the decree.  THE EFFECTS wait for their own page (the owner's standing rule): made, once, when the decree's
   last page is shown -- the five travellers leave (the game's own removal of a living villager, no body, no grave;
   the Cause of Death companion told, VvfpCauseVanishedBy) and the award -- and the Island Events log's one entry for
   the event takes them there (adv_log.inc). */

#define TS_ADULT_UNITS 360                   /* 18 years */
#define TS_TRAVELLERS 5
#define TS_ADVISORS 4
#define TS_GROUPS 4
#define TS_PICKS (TS_ADVISORS + TS_TRAVELLERS)
#define TS_POPULATION_MIN 61                 /* "A Dangerous Mission": a population of more than 60 */
#define TS_TRIBE_BYTES 96
#define TS_MAX_RECORDS 512

enum { TS_SPIRITUAL = 0, TS_MAGICIANS, TS_NATURALISTS, TS_SCIENTISTS };

/* ---- The game's side ------------------------------------------------------------------------------------------- */

typedef struct ts_game {
    const adv_game *g;
    int (*chief)(void);                              /* the robed Tribal Chief's record, -1 none */
    int (*population)(void);                         /* as "A Dangerous Mission" counts it */
    int (*tribe)(char *out, int cap);                /* the tribe's name: 1 when known */
    int (*stored)(int kind);                         /* the food / tech points stored */
    int (*age)(const unsigned char *record);         /* age units */
    int (*alive)(const unsigned char *record);       /* present and alive */
} ts_game;

static struct {
    const ts_game *t;
    const adv_game *g;
    int ready, answered, choice, effects_made;
    int chief, female;
    unsigned int chief_id;
    char chief_name[ADV_NAME_BYTES];
    char tribe[TS_TRIBE_BYTES];
    int advisor[TS_ADVISORS];
    char advisor_name[TS_ADVISORS][ADV_NAME_BYTES];
    int traveller[TS_TRAVELLERS];
    unsigned int traveller_id[TS_TRAVELLERS];
    int award[TS_GROUPS];                            /* the amount each answer's decree says (the full roll) */
    adv_pages intro;
    adv_pages result[TS_GROUPS];
    int tallest_set, tallest_page;
    int speaker;                                     /* the advisor a piece being filled names */
} ts;

static const int TS_KIND[TS_GROUPS] = { ADV_KIND_FOOD, ADV_KIND_TECH, ADV_KIND_FOOD, ADV_KIND_TECH };
static const int TS_SIGN[TS_GROUPS] = { -1, +1, +1, -1 };
static const int TS_LABELS[TS_GROUPS] = { TS_LABEL_SPIRITUAL, TS_LABEL_MAGICIANS, TS_LABEL_NATURALISTS,
                                          TS_LABEL_SCIENTISTS };

/* ---- Who ------------------------------------------------------------------------------------------------------- */

/* One of the nine: alive and present (never a look-alike record), 18 or more, not protected (adv_core.inc
   adv_is_protected, nothing allowed: the chief is never one of them -- the chief alone is let through, as the speaker,
   by ts_game.chief). */
static int ts_candidate(const ts_game *t, const unsigned char *r) {
    return r != NULL && t->alive(r) && t->age(r) >= TS_ADULT_UNITS && !adv_is_protected(t->g->game, r);
}

/* The candidates' records, in record order (at most `cap`); the count. */
static int ts_candidates(const ts_game *t, int except, int *out, int cap) {
    int i, n = 0, count = t->g->count();
    for (i = 0; i < count && n < cap; ++i) {
        if (i != except && ts_candidate(t, t->g->record(i))) {
            out[n++] = i;
        }
    }
    return n;
}

static int ts_possible(const ts_game *t) {
    static int list[TS_MAX_RECORDS];
    char tribe[TS_TRIBE_BYTES];
    int chief;
    if (t == NULL || t->g == NULL) {
        return 0;
    }
    chief = t->chief();
    return chief >= 0 && t->population() >= TS_POPULATION_MIN && t->tribe(tribe, sizeof tribe)
        && ts_candidates(t, chief, list, TS_MAX_RECORDS) >= TS_PICKS;
}

/* ---- Words ----------------------------------------------------------------------------------------------------- */

static const char *ts_name_of(char who) {
    if (who == 'a') {
        return ts.speaker >= 0 && ts.speaker < TS_ADVISORS ? ts.advisor_name[ts.speaker] : "";
    }
    return who == 't' ? ts.tribe : ts.chief_name;
}

static void ts_piece(char *out, int cap, int key, int number) {
    static char filled[ADV_PIECE_BYTES];
    const adv_piece_text *p = &TS_TEXT[key];
    const char *shown;
    adv_fill(filled, sizeof filled, p->english[ts.female], p->names, number, ts_name_of);
    shown = vvfp_trf(p->stem[ts.female], p->english[ts.female], filled, out, (unsigned int)cap);
    if (shown != out) {
        adv_copy(out, cap, shown);
    }
}

static char ts_buf[4][ADV_PIECE_BYTES];

static const char *ts_one(int slot, int key, int number) {
    ts_piece(ts_buf[slot], ADV_PIECE_BYTES, key, number);
    return ts_buf[slot];
}

static void ts_compose(const adv_game *g) {
    static const int ADVICE[TS_GROUPS] = { TS_ADVICE_SPIRITUAL, TS_ADVICE_MAGICIANS, TS_ADVICE_NATURALISTS,
                                           TS_ADVICE_SCIENTISTS };
    static const int DECREE[TS_GROUPS] = { TS_DECREE_SPIRITUAL, TS_DECREE_MAGICIANS, TS_DECREE_NATURALISTS,
                                           TS_DECREE_SCIENTISTS };
    static const int DEPART[TS_GROUPS] = { TS_DEPART_SPIRITUAL, TS_DEPART_MAGICIANS, TS_DEPART_NATURALISTS,
                                           TS_DEPART_SCIENTISTS };
    const char *p[5];
    int k;
    ts.speaker = -1;
    p[0] = ts_one(0, TS_INTRO_1, 0);
    p[1] = ts_one(1, TS_INTRO_2, 0);
    p[2] = NULL;
    adv_popup(g, &ts.intro, p);
    for (k = 0; k < TS_GROUPS; ++k) {
        ts.speaker = k;                                   /* the asked group's own advisor */
        p[0] = ts_one(0, ADVICE[k], 0);
        p[1] = NULL;
        adv_popup(g, &ts.result[k], p);
        p[0] = ts_one(0, TS_HEAR, 0);
        adv_popup(g, &ts.result[k], p);
        p[0] = ts_one(0, DECREE[k], 0);
        p[1] = ts_one(1, TS_DECREE_2, 0);
        p[2] = ts_one(2, DEPART[k], ts.award[k]);
        p[3] = k == TS_SCIENTISTS ? ts_one(3, TS_LOSS_SCIENTISTS, ts.award[k]) : NULL;
        p[4] = NULL;
        adv_popup(g, &ts.result[k], p);
    }
    ts.speaker = -1;
}

static const adv_pages *ts_set(int set) {
    return set == 0 ? &ts.intro : &ts.result[set - 1];
}

static void ts_find_tallest(const adv_game *g) {
    int set, k, best = -1, best_len = -1;
    ts.tallest_set = 0;
    ts.tallest_page = 0;
    for (set = 0; set <= TS_GROUPS; ++set) {
        const adv_pages *pages = ts_set(set);
        for (k = 0; k < pages->count; ++k) {
            int lines = adv_lines(g, pages->text[k]);
            int len = adv_len(pages->text[k]);
            if (lines > best || (lines == best && len > best_len)) {
                best = lines;
                best_len = len;
                ts.tallest_set = set;
                ts.tallest_page = k;
            }
        }
    }
}

static const char *ts_tallest_text(void) {
    return ts_set(ts.tallest_set)->text[ts.tallest_page];
}

/* The chief, the nine, every award and every page, for the popup about to be built (`g` lays the pages out); 0 when
   the event cannot happen. */
static int ts_begin(const ts_game *t, const adv_game *g) {
    static int list[TS_MAX_RECORDS];
    int n, k, set;
    memset(&ts, 0, sizeof ts);
    ts.t = t;
    ts.g = t != NULL ? t->g : NULL;
    ts.chief = -1;
    ts.speaker = -1;
    if (!ts_possible(t)) {
        return 0;
    }
    ts.chief = t->chief();
    ts.chief_id = adv_identity(t->g, ts.chief);
    ts.female = t->g->female(t->g->record(ts.chief)) ? 1 : 0;
    t->g->name(t->g->record(ts.chief), ts.chief_name, sizeof ts.chief_name);
    if (!t->tribe(ts.tribe, sizeof ts.tribe)) {
        return 0;
    }
    /* The nine: a partial shuffle, each draw among those not yet drawn (any nine equally likely). */
    n = ts_candidates(t, ts.chief, list, TS_MAX_RECORDS);
    if (n < TS_PICKS) {
        return 0;
    }
    for (k = 0; k < TS_PICKS; ++k) {
        int j = k + t->g->rand_below(n - k);
        int swap = list[k];
        list[k] = list[j];
        list[j] = swap;
    }
    for (k = 0; k < TS_ADVISORS; ++k) {
        ts.advisor[k] = list[k];
        t->g->name(t->g->record(list[k]), ts.advisor_name[k], sizeof ts.advisor_name[k]);
    }
    for (k = 0; k < TS_TRAVELLERS; ++k) {
        ts.traveller[k] = list[TS_ADVISORS + k];
        ts.traveller_id[k] = adv_identity(t->g, ts.traveller[k]);
    }
    /* The awards: the page says the full amount rolled, a loss too (the owner, 2026-11-13: "yeah show the full
       amount"); the store stops at 0 (ts_effects). */
    for (k = 0; k < TS_GROUPS; ++k) {
        ts.award[k] = adv_award_roll(t->g, TS_KIND[k], 1);
    }
    ts_compose(g);
    ts_find_tallest(g);
    ts.ready = 1;
    for (set = 0; set <= TS_GROUPS; ++set) {
        ts.ready &= ts_set(set)->count > 0;
    }
    return ts.ready;
}

/* ---- The answer and the effects -------------------------------------------------------------------------------- */

/* The answer `group` (TS_*), taken once, its effects not yet made (they wait for the decree's last page). */
static int ts_answer(int group) {
    if (!ts.ready || ts.answered || group < 0 || group >= TS_GROUPS) {
        return 0;
    }
    ts.answered = 1;
    ts.choice = group;
    return 1;
}

static void ts_effects(int group) {
    const adv_game *g = ts.g;
    int k;
    if (g == NULL || !ts.answered || ts.effects_made || group != ts.choice) {
        return;
    }
    ts.effects_made = 1;
    if (g->record(ts.chief) == NULL || adv_identity(g, ts.chief) != ts.chief_id) {
        return;                                          /* not the village the popup is about (a fault) */
    }
    for (k = 0; k < TS_TRAVELLERS; ++k) {
        int i = ts.traveller[k];
        if (g->record(i) != NULL && adv_identity(g, i) == ts.traveller_id[k] && ts.t->alive(g->record(i))) {
            g->vanish(i);
            adv_tell_vanished(g->game, i, "Disappeared in The Troubling Signs (left on the mission to heal the village)");
        }
    }
    if (ts.award[group] > 0) {
        int amount = ts.award[group];
        if (TS_SIGN[group] < 0) {
            int stored = ts.t->stored(TS_KIND[group]);
            amount = stored <= 0 ? 0 : (amount > stored ? stored : amount);   /* the store stops at 0 */
        }
        if (amount > 0) {
            g->award(TS_KIND[group], TS_SIGN[group] * amount);
        }
    }
}

static void ts_flow_effects(int group) {
    ts_effects(group);
}
