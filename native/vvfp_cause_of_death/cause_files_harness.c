/* Runtime harness for the Cause of Death graves file.  32-bit only.

   Drives the TEST build of "VVFP Cause of Death.dll" (its VvfpCauseTest*
   exports call the same routines the detours call) against real files under
   Documents\LDW\<this exe's basename>\Virtual Villagers Fun Patcher Data\,
   which the harness empties first and removes afterwards:

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
     6. Start Over: VvfpCauseVillageReset forgets the slot, and the shared
        reset (native/shared/save_reset.c, linked in) deletes the file; the
        next village in that slot starts empty.

   Usage:  cause_files_harness.exe "<path to VVFP Cause of Death.test.dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>

#include "save_reset.h"

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

typedef int (__stdcall *setup_t)(int, const void *, void *);
typedef void (__stdcall *index_cause_t)(int, int);
typedef void (__stdcall *index_t)(int);
typedef void (__stdcall *tick_t)(int);
typedef void (__stdcall *reset_t)(int, int);
typedef int (__stdcall *grave_t)(int, int *, int *);

static setup_t setup;
static index_cause_t died, buried;
static index_t decayed;
static tick_t tick;
static reset_t reset;
static grave_t grave_of;
static int *roll;
static HMODULE dll;
static const char *dll_path;

/* A New Home's geometry, as the DLL's GEO row has it. */
#define STRIDE 0x3D8
#define PRESENT 0x28
#define HEALTH 0x344
#define AGE 0x348
#define NAME 0x370
#define SKILLS 0x3BC
#define MANAGER 0x3E010
#define GRAVES 0xA31C
#define GRAVE_STRIDE 0x2C
#define GRAVE_AGE 0x24

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
    strncpy((char *)rec(i) + NAME, name, 0x1B);
    *(int *)(rec(i) + SKILLS + 4) = building;       /* storage index 1 = Building */
}

/* What the game does at a burial: free the record and write the grave. */
static void game_bury(int i, int k) {
    rec(i)[PRESENT] = 0;
    memset(grave(k), 0, GRAVE_STRIDE);
    strncpy((char *)grave(k), (const char *)rec(i) + NAME, 0x1B);
    *(int *)(grave(k) + GRAVE_AGE) = *(int *)(rec(i) + AGE);
}

