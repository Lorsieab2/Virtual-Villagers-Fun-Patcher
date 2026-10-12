/* Deaths in the load-time catch-up and the bodies a load packs: every Death
   record keeps its real cause (all five games).

   The owner (2026-10-11): "deaths during catchup should still be recorded"
   -- A New Home's Death 53, Hiji Temitope (age 1682, old age in a Time
   Skip), said "Cause of death: (not recorded: ...)".  His body lay through
   the save of 20:48:51 (Virtual Villagers21.ldw: health 0, age 1682) and was
   buried after the village was loaded again; the Deaths log was written at
   the next save, 20:50:02.

   A New Home and The Lost Children keep no cause of their own: the companion
   keeps each body's, by record, in the graves file (cod_vv12.inc).  The game's
   load packs the records (a body in record 6 is in record 3 after it), and
   the file was read, and its causes moved to the bodies' new records, only by
   the per-frame tick -- which runs once a village frame is drawn, after the
   load-time catch-up and the village's first updates.  Before it:
     - a body removed by the catch-up (240 minutes unburied: the usual end of
       a body after time away) or buried had no cause;
     - a death in the catch-up was put on the record the dying villager is in
       NOW, over the cause the file keeps for ANOTHER body that lay in that
       record before the load -- that body's cause was lost.
   Both in a new session and in a village loaded again in the same session.
   The fix (vv12_sync): every hooked death, burial and removal first binds the
   tables to the village being loaded (its slot is the game's own, set by the
   slot menu before the load) and moves the file's causes to their bodies.

   The Secret City, The Tree of Life and New Believers keep the cause on the
   record (+0xE7C; +0x1C44) and the Death record takes it from there, so a
   body from before the load gets the game's own cause there too: checked
   here for the removal of an unburied body before the first frame.

   This harness compiles the companion's whole source in (as the TEST build)
   with the Documents folder redirected to the folder on the command line,
   so every file it touches is inside that folder -- never the real
   Documents\LDW.  Its modes, each in a fresh folder:

     write <docs> <game>       A New Home / The Lost Children: the session in
                               which two villagers die (Old age, Disease);
                               their bodies are saved unburied (the quit)
     read <docs> <game> host   a new session: the catch-up kills a villager
                               the load packed into the first body's old
                               record and removes the first body; the second
                               body is buried before the first frame is
                               drawn; then the new body -- each with its cause
     read <docs> <game> late   the same with the slot not known until the
                               first frame (the catch-up's death waits for
                               it), then the removal and the burials
     reload <docs> <game>      the same village saved, and loaded again in
                               the same session
     later <docs> <game>       The Secret City, The Tree of Life, New
                               Believers: a body from before the load
                               removed in the catch-up keeps the game's cause

   Exit code 0 when every check passes.  Built and run by
   scripts/build_cause_catchup_harness.ps1 (tests/test_cause_catchup_deaths.py). */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static char g_docs[MAX_PATH];
static wchar_t g_docs_w[MAX_PATH];

static BOOL WINAPI harness_special_a(HWND owner, LPSTR out, int csidl, BOOL create) {
    (void)owner; (void)csidl; (void)create;
    lstrcpyA(out, g_docs);
    return TRUE;
}

static BOOL WINAPI harness_special_w(HWND owner, LPWSTR out, int csidl, BOOL create) {
    (void)owner; (void)csidl; (void)create;
    lstrcpyW(out, g_docs_w);
    return TRUE;
}

static HRESULT WINAPI harness_folder_a(HWND owner, int csidl, HANDLE token, DWORD flags, LPSTR out) {
    (void)owner; (void)csidl; (void)token; (void)flags;
    lstrcpyA(out, g_docs);
    return S_OK;
}

static HRESULT WINAPI harness_folder_w(HWND owner, int csidl, HANDLE token, DWORD flags, LPWSTR out) {
    (void)owner; (void)csidl; (void)token; (void)flags;
    lstrcpyW(out, g_docs_w);
    return S_OK;
}

