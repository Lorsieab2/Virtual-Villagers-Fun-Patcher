/* The head looks' per-save file against real files on disk (tests/test_head_look.py runs it through
   scripts/build_head_look_harness.ps1).

   The companion's store (head_look_store.inc) and the Start Over reset (native/shared/save_reset.c) are
   compiled here unchanged; only what they ask of the game is replaced: the save slot, a village of named
   records, and the save folder -- a fresh folder under %TEMP%, never the player's Documents\LDW.

   Proves: a look is published to "<save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\Head Looks\
   Head Looks - Save <S>.dat" in the documented format and read back by a new session; it follows its
   villager when a reload packs the records after a death, and when a copied file is read in another slot;
   a newborn in a dead villager's record never inherits a look, a body not yet buried keeps it, a rename
   keeps it; another village's file is never replaced by an empty table and is moved aside before the
   first look is written; a missing, short, mis-sized, wrong-game or wrong-magic file leaves every look
   Auto and is set aside intact; a value above 2 reads as Auto; Start Over deletes the file and the new
   village's looks are all Auto; a set that cannot be written changes nothing.  Exit code 0 when every
   check passes. */
#include <stdio.h>
#include <windows.h>
#include <string.h>

static int g_fail_writes;
static BOOL WINAPI harness_write(HANDLE h, LPCVOID data, DWORD size, LPDWORD wrote, LPOVERLAPPED o) {
    if (g_fail_writes) {
        *wrote = 0;
        SetLastError(ERROR_DISK_FULL);
        return FALSE;
    }
    return WriteFile(h, data, size, wrote, o);
}
#define VV_SIDECAR_WRITE_FILE harness_write

static DWORD g_ticks = 100000;
#define VV_SIDECAR_TICKS() g_ticks
#define GetTickCount() g_ticks

#include "../shared/save_folder.h"
#include "../shared/save_reset.h"
#include "../shared/sidecar_io.h"
#include "../shared/per_save_data.h"
#include "../shared/mask_follow.h"
#include "../shared/foreign_sidecar.h"

static int failures;
static char g_root[MAX_PATH];

static void check(int condition, const char *what) {
    printf("  [%s] %s\n", condition ? "PASS" : "FAIL", what);
    if (!condition) {
        ++failures;
    }
}

/* ---- the save folder: %TEMP%\vvfp_head_look_harness_<pid> ------------------------------------------ */

int vv_save_folder(char *out, int reserve) {
    if (lstrlenA(g_root) + reserve >= MAX_PATH) {
        return 0;
    }
    lstrcpyA(out, g_root);
    CreateDirectoryA(out, NULL);
    return 1;
}

int vv_save_folder_w(wchar_t *out, int reserve) {
    char narrow[MAX_PATH];
    if (!vv_save_folder(narrow, reserve)) {
        return 0;
    }
    MultiByteToWideChar(CP_ACP, 0, narrow, -1, out, MAX_PATH);
    return 1;
}

int vv_save_subfolder(char *out, const char *sub, int reserve) {
    char built[MAX_PATH];
    const char *p;
    if (!vv_save_folder(built, lstrlenA(sub) + 1 + reserve)) {
        return 0;
    }
    lstrcatA(built, "\\");
    for (p = sub; *p; ++p) {
        if (*p == '\\') {
            CreateDirectoryA(built, NULL);
        }
        built[lstrlenA(built) + 1] = '\0';
        built[lstrlenA(built)] = *p;
    }
    CreateDirectoryA(built, NULL);
    lstrcpyA(out, built);
    return 1;
}

int vv_save_subfolder_w(wchar_t *out, const wchar_t *sub, int reserve) {
    char narrow_sub[MAX_PATH];
    char narrow[MAX_PATH];
    WideCharToMultiByte(CP_ACP, 0, sub, -1, narrow_sub, MAX_PATH, NULL, NULL);
    if (!vv_save_subfolder(narrow, narrow_sub, reserve)) {
        return 0;
    }
    MultiByteToWideChar(CP_ACP, 0, narrow, -1, out, MAX_PATH);
    return 1;
}

