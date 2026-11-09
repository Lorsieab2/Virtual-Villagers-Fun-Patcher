/* Runtime harness for "VVFP Last Names.dll"'s Heathens (New Believers).  The
   owner, 2026-11-08: "in vv5, please give heathens random last names" -- and
   2026-11-09: "among the entire heathen tribe they should have like... maybe
   4-5 unique last names from the defaults list that don't overlap with the
   villagers' last names": always four family names per village, each Heathen
   one of them at random, roughly even.  32-bit only;
   tests/test_vv5_heathen_last_names.py builds and runs it.

   The companion's own source is included whole, so what runs here is the
   shipped choice and the shipped reading and writing of the Last Names
   record.  Only the "My Documents" folder is the harness's
   (SHGetSpecialFolderPathA answers the folder given on the command line), and
   the Parentage Export's WriteVillageRecord and the owners' batch are
   stand-ins that keep what they are handed.  The villager table is New
   Believers' own layout (0x2F44-byte records), 150 or 256 of them.

     1. A village's four family names: chosen once, at random, from the list,
        never a believer's last name or a "used" line's (a Heathen's own may
        be one); kept as four "family" lines; every free name reachable.
     2. Roughly even: a new village's 28 Heathens, over many villages, carry
        all four, none far ahead.
     3. The same four after a reload; Start Over (the record gone) chooses
        four of the new village's own.
     4. Fewer than four free names: the rest are others of the list, four
        different names still.
     5. Existing Heathens with no last name, named at the load: a family name
        each, a numeral kept after it, a "Name changed" record for each, the
        owners handed one batch; believers, Heathens who have one, the dead
        and empty records left alone; keyed "heathen" lines.
     6. A load whose session ended without a save: the same names again, no
        new lines; a later load names nobody and hands the batch over again.
     7. "Random from the existing Village Names": a Heathen's last name is not
        drawn and not written as a "used" line; once converted it is.
     8. 256 Villagers; a slot that cannot be told (the four kept for the
        session, written once it can be); another game's record; no room.
     9. The owners' rename pairs: [A, A, B, C, A] gives no A mapping.
    10. A Heathen's own rule follows the rename (never a believer's line).

   Exit code 0 when every check passes. */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>

static char g_docs[MAX_PATH];

static BOOL harness_docs(HWND owner, LPSTR path, int folder, BOOL create) {
    (void)owner;
    (void)folder;
    (void)create;
    lstrcpynA(path, g_docs, MAX_PATH);
    return TRUE;
}
#define SHGetSpecialFolderPathA harness_docs

/* The owners' VvfpVillagersRenamed (native/shared/villager_rekey.h): every batch handed over, kept. */
static int told_batches, told_count, told_slot;
static const void *told_records[256];
static char told_old[256][64];
static void harness_tell(int slot, int count, const void *const *records, const char *const *old_names) {
    int i;
    ++told_batches;
    told_slot = slot;
    told_count = count;
    for (i = 0; i < count && i < 256; ++i) {
        told_records[i] = records[i];
        lstrcpynA(told_old[i], old_names[i], 64);
    }
}
#define LN_TELL_OWNERS harness_tell

/* The game's own save slot, as the harness says it is (the companion reads the save manager's field). */
static int harness_slot;
static int harness_current_slot(void) { return harness_slot; }
#define LN_CURRENT_SLOT harness_current_slot

#include "vvfp_last_names.c"

static int failures;
static int checks;
static unsigned char *table;           /* 256 records */

static void check(int ok, const char *what) {
    ++checks;
    printf("  %s %s\n", ok ? "ok  " : "FAIL", what);
    failures += !ok;
}

/* The Parentage Export's WriteVillageRecord, kept. */
static int written;
static char written_before[8][128];

static int __stdcall fake_write(int game, int kind, const void *record, int check_it, const char *before,
                                const char *after, int detail) {
    (void)record;
    (void)after;
    if (game == 5 && kind == 10 && check_it == 1 && detail == 1 && before != NULL) {
        if (written < 8) {
            lstrcpynA(written_before[written], before, sizeof written_before[0]);
        }
        ++written;
    }
    return 1;
}

static unsigned char *rec(int i) { return table + (size_t)i * NB_STRIDE; }
static char *name_of(int i) { return (char *)(rec(i) + NB_NAME); }

