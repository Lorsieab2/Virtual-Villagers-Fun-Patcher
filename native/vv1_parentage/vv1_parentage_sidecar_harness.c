/* The VV1 parentage sidecar on disk: a file that is there but cannot be read
   must never be replaced, and one that is not a sidecar is set aside first.

   A New Home keeps no parents on a villager's record, so the sidecar is the
   only copy there is; an empty table written over it is a permanent loss.
   This harness compiles vv1_parentage.c itself into a 32-bit console program
   and drives the real sync, load and save code against synthetic villager
   arrays.  Only the Documents folder is redirected -- to the folder given on
   the command line -- so every file it touches is inside that folder.  The
   open and tick-count calls are wrapped only to count retries and to make
   the set-aside name predictable; both pass straight through.

   Built and run by tests/test_vv1_parentage_sidecar.py. */
#include <windows.h>
#include <shlobj.h>
#include <sddl.h>
#include <stdio.h>
#include <string.h>

static char g_docs[MAX_PATH];
static int g_opens;               /* OPEN_EXISTING opens: the sidecar reads */
static DWORD g_ticks = 12345u;

static HRESULT WINAPI harness_docs(HWND owner, int csidl, HANDLE token, DWORD flags, LPSTR out) {
    (void)owner; (void)csidl; (void)token; (void)flags;
    lstrcpyA(out, g_docs);
    return S_OK;
}

static HANDLE WINAPI harness_open(LPCSTR path, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                  DWORD disposition, DWORD flags, HANDLE templ) {
    if (disposition == OPEN_EXISTING) {
        ++g_opens;
    }
    return CreateFileA(path, access, share, sa, disposition, flags, templ);
}

static DWORD WINAPI harness_ticks(void) {
    return g_ticks;
}

#define SHGetFolderPathA harness_docs
#define CreateFileA harness_open
#define GetTickCount harness_ticks
#include "vv1_parentage.c"
#undef SHGetFolderPathA
#undef CreateFileA
#undef GetTickCount

#define SLOT 1
#define FRAMES 120

static unsigned char village_a[VV1_RECORD_COUNT * VV1_RECORD_STRIDE];
static unsigned char village_b[VV1_RECORD_COUNT * VV1_RECORD_STRIDE];
static unsigned char good[16 + sizeof(g_roster) + sizeof(g_entries)];
static DWORD good_size;
static char path[MAX_PATH];
static int failures;

static void check(int ok, const char *name) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok) {
        ++failures;
    }
}

static void put(unsigned char *records, int index, const char *name, int male, int scalar) {
    unsigned char *rec = records + (unsigned int)index * VV1_RECORD_STRIDE;
    rec[VV1_OCCUPIED_OFFSET] = 1;
    *(int *)(rec + VV1_GENDER_OFFSET) = male ? 1 : 2;
    *(int *)(rec + VV1_VARIANT_OFFSET) = scalar;
    *(int *)(rec + VV1_AGE_OFFSET) = 25 * VV1_UNITS_PER_YEAR;
    lstrcpyA((char *)rec + VV1_NAME_OFFSET, name);
}

/* The companion as a fresh process finds it. */
static void fresh(void) {
    memset(g_entries, 0, sizeof(g_entries));
    memset(g_roster, 0, sizeof(g_roster));
    g_loaded_slot = 0;
    g_strikes = 0;
    g_have_prev = 0;
    g_blocked_slot = 0;
    g_blocked_wait = 0;
    g_may_replace = 0;
    g_opens = 0;
}

