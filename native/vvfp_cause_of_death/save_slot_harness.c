/* A death recorded in a session whose village was MADE in that session keeps
   its cause through the save and a reload (The Lost Children, A New Home).

   Live (2026-10-10, The Lost Children): the game loaded a lost tribe in slot
   1; the player chose Change Tribe and made a new tribe in slot 2; three
   villagers died in that session; their bodies were saved unburied at the
   clean quit; the next session buried them and the Deaths log said "not
   recorded".  The game's save-all (0x424C00) ends with a save of the backup
   generation, slot + 20, so the save-path stub's slot read 22 -- "no slot" --
   from the new tribe's first save until the quit, the per-frame tick never
   bound the graves file, and the causes (kept only in memory) were lost.

   This harness compiles the companion's whole source in (as the TEST build)
   with the Documents folder redirected to the folder given on the command
   line, so every file it touches is inside that folder -- never the real
   Documents\LDW.  It runs as two processes, two game sessions:

     write <docs> <game> <mode>   the session that makes the village and
                                  records the deaths, then saves (the quit)
     read  <docs> <game> <mode>   a new session: the bodies are buried and
                                  each grave must show the recorded cause

   mode "host": the Origins host's slot as fixed (native/shared/
   game_save_slot.h) -- the game's own current slot from its save manager,
   with the stub stale (VV2: 22; VV1: 5, the first village of a fresh save
   folder); the slot must be the village's from creation, and the graves
   file written by the per-frame tick, before any save.
   mode "zero": a host that reports no slot all session (the old VV2
   behaviour); the save itself must write the causes to the saved slot.

   Exit code 0 when every check passes.  Built and run by
   tests/test_cause_save_slot.py. */
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
static int zero_mode;
static int stub_slot;                 /* what the exe's save-path stub holds */
static unsigned char *table;
static unsigned char manager[0x31000];   /* the save manager; the slot at VV_GAME_SAVE_SLOT_FIELD */
static unsigned char graveyard[0x31000];  /* the graves' owner (GRV[game].graves on) */
static unsigned char save_buffer[64];

/* The host's slot: as the Origins companions answer it now, or nothing. */
static int __stdcall host_slot(void) {
    return zero_mode ? 0 : vv_current_save_slot(game, stub_slot);
}
static struct { int size; int (__stdcall *slot)(void); } host = { 8, host_slot };

#define NEW_SLOT 2
#define OLD_SLOT 1
#define BODIES 3
static const char *const NAMES[BODIES] = { "Kaia Kotori", "Atepa Wanjiko", "Bibi Kenobi" };
static const int AGES[BODIES] = { 830, 660, 638 };
static const int CAUSES[BODIES] = { CAUSE_OLD_AGE, CAUSE_DISEASE, CAUSE_STARVATION };

static unsigned char *rec(int i) { return table + (size_t)i * REC[game].stride; }

static void villager(int i, const char *name, int age, int health) {
    memset(rec(i), 0, REC[game].stride);
    rec(i)[REC[game].present] = 1;
    *(int *)(rec(i) + REC[game].health) = health;
    *(int *)(rec(i) + REC[game].age) = age;
    *(int *)(rec(i) + REC[game].sex) = 2;
    strncpy((char *)rec(i) + REC[game].name, name, REC[game].name_capacity - 1);
}

/* The new village: three who will die, and two who live. */
static void make_village(int dead) {
    int i;
    for (i = 0; i < BODIES; ++i) {
        villager(i, NAMES[i], AGES[i], dead ? 0 : 50);
    }
    villager(3, "Amiri Bahati", 436, 80);
    villager(4, "Hiji Tamikai", 250, 80);
}

static void set_game_slot(int slot) {
    *(int *)(manager + VV_GAME_SAVE_SLOT_FIELD[game]) = slot;
}

static void graves_path(int slot, char *out) {
    char exe[MAX_PATH], *base, *dot;
    GetModuleFileNameA(NULL, exe, MAX_PATH);
    base = strrchr(exe, '\\') + 1;
    dot = strrchr(base, '.');
    if (dot) *dot = 0;
    _snprintf(out, MAX_PATH,
              "%s\\LDW\\%s\\Virtual Villagers Fun Patcher Data\\Graves\\Virtual Villagers %d Graves - Save %d.dat",
              g_docs, base, game, slot);
    out[MAX_PATH - 1] = 0;
}

/* The lying bodies' causes in slot's graves file: how many bodies carry the
   cause recorded for them. */
static int file_bodies(int slot, int *entries) {
    char path[MAX_PATH];
    unsigned char buf[16 + 44 * 64];
    FILE *f;
    long n;
    unsigned int count, k;
    int matched = 0;
    graves_path(slot, path);
    *entries = -1;
    f = fopen(path, "rb");
    if (f == NULL) return 0;
    n = (long)fread(buf, 1, sizeof buf, f);
    fclose(f);
    if (n < 16) return 0;
    count = *(unsigned int *)(buf + 12);
    *entries = (int)count;
    for (k = 0; k < count && 16 + (k + 1) * 44 <= (unsigned)n; ++k) {
        const unsigned char *e = buf + 16 + k * 44;
        int i;
        if (e[0] != 1) continue;
        for (i = 0; i < BODIES; ++i) {
            if (*(const unsigned int *)(e + 4) == cod_fingerprint((const unsigned char *)NAMES[i],
                                                                   REC[game].name_capacity, AGES[i])
                && (signed char)e[8] == CAUSES[i] && e[2] == i) {
                ++matched;
            }
        }
    }
    return matched;
}

