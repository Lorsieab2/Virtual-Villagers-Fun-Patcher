/* Prove a parentage log never takes records from the wrong village.
 *
 * Codex reported that switching save slots mid-village left select_log_file
 * choosing the same game-wide file, so conceptions from the new village were
 * appended under the previous village's header -- silently misattributed. That
 * is worse than a missing header: parentage cannot be recovered from a child
 * afterwards, so a record filed under the wrong village is permanently wrong.
 *
 * The header-matching logic is what decides this, so it is exercised directly
 * against real files on disk, including the cases where rotating would be the
 * WRONG answer.
 */
#include <stdio.h>
#include <string.h>
#include <windows.h>

/* The two routines under test are static inside the companion, so this harness
 * compiles the single translation unit and reaches them. */
#define main parentage_export_main_unused
#include "../parentage_export/parentage_export.c"
#undef main

static int failures = 0;

static void check(int condition, const char *what) {
    printf("%s %s\n", condition ? "  ok  " : "  FAIL", what);
    if (!condition) {
        failures++;
    }
}

static void write_log(const wchar_t *path, const char *contents) {
    FILE *f = _wfopen(path, L"wb");
    if (f != NULL) {
        fwrite(contents, 1, strlen(contents), f);
        fclose(f);
    }
}

int main(void) {
    wchar_t path[MAX_LOG_PATH];
    char header[256];

    printf("village rotation harness\n\n");

    GetTempPathW(MAX_LOG_PATH, path);
    wcscat(path, L"vvfp_rotation_test.txt");

    printf("recovering a log's own header:\n");
    write_log(path,
              "Village: Kalahuna Tribe 5 (Save 1)\r\n"
              "Conception 1\r\n  Mother: Anna\r\n");
    check(read_log_header(path, header, sizeof header),
          "a log written with a header reports one");
    check(strcmp(header, "Village: Kalahuna Tribe 5 (Save 1)") == 0,
          "and the line ending is trimmed off it");
    if (strcmp(header, "Village: Kalahuna Tribe 5 (Save 1)") != 0) {
        printf("       got \"%s\"\n", header);
    }

    write_log(path, "Conception 1\r\n  Mother: Anna\r\n");
    check(!read_log_header(path, header, sizeof header),
          "a log that starts with a record has no header");

    printf("\nmatching against the village being played:\n");
    write_log(path,
              "Village: Kalahuna Tribe 5 (Save 1)\r\nConception 1\r\n");
    check(log_belongs_to_village(path, "Village: Kalahuna Tribe 5 (Save 1)\n"),
          "the same village matches");
    check(!log_belongs_to_village(path, "Village: Poop (Save 2)\n"),
          "a DIFFERENT village does not match");
    check(!log_belongs_to_village(path, "Village: Kalahuna Tribe 5 (Save 2)\n"),
          "the same name in a different SAVE SLOT does not match");

    printf("\nwhen rotating would be wrong:\n");
    write_log(path, "Conception 1\r\n  Mother: Anna\r\n");
    check(log_belongs_to_village(path, "Village: Poop (Save 2)\n"),
          "a log predating headers is still the player's, so it matches");

    write_log(path,
              "Village: Kalahuna Tribe 5 (Save 1)\r\nConception 1\r\n");
    check(log_belongs_to_village(path, ""),
          "an unknown current village matches everything");
    check(log_belongs_to_village(path, NULL),
          "and so does no village at all");

    DeleteFileW(path);

    printf("\n%s (%d failure%s)\n",
           failures == 0 ? "PASS" : "FAIL",
           failures, failures == 1 ? "" : "s");
    return failures != 0;
}
