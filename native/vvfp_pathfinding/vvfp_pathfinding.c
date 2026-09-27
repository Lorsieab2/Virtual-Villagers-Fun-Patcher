/* VVFP Improved Pathfinding -- A New Home and The Lost Children.

   Brings The Secret City's route planning to the two earlier games, where
   villagers walking to a task get stuck behind obstacles and, on giving up,
   drop whatever they were doing.

   THE SECRET CITY'S MODEL (0x4232A0 / 0x423590, read from the stock
   executable): the moment a villager's next step is blocked, the game floods
   the walkability grid outward from the GOAL (breadth-first, four
   neighbours, blocked cells excluded) and then walks the villager down that
   distance field, cell by cell, choosing the neighbour closest to the goal.
   The route follows the obstacle round and the villager never gives up
   while a route exists.

   A NEW HOME has no route search at all.  Its blocked handler (0x43DFC0)
   nudges the villager sideways one grid cell at a time, fifteen times, and
   then clears the villager's whole action queue (0x439470) -- the villager
   forgets the task and drops what it was carrying.  This companion detours
   that handler: it floods the same 168x168 grid the game's straight-line
   walk consults (0x414200, ten-pixel cells, values 1..14 blocked), walks the
   field from the villager's cell to the end of the first straight run, and
   pushes that point to the FRONT of the villager's action queue as an
   ordinary walk-to (0x4399F0, the same call the stock nudge makes).  The
   stock walker takes it from there; on reaching the corner it pops back to
   the original task, and if the next straight line is blocked again the
   handler fires again from the new spot.  The stock handler is fallen back
   to -- unchanged -- whenever no route exists, so a genuinely unreachable
   goal still ends as it always did.

   THE LOST CHILDREN already has the later games' router (flood 0x41A700,
   descent 0x41A9B0, follower 0x44DE80), but two of its edges give up where
   The Secret City would not:
     * a goal in a blocked cell fails the flood outright (0x41A700 returns 0)
       and the walker clears the queue (0x4492A0) -- the villager drops the
       task instead of walking to the obstacle's edge;
     * a villager standing on an unreached or blocked cell (pushed there by
       a nudge or a load) gets no next waypoint from the descent, which takes
       the FIRST smaller neighbour in a fixed order rather than the best, and
       gives up.
   Both routines are replaced wholesale: the flood seeds the goal cell even
   when it is blocked, and the descent takes the neighbour nearest the goal,
   refuses to cut a corner between two blocked cells, steps into the goal
   cell last, and, from an unreached cell, heads for the nearest reached one.
   The field layout, the follower and the arrival test are the game's own.

   INSTALL SHAPE.  No executable byte is patched by the feature row: each
   game's Origins companion loads this DLL by full path from its per-frame
   tick and calls VvfpPathfindingInstall(game), which verifies the stock
   bytes at each hook site and writes a jmp to the handler here (the
   displaced bytes run from a trampoline).  A mismatch -- another build of
   the game -- installs nothing, and the game plays exactly as before.
   Everything runs on the game's own thread, never from DllMain.

   The routing itself is exposed through the VvfpPathfindingProbe* exports
   so native/vvfp_pathfinding/pathfinding_harness.c can drive it over
   synthetic grids without a game. */
#include <windows.h>
#include <stdlib.h>
#include <string.h>

#define GAME_VV1 1
#define GAME_VV2 2

#define UNREACHED 0xFFFFu
#define BLOCKED   0xFFFEu

/* ---- The shared field ----------------------------------------------------

   One breadth-first flood used by both games: `walkable(x, y)` is the game's
   own rule, `w` and `h` the grid, `out` a w*h array of distances from the
   goal (1 at the goal, then 2, 3, ...; BLOCKED for cells the rule refuses;
   UNREACHED for walkable cells no route reaches).  The goal cell is seeded
   even when the rule refuses it: a task whose target sits on an obstacle's
   edge is still walked to, from the nearest walkable side.  Only walkable
   cells are expanded through. */
typedef int (*walkable_fn)(const void *grid, int x, int y, int allow);

#define MAX_CELLS (256 * 256)
static unsigned short g_field[MAX_CELLS];
static int g_queue[MAX_CELLS];

static void flood(const void *grid, walkable_fn walkable, int allow, int w, int h,
                  int gx, int gy, unsigned short *out) {
    int head = 0;
    int tail = 0;
    int x;
    int y;
    for (y = 0; y < h; ++y) {
        for (x = 0; x < w; ++x) {
            out[x + y * w] = walkable(grid, x, y, allow) ? UNREACHED : BLOCKED;
        }
    }
    out[gx + gy * w] = 1;
    g_queue[tail++] = gx + gy * w;
    while (head < tail) {
        int cell = g_queue[head++];
        int cx = cell % w;
        int cy = cell / w;
        unsigned short next = (unsigned short)(out[cell] + 1);
        static const int dx[4] = { -1, 1, 0, 0 };
        static const int dy[4] = { 0, 0, -1, 1 };
        int k;
        for (k = 0; k < 4; ++k) {
            int nx = cx + dx[k];
            int ny = cy + dy[k];
            int n;
            if (nx < 0 || ny < 0 || nx >= w || ny >= h) {
                continue;
            }
            n = nx + ny * w;
            if (out[n] == UNREACHED) {
                out[n] = next;
                g_queue[tail++] = n;
            }
        }
    }
}

