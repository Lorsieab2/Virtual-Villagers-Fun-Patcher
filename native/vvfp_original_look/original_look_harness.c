/* The original looks' per-save file against real files on disk (tests/test_original_look.py runs it through
   scripts/build_original_look_harness.ps1).

   The companion's records (original_look_records.inc: the real games' layouts and identity), its store
   (original_look_store.inc) and the Start Over reset (native/shared/save_reset.c) are compiled here
   unchanged; only what they ask of the game is replaced: the save slot, a village of records laid out as the
   game's own, the Origins companion's mask, the game's save time, and the save folder -- a fresh folder
   under %TEMP%, never the player's Documents\LDW.

   With no argument it proves, exit code 0 when every check passes: the first run over an existing save
   records everyone's look and writes nothing until the game saves the slot; the file's format; a birth is
   recorded at first sight; an original is never written over by a later change, a later session or a later
   first sight; nothing is recorded while the mask cannot be told; each original follows its villager through
   a packed reload, a reused record and a rename; an identity two villagers share is never recorded; the
   logs' part takes over a first-run snapshot, never a seen one, and a "not known" stops any first sight;
   a corrupt file is set aside intact and never overwritten; another village's file -- a copied save, or the
   title screen's seeded records -- is never replaced on what is on screen alone; a roster that never holds
   still is never bound; Start Over deletes the file; a 256-record build; a failed write leaves the file.

   "identities": prints each game's identity of a few records (src/vv_original_look.py must agree).
   "write <path>": writes the file of a known village to <path> (the Python reader must read it).
   "read <path>": reads a file the Python writer made for that same village, and prints what it answers. */
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
#define VV_FOREIGN_TICKS() g_ticks
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

/* ---- the save folder: %TEMP%\vvfp_original_look_harness_<pid> -------------------------------------- */

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

/* ---- the game: records laid out as New Believers' (or another game's), a slot, masks, a save time ---- */

#define OL_MAX 256
static int g_game = 5;
#include "original_look_records.inc"

#define MAX_STRIDE 0xE48Cu                      /* The Lost Children's, the longest */
static unsigned char *g_mem;
static int g_count = 150;
static int g_game_slot = 1;                     /* the game's own slot field */
static int g_origins = 1;                       /* the Origins companion is loaded */
static int g_masks[OL_MAX];                     /* the mask it keeps on each record */
static int g_save_exists[6];
static FILETIME g_save_time[6];

static int ol_game(void) { return g_game; }
static int ol_slots(void) { return g_count; }
static const unsigned char *ol_record(int i) {
    return i >= 0 && i < g_count ? g_mem + (size_t)i * LAYOUT[g_game].stride : NULL;
}
static int ol_slot_now(void) { return g_game_slot; }

static unsigned char *rec(int i) {
    return g_mem + (size_t)i * LAYOUT[g_game].stride;
}

static int ol_look(const unsigned char *r, int *head, int *body, int *mask) {
    if (!g_origins) {
        return 0;
    }
    memcpy(head, r + LAYOUT[g_game].head, 4);
    memcpy(body, r + LAYOUT[g_game].body, 4);
    *mask = g_masks[(r - g_mem) / LAYOUT[g_game].stride];
    return 1;
}

static int ol_save_written(int slot, FILETIME *out) {
    if (slot < 1 || slot > 5 || !g_save_exists[slot]) {
        return 0;
    }
    *out = g_save_time[slot];
    return 1;
}

#include "original_look_store.inc"

/* ---- the village -------------------------------------------------------------------------------- */

static void villager(int i, const char *name, int sex, const char *father, const char *mother, int head,
                     int body) {
    const ol_layout *l = &LAYOUT[g_game];
    unsigned char *r = rec(i);
    memset(r, 0, l->stride);
    r[l->present] = 1;
    lstrcpynA((char *)r + l->name, name, (int)l->name_bytes);
    memcpy(r + l->sex, &sex, 4);
    if (l->father != 0) {
        lstrcpynA((char *)r + l->father, father, 0x19);
        lstrcpynA((char *)r + l->mother, mother, 0x19);
    }
    memcpy(r + l->head, &head, 4);
    memcpy(r + l->body, &body, 4);
    g_masks[i] = 0;
}

