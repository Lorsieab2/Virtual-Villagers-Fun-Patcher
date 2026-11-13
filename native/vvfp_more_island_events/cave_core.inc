/* The Cave Explorers: the owner's island event for A New Home (2026-11-12).  Included by vvfp_more_island_events.c
   after adv_core.inc, whose words, pages, rolls and effects it shares; adv_vv1.inc shows it in A New Home's
   encounter dialog (adv_flow: three questions in a row).

   WHO (the owner, 2026-11-12): only once The Cave puzzle is done (adv_game.cave_open); two villagers who may go on
   The Aspiring Adventurer (adv_game.eligible: alive and present, not carrying a baby, not the Golden Child), each 18
   or more (360 age units), at most 5 years (100 age units) apart.  The pair (name1, name2) is drawn among every
   such ordered pair, each equally likely.  No such pair: the event cannot happen.

   THE ROLLS (src/vv_cave_explorers.py has the same numbers), all made with the game's own random routine when the
   popup is built, so every page can say what happens:
     "Explore the Cave" -> "Proceed Further": 50% A (the scream), 50% B (the find).
       A: the screamer name1 or name2 (1 in 2), "what's wrong" one of four (1 in 4); then either run answer: 10% the
          argument, 80% they make up, 10% the chasm (the one who slips: name1 or name2, 1 in 2) -- both disappear,
          no graves, no food.
       B: the finder name1 or name2 (1 in 2); 10% a map (both leave for a strange place: they disappear, no
          graves), 30% gold coins (a normal tech award), 30% a treasure map (a huge one: 3x), 30% preserved food
          (a large food award: 2x).
     "Stay Here" -> "You're right, I'll return them.": food or tech points (1 in 2), a normal award;
                 -> "Curses schmurses. I'm keeping them.": 80% the researchers (a normal tech award), 10% name2 dies
                    and then name1 (two graves), 10% name2 dies (one grave).
   An award is adv_award_roll's (the game's stock island-event range, times 1, 2 or 3, then Island Events Scale).

   THE EFFECTS are made when the answer that leads to their page is clicked (adv_choose's rule): the dialog is modal,
   the village does not run and no save can come between the click and the pages, so the Island Events log's
   comparison around that click records them, under the event's title with the answer clicked.  "Dies" is the
   game's own death (health 0: a body, a grave, "Unknown causes"); "disappears" the game's own removal with no body,
   told to the Cause of Death companion (VvfpCauseVanishedBy). */

#define CAVE_ADULT_UNITS 360                 /* 18 years */
#define CAVE_GAP_UNITS 100                   /* 5 years */

enum { CAVE_Q_START = 0, CAVE_Q_DEEPER, CAVE_Q_RUN, CAVE_Q_STAY, CAVE_QUESTIONS };
enum { CAVE_E_DONT = 0, CAVE_E_FIND, CAVE_E_LEFT, CAVE_E_RIGHT, CAVE_E_RETURN, CAVE_E_KEEP, CAVE_ENDINGS };
enum { CAVE_END_ARGUE = 0, CAVE_END_MAKEUP = 1, CAVE_END_CHASM = 2 };
enum { CAVE_MAP = 0, CAVE_COINS = 1, CAVE_TREASURE = 2, CAVE_FOOD = 3 };
enum { CAVE_RESEARCH = 0, CAVE_BOTH_DIE = 1, CAVE_ONE_DIES = 2 };

static const int CAVE_LABELS[CAVE_QUESTIONS][2] = {
    { CAVE_LABEL_EXPLORE, CAVE_LABEL_DONT }, { CAVE_LABEL_PROCEED, CAVE_LABEL_STAY },
    { CAVE_LABEL_LEFT, CAVE_LABEL_RIGHT }, { CAVE_LABEL_RETURN, CAVE_LABEL_KEEP } };

