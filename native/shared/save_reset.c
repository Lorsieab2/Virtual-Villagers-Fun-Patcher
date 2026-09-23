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

/* Per-slot sidecars, by game. Every name here is one this patcher writes or
   has written -- the VV1 doubler file is retired and no longer written, but a
   copy left by an older build still belongs to the erased village -- and the
   game's own files are never listed and never deleted.

   The lists are per game rather than a single union because deleting a file
   another game owns would be a bug even though the folder differs: a player who
   renames two installs to the same basename would have them share a folder. Only
   the running game's own files are removed. */
/* Both the current folder and the loose pre-move names. A player who
   upgrades keeps whatever the previous build wrote beside their saves, and a
   sidecar left behind would restore a reset village's masks or parentage. */
static const char *const SIDECAR_FORMATS[5][6] = {
    /* VV1 */ { "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 1 Village Masks - Save %d.dat",
               "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 1 Origins Doublers - Save %d.dat",
               "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 1 Parentage Records - Save %d.dat",
               "%s\\vv1_masks_%d.dat", "%s\\vv1_doublers_%d.dat",
               "%s\\vv1_parents_%d.dat" },
    /* VV2 */ { "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 2 Village Masks - Save %d.dat",
               "%s\\vv2_masks_%d.dat", 0, 0, 0, 0 },
    /* VV3 */ { "%s\\Virtual Villagers Fun Patcher Data\\Village Masks - Save %d.dat",
               "%s\\vvfp_masks_%d.dat", 0, 0, 0, 0 },
    /* VV4 */ { "%s\\Virtual Villagers Fun Patcher Data\\Village Masks - Save %d.dat",
               "%s\\vvfp_masks_%d.dat", 0, 0, 0, 0 },
    /* VV5 */ { "%s\\Virtual Villagers Fun Patcher Data\\Village Masks - Save %d.dat",
               "%s\\vvfp_masks_%d.dat", 0, 0, 0, 0 },
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
    L"Virtual Villagers 1 Births and Conceptions Log",
    L"Virtual Villagers 2 Births and Conceptions Log",
    L"Virtual Villagers 3 Births and Conceptions Log",
    L"Virtual Villagers 4 Births and Conceptions Log",
    L"Virtual Villagers 5 Births and Conceptions Log",
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

/* Does this log file open with the header of the village being erased?

   The exporters write "Village: <name> (Save <n>)" as the first line of a new
   log, and that line is the only thing distinguishing one village's parentage
   log from another's: those files roll over by count rather than by slot, so
   the slot cannot address them.

   A file with no header is NOT matched. Logs written before headers existed
   cannot be attributed to any village, and deleting one on a guess would
   destroy history the player still wants. */
static int log_header_matches(const wchar_t *path, const char *village) {
    HANDLE f;
    char line[256];
    char want[256];
    DWORD got = 0;
    DWORD i;
    int n;

    if (village == NULL || village[0] == '\0') {
        return 0;
    }
    f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!ReadFile(f, line, sizeof(line) - 1, &got, NULL)) {
        CloseHandle(f);
        return 0;
    }
    CloseHandle(f);
    line[got] = '\0';
    for (i = 0; i < got; ++i) {
        if (line[i] == '\r' || line[i] == '\n') {
            line[i] = '\0';
            break;
        }
    }
    /* The published header carries its own trailing newline; compare first
       lines only. */
    lstrcpynA(want, village, (int)sizeof(want));
    n = lstrlenA(want);
    while (n > 0 && (want[n - 1] == '\n' || want[n - 1] == '\r')) {
        want[--n] = '\0';
    }
    if (want[0] == '\0') {
        return 0;
    }
    return lstrcmpA(line, want) == 0;
}

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

/* Resolve "<save folder>\\<sub>" WITHOUT creating any of it.

   vv_save_subfolder_w makes every missing component, which is right for a
   folder the exporters write to but wrong for a retired one: using it here
   would recreate an obsolete directory on every Start Over for players who
   never had one. Returns 0 when the folder does not exist, so the caller
   simply skips it. */