/* The game's save managers, at the harness's own addresses. */
static const unsigned char *harness_managers[6];
#define VV_GAME_SAVE_MANAGER_AT(game) ((const unsigned char *const volatile *)&harness_managers[game])

#define SHGetSpecialFolderPathA harness_special_a
#define SHGetSpecialFolderPathW harness_special_w
#define SHGetFolderPathA harness_folder_a
#define SHGetFolderPathW harness_folder_w
#define VVFP_TEST 1
#include "../shared/save_folder.c"
#include "vvfp_cause_of_death.c"
#include "../shared/game_save_slot.h"
#undef SHGetSpecialFolderPathA
#undef SHGetSpecialFolderPathW
#undef SHGetFolderPathA
#undef SHGetFolderPathW

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

static int game;
static unsigned char *table;
static unsigned char manager[0x31000];   /* the save manager; the slot at VV_GAME_SAVE_SLOT_FIELD */
static unsigned char graveyard[0x31000];
static unsigned char save_buffer[64];

/* The host's slot as the Origins companions answer it: the game's own. */
static int __stdcall host_slot(void) {
    return vv_current_save_slot(game, 0);
}
static struct { int size; int (__stdcall *slot)(void); } host = { 8, host_slot };

#define SLOT 1

/* The Death records written, in order: name and cause line. */
#define WRITTEN 16
static char written_name[WRITTEN][32];
static char written_cause[WRITTEN][192];
static int written_count;

static unsigned char *rec(int i) { return table + (size_t)i * REC[game].stride; }

static int __stdcall harness_writer(int g, int kind, const void *record, int check, const char *before,
                                    const char *after, int detail) {
    const char *line;
    const char *end;
    (void)g; (void)check; (void)after; (void)detail;
    if (kind != LOG_DEATH || written_count >= WRITTEN) {
        return 1;
    }
    lstrcpynA(written_name[written_count], (const char *)record + REC[game].name, 32);
    written_cause[written_count][0] = '\0';
    line = strstr(before, "  Cause of death: ");
    if (line != NULL) {
        line += 18;
        end = strchr(line, '\n');
        if (end == NULL) end = line + strlen(line);
        lstrcpynA(written_cause[written_count], line,
                  (int)((end - line + 1) < 192 ? (end - line + 1) : 192));
    }
    ++written_count;
    return 1;
}

/* The cause the Death record of `name` says, or NULL when none was written. */
static const char *cause_of(const char *name) {
    int i;
    for (i = 0; i < written_count; ++i) {
        if (strcmp(written_name[i], name) == 0) {
            return written_cause[i];
        }
    }
    return NULL;
}

static int says(const char *name, const char *words) {
    const char *got = cause_of(name);
    return got != NULL && strcmp(got, words) == 0;
}

static void villager(int i, const char *name, int age, int health) {
    memset(rec(i), 0, REC[game].stride);
    rec(i)[REC[game].present] = 1;
    *(int *)(rec(i) + REC[game].health) = health;
    *(int *)(rec(i) + REC[game].age) = age;
    *(int *)(rec(i) + REC[game].sex) = 1 + (i & 1);
    strncpy((char *)rec(i) + REC[game].name, name, REC[game].name_capacity - 1);
}

static void set_game_slot(int slot) {
    *(int *)(manager + VV_GAME_SAVE_SLOT_FIELD[game]) = slot;
}

static void frames(int n) {
    while (n-- > 0) {
        VvfpCauseTick(game);
    }
}

/* The village as it was saved: the living, and two bodies with gaps before
   them, so the load packs each body into a lower record.
     record  0 Ana, 2 Bo, 4 Cai          -> 0, 1, 2
            6 Hiji Temitope (body)       -> 3
            7 Dede, 8 Eno, 10 Fai        -> 4, 5, 6   (Fai: the first body's old record)
           12 Kita Awanata (body)        -> 7
           13 Lio, 14 Mana               -> 8, 9 */
