/* The story traits' per-save file against real files on disk (tests/test_story_traits_file.py runs it through
   scripts/build_story_traits_harness.ps1).

   The companion's trait store (story_traits.inc: "The Quiet Hands" gives its villager the story trait "mute") is
   compiled here unchanged, with the shared helpers it uses; only what it asks of the game is replaced: the save
   slot, a village of records laid out at each game's own offsets (RS_LAYOUT, sex_change.h's strides and sex
   values), and the save folder -- a fresh folder under %TEMP%, never the player's Documents\LDW.

   Proves, in all five games: a trait is published to "<save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\
   Island Events\Island Event Story Traits - Save <S>.dat" in the documented format and read back by a new session
   for that villager only; it follows the villager when a reload packs the records after a death; a newborn in the
   dead villager's record never inherits it; it stays through a rename in play (a title or mask writing the name);
   it follows a sex change in play and after a reload, also when the save was not saved after the change (the
   Sex Changes log); another village's file is never replaced.  Exit code 0 when every check passes. */
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

/* ---- the save folder: %TEMP%\vvfp_story_traits_harness_<pid> ---------------------------------------- */

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

#include "../shared/villager_rekey.h"
#include "../shared/sex_change.h"

/* ---- the game: a slot and a village of records at the game's own offsets ------------------------------ */

#define MAX_RECORDS 256
static unsigned char *g_records;            /* MAX_RECORDS records of the game's stride */
static unsigned char *g_saved;              /* a copy of a village's first records */
static unsigned char g_before[VV_SEX_RECORD_MAX];   /* a record as it was before a sex change */
static unsigned int g_stride;
static int g_count = 150;
static int g_slot = 1;

typedef struct {
    int record_count;
    const unsigned char *(*record)(int index);
    unsigned int off_dislikes;
    int pref_slots;
} ce_adapter;

static const unsigned char *harness_record(int i) {
    return i >= 0 && i < g_count ? g_records + (size_t)i * g_stride : NULL;
}

/* The dislikes: three ints at +0x100 (clear of every identity field) -- the harness's own place. */
#define H_DISLIKES 0x100u
static ce_adapter g_adapter = { 150, harness_record, H_DISLIKES, 3 };
static int g_game_now;

static const ce_adapter *ce_adapter_for(int game) {
    return game >= 1 && game <= 5 ? &g_adapter : NULL;
}

/* The games' preference lists (src/vv_cie_graph.py _PREFS_VV*): "talking" is entry 56 in The Lost Children .. New
   Believers; A New Home has no such word. */
#define CG_TRAIT_MUTE 1u
#define CG_MUTE_WORD "talking"
#define H_TALKING 56
static int cg_preference(const ce_adapter *a, const char *word) {
    (void)a;
    return g_game_now >= 2 && lstrcmpiA(word, CG_MUTE_WORD) == 0 ? H_TALKING : -1;
}

static int story_current_slot(int game) {
    (void)game;
    return g_slot;
}

#include "story_traits.inc"

#define MUTE 1u

static unsigned char *rec(int i) {
    return g_records + (size_t)i * g_stride;
}

/* A living villager in record i: a name, a sex, the parents' names (A New Home: a family number). */
static void villager(int game, int i, const char *name, int female) {
    const rs_layout *l = &RS_LAYOUT[game];
    unsigned char *r = rec(i);
    memset(r, 0, g_stride);
    r[l->present] = 1;
    memset(r + H_DISLIKES, 0xFF, 3 * sizeof(int));        /* no dislikes (-1 each) */
    memcpy(r + l->name, name, strlen(name));
    *(int *)(r + l->sex) = female ? VV_SEX_LAYOUT[game].female : VV_SEX_LAYOUT[game].male;
    if (l->family != 0) {
        *(unsigned int *)(r + l->family) = 7u + (unsigned int)i;
    } else {
        memcpy(r + l->father, "Kai", 3);
        memcpy(r + l->mother, "Lani", 4);
    }
}

static void village(int game, int n) {
    int i;
    char name[16];
    memset(g_records, 0, (size_t)MAX_RECORDS * g_stride);
    for (i = 0; i < n; ++i) {
        wsprintfA(name, "Villager%d", i);
        villager(game, i, name, i % 2);
    }
}

