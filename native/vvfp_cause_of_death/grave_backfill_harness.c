/* Runtime harness for the grave backfill: every grave in the Deaths log.
   32-bit only.

   Drives the TEST build of "VVFP Cause of Death.dll" (copied into "Virtual
   Villagers Fun Patcher Files" beside this executable under its shipped
   name, so "VVFP Parentage Export.dll" finds it there as it does in a game)
   and the shipped "VVFP Parentage Export.dll" (also copied there, the one
   copy both use), in all five games'
   geometry, against real files under Documents\LDW\<this exe's
   basename>\, which harness_ldw_tree.h leaves as it found them.

   The owner: "the player should be notified first before any fix runs" --
   the first-load cross-check asks VvfpCauseScanGraves how many graves lack a
   record, lists them in its popup, and passes the player's answer to
   VvfpCauseRepairGraves; only Repair writes anything.

   Each game, a village "Backfill Tribe" in slot 1 holding seven graves --
     0 Kito  1410  1 Chika 1428  2 Ghali 1434  3 Onawa 1379
     4 Dup    900  5 Dup    900  (two graves alike: name, age, skill line)
     6 Lonely 600  (never in the Village History log)
     20 Tupa 1222  (an Adept Scientist's grave)
   -- a Deaths log written by an older build with Death records for Ghali,
   Onawa, ONE Dup and a "no grave" Lonely (the owner's A New Home: Ghali and
   Onawa recorded, Kito and Chika buried before the log existed), a record
   for Tupa appended by hand in exactly the shape the owner appended Kito's
   and Chika's (its own "Recorded:" line, and "Master Scientist" where the
   grave says Adept), another
   village's log with a Kito record, and a Village History log in the
   population exporter's own format (Kito and Chika as the owner's last
   snapshot has them; a living namesake Kito, listed older than the dead
   Kito was last listed; another village's Chika, listed older than this
   village's; a namesake Lonely who lived past the grave's age):
     0. The scan counts the four graves the log lacks and writes nothing
        (no log line, no graves file, A New Home's graves file untouched);
        "Not now" (and no answer at all) records nothing at the save.
     1. After Repair, the save records exactly Kito, Chika, the second Dup and Lonely, in
        burial order, numbered on from the log; Ghali, Onawa and the first
        Dup are not recorded again; nor is Tupa, whose hand-written record
        is recognised by name and age at death; the other village's Kito
        counts for nothing; the "no grave" Lonely record is not Lonely's
        grave.
     2. Each record carries the grave's name, age at death, skill line,
        cause (A New Home / The Lost Children from the graves file; the later
        games from the entry) and epitaph, the head, body, likes and dislikes
        of the villager's last History snapshot with its date and age (the
        living namesake, the other village and the namesake who outlived the
        grave's age are not taken), "(unknown)" for Lonely, and the
        "Recorded from the grave" note.
     3. A second save, and a new session's save, write nothing.  The graves
        file says which graves are covered: with the Deaths log deleted, a
        save still writes nothing.
     4. A grave added later whose Death record is already in the log (as the
        burial hook writes it) is not recorded again; nor one whose record is
        still held for the save (Village Statistics shipped: the record waits
        for its save), even across two saves before it is written.
     5. A villager the last save held, gone with no report and buried
        unseen (the load-time catch-up), is recorded from the grave and is
        NOT an Unaccounted record.
     6. Start Over deletes the graves file.

   And from Codex's review of #524: a record from the grave that is only
   held for the save (the village not yet named) and lost with the session
   leaves the grave uncovered, so the next scan finds it again; a villager
   made young again (listed older once, then younger) is still found; and a
   departure is accounted for only by a grave whose History looks are the
   villager's own -- Rua, known to her grave only by name and age, stays
   Unaccounted.

   "VVFP Save Reset.dll" (shipped) is copied into that folder too: the scan
   at load names the village from the slot's own save file through it, so a
   synthetic save "Virtual Villagers1.ldw" is written in the save folder.

   Usage:  grave_backfill_harness.exe "<parentage dll>" "<cause of death test dll>" "<save reset dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "village_identity.h"
#include "save_reset.h"
#include "../shared/harness_ldw_tree.h"
#include "patcher_files.h"

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

typedef int (__stdcall *record_t)(int, int, const void *, int, const char *, const char *, int);
typedef int (__stdcall *ensure_village_t)(int, const char *, const void *);
typedef int (__stdcall *setup_t)(int, const void *, void *);
typedef void (__stdcall *save_done_t)(int, const void *);
typedef void (__stdcall *tick_t)(int);
typedef void (__stdcall *reset_t)(int, int);
typedef void (__stdcall *roster_t)(void *, void *);
typedef int (__stdcall *scan_t)(int, int);
typedef void (__stdcall *repair_t)(int, int, int);
typedef void (__stdcall *buried_t)(int, int);

/* Each game's villager record, as both DLLs' tables have it. */
struct layout {
    int game;
    unsigned int stride, slots, base, active, age, head, body, name, name_cap, health, sex;
    unsigned int rva;
    int is_pointer;
};
static const struct layout LAYOUTS[5] = {
    { 1, 0x3D8,  256, 0,    0x28,   0x348,  0x360,  0x364,  0x370,  0x1C, 0x344,  0x350,  0x8B614u,  1 },
    { 2, 0xE48C, 256, 0,    0x30,   0x530,  0x548,  0x54C,  0x564,  0x18, 0x52C,  0x538,  0x99F24u,  1 },
    { 3, 0x1F8C, 150, 0x14, 0xF10,  0xDC4,  0xDF0,  0xDF4,  0xDD4,  0x19, 0xE78,  0xDC8,  0x19E110u, 0 },
    { 4, 0x2E3C, 150, 0x44, 0x1CC4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B9C, 0x19, 0x1C40, 0x1B90, 0x10E568u, 0 },
    { 5, 0x2F44, 150, 0x48, 0x1CD4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B9C, 0x19, 0x1C40, 0x1B90, 0x154148u, 0 },
};

