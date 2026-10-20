/* Start Over clears the deleted logs' Like and Dislike Words boundaries -- on real files.
 *
 * The boundary files (log_words.h) hold "<offset>\t<key>\r\n" lines keyed by each log's path
 * inside the save folder, and an exporter records a new boundary for a log only when none is
 * recorded. Before v1.35.78 Start Over deleted the erased village's logs but kept their lines,
 * so the next village's log of the same name inherited the old boundary and its correct words
 * were treated as old ones (the owner's report, 2026-10-19).
 *
 * For each of the five games this builds the boundary files the way the companions leave them
 * -- the save's own, the shared one and an older build's "Log Words" one -- runs the real reset,
 * and checks, byte for byte, that only the deleted logs' lines went: another save's lines, this
 * save's kept Village History line and another village's shared log line all stay. Then a new log
 * of the same name is started the way an exporter starts one and must get boundary 0.
 *
 * Built and run by scripts/build_save_reset_words_harness.ps1 (tests/test_start_over_clears_
 * like_dislike_words.py). Documents is redirected to a %TEMP% folder (harness_ldw_tree.h).
 */
#include <stdio.h>
#include <string.h>
#include <windows.h>

#include "save_folder.h"
#include "save_reset.h"
#include "harness_ldw_tree.h"
#include "log_words.h"

/* The reset's test hook and refusal count (VV_RESET_TESTABLE, save_reset.c). */
extern void (*vv_reset_words_test_hook)(const char *dat);
extern int vv_reset_words_refusals;

static int failures = 0;

/* AN APPEND MADE DURING THE RESET. The hook runs after the reset has read the save's own boundary
   file and before it replaces it; it starts a writer that appends a boundary for another log the
   way an exporter does, and checks the writer is held back until the reset is done. */
static int race_game;
static char race_dat[MAX_PATH];
static char race_key[MAX_PATH];
static wchar_t race_log_w[MAX_PATH];
static HANDLE race_thread;
static int race_blocked;

static DWORD WINAPI race_writer(LPVOID unused) {
    (void)unused;
    if (vv_log_words_tracked(race_game)) {
        vv_log_words_appending(race_game, race_log_w);     /* the exporters' own path */
    } else {
        HANDLE lock = vv_log_words_lock(race_game);         /* what it does, for every game */
        if (lock != NULL) {
            vv_log_words_note(race_dat, 0, race_key);
            vv_log_words_unlock(lock);
        }
    }
    return 0;
}

static void race_hook(const char *dat) {
    if (race_thread != NULL || lstrcmpiA(dat, race_dat) != 0) {
        return;
    }
    race_thread = CreateThread(NULL, 0, race_writer, NULL, 0, NULL);
    race_blocked = race_thread != NULL && WaitForSingleObject(race_thread, 300) == WAIT_TIMEOUT;
}

/* A holder that keeps the game's lock longer than any writer waits. */
static HANDLE hold_taken, hold_release;
static int hold_game;

static DWORD WINAPI lock_holder(LPVOID unused) {
    HANDLE lock;
    (void)unused;
    lock = vv_log_words_lock(hold_game);
    SetEvent(hold_taken);
    WaitForSingleObject(hold_release, 15000);
    vv_log_words_unlock(lock);
    return 0;
}

/* Any "<boundary file>.*" temporary left beside it. */
static int temporaries_beside(const char *dat) {
    char filter[MAX_PATH];
    WIN32_FIND_DATAA found;
    HANDLE search;
    const char *base = strrchr(dat, '\\');
    int any = 0;
    base = base != NULL ? base + 1 : dat;
    wsprintfA(filter, "%s.*", dat);
    search = FindFirstFileA(filter, &found);
    if (search == INVALID_HANDLE_VALUE) {
        return 0;
    }
    do {
        /* "<name>.*" also matches "<name>" itself: only a longer name is a temporary. */
        if (lstrlenA(found.cFileName) > lstrlenA(base)) {
            any = 1;
        }
    } while (FindNextFileA(search, &found));
    FindClose(search);
    return any;
}

static void check(int game, int condition, const char *what) {
    printf("  [%s] game %d: %s\n", condition ? "PASS" : "FAIL", game, what);
    if (!condition) {
        ++failures;
    }
}

static void write_text(const char *path, const char *text) {
    HANDLE h;
    DWORD written = 0;
    vv_ps_make_parents_a(path);
    h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h != INVALID_HANDLE_VALUE) {
        WriteFile(h, text, (DWORD)lstrlenA(text), &written, NULL);
        CloseHandle(h);
    }
}

