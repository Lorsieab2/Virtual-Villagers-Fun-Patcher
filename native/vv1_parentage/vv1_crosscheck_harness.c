/* The first-load cross-check (vv1_crosscheck.inc), run against the real C.

   Compiles vv1_parentage.c itself into a 32-bit console program with the
   Documents folder redirected to the folder given on the command line, then
   drives the real code -- sync, load, follow, then the scan and (when the
   "player" answers Repair) the repair the Origins companion's prompt calls --
   against synthetic villager arrays, a real sidecar and a real Births and
   Conceptions log on disk.  The prompt itself, its timing and its two answers
   are native/shared/crosscheck_bridge.h's, tested by crosscheck_bridge_harness.c.

   Built and run by tests/test_vv1_crosscheck.py. */
#include <windows.h>
#include <shlobj.h>
#include <sddl.h>
#include <stdio.h>
#include <string.h>

static char g_docs[MAX_PATH];
static int g_asked;               /* times the scan found something to ask about */

static HRESULT WINAPI harness_docs(HWND owner, int csidl, HANDLE token, DWORD flags, LPSTR out) {
    (void)owner; (void)csidl; (void)token; (void)flags;
    lstrcpyA(out, g_docs);
    return S_OK;
}

#define SHGetFolderPathA harness_docs
#include "vv1_parentage.c"
#undef SHGetFolderPathA

#define SLOT 1

static int failures;
static char sidecar[MAX_PATH];
static char marker[MAX_PATH];
static char births_dir[MAX_PATH];
static char repairs[MAX_PATH];
static char backup1[MAX_PATH];
static char backup2[MAX_PATH];

static void check(int ok, const char *name) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok) {
        ++failures;
    }
}

/* ---- villages ---------------------------------------------------------- */

typedef struct {
    const char *name;
    int male, scalar, head, body;
    int couple;                   /* 0 none (founder or arrival), 1 Kito+Chika, 2 Ghali+Onawa */
} villager;

/* The owner's village: Ghali, Kito, Chika and Onawa are founders, Huata a
   founder too, and the children alternate between the two couples. */
static const villager owner[] = {
    { "Ghali", 1, 45, 6, 1, 0 }, { "Kito", 1, 19, 0, 18, 0 }, { "Chika", 0, 39, 19, 17, 0 },
    { "Onawa", 0, 50, 16, 2, 0 }, { "Huata", 0, 36, 11, 9, 0 },
    { "Nishi", 0, 39, 7, 3, 1 }, { "Penyo", 0, 50, 8, 15, 2 }, { "Chapa", 0, 39, 12, 4, 1 },
    { "Pupa", 0, 50, 14, 6, 2 }, { "Howi", 1, 39, 3, 11, 1 }, { "Usutu", 1, 50, 21, 2, 2 },
    { "Yepa", 0, 39, 9, 13, 1 }, { "Iruwa", 0, 50, 4, 20, 2 }, { "Goro", 1, 39, 17, 7, 1 },
    { "Hawa", 0, 50, 2, 19, 2 }, { "Lisha", 0, 50, 13, 10, 2 }, { "Kaimi", 0, 39, 5, 16, 1 },
};
#define OWNER_COUNT ((int)(sizeof(owner) / sizeof(owner[0])))
static const villager silko = { "Silko", 1, 77, 22, 5, 0 };   /* a grown arrival */

static unsigned char before_load[VV1_RECORD_COUNT * VV1_RECORD_STRIDE];
static unsigned char after_load[VV1_RECORD_COUNT * VV1_RECORD_STRIDE];
static unsigned char village[VV1_RECORD_COUNT * VV1_RECORD_STRIDE];

static void put(unsigned char *records, int index, const villager *v, int due) {
    unsigned char *rec = records + (unsigned int)index * VV1_RECORD_STRIDE;
    memset(rec, 0, VV1_RECORD_STRIDE);
    rec[VV1_OCCUPIED_OFFSET] = 1;
    *(int *)(rec + VV1_GENDER_OFFSET) = v->male ? 1 : 2;
    *(int *)(rec + VV1_VARIANT_OFFSET) = v->scalar;
    *(int *)(rec + VV1_AGE_OFFSET) = 25 * VV1_UNITS_PER_YEAR;
    *(int *)(rec + VV1_HEAD_OFFSET) = v->head;
    *(int *)(rec + VV1_BODY_OFFSET) = v->body;
    *(int *)(rec + VV1_DUE_OFFSET) = due;
    lstrcpyA((char *)rec + VV1_NAME_OFFSET, v->name);
}