/* What a save and a reload do: the held records packed down in record order. */
static void pack(void) {
    int i, to = 0;
    for (i = 0; i < g_count; ++i) {
        if (rec(i)[RS_LAYOUT[rs_game].present]) {
            if (to != i) {
                memcpy(rec(to), rec(i), g_stride);
                memset(rec(i), 0, g_stride);
            }
            ++to;
        }
    }
}

/* A new session of the game: the companion's memory as at load. */
static void new_session(void) {
    rs_game = 0;
    rs_have_roster = rs_slot = rs_sync_tried = rs_foreign = 0;
    rs_sync_tick = 0;
    memset(&rs_gate, 0, sizeof rs_gate);
    memset(rs_handle, 0, sizeof rs_handle);
    memset(rs_id, 0, sizeof rs_id);
    memset(rs_roster, 0, sizeof rs_roster);
    memset(rs_stable_ids, 0, sizeof rs_stable_ids);
    memset(rs_traits, 0, sizeof rs_traits);
    vv_rekey_forget(g_slot);
    g_ticks += 10000;
}

static void later(void) {
    g_ticks += 1000;
}

static int mute(int game, int i) {
    later();
    return rs_has_trait(game, rec(i), MUTE);
}

static DWORD file_size(const char *path) {
    WIN32_FILE_ATTRIBUTE_DATA a;
    return GetFileAttributesExA(path, GetFileExInfoStandard, &a) ? a.nFileSizeLow : 0u;
}

/* What vv_sex_change_apply does: the field written, the line logged, the companion told (its
   VvfpVillagerSexChanged: rs_sex_changed).  `tell` 0: a change the companion never heard of. */
static void flip_sex(int game, int i, int tell) {
    const vv_sex_layout *l = &VV_SEX_LAYOUT[game];
    unsigned char *r = rec(i);
    memcpy(g_before, r, g_stride);
    *(int *)(r + l->sex) = vv_sex_female(game, r) ? l->male : l->female;
    (void)vv_sex_log_add(game, g_slot, r);
    if (tell) {
        (void)rs_sex_changed(game, r, g_before);
    }
}

