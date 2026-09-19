/* Exercise vv_reset_slot_state against real files on disk.
 *
 * The properties that matter here cannot be established by reading the source:
 * that the right files are deleted, that neighbouring slots and the game's own
 * saves survive, and that an unresolvable path deletes nothing. So this creates
 * actual files, runs the real reset, and checks what is left.
 *
 * It runs as a 32-bit console program because that is what the companions are.
 * The save folder is resolved from the exe basename, so the harness copies
 * itself nowhere and instead reports which folder it resolved -- the caller
 * points it at a throwaway Documents via the usual environment.
 */
#include <stdio.h>
#include <windows.h>

#include "save_folder.h"
#include "save_reset.h"

/* the reset's internal guards, exposed by VV_RESET_TESTABLE */
int delete_if_present(const char *path);
int delete_if_present_w(const wchar_t *path);
int vv_save_folder_w(wchar_t *out, int reserve);
extern int vv_reset_refused_paths;

static int failures = 0;

static void check(int condition, const char *what) {
    printf("  [%s] %s\n", condition ? "PASS" : "FAIL", what);
    if (!condition) {
        ++failures;
    }
}

static void touch(const char *path) {
    HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD written = 0;
    if (h != INVALID_HANDLE_VALUE) {
        WriteFile(h, "x", 1, &written, NULL);
        CloseHandle(h);
    }
}

