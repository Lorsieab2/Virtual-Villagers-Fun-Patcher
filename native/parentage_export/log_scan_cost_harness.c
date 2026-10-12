/* What one Births and Conceptions record costs as the log grows.  32-bit.

   The owner's lag at 256 villagers (v1.35.70): every record -- a Conception,
   a Birth -- used to read every file of its log, in every folder of the
   game, three times over (the records of the file it goes into, each file's
   village header, the highest number printed anywhere), and looked the save
   folder up again, creating each of its components, once per file of the
   walk.  A long history paid that on every record, on the game's own thread.

   This loads "VVFP Parentage Export.dll" (the path on the command line),
   with its Documents redirected to a throwaway folder under %TEMP%
   (harness_redirect_documents.h: the real Documents\LDW is never touched),
   and writes A New Home's Conception and Birth records in rounds of 256
   conceptions and 256 births -- a new log file each round.  For every round
   it prints the bytes the process read (GetProcessIoCounters, every file
   read by any API counts) per record, and at the end every file the DLL
   wrote, with its size and an FNV-1a hash of its bytes, so a test can
   compare two builds byte for byte.

   The bound: a record of the last round may read no more than the file it
   goes into (a few times) -- not the whole history.  Before the fix a record
   of round 6 read about 3 times the history (some 2.4 MB); now about
   3 times the one file (under 0.4 MB).

   Usage:  log_scan_cost_harness.exe "<path to VVFP Parentage Export.dll>" [rounds]
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../shared/harness_redirect_documents.h"

typedef int (__stdcall *conceive_t)(int, const void *, const void *, const void *);
typedef int (__stdcall *born_t)(int, const char *, int, int, const char *, int, int, const char *, int, int,
                                const void *, int);

#define STRIDE 0x3D8
static unsigned char records[256 * STRIDE];
static unsigned char *rec(int i) { return records + i * STRIDE; }

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

static ULONGLONG bytes_read(void) {
    IO_COUNTERS io;
    return GetProcessIoCounters(GetCurrentProcess(), &io) ? io.ReadTransferCount : 0;
}

static ULONGLONG g_written;

static void dump(const char *dir, int root) {
    char pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA f;
    HANDLE h;
    _snprintf(pattern, MAX_PATH, "%s\\*", dir);
    pattern[MAX_PATH - 1] = '\0';
    h = FindFirstFileA(pattern, &f);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (strcmp(f.cFileName, ".") == 0 || strcmp(f.cFileName, "..") == 0) continue;
        _snprintf(path, MAX_PATH, "%s\\%s", dir, f.cFileName);
        path[MAX_PATH - 1] = '\0';
        if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            dump(path, root);
        } else {
            FILE *fp = fopen(path, "rb");
            unsigned int hash = 2166136261u;
            long n = 0;
            int c;
            if (fp == NULL) continue;
            while ((c = fgetc(fp)) != EOF) { hash = (hash ^ (unsigned int)c) * 16777619u; ++n; }
            fclose(fp);
            g_written += (ULONGLONG)n;
            printf("FILE %s %ld %08X\n", path + root, n, hash);
        }
    } while (FindNextFileA(h, &f));
    FindClose(h);
}

int main(int argc, char **argv) {
    HMODULE dll;
    conceive_t conceive;
    born_t born;
    int i, round, rounds = argc > 2 ? atoi(argv[2]) : 6;
    ULONGLONG last_round = 0, history = 0;
    if (argc < 2) {
        printf("usage: log_scan_cost_harness.exe <dll> [rounds]\n");
        return 2;
    }
    if (!harness_redirect_documents_process()) return 2;
    dll = LoadLibraryA(argv[1]);
    if (dll == NULL || !harness_redirect_documents(dll)) {
        printf("cannot load or redirect %s\n", argv[1]);
        return 2;
    }
    conceive = (conceive_t)GetProcAddress(dll, "WriteParentageRecordWithFather");
    born = (born_t)GetProcAddress(dll, "WriteParentageBirthLitter");
    if (conceive == NULL || born == NULL) {
        printf("exports missing\n");
        return 2;
    }
    for (i = 0; i < 256; ++i) {
        unsigned char *r = rec(i);
        int s;
        r[0x28] = 1;
        *(int *)(r + 0x348) = 400 + i;
        *(int *)(r + 0x360) = i % 20;
        *(int *)(r + 0x364) = i % 9;
        _snprintf((char *)r + 0x370, 0x1B, "Villager%03d", i);
        for (s = 0; s < 4; ++s) {
            *(int *)(r + 0x398 + s * 4) = (i + s) % 40;
            *(int *)(r + 0x3A8 + s * 4) = (i + s + 7) % 40;
        }
    }
    for (round = 0; round < rounds; ++round) {
        ULONGLONG before = bytes_read();
        for (i = 0; i < 256; ++i) {
            const unsigned char *mother = rec((i * 2) % 256);
            const unsigned char *father = rec((i * 2 + 1) % 256);
            conceive(1, records, mother, father);
            born(1, "Baby", i % 20, i % 9, (const char *)mother + 0x370, i % 20, i % 9,
                 (const char *)father + 0x370, (i + 1) % 20, (i + 1) % 9, rec((i * 2 + 2) % 256), 1);
        }
        last_round = (bytes_read() - before) / 512;
        printf("round %d: %llu bytes read per record\n", round + 1, last_round);
    }
    {
        char root[MAX_PATH];
        lstrcpynA(root, harness_redirect_documents_path(), MAX_PATH);
        dump(root, (int)strlen(root));
    }
    history = g_written;
    printf("history: %llu bytes in every file written\n", history);
    CHECK(history > 0, "the records were written");
    /* Each round fills one file, so a record of the last round goes into a
       file of at most 1/rounds of the history: reading it a few times stays
       well under half the history.  Reading every file (the old cost) is
       about 3 times the history. */
    CHECK(rounds < 4 || last_round * 2 < history,
          "a record of round %d reads %llu bytes, under half of the %llu-byte history", rounds, last_round, history);
    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
