/* Runtime harness for the babies lost with their mother (cod_lost.inc), all
   five games.  32-bit only.

   Drives the TEST build of "VVFP Cause of Death.dll" with its own villager
   table in each game's record geometry and its own record writer in place of
   "VVFP Parentage Export.dll" (VvfpCauseTestWriter), so it reads the text of
   every record the companion files.  Nothing is written to disk.

   For every game, on both departure paths -- a Death record (the burial and
   the unburied body's removal both write it through cod_log_death) and a
   Disappeared record (VvfpCauseVanished: the Custom Island Event, and the
   same cod_log_gone the stock disappearances call):
     1. a pregnant mother with one baby, head 0 and body 0, the father known
        (A New Home: from the VV1 Parentage stash; the others: the expected
        father the game copied onto her, head 0): the record's Nursing line,
        and a "Lost before birth" record naming mother, father and 1 baby;
     2. twins and triplets: "2 babies" / "3 babies";
     3. the father unknown (no name; A New Home: no stash): "(unknown)";
     4. the pregnancy field already cleared when the record is written, the
        tick having seen her pregnant: still lost -- unless her age counter
        shows the delivery came first, then nothing;
     5. a woman not pregnant: no line and no Lost record;
     6. New Believers' Heathen: the line, and no Lost record.

   Usage:  lost_birth_harness.exe "<path to VVFP Cause of Death.test.dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

struct geometry {
    unsigned int base, stride, slots, present, health, age, name, cap, sex, pregnant, litter, heathen,
        head, body;
    int female;
    unsigned int counter, father, fcap, fhead, fbody;
};

/* As vvfp_cause_of_death.c's REC and cod_lost.inc's LOST have them. */
static const struct geometry G[6] = {
    { 0 },
    { 0, 0x3D8, 256, 0x28, 0x344, 0x348, 0x370, 0x1C, 0x350, 0x358, 0x35C, 0, 0x360, 0x364, 2,
      0x34C, 0, 0, 0, 0 },
    { 0, 0xE48C, 256, 0x30, 0x52C, 0x530, 0x564, 0x18, 0x538, 0x540, 0x544, 0, 0x548, 0x54C, 2,
      0x534, 0x5C0, 0x18, 0x5E0, 0x5DC },
    { 0x14, 0x1F8C, 150, 0xF10, 0xE78, 0xDC4, 0xDD4, 0x19, 0xDC8, 0xE8C, 0xE90, 0, 0xDF0, 0xDF4, 1,
      0xE74, 0xE48, 0x18, 0xE68, 0xE64 },
    { 0x44, 0x2E3C, 150, 0x1CC4, 0x1C40, 0x1B8C, 0x1B9C, 0x19, 0x1B90, 0x1C4C, 0x1C50, 0, 0x1BB8, 0x1BBC, 1,
      0x1C3C, 0x1C10, 0x18, 0x1C30, 0x1C2C },
    { 0x48, 0x2F44, 150, 0x1CD4, 0x1C40, 0x1B8C, 0x1B9C, 0x19, 0x1B90, 0x1C4C, 0x1C50, 0x1CEC, 0x1BB8, 0x1BBC, 1,
      0x1C3C, 0x1C10, 0x18, 0x1C30, 0x1C2C },
};

typedef int (__stdcall *write_fn)(int, int, const void *, int, const char *, const char *, int);
typedef int (__stdcall *stash_fn)(int, char *, int, int *, int *);
typedef int (__stdcall *setup_t)(int, const void *, void *);
typedef void (__stdcall *set_writer_t)(write_fn);
typedef void (__stdcall *set_stash_t)(stash_fn);
typedef void (__stdcall *index_cause_t)(int, int);
typedef void (__stdcall *vanished_t)(int, int);
typedef void (__stdcall *void_t)(void);

static setup_t setup;
static set_writer_t set_writer;
static set_stash_t set_stash;
static index_cause_t death_record;
static vanished_t vanished;
static void_t lost_tick;

#define MAX_OUT 16
static struct { int kind; int check; char before[1024]; } out[MAX_OUT];
static int outs;

