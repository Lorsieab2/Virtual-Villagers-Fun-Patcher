/* Exercise select_log_file against REAL files with reset-created holes.
 *
 * The reset deletes only the erased village's numbered logs, so it leaves
 * gaps between files other villages still own. select_log_file used to end
 * its walk at the first missing number, which meant the surviving village
 * never saw its own later files: its cumulative conception count restarted,
 * and a birth took an older file as "newest" and landed apart from its own
 * conception.
 *
 * Reading the source cannot establish that. This builds the exact layout on
 * disk -- village A at 1 and 3 deleted, village B surviving at 2 and 4 --
 * and asks the real function what it returns.
 *
 * Built and run by scripts/build_select_holes_harness.ps1.
 */
#include <stdio.h>
#include <windows.h>
#include "../shared/harness_ldw_tree.h"

/* The size, in wide characters, of the buffer select_log_file writes its path
   into: parentage_export.c's MAX_LOG_PATH, which every shipped caller uses
   (tests/test_tribe_rename.py checks the two agree).  The harness passed a
   MAX_PATH (260) buffer, and _snwprintf_s(destination, MAX_LOG_PATH, ...)
   writes the LAST element of the stated size (destination[511]), not just
   the characters it formats: with `chosen` near the top of the main thread's
   stack, that write landed 502 bytes past it and off the end of the stack in
   about one run in ten (where the
   stack lands is randomised), an access violation before the first result
   line -- and, with stdout buffered, with no output at all. */
#define HARNESS_LOG_PATH 512

/* The unit under test, exposed for the harness. */
struct game_layout;
int select_log_file(const struct game_layout *g, const char *village,
                    wchar_t *destination, int *existing_records, int for_birth);
const struct game_layout *vv_parentage_layout(int game);
int vv_parentage_log_folder(wchar_t *out);
int vv_parentage_slot_log_folder(int slot, wchar_t *out);
int __stdcall EnsureParentageLog(int game_id, const char *village);

static int failures = 0;

static void check(int condition, const char *what) {
    printf("  [%s] %s\n", condition ? "PASS" : "FAIL", what);
    if (!condition) {
        ++failures;
    }
}

/* Conception records, with the village header the selector matches on. */
static void write_log(const wchar_t *folder, const wchar_t *stem, int number,
                      const char *village, int records) {
    wchar_t path[MAX_PATH];
    char line[512];
    HANDLE h;
    DWORD wrote;
    int i;
    wsprintfW(path, L"%ls\\%ls %d.txt", folder, stem, number);
    h = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        printf("  (could not create %ls: %lu)\n", path, GetLastError());
        return;
    }
    /* read_log_header takes the FIRST LINE VERBATIM and
       log_belongs_to_village compares it to the village string, so the header
       must be exactly that string, not a decorated form. An earlier version
       wrote "Village: X (Save 1)" and every file read as another village's,
       which made select_log_file refuse and looked like a defect in the code
       under test rather than in the harness. */
    wsprintfA(line, "%s\r\n\r\n", village);
    WriteFile(h, line, lstrlenA(line), &wrote, NULL);
    for (i = 0; i < records; ++i) {
        wsprintfA(line, "Conception %d\r\n  Mother: X\r\n\r\n", i + 1);
        WriteFile(h, line, lstrlenA(line), &wrote, NULL);
    }
    CloseHandle(h);
}

/* The same, numbering its records from `first` (a game's running count goes on across files). */
static void write_log_from(const wchar_t *folder, const wchar_t *stem, int number,
                           const char *village, int records, int first) {
    wchar_t path[MAX_PATH];
    char line[512];
    HANDLE h;
    DWORD wrote;
    int i;
    wsprintfW(path, L"%ls\\%ls %d.txt", folder, stem, number);
    h = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        printf("  (could not create %ls: %lu)\n", path, GetLastError());
        return;
    }
    wsprintfA(line, "%s\r\n\r\n", village);
    WriteFile(h, line, lstrlenA(line), &wrote, NULL);
    for (i = 0; i < records; ++i) {
        wsprintfA(line, "Conception %d\r\n  Mother: X\r\n\r\n", first + i);
        WriteFile(h, line, lstrlenA(line), &wrote, NULL);
    }
    CloseHandle(h);
}

