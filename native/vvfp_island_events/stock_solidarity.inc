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

static int stock_when_holds(const char *when, int facts) {
    static const struct { const char *word; int fact; } WORDS[] = {
        { "food+", SF_FOOD_UP }, { "food-", SF_FOOD_DOWN }, { "tech+", SF_TECH_UP }, { "tech-", SF_TECH_DOWN },
        { "lost", SF_LOST }, { "joined", SF_JOINED }, { "sick", SF_SICK }, { "sick2", SF_SICK2 },
        { "hurt", SF_HURT }, { "healed", SF_HEALED }, { "weather", SF_WEATHER },
    };
    size_t k;
    if (when[0] == '\0') {
        return 1;
    }
    for (k = 0; k < sizeof WORDS / sizeof WORDS[0]; ++k) {
        if (strcmp(when, WORDS[k].word) == 0) {
            return (facts & WORDS[k].fact) != 0;
        }
    }
    return 0;
}

/* ---- ANY LANGUAGE: the words shown, back to the game's own English ------------------------------------------

   "VVFP Translations.dll" puts a translation in place of a string table row's English (A New Home and The Lost
   Children: the row's text pointer; the later games: the entry's loaded text, +0xC).  So the title and the answer
   shown are found in the table as it is now -- the row whose text reads as shown -- and that row's English is the
   game's own: the later games' built-in text (+8, never written), A New Home's and The Lost Children's text
   pointer as the executable on disk holds it (read once, stock_originals).  Without a translation the words shown
   are the English already.  The table's addresses are the Translations companion's own (its GAMES table). */

#define STOCK_TEXT 256
#define STOCK_CANDIDATES 8
#define STOCK_ROWS_MAX 0x600

static const struct { unsigned int table, rows, stride; int sm; } STOCK_STRINGS[GAMES + 1] = {
    { 0, 0, 0, 0 },
    { 0x487208u, 0x275u, 0x14u, 0 },      /* A New Home: {id, English, ...} */
    { 0x496300u, 0x36Cu, 12u, 0 },        /* The Lost Children: {id, English, German} */
    { 0x4AB990u, 0x4BAu, 16u, 1 },        /* The Secret City: {id, name, built-in, loaded} */
    { 0x4C41F8u, 1338u, 16u, 1 },         /* The Tree of Life */
    { 0x4D31F0u, 1409u, 16u, 1 },         /* New Believers */
};

/* A New Home's and The Lost Children's rows' English as the executable holds them (0 none read). */
static unsigned int g_stock_original[STOCK_ROWS_MAX];
static int g_stock_originals;             /* 0 not read yet, 1 read, -1 not readable (a harness sets 1) */

static void stock_originals(void) {
    char path[MAX_PATH];
    HANDLE file;
    unsigned char head[0x400];
    DWORD got = 0;
    unsigned int pe, sections, count, opt, k, rva;
    if (g_stock_originals != 0) {
        return;
    }
    g_stock_originals = -1;
    if (STOCK_STRINGS[g_game].sm || STOCK_STRINGS[g_game].rows > STOCK_ROWS_MAX
        || GetModuleFileNameA(NULL, path, sizeof path) == 0) {
        return;
    }
    file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    rva = STOCK_STRINGS[g_game].table - 0x400000u;
    if (ReadFile(file, head, sizeof head, &got, NULL) && got == sizeof head && head[0] == 'M' && head[1] == 'Z') {
        pe = *(const unsigned int *)(head + 0x3C);
        if (pe + 0x18 < sizeof head) {
            count = *(const unsigned short *)(head + pe + 6);
            opt = *(const unsigned short *)(head + pe + 0x14);
            sections = pe + 0x18 + opt;
            for (k = 0; k < count && sections + 40 * (k + 1) <= sizeof head; ++k) {
                const unsigned char *sec = head + sections + 40 * k;
                unsigned int va = *(const unsigned int *)(sec + 12), raw_size = *(const unsigned int *)(sec + 16);
                unsigned int raw = *(const unsigned int *)(sec + 20);
                unsigned int bytes = STOCK_STRINGS[g_game].rows * STOCK_STRINGS[g_game].stride;
                static unsigned char rows[STOCK_ROWS_MAX * 0x14];
                if (rva >= va && rva + bytes <= va + raw_size && bytes <= sizeof rows
                    && SetFilePointer(file, (LONG)(raw + (rva - va)), NULL, FILE_BEGIN) != INVALID_SET_FILE_POINTER
                    && ReadFile(file, rows, bytes, &got, NULL) && got == bytes) {
                    unsigned int r;
                    for (r = 0; r < STOCK_STRINGS[g_game].rows; ++r) {
                        g_stock_original[r] = *(const unsigned int *)(rows + r * STOCK_STRINGS[g_game].stride + 4);
                    }
                    g_stock_originals = 1;
                    break;
                }
            }
        }
    }
    CloseHandle(file);
}

