/* Does deleting a tribe or starting over tell the story companion -- and
 * the Cause of Death companion?
 *
 * A pick or custom island event queued in one village must never be
 * delivered into the next (Codex, PR #495). "VVFP Save Reset.dll"'s
 * ResetDeletedTribe runs on both Start Over and a tribe deletion, and tells
 * "VVFP Story Upgrades.dll" through its VvfpStoryVillageReset export -- only
 * when that DLL is already loaded, and never loading it. It tells "VVFP Cause
 * of Death.dll" the same way (VvfpCauseVillageReset), so the graves table it
 * holds for the erased slot is dropped before the sweep deletes the slot's
 * file and can never be written back into the next village. And it tells
 * the game's Origins companion (VvfpOriginsVillageReset, under whichever
 * name that game ships it), so a Barrel of Babies or Island Event bought and
 * not yet delivered in the erased village never comes to the new one.
 *
 * This compiles the SHIPPED save_reset_export.c (included, not copied) with
 * the module lookups, the save folder and the sweep itself replaced by
 * recorders, so nothing on disk is read or deleted: the save folder answers
 * "unresolved", which the reset treats as "delete nothing".
 *
 * Build and run: scripts/build_story_notify_harness.ps1
 */
#include <windows.h>
#include <stdio.h>
#include <stddef.h>

#define STORY_MODULE ((HMODULE)(UINT_PTR)0x10000000u)
#define CAUSE_MODULE ((HMODULE)(UINT_PTR)0x11000000u)
#define ORIGINS_MODULE ((HMODULE)(UINT_PTR)0x12000000u)
#define AGING_MODULE ((HMODULE)(UINT_PTR)0x13000000u)
#define MAUSOLEUM_MODULE ((HMODULE)(UINT_PTR)0x14000000u)

/* The Heathens' graves at the mud hut (New Believers). */
static int g_mausoleum_loaded;
static int g_mausoleum_notified;
static int g_mausoleum_slot;
static int g_mausoleum_before_sweep;
static char g_mausoleum_proc_asked[64];

static int g_aging_loaded;
static int g_aging_notified;
static int g_aging_slot;
static int g_aging_before_sweep;
static char g_aging_proc_asked[64];

static int g_story_loaded;
static int g_story_exports;
static int g_cause_loaded;
static int g_cause_exports;
static char g_story_proc_asked[64];
static char g_cause_proc_asked[64];
static int g_modules_asked;
static int g_story_name_asked;
static int g_cause_name_asked;
static int g_notified;
static int g_notified_game;
static int g_notified_slot;
static int g_cause_notified;
static int g_cause_game;
static int g_cause_slot;
static int g_swept;
static int g_notified_before_sweep;
static int g_cause_before_sweep;
static const char *g_origins_name;     /* the name the Origins companion is loaded under, NULL: none */
static int g_origins_exports;
static char g_origins_proc_asked[64];
static int g_origins_notified;
static int g_origins_game;
static int g_origins_slot;
static int g_origins_before_sweep;

static void __stdcall fake_story_reset(int game, int slot) {
    ++g_notified;
    g_notified_game = game;
    g_notified_slot = slot;
    g_notified_before_sweep = g_swept == 0;
}

static void __stdcall fake_cause_reset(int game, int slot) {
    ++g_cause_notified;
    g_cause_game = game;
    g_cause_slot = slot;
    g_cause_before_sweep = g_swept == 0;
}

static void __stdcall fake_origins_reset(int game, int slot) {
    ++g_origins_notified;
    g_origins_game = game;
    g_origins_slot = slot;
    g_origins_before_sweep = g_swept == 0;
}

static void __stdcall fake_aging_reset(int game, int slot) {
    (void)game;
    ++g_aging_notified;
    g_aging_slot = slot;
    g_aging_before_sweep = g_swept == 0;
}

static void __stdcall fake_mausoleum_reset(int game, int slot) {
    (void)game;
    ++g_mausoleum_notified;
    g_mausoleum_slot = slot;
    g_mausoleum_before_sweep = g_swept == 0;
}

static HMODULE WINAPI harness_get_module(LPCSTR name) {
    ++g_modules_asked;
    if (g_origins_name != NULL && lstrcmpA(name, g_origins_name) == 0) {
        return ORIGINS_MODULE;
    }
    if (lstrcmpA(name, "VVFP Heathen Aging.dll") == 0) {
        return g_aging_loaded ? AGING_MODULE : NULL;
    }
    if (lstrcmpA(name, "VVFP Heathen Mausoleum.dll") == 0) {
        return g_mausoleum_loaded ? MAUSOLEUM_MODULE : NULL;
    }
    if (lstrcmpA(name, "VVFP Story Upgrades.dll") == 0) {
        ++g_story_name_asked;
        return g_story_loaded ? STORY_MODULE : NULL;
    }
    if (lstrcmpA(name, "VVFP Cause of Death.dll") == 0) {
        ++g_cause_name_asked;
        return g_cause_loaded ? CAUSE_MODULE : NULL;
    }
    return NULL;
}

