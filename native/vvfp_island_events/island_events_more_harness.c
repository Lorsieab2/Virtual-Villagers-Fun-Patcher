/* Runtime harness for island_event_more.inc (the owner's v1.35.66 order):
   a new villager's Sex and Age, the Custom Island Event's other villager
   changes (parents, custom title, mask, Special villager title, The Lost
   Children's totem) and the village record (food, tech points, food stores,
   puzzles, weather).  32-bit only; tests/test_island_events_more.py builds
   and runs it.

   The companion's own source is included whole, so what runs is the shipped
   comparison and the shipped tables.  The harness owns: the villager array
   (256 records of each game's stride), the game's addresses (mapped into a
   buffer of its own: g_more_address), the record writers (stubs that keep
   what they are handed), and the custom title and A New Home parents
   lookups (stubs keyed by the record).  No game, no file, nothing under
   Documents\LDW.

     1. A "New villager" record says the newcomer's Sex and Age ("Age: 340
        (17 years old)"), in all five games.
     2. Parents a Custom Island Event changes are lines of the villager's
        record: The Lost Children to New Believers from the record, A New
        Home from the Show Parents companion.
     3. A custom title set, changed or removed is a line.
     4. A Special villager title the event gives (the Golden Child, an
        Esteemed Elder, the Tribal Chief, the Heathen Chief) is a line; in
        New Believers the Heathen mask too.
     5. The Lost Children: an Esteemed Elder's totem changed is a line.
     6. The village: food, tech points, a food store, a puzzle solved and
        the weather (in the games that keep one) are one village record,
        "Village:" with each "old -> new", under the event's title; nothing
        changed in the village, no village record.
     7. Nothing at all changed: no record of any kind.

   Exit code 0 when every check passes. */
#include "vvfp_island_events.c"

static int failures;
static int checks;
#define CHECK(cond, ...) do { ++checks; if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

#define SLOTS 256
#define VILLAGE_HEAD "  Event: A Test Event\n  Village:\n"

struct written {
    int kind;
    const void *record;
    char before[512];
    char changes[2048];
};
static struct written g_out[32];
static int g_outs;
static char g_village_out[4][2048];
static int g_village_outs;

static int __stdcall stub_write(int game, int kind, const void *record, int live, const char *before,
                                const char *changes, int arrival) {
    (void)game;
    (void)live;
    (void)arrival;
    if (g_outs < (int)(sizeof g_out / sizeof g_out[0])) {
        g_out[g_outs].kind = kind;
        g_out[g_outs].record = record;
        lstrcpynA(g_out[g_outs].before, before != NULL ? before : "", sizeof g_out[g_outs].before);
        lstrcpynA(g_out[g_outs].changes, changes != NULL ? changes : "", sizeof g_out[g_outs].changes);
        ++g_outs;
    }
    return 1;
}

