/* Exercise the custom titles' .dat file against real files on disk.
 *
 * The companion's own title store (story_titles.inc) and the Start Over
 * reset (native/shared/save_reset.c) are compiled here unchanged; only what
 * they ask of the game is replaced: the save slot, a village of named
 * records, and the save folder -- which is a fresh folder under %TEMP%, never
 * the player's Documents\LDW.
 *
 * Proves: a title is published to "<save folder>\Virtual Villagers Fun
 * Patcher Data\Custom Titles\Custom Titles - Save N.dat" in the documented
 * format; it is read back by a fresh table (a new session) and shown only
 * for the villager whose name it was set for; each slot has its own file;
 * an invalid file is set aside, never overwritten; the reset deletes the
 * slot's file in every game and leaves other slots; a file deleted behind
 * the table's back (Start Over) is never written back; a villager who dies
 * or whose record is reused loses the title.
 *
 * Built and run by scripts/build_custom_titles_harness.ps1 (32-bit, like the
 * companion).  Exit code 0 when every check passes. */
#include <stdio.h>
#include <windows.h>
#include <string.h>

/* A write that fails on demand (sidecar_io.h's write hook). */
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

#include "../shared/save_folder.h"
#include "../shared/save_reset.h"
#include "../shared/custom_titles.h"
#include "../shared/sidecar_io.h"

static int failures = 0;
static char g_root[MAX_PATH];

static void check(int condition, const char *what) {
    printf("  [%s] %s\n", condition ? "PASS" : "FAIL", what);
    if (!condition) {
        ++failures;
    }
}

/* ---- the save folder: %TEMP%\vvfp_titles_harness_<pid> ------------------ */

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

/* ---- the game: a slot and a village of named records -------------------- */

#define RECORDS 8
#define NAME_BYTES 25
static unsigned char g_records[RECORDS][64];   /* [0] alive, [1..25] name */
static int g_slot = 1;

static int story_current_slot(int game) {
    (void)game;
    return g_slot;
}

static int story_record_count(int game) {
    (void)game;
    return RECORDS;
}

static unsigned char *story_record(int game, int index) {
    (void)game;
    return index >= 0 && index < RECORDS ? g_records[index] : NULL;
}

static int story_record_index(int game, const unsigned char *record) {
    int i;
    (void)game;
    for (i = 0; i < RECORDS; ++i) {
        if (record == g_records[i]) {
            return i;
        }
    }
    return -1;
}

static int story_record_present(int game, const unsigned char *record) {
    (void)game;
    return record[0] != 0;
}

static unsigned int story_title_identity(int game, const unsigned char *record) {
    (void)game;
    return vv_title_fingerprint(record + 1, NAME_BYTES);
}

static void villager(int index, const char *name) {
    memset(g_records[index], 0, sizeof g_records[index]);
    g_records[index][0] = 1;
    lstrcpynA((char *)g_records[index] + 1, name, NAME_BYTES);
}

#include "story_titles.inc"

/* ---- helpers ------------------------------------------------------------ */