static int read_all(const char *p, unsigned char *out, DWORD cap, DWORD *size) {
    HANDLE h = CreateFileA(p, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = ReadFile(h, out, cap, size, NULL);
    CloseHandle(h);
    return ok ? 1 : 0;
}

static int write_all(const char *p, const void *data, DWORD n) {
    HANDLE h = CreateFileA(p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    DWORD wrote = 0;
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = WriteFile(h, data, n, &wrote, NULL) && wrote == n;
    CloseHandle(h);
    return ok ? 1 : 0;
}

static int same_as(const char *p, const void *data, DWORD n) {
    static unsigned char buf[sizeof(good) + 64];
    DWORD size = 0;
    return read_all(p, buf, sizeof(buf), &size) && size == n && memcmp(buf, data, n) == 0;
}

static int set_dacl(const char *p, const char *sddl) {
    PSECURITY_DESCRIPTOR sd = NULL;
    BOOL ok;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorA(sddl, SDDL_REVISION_1, &sd, NULL)) {
        return 0;
    }
    ok = SetFileSecurityA(p, DACL_SECURITY_INFORMATION, sd);
    LocalFree(sd);
    return ok ? 1 : 0;
}

/* Readable by nobody, yet replaceable and deletable by anybody: exactly the
   file the old code overwrote.  (An open handle cannot model this, because
   Windows refuses to replace a file that has an open handle.) */
static int deny_read(const char *p) {
    return set_dacl(p, "D:(D;;0x1;;;WD)(A;;FA;;;WD)");
}

static int allow_all(const char *p) {
    return set_dacl(p, "D:(A;;FA;;;WD)");
}

/* Village A's good sidecar: Alba is the daughter of Bram and Cora. */
static void write_good_sidecar(void) {
    DeleteFileA(path);
    fresh();
    vv1_take_roster(village_a, g_roster);
    lstrcpyA(g_entries[5].father_name, "Bram");
    lstrcpyA(g_entries[5].mother_name, "Cora");
    g_entries[5].father_head = 4;
    g_entries[5].father_body = 5;
    g_entries[5].mother_head = 6;
    g_entries[5].mother_body = 7;
    g_may_replace = 1;
    if (!vv1_parents_save(SLOT, village_a) || !read_all(path, good, sizeof(good), &good_size)) {
        printf("FAIL setup: could not write the good sidecar\n");
        ++failures;
    }
    fresh();
}

/* Frames of play: every frame the village is known a conception is saved,
   which is the most any export could write.  Returns how many frames the
   companion said it knew the village. */
static int play(const unsigned char *records, int frames) {
    int known = 0;
    int f;
    for (f = 0; f < frames; ++f) {
        int slot = vv1_parents_sync_core(SLOT, records);
        if (slot) {
            ++known;
            vv1_parents_save(slot, records);
        }
    }
    return known;
}

/* Frames of play between the game's saves: the per-frame sync only. */
static void tick(const unsigned char *records, int frames) {
    int f;
    for (f = 0; f < frames; ++f) {
        (void)vv1_parents_sync_core(SLOT, records);
    }
}

static int aside_exists(DWORD ticks, int n) {
    char p[MAX_PATH];
    wsprintfA(p, "%s.unreadable-%lu-%d", path, (unsigned long)ticks, n);
    return GetFileAttributesA(p) != INVALID_FILE_ATTRIBUTES;
}

static int aside_same_as(DWORD ticks, int n, const void *data, DWORD size) {
    char p[MAX_PATH];
    wsprintfA(p, "%s.unreadable-%lu-%d", path, (unsigned long)ticks, n);
    return same_as(p, data, size);
}

static void remove_asides(DWORD ticks) {
    char p[MAX_PATH];
    int n;
    for (n = 0; n < 1000; ++n) {
        wsprintfA(p, "%s.unreadable-%lu-%d", path, (unsigned long)ticks, n);
        DeleteFileA(p);
    }
}

static int loaded_alba(void) {
    return lstrcmpA(g_entries[5].father_name, "Bram") == 0
        && lstrcmpA(g_entries[5].mother_name, "Cora") == 0
        && g_entries[5].father_head == 4 && g_entries[5].mother_body == 7;
}

/* ---- the parents follow the villager, not the record index ----------

   A New Home compacts its villager array when a save is loaded: the dead
   are dropped and everyone after them comes back lower.  The owner's own
   village is the model: Ghali [0] and Onawa [3] and Kito [1] and Chika [2]
   are founders with children alternating between the two couples; Kito and
   Chika die, and after the next load every child is two records lower.  The
   old code kept each entry at its index, so Lisha showed Kito and Chika and
   Kaimi showed Ghali and Onawa -- and Silko, a grown arrival with no parents,
   showed whoever had held his record. */

static unsigned char before_load[VV1_RECORD_COUNT * VV1_RECORD_STRIDE];
static unsigned char after_load[VV1_RECORD_COUNT * VV1_RECORD_STRIDE];

typedef struct { const char *name; int male; int scalar; int couple; } kin;   /* couple: 0 none, 1 Kito+Chika, 2 Ghali+Onawa */

static const kin owner_village[] = {
    { "Ghali", 1, 45, 0 }, { "Kito", 1, 19, 0 }, { "Chika", 0, 39, 0 }, { "Onawa", 0, 50, 0 },
    { "Huata", 0, 36, 0 }, { "Nishi", 0, 39, 1 }, { "Penyo", 0, 50, 2 }, { "Chapa", 0, 39, 1 },
    { "Pupa", 0, 50, 2 }, { "Howi", 1, 39, 1 }, { "Usutu", 1, 50, 2 }, { "Yepa", 0, 39, 1 },
    { "Iruwa", 0, 50, 2 }, { "Goro", 1, 39, 1 }, { "Hawa", 0, 50, 2 }, { "Lisha", 0, 50, 2 },
    { "Kaimi", 0, 39, 1 },
};
#define OWNER_VILLAGERS ((int)(sizeof(owner_village) / sizeof(owner_village[0])))

static void set_parents(int index, int couple) {
    vv1_parent_entry *e = &g_entries[index];
    memset(e, 0, sizeof(*e));
    if (couple == 1) {
        lstrcpyA(e->father_name, "Kito"); e->father_head = 2; e->father_body = 20;
        lstrcpyA(e->mother_name, "Chika"); e->mother_head = 21; e->mother_body = 19;
    } else if (couple == 2) {
        lstrcpyA(e->father_name, "Ghali"); e->father_head = 8; e->father_body = 3;
        lstrcpyA(e->mother_name, "Onawa"); e->mother_head = 18; e->mother_body = 4;
    }
}

static int has_parents(int index, int couple) {
    const vv1_parent_entry *e = &g_entries[index];
    if (couple == 1) {
        return lstrcmpA(e->father_name, "Kito") == 0 && lstrcmpA(e->mother_name, "Chika") == 0
            && e->father_head == 2 && e->mother_body == 19;
    }
    if (couple == 2) {
        return lstrcmpA(e->father_name, "Ghali") == 0 && lstrcmpA(e->mother_name, "Onawa") == 0
            && e->father_head == 8 && e->mother_body == 4;
    }
    return e->father_head == 0 && e->father_body == 0 && e->mother_head == 0 && e->mother_body == 0
        && e->father_name[0] == 0 && e->mother_name[0] == 0
        && e->stash_head == 0 && e->stash_name[0] == 0;
}

/* Lay the village out packed, skipping the villagers in `dead`, then add
   the given arrivals.  Returns how many records are occupied. */
static int lay_out(unsigned char *records, const char *dead_a, const char *dead_b) {
    int i, at = 0;
    memset(records, 0, VV1_RECORD_COUNT * VV1_RECORD_STRIDE);
    for (i = 0; i < OWNER_VILLAGERS; ++i) {
        if ((dead_a && lstrcmpA(owner_village[i].name, dead_a) == 0)
            || (dead_b && lstrcmpA(owner_village[i].name, dead_b) == 0)) {
            continue;
        }
        put(records, at++, owner_village[i].name, owner_village[i].male, owner_village[i].scalar);
    }
    return at;
}

static int where(const unsigned char *records, const char *name) {
    int i;
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        const unsigned char *rec = records + (unsigned int)i * VV1_RECORD_STRIDE;
        if (rec[VV1_OCCUPIED_OFFSET] && lstrcmpA((const char *)rec + VV1_NAME_OFFSET, name) == 0) {
            return i;
        }
    }
    return -1;
}

