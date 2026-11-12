/* The Aspiring Adventurer: what every game shares -- who may go, the rolls, the words and their pages, and the
   effects.  Included by vvfp_aspiring_adventurer.c; each game's file (adv_vv1.inc ... adv_vv345.inc) gives an
   adv_game and shows the pages in its own popup.

   WHO (the owner, 2026-11-12): one villager of 14 or more who is alive and present, not carrying a baby (nursing:
   the game's own "conceived" field of the record, a mother or a father who carries), and not special (each game's
   adv_game.eligible: A New Home's Golden Child, The Lost Children's Esteemed Elder statues, The Secret City's Tribal
   Chief, New Believers' Heathens, its chief and Retired Chief roles 12-17 and Reanimated spirits).  The friend of
   ending A8 passes the same test and is never the adventurer.  The event can happen only while at least two
   villagers pass it (adv_possible).

   THE ROLLS (the owner's; src/vv_aspiring_adventurer.py has the same numbers): all made with the game's own
   random routine when the popup is built, so the words can say what happens.
     Choice A: the find 50% nothing / 25% meat / 25% a golden chest; then 50% a surviving ending, 50% a deadly
       one: surviving with a find A1, A5 or A8 (1 in 3 each; A8 needs a friend, else A5), surviving with nothing A7
       or A9 (1 in 2 each); deadly A2, A3, A4 or A6 (1 in 4 each), the stranger of A4 and A6 a man or a woman (1 in 2).
     Choice B: 90% home safe; 10% lost, then lost endings 1-6 (1 in 6 each), and after 1 the healers' three (1 in
       3 each); the injured are left with 10-50 health (each equally likely) and dislike running; the survivalist
       of 3 gains 20-30 points (each equally likely) in Farming, Building, Research or Healing (1 in 4 each), to at
       most the game's 100.
   The reward (meat +500 food, the chest +2,000 tech points) is given only in A1, A5 and A8, through the game's own
   food or tech writer, scaled as each game's own island events are (adv_game.award_amount).

   THE EFFECTS are made when the player clicks the answer (adv_choose), as every stock two-choice event makes its
   own -- so the patcher's Island Events log, which compares the villagers around that click, records them:
   "dies" is the game's own death with the cause its stock island events give ("Unknown causes"), so the body,
   the grave, the logs and the statistics are the game's; "disappears" is the game's own removal of a living
   villager with no body (each game's own disappearing events' write), and the Cause of Death companion is told
   (VvfpCauseVanishedBy), so its Deaths log records the villager as Disappeared, in this event's words.

   THE PAGES.  The words are the owner's, in the player's language when a translation has them; nothing is cut.
   A popup's text is laid out in pages that fit the game's popup (adv_game.width characters a line, .lines lines a
   page): whole paragraphs where they fit, else whole sentences (never a sentence cut), so the text never runs off
   the screen; each page is shown in turn with OK.  The question's own text (the intro) is pages too, the last one
   shown with the two buttons.  The result of each choice is its first popup's pages (the opening and the find /
   the safe or lost walk home), then its ending's.  The sizes are data (ADV_GAMES' width and lines): when the popups
   can scroll, one page a popup is one number. */

#define ADV_MAX_PAGES 10
#define ADV_PAGE_BYTES 2400
#define ADV_PAGE_TEXT_MAX 1990              /* a page's bytes: the later games' popup builds its text in 2,000 */
#define ADV_PIECE_BYTES 2400
#define ADV_NAME_BYTES 96
#define ADV_ADULT_UNITS 280                  /* 14 years: every game counts 20 age units a year */

enum { ADV_FIND_NOTHING = 0, ADV_FIND_MEAT = 1, ADV_FIND_CHEST = 2 };
enum { ADV_FX_NONE = 0, ADV_FX_AWARD, ADV_FX_DIES, ADV_FX_DISAPPEARS, ADV_FX_INJURED, ADV_FX_SKILL, ADV_FX_JOINS };
enum { ADV_SKILL_FARMING = 0, ADV_SKILL_BUILDING = 1, ADV_SKILL_RESEARCH = 2, ADV_SKILL_HEALING = 3 };
enum { ADV_KIND_FOOD = 0, ADV_KIND_TECH = 1 };