static FARPROC WINAPI harness_get_proc(HMODULE module, LPCSTR name) {
    if (module == STORY_MODULE) {
        lstrcpynA(g_story_proc_asked, name, sizeof g_story_proc_asked);
        return g_story_exports ? (FARPROC)fake_story_reset : NULL;
    }
    if (module == CAUSE_MODULE) {
        lstrcpynA(g_cause_proc_asked, name, sizeof g_cause_proc_asked);
        return g_cause_exports ? (FARPROC)fake_cause_reset : NULL;
    }
    if (module == AGING_MODULE) {
        lstrcpynA(g_aging_proc_asked, name, sizeof g_aging_proc_asked);
        return (FARPROC)fake_aging_reset;
    }
    if (module == MAUSOLEUM_MODULE) {
        lstrcpynA(g_mausoleum_proc_asked, name, sizeof g_mausoleum_proc_asked);
        return (FARPROC)fake_mausoleum_reset;
    }
    if (module == ORIGINS_MODULE) {
        lstrcpynA(g_origins_proc_asked, name, sizeof g_origins_proc_asked);
        return g_origins_exports ? (FARPROC)fake_origins_reset : NULL;
    }
    return NULL;
}

int harness_reset_slot_state(int game, int slot, const char *village) {
    (void)game; (void)slot; (void)village;
    ++g_swept;
    return 0;
}

int harness_save_folder_w(wchar_t *out, int reserve) {
    (void)out; (void)reserve;
    return 0;
}

int harness_village_recall(char *out, size_t size) {
    (void)out; (void)size;
    return 0;
}

#define GetModuleHandleA harness_get_module
#define GetProcAddress harness_get_proc
#define vv_reset_slot_state harness_reset_slot_state
#define vv_save_folder_w harness_save_folder_w
#define vv_village_recall harness_village_recall
#include "save_reset_export.c"

static int failures = 0;

static void check(int condition, const char *what) {
    printf("  [%s] %s\n", condition ? "PASS" : "FAIL", what);
    if (!condition) {
        ++failures;
    }
}

static void reset_recorders(int story_loaded, int story_exports, int cause_loaded, int cause_exports) {
    g_story_loaded = story_loaded;
    g_story_exports = story_exports;
    g_cause_loaded = cause_loaded;
    g_cause_exports = cause_exports;
    g_story_proc_asked[0] = g_cause_proc_asked[0] = '\0';
    g_modules_asked = g_story_name_asked = g_cause_name_asked = 0;
    g_notified = g_notified_game = g_notified_slot = g_swept = g_notified_before_sweep = 0;
    g_cause_notified = g_cause_game = g_cause_slot = g_cause_before_sweep = 0;
    g_origins_name = NULL;
    g_origins_exports = 0;
    g_origins_proc_asked[0] = '\0';
    g_origins_notified = g_origins_game = g_origins_slot = g_origins_before_sweep = 0;
}