/* The owner's sidecar as the session before the load left it: every child's
   parents at its own record, Chapa [7] pregnant by Usutu. */
static void write_owner_sidecar(void) {
    int i;
    DeleteFileA(path);
    fresh();
    lay_out(before_load, NULL, NULL);
    vv1_take_roster(before_load, g_roster);
    for (i = 0; i < OWNER_VILLAGERS; ++i) {
        set_parents(i, owner_village[i].couple);
    }
    lstrcpyA(g_entries[7].stash_name, "Usutu"); g_entries[7].stash_head = 20; g_entries[7].stash_body = 3;
    g_may_replace = 1;
    if (!vv1_parents_save(SLOT, before_load)) {
        printf("FAIL setup: could not write the owner's sidecar\n");
        ++failures;
    }
    fresh();
}

/* The owner's sidecar with record `at` replaced by another villager of the
   given identity and parents (a second Howi, say). */
static void write_dup_sidecar(int at, const char *name, int male, int scalar, int couple) {
    int i;
    DeleteFileA(path);
    fresh();
    lay_out(before_load, NULL, NULL);
    put(before_load, at, name, male, scalar);
    vv1_take_roster(before_load, g_roster);
    for (i = 0; i < OWNER_VILLAGERS; ++i) {
        set_parents(i, owner_village[i].couple);
    }
    set_parents(at, couple);
    g_may_replace = 1;
    if (!vv1_parents_save(SLOT, before_load)) {
        printf("FAIL setup: could not write the duplicate sidecar\n");
        ++failures;
    }
    fresh();
}

static int every_child_follows(const unsigned char *records) {
    int i;
    for (i = 0; i < OWNER_VILLAGERS; ++i) {
        int at = where(records, owner_village[i].name);
        if (at >= 0 && !has_parents(at, owner_village[i].couple)) {
            printf("  ... %s at [%d] has father '%s' mother '%s'\n", owner_village[i].name, at,
                   g_entries[at].father_name, g_entries[at].mother_name);
            return 0;
        }
    }
    return 1;
}

