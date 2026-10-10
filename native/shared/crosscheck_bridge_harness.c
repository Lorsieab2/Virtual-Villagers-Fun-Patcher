/* The cross-check (crosscheck_bridge.h), run against the real header.

   The companions' scan and repair exports, the save slot, the clock, the
   patcher's "Check logs automatically" setting and the save folder are
   stood in for; the quit prompt is a real thread whose MessageBoxA answers
   what the case says the player clicked (or does not answer at all).
   Everything else -- when a load is examined, what the quit owes, the one
   prompt at the quit and only there, acting on the answer, the Repair Saves & Logs
   approval and its use, the quit hook's stub -- is the header's own code.

   Built and run by tests/test_first_load_prompt.py. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

static DWORD g_now = 100000u;
static int g_slot = 1;
static volatile LONG g_boxes;           /* message boxes shown */
static volatile LONG g_notices;         /* of them, the failure notice */
static volatile LONG g_play_boxes;      /* boxes shown while a village was being played */
static int g_answer = IDNO;
static DWORD g_box_delay;               /* ms the "player" takes to answer */
static int g_box_fails;                 /* the box cannot be shown (MessageBoxA returns 0) */
static char g_text[4096];
static int g_auto;                      /* "Check logs automatically" */
static int g_playing;                   /* inside play(): any box now is a box during gameplay */
static wchar_t g_folder[MAX_PATH];      /* the stand-in save folder */

/* The companions. */
static int g_parents = 0, g_counts[6];
static int g_graves = 0;
static int g_arrivals = 0;
static int g_births = 0;
static int g_stats = 0;
static char g_stats_lines[1536];     /* as large as the bridge's own stats_text */
static int g_parent_scans, g_scans, g_applies, g_apply_result = 1;
static int g_have_parentage = 1, g_have_cause = 1, g_have_stats = 1;
/* The at-the-next-save answers (Repair...) and the right-now repairs (...Now). */
static int g_later_graves, g_later_arrivals, g_later_births, g_later_stats, g_later_answer;
static int g_now_graves, g_now_arrivals, g_now_births, g_now_stats, g_now_game, g_now_slot;
static int g_now_result = 1;
static int g_now_fixes = 1;             /* a ...Now that succeeds leaves nothing for the next scan */
/* The companion's own orphan mask entries (orphan_masks.h). */
static int g_masks = 0, g_mask_scans, g_mask_repairs, g_mask_game, g_mask_slot, g_mask_result = 1;

static int WINAPI harness_msgbox(HWND owner, LPCSTR text, LPCSTR caption, UINT type) {
    (void)owner; (void)caption;
    InterlockedIncrement(&g_boxes);
    if (g_playing) {
        InterlockedIncrement(&g_play_boxes);
    }
    if (g_box_fails) {
        return 0;
    }
    if (g_box_delay) {
        Sleep(g_box_delay);
    }
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
static int __stdcall fake_apply_parents(void) {
    ++g_applies;
    if (g_apply_result && g_now_fixes) {
        g_parents = 0;
    }
    return g_apply_result;
}
static int __stdcall fake_scan_graves(int game, int slot) { (void)game; (void)slot; ++g_scans; return g_graves; }
static int __stdcall fake_scan_arrivals(int game, int slot) { (void)game; (void)slot; return g_arrivals; }
static int __stdcall fake_scan_births(int game, int slot) { (void)game; (void)slot; return g_births; }
static int __stdcall fake_scan_stats(int game, int slot, char *text, int cap) {
    (void)game; (void)slot;
    lstrcpynA(text, g_stats > 0 ? g_stats_lines : "", cap);
    return g_stats;
}
static void __stdcall later_graves(int game, int slot, int repair) { (void)game; (void)slot; ++g_later_graves; g_later_answer = repair; }
static void __stdcall later_arrivals(int game, int slot, int repair) { (void)game; (void)slot; ++g_later_arrivals; g_later_answer = repair; }
static void __stdcall later_births(int game, int slot, int repair) { (void)game; (void)slot; ++g_later_births; g_later_answer = repair; }
static void __stdcall later_stats(int game, int slot, int repair) { (void)game; (void)slot; ++g_later_stats; g_later_answer = repair; }
static void now_called(int game, int slot) { g_now_game = game; g_now_slot = slot; }
static int __stdcall now_graves(int game, int slot) {
    now_called(game, slot); ++g_now_graves;
    if (g_now_result && g_now_fixes) g_graves = 0;
    return g_now_result;
}
static int __stdcall now_arrivals(int game, int slot) {
    now_called(game, slot); ++g_now_arrivals;
    if (g_now_result && g_now_fixes) g_arrivals = 0;
    return g_now_result;
}
static int __stdcall now_births(int game, int slot) {
    now_called(game, slot); ++g_now_births;
    if (g_now_result && g_now_fixes) g_births = 0;
    return g_now_result;
}
static int __stdcall now_stats(int game, int slot) {
    now_called(game, slot); ++g_now_stats;
    if (g_now_result && g_now_fixes) g_stats = 0;
    return g_now_result;
}

/* The village's living villagers, as VVFP Cause of Death.dll's VvfpCauseVillager
   reads them (the missing last names), and whether this build ships the Last
   Names row. */
static int g_have_villagers, g_ln_shipped, g_vcount;
static const char *g_vnames[16];
static int g_vlooks[16][2];
static int __stdcall fake_villager(int game, int index, char *name, int cap, int *looks) {
    (void)game;
    if (index < 0 || index >= g_vcount) {
        return -1;
    }
    if (g_vnames[index] == NULL) {
        return 0;                   /* an empty record, a body, a Heathen... */
    }
    lstrcpynA(name, g_vnames[index], cap);
    looks[0] = g_vlooks[index][0];
    looks[1] = g_vlooks[index][1];
    return 1;
}

static FARPROC harness_proc(const char *module, const char *name) {
    if (lstrcmpA(module, "VVFP Cause of Death.dll") == 0 && g_have_villagers
        && lstrcmpA(name, "VvfpCauseVillager") == 0) {
        return (FARPROC)fake_villager;
    }
    if (lstrcmpA(module, "VVFP VV1 Parentage.dll") == 0 && g_have_parentage) {
        if (lstrcmpA(name, "Vv1ParentageCrossCheckScan") == 0) return (FARPROC)fake_scan_parents;
        if (lstrcmpA(name, "Vv1ParentageCrossCheckApply") == 0) return (FARPROC)fake_apply_parents;
    }
    if (lstrcmpA(module, "VVFP Cause of Death.dll") == 0 && g_have_cause) {
        if (lstrcmpA(name, "VvfpCauseScanGraves") == 0) return (FARPROC)fake_scan_graves;
        if (lstrcmpA(name, "VvfpCauseRepairGraves") == 0) return (FARPROC)later_graves;
        if (lstrcmpA(name, "VvfpCauseRepairGravesNow") == 0) return (FARPROC)now_graves;
        if (lstrcmpA(name, "VvfpCauseScanArrivals") == 0) return (FARPROC)fake_scan_arrivals;
        if (lstrcmpA(name, "VvfpCauseRepairArrivals") == 0) return (FARPROC)later_arrivals;
        if (lstrcmpA(name, "VvfpCauseRepairArrivalsNow") == 0) return (FARPROC)now_arrivals;
        if (lstrcmpA(name, "VvfpCauseScanBirths") == 0) return (FARPROC)fake_scan_births;
        if (lstrcmpA(name, "VvfpCauseRepairBirths") == 0) return (FARPROC)later_births;
        if (lstrcmpA(name, "VvfpCauseRepairBirthsNow") == 0) return (FARPROC)now_births;
    }
    if (lstrcmpA(module, "VVFP Statistics Export.dll") == 0 && g_have_stats) {
        if (lstrcmpA(name, "VvfpStatisticsScanReconcile") == 0) return (FARPROC)fake_scan_stats;
        if (lstrcmpA(name, "VvfpStatisticsRepairReconcile") == 0) return (FARPROC)later_stats;
        if (lstrcmpA(name, "VvfpStatisticsRepairReconcileNow") == 0) return (FARPROC)now_stats;
    }
    return NULL;
}

static int harness_folder(wchar_t *out) {
    lstrcpyW(out, g_folder);
    return 1;
}

#define MessageBoxA harness_msgbox
#define VVFP_XC_PROC(module, name) harness_proc(module, name)
#define VVFP_XC_LOAD(module, name) harness_proc(module, name)
#define VVFP_XC_NOW() g_now
#define VVFP_XC_AUTOMATIC() (g_auto != 0)
#define VVFP_XC_LAST_NAMES_SHIPPED() (g_ln_shipped != 0)
#define VVFP_XC_SAVE_FOLDER(out) harness_folder(out)
#define VVFP_XC_QUIT_WAIT_MS 1500u
#include "story_bridge.h"
static int __stdcall harness_slot(void) { return g_slot; }
static const vvfp_story_host *vvfp_story_host_table(void) {
    static const vvfp_story_host host = { sizeof(vvfp_story_host), harness_slot, NULL, NULL, NULL };
    return &host;
}
#include "crosscheck_bridge.h"
#include "orphan_masks.h"
#undef MessageBoxA

/* The Origins companion's own pair, stood in for. */
static int vvfp_xc_masks_scan(int game, int slot) { (void)game; (void)slot; ++g_mask_scans; return g_masks; }
static int vvfp_xc_masks_repair(int game, int slot) {
    ++g_mask_repairs; g_mask_game = game; g_mask_slot = slot;
    if (g_mask_result && g_now_fixes) g_masks = 0;
    return g_mask_result;
}

static int failures;
static void check(int ok, const char *name) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok) ++failures;
}

