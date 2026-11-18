/* Runtime harness for "VVFP Village Solidarity.dll" (tests/test_village_solidarity.py): the companion's own source,
   built with VVFP_TEST into a 32-bit console program, run against REAL files in a throwaway "Documents"
   (native/shared/harness_redirect_documents.h: the player's Documents\LDW is never touched).

   It checks the rules the owner set (2026-11-17): the score file's round trip (written, read back by a fresh start,
   an unreadable file set aside and the score back at 50), every raise and lower by the same step and the score kept
   within 0..100, neutral never moving it, the odds factor's direction and size with the strength, and the counter's
   words.  Prints "ok"/"FAIL" lines and "== <n> failure(s) ==". */
#define VVFP_TEST 1
#include "vvfp_village_solidarity.c"
#include "../shared/harness_redirect_documents.h"
#include <stdio.h>

static int failures;

#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
    else { ++failures; printf("  FAIL " __VA_ARGS__); printf("\n"); } } while (0)

static int read_text(const char *path, char *out, int cap) {
    FILE *f = fopen(path, "rb");
    int n;
    if (f == NULL) {
        out[0] = '\0';
        return -1;
    }
    n = (int)fread(out, 1, (size_t)cap - 1, f);
    fclose(f);
    out[n < 0 ? 0 : n] = '\0';
    return n;
}

static void write_text(const char *path, const char *text) {
    FILE *f = fopen(path, "wb");
    if (f != NULL) {
        fputs(text, f);
        fclose(f);
    }
}

static int count_aside(const char *path) {
    char pattern[MAX_PATH];
    WIN32_FIND_DATAA found;
    HANDLE h;
    int n = 0;
    wsprintfA(pattern, "%s.unreadable-*", path);
    h = FindFirstFileA(pattern, &found);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    do {
        ++n;
    } while (FindNextFileA(h, &found));
    FindClose(h);
    return n;
}

