/* The Cause of Death tick: what it costs a frame at 256 villagers, and that
   pacing it to once a draw pass in The Secret City and New Believers
   changes nothing it records.  32-bit.

   The companion's whole source is compiled in as the TEST build, with the
   Documents folder redirected to the folder on the command line (nothing is
   ever written under the real Documents\LDW) and the pacing clock supplied
   by this harness (COD_PACE_NOW_US), so a frame is exactly what the game
   gives the tick:

     A New Home, The Lost Children, The Tree of Life: one call a frame;
     The Secret City, New Believers: one call per villager head drawn --
       256 calls 20 us apart, then the rest of the frame (5 ms).

   Modes:
     cost <docs> <game>      the time of one call and of one frame, and how
                             many times the passes ran in 50 frames
     story <docs> <game> 0|1 a village's 40 frames of play -- a pregnant
                             mother and another villager vanish, a body,
                             three arrivals made by the game's creators, in
                             New Believers a Heathen turned believer -- with
                             the pacing off (0) or on (1); prints every
                             record written and a hash of the tick's tables
                             after each frame.  The two must be identical.
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static char g_docs[MAX_PATH];
static wchar_t g_docs_w[MAX_PATH];
static BOOL WINAPI harness_special_a(HWND o, LPSTR out, int c, BOOL cr) { (void)o; (void)c; (void)cr; lstrcpyA(out, g_docs); return TRUE; }
static BOOL WINAPI harness_special_w(HWND o, LPWSTR out, int c, BOOL cr) { (void)o; (void)c; (void)cr; lstrcpyW(out, g_docs_w); return TRUE; }
static HRESULT WINAPI harness_folder_a(HWND o, int c, HANDLE t, DWORD f, LPSTR out) { (void)o; (void)c; (void)t; (void)f; lstrcpyA(out, g_docs); return S_OK; }
static HRESULT WINAPI harness_folder_w(HWND o, int c, HANDLE t, DWORD f, LPWSTR out) { (void)o; (void)c; (void)t; (void)f; lstrcpyW(out, g_docs_w); return S_OK; }

static LONGLONG g_clock_us;       /* the pacing clock */
#define COD_PACE_NOW_US() g_clock_us

static const unsigned char *harness_managers[6];
#define VV_GAME_SAVE_MANAGER_AT(game) ((const unsigned char *const volatile *)&harness_managers[game])
#define SHGetSpecialFolderPathA harness_special_a
#define SHGetSpecialFolderPathW harness_special_w
#define SHGetFolderPathA harness_folder_a
#define SHGetFolderPathW harness_folder_w
#define VVFP_TEST 1
#include "../shared/save_folder.c"
#include "vvfp_cause_of_death.c"
#include "../shared/game_save_slot.h"

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

static int game;
static unsigned char *table;
static unsigned char manager[0x31000];
static unsigned char graveyard[0x31000];
static int __stdcall host_slot(void) { return vv_current_save_slot(game, 0); }
static struct { int size; int (__stdcall *slot)(void); } host = { 8, host_slot };

static int __stdcall harness_writer(int g, int kind, const void *record, int check, const char *before,
                                    const char *after, int detail) {
    (void)g; (void)check; (void)after; (void)detail;
    printf("RECORD kind %d %s | %s\n", kind, record != NULL ? (const char *)record + REC[game].name : "-",
           before != NULL ? before : "");
    return 1;
}

#define VILLAGERS 256
#define DRAWN 256
static unsigned char *rec(int i) { return table + (size_t)i * REC[game].stride; }

static void villager(int i, int heathen) {
    unsigned char *r = rec(i);
    memset(r, 0, REC[game].stride);
    r[REC[game].present] = 1;
    *(int *)(r + REC[game].health) = 80;
    *(int *)(r + REC[game].age) = 300 + i;
    *(int *)(r + REC[game].sex) = 1 + (i & 1);
    _snprintf((char *)r + REC[game].name, REC[game].name_capacity - 1, "Villager%03d", i);
    if (game == 5 && heathen) {
        r[REC[5].heathen] = 1;
    }
}

