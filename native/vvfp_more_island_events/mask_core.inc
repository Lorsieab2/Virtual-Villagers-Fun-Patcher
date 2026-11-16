/* The Mysterious Mask: the owner's island event for The Tree of Life (2026-11-13).  Included by
   vvfp_more_island_events.c after adv_core.inc and adv_log.inc, whose words, pages, picker test, effects and log it
   shares; mask_vv4.inc shows it in The Tree of Life's own island-event dialog with FOUR answers (adv_vv345.inc and the
   shared multi-answer popup, native/shared/vvfp_multi_answer.h: adv_flow.answers returns 4).

   WHO (the owner, 2026-11-13), every one passing the owner's protected check (adv_is_protected: never a villager
   carrying a baby, mother or father, nor a body or ghost), family ties never asked:
     * the GROUP: 2 to 4 children under 14 (280 age units), alive and present -- 4 when there are 4 or more, else all
       of them; name1, the finder, and name2 are two of them; each drawn among those left, each equally likely;
     * the EXPEDITION: 5 villagers of 18 or more (360 age units) who may be picked (adv_game.eligible), drawn alike;
     * the village's population 61 or more, as The Lost Children's "A Dangerous Mission" counts it (the living
       villagers plus the babies they carry: mk_game.population).
   The event can happen only while all three hold (two eligible villagers overall then always do).

   THE ROLLS (src/vv_mysterious_mask.py has the same numbers), made with the game's own random routine when the popup
   is built: after either walk, home safe (A) 50%, else lost (B); lost: captured (C) 25%, else rescued (D).

   THE EFFECTS wait for their own page (the owner's standing rule): an ending's are made, once, when the page that ends
   its text (the elders' page F) is shown, with the event's one Island Events log entry:
     every ending  the five volunteers leave for good -- gone, no body, no grave (adv_game.vanish), the Cause of Death
                   companion told for each;
     C             every child of the group too.

   THE PAGES are laid out MK_LINES_LESS lines shorter for each answer past two (The Troubling Signs' rule): the popup
   also holds the two more answer buttons, so it is no taller than a two-answer one. */

#define MK_CHILD_UNITS 280                   /* under 14 */
#define MK_ADULT_UNITS 360                   /* 18 or more */
#define MK_POPULATION 61
#define MK_GROUP_MAX 4
#define MK_GROUP_MIN 2
#define MK_EXPEDITION 5
#define MK_ANSWERS 4
#define MK_LINES_LESS 3                      /* lines a page loses for each answer past two */

enum { MK_A_WAIT = 0, MK_A_CRY, MK_A_CLEARING, MK_A_FOREST };
enum { MK_E_WAIT = 0, MK_E_CRY, MK_E_CLEARING_HOME, MK_E_CLEARING_CAPTURED, MK_E_CLEARING_RESCUED, MK_E_FOREST_HOME,
       MK_E_FOREST_CAPTURED, MK_E_FOREST_RESCUED, MK_ENDINGS };

typedef struct mk_game {
    const adv_game *g;
    int (*age)(const unsigned char *record);            /* age units */
    int (*alive)(const unsigned char *record);          /* present, living, not a body or ghost */
    int (*population)(void);                            /* the living plus the babies carried */
} mk_game;

static struct {
    const mk_game *t;
    const adv_game *g;
    int ready, answered, choice;
    int group[MK_GROUP_MAX], group_count;               /* record indexes: [0] name1, [1] name2 */
    unsigned int group_id[MK_GROUP_MAX];
    int volunteer[MK_EXPEDITION];
    unsigned int volunteer_id[MK_EXPEDITION];
    int female;                                         /* name1 */
    char name1[ADV_NAME_BYTES], name2[ADV_NAME_BYTES];
    int home;                                           /* a walk: 1 home safe (A), 0 lost (B) */
    int captured;                                       /* lost: 1 captured (C), 0 rescued (D) */
    int ending;                                         /* -1 none yet */
    int effects_made, gone;                             /* gone: the villagers the effects took */
    adv_pages intro;
    adv_pages endings[MK_ENDINGS];
    int tallest_set, tallest_page;
} mk;

