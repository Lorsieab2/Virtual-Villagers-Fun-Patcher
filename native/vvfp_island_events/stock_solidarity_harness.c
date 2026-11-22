/* Runtime harness for Village Solidarity and the games' own island events (stock_solidarity.inc in
   "VVFP Island Events.dll").  32-bit only; tests/test_stock_event_solidarity.py builds and runs it.

   The companion's own source is included whole, so what runs is the shipped comparison and the shipped table
   (stock_solidarity_table.inc, generated from data/stock_island_event_solidarity.txt).  The harness's own: the
   villagers are an array it owns (each game's real field table, stride and present byte), the game's addresses
   the village is read from (food, tech points, weather) are a block of its own memory (g_more_address), the log
   writers are stubs, and "VVFP Village Solidarity.dll"'s VvfpVillageScoreTag is a stub that counts its calls.
   No game, no file, nothing under Documents\LDW.

     1. EVERY ROW OF THE TABLE, in all five games: the result it names -- its title, its answer, and what tells it
        from the others behind the same title and answer -- moves the score by exactly its tag, exactly once
        (one call, that tag, the event's title).
     2. Nothing happens without the companion (GetModuleHandle finds no "VVFP Village Solidarity.dll").
     3. Nothing for an event the table does not hold (a new or custom event), for a two-choice event's title with
        no answer, for The Lost Children's two-choice constructor (its click is the event), for a later game's
        answer click its OK follows, or for the gong.
     4. Through the real brackets, exactly once per event shown: A New Home's encounter click, The Lost
        Children's two-choice click, and The Secret City's, The Tree of Life's and New Believers' presenter with
        the answer and OK inside it.
     5. Any language: a stock event shown translated (the game's string table as "VVFP Translations.dll" leaves it)
        moves the score by its English row's tag, once; words no row of the table reads as move nothing.
     6. A Custom Island Event (the Story engine's popup) with a stock title and answer gets no stock tag; the game's
        own event through the same routine, with that engine there, still does.

   Exit code 0 when every check passes. */
#include "vvfp_island_events.c"

static int failures;
static int checks;
#define CHECK(cond, ...) do { ++checks; if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

#define SLOTS 8

static int __stdcall stub_write(int game, int kind, const void *record, int live, const char *before,
                                const char *changes, int arrival) {
    (void)game; (void)kind; (void)record; (void)live; (void)before; (void)changes; (void)arrival;
    return 1;
}
static int __stdcall stub_write_village(int game, const char *text) {
    (void)game; (void)text;
    return 1;
}

/* VvfpVillageScoreTag, stood in for. */
static int g_calls;
static int g_last_tag;
static char g_last_title[TITLE_MAX];
static int __stdcall stub_tag(int game, int score_id, int tag, const char *title) {
    if (game == g_game && score_id == 0) {
        ++g_calls;
        g_last_tag = tag;
        lstrcpynA(g_last_title, title != NULL ? title : "", sizeof g_last_title);
    }
    return 50;
}

static const struct { unsigned int stride, present; } ARRAYS[GAMES + 1] = {
    { 0, 0 }, { 0x3D8, 0x28 }, { 0xE48C, 0x30 }, { 0x1F8C, 0xF10 }, { 0x2E3C, 0x1CC4 }, { 0x2F44, 0x1CD4 },
};
static unsigned char *g_array;
static int g_harness_game;

static int harness_villagers(unsigned char **out, int capacity) {
    return array_villagers(g_array, ARRAYS[g_harness_game].stride, SLOTS, ARRAYS[g_harness_game].present, out,
                           capacity);
}
static unsigned char *slot(int i) {
    return g_array + (size_t)i * ARRAYS[g_harness_game].stride;
}

/* The game's addresses 0x400000.. as a block of the harness's own; each game's world pointer at its address
   points at a world block of the harness's own. */
static unsigned char *g_image;
static unsigned char *g_world;
static unsigned char *harness_address(unsigned int address) {
    return address >= 0x400000u && address < 0x800000u ? g_image + (address - 0x400000u) : NULL;
}

