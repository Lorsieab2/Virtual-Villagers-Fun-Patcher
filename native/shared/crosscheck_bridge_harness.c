/* The first-load prompt (crosscheck_bridge.h), run against the real header.

   The companions' scan and repair exports, the save slot and the clock are
   stood in for; the prompt is a real thread whose MessageBoxA answers what
   the case says the player clicked.  Everything else -- the settling, the
   new-load rule, the retries, the one combined prompt, acting on the answer
   on the calling thread -- is the header's own code.

   Built and run by tests/test_first_load_prompt.py. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

static DWORD g_now = 100000u;
static int g_slot = 1;
static volatile LONG g_boxes;           /* message boxes shown */
static volatile LONG g_notices;         /* of them, the failure notice */
static int g_answer = IDNO;
static char g_text[2048];

/* The companions. */
static int g_parents = 0, g_counts[6];
static int g_graves = 0;
static int g_arrivals = 0, g_arrival_scans, g_arrival_calls, g_arrival_game, g_arrival_answer;
static int g_parent_scans, g_grave_scans, g_applies, g_apply_result = 1;
static int g_repair_calls, g_repair_game, g_repair_slot, g_repair_answer;
static int g_have_parentage = 1, g_have_cause = 1;

static int WINAPI harness_msgbox(HWND owner, LPCSTR text, LPCSTR caption, UINT type) {
    (void)owner; (void)caption;
    InterlockedIncrement(&g_boxes);
    if ((type & 0xF) == MB_OK) {
        InterlockedIncrement(&g_notices);
        return IDOK;
    }
    lstrcpynA(g_text, text, sizeof(g_text));
    return g_answer;
}

static int __stdcall fake_scan_parents(int *counts) {
    ++g_parent_scans;
    memcpy(counts, g_counts, sizeof(g_counts));
    return g_parents;
}
static int __stdcall fake_apply_parents(void) { ++g_applies; return g_apply_result; }
static int __stdcall fake_scan_graves(int game, int slot) { (void)game; (void)slot; ++g_grave_scans; return g_graves; }
static int __stdcall fake_scan_arrivals(int game, int slot) { (void)game; (void)slot; ++g_arrival_scans; return g_arrivals; }
static void __stdcall fake_repair_arrivals(int game, int slot, int repair) {
    (void)slot; ++g_arrival_calls; g_arrival_game = game; g_arrival_answer = repair;
}
static void __stdcall fake_repair_graves(int game, int slot, int repair) {
    ++g_repair_calls; g_repair_game = game; g_repair_slot = slot; g_repair_answer = repair;
}

static FARPROC harness_proc(const char *module, const char *name) {
    if (lstrcmpA(module, "VVFP VV1 Parentage.dll") == 0 && g_have_parentage) {
        if (lstrcmpA(name, "Vv1ParentageCrossCheckScan") == 0) return (FARPROC)fake_scan_parents;
        if (lstrcmpA(name, "Vv1ParentageCrossCheckApply") == 0) return (FARPROC)fake_apply_parents;
    }
    if (lstrcmpA(module, "VVFP Cause of Death.dll") == 0 && g_have_cause) {
        if (lstrcmpA(name, "VvfpCauseScanGraves") == 0) return (FARPROC)fake_scan_graves;
        if (lstrcmpA(name, "VvfpCauseRepairGraves") == 0) return (FARPROC)fake_repair_graves;
        if (lstrcmpA(name, "VvfpCauseScanArrivals") == 0) return (FARPROC)fake_scan_arrivals;
        if (lstrcmpA(name, "VvfpCauseRepairArrivals") == 0) return (FARPROC)fake_repair_arrivals;
    }
    return NULL;
}

#define MessageBoxA harness_msgbox
#define VVFP_XC_PROC(module, name) harness_proc(module, name)
#define VVFP_XC_NOW() g_now
#include "story_bridge.h"
static int __stdcall harness_slot(void) { return g_slot; }
static const vvfp_story_host *vvfp_story_host_table(void) {
    static const vvfp_story_host host = { sizeof(vvfp_story_host), harness_slot, NULL, NULL, NULL };
    return &host;
}
#include "crosscheck_bridge.h"
#undef MessageBoxA

static int failures;
static void check(int ok, const char *name) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok) ++failures;
}

static void reset(void) {
    memset(&vvfp_xc, 0, sizeof(vvfp_xc));
    g_now += 100000u;
    g_slot = 1;
    g_boxes = g_notices = 0;
    g_answer = IDNO;
    g_text[0] = '\0';
    g_parents = 0;
    memset(g_counts, 0, sizeof(g_counts));
    g_graves = 0;
    g_arrivals = g_arrival_scans = g_arrival_calls = g_arrival_game = 0;
    g_arrival_answer = -1;
    g_parent_scans = g_grave_scans = g_applies = 0;
    g_apply_result = 1;
    g_repair_calls = g_repair_game = g_repair_slot = 0;
    g_repair_answer = -1;
    g_have_parentage = g_have_cause = 1;
}