int main(void) {
    int game;
    for (game = 1; game <= 5; ++game) {
        char what[96];
        reset_recorders(1, 1, 1, 1);
        ResetDeletedTribe(game, 2);
        wsprintfA(what, "THE STORY COMPANION IS TOLD THE VILLAGE IS GONE (game %d)", game);
        check(g_notified == 1 && g_notified_game == game && g_notified_slot == 2, what);
        check(g_notified_before_sweep && g_swept == 1, "told before the sweep, and the sweep still runs");
        check(g_story_name_asked == 1 && lstrcmpA(g_story_proc_asked, "VvfpStoryVillageReset") == 0,
              "by its shipped name and export");
        wsprintfA(what, "THE CAUSE OF DEATH COMPANION IS TOLD THE VILLAGE IS GONE (game %d)", game);
        check(g_cause_notified == 1 && g_cause_game == game && g_cause_slot == 2, what);
        check(g_cause_before_sweep, "told before the sweep deletes its file");
        check(g_cause_name_asked == 1 && lstrcmpA(g_cause_proc_asked, "VvfpCauseVillageReset") == 0,
              "by its shipped name and export");
    }

    reset_recorders(0, 1, 0, 1);
    ResetDeletedTribe(5, 3);
    check(g_notified == 0 && g_story_proc_asked[0] == '\0' && g_swept == 1,
          "WITHOUT THE STORY COMPANION LOADED NOTHING IS CALLED");
    check(g_cause_notified == 0 && g_cause_proc_asked[0] == '\0',
          "WITHOUT THE CAUSE OF DEATH COMPANION LOADED NOTHING IS CALLED");

    reset_recorders(1, 0, 1, 0);
    ResetDeletedTribe(5, 3);
    check(g_notified == 0 && g_cause_notified == 0 && g_swept == 1,
          "companions without the export are left alone");

    reset_recorders(0, 0, 1, 1);
    ResetDeletedTribe(1, 4);
    check(g_notified == 0 && g_cause_notified == 1 && g_cause_slot == 4 && g_swept == 1,
          "either companion is told without the other");

    {
        /* Each game's Origins companion, under the name it ships as (data/vv*_origins_feature.json). */
        static const char *const names[5] = {
            "VVFP VV1 Origins Icons.dll", "VVFP VV2 Origins Icons.dll", "VVFP Origins Icons.dll",
            "VVFP VV4 Origins Icons.dll", "VVFP Origins Icons.dll"
        };
        for (game = 1; game <= 5; ++game) {
            char what[120];
            reset_recorders(1, 1, 1, 1);
            g_origins_name = names[game - 1];
            g_origins_exports = 1;
            ResetDeletedTribe(game, 3);
            wsprintfA(what, "THE ORIGINS COMPANION IS TOLD THE VILLAGE IS GONE (game %d, \"%s\")", game, names[game - 1]);
            check(g_origins_notified == 1 && g_origins_game == game && g_origins_slot == 3
                  && lstrcmpA(g_origins_proc_asked, "VvfpOriginsVillageReset") == 0, what);
            check(g_origins_before_sweep && g_swept == 1, "told before the sweep, and the sweep still runs");
        }
        reset_recorders(1, 1, 1, 1);
        g_origins_name = names[0];
        ResetDeletedTribe(1, 3);
        check(g_origins_notified == 0 && g_swept == 1 && g_notified == 1,
              "an Origins companion without the export is left alone");
        reset_recorders(1, 1, 1, 1);
        ResetDeletedTribe(4, 3);
        check(g_origins_notified == 0 && g_origins_proc_asked[0] == '\0' && g_swept == 1,
              "WITHOUT THE ORIGINS COMPANION LOADED NOTHING IS CALLED");
    }

    /* The Heathen aging rows' companion (New Believers): told before the sweep deletes its file. */
    reset_recorders(1, 1, 1, 1);
    g_aging_loaded = 1;
    g_aging_notified = g_aging_slot = g_aging_before_sweep = 0;
    ResetDeletedTribe(5, 4);
    check(g_aging_notified == 1 && g_aging_slot == 4 && g_aging_before_sweep
          && lstrcmpA(g_aging_proc_asked, "VvfpHeathenAgingVillageReset") == 0,
          "THE HEATHEN AGING COMPANION IS TOLD THE VILLAGE IS GONE, before the sweep");
    g_aging_loaded = 0;
    g_aging_notified = 0;
    ResetDeletedTribe(5, 4);
    check(g_aging_notified == 0, "WITHOUT THE HEATHEN AGING COMPANION LOADED NOTHING IS CALLED");

    /* The Heathens' graves at the mud hut (New Believers): told before the sweep deletes its file. */
    reset_recorders(1, 1, 1, 1);
    g_mausoleum_loaded = 1;
    g_mausoleum_notified = g_mausoleum_slot = g_mausoleum_before_sweep = 0;
    ResetDeletedTribe(5, 2);
    check(g_mausoleum_notified == 1 && g_mausoleum_slot == 2 && g_mausoleum_before_sweep
          && lstrcmpA(g_mausoleum_proc_asked, "VvfpHeathenMausoleumVillageReset") == 0,
          "THE HEATHEN MAUSOLEUM COMPANION IS TOLD THE VILLAGE IS GONE, before the sweep");
    g_mausoleum_loaded = 0;
    g_mausoleum_notified = 0;
    ResetDeletedTribe(5, 2);
    check(g_mausoleum_notified == 0, "WITHOUT THE HEATHEN MAUSOLEUM COMPANION LOADED NOTHING IS CALLED");

    reset_recorders(1, 1, 1, 1);
    ResetDeletedTribe(5, 0);
    ResetDeletedTribe(6, 1);
    check(g_notified == 0 && g_cause_notified == 0 && g_swept == 0 && g_modules_asked == 0,
          "an invalid game or slot is refused before anything");

    printf("\n%d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}
