/* Runtime harness for "VVFP VV1 Parentage.dll".  32-bit only.

   Drives the companion's inference through its test seams over a synthetic
   256-record array laid out exactly like A New Home's (stride 0x3D8,
   occupied +0x28, age +0x348, litter +0x35C, head +0x360, body +0x364,
   variant +0x36C, name +0x370).  The seams run the same code as the game
   exports minus the file I/O, the log and the game globals, so nothing here
   touches the player's folders.

   Usage:  vv1_parentage_harness.exe "<path to VVFP VV1 Parentage.dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

#define STRIDE 0x3D8
#define COUNT 256
#define OCC 0x28
#define AGE 0x348
#define LITTER 0x35C
#define HEAD 0x360
#define BODY 0x364
#define VARIANT 0x36C
#define NAME 0x370

typedef int (__stdcall *reset_t)(void);
typedef int (__stdcall *conceive_t)(const void *, const void *, const void *);
typedef int (__stdcall *tick_t)(const void *);
typedef int (__stdcall *entry_t)(int, int *);
typedef int (__stdcall *names_t)(int, char *, char *, int);
typedef int (__stdcall *births_t)(int *, int);
typedef int (__stdcall *layout_t)(int *, int *, unsigned int *);

static unsigned char records[COUNT * STRIDE];
static unsigned char *rec(int i) { return records + i * STRIDE; }
static void villager(int i, const char *name, int head, int body, int variant) {
    memset(rec(i), 0, STRIDE);
    rec(i)[OCC] = 1;
    *(int *)(rec(i) + HEAD) = head;
    *(int *)(rec(i) + BODY) = body;
    *(int *)(rec(i) + VARIANT) = variant;
    strncpy((char *)rec(i) + NAME, name, 28);   /* a 28-byte name leaves no terminator, like the game's buffer */
}
static void born_from(int child, int mother, const char *name) {
    memset(rec(child), 0, STRIDE);
    rec(child)[OCC] = 1;
    *(int *)(rec(child) + HEAD) = *(int *)(rec(mother) + HEAD);
    *(int *)(rec(child) + BODY) = *(int *)(rec(mother) + BODY);
    *(int *)(rec(child) + VARIANT) = *(int *)(rec(mother) + VARIANT);
    strncpy((char *)rec(child) + NAME, name, 28);
}
static int same(const int *e, int fh, int fb, int mh, int mb) {
    return e[0] == fh && e[1] == fb && e[2] == mh && e[3] == mb;
}

