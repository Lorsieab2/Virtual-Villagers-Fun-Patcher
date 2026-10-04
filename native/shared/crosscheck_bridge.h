/* The Origins companions' side of the first-load cross-check (v1.35.57, all
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
       save, where its header is certain).

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
    int counts[5];
    int graves;                   /* graves missing from the Deaths log, when > 0 */
    volatile LONG answer;         /* 0 while the prompt is open; IDYES or IDNO */
    HANDLE thread;
    char text[2048];
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
        vvfp_xc_add("- %d expecting %s the wrong father recorded for the baby. It will be corrected.\r\n",
                    c[4], "mother has", "mothers have");
        lstrcatA(vvfp_xc.text, "  (The parentage file is backed up first; every change is listed in the Repairs "
                               "log.)\r\n");
    }
    if (vvfp_xc.graves > 0) {
        vvfp_xc_add("- %d %s no record in the Deaths log (buried before the log existed). Their Death records "
                    "will be added the next time you save and quit the game.\r\n",
                    vvfp_xc.graves, "grave has", "graves have");
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
}

/* Examine the village: scan every part; ask when anything was found. */
static void vvfp_xc_examine(int game, int slot, DWORD now) {
    vvfp_xc_scan_parents_fn scan_parents = NULL;
    vvfp_xc_scan_graves_fn scan_graves;
    int parents = 0, graves = 0, pending;
    memset(vvfp_xc.counts, 0, sizeof(vvfp_xc.counts));
    if (game == 1) {
        scan_parents = (vvfp_xc_scan_parents_fn)VVFP_XC_PROC(VVFP_XC_PARENTAGE_DLL, "Vv1ParentageCrossCheckScan");
        parents = scan_parents != NULL ? scan_parents(vvfp_xc.counts) : 0;
    }
    scan_graves = (vvfp_xc_scan_graves_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseScanGraves");
    graves = scan_graves != NULL ? scan_graves(game, slot) : 0;
    pending = parents < 0 || graves < 0;
    if (pending && vvfp_xc.retries < VVFP_XC_RETRIES) {
        ++vvfp_xc.retries;            /* one of them cannot tell yet: ask once, for everything */
        vvfp_xc.next_try = now + VVFP_XC_RETRY_MS;
        return;
    }
    vvfp_xc.parents_found = parents == 1;
    vvfp_xc.graves = graves > 0 ? graves : 0;
    if (!vvfp_xc.parents_found && vvfp_xc.graves == 0) {
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
