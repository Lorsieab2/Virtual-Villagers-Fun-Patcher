/* ANOTHER VILLAGE'S FILE IS NEVER REPLACED, AND NO VERDICT IS REACHED
   AGAINST A VILLAGE THE FILE DOES NOT DESCRIBE.

   Since v1.35.66 every Origins companion keys its per-slot files by the
   game's OWN slot field (native/shared/game_save_slot.h).  That field names
   a slot before the village in it is in the villager array: at A New Home's
   title screen it already says the slot about to be loaded while the array
   still holds the founders the startup slot list seeded.  The owner's A New
   Home parents were wiped that way (v1.35.67: an empty table, committed
   against those founders, was written over the file the moment the real
   village loaded); the mask tables run the same kind of per-frame logic.

   The rules every per-village table follows (the parents file's,
   native/vv1_parentage/vv1_parentage.c):

     - a table loaded from a file is moved to its villagers only when the
       villagers on screen share somebody with the file's roster
       (vv_roster_shares); against a roster that shares nobody it waits --
       the village it belongs to may be about to load into that very slot;
     - the file of a village that is not on screen is never replaced: before
       the first write of a table that has something in it, it is moved aside
       to "<name>.another-village-<ticks>-<n>" (never over another file), and a
       table with nothing in it is never written over it at all.

   Header-only and static; every function is pure or touches only the one
   file it is given.  native/shared/foreign_sidecar_harness.c drives it. */
#ifndef VV_FOREIGN_SIDECAR_H
#define VV_FOREIGN_SIDECAR_H

#include <windows.h>

#ifndef VV_FOREIGN_TICKS
#define VV_FOREIGN_TICKS() GetTickCount()
#endif

/* Do the two rosters (n identities each, 0 = nobody) share a villager?
   1 yes, 0 no, -1 when either names nobody (nothing to judge by). */
static int vv_roster_shares(int n, const unsigned int *a, const unsigned int *b) {
    int i, j, any_a = 0, any_b = 0;
    for (i = 0; i < n; ++i) {
        any_a |= a[i] != 0;
        any_b |= b[i] != 0;
    }
    if (!any_a || !any_b) {
        return -1;
    }
    for (i = 0; i < n; ++i) {
        if (a[i] == 0) {
            continue;
        }
        for (j = 0; j < n; ++j) {
            if (b[j] == a[i]) {
                return 1;
            }
        }
    }
    return 0;
}

/* Does a table of n bytes hold anything? */
static int vv_table_any(const unsigned char *t, int n) {
    int i;
    for (i = 0; i < n; ++i) {
        if (t[i] != 0) {
            return 1;
        }
    }
    return 0;
}

static int vv_foreign_append_uint(char *out, int cap, unsigned int v) {
    char digits[11];
    int n = 0, len = lstrlenA(out);
    do {
        digits[n++] = (char)('0' + v % 10u);
        v /= 10u;
    } while (v != 0u);
    if (len + n + 1 > cap) {
        return 0;
    }
    while (n > 0) {
        out[len++] = digits[--n];
    }
    out[len] = '\0';
    return 1;
}

/* Move another village's file out of the way: "<path>.another-village-
   <ticks>-<n>", never replacing anything.  1 when the name is free now (moved,
   or there was no file), 0 when the file is still there. */
static int vv_foreign_set_aside(const char *path) {
    char aside[MAX_PATH];
    unsigned int n;
    int stem;
    if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) {
        DWORD err = GetLastError();
        return err == ERROR_FILE_NOT_FOUND || err == ERROR_PATH_NOT_FOUND;
    }
    if (lstrlenA(path) + (int)sizeof(".another-village-4294967295-999") > MAX_PATH) {
        return 0;
    }
    lstrcpyA(aside, path);
    lstrcatA(aside, ".another-village-");
    if (!vv_foreign_append_uint(aside, MAX_PATH, (unsigned int)VV_FOREIGN_TICKS())) {
        return 0;
    }
    lstrcatA(aside, "-");
    stem = lstrlenA(aside);
    for (n = 0; n < 1000u; ++n) {
        DWORD err;
        aside[stem] = '\0';
        if (!vv_foreign_append_uint(aside, MAX_PATH, n)) {
            return 0;
        }
        if (MoveFileExA(path, aside, MOVEFILE_WRITE_THROUGH)) {
            return 1;
        }
        err = GetLastError();
        if (err != ERROR_ALREADY_EXISTS && err != ERROR_FILE_EXISTS) {
            return 0;
        }
    }
    return 0;
}

/* Before writing a table over the file at `path` while `*foreign` says that
   file is another village's: 1 = go ahead and write (the file is out of the
   way now, and *foreign is cleared), 0 = do not write (the table holds nothing
   -- *wrote_nothing is then 1, it is not a failure -- or the file would not
   move). */
static int vv_foreign_before_write(int *foreign, const char *path, int table_has_anything, int *wrote_nothing) {
    *wrote_nothing = 0;
    if (!*foreign) {
        return 1;
    }
    if (!table_has_anything) {
        *wrote_nothing = 1;
        return 0;
    }
    if (!vv_foreign_set_aside(path)) {
        return 0;
    }
    *foreign = 0;
    return 1;
}

#endif /* VV_FOREIGN_SIDECAR_H */