static int *village_int(const char *label) {
    const struct village_field *f;
    for (f = VILLAGE_FIELDS[g_game]; f != NULL && f->label != NULL; ++f) {
        if (strcmp(f->label, label) == 0) {
            if (f->global != 0) {
                return (int *)(g_world + f->at);
            }
            return (int *)harness_address(f->at);
        }
    }
    return NULL;
}

static const struct field *field_named(const char *label) {
    return field_labelled(label);
}

static void set_int(int i, const char *label, int value) {
    const struct field *f = field_named(label);
    if (f == NULL) return;
    if (f->type == F_BYTE_FLAG) slot(i)[f->offset] = (unsigned char)value;
    else *(int *)(slot(i) + f->offset) = value;
}

/* A fresh village: three villagers at 50 health, well; 500 food, 5,000 tech points, clear weather. */
static void reset_village(void) {
    int i;
    memset(g_array, 0, (size_t)SLOTS * ARRAYS[g_harness_game].stride);
    for (i = 0; i < 3; ++i) {
        slot(i)[ARRAYS[g_harness_game].present] = 1;
        strcpy((char *)slot(i) + g_layout->name, i == 0 ? "Kahu" : i == 1 ? "Ana" : "Tavi");
        set_int(i, "Health", 50);
    }
    if (village_int("Food") != NULL) *village_int("Food") = 500;
    if (village_int("Tech points") != NULL) *village_int("Tech points") = 5000;
    if (village_int("Weather") != NULL) *village_int("Weather") = 0;
}

static void begin(const char *title, const char *answer, const char *item) {
    g_calls = 0;
    g_last_tag = 0;
    g_last_title[0] = '\0';
    g_answering = 0;
    g_more_entry = 0;
    g_snaps[0].title[0] = '\0';
    g_snaps[0].text[0] = '\0';
    g_choice[0] = '\0';
    take(&g_snaps[0]);
    lstrcpynA(g_snaps[0].title, title, sizeof g_snaps[0].title);
    lstrcpynA(g_snaps[0].text, item, sizeof g_snaps[0].text);
    lstrcpynA(g_choice, answer, sizeof g_choice);
}

/* What tells the result: make it happen in the village. */
static void apply(const char *when) {
    if (strcmp(when, "food+") == 0) *village_int("Food") += 300;
    else if (strcmp(when, "food-") == 0) *village_int("Food") -= 300;
    else if (strcmp(when, "tech+") == 0) *village_int("Tech points") += 2000;
    else if (strcmp(when, "tech-") == 0) *village_int("Tech points") -= 2000;
    else if (strcmp(when, "lost") == 0) slot(1)[ARRAYS[g_harness_game].present] = 0;
    else if (strcmp(when, "joined") == 0) {
        slot(3)[ARRAYS[g_harness_game].present] = 1;
        strcpy((char *)slot(3) + g_layout->name, "Newt");
    } else if (strcmp(when, "sick") == 0) set_int(0, "Sick", 1);
    else if (strcmp(when, "sick2") == 0) { set_int(0, "Sick", 1); set_int(1, "Sick", 1); }
    else if (strcmp(when, "hurt") == 0) set_int(0, "Health", 35);
    else if (strcmp(when, "healed") == 0) set_int(0, "Health", 100);
    else if (strcmp(when, "weather") == 0) *village_int("Weather") = 3;
}

static void check_rows(void) {
    int i, rows = 0, right = 0;
    for (i = 0; i < STOCK_TAG_COUNT; ++i) {
        const struct stock_tag *row = &STOCK_TAGS[i];
        if (row->game != g_game) {
            continue;
        }
        ++rows;
        reset_village();
        begin(row->title, row->answer, "");
        apply(row->when);
        compare(&g_snaps[0]);
        if (g_calls == 1 && g_last_tag == row->tag && strcmp(g_last_title, row->title) == 0) {
            ++right;
        } else {
            printf("  FAIL row %d: \"%s\" / \"%s\" / %s: %d call(s), tag %d (want %d)\n", i, row->title,
                   row->answer, row->when[0] ? row->when : "-", g_calls, g_last_tag, row->tag);
        }
    }
    CHECK(rows > 0 && right == rows, "every one of the %d rows moves the score by its own tag, exactly once", rows);
}

