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

/* The unit under test, exposed for the harness. */
struct game_layout;
int select_log_file(const struct game_layout *g, const char *village,
                    wchar_t *destination, int *existing_records, int for_birth);
const struct game_layout *vv_parentage_layout(int game);
int vv_parentage_log_folder(wchar_t *out);

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
    const struct game_layout *g = vv_parentage_layout(1);
    const wchar_t *stem = L"Virtual Villagers 1 Births and Conceptions Log";
    wchar_t folder[MAX_PATH];
    wchar_t chosen[MAX_PATH];
    wchar_t expect[MAX_PATH];
    int records = 0;
    int i;

    if (g == NULL || !vv_parentage_log_folder(folder)) {
        printf("  [FAIL] could not resolve the log folder\n");
        return 1;
    }
    printf("folder: %ls\n", folder);

    /* Clear anything a previous run left. */
    for (i = 1; i <= 8; ++i) {
        remove_log(folder, stem, i);
    }

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
