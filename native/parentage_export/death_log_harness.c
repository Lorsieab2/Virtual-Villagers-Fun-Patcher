/* Runtime harness for the Deaths log.  32-bit only.

   Drives the real "VVFP Parentage Export.dll" (WriteDeathRecord, and the
   EnsureParentageLogForVillage the population exporter calls after every
   save) in all five games' record geometry, against real files under
   Documents\LDW\<this exe's basename>\Virtual Villagers Fun Patcher Logs\,
   which the harness empties first and removes afterwards:

     1. With "VVFP Cause of Death.dll" beside the executable, a village's
        first save creates its Deaths log, headed with the village, empty.
     2. A death is written as one "Death <n>" record, in the same format in
        all five games: name, age at death in the game's units, cause, head,
        body.  The Births and Conceptions log gets nothing.
     3. A record outside the game's villager table is refused.
     4. A death before the village is known (no save yet) is held, then
        written under the village's header at the save.
     5. 256 records per file: the 257th starts file 2, numbered on.
     6. Start Over (native/shared/save_reset.c, linked in) deletes that
        village's Deaths logs and no other village's.
     7. Without "VVFP Cause of Death.dll" no Deaths log is created.

   The statistics companion and the cause-of-death companion are detected by
   their files beside the executable, so the harness creates empty stand-ins
   there and removes them when done.

   Usage:  death_log_harness.exe "<path to VVFP Parentage Export.dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "village_identity.h"
#include "save_reset.h"

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

typedef int (__stdcall *death_t)(int, const void *, int, const char *);
typedef int (__stdcall *ensure_village_t)(int, const char *, const void *);

/* Each game's record geometry, as the export DLL's own layout table has it. */
struct layout {
    int game;
    unsigned int stride, slots, base, active, age, head, body, name, name_cap;
};
static const struct layout LAYOUTS[5] = {
    { 1, 0x3D8,  256, 0,    0x28,   0x348,  0x360,  0x364,  0x370,  0x1C },
    { 2, 0xE48C, 256, 0,    0x30,   0x530,  0x548,  0x54C,  0x564,  0x18 },
    { 3, 0x1F8C, 150, 0x14, 0xF10,  0xDC4,  0xDF0,  0xDF4,  0xDD4,  0x19 },
    { 4, 0x2E3C, 150, 0x44, 0x1CC4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B9C, 0x19 },
    { 5, 0x2F44, 150, 0x48, 0x1CD4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B9C, 0x19 },
};

/* Where each game keeps its table, from the executable's base -- the DLL
   reads it there (parentage_export.c VILLAGER_TABLE), so the harness, linked
   at a fixed base with free memory above it (scripts/build_death_log_harness.ps1),
   puts its table at the same offset from its own base: VV1 and VV2 hold a
   pointer to it, VV3-VV5 the table itself. */
static const struct { unsigned int rva; int is_pointer; } TABLE[5] = {
    { 0x8B614u, 1 }, { 0x99F24u, 1 }, { 0x19E110u, 0 }, { 0x10E568u, 0 }, { 0x154148u, 0 },
};

static const struct layout *g;
static unsigned char *records;
static void *pointer_page;