/* Packed, without the two named dead; Silko after them when `arrival`. */
static int lay_out(unsigned char *records, const char *dead_a, const char *dead_b, int arrival) {
    int i, at = 0;
    memset(records, 0, VV1_RECORD_COUNT * VV1_RECORD_STRIDE);
    for (i = 0; i < OWNER_COUNT; ++i) {
        if ((dead_a && lstrcmpA(owner[i].name, dead_a) == 0) || (dead_b && lstrcmpA(owner[i].name, dead_b) == 0)) {
            continue;
        }
        put(records, at++, &owner[i], 0);
    }
    if (arrival) {
        put(records, at++, &silko, 0);
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

static const villager *find(const char *name) {
    int i;
    for (i = 0; i < OWNER_COUNT; ++i) {
        if (lstrcmpA(owner[i].name, name) == 0) return &owner[i];
    }
    return lstrcmpA(name, "Silko") == 0 ? &silko : NULL;
}

/* The entry the log says villager `v` should have. */
static void true_entry(const villager *v, vv1_parent_entry *e) {
    const villager *f = NULL, *m = NULL;
    memset(e, 0, sizeof(*e));
    if (v->couple == 1) { f = find("Kito"); m = find("Chika"); }
    if (v->couple == 2) { f = find("Ghali"); m = find("Onawa"); }
    if (f) { e->father_head = (unsigned char)(f->head + 1); e->father_body = (unsigned char)(f->body + 1); lstrcpyA(e->father_name, f->name); }
    if (m) { e->mother_head = (unsigned char)(m->head + 1); e->mother_body = (unsigned char)(m->body + 1); lstrcpyA(e->mother_name, m->name); }
}

/* ---- files ------------------------------------------------------------- */

static DWORD file_size(const char *p) {
    WIN32_FILE_ATTRIBUTE_DATA a;
    return GetFileAttributesExA(p, GetFileExInfoStandard, &a) ? a.nFileSizeLow : 0xFFFFFFFFu;
}

static int exists(const char *p) {
    return GetFileAttributesA(p) != INVALID_FILE_ATTRIBUTES;
}

static int read_all(const char *p, void *out, DWORD cap, DWORD *size) {
    HANDLE h = CreateFileA(p, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    BOOL ok;
    *size = 0;
    if (h == INVALID_HANDLE_VALUE) return 0;
    ok = ReadFile(h, out, cap, size, NULL);
    CloseHandle(h);
    return ok ? 1 : 0;
}

static int write_text(const char *p, const char *text) {
    HANDLE h = CreateFileA(p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    DWORD wrote = 0;
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) return 0;
    ok = WriteFile(h, text, (DWORD)lstrlenA(text), &wrote, NULL);
    CloseHandle(h);
    return ok ? 1 : 0;
}

static char *slurp(const char *p) {
    static char buf[256 * 1024];
    DWORD size = 0;
    buf[0] = '\0';
    if (read_all(p, buf, sizeof(buf) - 1, &size)) buf[size] = '\0';
    return buf;
}

static int same_files(const char *a, const char *b) {
    static unsigned char x[64 * 1024], y[64 * 1024];
    DWORD sx = 0, sy = 0;
    return read_all(a, x, sizeof(x), &sx) && read_all(b, y, sizeof(y), &sy) && sx == sy && memcmp(x, y, sx) == 0;
}

static int set_dacl(const char *p, const char *sddl) {
    PSECURITY_DESCRIPTOR sd = NULL;
    BOOL ok;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorA(sddl, SDDL_REVISION_1, &sd, NULL)) return 0;
    ok = SetFileSecurityA(p, DACL_SECURITY_INFORMATION, sd);
    LocalFree(sd);
    return ok ? 1 : 0;
}

static void log_path(char *out, int n) {
    wsprintfA(out, "%s\\Virtual Villagers 1 Births and Conceptions Log %d.txt", births_dir, n);
}

static void clear_files(void) {
    char p[MAX_PATH];
    int n;
    DeleteFileA(sidecar);
    DeleteFileA(marker);
    DeleteFileA(repairs);
    DeleteFileA(backup1);
    DeleteFileA(backup2);
    for (n = 1; n <= 12; ++n) { log_path(p, n); DeleteFileA(p); }
}

/* ---- the Births log ---------------------------------------------------- */

static char logtext[128 * 1024];

static void log_begin(const char *village_line) {
    wsprintfA(logtext, "%s\n", village_line);
}

static void log_person(const char *label, const villager *v) {
    wsprintfA(logtext + lstrlenA(logtext), "  %s: %s\n    Head: %d\n    Body: %d\n", label, v->name, v->head, v->body);
}

static void log_birth_of(const villager *child, const villager *mother, const villager *father) {
    wsprintfA(logtext + lstrlenA(logtext), "Birth\n  Child: %s\n    Head: %d\n    Body: %d\n    Likes: (none)\n    Dislikes: (none)\n"
              "  Skills:\n    Breeding   0\n    Building   0\n", child->name, child->head, child->body);
    if (mother) log_person("Mother", mother);
    if (father) log_person("Father", father);
    lstrcatA(logtext, "\n");
}

static int conceptions;
static void log_conception_of(const villager *mother, const villager *father) {
    wsprintfA(logtext + lstrlenA(logtext), "Conception %d\n  Mother: %s\n    Age at conception: 400\n    Head: %d\n    Body: %d\n"
              "    Likes: (none)\n    Dislikes: (none)\n", ++conceptions, mother->name, mother->head, mother->body);
    if (father) {
        wsprintfA(logtext + lstrlenA(logtext), "  Father: %s\n    Age at conception: 400\n    Head: %d\n    Body: %d\n",
                  father->name, father->head, father->body);
    }
    lstrcatA(logtext, "  Babies in pregnancy: 1\n\n");
}

/* The owner's whole village's births, as the companion logged them. */
static void log_owner_births(void) {
    int i;
    for (i = 0; i < OWNER_COUNT; ++i) {
        if (owner[i].couple == 1) log_birth_of(&owner[i], find("Chika"), find("Kito"));
        if (owner[i].couple == 2) log_birth_of(&owner[i], find("Onawa"), find("Ghali"));
    }
}

static void log_save(int n) {
    char p[MAX_PATH];
    log_path(p, n);
    write_text(p, logtext);
}

/* ---- the companion ----------------------------------------------------- */

static void fresh(void) {
    memset(g_entries, 0, sizeof(g_entries));
    memset(g_roster, 0, sizeof(g_roster));
    g_loaded_slot = 0;
    g_strikes = 0;
    g_have_prev = 0;
    g_blocked_slot = 0;
    g_blocked_wait = 0;
    g_may_replace = 0;
    g_asked = 0;
    memset(g_session_born, 0, sizeof(g_session_born));
    memset(g_session_stash, 0, sizeof(g_session_stash));
    g_xc_father_count = 0;
}

/* Write a sidecar holding `entries` against `records`' roster, as an earlier
   build left it on disk. */
static void write_sidecar(const unsigned char *records, const vv1_parent_entry *entries) {
    DeleteFileA(sidecar);
    fresh();
    vv1_take_roster(records, g_roster);
    memcpy(g_entries, entries, sizeof(g_entries));
    g_may_replace = 1;
    if (!vv1_parents_save(SLOT, records)) {
        printf("FAIL setup: could not write the sidecar\n");
        ++failures;
    }
    fresh();
}

static vv1_xc_plan g_plan;
static int g_applied;

/* A new process loads the village (frames of the real sync), then the
   prompt's decision runs as the bridge drives it: the scan, and -- when it
   found something to ask about -- the player's answer, IDYES calling the
   repair.  Returns the number of times the player was asked (0 or 1). */
static int load_and_check(const unsigned char *records, int answer) {
    int f;
    fresh();
    g_applied = -1;
    for (f = 0; f < 3; ++f) {
        vv1_parents_sync_core(SLOT, records);
    }
    if (vv1_xc_scan(SLOT, records, &g_plan) == 1) {
        ++g_asked;
        if (answer == IDYES) {
            g_applied = vv1_xc_apply(SLOT, records);
        }
    }
    return g_asked;
}

/* Only the load: what the Details screen would show. */
static void load_only(const unsigned char *records) {
    int f;
    fresh();
    for (f = 0; f < 3; ++f) {
        vv1_parents_sync_core(SLOT, records);
    }
}

static int entry_matches(int index, const vv1_parent_entry *want) {
    const vv1_parent_entry *e = &g_entries[index];
    return e->father_head == want->father_head && e->father_body == want->father_body
        && e->mother_head == want->mother_head && e->mother_body == want->mother_body
        && lstrcmpA(e->father_name, want->father_name) == 0 && lstrcmpA(e->mother_name, want->mother_name) == 0;
}

/* Every living villager in `records` has the parents the log names. */
static int all_true(const unsigned char *records) {
    int i;
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        const unsigned char *rec = records + (unsigned int)i * VV1_RECORD_STRIDE;
        vv1_parent_entry want;
        const villager *v;
        if (!rec[VV1_OCCUPIED_OFFSET]) continue;
        v = find((const char *)rec + VV1_NAME_OFFSET);
        if (v == NULL) continue;
        true_entry(v, &want);
        if (!entry_matches(i, &want)) {
            printf("  ... %s at [%d] has father '%s' mother '%s'\n", v->name, i, g_entries[i].father_name, g_entries[i].mother_name);
            return 0;
        }
    }
    return 1;
}

static unsigned int marker_result(void) {
    unsigned int data[12];
    DWORD size = 0;
    if (!read_all(marker, data, sizeof(data), &size) || size != sizeof(data)) return 0;
    return data[0] == VV1_XC_MAGIC && data[3] == SLOT ? data[4] : 0;
}

/* The owner's sidecar as the pre-v1.35.57 build left it after Kito and Chika
   died and the save was loaded: the array compacted, every entry stayed at its
   index, and the roster was rebound to the new occupants -- so everyone from
   record 1 up holds the entry of whoever was two records higher before. */
static void write_drifted_owner_sidecar(void) {
    static vv1_parent_entry entries[VV1_RECORD_COUNT];
    int i;
    lay_out(before_load, NULL, NULL, 0);
    lay_out(after_load, "Kito", "Chika", 1);
    memset(entries, 0, sizeof(entries));
    for (i = 0; i < OWNER_COUNT; ++i) {
        true_entry(&owner[i], &entries[i]);          /* indexed as BEFORE the load */
    }
    write_sidecar(after_load, entries);              /* ... but bound to the roster AFTER it */
}

/* ---- the cases --------------------------------------------------------- */

static void owner_scenario(void) {
    static unsigned char drifted[16 + sizeof(g_roster) + sizeof(g_entries)];
    DWORD drifted_size = 0;
    int lisha, silko_at, nishi, asked;
    char *note;

    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_save(1);
    write_drifted_owner_sidecar();
    read_all(sidecar, drifted, sizeof(drifted), &drifted_size);

    /* The drift is real: following alone cannot see it. */
    load_only(after_load);
    lisha = where(after_load, "Lisha");
    silko_at = where(after_load, "Silko");
    nishi = where(after_load, "Nishi");
    check(lisha == 13 && lstrcmpA(g_entries[lisha].father_name, "Kito") == 0,
          "the drifted sidecar shows Lisha [13] as Kito and Chika's, as the owner saw");
    check(lstrcmpA(g_entries[silko_at].father_name, "Ghali") == 0,
          "... and Silko, a grown arrival, as Ghali and Onawa's");

    /* Not now: nothing changes, nothing is recorded, and it asks again next load. */
    asked = load_and_check(after_load, IDNO);
    check(asked == 1, "the player is asked before anything is repaired");
    check(g_plan.corrected == 2 && g_plan.cleared == 1 && g_plan.filled == 2 && g_plan.ambiguous == 0,
          "... and the scan counts what the prompt will say: Lisha and Kaimi corrected, Nishi and Penyo filled in, Silko set to unknown");
    check(same_files(sidecar, sidecar) && file_size(sidecar) == drifted_size, "Not now: the sidecar is untouched");
    {
        static unsigned char now_bytes[sizeof(drifted)];
        DWORD n = 0;
        read_all(sidecar, now_bytes, sizeof(now_bytes), &n);
        check(n == drifted_size && memcmp(now_bytes, drifted, n) == 0, "... byte for byte");
    }
    check(!exists(marker) && !exists(backup1) && !exists(repairs),
          "... no marker, no backup, no Repairs log");
    check(lstrcmpA(g_entries[lisha].father_name, "Kito") == 0, "... and the table in memory is as it was");

    /* Repair. */
    asked = load_and_check(after_load, IDYES);
    check(asked == 1 && g_applied == 1, "the next load asks again, and the player chooses Repair");
    check(all_true(after_load), "every living villager now has the parents the Births log names");
    check(lstrcmpA(g_entries[lisha].father_name, "Ghali") == 0 && lstrcmpA(g_entries[lisha].mother_name, "Onawa") == 0,
          "... Lisha [13] is Ghali and Onawa's again");
    check(lstrcmpA(g_entries[nishi].father_name, "Kito") == 0, "... Nishi is Kito and Chika's");
    check(!vv1_xc_has_parents(&g_entries[silko_at]), "... and Silko, a grown arrival, has no parents");
    check(!vv1_xc_has_parents(&g_entries[where(after_load, "Ghali")]), "... and the founders have none");
    check(exists(backup1) && file_size(backup1) == drifted_size, "the file was backed up beside itself first");
    {
        static unsigned char b[sizeof(drifted)];
        DWORD n = 0;
        read_all(backup1, b, sizeof(b), &n);
        check(n == drifted_size && memcmp(b, drifted, n) == 0, "... and the backup is the file as it was, byte for byte");
    }
    check(marker_result() == VV1_XC_RESULT_REPAIRED, "the marker records that the check ran and repaired");
    note = slurp(repairs);
    check(strncmp(note, "Village: Kalahuna Tribe 1 (Save 1)\r\nRepair 1\r\n",
                  sizeof("Village: Kalahuna Tribe 1 (Save 1)\r\nRepair 1\r\n") - 1) == 0,
          "the Repairs log opens with the village's own header and Repair 1");
    check(strstr(note, "Corrected: Lisha -- now father Ghali, mother Onawa (was father Kito, mother Chika)") != NULL,
          "... and lists Lisha's correction");
    check(strstr(note, "Set to unknown: Silko -- no Birth record in the log (was father Ghali, mother Onawa)") != NULL,
          "... and Silko's");
    check(strstr(note, "Backup: Virtual Villagers 1 Parentage Records - Save 1.dat.before-v1.35.58-repair") != NULL,
          "... and names the backup");

    /* What is on disk is what is shown: a new process loads the repaired file. */
    load_only(after_load);
    check(all_true(after_load), "the repaired sidecar on disk loads with every villager's true parents");

    /* Runs once. */
    {
        static unsigned char repaired[sizeof(drifted)];
        static unsigned char again[sizeof(drifted)];
        DWORD a = 0, b = 0;
        DWORD note_size = file_size(repairs);
        read_all(sidecar, repaired, sizeof(repaired), &a);
        asked = load_and_check(after_load, IDYES);
        read_all(sidecar, again, sizeof(again), &b);
        check(asked == 0 && vv1_xc_scan(SLOT, after_load, &g_plan) == 0,
              "the next load does not ask again: it runs once per village (the scan answers 'nothing', not 'later')");
        check(a == b && memcmp(repaired, again, a) == 0 && file_size(repairs) == note_size && !exists(backup2),
              "... and changes nothing, backs nothing up, notes nothing");
    }
}

static void clean_and_no_log_cases(void) {
    static vv1_parent_entry entries[VV1_RECORD_COUNT];
    static unsigned char before[16 + sizeof(g_roster) + sizeof(g_entries)];
    static unsigned char after[sizeof(before)];
    DWORD a = 0, b = 0;
    int i, asked;

    /* A table already in step with the log (written by this build): checked silently. */
    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_save(1);
    lay_out(village, "Kito", "Chika", 1);
    memset(entries, 0, sizeof(entries));
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        const unsigned char *rec = village + (unsigned int)i * VV1_RECORD_STRIDE;
        if (rec[VV1_OCCUPIED_OFFSET]) true_entry(find((const char *)rec + VV1_NAME_OFFSET), &entries[i]);
    }
    write_sidecar(village, entries);
    read_all(sidecar, before, sizeof(before), &a);
    asked = load_and_check(village, IDYES);
    read_all(sidecar, after, sizeof(after), &b);
    check(asked == 0, "a table already in step with the log: no prompt");
    check(a == b && memcmp(before, after, a) == 0 && !exists(backup1) && !exists(repairs),
          "... nothing changed, nothing backed up, nothing noted");
    check(marker_result() == VV1_XC_RESULT_CLEAN, "... and the marker records a clean check");

    /* No Births log at all: nothing to check against. */
    clear_files();
    write_sidecar(village, entries);
    read_all(sidecar, before, sizeof(before), &a);
    asked = load_and_check(village, IDYES);
    read_all(sidecar, after, sizeof(after), &b);
    check(asked == 0 && a == b && memcmp(before, after, a) == 0, "no Births log: no prompt, nothing changed");
    check(marker_result() == VV1_XC_RESULT_NO_LOG, "... and the marker records there was nothing to check");

    /* A log with this village's conceptions but no Birth at all says nothing about who was born. */
    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_conception_of(find("Chika"), find("Kito"));
    log_save(1);
    write_sidecar(village, entries);
    asked = load_and_check(village, IDYES);
    check(asked == 0 && marker_result() == VV1_XC_RESULT_NO_LOG,
          "a log with no Birth record clears nobody: treated as no log");

    /* Another slot's births are not this village's. */
    clear_files();
    conceptions = 0;
    log_begin("Village: Other Tribe (Save 2)");
    log_owner_births();
    log_save(1);
    write_sidecar(village, entries);
    asked = load_and_check(village, IDYES);
    check(asked == 0 && marker_result() == VV1_XC_RESULT_NO_LOG, "another slot's births are never used");

    /* ... and another slot's section AFTER this village's does not hide this village's. */
    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    lstrcatA(logtext, "Village: Other Tribe (Save 2)\n");
    log_save(1);
    write_drifted_owner_sidecar();
    asked = load_and_check(after_load, IDYES);
    check(asked == 1 && g_applied == 1 && all_true(after_load),
          "a log that goes on to another slot's village still repairs this one from its own section");
}