static void follow_cases(void) {
    int at, i, n;
    static unsigned char file_now[sizeof(good)];
    DWORD size = 0;

    /* 12. The owner's scenario: Kito [1] and Chika [2] die; the load packs
           everyone after them two records lower; Silko arrives grown. */
    write_owner_sidecar();
    n = lay_out(after_load, "Kito", "Chika");
    put(after_load, n, "Silko", 1, 1);
    /* One sync and nothing else -- no birth, no death, no export: the
       followed table must reach the file by itself. */
    check(vv1_parents_sync_core(SLOT, after_load) == SLOT
          && read_all(path, file_now, sizeof(file_now), &size) && size == good_size
          && lstrcmpA((const char *)file_now + 12 + 13 * sizeof(vv1_occupant) + 8, "Lisha") == 0
          && lstrcmpA((const char *)file_now + 12 + sizeof(g_roster) + 13 * sizeof(vv1_parent_entry) + 8, "Ghali") == 0,
          "the load writes the followed table back at once (Lisha and her father at record 13 in the file)");
    play(after_load, 2);
    check(g_loaded_slot == SLOT, "the compacted village is still this village's sidecar");
    check(every_child_follows(after_load), "after a load that compacted the array, every child keeps its own parents");
    at = where(after_load, "Lisha");
    check(at == 13 && has_parents(at, 2), "... Lisha [15 -> 13] is still Ghali and Onawa's");
    at = where(after_load, "Kaimi");
    check(at == 14 && has_parents(at, 1), "... Kaimi [16 -> 14] is still Kito and Chika's");
    at = where(after_load, "Nishi");
    check(at == 3 && has_parents(at, 1), "... Nishi [5 -> 3] is still Kito and Chika's");
    at = where(after_load, "Silko");
    check(at == 15 && has_parents(at, 0), "a grown arrival in a record a child used to hold has no parents");
    at = where(after_load, "Chapa");
    check(at == 5 && lstrcmpA(g_entries[at].stash_name, "Usutu") == 0 && g_entries[at].stash_head == 20,
          "the pregnancy stash follows the mother (Chapa [7 -> 5] still carries Usutu's child)");
    check(lstrcmpA(g_entries[3].stash_name, "") == 0 && lstrcmpA(g_entries[2].stash_name, "") == 0,
          "... and nobody else inherits a stash");
    check(has_parents(16, 0), "the record past the end of the packed array keeps nothing of Kaimi's");
    /* the file written after the follow is in step: reading it again changes nothing */
    check(read_all(path, file_now, sizeof(file_now), &size) && size == good_size,
          "the followed table was written back");
    fresh();
    play(after_load, 2);
    check(every_child_follows(after_load) && has_parents(15, 0),
          "the rewritten sidecar loads in step: the same parents, nothing moves twice");

    /* 13. A death at record 0: nobody is at their old index any more.  The
           old same-index village test called that "another village" and,
           after the strike window, replaced the whole table with an empty
           one. */
    write_owner_sidecar();
    lay_out(after_load, "Ghali", NULL);
    play(after_load, FRAMES);
    check(g_loaded_slot == SLOT && every_child_follows(after_load),
          "a death at record 0 shifts everyone, and the table still follows them all");
    for (i = 0, n = 0; i < VV1_RECORD_COUNT; ++i) {
        if (g_entries[i].mother_name[0]) ++n;
    }
    check(n == 12, "... all twelve children's parents are in it");
    fresh();
    play(after_load, 2);
    check(every_child_follows(after_load), "... and the sidecar written afterwards holds them too");

    /* 14. Two villagers who share name, gender and scalar are ambiguous: after
           a repack neither is guessed at. */
    write_dup_sidecar(13, "Howi", 1, 39, 2);   /* Goro [13] becomes a second Howi */
    lay_out(after_load, "Kito", "Chika");
    put(after_load, 11, "Howi", 1, 39);   /* the second Howi, two lower; Goro is gone */
    play(after_load, 2);
    check(has_parents(7, 0) && has_parents(11, 0),
          "two villagers with the same identity are left unknown after a repack, never guessed");
    check(has_parents(where(after_load, "Lisha"), 2), "... while everyone else still follows");
    /* The same two when nothing moved (only a birth elsewhere): kept in place. */
    write_dup_sidecar(13, "Howi", 1, 39, 2);
    memcpy(after_load, before_load, sizeof(after_load));
    put(after_load, 20, "Newborn", 0, 50);
    play(after_load, 2);
    check(has_parents(9, 1) && has_parents(13, 2),
          "... but when nothing moved, the same two keep the parents at their own records");
    check(has_parents(20, 0), "... and the newcomer starts unknown");
    /* One of the two below the deaths keeps its record while everyone after
       moves: still ambiguous, because a repack happened -- not kept in place. */
    write_dup_sidecar(0, "Howi", 1, 39, 2);    /* Ghali [0] becomes a second Howi */
    lay_out(after_load, "Kito", "Chika");
    put(after_load, 0, "Howi", 1, 39);
    play(after_load, 2);
    check(has_parents(0, 0) && has_parents(7, 0),
          "a duplicate that happens to keep its record during a repack is not guessed at either");
    /* The same name and gender with another family scalar is someone else. */
    write_dup_sidecar(13, "Howi", 1, 50, 2);
    lay_out(after_load, "Kito", "Chika");
    put(after_load, 11, "Howi", 1, 50);
    play(after_load, 2);
    check(has_parents(7, 1) && has_parents(11, 2),
          "two villagers with one name but different family scalars each keep their own parents");

    /* 15. During play a death leaves the record empty: the entry stays,
           under the villager's identity, until someone else holds it. */
    write_owner_sidecar();
    memcpy(after_load, before_load, sizeof(after_load));
    play(after_load, 2);
    after_load[15 * VV1_RECORD_STRIDE + VV1_OCCUPIED_OFFSET] = 0;   /* Lisha dies */
    play(after_load, 2);
    check(has_parents(15, 2) && lstrcmpA(g_roster[15].name, "Lisha") == 0,
          "a villager who dies keeps the entry while the record stays empty");
    check(g_roster[15].departed == 1 && read_all(path, file_now, sizeof(file_now), &size)
          && file_now[12 + 15 * sizeof(vv1_occupant) + 1] == 1,
          "... and the roster, on disk too, marks her record departed (so a reload ranks the living)");
    put(after_load, 15, "Baby", 0, 39);
    play(after_load, 2);
    check(has_parents(15, 0), "a new occupant of that record inherits nothing");

    /* 16. A villager who was away and comes back in another record is
           found again by identity. */
    write_owner_sidecar();
    memcpy(after_load, before_load, sizeof(after_load));
    play(after_load, 2);
    after_load[16 * VV1_RECORD_STRIDE + VV1_OCCUPIED_OFFSET] = 0;   /* Kaimi away */
    play(after_load, 2);
    put(after_load, 40, "Tiny", 1, 50);                              /* a birth meanwhile */
    play(after_load, 2);
    put(after_load, 30, "Kaimi", 0, 39);
    play(after_load, 2);
    check(has_parents(30, 1) && has_parents(16, 0),
          "a villager who comes back in another record takes the entry with her, and leaves none behind");

    /* 18. Codex (#516): a repack made of nothing but duplicates.  Record 0
           died; identical twins at 1 and 2 (one name, gender and scalar,
           different parents) come back at 0 and 1.  No unique villager
           moved, but the roster did: neither twin is guessed at. */
    DeleteFileA(path);
    fresh();
    memset(before_load, 0, sizeof(before_load));
    put(before_load, 0, "Gone", 1, 7);
    put(before_load, 1, "Twin", 1, 5);
    put(before_load, 2, "Twin", 1, 5);
    vv1_take_roster(before_load, g_roster);
    set_parents(1, 1);
    set_parents(2, 2);
    g_may_replace = 1;
    vv1_parents_save(SLOT, before_load);
    fresh();
    memset(after_load, 0, sizeof(after_load));
    put(after_load, 0, "Twin", 1, 5);
    put(after_load, 1, "Twin", 1, 5);
    play(after_load, 2);
    check(g_loaded_slot == SLOT && has_parents(0, 0) && has_parents(1, 0),
          "a repack of nothing but identical twins leaves both unknown (record 1 is not kept for the other twin)");

    /* 18b. The owner's two Sukis (2026-10-06): one name, gender and family
           scalar, different looks.  Three villagers before them died and
           the array was repacked; the follow dropped both Sukis' parents.
           Their looks, recorded in the roster, tell them apart: each keeps
           her own parents.  Identical looks are still never guessed at. */
    DeleteFileA(path);
    fresh();
    memset(before_load, 0, sizeof(before_load));
    put(before_load, 0, "Gone", 1, 7);
    put(before_load, 1, "Gone2", 0, 8);
    put(before_load, 2, "Suki", 0, 50);
    put(before_load, 3, "Suki", 0, 50);
    put(before_load, 4, "Keep", 1, 9);
    put(before_load, 5, "Stay", 0, 11);
    put(before_load, 6, "Ann", 0, 12);
    put(before_load, 7, "Bo", 1, 13);
    *(int *)(before_load + 2 * VV1_RECORD_STRIDE + VV1_HEAD_OFFSET) = 1;
    *(int *)(before_load + 2 * VV1_RECORD_STRIDE + VV1_BODY_OFFSET) = 3;
    *(int *)(before_load + 3 * VV1_RECORD_STRIDE + VV1_HEAD_OFFSET) = 14;
    *(int *)(before_load + 3 * VV1_RECORD_STRIDE + VV1_BODY_OFFSET) = 17;
    vv1_take_roster(before_load, g_roster);
    set_parents(2, 1);
    set_parents(3, 2);
    g_may_replace = 1;
    vv1_parents_save(SLOT, before_load);
    fresh();
    memset(after_load, 0, sizeof(after_load));
    put(after_load, 0, "Suki", 0, 50);
    put(after_load, 1, "Suki", 0, 50);
    put(after_load, 2, "Keep", 1, 9);
    put(after_load, 3, "Stay", 0, 11);
    put(after_load, 4, "Ann", 0, 12);
    put(after_load, 5, "Bo", 1, 13);
    *(int *)(after_load + 0 * VV1_RECORD_STRIDE + VV1_HEAD_OFFSET) = 1;
    *(int *)(after_load + 0 * VV1_RECORD_STRIDE + VV1_BODY_OFFSET) = 3;
    *(int *)(after_load + 1 * VV1_RECORD_STRIDE + VV1_HEAD_OFFSET) = 14;
    *(int *)(after_load + 1 * VV1_RECORD_STRIDE + VV1_BODY_OFFSET) = 17;
    play(after_load, 2);
    check(g_loaded_slot == SLOT && has_parents(0, 1) && has_parents(1, 2),
          "two villagers who share name, gender and scalar but not their looks each keep their own parents after a repack");
    check(read_all(path, file_now, sizeof(file_now), &size)
          && file_now[12 + 0 * sizeof(vv1_occupant) + 2] == 2 && file_now[12 + 0 * sizeof(vv1_occupant) + 3] == 4,
          "... and the roster on disk records each villager's looks (head + 1, body + 1)");

    /* 18c. Codex (#553): a Suki's looks change while nothing else moves (the
           Custom Island Event), then the array repacks: the roster on disk
           took her new looks at once, so each Suki still keeps her own. */
    play(after_load, 2);
    *(int *)(after_load + 0 * VV1_RECORD_STRIDE + VV1_HEAD_OFFSET) = 5;
    tick(after_load, 2);                  /* no game save in between */
    check(read_all(path, file_now, sizeof(file_now), &size)
          && file_now[12 + 0 * sizeof(vv1_occupant) + 2] == 6,
          "a looks change while nothing else moved reaches the roster on disk at once");
    memmove(after_load, after_load + VV1_RECORD_STRIDE, sizeof(after_load) - VV1_RECORD_STRIDE);
    memset(after_load + sizeof(after_load) - VV1_RECORD_STRIDE, 0, VV1_RECORD_STRIDE);
    put(after_load, 5, "Suki", 0, 50);    /* the changed Suki, now after the others */
    *(int *)(after_load + 5 * VV1_RECORD_STRIDE + VV1_HEAD_OFFSET) = 5;
    *(int *)(after_load + 5 * VV1_RECORD_STRIDE + VV1_BODY_OFFSET) = 3;
    tick(after_load, 2);
    check(g_loaded_slot == SLOT && has_parents(5, 1) && has_parents(0, 2),
          "... and after a repack each Suki still keeps her own parents");

    /* 19. Codex (#516): another village in the slot that shares ONE identity
           with the old roster, at another record, is not the old village. */
    write_owner_sidecar();
    memset(after_load, 0, sizeof(after_load));
    put(after_load, 0, "Penyo", 0, 50);       /* the old village had a Penyo (Ghali and Onawa's) at 6 */
    put(after_load, 1, "Moana", 0, 12);
    put(after_load, 2, "Tane", 1, 13);
    put(after_load, 3, "Rua", 1, 14);
    put(after_load, 4, "Kiri", 0, 15);
    play(after_load, FRAMES);
    check(g_loaded_slot == SLOT && has_parents(0, 0),
          "one coincidental identity elsewhere is not the same village: the new Penyo gets no parents");

    /* 20. Ghali, Kito and Chika died before the quit (their records marked
           departed); after the reload Onawa is the only survivor, at record
           0 -- her rank -- with four newborns from the catch-up beside her.
           One unique identity of five on screen is no majority, but a
           villager at her exact packed record is this village. */
    DeleteFileA(path);
    fresh();
    lay_out(before_load, NULL, NULL);
    vv1_take_roster(before_load, g_roster);
    g_roster[0].departed = 1; g_roster[1].departed = 1; g_roster[2].departed = 1;
    for (i = 0; i < 3; ++i) {
        before_load[i * VV1_RECORD_STRIDE + VV1_OCCUPIED_OFFSET] = 0;   /* they died before the quit */
    }
    for (i = 0; i < OWNER_VILLAGERS; ++i) {
        set_parents(i, owner_village[i].couple);
    }
    g_may_replace = 1;
    vv1_parents_save(SLOT, before_load);
    fresh();
    memset(after_load, 0, sizeof(after_load));
    put(after_load, 0, "Onawa", 0, 50);
    put(after_load, 1, "Baby1", 0, 50);
    put(after_load, 2, "Baby2", 1, 50);
    put(after_load, 3, "Baby3", 0, 39);
    put(after_load, 4, "Baby4", 1, 39);
    check(vv1_parents_sync_core(SLOT, after_load) == SLOT,
          "a survivor at her packed record (her rank) is this village even without a majority");

    /* 17. The same village loaded again in the same session (back to the
           menu, Continue): the array is repacked between two frames while the
           per-frame birth inference holds a snapshot of the old layout.  That
           snapshot must not see the moved villagers as new occupants -- the
           inference starts a new occupant's entry over. */
    write_owner_sidecar();
    memcpy(after_load, before_load, sizeof(after_load));
    play(after_load, 2);
    vv1_frame(after_load, 0);                 /* the inference's snapshot of this layout */
    vv1_frame(after_load, 0);
    n = lay_out(after_load, "Kito", "Chika");
    for (i = 0; i < 2; ++i) {
        if (vv1_parents_sync_core(SLOT, after_load)) {
            vv1_frame(after_load, 0);
        }
    }
    check(every_child_follows(after_load),
          "a repack between two frames of play is followed, and the inference does not wipe the moved villagers");

    /* 21. Codex (#516): the player renames Nishi [5] (Kito and Chika's
           daughter) during play.  Same record, gender, family scalar and
           age: she keeps her parents, the rest of the village keeps theirs,
           and no birth is inferred. */
    write_owner_sidecar();
    memcpy(after_load, before_load, sizeof(after_load));
    play(after_load, 2);
    vv1_frame(after_load, 0);
    lstrcpyA((char *)after_load + 5 * VV1_RECORD_STRIDE + VV1_NAME_OFFSET, "Renamed");
    for (i = 0; i < 2; ++i) {
        if (vv1_parents_sync_core(SLOT, after_load)) {
            vv1_frame(after_load, 0);
        }
    }
    check(has_parents(5, 1) && every_child_follows(after_load) && g_birth_count == 0,
          "a villager renamed during play keeps her parents, and no birth is inferred");
    check(lstrcmpA(g_roster[5].name, "Renamed") == 0, "... and the table is bound to her new name");

    /* 22. ...and after a quit and a reload she is still found under it. */
    fresh();
    for (i = 0; i < VV1_NEW_VILLAGE_STRIKES + 2 && !g_loaded_slot; ++i) {
        vv1_parents_sync_core(SLOT, after_load);
    }
    check(g_loaded_slot == SLOT && has_parents(5, 1) && every_child_follows(after_load),
          "the renamed villager's parents survive a reload");

    /* 23. A village of one: her only villager renamed.  The overlap with the
           bound roster would be nobody; the rename keeps the table. */
    DeleteFileA(path);
    fresh();
    memset(before_load, 0, sizeof(before_load));
    put(before_load, 0, "Nishi", 0, 39);
    vv1_take_roster(before_load, g_roster);
    set_parents(0, 1);
    g_may_replace = 1;
    vv1_parents_save(SLOT, before_load);
    fresh();
    memcpy(after_load, before_load, sizeof(after_load));
    play(after_load, 2);
    lstrcpyA((char *)after_load + VV1_NAME_OFFSET, "Solo");
    for (i = 0; i < VV1_NEW_VILLAGE_STRIKES + 2; ++i) {
        if (vv1_parents_sync_core(SLOT, after_load)) {
            vv1_frame(after_load, 0);
        }
    }
    check(has_parents(0, 1) && lstrcmpA(g_roster[0].name, "Solo") == 0,
          "renaming the only villager of a village of one keeps the table");

    /* 24. Not a rename: a newborn in a dead villager's record between two
           frames (same gender and scalar, but a baby): a new occupant. */
    write_owner_sidecar();
    memcpy(after_load, before_load, sizeof(after_load));
    play(after_load, 2);
    vv1_frame(after_load, 0);
    lstrcpyA((char *)after_load + 5 * VV1_RECORD_STRIDE + VV1_NAME_OFFSET, "Baby");
    *(int *)(after_load + 5 * VV1_RECORD_STRIDE + VV1_AGE_OFFSET) = 0;
    vv1_frame(after_load, 0);
    check(g_birth_count == 1 && has_parents(5, 0), "a baby in a dead villager's record is a new occupant, not a rename");

    /* 25. Not a rename: a rename and a birth seen at once change two records;
           the follow decides, as before. */
    write_owner_sidecar();
    memcpy(after_load, before_load, sizeof(after_load));
    play(after_load, 2);
    lstrcpyA((char *)after_load + 5 * VV1_RECORD_STRIDE + VV1_NAME_OFFSET, "Renamed");
    put(after_load, OWNER_VILLAGERS, "Newcomer", 1, 77);
    check(vv1_roster_renamed(g_roster) == -1, "(the bound roster against itself is no rename)");
    {
        static vv1_occupant now2[VV1_RECORD_COUNT];
        vv1_take_roster(after_load, now2);
        check(vv1_roster_renamed(now2) == -1, "a rename seen together with a birth is not taken for a rename");
    }

    /* 26. A Start Over into the same slot whose founders happen to have the
           old village's genders and family scalars, record by record: every
           record changed, so none of it is a rename. */
    {
        static vv1_occupant now3[VV1_RECORD_COUNT];
        static char renamed[OWNER_VILLAGERS][16];
        memcpy(after_load, before_load, sizeof(after_load));
        for (i = 0; i < OWNER_VILLAGERS; ++i) {
            wsprintfA(renamed[i], "New%d", i);
            lstrcpyA((char *)after_load + i * VV1_RECORD_STRIDE + VV1_NAME_OFFSET, renamed[i]);
        }
        vv1_take_roster(after_load, now3);
        check(vv1_roster_renamed(now3) == -1,
              "a new village with the old genders and family scalars is not a rename");

        /* 27. One record's occupant changed to a grown villager of the same
               gender but another family scalar: an arrival, not a rename. */
        memcpy(after_load, before_load, sizeof(after_load));
        put(after_load, 5, "Stranger", 0, 77);
        vv1_take_roster(after_load, now3);
        check(vv1_roster_renamed(now3) == -1, "another family's villager in a record is not a rename");
    }

    DeleteFileA(path);
}

