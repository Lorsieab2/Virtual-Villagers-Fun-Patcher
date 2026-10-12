/* The Lost Children's route descent (vv2_next, Improved Pathfinding): the
   waypoint it picks is the same as when it translated the whole field, and
   it costs a small fraction of that.  32-bit.

   Until v1.35.70 every call translated all 168 x 168 cells of the walker's
   distance field before looking at the few around the walker -- on every
   waypoint of every walking villager.  It now translates only the square
   best_step and nearest_reached read.  This compiles the companion's source
   in, keeps the old whole-field descent here as the reference (the same
   helpers, the same retry), and asks both for the next waypoint from 60,000
   points on four random terrains (open, scattered rocks, dense rocks, and
   the 24 cells only a goal on them opens), including standing on blocked
   cells, unreached pockets, the goal cell and the field's border; each answer
   and the field each retry re-floods must be identical.  Then it times both.

   Exit code 0 when every check passes. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define VVFP_TEST 1
#include "vvfp_pathfinding.c"

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

#define FIELD_INTS (2 + VV2_GRID * VV2_GRID / 2 + 4)
static unsigned int grid[VV2_GRID * VV2_MAP_STRIDE];
static int field_new[FIELD_INTS];
static int field_old[FIELD_INTS];

/* The descent as it was: the whole field translated, then the same steps. */
static int *__cdecl reference_next(const unsigned int *g, int *out, int *field, int x, int y, int retry) {
    int cx = x / VV2_CELL;
    int cy = y / VV2_CELL;
    const unsigned short *words = (const unsigned short *)(field + 2);
    int nx, ny, i;
    out[0] = -1;
    out[1] = -1;
    if (g == NULL || field == NULL || x < 0 || y < 0 || cx >= VV2_GRID || cy >= VV2_GRID) {
        return out;
    }
    for (i = 0; i < VV2_GRID * VV2_GRID; ++i) {
        unsigned int d = words[i];
        g_field[i] = (unsigned short)(d == VV2_FIELD_BLOCKED ? BLOCKED
                                      : d == VV2_FIELD_UNREACHED ? UNREACHED : d);
    }
    if (g_field[cx + cy * VV2_GRID] == 1) {
        out[0] = field[0];
        out[1] = field[1];
        return out;
    }
    if (g_field[cx + cy * VV2_GRID] >= BLOCKED) {
        if (nearest_reached(g_field, VV2_GRID, VV2_GRID, cx, cy, 3, &nx, &ny)) {
            out[0] = nx * VV2_CELL + VV2_CELL / 2;
            out[1] = ny * VV2_CELL + VV2_CELL / 2;
            return out;
        }
    } else if (best_step(g_field, VV2_GRID, VV2_GRID, cx, cy, &nx, &ny)) {
        if (g_field[nx + ny * VV2_GRID] == 1) {
            out[0] = field[0];
            out[1] = field[1];
        } else {
            out[0] = nx * VV2_CELL + VV2_CELL / 2;
            out[1] = ny * VV2_CELL + VV2_CELL / 2;
        }
        return out;
    }
    if (!retry && vv2_flood(g, field, field[0], field[1])) {
        return reference_next(g, out, field, x, y, 1);
    }
    return out;
}

static unsigned int g_seed = 12345u;
static unsigned int next_random(void) {
    g_seed = g_seed * 1103515245u + 12345u;
    return (g_seed >> 8) & 0xFFFFFFu;
}

static void terrain(int kind) {
    int x, y;
    for (x = 0; x < VV2_GRID; ++x) {
        for (y = 0; y < VV2_GRID; ++y) {
            unsigned int r = next_random() % 100u;
            unsigned int v = 0u;
            if (kind == 1 && r < 10u) v = 5u;
            if (kind == 2 && r < 35u) v = 1u + r % 23u;
            if (kind == 3 && r < 15u) v = 24u;
            grid[x * VV2_MAP_STRIDE + y] = v;
        }
    }
}

int main(void) {
    int kind, i, same = 1, compared = 0;
    LARGE_INTEGER fr, a, b;
    double old_us = 0.0, new_us = 0.0;
    QueryPerformanceFrequency(&fr);
    for (kind = 0; kind < 4; ++kind) {
        int goal_x = 40 + (int)(next_random() % 1500u);
        int goal_y = 40 + (int)(next_random() % 1500u);
        terrain(kind);
        grid[(goal_x / VV2_CELL) * VV2_MAP_STRIDE + goal_y / VV2_CELL] = kind == 3 ? 24u : 0u;
        memset(field_old, 0, sizeof field_old);
        if (!vv2_flood(grid, field_old, goal_x, goal_y)) {
            printf("  FAIL terrain %d: the goal is not reachable\n", kind);
            ++failures;
            continue;
        }
        memcpy(field_new, field_old, sizeof field_new);
        for (i = 0; i < 15000; ++i) {
            int out_old[2], out_new[2];
            int x = (int)(next_random() % (VV2_GRID * VV2_CELL));
            int y = (int)(next_random() % (VV2_GRID * VV2_CELL));
            if (i % 50 == 0) { x = goal_x; y = goal_y; }
            if (i % 70 == 0) { x = (int)(next_random() % 20u); }
            /* Now and then a field whose goal moved: the retry re-floods. */
            if (i % 997 == 0) {
                field_old[0] = field_new[0] = 40 + (int)(next_random() % 1500u);
                field_old[1] = field_new[1] = 40 + (int)(next_random() % 1500u);
            }
            QueryPerformanceCounter(&a);
            reference_next(grid, out_old, field_old, x, y, 0);
            QueryPerformanceCounter(&b);
            old_us += (double)(b.QuadPart - a.QuadPart);
            QueryPerformanceCounter(&a);
            vv2_next(grid, out_new, field_new, x, y, 0);
            QueryPerformanceCounter(&b);
            new_us += (double)(b.QuadPart - a.QuadPart);
            ++compared;
            if (out_old[0] != out_new[0] || out_old[1] != out_new[1]
                || memcmp(field_old, field_new, sizeof field_old) != 0) {
                if (same) {
                    printf("  first difference: terrain %d, (%d, %d): (%d, %d) vs (%d, %d)\n", kind, x, y,
                           out_old[0], out_old[1], out_new[0], out_new[1]);
                }
                same = 0;
            }
        }
    }
    old_us = old_us * 1e6 / (double)fr.QuadPart / compared;
    new_us = new_us * 1e6 / (double)fr.QuadPart / compared;
    printf("  descent: %.2f us a call translating the whole field, %.2f us now (%d calls)\n",
           old_us, new_us, compared);
    CHECK(same, "every waypoint and every re-flooded field is the same as the whole-field descent's (%d calls)",
          compared);
    CHECK(new_us * 5.0 < old_us, "a call costs under a fifth of the whole-field descent's");
    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