/* ---- the game: a slot and a village of records -------------------------------------------------------
   Each record: [0] held, [1..25] name, [28] sex dword, [32..56] the father's name, [57..81] the mother's. */

#define HL_MAX 256
#define REC 96
static unsigned char g_records[HL_MAX][REC];
static int g_count = 150;
static int g_slot = 1;
static int g_game = 5;

static int hl_game(void) { return g_game; }
static int hl_slots(void) { return g_count; }
static const unsigned char *hl_record(int i) { return i >= 0 && i < g_count ? g_records[i] : NULL; }
static int hl_present(const unsigned char *r) { return r[0] != 0; }
static int hl_slot_now(void) { return g_slot; }

static unsigned int fnv(unsigned int h, const unsigned char *t, int cap) {
    int k;
    for (k = 0; k < cap && t[k]; ++k) {
        h = (h ^ t[k]) * 16777619u;
    }
    return h;
}

static unsigned int hl_stable(const unsigned char *r) {
    unsigned int h = fnv(2166136261u, r + 28, 4);
    h = fnv((h ^ r[28]) * 16777619u, r + 32, 25);
    h = fnv((h ^ 0xFEu) * 16777619u, r + 57, 25);
    return h ? h : 1u;
}

static unsigned int hl_identity(const unsigned char *r) {
    unsigned int h = fnv(2166136261u, r + 1, 25);
    h = ((h ^ 0xFFu) * 16777619u ^ hl_stable(r)) * 16777619u;
    return h ? h : 1u;
}

#include "head_look_store.inc"

static void villager(int i, const char *name, int sex, const char *father, const char *mother) {
    memset(g_records[i], 0, REC);
    g_records[i][0] = 1;
    lstrcpynA((char *)g_records[i] + 1, name, 25);
    g_records[i][28] = (unsigned char)sex;
    lstrcpynA((char *)g_records[i] + 32, father, 25);
    lstrcpynA((char *)g_records[i] + 57, mother, 25);
}

static void clear_village(void) {
    memset(g_records, 0, sizeof g_records);
}

/* A village of `n` founders, Ann0, Ann1, ... */
static void founders(int n, const char *stem) {
    int i;
    char name[32];
    clear_village();
    for (i = 0; i < n; ++i) {
        wsprintfA(name, "%s%d", stem, i);
        villager(i, name, i & 1, "", "");
    }
}

/* The game packs its records on a load: every held record moves down over the empty ones. */
static void pack(void) {
    int i, to = 0;
    for (i = 0; i < g_count; ++i) {
        if (g_records[i][0]) {
            if (i != to) {
                memcpy(g_records[to], g_records[i], REC);
                memset(g_records[i], 0, REC);
            }
            ++to;
        }
    }
}

/* A new session of the game: the DLL's memory is fresh, the files are what they were. */
static void new_session(void) {
    memset(g_look, 0, sizeof g_look);
    memset(g_look_id, 0, sizeof g_look_id);
    memset(g_roster, 0, sizeof g_roster);
    memset(g_stable, 0, sizeof g_stable);
    memset(&g_gate, 0, sizeof g_gate);
    g_have_roster = 0;
    g_slot = 0;
    g_foreign = 0;
    g_ticks += 10000;
}

/* A moment later in the same session. */
static void later(void) {
    g_ticks += HL_SYNC_MS + 1;
}

static int look(int i) {
    later();
    return hl_get(g_records[i]);
}

static void file_path(int slot, char *out) {
    wsprintfA(out, "%s\\Virtual Villagers Fun Patcher\\Save %d\\Data\\Head Looks\\Head Looks - Save %d.dat",
              g_root, slot, slot);
}

static DWORD read_file(const char *path, unsigned char *buf, DWORD cap) {
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    DWORD got = 0;
    if (h == INVALID_HANDLE_VALUE) {
        return 0xFFFFFFFFu;
    }
    ReadFile(h, buf, cap, &got, NULL);
    CloseHandle(h);
    return got;
}