static void set_look(int i, int head, int body) {
    memcpy(rec(i) + LAYOUT[g_game].head, &head, 4);
    memcpy(rec(i) + LAYOUT[g_game].body, &body, 4);
}

static void clear_village(void) {
    memset(g_mem, 0, (size_t)OL_MAX * MAX_STRIDE);
    memset(g_masks, 0, sizeof g_masks);
}

/* A village of `n` founders, Kai0, Kai1, ...: head i % 20, body i % 10. */
static void founders(int n, const char *stem) {
    int i;
    char name[32];
    clear_village();
    for (i = 0; i < n; ++i) {
        wsprintfA(name, "%s%d", stem, i);
        villager(i, name, i & 1, "", "", i % 20, i % 10);
    }
}

/* The game packs its records on a load: every held record moves down over the empty ones. */
static void pack(void) {
    int i, to = 0;
    size_t stride = LAYOUT[g_game].stride;
    for (i = 0; i < g_count; ++i) {
        if (rec(i)[LAYOUT[g_game].present]) {
            if (i != to) {
                memcpy(rec(to), rec(i), stride);
                g_masks[to] = g_masks[i];
                memset(rec(i), 0, stride);
                g_masks[i] = 0;
            }
            ++to;
        }
    }
}

/* A new session of the game: the DLL's memory is fresh, the files are what they were. */
static void new_session(void) {
    memset(g_source, 0, sizeof g_source);
    memset(g_id, 0, sizeof g_id);
    memset(g_head, 0, sizeof g_head);
    memset(g_body, 0, sizeof g_body);
    memset(g_mask, 0, sizeof g_mask);
    memset(g_logged, 0, sizeof g_logged);
    g_logged_count = 0;
    memset(g_roster, 0, sizeof g_roster);
    memset(g_stable, 0, sizeof g_stable);
    memset(g_at_bind, 0, sizeof g_at_bind);
    memset(g_candidate, 0, sizeof g_candidate);
    memset(&g_gate, 0, sizeof g_gate);
    g_state = OL_UNBOUND;
    g_slot = 0;
    g_foreign = 0;
    g_saved_known = 0;
    g_synced = 0;
    g_candidate_slot = 0;
    g_origins = 1;
    g_ticks += 10000;
}

/* A look a moment later. */
static int tick(void) {
    g_ticks += OL_SYNC_MS + 1;
    return ol_sync(0);
}

/* The village holds still long enough to be bound. */
static void settle(void) {
    (void)tick();
    g_ticks += OL_SETTLE_MS;
    (void)tick();
}

/* The game saves the slot (its .ldw written again). */
static void game_saves(int slot) {
    g_save_exists[slot] = 1;
    ++g_save_time[slot].dwLowDateTime;
    (void)tick();
}

/* The original of record i: head * 10000 + body * 10 + mask, or -1 when not known. */
static int original(int i) {
    int h, b, m;
    g_ticks += 1;
    if (!ol_get(rec(i), &h, &b, &m)) {
        return -1;
    }
    return h * 10000 + b * 10 + m;
}

