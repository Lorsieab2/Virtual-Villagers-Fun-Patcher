/* VVFP Stuck Walks -- part of "Fix Vanilla Bugs" in The Lost Children (the owner, 2026-11-03: "They tend
   to get stuck pathfinding to things especially herbs. Would be nice to fix in Vanilla Bugs. (All
   games!!!)", "The villager should try to find alternate paths to objects before giving up!", "please
   don't drop mushrooms and collectibles and stuff if you run into things if at all possible!!").

   THE STOCK LOOP (docs/reports/vv2-stuck-villager/root-cause.md, found by emulating the stock exe).  The
   walk step 0x45E880 reads the map cell the villager is about to enter (0x4181D0); a cell of 76..80 calls
   the band handler 0x44FCB0 (thiscall: ecx = the village, [esp+4] = villager index, [esp+8] = the cell;
   ret 8; entered only from 0x45EB1A and 0x45ECF5) and the step is undone.  For 76..79 the handler puts
   fixed waypoints at the FRONT of the villager's step queue (0x449B70, mode 2) and restarts the front
   step (0x44FBB0).  Cell 79 (the lines y 1210 and y 1280, x 1400..1579) queues the walk to (1325, 1242);
   from there a straight walk to the herb in the south-east sand reaches (1398..1399, 1280) and its next
   step is the band's first cell again: the waypoint is queued again, forever.  The step queue never
   empties, so the scheduler never gives the villager anything else to do.

   THE FIX.  This companion detours the handler's entry.  Every call runs the stock handler unchanged
   except when it is looping:
     * an APPROACH is a band hit while the queue's front step is a walk (type 3) to a point that is not
       one of the handler's twelve waypoints -- the villager heading for its real target.  (Hits while
       it walks to a stock waypoint, or slides along the band and gets another copy of it, are the
       stock handler's own business and are never counted.)
     * per villager (by index, at most 256) the companion remembers the target of the approaches and
       where the feet were; an approach to the same target within 8 pixels of two earlier ones is a
       loop: the stock redirect has already failed twice from this spot.
     * then, instead of the stock waypoint, the villager walks to an ALTERNATE STANDING POINT: the
       nearest point on rings of 12, 24, 36, 48, 60 and 80 pixels round the feet (16 directions) that
       the game's own map read (0x4181D0) calls walkable -- cell 0 or above 23 (24 only for an adult,
       as the walk 0x45E9E5 rules), and not 75..80 (the band, and the read's off-map answer) -- with a
       walkable straight line to it and from it to the target.  It is queued exactly as the stock
       handler queues a waypoint (3, x, y, 0, front, 100) and the front step restarted.  Each point is
       tried once; if the walk to it meets the band too, the next is tried in its place.
     * with no point left (16 tried, or none walkable): the villager gives up like the stock game does
       when a route fails -- the step queue is emptied, so the scheduler picks a new job -- but unlike
       the stock clear 0x4492A0 the record's +0x40 and +0x44 (0x4492A0 writes 0 and 0x1A, or 0x0B
       when nursing) are left as they are: whatever the villager holds stays with it.
   An ordinary walk -- one the stock redirect gets past -- never has a third approach from the same
   spot, so it runs exactly as before, step for step (tests/test_vv2_stuck_walks_native.py).

   It composes with Improved Pathfinding (VVFP Improved Pathfinding.dll), which detours the router's
   flood and descent (0x41A700, 0x41A9B0): a different routine; the alternate point is walked to by the
   stock walk, which uses that router on a blocked cell as it always does.

   INSTALLING.  VvfpStartup(game, shipped), called once by VVFP Startup.dll at game start (second word,
   native/shared/startup_companions_2.h), outside DllMain.  The site's five stock bytes are checked and
   replaced by a jmp through the shared all-or-none writer (native/shared/install_sites.h); the displaced
   instructions (mov eax,[esp+8]; push esi) are re-run by the stub itself before it jumps back to
   0x44FCB5, so no trampoline page is needed.  Another build of the game installs nothing.

   The other four games were traced for the same loop (docs/reports/vv2-stuck-villager/other-games.md):
   none has it.  The probes below exist only in the TEST build (VVFP_TEST, tests/test_dlls/). */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"

#define GAME_VV2 2