/* The neighbour of (cx, cy) nearest the goal: the reached cell with the
   smallest distance, orthogonal neighbours first among equals, a diagonal
   only when both cells it passes between are walkable (a villager cannot
   squeeze between two obstacles touching at a corner; The Secret City's
   descent allows it and its villagers judder there).  The goal cell counts
   even when blocked, so the last step reaches it.  Returns 0 with no
   candidate. */
static int best_step(const unsigned short *field, int w, int h, int cx, int cy,
                     int *nx, int *ny) {
    static const int dx[8] = { 0, 0, -1, 1, -1, 1, -1, 1 };
    static const int dy[8] = { -1, 1, 0, 0, -1, -1, 1, 1 };
    unsigned int best = field[cx + cy * w];
    int found = 0;
    int k;
    if (best >= BLOCKED) {
        best = BLOCKED;                 /* from an unreached cell any reached one is better */
    }
    for (k = 0; k < 8; ++k) {
        int x = cx + dx[k];
        int y = cy + dy[k];
        unsigned int d;
        if (x < 0 || y < 0 || x >= w || y >= h) {
            continue;
        }
        d = field[x + y * w];
        if (d >= best) {
            continue;
        }
        if (k >= 4) {
            unsigned int side_a = field[x + cy * w];    /* the two cells the diagonal passes between */
            unsigned int side_b = field[cx + y * w];
            if (side_a == BLOCKED || side_b == BLOCKED) {
                continue;
            }
        }
        best = d;
        *nx = x;
        *ny = y;
        found = 1;
    }
    return found;
}

/* From an unreached or blocked cell: the reached cell nearest by distance to
   the goal within `radius`, ties to the closer cell.  Returns 0 if none. */
static int nearest_reached(const unsigned short *field, int w, int h, int cx, int cy,
                           int radius, int *nx, int *ny) {
    unsigned int best = BLOCKED;
    int best_ring = radius + 1;
    int r;
    int found = 0;
    for (r = 1; r <= radius; ++r) {
        int x;
        int y;
        for (y = cy - r; y <= cy + r; ++y) {
            for (x = cx - r; x <= cx + r; ++x) {
                unsigned int d;
                if (abs(x - cx) != r && abs(y - cy) != r) {
                    continue;           /* inside the ring: seen already */
                }
                if (x < 0 || y < 0 || x >= w || y >= h) {
                    continue;
                }
                d = field[x + y * w];
                if (d < best || (d == best && r < best_ring)) {
                    best = d;
                    best_ring = r;
                    *nx = x;
                    *ny = y;
                    found = 1;
                }
            }
        }
        if (found) {
            return 1;                   /* the nearest ring with anything reached */
        }
    }
    return 0;
}

/* ---- A New Home ----------------------------------------------------------

   The village object is the villager array: record i at village + 984 * i,
   256 records.  Inside a record (DWORD index): [1] x, [2] y (the sprite; the
   feet the walk tests are at x + 20, y + 65), [3] [4] the step, and from
   +68 the action queue of thirty 24-byte entries {type, x, y, a6, counter,
   speed}; entry 0 is the current action, so [18] [19] are its target and
   [21] its re-aim counter, [22] its speed.  The terrain grid pointer sits at
   village + 253972: 168 x 168 DWORDs indexed [x/10 * 168 + y/10] (0x414200),
   values 1..14 blocked, anything else open; out of range reads 42. */
#define VV1_RECORD_STRIDE  984
#define VV1_RECORDS        256
#define VV1_MAP_OFFSET     253972
#define VV1_GRID           168
#define VV1_CELL           10
#define VV1_FEET_DX        20
#define VV1_FEET_DY        65
#define VV1_QUEUE          68
#define VV1_QUEUE_ENTRY    24
#define VV1_QUEUE_ENTRIES  30
#define VV1_WALK_TO        3     /* the queue entry type the stock nudge pushes */
#define VV1_PUSH_FRONT     2

#define VV1_BLOCKED_HANDLER 0x43DFC0u
#define VV1_PUSH_ACTION     0x4399F0u
#define VV1_START_NEXT      0x43DEF0u

/* thiscall through fastcall: ecx = this, edx unused, the rest on the stack,
   callee-cleaned -- the same frame the game's own callers build. */