static void write_file(const char *path, const unsigned char *buf, DWORD n) {
    HANDLE h;
    DWORD wrote;
    char folder[MAX_PATH];
    char *cut;
    lstrcpyA(folder, path);
    for (cut = folder; *cut; ++cut) {
        if (*cut == '\\') {
            *cut = '\0';
            CreateDirectoryA(folder, NULL);
            *cut = '\\';
        }
    }
    h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    WriteFile(h, buf, n, &wrote, NULL);
    CloseHandle(h);
}

static int exists(const char *path) {
    return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

/* Files in the Head Looks folder of `slot` whose name starts with `prefix` (the set-aside copies). */
static int count_files(int slot, const char *prefix) {
    char pattern[MAX_PATH];
    WIN32_FIND_DATAA found;
    HANDLE h;
    int n = 0;
    wsprintfA(pattern, "%s\\Virtual Villagers Fun Patcher\\Save %d\\Data\\Head Looks\\%s*", g_root, slot, prefix);
    h = FindFirstFileA(pattern, &found);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    do {
        ++n;
    } while (FindNextFileA(h, &found));
    FindClose(h);
    return n;
}

static void remove_tree(const char *folder) {
    char pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA found;
    HANDLE h;
    wsprintfA(pattern, "%s\\*", folder);
    h = FindFirstFileA(pattern, &found);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (lstrcmpA(found.cFileName, ".") == 0 || lstrcmpA(found.cFileName, "..") == 0) {
                continue;
            }
            wsprintfA(path, "%s\\%s", folder, found.cFileName);
            if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                remove_tree(path);
            } else {
                DeleteFileA(path);
            }
        } while (FindNextFileA(h, &found));
        FindClose(h);
    }
    RemoveDirectoryA(folder);
}

static void fresh_disk(void) {
    remove_tree(g_root);
    CreateDirectoryA(g_root, NULL);
}