/* A row of this game: its title and answer (the first row with an answer, or none). */
static const struct stock_tag *first_row(int with_answer) {
    int i;
    for (i = 0; i < STOCK_TAG_COUNT; ++i) {
        if (STOCK_TAGS[i].game == g_game && (STOCK_TAGS[i].answer[0] != '\0') == with_answer
            && STOCK_TAGS[i].when[0] == '\0') {
            return &STOCK_TAGS[i];
        }
    }
    return NULL;
}

static void check_nothing(void) {
    const struct stock_tag *single = first_row(0), *two = first_row(1);
    /* 2. No companion. */
    g_score_tag = NULL;
    g_score_tag_looked = 0;
    reset_village();
    begin(single->title, "", "");
    compare(&g_snaps[0]);
    CHECK(g_calls == 0 && g_score_tag == NULL, "without \"VVFP Village Solidarity.dll\" nothing is moved (%s)",
          single->title);
    g_score_tag = stub_tag;
    /* 3. Not the table's, or not the event's own comparison. */
    reset_village();
    begin("The Aspiring Adventurer", "", "");
    compare(&g_snaps[0]);
    CHECK(g_calls == 0, "an event the table does not hold (a new or custom one) moves nothing");
    reset_village();
    begin(two->title, "", "");
    compare(&g_snaps[0]);
    CHECK(g_calls == 0, "a two-choice event's title with no answer (\"%s\") moves nothing", two->title);
    reset_village();
    begin(two->title, two->answer, "");
    g_answering = 1;
    compare(&g_snaps[0]);
    CHECK(g_calls == 0, "an answer click its OK follows moves nothing (the OK is the event's own)");
    g_answering = 0;
    reset_village();
    begin(single->title, "", "");
    g_snaps[0].title[0] = '\0';
    compare(&g_snaps[0]);
    CHECK(g_calls == 0, "a popup with no title moves nothing");
    if (g_game == 2) {
        reset_village();
        begin("The Strange Request", "", "");
        g_more_entry = 0x422380u;
        compare(&g_snaps[0]);
        CHECK(g_calls == 0, "The Lost Children's two-choice constructor (Biggles made) moves nothing");
        reset_village();
        begin("The Gong of Wonder", "", "");
        compare(&g_snaps[0]);
        CHECK(g_calls == 0, "the Gong of Wonder (no island event, the owner) moves nothing");
    }
}

/* ---- 4. Through the real brackets ---------------------------------------------------------------------------- */

static void call_site(int index, const void *self, unsigned int msg, unsigned int id, void (*inside)(void)) {
    unsigned int frame[12];
    memset(frame, 0, sizeof frame);
    frame[6] = (unsigned int)(uintptr_t)self;
    frame[8] = 0x401000u;
    frame[9] = msg;
    frame[10] = id;
    before_call(frame, index);
    if (inside != NULL) {
        inside();
    }
    (void)after_call();
}

static void lose_food(void) {
    *village_int("Food") -= 100;
}

/* A New Home's encounter / The Lost Children's two-choice dialog: question at +0x74 (+0x7C), answer ids at
   +0x54 / +0x58, labels at +0x4E92 (+0x4E9A) and 0x100 on. */
static unsigned char g_old_dialog[0x5100];

