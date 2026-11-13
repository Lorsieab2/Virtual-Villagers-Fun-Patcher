/* Diving for Treasure: the owner's island event for The Secret City (2026-11-13).  Included by
   vvfp_more_island_events.c after adv_core.inc and adv_log.inc, whose words, pages, award, picker test, effects and
   log it shares; dive_vv3.inc shows it in The Secret City's own two-choice island-event dialog (adv_vv345.inc, as
   The Aspiring Adventurer: adv_flow).

   WHO (the owner, 2026-11-13):
     * the DIVER: one villager who may be picked (adv_game.eligible: alive and present, never a look-alike record, not
       protected -- adv_core.inc adv_is_protected: never a villager carrying a baby, mother or father, nor the Tribal
       Chief) and 18 or more (360 age units).  No spouse or children are needed ("Any adult works regardless of if
       they have children or a spouse"); the "Better not" page keeps its words regardless;
     * the "(random name), the head Doctor" of the rescue: flavour text only (the owner, 2026-11-13) -- any other such
       villager, 18 or more and not protected, never the diver, drawn at random.
   The event can happen only while at least two such villagers live (a diver and someone to name on the rescue page:
   the pages are composed before the answer).  Each is drawn among them, each equally likely.

   THE ROLLS (src/vv_diving_for_treasure.py has the same numbers), all made with the game's own random routine when
   the popup is built, so every page can say what happens:
     "Swim deeper": A, B, C, D 1 in 4 each; D: 75% survives, else sinks; sinking: 17% dies, 17% disappears, 66%
       rescued; A a NORMAL tech award, C a NORMAL food award (adv_award_roll x 1: a random amount in The Secret City's
       stock range, food 200-600, tech 1,000-2,000, then its own two-choice factor);
     the rescue's Healing gain and "Better not"'s Parenting gain: 10 to 20 each (each equally likely).

   THE EFFECTS wait for their own page (the owner's standing rule): each ending's are made, once, when the page that
   ends its text is shown (adv_vv345.inc), and the Island Events log's one entry for the event takes them there:
     A  the tech award, through the game's own tech writer;      B  nothing;
     C  the food award, through the game's own food writer;
     D1 the diver now dislikes swimming (dv_game.dislike_swimming: the game's own preference, taken from the likes);
     D2a the game's own death (adv_game.kill: health 0 -- a body, a grave, "Unknown causes");
     D2b gone for good, no body, no grave (adv_game.vanish), the Cause of Death companion told (VvfpCauseVanishedBy);
     D2c + the gain to Healing, at most the game's 100 (adv_game.skill);
     "Better not" + the gain to Parenting, at most the game's 100. */

#define DV_ADULT_UNITS 360                   /* 18 years */

enum { DV_E_A = 0, DV_E_B, DV_E_C, DV_E_D1, DV_E_D2A, DV_E_D2B, DV_E_D2C, DV_E_NOT, DV_ENDINGS };

typedef struct dv_game {
    const adv_game *g;
    int (*age)(const unsigned char *record);           /* age units */
    void (*dislike_swimming)(int index);               /* the game's own "dislikes swimming" */
} dv_game;

static struct {
    const dv_game *t;
    const adv_game *g;
    int ready, answered, choice;
    int diver, doctor;                            /* record indexes */
    unsigned int diver_id;
    int female;
    char name[ADV_NAME_BYTES], doctor_name[ADV_NAME_BYTES];
    int find;                                     /* 0..3: A, B, C, D */
    int survives;                                 /* D: 1 survives (D1), 0 sinks */
    int sink;                                     /* sinking: 0 dies, 1 disappears, 2 rescued */
    int tech_award, food_award;
    int healing_gain, parenting_gain;             /* before the cap */
    int ending;                                   /* the ending reached, -1 none yet */
    int effects_made;
    adv_pages intro;
    adv_pages endings[DV_ENDINGS];
    int tallest_set, tallest_page;
} dv;

/* ---- Who ----------------------------------------------------------------------------------------------------- */

static int dv_candidate(const dv_game *t, const unsigned char *r) {
    return r != NULL && t->g->eligible(r) && t->age(r) >= DV_ADULT_UNITS;
}

/* How many may be picked, never `except`; dv_at: the k-th of them (0-based), or -1. */
static int dv_count(const dv_game *t, int except) {
    int i, n = 0, count = t->g->count();
    for (i = 0; i < count; ++i) {
        n += i != except && dv_candidate(t, t->g->record(i));
    }
    return n;
}

static int dv_at(const dv_game *t, int except, int k) {
    int i, count = t->g->count();
    for (i = 0; i < count; ++i) {
        if (i != except && dv_candidate(t, t->g->record(i)) && k-- == 0) {
            return i;
        }
    }
    return -1;
}

