/* See save_reset.h. Deletes this patcher's state for one erased village. */
#include "save_reset.h"
#include "save_folder.h"
#define VV_DATA_SUBFOLDER_NAMES_ONLY   /* the folder names; nothing is moved here */
#include "data_subfolder.h"
#include "village_rename.h"
#include "log_slot.h"       /* one folder of logs per save slot */
#include "log_words.h"      /* the Like and Dislike Words boundaries a deleted log leaves behind */

#include <windows.h>
#include <string.h>         /* memcmp, memcpy */

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
   (Repair Saves & Logs in the patcher window, src/vv_log_tools.py; used up by the
   game, native/shared/crosscheck_bridge.h): it was given for the village
   being erased, never for the one started after the reset. */
#define APPROVAL_FORMAT(n) \
    "%s\\Virtual Villagers Fun Patcher Data\\Log Checks\\Virtual Villagers " n " Repair Approved - Save %d.dat", \
    "%s\\Virtual Villagers Fun Patcher Data\\Cross-Check\\Virtual Villagers " n " Repair Approved - Save %d.dat"
/* ...and New Believers' former Heathens and the masks they wore
   (native/shared/former_heathens.h), which the game does not keep. */
#define FORMER_HEATHENS_FORMAT \
    "%s\\Virtual Villagers Fun Patcher Data\\Former Heathens\\Former Heathens - Save %d.dat"
/* ...and a bought purchase not delivered yet (native/shared/paid_purchases.h):
   it belongs to the village being erased, never to the one started after. */
#define PAID_FORMAT(n) \
    "%s\\Virtual Villagers Fun Patcher Data\\Paid Purchases\\Virtual Villagers " n " Paid Purchases - Save %d.dat"
#define STORY_QUEUE_FORMAT(n) \
    "%s\\Virtual Villagers Fun Patcher Data\\Paid Purchases\\Virtual Villagers " n " Story Purchases - Save %d.dat"
/* ...and the bodies the Custom Island Event's "Dies" left lying in The Secret
   City, The Tree of Life and New Believers (native/vvfp_cause_of_death/
   cod_cie.inc): they belong to the village being erased. */
#define CIE_DEATHS_FORMAT(n) \
    "%s\\Virtual Villagers Fun Patcher Data\\Custom Island Event Deaths\\Virtual Villagers " n " Custom Island Event Deaths - Save %d.dat"
/* ...and The Secret City's second faction (native/vvfp_vv3_both_factions):
   the faction bought second, which the save never holds.  It belongs to the
   village being erased.  Written only in the save's own folder (per_save.h),
   which the older-layout name below routes to. */
#define BOTH_FACTIONS_FORMAT DATA_FORMAT("Factions", "Virtual Villagers 3 Second Faction")
/* ...and The Secret City's fruit-tree schedule (native/shared/vv3_fruit_timers.h: All Fruit
   Trees Refill at the Same Time, or Fruit Trees Take Turns Refilling), which the save never
   holds.  It belongs to the village being erased; routed the same way. */
#define FRUIT_TREES_FORMAT DATA_FORMAT("Fruit Trees", "Virtual Villagers 3 Fruit Tree Timers")
/* ...and the head look Change Appearance chose for each villager (Auto, Young or Old;
   native/vvfp_head_look/head_look_store.inc): it belongs to the village being erased.  Written only in
   the save's own folder (per_save.h), which the older-layout name below routes to. */
