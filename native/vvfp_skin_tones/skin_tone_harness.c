/* The skin tones' per-save file and their rules, against real files on disk (tests/test_vv1_skin_tones.py runs it
   through scripts/build_skin_tone_harness.ps1).

   The companion's store and rules (skin_tone_store.inc) and the Start Over reset (native/shared/save_reset.c) are
   compiled here unchanged; only what they ask of the game is replaced: the save slot, a village of named records
   (with the family number and the due field a carrying mother has), the number of tones, the random numbers, and
   the save folder -- a fresh folder under %TEMP%, never the player's Documents\LDW.

   Proves: founders and arrivals are given a random tone 0..N -- only once the roster has settled, never to a
   villager the file already gives one -- spread over the tones; a tone is published in the documented format and
   read back by a new session; it follows its villager through a death and a packed reload, a rename and a copied
   file; a newborn in a dead villager's record never inherits; a baby takes the midpoint of its parents' tones AS
   THEY WERE AT CONCEPTION (a half step toward the mother's), the mother's tone with no father known or no
   conception seen, the same tone for a twin, and never a random one; the conception's tones are dropped once the
   mother is no longer carrying; Change Appearance's choice is kept (one, or many in one write) and a write that
   fails changes nothing; another village's file is never replaced; a broken file is set aside; Start Over deletes
   the file and the new founders get new random tones.  Exit code 0 when every check passes. */
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

/* ---- the save folder: %TEMP%\vvfp_skin_tone_harness_<pid> ----------------------------------------------- */

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

/* ---- the game: a slot and a village of records ------------------------------------------------------------
   Each record: [0] held, [1..25] name, [28] sex dword, [32] family dword (+0x36C), [36] due dword (+0x358). */

#define ST_MAX 256
#define ST_TONE_LIMIT 15
#define REC 64
static unsigned char g_records[ST_MAX][REC];
static int g_count = 256;
static int g_slot = 1;
static int g_tones = 8;
static unsigned int g_rng = 12345u;

static int st_game(void) { return 1; }
static int st_slots(void) { return g_count; }
static const unsigned char *st_record(int i) { return i >= 0 && i < g_count ? g_records[i] : NULL; }
static int st_present(const unsigned char *r) { return r[0] != 0; }
static int st_pregnant(const unsigned char *r) { return *(const int *)(r + 36) != 0; }
static int st_slot_now(void) { return g_slot; }
static int st_tone_count(void) { return g_tones; }
static int st_random(int n) {
    g_rng ^= g_rng << 13;
    g_rng ^= g_rng >> 17;
    g_rng ^= g_rng << 5;
    return n > 0 ? (int)((g_rng >> 8) % (unsigned int)n) : 0;
}

static unsigned int fnv(unsigned int h, const unsigned char *t, int cap, int stop) {
    int k;
    for (k = 0; k < cap && !(stop && t[k] == 0); ++k) {
        h = (h ^ t[k]) * 16777619u;
    }
    return h;
}

static unsigned int st_stable(const unsigned char *r) {
    unsigned int h = fnv(fnv(2166136261u, r + 28, 4, 0), r + 32, 4, 0);
    return h ? h : 1u;
}

static unsigned int st_identity(const unsigned char *r) {
    unsigned int h = fnv(2166136261u, r + 1, 25, 1);
    h = ((h ^ 0xFFu) * 16777619u ^ st_stable(r)) * 16777619u;
    return h ? h : 1u;
}

#include "skin_tone_store.inc"

static void villager(int i, const char *name, int sex, int family) {
    memset(g_records[i], 0, REC);
    g_records[i][0] = 1;
    lstrcpynA((char *)g_records[i] + 1, name, 25);
    g_records[i][28] = (unsigned char)sex;
    memcpy(g_records[i] + 32, &family, 4);
}

static void set_due(int i, int due) {
    memcpy(g_records[i] + 36, &due, 4);
}

static void clear_village(void) {
    memset(g_records, 0, sizeof g_records);
}

static void founders(int n, const char *stem) {
    int i;
    char name[32];
    clear_village();
    for (i = 0; i < n; ++i) {
        wsprintfA(name, "%s%d", stem, i);
        villager(i, name, i & 1, 100 + i);
    }
}

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