typedef struct adv_game {
    int game;
    int (*count)(void);                              /* the records */
    unsigned char *(*record)(int index);
    int (*eligible)(const unsigned char *record);    /* WHO, above */
    int (*female)(const unsigned char *record);
    void (*name)(const unsigned char *record, char *out, int cap);   /* as the game's own events name them */
    int (*rand_below)(int n);                        /* the game's own rand() % n */
    void (*kill)(int index);
    void (*vanish)(int index);
    void (*injure)(int index, int health);           /* the health, and running disliked */
    void (*skill)(int index, int which, int amount); /* ADV_SKILL_*, at most the game's 100 */
    void (*convert)(int index);                      /* New Believers: the game's own conversion to a Heathen */
    int (*award_amount)(int kind, int base);         /* the amount the game's own rule gives */
    void (*award)(int kind, int amount);             /* through the game's own food / tech writer */
    int (*joins_key)(void);                          /* lost ending 2's words: ADV_L2_* */
    int width;                                       /* characters a line (counted as the popup wraps) */
    int lines;                                       /* lines a page (the title apart) */
    int wrap;                                        /* 1: the popup does not wrap -- the pages carry the breaks */
} adv_game;

typedef struct {
    int count;
    char text[ADV_MAX_PAGES][ADV_PAGE_BYTES];
} adv_pages;

static struct {
    const adv_game *g;
    int ready;                                        /* composed, not yet answered */
    int answered;
    int choice;                                       /* 0 A, 1 B */
    int hero, friend_;                                /* record indexes (friend -1: none) */
    unsigned int hero_id;
    int female, stranger_female;
    char name[ADV_NAME_BYTES], friend_name[ADV_NAME_BYTES];
    int find, a_end;                                  /* a_end 1..9 (A1..A9) */
    int lost, lost_end, healer;                       /* lost 0/1, lost_end 1..6, healer 1..3 */
    int skill_which, skill_amount, injured_health;
    int award_kind, award;                            /* the find's kind and the amount it gives */
    int effect[2];                                    /* ADV_FX_* of each choice */
    adv_pages intro;
    adv_pages result[2];
    int tallest;                                      /* the page with the most lines: [0] intro, 1/2 result */
    int tallest_page;
} adv;

/* ---- Counting ---------------------------------------------------------------------------------------------- */

/* The villagers who may go (or be the friend), never `except`. */
static int adv_eligible_count(const adv_game *g, int except) {
    int i, n = 0, count = g->count();
    for (i = 0; i < count; ++i) {
        const unsigned char *r = g->record(i);
        if (i != except && r != NULL && g->eligible(r)) {
            ++n;
        }
    }
    return n;
}

/* The k-th of them (0-based), or -1. */
static int adv_eligible_at(const adv_game *g, int except, int k) {
    int i, count = g->count();
    for (i = 0; i < count; ++i) {
        const unsigned char *r = g->record(i);
        if (i != except && r != NULL && g->eligible(r) && k-- == 0) {
            return i;
        }
    }
    return -1;
}

/* The event's condition (the owner): at least two villagers who may go. */
static int adv_possible(const adv_game *g) {
    return g != NULL && adv_eligible_count(g, -1) >= 2;
}

static unsigned int adv_identity(const adv_game *g, int index) {
    char name[ADV_NAME_BYTES];
    unsigned int h = 2166136261u;
    const unsigned char *r = g->record(index);
    int i;
    if (r == NULL) {
        return 0;
    }
    g->name(r, name, sizeof name);
    for (i = 0; name[i] != '\0'; ++i) {
        h = (h ^ (unsigned char)name[i]) * 16777619u;
    }
    return h ^ (unsigned int)g->female(r) ^ ((unsigned int)index << 20);
}

/* ---- Words ------------------------------------------------------------------------------------------------- */

static int adv_len(const char *s) {
    int n = 0;
    while (s[n] != '\0') {
        ++n;
    }
    return n;
}

static void adv_copy(char *out, int cap, const char *in) {
    int i = 0;
    if (cap <= 0) {
        return;
    }
    while (in != NULL && in[i] != '\0' && i < cap - 1) {
        out[i] = in[i];
        ++i;
    }
    out[i] = '\0';
}

static void adv_cat(char *out, int cap, const char *in) {
    int n = adv_len(out);
    adv_copy(out + n, cap - n, in);
}

