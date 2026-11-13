/* The Climb: the owner's island event for The Lost Children (2026-11-12).  Included by vvfp_more_island_events.c
   after adv_core.inc, whose words, pages, award and effects it shares; adv_vv2.inc shows it in The Lost Children's
   family-A dialog (adv_flow: one question, three endings).

   WHO (the owner, 2026-11-12): one villager who may go on The Aspiring Adventurer (adv_game.eligible: alive and
   present, not carrying a baby -- mother or father -- and not special: The Lost Children's Esteemed Elder statues),
   18 or more (360 age units) and at least a "Trainee" in Research: 20 or more (adv_game.research; the game's own
   Details panel calls a skill below 20 "Untrained" and an adult's 20 to 49 "Trainee", 0x429C3D `cmp eax, 0x14; jl`
   on the Research field +0x7F4).  One such villager is enough; with none the event cannot happen.  The villager is
   drawn among them, each equally likely.

   THE ROLLS (src/vv_the_climb.py has the same numbers), all made with the game's own random routine when the popup
   is built, so every page can say what happens:
     "Go with the plan": 50% the fall, 50% the summit; the summit's award a LARGE tech award (adv_award_roll x 2:
       twice a normal one, drawn from the game's stock tech range, then the game's own two-choice factor);
     "Follow the scientists' advice": +10 to 20 Research (each equally likely), at most the game's 100.

   THE EFFECTS are made when the answer is clicked (adv_choose's rule: the dialog is modal, the village does not run
   and no save can come between the click and the pages, so the Island Events log's comparison around that click
   records them, under the event's title with the answer clicked):
     the fall: the game's own death (adv_game.kill: health 0 -- a body, a grave, "Unknown causes");
     the summit: Research set to the game's maximum, 100 (adv_game.skill: 0x4212F4's own cap), the award through the
       game's own tech writer, and the village celebrates (adv_game.celebrate: the game's own village celebration, as
       its Old Friends event calls it); "Distinguished Scientist" is the story's words only, not a game title;
     the advice: + the gain to Research, at most 100. */

#define CLIMB_ADULT_UNITS 360                /* 18 years */
#define CLIMB_TRAINEE 20                     /* the game's own "Trainee" level (0x429C3D) */
#define CLIMB_RESEARCH_MAX 100               /* the game's own skill cap (0x4212F4) */

enum { CLIMB_E_FALL = 0, CLIMB_E_SUMMIT, CLIMB_E_ADVICE, CLIMB_ENDINGS };

static struct {
    const adv_game *g;
    int ready, answered, choice;
    int hero;                                     /* the villager's record */
    unsigned int hero_id;
    int female;
    char name[ADV_NAME_BYTES];
    int falls;                                    /* "Go with the plan": 1 the fall, 0 the summit */
    int award;                                    /* the summit's award */
    int gain;                                     /* the advice's Research gain (before the cap) */
    int ending;                                   /* the ending reached, -1 none yet */
    adv_pages intro;
    adv_pages endings[CLIMB_ENDINGS];
    int tallest_set, tallest_page;
} climb;

/* ---- Who ----------------------------------------------------------------------------------------------------- */

static int climb_eligible(const adv_game *g, const unsigned char *r) {
    return r != NULL && g->eligible(r) && g->age(r) >= CLIMB_ADULT_UNITS && g->research(r) >= CLIMB_TRAINEE;
}

/* How many villagers may climb; climb_at: the k-th of them (0-based), or -1. */
static int climb_count(const adv_game *g) {
    int i, n = 0, count = g->count();
    for (i = 0; i < count; ++i) {
        n += climb_eligible(g, g->record(i));
    }
    return n;
}

static int climb_at(const adv_game *g, int k) {
    int i, count = g->count();
    for (i = 0; i < count; ++i) {
        if (climb_eligible(g, g->record(i)) && k-- == 0) {
            return i;
        }
    }
    return -1;
}

/* The event's condition (the owner): one villager who may climb. */
static int climb_possible(const adv_game *g) {
    return g != NULL && g->age != NULL && g->research != NULL && g->celebrate != NULL && climb_count(g) > 0;
}

/* ---- Words --------------------------------------------------------------------------------------------------- */

static const char *climb_name_of(char who) {
    (void)who;
    return climb.name;
}

static void climb_piece(char *out, int cap, int key, int number) {
    static char filled[ADV_PIECE_BYTES];
    const adv_piece_text *t = &CLIMB_TEXT[key];
    const char *shown;
    adv_fill(filled, sizeof filled, t->english[climb.female], t->names, number, climb_name_of);
    shown = vvfp_trf(t->stem[climb.female], t->english[climb.female], filled, out, (unsigned int)cap);
    if (shown != out) {
        adv_copy(out, cap, shown);
    }
}

static char climb_buf[3][ADV_PIECE_BYTES];

/* "<a> <b>": two pieces as one paragraph (b < 0: a alone). */
static const char *climb_join(int slot, int a, int b, int number) {
    static char second[ADV_PIECE_BYTES];
    climb_piece(climb_buf[slot], ADV_PIECE_BYTES, a, number);
    if (b >= 0) {
        climb_piece(second, sizeof second, b, number);
        adv_cat(climb_buf[slot], ADV_PIECE_BYTES, " ");
        adv_cat(climb_buf[slot], ADV_PIECE_BYTES, second);
    }
    return climb_buf[slot];
}

