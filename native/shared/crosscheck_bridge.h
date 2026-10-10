/* The Origins companions' side of the cross-check (v1.35.58, all five
   games): the patcher's records checked against their sources of truth, and
   repaired only when the player has said so.

   The owner (2026-10-05): "For the 'repair' popups that appear during
   gameplay, can you make them appear only if the player clicks the 'check
   logs' and 'repair' button?  Or perhaps have a setting in the patcher that
   toggles the automatic check during gameplay.  When it is toggled ON, it
   brings up the repair prompt when the game is closed, not while it is
   running, and only if there's a problem."  Both are built.  Later the
   same day: "Can you make the check logs automatically default on? (With a
   message in the prompt on how to turn the toggle off)" -- the setting is
   ON by default and the quit-time box ends with how to turn it off.
   NOTHING HERE EVER SHOWS ANYTHING WHILE A VILLAGE IS BEING PLAYED.

   WHAT IS CHECKED AND REPAIRED.  Only what a source of truth confirms wrong
   AND the patcher can put right (docs/first-load-cross-check.md has the full
   table of every log and data file, and why the others are only reported by
   scripts/vvfp_consistency_check.py):

     - A New Home's recorded parents, rebuilt from the village's Births and
       Conceptions log, with its expected fathers left on villagers who are
       not expecting ("VVFP VV1 Parentage.dll": Vv1ParentageCrossCheckScan
       and Vv1ParentageCrossCheckApply; vv1_crosscheck.inc has the rules);
     - graves with no Death record in the village's Deaths log, every game
       ("VVFP Cause of Death.dll": VvfpCauseScanGraves, VvfpCauseRepairGraves
       and VvfpCauseRepairGravesNow);
     - villagers with neither a Birth nor an Arrived record in the Births
       log, every game (VvfpCauseScanArrivals, VvfpCauseRepairArrivals,
       VvfpCauseRepairArrivalsNow);
     - villagers the save says were born in the village (The Lost Children
       to New Believers keep each villager's parents on the record) with no
       Birth record (VvfpCauseScanBirths, VvfpCauseRepairBirths,
       VvfpCauseRepairBirthsNow);
     - the Village Elders and Village Statistics files, where the save and
       the logs prove more than they hold ("VVFP Statistics Export.dll":
       VvfpStatisticsScanReconcile, which also writes the prompt's lines,
       VvfpStatisticsRepairReconcile and VvfpStatisticsRepairReconcileNow;
       statistics_reconcile.inc).  That companion is loaded by the
       executable only at its first save, so it is loaded here, by full path
       from the executable's folder, when this build ships it;
     - orphan entries in the Village Masks file, every game (v1.35.59): an
       entry whose stored villager identity no villager in the village
       carries (orphan_masks.h has the rule).  The masks are this
       companion's own, so its own vvfp_xc_masks_scan and
       vvfp_xc_masks_repair are called -- every Origins companion defines
       the pair after its mask code; nothing is looked up.  The repair is
       made there and then, approved at load included: the mask file is the
       companion's own, written whenever the table changes, not at a save.

   Each is found through its own companion's exports, by the module name it
   was loaded under; a companion that is not loaded (its row is off) or that
   does not export the call is simply not asked.  Every scan only reads,
   except that A New Home's parentage scan records "checked, nothing to
   change" in its own marker when it finds nothing (vv1_crosscheck.inc).

   TWO WAYS A REPAIR IS ALLOWED.

   1. "Check logs automatically" (the patcher's setting, ON by default; the
      patcher writes it into the executable's startup loader as bit 31 of
      the companion bits, VVFP_STARTUP_CHECK_LOGS).  When it is ON, each
      load of a village is scanned silently once the village has been on
      screen for VVFP_XC_SETTLE_MS (past the load-time catch-up), and
      nothing else happens then.  When the player QUITS the game after
      playing a village the scan found something in, the game's own quit
      save runs first; then, right after it and before the game frees
      anything, the village is scanned again (from the state the save just
      wrote) and, only if something is still confirmed wrong, ONE message
      box asks "Repair" or "Not now":

        Repair:  every part found is repaired there and then, by the
                 companion that owns it, from the state just saved (backed
                 up first, written atomically, every change listed in the
                 Repairs log, its marker written);
        Not now: nothing is written; the question comes back the next time
                 the player quits after playing that village.

      The box always ends with how to stop these checks (VVFP_XC_HOW_TO_STOP):
      the setting is written into the game when it is patched, so turning
      it off means unticking the box and patching the game again.

      When it is OFF, nothing is scanned and nothing is asked, ever.

   2. "Repair Saves & Logs..." in the patcher window (src/vv_log_tools.py): with the
      game closed it backs the save folder up, clears the parts' "already
      checked" markers (vv_log_tools.REARM_MARKERS) and writes the slot's
      approval file

          <save folder>\Virtual Villagers Fun Patcher Data\Cross-Check\
              Virtual Villagers N Repair Approved - Save S.dat

      (16 bytes: 'VRA1', version 1, game, slot).  The next time that
      village is played, whatever the setting, it is repaired WITHOUT a
      question: A New Home's parents as soon as the village has settled,
      everything else at the village's next save -- the quit save at the
      latest -- exactly as the companions always have; and at the quit,
      after that save, anything still found is completed the same way as an
      answered Repair.  Then the approval is used up (deleted).  A game that
      ends without its quit save (a crash) keeps the approval for the next
      time.  Start Over deletes it with the village (save_reset.c).

   WHY AT THE QUIT, AND WHY THERE.  Every game saves a village only when it
   is left (the save-slot screen's own save) and when the game quits: the
   application's shutdown, vtable +0x14 of the application object, saves
   the current slot and then the game's settings (slot 0), and only then
   deletes its screens and the village (A New Home 0x41B230, The Lost
   Children 0x423C30, The Secret City 0x427300, The Tree of Life 0x41E4C0,
   New Believers 0x423970).  The quit hook is the instruction right after
   those two saves (VVFP_XC_QUIT below): the save is on disk, every
   companion's save-time work has run, and the village, its graves and the
   save manager are all still exactly what was saved -- slot 0's save only
   writes the settings block and runs no patcher hook (the companions'
   save hooks take slots 1-5 only).  So every repair that the companions
   otherwise make at "the next save" can be completed there, from the same
   state, with the village's header read back from the saved file.  The
   slot is the one the shutdown just saved, read from the save manager the
   way the shutdown reads it ([application+4] + VVFP_XC_SLOT_FIELD).

   THE QUIT PROMPT never hangs the exit.  It is a message box on a thread of
   its own, owned by nothing; the game's window (this thread's own) is
   minimised first so the box is not hidden behind a full-screen game.
   While it is open the game's thread only takes messages SENT to it (so
   nothing waiting on it deadlocks) and runs no game code.  If the box
   cannot be shown, or is not answered within VVFP_XC_QUIT_WAIT_MS, nothing
   is done -- as "Not now" -- and the game goes on closing.  A fault
   anywhere in the quit check is caught, and the game goes on closing.

   Included once per companion, after cause_bridge.h; everything is
   file-static.  The companion calls vvfp_crosscheck_startup(game) from its
   VvfpStartup (and again, a no-op by then, from its per-frame path) to
   install the quit hook, and vvfp_crosscheck_bridge(game, on_screen) from
   its village-only per-frame path. */