static void file_path(int slot, char *out) {
    wsprintfA(out, "%s\\Virtual Villagers Fun Patcher\\Save %d\\Data\\Original Looks\\Original Looks - Save %d.dat",
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

/* Files in the Original Looks folder of `slot` whose name starts with `prefix` (the set-aside copies). */
static int count_files(int slot, const char *prefix) {
    char pattern[MAX_PATH];
    WIN32_FIND_DATAA found;
    HANDLE h;
    int n = 0;
    wsprintfA(pattern, "%s\\Virtual Villagers Fun Patcher\\Save %d\\Data\\Original Looks\\%s*", g_root, slot, prefix);
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
    memset(g_save_exists, 0, sizeof g_save_exists);
}

static unsigned int u32_at(const unsigned char *buf, DWORD at) {
    unsigned int v;
    memcpy(&v, buf + at, 4);
    return v;
}

/* Kai0..Kai9 of New Believers in slot 1, bound and saved: the village the Python cross-checks use. */
static void known_village(void) {
    g_game = 5;
    g_count = 150;
    new_session();
    g_game_slot = 1;
    founders(10, "Kai");
    g_masks[4] = 3;
    g_save_exists[1] = 1;
    settle();
    game_saves(1);
}

/* ---- the modes the Python tests drive ------------------------------------------------------------- */

static int print_identities(void) {
    int game;
    for (game = 1; game <= 5; ++game) {
        g_game = game;
        clear_village();
        villager(0, "Kai", 1, "Aru", "Malia", 3, 4);
        villager(1, "Leilani Kahale", 0, "", "", 0, 0);
        villager(2, "Ana", 0, "Kaimana Alohilani", "Pua", 19, 9);
        if (game == 1) {
            int family = 7;
            memcpy(rec(0) + LAYOUT[1].family, &family, 4);
        }
        printf("IDENTITY %d 0 %u %u\n", game, ol_identity(rec(0)), ol_stable(rec(0)));
        printf("IDENTITY %d 1 %u %u\n", game, ol_identity(rec(1)), ol_stable(rec(1)));
        printf("IDENTITY %d 2 %u %u\n", game, ol_identity(rec(2)), ol_stable(rec(2)));
    }
    printf("CRC %u\n", ol_crc32((const unsigned char *)"123456789", 9));
    return 0;
}

static int write_known(const char *out) {
    char path[MAX_PATH];
    static unsigned char buf[OL_FILE_MAX];
    DWORD got;
    known_village();
    villager(10, "Baby", 0, "Kai0", "Kai1", 7, 3);   /* a birth: SEEN */
    (void)tick();
    file_path(1, path);
    got = read_file(path, buf, sizeof buf);
    if (got == 0xFFFFFFFFu) {
        return 1;
    }
    write_file(out, buf, got);
    return 0;
}

static int read_python(const char *in) {
    char path[MAX_PATH];
    static unsigned char buf[OL_FILE_MAX];
    DWORD got = read_file(in, buf, sizeof buf);
    int i;
    if (got == 0xFFFFFFFFu) {
        return 1;
    }
    g_game = 5;
    g_count = 150;
    new_session();
    g_game_slot = 1;
    founders(10, "Kai");
    g_masks[4] = 3;
    set_look(3, 15, 6);                         /* Kai3 was changed since: the logs know the original */
    g_save_exists[1] = 1;
    file_path(1, path);
    write_file(path, buf, got);
    settle();
    for (i = 0; i < 10; ++i) {
        int o = original(i);
        printf("ORIGINAL %d %d %d\n", i, o, g_source[i]);
    }
    return 0;
}

/* ---- the checks ----------------------------------------------------------------------------------- */

int main(int argc, char **argv) {
    char path[MAX_PATH], other[MAX_PATH];
    static unsigned char buf[OL_FILE_MAX], buf2[OL_FILE_MAX];
    DWORD got;
    char temp[MAX_PATH];
    unsigned int kai0;
    int result;
    g_mem = (unsigned char *)VirtualAlloc(NULL, (SIZE_T)OL_MAX * MAX_STRIDE, MEM_COMMIT | MEM_RESERVE,
                                          PAGE_READWRITE);
    if (g_mem == NULL) {
        return 2;
    }
    GetTempPathA(MAX_PATH, temp);
    wsprintfA(g_root, "%svvfp_original_look_harness_%lu", temp, GetCurrentProcessId());
    fresh_disk();
    if (argc >= 2 && lstrcmpA(argv[1], "identities") == 0) {
        result = print_identities();
        remove_tree(g_root);
        return result;
    }
    if (argc >= 3 && lstrcmpA(argv[1], "write") == 0) {
        result = write_known(argv[2]);
        remove_tree(g_root);
        return result;
    }
    if (argc >= 3 && lstrcmpA(argv[1], "read") == 0) {
        result = read_python(argv[2]);
        remove_tree(g_root);
        return result;
    }

    printf("the first run over an existing save\n");
    new_session();
    g_game_slot = 1;
    founders(10, "Kai");
    g_masks[4] = 3;
    g_save_exists[1] = 1;
    check(original(2) == -1, "nothing is known before the village has held still");
    settle();
    check(g_state == OL_PENDING, "a village with no file is kept in memory only");
    check(original(2) == 20020 && original(4) == 40043, "everyone's look is recorded at first sight, the mask too");
    check(g_source[2] == OL_FIRST_RUN, "...as FIRST RUN originals");
    file_path(1, path);
    check(!exists(path), "nothing is written before the game saves the slot");
    g_ticks += 60000;
    (void)tick();
    check(!exists(path), "...however long it waits");
    game_saves(1);
    check(g_state == OL_BOUND && exists(path), "the game's save of the slot confirms the village: the file is written");
    got = read_file(path, buf, sizeof buf);
    check(got == 28 + 150 * 20, "the file is 28 + 150 * 20 bytes, in the save's own Data\\Original Looks folder");
    check(u32_at(buf, 0) == 0x314C4F56u && u32_at(buf, 4) == 1 && u32_at(buf, 8) == 5 && u32_at(buf, 12) == 150
          && u32_at(buf, 16) == 0 && u32_at(buf, 20) == 0, "magic 'VOL1', version 1, the game, 150 records, no logs' part");
    check(u32_at(buf, got - 4) == ol_crc32(buf, got - 4), "the CRC-32 of everything before it at the end");
    check(u32_at(buf, 24 + 2 * 20) == ol_identity(rec(2)) && u32_at(buf, 24 + 2 * 20 + 4) == ol_identity(rec(2))
          && u32_at(buf, 24 + 2 * 20 + 8) == 2 && u32_at(buf, 24 + 2 * 20 + 12) == 2
          && buf[24 + 2 * 20 + 16] == 0 && buf[24 + 2 * 20 + 17] == OL_FIRST_RUN,
          "each record: roster, identity, head, body, mask, source");
    check(buf[24 + 4 * 20 + 16] == 3, "the mask the Origins companion keeps");
    check(u32_at(buf, 24 + 10 * 20) == 0 && u32_at(buf, 24 + 10 * 20 + 4) == 0, "an empty record keeps nothing");

    printf("recording at first sight\n");
    villager(10, "Baby", 0, "Kai0", "Kai1", 7, 3);
    (void)tick();
    check(original(10) == 70030 && g_source[10] == OL_SEEN, "a birth in play is recorded as SEEN");
    got = read_file(path, buf, sizeof buf);
    check(buf[24 + 10 * 20 + 17] == OL_SEEN && u32_at(buf, 24 + 10 * 20 + 8) == 7, "...and written at once");
    villager(11, "", 0, "", "", 5, 5);
    (void)tick();
    check(g_source[11] == OL_NONE, "a record not named yet is not seen yet");
    lstrcpyA((char *)rec(11) + LAYOUT[5].name, "Late");
    (void)tick();
    check(original(11) == 50050, "...and is, once the game names it");

    printf("an original is never written over\n");
    set_look(2, 15, 6);
    g_masks[2] = 4;
    (void)tick();
    check(original(2) == 20020, "Change Appearance afterwards: the original stays");
    new_session();
    g_game_slot = 1;
    settle();
    check(g_state == OL_BOUND, "a new session binds its own file at once");
    check(original(2) == 20020 && original(10) == 70030, "...and reads the originals back, not the new look");

    printf("nothing while the mask cannot be told\n");
    g_origins = 0;
    villager(12, "Nalu", 1, "Kai2", "Kai3", 9, 9);
    (void)tick();
    check(g_source[12] == OL_NONE, "the Origins companion not loaded: nothing recorded");
    g_origins = 1;
    (void)tick();
    check(original(12) == 90090, "recorded once it is");

    printf("following the villager\n");
    /* Kai1 dies; the save is reloaded packed: Kai3 is now in record 2. */
    rec(1)[LAYOUT[5].present] = 0;
    (void)tick();
    check(original(3) == 30030, "a death in play moves nobody");
    new_session();
    g_game_slot = 1;
    pack();
    check(lstrcmpA((char *)rec(2) + LAYOUT[5].name, "Kai3") == 0, "(the reload packed Kai3 into record 2)");
    settle();
    check(original(2) == 30030, "after the reload Kai3's original is on Kai3 in record 2");
    check(original(1) == 20020, "...and Kai2's on Kai2 in record 1");
    got = read_file(path, buf, sizeof buf);
    check(u32_at(buf, 24 + 2 * 20 + 8) == 3, "the moved table is written back at once");
    rec(3)[LAYOUT[5].present] = 0;           /* Kai4 (record 3) buried */
    (void)tick();
    check(g_source[3] != OL_NONE, "an empty record keeps the dead villager's original while nobody takes it");
    villager(3, "Newborn", 1, "Kai0", "Kai2", 11, 1);
    (void)tick();
    check(original(3) == 110010 && g_source[3] == OL_SEEN, "a newborn in a dead villager's record is seen as themselves");
    lstrcpyA((char *)rec(5) + LAYOUT[5].name, "Renamed");
    (void)tick();
    check(original(5) == 60060, "a renamed villager keeps the original");
    new_session();
    g_game_slot = 1;
    settle();
    check(original(5) == 60060, "...and after a reload, under the new name");
    rec(0)[LAYOUT[5].present] = 0;             /* Kai0 dies, and the game quits before the next look */
    new_session();
    g_game_slot = 1;
    pack();
    settle();
    check(g_state == OL_BOUND && original(0) == 20020,
          "a death the file missed shifts every rank: still this village's file, Kai2's original on Kai2");

    printf("an identity two villagers share\n");
    villager(20, "Twin", 0, "Kai0", "Kai2", 1, 1);
    villager(21, "Twin", 0, "Kai0", "Kai2", 2, 2);
    (void)tick();
    check(original(20) == -1 && original(21) == -1, "never recorded for either");

    printf("the logs' part (src/vv_original_look.py)\n");
    {
        const int kai6 = 6, kai7 = 7, baby = 10;
        fresh_disk();
        new_session();
        g_game_slot = 1;
        founders(10, "Kai");
        settle();
        game_saves(1);
        villager(baby, "Baby", 0, "Kai0", "Kai1", 7, 3);
        (void)tick();
        file_path(1, path);
        check(g_source[kai6] == OL_FIRST_RUN && g_source[baby] == OL_SEEN,
              "(Kai6 has a FIRST RUN original, Baby a SEEN one)");
        g_logged[0].id = ol_identity(rec(kai6));
        g_logged[0].head = 33;
        g_logged[0].body = 4;
        g_logged[0].mask = 2;
        g_logged[0].kind = OL_LOGGED_KNOWN;
        g_logged[1].id = ol_identity(rec(kai7));
        g_logged[1].kind = OL_LOGGED_UNKNOWN;
        g_logged[2].id = ol_identity(rec(baby));
        g_logged[2].head = 1;
        g_logged[2].kind = OL_LOGGED_KNOWN;
        g_logged_count = 3;
        check(ol_publish() == 1, "(a file with a logs' part, as Repair Saves & Logs leaves it)");
        new_session();
        g_game_slot = 1;
        settle();
        check(original(kai6) == 330042 && g_source[kai6] == OL_LOGS, "the logs' original takes over a first-run snapshot");
        set_look(kai6, 1, 1);
        (void)tick();
        new_session();
        g_game_slot = 1;
        settle();
        check(original(kai6) == 330042, "...and stays when the look changes again and the village reloads");
        check(original(kai7) == -1, "a logged \"not known\" removes a first-run snapshot");
        check(original(baby) == 70030, "a SEEN original is never replaced by the logs");
        rec(kai7)[LAYOUT[5].present] = 0;
        (void)tick();
        villager(kai7, "Kai7", 1, "", "", 7, 7);
        (void)tick();
        check(original(kai7) == -1, "and no first sight is ever recorded for that villager");
        got = read_file(path, buf, sizeof buf);
        check(u32_at(buf, 16) == 3 && got == 28 + 150 * 20 + 3 * 16, "the companion keeps the logs' part as it read it");
    }

    printf("the game's own changes are kept\n");
    fresh_disk();
    new_session();
    g_game_slot = 1;
    founders(6, "Kai");
    settle();
    game_saves(1);
    check(original(2) == 20020, "(Kai2's original: head 2, body 2)");
    check(ol_game_body(rec(2), 29) == 1, "the robe (the game's own writer) is told to the store");
    set_look(2, 2, 29);
    (void)tick();
    check(original(2) == 20290, "the game-made body is folded into the original; the head stays");
    file_path(1, path);
    got = read_file(path, buf, sizeof buf);
    check(u32_at(buf, 24 + 2 * 20 + 12) == 29, "...and written at once");
    set_look(2, 9, 9);
    (void)tick();
    check(original(2) == 20290, "a Change Appearance after it is not folded in");
    check(ol_game_body(rec(2), 29) == 0, "the same body again changes nothing");
    villager(6, "Newborn", 0, "Kai0", "Kai1", 4, 4);
    check(ol_game_body(rec(6), 12) == 0, "a villager not seen yet: left to the first sight");
    set_look(6, 4, 12);
    (void)tick();
    check(original(6) == 40120, "...which sees the game's body");
    new_session();
    g_game_slot = 1;
    check(ol_game_body(rec(2), 5) == 0, "no village bound: nothing");

    printf("a corrupt or missing file\n");
    {
        static const char *const WHAT[] = { "a wrong checksum", "a short file", "another version", "another game" };
        int k;
        for (k = 0; k < 4; ++k) {
            DWORD len;
            fresh_disk();
            new_session();
            g_game_slot = 3;
            founders(6, "Lea");
            g_save_exists[3] = 1;
            settle();
            game_saves(3);
            file_path(3, path);
            len = read_file(path, buf, sizeof buf);
            if (k == 0) {
                buf[30] ^= 1;
            } else if (k == 1) {
                len -= 1;
            } else if (k == 2) {
                buf[4] = 2;
            } else {
                buf[8] = 4;
            }
            if (k >= 2) {
                unsigned int crc = ol_crc32(buf, len - 4);
                memcpy(buf + len - 4, &crc, 4);
            }
            write_file(path, buf, len);
            new_session();
            g_game_slot = 3;
            settle();
            check(original(1) == 10010 && g_state == OL_PENDING, WHAT[k]);
            check(!exists(path) && count_files(3, "Original Looks - Save 3.dat.unreadable-") == 1,
                  "...is set aside intact, never read or overwritten");
            game_saves(3);
            check(exists(path) && count_files(3, "Original Looks - Save 3.dat.unreadable-") == 1,
                  "...and the village gets a new file only when the game saves it");
        }
        fresh_disk();
        new_session();
        g_game_slot = 3;
        founders(6, "Lea");
        settle();
        check(g_state == OL_PENDING && original(1) == 10010, "a missing file: the first run records everyone");
    }

    printf("another village's file\n");
    fresh_disk();
    new_session();
    g_game_slot = 2;
    founders(8, "Kai");
    settle();
    game_saves(2);
    file_path(2, other);
    check(exists(other), "(Kai's village has its file in slot 2)");
    kai0 = ol_identity(rec(0));
    /* A copied save: Zed's village now in slot 2. */
    new_session();
    g_game_slot = 2;
    founders(8, "Zed");
    settle();
    check(g_state == OL_PENDING && g_foreign, "another village's file is never bound");
    got = read_file(other, buf, sizeof buf);
    check(u32_at(buf, 24) == kai0, "the file is still Kai's");
    g_ticks += 60000;
    (void)tick();
    check(count_files(2, "Original Looks - Save 2.dat.another-village-") == 0, "...nor moved while the slot is not saved");
    game_saves(2);
    check(count_files(2, "Original Looks - Save 2.dat.another-village-") == 1 && exists(other),
          "the game's save of the slot: the other village's file is moved aside, this village's written");
    got = read_file(other, buf, sizeof buf);
    check(u32_at(buf, 24 + 4) == ol_identity(rec(0)), "the new file is this village's");

    printf("the title screen's seeded records\n");
    fresh_disk();
    new_session();
    g_game_slot = 1;
    founders(9, "Kai");
    settle();
    game_saves(1);
    villager(9, "Baby", 0, "Kai0", "Kai1", 7, 3);
    (void)tick();
    file_path(1, path);
    got = read_file(path, buf, sizeof buf);
    /* The next start: the slot field says 1, the records hold another slot's village. */
    new_session();
    g_game_slot = 1;
    founders(9, "Zed");
    settle();
    g_ticks += 600000;
    (void)tick();
    check(read_file(path, buf2, sizeof buf2) == got && memcmp(buf, buf2, got) == 0 && count_files(1, "Original Looks - Save 1.dat.another-village-") == 0,
          "the slot's own file is never touched while another village is on screen");
    founders(9, "Kai");
    villager(9, "Baby", 0, "Kai0", "Kai1", 7, 3);
    set_look(9, 12, 2);
    settle();
    check(g_state == OL_BOUND && original(9) == 70030, "the real village loads: its originals, as SEEN");

    printf("a roster that never holds still\n");
    fresh_disk();
    new_session();
    g_game_slot = 4;
    founders(5, "Run");
    {
        int k;
        for (k = 0; k < 20; ++k) {
            villager(5 + k, k & 1 ? "Odd" : "Even", k, "", "", k, k);
            g_ticks += OL_SETTLE_MS / 2;
            (void)tick();
        }
    }
    check(g_state == OL_UNBOUND && original(0) == -1, "is never bound, and nothing is recorded");

    printf("Start Over\n");
    fresh_disk();
    new_session();
    g_game_slot = 4;
    founders(12, "Old");
    settle();
    game_saves(4);
    file_path(4, path);
    check(exists(path), "(the slot has its file)");
    vv_reset_slot_state(5, 4, "Village: Test (Save 4)\n");
    check(!exists(path), "Start Over deletes the slot's Original Looks file");
    founders(5, "New");
    settle();
    check(original(0) == 0 && g_state == OL_PENDING, "the new founders are recorded in memory");
    check(!exists(path), "and nothing is written before their first save");
    game_saves(4);
    got = read_file(path, buf, sizeof buf);
    check(got == 28 + 150 * 20 && u32_at(buf, 24 + 4) == ol_identity(rec(0)), "then the new village's file");

    printf("a failed write\n");
    got = read_file(path, buf, sizeof buf);
    g_fail_writes = 1;
    villager(5, "Born", 0, "New0", "New1", 3, 3);
    (void)tick();
    check(read_file(path, buf2, sizeof buf2) == got && memcmp(buf, buf2, got) == 0,
          "a write that fails leaves the file as it was");
    g_fail_writes = 0;
    villager(6, "Born2", 1, "New0", "New1", 4, 4);
    (void)tick();
    got = read_file(path, buf, sizeof buf);
    check(buf[24 + 5 * 20 + 17] == OL_SEEN && buf[24 + 6 * 20 + 17] == OL_SEEN, "...and the next write carries everything");

    printf("no village\n");
    new_session();
    g_game_slot = 0;
    check(original(1) == -1, "no slot: nothing is known");
    g_game_slot = 1;
    clear_village();
    check(original(1) == -1, "nobody in the records: nothing is known");

    printf("256 records, and the other games' layouts\n");
    fresh_disk();
    new_session();
    g_count = 256;
    g_game_slot = 5;
    founders(200, "Big");
    settle();
    game_saves(5);
    file_path(5, path);
    check(read_file(path, buf, sizeof buf) == 28 + 256 * 20, "a 256-record build writes 256 entries");
    new_session();
    g_game_slot = 5;
    settle();
    check(original(199) == 190090, "and reads them back");
    {
        int game;
        for (game = 1; game <= 4; ++game) {
            char what[64];
            fresh_disk();
            g_game = game;
            g_count = game <= 2 ? 256 : 150;
            new_session();
            g_game_slot = 2;
            founders(7, "Ola");
            settle();
            game_saves(2);
            set_look(3, 18, 8);
            (void)tick();
            new_session();
            g_game_slot = 2;
            settle();
            wsprintfA(what, "game %d: the original kept and read back", game);
            check(original(3) == 30030 && g_state == OL_BOUND, what);
        }
        g_game = 5;
        g_count = 150;
    }

    remove_tree(g_root);
    printf("failures: %d\n", failures);
    return failures;
}
