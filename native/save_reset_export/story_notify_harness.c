/* Does deleting a tribe or starting over tell the story companion?
 *
 * A pick or custom island event queued in one village must never be
 * delivered into the next (Codex, PR #495). "VVFP Save Reset.dll"'s
 * ResetDeletedTribe runs on both Start Over and a tribe deletion, and tells
 * "VVFP Story Upgrades.dll" through its VvfpStoryVillageReset export -- only
 * when that DLL is already loaded, and never loading it.
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

static int g_story_loaded;
static int g_story_exports;
static char g_module_asked[64];
static char g_proc_asked[64];
static int g_notified;
static int g_notified_game;
static int g_notified_slot;
static int g_swept;
static int g_notified_before_sweep;

static void __stdcall fake_story_reset(int game, int slot) {
    ++g_notified;
    g_notified_game = game;
    g_notified_slot = slot;
    g_notified_before_sweep = g_swept == 0;
}

static HMODULE WINAPI harness_get_module(LPCSTR name) {
    lstrcpynA(g_module_asked, name, sizeof g_module_asked);
    return g_story_loaded ? (HMODULE)(UINT_PTR)0x10000000u : NULL;
}

static FARPROC WINAPI harness_get_proc(HMODULE module, LPCSTR name) {
    lstrcpynA(g_proc_asked, name, sizeof g_proc_asked);
    if (module != (HMODULE)(UINT_PTR)0x10000000u) {
        return NULL;
    }
    return g_story_exports ? (FARPROC)fake_story_reset : NULL;
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

static void reset_recorders(int loaded, int exports) {
    g_story_loaded = loaded;
    g_story_exports = exports;
    g_module_asked[0] = g_proc_asked[0] = '\0';
    g_notified = g_notified_game = g_notified_slot = g_swept = g_notified_before_sweep = 0;
}

int main(void) {
    int game;
    for (game = 1; game <= 5; ++game) {
        char what[96];
        reset_recorders(1, 1);
        ResetDeletedTribe(game, 2);
        wsprintfA(what, "THE STORY COMPANION IS TOLD THE VILLAGE IS GONE (game %d)", game);
        check(g_notified == 1 && g_notified_game == game && g_notified_slot == 2, what);
        check(g_notified_before_sweep && g_swept == 1, "told before the sweep, and the sweep still runs");
        check(lstrcmpA(g_module_asked, "VVFP Story Upgrades.dll") == 0
                  && lstrcmpA(g_proc_asked, "VvfpStoryVillageReset") == 0,
              "by its shipped name and export");
    }

    reset_recorders(0, 1);
    ResetDeletedTribe(5, 3);
    check(g_notified == 0 && g_proc_asked[0] == '\0' && g_swept == 1,
          "WITHOUT THE STORY COMPANION LOADED NOTHING IS CALLED");

    reset_recorders(1, 0);
    ResetDeletedTribe(5, 3);
    check(g_notified == 0 && g_swept == 1, "a story companion without the export is left alone");

    reset_recorders(1, 1);
    ResetDeletedTribe(5, 0);
    ResetDeletedTribe(6, 1);
    check(g_notified == 0 && g_swept == 0, "an invalid game or slot is refused before anything");

    printf("\n%d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}
