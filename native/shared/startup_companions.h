/* The companions "VVFP Startup.dll" may start, and which of them THIS build
   ships.

   The patcher's startup stub passes VvfpStartup(game, shipped): one bit per
   companion DLL the build ships -- bit 0 the game's Origins companion, then
   bit 1 + i for VVFP_STARTUP_COMPANIONS[i].  The bit order is a contract with
   the patcher (STARTUP_LOADER_COMPANIONS in src/vv_fun_patcher.py, pinned by
   tests/test_startup_loader.py): APPEND ONLY -- never reorder, rename or
   remove an entry, or a build's bits name the wrong DLLs.

   The Origins companions keep the bits their own VvfpStartup is handed
   (vvfp_startup_note_shipped) and every install bridge asks
   vvfp_startup_ships(name) before loading a companion, so a patcher DLL
   left in the folder by another build is never loaded by them either.  When
   VvfpStartup never ran (the loader's file is missing) nothing is known and
   every bridge loads what it finds, as before the loader existed.

   Included by native/vvfp_startup/vvfp_startup.c and, through
   story_bridge.h, by every Origins companion; everything is file-static. */
#ifndef VVFP_STARTUP_COMPANIONS_H
#define VVFP_STARTUP_COMPANIONS_H

#include <windows.h>

static const char *const VVFP_STARTUP_COMPANIONS[] = {
    "VVFP Parentage Export.dll",
    "VVFP Statistics Export.dll",
    "VVFP Population Export.dll",
    "VVFP Save Reset.dll",
    "VVFP Fix Huts.dll",
    "VVFP Work First.dll",
    "VVFP Lesson Cap.dll",
    "VVFP Healers Study.dll",
    "VVFP Improved Pathfinding.dll",
    "VVFP Story Upgrades.dll",
    "VVFP Cause of Death.dll",
    "VVFP VV1 Parentage.dll",
    "VVFP VV1 Number Keys.dll",
    "VVFP VV1 Sort By.dll",
    "VVFP VV1 Watering Builds.dll",
    "VVFP Golden Mushroom.dll",
    /* APPEND ONLY (see above). */
};
#define VVFP_STARTUP_COMPANION_COUNT \
    (sizeof VVFP_STARTUP_COMPANIONS / sizeof VVFP_STARTUP_COMPANIONS[0])

static unsigned int vvfp_startup_shipped;
static int vvfp_startup_known;

static void vvfp_startup_note_shipped(unsigned int shipped) {
    vvfp_startup_shipped = shipped;
    vvfp_startup_known = 1;
}

/* Whether companion `name` may be loaded: its bit is set, or nothing is
   known (no VvfpStartup ran).  A name that is not in the list is never
   in a build the loader started. */
static int vvfp_startup_ships(const char *name) {
    size_t i;
    if (!vvfp_startup_known) {
        return 1;
    }
    for (i = 0; i < VVFP_STARTUP_COMPANION_COUNT; ++i) {
        if (lstrcmpiA(VVFP_STARTUP_COMPANIONS[i], name) == 0) {
            return (vvfp_startup_shipped & (1u << (i + 1))) != 0;
        }
    }
    return 0;
}

/* One install at game start, on its own: a companion that faults inside its
   install is abandoned (structured exception handling) and the next install
   still runs, so one faulting add-on never leaves the others unarmed
   (Codex, #537).  Every call in an Origins companion's VvfpStartup goes
   through this. */
#define VVFP_STARTUP_GUARDED(call)     __try { (void)(call); } __except (EXCEPTION_EXECUTE_HANDLER) { }

#endif /* VVFP_STARTUP_COMPANIONS_H */
