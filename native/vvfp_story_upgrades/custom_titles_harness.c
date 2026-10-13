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

#include "identity_in_place.h"

/* ---- the game: a slot and a village of named records -------------------- */

#define RECORDS 8
#define NAME_BYTES 25
static unsigned char g_records[RECORDS][96];   /* [0] alive, [1..25] name; looks from [48] */
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

/* The identity: the name, and byte [44] standing for the likes and dislikes
   (vv_title_identity hashes those too; 0 in every villager() unless a case
   changes them -- as an island event does). */
static unsigned int story_title_identity(int game, const unsigned char *record) {
    unsigned int h = vv_title_fingerprint(record + 1, NAME_BYTES);
    (void)game;
    h = (h ^ record[44]) * 16777619u;
    return h ? h : 1u;
}

/* What a rename leaves alone: byte [40] stands for the sex, and [44] the
   likes and dislikes (0 in every villager() unless a case sets it). */
static unsigned int story_title_stable(int game, const unsigned char *record) {
    (void)game;
    return 1u + record[40] + 256u * record[44];
}

/* What a likes / dislikes change leaves alone: the name and the sex
   (dword [48]); and the age (int [52]). */
static unsigned int story_title_keep(int game, const unsigned char *record) {
    (void)game;
    return vv_identity_keep(record, 1u, NAME_BYTES, 48u);
}

static int story_title_age(int game, const unsigned char *record) {
    (void)game;
    return *(const int *)(record + 52);
}

/* The looks a title is kept by (story_title_looks): the sex dword [48], the
   age [52], head [56] and body [60], and six int skills from [64]. */
static void story_title_looks(int game, const unsigned char *record, vv_title_looks *out) {
    int k;
    (void)game;
    memset(out, 0, sizeof *out);
    out->sex = *(const int *)(record + 48);
    out->age = *(const int *)(record + 52);
    out->head = *(const int *)(record + 56);
    out->body = *(const int *)(record + 60);
    for (k = 0; k < VV_TITLE_SKILLS; ++k) {
        out->skills[k] = *(const unsigned int *)(record + 64 + 4 * k);
    }
}

static int g_skills_float;          /* 1: the skills are floats (The Tree of Life, New Believers) */

static int story_title_skills_float(int game) {
    (void)game;
    return g_skills_float;
}

/* A skill dword for the value `v`: the int itself, or the float's bits. */
static unsigned int skill_dword(int v) {
    float f = (float)v;
    unsigned int bits;
    if (!g_skills_float) {
        return (unsigned int)v;
    }
    memcpy(&bits, &f, sizeof bits);
    return bits;
}

static void set_skill(int index, int skill, int v) {
    *(unsigned int *)(g_records[index] + 64 + 4 * skill) = skill_dword(v);
}

/* Set a villager's looks: sex, age, head, body, and every skill to `skill`. */
static void looks(int index, int sex, int age, int head, int body, int skill) {
    int k;
    *(int *)(g_records[index] + 48) = sex;
    *(int *)(g_records[index] + 52) = age;
    *(int *)(g_records[index] + 56) = head;
    *(int *)(g_records[index] + 60) = body;
    for (k = 0; k < VV_TITLE_SKILLS; ++k) {
        *(int *)(g_records[index] + 64 + 4 * k) = skill;
    }
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
    _snprintf_s(out, MAX_PATH, _TRUNCATE,
                "%s\\Virtual Villagers Fun Patcher Data\\Custom Titles\\Custom Titles - Save %d.dat", g_root, slot);
}

/* A new session: the table starts empty and loads from disk. */
static void new_session(void) {
    memset(&titles, 0, sizeof titles);
}

/* The record of the entry with this title, VV_TITLE_PENDING (as -1), or -2: none. */
static int title_index(const char *title) {
    int k;
    for (k = 0; k < titles.count; ++k) {
        if (lstrcmpA(titles.entries[k].title, title) == 0) {
            return (int)titles.entries[k].index;
        }
    }
    return -2;
}

/* What the harness needs under %TEMP% (GetTempPath ends in a backslash): the root
   "vvfp_titles_harness_<pid>" (20 + at most 10 characters), then the longest file under it,
   "\Virtual Villagers Fun Patcher Data\Custom Titles\Custom Titles - Save 1.dat" (76), its
   ".unreadable-*" set-aside pattern (13), and 16 for the temporary names the atomic publish makes. */
#define HARNESS_PATH_NEED (20 + 10 + 76 + 13 + 16)

/* The save folder root: <GetTempPath>\vvfp_titles_harness_<pid>.  A %TEMP% so long that the files under
   it would pass MAX_PATH makes the harness say so and stop, instead of failing every check on a path
   that does not fit (review of 3f176ddd).  It does not rely on 8.3 short names (a volume may have them
   off): the build script keeps its own folder name short instead. */