typedef int (__fastcall *vv1_push_t)(void *village, void *edx, int idx, int type,
                                     int x, int y, int a6, int mode, int speed);
typedef int (__fastcall *vv1_start_t)(void *village, void *edx, int idx);

static int vv1_walkable(const void *grid, int x, int y, int allow) {
    unsigned int v;
    (void)allow;
    if (x < 0 || y < 0 || x >= VV1_GRID || y >= VV1_GRID) {
        return 0;
    }
    v = ((const unsigned int *)grid)[x * VV1_GRID + y];
    return v < 1u || v > 14u;
}

/* The corner to walk to next, in feet coordinates: from the feet's cell,
   follow the field toward the goal for at most `max_run` cells and stop
   where the direction changes.  CORNER_FOUND with the waypoint; CORNER_NONE
   when there is no route -- the goal's own cell blocked (The Secret City's
   flood refuses that outright, 0x4232A0), the goal walled off, or the feet
   or goal off the grid; CORNER_AT_GOAL when the feet already stand in the
   goal's cell. */
#define CORNER_NONE    0
#define CORNER_FOUND   1
#define CORNER_AT_GOAL 2
/* The whole route as corners -- the end of each straight run along the
   field, the last one the goal's own cell -- so the villager walks leg to
   leg and never meets the obstacle again (The Secret City hands its walker
   the whole waypoint list at once).  At most `max_corners` are written to
   `corners` (x, y pairs, feet coordinates); `*count` receives how many. */
static int vv1_route(const unsigned int *grid, int feet_x, int feet_y,
                     int goal_x, int goal_y, int max_run,
                     int *corners, int max_corners, int *count) {
    int cx = feet_x / VV1_CELL;
    int cy = feet_y / VV1_CELL;
    int gx = goal_x / VV1_CELL;
    int gy = goal_y / VV1_CELL;
    int x;
    int y;
    int nx;
    int ny;
    int total = 0;
    *count = 0;
    if (feet_x < 0 || feet_y < 0 || goal_x < 0 || goal_y < 0
        || cx >= VV1_GRID || cy >= VV1_GRID || gx >= VV1_GRID || gy >= VV1_GRID
        || max_corners < 1) {
        return CORNER_NONE;
    }
    if (!vv1_walkable(grid, gx, gy, 0)) {
        return CORNER_NONE;             /* a goal on an obstacle: refused, as The Secret City does */
    }
    if (cx == gx && cy == gy) {
        return CORNER_AT_GOAL;
    }
    flood(grid, vv1_walkable, 0, VV1_GRID, VV1_GRID, gx, gy, g_field);
    x = cx;
    y = cy;
    if (g_field[cx + cy * VV1_GRID] >= BLOCKED) {
        /* Standing off the reachable area (nudged onto an edge): step to the
           nearest reached cell first. */
        if (!nearest_reached(g_field, VV1_GRID, VV1_GRID, cx, cy, 3, &nx, &ny)) {
            return CORNER_NONE;
        }
        corners[0] = nx * VV1_CELL + VV1_CELL / 2;
        corners[1] = ny * VV1_CELL + VV1_CELL / 2;
        *count = 1;
        x = nx;
        y = ny;
    }
    while (*count < max_corners && !(x == gx && y == gy) && total < VV1_GRID * 4) {
        int dirx;
        int diry;
        int steps = 0;
        if (!best_step(g_field, VV1_GRID, VV1_GRID, x, y, &nx, &ny)) {
            break;                      /* walled off: no reached neighbour */
        }
        dirx = nx - x;
        diry = ny - y;
        x = nx;
        y = ny;
        ++total;
        /* Extend the straight run while the field keeps pointing the same way. */
        while (++steps < max_run && !(x == gx && y == gy)) {
            int tx;
            int ty;
            if (!best_step(g_field, VV1_GRID, VV1_GRID, x, y, &tx, &ty)
                || tx - x != dirx || ty - y != diry) {
                break;
            }
            x = tx;
            y = ty;
            ++total;
        }
        corners[*count * 2] = x * VV1_CELL + VV1_CELL / 2;
        corners[*count * 2 + 1] = y * VV1_CELL + VV1_CELL / 2;
        ++*count;
    }
    return *count > 0 ? CORNER_FOUND : CORNER_NONE;
}

/* Counters a test can read out of the running game (exported data): how
   often each detour fired and what it decided.  Diagnostic only. */
struct vvfp_pathfinding_stats {
    int vv1_calls;          /* the blocked handler fired */
    int vv1_routed;         /* a corner was queued */
    int vv1_unstuck;        /* ...of which from off the reachable area */
    int vv1_fell_through;   /* the stock handler ran (no village or grid) */
    int vv1_gave_up;        /* no route: the action ended, as The Secret City would */
    int vv1_arrived;        /* blocked inside the goal's own cell: aimed at the feet */
    int vv2_floods;
    int vv2_blocked_goal_floods;
    int vv2_descents;
    int vv2_descent_none;   /* -1,-1 returned */
    int vv2_descent_unstuck;
};
__declspec(dllexport) struct vvfp_pathfinding_stats VvfpPathfindingStats = { 0 };