static void ambiguity_cases(void) {
    static vv1_parent_entry entries[VV1_RECORD_COUNT];
    static const villager twin_a = { "Ama", 0, 39, 7, 7, 1 };
    static const villager twin_b = { "Ama", 0, 39, 7, 7, 1 };
    static const villager changed = { "Howi", 1, 39, 25, 25, 1 };   /* looks changed since birth */
    int asked;

    /* Two Birth records for one name, head and body that name different
       parents: the log cannot tell, so the parents are unknown. */
    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_birth_of(&twin_a, find("Chika"), find("Kito"));
    log_birth_of(&twin_a, find("Onawa"), find("Ghali"));
    log_save(1);
    memset(village, 0, sizeof(village));
    put(village, 0, find("Ghali"), 0);
    put(village, 1, &twin_a, 0);
    memset(entries, 0, sizeof(entries));
    true_entry(find("Lisha"), &entries[1]);
    write_sidecar(village, entries);
    asked = load_and_check(village, IDYES);
    check(asked == 1 && !vv1_xc_has_parents(&g_entries[1]),
          "Birth records that disagree for one villager: the parents are set to unknown, never guessed");

    /* Identical twins (one name, one look) and two Birth records naming the
       same parents: both are those parents' children. */
    clear_files();
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_birth_of(&twin_a, find("Chika"), find("Kito"));
    log_birth_of(&twin_b, find("Chika"), find("Kito"));
    log_save(1);
    memset(village, 0, sizeof(village));
    put(village, 0, &twin_a, 0);
    put(village, 1, &twin_b, 0);
    memset(entries, 0, sizeof(entries));
    true_entry(find("Lisha"), &entries[0]);
    true_entry(find("Lisha"), &entries[1]);
    write_sidecar(village, entries);
    asked = load_and_check(village, IDYES);
    {
        vv1_parent_entry want;
        true_entry(find("Nishi"), &want);
        check(asked == 1 && entry_matches(0, &want) && entry_matches(1, &want),
              "identical twins whose Birth records agree both get those parents");
    }

    /* ... but two living villagers sharing name and looks with only ONE Birth
       record: one of them was not born here, and nobody can say which. */
    clear_files();
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_birth_of(&twin_a, find("Chika"), find("Kito"));
    log_save(1);
    write_sidecar(village, entries);
    asked = load_and_check(village, IDYES);
    check(asked == 1 && !vv1_xc_has_parents(&g_entries[0]) && !vv1_xc_has_parents(&g_entries[1]),
          "two identical villagers and one Birth record: both unknown");

    /* A villager whose name has Birth records but none with their looks (an
       appearance upgrade since birth) cannot be confirmed: left as it is. */
    clear_files();
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_birth_of(find("Howi"), find("Chika"), find("Kito"));
    log_save(1);
    memset(village, 0, sizeof(village));
    put(village, 0, &changed, 0);
    memset(entries, 0, sizeof(entries));
    true_entry(find("Lisha"), &entries[0]);          /* Ghali and Onawa: unconfirmable */
    write_sidecar(village, entries);
    asked = load_and_check(village, IDYES);
    check(asked == 0 && lstrcmpA(g_entries[0].father_name, "Ghali") == 0 && marker_result() == VV1_XC_RESULT_CLEAN,
          "a villager whose looks changed since birth is left as it is, never cleared");
}

