/* Runtime harness for "VVFP VV1 Parentage.dll".  32-bit only.

   Drives the companion's inference through its test seams over a synthetic
   256-record array laid out exactly like A New Home's (stride 0x3D8,
   occupied +0x28, age +0x348, litter +0x35C, head +0x360, body +0x364,
   variant +0x36C, name +0x370, the conception scalar +0x390).  A birth is
   modelled the way sub_43C350 does it: a fresh record with random looks --
   never the mother's -- whose +0x36C is her +0x390 and whose age is 2.  The seams run the same code as the game
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
#define DUE 0x358
#define LITTER 0x35C
#define HEAD 0x360
#define BODY 0x364
#define VARIANT 0x36C
#define LEGACY 0x390     /* stored against the mother at conception; sub_43C350 copies it into her child's +0x36C */
#define NAME 0x370
#define GENDER 0x350

typedef int (__stdcall *reset_t)(void);
typedef int (__stdcall *conceive_t)(const void *, const void *, const void *);
typedef int (__stdcall *tick_t)(const void *);
typedef int (__stdcall *born_t)(const void *, const void *, const void *);
typedef int (__stdcall *entry_t)(int, int *);
typedef int (__stdcall *names_t)(int, char *, char *, int);
typedef int (__stdcall *births_t)(int *, int);
typedef int (__stdcall *layout_t)(int *, int *, unsigned int *);
typedef int (__stdcall *roster_t)(const void *, void *);
typedef int (__stdcall *overlap_t)(const void *, const void *);
typedef int (__stdcall *sync_t)(int, const void *);
typedef int (__stdcall *bind_t)(const void *);

static unsigned char records[COUNT * STRIDE];
static unsigned char *rec(int i) { return records + i * STRIDE; }
static void villager(int i, const char *name, int head, int body, int variant) {
    memset(rec(i), 0, STRIDE);
    rec(i)[OCC] = 1;
    *(int *)(rec(i) + HEAD) = head;
    *(int *)(rec(i) + BODY) = body;
    *(int *)(rec(i) + VARIANT) = variant;
    *(int *)(rec(i) + LEGACY) = -1;             /* never conceived: nothing to hand a child */
    *(int *)(rec(i) + AGE) = 25 * 20;
    strncpy((char *)rec(i) + NAME, name, 28);   /* a 28-byte name leaves no terminator, like the game's buffer */
}
static int looks_counter;
/* As sub_43C350 creates a child: a fresh record, head and body rolled (never
   the mother's), +0x36C copied from the mother's +0x390, age 2 years. */
static void born_from(int child, int mother, const char *name) {
    memset(rec(child), 0, STRIDE);
    rec(child)[OCC] = 1;
    *(int *)(rec(child) + HEAD) = 13 + (looks_counter % 5);
    *(int *)(rec(child) + BODY) = 17 + (looks_counter % 7);
    ++looks_counter;
    *(int *)(rec(child) + VARIANT) = *(int *)(rec(mother) + LEGACY);
    *(int *)(rec(child) + AGE) = 2 * 20;
    strncpy((char *)rec(child) + NAME, name, 28);
}
typedef int (__stdcall *conceive_fn)(const void *, const void *, const void *);
/* As a conception does it: the game stores the father's scalar against the
   mother (0x43BC10) and the companion stashes him. */