static void villager(int i, const char *name, int heathen, int health) {
    unsigned char *r = rec(i);
    memset(r, 0, NB_STRIDE);
    r[NB_ACTIVE] = 1;
    r[NB_FACTION] = (unsigned char)heathen;
    *(int *)(r + NB_HEALTH) = health;
    *(int *)(r + NB_AGE) = 300 + i;
    *(int *)(r + NB_HEAD) = i % 7;
    *(int *)(r + NB_BODY) = i % 5;
    memcpy(r + NB_NAME, name, strlen(name) + 1);
}

static void clear_table(void) { memset(table, 0, (size_t)256 * NB_STRIDE); }

static char g_path[MAX_PATH * 2];

static void put_record(const char *text) {
    FILE *f;
    if (text == NULL) {
        DeleteFileA(g_path);
        return;
    }
    vv_ps_make_parents_a(g_path);
    f = fopen(g_path, "wb");
    fputs(text, f);
    fclose(f);
}

static const char *record_text(void) {
    static char text[RULE_FILE_MAX + 1];
    FILE *f = fopen(g_path, "rb");
    size_t n = 0;
    text[0] = '\0';
    if (f != NULL) {
        n = fread(text, 1, RULE_FILE_MAX, f);
        fclose(f);
    }
    text[n] = '\0';
    return text;
}

static int count_lines(const char *text, const char *prefix) {
    int n = 0;
    const char *p = text;
    size_t k = strlen(prefix);
    while (p != NULL && *p != '\0') {
        n += strncmp(p, prefix, k) == 0;
        p = strchr(p, '\n');
        p = p ? p + 1 : NULL;
    }
    return n;
}

/* The list index of the last word of `name` (a numeral passed over), or -1. */
static int last_index(const char *name) {
    char last[LONGEST_LAST + 1];
    int i;
    carried_last(name, last);
    for (i = 0; i < FAMILIES; ++i) {
        if (last[0] != '\0' && strcmp(g_last[i], last) == 0) {
            return i;
        }
    }
    return -1;
}

/* The record's "family" lines as list indexes (out[4]); returns how many. */
static int families_in_file(int *out) {
    const char *p = record_text();
    int n = 0;
    while (p != NULL && *p != '\0') {
        if (strncmp(p, "family\t", 7) == 0 && n < 8) {
            char last[LONGEST_LAST + 1];
            size_t len = strcspn(p + 7, "\r\n");
            int i;
            memcpy(last, p + 7, len < LONGEST_LAST ? len : LONGEST_LAST);
            last[len < LONGEST_LAST ? len : LONGEST_LAST] = '\0';
            for (i = 0; i < FAMILIES && strcmp(g_last[i], last) != 0; ++i) {
            }
            out[n++ % 8] = i < FAMILIES ? i : -1;
        }
        p = strchr(p, '\n');
        p = p ? p + 1 : NULL;
    }
    return n;
}

static int in_set(int at, const int *set, int n) {
    int k;
    for (k = 0; k < n; ++k) {
        if (set[k] == at && at >= 0) {
            return 1;
        }
    }
    return 0;
}

/* A new village: the 28 Heathens the game makes, one after another (records 10..37). */
static void new_village_heathens(int count) {
    int i;
    char name[16];
    for (i = 0; i < count; ++i) {
        _snprintf(name, sizeof name, "H%c%c", 'a' + i / 26, 'a' + i % 26);
        villager(10 + i, name, 1, 50);
        heathen_created(rec(10 + i) + NB_VILLAGER, table, 150, 1);
    }
}

