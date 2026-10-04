/* Runtime harness: the logs name their village without Village Statistics.
   32-bit only.

   Codex (#504 review): with Cause of Death and Write Births and Conceptions
   Log ticked but Village Statistics not, nothing published the village, so
   the Deaths and Unaccounted Villagers records were written at once with no
   header -- into files every village then shared, which Start Over could not
   attribute -- and the logs were not created at a village's first save.

   "VVFP Cause of Death.dll" sits on the game's save call, and now hands the
   parentage DLL the save buffer and slot there (PublishVillageAtSave). This
   drives the real "VVFP Parentage Export.dll" in all five games' record
   geometry, against real files under
   Documents\LDW\<this exe's basename>\Virtual Villagers Fun Patcher Logs\,
   which harness_ldw_tree_begin() guarantees did not exist before the run
   and which the harness removes afterwards:

     1. Cause of Death shipped, no Village Statistics: a Birth and a Death
        before the first save are HELD -- nothing on disk.
     2. The save (PublishVillageAtSave with the game's own save buffer):
        the village's header is published exactly as the statistics
        companion formats it, and the Births and Conceptions, Deaths and
        Unaccounted Villagers logs all exist, opening with it, holding the
        held records.
     3. A record after the save goes straight under the same header.
     4. Bad arguments are refused and publish nothing.
     5. With Village Statistics shipped, PublishVillageAtSave does nothing:
        that companion already named this save's village.
     6. Cause of Death loaded but refused (its hooks did not install): it
        will never name a village, so records are written at once,
        unlabelled -- held ones first, in order -- exactly as with neither
        companion. Uses the TEST build of the companion, renamed beside the
        harness, whose install is refused here because no game is mapped.
     6b. Cause of Death shipped but unable to load: the same, at once.
     7. Neither companion: records are written at once, unlabelled, as
        before.

   The companions are detected by their files beside the executable, so the
   harness creates stand-ins there and removes them when done.

   Usage:  village_publisher_harness.exe "<VVFP Parentage Export.dll>" "<VVFP Cause of Death.test.dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "village_identity.h"
#include "../shared/harness_ldw_tree.h"

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

typedef int (__stdcall *record_t)(int, int, const void *, int, const char *, const char *, int);
typedef int (__stdcall *birth_t)(int, const char *, int, int, const char *, int, int,
                                 const char *, int, int, const void *);
typedef int (__stdcall *publish_t)(int, const void *, int);
typedef int (__stdcall *install_t)(int, const void *);
typedef int (__stdcall *setup_t)(int, const void *, void *);
typedef void (__stdcall *arm_t)(int);
typedef void (__stdcall *save_done_t)(int, const void *);

enum { DEATH = 2 };

/* Each game's record geometry, as the export DLL's own layout table has it
   (the same rows as death_log_harness.c). */
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