static int __stdcall stub_write_village(int game, const char *text) {
    (void)game;
    if (g_village_outs < 4) {
        lstrcpynA(g_village_out[g_village_outs], text, sizeof g_village_out[0]);
        ++g_village_outs;
    }
    return 1;
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

static unsigned char *harness_records(void) {
    return g_array;
}

/* The games' addresses 0x400000..0x7FFFFF, in memory of the harness's own. */
static unsigned char *g_image;
static unsigned char *harness_address(unsigned int address) {
    if (address < 0x400000u || address >= 0x800000u) {
        return NULL;
    }
    return g_image + (address - 0x400000u);
}

static unsigned char *g_world;            /* what a world pointer points to */

/* Custom titles, by record: what VillageCustomTitle would read from the file. */
static const void *g_titled;
static char g_title[32];
static int __stdcall stub_title(int game, const void *record, char *out, int size) {
    (void)game;
    lstrcpynA(out, record == g_titled ? g_title : "", size);
    return 1;
}

/* A New Home's parents, by record index: what the Show Parents companion keeps. */
static char g_vv1_father[0x20], g_vv1_mother[0x20];
static int g_vv1_looks[4] = { -1, -1, -1, -1 };
static int g_vv1_index = 2;               /* the record the stubs answer for */
static int __stdcall stub_vv1_query(int index, int *out) {
    int k;
    for (k = 0; k < 4; ++k) {
        out[k] = index == g_vv1_index ? g_vv1_looks[k] : -1;
    }
    return 1;
}
static int __stdcall stub_vv1_names(int index, char *father, char *mother, int capacity) {
    lstrcpynA(father, index == g_vv1_index ? g_vv1_father : "", capacity);
    lstrcpynA(mother, index == g_vv1_index ? g_vv1_mother : "", capacity);
    return 1;
}

/* Every filled preference slot, "w<index>", ", " between: the shape of
   VillagePreferenceListText (the words come from the game's list there). */
static int __stdcall stub_preferences(int game, const void *record, int dislikes, char *out, int size) {
    const struct field *f = NULL;
    int k, used = 0;
    (void)game;
    for (k = 0; k < g_layout->field_count; ++k) {
        if (g_layout->fields[k].type == (dislikes ? F_DISLIKES : F_LIKES)) {
            f = &g_layout->fields[k];
        }
    }
    out[0] = '\0';
    for (k = 0; f != NULL && k < (int)f->size; ++k) {
        int v = *(const int *)((const unsigned char *)record + f->offset + 4 * k);
        if (v > 0) {
            used += _snprintf(out + used, (size_t)(size - used), "%sw%d", used ? ", " : "", v);
        }
    }
    if (used == 0) {
        lstrcpynA(out, "(none)", size);
    }
    return 1;
}

static const struct field *field_named(const struct game_layout *layout, const char *label) {
    int k;
    for (k = 0; k < layout->field_count; ++k) {
        if (strcmp(layout->fields[k].label, label) == 0) {
            return &layout->fields[k];
        }
    }
    return NULL;
}

static void begin(void) {
    g_outs = 0;
    g_village_outs = 0;
    g_snaps[0].title[0] = '\0';
    g_snaps[0].text[0] = '\0';
    g_choice[0] = '\0';
    g_answering = 0;
    g_answer_self = 0;
    g_more_entry = 0;
    lstrcpynA(g_snaps[0].title, "A Test Event", sizeof g_snaps[0].title);
    take(&g_snaps[0]);
    lstrcpynA(g_snaps[0].title, "A Test Event", sizeof g_snaps[0].title);
}

static int any_contains(const char *text) {
    int i;
    for (i = 0; i < g_outs; ++i) {
        if (strstr(g_out[i].changes, text) != NULL) {
            return 1;
        }
    }
    return 0;
}

static const struct written *record_of(const void *record) {
    int i;
    for (i = 0; i < g_outs; ++i) {
        if (g_out[i].record == record && g_out[i].kind == KIND_ISLAND_EVENT) {
            return &g_out[i];
        }
    }
    return NULL;
}

static void put_text(unsigned char *at, const char *text) {
    strcpy((char *)at, text);
}

static void put_int(const struct field *f, unsigned char *record, int value) {
    *(int *)(record + f->offset) = value;
}

/* A village field's address in the harness, by its label. */
static unsigned char *village_at(const char *label, int *type, unsigned int *extra) {
    const struct village_field *f = VILLAGE_FIELDS[g_harness_game];
    for (; f->label != NULL; ++f) {
        if (strcmp(f->label, label) == 0) {
            *type = f->type;
            *extra = f->extra;
            if (f->global != 0) {
                *(unsigned char **)harness_address(f->global) = g_world;
                return g_world + f->at;
            }
            return harness_address(f->at);
        }
    }
    return NULL;
}

/* The first puzzle of the game's village table. */
static const struct village_field *first_puzzle(void) {
    const struct village_field *f = VILLAGE_FIELDS[g_harness_game];
    for (; f->label != NULL; ++f) {
        if (f->type == VF_SOLVED_BYTE || f->type == VF_SOLVED_AT || f->type == VF_SOLVED_TABLE) {
            return f;
        }
    }
    return NULL;
}

int main(void) {
    static const char *const GAME_NAMES[GAMES + 1] = {
        "", "A New Home", "The Lost Children", "The Secret City", "The Tree of Life", "New Believers",
    };
    setvbuf(stdout, NULL, _IONBF, 0);
    g_write = stub_write;
    g_write_village = stub_write_village;
    g_more_title = stub_title;
    g_vv1_query = stub_vv1_query;
    g_vv1_names = stub_vv1_names;
    g_preferences = stub_preferences;
    g_more_address = harness_address;
    g_more_vv1_records = harness_records;
    g_more_vv2_records = harness_records;
    g_image = (unsigned char *)VirtualAlloc(NULL, 0x400000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    g_world = (unsigned char *)VirtualAlloc(NULL, 0x40000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    for (g_harness_game = 1; g_harness_game <= GAMES; ++g_harness_game) {
        struct game_layout layout = *GAME_LAYOUTS[g_harness_game];
        const struct field *sex = field_named(&layout, "Sex");
        const struct field *age = field_named(&layout, "Age");
        const struct field *father = field_named(&layout, "Father");
        const struct field *mother_head = field_named(&layout, "Mother's head");
        const struct field *health = field_named(&layout, "Health");
        unsigned int present = ARRAYS[g_harness_game].present;
        int female = g_harness_game <= 2 ? 2 : 1;   /* F_SEX12 / F_SEX01 */
        int type;
        unsigned int extra;
        unsigned char *food, *tech, *weather;
        const struct village_field *puzzle;
        printf("Virtual Villagers %d (%s)\n", g_harness_game, GAME_NAMES[g_harness_game]);
        g_array = (unsigned char *)VirtualAlloc(NULL, (SIZE_T)SLOTS * ARRAYS[g_harness_game].stride,
                                                MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        memset(g_image, 0, 0x400000);
        memset(g_world, 0, 0x40000);
        if (g_array == NULL || g_image == NULL || g_world == NULL || sex == NULL || age == NULL) {
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
        g_titled = NULL;
        g_title[0] = '\0';
        g_vv1_father[0] = g_vv1_mother[0] = '\0';
        g_vv1_looks[0] = g_vv1_looks[1] = g_vv1_looks[2] = g_vv1_looks[3] = -1;
        slot(0)[present] = 1;
        put_text(slot(0) + layout.name, "Kahu");
        slot(1)[present] = 1;
        put_text(slot(1) + layout.name, "Ana");
        slot(2)[present] = 1;
        put_text(slot(2) + layout.name, "Tavi");

        /* 7. Nothing changed: nothing written. */
        begin();
        compare(&g_snaps[0]);
        CHECK(g_outs == 0 && g_village_outs == 1
              && strcmp(g_village_out[0], "  Event: A Test Event\n  Changes: none\n") == 0,
              "an event that changes nothing is one record: \"Event: A Test Event\", \"Changes: none\"");

        /* 1. A newcomer's sex and age. */
        begin();
        slot(3)[present] = 1;
        put_text(slot(3) + layout.name, "Newt");
        put_int(sex, slot(3), female);
        put_int(age, slot(3), 340);
        put_int(health, slot(3), 75);
        compare(&g_snaps[0]);
        CHECK(record_of(slot(3)) != NULL
              && strcmp(record_of(slot(3))->changes,
                        "  New villager: yes\n  Sex: Female\n  Age: 340 (17 years old)\n  Health: 75\n") == 0,
              "a new villager's record says \"Sex: Female\", \"Age: 340 (17 years old)\" and \"Health: 75\"");
        /* 0 is a valid head, body and age (the owner): a newborn-aged newcomer
           with head 0 and body 0 is named with them, never as unknown. */
        begin();
        slot(6)[present] = 1;
        put_text(slot(6) + layout.name, "Zero");
        *(int *)(slot(6) + layout.head) = 0;
        *(int *)(slot(6) + layout.body) = 0;
        put_int(sex, slot(6), female);
        put_int(age, slot(6), 0);
        compare(&g_snaps[0]);
        CHECK(record_of(slot(6)) != NULL
              && strcmp(record_of(slot(6))->changes,
                        "  New villager: yes\n  Sex: Female\n  Age: 0 (0 years old)\n  Health: 0\n") == 0,
              "a newcomer of age 0, head 0, body 0: \"Age: 0 (0 years old)\", recorded like any other");

        /* 1b. A Custom Island Event's new villager with the parents it chose
           (the owner, 2026-10-10): each named parent and their looks, in the
           labels a parents change prints -- Joey (head 2, body 2) and a
           mother with head 0 and body 0 (real looks, never "unknown"). */
        begin();
        slot(7)[present] = 1;
        put_text(slot(7) + layout.name, "Kiri");
        put_int(sex, slot(7), female);
        put_int(age, slot(7), 100);
        put_int(health, slot(7), 60);
        if (g_harness_game == 1) {
            g_vv1_index = 7;
            lstrcpynA(g_vv1_father, "Joey", sizeof g_vv1_father);
            lstrcpynA(g_vv1_mother, "Ana Moana", sizeof g_vv1_mother);
            g_vv1_looks[0] = 2;
            g_vv1_looks[1] = 2;
            g_vv1_looks[2] = 0;
            g_vv1_looks[3] = 0;
        } else {
            const struct field *fh = field_named(&layout, "Father's head");
            const struct field *fb = field_named(&layout, "Father's body");
            const struct field *mb = field_named(&layout, "Mother's body");
            put_text(slot(7) + father->offset, "Joey");
            put_text(slot(7) + field_named(&layout, "Mother")->offset, "Ana Moana");
            put_int(fh, slot(7), 2);
            put_int(fb, slot(7), 2);
            put_int(mother_head, slot(7), 0);
            put_int(mb, slot(7), 0);
        }
        compare(&g_snaps[0]);
        CHECK(record_of(slot(7)) != NULL
              && strcmp(record_of(slot(7))->changes,
                        "  New villager: yes\n  Sex: Female\n  Age: 100 (5 years old)\n  Health: 60\n"
                        "  Father: Joey\n  Father's head: 2\n  Father's body: 2\n"
                        "  Mother: Ana Moana\n  Mother's head: 0\n  Mother's body: 0\n") == 0,
              "a new villager's chosen parents: \"Father: Joey\", his head 2 and body 2, \"Mother: Ana Moana\", 0 and 0");
        g_vv1_index = 2;
        g_vv1_father[0] = g_vv1_mother[0] = '\0';
        g_vv1_looks[0] = g_vv1_looks[1] = g_vv1_looks[2] = g_vv1_looks[3] = -1;
        slot(7)[present] = 0;

        /* 2. Parents. */
        begin();
        if (g_harness_game == 1) {
            lstrcpynA(g_vv1_father, "Rongo", sizeof g_vv1_father);
            lstrcpynA(g_vv1_mother, "Mele", sizeof g_vv1_mother);
            g_vv1_looks[2] = 4;
        } else {
            put_text(slot(2) + father->offset, "Rongo");
            put_text(slot(2) + father->offset + (g_harness_game == 2 ? 0x19 : 0x19), "Mele");
            put_int(mother_head, slot(2), 4);
        }
        compare(&g_snaps[0]);
        CHECK(record_of(slot(2)) != NULL && strstr(record_of(slot(2))->changes, "  Father: (none) -> Rongo\n")
              && strstr(record_of(slot(2))->changes, "  Mother: (none) -> Mele\n")
              && strstr(record_of(slot(2))->changes, g_harness_game == 1 ? "  Mother's head: (unknown) -> 4\n"
                                                                         : "  Mother's head: 0 -> 4\n"),
              "parents a Custom Island Event changes are lines: \"Father: (none) -> Rongo\", the mother, her head");
        /* ...and a parent's head set to 0 is a value, not "unknown". */
        begin();
        if (g_harness_game == 1) {
            g_vv1_looks[2] = 0;
        } else {
            put_int(mother_head, slot(2), 0);
        }
        compare(&g_snaps[0]);
        CHECK(record_of(slot(2)) != NULL && strcmp(record_of(slot(2))->changes, "  Mother's head: 4 -> 0\n") == 0,
              "a mother's head changed to 0 is \"Mother's head: 4 -> 0\"");

        /* 3. A custom title set, then removed. */
        begin();
        g_titled = slot(0);
        lstrcpynA(g_title, "Keeper of the Well", sizeof g_title);
        compare(&g_snaps[0]);
        CHECK(record_of(slot(0)) != NULL
              && strcmp(record_of(slot(0))->changes, "  Custom title: none -> Keeper of the Well\n") == 0,
              "a custom title set is \"Custom title: none -> Keeper of the Well\"");
        begin();
        g_title[0] = '\0';
        compare(&g_snaps[0]);
        CHECK(record_of(slot(0)) != NULL
              && strcmp(record_of(slot(0))->changes, "  Custom title: Keeper of the Well -> none\n") == 0,
              "...and removed, \"Custom title: Keeper of the Well -> none\"");

        /* 4. A Special villager title the event gives. */
        begin();
        switch (g_harness_game) {
        case 1: *(int *)(slot(1) + 0x36C) = 0xC7; break;
        case 2: slot(1)[0x7FC] = 1; break;
        case 3: slot(1)[0xE80] = 1; break;
        case 4: {
            int k;
            for (k = 0; k < 5; ++k) {
                *(float *)(slot(1) + 0x1C5C + 4 * k) = 90.0f;
            }
            break;
        }
        default:
            slot(1)[VV5_FACTION] = 1;
            *(int *)(slot(1) + VV5_TYPE) = 13;
            break;
        }
        compare(&g_snaps[0]);
        {
            static const char *const WANT[GAMES + 1] = {
                "", "  Special villager: none -> Golden Child\n", "  Special villager: none -> Esteemed Elder\n",
                "  Special villager: none -> Tribal Chief\n", "  Special villager: none -> Scholar\n",
                "  Special villager: none -> Heathen Chief\n",
            };
            CHECK(record_of(slot(1)) != NULL && strstr(record_of(slot(1))->changes, WANT[g_harness_game]) != NULL,
                  "a Special villager title the event gives is a line: %.*s", (int)strlen(WANT[g_harness_game]) - 3,
                  WANT[g_harness_game] + 2);
        }
        if (g_harness_game == 5) {
            CHECK(strstr(record_of(slot(1))->changes, "  Heathen: no -> yes\n") != NULL
                  && strstr(record_of(slot(1))->changes, "  Mask: none -> Tribal Chief Mask\n") != NULL,
                  "...and a Heathen made the Heathen Chief: \"Heathen: no -> yes\", \"Mask: none -> Tribal Chief Mask\"");
        }

        /* 5. The Lost Children: the elder's totem (the statue record). */
        if (g_harness_game == 2) {
            unsigned char *statue = slot(9);
            statue[0x30] = 1;
            statue[0x558] = 1;                    /* a statue: a look-alike, never a villager */
            memcpy(statue + 0x564, slot(1) + 0x564, 0x18);
            *(int *)(statue + 0x550) = 9;         /* frame 1: green figure */
            begin();
            *(int *)(statue + 0x550) = 12;        /* frame 4: red headdress */
            compare(&g_snaps[0]);
            CHECK(record_of(slot(1)) != NULL
                  && strcmp(record_of(slot(1))->changes, "  Totem: green figure -> red headdress\n") == 0
                  && record_of(statue) == NULL,
                  "an Esteemed Elder's totem changed is \"Totem: green figure -> red headdress\" (the statue is no villager)");
        }

        /* 8. A like added in a later slot: the whole lists, never "w3 -> w3";
           and a change that reads the same (a skill within its rounding) is no line. */
        {
            const struct field *likes = field_named(&layout, "Likes");
            const struct field *farming = field_named(&layout, "Farming");
            begin();
            *(int *)(slot(0) + likes->offset) = 3;
            compare(&g_snaps[0]);
            begin();
            *(int *)(slot(0) + likes->offset + 4) = 7;
            compare(&g_snaps[0]);
            CHECK(record_of(slot(0)) != NULL && strcmp(record_of(slot(0))->changes, "  Likes: w3 -> w3, w7\n") == 0,
                  "a like added in a later slot prints the whole lists: \"Likes: w3 -> w3, w7\"");
            begin();
            if (farming->type == F_FLOAT) {
                *(float *)(slot(0) + farming->offset) = 20.2f;
                compare(&g_snaps[0]);
                begin();
                *(float *)(slot(0) + farming->offset) = 20.4f;
            } else {
                *(int *)(slot(0) + likes->offset + 4) = -1;   /* emptied: -1 and 0 both read empty here */
                compare(&g_snaps[0]);
                begin();
                *(int *)(slot(0) + likes->offset + 4) = 0;
            }
            compare(&g_snaps[0]);
            CHECK(g_outs == 0, "a change whose old and new read the same is no line (and no record)");
        }

        /* 6. The village. */        food = village_at("Food", &type, &extra);
        tech = village_at("Tech points", &type, &extra);
        weather = village_at("Weather", &type, &extra);
        puzzle = first_puzzle();
        if (puzzle != NULL && puzzle->type == VF_SOLVED_TABLE) {
            *(int *)harness_address(puzzle->extra) = 5;    /* the threshold the game fills */
        }
        begin();
        *(int *)food = 120;
        *(int *)tech = 75;
        if (weather != NULL) {
            *(int *)weather = g_harness_game == 5 ? 5 : 2;   /* New Believers: the Tempest's storm */
        }
        if (puzzle != NULL) {
            unsigned char *at = puzzle->global != 0 ? g_world + puzzle->at : harness_address(puzzle->at);
            if (puzzle->type == VF_SOLVED_BYTE) {
                at[0] = 1;
            } else {
                *(int *)at = puzzle->type == VF_SOLVED_AT ? (int)puzzle->extra : 5;
            }
        }
        compare(&g_snaps[0]);
        {
            char want[256];
            _snprintf(want, sizeof want, "    %s: unsolved -> solved\n", puzzle != NULL ? puzzle->label : "?");
            CHECK(g_outs == 0 && g_village_outs == 1
                  && strncmp(g_village_out[0], VILLAGE_HEAD, strlen(VILLAGE_HEAD)) == 0
                  && strstr(g_village_out[0], "    Food: 0 -> 120\n") != NULL
                  && strstr(g_village_out[0], "    Tech points: 0 -> 75\n") != NULL
                  && strstr(g_village_out[0], want) != NULL,
                  "the village is one record: \"Village:\", \"Food: 0 -> 120\", \"Tech points: 0 -> 75\", \"%s: unsolved -> solved\"",
                  puzzle != NULL ? puzzle->label : "?");
        }
        /* Exactly one record per event shown: a routine that is no whole event,
           an answer whose OK follows, an event with no title -- no "Changes: none". */
        if (g_harness_game >= 3) {
            const char *want = g_harness_game == 5 ? "    Weather: clear -> storm\n" : "    Weather: clear -> rain\n";
            CHECK(g_village_outs == 1 && strstr(g_village_out[0], want) != NULL, "...and the weather, \"%.*s\"",
                  (int)strlen(want) - 5, want + 4);
            /* A type with no word (The Tree of Life's 1, The Arc of Brilliant Colors: the owner,
               "not weather"; any 1 or 3 the schedule draws): to or from it, no Weather line. */
            begin();
            *(int *)weather = 1;
            *(int *)food += 1;
            compare(&g_snaps[0]);
            CHECK(g_village_outs == 1 && strstr(g_village_out[0], "Weather") == NULL
                  && strstr(g_village_out[0], "type ") == NULL,
                  "a weather type with no word, to or from: no Weather line, never \"type N\"");
        } else {
            CHECK(weather == NULL, "%s keeps no weather the events change: none is compared", GAME_NAMES[g_harness_game]);
        }
        begin();
        if (g_harness_game == 1) {
            g_snaps[0].title[0] = '\0';
            compare(&g_snaps[0]);
            CHECK(g_outs == 0 && g_village_outs == 0, "an event with no title: no \"Changes: none\"");
        } else if (g_harness_game == 2 || g_harness_game == 4) {
            g_more_entry = g_harness_game == 2 ? 0x422380u : 0x417790u;
            compare(&g_snaps[0]);
            CHECK(g_outs == 0 && g_village_outs == 0,
                  "the routine that only asks or builds the dialog (0x%X) writes no \"Changes: none\"", g_more_entry);
        } else {
            int answer_records, ok_records;
            g_answering = 1;
            g_answer_self = 0x1234;
            *(int *)(slot(0) + layout.head) += 1;
            compare(&g_snaps[0]);
            answer_records = g_outs + g_village_outs;
            begin();
            g_answer_self = 0x1234;
            compare(&g_snaps[0]);
            ok_records = g_outs + g_village_outs;
            CHECK(answer_records == 2 && ok_records == 0,
                  "an answer logged with changes, then its OK with none: one event, no \"Changes: none\"");
        }        {
            static const char *const STORE[GAMES + 1] = {
                "", "Berries remaining", "Fish", "Honey", "Blackberries", "Noni remaining",
            };
            unsigned char *store = village_at(STORE[g_harness_game], &type, &extra);
            char want[96];
            begin();
            *(int *)store += 500;
            compare(&g_snaps[0]);
            _snprintf(want, sizeof want, "    %s: ", STORE[g_harness_game]);
            CHECK(g_village_outs == 1 && strstr(g_village_out[0], want) != NULL
                  && strstr(g_village_out[0], "Food:") == NULL,
                  "a food store refilled is a line (\"%s\"), and only what changed is written",
                  STORE[g_harness_game]);
        }

        VirtualFree(g_array, 0, MEM_RELEASE);
    }
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
