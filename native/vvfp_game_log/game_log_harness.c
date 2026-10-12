/* Runtime harness for "VVFP Game Log.dll" (native/vvfp_game_log).

   Includes the companion's source whole and drives the replacement writer,
   write_line(), exactly as a game's call sites do (the log object, a format
   and its values), against a folder of its own under %TEMP% and a clock of its
   own -- never the player's Documents\LDW.  tests/test_game_log.py builds and
   runs it (32-bit MSVC) and expects every check to pass:
     the line format (asctime, ": ", CR-LF, a '\n' in the text as CR-LF);
     lines kept across runs (append, never "wt");
     an exact repeat written once a minute with its count;
     the per-minute cap and its note;
     the roll-over at 4 MiB to "ldwLog <n>.txt" after the highest n;
     a value the format cannot read keeps the format, never faults;
     the install refuses an executable whose writer bytes differ. */
#define _CRT_SECURE_NO_WARNINGS
#include "vvfp_game_log.c"

#include <stdlib.h>

static int checks, failures;
static ULONGLONG fake_now = 1000000;   /* seconds since Windows started */
static SYSTEMTIME fake_date = {2026, 9, 1, 28, 23, 27, 56, 0};   /* Mon Sep 28 23:27:56 2026 */

static ULONGLONG fake_seconds(void) {
    return fake_now;
}

static void fake_local_time(SYSTEMTIME *now) {
    *now = fake_date;
}

static void check(int ok, const char *what) {
    ++checks;
    if (ok) {
        printf("  ok %s\n", what);
    } else {
        ++failures;
        printf("  FAIL %s\n", what);
    }
}

static wchar_t root[MAX_PATH];

static void path_of(const wchar_t *name, wchar_t *out) {
    _snwprintf(out, MAX_PATH, L"%ls\\%ls", folder, name);
    out[MAX_PATH - 1] = 0;
}

/* The whole of a file in the folder, NUL-terminated (caller frees); NULL when absent. */
static char *read_all(const wchar_t *name, long *size) {
    wchar_t path[MAX_PATH];
    FILE *f;
    char *data;
    long n;
    path_of(name, path);
    f = _wfopen(path, L"rb");
    if (f == NULL) {
        return NULL;
    }
    fseek(f, 0, SEEK_END);
    n = ftell(f);
    fseek(f, 0, SEEK_SET);
    data = (char *)malloc((size_t)n + 1);
    fread(data, 1, (size_t)n, f);
    data[n] = 0;
    fclose(f);
    if (size) *size = n;
    return data;
}

/* What asctime() prints for the harness's date, without its newline. */
static void stamp_of(char *out) {
    static const char *days[] = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
    static const char *months[] = {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
    sprintf(out, "%.3s %.3s%3d %.2d:%.2d:%.2d %d", days[fake_date.wDayOfWeek], months[fake_date.wMonth - 1],
            fake_date.wDay, fake_date.wHour, fake_date.wMinute, fake_date.wSecond, fake_date.wYear);
}

static int count_of(const char *hay, const char *needle) {
    int n = 0;
    const char *p = hay;
    while ((p = strstr(p, needle)) != NULL) {
        ++n;
        p += strlen(needle);
    }
    return n;
}

/* A new run of the game: the process state starts over, the files stay. */
static void new_run(void) {
    if (file != INVALID_HANDLE_VALUE) {
        CloseHandle(file);
        file = INVALID_HANDLE_VALUE;
    }
    file_size = 0;
    have_last = 0;
    last_line[0] = 0;
    repeats = 0;
    rate_start = 0;
    rate_count = 0;
    rate_dropped = 0;
}

static void remove_folder(void) {
    wchar_t pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAW f;
    HANDLE h;
    new_run();
    _snwprintf(pattern, MAX_PATH, L"%ls\\*", folder);
    h = FindFirstFileW(pattern, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
            path_of(f.cFileName, path);
            DeleteFileW(path);
        } while (FindNextFileW(h, &f));
        FindClose(h);
    }
    RemoveDirectoryW(folder);
    RemoveDirectoryW(root);
}