/* Where each game keeps its table, from the executable's base (see
   death_log_harness.c): the harness is linked at a fixed base with free
   memory above it. */
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
static record_t write_record;
static birth_t birth;
static publish_t publish;
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
    static const char *const FOLDERS[3] = { "Deaths", "Unaccounted Villagers", "Births and Conceptions" };
    char sub[MAX_PATH], parent[MAX_PATH], *cut;
    int k;
    for (k = 0; k < 3; ++k) {
        _snprintf(sub, MAX_PATH, "%s\\%s", logs, FOLDERS[k]);
        empty_folder(sub);
        if (remove_dirs) RemoveDirectoryA(sub);
    }
    if (remove_dirs) {
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

/* Unload every reference to the Cause of Death companion, so the next phase
   starts without it (the parentage DLL may have loaded it itself). */
static void drop_cause(void) {
    HMODULE h;
    while ((h = GetModuleHandleA("VVFP Cause of Death.dll")) != NULL) {
        FreeLibrary(h);
    }
    /* ...and every parentage DLL instance: the companion keeps its own
       reference to the one it loaded, so a phase would otherwise inherit
       the previous phase's state. */
    while ((h = GetModuleHandleA("VVFP Parentage Export.dll")) != NULL) {
        FreeLibrary(h);
    }
}

/* The companion beside the executable: its TEST build (which loads, and
   reports it is not installed yet), or an empty file that cannot load. */
static void cause_beside(const char *test_dll, int loadable) {
    char path[MAX_PATH];
    drop_cause();
    _snprintf(path, MAX_PATH, "%s\\VVFP Cause of Death.dll", exe_dir);
    path[MAX_PATH - 1] = 0;
    if (loadable) {
        CopyFileA(test_dll, path, FALSE);
    } else {
        HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
        if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
    }
}

static void load(void) {
    dll = LoadLibraryA(dll_path);
    if (dll == NULL) { printf("cannot load %s\n", dll_path); exit(2); }
    write_record = (record_t)GetProcAddress(dll, "WriteVillageRecord");
    birth = (birth_t)GetProcAddress(dll, "WriteParentageBirth");
    publish = (publish_t)GetProcAddress(dll, "PublishVillageAtSave");
    if (write_record == NULL || birth == NULL) { printf("missing exports\n"); exit(2); }
}

static char text[1 << 16];
#define STARTS(literal) (strncmp(text, literal, sizeof(literal) - 1) == 0)
static int read_log(const char *folder, const char *stem, int game, int number) {
    char path[MAX_PATH];
    FILE *f;
    size_t n;
    _snprintf(path, MAX_PATH, "%s\\%s\\Virtual Villagers %d %s %d.txt", logs, folder, game, stem, number);
    f = fopen(path, "rb");
    if (f == NULL) { text[0] = 0; return 0; }
    n = fread(text, 1, sizeof text - 1, f);
    text[n] = 0;
    fclose(f);
    return 1;
}
static int read_deaths(int game) { return read_log("Deaths", "Deaths Log", game, 1); }
static int read_unaccounted(int game) { return read_log("Unaccounted Villagers", "Unaccounted Villagers Log", game, 1); }
static int read_births(int game) { return read_log("Births and Conceptions", "Births and Conceptions Log", game, 1); }

/* The block a game hands its save writer, with the village name where that
   game keeps it (native/shared/village_identity.c). */
static unsigned char *save_buffer(int game, const char *name) {
    unsigned int at = vv_village_name_offset(game);
    unsigned char *buffer = (unsigned char *)calloc(1, at + VV_VILLAGE_NAME_MAX + 16);
    strcpy((char *)buffer + at, name);
    return buffer;
}

#define DIED "  Age at death: 300\n  Cause of death: Unknown causes\n  Grave: no grave (never buried: the game removed the body)\n  Epitaph: (none)\n"
#define BURIED "  Age at death: 1234\n  Cause of death: Old age\n  Grave: Master Builder\n  Epitaph: Inspired Architect\n"

int main(int argc, char **argv) {
    harness_ldw_tree_begin();   /* first: leaves Documents\LDW as it found it */
    char header[128];
    char expected[160];
    int game;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc < 3) {
        printf("usage: village_publisher_harness <parentage dll> <cause of death test dll>\n");
        return 2;
    }
    dll_path = argv[1];
    if (!locate()) return 2;
    stand_in("VVFP Statistics Export.dll", 0);
    cause_beside(argv[2], 1);

    for (game = 1; game <= 5; ++game) {
        unsigned char *buffer;
        g = &LAYOUTS[game - 1];
        printf("Virtual Villagers %d: Cause of Death, no Village Statistics\n", game);
        records = alloc_table(game);
        if (records == NULL) { printf("cannot place the table at the game's address\n"); return 2; }
        villager(0, "Ana", 600, 3, 4);
        villager(1, "Bonedry", 1234, 7, 9);
        villager(2, "Cala", 300, 1, 2);
        vv_village_publish("");         /* a new session: nothing named yet */
        load();
        {
            /* The companion as the game has it once installed: its TEST
               build, pointed at this table (no game image is mapped here,
               so its own table addresses cannot be read). */
            char cause[MAX_PATH];
            HMODULE companion;
            setup_t setup;
            _snprintf(cause, MAX_PATH, "%s\\VVFP Cause of Death.dll", exe_dir);
            companion = LoadLibraryA(cause);
            setup = companion != NULL ? (setup_t)GetProcAddress(companion, "VvfpCauseTestSetup") : NULL;
            CHECK(setup != NULL && setup(game, NULL, records) == 1, "Cause of Death is installed");
        }

        /* 1: before the first save, records are held. */
        CHECK(birth(game, "", -1, -1, "Ana", 3, 4, "Bonedry", 7, 9, rec(2)) == 1,
              "a birth before the first save is accepted");
        CHECK(write_record(game, DEATH, rec(1), 1, BURIED, NULL, 1) == 1,
              "a death before the first save is accepted");
        CHECK(!read_births(game) && !read_deaths(game) && !read_unaccounted(game),
              "...and held: no log on disk before the save");
        CHECK(publish != NULL, "PublishVillageAtSave is exported");
        if (publish == NULL) {
            printf("== %d failure(s) ==\n", failures);
            wipe(1);
            return 1;
        }

        /* 4: bad arguments publish nothing. */
        buffer = save_buffer(game, "Publisher Tribe");
        CHECK(publish(game, buffer, 0) == 0 && publish(game, NULL, 2) == 0
              && publish(6, buffer, 2) == 0, "a bad slot, buffer or game is refused");
        CHECK(!vv_village_recall(header, sizeof header) || strstr(header, "Publisher") == NULL,
              "...and publishes nothing");

        /* 2: the save. */
        CHECK(publish(game, buffer, 2) == 1, "the save names the village");
        _snprintf(expected, sizeof expected, "Village: Publisher Tribe (Save 2)\n");
        CHECK(vv_village_recall(header, sizeof header) && strcmp(header, expected) == 0,
              "the published header is the statistics companion's format");
        CHECK(read_unaccounted(game) && strcmp(text, "Village: Publisher Tribe (Save 2)\r\n") == 0,
              "the Unaccounted Villagers log exists at the first save, headed and empty");
        CHECK(read_deaths(game)
              && STARTS("Village: Publisher Tribe (Save 2)\r\nDeath 1\r\n  Name: Bonedry\r\n"),
              "the Deaths log opens with the header and the held death");
        CHECK(read_births(game)
              && STARTS("Village: Publisher Tribe (Save 2)\r\n")
              && strstr(text, "Birth\r\n  Child: Cala\r\n") != NULL,
              "the Births and Conceptions log opens with the header and the held birth");

        /* 3: after the save, straight under the header. */
        CHECK(write_record(game, DEATH, rec(2), 1, DIED, NULL, 1) == 1, "a death after the save");
        CHECK(read_deaths(game) && strstr(text, "Death 2\r\n  Name: Cala\r\n") != NULL
              && strstr(text + 1, "Village: ") == NULL,
              "is written at once, under the one header");
        CHECK(publish(game, buffer, 2) == 1 && read_deaths(game) && strstr(text + 1, "Village: ") == NULL
              && strstr(text, "Death 3") == NULL,
              "a second save adds no header and writes nothing twice");

        free(buffer);
        FreeLibrary(dll);
        drop_cause();
        free_table(game);
        wipe(0);
    }

    /* 5: with Village Statistics shipped, it already named the village. */
    printf("Virtual Villagers 3: Village Statistics too\n");
    stand_in("VVFP Statistics Export.dll", 1);
    g = &LAYOUTS[2];
    records = alloc_table(3);
    villager(0, "Ana", 600, 3, 4);
    load();
    vv_village_publish("Village: Statistics Tribe (Save 1)\n");
    {
        unsigned char *buffer = save_buffer(3, "Publisher Tribe");
        CHECK(publish(3, buffer, 1) == 0, "PublishVillageAtSave does nothing");
        CHECK(vv_village_recall(header, sizeof header)
              && strcmp(header, "Village: Statistics Tribe (Save 1)\n") == 0,
              "the statistics companion's header stands");
        CHECK(!read_deaths(3) && !read_births(3), "and creates no log");
        free(buffer);
    }
    FreeLibrary(dll);
    free_table(3);
    stand_in("VVFP Statistics Export.dll", 0);
    wipe(0);

    /* 6: Cause of Death loaded but refused. */
    printf("Virtual Villagers 3: Cause of Death refused\n");
    {
        char cause[MAX_PATH], beside[MAX_PATH];
        HMODULE companion;
        install_t install;
        const char *shipped = dll_path;
        _snprintf(cause, MAX_PATH, "%s\\VVFP Cause of Death.dll", exe_dir);
        drop_cause();
        CHECK(CopyFileA(argv[2], cause, FALSE), "the companion's TEST build is beside the harness");
        /* The companion loads the parentage DLL from the executable's folder,
           so this phase uses that copy: one module, one queue. */
        _snprintf(beside, MAX_PATH, "%s\\VVFP Parentage Export.dll", exe_dir);
        CHECK(CopyFileA(shipped, beside, FALSE), "the parentage DLL is beside the harness");
        dll_path = beside;
        g = &LAYOUTS[2];
        records = alloc_table(3);
        villager(0, "Ana", 600, 3, 4);
        villager(1, "Bonedry", 1234, 7, 9);
        load();
        vv_village_publish("");
        companion = LoadLibraryA(cause);
        if (companion != NULL) {
            arm_t arm = (arm_t)GetProcAddress(companion, "VvfpCauseTestArm");
            if (arm != NULL) arm(1);      /* its save hook arms, as in a game */
        }
        CHECK(write_record(3, DEATH, rec(1), 1, BURIED, NULL, 1) == 1 && !read_deaths(3),
              "before the companion is installed, a death is held: it will name the village");
        install = companion != NULL ? (install_t)GetProcAddress(companion, "VvfpCauseInstall") : NULL;
        CHECK(install != NULL && install(3, NULL) == 0, "its install is refused (no game here)");
        CHECK(read_deaths(3) && STARTS("Death 1\r\n  Name: Bonedry\r\n") && strstr(text, "Village: ") == NULL,
              "the refusal itself writes the held death, unlabelled -- no later record needed (#512)");
        CHECK(write_record(3, DEATH, rec(0), 1, BURIED, NULL, 1) == 1, "the next death");
        CHECK(read_deaths(3) && STARTS("Death 1\r\n  Name: Bonedry\r\n")
              && strstr(text, "Death 2\r\n  Name: Ana\r\n") != NULL && strstr(text, "Village: ") == NULL,
              "is written at once, unlabelled, after the held one, in order");
        if (companion != NULL) FreeLibrary(companion);
        FreeLibrary(dll);
        drop_cause();
        free_table(3);
        DeleteFileA(cause);
        DeleteFileA(beside);
        dll_path = shipped;
        wipe(0);
    }

    /* 6a: a save before the install (#512 review): The Secret City installs
       the companion only when a villager is first drawn, so a catch-up
       record can be held when the game saves. The save hook the parentage
       DLL armed names the village there, and the held records go out under
       it -- without reconciling anything, since nothing was watching. */
    printf("Virtual Villagers 3: a save before Cause of Death is installed\n");
    {
        char cause[MAX_PATH], beside[MAX_PATH];
        HMODULE companion;
        save_done_t save_done = NULL;
        const char *shipped = dll_path;
        unsigned char *buffer = save_buffer(3, "Early Tribe");
        _snprintf(cause, MAX_PATH, "%s\\VVFP Cause of Death.dll", exe_dir);
        drop_cause();
        CopyFileA(argv[2], cause, FALSE);
        _snprintf(beside, MAX_PATH, "%s\\VVFP Parentage Export.dll", exe_dir);
        CopyFileA(shipped, beside, FALSE);
        dll_path = beside;
        g = &LAYOUTS[2];
        records = alloc_table(3);
        villager(0, "Ana", 600, 3, 4);
        villager(1, "Bonedry", 1234, 7, 9);
        villager(2, "Cala", 300, 1, 2);
        load();
        vv_village_publish("");
        companion = LoadLibraryA(cause);
        if (companion != NULL) {
            arm_t arm = (arm_t)GetProcAddress(companion, "VvfpCauseTestArm");
            save_done = (save_done_t)GetProcAddress(companion, "VvfpCauseTestSaveDone");
            if (arm != NULL) arm(1);
        }
        CHECK(birth(3, "", -1, -1, "Ana", 3, 4, "Bonedry", 7, 9, rec(2)) == 1
              && write_record(3, DEATH, rec(1), 1, BURIED, NULL, 1) == 1
              && !read_births(3) && !read_deaths(3),
              "catch-up records are held while the companion is not installed");
        CHECK(save_done != NULL, "the TEST build has the save entry");
        if (save_done != NULL) save_done(1, buffer);
        CHECK(read_births(3) && STARTS("Village: Early Tribe (Save 1)\r\n")
              && strstr(text, "Birth\r\n  Child: Cala\r\n") != NULL,
              "the save names the village and writes the held birth under it");
        CHECK(read_deaths(3) && STARTS("Village: Early Tribe (Save 1)\r\nDeath 1\r\n  Name: Bonedry\r\n"),
              "...and the held death");
        CHECK(read_unaccounted(3) && strcmp(text, "Village: Early Tribe (Save 1)\r\n") == 0,
              "nothing is reconciled before the install: the Unaccounted log is only headed");
        free(buffer);
        if (companion != NULL) FreeLibrary(companion);
        FreeLibrary(dll);
        drop_cause();
        free_table(3);
        DeleteFileA(cause);
        DeleteFileA(beside);
        dll_path = shipped;
        wipe(0);
    }

    /* 6c: a save hook that cannot be armed can never name a village: the
       first record goes out at once, unlabelled. */
    printf("Virtual Villagers 3: the save hook cannot be armed\n");
    {
        char cause[MAX_PATH];
        HMODULE companion;
        _snprintf(cause, MAX_PATH, "%s\\VVFP Cause of Death.dll", exe_dir);
        drop_cause();
        CopyFileA(argv[2], cause, FALSE);
        g = &LAYOUTS[2];
        records = alloc_table(3);
        villager(1, "Bonedry", 1234, 7, 9);
        load();
        vv_village_publish("");
        companion = LoadLibraryA(cause);
        if (companion != NULL) {
            arm_t arm = (arm_t)GetProcAddress(companion, "VvfpCauseTestArm");
            if (arm != NULL) arm(-1);
        }
        CHECK(write_record(3, DEATH, rec(1), 1, BURIED, NULL, 1) == 1 && read_deaths(3)
              && STARTS("Death 1\r\n  Name: Bonedry\r\n"),
              "a death is written at once, unlabelled");
        if (companion != NULL) FreeLibrary(companion);
        FreeLibrary(dll);
        drop_cause();
        free_table(3);
        wipe(0);
    }

    /* 6b: Cause of Death shipped but unloadable (#512 review): it can never
       name a village, so records are written at once, unlabelled -- not
       held until exit. */
    printf("Virtual Villagers 3: Cause of Death cannot load\n");
    cause_beside(argv[2], 0);
    g = &LAYOUTS[2];
    records = alloc_table(3);
    villager(0, "Ana", 600, 3, 4);
    villager(1, "Bonedry", 1234, 7, 9);
    load();
    vv_village_publish("");
    CHECK(write_record(3, DEATH, rec(1), 1, BURIED, NULL, 1) == 1 && read_deaths(3)
          && STARTS("Death 1\r\n  Name: Bonedry\r\n"),
          "a death is written at once, unlabelled, not held for a companion that cannot load");
    FreeLibrary(dll);
    drop_cause();
    free_table(3);
    wipe(0);

    /* 7: neither companion. */
    printf("Virtual Villagers 3: neither companion\n");
    drop_cause();
    stand_in("VVFP Cause of Death.dll", 0);
    g = &LAYOUTS[2];
    records = alloc_table(3);
    villager(0, "Ana", 600, 3, 4);
    villager(2, "Cala", 300, 1, 2);
    load();
    CHECK(birth(3, "", -1, -1, "Ana", 3, 4, "Bo", 7, 9, rec(2)) == 1 && read_births(3)
          && STARTS("Birth\r\n  Child: Cala\r\n"),
          "a birth is written at once, unlabelled, as before");
    FreeLibrary(dll);
    free_table(3);

    wipe(1);
    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
