#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shlobj.h>   /* SHGetSpecialFolderPathA for the mask-sidecar path */

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

__declspec(dllexport) void __stdcall VV3WorldMaskDraw(int index);
__declspec(dllexport) void __stdcall VV3WorldMaskDrawAt(void *record, int *args);
__declspec(dllexport) void __stdcall VV3WorldMaskFlush(void);

/* The village head-draw cave reads this fixed exe .data slot for the world-mask
   draw fn, so the per-frame cave needs no LoadLibrary/GetProcAddress -- we publish
   our own export here on load.  The slot is in the same writable, otherwise-unused
   .data page tail as MASK_DRAWFN_PTR (0x6C7A00); 0x6C7A04 is the next dword.  We
   publish the INTERCEPT variant (called from the head-draw call site with the
   head's exact x/y/scale). */
#define VV3_WORLD_DRAWFN_PTR_SLOT  0x006C7A04u
/* Z-ORDER (final): the mask is drawn by the wrapper spliced at the per-villager handler's
   CALL SITE (0x42E3F5) -- it runs the whole handler, then calls VV3WorldMaskDraw(index),
   which the wrapper reads from this fixed .data slot.  Recomputed from the record, so it
   catches EVERY villager (children included) and lands on top of all layers.  (The old
   head-site stash path VV3WorldMaskDrawAt/Flush is retained but unused.) */
#define VV3_WORLD_INDEXFN_PTR_SLOT 0x006C7A08u

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        module_instance = instance;
        *(void **)(UINT_PTR)VV3_WORLD_DRAWFN_PTR_SLOT  = (void *)&VV3WorldMaskDrawAt;
        *(void **)(UINT_PTR)VV3_WORLD_INDEXFN_PTR_SLOT = (void *)&VV3WorldMaskDraw;
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

/* Self-deploy the embedded atlas (RCDATA 5000) into <game>\Images\heathen_masks.png
   if it is missing, so the feature ships with ONLY the companion DLL -- no patcher
   manifest asset step (companion_files is locked to the DLL, and relaxing it would
   touch shared cross-game core).  Skips if the file already exists, so a user can
   replace the art.  A failure just leaves the atlas unloadable -> no mask. */
static void vv3_extract_mask_atlas(void) {
    char exe[MAX_PATH], path[MAX_PATH];
    char *base, *p;
    HRSRC res;
    HGLOBAL blob;
    const void *data;
    DWORD size, written;
    HANDLE fh;
    DWORD n = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;
    base = exe;
    for (p = exe; *p != '\0'; ++p) if (*p == '\\' || *p == '/') base = p + 1;
    *base = '\0';                                    /* game directory + trailing slash */
    if (lstrlenA(exe) + 24 >= (int)sizeof(path)) return;
    wsprintfA(path, "%sImages\\heathen_masks.png", exe);
    if (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES) return;  /* already present */
    res = FindResourceA(module_instance, MAKEINTRESOURCEA(5000), RT_RCDATA);
    if (res == NULL) return;
    size = SizeofResource(module_instance, res);
    blob = LoadResource(module_instance, res);
    if (blob == NULL || size == 0) return;
    data = LockResource(blob);
    if (data == NULL) return;
    fh = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                     FILE_ATTRIBUTE_NORMAL, NULL);
    if (fh == INVALID_HANDLE_VALUE) return;
    WriteFile(fh, data, size, &written, NULL);
    CloseHandle(fh);
}

