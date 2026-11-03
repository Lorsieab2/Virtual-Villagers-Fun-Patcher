/* VVFP Keep Carried -- part of "Fix Vanilla Bugs" (A New Home first; the other games are added game by game).

   The owner (2026-11-03): "please don't drop mushrooms and collectibles and stuff if you run into things if at
   all possible!!" and "The villager should try to find alternate paths to objects before giving up!"

   THE STOCK LOSS (docs/reports/vv2-stuck-villager/other-games.md).  A villager walking with something in its
   hands -- berries, crops, fish, a mushroom -- whose walk is blocked nudges sideways; after fifteen nudges the
   game gives up the walk (A New Home: 0x43DFC0 calls 0x439470).  The give-up zeroes the whole step queue, and
   so the rest of the job (the release step and the reward) is gone, and resets the carried-item field (record
   +0x3C: 0x13 nothing, 3 the baby) to "nothing": the villager drops what it carried and the food is never paid.

   THE FIX.  The give-up call inside the blocked handler (the `call 0x439470` at 0x43DFEE, five bytes) is
   retargeted to this companion.  When the villager holds something (not 0x13, not the baby), the front step is
   the walk that failed and the queue holds more steps behind it (the rest of the job: walk on to the delivery
   spot, release, reward), the walk is NOT given up.  Instead the villager is sent to an ALTERNATE STANDING POINT:
   the nearest point on rings of 12 to 160 pixels round its feet that the game's own map read (0x414200) calls
   walkable (cells 1..14 block; 0x2A is avoided too), with a walkable straight line to it and from it to the walk's
   target.  It is queued as the stock nudge queues its waypoint (0x4399F0: walk, x, y, 0, front, the failed
   walk's speed), the nudge count (+0x40) is reset and the step restarted (0x43DEF0, +0x54 = 99), so the walk
   goes on to the same target and then through the queue as ever.  Each point is tried once, at most 12 per walk;
   if the walk to a point fails too, the next point takes its place.  Only when no point is left (or none
   exists) does the stock give-up run: the villager then loses the item exactly as before.

   Everything else is stock: a villager holding nothing, a give-up from any other site, a walk that never reaches
   the cap -- the companion is not even called for those, or hands straight on to 0x439470.  With Improved
   Pathfinding installed the stock handler is not reached for a routable goal (the pathfinding companion routes
   round the obstacle), and its own "no route at all" give-up calls 0x439470 directly: an alternate point with a
   free line to the target cannot exist then, and the item is lost as before -- there is no way to deliver it.

   INSTALLING.  VvfpStartup(game, shipped), called once by VVFP Startup.dll at game start (second word), outside
   DllMain.  The site's five stock bytes are checked and replaced by the shared all-or-none writer
   (native/shared/install_sites.h).  Another build of the game installs nothing.  The probes below exist only in
   the TEST build (VVFP_TEST, tests/test_dlls/). */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"

#define GAME_VV1 1

#define MAX_VILLAGERS 256
#define MAX_TRIED     12
#define MAX_QUEUE     30
#define WALK_GAP_SECONDS 40                  /* a walk silent this long is over; the next is a new one */

#define MAX_CORNERS   12
#define MAX_ROUTES    4                      /* routes queued per walk before the stock give-up */
#define GRID          168
#define CELL          10

typedef struct walk_state {
    int active;
    int last_clock;
    int item;
    int target_x, target_y;                  /* the walk that keeps failing */
    int routes;                              /* routes queued so far */
} walk_state;

static walk_state g_walks[MAX_VILLAGERS];

#ifdef VVFP_TEST
/* Counters the tests read (never in a shipped build). */
__declspec(dllexport) struct {
    int calls, kept, alternates, give_ups;
} VvfpKeepCarriedStats;
#define COUNT(field) (++VvfpKeepCarriedStats.field)
#else
#define COUNT(field) ((void)0)
#endif

static int round_int(double v) {
    return v >= 0.0 ? (int)(v + 0.5) : -(int)(-v + 0.5);
}

static int isqrt(int v) {
    int r = 0;
    int bit = 1 << 30;
    if (v <= 0) {
        return 0;
    }
    while (bit > v) {
        bit >>= 2;
    }
    while (bit != 0) {
        if (v >= r + bit) {
            v -= r + bit;
            r = (r >> 1) + bit;
        } else {
            r >>= 1;
        }
        bit >>= 2;
    }
    return r;
}