static struct {
    const adv_game *g;
    int ready, ended;
    int who[2];                                   /* name1's and name2's records */
    unsigned int id[2];
    int female[2];
    char name[2][ADV_NAME_BYTES];
    int scream_a;                                 /* "Proceed Further": 1 A, 0 B */
    int screamer, wrong, a_end, faller;           /* A: 0 name1 / 1 name2; WRONG 0..3; CAVE_END_ARGUE..; 0/1 */
    int finder, find, find_award;                 /* B: 0/1; CAVE_MAP..; the award */
    int return_food, return_award;                /* "You're right": 1 food, 0 tech */
    int keep_end, keep_award;                     /* "Curses schmurses": CAVE_RESEARCH.. */
    int answers[3], answered;                     /* each answer clicked (0 the first button), how many */
    int ending;                                   /* the ending reached, -1 none yet */
    adv_pages question[CAVE_QUESTIONS];
    adv_pages endings[CAVE_ENDINGS];
    int tallest_set, tallest_page;
} cave;

/* ---- Who ----------------------------------------------------------------------------------------------------- */

static int cave_adult(const adv_game *g, const unsigned char *r) {
    return r != NULL && g->eligible(r) && g->age(r) >= CAVE_ADULT_UNITS;
}

/* The ordered pairs (name1, name2) who may go: k >= 0 the k-th one into *a, *b; returns how many there are. */
static int cave_pairs(const adv_game *g, int k, int *a, int *b) {
    int i, j, n = 0, count = g->count();
    for (i = 0; i < count; ++i) {
        const unsigned char *ri = g->record(i);
        if (!cave_adult(g, ri)) {
            continue;
        }
        for (j = 0; j < count; ++j) {
            const unsigned char *rj = g->record(j);
            int gap;
            if (j == i || !cave_adult(g, rj)) {
                continue;
            }
            gap = g->age(ri) - g->age(rj);
            if (gap < 0) {
                gap = -gap;
            }
            if (gap > CAVE_GAP_UNITS) {
                continue;
            }
            if (n == k) {
                *a = i;
                *b = j;
            }
            ++n;
        }
    }
    return n;
}

/* The event's condition (the owner): The Cave puzzle done and a pair who may go. */
static int cave_possible(const adv_game *g) {
    int a, b;
    return g != NULL && g->age != NULL && g->cave_open != NULL && g->cave_open() && cave_pairs(g, -1, &a, &b) > 0;
}

/* ---- Words --------------------------------------------------------------------------------------------------- */

/* Which of the two a letter of the text's names is (cave_text.inc: a name1, b name2, s the screamer, o the other,
   r the finder, c the one who slips, d the other). */
static int cave_index(char who) {
    switch (who) {
    case 'b': return 1;
    case 's': return cave.screamer;
    case 'o': return 1 - cave.screamer;
    case 'r': return cave.finder;
    case 'c': return cave.faller;
    case 'd': return 1 - cave.faller;
    default: return 0;
    }
}

static const char *cave_name_of(char who) {
    return cave.name[cave_index(who)];
}

/* Piece `key` with the names, the pronouns of each villager it speaks of and `number` filled in, in the player's
   language when a translation has it. */
static void cave_piece(char *out, int cap, int key, int number) {
    static char filled[ADV_PIECE_BYTES];
    const cave_piece_text *t = &CAVE_TEXT[key];
    const char *shown;
    int form = 0, k;
    for (k = 0; t->pronouns[k] != '\0'; ++k) {
        form |= cave.female[cave_index(t->pronouns[k])] << k;
    }
    adv_fill(filled, sizeof filled, t->english[form], t->names, number, cave_name_of);
    shown = vvfp_trf(t->stem[form], t->english[form], filled, out, (unsigned int)cap);
    if (shown != out) {
        adv_copy(out, cap, shown);
    }
}

static char cave_buf[6][ADV_PIECE_BYTES];

