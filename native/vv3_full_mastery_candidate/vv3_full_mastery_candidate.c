#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shlobj.h>   /* SHGetSpecialFolderPathA for the mask-sidecar path */
#include <string.h>

static HINSTANCE module_instance;

enum {
    IDD_ORIGINS_TECH = 201,
    IDD_ORIGINS_VILLAGER = 202,
    IDD_ORIGINS_FULL_MASTERY = 203,
    ID_BUY_FIRST = 1000,
    ID_BUY_LAST = 1013,
    ID_CHECK_FIRST = 1100,
    STATE_VILLAGER = 0x10000,
    STATE_VILLAGE_WIDE = 0x20000,
    STATE_RUNNING_ONLY = 0x40000,
    STATE_FULL_MASTERY_ONLY = 0x80000
};

/* Upgrade names and formatted costs, indexed by the Buy-button row (command -
   ID_BUY_FIRST).  Used to build the per-upgrade preview confirm and the
   "<Upgrade> completed." results, matching OFFICIAL Origins Upgrade Prompts. */
static const char *const tech_names[] = {
    "Time Warp", "Island Event", "Barrel of Babies", "Tech Point Doubler",
    "Food Point Doubler", "Full Heal / Cure All",
    "Grant Running to All Villagers", "Grant Full Mastery to All Villagers",
    "All Villagers are Exactly 18", "Complete All Collections",
    "Reset All Collections",
    "Equal Division of Labor (Includes Parenting)",
    "Equal Division of Labor (No Parenting)",
    "Change Appearance for All"
};
static const char *const tech_costs[] = {
    "50,000", "30,000", "75,000", "500,000", "500,000", "30,000",
    "1,000,000", "1,000,000", "1,000,000", "1,000,000", "1,000,000",
    "1,000,000", "1,000,000", "450,000"
};
static const char *const detail_names[] = {
    "Grant Youth", "Grant Full Mastery", "Grant Running", "Set Age to 18",
    "Change Appearance"
};
static const char *const detail_costs[] = {
    "50,000", "100,000", "40,000", "50,000", "5,000"
};

/* Set at WM_INITDIALOG so WM_COMMAND knows whether this is the Tech (0) or
   Villager Details (1) menu, and the row state (owned bits) so an owned
   Doubler's "Remove" click is confirmed as a removal, not a purchase.  The
   menus are modal and shown one at a time. */
static int s_villager_menu;
static int s_dialog_state;

__declspec(dllexport) void __stdcall VV3WorldMaskDrawAt(void *record, int *args);
__declspec(dllexport) void __stdcall VV3RunningMaskBoundary(int after);

/* The exe caves read these fixed slots for our draw fns, so a per-frame cave needs no
   LoadLibrary/GetProcAddress -- we publish our exports here on load.
   ALL SLOTS LIVE IN THE PATCH-OWNED APPENDED SECTION .vv3md (R/W, VA 0x6E0000, 0x1000
   bytes), NOT in a borrowed gap.  They previously sat at 0x6C7A00+, which is past .data's
   VirtualSize (0x6C7518) -- i.e. in the slack between .data's vsize and the next section.
   That is a code cave and violates docs/head-mask-rendering.md Part 7, so the build now
   appends .vv3mc (R-X, trampolines) + .vv3md (R/W, these slots) and everything moved.
   Layout: +0x00 MASK_DRAWFN (Detail cave), +0x04 world DrawAt, +0x08..+0x34 reserved,
   +0x34 auto-load latch (exe-side), +0x3C worlddbg, +0x40 chiefdbg, +0x44 active save
   slot (captured by the exe save-builder trampoline), +0x48 Running-boundary fn. */
#define VV3_WORLD_DRAWFN_PTR_SLOT  0x006E0004u
#define VV3_RUNNING_BOUNDARY_PTR_SLOT 0x006E0048u

extern int g_vv3_worlddbg[8];
extern int g_vv3_chiefdbg[8];

/* The companion can be loaded by an unpatched executable (or inspected by a
   tool) before the patch-owned .vv3md section exists.  Do not let DllMain
   write the fixed slots in that case.  Require one committed writable region
   covering the complete 0x1000-byte data page before publishing any pointer. */
static BOOL vv3_mask_data_page_writable(void) {
    MEMORY_BASIC_INFORMATION info;
    UINT_PTR begin = (UINT_PTR)0x006E0000u;
    UINT_PTR end = begin + 0x1000u;
    UINT_PTR region_begin;
    UINT_PTR region_end;
    DWORD protection;
    SIZE_T queried = VirtualQuery(
        (LPCVOID)begin, &info, sizeof(info)
    );
    if (queried != sizeof(info) || info.State != MEM_COMMIT) return FALSE;
    region_begin = (UINT_PTR)info.BaseAddress;
    region_end = region_begin + info.RegionSize;
    if (region_begin > begin || region_end < end) return FALSE;
    protection = info.Protect;
    if ((protection & (PAGE_GUARD | PAGE_NOACCESS)) != 0) return FALSE;
    switch (protection & 0xFFu) {
    case PAGE_READWRITE:
    case PAGE_WRITECOPY:
    case PAGE_EXECUTE_READWRITE:
    case PAGE_EXECUTE_WRITECOPY:
        return TRUE;
    default:
        return FALSE;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        module_instance = instance;
        if (!vv3_mask_data_page_writable()) return TRUE;
        *(void **)(UINT_PTR)VV3_WORLD_DRAWFN_PTR_SLOT  = (void *)&VV3WorldMaskDrawAt;
        /* No cursor/held function pointer is published.  The stock calls at 0x434357 and
           0x4344B3 are both inside the same three-style timed UI/effect renderer: its
           selector is 0..2, entries are 24 bytes, elapsed time is compared with 0x12C and
           0x7080, and no villager record reaches either call.  Their bytes remain stock until
           a player trace proves the real grab and held-render boundaries. */
        *(void **)(UINT_PTR)0x006E003Cu                  = (void *)&g_vv3_worlddbg[0];
        *(void **)(UINT_PTR)0x006E0040u                  = (void *)&g_vv3_chiefdbg[0];
        *(void **)(UINT_PTR)VV3_RUNNING_BOUNDARY_PTR_SLOT = (void *)&VV3RunningMaskBoundary;
    }
    return TRUE;
}

/* ---- Heathen-mask overlay atlas (Detail-screen render support) ----
   The Detail head-draw hook draws the villager head, then (if the villager's
   mask byte record+0xED0 is 1..5) draws a mask cell on top from a DEDICATED mask
   atlas, Images/heathen_masks.png (8 directional cols x 5 mask rows).  Loading a
   game sprite atlas requires the game's own allocator + loader (the atlas object
   is a game-internal type), so this export builds it once through those exe
   routines and caches the result -- keeping the ~90 bytes of one-time load code
   (and the filename string) in the DLL so the exe render cave stays tiny.  It
   never touches save data.  These absolute addresses are fixed: the game exe is
   non-ASLR (image base 0x00400000) and loaded in this process.

     0x0046EC93  game allocator(size) -> ptr (cdecl, caller-cleaned)
     0x0040AF10  atlas loader(this=ecx, filename, cols, rows) -> atlas (ret 0xC)

   Returns the loaded atlas object pointer (NULL if the load fails, e.g. the PNG
   is missing -- the render cave then simply skips the mask, so a missing asset
   degrades to "no mask", never a crash).  Called lazily from the render hook, so
   the graphics subsystem is always up by the time this runs. */
static void *g_mask_atlas;

/* Compare an installed file with the exact embedded RCDATA.  A merely present PNG
   is not enough: the stock loader assumes the canonical 520x725 atlas and can
   dereference an incomplete/stale image while constructing its object. */
static BOOL vv3_file_matches_blob(const char *path, const void *data, DWORD size) {
    HANDLE fh;
    LARGE_INTEGER length;
    unsigned char buffer[4096];
    DWORD offset = 0, want, got;
    BOOL same = TRUE;
    fh = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                     FILE_ATTRIBUTE_NORMAL, NULL);
    if (fh == INVALID_HANDLE_VALUE) return FALSE;
    if (!GetFileSizeEx(fh, &length) || length.QuadPart != (LONGLONG)size) {
        CloseHandle(fh);
        return FALSE;
    }
    while (offset < size) {
        want = size - offset;
        if (want > (DWORD)sizeof(buffer)) want = (DWORD)sizeof(buffer);
        if (!ReadFile(fh, buffer, want, &got, NULL) || got != want
            || memcmp(buffer, (const unsigned char *)data + offset, got) != 0) {
            same = FALSE;
            break;
        }
        offset += got;
    }
    CloseHandle(fh);
    return same;
}

/* Self-deploy the canonical embedded atlas (RCDATA 5000) into
   <game>\Images\heathen_masks.png.  Existing non-canonical/stale art is replaced
   through a sibling temp file and an atomic MoveFileExA publish.  The return value
   is deliberately part of the loader gate: no valid canonical file means the
   unsafe game atlas constructor is never called. */