/* ---- A New Home -------------------------------------------------------------------------------------------- */
#define VV1_GIVE_UP      0x439470u          /* thiscall(village, idx), ret 4: the clear */
#define VV1_CALL_CAP     0x43DFEEu          /* the blocked handler's `call 0x439470` past 15 nudges */
#define VV1_CALL_EDGE_X  0x445F3Bu          /* the walk's `call 0x439470` when the feet leave the map in x */
#define VV1_CALL_EDGE_Y  0x445F71u          /* ... in y */
#define VV1_CELL_READ    0x414200u          /* thiscall(map, x, y), ret 8 */
#define VV1_QUEUE_PUSH   0x4399F0u          /* thiscall(village, idx, type, x, y, a, mode, speed), ret 0x1C */
#define VV1_STEP_START   0x43DEF0u          /* thiscall(village, idx), ret 4 */
#define VV1_CLOCK        0x402F70u          /* cdecl(): whole real seconds */
#define VV1_MAP_PTR      0x3E014u           /* village + this: the map object */
#define VV1_RECORD       0x3D8u
#define VV1_X            0x4
#define VV1_Y            0x8
#define VV1_NUDGES       0x40               /* the blocked handler's count (stock gives up past 15) */
#define VV1_QUEUE        0x44               /* 30 entries of 24 bytes: type, x, y, a, mode, speed */
#define VV1_SPEED        0x58               /* the front entry's speed */
#define VV1_AIM          0x54               /* the stock nudge sets this to 99 after starting its waypoint */
#define VV1_ITEM         0x3C
#define VV1_ITEM_NONE    0x13
#define VV1_ITEM_BABY    3
#define VV1_FEET_DX      20
#define VV1_FEET_DY      65
#define VV1_MAP_PIXELS   1690

/* E8 rel32 to 0x439470 from each site. */
static const unsigned char VV1_CAP_STOCK[] = { 0xE8, 0x7D, 0xB4, 0xFF, 0xFF };
static const unsigned char VV1_EDGE_X_STOCK[] = { 0xE8, 0x30, 0x35, 0xFF, 0xFF };
static const unsigned char VV1_EDGE_Y_STOCK[] = { 0xE8, 0xFA, 0x34, 0xFF, 0xFF };

typedef int (__fastcall *cell_t)(void *map, void *edx, int x, int y);
typedef int (__fastcall *push_t)(void *village, void *edx, int idx, int type, int x, int y, int a, int mode,
                                 int speed);
typedef int (__fastcall *start_t)(void *village, void *edx, int idx);
typedef int (__cdecl *clock_t_)(void);

static int vv1_cell(void *village, int x, int y) {
    void *map = *(void **)((unsigned char *)village + VV1_MAP_PTR);
    return ((cell_t)(UINT_PTR)VV1_CELL_READ)(map, NULL, x, y);
}

/* The walk's own rule (0x445CB0 reads 0x414200 at the feet): cells 1..14 block; 0x2A is the cell the blocked
   handler itself refuses to nudge along. */
static int walkable(void *village, int x, int y) {
    int c;
    if (x < 30 || y < 30 || x >= 1530 || y >= 1590 || x >= VV1_MAP_PIXELS) {
        return 0;
    }
    c = vv1_cell(village, x, y);
    return !(c >= 1 && c <= 14) && c != 0x2A;
}

static int line_walkable(void *village, int ax, int ay, int bx, int by) {
    int dx = bx - ax;
    int dy = by - ay;
    int n = isqrt(dx * dx + dy * dy) / 3;
    int i;
    if (n < 1) {
        n = 1;
    }
    for (i = 0; i <= n; ++i) {
        if (!walkable(village, ax + round_int((double)dx * i / n), ay + round_int((double)dy * i / n))) {
            return 0;
        }
    }
    return 1;
}

static short g_parent[GRID * GRID];          /* BFS parent cell: -1 the start, -2 not reached */
static unsigned short g_open[GRID * GRID];
static unsigned short g_path[GRID * GRID];

static int cell_free(void *village, int cx, int cy) {
    return cx >= 3 && cy >= 3 && cx < 153 && cy < 159 && walkable(village, cx * CELL + CELL / 2, cy * CELL + CELL / 2);
}

/* A route over the grid (4 neighbours, the cells the walk itself would enter) from the feet's cell to the
   target's, cut to corners with a free straight line between each.  Returns the corner count (0: none). */