#define HEAD_LOOKS_FORMAT DATA_FORMAT("Head Looks", "Head Looks")
#define SIDECAR_FORMAT_COUNT 23
static const char *const SIDECAR_FORMATS[5][SIDECAR_FORMAT_COUNT] = {
    /* VV1 */ { PAID_FORMAT("1"), STORY_QUEUE_FORMAT("1"), DATA_FORMAT(VV_DATA_SUB_MASKS, "Virtual Villagers 1 Village Masks"),
               "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 1 Village Masks - Save %d.dat",
               "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 1 Origins Doublers - Save %d.dat",
               DATA_FORMAT(VV_DATA_SUB_PARENTAGE, "Virtual Villagers 1 Parentage Records"),
               DATA_FORMAT(VV_DATA_SUB_PARENTAGE_OLD, "Virtual Villagers 1 Parentage Records"),
               "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 1 Parentage Records - Save %d.dat",
               "%s\\vv1_masks_%d.dat", "%s\\vv1_doublers_%d.dat",
               "%s\\vv1_parents_%d.dat", CUSTOM_TITLES_FORMAT,
               DATA_FORMAT(VV_DATA_SUB_GRAVES, "Virtual Villagers 1 Graves"), CAUSE_OF_DEATH_FORMAT("1"),
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 1 Villagers at Last Save"),
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 1 Village Roster"),
               ROSTER_FORMAT("1"), GRAVES_LOGGED_FORMAT("1"), ARRIVALS_FORMAT("1"), APPROVAL_FORMAT("1"),
               HEAD_LOOKS_FORMAT },
    /* VV2 */ { PAID_FORMAT("2"), STORY_QUEUE_FORMAT("2"), DATA_FORMAT(VV_DATA_SUB_MASKS, "Virtual Villagers 2 Village Masks"),
               "%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 2 Village Masks - Save %d.dat",
               "%s\\vv2_masks_%d.dat", CUSTOM_TITLES_FORMAT,
               DATA_FORMAT(VV_DATA_SUB_GRAVES, "Virtual Villagers 2 Graves"), CAUSE_OF_DEATH_FORMAT("2"),
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 2 Villagers at Last Save"),
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 2 Village Roster"),
               ROSTER_FORMAT("2"), GRAVES_LOGGED_FORMAT("2"), ARRIVALS_FORMAT("2"), BIRTHS_FORMAT("2"),
               APPROVAL_FORMAT("2"), HEAD_LOOKS_FORMAT, 0, 0, 0 },
    /* VV3 */ { PAID_FORMAT("3"), STORY_QUEUE_FORMAT("3"), DATA_FORMAT(VV_DATA_SUB_MASKS, "Village Masks"),
               "%s\\Virtual Villagers Fun Patcher Data\\Village Masks - Save %d.dat",
               "%s\\vvfp_masks_%d.dat", CUSTOM_TITLES_FORMAT,
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 3 Villagers at Last Save"),
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 3 Village Roster"),
               ROSTER_FORMAT("3"), GRAVES_LOGGED_FORMAT("3"), ARRIVALS_FORMAT("3"), BIRTHS_FORMAT("3"),
               APPROVAL_FORMAT("3"), CIE_DEATHS_FORMAT("3"), BOTH_FACTIONS_FORMAT, FRUIT_TREES_FORMAT,
               HEAD_LOOKS_FORMAT, 0, 0 },
    /* VV4 */ { PAID_FORMAT("4"), STORY_QUEUE_FORMAT("4"), DATA_FORMAT(VV_DATA_SUB_MASKS, "Village Masks"),
               "%s\\Virtual Villagers Fun Patcher Data\\Village Masks - Save %d.dat",
               "%s\\vvfp_masks_%d.dat", CUSTOM_TITLES_FORMAT,
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 4 Villagers at Last Save"),
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 4 Village Roster"),
               ROSTER_FORMAT("4"), GRAVES_LOGGED_FORMAT("4"), ARRIVALS_FORMAT("4"), BIRTHS_FORMAT("4"),
               APPROVAL_FORMAT("4"), CIE_DEATHS_FORMAT("4"), HEAD_LOOKS_FORMAT, 0, 0, 0, 0 },
    /* VV5 */ { PAID_FORMAT("5"), STORY_QUEUE_FORMAT("5"), DATA_FORMAT(VV_DATA_SUB_MASKS, "Village Masks"),
               "%s\\Virtual Villagers Fun Patcher Data\\Village Masks - Save %d.dat",
               "%s\\vvfp_masks_%d.dat", CUSTOM_TITLES_FORMAT,
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 5 Villagers at Last Save"),
               DATA_FORMAT(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers 5 Village Roster"),
               ROSTER_FORMAT("5"), GRAVES_LOGGED_FORMAT("5"), ARRIVALS_FORMAT("5"), BIRTHS_FORMAT("5"),
               APPROVAL_FORMAT("5"), FORMER_HEATHENS_FORMAT, CIE_DEATHS_FORMAT("5"), HEAD_LOOKS_FORMAT, 0, 0,
               0 },
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

/* The save's own folder (per_save.h) for the older-layout slot folder `slot_sub` ("Virtual Villagers
   Fun Patcher Logs\Save <S>\<sub>"), only when it is there; never created. */
static int own_subfolder_w(wchar_t *out, const wchar_t *slot_sub) {
    wchar_t root[MAX_PATH], old[MAX_PATH];
    if (out == NULL || slot_sub == NULL || !vv_save_folder_w(root, (int)wcslen(slot_sub) + 1 + 64 + 16)) {
        return 0;
    }
    /* (vv_save_folder_w has refused a root that leaves no room for the tail and 64 more.) */
    lstrcpyW(old, root);
    lstrcatW(old, L"\\");
    lstrcatW(old, slot_sub);
    return vv_ps_new_path_w(old, out, MAX_PATH) && GetFileAttributesW(out) != INVALID_FILE_ATTRIBUTES;
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

/* START OVER CLEARS A DELETED LOG'S LIKE AND DISLIKE WORDS BOUNDARIES.

   The boundary files (log_words.h) hold "<offset>\t<key>\r\n" lines keyed by
   each log's path inside the save folder, and the last line naming a log is
   the one that counts.  A log deleted here and later made again under the
   same name (the next village's "... Log 1.txt") would otherwise inherit the
   erased village's boundary: the exporter records a new boundary only when
   none is recorded, so the stale one stayed and turned the new log's correct
   words into "old" ones (the owner's report, 2026-10-19).

   So every line naming the deleted log is removed -- from the save's own
   boundary file first, then from the shared one and an older build's "Log
   Words" one -- and every other line is kept byte for byte: other saves'
   logs, and any log of this save Start Over could not delete.  A file
   holding no such line is not rewritten.  The rewrite goes through a
   ".tmp" beside it and replaces the file in one move, so a failure leaves the
   old file whole.  Keys compare without case, as the file system does.

   The whole read-modify-replace of every file is done holding the game's
   boundary lock (log_words.h vv_log_words_lock), which every other writer
   holds to append, so no line written meanwhile can be lost (Codex, #597).
   The wait is bounded: when the lock cannot be had in time nothing is
   rewritten and the refusal is counted (vv_reset_words_refusals).  The
   ".tmp" name is unique to the process and the operation, so two resets never
   share one. */
int vv_reset_words_refusals = 0;
static LONG vv_reset_tmp_counter = 0;

#ifdef VV_RESET_TESTABLE
/* Called after a file was read and before it is replaced, so the harness can
   try to append right then (save_reset_words_harness.c). */
void (*vv_reset_words_test_hook)(const char *dat) = NULL;
#endif
static int words_line_names(const char *line, size_t length, const char *key) {
    const char *tab = (const char *)memchr(line, '\t', length);
    size_t key_length = strlen(key);
    size_t rest;
    if (tab == NULL) {
        return 0;
    }
    rest = length - (size_t)(tab + 1 - line);
    while (rest > 0 && (tab[rest] == '\r' || tab[rest] == '\n')) {
        --rest;
    }
    return rest == key_length && _strnicmp(tab + 1, key, key_length) == 0;
}

VV_RESET_STATIC int forget_words_in(const char *dat, const char *key) {
    HANDLE file;
    DWORD size, got = 0, wrote = 0;
    char *text, *kept, *p, *end;
    size_t kept_length = 0;
    int dropped = 0;
    char tmp[MAX_PATH];
    if (dat == NULL || dat[0] == '\0' || key == NULL || key[0] == '\0'
        || lstrlenA(dat) + 32 >= MAX_PATH) {
        return 0;
    }
    file = CreateFileA(dat, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    size = GetFileSize(file, NULL);
    if (size == INVALID_FILE_SIZE || size == 0 || size > 16u * 1024u * 1024u) {
        CloseHandle(file);
        return 0;
    }
    text = (char *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)size);
    kept = (char *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)size);
    if (text == NULL || kept == NULL || !(ReadFile(file, text, size, &got, NULL) && got == size)) {
        CloseHandle(file);
        if (text != NULL) HeapFree(GetProcessHeap(), 0, text);
        if (kept != NULL) HeapFree(GetProcessHeap(), 0, kept);
        return 0;
    }
    CloseHandle(file);
    for (p = text; p < text + size; p = end) {
        end = (char *)memchr(p, '\n', (size_t)(text + size - p));
        end = end == NULL ? text + size : end + 1;
        if (words_line_names(p, (size_t)(end - p), key)) {
            ++dropped;
        } else {
            memcpy(kept + kept_length, p, (size_t)(end - p));
            kept_length += (size_t)(end - p);
        }
    }
    HeapFree(GetProcessHeap(), 0, text);
#ifdef VV_RESET_TESTABLE
    if (vv_reset_words_test_hook != NULL) {
        vv_reset_words_test_hook(dat);
    }
#endif
    if (dropped > 0) {
        wsprintfA(tmp, "%s.%lu-%ld.tmp", dat, GetCurrentProcessId(),
                  InterlockedIncrement(&vv_reset_tmp_counter));
        file = CreateFileA(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        if (file == INVALID_HANDLE_VALUE) {
            dropped = 0;
        } else {
            BOOL ok = kept_length == 0
                      || (WriteFile(file, kept, (DWORD)kept_length, &wrote, NULL) && wrote == kept_length);
            ok = FlushFileBuffers(file) && ok;
            CloseHandle(file);
            if (!ok || !MoveFileExA(tmp, dat, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
                DeleteFileA(tmp);   /* the old file is left whole */
                dropped = 0;
            }
        }
    }
    HeapFree(GetProcessHeap(), 0, kept);
    return dropped;
}

/* Every boundary line of the log at `path` (already deleted), in each boundary file of `game`:
   the save's own (`slot`'s, and the save the key itself names if that differs), then the shared
   one and an older build's.  Returns the lines removed. */
VV_RESET_STATIC int forget_log_words(int game, int slot, const wchar_t *path) {
    char key[MAX_PATH], save_dat[MAX_PATH], new_dat[MAX_PATH], old_dat[MAX_PATH];
    int forgotten = 0;
    int key_slot;
    HANDLE lock;
    if (path == NULL || !vv_log_words_name(path, key, sizeof key)) {
        return 0;
    }
    lock = vv_log_words_lock(game);   /* held across every file's read-modify-replace */
    if (lock == NULL) {
        ++vv_reset_words_refusals;    /* every file left as it was */
        return 0;
    }
    key_slot = vv_log_words_name_slot(key);
    if (vv_log_words_save_path(game, slot, save_dat, sizeof save_dat)) {
        forgotten += forget_words_in(save_dat, key);
    }
    if (key_slot != 0 && key_slot != slot && vv_log_words_save_path(game, key_slot, save_dat, sizeof save_dat)) {
        forgotten += forget_words_in(save_dat, key);
    }
    if (vv_log_words_paths(game, new_dat, old_dat, sizeof new_dat)) {
        forgotten += forget_words_in(new_dat, key);
        forgotten += forget_words_in(old_dat, key);
    }
    vv_log_words_unlock(lock);
    return forgotten;
}

/* Delete one of the village's logs and, when it went, its boundary lines. */
static int delete_log_w(int game, int slot, const wchar_t *path) {
    if (!delete_if_present_w(path)) {
        return 0;
    }
    (void)forget_log_words(game, slot, path);
    return 1;
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
static int delete_village_population_pages(int game, int slot, const wchar_t *dir,
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
            removed += delete_log_w(game, slot, path);
        }
    } while (FindNextFileW(search, &found));
    FindClose(search);
    return removed;
}

/* ===================================================================================================
   START OVER WIPES THE WHOLE SAVE (the owner, v1.35.79: Start Over is the sole exception to "nothing
   is ever deleted" -- it makes a new tribe, so every remnant of the old one goes, in all five games).

   For the erased slot N, after the named files above, this deletes:
     - the save's own folder "<save folder>\Virtual Villagers Fun Patcher\Save N\", everything in it
       (every log, the Village History too, and every data file, ElderTotems.dat too);
     - the slot's files of the older layout: all of "Virtual Villagers Fun Patcher Logs\Save N\", and
       every file under "Virtual Villagers Fun Patcher Data\" whose name says " - Save N";
     - the slot's family tree files in "Virtual Villagers Fun Patcher Family Trees" (its Reports too,
       and the older "Virtual Villagers Fun Patcher Logs\Genealogy"): its .vvtree files (the save they
       record, src/vv_genealogy_window.py _save_tree), its Village Matchmaker text and its Genealogy
       reports (by the "(Save N)" / " - Save N" in the names src/vv_family_tree.py gives them).
   It KEEPS: the Backups and "Copies Made Before Repairs" folders, any repair copy kept beside its file
   (".before-..."), every picture (.png, .jpg, .jpeg, .bmp, .gif) of any save, the game's own saves and
   every other save's files.  A file whose save cannot be told for sure is kept and listed in the
   report; a link or junction is never followed (nor deleted) and is listed; a file that cannot be
   deleted is listed, never retried.  The report, when there is anything to list, is
   "<save folder>\Virtual Villagers Fun Patcher\Start Over Report - Save N.txt" (replaced by the next
   Start Over of that save).  Every name is checked before anything is deleted; nothing outside the
   save folder is ever reached.  The folders themselves are left, empty: the running game's
   companions keep the paths they write to, and must find their folders there for the new tribe. */
int vv_reset_wipe_kept_unclear = 0;   /* kept because its save could not be told */
int vv_reset_wipe_not_deleted = 0;    /* could not be deleted (in use, read-only) */
int vv_reset_wipe_links = 0;          /* links and junctions not followed */

#define WIPE_ALL   0    /* a folder of the slot's own: everything but the kept kinds */
#define WIPE_DATA  1    /* the older Data folder: only names saying " - Save N" */
#define WIPE_TREES 2    /* the Family Trees: the slot's tree files, reports and matchmaker text */
#define WIPE_DEPTH_MAX 24
#define WIPE_REPORT_BYTES 65536
#define WIPE_TREE_BYTES (16u * 1024u * 1024u)

typedef struct {
    int game;
    int slot;
    int root_len;           /* the save folder's length: report lines are relative to it */
    char *report;
    int report_len;
    int removed;
    HANDLE words_lock;      /* the game's Like and Dislike Words lock, held for the whole wipe */
} vv_wipe;

/* `out` = `a` + "\" + `b`, when it fits in MAX_PATH. */
static int wipe_join(wchar_t *out, const wchar_t *a, const wchar_t *b) {
    int a_len = lstrlenW(a), b_len = lstrlenW(b);
    if (a_len + 1 + b_len + 1 > MAX_PATH) {
        return 0;
    }
    lstrcpyW(out, a);
    out[a_len] = L'\\';
    lstrcpyW(out + a_len + 1, b);
    return 1;
}

static int wipe_ends_i(const wchar_t *name, const wchar_t *tail) {
    int n = lstrlenW(name), t = lstrlenW(tail);
    return n >= t && lstrcmpiW(name + n - t, tail) == 0;
}

static int wipe_contains_i(const wchar_t *name, const wchar_t *needle) {
    int n = lstrlenW(needle);
    for (; *name != L'\0'; ++name) {
        if (lstrlenW(name) >= n
            && CompareStringW(LOCALE_INVARIANT, NORM_IGNORECASE, name, n, needle, n) == CSTR_EQUAL) {
            return 1;
        }
    }
    return 0;
}

/* A picture: kept, whatever save it is of (the owner: exported family tree pictures stay). */
static int wipe_is_picture(const wchar_t *name) {
    return wipe_ends_i(name, L".png") || wipe_ends_i(name, L".jpg") || wipe_ends_i(name, L".jpeg")
        || wipe_ends_i(name, L".bmp") || wipe_ends_i(name, L".gif");
}

/* A repair's copy kept beside its file by an older build ("<name>.before-repair",
   "<name>.before-v1.35.58-repair..."): a Copy Made Before Repairs, kept. */
static int wipe_is_repair_copy(const wchar_t *name) {
    return wipe_contains_i(name, L".before-");
}

/* A folder that is never entered: Backups, and the Copies Made Before Repairs. */
static int wipe_is_kept_folder(const wchar_t *name) {
    return lstrcmpiW(name, L"Backups") == 0 || lstrcmpiW(name, L"Copies Made Before Repairs") == 0;
}

/* The game a name starts with ("Virtual Villagers <G> ..."), or 0. */
static int wipe_name_game(const wchar_t *name) {
    static const wchar_t stem[] = L"Virtual Villagers ";
    int n = (int)(sizeof stem / sizeof stem[0]) - 1;
    if (lstrlenW(name) > n + 1
        && CompareStringW(LOCALE_INVARIANT, NORM_IGNORECASE, name, n, stem, n) == CSTR_EQUAL
        && name[n] >= L'1' && name[n] <= L'5' && name[n + 1] == L' ') {
        return name[n] - L'0';
    }
    return 0;
}

/* The save a file name says it is of: " - Save <S>" followed by "." or the end (the data files, the
   reports, the matchmaker), and, when `trees`, also "(Save <S>)" (a tree file's default name) and
   " - Save <S> " (a report's later page).  0 none said, -1 two different saves said, else S. */
static int wipe_name_slot(const wchar_t *name, int trees) {
    static const wchar_t dash[] = L" - Save ";
    static const wchar_t paren[] = L"(Save ";
    const int dash_n = (int)(sizeof dash / sizeof dash[0]) - 1;
    const int paren_n = (int)(sizeof paren / sizeof paren[0]) - 1;
    int found = 0;
    const wchar_t *p;
    for (p = name; *p != L'\0'; ++p) {
        int s = 0;
        int rest = lstrlenW(p);
        if (rest > dash_n && CompareStringW(LOCALE_INVARIANT, NORM_IGNORECASE, p, dash_n, dash, dash_n) == CSTR_EQUAL
            && p[dash_n] >= L'0' && p[dash_n] <= L'9'
            && (p[dash_n + 1] == L'.' || p[dash_n + 1] == L'\0' || (trees && p[dash_n + 1] == L' '))) {
            s = p[dash_n] - L'0';
        } else if (trees && rest > paren_n + 1
                   && CompareStringW(LOCALE_INVARIANT, NORM_IGNORECASE, p, paren_n, paren, paren_n) == CSTR_EQUAL
                   && p[paren_n] >= L'0' && p[paren_n] <= L'9' && p[paren_n + 1] == L')') {
            s = p[paren_n] - L'0';
        }
        if (s != 0) {
            if (found != 0 && found != s) {
                return -1;
            }
            found = s;
        }
    }
    return found;
}

/* The game and save a family tree file records ({"format": ..., "game": G, "slot": S, ...}, written
   by src/vv_genealogy_window.py _save_tree): the top level's "game" and "slot" keys only, never a
   key nested in its edits.  1 with *slot (and *game, 0 when not recorded), 0 when the file cannot be
   read or records no save. */
static int wipe_tree_record(const wchar_t *path, int *game, int *slot) {
    HANDLE file;
    DWORD size, got = 0, i;
    char *text;
    int depth = 0, in_string = 0, escaped = 0;
    DWORD key_start = 0, key_end = 0;
    int have_key = 0, ok = 0;
    *game = 0;
    *slot = 0;
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    size = GetFileSize(file, NULL);
    if (size == INVALID_FILE_SIZE || size == 0 || size > WIPE_TREE_BYTES) {
        CloseHandle(file);
        return 0;
    }
    text = (char *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)size);
    if (text == NULL) {
        CloseHandle(file);
        return 0;
    }
    if (!(ReadFile(file, text, size, &got, NULL) && got == size)) {
        CloseHandle(file);
        HeapFree(GetProcessHeap(), 0, text);
        return 0;
    }
    CloseHandle(file);
    for (i = 0; i < size; ++i) {
        char c = text[i];
        if (in_string) {
            if (escaped) {
                escaped = 0;
            } else if (c == '\\') {
                escaped = 1;
            } else if (c == '"') {
                in_string = 0;
                key_end = i;
                have_key = depth == 1;
            }
            continue;
        }
        if (c == '"') {
            in_string = 1;
            key_start = i + 1;
            have_key = 0;
        } else if (c == '{' || c == '[') {
            ++depth;
            have_key = 0;
        } else if (c == '}' || c == ']') {
            --depth;
            have_key = 0;
        } else if (c == ':' && have_key) {
            int is_game = key_end - key_start == 4 && memcmp(text + key_start, "game", 4) == 0;
            int is_slot = key_end - key_start == 4 && memcmp(text + key_start, "slot", 4) == 0;
            have_key = 0;
            if (is_game || is_slot) {
                DWORD j = i + 1;
                int value = 0, digits = 0;
                while (j < size && (text[j] == ' ' || text[j] == '\t' || text[j] == '\r' || text[j] == '\n')) {
                    ++j;
                }
                while (j < size && text[j] >= '0' && text[j] <= '9' && digits < 3) {
                    value = value * 10 + (text[j] - '0');
                    ++digits;
                    ++j;
                }
                if (digits > 0 && digits < 3 && !(j < size && text[j] >= '0' && text[j] <= '9')) {
                    if (is_game) {
                        *game = value;
                    } else {
                        *slot = value;
                        ok = 1;
                    }
                } else if (is_slot) {
                    ok = 0;     /* a slot that is not a plain number: not told */
                    *slot = 0;
                    break;
                }
            }
        } else if (c != ' ' && c != '\t' && c != '\r' && c != '\n') {
            have_key = 0;
        }
    }
    HeapFree(GetProcessHeap(), 0, text);
    return ok && *slot >= 1 && *slot <= 5;
}

/* One line of the report: "<what>: <path inside the save folder>". */
static void wipe_note(vv_wipe *w, const char *what, const wchar_t *path) {
    char line[MAX_PATH * 3 + 96];
    int n, m;
    const wchar_t *rel = lstrlenW(path) > w->root_len ? path + w->root_len + 1 : path;
    if (w->report == NULL) {
        w->report = (char *)HeapAlloc(GetProcessHeap(), 0, WIPE_REPORT_BYTES);
        if (w->report == NULL) {
            return;
        }
        w->report_len = 0;
    }
    n = lstrlenA(what);
    if (n + 2 >= (int)sizeof line) {
        return;
    }
    lstrcpyA(line, what);
    line[n++] = ':';
    line[n++] = ' ';
    m = WideCharToMultiByte(CP_UTF8, 0, rel, -1, line + n, (int)sizeof line - n - 3, NULL, NULL);
    if (m <= 0) {
        return;
    }
    n += m - 1;
    line[n++] = '\r';
    line[n++] = '\n';
    if (w->report_len + n <= WIPE_REPORT_BYTES) {
        memcpy(w->report + w->report_len, line, (size_t)n);
        w->report_len += n;
    }
}

/* Delete one file of the slot; a log's Like and Dislike Words lines go with it (only while the
   game's lock is held: taken once for the whole wipe, so a lock held elsewhere costs one bounded
   wait, not one per log). */
static void wipe_delete(vv_wipe *w, const wchar_t *path, const wchar_t *name) {
    int gone = wipe_ends_i(name, L".txt") && w->words_lock != NULL ? delete_log_w(w->game, w->slot, path)
                                                                    : delete_if_present_w(path);
    if (gone) {
        ++w->removed;
    } else if (GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES) {
        ++vv_reset_wipe_not_deleted;
        wipe_note(w, "Could not be deleted (in use or read-only)", path);
    }
}

/* What becomes of one file in `mode`. */
static void wipe_file(vv_wipe *w, const wchar_t *path, const wchar_t *name, int mode) {
    int said;
    int name_game = wipe_name_game(name);
    if (wipe_is_picture(name) || wipe_is_repair_copy(name)) {
        return;                                 /* kept, whatever save it is of */
    }
    if (mode == WIPE_ALL) {
        wipe_delete(w, path, name);
        return;
    }
    if (name_game != 0 && name_game != w->game) {
        return;                                 /* another game's (a shared folder), never this one's */
    }
    said = wipe_name_slot(name, mode == WIPE_TREES);
    if (mode == WIPE_TREES && (wipe_ends_i(name, L".vvtree") || wipe_ends_i(name, L".vvtree.tmp"))) {
        int game = 0, recorded = 0;
        if (!wipe_tree_record(path, &game, &recorded)) {
            ++vv_reset_wipe_kept_unclear;
            wipe_note(w, "Kept, its save could not be told (a family tree file that records no save)", path);
            return;
        }
        if (game != 0 && game != w->game) {
            return;                             /* another game's tree */
        }
        if (said != 0 && said != recorded) {
            ++vv_reset_wipe_kept_unclear;
            wipe_note(w, "Kept, its save could not be told (its name and its contents name different saves)", path);
            return;
        }
        if (recorded == w->slot) {
            wipe_delete(w, path, name);
        }
        return;
    }
    if (said == w->slot) {
        wipe_delete(w, path, name);
    } else if (said == -1 || (said == 0 && mode == WIPE_TREES)) {
        ++vv_reset_wipe_kept_unclear;
        wipe_note(w, "Kept, its save could not be told", path);
    }
}

/* Every entry of `dir`, depth first.  A link or junction is listed and never entered or deleted; the
   kept folders are never entered.  Files are deleted; folders are left, empty. */
static void wipe_walk(vv_wipe *w, const wchar_t *dir, int mode, int depth) {
    wchar_t filter[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAW found;
    HANDLE search;
    if (depth > WIPE_DEPTH_MAX) {
        wipe_note(w, "Not reached (folders nested too deep)", dir);
        return;
    }
    if (!wipe_join(filter, dir, L"*")) {
        wipe_note(w, "Not reached (the path is too long)", dir);
        return;
    }
    search = FindFirstFileW(filter, &found);
    if (search == INVALID_HANDLE_VALUE) {
        return;
    }
    do {
        if (lstrcmpW(found.cFileName, L".") == 0 || lstrcmpW(found.cFileName, L"..") == 0) {
            continue;
        }
        if (!wipe_join(path, dir, found.cFileName)) {
            wipe_note(w, "Not reached (the path is too long)", dir);
            continue;
        }
        if (found.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) {
            ++vv_reset_wipe_links;
            wipe_note(w, "Not followed (a link or junction)", path);
            continue;
        }
        if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            if (wipe_is_kept_folder(found.cFileName)) {
                continue;
            }
            /* The folder itself stays, emptied: the running game's companions keep the paths of
               the files they write, and a folder taken from under one would lose the new tribe's
               first writes (the custom titles harness caught exactly that). */
            wipe_walk(w, path, mode, depth + 1);
            continue;
        }
        wipe_file(w, path, found.cFileName, mode);
    } while (FindNextFileW(search, &found));
    FindClose(search);
}

/* `out` = the save folder + "\" + `sub`, when it is there as an ordinary folder.  A link or junction
   there is listed and never entered. */
static int wipe_folder(vv_wipe *w, const wchar_t *root, const wchar_t *sub, wchar_t *out) {
    DWORD attributes;
    if (!wipe_join(out, root, sub)) {
        return 0;
    }
    attributes = GetFileAttributesW(out);
    if (attributes == INVALID_FILE_ATTRIBUTES || !(attributes & FILE_ATTRIBUTE_DIRECTORY)) {
        return 0;
    }
    if (attributes & FILE_ATTRIBUTE_REPARSE_POINT) {
        ++vv_reset_wipe_links;
        wipe_note(w, "Not followed (a link or junction)", out);
        return 0;
    }
    return 1;
}

/* The wipe itself, after the named files.  Returns the files it deleted. */
static int wipe_slot(int game, int slot, const char *village) {
    vv_wipe w;
    wchar_t root[MAX_PATH], top[MAX_PATH], dir[MAX_PATH], report[MAX_PATH];
    wchar_t save_n[16], report_name[48];
    ZeroMemory(&w, sizeof w);
    w.game = game;
    w.slot = slot;
    if (!vv_save_folder_w(root, 96)) {
        return 0;
    }
    w.root_len = lstrlenW(root);
    save_n[0] = L'\0';
    lstrcpyW(save_n, L"Save ");
    save_n[5] = (wchar_t)(L'0' + slot);
    save_n[6] = L'\0';
    lstrcpyW(report_name, L"Start Over Report - Save ");
    lstrcatW(report_name, save_n + 5);
    lstrcatW(report_name, L".txt");
    report[0] = L'\0';
    /* The game's words lock, once (a mutex its owner may take again: forget_log_words' own takes
       return at once).  Not had in time: the files still go, their words lines are left as they are,
       and the refusal is counted once. */
    w.words_lock = vv_log_words_lock(game);
    if (w.words_lock == NULL) {
        ++vv_reset_words_refusals;
    }

    /* The save's own folder, everything in it. */
    if (wipe_folder(&w, root, L"Virtual Villagers Fun Patcher", top)) {
        if (wipe_join(report, top, report_name)) {
            (void)DeleteFileW(report);          /* the last Start Over's report of this save */
        }
        if (wipe_folder(&w, top, save_n, dir)) {
            wipe_walk(&w, dir, WIPE_ALL, 0);
        }
    }
    /* The older layout: the slot's folder of logs, and its " - Save N" data files. */
    if (wipe_folder(&w, root, L"Virtual Villagers Fun Patcher Logs", top)) {
        if (wipe_folder(&w, top, save_n, dir)) {
            wipe_walk(&w, dir, WIPE_ALL, 0);
        }
        if (wipe_folder(&w, top, L"Genealogy", dir)) {
            wipe_walk(&w, dir, WIPE_TREES, 0);  /* the Family Trees' Reports in older builds */
        }
    }
    if (wipe_folder(&w, root, L"Virtual Villagers Fun Patcher Data", top)) {
        wipe_walk(&w, top, WIPE_DATA, 0);
    }
    /* The family trees (and their Reports). */
    if (wipe_folder(&w, root, L"Virtual Villagers Fun Patcher Family Trees", top)) {
        wipe_walk(&w, top, WIPE_TREES, 0);
    }

    if (w.report != NULL && w.report_len > 0) {
        /* Listed for the player: what was kept and why.  Written beside the save folders, never in
           the one just wiped. */
        wchar_t parent[MAX_PATH];
        if (wipe_join(parent, root, L"Virtual Villagers Fun Patcher")
            && (CreateDirectoryW(parent, NULL) || GetLastError() == ERROR_ALREADY_EXISTS)
            && !(GetFileAttributesW(parent) & FILE_ATTRIBUTE_REPARSE_POINT)
            && wipe_join(report, parent, report_name)) {
            HANDLE file = CreateFileW(report, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
            if (file != INVALID_HANDLE_VALUE) {
                char head[512];
                SYSTEMTIME now;
                DWORD wrote = 0;
                int n;
                GetLocalTime(&now);
                n = wsprintfA(head, "Start Over of Save %d -- %04d-%02d-%02d %02d:%02d:%02d\r\n",
                              slot, now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute, now.wSecond);
                if (village != NULL && village[0] != '\0' && lstrlenA(village) < 256) {
                    int v = lstrlenA(village);
                    memcpy(head + n, village, (size_t)v);
                    n += v;
                    while (n > 0 && (head[n - 1] == '\n' || head[n - 1] == '\r')) {
                        --n;
                    }
                    head[n++] = '\r';
                    head[n++] = '\n';
                }
                lstrcpyA(head + n, "Start Over wiped everything the Fun Patcher kept for this save, except:\r\n\r\n");
                n += lstrlenA(head + n);
                (void)WriteFile(file, head, (DWORD)n, &wrote, NULL);
                (void)WriteFile(file, w.report, (DWORD)w.report_len, &wrote, NULL);
                CloseHandle(file);
            }
        }
    }
    if (w.words_lock != NULL) {
        vv_log_words_unlock(w.words_lock);
    }
    if (w.report != NULL) {
        HeapFree(GetProcessHeap(), 0, w.report);
    }
    return w.removed;
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
        {
            /* ...and the same file in the save's own folder (per_save.h). */
            wchar_t wide[MAX_PATH], own[MAX_PATH];
            if (MultiByteToWideChar(CP_ACP, 0, path, -1, wide, MAX_PATH) > 0
                && vv_ps_new_path_w(wide, own, MAX_PATH)) {
                removed += delete_if_present_w(own);
            }
        }
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
    /* ONE FOLDER OF LOGS PER SAVE SLOT (log_slot.h): the shared folder older builds wrote, and the
       slot's own "...Logs\Save <slot>\Village Statistics" -- each probed, never created. */
    if (legacy_subfolder_w(sub_w, L"Virtual Villagers Fun Patcher Logs\\Village Statistics")) {
        wsprintfW(path_w, L"%ls\\Village Statistics - Save %d.txt", sub_w, slot);
        removed += delete_log_w(game, slot, path_w);
        /* The current log, which replaced the file above. */
        wsprintfW(path_w, L"%ls\\Village Statistics v2 - Save %d.txt", sub_w, slot);
        removed += delete_log_w(game, slot, path_w);
    }
    {
        wchar_t slot_sub[MAX_PATH];
        if (vv_log_rel_w(slot_sub, MAX_PATH, slot, L"Village Statistics") && legacy_subfolder_w(sub_w, slot_sub)) {
            /* The same file the shared folder's sweep removes, no more. */
            wsprintfW(path_w, L"%ls\\Village Statistics v2 - Save %d.txt", sub_w, slot);
            removed += delete_log_w(game, slot, path_w);
        }
        /* ...and in the save's own folder (per_save.h). */
        if (vv_log_rel_w(slot_sub, MAX_PATH, slot, L"Village Statistics") && own_subfolder_w(sub_w, slot_sub)) {
            wsprintfW(path_w, L"%ls\\Village Statistics v2 - Save %d.txt", sub_w, slot);
            removed += delete_log_w(game, slot, path_w);
        }
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
            {
                /* The same two files in the save's own folder (per_save.h), probed by name. */
                static const wchar_t *const TAILS[2] = { L".dat", L".dat.tmp" };
                wchar_t old[MAX_PATH], own[MAX_PATH];
                int t;
                for (t = 0; t < 2; ++t) {
                    if ((int)wcslen(folder_w) + 1 + (int)wcslen(DATA_FOLDERS[data]) + 1
                            + (int)wcslen(DATA_STEMS[data]) + 16 < MAX_PATH) {
                        wchar_t digit[2];
                        digit[0] = (wchar_t)(L'0' + slot);
                        digit[1] = L'\0';
                        lstrcpyW(old, folder_w);
                        lstrcatW(old, L"\\");
                        lstrcatW(old, DATA_FOLDERS[data]);
                        lstrcatW(old, L"\\");
                        lstrcatW(old, DATA_STEMS[data]);
                        lstrcatW(old, L" ");
                        lstrcatW(old, digit);
                        lstrcatW(old, TAILS[t]);
                        if (vv_ps_new_path_w(old, own, MAX_PATH)) {
                            removed += delete_if_present_w(own);
                        }
                    }
                }
            }
            if (!legacy_subfolder_w(sub_w, DATA_FOLDERS[data])) {
                continue;
            }
            wsprintfW(path_w, L"%ls\\%ls %d.dat", sub_w, DATA_STEMS[data], slot);
            removed += delete_if_present_w(path_w);
            wsprintfW(path_w, L"%ls\\%ls %d.dat.tmp", sub_w, DATA_STEMS[data], slot);
            removed += delete_if_present_w(path_w);
        }
    }
    /* THE LOST CHILDREN'S ELDER TOTEMS (native/vvfp_vv2_totems): the slot's
       totems and its give-automatically setting belong to the village being
       erased.  A new file of the save's own folder only (never in the older
       layout): "<save>\Virtual Villagers Fun Patcher\Save <S>\Data\Elder
       Totems\ElderTotems.dat", its ".tmp", and "Elder Totem Settings.dat". */
    if (game == 2) {
        static const wchar_t *const TOTEM_FILES[3] = {
            L"ElderTotems.dat", L"ElderTotems.dat.tmp", L"Elder Totem Settings.dat"
        };
        int t;
        wchar_t totems[MAX_PATH];
        wchar_t save_dir[16];
        lstrcpyW(save_dir, L"Save ");
        save_dir[5] = (wchar_t)(L'0' + slot);
        save_dir[6] = L'\0';
        /* Joined with bounds (wipe_join), never formatted unbounded. */
        if (wipe_join(totems, folder_w, L"Virtual Villagers Fun Patcher") && wipe_join(path_w, totems, save_dir)
            && wipe_join(totems, path_w, L"Data\\Elder Totems")) {
            for (t = 0; t < 3; ++t) {
                if (wipe_join(path_w, totems, TOTEM_FILES[t])) {
                    removed += delete_if_present_w(path_w);
                }
            }
        }
    }
    /* The folder name before it was spelled out, probed but never
       recreated: a player who upgrades keeps whatever the previous build
       wrote, and a file left in a folder nothing writes to any more would
       survive a reset that was meant to clear it. */
    if (legacy_subfolder_w(sub_w, L"VVFP Logs\\Village Statistics")) {
        wsprintfW(path_w, L"%ls\\Village Statistics - Save %d.txt", sub_w, slot);
        removed += delete_log_w(game, slot, path_w);
    }
    /* The pre-move location, probed and cleared but never recreated. */
    wsprintfW(path_w, L"%ls\\Village Statistics - Save %d.txt", folder_w, slot);
    removed += delete_log_w(game, slot, path_w);
    /* THE ROSTER IS NUMBERED BY PAGE, NOT BY SLOT, so it is matched by the
       village header on each page's second line -- every page of the erased
       village, in the current folder and the retired one, and nothing else.
       Without a village string nothing is deleted, as for parentage.
       vv_save_subfolder_w creates the folder if absent, which is harmless
       here -- an empty folder is not a stale roster. */
    if (legacy_subfolder_w(sub_w, L"Virtual Villagers Fun Patcher Logs\\Tribe Population")) {
        removed += delete_village_population_pages(game, slot, sub_w, village);
    }
    {
        /* The slot's own roster folder (log_slot.h), matched by header like the shared one. */
        wchar_t slot_sub[MAX_PATH];
        if (vv_log_rel_w(slot_sub, MAX_PATH, slot, L"Tribe Population") && legacy_subfolder_w(sub_w, slot_sub)) {
            removed += delete_village_population_pages(game, slot, sub_w, village);
        }
        if (vv_log_rel_w(slot_sub, MAX_PATH, slot, L"Tribe Population") && own_subfolder_w(sub_w, slot_sub)) {
            removed += delete_village_population_pages(game, slot, sub_w, village);
        }
    }
    if (legacy_subfolder_w(sub_w, L"VVFP Logs\\Tribe Population")) {
        removed += delete_village_population_pages(game, slot, sub_w, village);
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
           reset must not create one.  Index 6 is the Island Events log
           ("VVFP Island Events.dll", through the same exporter), probed the
           same way. */
        /* Indexes 8 to 11 are the same four logs in the slot's own folder, "...Logs\Save <slot>\"
           (log_slot.h), where this build writes them; matched by header like every other. */
        static const wchar_t *const SLOT_SUBS[4] = {
            L"Births and Conceptions", L"Deaths and Disappearances", L"Unaccounted Villagers", L"Island Events"
        };
        static const wchar_t *const FOLDERS[8] = {
            L"Virtual Villagers Fun Patcher Logs\\Births and Conceptions",
            L"Virtual Villagers Fun Patcher Logs\\Tribe Parental Records",
            L"VVFP Logs\\Births and Conceptions",
            L"VVFP Logs\\Tribe Parental Records",
            L"Virtual Villagers Fun Patcher Logs\\Deaths and Disappearances",
            L"Virtual Villagers Fun Patcher Logs\\Unaccounted Villagers",
            L"Virtual Villagers Fun Patcher Logs\\Island Events",
            /* 7: the Deaths log's folder as older builds named it (native/shared/save_layout.h),
               while it has not been moved. */
            L"Virtual Villagers Fun Patcher Logs\\Deaths"
        };
        static const wchar_t *const EVENTS_LOG[5] = {
            L"Virtual Villagers 1 Island Events Log",
            L"Virtual Villagers 2 Island Events Log",
            L"Virtual Villagers 3 Island Events Log",
            L"Virtual Villagers 4 Island Events Log",
            L"Virtual Villagers 5 Island Events Log"
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
        /* Passes 12 to 15 are passes 8 to 11's logs in the save's own folder (per_save.h), probed
           and matched by header the same way. */
        for (pass = 0; pass < 16; ++pass) {
            /* The old FILE name went with the old FOLDER name, so the
               stem follows the folder rather than the pass number. */
            const int own_pass = pass >= 12;
            const int slot_pass = own_pass ? pass - 4 : pass;
            const wchar_t *stem = slot_pass >= 8
                ? (slot_pass == 8 ? PARENTAGE_LOG[game - 1] : slot_pass == 9 ? DEATH_LOG[game - 1]
                   : slot_pass == 10 ? UNACCOUNTED_LOG[game - 1] : EVENTS_LOG[game - 1])
                : pass == 6 ? EVENTS_LOG[game - 1]
                : pass == 5 ? UNACCOUNTED_LOG[game - 1]
                : pass == 4 || pass == 7 ? DEATH_LOG[game - 1]
                : (pass % 2 == 0) ? PARENTAGE_LOG[game - 1] : LEGACY_LOG[game - 1];
            if (slot_pass >= 8) {
                wchar_t slot_sub[MAX_PATH];
                if (!vv_log_rel_w(slot_sub, MAX_PATH, slot, SLOT_SUBS[slot_pass - 8])
                    || !(own_pass ? own_subfolder_w(sub_w, slot_sub) : legacy_subfolder_w(sub_w, slot_sub))) {
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
                            removed += delete_log_w(game, slot, path_w);
                        }
                    } while (FindNextFileW(search, &found));
                    FindClose(search);
                }
            }
        }
    }
    /* And then everything else of the slot's (the owner, v1.35.79; see wipe_slot above). */
    removed += wipe_slot(game, slot, village);
    return removed;
}