static void stash_cases(void) {
    static vv1_parent_entry entries[VV1_RECORD_COUNT];
    int asked;
    /* Chapa is expecting; her last logged conception names Usutu, but the
       table (drifted) says Howi.  Corrected. */
    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_conception_of(find("Chapa"), find("Howi"));
    log_birth_of(find("Yepa"), find("Chapa"), find("Howi"));   /* an earlier baby */
    log_conception_of(find("Chapa"), find("Usutu"));
    log_save(1);
    memset(village, 0, sizeof(village));
    put(village, 0, find("Chapa"), 900);
    put(village, 1, find("Usutu"), 0);
    put(village, 2, find("Howi"), 0);
    memset(entries, 0, sizeof(entries));
    true_entry(find("Chapa"), &entries[0]);
    lstrcpyA(entries[0].stash_name, "Howi"); entries[0].stash_head = 4; entries[0].stash_body = 12;
    true_entry(find("Usutu"), &entries[1]);
    true_entry(find("Howi"), &entries[2]);
    write_sidecar(village, entries);
    asked = load_and_check(village, IDYES);
    check(asked == 1 && lstrcmpA(g_entries[0].stash_name, "Usutu") == 0
          && g_entries[0].stash_head == 22 && g_entries[0].stash_body == 3,
          "an expecting mother's baby gets the father of her last logged conception");
    check(strstr(slurp(repairs), "Pregnancy: Chapa -- father Usutu (was Howi)") != NULL,
          "... and the Repairs log says so");

    /* ... but when she delivered after her last logged conception, this
       pregnancy is not in the log: the stash is left alone. */
    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_conception_of(find("Chapa"), find("Usutu"));
    log_birth_of(find("Yepa"), find("Chapa"), find("Usutu"));
    log_save(1);
    entries[0].stash_head = 4;
    write_sidecar(village, entries);
    asked = load_and_check(village, IDYES);
    check(lstrcmpA(g_entries[0].stash_name, "Howi") == 0, "a pregnancy the log does not hold keeps its stash");
}

