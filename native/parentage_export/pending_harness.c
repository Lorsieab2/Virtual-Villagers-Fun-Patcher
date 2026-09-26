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
typedef int (__stdcall *ensure_village_t)(int, const char *, const void *);

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
#define OWN_FATHER  0xDF8   /* the villager's own parents, kept for life */
#define OWN_MOTHER  0xE11
#define OWN_CAP     0x19
#define TITLE       "Virtual Villagers 3 Births and Conceptions Log"
#define VILLAGE     "Village: Harness Tribe (Save 1)\n"
#define VILLAGE2    "Village: Second Tribe (Save 2)\n"

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

static void parents(int i, const char *father, const char *mother) {
    memset(rec(i) + OWN_FATHER, 0, OWN_CAP);
    memset(rec(i) + OWN_MOTHER, 0, OWN_CAP);
    strncpy((char *)rec(i) + OWN_FATHER, father, OWN_CAP);
    strncpy((char *)rec(i) + OWN_MOTHER, mother, OWN_CAP);
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
    /* And the two folders above it that the DLL created for this harness --
       "Virtual Villagers Fun Patcher Logs" and Documents\LDW\<harness name>.
       Left behind, they piled up in the owner's real LDW save folder after
       every run. RemoveDirectory only removes an EMPTY folder, so nothing
       else can be lost. */
    {
        char parent[MAX_PATH];
        char *cut;
        int level;
        lstrcpynA(parent, folder, MAX_PATH);
        for (level = 0; level < 2; ++level) {
            cut = strrchr(parent, '\\');
            if (cut == NULL) break;
            *cut = 0;
            RemoveDirectoryA(parent);
        }
    }
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
static int read_log_n(int number) {
    char path[MAX_PATH];
    FILE *f;
    size_t n;
    _snprintf(path, MAX_PATH, "%s\\%s %d.txt", folder, TITLE, number);
    f = fopen(path, "rb");
    if (f == NULL) { logtext[0] = 0; return 0; }
    n = fread(logtext, 1, sizeof logtext - 1, f);
    logtext[n] = 0;
    fclose(f);
    return 1;
}
static int read_log(void) { return read_log_n(1); }

/* A save, as the population exporter makes it: the village just saved and the
   villager table it wrote the roster from. Falls back to the two-argument
   export for a DLL that predates the three-argument one. */
static ensure_t ensure;
static ensure_village_t ensure_village;
static int save(const char *village) {
    if (ensure_village != NULL) {
        return ensure_village(3, village, records);
    }
    return ensure(3, village);
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
    ensure_village = (ensure_village_t)GetProcAddress(dll, "EnsureParentageLogForVillage");
    CHECK(ensure_village != NULL, "EnsureParentageLogForVillage is exported");
    CHECK(write && birth && ensure, "the three exports resolve");
    if (!(write && birth && ensure)) {
        DeleteFileA(marker);
        return 1;
    }

    records = (unsigned char *)calloc(1, BASE + SLOTS * STRIDE);

    printf("-- the game's pre-tribe simulation: its records are held --\n");
    villager(0, "Makawa", 487, 24, 20);
    villager(1, "Kao", 434, 22, 2);
    villager(2, "Tufi", 453, 22, 3);
    villager(3, "Maro", 479, 8, 16);
    conceive(0, 1);
    CHECK(write(3, records, rec(0), rec(1)) == 1, "a simulated conception is accepted");
    conceive(2, 3);
    CHECK(write(3, records, rec(2), rec(3)) == 1, "a second simulated conception is accepted");
    CHECK(log_files() == 0, "nothing is written while the village is unknown");

    printf("-- the player's tribe replaces the whole table --\n");
    memset(records, 0, BASE + SLOTS * STRIDE);
    villager(0, "Tikina", 414, 23, 1);
    villager(1, "Koro", 436, 9, 25);
    villager(2, "Nui", 400, 17, 9);
    villager(3, "Ika", 380, 29, 26);
    villager(4, "Samoa", 0, 6, 28);
    parents(4, "Koro", "Tikina");
    villager(5, "Epeli", 0, 16, 15);
    parents(5, "Koro", "Nui");
    villager(6, "Mahu", 0, 16, 21);
    parents(6, "Koro", "Tikina");
    villager(7, "Saka", 400, 4, 15);
    conceive(0, 1);
    CHECK(write(3, records, rec(0), rec(1)) == 1, "the tribe's conception is accepted");
    conceive(2, 1);
    CHECK(write(3, records, rec(2), rec(1)) == 1, "a conception whose mother will die is accepted");
    conceive(3, 1);
    CHECK(write(3, records, rec(3), rec(1)) == 1, "a conception whose mother will be renamed is accepted");
    CHECK(birth(3, "", -1, -1, "Tikina", 23, 1, "Koro", 9, 25, rec(6)) == 1, "a birth is accepted");
    CHECK(birth(3, "", -1, -1, "Nui", 17, 9, "Koro", 9, 25, rec(5)) == 1,
          "a birth during a save-less Time Warp is accepted (Epeli)");
    CHECK(birth(3, "", -1, -1, "Tikina", 23, 1, "Koro", 9, 25, rec(4)) == 1,
          "a birth that will be de-aged and restyled is accepted");
    CHECK(log_files() == 0, "still nothing written");

    printf("-- before the save: ordinary game behaviour changes villagers --\n");
    *(int *)(rec(0) + AGE) = 534;                   /* ages */
    *(int *)(rec(5) + AGE) = 241;                   /* Epeli grows... */
    *(int *)(rec(5) + LIKES) = 5;                   /* ...and takes up a like */
    *(int *)(rec(4) + AGE) = 0;                     /* Samoa: the Gong de-ages */
    *(int *)(rec(4) + HEAD) = 12;                   /* Change Appearance */
    *(int *)(rec(4) + BODY) = 3;
    memset(rec(3) + NAME, 0, NAME_CAP);             /* the player renames Ika */
    strncpy((char *)rec(3) + NAME, "Ikaika", NAME_CAP);
    rec(2)[ACTIVE] = 0;                             /* Nui dies */

    printf("-- the first save --\n");
    vv_village_publish(VILLAGE);
    CHECK(save(VILLAGE) == 1, "EnsureParentageLog succeeds");
    CHECK(read_log(), "the log now exists");
    CHECK(strncmp(logtext, "Village: Harness Tribe (Save 1)\r\n", 33) == 0,
          "the log opens with the Village header");
    CHECK(count("Village: ") == 1, "exactly one header");
    CHECK(strstr(logtext, "Makawa") == NULL && strstr(logtext, "Tufi") == NULL,
          "the simulation's conceptions are dropped: its table was replaced");
    CHECK(count("Conception ") == 3, "all three of the tribe's conceptions are kept");
    CHECK(strstr(logtext, "Conception 1\r\n  Mother: Tikina\r\n") != NULL, "Tikina's is Conception 1");
    CHECK(strstr(logtext, "Conception 2\r\n  Mother: Nui\r\n") != NULL,
          "a mother who died before the save is still logged");
    CHECK(strstr(logtext, "Conception 3\r\n  Mother: Ika\r\n") != NULL,
          "a mother renamed before the save is logged under the name she had");
    CHECK(strstr(logtext, "Birth\r\n  Child: Mahu\r\n") != NULL, "the tribe's birth is kept");
    CHECK(strstr(logtext, "Birth\r\n  Child: Epeli\r\n") != NULL,
          "a child who grew and took up a like before the save is logged (Epeli)");
    CHECK(strstr(logtext, "Birth\r\n  Child: Samoa\r\n") != NULL,
          "a child de-aged and restyled before the save is logged");
    CHECK(strstr(logtext, "Conception 1") < strstr(logtext, "Birth"), "held records keep their order");

    printf("-- after the first save: records are written at once --\n");
    conceive(7, 1);
    CHECK(write(3, records, rec(7), rec(1)) == 1, "a later conception is accepted");
    CHECK(read_log(), "the log is still there");
    second = strstr(logtext, "Conception 4\r\n  Mother: Saka\r\n");
    CHECK(second != NULL, "it is written immediately as Conception 4");
    CHECK(count("Village: ") == 1, "still exactly one header");
    CHECK(save(VILLAGE) == 1, "a later save changes nothing");
    CHECK(read_log() && count("Conception ") == 4 && count("Village: ") == 1,
          "no record is written twice");

    printf("-- a write that fails is retried, not lost --\n");
    {
        char path[MAX_PATH];
        HANDLE lock;
        _snprintf(path, MAX_PATH, "%s\\%s 1.txt", folder, TITLE);
        lock = CreateFileA(path, GENERIC_READ, 0, NULL, OPEN_EXISTING, 0, NULL);
        CHECK(lock != INVALID_HANDLE_VALUE, "the log can be locked for the test");
        villager(8, "Napa", 380, 28, 9);
        conceive(8, 1);
        CHECK(write(3, records, rec(8), rec(1)) == 1, "a conception during the lock is kept");
        villager(9, "Lomai", 466, 7, 0);
        conceive(9, 1);
        CHECK(write(3, records, rec(9), rec(1)) == 1, "a second one during the lock is kept");
        (void)save(VILLAGE);                 /* a save while the log is still locked */
        CloseHandle(lock);
        CHECK(read_log() && count("Conception ") == 4, "nothing reached the locked log");
        CHECK(save(VILLAGE) == 1, "the next save succeeds");
        CHECK(read_log() && count("Conception ") == 6, "both held conceptions are written after it");
        CHECK(strstr(logtext, "Conception 5\r\n  Mother: Napa\r\n") != NULL
              && strstr(logtext, "Conception 6\r\n  Mother: Lomai\r\n") != NULL,
              "in the order they happened");
        CHECK(count("Village: ") == 1, "still exactly one header");
    }

    printf("-- Start Over: a simulation, then a new tribe, while the old header is still published --\n");
    memset(records, 0, BASE + SLOTS * STRIDE);
    villager(0, "Moana", 470, 5, 5);
    villager(1, "Rua", 460, 6, 6);
    conceive(0, 1);
    CHECK(write(3, records, rec(0), rec(1)) == 1, "a simulated conception is accepted");
    memset(records, 0, BASE + SLOTS * STRIDE);
    villager(0, "Vaea", 420, 11, 5);
    villager(1, "Tane", 450, 3, 17);
    conceive(0, 1);
    CHECK(write(3, records, rec(0), rec(1)) == 1, "the new tribe's conception is accepted");
    CHECK(read_log() && count("Conception ") == 6 && strstr(logtext, "Vaea") == NULL
          && strstr(logtext, "Moana") == NULL,
          "neither is written under the OLD tribe's header");
    vv_village_publish(VILLAGE2);
    CHECK(save(VILLAGE2) == 1, "the new tribe's first save");
    CHECK(read_log() && count("Conception ") == 6 && strstr(logtext, "Vaea") == NULL,
          "the old tribe's log is untouched");
    CHECK(read_log_n(2) && strncmp(logtext, "Village: Second Tribe (Save 2)\r\n", 32) == 0,
          "the new tribe gets its own headed log");
    CHECK(strstr(logtext, "  Mother: Vaea\r\n") != NULL, "its conception is filed there");
    CHECK(strstr(logtext, "Moana") == NULL, "the simulated one is dropped");

    printf("-- all five games: a replaced table is dropped; growth, de-aging, restyling and renames are not --\n");
    {
        /* Each game's own record geometry, from the export DLL's GAME_LAYOUTS. */
        static const struct {
            int game; unsigned int stride, slots, base, active, age, head, body,
                name, cap, likes, father_of, mother_of, parent_cap;
            const char *title;
        } G[5] = {
            {1, 0x3D8, 256, 0, 0x28, 0x348, 0x360, 0x364, 0x370, 0x1C, 0x398, 0, 0, 0,
             "Virtual Villagers 1 Births and Conceptions Log"},
            {2, 0xE48C, 256, 0, 0x30, 0x530, 0x548, 0x54C, 0x564, 0x18, 0x5F0, 0x57D, 0x596, 0x18,
             "Virtual Villagers 2 Births and Conceptions Log"},
            {3, 0x1F8C, 150, 0x14, 0xF10, 0xDC4, 0xDF0, 0xDF4, 0xDD4, 0x19, 0xFB4, 0xDF8, 0xE11, 0x19,
             "Virtual Villagers 3 Births and Conceptions Log"},
            {4, 0x2E3C, 150, 0x44, 0x1CC4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B9C, 0x19, 0x1E60, 0x1BC0, 0x1BD9, 0x19,
             "Virtual Villagers 4 Births and Conceptions Log"},
            {5, 0x2F44, 150, 0x48, 0x1CD4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B9C, 0x19, 0x1F5C, 0x1BC0, 0x1BD9, 0x19,
             "Virtual Villagers 5 Births and Conceptions Log"},
        };
        int k;
        for (k = 0; k < 5; ++k) {
            size_t bytes = G[k].base + G[k].slots * G[k].stride;
            unsigned char *t = (unsigned char *)calloc(1, bytes);
            char village[64], path[MAX_PATH], text[1 << 14];
            FILE *f;
            size_t n;
#define GREC(i) (t + G[k].base + (i) * G[k].stride)
#define GPUT(i, nm, a, h, b, pa, ma) do { unsigned char *r_ = GREC(i); \
                r_[G[k].active] = 1; *(int *)(r_ + G[k].age) = (a); \
                *(int *)(r_ + G[k].head) = (h); *(int *)(r_ + G[k].body) = (b); \
                memset(r_ + G[k].name, 0, G[k].cap); strncpy((char *)r_ + G[k].name, (nm), G[k].cap); \
                *(int *)(r_ + G[k].likes) = -1; \
                if (G[k].father_of) { strncpy((char *)r_ + G[k].father_of, (pa), G[k].parent_cap); \
                                      strncpy((char *)r_ + G[k].mother_of, (ma), G[k].parent_cap); } } while (0)
            /* The game's pre-tribe simulation. */
            GPUT(0, "Makawa", 487, 24, 20, "", "");
            GPUT(1, "Kao", 434, 22, 2, "", "");
            GPUT(2, "Tufi", 453, 22, 3, "", "");
            (void)write(G[k].game, t, GREC(0), GREC(1));
            /* The tribe replaces the whole table. */
            memset(t, 0, bytes);
            GPUT(0, "Kuka", 501, 7, 2, "", "");
            GPUT(1, "Yap", 565, 24, 0, "", "");
            GPUT(2, "Epeli", 0, 16, 15, "Yap", "Kuka");
            GPUT(3, "Paka", 542, 9, 2, "", "");
            (void)write(G[k].game, t, GREC(0), GREC(1));
            (void)birth(G[k].game, "", -1, -1, "Kuka", 7, 2, "Yap", 24, 0, GREC(2));
            /* Before the save: Epeli grows, takes up a like, is de-aged by an
               event and restyled; the player renames Kuka. */
            *(int *)(GREC(2) + G[k].age) = 60;
            *(int *)(GREC(2) + G[k].likes) = 5;
            *(int *)(GREC(2) + G[k].head) = 9;
            *(int *)(GREC(2) + G[k].body) = 11;
            memset(GREC(0) + G[k].name, 0, G[k].cap);
            strncpy((char *)GREC(0) + G[k].name, "Kukana", G[k].cap);
            _snprintf(village, sizeof village, "Village: Game %d Tribe (Save 3)\n", G[k].game);
            vv_village_publish(village);
            if (ensure_village != NULL) {
                (void)ensure_village(G[k].game, village, t);
            } else {
                (void)ensure(G[k].game, village);    /* a DLL that predates it */
            }
            /* The village's own log: another village may already own log 1
               (VV3's earlier phases do), and this one then rolls to a new file. */
            text[0] = 0;
            {
                int number;
                for (number = 1; number <= 5
                     && strncmp(text, village, strlen(village) - 1) != 0; ++number) {
                    _snprintf(path, MAX_PATH, "%s\\%s %d.txt", folder, G[k].title, number);
                    text[0] = 0;
                    f = fopen(path, "rb");
                    if (f) { n = fread(text, 1, sizeof text - 1, f); text[n] = 0; fclose(f); }
                }
            }
            CHECK(strncmp(text, "Village: Game ", 14) == 0, "VV%d: the log opens with the Village header", G[k].game);
            CHECK(strstr(text, "  Mother: Kuka\r\n") != NULL,
                  "VV%d: the tribe's conception is logged although the mother was renamed", G[k].game);
            CHECK(strstr(text, "Birth\r\n  Child: Epeli\r\n") != NULL,
                  "VV%d: a child who grew, took up a like, was de-aged and restyled is logged", G[k].game);
            CHECK(strstr(text, "Makawa") == NULL,
                  "VV%d: the simulation's conception is dropped (its table was replaced)", G[k].game);
#undef GPUT
#undef GREC
            free(t);
        }
    }

    FreeLibrary(dll);
    free(records);
    remove_logs();
    DeleteFileA(marker);
    printf("== %d failure(s) ==\n", failures);
    return failures == 0 ? 0 : 1;
}