/* The event's condition: a diver and another to name as the head Doctor. */
static int dv_possible(const dv_game *t) {
    return t != NULL && t->g != NULL && dv_count(t, -1) >= 2;
}

/* ---- Words --------------------------------------------------------------------------------------------------- */

static const char *dv_name_of(char who) {
    return who == 'd' ? dv.doctor_name : dv.name;
}

static void dv_piece(char *out, int cap, int key, int number) {
    static char filled[ADV_PIECE_BYTES];
    const adv_piece_text *p = &DV_TEXT[key];
    const char *shown;
    adv_fill(filled, sizeof filled, p->english[dv.female], p->names, number, dv_name_of);
    shown = vvfp_trf(p->stem[dv.female], p->english[dv.female], filled, out, (unsigned int)cap);
    if (shown != out) {
        adv_copy(out, cap, shown);
    }
}

static char dv_buf[2][ADV_PIECE_BYTES];

static const char *dv_one(int slot, int key, int number) {
    dv_piece(dv_buf[slot], ADV_PIECE_BYTES, key, number);
    return dv_buf[slot];
}

/* One popup of paragraphs a and b (b < 0: a alone), starting on a new page. */
static void dv_popup(const adv_game *g, adv_pages *pages, int a, int b, int number) {
    const char *p[3];
    p[0] = dv_one(0, a, number);
    p[1] = b >= 0 ? dv_one(1, b, number) : NULL;
    p[2] = NULL;
    adv_popup(g, pages, p);
}

/* Every ending's popups (src/vv_diving_for_treasure.py pages_of): "Swim deeper" with the find; the air tank's
   ending in a popup of its own; the sinking's outcome in another. */
static void dv_compose(const adv_game *g) {
    static const int FINDS[4] = { DV_FIND_A, DV_FIND_B, DV_FIND_C, DV_FIND_D };
    int e;
    dv_popup(g, &dv.intro, DV_INTRO, -1, 0);
    for (e = DV_E_A; e <= DV_E_C; ++e) {
        dv_popup(g, &dv.endings[e], DV_DEEPER, FINDS[e], e == DV_E_A ? dv.tech_award : dv.food_award);
    }
    for (e = DV_E_D1; e <= DV_E_D2C; ++e) {
        dv_popup(g, &dv.endings[e], DV_DEEPER, DV_FIND_D, 0);
        if (e == DV_E_D1) {
            dv_popup(g, &dv.endings[e], DV_D1, -1, 0);
            continue;
        }
        dv_popup(g, &dv.endings[e], DV_D2_1, DV_D2_2, 0);
        if (e == DV_E_D2A) {
            dv_popup(g, &dv.endings[e], DV_D2A, -1, 0);
        } else if (e == DV_E_D2B) {
            dv_popup(g, &dv.endings[e], DV_D2B, -1, 0);
        } else {
            dv_popup(g, &dv.endings[e], DV_D2C_1, DV_D2C_2, 0);
        }
    }
    dv_popup(g, &dv.endings[DV_E_NOT], DV_NOT, -1, 0);
}

static const adv_pages *dv_set(int set) {
    return set == 0 ? &dv.intro : &dv.endings[set - 1];
}

static void dv_find_tallest(const adv_game *g) {
    int set, k, best = -1, best_len = -1;
    dv.tallest_set = 0;
    dv.tallest_page = 0;
    for (set = 0; set <= DV_ENDINGS; ++set) {
        const adv_pages *pages = dv_set(set);
        for (k = 0; k < pages->count; ++k) {
            int lines = adv_lines(g, pages->text[k]);
            int len = adv_len(pages->text[k]);
            if (lines > best || (lines == best && len > best_len)) {
                best = lines;
                best_len = len;
                dv.tallest_set = set;
                dv.tallest_page = k;
            }
        }
    }
}

/* The diver, the head Doctor, every roll and every page, for the popup about to be built (`g` lays the pages out);
   0 when the event cannot happen. */