/* The load-time catch-up delivers babies before the village is on screen,
   and the session's log records are only written at the next save. */
static void session_cases(void) {
    static vv1_parent_entry entries[VV1_RECORD_COUNT];
    static const villager baba = { "Baba", 0, 39, 3, 3, 0 };
    unsigned char *mrec, *crec;
    int asked, c;

    /* Chapa is expecting; her last logged conception names Usutu; the
       drifted table's stash says Howi. */
    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_conception_of(find("Chapa"), find("Usutu"));
    log_save(1);
    memset(village, 0, sizeof(village));
    put(village, 0, find("Chapa"), 900);
    put(village, 1, find("Usutu"), 0);
    put(village, 2, find("Howi"), 0);
    memset(entries, 0, sizeof(entries));
    true_entry(find("Chapa"), &entries[0]);
    lstrcpyA(entries[0].stash_name, "Howi"); entries[0].stash_head = 4; entries[0].stash_body = 12;
    true_entry(find("Usutu"), &entries[1]);
    true_entry(find("Howi"), &entries[2]);
    write_sidecar(village, entries);

    /* The load, then a catch-up birth -- before anyone is asked anything. */
    load_only(village);
    mrec = village;
    crec = village + 3u * VV1_RECORD_STRIDE;
    put(village, 3, &baba, 0);
    *(int *)(crec + VV1_AGE_OFFSET) = 40;
    c = vv1_born(village, crec, mrec);
    *(int *)(mrec + VV1_DUE_OFFSET) = 0;             /* the delivery ends the pregnancy */
    check(c == 3 && lstrcmpA(g_entries[3].father_name, "Usutu") == 0 && g_entries[3].father_head == 22
          && lstrcmpA(g_entries[3].mother_name, "Chapa") == 0,
          "a catch-up birth before the check takes the father the log confirms, not the drifted stash");
    check(lstrcmpA(g_entries[0].stash_name, "Howi") == 0, "... and the stash itself is not changed before the player is asked");

    /* The newborn has no Birth record in the log FILE yet: it is left alone. */
    asked = vv1_xc_scan(SLOT, village, &g_plan);
    {
        int i, newborn_listed = 0;
        for (i = 0; i < g_plan.count; ++i) newborn_listed |= g_plan.changes[i].index == 3;
        check(asked == 1 && !newborn_listed && g_plan.cleared == 0,
              "a villager born this session is never cleared for want of a Birth record the log has not written yet");
        check(g_plan.stashes == 1,
              "... and the stash of a pregnancy the catch-up already delivered is corrected too (a crash would deliver it again)");
    }
    check(vv1_xc_apply(SLOT, village) == 1 && lstrcmpA(g_entries[3].mother_name, "Chapa") == 0
          && lstrcmpA(g_entries[3].father_name, "Usutu") == 0,
          "... and keeps both parents through the repair");

    /* A villager the file does not know -- born in a later session than the
       file's, with a Birth record in the log -- is not a newborn of THIS
       session: the check fills them in. */
    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_save(1);
    memset(village, 0, sizeof(village));
    put(village, 0, find("Usutu"), 0);
    put(village, 1, find("Howi"), 0);
    {
        static vv1_parent_entry known[VV1_RECORD_COUNT];
        true_entry(find("Usutu"), &known[0]);
        true_entry(find("Howi"), &known[1]);
        write_sidecar(village, known);               /* the file: Usutu and Howi */
    }
    put(village, 2, find("Lisha"), 0);               /* the save: Lisha too */
    load_only(village);
    asked = vv1_xc_scan(SLOT, village, &g_plan);
    check(asked == 1 && g_plan.filled == 1 && vv1_xc_apply(SLOT, village) == 1
          && lstrcmpA(g_entries[2].father_name, "Ghali") == 0,
          "a villager the old file never knew, with a Birth record, is filled in (not taken for a newborn)");

    /* A conception made this session is always right: its stash is used. */
    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_conception_of(find("Chapa"), find("Usutu"));
    log_save(1);
    memset(village, 0, sizeof(village));
    put(village, 0, find("Chapa"), 900);
    put(village, 1, find("Usutu"), 0);
    put(village, 2, find("Howi"), 0);
    write_sidecar(village, entries);
    load_only(village);
    vv1_stash(village, village, village + 2u * VV1_RECORD_STRIDE);   /* Chapa conceives by Howi now */
    put(village, 3, &baba, 0);
    c = vv1_born(village, village + 3u * VV1_RECORD_STRIDE, village);
    check(c == 3 && lstrcmpA(g_entries[3].father_name, "Howi") == 0,
          "a conception made this session gives its own father");
    asked = vv1_xc_scan(SLOT, village, &g_plan);
    check(g_plan.stashes == 0, "... and its stash is never 'corrected' from an older conception");

    /* Once the check has run, the stash is the log's: births use it. */
    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_conception_of(find("Chapa"), find("Usutu"));
    log_save(1);
    memset(village, 0, sizeof(village));
    put(village, 0, find("Chapa"), 900);
    put(village, 1, find("Usutu"), 0);
    put(village, 2, find("Howi"), 0);
    write_sidecar(village, entries);
    vv1_xc_marker_write(SLOT, VV1_XC_RESULT_CLEAN, NULL, vv1_xc_village_id("Village: Kalahuna Tribe 1 (Save 1)"));
    load_only(village);
    put(village, 3, &baba, 0);
    c = vv1_born(village, village + 3u * VV1_RECORD_STRIDE, village);
    check(c == 3 && lstrcmpA(g_entries[3].father_name, "Howi") == 0,
          "after the check has run, a birth takes the stash as it always did");
}

