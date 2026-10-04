/* Runtime harness for the Cause of Death companion's two files.  32-bit only.

   Drives the TEST build of "VVFP Cause of Death.dll" (its VvfpCauseTest*
   exports call the same routines the detours call) against real files under
   Documents\LDW\<this exe's basename>\Virtual Villagers Fun Patcher Data\
   Graves\ and ...\Unaccounted Villagers\, which the harness empties first
   and removes afterwards.

   THE GRAVES FILE (A New Home):
     1. A death and its burial, then the tick: the file for the slot exists
        with exactly the documented bytes, written through a .tmp that is gone.
     2. A fresh load of the DLL (a new game session) reads it back: the grave
        shows the same cause and epitaph; a grave whose name changed shows
        nothing.
     3. Deaths and burials the hooks report BEFORE the slot is known (the
        load-time catch-up) are kept and written once it is.
     4. Two slots never share entries.
     5. An unreadable file is set aside (".unreadable-...") and never
        overwritten; a file that cannot be opened is neither read nor written.
     6. The player's own epitaph: kept with flag 1 and its text, read back by
        a new session, and an unchanged one writes nothing.
     7. Start Over: VvfpCauseVillageReset forgets the slot, and the shared
        reset (native/shared/save_reset.c, linked in) deletes the file; the
        next village in that slot starts empty.

   THE VILLAGE ROSTER (the Unaccounted Villagers reconciliation):
     8. The first save writes the roster and reports nothing; a villager gone
        with no report is one Unaccounted record at the next save; the game's
        load packing the records (a reload) reports nothing; a reported
        departure and a reported arrival report nothing; an arrival nobody
        reported is one record; another village's roster is set aside
        without records; Start Over deletes the roster.

   EACH KIND IN ITS OWN FOLDER (native/shared/data_subfolder.h):
    10. A graves file and a roster an older build left loose in the Data
        folder are moved into Graves\ and Unaccounted Villagers\ at the
        first load, and read: the grave shows its cause, and the roster
        still reconciles. Where both a folder copy and a loose one exist,
        the folder's is read and the loose one is left byte-for-byte.
        Start Over deletes the slot's file at both places.
     9. A record freed by a recorded departure (a burial, a body's removal)
        and filled again: a newcomer nobody reported is one record even with
        the same sex, or the same name and sex (the buried villager's own
        bytes written back); so is one after a reported arrival that was
        then buried.  A reported birth into it, a villager born and buried
        between saves, a body kept across a save, a body revived, and the
        load packing the records after burials report nothing.

   Usage:  cause_files_harness.exe "<path to VVFP Cause of Death.test.dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>

#include "save_reset.h"
#include "../shared/harness_ldw_tree.h"

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

typedef int (__stdcall *setup_t)(int, const void *, void *);
typedef void (__stdcall *index_cause_t)(int, int);
typedef void (__stdcall *index_t)(int);
typedef void (__stdcall *tick_t)(int);
typedef void (__stdcall *reset_t)(int, int);
typedef int (__stdcall *grave_t)(int, int *, int *);
typedef void (__stdcall *epitaph_t)(int, const char *);

static setup_t setup;
static index_cause_t died_raw, buried;
static index_t decayed, arrived, saved;
static tick_t tick;
static reset_t reset;
static grave_t grave_of;
static epitaph_t edit_epitaph;
static int *roll;
static int *stats;            /* VvfpCauseStats: ... [9] = unaccounted */
static HMODULE dll;
static const char *dll_path;

/* A New Home's geometry, as the DLL's tables have it. */
#define STRIDE 0x3D8
#define PRESENT 0x28
#define HEALTH 0x344
#define AGE 0x348
#define SEX 0x350
#define NAME 0x370
#define SKILLS 0x3BC
#define MANAGER 0x3E010
#define GRAVES 0xA31C
#define GRAVE_STRIDE 0x2C
#define GRAVE_AGE 0x24
#define ENTRY 44
#define NO_CAUSE 0x7F       /* recorded nothing: a grave from before */

static unsigned char *array;
static unsigned char *manager;
static int current_slot;

static int __stdcall host_slot(void) { return current_slot; }
static struct { int size; int (__stdcall *slot)(void); } host = { 8, host_slot };