__declspec(dllexport) void *__stdcall VV3GetMaskAtlas(void) {
    static const char mask_atlas_name[] = "heathen_masks.png";
    void *atlas = NULL;
    if (g_mask_atlas != NULL) {
        return g_mask_atlas;
    }
    vv3_extract_mask_atlas();          /* ensure Images/heathen_masks.png exists */
    __asm {
        push 0x34               /* atlas object size (matches the game's own) */
        mov  eax, 0x0046EC93
        call eax                /* eax = fresh atlas object                    */
        add  esp, 4
        mov  ecx, eax           /* this = the object                           */
        push 5                  /* rows (5 masks)                              */
        push 8                  /* cols (8 directional frames)                 */
        lea  eax, mask_atlas_name
        push eax                /* filename                                    */
        mov  eax, 0x0040AF10
        call eax                /* loader(this, name, 8, 5) -> eax = atlas     */
        mov  atlas, eax
    }
    g_mask_atlas = atlas;
    return atlas;
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
        for (row = 0; row < 9; ++row) {
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
        }
        for (row = 0; row < row_count; ++row) {
            if ((lparam & (1 << row)) != 0) {
                ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
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
            /* Owned Tech/Food Doublers (rows 3/4) show a "Remove" button; a
               removal costs and refunds nothing, so confirm it as a removal
               rather than a 500,000-tech purchase. */
            int is_remove = !s_villager_menu && (row == 3 || row == 4)
                && (s_dialog_state & (1 << row)) != 0;
            char prompt[256];
            if (is_remove) {
                wsprintfA(
                    prompt,
                    "Do you want to remove %s?\r\n"
                    "It will be removed with no refund.\r\n"
                    "Press OK to confirm, or Cancel.",
                    name);
            } else {
                wsprintfA(
                    prompt,
                    "Do you want to buy %s for %s tech points?\r\n"
                    "Press OK to confirm, or Cancel.",
                    name, cost);
            }
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
   stored mask is guarded by an identity fingerprint over fields fixed at birth
   (gender + 3 Likes + 3 Dislikes): on read we recompute it and only return the
   mask when it still matches, so a reused slot reads as "no mask" and can never
   inherit the previous villager's mask.  Persistence (a sidecar file next to the
   save) is a later step -- for now the table is in-memory (masks reset on quit),
   matching VV2's current state.  Render reads via VV3_GetMaskForRecord; the
   Change Appearance chooser writes via VV3_SetMaskForRecord. */
#define VV3_MASK_SLOTS 256
#define VV3_MASK_MAX   5             /* 1..5 = Blue/Orange/Red/Purple/Chief; 0=none */

static unsigned char g_vv3_mask[VV3_MASK_SLOTS];
static unsigned int  g_vv3_mask_fp[VV3_MASK_SLOTS];

/* FNV-1a/32 over the villager's immutable-at-birth genetics; 0 -> 1 (0 reserved). */
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
    if (record == NULL || p < base) return -1;
    off = p - base;
    if (off % VV3_STRIDE) return -1;
    idx = off / VV3_STRIDE;
    if (idx >= VV3_MASK_SLOTS) return -1;
    return (int)idx;
}

/* ---- Sidecar persistence (a file next to the save; never the save itself) ----
   The table is DLL memory, so without this masks would reset on quit.  The
   sidecar is Documents\LDW\<exe-basename>\vvfp_masks.dat -- the same folder VV3
   keeps its saves in -- holding the mask + fingerprint arrays.  Written on every
   chooser commit (write-through) and read once on the first table access of the
   session (so a loaded village restores its masks; the fingerprint guard keeps
   them correct even if slot indices shifted).  All file I/O is in these normal
   functions, never DllMain (loader-lock safe).  Keyed by record index; switching
   saves mid-session shows the prior masks until re-set (no reset hook yet) --
   matching VV5's model.  A missing/short file just leaves the table zeroed. */
#define VV3_MASK_MAGIC 0x334B534Du   /* "MSK3" little-endian */
static int g_vv3_mask_loaded;

static int vv3_mask_sidecar_path(char *out, int cap) {
    char docs[MAX_PATH], exe[MAX_PATH], dir[MAX_PATH];
    char *base, *dot, *p;
    DWORD n;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) return 0;
    n = GetModuleFileNameA(NULL, exe, MAX_PATH);           /* the GAME exe */
    if (n == 0 || n >= MAX_PATH) return 0;
    base = exe;
    for (p = exe; *p; ++p) if (*p == '\\' || *p == '/') base = p + 1;
    dot = NULL;
    for (p = base; *p; ++p) if (*p == '.') dot = p;
    if (dot) *dot = '\0';                                  /* strip extension */
    if (lstrlenA(docs) + lstrlenA(base) + 24 >= cap) return 0;
    wsprintfA(dir, "%s\\LDW", docs);                       CreateDirectoryA(dir, NULL);
    wsprintfA(dir, "%s\\LDW\\%s", docs, base);             CreateDirectoryA(dir, NULL);
    wsprintfA(out, "%s\\LDW\\%s\\vvfp_masks.dat", docs, base);
    return 1;
}