static void failure_cases(void) {
    static unsigned char before[16 + sizeof(g_roster) + sizeof(g_entries)];
    static unsigned char after[sizeof(before)];
    char p[MAX_PATH];
    char tmpdir[MAX_PATH];
    DWORD a = 0, b = 0;
    int asked;

    /* An unreadable Births log: nothing changes, and it is tried again next load. */
    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_save(1);
    write_drifted_owner_sidecar();
    log_path(p, 1);
    set_dacl(p, "D:(D;;0x1;;;WD)(A;;FA;;;WD)");
    read_all(sidecar, before, sizeof(before), &a);
    asked = load_and_check(after_load, IDYES);
    read_all(sidecar, after, sizeof(after), &b);
    check(asked == 0 && a == b && memcmp(before, after, a) == 0 && !exists(marker),
          "an unreadable Births log: nothing changed, no marker");
    set_dacl(p, "D:(A;;FA;;;WD)");
    asked = load_and_check(after_load, IDYES);
    check(asked == 1 && all_true(after_load), "... and once it can be read, the next load repairs");

    /* A table that cannot be written: nothing changes, nothing is recorded. */
    clear_files();
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_save(1);
    write_drifted_owner_sidecar();
    read_all(sidecar, before, sizeof(before), &a);
    wsprintfA(tmpdir, "%s.tmp", sidecar);
    CreateDirectoryA(tmpdir, NULL);              /* the atomic save's temporary cannot be created */
    asked = load_and_check(after_load, IDYES);
    read_all(sidecar, after, sizeof(after), &b);
    check(asked == 1 && g_applied == 0 && a == b && memcmp(before, after, a) == 0,
          "a repair that cannot be written changes nothing on disk, and says so");
    check(lstrcmpA(g_entries[where(after_load, "Lisha")].father_name, "Kito") == 0,
          "... nor in memory (the old parents still show, as on disk)");
    check(!exists(marker) && !exists(backup1), "... and marks nothing done (its own backup removed), so the next load tries again");
    check(strstr(slurp(repairs), "  Not applied: the parentage file could not be written; nothing was changed.") != NULL,
          "... and the Repairs log says the repair was not applied");
    RemoveDirectoryA(tmpdir);

    /* A Repairs log that cannot be written stops the repair: no change without its record. */
    clear_files();
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_save(1);
    write_drifted_owner_sidecar();
    read_all(sidecar, before, sizeof(before), &a);
    CreateDirectoryA(repairs, NULL);             /* the note's file name is taken by a folder */
    asked = load_and_check(after_load, IDYES);
    read_all(sidecar, after, sizeof(after), &b);
    check(asked == 1 && g_applied == 0 && a == b && memcmp(before, after, a) == 0 && !exists(marker) && !exists(backup1),
          "a repair whose note cannot be written is not made at all");
    RemoveDirectoryA(repairs);

    /* A marker for another village in this slot (a save copied in) does not stop the check. */
    clear_files();
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_save(1);
    write_drifted_owner_sidecar();
    vv1_xc_marker_write(SLOT, VV1_XC_RESULT_CLEAN, NULL, vv1_xc_village_id("Village: Another Tribe (Save 1)"));
    asked = load_and_check(after_load, IDYES);
    check(asked == 1 && g_applied == 1, "a marker left by another village in the slot does not count for this one");

    /* A parent the log could not name is no parent. */
    clear_files();
    lstrcpyA(logtext, "Village: Kalahuna Tribe 1 (Save 1)\nBirth\n  Child: Nishi\n    Head: 7\n    Body: 3\n"
                      "  Mother: Chika\n    Head: 19\n    Body: 17\n  Father: (unknown)\n    Head: -1\n    Body: -1\n\n");
    log_save(1);
    memset(village, 0, sizeof(village));
    put(village, 0, find("Nishi"), 0);
    {
        static vv1_parent_entry none[VV1_RECORD_COUNT];
        write_sidecar(village, none);
    }
    asked = load_and_check(village, IDYES);
    check(asked == 1 && g_applied == 1 && g_entries[0].father_name[0] == '\0' && g_entries[0].father_head == 0
          && lstrcmpA(g_entries[0].mother_name, "Chika") == 0,
          "a Birth record's \"(unknown)\" father is no father, never the name \"(unknown)\"");

    /* More villages for this slot than the header table holds: change nothing. */
    clear_files();
    logtext[0] = '\0';
    {
        int k;
        for (k = 0; k < VV1_XC_MAX_HEADERS + 2; ++k) {
            wsprintfA(logtext + lstrlenA(logtext), "Village: Tribe %d (Save 1)\nBirth\n  Child: Nishi\n    Head: 7\n"
                      "    Body: 3\n  Mother: Onawa\n    Head: 16\n    Body: 2\n\n", k);
        }
    }
    log_save(1);
    asked = load_and_check(village, IDYES);
    check(asked == 0 && !exists(marker), "a log naming more villages than can be told apart changes nothing");

    /* A backup name already taken is never replaced. */
    clear_files();
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_save(1);
    write_drifted_owner_sidecar();
    write_text(backup1, "the player's own older backup");
    asked = load_and_check(after_load, IDYES);
    check(asked == 1 && lstrcmpA(slurp(backup1), "the player's own older backup") == 0 && exists(backup2),
          "an existing backup is never replaced: the next free name is used");

    /* A marker that is not a marker is set aside, and the check runs. */
    clear_files();
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_save(1);
    write_drifted_owner_sidecar();
    write_text(marker, "garbage");
    asked = load_and_check(after_load, IDYES);
    check(asked == 1 && marker_result() == VV1_XC_RESULT_REPAIRED, "a damaged marker is set aside and the check runs");
}