#ifndef VVFP_CROSSCHECK_BRIDGE_H
#define VVFP_CROSSCHECK_BRIDGE_H

#include <windows.h>
#include <shlobj.h>
#include <stdint.h>
#include <string.h>
#include "patcher_files.h"
#include "save_layout.h"

#define VVFP_XC_PARENTAGE_DLL "VVFP VV1 Parentage.dll"
#define VVFP_XC_CAUSE_DLL     "VVFP Cause of Death.dll"
#define VVFP_XC_STATS_DLL     "VVFP Statistics Export.dll"
#define VVFP_XC_SETTLE_MS     3000u
#define VVFP_XC_GAP_MS        2000u
#define VVFP_XC_RETRY_MS      2000u
#define VVFP_XC_RETRIES       15
#ifndef VVFP_XC_QUIT_WAIT_MS
#define VVFP_XC_QUIT_WAIT_MS  (5u * 60u * 1000u)   /* how long the quit prompt waits for an answer */
#endif

#define VVFP_XC_LAST_NAMES_DLL "VVFP Last Names.dll"
#define VVFP_XC_NO_LAST_MAX    64                   /* villagers with no last name named in one prompt */
#define VVFP_XC_NAME_BYTES     32                   /* every game's name field, and its terminator */
#define VVFP_XC_LN_FILE_MAX    65536                /* the last-names files read here */

#define VVFP_XC_APPROVAL_MAGIC   0x31415256u        /* 'V' 'R' 'A' '1' */
#define VVFP_XC_APPROVAL_VERSION 1u

typedef int (__stdcall *vvfp_xc_scan_parents_fn)(int *counts);
typedef int (__stdcall *vvfp_xc_count_fn)(void);
typedef int (__stdcall *vvfp_xc_apply_parents_fn)(void);
typedef int (__stdcall *vvfp_xc_scan_graves_fn)(int game, int slot);
typedef void (__stdcall *vvfp_xc_repair_graves_fn)(int game, int slot, int repair);
typedef int (__stdcall *vvfp_xc_now_fn)(int game, int slot);
typedef int (__stdcall *vvfp_xc_scan_text_fn)(int game, int slot, char *text, int cap);

/* The companion's own orphan mask entries (orphan_masks.h), defined by every
   Origins companion after its mask code.  The scan: how many there are (it
   notes them for the repair), 0 none, -1 cannot tell yet (the masks or the
   village are not loaded); reads only.  The repair: removes the ones the
   scan noted that are still orphans; 1 when nothing is left undone. */
static int vvfp_xc_masks_scan(int game, int slot);
static int vvfp_xc_masks_repair(int game, int slot);
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
   file of that name in the patcher's folder beside the executable, loaded
   by full path (native/shared/patcher_files.h); NULL when it is not there
   (its row is off). */
#ifndef VVFP_XC_LOAD
#define VVFP_XC_LOAD(module, name) vvfp_xc_load(module, name)
static FARPROC vvfp_xc_load(const char *module, const char *name) {
    HMODULE m = GetModuleHandleA(module);
    if (m == NULL && vvfp_startup_ships(module) && vvfp_patcher_file_exists(module)) {
        m = vvfp_load_patcher_dll(module);
    }
    return m != NULL ? GetProcAddress(m, name) : NULL;
}
#endif
/* "Check logs automatically": the patcher's setting, handed over with this
   build's companion bits at game start.  Off when it was not (no loader). */
#ifndef VVFP_XC_AUTOMATIC
#define VVFP_XC_AUTOMATIC() (vvfp_startup_known && (vvfp_startup_shipped & VVFP_STARTUP_CHECK_LOGS) != 0u)
#endif
/* Whether this build gives new villagers last names (the Villagers Have Last
   Names row ships "VVFP Last Names.dll"). */
#ifndef VVFP_XC_LAST_NAMES_SHIPPED
#define VVFP_XC_LAST_NAMES_SHIPPED() vvfp_startup_ships(VVFP_XC_LAST_NAMES_DLL)
#endif
/* "<Documents>\LDW\<executable's name>": where the game saves (the same
   rule as native/shared/save_folder.c, which this companion does not link;
   nothing is created here -- the approval file is only read and deleted). */
