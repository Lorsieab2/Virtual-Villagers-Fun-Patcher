/* VVFP No Safeguards -- the game's own island events under "No Safeguards for Island Events (and Additional Events
   too)" (island_events_any_time, all five games; the owner, 2026-11-15).

   WHAT.  With that patch installed, each game's own natural island events ignore their conditions except what an
   event needs to happen or make sense: a villager or kind of villager it casts (a child for a child's event, a
   pregnant villager, a woman and a man, a healer, the Tribal Chief...), a puzzle or puzzle state it is tied to, and
   at least one grave for a Day of Honor.  Technology, building, population, food, tech-point and illness
   conditions, "not the chief" and "not pregnant / not sick" protections, minimum head-counts and the room checks
   are lifted.  KEPT FOR SAFETY: the villager table's real size (a villager is never made past it: the game's own
   creators answer -1 when it is full, and the patcher's record guards stay), and each game's other kept items in
   its table's comment.  ALWAYS PROTECTED: records that are not living villagers (The Lost Children's totems, the
   dead, bodies, ghosts and spirits): every event's casting scan still needs a living villager, and no site here
   touches those scans.  NOT CHANGED: the timer and the delays (More Frequent Island Events changes those), which
   event is chosen among the ones that pass (the family weights and case rolls), the rescue rule and the first-event
   rules.  Each game's lifted and kept conditions, event by event, are in ns_vvN.inc.

   HOW.  Every site is a byte replacement at the condition's branch (ns_site.h), written at start (VvfpStartup, before
   WinMain) only after every one of the game's sites holds its stock bytes (native/shared/install_sites.h: all of
   them, or none), and only when the patcher's installed-patches list ("VVFP Installed Patches.txt", in the patcher's
   folder) names vvN_island_events_any_time.  The patcher ships this DLL only with that row.

   SAFETY.  Nothing is written to a save, a villager record or a file; no text is shown.  The list is only read.
   No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"
#include "ns_site.h"
#include "ns_vv1.inc"
#include "ns_vv2.inc"
#include "ns_vv3.inc"
#include "ns_vv4.inc"
#include "ns_vv5.inc"

#define NS_INSTALLED_LEAF "VVFP Installed Patches.txt"
#define NS_INSTALLED_BYTES 16384
#define NS_ROW "island_events_any_time"
#define NS_MAX_SITES 64

typedef struct {
    int game;
    const ns_site *sites;
    int count;
} ns_game;

static const ns_game NS_GAMES[] = {
    { 1, NS_VV1_SITES, (int)NS_VV1_COUNT },
    { 2, NS_VV2_SITES, (int)NS_VV2_COUNT },
    { 3, NS_VV3_SITES, (int)NS_VV3_COUNT },
    { 4, NS_VV4_SITES, (int)NS_VV4_COUNT },
    { 5, NS_VV5_SITES, (int)NS_VV5_COUNT },
};

static int g_installed;
static int g_count;
static char g_list[NS_INSTALLED_BYTES];

/* 1 when the installed-patches list has the line "vv<game>_island_events_any_time". */
static int row_installed(int game) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    char want[40];
    HANDLE file;
    DWORD got = 0;
    const char *p;
    int n;
    if (vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, NS_INSTALLED_LEAF) == 0) {
        return 0;
    }
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!ReadFile(file, g_list, NS_INSTALLED_BYTES - 1, &got, NULL)) {
        got = 0;
    }
    CloseHandle(file);
    g_list[got] = '\0';
    want[0] = 'v';
    want[1] = 'v';
    want[2] = (char)('0' + game);
    want[3] = '_';
    lstrcpyA(want + 4, NS_ROW);
    n = lstrlenA(want);
    for (p = g_list; *p != '\0';) {
        const char *end = p;
        while (*end != '\0' && *end != '\n' && *end != '\r') {
            ++end;
        }
        if (end - p == n && memcmp(p, want, (size_t)n) == 0) {
            return 1;
        }
        p = *end != '\0' ? end + 1 : end;
    }
    return 0;
}

/* 1 when every site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpNoSafeguardsInstalled(void) {
    return g_installed;
}

/* How many sites the game's table has written (for the tests' emulation). */
int __stdcall VvfpNoSafeguardsSites(void) {
    return g_installed ? g_count : 0;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static vvfp_site_write w[NS_MAX_SITES];
    const ns_game *g = NULL;
    int i;
    (void)shipped;
    if (g_installed) {
        return;
    }
    for (i = 0; i < (int)(sizeof NS_GAMES / sizeof NS_GAMES[0]); ++i) {
        if (NS_GAMES[i].game == game) {
            g = &NS_GAMES[i];
        }
    }
    if (g == NULL || g->count <= 0 || g->count > NS_MAX_SITES || !row_installed(game)) {
        return;
    }
    for (i = 0; i < g->count; ++i) {
        vvfp_site_bytes(&w[i], g->sites[i].va, g->sites[i].length, g->sites[i].expect, g->sites[i].bytes);
    }
    if (vvfp_install_sites(w, g->count)) {
        g_count = g->count;
        g_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