int main(void) {
    char path[MAX_PATH], other[MAX_PATH];
    unsigned char buf[4096];
    DWORD got;
    unsigned int u;
    char temp[MAX_PATH];
    GetTempPathA(MAX_PATH, temp);
    wsprintfA(g_root, "%svvfp_head_look_harness_%lu", temp, GetCurrentProcessId());
    fresh_disk();

    printf("round trip\n");
    new_session();
    g_slot = 1;
    founders(10, "Kai");
    check(look(2) == 0 && look(3) == 0, "every villager starts Auto");
    check(hl_set(g_records[2], 1) == 1 && hl_set(g_records[3], 2) == 1, "Young and Old are kept");
    check(look(2) == 1 && look(3) == 2 && look(4) == 0, "the table says so");
    file_path(1, path);
    got = read_file(path, buf, sizeof buf);
    check(got == 12 + 150 * 5, "the file is 12 + 150 * 5 bytes, in the save's own Data\\Head Looks folder");
    memcpy(&u, buf, 4);
    check(u == 0x314C4856u, "magic 'VHL1'");
    memcpy(&u, buf + 4, 4);
    check(u == 5, "the game");
    memcpy(&u, buf + 8, 4);
    check(u == 150, "the record count");
    check(buf[12 + 150 * 4 + 2] == 1 && buf[12 + 150 * 4 + 3] == 2 && buf[12 + 150 * 4 + 4] == 0,
          "each record's look after the roster");
    memcpy(&u, buf + 12 + 3 * 4, 4);
    check(u == hl_identity(g_records[3]), "each record's identity in the roster");
    new_session();
    g_slot = 1;
    check(look(2) == 1 && look(3) == 2 && look(5) == 0, "a new session reads the looks back");
    check(hl_set(g_records[2], 0) == 1 && look(2) == 0, "Auto again");

    printf("following the villager\n");
    /* Kai3 (Old) is behind Kai1, who dies; the save is reloaded packed: Kai3 is now in record 2. */
    hl_set(g_records[3], 2);
    hl_set(g_records[7], 1);
    g_records[1][0] = 0;
    later();
    (void)look(0);
    check(look(3) == 2, "a death in play moves nobody: Kai3 keeps Old in record 3");
    new_session();
    g_slot = 1;
    pack();
    check(lstrcmpA((char *)g_records[2] + 1, "Kai3") == 0, "(the reload packed Kai3 into record 2)");
    check(look(2) == 2 && look(3) == 0, "after the reload the look is on Kai3 in record 2, and nobody else's");
    check(look(6) == 1 && look(7) == 0, "Kai7 (now record 6) keeps Young");
    got = read_file(path, buf, sizeof buf);
    check(buf[12 + 150 * 4 + 2] == 2 && buf[12 + 150 * 4 + 3] == 0, "the moved table is written back at once");

    printf("record reuse and bodies\n");
    /* Kai3 (record 2, Old) dies: a body not buried keeps the record held; the look stays. */
    later();
    (void)look(0);
    g_records[2][0] = 0;                      /* buried: the record is free */
    later();
    (void)look(0);
    check(g_look[2] == 2, "an empty record keeps the dead villager's look while nobody takes it");
    villager(2, "Baby", 1, "Kai0", "Kai4");     /* a newborn in the same record */
    check(look(2) == 0, "a newborn in a dead villager's record never inherits the look");
    check(g_look[2] == 0, "and the look is dropped");

    printf("rename\n");
    hl_set(g_records[4], 2);
    later();
    lstrcpyA((char *)g_records[4] + 1, "Renamed");
    check(look(4) == 2, "a renamed villager keeps the look");
    new_session();
    g_slot = 1;
    check(look(4) == 2, "...and after a reload, under the new name");

    printf("copied and restored saves\n");
    /* The village's file copied to slot 2 (a save copied with its folder): the looks are read there. */
    file_path(2, other);
    got = read_file(path, buf, sizeof buf);
    write_file(other, buf, got);
    new_session();
    g_slot = 2;
    check(look(4) == 2 && look(6) == 1, "a copy in another slot follows the same villagers");
    /* Restored to an older copy: whatever that copy says. */
    hl_set(g_records[6], 2);
    write_file(other, buf, got);
    new_session();
    g_slot = 2;
    check(look(6) == 1, "a restored file is read as it was backed up");

    printf("another village's file\n");
    new_session();
    g_slot = 2;
    founders(8, "Zed");                        /* another village in slot 2 */
    check(look(1) == 0, "another village's file gives no looks");
    later();
    (void)look(0);
    got = read_file(other, buf, sizeof buf);
    check(got == 12 + 150 * 5 && buf[12 + 150 * 4 + 6] == 1, "and is never replaced while nothing is chosen");
    check(hl_set(g_records[1], 2) == 1, "the first look chosen there is kept");
    check(count_files(2, "Head Looks - Save 2.dat.another-village-") == 1, "after the other file was moved aside");
    got = read_file(other, buf, sizeof buf);
    check(got == 12 + 150 * 5 && buf[12 + 150 * 4 + 1] == 2, "the new file is this village's");

    printf("broken files\n");
    {
        static const struct { const char *what; int len; int magic; int game; int count; } BAD[] = {
            { "a short file", 11, 0x314C4856, 5, 150 },
            { "a file of the wrong size", 12 + 150 * 5 - 1, 0x314C4856, 5, 150 },
            { "the wrong magic", 12 + 150 * 5, 0x314C4857, 5, 150 },
            { "another game's file", 12 + 150 * 5, 0x314C4856, 4, 150 },
            { "an unknown record count", 12 + 151 * 5, 0x314C4856, 5, 151 },
        };
        int k;
        for (k = 0; k < (int)(sizeof BAD / sizeof BAD[0]); ++k) {
            fresh_disk();
            new_session();
            g_slot = 3;
            founders(6, "Lea");
            memset(buf, 0, sizeof buf);
            memcpy(buf, &BAD[k].magic, 4);
            memcpy(buf + 4, &BAD[k].game, 4);
            memcpy(buf + 8, &BAD[k].count, 4);
            for (u = 0; u < 6; ++u) {
                unsigned int id = hl_identity(g_records[u]);
                memcpy(buf + 12 + u * 4, &id, 4);
                buf[12 + 150 * 4 + u] = 2;
            }
            file_path(3, path);
            write_file(path, buf, (DWORD)BAD[k].len);
            check(look(2) == 0, BAD[k].what);
            check(!exists(path) && count_files(3, "Head Looks - Save 3.dat.unreadable-") == 1,
                  "...is set aside intact, never overwritten");
        }
        fresh_disk();
        new_session();
        g_slot = 3;
        founders(6, "Lea");
        check(look(1) == 0, "a missing file: every look Auto");
        hl_set(g_records[1], 2);
        got = read_file(path, buf, sizeof buf);
        buf[12 + 150 * 4 + 1] = 7;
        write_file(path, buf, got);
        new_session();
        g_slot = 3;
        check(look(1) == 0, "a value above 2 reads as Auto");
    }

    printf("Start Over\n");
    fresh_disk();
    new_session();
    g_slot = 4;
    founders(12, "Old");
    hl_set(g_records[5], 2);
    file_path(4, path);
    check(exists(path), "(the slot has its file)");
    vv_reset_slot_state(5, 4, "Village: Test (Save 4)\n");
    check(!exists(path), "Start Over deletes the slot's Head Looks file");
    founders(5, "New");
    check(look(0) == 0 && look(5) == 0, "the new village's looks are all Auto");
    later();
    (void)look(1);
    check(!exists(path), "and the erased village's looks are never written back");

    printf("a failed write\n");
    fresh_disk();
    new_session();
    g_slot = 1;
    founders(4, "Ike");
    hl_set(g_records[1], 1);
    g_fail_writes = 1;
    check(hl_set(g_records[1], 2) == 0, "a set that cannot be written reports so");
    check(look(1) == 1, "and changes nothing");
    g_fail_writes = 0;

    printf("many at once (Change Appearance for All)\n");
    {
        const unsigned char *many[3];
        int looks[3];
        many[0] = g_records[0]; many[1] = g_records[2]; many[2] = g_records[3];
        looks[0] = 2; looks[1] = 1; looks[2] = 2;
        check(hl_set_many(many, looks, 3) == 1, "three looks kept in one write");
        check(look(0) == 2 && look(1) == 1 && look(2) == 1 && look(3) == 2, "each villager has its own look");
        new_session();
        g_slot = 1;
        check(look(0) == 2 && look(2) == 1 && look(3) == 2, "and the file says so");
        looks[0] = 0; looks[1] = 2; looks[2] = 1;
        g_fail_writes = 1;
        check(hl_set_many(many, looks, 3) == 0, "a batch that cannot be written reports so");
        check(look(0) == 2 && look(2) == 1 && look(3) == 2, "and every look is as it was");
        g_fail_writes = 0;
        looks[2] = 3;
        check(hl_set_many(many, looks, 3) == 0 && look(0) == 2 && look(2) == 1, "a look above 2 changes nobody");
        g_records[2][0] = 0;
        looks[2] = 1;
        check(hl_set_many(many, looks, 3) == 0 && look(0) == 2, "a record nobody holds changes nobody");
        g_records[2][0] = 1;
    }

    printf("no village\n");
    new_session();
    g_slot = 0;
    check(hl_set(g_records[1], 2) == 0 && look(1) == 0, "no slot: nothing is kept or read");
    g_slot = 1;
    clear_village();
    check(hl_set(g_records[1], 2) == 0, "nobody in the records: nothing is kept");

    printf("256 records\n");
    fresh_disk();
    new_session();
    g_count = 256;
    g_slot = 5;
    founders(200, "Big");
    hl_set(g_records[199], 2);
    file_path(5, path);
    check(read_file(path, buf, sizeof buf) == 12 + 256 * 5, "a 256-record build writes 256 entries");
    new_session();
    g_slot = 5;
    check(look(199) == 2, "and reads them back");

    remove_tree(g_root);
    printf("failures: %d\n", failures);
    return failures;
}
