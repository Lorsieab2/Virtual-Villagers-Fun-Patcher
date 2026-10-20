/* Runtime harness for "VVFP Last Names.dll"'s VvfpRuleLastName2: the last
   name a baby takes by the village's rule and each parent's own rule (the
   owner, 2026-10-09).  32-bit only; tests/test_last_names_own_rules.py builds
   and runs it.

   The companion's own source is included whole, so what runs here is the
   shipped reading of the Last Names record and the shipped choice.  Only the
   "My Documents" folder is the harness's: SHGetSpecialFolderPathA answers the
   folder given on the command line, so every record is written under it and
   nothing under Documents\LDW.

     1. Every combination of the father's own rule (none, father, mother,
        50:50), the mother's own rule (the same four) and the village's rule
        (none, father, mother, 50:50, "Random from list"): one parent's own
        rule decides; both parents' when they agree; the village's when they
        disagree or neither has one; nothing changes when no rule decides.
     2. A parent's own rule is theirs only by name, head, body AND sex: a
        namesake with other looks, a parent whose looks are unknown, or a
        line for the other sex is not theirs.
     3. A name kept in UTF-8 in the record (Élodie) is the game's Latin-1.
     4. A record without "villager" lines (an earlier build's) works as before.
     5. Head 0 and body 0 are real looks; only a negative look is unknown.
     6. VvfpRelookLastName: a change of looks copies exactly the matching
        line (name, sex, old looks) to the new looks right after it (the old
        line stays for a child already conceived), through a temporary file;
        with slot 0 the slot is the save that holds the name.
     7. "From the father" / "From the mother" give that parent's last name
        only: none when that known parent has none, never the other's.
     8. A village with no rule recorded (no file, or no rule line) -- or a
        birth whose village cannot be told -- uses "From the father", in
        every game; "list" and "each" still change nothing.
     9. The record in the save's own folder.
    10. A parent's own "Random last name from the list": every child a name
        of the list, all 50 reachable and evenly drawn (chi-square), twins
        each their own draw; disagreeing parents use the village's rule; an
        unknown rule code is no rule.
    11. 50:50 is a fair draw for each child, twins born in the same tick too.
    12. "From the mother" is the mother's: triplets, a renamed or numbered
        mother, a mother with no last name, an unknown mother, own rules.

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

static char g_path[MAX_PATH * 2];

static void record(const char *rule, const char *lines) {
    FILE *f = fopen(g_path, "wb");
    if (f == NULL) {
        printf("  FAIL cannot write %s\n", g_path);
        exit(2);
    }
    fprintf(f, "VVFP LAST NAMES v1 game=%d\n", g_game);
    if (rule != NULL) {
        fprintf(f, "rule\t%s\n", rule);
    }
    fputs(lines, f);
    fclose(f);
}

/* The baby's name after the rule: "Kid <last>" or "Kid Akikai" unchanged. */
static const char *born(const char *father, int fh, int fb, const char *mother, int mh, int mb) {
    static char name[24];
    strcpy(name, "Kid Akikai");
    VvfpRuleLastName2(name, sizeof name, father, fh, fb, mother, mh, mb, 1);
    return name;
}

static void check(int ok, const char *what) {
    ++checks;
    printf("  %s %s\n", ok ? "ok  " : "FAIL", what);
    failures += !ok;
}

static const char *const OWN[4] = { NULL, "father", "mother", "random" };
static const char *const VILLAGE[5] = { NULL, "father", "mother", "random", "list" };