static void climb_compose(const adv_game *g) {
    const char *p[2];
    int e;
    p[1] = NULL;
    p[0] = climb_join(0, CLIMB_INTRO, -1, 0);
    adv_popup(g, &climb.intro, p);
    for (e = CLIMB_E_FALL; e <= CLIMB_E_SUMMIT; ++e) {   /* the plan's popup, then the climb's (the owner: "Then") */
        p[0] = climb_join(0, CLIMB_PLAN, -1, 0);
        adv_popup(g, &climb.endings[e], p);
        p[0] = climb_join(1, CLIMB_CLIMB, e == CLIMB_E_FALL ? CLIMB_FALL : CLIMB_SUMMIT, climb.award);
        adv_popup(g, &climb.endings[e], p);
    }
    p[0] = climb_join(0, CLIMB_ADVICE, -1, 0);
    adv_popup(g, &climb.endings[CLIMB_E_ADVICE], p);
}

static const adv_pages *climb_set(int set) {
    return set == 0 ? &climb.intro : &climb.endings[set - 1];
}

static void climb_find_tallest(const adv_game *g) {
    int set, k, best = -1, best_len = -1;
    climb.tallest_set = 0;
    climb.tallest_page = 0;
    for (set = 0; set <= CLIMB_ENDINGS; ++set) {
        const adv_pages *pages = climb_set(set);
        for (k = 0; k < pages->count; ++k) {
            int lines = adv_lines(g, pages->text[k]);
            int len = adv_len(pages->text[k]);
            if (lines > best || (lines == best && len > best_len)) {
                best = lines;
                best_len = len;
                climb.tallest_set = set;
                climb.tallest_page = k;
            }
        }
    }
}

/* Who climbs, every roll and every page, for the popup about to be built; 0 when the event cannot happen. */
static int climb_begin(const adv_game *g) {
    int n, set;
    const unsigned char *r;
    memset(&climb, 0, sizeof climb);
    climb.g = g;
    climb.ending = -1;
    if (!climb_possible(g)) {
        return 0;
    }
    n = climb_count(g);
    climb.hero = climb_at(g, g->rand_below(n));
    if (climb.hero < 0) {
        return 0;
    }
    r = g->record(climb.hero);
    climb.hero_id = adv_identity(g, climb.hero);
    climb.female = g->female(r) ? 1 : 0;
    g->name(r, climb.name, sizeof climb.name);
    /* "Go with the plan". */
    climb.falls = adv_percent(g, 50);
    climb.award = adv_award_roll(g, ADV_KIND_TECH, 2);
    /* "Follow the scientists' advice". */
    climb.gain = 10 + g->rand_below(11);
    climb_compose(g);
    climb_find_tallest(g);
    climb.ready = 1;
    for (set = 0; set <= CLIMB_ENDINGS; ++set) {
        climb.ready &= climb_set(set)->count > 0;
    }
    return climb.ready;
}

/* ---- The effects --------------------------------------------------------------------------------------------- */

static int climb_same(void) {
    return climb.g != NULL && climb.g->record(climb.hero) != NULL && adv_identity(climb.g, climb.hero) == climb.hero_id;
}

/* Ending `e`'s effects, made once. */
static void climb_effects(int e) {
    const adv_game *g = climb.g;
    if (!climb_same()) {
        return;
    }
    switch (e) {
    case CLIMB_E_FALL:
        g->kill(climb.hero);
        break;
    case CLIMB_E_SUMMIT:
        g->skill(climb.hero, ADV_SKILL_RESEARCH, CLIMB_RESEARCH_MAX);     /* capped: the game's maximum */
        g->award(ADV_KIND_TECH, climb.award);
        g->celebrate();
        break;
    case CLIMB_E_ADVICE:
        g->skill(climb.hero, ADV_SKILL_RESEARCH, climb.gain);
        break;
    default:
        break;
    }
}

/* ---- As a dialog shows it (adv_flow) --------------------------------------------------------------------------- */

static const adv_pages *climb_flow_question(int node) {
    (void)node;
    return &climb.intro;
}

static void climb_flow_label(int node, int which, char *out, int cap) {
    (void)node;
    climb_piece(out, cap, which ? CLIMB_LABEL_ADVICE : CLIMB_LABEL_PLAN, 0);
}

/* The answer `choice` (0 "Go with the plan", 1 "Follow the scientists' advice"): its ending, with its effects. */
static int climb_flow_answer(int node, int choice) {
    (void)node;
    if (!climb.ready || climb.answered) {
        return ADV_ENDING(climb.ending >= 0 ? climb.ending : CLIMB_E_ADVICE);
    }
    climb.answered = 1;
    climb.choice = choice != 0;
    climb.ending = climb.choice ? CLIMB_E_ADVICE : (climb.falls ? CLIMB_E_FALL : CLIMB_E_SUMMIT);
    climb_effects(climb.ending);
    return ADV_ENDING(climb.ending);
}

static const adv_pages *climb_flow_ending(int e) {
    return &climb.endings[e >= 0 && e < CLIMB_ENDINGS ? e : CLIMB_E_ADVICE];
}

static const char *climb_flow_tallest(void) {
    return climb_set(climb.tallest_set)->text[climb.tallest_page];
}

static int climb_flow_subject(void) {
    return climb.hero;
}

static void climb_flow_title(char *out, int cap) {
    climb_piece(out, cap, CLIMB_TITLE, 0);
}

static const adv_flow CLIMB_FLOW = {
    climb_flow_question, climb_flow_label, climb_flow_answer, climb_flow_ending, climb_flow_tallest,
    climb_flow_subject, climb_flow_title
};
