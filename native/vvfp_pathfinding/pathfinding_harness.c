/* Runtime harness for "VVFP Improved Pathfinding.dll".  32-bit only.

   Drives the DLL's routing through its probe exports over synthetic grids
   laid out exactly as the games keep theirs -- A New Home's 168x168 DWORDs
   at [x * 168 + y], The Lost Children's at [x * 170 + y] with the field the
   follower reads -- and checks the routes a villager would be given:

     A New Home: each waypoint is the end of a straight run the stock walk
     can take without meeting a blocked cell; a wall is walked round; a
     corner between two obstacles is never cut; a goal on an obstacle's edge
     is approached from the open side and then left to the stock handler; a
     villager nudged onto a blocked cell is first brought back; an enclosed
     goal is refused so the stock handler runs.

     The Lost Children: the flood writes the field the way the game's
     follower reads it (goal 1, blocked 0x7FFE, unreached 0x7FFF, the outer
     ring blocked), no longer refuses a blocked goal, honours the goal-on-24
     rule; the descent walks a villager to the goal's exact point without
     entering a blocked cell except the goal, recovers from an unreached
     cell, and refuses to cut a corner.

   Usage:  pathfinding_harness.exe "<path to VVFP Improved Pathfinding.test.dll>"
   The probe exports it calls exist only in the TEST build
   (tests\test_dlls\, built with VVFP_TEST by the DLL's own build script);
   the shipped DLL exports none of them.
   Exit code 0 when every check passes. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures;
#define CHECK(cond, ...) do { \
        if (cond) { printf("  ok   "); } else { printf("  FAIL "); ++failures; } \
        printf(__VA_ARGS__); printf("\n"); } while (0)

typedef int (__stdcall *probe_vv1_t)(const unsigned int *, int, int, int, int, int *, int *);
typedef int (__stdcall *probe_vv2_flood_t)(const unsigned int *, int *, int, int);
typedef int (__stdcall *probe_vv2_next_t)(const unsigned int *, int *, int, int, int, int *);
typedef int (__stdcall *probe_site_t)(int, int, unsigned int *, unsigned char *, int);

static probe_vv1_t vv1_route;
static probe_vv2_flood_t vv2_flood;
static probe_vv2_next_t vv2_next;

/* ---- A New Home ---------------------------------------------------------- */
#define G1 168
static unsigned int grid1[G1 * G1];
static void vv1_clear(void) { memset(grid1, 0, sizeof grid1); }
static void vv1_block(int x, int y) { grid1[x * G1 + y] = 5; }
static int vv1_open(int x, int y) {
    unsigned int v;
    if (x < 0 || y < 0 || x >= G1 || y >= G1) return 0;
    v = grid1[x * G1 + y];
    return v < 1 || v > 14;
}
/* The stock walk's own test, step by step along the line, in feet pixels. */
static int vv1_line_clear(int x0, int y0, int x1, int y1) {
    int steps = abs(x1 - x0) > abs(y1 - y0) ? abs(x1 - x0) : abs(y1 - y0);
    int i;
    for (i = 0; i <= steps; ++i) {
        int x = x0 + (x1 - x0) * i / (steps ? steps : 1);
        int y = y0 + (y1 - y0) * i / (steps ? steps : 1);
        if (!vv1_open(x / 10, y / 10)) return 0;
    }
    return 1;
}
/* Walk as the game would: straight when clear, else ask for a corner and go
   there.  Returns the number of corners, -1 if a leg was not clear, -2 if a
   corner was refused before the goal became reachable, -3 on a runaway. */
static int vv1_walk(int fx, int fy, int gx, int gy, int *end_x, int *end_y) {
    int corners = 0;
    while (corners < 200) {
        int wx, wy;
        if (vv1_line_clear(fx, fy, gx, gy)) { *end_x = gx; *end_y = gy; return corners; }
        if (!vv1_route(grid1, fx, fy, gx, gy, &wx, &wy)) { *end_x = fx; *end_y = fy; return -2; }
        if (!vv1_line_clear(fx, fy, wx, wy)) { *end_x = wx; *end_y = wy; return -1; }
        fx = wx; fy = wy; ++corners;
    }
    return -3;
}

/* ---- The Lost Children --------------------------------------------------- */
#define G2 168
#define M2 170
static unsigned int grid2[G2 * M2];
static int field2[2 + (G2 * G2) / 2 + 1];
static unsigned short *words2 = (unsigned short *)(field2 + 2);
static void vv2_clear(void) { memset(grid2, 0, sizeof grid2); }
static void vv2_set(int x, int y, unsigned int v) { grid2[x * M2 + y] = v; }
static unsigned short vv2_at(int x, int y) { return words2[x + y * G2]; }
/* Follow the field as the game's follower does: ask for the next point from
   where we stand until it is the goal's exact point. */