static int file_exists(const char *path) {
    return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

static long file_size(const char *path) {
    WIN32_FILE_ATTRIBUTE_DATA info;
    if (!GetFileAttributesExA(path, GetFileExInfoStandard, &info)) {
        return -1;
    }
    return (long)info.nFileSizeLow;
}

static void titles_path(int slot, char *out) {
    wsprintfA(out, "%s\\Virtual Villagers Fun Patcher Data\\Custom Titles\\Custom Titles - Save %d.dat",
              g_root, slot);
}

/* A new session: the table starts empty and loads from disk. */
static void new_session(void) {
    memset(&titles, 0, sizeof titles);
}

static void write_bytes(const char *path, const void *data, DWORD size) {
    HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD written = 0;
    if (h != INVALID_HANDLE_VALUE) {
        WriteFile(h, data, size, &written, NULL);
        CloseHandle(h);
    }
}

int main(void) {
    char path1[MAX_PATH];
    char path2[MAX_PATH];
    const char *seen;
    int game;
    unsigned char raw[64];
    HANDLE h;
    DWORD got = 0;

    wsprintfA(g_root, "%s", "");
    GetTempPathA(MAX_PATH, g_root);
    wsprintfA(g_root + lstrlenA(g_root), "vvfp_titles_harness_%lu", GetCurrentProcessId());
    CreateDirectoryA(g_root, NULL);
    printf("save folder: %s\n\n", g_root);
    titles_path(1, path1);
    titles_path(2, path2);

    villager(0, "Hina");
    villager(1, "Kai");
    villager(2, "Lani");

    /* -- set, publish, the documented format ---------------------------- */
    check(titles_set(3, 1, "Master Storyteller") == 1, "a title is set and published");
    check(file_exists(path1), "CUSTOM TITLES FILE PUBLISHED BESIDE THE SAVES");
    check(file_size(path1) == 16 + 40, "the file is the header plus one 40-byte entry");
    h = CreateFileA(path1, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    ReadFile(h, raw, sizeof raw, &got, NULL);
    CloseHandle(h);
    check(got == 56 && memcmp(raw, "VCT1", 4) == 0 && raw[8] == 3 && raw[12] == 1 && raw[16] == 1,
          "magic 'VCT1', game 3, one entry, record index 1");
    check(lstrcmpA((const char *)raw + 24, "Master Storyteller") == 0, "the title text is stored");
    check(!vv_title_valid("") && !vv_title_valid("   ") && vv_title_valid("Chief"),
          "an empty or all-space title is refused");
    check(titles_set(3, 2, "This title is far too long to be shown") == 0, "a title over 31 characters is refused");

    /* -- read back in a new session, only for that villager -------------- */
    new_session();
    seen = titles_lookup(3, g_records[1]);
    check(seen != NULL && lstrcmpA(seen, "Master Storyteller") == 0,
          "A NEW SESSION READS THE TITLE BACK FROM THE .DAT");
    check(titles_lookup(3, g_records[0]) == NULL, "another villager has no title");
    villager(1, "Kalani");                       /* a birth reused record 1 */
    check(titles_lookup(3, g_records[1]) == NULL, "A REUSED RECORD NEVER INHERITS THE TITLE");
    villager(1, "Kai");

    /* -- each slot its own file ------------------------------------------ */
    g_slot = 2;
    check(titles_lookup(3, g_records[1]) == NULL, "slot 2 does not see slot 1's titles");
    check(titles_set(3, 0, "Healer of Slot Two") == 1 && file_exists(path2), "slot 2 publishes its own file");
    g_slot = 1;
    seen = titles_lookup(3, g_records[1]);
    check(seen != NULL && lstrcmpA(seen, "Master Storyteller") == 0, "back on slot 1, slot 1's titles");
    check(titles_lookup(3, g_records[0]) == NULL, "and not slot 2's");

    /* -- the villager dies: the title goes ------------------------------- */
    titles_tick(3);                              /* seen alive this session */
    check(titles.count == 1, "a living villager keeps the title through the sweep");
    g_records[1][0] = 0;
    titles.checked_at = GetTickCount();
    titles_tick(3);
    check(titles.count == 0, "A VILLAGER WHO DIES LOSES THE TITLE");
    check(file_size(path1) == 16, "and the file is rewritten without it");
    g_records[1][0] = 1;

    /* -- an invalid file is set aside, never overwritten ----------------- */
    new_session();
    write_bytes(path1, "garbage", 7);
    check(titles_lookup(3, g_records[0]) == NULL, "an invalid file shows no titles");
    check(titles.loaded == 1 && titles.count == 0, "it loads as empty");
    {
        WIN32_FIND_DATAA found;
        char pattern[MAX_PATH];
        HANDLE f;
        wsprintfA(pattern, "%s.unreadable-*", path1);
        f = FindFirstFileA(pattern, &found);
        check(f != INVALID_HANDLE_VALUE, "THE INVALID FILE IS MOVED ASIDE, NOT OVERWRITTEN");
        if (f != INVALID_HANDLE_VALUE) {
            FindClose(f);
        }
    }

    /* -- a write that fails leaves the table as it was ------------------- */
    new_session();
    g_slot = 1;
    DeleteFileA(path1);
    check(titles_set(3, 1, "Kept Title") == 1, "a title published before the failing writes");
    g_fail_writes = 1;
    check(titles_set(3, 1, "Changed") == 0, "a change that can not be written is refused");
    seen = titles_lookup(3, g_records[1]);
    check(seen != NULL && lstrcmpA(seen, "Kept Title") == 0,
          "A FAILED WRITE LEAVES THE CHANGED TITLE AS IT WAS IN MEMORY");
    check(titles_set(3, 2, "Added") == 0 && titles.count == 1 && titles_lookup(3, g_records[2]) == NULL,
          "A FAILED WRITE ADDS NO TITLE IN MEMORY");
    check(titles_set(3, 1, NULL) == 0 && titles_lookup(3, g_records[1]) != NULL,
          "A FAILED WRITE REMOVES NO TITLE IN MEMORY");
    g_fail_writes = 0;
    check(titles_set(3, 0, "Later") == 1 && file_size(path1) == 16 + 80,
          "the next write holds only the changes that were made");
    new_session();
    seen = titles_lookup(3, g_records[1]);
    check(seen != NULL && lstrcmpA(seen, "Kept Title") == 0 && titles_lookup(3, g_records[2]) == NULL,
          "and the file agrees with what memory showed");
    DeleteFileA(path1);

    /* -- Start Over: the reset deletes the slot's file, every game ------- */
    for (game = 1; game <= 5; ++game) {
        char what[96];
        new_session();
        g_slot = 1;
        check(titles_set(game, 0, "Founder") == 1, "a title published before Start Over");
        g_slot = 2;
        titles_set(game, 0, "Other Slot");
        g_slot = 1;
        check(titles_lookup(game, g_records[0]) != NULL, "slot 1's title shown before Start Over");
        vv_reset_slot_state(game, 1, "Village: Test (Save 1)\n");
        wsprintfA(what, "START OVER DELETES SLOT 1'S TITLES (game %d)", game);
        check(!file_exists(path1), what);
        wsprintfA(what, "slot 2's titles survive (game %d)", game);
        check(file_exists(path2), what);
        /* The table still holds the old village's title in memory: the tick
           notices the file is gone and forgets it, without writing it back,
           and a new village's founder in the same record is not given it. */
        titles.checked_at = GetTickCount() - 3 * TITLES_CHECK_MS;
        titles_tick(game);
        check(titles.count == 0, "THE OLD VILLAGE'S TITLES ARE FORGOTTEN AFTER START OVER");
        check(!file_exists(path1), "THE DELETED FILE IS NOT WRITTEN BACK");
        check(titles_lookup(game, g_records[0]) == NULL, "the new village is not shown the old title");
        /* A title set in the new village starts the file afresh. */
        check(titles_set(game, 1, "New Village") == 1 && file_size(path1) == 16 + 40,
              "a new village's first title is the file's only entry");
        /* And a reset nobody ticked through: the write notices it too. */
        vv_reset_slot_state(game, 1, "Village: Test (Save 1)\n");
        check(titles_set(game, 2, "Second Start") == 1 && file_size(path1) == 16 + 40,
              "AFTER AN UNTICKED START OVER ONLY THE NEW TITLE IS WRITTEN");
    }

    printf("\n%d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}
