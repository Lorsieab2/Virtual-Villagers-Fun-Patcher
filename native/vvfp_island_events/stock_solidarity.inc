/* Village Solidarity and the games' OWN island events (the owner, 2026-11-20, v1.35.97; included by
   vvfp_island_events.c after island_event_more.inc).

   When the comparison of a stock event's result is made (compare), the result shown is looked up in the owner's
   table (data/stock_island_event_solidarity.txt -> stock_solidarity_table.inc): its title, the answer picked, and --
   where one title and answer can show different results by a hidden roll -- what the result did to the village
   (the stored food or tech points up or down, a villager lost or joined, sick, hurt or healed, the weather, the
   item the popup names).  Its tag (1 raise, 2 lower, 3 neutral) is handed to "VVFP Village Solidarity.dll"
   (VvfpVillageScoreTag, score 0), once: only for the comparison that is the event's own (never for The Lost
   Children's two-choice constructor or The Tree of Life's dialog constructor alone, never for a later game's
   answer click that its OK follows, never for a branching event's page).

   SCORE ONLY.  Nothing here runs before the game's routine, and nothing is written to the game: the event, its
   draw and its result are the game's own, read after they happened.  Only when the Village Solidarity companion
   is loaded (the row ticked: GetModuleHandle never loads it) and started for this game (its export answers -1
   otherwise). */

struct stock_tag {
    int game;
    const char *title;
    const char *answer;                   /* "" for an event with no choice */
    const char *when;                     /* "" always */
    int tag;
};
#include "stock_solidarity_table.inc"

#define STOCK_TAG_COUNT ((int)(sizeof STOCK_TAGS / sizeof STOCK_TAGS[0]))

typedef int (__stdcall *score_tag_fn)(int game, int score_id, int tag, const char *event_title);
static score_tag_fn g_score_tag;          /* a harness sets its own */
static int g_score_tag_looked;

static score_tag_fn score_tagger(void) {
    if (g_score_tag == NULL && !g_score_tag_looked) {
        HMODULE module = GetModuleHandleA("VVFP Village Solidarity.dll");
        if (module == NULL) {
            return NULL;                  /* not loaded (yet): asked again next time */
        }
        g_score_tag_looked = 1;
        g_score_tag = (score_tag_fn)(void *)GetProcAddress(module, "VvfpVillageScoreTag");
    }
    return g_score_tag;
}

/* `a` and `b` the same words: runs of spaces as one, a final "." and spaces dropped ("The  Foul Passing"). */
static int same_words(const char *a, const char *b) {
    for (;;) {
        while (*a == ' ' && a[1] == ' ') ++a;
        while (*b == ' ' && b[1] == ' ') ++b;
        if (*a == '\0' || *b == '\0') {
            const char *rest = *a != '\0' ? a : b;
            while (*rest == ' ' || *rest == '.') ++rest;
            return *rest == '\0';
        }
        if (*a != *b) {
            /* a final "." (or spaces) on one side only */
            const char *x = a, *y = b;
            while (*x == ' ' || *x == '.') ++x;
            while (*y == ' ' || *y == '.') ++y;
            return *x == '\0' && *y == '\0';
        }
        ++a;
        ++b;
    }
}

/* What the result did, as the table's WHEN words. */
enum {
    SF_FOOD_UP = 1 << 0, SF_FOOD_DOWN = 1 << 1, SF_TECH_UP = 1 << 2, SF_TECH_DOWN = 1 << 3, SF_LOST = 1 << 4,
    SF_JOINED = 1 << 5, SF_SICK = 1 << 6, SF_SICK2 = 1 << 7, SF_HURT = 1 << 8, SF_HEALED = 1 << 9,
    SF_WEATHER = 1 << 10
};

static int stock_int_of(const unsigned char *record, const struct field *f) {
    if (f == NULL) {
        return 0;
    }
    return f->type == F_BYTE_FLAG ? record[f->offset] != 0 : *(const int *)(record + f->offset);
}