int main(void) {
    char path[MAX_PATH], text[4096], counter[128];
    int k, score, tags;
    InitializeCriticalSection(&g_lock);
    if (!harness_redirect_documents_process()) {
        printf("  FAIL the harness could not redirect Documents\n== 1 failure(s) ==\n");
        return 1;
    }

    printf("-- the moves: every raise and lower by the same step, within 0..100\n");
    CHECK(vs_moved(50, VS_TAG_RAISE) == 50 + VS_STEP && vs_moved(50, VS_TAG_LOWER) == 50 - VS_STEP,
          "raise and lower move by the same step (%d)", VS_STEP);
    for (k = 0; k <= 100; ++k) {
        int up = vs_moved(k, VS_TAG_RAISE), down = vs_moved(k, VS_TAG_LOWER);
        if (up < 0 || up > 100 || down < 0 || down > 100 || vs_moved(k, VS_TAG_NEUTRAL) != k
            || vs_moved(k, VS_TAG_NONE) != k || (k <= 100 - VS_STEP && up - k != VS_STEP)
            || (k >= VS_STEP && k - down != VS_STEP)) {
            break;
        }
    }
    CHECK(k == 101, "every score 0..100: the same step each way, neutral and none unchanged, clamped");
    CHECK(vs_moved(98, VS_TAG_RAISE) == 100 && vs_moved(2, VS_TAG_LOWER) == 0 && vs_moved(100, VS_TAG_RAISE) == 100
          && vs_moved(0, VS_TAG_LOWER) == 0, "clamped at 0 and 100");

    printf("-- the factor: only ever raises the favoured side's weight, with the strength\n");
    CHECK(vs_factor(50, VS_FAVOUR_HIGH, 10) == 1000 && vs_factor(50, VS_FAVOUR_LOW, 10) == 1000, "at 50: unchanged");
    CHECK(vs_factor(60, VS_FAVOUR_HIGH, 10) == 1200 && vs_factor(60, VS_FAVOUR_LOW, 10) == 1000,
          "high score: cooperative x1.2 at 60, repair unchanged");
    CHECK(vs_factor(40, VS_FAVOUR_LOW, 10) == 1200 && vs_factor(40, VS_FAVOUR_HIGH, 10) == 1000,
          "low score: repair x1.2 at 40, cooperative unchanged");
    CHECK(vs_factor(100, VS_FAVOUR_HIGH, 10) == 2000 && vs_factor(0, VS_FAVOUR_LOW, 10) == 2000,
          "normal strength: doubled at 100 / 0");
    CHECK(vs_factor(100, VS_FAVOUR_HIGH, 100) == 11000 && vs_factor(100, VS_FAVOUR_HIGH, 1) == 1100
          && vs_factor(70, VS_FAVOUR_HIGH, 20) == 1800, "the strength scales it (10x, 0.1x, 2x)");
    CHECK(vs_factor(80, VS_FAVOUR_NONE, 10) == 1000 && vs_factor(80, VS_FAVOUR_HIGH, 0) == 1000
          && vs_factor(80, VS_FAVOUR_HIGH, 101) == 1000, "neither side, or a strength out of range: unchanged");
    for (k = 51, score = 1; k <= 100; ++k) {
        score &= vs_factor(k, VS_FAVOUR_HIGH, 10) > vs_factor(k - 1, VS_FAVOUR_HIGH, 10)
              && vs_factor(100 - k, VS_FAVOUR_LOW, 10) > vs_factor(101 - k, VS_FAVOUR_LOW, 10);
    }
    CHECK(score, "each point further from 50 raises the favoured side's factor");

    printf("-- the strength file's number\n");
    CHECK(vs_parse_tenths("1\n", 2) == 10 && vs_parse_tenths("0.5", 3) == 5 && vs_parse_tenths("2.5\r\n", 5) == 25
          && vs_parse_tenths("10", 2) == 100 && vs_parse_tenths("0.1", 3) == 1, "1, 0.5, 2.5, 10, 0.1");
    CHECK(vs_parse_tenths("0", 1) == 0 && vs_parse_tenths("10.1", 4) == 0 && vs_parse_tenths("abc", 3) == 0
          && vs_parse_tenths("-1", 2) == 0 && vs_parse_tenths("1.25", 4) == 0, "anything else refused (1x then)");

    printf("-- the score file: written, read back, set aside when unreadable\n");
    VvfpVillageScoreProbeStart(4, 2, 10);
    CHECK(VvfpVillageScoreGet(4, 0) == 50, "a new village starts at 50");
    CHECK(VvfpVillageScoreGet(3, 0) == -1 && VvfpVillageScoreTag(3, 0, VS_TAG_RAISE, "x") == -1
          && VvfpVillageScoreFactor(3, 0, VS_FAVOUR_HIGH) == 1000, "another game: nothing (factor 1000)");
    CHECK(vs_file_path(path, 2), "its path");
    CHECK(read_text(path, text, sizeof text) > 0 && strstr(text, "Village Solidarity 50\r\n") != NULL
          && strncmp(text, VS_FILE_HEADER "\r\n", sizeof VS_FILE_HEADER + 1) == 0, "written at once: %s", path);
    CHECK(strstr(path, "Virtual Villagers Fun Patcher\\Save 2\\Data\\Village Scores\\Village Scores - Save 2.txt")
          != NULL, "in the save's own Data folder");
    for (k = 0; k < 3; ++k) {
        score = VvfpVillageScoreTag(4, 0, VS_TAG_RAISE, "A Song by the Fire");
    }
    CHECK(score == 65, "three raises: 65 (%d)", score);
    CHECK(VvfpVillageScoreTag(4, 0, VS_TAG_NEUTRAL, "A Quiet Evening") == 65, "neutral: unchanged");
    CHECK(VvfpVillageScoreFactor(4, 0, VS_FAVOUR_HIGH) == 1300 && VvfpVillageScoreFactor(4, 0, VS_FAVOUR_LOW) == 1000,
          "at 65: cooperative x1.3, repair unchanged");
    CHECK(VvfpVillageScoreProbeCounterText(counter, sizeof counter) > 0
          && strcmp(counter, "Village Solidarity: 65 / 100") == 0, "the counter: \"%s\"", counter);
    VvfpVillageScoreProbeStart(4, 2, 10);   /* a fresh start: read back from the file */
    CHECK(VvfpVillageScoreGet(4, 0) == 65, "read back after a restart: 65");
    for (k = 0, tags = 0; k < 30; ++k) {
        tags = VvfpVillageScoreTag(4, 0, VS_TAG_LOWER, "A Quarrel Left Alone");
    }
    CHECK(tags == 0, "lowered past 0: kept at 0");
    CHECK(VvfpVillageScoreFactor(4, 0, VS_FAVOUR_LOW) == 2000, "at 0: repair doubled");
    VvfpVillageScoreProbeStart(4, 2, 25);
    CHECK(VvfpVillageScoreFactor(4, 0, VS_FAVOUR_LOW) == 1000 + 2 * 25 * 50, "at 0 with 2.5x: x3.5");
    VvfpVillageScoreProbeStart(4, 3, 10);
    CHECK(VvfpVillageScoreGet(4, 0) == 50, "another save slot: its own score");
    VvfpVillageScoreProbeStart(4, 0, 10);
    CHECK(VvfpVillageScoreGet(4, 0) == -1 && VvfpVillageScoreFactor(4, 0, VS_FAVOUR_LOW) == 1000,
          "no village: nothing, factor 1000");
    write_text(path, "not a scores file\r\n");
    VvfpVillageScoreProbeStart(4, 2, 10);
    CHECK(VvfpVillageScoreGet(4, 0) == 50 && count_aside(path) == 1, "an unreadable file: set aside, back to 50");
    {
        char log[MAX_PATH];
        wchar_t wlog[MAX_PATH];
        int fresh;
        CHECK(vs_log_path(wlog, 2, &VS_SCORES[0], &fresh) && !fresh, "the log exists");
        WideCharToMultiByte(CP_ACP, 0, wlog, -1, log, MAX_PATH, NULL, NULL);
        read_text(log, text, sizeof text);
        CHECK(strstr(text, "Village Solidarity (Save 2)") != NULL
              && strstr(text, "A Song by the Fire: raised by 5, 50 -> 55 / 100.") != NULL
              && strstr(text, "A Quiet Evening: no change (65 / 100).") != NULL
              && strstr(text, "A Quarrel Left Alone: would lower it, but it is already 0 / 100.") != NULL,
              "the log has every change, in the same words in every game");
    }

    printf("== %d failure(s) ==\n", failures);
    harness_docs_cleanup();
    return failures == 0 ? 0 : 1;
}