/* `format` with each %s the next of `names` (n: the adventurer's, f: the friend's), %d `number`, %% a %. */
static void adv_fill(char *out, int cap, const char *format, const char *names, int number) {
    int o = 0, k = 0;
    const char *p;
    for (p = format; *p != '\0' && o < cap - 1; ++p) {
        if (p[0] == '%' && p[1] == 's') {
            const char *v = names[k] == 'f' ? adv.friend_name : adv.name;
            if (names[k] != '\0') {
                ++k;
            }
            while (*v != '\0' && o < cap - 1) {
                out[o++] = *v++;
            }
            ++p;
        } else if (p[0] == '%' && p[1] == 'd') {
            char digits[16];
            int d = 0;
            unsigned int u = number < 0 ? (unsigned int)(-number) : (unsigned int)number;
            if (number < 0 && o < cap - 1) {
                out[o++] = '-';
            }
            do {
                digits[d++] = (char)('0' + u % 10u);
                u /= 10u;
            } while (u != 0u && d < 15);
            while (d > 0 && o < cap - 1) {
                out[o++] = digits[--d];
            }
            ++p;
        } else if (p[0] == '%' && p[1] == '%') {
            out[o++] = '%';
            ++p;
        } else {
            out[o++] = *p;
        }
    }
    out[o] = '\0';
}

/* Piece `key` for this adventurer (STRANGER: this stranger), the names and `number` filled in, in the player's
   language when a translation has it (vvfp_trf: the translation of the row with the same values). */
static void adv_piece(char *out, int cap, int key, int number) {
    static char filled[ADV_PIECE_BYTES];
    const adv_piece_text *t = &ADV_TEXT[key];
    int form = key == ADV_STRANGER ? adv.stranger_female : adv.female;
    const char *shown;
    adv_fill(filled, sizeof filled, t->english[form], t->names, number);
    shown = vvfp_trf(t->stem[form], t->english[form], filled, out, (unsigned int)cap);
    if (shown != out) {
        adv_copy(out, cap, shown);
    }
}

/* ---- Lines and pages --------------------------------------------------------------------------------------- */

/* Characters as the popup counts them: a UTF-8 continuation byte is part of the letter before it. */
static int adv_is_letter(unsigned char c) {
    return (c & 0xC0u) != 0x80u;
}

static int adv_width_of(const char *s, int n) {
    int i, w = 0;
    for (i = 0; i < n; ++i) {
        w += adv_is_letter((unsigned char)s[i]);
    }
    return w;
}

/* The lines `text` takes (paragraphs at '\n'), wrapped at `width` characters between words; with `out`, the text
   with every wrap a '\n' (the A New Home / The Lost Children popups break only there). */
static int adv_wrap(const char *text, int width, char *out, int cap) {
    int lines = 0, o = 0;
    const char *p = text;
    if (width < 8) {
        width = 8;
    }
    if (out != NULL && cap > 0) {
        out[0] = '\0';
    }
    for (;;) {
        const char *end = p;
        int used = 0, first = 1;
        while (*end != '\0' && *end != '\n') {
            ++end;
        }
        ++lines;
        while (p < end) {
            const char *w = p;
            int n, wn;
            while (w < end && *w != ' ') {
                ++w;
            }
            n = (int)(w - p);
            wn = adv_width_of(p, n);
            if (!first && used + 1 + wn > width) {
                ++lines;
                used = 0;
                if (out != NULL && o < cap - 1) {
                    out[o++] = '\n';
                }
                first = 1;
            }
            if (!first) {
                if (out != NULL && o < cap - 1) {
                    out[o++] = ' ';
                }
                ++used;
            }
            while (wn > width) {                       /* a word longer than a line: the game breaks it too */
                ++lines;
                wn -= width;
            }
            if (out != NULL) {
                int i;
                for (i = 0; i < n && o < cap - 1; ++i) {
                    out[o++] = p[i];
                }
            }
            used += wn;
            first = 0;
            p = w;
            while (p < end && *p == ' ') {
                ++p;
            }
        }
        if (*end == '\0') {
            break;
        }
        if (out != NULL && o < cap - 1) {
            out[o++] = '\n';
        }
        p = end + 1;
    }
    if (out != NULL && cap > 0) {
        out[o] = '\0';
    }
    return lines;
}

static int adv_lines(const adv_game *g, const char *text) {
    return text[0] == '\0' ? 0 : adv_wrap(text, g->width, NULL, 0);
}

/* The end of the sentence starting at `s` (after its . ! ? -- and any further dots -- before a space), or the
   end of the text. */
