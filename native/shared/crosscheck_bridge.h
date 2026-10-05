/* The Origins companions' side of the first-load cross-check (v1.35.58, all
   five games): ONE Repair / Not now prompt for everything the patcher's
   records disagree with their source of truth on, shown before anything is
   changed (owner: "the player should be notified first before any fix
   runs").

   WHAT IT ASKS ABOUT.  Only what a source of truth confirms wrong AND the
   patcher can put right (docs/first-load-cross-check.md has the full table
   of every log and data file, and why the others are only reported by
   scripts/vvfp_consistency_check.py):

     - A New Home's recorded parents, rebuilt from the village's Births and
       Conceptions log ("VVFP VV1 Parentage.dll": Vv1ParentageCrossCheckScan
       and Vv1ParentageCrossCheckApply; vv1_crosscheck.inc has the rules);
     - graves with no Death record in the village's Deaths log, every game
       ("VVFP Cause of Death.dll": VvfpCauseScanGraves and
       VvfpCauseRepairGraves; the records are written at the village's next
       save, where its header is certain);
     - villagers with neither a Birth nor an Arrived record in the Births
       log, every game ("VVFP Cause of Death.dll": VvfpCauseScanArrivals and
       VvfpCauseRepairArrivals, the same contract as the graves pair);
     - villagers the save says were born in the village (The Lost Children
       to New Believers keep each villager's parents on the record) with no
       Birth record: one is written from the save ("VVFP Cause of
       Death.dll": VvfpCauseScanBirths and VvfpCauseRepairBirths, the same
       contract);
     - the Village Elders and Village Statistics files, where the save and
       the logs prove more than they hold ("VVFP Statistics Export.dll":
       VvfpStatisticsScanReconcile, which also writes the prompt's lines, and
       VvfpStatisticsRepairReconcile; statistics_reconcile.inc).  That companion
       is loaded by the executable only at its first save, so it is loaded
       here, by full path from the executable's folder, when it is there;
     - orphan entries in the Village Masks file, every game (v1.35.59): an
       entry whose stored villager identity no villager in the village
       carries.  The masks are this companion's own, so its own
       vvfp_xc_masks_scan and vvfp_xc_masks_repair (orphan_masks.h has the
       rule) are called -- every Origins companion defines the pair after
       its mask code; nothing is looked up.  Unlike the others the repair
       is made at once: the mask file is written whenever the table
       changes, not at a save.

   What is not repaired -- the Village Population and History logs (written
   from the game at every save), both Village Roster files (a mismatch IS
   the evidence the next save uses), custom titles, stews and the
   game's own statistics counters -- is reported by
   scripts/vvfp_consistency_check.py with the reason
   (docs/first-load-cross-check.md).

   A New Home's expected fathers left on villagers who are not expecting are
   part of the first item.  The later games keep the expected father in the
   game's own record (the mother's, set and spent by the game), so the
   patcher has no copy of it to go stale there.

   Each is found through its own companion's exports, by the module name
   that companion was loaded under (GetModuleHandle: the folder it was
   loaded from does not matter).  A companion that is not loaded -- its row
   is off -- or that does not export the call is simply not asked.

   WHEN.  Called from the companion's village-only per-frame path (a head
   draw, the village frame, the compositor with a village).  The village is
   examined once per LOAD, when it has been on screen for VVFP_XC_SETTLE_MS
   continuously: the load-time catch-up runs inside the first ticks, before
   the village is drawn at all, so it is over by then.  A gap in the calls of
   more than VVFP_XC_GAP_MS (the menus, a loading screen) or a different slot
   is a new load and is examined again.  A scan that cannot tell yet (-1:
   the table is not this village's yet, a log is locked) is retried every
   VVFP_XC_RETRY_MS, VVFP_XC_RETRIES times, before the load is let go.

   THE PROMPT.  A message box whose two buttons read "Repair" and "Not now",
   owned by the game's window and shown from a thread of its own: the game's
   render path (where every one of these entries runs) is never blocked by a
   modal loop -- the reentry the VV1 Origins companion's history warns
   about -- and the answer is acted on HERE, on the game's own thread, at
   the next call.  The SDL hint that keeps an exclusive-fullscreen game from
   minimising when it loses focus is set first, as the Origins menus do.

     Repair:  each part found is repaired by its own companion (backed up,
              written atomically, listed in a log, marked done).
     Not now: nothing is changed and nothing is recorded; the question comes
              back the next time this village is loaded.

   Included once per companion, after cause_bridge.h; everything is
   file-static. */