static void check_old_click(int site, unsigned int question, unsigned int labels, const char *title,
                            const char *first, int want) {
    memset(g_old_dialog, 0, sizeof g_old_dialog);
    _snprintf((char *)g_old_dialog + question, 0x200, "            %s \n\n\n\nSome words.", title);
    _snprintf((char *)g_old_dialog + labels, 0x100, "%s.", first);
    *(unsigned int *)(g_old_dialog + 0x54) = 7;
    *(unsigned int *)(g_old_dialog + 0x58) = 8;
    g_sites[0] = &GAME_SITES[g_game][site];
    reset_village();
    g_calls = 0;
    call_site(0, g_old_dialog, 8, 7, lose_food);
    CHECK(g_calls == 1 && g_last_tag == want && strcmp(g_last_title, title) == 0,
          "the click on \"%s\" in \"%s\": one move, tag %d", first, title, want);
    g_calls = 0;
    call_site(0, g_old_dialog, 8, 99, lose_food);   /* not an answer: not watched */
    CHECK(g_calls == 0, "a click that is no answer moves nothing");
    g_sites[0] = NULL;
}

/* The later games' dialog: the event at +0x50, the title's text at +0x54, buttons +0x85C / +0x860 -> +0x10 -> +0x40. */
static unsigned char g_dialog[0x900];
static unsigned char g_buttons[2][0x20];
static unsigned char g_controls[2][0x60];
static char g_labels[2][64];
static char g_title_text[128];

static void build_dialog(const char *title, const char *a, const char *b) {
    int k;
    memset(g_dialog, 0, sizeof g_dialog);
    _snprintf(g_title_text, sizeof g_title_text, "%s\nSome words.", title);
    g_title_text[sizeof g_title_text - 1] = '\0';
    *(unsigned int *)(g_dialog + 0x50) = (unsigned int)(uintptr_t)g_buttons;
    *(unsigned int *)(g_dialog + 0x54) = (unsigned int)(uintptr_t)g_title_text;
    lstrcpynA(g_labels[0], a, sizeof g_labels[0]);
    lstrcpynA(g_labels[1], b, sizeof g_labels[1]);
    for (k = 0; k < 2; ++k) {
        *(unsigned int *)(g_dialog + 0x85C + 4 * k) = (unsigned int)(uintptr_t)g_buttons[k];
        *(unsigned int *)(g_buttons[k] + 0x10) = (unsigned int)(uintptr_t)g_controls[k];
        *(unsigned int *)(g_controls[k] + 0x40) = (unsigned int)(uintptr_t)g_labels[k];
    }
}

static int g_ctor_index = -1;
static void answer_first_then_ok(void) {
    if (g_ctor_index >= 0) {
        call_site(g_ctor_index, g_dialog, 0, 0, NULL);          /* The Tree of Life: the dialog names the event */
    }
    call_site(1, g_dialog, 8, 2, NULL);                          /* the first answer */
    call_site(1, g_dialog, 8, 1, lose_food);                     /* OK applies it */
}

static void check_presenter(const char *title, const char *a, const char *b, int want) {
    const struct site *sites = GAME_SITES[g_game];
    int k, click = -1, ctor = -1;
    for (k = 0; sites[k].entry != 0; ++k) {
        if (sites[k].answer != NULL) click = k;
        if (sites[k].entry == 0x417790u) ctor = k;
    }
    g_sites[0] = &sites[0];
    g_sites[1] = &sites[click];
    g_ctor_index = -1;
    if (ctor >= 0) {
        g_sites[2] = &sites[ctor];
        g_ctor_index = 2;
    }
    build_dialog(title, a, b);
    reset_village();
    g_calls = 0;
    g_answer[0] = '\0';
    g_answer_self = 0;
    call_site(0, NULL, 0, 0, answer_first_then_ok);
    CHECK(g_calls == 1 && g_last_tag == want && strcmp(g_last_title, title) == 0,
          "the presenter with \"%s\" answered and OK'd inside it: one move, tag %d", title, want);
    g_sites[0] = g_sites[1] = g_sites[2] = NULL;
    g_answer[0] = '\0';
    g_answer_self = 0;
}