static void setup(int heathens) {
    size_t span;
    int i;
    REC[game].slots = VILLAGERS;
    span = (size_t)REC[game].record_base + (size_t)REC[game].stride * VILLAGERS;
    if (game <= 2 && span < (size_t)GRV[game].owner + 4) span = (size_t)GRV[game].owner + 4;
    table = (unsigned char *)VirtualAlloc(NULL, span, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (game <= 2) *(unsigned char **)(table + GRV[game].owner) = graveyard;
    harness_managers[game] = manager;
    *(int *)(manager + VV_GAME_SAVE_SLOT_FIELD[game]) = 1;
    VvfpCauseRollTest = 0;
    VvfpCauseTestSetup(game, &host, table);
    table += REC[game].record_base;
    write_record = harness_writer;
    log_state = 1;
    for (i = 0; i < VILLAGERS; ++i) {
        villager(i, i >= VILLAGERS - heathens);
    }
}

/* One frame as the game calls the tick. */
static int draw_driven(void) { return game == 3 || game == 5; }
static void frame(void) {
    int i;
    if (draw_driven()) {
        for (i = 0; i < DRAWN; ++i) {
            VvfpCauseTick(game);
            g_clock_us += 20;
        }
    } else {
        VvfpCauseTick(game);
    }
    g_clock_us += 5000;
}

static unsigned int fnv(unsigned int h, const void *p, size_t n) {
    const unsigned char *b = (const unsigned char *)p;
    size_t i;
    for (i = 0; i < n; ++i) h = (h ^ b[i]) * 16777619u;
    return h;
}

static unsigned int tables_hash(void) {
    unsigned int h = 2166136261u;
    h = fnv(h, seen_alive, sizeof seen_alive);
    h = fnv(h, temporary, sizeof temporary);
    h = fnv(h, temporary_name, sizeof temporary_name);
    h = fnv(h, lost_due, sizeof lost_due);
    h = fnv(h, lost_litter, sizeof lost_litter);
    h = fnv(h, lost_name, sizeof lost_name);
    h = fnv(h, arrivals, sizeof arrivals);
    h = fnv(h, departed, sizeof departed);
    h = fnv(h, arrived, sizeof arrived);
    h = fnv(h, faction_seen, sizeof faction_seen);
    h = fnv(h, former_kind_seen, sizeof former_kind_seen);
    h = fnv(h, former_roster, sizeof former_roster);
    h = fnv(h, bodies, sizeof bodies);
    return h;
}

static void story(void) {
    int f;
    *(int *)(rec(10) + REC[game].pregnant) = 1;
    *(int *)(rec(10) + REC[game].litter) = 0;
    for (f = 0; f < 40; ++f) {
        switch (f) {
        case 5:                           /* the pregnant mother vanishes, no site told */
            rec(10)[REC[game].present] = 0;
            break;
        case 8:                           /* a body: health 0, still in its record */
            *(int *)(rec(20) + REC[game].health) = 0;
            break;
        case 11:                          /* another villager vanishes */
            rec(21)[REC[game].present] = 0;
            break;
        case 14:                          /* the game's creators make three villagers */
            villager(10, 0);
            VvfpCauseTestCreated(10, 0u);
            villager(21, 0);
            VvfpCauseTestCreated(21, 0u);
            break;
        case 15:
            villager(40, 0);
            rec(40)[REC[game].present] = 0;
            break;
        case 17:
            villager(40, 0);
            VvfpCauseTestCreated(40, 0u);
            break;
        case 20:                          /* New Believers: a Heathen turns believer */
            if (game == 5) rec(200)[REC[5].heathen] = 0;
            break;
        case 24:                          /* a rename */
            _snprintf((char *)rec(50) + REC[game].name, REC[game].name_capacity - 1, "Renamed%03d", 50);
            break;
        default:
            break;
        }
        frame();
        printf("FRAME %d tables %08X\n", f, tables_hash());
    }
}

int main(int argc, char **argv) {
    const char *mode;
    if (argc < 4) {
        printf("usage: cause_tick_cost_harness cost|story <docs> <game> [pace]\n");
        return 2;
    }
    mode = argv[1];
    lstrcpynA(g_docs, argv[2], MAX_PATH);
    MultiByteToWideChar(CP_ACP, 0, g_docs, -1, g_docs_w, MAX_PATH);
    game = atoi(argv[3]);
    if (game < 1 || game > 5) {
        return 2;
    }
    if (strcmp(mode, "story") == 0) {
        cod_test_pace = argc > 4 && atoi(argv[4]) != 0;
        setup(game == 5 ? 150 : 0);
        story();
        return 0;
    }
    {
        LARGE_INTEGER fr, a, b;
        int f, passes_before;
        double per_call, per_frame;
        cod_test_pace = 1;                /* as shipped */
        setup(game == 5 ? 150 : 0);
        for (f = 0; f < 20; ++f) frame();
        QueryPerformanceFrequency(&fr);
        cod_test_pace = 0;                /* every call runs the passes: one call's cost */
        QueryPerformanceCounter(&a);
        for (f = 0; f < 500; ++f) VvfpCauseTick(game);
        QueryPerformanceCounter(&b);
        per_call = (double)(b.QuadPart - a.QuadPart) * 1e6 / (double)fr.QuadPart / 500;
        QueryPerformanceCounter(&a);
        for (f = 0; f < 20; ++f) frame();     /* unpaced: every call's passes, as before v1.35.70 */
        QueryPerformanceCounter(&b);
        printf("  unpaced frame (every call runs the passes): %.2f us\n",
               (double)(b.QuadPart - a.QuadPart) * 1e6 / (double)fr.QuadPart / 20);
        cod_test_pace = 1;
        passes_before = cod_test_passes;
        QueryPerformanceCounter(&a);
        for (f = 0; f < 50; ++f) frame();
        QueryPerformanceCounter(&b);
        per_frame = (double)(b.QuadPart - a.QuadPart) * 1e6 / (double)fr.QuadPart / 50;
        printf("== game %d, %d villagers%s ==\n", game, VILLAGERS, game == 5 ? ", 150 Heathens" : "");
        printf("  one call: %.2f us; one frame (%d calls): %.2f us; passes in 50 frames: %d\n", per_call,
               draw_driven() ? DRAWN : 1, per_frame, cod_test_passes - passes_before);
        CHECK(cod_test_passes - passes_before == 50, "the passes run once a frame (%d in 50 frames)",
              cod_test_passes - passes_before);
        CHECK(per_frame < 1000.0, "a frame's tick costs under 1 ms (%.2f us)", per_frame);
        printf("== %d failure(s) ==\n", failures);
    }
    return failures ? 1 : 0;
}
