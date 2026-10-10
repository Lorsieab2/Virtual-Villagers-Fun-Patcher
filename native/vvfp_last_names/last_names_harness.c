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
    fprintf(f, "VVFP LAST NAMES v1 game=3\n");
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
    check(strcmp(born("Ago Bahati", 5, 6, "Aipi Wanjiko", 7, 8), "Kid Akikai") == 0, "no record: unchanged");

    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures ? 1 : 0;
}