static unsigned char *rec(int i) { return array + i * STRIDE; }
static unsigned char *grave(int k) { return manager + GRAVES + k * GRAVE_STRIDE; }

static void villager(int i, const char *name, int age, int health, int building) {
    memset(rec(i), 0, STRIDE);
    rec(i)[PRESENT] = 1;
    *(int *)(rec(i) + HEALTH) = health;
    *(int *)(rec(i) + AGE) = age;
    *(int *)(rec(i) + SEX) = 1 + (i & 1);
    strncpy((char *)rec(i) + NAME, name, 0x1B);
    *(int *)(rec(i) + SKILLS + 4) = building;       /* storage index 1 = Building */
}

/* Somebody new written into record i (a memory edit), keeping the sex of
   whoever was there last. */
static void reoccupy(int i, const char *name) {
    int sex = *(int *)(rec(i) + SEX);
    villager(i, name, 500, 90, 0);
    *(int *)(rec(i) + SEX) = sex;
}

/* What a death site does: the cause is recorded before the store that
   kills, and then the villager is a body. */
static void died(int i, int cause) {
    died_raw(i, cause);
    *(int *)(rec(i) + HEALTH) = 0;
}

/* What the game does at a burial: free the record and write the grave. */
static void game_bury(int i, int k) {
    rec(i)[PRESENT] = 0;
    memset(grave(k), 0, GRAVE_STRIDE);
    strncpy((char *)grave(k), (const char *)rec(i) + NAME, 0x1B);
    *(int *)(grave(k) + GRAVE_AGE) = *(int *)(rec(i) + AGE);
    /* the best skill and its job, as the game's burial writes them */
    if (*(int *)(rec(i) + SKILLS + 4) > 0) {
        *(int *)(grave(k) + 0x1C) = *(int *)(rec(i) + SKILLS + 4);
        *(int *)(grave(k) + 0x20) = 4;                /* Builder */
    }
}

static void load(void) {
    dll = LoadLibraryA(dll_path);
    if (dll == NULL) {
        printf("cannot load %s\n", dll_path);
        exit(2);
    }
    setup = (setup_t)GetProcAddress(dll, "VvfpCauseTestSetup");
    died_raw = (index_cause_t)GetProcAddress(dll, "VvfpCauseTestDied");
    buried = (index_cause_t)GetProcAddress(dll, "VvfpCauseTestBuried");
    decayed = (index_t)GetProcAddress(dll, "VvfpCauseTestDecayed");
    arrived = (index_t)GetProcAddress(dll, "VvfpCauseTestArrived");
    saved = (index_t)GetProcAddress(dll, "VvfpCauseTestSaved");
    edit_epitaph = (epitaph_t)GetProcAddress(dll, "VvfpCauseTestEpitaph");
    tick = (tick_t)GetProcAddress(dll, "VvfpCauseTick");
    reset = (reset_t)GetProcAddress(dll, "VvfpCauseVillageReset");
    grave_of = (grave_t)GetProcAddress(dll, "VvfpCauseTestGrave");
    roll = (int *)GetProcAddress(dll, "VvfpCauseRollTest");
    stats = (int *)GetProcAddress(dll, "VvfpCauseStats");
    if (!setup || !died_raw || !buried || !decayed || !arrived || !saved || !edit_epitaph || !tick
        || !reset || !grave_of || !roll || !stats) {
        printf("missing exports\n");
        exit(2);
    }
    setup(1, &host, array);
    *roll = 1;
}

static void unload(void) {
    FreeLibrary(dll);
    dll = NULL;
}

static char data_dir[MAX_PATH];

static int locate(void) {
    char docs[MAX_PATH], exe[MAX_PATH], *base, *dot;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) return 0;
    if (GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) return 0;
    base = strrchr(exe, '\\');
    if (base == NULL) return 0;
    ++base;
    dot = strrchr(base, '.');
    if (dot) *dot = 0;
    _snprintf(data_dir, MAX_PATH, "%s\\LDW\\%s\\Virtual Villagers Fun Patcher Data", docs, base);
    data_dir[MAX_PATH - 1] = 0;
    return 1;
}

