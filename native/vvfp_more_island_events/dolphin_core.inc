/* The Playful Dolphins: the owner's island event for The Tree of Life (2026-11-13).  Included by
   vvfp_more_island_events.c after adv_core.inc and adv_log.inc, whose words, pages, award, picker test, effects and
   log it shares; dolphin_vv4.inc shows it in The Tree of Life's own two-choice island-event dialog (adv_vv345.inc,
   as The Aspiring Adventurer and Diving for Treasure: adv_flow).

   WHO (the owner, 2026-11-13): one villager who may be picked (adv_game.eligible: alive and present, 14 or more,
   not protected -- adv_core.inc adv_is_protected: never a villager carrying a baby, mother or father, nor a body or
   ghost), drawn among them, each equally likely.  The event can happen only while at least two such villagers live
   (The Aspiring Adventurer's rule, adv_possible).  It needs no puzzle: not the Fishing Nets, nor any other.

   THE ROLLS (src/vv_playful_dolphins.py has the same numbers), all made with the game's own random routine when the
   popup is built, so every page can say what happens:
     "Swim towards the dolphins": the hunt 50%, the tail slap 50%; the hunt's award a LARGE food award
       (adv_award_roll x 2: twice a random amount in The Tree of Life's stock range, then Island Events Scale); the
       slap's loss 30 to 50 health (each equally likely);
     "Hang back": a SMALL food award (adv_award_roll_part x 1 / 2: half a normal one, then Island Events Scale).

   THE EFFECTS wait for their own page (the owner's standing rule): each ending's are made, once, when the page that
   ends its text is shown (adv_vv345.inc), and the Island Events log's one entry for the event takes them there:
     the hunt   Farming becomes 100, the game's maximum (adv_game.skill with DP_MASTER_GAIN: any Farming from 0 to
                100 plus 200, capped at 100), and the food award through the game's own food writer;
     the slap   health drops by the loss, never below DP_HEALTH_LEFT (dp_game.set_health: the game's own setter);
     hang back  the food award through the game's own food writer. */

#define DP_MASTER_GAIN 200                   /* added, then capped at the game's 100: Farming exactly 100 */
#define DP_HEALTH_LEFT 1                     /* the slap never kills: at least this much health is left */

enum { DP_E_HUNT = 0, DP_E_SLAP, DP_E_BACK, DP_ENDINGS };

typedef struct dp_game {
    const adv_game *g;
    int (*health)(int index);                          /* 0..100 */
    void (*set_health)(int index, int value);          /* the game's own health setter */
} dp_game;

static struct {
    const dp_game *t;
    const adv_game *g;
    int ready, answered, choice;
    int swimmer;                                  /* record index */
    unsigned int swimmer_id;
    int female;
    char name[ADV_NAME_BYTES];
    int slap;                                     /* "Swim towards the dolphins": 0 the hunt, 1 the tail slap */
    int hunt_award, back_award;
    int loss;                                     /* the slap's health loss, before the floor */
    int health_before, health_after;              /* the slap's, when made */
    int ending;                                   /* the ending reached, -1 none yet */
    int effects_made;
    adv_pages intro;
    adv_pages endings[DP_ENDINGS];
    int tallest_set, tallest_page;
} dp;

/* ---- Who ----------------------------------------------------------------------------------------------------- */

static int dp_possible(const dp_game *t) {
    return t != NULL && t->g != NULL && adv_possible(t->g);
}

/* ---- Words --------------------------------------------------------------------------------------------------- */

static const char *dp_name_of(char who) {
    (void)who;
    return dp.name;
}

static void dp_piece(char *out, int cap, int key, int number) {
    static char filled[ADV_PIECE_BYTES];
    const adv_piece_text *p = &DP_TEXT[key];
    const char *shown;
    adv_fill(filled, sizeof filled, p->english[dp.female], p->names, number, dp_name_of);
    shown = vvfp_trf(p->stem[dp.female], p->english[dp.female], filled, out, (unsigned int)cap);
    if (shown != out) {
        adv_copy(out, cap, shown);
    }
}

static char dp_buf[3][ADV_PIECE_BYTES];

/* One popup of up to three paragraphs (-1: none), starting on a new page. */
static void dp_popup(const adv_game *g, adv_pages *pages, int a, int b, int c, int number) {
    const char *p[4];
    int keys[3], k, n = 0;
    keys[0] = a; keys[1] = b; keys[2] = c;
    for (k = 0; k < 3; ++k) {
        if (keys[k] >= 0) {
            dp_piece(dp_buf[n], ADV_PIECE_BYTES, keys[k], number);
            p[n] = dp_buf[n];
            ++n;
        }
    }
    p[n] = NULL;
    adv_popup(g, pages, p);
}

/* Every ending's popups (src/vv_playful_dolphins.py pages_of). */
static void dp_compose(const adv_game *g) {
    dp_popup(g, &dp.intro, DP_INTRO, -1, -1, 0);
    dp_popup(g, &dp.endings[DP_E_HUNT], DP_SWIM, DP_HUNT_1, DP_HUNT_2, dp.hunt_award);
    dp_popup(g, &dp.endings[DP_E_SLAP], DP_SWIM, DP_SLAP, -1, 0);
    dp_popup(g, &dp.endings[DP_E_BACK], DP_BACK, -1, -1, dp.back_award);
}

static const adv_pages *dp_set(int set) {
    return set == 0 ? &dp.intro : &dp.endings[set - 1];
}