static void remove_log(const wchar_t *folder, const wchar_t *stem, int number) {
    wchar_t path[MAX_PATH];
    wsprintfW(path, L"%ls\\%ls %d.txt", folder, stem, number);
    DeleteFileW(path);
}

static int present(const wchar_t *folder, const wchar_t *stem, int number) {
    wchar_t path[MAX_PATH];
    wsprintfW(path, L"%ls\\%ls %d.txt", folder, stem, number);
    return GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES;
}

int main(void) {
    harness_ldw_tree_begin();   /* first: leaves Documents\LDW as it found it */
    /* Unbuffered: piped stdout is otherwise fully buffered, and a run that dies
       part-way (a crash, a killed process) lost every line it had printed --
       the test then saw a nonzero exit and not one word of which check it
       reached.  (harness_ldw_tree_begin prints only to stderr, which is
       unbuffered already.) */
    setvbuf(stdout, NULL, _IONBF, 0);
    const struct game_layout *g = vv_parentage_layout(1);
    const wchar_t *stem = L"Virtual Villagers 1 Births and Conceptions Log";
    wchar_t folder[MAX_PATH];
    wchar_t chosen[HARNESS_LOG_PATH];
    wchar_t expect[HARNESS_LOG_PATH];
    int records = 0;
    int i;

    if (g == NULL || !vv_parentage_log_folder(folder)) {
        printf("  [FAIL] could not resolve the log folder\n");
        return 1;
    }
    printf("folder: %ls\n", folder);

    /* THE LAYOUT A RESET LEAVES BEHIND.
       Village A owned 1 and 3 and has been reset; village B owns 2 and 4. */
    write_log(folder, stem, 2, "Bravo", 5);
    write_log(folder, stem, 4, "Bravo", 7);

    /* A nonzero denominator: if the setup did not land, everything below
       would "pass" against an empty folder. */
    check(present(folder, stem, 2), "setup: file 2 exists");
    check(present(folder, stem, 4), "setup: file 4 exists");
    check(!present(folder, stem, 1), "setup: file 1 is a hole");
    check(!present(folder, stem, 3), "setup: file 3 is a hole");

    /* A CONCEPTION takes the first file of B's that has room. That is file
       2, past the hole at 1, and `existing` is the running total UP TO AND
       INCLUDING it -- 5, not 12. Before the fix the walk ended at the hole
       and never reached file 2 at all. */
    if (select_log_file(g, "Bravo", chosen, &records, 0)) {
        wsprintfW(expect, L"%ls\\%ls 2.txt", folder, stem);
        printf("  conception -> %ls (existing=%d)\n", chosen, records);
        check(lstrcmpiW(chosen, expect) == 0,
              "CONCEPTION REACHES FILE 2 PAST THE HOLE AT 1");
        check(records == 5, "its running total is file 2's own 5 records");
    } else {
        check(0, "select_log_file returned a path for a conception");
    }

    /* A BIRTH belongs in B's NEWEST file, which is 4 -- past two holes. */
    if (select_log_file(g, "Bravo", chosen, &records, 1)) {
        wsprintfW(expect, L"%ls\\%ls 4.txt", folder, stem);
        printf("  birth      -> %ls (existing=%d)\n", chosen, records);
        check(lstrcmpiW(chosen, expect) == 0,
              "BIRTH LANDS IN FILE 4, not an older file before the hole");
    } else {
        check(0, "select_log_file returned a path for a birth");
    }

    /* A NEW file must go AFTER the highest, never into a hole: the printed
       record number is a running total in file order, so a file dropped at 1
       or 3 would number records before ones already written in 4. */
    write_log(folder, stem, 2, "Bravo", 256);   /* full */
    write_log(folder, stem, 4, "Bravo", 256);   /* full */
    if (select_log_file(g, "Bravo", chosen, &records, 0)) {
        printf("  rollover   -> %ls\n", chosen);
        wsprintfW(expect, L"%ls\\%ls 1.txt", folder, stem);
        check(lstrcmpiW(chosen, expect) != 0,
              "a rollover does NOT drop into the hole at 1");
        wsprintfW(expect, L"%ls\\%ls 3.txt", folder, stem);
        check(lstrcmpiW(chosen, expect) != 0,
              "a rollover does NOT drop into the hole at 3");
        wsprintfW(expect, L"%ls\\%ls 5.txt", folder, stem);
        check(lstrcmpiW(chosen, expect) == 0,
              "a rollover goes after the highest existing file (5)");
    } else {
        check(0, "select_log_file returned a path for a rollover");
    }

    /* A BIRTH AT THE ROLLOVER BOUNDARY STAYS WITH ITS CONCEPTION.

       Births are not counted toward the roll, so a file is full the moment
       its 256th conception is written. The pregnancy that conception started
       is still in flight: its birth must go to that same file, not to the
       next one, which a conception would be handed. Asserting only that both
       calls share select_log_file passed while the birth rolled over (Codex,
       #423); this asks the real function at the boundary. */
    for (i = 1; i <= 8; ++i) {
        remove_log(folder, stem, i);
    }
    write_log(folder, stem, 1, "Bravo", 256);   /* conception 256 just filled it */
    check(present(folder, stem, 1), "setup: file 1 holds exactly 256 conceptions");
    if (select_log_file(g, "Bravo", chosen, &records, 0)) {
        wsprintfW(expect, L"%ls\\%ls 2.txt", folder, stem);
        printf("  boundary conception -> %ls (existing=%d)\n", chosen, records);
        check(lstrcmpiW(chosen, expect) == 0,
              "conception 257 rolls over to file 2");
        check(records == 256, "numbered after the 256 already written");
    } else {
        check(0, "select_log_file returned a path for conception 257");
    }
    if (select_log_file(g, "Bravo", chosen, &records, 1)) {
        wsprintfW(expect, L"%ls\\%ls 1.txt", folder, stem);
        printf("  boundary birth      -> %ls (existing=%d)\n", chosen, records);
        check(lstrcmpiW(chosen, expect) == 0,
              "A BIRTH AFTER CONCEPTION 256 STAYS IN FILE 1, beside its conception");
    } else {
        check(0, "select_log_file returned a path for the boundary birth");
    }
    check(!present(folder, stem, 2), "selection created no file");
    remove_log(folder, stem, 1);

    /* A GAP WIDER THAN ANY FIXED BOUND.

       An earlier fix stopped after a fixed run of missing numbers, assuming
       the widest gap a reset leaves is bounded by what one village owned.
       Gaps from SEVERAL reset villages coalesce, so no per-village figure
       bounds them: with a leading gap wider than the bound the selector
       returned no path at all and logging stopped. Found in review.

       100 consecutive holes is wider than the 64 that bound was, so this
       case fails against it and passes against the measured ceiling. */
    for (i = 1; i <= 8; ++i) {
        remove_log(folder, stem, i);
    }
    write_log(folder, stem, 101, "Bravo", 3);
    check(present(folder, stem, 101), "setup: file 101 exists past 100 holes");
    check(!present(folder, stem, 1), "setup: 1..100 are all holes");
    if (select_log_file(g, "Bravo", chosen, &records, 0)) {
        wsprintfW(expect, L"%ls\\%ls 101.txt", folder, stem);
        printf("  wide gap   -> %ls (existing=%d)\n", chosen, records);
        check(lstrcmpiW(chosen, expect) == 0,
              "SELECTION CROSSES A 100-FILE GAP to reach file 101");
        check(records == 3, "and counts its 3 records");
    } else {
        check(0, "select_log_file returned a path across a wide gap");
    }
    remove_log(folder, stem, 101);

    /* AN EMPTY FOLDER MUST STILL YIELD FILE 1.

       A fresh installation, or the folder after resetting the only village,
       has no logs at all. If the very first log can never be created, the
       feature simply does not work for a new player. Found in review. */
    for (i = 1; i <= 8; ++i) {
        remove_log(folder, stem, i);
    }
    check(!present(folder, stem, 1), "setup: the folder is empty");
    if (select_log_file(g, "Bravo", chosen, &records, 0)) {
        wsprintfW(expect, L"%ls\\%ls 1.txt", folder, stem);
        printf("  empty      -> %ls (existing=%d)\n", chosen, records);
        check(lstrcmpiW(chosen, expect) == 0,
              "AN EMPTY FOLDER YIELDS FILE 1 (a fresh install can log at all)");
        check(records == 0, "with a zero running total");
    } else {
        check(0, "select_log_file returned a path for an empty folder");
    }

    /* A HAND-MADE NAME MUST NOT RAISE THE CEILING.

       highest_log_number matches "<stem> <digits>.txt" and nothing else. If a
       backup or a note sharing the prefix could raise the ceiling, the walk
       would run past the real files toward a number nothing owns -- and a name
       parsing as a huge number would push it to the 4096 cap, which is exactly
       the probe cost the enumeration exists to avoid. */
    {
        wchar_t odd[MAX_PATH];
        HANDLE h;
        DWORD wrote;
        for (i = 1; i <= 8; ++i) {
            remove_log(folder, stem, i);
        }
        /* FULL, so the walk cannot return early and must run to the
           ceiling -- which is the only situation where a raised ceiling
           costs anything. With a file that has room the loop returns at
           once and the ceiling never matters, which is why an earlier
           version of this case passed against its own mutation. */
        write_log(folder, stem, 2, "Bravo", 256);

        /* A LEADING ZERO IS NOT CANONICAL. The exporter formats with %d, so
           "... Log 04096.txt" is not a file it wrote -- but parsed as 4096 it
           raised the ceiling and reintroduced 4096 probes per call, the exact
           cost the enumeration removes. Found in review. */
        wsprintfW(odd, L"%ls\\%ls 04096.txt", folder, stem);
        h = CreateFileW(odd, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                        FILE_ATTRIBUTE_NORMAL, NULL);
        if (h != INVALID_HANDLE_VALUE) {
            WriteFile(h, "x", 1, &wrote, NULL);
            CloseHandle(h);
        }
        wsprintfW(odd, L"%ls\\%ls 9999 backup.txt", folder, stem);
        h = CreateFileW(odd, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                        FILE_ATTRIBUTE_NORMAL, NULL);
        if (h != INVALID_HANDLE_VALUE) {
            WriteFile(h, "x", 1, &wrote, NULL);
            CloseHandle(h);
        }
        wsprintfW(odd, L"%ls\\%ls copy.txt", folder, stem);
        h = CreateFileW(odd, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                        FILE_ATTRIBUTE_NORMAL, NULL);
        if (h != INVALID_HANDLE_VALUE) {
            WriteFile(h, "x", 1, &wrote, NULL);
            CloseHandle(h);
        }

        /* THE HARM IS COST, NOT JUST CORRECTNESS.

           A leading-zero name parses as a huge number and raises the ceiling,
           so the walk probes thousands of absent files on EVERY conception
           and birth -- the stall this enumeration exists to remove. Selection
           still lands correctly, so asserting only the path lets that
           regression through: an earlier version of this case passed against
           the very mutation it was written to catch.

           Time it instead. A correct scan touches a handful of files and is
           effectively instant; 4096 probes take hundreds of milliseconds even
           on a local disk, and far longer on OneDrive or a share. */
        {
            LARGE_INTEGER freq, t0, t1;
            double ms;
            int ok;
            QueryPerformanceFrequency(&freq);
            QueryPerformanceCounter(&t0);
            ok = select_log_file(g, "Bravo", chosen, &records, 0);
            QueryPerformanceCounter(&t1);
            ms = 1000.0 * (double)(t1.QuadPart - t0.QuadPart) / (double)freq.QuadPart;
            if (ok) {
                wsprintfW(expect, L"%ls\\%ls 3.txt", folder, stem);
                printf("  odd names  -> %ls (existing=%d, %.1f ms)\n",
                       chosen, records, ms);
                check(lstrcmpiW(chosen, expect) == 0,
                      "A HAND-MADE NAME DOES NOT DIVERT SELECTION (rolls to 3)");
                check(records == 256, "and does not disturb the running total");
                check(ms < 50.0,
                      "AND DOES NOT RAISE THE CEILING (scan stays fast)");
            } else {
                check(0, "select_log_file returned a path beside odd names");
            }
        }

        wsprintfW(odd, L"%ls\\%ls 9999 backup.txt", folder, stem);
        DeleteFileW(odd);
        wsprintfW(odd, L"%ls\\%ls copy.txt", folder, stem);
        DeleteFileW(odd);
        wsprintfW(odd, L"%ls\\%ls 04096.txt", folder, stem);
        DeleteFileW(odd);
        remove_log(folder, stem, 2);
    }

    /* A RENAMED TRIBE KEEPS ITS LOG.

       Rename Tribe changes the name in a closed game's save and appends
       "Tribe renamed from <old> to <new> on <date>" to the village's logs,
       never touching the header. The next save publishes the NEW header, so
       selection must follow the note: the same file, the same running total,
       and no new file -- otherwise the first record after a rename starts a
       fresh log as if the village were new. */
    {
        static const char NOTE[] = "Tribe renamed from Old Name to New Name on 2026-10-04\r\n";
        static const char NOTE2[] = "Tribe renamed from New Name to Third on 2026-10-05\r\n";
        wchar_t path[MAX_PATH];
        wchar_t folder[MAX_PATH];     /* "(Save 1)": that slot's own folder (log_slot.h) */
        HANDLE h;
        DWORD wrote;
        vv_parentage_slot_log_folder(1, folder);
        for (i = 1; i <= 8; ++i) {
            remove_log(folder, stem, i);
        }
        write_log(folder, stem, 1, "Village: Old Name (Save 1)", 3);
        wsprintfW(path, L"%ls\\%ls 1.txt", folder, stem);
        h = CreateFileW(path, FILE_APPEND_DATA, 0, NULL, OPEN_EXISTING,
                        FILE_ATTRIBUTE_NORMAL, NULL);
        if (h != INVALID_HANDLE_VALUE) {
            WriteFile(h, NOTE, lstrlenA(NOTE), &wrote, NULL);
            CloseHandle(h);
        }
        check(present(folder, stem, 1), "setup: the renamed village's file 1 exists");
        if (select_log_file(g, "Village: New Name (Save 1)\n", chosen, &records, 0)) {
            wsprintfW(expect, L"%ls\\%ls 1.txt", folder, stem);
            printf("  renamed    -> %ls (existing=%d)\n", chosen, records);
            check(lstrcmpiW(chosen, expect) == 0,
                  "A CONCEPTION AFTER A RENAME STAYS IN THE VILLAGE'S FILE 1");
            check(records == 3, "and continues its running total (3)");
        } else {
            check(0, "select_log_file returned a path after a rename");
        }
        if (select_log_file(g, "Village: New Name (Save 1)\n", chosen, &records, 1)) {
            wsprintfW(expect, L"%ls\\%ls 1.txt", folder, stem);
            check(lstrcmpiW(chosen, expect) == 0,
                  "A BIRTH AFTER A RENAME STAYS IN FILE 1 beside its conception");
        } else {
            check(0, "select_log_file returned a path for a birth after a rename");
        }
        /* The old name is no longer this file's village. */
        if (select_log_file(g, "Village: Old Name (Save 1)\n", chosen, &records, 0)) {
            wsprintfW(expect, L"%ls\\%ls 1.txt", folder, stem);
            check(lstrcmpiW(chosen, expect) != 0,
                  "the OLD name no longer selects the renamed village's file");
        }
        /* EnsureParentageLog runs after every save: it must find the file,
           not head a new one for the "new" village. */
        EnsureParentageLog(1, "Village: New Name (Save 1)\n");
        check(!present(folder, stem, 2),
              "THE SAVE AFTER A RENAME CREATES NO NEW LOG (no rollover)");
        /* A second rename chains. */
        h = CreateFileW(path, FILE_APPEND_DATA, 0, NULL, OPEN_EXISTING,
                        FILE_ATTRIBUTE_NORMAL, NULL);
        if (h != INVALID_HANDLE_VALUE) {
            WriteFile(h, NOTE2, lstrlenA(NOTE2), &wrote, NULL);
            CloseHandle(h);
        }
        if (select_log_file(g, "Village: Third (Save 1)\n", chosen, &records, 0)) {
            wsprintfW(expect, L"%ls\\%ls 1.txt", folder, stem);
            check(lstrcmpiW(chosen, expect) == 0,
                  "A SECOND RENAME CHAINS: the newest name selects file 1");
        } else {
            check(0, "select_log_file returned a path after a second rename");
        }
        /* The note names the slot only through the header: the same new name
           in ANOTHER slot is another village. */
        if (select_log_file(g, "Village: Third (Save 2)\n", chosen, &records, 0)) {
            wsprintfW(expect, L"%ls\\%ls 1.txt", folder, stem);
            check(lstrcmpiW(chosen, expect) != 0,
                  "the new name in a different save slot is another village");
        }
        for (i = 1; i <= 8; ++i) {
            remove_log(folder, stem, i);
        }
    }

    /* ONE FOLDER OF LOGS PER SAVE SLOT (native/shared/log_slot.h).

       A village "(Save S)" is logged in "...Logs\Save S\Births and Conceptions"; the shared
       folder older builds wrote is only read.  Numbers are the GAME's: a record continues after
       the highest number printed in the shared folder and in every slot's. */
    {
        wchar_t shared[MAX_PATH], save1[MAX_PATH], save2[MAX_PATH], save3[MAX_PATH];
        int k;
        lstrcpyW(shared, folder);
        vv_parentage_slot_log_folder(1, save1);
        vv_parentage_slot_log_folder(2, save2);
        vv_parentage_slot_log_folder(3, save3);
        for (k = 1; k <= 8; ++k) {
            remove_log(shared, stem, k);
            remove_log(save1, stem, k);
            remove_log(save2, stem, k);
            remove_log(save3, stem, k);
        }
        /* An older build's shared log: Alpha (Save 1) Conceptions 1-3 in file 1, Beta (Save 2)
           Conceptions 4-5 in file 2. */
        write_log_from(shared, stem, 1, "Village: Alpha (Save 1)", 3, 1);
        write_log_from(shared, stem, 2, "Village: Beta (Save 2)", 2, 4);
        if (select_log_file(g, "Village: Alpha (Save 1)\n", chosen, &records, 0)) {
            wsprintfW(expect, L"%ls\\%ls 1.txt", save1, stem);
            printf("  slot 1     -> %ls (existing=%d)\n", chosen, records);
            check(lstrcmpiW(chosen, expect) == 0,
                  "A SAVE 1 RECORD GOES TO SAVE 1'S OWN FOLDER, not the shared file it once used");
            check(records == 5, "numbered after the shared folder's highest (Conception 6)");
        } else {
            check(0, "select_log_file returned a path for Save 1");
        }
        /* This build then wrote Conception 6-7 for Alpha in Save 1's folder. */
        write_log_from(save1, stem, 1, "Village: Alpha (Save 1)", 2, 6);
        if (select_log_file(g, "Village: Beta (Save 2)\n", chosen, &records, 0)) {
            wsprintfW(expect, L"%ls\\%ls 1.txt", save2, stem);
            printf("  slot 2     -> %ls (existing=%d)\n", chosen, records);
            check(lstrcmpiW(chosen, expect) == 0, "TWO SLOTS STAY APART: Save 2 has its own folder");
            check(records == 7, "and continues the game's numbering after Save 1's Conception 7");
        } else {
            check(0, "select_log_file returned a path for Save 2");
        }
        if (select_log_file(g, "Village: Alpha (Save 1)\n", chosen, &records, 0)) {
            wsprintfW(expect, L"%ls\\%ls 1.txt", save1, stem);
            check(lstrcmpiW(chosen, expect) == 0 && records == 7,
                  "Save 1's next record stays in its file 1, numbered 8");
        }
        if (select_log_file(g, "Village: Alpha (Save 1)\n", chosen, &records, 1)) {
            wsprintfW(expect, L"%ls\\%ls 1.txt", save1, stem);
            check(lstrcmpiW(chosen, expect) == 0, "a birth goes to the slot's newest file");
        }
        /* The save after a new village is made creates its log in its slot's folder, headed. */
        EnsureParentageLog(1, "Village: Gamma (Save 3)\n");
        check(present(save3, stem, 1), "VILLAGE CREATION MAKES SAVE 3'S OWN LOG");
        check(!present(shared, stem, 3) && !present(save1, stem, 2),
              "...and nothing in the shared folder or another slot's");
        check(present(shared, stem, 1) && present(shared, stem, 2), "the shared files are all still there");
        for (k = 1; k <= 8; ++k) {
            remove_log(shared, stem, k);
            remove_log(save1, stem, k);
            remove_log(save2, stem, k);
            remove_log(save3, stem, k);
        }
    }

    if (failures) {
        printf("  (files left in place for inspection)\n");
    } else {
        for (i = 1; i <= 8; ++i) {
            remove_log(folder, stem, i);
        }
    }
    if (failures) {
        printf("\nFAILED (%d failure(s))\n", failures);
    } else {
        printf("\nOK (0 failures)\n");
    }
    return failures ? 1 : 0;
}