static void many_files_case(void) {
    int asked;
    /* Records in files 2 and 10 are read in number order (2 before 10): the
       stash comes from the LAST conception, which is in file 10. */
    static vv1_parent_entry entries[VV1_RECORD_COUNT];
    clear_files();
    conceptions = 0;
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_owner_births();
    log_conception_of(find("Chapa"), find("Howi"));
    log_save(2);
    log_begin("Village: Kalahuna Tribe 1 (Save 1)");
    log_conception_of(find("Chapa"), find("Usutu"));
    log_save(10);
    memset(village, 0, sizeof(village));
    put(village, 0, find("Chapa"), 900);
    memset(entries, 0, sizeof(entries));
    true_entry(find("Chapa"), &entries[0]);
    write_sidecar(village, entries);
    asked = load_and_check(village, IDYES);
    check(asked == 1 && lstrcmpA(g_entries[0].stash_name, "Usutu") == 0,
          "numbered log files are read in number order (file 10 after file 2)");
}

int main(int argc, char **argv) {
    char game[MAX_PATH];
    if (argc < 2) {
        printf("usage: vv1_crosscheck_harness <docs folder>\n");
        return 2;
    }
    lstrcpyA(g_docs, argv[1]);
    vv1_parents_path(sidecar, sizeof(sidecar), SLOT);
    vv1_xc_marker_path(marker, sizeof(marker), SLOT);
    vv1_xc_subfolder(births_dir, sizeof(births_dir), "Virtual Villagers Fun Patcher Logs", "Births and Conceptions", 80);
    vv1_xc_subfolder(game, sizeof(game), "Virtual Villagers Fun Patcher Logs", "Repairs", 80);
    wsprintfA(repairs, "%s\\Virtual Villagers 1 Repairs Log 1.txt", game);
    wsprintfA(backup1, "%s" VV1_XC_BACKUP_SUFFIX, sidecar);
    wsprintfA(backup2, "%s" VV1_XC_BACKUP_SUFFIX "-2", sidecar);

    owner_scenario();
    clean_and_no_log_cases();
    ambiguity_cases();
    stash_cases();
    session_cases();
    failure_cases();
    many_files_case();

    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