static int exists(const char *path) {
    return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

/* The whole file as text (at most 8 KB), or "" when it cannot be read. */
static const char *read_text(const char *path, char *out, int size) {
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD got = 0;
    out[0] = '\0';
    if (h != INVALID_HANDLE_VALUE) {
        if (ReadFile(h, out, (DWORD)size - 1, &got, NULL)) {
            out[got] = '\0';
        }
        CloseHandle(h);
    }
    return out;
}

static int written_at(const char *path, FILETIME *when) {
    WIN32_FILE_ATTRIBUTE_DATA info;
    if (!GetFileAttributesExA(path, GetFileExInfoStandard, &info)) {
        return 0;
    }
    *when = info.ftLastWriteTime;
    return 1;
}

/* "<folder>\<rel>\<name>" in a and its wide form; the folder is made (routed like a companion's). */
static int place(char *a, wchar_t *w, const char *rel, const char *name) {
    char dir[MAX_PATH];
    if (!vv_save_subfolder(dir, rel, 96)) {
        return 0;
    }
    wsprintfA(a, "%s\\%s", dir, name);
    return MultiByteToWideChar(CP_ACP, 0, a, -1, w, MAX_PATH) > 0;
}

int main(void) {
    harness_ldw_tree_begin();   /* first: Documents is a %TEMP% folder, left as found */
    static const char VILLAGE[] = "Village: Kalahuna (Save 1)\n";
    static const char VILLAGE2[] = "Village: Elsewhere (Save 2)\n";
    int game;

    /* NEVER THE PLAYER'S SAVES: the folder the reset resolves must be inside the throwaway
       Documents harness_ldw_tree_begin made under %TEMP%, or nothing below runs. */
    {
        char folder[MAX_PATH], temp[MAX_PATH];
        const char *docs = harness_redirect_documents_path();
        DWORD n = GetTempPathA(MAX_PATH, temp);
        if (!vv_save_folder(folder, 64) || n == 0 || n >= MAX_PATH || docs[0] == '\0'
            || _strnicmp(folder, temp, n) != 0 || _strnicmp(folder, docs, strlen(docs)) != 0
            || folder[strlen(docs)] != '\\') {
            printf("the save folder is not under the throwaway Documents (%s); not running\n", docs);
            return 2;
        }
        printf("save folder: %s\n", folder);
    }

    for (game = 1; game <= 5; ++game) {
        char log1[MAX_PATH], deaths1[MAX_PATH], hist1[MAX_PATH], slot2[MAX_PATH], other[MAX_PATH];
        wchar_t log1_w[MAX_PATH], deaths1_w[MAX_PATH], hist1_w[MAX_PATH], slot2_w[MAX_PATH], other_w[MAX_PATH];
        char k_log1[MAX_PATH], k_deaths1[MAX_PATH], k_hist1[MAX_PATH], k_slot2[MAX_PATH], k_other[MAX_PATH];
        char save1_dat[MAX_PATH], save2_dat[MAX_PATH], new_dat[MAX_PATH], old_dat[MAX_PATH];
        char name[MAX_PATH], text[8192], want[8192], buf[8192];
        FILETIME save2_before, save2_after;
        LONGLONG offset = -1;
        int ok;

        printf("game %d\n", game);
        /* The erased village's (save 1) Births log in the save's own folder, its Deaths log in the
           shared folder (recorded under the folder's older name, "Deaths"), and its Village History,
           which Start Over keeps; save 2's Births log; another village's log in the shared folder. */
        wsprintfA(name, "Virtual Villagers %d Births and Conceptions Log 1.txt", game);
        ok = place(log1, log1_w, "Virtual Villagers Fun Patcher Logs\\Save 1\\Births and Conceptions", name)
             && place(slot2, slot2_w, "Virtual Villagers Fun Patcher Logs\\Save 2\\Births and Conceptions", name);
        wsprintfA(name, "Virtual Villagers %d Deaths Log 1.txt", game);
        ok = ok && place(deaths1, deaths1_w, "Virtual Villagers Fun Patcher Logs\\Deaths and Disappearances", name);
        ok = ok && place(hist1, hist1_w, "Virtual Villagers Fun Patcher Logs\\Save 1\\Tribe History", "Village History 1.txt");
        wsprintfA(name, "Virtual Villagers %d Births and Conceptions Log 2.txt", game);
        ok = ok && place(other, other_w, "Virtual Villagers Fun Patcher Logs\\Births and Conceptions", name);
        ok = ok && vv_log_words_name(log1_w, k_log1, MAX_PATH) && vv_log_words_name(deaths1_w, k_deaths1, MAX_PATH)
             && vv_log_words_name(hist1_w, k_hist1, MAX_PATH) && vv_log_words_name(slot2_w, k_slot2, MAX_PATH)
             && vv_log_words_name(other_w, k_other, MAX_PATH);
        ok = ok && vv_log_words_save_path(game, 1, save1_dat, MAX_PATH) && vv_log_words_save_path(game, 2, save2_dat, MAX_PATH)
             && vv_log_words_paths(game, new_dat, old_dat, MAX_PATH);
        if (!ok) {
            check(game, 0, "the fixture paths resolve");
            continue;
        }
        check(game, strncmp(k_log1, "Virtual Villagers Fun Patcher\\Save 1\\Logs\\", 42) == 0,
              "the save-1 log's key is in the save's own folder");
        check(game, strncmp(k_deaths1, "Virtual Villagers Fun Patcher Logs\\Deaths\\", 42) == 0,
              "the shared Deaths log is keyed under the folder's older name");

        write_text(log1, VILLAGE);
        write_text(deaths1, VILLAGE);
        write_text(hist1, "=== Virtual Villagers -- 2026-10-10 10:00:00 ===\nVillage: Kalahuna (Save 1)\n\n");
        write_text(slot2, VILLAGE2);
        write_text(other, VILLAGE2);

        wsprintfA(text, "5000\t%s\r\n777\t%s\r\n4800\t%s\r\n", k_log1, k_hist1, k_log1);
        write_text(save1_dat, text);
        wsprintfA(text, "4000\t%s\r\n", k_slot2);
        write_text(save2_dat, text);
        wsprintfA(text, "3000\t%s\r\n888\t%s\r\n2500\t%s\r\n", k_deaths1, k_hist1, k_other);
        write_text(new_dat, text);
        wsprintfA(text, "1234\t%s\r\n6000\t%s\r\n2600\t%s\r\n", k_deaths1, k_log1, k_other);
        write_text(old_dat, text);
        Sleep(20);
        check(game, written_at(save2_dat, &save2_before), "save 2's boundary file written");
        check(game, vv_log_words_recorded(game, k_log1, &offset) && offset == 4800,
              "before Start Over the save-1 log has its boundary (nonzero denominator)");

        vv_reset_slot_state(game, 1, VILLAGE);

        check(game, !exists(log1) && !exists(deaths1), "Start Over deleted the erased village's logs");
        /* START OVER WIPES THE WHOLE SAVE (the owner, v1.35.79): the Village History goes too, and
           the save's own words file with the save's folder. */
        check(game, !exists(hist1), "THE VILLAGE HISTORY IS DELETED TOO (v1.35.79)");
        check(game, exists(slot2) && exists(other), "...and save 2's and another village's logs are kept");
        check(game, !exists(save1_dat), "the save's own words file goes with the save's folder");
        check(game, !vv_log_words_recorded(game, k_log1, &offset),
              "A DELETED LOG'S BOUNDARY IS GONE (save's own file and the older shared one)");
        check(game, !vv_log_words_recorded(game, k_deaths1, &offset),
              "a deleted shared log's boundary is gone from both shared files");
        check(game, !vv_log_words_recorded(game, k_hist1, &offset),
              "the deleted Village History's boundary is gone, from the shared file too");
        wsprintfA(want, "4000\t%s\r\n", k_slot2);
        check(game, strcmp(read_text(save2_dat, buf, sizeof buf), want) == 0,
              "ANOTHER SAVE'S BOUNDARY STAYS, byte for byte");
        check(game, written_at(save2_dat, &save2_after) && CompareFileTime(&save2_before, &save2_after) == 0,
              "another save's boundary file is not rewritten at all");
        wsprintfA(want, "2500\t%s\r\n", k_other);
        check(game, strcmp(read_text(new_dat, buf, sizeof buf), want) == 0,
              "the shared file keeps another village's line, byte for byte");
        wsprintfA(want, "2600\t%s\r\n", k_other);
        check(game, strcmp(read_text(old_dat, buf, sizeof buf), want) == 0,
              "the older Log Words file keeps another village's line, byte for byte");
        check(game, !temporaries_beside(save1_dat) && !temporaries_beside(new_dat) && !temporaries_beside(old_dat),
              "no .tmp is left beside the rewritten file");

        /* The next village starts a log of the same name, as an exporter does. */
        write_text(log1, "");
        vv_log_words_appending(game, log1_w);
        check(game, vv_log_words_boundary(game, log1_w) == 0,
              "A NEW LOG REUSING THE NAME DOES NOT INHERIT THE OLD BOUNDARY (boundary 0)");
        if (vv_log_words_tracked(game)) {
            wsprintfA(want, "0\t%s\r\n", k_log1);
            check(game, strcmp(read_text(save1_dat, buf, sizeof buf), want) == 0,
                  "the new log's boundary 0 is recorded in the save's own file");
        }

        /* AN APPEND MADE DURING THE RESET IS KEPT (Codex, #597): it waits for the reset's lock and
           lands after the replace, never into the file the replace then overwrites.  Raced on the
           shared file: the save's own one goes with the save's folder (v1.35.79). */
        {
            char island[MAX_PATH];
            wsprintfA(name, "Virtual Villagers %d Island Events Log 1.txt", game);
            if (!place(island, race_log_w, "Virtual Villagers Fun Patcher Logs\\Island Events", name)
                || !vv_log_words_name(race_log_w, race_key, MAX_PATH)) {
                check(game, 0, "the racing log's path resolves");
            } else {
                DeleteFileA(island);              /* a new log: its boundary is 0 */
                race_game = game;
                lstrcpyA(race_dat, new_dat);
                race_thread = NULL;
                race_blocked = 0;
                write_text(log1, VILLAGE);
                write_text(deaths1, VILLAGE);
                wsprintfA(text, "3000\t%s\r\n2500\t%s\r\n", k_deaths1, k_other);
                write_text(new_dat, text);
                vv_reset_words_test_hook = race_hook;
                vv_reset_slot_state(game, 1, VILLAGE);
                vv_reset_words_test_hook = NULL;
                check(game, race_thread != NULL, "a writer appended while the reset was replacing the file");
                if (race_thread != NULL) {
                    check(game, WaitForSingleObject(race_thread, 10000) == WAIT_OBJECT_0, "...and finished");
                    CloseHandle(race_thread);
                    race_thread = NULL;
                }
                check(game, race_blocked, "THE WRITER WAITED FOR THE RESET'S LOCK");
                wsprintfA(want, "2500\t%s\r\n0\t%s\r\n", k_other, race_key);
                check(game, strcmp(read_text(new_dat, buf, sizeof buf), want) == 0,
                      "AN APPEND MADE DURING THE RESET IS KEPT, and the deleted log's line is still gone");
                DeleteFileA(island);
            }
        }

        /* A LOCK HELD TOO LONG: the reset waits a bounded time, leaves every boundary file as it
           was, counts the refusal, and still deletes the log. */
        {
            DWORD started, took;
            int refusals = vv_reset_words_refusals;
            HANDLE holder;
            write_text(log1, VILLAGE);
            wsprintfA(text, "6000\t%s\r\n2500\t%s\r\n", k_log1, k_other);
            write_text(new_dat, text);
            hold_game = game;
            hold_taken = CreateEventA(NULL, TRUE, FALSE, NULL);
            hold_release = CreateEventA(NULL, TRUE, FALSE, NULL);
            holder = CreateThread(NULL, 0, lock_holder, NULL, 0, NULL);
            WaitForSingleObject(hold_taken, 5000);
            started = GetTickCount();
            vv_reset_slot_state(game, 1, VILLAGE);
            took = GetTickCount() - started;
            SetEvent(hold_release);
            WaitForSingleObject(holder, 10000);
            CloseHandle(holder); CloseHandle(hold_taken); CloseHandle(hold_release);
            check(game, !exists(log1), "with the lock held elsewhere the log is still deleted");
            check(game, strcmp(read_text(new_dat, buf, sizeof buf), text) == 0,
                  "A LOCK NOT HAD IN TIME LEAVES THE BOUNDARY FILE UNTOUCHED");
            /* Once for the log the named passes deleted, once for the whole wipe (v1.35.79): never
               once per file the wipe deletes. */
            check(game, vv_reset_words_refusals == refusals + 2, "...and the refusals are counted");
            check(game, took >= 2 * VV_LOG_WORDS_LOCK_MS - 100 && took < 2 * VV_LOG_WORDS_LOCK_MS + 3000,
                  "the reset waited the bounded time, no longer");
        }

        DeleteFileA(log1); DeleteFileA(hist1); DeleteFileA(slot2); DeleteFileA(other);
        DeleteFileA(save1_dat); DeleteFileA(save2_dat); DeleteFileA(new_dat); DeleteFileA(old_dat);
    }

    printf("\n%s (%d failure%s)\n", failures ? "FAILED" : "OK", failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}