/* The Lost Children's routines and layout. */
#define VV2_BAND_HANDLER 0x44FCB0u
#define VV2_BAND_BACK    0x44FCB5u          /* after the displaced mov eax,[esp+8]; push esi */
#define VV2_CELL_READ    0x4181D0u          /* thiscall(map, x, y), ret 8 */
#define VV2_QUEUE_PUSH   0x449B70u          /* thiscall(village, idx, type, x, y, a, mode, speed), ret 0x1C */
#define VV2_STEP_START   0x44FBB0u          /* thiscall(village, idx), ret 4 */
#define VV2_CLOCK        0x403200u          /* cdecl(), whole real seconds (time() minus the save's base) */
#define VV2_MAP_PTR      0xE574D8u          /* village + this: the map object */
#define VV2_RECORD       0xE48Cu            /* village + idx * this: the villager record */
#define VV2_X            0x4
#define VV2_Y            0x8
#define VV2_QUEUE        0x4C                /* 50 entries of 24 bytes: type, x, y, a, mode, speed */
#define VV2_QUEUE_BYTES  (50 * 24)
#define VV2_AGE          0x530
#define VV2_ADULT_AGE    0x118
#define VV2_FEET_DX      20
#define VV2_FEET_DY      65
#define VV2_MAP_PIXELS   1690                /* 169 cells of 10 pixels (0x4181D0: index 0..0xA8) */

static const unsigned char VV2_BAND_STOCK[] = { 0x8B, 0x44, 0x24, 0x08, 0x56 };   /* mov eax,[esp+8]; push esi */

/* The handler's own waypoints (0x44FCCF..0x44FDE3), x then y. */
static const int VV2_WAYPOINTS[12][2] = {
    { 1157, 647 }, { 1190, 466 }, { 1384, 323 }, { 1510, 354 },          /* cell 76 */
    { 908, 700 }, { 1061, 653 }, { 1068, 567 },                          /* cell 77 */
    { 887, 1183 }, { 998, 1228 }, { 1010, 1434 }, { 781, 1463 },         /* cell 78 */
    { 1325, 1242 },                                                      /* cell 79 */
};

/* thiscall through fastcall: ecx = this, edx unused, the rest on the stack, callee-cleaned. */
typedef int (__fastcall *vv2_cell_t)(void *map, void *edx, int x, int y);
typedef int (__fastcall *vv2_push_t)(void *village, void *edx, int idx, int type, int x, int y,
                                     int a, int mode, int speed);
typedef int (__fastcall *vv2_start_t)(void *village, void *edx, int idx);

#define MAX_VILLAGERS 256
#define APPROACHES    4
#define MAX_TRIED     16
#define NEAR_PIXELS   8
#define WALK_GAP_SECONDS 40                  /* a walk silent this long is over; the next is a new one */
#define RINGS         6
#define DIRECTIONS    16

typedef struct walk_state {
    int active;
    int last_clock;                          /* the game clock at the last band call of this walk */
    int target_x, target_y;
    int approaches;                          /* how many are remembered (a ring of APPROACHES) */
    int next;
    int approach_x[APPROACHES], approach_y[APPROACHES];
    int looping;                             /* the stock redirect failed twice from one spot */
    int has_point, point_x, point_y;         /* the alternate standing point now queued */
    int tried;
    int tried_x[MAX_TRIED], tried_y[MAX_TRIED];
} walk_state;

static walk_state g_walks[MAX_VILLAGERS];

/* round(r * cos(k * 22.5 deg)), round(r * sin(...)) are built from these (exact at the axes). */
static const double COS16[DIRECTIONS] = {
    1.0, 0.92387953251128674, 0.70710678118654757, 0.38268343236508984,
    0.0, -0.38268343236508973, -0.70710678118654746, -0.92387953251128674,
    -1.0, -0.92387953251128674, -0.70710678118654768, -0.38268343236509034,
    0.0, 0.38268343236509, 0.70710678118654735, 0.92387953251128652,
};
static const int RING_PIXELS[RINGS] = { 12, 24, 36, 48, 60, 80 };

#ifdef VVFP_TEST
/* Counters the tests read (never in a shipped build). */
__declspec(dllexport) struct {
    int band_calls, approaches, loops, alternates, give_ups;
} VvfpStuckWalksStats;
#define COUNT(field) (++VvfpStuckWalksStats.field)
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

static int cell_at(void *village, int x, int y) {
    void *map = *(void **)((unsigned char *)village + VV2_MAP_PTR);
    return ((vv2_cell_t)(UINT_PTR)VV2_CELL_READ)(map, NULL, x, y);
}

/* The walk's own rule (0x45E880): cells 1..23 stop everyone, 24 stops a child (age below 0x118); 76..80
   is the band, and 75 is what the read answers off the map. */
static int walkable(void *village, int adult, int x, int y) {
    int c;
    if (x < 0 || y < 0 || x >= VV2_MAP_PIXELS || y >= VV2_MAP_PIXELS) {
        return 0;
    }
    c = cell_at(village, x, y);
    if (c == 0) {
        return 1;
    }
    if (c < 24 || (c == 24 && !adult)) {
        return 0;
    }
    return c < 75 || c > 80;
}