static int vv2_max_y;   /* the largest y (feet pixels) the walk visited */
static int vv2_walk(int x, int y, int gx, int gy, int *steps, int allow_goal_blocked) {
    int out[2];
    *steps = 0;
    vv2_max_y = y;
    while (*steps < 2000) {
        if (x == gx && y == gy) return 1;
        if (!vv2_next(grid2, field2, x, y, 0, out)) return 0;
        ++*steps;
        {
            unsigned int v = grid2[(out[0] / 10) * M2 + out[1] / 10];
            int is_goal = out[0] == gx && out[1] == gy;
            if (v >= 1 && v <= 23 && !(is_goal && allow_goal_blocked)) return -1;
        }
        x = out[0]; y = out[1];
        if (y > vv2_max_y) vv2_max_y = y;
    }
    return -3;
}

int main(int argc, char **argv) {
    HMODULE dll;
    probe_site_t site;
    if (argc < 2) { fprintf(stderr, "usage: pathfinding_harness.exe <dll>\n"); return 2; }
    dll = LoadLibraryA(argv[1]);
    CHECK(dll != NULL, "the DLL loads");
    if (dll == NULL) return 1;
    vv1_route = (probe_vv1_t)GetProcAddress(dll, "VvfpPathfindingProbeVv1");
    vv2_flood = (probe_vv2_flood_t)GetProcAddress(dll, "VvfpPathfindingProbeVv2Flood");
    vv2_next = (probe_vv2_next_t)GetProcAddress(dll, "VvfpPathfindingProbeVv2Next");
    site = (probe_site_t)GetProcAddress(dll, "VvfpPathfindingProbeSite");
    CHECK(vv1_route && vv2_flood && vv2_next && site, "the probe exports resolve");
    CHECK(GetProcAddress(dll, "VvfpPathfindingInstall") != NULL, "VvfpPathfindingInstall is exported");
    if (!(vv1_route && vv2_flood && vv2_next && site)) return 1;

    printf("-- A New Home: a wall between villager and task --\n");
    {
        int x, ex, ey, n;
        vv1_clear();
        for (x = 0; x <= 20; ++x) vv1_block(30, x);        /* x = 30, y 0..20 */
        n = vv1_walk(105, 105, 505, 105, &ex, &ey);
        CHECK(n >= 1, "the villager is routed round the wall in %d corner(s)", n);
        CHECK(n >= 0 && ex == 505 && ey == 105, "and arrives at the task (%d,%d)", ex, ey);
        CHECK(!vv1_line_clear(105, 105, 505, 105), "(the straight line really was blocked)");
    }
    printf("-- A New Home: a walled-off task has no route (the action ends, as in The Secret City) --\n");
    {
        int i, wx, wy;
        vv1_clear();
        for (i = 48; i <= 52; ++i) { vv1_block(i, 8); vv1_block(i, 12); vv1_block(48, i - 40); vv1_block(52, i - 40); }
        CHECK(vv1_route(grid1, 105, 105, 505, 105, &wx, &wy) == 0, "no route: the probe returns 0");
    }
    printf("-- A New Home: a task on an obstacle is refused outright, as The Secret City's flood does --\n");
    {
        int wx, wy, x;
        vv1_clear();
        for (x = 0; x <= 20; ++x) vv1_block(30, x);
        vv1_block(50, 10);                                   /* the goal cell itself */
        CHECK(vv1_route(grid1, 105, 105, 505, 105, &wx, &wy) == 0, "no route: the probe returns 0");
        vv1_clear();
        for (x = 0; x <= 20; ++x) vv1_block(30, x);
        CHECK(vv1_route(grid1, 105, 105, 505, 105, &wx, &wy) == 1, "...and with the goal open the same map routes");
    }
    printf("-- A New Home: bumping into a hut is never unreachable --\n");
    {
        int ex, ey, n, x, y;
        vv1_clear();
        for (x = 20; x <= 26; ++x) for (y = 8; y <= 13; ++y) vv1_block(x, y);   /* a hut footprint */
        n = vv1_walk(105, 105, 505, 105, &ex, &ey);
        CHECK(n >= 1 && ex == 505 && ey == 105, "the villager is routed round it in %d corner(s)", n);
        n = vv1_walk(105, 105, 235, 55, &ex, &ey);           /* a task at the hut's side */
        CHECK(n >= 0 && ex == 235 && ey == 55, "and to a task on the hut's own side (%d corner(s))", n);
    }
    printf("-- A New Home: never between two obstacles touching at a corner --\n");
    {
        int ex, ey, n, y;
        vv1_clear();
        for (y = 0; y <= 168; ++y) if (y != 10 && y != 11) vv1_block(30, y);   /* a wall with a 2-cell gap */
        vv1_block(29, 11); vv1_block(31, 10);                /* two blocks that touch the gap diagonally */
        n = vv1_walk(105, 105, 505, 105, &ex, &ey);
        CHECK(n >= 0 && ex == 505, "the villager still gets through the open cells (%d corners)", n);
    }
    printf("-- A New Home: a villager nudged onto a blocked cell is brought back first --\n");
    {
        int wx, wy, r;
        vv1_clear();
        vv1_block(10, 10);
        r = vv1_route(grid1, 105, 105, 505, 105, &wx, &wy);
        CHECK(r == 1 && vv1_open(wx / 10, wy / 10) && abs(wx / 10 - 10) <= 1 && abs(wy / 10 - 10) <= 1,
              "the first waypoint is an open neighbour (%d,%d)", wx, wy);
    }
    printf("-- A New Home: the whole route is queued at once, so the obstacle is never met again --\n");
    {
        typedef int (__stdcall *route_t)(const unsigned int *, int, int, int, int, int *, int);
        route_t route = (route_t)GetProcAddress(dll, "VvfpPathfindingProbeVv1Route");
        int pts[24], n, i, x = 105, y = 105, clear = 1, at_goal = 0;
        CHECK(route != NULL, "VvfpPathfindingProbeVv1Route is exported");
        vv1_clear();
        for (i = 0; i <= 20; ++i) vv1_block(30, i);
        for (i = 20; i <= 26; ++i) { int yy; for (yy = 8; yy <= 13; ++yy) vv1_block(i, yy); }
        n = route ? route(grid1, x, y, 505, 105, pts, 12) : 0;
        for (i = 0; i < n; ++i) {
            if (!vv1_line_clear(x, y, pts[i * 2], pts[i * 2 + 1])) clear = 0;
            x = pts[i * 2]; y = pts[i * 2 + 1];
        }
        at_goal = n > 0 && x / 10 == 50 && y / 10 == 10;
        CHECK(n >= 2 && n <= 12, "a hut and a wall give %d corner(s)", n);
        CHECK(clear, "every leg between corners is clear of blocked cells");
        CHECK(at_goal, "and the last corner is the task's own cell (%d,%d)", x, y);
    }
    printf("-- A New Home: a maze --\n");
    {
        int ex, ey, n, i;
        vv1_clear();
        for (i = 0; i < 150; ++i) { if (i != 5) vv1_block(20, i); if (i != 140) vv1_block(40, i); if (i != 5) vv1_block(60, i); }
        n = vv1_walk(105, 705, 705, 705, &ex, &ey);
        CHECK(n > 0 && ex == 705 && ey == 705, "three walls with offset gaps are threaded (%d corners)", n);
    }

    printf("-- The Lost Children: the field is laid out as the follower reads it --\n");
    {
        int r, x;
        vv2_clear();
        vv2_set(30, 10, 3);
        r = vv2_flood(grid2, field2, 505, 105);
        CHECK(r == 1, "the flood succeeds");
        CHECK(field2[0] == 505 && field2[1] == 105, "the goal is recorded first");
        CHECK(vv2_at(50, 10) == 1, "the goal cell reads 1");
        CHECK(vv2_at(51, 10) == 2 && vv2_at(50, 11) == 2 && vv2_at(49, 10) == 2, "its neighbours read 2");
        CHECK(vv2_at(30, 10) == 0x7FFE, "a blocked cell reads 0x7FFE");
        CHECK(vv2_at(0, 50) == 0x7FFE && vv2_at(167, 50) == 0x7FFE && vv2_at(50, 0) == 0x7FFE && vv2_at(50, 167) == 0x7FFE,
              "the outer ring is blocked, as the stock flood leaves it");
        for (x = 45; x <= 55; ++x) { vv2_set(x, 5, 3); vv2_set(x, 15, 3); }
        for (x = 5; x <= 15; ++x) { vv2_set(45, x, 3); vv2_set(55, x, 3); }
        r = vv2_flood(grid2, field2, 505, 105);
        CHECK(r == 1 && vv2_at(10, 10) == 0x7FFF, "a cell the goal cannot reach reads 0x7FFF");
        CHECK(vv2_flood(grid2, field2, -5, 105) == 0 && field2[0] == -1, "a goal off the grid is refused, as before");
    }
    printf("-- The Lost Children: a goal on a blocked cell is refused, as the stock and The Secret City do --\n");
    {
        int r;
        vv2_clear();
        vv2_set(50, 10, 3);
        r = vv2_flood(grid2, field2, 505, 105);
        CHECK(r == 0 && field2[0] == -1, "the flood returns 0 and marks the field");
    }
    printf("-- The Lost Children: a wall is walked round --\n");
    {
        int steps, w, x;
        vv2_clear();
        for (x = 0; x <= 20; ++x) vv2_set(30, x, 7);
        CHECK(vv2_flood(grid2, field2, 505, 105) == 1, "flood");
        w = vv2_walk(105, 105, 505, 105, &steps, 0);
        CHECK(w == 1, "the villager reaches the goal in %d steps without entering a blocked cell", steps);
        CHECK(vv2_max_y >= 210, "by going below the wall's end (down to y=%d)", vv2_max_y);
    }
    printf("-- The Lost Children: a villager on an unreached cell is brought back --\n");
    {
        int steps, w, out[2];
        vv2_clear();
        vv2_set(10, 10, 7);
        CHECK(vv2_flood(grid2, field2, 505, 105) == 1, "flood");
        CHECK(vv2_next(grid2, field2, 105, 105, 0, out) == 1 && abs(out[0] / 10 - 10) <= 1 && abs(out[1] / 10 - 10) <= 1,
              "the first waypoint is a reached neighbour (%d,%d)", out[0], out[1]);
        w = vv2_walk(105, 105, 505, 105, &steps, 0);
        CHECK(w == 1, "and the walk completes (%d steps)", steps);
        CHECK(vv2_next(grid2, field2, 505, 105, 0, out) == 1 && out[0] == 505 && out[1] == 105,
              "standing on the goal cell yields the goal point");
    }
    printf("-- The Lost Children: the goal-on-24 rule --\n");
    {
        int x;
        vv2_clear();
        for (x = 0; x < 168; ++x) vv2_set(30, x, 24);
        CHECK(vv2_flood(grid2, field2, 505, 105) == 1 && vv2_at(10, 10) == 0x7FFF, "24 blocks a goal that is not on 24");
        vv2_set(50, 10, 24);
        CHECK(vv2_flood(grid2, field2, 505, 105) == 1 && vv2_at(10, 10) < 0x7FFE, "24 is open when the goal is on 24");
    }
    printf("-- The Lost Children: never between two obstacles touching at a corner --\n");
    {
        int steps, w, y;
        vv2_clear();
        for (y = 0; y < 168; ++y) if (y != 10 && y != 11) vv2_set(30, y, 7);
        vv2_set(29, 11, 7); vv2_set(31, 10, 7);
        CHECK(vv2_flood(grid2, field2, 505, 105) == 1, "flood");
        w = vv2_walk(105, 105, 505, 105, &steps, 0);
        CHECK(w == 1, "the villager threads the gap through open cells only (%d steps)", steps);
    }
    printf("-- the hook sites --\n");
    {
        unsigned int va; unsigned char bytes[16]; int n;
        n = site(1, 0, &va, bytes, sizeof bytes);
        CHECK(n == 7 && va == 0x43DFC0 && bytes[0] == 0x51 && bytes[3] == 0x8B, "A New Home's blocked handler at 0x43DFC0, 7 stock bytes");
        n = site(2, 0, &va, bytes, sizeof bytes);
        CHECK(n == 5 && va == 0x41A700 && bytes[0] == 0xB8, "The Lost Children's flood at 0x41A700, 5 stock bytes");
        n = site(2, 1, &va, bytes, sizeof bytes);
        CHECK(n == 5 && va == 0x41A9B0 && bytes[0] == 0xB8, "The Lost Children's descent at 0x41A9B0, 5 stock bytes");
    }
    printf("-- the jmp each site is overwritten with lands on its handler --\n");
    {
        typedef int (__stdcall *probe_bytes_t)(int, int, unsigned int *, unsigned char *, unsigned int *);
        probe_bytes_t bytes_of = (probe_bytes_t)GetProcAddress(dll, "VvfpPathfindingProbeSiteBytes");
        int game, which;
        CHECK(bytes_of != NULL, "VvfpPathfindingProbeSiteBytes is exported");
        for (game = 1; bytes_of != NULL && game <= 2; ++game) {
            for (which = 0; which < 2; ++which) {
                unsigned int va, handler; unsigned char b[16]; int n, i, pad_ok = 1;
                int rel; unsigned int lands;
                n = bytes_of(game, which, &va, b, &handler);
                if (n == 0) continue;
                memcpy(&rel, b + 1, 4);
                lands = va + 5 + (unsigned int)rel;
                for (i = 5; i < n; ++i) if (b[i] != 0x90) pad_ok = 0;
                CHECK(b[0] == 0xE9 && lands == handler && pad_ok,
                      "VV%d site %d: jmp from 0x%X lands on the handler at 0x%X (%s), %d byte(s) padded",
                      game, which, va, handler, lands == handler ? "yes" : "NO", n - 5);
            }
        }
    }
    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