static void frames(int n) {
    while (n-- > 0) {
        VvfpCauseTick(game);
    }
}

static int session_write(void) {
    int entries;
    int i;
    /* Game start: the lost tribe in slot 1 is loaded (stub and game agree). */
    stub_slot = OLD_SLOT;
    set_game_slot(OLD_SLOT);
    villager(0, "Lost One", 900, 0);
    frames(3);
    CHECK(cod_slot() == (zero_mode ? 0 : OLD_SLOT), "the loaded tribe's slot is %d", cod_slot());
    /* Change Tribe -> NEW PLAYER (slot 2): the menu sets the game's slot,
       the new world replaces the records, and the save-all leaves the stub
       at the backup generation (VV2 22) -- or, in A New Home's first
       village, at 5 from the slot list. */
    set_game_slot(NEW_SLOT);
    stub_slot = game == 2 ? NEW_SLOT + 20 : 5;
    memset(table, 0, (size_t)REC[game].stride * 8);
    make_village(0);
    frames(3);
    if (!zero_mode) {
        CHECK(cod_slot() == NEW_SLOT, "the new tribe's slot from its creation: %d (stub %d)", cod_slot(), stub_slot);
    }
    /* Three die (the hooked sites record the cause before the store that kills). */
    for (i = 0; i < BODIES; ++i) {
        cod_died(rec(i), CAUSES[i]);
        *(int *)(rec(i) + REC[game].health) = 0;
    }
    frames(3);
    if (!zero_mode) {
        CHECK(file_bodies(NEW_SLOT, &entries) == BODIES,
              "the tick wrote the three causes to Save %d before any save (%d entries)", NEW_SLOT, entries);
    } else {
        CHECK(file_bodies(NEW_SLOT, &entries) == 0 && entries < 0,
              "with no slot from the host, nothing is written before the save");
    }
    CHECK(file_bodies(OLD_SLOT, &entries) == 0 && entries < 0, "the lost tribe's Save %d file is untouched", OLD_SLOT);
    if (game == 1) {
        CHECK(file_bodies(5, &entries) == 0 && entries < 0, "no Save 5 file");
    }
    /* The clean quit: the save of slot 2 (the game's own save hook). */
    cod_save_done(NEW_SLOT, save_buffer);
    CHECK(file_bodies(NEW_SLOT, &entries) == BODIES,
          "after the quit save, Save %d holds the three bodies' causes (%d entries)", NEW_SLOT, entries);
    CHECK(cod_slot() == NEW_SLOT, "after the save the slot is %d", cod_slot());
    frames(3);
    CHECK(file_bodies(NEW_SLOT, &entries) == BODIES, "a tick after the save keeps them (%d entries)", entries);
    return failures;
}

static int session_read(void) {
    int i;
    /* The next session loads slot 2: the bodies are still lying. */
    stub_slot = NEW_SLOT;
    set_game_slot(NEW_SLOT);
    make_village(1);
    zero_mode = 0;
    frames(3);
    CHECK(store.loaded && store.slot == NEW_SLOT, "the graves file of Save %d is loaded", NEW_SLOT);
    for (i = 0; i < BODIES; ++i) {
        unsigned char *grave = cod_grave(i);
        CHECK(cod_cause_of(rec(i), i) == CAUSES[i], "%s's body keeps cause %d (got %d)", NAMES[i], CAUSES[i],
              cod_cause_of(rec(i), i));
        /* The burial: the game frees the record and writes grave i. */
        memset(grave, 0, GRV[game].stride);
        strncpy((char *)grave, NAMES[i], GRV[game].name_capacity);
        *(int *)(grave + GRV[game].age) = AGES[i];
        cod_buried(i, 1, i);
        rec(i)[REC[game].present] = 0;
        CHECK(graves[i].valid && graves[i].cause == CAUSES[i], "%s's grave shows cause %d", NAMES[i], CAUSES[i]);
    }
    return failures;
}

int main(int argc, char **argv) {
    size_t span;
    if (argc != 5) {
        printf("usage: save_slot_harness write|read <docs folder> <game 1|2> host|zero\n");
        return 2;
    }
    lstrcpynA(g_docs, argv[2], MAX_PATH);
    MultiByteToWideChar(CP_ACP, 0, g_docs, -1, g_docs_w, MAX_PATH);
    game = atoi(argv[3]);
    zero_mode = strcmp(argv[4], "zero") == 0;
    if (game != 1 && game != 2) {
        printf("game must be 1 or 2\n");
        return 2;
    }
    /* The villager table, with the graves' owner pointer where the game
       keeps it (GRV[game].owner past the first record). */
    span = (size_t)GRV[game].owner + 4;
    if (span < (size_t)REC[game].stride * 8) span = (size_t)REC[game].stride * 8;
    table = (unsigned char *)VirtualAlloc(NULL, span, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (table == NULL) {
        printf("no memory\n");
        return 2;
    }
    *(unsigned char **)(table + GRV[game].owner) = graveyard;
    harness_managers[game] = manager;
    VvfpCauseRollTest = 0;
    VvfpCauseTestSetup(game, &host, table);
    printf("%s, game %d, %s host\n", argv[1], game, zero_mode ? "no-slot" : "fixed");
    if (strcmp(argv[1], "write") == 0) {
        session_write();
    } else if (strcmp(argv[1], "read") == 0) {
        session_read();
    } else {
        return 2;
    }
    printf(failures ? "%d FAILED\n" : "all passed\n", failures);
    return failures ? 1 : 0;
}