#ifndef VVFP_XC_SAVE_FOLDER
#define VVFP_XC_SAVE_FOLDER(out) vvfp_xc_save_folder(out)
static int vvfp_xc_save_folder(wchar_t *out) {
    wchar_t docs[MAX_PATH];
    wchar_t exe[MAX_PATH];
    wchar_t *base;
    wchar_t *dot;
    DWORD n;
    if (FAILED(SHGetFolderPathW(NULL, CSIDL_PERSONAL, NULL, 0, docs))) {
        return 0;
    }
    n = GetModuleFileNameW(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    base = wcsrchr(exe, L'\\');
    base = base != NULL ? base + 1 : exe;
    dot = wcsrchr(base, L'.');
    if (dot != NULL) {
        *dot = L'\0';
    }
    if (base[0] == L'\0' || lstrlenW(docs) + 5 + lstrlenW(base) + 1 > MAX_PATH) {
        return 0;
    }
    wsprintfW(out, L"%ls\\LDW\\%ls", docs, base);
    return 1;
}
#endif

/* ---- The quit hook ------------------------------------------------------- */

/* Each game's application shutdown, right after its quit save (see above):
   the five bytes the hook displaces -- `mov ecx,[esi+0Ch]; test ecx,ecx`
   (A New Home, The Lost Children) or `mov ecx,[esi+8]; cmp ecx,edi` (the
   later three) -- all position-independent, and no branch lands inside
   them.  The Secret City's `je` over its saves when no slot is current
   lands on the first of them, which is the hook's own jump. */
static const struct {
    unsigned int va;
    unsigned char stock[5];
} VVFP_XC_QUIT[6] = {
    { 0, { 0 } },
    { 0x41B25Bu, { 0x8B, 0x4E, 0x0C, 0x85, 0xC9 } },
    { 0x423C5Bu, { 0x8B, 0x4E, 0x0C, 0x85, 0xC9 } },
    { 0x427331u, { 0x8B, 0x4E, 0x08, 0x3B, 0xCF } },
    { 0x41E4F1u, { 0x8B, 0x4E, 0x08, 0x3B, 0xCF } },
    { 0x4239A1u, { 0x8B, 0x4E, 0x08, 0x3B, 0xCF } },
};
/* The save manager's current-slot field ([application+4] + this): the slot
   the shutdown just saved (docs/start-over-reset-hook.md has the same
   fields as the village's current slot). */
static const unsigned int VVFP_XC_SLOT_FIELD[6] = { 0, 0xABE4u, 0x30378u, 0x12F24u, 0x17114u, 0x17D80u };

#define VVFP_XC_STUB_BYTES 32

static int vvfp_xc_hook_state;          /* 0 = not tried, 1 = installed, -1 = refused */

/* Hook the five bytes at `site` (which must hold `stock`): a stub that saves
   every register and the flags, calls handler(game, esi), restores them,
   runs the displaced instructions and jumps back.  The stub's page is never
   writable and executable at once.  1 when written; 0 and nothing written
   otherwise. */
static int vvfp_xc_hook(unsigned char *site, const unsigned char *stock, int game,
                        void (__stdcall *handler)(int, const unsigned char *)) {
    MEMORY_BASIC_INFORMATION info;
    unsigned char *page;
    unsigned char *p;
    unsigned char jump[5];
    DWORD old;
    int rel;
    if (VirtualQuery(site, &info, sizeof(info)) != sizeof(info) || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))
        || memcmp(site, stock, 5) != 0) {
        return 0;
    }
    page = (unsigned char *)VirtualAlloc(NULL, VVFP_XC_STUB_BYTES, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (page == NULL) {
        return 0;
    }
    p = page;
    *p++ = 0x60;                                      /* pushad */
    *p++ = 0x9C;                                      /* pushfd */
    *p++ = 0x56;                                      /* push esi (the application) */
    *p++ = 0x6A; *p++ = (unsigned char)game;          /* push game */
    *p++ = 0xE8;                                      /* call handler (stdcall: pops both) */
    rel = (int)((uintptr_t)handler - ((uintptr_t)p + 4));
    memcpy(p, &rel, 4); p += 4;
    *p++ = 0x9D;                                      /* popfd */
    *p++ = 0x61;                                      /* popad */
    memcpy(p, stock, 5); p += 5;                      /* the displaced instructions */
    *p++ = 0xE9;                                      /* jmp back */
    rel = (int)((uintptr_t)(site + 5) - ((uintptr_t)p + 4));
    memcpy(p, &rel, 4);
    if (!VirtualProtect(page, VVFP_XC_STUB_BYTES, PAGE_EXECUTE_READ, &old)) {
        VirtualFree(page, 0, MEM_RELEASE);
        return 0;
    }
    FlushInstructionCache(GetCurrentProcess(), page, VVFP_XC_STUB_BYTES);
    jump[0] = 0xE9;
    rel = (int)((uintptr_t)page - ((uintptr_t)site + 5));
    memcpy(jump + 1, &rel, 4);
    if (!VirtualProtect(site, 5, PAGE_EXECUTE_READWRITE, &old)) {
        VirtualFree(page, 0, MEM_RELEASE);
        return 0;
    }
    memcpy(site, jump, 5);
    VirtualProtect(site, 5, old, &old);
    FlushInstructionCache(GetCurrentProcess(), site, 5);
    return 1;
}

/* ---- What this load found, and what the quit owes ------------------------ */

static struct {
    int slot;                     /* the load being followed (0: none yet) */
    DWORD seen;                   /* when this load's village was first on screen */
    DWORD last;                   /* the last call */
    DWORD next_try;
    int examined;                 /* this load has been examined (or let go) */
    int retries;
    /* What the last scan found. */
    int parents_found;            /* the parentage scan said 1 */
    int counts[6];
    int recorded;                 /* A New Home: Birth records to write afterwards from the parentage file */
    int graves;                   /* graves missing from the Deaths log, when > 0 */
    int arrivals;                 /* villagers with no Birth or Arrived record, when > 0 */
    int births;                   /* villagers born here with no Birth record, when > 0 */
    int stats;                    /* changes to the Elders and Statistics files, when > 0 */
    int masks;                    /* orphan mask entries, when > 0 */
    char stats_text[1536];        /* their lines, from the statistics companion */
    /* What the quit owes the village loaded last: its slot, and whether it
       is approved (Repair Saves & Logs) or was examined with the setting on, so the
       quit looks again from the state just saved (Codex, #542: something
       that goes wrong later in the session -- a record write that failed on
       a locked log -- must still be asked about, though the load found
       nothing). */
    int quit_slot;
    int quit_approved;
    int quit_found;
    /* The prompt. */
    volatile LONG answer;         /* 0 until answered; IDYES or IDNO */
    UINT box_type;
    const char *yes_label;        /* the Yes button's words; NULL: "Repair" */
    char text[4096];
    /* Living villagers with no last name in a village that uses last names
       (the missing last names below): the last scan's, at most
       VVFP_XC_NO_LAST_MAX of them. */
    int no_last;
    int no_last_looks[VVFP_XC_NO_LAST_MAX][2];
    char no_last_name[VVFP_XC_NO_LAST_MAX][VVFP_XC_NAME_BYTES];
} vvfp_xc;

static HHOOK vvfp_xc_cbt_hook;

/* The slot's approval file (Repair Saves & Logs), as a path; 0 when the save folder
   cannot be told. */
static int vvfp_xc_approval_path(int game, int slot, wchar_t *path) {
    wchar_t folder[MAX_PATH];
    if (!VVFP_XC_SAVE_FOLDER(folder)) {
        return 0;
    }
    if (lstrlenW(folder) + 120 > MAX_PATH) {
        return 0;
    }
    /* "Log Checks" -- "Cross-Check" in older builds, used where it is, never moved (save_layout.h).
       An approval under BOTH names is acted on under neither: which one the player meant cannot be
       told, so nothing is repaired without asking and neither file is touched. */
    {
        wchar_t old_path[MAX_PATH];
        int in_new, in_old;
        wsprintfW(path, L"%ls\\Virtual Villagers Fun Patcher Data\\Log Checks\\Virtual Villagers %d Repair Approved - Save %d.dat",
                  folder, game, slot);
        wsprintfW(old_path, L"%ls\\Virtual Villagers Fun Patcher Data\\Cross-Check\\Virtual Villagers %d Repair Approved - Save %d.dat",
                  folder, game, slot);
        in_new = vv_layout_probe_w(path, NULL) != VV_LAYOUT_ABSENT;
        in_old = vv_layout_probe_w(old_path, NULL) != VV_LAYOUT_ABSENT;
        if (in_new && in_old) {
            return 0;
        }
        if (in_old) {
            lstrcpyW(path, old_path);
        }
    }
    return 1;
}

/* Whether the player approved repairing this slot's village (Repair Saves & Logs):
   the file is there and says exactly this game and slot. */
static int vvfp_xc_approved(int game, int slot) {
    wchar_t path[MAX_PATH];
    unsigned int body[4];
    DWORD got = 0;
    HANDLE f;
    int ok;
    if (!vvfp_xc_approval_path(game, slot, path)) {
        return 0;
    }
    f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = GetFileSize(f, NULL) == sizeof(body) && ReadFile(f, body, sizeof(body), &got, NULL) && got == sizeof(body)
         && body[0] == VVFP_XC_APPROVAL_MAGIC && body[1] == VVFP_XC_APPROVAL_VERSION
         && body[2] == (unsigned int)game && body[3] == (unsigned int)slot;
    CloseHandle(f);
    return ok;
}