/* While a route exists the villager is never handed back to the stock
   handler: bumping into a hut or the side of anything is routed round, as
   The Secret City does it.  There is no retry guard, and none is needed:
   the task walk's only collision test is this same grid (0x414200, both
   axes, in 0x445CB0), and this handler is called from nowhere else, so
   nothing can block a villager that the route does not see (Codex, #456).
   The Secret City has no such guard either. */

static void *vv1_trampoline;

/* No route at all -- the goal on an obstacle or walled off.  The Secret
   City ends the action at once (0x460F70: the queue cleared, the villager
   idle); A New Home's equivalent is 0x439470, the call its own handler
   makes after fifteen failed nudges.  Called directly, so the villager does
   not jitter first. */
#define VV1_GIVE_UP 0x439470u
typedef int (__fastcall *vv1_give_up_t)(void *village, void *edx, int idx);

/* The detoured blocked handler.  Returns 1 when it dealt with the villager
   and the stock handler must not run. */
#define VV1_MAX_CORNERS 12

static int __cdecl vv1_blocked(unsigned char *village, int idx, int direction) {
    unsigned char *record;
    const unsigned int *grid;
    int *fields;
    int feet_x;
    int feet_y;
    int corners[VV1_MAX_CORNERS * 2];
    int count;
    int occupied;
    int room;
    int speed;
    int i;
    (void)direction;
    ++VvfpPathfindingStats.vv1_calls;
    if (village == NULL || idx < 0 || idx >= VV1_RECORDS) {
        ++VvfpPathfindingStats.vv1_fell_through;
        return 0;
    }
    grid = *(const unsigned int *const *)(village + VV1_MAP_OFFSET);
    if (grid == NULL) {
        ++VvfpPathfindingStats.vv1_fell_through;
        return 0;
    }
    record = village + (size_t)idx * VV1_RECORD_STRIDE;
    fields = (int *)record;
    feet_x = fields[1] + VV1_FEET_DX;
    feet_y = fields[2] + VV1_FEET_DY;
    /* Room in the action queue: thirty entries, the current action first;
       every corner pushed in front moves the rest down, and the last entry
       would fall off, so never push more than the free entries hold. */
    occupied = 0;
    while (occupied < VV1_QUEUE_ENTRIES
           && *(int *)(record + VV1_QUEUE + occupied * VV1_QUEUE_ENTRY) != 0) {
        ++occupied;
    }
    room = VV1_QUEUE_ENTRIES - 1 - occupied;
    if (room > VV1_MAX_CORNERS) {
        room = VV1_MAX_CORNERS;
    }
    switch (vv1_route(grid, feet_x, feet_y, fields[18], fields[19], VV1_GRID,
                      corners, room > 0 ? room : 1, &count)) {
    case CORNER_NONE:
        ++VvfpPathfindingStats.vv1_gave_up;
        ((vv1_give_up_t)VV1_GIVE_UP)(village, NULL, idx);
        return 1;
    case CORNER_AT_GOAL:
        /* In the goal's cell yet blocked: a sub-cell edge.  Aim the action
           at the feet so the arrival test passes and the task goes on. */
        ++VvfpPathfindingStats.vv1_arrived;
        fields[18] = feet_x;
        fields[19] = feet_y;
        return 1;
    default:
        break;
    }
    ++VvfpPathfindingStats.vv1_routed;
    if (!vv1_walkable(grid, feet_x / VV1_CELL, feet_y / VV1_CELL, 0)) {
        ++VvfpPathfindingStats.vv1_unstuck;
    }
    /* Exactly what the stock nudge does with its own waypoint, once per
       corner: pushed in front of the current action at the villager's
       speed -- last corner first, so the first ends up in front -- then the
       first is started and a re-aim forced on the next frame.  Reaching
       each corner pops to the next; after the last, to the task. */
    speed = fields[22];
    for (i = count - 1; i >= 0; --i) {
        ((vv1_push_t)VV1_PUSH_ACTION)(village, NULL, idx, VV1_WALK_TO,
                                      corners[i * 2], corners[i * 2 + 1], 0,
                                      VV1_PUSH_FRONT, speed);
    }
    ((vv1_start_t)VV1_START_NEXT)(village, NULL, idx);
    fields[21] = 99;
    return 1;
}

/* Entry: ecx = village, [esp+4] = idx, [esp+8] = direction; thiscall, ret 8. */
static __declspec(naked) void vv1_blocked_stub(void) {
    __asm {
        pushfd
        pushad
        mov eax, [esp + 0x2C]           ; direction
        push eax
        mov eax, [esp + 0x2C]           ; idx (the push moved it up by 4)
        push eax
        push ecx                        ; village
        call vv1_blocked
        add esp, 12
        test eax, eax
        jz fall_through
        popad
        popfd
        ret 8
    fall_through:
        popad
        popfd
        jmp dword ptr [vv1_trampoline]
    }
}

