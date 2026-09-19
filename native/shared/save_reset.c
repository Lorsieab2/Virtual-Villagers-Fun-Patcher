/* See save_reset.h. Deletes this patcher's state for one erased village. */
#include "save_reset.h"
#include "save_folder.h"

#include <windows.h>

/* Counts paths refused before any filesystem call is made.
   DeleteFile fails on an empty path by itself, so the return value cannot
   distinguish this guard from its absence -- a mutation dropping the empty
   check survived testing for exactly that reason. This makes the refusal
   itself observable. */
int vv_reset_refused_paths = 0;

/* Per-slot sidecars, by game. Every name here is one this patcher writes; the
   game's own files are never listed and never deleted.

   The lists are per game rather than a single union because deleting a file
   another game owns would be a bug even though the folder differs: a player who
   renames two installs to the same basename would have them share a folder. Only
   the running game's own files are removed. */
static const char *const SIDECAR_FORMATS[5][3] = {
    /* VV1 */ { "%s\\vv1_masks_%d.dat", "%s\\vv1_doublers_%d.dat", 0 },
    /* VV2 */ { "%s\\vv2_masks_%d.dat", 0, 0 },
    /* VV3 */ { "%s\\vvfp_masks_%d.dat", 0, 0 },
    /* VV4 */ { "%s\\vvfp_masks_%d.dat", 0, 0 },
    /* VV5 */ { "%s\\vvfp_masks_%d.dat", 0, 0 },
};

/* The exported logs, which carry the village name in their first line and are
   numbered by roll-over rather than by slot.

   A log is village-scoped but not slot-scoped: select_log_file walks the
   numbered files and skips any whose header names a different village, so a
   dead village's log is already never appended to. Removing them on Start Over
   is what stops the new village silently continuing the old one's numbering,
   and it is what the owner asked for -- start over means the logs reset too.

   MAX_LOG_FILES bounds the walk. It matches the roll-over ceiling the exporters
   use, so a player with the maximum number of log files still has all of them
   removed, and a corrupt or hand-made file beyond that bound is left alone
   rather than guessed at. */
#define MAX_LOG_FILES 4096

static const wchar_t *const PARENTAGE_LOG[5] = {
    L"Virtual Villagers 1 Parentage Log",
    L"Virtual Villagers 2 Parentage Log",
    L"Virtual Villagers 3 Parentage Log",
    L"Virtual Villagers 4 Parentage Log",
    L"Virtual Villagers 5 Parentage Log",
};

/* Exposed to the harness under VV_RESET_TESTABLE so the empty-path guard can
   be called directly. It is unreachable at runtime -- every caller passes a
   formatted path -- but it is the last check before a DeleteFile, so it is
   tested rather than assumed. The production build keeps it static. */
#ifdef VV_RESET_TESTABLE
int vv_test_delete_if_present(const char *path);
#define VV_RESET_STATIC
#else
#define VV_RESET_STATIC static
#endif

VV_RESET_STATIC int delete_if_present(const char *path) {
    if (path == NULL || path[0] == '\0') {
        ++vv_reset_refused_paths;   /* refused before touching the filesystem */
        return 0;
    }
    if (DeleteFileA(path)) {
        return 1;
    }
    return 0;                   /* absent, or in use: not an error */
}

VV_RESET_STATIC int delete_if_present_w(const wchar_t *path) {
    if (path == NULL || path[0] == L'\0') {
        ++vv_reset_refused_paths;
        return 0;
    }
    if (DeleteFileW(path)) {
        return 1;
    }
    return 0;
}

int vv_reset_slot_state(int game, int slot) {
    char folder[MAX_PATH];
    wchar_t folder_w[MAX_PATH];
    char path[MAX_PATH];
    wchar_t path_w[MAX_PATH];
    int removed = 0;
    int i;

    /* Refuse anything that is not a real village slot. Slot 0 is the meta file
       and is not a village; a negative or out-of-range slot means the caller
       handed us something unexpected, and the answer to that is to do nothing
       rather than to delete a guess. */
    if (game < 1 || game > 5 || slot < 1 || slot > 5) {
        return -1;
    }
    /* Reserve the longest tail any name below appends. */
    if (!vv_save_folder(folder, 64)) {
        return -1;              /* unresolved path is never a deletion target */
    }

    for (i = 0; i < 3; ++i) {
        const char *fmt = SIDECAR_FORMATS[game - 1][i];
        if (fmt == NULL) {
            break;
        }
        wsprintfA(path, fmt, folder, slot);
        removed += delete_if_present(path);
    }

    if (!vv_save_folder_w(folder_w, 64)) {
        return removed;         /* sidecars already handled; logs need the wide form */
    }
    for (i = 1; i <= MAX_LOG_FILES; ++i) {
        int hit = 0;
        wsprintfW(path_w, L"%ls\\%ls %d.txt", folder_w, PARENTAGE_LOG[game - 1], i);
        hit += delete_if_present_w(path_w);
        wsprintfW(path_w, L"%ls\\Village Statistics - Save %d.txt", folder_w, i);
        hit += delete_if_present_w(path_w);
        wsprintfW(path_w, L"%ls\\Village Population %d.txt", folder_w, i);
        hit += delete_if_present_w(path_w);
        removed += hit;
        /* Stop at the first gap. The exporters number their files without
           holes, so a missing index means there are no more -- walking all 4096
           on every Start Over would stat twelve thousand paths for nothing. */
        if (hit == 0 && i > 1) {
            break;
        }
    }
    return removed;
}