/* ---- Who ----------------------------------------------------------------------------------------------------- */

static int mk_child(const mk_game *t, const unsigned char *r) {
    return r != NULL && t->alive(r) && t->age(r) < MK_CHILD_UNITS && !adv_is_protected(t->g->game, r);
}

static int mk_adult(const mk_game *t, const unsigned char *r) {
    return r != NULL && t->g->eligible(r) && t->age(r) >= MK_ADULT_UNITS;
}

static int mk_taken(const int *taken, int n, int index) {
    int k;
    for (k = 0; k < n; ++k) {
        if (taken[k] == index) {
            return 1;
        }
    }
    return 0;
}

/* How many of `adult` (1) or children (0) may be picked, none of `taken`; mk_at: the k-th of them, or -1. */
static int mk_count(const mk_game *t, int adult, const int *taken, int n) {
    int i, c = 0, count = t->g->count();
    for (i = 0; i < count; ++i) {
        const unsigned char *r = t->g->record(i);
        c += !mk_taken(taken, n, i) && (adult ? mk_adult(t, r) : mk_child(t, r));
    }
    return c;
}

static int mk_at(const mk_game *t, int adult, const int *taken, int n, int k) {
    int i, count = t->g->count();
    for (i = 0; i < count; ++i) {
        const unsigned char *r = t->g->record(i);
        if (!mk_taken(taken, n, i) && (adult ? mk_adult(t, r) : mk_child(t, r)) && k-- == 0) {
            return i;
        }
    }
    return -1;
}

static int mk_possible(const mk_game *t) {
    return t != NULL && t->g != NULL && t->population() >= MK_POPULATION && mk_count(t, 0, NULL, 0) >= MK_GROUP_MIN
        && mk_count(t, 1, NULL, 0) >= MK_EXPEDITION && adv_possible(t->g);
}

/* `want` of `adult` (1) or children (0) into `out`, each drawn among those left; the number drawn. */
static int mk_draw(const mk_game *t, int adult, int *out, int want) {
    int k;
    for (k = 0; k < want; ++k) {
        int n = mk_count(t, adult, out, k);
        if (n <= 0) {
            break;
        }
        out[k] = mk_at(t, adult, out, k, t->g->rand_below(n));
        if (out[k] < 0) {
            break;
        }
    }
    return k;
}

/* ---- Words --------------------------------------------------------------------------------------------------- */

static const char *mk_name_of(char who) {
    return who == 'b' ? mk.name2 : mk.name1;
}

static void mk_piece(char *out, int cap, int key) {
    static char filled[ADV_PIECE_BYTES];
    const adv_piece_text *p = &MK_TEXT[key];
    const char *shown;
    adv_fill(filled, sizeof filled, p->english[mk.female], p->names, 0, mk_name_of);
    shown = vvfp_trf(p->stem[mk.female], p->english[mk.female], filled, out, (unsigned int)cap);
    if (shown != out) {
        adv_copy(out, cap, shown);
    }
}

static char mk_buf[4][ADV_PIECE_BYTES * 2];

/* Paragraph `slot`: the pieces `keys` (-1 ends) joined with a space. */
static const char *mk_paragraph(int slot, const int *keys) {
    static char piece[ADV_PIECE_BYTES];
    char *out = mk_buf[slot];
    int k;
    out[0] = '\0';
    for (k = 0; k < 3 && keys[k] >= 0; ++k) {
        mk_piece(piece, sizeof piece, keys[k]);
        if (k > 0) {
            adv_cat(out, (int)sizeof mk_buf[slot], " ");
        }
        adv_cat(out, (int)sizeof mk_buf[slot], piece);
    }
    return out;
}

