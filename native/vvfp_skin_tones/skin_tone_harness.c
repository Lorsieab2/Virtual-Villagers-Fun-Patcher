/* The skin tones' data DLL against real files on disk (tests/test_skin_tones.py runs it through
   scripts/build_skin_tone_harness.ps1).

   vvfp_skin_tones.c is compiled here unchanged with VVFP_SKIN_TONE_HARNESS, which replaces only what it asks
   of the game: the save slot and a village of records in New Believers' own layout.  The save folder is a
   fresh folder under %TEMP%, never the player's Documents\LDW.

   Proves: founders and arrivals get a random tone, every tone turning up; a tone is published to
   "<save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\Skin Tones\Skin Tones - Save <S>.dat" in the
   documented shape and read back by a new session; it follows its villager when a load packs the records;
   a baby that names its parents gets a tone by the head rule on theirs; the tone rolled at a conception is
   what the held baby shows and exactly what the newborn gets, also when the father is gone by then, and is
   spent afterwards; twins are alike; a parent not known counts as the other; Change Appearance's set, the
   chosen "Game's own", the Revive read and write; a set that cannot be written changes nothing.  It also
   prints the rule itself for every case (INHERIT lines) for the test to compare with the Python rule.
   Exit code 0 when every check passes. */
#include <stdio.h>
#include <stdlib.h>
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

static int failures;
static char g_root[MAX_PATH];

static void check(int condition, const char *what) {
    printf("  [%s] %s\n", condition ? "PASS" : "FAIL", what);
    if (!condition) {
        ++failures;
    }
}

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

#define VVFP_SKIN_TONE_HARNESS
#include "vvfp_skin_tones.c"

#define GAME 5
#define COUNT 150
#define N VVFP_SKIN_TONE_COUNT

static unsigned char *rec(int i) {
    return g_harness_records + (size_t)i * LAYOUT[GAME].stride;
}

static void villager(int i, const char *name, int age, const char *father, const char *mother) {
    const st_layout *l = &LAYOUT[GAME];
    unsigned char *r = rec(i);
    memset(r, 0, l->stride);
    r[l->present] = 1;
    lstrcpynA((char *)r + l->name, name, (int)l->name_bytes);
    *(int *)(r + l->sex) = i & 1;
    *(int *)(r + l->age) = age;
    lstrcpynA((char *)r + l->father, father, (int)ST_PARENT_BYTES);
    lstrcpynA((char *)r + l->mother, mother, (int)ST_PARENT_BYTES);
}

static void gone(int i) {
    memset(rec(i), 0, LAYOUT[GAME].stride);
}

static void clear_village(void) {
    memset(g_harness_records, 0, (size_t)COUNT * LAYOUT[GAME].stride);
}

static void founders(int n, const char *stem) {
    int i;
    char name[32];
    clear_village();
    for (i = 0; i < n; ++i) {
        wsprintfA(name, "%s%d", stem, i);
        villager(i, name, 400 + i, "", "");
    }
}

static void pack(void) {
    int i, to = 0;
    size_t stride = LAYOUT[GAME].stride;
    for (i = 0; i < COUNT; ++i) {
        if (rec(i)[LAYOUT[GAME].present]) {
            if (i != to) {
                memcpy(rec(to), rec(i), stride);
                memset(rec(i), 0, stride);
            }
            ++to;
        }
    }
}

static void new_session(void) {
    memset(g_look, 0, sizeof g_look);
    memset(g_second, 0, sizeof g_second);
    memset(g_look_id, 0, sizeof g_look_id);
    memset(g_roster, 0, sizeof g_roster);
    memset(g_stable, 0, sizeof g_stable);
    memset(&g_gate, 0, sizeof g_gate);
    g_have_roster = 0;
    g_sync_tried = 0;
    g_sync_tick = 0;
    g_slot = 0;
    g_foreign = 0;
    g_give_tried = 0;
    g_ticks += 10000;
}

static void later(void) {
    g_ticks += HL_SYNC_MS + 1;
}

