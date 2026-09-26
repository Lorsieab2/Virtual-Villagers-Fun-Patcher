/* Runtime harness for records written before a village's first save.
   32-bit only.

   Drives the real "VVFP Parentage Export.dll" through the window in which the
   owner's first v1.35.27 tribes went wrong: records written before anything
   had published the village. VV1's and VV3's logs came out with no Village
   header, and VV3's gained seven conceptions between villagers that were in
   neither of that tribe's saves.

   Uses VV3's record geometry, where the phantom records were seen:

     1. With the statistics companion present and no village published, a
        conception and a birth are HELD: nothing reaches the disk.
     2. A second held conception's mother is then replaced in her slot -- a
        different villager where she was, as when the game builds the player's
        tribe over the villagers it simulated before it -- and a third's
        mother stops being live.
     3. The village is published and EnsureParentageLog runs, as the
        population exporter does after every save. The log must now exist,
        open with the Village header, hold the kept conception as number 1
        and the birth, and hold neither dropped conception.
     4. A conception written once the village is known goes straight to the
        log as number 2, under the same single header.

   The statistics companion is detected by its file beside the executable, so
   the harness creates an empty stand-in there and removes it when done. Logs
   go under Documents\LDW\<this exe's basename>\, which the harness empties
   first and removes afterwards.

   Usage:  pending_harness.exe "<path to VVFP Parentage Export.dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "village_identity.h"

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

typedef int (__stdcall *write_t)(int, const void *, const void *, const void *);
typedef int (__stdcall *birth_t)(int, const char *, int, int, const char *, int, int,
                                 const char *, int, int, const void *);
typedef int (__stdcall *ensure_t)(int, const char *);

/* VV3, as the export DLL's GAME_LAYOUTS row and parentage_export_harness.c
   have it. */
#define STRIDE      0x1F8C
#define SLOTS       150
#define BASE        0x14
#define ACTIVE      0xF10
#define AGE         0xDC4
#define HEAD        0xDF0
#define BODY        0xDF4
#define NAME        0xDD4
#define NAME_CAP    0x19
#define FATHER_NAME 0xE48
#define FATHER_CAP  0x18
#define HEAD_COPY   0xE68
#define BODY_COPY   0xE64
#define LIKES       0xFB4
#define DISLIKES    0xFC0
#define PREF_SLOTS  3
#define TITLE       "Virtual Villagers 3 Births and Conceptions Log"
#define VILLAGE     "Village: Harness Tribe (Save 1)\n"

static unsigned char *records;
static unsigned char *rec(int i) { return records + BASE + i * STRIDE; }

static void villager(int i, const char *name, int age, int head, int body) {
    int s;
    memset(rec(i), 0, STRIDE);
    rec(i)[ACTIVE] = 1;
    *(int *)(rec(i) + AGE) = age;
    *(int *)(rec(i) + HEAD) = head;
    *(int *)(rec(i) + BODY) = body;
    strncpy((char *)rec(i) + NAME, name, NAME_CAP);
    for (s = 0; s < PREF_SLOTS; ++s) {
        *(int *)(rec(i) + LIKES + s * 4) = -1;
        *(int *)(rec(i) + DISLIKES + s * 4) = -1;
    }
}

static void conceive(int mother, int father) {
    memset(rec(mother) + FATHER_NAME, 0, FATHER_CAP);
    strncpy((char *)rec(mother) + FATHER_NAME, (const char *)rec(father) + NAME, FATHER_CAP);
    *(int *)(rec(mother) + HEAD_COPY) = *(int *)(rec(father) + HEAD);
    *(int *)(rec(mother) + BODY_COPY) = *(int *)(rec(father) + BODY);
}

static char folder[MAX_PATH];
static char marker[MAX_PATH];

static int locate(void) {
    char docs[MAX_PATH], exe[MAX_PATH], *base, *dot;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) return 0;
    if (GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) return 0;
    base = strrchr(exe, '\\');
    if (base == NULL) return 0;
    _snprintf(marker, MAX_PATH, "%.*s\\VVFP Statistics Export.dll", (int)(base - exe), exe);
    marker[MAX_PATH - 1] = '\0';
    ++base;
    dot = strrchr(base, '.');
    if (dot) *dot = 0;
    _snprintf(folder, MAX_PATH,
              "%s\\LDW\\%s\\Virtual Villagers Fun Patcher Logs\\Births and Conceptions",
              docs, base);
    folder[MAX_PATH - 1] = '\0';
    return 1;
}

static void remove_logs(void) {
    char pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA f;
    HANDLE h;
    _snprintf(pattern, MAX_PATH, "%s\\*.txt", folder);
    h = FindFirstFileA(pattern, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do { _snprintf(path, MAX_PATH, "%s\\%s", folder, f.cFileName); DeleteFileA(path); }
        while (FindNextFileA(h, &f));
        FindClose(h);
    }
    RemoveDirectoryA(folder);
}

static int log_files(void) {
    char pattern[MAX_PATH];
    WIN32_FIND_DATAA f;
    HANDLE h;
    int n = 0;
    _snprintf(pattern, MAX_PATH, "%s\\*.txt", folder);
    h = FindFirstFileA(pattern, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do { ++n; } while (FindNextFileA(h, &f));
        FindClose(h);
    }
    return n;
}