/* "<a><sep><b>": two pieces as one paragraph (b < 0: a alone). */
static const char *cave_join(int slot, int a, const char *sep, int b, int number) {
    static char second[ADV_PIECE_BYTES];
    cave_piece(cave_buf[slot], ADV_PIECE_BYTES, a, number);
    if (b >= 0) {
        cave_piece(second, sizeof second, b, number);
        adv_cat(cave_buf[slot], ADV_PIECE_BYTES, sep);
        adv_cat(cave_buf[slot], ADV_PIECE_BYTES, second);
    }
    return cave_buf[slot];
}

static const char *cave_one(int slot, int key) {
    return cave_join(slot, key, "", -1, 0);
}

static void cave_compose(const adv_game *g) {
    static const int WRONG[4] = { CAVE_WRONG_1, CAVE_WRONG_2, CAVE_WRONG_3, CAVE_WRONG_4 };
    static const int FINDS[4] = { CAVE_FIND_MAP, CAVE_FIND_COINS, CAVE_FIND_TREASURE, CAVE_FIND_FOOD };
    static const int KEEPS[3] = { CAVE_KEEP_RESEARCH, CAVE_KEEP_BOTH, CAVE_KEEP_ONE };
    const char *p[4];
    int side;
    p[0] = cave_one(0, CAVE_INTRO); p[1] = NULL;
    adv_popup(g, &cave.question[CAVE_Q_START], p);
    p[0] = cave_one(0, CAVE_EXPLORE_1); p[1] = cave_one(1, CAVE_EXPLORE_2); p[2] = NULL;
    adv_popup(g, &cave.question[CAVE_Q_DEEPER], p);
    p[0] = cave_one(0, CAVE_DEEPER); p[1] = cave_join(1, CAVE_A_SCREAM, " ", WRONG[cave.wrong], 0);
    p[2] = cave_one(2, CAVE_RUN); p[3] = NULL;
    adv_popup(g, &cave.question[CAVE_Q_RUN], p);
    p[0] = cave_one(0, CAVE_STAY); p[1] = NULL;
    adv_popup(g, &cave.question[CAVE_Q_STAY], p);

    p[0] = cave_one(0, CAVE_DONT); p[1] = NULL;
    adv_popup(g, &cave.endings[CAVE_E_DONT], p);
    p[0] = cave_one(0, CAVE_DEEPER); p[1] = cave_join(1, CAVE_B_SEARCH, " ", FINDS[cave.find], cave.find_award);
    p[2] = NULL;
    adv_popup(g, &cave.endings[CAVE_E_FIND], p);
    for (side = 0; side < 2; ++side) {
        p[0] = cave_one(0, side == 0 ? CAVE_RUN_LEFT : CAVE_RUN_RIGHT);
        if (cave.a_end == CAVE_END_ARGUE) {
            p[1] = cave_one(1, CAVE_ARGUE); p[2] = cave_one(2, CAVE_ARGUE_2); p[3] = NULL;
        } else {
            p[1] = cave_one(1, cave.a_end == CAVE_END_MAKEUP ? CAVE_MAKEUP : CAVE_CHASM); p[2] = NULL;
        }
        adv_popup(g, &cave.endings[CAVE_E_LEFT + side], p);
    }
    p[0] = cave_join(0, cave.return_food ? CAVE_RETURN_FOOD : CAVE_RETURN_TECH, "", -1, cave.return_award);
    p[1] = NULL;
    adv_popup(g, &cave.endings[CAVE_E_RETURN], p);
    p[0] = cave_join(0, CAVE_KEEP, ", ", KEEPS[cave.keep_end], cave.keep_award); p[1] = NULL;
    adv_popup(g, &cave.endings[CAVE_E_KEEP], p);
}

static const adv_pages *cave_set(int set) {
    return set < CAVE_QUESTIONS ? &cave.question[set] : &cave.endings[set - CAVE_QUESTIONS];
}