/* The graves, as cod_vv12.inc and cod_vv345.inc read them. */
struct grave_layout {
    unsigned int owner;      /* VV1/VV2: the owner pointer's offset in the table */
    unsigned int graves;     /* VV1/VV2: the graves' offset in the owner */
    unsigned int stride, name_cap, age, job, value, cause, epitaph;
};
static const struct grave_layout GRAVES[5] = {
    { 0x3E010u, 0xA31Cu, 0x2C, 0x1C, 0x24, 0x20, 0x1C, 0, 0 },
    { 0xE574D4u, 0x2EB0Cu, 0x7C, 0x18, 0x74, 0x70, 0x6C, 0, 0x19 },
    { 0, 0, 0x30, 0x19, 0x1C, 0x20, 0x24, 0x2C, 0 },
    { 0, 0, 0x5C, 0x19, 0x1C, 0x28, 0x2C, 0x34, 0x38 },
    { 0, 0, 0x5C, 0x19, 0x1C, 0x28, 0x2C, 0x34, 0x38 },
};

static const struct layout *g;
static const struct grave_layout *gl;
static int game;
static unsigned char *table;          /* what the DLLs read: the container */
static unsigned char *owner;          /* VV1/VV2 graves' owner */
static unsigned char *roster;         /* VV3-VV5 entries */
static unsigned char *stones;         /* VV3 gravestones */
static void *pointer_page;

static unsigned char *rec(int i) { return table + g->base + (size_t)i * g->stride; }

static unsigned int table_bytes(void) {
    unsigned int size = g->base + g->slots * g->stride;
    if (gl->owner + 4 > size) size = gl->owner + 4;
    return size;
}

static int alloc_game(void) {
    unsigned char *at = (unsigned char *)((uintptr_t)GetModuleHandleW(NULL) + g->rva);
    if (g->is_pointer) {
        pointer_page = VirtualAlloc((void *)((uintptr_t)at & ~0xFFFu), 0x1000, MEM_RESERVE | MEM_COMMIT,
                                    PAGE_READWRITE);
        table = (unsigned char *)VirtualAlloc(NULL, table_bytes(), MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        if (table == NULL || pointer_page == NULL) return 0;
        *(unsigned char **)at = table;
        owner = (unsigned char *)VirtualAlloc(NULL, gl->graves + 50 * gl->stride, MEM_RESERVE | MEM_COMMIT,
                                              PAGE_READWRITE);
        if (owner == NULL) return 0;
        *(unsigned char **)(table + gl->owner) = owner;
    } else {
        if (VirtualAlloc((void *)((uintptr_t)at & ~0xFFFFu), table_bytes() + ((uintptr_t)at & 0xFFFFu),
                         MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) == NULL) {
            return 0;
        }
        table = at;
        roster = (unsigned char *)VirtualAlloc(NULL, 500 * gl->stride, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        stones = (unsigned char *)VirtualAlloc(NULL, 50 * 0x2C, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        if (roster == NULL || stones == NULL) return 0;
    }
    return 1;
}

static void free_game(void) {
    if (g->is_pointer) {
        VirtualFree(table, 0, MEM_RELEASE);
        VirtualFree(owner, 0, MEM_RELEASE);
        VirtualFree(pointer_page, 0, MEM_RELEASE);
    } else {
        VirtualFree((void *)((uintptr_t)table & ~0xFFFFu), 0, MEM_RELEASE);
        VirtualFree(roster, 0, MEM_RELEASE);
        VirtualFree(stones, 0, MEM_RELEASE);
    }
    table = owner = roster = stones = NULL;
}

static void villager(int i, const char *name, int age, int head, int body) {
    memset(rec(i), 0, g->stride);
    rec(i)[g->active] = 1;
    *(int *)(rec(i) + g->health) = 90;
    *(int *)(rec(i) + g->age) = age;
    *(int *)(rec(i) + g->head) = head;
    *(int *)(rec(i) + g->body) = body;
    *(int *)(rec(i) + g->sex) = 1;
    strncpy((char *)rec(i) + g->name, name, g->name_cap - 1);
}

static unsigned char *grave_at(int k) {
    return game <= 2 ? owner + gl->graves + (size_t)k * gl->stride : roster + (size_t)k * gl->stride;
}

/* job 3 (VV1 Scientist, VV2 Doctor, VV3-5 Scientist), value 95: "Master ...". */
static void dig(int k, const char *name, int age, int job, int value, int cause, const char *epitaph) {
    unsigned char *grave = grave_at(k);
    memset(grave, 0, gl->stride);
    strncpy((char *)grave, name, gl->name_cap - 1);
    *(int *)(grave + gl->age) = age;
    *(int *)(grave + gl->job) = job;
    *(int *)(grave + gl->value) = value;
    if (game >= 3) {
        *(int *)(grave + gl->cause) = cause;
    }
    if (epitaph != NULL) {
        if (game == 2 || game >= 4) {
            strncpy((char *)grave + gl->epitaph, epitaph, 31);
        } else if (game == 3 && k < 50) {
            memset(stones + k * 0x2C, 0, 0x2C);
            strncpy((char *)stones + k * 0x2C + 8, epitaph, 31);
        }
    }
}

/* The skill lines the DLL prints for job / value 95 and job / value 0. */
static const char *const MASTER[6][7] = {
    { 0 },
    { NULL, "Master Farmer", "Master Parent", "Master Scientist", "Master Builder", "Master Doctor" },
    { NULL, "Master Farmer", "Master Parent", "Master Doctor", "Master Scientist", "Master Builder" },
    { "Master Farmer", "Master Parent", "Master Doctor", "Master Scientist", "Master Builder" },
    { "Master Farmer", "Master Parent", "Master Doctor", "Master Scientist", "Master Builder" },
    { "Master Farmer", "Master Parent", "Master Doctor", "Master Scientist", "Master Builder" },
};

static unsigned int fnv(const char *name, unsigned int capacity, int age) {
    unsigned int h = 2166136261u, i;
    for (i = 0; i < capacity && name[i] != 0; ++i) h = (h ^ (unsigned char)name[i]) * 16777619u;
    h = (h ^ 0xFFu) * 16777619u;
    for (i = 0; i < 4; ++i) h = (h ^ ((unsigned int)age >> (8 * i) & 0xFFu)) * 16777619u;
    return h != 0 ? h : 1u;
}

/* ---- Paths ------------------------------------------------------------------ */

static char root[MAX_PATH];          /* Documents\LDW\<exe> */
static char exe_dir[MAX_PATH];
/* "<exe_dir>\Virtual Villagers Fun Patcher Files": where the companions are,
   as in a patched game (native/shared/patcher_files.h). */
static char files_dir[MAX_PATH];

static int locate(void) {
    char docs[MAX_PATH], exe[MAX_PATH], *base, *dot;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) return 0;
    if (GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) return 0;
    base = strrchr(exe, '\\');
    if (base == NULL) return 0;
    lstrcpynA(exe_dir, exe, (int)(base - exe) + 1);
    _snprintf(files_dir, MAX_PATH, "%s\\" VVFP_PATCHER_FILES_FOLDER, exe_dir);
    files_dir[MAX_PATH - 1] = 0;
    ++base;
    dot = strrchr(base, '.');
    if (dot) *dot = 0;
    _snprintf(root, MAX_PATH, "%s\\LDW\\%s", docs, base);
    root[MAX_PATH - 1] = 0;
    return 1;
}

static void make_dirs(const char *path) {
    char buf[MAX_PATH];
    char *p;
    lstrcpynA(buf, path, MAX_PATH);
    for (p = buf + 3; *p; ++p) {
        if (*p == '\\') { *p = 0; CreateDirectoryA(buf, NULL); *p = '\\'; }
    }
    CreateDirectoryA(buf, NULL);
}

static void remove_tree(const char *dir) {
    char pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA f;
    HANDLE h;
    _snprintf(pattern, MAX_PATH, "%s\\*", dir);
    h = FindFirstFileA(pattern, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (strcmp(f.cFileName, ".") == 0 || strcmp(f.cFileName, "..") == 0) continue;
            _snprintf(path, MAX_PATH, "%s\\%s", dir, f.cFileName);
            if (f.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) continue;
            if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) { remove_tree(path); RemoveDirectoryA(path); }
            else DeleteFileA(path);
        } while (FindNextFileA(h, &f));
        FindClose(h);
    }
}