static int route(void *village, int fx, int fy, int tx, int ty, int *cx_out, int *cy_out, int max_corners) {
    static const int DX[4] = { 1, -1, 0, 0 };
    static const int DY[4] = { 0, 0, 1, -1 };
    int start = (fy / CELL) * GRID + fx / CELL;
    int goal = (ty / CELL) * GRID + tx / CELL;
    int head = 0;
    int tail = 0;
    int n = 0;
    int c;
    int i;
    int j;
    int count = 0;
    int px = fx;
    int py = fy;
    if (fx < 0 || fy < 0 || tx < 0 || ty < 0 || fx >= GRID * CELL || fy >= GRID * CELL || tx >= GRID * CELL
        || ty >= GRID * CELL || start == goal || !cell_free(village, tx / CELL, ty / CELL)) {
        return 0;
    }
    for (i = 0; i < GRID * GRID; ++i) {
        g_parent[i] = -2;
    }
    g_parent[start] = -1;
    g_open[tail++] = (unsigned short)start;
    while (head < tail && g_parent[goal] == -2) {
        int cur = g_open[head++];
        int ux = cur % GRID;
        int uy = cur / GRID;
        for (i = 0; i < 4; ++i) {
            int nx = ux + DX[i];
            int ny = uy + DY[i];
            int nc = ny * GRID + nx;
            if (nx < 0 || ny < 0 || nx >= GRID || ny >= GRID || g_parent[nc] != -2 || !cell_free(village, nx, ny)) {
                continue;
            }
            g_parent[nc] = (short)cur;
            g_open[tail++] = (unsigned short)nc;
        }
    }
    if (g_parent[goal] == -2) {
        return 0;
    }
    for (c = goal; c != -1; c = g_parent[c]) {
        g_path[n++] = (unsigned short)c;     /* the goal first ... the start last */
    }
    i = n - 1;                               /* the start */
    while (i > 0 && count < max_corners) {
        int next = i - 1;
        for (j = 0; j < i - 1; ++j) {        /* the farthest cell along the path a free straight line reaches */
            if (line_walkable(village, px, py, (g_path[j] % GRID) * CELL + CELL / 2,
                              (g_path[j] / GRID) * CELL + CELL / 2)) {
                next = j;
                break;
            }
        }
        px = (g_path[next] % GRID) * CELL + CELL / 2;
        py = (g_path[next] / GRID) * CELL + CELL / 2;
        cx_out[count] = px;
        cy_out[count] = py;
        ++count;
        i = next;
    }
    return count;
}

/* 1: the give-up was replaced by a route round the obstacle (the caller returns as 0x439470 does);
   0: run the stock give-up. */
static int __stdcall vv1_keep(void *village, int idx) {
    unsigned char *rec;
    walk_state *s;
    int item, now, tx, ty, fx, fy, entries, count, run, i;
    int cx[MAX_CORNERS], cy[MAX_CORNERS];
    COUNT(calls);
    if (village == NULL || idx < 0 || idx >= MAX_VILLAGERS) {
        return 0;
    }
    rec = (unsigned char *)village + (unsigned int)idx * VV1_RECORD;
    item = *(int *)(rec + VV1_ITEM);
    if (item == VV1_ITEM_NONE || item == VV1_ITEM_BABY || item < 0 || item > VV1_ITEM_NONE) {
        return 0;                            /* nothing to keep */
    }
    if (*(int *)(rec + VV1_QUEUE) != 3) {
        return 0;
    }
    entries = 0;
    while (entries < MAX_QUEUE && *(int *)(rec + VV1_QUEUE + entries * 24) != 0) {
        ++entries;
    }
    if (entries < 2) {
        return 0;                            /* no rest of a job behind the walk: nothing delivers it */
    }
    /* The stock nudge pushes a waypoint in front of the walk each time and pops it only on arrival, so at the
       cap the queue starts with a run of walks -- the nudges' waypoints, then the walk to the real target --
       and after the run come the job's other steps.  The real target is the run's last walk. */
    run = 1;
    while (run < entries && *(int *)(rec + VV1_QUEUE + run * 24) == 3) {
        ++run;
    }
    if (run >= entries) {
        return 0;                            /* only walks: no step behind them to deliver */
    }
    tx = *(int *)(rec + VV1_QUEUE + (run - 1) * 24 + 4);
    ty = *(int *)(rec + VV1_QUEUE + (run - 1) * 24 + 8);
    now = ((clock_t_)(UINT_PTR)VV1_CLOCK)();
    s = &g_walks[idx];
    if (s->active && (now - s->last_clock > WALK_GAP_SECONDS || s->item != item)) {
        memset(s, 0, sizeof *s);
    }
    if (!s->active || tx != s->target_x || ty != s->target_y) {
        memset(s, 0, sizeof *s);
        s->active = 1;
        s->item = item;
        s->target_x = tx;
        s->target_y = ty;
    }
    s->last_clock = now;
    fx = *(int *)(rec + VV1_X) + VV1_FEET_DX;
    fy = *(int *)(rec + VV1_Y) + VV1_FEET_DY;
    /* At the map edge the feet are outside it (the stock walk pulls them back right after this call): start
       the route from the nearest cell inside. */
    fx = fx < 40 ? 40 : (fx > 1520 ? 1520 : fx);
    fy = fy < 40 ? 40 : (fy > 1580 ? 1580 : fy);
    count = 0;
    if (s->routes < MAX_ROUTES) {
        count = route(village, fx, fy, tx, ty, cx, cy, MAX_CORNERS);
    }
    if (count == 0) {
        COUNT(give_ups);
        memset(s, 0, sizeof *s);
        return 0;                            /* no way round: the stock give-up, the item is lost as before */
    }
    /* The nudges' waypoints go (the route replaces them); the real target and the job's steps stay. */
    if (run > 1) {
        memmove(rec + VV1_QUEUE, rec + VV1_QUEUE + (run - 1) * 24, (size_t)(entries - (run - 1)) * 24);
        memset(rec + VV1_QUEUE + (entries - (run - 1)) * 24, 0, (size_t)(run - 1) * 24);
        entries -= run - 1;
    }
    if (entries + count > MAX_QUEUE - 1) {
        count = MAX_QUEUE - 1 - entries;     /* the queue holds 30; the next give-up routes on from there */
    }
    if (count < 1) {
        return 0;
    }
    ++s->routes;
    COUNT(alternates);
    for (i = count - 1; i >= 0; --i) {       /* the last corner first: the first ends up in front */
        ((push_t)(UINT_PTR)VV1_QUEUE_PUSH)(village, NULL, idx, 3, cx[i], cy[i], 0, 2, *(int *)(rec + VV1_SPEED));
    }
    *(int *)(rec + VV1_NUDGES) = 0;
    ((start_t)(UINT_PTR)VV1_STEP_START)(village, NULL, idx);
    *(int *)(rec + VV1_AIM) = 99;
    COUNT(kept);
    return 1;
}