static void vv3_mask_write_sidecar(void) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD w = 0;
    unsigned int magic = VV3_MASK_MAGIC;
    if (!vv3_mask_sidecar_path(path, sizeof(path))) return;
    h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    WriteFile(h, &magic, sizeof(magic), &w, NULL);
    WriteFile(h, g_vv3_mask, sizeof(g_vv3_mask), &w, NULL);
    WriteFile(h, g_vv3_mask_fp, sizeof(g_vv3_mask_fp), &w, NULL);
    CloseHandle(h);
}

static void vv3_mask_read_sidecar(void) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD r = 0;
    unsigned int magic = 0;
    g_vv3_mask_loaded = 1;                                 /* one-shot; set first */
    if (!vv3_mask_sidecar_path(path, sizeof(path))) return;
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    if (ReadFile(h, &magic, sizeof(magic), &r, NULL) && r == sizeof(magic)
        && magic == VV3_MASK_MAGIC) {
        ReadFile(h, g_vv3_mask, sizeof(g_vv3_mask), &r, NULL);
        ReadFile(h, g_vv3_mask_fp, sizeof(g_vv3_mask_fp), &r, NULL);
    }
    CloseHandle(h);
}

/* Render hook: mask (1..5) to draw over this villager's head, or 0 for none /
   empty slot / a reused slot whose fingerprint no longer matches. */
__declspec(dllexport) int __stdcall VV3_GetMaskForRecord(void *record) {
    const unsigned char *rec = (const unsigned char *)record;
    int idx;
    if (!g_vv3_mask_loaded) vv3_mask_read_sidecar();       /* restore on first use */
    idx = vv3_mask_index(record);
    if (idx < 0) return 0;
    if (g_vv3_mask[idx] == 0) return 0;
    if (g_vv3_mask_fp[idx] != vv3_mask_fingerprint(rec)) return 0;
    return g_vv3_mask[idx];
}

/* Chooser commit: store the chosen mask (0..5) for this villager.  Never writes
   the record.  Returns 1 on a valid record. */