static const char *adv_sentence_end(const char *s) {
    const char *p = s;
    while (*p != '\0') {
        if ((*p == '.' || *p == '!' || *p == '?') && p > s) {
            const char *q = p;
            while (*q == '.' || *q == '!' || *q == '?' || *q == '"' || *q == '\'') {
                ++q;
            }
            if (*q == ' ' || *q == '\0') {
                return q;
            }
            p = q;
            continue;
        }
        ++p;
    }
    return p;
}

typedef struct {
    const adv_game *g;
    adv_pages *pages;
    char page[ADV_PAGE_BYTES];                  /* the page being filled */
} adv_pager;

static void adv_flush(adv_pager *w) {
    if (w->page[0] != '\0' && w->pages->count < ADV_MAX_PAGES) {
        adv_copy(w->pages->text[w->pages->count], ADV_PAGE_BYTES, w->page);
        ++w->pages->count;
    }
    w->page[0] = '\0';
}

/* The page with `sep` and `piece` added still fits. */
static int adv_fits(adv_pager *w, const char *sep, const char *piece, int n) {
    static char trial[ADV_PAGE_BYTES];
    int len;
    adv_copy(trial, sizeof trial, w->page);
    if (trial[0] != '\0') {
        adv_cat(trial, sizeof trial, sep);
    }
    len = adv_len(trial);
    if (len + n + 1 >= ADV_PAGE_TEXT_MAX) {
        return 0;
    }
    memcpy(trial + len, piece, (size_t)n);
    trial[len + n] = '\0';
    return adv_lines(w->g, trial) <= w->g->lines;
}

static void adv_put(adv_pager *w, const char *sep, const char *piece, int n) {
    int len;
    if (w->page[0] != '\0') {
        adv_cat(w->page, sizeof w->page, sep);
    }
    len = adv_len(w->page);
    if (len + n + 1 < (int)sizeof w->page) {
        memcpy(w->page + len, piece, (size_t)n);
        w->page[len + n] = '\0';
    }
}

/* A sentence no page can hold (a translation's, never the English): its words, page after page. */
static void adv_put_words(adv_pager *w, const char *sep, const char *s, int n) {
    const char *p = s, *end = s + n;
    int first = 1;
    while (p < end) {
        const char *q = p;
        while (q < end && *q != ' ') {
            ++q;
        }
        if (!adv_fits(w, first ? sep : " ", p, (int)(q - p)) && w->page[0] != '\0') {
            adv_flush(w);
        }
        adv_put(w, first ? sep : " ", p, (int)(q - p));
        first = 0;
        p = q;
        while (p < end && *p == ' ') {
            ++p;
        }
    }
}

/* One paragraph: whole on this page, else whole on a new page, else sentence by sentence. */
static void adv_paragraph(adv_pager *w, const char *text) {
    const char *s = text;
    int n = adv_len(text);
    int first = 1;
    if (n == 0) {
        return;
    }
    if (adv_fits(w, "\n", text, n)) {
        adv_put(w, "\n", text, n);
        return;
    }
    if (w->page[0] != '\0') {
        char saved[ADV_PAGE_BYTES];
        adv_copy(saved, sizeof saved, w->page);
        w->page[0] = '\0';
        if (adv_fits(w, "\n", text, n)) {
            adv_copy(w->page, sizeof w->page, saved);
            adv_flush(w);
            adv_put(w, "\n", text, n);
            return;
        }
        adv_copy(w->page, sizeof w->page, saved);
    }
    while (*s != '\0') {
        const char *e = adv_sentence_end(s);
        const char *sep = first ? "\n" : " ";
        int len = (int)(e - s);
        if (!adv_fits(w, sep, s, len)) {
            adv_flush(w);
            if (!adv_fits(w, sep, s, len)) {
                adv_put_words(w, sep, s, len);
                goto next;
            }
        }
        adv_put(w, sep, s, len);
    next:
        first = 0;
        s = e;
        while (*s == ' ') {
            ++s;
        }
    }
}

/* A popup's paragraphs (NULL-ended), starting on a new page. */
static void adv_popup(const adv_game *g, adv_pages *pages, const char *const *paragraphs) {
    static adv_pager w;
    int i;
    w.g = g;
    w.pages = pages;
    w.page[0] = '\0';
    for (i = 0; paragraphs[i] != NULL; ++i) {
        adv_paragraph(&w, paragraphs[i]);
    }
    adv_flush(&w);
}

/* ---- Composing ----------------------------------------------------------------------------------------------- */