int main(int argc, char **argv) {
    char head[64], buf[4096];
    int i, k;
    if (argc < 2) {
        printf("usage: heathen_names_harness <documents folder>\n");
        return 2;
    }
    lstrcpynA(g_docs, argv[1], MAX_PATH);
    CreateDirectoryA(g_docs, NULL);
    table = (unsigned char *)VirtualAlloc(NULL, (size_t)256 * NB_STRIDE, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    g_game = 5;
    install_state = 1;
    for (i = 0; i < FAMILIES; ++i) {         /* no letter of a Roman numeral but the K */
        _snprintf(g_last[i], sizeof g_last[i], "Ka%c%c", 'a' + i / 26, 'a' + i % 26);
    }
    g_write_village_record_looked = 1;
    g_write_village_record = fake_write;
    record_path(1, g_path, sizeof g_path);
    _snprintf(head, sizeof head, "VVFP LAST NAMES v1 game=5\n");

    printf("1. A village's four family names\n");
    {
        int seen[FAMILIES] = { 0 }, bad = 0, reached = 0, four = 1, theirs = 1, fam[8];
        char base[2048];
        size_t n = strlen(head);
        memcpy(base, head, n);
        for (i = 10; i < 15; ++i) {
            n += (size_t)_snprintf(base + n, sizeof base - n, "used\t%s\n", g_last[i]);
        }
        base[n] = '\0';
        for (k = 0; k < 400; ++k) {
            int f;
            clear_table();
            for (i = 0; i < 5; ++i) {            /* the tribe: 0-4 */
                _snprintf(buf, sizeof buf, "Ago %s", g_last[i]);
                villager(i, buf, 0, 50);
            }
            villager(5, "Pua Kaap", 1, 50);       /* an earlier build's Heathen, with a name of their own */
            villager(20, "Tama", 1, 50);         /* the new Heathen, as the routine named them */
            put_record(base);
            heathen_created(rec(20) + NB_VILLAGER, table, 150, 1);
            f = families_in_file(fam);
            four &= f == 4 && strncmp(record_text(), base, strlen(base)) == 0;
            for (i = 0; i < f && i < 4; ++i) {
                if (fam[i] < 5 || (fam[i] >= 10 && fam[i] < 15) || in_set(fam[i], fam, i)) {
                    ++bad;
                } else {
                    seen[fam[i]] = 1;
                }
            }
            theirs &= in_set(last_index(name_of(20)), fam, f);
        }
        for (i = 0; i < FAMILIES; ++i) {
            reached += seen[i];
        }
        check(four, "four \"family\" lines are added once, every other line byte for byte");
        check(bad == 0, "four different names, never a believer's last name or a used line's");
        check(reached == 40, "every one of the 40 free names is chosen in some village (a Heathen's own may be)");
        check(theirs, "the new Heathen carries one of the four");
        put_record(NULL);
        clear_table();
        villager(0, "Ago", 0, 50);
        villager(1, "Tama", 1, 50);
        heathen_created(rec(1) + NB_VILLAGER, table, 150, 1);
        check(families_in_file(fam) == 4 && strncmp(record_text(), head, strlen(head)) == 0,
              "a village with no record yet: the record is made, its header and the four");
        strcpy(name_of(1), "Tama Kaab");
        check(!heathen_created(rec(1) + NB_VILLAGER, table, 150, 1) && strcmp(name_of(1), "Tama Kaab") == 0,
              "a name that already carries a last name is kept");
    }

    printf("2. Roughly even\n");
    {
        int empty = 0, huge = 0, outside = 0, villages = 300, least = 28, most = 0;
        for (k = 0; k < villages; ++k) {
            int fam[8], per[4] = { 0 }, f, j;
            put_record(head);
            clear_table();
            new_village_heathens(28);
            f = families_in_file(fam);
            for (i = 0; i < 28; ++i) {
                int at = last_index(name_of(10 + i));
                for (j = 0; j < f && j < 4 && fam[j] != at; ++j) {
                }
                if (j < 4 && j < f) {
                    ++per[j];
                } else {
                    ++outside;
                }
            }
            for (j = 0; j < 4; ++j) {
                empty += per[j] == 0;
                huge += per[j] > 10;
                least = per[j] < least ? per[j] : least;
                most = per[j] > most ? per[j] : most;
            }
        }
        printf("  (28 Heathens in 4 families, %d villages: from %d to %d in a family)\n", villages, least, most);
        check(outside == 0, "every Heathen of a new village carries one of its four");
        check(empty == 0, "no family is ever empty");
        check(huge == 0, "none has more than 10 of 28 (7 is even)");
    }

    printf("3. The same four after a reload; Start Over\n");
    {
        int fam[8], again[8], f, g, same = 1, ok = 1;
        put_record(head);
        clear_table();
        new_village_heathens(28);
        f = families_in_file(fam);
        g_family_count = 0;                        /* a new session: nothing in memory */
        g_family_session_slot = -1;
        villager(60, "Lani", 1, 50);               /* a barrel's Heathen baby, later */
        heathen_created(rec(60) + NB_VILLAGER, table, 150, 1);
        g = families_in_file(again);
        for (i = 0; i < 4; ++i) {
            same &= fam[i] == again[i];
        }
        check(f == 4 && g == 4 && same, "the record keeps the same four: none chosen again");
        check(in_set(last_index(name_of(60)), fam, 4), "a later Heathen carries one of the same four");
        {
            int differs = 0;
            for (k = 0; k < 30 && ok; ++k) {       /* Start Over deletes the record with the village */
                int fresh[8];
                put_record(NULL);
                clear_table();
                new_village_heathens(4);
                ok = families_in_file(fresh) == 4;
                for (i = 0; i < 4 && ok; ++i) {
                    differs |= !in_set(fresh[i], fam, 4);
                }
            }
            check(ok && differs, "Start Over: each new village chooses four of its own");
        }
    }

    printf("4. Fewer than four free names\n");
    {
        int fam[8], f, distinct = 1, free_ones = 0;
        put_record(head);
        clear_table();
        for (i = 0; i < 48; ++i) {                 /* believers carry 48 of the 50 */
            _snprintf(buf, sizeof buf, "Ago %s", g_last[i]);
            villager(i % 150, buf, 0, 50);
        }
        villager(100, "Tama", 1, 50);
        heathen_created(rec(100) + NB_VILLAGER, table, 150, 1);
        f = families_in_file(fam);
        for (i = 0; i < f; ++i) {
            distinct &= fam[i] >= 0 && !in_set(fam[i], fam, i);
            free_ones += fam[i] >= 48;
        }
        check(f == 4 && distinct && free_ones == 2, "the two free names and two others of the list: four different");
    }

    printf("5. Existing Heathens with no last name, named at the load\n");
    {
        int fam[8], all_family = 1;
        const char *text;
        _snprintf(buf, sizeof buf, "%srule\tfather\nused\t%s\n", head, g_last[3]);
        put_record(buf);
        clear_table();
        villager(0, "Ago Kaaa", 0, 50);            /* believers */
        villager(1, "Lupa", 0, 50);                /* a believer with none: not a Heathen */
        villager(2, "Tama", 1, 50);                /* nameless Heathens */
        villager(3, "Kai II", 1, 50);
        villager(4, "Mele", 1, 50);
        villager(5, "Lono Kaab", 1, 50);           /* has one */
        villager(6, "Hoku", 1, 0);                 /* dead */
        villager(7, "Nalu", 1, 50);
        rec(7)[NB_ACTIVE] = 0;                     /* an empty record */
        written = 0;
        told_batches = 0;
        k = heathens_at_load(table, 150, 1);
        check(k == 3, "three Heathens named");
        check(told_batches == 1 && told_slot == 1 && told_count == 3 && told_records[0] == rec(2)
              && told_records[1] == rec(3) && told_records[2] == rec(4) && strcmp(told_old[0], "Tama") == 0
              && strcmp(told_old[1], "Kai II") == 0 && strcmp(told_old[2], "Mele") == 0,
              "the owners are handed one batch: the renamed records and the names they had");
        check(families_in_file(fam) == 4 && !in_set(0, fam, 4) && !in_set(3, fam, 4),
              "the village's four: never the believer's last name or the used line's");
        for (i = 2; i <= 4; ++i) {
            all_family &= in_set(last_index(name_of(i)), fam, 4);
        }
        check(all_family, "each renamed Heathen carries one of the four");
        _snprintf(buf, sizeof buf, "Kai %s II", g_last[last_index(name_of(3)) < 0 ? 0 : last_index(name_of(3))]);
        check(strcmp(name_of(3), buf) == 0, "the numeral is kept after the last name (Kai <last> II)");
        check(strcmp(name_of(0), "Ago Kaaa") == 0 && strcmp(name_of(1), "Lupa") == 0
              && strcmp(name_of(5), "Lono Kaab") == 0 && strcmp(name_of(6), "Hoku") == 0
              && strcmp(name_of(7), "Nalu") == 0,
              "believers, a Heathen who has one, the dead and an empty record are left alone");
        check(written == 3 && strcmp(written_before[0], "  Old name: Tama\n  Age: 302\n") == 0
              && strcmp(written_before[1], "  Old name: Kai II\n  Age: 303\n") == 0,
              "a Name changed record for each: the old name and the age");
        text = record_text();
        _snprintf(buf, sizeof buf, "heathen\t%s\tTama\t2\t2\n", g_last[last_index(name_of(2))]);
        check(count_lines(text, "heathen\t") == 3 && strstr(text, buf) != NULL && strstr(text, "rule\tfather\n") != NULL,
              "keyed heathen lines (the name, head and body they had), the rest of the record kept");
    }

    printf("6. A load whose session ended without a save\n");
    {
        char before_text[4096], names[3][32];
        lstrcpynA(before_text, record_text(), sizeof before_text);
        for (i = 0; i < 3; ++i) {
            lstrcpynA(names[i], name_of(2 + i), sizeof names[i]);
        }
        strcpy(name_of(2), "Tama");
        strcpy(name_of(3), "Kai II");
        strcpy(name_of(4), "Mele");
        written = 0;
        k = heathens_at_load(table, 150, 1);
        check(k == 3 && strcmp(name_of(2), names[0]) == 0 && strcmp(name_of(3), names[1]) == 0
              && strcmp(name_of(4), names[2]) == 0, "the same three names again");
        check(strcmp(record_text(), before_text) == 0, "no new line");
        check(written == 3, "the Name changed records again (the first ones were never saved)");
        told_batches = 0;
        written = 0;
        k = heathens_at_load(table, 150, 1);       /* a later load: the save already has the names */
        check(k == 0 && written == 0 && told_batches == 1 && told_count == 3 && strcmp(told_old[0], "Tama") == 0
              && told_records[0] == rec(2),
              "a later load names nobody, and hands the owners the earlier renames again");
        /* two nameless Heathens with the same name and looks: each their own keyed line, each a family name */
        villager(10, "Tama", 1, 50);
        *(int *)(rec(10) + NB_HEAD) = 2;
        *(int *)(rec(10) + NB_BODY) = 2;
        strcpy(name_of(2), "Tama");
        told_batches = 0;
        heathens_at_load(table, 150, 1);
        {
            int fam[8];
            families_in_file(fam);
            check(strcmp(name_of(2), names[0]) == 0 && in_set(last_index(name_of(10)), fam, 4)
                  && count_lines(record_text(), "heathen\t") == 4,
                  "a namesake with the same looks: the first keeps their line, the second gets a family name and a line");
        }
    }

    printf("7. Random from the existing Village Names: not a Heathen's until they convert\n");
    {
        int heathen_name = 0, other = 0, kaab = 0, after = 0;
        char name[0x18];
        _snprintf(buf, sizeof buf, "%srule\tvillage\n", head);
        put_record(buf);
        clear_table();
        villager(0, "Ana Kaab", 0, 50);
        villager(1, "Tama Kabx", 1, 50);           /* a Heathen */
        for (k = 0; k < 300; ++k) {
            memset(name, 0, sizeof name);
            memcpy(name, "Kid Akikai", 10);
            /* the mother is the Heathen herself (the Heathen Mommy's child) */
            VvfpRuleLastName3(name, 0x18, "Ago", 5, 6, "Tama Kabx", 7, 8, 1, table, NB_STRIDE, 150, NB_ACTIVE, NB_NAME,
                              NB_NAME_CAP);
            heathen_name += strcmp(name, "Kid Kabx") == 0;
            kaab += strcmp(name, "Kid Kaab") == 0;
            other += strcmp(name, "Kid Kabx") != 0 && strcmp(name, "Kid Kaab") != 0;
        }
        check(heathen_name == 0 && kaab == 300 && other == 0,
              "a Heathen's last name is never drawn, not even when she is the mother");
        check(strstr(record_text(), "used\tKabx") == NULL, "nor written as a used line");
        rec(1)[NB_FACTION] = 0;                    /* converted: the name kept */
        for (k = 0; k < 300; ++k) {
            memset(name, 0, sizeof name);
            memcpy(name, "Kid Akikai", 10);
            VvfpRuleLastName3(name, 0x18, "Ago", 5, 6, "Aipi", 7, 8, 1, table, NB_STRIDE, 150, NB_ACTIVE, NB_NAME, NB_NAME_CAP);
            after += strcmp(name, "Kid Kabx") == 0;
        }
        check(after > 100 && after < 200, "once converted, theirs is drawn like any other");
        check(strstr(record_text(), "used\tKabx\n") != NULL, "and kept as a used line");
    }

    printf("8. 256 Villagers, no slot, another game's record, no room\n");
    {
        int fam[8], session[4];
        put_record(head);
        clear_table();
        villager(200, "Tama", 1, 50);
        heathens_at_load(table, 150, 1);
        check(strcmp(name_of(200), "Tama") == 0, "150 records: record 200 is not one of them");
        heathens_at_load(table, 256, 1);
        check(last_index(name_of(200)) >= 0, "256 records: the Heathen in record 200 is named");
        put_record(NULL);
        clear_table();
        g_family_count = 0;
        g_family_session_slot = -1;
        villager(0, "Tama", 1, 50);
        villager(1, "Pua", 1, 50);
        told_batches = 0;
        heathens_at_load(table, 150, 0);
        check(last_index(name_of(0)) >= 0 && GetFileAttributesA(g_path) == INVALID_FILE_ATTRIBUTES
              && told_batches == 0, "a slot that cannot be told: named, nothing written, no owner told");
        for (i = 0; i < 4; ++i) {
            for (k = 0; k < FAMILIES && strcmp(g_last[k], g_family[i]) != 0; ++k) {
            }
            session[i] = k;
        }
        villager(2, "Hina", 1, 50);
        heathen_created(rec(2) + NB_VILLAGER, table, 150, 1);   /* the slot is known now */
        check(families_in_file(fam) == 4 && fam[0] == session[0] && fam[3] == session[3]
              && in_set(last_index(name_of(0)), fam, 4),
              "the four chosen before the slot was known are the ones kept once it is");
        put_record("VVFP LAST NAMES v1 game=4\nrule\tfather\n");
        strcpy(name_of(0), "Tama");
        heathens_at_load(table, 150, 1);
        check(last_index(name_of(0)) >= 0 && strcmp(record_text(), "VVFP LAST NAMES v1 game=4\nrule\tfather\n") == 0,
              "a record that is not this game's is never replaced");
        put_record(head);
        villager(3, "Abcdefghijklmnopqrst", 1, 50);   /* 20 letters: " Kaxx" would not fit 23 */
        heathens_at_load(table, 150, 1);
        check(strcmp(name_of(3), "Abcdefghijklmnopqrst") == 0, "a name with no room for a last name is left alone");
    }

    printf("9. The owners' rename pairs (native/shared/villager_rekey.h)\n");
    {
        unsigned int from[5] = { 0xA, 0xA, 0xB, 0xC, 0xA }, to[5] = { 1, 2, 3, 4, 5 };
        unsigned int ids[3] = { 0xA, 0xB, 0xC };
        int kept;
        vv_rekey_count = 0;
        kept = vv_rekey_note(1, from, to, 5);
        check(kept == 2 && from[0] == 0xB && to[0] == 3 && from[1] == 0xC && to[1] == 4,
              "[A, A, B, C, A]: B and C are kept, in order");
        check(vv_rekey_follow(1, 0xA) == 0xA && vv_rekey_apply(1, ids, 3) == 2 && ids[0] == 0xA && ids[1] == 3
              && ids[2] == 4, "and no A mapping: what three villagers were goes to none of them");
        vv_rekey_count = 0;
    }

    printf("10. A Heathen's own rule follows the rename\n");
    {
        static char want[RULE_FILE_MAX + 1];
        char rule[8];
        const char *text;
        clear_table();
        villager(2, "Tama", 1, 50);
        villager(4, "Pua", 1, 50);
        villager(5, "Pua", 0, 50);                 /* a believer with the Heathen's name and looks */
        *(int *)(rec(5) + NB_HEAD) = *(int *)(rec(4) + NB_HEAD);
        *(int *)(rec(5) + NB_BODY) = *(int *)(rec(4) + NB_BODY);
        _snprintf(buf, sizeof buf, "%srule\tfather\nvillager\tTama\t2\t2\tM\tmother\nvillager\tPua\t4\t4\tM\tlist\n",
                  head);
        put_record(buf);
        heathens_at_load(table, 150, 1);
        text = record_text();
        _snprintf(want, sizeof want, "villager\t%s\t2\t2\tM\tmother\n", name_of(2));
        check(strstr(text, want) != NULL && strstr(text, "villager\tTama\t2\t2\tM\tmother\n") == NULL,
              "the Heathen's own rule is under their new name, the rest of the line as it was");
        check(strstr(text, "villager\tPua\t4\t4\tM\tlist\n") != NULL,
              "a line a believer outside the batch still is (name, looks, sex) is left as it is");
        check(read_record(1, rule, sizeof rule) && own_rule(name_of(2), 2, 2, 'M') == 'm',
              "the rule is theirs at a birth: own_rule finds it by the new name");
        lstrcpynA(want, record_text(), sizeof want);
        heathens_at_load(table, 150, 1);
        check(strcmp(record_text(), want) == 0, "a later load carries nothing more");
    }

    printf("11. Four chosen before the slot was known are written once it is (Codex, #743)\n");
    {
        int fam[8], again[8], same = 1, f;
        char memory[4][LONGEST_LAST + 1];
        put_record(NULL);
        clear_table();
        g_family_count = 0;
        g_family_session_slot = -1;
        harness_slot = 0;
        for (i = 0; i < 4; ++i) {                  /* a new village's Heathens, its slot not known yet */
            _snprintf(buf, sizeof buf, "H%c", 'a' + i);
            villager(10 + i, buf, 1, 50);
            heathen_created(rec(10 + i) + NB_VILLAGER, table, 150, 0);
        }
        for (i = 0; i < 4; ++i) {
            lstrcpynA(memory[i], g_family[i], sizeof memory[i]);
        }
        f = GetFileAttributesA(g_path) == INVALID_FILE_ATTRIBUTES;
        harness_slot = 1;                          /* the game names the slot; no Heathen is named */
        families_flush_pending();
        check(f && families_in_file(fam) == 4 && strcmp(g_last[fam[0]], memory[0]) == 0
              && strcmp(g_last[fam[3]], memory[3]) == 0,
              "nothing written while the slot is unknown; the four are written as soon as it is known");
        g_family_count = 0;                        /* the next session */
        g_family_session_slot = -1;
        harness_slot = 0;
        villager(20, "Lani", 1, 50);
        heathen_created(rec(20) + NB_VILLAGER, table, 150, 1);
        families_in_file(again);
        for (i = 0; i < 4; ++i) {
            same &= fam[i] == again[i];
        }
        check(same && count_lines(record_text(), "family\t") == 4, "a reload keeps the same four");
        check(in_set(last_index(name_of(20)), fam, 4) && in_set(last_index(name_of(10)), fam, 4),
              "the saved Heathens and a later one carry the same four");
    }

    printf("12. A lost record never splits the tribe (Codex, #743)\n");
    {
        static const int carried[11] = { 1, 1, 1, 1, 2, 2, 2, 3, 3, 4, 5 };   /* Kaab x4, Kaac x3, ... */
        int fam[8];
        put_record(NULL);
        clear_table();
        g_family_count = 0;
        g_family_session_slot = -1;
        villager(0, "Ago Kaag", 0, 50);            /* a believer */
        for (i = 0; i < 11; ++i) {
            _snprintf(buf, sizeof buf, "H%c %s", 'a' + i, g_last[carried[i]]);
            villager(1 + i, buf, 1, 50);
        }
        k = heathens_at_load(table, 150, 1);
        check(k == 0 && families_in_file(fam) == 4 && fam[0] == 1 && fam[1] == 2 && fam[2] == 3 && fam[3] == 4,
              "the four are the Heathens' own names, the most carried first: written at the load");
        villager(30, "Lani", 1, 50);
        heathen_created(rec(30) + NB_VILLAGER, table, 150, 1);
        check(in_set(last_index(name_of(30)), fam, 4) && families_in_file(fam) == 4,
              "a later Heathen carries one of them, and none is chosen anew");
    }

    DeleteFileA(g_path);
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures ? 1 : 0;
}
