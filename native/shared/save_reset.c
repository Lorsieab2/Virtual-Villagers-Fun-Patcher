/* See save_reset.h. Deletes this patcher's state for one erased village. */
#include "save_reset.h"
#include "save_folder.h"
#define VV_DATA_SUBFOLDER_NAMES_ONLY   /* the folder names; nothing is moved here */
#include "data_subfolder.h"
#include "village_rename.h"

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
/* The Story / Cheat Upgrades custom titles (native/shared/custom_titles.h)
   are per slot in every game: the owner's rule is that the .dat follows the
   Start Over reset. */
#define CUSTOM_TITLES_FORMAT \
    "%s\\Virtual Villagers Fun Patcher Data\\Custom Titles\\Custom Titles - Save %d.dat"
/* The Cause of Death row (native/vvfp_cause_of_death), per slot so it
   follows Start Over: A New Home's and The Lost Children's graves (each
   grave's cause of death, and in A New Home its epitaph, which those games
   never keep), and in every game the village roster the Unaccounted
   Villagers log is reconciled against at each save. */
#define CAUSE_OF_DEATH_FORMAT(n) \
    "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers " n " Graves - Save %d.dat"
#define ROSTER_FORMAT(n) \
    "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers " n " Village Roster - Save %d.dat"
/* ...and that the slot's villagers who arrived before the Arrived record
   existed have theirs (native/shared/arrival_backfill.h), in its own
   "Arrivals" folder: the village started after the reset is asked again. */
#define ARRIVALS_FORMAT(n) \
    "%s\\Virtual Villagers Fun Patcher Data\\Arrivals\\Virtual Villagers " n " Arrivals Recorded - Save %d.dat"
/* ...and the same for the Birth records backfilled from the save (The Lost
   Children to New Believers; A New Home keeps no parents, so has none). */
#define BIRTHS_FORMAT(n) \
    "%s\\Virtual Villagers Fun Patcher Data\\Births\\Virtual Villagers " n " Births Recorded - Save %d.dat"
/* EACH KIND IN ITS OWN FOLDER (native/shared/data_subfolder.h). The masks,
   the graves, VV1's parentage records and the Unaccounted Villagers roster
   used to be written loose in "Virtual Villagers Fun Patcher Data" and now
   live in a folder each. A companion moves a loose file in when it first
   reads it -- but a file it could not move, or one for a slot never loaded
   since the upgrade, is still loose. Start Over removes the village's file
   at BOTH places, so neither copy can bring an erased village's state back. */
#define DATA_FORMAT(sub, name) \
    "%s\\Virtual Villagers Fun Patcher Data\\" sub "\\" name " - Save %d.dat"
/* ...and which graves already have their Death record in the Deaths log
   (native/vvfp_cause_of_death/cod_backfill.inc), deleted with that log.  It
   was never written loose: it has always been in its own "Deaths" folder. */
#define GRAVES_LOGGED_FORMAT(n) \
    "%s\\Virtual Villagers Fun Patcher Data\\Deaths\\Virtual Villagers " n " Graves Logged - Save %d.dat"
/* ...and the player's approval to repair the slot's village without asking
   (Repair Logs in the patcher window, src/vv_log_tools.py; used up by the
   game, native/shared/crosscheck_bridge.h): it was given for the village
   being erased, never for the one started after the reset. */
#define APPROVAL_FORMAT(n) \
    "%s\\Virtual Villagers Fun Patcher Data\\Cross-Check\\Virtual Villagers " n " Repair Approved - Save %d.dat"
