/* The Origins companions' side of "Cause of Death" (all five games).

   "VVFP Cause of Death.dll" ships only with the Cause of Death row of each
   game.  Each game's Origins companion loads it by full path from the
   executable's own directory (never by a bare name), outside DllMain, and
   asks it to install for that game, once.  The companion hands it the same
   host table it hands the Story / Cheat Upgrades companion (story_bridge.h),
   which carries the save slot A New Home and The Lost Children key their
   graves file by.  After that, every call is the companion's per-frame tick
   (VvfpCauseTick), which keeps that file and notices deaths no hooked site
   reported.  Not shipped (the row is off): nothing is loaded and the stock
   game runs.

   Included once per companion, after story_bridge.h; everything is
   file-static. */
#ifndef VVFP_CAUSE_BRIDGE_H
#define VVFP_CAUSE_BRIDGE_H

#include <windows.h>
#include <string.h>

#define VVFP_CAUSE_DLL "VVFP Cause of Death.dll"

typedef int (__stdcall *vvfp_cause_install_fn)(int game, const void *host);
typedef void (__stdcall *vvfp_cause_tick_fn)(int game);

static int vvfp_cause_state;     /* 0 = not tried, 1 = installed, -1 = unavailable */
static vvfp_cause_tick_fn vvfp_cause_tick;

/* Load and install for `game`, once; then the tick, on every call.  Called
   from every place the companion calls vvfp_story_bridge, so it is in place
   before the first catch-up and runs on the per-frame path. */
static void vvfp_cause_bridge(int game) {
    char path[MAX_PATH];
    char *slash;
    DWORD n;
    HMODULE module;
    vvfp_cause_install_fn install;
    if (vvfp_cause_state == 1) {
        vvfp_cause_tick(game);
        return;
    }
    if (vvfp_cause_state != 0) {
        return;
    }
    vvfp_cause_state = -1;
    n = GetModuleFileNameA(NULL, path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return;
    }
    slash = strrchr(path, '\\');
    if (slash == NULL || (size_t)(slash + 1 - path) + sizeof(VVFP_CAUSE_DLL) > sizeof(path)) {
        return;
    }
    lstrcpyA(slash + 1, VVFP_CAUSE_DLL);
    module = LoadLibraryA(path);
    if (module == NULL) {
        return;                       /* not shipped: the row is off */
    }
    install = (vvfp_cause_install_fn)GetProcAddress(module, "VvfpCauseInstall");
    vvfp_cause_tick = (vvfp_cause_tick_fn)GetProcAddress(module, "VvfpCauseTick");
    if (install != NULL && vvfp_cause_tick != NULL && install(game, vvfp_story_host_table())) {
        vvfp_cause_state = 1;
        vvfp_cause_tick(game);
    }
}

#endif /* VVFP_CAUSE_BRIDGE_H */
