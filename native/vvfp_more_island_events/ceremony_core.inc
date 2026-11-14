/* The Remembrance Ceremony and The Rumblings: the owner's single-popup island events for all five games
   (2026-11-13).  Included by vvfp_more_island_events.c after adv_core.inc, adv_log.inc and ceremony_text.inc; each
   game's side (its own records, actions, structures and its single-result popup) is in ceremony_games.inc.

   THE SHARED SINGLE-RESULT PATH.  Both events are one popup with OK only, like the games' own single-result island
   events: no question, no pages of our own, the game's own popup (A New Home / The Lost Children: the island event's
   text buffer, which the game's own popup shows and scrolls; the later three: an event object built from a copy of a
   stock simple event's virtual table).  The effects are made as the popup is built -- "when the popup shows", as the
   games' own single-result events make theirs -- and the event keeps ONE Island Events log entry (adv_log.inc), its
   own lines saying what the comparison of the villagers cannot (each damaged structure).  Each event has its own
   place in its game's draw, as likely as one stock event, and can come again.

   THE REMEMBRANCE CEREMONY (src/vv_remembrance_ceremony.py has the same rules):
     when    the game's own grave count is at least 1 (cr_game.graves) -- New Believers also needs The Last Heathen
             (project 25) done (cr_game.heathens_done);
     who     every villager the game's records hold as living and present (cr_game.goes): children, babies that are
             records, nursing mothers and fathers, the protected villagers, puzzle workers -- no one left out (the
             owner); New Believers' believers only;
     what    each is sent on its own through the game's own action starter, as the game's own Day of Honor starts
             each one (cr_game.send: the stop, then the action -- so the stock group filters leave no one out); the
             place and the action as ceremony_games.inc says for each game;
     food    the feast quietly uses 10 food for every villager the game counts, never below 0 (cr_game.feast:
             Blessings Day's own rule).
   THE RUMBLINGS (src/vv_the_rumblings.py):
     when    every puzzle on the game's own Puzzles screen is solved (cr_game.puzzles_done) and at least one of the
             structures the event may damage is finished (cr_game.finished: population huts, the clothing hut, the
             love shack, the nursery school, the hospital -- whichever the game has and is not itself a puzzle);
     what    each finished one is damaged with rand(100) < 25; none drawn: one of them, each equally likely; each
             damaged one loses 10 + rand(91) percent of its building work (cr_game.damage: only states the game's own
             construction passes through; 100% is the game's new-village state).  No one is hurt, nobody leaves. */

#include "../shared/structure_damage.h"   /* The Rumblings' structures (shared with the Story DLL's "damage") */

#define CR_REMEMBRANCE 0
#define CR_RUMBLINGS 1
#define CR_EVENTS 2
#define CR_MAX_STRUCTURES 8
#define CR_DAMAGE_PERCENT 25
#define CR_LOSS_LO 10
#define CR_LOSS_SPAN 91                       /* 10..100 */
#define CR_FOOD_PER_VILLAGER 10
#define CR_HONOR_PERCENT 50
#define CR_HOVEL_PERCENT 50

typedef struct cr_game {
    int game;
    int (*count)(void);                       /* the records */
    int (*rand_below)(int n);                 /* the game's own rand() % n */
    /* The Remembrance Ceremony. */
    int (*graves)(void);                      /* the game's own grave count */
    int (*heathens_done)(void);               /* New Believers: The Last Heathen done; NULL elsewhere */
    int (*goes)(int index);                   /* a living, present villager (New Believers: a believer) */
    int (*send)(int index);                   /* started: what it does (CR_ACT_*) */
    int (*feast)(void);                       /* the food used */
    /* The Rumblings. */
    int (*puzzles_done)(void);
    int structures;
    const char *const *structure_names;       /* the log's words */
    int (*finished)(int k);
    void (*damage)(int k, int loss);
    int text_width;                           /* A New Home / The Lost Children: the popup's line (it does not wrap) */
} cr_game;

enum { CR_ACT_NONE = 0, CR_ACT_HONOR, CR_ACT_REFLECT, CR_ACT_HOVEL_HONOR, CR_ACT_HOVEL_REFLECT };

static struct {
    const cr_game *g;
    int which;                                /* the event shown last, -1 none */
    int sent, hovel;                          /* Remembrance: the villagers sent; those sent to the hovel */
    int acts[256];                            /* each record's CR_ACT_* (the tests) */
    int food;                                 /* the food the feast used */
    int candidates;                           /* Rumblings: the finished structures */
    int damaged[CR_MAX_STRUCTURES];           /* each structure's loss, 0 not damaged */
    int forced;                               /* none was drawn: one picked */
    int effects_made;
} cr;

static char cr_title_text[256];
static char cr_body_text[ADV_PAGE_BYTES];

/* Piece `key` in the player's language when a translation has it. */
static void cr_piece(char *out, int cap, int key) {
    const adv_piece_text *t = &CR_TEXT[key];
    const char *shown = vvfp_trf(t->stem[0], t->english[0], t->english[0], out, (unsigned int)cap);
    if (shown != out) {
        adv_copy(out, cap, shown);
    }
}