#define FIRST_OLD 6
#define FIRST_NEW 3
#define SECOND_OLD 12
#define SECOND_NEW 7
#define FAI_OLD 10
#define FAI_NEW 6
static const char *const FIRST = "Hiji Temitope";
static const char *const SECOND = "Kita Awanata";
static const char *const FAI = "Fai Alosaka";

static void saved_village(int dead) {
    memset(table, 0, (size_t)REC[game].stride * 20);
    villager(0, "Ana", 400, 80);
    villager(2, "Bo", 410, 80);
    villager(4, "Cai", 420, 80);
    villager(FIRST_OLD, FIRST, 1682, dead ? 0 : 60);
    villager(7, "Dede", 430, 80);
    villager(8, "Eno", 440, 80);
    villager(FAI_OLD, FAI, 1300, 2);
    villager(SECOND_OLD, SECOND, 1732, dead ? 0 : 60);
    villager(13, "Lio", 450, 80);
    villager(14, "Mana", 460, 80);
}

/* The game's load: the occupied records packed into 0, 1, 2, ... */
static void game_load_packs(void) {
    int to = 0, from;
    for (from = 0; from < 20; ++from) {
        if (rec(from)[REC[game].present]) {
            if (from != to) {
                memcpy(rec(to), rec(from), REC[game].stride);
                memset(rec(from), 0, REC[game].stride);
            }
            ++to;
        }
    }
}

/* The two deaths, in the session before, and the quit's save. */
static void session_write(void) {
    saved_village(0);
    set_game_slot(SLOT);
    frames(3);
    cod_died(rec(FIRST_OLD), CAUSE_OLD_AGE);
    *(int *)(rec(FIRST_OLD) + REC[game].health) = 0;
    cod_died(rec(SECOND_OLD), CAUSE_DISEASE);
    *(int *)(rec(SECOND_OLD) + REC[game].health) = 0;
    frames(3);
    cod_save_done(SLOT, save_buffer);
    CHECK(store.loaded && bodies[FIRST_OLD].valid && bodies[SECOND_OLD].valid,
          "the two bodies' causes are kept for the save");
}

/* The catch-up, then the village: Fai (packed into the first body's old
   record) starves in the catch-up, the first body is removed unburied, the
   second body is buried (the graveyard full) in the first update -- before
   the first frame is drawn when the slot was known at the load -- and then
   Fai's. */
static void catch_up_and_play(int slot_late) {
    CHECK(strcmp((const char *)rec(FAI_NEW) + REC[game].name, FAI) == 0
          && strcmp((const char *)rec(FIRST_NEW) + REC[game].name, FIRST) == 0
          && strcmp((const char *)rec(SECOND_NEW) + REC[game].name, SECOND) == 0,
          "the load packed the records (Fai now in record %d, the bodies in %d and %d)",
          FAI_NEW, FIRST_NEW, SECOND_NEW);
    set_game_slot(slot_late ? 0 : SLOT);
    /* The catch-up's starvation drain (K_DEC1): the cause is recorded before
       the store that kills. */
    cod_died(rec(FAI_NEW), CAUSE_STARVATION);
    *(int *)(rec(FAI_NEW) + REC[game].health) = 0;
    if (slot_late) {
        set_game_slot(SLOT);
        frames(1);
    }
    /* The catch-up's removal of a body unburied for 240 minutes, before the
       store that clears the presence byte. */
    cod_decayed(rec(FIRST_NEW));
    rec(FIRST_NEW)[REC[game].present] = 0;
    /* A burial in the village's first update, before its first frame is drawn
       (slot known at the load) or after it: the game frees the record, finds
       no free grave, and the hook after its grave loop runs. */
    rec(SECOND_NEW)[REC[game].present] = 0;
    cod_buried(SECOND_NEW, 0, -1);
    if (!slot_late) {
        frames(1);
    }
    rec(FAI_NEW)[REC[game].present] = 0;
    cod_buried(FAI_NEW, 0, -1);
    CHECK(says(FIRST, "Old age"), "%s, removed in the catch-up: \"%s\"", FIRST,
          cause_of(FIRST) ? cause_of(FIRST) : "(no Death record)");
    CHECK(says(SECOND, "Disease"), "%s, buried after the load: \"%s\"", SECOND,
          cause_of(SECOND) ? cause_of(SECOND) : "(no Death record)");
    CHECK(says(FAI, "Starvation"), "%s, who died in the catch-up: \"%s\"", FAI,
          cause_of(FAI) ? cause_of(FAI) : "(no Death record)");
}