/* ---- 5. Any language: a translated stock event still moves the score ----------------------------------------

   The game's string table as "VVFP Translations.dll" leaves it: A New Home's and The Lost Children's rows point at
   the translation (their English is what the executable on disk holds: g_stock_original), the later games' entries
   keep their built-in English at +8 and the translation at +0xC.  The popup shows the translation. */
static char g_fr_title[128], g_en_title[128], g_fr_answer[128], g_en_answer[128];

static void put_row(unsigned int r, const char *now, const char *english) {
    unsigned char *row = harness_address(STOCK_STRINGS[g_game].table + r * STOCK_STRINGS[g_game].stride);
    memset(row, 0, STOCK_STRINGS[g_game].stride);
    *(unsigned int *)row = 100 + r;
    if (STOCK_STRINGS[g_game].sm) {
        ((unsigned int *)row)[2] = (unsigned int)(uintptr_t)english;
        ((unsigned int *)row)[3] = (unsigned int)(uintptr_t)now;
    } else {
        ((unsigned int *)row)[1] = (unsigned int)(uintptr_t)now;
        g_stock_original[r] = (unsigned int)(uintptr_t)english;
    }
}

static void clear_table(void) {
    memset(harness_address(STOCK_STRINGS[g_game].table), 0, STOCK_STRINGS[g_game].rows * STOCK_STRINGS[g_game].stride);
    memset(g_stock_original, 0, sizeof g_stock_original);
    g_stock_originals = 1;
}

static void check_translated(const char *title, const char *fr_title, const char *answer_row_en,
                             const char *answer_row_fr, const char *shown_answer, int want) {
    int old = !STOCK_STRINGS[g_game].sm;
    clear_table();
    /* A New Home's and The Lost Children's event text: the title is its first line, after the game's padding. */
    _snprintf(g_en_title, sizeof g_en_title, old ? "          %s \n\n\n\nThe words." : "%s", title);
    _snprintf(g_fr_title, sizeof g_fr_title, old ? "          %s \n\n\n\nLes mots." : "%s", fr_title);
    lstrcpynA(g_en_answer, answer_row_en, sizeof g_en_answer);
    lstrcpynA(g_fr_answer, answer_row_fr, sizeof g_fr_answer);
    put_row(3, g_fr_title, g_en_title);
    put_row(7, g_fr_answer, g_en_answer);
    reset_village();
    begin(fr_title, shown_answer, "");
    compare(&g_snaps[0]);
    CHECK(g_calls == 1 && g_last_tag == want,
          "translated: \"%s\" / \"%s\" (the table's \"%s\" / \"%s\") moves the score once, tag %d", fr_title,
          shown_answer, title, answer_row_en, want);
    /* The same words with no row of the table reading so: nothing (never a guess). */
    clear_table();
    reset_village();
    begin(fr_title, shown_answer, "");
    compare(&g_snaps[0]);
    CHECK(g_calls == 0, "words no row of the game's table reads as move nothing");
    clear_table();
}

static void check_translations(void) {
    switch (g_game) {
    case 1:
        check_translated("The Old Drum", "Le Vieux Tambour", "Keep the drum to make music.",
                         "Garder le tambour pour la musique.", "Garder le tambour pour la musique", 1);
        break;
    case 2:
        check_translated("The Cursed Idol", "L'Idole maudite", "Make an offering of food",
                         "Faire une offrande de nourriture", "Faire une offrande de nourriture", 2);
        /* A row with the game's codes and a translation's select: "Agree ^ is the fastest". */
        check_translated("The Fastest Runner", "Le Plus Rapide", "Agree ^ is the fastest",
                         "Admettre qu'{*: il|elle} est le plus rapide", "Admettre qu'elle est le plus rapide", 3);
        break;
    case 3:
        check_translated("The Hole in the Hut", "Le Trou dans la hutte", "Use beeswax", "Utiliser la cire",
                         "Utiliser la cire", 2);
        break;
    case 4:
        check_translated("The Calabash Instrument", "La Calebasse", "Fill it up to the first notch",
                         "Remplir jusqu'au premier cran", "Remplir jusqu'au premier cran", 1);
        break;
    default:
        check_translated("The Straw Hat", "Le Chapeau de paille", "Use it as a cooking strainer",
                         "{name} s'en sert de passoire", "Kahu s'en sert de passoire", 1);
        break;
    }
    g_stock_originals = 1;               /* (the table cleared: never the harness's own file) */
}

