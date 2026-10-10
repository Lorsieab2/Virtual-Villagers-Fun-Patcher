/* Runtime harness for "VVFP Island Events.dll"'s comparison (compare() in
   vvfp_island_events.c).  32-bit only; tests/test_island_events_log.py builds
   and runs it.

   The companion's own source is included whole, so what runs here is the
   shipped comparison, field tables and all; only two things are the
   harness's: the villagers are read from an array it owns (each game's real
   field table, record stride and present byte, with an `enumerate` that reads
   the harness's array instead of the game's), and the record writer is a stub
   that keeps each record it is handed.  No game, no file, nothing under
   Documents\LDW.

     1. A renamed villager stays one villager (Codex, #577): The Secret City's
        Return of Biggles, confronted, names its subject "?" -- one record,
        "Name: Kahu -> ?" with the Research it gives, never "Gone" and never
        "New villager".  In all five games.
     2. A villager the event removes is still "Gone", named from the copy; one
        it brings is still "New villager".
     3. An event that starts a pregnancy logs the conception's lasting fields on the
        mother, not only her Pregnant flag: the babies and the expected
        father's name, head and body (Codex, #577), in all five games: A New
        Home's father from the Show Parents companion's record of the
        conception (a stand-in here), and none printed when it has none
        (3d).  They are printed whole even when the last pregnancy left the
        same father or babies on her (3b), A New Home's and The Lost
        Children's 0 for one baby as 1; a pregnancy's babies changed later
        are "old -> new" (3c).
     4. Bytes after a name's terminator are not a change.
     5. A record slot the event freed and filled with someone else (the name
        AND the head or body differ) is the one before "Gone" and the one now
        "New villager", not a rename.
     6. The records the games do not count as villagers (The Lost Children's
        Esteemed Elder statues, The Secret City's +0xE94 records, The Tree of
        Life's ghosts, New Believers' Reanimate stand-ins) are never logged,
        though an event changes everyone; the villagers still are.

     7. The Secret City, The Tree of Life and New Believers: the answer
        clicked in their two-choice dialog is the record's "Choice:" line, as
        in A New Home and The Lost Children -- inside the presenter, and (The
        Secret City, New Believers) for the dialog on its own, its OK's record;
        never carried to the next event shown at the same address.

   Exit code 0 when every check passes. */
#include "vvfp_island_events.c"

static int failures;
static int checks;
#define CHECK(cond, ...) do { ++checks; if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

#define SLOTS 8

struct written {
    int kind;
    const void *record;
    int live;
    char before[512];
    char changes[2048];
};
static struct written g_out[32];
static int g_outs;

static int __stdcall stub_write(int game, int kind, const void *record, int live, const char *before,
                                const char *changes, int arrival) {
    (void)game;
    (void)arrival;
    if (g_outs < (int)(sizeof g_out / sizeof g_out[0])) {
        g_out[g_outs].kind = kind;
        g_out[g_outs].record = record;
        g_out[g_outs].live = live;
        lstrcpynA(g_out[g_outs].before, before != NULL ? before : "", sizeof g_out[g_outs].before);
        lstrcpynA(g_out[g_outs].changes, changes != NULL ? changes : "", sizeof g_out[g_outs].changes);
        ++g_outs;
    }
    return 1;
}

/* Each game's stride and present byte, as island_event_games.inc reads them. */
static const struct { unsigned int stride, present; } ARRAYS[GAMES + 1] = {
    { 0, 0 }, { 0x3D8, 0x28 }, { 0xE48C, 0x30 }, { 0x1F8C, 0xF10 }, { 0x2E3C, 0x1CC4 }, { 0x2F44, 0x1CD4 },
};
/* Each game's look-alike byte (native/shared/villager_lookalike.h); A New Home has none. */
static const unsigned int LOOKALIKE[GAMES + 1] = { 0, 0, 0x558, 0xE94, 0x1CC7, 0x1CE1 };
static unsigned char *g_array;
static int g_harness_game;

static int harness_villagers(unsigned char **out, int capacity) {
    return array_villagers(g_array, ARRAYS[g_harness_game].stride, SLOTS, ARRAYS[g_harness_game].present, out,
                           capacity);
}