/* ---- The Lost Children ---------------------------------------------------

   The grid is 168 x 168 DWORDs indexed [x/10 * 170 + y/10] (0x4181D0):
   1..23 blocked, 24 blocked unless the goal itself is on a 24 cell (the
   flood's own rule at 0x41A700), anything else open.  The distance field
   lives in the villager's record: two ints (the goal) then 168*168 WORDs
   indexed [x/10 + 168 * (y/10)], 1 at the goal, 0x7FFE blocked, 0x7FFF
   unreached, with the outermost ring forced blocked -- the layout the
   follower (0x44DE80) and its arrival test (0x418340, "the cell reads 1")
   expect. */
#define VV2_GRID        168
#define VV2_MAP_STRIDE  170
#define VV2_CELL        10
#define VV2_FIELD_BLOCKED   0x7FFEu
#define VV2_FIELD_UNREACHED 0x7FFFu

#define VV2_FLOOD   0x41A700u
#define VV2_DESCENT 0x41A9B0u

static int vv2_walkable(const void *grid, int x, int y, int allow24) {
    unsigned int v;
    if (x < 0 || y < 0 || x >= VV2_GRID || y >= VV2_GRID) {
        return 0;
    }
    v = ((const unsigned int *)grid)[x * VV2_MAP_STRIDE + y];
    if (v >= 1u && v <= 23u) {
        return 0;
    }
    if (v == 24u && !allow24) {
        return 0;
    }
    return 1;
}

/* Replaces 0x41A700: fill the villager's field from the goal.  Returns 1
   unless the goal is off the grid or on a blocked cell -- the stock rule,
   and The Secret City's (0x4232A0): such a goal is unreachable and the
   walker ends the action.  What this replacement changes is only the
   field's quality for the descent that follows. */
static int __cdecl vv2_flood(const unsigned int *grid, int *field, int goal_x, int goal_y) {
    int gx = goal_x / VV2_CELL;
    int gy = goal_y / VV2_CELL;
    unsigned short *words = (unsigned short *)(field + 2);
    int allow24;
    int i;
    if (grid == NULL || field == NULL || goal_x < 0 || goal_y < 0
        || gx >= VV2_GRID || gy >= VV2_GRID) {
        if (field != NULL) {
            field[0] = -1;
        }
        return 0;
    }
    allow24 = grid[gx * VV2_MAP_STRIDE + gy] == 24u;
    ++VvfpPathfindingStats.vv2_floods;
    if (!vv2_walkable(grid, gx, gy, allow24)) {
        ++VvfpPathfindingStats.vv2_blocked_goal_floods;
        field[0] = -1;
        return 0;
    }
    field[0] = goal_x;
    field[1] = goal_y;
    flood(grid, vv2_walkable, allow24, VV2_GRID, VV2_GRID, gx, gy, g_field);
    for (i = 0; i < VV2_GRID * VV2_GRID; ++i) {
        unsigned int d = g_field[i];
        int x = i % VV2_GRID;
        int y = i / VV2_GRID;
        if (d == BLOCKED || x == 0 || y == 0 || x == VV2_GRID - 1 || y == VV2_GRID - 1) {
            words[i] = (unsigned short)VV2_FIELD_BLOCKED;   /* the stock border ring */
        } else if (d == UNREACHED) {
            words[i] = (unsigned short)VV2_FIELD_UNREACHED;
        } else {
            words[i] = (unsigned short)d;
        }
    }
    words[gx + gy * VV2_GRID] = 1;      /* the goal, even on the ring */
    return 1;
}

/* Replaces 0x41A9B0: the next waypoint from (x, y) along the field, in feet
   coordinates, or -1,-1 when there is none.  `retry` is the stock's own
   flag: 0 allows one re-flood from the field's goal before giving up. */