/* Ending `e`'s popups (src/vv_mysterious_mask.py paragraphs_of): the story, then the elders' page F. */
static void mk_compose_ending(const adv_game *layout, int e) {
    static const int STORY[MK_ENDINGS][3] = {
        { MK_WAIT, -1, -1 }, { MK_CRY, -1, -1 },
        { MK_CLEARING, MK_HOME, -1 }, { MK_CLEARING, MK_LOST, MK_CAPTURED }, { MK_CLEARING, MK_LOST, MK_RESCUED },
        { MK_FOREST, MK_HOME, -1 }, { MK_FOREST, MK_LOST, MK_CAPTURED }, { MK_FOREST, MK_LOST, MK_RESCUED } };
    static const int F[MK_ENDINGS] = { MK_F_WAITED, MK_F_CRIED, MK_F_BACK, MK_F_CAPTURED, MK_F_RESCUED, MK_F_BACK,
                                       MK_F_CAPTURED, MK_F_RESCUED };
    const char *p[5];
    int elders[3], appeal[3] = { MK_APPEAL, -1, -1 }, volunteers[3] = { MK_VOLUNTEERS, -1, -1 };
    int parents[3] = { MK_PARENTS, -1, -1 };
    p[0] = mk_paragraph(0, STORY[e]);
    p[1] = NULL;
    adv_popup(layout, &mk.endings[e], p);
    elders[0] = MK_ELDERS; elders[1] = F[e]; elders[2] = -1;
    p[0] = mk_paragraph(0, elders);
    p[1] = mk_paragraph(1, appeal);
    p[2] = mk_paragraph(2, volunteers);
    p[3] = mk_paragraph(3, parents);
    p[4] = NULL;
    adv_popup(layout, &mk.endings[e], p);
}

static void mk_compose(const adv_game *layout) {
    int intro[3] = { MK_INTRO, -1, -1 }, e;
    const char *p[2];
    p[0] = mk_paragraph(0, intro);
    p[1] = NULL;
    adv_popup(layout, &mk.intro, p);
    for (e = 0; e < MK_ENDINGS; ++e) {
        mk_compose_ending(layout, e);
    }
}

static const adv_pages *mk_set(int set) {
    return set == 0 ? &mk.intro : &mk.endings[set - 1];
}

static void mk_find_tallest(const adv_game *layout) {
    int set, k, best = -1, best_len = -1;
    mk.tallest_set = 0;
    mk.tallest_page = 0;
    for (set = 0; set <= MK_ENDINGS; ++set) {
        const adv_pages *pages = mk_set(set);
        for (k = 0; k < pages->count; ++k) {
            int lines = adv_lines(layout, pages->text[k]);
            int len = adv_len(pages->text[k]);
            if (lines > best || (lines == best && len > best_len)) {
                best = lines;
                best_len = len;
                mk.tallest_set = set;
                mk.tallest_page = k;
            }
        }
    }
}

/* The group, the expedition, every roll and every page, for the popup about to be built (`layout` lays the pages
   out); 0 when the event cannot happen. */
static int mk_begin(const mk_game *t, const adv_game *layout) {
    int k, n, set;
    memset(&mk, 0, sizeof mk);
    mk.t = t;
    mk.g = t != NULL ? t->g : NULL;
    mk.ending = -1;
    for (k = 0; k < MK_GROUP_MAX; ++k) {
        mk.group[k] = -1;
    }
    for (k = 0; k < MK_EXPEDITION; ++k) {
        mk.volunteer[k] = -1;
    }
    if (!mk_possible(t)) {
        return 0;
    }
    n = mk_count(t, 0, NULL, 0);
    mk.group_count = mk_draw(t, 0, mk.group, n < MK_GROUP_MAX ? n : MK_GROUP_MAX);
    if (mk.group_count < MK_GROUP_MIN || mk_draw(t, 1, mk.volunteer, MK_EXPEDITION) < MK_EXPEDITION) {
        return 0;
    }
    for (k = 0; k < mk.group_count; ++k) {
        mk.group_id[k] = adv_identity(t->g, mk.group[k]);
    }
    for (k = 0; k < MK_EXPEDITION; ++k) {
        mk.volunteer_id[k] = adv_identity(t->g, mk.volunteer[k]);
    }
    mk.female = t->g->female(t->g->record(mk.group[0])) ? 1 : 0;
    t->g->name(t->g->record(mk.group[0]), mk.name1, sizeof mk.name1);
    t->g->name(t->g->record(mk.group[1]), mk.name2, sizeof mk.name2);
    mk.home = adv_percent(t->g, 50);
    mk.captured = adv_percent(t->g, 25);
    mk_compose(layout);
    mk_find_tallest(layout);
    mk.ready = 1;
    for (set = 0; set <= MK_ENDINGS; ++set) {
        mk.ready &= mk_set(set)->count > 0;
    }
    return mk.ready;
}