static void approval_path(int game, int slot, wchar_t *out) {
    wsprintfW(out, L"%ls\\Virtual Villagers Fun Patcher Data\\Log Checks\\Virtual Villagers %d Repair Approved - Save %d.dat",
              g_folder, game, slot);
}

/* What Repair Saves & Logs writes (src/vv_log_tools.py). */
static void approve(int game, int slot) {
    wchar_t path[MAX_PATH];
    unsigned int body[4];
    HANDLE f;
    DWORD put = 0;
    body[0] = 0x31415256u; body[1] = 1u; body[2] = (unsigned int)game; body[3] = (unsigned int)slot;
    approval_path(game, slot, path);
    f = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    WriteFile(f, body, sizeof(body), &put, NULL);
    CloseHandle(f);
}

static int approval_there(int game, int slot) {
    wchar_t path[MAX_PATH];
    approval_path(game, slot, path);
    return GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES;
}

static void clear_approvals(void) {
    int g, s;
    wchar_t path[MAX_PATH];
    for (g = 1; g <= 5; ++g) {
        for (s = 1; s <= 5; ++s) {
            approval_path(g, s, path);
            DeleteFileW(path);
        }
    }
}

/* The box ends by telling the player how to turn the checks off. */
static const char how_to_stop[] =
    "this village.\r\n\r\nTo stop these checks, untick 'Check logs automatically' in the "
    "Virtual Villagers Fun Patcher and patch the game again.";
static int ends_with_how_to_stop(void) {
    int len = lstrlenA(g_text), tail = lstrlenA(how_to_stop);
    return len >= tail && lstrcmpA(g_text + len - tail, how_to_stop) == 0;
}

static void reset(void) {
    memset(&vvfp_xc, 0, sizeof(vvfp_xc));
    g_now += 100000u;
    g_slot = 1;
    g_boxes = g_notices = g_play_boxes = 0;
    g_answer = IDNO;
    g_box_delay = 0;
    g_box_fails = 0;
    g_text[0] = '\0';
    g_auto = 1;
    g_parents = 0;
    memset(g_counts, 0, sizeof(g_counts));
    g_graves = g_arrivals = g_births = g_stats = 0;
    g_parent_scans = g_scans = g_applies = 0;
    g_apply_result = 1;
    g_have_parentage = g_have_cause = g_have_stats = 1;
    g_later_graves = g_later_arrivals = g_later_births = g_later_stats = 0;
    g_later_answer = -1;
    g_now_graves = g_now_arrivals = g_now_births = g_now_stats = g_now_game = g_now_slot = 0;
    g_now_result = 1;
    g_now_fixes = 1;
    g_masks = g_mask_scans = g_mask_repairs = g_mask_game = g_mask_slot = 0;
    g_mask_result = 1;
    lstrcpyA(g_stats_lines, "- Villagers Buried is 3, but the Deaths log and the graves show 5 burials. "
                            "It will be raised to 5.\r\n");
    g_have_villagers = g_ln_shipped = g_vcount = 0;
    clear_approvals();
}