static int exists(const char *path) {
    return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

int main(void) {
    char folder[MAX_PATH];
    wchar_t folder_w_probe[MAX_PATH];
    char mask1[MAX_PATH], mask2[MAX_PATH], doubler1[MAX_PATH];
    char save1[MAX_PATH], other_game[MAX_PATH];
    char log1[MAX_PATH];
    int removed;

    if (!vv_save_folder(folder, 64)) {
        printf("could not resolve the save folder\n");
        return 2;
    }
    printf("save folder: %s\n\n", folder);
    if (!vv_save_folder_w(folder_w_probe, 64)) {
        printf("could not resolve the wide save folder\n");
        return 2;
    }

    /* VV1 owns two sidecars per slot. Create slot 1 and slot 2, plus a game
       save and a file belonging to a different game, so the test can show what
       survives as well as what goes. */
    wsprintfA(mask1, "%s\\vv1_masks_1.dat", folder);
    wsprintfA(mask2, "%s\\vv1_masks_2.dat", folder);
    wsprintfA(doubler1, "%s\\vv1_doublers_1.dat", folder);
    wsprintfA(save1, "%s\\Virtual Villagers1.ldw", folder);
    wsprintfA(other_game, "%s\\vv2_masks_1.dat", folder);
    wsprintfA(log1, "%s\\Virtual Villagers 1 Parentage Log 1.txt", folder);

    touch(mask1); touch(mask2); touch(doubler1);
    touch(save1); touch(other_game); touch(log1);

    printf("created 6 files; resetting VV1 slot 1\n");
    check(exists(mask1) && exists(mask2) && exists(doubler1)
          && exists(save1) && exists(other_game) && exists(log1),
          "all 6 files exist before the reset (nonzero denominator)");

    removed = vv_reset_slot_state(1, 1);
    printf("vv_reset_slot_state(1, 1) removed %d files\n", removed);

    check(removed >= 3, "reset reported removing at least the 3 VV1 slot-1 files");
    check(!exists(mask1), "slot 1 mask sidecar deleted");
    check(!exists(doubler1), "slot 1 doubler sidecar deleted");
    check(!exists(log1), "slot 1 parentage log deleted");
    check(exists(mask2), "SLOT 2 sidecar SURVIVES (no cross-slot deletion)");
    check(exists(save1), "the game's own .ldw SURVIVES (patcher deletes only its own)");
    check(exists(other_game), "another game's sidecar SURVIVES");

    /* Refusals: nothing outside a real village slot may delete anything. */
    check(vv_reset_slot_state(1, 0) == -1, "slot 0 refused (meta file, not a village)");
    check(vv_reset_slot_state(1, 6) == -1, "slot 6 refused (out of range)");
    check(vv_reset_slot_state(1, -1) == -1, "negative slot refused");
    check(vv_reset_slot_state(0, 1) == -1, "game 0 refused");
    check(vv_reset_slot_state(6, 1) == -1, "game 6 refused");
    check(exists(mask2) && exists(save1) && exists(other_game),
          "survivors still present after all five refusals");

    /* The two guards above are easy to write and easy to get wrong. Mutation
       testing showed an earlier version of this harness could not tell a
       correct implementation from a broken one: removing the empty-path guard,
       and making vv_save_folder fall back to ".", both left it green. So both
       are now asserted directly rather than inferred from the reset's result.

       EMPTY PATH. A reset that cannot build a path must delete nothing. An
       out-of-range slot returns before any path is constructed, so if a later
       guard were removed this still proves nothing was touched. */
    {
        char probe[MAX_PATH];
        int before, after;
        wsprintfA(probe, "%s\\vv1_masks_2.dat", folder);
        before = exists(probe);
        check(vv_reset_slot_state(1, 99) == -1, "slot 99 refused before any path is built");
        after = exists(probe);
        check(before && after, "refused reset deleted nothing (empty-path guard holds)");
    }

    /* CURRENT-DIRECTORY FALLBACK. If vv_save_folder ever resolved to "." the
       reset would delete files beside the executable. A "." or empty result is
       exactly the fallback that must never exist. */
    check(folder[0] != '\0', "resolved folder is not empty");
    check(!(folder[0] == '.' && folder[1] == '\0'),
          "resolved folder is not the current directory");
    check(folder[1] == ':' && folder[2] == '\\',
          "resolved folder is absolute (drive-qualified)");
    {
        /* and it is the SAVE folder, not the install folder -- the defect that
           put exported logs next to the .exe in all five games. */
        char exe[MAX_PATH];
        char *slash;
        GetModuleFileNameA(NULL, exe, MAX_PATH);
        slash = strrchr(exe, '\\');
        if (slash != NULL) {
            *slash = '\0';
        }
        check(lstrcmpiA(folder, exe) != 0,
              "resolved folder is NOT the executable's directory");
    }

    /* DIRECT CALLS. The two checks above prove the guards are not reached in
       normal operation; these prove the guards themselves are correct. Both
       mutations that survived the first mutation run -- deleting on an empty
       path, and resolving the save folder to "." -- fail here.

       A real file is created first so a wrongly-permissive guard has something
       to destroy: asserting "returns 0" against a path that does not exist
       would pass even if the guard were gone. */
    {
        char victim[MAX_PATH];
        wchar_t victim_w[MAX_PATH];

        wsprintfA(victim, "%s\\guard_probe.dat", folder);
        touch(victim);
        check(exists(victim), "guard probe file created (nonzero denominator)");

        vv_reset_refused_paths = 0;
        check(delete_if_present("") == 0, "empty path deletes nothing");
        check(vv_reset_refused_paths == 1,
              "empty path was REFUSED before any filesystem call");
        check(delete_if_present(NULL) == 0, "NULL path deletes nothing");
        check(exists(victim), "probe survived the empty/NULL path calls");

        vv_reset_refused_paths = 0;
        check(delete_if_present_w(L"") == 0, "empty wide path deletes nothing");
        check(vv_reset_refused_paths == 1,
              "empty wide path was REFUSED before any filesystem call");
        check(delete_if_present_w(NULL) == 0, "NULL wide path deletes nothing");
        check(exists(victim), "probe survived the wide empty/NULL calls");

        /* and the guard does not refuse a real path -- a guard that refused
           everything would pass every check above while breaking the reset. */
        check(delete_if_present(victim) == 1, "a real path IS deleted");
        check(!exists(victim), "probe actually removed");

        wsprintfW(victim_w, L"%ls\\guard_probe_w.dat", folder_w_probe);
        {
            HANDLE h = CreateFileW(victim_w, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                                   FILE_ATTRIBUTE_NORMAL, NULL);
            if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
        }
        check(GetFileAttributesW(victim_w) != INVALID_FILE_ATTRIBUTES,
              "wide probe created");
        check(delete_if_present_w(victim_w) == 1, "a real wide path IS deleted");
    }

    /* Clean up what the harness made. */
    DeleteFileA(mask2); DeleteFileA(save1); DeleteFileA(other_game);

    printf("\n%s (%d failure%s)\n", failures ? "FAILED" : "OK",
           failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}