/* Whether `which` can happen now. */
static int cr_possible(const cr_game *g, int which) {
    int k;
    if (g == NULL) {
        return 0;
    }
    if (which == CR_REMEMBRANCE) {
        return g->graves() >= 1 && (g->heathens_done == NULL || g->heathens_done());
    }
    if (!g->puzzles_done()) {
        return 0;
    }
    for (k = 0; k < g->structures; ++k) {
        if (g->finished(k)) {
            return 1;
        }
    }
    return 0;
}

static int cr_possible_safe(const cr_game *g, int which) {
    int possible = 0;
    __try {
        possible = cr_possible(g, which);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        possible = 0;
    }
    return possible;
}

/* The title and the words of `which`, in the player's language. */
static void cr_compose(int which) {
    cr_piece(cr_title_text, sizeof cr_title_text, which == CR_REMEMBRANCE ? RC_TITLE : RB_TITLE);
    cr_piece(cr_body_text, sizeof cr_body_text, which == CR_REMEMBRANCE ? RC_TEXT : RB_TEXT);
}

static void cr_log_line(const char *a, const char *b, int number, const char *c) {
    char digits[16];
    int d = 0;
    unsigned int u = number < 0 ? 0u : (unsigned int)number;
    char line[256];
    char rev[16];
    do {
        rev[d++] = (char)('0' + u % 10u);
        u /= 10u;
    } while (u != 0u && d < 15);
    for (u = 0; (int)u < d; ++u) {
        digits[u] = rev[d - 1 - (int)u];
    }
    digits[d] = '\0';
    adv_copy(line, sizeof line, a);
    adv_cat(line, sizeof line, b);
    adv_cat(line, sizeof line, digits);
    adv_cat(line, sizeof line, c);
    adv_log_extra(line);
}

/* The Remembrance Ceremony's effects: everyone sent, the feast. */
static void cr_remembrance(const cr_game *g) {
    int i, count = g->count();
    for (i = 0; i < count && i < 256; ++i) {
        int act = CR_ACT_NONE;
        __try {
            if (g->goes(i)) {
                act = g->send(i);
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            act = CR_ACT_NONE;
        }
        cr.acts[i] = act;
        if (act != CR_ACT_NONE) {
            ++cr.sent;
            if (act == CR_ACT_HOVEL_HONOR || act == CR_ACT_HOVEL_REFLECT) {
                ++cr.hovel;
            }
        }
    }
    __try {
        cr.food = g->feast();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        cr.food = 0;
    }
    cr_log_line("  Villagers at the ceremony: ", "", cr.sent, "\n");
    if (cr.hovel > 0) {
        cr_log_line("  Of them at the old Heathen hovel: ", "", cr.hovel, "\n");
    }
}

/* The Rumblings' effects: each finished structure 25%, at least one; each damaged one loses 10..100%. */
static void cr_rumblings(const cr_game *g) {
    int list[CR_MAX_STRUCTURES];
    int k, n = 0, any = 0;
    for (k = 0; k < g->structures && k < CR_MAX_STRUCTURES; ++k) {
        if (g->finished(k)) {
            list[n++] = k;
        }
    }
    cr.candidates = n;
    if (n == 0) {
        return;
    }
    for (k = 0; k < n; ++k) {
        if (g->rand_below(100) < CR_DAMAGE_PERCENT) {
            cr.damaged[list[k]] = -1;
            any = 1;
        }
    }
    if (!any) {
        cr.damaged[list[g->rand_below(n)]] = -1;
        cr.forced = 1;
    }
    for (k = 0; k < g->structures && k < CR_MAX_STRUCTURES; ++k) {
        if (cr.damaged[k] != 0) {
            int loss = CR_LOSS_LO + g->rand_below(CR_LOSS_SPAN);
            cr.damaged[k] = loss;
            __try {
                g->damage(k, loss);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
            static char named[128];
            adv_copy(named, sizeof named, g->structure_names[k]);
            adv_cat(named, sizeof named, ", ");
            cr_log_line("  Damaged: ", named, loss,
                        loss >= 100 ? "% of its building work lost (back to unbuilt)\n"
                                    : "% of its building work lost\n");
        }
    }
}

static void cr_effects(int which) {
    const cr_game *g = cr.g;
    if (g == NULL || cr.effects_made) {
        return;
    }
    cr.effects_made = 1;
    if (which == CR_REMEMBRANCE) {
        cr_remembrance(g);
    } else {
        cr_rumblings(g);
    }
}

/* `which` drawn for the popup about to be shown: its words composed, its effects made, its one log entry. */
static void cr_happen(const cr_game *g, int which) {
    memset(&cr, 0, sizeof cr);
    cr.g = g;
    cr.which = which;
    cr_compose(which);
    adv_log_event(g->game, cr_title_text);
    adv_log_effects(cr_effects, which);
}
