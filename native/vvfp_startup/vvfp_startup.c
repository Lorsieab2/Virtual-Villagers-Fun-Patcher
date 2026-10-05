/* VVFP Startup -- every patcher companion loaded and armed at game start.

   WHY.  The Virtual Villagers games catch up the time that passed while
   they were closed when a village is loaded (and again after a Time Warp):
   births, deaths, burials, disappearances and island events happen in one
   batch before the village is first drawn.  The patcher's runtime
   companions used to be installed from the Origins companion's per-frame
   or per-draw paths -- in The Secret City only when a villager was first
   drawn -- so a recording hook could arm AFTER that catch-up and miss its
   events, which the logs then recovered later without their details.  The
   owner's rule: every patcher add-on starts as soon as the game is opened.

   HOW.  The patcher appends one small section to every executable it ships
   with a companion DLL (src/vv_fun_patcher.py, _apply_startup_loader).  Its
   stub replaces the C runtime's `call WinMain`: it loads this DLL by its
   full path in the executable's own folder, calls VvfpStartup(game), and
   then enters WinMain exactly as before.  That is the first point that is
   both the game's own thread and outside the loader lock (DllMain is never
   used), and it precedes the window, the title screen, the slot menu and
   every load.

   WHAT.  VvfpStartup loads this game's companions by full path from the
   same folder -- the Origins companion first, whose own VvfpStartup loads
   and installs the runtime companions with its host table (Cause of Death,
   Story / Cheat Upgrades, Builders Fix Huts When Idle and Work First, the
   lesson caps, Healers Study, Improved Pathfinding, Watering Builds), then
   every other companion, each of which is loaded whether or not the others
   are present.  A companion that exports VvfpStartup(game) is asked to arm
   itself; the Golden Mushroom companion is asked to install through its
   per-game ordinal, exactly as the executable's own image-load stub asks
   later (a no-op then).  Nothing here, and nothing a VvfpStartup does,
   reads or writes the game's data or calls a game routine: at this point
   the game has initialised nothing.  Parts that need a village (ticks,
   drawing, prompts) stay on their own per-frame or per-event entries.

   ONLY THIS BUILD'S COMPANIONS.  The stub passes, beside the game number,
   a bit for each companion this build ships (bit 0 the Origins companion,
   bit 1 + i COMPANIONS[i], GOLDEN_MUSHROOM_BIT the Golden Mushroom), which
   the patcher writes from the selection (STARTUP_LOADER_COMPANIONS in
   src/vv_fun_patcher.py, in this order).  A patcher DLL that is in the
   folder but not in this build -- left over from another build, or copied
   along with the game folder -- is never loaded.

   FAIL-SAFE.  A companion that is not shipped is skipped; one that fails
   to load, or lacks an export, is skipped and the rest still load; and
   whatever happens here, the stub then runs the game's own WinMain. */
#include <windows.h>
#include <string.h>

#define VVFP_STARTUP_GAMES 5

/* Each game's Origins companion, loaded first (see above). */
static const char *const ORIGINS[VVFP_STARTUP_GAMES + 1] = {
    NULL,
    "VVFP VV1 Origins Icons.dll",
    "VVFP VV2 Origins Icons.dll",
    "VVFP Origins Icons.dll",
    "VVFP VV4 Origins Icons.dll",
    "VVFP Origins Icons.dll",
};

/* Every other companion the patcher ships, in any game (and
   GOLDEN_MUSHROOM below), in the order of their bits.
   tests/test_startup_loader.py requires every companion DLL of the catalog
   to be named here, in ORIGINS or as GOLDEN_MUSHROOM, and this order to be
   the patcher's. */
static const char *const COMPANIONS[] = {
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
};

/* The Golden Mushroom companion installs through the export whose ordinal
   is the game number (no export for The Lost Children). */
static const char GOLDEN_MUSHROOM[] = "VVFP Golden Mushroom.dll";
#define GOLDEN_MUSHROOM_BIT (1 + sizeof COMPANIONS / sizeof COMPANIONS[0])

typedef void (__stdcall *vvfp_startup_fn)(int game);
typedef int (__stdcall *vvfp_golden_install_fn)(void);

/* Load `name` from the executable's own folder; NULL when it is not there
   or does not load.  Never a bare name: the search order is never used. */
static HMODULE load_beside_executable(const char *name) {
    char path[MAX_PATH];
    char *slash;
    DWORD n;
    size_t length = strlen(name);
    n = GetModuleFileNameA(NULL, path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return NULL;
    }
    slash = strrchr(path, '\\');
    if (slash == NULL || (size_t)(slash + 1 - path) + length + 1 > sizeof(path)) {
        return NULL;
    }
    memcpy(slash + 1, name, length + 1);
    return LoadLibraryA(path);        /* NULL when not shipped: that row is off */
}

/* Load `name`; ask it to arm itself when it exports VvfpStartup. */
static void start(int game, const char *name) {
    HMODULE module = load_beside_executable(name);
    vvfp_startup_fn startup;
    if (module == NULL) {
        return;
    }
    startup = (vvfp_startup_fn)GetProcAddress(module, "VvfpStartup");
    if (startup != NULL) {
        startup(game);
    }
}

/* Called once, by the executable's startup stub before WinMain, with the
   executable's own game number (1-5) and this build's companion bits. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    HMODULE golden;
    vvfp_golden_install_fn install;
    size_t i;
    if (shipped & 1u) {
        start(game, ORIGINS[game]);
    }
    for (i = 0; i < sizeof COMPANIONS / sizeof COMPANIONS[0]; ++i) {
        if (shipped & (1u << (i + 1))) {
            start(game, COMPANIONS[i]);
        }
    }
    if (shipped & (1u << GOLDEN_MUSHROOM_BIT)) {
        golden = load_beside_executable(GOLDEN_MUSHROOM);
        install = golden != NULL
            ? (vvfp_golden_install_fn)GetProcAddress(golden, MAKEINTRESOURCEA(game))
            : NULL;
        if (install != NULL) {
            (void)install();
        }
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