/* ---- 6. A Custom Island Event with a stock title and answer is not the game's own ----------------------------

   "VVFP Story Upgrades.dll"'s VvfpStoryCustomState, stood in for: its count of popups the custom-event path
   filled (x2) plus 1 while a custom question waits for its click. */
static unsigned int g_story_serial;
static int g_story_asked;
static unsigned int __stdcall stub_custom_state(int game) {
    (void)game;
    return (g_story_serial << 1) | (unsigned int)(g_story_asked != 0);
}

static void deliver_custom_then_lose_food(void) {
    ++g_story_serial;                     /* the custom-event path fills the popup */
    *village_int("Food") -= 100;
}

static void custom_answer_then_lose_food(void) {
    ++g_story_serial;
    if (g_ctor_index >= 0) {
        call_site(g_ctor_index, g_dialog, 0, 0, NULL);
    }
    call_site(1, g_dialog, 8, 2, NULL);
    call_site(1, g_dialog, 8, 1, lose_food);
}

static void check_custom(void) {
    const struct site *sites = GAME_SITES[g_game];
    int k, click = -1;
    g_custom_state = stub_custom_state;
    g_story_serial = 5;
    g_story_asked = 0;
    if (g_game <= 2) {
        /* A New Home's encounters, The Lost Children's two-choice events: a custom question's click (the
           question was the engine's, waiting for its click when the click began). */
        int site = g_game == 1 ? 1 : 2;
        unsigned int question = g_game == 1 ? 0x74 : 0x7C, labels = g_game == 1 ? 0x4E92 : 0x4E9A;
        const char *title = g_game == 1 ? "The Old Drum" : "The Cursed Idol";
        const char *first = g_game == 1 ? "Keep the drum to make music" : "Make an offering of food";
        memset(g_old_dialog, 0, sizeof g_old_dialog);
        _snprintf((char *)g_old_dialog + question, 0x200, "            %s \n\n\n\nSome words.", title);
        _snprintf((char *)g_old_dialog + labels, 0x100, "%s.", first);
        *(unsigned int *)(g_old_dialog + 0x54) = 7;
        *(unsigned int *)(g_old_dialog + 0x58) = 8;
        g_sites[0] = &sites[site];
        reset_village();
        g_calls = 0;
        g_story_asked = 1;
        call_site(0, g_old_dialog, 8, 7, lose_food);
        CHECK(g_calls == 0, "a Custom Island Event's question titled \"%s\", answered \"%s\": no stock tag", title,
              first);
        g_story_asked = 0;
        g_calls = 0;
        call_site(0, g_old_dialog, 8, 7, lose_food);
        CHECK(g_calls == 1, "...the game's own \"%s\" with the Story engine there: tagged once", title);
        /* A plain custom event filled into the island event's own popup (the constructor). */
        g_sites[0] = &sites[0];
        reset_village();
        g_calls = 0;
        begin("A Plague of Locusts", "", "");     /* the constructor's after() would name it; set directly */
        stock_begin();
        deliver_custom_then_lose_food();
        g_more_entry = sites[0].entry;
        compare(&g_snaps[0]);
        CHECK(g_calls == 0, "a plain Custom Island Event with a stock title: no stock tag");
        g_sites[0] = NULL;
    } else {
        for (k = 0; sites[k].entry != 0; ++k) {
            if (sites[k].answer != NULL) click = k;
        }
        g_sites[0] = &sites[0];
        g_sites[1] = &sites[click];
        g_ctor_index = -1;
        for (k = 0; sites[k].entry != 0; ++k) {
            if (sites[k].entry == 0x417790u) {
                g_sites[2] = &sites[k];
                g_ctor_index = 2;
            }
        }
        build_dialog(g_game == 3 ? "The Hole in the Hut" : g_game == 4 ? "The Calabash Instrument" : "The Straw Hat",
                     g_game == 3 ? "Use beeswax" : g_game == 4 ? "Fill it up to the first notch" : "Wear it", "B");
        reset_village();
        g_calls = 0;
        g_answer[0] = '\0';
        g_answer_self = 0;
        call_site(0, NULL, 0, 0, custom_answer_then_lose_food);
        CHECK(g_calls == 0, "a Custom Island Event delivered by the presenter with a stock title and answer: no "
                            "stock tag");
        g_calls = 0;
        g_answer[0] = '\0';
        g_answer_self = 0;
        call_site(0, NULL, 0, 0, answer_first_then_ok);
        CHECK(g_calls == 1, "...the game's own event through the same presenter: tagged once");
        g_sites[0] = g_sites[1] = g_sites[2] = NULL;
        g_ctor_index = -1;
        g_answer[0] = '\0';
        g_answer_self = 0;
    }
    g_custom_state = NULL;
    g_custom_looked = 0;
    g_custom_before = 0;
}