static BOOL vv3_extract_mask_atlas(void) {
    char exe[MAX_PATH], images[MAX_PATH], path[MAX_PATH], tmp[MAX_PATH];
    char *base, *p;
    HRSRC res;
    HGLOBAL blob;
    const void *data;
    DWORD size, written;
    HANDLE fh;
    BOOL ok;
    DWORD n = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return FALSE;
    base = exe;
    for (p = exe; *p != '\0'; ++p) if (*p == '\\' || *p == '/') base = p + 1;
    *base = '\0';                                    /* game directory + trailing slash */
    /* Budget both the final path and the ".tmp" staging name (longest suffix). */
    if (lstrlenA(exe) + (int)sizeof("Images\\heathen_masks.png.tmp") >= (int)sizeof(path)) return FALSE;
    wsprintfA(images, "%sImages", exe);
    if (!CreateDirectoryA(images, NULL)
        && GetLastError() != ERROR_ALREADY_EXISTS) return FALSE;
    wsprintfA(path, "%sImages\\heathen_masks.png", exe);
    res = FindResourceA(module_instance, MAKEINTRESOURCEA(5000), RT_RCDATA);
    if (res == NULL) return FALSE;
    size = SizeofResource(module_instance, res);
    blob = LoadResource(module_instance, res);
    if (blob == NULL || size == 0) return FALSE;
    data = LockResource(blob);
    if (data == NULL) return FALSE;
    if (vv3_file_matches_blob(path, data, size)) return TRUE;
    /* Write to a sibling ".tmp" first, verify the FULL payload landed, then publish
       with MoveFileExA.  A short/interrupted write can never leave a truncated
       heathen_masks.png that the loader could consume. */
    wsprintfA(tmp, "%sImages\\heathen_masks.tmp", exe);
    fh = CreateFileA(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                     FILE_ATTRIBUTE_NORMAL, NULL);
    if (fh == INVALID_HANDLE_VALUE) return FALSE;
    written = 0;
    ok = WriteFile(fh, data, size, &written, NULL);
    CloseHandle(fh);
    if (!ok || written != size) {                    /* short write -> discard staging */
        DeleteFileA(tmp);
        return FALSE;
    }
    if (!MoveFileExA(tmp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileA(tmp);
        return FALSE;
    }
    return vv3_file_matches_blob(path, data, size);
}

static int g_mask_atlas_tried;

/* The VV3 atlas object shape is known from the stock loader contract.  Guard the
   object read and all required dimensions before caching it; a malformed loader
   result therefore degrades to no mask instead of reaching 0x42E5E0. */
static BOOL vv3_mask_atlas_shape_valid(void *atlas) {
    BOOL valid = FALSE;
    if (atlas == NULL) return FALSE;
    __try {
        valid = (*(void **)((unsigned char *)atlas + 0x04) != NULL
            && *(int *)((unsigned char *)atlas + 0x08) == 8
            && *(int *)((unsigned char *)atlas + 0x0C) == 5
            && *(int *)((unsigned char *)atlas + 0x10) == 65
            && *(int *)((unsigned char *)atlas + 0x14) == 145);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        valid = FALSE;
    }
    return valid;
}

__declspec(dllexport) void *__stdcall VV3GetMaskAtlas(void) {
    static const char mask_atlas_name[] = "heathen_masks.png";
    void *atlas = NULL, *atlas_object = NULL;
    if (g_mask_atlas != NULL) return g_mask_atlas;
    if (g_mask_atlas_tried) return NULL;
    g_mask_atlas_tried = 1;
    if (!vv3_extract_mask_atlas()) return NULL;
    __try {
        __asm {
            push 0x34               /* atlas object size (matches the game's own) */
            mov  eax, 0x0046EC93
            call eax                /* eax = fresh atlas object                    */
            add  esp, 4
            mov  atlas_object, eax
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        atlas_object = NULL;
    }
    /* Never call the image loader with a null/invalid allocator result. */
    if (atlas_object == NULL) return NULL;
    __try {
        __asm {
            mov  ecx, atlas_object    /* this = the object                         */
            push 5                    /* rows (5 masks)                            */
            push 8                    /* cols (8 directional frames)               */
            lea  eax, mask_atlas_name
            push eax                  /* filename                                  */
            mov  eax, 0x0040AF10
            call eax                  /* loader(this, name, 8, 5) -> eax = atlas   */
            mov  atlas, eax
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        atlas = NULL;
    }
    if (!vv3_mask_atlas_shape_valid(atlas)) return NULL;
    g_mask_atlas = atlas;
    return g_mask_atlas;
}

/* These old SDL2 games run "fullscreen" as a WS_EX_TOPMOST borderless window,
   so a normal owned dialog is painted *behind* the game and can't be reached.
   Lift the dialog above the game and center it on the game's monitor.  Called
   at WM_INITDIALOG for every dialog the patch shows.  A no-op in windowed mode
   beyond re-centering, which is harmless. */
static void center_topmost_on_owner(HWND window) {
    HWND owner = GetWindow(window, GW_OWNER);
    HMONITOR monitor = MonitorFromWindow(owner ? owner : window,
                                         MONITOR_DEFAULTTONEAREST);
    MONITORINFO mi;
    RECT rc;
    int win_w, win_h, x, y;

    mi.cbSize = sizeof(mi);
    if (!GetMonitorInfoA(monitor, &mi)) {
        SetWindowPos(window, HWND_TOPMOST, 0, 0, 0, 0,
                     SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
        SetForegroundWindow(window);
        return;
    }
    GetWindowRect(window, &rc);
    win_w = rc.right - rc.left;
    win_h = rc.bottom - rc.top;
    x = mi.rcMonitor.left + (mi.rcMonitor.right - mi.rcMonitor.left - win_w) / 2;
    y = mi.rcMonitor.top + (mi.rcMonitor.bottom - mi.rcMonitor.top - win_h) / 2;
    SetWindowPos(window, HWND_TOPMOST, x, y, 0, 0, SWP_NOSIZE | SWP_SHOWWINDOW);
    SetForegroundWindow(window);
}

/* Make the upgrade menus usable in fullscreen, exactly the way the other VV
   games' shipped patches do.  VV3 runs "fullscreen" as a topmost SDL2 window
   covering the monitor.  When our modal dialog takes the foreground, SDL's
   default behavior MINIMIZES that window (the SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS
   hint) -- and minimizing/restoring the SDL surface while a modal blocks the
   render loop is the hazardous transition that left the game black and hung
   behind the menu.  The fix (see native/vv2_origins_icons, vv4_origins_icons):
   turn that hint OFF so the game stays fullscreen and visible behind the
   dialog; the dialog is then lifted above the fullscreen surface and to the
   foreground at WM_INITDIALOG (center_topmost_on_owner).  SDL2.dll is already
   loaded by the game and re-reads the hint on focus loss, so setting it before
   we show any dialog / message box is enough.  We touch no window, engine, or
   render state -- so nothing can corrupt the surface or hang the loop. */
static void vv3_prep_fullscreen(void) {
    HMODULE sdl = GetModuleHandleA("SDL2.dll");
    if (sdl != NULL) {
        typedef int(__cdecl * set_hint_t)(const char *, const char *);
        set_hint_t set_hint = (set_hint_t)GetProcAddress(sdl, "SDL_SetHint");
        if (set_hint != NULL) {
            set_hint("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0");
        }
    }
}

/* Kept for call-site compatibility: prep fullscreen before a modal; there is
   nothing to restore afterward, so end_modal_over_game is a no-op. */
static HWND begin_modal_over_game(void) {
    vv3_prep_fullscreen();
    return NULL;
}

static void end_modal_over_game(HWND owner) {
    (void)owner;
}


/* Villager record array. Base and stride are fixed in the image, so this needs
   nothing from the executable -- the DLL can answer the question on its own.
   The slot bound is read from the same 0x42883A immediate the robe fan-out
   uses, because expanded builds raise it from 150 to 256.

   A slot counts as OCCUPIED whenever its active field is set, whether or not
   the villager in it is alive. That is the whole point: an unburied skeleton
   still holds its record, and the game's own population counter skips it
   (health <= 0), so a village full of bodies reads as small while its slots
   are nearly all taken. The barrel then spawns fewer children than it charged
   for -- sometimes none. */
#define VV3_RECORD_BASE      0x59E124
#define VV3_RECORD_STRIDE    0x1F8C
#define VV3_SLOT_BOUND_PTR   0x42883A
#define VV3_OFF_ACTIVE       0xF10
#define VV3_BARREL_CHILDREN  3

static int vv3_has_free_villager_slots(int wanted) {
    unsigned int bound = *(volatile unsigned int *)(UINT_PTR)VV3_SLOT_BOUND_PTR;
    const unsigned char *record = (const unsigned char *)(UINT_PTR)VV3_RECORD_BASE;
    unsigned int index;
    int free_slots = 0;

    if (bound == 0 || bound > 256) {
        return 1;               /* unrecognised bound -> do not block */
    }
    for (index = 0; index < bound; ++index) {
        if (*(volatile int *)(record + VV3_OFF_ACTIVE) == 0) {
            ++free_slots;
            if (free_slots >= wanted) {
                return 1;
            }
        }
        record += VV3_RECORD_STRIDE;
    }
    return 0;
}

/* Duplicate-purchase state for the Tech menu's Island Event and Barrel of
   Babies rows.

   Both are queued by writing a value that may already be there -- the Island
   countdown zeroed, the Barrel flag set -- so buying a second one while the
   first is still pending changes nothing and charges full price anyway.

   The other four games have their executable compute this and hand it over in
   the menu's state word. VV3's payload has no cave space left for that, which
   is exactly what this DLL is for: it runs inside the game's own process, so
   it can reach the world manager and read the two values itself. Nothing is
   asked of the executable.

   It reads the manager's singleton POINTER (0x4B309C) rather than calling the
   getter at 0x428B60 that the executable's own purchase path uses. That getter
   is a lazy constructor: when the pointer is null it allocates 0x12FD4 bytes
   and constructs the manager. Building the menu must not have that side
   effect, and a null pointer already answers the question -- with no manager
   there is nothing pending.

   The manager layout differs between the stock and expanded builds. The
   executable picks between them by testing whether the immediate at 0x42883A
   is 256, and this uses that same probe so both builds read the right field. */
#define VV3_MANAGER_SINGLETON     0x4B309C
#define VV3_ARCH_PROBE            0x42883A
#define VV3_ARCH_EXPANDED_VALUE   0x100
#define VV3_ARCH_EXPANDED_OFFSET  0x7598
#define VV3_ISLAND_COUNTDOWN_OFF  0x12EF4
#define VV3_BARREL_PENDING_FLAG   0x4B3C75

enum {
    VV3_PENDING_ROW_ISLAND = 1,
    VV3_PENDING_ROW_BARREL = 2
};

/* Is this Tech-menu row blocked by an identical purchase already pending?
   Villager-menu rows are never affected. */
static int vv3_row_purchase_pending(int villager_menu, int row) {
    unsigned char *manager;
    int extra;

    if (villager_menu) {
        return 0;
    }
    if (row == VV3_PENDING_ROW_BARREL) {
        if (*(volatile unsigned char *)(UINT_PTR)VV3_BARREL_PENDING_FLAG != 0) {
            return 1;
        }
        return !vv3_has_free_villager_slots(VV3_BARREL_CHILDREN);
    }
    if (row != VV3_PENDING_ROW_ISLAND) {
        return 0;
    }
    manager = *(unsigned char *volatile *)(UINT_PTR)VV3_MANAGER_SINGLETON;
    if (manager == NULL) {
        return 0;                 /* no manager yet -> claim nothing */
    }
    extra = (*(volatile unsigned int *)(UINT_PTR)VV3_ARCH_PROBE
             == (unsigned int)VV3_ARCH_EXPANDED_VALUE)
        ? VV3_ARCH_EXPANDED_OFFSET
        : 0;
    return *(volatile int *)(manager + extra + VV3_ISLAND_COUNTDOWN_OFF) == 0;
}


/* Barrel of Babies is the one row whose result the village's current state can
   quietly reduce, so its confirmation says so before the player pays.

   Measured in play: with skeletons lying unburied the barrel delivered two
   children; once villagers had buried some, the same purchase delivered three.
   This is NOT the living-population count -- the games' own counters skip any
   record whose health field is <= 0, so the dead are already excluded there
   and the capacity gate that uses them passed. The reduction happens further
   in, where the spawn places each child, so an unburied body still costs a
   slot. */
#define BARREL_CAPACITY_NOTE \
    "\r\n\r\nNote: unburied villagers still take up room in the village, " \
    "so lying skeletons can reduce how many babies arrive. Bury them first " \
    "for the full three."


static INT_PTR CALLBACK upgrade_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        int villager_menu = (lparam & STATE_VILLAGER) != 0;
        s_villager_menu = villager_menu;
        s_dialog_state = (int)lparam;
        int row_count = villager_menu
            ? 5
            : ((lparam & STATE_RUNNING_ONLY) != 0
                ? 7
                : ((lparam & STATE_FULL_MASTERY_ONLY) != 0
                    ? 8
                    : ((lparam & STATE_VILLAGE_WIDE) != 0 ? 9 : 6)));
        int row;
        /* Hide EVERY badge the dialog can carry, not just the first nine.
           The tech menu runs to 14 rows (6 base + 3 village-wide grants +
           Complete/Reset Collections + two Equal Division rows + Change
           Appearance for All).  The resource creates those badges VISIBLE, so
           stopping at 9 left rows 9-13 showing a green checkmark permanently,
           whatever the player owned.  The show loop below re-shows only the
           rows whose owned bit is set, and the exe sets only bits 3 and 4 --
           the Tech and Food Point Doublers -- so those two rows are the only
           ones that can ever display a checkmark, and only while owned in the
           current save.  GetDlgItem returns NULL for a row this game does not
           declare and ShowWindow(NULL, ...) is a harmless no-op. */
        for (row = 0; row < 14; ++row) {
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
        }
        for (row = 0; row < row_count; ++row) {
            if (vv3_row_purchase_pending(villager_menu, row)) {
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
                continue;
            }
            if ((lparam & (1 << row)) != 0) {
                /* Only the two Doublers may ever show a green check, and only
                   while they are owned in the current save. Every other row --
                   including the Details menu's already-satisfied rows, whose
                   state bits 0-3 the callers deliberately set -- keeps its
                   badge hidden and conveys state through the button instead. */
                if (!villager_menu && (row == 3 || row == 4)) {
                    ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
                }
                if (villager_menu) {
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
                } else if (row == 3 || row == 4) {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Remove");
                } else {
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
                }
            } else if ((lparam & (1 << (8 + row))) != 0) {
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
            }
        }
        center_topmost_on_owner(window);
        return TRUE;
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command >= ID_BUY_FIRST && command <= ID_BUY_LAST) {
            int row = (int)(command - ID_BUY_FIRST);
            const char *name = s_villager_menu ? detail_names[row] : tech_names[row];
            const char *cost = s_villager_menu ? detail_costs[row] : tech_costs[row];
            /* Owned Tech/Food Doublers (rows 3/4) show an explicit "Remove"
               button. Removal is not a purchase and therefore has no
               confirmation prompt; the caller reports the no-refund result
               after the action-specific removal path completes. */
            int is_remove = !s_villager_menu && (row == 3 || row == 4)
                && (s_dialog_state & (1 << row)) != 0;
            char prompt[512];
            if (is_remove) {
                EndDialog(window, (INT_PTR)row);
                return TRUE;
            }
            wsprintfA(
                prompt,
                "Do you want to buy %s for %s tech points?\r\n"
                "Press OK to confirm, or Cancel.%s",
                name, cost,
                (!s_villager_menu && row == VV3_PENDING_ROW_BARREL)
                    ? BARREL_CAPACITY_NOTE : "");
            if (MessageBoxA(
                    window,
                    prompt,
                    s_villager_menu ? "Villager Upgrades" : "Origins Upgrades",
                    MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST) == IDOK) {
                EndDialog(window, (INT_PTR)row);
            }
            return TRUE;
        }
        if (command == IDCANCEL) {
            EndDialog(window, -1);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, -1);
        return TRUE;
    }
    return FALSE;
}

static int show_upgrade_menu(int villager_menu, int dialog_state) {
    int resource = villager_menu
        ? IDD_ORIGINS_VILLAGER
        : (((dialog_state & STATE_FULL_MASTERY_ONLY) != 0)
            ? IDD_ORIGINS_FULL_MASTERY
            : IDD_ORIGINS_TECH);
    int result;
    if (villager_menu) {
        dialog_state |= STATE_VILLAGER;
    }
    /* Stop SDL minimizing the game when the dialog takes focus, then show the
       dialog owned by the game window and lift it above the fullscreen surface
       (center_topmost_on_owner at WM_INITDIALOG). */
    begin_modal_over_game();
    result = (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(resource),
        GetForegroundWindow(),
        upgrade_dialog,
        dialog_state
    );
    return result;
}

__declspec(dllexport) int __stdcall ShowOriginsUpgradeMenuState(
    int villager_menu,
    int dialog_state
) {
    return show_upgrade_menu(villager_menu, dialog_state);
}

__declspec(dllexport) int __stdcall ShowOriginsUpgradeMenu(
    int villager_menu,
    int state
) {
    int dialog_state = 0;
    if (villager_menu) {
        unsigned char *villager = (unsigned char *)(UINT_PTR)(unsigned int)state;
        int row;
        int running_like = 0;
        int running_dislike = 0;
        int available_like = 0;
        if (villager != NULL) {
            if (*(int *)(villager + 0x348) <= 100) {
                dialog_state |= 1 << 0;
            }
            if (*(int *)(villager + 0x3BC) >= 90
                && *(int *)(villager + 0x3C0) >= 90
                && *(int *)(villager + 0x3C4) >= 90
                && *(int *)(villager + 0x3C8) >= 90
                && *(int *)(villager + 0x3CC) >= 90) {
                dialog_state |= 1 << 1;
            }
            for (row = 0; row < 3; ++row) {
                int like = *(int *)(villager + 0x398 + row * 4);
                if (like == 38) {
                    running_like = 1;
                } else if (like == -1) {
                    available_like = 1;
                }
                if (*(int *)(villager + 0x3A8 + row * 4) == 38) {
                    running_dislike = 1;
                }
            }
            if (running_like && !running_dislike) {
                dialog_state |= 1 << 2;
            } else if (!running_like && !available_like) {
                dialog_state |= 1 << (8 + 2);
            }
            if (*(int *)(villager + 0x348) == 360) {
                dialog_state |= 1 << 3;
            }
        }
    } else {
        if ((state & 1) != 0) {
            dialog_state |= 1 << 3;
        }
        if ((state & 2) != 0) {
            dialog_state |= 1 << 4;
        }
    }
    return show_upgrade_menu(villager_menu, dialog_state);
}

/* ---- VV3 village-wide count + VV5-Task9-style result ----
   The payload's village-wide applies don't report counts, so the DLL counts
   affected villagers directly (read-only) using VV3's record layout, before the
   payload applies the change.  Prepare stores the counts and returns whether the
   purchase would change anything (so the payload can refund/skip on a no-op);
   the result reader formats the message from the stored counts. */
#define VV3_REC_BASE   0x0059E124u
#define VV3_SLOTS_PTR  0x0042883Au
#define VV3_STRIDE     0x1F8Cu
#define VV3_ACTIVE     0xF10   /* byte: 0 = empty slot                */
#define VV3_HEALTH     0xE78   /* int:  <= 0 = not a living villager  */
#define VV3_AGE        0xDC4   /* int:  360 = 18 years                */
#define VV3_SKILL0     0xEAC   /* 5 ints, +4 each; 100 = mastered     */
#define VV3_LIKES      0xFB4   /* 3 ints; 38 = running; -1 = empty    */
#define VV3_DISLIKES   0xFC0   /* 3 ints; 38 = running                */
#define VV3_RUN_PREF   38
#define VV3_GENDER     0xDC8   /* byte: 0 = male, 1 = female          */
#define VV3_CHIEF      0xE80   /* byte: != 0 = Tribal Chief (no pref) */
#define VV3_PREF       0xEC0   /* int:  -1 none, 0..4 preferred skill */
#define VV3_TECH_POINTS 0x00582644u  /* int: the tech-point pool the Buy charges */
#define EDL_COST       1000000

/* ---- Cosmetic Heathen-mask store (SAFE: DLL-owned, never the record/save) ----
   The per-villager mask choice can NOT live in a record byte: VV3's record +0xED0
   read 0 statically but the running sim ZEROES it every frame (the same trap that
   killed VV2's +0x480), so a written mask vanishes within a frame.  So the choice
   lives in DLL memory the patch owns -- a 256-entry table keyed by villager slot
   index (index = (record - 0x59E124) / 0x1F8C, the id the game itself uses).  The
   villager record and the save file are NEVER written.

   A slot is reused when a villager dies and a newborn takes its place, so each
   stored mask is guarded by an identity fingerprint over gender + 3 Likes + 3
   Dislikes.  Ordinary reads require exactly one matching live villager and
   exactly one matching stored mask.  A whole-village appearance transaction
   may bind a collision group only when it covers every live owner and gives
   the entire group one mask; that intent is encoded as one identical stored
   copy per live owner, and reads require the live/stored counts to remain equal.
   Any incomplete, mixed-mask, or subsequently changed group fails closed.  The
   owned Grant Running writers bracket their exact preference transforms and
   refresh only unique live/stored preimages, so that upgrade cannot cross-tag
   indistinguishable villagers.  A sequential replacement with the same
   fingerprint remains unresolvable without a proven stable identity field.
   Persistence is kept in a sidecar next
   to the active save.  The executable's save-builder hook publishes the active
   positive save number in the patch-owned .vv3md slot below; a change of that
   number clears the in-memory table before the matching sidecar is loaded.
   Render reads via VV3_GetMaskForRecord; the individual chooser writes through
   VV3_SetMaskForRecord, while the village-wide dialog owns its shadow commit. */
#define VV3_MASK_SLOTS 256
#define VV3_MASK_MAX   5             /* 1..5 = Blue/Orange/Red/Purple/Chief; 0=none */

static unsigned char g_vv3_mask[VV3_MASK_SLOTS];
static unsigned int  g_vv3_mask_fp[VV3_MASK_SLOTS];
/* Grant Running changes the same preference arrays used by the slot-shift
   fingerprint.  The boundary export snapshots the pre-write live and stored
   identities, then refreshes only a preimage unique in both populations.  A
   stale or ambiguous entry therefore cannot be retagged merely because a
   village-wide write happened. */
static unsigned int g_vv3_running_before[VV3_MASK_SLOTS];
static unsigned int g_vv3_running_mask_before[VV3_MASK_SLOTS];
static int g_vv3_running_capture;

/* The Origins patch captures the save number at the exact stock save-builder
   entry (0x403290) into this .vv3md word.  Zero is deliberately invalid: no
   mask data is read or written until the game has identified a positive save.
   This is patch-owned memory, not a villager record or a save-file field. */
#define VV3_MASK_SLOT_PTR 0x006E0044u

/* FNV-1a/32 over the current identity fields; Grant Running's owned mutation
   is bracketed by VV3RunningMaskBoundary, so this raw fingerprint can continue
   to protect slot reuse and slot-shift recovery without assuming Likes/Dislikes
   are immutable.  0 -> 1 (0 reserved). */
static unsigned int vv3_mask_fingerprint(const unsigned char *rec) {
    unsigned int h = 2166136261u;
    const unsigned char *p;
    int i, b;
    h = (h ^ rec[VV3_GENDER]) * 16777619u;
    for (i = 0; i < 3; ++i) {
        p = rec + VV3_LIKES + i * 4;
        for (b = 0; b < 4; ++b) h = (h ^ p[b]) * 16777619u;
    }
    for (i = 0; i < 3; ++i) {
        p = rec + VV3_DISLIKES + i * 4;
        for (b = 0; b < 4; ++b) h = (h ^ p[b]) * 16777619u;
    }
    return h ? h : 1u;
}

/* Slot index for a record pointer, or -1 if it is not a valid record base. */
static int vv3_mask_index(const void *record) {
    UINT_PTR base = (UINT_PTR)VV3_REC_BASE;
    UINT_PTR p = (UINT_PTR)record;
    UINT_PTR off, idx;
    int slots;
    if (record == NULL || p < base) return -1;
    off = p - base;
    if (off % VV3_STRIDE) return -1;
    idx = off / VV3_STRIDE;
    slots = *(int *)(UINT_PTR)VV3_SLOTS_PTR;
    if (slots < 0) return -1;
    if (slots > VV3_MASK_SLOTS) slots = VV3_MASK_SLOTS;
    if (idx >= (UINT_PTR)slots) return -1;
    return (int)idx;
}

/* A raw preference fingerprint is not an identity.  Resolve it only when one
   active/living record owns it; -1 means absent OR ambiguous.  Returning the
   unique slot lets the caller prove that the supplied record is that owner,
   rather than accepting an unrelated pointer with the same hash. */
static int vv3_mask_unique_live_index(unsigned int fp) {
    const unsigned char *rec = (const unsigned char *)(UINT_PTR)VV3_REC_BASE;
    int found = -1;
    int i, slots = *(int *)(UINT_PTR)VV3_SLOTS_PTR;
    if (fp == 0) return -1;
    if (slots < 0) slots = 0;
    if (slots > VV3_MASK_SLOTS) slots = VV3_MASK_SLOTS;
    for (i = 0; i < slots; ++i, rec += VV3_STRIDE) {
        if (rec[VV3_ACTIVE] == 0 || *(const int *)(rec + VV3_HEALTH) <= 0)
            continue;
        if (vv3_mask_fingerprint(rec) != fp) continue;
        if (found >= 0) return -1;
        found = i;
    }
    return found;
}

/* Resolve a sidecar fingerprint only when exactly one nonzero mask owns it.
   This check deliberately precedes the same-slot fast path: after a reload or
   compaction, a duplicate live fingerprint could otherwise make the wrong
   stored index look valid. */
static int vv3_mask_unique_stored_index(unsigned int fp) {
    int found = -1;
    int i;
    if (fp == 0) return -1;
    for (i = 0; i < VV3_MASK_SLOTS; ++i) {
        if (g_vv3_mask[i] == 0 || g_vv3_mask_fp[i] != fp) continue;
        if (found >= 0) return -1;
        found = i;
    }
    return found;
}

/* Count active/living owners for the unique and batch-group proof paths. */
static int vv3_mask_live_fingerprint_count(unsigned int fp) {
    const unsigned char *rec = (const unsigned char *)(UINT_PTR)VV3_REC_BASE;
    int found = 0;
    int i, slots = *(int *)(UINT_PTR)VV3_SLOTS_PTR;
    if (fp == 0) return 0;
    if (slots < 0) slots = 0;
    if (slots > VV3_MASK_SLOTS) slots = VV3_MASK_SLOTS;
    for (i = 0; i < slots; ++i, rec += VV3_STRIDE) {
        if (rec[VV3_ACTIVE] == 0 || *(const int *)(rec + VV3_HEALTH) <= 0)
            continue;
        if (vv3_mask_fingerprint(rec) != fp) continue;
        ++found;
    }
    return found;
}

static int vv3_mask_has_duplicate_live_fingerprint(unsigned int fp) {
    return vv3_mask_live_fingerprint_count(fp) >= 2;
}

/* Only a nonzero stored mask is able to reappear through the guarded getter.
   A zero mask/fingerprint pair is already empty and must not make an explicit
   None batch look applicable. */
static int vv3_mask_has_stored_fingerprint(unsigned int fp) {
    int i;
    if (fp == 0) return 0;
    for (i = 0; i < VV3_MASK_SLOTS; ++i)
        if (g_vv3_mask[i] != 0 && g_vv3_mask_fp[i] == fp) return 1;
    return 0;
}

/* A batch-owned collision group is renderable only while its sidecar still has
   exactly one identical nonzero copy for every active/living owner.  This is a
   positive group proof, not a relaxation of the ordinary uniqueness gate. */
static int vv3_mask_stored_group_value(unsigned int fp) {
    int i, live_count, stored_count = 0, value = 0;
    if (fp == 0) return 0;
    live_count = vv3_mask_live_fingerprint_count(fp);
    if (live_count < 2) return 0;
    for (i = 0; i < VV3_MASK_SLOTS; ++i) {
        if (g_vv3_mask[i] == 0 || g_vv3_mask_fp[i] != fp) continue;
        if (value == 0)
            value = g_vv3_mask[i];
        else if (value != g_vv3_mask[i])
            return 0;
        ++stored_count;
    }
    return stored_count == live_count ? value : 0;
}

/* A nonempty current slot may be reused only when it is already owned by the
   target fingerprint or when its fingerprint has no active/living owner.  A
   unique or duplicate live owner is foreign state and must be preserved. */
static int vv3_mask_current_slot_writable(int idx, unsigned int target_fp) {
    unsigned int current_fp;
    if (idx < 0 || idx >= VV3_MASK_SLOTS) return 0;
    if (g_vv3_mask[idx] == 0) return 1;
    current_fp = g_vv3_mask_fp[idx];
    if (current_fp == 0 || current_fp == target_fp) return 1;
    if (vv3_mask_unique_live_index(current_fp) >= 0) return 0;
    if (vv3_mask_has_duplicate_live_fingerprint(current_fp)) return 0;
    return 1;
}

static int vv3_mask_current_slot_foreign_live(int idx, unsigned int target_fp) {
    if (idx < 0 || idx >= VV3_MASK_SLOTS || g_vv3_mask[idx] == 0)
        return 0;
    return !vv3_mask_current_slot_writable(idx, target_fp)
        && g_vv3_mask_fp[idx] != target_fp;
}

/* The caller must have prepared the active save slot.  Zero does not claim
   fingerprint ownership and may clear stale/current target state; the apply
   helper preserves a foreign live-owned current slot.  A nonzero bind requires
   the addressed record to be the sole live owner. */
static int vv3_mask_can_set_prepared(const void *record, int mask) {
    const unsigned char *rec = (const unsigned char *)record;
    unsigned int fpv;
    int idx = vv3_mask_index(record);
    if (idx < 0) return 0;
    fpv = vv3_mask_fingerprint(rec);
    /* An individual clear cannot name one member of a collision group.  The
       village-wide shadow transaction owns the only group clear/bind path. */
    if (mask == 0)
        return !vv3_mask_has_duplicate_live_fingerprint(fpv);
    if (vv3_mask_unique_live_index(fpv) != idx) return 0;
    return vv3_mask_current_slot_writable(idx, fpv);
}

/* ---- Sidecar persistence (a file next to the save; never the save itself) ----
   The table is DLL memory, so without this masks would reset on quit.  Each
   active save owns its own sidecar, Documents\LDW\<exe-basename>\
   vvfp_masks_<slot>.dat, holding the mask + fingerprint arrays.  Written on
   every chooser commit (write-through) and read once after the executable
   publishes that save's slot.  All file I/O is in these normal functions,
   never DllMain (loader-lock safe).  A missing/short file leaves the table
   zeroed.  There is intentionally no legacy unsuffixed-file migration. */
#define VV3_MASK_MAGIC 0x334B534Du   /* "MSK3" little-endian */
static int g_vv3_mask_loaded;
static int g_vv3_mask_slot;

static void vv3_mask_clear_tables(void) {
    ZeroMemory(g_vv3_mask, sizeof(g_vv3_mask));
    ZeroMemory(g_vv3_mask_fp, sizeof(g_vv3_mask_fp));
    ZeroMemory(g_vv3_running_before, sizeof(g_vv3_running_before));
    ZeroMemory(g_vv3_running_mask_before, sizeof(g_vv3_running_mask_before));
    g_vv3_running_capture = 0;
}

/* Sidecars are user-writable files, so never publish an unchecked byte as an
   atlas row.  The current MSK3 format is magic + mask[256] + fingerprint[256]
   (the historical unslotted and current per-save files use the same payload),
   and the fingerprint is only meaningful when its paired mask is 1..5.  Drop
   both fields for every invalid mask so reads fail closed to "no mask" and a
   bogus value can never reach (mask - 1) * 8 atlas indexing. */
static void vv3_mask_sanitize_loaded_table(void) {
    int i;
    for (i = 0; i < VV3_MASK_SLOTS; ++i) {
        if (g_vv3_mask[i] > VV3_MASK_MAX) {
            g_vv3_mask[i] = 0;
            g_vv3_mask_fp[i] = 0;
        }
    }
}

static int vv3_mask_captured_slot(void) {
    int slot = *(int *)(UINT_PTR)VV3_MASK_SLOT_PTR;
    return (slot >= 1 && slot <= 5) ? slot : 0;
}

static int vv3_mask_sidecar_path(char *out, int cap, int slot) {
    char docs[MAX_PATH], exe[MAX_PATH], dir[MAX_PATH];
    char *base, *dot, *p;
    DWORD n;
    if (slot < 1 || slot > 5) return 0;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) return 0;
    n = GetModuleFileNameA(NULL, exe, MAX_PATH);           /* the GAME exe */
    if (n == 0 || n >= MAX_PATH) return 0;
    base = exe;
    for (p = exe; *p; ++p) if (*p == '\\' || *p == '/') base = p + 1;
    dot = NULL;
    for (p = base; *p; ++p) if (*p == '.') dot = p;
    if (dot) *dot = '\0';                                  /* strip extension */
    if (lstrlenA(docs) + lstrlenA(base) + 40 >= cap) return 0;
    wsprintfA(dir, "%s\\LDW", docs);                       CreateDirectoryA(dir, NULL);
    wsprintfA(dir, "%s\\LDW\\%s", docs, base);             CreateDirectoryA(dir, NULL);
    wsprintfA(out, "%s\\LDW\\%s\\vvfp_masks_%d.dat", docs, base, slot);
    return 1;
}