static void write_text(const char *path, const char *text) {
    char dir[MAX_PATH], *slash;
    FILE *f;
    lstrcpynA(dir, path, MAX_PATH);
    slash = strrchr(dir, '\\');
    if (slash) { *slash = 0; make_dirs(dir); }
    f = fopen(path, "w");                 /* text mode: CRLF, as the DLLs write */
    if (f) { fwrite(text, 1, strlen(text), f); fclose(f); }
}

static char text[1 << 17];
static long read_into(const char *path) {
    FILE *f = fopen(path, "rb");
    long n;
    if (f == NULL) { text[0] = 0; return -1; }
    n = (long)fread(text, 1, sizeof text - 1, f);
    text[n] = 0;
    fclose(f);
    return n;
}

static void deaths_path(int number, char *out) {
    _snprintf(out, MAX_PATH, "%s\\Virtual Villagers Fun Patcher Logs\\Deaths\\Virtual Villagers %d Deaths Log %d.txt",
              root, game, number);
}

static void logged_path(char *out) {
    _snprintf(out, MAX_PATH, "%s\\Virtual Villagers Fun Patcher Data\\Deaths\\Virtual Villagers %d Graves Logged - Save 1.dat",
              root, game);
}

static int count_of(const char *haystack, const char *needle) {
    int n = 0;
    const char *at = haystack;
    while ((at = strstr(at, needle)) != NULL) { ++n; at += strlen(needle); }
    return n;
}

/* The record whose "  Name: <name>" follows "Death <number>". */
static const char *death(int number, const char *name) {
    char want[160];
    _snprintf(want, sizeof want, "Death %d\r\n  Name: %s\r\n", number, name);
    return strstr(text, want);
}

/* ---- The DLLs ------------------------------------------------------------- */

static HMODULE parentage, cause;
static record_t write_record;
static ensure_village_t ensure_village;
static setup_t setup;
static save_done_t save_done;
static tick_t tick;
static reset_t reset;
static roster_t set_roster;
static scan_t scan_graves;
static repair_t repair_graves;
static buried_t test_buried;           /* A New Home / The Lost Children: the burial hook's own path */
static int *stats;

static int __stdcall host_slot(void) { return 1; }
static struct { int size; int (__stdcall *slot)(void); } host = { 8, host_slot };

static void load(void) {
    /* By full path in the patcher's folder, as the companions load each other. */
    parentage = vvfp_load_patcher_dll("VVFP Parentage Export.dll");
    cause = vvfp_load_patcher_dll("VVFP Cause of Death.dll");
    if (parentage == NULL || cause == NULL) { printf("cannot load the DLLs\n"); exit(2); }
    write_record = (record_t)GetProcAddress(parentage, "WriteVillageRecord");
    ensure_village = (ensure_village_t)GetProcAddress(parentage, "EnsureParentageLogForVillage");
    setup = (setup_t)GetProcAddress(cause, "VvfpCauseTestSetup");
    save_done = (save_done_t)GetProcAddress(cause, "VvfpCauseTestSaveDone");
    tick = (tick_t)GetProcAddress(cause, "VvfpCauseTick");
    reset = (reset_t)GetProcAddress(cause, "VvfpCauseVillageReset");
    set_roster = (roster_t)GetProcAddress(cause, "VvfpCauseTestRoster");
    stats = (int *)GetProcAddress(cause, "VvfpCauseStats");
    scan_graves = (scan_t)GetProcAddress(cause, "VvfpCauseScanGraves");
    repair_graves = (repair_t)GetProcAddress(cause, "VvfpCauseRepairGraves");
    test_buried = (buried_t)GetProcAddress(cause, "VvfpCauseTestBuried");
    if (!write_record || !ensure_village || !setup || !save_done || !tick || !reset || !set_roster || !stats
        || !scan_graves || !repair_graves
        || GetProcAddress(parentage, "RecordGravesMissingFromLog") == NULL) {
        printf("missing exports\n");
        exit(2);
    }
    setup(game, &host, table);
    set_roster(roster, stones);
    tick(game);                       /* binds A New Home's graves file to the slot */
}