#ifndef VVFP_CROSSCHECK_BRIDGE_H
#define VVFP_CROSSCHECK_BRIDGE_H

#include <windows.h>
#include <string.h>

#define VVFP_XC_PARENTAGE_DLL "VVFP VV1 Parentage.dll"
#define VVFP_XC_CAUSE_DLL     "VVFP Cause of Death.dll"
#define VVFP_XC_SETTLE_MS     3000u
#define VVFP_XC_GAP_MS        2000u
#define VVFP_XC_RETRY_MS      2000u
#define VVFP_XC_RETRIES       15

typedef int (__stdcall *vvfp_xc_scan_parents_fn)(int *counts);
typedef int (__stdcall *vvfp_xc_apply_parents_fn)(void);
typedef int (__stdcall *vvfp_xc_scan_graves_fn)(int game, int slot);
typedef void (__stdcall *vvfp_xc_repair_graves_fn)(int game, int slot, int repair);
typedef int (__stdcall *vvfp_xc_scan_text_fn)(int game, int slot, char *text, int cap);
#define VVFP_XC_STATS_DLL     "VVFP Statistics Export.dll"

/* The companion's own orphan mask entries (orphan_masks.h), defined by every
   Origins companion after its mask code.  The scan: how many there are (it
   notes them for the repair), 0 none, -1 cannot tell yet (the masks or the
   village are not loaded); reads only.  The repair: with `repair` 1, removes
   the ones the scan noted that are still orphans; with 0, changes nothing. */
static int vvfp_xc_masks_scan(int game, int slot);
static void vvfp_xc_masks_repair(int game, int slot, int repair);
static void vv_om_describe(int count, char *text, size_t cap);

/* The harness replaces these to stand in for the companions and the clock. */
#ifndef VVFP_XC_PROC
#define VVFP_XC_PROC(module, name) vvfp_xc_proc(module, name)
static FARPROC vvfp_xc_proc(const char *module, const char *name) {
    HMODULE m = GetModuleHandleA(module);
    return m != NULL ? GetProcAddress(m, name) : NULL;
}
#endif
#ifndef VVFP_XC_NOW
#define VVFP_XC_NOW() GetTickCount()
#endif
/* A companion that may not be loaded yet (the statistics companion, loaded
   by the executable at its first save): the one already loaded, else the
   file of that name beside the executable, loaded by full path; NULL when
   it is not there (its row is off). */
#ifndef VVFP_XC_LOAD
#define VVFP_XC_LOAD(module, name) vvfp_xc_load(module, name)
static FARPROC vvfp_xc_load(const char *module, const char *name) {
    char path[MAX_PATH];
    char *slash;
    DWORD n;
    HMODULE m = GetModuleHandleA(module);
    if (m == NULL) {
        n = GetModuleFileNameA(NULL, path, MAX_PATH);
        slash = n != 0 && n < MAX_PATH ? strrchr(path, '\\') : NULL;
        if (slash == NULL || (size_t)(slash + 1 - path) + lstrlenA(module) + 1 > MAX_PATH) {
            return NULL;
        }
        lstrcpyA(slash + 1, module);
        if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) {
            return NULL;
        }
        m = LoadLibraryA(path);
    }
    return m != NULL ? GetProcAddress(m, name) : NULL;
}
#endif