/* ---- Missing last names: the slot's Last Names files ----------------------- */

static void ln_file(int game, int slot, int request, wchar_t *out) {
    wsprintfW(out, request
              ? L"%ls\\Virtual Villagers Fun Patcher Data\\Last Names\\Virtual Villagers %d Missing Last Names - Save %d.dat"
              : L"%ls\\Virtual Villagers Fun Patcher Data\\Last Names\\Virtual Villagers %d Last Names - Save %d.dat",
              g_folder, game, slot);
}

static void ln_write(int game, int slot, int request, const char *text) {
    wchar_t path[MAX_PATH], sub[MAX_PATH];
    HANDLE f;
    DWORD put = 0;
    wsprintfW(sub, L"%ls\\Virtual Villagers Fun Patcher Data\\Last Names", g_folder);
    CreateDirectoryW(sub, NULL);
    ln_file(game, slot, request, path);
    f = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    WriteFile(f, text, (DWORD)lstrlenA(text), &put, NULL);
    CloseHandle(f);
}

/* The file's text ("" when it is not there). */
static const char *ln_read(int game, int slot, int request) {
    static char text[4096];
    wchar_t path[MAX_PATH];
    HANDLE f;
    DWORD got = 0;
    text[0] = '\0';
    ln_file(game, slot, request, path);
    f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f != INVALID_HANDLE_VALUE) {
        ReadFile(f, text, sizeof(text) - 1, &got, NULL);
        CloseHandle(f);
        text[got] = '\0';
    }
    return text;
}

static void ln_clear(void) {
    wchar_t path[MAX_PATH];
    int g;
    for (g = 1; g <= 5; ++g) {
        ln_file(g, 1, 0, path);
        DeleteFileW(path);
        ln_file(g, 1, 1, path);
        DeleteFileW(path);
    }
}

static void villagers(const char *const *names, int count) {
    int i;
    g_have_villagers = 1;
    g_vcount = count;
    for (i = 0; i < count; ++i) {
        g_vnames[i] = names[i];
        g_vlooks[i][0] = i;           /* 0 is a real head and body */
        g_vlooks[i][1] = i;
    }
}

/* Frames of play, `ms` apart, for `total` milliseconds.  Any message box
   shown meanwhile is one shown during gameplay. */
static void play(int game, int on_screen, DWORD total, DWORD ms) {
    DWORD t;
    g_playing = 1;
    for (t = 0; t < total; t += ms) {
        vvfp_crosscheck_bridge(game, on_screen);
        g_now += ms;
    }
    Sleep(20);                      /* a box thread, if one were ever started, gets its chance */
    g_playing = 0;
}

static int nothing_repaired(void) {
    return g_applies == 0 && g_later_graves + g_later_arrivals + g_later_births + g_later_stats == 0
           && g_now_graves + g_now_arrivals + g_now_births + g_now_stats == 0 && g_mask_repairs == 0;
}

/* ---- The quit hook's stub, on a stand-in site --------------------------- */

static int g_hit_game;
static const unsigned char *g_hit_app;
static int g_hits;
static void __stdcall harness_hit(int game, const unsigned char *app) {
    ++g_hits;
    g_hit_game = game;
    g_hit_app = app;
}

/* The site's code: the stock bytes, then `ret`. */
static unsigned char *site_with(const unsigned char *stock) {
    unsigned char *code = (unsigned char *)VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    memcpy(code, stock, 5);
    code[5] = 0xC3;
    return code;
}