/* A new game session: both DLLs gone from the process, their state with
   them.  Cause of Death loads the parentage DLL itself as well, so it is
   freed until it is really unloaded. */
static void unload(void) {
    int guard;
    FreeLibrary(cause);
    for (guard = 0; guard < 8 && GetModuleHandleA("VVFP Parentage Export.dll") != NULL; ++guard) {
        FreeLibrary(GetModuleHandleA("VVFP Parentage Export.dll"));
    }
    cause = parentage = NULL;
}

static unsigned char *save_buffer(const char *name) {
    unsigned int at = vv_village_name_offset(game);
    unsigned char *buffer = (unsigned char *)calloc(1, at + VV_VILLAGE_NAME_MAX + 16);
    strcpy((char *)buffer + at, name);
    return buffer;
}

static void stand_in(const char *name, int present) {
    char path[MAX_PATH];
    _snprintf(path, MAX_PATH, "%s\\%s", files_dir, name);
    if (present) {
        HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
        if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
    } else {
        DeleteFileA(path);
    }
}

#define VILLAGE "Village: Backfill Tribe (Save 1)\n"

/* The Village History log as the population exporter writes it. */
static void write_history(void) {
    char path[MAX_PATH];
    static char h[8192];
    char t[32], other[32];
    /* The population exporter's heading names the game; another game's
       snapshot of a village with the same name and slot (renamed games can
       share a save folder) is not this village's. */
    _snprintf(t, sizeof t, "Virtual Villagers %d", game);
    _snprintf(other, sizeof other, "Virtual Villagers %d", game % 5 + 1);
    _snprintf(path, MAX_PATH, "%s\\Virtual Villagers Fun Patcher Logs\\Tribe History\\Village History 1.txt", root);
    _snprintf(h, sizeof h,
        "=== %s -- 2026-09-26 14:30:48 ===\nVillage: Backfill Tribe (Save 1)\n\n"
        "Villager 1\n  Name: Kito\n  Age: 502\n  Head: 0\n  Body: 18\n  Likes: exploring\n  Dislikes: resting\n"
        "  Skills:\n    Breeding   0\n\n"
        "Villager 2\n  Name: Chika\n  Age: 520\n  Head: 19\n  Body: 17\n  Likes: playing\n  Skills:\n    Breeding   0\n\n"
        "Villager 3\n  Name: Ghali\n  Age: 447\n  Head: 6\n  Body: 1\n  Likes: caves\n\n"
        "Villager 4\n  Name: Lonely\n  Age: 500\n  Head: 9\n  Body: 9\n\n"
        "Villager 5\n  Name: Youth\n  Age: 900\n  Head: 7\n  Body: 7\n  Likes: rain\n\n\n"
        "=== %s -- 2026-10-01 16:21:22 ===\nVillage: Backfill Tribe (Save 1)\n\n"
        "Villager 1\n  Name: Kito\n  Age: 1276\n  Head: 0\n  Body: 18\n  Likes: exploring\n  Dislikes: resting\n"
        "  Parents:\n    Father: Ghali\n      Head: 77\n      Body: 77\n  Skills:\n    Research   100\n\n"
        "Villager 2\n  Name: Chika\n  Age: 1294\n  Head: 19\n  Body: 17\n  Likes: playing\n  Skills:\n    Healing    100\n\n"
        "Villager 3\n  Name: Dup\n  Age: 850\n  Head: 4\n  Body: 4\n\n"
        "Villager 4\n  Name: Lonely\n  Age: 700\n  Head: 9\n  Body: 9\n\n"
        "Villager 5\n  Name: Youth\n  Age: 300\n  Head: 7\n  Body: 7\n  Likes: stars\n\n\n"
        "=== %s -- 2026-10-01 18:00:00 ===\nVillage: Other Tribe (Save 2)\n\n"
        "Villager 1\n  Name: Chika\n  Age: 1300\n  Head: 1\n  Body: 1\n  Likes: ants\n\n\n"
        "=== %s -- 2026-10-02 09:00:00 ===\nVillage: Backfill Tribe (Save 1)\n\n"
        "Villager 1\n  Name: Kito\n  Age: 1300\n  Head: 5\n  Body: 5\n  Likes: drums\n\n"
        "Villager 2\n  Name: Ana\n  Age: 600\n  Head: 3\n  Body: 3\n\n"
        "Villager 3\n  Name: Bolo\n  Age: 690\n  Head: 8\n  Body: 8\n\n\n"
        "=== %s -- 2026-10-02 10:00:00 ===\nVillage: Backfill Tribe (Save 1)\n\n"
        "Villager 1\n  Name: Chika\n  Age: 1310\n  Head: 1\n  Body: 1\n  Likes: ants\n\n\n"
        /* A snapshot cut short by an interrupted append: Chika's record has
           no likes and never ends. */
        "=== %s -- 2026-10-03 11:00:00 ===\nVillage: Backfill Tribe (Save 1)\n\n"
        "Villager 1\n  Name: Chika\n  Age: 1320\n  Head: 19\n  Body: 17\n"
        /* The Rename Tribe tool's note (village_rename.h), appended to the
           newest file: the village was "Oldname Tribe" before. */
        "Tribe renamed from Oldname Tribe to Backfill Tribe on 2026-09-21 (Save 1)\n",
        t, t, t, t, other, t);
    write_text(path, h);
    /* An older build's unnumbered history, not yet moved to file 1 (the
       population exporter moves it at a save, possibly after this backfill),
       holding the village under its old name: Renny's only snapshot. */
    _snprintf(path, MAX_PATH, "%s\\Virtual Villagers Fun Patcher Logs\\Tribe History\\Village History.txt", root);
    _snprintf(h, sizeof h,
        "=== %s -- 2026-09-20 10:00:00 ===\nVillage: Oldname Tribe (Save 1)\n\n"
        "Villager 1\n  Name: Renny\n  Age: 700\n  Head: 6\n  Body: 6\n  Likes: honey\n\n\n", t);
    write_text(path, h);
}