#define VVFP_XC_ARMED   0
#define VVFP_XC_ASKING  1
#define VVFP_XC_DECIDED 2

static struct {
    int slot;                     /* the load being examined (0: none yet) */
    DWORD seen;                   /* when this load's village was first on screen */
    DWORD last;                   /* the last call */
    DWORD next_try;
    int state;
    int retries;
    int asked_game, asked_slot;
    int parents_found;            /* the parentage scan said 1 */
    int counts[6];
    int graves;                   /* graves missing from the Deaths log, when > 0 */
    int arrivals;                 /* villagers with no Birth or Arrived record, when > 0 */
    int births;                   /* villagers born here with no Birth record, when > 0 */
    int stats;                    /* changes to the Elders and Statistics files, when > 0 */
    int masks;                    /* orphan mask entries, when > 0 */
    char stats_text[1536];        /* their lines, from the statistics companion */
    volatile LONG answer;         /* 0 while the prompt is open; IDYES or IDNO */
    HANDLE thread;
    char text[4096];
} vvfp_xc;

static HHOOK vvfp_xc_hook;

/* Relabel the prompt's two buttons as it opens. */
static LRESULT CALLBACK vvfp_xc_cbt(int code, WPARAM wparam, LPARAM lparam) {
    if (code == HCBT_ACTIVATE) {
        SetDlgItemTextA((HWND)wparam, IDYES, "Repair");
        SetDlgItemTextA((HWND)wparam, IDNO, "Not now");
    }
    return CallNextHookEx(vvfp_xc_hook, code, wparam, lparam);
}

/* The game's own window: a visible, unowned top-level window of this process. */
static BOOL CALLBACK vvfp_xc_find_window(HWND window, LPARAM out) {
    DWORD pid = 0;
    GetWindowThreadProcessId(window, &pid);
    if (pid == GetCurrentProcessId() && IsWindowVisible(window) && GetWindow(window, GW_OWNER) == NULL) {
        *(HWND *)out = window;
        return FALSE;
    }
    return TRUE;
}

static DWORD WINAPI vvfp_xc_prompt(LPVOID owner) {
    int answer;
    vvfp_xc_hook = SetWindowsHookExA(WH_CBT, vvfp_xc_cbt, NULL, GetCurrentThreadId());
    answer = MessageBoxA((HWND)owner, vvfp_xc.text, "Virtual Villagers Fun Patcher",
                         MB_YESNO | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND | MB_DEFBUTTON1);
    if (vvfp_xc_hook != NULL) {
        UnhookWindowsHookEx(vvfp_xc_hook);
        vvfp_xc_hook = NULL;
    }
    InterlockedExchange(&vvfp_xc.answer, answer == IDYES ? IDYES : IDNO);
    return 0;
}

static DWORD WINAPI vvfp_xc_notice(LPVOID owner) {
    MessageBoxA((HWND)owner,
                "The parents could not be repaired: a file could not be read or written. Nothing was "
                "changed, and you will be asked again the next time this village is loaded.",
                "Virtual Villagers Fun Patcher", MB_OK | MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND);
    return 0;
}

static void vvfp_xc_add(const char *format, int count, const char *one, const char *many) {
    size_t len = (size_t)lstrlenA(vvfp_xc.text);
    if (count > 0 && len + 400 < sizeof(vvfp_xc.text)) {
        wsprintfA(vvfp_xc.text + len, format, count, count == 1 ? one : many);
    }
}