int main(void) {
    int game;
    {
        wchar_t temp[MAX_PATH], sub[MAX_PATH];
        GetTempPathW(MAX_PATH, temp);
        wsprintfW(g_folder, L"%lsvvfp_xc_harness_%lu", temp, GetCurrentProcessId());
        CreateDirectoryW(g_folder, NULL);
        wsprintfW(sub, L"%ls\\Virtual Villagers Fun Patcher Data", g_folder);
        CreateDirectoryW(sub, NULL);
        wsprintfW(sub, L"%ls\\Virtual Villagers Fun Patcher Data\\Log Checks", g_folder);
        CreateDirectoryW(sub, NULL);
    }

    /* ---- The setting OFF: nothing, ever. ---- */
    reset();
    g_auto = 0;
    g_parents = 1; g_counts[0] = 2;
    g_graves = 2; g_arrivals = 1; g_births = 1; g_stats = 1;
    play(1, 1, 20000, 16);
    play(1, 0, 100, 16);
    play(1, 1, 20000, 16);
    vvfp_crosscheck_quit(1, 1);
    check(g_parent_scans == 0 && g_scans == 0 && g_boxes == 0 && nothing_repaired(),
          "setting off: nothing is scanned, asked or repaired -- not while playing, not at the quit");

    /* ---- The setting ON, nothing wrong. ---- */
    reset();
    play(1, 1, 10000, 16);
    check(g_parent_scans == 1 && g_scans == 1 && g_boxes == 0, "setting on, nothing wrong: scanned once, silently");
    vvfp_crosscheck_quit(1, 1);
    check(g_boxes == 0 && nothing_repaired(), "... and nothing is asked at the quit");

    /* ---- Clean at the load, wrong by the quit (Codex, #542): a record
       write that failed later in the session is still asked about. ---- */
    reset();
    play(2, 1, 10000, 16);
    check(g_scans == 1 && g_boxes == 0, "clean at the load: scanned once, silently");
    g_graves = 1;                       /* a Death record that could not be written meanwhile */
    g_answer = IDYES;
    vvfp_crosscheck_quit(2, 1);
    check(g_scans == 2 && g_boxes == 1 && g_now_graves == 1,
          "... the quit looks again from the state just saved, asks, and repairs");

    /* ---- Not in the first seconds of a load. ---- */
    reset();
    g_parents = 1; g_counts[0] = 2;
    play(1, 1, VVFP_XC_SETTLE_MS - 16, 16);
    check(g_parent_scans == 0, "nothing is scanned in the first seconds of a load (past the catch-up)");
    play(1, 1, 200, 16);
    check(g_parent_scans == 1 && g_boxes == 0, "... and then it is scanned, silently");

    /* ---- The setting ON, something wrong: asked at the quit only. ---- */
    reset();
    g_parents = 1; g_counts[0] = 2; g_counts[1] = 1; g_counts[3] = 2;
    play(1, 1, 60000, 16);
    check(g_parent_scans == 1 && g_boxes == 0 && nothing_repaired(),
          "setting on, parents wrong: no prompt and no change while the village is played");
    g_answer = IDNO;
    vvfp_crosscheck_quit(1, 1);
    check(g_boxes == 1 && g_parent_scans == 2, "... it is scanned again at the quit and the player is asked, once");
    check(strstr(g_text, "2 villagers have the wrong parents recorded") != NULL
          && strstr(g_text, "1 villager has parents recorded but no Birth record") != NULL
          && strstr(g_text, "2 villagers have no parents recorded") != NULL
          && strstr(g_text, "The game has already been saved. Repair them now?") != NULL
          && strstr(g_text, "\"Not now\" changes nothing") != NULL
          && strstr(g_text, "the next time you close the game after playing this village") != NULL,
          "... and the prompt says plainly what was found and what will happen");
    check(ends_with_how_to_stop(), "... and it ends by saying how to turn the checks off");
    check(strstr(g_text, "cannot tell apart") == NULL && strstr(g_text, "pregnancy") == NULL,
          "... and says nothing of what was not found");

    /* ---- The same village, a while with no villager drawn (The Secret City
       to New Believers call this only while a villager is drawn: the view
       scrolled away from all of them), then a quit before the next look. ---- */
    reset();
    g_parents = 1; g_counts[0] = 2;
    play(1, 1, 10000, 16);           /* (the gap rule is every game's; the parents part is A New Home's) */
    g_now += VVFP_XC_GAP_MS + 3000;  /* no villager drawn */
    play(1, 1, 500, 16);             /* back, quit before the village settles again */
    g_answer = IDNO;
    vvfp_crosscheck_quit(1, 1);
    check(g_boxes == 1, "a pause with no villager drawn keeps what the quit owes: the quit still asks");
    check(nothing_repaired(), "Not now: nothing is repaired or passed on");

    /* ---- The fullest box: every finding, huge counts, the longest stats text. ---- */
    reset();
    g_parents = 1;
    for (game = 0; game < 6; ++game) g_counts[game] = 2000000000;
    g_graves = g_arrivals = g_births = 2000000000; g_stats = 1;
    memset(g_stats_lines, 'x', sizeof(g_stats_lines) - 3);
    lstrcpyA(g_stats_lines + sizeof(g_stats_lines) - 4, "!\r\n");
    play(1, 1, 8000, 16);
    g_answer = IDNO;
    vvfp_crosscheck_quit(1, 1);
    check(g_boxes == 1 && strstr(g_text, "x!\r\n  (The Village Elders and Village Statistics files") != NULL
          && strstr(g_text, "2000000000 mothers have the wrong father") != NULL
          && strstr(g_text, "2000000000 villagers were born in the village") != NULL
          && lstrlenA(g_text) < (int)sizeof(g_text) - 1 && ends_with_how_to_stop(),
          "the fullest box still holds every finding, the statistics and how to turn the checks off");

    reset();
    g_parents = 1; g_counts[0] = 2;
    play(1, 1, 8000, 16);
    g_answer = IDYES;
    vvfp_crosscheck_quit(1, 1);
    check(g_boxes == 1 && g_applies == 1 && g_notices == 0, "Repair at the quit: the parents are repaired, once, no notice");
    check(g_later_graves + g_later_arrivals + g_later_births + g_later_stats == 0,
          "... and nothing is left for a save that will not come");

    /* Every part, every game it applies to: repaired right after the quit save. */
    for (game = 1; game <= 5; ++game) {
        reset();
        g_slot = game;
        if (game == 1) { g_parents = 1; g_counts[5] = 7; }
        g_graves = 3; g_arrivals = 2; g_stats = 1;
        if (game >= 2) g_births = 4;
        play(game, 1, 8000, 16);
        if (g_boxes != 0 || !nothing_repaired()) break;
        g_answer = IDYES;
        vvfp_crosscheck_quit(game, game);
        if (!(g_boxes == 1 && g_now_graves == 1 && g_now_arrivals == 1 && g_now_stats == 1
              && g_now_births == (game >= 2) && g_applies == (game == 1)
              && g_now_game == game && g_now_slot == game
              && strstr(g_text, "3 graves have no record in the Deaths log") != NULL
              && strstr(g_text, "Their Death records will be added.") != NULL
              && strstr(g_text, "2 villagers have no Birth or Arrived record") != NULL
              && strstr(g_text, "Villagers Buried is 3") != NULL
              && (game < 2 || strstr(g_text, "4 villagers were born in the village but no Birth record") != NULL)
              && (game != 1 || strstr(g_text, "7 villagers have an expected father recorded for a pregnancy that is over") != NULL)
              && strstr(g_text, "next time you save") == NULL)) {
            break;
        }
    }
    check(game == 6, "all five games: every part found is asked about at the quit and repaired there and then");

    /* The quit's own scan decides. */
    reset();
    g_graves = 2;
    play(3, 1, 8000, 16);
    g_graves = 0;                       /* put right meanwhile */
    vvfp_crosscheck_quit(3, 1);
    check(g_boxes == 0 && nothing_repaired(), "found at the load but not at the quit: nothing is asked");
    reset();
    g_graves = -1;                      /* could never tell at the load */
    play(4, 1, VVFP_XC_SETTLE_MS + VVFP_XC_RETRY_MS * (VVFP_XC_RETRIES + 3), 16);
    check(g_boxes == 0 && g_scans == VVFP_XC_RETRIES + 1, "a scan that cannot tell is retried, then let go, silently");
    g_graves = 2;
    g_answer = IDYES;
    vvfp_crosscheck_quit(4, 1);
    check(g_boxes == 1 && g_now_graves == 1, "... and the quit looks again, and asks when it finds something");
    reset();
    g_graves = 1; g_arrivals = -1;
    play(5, 1, VVFP_XC_SETTLE_MS + VVFP_XC_RETRY_MS * (VVFP_XC_RETRIES + 3), 16);
    g_answer = IDYES;
    vvfp_crosscheck_quit(5, 1);
    check(g_boxes == 1 && g_now_graves == 1 && g_now_arrivals == 0 && strstr(g_text, "Arrived") == NULL,
          "at the quit, a part that cannot tell is left out; the rest is still asked about");

    /* Only the village the load checked, and only the slot the quit saved. */
    reset();
    g_graves = 1;
    play(2, 1, 8000, 16);
    vvfp_crosscheck_quit(2, 3);
    check(g_boxes == 0 && nothing_repaired(), "a quit that saved another slot asks nothing");
    reset();
    g_graves = 1;
    play(2, 1, 8000, 16);
    vvfp_crosscheck_quit(2, 0);
    check(g_boxes == 0, "a quit with no slot saved asks nothing");
    reset();
    g_graves = 1;
    play(2, 1, 8000, 16);              /* village 1: something wrong */
    play(2, 0, 200, 16);               /* back at the menus */
    g_slot = 2;
    g_graves = 0;
    play(2, 1, 8000, 16);              /* village 2: nothing */
    g_graves = 1;                      /* still wrong in village 1 */
    vvfp_crosscheck_quit(2, 1);        /* a quit save of village 1's slot is not the load just checked */
    check(g_boxes == 0, "what the quit owes is the last village played's (another load replaces it)");
    reset();
    g_graves = 1;
    play(2, 1, 8000, 16);
    play(2, 0, 3000, 16);              /* back at the title screen, then the game is closed */
    g_answer = IDYES;
    vvfp_crosscheck_quit(2, 1);
    check(g_boxes == 1 && g_now_graves == 1, "quitting from the title screen still asks about the village just played");
    reset();
    g_graves = 1;
    play(2, 1, 1000, 16);              /* closed before it settled */
    vvfp_crosscheck_quit(2, 1);
    check(g_boxes == 0 && g_scans == 0, "a village closed before it settled is not asked about");

    /* No answer in time, or no box: nothing, and the game goes on closing. */
    reset();
    g_graves = 2;
    play(3, 1, 8000, 16);
    g_answer = IDYES;
    g_box_delay = 4000;                /* longer than the quit prompt waits */
    {
        DWORD start = GetTickCount();
        vvfp_crosscheck_quit(3, 1);
        check(GetTickCount() - start < 3500 && nothing_repaired(),
              "a prompt not answered in time is let go: nothing is repaired and the exit is not held up");
    }
    Sleep(3000);
    check(nothing_repaired(), "... and an answer that comes later changes nothing");
    reset();
    g_graves = 2;
    play(3, 1, 8000, 16);
    g_box_fails = 1;
    vvfp_crosscheck_quit(3, 1);
    check(nothing_repaired(), "a box that cannot be shown changes nothing");

    /* A repair that could not be done says so (at the quit), and nothing else. */
    reset();
    g_graves = 1;
    play(4, 1, 8000, 16);
    g_answer = IDYES;
    g_now_result = 0;
    vvfp_crosscheck_quit(4, 1);
    check(g_boxes == 2 && g_notices == 1, "a repair that could not be done tells the player, at the quit");

    /* Companions that are not there are not asked. */
    reset();
    g_have_parentage = g_have_cause = g_have_stats = 0;
    g_parents = 1; g_graves = 1;
    play(1, 1, 8000, 16);
    vvfp_crosscheck_quit(1, 1);
    check(g_boxes == 0 && g_parent_scans == 0 && g_scans == 0, "with no companion loaded, nothing is asked");
    reset();
    g_have_stats = 0;
    g_graves = 1; g_stats = 1;
    play(3, 1, 8000, 16);
    g_answer = IDYES;
    vvfp_crosscheck_quit(3, 1);
    check(g_boxes == 1 && g_now_graves == 1 && g_now_stats == 0, "without the statistics companion the rest is still asked");
    reset();
    g_stats = 1;
    g_stats_lines[0] = '\0';
    play(3, 1, 8000, 16);
    vvfp_crosscheck_quit(3, 1);
    check(g_boxes == 0, "a statistics count with no lines to show is never asked about");

    /* No village: nothing at all. */
    reset();
    g_parents = 1;
    play(1, 0, 10000, 16);
    g_slot = 0;
    play(1, 1, 10000, 16);
    check(g_parent_scans == 0, "no village on screen (or no slot): nothing is scanned");

    /* ---- Repair Saves & Logs: approved, repaired without a question. ---- */
    reset();
    g_auto = 0;                         /* whatever the setting */
    approve(1, 1);
    g_parents = 1; g_counts[0] = 1;
    g_graves = 2; g_arrivals = 1; g_stats = 1;
    play(1, 1, 8000, 16);
    check(g_boxes == 0 && g_applies == 1 && g_later_graves == 1 && g_later_arrivals == 1 && g_later_stats == 1
          && g_later_answer == 1 && g_now_graves + g_now_arrivals + g_now_stats == 0,
          "approved: the parents are repaired as the village settles, the rest at its next save -- no question");
    /* The quit save did its part: nothing is left at the quit. */
    g_graves = g_arrivals = g_stats = 0;
    vvfp_crosscheck_quit(1, 1);
    check(g_boxes == 0 && g_now_graves + g_now_arrivals + g_now_stats == 0 && g_applies == 1,
          "... the quit finds nothing left, so nothing is repaired twice");
    check(!approval_there(1, 1), "... and the approval is used up");

    reset();
    g_auto = 1;
    approve(3, 2);
    g_slot = 2;
    g_graves = 2;
    play(3, 1, 8000, 16);
    check(g_boxes == 0 && g_later_graves == 1, "approved with the setting on: still no question");
    vvfp_crosscheck_quit(3, 2);         /* the save left the records held: completed now */
    check(g_boxes == 0 && g_now_graves == 1 && !approval_there(3, 2),
          "... what the save left undone is completed at the quit, silently, and the approval used up");

    reset();
    approve(4, 1);
    play(4, 1, 8000, 16);
    vvfp_crosscheck_quit(4, 1);
    check(g_boxes == 0 && nothing_repaired() && !approval_there(4, 1), "approved but nothing wrong: used up, nothing changed");

    reset();
    approve(5, 1);
    g_graves = 1;
    play(5, 1, 8000, 16);
    g_now_result = 0;
    vvfp_crosscheck_quit(5, 1);
    check(g_boxes == 0 && g_now_graves == 1 && approval_there(5, 1),
          "approved, but a repair could not be done: the approval is kept for next time (nothing shown)");

    reset();
    approve(2, 1);
    g_graves = 1;
    play(2, 1, 8000, 16);
    /* the game ends without its quit save: no quit */
    check(approval_there(2, 1), "a game that never reaches its quit save keeps the approval");

    reset();
    g_auto = 0;
    approve(2, 1);
    g_slot = 2;
    g_graves = 1;
    play(2, 1, 8000, 16);
    vvfp_crosscheck_quit(2, 2);
    check(g_scans == 0 && nothing_repaired() && approval_there(2, 1), "an approval is for its own slot only");

    reset();
    g_auto = 0;
    approve(1, 1);
    {
        /* Rewritten as another game's approval: not this game's. */
        wchar_t path[MAX_PATH];
        unsigned int body[4] = { 0x31415256u, 1u, 3u, 1u };
        HANDLE f;
        DWORD put = 0;
        approval_path(1, 1, path);
        f = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        WriteFile(f, body, sizeof(body), &put, NULL);
        CloseHandle(f);
    }
    g_graves = 1;
    play(1, 1, 8000, 16);
    vvfp_crosscheck_quit(1, 1);
    check(g_scans == 0 && nothing_repaired(), "an approval file that does not say this game and slot is not one");

    reset();
    g_auto = 0;
    approve(3, 1);
    g_graves = 1;
    play(3, 1, 8000, 16);
    clear_approvals();                  /* Start Over erased the village meanwhile */
    g_now_graves = 0;
    vvfp_crosscheck_quit(3, 1);
    check(g_now_graves == 0, "an approval removed before the quit (Start Over) repairs nothing more at the quit");

    /* ---- The quit hook. ---- */
    {
        static const unsigned char stock12[5] = { 0x8B, 0x4E, 0x0C, 0x85, 0xC9 };
        static const unsigned char stock345[5] = { 0x8B, 0x4E, 0x08, 0x3B, 0xCF };
        static unsigned int app[8];
        unsigned char *site = site_with(stock12);
        unsigned int ecx_after = 0, esi_after = 0, edi_after = 0, ebx_after = 0, ebp_after = 0, zf_after = 7;
        int ok;
        app[3] = 0x12345678u;           /* [esi+0Ch] */
        g_hits = 0;
        ok = vvfp_xc_hook(site, stock12, 2, harness_hit);
        check(ok && site[0] == 0xE9, "the hook is written over the stock bytes");
        {
            unsigned int *a = app;
            __asm {
                push ebx
                mov esi, a
                mov edi, 0x11111111
                mov ebx, 0x22222222
                mov edx, ebp
                call site
                mov ecx_after, ecx
                setz al
                movzx eax, al
                mov zf_after, eax
                mov esi_after, esi
                mov edi_after, edi
                mov ebx_after, ebx
                mov ebp_after, ebp
                pop ebx
            }
        }
        check(g_hits == 1 && g_hit_game == 2 && g_hit_app == (const unsigned char *)app,
              "the hook calls the quit check with the game and the application (esi)");
        check(ecx_after == 0x12345678u && zf_after == 0 && esi_after == (unsigned int)(uintptr_t)app
              && edi_after == 0x11111111u && ebx_after == 0x22222222u && ebp_after != 0,
              "... then runs the displaced instructions, with every register as it was, and returns to the game");
        app[3] = 0;
        {
            unsigned int *a = app;
            __asm {
                mov esi, a
                call site
                setz al
                movzx eax, al
                mov zf_after, eax
            }
        }
        check(zf_after == 1 && g_hits == 2, "... the flags the game's next jump reads are the displaced test's own");
        site = site_with(stock345);
        site[2] = 0x0C;                 /* not this game's bytes */
        check(!vvfp_xc_hook(site, stock345, 3, harness_hit) && site[0] == 0x8B,
              "a site that does not hold its stock bytes is left alone");
    }
    {
        /* The handler reads the slot the shutdown saved. */
        static unsigned char manager[0x31000];
        static unsigned char *app[2];
        app[1] = manager;
        reset();
        g_graves = 1;
        g_slot = 4;
        play(2, 1, 8000, 16);
        *(int *)(manager + 0x30378) = 4;
        g_answer = IDYES;
        vvfp_xc_quit_hit(2, (const unsigned char *)app);
        check(g_boxes == 1 && g_now_graves == 1 && g_now_slot == 4,
              "the quit hook takes the slot from the save manager, where the shutdown read it");
        reset();
        g_graves = 1;
        play(3, 1, 8000, 16);
        vvfp_xc_quit_hit(3, NULL);
        vvfp_xc_quit_hit(3, (const unsigned char *)(uintptr_t)0x10);
        check(g_boxes == 0, "a fault while reading the slot is caught: nothing, and the game goes on closing");
    }

    /* ---- Orphan mask entries (v1.35.59), every game: the companion's own pair. ---- */
    for (game = 1; game <= 5; ++game) {
        reset();
        g_masks = 3;
        g_slot = game;
        play(game, 1, 20000, 16);
        if (!(g_mask_scans == 1 && g_boxes == 0 && nothing_repaired())) break;
        g_answer = game % 2 ? IDYES : IDNO;
        vvfp_crosscheck_quit(game, game);
        if (!(g_boxes == 1 && g_mask_scans == 2
              && strstr(g_text, "- 3 mask entries for villagers who are no longer in the village. "
                                "They will be removed.\r\n") != NULL
              && strstr(g_text, "The Village Masks file is backed up first; every removal is listed in the "
                                "Repairs log.") != NULL
              && ends_with_how_to_stop()
              && g_mask_repairs == (game % 2 ? 1 : 0) && (game % 2 == 0 || (g_mask_game == game && g_mask_slot == game)))) {
            break;
        }
    }
    check(game == 6, "orphan masks, every game: scanned silently at load, asked about at the quit, removed only on Repair");
    reset();
    g_masks = 1;
    play(2, 1, 8000, 16);
    vvfp_crosscheck_quit(2, 1);
    check(g_boxes == 1 && strstr(g_text, "- 1 mask entry for a villager who is no longer in the village. "
                                         "It will be removed.") != NULL, "... in the singular for one");
    reset();
    g_masks = 2;
    play(4, 1, 8000, 16);
    g_masks = 0;                    /* gone by the quit save (the villager's record taken) */
    vvfp_crosscheck_quit(4, 1);
    check(g_boxes == 0 && g_mask_repairs == 0, "masks no longer orphaned at the quit: nothing is asked");
    reset();
    g_masks = -1;
    g_graves = 1;
    play(5, 1, VVFP_XC_SETTLE_MS + 100, 16);
    check(g_mask_scans == 1 && vvfp_xc.examined == 0, "a mask scan that cannot tell yet is retried, like the others");
    reset();
    g_masks = 2;
    g_answer = IDYES;
    g_mask_result = 0;
    play(3, 1, 8000, 16);
    vvfp_crosscheck_quit(3, 1);
    check(g_mask_repairs == 1 && g_notices == 1, "a mask repair that could not be made: the player is told");
    reset();
    g_auto = 0;
    g_masks = 2;
    approve(1, 1);
    play(1, 1, 8000, 16);
    check(g_boxes == 0 && g_mask_repairs == 1 && g_mask_game == 1 && g_mask_slot == 1,
          "Repair Saves & Logs approval: the masks are removed at load, without asking");
    vvfp_crosscheck_quit(1, 1);
    check(g_boxes == 0 && !approval_there(1, 1), "... and nothing is left at the quit: the approval is used up");
    reset();
    g_auto = 0;
    g_masks = 2;
    g_mask_result = 0;
    approve(5, 1);
    play(5, 1, 8000, 16);
    g_mask_result = 1;
    vvfp_crosscheck_quit(5, 1);
    check(g_boxes == 0 && g_mask_repairs == 2 && !approval_there(5, 1),
          "... one that failed at load is completed after the quit save, then the approval is used up");

    /* ---- An older build's "Cross-Check" folder (native/shared/save_layout.h): never moved.  An
       approval there is the player's, used where it is; an approval under BOTH names is acted on
       under neither, and neither file is touched. ---- */
    reset();
    {
        wchar_t sub[MAX_PATH], old_sub[MAX_PATH], old_file[MAX_PATH], new_file[MAX_PATH], path[MAX_PATH];
        unsigned int body[4] = { 0x31415256u, 1u, 2u, 1u };
        HANDLE f;
        DWORD put = 0;
        wsprintfW(sub, L"%ls\\Virtual Villagers Fun Patcher Data\\Log Checks", g_folder);
        wsprintfW(old_sub, L"%ls\\Virtual Villagers Fun Patcher Data\\Cross-Check", g_folder);
        wsprintfW(old_file, L"%ls\\Virtual Villagers 2 Repair Approved - Save 1.dat", old_sub);
        wsprintfW(new_file, L"%ls\\Virtual Villagers 2 Repair Approved - Save 1.dat", sub);
        RemoveDirectoryW(sub);
        CreateDirectoryW(old_sub, NULL);
        f = CreateFileW(old_file, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        WriteFile(f, body, sizeof(body), &put, NULL);
        CloseHandle(f);
        check(vvfp_xc_approval_path(2, 1, path) && lstrcmpW(path, old_file) == 0 && vvfp_xc_approved(2, 1)
              && GetFileAttributesW(sub) == INVALID_FILE_ATTRIBUTES,
              "an older build's Cross-Check approval is used where it is, never moved");
        g_auto = 0;
        g_graves = 1;
        play(2, 1, 8000, 16);
        vvfp_crosscheck_quit(2, 1);
        check(g_boxes == 0 && g_later_graves == 1 && g_now_graves == 1
              && GetFileAttributesW(old_file) == INVALID_FILE_ATTRIBUTES,
              "... and that approval is used, like any other");
        /* Both there: neither is acted on, neither is touched. */
        reset();
        f = CreateFileW(old_file, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        WriteFile(f, body, sizeof(body), &put, NULL);
        CloseHandle(f);
        CreateDirectoryW(sub, NULL);
        f = CreateFileW(new_file, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        WriteFile(f, body, sizeof(body), &put, NULL);
        CloseHandle(f);
        g_auto = 0;
        g_graves = 1;
        play(2, 1, 8000, 16);
        vvfp_crosscheck_quit(2, 1);
        check(!vvfp_xc_approved(2, 1) && g_now_graves == 0
              && GetFileAttributesW(old_file) != INVALID_FILE_ATTRIBUTES
              && GetFileAttributesW(new_file) != INVALID_FILE_ATTRIBUTES,
              "an approval under both Log Checks and Cross-Check is acted on under neither, and both are kept");
        DeleteFileW(old_file);
        DeleteFileW(new_file);
        RemoveDirectoryW(old_sub);
    }

    /* ---- Missing last names: words split as Python's str.split() splits them -- a trailing, leading or
       doubled space is never a last name, while a second real word still is. ---- */
    {
        static const char *const spaced[] = { "Kele ", "Iko  Ana", "Lani II ", " Pua", "Mano Kai " };
        reset();
        ln_clear();
        ln_write(3, 1, 0, "VVFP LAST NAMES v1 game=3\nrule\tfather\n");
        villagers(spaced, 5);
        g_answer = IDNO;
        play(3, 1, 8000, 16);
        vvfp_crosscheck_quit(3, 1);
        check(g_boxes == 1 && strstr(g_text, "3 villagers have no last name") != NULL
              && strstr(g_text, "Kele ") != NULL && strstr(g_text, "Lani II ") != NULL
              && strstr(g_text, " Pua") != NULL && strstr(g_text, "Iko") == NULL && strstr(g_text, "Mano") == NULL,
              "missing last names: \"Kele \", \"Lani II \" and \" Pua\" have none (an empty word is no last "
              "name); \"Iko  Ana\" and \"Mano Kai \" have one");
        ln_clear();
    }

    /* ---- Missing last names (v1.35.66): asked about after the quit save, with the setting on, only in a
       village that uses last names; the answer is queued for the patcher, "Not now" is remembered. ---- */
    {
        static const char *const village[] = {
            "Kalea", "Soda Akikai", "Soda II", NULL, "Mele Ana", "Tavi Lono II",
        };
        static const char *const grown[] = {
            "Kalea", "Soda Akikai", "Soda II", NULL, "Mele Ana", "Tavi Lono II", "Noa",
        };
        const char *file;
        reset();
        ln_clear();
        ln_write(3, 1, 0, "VVFP LAST NAMES v1 game=3\nrule\tfather\nwhole\tMele Ana\n");
        villagers(village, 6);
        g_answer = IDYES;
        play(3, 1, 8000, 16);
        check(g_boxes == 0, "missing last names: nothing is asked while the village is played");
        vvfp_crosscheck_quit(3, 1);
        file = ln_read(3, 1, 1);
        check(g_boxes == 1 && strstr(g_text, "3 villagers have no last name") != NULL
              && strstr(g_text, "Kalea, Soda II, Mele Ana") != NULL && strstr(g_text, "Akikai") == NULL
              && strstr(g_text, "Tavi") == NULL,
              "missing last names: one word, a numeral after one word, and a name the record says is one first "
              "name have none; a second word, numeral or not, is one");
        check(strstr(g_text, "Repair Saves & Logs...") != NULL
              && strstr(g_text, "'Give villagers last names, in the game and the logs'") != NULL
              && strstr(g_text, "\"Remind me\"") != NULL && strstr(g_text, "\"Not now\"") != NULL
              && strstr(g_text, "untick 'Check logs automatically'") != NULL,
              "... the box says, step by step, how to give them last names, and how to stop the checks");
        check(strcmp(file, "VVFP MISSING LAST NAMES v1 game=3\nasked\tremind\nvillager\tKalea\t0\t0\n"
                           "villager\tSoda II\t2\t2\nvillager\tMele Ana\t4\t4\n") == 0,
              "... Remind me: the request is queued for the patcher, with each villager (head and body 0 kept)");
        play(3, 1, 8000, 16);
        vvfp_crosscheck_quit(3, 1);
        check(g_boxes == 1, "... and the same villagers are not asked about again");
        villagers(grown, 7);
        g_answer = IDNO;
        play(3, 1, 8000, 16);
        vvfp_crosscheck_quit(3, 1);
        file = ln_read(3, 1, 1);
        check(g_boxes == 2 && strstr(g_text, "4 villagers have no last name") != NULL
              && strstr(file, "asked\tnot now\n") != NULL && strstr(file, "villager\tNoa\t6\t6\n") != NULL,
              "a new villager with no last name (an arrival): asked again; Not now is kept with every one of them");
        play(3, 1, 8000, 16);
        vvfp_crosscheck_quit(3, 1);
        check(g_boxes == 2, "... and after Not now they are not asked about again");

        /* A village that does not use last names: no row, no record. */
        reset();
        ln_clear();
        villagers(village, 6);
        g_answer = IDYES;
        play(4, 1, 8000, 16);
        vvfp_crosscheck_quit(4, 1);
        check(g_boxes == 0 && ln_read(4, 1, 1)[0] == '\0',
              "a village that does not use last names is never asked about them");
        /* The row shipped, no record yet: it does. */
        g_ln_shipped = 1;
        play(4, 1, 8000, 16);
        vvfp_crosscheck_quit(4, 1);
        /* No record: "Mele Ana" is a first and a last name (no "whole" line says otherwise). */
        check(g_boxes == 1 && strstr(g_text, "2 villagers have no last name") != NULL
              && strstr(g_text, "Kalea, Soda II\r\n") != NULL
              && strstr(ln_read(4, 1, 1), "asked\tremind\n") != NULL,
              "... with the Last Names row shipped it is, every game alike");
        /* The setting off: nothing. */
        reset();
        ln_clear();
        g_ln_shipped = 1;
        g_auto = 0;
        villagers(village, 6);
        play(1, 1, 8000, 16);
        vvfp_crosscheck_quit(1, 1);
        check(g_boxes == 0 && ln_read(1, 1, 1)[0] == '\0', "the setting off: missing last names are never asked about");
        /* A box that cannot be shown, or is not answered: nothing is written. */
        reset();
        ln_clear();
        g_ln_shipped = 1;
        g_box_fails = 1;
        villagers(village, 6);
        play(2, 1, 8000, 16);
        vvfp_crosscheck_quit(2, 1);
        check(ln_read(2, 1, 1)[0] == '\0', "a last-names box that cannot be shown writes nothing");
        reset();
        ln_clear();
        g_ln_shipped = 1;
        g_box_delay = 2500;
        villagers(village, 6);
        play(5, 1, 8000, 16);
        vvfp_crosscheck_quit(5, 1);
        check(ln_read(5, 1, 1)[0] == '\0', "a last-names box not answered in time writes nothing");
        Sleep(1500);
        /* Repairs and last names: the repair box first, then the last names. */
        reset();
        ln_clear();
        g_ln_shipped = 1;
        g_graves = 1;
        villagers(village, 6);
        g_answer = IDNO;
        play(5, 1, 8000, 16);
        vvfp_crosscheck_quit(5, 1);
        check(g_boxes == 2 && strstr(g_text, "no last name") != NULL && g_now_graves == 0,
              "with repairs found too: the repair box, then the last-names box, each answered on its own");
        ln_clear();
        {
            wchar_t sub[MAX_PATH];
            wsprintfW(sub, L"%ls\\Virtual Villagers Fun Patcher Data\\Last Names", g_folder);
            RemoveDirectoryW(sub);
        }
    }

    clear_approvals();
    {
        wchar_t sub[MAX_PATH];
        wsprintfW(sub, L"%ls\\Virtual Villagers Fun Patcher Data\\Log Checks", g_folder);
        RemoveDirectoryW(sub);
        wsprintfW(sub, L"%ls\\Virtual Villagers Fun Patcher Data", g_folder);
        RemoveDirectoryW(sub);
        RemoveDirectoryW(g_folder);
    }
    check(g_play_boxes == 0, "NO message box was ever shown while a village was being played");
    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