static int *__cdecl vv2_next(const unsigned int *grid, int *out, int *field,
                             int x, int y, int retry) {
    int cx = x / VV2_CELL;
    int cy = y / VV2_CELL;
    const unsigned short *words = (const unsigned short *)(field + 2);
    int nx;
    int ny;
    int i;
    out[0] = -1;
    out[1] = -1;
    if (!retry) {
        ++VvfpPathfindingStats.vv2_descents;
    }
    if (grid == NULL || field == NULL || x < 0 || y < 0 || cx >= VV2_GRID || cy >= VV2_GRID) {
        ++VvfpPathfindingStats.vv2_descent_none;
        return out;
    }
    /* The game's words, in this file's terms, for the shared helpers. */
    for (i = 0; i < VV2_GRID * VV2_GRID; ++i) {
        unsigned int d = words[i];
        g_field[i] = (unsigned short)(d == VV2_FIELD_BLOCKED ? BLOCKED
                                      : d == VV2_FIELD_UNREACHED ? UNREACHED : d);
    }
    if (g_field[cx + cy * VV2_GRID] == 1) {
        out[0] = field[0];              /* standing on the goal cell: its exact point */
        out[1] = field[1];
        return out;
    }
    if (g_field[cx + cy * VV2_GRID] >= BLOCKED) {
        if (nearest_reached(g_field, VV2_GRID, VV2_GRID, cx, cy, 3, &nx, &ny)) {
            ++VvfpPathfindingStats.vv2_descent_unstuck;
            out[0] = nx * VV2_CELL + VV2_CELL / 2;
            out[1] = ny * VV2_CELL + VV2_CELL / 2;
            return out;
        }
    } else if (best_step(g_field, VV2_GRID, VV2_GRID, cx, cy, &nx, &ny)) {
        if (g_field[nx + ny * VV2_GRID] == 1) {
            out[0] = field[0];          /* the last step: the goal's exact point */
            out[1] = field[1];
        } else {
            out[0] = nx * VV2_CELL + VV2_CELL / 2;
            out[1] = ny * VV2_CELL + VV2_CELL / 2;
        }
        return out;
    }
    if (!retry && vv2_flood(grid, field, field[0], field[1])) {
        return vv2_next(grid, out, field, x, y, 1);
    }
    ++VvfpPathfindingStats.vv2_descent_none;
    return out;
}

/* Entry: ecx = grid, [esp+4] = field, [esp+8] = goal x, [esp+12] = goal y;
   thiscall, ret 0xC, result in al. */
static __declspec(naked) void vv2_flood_stub(void) {
    __asm {
        push ebx
        push esi
        push edi
        mov eax, [esp + 0x18]           ; goal y
        push eax
        mov eax, [esp + 0x18]           ; goal x
        push eax
        mov eax, [esp + 0x18]           ; field
        push eax
        push ecx                        ; grid
        call vv2_flood
        add esp, 16
        pop edi
        pop esi
        pop ebx
        ret 0xC
    }
}

/* Entry: ecx = grid, [esp+4] = out, [esp+8] = field, [esp+12] = x,
   [esp+16] = y, [esp+20] = retry (a byte); thiscall, ret 0x14, eax = out. */
static __declspec(naked) void vv2_descent_stub(void) {
    __asm {
        push ebx
        push esi
        push edi
        movzx eax, byte ptr [esp + 0x20] ; retry
        push eax
        mov eax, [esp + 0x20]           ; y
        push eax
        mov eax, [esp + 0x20]           ; x
        push eax
        mov eax, [esp + 0x20]           ; field
        push eax
        mov eax, [esp + 0x20]           ; out
        push eax
        push ecx                        ; grid
        call vv2_next
        add esp, 24
        pop edi
        pop esi
        pop ebx
        ret 0x14
    }
}

/* ---- Installing the detours ----------------------------------------------

   Each site's stock bytes are checked first; a different build of the game
   installs nothing.  The displaced instructions are copied to a small
   executable page followed by a jump back, so the stock routine can still
   be run in full (the A New Home fall-through).  The page is made
   read-execute once written; the site is writable only for the write. */
struct detour {
    unsigned int va;
    const unsigned char *stock;
    int length;                         /* whole instructions, >= 5 */
    void (*handler)(void);
    void **trampoline;
};

static const unsigned char VV1_BLOCKED_STOCK[] = {
    0x51, 0x53, 0x55, 0x8B, 0x6C, 0x24, 0x10        /* push ecx/ebx/ebp; mov ebp,[esp+10h] */
};
static const unsigned char VV2_FLOOD_STOCK[] = {
    0xB8, 0x10, 0xB9, 0x01, 0x00                    /* mov eax, 1B910h (before __chkstk) */
};
static const unsigned char VV2_DESCENT_STOCK[] = {
    0xB8, 0x67, 0x66, 0x66, 0x66                    /* mov eax, 66666667h */
};
static void *vv2_flood_trampoline;
static void *vv2_descent_trampoline;