static int stock_facts(const struct snapshot *s) {
    const struct village_field *fields = VILLAGE_FIELDS[g_game];
    const struct field *health = field_labelled("Health"), *sick = field_labelled("Sick");
    const struct field *heathen = field_labelled("Heathen");
    unsigned char *now[MAX_VILLAGERS];
    int facts = 0, sick_count = 0, count, i;
    for (i = 0; fields != NULL && i < VILLAGE_MAX && fields[i].label != NULL; ++i) {
        char after[MORE_TEXT];
        int food = strcmp(fields[i].label, "Food") == 0, tech = strcmp(fields[i].label, "Tech points") == 0;
        village_text(&fields[i], after, sizeof after);
        if (food || tech) {
            int b, a;
            if (g_village_before[i][0] == '\0' || after[0] == '\0') {
                continue;
            }
            b = atoi(g_village_before[i]);
            a = atoi(after);
            if (a > b) facts |= food ? SF_FOOD_UP : SF_TECH_UP;
            if (a < b) facts |= food ? SF_FOOD_DOWN : SF_TECH_DOWN;
        } else if (fields[i].type == VF_WEATHER && strcmp(g_village_before[i], after) != 0) {
            facts |= SF_WEATHER;
        }
    }
    count = g_layout->enumerate(now, MAX_VILLAGERS);
    for (i = 0; i < s->count; ++i) {
        const unsigned char *old = s->copy + (size_t)i * g_layout->copy_size;
        const unsigned char *live = s->where[i];
        int h0, h1;
        if (live == NULL) {
            continue;
        }
        if (!present_now(live, now, count) || reused(old, live)) {
            facts |= SF_LOST;
            continue;
        }
        h0 = stock_int_of(old, health);
        h1 = stock_int_of(live, health);
        if (health != NULL && h0 > 0 && h1 <= 0) facts |= SF_LOST;
        if (health != NULL && h1 < h0) facts |= SF_HURT;
        if (health != NULL && h1 > h0) facts |= SF_HEALED;
        if (sick != NULL && !stock_int_of(old, sick) && stock_int_of(live, sick)) ++sick_count;
        if (sick != NULL && stock_int_of(old, sick) && !stock_int_of(live, sick)) facts |= SF_HEALED;
    }
    if (sick_count >= 1) facts |= SF_SICK;
    if (sick_count >= 2) facts |= SF_SICK2;
    for (i = 0; i < count; ++i) {
        int k = copy_of(s, now[i]);
        if ((k < 0 || reused(s->copy + (size_t)k * g_layout->copy_size, now[i]))
            && (heathen == NULL || !stock_int_of(now[i], heathen))) {
            facts |= SF_JOINED;           /* a newcomer (New Believers: a believer, not a Heathen) */
        }
    }
    return facts;
}

static int stock_when_holds(const char *when, int facts, const char *item) {
    static const struct { const char *word; int fact; } WORDS[] = {
        { "food+", SF_FOOD_UP }, { "food-", SF_FOOD_DOWN }, { "tech+", SF_TECH_UP }, { "tech-", SF_TECH_DOWN },
        { "lost", SF_LOST }, { "joined", SF_JOINED }, { "sick", SF_SICK }, { "sick2", SF_SICK2 },
        { "hurt", SF_HURT }, { "healed", SF_HEALED }, { "weather", SF_WEATHER },
    };
    size_t k;
    if (when[0] == '\0') {
        return 1;
    }
    if (strncmp(when, "item:", 5) == 0) {
        return item[0] != '\0' && strstr(item, when + 5) != NULL;
    }
    for (k = 0; k < sizeof WORDS / sizeof WORDS[0]; ++k) {
        if (strcmp(when, WORDS[k].word) == 0) {
            return (facts & WORDS[k].fact) != 0;
        }
    }
    return 0;
}

/* The tag of the result shown (1 raise, 2 lower, 3 neutral), 0 when the table has none. */
static int stock_tag_of(const struct snapshot *s, const char *answer) {
    int i, facts = -1;
    for (i = 0; i < STOCK_TAG_COUNT; ++i) {
        const struct stock_tag *row = &STOCK_TAGS[i];
        if (row->game != g_game || !same_words(row->title, s->title) || !same_words(row->answer, answer)) {
            continue;
        }
        if (row->when[0] != '\0' && strncmp(row->when, "item:", 5) != 0 && facts < 0) {
            facts = stock_facts(s);
        }
        if (stock_when_holds(row->when, facts < 0 ? 0 : facts, s->text)) {
            return row->tag;
        }
    }
    return 0;
}

static void stock_solidarity(const struct snapshot *s) {
    score_tag_fn tag_fn;
    int tag;
    if (g_answering || more_never_alone(g_more_entry) || s->title[0] == '\0') {
        return;
    }
    tag_fn = score_tagger();
    if (tag_fn == NULL) {
        return;
    }
    tag = stock_tag_of(s, g_choice);
    if (tag != 0) {
        (void)tag_fn(g_game, 0, tag, s->title);
    }
}