static char adv_buf[8][ADV_PIECE_BYTES];

/* "<a> <b>": two pieces as one paragraph. */
static const char *adv_join(int slot, int a, int b, int number) {
    static char second[ADV_PIECE_BYTES];
    adv_piece(adv_buf[slot], ADV_PIECE_BYTES, a, number);
    if (b >= 0) {
        adv_piece(second, sizeof second, b, number);
        adv_cat(adv_buf[slot], ADV_PIECE_BYTES, " ");
        adv_cat(adv_buf[slot], ADV_PIECE_BYTES, second);
    }
    return adv_buf[slot];
}

static const char *adv_one(int slot, int key) {
    return adv_join(slot, key, -1, 0);
}

static int adv_award_key(void) {
    return adv.award_kind == ADV_KIND_FOOD ? ADV_AWARD_FOOD : ADV_AWARD_TECH;
}

static void adv_compose_a(const adv_game *g) {
    static const int FINDS[3] = { ADV_FIND_1, ADV_FIND_2, ADV_FIND_3 };
    const char *p[6];
    adv_pages *pages = &adv.result[0];
    pages->count = 0;
    p[0] = adv_join(0, ADV_A_OPEN, FINDS[adv.find], 0);
    p[1] = NULL;
    adv_popup(g, pages, p);
    switch (adv.a_end) {
    case 1: p[0] = adv_join(1, ADV_A1, adv_award_key(), adv.award); p[1] = NULL; break;
    case 2: p[0] = adv_one(1, ADV_TRAP); p[1] = adv_one(2, ADV_BEAST); p[2] = adv_one(3, ADV_A2_END); p[3] = NULL; break;
    case 3: p[0] = adv_one(1, ADV_TRAP); p[1] = adv_one(2, ADV_BEAST); p[2] = adv_one(3, ADV_A3_END); p[3] = NULL; break;
    case 4: p[0] = adv_one(1, ADV_TRAP); p[1] = adv_one(2, ADV_STRANGER); p[2] = adv_one(3, ADV_A4_END); p[3] = NULL; break;
    case 5: p[0] = adv_one(1, ADV_TRAP); p[1] = adv_join(2, ADV_A5_END, adv_award_key(), adv.award); p[2] = NULL; break;
    case 6: p[0] = adv_one(1, ADV_TRAP); p[1] = adv_one(2, ADV_STRANGER); p[2] = adv_one(3, ADV_A6_END); p[3] = NULL; break;
    case 7: p[0] = adv_one(1, ADV_A7); p[1] = NULL; break;
    case 8: p[0] = adv_one(1, ADV_TRAP); p[1] = adv_join(2, ADV_A8_END, adv_award_key(), adv.award); p[2] = NULL; break;
    default: p[0] = adv_one(1, ADV_A9); p[1] = NULL; break;
    }
    adv_popup(g, pages, p);
}

static void adv_compose_b(const adv_game *g) {
    static const int HEALERS[3] = { ADV_H1, ADV_H2, ADV_H3 };
    const char *p[4];
    adv_pages *pages = &adv.result[1];
    pages->count = 0;
    p[0] = adv_join(4, ADV_B_OPEN, adv.lost ? ADV_B_LOST : ADV_B_HOME, 0);
    p[1] = NULL;
    adv_popup(g, pages, p);
    if (!adv.lost) {
        return;
    }
    switch (adv.lost_end) {
    case 1:                                  /* the healers' outcome is a popup of its own (the owner) */
        p[0] = adv_one(5, ADV_L1);
        p[1] = NULL;
        adv_popup(g, pages, p);
        p[0] = adv_one(6, HEALERS[adv.healer - 1]);
        break;
    case 2: p[0] = adv_one(5, g->joins_key != NULL ? g->joins_key() : ADV_L2_OTHER); p[1] = NULL; break;
    case 3: p[0] = adv_one(5, ADV_L3); p[1] = NULL; break;
    case 4: p[0] = adv_one(5, ADV_L4); p[1] = NULL; break;
    case 5: p[0] = adv_one(5, ADV_L5); p[1] = NULL; break;
    default: p[0] = adv_one(5, ADV_L6); p[1] = NULL; break;
    }
    adv_popup(g, pages, p);
}