static int __stdcall capture(int game, int kind, const void *record, int check, const char *before,
                             const char *after, int detail) {
    (void)game; (void)record; (void)after; (void)detail;
    if (outs < MAX_OUT) {
        out[outs].kind = kind;
        out[outs].check = check;
        lstrcpynA(out[outs].before, before != NULL ? before : "", (int)sizeof out[outs].before);
        ++outs;
    }
    return 1;
}

/* A New Home's stash: "Tamil", head 0, body 7, for record 3 only (when on). */
static int stash_on;
static int __stdcall stash(int index, char *father, int capacity, int *head, int *body) {
    if (!stash_on || index != 3) {
        return 0;
    }
    lstrcpynA(father, "Tamil", capacity);
    *head = 0;
    *body = 7;
    return 1;
}

static int __stdcall host_slot(void) { return 1; }
static struct { int size; int (__stdcall *slot)(void); } host = { 8, host_slot };

static unsigned char *table;
static int game;

static unsigned char *rec(int i) { return table + G[game].base + (size_t)i * G[game].stride; }
static void put(int i, unsigned int at, int v) { *(int *)(rec(i) + at) = v; }

/* Ann in record 3, alive, female, head 0, body 0, age 600, counter 600. */
static void mother(int babies_field, int due, const char *father) {
    const struct geometry *g = &G[game];
    memset(rec(3), 0, g->stride);
    rec(3)[g->present] = 1;
    put(3, g->health, 80);
    put(3, g->age, 600);
    put(3, g->sex, g->female);
    strcpy((char *)rec(3) + g->name, "Ann");
    put(3, g->head, 0);
    put(3, g->body, 0);
    put(3, g->counter, 600);
    put(3, g->pregnant, due);
    put(3, g->litter, babies_field);
    if (g->father != 0 && father != NULL) {
        strcpy((char *)rec(3) + g->father, father);
        put(3, g->fhead, 0);
        put(3, g->fbody, 7);
    }
    lost_tick();                     /* the tick sees her alive, as it would */
}

static const char *find(int kind) {
    int k;
    for (k = 0; k < outs; ++k) {
        if (out[k].kind == kind) {
            return out[k].before;
        }
    }
    return NULL;
}

static int count(int kind) {
    int k, n = 0;
    for (k = 0; k < outs; ++k) {
        n += out[k].kind == kind;
    }
    return n;
}

/* Record 3 departs: a Death record (path 0) or a disappearance (path 1). */
static void depart(int path) {
    outs = 0;
    if (path == 0) {
        put(3, G[game].health, 0);
        death_record(3, 0);
    } else {
        rec(3)[G[game].present] = 0;
        vanished(game, 3);
    }
}

static int has(const char *text, const char *want) {
    return text != NULL && strstr(text, want) != NULL;
}

/* The babies field each game writes for one, two and three babies. */
static int field_for(int babies) {
    return babies == 1 ? (game <= 2 ? 0 : 1) : babies;
}