/* Every 3 pixels of the straight line from (ax, ay) to (bx, by), both ends included. */
static int line_walkable(void *village, int adult, int ax, int ay, int bx, int by) {
    int dx = bx - ax;
    int dy = by - ay;
    int n = isqrt(dx * dx + dy * dy) / 3;
    int i;
    if (n < 1) {
        n = 1;
    }
    for (i = 0; i <= n; ++i) {
        if (!walkable(village, adult, ax + round_int((double)dx * i / n), ay + round_int((double)dy * i / n))) {
            return 0;
        }
    }
    return 1;
}

static int is_stock_waypoint(int x, int y) {
    int i;
    for (i = 0; i < 12; ++i) {
        if (VV2_WAYPOINTS[i][0] == x && VV2_WAYPOINTS[i][1] == y) {
            return 1;
        }
    }
    return 0;
}

static int was_tried(const walk_state *s, int x, int y) {
    int i;
    for (i = 0; i < s->tried; ++i) {
        if (s->tried_x[i] == x && s->tried_y[i] == y) {
            return 1;
        }
    }
    return 0;
}

static void forget(walk_state *s, int target_x, int target_y, int now) {
    memset(s, 0, sizeof *s);
    s->active = 1;
    s->target_x = target_x;
    s->target_y = target_y;
    s->last_clock = now;
}

/* The nearest untried alternate standing point round the feet (ties: smaller x, then smaller y). */
static int alternate_point(void *village, int adult, const walk_state *s, int fx, int fy, int *ox, int *oy) {
    int best = -1;
    int r;
    int k;
    for (r = 0; r < RINGS; ++r) {
        for (k = 0; k < DIRECTIONS; ++k) {
            int cx = fx + round_int(RING_PIXELS[r] * COS16[k]);
            int cy = fy + round_int(RING_PIXELS[r] * COS16[(k + 12) % DIRECTIONS]);   /* sin = cos(a - 90) */
            int d = (cx - fx) * (cx - fx) + (cy - fy) * (cy - fy);
            if (best >= 0 && (d > best || (d == best && (cx > *ox || (cx == *ox && cy >= *oy))))) {
                continue;
            }
            if (was_tried(s, cx, cy) || !walkable(village, adult, cx, cy)
                || !line_walkable(village, adult, fx, fy, cx, cy)
                || !line_walkable(village, adult, cx, cy, s->target_x, s->target_y)) {
                continue;
            }
            best = d;
            *ox = cx;
            *oy = cy;
        }
    }
    return best >= 0;
}

/* Send the looping villager to its next alternate point, or give up keeping what it holds.  The stock
   handler is not run (the caller returns as the handler does, ret 8). */
static void redirect(void *village, int idx, unsigned char *rec, walk_state *s, int fx, int fy) {
    int adult = *(int *)(rec + VV2_AGE) >= VV2_ADULT_AGE;
    int x;
    int y;
    if (s->tried < MAX_TRIED && alternate_point(village, adult, s, fx, fy, &x, &y)) {
        s->tried_x[s->tried] = x;
        s->tried_y[s->tried] = y;
        ++s->tried;
        COUNT(alternates);
        if (s->has_point && *(int *)(rec + VV2_QUEUE) == 3
            && *(int *)(rec + VV2_QUEUE + 4) == s->point_x && *(int *)(rec + VV2_QUEUE + 8) == s->point_y) {
            /* The walk to the last point met the band too: this point takes its place. */
            *(int *)(rec + VV2_QUEUE + 4) = x;
            *(int *)(rec + VV2_QUEUE + 8) = y;
        } else {
            ((vv2_push_t)(UINT_PTR)VV2_QUEUE_PUSH)(village, NULL, idx, 3, x, y, 0, 2, 100);
        }
        s->has_point = 1;
        s->point_x = x;
        s->point_y = y;
        ((vv2_start_t)(UINT_PTR)VV2_STEP_START)(village, NULL, idx);
        return;
    }
    /* No way round: the queue emptied (the stock clear 0x4492A0 without its +0x40 / +0x44 writes). */
    COUNT(give_ups);
    memset(rec + VV2_QUEUE, 0, VV2_QUEUE_BYTES);
    memset(s, 0, sizeof *s);
}