static char logtext[1 << 16];
static int read_log(void) {
    char path[MAX_PATH];
    FILE *f;
    size_t n;
    _snprintf(path, MAX_PATH, "%s\\%s 1.txt", folder, TITLE);
    f = fopen(path, "rb");
    if (f == NULL) { logtext[0] = 0; return 0; }
    n = fread(logtext, 1, sizeof logtext - 1, f);
    logtext[n] = 0;
    fclose(f);
    return 1;
}

static int count(const char *needle) {
    int n = 0;
    const char *p = logtext;
    size_t len = strlen(needle);
    while ((p = strstr(p, needle)) != NULL) { ++n; p += len; }
    return n;
}

int main(int argc, char **argv) {
    HMODULE dll;
    write_t write;
    birth_t birth;
    ensure_t ensure;
    HANDLE stand_in;
    const char *second;

    if (argc != 2) {
        printf("usage: pending_harness.exe <VVFP Parentage Export.dll>\n");
        return 2;
    }
    if (!locate()) {
        printf("could not locate Documents or this executable\n");
        return 2;
    }
    remove_logs();
    stand_in = CreateFileA(marker, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (stand_in == INVALID_HANDLE_VALUE) {
        printf("could not create the statistics stand-in beside the harness\n");
        return 2;
    }
    CloseHandle(stand_in);

    dll = LoadLibraryA(argv[1]);
    if (dll == NULL) {
        printf("could not load %s\n", argv[1]);
        DeleteFileA(marker);
        return 2;
    }
    write = (write_t)GetProcAddress(dll, "WriteParentageRecordWithFather");
    birth = (birth_t)GetProcAddress(dll, "WriteParentageBirth");
    ensure = (ensure_t)GetProcAddress(dll, "EnsureParentageLog");
    CHECK(write && birth && ensure, "the three exports resolve");
    if (!(write && birth && ensure)) {
        DeleteFileA(marker);
        return 1;
    }

    records = (unsigned char *)calloc(1, BASE + SLOTS * STRIDE);

    /* The player's tribe: Tikina and Koro, and their child Mahu. */
    villager(0, "Tikina", 414, 23, 1);
    villager(1, "Koro", 436, 9, 25);
    villager(4, "Mahu", 0, 16, 21);
    /* Two villagers of the simulation the game runs before the tribe exists. */
    villager(2, "Makawa", 487, 24, 20);
    villager(3, "Kao", 434, 22, 2);
    villager(5, "Tufi", 453, 22, 3);
    villager(6, "Maro", 479, 8, 16);

    printf("-- before the first save: records are held --\n");
    conceive(2, 3);
    CHECK(write(3, records, rec(2), rec(3)) == 1, "a pre-tribe conception is accepted");
    conceive(0, 1);
    CHECK(write(3, records, rec(0), rec(1)) == 1, "the tribe's conception is accepted");
    conceive(5, 6);
    CHECK(write(3, records, rec(5), rec(6)) == 1, "a second pre-tribe conception is accepted");
    CHECK(birth(3, "", -1, -1, "Tikina", 23, 1, "Koro", 9, 25, rec(4)) == 1,
          "the tribe's birth is accepted");
    CHECK(log_files() == 0, "nothing is written while the village is unknown");

    printf("-- the tribe replaces the simulated villagers --\n");
    villager(2, "Tasiri", 380, 17, 8);     /* a different villager in Makawa's slot */
    rec(5)[ACTIVE] = 0;                     /* Tufi's slot is no longer live */

    printf("-- the first save --\n");
    vv_village_publish(VILLAGE);
    CHECK(ensure(3, VILLAGE) == 1, "EnsureParentageLog succeeds");
    CHECK(read_log(), "the log now exists");
    CHECK(strncmp(logtext, "Village: Harness Tribe (Save 1)\r\n", 33) == 0,
          "the log opens with the Village header");
    CHECK(count("Village: ") == 1, "exactly one header");
    CHECK(count("Conception ") == 1, "exactly one conception was kept");
    CHECK(strstr(logtext, "Conception 1\r\n  Mother: Tikina\r\n") != NULL,
          "the tribe's conception is Conception 1");
    CHECK(strstr(logtext, "Makawa") == NULL, "the replaced villager's conception is dropped");
    CHECK(strstr(logtext, "Tufi") == NULL, "the no-longer-live villager's conception is dropped");
    CHECK(strstr(logtext, "Birth\r\n  Child: Mahu\r\n") != NULL, "the tribe's birth is kept");
    CHECK(strstr(logtext, "Conception 1") < strstr(logtext, "Birth"),
          "held records keep their order");

    printf("-- after the first save: records are written at once --\n");
    villager(7, "Saka", 400, 4, 15);
    conceive(7, 1);
    CHECK(write(3, records, rec(7), rec(1)) == 1, "a later conception is accepted");
    CHECK(read_log(), "the log is still there");
    second = strstr(logtext, "Conception 2\r\n  Mother: Saka\r\n");
    CHECK(second != NULL, "it is written immediately as Conception 2");
    CHECK(count("Village: ") == 1, "still exactly one header");
    CHECK(ensure(3, VILLAGE) == 1, "a later save changes nothing");
    CHECK(read_log() && count("Conception ") == 2 && count("Village: ") == 1,
          "no record is written twice");

    FreeLibrary(dll);
    free(records);
    remove_logs();
    DeleteFileA(marker);
    printf("== %d failure(s) ==\n", failures);
    return failures == 0 ? 0 : 1;
}