static const unsigned int vv1_give_up_stock = VV1_GIVE_UP;

/* Entry, as 0x439470: ecx = village, [esp+4] = index; ret 4. */
static __declspec(naked) void vv1_keep_stub(void) {
    __asm {
        push ecx
        push dword ptr [esp + 8]        ; index
        push ecx                        ; village
        call vv1_keep
        pop ecx
        test eax, eax
        jz stock
        ret 4
    stock:
        jmp dword ptr [vv1_give_up_stock]
    }
}

#define VV1_SITES 3

static void vv1_sites(vvfp_site_write *w) {
    vvfp_site_branch(&w[0], VV1_CALL_CAP, (int)sizeof VV1_CAP_STOCK, VV1_CAP_STOCK, 0xE8, (const void *)vv1_keep_stub);
    vvfp_site_branch(&w[1], VV1_CALL_EDGE_X, (int)sizeof VV1_EDGE_X_STOCK, VV1_EDGE_X_STOCK, 0xE8,
                     (const void *)vv1_keep_stub);
    vvfp_site_branch(&w[2], VV1_CALL_EDGE_Y, (int)sizeof VV1_EDGE_Y_STOCK, VV1_EDGE_Y_STOCK, 0xE8,
                     (const void *)vv1_keep_stub);
}

static int installed;

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w[VV1_SITES];
    (void)shipped;
    if (installed || game != GAME_VV1) {
        return;
    }
    vv1_sites(w);
    if (vvfp_install_sites(w, VV1_SITES)) {
        installed = 1;
    }
}

/* 1 when the sites went in, 0 when they did not (or this game has none). */
__declspec(dllexport) int __stdcall VvfpKeepCarriedInstalled(void) {
    return installed;
}

#ifdef VVFP_TEST
/* What VvfpStartup would write at the site, so a test can lay it into an emulated game. */
__declspec(dllexport) int __stdcall VvfpKeepCarriedProbeSite(int game, int which, unsigned int *va,
                                                              unsigned char *bytes) {
    vvfp_site_write w[VV1_SITES];
    if (game != GAME_VV1 || which < 0 || which >= VV1_SITES) {
        return 0;
    }
    vv1_sites(w);
    *va = w[which].va;
    memcpy(bytes, w[which].bytes, (size_t)w[which].length);
    return w[which].length;
}

/* Forget every villager's walk state (a fresh game). */
__declspec(dllexport) void __stdcall VvfpKeepCarriedProbeReset(void) {
    memset(g_walks, 0, sizeof g_walks);
    memset(&VvfpKeepCarriedStats, 0, sizeof VvfpKeepCarriedStats);
}
#endif /* VVFP_TEST */

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