static int stock_bytes_present(const struct detour *d) {
    MEMORY_BASIC_INFORMATION info;
    if (VirtualQuery((const void *)(uintptr_t)d->va, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp((const void *)(uintptr_t)d->va, d->stock, (size_t)d->length) == 0;
}

/* A jmp rel32 into `out`, displaced from `from` -- the address the five
   bytes will EXECUTE at, which is not always where they are assembled
   (the site's jmp is assembled in a buffer first). */
static void write_jmp(unsigned char *out, const unsigned char *from, const void *to) {
    unsigned int rel = (unsigned int)((const unsigned char *)to - (from + 5));
    out[0] = 0xE9;
    memcpy(out + 1, &rel, 4);
}

/* The bytes that replace a site: the jmp to its handler, then nops. */
static void site_bytes(const struct detour *d, unsigned char *out) {
    int i;
    write_jmp(out, (const unsigned char *)(uintptr_t)d->va, (const void *)d->handler);
    for (i = 5; i < d->length; ++i) {
        out[i] = 0x90;
    }
}

/* Everything that can fail is done here, before any site is touched: the
   stock bytes checked and the trampoline page built and made read-execute. */
static int prepare_detour(const struct detour *d) {
    unsigned char *site = (unsigned char *)(uintptr_t)d->va;
    unsigned char *page;
    DWORD old;
    if (!stock_bytes_present(d)) {
        return 0;
    }
    page = (unsigned char *)VirtualAlloc(NULL, 64, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (page == NULL) {
        return 0;
    }
    memcpy(page, d->stock, (size_t)d->length);
    write_jmp(page + d->length, page + d->length, site + d->length);
    if (!VirtualProtect(page, 64, PAGE_EXECUTE_READ, &old)) {
        VirtualFree(page, 0, MEM_RELEASE);
        return 0;
    }
    *d->trampoline = page;
    return 1;
}

static void discard_detour(const struct detour *d) {
    if (*d->trampoline != NULL) {
        VirtualFree(*d->trampoline, 0, MEM_RELEASE);
        *d->trampoline = NULL;
    }
}

/* Write `bytes` (the jmp, or the stock bytes back) over the site. */
static int write_site(const struct detour *d, const unsigned char *bytes) {
    unsigned char *site = (unsigned char *)(uintptr_t)d->va;
    DWORD old;
    if (!VirtualProtect(site, (SIZE_T)d->length, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(site, bytes, (size_t)d->length);
    VirtualProtect(site, (SIZE_T)d->length, old, &old);
    FlushInstructionCache(GetCurrentProcess(), site, (SIZE_T)d->length);
    return 1;
}

static int install_detour(const struct detour *d) {
    unsigned char jmp[16];
    if (!stock_bytes_present(d)) {
        return 0;
    }
    site_bytes(d, jmp);
    return write_site(d, jmp);
}

/* Put the stock bytes back (Codex, #454: a set that fails part-way must
   not leave the earlier sites detoured).  If even that write fails, the
   site is still detoured, so its trampoline page must stay: the handler
   is complete on its own and keeps working (Codex, #455). */
static void restore_detour(const struct detour *d) {
    if (write_site(d, d->stock)) {
        discard_detour(d);
    }
}

static int install_state[3];            /* per game: 0 untried, 1 installed, -1 refused */

/* Called by the game's Origins companion from its per-frame tick, once the
   game is up.  Idempotent.  Returns 1 while the detours are live. */
__declspec(dllexport) int __stdcall VvfpPathfindingInstall(int game_id) {
    static const struct detour vv1[] = {
        { VV1_BLOCKED_HANDLER, VV1_BLOCKED_STOCK, sizeof VV1_BLOCKED_STOCK,
          vv1_blocked_stub, &vv1_trampoline },
    };
    static const struct detour vv2[] = {
        { VV2_FLOOD, VV2_FLOOD_STOCK, sizeof VV2_FLOOD_STOCK,
          vv2_flood_stub, &vv2_flood_trampoline },
        { VV2_DESCENT, VV2_DESCENT_STOCK, sizeof VV2_DESCENT_STOCK,
          vv2_descent_stub, &vv2_descent_trampoline },
    };
    const struct detour *set;
    int count;
    int i;
    if (game_id != GAME_VV1 && game_id != GAME_VV2) {
        return 0;
    }
    if (install_state[game_id] != 0) {
        return install_state[game_id] == 1;
    }
    set = game_id == GAME_VV1 ? vv1 : vv2;
    count = game_id == GAME_VV1 ? (int)(sizeof vv1 / sizeof vv1[0])
                                : (int)(sizeof vv2 / sizeof vv2[0]);
    /* All or nothing: The Lost Children's flood and descent share a field
       layout contract, so one without the other is refused.  Every site is
       verified and every trampoline built before the first byte is written;
       a write that still fails puts the sites already written back. */
    for (i = 0; i < count; ++i) {
        if (!prepare_detour(&set[i])) {
            while (i-- > 0) {
                discard_detour(&set[i]);
            }
            install_state[game_id] = -1;
            return 0;
        }
    }
    for (i = 0; i < count; ++i) {
        if (!install_detour(&set[i])) {
            int failed = i;
            while (i-- > 0) {
                restore_detour(&set[i]);      /* keeps its page if the site stays detoured */
            }
            for (i = failed; i < count; ++i) {
                discard_detour(&set[i]);      /* never written: only their pages exist */
            }
            install_state[game_id] = -1;
            return 0;
        }
    }
    install_state[game_id] = 1;
    return 1;
}

/* ---- Probes for the harness ---------------------------------------------- */

/* A New Home's corner finder over a caller-supplied 168x168 grid (the
   game's own indexing, [x * 168 + y]).  Returns 1 with the waypoint in feet
   coordinates, 0 for "the stock handler would run". */
__declspec(dllexport) int __stdcall VvfpPathfindingProbeVv1(const unsigned int *grid,
                                                             int feet_x, int feet_y,
                                                             int goal_x, int goal_y,
                                                             int *out_x, int *out_y) {
    int corners[2];
    int count;
    int r = vv1_route(grid, feet_x, feet_y, goal_x, goal_y, VV1_GRID, corners, 1, &count);
    if (r == CORNER_FOUND) {
        *out_x = corners[0];
        *out_y = corners[1];
    }
    return r == CORNER_FOUND;
}

/* The whole route A New Home's handler would queue: up to `capacity`
   corners into `out` (x, y pairs); returns the count, 0 for no route. */
__declspec(dllexport) int __stdcall VvfpPathfindingProbeVv1Route(const unsigned int *grid,
                                                                  int feet_x, int feet_y,
                                                                  int goal_x, int goal_y,
                                                                  int *out, int capacity) {
    int count;
    if (vv1_route(grid, feet_x, feet_y, goal_x, goal_y, VV1_GRID, out, capacity, &count)
        != CORNER_FOUND) {
        return 0;
    }
    return count;
}

/* The Lost Children's flood and descent over a caller-supplied grid
   ([x * 170 + y]) and field (2 ints + 168*168 WORDs). */
__declspec(dllexport) int __stdcall VvfpPathfindingProbeVv2Flood(const unsigned int *grid,
                                                                  int *field, int goal_x, int goal_y) {
    return vv2_flood(grid, field, goal_x, goal_y);
}

__declspec(dllexport) int __stdcall VvfpPathfindingProbeVv2Next(const unsigned int *grid,
                                                                 int *field, int x, int y,
                                                                 int retry, int *out) {
    vv2_next(grid, out, field, x, y, retry);
    return out[0] != -1;
}

/* What a site would be overwritten with, and the handler's address, so a
   test can decode the jmp and confirm it lands on the handler from the
   SITE (Codex, #455: an earlier version displaced it from the buffer it
   was assembled in).  Returns the byte count. */
__declspec(dllexport) int __stdcall VvfpPathfindingProbeSiteBytes(int game_id, int which,
                                                                   unsigned int *va,
                                                                   unsigned char *bytes,
                                                                   unsigned int *handler_va) {
    static const struct detour vv1_blocked = { VV1_BLOCKED_HANDLER, VV1_BLOCKED_STOCK,
        sizeof VV1_BLOCKED_STOCK, vv1_blocked_stub, &vv1_trampoline };
    static const struct detour vv2_flood_d = { VV2_FLOOD, VV2_FLOOD_STOCK,
        sizeof VV2_FLOOD_STOCK, vv2_flood_stub, &vv2_flood_trampoline };
    static const struct detour vv2_descent_d = { VV2_DESCENT, VV2_DESCENT_STOCK,
        sizeof VV2_DESCENT_STOCK, vv2_descent_stub, &vv2_descent_trampoline };
    const struct detour *d;
    if (game_id == GAME_VV1 && which == 0) {
        d = &vv1_blocked;
    } else if (game_id == GAME_VV2 && which == 0) {
        d = &vv2_flood_d;
    } else if (game_id == GAME_VV2 && which == 1) {
        d = &vv2_descent_d;
    } else {
        return 0;
    }
    *va = d->va;
    *handler_va = (unsigned int)(uintptr_t)d->handler;
    site_bytes(d, bytes);
    return d->length;
}

/* The bytes each hook site must hold, so a test can pin them against the
   stock executables without loading the game. */
__declspec(dllexport) int __stdcall VvfpPathfindingProbeSite(int game_id, int which,
                                                              unsigned int *va,
                                                              unsigned char *bytes, int capacity) {
    const unsigned char *stock;
    int length;
    if (game_id == GAME_VV1 && which == 0) {
        *va = VV1_BLOCKED_HANDLER; stock = VV1_BLOCKED_STOCK; length = sizeof VV1_BLOCKED_STOCK;
    } else if (game_id == GAME_VV2 && which == 0) {
        *va = VV2_FLOOD; stock = VV2_FLOOD_STOCK; length = sizeof VV2_FLOOD_STOCK;
    } else if (game_id == GAME_VV2 && which == 1) {
        *va = VV2_DESCENT; stock = VV2_DESCENT_STOCK; length = sizeof VV2_DESCENT_STOCK;
    } else {
        return 0;
    }
    if (capacity < length) {
        return 0;
    }
    memcpy(bytes, stock, (size_t)length);
    return length;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reason;
    (void)reserved;
    return TRUE;
}