/* Row `r`'s text now (translated or not), and its English; NULL when unreadable. */
static const char *stock_text_now(unsigned int r) {
    const unsigned int *row = (const unsigned int *)g_more_address(STOCK_STRINGS[g_game].table
                                                                   + r * STOCK_STRINGS[g_game].stride);
    const char *text;
    if (row == NULL || !readable(row, STOCK_STRINGS[g_game].stride)) {
        return NULL;
    }
    text = STOCK_STRINGS[g_game].sm ? (const char *)(uintptr_t)(row[3] != 0 ? row[3] : row[2])
                                    : (const char *)(uintptr_t)row[1];
    return text != NULL && readable(text, 1) ? text : NULL;
}

static const char *stock_text_english(unsigned int r) {
    const unsigned int *row = (const unsigned int *)g_more_address(STOCK_STRINGS[g_game].table
                                                                   + r * STOCK_STRINGS[g_game].stride);
    const char *text;
    if (row == NULL || !readable(row, STOCK_STRINGS[g_game].stride)) {
        return NULL;
    }
    if (STOCK_STRINGS[g_game].sm) {
        text = (const char *)(uintptr_t)row[2];
    } else {
        stock_originals();
        text = g_stock_originals == 1 && g_stock_original[r] != 0 ? (const char *)(uintptr_t)g_stock_original[r]
                                                                   : (const char *)(uintptr_t)row[1];
    }
    return text != NULL && readable(text, 1) ? text : NULL;
}

/* `src` (its first line only when `line`) with each run of spaces as one, no spaces at either end and no final
   "." -- "            The  Foul Passing \n" -> "The Foul Passing". */
static void stock_norm(const char *src, int line, char *out, size_t size) {
    size_t n = 0, i, room;
    int space = 0;
    MEMORY_BASIC_INFORMATION info;
    out[0] = '\0';
    if (src == NULL || VirtualQuery(src, &info, sizeof info) != sizeof info || info.State != MEM_COMMIT
        || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
        return;
    }
    room = (size_t)((const char *)info.BaseAddress + info.RegionSize - src);   /* one query for the whole text */
    for (i = 0; i < 4096 && i < room && src[i] != '\0' && n + 1 < size; ++i) {
        char c = src[i];
        if (c == '\n' || c == '\r') {
            if (line && n > 0) break;
            c = ' ';
        }
        if (c == ' ' || c == '\t') {
            space = n > 0;
            continue;
        }
        if (space && n + 2 < size) out[n++] = ' ';
        space = 0;
        out[n++] = c;
    }
    while (n > 0 && (out[n - 1] == '.' || out[n - 1] == ' ')) --n;
    out[n] = '\0';
}

/* The games' own word codes in a row's text (a name, he, his...: "*^&+=|~@#$") match one or more characters; a
   "{...}" (a translation's select, the later games' {name} and {M/F}) matches any run. */
static int stock_code(char c) {
    return c != '\0' && strchr("*^&+=|~@#$", c) != NULL;
}

static int stock_glob(const char *p, const char *t, int depth) {
    if (depth > 64) {
        return 0;
    }
    for (;;) {
        if (*p == '\0') {
            return *t == '\0';
        }
        if (*p == '{') {
            const char *end = strchr(p, '}');
            size_t k;
            if (end == NULL) {
                return 0;
            }
            for (k = 0;; ++k) {
                if (stock_glob(end + 1, t + k, depth + 1)) return 1;
                if (t[k] == '\0') return 0;
            }
        }
        if (stock_code(*p)) {
            size_t k;
            for (k = 1; t[k - 1] != '\0'; ++k) {
                if (stock_glob(p + 1, t + k, depth + 1)) return 1;
            }
            return 0;
        }
        if (*p != *t) {
            return 0;
        }
        ++p;
        ++t;
    }
}

/* How many of `p`'s characters are its own (not a code or a select): a row of codes alone is no evidence. */
static int stock_literals(const char *p) {
    int n = 0;
    for (; *p != '\0'; ++p) {
        if (*p == '{') {
            const char *end = strchr(p, '}');
            if (end == NULL) break;
            p = end;
        } else if (!stock_code(*p) && *p != ' ') {
            ++n;
        }
    }
    return n;
}

struct stock_words {
    int count;
    char text[STOCK_CANDIDATES][STOCK_TEXT];
};

/* The English the words `shown` stand for: `shown` itself, then the English of every table row that reads as
   shown -- the same words first; only when none does, the rows whose codes and selects make them read so. */
