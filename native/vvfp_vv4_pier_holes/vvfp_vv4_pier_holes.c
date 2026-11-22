/* VVFP VV4 Pier Holes -- part of "Fix Vanilla Bugs", The Tree of Life.

   WHAT.  The two broken piers (the Fishing Nets puzzle) are drawn with ten hole pictures over the pier, sprites 104
   to 113 of the game's sprite table (northPierHoleEast.png .. southPierHoleNorthEast.png, one 1 x 1 grid each).
   The owner redrew the holes (art by Lorsieab2, 2026-11-19).  The owner's pictures ship as ten separate files in
   the game's Images folder, "vvfp_" + the stock name, each the stock picture's exact size and place; the game
   draws them in place of the stock holes, at the same times, places and sizes.  The game's own pictures are never
   changed.

   HOW.  The game builds every table sprite on first use from its entry in the sprite table at 0x4C07C8 (0x30 bytes
   each: id, the name's address, columns, rows, ..., then the registry's cached object; the registry 0x44CB80 builds
   it with ldwImageGrid 0x40AB10(name, 1, 1) and keeps it).  At start, before WinMain and so before any sprite is
   built, each of the ten entries gets the address of this companion's own name for the hole ("vvfp_..."), so the
   game's own registry builds and draws the owner's picture instead.  Nothing else in the entry changes.

   SAFETY.  A hole is switched only when its whole entry is the stock one (the id, the stock name's address, 1 x 1,
   nothing built yet) and the stock name is at that address, and when Images\vvfp_<stock name> is there and its PNG
   header says 8-bit RGBA of the stock picture's exact width and height.  A missing or wrong file leaves that hole's
   entry stock: the stock picture is drawn.  The switched entries are written together, all or none
   (native/shared/install_sites.h).  Nothing is written to a save, a villager record or a file; no text is shown.
   No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"

#define PH_GAME 4                        /* The Tree of Life */
#define PH_TABLE 0x4C07C8u               /* the sprite table: 305 entries of PH_STRIDE bytes */
#define PH_STRIDE 0x30
#define PH_FIRST_ID 104                  /* the first hole's id; its entry is table index PH_FIRST_INDEX */
#define PH_FIRST_INDEX 56
#define PH_COUNT 10

typedef struct {
    unsigned int stock_name_at;          /* the stock name's address (.rdata) */
    const char *stock_name;
    const char *ours;                    /* the owner's picture in Images */
    int width, height;                   /* the stock picture's size, which the owner's keeps */
} ph_hole;

/* In table order: ids 104 .. 113. */
static const ph_hole PH_HOLES[PH_COUNT] = {
    { 0x491940u, "northPierHoleEast.png", "vvfp_northPierHoleEast.png", 21, 14 },
    { 0x491924u, "southPierHoleNorthWest.png", "vvfp_southPierHoleNorthWest.png", 26, 32 },
    { 0x49190Cu, "southPierHoleEast.png", "vvfp_southPierHoleEast.png", 20, 29 },
    { 0x4918F0u, "southPierHoleSouthWest.png", "vvfp_southPierHoleSouthWest.png", 23, 37 },
    { 0x4918D4u, "northPierHoleMidSouth.png", "vvfp_northPierHoleMidSouth.png", 20, 12 },
    { 0x4918B8u, "northPierHoleMidNorth.png", "vvfp_northPierHoleMidNorth.png", 25, 24 },
    { 0x49189Cu, "northPierHoleSouthEast.png", "vvfp_northPierHoleSouthEast.png", 25, 25 },
    { 0x491884u, "northPierHoleWest.png", "vvfp_northPierHoleWest.png", 36, 43 },
    { 0x491868u, "southPierHoleSouthEast.png", "vvfp_southPierHoleSouthEast.png", 24, 38 },
    { 0x49184Cu, "southPierHoleNorthEast.png", "vvfp_southPierHoleNorthEast.png", 20, 21 },
};

static unsigned int g_stock[PH_COUNT][PH_STRIDE / 4];   /* each entry as the stock table holds it */
static unsigned int g_ours[PH_COUNT][PH_STRIDE / 4];    /* the same with the owner's name */
static int g_installed;                                 /* how many holes draw the owner's picture */

/* Images\<name> says 8-bit RGBA, width x height, in its PNG header. */
static int art_file_fits(const char *name, int width, int height) {
    static const unsigned char SIGNATURE[16] = {
        0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D, 'I', 'H', 'D', 'R',
    };
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    char leaf[64];
    unsigned char header[26];
    DWORD got = 0;
    HANDLE file;
    int ok;
    wsprintfA(leaf, "Images\\%s", name);
    if (!vvfp_game_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, leaf)) {
        return 0;
    }
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = ReadFile(file, header, sizeof header, &got, NULL) && got == sizeof header
        && memcmp(header, SIGNATURE, sizeof SIGNATURE) == 0
        && header[16] == 0 && header[17] == 0 && header[18] == (width >> 8) && header[19] == (width & 0xFF)
        && header[20] == 0 && header[21] == 0 && header[22] == (height >> 8) && header[23] == (height & 0xFF)
        && header[24] == 8 && header[25] == 6;
    CloseHandle(file);
    return ok;
}

/* How many holes draw the owner's picture (for the tests' emulation): 0 when nothing was installed. */
int __stdcall VvfpPierHolesInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w[PH_COUNT];
    int i, n = 0;
    (void)shipped;
    if (g_installed || game != PH_GAME) {
        return;
    }
    for (i = 0; i < PH_COUNT; ++i) {
        const ph_hole *h = &PH_HOLES[i];
        memset(g_stock[i], 0, sizeof g_stock[i]);
        g_stock[i][0] = (unsigned int)(PH_FIRST_ID + i);
        g_stock[i][1] = h->stock_name_at;
        g_stock[i][2] = 1;                                /* columns */
        g_stock[i][3] = 1;                                /* rows */
        memcpy(g_ours[i], g_stock[i], sizeof g_ours[i]);
        g_ours[i][1] = (unsigned int)(UINT_PTR)h->ours;
        if (!vvfp_site_holds(h->stock_name_at, (const unsigned char *)h->stock_name, lstrlenA(h->stock_name) + 1)
            || !art_file_fits(h->ours, h->width, h->height)) {
            continue;                                     /* the stock picture stays */
        }
        vvfp_site_bytes(&w[n], PH_TABLE + (unsigned int)(PH_FIRST_INDEX + i) * PH_STRIDE, PH_STRIDE,
                        (const unsigned char *)g_stock[i], (const unsigned char *)g_ours[i]);
        ++n;
    }
    if (n > 0 && vvfp_install_sites(w, n)) {
        g_installed = n;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