static int conceived(conceive_fn conceive, int mother, int father) {
    *(int *)(rec(mother) + LEGACY) = *(int *)(rec(father) + VARIANT);
    return conceive(records, rec(mother), rec(father));
}
static int same(const int *e, int fh, int fb, int mh, int mb) {
    return e[0] == fh && e[1] == fb && e[2] == mh && e[3] == mb;
}

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IONBF, 0);   /* every line reaches the console even if a check crashes */
    HMODULE dll; reset_t reset; conceive_t conceive; tick_t tick; entry_t entry; names_t names; births_t births; layout_t layout; born_t born; roster_t roster; overlap_t overlap; sync_t sync; bind_t bind;
    static unsigned char fp[256 * 64];
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
    born = (born_t)GetProcAddress(dll, "Vv1ParentageProbeBorn");
    roster = (roster_t)GetProcAddress(dll, "Vv1ParentageProbeRoster");
    overlap = (overlap_t)GetProcAddress(dll, "Vv1ParentageProbeOverlap");
    sync = (sync_t)GetProcAddress(dll, "Vv1ParentageProbeSync");
    bind = (bind_t)GetProcAddress(dll, "Vv1ParentageProbeBind");
    CHECK(reset && conceive && tick && entry && names && births && layout && born && roster && overlap && sync && bind, "probe seams resolve");
    CHECK(GetProcAddress(dll, "Vv1ParentageConceived") && GetProcAddress(dll, "Vv1ParentageTick")
          && GetProcAddress(dll, "Vv1ParentageDrawPortrait") && GetProcAddress(dll, "Vv1ParentageQuery")
          && GetProcAddress(dll, "Vv1ParentageQueryNames") && GetProcAddress(dll, "Vv1ParentageBorn"), "game exports resolve");
    if (!(reset && conceive && tick && entry && names && births && layout)) return 1;

    layout(&entry_bytes, &entries, &magic);
    CHECK(entry_bytes == 92 && entries == 256 && magic == 0x32305056u,
          "sidecar layout: 256 entries of 92 bytes under VP02 (got %d x %d, %08X)", entries, entry_bytes, magic);

    printf("== a village: mother Aisha [1] (head 4, body 9, variant 17), father Goro [2] (7, 2) ==\n");
    memset(records, 0, sizeof records);
    villager(0, "Bomani", 1, 1, 5); villager(1, "Aisha", 4, 9, 17); villager(2, "Goro", 7, 2, 30); villager(3, "Zero", 0, 0, 44);   /* head 0 / body 0 is a real look */
    reset();
    CHECK(tick(records) == 0, "first tick takes the baseline and infers nothing");
    entry(1, e); CHECK(same(e, -1, -1, -1, -1), "founders have unknown parents");
    names(1, father, mother, 32); CHECK(father[0] == 0 && mother[0] == 0, "founders have no parent names");

    printf("== conception: Goro fathers the twins of Aisha ==\n");
    CHECK(conceived(conceive, 1, 2) == 1, "stash keyed by the index of the mother (1)");
    CHECK(conceive(records, rec(1) + 4, rec(2)) == -1, "a pointer off a record boundary is refused");
    *(int *)(rec(1) + LITTER) = 2;
    CHECK(tick(records) == 0, "pregnancy in progress: nothing changes");
    CHECK(births(NULL, 0) == 0, "no births seen");

    printf("== delivery: litter 2 -> 0 and two new records, same frame ==\n");
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
    entry(12, e); CHECK(same(e, -1, -1, 4, 9), "a later birth with no new conception: mother known, father blank (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    names(12, father, mother, 32); CHECK(father[0] == 0 && strcmp(mother, "Aisha") == 0, "...no father name, mother %s", mother);
    CHECK(births(b, 8) == 1 && b[0] == 12 && b[1] == 1, "one birth seen this frame");

    printf("== a founder appears with nobody delivering ==\n");
    villager(20, "Immigrant", 12, 12, 3); tick(records);
    entry(20, e); CHECK(same(e, -1, -1, -1, -1), "no delivering mother: unknown parents");
    CHECK(births(b, 8) == 1 && b[0] == 20 && b[1] == -1, "the arrival is reported with mother -1");

    printf("== an adult who appears during a delivery is not her child ==\n");
    conceived(conceive, 1, 2);
    *(int *)(rec(1) + LITTER) = 1; tick(records);
    *(int *)(rec(1) + LITTER) = 0; born_from(14, 1, "Grown"); *(int *)(rec(14) + AGE) = 30 * 20; tick(records);
    entry(14, e); CHECK(same(e, -1, -1, -1, -1), "a 30-year-old arrival during her delivery gets no parents (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    CHECK(births(b, 8) == 1 && b[0] == 14 && b[1] == -1, "...and is reported with mother -1, so it is never logged");
    born_from(15, 1, "Late"); tick(records);
    entry(15, e); CHECK(same(e, -1, -1, -1, -1), "a newborn a frame later has no delivering mother: unknown");

    printf("== twins delivered one per frame: litter 2 -> 1 -> 0 ==\n");
    conceived(conceive, 1, 2);
    *(int *)(rec(1) + LITTER) = 2; tick(records);
    *(int *)(rec(1) + LITTER) = 1; born_from(16, 1, "TwinA"); tick(records);
    entry(16, e); CHECK(same(e, 7, 2, 4, 9), "the first twin, while the counter is still 1, gets both parents (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    *(int *)(rec(1) + LITTER) = 0; born_from(17, 1, "TwinB"); tick(records);
    entry(17, e); CHECK(same(e, 7, 2, 4, 9), "the second twin, a frame later, gets the same two parents (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    names(17, father, mother, 32); CHECK(strcmp(father, "Goro") == 0 && strcmp(mother, "Aisha") == 0, "...by name too: %s / %s", father, mother);
    *(int *)(rec(1) + LITTER) = 1; tick(records); *(int *)(rec(1) + LITTER) = 0; born_from(18, 1, "After"); tick(records);
    entry(18, e); CHECK(same(e, -1, -1, 4, 9), "the stash was spent when the counter reached zero: the next birth has no father (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);

    printf("== a single baby: the litter counter never moves, only the due field ==\n");
    conceived(conceive, 1, 2);
    *(int *)(rec(1) + DUE) = 500; tick(records);
    CHECK(births(NULL, 0) == 0, "pregnant with one: nothing yet");
    *(int *)(rec(1) + DUE) = 0; born_from(19, 1, "Solo"); tick(records);
    entry(19, e); CHECK(same(e, 7, 2, 4, 9), "the single child gets both parents from the due field alone (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    *(int *)(rec(1) + DUE) = 600; tick(records); *(int *)(rec(1) + DUE) = 0; born_from(21, 1, "Next"); tick(records);
    entry(21, e); CHECK(same(e, -1, -1, 4, 9), "...and the stash was spent with it: no father (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);

    printf("== a slot freed and refilled between two frames ==\n");
    villager(12, "Stranger", 1, 2, 3); tick(records);   /* occupied in both snapshots, different name and variant */
    entry(12, e); CHECK(same(e, -1, -1, -1, -1), "the new tenant of a slot occupied in both frames starts unknown (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    conceived(conceive, 1, 2); *(int *)(rec(1) + DUE) = 700; tick(records);
    *(int *)(rec(1) + DUE) = 0; born_from(13, 1, "Reborn"); tick(records);   /* slot 13 was Zed, occupied: only the name differs */
    entry(13, e); CHECK(same(e, 7, 2, 4, 9), "a newborn refilling an occupied slot in the delivery frame is matched by its new name (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    names(13, father, mother, 32); CHECK(strcmp(father, "Goro") == 0, "...with the father from the stash (%s)", father);

    printf("== the exact birth hook: child and mother handed over by the executable ==\n");
    conceived(conceive, 1, 2);
    *(int *)(rec(1) + DUE) = 800; tick(records);
    born_from(22, 1, "Hooked");                                   /* created and named by sub_43C350 */
    CHECK(born(records, rec(22), rec(1)) == 22, "the hook records by index (22)");
    entry(22, e); CHECK(same(e, 7, 2, 4, 9), "child [22]: both parents from the hook (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    names(22, father, mother, 32); CHECK(strcmp(father, "Goro") == 0 && strcmp(mother, "Aisha") == 0, "...with names %s / %s", father, mother);
    CHECK(tick(records) == 0, "the next frame does not treat the hooked child as a new unknown occupant");
    entry(22, e); CHECK(same(e, 7, 2, 4, 9), "...and its entry is intact");
    born_from(23, 1, "HookedTwin"); born(records, rec(23), rec(1));
    entry(23, e); CHECK(same(e, 7, 2, 4, 9), "a twin through the hook gets the same father: the stash is not spent by the hook");
    *(int *)(rec(1) + DUE) = 0; tick(records);
    entry(1, e); CHECK(same(e, -1, -1, -1, -1), "(the mother is untouched)");
    born_from(24, 1, "Later"); born(records, rec(24), rec(1)); entry(24, e); CHECK(same(e, -1, -1, 4, 9), "after the delivery ended the stash is spent: mother only (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    CHECK(born(records, rec(1), rec(1)) == -1, "child == mother is refused");
    CHECK(born(records, rec(1) + 4, rec(2)) == -1, "an unaligned pointer is refused");

    printf("== father with head 0 / body 0 is a real father ==\n");
    conceived(conceive, 1, 3);
    *(int *)(rec(1) + LITTER) = 1; tick(records);
    *(int *)(rec(1) + LITTER) = 0; born_from(13, 1, "Zed"); tick(records);
    entry(13, e); CHECK(same(e, 0, 0, 4, 9), "child [13]: father (0,0) recorded as 0, not unknown (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    names(13, father, mother, 32); CHECK(strcmp(father, "Zero") == 0, "child [13] father name %s", father);

    printf("== two mothers deliver in one frame ==\n");
    villager(30, "Ama", 20, 21, 70); villager(31, "Bea", 22, 23, 71); tick(records);
    conceived(conceive, 30, 2); conceived(conceive, 31, 0);   /* different fathers: their scalars tell the children apart */
    *(int *)(rec(30) + LITTER) = 1; *(int *)(rec(31) + LITTER) = 1; tick(records);
    *(int *)(rec(30) + LITTER) = 0; *(int *)(rec(31) + LITTER) = 0; born_from(40, 30, "Cy"); born_from(41, 31, "Di"); tick(records);
    entry(40, e); CHECK(same(e, 7, 2, 20, 21), "child of [30] gets Goro and [30] (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    entry(41, e); CHECK(same(e, 1, 1, 22, 23), "child of [31] gets [0] and [31] (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    names(41, father, mother, 32); CHECK(strcmp(father, "Bomani") == 0 && strcmp(mother, "Bea") == 0, "child of [31] names %s / %s", father, mother);

    printf("== two mothers with the same father deliver in one frame: ambiguous, so unknown ==\n");
    villager(50, "Twin1", 5, 5, 9); villager(51, "Twin2", 5, 5, 9); tick(records);
    conceived(conceive, 50, 2); conceived(conceive, 51, 2);   /* the same scalar reaches both children */
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
    conceived(conceive, 70, 71);
    *(int *)(rec(70) + LITTER) = 1; tick(records);
    *(int *)(rec(70) + LITTER) = 0; born_from(72, 70, "Kid"); tick(records);
    names(72, father, mother, 32); CHECK(strlen(father) == 27 && strncmp(father, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0", 27) == 0, "father name cut to 27: %s", father);
    names(72, father, mother, 5); CHECK(strlen(father) == 4, "a small caller buffer is honoured (%s)", father);

    printf("== the village is its living roster ==\n");
    memset(records, 0, sizeof records);
    villager(0, "Bomani", 1, 1, 5); villager(1, "Aisha", 4, 9, 17); villager(2, "Goro", 7, 2, 30);
    *(int *)(rec(0) + GENDER) = 1; *(int *)(rec(2) + GENDER) = 1; *(int *)(rec(1) + GENDER) = 2;
    CHECK(roster(records, fp) == 36, "an occupant fingerprint is 36 bytes");
    CHECK(overlap(records, fp) == 1, "a village matches its own roster");
    *(int *)(rec(0) + HEAD) = 19; *(int *)(rec(0) + BODY) = 19; *(int *)(rec(1) + HEAD) = 18; *(int *)(rec(2) + BODY) = 18;
    CHECK(overlap(records, fp) == 1, "changing everyone's head and body (the Origins upgrades) does not make it another village");
    rec(0)[OCC] = 0; rec(2)[OCC] = 0; born_from(9, 1, "Kai"); *(int *)(rec(9) + GENDER) = 1;
    CHECK(overlap(records, fp) == 1, "two deaths and a birth: still the same village while Aisha lives");
    rec(1)[OCC] = 0;
    CHECK(overlap(records, fp) == 0, "every recorded villager dead and a stranger in the array: another village");
    villager(0, "Bomani", 1, 1, 5); *(int *)(rec(0) + GENDER) = 2;
    CHECK(overlap(records, fp) == 0, "the same name at the same slot with the other gender is not him");
    *(int *)(rec(0) + GENDER) = 1; *(int *)(rec(0) + VARIANT) = 6;
    CHECK(overlap(records, fp) == 0, "...nor with another family scalar");
    *(int *)(rec(0) + VARIANT) = 5;
    CHECK(overlap(records, fp) == 1, "name, gender and scalar at the slot: him");
    memset(records, 0, sizeof records);
    CHECK(overlap(records, fp) == -1, "nobody on screen: no verdict (the array is being rebuilt)");
    villager(0, "Bomani", 1, 1, 5);
    memset(fp, 0, sizeof fp);
    CHECK(overlap(records, fp) == -1, "an empty roster has nothing to contradict");
    /* Start Over: same slot, new founders with fresh names */
    roster(records, fp);
    memset(records, 0, sizeof records);
    villager(0, "Tane", 2, 2, 5); villager(1, "Moa", 3, 3, 9); *(int *)(rec(0) + GENDER) = 1;
    CHECK(overlap(records, fp) == 0, "Start Over in the same slot: nobody in common, so another village");

    printf("== the sync: no mutation while the roster verdict is unsettled ==\n");
    /* Village A, bound to its table: Aisha and Goro, with Kai their child. */
    reset();
    memset(records, 0, sizeof records);
    villager(0, "Bomani", 1, 1, 5); villager(1, "Aisha", 4, 9, 7); villager(2, "Goro", 7, 2, 3);
    *(int *)(rec(2) + GENDER) = 1;
    CHECK(sync(1, records) == 1, "a village with no table yet is identified: recording may begin");
    conceive(records, rec(1), rec(2));
    *(int *)(rec(1) + LITTER) = 1; tick(records); *(int *)(rec(1) + LITTER) = 0; born_from(9, 1, "Kai"); tick(records);
    entry(9, e); CHECK(same(e, 7, 2, 4, 9), "Kai has both parents (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    bind(records);
    CHECK(sync(1, records) == 1, "the village matches its own table: identified");
    /* Start Over in the same slot: strangers, nobody in common. */
    memset(records, 0, sizeof records);
    villager(0, "Tane", 2, 2, 5); villager(1, "Moa", 3, 3, 9); *(int *)(rec(0) + GENDER) = 1;
    {
        int frame, settled = 1;
        for (frame = 1; frame < 30; ++frame) {
            if (sync(1, records) != 0) { settled = 0; break; }
        }
        CHECK(settled, "for 29 frames of strangers the sync answers 0: nothing is known, nothing is touched (broke at frame %d)", frame);
    }
    entry(9, e); CHECK(same(e, 7, 2, 4, 9), "...and Kai's parents are still in the table meanwhile (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    CHECK(sync(1, records) == 1, "the 30th frame: verdict final, the table is reloaded for the other village");
    entry(9, e); CHECK(same(e, -1, -1, -1, -1), "...which the old table does not serve: Kai's slot is empty for the new village (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    /* The same village, mid-rebuild: the array empties for a few frames. */
    reset();
    memset(records, 0, sizeof records);
    villager(0, "Bomani", 1, 1, 5); villager(1, "Aisha", 4, 9, 7); villager(2, "Goro", 7, 2, 3);
    *(int *)(rec(2) + GENDER) = 1;
    sync(1, records);
    conceive(records, rec(1), rec(2));
    *(int *)(rec(1) + LITTER) = 1; tick(records); *(int *)(rec(1) + LITTER) = 0; born_from(9, 1, "Kai"); tick(records);
    bind(records);

    {
        static unsigned char keep[COUNT * STRIDE];
        memcpy(keep, records, sizeof keep);
        memset(records, 0, sizeof records);
        CHECK(sync(1, records) == 0, "nobody on screen (the array is being rebuilt): nothing is known");
        CHECK(sync(1, records) == 0, "...for as long as that lasts");
        entry(9, e); CHECK(same(e, 7, 2, 4, 9), "...and the table is untouched (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
        memcpy(records, keep, sizeof keep);
        CHECK(sync(1, records) == 1, "the same villagers are back: identified again, no strikes were counted");
        entry(9, e); CHECK(same(e, 7, 2, 4, 9), "...with Kai's parents intact (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    }

    printf("== a slot change waits for the array to be rebuilt ==\n");
    /* Slot 2 is selected while the array is still empty from the previous
       village's teardown, then slot 2's own villagers appear.  The table must
       not be bound to slot 2 until somebody is actually there -- otherwise
       the sidecar is read against the wrong array, rejected, and the slot
       marked loaded anyway, so it is never retried.

       Nothing here may let the sync take its persist branch: vv1_parents_save
       reads the GAME's global array, which does not exist under the harness.
       Binding the roster to the array before each matching sync is what the
       scenarios above do for the same reason. */
    reset();
    memset(records, 0, sizeof records);
    villager(0, "Bomani", 1, 1, 5); villager(1, "Aisha", 4, 9, 7); villager(2, "Goro", 7, 2, 3);
    *(int *)(rec(2) + GENDER) = 1;
    bind(records);
    CHECK(sync(1, records) == 1, "slot 1 with its own villagers: identified");
    conceive(records, rec(1), rec(2));
    *(int *)(rec(1) + LITTER) = 1; tick(records); *(int *)(rec(1) + LITTER) = 0; born_from(9, 1, "Kai"); tick(records);
    bind(records);
    entry(9, e); CHECK(same(e, 7, 2, 4, 9), "slot 1: Kai has both parents (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    memset(records, 0, sizeof records);
    CHECK(sync(2, records) == 0, "the slot changed but the array is empty: nothing is known");
    CHECK(sync(2, records) == 0, "...for as long as the rebuild lasts");
    entry(9, e); CHECK(same(e, 7, 2, 4, 9), "...and slot 1's table is still intact meanwhile (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);
    villager(0, "Tane", 2, 2, 5); villager(1, "Moa", 3, 3, 9); *(int *)(rec(0) + GENDER) = 1;
    CHECK(sync(2, records) == 2, "slot 2's villagers are on screen: only now is the slot loaded");
    entry(9, e); CHECK(same(e, -1, -1, -1, -1), "...and slot 2 does not inherit slot 1's parents (%d,%d,%d,%d)", e[0], e[1], e[2], e[3]);

    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