static void file_of(int slot, char *out) {
    _snprintf(out, MAX_PATH, "%s\\Graves\\Virtual Villagers 1 Graves - Save %d.dat", data_dir, slot);
    out[MAX_PATH - 1] = 0;
}

static void roster_of(int slot, char *out) {
    _snprintf(out, MAX_PATH, "%s\\Unaccounted Villagers\\Virtual Villagers 1 Village Roster - Save %d.dat",
              data_dir, slot);
    out[MAX_PATH - 1] = 0;
}

/* Where an older build wrote them: loose in the Data folder. */
static void loose_file_of(int slot, char *out) {
    _snprintf(out, MAX_PATH, "%s\\Virtual Villagers 1 Graves - Save %d.dat", data_dir, slot);
    out[MAX_PATH - 1] = 0;
}

static void loose_roster_of(int slot, char *out) {
    _snprintf(out, MAX_PATH, "%s\\Virtual Villagers 1 Village Roster - Save %d.dat", data_dir, slot);
    out[MAX_PATH - 1] = 0;
}

static const char *const KIND_FOLDERS[2] = { "Graves", "Unaccounted Villagers" };

static long read_file(const char *path, unsigned char *buf, long cap) {
    FILE *f = fopen(path, "rb");
    long n;
    if (f == NULL) return -1;
    n = (long)fread(buf, 1, (size_t)cap, f);
    fclose(f);
    return n;
}

static void wipe_files(const char *dir) {
    char pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA f;
    HANDLE h;
    _snprintf(pattern, MAX_PATH, "%s\\*", dir);
    pattern[MAX_PATH - 1] = 0;
    h = FindFirstFileA(pattern, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (!(f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
                _snprintf(path, MAX_PATH, "%s\\%s", dir, f.cFileName);
                path[MAX_PATH - 1] = 0;
                DeleteFileA(path);
            }
        } while (FindNextFileA(h, &f));
        FindClose(h);
    }
    RemoveDirectoryA(dir);
}

static void wipe(void) {
    char parent[MAX_PATH], sub[MAX_PATH], *slash;
    int k;
    for (k = 0; k < 2; ++k) {
        _snprintf(sub, MAX_PATH, "%s\\%s", data_dir, KIND_FOLDERS[k]);
        sub[MAX_PATH - 1] = 0;
        wipe_files(sub);
    }
    wipe_files(data_dir);
    lstrcpyA(parent, data_dir);
    slash = strrchr(parent, '\\');
    if (slash) { *slash = 0; RemoveDirectoryA(parent); }
}

/* Set-aside files, beside the file they were: in the kind's folder. */
static int count_unreadable(void) {
    char pattern[MAX_PATH];
    WIN32_FIND_DATAA f;
    HANDLE h;
    int n = 0;
    int k;
    for (k = 0; k < 2; ++k) {
        _snprintf(pattern, MAX_PATH, "%s\\%s\\*.unreadable-*", data_dir, KIND_FOLDERS[k]);
        pattern[MAX_PATH - 1] = 0;
        h = FindFirstFileA(pattern, &f);
        if (h != INVALID_HANDLE_VALUE) {
            do { ++n; } while (FindNextFileA(h, &f));
            FindClose(h);
        }
    }
    return n;
}

static int write_file(const char *path, const unsigned char *buf, long n) {
    FILE *f = fopen(path, "wb");
    long wrote;
    if (f == NULL) return 0;
    wrote = (long)fwrite(buf, 1, (size_t)n, f);
    fclose(f);
    return wrote == n;
}

static int unaccounted(void) { return stats[9]; }

/* The game's load: the occupied records packed into 0, 1, 2, ... */
static void game_reload(void) {
    int to = 0, from;
    for (from = 0; from < 256; ++from) {
        if (rec(from)[PRESENT]) {
            if (from != to) {
                memcpy(rec(to), rec(from), STRIDE);
                memset(rec(from), 0, STRIDE);
            }
            ++to;
        }
    }
}

