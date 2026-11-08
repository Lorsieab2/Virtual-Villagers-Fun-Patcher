/* Runtime harness for "VVFP Last Names.dll"'s Heathens (New Believers; the
   owner, 2026-11-08: "in vv5, please give heathens random last names
   thanks!!!! (they can share last names but be unrelated if there's not
   enough default ones in the list, but try to make them all unique)").
   32-bit only; tests/test_vv5_heathen_last_names.py builds and runs it.

   The companion's own source is included whole, so what runs here is the
   shipped choice and the shipped reading and writing of the Last Names
   record.  Only the "My Documents" folder is the harness's
   (SHGetSpecialFolderPathA answers the folder given on the command line), and
   the Parentage Export's WriteVillageRecord is a stand-in that keeps what it
   is handed.  The villager table is New Believers' own layout (0x2F44-byte
   records), 150 or 256 of them.

     1. A new Heathen gets a last name nobody has used: never a villager's in
        the game (tribe or Heathen), a "used" line's or a "heathen" line's;
        every free name reachable; the name kept as a "heathen" line.
     2. New Heathens one after another all get different names until the list
        is exhausted; then they share, and a shared name never repeats a
        living villager's full name when another would not.
     3. An existing Heathen with no last name is named at the load: each a
        different free name, a numeral kept after it, a "Name changed" record
        for each (the old name and age); believers, Heathens who have one, the
        dead and empty records are left alone; keyed "heathen" lines.
     4. A load whose session ended without a save: the same names again, and
        no new lines.
     5. "Random from the existing Village Names": a Heathen's last name is not
        drawn and not written as a "used" line; once converted it is.
     6. 256 Villagers: a Heathen in record 200 is named.
     7. A slot that cannot be told: named, nothing written; a record of
        another game is never replaced; a name with no room is left alone.
     8. A load with more nameless Heathens than the list has names: every
        name used once before any is shared.

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

    printf("1. A new Heathen gets a last name nobody has used\n");
    {
        int seen[FAMILIES] = { 0 }, bad = 0, reached = 0, lines_ok = 1;
        char base[2048];
        size_t n = strlen(head);
        memcpy(base, head, n);
        for (i = 10; i < 15; ++i) {
            n += (size_t)_snprintf(base + n, sizeof base - n, "used\t%s\n", g_last[i]);
        }
        for (i = 15; i < 20; ++i) {
            n += (size_t)_snprintf(base + n, sizeof base - n, "heathen\t%s\n", g_last[i]);
        }
        base[n] = '\0';
        for (k = 0; k < 900; ++k) {
            clear_table();
            for (i = 0; i < 5; ++i) {            /* the tribe: 0-4 */
                _snprintf(buf, sizeof buf, "Ago %s", g_last[i]);
                villager(i, buf, 0, 50);
            }
            for (i = 5; i < 10; ++i) {           /* living Heathens: 5-9 */
                _snprintf(buf, sizeof buf, "Pua %s", g_last[i]);
                villager(i, buf, 1, 50);
            }
            villager(20, "Tama", 1, 50);         /* the new Heathen, as the routine named them */
            put_record(base);
            if (!heathen_created(rec(20) + NB_VILLAGER, table, 150, 1)) {
                ++bad;
                continue;
            }
            {
                int at = last_index(name_of(20));
                char want[2100];
                if (at < 20) {
                    ++bad;
                } else {
                    seen[at] = 1;
                }
                _snprintf(want, sizeof want, "%sheathen\t%s\n", base, at >= 0 ? g_last[at] : "?");
                lines_ok &= strcmp(record_text(), want) == 0;
            }
        }
        for (i = 20; i < FAMILIES; ++i) {
            reached += seen[i];
        }
        check(bad == 0, "never a tribe member's, a living Heathen's, a used line's or a heathen line's");
        check(reached == 30, "every one of the 30 free names is drawn");
        check(lines_ok, "the record gains exactly \"heathen\\t<last name>\", every other line byte for byte");
        put_record(NULL);
        clear_table();
        villager(0, "Ago", 0, 50);
        villager(1, "Tama", 1, 50);
        heathen_created(rec(1) + NB_VILLAGER, table, 150, 1);
        _snprintf(buf, sizeof buf, "%sheathen\t%s\n", head, g_last[last_index(name_of(1)) < 0 ? 0 : last_index(name_of(1))]);
        check(last_index(name_of(1)) >= 0 && strcmp(record_text(), buf) == 0,
              "a village with no record yet: the record is made, its header and the line");
        strcpy(name_of(1), "Tama Kaab");
        check(!heathen_created(rec(1) + NB_VILLAGER, table, 150, 1) && strcmp(name_of(1), "Tama Kaab") == 0,
              "a name that already carries a last name is kept");
    }

    printf("2. New Heathens one after another, then the list is exhausted\n");
    {
        int seen[FAMILIES] = { 0 }, distinct = 0, ok = 1, shared_full = 0;
        put_record(head);
        clear_table();
        for (k = 0; k < FAMILIES; ++k) {
            villager(k, "Tama", 1, 50);
            heathen_created(rec(k) + NB_VILLAGER, table, 256, 1);
            i = last_index(name_of(k));
            if (i < 0 || seen[i]) {
                ok = 0;
            } else {
                seen[i] = 1;
                ++distinct;
            }
        }
        check(ok && distinct == FAMILIES, "50 new Heathens: 50 different last names");
        check(count_lines(record_text(), "heathen\t") == FAMILIES, "50 heathen lines");
        villager(60, "Tama", 1, 50);
        heathen_created(rec(60) + NB_VILLAGER, table, 256, 1);
        check(last_index(name_of(60)) >= 0, "the 51st still gets one: the list is exhausted, so they share");
        villager(61, "Pua", 1, 50);
        strcpy(name_of(0), "Pua Kaaa");             /* a living Pua Kaaa */
        for (k = 0; k < 400; ++k) {
            strcpy(name_of(61), "Pua");
            heathen_created(rec(61) + NB_VILLAGER, table, 256, 1);
            shared_full += strcmp(name_of(61), "Pua Kaaa") == 0;
        }
        check(shared_full == 0, "a shared last name never repeats a living villager's full name when another would not");
    }

    printf("3. Existing Heathens with no last name, named at the load\n");
    {
        int distinct = 1, taken_ok = 1, a, b;
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
        k = heathens_at_load(table, 150, 1);
        check(k == 3, "three Heathens named");
        for (a = 2; a <= 4; ++a) {
            i = last_index(name_of(a));
            taken_ok &= i >= 0 && i != 0 && i != 1 && i != 3;
            for (b = 2; b < a; ++b) {
                distinct &= last_index(name_of(b)) != i;
            }
        }
        check(taken_ok, "never a living villager's or a used line's");
        check(distinct, "each a different one");
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

    printf("4. A load whose session ended without a save\n");
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
        /* two nameless Heathens with the same name and looks share no keyed line */
        villager(10, "Tama", 1, 50);
        *(int *)(rec(10) + NB_HEAD) = 2;
        *(int *)(rec(10) + NB_BODY) = 2;
        strcpy(name_of(2), "Tama");
        heathens_at_load(table, 150, 1);
        check(last_index(name_of(10)) >= 0 && last_index(name_of(10)) != last_index(name_of(2)),
              "a namesake with the same looks gets a name of their own");
    }

    printf("5. Random from the existing Village Names: not a Heathen's until they convert\n");
    {
        int heathen_name = 0, other = 0, kaab = 0, after = 0;
        char name[0x18];
        _snprintf(buf, sizeof buf, "%srule\tvillage\n", head);
        put_record(buf);
        clear_table();
        villager(0, "Ana Kaab", 0, 50);
        villager(1, "Tama Kazz", 1, 50);           /* a Heathen */
        strcpy(name_of(1), "Tama Kabx");
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

    printf("6. 256 Villagers\n");
    {
        put_record(head);
        clear_table();
        villager(200, "Tama", 1, 50);
        heathens_at_load(table, 150, 1);
        check(strcmp(name_of(200), "Tama") == 0, "150 records: record 200 is not one of them");
        heathens_at_load(table, 256, 1);
        check(last_index(name_of(200)) >= 0, "256 records: the Heathen in record 200 is named");
    }

    printf("7. No slot, another game's record, no room\n");
    {
        put_record(NULL);
        clear_table();
        villager(0, "Tama", 1, 50);
        heathens_at_load(table, 150, 0);
        check(last_index(name_of(0)) >= 0 && GetFileAttributesA(g_path) == INVALID_FILE_ATTRIBUTES,
              "a slot that cannot be told: named, nothing written");
        put_record("VVFP LAST NAMES v1 game=4\nrule\tfather\n");
        strcpy(name_of(0), "Tama");
        heathens_at_load(table, 150, 1);
        check(last_index(name_of(0)) >= 0 && strcmp(record_text(), "VVFP LAST NAMES v1 game=4\nrule\tfather\n") == 0,
              "a record that is not this game's is never replaced");
        put_record(head);
        villager(1, "Abcdefghijklmnopqrst", 1, 50);   /* 20 letters: " Kaxx" would not fit 23 */
        heathens_at_load(table, 150, 1);
        check(strcmp(name_of(1), "Abcdefghijklmnopqrst") == 0, "a name with no room for a last name is left alone");
    }

    printf("8. More nameless Heathens than names\n");
    {
        int uses[FAMILIES] = { 0 }, ok = 1;
        put_record(head);
        clear_table();
        for (i = 0; i < 70; ++i) {
            _snprintf(buf, sizeof buf, "H%c%c", 'a' + i / 26, 'a' + i % 26);
            villager(i, buf, 1, 50);
        }
        k = heathens_at_load(table, 150, 1);
        for (i = 0; i < 70; ++i) {
            int at = last_index(name_of(i));
            if (at < 0) {
                ok = 0;
            } else {
                ++uses[at];
                if (i < FAMILIES && uses[at] > 1) {
                    ok = 0;                        /* shared before the list ran out */
                }
            }
        }
        check(k == 70 && ok, "all 70 named, the first 50 each a different name, then shared");
    }

    DeleteFileA(g_path);
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures ? 1 : 0;
}