static void stock_english_of(const char *shown, int title, struct stock_words *out) {
    unsigned int r, rows = STOCK_STRINGS[g_game].rows;
    int pass;
    char now[STOCK_TEXT];
    out->count = 0;
    stock_norm(shown, title, out->text[0], STOCK_TEXT);
    if (out->text[0][0] == '\0') {
        return;
    }
    out->count = 1;
    for (pass = 0; pass < 2 && out->count == 1; ++pass) {
        for (r = 0; r < rows && out->count < STOCK_CANDIDATES; ++r) {
            const char *text = stock_text_now(r);
            int hit;
            if (text == NULL) continue;
            stock_norm(text, title, now, sizeof now);
            hit = pass == 0 ? strcmp(now, out->text[0]) == 0
                            : !title && stock_literals(now) >= 3 && stock_glob(now, out->text[0], 0);
            if (hit) {
                stock_norm(stock_text_english(r), title, out->text[out->count], STOCK_TEXT);
                if (out->text[out->count][0] != '\0') {
                    ++out->count;
                }
            }
        }
    }
}

/* The table's English `english` (spaces collapsed, no final ".") is one of `words`: the same, or a row's English
   whose codes read as it ("Agree ^ is the fastest" for "Agree he is the fastest"). */
static int stock_is(const char *english, const struct stock_words *words) {
    char want[STOCK_TEXT];
    int k;
    stock_norm(english, 0, want, sizeof want);
    for (k = 0; k < words->count; ++k) {
        if (strcmp(want, words->text[k]) == 0 || stock_glob(words->text[k], want, 0)) {
            return 1;
        }
    }
    return 0;
}

/* ---- ONLY THE GAME'S OWN EVENTS -----------------------------------------------------------------------------

   A Custom Island Event (or a branching or collection event) is shown by "VVFP Story Upgrades.dll" through the
   same popups, and may carry a stock title and answer.  Its custom-event path counts every popup it fills and
   says when its question waits for a click (VvfpStoryCustomState): read when the watched event begins and again
   at its comparison, a change -- or a question waiting when it began -- means the popup was that engine's, which
   tags its own pages, and nothing is taken from this table. */
typedef unsigned int (__stdcall *custom_state_fn)(int game);
static custom_state_fn g_custom_state;    /* a harness sets its own */
static int g_custom_looked;
static unsigned int g_custom_before;

static custom_state_fn custom_state(void) {
    if (g_custom_state == NULL && !g_custom_looked) {
        HMODULE story = GetModuleHandleA("VVFP Story Upgrades.dll");
        if (story == NULL) {
            return NULL;
        }
        g_custom_looked = 1;
        g_custom_state = (custom_state_fn)(void *)GetProcAddress(story, "VvfpStoryCustomState");
    }
    return g_custom_state;
}

/* When a watched event begins (before_call). */
static void stock_begin(void) {
    custom_state_fn state = custom_state();
    g_custom_before = state != NULL ? state(g_game) : 0u;
}

static int stock_custom_event(void) {
    custom_state_fn state = custom_state();
    unsigned int now;
    if (state == NULL) {
        return 0;                         /* no Story engine: every event is the game's own */
    }
    now = state(g_game);
    return (g_custom_before & 1u) != 0 || (now >> 1) != (g_custom_before >> 1);
}

/* The tag of the result shown (1 raise, 2 lower, 3 neutral), 0 when the table has none. */
static int stock_tag_of(const struct snapshot *s, const char *answer) {
    static struct stock_words titles, answers;
    int i, facts = -1, attempt, matched = 0;
    /* First the words as shown (English: no table read); only when no row is theirs, the table's English. */
    for (attempt = 0; attempt < 2 && !matched; ++attempt) {
        if (attempt == 0) {
            stock_norm(s->title, 1, titles.text[0], STOCK_TEXT);
            stock_norm(answer, 0, answers.text[0], STOCK_TEXT);
            titles.count = titles.text[0][0] != '\0';
            answers.count = answers.text[0][0] != '\0';
        } else {
            unsigned int bytes = STOCK_STRINGS[g_game].rows * STOCK_STRINGS[g_game].stride;
            if (STOCK_STRINGS[g_game].rows == 0
                || !readable(g_more_address(STOCK_STRINGS[g_game].table), bytes)) {
                break;
            }
            stock_english_of(s->title, 1, &titles);
            stock_english_of(answer, 0, &answers);
        }
        for (i = 0; i < STOCK_TAG_COUNT; ++i) {
            const struct stock_tag *row = &STOCK_TAGS[i];
            if (row->game != g_game || !stock_is(row->title, &titles)
                || (row->answer[0] == '\0' ? answers.count != 0 : !stock_is(row->answer, &answers))) {
                continue;
            }
            matched = 1;
            if (row->when[0] != '\0' && facts < 0) {
                facts = stock_facts(s);
            }
            if (stock_when_holds(row->when, facts < 0 ? 0 : facts)) {
                return row->tag;
            }
        }
    }
    return 0;
}

static void stock_solidarity(const struct snapshot *s) {
    score_tag_fn tag_fn;
    int tag;
    if (g_answering || more_never_alone(g_more_entry) || s->title[0] == '\0' || stock_custom_event()) {
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