static void run_game(void) {
    static const char *const paths[2] = { "death", "disappearance" };
    const int departed_kind[2] = { 2, 3 };
    int path, babies;
    char want[160];
    for (path = 0; path < 2; ++path) {
        const char *how = path == 0 ? "died" : "disappeared";
        /* 1-2: one, two and three babies, the father known, head 0 / body 0. */
        for (babies = 1; babies <= 3; ++babies) {
            stash_on = 1;
            mother(field_for(babies), 400, "Tamil");
            depart(path);
            wsprintfA(want, "  Nursing: yes, %d %s (never born: lost with their mother)\n", babies,
                      babies > 1 ? "babies" : "baby");
            CHECK(has(find(departed_kind[path]), want), "game %d %s, %d baby/babies: the Nursing line",
                  game, paths[path], babies);
            wsprintfA(want, "  Babies nursing: %d\n", babies);
            CHECK(count(9) == 1 && has(find(9), "  Mother: Ann\n    Head: 0\n    Body: 0\n")
                  && has(find(9), "  Father: Tamil\n    Head: 0\n    Body: 7\n") && has(find(9), want),
                  "game %d %s, %d baby/babies: Lost before birth names mother, father, babies", game,
                  paths[path], babies);
            wsprintfA(want, "  What happened: the mother %s while nursing; never born\n", how);
            CHECK(has(find(9), want), "game %d %s: says how the babies were lost", game, paths[path]);
        }
        /* 3: the father unknown. */
        stash_on = 0;
        mother(field_for(1), 400, NULL);
        depart(path);
        CHECK(count(9) == 1 && has(find(9), "  Father: (unknown)\n    Head: (unknown)\n    Body: (unknown)\n"),
              "game %d %s: an unknown father is (unknown)", game, paths[path]);
        /* 4: the field cleared by the time of the record; the tick saw her pregnant. */
        stash_on = 1;
        mother(field_for(2), 590, "Tamil");
        lost_tick();
        put(3, G[game].pregnant, 0);
        depart(path);
        CHECK(has(find(departed_kind[path]), "  Nursing: yes, 2 babies") && count(9) == 1,
              "game %d %s: a field cleared after the tick saw her pregnant: still lost", game, paths[path]);
        mother(field_for(2), 590, "Tamil");
        lost_tick();
        put(3, G[game].pregnant, 0);
        put(3, G[game].counter, 590 + 45);       /* past the delivery: she gave birth first */
        depart(path);
        CHECK(!has(find(departed_kind[path]), "Nursing") && count(9) == 0,
              "game %d %s: delivered before the record: nothing lost", game, paths[path]);
        /* 5: not pregnant. */
        mother(0, 0, NULL);
        depart(path);
        CHECK(find(departed_kind[path]) != NULL && !has(find(departed_kind[path]), "Nursing")
              && count(9) == 0, "game %d %s: not pregnant: no line, no Lost record", game, paths[path]);
    }
    /* 6: New Believers' Heathen. */
    if (G[game].heathen != 0) {
        mother(1, 400, "Tamil");
        rec(3)[G[game].heathen] = 1;
        depart(0);
        CHECK(has(find(2), "  Nursing: yes, 1 baby") && count(9) == 0,
              "game %d: a Heathen's record says it, no Lost record", game);
    }
}

int main(int argc, char **argv) {
    HMODULE dll;
    size_t bytes = 0x40000;
    if (argc < 2) {
        printf("usage: lost_birth_harness <VVFP Cause of Death.test.dll>\n");
        return 2;
    }
    dll = LoadLibraryA(argv[1]);
    if (dll == NULL) {
        printf("cannot load %s\n", argv[1]);
        return 2;
    }
    setup = (setup_t)GetProcAddress(dll, "VvfpCauseTestSetup");
    set_writer = (set_writer_t)GetProcAddress(dll, "VvfpCauseTestWriter");
    set_stash = (set_stash_t)GetProcAddress(dll, "VvfpCauseTestVv1Stash");
    death_record = (index_cause_t)GetProcAddress(dll, "VvfpCauseTestDeathRecord");
    vanished = (vanished_t)GetProcAddress(dll, "VvfpCauseVanished");
    lost_tick = (void_t)GetProcAddress(dll, "VvfpCauseTestLostTick");
    if (!setup || !set_writer || !set_stash || !death_record || !vanished || !lost_tick) {
        printf("missing exports\n");
        return 2;
    }
    for (game = 1; game <= 5; ++game) {
        size_t need = G[game].base + (size_t)G[game].slots * G[game].stride;
        if (need > bytes) {
            bytes = need;
        }
    }
    table = (unsigned char *)calloc(1, bytes);
    if (table == NULL) {
        return 2;
    }
    set_writer(capture);
    set_stash(stash);
    for (game = 1; game <= 5; ++game) {
        memset(table, 0, bytes);
        setup(game, &host, table);
        printf("game %d\n", game);
        run_game();
    }
    printf(failures ? "%d FAILED\n" : "all passed\n", failures);
    return failures ? 1 : 0;
}