static unsigned char *alloc_table(int game) {
    size_t size = g->base + (size_t)g->slots * g->stride;
    unsigned char *at = (unsigned char *)((uintptr_t)GetModuleHandleW(NULL) + TABLE[game - 1].rva);
    unsigned char *table;
    if (TABLE[game - 1].is_pointer) {
        /* The pointer's page first: a table allocated anywhere could land on it. */
        pointer_page = VirtualAlloc((void *)((uintptr_t)at & ~0xFFFu), 0x1000, MEM_RESERVE | MEM_COMMIT,
                                    PAGE_READWRITE);
        table = (unsigned char *)VirtualAlloc(NULL, size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        if (table == NULL || pointer_page == NULL) return NULL;
        *(unsigned char **)at = table;
        return table;
    }
    table = (unsigned char *)VirtualAlloc((void *)((uintptr_t)at & ~0xFFFFu),
                                          size + ((uintptr_t)at & 0xFFFFu),
                                          MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    return table == NULL ? NULL : at;
}

static void free_table(int game) {
    if (TABLE[game - 1].is_pointer) {
        VirtualFree(*(unsigned char **)((uintptr_t)GetModuleHandleW(NULL) + TABLE[game - 1].rva), 0, MEM_RELEASE);
        VirtualFree(pointer_page, 0, MEM_RELEASE);
    } else {
        VirtualFree((void *)((uintptr_t)records & ~0xFFFFu), 0, MEM_RELEASE);
    }
}
static unsigned char *rec(int i) { return records + g->base + i * g->stride; }

static void villager(int i, const char *name, int age, int head, int body) {
    memset(rec(i), 0, g->stride);
    rec(i)[g->active] = 1;
    *(int *)(rec(i) + g->age) = age;
    *(int *)(rec(i) + g->head) = head;
    *(int *)(rec(i) + g->body) = body;
    strncpy((char *)rec(i) + g->name, name, g->name_cap - 1);
}

static char logs[MAX_PATH];
static char exe_dir[MAX_PATH];
static HMODULE dll;
static death_t write_death;
static ensure_village_t ensure_village;
static const char *dll_path;

static int locate(void) {
    char docs[MAX_PATH], exe[MAX_PATH], *base, *dot;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) return 0;
    if (GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) return 0;
    base = strrchr(exe, '\\');
    if (base == NULL) return 0;
    lstrcpynA(exe_dir, exe, (int)(base - exe) + 1);
    ++base;
    dot = strrchr(base, '.');
    if (dot) *dot = 0;
    _snprintf(logs, MAX_PATH, "%s\\LDW\\%s\\Virtual Villagers Fun Patcher Logs", docs, base);
    logs[MAX_PATH - 1] = 0;
    return 1;
}

static void empty_folder(const char *folder) {
    char pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA f;
    HANDLE h;
    _snprintf(pattern, MAX_PATH, "%s\\*.txt", folder);
    h = FindFirstFileA(pattern, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do { _snprintf(path, MAX_PATH, "%s\\%s", folder, f.cFileName); DeleteFileA(path); }
        while (FindNextFileA(h, &f));
        FindClose(h);
    }
}

static void wipe(int remove_dirs) {
    char sub[MAX_PATH], parent[MAX_PATH], *cut;
    _snprintf(sub, MAX_PATH, "%s\\Deaths", logs);
    empty_folder(sub);
    if (remove_dirs) RemoveDirectoryA(sub);
    _snprintf(sub, MAX_PATH, "%s\\Births and Conceptions", logs);
    empty_folder(sub);
    if (remove_dirs) {
        RemoveDirectoryA(sub);
        RemoveDirectoryA(logs);
        lstrcpyA(parent, logs);
        cut = strrchr(parent, '\\');
        if (cut) { *cut = 0; RemoveDirectoryA(parent); }
    }
}

static void stand_in(const char *name, int present) {
    char path[MAX_PATH];
    _snprintf(path, MAX_PATH, "%s\\%s", exe_dir, name);
    path[MAX_PATH - 1] = 0;
    if (present) {
        HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
        if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
    } else {
        DeleteFileA(path);
    }
}

static void load(void) {
    dll = LoadLibraryA(dll_path);
    if (dll == NULL) { printf("cannot load %s\n", dll_path); ExitProcess(2); }
    write_death = (death_t)GetProcAddress(dll, "WriteDeathRecord");
    ensure_village = (ensure_village_t)GetProcAddress(dll, "EnsureParentageLogForVillage");
    if (write_death == NULL || ensure_village == NULL) { printf("missing exports\n"); ExitProcess(2); }
}

static char text[1 << 17];
static int read_deaths(int game, int number) {
    char path[MAX_PATH];
    FILE *f;
    size_t n;
    _snprintf(path, MAX_PATH, "%s\\Deaths\\Virtual Villagers %d Deaths Log %d.txt", logs, game, number);
    f = fopen(path, "rb");
    if (f == NULL) { text[0] = 0; return 0; }
    n = fread(text, 1, sizeof text - 1, f);
    text[n] = 0;
    fclose(f);
    return 1;
}

static int births_mention_death(int game) {
    char path[MAX_PATH], buf[4096];
    FILE *f;
    size_t n;
    _snprintf(path, MAX_PATH, "%s\\Births and Conceptions\\Virtual Villagers %d Births and Conceptions Log 1.txt",
              logs, game);
    f = fopen(path, "rb");
    if (f == NULL) return 0;
    n = fread(buf, 1, sizeof buf - 1, f);
    buf[n] = 0;
    fclose(f);
    return strstr(buf, "Death") != NULL;
}

#define VILLAGE "Village: Harness Tribe (Save 1)\n"
#define OTHER   "Village: Other Tribe (Save 2)\n"

int main(int argc, char **argv) {
    char expected[512];
    char record_text[5][512];
    int game;

    if (argc < 2) { printf("usage: death_log_harness <dll>\n"); return 2; }
    dll_path = argv[1];
    if (!locate()) return 2;
    wipe(1);
    stand_in("VVFP Statistics Export.dll", 1);
    stand_in("VVFP Cause of Death.dll", 1);

    for (game = 1; game <= 5; ++game) {
        g = &LAYOUTS[game - 1];
        printf("Virtual Villagers %d\n", game);
        records = alloc_table(game);
        if (records == NULL) {
            MEMORY_BASIC_INFORMATION info;
            VirtualQuery((void *)((uintptr_t)GetModuleHandleW(NULL) + TABLE[game - 1].rva), &info, sizeof info);
            printf("cannot place the table at the game's address (error %lu; region %p state %lx)\n",
                   GetLastError(), info.AllocationBase, info.State);
            return 2;
        }
        villager(0, "Ana", 600, 3, 4);
        villager(1, "Bonedry", 1234, 7, 9);
        villager(2, "Cala", 300, 1, 2);
        load();

        /* 4 first: a death before any save is held. */
        CHECK(write_death(game, rec(2), 300, "Unknown causes") == 1, "a death before the first save is accepted");
        CHECK(!read_deaths(game, 1), "...and held: nothing on disk yet");

        /* 1: the first save creates the log and files the held record. */
        vv_village_publish(VILLAGE);
        CHECK(ensure_village(game, VILLAGE, records) == 1, "the save ensures the logs");
        CHECK(read_deaths(game, 1), "the Deaths log exists after the save");
        _snprintf(expected, sizeof expected,
                  "Village: Harness Tribe (Save 1)\r\n"
                  "Death 1\r\n  Name: Cala\r\n  Age at death: 300\r\n  Cause of death: Unknown causes\r\n"
                  "  Head: 1\r\n  Body: 2\r\n\r\n");
        CHECK(strcmp(text, expected) == 0, "the held death is written under the village header");

        /* 2: a death once the village is known. */
        CHECK(write_death(game, rec(1), 1234, "Old age") == 1, "a death is written");
        read_deaths(game, 1);
        {
            const char *at = strstr(text, "Death 2\r\n");
            CHECK(at != NULL, "numbered on: Death 2");
            if (at != NULL) {
                lstrcpynA(record_text[game - 1], at + 9, 512);
                CHECK(strcmp(at, "Death 2\r\n  Name: Bonedry\r\n  Age at death: 1234\r\n"
                                 "  Cause of death: Old age\r\n  Head: 7\r\n  Body: 9\r\n\r\n") == 0,
                      "name, age in the game's units, cause, head, body");
            }
        }
        CHECK(!births_mention_death(game), "the Births and Conceptions log has no Death record");

        /* 3: not a villager record. */
        {
            unsigned char stray[0x4000];
            memset(stray, 0, sizeof stray);
            CHECK(write_death(game, stray + 0x10, 99, "Old age") == 0, "a record outside the table is refused");
            CHECK(write_death(game, rec(1) + 4, 99, "Old age") == 0, "a pointer inside a record is refused");
        }

        /* 5: the roll (VV1 only; the code is shared). */
        if (game == 1) {
            int k;
            for (k = 0; k < 254; ++k) {
                write_death(game, rec(0), 600, "Disease");
            }
            read_deaths(game, 1);
            CHECK(strstr(text, "Death 256\r\n") != NULL && strstr(text, "Death 257") == NULL,
                  "file 1 ends at Death 256");
            write_death(game, rec(0), 600, "Disease");
            CHECK(read_deaths(game, 2) && strncmp(text, "Village: Harness Tribe (Save 1)\r\nDeath 257\r\n", 44) == 0,
                  "Death 257 starts file 2 under the same header");
        }

        /* 6: Start Over deletes this village's Deaths logs, not another's. */
        vv_village_publish(OTHER);
        ensure_village(game, OTHER, records);
        write_death(game, rec(1), 1234, "Starvation");
        {
            int other_file = game == 1 ? 3 : 2;
            CHECK(read_deaths(game, other_file) && strstr(text, "Other Tribe") != NULL,
                  "another village gets its own Deaths log (file %d)", other_file);
            vv_reset_slot_state(game, 1, VILLAGE);
            CHECK(!read_deaths(game, 1), "Start Over deleted the village's Deaths log");
            if (game == 1) CHECK(!read_deaths(game, 2), "...all of them");
            CHECK(read_deaths(game, other_file), "the other village's Deaths log is kept");
        }
        FreeLibrary(dll);
        free_table(game);
        wipe(0);
    }

    for (game = 2; game <= 5; ++game) {
        CHECK(strcmp(record_text[game - 1], record_text[0]) == 0,
              "Virtual Villagers %d writes the same record as Virtual Villagers 1", game);
    }

    /* 7: no cause-of-death companion, no Deaths log. */
    printf("without VVFP Cause of Death.dll\n");
    stand_in("VVFP Cause of Death.dll", 0);
    g = &LAYOUTS[2];
    records = alloc_table(3);
    villager(0, "Ana", 600, 3, 4);
    load();
    vv_village_publish(VILLAGE);
    ensure_village(3, VILLAGE, records);
    CHECK(!read_deaths(3, 1), "the save creates no Deaths log");
    FreeLibrary(dll);
    free_table(3);

    stand_in("VVFP Statistics Export.dll", 0);
    wipe(1);
    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