/* 1: handled here (the stub returns as the handler does); 0: run the stock handler. */
static int __stdcall vv2_band(void *village, int idx, int cell) {
    unsigned char *rec;
    walk_state *s;
    int fx, fy, tx, ty, close_by, i, now;
    COUNT(band_calls);
    if (cell < 76 || cell > 79 || idx < 0 || idx >= MAX_VILLAGERS || village == NULL) {
        return 0;
    }
    rec = (unsigned char *)village + (unsigned int)idx * VV2_RECORD;
    if (*(int *)(rec + VV2_QUEUE) != 3) {
        return 0;
    }
    tx = *(int *)(rec + VV2_QUEUE + 4);
    ty = *(int *)(rec + VV2_QUEUE + 8);
    now = ((int (__cdecl *)(void))(UINT_PTR)VV2_CLOCK)();
    s = &g_walks[idx];
    if (s->active && now - s->last_clock > WALK_GAP_SECONDS) {
        memset(s, 0, sizeof *s);             /* the earlier walk finished (or was replaced): its history is void */
    }
    if (s->active) {
        s->last_clock = now;                 /* also by the stock waypoints' hits: the episode is still going */
    }
    if (is_stock_waypoint(tx, ty)) {
        return 0;                            /* the stock handler's own chain */
    }
    fx = *(int *)(rec + VV2_X) + VV2_FEET_DX;
    fy = *(int *)(rec + VV2_Y) + VV2_FEET_DY;
    if (s->active && s->looping && s->has_point && tx == s->point_x && ty == s->point_y) {
        redirect(village, idx, rec, s, fx, fy);      /* the walk to an alternate point met the band */
        return 1;
    }
    if (!s->active || tx != s->target_x || ty != s->target_y) {
        forget(s, tx, ty, now);
    }
    if (s->looping) {
        redirect(village, idx, rec, s, fx, fy);
        return 1;
    }
    COUNT(approaches);
    close_by = 0;
    for (i = 0; i < s->approaches; ++i) {
        int dx = s->approach_x[i] - fx;
        int dy = s->approach_y[i] - fy;
        if (dx * dx + dy * dy <= NEAR_PIXELS * NEAR_PIXELS) {
            ++close_by;
        }
    }
    s->approach_x[s->next] = fx;
    s->approach_y[s->next] = fy;
    s->next = (s->next + 1) % APPROACHES;
    if (s->approaches < APPROACHES) {
        ++s->approaches;
    }
    if (close_by < 2) {
        return 0;
    }
    COUNT(loops);
    s->looping = 1;
    redirect(village, idx, rec, s, fx, fy);
    return 1;
}

static const unsigned int vv2_band_back = VV2_BAND_BACK;

/* Entry, as 0x44FCB0: ecx = village, [esp+4] = index, [esp+8] = cell. */
static __declspec(naked) void vv2_band_stub(void) {
    __asm {
        push ecx
        push dword ptr [esp + 12]       ; cell
        push dword ptr [esp + 12]       ; index
        push ecx                        ; village
        call vv2_band
        pop ecx
        test eax, eax
        jz stock
        ret 8
    stock:
        mov eax, [esp + 8]              ; the displaced instructions
        push esi
        jmp dword ptr [vv2_band_back]
    }
}

/* The site's bytes: a jmp from 0x44FCB0 to the stub. */
static void band_site(vvfp_site_write *w) {
    vvfp_site_branch(w, VV2_BAND_HANDLER, (int)sizeof VV2_BAND_STOCK, VV2_BAND_STOCK, 0xE9,
                     (const void *)vv2_band_stub);
}

static int installed;

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w;
    (void)shipped;
    if (installed || game != GAME_VV2) {
        return;
    }
    band_site(&w);
    if (vvfp_install_sites(&w, 1)) {
        installed = 1;
    }
}

/* 1 when the site went in, 0 when it did not (or this game has none). */
__declspec(dllexport) int __stdcall VvfpStuckWalksInstalled(void) {
    return installed;
}

#ifdef VVFP_TEST
/* What VvfpStartup would write at the site, so a test can lay it into an emulated game: returns the
   byte count, with the site's address in *va. */
__declspec(dllexport) int __stdcall VvfpStuckWalksProbeSite(int game, unsigned int *va, unsigned char *bytes) {
    vvfp_site_write w;
    if (game != GAME_VV2) {
        return 0;
    }
    band_site(&w);
    *va = w.va;
    memcpy(bytes, w.bytes, (size_t)w.length);
    return w.length;
}

/* Forget every villager's walk state (a fresh game). */
__declspec(dllexport) void __stdcall VvfpStuckWalksProbeReset(void) {
    memset(g_walks, 0, sizeof g_walks);
    memset(&VvfpStuckWalksStats, 0, sizeof VvfpStuckWalksStats);
}
#endif /* VVFP_TEST */

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