int main(int argc, char **argv) {
    HMODULE dll; reset_t reset; conceive_t conceive; tick_t tick; entry_t entry; names_t names; births_t births; layout_t layout;
    int e[4];
    int b[8];
    char father[32], mother[32];
    int entry_bytes = 0, entries = 0; unsigned int magic = 0;
    if (argc < 2) { printf("usage: harness <dll>\n"); return 2; }
    dll = LoadLibraryA(argv[1]);
    CHECK(dll != NULL, "DLL loads");
    if (!dll) return 1;
    reset = (reset_t)GetProcAddress(dll, "Vv1ParentageProbeReset");
    conceive = (conceive_t)GetProcAddress(dll, "Vv1ParentageProbeConceive");
    tick = (tick_t)GetProcAddress(dll, "Vv1ParentageProbeTick");
    entry = (entry_t)GetProcAddress(dll, "Vv1ParentageProbeEntry");
    names = (names_t)GetProcAddress(dll, "Vv1ParentageProbeNames");
    births = (births_t)GetProcAddress(dll, "Vv1ParentageProbeBirths");
    layout = (layout_t)GetProcAddress(dll, "Vv1ParentageProbeLayout");
    CHECK(reset && conceive && tick && entry && names && births && layout, "probe seams resolve");
    CHECK(GetProcAddress(dll, "Vv1ParentageConceived") && GetProcAddress(dll, "Vv1ParentageTick")
          && GetProcAddress(dll, "Vv1ParentageDrawPortrait") && GetProcAddress(dll, "Vv1ParentageQuery")
          && GetProcAddress(dll, "Vv1ParentageQueryNames"), "game exports resolve");
    if (!(reset && conceive && tick && entry && names && births && layout)) return 1;

    layout(&entry_bytes, &entries, &magic);
    CHECK(entry_bytes == 92 && entries == 256 && magic == 0x31305056u,
          "sidecar layout: 256 entries of 92 bytes under VP01 (got %d x %d, %08X)", entries, entry_bytes, magic);

    printf("== a village: mother Aisha [1] (head 4, body 9, variant 17), father Goro [2] (7, 2) ==\n");
    memset(records, 0, sizeof records);
    villager(0, "Bomani", 1, 1, 5); villager(1, "Aisha", 4, 9, 17); villager(2, "Goro", 7, 2, 30); villager(3, "Zero", 0, 0, 44);   /* head 0 / body 0 is a real look */
    reset();
    CHECK(tick(records) == 0, "first tick takes the baseline and infers nothing");
    entry(1, e); CHECK(same(e, -1, -1, -1, -1), "founders have unknown parents");
    names(1, father, mother, 32); CHECK(father[0] == 0 && mother[0] == 0, "founders have no parent names");

    printf("== conception: Goro fathers the twins of Aisha ==\n");
    CHECK(conceive(records, rec(1), rec(2)) == 1, "stash keyed by the index of the mother (1)");
    CHECK(conceive(records, rec(1) + 4, rec(2)) == -1, "a pointer off a record boundary is refused");
    *(int *)(rec(1) + LITTER) = 2;
    CHECK(tick(records) == 0, "pregnancy in progress: nothing changes");
    CHECK(births(NULL, 0) == 0, "no births seen");

    printf("== delivery: litter 2 -> 0 and two new records copied from Aisha, same frame ==\n");
    *(int *)(rec(1) + LITTER) = 0;
    born_from(10, 1, "Kai"); born_from(11, 1, "Nia");
    CHECK(tick(records) == 1, "the frame changed the table");
    CHECK(births(b, 8) == 2 && b[0] == 10 && b[1] == 1 && b[2] == 11 && b[3] == 1,
          "two births seen, each with mother [1] (got %d: %d<-%d, %d<-%d)", births(NULL, 0), b[0], b[1], b[2], b[3]);
    entry(10, e); CHECK(same(e, 7, 2, 4, 9), "child [10]: father Goro (7,2), mother Aisha (4,9), got (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    entry(11, e); CHECK(same(e, 7, 2, 4, 9), "child [11]: same parents");
    names(10, father, mother, 32); CHECK(strcmp(father, "Goro") == 0 && strcmp(mother, "Aisha") == 0, "child [10] names: %s / %s", father, mother);
    names(11, father, mother, 32); CHECK(strcmp(father, "Goro") == 0 && strcmp(mother, "Aisha") == 0, "child [11] names: %s / %s", father, mother);
    entry(1, e);  CHECK(same(e, -1, -1, -1, -1), "the parents of the mother herself stay unknown (the stash is not her parentage)");
    /* the stash is spent */
    *(int *)(rec(1) + LITTER) = 1; tick(records); *(int *)(rec(1) + LITTER) = 0; born_from(12, 1, "Ola"); tick(records);
    entry(12, e); CHECK(same(e, -1, -1, 4, 9), "a later birth with no new conception: mother known, father unknown (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    names(12, father, mother, 32); CHECK(father[0] == 0 && strcmp(mother, "Aisha") == 0, "...and no father name, mother %s", mother);
    CHECK(births(b, 8) == 1 && b[0] == 12 && b[1] == 1, "one birth seen this frame");

    printf("== a founder appears with nobody delivering ==\n");
    villager(20, "Immigrant", 12, 12, 3); tick(records);
    entry(20, e); CHECK(same(e, -1, -1, -1, -1), "no delivering mother: unknown parents");
    CHECK(births(b, 8) == 1 && b[0] == 20 && b[1] == -1, "the arrival is reported with mother -1");

    printf("== an adult who appears during a delivery with the same look is not her child ==\n");
    conceive(records, rec(1), rec(2));
    *(int *)(rec(1) + LITTER) = 1; tick(records);
    *(int *)(rec(1) + LITTER) = 0; born_from(14, 1, "Grown"); *(int *)(rec(14) + AGE) = 30 * 20; tick(records);
    entry(14, e); CHECK(same(e, -1, -1, -1, -1), "a 30-year-old copy of the mother gets no parents (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    CHECK(births(b, 8) == 1 && b[0] == 14 && b[1] == -1, "...and is reported with mother -1, so it is never logged");
    born_from(15, 1, "Late"); tick(records);
    entry(15, e); CHECK(same(e, -1, -1, -1, -1), "a newborn copy a frame later has no delivering mother: unknown");

    printf("== twins delivered one per frame: litter 2 -> 1 -> 0 ==\n");
    conceive(records, rec(1), rec(2));
    *(int *)(rec(1) + LITTER) = 2; tick(records);
    *(int *)(rec(1) + LITTER) = 1; born_from(16, 1, "TwinA"); tick(records);
    entry(16, e); CHECK(same(e, 7, 2, 4, 9), "the first twin, while the counter is still 1, gets both parents (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    *(int *)(rec(1) + LITTER) = 0; born_from(17, 1, "TwinB"); tick(records);
    entry(17, e); CHECK(same(e, 7, 2, 4, 9), "the second twin, a frame later, gets the same two parents (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    names(17, father, mother, 32); CHECK(strcmp(father, "Goro") == 0 && strcmp(mother, "Aisha") == 0, "...by name too: %s / %s", father, mother);
    *(int *)(rec(1) + LITTER) = 1; tick(records); *(int *)(rec(1) + LITTER) = 0; born_from(18, 1, "After"); tick(records);
    entry(18, e); CHECK(same(e, -1, -1, 4, 9), "the stash was spent when the counter reached zero (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);

    printf("== father with head 0 / body 0 is a real father ==\n");
    conceive(records, rec(1), rec(3));
    *(int *)(rec(1) + LITTER) = 1; tick(records);
    *(int *)(rec(1) + LITTER) = 0; born_from(13, 1, "Zed"); tick(records);
    entry(13, e); CHECK(same(e, 0, 0, 4, 9), "child [13]: father (0,0) recorded as 0, not unknown (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    names(13, father, mother, 32); CHECK(strcmp(father, "Zero") == 0, "child [13] father name %s", father);

    printf("== two mothers deliver in one frame ==\n");
    villager(30, "Ama", 20, 21, 70); villager(31, "Bea", 22, 23, 71); tick(records);
    conceive(records, rec(30), rec(2)); conceive(records, rec(31), rec(0));
    *(int *)(rec(30) + LITTER) = 1; *(int *)(rec(31) + LITTER) = 1; tick(records);
    *(int *)(rec(30) + LITTER) = 0; *(int *)(rec(31) + LITTER) = 0; born_from(40, 30, "Cy"); born_from(41, 31, "Di"); tick(records);
    entry(40, e); CHECK(same(e, 7, 2, 20, 21), "child of [30] gets Goro and [30] (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    entry(41, e); CHECK(same(e, 1, 1, 22, 23), "child of [31] gets [0] and [31] (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    names(41, father, mother, 32); CHECK(strcmp(father, "Bomani") == 0 && strcmp(mother, "Bea") == 0, "child of [31] names %s / %s", father, mother);

    printf("== two look-alike mothers deliver in one frame: ambiguous, so unknown ==\n");
    villager(50, "Twin1", 5, 5, 9); villager(51, "Twin2", 5, 5, 9); tick(records);
    conceive(records, rec(50), rec(2)); conceive(records, rec(51), rec(0));
    *(int *)(rec(50) + LITTER) = 1; *(int *)(rec(51) + LITTER) = 1; tick(records);
    *(int *)(rec(50) + LITTER) = 0; *(int *)(rec(51) + LITTER) = 0; born_from(60, 50, "Ex"); tick(records);
    entry(60, e); CHECK(same(e, -1, -1, -1, -1), "cannot tell the mothers apart: left unknown rather than guessed");

    printf("== an entry outlives its villager ==\n");
    rec(10)[OCC] = 0; tick(records);
    entry(10, e); CHECK(same(e, 7, 2, 4, 9), "a dead villager keeps its entry while the slot is empty");
    names(10, father, mother, 32); CHECK(strcmp(father, "Goro") == 0, "...and its names");
    *(int *)(rec(11) + AGE) = 1000; tick(records);
    entry(11, e); CHECK(same(e, 7, 2, 4, 9), "growing up (age 1000) does not touch the entry");
    *(int *)(rec(11) + AGE) = 100; tick(records);
    entry(11, e); CHECK(same(e, 7, 2, 4, 9), "nor does growing young again");
    villager(10, "Newcomer", 9, 9, 9); tick(records);
    entry(10, e); CHECK(same(e, -1, -1, -1, -1), "a new occupant of the slot starts unknown");
    names(10, father, mother, 32); CHECK(father[0] == 0 && mother[0] == 0, "...with no names");

    printf("== a name that fills its buffer is cut at 27 characters ==\n");
    villager(70, "Mum", 30, 31, 80); villager(71, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", 32, 33, 81); tick(records);
    conceive(records, rec(70), rec(71));
    *(int *)(rec(70) + LITTER) = 1; tick(records);
    *(int *)(rec(70) + LITTER) = 0; born_from(72, 70, "Kid"); tick(records);
    names(72, father, mother, 32); CHECK(strlen(father) == 27 && strncmp(father, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0", 27) == 0, "father name cut to 27: %s", father);
    names(72, father, mother, 5); CHECK(strlen(father) == 4, "a small caller buffer is honoured (%s)", father);

    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
