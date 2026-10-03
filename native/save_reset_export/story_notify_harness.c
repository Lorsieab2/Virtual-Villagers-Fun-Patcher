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
 * file and can never be written back into the next village.
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

static HMODULE WINAPI harness_get_module(LPCSTR name) {
    ++g_modules_asked;
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

    reset_recorders(1, 1, 1, 1);
    ResetDeletedTribe(5, 0);
    ResetDeletedTribe(6, 1);
    check(g_notified == 0 && g_cause_notified == 0 && g_swept == 0 && g_modules_asked == 0,
          "an invalid game or slot is refused before anything");

    printf("\n%d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}