static void one_game(int game) {
    char path[MAX_PATH], line[160];
    unsigned char head[12];
    unsigned int magic, gm, count, trait_row;
    HANDLE h;
    DWORD got = 0;
    int i, dead;

    printf("== game %d\n", game);
    g_stride = VV_SEX_LAYOUT[game].stride;
    g_count = g_adapter.record_count = 150;
    g_slot = game;                                /* a slot of its own: a fresh file and log */
    g_game_now = game;
    new_session();

    /* a villager who dislikes talking counts as mute where the game has the word, with no trait kept */
    village(game, 12);
    ((int *)(rec(9) + H_DISLIKES))[1] = H_TALKING;
    check(mute(game, 9) == (game >= 2), game >= 2 ? "a villager who dislikes talking is story-mute"
                                                  : "A New Home has no talking dislike: nobody is mute by it");
    new_session();

    /* written, in the documented format */
    village(game, 12);
    later();
    rs_set_trait(game, 5, MUTE);
    check(mute(game, 5), "the villager given the trait has it");
    check(!mute(game, 4) && !mute(game, 6), "nobody else has it");
    wsprintfA(line, "\\Virtual Villagers Fun Patcher\\Save %d\\Data\\Island Events\\Island Event Story Traits - Save "
              "%d.dat", g_slot, g_slot);
    check(rs_path(g_slot, path) && lstrlenA(path) > lstrlenA(line)
          && lstrcmpA(path + lstrlenA(path) - lstrlenA(line), line) == 0 && file_size(path) == RS_FILE_BYTES(150),
          "the file is written beside the save, 12 + 150 * 9 + 255 * 4 bytes");
    if (!(file_size(path) == RS_FILE_BYTES(150))) {
        printf("    (path %s, %lu bytes)\n", path, file_size(path));
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h != INVALID_HANDLE_VALUE) {
        (void)ReadFile(h, rs_file, sizeof rs_file, &got, NULL);
        CloseHandle(h);
    }
    memcpy(head, rs_file, 12);
    memcpy(&magic, head, 4);
    memcpy(&gm, head + 4, 4);
    memcpy(&count, head + 8, 4);
    check(magic == RS_MAGIC && gm == (unsigned int)game && count == 150u, "its header: 'VST1', the game, 150");
    trait_row = rs_file[12 + 150 * 8 + 5];
    check(trait_row != 0 && rs_file[12 + 150 * 9 + (trait_row - 1) * 4] == MUTE,
          "record 5's handle names a row holding bit 0, mute");

    /* a new session reads it back */
    new_session();
    check(mute(game, 5) && !mute(game, 4), "a new session reads the trait back for that villager only");

    /* a death, a save and a reload: the records pack, the trait follows its villager */
    rec(2)[RS_LAYOUT[game].present] = 0;
    pack();
    new_session();
    check(mute(game, 4) && !mute(game, 5), "after a death and a packed reload the trait is in the villager's new record");

    /* in play: the villager dies and a newborn takes the record -- it never inherits the trait */
    rec(4)[RS_LAYOUT[game].present] = 0;
    later();
    (void)mute(game, 4);
    villager(game, 4, "Newborn", 1);
    check(!mute(game, 4), "a newborn in the dead villager's record never inherits the trait");
    new_session();
    check(!mute(game, 4), "...nor after a reload");

    /* a rename in play (a title or a mask writing the name) keeps it */
    village(game, 12);
    new_session();
    later();
    rs_set_trait(game, 7, MUTE);
    memset(rec(7) + RS_LAYOUT[game].name, 0, RS_LAYOUT[game].name_bytes);
    memcpy(rec(7) + RS_LAYOUT[game].name, "Masked One", 10);
    check(mute(game, 7), "a rename in play (a mask or title on the name) keeps the trait");
    new_session();
    check(mute(game, 7), "...and after a reload");

    /* a sex change in play keeps it, and after a reload */
    (void)mute(game, 7);                          /* the game running: the table bound to the village */
    flip_sex(game, 7, 1);
    check(mute(game, 7), "a sex change in play keeps the trait");
    new_session();
    check(mute(game, 7), "...and after a reload");

    /* a sex change the save never saw the file written after: the log leads the file's identity to them */
    (void)mute(game, 7);
    flip_sex(game, 7, 1);                         /* the file follows the change in play */
    {
        const vv_sex_layout *sl = &VV_SEX_LAYOUT[game];   /* ...then the player restores the save before it */
        *(int *)(rec(7) + sl->sex) = vv_sex_female(game, rec(7)) ? sl->male : sl->female;
    }
    new_session();
    check(mute(game, 7), "a file written after a sex change still finds the villager in a save from before it");

    /* another village's file is never replaced */
    memcpy(g_saved, g_records, (size_t)12 * g_stride);
    for (dead = 0, i = 0; i < 12; ++i) {
        char other[16];
        wsprintfA(other, "Stranger%d", i);
        villager(game, i, other, i % 2);
    }
    new_session();
    check(!mute(game, 7), "another village does not take the trait");
    later();
    (void)mute(game, 3);
    check(file_size(path) == RS_FILE_BYTES(150) && rs_foreign, "another village's file is told and kept");
    memset(g_records, 0, (size_t)MAX_RECORDS * g_stride);
    memcpy(g_records, g_saved, (size_t)12 * g_stride);
    new_session();
    check(mute(game, 7) && !dead, "the first village's file still holds its villager's trait");
}

int main(void) {
    char temp[MAX_PATH];
    int game;
    GetTempPathA(MAX_PATH, temp);
    wsprintfA(g_root, "%svvfp_story_traits_harness_%lu", temp, GetCurrentProcessId());
    CreateDirectoryA(g_root, NULL);
    g_records = (unsigned char *)VirtualAlloc(NULL, (size_t)MAX_RECORDS * VV_SEX_RECORD_MAX, MEM_COMMIT | MEM_RESERVE,
                                              PAGE_READWRITE);
    g_saved = (unsigned char *)VirtualAlloc(NULL, (size_t)12 * VV_SEX_RECORD_MAX, MEM_COMMIT | MEM_RESERVE,
                                            PAGE_READWRITE);
    if (g_records == NULL || g_saved == NULL) {
        printf("no memory\n");
        return 2;
    }
    for (game = 1; game <= 5; ++game) {
        one_game(game);
    }
    printf("failures: %d\n", failures);
    return failures ? 1 : 0;
}