/* The log an older build wrote: Ghali, Onawa, one Dup, a "no grave" Lonely;
   and another village's file with a Kito. */
static void write_old_logs(void) {
    char path[MAX_PATH];
    static char d[4096];
    _snprintf(d, sizeof d,
        "Village: Backfill Tribe (Save 1)\n"
        "Death 1\n  Name: Ghali\n  Age at death: 1434\n  Cause of death: Old age\n  Grave: %s\n"
        "  Epitaph: Inspired Architect\n  Head: 6\n  Body: 1\n  Likes: caves\n  Dislikes: (none)\n\n"
        "Death 2\n  Name: Onawa\n  Age at death: 1379\n  Cause of death: Old age\n  Grave: %s\n"
        "  Epitaph: Child of the Earth\n  Head: 16\n  Body: 2\n  Likes: (none)\n  Dislikes: (none)\n\n"
        "Disappeared\n  Name: Gone\n\n"
        "Death 3\n  Name: Dup\n  Age at death: 900\n  Cause of death: Disease\n  Grave: Untrained\n"
        "  Epitaph: (none)\n  Head: 4\n  Body: 4\n  Likes: (none)\n  Dislikes: (none)\n\n"
        "Death 4\n  Name: Lonely\n  Age at death: 600\n  Cause of death: Unknown causes\n"
        "  Grave: no grave (never buried: the game removed the body)\n  Epitaph: (none)\n"
        "  Head: 1\n  Body: 1\n  Likes: (none)\n  Dislikes: (none)\n\n"
        "Death 5\n  Name: Tupa\n  Age at death: 1222\n  Cause of death: Old age\n  Grave: Master Scientist\n"
        "  Epitaph: Dedicated Student\n  Head: 0\n  Body: 18\n  Likes: exploring\n  Dislikes: resting\n"
        "  Recorded: afterwards (died before this log existed); from the grave and the last Village History"
        " snapshot, 2026-10-01 16:21:22\n\n",
        MASTER[game][4], MASTER[game][game >= 3 ? 0 : 1]);
    deaths_path(1, path);
    write_text(path, d);
    _snprintf(d, sizeof d,
        "Village: Other Tribe (Save 2)\n"
        "Death 5\n  Name: Kito\n  Age at death: 1410\n  Cause of death: Old age\n  Grave: %s\n"
        "  Epitaph: (none)\n  Head: 0\n  Body: 18\n  Likes: (none)\n  Dislikes: (none)\n\n",
        MASTER[game][3]);
    deaths_path(2, path);
    write_text(path, d);
    /* A file of this village whose only record was cut short by an
       interrupted append: Chika's name and age at death, no grave line, no
       ending blank line.  It is no grave's record (Codex, #524).  Removed
       after the first Repair save (a fourth file would move the new log
       the Deaths-log-deleted case expects to be file 3). */
    deaths_path(4, path);
    write_text(path, "Village: Backfill Tribe (Save 1)\n"
                     "Death 99\n  Name: Chika\n  Age at death: 1428\n  Cause of death: Old age\n");
}

/* A New Home's and The Lost Children's graves file: Kito's cause (and in A
   New Home his epitaph, Inspired Inventor), as the burial would have kept it. */
static void write_graves_file(void) {
    char path[MAX_PATH];
    unsigned char b[16 + 44];
    FILE *f;
    if (game > 2) return;
    memset(b, 0, sizeof b);
    *(unsigned int *)b = 0x31444356u;
    *(unsigned int *)(b + 4) = 1;
    *(unsigned int *)(b + 8) = (unsigned int)game;
    *(unsigned int *)(b + 12) = 1;
    /* kind 0 (grave), index 0 */
    *(unsigned int *)(b + 16 + 4) = fnv("Kito", gl->name_cap, 1410);
    b[16 + 8] = 2;                                /* Old age */
    b[16 + 9] = game == 1 ? 9 : 0;                /* Inspired Inventor */
    _snprintf(path, MAX_PATH, "%s\\Virtual Villagers Fun Patcher Data", root);
    make_dirs(path);
    _snprintf(path, MAX_PATH, "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers %d Graves - Save 1.dat",
              root, game);
    f = fopen(path, "wb");
    if (f) { fwrite(b, 1, sizeof b, f); fclose(f); }
}

/* The slot's own save, as the game writes it: what the scan at load names
   the village from (through "VVFP Save Reset.dll", SavedVillageHeader). */
static void write_save_file(void) {
    static const DWORD HEADER[5] = { 12u, 12u, 12u, 24u, 24u };
    static const DWORD LENGTH_AT[5] = { 8u, 8u, 8u, 16u, 16u };
    static const DWORD BUFFER[5] = { 0x0ABDCu, 0x30370u, 0x12F1Cu, 0x1710Cu, 0x17D78u };
    char path[MAX_PATH];
    DWORD total = HEADER[game - 1] + BUFFER[game - 1];
    unsigned char *data = (unsigned char *)calloc(1, total);
    FILE *f;
    if (data == NULL) return;
    memcpy(data, "ldwg", 4);
    memcpy(data + LENGTH_AT[game - 1], &BUFFER[game - 1], 4);
    strcpy((char *)data + HEADER[game - 1] + vv_village_name_offset(game), "Backfill Tribe");
    data[HEADER[game - 1] + vv_village_name_offset(game) + 40] = 0x7F;
    _snprintf(path, MAX_PATH, "%s\\Virtual Villagers1.ldw", root);
    make_dirs(root);
    f = fopen(path, "wb");
    if (f) { fwrite(data, 1, total, f); fclose(f); }
    free(data);
}

static const char *ROOT_SUBS[2] = { "Virtual Villagers Fun Patcher Logs", "Virtual Villagers Fun Patcher Data" };