static void dp_find_tallest(const adv_game *g) {
    int set, k, best = -1, best_len = -1;
    dp.tallest_set = 0;
    dp.tallest_page = 0;
    for (set = 0; set <= DP_ENDINGS; ++set) {
        const adv_pages *pages = dp_set(set);
        for (k = 0; k < pages->count; ++k) {
            int lines = adv_lines(g, pages->text[k]);
            int len = adv_len(pages->text[k]);
            if (lines > best || (lines == best && len > best_len)) {
                best = lines;
                best_len = len;
                dp.tallest_set = set;
                dp.tallest_page = k;
            }
        }
    }
}

/* The swimmer, every roll and every page, for the popup about to be built (`g` lays the pages out); 0 when the
   event cannot happen. */
static int dp_begin(const dp_game *t, const adv_game *g) {
    int n, set;
    const unsigned char *r;
    memset(&dp, 0, sizeof dp);
    dp.t = t;
    dp.g = t != NULL ? t->g : NULL;
    dp.swimmer = -1;
    dp.ending = -1;
    if (!dp_possible(t)) {
        return 0;
    }
    n = adv_eligible_count(t->g, -1);
    dp.swimmer = adv_eligible_at(t->g, -1, t->g->rand_below(n));
    if (dp.swimmer < 0) {
        return 0;
    }
    r = t->g->record(dp.swimmer);
    dp.swimmer_id = adv_identity(t->g, dp.swimmer);
    dp.female = t->g->female(r) ? 1 : 0;
    t->g->name(r, dp.name, sizeof dp.name);
    /* "Swim towards the dolphins". */
    dp.slap = !adv_percent(t->g, 50);
    dp.loss = 30 + t->g->rand_below(21);
    /* The awards: the hunt's LARGE, hanging back's SMALL. */
    dp.hunt_award = adv_award_roll(t->g, ADV_KIND_FOOD, 2);
    dp.back_award = adv_award_roll_part(t->g, ADV_KIND_FOOD, 1, 2);
    dp_compose(g);
    dp_find_tallest(g);
    dp.ready = 1;
    for (set = 0; set <= DP_ENDINGS; ++set) {
        dp.ready &= dp_set(set)->count > 0;
    }
    return dp.ready;
}

/* ---- The effects --------------------------------------------------------------------------------------------- */

static int dp_same(void) {
    return dp.g != NULL && dp.g->record(dp.swimmer) != NULL && adv_identity(dp.g, dp.swimmer) == dp.swimmer_id;
}

/* Ending `e`'s effects, made once. */
static void dp_effects(int e) {
    const adv_game *g = dp.g;
    int health;
    if (g == NULL || dp.effects_made || e != dp.ending) {
        return;
    }
    dp.effects_made = 1;
    if (!dp_same()) {
        return;                                          /* not the village the popup is about (a fault) */
    }
    switch (e) {
    case DP_E_HUNT:
        g->skill(dp.swimmer, ADV_SKILL_FARMING, DP_MASTER_GAIN);
        g->award(ADV_KIND_FOOD, dp.hunt_award);
        break;
    case DP_E_SLAP:
        health = dp.t->health(dp.swimmer);
        dp.health_before = health;
        health -= dp.loss;
        if (health < DP_HEALTH_LEFT) {
            health = DP_HEALTH_LEFT;
        }
        if (health < dp.health_before) {
            dp.t->set_health(dp.swimmer, health);
        }
        dp.health_after = dp.t->health(dp.swimmer);
        break;
    default:                                             /* hang back */
        g->award(ADV_KIND_FOOD, dp.back_award);
        break;
    }
}

/* ---- As a dialog shows it (adv_flow) --------------------------------------------------------------------------- */

static const adv_pages *dp_flow_question(int node) {
    (void)node;
    return &dp.intro;
}

static void dp_flow_label(int node, int which, char *out, int cap) {
    (void)node;
    dp_piece(out, cap, which ? DP_LABEL_BACK : DP_LABEL_SWIM, 0);
}

/* The answer `choice` (0 "Swim towards the dolphins", 1 "Hang back"): its ending, its effects not yet made (they
   wait for their own page: dp_flow_effects). */
static int dp_flow_choose(int node, int choice) {
    (void)node;
    if (!dp.ready || dp.answered) {
        return ADV_ENDING(dp.ending >= 0 ? dp.ending : DP_E_BACK);
    }
    dp.answered = 1;
    dp.choice = choice != 0;
    dp.ending = dp.choice ? DP_E_BACK : (dp.slap ? DP_E_SLAP : DP_E_HUNT);
    return ADV_ENDING(dp.ending);
}

static void dp_flow_effects(int e) {
    dp_effects(e);
}

static int dp_flow_answer(int node, int choice) {
    int next = dp_flow_choose(node, choice);
    dp_effects(-1 - next);
    return next;
}

static const adv_pages *dp_flow_ending(int e) {
    return &dp.endings[e >= 0 && e < DP_ENDINGS ? e : DP_E_BACK];
}

static const char *dp_flow_tallest(void) {
    return dp_set(dp.tallest_set)->text[dp.tallest_page];
}

static int dp_flow_subject(void) {
    return dp.swimmer;
}

static void dp_flow_title(char *out, int cap) {
    dp_piece(out, cap, DP_TITLE, 0);
}

static const adv_flow DP_FLOW = {
    dp_flow_question, dp_flow_label, dp_flow_answer, dp_flow_ending, dp_flow_tallest,
    dp_flow_subject, dp_flow_title, dp_flow_choose, dp_flow_effects
};