/* A New Home's villager pointer (0x0048B614) and save slot (0x004911F4),
   which Vv1ParentageSetParents reads (case 11), live on this page.  By the
   time main runs the CRT heap has usually reserved it, so the harness runs
   itself again suspended, maps the page in that copy before its heap
   exists, and lets it run every case.  The test links this program away
   from 0x00400000 so its own image never holds the page. */
#define GAME_PAGE ((void *)0x00480000u)
#define GAME_PAGE_SIZE 0x20000u

static int run_with_the_game_page(const char *docs) {
    char self[MAX_PATH];
    char line[3 * MAX_PATH];
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    DWORD code = 1;
    if (!GetModuleFileNameA(NULL, self, sizeof(self))) {
        printf("FAIL setup: no harness path\n");
        return 1;
    }
    wsprintfA(line, "\"%s\" \"%s\" mapped", self, docs);
    memset(&si, 0, sizeof(si));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    fflush(stdout);
    if (!CreateProcessA(self, line, NULL, NULL, TRUE, CREATE_SUSPENDED, NULL, NULL, &si, &pi)) {
        printf("FAIL setup: the harness could not run itself (error %lu)\n", GetLastError());
        return 1;
    }
    if (VirtualAllocEx(pi.hProcess, GAME_PAGE, GAME_PAGE_SIZE, MEM_RESERVE | MEM_COMMIT,
                       PAGE_READWRITE) != GAME_PAGE) {
        printf("FAIL setup: the game's globals are mapped (error %lu)\n", GetLastError());
        TerminateProcess(pi.hProcess, 1);
    } else {
        ResumeThread(pi.hThread);
    }
    WaitForSingleObject(pi.hProcess, INFINITE);
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return (int)code;
}