#define SIDECAR_FORMAT_COUNT 16
static const char *const SIDECAR_FORMATS[5][SIDECAR_FORMAT_COUNT] = {
    /* VV1 */ { DATA_FORMAT(VV_DATA_SUB_MASKS, "Virtual Villagers 1 Village Masks"),
               "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 1 Village Masks - Save %d.dat",
               "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 1 Origins Doublers - Save %d.dat",
               DATA_FORMAT(VV_DATA_SUB_PARENTAGE, "Virtual Villagers 1 Parentage Records"),
               "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 1 Parentage Records - Save %d.dat",
               "%s\\vv1_masks_%d.dat", "%s\\vv1_doublers_%d.dat",
               "%s\\vv1_parents_%d.dat", CUSTOM_TITLES_FORMAT,
               DATA_FORMAT(VV_DATA_SUB_GRAVES, "Virtual Villagers 1 Graves"), CAUSE_OF_DEATH_FORMAT("1"),
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 1 Village Roster"),
               ROSTER_FORMAT("1"), GRAVES_LOGGED_FORMAT("1"), ARRIVALS_FORMAT("1"), APPROVAL_FORMAT("1") },
    /* VV2 */ { DATA_FORMAT(VV_DATA_SUB_MASKS, "Virtual Villagers 2 Village Masks"),
               "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 2 Village Masks - Save %d.dat",
               "%s\\vv2_masks_%d.dat", CUSTOM_TITLES_FORMAT,
               DATA_FORMAT(VV_DATA_SUB_GRAVES, "Virtual Villagers 2 Graves"), CAUSE_OF_DEATH_FORMAT("2"),
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 2 Village Roster"),
               ROSTER_FORMAT("2"), GRAVES_LOGGED_FORMAT("2"), ARRIVALS_FORMAT("2"), BIRTHS_FORMAT("2"),
               APPROVAL_FORMAT("2"), 0, 0, 0, 0 },
    /* VV3 */ { DATA_FORMAT(VV_DATA_SUB_MASKS, "Village Masks"),
               "%s\\Virtual Villagers Fun Patcher Data\\Village Masks - Save %d.dat",
               "%s\\vvfp_masks_%d.dat", CUSTOM_TITLES_FORMAT,
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 3 Village Roster"),
               ROSTER_FORMAT("3"), GRAVES_LOGGED_FORMAT("3"), ARRIVALS_FORMAT("3"), BIRTHS_FORMAT("3"),
               APPROVAL_FORMAT("3"), 0, 0, 0, 0, 0, 0 },
    /* VV4 */ { DATA_FORMAT(VV_DATA_SUB_MASKS, "Village Masks"),
               "%s\\Virtual Villagers Fun Patcher Data\\Village Masks - Save %d.dat",
               "%s\\vvfp_masks_%d.dat", CUSTOM_TITLES_FORMAT,
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 4 Village Roster"),
               ROSTER_FORMAT("4"), GRAVES_LOGGED_FORMAT("4"), ARRIVALS_FORMAT("4"), BIRTHS_FORMAT("4"),
               APPROVAL_FORMAT("4"), 0, 0, 0, 0, 0, 0 },
    /* VV5 */ { DATA_FORMAT(VV_DATA_SUB_MASKS, "Village Masks"),
               "%s\\Virtual Villagers Fun Patcher Data\\Village Masks - Save %d.dat",
               "%s\\vvfp_masks_%d.dat", CUSTOM_TITLES_FORMAT,
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 5 Village Roster"),
               ROSTER_FORMAT("5"), GRAVES_LOGGED_FORMAT("5"), ARRIVALS_FORMAT("5"), BIRTHS_FORMAT("5"),
               APPROVAL_FORMAT("5"), 0, 0, 0, 0, 0, 0 },
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
/* The same test against a later line: LINE_INDEX lines are skipped first.
   The Village Population roster opens with its title and puts the village
   header on its SECOND line, so it is matched with line_index 1. */
/* A RENAMED TRIBE'S LOGS ARE STILL ITS OWN. The patcher's Rename Tribe tool
   never rewrites a header; it appends "Tribe renamed from <old> to <new> on
   <date>" to each of the village's logs, and the header a file stands for
   follows every such line in order (village_rename.h). So the whole file is
   read, line by line, and the recovered header has each note applied before
   it is compared. Without this a Start Over of a renamed village would read
   its NEW name from the save and leave every log it kept under the old one.

   Lines are assembled from fixed reads; a line longer than the buffer is
   skipped whole (it is a record line, never a header or a note), so nothing
   past the buffer is ever written. */
#define RESET_LINE_MAX 512

static int log_line_matches(const wchar_t *path, const char *village,
                            int line_index) {
    HANDLE f;
    char chunk[4096];
    char line[RESET_LINE_MAX];
    char header[RESET_LINE_MAX];
    char want[256];
    DWORD got = 0;
    DWORD i;
    int n;
    int used = 0;
    int overlong = 0;
    int line_number = 0;
    int have_header = 0;
    int at_end = 0;

    if (village == NULL || village[0] == '\0') {
        return 0;
    }
    f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        return 0;
    }
    header[0] = '\0';
    while (!at_end) {
        if (!ReadFile(f, chunk, sizeof(chunk), &got, NULL)) {
            CloseHandle(f);
            return 0;
        }
        if (got == 0) {
            at_end = 1;
            chunk[0] = '\n';    /* end the last line as if it had a newline */
            got = used > 0 || overlong ? 1 : 0;
        }
        for (i = 0; i < got; ++i) {
            char c = chunk[i];
            if (c != '\n') {
                if (used < RESET_LINE_MAX - 1) {
                    line[used++] = c;
                } else {
                    overlong = 1;
                }
                continue;
            }
            /* One whole line, without its line ending. */
            while (used > 0 && line[used - 1] == '\r') {
                --used;
            }
            line[used] = '\0';
            if (line_number == line_index) {
                if (!overlong) {
                    lstrcpynA(header, line, (int)sizeof(header));
                    have_header = header[0] != '\0';
                }
                if (!have_header) {
                    CloseHandle(f);
                    return 0;
                }
            } else if (line_number > line_index && have_header && !overlong) {
                (void)vv_rename_apply(header, sizeof(header), line);
            }
            ++line_number;
            used = 0;
            overlong = 0;
        }
    }
    CloseHandle(f);
    if (!have_header) {
        return 0;               /* the file ends before the header line */
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
    return lstrcmpA(header, want) == 0;
}

static int log_header_matches(const wchar_t *path, const char *village) {
    return log_line_matches(path, village, 0);
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

/* Delete every "Village Population <n>.txt" page in DIR that belongs to
   VILLAGE, by the header on its second line.

   The roster is NOT numbered by slot. The exporter rolls it over by page --
   one file per VILLAGERS_PER_FILE villagers, 1..N -- in a folder every slot
   shares, and each page opens "<title> Village Population" then the village
   header. So page 1 is whichever village saved last, and the only thing that
   says whose a page is, is its header. Deleting "page <slot>" instead erased
   page 1 of whatever village saved last on a slot-1 Start Over, and a page of
   some other village, or nothing, on slots 2..5. */
static int delete_village_population_pages(const wchar_t *dir,
                                           const char *village) {
    static const wchar_t STEM[] = L"Village Population ";
    WIN32_FIND_DATAW found;
    HANDLE search;
    wchar_t filter[MAX_PATH];
    wchar_t path[MAX_PATH];
    int removed = 0;
    int stem_len = lstrlenW(STEM);
    int dir_len = lstrlenW(dir);

    if (village == NULL || village[0] == '\0') {
        return 0;
    }
    if (dir_len + 1 + stem_len + 5 + 1 >= MAX_PATH) {
        return 0;
    }
    wsprintfW(filter, L"%ls\\Village Population *.txt", dir);
    search = FindFirstFileW(filter, &found);
    if (search == INVALID_HANDLE_VALUE) {
        return 0;
    }
    do {
        const wchar_t *tail;
        int number = 0;
        int digits = 0;
        if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            continue;
        }
        /* Only the exporter's own shape: the stem, a plain page number,
           ".txt". FindFirstFileW also matches 8.3 aliases and anything else
           sharing the prefix, and those are left alone. */
        if (lstrlenW(found.cFileName) <= stem_len
            || CompareStringW(LOCALE_INVARIANT, NORM_IGNORECASE,
                              found.cFileName, stem_len, STEM, stem_len)
                   != CSTR_EQUAL) {
            continue;
        }
        tail = found.cFileName + stem_len;
        while (*tail >= L'0' && *tail <= L'9' && digits <= 5) {
            number = number * 10 + (int)(*tail - L'0');
            ++digits;
            ++tail;
        }
        if (digits == 0 || digits > 5 || number < 1
            || lstrcmpiW(tail, L".txt") != 0
            || dir_len + 1 + lstrlenW(found.cFileName) >= MAX_PATH) {
            continue;
        }
        wsprintfW(path, L"%ls\\%ls", dir, found.cFileName);
        if (log_line_matches(path, village, 1)) {
            removed += delete_if_present_w(path);
        }
    } while (FindNextFileW(search, &found));
    FindClose(search);
    return removed;
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
    /* Every name below is formatted onto the save folder with wsprintfA,
       which takes no destination bound, so each one is bounded before it is
       formatted -- a name that would not fit in MAX_PATH is skipped, never
       overrun. Such a file cannot exist: the companion that writes it
       refuses the same path.

       The folder is resolved with the SHORTEST name's room, not the
       longest's. On a long Documents path or exe name the longest (a nested
       Unaccounted Villagers roster) may not fit while a shorter one -- a
       loose mask file, which data_subfolder.h falls back to exactly then --
       still does, and refusing the whole reset over the longest left that
       file behind for the next village (Codex, #519).

       Each format is "%s" + tail + "%d" + ".dat"-ish, so it formats to the
       folder plus (format length - 4) + one slot digit; with the NUL that is
       format length - 2. Measured from the table, so it recomputes whenever
       a name is edited or a row added. */
    {
        int reserve = 0;
        for (i = 0; i < SIDECAR_FORMAT_COUNT; ++i) {
            const char *fmt = SIDECAR_FORMATS[game - 1][i];
            if (fmt != NULL && (reserve == 0 || lstrlenA(fmt) - 4 + 2 < reserve)) {
                reserve = lstrlenA(fmt) - 4 + 2;
            }
        }
        if (!vv_save_folder(folder, reserve)) {
            return -1;          /* unresolved path is never a deletion target */
        }
    }

    for (i = 0; i < SIDECAR_FORMAT_COUNT; ++i) {
        const char *fmt = SIDECAR_FORMATS[game - 1][i];
        if (fmt == NULL) {
            continue;   /* a hole, not the end: the rows are not packed */
        }
        if (lstrlenA(folder) + lstrlenA(fmt) - 4 + 2 > MAX_PATH) {
            continue;   /* would not fit in path[]: no companion can have written it */
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
        /* The current log, which replaced the file above. */
        wsprintfW(path_w, L"%ls\\Village Statistics v2 - Save %d.txt", sub_w, slot);
        removed += delete_if_present_w(path_w);
    }
    /* THE STATISTICS COMPANION'S PER-SLOT DATA. Village Statistics holds the
       patch's own lifetime counters, Stew Discoveries the unique stews (The
       Lost Children, The Secret City and The Tree of Life only), and Village
       Elders the villagers seen holding the status. Each is one file per
       slot, addressed by slot, and belongs to the village being erased: left
       behind, the next village started in this slot would inherit its totals
       and discoveries. The ".tmp" beside each is the companion's
       half-written replacement, which a crash can leave.

       The folders are probed, never created: a player who never ran the
       companion has nothing here to clear. Files set aside as unreadable
       ("<name>.unreadable") are deliberately left: they are kept evidence of
       a file the companion could not read, and nothing ever loads them. */
    {
        static const wchar_t *const DATA_FOLDERS[3] = {
            L"Virtual Villagers Fun Patcher Data\\Village Statistics",
            L"Virtual Villagers Fun Patcher Data\\Stew Discoveries",
            L"Virtual Villagers Fun Patcher Data\\Village Elders"
        };
        static const wchar_t *const DATA_STEMS[3] = {
            L"Village Statistics - Save",
            L"Stew Discoveries - Save",
            L"Village Elders - Save"
        };
        int data;
        for (data = 0; data < 3; ++data) {
            if (data == 1 && (game < 2 || game > 4)) {
                continue;   /* only three games make stews */
            }
            if (!legacy_subfolder_w(sub_w, DATA_FOLDERS[data])) {
                continue;
            }
            wsprintfW(path_w, L"%ls\\%ls %d.dat", sub_w, DATA_STEMS[data], slot);
            removed += delete_if_present_w(path_w);
            wsprintfW(path_w, L"%ls\\%ls %d.dat.tmp", sub_w, DATA_STEMS[data], slot);
            removed += delete_if_present_w(path_w);
        }
        /* ...and the living roster those files were kept for ("Village
           Roster - Save N.dat", its replacement written as ".tmp"): left
           behind, the next village's first save in the slot was checked
           against the erased village's villagers (the owner's v1.35.59 live
           pass: it stayed after Start Over). */
        if (legacy_subfolder_w(sub_w, DATA_FOLDERS[0])) {
            wsprintfW(path_w, L"%ls\\Village Roster - Save %d.dat", sub_w, slot);
            removed += delete_if_present_w(path_w);
            wsprintfW(path_w, L"%ls\\Village Roster - Save %d.tmp", sub_w, slot);
            removed += delete_if_present_w(path_w);
        }
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
    /* THE ROSTER IS NUMBERED BY PAGE, NOT BY SLOT, so it is matched by the
       village header on each page's second line -- every page of the erased
       village, in the current folder and the retired one, and nothing else.
       Without a village string nothing is deleted, as for parentage.
       vv_save_subfolder_w creates the folder if absent, which is harmless
       here -- an empty folder is not a stale roster. */
    if (vv_save_subfolder_w(sub_w, L"Virtual Villagers Fun Patcher Logs\\Tribe Population", 64)) {
        removed += delete_village_population_pages(sub_w, village);
    }
    if (legacy_subfolder_w(sub_w, L"VVFP Logs\\Tribe Population")) {
        removed += delete_village_population_pages(sub_w, village);
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
        /* Indexes 4 and 5 are the Deaths and Unaccounted Villagers logs:
           "VVFP Cause of Death.dll" records deaths, disappearances and
           villagers no record accounts for through the parentage exporter,
           into village-headed logs like the births one. They are only
           probed -- a player without that row has neither folder, and a
           reset must not create one. */
        static const wchar_t *const FOLDERS[6] = {
            L"Virtual Villagers Fun Patcher Logs\\Births and Conceptions",
            L"Virtual Villagers Fun Patcher Logs\\Tribe Parental Records",
            L"VVFP Logs\\Births and Conceptions",
            L"VVFP Logs\\Tribe Parental Records",
            L"Virtual Villagers Fun Patcher Logs\\Deaths",
            L"Virtual Villagers Fun Patcher Logs\\Unaccounted Villagers"
        };
        static const wchar_t *const DEATH_LOG[5] = {
            L"Virtual Villagers 1 Deaths Log",
            L"Virtual Villagers 2 Deaths Log",
            L"Virtual Villagers 3 Deaths Log",
            L"Virtual Villagers 4 Deaths Log",
            L"Virtual Villagers 5 Deaths Log"
        };
        static const wchar_t *const UNACCOUNTED_LOG[5] = {
            L"Virtual Villagers 1 Unaccounted Villagers Log",
            L"Virtual Villagers 2 Unaccounted Villagers Log",
            L"Virtual Villagers 3 Unaccounted Villagers Log",
            L"Virtual Villagers 4 Unaccounted Villagers Log",
            L"Virtual Villagers 5 Unaccounted Villagers Log"
        };
        static const wchar_t *const LEGACY_LOG[5] = {
            L"Virtual Villagers 1 Parentage Log",
            L"Virtual Villagers 2 Parentage Log",
            L"Virtual Villagers 3 Parentage Log",
            L"Virtual Villagers 4 Parentage Log",
            L"Virtual Villagers 5 Parentage Log"
        };
        int pass;
        for (pass = 0; pass < 6; ++pass) {
            /* The old FILE name went with the old FOLDER name, so the
               stem follows the folder rather than the pass number. */
            const wchar_t *stem = pass == 5 ? UNACCOUNTED_LOG[game - 1]
                : pass == 4 ? DEATH_LOG[game - 1]
                : (pass % 2 == 0) ? PARENTAGE_LOG[game - 1] : LEGACY_LOG[game - 1];
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
            /* ENUMERATE THE FOLDER, DO NOT PREDICT ITS CONTENTS.

               An earlier version walked 1..MAX_LOG_FILES and stopped at
               the first absent number. That was wrong, because THIS
               FUNCTION MAKES HOLES: it deletes the erased village's files
               and select_log_file then hands the freed number to the next
               village, so different villages legitimately own
               non-consecutive numbers. A second reset walked into the hole
               the first had left and stopped there -- village A in file 1
               and village B in file 2, resetting A deletes 1, and B's own
               Start Over never looked at 2.

               Walking the whole range fixed that but cost 4096 probes per
               pass, four passes, whether or not the folder held anything:
               609 ms on a local disk, and far worse on Documents
               redirected to an SMB share, where each probe is a round trip
               and this runs inside the game's own delete handler. Both
               problems were found in review.

               Asking the directory what it contains costs what the folder
               actually holds, and holes stop mattering because nothing is
               being predicted.

               The name filter is the shape the exporter writes -- the stem,
               a space, a number in 1..MAX_LOG_FILES, ".txt" -- so a
               hand-made or corrupt name is left alone rather than guessed
               at, exactly as the bounded walk did. Every match is still
               checked by header before deletion, so this can only ever
               remove the erased village's own logs. */
            {
                WIN32_FIND_DATAW found;
                HANDLE search;
                wchar_t filter[MAX_PATH];
                int stem_len = lstrlenW(stem);
                wsprintfW(filter, L"%ls\\%ls *.txt", sub_w, stem);
                search = FindFirstFileW(filter, &found);
                if (search != INVALID_HANDLE_VALUE) {
                    do {
                        const wchar_t *tail;
                        int number = 0;
                        int digits = 0;
                        if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                            continue;
                        }
                        /* The wildcard matched "<stem> <something>.txt".
                           Accept only a plain number in range: FindFirstFileW
                           also matches short 8.3 aliases and anything else
                           sharing the prefix. */
                        if (lstrlenW(found.cFileName) <= stem_len + 1) {
                            continue;
                        }
                        tail = found.cFileName + stem_len + 1;
                        while (*tail >= L'0' && *tail <= L'9') {
                            if (digits > 5) {
                                break;      /* absurd; not ours */
                            }
                            number = number * 10 + (int)(*tail - L'0');
                            ++digits;
                            ++tail;
                        }
                        if (digits == 0 || number < 1 || number > MAX_LOG_FILES) {
                            continue;
                        }
                        if (lstrcmpiW(tail, L".txt") != 0) {
                            continue;
                        }
                        wsprintfW(path_w, L"%ls\\%ls", sub_w, found.cFileName);
                        if (log_header_matches(path_w, village)) {
                            removed += delete_if_present_w(path_w);
                        }
                    } while (FindNextFileW(search, &found));
                    FindClose(search);
                }
            }
        }
    }
    return removed;
}