static void vvfp_xc_compose(void) {
    const int *c = vvfp_xc.counts;
    lstrcpyA(vvfp_xc.text, "The Fun Patcher checked this village's records against its save and its logs, "
                           "and found some it can put right:\r\n\r\n");
    if (vvfp_xc.parents_found) {
        vvfp_xc_add("- %d %s the wrong parents recorded. They will be corrected from the Births log.\r\n",
                    c[0], "villager has", "villagers have");
        vvfp_xc_add("- %d %s parents recorded but no Birth record in the Births log (founders or grown "
                    "arrivals). They will be set to unknown.\r\n", c[1], "villager has", "villagers have");
        vvfp_xc_add("- %d %s parents the Births log cannot tell apart. They will be set to unknown.\r\n",
                    c[2], "villager has", "villagers have");
        vvfp_xc_add("- %d %s no parents recorded. They will be filled in from the Births log.\r\n",
                    c[3], "villager has", "villagers have");
        vvfp_xc_add("- %d %s the wrong father recorded for a pregnancy. The father will be corrected "
                    "from the mother's last conception in the Births log.\r\n", c[4], "mother has", "mothers have");
        vvfp_xc_add("- %d %s an expected father recorded for a pregnancy that is over. It will be cleared.\r\n",
                    c[5], "villager has", "villagers have");
        lstrcatA(vvfp_xc.text, "  (The parentage file is backed up first; every change is listed in the Repairs "
                               "log.)\r\n");
    }
    if (vvfp_xc.graves > 0) {
        vvfp_xc_add("- %d %s no record in the Deaths log (buried before the log existed). Their Death records "
                    "will be added the next time you save and quit the game.\r\n",
                    vvfp_xc.graves, "grave has", "graves have");
    }
    if (vvfp_xc.arrivals > 0) {
        vvfp_xc_add("- %d %s no Birth or Arrived record in the Births log (arrived before that record existed). "
                    "Their Arrived records will be added the next time you save and quit the game.\r\n",
                    vvfp_xc.arrivals, "villager has", "villagers have");
    }
    if (vvfp_xc.births > 0) {
        vvfp_xc_add("- %d %s born in the village but no Birth record in the Births log (born before that record "
                    "existed). Their Birth records will be added from the save the next time you save and quit "
                    "the game.\r\n", vvfp_xc.births, "villager was", "villagers were");
    }
    if (vvfp_xc.stats > 0 && (size_t)lstrlenA(vvfp_xc.text) + (size_t)lstrlenA(vvfp_xc.stats_text) + 400
                                 < sizeof(vvfp_xc.text)) {
        lstrcatA(vvfp_xc.text, vvfp_xc.stats_text);
        lstrcatA(vvfp_xc.text, "  (The Village Elders and Village Statistics files are changed the next time you save "
                               "and quit the game; they are backed up first and every change is listed in the "
                               "Repairs log.)\r\n");
    }
    if (vvfp_xc.masks > 0) {
        size_t len = (size_t)lstrlenA(vvfp_xc.text);
        if (len + 400 < sizeof(vvfp_xc.text)) {
            vv_om_describe(vvfp_xc.masks, vvfp_xc.text + len, sizeof(vvfp_xc.text) - len);
            lstrcatA(vvfp_xc.text, "  (The Village Masks file is backed up first; every removal is listed in the "
                                   "Repairs log.)\r\n");
        }
    }
    lstrcatA(vvfp_xc.text, "\r\nRepair them now?\r\n\r\n\"Not now\" changes nothing; you will be asked again the "
                           "next time this village is loaded.");
}