int main(int argc, char **argv) {
    int known;
    int opens;
    int f;
    HANDLE lock;
    void *game;
    static const char junk[] = "not a parentage sidecar";

    if (argc < 2) {
        printf("usage: harness <scratch folder>\n");
        return 2;
    }
    if (argc < 3 || lstrcmpA(argv[2], "mapped") != 0) {
        return run_with_the_game_page(argv[1]);
    }
    {
        MEMORY_BASIC_INFORMATION page;
        game = VirtualQuery(GAME_PAGE, &page, sizeof(page)) && page.State == MEM_COMMIT
               && page.AllocationBase == GAME_PAGE ? GAME_PAGE : NULL;
    }
    lstrcpynA(g_docs, argv[1], MAX_PATH);
    put(village_a, 3, "Bram", 1, 11);
    put(village_a, 4, "Cora", 0, 12);
    put(village_a, 5, "Alba", 0, 13);
    put(village_b, 3, "Dax", 1, 21);
    put(village_b, 4, "Eda", 0, 22);
    if (!vv1_parents_path(path, sizeof(path), SLOT)) {
        printf("FAIL setup: no sidecar path\n");
        return 1;
    }

    /* 1. A sidecar nobody may read -- the lock, denial or scanner case. */
    write_good_sidecar();
    check(deny_read(path), "setup: the sidecar is made unreadable");
    known = play(village_a, FRAMES);
    check(known == 0, "an unreadable sidecar leaves the village unknown, never committed empty");
    opens = g_opens;
    check(opens >= 2 && opens <= FRAMES / VV1_NEW_VILLAGE_STRIKES + 1,
          "an unreadable sidecar is retried each strike window, not every frame");
    check(!aside_exists(g_ticks, 0), "an unreadable sidecar is not set aside");
    check(allow_all(path), "setup: the sidecar is readable again");
    check(same_as(path, good, good_size), "... and the unreadable sidecar is left byte-for-byte unchanged");
    known = play(village_a, VV1_NEW_VILLAGE_STRIKES + 2);
    check(known > 0 && loaded_alba(), "once readable, the parents are loaded from the file");

    /* 2. The same while the village already on hand turns into strangers
          (the same-slot path) and the file is unreadable. */
    write_good_sidecar();
    play(village_a, 2);
    check(loaded_alba(), "setup: village A is loaded");
    check(deny_read(path), "setup: the sidecar is made unreadable");
    known = play(village_b, FRAMES);
    check(known == 0, "strangers with an unreadable sidecar leave the village unknown");
    check(loaded_alba(), "... and the table on hand is not emptied");
    check(allow_all(path), "setup: the sidecar is readable again");
    check(same_as(path, good, good_size), "... and that sidecar is left byte-for-byte unchanged");

    /* 3. A file held open with no sharing, then released. */
    write_good_sidecar();
    lock = CreateFileA(path, GENERIC_READ, 0, NULL, OPEN_EXISTING, 0, NULL);
    check(lock != INVALID_HANDLE_VALUE, "setup: the sidecar is held open without sharing");
    known = play(village_a, FRAMES);
    CloseHandle(lock);
    check(known == 0, "a sidecar held open leaves the village unknown");
    known = play(village_a, VV1_NEW_VILLAGE_STRIKES + 2);
    check(known > 0 && loaded_alba(), "once released, the parents are loaded from the file");
    check(g_entries[5].father_head == 4, "... and the saves after it keep them");

    /* 3b. A file that opens but whose bytes are locked: the read fails, and
           that is a lock to wait out, not a file to set aside. */
    write_good_sidecar();
    lock = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE, NULL, OPEN_EXISTING, 0, NULL);
    check(lock != INVALID_HANDLE_VALUE && LockFile(lock, 0, 0, 0xFFFFFFFFu, 0),
          "setup: the sidecar's bytes are locked");
    known = play(village_a, FRAMES);
    UnlockFile(lock, 0, 0, 0xFFFFFFFFu, 0);
    CloseHandle(lock);
    check(known == 0 && !aside_exists(g_ticks, 0), "a sidecar whose read fails is waited for, not set aside");
    check(same_as(path, good, good_size), "... and it is left byte-for-byte unchanged");
    known = play(village_a, VV1_NEW_VILLAGE_STRIKES + 2);
    check(known > 0 && loaded_alba(), "once unlocked, the parents are loaded from the file");

    /* 4. A file that is not a sidecar is set aside under an unused name. */
    DeleteFileA(path);
    remove_asides(g_ticks);
    fresh();
    check(write_all(path, junk, sizeof(junk)), "setup: a short, foreign file sits at the sidecar's name");
    {
        char taken[MAX_PATH];
        wsprintfA(taken, "%s.unreadable-%lu-0", path, (unsigned long)g_ticks);
        check(write_all(taken, "earlier", 7), "setup: the first set-aside name is already taken");
    }
    known = play(village_a, FRAMES);
    check(aside_same_as(g_ticks, 1, junk, sizeof(junk)), "an invalid sidecar is set aside byte-for-byte");
    check(aside_same_as(g_ticks, 0, "earlier", 7), "... never over a file already set aside");
    check(known > 0, "... and the village then starts a table of its own");
    {
        DWORD size = 0;
        unsigned char *buf = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, sizeof(good));
        int ok = buf && read_all(path, buf, sizeof(good), &size) && size == sizeof(good) - 4
                 && *(unsigned int *)buf == VV1_PARENTS_MAGIC;
        check(ok, "... written as a sound sidecar");
        if (buf) HeapFree(GetProcessHeap(), 0, buf);
    }

    /* 5. A full-length file with a foreign magic (a 'VP01' file). */
    DeleteFileA(path);
    remove_asides(g_ticks);
    write_good_sidecar();
    good[3] = '1';                                   /* 'VP02' -> 'VP01' */
    check(write_all(path, good, good_size), "setup: a full-length 'VP01' file");
    play(village_a, FRAMES);
    check(aside_same_as(g_ticks, 0, good, good_size), "a sidecar with a foreign magic is set aside, not overwritten");
    good[3] = '2';

    /* 6. An invalid file that cannot be set aside is left alone. */
    DeleteFileA(path);
    remove_asides(g_ticks);
    fresh();
    check(write_all(path, junk, sizeof(junk)), "setup: a foreign file at the sidecar's name");
    for (f = 0; f < 1000; ++f) {
        char taken[MAX_PATH];
        wsprintfA(taken, "%s.unreadable-%lu-%d", path, (unsigned long)g_ticks, f);
        write_all(taken, "x", 1);
    }
    known = play(village_a, FRAMES);
    check(known == 0, "an invalid sidecar that cannot be set aside leaves the village unknown");
    check(same_as(path, junk, sizeof(junk)), "... and nothing is written over it");
    remove_asides(g_ticks);

    /* 7. No file at all: the village starts empty and a file is written
          (unchanged behaviour). */
    DeleteFileA(path);
    fresh();
    known = play(village_a, FRAMES);
    check(known > 0 && GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES,
          "with no sidecar the village starts empty and one is written");

    /* 8. A file that appears after an empty start is read, not replaced. */
    write_good_sidecar();
    {
        static unsigned char keep[sizeof(good)];
        DWORD keep_size = good_size;
        memcpy(keep, good, good_size);
        DeleteFileA(path);
        fresh();
        for (f = 0; f < VV1_NEW_VILLAGE_STRIKES + 1 && !vv1_parents_sync_core(SLOT, village_a); ++f) {
        }
        check(g_loaded_slot == SLOT, "setup: committed with no sidecar on disk");
        check(write_all(path, keep, keep_size), "setup: the sidecar reappears (a sync restores it)");
        vv1_parents_save(SLOT, village_a);
        check(same_as(path, keep, keep_size), "a sidecar that appears after an empty start is not replaced");
        known = play(village_a, 3);
        check(known > 0 && loaded_alba(), "... and it is read on the next frame");
    }

    /* 9. Another village's sound file is still superseded after the strike
          window: Start Over keeps the slot (unchanged behaviour). */
    write_good_sidecar();
    known = play(village_b, FRAMES);
    {
        static unsigned char now[sizeof(good)];
        DWORD size = 0;
        int ok = read_all(path, now, sizeof(now), &size) && size == good_size
                 && memcmp(now + 12, good + 12, sizeof(g_roster)) != 0;
        check(known > 0 && ok, "another village's sidecar is superseded after the strike window");
    }

    /* 10. This village's own file loads at once. */
    write_good_sidecar();
    known = play(village_a, 1);
    check(known == 1 && loaded_alba(), "this village's own sidecar loads at once");

    /* 11. A parent change (the Custom Island Event's) whose save fails is
           rolled back: it must not show, nor reach a later save.  The
           export reads the game's own villager pointer and save slot, so
           the page holding them is mapped here and pointed at village A;
           a folder where the save's temporary file goes makes the save
           fail. */
    write_good_sidecar();
    play(village_a, 2);
    check(loaded_alba(), "setup: village A is loaded for the parent change");
    {
        char tmp[MAX_PATH];
        check(game != NULL, "setup: the game's globals are mapped");
        if (game != NULL) {
            *(unsigned char **)0x0048B614u = village_a;
            *(unsigned int *)0x004911F4u = SLOT;
            wsprintfA(tmp, "%s.tmp", path);
            check(CreateDirectoryA(tmp, NULL), "setup: the save's temporary file cannot be created");
            check(Vv1ParentageSetParents(5, "Zed", 1, 2, "Yara", 3, 4) == 0,
                  "a parent change whose save fails is refused");
            check(loaded_alba(), "... and the table keeps the parents it had");
            RemoveDirectoryA(tmp);
            vv1_parents_save(SLOT, village_a);
            fresh();
            play(village_a, 2);
            check(loaded_alba(), "... and the next save does not persist the refused change");
            check(Vv1ParentageSetParents(5, "Zed", 1, 2, "Yara", 3, 4) == 1
                  && lstrcmpA(g_entries[5].father_name, "Zed") == 0,
                  "a parent change whose save succeeds is kept");
            *(unsigned char **)0x0048B614u = NULL;
        }
    }

    follow_cases();

    DeleteFileA(path);
    printf("%d failure(s)\n", failures);
    return failures ? 1 : 0;
}
