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
        char item[64];
        if (row->game != g_game) {
            continue;
        }
        ++rows;
        reset_village();
        item[0] = '\0';
        if (strncmp(row->when, "item:", 5) == 0) {
            _snprintf(item, sizeof item, "a large %s thing", row->when + 5);
            item[sizeof item - 1] = '\0';
        }
        begin(row->title, row->answer, item);
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

int main(void) {
    static const char *const GAME_NAMES[GAMES + 1] = {
        "", "A New Home", "The Lost Children", "The Secret City", "The Tree of Life", "New Believers",
    };
    setvbuf(stdout, NULL, _IONBF, 0);
    g_write = stub_write;
    g_write_village = stub_write_village;
    g_score_tag = stub_tag;
    g_more_address = harness_address;
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
        VirtualFree(g_array, 0, MEM_RELEASE);
    }
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