static void session_read(int slot_late) {
    saved_village(1);
    game_load_packs();
    catch_up_and_play(slot_late);
}

/* The same village saved, and loaded again in this same session (back to
   the title, then the slot again): the tables stay bound to the slot, keyed
   by the records as they were before the load. */
static void session_reload(void) {
    session_write();
    game_load_packs();
    catch_up_and_play(0);
}

/* The Secret City, The Tree of Life, New Believers: the record keeps the
   game's cause; a body from before the load is removed before any frame. */
static void session_later(void) {
    memset(table, 0, (size_t)REC[game].stride * 4 + REC[game].record_base);
    set_game_slot(SLOT);
    villager(0, "Ana", 400, 80);
    villager(1, FIRST, 1682, 0);
    *(int *)(rec(1) + V345[game].cause) = CAUSE_OLD_AGE;
    villager(2, SECOND, 1732, 0);
    *(int *)(rec(2) + V345[game].cause) = CAUSE_DISEASE;
    v345_decayed_record(rec(1));
    v345_decayed_record(rec(2));
    CHECK(says(FIRST, "Old age"), "%s, removed in the catch-up: \"%s\"", FIRST,
          cause_of(FIRST) ? cause_of(FIRST) : "(no Death record)");
    CHECK(says(SECOND, "Disease"), "%s, removed in the catch-up: \"%s\"", SECOND,
          cause_of(SECOND) ? cause_of(SECOND) : "(no Death record)");
}

int main(int argc, char **argv) {
    size_t span;
    const char *mode;
    if (argc < 4) {
        printf("usage: catchup_deaths_harness write|read|reload|later <docs folder> <game> [host|late]\n");
        return 2;
    }
    mode = argv[1];
    lstrcpynA(g_docs, argv[2], MAX_PATH);
    MultiByteToWideChar(CP_ACP, 0, g_docs, -1, g_docs_w, MAX_PATH);
    game = atoi(argv[3]);
    if (game < 1 || game > 5 || (strcmp(mode, "later") == 0) != (game >= 3)) {
        printf("A New Home and The Lost Children: write, read, reload; the later three: later\n");
        return 2;
    }
    span = (size_t)REC[game].record_base + (size_t)REC[game].stride * 20;
    if (game <= 2 && span < (size_t)GRV[game].owner + 4) {
        span = (size_t)GRV[game].owner + 4;
    }
    table = (unsigned char *)VirtualAlloc(NULL, span, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (table == NULL) {
        printf("no memory\n");
        return 2;
    }
    if (game <= 2) {
        *(unsigned char **)(table + GRV[game].owner) = graveyard;
    }
    harness_managers[game] = manager;
    VvfpCauseRollTest = 0;
    VvfpCauseTestSetup(game, &host, table);
    /* VvfpCauseTestSetup hands the records' base; the harness's table is
       the records themselves for the later three too. */
    table += REC[game].record_base;
    write_record = harness_writer;
    log_state = 1;
    printf("%s, game %d%s%s\n", mode, game, argc > 4 ? ", " : "", argc > 4 ? argv[4] : "");
    if (strcmp(mode, "write") == 0) {
        session_write();
    } else if (strcmp(mode, "read") == 0) {
        session_read(argc > 4 && strcmp(argv[4], "late") == 0);
    } else if (strcmp(mode, "reload") == 0) {
        session_reload();
    } else if (strcmp(mode, "later") == 0) {
        session_later();
    } else {
        return 2;
    }
    printf(failures ? "%d FAILED\n" : "all passed\n", failures);
    return failures ? 1 : 0;
}