/* A New Home's expected father: the harness's array in place of the game's,
   and a stand-in for the Show Parents companion's Vv1ParentageQueryExpected
   that knows a conception by Rongo (head 3, body 7) for record
   g_vv1_stash_index only, and remembers the record it was asked about. */
static int g_vv1_stash_index = 2;
static int g_vv1_queried = -1;

static unsigned char *harness_array(void) {
    return g_array;
}

static int __stdcall stub_query_expected(int index, char *name, int capacity, int *head, int *body) {
    g_vv1_queried = index;
    if (index != g_vv1_stash_index) {
        return 0;
    }
    lstrcpynA(name, "Rongo", capacity);
    *head = 3;
    *body = 7;
    return 1;
}

static unsigned char *slot(int i) {
    return g_array + (size_t)i * ARRAYS[g_harness_game].stride;
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

static void put_name(unsigned char *record, unsigned int offset, const char *name) {
    strcpy((char *)record + offset, name);
}

static void begin(void) {
    g_outs = 0;
    g_snaps[0].title[0] = '\0';
    g_snaps[0].text[0] = '\0';
    g_choice[0] = '\0';
    take(&g_snaps[0]);
}

static int count_kind(int kind) {
    int i, n = 0;
    for (i = 0; i < g_outs; ++i) {
        n += g_out[i].kind == kind;
    }
    return n;
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

/* A two-choice dialog as the later games build it: the event at +0x50, the
   answer buttons at +0x85C / +0x860, each button's control at +0x10 keeping
   its label at +0x40. */
static unsigned char g_dialog[0x900];
static unsigned char g_buttons[2][0x20];
static unsigned char g_controls[2][0x60];
static char g_labels[2][32];

static void build_dialog(void) {
    int b;
    memset(g_dialog, 0, sizeof g_dialog);
    *(unsigned int *)(g_dialog + 0x50) = (unsigned int)(uintptr_t)g_buttons;   /* any event: non-zero */
    lstrcpynA(g_labels[0], "Swim it back\n", sizeof g_labels[0]);
    lstrcpynA(g_labels[1], "Leave it.", sizeof g_labels[1]);
    for (b = 0; b < 2; ++b) {
        *(unsigned int *)(g_dialog + 0x85C + 4 * b) = (unsigned int)(uintptr_t)g_buttons[b];
        *(unsigned int *)(g_buttons[b] + 0x10) = (unsigned int)(uintptr_t)g_controls[b];
        *(unsigned int *)(g_controls[b] + 0x40) = (unsigned int)(uintptr_t)g_labels[b];
    }
}

/* One call of site `site` (index 0 or 1 in g_sites) with `this` and the click
   (msg, id); `inside` runs between its entry and its return. */
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

static int g_choice_research;
static int g_choice_float;
static void gain_research(void) {
    if (g_choice_float) {
        *(float *)(slot(0) + g_choice_research) += 1.0f;
    } else {
        *(int *)(slot(0) + g_choice_research) += 1;
    }
}
static void answer_second_then_ok(void) {
    call_site(1, g_dialog, 8, 3, NULL);
    call_site(1, g_dialog, 8, 1, gain_research);
}

static void check_choice(const struct game_layout *layout, const struct field *research, int skills_float) {
    const struct site *sites = GAME_SITES[g_harness_game];
    const struct site *click = NULL;
    int k;
    (void)layout;
    for (k = 0; sites[k].entry != 0; ++k) {
        if (sites[k].answer != NULL) {
            click = &sites[k];
        }
    }
    CHECK(click != NULL && sites[0].watch == NULL && sites[0].answer == NULL,
          "the two-choice dialog's button handler is watched for the answer");
    if (click == NULL) {
        return;
    }
    g_sites[0] = &sites[0];               /* the presenter */
    g_sites[1] = click;
    g_choice_research = (int)research->offset;
    g_choice_float = skills_float;
    build_dialog();

    /* a. Inside the presenter: the second answer, then OK applies the event. */
    g_outs = 0;
    call_site(0, NULL, 0, 0, answer_second_then_ok);
    CHECK(g_outs == 1 && strstr(g_out[0].before, "  Choice: Leave it\n") != NULL
          && strstr(g_out[0].changes, "  Research: ") != NULL,
          "inside the presenter: \"Choice: Leave it\" (the second answer's label, as shown) on the record");

    /* b. The next event at the same address, no answer clicked: no Choice. */
    g_outs = 0;
    call_site(0, NULL, 0, 0, gain_research);
    CHECK(g_outs == 1 && strstr(g_out[0].before, "Choice:") == NULL,
          "the next event shown in the same dialog, no answer: no Choice carried over");

    /* c. The dialog on its own (no presenter): the first answer, then OK. */
    if (click->watch != never) {
        g_outs = 0;
        *(unsigned int *)(g_dialog + 0x50) = (unsigned int)(uintptr_t)g_buttons;
        call_site(1, g_dialog, 8, 2, NULL);
        call_site(1, g_dialog, 8, 1, gain_research);
        CHECK(g_outs == 1 && strstr(g_out[0].before, "  Choice: Swim it back\n") != NULL,
              "the dialog on its own: the answer is kept for the OK's record (\"Choice: Swim it back\")");
    } else {
        /* The Tree of Life: its click handler starts no comparison. */
        g_outs = 0;
        call_site(1, g_dialog, 8, 3, gain_research);
        CHECK(g_outs == 0 && g_depth == 0, "The Tree of Life's click handler alone writes nothing");
        g_answer[0] = '\0';
        g_answer_self = 0;
    }
    g_sites[0] = g_sites[1] = NULL;
}

int main(void) {
    static const char *const GAME_NAMES[GAMES + 1] = {
        "", "A New Home", "The Lost Children", "The Secret City", "The Tree of Life", "New Believers",
    };
    setvbuf(stdout, NULL, _IONBF, 0);
    g_write = stub_write;
    g_vv1_array = harness_array;
    g_vv1_query_expected = stub_query_expected;
    g_vv1_query_looked = 1;
    for (g_harness_game = 1; g_harness_game <= GAMES; ++g_harness_game) {
        struct game_layout layout = *GAME_LAYOUTS[g_harness_game];
        const struct field *research = field_named(&layout, "Research");
        const struct field *pregnant = field_named(&layout, "Pregnant");
        const struct field *babies = field_named(&layout, "Babies in pregnancy");
        const struct field *father = field_named(&layout, "Expected father");
        const struct field *father_head = field_named(&layout, "Expected father's head");
        const struct field *father_body = field_named(&layout, "Expected father's body");
        unsigned int present = ARRAYS[g_harness_game].present;
        int skills_float = research != NULL && research->type == F_FLOAT;
        printf("Virtual Villagers %d (%s)\n", g_harness_game, GAME_NAMES[g_harness_game]);
        g_array = (unsigned char *)VirtualAlloc(NULL, (SIZE_T)SLOTS * ARRAYS[g_harness_game].stride + 0x1000,
                                                MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (g_array == NULL || research == NULL || pregnant == NULL || babies == NULL) {
            printf("  FAIL cannot set the game up\n");
            ++failures;
            continue;
        }
        layout.enumerate = harness_villagers;
        g_game = g_harness_game;
        g_layout = &layout;
        if (g_snaps[0].copy != NULL) {
            VirtualFree(g_snaps[0].copy, 0, MEM_RELEASE);   /* sized per game by take() */
            g_snaps[0].copy = NULL;
        }
        slot(0)[present] = 1;
        put_name(slot(0), layout.name, "Kahu");
        slot(1)[present] = 1;
        put_name(slot(1), layout.name, "Ana");
        slot(2)[present] = 1;
        put_name(slot(2), layout.name, "Tavi");

        /* 1. Renamed: "Kahu" -> "?", and Research gained. */
        begin();
        memset(slot(0) + layout.name, 0, 4);
        put_name(slot(0), layout.name, "?");
        if (skills_float) {
            *(float *)(slot(0) + research->offset) += 20.0f;
        } else {
            *(int *)(slot(0) + research->offset) += 20;
        }
        compare(&g_snaps[0]);
        CHECK(g_outs == 1 && g_out[0].kind == KIND_ISLAND_EVENT && g_out[0].live == 1 && g_out[0].record == slot(0)
              && strstr(g_out[0].changes, "  Name: Kahu -> ?\n") != NULL
              && strstr(g_out[0].changes, "  Research: 0 -> 20\n") != NULL,
              "a renamed villager is one record: \"Name: Kahu -> ?\" and the Research it gave");
        CHECK(!any_contains("Gone:") && !any_contains("New villager:"),
              "...never \"Gone\" and never \"New villager\"");

        /* 2. Removed and brought. */
        begin();
        slot(1)[present] = 0;
        slot(3)[present] = 1;
        put_name(slot(3), layout.name, "Newt");
        compare(&g_snaps[0]);
        CHECK(g_outs == 2 && count_kind(KIND_ISLAND_EVENT) == 2
              && g_out[0].live == 0 && strstr(g_out[0].changes, "  Gone: yes\n") != NULL
              && strcmp((const char *)g_out[0].record + layout.name, "Ana") == 0
              && g_out[1].record == slot(3) && strstr(g_out[1].changes, "  New villager: yes\n") != NULL,
              "a villager removed is \"Gone\" (named from the copy), one brought is \"New villager\"");

        /* 3. A pregnancy the event starts, on Tavi: twins by Rongo.  The
           Pregnant field holds what each game writes (The Lost Children a
           countdown, the others 1). */
        begin();
        *(int *)(slot(2) + pregnant->offset) = g_harness_game == 2 ? 710 : 1;
        *(int *)(slot(2) + babies->offset) = 2;
        if (father != NULL) {
            put_name(slot(2), father->offset, "Rongo");
            *(int *)(slot(2) + father_head->offset) = 3;
            *(int *)(slot(2) + father_body->offset) = 7;
        }
        compare(&g_snaps[0]);
        CHECK(g_outs == 1 && g_out[0].record == slot(2)
              && strstr(g_out[0].changes, "  Pregnant: no -> yes\n") != NULL
              && strstr(g_out[0].changes, "  Babies in pregnancy: 2\n") != NULL,
              "a pregnancy the event starts: Pregnant and the babies");
        CHECK(g_outs == 1
              && strstr(g_out[0].changes, "  Babies in pregnancy: 2\n  Expected father: Rongo\n"
                                          "  Expected father's head: 3\n  Expected father's body: 7\n") != NULL
              && (g_harness_game == 1 ? father == NULL && father_head == NULL && father_body == NULL
                                      : father != NULL && father_head != NULL && father_body != NULL),
              "...and the expected father's name, head and body (%s)",
              g_harness_game == 1 ? "the Show Parents companion's record of the conception"
                                  : "the conception copied them onto her");

        /* 3b. Delivered (A New Home and The Lost Children clear the litter;
           the later games leave their 1, 2 or 3), then one baby by the same
           father: the conception is printed whole though its father is the
           one already on her record. */
        *(int *)(slot(2) + pregnant->offset) = 0;
        *(int *)(slot(2) + babies->offset) = g_harness_game <= 2 ? 0 : 1;
        begin();
        *(int *)(slot(2) + pregnant->offset) = g_harness_game == 2 ? 615 : 1;
        compare(&g_snaps[0]);
        CHECK(g_outs == 1 && g_out[0].record == slot(2)
              && strstr(g_out[0].changes, "  Pregnant: no -> yes\n") != NULL
              && strstr(g_out[0].changes, "  Babies in pregnancy: 1\n") != NULL
              && strstr(g_out[0].changes, "  Expected father: Rongo\n") != NULL
              && strstr(g_out[0].changes, "  Expected father's head: 3\n") != NULL
              && strstr(g_out[0].changes, "  Expected father's body: 7\n") != NULL,
              "a second conception by the same father, one baby: \"Babies in pregnancy: 1\" and the father again");
        if (g_harness_game == 1) {
            /* 3d. A New Home with no conception recorded this session (the
               companion answers 0): no father line, never a stale one. */
            g_vv1_stash_index = -1;
            *(int *)(slot(2) + pregnant->offset) = 0;
            *(int *)(slot(2) + babies->offset) = 0;
            begin();
            *(int *)(slot(2) + pregnant->offset) = 1;
            compare(&g_snaps[0]);
            CHECK(g_outs == 1 && strcmp(g_out[0].changes, "  Pregnant: no -> yes\n  Babies in pregnancy: 1\n") == 0
                  && g_vv1_queried == 2,
                  "A New Home with no conception recorded for her: no expected father printed (record 2 asked)");
            g_vv1_stash_index = 2;
        }

        /* 3c. An event that changes the babies of a pregnancy (a Custom
           Island Event): one baby becomes three, "1 -> 3" in every game. */
        begin();
        *(int *)(slot(2) + babies->offset) = 3;
        compare(&g_snaps[0]);
        CHECK(g_outs == 1 && g_out[0].record == slot(2)
              && strcmp(g_out[0].changes, "  Babies in pregnancy: 1 -> 3\n") == 0,
              "a pregnancy's babies changed: \"Babies in pregnancy: 1 -> 3\" alone");

        /* 4. Stale bytes after a name's terminator. */
        begin();
        slot(2)[layout.name + 10] = 'x';
        compare(&g_snaps[0]);
        CHECK(g_outs == 0, "bytes after a name's terminator are no change");

        /* 5. A slot reused by someone else in one event: name and looks changed. */
        begin();
        memset(slot(0) + layout.name, 0, 8);
        put_name(slot(0), layout.name, "Bran");
        *(int *)(slot(0) + layout.head) += 4;
        *(int *)(slot(0) + layout.body) += 5;
        compare(&g_snaps[0]);
        CHECK(g_outs == 2 && g_out[0].live == 0 && strstr(g_out[0].changes, "  Gone: yes\n") != NULL
              && strcmp((const char *)g_out[0].record + layout.name, "?") == 0
              && g_out[1].record == slot(0) && strstr(g_out[1].changes, "  New villager: yes\n") != NULL
              && !any_contains("Name:"),
              "name, head and body changed in one slot: the one before Gone, the one now New (never a rename)");

        /* 6. Look-alikes (villager_lookalike.h): a statue, ghost or stand-in
           present before and after an event that changes everyone, and one
           that appears during it, are never logged; the villagers still are. */
        if (LOOKALIKE[g_harness_game] != 0) {
            int s, logged_lookalike = 0;
            slot(4)[present] = 1;
            slot(4)[LOOKALIKE[g_harness_game]] = 1;
            put_name(slot(4), layout.name, "Statue");
            begin();
            for (s = 0; s < 5; ++s) {
                if (skills_float) {
                    *(float *)(slot(s) + research->offset) += 1.0f;
                } else {
                    *(int *)(slot(s) + research->offset) += 1;
                }
            }
            slot(5)[present] = 1;
            slot(5)[LOOKALIKE[g_harness_game]] = 1;
            put_name(slot(5), layout.name, "Ghost");
            compare(&g_snaps[0]);
            for (s = 0; s < g_outs; ++s) {
                logged_lookalike |= g_out[s].record == slot(4) || g_out[s].record == slot(5)
                                    || strcmp((const char *)g_out[s].record + layout.name, "Statue") == 0;
            }
            CHECK(g_outs == 3 && !logged_lookalike && !any_contains("Gone:") && !any_contains("New villager:")
                  && g_out[0].record == slot(0) && g_out[1].record == slot(2) && g_out[2].record == slot(3),
                  "look-alikes (+0x%X) are never logged, before, after or appearing; the three villagers are",
                  LOOKALIKE[g_harness_game]);
        }

        /* 7. The later games' two-choice answer: "Choice:" as A New Home and
           The Lost Children write it (their answer_label). */
        if (g_harness_game >= 3) {
            check_choice(&layout, research, skills_float);
        }

        memset(g_array, 0, (size_t)SLOTS * ARRAYS[g_harness_game].stride);
        VirtualFree(g_array, 0, MEM_RELEASE);
    }
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