static void clean(void) {
    char sub[MAX_PATH];
    int k;
    for (k = 0; k < 2; ++k) {
        _snprintf(sub, MAX_PATH, "%s\\%s", root, ROOT_SUBS[k]);
        remove_tree(sub);
        RemoveDirectoryA(sub);
    }
}

int main(int argc, char **argv) {
    harness_ldw_tree_begin();   /* first: leaves Documents\LDW as it found it */
    char path[MAX_PATH], logged[MAX_PATH];
    char first[1 << 15];
    char line[512];
    unsigned char *buffer;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc < 4) {
        printf("usage: grave_backfill_harness <parentage dll> <cause of death test dll> <save reset dll>\n");
        return 2;
    }
    if (!locate()) return 2;
    CreateDirectoryA(files_dir, NULL);
    _snprintf(path, MAX_PATH, "%s\\VVFP Parentage Export.dll", files_dir);
    if (!CopyFileA(argv[1], path, FALSE)) { printf("cannot copy %s\n", argv[1]); return 2; }
    _snprintf(path, MAX_PATH, "%s\\VVFP Cause of Death.dll", files_dir);
    if (!CopyFileA(argv[2], path, FALSE)) { printf("cannot copy %s\n", argv[2]); return 2; }
    _snprintf(path, MAX_PATH, "%s\\VVFP Save Reset.dll", files_dir);
    if (!CopyFileA(argv[3], path, FALSE)) { printf("cannot copy %s\n", argv[3]); return 2; }
    stand_in("VVFP Statistics Export.dll", 0);

    for (game = 1; game <= 5; ++game) {
        int cause_value = 2;                       /* Old age */
        g = &LAYOUTS[game - 1];
        gl = &GRAVES[game - 1];
        printf("Virtual Villagers %d\n", game);
        clean();
        if (!alloc_game()) { printf("cannot place the tables\n"); return 2; }
        villager(0, "Ana", 600, 3, 3);
        villager(1, "Kito", 1300, 5, 5);          /* a living namesake, listed older than Kito was */
        villager(2, "Bolo", 700, 8, 8);
        dig(0, "Kito", 1410, game >= 3 ? 3 : 3, 95, cause_value, "Inspired Inventor");
        dig(1, "Chika", 1428, game >= 3 ? 2 : 5, 95, cause_value, "Guardian of Health");
        dig(2, "Ghali", 1434, game >= 3 ? 4 : 4, 95, cause_value, "Inspired Architect");
        dig(3, "Onawa", 1379, game >= 3 ? 0 : 1, 95, cause_value, "Child of the Earth");
        dig(4, "Dup", 900, game >= 3 ? -1 : 0, 0, 0, NULL);
        dig(5, "Dup", 900, game >= 3 ? -1 : 0, 0, 0, NULL);
        dig(6, "Lonely", 600, game >= 3 ? -1 : 0, 0, -1, NULL);
        dig(20, "Tupa", 1222, 3, 60, cause_value, "Dedicated Student");
        dig(21, "Youth", 800, game >= 3 ? -1 : 0, 0, cause_value, NULL);   /* made young again once */
        dig(22, "Renny", 720, game >= 3 ? -1 : 0, 0, cause_value, NULL);   /* listed only before a rename */
        write_history();
        write_old_logs();
        write_graves_file();
        write_save_file();
        vv_village_publish("");
        load();
        buffer = save_buffer("Backfill Tribe");

        /* 0: the scan, and no answer or "Not now". */
        {
            char before_log[1 << 13];
            char graves_file[MAX_PATH];
            long graves_before;
            deaths_path(1, path);
            read_into(path);
            lstrcpynA(before_log, text, sizeof before_log);
            _snprintf(graves_file, MAX_PATH,
                      "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers %d Graves - Save 1.dat", root, game);
            graves_before = read_into(graves_file);
            logged_path(logged);
            CHECK(scan_graves(game, 1) == 6, "the scan counts the six graves the log lacks");
            CHECK(scan_graves(game, 2) == -1, "...and none for a slot with no save");
            read_into(path);
            CHECK(strcmp(before_log, text) == 0 && GetFileAttributesA(logged) == INVALID_FILE_ATTRIBUTES
                  && read_into(graves_file) == graves_before,
                  "...writing nothing: no log line, no graves file, the graves file untouched");
            save_done(1, buffer);
            read_into(path);
            CHECK(strstr(text, "Kito") == NULL && GetFileAttributesA(logged) == INVALID_FILE_ATTRIBUTES,
                  "with no answer the save records nothing");
            repair_graves(game, 1, 0);
            save_done(1, buffer);
            read_into(path);
            CHECK(strstr(text, "Kito") == NULL && GetFileAttributesA(logged) == INVALID_FILE_ATTRIBUTES,
                  "\"Not now\": the save records nothing");
        }

        /* 1, 2: Repair, and the save -- first with a Village History file
           that cannot be read (locked): nothing is decided from part of the
           history (Codex, #524), and the graves wait for the next save. */
        repair_graves(game, 1, 1);
        {
            char locked_path[MAX_PATH];
            HANDLE locked;
            _snprintf(locked_path, MAX_PATH,
                      "%s\\Virtual Villagers Fun Patcher Logs\\Tribe History\\Village History 2.txt", root);
            write_text(locked_path, "=== Virtual Villagers 9 -- 2026-10-03 00:00:00 ===\n");
            locked = CreateFileA(locked_path, GENERIC_READ, 0, NULL, OPEN_EXISTING, 0, NULL);
            save_done(1, buffer);
            deaths_path(1, path);
            read_into(path);
            CHECK(locked != INVALID_HANDLE_VALUE && strstr(text, "Kito") == NULL
                  && GetFileAttributesA(logged) == INVALID_FILE_ATTRIBUTES,
                  "with a History file that cannot be read, the save decides nothing");
            if (locked != INVALID_HANDLE_VALUE) CloseHandle(locked);
            DeleteFileA(locked_path);
        }
        save_done(1, buffer);
        deaths_path(1, path);
        read_into(path);
        CHECK(count_of(text, "\r\n  Name: Ghali\r\n") == 1 && count_of(text, "\r\n  Name: Onawa\r\n") == 1,
              "Ghali and Onawa are not recorded again");
        CHECK(death(6, "Kito") && death(7, "Chika") && death(8, "Dup") && death(9, "Lonely")
              && death(10, "Youth") && death(11, "Renny") && !strstr(text, "Death 12"),
              "Kito, Chika, the second Dup, Lonely, Youth and Renny are recorded, in burial order");
        {
            const char *r = death(11, "Renny");
            CHECK(r != NULL && strstr(r, "  Head: 6\r\n  Body: 6\r\n  Likes: honey\r\n  Dislikes: (none)\r\n") != NULL
                  && strstr(r, "2026-09-20 10:00:00 (age 700 then)") != NULL,
                  "a villager listed only before a rename, in the unnumbered older history, is identified");
        }
        {
            const char *y = death(10, "Youth");
            CHECK(y != NULL && strstr(y, "  Head: 7\r\n  Body: 7\r\n  Likes: stars\r\n") != NULL
                  && strstr(y, "(age 300 then)") != NULL,
                  "a villager made young again is still found: listed older once, then younger");
        }
        CHECK(count_of(text, "\r\n  Name: Tupa\r\n") == 1,
              "the record appended by hand in the owner's shape counts for Tupa's grave (name, age at death)");
        CHECK(count_of(text, "\r\n  Name: Dup\r\n") == 2, "two Dup graves, two Dup records");
        {
            const char *k = death(6, "Kito");
            const char *c = death(7, "Chika");
            const char *l = death(9, "Lonely");
            char want[1024];
            _snprintf(want, sizeof want,
                "Death 6\r\n  Name: Kito\r\n  Age at death: 1410\r\n  Cause of death: Old age\r\n"
                "  Grave: %s\r\n  Epitaph: %s\r\n  Head: 0\r\n  Body: 18\r\n  Likes: exploring\r\n"
                "  Dislikes: resting\r\n  Recorded from the grave: this death was not seen when it happened"
                " (it came before\r\n    this log was kept, or while the game was catching up on time away)\r\n"
                "  Head, body, likes and dislikes: from the Village History snapshot of 2026-10-01 16:21:22"
                " (age 1276 then)\r\n\r\n",
                MASTER[game][3], "Inspired Inventor");
            CHECK(k != NULL && strncmp(k, want, strlen(want)) == 0,
                  "Kito's record: the grave, his last snapshot's looks (not the living namesake's), the note");
            if (k != NULL && strncmp(k, want, strlen(want)) != 0) {
                printf("--- got:\n%.700s\n--- want:\n%s\n", k, want);
            }
            CHECK(c != NULL && strstr(c, "  Head: 19\r\n  Body: 17\r\n  Likes: playing\r\n  Dislikes: (none)\r\n") != NULL
                  && strstr(c, "16:21:22 (age 1294 then)") != NULL
                  && strstr(c, "  Cause of death: ") != NULL,
                  "Chika's looks are hers: not the other village's, nor another game's, nor a record cut short;"
                  " and a Death record cut short is not her grave's");
            if (game <= 2) {
                CHECK(c != NULL && strstr(c, "  Cause of death: (not recorded:") != NULL,
                      "a grave the graves file has no cause for says so");
            } else {
                CHECK(c != NULL && strstr(c, "  Cause of death: Old age\r\n") != NULL,
                      "the later games' cause is the entry's own");
            }
            CHECK(l != NULL && strstr(l, "  Head: (unknown)\r\n  Body: (unknown)\r\n  Likes: (unknown)\r\n"
                                         "  Dislikes: (unknown)\r\n") != NULL
                  && strstr(l, "does not list this villager") != NULL,
                  "Lonely's looks are unknown, never guessed");
            if (game == 1) {
                /* A New Home keeps none: the one its popup shows, by the rule
                   for a Doctor's grave, kept from now on. */
                CHECK(c != NULL && (strstr(c, "  Epitaph: Guardian of Health\r\n") != NULL
                                    || strstr(c, "  Epitaph: Dedicated to Others\r\n") != NULL),
                      "the epitaph is the one the grave's popup shows");
            } else {
                CHECK(c != NULL && strstr(c, "  Epitaph: Guardian of Health\r\n") != NULL,
                      "the epitaph is the grave's");
            }
        }
        CHECK(read_into(logged) == 16 + 10 * 8, "the graves file covers all ten graves");
        CHECK(scan_graves(game, 1) == 0, "the scan now finds nothing missing");
        read_into(path);
        lstrcpynA(first, text, sizeof first);
        deaths_path(4, path);
        DeleteFileA(path);                         /* the cut-short record's file (write_old_logs) */
        deaths_path(2, path);
        read_into(path);
        CHECK(count_of(text, "Death ") == 1, "the other village's log is untouched");

        /* 3: again, and in a new session. */
        save_done(1, buffer);
        deaths_path(1, path);
        read_into(path);
        CHECK(strcmp(first, text) == 0, "a second save writes nothing");
        unload();
        load();
        CHECK(scan_graves(game, 1) == 0, "a new session's scan finds nothing missing");
        repair_graves(game, 1, 1);
        save_done(1, buffer);
        read_into(path);
        CHECK(strcmp(first, text) == 0, "a new session's save writes nothing");
        DeleteFileA(path);
        save_done(1, buffer);
        {
            /* The village's new log is file 3, after the other village's. */
            char third[MAX_PATH];
            deaths_path(3, third);
            CHECK(read_into(third) > 0 && strstr(text, "Death") == NULL
                  && read_into(path) < 0,
                  "with the Deaths log deleted, the graves file still says every grave is covered");
            DeleteFileA(third);
        }
        /* The save replaced outside the game by another village whose grave
           0 differs (Codex, #524): the graves file is no longer this
           village's, so none of its coverage is trusted -- with no log on
           disk, every grave (all ten) is missing, not only grave 0. */
        strncpy((char *)grave_at(0), "Zito", gl->name_cap - 1);
        {
            int missing = scan_graves(game, 1);
            CHECK(missing == 10, "a replaced save trusts none of the graves file's coverage");
            if (missing != 10) printf("       (scan said %d)\n", missing);
        }
        strncpy((char *)grave_at(0), "Kito", gl->name_cap - 1);
        {
            FILE *f = fopen(path, "wb");          /* put the log back as it was */
            if (f) { fwrite(first, 1, strlen(first), f); fclose(f); }
        }

        /* 4: a grave whose record the burial already wrote; one still held. */
        villager(3, "Newman", 800, 2, 2);
        CHECK(write_record(game, 2, rec(3), 1,
                           "  Age at death: 800\n  Cause of death: Disease\n  Grave: Untrained\n  Epitaph: (none)\n",
                           NULL, 1) == 1, "the burial's own record is written");
        rec(3)[g->active] = 0;
        dig(7, "Newman", 800, game >= 3 ? -1 : 0, 0, 0, NULL);
        save_done(1, buffer);
        read_into(path);
        CHECK(count_of(text, "\r\n  Name: Newman\r\n") == 1, "...and the grave is not recorded again");

        stand_in("VVFP Statistics Export.dll", 1);  /* the statistics companion publishes at its save */
        unload();
        vv_village_publish("");
        load();
        repair_graves(game, 1, 1);
        villager(4, "Heldo", 810, 2, 2);
        CHECK(write_record(game, 2, rec(4), 1,
                           "  Age at death: 810\n  Cause of death: Disease\n  Grave: Untrained\n  Epitaph: (none)\n",
                           NULL, 1) == 1, "a burial's record before the village is known is accepted");
        rec(4)[g->active] = 0;
        dig(8, "Heldo", 810, game >= 3 ? -1 : 0, 0, 0, NULL);
        save_done(1, buffer);
        save_done(1, buffer);
        read_into(path);
        CHECK(strstr(text, "Heldo") == NULL, "...it is held, and two saves record nothing for its grave");
        ensure_village(game, VILLAGE, table);       /* the statistics companion's publish */
        read_into(path);
        CHECK(count_of(text, "\r\n  Name: Heldo\r\n") == 1, "...then it is written, once");
        /* A grave recorded from at a save whose record is only held (the
           statistics companion has not named the village yet), and the game
           ends before it is written: the grave is not taken as covered. */
        dig(10, "Qued", 820, game >= 3 ? -1 : 0, 0, 0, NULL);
        if (game <= 2) {
            /* ...and a burial the hook records while its record can only be
               held (Codex, #524): the grave is not taken on trust either. */
            villager(6, "Lostie", 830, 2, 2);
            *(int *)(rec(6) + g->health) = 0;
            dig(12, "Lostie", 830, 0, 0, 0, NULL);
            test_buried(6, 12);
            rec(6)[g->active] = 0;
        }
        save_done(1, buffer);
        read_into(path);
        CHECK(strstr(text, "Qued") == NULL, "a record from the grave before the village is named is held");
        stand_in("VVFP Statistics Export.dll", 0);
        unload();                                   /* ...and lost with the session */
        vv_village_publish("");
        load();
        CHECK(scan_graves(game, 1) == (game <= 2 ? 2 : 1),
              "...so the next session's scan finds that grave (and a held burial's) missing again");
        repair_graves(game, 1, 1);

        /* 5: the load-time catch-up buried Bolo, whom the last save held. */
        villager(5, "Rua", 650, 0, 0);             /* head 0, body 0; never in the Village History log; her
                                                       unreported arrival is one record */
        save_done(1, buffer);                       /* the roster: Ana, Kito, Bolo, Rua */
        read_into(path);
        CHECK(count_of(text, "\r\n  Name: Qued\r\n") == 1
              && count_of(text, "\r\n  Name: Lostie\r\n") == (game <= 2 ? 1 : 0),
              "...and that save records it, once");
        rec(2)[g->active] = 0;                      /* gone with no report */
        rec(5)[g->active] = 0;
        dig(9, "Bolo", 705, game >= 3 ? -1 : 0, 0, -1, NULL);
        dig(11, "Rua", 660, game >= 3 ? -1 : 0, 0, -1, NULL);
        save_done(1, buffer);
        read_into(path);
        CHECK(count_of(text, "\r\n  Name: Bolo\r\n") == 1 && count_of(text, "\r\n  Name: Rua\r\n") == 1,
              "Bolo's and Rua's graves are recorded from");
        _snprintf(line, sizeof line,
                  "%s\\Virtual Villagers Fun Patcher Logs\\Unaccounted Villagers\\Virtual Villagers %d Unaccounted Villagers Log 1.txt",
                  root, game);
        read_into(line);
        CHECK(strstr(text, "Bolo") == NULL, "...Bolo, whose History looks are his, is not Unaccounted");
        CHECK(count_of(text, "Left the village with no Death or Disappeared record") == 1
              && strstr(text, "  Name: Rua\r\n  What: Left the village") != NULL,
              "...Rua, known to the grave only by name and age, stays Unaccounted");

        /* 6: Start Over. */
        reset(game, 1);
        vv_reset_slot_state(game, 1, VILLAGE);
        _snprintf(path, MAX_PATH, "%s\\Virtual Villagers1.ldw", root);
        DeleteFileA(path);
        CHECK(GetFileAttributesA(logged) == INVALID_FILE_ATTRIBUTES, "Start Over deletes the graves file");

        unload();
        free(buffer);
        free_game();
    }
    clean();
    _snprintf(path, MAX_PATH, "%s\\VVFP Parentage Export.dll", files_dir);
    DeleteFileA(path);
    _snprintf(path, MAX_PATH, "%s\\VVFP Cause of Death.dll", files_dir);
    DeleteFileA(path);
    _snprintf(path, MAX_PATH, "%s\\VVFP Save Reset.dll", files_dir);
    DeleteFileA(path);
    RemoveDirectoryA(files_dir);   /* only when empty */
    printf("== %d failure(s) ==\n", failures);
    return failures == 0 ? 0 : 1;
}