int main(int argc, char **argv) {
    harness_ldw_tree_begin();   /* first: leaves Documents\LDW as it found it */
    char path[MAX_PATH], tmp[MAX_PATH];
    unsigned char buf[0x40000];
    long n;
    int cause, epitaph, before, i;

    if (argc < 2) {
        printf("usage: cause_files_harness <dll>\n");
        return 2;
    }
    dll_path = argv[1];
    if (!locate()) return 2;
    wipe();
    array = (unsigned char *)VirtualAlloc(NULL, MANAGER + 0x100, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    manager = (unsigned char *)VirtualAlloc(NULL, 0xB000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    *(unsigned char **)(array + MANAGER) = manager;

    printf("1. a death, its burial and the tick write the slot's file\n");
    load();
    current_slot = 2;
    tick(1);
    villager(5, "Builda", 1500, 30, 60);
    died(5, 2);                         /* Old age */
    game_bury(5, 3);
    buried(5, 3);
    tick(1);
    file_of(2, path);
    n = read_file(path, buf, sizeof buf);
    CHECK(n == 16 + ENTRY, "the file holds one entry (%ld bytes)", n);
    CHECK(n >= 16 && *(unsigned int *)buf == 0x31444356u && *(unsigned int *)(buf + 4) == 1u
          && *(unsigned int *)(buf + 8) == 1u && *(unsigned int *)(buf + 12) == 1u,
          "header: 'VCD1', version 1, game 1, count 1");
    CHECK(n == 16 + ENTRY && buf[16] == 0 && buf[17] == 0 && buf[18] == 3 && buf[19] == 0
          && buf[24] == 2 && buf[25] == 11 && buf[26] == 0 && buf[27] == 0
          && memcmp(buf + 28, "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0", 32) == 0,
          "entry: a grave, slot 3, cause 2 (Old age), epitaph 11 (Strong Arms, Big Heart), no text");
    _snprintf(tmp, MAX_PATH, "%s.tmp", path);
    CHECK(GetFileAttributesA(tmp) == INVALID_FILE_ATTRIBUTES, "no .tmp is left behind");
    CHECK(grave_of(3, &cause, &epitaph) && cause == 2 && epitaph == 11, "the grave shows Old age and the epitaph");
    unload();

    printf("2. a new session reads it back\n");
    load();
    tick(1);
    CHECK(grave_of(3, &cause, &epitaph) && cause == 2 && epitaph == 11, "read back from the file");
    grave(3)[0] = 'X';
    CHECK(grave_of(3, &cause, &epitaph) && cause == NO_CAUSE,
          "a grave whose name changed shows no cause (only an epitaph by the rule)");
    grave(3)[0] = 'B';
    unload();

    printf("3. deaths before the slot is known are kept\n");
    current_slot = 0;
    load();
    tick(1);
    villager(6, "Early", 900, 1, 0);
    died(6, 0);                         /* Disease, during the load-time catch-up */
    game_bury(6, 4);
    buried(6, 4);
    tick(1);                            /* still no slot */
    current_slot = 2;
    tick(1);
    CHECK(grave_of(4, &cause, &epitaph) && cause == 0, "the catch-up grave has its cause");
    CHECK(grave_of(3, &cause, &epitaph) && cause == 2, "the file's own grave is kept");
    n = read_file(path, buf, sizeof buf);
    CHECK(n == 16 + 2 * ENTRY, "both are in the file (%ld bytes)", n);
    unload();

    printf("4. slots never share entries\n");
    current_slot = 3;
    load();
    tick(1);
    CHECK(grave_of(3, &cause, &epitaph) && cause == NO_CAUSE && grave_of(4, &cause, &epitaph)
          && cause == NO_CAUSE, "slot 3 has none of slot 2's causes");
    villager(7, "Other", 1200, 30, 0);
    died(7, 3);
    game_bury(7, 5);
    buried(7, 5);
    tick(1);
    current_slot = 2;
    tick(1);
    CHECK(grave_of(5, &cause, &epitaph) && cause == NO_CAUSE, "slot 2 has none of slot 3's causes");
    CHECK(grave_of(3, &cause, &epitaph) && cause == 2, "slot 2's own are back");
    unload();

    printf("5. an unreadable file is set aside, never overwritten\n");
    file_of(4, path);
    {
        FILE *f = fopen(path, "wb");
        fwrite("garbage that is not a graves file", 1, 34, f);
        fclose(f);
    }
    current_slot = 4;
    load();
    tick(1);
    CHECK(count_unreadable() == 1, "the bad file was moved aside");
    villager(8, "After", 1000, 30, 0);
    died(8, 1);
    game_bury(8, 6);
    buried(8, 6);
    tick(1);
    n = read_file(path, buf, sizeof buf);
    CHECK(n == 16 + ENTRY && buf[24] == 1, "a new file holds only the new grave");
    unload();
    {
        HANDLE locked = CreateFileA(path, GENERIC_READ, 0, NULL, OPEN_EXISTING, 0, NULL);
        current_slot = 4;
        memset(manager + GRAVES, 0, 50 * GRAVE_STRIDE);
        load();
        tick(1);
        villager(9, "Locked", 1000, 30, 0);
        died(9, 1);
        game_bury(9, 7);
        buried(9, 7);
        tick(1);
        CloseHandle(locked);
        n = read_file(path, buf, sizeof buf);
        CHECK(n == 16 + ENTRY, "a file that cannot be opened is not written while it is locked");
        unload();
    }

    printf("6. the player's own epitaph is kept and read back\n");
    memset(grave(3), 0, GRAVE_STRIDE);  /* slot 2's grave 3 again (5 cleared the table) */
    strncpy((char *)grave(3), "Builda", 0x1B);
    *(int *)(grave(3) + GRAVE_AGE) = 1500;
    current_slot = 2;
    load();
    tick(1);
    edit_epitaph(3, "Builder of \xE9" "toiles");
    tick(1);
    file_of(2, path);
    n = read_file(path, buf, sizeof buf);
    CHECK(n == 16 + 2 * ENTRY && buf[16 + 10] == 1 && strcmp((const char *)buf + 16 + 12, "Builder of \xE9" "toiles") == 0,
          "flag 1 and the text, a byte above 0x7F included, in the file");
    CHECK(grave_of(3, &cause, &epitaph) && epitaph == 0x100 && cause == 2, "the grave keeps its cause");
    unload();
    load();
    tick(1);
    CHECK(grave_of(3, &cause, &epitaph) && epitaph == 0x100, "a new session reads the player's text back");
    before = stats[6];
    edit_epitaph(3, "Builder of \xE9" "toiles");
    tick(1);
    CHECK(stats[6] == before, "Done with the text unchanged writes nothing");
    edit_epitaph(3, "");
    tick(1);
    n = read_file(path, buf, sizeof buf);
    CHECK(n == 16 + 2 * ENTRY && buf[16 + 10] == 1 && buf[16 + 12] == 0, "an epitaph cleared is kept, empty");
    unload();

    printf("7. Start Over forgets the slot and deletes its file\n");
    current_slot = 2;
    load();
    tick(1);
    reset(1, 2);
    file_of(2, path);
    vv_reset_slot_state(1, 2, NULL);
    CHECK(GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES, "the reset deleted the file");
    tick(1);
    tick(1);
    CHECK(GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES, "nothing held in memory wrote it back");
    CHECK(grave_of(3, &cause, &epitaph) && cause == NO_CAUSE && epitaph != 0x100,
          "the new village starts empty: no cause, no player's text");
    file_of(3, path);
    CHECK(GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES, "slot 3's file is untouched");
    unload();

    printf("8. the village roster at each save\n");
    memset(array, 0, 256 * STRIDE);
    current_slot = 5;
    load();
    tick(1);
    for (i = 0; i < 8; ++i) {
        char name[16];
        _snprintf(name, sizeof name, "Rost%d", i);
        villager(i, name, 400 + i, 80, 0);
    }
    saved(5);
    roster_of(5, path);
    n = read_file(path, buf, sizeof buf);
    CHECK(n == 32 + 8 * (16 + STRIDE) && *(unsigned int *)buf == 0x31524356u && *(unsigned int *)(buf + 12) == 8u,
          "the first save writes the roster: 'VCR1', 8 entries (%ld bytes)", n);
    CHECK(unaccounted() == 0, "and reports nothing");
    rec(2)[PRESENT] = 0;                /* gone, nothing reported */
    saved(5);
    CHECK(unaccounted() == 1, "a villager gone with no report: one Unaccounted record");
    n = read_file(path, buf, sizeof buf);
    CHECK(n == 32 + 7 * (16 + STRIDE) && buf[32 + 2 * (16 + STRIDE)] == 3 && buf[32 + 2 * (16 + STRIDE) + 2] == 2,
          "the roster keeps record 3 at rank 2");
    unload();
    game_reload();                      /* a new session: 3..7 now in 2..6 */
    load();
    tick(1);
    saved(5);
    CHECK(unaccounted() == 0, "the load packing the records reports nothing");
    died(4, 2);
    game_bury(4, 8);
    buried(4, 8);
    villager(9, "Newborn", 0, 100, 0);
    arrived(9);
    saved(5);
    CHECK(unaccounted() == 0, "a reported departure and a reported arrival report nothing");
    villager(10, "Stranger", 500, 100, 0);
    saved(5);
    CHECK(unaccounted() == 1, "an arrival nobody reported: one record");
    saved(5);
    CHECK(unaccounted() == 1, "each record is written once");

    printf("9. a record freed by a recorded departure, then filled again\n");
    /* now: 0..3, 5, 6 the first eight's survivors, 9 Newborn, 10 Stranger */
    died(5, 2);
    game_bury(5, 10);
    buried(5, 10);
    reoccupy(5, "Intruder");            /* the same sex, nobody reported */
    saved(5);
    CHECK(unaccounted() == 2, "a newcomer of the same sex in a buried villager's record: one record");
    died(6, 2);
    game_bury(6, 11);
    buried(6, 11);
    rec(6)[PRESENT] = 1;                /* the buried villager's own bytes back */
    *(int *)(rec(6) + HEALTH) = 80;
    saved(5);
    CHECK(unaccounted() == 3, "the buried villager written back unreported, same name and sex: one record");
    died(3, 2);
    decayed(3);                         /* the unburied body removed */
    rec(3)[PRESENT] = 0;
    reoccupy(3, "Squatter");
    saved(5);
    CHECK(unaccounted() == 4, "a newcomer in a removed body's record: one record");
    villager(11, "Baby", 0, 100, 0);
    arrived(11);
    died(11, 0);
    game_bury(11, 12);
    buried(11, 12);
    reoccupy(11, "Changeling");         /* a reported arrival, gone, then nobody reported */
    saved(5);
    CHECK(unaccounted() == 5, "an arrival reported, then buried, then a newcomer unreported: one record");
    villager(12, "Brief", 0, 100, 0);
    arrived(12);
    died(12, 0);
    game_bury(12, 13);
    buried(12, 13);
    saved(5);
    CHECK(unaccounted() == 5, "born and buried between two saves: nothing");
    villager(13, "Later", 0, 100, 0);
    arrived(13);                        /* a birth, then a burial elsewhere */
    died(0, 2);
    game_bury(0, 15);
    buried(0, 15);
    reoccupy(0, "Heir");
    arrived(0);
    saved(5);
    CHECK(unaccounted() == 5, "a birth, then a burial in another record and a birth into it: nothing");
    died(2, 2);
    game_bury(2, 14);
    buried(2, 14);
    reoccupy(2, "Firstborn");
    arrived(2);                         /* a birth into a buried villager's record */
    saved(5);
    CHECK(unaccounted() == 5, "a reported birth into a buried villager's record: nothing");
    died(1, 3);                         /* a body ... */
    saved(5);
    CHECK(unaccounted() == 5, "a body kept across a save: nothing");
    *(int *)(rec(1) + HEALTH) = 60;     /* ... revived, no Death record */
    saved(5);
    CHECK(unaccounted() == 5, "a body revived keeps its record: nothing");
    unload();
    game_reload();                      /* the load packs the records after the burials
                                           (a new session: the counters start again) */
    load();
    tick(1);
    saved(5);
    CHECK(unaccounted() == 0, "the load packing the records after burials reports nothing");

    for (i = 0; i < 12; ++i) {
        char name[16];
        _snprintf(name, sizeof name, "Elsewhere%d", i);
        villager(i, name, 300, 90, 0);
    }
    saved(5);
    CHECK(unaccounted() == 0, "another village's roster: a new roster, no records");
    {
        FILE *f = fopen(path, "wb");
        fwrite("not a roster", 1, 12, f);
        fclose(f);
    }
    before = count_unreadable();
    saved(5);
    CHECK(unaccounted() == 0 && count_unreadable() == before + 1, "an unreadable roster is set aside, no records");
    reset(1, 5);
    vv_reset_slot_state(1, 5, NULL);
    CHECK(GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES, "Start Over deletes the roster");
    unload();

    printf("10. files an older build left loose in the Data folder\n");
    {
        char loose[MAX_PATH], moved[MAX_PATH], rloose[MAX_PATH], rmoved[MAX_PATH];
        unsigned char graves[16 + 2 * ENTRY], roster[0x40000], other[16 + 2 * ENTRY];
        long graves_n, roster_n, other_n;
        /* A real graves file and a real roster, as this build writes them,
           then put where an older build kept them. */
        memset(manager + GRAVES, 0, 50 * GRAVE_STRIDE);
        current_slot = 1;
        load();
        tick(1);
        villager(20, "Oldfile", 1400, 30, 60);
        died(20, 3);                        /* Work accident */
        game_bury(20, 8);
        buried(20, 8);
        tick(1);
        saved(1);
        unload();
        file_of(1, moved);
        roster_of(1, rmoved);
        loose_file_of(1, loose);
        loose_roster_of(1, rloose);
        graves_n = read_file(moved, graves, sizeof graves);
        roster_n = read_file(rmoved, roster, sizeof roster);
        CHECK(graves_n == 16 + ENTRY && roster_n > 32, "set up: a graves file and a roster (nonzero denominator)");
        CHECK(MoveFileA(moved, loose) && MoveFileA(rmoved, rloose), "both moved back to the loose names");

        load();
        tick(1);
        CHECK(GetFileAttributesA(loose) == INVALID_FILE_ATTRIBUTES && read_file(moved, buf, sizeof buf) == graves_n
              && memcmp(buf, graves, (size_t)graves_n) == 0,
              "the first load moved the graves file into Graves\\, byte for byte");
        CHECK(grave_of(8, &cause, &epitaph) && cause == 3, "and the grave still shows its cause (Work accident)");
        before = unaccounted();
        saved(1);
        CHECK(GetFileAttributesA(rloose) == INVALID_FILE_ATTRIBUTES && GetFileAttributesA(rmoved) != INVALID_FILE_ATTRIBUTES,
              "the save moved the roster into Unaccounted Villagers\\");
        CHECK(unaccounted() == before, "and reconciled against it: nobody unaccounted");
        unload();

        /* Both: the folder's copy is read, the loose one never touched. */
        memcpy(other, graves, sizeof other);
        other_n = graves_n;
        other[16 + 8] = 1;                  /* a different cause */
        CHECK(write_file(loose, other, other_n), "set up: a stale loose copy beside the folder's file");
        load();
        tick(1);
        CHECK(grave_of(8, &cause, &epitaph) && cause == 3, "the folder's file is read (its cause, not the loose copy's)");
        CHECK(read_file(loose, buf, sizeof buf) == other_n && memcmp(buf, other, (size_t)other_n) == 0,
              "the loose copy is left byte-for-byte");
        unload();

        /* Start Over: the slot's file at both places. */
        CHECK(write_file(rloose, roster, roster_n), "set up: a loose roster beside the folder's");
        vv_reset_slot_state(1, 1, NULL);
        CHECK(GetFileAttributesA(moved) == INVALID_FILE_ATTRIBUTES && GetFileAttributesA(loose) == INVALID_FILE_ATTRIBUTES,
              "Start Over deletes the graves file in Graves\\ and the loose one");
        CHECK(GetFileAttributesA(rmoved) == INVALID_FILE_ATTRIBUTES && GetFileAttributesA(rloose) == INVALID_FILE_ATTRIBUTES,
              "Start Over deletes the roster in Unaccounted Villagers\\ and the loose one");
    }

    wipe();
    printf("%s: %d failure(s)\n", failures ? "FAILED" : "PASSED", failures);
    return failures ? 1 : 0;
}