static int make_root(void) {
    char temp[MAX_PATH];
    DWORD n = GetTempPathA(MAX_PATH, temp);
    if (n == 0 || n >= MAX_PATH) {
        printf("%%TEMP%% is unreadable or longer than MAX_PATH: the harness cannot run\n");
        return 0;
    }
    if (n + HARNESS_PATH_NEED >= MAX_PATH) {
        printf("%%TEMP%% (%s, %lu characters) is too long for the files under it to fit MAX_PATH:"
               " the harness cannot run\n", temp, (unsigned long)n);
        return 0;
    }
    _snprintf_s(g_root, MAX_PATH, _TRUNCATE, "%svvfp_titles_harness_%lu", temp, GetCurrentProcessId());
    return CreateDirectoryA(g_root, NULL) || GetLastError() == ERROR_ALREADY_EXISTS;
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
    unsigned char raw[128];
    HANDLE h;
    DWORD got = 0;

    if (!make_root()) {
        printf("\n1 failure(s)\n");
        return 2;
    }
    printf("save folder: %s\n\n", g_root);
    titles_path(1, path1);
    titles_path(2, path2);

    villager(0, "Hina");
    villager(1, "Kai");
    villager(2, "Lani");

    /* -- set, publish, the documented format ---------------------------- */
    check(titles_set(3, 1, "Master Storyteller") == 1, "a title is set and published");
    check(file_exists(path1), "CUSTOM TITLES FILE PUBLISHED BESIDE THE SAVES");
    check(file_size(path1) == 16 + 84, "the file is the header plus one 84-byte entry");
    h = CreateFileA(path1, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    ReadFile(h, raw, sizeof raw, &got, NULL);
    CloseHandle(h);
    check(got == 100 && memcmp(raw, "VCT1", 4) == 0 && raw[4] == 3 && raw[8] == 3 && raw[12] == 1
          && raw[16] == 1 && raw[24] == VV_TITLE_KNOWN,
          "magic 'VCT1', version 3, game 3, one entry, record index 1, its looks known");
    check(lstrcmpA((const char *)raw + 16 + 52, "Master Storyteller") == 0, "the title text is stored");
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
    g_records[1][40] = 5;                        /* ...a newborn with likes of her own */
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
        _snprintf_s(pattern, MAX_PATH, _TRUNCATE, "%s.unreadable-*", path1);
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
    check(titles_set(3, 0, "Later") == 1 && file_size(path1) == 16 + 2 * 84,
          "the next write holds only the changes that were made");
    new_session();
    seen = titles_lookup(3, g_records[1]);
    check(seen != NULL && lstrcmpA(seen, "Kept Title") == 0 && titles_lookup(3, g_records[2]) == NULL,
          "and the file agrees with what memory showed");
    DeleteFileA(path1);

    /* -- a reload renumbers the villagers: the titles follow them --------
       The games load a save packed into records 0, 1, 2, ...: Hina [0] dies,
       and after the reload Kai, Lani and Moku are each one record lower. */
    new_session();
    g_slot = 1;
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Hina"); villager(1, "Kai"); villager(2, "Lani"); villager(3, "Moku");
    check(titles_set(3, 0, "Matriarch") == 1 && titles_set(3, 1, "Kai Title") == 1
          && titles_set(3, 3, "Moku Title") == 1, "setup: Hina, Kai and Moku have titles");
    new_session();
    memset(g_records, 0, sizeof g_records);
    villager(0, "Kai"); villager(1, "Lani"); villager(2, "Moku");
    titles_tick(3);
    seen = titles_lookup(3, g_records[0]);
    check(seen != NULL && lstrcmpA(seen, "Kai Title") == 0, "AFTER A RELOAD KAI [1 -> 0] KEEPS HIS TITLE");
    seen = titles_lookup(3, g_records[2]);
    check(seen != NULL && lstrcmpA(seen, "Moku Title") == 0, "... and Moku [3 -> 2] keeps hers");
    check(titles_lookup(3, g_records[1]) == NULL, "... Lani, now in Kai's old record, is given nothing");
    check(titles.count == 3 && title_index("Matriarch") == (int)VV_TITLE_PENDING,
          "... and the dead Hina's title waits PENDING, shown on nobody: a load never drops a title");
    new_session();
    seen = titles_lookup(3, g_records[0]);
    check(seen != NULL && lstrcmpA(seen, "Kai Title") == 0 && file_size(path1) == 16 + 3 * 84,
          "THE FOLLOWED TITLES ARE WRITTEN BACK: a new session reads them at their new records");
    /* The same within one session (a reload without leaving the game): the
       sweep must not take a villager who merely moved for one who died. */
    titles_tick(3);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(1, "Moku"); villager(2, "Kai");
    titles_tick(3);
    seen = titles_lookup(3, g_records[2]);
    check(seen != NULL && lstrcmpA(seen, "Kai Title") == 0 && titles.count == 3,
          "A VILLAGER WHO MOVED IN THIS SESSION IS NOT SWEPT AWAY AS DEAD");

    /* -- THE OWNER'S BUG (v1.35.70): a title dropped as ambiguous ---------
       A titled Kai and an identical-looking namesake (the same name, likes,
       dislikes, head, body and sex) after a reload.  Either could be him: the
       title was dropped once and for all.  It is kept PENDING now: shown on
       neither, still in the file, and bound again by the WHOLE identity
       once only one villager can be him. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(1, "Kai");
    looks(1, 1, 500, 3, 4, 20);
    titles_tick(3);
    check(titles_set(3, 1, "Kai Title") == 1, "setup: Kai [1], age 500, has a title");
    new_session();
    memset(g_records, 0, sizeof g_records);
    villager(0, "Kai"); looks(0, 1, 520, 3, 4, 20);             /* the titled Kai, a little older */
    villager(1, "Moku");
    villager(3, "Kai"); looks(3, 1, 600, 3, 4, 30);             /* a namesake who could be him */
    titles_tick(3);
    titles_tick(3);
    check(titles_lookup(3, g_records[0]) == NULL && titles_lookup(3, g_records[3]) == NULL,
          "AN IDENTICAL-LOOKING NAMESAKE AFTER A RELOAD: THE TITLE IS KEPT PENDING, SHOWN ON NEITHER");
    check(titles.count == 1 && title_index("Kai Title") == (int)VV_TITLE_PENDING,
          "... the entry is kept, pending -- never dropped");
    new_session();
    titles_sync(3);                              /* the file as written */
    check(titles.loaded && titles.count == 1 && titles.entries[0].index == VV_TITLE_PENDING
          && (titles.entries[0].flags & VV_TITLE_KNOWN) && titles.entries[0].looks.age == 500
          && titles.entries[0].looks.head == 3 && titles.entries[0].looks.skills[0] == 20,
          "THE FILE STILL HOLDS THE PENDING TITLE, WITH THE WHOLE IDENTITY IT WAS KEPT BY");
    check(titles.entries[0].flags & VV_TITLE_CONTESTED,
          "TWO COULD BE HIM AT ONCE: THE PENDING TITLE IS MARKED CONTESTED IN THE FILE");
    /* NEVER A GUESS (the owner): the namesake dies, and the one Kai left is
       not taken for the titled one -- which of the two died can not be told.
       The title waits for the player (the reconciliation names the Kai left
       as the one who could be him). */
    titles_tick(3);
    g_records[3][0] = 0;
    titles.checked_at = GetTickCount() - 3 * TITLES_CHECK_MS;
    titles_tick(3);
    titles_tick(3);
    check(titles_lookup(3, g_records[0]) == NULL && titles.count == 1
          && title_index("Kai Title") == (int)VV_TITLE_PENDING,
          "THE NAMESAKE DIES: THE ONE KAI LEFT IS NOT GIVEN THE CONTESTED TITLE -- IT WAITS FOR THE PLAYER");
    /* ...nor after the next load, with the namesake gone from the save. */
    new_session();
    memset(g_records, 0, sizeof g_records);
    villager(0, "Kai"); looks(0, 1, 540, 3, 4, 20);
    villager(1, "Moku");
    titles_tick(3);
    titles.checked_at = GetTickCount() - 3 * TITLES_CHECK_MS;
    titles_tick(3);
    check(titles_lookup(3, g_records[0]) == NULL && titles.count == 1
          && title_index("Kai Title") == (int)VV_TITLE_PENDING
          && (titles.entries[0].flags & VV_TITLE_CONTESTED),
          "... NOR AFTER A RELOAD WITH ONE KAI LEFT: STILL PENDING AND CONTESTED");
    /* ...nor when the namesake changes (new likes) and so stops matching. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20);
    titles_tick(3);
    titles_set(3, 1, "Kai Title");
    new_session();
    memset(g_records, 0, sizeof g_records);
    villager(0, "Kai"); looks(0, 1, 520, 3, 4, 20);
    villager(3, "Kai"); looks(3, 1, 600, 3, 4, 30);
    titles_tick(3);
    check(title_index("Kai Title") == (int)VV_TITLE_PENDING, "setup: the title is pending between two Kais");
    g_records[3][44] = 6;                                        /* the namesake's likes change */
    titles_tick(3);
    check(titles_lookup(3, g_records[0]) == NULL && titles_lookup(3, g_records[3]) == NULL
          && title_index("Kai Title") == (int)VV_TITLE_PENDING,
          "THE NAMESAKE'S LIKES CHANGE: THE CONTESTED TITLE STILL WAITS, GIVEN TO NEITHER");
    /* A pending title that was never contested -- only a namesake who is
       not him was there -- binds by itself once exactly one villager has his
       whole identity. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20);
    titles_tick(3);
    titles_set(3, 1, "Kai Title");
    new_session();
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani");
    villager(1, "Kai"); looks(1, 1, 400, 3, 4, 20);             /* younger: not him */
    titles_tick(3);
    titles_tick(3);
    check(title_index("Kai Title") == (int)VV_TITLE_PENDING && !(titles.entries[0].flags & VV_TITLE_CONTESTED),
          "setup: pending, never contested (nobody could be him)");
    new_session();
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani");
    villager(2, "Kai"); looks(2, 1, 530, 3, 4, 25);             /* the titled Kai is back */
    titles_tick(3);
    seen = titles_lookup(3, g_records[2]);
    check(seen != NULL && lstrcmpA(seen, "Kai Title") == 0,
          "A NEVER-CONTESTED PENDING TITLE BINDS AGAIN WHEN EXACTLY ONE VILLAGER HAS THE WHOLE IDENTITY");

    /* A LOAD IS NEVER A DEATH: Kai is renamed in this session (the title
       follows the new name), then the village is reloaded without a save --
       the save still has "Kai", and the records are packed differently.
       Nobody carries the new name now: the title waits pending, never
       dropped as if he had died. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Hina"); villager(1, "Lani"); villager(2, "Kai"); looks(2, 1, 500, 3, 4, 20);
    titles_tick(3);
    check(titles_set(3, 2, "Kai Title") == 1, "setup: Kai [2] has a title");
    titles_tick(3);
    lstrcpynA((char *)g_records[2] + 1, "Kaimana", NAME_BYTES);  /* renamed in session */
    titles_tick(3);
    check(titles_lookup(3, g_records[2]) != NULL, "setup: the renamed Kaimana keeps the title");
    memset(g_records, 0, sizeof g_records);                     /* reloaded without a save: Hina's body gone */
    villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20);
    titles_tick(3);
    titles.checked_at = GetTickCount() - 3 * TITLES_CHECK_MS;
    titles_tick(3);
    check(titles.count == 1 && title_index("Kai Title") == (int)VV_TITLE_PENDING,
          "A TITLE WHOSE VILLAGER WAS RENAMED AND THEN RELOADED WITHOUT A SAVE WAITS PENDING, NEVER DROPPED");

    /* A CORRUPTED SKILL RESET IS NOT A LOWER SKILL: Kai's title was set
       while a skill held 150 (no game can hold it); the corrupted-skill
       reset made it 100.  After a load he is still him. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 150);
    titles_tick(3);
    check(titles_set(3, 1, "Kai Title") == 1, "setup: Kai [1], a skill at a corrupted 150, has a title");
    check(titles.entries[0].looks.skills[0] == 100, "THE STORED SKILL IS THE ONE THE CORRUPTED-SKILL RESET LEAVES (100)");
    new_session();
    memset(g_records, 0, sizeof g_records);
    villager(0, "Kai"); looks(0, 1, 510, 3, 4, 100);           /* reset to 100, and packed to [0] */
    villager(1, "Lani");
    titles_tick(3);
    seen = titles_lookup(3, g_records[0]);
    check(seen != NULL && lstrcmpA(seen, "Kai Title") == 0,
          "A CORRUPTED SKILL RESET (150 -> 100) DOES NOT STOP THE TITLE FOLLOWING ITS VILLAGER");
    /* ...and a negative corrupted skill reset to 0 likewise. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20);
    *(int *)(g_records[1] + 64) = -7;
    titles_tick(3);
    titles_set(3, 1, "Kai Title");
    new_session();
    memset(g_records, 0, sizeof g_records);
    villager(0, "Kai"); looks(0, 1, 510, 3, 4, 20);
    *(int *)(g_records[0] + 64) = 0;                            /* reset to 0 */
    villager(1, "Lani");
    titles_tick(3);
    seen = titles_lookup(3, g_records[0]);
    check(seen != NULL && lstrcmpA(seen, "Kai Title") == 0,
          "A CORRUPTED SKILL RESET (-7 -> 0) DOES NOT STOP THE TITLE FOLLOWING ITS VILLAGER");
    /* The titled Kai died before the reload and the namesake left is NOT
       him by the whole identity: younger, less skilled, or the other sex.
       (The old follow moved the title to the one carrier of the name and
       likes -- the wrong villager.) */
    {
        static const struct { int sex, age, skill; const char *what; } wrong[] = {
            { 1, 400, 30, "THE TITLED KAI GONE, A YOUNGER NAMESAKE IS NOT GIVEN THE TITLE: IT STAYS PENDING" },
            { 1, 600, 10, "... nor a namesake with a lower skill" },
            { 2, 600, 30, "... nor a namesake of the other sex" },
        };
        int w;
        for (w = 0; w < 3; ++w) {
            new_session();
            DeleteFileA(path1);
            memset(g_records, 0, sizeof g_records);
            villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20);
            titles_tick(3);
            titles_set(3, 1, "Kai Title");
            new_session();
            memset(g_records, 0, sizeof g_records);
            villager(0, "Lani");
            villager(1, "Kai"); looks(1, wrong[w].sex, wrong[w].age, 3, 4, wrong[w].skill);
            titles_tick(3);
            titles_tick(3);
            check(titles_lookup(3, g_records[1]) == NULL && titles.count == 1
                  && title_index("Kai Title") == (int)VV_TITLE_PENDING, wrong[w].what);
        }
    }

    /* v1.35.72: A LOWERED AGE OR SKILL THE PATCHER MADE ITSELF (a Custom
       Island Event's Villager changes).  Left as stored, the next load finds
       nobody "no younger, no less skilled" and the title goes pending; the
       event re-stores the title's looks (titles_rebase).  Without it (a
       change nobody told the companion of) the title still waits pending --
       never a guess. */
    {
        int told;
        for (told = 0; told < 2; ++told) {
            new_session();
            DeleteFileA(path1);
            memset(g_records, 0, sizeof g_records);
            villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20);
            titles_tick(3);
            titles_set(3, 1, "Kai Title");
            titles_tick(3);
            looks(1, 1, 300, 3, 4, 5);                           /* the event lowers age and skills */
            if (told) {
                check(titles_rebase(3, 1) == 1, "the event's lowered age and skills are re-stored and published");
            }
            titles_tick(3);
            titles_tick(3);
            if (told) {
                check(title_index("Kai Title") == 1, "... the title stays on Kai in the session");
            } else {
                /* The age fell: the sweep takes a younger villager in the same record for a namesake
                   born into a freed record (titles_reborn), and a title whose villager was seen is
                   deleted -- what an unannounced AGE lowering (Cheat Engine) does. */
                check(titles.count == 0, "... an unannounced age lowering DELETES the seen title (reborn namesake)");
            }
            new_session();
            memset(g_records, 0, sizeof g_records);
            villager(0, "Kai"); looks(0, 1, 300, 3, 4, 5);       /* reloaded, packed to [0] */
            villager(1, "Lani");
            titles_tick(3);
            seen = titles_lookup(3, g_records[0]);
            if (told) {
                check(seen != NULL && lstrcmpA(seen, "Kai Title") == 0,
                      "A LOWERED AGE AND SKILL FROM A CUSTOM ISLAND EVENT: THE TITLE STILL FOLLOWS KAI AFTER A RELOAD");
            } else {
                check(seen == NULL && titles.count == 0 && title_index("Kai Title") == -2,
                      "... and after a reload the deleted title is on nobody and not in the file");
            }
        }
        /* Re-storing touches only the entry bound to that very villager. */
        new_session();
        DeleteFileA(path1);
        memset(g_records, 0, sizeof g_records);
        villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20); villager(2, "Moku");
        looks(2, 1, 400, 2, 2, 10);
        titles_tick(3);
        titles_set(3, 1, "Kai Title");
        looks(2, 1, 100, 2, 2, 1);
        check(titles_rebase(3, 2) == 1 && titles.entries[0].looks.age == 500
              && titles.entries[0].looks.skills[0] == 20, "a record with no title leaves other entries alone");

        /* The stored values only ever go DOWN (v1.35.72, review): an event that raises age or skills
           must not lift the stored looks above what the save still holds after an Alt-F4 or a crash. */
        new_session();
        DeleteFileA(path1);
        memset(g_records, 0, sizeof g_records);
        villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20);
        titles_tick(3);
        titles_set(3, 1, "Kai Title");
        titles_tick(3);
        looks(1, 1, 700, 3, 4, 60);                              /* the event raises age and skills */
        check(titles_rebase(3, 1) == 1 && titles.entries[0].looks.age == 500 && titles.entries[0].looks.skills[0] == 20
              && titles.base_age[1] == 500 && titles.base_skills[1][0] == 20,
              "AN EVENT THAT RAISES AGE AND SKILLS NEVER LIFTS WHAT THE TITLE IS KEPT BY");
        titles_tick(3);
        titles_tick(3);
        new_session();                                           /* a crash: the save still holds the older values */
        memset(g_records, 0, sizeof g_records);
        villager(0, "Kai"); looks(0, 1, 500, 3, 4, 20);
        villager(1, "Lani");
        titles_tick(3);
        seen = titles_lookup(3, g_records[0]);
        check(seen != NULL && lstrcmpA(seen, "Kai Title") == 0,
              "... SO AFTER AN ALT-F4 THE OLDER SAVE'S KAI STILL HAS HIS TITLE");
        /* Mixed: age lowered, one skill raised, another lowered -- each field its own lower value. */
        new_session();
        DeleteFileA(path1);
        memset(g_records, 0, sizeof g_records);
        villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20);
        titles_tick(3);
        titles_set(3, 1, "Kai Title");
        titles_tick(3);
        looks(1, 1, 400, 3, 4, 20);
        *(int *)(g_records[1] + 64) = 90;                        /* skill 0 raised */
        *(int *)(g_records[1] + 68) = 5;                         /* skill 1 lowered */
        check(titles_rebase(3, 1) == 1 && titles.entries[0].looks.age == 400 && titles.entries[0].looks.skills[0] == 20
              && titles.entries[0].looks.skills[1] == 5, "each field follows the event down only");
        /* A write that fails rolls back the bases and the last look's age with the table. */
        new_session();
        DeleteFileA(path1);
        memset(g_records, 0, sizeof g_records);
        villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20);
        titles_tick(3);
        titles_set(3, 1, "Kai Title");
        titles_tick(3);
        looks(1, 1, 300, 3, 4, 5);
        g_fail_writes = 1;
        check(titles_rebase(3, 1) == 0, "a rebase that can not be written is refused");
        g_fail_writes = 0;
        check(titles.entries[0].looks.age == 500 && titles.entries[0].looks.skills[0] == 20
              && titles.base_age[1] == 500 && titles.base_skills[1][0] == 20 && titles.roster_age[1] == 500,
              "... and leaves the entry, the bases and the last look's age as they were");
        /* Nothing is touched before the table has been followed against the village. */
        new_session();
        titles_sync(3);
        check(titles.loaded && !titles.roster_anyone && titles_rebase(3, 1) == 1 && titles.entries[0].looks.age == 500
              && titles.base_age[1] == 0, "a rebase before the table was followed changes nothing");
    }

    /* v1.35.72 (re-review): A TITLE SET AFTER A LOWERING.  The lowering (a Custom Island Event's skill
       change) moves what a title is kept by even when nobody holds a title yet, so a title set on that
       villager later in the session, or in the same event after the lowering, is stored with the
       lowered skill -- not the higher one the villager was first seen with, which no clean save can
       match.  Ints (A New Home to The Secret City) and floats (The Tree of Life, New Believers). */
    {
        int fl, same_event;
        for (fl = 0; fl < 2; ++fl) {
            for (same_event = 0; same_event < 2; ++same_event) {
                char what[160];
                g_skills_float = fl;
                new_session();
                DeleteFileA(path1);
                memset(g_records, 0, sizeof g_records);
                villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 0);
                set_skill(1, 0, 50);
                titles_tick(3);
                titles_tick(3);
                set_skill(1, 0, 10);                             /* the event lowers a skill: nobody has a title yet */
                check(titles_rebase(3, 1) == 1, "a lowering with no title bound is followed (nothing to publish)");
                if (!same_event) {
                    titles_tick(3);
                    titles_tick(3);
                }
                check(titles_set(3, 1, "Kai Title") == 1, "the title is set after the lowering");
                wsprintfA(what, "THE NEW TITLE IS STORED WITH THE LOWERED SKILL (%s, %s)", fl ? "floats" : "ints",
                          same_event ? "same event" : "later");
                check(titles.entries[0].looks.skills[0] == skill_dword(10), what);
                titles_tick(3);
                titles_tick(3);
                check(titles.entries[0].looks.skills[0] == skill_dword(10), "... and the next ticks keep it");
                new_session();                                   /* a clean save and reload: skill 10, packed to [0] */
                memset(g_records, 0, sizeof g_records);
                villager(0, "Kai"); looks(0, 1, 500, 3, 4, 0); set_skill(0, 0, 10);
                villager(1, "Lani");
                titles_tick(3);
                seen = titles_lookup(3, g_records[0]);
                wsprintfA(what, "... SO A CLEAN SAVE RELOAD KEEPS THE TITLE BOUND (%s, %s)", fl ? "floats" : "ints",
                          same_event ? "same event" : "later");
                check(seen != NULL && lstrcmpA(seen, "Kai Title") == 0, what);
                new_session();                                   /* an Alt-F4: the older save, skill 50 */
                memset(g_records, 0, sizeof g_records);
                villager(0, "Kai"); looks(0, 1, 500, 3, 4, 0); set_skill(0, 0, 50);
                villager(1, "Lani");
                titles_tick(3);
                seen = titles_lookup(3, g_records[0]);
                wsprintfA(what, "... AND AN ALT-F4 RELOAD OF THE OLDER SAVE STILL KEEPS IT (%s, %s)",
                          fl ? "floats" : "ints", same_event ? "same event" : "later");
                check(seen != NULL && lstrcmpA(seen, "Kai Title") == 0, what);
            }
        }
        g_skills_float = 0;
    }

    /* v1.35.72: A CHANGE APPEARANCE AND A LOG IN THE SAME FRAME.  The file
       still holds the old head and body until the next tick republishes
       them; a Death or Disappeared record written in between compares the
       villager's new looks against those and leaves the title out.  Origins'
       Change Appearance now tells the companion in the same call that logs
       it, and the file is published before that call returns. */
    {
        int told;
        for (told = 0; told < 2; ++told) {
            vv_title_looks stored;
            new_session();
            DeleteFileA(path1);
            memset(g_records, 0, sizeof g_records);
            villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20);
            titles_tick(3);
            titles_set(3, 1, "Kai Title");
            titles_tick(3);
            looks(1, 1, 500, 7, 8, 20);                          /* Change Appearance: head 3 -> 7, body 4 -> 8 */
            if (told) {
                check(VvfpStoryAppearanceChanged(3, g_records[1], 7, 8) == 1, "the companion is told of the new looks");
            }
            new_session();                                       /* what a log written now reads: the file */
            titles_sync(3);
            stored = titles.entries[0].looks;
            check(told ? stored.head == 7 && stored.body == 8 && stored.age == 500 && stored.skills[0] == 20
                       : stored.head == 3 && stored.body == 4,
                  told ? "A CHANGE APPEARANCE IS IN THE FILE AT ONCE: A LOG IN THE SAME FRAME COMPARES THE NEW LOOKS"
                       : "... without it the file keeps the old looks until the next tick");
        }
        /* A villager with no title, or another record's, leaves the file alone. */
        new_session();
        DeleteFileA(path1);
        memset(g_records, 0, sizeof g_records);
        villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20);
        titles_tick(3);
        titles_set(3, 1, "Kai Title");
        titles_tick(3);
        looks(0, 1, 100, 5, 6, 1);
        check(VvfpStoryAppearanceChanged(3, g_records[0], 5, 6) == 1 && titles.entries[0].looks.head == 3,
              "a villager with no title leaves every entry alone");
    }

    /* v1.35.73: an island event that changes BOTH the likes and the head before the next frame (the
       island events DLL tells the companion of the new head, VvfpStoryAppearanceChanged, in the same
       frame).  The likes change is carried to the new identity first, as the lookup carries it, so
       the new head is stored at once under that identity -- in the file too -- in every game. */
    for (game = 1; game <= 5; ++game) {
        char what[160];
        new_session();
        DeleteFileA(path1);
        memset(g_records, 0, sizeof g_records);
        villager(0, "Lani"); villager(1, "Kai"); looks(1, 1, 500, 3, 4, 20);
        titles_tick(game);
        check(titles_set(game, 1, "Kai Title") == 1, "setup: Kai has a title");
        titles_tick(game);
        g_records[1][44] = 7;                                         /* the event's new likes ... */
        looks(1, 1, 500, 7, 8, 20);                                   /* ... and new head and body, same frame */
        check(VvfpStoryAppearanceChanged(game, g_records[1], 7, 8) == 1, "the companion is told of the new head");
        wsprintfA(what, "AN EVENT CHANGING LIKES AND HEAD: THE NEW HEAD IS STORED UNDER THE NEW IDENTITY (game %d)", game);
        check(titles.count == 1 && titles.entries[0].index == 1 && titles.entries[0].looks.head == 7
              && titles.entries[0].looks.body == 8
              && titles.entries[0].fingerprint == story_title_identity(game, g_records[1]), what);
        new_session();                                                /* what a log written now reads: the file */
        titles_sync(game);
        wsprintfA(what, "... and the file holds the new head and identity (game %d)", game);
        check(titles.count == 1 && titles.entries[0].looks.head == 7
              && titles.entries[0].fingerprint == story_title_identity(game, g_records[1]), what);
    }

    /* Twins identical in everything: whose the title is can never be told
       while both live -- it stays pending, and the reconciliation asks. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani");
    villager(5, "Kai"); looks(5, 1, 500, 3, 4, 20);
    villager(6, "Kai"); looks(6, 1, 500, 3, 4, 20);
    titles_tick(3);
    check(titles_set(3, 5, "Only This Kai") == 1, "setup: one of two identical twins has a title");
    new_session();
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani");
    villager(4, "Kai"); looks(4, 1, 500, 3, 4, 20);
    villager(5, "Kai"); looks(5, 1, 500, 3, 4, 20);
    titles_tick(3);
    titles.checked_at = GetTickCount() - 3 * TITLES_CHECK_MS;
    titles_tick(3);
    titles_tick(3);
    check(titles_lookup(3, g_records[4]) == NULL && titles_lookup(3, g_records[5]) == NULL
          && titles.count == 1 && title_index("Only This Kai") == (int)VV_TITLE_PENDING,
          "TWINS IDENTICAL IN EVERYTHING: THE TITLE STAYS PENDING, SHOWN ON NEITHER, KEPT");
    new_session();
    titles_sync(3);
    check(titles.count == 1 && titles.entries[0].index == VV_TITLE_PENDING,
          "... and the file keeps it pending for the reconciliation to ask about");

    /* Two titled villagers of one whole identity, one of whom died before
       the reload: the survivor could be either, so neither title is given --
       both wait, and the file never lists one record twice. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(1, "Kai"); villager(3, "Kai");
    check(titles_set(3, 1, "First Kai") == 1 && titles_set(3, 3, "Second Kai") == 1,
          "setup: two villagers named Kai, each with a title");
    new_session();
    memset(g_records, 0, sizeof g_records);
    villager(0, "Kai"); villager(1, "Lani");
    titles_tick(3);
    check(titles_lookup(3, g_records[0]) == NULL, "a surviving Kai is not given either Kai's title");
    new_session();
    check(titles_lookup(3, g_records[1]) == NULL && titles.loaded && titles.count == 2
          && title_index("First Kai") == (int)VV_TITLE_PENDING && title_index("Second Kai") == (int)VV_TITLE_PENDING,
          "... both entries wait pending, and the file still loads (no record listed twice)");
    /* A move and nothing else is written back too. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(1, "Kai");
    check(titles_set(3, 1, "Moved Only") == 1, "setup: Kai [1] has a title, Lani [0] none");
    new_session();
    memset(g_records, 0, sizeof g_records);
    villager(0, "Kai"); villager(1, "Lani");
    titles_tick(3);
    new_session();
    titles_sync(3);                              /* the file as written, before any follow */
    check(titles.loaded && titles.count == 1 && titles.entries[0].index == 0,
          "A PURE MOVE IS WRITTEN BACK: the next session finds Kai's title at record 0");

    /* Codex (#516): a titled Kai at record 5 and an untitled namesake of the
       same looks at 6; a death below moves them to 4 and 5.  Record 5 still
       carries the title's fingerprint -- but it is the OTHER Kai now, younger
       and less skilled than the title's.  The title follows its own Kai. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani");
    villager(5, "Kai"); looks(5, 1, 600, 3, 4, 30);
    villager(6, "Kai"); looks(6, 1, 300, 3, 4, 10);
    titles_tick(3);
    check(titles_set(3, 5, "Only This Kai") == 1, "setup: the older of two look-alike Kais has a title");
    new_session();
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani");
    villager(4, "Kai"); looks(4, 1, 610, 3, 4, 30);
    villager(5, "Kai"); looks(5, 1, 310, 3, 4, 10);
    titles_tick(3);
    seen = titles_lookup(3, g_records[4]);
    check(seen != NULL && lstrcmpA(seen, "Only This Kai") == 0 && titles_lookup(3, g_records[5]) == NULL,
          "A YOUNGER NAMESAKE PACKED INTO THE TITLE'S OLD RECORD IS NOT GIVEN IT: THE TITLE FOLLOWS ITS VILLAGER");

    /* -- the 256 cap: every record taken, deaths free records that births
       reuse, and every load packs (the owner's A New Home village; RECORDS
       stands for the cap here). */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    {
        static const char *names[RECORDS] = { "Abe", "Bea", "Cai", "Hoku", "Eka", "Fai", "Ana", "Hiro" };
        int k;
        for (k = 0; k < RECORDS; ++k) {
            villager(k, names[k]);
            looks(k, 1 + k % 2, 300 + 100 * k, k, k, 10 + k);
        }
        titles_tick(3);
        check(titles_set(3, 3, "Hoku Title") == 1 && titles_set(3, 6, "Ana Title") == 1,
              "setup at the cap: Hoku [3] and Ana [6] have titles");
        /* Hoku dies and is buried; the reload packs everyone behind him
           down, and a newborn namesake (the same name, likes and looks)
           takes the freed last record. */
        new_session();
        memset(g_records, 0, sizeof g_records);
        for (k = 0; k < RECORDS - 1; ++k) {
            int from = k < 3 ? k : k + 1;
            villager(k, names[from]);
            looks(k, 1 + from % 2, 320 + 100 * from, from, from, 10 + from);
        }
        villager(7, "Hoku"); looks(7, 1 + 3 % 2, 0, 3, 3, 13);
        titles_tick(3);
        seen = titles_lookup(3, g_records[5]);
        check(seen != NULL && lstrcmpA(seen, "Ana Title") == 0,
              "AT THE CAP A TITLED VILLAGER MOVED BY LOAD PACKING KEEPS HER TITLE (Ana [6 -> 5])");
        check(titles_lookup(3, g_records[7]) == NULL && title_index("Hoku Title") == (int)VV_TITLE_PENDING,
              "A BIRTH INTO A FREED RECORD AT THE CAP NEVER INHERITS THE TITLE (Hoku's waits, pending)");
        /* In one session: Ana dies and, between two looks, a newborn Ana
           (the same name and likes) is born into her very record. */
        titles_tick(3);
        looks(5, 1 + 6 % 2, 0, 6, 6, 16);
        titles_tick(3);
        check(titles_lookup(3, g_records[5]) == NULL && title_index("Ana Title") == -2,
              "A BIRTH INTO A DEAD VILLAGER'S RECORD AT THE CAP NEVER INHERITS THE TITLE (in session: she died)");
    }

    /* -- an old (version 2) file is still read, followed, and written back
       as version 3 ------------------------------------------------------ */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(1, "Kai");
    {
        unsigned char v2[16 + 40];
        unsigned int head[4] = { VV_TITLES_MAGIC, 2u, 3u, 1u };
        unsigned int at = 1, fp = story_title_identity(3, g_records[1]);
        memset(v2, 0, sizeof v2);
        memcpy(v2, head, 16);
        memcpy(v2 + 16, &at, 4);
        memcpy(v2 + 20, &fp, 4);
        lstrcpyA((char *)v2 + 24, "Old Title");
        write_bytes(path1, v2, sizeof v2);
    }
    memset(g_records, 0, sizeof g_records);
    villager(0, "Kai"); looks(0, 1, 700, 2, 2, 5);                /* a reload moved Kai down */
    seen = titles_lookup(3, g_records[0]);
    check(seen != NULL && lstrcmpA(seen, "Old Title") == 0, "AN OLD-FORMAT (VERSION 2) FILE STILL LOADS AND FOLLOWS");
    titles_tick(3);
    h = CreateFileA(path1, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    got = 0;
    ReadFile(h, raw, sizeof raw, &got, NULL);
    CloseHandle(h);
    check(got == 100 && raw[4] == 3 && raw[16] == 0 && raw[24] == VV_TITLE_KNOWN && *(int *)(raw + 28) == 700,
          "... and is written back as version 3, with the villager's looks");

    /* With nothing moved (the same session, no reload), a title set on one
       of two identical villagers stays where it was set. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(5, "Kai"); villager(6, "Kai");
    titles_tick(3);
    check(titles_set(3, 5, "Set In Session") == 1, "setup: a title set in session on one of two twins");
    titles_tick(3);
    titles_tick(3);
    check(titles.count == 1 && titles.entries[0].index == 5,
          "with nothing moved, the twin's title is kept on the record it was set on");
    seen = titles_lookup(3, g_records[5]);
    check(seen != NULL && lstrcmpA(seen, "Set In Session") == 0 && titles_lookup(3, g_records[6]) == NULL,
          "... and shown there, on that twin only");
    lstrcpynA((char *)g_records[0] + 1, "Leilani", NAME_BYTES);    /* someone else is renamed */
    titles_tick(3);
    check(titles.count == 1 && titles_lookup(3, g_records[5]) != NULL,
          "another villager's rename is not a move: the twin's title stays");
    /* A namesake born in this session is not the titled villager: a title
       read from its file whose villager is away (nobody carries it) keeps
       waiting at its record; it does not jump to a newborn of the same name,
       and is shown again when she is back. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(7, "Moana"); looks(7, 2, 300, 5, 5, 12);
    titles_tick(3);
    check(titles_set(3, 7, "Moana Title") == 1, "setup: Moana [7] has a title");
    new_session();
    g_records[7][0] = 0;                                          /* away */
    titles_tick(3);
    titles_tick(3);
    villager(2, "Moana"); looks(2, 2, 0, 5, 5, 0);                /* a namesake, born into record 2 */
    titles_tick(3);
    check(titles_lookup(3, g_records[2]) == NULL && titles.count == 1 && titles.entries[0].index == 7,
          "a namesake born in the same session does not inherit the title");
    g_records[7][0] = 1;                                          /* back */
    titles_tick(3);
    seen = titles_lookup(3, g_records[7]);
    check(seen != NULL && lstrcmpA(seen, "Moana Title") == 0 && titles_lookup(3, g_records[2]) == NULL,
          "... and the title is shown again when its villager is back");
    memset(g_records[2], 0, sizeof g_records[2]);
    memset(g_records[7], 0, sizeof g_records[7]);
    villager(5, "Kai"); villager(6, "Kai");
    /* the twins' file again, for the next case */
    new_session();
    DeleteFileA(path1);
    titles_tick(3);
    check(titles_set(3, 5, "Set In Session") == 1, "setup: the twin's title again");
    /* A table just read from its file is followed before anything is shown:
       its first lookup -- before any tick -- already finds the twin's title
       ambiguous (a reload may have moved them). */
    new_session();
    check(titles_lookup(3, g_records[5]) == NULL && titles.count == 1
          && titles.entries[0].index == VV_TITLE_PENDING,
          "a lookup before any tick follows the table first: the twin's title is kept pending, not shown");

    /* Another save slot is another village loaded: its file is followed
       afresh (the last look belonged to the other slot), so a twin's title
       in it is pending rather than shown on record 5. */
    new_session();
    g_slot = 2;
    DeleteFileA(path2);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(5, "Kai"); villager(6, "Kai");
    titles_tick(3);
    check(titles_set(3, 5, "Slot Two Twin") == 1, "setup: slot 2 has a twin's title");
    g_slot = 1;
    titles_tick(3);
    g_slot = 2;
    check(titles_lookup(3, g_records[5]) == NULL,
          "a slot switched back to is followed afresh: the twin's title is not shown on the old look");
    g_slot = 1;
    DeleteFileA(path2);

    /* The first lookup's own follow does not run the death sweep: a title
       set before any tick, with another villager in its record at that
       lookup, is not shown -- and waits for its villager. */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(1, "Kai");
    check(titles_set(3, 1, "Before Any Tick") == 1, "setup: a title set before any tick");
    lstrcpynA((char *)g_records[1] + 1, "Kaj", NAME_BYTES);
    check(titles_lookup(3, g_records[1]) == NULL, "another villager in the record is not shown the title");
    lstrcpynA((char *)g_records[1] + 1, "Kai", NAME_BYTES);
    titles_tick(3);
    seen = titles_lookup(3, g_records[1]);
    check(seen != NULL && lstrcmpA(seen, "Before Any Tick") == 0,
          "the first lookup's follow does not sweep: the title is still there for its villager");

    /* -- Codex (#516, round 2): a villager renamed during play ----------- */
    new_session();
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Lani"); villager(1, "Kai"); villager(2, "Moku");
    titles_tick(3);
    check(titles_set(3, 1, "Renamed Hero") == 1, "setup: Kai [1] has a title");
    titles_tick(3);
    lstrcpynA((char *)g_records[1] + 1, "Kainoa", NAME_BYTES);    /* the player renames him */
    titles_tick(3);
    titles_tick(3);
    seen = titles_lookup(3, g_records[1]);
    check(seen != NULL && lstrcmpA(seen, "Renamed Hero") == 0, "A RENAMED VILLAGER KEEPS THE TITLE");
    new_session();
    seen = titles_lookup(3, g_records[1]);
    check(seen != NULL && lstrcmpA(seen, "Renamed Hero") == 0, "... and the file has it under the new name");
    /* Not a rename: another villager (other likes) in the record. */
    titles_tick(3);
    lstrcpynA((char *)g_records[1] + 1, "Stranger", NAME_BYTES);
    g_records[1][40] = 9;
    titles_tick(3);
    check(titles_lookup(3, g_records[1]) == NULL && titles.count == 1
          && title_index("Renamed Hero") == (int)VV_TITLE_PENDING,
          "a different villager in the record is not a rename: not shown on them, and -- nobody saw Kainoa die -- the title waits pending");
    DeleteFileA(path1);
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Hina"); villager(1, "Kai"); villager(2, "Lani");

    /* -- v1.35.68: likes / dislikes changed by an island event ------------
       The Tree of Life's "Faces in the Night" gave Alapai new dislikes and
       the Island Events log said "Custom title: Moon Mother -> none": the
       identity hashes the likes and dislikes, so the title was swept away.
       Every game. */
    for (game = 1; game <= 5; ++game) {
        char what[128];
        new_session();
        DeleteFileA(path1);
        memset(g_records, 0, sizeof g_records);
        villager(0, "Lani"); villager(1, "Alapai"); villager(2, "Moku"); villager(3, "Kai");
        *(int *)(g_records[1] + 52) = 300;
        g_records[1][48] = 1;                                         /* female */
        titles_tick(game);
        check(titles_set(game, 1, "Moon Mother") == 1 && titles_set(game, 3, "Sea Watcher") == 1,
              "setup: Alapai [1] and Kai [3] have titles");
        titles_tick(game);
        g_records[1][44] = 7;                                         /* the event's new dislikes */
        seen = titles_lookup(game, g_records[1]);                     /* the Island Events log asks at once */
        wsprintfA(what, "THE TITLE SURVIVES A LIKES / DISLIKES CHANGE, ASKED IN THE SAME FRAME (game %d)", game);
        check(seen != NULL && lstrcmpA(seen, "Moon Mother") == 0, what);
        titles_tick(game);
        *(int *)(g_records[1] + 52) = 301;                            /* a year passes... */
        titles_tick(game);
        seen = titles_lookup(game, g_records[1]);
        wsprintfA(what, "... and every tick after it (game %d)", game);
        check(seen != NULL && lstrcmpA(seen, "Moon Mother") == 0, what);
        new_session();
        seen = titles_lookup(game, g_records[1]);
        wsprintfA(what, "... and the file has it under the new identity (game %d)", game);
        check(seen != NULL && lstrcmpA(seen, "Moon Mother") == 0, what);
        /* An event that changes everyone's likes at once: both titles stay. */
        titles_tick(game);
        g_records[1][44] = 8;
        g_records[3][44] = 9;
        g_records[0][44] = 3;
        titles_tick(game);
        titles_tick(game);
        wsprintfA(what, "an event changing everyone's likes keeps every title (game %d)", game);
        check(titles_lookup(game, g_records[1]) != NULL && titles_lookup(game, g_records[3]) != NULL
              && titles.count == 2, what);
        /* A newborn namesake of the same sex in the record: not her (age 0). */
        g_records[1][44] = 5;
        *(int *)(g_records[1] + 52) = 0;
        titles_tick(game);
        titles_tick(game);
        wsprintfA(what, "a newborn namesake in the freed record does not get the title (game %d)", game);
        check(titles_lookup(game, g_records[1]) == NULL && titles.count == 2
              && titles.entries[0].index == VV_TITLE_PENDING, what);
        /* A reload that packs a same-name, same-sex, same-age twin into her
           dead sister's record is not a likes change: the title is not
           given to the twin. */
        new_session();
        DeleteFileA(path1);
        memset(g_records, 0, sizeof g_records);
        villager(0, "Pua"); villager(1, "Pua"); villager(2, "Moku");
        g_records[0][44] = 1;
        g_records[1][44] = 2;
        titles_tick(game);
        check(titles_set(game, 0, "Elder Twin") == 1, "setup: twin Pua [0] has a title");
        titles_tick(game);
        memcpy(g_records[0], g_records[1], sizeof g_records[0]);     /* [0] died; the reload packs */
        memcpy(g_records[1], g_records[2], sizeof g_records[1]);
        memset(g_records[2], 0, sizeof g_records[2]);
        titles_tick(game);
        titles_tick(game);
        wsprintfA(what, "A PACKED RELOAD NEVER GIVES THE DEAD TWIN'S TITLE TO HER NAMESAKE (game %d)", game);
        check(titles_lookup(game, g_records[0]) == NULL, what);
        /* A village of one whose likes change shares no identity with the
           last look: still play, not the title screen's other array. */
        new_session();
        DeleteFileA(path1);
        memset(g_records, 0, sizeof g_records);
        villager(0, "Alapai");
        titles_tick(game);
        check(titles_set(game, 0, "Moon Mother") == 1, "setup: a village of one, titled");
        titles_tick(game);
        g_records[0][44] = 4;
        titles_tick(game);
        titles_tick(game);
        wsprintfA(what, "A VILLAGE OF ONE KEEPS THE TITLE THROUGH A LIKES CHANGE (game %d)", game);
        check(titles_lookup(game, g_records[0]) != NULL && titles.frozen == 0, what);
    }
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Hina"); villager(1, "Kai"); villager(2, "Lani");
    /* -- the title screen: another array with the slot unchanged ---------
       A quit to the menu leaves the startup slot list's seeded founders in
       the records while the game's slot field still says 1 (the owner's
       v1.35.67 parents loss).  The titles of villagers seen this session must
       not be swept and written away; when the village is back -- packed
       differently -- they follow it. */
    new_session();
    g_slot = 1;
    DeleteFileA(path1);
    check(titles_set(3, 1, "Keeper of Fire") == 1, "a title for Kai");
    titles_tick(3);
    titles_tick(3);                              /* Kai seen alive this session */
    memset(g_records, 0, sizeof g_records);
    villager(0, "Abebe"); villager(1, "Kanoa"); villager(2, "Mele"); villager(3, "Tavita");
    titles.checked_at = GetTickCount();
    titles_tick(3);
    titles_tick(3);
    check(titles.count == 1, "THE TITLE SCREEN'S FOUNDERS DO NOT SWEEP KAI'S TITLE AWAY");
    check(file_size(path1) == 16 + 84, "and the file still holds it");
    memset(g_records, 0, sizeof g_records);
    villager(0, "Kai"); villager(1, "Lani");     /* the village loaded again, Hina gone */
    titles_tick(3);
    seen = titles_lookup(3, g_records[0]);
    check(seen != NULL && lstrcmpA(seen, "Keeper of Fire") == 0,
          "BACK IN THE VILLAGE, KAI'S TITLE FOLLOWS HIM TO HIS NEW RECORD");
    DeleteFileA(path1);
    memset(g_records, 0, sizeof g_records);
    villager(0, "Hina"); villager(1, "Kai"); villager(2, "Lani");

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
        check(titles_set(game, 1, "New Village") == 1 && file_size(path1) == 16 + 84,
              "a new village's first title is the file's only entry");
        /* And a reset nobody ticked through: the write notices it too. */
        vv_reset_slot_state(game, 1, "Village: Test (Save 1)\n");
        check(titles_set(game, 2, "Second Start") == 1 && file_size(path1) == 16 + 84,
              "AFTER AN UNTICKED START OVER ONLY THE NEW TITLE IS WRITTEN");
    }

    /* -- Start Over whose founders share nobody with the last look (review of
       #585, v1.35.71): it looks like the title screen's other array.  The
       table was frozen before the deleted file was noticed, kept the erased
       village's title in memory, and gave it to a founder later put in the
       same record with the same identity. */
    for (game = 1; game <= 5; ++game) {
        char what[96];
        new_session();
        g_slot = 1;
        DeleteFileA(path1);
        memset(g_records, 0, sizeof g_records);
        villager(0, "Hina"); villager(1, "Kai"); villager(2, "Lani");
        titles_tick(game);
        check(titles_set(game, 0, "Old Village") == 1, "setup: a title in the old village");
        titles_tick(game);
        titles_tick(game);                       /* Hina seen alive this session */
        vv_reset_slot_state(game, 1, "Village: Test (Save 1)\n");
        memset(g_records, 0, sizeof g_records);
        villager(0, "Abebe"); villager(1, "Kanoa");   /* the new founders: nobody of the last look */
        titles_tick(game);
        titles_tick(game);
        wsprintfA(what, "START OVER TO A FOUNDER ROSTER FORGETS THE OLD TITLES (game %d)", game);
        check(titles.count == 0 && titles.frozen == 0, what);
        villager(2, "Hina");                     /* a founder with the erased villager's identity... */
        memset(g_records[0], 0, sizeof g_records[0]);
        villager(0, "Hina");                     /* ...in her old record */
        titles_tick(game);
        titles_tick(game);
        wsprintfA(what, "a new village's Hina is never shown the erased village's title (game %d)", game);
        check(titles_lookup(game, g_records[0]) == NULL && !file_exists(path1), what);
        /* The reset's own call forgets the table at once, whatever the records show. */
        new_session();
        DeleteFileA(path1);
        memset(g_records, 0, sizeof g_records);
        villager(0, "Hina"); villager(1, "Kai");
        titles_tick(game);
        check(titles_set(game, 0, "Old Village") == 1, "setup: a title again");
        titles_village_reset(game, 2);           /* another slot's tribe deleted: nothing here */
        check(titles.count == 1, "another slot's reset leaves this slot's table");
        titles_village_reset(game, 1);
        wsprintfA(what, "VvfpStoryVillageReset forgets the slot's titles at once (game %d)", game);
        check(titles.count == 0 && titles.file_present == 0, what);
    }

    printf("\n%d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}