__declspec(dllexport) int __stdcall VV3_SetMaskForRecord(void *record, int mask) {
    const unsigned char *rec = (const unsigned char *)record;
    int idx = vv3_mask_index(record);
    if (!g_vv3_mask_loaded) vv3_mask_read_sidecar();       /* don't clobber unread data */
    if (idx < 0) return 0;
    if (mask < 0 || mask > VV3_MASK_MAX) mask = 0;
    g_vv3_mask[idx] = (unsigned char)mask;
    g_vv3_mask_fp[idx] = mask ? vv3_mask_fingerprint(rec) : 0u;
    vv3_mask_write_sidecar();                              /* persist next to the save */
    return 1;
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
#define VV3_MASK_LIFT_MUL 34          /* y_mask = y - ((scaledY*MUL)>>7); live-tuned
                                         2026-08-23 (54 too high, 16 too low, 34 seats
                                         the mask on the head) */
#define VV3_MASK_DRAW_FN  0x004093A0u

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
    x       = args[1];
    frame   = args[4];
    scaledY = args[5];
    flag    = args[6];
    row     = mask - 1;
    ymask   = args[2] - ((scaledY * VV3_MASK_LIFT_MUL) >> 7);
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

/* ---- World / village mask draw (called from the flush's per-villager handler) --
   VV3's village view is a DEFERRED renderer: the world loop enqueues each villager
   and the flush sub_42E2A0 depth-sorts then draws each via the per-villager handler
   sub_4605F0 (0x4605F0).  The exe WRAPS that handler: it runs the original (draws
   the villager), then calls this with the villager record.  We look up the mask
   (fingerprint-guarded table) and, if set, draw the mask cell ON TOP at the
   villager's OWN world position -- obtained from the same helper the villager draw
   uses (0x455EF0) -- via the world's immediate blit 0x42E510, which applies the
   camera scroll/zoom itself, so the mask tracks the villager as the view pans.
   Because the handler runs once per villager in depth-sorted order, drawing here
   gives correct z-order with no stash list.  All tunables (lift, facing) are C so
   they can be live-tuned by WPM like the Detail lift.  Writes NO villager state; a
   missing atlas / no mask / bad record draws nothing (never a crash). */
#define VV3_WORLD_MGR      0x0058F6F8u   /* the deferred-draw manager object       */
#define VV3_WORLD_POS_FN   0x00455EF0u   /* __thiscall(record, &out{x,y}) -> base   */
#define VV3_WORLD_SCALE_FN 0x00455E50u   /* __thiscall(record) -> double age-scale  */
#define VV3_WORLD_DRAW_FN  0x0042E510u   /* __thiscall(mgr, atlas, x, y, cell, sc)  */
#define VV3_WORLD_ATLAS_COLS 8           /* mask atlas = 8 facings x 5 masks        */
#define VV3_WORLD_HEAD_DX  34            /* head x-offset from base (per sub_4605F0) */
#define VV3_WORLD_HEAD_DY  32            /* head y-offset from base (per sub_4605F0) */
int g_vv3_world_lift   = 75;   /* scale-relative lift; 75 seats ADULTS perfectly     */
int g_vv3_world_facing = -1;   /* -1 = AUTO (read head atlas frame); >=0 = force col */
int g_vv3_world_dx     = 15;   /* live-tuned X nudge: +right / -left (scaled px)     */
int g_vv3_world_dy     = 0;    /* live-tuned Y nudge: +down / -up (scaled px)       */
int g_vv3_world_liftfloor = 78;/* min scale%% used for the LIFT only, so small/child */
                               /* villagers lift enough (else masks sit low on kids) */
int g_vv3_world_facing_off = 0xF18; /* RECORD offset of the 0..7 facing COLUMN.  VV5's */
                               /* native mask render confirmed: +0xF14 is the x8 POSITION */
                               /* term (VV5 +0x1D00); the direct atlas COLUMN the head    */
                               /* (and mask) uses is the ADJACENT field +0xF18 (VV5       */
                               /* +0x1D04), range 0..7 = 8 directions. K=0 (same column). */
int g_vv3_world_facing_remap = 0;   /* +(mod 8) to rotate columns if head/mask order differ */
#define VV3_WORLD_CARRIED_OFF   0xF12 /* byte !=0 => carried/held (half-scale) -> skip */

/* Per-frame stash of the EXACT head-draw position/scale, set by the head-site cave
   (0x460A60 -> VV3WorldMaskDrawAt) DURING the handler.  Lets the mask reuse the head's
   real ANIMATED position (walk/dance bob, and the +0x14 carry offset when a villager is
   picked up) instead of a static recompute.  Single-threaded render loop => one global
   stash is safe: set during the handler, consumed once by the wrapper's draw. */
static int   g_vv3_stash_valid  = 0;
static void *g_vv3_stash_record = NULL;
static int   g_vv3_stash_x = 0, g_vv3_stash_y = 0, g_vv3_stash_scale = 0;
/* Also stash the manager's per-villager render term [mgr+0x3010] AS IT WAS at the head
   draw: my mask draws later (at the wrapper, after hair/overlays/action/props), by when
   this shared field may have changed -> the mask would blend/scale differently from the
   head (the "faded" mismatch).  Reusing the head-time value makes the mask inherit the
   head's exact render state. */
static int   g_vv3_stash_m3010 = 0;

/* Draw the world mask for one villager INDEX, on top of the fully-drawn villager.
   Called from the wrapper spliced at the handler's SOLE call site (0x42E3F5): the whole
   villager (head, hair, overlays, action, props) is drawn by sub_4605F0, THEN this runs
   -> guaranteed last layer.  POSITION: prefer the EXACT head-draw x/y/scale the head-site
   cave stashed this pass (so the mask tracks the head's real animation bob AND follows a
   picked-up/carried villager); fall back to a record recompute (sub_455EF0 pos +
   sub_455E50 age-scale) for villagers drawn via a path that skips the 0x460A60 head draw.
   Either way the age-derived scale makes the mask track each villager's size (children
   included).  Skips HELD/carried villagers (VV5's behavior) and inherits the head's exact
   [mgr+0x3010] render state so the mask isn't faded relative to the head. */
__declspec(dllexport) void __stdcall VV3WorldMaskDraw(int index)
{
    void *record = (void *)(UINT_PTR)(VV3_REC_BASE + (unsigned)index * VV3_STRIDE);
    int mask, x, y, cell, facing, scaleBits, used_stash = 0;
    void *atlas;
    int pos[2];
    double scale = 1.0;
    float fscale, liftsc, floor;
    if (index < 0 || index >= 150) {
        g_vv3_stash_valid = 0;
        return;
    }
    mask = VV3_GetMaskForRecord(record);
    if (mask <= 0) {
        g_vv3_stash_valid = 0;
        return;
    }
    /* HELD/CARRIED skip (VV5's approach): when a villager is picked up/dragged/carried, a
       SEPARATE renderer (0x4342xx, floating array 0x5947B8) draws the moving copy at the
       cursor, while the queue still draws a faded copy at the villager's old ground spot.
       Drawing the mask on that ground copy = a faded, misaligned ghost.  So skip the mask
       while held (record+0xF12 != 0) -- the mask cleanly disappears for the brief drag,
       exactly as VV5's native mask does (it skips the whole head+mask block when held). */
    if (*((unsigned char *)record + VV3_WORLD_CARRIED_OFF) != 0) {
        g_vv3_stash_valid = 0;
        return;
    }
    atlas = VV3GetMaskAtlas();
    if (atlas == NULL) {
        g_vv3_stash_valid = 0;
        return;
    }
    if (g_vv3_stash_valid && g_vv3_stash_record == record) {
        /* EXACT head-draw position/scale from this pass (tracks animation + carry) */
        x = g_vv3_stash_x;
        y = g_vv3_stash_y;
        scaleBits = g_vv3_stash_scale;
        fscale = *(float *)&scaleBits;
        used_stash = 1;
    } else {
        /* fallback: recompute the head anchor from the record.
           base world position (v10,v11) -- the same helper sub_4605F0 uses */
        __asm {
            lea  eax, pos
            push eax
            mov  ecx, record
            mov  edx, VV3_WORLD_POS_FN
            call edx                         /* sub_455EF0(record, &pos); ret 4 */
        }
        __asm {
            mov  ecx, record
            mov  edx, VV3_WORLD_SCALE_FN
            call edx                         /* sub_455E50(record) -> double */
            fstp scale
        }
        fscale = (float)scale;
        x = pos[0] - (int)(scale * VV3_WORLD_HEAD_DX);
        y = pos[1] - (int)(scale * VV3_WORLD_HEAD_DY);
    }
    g_vv3_stash_valid = 0;                    /* consume this pass's stash */
    /* FACING: villager 0..7 direction from record+0xF18 (VV5's direct head-column analog),
       live-tunable offset+remap; g_vv3_world_facing >= 0 forces a column. */
    if (g_vv3_world_facing >= 0) {
        facing = g_vv3_world_facing & 7;
    } else {
        facing = ((*(int *)((unsigned char *)record + g_vv3_world_facing_off))
                  + g_vv3_world_facing_remap) & 7;
    }
    cell = (mask - 1) * VV3_WORLD_ATLAS_COLS + facing;
    /* child lift boost: floor the scale used for the LIFT (not the draw) so small
       villagers still lift the tall cell onto the head */
    liftsc = fscale;
    floor = g_vv3_world_liftfloor * 0.01f;
    if (liftsc < floor) {
        liftsc = floor;
    }
    /* The head anchor (x,y) above matches sub_4605F0's head draw; add the taller mask
       cell's lift + live nudges, all scale-relative so the mask tracks age/perspective. */
    x += (int)(g_vv3_world_dx * fscale);
    y += - (int)(g_vv3_world_lift * liftsc) + (int)(g_vv3_world_dy * fscale);
    {
        /* FADE FIX (VV2 trace): both the head draw (42E570) and my cell draw (42E510)
           converge on the same terminal blit 0x404620, which FAST-PATHS (solid) when the
           two float scale args are 1.0 and otherwise takes a SOFTWARE-SCALED path that
           couples ALPHA to scale (-> a small child's mask goes translucent).  The head
           escapes this by passing 1.0 for the float scale and folding the size reduction
           into the INTEGER term [mgr+0x3010] (fild [3010]; fmul scale; ftol).  So mirror
           the head exactly: pass scale = 1.0f to 42E510 (fast path, solid alpha) and set
           [mgr+0x3010] = round(base3010 * scale) for the size.  base3010 = the value the
           head used (stashed) when available.  Restore [3010] afterwards. */
        int   *p3010    = (int *)(UINT_PTR)(VV3_WORLD_MGR + 0x3010);
        int    save3010 = *p3010;
        int    base3010 = used_stash ? g_vv3_stash_m3010 : save3010;
        int    one      = 0x3F800000;           /* float 1.0 -> fast, non-faded blit path */
        double sized    = (double)base3010 * (double)fscale;
        *p3010 = (int)(sized >= 0.0 ? sized + 0.5 : sized - 0.5);
        __asm {
            mov  eax, one                /* arg5 = 1.0f -> 0x404620 fast path (solid alpha) */
            push eax
            push cell                    /* atlas cell (linear index) -> 42E510 arg4         */
            push y
            push x
            push atlas
            mov  ecx, VV3_WORLD_MGR
            mov  edx, VV3_WORLD_DRAW_FN
            call edx                     /* sub_42E510(mgr, atlas, x, y, cell, 1.0f); ret 0x14 */
        }
        *p3010 = save3010;               /* restore the shared manager field */
    }
}

/* Head-site STASH: spliced at 0x460A60 (the head draw) via a cave that re-issues the head
   then calls this.  It records the head's EXACT animated x/y/scale so VV3WorldMaskDraw can
   reuse the real head position (walk/dance bob, carry offset) instead of a static
   recompute.  It does NOT draw -- drawing here would land under the front-hair; the wrapper
   at the handler call site draws last, on top.  (g_vv3_stash_* declared above.)
   args points at the 5 head-draw args on the exe stack, in push order:
   args[0]=headSprite  args[1]=x  args[2]=y  args[3]=scale(float bits)  args[4]=flag. */
__declspec(dllexport) void __stdcall VV3WorldMaskDrawAt(void *record, int *args)
{
    g_vv3_stash_record = record;
    g_vv3_stash_x      = args[1];
    g_vv3_stash_y      = args[2];
    g_vv3_stash_scale  = args[3];
    g_vv3_stash_m3010  = *(int *)(UINT_PTR)(VV3_WORLD_MGR + 0x3010);
    g_vv3_stash_valid  = 1;
}

/* Draw the stashed mask on top of the just-drawn head+hair.  Called from the post-hair
   convergence cave with NO args (all state is in the stash).  Draws through the SAME
   manager 0x58F6F8 so alpha/fade inherit; offsets are scale-relative + live-tunable. */
__declspec(dllexport) void __stdcall VV3WorldMaskFlush(void)
{
    void *record, *atlas;
    float fscale, liftsc, floor;
    int mask, cell, mx, my, x, y, scaleBits, facing;
    if (!g_vv3_stash_valid) {
        return;
    }
    g_vv3_stash_valid = 0;               /* consume: one mask draw per villager */
    record = g_vv3_stash_record;
    if (record == NULL) {
        return;
    }
    mask = VV3_GetMaskForRecord(record);
    if (mask <= 0) {
        return;
    }
    /* skip masks on carried/held villagers (they draw half-scale at the carrier's
       hand -- a stray tiny mask otherwise) */
    if (*((unsigned char *)record + VV3_WORLD_CARRIED_OFF) != 0) {
        return;
    }
    atlas = VV3GetMaskAtlas();
    if (atlas == NULL) {
        return;
    }
    x = g_vv3_stash_x;
    y = g_vv3_stash_y;
    scaleBits = g_vv3_stash_scale;
    fscale = *(float *)&scaleBits;
    /* FACING: read the villager's 0..7 direction from the RECORD (record+0xF18, VV5's
       direct head-column analog; changes as villagers turn).  Offset + remap are
       live-tunable.  g_vv3_world_facing >= 0 forces a column. */
    if (g_vv3_world_facing >= 0) {
        facing = g_vv3_world_facing & 7;
    } else {
        facing = ((*(int *)((unsigned char *)record + g_vv3_world_facing_off))
                  + g_vv3_world_facing_remap) & 7;
    }
    cell = (mask - 1) * VV3_WORLD_ATLAS_COLS + facing;
    /* child lift boost: floor the scale used for the LIFT (not the draw) so small
       villagers still lift the tall cell onto the head */
    liftsc = fscale;
    floor = g_vv3_world_liftfloor * 0.01f;
    if (liftsc < floor) {
        liftsc = floor;
    }
    mx = x + (int)(g_vv3_world_dx * fscale);
    my = y - (int)(g_vv3_world_lift * liftsc) + (int)(g_vv3_world_dy * fscale);
    __asm {
        mov  eax, scaleBits              /* a6 = same scale the head used */
        push eax
        push cell
        push my
        push mx
        push atlas
        mov  ecx, VV3_WORLD_MGR
        mov  edx, VV3_WORLD_DRAW_FN
        call edx                         /* sub_42E510(mgr, atlas, mx, my, cell, scale) */
    }
}

/* ================= Change Appearance for All (village-wide) ================
   Mirrors VV2's design: EVERYTHING is DLL-side, so the exe stays a thin one-call
   bridge (low risk).  vv3_apply_for_all iterates the villager record array and
   applies the dialog's choices: Head/Body are INDEPENDENT per-sex (a >=0 value
   overwrites +0xDF0/+0xDF4 for that sex; -1 = leave alone), and the MASK is one
   mutually-exclusive choice (mask_mode) written through VV3_SetMaskForRecord (the
   fingerprint-guarded table + sidecar) -- never the record/save.
     mask_mode: 0 = OFF (use the per-sex mask cyclers mask_m/mask_f)
                1 = VV5-style   2 = Random   3 = Equal
                4..9 = a single mask for everyone (4=None .. 9=Chief -> byte 0..5) */
#define VV3_HEAD_OFF 0xDF0
#define VV3_BODY_OFF 0xDF4

static unsigned int caf_rng;                 /* xorshift32, seeded from GetTickCount */
static unsigned int caf_rand(void) {
    unsigned int x = caf_rng ? caf_rng : (caf_rng = GetTickCount() | 1u);
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    caf_rng = x;
    return x;
}

static void vv3_apply_for_all(int head_m, int body_m, int mask_m,
                              int head_f, int body_f, int mask_f, int mask_mode) {
    unsigned char *rec = (unsigned char *)(UINT_PTR)VV3_REC_BASE;
    int slots = *(int *)(UINT_PTR)VV3_SLOTS_PTR;
    int idx[256], sex[256], order[256];
    unsigned char maskof[256];
    int n = 0, chief = -1, i, s;
    if (slots > 256) slots = 256;
    for (i = 0; i < slots; ++i, rec += VV3_STRIDE) {
        if (rec[VV3_ACTIVE] == 0) continue;
        if (*(int *)(rec + VV3_HEALTH) <= 0) continue;
        idx[n] = i;
        sex[n] = rec[VV3_GENDER] != 0;           /* 1 = female */
        if (rec[VV3_CHIEF] != 0) chief = n;       /* the robe-wearing Tribal Chief */
        ++n;
    }
    /* Head/Body: independent per-sex, always applied when >= 0. */
    for (i = 0; i < n; ++i) {
        unsigned char *r = (unsigned char *)(UINT_PTR)(VV3_REC_BASE + idx[i] * VV3_STRIDE);
        int h = sex[i] ? head_f : head_m;
        int b = sex[i] ? body_f : body_m;
        if (h >= 0) *(int *)(r + VV3_HEAD_OFF) = h;
        if (b >= 0) *(int *)(r + VV3_BODY_OFF) = b;
    }
    /* Mask: one exclusive behaviour. */
    if (mask_mode == 0) {                         /* OFF: per-sex mask cyclers */
        for (i = 0; i < n; ++i) {
            int m = sex[i] ? mask_f : mask_m;
            if (m >= 0)
                VV3_SetMaskForRecord((void *)(UINT_PTR)(VV3_REC_BASE + idx[i] * VV3_STRIDE), m);
        }
        return;
    }
    if (mask_mode >= 4) {                          /* single mask for everyone */
        int m = mask_mode - 4;                     /* 4=None(0) .. 9=Chief(5) */
        for (i = 0; i < n; ++i)
            VV3_SetMaskForRecord((void *)(UINT_PTR)(VV3_REC_BASE + idx[i] * VV3_STRIDE), m);
        return;
    }
    if (mask_mode == 2) {                          /* Random (incl. None) */
        for (i = 0; i < n; ++i)
            VV3_SetMaskForRecord((void *)(UINT_PTR)(VV3_REC_BASE + idx[i] * VV3_STRIDE),
                                 (int)(caf_rand() % 6u));
        return;
    }
    if (mask_mode == 1) {                          /* VV5-style proportions */
        static const int quota[3] = {4, 7, 10};    /* purple, red, orange caps    */
        static const int mval[3]  = {4, 3, 2};     /* -> byte 4/3/2               */
        int qi, got, p = 0;
        for (i = 0; i < n; ++i) { order[i] = i; maskof[i] = 1; }   /* default Blue */
        for (i = n - 1; i > 0; --i) {              /* Fisher-Yates shuffle */
            int j = (int)(caf_rand() % (unsigned)(i + 1));
            int t = order[i]; order[i] = order[j]; order[j] = t;
        }
        /* Chief mask -> the robe-wearing Tribal Chief (+0xE80); if there is NO Tribal
           Chief, give the Chief mask to a random villager instead (owner's spec). */
        if (chief < 0 && n > 0) chief = (int)(caf_rand() % (unsigned)n);
        if (chief >= 0) maskof[chief] = 5;
        for (qi = 0; qi < 3; ++qi) {
            for (got = 0; got < quota[qi] && p < n; ) {
                int a = order[p++];
                if (a == chief) continue;
                if (maskof[a] != 1) continue;
                maskof[a] = (unsigned char)mval[qi];
                ++got;
            }
        }
        for (i = 0; i < n; ++i)
            VV3_SetMaskForRecord((void *)(UINT_PTR)(VV3_REC_BASE + idx[i] * VV3_STRIDE), maskof[i]);
        return;
    }
    if (mask_mode == 3) {                          /* Equal, balanced M/F */
        int males[256], females[256], nm = 0, nf = 0, k = 0, mi = 0, fi = 0;
        for (i = 0; i < n; ++i) { if (sex[i]) females[nf++] = i; else males[nm++] = i; }
        for (i = nm - 1; i > 0; --i) { int j = (int)(caf_rand()%(unsigned)(i+1)); int t=males[i]; males[i]=males[j]; males[j]=t; }
        for (i = nf - 1; i > 0; --i) { int j = (int)(caf_rand()%(unsigned)(i+1)); int t=females[i]; females[i]=females[j]; females[j]=t; }
        while (mi < nm || fi < nf) {               /* interleave M,F,M,F -> balanced */
            if (mi < nm) { VV3_SetMaskForRecord((void*)(UINT_PTR)(VV3_REC_BASE+idx[males[mi++]]*VV3_STRIDE), (k++%5)+1); }
            if (fi < nf) { VV3_SetMaskForRecord((void*)(UINT_PTR)(VV3_REC_BASE+idx[females[fi++]]*VV3_STRIDE), (k++%5)+1); }
        }
        (void)s;
        return;
    }
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
        wsprintfA(message, "Fully mastered %u villagers.", changed);
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
#define VV3_HEAD_COUNT 30
#define VV3_BODY_COUNT 29
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
    if (head) {
        *head = vv3_appearance_head;
    }
    if (body) {
        *body = vv3_appearance_body;
    }
    /* Commit the mask to the DLL-owned table; the record/save are never written. */
    VV3_SetMaskForRecord(record, vv3_appearance_mask);
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

static INT_PTR CALLBACK vv3_caf_dialog(HWND w, UINT msg, WPARAM wp, LPARAM lp) {
    (void)lp;
    if (msg == WM_INITDIALOG) {
        int r;
        center_topmost_on_owner(w);
        for (r = 0; r < 10; ++r)
            CheckDlgButton(w, IDC_CAF_MODE_FIRST + r, r == caf_mask_mode ? BST_CHECKED : BST_UNCHECKED);
        SetDlgItemTextA(w, IDC_CAF_M_MASK_T, caf_mask_text(caf_m_mask));
        SetDlgItemTextA(w, IDC_CAF_F_MASK_T, caf_mask_text(caf_f_mask));
        caf_set_mask_enable(w);
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
    int changed;
    caf_m_head = caf_m_body = caf_m_mask = -1;
    caf_f_head = caf_f_body = caf_f_mask = -1;
    caf_mask_mode = 0;

    begin_modal_over_game();
    result = DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_VV3_APPEARANCE_ALL),
                             GetForegroundWindow(), vv3_caf_dialog, 0);
    if (result != 1) {
        return 0;
    }
    changed = (caf_m_head >= 0 || caf_m_body >= 0 || caf_f_head >= 0 || caf_f_body >= 0
               || caf_mask_mode != 0 || caf_m_mask >= 0 || caf_f_mask >= 0);
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
    if (caf_m_head >= 0 || caf_f_head >= 0) {
        if (MessageBoxA(GetForegroundWindow(),
                "Warning: This will change the head genetics of every villager of the chosen sex.",
                "Origins Upgrades", MB_OKCANCEL | MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND)
            != IDOK) {
            return 0;
        }
    }
    *tech -= VV3_CAF_COST;
    vv3_apply_for_all(caf_m_head, caf_m_body, caf_m_mask,
                      caf_f_head, caf_f_body, caf_f_mask, caf_mask_mode);
    MessageBoxA(GetForegroundWindow(),
        "Change Appearance for All applied.",
        "Origins Upgrades", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 1;
}