/* The approval is used up. */
static void vvfp_xc_consume_approval(int game, int slot) {
    wchar_t path[MAX_PATH];
    if (vvfp_xc_approval_path(game, slot, path)) {
        DeleteFileW(path);
    }
}

/* Whether the last scan found anything (in the parts that could tell). */
static int vvfp_xc_any(void) {
    return vvfp_xc.parents_found || vvfp_xc.graves > 0 || vvfp_xc.arrivals > 0 || vvfp_xc.births > 0
           || vvfp_xc.stats > 0 || vvfp_xc.masks > 0;
}

/* Scan every part, reading only.  -1 when one of them cannot tell yet (the
   others' findings are still in the fields), 0 nothing found, 1 something
   found (the fields say what). */
static int vvfp_xc_scan(int game, int slot) {
    vvfp_xc_scan_parents_fn scan_parents;
    vvfp_xc_scan_graves_fn scan_graves, scan_arrivals, scan_births;
    vvfp_xc_scan_text_fn scan_stats;
    int parents = 0, graves, arrivals, births, stats, masks;
    memset(vvfp_xc.counts, 0, sizeof(vvfp_xc.counts));
    vvfp_xc.recorded = 0;
    if (game == 1) {
        scan_parents = (vvfp_xc_scan_parents_fn)VVFP_XC_PROC(VVFP_XC_PARENTAGE_DLL, "Vv1ParentageCrossCheckScan");
        parents = scan_parents != NULL ? scan_parents(vvfp_xc.counts) : 0;
        {
            /* Optional: a companion that predates it never writes one. */
            vvfp_xc_count_fn recorded = (vvfp_xc_count_fn)VVFP_XC_PROC(VVFP_XC_PARENTAGE_DLL,
                                                                       "Vv1ParentageCrossCheckRecorded");
            vvfp_xc.recorded = parents == 1 && recorded != NULL ? recorded() : 0;
        }
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
    vvfp_xc.parents_found = parents == 1;
    vvfp_xc.graves = graves > 0 ? graves : 0;
    vvfp_xc.arrivals = arrivals > 0 ? arrivals : 0;
    vvfp_xc.births = births > 0 ? births : 0;
    vvfp_xc.stats = stats > 0 && vvfp_xc.stats_text[0] != '\0' ? stats : 0;
    masks = vvfp_xc_masks_scan(game, slot);
    vvfp_xc.masks = masks > 0 ? masks : 0;
    if (parents < 0 || graves < 0 || arrivals < 0 || births < 0 || stats < 0 || masks < 0) {
        return -1;
    }
    return vvfp_xc_any();
}

/* Approved at load: A New Home's parents now (nothing is shown; a failure
   is retried at the quit), and every other part found at the village's
   next save, by the companion that owns it -- as an answered Repair always
   was.  Nothing found: nothing to pass on. */
static void vvfp_xc_repair_at_save(int game, int slot) {
    vvfp_xc_repair_graves_fn repair;
    if (vvfp_xc.parents_found) {
        vvfp_xc_apply_parents_fn apply =
            (vvfp_xc_apply_parents_fn)VVFP_XC_PROC(VVFP_XC_PARENTAGE_DLL, "Vv1ParentageCrossCheckApply");
        if (apply != NULL) {
            (void)apply();
        }
    }
    if (vvfp_xc.graves > 0
        && (repair = (vvfp_xc_repair_graves_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseRepairGraves")) != NULL) {
        repair(game, slot, 1);
    }
    if (vvfp_xc.arrivals > 0
        && (repair = (vvfp_xc_repair_graves_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseRepairArrivals")) != NULL) {
        repair(game, slot, 1);
    }
    if (vvfp_xc.births > 0
        && (repair = (vvfp_xc_repair_graves_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseRepairBirths")) != NULL) {
        repair(game, slot, 1);
    }
    if (vvfp_xc.stats > 0
        && (repair = (vvfp_xc_repair_graves_fn)VVFP_XC_LOAD(VVFP_XC_STATS_DLL, "VvfpStatisticsRepairReconcile")) != NULL) {
        repair(game, slot, 1);
    }
    if (vvfp_xc.masks > 0) {
        (void)vvfp_xc_masks_repair(game, slot);   /* the masks now; one left undone is found at the quit */
    }
}

/* At the quit, after the quit save: every part the scan just found,
   repaired now from the state that save wrote.  1 when every part says it
   is done; 0 when one could not be (it is found again next time). */
static int vvfp_xc_repair_now(int game, int slot) {
    vvfp_xc_now_fn now;
    int ok = 1;
    if (vvfp_xc.parents_found) {
        vvfp_xc_apply_parents_fn apply =
            (vvfp_xc_apply_parents_fn)VVFP_XC_PROC(VVFP_XC_PARENTAGE_DLL, "Vv1ParentageCrossCheckApply");
        ok &= apply != NULL && apply() != 0;
    }
    if (vvfp_xc.graves > 0) {
        now = (vvfp_xc_now_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseRepairGravesNow");
        ok &= now != NULL && now(game, slot) != 0;
    }
    if (vvfp_xc.arrivals > 0) {
        now = (vvfp_xc_now_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseRepairArrivalsNow");
        ok &= now != NULL && now(game, slot) != 0;
    }
    if (vvfp_xc.births > 0) {
        now = (vvfp_xc_now_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseRepairBirthsNow");
        ok &= now != NULL && now(game, slot) != 0;
    }
    if (vvfp_xc.stats > 0) {
        now = (vvfp_xc_now_fn)VVFP_XC_LOAD(VVFP_XC_STATS_DLL, "VvfpStatisticsRepairReconcileNow");
        ok &= now != NULL && now(game, slot) != 0;
    }
    if (vvfp_xc.masks > 0) {
        ok &= vvfp_xc_masks_repair(game, slot) != 0;
    }
    return ok;
}

/* ---- The quit prompt ----------------------------------------------------- */

/* As the prompt opens: relabel a Yes/No box's two buttons, and make sure the
   box is SEEN.  The game minimises its own window for it, and the box comes
   from a thread of its own, which Windows' foreground lock may refuse to
   bring forward -- a box left behind other windows, with the game's window
   in the taskbar, is a game that seems to hang windowless at the quit (live,
   v1.35.66, A New Home: the process stayed up with no window for over 40 s
   after the quit save).  So the box is put on top, shown, brought forward
   and flashed in the taskbar. */
static LRESULT CALLBACK vvfp_xc_cbt(int code, WPARAM wparam, LPARAM lparam) {
    if (code == HCBT_ACTIVATE) {
        HWND box = (HWND)wparam;
        FLASHWINFO flash;
        if ((vvfp_xc.box_type & 0xFu) == MB_YESNO) {
            SetDlgItemTextA(box, IDYES, vvfp_xc.yes_label != NULL ? vvfp_xc.yes_label : "Repair");
            SetDlgItemTextA(box, IDNO, "Not now");
        }
        SetWindowPos(box, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
        SetForegroundWindow(box);
        memset(&flash, 0, sizeof flash);
        flash.cbSize = sizeof flash;
        flash.hwnd = box;
        flash.dwFlags = FLASHW_ALL | FLASHW_TIMERNOFG;
        FlashWindowEx(&flash);
    }
    return CallNextHookEx(vvfp_xc_cbt_hook, code, wparam, lparam);
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

static DWORD WINAPI vvfp_xc_box(LPVOID unused) {
    int answer;
    (void)unused;
    vvfp_xc_cbt_hook = SetWindowsHookExA(WH_CBT, vvfp_xc_cbt, NULL, GetCurrentThreadId());
    answer = MessageBoxA(NULL, vvfp_xc.text, "Virtual Villagers Fun Patcher",
                         vvfp_xc.box_type | MB_TOPMOST | MB_SETFOREGROUND);
    if (vvfp_xc_cbt_hook != NULL) {
        UnhookWindowsHookEx(vvfp_xc_cbt_hook);
        vvfp_xc_cbt_hook = NULL;
    }
    /* -1: the box could not be shown (no answer, as one let go). */
    InterlockedExchange(&vvfp_xc.answer, answer == IDYES ? IDYES : answer == 0 ? -1 : IDNO);
    return 0;
}

/* Show vvfp_xc.text in a box of `type` and wait for the answer: IDYES or
   IDNO; 0 when it was not answered in time (or its thread could not start),
   -1 when the box could not be shown.  Only
   messages SENT to this thread are taken while waiting. */
static int vvfp_xc_ask(UINT type) {
    HANDLE thread;
    DWORD start = GetTickCount();
    HWND game_window = NULL;
    vvfp_xc.answer = 0;
    vvfp_xc.box_type = type;
    EnumWindows(vvfp_xc_find_window, (LPARAM)&game_window);
    /* The game's thread is the foreground one now: let the box's thread take
       the foreground from it (see vvfp_xc_cbt). */
    AllowSetForegroundWindow(ASFW_ANY);
    if (game_window != NULL && GetWindowThreadProcessId(game_window, NULL) == GetCurrentThreadId()) {
        ShowWindow(game_window, SW_MINIMIZE);   /* out of full screen: the box is not hidden behind it */
    }
    thread = CreateThread(NULL, 0, vvfp_xc_box, NULL, 0, NULL);
    if (thread == NULL) {
        return 0;
    }
    for (;;) {
        DWORD waited = GetTickCount() - start;
        DWORD r;
        MSG msg;
        if (waited >= VVFP_XC_QUIT_WAIT_MS) {
            break;
        }
        r = MsgWaitForMultipleObjects(1, &thread, FALSE, VVFP_XC_QUIT_WAIT_MS - waited, QS_SENDMESSAGE);
        if (r == WAIT_OBJECT_0 + 1) {
            PeekMessageA(&msg, NULL, 0, 0, PM_NOREMOVE | PM_QS_SENDMESSAGE);   /* delivers sent messages only */
            continue;
        }
        break;
    }
    CloseHandle(thread);
    return (int)vvfp_xc.answer;
}

static void vvfp_xc_add(const char *format, int count, const char *one, const char *many) {
    size_t len = (size_t)lstrlenA(vvfp_xc.text);
    if (count > 0 && len + 400 < sizeof(vvfp_xc.text)) {
        wsprintfA(vvfp_xc.text + len, format, count, count == 1 ? one : many);
    }
}

/* How the player turns the checks off: the setting is written into the game
   when it is patched (the owner, 2026-10-05: "With a message in the prompt
   on how to turn the toggle off"). */
#define VVFP_XC_HOW_TO_STOP \
    "To stop these checks, untick 'Check logs automatically' in the Virtual Villagers Fun Patcher " \
    "and patch the game again."
#define VVFP_XC_STATS_NOTE \
    "  (The Village Elders and Village Statistics files are backed up first; every change " \
    "is listed in the Repairs log.)\r\n"
#define VVFP_XC_MASKS_NOTE \
    "  (The Village Masks file is backed up first; every removal is listed in the Repairs log.)\r\n"
#define VVFP_XC_CLOSING \
    "\r\nThe game has already been saved. Repair them now?\r\n\r\n\"Not now\" changes " \
    "nothing; you will be asked again the next time you close the game after playing this " \
    "village.\r\n\r\n" VVFP_XC_HOW_TO_STOP

static void vvfp_xc_compose(void) {
    const int *c = vvfp_xc.counts;
    lstrcpyA(vvfp_xc.text, "Before the game closes: the Fun Patcher checked the records of the village you just "
                           "played against its save and its logs, and found some it can put right:\r\n\r\n");
    if (vvfp_xc.parents_found) {
        vvfp_xc_add("- %d %s the wrong parents recorded. They will be corrected from the Births log.\r\n",
                    c[0], "villager has", "villagers have");
        vvfp_xc_add("- %d %s parents recorded but no Birth record in the Births log (founders or grown "
                    "arrivals). They will be set to unknown.\r\n", c[1], "villager has", "villagers have");
        vvfp_xc_add("- %d %s parents the Births log cannot tell apart. They will be set to unknown.\r\n",
                    c[2], "villager has", "villagers have");
        vvfp_xc_add("- %d %s parents recorded but no Birth or Arrived record in the Births log (born before "
                    "that record existed). Their Birth records will be added from the parentage file.\r\n",
                    vvfp_xc.recorded, "villager has", "villagers have");
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
                    "will be added.\r\n", vvfp_xc.graves, "grave has", "graves have");
    }
    if (vvfp_xc.arrivals > 0) {
        vvfp_xc_add("- %d %s no Birth or Arrived record in the Births log (arrived before that record existed). "
                    "Their Arrived records will be added.\r\n", vvfp_xc.arrivals, "villager has", "villagers have");
    }
    if (vvfp_xc.births > 0) {
        vvfp_xc_add("- %d %s born in the village but no Birth record in the Births log (born before that record "
                    "existed). Their Birth records will be added from the save.\r\n",
                    vvfp_xc.births, "villager was", "villagers were");
    }
    /* sizeof counts each terminator: room for the stats lines, their note,
       the closing text and one terminator, with a byte to spare. */
    if (vvfp_xc.stats > 0 && (size_t)lstrlenA(vvfp_xc.text) + (size_t)lstrlenA(vvfp_xc.stats_text)
                                 + sizeof(VVFP_XC_STATS_NOTE) + sizeof(VVFP_XC_CLOSING) < sizeof(vvfp_xc.text)) {
        lstrcatA(vvfp_xc.text, vvfp_xc.stats_text);
        lstrcatA(vvfp_xc.text, VVFP_XC_STATS_NOTE);
    }
    if (vvfp_xc.masks > 0) {
        size_t len = (size_t)lstrlenA(vvfp_xc.text);
        if (len + 200 + sizeof(VVFP_XC_MASKS_NOTE) + sizeof(VVFP_XC_CLOSING) < sizeof(vvfp_xc.text)) {
            vv_om_describe(vvfp_xc.masks, vvfp_xc.text + len, sizeof(vvfp_xc.text) - len);
            lstrcatA(vvfp_xc.text, VVFP_XC_MASKS_NOTE);
        }
    }
    lstrcatA(vvfp_xc.text, VVFP_XC_CLOSING);
}

/* ---- Missing last names --------------------------------------------------

   The owner (v1.35.66): "if repair logs detects a missing last name, please
   prompt the player to add one if auto check is enabled" -- "like for
   arrivals and stuff. and direct them how to add last names".  With "Check
   logs automatically" on, a village that uses last names (this build ships
   the Villagers Have Last Names row, or the slot has a Last Names record) is
   looked at right after the quit save: every living villager of the village
   (VVFP Cause of Death.dll's VvfpCauseVillager: never a body, a statue, a
   ghost, a stand-in or a Heathen) whose name carries no last name, read as
   src/vv_last_names.py split_name reads it -- the words after the first, less
   a numeral ("Soda II"), and never a name the player said is one first name
   (the record's "whole" lines).  Last names can only be given with the game
   closed (the patcher writes the save and every log), so the box only
   queues the request and says how to give them:

     Remind me: the slot's request file says "remind" -- the patcher asks the
                next time it opens (src/vv_fun_patcher_gui.py), with those
                villagers' boxes highlighted and a last name suggested;
     Not now:   it says "not now" -- neither the game nor the patcher asks
                again while every villager with no last name is one it lists.

   No answer (the box not shown, or let go) writes nothing.  The request file
   (src/vv_last_names.py MISSING_HEADER), written through a temporary file:

     <save folder>\Virtual Villagers Fun Patcher Data\Last Names\
         Virtual Villagers N Missing Last Names - Save S.dat
     VVFP MISSING LAST NAMES v1 game=N
     asked<TAB>remind | not now
     villager<TAB>name<TAB>head<TAB>body          (the game's own Latin-1)

   A request that already lists every villager found asks nothing more. */

typedef int (__stdcall *vvfp_xc_villager_fn)(int game, int index, char *name, int cap, int *looks);

static char vvfp_xc_ln_record[VVFP_XC_LN_FILE_MAX + 1];
static char vvfp_xc_ln_request[VVFP_XC_LN_FILE_MAX + 1];

/* The slot's Last Names file: `request` 0 the record, 1 the request. */
static int vvfp_xc_ln_path(int game, int slot, int request, wchar_t *path) {
    wchar_t folder[MAX_PATH];
    if (!VVFP_XC_SAVE_FOLDER(folder) || lstrlenW(folder) + 120 > MAX_PATH) {
        return 0;
    }
    wsprintfW(path, request
              ? L"%ls\\Virtual Villagers Fun Patcher Data\\Last Names\\Virtual Villagers %d Missing Last Names - Save %d.dat"
              : L"%ls\\Virtual Villagers Fun Patcher Data\\Last Names\\Virtual Villagers %d Last Names - Save %d.dat",
              folder, game, slot);
    return 1;
}

/* A small text file whose first line is `header`, into buf (terminated); 0
   when it is not there, cannot be read, is larger than the buffer or is
   another file. */
static int vvfp_xc_ln_read(const wchar_t *path, const char *header, char *buf) {
    HANDLE f;
    DWORD size, got = 0;
    size_t n = (size_t)lstrlenA(header);
    buf[0] = '\0';
    f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        return 0;
    }
    size = GetFileSize(f, NULL);
    if (size == INVALID_FILE_SIZE || size > VVFP_XC_LN_FILE_MAX || !ReadFile(f, buf, size, &got, NULL) || got != size) {
        CloseHandle(f);
        buf[0] = '\0';
        return 0;
    }
    CloseHandle(f);
    buf[got] = '\0';
    if (strncmp(buf, header, n) != 0 || (buf[n] != '\r' && buf[n] != '\n')) {
        buf[0] = '\0';
        return 0;
    }
    return 1;
}

/* The next line of `text` after `line`, or NULL. */
static const char *vvfp_xc_ln_next(const char *line) {
    const char *end = strchr(line, '\n');
    return end != NULL && end[1] != '\0' ? end + 1 : NULL;
}

/* Whether `field` (up to tab, CR or LF; UTF-8 in the record) is the n
   Latin-1 bytes at `text`. */
static int vvfp_xc_ln_same(const char *field, const char *text, size_t n, int utf8) {
    size_t k = 0;
    while (*field != '\0' && *field != '\t' && *field != '\r' && *field != '\n') {
        unsigned char c = (unsigned char)*field++;
        if (utf8 && (c == 0xC2 || c == 0xC3) && ((unsigned char)*field & 0xC0u) == 0x80u) {
            c = (unsigned char)(((c & 0x03u) << 6) | ((unsigned char)*field++ & 0x3Fu));
        }
        if (k >= n || (unsigned char)text[k] != c) {
            return 0;
        }
        ++k;
    }
    return k == n;
}

static int vvfp_xc_ln_numeral(const char *word, size_t n) {
    size_t i;
    if (n == 0) {
        return 0;
    }
    for (i = 0; i < n; ++i) {
        if (strchr("IVXLCDM", word[i]) == NULL || word[i] == '\0') {
            return 0;
        }
    }
    return 1;
}

/* White space as Python's str.isspace() reads a Latin-1 name. */
static int vvfp_xc_ln_space(char ch) {
    unsigned char c = (unsigned char)ch;
    return c == ' ' || (c >= 0x09 && c <= 0x0D) || (c >= 0x1C && c <= 0x1F) || c == 0x85 || c == 0xA0;
}

/* Whether `name` carries no last name (split_name): one word, perhaps with a
   numeral after it, or words the record says are one first name. */
static int vvfp_xc_ln_missing(const char *name) {
    const char *starts[16];
    size_t lens[16];
    int count = 0, k;
    const char *p = name;
    const char *line;
    size_t base;
    /* The words as Python's str.split() makes them: runs of white space
       separate words and an empty word is never one, so a leading, trailing
       or doubled space is never taken for a last name ("Kele " has none). */
    while (count < 16) {
        size_t n = 0;
        while (*p != '\0' && vvfp_xc_ln_space(*p)) {
            ++p;
        }
        if (*p == '\0') {
            break;
        }
        while (p[n] != '\0' && !vvfp_xc_ln_space(p[n])) {
            ++n;
        }
        starts[count] = p;
        lens[count] = n;
        ++count;
        p += n;
    }
    if (count == 0) {
        return 1;
    }
    k = count - 1;
    while (k > 0 && vvfp_xc_ln_numeral(starts[k], lens[k])) {
        --k;
    }
    if (k == 0) {
        return 1;
    }
    base = (size_t)(starts[k] - name) + lens[k];
    for (line = vvfp_xc_ln_record; line != NULL && *line != '\0'; line = vvfp_xc_ln_next(line)) {
        if (strncmp(line, "whole\t", 6) == 0 && vvfp_xc_ln_same(line + 6, name, base, 1)) {
            return 1;
        }
    }
    return 0;
}

/* Whether the request file lists this villager. */
static int vvfp_xc_ln_listed(const char *name, int head, int body) {
    const char *line;
    char tail[32];
    size_t n = (size_t)lstrlenA(name);
    wsprintfA(tail, "\t%d\t%d", head, body);
    for (line = vvfp_xc_ln_request; line != NULL && *line != '\0'; line = vvfp_xc_ln_next(line)) {
        if (strncmp(line, "villager\t", 9) == 0 && vvfp_xc_ln_same(line + 9, name, n, 0)
            && strncmp(line + 9 + n, tail, (size_t)lstrlenA(tail)) == 0
            && (line[9 + n + lstrlenA(tail)] == '\r' || line[9 + n + lstrlenA(tail)] == '\n'
                || line[9 + n + lstrlenA(tail)] == '\0')) {
            return 1;
        }
    }
    return 0;
}

/* Right after the quit save: the village's living villagers with no last
   name, when the village uses last names.  How many to ask about -- 0 when
   there are none, or the request file already lists every one (asked to be
   reminded, or "Not now"). */
static int vvfp_xc_last_names_scan(int game, int slot) {
    vvfp_xc_villager_fn villager;
    wchar_t path[MAX_PATH];
    char header[48], name[VVFP_XC_NAME_BYTES];
    int looks[2], i, r, all_listed = 1, record;
    vvfp_xc.no_last = 0;
    wsprintfA(header, "VVFP LAST NAMES v1 game=%d", game);
    record = vvfp_xc_ln_path(game, slot, 0, path) && vvfp_xc_ln_read(path, header, vvfp_xc_ln_record);
    if (!record && !VVFP_XC_LAST_NAMES_SHIPPED()) {
        return 0;                     /* the village does not use last names */
    }
    villager = (vvfp_xc_villager_fn)VVFP_XC_PROC(VVFP_XC_CAUSE_DLL, "VvfpCauseVillager");
    if (villager == NULL) {
        return 0;
    }
    for (i = 0; i < 256 && vvfp_xc.no_last < VVFP_XC_NO_LAST_MAX; ++i) {
        name[0] = '\0';
        r = villager(game, i, name, (int)sizeof name, looks);
        if (r < 0) {
            break;
        }
        name[sizeof name - 1] = '\0';
        if (r == 1 && name[0] != '\0' && vvfp_xc_ln_missing(name)) {
            lstrcpynA(vvfp_xc.no_last_name[vvfp_xc.no_last], name, VVFP_XC_NAME_BYTES);
            vvfp_xc.no_last_looks[vvfp_xc.no_last][0] = looks[0];
            vvfp_xc.no_last_looks[vvfp_xc.no_last][1] = looks[1];
            ++vvfp_xc.no_last;
        }
    }
    if (vvfp_xc.no_last == 0) {
        return 0;
    }
    wsprintfA(header, "VVFP MISSING LAST NAMES v1 game=%d", game);
    if (vvfp_xc_ln_path(game, slot, 1, path) && vvfp_xc_ln_read(path, header, vvfp_xc_ln_request)) {
        for (i = 0; i < vvfp_xc.no_last && all_listed; ++i) {
            all_listed = vvfp_xc_ln_listed(vvfp_xc.no_last_name[i], vvfp_xc.no_last_looks[i][0],
                                           vvfp_xc.no_last_looks[i][1]);
        }
        if (all_listed) {
            return 0;                 /* already asked about every one of them */
        }
    }
    return vvfp_xc.no_last;
}

#define VVFP_XC_LN_HOW \
    "To give them last names: close the game, open the Virtual Villagers Fun Patcher and choose " \
    "Repair Saves & Logs... Pick this game, its save folder and this tribe, and press Repair Saves & Logs. " \
    "Tick 'Give villagers last names, in the game and the logs' and press Choose... Their boxes are " \
    "highlighted, with a last name suggested: keep it, pick another from the list or type your own, " \
    "press OK, then Repair."

static void vvfp_xc_last_names_compose(void) {
    int i;
    lstrcpyA(vvfp_xc.text, "Before the game closes: in the village you just played, ");
    wsprintfA(vvfp_xc.text + lstrlenA(vvfp_xc.text), vvfp_xc.no_last == 1 ? "%d villager has no last name:\r\n\r\n"
                                                                          : "%d villagers have no last name:\r\n\r\n",
              vvfp_xc.no_last);
    for (i = 0; i < vvfp_xc.no_last && lstrlenA(vvfp_xc.text) + 2 * VVFP_XC_NAME_BYTES + 1200 < (int)sizeof vvfp_xc.text;
         ++i) {
        lstrcatA(vvfp_xc.text, i ? ", " : "  ");
        lstrcatA(vvfp_xc.text, vvfp_xc.no_last_name[i]);
    }
    if (i < vvfp_xc.no_last) {
        wsprintfA(vvfp_xc.text + lstrlenA(vvfp_xc.text), " and %d more", vvfp_xc.no_last - i);
    }
    lstrcatA(vvfp_xc.text,
             "\r\n\r\nLast names can only be given while the game is closed. \"Remind me\": the Fun Patcher "
             "offers to give them last names the next time you open it. \"Not now\": you will not be asked "
             "about these villagers again (only when another villager has no last name).\r\n\r\n"
             VVFP_XC_LN_HOW "\r\n\r\n" VVFP_XC_HOW_TO_STOP);
}

/* The player's answer, kept in the request file: `state` "remind" or "not
   now", with every villager this scan found.  Written to a temporary file and
   swapped in; 0 when it could not be. */
static int vvfp_xc_last_names_answer(int game, int slot, const char *state) {
    wchar_t path[MAX_PATH], temporary[MAX_PATH + 8], folder[MAX_PATH];
    char line[96];
    HANDLE f;
    DWORD put;
    int i, ok;
    if (!vvfp_xc_ln_path(game, slot, 1, path) || !VVFP_XC_SAVE_FOLDER(folder)
        || lstrlenW(folder) + 60 > MAX_PATH) {
        return 0;
    }
    lstrcatW(folder, L"\\Virtual Villagers Fun Patcher Data");
    CreateDirectoryW(folder, NULL);
    lstrcatW(folder, L"\\Last Names");
    CreateDirectoryW(folder, NULL);
    wsprintfW(temporary, L"%ls.tmp", path);
    f = CreateFileW(temporary, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        return 0;
    }
    wsprintfA(line, "VVFP MISSING LAST NAMES v1 game=%d\nasked\t%s\n", game, state);
    ok = WriteFile(f, line, (DWORD)lstrlenA(line), &put, NULL) && put == (DWORD)lstrlenA(line);
    for (i = 0; ok && i < vvfp_xc.no_last; ++i) {
        wsprintfA(line, "villager\t%s\t%d\t%d\n", vvfp_xc.no_last_name[i], vvfp_xc.no_last_looks[i][0],
                  vvfp_xc.no_last_looks[i][1]);
        ok = WriteFile(f, line, (DWORD)lstrlenA(line), &put, NULL) && put == (DWORD)lstrlenA(line);
    }
    ok = ok && FlushFileBuffers(f);
    CloseHandle(f);
    if (!ok || !MoveFileExW(temporary, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(temporary);
        return 0;
    }
    return 1;
}

/* ---- At the quit --------------------------------------------------------- */

/* The game is quitting: its quit save of `slot` (0: none) has just been
   written, and nothing is freed yet. */
static void vvfp_crosscheck_quit(int game, int slot) {
    int found;
    if (slot < 1 || slot > 5 || slot != vvfp_xc.quit_slot) {
        return;                       /* not the village the load checked: nothing is owed */
    }
    if (vvfp_xc.quit_approved) {
        if (!vvfp_xc_approved(game, slot)) {
            return;                   /* removed meanwhile (Start Over): nothing approved now */
        }
        /* Whatever the village's saves have not already put right, now.  The
           approval is used up once nothing is left undone: a part that
           cannot tell, or a repair that failed, keeps it for the next time
           this village is played. */
        found = vvfp_xc_scan(game, slot);
        if (vvfp_xc_any() ? vvfp_xc_repair_now(game, slot) && found >= 0 : found == 0) {
            vvfp_xc_consume_approval(game, slot);
        }
    } else if (!vvfp_xc.quit_found) {
        return;                       /* the setting is off: the load never looked, nothing is owed */
    } else {
        (void)vvfp_xc_scan(game, slot);   /* again, from the state just saved */
        if (vvfp_xc_any()) {              /* nothing confirmed wrong now: nothing is asked */
            vvfp_xc_compose();
            vvfp_xc.yes_label = NULL;
            /* Not now, or no answer: nothing is written */
            if (vvfp_xc_ask(MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON1) == IDYES && !vvfp_xc_repair_now(game, slot)) {
                lstrcpyA(vvfp_xc.text, "Some of the records could not be repaired: a file could not be read or written. "
                                       "What could not be repaired was left as it was, and you will be asked about it "
                                       "again the next time you close the game after playing this village.");
                (void)vvfp_xc_ask(MB_OK | MB_ICONWARNING);
            }
        }
    }
    /* Villagers with no last name (the automatic check only): the request is
       queued for the patcher, which gives them with the game closed. */
    if (VVFP_XC_AUTOMATIC() && vvfp_xc_last_names_scan(game, slot) > 0) {
        int answer;
        vvfp_xc_last_names_compose();
        vvfp_xc.yes_label = "Remind me";
        answer = vvfp_xc_ask(MB_YESNO | MB_ICONINFORMATION | MB_DEFBUTTON1);
        vvfp_xc.yes_label = NULL;
        if (answer == IDYES || answer == IDNO) {
            (void)vvfp_xc_last_names_answer(game, slot, answer == IDYES ? "remind" : "not now");
        }
    }
}

/* The quit hook's handler (once: the game shuts down once): the slot the
   shutdown just saved, read from its save manager the way the shutdown read
   it.  Nothing that goes wrong here may stop the game closing: a fault is
   caught and the game goes on closing. */
static void __stdcall vvfp_xc_quit_hit(int game, const unsigned char *application) {
    __try {
        const unsigned char *manager = *(const unsigned char *const *)(application + 4);
        vvfp_crosscheck_quit(game, *(const int *)(manager + VVFP_XC_SLOT_FIELD[game]));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* Install the quit hook, once: from the companion's VvfpStartup (game
   start), and as a no-op from its per-frame path.  Only this game's own
   site, and only when it holds its stock bytes. */
static int vvfp_crosscheck_startup(int game) {
    if (vvfp_xc_hook_state != 0) {
        return vvfp_xc_hook_state == 1;
    }
    vvfp_xc_hook_state = -1;
    if (vvfp_xc_hook((unsigned char *)(uintptr_t)VVFP_XC_QUIT[game].va, VVFP_XC_QUIT[game].stock, game,
                     vvfp_xc_quit_hit)) {
        vvfp_xc_hook_state = 1;
    }
    return vvfp_xc_hook_state == 1;
}

/* ---- At each load -------------------------------------------------------- */

/* The village has settled after a load: see what the quit will owe it.
   Nothing is shown and nothing is changed here unless Repair Saves & Logs approved
   this slot. */
static void vvfp_xc_examine(int game, int slot, DWORD now) {
    int approved = vvfp_xc_approved(game, slot);
    int found;
    if (!approved && !VVFP_XC_AUTOMATIC()) {
        vvfp_xc.examined = 1;         /* the setting is off: no scan, nothing owed */
        return;
    }
    found = vvfp_xc_scan(game, slot);
    if (found < 0 && vvfp_xc.retries < VVFP_XC_RETRIES) {
        ++vvfp_xc.retries;            /* one of them cannot tell yet */
        vvfp_xc.next_try = now + VVFP_XC_RETRY_MS;
        return;
    }
    vvfp_xc.examined = 1;
    vvfp_xc.quit_slot = slot;
    vvfp_xc.quit_approved = approved;
    /* The quit looks again, whatever this scan found, and asks only if it
       then finds something. */
    (void)found;
    vvfp_xc.quit_found = 1;
    if (approved && vvfp_xc_any()) {
        vvfp_xc_repair_at_save(game, slot);
    }
}

/* From the companion's village-only per-frame path.  `on_screen` is the
   caller's own word that a village is being played right now.  It never
   shows anything. */
static void vvfp_crosscheck_bridge(int game, int on_screen) {
    DWORD now = VVFP_XC_NOW();
    const vvfp_story_host *host;
    int slot = 0;
    (void)vvfp_crosscheck_startup(game);   /* a no-op once game start has installed it */
    if (on_screen) {
        host = vvfp_story_host_table();
        slot = host != NULL && host->slot != NULL ? host->slot() : 0;
    }
    if (slot < 1 || slot > 5) {
        vvfp_xc.slot = 0;             /* no village: the next one seen is a new load */
        return;
    }
    if (slot != vvfp_xc.slot || now - vvfp_xc.last > VVFP_XC_GAP_MS) {
        /* A new load -- or, in the same slot, a while with no villager drawn
           (in The Secret City to New Believers only a drawn villager calls
           this, so the view scrolled away from every villager is one too):
           look again once it settles.  Another slot owes nothing of the last
           one's.  The same slot holds the same village (Start Over clears
           it), so what the quit owes stays until the next look replaces it:
           a quit before that look still asks what the last one found (the
           quit scans again from the state just saved). */
        if (slot != vvfp_xc.slot) {
            vvfp_xc.quit_slot = 0;
            vvfp_xc.quit_approved = vvfp_xc.quit_found = 0;
        }
        vvfp_xc.slot = slot;
        vvfp_xc.seen = now;
        vvfp_xc.examined = 0;
        vvfp_xc.retries = 0;
        vvfp_xc.next_try = now;
    }
    vvfp_xc.last = now;
    if (vvfp_xc.examined || now - vvfp_xc.seen < VVFP_XC_SETTLE_MS || (LONG)(now - vvfp_xc.next_try) < 0) {
        return;
    }
    vvfp_xc_examine(game, slot, now);
}

#endif /* VVFP_CROSSCHECK_BRIDGE_H */