/* The page with the most lines (and, of equal ones, the most characters): the popup is sized for it. */
static void adv_find_tallest(const adv_game *g) {
    int set, k, best = -1, best_len = -1;
    adv.tallest = 0;
    adv.tallest_page = 0;
    for (set = 0; set < 3; ++set) {
        const adv_pages *pages = set == 0 ? &adv.intro : &adv.result[set - 1];
        for (k = 0; k < pages->count; ++k) {
            int lines = adv_lines(g, pages->text[k]);
            int len = adv_len(pages->text[k]);
            if (lines > best || (lines == best && len > best_len)) {
                best = lines;
                best_len = len;
                adv.tallest = set;
                adv.tallest_page = k;
            }
        }
    }
}

static const char *adv_tallest_text(void) {
    const adv_pages *pages = adv.tallest == 0 ? &adv.intro : &adv.result[adv.tallest - 1];
    return pages->text[adv.tallest_page];
}

static int adv_percent(const adv_game *g, int percent) {
    return g->rand_below(100) < percent;
}

/* Who goes, the rolls and the words, for the popup about to be built; 0 when nobody may go. */
static int adv_begin(const adv_game *g) {
    static const int SURVIVE_FIND[3] = { 1, 5, 8 };
    static const int DEADLY[4] = { 2, 3, 4, 6 };
    int n, roll;
    const char *p[3];
    memset(&adv, 0, sizeof adv);
    adv.g = g;
    adv.friend_ = -1;
    n = adv_eligible_count(g, -1);
    if (n < 2) {
        return 0;
    }
    adv.hero = adv_eligible_at(g, -1, g->rand_below(n));
    if (adv.hero < 0) {
        return 0;
    }
    adv.hero_id = adv_identity(g, adv.hero);
    adv.female = g->female(g->record(adv.hero)) ? 1 : 0;
    g->name(g->record(adv.hero), adv.name, sizeof adv.name);
    n = adv_eligible_count(g, adv.hero);
    if (n > 0) {
        adv.friend_ = adv_eligible_at(g, adv.hero, g->rand_below(n));
        if (adv.friend_ >= 0) {
            g->name(g->record(adv.friend_), adv.friend_name, sizeof adv.friend_name);
        }
    }
    /* Choice A. */
    roll = g->rand_below(100);
    adv.find = roll < 50 ? ADV_FIND_NOTHING : (roll < 75 ? ADV_FIND_MEAT : ADV_FIND_CHEST);
    if (adv_percent(g, 50)) {
        if (adv.find == ADV_FIND_NOTHING) {
            adv.a_end = g->rand_below(2) == 0 ? 7 : 9;
        } else {
            adv.a_end = SURVIVE_FIND[g->rand_below(3)];
            if (adv.a_end == 8 && adv.friend_ < 0) {
                adv.a_end = 5;
            }
        }
    } else {
        adv.a_end = DEADLY[g->rand_below(4)];
    }
    adv.stranger_female = g->rand_below(2);
    adv.award_kind = adv.find == ADV_FIND_CHEST ? ADV_KIND_TECH : ADV_KIND_FOOD;
    adv.award = g->award_amount(adv.award_kind, adv.award_kind == ADV_KIND_TECH ? 2000 : 500);
    switch (adv.a_end) {
    case 1: case 5: case 8: adv.effect[0] = ADV_FX_AWARD; break;
    case 2: case 4: adv.effect[0] = ADV_FX_DIES; break;
    case 3: case 6: adv.effect[0] = ADV_FX_DISAPPEARS; break;
    default: adv.effect[0] = ADV_FX_NONE; break;
    }
    /* Choice B. */
    adv.lost = adv_percent(g, 10);
    adv.lost_end = 1 + g->rand_below(6);
    adv.healer = 1 + g->rand_below(3);
    adv.skill_which = g->rand_below(4);
    adv.skill_amount = 20 + g->rand_below(11);
    adv.injured_health = 10 + g->rand_below(41);
    if (!adv.lost) {
        adv.effect[1] = ADV_FX_NONE;
    } else {
        switch (adv.lost_end) {
        case 1: adv.effect[1] = adv.healer == 1 ? ADV_FX_DIES : (adv.healer == 3 ? ADV_FX_INJURED : ADV_FX_NONE); break;
        case 2: adv.effect[1] = ADV_FX_JOINS; break;
        case 3: adv.effect[1] = ADV_FX_SKILL; break;
        case 4: case 5: adv.effect[1] = ADV_FX_DIES; break;
        default: adv.effect[1] = ADV_FX_DISAPPEARS; break;
        }
    }
    /* The words. */
    p[0] = adv_one(0, ADV_INTRO_1);
    p[1] = adv_one(1, ADV_INTRO_2);
    p[2] = NULL;
    adv.intro.count = 0;
    adv_popup(g, &adv.intro, p);
    adv_compose_a(g);
    adv_compose_b(g);
    adv_find_tallest(g);
    adv.ready = adv.intro.count > 0 && adv.result[0].count > 0 && adv.result[1].count > 0;
    return adv.ready;
}