/* ---- The effects --------------------------------------------------------------------------------------------- */

static int mk_still(int index, unsigned int id) {
    return index >= 0 && mk.g->record(index) != NULL && adv_identity(mk.g, index) == id;
}

/* Ending `e`'s effects, made once. */
static void mk_effects(int e) {
    const adv_game *g = mk.g;
    int k;
    if (g == NULL || mk.effects_made || e != mk.ending) {
        return;
    }
    mk.effects_made = 1;
    for (k = 0; k < MK_EXPEDITION; ++k) {
        if (mk_still(mk.volunteer[k], mk.volunteer_id[k])) {
            g->vanish(mk.volunteer[k]);
            adv_tell_vanished(g->game, mk.volunteer[k],
                              "Disappeared in The Mysterious Mask (left on the elders' expedition)");
            ++mk.gone;
        }
    }
    if (e == MK_E_CLEARING_CAPTURED || e == MK_E_FOREST_CAPTURED) {
        for (k = 0; k < mk.group_count; ++k) {
            if (mk_still(mk.group[k], mk.group_id[k])) {
                g->vanish(mk.group[k]);
                adv_tell_vanished(g->game, mk.group[k], "Disappeared in The Mysterious Mask (taken by masked strangers)");
                ++mk.gone;
            }
        }
    }
}

/* ---- As a dialog shows it (adv_flow) --------------------------------------------------------------------------- */

static const adv_pages *mk_flow_question(int node) {
    (void)node;
    return &mk.intro;
}

static void mk_flow_label(int node, int which, char *out, int cap) {
    static const int LABELS[MK_ANSWERS] = { MK_LABEL_WAIT, MK_LABEL_CRY, MK_LABEL_CLEARING, MK_LABEL_FOREST };
    (void)node;
    mk_piece(out, cap, LABELS[which >= 0 && which < MK_ANSWERS ? which : 0]);
}

static int mk_flow_answers(int node) {
    (void)node;
    return MK_ANSWERS;
}

/* The answer `choice` (0..3, top to bottom): its ending, its effects not yet made (they wait for their own page). */
static int mk_flow_choose(int node, int choice) {
    int walk;
    (void)node;
    if (!mk.ready || mk.answered) {
        return ADV_ENDING(mk.ending >= 0 ? mk.ending : MK_E_WAIT);
    }
    mk.answered = 1;
    mk.choice = choice >= 0 && choice < MK_ANSWERS ? choice : 0;
    if (mk.choice == MK_A_WAIT || mk.choice == MK_A_CRY) {
        mk.ending = mk.choice == MK_A_WAIT ? MK_E_WAIT : MK_E_CRY;
    } else {
        walk = mk.choice == MK_A_CLEARING ? MK_E_CLEARING_HOME : MK_E_FOREST_HOME;
        mk.ending = walk + (mk.home ? 0 : (mk.captured ? 1 : 2));
    }
    return ADV_ENDING(mk.ending);
}

static void mk_flow_effects(int e) {
    mk_effects(e);
}

static int mk_flow_answer(int node, int choice) {
    int next = mk_flow_choose(node, choice);
    mk_effects(-1 - next);
    return next;
}

static const adv_pages *mk_flow_ending(int e) {
    return &mk.endings[e >= 0 && e < MK_ENDINGS ? e : MK_E_WAIT];
}

static const char *mk_flow_tallest(void) {
    return mk_set(mk.tallest_set)->text[mk.tallest_page];
}

static int mk_flow_subject(void) {
    return mk.group[0];
}

static void mk_flow_title(char *out, int cap) {
    mk_piece(out, cap, MK_TITLE);
}

static const adv_flow MK_FLOW = {
    mk_flow_question, mk_flow_label, mk_flow_answer, mk_flow_ending, mk_flow_tallest,
    mk_flow_subject, mk_flow_title, mk_flow_choose, mk_flow_effects, mk_flow_answers
};