static int tone(int i) {
    later();
    return VvfpSkinToneGet(GAME, rec(i));
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

static void fresh_village(int slot, const char *stem, unsigned int seed) {
    g_harness_slot = slot;
    g_seed = seed;
    new_session();
    founders(12, stem);
}

int main(void) {
    static unsigned char file[4096];
    static int seen[N + 1], near_parents, births;
    char path[MAX_PATH], name[32];
    int i, k, a, b, t, ok;
    unsigned int f, m, r100, r3, rn;
    DWORD got;
    static const unsigned int R100[5] = { 0u, 4u, 5u, 50u, 99u };

    GetTempPathA(MAX_PATH, g_root);
    wsprintfA(g_root + lstrlenA(g_root), "vvfp_skin_tone_harness_%lu", GetCurrentProcessId());
    remove_tree(g_root);
    g_harness_records = (unsigned char *)calloc(COUNT, LAYOUT[GAME].stride);
    g_harness_count = COUNT;
    VvfpStartup(GAME, 0);
    check(VvfpSkinToneInstalled(GAME) == 1 && VvfpSkinToneInstalled(4) == 0, "the DLL keeps this game's tones only");
    check(VvfpSkinToneDrawn(GAME) == 0, "no draw follows a tone until a draw companion says so");
    check(VvfpSkinToneCount() == N, "ten tones");

    /* The rule, every case. */
    for (f = 0; f <= 11; ++f) {
        for (m = 0; m <= 11; ++m) {
            for (k = 0; k < 5; ++k) {
                r100 = R100[k];
                for (r3 = 0; r3 < 3; ++r3) {
                    for (rn = 0; rn < 3; ++rn) {
                        printf("INHERIT %u %u %u %u %u %d\n", f, m, r100, r3, rn * 4u,
                               VvfpSkinToneInherit((int)f, (int)m, r100, r3, rn * 4u));
                    }
                }
            }
        }
    }

    /* The preferred-tone rule, every case (RANDOM lines, compared with src/vv_skin_tones.py random_tone). */
    for (f = 0; f <= 11; ++f) {
        for (k = 0; k < 100; k += 3) {
            for (rn = 0; rn < 12; ++rn) {
                printf("RANDOM %u %u %u %d\n", f, k, rn * 7u, VvfpSkinToneRandom((int)f, k, rn * 7u));
            }
        }
    }
    check(VvfpSkinTonePreferred() == 0, "no choice file: no preferred tone");

    printf("Founders and arrivals\n");
    for (k = 0; k < 40; ++k) {
        wsprintfA(name, "F%d_", k);
        fresh_village(1 + k % 5, name, 1000u + (unsigned int)k * 7919u);
        for (i = 0; i < 12; ++i) {
            t = tone(i);
            if (t >= 1 && t <= N) {
                ++seen[t];
            } else {
                ++seen[0];
            }
        }
    }
    ok = seen[0] == 0;
    for (i = 1; i <= N; ++i) {
        ok = ok && seen[i] >= 20;               /* 480 founders over ten tones: about 48 each */
    }
    check(ok, "every founder gets a tone 1..10, and every tone turns up");

    remove_tree(g_root);
    fresh_village(1, "Ann", 4242u);
    for (i = 0; i < 12; ++i) {
        seen[0] = tone(i);
    }
    file_path(1, path);
    got = read_file(path, file, sizeof file);
    check(got == 12u + COUNT * 10u && memcmp(file, "VST2", 4) == 0 && *(unsigned int *)(file + 4) == GAME
          && *(unsigned int *)(file + 8) == COUNT, "the file: 'VST2', the game, the count, 12 + count x 10 bytes");
    ok = 1;
    for (i = 0; i < 12; ++i) {
        ok = ok && (file[12 + COUNT * 8 + i] & 0x0F) == VvfpSkinToneGet(GAME, rec(i))
             && file[12 + COUNT * 9 + i] == VvfpSkinToneGet(GAME, rec(i))
             && VvfpSkinToneBirth(GAME, rec(i)) == VvfpSkinToneGet(GAME, rec(i));
    }
    check(ok, "the file holds each villager's tone, and the same as their birth tone");
    {
        /* The first layout, 'VST1' (one byte each): still read; the tones it holds are the birth tones. */
        static unsigned char old[4096];
        HANDLE h;
        DWORD wrote;
        memcpy(old, file, 12u + COUNT * 9u);
        memcpy(old, "VST1", 4);
        old[12 + COUNT * 8 + 3] = 6;
        h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
        WriteFile(h, old, 12u + COUNT * 9u, &wrote, NULL);
        CloseHandle(h);
        new_session();
        check(tone(3) == 6 && VvfpSkinToneBirth(GAME, rec(3)) == 6, "a 'VST1' file is read: its tones, and they are the birth tones");
        later();
        (void)VvfpSkinToneSet(GAME, rec(3), 6);
        got = read_file(path, file, sizeof file);
        check(got == 12u + COUNT * 10u && memcmp(file, "VST2", 4) == 0, "and it is written again as 'VST2'");
    }
    a = tone(3);
    b = tone(7);
    new_session();
    check(tone(3) == a && tone(7) == b, "a new session reads the same tones back");
    villager(12, "Newcomer", 500, "", "");
    t = tone(12);
    check(t >= 1 && t <= N && tone(3) == a, "an arrival gets a tone; nobody else's changes");
    check(tone(12) == t, "and keeps it");

    printf("Following the villager\n");
    k = tone(2);
    gone(1);
    gone(4);
    pack();
    new_session();
    check(tone(1) == k && tone(5) == b && tone(2) == a, "after a pack, each tone is still its villager's");
    check(VvfpSkinToneBirth(GAME, rec(1)) == k && VvfpSkinToneBirth(GAME, rec(5)) == b, "and so is each birth tone");

    printf("Chosen in Change Appearance\n");
    k = VvfpSkinToneBirth(GAME, rec(0));
    check(VvfpSkinToneSet(GAME, rec(0), k == 9 ? 8 : 9) == 1 && tone(0) == (k == 9 ? 8 : 9), "a tone is set");
    check(VvfpSkinToneBirth(GAME, rec(0)) == k, "the birth tone is not changed by it");
    new_session();
    check(VvfpSkinToneBirth(GAME, rec(0)) == k && tone(0) == (k == 9 ? 8 : 9), "both are in the file");
    check(VvfpSkinToneReset(GAME, rec(0)) == 1 && tone(0) == k, "Reset to birth tone puts it back");
    (void)VvfpSkinToneSet(GAME, rec(0), 9);
    check(VvfpSkinToneSet(GAME, rec(0), 11) == 0 && VvfpSkinToneSet(GAME, rec(0), 0) == 0 && tone(0) == 9,
          "a number that is no tone is refused");
    check(VvfpSkinToneSet(GAME, rec(0), VVFP_SKIN_TONE_GAMES_OWN) == 1 && tone(0) == 0
          && (VvfpSkinToneOf(GAME, rec(0)) & 0xFF) == VVFP_SKIN_TONE_GAMES_OWN
          && VvfpSkinToneBirth(GAME, rec(0)) == k, "Game's own, chosen: drawn with the game's own art, and kept; the birth tone stays");
    later();
    check(tone(0) == 0, "a chosen Game's own is not given a random tone again");
    {
        const void *both[2];
        int tones2[2] = { 2, 8 };
        both[0] = rec(0);
        both[1] = rec(1);
        check(VvfpSkinToneSetMany(GAME, both, tones2, 2) == 1 && tone(0) == 2 && tone(1) == 8, "two set in one write");
    }
    g_fail_writes = 1;
    check(VvfpSkinToneSet(GAME, rec(0), 5) == 0, "a set that cannot be written is refused");
    g_fail_writes = 0;
    check(tone(0) == 2, "and changed nothing");

    printf("The Revive read and write\n");
    a = VvfpSkinToneOf(GAME, rec(1));
    check((a & 0xFF) == 8 && (a >> 8) == VvfpSkinToneBirth(GAME, rec(1)) && VvfpSkinToneGive(GAME, rec(2), a) == 1
          && VvfpSkinToneOf(GAME, rec(2)) == a,
          "what VvfpSkinToneOf reads (tone and birth tone) is handed to another villager with VvfpSkinToneGive");
    check(VvfpSkinToneGive(GAME, rec(2), 0x10000 | a) == 0 && VvfpSkinToneGive(GAME, rec(2), (11 << 8) | 3) == 0,
          "a number that is not one of its own is refused");

    printf("Babies\n");
    /* rec 0 is the father (tone 2), rec 1 the mother (tone 8): the head rule gives 4, 5 or 6 on 95%. */
    births = near_parents = 0;
    for (k = 0; k < 300; ++k) {
        wsprintfA(name, "Baby%d", k);
        villager(20, name, 0, (const char *)rec(0) + LAYOUT[GAME].name, (const char *)rec(1) + LAYOUT[GAME].name);
        t = tone(20);
        ++births;
        if (t >= 4 && t <= 6) {
            ++near_parents;
        }
        if (t < 1 || t > N) {
            near_parents = -100000;
        }
        gone(20);
        later();
        (void)tone(0);
    }
    check(near_parents >= 270 && near_parents < 300,
          "a baby that names its parents: their average +-1 on about 95% (the head rule), any tone on the rest");

    t = VvfpSkinToneConceived(GAME, rec(1), rec(0));
    check(t >= 1 && t <= N && VvfpSkinTonePending(GAME, rec(1)) == t, "a conception rolls the baby's tone and keeps it on the mother");
    check(tone(1) == 8, "her own tone is untouched");
    new_session();
    check(VvfpSkinTonePending(GAME, rec(1)) == t, "the promise is in the file");
    {
        char father_name[32];
        lstrcpyA(father_name, (const char *)rec(0) + LAYOUT[GAME].name);
        VvfpSkinToneSet(GAME, rec(0), 10);      /* the father changes afterwards: the promise does not */
        gone(0);                                /* ... and then he is gone */
        villager(20, "Promised", 0, father_name, (const char *)rec(1) + LAYOUT[GAME].name);
        villager(21, "Twin", 0, father_name, (const char *)rec(1) + LAYOUT[GAME].name);
        check(tone(20) == t && VvfpSkinToneBirth(GAME, rec(20)) == t,
              "the newborn gets exactly the tone rolled at the conception, the father gone or not; it is the birth tone");
        check(tone(21) == t, "a twin is the same");
        later();
        check(VvfpSkinTonePending(GAME, rec(1)) == 0, "the promise is spent");
    }

    /* A parent not known: only the mother is in the village. */
    births = near_parents = 0;
    for (k = 0; k < 200; ++k) {
        wsprintfA(name, "Half%d", k);
        villager(22, name, 0, "Nobody Here", (const char *)rec(1) + LAYOUT[GAME].name);
        t = tone(22);
        if (t >= 7 && t <= 9) {
            ++near_parents;
        }
        gone(22);
        later();
        (void)tone(1);
    }
    check(near_parents >= 175, "a father who is not in the village: the mother's tone +-1");

    /* A New Home's way: the birth is told. */
    t = VvfpSkinToneConceived(GAME, rec(1), rec(2));
    villager(23, "Told", 0, "", "");
    check(VvfpSkinToneBorn(GAME, rec(23), rec(1), NULL, 0) == t && VvfpSkinToneOf(GAME, rec(23)) == (t | (t << 8)),
          "a birth that is told gives the promised tone at once, and it is the birth tone");
    villager(24, "ToldTwin", 0, "", "");
    check(VvfpSkinToneBorn(GAME, rec(24), rec(1), rec(23), 1) == t && VvfpSkinTonePending(GAME, rec(1)) == 0,
          "the second baby copies the first, and the last one spends the promise");

    remove_tree(g_root);
    printf("%s\n", failures ? "FAILED" : "ALL PASSED");
    return failures != 0;
}