static void load(void) {
    dll = LoadLibraryA(dll_path);
    if (dll == NULL) {
        printf("cannot load %s\n", dll_path);
        ExitProcess(2);
    }
    setup = (setup_t)GetProcAddress(dll, "VvfpCauseTestSetup");
    died = (index_cause_t)GetProcAddress(dll, "VvfpCauseTestDied");
    buried = (index_cause_t)GetProcAddress(dll, "VvfpCauseTestBuried");
    decayed = (index_t)GetProcAddress(dll, "VvfpCauseTestDecayed");
    tick = (tick_t)GetProcAddress(dll, "VvfpCauseTick");
    reset = (reset_t)GetProcAddress(dll, "VvfpCauseVillageReset");
    grave_of = (grave_t)GetProcAddress(dll, "VvfpCauseTestGrave");
    roll = (int *)GetProcAddress(dll, "VvfpCauseRollTest");
    if (!setup || !died || !buried || !decayed || !tick || !reset || !grave_of || !roll) {
        printf("missing exports\n");
        ExitProcess(2);
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
    _snprintf(out, MAX_PATH, "%s\\Virtual Villagers 1 Graves - Save %d.dat", data_dir, slot);
    out[MAX_PATH - 1] = 0;
}

static long read_file(const char *path, unsigned char *buf, long cap) {
    FILE *f = fopen(path, "rb");
    long n;
    if (f == NULL) return -1;
    n = (long)fread(buf, 1, (size_t)cap, f);
    fclose(f);
    return n;
}

static void wipe(void) {
    char pattern[MAX_PATH], path[MAX_PATH], parent[MAX_PATH], *slash;
    WIN32_FIND_DATAA f;
    HANDLE h;
    _snprintf(pattern, MAX_PATH, "%s\\*", data_dir);
    h = FindFirstFileA(pattern, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (!(f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
                _snprintf(path, MAX_PATH, "%s\\%s", data_dir, f.cFileName);
                DeleteFileA(path);
            }
        } while (FindNextFileA(h, &f));
        FindClose(h);
    }
    RemoveDirectoryA(data_dir);
    lstrcpyA(parent, data_dir);
    slash = strrchr(parent, '\\');
    if (slash) { *slash = 0; RemoveDirectoryA(parent); }
}

static int count_unreadable(void) {
    char pattern[MAX_PATH];
    WIN32_FIND_DATAA f;
    HANDLE h;
    int n = 0;
    _snprintf(pattern, MAX_PATH, "%s\\*.unreadable-*", data_dir);
    h = FindFirstFileA(pattern, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do { ++n; } while (FindNextFileA(h, &f));
        FindClose(h);
    }
    return n;
}

int main(int argc, char **argv) {
    char path[MAX_PATH], tmp[MAX_PATH];
    unsigned char buf[4096];
    long n;
    int cause, epitaph;

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
    CHECK(n == 16 + 12, "the file holds one entry (%ld bytes)", n);
    CHECK(n >= 16 && *(unsigned int *)buf == 0x31444356u && *(unsigned int *)(buf + 4) == 1u
          && *(unsigned int *)(buf + 8) == 1u && *(unsigned int *)(buf + 12) == 1u,
          "header: 'VCD1', version 1, game 1, count 1");
    CHECK(n == 28 && buf[16] == 0 && buf[17] == 0 && buf[18] == 3 && buf[19] == 0
          && buf[24] == 2 && buf[25] == 11 && buf[26] == 0 && buf[27] == 0,
          "entry: a grave, slot 3, cause 2 (Old age), epitaph 11 (Strong Arms, Big Heart)");
    _snprintf(tmp, MAX_PATH, "%s.tmp", path);
    CHECK(GetFileAttributesA(tmp) == INVALID_FILE_ATTRIBUTES, "no .tmp is left behind");
    CHECK(grave_of(3, &cause, &epitaph) && cause == 2 && epitaph == 11, "the grave shows Old age and the epitaph");
    unload();

    printf("2. a new session reads it back\n");
    load();
    tick(1);
    CHECK(grave_of(3, &cause, &epitaph) && cause == 2 && epitaph == 11, "read back from the file");
    grave(3)[0] = 'X';
    CHECK(!grave_of(3, &cause, &epitaph), "a grave whose name changed shows nothing");
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
    CHECK(n == 16 + 2 * 12, "both are in the file (%ld bytes)", n);
    unload();

    printf("4. slots never share entries\n");
    current_slot = 3;
    load();
    tick(1);
    CHECK(!grave_of(3, &cause, &epitaph) && !grave_of(4, &cause, &epitaph), "slot 3 has none of slot 2's");
    villager(7, "Other", 1200, 30, 0);
    died(7, 3);
    game_bury(7, 5);
    buried(7, 5);
    tick(1);
    current_slot = 2;
    tick(1);
    CHECK(!grave_of(5, &cause, &epitaph), "slot 2 has none of slot 3's");
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
    CHECK(n == 28 && buf[24] == 1, "a new file holds only the new grave");
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
        CHECK(n == 28, "a file that cannot be opened is not written while it is locked");
        unload();
    }

    printf("6. Start Over forgets the slot and deletes its file\n");
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
    CHECK(!grave_of(3, &cause, &epitaph), "the new village starts empty");
    file_of(3, path);
    CHECK(GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES, "slot 3's file is untouched");
    unload();

    wipe();
    printf("%s: %d failure(s)\n", failures ? "FAILED" : "PASSED", failures);
    return failures ? 1 : 0;
}