/* The player has answered (on the prompt's thread); act on it here. */
static void vvfp_xc_answered(int game) {
    int yes = vvfp_xc.answer == IDYES;
    const vvfp_story_host *host = vvfp_story_host_table();
    int slot_now = host != NULL && host->slot != NULL ? host->slot() : 0;
    vvfp_xc_repair_graves_fn repair_graves;
    if (vvfp_xc.thread != NULL) {
        CloseHandle(vvfp_xc.thread);
        vvfp_xc.thread = NULL;
    }
    vvfp_xc.state = VVFP_XC_DECIDED;
    if (game != vvfp_xc.asked_game || slot_now != vvfp_xc.asked_slot) {
        yes = 0;                      /* another village by now: the answer was not about it */
    }
    if (yes && vvfp_xc.parents_found) {
        vvfp_xc_apply_parents_fn apply =
            (vvfp_xc_apply_parents_fn)VVFP_XC_PROC(VVFP_XC_PARENTAGE_DLL, "Vv1ParentageCrossCheckApply");
        if (apply == NULL || !apply()) {
            HWND owner = NULL;
            HANDLE t;
            EnumWindows(vvfp_xc_find_window, (LPARAM)&owner);
            t = CreateThread(NULL, 0, vvfp_xc_notice, owner, 0, NULL);
            if (t != NULL) {
                CloseHandle(t);
            }
        }
    }
    if (vvfp_xc.graves > 0) {
        repair_graves = (vvfp_xc_repair_graves_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseRepairGraves");
        if (repair_graves != NULL) {
            repair_graves(vvfp_xc.asked_game, vvfp_xc.asked_slot, yes);
        }
    }
    if (vvfp_xc.arrivals > 0) {
        /* The same contract as the graves pair (feat/arrived-records). */
        repair_graves = (vvfp_xc_repair_graves_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseRepairArrivals");
        if (repair_graves != NULL) {
            repair_graves(vvfp_xc.asked_game, vvfp_xc.asked_slot, yes);
        }
    }
    if (vvfp_xc.births > 0) {
        repair_graves = (vvfp_xc_repair_graves_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseRepairBirths");
        if (repair_graves != NULL) {
            repair_graves(vvfp_xc.asked_game, vvfp_xc.asked_slot, yes);
        }
    }
    if (vvfp_xc.stats > 0) {
        repair_graves = (vvfp_xc_repair_graves_fn)VVFP_XC_LOAD(VVFP_XC_STATS_DLL, "VvfpStatisticsRepairReconcile");
        if (repair_graves != NULL) {
            repair_graves(vvfp_xc.asked_game, vvfp_xc.asked_slot, yes);
        }
    }
    if (vvfp_xc.masks > 0) {
        vvfp_xc_masks_repair(vvfp_xc.asked_game, vvfp_xc.asked_slot, yes);
    }
}

/* Examine the village: scan every part; ask when anything was found. */
static void vvfp_xc_examine(int game, int slot, DWORD now) {
    vvfp_xc_scan_parents_fn scan_parents = NULL;
    vvfp_xc_scan_graves_fn scan_graves, scan_arrivals, scan_births;
    vvfp_xc_scan_text_fn scan_stats;
    int parents = 0, graves = 0, arrivals = 0, births = 0, stats = 0, masks, pending;
    memset(vvfp_xc.counts, 0, sizeof(vvfp_xc.counts));
    if (game == 1) {
        scan_parents = (vvfp_xc_scan_parents_fn)VVFP_XC_PROC(VVFP_XC_PARENTAGE_DLL, "Vv1ParentageCrossCheckScan");
        parents = scan_parents != NULL ? scan_parents(vvfp_xc.counts) : 0;
    }
    scan_graves = (vvfp_xc_scan_graves_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseScanGraves");
    graves = scan_graves != NULL ? scan_graves(game, slot) : 0;
    scan_arrivals = (vvfp_xc_scan_graves_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseScanArrivals");
    arrivals = scan_arrivals != NULL ? scan_arrivals(game, slot) : 0;
    scan_births = (vvfp_xc_scan_graves_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseScanBirths");
    births = scan_births != NULL ? scan_births(game, slot) : 0;
    scan_stats = (vvfp_xc_scan_text_fn)VVFP_XC_LOAD(VVFP_XC_STATS_DLL, "VvfpStatisticsScanReconcile");
    vvfp_xc.stats_text[0] = '\0';
    stats = scan_stats != NULL ? scan_stats(game, slot, vvfp_xc.stats_text, (int)sizeof(vvfp_xc.stats_text)) : 0;
    masks = vvfp_xc_masks_scan(game, slot);
    pending = parents < 0 || graves < 0 || arrivals < 0 || births < 0 || stats < 0 || masks < 0;
    if (pending && vvfp_xc.retries < VVFP_XC_RETRIES) {
        ++vvfp_xc.retries;            /* one of them cannot tell yet: ask once, for everything */
        vvfp_xc.next_try = now + VVFP_XC_RETRY_MS;
        return;
    }
    vvfp_xc.parents_found = parents == 1;
    vvfp_xc.graves = graves > 0 ? graves : 0;
    vvfp_xc.arrivals = arrivals > 0 ? arrivals : 0;
    vvfp_xc.births = births > 0 ? births : 0;
    vvfp_xc.stats = stats > 0 && vvfp_xc.stats_text[0] != '\0' ? stats : 0;
    vvfp_xc.masks = masks > 0 ? masks : 0;
    if (!vvfp_xc.parents_found && vvfp_xc.graves == 0 && vvfp_xc.arrivals == 0 && vvfp_xc.births == 0
        && vvfp_xc.stats == 0 && vvfp_xc.masks == 0) {
        vvfp_xc.state = VVFP_XC_DECIDED;   /* nothing to ask about on this load */
        return;
    }
    vvfp_xc_compose();
    vvfp_xc.asked_game = game;
    vvfp_xc.asked_slot = slot;
    vvfp_xc.answer = 0;
    {
        HWND owner = NULL;
        HMODULE sdl = GetModuleHandleA("SDL2.dll");
        if (sdl != NULL) {
            typedef int(__cdecl * set_hint_t)(const char *, const char *);
            set_hint_t set_hint = (set_hint_t)GetProcAddress(sdl, "SDL_SetHint");
            if (set_hint != NULL) {
                set_hint("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0");
            }
        }
        EnumWindows(vvfp_xc_find_window, (LPARAM)&owner);
        vvfp_xc.thread = CreateThread(NULL, 0, vvfp_xc_prompt, owner, 0, NULL);
    }
    if (vvfp_xc.thread == NULL) {
        vvfp_xc.state = VVFP_XC_DECIDED;   /* could not ask: change nothing; the next load asks */
        return;
    }
    vvfp_xc.state = VVFP_XC_ASKING;
}

/* From the companion's village-only per-frame path.  `on_screen` is the
   caller's own word that a village is being played right now. */
static void vvfp_crosscheck_bridge(int game, int on_screen) {
    DWORD now = VVFP_XC_NOW();
    const vvfp_story_host *host;
    int slot = 0;
    if (vvfp_xc.state == VVFP_XC_ASKING) {
        if (vvfp_xc.answer != 0) {
            vvfp_xc_answered(game);
            vvfp_xc.last = now;
        }
        return;                       /* nothing else happens while the player decides */
    }
    if (on_screen) {
        host = vvfp_story_host_table();
        slot = host != NULL && host->slot != NULL ? host->slot() : 0;
    }
    if (slot < 1 || slot > 5) {
        vvfp_xc.slot = 0;             /* no village: the next one seen is a new load */
        return;
    }
    if (slot != vvfp_xc.slot || now - vvfp_xc.last > VVFP_XC_GAP_MS) {
        vvfp_xc.slot = slot;          /* a new load */
        vvfp_xc.seen = now;
        vvfp_xc.state = VVFP_XC_ARMED;
        vvfp_xc.retries = 0;
        vvfp_xc.next_try = now;
    }
    vvfp_xc.last = now;
    if (vvfp_xc.state != VVFP_XC_ARMED || now - vvfp_xc.seen < VVFP_XC_SETTLE_MS
        || (LONG)(now - vvfp_xc.next_try) < 0) {
        return;
    }
    vvfp_xc_examine(game, slot, now);
}

#endif /* VVFP_CROSSCHECK_BRIDGE_H */