static int vv3_mask_write_sidecar_tables(const unsigned char *mask_table,
                                         const unsigned int *fp_table) {
    char path[MAX_PATH];
    char tmp[MAX_PATH];
    HANDLE h;
    DWORD w = 0;
    unsigned int magic = VV3_MASK_MAGIC;
    BOOL ok = TRUE;
    if (g_vv3_mask_slot <= 0) return 0;
    if (!vv3_mask_sidecar_path(path, sizeof(path), g_vv3_mask_slot)) return 0;
    /* Keep the published sidecar intact until the complete payload is durable.
       The temporary suffix has its own MAX_PATH budget because the final path
       may be valid while its publication path is not. */
    if (lstrlenA(path) + (int)sizeof(".tmp") > MAX_PATH) return 0;
    lstrcpyA(tmp, path);
    lstrcatA(tmp, ".tmp");
    h = CreateFileA(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return 0;
    if (!WriteFile(h, &magic, sizeof(magic), &w, NULL) ||
        w != sizeof(magic)) {
        ok = FALSE;
    }
    if (ok && (!WriteFile(h, mask_table, sizeof(g_vv3_mask), &w, NULL) ||
               w != sizeof(g_vv3_mask))) {
        ok = FALSE;
    }
    if (ok && (!WriteFile(h, fp_table, sizeof(g_vv3_mask_fp), &w, NULL) ||
               w != sizeof(g_vv3_mask_fp))) {
        ok = FALSE;
    }
    if (ok && !FlushFileBuffers(h)) {
        ok = FALSE;
    }
    if (!CloseHandle(h)) {
        ok = FALSE;
    }
    if (!ok) {
        /* Only remove the exact temporary path; the previous final remains. */
        DeleteFileA(tmp);
        return 0;
    }
    if (!MoveFileExA(tmp, path,
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileA(tmp);
        return 0;
    }
    return 1;
}

static int vv3_mask_write_sidecar(void) {
    return vv3_mask_write_sidecar_tables(g_vv3_mask, g_vv3_mask_fp);
}

static void vv3_mask_read_sidecar(int slot) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD r = 0, mask_r = 0, fp_r = 0;
    unsigned int magic = 0;
    g_vv3_mask_loaded = 1;                                 /* one-shot; set first */
    vv3_mask_clear_tables();
    if (!vv3_mask_sidecar_path(path, sizeof(path), slot)) return;
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    if (ReadFile(h, &magic, sizeof(magic), &r, NULL) && r == sizeof(magic)
        && magic == VV3_MASK_MAGIC) {
        if (!ReadFile(h, g_vv3_mask, sizeof(g_vv3_mask), &mask_r, NULL)
            || mask_r != sizeof(g_vv3_mask)
            || !ReadFile(h, g_vv3_mask_fp, sizeof(g_vv3_mask_fp), &fp_r, NULL)
            || fp_r != sizeof(g_vv3_mask_fp)) {
            vv3_mask_clear_tables();
        } else {
            vv3_mask_sanitize_loaded_table();
        }
    }
    CloseHandle(h);
}

/* Observe the active save number before every read/write.  On a save switch,
   discard the previous table and reload only the new save's sidecar.  Save 0
   (including the interval before the stock builder first captures a slot) is
   fail-closed and cannot expose or persist stale mask data. */
static int vv3_mask_prepare_slot(void) {
    int slot = vv3_mask_captured_slot();
    if (slot <= 0) {
        if (g_vv3_mask_slot != 0) {
            vv3_mask_clear_tables();
            g_vv3_mask_slot = 0;
        }
        g_vv3_mask_loaded = 1;
        return 0;
    }
    if (g_vv3_mask_slot != slot) {
        vv3_mask_clear_tables();
        g_vv3_mask_slot = slot;
        g_vv3_mask_loaded = 0;
    }
    if (!g_vv3_mask_loaded) vv3_mask_read_sidecar(slot);
    return 1;
}

/* Resolve a captured live preimage only when one record owned it at the exact
   before-boundary.  The after-boundary runs immediately around patch-owned
   preference stores, so the returned slot is the record to fingerprint again. */
static int vv3_running_unique_live_preimage_index(unsigned int fp, int slots) {
    int found = -1;
    int i;
    if (fp == 0) return -1;
    for (i = 0; i < slots; ++i) {
        if (g_vv3_running_before[i] != fp) continue;
        if (found >= 0) return -1;
        found = i;
    }
    return found;
}

/* Use the immutable before-snapshot rather than the table being retagged, so
   one entry's new fingerprint cannot change another entry's uniqueness result
   partway through the transaction. */
static int vv3_running_unique_stored_preimage_index(unsigned int fp) {
    int found = -1;
    int i;
    if (fp == 0) return -1;
    for (i = 0; i < VV3_MASK_SLOTS; ++i) {
        if (g_vv3_running_mask_before[i] != fp) continue;
        if (found >= 0) return -1;
        found = i;
    }
    return found;
}

/* Bracket every VV3 Grant Running preference write owned by this composition.
   `after == 0` captures both the live fingerprints and the stored-mask
   fingerprints.  `after != 0` retags an entry only when its old fingerprint
   had exactly one live owner and exactly one stored owner in that immutable
   preimage.  This preserves unique slot-shift recovery while a collision fails
   closed instead of cross-tagging masks.  No unproved name/ID field is
   substituted, and no villager record byte is touched by this refresh. */
__declspec(dllexport) void __stdcall VV3RunningMaskBoundary(int after) {
    unsigned char *rec = (unsigned char *)(UINT_PTR)VV3_REC_BASE;
    int i, j, slots = *(int *)(UINT_PTR)VV3_SLOTS_PTR;
    if (slots < 0) slots = 0;
    if (slots > VV3_MASK_SLOTS) slots = VV3_MASK_SLOTS;
    if (!vv3_mask_prepare_slot()) {
        g_vv3_running_capture = 0;
        return;
    }
    if (!after) {
        for (i = 0; i < slots; ++i, rec += VV3_STRIDE) {
            if (rec[VV3_ACTIVE] != 0 && *(int *)(rec + VV3_HEALTH) > 0)
                g_vv3_running_before[i] = vv3_mask_fingerprint(rec);
            else
                g_vv3_running_before[i] = 0;
        }
        for (; i < VV3_MASK_SLOTS; ++i) g_vv3_running_before[i] = 0;
        for (i = 0; i < VV3_MASK_SLOTS; ++i)
            g_vv3_running_mask_before[i] =
                g_vv3_mask[i] ? g_vv3_mask_fp[i] : 0u;
        g_vv3_running_capture = 1;
        return;
    }
    if (!g_vv3_running_capture) return;
    for (i = 0; i < VV3_MASK_SLOTS; ++i) {
        unsigned int old_fp = g_vv3_running_mask_before[i];
        if (g_vv3_mask[i] == 0 || old_fp == 0 || g_vv3_mask_fp[i] != old_fp)
            continue;
        if (vv3_running_unique_stored_preimage_index(old_fp) != i) continue;
        j = vv3_running_unique_live_preimage_index(old_fp, slots);
        if (j < 0) continue;
        rec = (unsigned char *)(UINT_PTR)(VV3_REC_BASE + j * VV3_STRIDE);
        if (rec[VV3_ACTIVE] != 0 && *(int *)(rec + VV3_HEALTH) > 0)
            g_vv3_mask_fp[i] = vv3_mask_fingerprint(rec);
    }
    g_vv3_running_capture = 0;
    vv3_mask_write_sidecar();
}

/* Render hook: mask (1..5) to draw over this villager's head, or 0 for none /
   empty slot / a reused slot whose fingerprint no longer matches. */
__declspec(dllexport) int __stdcall VV3_GetMaskForRecord(void *record) {
    const unsigned char *rec = (const unsigned char *)record;
    unsigned int fpv;
    int idx, live_idx, stored_idx, group_value;
    if (record == NULL) return 0;
    if (!vv3_mask_prepare_slot()) return 0;
    idx = vv3_mask_index(record);
    if (idx < 0) return 0;
    if (rec[VV3_ACTIVE] == 0 || *(const int *)(rec + VV3_HEALTH) <= 0)
        return 0;
    fpv = vv3_mask_fingerprint(rec);
    live_idx = vv3_mask_unique_live_index(fpv);
    if (live_idx != idx) {
        /* The only duplicate exception is the count-matched, same-value group
           representation emitted atomically by Change Appearance for All. */
        group_value = vv3_mask_stored_group_value(fpv);
        return group_value;
    }
    /* A unique live owner still requires exactly one stored owner before the
       same-slot or slot-shift path may return a value. */
    stored_idx = vv3_mask_unique_stored_index(fpv);
    if (stored_idx < 0) return 0;
    /* FAST PATH: villager still at its sole stored slot (common within a session). */
    if (stored_idx == idx) {
        return g_vv3_mask[idx];
    }
    /* SLOT-SHIFT RECOVERY: villager slot indices are NOT stable -- deaths, births and
       save reloads renumber them, so the per-index table goes stale and the fast-path
       fingerprint check fails for almost everyone (observed: ~97/100 villagers read as
       no-mask after a reload).  The mask is stored WITH the villager's birth-fixed genetic
       fingerprint, so recover it by SEARCHING the table for that fingerprint regardless of
       the current slot -- the mask follows the VILLAGER, not the index.  This is what makes
       saved masks reappear after a reload.  Recovery is allowed only after the
        identity gates above.  (Fingerprint = gender + 3 Likes + 3 Dislikes;
       the owned Grant Running mutation refreshes unique identities at its exact
       write boundary.) */
    return g_vv3_mask[stored_idx];
}

static int g_vv3_mask_last_persist_failed;

/* Apply an individual mask-table change without touching a villager record.
   This path retains the unique-owner and shifted-copy gates; the village-wide
   group transaction uses its separate, fully preflighted shadow table.  Build
   and durably publish an individual shadow before changing the live table so a
   persistence failure cannot report success or permit the native charge. */
static int vv3_mask_apply_prepared(const void *record, int mask, int persist) {
    const unsigned char *rec = (const unsigned char *)record;
    unsigned char shadow_mask[VV3_MASK_SLOTS];
    unsigned int shadow_fp[VV3_MASK_SLOTS];
    unsigned int fpv;
    int idx = vv3_mask_index(record);
    int i, live_idx, current_foreign_live;
    g_vv3_mask_last_persist_failed = 0;
    if (!vv3_mask_prepare_slot()) return 0;
    if (idx < 0) return 0;
    if (mask < 0 || mask > VV3_MASK_MAX) mask = 0;
    fpv = vv3_mask_fingerprint(rec);
    current_foreign_live = vv3_mask_current_slot_foreign_live(idx, fpv);
    if (mask != 0 && current_foreign_live) return 0;
    if (!vv3_mask_can_set_prepared(record, mask)) return 0;
    CopyMemory(shadow_mask, g_vv3_mask, sizeof(g_vv3_mask));
    CopyMemory(shadow_fp, g_vv3_mask_fp, sizeof(g_vv3_mask_fp));
    live_idx = vv3_mask_unique_live_index(fpv);
    if (live_idx == idx) {
        for (i = 0; i < VV3_MASK_SLOTS; ++i) {
            if (i != idx && shadow_mask[i] != 0 && shadow_fp[i] == fpv) {
                shadow_mask[i] = 0;
                shadow_fp[i] = 0;
            }
        }
    }
    if (!(mask == 0 && current_foreign_live)) {
        shadow_mask[idx] = (unsigned char)mask;
        shadow_fp[idx] = mask ? fpv : 0u;
    }
    if (persist && !vv3_mask_write_sidecar_tables(shadow_mask, shadow_fp)) {
        g_vv3_mask_last_persist_failed = 1;
        return 0;
    }
    CopyMemory(g_vv3_mask, shadow_mask, sizeof(g_vv3_mask));
    CopyMemory(g_vv3_mask_fp, shadow_fp, sizeof(g_vv3_mask_fp));
    return 1;
}

/* Chooser commit: bind the chosen mask (0..5) to this villager.  A nonzero mask
   requires the supplied record to be the one unique active/living owner of its
   fingerprint; an inactive/stale pointer therefore cannot seed a mask that a
   different live villager later recovers.  An explicit zero may clear a unique
   owner's addressed stale slot, but cannot target one member of a collision
   group.  When the live owner is unique, clear every
   older shifted copy of its fingerprint before writing the current slot, so an
   explicit chooser commit also resolves stored-table duplication.  Never writes
   the record.  Returns 1 only when the requested table commit is accepted. */
__declspec(dllexport) int __stdcall VV3_SetMaskForRecord(void *record, int mask) {
    return vv3_mask_apply_prepared(record, mask, 1);
}

/* ---- Mask draw (called from the exe Detail head-draw hook) ----
   The exe cave draws the villager head normally, then calls this once with the
   record, the sprite/draw object ([record+0x1F7C]), and a pointer to the 7 head-
   draw args it just used.  We look up the villager's mask (fingerprint-guarded
   DLL table), and if set, draw the mask cell ON TOP from the dedicated atlas via
   the game's own draw routine 0x004093A0 -- reusing the head's x / frame / scale,
   with the atlas swapped to the mask atlas, the row set to (mask-1), and the y
   lifted so the tall masks seat on the head.  Doing the draw here keeps the exe
   cave tiny (just "draw head, call this") and all the tunable mask logic in C.

   Head-draw args (as the exe pushed them, param1..param7):
     args[0]=head atlas  args[1]=x  args[2]=y  args[3]=head row
     args[4]=frame/param5  args[5]=scaled-Y  args[6]=flag(1)
   0x004093A0 is __thiscall (ecx = *(sprite_obj)), 7 stack args, callee-cleaned
   (ret 0x1C).  A missing atlas / no-mask / bad record degrades to drawing nothing
   -- never a crash.  Writes NO villager state. */
#define VV3_MASK_LIFT_MUL 18          /* y_mask = y - ((scaledY*MUL)>>7).  With the
                                         stock Details scaledY=0xC8 this candidate moves
                                         the adult mask down 25px relative to multiplier
                                         34 (200*18>>7 = 28; 200*34>>7 = 53).  Visual
                                         placement remains pending player acceptance. */
#define VV3_MASK_DRAW_FN  0x004093A0u
/* Player-tuned Details registration, on the same pattern VV1 and VV2 use, so
   all three games expose one reviewable number per axis.  Screen X grows
   rightward and screen Y grows downward, so a negative value seats the mask
   further left and higher on the portrait.  The X value carries the earlier
   art-registration correction (-8) plus a further 3 px left; the Y nudge is
   applied on top of the scale-aware lift so the lift stays scale-correct.
   The Y value was -5 and is now -1: a reviewed 4 px DOWNWARD move, requested
   after looking at the portrait.  This is INDEPENDENT of the village-view
   registration below -- the two screens draw through different engine
   functions in different coordinate spaces and must be tuned separately. */
#define VV3_DETAILS_MASK_X_NUDGE_PX (-11)
#define VV3_DETAILS_MASK_Y_NUDGE_PX (-1)

__declspec(dllexport) void __stdcall VV3DrawMaskOnHead(
    void *record, void *sprite_obj, const int *args)
{
    int mask = VV3_GetMaskForRecord(record);
    void *atlas, *draw_this;
    int row, ymask, x, scaledY, frame, flag;
    if (mask <= 0 || sprite_obj == NULL || args == NULL) {
        return;
    }
    atlas = VV3GetMaskAtlas();
    if (atlas == NULL) {
        return;
    }
    /* The VV2 portrait registration is face-centered; VV3's mask atlas has a
       rightward art registration at this scaled head tuple.  Keep the
       authoritative head x and apply only the reviewed visual correction. */
    x       = args[1] + VV3_DETAILS_MASK_X_NUDGE_PX;
    frame   = args[4];
    scaledY = args[5];
    flag    = args[6];
    row     = mask - 1;
    ymask   = args[2] - ((scaledY * VV3_MASK_LIFT_MUL) >> 7)
              + VV3_DETAILS_MASK_Y_NUDGE_PX;
    draw_this = *(void **)sprite_obj;   /* the game's own "mov ecx,[ecx]" deref */
    __asm {
        push flag
        push scaledY
        push frame
        push row
        push ymask
        push x
        push atlas
        mov  ecx, draw_this
        mov  eax, VV3_MASK_DRAW_FN
        call eax                        /* draws the mask cell; ret 0x1C */
    }
}

/* ---- World / village mask draw (inline at the stock head painter) ---------------
   The stock appearance head call at 0x460C7F supplies six authoritative arguments
   to 0x42E5E0: atlas, x, y, head row, facing, scale.  The patched cave replays that
   call unchanged, then invokes VV3WorldMaskDrawAt while the original arguments are
   still present.  This callback changes only atlas and row and calls 0x42E5E0 again,
   so camera, coordinates, facing, scale, and alpha remain stock.  No post-handler
   draw or action reconstruction is used.  The stock held (`+0xF12`) branch rejoins this same
   body/head sequence, so held masks inherit the true tuple; cursor ownership and
   visual follow remain player-trace gates. */
#define VV3_WORLD_MGR      0x0058F6F8u   /* the world appearance manager object   */
#define VV3_WORLD_POS_FN   0x00455EF0u   /* __thiscall(record, &out{x,y}) -> base   */
#define VV3_WORLD_HEAD_DRAW_FN 0x0042E5E0u /* __thiscall(mgr, atlas, x, y, row, facing, scale) */
/* WORLD-path draw log, so the running game can say WHICH hook paints a given mask instead of
   me inferring it.  [0]=villager index [1]=anim [2]=facing [3]=x [4]=y [5]=scale bits
   [6]=mask colour [7]=draw count.  Published at 0x6E003C. */
int g_vv3_worlddbg[8] = {0};
/* Targeted log of the CHIEF-colour (mask==5) world draw. A player trace may correlate this
   with a pickup, but this diagnostic does not identify grab state. [0]=index [1]=anim
   [2]=facing [3]=x [4]=y [5]=record state +0xF1C [6]=villager world x [7]=count.
   Published at 0x6E0040. */
int g_vv3_chiefdbg[8] = {0};

static int vv3_world_record_index(void *record)
{
    UINT_PTR p = (UINT_PTR)record;
    UINT_PTR base = (UINT_PTR)VV3_REC_BASE;
    UINT_PTR delta;
    if (p < base) return -1;
    delta = p - base;
    if ((delta % VV3_STRIDE) != 0 || (delta / VV3_STRIDE) >= 150) return -1;
    return (int)(delta / VV3_STRIDE);
}

/* ---- Village-view mask registration --------------------------------------
   Screen X grows rightward and screen Y grows downward, so both negatives seat
   the mask further left and higher on the villager.  Tuned from a village
   screenshot in which the masks floated low and to the right of the faces.

   These are deliberately SEPARATE numbers from VV3_DETAILS_MASK_*_NUDGE_PX.
   The Details portrait draws through 0x004093A0 with an INTEGER scaled-Y; the
   village draws through 0x0042E5E0, whose sixth argument is an IEEE-754 FLOAT.
   Different function, different coordinate space -- retuning one screen must
   never move the other. */
#define VV3_WORLD_MASK_X_NUDGE_PX (-10)
#define VV3_WORLD_MASK_Y_NUDGE_PX (-33)

/* An extra horizontal nudge for the right-facing frames only, on top of the
   nudge above that every frame gets.  The right-facing mask art sits further
   into its cell than the left-facing art does, so one shared X nudge cannot
   centre both.

   Indexed by the villager's 8-way facing -- the low three bits of the head
   draw's fifth argument, which is also the column the mask atlas is sampled
   from.  Columns 4-6 are the front-facing poses (a full symmetric face) and
   0-3 are mirrored profiles; of those, 0 and 1 are the pair whose art is
   biased toward the right of its 65px cell, which makes them the right-facing
   ones.  Facing 7 is very nearly centred and is left alone.

   A table rather than a condition so that retuning any single direction is a
   one-number change and cannot disturb the others. */
static const int VV3_WORLD_MASK_X_NUDGE_BY_FACING[8] = {
    -4, -4, 0, 0, 0, 0, 0, 0
};

/* The sixth village head-draw argument is a float, not an int.  0x0042E5E0
   does `fild [arg]; fmul [cam+0x300c]` for the two coordinates but
   `fild [cam+0x3010]; fmul [esp+arg5]` for the size -- arg5 is consumed as a
   float directly, so it must be reinterpreted, never used as an integer.

   The stock caller pins its range exactly.  At 0x00460913 the renderer
   compares the villager's age (+0xDC4) with 0x118 and then either stores
   0x3F800000 -- literally 1.0f -- for an adult (0x0046093A), or computes
   (age * 1/14 + 80) * 0.01 for a child (0x0046091E..0x00460934), which runs
   from 0.80 at birth up to 1.00 at adulthood.

   So the nudges above are written for a full-size adult and multiplied by this
   live scale.  That is what "scale with height / child size" means here: the
   adult registration is 33 px up and 10 px left (14 on the two right-facing
   frames, which add VV3_WORLD_MASK_X_NUDGE_BY_FACING), so a newborn at 0.80
   moves 26 px up and 8 px left -- 11 px left when right-facing.

   The coordinates themselves are plain screen pixels.  Every village caller of
   the camera setter 0x0042E250 (0x0042E49C, 0x00464BF1, 0x0046A1DA,
   0x0046A843) pushes 0x3F800000 for the zoom stored at +0x300c, so the
   coordinate fmul is by 1.0 and one unit of args[1]/args[2] is one pixel. */
static float vv3_world_scale(int raw)
{
    float scale;
    memcpy(&scale, &raw, sizeof(scale));
    /* Written as negated comparisons so a NaN -- which fails every ordered
       test -- also lands on the fallback.  A garbage scale must degrade to the
       stock adult 1.0, never fling the mask off the villager. */
    if (!(scale > 0.05f) || !(scale < 8.0f)) {
        return 1.0f;
    }
    return scale;
}

/* Round half away from zero, so a nudge never collapses to 0 by truncation. */
static int vv3_scaled_nudge(int px, float scale)
{
    float value = (float)px * scale;
    return (int)(value >= 0.0f ? value + 0.5f : value - 0.5f);
}

/* Inline world/head mask draw.  This callback is invoked immediately after the
   stock 0x42E5E0 call at 0x460C7F, while its untouched six arguments remain on
   the stack.  The mask reuses those exact x/y/facing/scale values and changes
   only the atlas and row.  No post-handler reconstruction or action hook exists. */
__declspec(dllexport) void __stdcall VV3WorldMaskDrawAt(void *record, int *args)
{
    void *atlas;
    int mask, index, facing, mask_args[6], i;
    int arg0, arg1, arg2, arg3, arg4, arg5;
    float scale;
    int wp[2];
    if (record == NULL || args == NULL) return;
    mask = VV3_GetMaskForRecord(record);
    if (mask <= 0) return;
    atlas = VV3GetMaskAtlas();
    if (atlas == NULL) return;
    for (i = 0; i < 6; ++i) mask_args[i] = args[i];
    mask_args[0] = (int)(UINT_PTR)atlas;
    mask_args[3] = mask - 1;
    facing = mask_args[4] & 7;
    /* Select the mask COLUMN explicitly, never reuse the head's frame index --
       docs/head-mask-rendering.md Part 6 rule 3.  VV1 may replay args[4]
       directly because its mask atlas shares its head atlas' column layout;
       VV3's does not.  heathen_masks.png is 520x725 = 8 facing columns x 5
       colour rows of 65x145, so the column is the villager's 8-way facing,
       while the head's args[4] is a composite whose facing is only the low
       three bits -- which is exactly why `facing` is masked out below.
       Passing the raw composite indexed past column 7 and drew the wrong
       cell.  When args[4] already holds a bare facing this is a no-op. */
    mask_args[4] = facing;
    /* Seat the mask on the face.  Applied BEFORE the debug capture below so
       g_vv3_worlddbg reports the coordinates actually drawn, and before the
       arg0..arg5 copy so the renderer receives them. */
    scale = vv3_world_scale(mask_args[5]);
    mask_args[1] += vv3_scaled_nudge(
        VV3_WORLD_MASK_X_NUDGE_PX + VV3_WORLD_MASK_X_NUDGE_BY_FACING[facing & 7],
        scale);
    mask_args[2] += vv3_scaled_nudge(VV3_WORLD_MASK_Y_NUDGE_PX, scale);
    index = vv3_world_record_index(record);
    g_vv3_worlddbg[0] = index;
    g_vv3_worlddbg[1] = *(int *)((unsigned char *)record + 0xF20);
    g_vv3_worlddbg[2] = facing;
    g_vv3_worlddbg[3] = mask_args[1];
    g_vv3_worlddbg[4] = mask_args[2];
    g_vv3_worlddbg[5] = mask_args[5];
    g_vv3_worlddbg[6] = mask | (*(int *)((unsigned char *)record + 0xF1C) << 8);
    g_vv3_worlddbg[7]++;
    if (mask == 5) {
        __asm {
            lea  eax, wp
            push eax
            mov  ecx, record
            mov  edx, VV3_WORLD_POS_FN
            call edx
        }
        g_vv3_chiefdbg[0] = index;
        g_vv3_chiefdbg[1] = *(int *)((unsigned char *)record + 0xF20);
        g_vv3_chiefdbg[2] = facing;
        g_vv3_chiefdbg[3] = mask_args[1];
        g_vv3_chiefdbg[4] = mask_args[2];
        g_vv3_chiefdbg[5] = *(int *)((unsigned char *)record + 0xF1C);
        g_vv3_chiefdbg[6] = wp[0];
        g_vv3_chiefdbg[7]++;
    }
    /* MSVC inline assembly treats `arr[N]` as a BYTE displacement, not an
       element index.  `push mask_args[4]` therefore pushed base+4 -- element 1,
       the x coordinate -- and four of the six pushes were UNALIGNED reads
       straddling two elements, so the renderer received garbage for x, y, row,
       column and scale (only element 0, the atlas, was right by coincidence).
       The shipped DLL showed it plainly: the six pushes came out at
       [ebp-0x24]..[ebp-0x1f], one byte apart instead of four.
       Copying the tuple into scalars first removes the ambiguity entirely --
       do NOT fold these back into indexed pushes. */
    arg0 = mask_args[0];
    arg1 = mask_args[1];
    arg2 = mask_args[2];
    arg3 = mask_args[3];
    arg4 = mask_args[4];
    arg5 = mask_args[5];
    __asm {
        push arg5
        push arg4
        push arg3
        push arg2
        push arg1
        push arg0
        mov  ecx, VV3_WORLD_MGR
        mov  edx, VV3_WORLD_HEAD_DRAW_FN
        call edx                     /* 0x42E5E0 -> 0x409FB0, exact tuple */
    }
}

/* ================= Change Appearance for All (village-wide) ================
   Mirrors VV2's design: EVERYTHING is DLL-side, so the exe stays a thin one-call
   bridge (low risk).  vv3_apply_for_all iterates the villager record array and
   applies the dialog's choices: Head/Body are INDEPENDENT per-sex (a >=0 value
   overwrites +0xDF0/+0xDF4 for that sex; -1 = leave alone), and the MASK is one
   mutually-exclusive choice (mask_mode) committed through a preflighted shadow
   of the fingerprint-guarded table + sidecar -- never the record/save.
     mask_mode: 0 = OFF (use the per-sex mask cyclers mask_m/mask_f)
                1 = VV5-style   2 = Random   3 = Equal
                4..9 = a single mask for everyone (4=None .. 9=Chief -> byte 0..5) */
#define VV3_HEAD_OFF 0xDF0
#define VV3_BODY_OFF 0xDF4

static unsigned int caf_rng;                 /* xorshift32, seeded from GetTickCount */
/* Why a mask batch refused to apply.  Four unrelated conditions used to share
   one "could not be safely matched to unique villagers" message, which made a
   failure impossible to act on: a village with no captured save slot reported a
   fingerprint problem it did not have.  Each cause now names itself.  Zero is
   "no mask failure"; the values are only ever read by the result message. */
#define VV3_CAF_MASK_OK          0
#define VV3_CAF_MASK_NO_SLOT     1   /* no active numbered save slot available */
#define VV3_CAF_MASK_BAD_MODE    2   /* selector emitted an unsupported mode */
#define VV3_CAF_MASK_AMBIGUOUS   3   /* villagers share a fingerprint group */
#define VV3_CAF_MASK_NO_ROOM     4   /* sidecar shadow could not seat the plan */
static int g_vv3_caf_mask_fail;
static int g_vv3_caf_mask_persist_failed;
static unsigned int caf_rand(void) {
    unsigned int x = caf_rng ? caf_rng : (caf_rng = GetTickCount() | 1u);
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    caf_rng = x;
    return x;
}

static int vv3_mask_plan_has_selected_fp(unsigned int target_fp,
                                         const unsigned int *plan_fp,
                                         const int *selected, int n) {
    int i;
    for (i = 0; i < n; ++i)
        if (selected[i] && plan_fp[i] == target_fp) return 1;
    return 0;
}

/* The village-wide dialog covers every active/living record.  Turn each raw
   per-record dynamic result into one result per collision group, then prove
   that the plan contains every live owner.  Fixed/per-sex modes must already
   agree naturally (gender is part of the fingerprint); a hash collision that
   crosses selections therefore still fails closed.  VV5 Chief takes priority
   when the Chief shares a fingerprint with another planned villager. */
static int vv3_mask_make_plan_group_coherent(const unsigned int *plan_fp,
                                              const int *selected,
                                              int *desired, int n,
                                              int mask_mode) {
    int i, j, count, canonical, seen;
    for (i = 0; i < n; ++i) {
        seen = 0;
        for (j = 0; j < i; ++j)
            if (plan_fp[j] == plan_fp[i]) { seen = 1; break; }
        if (seen) continue;
        count = 0;
        canonical = desired[i];
        for (j = i; j < n; ++j) {
            if (plan_fp[j] != plan_fp[i]) continue;
            ++count;
            if (selected[j] != selected[i]) return 0;
            if (!selected[i]) continue;
            if (desired[j] < 0 || desired[j] > VV3_MASK_MAX) return 0;
            if (mask_mode >= 1 && mask_mode <= 3) {
                if (mask_mode == 1 && desired[j] == VV3_MASK_MAX)
                    canonical = VV3_MASK_MAX;
            } else if (desired[j] != canonical) {
                return 0;
            }
        }
        if (count != vv3_mask_live_fingerprint_count(plan_fp[i])) return 0;
        if (selected[i] && mask_mode >= 1 && mask_mode <= 3)
            for (j = i; j < n; ++j)
                if (plan_fp[j] == plan_fp[i]) desired[j] = canonical;
    }
    return 1;
}

static int vv3_mask_shadow_slot_available(unsigned char mask, unsigned int fp) {
    if (mask == 0 || fp == 0) return 1;
    return vv3_mask_live_fingerprint_count(fp) == 0;
}

/* Build the complete sidecar result in scratch memory.  Selected fingerprints
   are removed first, while entries owned by an unselected live group are never
   overwritten.  A nonzero selected group receives exactly one identical copy
   per live owner, which is the proof consumed by the guarded render getter.
   Nothing in the live table changes unless this entire allocation succeeds. */
static int vv3_mask_build_batch_shadow(const int *idx,
                                        const unsigned int *plan_fp,
                                        const int *selected,
                                        const int *desired, int n,
                                        unsigned char *out_mask,
                                        unsigned int *out_fp) {
    int i, j, pos, seen, needed, placed;
    CopyMemory(out_mask, g_vv3_mask, sizeof(g_vv3_mask));
    CopyMemory(out_fp, g_vv3_mask_fp, sizeof(g_vv3_mask_fp));

    for (pos = 0; pos < VV3_MASK_SLOTS; ++pos) {
        if (out_fp[pos] != 0
            && vv3_mask_plan_has_selected_fp(out_fp[pos], plan_fp, selected, n)) {
            out_mask[pos] = 0;
            out_fp[pos] = 0;
        }
    }

    for (i = 0; i < n; ++i) {
        if (!selected[i]) continue;
        seen = 0;
        for (j = 0; j < i; ++j)
            if (selected[j] && plan_fp[j] == plan_fp[i]) { seen = 1; break; }
        if (seen || desired[i] == 0) continue;
        needed = vv3_mask_live_fingerprint_count(plan_fp[i]);
        placed = 0;

        /* Prefer the group's current record indices, but never evict a slot
           whose fingerprint still belongs to an unselected live owner. */
        for (j = i; j < n && placed < needed; ++j) {
            if (!selected[j] || plan_fp[j] != plan_fp[i]) continue;
            pos = idx[j];
            if (!vv3_mask_shadow_slot_available(out_mask[pos], out_fp[pos]))
                continue;
            out_mask[pos] = (unsigned char)desired[i];
            out_fp[pos] = plan_fp[i];
            ++placed;
        }
        for (pos = 0; pos < VV3_MASK_SLOTS && placed < needed; ++pos) {
            if (!vv3_mask_shadow_slot_available(out_mask[pos], out_fp[pos]))
                continue;
            out_mask[pos] = (unsigned char)desired[i];
            out_fp[pos] = plan_fp[i];
            ++placed;
        }
        if (placed != needed) return 0;
    }
    return 1;
}

/* Head/body variant counts and the generated hair-colour buckets, declared
   here rather than beside the Change Appearance cyclers further down
   because vv3_apply_for_all plans the village-wide overrides and needs
   both before that point. */
#define VV3_HEAD_COUNT 30
#define VV3_BODY_COUNT 30
#include "vv3_head_buckets.h"

static int vv3_apply_for_all(int head_m, int body_m, int mask_m,
                             int head_f, int body_f, int mask_f, int mask_mode,
                             int head_mode, int body_mode) {
    unsigned char *rec = (unsigned char *)(UINT_PTR)VV3_REC_BASE;
    int slots = *(int *)(UINT_PTR)VV3_SLOTS_PTR;
    int idx[256], sex[256], order[256], desired_mask[256], mask_changed[256];
    int plan_head[256], plan_body[256];
    unsigned int head_rng = GetTickCount() ^ 0x5BD1E995u;
    int mask_selected[256];
    unsigned int plan_fp[256], shadow_fp[256];
    unsigned char shadow_mask[256];
    int n = 0, chief = -1, affected = 0, mask_changed_any = 0, i, s;
    int mask_requested = (mask_mode != 0 || mask_m >= 0 || mask_f >= 0);
    g_vv3_caf_mask_fail = VV3_CAF_MASK_OK;
    g_vv3_caf_mask_persist_failed = 0;
    if (slots < 0) slots = 0;
    if (slots > 256) slots = 256;
    for (i = 0; i < slots; ++i, rec += VV3_STRIDE) {
        if (rec[VV3_ACTIVE] == 0) continue;
        if (*(int *)(rec + VV3_HEALTH) <= 0) continue;
        idx[n] = i;
        sex[n] = rec[VV3_GENDER] != 0;           /* 1 = female */
        plan_fp[n] = vv3_mask_fingerprint(rec);
        if (rec[VV3_CHIEF] != 0) chief = n;       /* the robe-wearing Tribal Chief */
        ++n;
    }
    /* Prepare the sidecar before planning; this may load but never writes it. */
    if (mask_requested) {
        if (!vv3_mask_prepare_slot()) {
            g_vv3_caf_mask_fail = VV3_CAF_MASK_NO_SLOT;
            return 0;
        }
        if (mask_mode < 0 || mask_mode > 9) {
            g_vv3_caf_mask_fail = VV3_CAF_MASK_BAD_MODE;
            return 0;
        }
        for (i = 0; i < n; ++i)
            mask_selected[i] =
                (mask_mode != 0 || (sex[i] ? mask_f : mask_m) >= 0);
    }
    /* Plan the village-wide Head/Body result BEFORE counting, for exactly the
       reason the mask plan below exists: Random and the hair buckets must be
       decided once and then reused by the apply pass, or the preflight could
       count a different random draw than the one written, and charge for it.
       Mode 0 keeps the per-sex selector, so the planned value is just it. */
    for (i = 0; i < n; ++i) {
        if (head_mode <= 0) {
            plan_head[i] = sex[i] ? head_f : head_m;
        } else if (head_mode == 1) {
            head_rng = (head_rng * 1103515245u) + 12345u;
            plan_head[i] = (int)((head_rng >> 16) % (unsigned int)VV3_HEAD_COUNT);
        } else {
            /* vv3_head_pick takes 1 = male; sex[] here is 1 = female. */
            plan_head[i] = vv3_head_pick(!sex[i], head_mode - 2, &head_rng);
        }
        if (body_mode <= 0) {
            plan_body[i] = sex[i] ? body_f : body_m;
        } else {
            head_rng = (head_rng * 1103515245u) + 12345u;
            plan_body[i] = (int)((head_rng >> 16) % (unsigned int)VV3_BODY_COUNT);
        }
    }
    /* Build the exact mask result before counting.  Random, proportional, and
       equal modes must be planned once and then reused by the apply pass;
       otherwise a preflight comparison could charge for a different random
       result than the one eventually written.  Planning only consumes DLL RNG
       state and does not touch a villager, the mask table, or the sidecar. */
    if (mask_requested) {
        if (mask_mode == 0) {
            for (i = 0; i < n; ++i)
                desired_mask[i] = sex[i] ? mask_f : mask_m;
        } else if (mask_mode >= 4) {
            for (i = 0; i < n; ++i)
                desired_mask[i] = mask_mode - 4;
        } else if (mask_mode == 2) {                /* Random (incl. None) */
            for (i = 0; i < n; ++i)
                desired_mask[i] = (int)(caf_rand() % 6u);
        } else if (mask_mode == 1) {                /* VV5-style proportions */
            static const int quota[3] = {4, 7, 10};
            static const int mval[3]  = {4, 3, 2};
            int qi, got, p = 0;
            for (i = 0; i < n; ++i) { order[i] = i; desired_mask[i] = 1; }
            for (i = n - 1; i > 0; --i) {
                int j = (int)(caf_rand() % (unsigned)(i + 1));
                int t = order[i]; order[i] = order[j]; order[j] = t;
            }
            /* Chief mask -> the robe-wearing Tribal Chief (+0xE80); if there
               is NO Tribal Chief, give the Chief mask to a random villager. */
            if (chief < 0 && n > 0) chief = (int)(caf_rand() % (unsigned)n);
            if (chief >= 0) desired_mask[chief] = 5;
            for (qi = 0; qi < 3; ++qi) {
                for (got = 0; got < quota[qi] && p < n; ) {
                    int a = order[p++];
                    if (a == chief) continue;
                    if (desired_mask[a] != 1) continue;
                    desired_mask[a] = mval[qi];
                    ++got;
                }
            }
        } else if (mask_mode == 3) {                /* Equal, balanced M/F */
            int males[256], females[256], nm = 0, nf = 0, k = 0, mi = 0, fi = 0;
            for (i = 0; i < n; ++i) {
                desired_mask[i] = 0;
                if (sex[i]) females[nf++] = i; else males[nm++] = i;
            }
            for (i = nm - 1; i > 0; --i) {
                int j = (int)(caf_rand() % (unsigned)(i + 1));
                int t = males[i]; males[i] = males[j]; males[j] = t;
            }
            for (i = nf - 1; i > 0; --i) {
                int j = (int)(caf_rand() % (unsigned)(i + 1));
                int t = females[i]; females[i] = females[j]; females[j] = t;
            }
            while (mi < nm || fi < nf) {
                if (mi < nm) desired_mask[males[mi++]] = (k++ % 5) + 1;
                if (fi < nf) desired_mask[females[fi++]] = (k++ % 5) + 1;
            }
        } else {
            /* The dialog does not emit other modes; fail closed if one is
               ever supplied so it cannot charge for an unapplied selection. */
            for (i = 0; i < n; ++i) desired_mask[i] = 0;
        }
        /* Only the completed, one-shot plan may authorize a collision group.
           Build the exact shadow sidecar before any villager or mask mutation. */
        if (!vv3_mask_make_plan_group_coherent(
                plan_fp, mask_selected, desired_mask, n, mask_mode)) {
            g_vv3_caf_mask_fail = VV3_CAF_MASK_AMBIGUOUS;
            return 0;
        }
        if (!vv3_mask_build_batch_shadow(
                idx, plan_fp, mask_selected, desired_mask, n,
                shadow_mask, shadow_fp)) {
            g_vv3_caf_mask_fail = VV3_CAF_MASK_NO_ROOM;
            return 0;
        }
    }
    /* Count each eligible record once, and only when at least one selected
       value would differ from the current value for that record.  A selected
       female field in an all-male village (or vice versa) is therefore a
       no-op, and an already-matching fixed mask is also a no-op. */
    for (i = 0; i < n; ++i) {
        unsigned char *r =
            (unsigned char *)(UINT_PTR)(VV3_REC_BASE + idx[i] * VV3_STRIDE);
        int h = plan_head[i];
        int b = plan_body[i];
        mask_changed[i] = 0;
        if (mask_requested && mask_selected[i]) {
            /* VV3_GetMaskForRecord is the guarded logical lookup: it recovers
               both a unique shifted mask and a count-matched collision-group
               mask.  None also removes every stored copy for its selected
               fingerprint through the already-built shadow table. */
            {
                int recovered_mask = VV3_GetMaskForRecord(r);
                if (desired_mask[i] == 0)
                    mask_changed[i] =
                        (recovered_mask != 0
                         || vv3_mask_has_stored_fingerprint(plan_fp[i]));
                else
                    mask_changed[i] = desired_mask[i] != recovered_mask;
            }
            if (mask_changed[i]) mask_changed_any = 1;
        }
        if ((h >= 0 && *(int *)(r + VV3_HEAD_OFF) != h)
            || (b >= 0 && *(int *)(r + VV3_BODY_OFF) != b)
            || mask_changed[i])
            ++affected;
    }
    if (affected == 0)
        return 0;
    /* Durably publish the already-proven mask result before any villager or
       live-table mutation.  A failed path/create/write/flush/close/rename
       therefore returns without changing appearance or charging tech points.
       Head/body-only batches do not need a sidecar publication. */
    if (mask_requested && mask_changed_any
        && !vv3_mask_write_sidecar_tables(shadow_mask, shadow_fp)) {
        g_vv3_caf_mask_persist_failed = 1;
        return 0;
    }
    /* Head/Body: independent per-sex, applied in the one mutation pass. */
    for (i = 0; i < n; ++i) {
        unsigned char *r = (unsigned char *)(UINT_PTR)(VV3_REC_BASE + idx[i] * VV3_STRIDE);
        int h = plan_head[i];
        int b = plan_body[i];
        if (h >= 0 && *(int *)(r + VV3_HEAD_OFF) != h) *(int *)(r + VV3_HEAD_OFF) = h;
        if (b >= 0 && *(int *)(r + VV3_BODY_OFF) != b) *(int *)(r + VV3_BODY_OFF) = b;
    }
    /* Publish the already-proven, already-persisted scratch table as one
       in-memory commit.  Individual setters are intentionally not used here. */
    if (mask_requested && mask_changed_any) {
        CopyMemory(g_vv3_mask, shadow_mask, sizeof(g_vv3_mask));
        CopyMemory(g_vv3_mask_fp, shadow_fp, sizeof(g_vv3_mask_fp));
    }
    (void)s;
    return affected;
}

#define VW_RUNNING 6
#define VW_MASTERY 7
#define VW_AGE     8

static unsigned int vw_granted, vw_already, vw_noslot, vw_removed;

static void vv3_count_village_wide(int command) {
    unsigned char *rec = (unsigned char *)(UINT_PTR)VV3_REC_BASE;
    int slots = *(int *)(UINT_PTR)VV3_SLOTS_PTR;
    int i, s;
    vw_granted = vw_already = vw_noslot = vw_removed = 0;
    for (i = 0; i < slots; ++i, rec += VV3_STRIDE) {
        if (rec[VV3_ACTIVE] == 0) continue;
        if (*(int *)(rec + VV3_HEALTH) <= 0) continue;
        if (command == VW_MASTERY) {
            int mastered = 1;
            for (s = 0; s < 5; ++s)
                if (*(int *)(rec + VV3_SKILL0 + s * 4) != 100) { mastered = 0; break; }
            if (mastered) vw_already++; else vw_granted++;
        } else if (command == VW_AGE) {
            /* Set-to-18 forces age to exactly 360 for everyone (older villagers
               are set back down), so only an already-exactly-18 villager is a
               no-change. */
            if (*(int *)(rec + VV3_AGE) == 360) vw_already++; else vw_granted++;
        } else if (command == VW_RUNNING) {
            int has_like = 0, has_free = 0, has_dislike = 0, v;
            for (s = 0; s < 3; ++s) {
                v = *(int *)(rec + VV3_LIKES + s * 4);
                if (v == VV3_RUN_PREF) has_like = 1;
                else if (v == -1) has_free = 1;
            }
            for (s = 0; s < 3; ++s)
                if (*(int *)(rec + VV3_DISLIKES + s * 4) == VV3_RUN_PREF) has_dislike = 1;
            if (has_like) vw_already++;
            else if (has_free) vw_granted++;
            else vw_noslot++;
            if (has_dislike) vw_removed++;
        }
    }
}

/* Count affected villagers and store the result.  Returns nonzero if the
   purchase would change anything, so the payload can refund and skip on a
   no-op. */
__declspec(dllexport) int __stdcall PrepareOriginsVillageWide(int command) {
    vv3_count_village_wide(command);
    if (command == VW_RUNNING)
        return (int)(vw_granted + vw_removed);
    return (int)vw_granted;
}

/* ---- Barrel-of-Babies capacity check (mode-aware) ----
   The village maximum population is base + population-tech bonuses + a
   nature-level bonus.  The base is the byte the patcher rewrites per population
   mode at 0x0045FEE3 (90 for the stock max, 115 for Collection Progression, and
   so on), so we read it live instead of hardcoding the base-game 90 -- that is
   what keeps this check dynamic across the patcher's population modes.  The
   bonus math mirrors the game's own barrel eligibility 0x0045FE30 by calling its
   routines: +5 per owned population tech (0x0042DE40 on manager 0x0058F428,
   flags 0x34/0x40/0x4C/0x58, all four rounding up to 25), and +10 once the
   nature level (0x00426FC0 on 0x00582618) reaches 3.  Returns 1 when the village
   can hold three more villagers (current + 3 <= max), else 0, so the payload's
   Barrel preflight can refuse before charging.  These absolute addresses are
   fixed: the game exe is non-ASLR (image base 0x00400000) and loaded in this
   process. */
__declspec(dllexport) int __stdcall PrepareBarrelBabies(void) {
    unsigned int current = 0;
    unsigned int maxpop = 0;

    /* The game's routines are __thiscall (this in ecx, stack args callee-cleaned
       via ret 4), so drive them with inline asm; esi accumulates the bonus
       exactly as 0x0045FE30 does.  ebx/esi/edi are preserved for the caller. */
    __asm {
        push ebx
        push esi
        push edi
        mov ecx, 0x59E110       /* population manager */
        mov eax, 0x45E8F0
        call eax                /* current living population */
        mov current, eax
        xor esi, esi            /* bonus */
        mov edi, 0x34           /* population-tech flag id */
    pbb_tech:
        push edi
        mov ecx, 0x58F428
        mov eax, 0x42DE40
        call eax                /* tech owned? (ret 4) */
        test al, al
        je pbb_tech_next
        add esi, 5
    pbb_tech_next:
        add edi, 0x0C
        cmp edi, 0x64
        jl pbb_tech
        cmp esi, 0x14
        jne pbb_level
        mov esi, 0x19           /* all four techs -> 25, not 20 */
    pbb_level:
        push 6
        mov ecx, 0x582618
        mov eax, 0x426FC0
        call eax                /* nature level (ret 4) */
        cmp eax, 3
        jl pbb_base
        add esi, 0x0A
    pbb_base:
        mov eax, 0x45FEE3       /* live per-mode base-population byte */
        movzx eax, byte ptr [eax]
        add eax, esi
        mov maxpop, eax
        pop edi
        pop esi
        pop ebx
    }
    return (current + 3u <= maxpop) ? 1 : 0;
}

/* ---- Tech-screen one-shot / guard result boxes ----
   The payload's Tech one-shots and the Barrel guard have no room left for their
   result strings, so the DLL owns the exact OFFICIAL-sheet wording and the
   payload just calls this by code.  Titled "Origins Upgrades" like the other
   Tech results, topmost so it surfaces over the game. */
__declspec(dllexport) int __stdcall ShowOriginsUpgradeResult(int code) {
    const char *message;
    const char *title = "Origins Upgrades";
    switch (code) {
    case 1:
        message = "Island Event completed.";
        break;
    case 2:
        message = "Tech Point Doubler completed.";
        break;
    case 3:
        message = "Food Point Doubler completed.";
        break;
    case 4:
        message = "Tech Point Doubler was removed. No refund was issued.";
        break;
    case 5:
        message = "Food Point Doubler was removed. No refund was issued.";
        break;
    case 6:
        message = "Village population is close to its maximum. "
                  "The Barrel of Babies needs room for 3 children. "
                  "No tech points have been deducted.";
        break;
    case 7:
        message = "Barrel of Babies completed.";
        break;
    case 8:
        message = "All collectibles are already found. "
                  "No tech points have been deducted.";
        break;
    case 9:
        message = "The collections are already cleared. "
                  "No tech points have been deducted.";
        break;
    case 10:
        /* An Island Event is queued by zeroing its countdown, so buying a
           second one while the first is still pending changes nothing and the
           player pays twice for one event.  The refusal lives here rather than
           as an executable string because the exe's string block is full. */
        message = "An Island Event is already on its way. "
                  "No tech points have been deducted.";
        break;
    /* Details-screen (Villager Upgrades) Grant Running no-change cases. */
    case 20:
        title = "Villager Upgrades";
        message = "This villager already likes Running. "
                  "No tech points have been deducted.";
        break;
    case 21:
        title = "Villager Upgrades";
        message = "This villager's Likes are full, so Running could not be "
                  "added, but its Running dislike was removed. "
                  "No tech points have been deducted.";
        break;
    case 22:
        title = "Villager Upgrades";
        message = "This villager already has full Likes slots. "
                  "Running can not be added.";
        break;
    default:
        return 0;
    }
    MessageBoxA(GetForegroundWindow(), message, title,
                MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 0;
}

/* "Villager" for a count of 1, "Villagers" otherwise -- the sheet requires
   correct singular/plural in the counted results. */
static const char *villagers_word(unsigned int n) {
    return n == 1 ? "Villager" : "Villagers";
}

__declspec(dllexport) int __stdcall ShowOriginsVillageWideResult(int command) {
    char message[512];
    char line[160];
    if (command == VW_RUNNING) {
        if (vw_granted == 0 && vw_removed == 0) {
            lstrcpyA(message, "Everyone already likes running, or has full Likes slots. "
                              "No tech points have been deducted.");
        } else {
            wsprintfA(message, "Granted Running to %u %s.",
                      vw_granted, villagers_word(vw_granted));
            wsprintfA(line, "\r\n\r\nRemoved a Running dislike from %u %s.",
                      vw_removed, villagers_word(vw_removed));
            lstrcatA(message, line);
            wsprintfA(line, "\r\n\r\nSkipped %u %s: already like Running.",
                      vw_already, villagers_word(vw_already));
            lstrcatA(message, line);
            wsprintfA(line, "\r\n\r\nSkipped %u %s: already have 3 likes.",
                      vw_noslot, villagers_word(vw_noslot));
            lstrcatA(message, line);
        }
    } else if (command == VW_MASTERY) {
        if (vw_granted == 0) {
            lstrcpyA(message, "Everyone has already mastered their skills. "
                              "No tech points have been deducted.");
        } else {
            wsprintfA(message, "Granted Full Mastery to %u %s.",
                      vw_granted, villagers_word(vw_granted));
            wsprintfA(line, "\r\n\r\nSkipped %u %s: already fully mastered.",
                      vw_already, villagers_word(vw_already));
            lstrcatA(message, line);
        }
    } else if (command == VW_AGE) {
        if (vw_granted == 0) {
            lstrcpyA(message, "Everyone is already exactly 18. No tech points have been deducted.");
        } else {
            wsprintfA(message, "Set %u %s to Age 18.",
                      vw_granted, villagers_word(vw_granted));
            wsprintfA(line, "\r\n\r\nSkipped %u %s: already exactly 18.",
                      vw_already, villagers_word(vw_already));
            lstrcatA(message, line);
        }
    } else {
        return 0;
    }
    MessageBoxA(GetForegroundWindow(), message, "Origins Upgrades",
                MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 0;
}

/* ---- Equal Division of Labor (Tech-screen buttons 1011/1012) ----
   Scans the whole population and cyclically assigns each eligible villager's
   job-preference checkmark (record +0xEC0, an index: 0=Farming, 1=Parenting,
   2=Healing, 3=Research, 4=Building) in the order Farmer, Builder, Researcher,
   Healer[, Parenting] -- indices [0,4,3,2(,1)] -- repeating.  Males and females
   cycle on independent counters so each profession gets a balanced M/F split as
   well as a balanced count.  Eligible = every active villager EXCEPT the Tribal
   Chief (+0xE80 != 0), who cannot hold a preference; children of any age and
   nursing mothers are included.  Each eligible villager's existing preference is
   overwritten unconditionally (no "already correct" state), so N is simply how
   many were eligible.  The DLL owns the whole transaction (the exe payload is
   nearly full): it verifies funds and deducts the 1,000,000 cost from the tech
   pool 0x00582644 itself, then shows the OFFICIAL-sheet result.  Returns N. */
__declspec(dllexport) int __stdcall EqualDivisionOfLabor(int includeParenting) {
    /* Farmer, Builder, Researcher, Healer, Parenting -> +0xEC0 index values. */
    static const int cycle[5] = {0, 4, 3, 2, 1};
    const char *names[5] = {"Farming", "Building", "Research", "Healing", "Breeding"};
    unsigned char *rec = (unsigned char *)(UINT_PTR)VV3_REC_BASE;
    int slots = *(int *)(UINT_PTR)VV3_SLOTS_PTR;
    int cyclen = includeParenting ? 5 : 4;
    int *tech = (int *)(UINT_PTR)VV3_TECH_POINTS;
    unsigned int per_m[5] = {0, 0, 0, 0, 0};
    unsigned int per_f[5] = {0, 0, 0, 0, 0};
    unsigned int total = 0, skipped = 0, eligible = 0;
    int male_ctr = 0, female_ctr = 0;
    char message[512];
    char line[160];
    int i, k;
    unsigned char *r;

    /* First pass: how many villagers could be assigned (everyone active but the
       Chief).  Refuse before charging if there is nobody. */
    for (i = 0, r = rec; i < slots; ++i, r += VV3_STRIDE) {
        if (r[VV3_ACTIVE] == 0) continue;
        if (r[VV3_CHIEF] != 0) continue;
        eligible++;
    }
    if (eligible == 0) {
        MessageBoxA(GetForegroundWindow(),
                    "No villagers were eligible. No tech points have been deducted.",
                    "Origins Upgrades",
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    if ((unsigned int)*tech < (unsigned int)EDL_COST) {
        MessageBoxA(GetForegroundWindow(), "Not enough tech points.",
                    "Origins Upgrades",
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    *tech -= EDL_COST;

    /* Second pass: assign round-robin, males and females on separate counters. */
    for (i = 0; i < slots; ++i, rec += VV3_STRIDE) {
        int skill, female;
        if (rec[VV3_ACTIVE] == 0) continue;
        if (rec[VV3_CHIEF] != 0) { skipped++; continue; }
        female = rec[VV3_GENDER] != 0;
        if (female) { skill = cycle[female_ctr % cyclen]; female_ctr++; }
        else        { skill = cycle[male_ctr % cyclen];   male_ctr++;  }
        *(int *)(rec + VV3_PREF) = skill;
        if (female) per_f[skill]++; else per_m[skill]++;
        total++;
    }

    /* Build the OFFICIAL-sheet success message.  Professions print in the sheet's
       order Farming, Building, Research, Healing[, Breeding]; their +0xEC0 indices
       are 0, 4, 3, 2, 1. */
    {
        static const int order[5] = {0, 4, 3, 2, 1};
        wsprintfA(message, "Set %u %s' Job Preferences.",
                  total, villagers_word(total));
        for (k = 0; k < cyclen; ++k) {
            int idx = order[k];
            unsigned int m = per_m[idx], f = per_f[idx];
            wsprintfA(line, "\r\n\r\n%s: %u %s (%u Male, %u Female).",
                      names[k], m + f, villagers_word(m + f), m, f);
            lstrcatA(message, line);
        }
        wsprintfA(line, "\r\n\r\nSkipped %u %s: is Tribal Chief.",
                  skipped, villagers_word(skipped));
        lstrcatA(message, line);
    }
    MessageBoxA(GetForegroundWindow(), message, "Origins Upgrades",
                MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return (int)total;
}

__declspec(dllexport) int __stdcall ShowOriginsFullMasteryResult(
    unsigned int status,
    unsigned int changed
) {
    char message[256];
    if (status == 0) {
        lstrcpyA(
            message,
            "Everyone is already fully mastered.\r\n"
            "No tech points have been deducted."
        );
    } else if (status == 2) {
        lstrcpyA(
            message,
            "Not enough tech points.\r\n"
            "No tech points have been deducted."
        );
    } else if (status == 3) {
        lstrcpyA(
            message,
            "Full Mastery cannot be applied because an eligible villager has "
            "an out-of-range skill.\r\n"
            "No tech points have been deducted."
        );
    } else {
        wsprintfA(message, "Fully mastered %u %s.", changed, villagers_word(changed));
    }
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}

/* ---- Change Appearance chooser (dialog 213) ----
   The DLL owns only the preview UI: it renders the extracted head/body atlas
   strips (one 40x65 cell per index) and cycles head/body with the arrows.  The
   payload owns eligibility, the 5,000-tech charge, and writing the villager
   record; this code never touches save data.  head is +0xDF0 (0..29), body is
   +0xDF4 (0..28). */
#define IDD_VV3_APPEARANCE 213
#define IDB_HEAD_M_YOUNG 3001
#define IDB_HEAD_M_OLD   3002
#define IDB_HEAD_F_YOUNG 3003
#define IDB_HEAD_F_OLD   3004
#define IDB_BODY_M       3011
#define IDB_BODY_F       3012
#define IDC_BODY_PREVIEW 3101
#define IDC_HEAD_PREVIEW 3102
#define IDC_BODY_PREV    3103
#define IDC_BODY_NEXT    3104
#define IDC_HEAD_PREV    3105
#define IDC_HEAD_NEXT    3106
#define IDC_MASK_NAME    3107
#define IDC_MASK_PREV    3108
#define IDC_MASK_NEXT    3109
#define IDC_MASK_PREVIEW 3110
#define IDB_MASK_STRIP   3021
#define VV3_MASK_COUNT   6   /* 0=(None), 1..5 = Blue/Orange/Red/Purple/Chief */

static const char *const vv3_mask_names[VV3_MASK_COUNT] = {
    "(None)", "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask",
    "Tribal Chief Mask"
};
#define VV3_APPEARANCE_CELL_W 40
#define VV3_APPEARANCE_CELL_H 65
/* Both counts are the ranges VV3 itself uses, not a copy of another game's.
   Heads: the male_heads/female_heads atlases are 320x1950, i.e. 30 rows of 65.
   Bodies: villager creation assigns `rand(30)` at 0x41751D and 0x417536, so the
   game hands out body indices 0..29 and every one of them has art. VV4 and VV5
   really are 29 -- their creation uses `rand(29)` -- so this count must not be
   made "consistent" with theirs. */
/* The mask preview uses the same 40x65 head/body cell (each mask scaled to fit
   + centred), matching the VV5 New Believers chooser so the chooser sprites are
   the same size across games. */
#define VV3_MASK_CELL_W 40
#define VV3_MASK_CELL_H 65

static int vv3_appearance_sex;
static int vv3_appearance_old;
static int vv3_appearance_head;
static int vv3_appearance_body;
static int vv3_appearance_mask;   /* 0..VV3_MASK_COUNT-1 */

static int vv3_appearance_head_bitmap(void) {
    if (vv3_appearance_sex) {
        return vv3_appearance_old ? IDB_HEAD_F_OLD : IDB_HEAD_F_YOUNG;
    }
    return vv3_appearance_old ? IDB_HEAD_M_OLD : IDB_HEAD_M_YOUNG;
}

static int vv3_appearance_body_bitmap(void) {
    return vv3_appearance_sex ? IDB_BODY_F : IDB_BODY_M;
}

static void vv3_appearance_draw(DRAWITEMSTRUCT *item, int bitmap_id, int index,
                                int cell_w, int cell_h) {
    /* The None entry has no artwork, so blitting its cell leaves an empty
       grey box beside Body and Head, which print words. Name it: a blank
       cell reads as a broken preview rather than a deliberate choice. */
    if (bitmap_id == IDB_MASK_STRIP && index == 0) {
        RECT none_rc = item->rcItem;
        HBRUSH none_bg = CreateSolidBrush(RGB(236, 236, 236));
        FillRect(item->hDC, &none_rc, none_bg);
        DeleteObject(none_bg);
        SetBkMode(item->hDC, TRANSPARENT);
        DrawTextA(item->hDC, "(None)", -1, &none_rc,
                  DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        return;
    }

    RECT rc = item->rcItem;
    int width = rc.right - rc.left;
    int height = rc.bottom - rc.top;
    HBRUSH background = CreateSolidBrush(RGB(236, 236, 236));
    HBITMAP bitmap;
    HDC source;
    HBITMAP previous;
    double scale_x, scale_y, scale;
    int draw_w, draw_h, draw_x, draw_y;

    FillRect(item->hDC, &rc, background);
    DeleteObject(background);

    bitmap = LoadBitmapA(module_instance, MAKEINTRESOURCEA(bitmap_id));
    if (bitmap == NULL) {
        return;
    }
    source = CreateCompatibleDC(item->hDC);
    previous = (HBITMAP)SelectObject(source, bitmap);

    scale_x = (double)width / cell_w;
    scale_y = (double)height / cell_h;
    scale = scale_x < scale_y ? scale_x : scale_y;
    draw_w = (int)(cell_w * scale);
    draw_h = (int)(cell_h * scale);
    draw_x = rc.left + (width - draw_w) / 2;
    draw_y = rc.top + (height - draw_h) / 2;

    SetStretchBltMode(item->hDC, COLORONCOLOR);
    StretchBlt(
        item->hDC, draw_x, draw_y, draw_w, draw_h,
        source, index * cell_w, 0,
        cell_w, cell_h, SRCCOPY
    );

    SelectObject(source, previous);
    DeleteDC(source);
    DeleteObject(bitmap);
}

static void vv3_appearance_repaint(HWND window, int control) {
    InvalidateRect(GetDlgItem(window, control), NULL, TRUE);
}

static INT_PTR CALLBACK vv3_appearance_dialog(
    HWND window, UINT message, WPARAM wparam, LPARAM lparam
) {
    (void)lparam;
    if (message == WM_INITDIALOG) {
        center_topmost_on_owner(window);
        SetDlgItemTextA(window, IDC_MASK_NAME, vv3_mask_names[vv3_appearance_mask]);
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        DRAWITEMSTRUCT *item = (DRAWITEMSTRUCT *)lparam;
        if (item->CtlID == IDC_BODY_PREVIEW) {
            vv3_appearance_draw(item, vv3_appearance_body_bitmap(), vv3_appearance_body,
                                VV3_APPEARANCE_CELL_W, VV3_APPEARANCE_CELL_H);
            return TRUE;
        }
        if (item->CtlID == IDC_HEAD_PREVIEW) {
            vv3_appearance_draw(item, vv3_appearance_head_bitmap(), vv3_appearance_head,
                                VV3_APPEARANCE_CELL_W, VV3_APPEARANCE_CELL_H);
            return TRUE;
        }
        if (item->CtlID == IDC_MASK_PREVIEW) {
            vv3_appearance_draw(item, IDB_MASK_STRIP, vv3_appearance_mask,
                                VV3_MASK_CELL_W, VV3_MASK_CELL_H);
            return TRUE;
        }
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command == IDC_BODY_PREV) {
            vv3_appearance_body = (vv3_appearance_body + VV3_BODY_COUNT - 1) % VV3_BODY_COUNT;
            vv3_appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_BODY_NEXT) {
            vv3_appearance_body = (vv3_appearance_body + 1) % VV3_BODY_COUNT;
            vv3_appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_PREV) {
            vv3_appearance_head = (vv3_appearance_head + VV3_HEAD_COUNT - 1) % VV3_HEAD_COUNT;
            vv3_appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_NEXT) {
            vv3_appearance_head = (vv3_appearance_head + 1) % VV3_HEAD_COUNT;
            vv3_appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == IDC_MASK_PREV) {
            vv3_appearance_mask =
                (vv3_appearance_mask + VV3_MASK_COUNT - 1) % VV3_MASK_COUNT;
            SetDlgItemTextA(window, IDC_MASK_NAME, vv3_mask_names[vv3_appearance_mask]);
            vv3_appearance_repaint(window, IDC_MASK_PREVIEW);
            return TRUE;
        }
        if (command == IDC_MASK_NEXT) {
            vv3_appearance_mask = (vv3_appearance_mask + 1) % VV3_MASK_COUNT;
            SetDlgItemTextA(window, IDC_MASK_NAME, vv3_mask_names[vv3_appearance_mask]);
            vv3_appearance_repaint(window, IDC_MASK_PREVIEW);
            return TRUE;
        }
        if (command == IDOK) {
            EndDialog(window, 1);
            return TRUE;
        }
        if (command == IDCANCEL) {
            EndDialog(window, 0);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, 0);
        return TRUE;
    }
    return FALSE;
}

/* ------------------------------------------------------------------ *
 *  Time Warp                                                          *
 * ------------------------------------------------------------------ *
 *
 * The aging mechanism is the same in all five games, but VV3 differs from VV1
 * and VV2 in two ways that matter, both read off this exact build rather than
 * carried over:
 *
 *   * the record layout is NOT the VV1/VV2 shape.  There the pending slice and
 *     the marker sit just below the age field; here the age is at +0xDC4 while
 *     the pending slice is at +0xE6C and the marker at +0xE70, ABOVE it.  The
 *     aging loop walks esi = record + 0xF10, so its [esi-0x14C] is the age and
 *     its [esi-0xA0] the marker -- confirmed twice over, because the same base
 *     puts the health field it tests at [esi-0x98] = record + 0xE78, which is
 *     the offset the rest of this project already uses.
 *
 *   * the age is NOT a plain add.  0x0045C640 adds the units and then, if the
 *     total reaches 0x640 (1600 units = 80 years), tail-calls 0x00412CD0 --
 *     the old-age notification.  Writing the field directly would skip that,
 *     so this calls the game's own routine instead.  VV1 and VV2 really do
 *     just `add`, which is why they can write theirs.
 *
 * How the engine ages a villager here:
 *
 *   [0x004A4210] is a time_t epoch.  sub_403330 returns "real seconds since
 *   that epoch".  The difference accumulates at +0xE6C and is then CLAMPED at
 *   0x0045F51D:
 *
 *       > 86400                                   -> forced to 86400
 *       > 23800 slow / 31000 normal / 38200 fast  -> forced to 31000
 *
 *   before converting with  units += (pending / 60) / speed_code, at 20 units
 *   per villager year.
 *
 * That clamp is why simply moving the epoch cannot work.  The advance the
 * targets need -- 36000 s at slow, 43200 s at normal and fast -- is over the
 * threshold at every speed, so all three collapse to 31000 and yield
 * 2.55 / 4.3 / 8.6 years instead of 3 / 6 / 12.  Pushing a LARGER number in
 * makes the warp smaller, which is exactly the reported bug.
 *
 * So the advance is applied in two halves: the epoch moves by the true delta
 * so every other time-based system sees a real jump, and each villager is
 * credited the exact units through the game's own routine, with its marker
 * moved by the same delta so its own tick does not process -- and clamp -- the
 * same jump a second time.
 */
#define VV3_TW_SPEED_OFFSET        0x12F20  /* off the manager, arch-adjusted   */
#define VV3_TW_SPEED_PAUSED           999
#define VV3_TW_TIME_EPOCH_VA         0x004A4210u
#define VV3_TW_TECH_POINTS_VA   0x00582644u
#define VV3_TW_AGE_OFFSET          0xDC4    /* age units; 20 == 1 villager year */
#define VV3_TW_LAST_SEEN_OFFSET    0xE70    /* elapsed value this record saw    */
#define VV3_TW_HEALTH_OFFSET       0xE78
#define VV3_TW_TICK_GATE_OFFSET    0xE94    /* engine ages only while this is 0 */
#define VV3_TW_UNITS_PER_YEAR   20
#define VV3_TW_ADD_AGE_FN       0x0045C640u

/* Speed codes are the engine's own divisors, written by the speed menu at
   0x0041DB13 / 0x0041DB65 / 0x0041DBB4.  A year is 20 * 60 * code seconds:
   2 hours at normal and 1 at fast exactly, and 3h20m at slow -- slow is NOT
   the 4 hours it is often quoted as, which is why the years are targeted
   directly here instead of derived from an hours-per-year figure. */
#define VV3_TW_SPEED_SLOW       10
#define VV3_TW_SPEED_NORMAL     6
#define VV3_TW_SPEED_FAST       3

/* 0x0045C640: adds `units` to the age field addressed by ECX, and fires the
   80-year notification if the total crosses 1600.  ret 4.

   That is __thiscall, which MSVC does not accept on a function pointer in C.
   __fastcall is the exact equivalent here: it puts the first argument in ECX
   and the second in EDX, and passes the rest on the stack for the callee to
   clean -- so declaring a dead EDX parameter reproduces the target's ABI
   byte for byte (ECX = this, one stack argument, ret 4). */
typedef void(__fastcall *vv3_add_age_fn)(void *age_field, int unused_edx,
                                         int units);

#define VV3_TW_CANCELLED 0
#define VV3_TW_APPLIED   1
#define VV3_TW_REFUSED   2

static int vv3_time_warp_years(int speed) {
    switch (speed) {
    case VV3_TW_SPEED_SLOW:   return 3;
    case VV3_TW_SPEED_NORMAL: return 6;
    case VV3_TW_SPEED_FAST:   return 12;
    default:                  return 0;   /* paused, or a code we don't know */
    }
}

static const char *vv3_speed_name(int speed) {
    switch (speed) {
    case VV3_TW_SPEED_SLOW:   return "slow";
    case VV3_TW_SPEED_NORMAL: return "normal";
    case VV3_TW_SPEED_FAST:   return "fast";
    default:                  return "unknown";
    }
}

/* The manager, and the speed field on it.  Reads the singleton POINTER rather
   than calling the lazy getter at 0x428B60, for the same reason the pending-row
   probe above does: the getter constructs a manager when there is none, and a
   null pointer already answers the question.  The arch probe picks the right
   field offset on expanded builds, exactly as the executable does. */
static int *vv3_speed_field(void) {
    unsigned char *manager =
        *(unsigned char **)(UINT_PTR)VV3_MANAGER_SINGLETON;
    unsigned int extra = 0;
    if (manager == 0) {
        return 0;
    }
    if (*(volatile unsigned int *)(UINT_PTR)VV3_ARCH_PROBE
        == VV3_ARCH_EXPANDED_VALUE) {
        extra = VV3_ARCH_EXPANDED_OFFSET;
    }
    return (int *)(manager + extra + VV3_TW_SPEED_OFFSET);
}

/* Returns how many records were carried, 0 when the village is empty -- the
   caller treats that as "nothing happened" and charges nothing. */
static int vv3_time_warp_apply(int speed, int years) {
    unsigned int bound = *(volatile unsigned int *)(UINT_PTR)VV3_SLOT_BOUND_PTR;
    unsigned char *base = (unsigned char *)(UINT_PTR)VV3_RECORD_BASE;
    vv3_add_age_fn add_age = (vv3_add_age_fn)(UINT_PTR)VV3_TW_ADD_AGE_FN;
    int units = years * VV3_TW_UNITS_PER_YEAR;
    int delta = units * 60 * speed;
    unsigned int i;
    int occupied = 0;

    if (bound == 0 || bound > 256) {
        return 0;               /* unrecognised bound -> do nothing */
    }
    /* Count BEFORE touching anything: an empty village must not move the world
       clock, because the caller charges nothing when this returns zero. Any
       occupied record counts, whether or not the age credit will reach it. */
    for (i = 0; i < bound; ++i) {
        if (*(volatile int *)(base + i * VV3_RECORD_STRIDE + VV3_OFF_ACTIVE)) {
            ++occupied;
        }
    }
    if (occupied == 0) {
        return 0;
    }

    *(int *)(UINT_PTR)VV3_TW_TIME_EPOCH_VA -= delta;

    for (i = 0; i < bound; ++i) {
        unsigned char *rec = base + i * VV3_RECORD_STRIDE;
        if (*(volatile int *)(rec + VV3_OFF_ACTIVE) == 0) {
            continue;
        }
        /* The marker moves for EVERY occupied record, including ones the age
           credit skips.  It is what stops that villager's own tick from
           putting this jump through the clamp -- skipping it would not hold
           the record's age, it would advance it by the clamped amount. */
        *(int *)(rec + VV3_TW_LAST_SEEN_OFFSET) += delta;
        /* Credit only what the engine's own loop would age: it requires the
           tick gate clear and health above zero (0x0045F4A6 / 0x0045F4AF).
           A skeleton holds a record but does not get older. */
        if (*(unsigned char *)(rec + VV3_TW_TICK_GATE_OFFSET) != 0) {
            continue;
        }
        if (*(int *)(rec + VV3_TW_HEALTH_OFFSET) <= 0) {
            continue;
        }
        add_age(rec + VV3_TW_AGE_OFFSET, 0, units);
    }
    return occupied;
}

/* Tech-menu row 0.  Owns its own confirmation, afford check, charge and
   result, because what it advances and what it says both depend on the game
   speed at the moment of purchase.

   Return value, which the caller branches on:
     0  the player pressed Cancel -- nothing was said and nothing was done, so
        the Tech menu reopens, exactly as Cancel does on every other row;
     1  applied and charged;
     2  refused, with the reason already shown -- the menu closes afterwards,
        which is what every other refusal in this menu does. */
/* Exported through the .def alias only, like the rest of this file: adding
   __declspec(dllexport) as well publishes the decorated _ShowVV3TimeWarp@4
   alongside it, which would grow the export table by two. */
int __stdcall ShowVV3TimeWarp(int cost) {
    static const char *const TITLE = "Origins Upgrades";
    char message[448];
    HWND owner = GetForegroundWindow();
    int *speed_field = vv3_speed_field();
    int *tech = (int *)(UINT_PTR)VV3_TW_TECH_POINTS_VA;
    int speed, years;

    if (speed_field == 0) {
        MessageBoxA(owner,
                    "Time Warp could not reach the village. No tech points "
                    "have been deducted.",
                    TITLE, MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return VV3_TW_REFUSED;
    }
    speed = *speed_field;
    years = vv3_time_warp_years(speed);
    if (years <= 0) {
        /* Paused advances nothing at all, so it must refuse BEFORE any charge
           rather than bill for a no-op. */
        MessageBoxA(owner,
                    speed >= VV3_TW_SPEED_PAUSED
                        ? "Time Warp is unavailable while the game is paused."
                        : "Time Warp could not read the game speed. No tech "
                          "points have been deducted.",
                    TITLE, MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return VV3_TW_REFUSED;
    }
    wsprintfA(message,
              "Do you want to buy Time Warp for %d tech points?\r\n"
              "On %s game speed, this will advance %d villager years.\r\n"
              "Press OK to confirm, or Cancel.",
              cost, vv3_speed_name(speed), years);
    if (MessageBoxA(owner, message, TITLE,
                    MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND)
        != IDOK) {
        return VV3_TW_CANCELLED;
    }
    if (*tech < cost) {
        MessageBoxA(owner, "Not enough tech points.", TITLE,
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return VV3_TW_REFUSED;
    }
    if (vv3_time_warp_apply(speed, years) <= 0) {
        MessageBoxA(owner,
                    "Time Warp could not reach the village records. No tech "
                    "points have been deducted.",
                    TITLE, MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return VV3_TW_REFUSED;
    }
    *tech -= cost;
    wsprintfA(message, "Advanced %d years.", years);
    MessageBoxA(owner, message, TITLE,
                MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return VV3_TW_APPLIED;
}

__declspec(dllexport) int __stdcall ShowVV3AppearanceChooser(
    int sex,
    int age,
    int *head,
    int *body,
    void *record
) {
    INT_PTR result;
    HWND owner;
    int orig_head;
    int orig_body;
    int orig_mask;
    int cur_mask;
    vv3_appearance_sex = sex ? 1 : 0;
    vv3_appearance_old = age >= 1100 ? 1 : 0;
    vv3_appearance_head = (head && *head >= 0 && *head < VV3_HEAD_COUNT) ? *head : 0;
    vv3_appearance_body = (body && *body >= 0 && *body < VV3_BODY_COUNT) ? *body : 0;
    /* The mask choice comes from the DLL-owned table (never a record byte). */
    cur_mask = VV3_GetMaskForRecord(record);
    vv3_appearance_mask = (cur_mask >= 0 && cur_mask < VV3_MASK_COUNT) ? cur_mask : 0;
    orig_head = vv3_appearance_head;
    orig_body = vv3_appearance_body;
    orig_mask = vv3_appearance_mask;

    owner = begin_modal_over_game();
    result = DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_VV3_APPEARANCE),
        GetForegroundWindow(),
        vv3_appearance_dialog,
        0
    );
    end_modal_over_game(owner);

    /* Cancel / close: no change, no charge, no message. */
    if (result != 1) {
        return 0;
    }
    /* OK with nothing changed: report it and do not charge. */
    if (vv3_appearance_head == orig_head && vv3_appearance_body == orig_body &&
        vv3_appearance_mask == orig_mask) {
        MessageBoxA(GetForegroundWindow(),
            "The appearance is unchanged. No tech points have been deducted.",
            "Villager Upgrades",
            MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    /* The head field is hereditary, so changing it warns first; Cancel backs
       out with no write and no charge.  The mask is purely cosmetic (no warning). */
    if (vv3_appearance_head != orig_head) {
        if (MessageBoxA(GetForegroundWindow(),
                "Warning: This will change the villager's head genetics.",
                "Villager Upgrades",
                MB_OKCANCEL | MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND)
            != IDOK) {
            return 0;
        }
    }
    /* Commit a changed mask first.  An unchanged mask must not be rebound:
       the getter can fail closed to 0 during a simultaneous live/stored
       ambiguity even when a stored mask exists, and rebinding that value
       would incorrectly clear the stored mask.  If a changed mask cannot be
       bound to exactly one live villager, abort before changing the staged
       head/body values; the exe sees return 0 and therefore performs no
       writes and no 5,000-point charge. */
    if (vv3_appearance_mask != orig_mask &&
        !VV3_SetMaskForRecord(record, vv3_appearance_mask)) {
        MessageBoxA(GetForegroundWindow(),
            g_vv3_mask_last_persist_failed
                ? "The mask choice could not be saved beside the active save. "
                  "No appearance was changed and no tech points have been deducted."
                : "The appearance could not be safely matched to this villager. "
                  "No tech points have been deducted.",
            "Villager Upgrades",
            MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    if (head) {
        *head = vv3_appearance_head;
    }
    if (body) {
        *body = vv3_appearance_body;
    }
    return 1;
}

/* ================= Change Appearance for All dialog (214) =================
   Two panels (Male / Female), each with Body/Head/Mask cyclers whose "-1" state
   = "no change" (leave that field alone).  A single mutually-exclusive mask-mode
   group (Off / VV5-style / Random / Equal / None / Blue / Orange / Red / Purple /
   Chief) overrides the per-sex Mask cyclers for EVERYONE; when any mode but Off is
   chosen, the per-sex Mask cyclers are greyed.  Head/Body stay independent per-sex.
   All logic is DLL-side (vv3_apply_for_all); the exe just calls the export. */
#define IDD_VV3_APPEARANCE_ALL 214
#define IDC_CAF_M_BODY   3201
#define IDC_CAF_M_BODY_P 3202
#define IDC_CAF_M_BODY_N 3203
#define IDC_CAF_M_HEAD   3204
#define IDC_CAF_M_HEAD_P 3205
#define IDC_CAF_M_HEAD_N 3206
#define IDC_CAF_M_MASK   3207
#define IDC_CAF_M_MASK_P 3208
#define IDC_CAF_M_MASK_N 3209
#define IDC_CAF_M_MASK_T 3210
#define IDC_CAF_F_BODY   3221
#define IDC_CAF_F_BODY_P 3222
#define IDC_CAF_F_BODY_N 3223
#define IDC_CAF_F_HEAD   3224
#define IDC_CAF_F_HEAD_P 3225
#define IDC_CAF_F_HEAD_N 3226
#define IDC_CAF_F_MASK   3227
#define IDC_CAF_F_MASK_P 3228
#define IDC_CAF_F_MASK_N 3229
#define IDC_CAF_F_MASK_T 3230
#define IDC_CAF_MODE_FIRST 3301    /* 3301..3310 = Off,VV5,Random,Equal,None,Blue,Orange,Red,Purple,Chief */

static int caf_m_head, caf_m_body, caf_m_mask;   /* -1 = no change */
static int caf_f_head, caf_f_body, caf_f_mask;
static int caf_mask_mode;                          /* 0..9 (radio id - 3301) */
/* Village-wide Head/Body overrides.  The other four games number these
   3220..3226 / 3240..3241, which VV3 cannot reuse because 3220..3229 is
   already its FEMALE panel -- hence the 3400 block. */
#define IDC_CAF_HEAD_FIRST 3400
#define IDC_CAF_HEAD_LAST  3406
#define IDC_CAF_BODY_FIRST 3410
#define IDC_CAF_BODY_LAST  3411
static int caf_head_mode;   /* 0 = off, 1 = random, 2..6 = hair colour + 2 */
static int caf_body_mode;   /* 0 = off, 1 = random */

static const char *const caf_mode_names[10] = {
    "Off (use per-sex)", "VV5-style", "Random", "Equal",
    "None", "Blue", "Orange", "Red", "Purple", "Chief"
};

/* Cycle a selector through -1 (no change) then 0..count-1 and back to -1. */
static int caf_cycle(int v, int count, int dir) {
    v += dir;
    if (v < -1) return count - 1;
    if (v >= count) return -1;
    return v;
}

static const char *caf_mask_text(int v) {
    if (v < 0) return "No change";
    return vv3_mask_names[v];
}

/* Draw a preview cell, or a blank "no change" panel when index < 0. */
static void caf_draw(DRAWITEMSTRUCT *item, int bitmap_id, int index,
                     int cell_w, int cell_h) {
    /* The None entry has no artwork, so blitting its cell leaves an empty
       grey box beside Body and Head, which print words. Name it: a blank
       cell reads as a broken preview rather than a deliberate choice. */
    if (bitmap_id == IDB_MASK_STRIP && index == 0) {
        RECT none_rc = item->rcItem;
        HBRUSH none_bg = CreateSolidBrush(RGB(236, 236, 236));
        FillRect(item->hDC, &none_rc, none_bg);
        DeleteObject(none_bg);
        SetBkMode(item->hDC, TRANSPARENT);
        DrawTextA(item->hDC, "(None)", -1, &none_rc,
                  DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        return;
    }

    if (index < 0) {
        HBRUSH bg = CreateSolidBrush(RGB(236, 236, 236));
        FillRect(item->hDC, &item->rcItem, bg);
        DeleteObject(bg);
        DrawTextA(item->hDC, "(no change)", -1, &item->rcItem,
                  DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        return;
    }
    vv3_appearance_draw(item, bitmap_id, index, cell_w, cell_h);
}

static void caf_set_mask_enable(HWND w) {
    BOOL off = (caf_mask_mode == 0);
    EnableWindow(GetDlgItem(w, IDC_CAF_M_MASK_P), off);
    EnableWindow(GetDlgItem(w, IDC_CAF_M_MASK_N), off);
    EnableWindow(GetDlgItem(w, IDC_CAF_F_MASK_P), off);
    EnableWindow(GetDlgItem(w, IDC_CAF_F_MASK_N), off);
}

/* A village-wide Head/Body choice supersedes the matching per-sex cyclers, so
   grey them rather than leaving two controls that disagree about the result. */
static void caf_set_head_body_enable(HWND w) {
    BOOL head_off = (caf_head_mode == 0);
    BOOL body_off = (caf_body_mode == 0);
    EnableWindow(GetDlgItem(w, IDC_CAF_M_HEAD_P), head_off);
    EnableWindow(GetDlgItem(w, IDC_CAF_M_HEAD_N), head_off);
    EnableWindow(GetDlgItem(w, IDC_CAF_F_HEAD_P), head_off);
    EnableWindow(GetDlgItem(w, IDC_CAF_F_HEAD_N), head_off);
    EnableWindow(GetDlgItem(w, IDC_CAF_M_BODY_P), body_off);
    EnableWindow(GetDlgItem(w, IDC_CAF_M_BODY_N), body_off);
    EnableWindow(GetDlgItem(w, IDC_CAF_F_BODY_P), body_off);
    EnableWindow(GetDlgItem(w, IDC_CAF_F_BODY_N), body_off);
}

static INT_PTR CALLBACK vv3_caf_dialog(HWND w, UINT msg, WPARAM wp, LPARAM lp) {
    (void)lp;
    if (msg == WM_INITDIALOG) {
        int r;
        center_topmost_on_owner(w);
        for (r = 0; r < 10; ++r)
            CheckDlgButton(w, IDC_CAF_MODE_FIRST + r, r == caf_mask_mode ? BST_CHECKED : BST_UNCHECKED);
        SetDlgItemTextA(w, IDC_CAF_M_MASK_T, caf_mask_text(caf_m_mask));
        SetDlgItemTextA(w, IDC_CAF_F_MASK_T, caf_mask_text(caf_f_mask));
        for (r = IDC_CAF_HEAD_FIRST; r <= IDC_CAF_HEAD_LAST; ++r)
            CheckDlgButton(w, r, (r - IDC_CAF_HEAD_FIRST) == caf_head_mode
                                 ? BST_CHECKED : BST_UNCHECKED);
        for (r = IDC_CAF_BODY_FIRST; r <= IDC_CAF_BODY_LAST; ++r)
            CheckDlgButton(w, r, (r - IDC_CAF_BODY_FIRST) == caf_body_mode
                                 ? BST_CHECKED : BST_UNCHECKED);
        caf_set_mask_enable(w);
        caf_set_head_body_enable(w);
        return TRUE;
    } else if (msg == WM_DRAWITEM) {
        DRAWITEMSTRUCT *it = (DRAWITEMSTRUCT *)lp;
        switch (it->CtlID) {
        case IDC_CAF_M_BODY: caf_draw(it, IDB_BODY_M, caf_m_body, VV3_APPEARANCE_CELL_W, VV3_APPEARANCE_CELL_H); return TRUE;
        case IDC_CAF_M_HEAD: caf_draw(it, IDB_HEAD_M_YOUNG, caf_m_head, VV3_APPEARANCE_CELL_W, VV3_APPEARANCE_CELL_H); return TRUE;
        case IDC_CAF_M_MASK: caf_draw(it, IDB_MASK_STRIP, caf_m_mask, VV3_MASK_CELL_W, VV3_MASK_CELL_H); return TRUE;
        case IDC_CAF_F_BODY: caf_draw(it, IDB_BODY_F, caf_f_body, VV3_APPEARANCE_CELL_W, VV3_APPEARANCE_CELL_H); return TRUE;
        case IDC_CAF_F_HEAD: caf_draw(it, IDB_HEAD_F_YOUNG, caf_f_head, VV3_APPEARANCE_CELL_W, VV3_APPEARANCE_CELL_H); return TRUE;
        case IDC_CAF_F_MASK: caf_draw(it, IDB_MASK_STRIP, caf_f_mask, VV3_MASK_CELL_W, VV3_MASK_CELL_H); return TRUE;
        default: break;
        }
    } else if (msg == WM_COMMAND) {
        unsigned int id = LOWORD(wp);
        /* These two run BEFORE the mask branch, not inside it.  3400..3411 can
           never satisfy the 3301..3310 test, so nesting them there left both
           modes stuck at zero: the radio looked selected through the control's
           own behaviour while OK saw no override at all. */
        if (id >= IDC_CAF_HEAD_FIRST && id <= IDC_CAF_HEAD_LAST) {
            caf_head_mode = (int)(id - IDC_CAF_HEAD_FIRST);
            caf_set_head_body_enable(w);
            return TRUE;
        }
        if (id >= IDC_CAF_BODY_FIRST && id <= IDC_CAF_BODY_LAST) {
            caf_body_mode = (int)(id - IDC_CAF_BODY_FIRST);
            caf_set_head_body_enable(w);
            return TRUE;
        }
        if (id >= IDC_CAF_MODE_FIRST && id <= IDC_CAF_MODE_FIRST + 9) {
            int r;
            caf_mask_mode = (int)(id - IDC_CAF_MODE_FIRST);
            for (r = 0; r < 10; ++r)
                CheckDlgButton(w, IDC_CAF_MODE_FIRST + r, r == caf_mask_mode ? BST_CHECKED : BST_UNCHECKED);
            caf_set_mask_enable(w);
            return TRUE;
        }
        switch (id) {
        case IDC_CAF_M_BODY_P: caf_m_body = caf_cycle(caf_m_body, VV3_BODY_COUNT, -1); vv3_appearance_repaint(w, IDC_CAF_M_BODY); return TRUE;
        case IDC_CAF_M_BODY_N: caf_m_body = caf_cycle(caf_m_body, VV3_BODY_COUNT,  1); vv3_appearance_repaint(w, IDC_CAF_M_BODY); return TRUE;
        case IDC_CAF_M_HEAD_P: caf_m_head = caf_cycle(caf_m_head, VV3_HEAD_COUNT, -1); vv3_appearance_repaint(w, IDC_CAF_M_HEAD); return TRUE;
        case IDC_CAF_M_HEAD_N: caf_m_head = caf_cycle(caf_m_head, VV3_HEAD_COUNT,  1); vv3_appearance_repaint(w, IDC_CAF_M_HEAD); return TRUE;
        case IDC_CAF_M_MASK_P: caf_m_mask = caf_cycle(caf_m_mask, VV3_MASK_COUNT, -1); SetDlgItemTextA(w, IDC_CAF_M_MASK_T, caf_mask_text(caf_m_mask)); vv3_appearance_repaint(w, IDC_CAF_M_MASK); return TRUE;
        case IDC_CAF_M_MASK_N: caf_m_mask = caf_cycle(caf_m_mask, VV3_MASK_COUNT,  1); SetDlgItemTextA(w, IDC_CAF_M_MASK_T, caf_mask_text(caf_m_mask)); vv3_appearance_repaint(w, IDC_CAF_M_MASK); return TRUE;
        case IDC_CAF_F_BODY_P: caf_f_body = caf_cycle(caf_f_body, VV3_BODY_COUNT, -1); vv3_appearance_repaint(w, IDC_CAF_F_BODY); return TRUE;
        case IDC_CAF_F_BODY_N: caf_f_body = caf_cycle(caf_f_body, VV3_BODY_COUNT,  1); vv3_appearance_repaint(w, IDC_CAF_F_BODY); return TRUE;
        case IDC_CAF_F_HEAD_P: caf_f_head = caf_cycle(caf_f_head, VV3_HEAD_COUNT, -1); vv3_appearance_repaint(w, IDC_CAF_F_HEAD); return TRUE;
        case IDC_CAF_F_HEAD_N: caf_f_head = caf_cycle(caf_f_head, VV3_HEAD_COUNT,  1); vv3_appearance_repaint(w, IDC_CAF_F_HEAD); return TRUE;
        case IDC_CAF_F_MASK_P: caf_f_mask = caf_cycle(caf_f_mask, VV3_MASK_COUNT, -1); SetDlgItemTextA(w, IDC_CAF_F_MASK_T, caf_mask_text(caf_f_mask)); vv3_appearance_repaint(w, IDC_CAF_F_MASK); return TRUE;
        case IDC_CAF_F_MASK_N: caf_f_mask = caf_cycle(caf_f_mask, VV3_MASK_COUNT,  1); SetDlgItemTextA(w, IDC_CAF_F_MASK_T, caf_mask_text(caf_f_mask)); vv3_appearance_repaint(w, IDC_CAF_F_MASK); return TRUE;
        case IDOK: EndDialog(w, 1); return TRUE;
        case IDCANCEL: EndDialog(w, 0); return TRUE;
        default: break;
        }
    } else if (msg == WM_CLOSE) {
        EndDialog(w, 0);
        return TRUE;
    }
    return FALSE;
}

/* Village-wide "Change Appearance for All" (Tech menu, 450,000).  Owns the whole
   transaction DLL-side: show the dialog, and on OK-with-a-change deduct 450k from
   the tech pool 0x00582644 and apply to every active villager.  Returns 1 when it
   charged + applied, else 0 (cancel / nothing changed / insufficient funds). */
#define VV3_CAF_COST 450000
__declspec(dllexport) int __stdcall ShowVV3AppearanceForAll(void) {
    int *tech = (int *)(UINT_PTR)VV3_TECH_POINTS;
    INT_PTR result;
    int changed, affected;
    caf_m_head = caf_m_body = caf_m_mask = -1;
    caf_f_head = caf_f_body = caf_f_mask = -1;
    caf_mask_mode = 0;
    caf_head_mode = caf_body_mode = 0;

    begin_modal_over_game();
    result = DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_VV3_APPEARANCE_ALL),
                             GetForegroundWindow(), vv3_caf_dialog, 0);
    if (result != 1) {
        return 0;
    }
    changed = (caf_m_head >= 0 || caf_m_body >= 0 || caf_f_head >= 0 || caf_f_body >= 0
               || caf_mask_mode != 0 || caf_m_mask >= 0 || caf_f_mask >= 0
               || caf_head_mode != 0 || caf_body_mode != 0);
    if (!changed) {
        MessageBoxA(GetForegroundWindow(),
            "Nothing was selected to change. No tech points have been deducted.",
            "Origins Upgrades", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    if ((unsigned int)*tech < (unsigned int)VV3_CAF_COST) {
        MessageBoxA(GetForegroundWindow(), "Not enough tech points.",
            "Origins Upgrades", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    /* Head is hereditary -> one genetics warning at village scale; Cancel = no charge. */
    if (caf_m_head >= 0 || caf_f_head >= 0 || caf_head_mode != 0) {
        if (MessageBoxA(GetForegroundWindow(),
                "Warning: This will change the head genetics of every villager "
                "of the selected sex, affecting their descendants.\r\n\r\n"
                "Proceed?",
                "Change Appearance for All",
                MB_OKCANCEL | MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND)
            != IDOK) {
            return 0;
        }
    }
    affected = vv3_apply_for_all(caf_m_head, caf_m_body, caf_m_mask,
                                 caf_f_head, caf_f_body, caf_f_mask, caf_mask_mode,
                                 caf_head_mode, caf_body_mode);
    if (affected == 0) {
        const char *why;
        if (g_vv3_caf_mask_persist_failed) {
            why = "The selected masks could not be saved beside the active save. "
                  "No appearance was changed and no tech points have been deducted.";
        } else if (g_vv3_caf_mask_fail == VV3_CAF_MASK_NO_SLOT) {
            why = "No active save slot is available yet, so masks cannot be "
                  "stored beside the save file. Load or save this village, "
                  "then try again. "
                  "No tech points have been deducted.";
        } else if (g_vv3_caf_mask_fail == VV3_CAF_MASK_BAD_MODE) {
            why = "That mask option was not recognized, so nothing was changed. "
                  "No tech points have been deducted.";
        } else if (g_vv3_caf_mask_fail == VV3_CAF_MASK_AMBIGUOUS) {
            why = "Some villagers cannot be told apart, so their masks could not "
                  "be assigned individually. "
                  "No tech points have been deducted.";
        } else if (g_vv3_caf_mask_fail == VV3_CAF_MASK_NO_ROOM) {
            why = "There was no room to record the selected masks for every "
                  "villager. "
                  "No tech points have been deducted.";
        } else {
            why = "No eligible villagers matched the selected appearance options. "
                  "No tech points have been deducted.";
        }
        MessageBoxA(GetForegroundWindow(), why,
            "Origins Upgrades", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    *tech -= VV3_CAF_COST;
    MessageBoxA(GetForegroundWindow(),
        "Change Appearance for All applied.",
        "Origins Upgrades", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 1;
}