static void new_session(void) {
    memset(g_st, 0, sizeof g_st);
    memset(g_st_id, 0, sizeof g_st_id);
    memset(g_roster, 0, sizeof g_roster);
    memset(g_stable, 0, sizeof g_stable);
    memset(&g_gate, 0, sizeof g_gate);
    g_have_roster = 0;
    g_sync_tried = 0;
    g_sync_tick = 0;
    g_slot = 0;
    g_quiet = 0;
    g_foreign = 0;
    g_ticks += 10000;
}

static void later(void) {
    g_ticks += ST_SYNC_MS + 1;
}

static int tone(int i) {
    later();
    return st_get(g_records[i]);
}

/* Enough looks in a row for the roster to settle (and newcomers to be given a tone). */
static void settle(void) {
    int k;
    for (k = 0; k <= ST_SETTLE + 1; ++k) {
        (void)tone(0);
    }
}

static void file_path(int slot, char *out) {
    wsprintfA(out, "%s\\Virtual Villagers Fun Patcher\\Save %d\\Data\\Skin Tones\\Skin Tones - Save %d.dat",
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

static int count_files(int slot, const char *prefix) {
    char pattern[MAX_PATH];
    WIN32_FIND_DATAA found;
    HANDLE h;
    int n = 0;
    wsprintfA(pattern, "%s\\Virtual Villagers Fun Patcher\\Save %d\\Data\\Skin Tones\\%s*", g_root, slot, prefix);
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

/* A fresh village of `n` founders in `slot`, settled: every founder has a random tone. */
static void village(int slot, int n, const char *stem) {
    new_session();
    g_slot = slot;
    founders(n, stem);
    settle();
}

/* Mother m conceives by father f (-1: no father captured); born into record c. */
static int conceive(int m, int f) {
    set_due(m, 400);
    later();
    return st_conceived(g_records[m], f >= 0 ? g_records[f] : NULL);
}

static int birth(int c, const char *name, int m) {
    villager(c, name, 0, 300 + c);
    return st_born(g_records[c], g_records[m]);
}

int main(void) {
    char path[MAX_PATH], other[MAX_PATH];
    unsigned char buf[8192];
    DWORD got;
    unsigned int u;
    int i, seen[16], spread, all_in_range;
    char temp[MAX_PATH];
    GetTempPathA(MAX_PATH, temp);
    wsprintfA(g_root, "%svvfp_skin_tone_harness_%lu", temp, GetCurrentProcessId());
    fresh_disk();

    printf("founders get a random tone, once the roster has settled\n");
    new_session();
    g_slot = 1;
    founders(60, "Kai");
    check(tone(0) == -1 && tone(5) == -1, "a village just seen: nobody has a tone yet (drawn with the game's own)");
    settle();
    memset(seen, 0, sizeof seen);
    all_in_range = 1;
    for (i = 0; i < 60; ++i) {
        int t = tone(i);
        all_in_range &= t >= 0 && t <= g_tones;
        if (t >= 0 && t <= 15) {
            seen[t] = 1;
        }
    }
    for (spread = 0, i = 0; i <= g_tones; ++i) {
        spread += seen[i];
    }
    check(all_in_range, "then every founder has a tone 0..N (N = 8)");
    check(spread >= 7, "spread over the tones (random, not one for all)");
    check(seen[0], "tone 0, the game's own art, is one of them");
    check(st_original(g_records[7]) == tone(7), "a founder's original tone is the one first given");
    file_path(1, path);
    got = read_file(path, buf, sizeof buf);
    check(got == 12 + 256 * 12, "the file is 12 + 256 * 12 bytes, in the save's own Data\\Skin Tones folder");
    memcpy(&u, buf, 4);
    check(u == 0x31545356u, "magic 'VST1'");
    memcpy(&u, buf + 4, 4);
    check(u == 1, "the game: A New Home");
    memcpy(&u, buf + 8, 4);
    check(u == 256, "the record count");
    check(buf[12 + 256 * 8 + 3] == (unsigned char)(tone(3) + 1), "each record's tone + 1 after the roster and ids");
    check(buf[12 + 256 * 9 + 3] == (unsigned char)(st_original(g_records[3]) + 1), "then the original tones");
    memcpy(&u, buf + 12 + 3 * 4, 4);
    check(u == st_identity(g_records[3]), "each record's identity in the roster");

    printf("a new session reads them back, and gives nobody a new one\n");
    {
        int before[60];
        for (i = 0; i < 60; ++i) {
            before[i] = tone(i);
        }
        new_session();
        g_slot = 1;
        settle();
        for (i = 0; i < 60 && tone(i) == before[i]; ++i) {
        }
        check(i == 60, "every founder keeps the tone the file gives");
    }

    printf("an arrival gets a random tone\n");
    villager(60, "Stranger", 1, 999);
    check(tone(60) == -1, "an arrival just seen has none yet");
    settle();
    check(tone(60) >= 0 && tone(60) <= g_tones, "then a random one");

    printf("following the villager\n");
    {
        int kai3, kai7;
        check(st_set(g_records[3], 6) == 1 && st_set(g_records[7], 2) == 1, "(Kai3 tone 6, Kai7 tone 2)");
        kai3 = tone(3);
        kai7 = tone(7);
        g_records[1][0] = 0;                   /* Kai1 dies and is buried */
        settle();
        check(tone(3) == kai3, "a death in play moves nobody");
        new_session();
        g_slot = 1;
        pack();
        check(lstrcmpA((char *)g_records[2] + 1, "Kai3") == 0, "(the reload packed Kai3 into record 2)");
        check(tone(2) == 6 && tone(6) == 2, "after the reload each tone is on its villager, one record down");
        lstrcpyA((char *)g_records[2] + 1, "Renamed");
        check(tone(2) == 6, "a renamed villager keeps the tone");
        new_session();
        g_slot = 1;
        check(tone(2) == 6, "...and after a reload, under the new name");
    }

    printf("a newborn in a dead villager's record\n");
    {
        village(2, 10, "Ann");
        st_set(g_records[2], 1);               /* the mother */
        st_set(g_records[3], 5);               /* the father */
        st_set(g_records[9], 8);               /* Ann9, about to die */
        g_records[9][0] = 0;                   /* buried: record 9 is free, its entry kept while empty */
        settle();
        check(g_st[ST_TONE][9] == 9, "an empty record keeps the dead villager's tone while nobody takes it");
        conceive(2, 3);
        check(birth(9, "Baby", 2) == 1, "a baby is born into the dead villager's record");
        check(tone(9) == 3, "it takes its parents' midpoint (1 and 5: 3), never the dead villager's 8");
        settle();
        check(tone(9) == 3, "and the settled roster gives it no random tone");
    }

    printf("babies inherit, never at random\n");
    {
        static const struct { int mother, father, baby; const char *what; } CASES[] = {
            { 2, 7, 4, "2 and 7: 4.5, a half step toward the mother: 4" },
            { 7, 2, 5, "7 and 2: 4.5, a half step toward the mother: 5" },
            { 3, 3, 3, "3 and 3: 3" },
            { 0, 8, 4, "0 (the game's own) and 8: 4" },
            { 0, 1, 0, "0 and 1: 0.5, toward the mother: 0" },
            { 8, 8, 8, "8 and 8: 8" },
        };
        int k;
        for (k = 0; k < (int)(sizeof CASES / sizeof CASES[0]); ++k) {
            fresh_disk();
            village(1, 6, "Mum");
            st_set(g_records[0], CASES[k].mother);
            st_set(g_records[1], CASES[k].father);
            conceive(0, 1);
            birth(10, "Kid", 0);
            check(tone(10) == CASES[k].baby, CASES[k].what);
            check(st_original(g_records[10]) == CASES[k].baby, "...and that is its original tone");
        }
    }

    printf("the tones are the ones at conception\n");
    fresh_disk();
    village(1, 6, "Eve");
    st_set(g_records[0], 2);                   /* mother */
    st_set(g_records[1], 6);                   /* father */
    conceive(0, 1);
    st_set(g_records[1], 0);                   /* the father's tone changes during the pregnancy */
    st_set(g_records[0], 8);                   /* and the mother's */
    g_records[1][0] = 0;                       /* and he dies before the birth */
    settle();
    check(birth(10, "Twin1", 0) == 1 && tone(10) == 4, "the baby takes 2 and 6 as they were (4)");
    check(birth(11, "Twin2", 0) == 1 && tone(11) == 4, "a twin takes the same tone");
    new_session();
    g_slot = 1;
    check(birth(12, "Twin3", 0) == 1 && tone(12) == 4, "a triplet born after a reload too (the file keeps them)");
    set_due(0, 0);                             /* the delivery is over */
    settle();
    check(g_st[ST_MOTHER][0] == 0 && g_st[ST_FATHER][0] == 0, "once she is no longer carrying they are dropped");
    check(birth(13, "Late", 0) == 1 && tone(13) == 8, "a later birth with no conception seen: the mother's own tone");

    printf("no father known\n");
    fresh_disk();
    village(1, 6, "Ida");
    st_set(g_records[0], 6);
    conceive(0, -1);
    check(birth(10, "Solo", 0) == 1 && tone(10) == 6, "a conception with no father captured: the mother's tone");

    printf("a mother first seen at the birth (a catch-up birth just after installing)\n");
    fresh_disk();
    new_session();
    g_slot = 1;
    founders(6, "New");
    later();
    check(birth(10, "First", 0) == 1, "the birth is kept");
    check(tone(0) >= 0 && tone(10) == tone(0), "the mother is given her tone first, and the baby takes it");

    printf("Change Appearance\n");
    fresh_disk();
    village(1, 8, "Lea");
    {
        int was = tone(4), original = st_original(g_records[4]);
        int pick = (was + 3) % (g_tones + 1);
        check(st_set(g_records[4], pick) == 1 && tone(4) == pick, "a chosen tone is kept");
        check(st_original(g_records[4]) == original, "the original tone stays what it was (Reset to original)");
        new_session();
        g_slot = 1;
        check(tone(4) == pick, "and read back by a new session");
        check(st_set(g_records[4], 16) == 0 && tone(4) == pick, "a tone above 15 changes nothing");
        g_records[5][0] = 0;
        check(st_set(g_records[5], 1) == 0, "a record nobody holds changes nothing");
        g_records[5][0] = 1;
        g_fail_writes = 1;
        check(st_set(g_records[4], 0) == 0 && tone(4) == pick, "a set that cannot be written changes nothing");
        g_fail_writes = 0;
    }
    {
        const unsigned char *many[3];
        int tones[3];
        many[0] = g_records[0]; many[1] = g_records[1]; many[2] = g_records[2];
        tones[0] = 1; tones[1] = 2; tones[2] = 3;
        check(st_set_many(many, tones, 3) == 1, "Change Appearance for All: three tones in one write");
        check(tone(0) == 1 && tone(1) == 2 && tone(2) == 3, "each villager has its own");
        tones[0] = 7; tones[1] = 7; tones[2] = 7;
        g_fail_writes = 1;
        check(st_set_many(many, tones, 3) == 0 && tone(0) == 1 && tone(2) == 3, "a failed batch changes nobody");
        g_fail_writes = 0;
    }

    printf("copied files and another village's file\n");
    file_path(1, path);
    file_path(2, other);
    got = read_file(path, buf, sizeof buf);
    write_file(other, buf, got);
    new_session();
    g_slot = 2;
    check(tone(0) == 1 && tone(2) == 3, "a copy in another slot follows the same villagers");
    new_session();
    g_slot = 2;
    founders(8, "Zed");                        /* another village in slot 2 */
    settle();
    got = read_file(other, buf, sizeof buf);
    check(count_files(2, "Skin Tones - Save 2.dat.another-village-") == 1,
          "the other village's file is moved aside, never written over, before its own tones are written");
    check(got == 12 + 256 * 12 && tone(0) >= 0, "and the new village's founders have tones of their own");

    printf("a broken file\n");
    fresh_disk();
    new_session();
    g_slot = 3;
    founders(6, "Bo");
    file_path(3, path);
    memset(buf, 0, sizeof buf);
    u = 0x31545356u;
    memcpy(buf, &u, 4);
    u = 1;
    memcpy(buf + 4, &u, 4);
    u = 256;
    memcpy(buf + 8, &u, 4);
    write_file(path, buf, 12 + 256 * 12 - 1);
    check(tone(1) == -1, "a file of the wrong size gives no tones");
    check(count_files(3, "Skin Tones - Save 3.dat.unreadable-") == 1, "and is set aside intact");

    printf("Start Over\n");
    fresh_disk();
    village(4, 12, "Old");
    st_set(g_records[5], 3);
    file_path(4, path);
    check(exists(path), "(the slot has its file)");
    vv_reset_slot_state(1, 4, "Village: Test (Save 4)\n");
    check(!exists(path), "Start Over deletes the slot's Skin Tones file");
    founders(5, "New");
    settle();
    check(tone(0) >= 0 && tone(4) >= 0, "the new founders are given random tones of their own");
    check(exists(path), "in a new file");

    remove_tree(g_root);
    printf("failures: %d\n", failures);
    return failures;
}