/* Frames of play, `ms` apart, for `total` milliseconds; when a prompt is
   open, wait for the "player" (the box answers at once) before the next. */
static void play(int game, int on_screen, DWORD total, DWORD ms) {
    DWORD t;
    for (t = 0; t < total; t += ms) {
        vvfp_crosscheck_bridge(game, on_screen);
        if (vvfp_xc.state == VVFP_XC_ASKING) {
            int spins;
            for (spins = 0; spins < 500 && vvfp_xc.answer == 0; ++spins) Sleep(10);
        }
        g_now += ms;
    }
}

static void wait_notices(void) {
    int spins;
    for (spins = 0; spins < 300 && g_notices == 0; ++spins) Sleep(10);
}

int main(void) {
    /* Nothing found: no prompt. */
    reset();
    play(1, 1, 10000, 16);
    check(g_boxes == 0 && g_parent_scans == 1 && g_grave_scans == 1 && vvfp_xc.state == VVFP_XC_DECIDED,
          "nothing to repair: examined once, no prompt");
    check(g_repair_calls == 0 && g_applies == 0, "... and nothing is repaired or declined");

    /* Not before the village has been on screen for a while. */
    reset();
    g_parents = 1; g_counts[0] = 2;
    play(1, 1, VVFP_XC_SETTLE_MS - 16, 16);
    check(g_parent_scans == 0 && g_boxes == 0, "nothing is examined in the first seconds of a load (past the catch-up)");
    play(1, 1, 200, 16);
    check(g_parent_scans == 1 && g_boxes == 1, "... and then it is");

    /* A New Home's parents, Not now. */
    reset();
    g_parents = 1; g_counts[0] = 2; g_counts[1] = 1; g_counts[3] = 2;
    g_answer = IDNO;
    play(1, 1, 8000, 16);
    check(g_boxes == 1, "parents found: the player is asked, once");
    check(strstr(g_text, "2 villagers have the wrong parents recorded") != NULL
          && strstr(g_text, "1 villager has parents recorded but no Birth record") != NULL
          && strstr(g_text, "2 villagers have no parents recorded") != NULL
          && strstr(g_text, "Repair them now?") != NULL && strstr(g_text, "\"Not now\" changes nothing") != NULL,
          "... and the prompt says plainly what was found and what will happen");
    check(strstr(g_text, "villagers have parents the Births log cannot tell apart") == NULL
          && strstr(g_text, "pregnancy") == NULL, "... and says nothing of what was not found");
    check(g_applies == 0 && g_repair_calls == 0, "Not now: nothing is repaired");
    play(1, 1, 20000, 16);
    check(g_boxes == 1 && g_parent_scans == 1, "... and the same load does not ask again");
    play(1, 0, 100, 16);           /* back at the menus */
    play(1, 1, 8000, 16);
    check(g_boxes == 2, "... but the next load does");
    g_now += VVFP_XC_GAP_MS + 500;  /* a loading screen: no village frames for a while */
    play(1, 1, 8000, 16);
    check(g_boxes == 3, "... and so does one after a gap in the village frames");

    /* Repair. */
    reset();
    g_parents = 1; g_counts[0] = 2;
    g_answer = IDYES;
    play(1, 1, 8000, 16);
    check(g_boxes == 1 && g_applies == 1, "Repair: the parents are repaired, once");
    check(g_notices == 0, "... with no failure notice when it worked");

    /* A repair that could not be written says so. */
    reset();
    g_parents = 1; g_counts[0] = 1;
    g_answer = IDYES;
    g_apply_result = 0;
    play(1, 1, 8000, 16);
    wait_notices();
    check(g_applies == 1 && g_notices == 1, "a repair that could not be written tells the player nothing changed");

    /* Graves, in another game: Not now, then Repair. */
    reset();
    g_graves = 3;
    g_slot = 2;
    g_answer = IDNO;
    play(3, 1, 8000, 16);
    check(g_boxes == 1 && g_parent_scans == 0, "graves missing from the Deaths log (The Secret City): asked; no parents scan outside A New Home");
    check(strstr(g_text, "3 graves have no record in the Deaths log") != NULL
          && strstr(g_text, "the next time you save and quit") != NULL,
          "... and the prompt says when the records will be written");
    check(g_repair_calls == 1 && g_repair_answer == 0 && g_repair_game == 3 && g_repair_slot == 2,
          "Not now is passed on: nothing will be written");
    reset();
    g_graves = 1;
    g_answer = IDYES;
    play(5, 1, 8000, 16);
    check(g_repair_calls == 1 && g_repair_answer == 1 && g_repair_game == 5,
          "Repair is passed on (New Believers)");
    check(strstr(g_text, "1 grave has no record") != NULL, "... in the singular for one");

    /* Both at once: one prompt. */
    reset();
    g_parents = 1; g_counts[0] = 1;
    g_graves = 2;
    g_answer = IDYES;
    play(1, 1, 8000, 16);
    check(g_boxes == 1 && g_applies == 1 && g_repair_calls == 1 && g_repair_answer == 1,
          "parents and graves together: ONE prompt, and Repair repairs both");

    /* A part that cannot tell yet is waited for, so one prompt covers both. */
    reset();
    g_parents = -1;
    g_graves = 2;
    g_answer = IDNO;
    play(1, 1, VVFP_XC_SETTLE_MS + 100, 16);
    check(g_boxes == 0 && g_parent_scans == 1, "a scan that cannot tell yet is not answered with a half prompt");
    g_parents = 1; g_counts[0] = 1;
    play(1, 1, VVFP_XC_RETRY_MS + 200, 16);
    check(g_boxes == 1 && strstr(g_text, "wrong parents") != NULL && strstr(g_text, "graves") != NULL,
          "... it is retried, and the one prompt covers both");

    /* ... but not forever. */
    reset();
    g_parents = -1;
    play(1, 1, VVFP_XC_SETTLE_MS + VVFP_XC_RETRY_MS * (VVFP_XC_RETRIES + 3), 16);
    check(g_parent_scans == VVFP_XC_RETRIES + 1 && g_boxes == 0 && vvfp_xc.state == VVFP_XC_DECIDED,
          "a scan that never can tell is let go for this load, without a prompt");

    /* An answer about another village is not acted on. */
    reset();
    g_parents = 1; g_counts[0] = 1;
    g_graves = 1;
    g_answer = IDYES;
    {
        DWORD t;
        int spins;
        for (t = 0; t < VVFP_XC_SETTLE_MS + 200 && vvfp_xc.state != VVFP_XC_ASKING; t += 16) {
            vvfp_crosscheck_bridge(1, 1);
            g_now += 16;
        }
        g_slot = 3;                 /* the player loaded another slot meanwhile */
        for (spins = 0; spins < 500 && vvfp_xc.answer == 0; ++spins) Sleep(10);
        vvfp_crosscheck_bridge(1, 1);
    }
    check(g_applies == 0 && g_repair_calls == 1 && g_repair_answer == 0,
          "an answer given while another village was loaded repairs nothing");

    /* Companions that are not there are not asked. */
    reset();
    g_have_parentage = 0;
    g_have_cause = 0;
    play(1, 1, 8000, 16);
    check(g_boxes == 0 && g_parent_scans == 0 && g_grave_scans == 0, "with neither companion loaded, nothing is asked");

    /* No village: nothing at all. */
    reset();
    g_parents = 1; g_counts[0] = 1;
    play(1, 0, 10000, 16);
    g_slot = 0;
    play(1, 1, 10000, 16);
    check(g_parent_scans == 0 && g_boxes == 0, "no village on screen (or no slot): nothing is examined");

    /* A New Home's stale expected fathers are listed with the parents. */
    reset();
    g_parents = 1; g_counts[5] = 7;
    play(1, 1, 8000, 16);
    check(g_boxes == 1 && strstr(g_text, "7 villagers have an expected father recorded for a pregnancy that is over. "
                                         "It will be cleared.") != NULL,
          "stale expected fathers: the prompt lists them");

    /* Arrivals with no record, in every game: Not now and Repair are passed on, and they share the one prompt. */
    {
        int game;
        for (game = 1; game <= 5; ++game) {
            reset();
            g_arrivals = 2;
            g_answer = game % 2 ? IDYES : IDNO;
            play(game, 1, 8000, 16);
            if (!(g_boxes == 1 && g_arrival_calls == 1 && g_arrival_game == game
                  && g_arrival_answer == (game % 2 ? 1 : 0)
                  && strstr(g_text, "2 villagers have no Birth or Arrived record in the Births log") != NULL
                  && strstr(g_text, "Their Arrived records will be added the next time you save and quit") != NULL)) {
                break;
            }
        }
        check(game == 6, "villagers with no Birth or Arrived record are asked about in all five games, and the answer is passed on");
    }
    reset();
    g_arrivals = -1;
    g_graves = 1;
    play(4, 1, VVFP_XC_SETTLE_MS + 100, 16);
    check(g_boxes == 0, "an arrivals scan that cannot tell yet holds the prompt back, like the others");
    reset();
    g_parents = 1; g_counts[0] = 1;
    g_graves = 1;
    g_arrivals = 1;
    g_answer = IDYES;
    play(1, 1, 8000, 16);
    check(g_boxes == 1 && g_applies == 1 && g_repair_calls == 1 && g_arrival_calls == 1 && g_arrival_answer == 1,
          "parents, graves and arrivals together: one prompt, and Repair repairs all three");

    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