static void cave_find_tallest(const adv_game *g) {
    int set, k, best = -1, best_len = -1;
    cave.tallest_set = 0;
    cave.tallest_page = 0;
    for (set = 0; set < CAVE_QUESTIONS + CAVE_ENDINGS; ++set) {
        const adv_pages *pages = cave_set(set);
        for (k = 0; k < pages->count; ++k) {
            int lines = adv_lines(g, pages->text[k]);
            int len = adv_len(pages->text[k]);
            if (lines > best || (lines == best && len > best_len)) {
                best = lines;
                best_len = len;
                cave.tallest_set = set;
                cave.tallest_page = k;
            }
        }
    }
}

/* Who goes, every roll and every page, for the popup about to be built; 0 when the event cannot happen. */
static int cave_begin(const adv_game *g) {
    int n, roll, set;
    memset(&cave, 0, sizeof cave);
    cave.g = g;
    cave.ending = -1;
    if (!cave_possible(g)) {
        return 0;
    }
    n = cave_pairs(g, -1, &cave.who[0], &cave.who[1]);
    cave_pairs(g, g->rand_below(n), &cave.who[0], &cave.who[1]);
    for (n = 0; n < 2; ++n) {
        const unsigned char *r = g->record(cave.who[n]);
        cave.id[n] = adv_identity(g, cave.who[n]);
        cave.female[n] = g->female(r) ? 1 : 0;
        g->name(r, cave.name[n], ADV_NAME_BYTES);
    }
    /* "Proceed Further". */
    cave.scream_a = adv_percent(g, 50);
    cave.screamer = g->rand_below(2);
    cave.wrong = g->rand_below(4);
    roll = g->rand_below(100);
    cave.a_end = roll < 10 ? CAVE_END_ARGUE : (roll < 90 ? CAVE_END_MAKEUP : CAVE_END_CHASM);
    cave.faller = g->rand_below(2);
    cave.finder = g->rand_below(2);
    roll = g->rand_below(100);
    cave.find = roll < 10 ? CAVE_MAP : (roll < 40 ? CAVE_COINS : (roll < 70 ? CAVE_TREASURE : CAVE_FOOD));
    if (cave.find == CAVE_COINS) {
        cave.find_award = adv_award_roll(g, ADV_KIND_TECH, 1);
    } else if (cave.find == CAVE_TREASURE) {
        cave.find_award = adv_award_roll(g, ADV_KIND_TECH, 3);
    } else if (cave.find == CAVE_FOOD) {
        cave.find_award = adv_award_roll(g, ADV_KIND_FOOD, 2);
    }
    /* "Stay Here". */
    cave.return_food = g->rand_below(2) == 0;
    cave.return_award = adv_award_roll(g, cave.return_food ? ADV_KIND_FOOD : ADV_KIND_TECH, 1);
    roll = g->rand_below(100);
    cave.keep_end = roll < 80 ? CAVE_RESEARCH : (roll < 90 ? CAVE_BOTH_DIE : CAVE_ONE_DIES);
    cave.keep_award = adv_award_roll(g, ADV_KIND_TECH, 1);
    cave_compose(g);
    cave_find_tallest(g);
    cave.ready = 1;
    for (set = 0; set < CAVE_QUESTIONS + CAVE_ENDINGS; ++set) {
        cave.ready &= cave_set(set)->count > 0;
    }
    return cave.ready;
}

/* ---- The effects --------------------------------------------------------------------------------------------- */

/* Villager `k` (0 name1, 1 name2) is still who the popup is about. */
static int cave_same(int k) {
    return cave.g != NULL && cave.g->record(cave.who[k]) != NULL && adv_identity(cave.g, cave.who[k]) == cave.id[k];
}

static void cave_kill(int k) {
    if (cave_same(k)) {
        cave.g->kill(cave.who[k]);
    }
}

static void cave_vanish(int k, const char *what) {
    if (cave_same(k)) {
        cave.g->vanish(cave.who[k]);
        adv_tell_vanished(cave.g->game, cave.who[k], what);
    }
}