int main(void) {
    static const char *const GAME_NAMES[GAMES + 1] = {
        "", "A New Home", "The Lost Children", "The Secret City", "The Tree of Life", "New Believers",
    };
    setvbuf(stdout, NULL, _IONBF, 0);
    g_write = stub_write;
    g_write_village = stub_write_village;
    g_score_tag = stub_tag;
    g_more_address = harness_address;
    g_stock_originals = 1;               /* the executable's rows: the harness's tables (check_translations) */
    g_image = (unsigned char *)VirtualAlloc(NULL, 0x400000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    g_world = (unsigned char *)VirtualAlloc(NULL, 0x40000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (g_image == NULL || g_world == NULL) {
        printf("  FAIL no memory\n");
        return 1;
    }
    /* Every game's world pointer (VILLAGE_FIELDS' globals) at its address. */
    for (g_harness_game = 1; g_harness_game <= GAMES; ++g_harness_game) {
        const struct village_field *f;
        for (f = VILLAGE_FIELDS[g_harness_game]; f->label != NULL; ++f) {
            if (f->global != 0) {
                *(unsigned char **)harness_address(f->global) = g_world;
            }
        }
    }
    for (g_harness_game = 1; g_harness_game <= GAMES; ++g_harness_game) {
        struct game_layout layout = *GAME_LAYOUTS[g_harness_game];
        printf("Virtual Villagers %d (%s)\n", g_harness_game, GAME_NAMES[g_harness_game]);
        g_array = (unsigned char *)VirtualAlloc(NULL, (SIZE_T)SLOTS * ARRAYS[g_harness_game].stride + 0x1000,
                                                MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (g_array == NULL) {
            printf("  FAIL cannot set the game up\n");
            ++failures;
            continue;
        }
        layout.enumerate = harness_villagers;
        g_game = g_harness_game;
        g_layout = &layout;
        if (g_snaps[0].copy != NULL) {
            VirtualFree(g_snaps[0].copy, 0, MEM_RELEASE);
            g_snaps[0].copy = NULL;
        }
        check_rows();
        check_nothing();
        switch (g_game) {
        case 1: check_old_click(1, 0x74, 0x4E92, "The Old Drum", "Keep the drum to make music", 1); break;
        case 2: check_old_click(2, 0x7C, 0x4E9A, "The Cursed Idol", "Make an offering of food", 2); break;
        case 3: check_presenter("The Hole in the Hut", "Use beeswax", "Use tree sap", 2); break;
        case 4: check_presenter("The Calabash Instrument", "Fill it up to the first notch", "Fill it to the top", 1);
                break;
        default: check_presenter("The Straw Hat", "Wear it", "Use it as a cooking strainer", 3); break;
        }
        check_translations();
        check_custom();
        VirtualFree(g_array, 0, MEM_RELEASE);
    }
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