static int dv_begin(const dv_game *t, const adv_game *g) {
    int n, roll, set;
    const unsigned char *r;
    memset(&dv, 0, sizeof dv);
    dv.t = t;
    dv.g = t != NULL ? t->g : NULL;
    dv.diver = dv.doctor = -1;
    dv.ending = -1;
    if (!dv_possible(t)) {
        return 0;
    }
    n = dv_count(t, -1);
    dv.diver = dv_at(t, -1, t->g->rand_below(n));
    if (dv.diver < 0) {
        return 0;
    }
    r = t->g->record(dv.diver);
    dv.diver_id = adv_identity(t->g, dv.diver);
    dv.female = t->g->female(r) ? 1 : 0;
    t->g->name(r, dv.name, sizeof dv.name);
    n = dv_count(t, dv.diver);
    dv.doctor = dv_at(t, dv.diver, t->g->rand_below(n));
    if (dv.doctor < 0) {
        return 0;
    }
    t->g->name(t->g->record(dv.doctor), dv.doctor_name, sizeof dv.doctor_name);
    /* "Swim deeper". */
    dv.find = t->g->rand_below(4);
    dv.survives = adv_percent(t->g, 75);
    roll = t->g->rand_below(100);
    dv.sink = roll < 17 ? 0 : (roll < 34 ? 1 : 2);
    dv.healing_gain = 10 + t->g->rand_below(11);
    /* "Better not". */
    dv.parenting_gain = 10 + t->g->rand_below(11);
    /* The awards (A tech, C food). */
    dv.tech_award = adv_award_roll(t->g, ADV_KIND_TECH, 1);
    dv.food_award = adv_award_roll(t->g, ADV_KIND_FOOD, 1);
    dv_compose(g);
    dv_find_tallest(g);
    dv.ready = 1;
    for (set = 0; set <= DV_ENDINGS; ++set) {
        dv.ready &= dv_set(set)->count > 0;
    }
    return dv.ready;
}

/* ---- The effects --------------------------------------------------------------------------------------------- */

static int dv_same(void) {
    return dv.g != NULL && dv.g->record(dv.diver) != NULL && adv_identity(dv.g, dv.diver) == dv.diver_id;
}

/* Ending `e`'s effects, made once. */
static void dv_effects(int e) {
    const adv_game *g = dv.g;
    if (g == NULL || dv.effects_made || e != dv.ending) {
        return;
    }
    dv.effects_made = 1;
    if (!dv_same()) {
        return;                                          /* not the village the popup is about (a fault) */
    }
    switch (e) {
    case DV_E_A:
        g->award(ADV_KIND_TECH, dv.tech_award);
        break;
    case DV_E_C:
        g->award(ADV_KIND_FOOD, dv.food_award);
        break;
    case DV_E_D1:
        dv.t->dislike_swimming(dv.diver);
        break;
    case DV_E_D2A:
        g->kill(dv.diver);
        break;
    case DV_E_D2B:
        g->vanish(dv.diver);
        adv_tell_vanished(g->game, dv.diver, "Disappeared in Diving for Treasure (lost at sea)");
        break;
    case DV_E_D2C:
        g->skill(dv.diver, ADV_SKILL_HEALING, dv.healing_gain);
        break;
    case DV_E_NOT:
        g->skill(dv.diver, ADV_SKILL_PARENTING, dv.parenting_gain);
        break;
    default:                                             /* B: nothing happens */
        break;
    }
}

/* ---- As a dialog shows it (adv_flow) --------------------------------------------------------------------------- */

static const adv_pages *dv_flow_question(int node) {
    (void)node;
    return &dv.intro;
}

static void dv_flow_label(int node, int which, char *out, int cap) {
    (void)node;
    dv_piece(out, cap, which ? DV_LABEL_NOT : DV_LABEL_DEEPER, 0);
}

/* The answer `choice` (0 "Swim deeper", 1 "Better not"): its ending, its effects not yet made (they wait for their
   own page: dv_flow_effects). */
static int dv_flow_choose(int node, int choice) {
    static const int FINDS[3] = { DV_E_A, DV_E_B, DV_E_C };
    (void)node;
    if (!dv.ready || dv.answered) {
        return ADV_ENDING(dv.ending >= 0 ? dv.ending : DV_E_NOT);
    }
    dv.answered = 1;
    dv.choice = choice != 0;
    if (dv.choice) {
        dv.ending = DV_E_NOT;
    } else if (dv.find < 3) {
        dv.ending = FINDS[dv.find];
    } else if (dv.survives) {
        dv.ending = DV_E_D1;
    } else {
        dv.ending = dv.sink == 0 ? DV_E_D2A : (dv.sink == 1 ? DV_E_D2B : DV_E_D2C);
    }
    return ADV_ENDING(dv.ending);
}

static void dv_flow_effects(int e) {
    dv_effects(e);
}

static int dv_flow_answer(int node, int choice) {
    int next = dv_flow_choose(node, choice);
    dv_effects(-1 - next);
    return next;
}

static const adv_pages *dv_flow_ending(int e) {
    return &dv.endings[e >= 0 && e < DV_ENDINGS ? e : DV_E_NOT];
}

static const char *dv_flow_tallest(void) {
    return dv_set(dv.tallest_set)->text[dv.tallest_page];
}

static int dv_flow_subject(void) {
    return dv.diver;
}

static void dv_flow_title(char *out, int cap) {
    dv_piece(out, cap, DV_TITLE, 0);
}

static const adv_flow DV_FLOW = {
    dv_flow_question, dv_flow_label, dv_flow_answer, dv_flow_ending, dv_flow_tallest,
    dv_flow_subject, dv_flow_title, dv_flow_choose, dv_flow_effects
};