int main(int argc, char **argv) {
    char folder[MAX_PATH * 2], exe[MAX_PATH], *base, *dot;
    int f, m, v, k;
    if (argc < 2) {
        printf("usage: last_names_harness <documents folder>\n");
        return 2;
    }
    lstrcpynA(g_docs, argv[1], MAX_PATH);
    GetModuleFileNameA(NULL, exe, MAX_PATH);
    base = strrchr(exe, '\\');
    base = base ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot) {
        *dot = '\0';
    }
    _snprintf(folder, sizeof folder, "%s\\LDW\\%s\\Virtual Villagers Fun Patcher Data\\Last Names", g_docs, base);
    SHCreateDirectoryExA(NULL, folder, NULL);
    _snprintf(g_path, sizeof g_path, "%s\\Virtual Villagers 3 Last Names - Save 1.dat", folder);
    g_game = 3;
    install_state = 1;

    printf("1. Every combination of the parents' own rules and the village's\n");
    for (f = 0; f < 4; ++f) {
        for (m = 0; m < 4; ++m) {
            for (v = 0; v < 5; ++v) {
                char lines[256], what[160];
                const char *decided, *got;
                lines[0] = '\0';
                if (OWN[f]) {
                    _snprintf(lines, sizeof lines, "villager\tAgo Bahati\t5\t6\tM\t%s\n", OWN[f]);
                }
                if (OWN[m]) {
                    size_t n = strlen(lines);
                    _snprintf(lines + n, sizeof lines - n, "villager\tAipi Wanjiko\t7\t8\tF\t%s\n", OWN[m]);
                }
                record(VILLAGE[v], lines);
                decided = OWN[f] && OWN[m] ? (strcmp(OWN[f], OWN[m]) == 0 ? OWN[f] : VILLAGE[v])
                          : OWN[f] ? OWN[f] : OWN[m] ? OWN[m] : VILLAGE[v];
                if (decided == NULL) {
                    decided = "father";             /* no village rule: DEFAULT_RULE */
                }
                _snprintf(what, sizeof what, "father %-6s mother %-6s village %-6s -> %s",
                          OWN[f] ? OWN[f] : "-", OWN[m] ? OWN[m] : "-", VILLAGE[v] ? VILLAGE[v] : "-",
                          decided ? decided : "-");
                if (decided && strcmp(decided, "random") == 0) {
                    int dad = 0, mum = 0;
                    for (k = 0; k < 64; ++k) {
                        got = born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8);
                        dad += strcmp(got, "Kid Bahati") == 0;
                        mum += strcmp(got, "Kid Wanjiko") == 0;
                        Sleep(k % 3 == 0 ? 16 : 0);
                    }
                    check(dad + mum == 64 && dad > 0 && mum > 0, what);
                } else {
                    got = born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8);
                    check(strcmp(got, decided == NULL || strcmp(decided, "list") == 0 ? "Kid Akikai"
                                      : strcmp(decided, "father") == 0 ? "Kid Bahati" : "Kid Wanjiko") == 0,
                          what);
                }
            }
        }
    }

    printf("2. Only that villager's own rule\n");
    record("father", "villager\tAgo Bahati\t5\t6\tM\tmother\n");
    check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0, "the father himself");
    check(strcmp(born("Ago Bahati", 5, 9, "Aipi Wanjiko", 7, 8), "Kid Bahati") == 0,
          "a namesake with another body: the village's");
    check(strcmp(born("Ago Bahati", 1, 6, "Aipi Wanjiko", 7, 8), "Kid Bahati") == 0,
          "a namesake with another head: the village's");
    check(strcmp(born("Ago Bahati", -1, -1, "Aipi Wanjiko", 7, 8), "Kid Bahati") == 0,
          "his looks unknown: the village's");
    check(strcmp(born("Ago Bahatix", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Bahatix") == 0,
          "another name: the village's");
    record("father", "villager\tAgo Bahati\t5\t6\tF\tmother\n");
    check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Bahati") == 0,
          "a line for a woman is never a father's");
    record("father", "villager\tAgo Bahati\t5\t6\tM\tmother\nvillager\tAgo Bahati\t5\t6\tM\tfather\n");
    check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Bahati") == 0,
          "two lines that disagree: no own rule");
    record("father", "villager\tAgo Bahati\t5\t6\tM\tmother\textra\nvillager\tAgo Bahati\t5\tx\tM\tmother\n");
    check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Bahati") == 0,
          "malformed lines are skipped");

    printf("3. A UTF-8 name in the record is the game's Latin-1\n");
    record("father", "villager\t\xC3\x89lodie Wanjiko\t7\t8\tF\tmother\n");
    check(strcmp(born("Ago Bahati", 5, 6, "\xC9lodie Wanjiko", 7, 8), "Kid Wanjiko") == 0, "\\xC9lodie");

    printf("4. An earlier build's record\n");
    record("mother", "whole\tBig Bob\n");
    check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0, "the village's rule");
    DeleteFileA(g_path);
    check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Bahati") == 0, "no record: the father's");

    printf("5. Head 0 and body 0 are real looks\n");
    record("father", "villager\tAgo Bahati\t0\t0\tM\tmother\nvillager\tAipi Wanjiko\t0\t0\tF\tmother\n");
    check(strcmp(born("Ago Bahati", 0, 0, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0, "a father with head 0, body 0");
    check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 0, 0), "Kid Wanjiko") == 0, "a mother with head 0, body 0");
    check(strcmp(born("Ago Bahati", -1, -1, "Aipi Wanjiko", 7, 8), "Kid Bahati") == 0,
          "unknown looks (negative) are not 0");

    printf("6. A change of looks takes the villager's rule along (VvfpRelookLastName)\n");
    {
        static const char before[] = "VVFP LAST NAMES v1 game=3\nrule\tfather\nwhole\tBig Bob\n"
                                     "villager\tAgo Bahati\t5\t6\tM\tmother\n"
                                     "villager\tAgo Bahati\t5\t6\tF\trandom\n"
                                     "villager\tAgo Bahati\t1\t1\tM\trandom\n"
                                     "villager\t\xC3\x89lodie\t7\t8\tF\tmother\n";
        static const char after[] = "VVFP LAST NAMES v1 game=3\nrule\tfather\nwhole\tBig Bob\n"
                                    "villager\tAgo Bahati\t5\t6\tM\tmother\n"
                                    "villager\tAgo Bahati\t0\t12\tM\tmother\n"
                                    "villager\tAgo Bahati\t5\t6\tF\trandom\n"
                                    "villager\tAgo Bahati\t1\t1\tM\trandom\n"
                                    "villager\t\xC3\x89lodie\t7\t8\tF\tmother\n";
        char got[1024], save[MAX_PATH * 2], tmp[MAX_PATH * 2 + 16];
        FILE *fp;
        size_t n;
        record(NULL, "");
        fp = fopen(g_path, "wb");
        fputs(before, fp);
        fclose(fp);
        check(VvfpRelookLastName("Ago Bahati", 1, 5, 6, 0, 12, 1) == 1, "one line copied to the new looks");
        fp = fopen(g_path, "rb");
        n = fread(got, 1, sizeof got - 1, fp);
        fclose(fp);
        got[n] = '\0';
        check(strcmp(got, after) == 0, "the copy right after it, nothing else changed, byte for byte");
        _snprintf(tmp, sizeof tmp, "%s.relook-tmp", g_path);
        check(GetFileAttributesA(tmp) == INVALID_FILE_ATTRIBUTES, "no temporary file left");
        check(strcmp(born("Ago Bahati", 0, 12, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0,
              "the next birth finds him by his new looks");
        check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0,
              "and a child conceived before the change still by the old ones");
        check(VvfpRelookLastName("Ago Bahati", 1, 5, 6, 0, 12, 1) == 0, "done again: not doubled");
        check(VvfpRelookLastName("Ago Bahati", 1, 8, 8, 9, 9, 1) == 0, "no line with those looks: nothing");
        check(VvfpRelookLastName("Ago Bahati", 1, 0, 12, 0, 12, 1) == 0, "the same looks: nothing");
        check(VvfpRelookLastName("\xC9lodie", 0, 7, 8, 2, 3, 1) == 1, "a Latin-1 name");
        /* Slot 0: the slot whose save holds the name. */
        _snprintf(save, sizeof save, "%s\\LDW\\%s\\Virtual Villagers - The Secret City1.ldw", g_docs, base);
        fp = fopen(save, "wb");
        fwrite("ldwg\0\0Ago Bahati\0\0", 1, 19, fp);
        fclose(fp);
        check(VvfpRelookLastName("Ago Bahati", 1, 1, 1, 4, 4, 0) == 1, "slot 0: found from the save");
        DeleteFileA(save);
    }

    printf("7. The rule's parent only, never the other (the owner, 2026-10-14), in every game\n");
    {
        int g;
        for (g = 1; g <= 5; ++g) {
            g_game = g;
            _snprintf(g_path, sizeof g_path, "%s\\Virtual Villagers %d Last Names - Save 1.dat", folder, g);
            printf("  game %d\n", g);
            record("father", "");
            check(strcmp(born("Hokou Helaku", 0, 15, "Alana Tawonga", 29, 15), "Kid Helaku") == 0,
                  "From the father: Hokou Helaku's, not Alana Tawonga's");
            check(strcmp(born("Ago", 5, 6, "Aipi Wanjiko", 7, 8), "Kid") == 0,
                  "From the father, the father with no last name: none, never the mother's or the family's");
            check(strcmp(born(NULL, -1, -1, "Aipi Wanjiko", 7, 8), "Kid Akikai") == 0,
                  "From the father, the father unknown: the family's stays");
            record("mother", "");
            check(strcmp(born("Ago Bahati", 5, 6, "Aipi", 7, 8), "Kid") == 0,
                  "From the mother, the mother with no last name: none, never the father's");
            record("random", "");
            check(strcmp(born("Ago", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0,
                  "50:50 with one parent's last name: that one");
        }
        g_game = 3;
    }

    printf("8. A village with no rule recorded: \"From the father\" (the owner, 2026-10-14), in every game\n");
    {
        int g;
        for (g = 1; g <= 5; ++g) {
            g_game = g;
            _snprintf(g_path, sizeof g_path, "%s\\Virtual Villagers %d Last Names - Save 1.dat", folder, g);
            printf("  game %d\n", g);
            DeleteFileA(g_path);
            check(strcmp(born("Keiau Chinaka", 9, 8, "Zucca Wanjiko", 13, 25), "Kid Chinaka") == 0,
                  "no record: Watu is his father Keiau Chinaka's, not his mother's family's");
            {
                static char name[24];
                strcpy(name, "Kid Akikai");
                VvfpRuleLastName2(name, sizeof name, "Keiau Chinaka", 9, 8, "Zucca Wanjiko", 13, 25, 0);
                check(strcmp(name, "Kid Chinaka") == 0, "no slot and no save names the parents: the father's");
            }
            check(strcmp(born("Ago", 5, 6, "Aipi Wanjiko", 7, 8), "Kid") == 0,
                  "no record, the father with no last name: none, never the mother's");
            check(strcmp(born(NULL, -1, -1, "Aipi Wanjiko", 7, 8), "Kid Akikai") == 0,
                  "no record, the father unknown: the family's stays");
            record(NULL, "whole\tBig Bob\n");
            check(strcmp(born("Keiau Chinaka", 9, 8, "Zucca Wanjiko", 13, 25), "Kid Chinaka") == 0,
                  "a record with no rule line: the father's");
            record(NULL, "villager\tZucca Wanjiko\t13\t25\tF\tmother\n");
            check(strcmp(born("Keiau Chinaka", 9, 8, "Zucca Wanjiko", 13, 25), "Kid Wanjiko") == 0,
                  "no rule line, the mother's own rule: hers");
            record("each", "");
            check(strcmp(born("Keiau Chinaka", 9, 8, "Zucca Wanjiko", 13, 25), "Kid Akikai") == 0,
                  "Choose from list: unchanged");
            record("list", "");
            check(strcmp(born("Keiau Chinaka", 9, 8, "Zucca Wanjiko", 13, 25), "Kid Akikai") == 0,
                  "Random from list: unchanged");
            record("mother", "");
            check(strcmp(born("Keiau Chinaka", 9, 8, "Zucca Wanjiko", 13, 25), "Kid Wanjiko") == 0,
                  "From the mother recorded: the mother's");
            DeleteFileA(g_path);
        }
        g_game = 3;
    }

    printf("9. One folder per save: the record in the save's own folder (native/shared/per_save.h)\n");
    {
        char own[MAX_PATH * 2], older[MAX_PATH * 2];
        _snprintf(older, sizeof older, "%s\\Virtual Villagers 3 Last Names - Save 1.dat", folder);
        DeleteFileA(older);
        _snprintf(own, sizeof own, "%s\\LDW\\%s\\Virtual Villagers Fun Patcher\\Save 1\\Data\\Last Names", g_docs, base);
        SHCreateDirectoryExA(NULL, own, NULL);
        lstrcatA(own, "\\Virtual Villagers 3 Last Names - Save 1.dat");
        g_game = 3;
        lstrcpynA(g_path, own, sizeof g_path);
        record("mother", "villager\tAgo Bahati\t5\t6\tM\tmother\n");
        check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0,
              "the village's rule is read from the save's own folder");
        check(VvfpRelookLastName("Ago Bahati", 1, 5, 6, 2, 2, 1) == 1
              && GetFileAttributesA(older) == INVALID_FILE_ATTRIBUTES,
              "a change of looks is written there, nothing in the older layout's folder");
        check(strcmp(born("Ago Bahati", 2, 2, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0,
              "...and the next birth finds him by his new looks there");
        DeleteFileA(own);
    }

    /* The list the game's own would be (VvfpStartup reads it from the executable; the emulator test in
       tests/test_last_names_random_rule.py runs the shipped DLL over each game's real list). */
    for (k = 0; k < FAMILIES; ++k) {
        _snprintf(g_last[k], sizeof g_last[k], "Ln%c%c", 'a' + k / 26, 'a' + k % 26);
    }

    printf("10. \"Random last name from the list\", a parent's own rule (the owner, v1.35.79), in every game\n");
    {
        int g;
        for (g = 1; g <= 5; ++g) {
            int counts[FAMILIES], all_listed = 1, reached = 0, same = 0, i;
            double chi = 0.0;
            const int draws = 2500;
            g_game = g;
            _snprintf(g_path, sizeof g_path, "%s\\Virtual Villagers %d Last Names - Save 1.dat", folder, g);
            printf("  game %d\n", g);
            memset(counts, 0, sizeof counts);
            record("father", "villager\tAgo Bahati\t5\t6\tM\tlist\n");
            for (i = 0; i < draws; ++i) {
                const char *got = born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8);
                int found = -1, j;
                for (j = 0; j < FAMILIES; ++j) {
                    if (strncmp(got, "Kid ", 4) == 0 && strcmp(got + 4, g_last[j]) == 0) {
                        found = j;
                    }
                }
                if (found < 0) {
                    all_listed = 0;
                } else {
                    ++counts[found];
                }
            }
            for (i = 0; i < FAMILIES; ++i) {
                double e = (double)draws / FAMILIES;
                reached += counts[i] > 0;
                chi += (counts[i] - e) * (counts[i] - e) / e;
            }
            check(all_listed, "the father's own rule: every child's last name is one of the list's");
            check(reached == FAMILIES, "every one of the 50 names is drawn, the first and the last too");
            check(chi < 90.0, "evenly: chi-square over 50 names below 90 (49 degrees of freedom, p < 0.001)");
            for (i = 0; i < 1000; ++i) {     /* twins: two births in a row, in the same tick */
                char first[24];
                strcpy(first, born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8));
                same += strcmp(first, born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8)) == 0;
            }
            check(same < 60, "twins born together each get their own draw (about 1 pair in 50 alike)");
            record("father", "villager\tAipi Wanjiko\t7\t8\tF\tlist\n");
            memset(counts, 0, sizeof counts);
            reached = 0;
            for (i = 0; i < 500; ++i) {
                const char *got = born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8);
                int j;
                for (j = 0; j < FAMILIES; ++j) {
                    if (strcmp(got + 4, g_last[j]) == 0) {
                        ++counts[j];
                    }
                }
            }
            for (i = 0; i < FAMILIES; ++i) {
                reached += counts[i] > 0;
            }
            check(reached >= 45, "the mother's own rule: drawn from the list too");
            record("father", "villager\tAgo Bahati\t5\t6\tM\tlist\nvillager\tAipi Wanjiko\t7\t8\tF\tmother\n");
            check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Bahati") == 0,
                  "parents' own rules disagree: the village's, never a draw");
            record("list", "villager\tAgo Bahati\t5\t6\tM\tlist\nvillager\tAipi Wanjiko\t7\t8\tF\tlist\n");
            check(strncmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Ln", 6) == 0,
                  "both parents' own: a draw (under the village's Random from list too)");
            record("father", "villager\tAgo Bahati\t5\t6\tM\tlisx\nvillager\tAgo Bahati\t5\t6\tM\tlist2\n");
            check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Bahati") == 0,
                  "an unknown rule code is no rule: the village's");
            {
                static char name[8];
                strcpy(name, "Kid");       /* room 8: "Kid Lnaa" needs 9 bytes: none fits */
                VvfpRuleLastName2(name, sizeof name, "Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8, 1);
                check(strcmp(name, "Kid") == 0, "no list name fits the field: the name is left as it is");
            }
            DeleteFileA(g_path);
        }
        g_game = 3;
    }

    printf("11. 50:50 is a fair draw for each child, twins too\n");
    {
        int g, i;
        for (g = 1; g <= 5; ++g) {
            int dad = 0, differ = 0;
            g_game = g;
            _snprintf(g_path, sizeof g_path, "%s\\Virtual Villagers %d Last Names - Save 1.dat", folder, g);
            printf("  game %d\n", g);
            record("random", "");
            for (i = 0; i < 1000; ++i) {     /* no Sleep: births in the same tick */
                char first[24];
                strcpy(first, born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8));
                dad += strcmp(first, "Kid Bahati") == 0;
                differ += strcmp(first, born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8)) != 0;
            }
            check(dad > 420 && dad < 580, "the father's in about half of 1000 births");
            check(differ > 420 && differ < 580, "twins born together differ about half the time");
            DeleteFileA(g_path);
        }
        g_game = 3;
    }

    printf("12. From the mother is the mother's (the owner, v1.35.79), in every game\n");
    {
        int g;
        for (g = 1; g <= 5; ++g) {
            g_game = g;
            _snprintf(g_path, sizeof g_path, "%s\\Virtual Villagers %d Last Names - Save 1.dat", folder, g);
            printf("  game %d\n", g);
            record("mother", "");
            check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0
                  && strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0
                  && strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0,
                  "triplets: each the mother's, never the father's");
            check(strcmp(born("Ago Bahati", 5, 6, "Aipi Okelani", 7, 8), "Kid Okelani") == 0,
                  "a mother renamed before the birth: the name she has at the birth");
            check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko II", 7, 8), "Kid Wanjiko") == 0,
                  "a numbered mother: her last name, not her numeral");
            check(strcmp(born("Ago Bahati", 5, 6, "Aipi", 7, 8), "Kid") == 0,
                  "a mother with no last name: none, never the father's or the family's");
            check(strcmp(born("Ago", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0,
                  "a father with no last name changes nothing");
            check(strcmp(born("Ago Bahati", 5, 6, NULL, -1, -1), "Kid Akikai") == 0,
                  "the mother unknown: the family's stays, never the father's");
            record("father", "villager\tAipi Wanjiko\t7\t8\tF\tmother\n");
            check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0,
                  "her own From the mother under the village's From the father");
            record("father", "villager\tAgo Bahati\t5\t6\tM\tmother\n");
            check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Wanjiko") == 0,
                  "his own From the mother: the mother's, not his");
            DeleteFileA(g_path);
        }
        g_game = 3;
    }

    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures ? 1 : 0;
}