static void cave_award(int kind, int amount) {
    if (cave_same(0) || cave_same(1)) {
        cave.g->award(kind, amount);
    }
}

/* Ending `e`'s effects, made once. */
static void cave_effects(int e) {
    switch (e) {
    case CAVE_E_FIND:
        if (cave.find == CAVE_MAP) {
            cave_vanish(0, "Disappeared in The Cave Explorers (left for a strange place)");
            cave_vanish(1, "Disappeared in The Cave Explorers (left for a strange place)");
        } else {
            cave_award(cave.find == CAVE_FOOD ? ADV_KIND_FOOD : ADV_KIND_TECH, cave.find_award);
        }
        break;
    case CAVE_E_LEFT:
    case CAVE_E_RIGHT:
        if (cave.a_end == CAVE_END_CHASM) {
            cave_vanish(cave.faller, "Disappeared in The Cave Explorers (fell down a chasm)");
            cave_vanish(1 - cave.faller, "Disappeared in The Cave Explorers (fell down a chasm)");
        }
        break;
    case CAVE_E_RETURN:
        cave_award(cave.return_food ? ADV_KIND_FOOD : ADV_KIND_TECH, cave.return_award);
        break;
    case CAVE_E_KEEP:
        if (cave.keep_end == CAVE_RESEARCH) {
            cave_award(ADV_KIND_TECH, cave.keep_award);
        } else {
            cave_kill(1);                         /* name2 first, as the words tell it */
            if (cave.keep_end == CAVE_BOTH_DIE) {
                cave_kill(0);
            }
        }
        break;
    default:
        break;
    }
}

/* ---- As a dialog shows it (adv_flow) --------------------------------------------------------------------------- */

static const adv_pages *cave_flow_question(int node) {
    return &cave.question[node >= 0 && node < CAVE_QUESTIONS ? node : 0];
}

static void cave_flow_label(int node, int which, char *out, int cap) {
    cave_piece(out, cap, CAVE_LABELS[node >= 0 && node < CAVE_QUESTIONS ? node : 0][which != 0], 0);
}

/* The answer `choice` (0 the first button) to question `node`: the next question, or an ending with its effects. */
static int cave_flow_answer(int node, int choice) {
    int next;
    if (!cave.ready || cave.ending >= 0 || node < 0 || node >= CAVE_QUESTIONS || cave.answered >= 3) {
        return ADV_ENDING(cave.ending >= 0 ? cave.ending : CAVE_E_DONT);
    }
    choice = choice != 0;
    cave.answers[cave.answered++] = choice;
    switch (node) {
    case CAVE_Q_START: next = choice ? ADV_ENDING(CAVE_E_DONT) : CAVE_Q_DEEPER; break;
    case CAVE_Q_DEEPER: next = choice ? CAVE_Q_STAY : (cave.scream_a ? CAVE_Q_RUN : ADV_ENDING(CAVE_E_FIND)); break;
    case CAVE_Q_RUN: next = ADV_ENDING(choice ? CAVE_E_RIGHT : CAVE_E_LEFT); break;
    default: next = ADV_ENDING(choice ? CAVE_E_KEEP : CAVE_E_RETURN); break;
    }
    if (next < 0) {
        cave.ending = -1 - next;
        cave_effects(cave.ending);
    }
    return next;
}

static const adv_pages *cave_flow_ending(int e) {
    return &cave.endings[e >= 0 && e < CAVE_ENDINGS ? e : 0];
}

static const char *cave_flow_tallest(void) {
    return cave_set(cave.tallest_set)->text[cave.tallest_page];
}

static int cave_flow_subject(void) {
    return cave.who[0];
}

static void cave_flow_title(char *out, int cap) {
    cave_piece(out, cap, CAVE_TITLE, 0);
}

static const adv_flow CAVE_FLOW = {
    cave_flow_question, cave_flow_label, cave_flow_answer, cave_flow_ending, cave_flow_tallest, cave_flow_subject,
    cave_flow_title
};