/* The words a page shows, laid out for a game whose popup does not wrap (adv_game.wrap). */
static const char *adv_shown(const char *page) {
    static char out[ADV_PAGE_BYTES];
    if (adv.g == NULL || !adv.g->wrap) {
        return page;
    }
    adv_wrap(page, adv.g->width, out, sizeof out);
    return out;
}

/* ---- The effects ------------------------------------------------------------------------------------------------- */

typedef void (__stdcall *adv_vanished_fn)(int game, int index, const char *what);

/* The Cause of Death companion's Deaths log: a disappearance, in the event's words (absent, or an older one
   without the export: nothing -- its save-time check then lists the villager as Unaccounted). */
static void adv_tell_vanished(int game, int index, const char *what) {
    HMODULE module = GetModuleHandleA("VVFP Cause of Death.dll");
    adv_vanished_fn told = module != NULL ? (adv_vanished_fn)(void *)GetProcAddress(module, "VvfpCauseVanishedBy")
                                          : NULL;
    if (told != NULL) {
        told(game, index, what);
    }
}

/* The adventurer is still who the popup is about (the popup freezes the village, so always, short of a fault). */
static int adv_same_hero(void) {
    const unsigned char *r;
    if (adv.g == NULL || adv.hero < 0) {
        return 0;
    }
    r = adv.g->record(adv.hero);
    return r != NULL && adv_identity(adv.g, adv.hero) == adv.hero_id;
}

/* The answer: `choice` 0 is "Go investigate!", 1 "Stay on the safe path".  Made once. */
static void adv_choose(int choice) {
    const adv_game *g = adv.g;
    if (g == NULL || !adv.ready || adv.answered || choice < 0 || choice > 1) {
        return;
    }
    adv.answered = 1;
    adv.choice = choice;
    if (!adv_same_hero()) {
        return;
    }
    switch (adv.effect[choice]) {
    case ADV_FX_AWARD:
        g->award(adv.award_kind, adv.award);
        break;
    case ADV_FX_DIES:
        g->kill(adv.hero);
        break;
    case ADV_FX_DISAPPEARS:
        g->vanish(adv.hero);
        adv_tell_vanished(g->game, adv.hero,
                          choice == 0 ? (adv.a_end == 3 ? "Disappeared in The Aspiring Adventurer (taken by a beast)"
                                                        : "Disappeared in The Aspiring Adventurer (taken by a stranger)")
                                      : "Disappeared in The Aspiring Adventurer (lost in the jungle)");
        break;
    case ADV_FX_INJURED:
        g->injure(adv.hero, adv.injured_health);
        break;
    case ADV_FX_SKILL:
        g->skill(adv.hero, adv.skill_which, adv.skill_amount);
        break;
    case ADV_FX_JOINS:
        if (g->convert != NULL) {
            g->convert(adv.hero);
        } else {
            g->vanish(adv.hero);
            adv_tell_vanished(g->game, adv.hero, "Disappeared in The Aspiring Adventurer (joined another tribe)");
        }
        break;
    default:
        break;
    }
}

/* ---- Skill and preference helpers the games share -------------------------------------------------------------- */

/* Running disliked in a likes / dislikes pair of `slots` ints each (-1 empty): taken from the likes, added to the
   dislikes in the first empty slot, or -- when they are full -- in place of the last one (the owner: "now dislikes
   running"). */
static void adv_dislike(int *likes, int *dislikes, int slots, int running) {
    int i, empty = -1;
    for (i = 0; i < slots; ++i) {
        if (likes[i] == running) {
            likes[i] = -1;
        }
    }
    for (i = 0; i < slots; ++i) {
        if (dislikes[i] == running) {
            return;
        }
        if (dislikes[i] == -1 && empty < 0) {
            empty = i;
        }
    }
    dislikes[empty >= 0 ? empty : slots - 1] = running;
}

static int adv_capped(int value) {
    return value < 0 ? 0 : (value > 100 ? 100 : value);
}