VV_RESET_STATIC int legacy_subfolder_w(wchar_t *out, const wchar_t *sub) {
    wchar_t root[MAX_PATH];
    if (out == NULL || sub == NULL || sub[0] == L'\0') {
        return 0;
    }
    if (!vv_save_folder_w(root, (int)wcslen(sub) + 1 + 64)) {
        return 0;
    }
    wsprintfW(out, L"%ls\\%ls", root, sub);
    return GetFileAttributesW(out) != INVALID_FILE_ATTRIBUTES;
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

int vv_reset_slot_state(int game, int slot, const char *village) {
    char folder[MAX_PATH];
    wchar_t folder_w[MAX_PATH];
    char path[MAX_PATH];
    wchar_t path_w[MAX_PATH];
    wchar_t sub_w[MAX_PATH];     /* the log subfolder the reset now targets */
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

    for (i = 0; i < 6; ++i) {
        const char *fmt = SIDECAR_FORMATS[game - 1][i];
        if (fmt == NULL) {
            continue;   /* a hole, not the end: the rows are not packed */
        }
        wsprintfA(path, fmt, folder, slot);
        removed += delete_if_present(path);
    }

    if (!vv_save_folder_w(folder_w, 64)) {
        return removed;         /* sidecars done; the logs need the wide form */
    }

    /* STATISTICS AND POPULATION ARE NUMBERED BY SLOT, NOT BY ROLL-OVER.
       build_output_paths formats save_id straight into the name, so the file
       for the village being erased is the one bearing this slot -- and every
       other numbered file belongs to a village that was NOT reset. Addressing
       them directly is what stops a reset of slot 1 destroying slots 2..5.

       An earlier version of this function walked every number and deleted what
       it found. Codex caught it on #380. */
    /* Village Statistics moved into the owner's log layout, so the reset
       follows it -- and still clears the pre-move copy, which a player who
       upgrades keeps loose in the save folder. Leaving that behind would
       survive a Start Over as a record of the village just erased, the
       same defect the parentage passes below already guard against.

       Both are addressed by SLOT, never by walking every number: a reset
       of slot 1 must not touch slots 2..5. */
    if (vv_save_subfolder_w(sub_w, L"Virtual Villagers Fun Patcher Logs\\Village Statistics", 64)) {
        wsprintfW(path_w, L"%ls\\Village Statistics - Save %d.txt", sub_w, slot);
        removed += delete_if_present_w(path_w);
    }
    /* The folder name before it was spelled out, probed but never
       recreated: a player who upgrades keeps whatever the previous build
       wrote, and a file left in a folder nothing writes to any more would
       survive a reset that was meant to clear it. */
    if (legacy_subfolder_w(sub_w, L"VVFP Logs\\Village Statistics")) {
        wsprintfW(path_w, L"%ls\\Village Statistics - Save %d.txt", sub_w, slot);
        removed += delete_if_present_w(path_w);
    }
    /* The pre-move location, probed and cleared but never recreated. */
    wsprintfW(path_w, L"%ls\\Village Statistics - Save %d.txt", folder_w, slot);
    removed += delete_if_present_w(path_w);
    /* The roster moved into the owner's log layout; the reset follows it.
       vv_save_subfolder_w creates the folder if absent, which is harmless
       here -- an empty folder is not a stale roster. */
    if (vv_save_subfolder_w(sub_w, L"Virtual Villagers Fun Patcher Logs\\Tribe Population", 64)) {
        wsprintfW(path_w, L"%ls\\Village Population %d.txt", sub_w, slot);
        removed += delete_if_present_w(path_w);
    }
    if (legacy_subfolder_w(sub_w, L"VVFP Logs\\Tribe Population")) {
        wsprintfW(path_w, L"%ls\\Village Population %d.txt", sub_w, slot);
        removed += delete_if_present_w(path_w);
    }

    /* PARENTAGE IS VILLAGE-SCOPED, SO IT IS MATCHED BY HEADER.
       Its files roll over by count rather than by slot, so the slot cannot
       address them. Each one opens with the header the exporter wrote, and a
       file is deleted only when that header is the village being erased.

       Without a village string nothing here is deleted. Guessing would mean
       deleting another village's history, and losing a header line is a far
       smaller harm than that. */
    if (village != NULL && village[0] != '\0') {
        /* Both the current location and the one it was renamed from.

           A player who upgrades keeps whatever the previous build wrote: in
           "Tribe Parental Records", under the old file name. Scanning only
           the new pair leaves those behind on a Start Over -- records of the
           village just erased, surviving in a folder nothing writes to any
           more, which is this function's contract broken quietly. Found in
           review.

           A build predating the rename cannot have written the new names and
           one following it cannot have written the old, so the two passes
           never contend for the same file. */
        /* Every folder these logs have EVER lived in. Index 0 is the one
           the exporter writes to now; the rest are retired and only probed.

           The folder was renamed twice: "VVFP Logs" spelled out to
           "Virtual Villagers Fun Patcher Logs" at the owner's request, and
           before that "Tribe Parental Records" renamed to "Births and
           Conceptions". A player can be upgrading from either, so all four
           combinations are swept. No build wrote more than one of them, so
           the passes never contend for the same file. */
        static const wchar_t *const FOLDERS[4] = {
            L"Virtual Villagers Fun Patcher Logs\\Births and Conceptions",
            L"Virtual Villagers Fun Patcher Logs\\Tribe Parental Records",
            L"VVFP Logs\\Births and Conceptions",
            L"VVFP Logs\\Tribe Parental Records"
        };
        static const wchar_t *const LEGACY_LOG[5] = {
            L"Virtual Villagers 1 Parentage Log",
            L"Virtual Villagers 2 Parentage Log",
            L"Virtual Villagers 3 Parentage Log",
            L"Virtual Villagers 4 Parentage Log",
            L"Virtual Villagers 5 Parentage Log"
        };
        int pass;
        for (pass = 0; pass < 4; ++pass) {
            /* The old FILE name went with the old FOLDER name, so the
               stem follows the folder rather than the pass number. */
            const wchar_t *stem = (pass % 2 == 0)
                ? PARENTAGE_LOG[game - 1] : LEGACY_LOG[game - 1];
            if (pass == 0) {
                /* The current folder, which the exporter writes to anyway. */
                if (!vv_save_subfolder_w(sub_w, FOLDERS[pass], 64)) {
                    continue;
                }
            } else if (!legacy_subfolder_w(sub_w, FOLDERS[pass])) {
                /* A RETIRED folder is only probed, never created: creating
                   it would litter every player who never had one. Absent
                   means there is nothing of that vintage to clean up. */
                continue;
            }
            for (i = 1; i <= MAX_LOG_FILES; ++i) {
                wsprintfW(path_w, L"%ls\\%ls %d.txt", sub_w, stem, i);
                if (GetFileAttributesW(path_w) == INVALID_FILE_ATTRIBUTES) {
                    break;      /* the exporter numbers without holes */
                }
                if (log_header_matches(path_w, village)) {
                    removed += delete_if_present_w(path_w);
                }
            }
        }
    }
    return removed;
}
