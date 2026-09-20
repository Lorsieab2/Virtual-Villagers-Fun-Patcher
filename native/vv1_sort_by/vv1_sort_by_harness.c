/* Runtime harness for "VVFP VV1 Sort By.dll".  32-bit only.

   Drives the ordering and the arrow stepping through the test seams over a
   synthetic 256-record array laid out like A New Home's (stride 0x3D8,
   occupied +0x28, health +0x344, age +0x348, skills +0x3BC x5).  The expected
   answers are the later games' rule as measured live in The Secret City:
   ascending key, index tie-break, a position that survives a mode change.

   Usage:  vv1_sort_by_harness.exe "<path to VVFP VV1 Sort By.dll>"
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
#define HEALTH 0x344
#define AGE 0x348
#define SKILLS 0x3BC

typedef int (__stdcall *reset_t)(int);
typedef int (__stdcall *setmode_t)(int);
typedef int (__stdcall *step_t)(const void *, int, int, int);
typedef int (__stdcall *list_t)(const void *, int, int *, int);
typedef int (__stdcall *hit_t)(int, int);

static unsigned char records[COUNT * STRIDE];
static unsigned char *rec(int i) { return records + i * STRIDE; }
static void villager(int i, int age, int health, int s0, int s1, int s2, int s3, int s4) {
    memset(rec(i), 0, STRIDE);
    rec(i)[OCC] = 1;
    *(int *)(rec(i) + AGE) = age;
    *(int *)(rec(i) + HEALTH) = health;
    *(int *)(rec(i) + SKILLS + 0) = s0; *(int *)(rec(i) + SKILLS + 4) = s1; *(int *)(rec(i) + SKILLS + 8) = s2;
    *(int *)(rec(i) + SKILLS + 12) = s3; *(int *)(rec(i) + SKILLS + 16) = s4;
}
static int same(const int *a, const int *b, int n) { int i; for (i = 0; i < n; ++i) if (a[i] != b[i]) return 0; return 1; }

int main(int argc, char **argv) {
    HMODULE dll; reset_t reset; setmode_t setmode; step_t step; list_t list; hit_t hit;
    int out[COUNT];
    if (argc < 2) { printf("usage: harness <dll>\n"); return 2; }
    dll = LoadLibraryA(argv[1]);
    CHECK(dll != NULL, "DLL loads");
    if (!dll) return 1;
    reset = (reset_t)GetProcAddress(dll, "Vv1SortByProbeReset");
    setmode = (setmode_t)GetProcAddress(dll, "Vv1SortByProbeSetMode");
    step = (step_t)GetProcAddress(dll, "Vv1SortByProbeStep");
    list = (list_t)GetProcAddress(dll, "Vv1SortByProbeList");
    hit = (hit_t)GetProcAddress(dll, "Vv1SortByProbeHit");
    CHECK(reset && setmode && step && list && hit, "probe seams resolve");
    CHECK(GetProcAddress(dll, "Vv1SortByStep") && GetProcAddress(dll, "Vv1SortByDraw") && GetProcAddress(dll, "Vv1SortByMode"), "game exports resolve");
    if (!(reset && setmode && step && list && hit)) return 1;

    printf("== a village ==\n");
    memset(records, 0, sizeof records);
    /*        idx  age  hp   farm build res heal breed */
    villager(0,  690, 100,   0,   0,  0,  0,  92);   /* Watoto */
    villager(3,  400, 100, 100,   0,  0,  0,   0);
    villager(5,  690, 100, 100,  10,  0,  4,   7);   /* same age as 0 */
    villager(7, 1113, 100,   0,  31,  0,  5,  98);   /* Yasawa */
    villager(9,  996,  98, 100,  27,  5,  0,   0);   /* the one sick villager */
    villager(12, 133, 100,   0,   0,  7,  7,   0);   /* Moka: max 7 */
    villager(20,  63, 100,   0,   0,  0,  7,   0);   /* Tautai: max 7 */
    villager(30, 500,   0, 100, 100, 100, 100, 100); /* dead: health 0, never listed */
    villager(40, 800, 100,  50,  50, 50, 50,  50);
    rec(50)[OCC] = 0;                                /* empty */

    {
        int exp_age[] = {20, 12, 3, 0, 5, 40, 9, 7};
        int exp_skill[] = {12, 20, 40, 7, 3, 5, 9, 0};   /* 7,7,50,98,100,100,100,92 -> 7(12) 7(20) 50 92(0)? see below */
        int n;
        /* Skill: max skill ascending, index ties: 12:7, 20:7, 40:50, 0:92, 7:98, 3:100, 5:100, 9:100 */
        int exp_skill_true[] = {12, 20, 40, 0, 7, 3, 5, 9};
        int exp_health[] = {9, 0, 3, 5, 7, 12, 20, 40};  /* 98 first, then 100s by index */
        (void)exp_skill;
        n = list(records, 0, out, COUNT);
        CHECK(n == 8 && same(out, exp_age, 8), "Age: ascending age, index tie-break, the dead and the empty left out (n=%d: %d %d %d %d %d %d %d %d)", n, out[0], out[1], out[2], out[3], out[4], out[5], out[6], out[7]);
        n = list(records, 1, out, COUNT);
        CHECK(n == 8 && same(out, exp_skill_true, 8), "Skill: highest skill ascending, index tie-break (%d %d %d %d %d %d %d %d)", out[0], out[1], out[2], out[3], out[4], out[5], out[6], out[7]);
        n = list(records, 2, out, COUNT);
        CHECK(n == 8 && same(out, exp_health, 8), "Health: health ascending, index tie-break (%d %d %d %d %d %d %d %d)", out[0], out[1], out[2], out[3], out[4], out[5], out[6], out[7]);
    }

    printf("== the arrows walk the order and wrap ==\n");
    reset(0);
    CHECK(step(records, 0, 99, +1) == 5, "from Watoto [0] (age 690, position 3) right -> [5] (690, same age, higher index)");
    CHECK(step(records, 5, 99, +1) == 40, "right again -> [40] (800)");
    CHECK(step(records, 40, 99, +1) == 9, "-> [9] (996)");
    CHECK(step(records, 9, 99, +1) == 7, "-> [7] (1113, the oldest)");
    CHECK(step(records, 7, 99, +1) == 20, "-> wraps to [20] (63, the youngest)");
    CHECK(step(records, 20, 99, -1) == 7, "left from the youngest wraps back to the oldest");
    CHECK(step(records, 7, 99, -1) == 9, "left -> [9]");

    printf("== a selection made elsewhere resyncs the position ==\n");
    CHECK(step(records, 12, 99, +1) == 3, "the player clicked Moka [12] (position 1): right -> [3] (400)");

    printf("== changing the order keeps the position, as in the later games ==\n");
    reset(0);
    step(records, 20, 99, +1);   /* age list: 20 12 3 0 5 40 9 7 -> position 1 = [12] */
    CHECK(step(records, 12, 99, +1) == 3, "age: position 2 = [3]");
    setmode(1);                  /* skill list: 12 20 40 0 7 3 5 9; position stays 2 */
    CHECK(step(records, 3, 99, +1) == 0, "switched to Skill without moving: next press shows skill position 3 = [0], not the villager after [3]");
    setmode(2);                  /* health list: 9 0 3 5 7 12 20 40; position stays 3 */
    CHECK(step(records, 0, 99, +1) == 7, "switched to Health: next press shows health position 4 = [7]");

    printf("== nothing to list ==\n");
    memset(records, 0, sizeof records);
    reset(0);
    CHECK(step(records, -1, 99, +1) == 99, "an empty village hands back the stock candidate");
    CHECK(step(NULL, -1, 99, +1) == 99, "no records: the stock candidate");

    printf("== the click map ==\n");
    CHECK(hit(6 + 30, 499 + 8) == 0 && hit(94 + 30, 499 + 8) == 1 && hit(182 + 30, 499 + 8) == 2, "each plate answers its order");
    CHECK(hit(6 + 60 + 4 + 8, 499 + 8) == 0 && hit(6 + 60 + 4 + 30, 499 + 8) == 0, "the radio beside a plate answers the same order");
    CHECK(hit(6 + 30, 300) == -1 && hit(400, 499 + 8) == -1, "outside the band: nothing");

    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
