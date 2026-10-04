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
#include "harness_ldw_tree.h"

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

static void write_text(const char *path, const char *text) {
    HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD written = 0;
    if (h != INVALID_HANDLE_VALUE) {
        WriteFile(h, text, (DWORD)lstrlenA(text), &written, NULL);
        CloseHandle(h);
    }
}

static int exists(const char *path) {
    return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

int main(void) {
    harness_ldw_tree_begin();   /* first: leaves Documents\LDW as it found it */
    char folder[MAX_PATH];
    wchar_t folder_w_probe[MAX_PATH];
    char mask1[MAX_PATH], mask2[MAX_PATH], doubler1[MAX_PATH];
    char save1[MAX_PATH], other_game[MAX_PATH];
    char log1[MAX_PATH];
    int removed;
    char stats1[MAX_PATH], stats2[MAX_PATH];
    char pop1[MAX_PATH], pop2[MAX_PATH];
    char log_other[MAX_PATH];
    char popdir[MAX_PATH], pardir[MAX_PATH];   /* the moved log folders */
    static const char VILLAGE[]  = "Village: Kalahuna (Save 1)\n";
    static const char VILLAGE2[] = "Village: Elsewhere (Save 2)\n";

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
    /* The population and parentage logs moved into the owner's log layout
       (#418); the harness follows so it tests the reset against where the
       exporters actually write. */
    if (!vv_save_subfolder(popdir, "Virtual Villagers Fun Patcher Logs\\Tribe Population", 64)
        || !vv_save_subfolder(pardir, "Virtual Villagers Fun Patcher Logs\\Births and Conceptions", 64)) {
        printf("could not resolve the log subfolders\n");
        return 2;
    }
    /* The subfolders must be INSIDE the save folder -- "<save>\\Virtual Villagers Fun Patcher Logs\\...",
       not "<save>Virtual Villagers Fun Patcher Logs..." glued onto its name. A live run found the
       helper doing exactly that while this harness passed, because the
       fixtures and the reset used the same wrong path. Checked against
       the resolved save folder, not against a literal. */
    {
        int flen = lstrlenA(folder);
        check(strncmp(popdir, folder, flen) == 0 && popdir[flen] == '\\'
              && strcmp(popdir + flen, "\\Virtual Villagers Fun Patcher Logs\\Tribe Population") == 0,
              "population subfolder is <save folder>\\Virtual Villagers Fun Patcher Logs\\Tribe Population");
        check(strncmp(pardir, folder, flen) == 0 && pardir[flen] == '\\'
              && strcmp(pardir + flen, "\\Virtual Villagers Fun Patcher Logs\\Births and Conceptions") == 0,
              "parental subfolder is <save folder>\\Virtual Villagers Fun Patcher Logs\\Births and Conceptions");
        check(GetFileAttributesA(popdir) != INVALID_FILE_ATTRIBUTES,
              "population subfolder was actually created");
    }
    wsprintfA(mask1, "%s\\vv1_masks_1.dat", folder);
    wsprintfA(mask2, "%s\\vv1_masks_2.dat", folder);
    wsprintfA(doubler1, "%s\\vv1_doublers_1.dat", folder);
    wsprintfA(save1, "%s\\Virtual Villagers1.ldw", folder);
    wsprintfA(other_game, "%s\\vv2_masks_1.dat", folder);
    wsprintfA(log1, "%s\\Virtual Villagers 1 Births and Conceptions Log 1.txt", pardir);

    wsprintfA(stats1, "%s\\Village Statistics - Save 1.txt", folder);
    wsprintfA(stats2, "%s\\Village Statistics - Save 2.txt", folder);
    wsprintfA(pop1, "%s\\Village Population 1.txt", popdir);
    wsprintfA(pop2, "%s\\Village Population 2.txt", popdir);
    wsprintfA(log_other, "%s\\Virtual Villagers 1 Births and Conceptions Log 2.txt", pardir);

    touch(mask1); touch(mask2); touch(doubler1);
    touch(save1); touch(other_game);
    touch(stats1); touch(stats2);
    /* The roster is numbered by PAGE in a folder every slot shares, and each
       page opens with the title and then the village header, exactly as
       population_export.c writes it. Pages 1 and 2 are the erased village's;
       see below for the pages that are not. */
    write_text(pop1, "Virtual Villagers: A New Home Village Population\n"
                     "Village: Kalahuna (Save 1)\n\n1. Someone\n");
    write_text(pop2, "Virtual Villagers: A New Home Village Population\n"
                     "Village: Kalahuna (Save 1)\n\n257. Someone else\n");
    /* The two parentage logs carry DIFFERENT village headers: log1 belongs to
       the village being erased, log_other to a village that is not. */
    write_text(log1, VILLAGE);
    write_text(log_other, VILLAGE2);

    printf("created 6 files; resetting VV1 slot 1\n");
    check(exists(mask1) && exists(mask2) && exists(doubler1)
          && exists(save1) && exists(other_game) && exists(log1),
          "all 6 files exist before the reset (nonzero denominator)");

    removed = vv_reset_slot_state(1, 1, VILLAGE);
    printf("vv_reset_slot_state(1, 1) removed %d files\n", removed);

    check(removed >= 3, "reset reported removing at least the 3 VV1 slot-1 files");
    check(!exists(mask1), "slot 1 mask sidecar deleted");
    check(!exists(doubler1), "slot 1 doubler sidecar deleted");
    check(!exists(log1), "slot 1 parentage log deleted");
    check(exists(mask2), "SLOT 2 sidecar SURVIVES (no cross-slot deletion)");
    check(exists(save1), "the game's own .ldw SURVIVES (patcher deletes only its own)");
    check(exists(other_game), "another game's sidecar SURVIVES");

    /* THE P1 CODEX FOUND ON #380. Statistics and population logs are numbered
       by SLOT, so an unscoped walk deleted villages that were never reset. */
    check(!exists(stats1), "slot 1 statistics log deleted");
    check(exists(stats2), "SLOT 2 STATISTICS SURVIVES (was destroyed before the fix)");
    /* Population pages belong to a VILLAGE, not a slot: all of the erased
       village's pages go, whatever their numbers. */
    check(!exists(pop1), "population page 1 of the erased village deleted");
    check(!exists(pop2), "POPULATION PAGE 2 OF THE ERASED VILLAGE DELETED (slot 1 left it before the fix)");

    /* THE ROSTER IS MATCHED BY HEADER, NEVER BY SLOT.

       Before this fix the reset deleted "Village Population <slot>.txt":
       a slot-1 Start Over deleted page 1 of whichever village had saved
       last, and slots 2..5 deleted a page of someone else's roster or
       nothing at all. */
    {
        char legacy_dir[MAX_PATH], legacy1[MAX_PATH];
        static const char OTHER_PAGE[] =
            "Virtual Villagers: A New Home Village Population\n"
            "Village: Elsewhere (Save 2)\n\n1. Someone\n";
        static const char ERASED_PAGE[] =
            "Virtual Villagers: A New Home Village Population\n"
            "Village: Kalahuna (Save 1)\n\n1. Someone\n";

        /* Another village owns page 1: a slot-1 reset of Kalahuna must
           leave it, which the slot-numbered sweep did not. */
        write_text(pop1, OTHER_PAGE);
        write_text(pop2, ERASED_PAGE);
        check(exists(pop1) && exists(pop2), "roster pages recreated (nonzero denominator)");
        vv_reset_slot_state(1, 1, VILLAGE);
        check(exists(pop1), "ANOTHER VILLAGE'S POPULATION PAGE 1 SURVIVES A SLOT-1 RESET");
        check(!exists(pop2), "the erased village's page 2 is deleted though slot is 1");

        /* The slot number is irrelevant: erasing slot 2's village deletes
           the page it owns even though that page is number 1. */
        vv_reset_slot_state(1, 2, VILLAGE2);
        check(!exists(pop1), "SLOT-2 RESET DELETES ITS VILLAGE'S PAGE 1 (slot number irrelevant)");
        /* That reset rightly took slot 2's own sidecar, statistics and
           Elsewhere's parentage log; put them back for the survivor checks
           further down. */
        touch(mask2);
        touch(stats2);
        write_text(log_other, VILLAGE2);

        /* Without a village string nothing is guessed at. */
        write_text(pop1, ERASED_PAGE);
        vv_reset_slot_state(1, 1, NULL);
        check(exists(pop1), "NULL village leaves population pages alone");
        vv_reset_slot_state(1, 1, "");
        check(exists(pop1), "empty village leaves population pages alone");

        /* A header on the FIRST line is not the roster's shape. */
        write_text(pop2, "Village: Kalahuna (Save 1)\nnot a roster\n");
        vv_reset_slot_state(1, 1, VILLAGE);
        check(!exists(pop1), "erased village's page deleted on a real reset");
        check(exists(pop2), "a file whose FIRST line is the header is not a roster page");
        DeleteFileA(pop2);

        /* The retired folder is swept the same way, and only by header. */
        wsprintfA(legacy_dir, "%s\\VVFP Logs", folder);
        CreateDirectoryA(legacy_dir, NULL);
        wsprintfA(legacy_dir, "%s\\VVFP Logs\\Tribe Population", folder);
        CreateDirectoryA(legacy_dir, NULL);
        wsprintfA(legacy1, "%s\\Village Population 3.txt", legacy_dir);
        write_text(legacy1, ERASED_PAGE);
        write_text(pop1, OTHER_PAGE);
        check(exists(legacy1), "legacy roster page created (nonzero denominator)");
        vv_reset_slot_state(1, 1, VILLAGE);
        check(!exists(legacy1), "erased village's page in the RETIRED folder deleted");
        check(exists(pop1), "other village's page survives the retired-folder pass");
        DeleteFileA(pop1);
        RemoveDirectoryA(legacy_dir);
        wsprintfA(legacy_dir, "%s\\VVFP Logs", folder);
        RemoveDirectoryA(legacy_dir);
    }

    /* The Story / Cheat Upgrades custom titles (native/shared/custom_titles.h)
       are per slot in every game, and the owner's rule is that the .dat
       follows the Start Over reset: slot 1's goes, slot 2's stays. */
    {
        char titles_dir[MAX_PATH], t1[MAX_PATH], t2[MAX_PATH];
        int game;
        if (!vv_save_subfolder(titles_dir, "Virtual Villagers Fun Patcher Data\\Custom Titles", 64)) {
            printf("could not resolve the custom titles folder\n");
            return 2;
        }
        wsprintfA(t1, "%s\\Custom Titles - Save 1.dat", titles_dir);
        wsprintfA(t2, "%s\\Custom Titles - Save 2.dat", titles_dir);
        for (game = 1; game <= 5; ++game) {
            char what[96];
            touch(t1);
            touch(t2);
            check(exists(t1) && exists(t2), "custom titles files exist before the reset (nonzero denominator)");
            vv_reset_slot_state(game, 1, VILLAGE);
            wsprintfA(what, "CUSTOM TITLES OF SLOT 1 DELETED BY START OVER (game %d)", game);
            check(!exists(t1), what);
            wsprintfA(what, "custom titles of slot 2 survive a slot-1 reset (game %d)", game);
            check(exists(t2), what);
            /* other_game is "vv2_masks_1.dat": the "another game's sidecar"
               fixture for the VV1 resets, but VV2's OWN slot-1 sidecar, so
               this loop's VV2 slot-1 Start Over rightly deletes it. Assert
               that, then put it back so the survivor checks further down
               still have it to test (they failed on every run from #495
               until this restore: the fixture was gone, not the reset wrong). */
            if (game == 2) {
                check(!exists(other_game), "VV2 slot-1 reset deletes VV2's own slot-1 sidecar");
                touch(other_game);
            }
        }
        DeleteFileA(t2);
    }

    /* The statistics companion's per-slot data: the counters, the stew
       discoveries and the elders, each a .dat addressed by slot, plus the
       current "v2" statistics log. Start Over must clear slot 1's and leave
       slot 2's. The reset is run as The Secret City, one of the three games
       that make stews, and then as A New Home, which does not. */
    {
        char dat_dir[MAX_PATH], stew_dir[MAX_PATH], elder_dir[MAX_PATH], log_dir[MAX_PATH];
        char s1[MAX_PATH], s2[MAX_PATH], st1[MAX_PATH], st2[MAX_PATH];
        char e1[MAX_PATH], e2[MAX_PATH], tmp1[MAX_PATH], aside1[MAX_PATH];
        char v2log1[MAX_PATH], v2log2[MAX_PATH];
        if (!vv_save_subfolder(dat_dir, "Virtual Villagers Fun Patcher Data\\Village Statistics", 64)
            || !vv_save_subfolder(stew_dir, "Virtual Villagers Fun Patcher Data\\Stew Discoveries", 64)
            || !vv_save_subfolder(elder_dir, "Virtual Villagers Fun Patcher Data\\Village Elders", 64)
            || !vv_save_subfolder(log_dir, "Virtual Villagers Fun Patcher Logs\\Village Statistics", 64)) {
            printf("could not resolve the data subfolders\n");
            return 2;
        }
        wsprintfA(s1, "%s\\Village Statistics - Save 1.dat", dat_dir);
        wsprintfA(s2, "%s\\Village Statistics - Save 2.dat", dat_dir);
        wsprintfA(tmp1, "%s\\Village Statistics - Save 1.dat.tmp", dat_dir);
        wsprintfA(st1, "%s\\Stew Discoveries - Save 1.dat", stew_dir);
        wsprintfA(st2, "%s\\Stew Discoveries - Save 2.dat", stew_dir);
        wsprintfA(aside1, "%s\\Stew Discoveries - Save 1.dat.unreadable", stew_dir);
        wsprintfA(e1, "%s\\Village Elders - Save 1.dat", elder_dir);
        wsprintfA(e2, "%s\\Village Elders - Save 2.dat", elder_dir);
        wsprintfA(v2log1, "%s\\Village Statistics v2 - Save 1.txt", log_dir);
        wsprintfA(v2log2, "%s\\Village Statistics v2 - Save 2.txt", log_dir);
        touch(s1); touch(s2); touch(tmp1); touch(st1); touch(st2); touch(aside1);
        touch(e1); touch(e2); touch(v2log1); touch(v2log2);
        check(exists(s1) && exists(st1) && exists(e1) && exists(tmp1) && exists(v2log1),
              "statistics data files exist before the reset (nonzero denominator)");
        vv_reset_slot_state(3, 1, VILLAGE);
        check(!exists(s1), "slot 1 Village Statistics .dat deleted");
        check(!exists(tmp1), "slot 1 Village Statistics .dat.tmp deleted");
        check(!exists(st1), "slot 1 Stew Discoveries .dat deleted");
        check(!exists(e1), "slot 1 Village Elders .dat deleted");
        check(!exists(v2log1), "slot 1 Village Statistics v2 log deleted");
        check(exists(s2) && exists(st2) && exists(e2) && exists(v2log2),
              "SLOT 2 statistics data SURVIVES");
        check(exists(aside1), "a file set aside as unreadable is left alone");
        touch(st1);
        vv_reset_slot_state(1, 1, VILLAGE);
        check(exists(st1), "A New Home, which makes no stews, leaves a stew file alone");
        DeleteFileA(s2); DeleteFileA(st1); DeleteFileA(st2); DeleteFileA(aside1);
        DeleteFileA(e2); DeleteFileA(v2log2);
    }

    /* Parentage logs roll over by count, so they are matched by header. */
    check(!exists(log1), "parentage log of the erased village deleted");
    check(exists(log_other), "ANOTHER VILLAGE'S PARENTAGE LOG SURVIVES (header mismatch)");

    /* Without a village string, parentage cannot be identified and must be
       left alone rather than deleted on a guess. */
    {
        char probe[MAX_PATH];
        wsprintfA(probe, "%s\\Virtual Villagers 1 Births and Conceptions Log 1.txt", pardir);
        write_text(probe, VILLAGE);
        check(exists(probe), "parentage probe recreated (nonzero denominator)");
        vv_reset_slot_state(1, 1, NULL);
        check(exists(probe), "NULL village leaves parentage logs alone");
        vv_reset_slot_state(1, 1, "");
        check(exists(probe), "empty village leaves parentage logs alone");
        DeleteFileA(probe);
    }

    /* A RESET MUST SEE PAST THE HOLES AN EARLIER RESET MADE.

       This sweep deletes the erased village's numbered logs, and the
       exporter then hands a freed number to the next village, so different
       villages legitimately end up owning non-consecutive numbers. A scan
       that stopped at the first absent number walked into the hole the
       previous reset left and stopped there, and the later village's own
       Start Over never reached its file. Found in review.

       Reproduce it exactly: leave number 1 absent and put the village being
       erased at number 2. */
    {
        char gap1[MAX_PATH];
        char gap2[MAX_PATH];
        wsprintfA(gap1, "%s\\Virtual Villagers 1 Births and Conceptions Log 1.txt", pardir);
        wsprintfA(gap2, "%s\\Virtual Villagers 1 Births and Conceptions Log 2.txt", pardir);
        DeleteFileA(gap1);                 /* the hole a previous reset made */
        write_text(gap2, VILLAGE);         /* the erased village, past the hole */
        check(!exists(gap1) && exists(gap2),
              "gap case set up: number 1 absent, erased village at number 2");
        vv_reset_slot_state(1, 1, VILLAGE);
        check(!exists(gap2),
              "LOG PAST A HOLE IS DELETED (survived its own reset before the fix)");
        DeleteFileA(gap2);
    }

    /* Refusals: nothing outside a real village slot may delete anything. */
    check(vv_reset_slot_state(1, 0, VILLAGE) == -1, "slot 0 refused (meta file, not a village)");
    check(vv_reset_slot_state(1, 6, VILLAGE) == -1, "slot 6 refused (out of range)");
    check(vv_reset_slot_state(1, -1, VILLAGE) == -1, "negative slot refused");
    check(vv_reset_slot_state(0, 1, VILLAGE) == -1, "game 0 refused");
    check(vv_reset_slot_state(6, 1, VILLAGE) == -1, "game 6 refused");
    /* One check per survivor, so a failure names the file that went. */
    check(exists(mask2), "survivor: VV1 slot-2 sidecar present after all five refusals");
    check(exists(save1), "survivor: the game's own .ldw present after all five refusals");
    check(exists(other_game), "survivor: VV2 slot-1 sidecar present after all five refusals");

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
        check(vv_reset_slot_state(1, 99, VILLAGE) == -1, "slot 99 refused before any path is built");
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
    DeleteFileA(stats2); DeleteFileA(pop2); DeleteFileA(log_other);

    printf("\n%s (%d failure%s)\n", failures ? "FAILED" : "OK",
           failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}