int main(void) {
    wchar_t temp[MAX_PATH];
    char stamp[32], expect[512], *text;
    long size;
    int i;

    GetTempPathW(MAX_PATH, temp);
    _snwprintf(root, MAX_PATH, L"%lsvvfp_game_log_harness_%lu", temp, GetCurrentProcessId());
    CreateDirectoryW(root, NULL);
    _snwprintf(folder, MAX_PATH, L"%ls\\Virtual Villagers - New Believers", root);
    CreateDirectoryW(folder, NULL);
    folder_state = 1;                      /* never the real Documents\LDW */
    local_time = fake_local_time;
    seconds_now = fake_seconds;
    InitializeCriticalSection(&lock);
    lock_ready = 1;

    printf("== the line format ==\n");
    write_line(NULL, "ldwSoundFx Missing File ->%s", "gold_dust_pour .ogg");
    write_line(NULL, "Font Image not found: %s\n", "font1.png");
    write_line(NULL, "%s is going to the love shack door at %d, %d (isBlocking=%s)", "Manaka", 1100, 1462, "false");
    text = read_all(L"ldwLog.txt", &size);
    stamp_of(stamp);
    _snprintf(expect, sizeof expect,
              "%s: ldwSoundFx Missing File ->gold_dust_pour .ogg\r\n"
              "%s: Font Image not found: font1.png\r\n\r\n"
              "%s: Manaka is going to the love shack door at 1100, 1462 (isBlocking=false)\r\n",
              stamp, stamp, stamp);
    check(text != NULL && strcmp(text, expect) == 0, "asctime stamp, the game's text, CR-LF, a newline in the text kept");
    free(text);
    {
        char out[64];
        unsigned int n;
        fake_date.wDay = 8;
        fake_date.wDayOfWeek = 2;
        n = stamp_text(out);
        out[n] = 0;
        stamp_of(stamp);
        check(strcmp(out, stamp) == 0 && strcmp(out, "Tue Sep  8 23:27:56 2026") == 0, "a one-digit day is padded with a space, as asctime does");
        fake_date.wDay = 28;
        fake_date.wDayOfWeek = 1;
    }

    printf("== lines are kept across runs ==\n");
    new_run();
    fake_now += 3600;
    write_line(NULL, "Seconds Timer out of bounds!");
    text = read_all(L"ldwLog.txt", &size);
    check(text != NULL && strstr(text, "gold_dust_pour .ogg") != NULL
          && strstr(text, "Seconds Timer out of bounds!") != NULL, "a new run appends; the earlier run's lines stay");
    free(text);

    printf("== an exact repeat ==\n");
    for (i = 0; i < 500; ++i) {
        write_line(NULL, "Seconds Timer out of bounds!");     /* the same frame-by-frame line */
    }
    text = read_all(L"ldwLog.txt", &size);
    check(count_of(text, "Seconds Timer out of bounds!") == 1, "500 repeats within a minute write nothing more");
    free(text);
    fake_now += REPEAT_SECONDS;
    write_line(NULL, "Seconds Timer out of bounds!");
    text = read_all(L"ldwLog.txt", &size);
    check(strstr(text, "(the line above was repeated 500 more times)\r\n") != NULL
          && count_of(text, "Seconds Timer out of bounds!") == 2, "after a minute: the count, then the line again");
    free(text);
    write_line(NULL, "Seconds Timer out of bounds!");
    write_line(NULL, "Manaka could not find someone to heal.");
    text = read_all(L"ldwLog.txt", &size);
    check(strstr(text, "(the line above was repeated 1 more time)\r\n") != NULL
          && strstr(text, "Manaka could not find someone to heal.\r\n") != NULL, "a different line writes the count first");
    free(text);

    printf("== the per-minute cap ==\n");
    new_run();
    fake_now += 3600;
    for (i = 0; i < (int)RATE_LINES + 250; ++i) {
        write_line(NULL, "%s is stuck!", i % 2 ? "Rata" : "Loa");      /* different from the one before */
    }
    text = read_all(L"ldwLog.txt", &size);
    check(count_of(text, " is stuck!") == (int)RATE_LINES, "at most 1000 lines in a minute");
    free(text);
    fake_now += RATE_SECONDS;
    write_line(NULL, "Loa is stuck!");
    text = read_all(L"ldwLog.txt", &size);
    check(strstr(text, "(250 more lines were left out: the game wrote more than 1000 lines in a minute)\r\n") != NULL
          && count_of(text, " is stuck!") == (int)RATE_LINES + 1, "the next minute says how many were left out, then goes on");
    free(text);

    printf("== roll-over ==\n");
    {
        wchar_t path[MAX_PATH];
        FILE *f;
        static char block[65536];
        long before;
        new_run();
        memset(block, 'x', sizeof block);
        path_of(L"ldwLog 3.txt", path);           /* an older roll-over: the next is 4 */
        f = _wfopen(path, L"wb");
        fputs("old\r\n", f);
        fclose(f);
        path_of(L"ldwLog - Copy.txt", path);      /* the player's own copy: not a number */
        f = _wfopen(path, L"wb");
        fclose(f);
        path_of(L"ldwLog.txt", path);
        f = _wfopen(path, L"ab");
        while (ftell(f) < (long)ROLL_BYTES - 50) {
            fwrite(block, 1, sizeof block < (size_t)((long)ROLL_BYTES - 50 - ftell(f)) ? sizeof block
                   : (size_t)((long)ROLL_BYTES - 50 - ftell(f)), f);
        }
        before = ftell(f);
        fclose(f);
        write_line(NULL, "Akivi is going to the love shack door at %d, %d (isBlocking=%s)", 1463, 1484, "false");
        text = read_all(L"ldwLog 4.txt", &size);
        check(text != NULL && size == before, "the full file is kept whole as ldwLog 4.txt");
        free(text);
        text = read_all(L"ldwLog.txt", &size);
        stamp_of(stamp);
        _snprintf(expect, sizeof expect, "%s: Akivi is going to the love shack door at 1463, 1484 (isBlocking=false)\r\n", stamp);
        check(text != NULL && strcmp(text, expect) == 0, "the new ldwLog.txt starts with the line that did not fit");
        free(text);
        text = read_all(L"ldwLog 3.txt", &size);
        check(text != NULL && strcmp(text, "old\r\n") == 0, "older roll-overs are never touched");
        free(text);
        text = read_all(L"ldwLog - Copy.txt", &size);
        check(text != NULL && size == 0, "a file named otherwise is never touched");
        free(text);
    }

    printf("== safety ==\n");
    write_line(NULL, "%s could not find someone to heal.", (const char *)(UINT_PTR)8);
    text = read_all(L"ldwLog.txt", &size);
    check(strstr(text, ": %s could not find someone to heal.\r\n") != NULL, "a value the format cannot read: the format is written, no fault");
    free(text);
    write_line(NULL, NULL);
    check(1, "a missing format is ignored");
    check(install(1) == 0 && install_state == -1, "an executable whose writer bytes differ installs nothing");
    {
        unsigned char bytes[SITE_LENGTH];
        unsigned int rel;
        site_bytes(SITES[5].va, bytes);
        memcpy(&rel, bytes + 1, 4);
        check(bytes[0] == 0xE9 && bytes[5] == 0x90 && SITES[5].va + 5 + rel == (unsigned int)(UINT_PTR)write_line,
              "the writer's first six bytes become jmp write_line; nop");
    }

    remove_folder();
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures ? 1 : 0;
}
