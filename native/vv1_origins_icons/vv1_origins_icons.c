#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#ifndef VV_AGE_OFFSET
#define VV_AGE_OFFSET 0x348
#endif
#ifndef VV_SKILL_FARMING_OFFSET
#define VV_SKILL_FARMING_OFFSET 0x3BC
#endif
#ifndef VV_SKILL_BUILDING_OFFSET
#define VV_SKILL_BUILDING_OFFSET 0x3C0
#endif
#ifndef VV_SKILL_RESEARCH_OFFSET
#define VV_SKILL_RESEARCH_OFFSET 0x3C4
#endif
#ifndef VV_SKILL_HEALING_OFFSET
#define VV_SKILL_HEALING_OFFSET 0x3C8
#endif
#ifndef VV_SKILL_PARENTING_OFFSET
#define VV_SKILL_PARENTING_OFFSET 0x3CC
#endif
#ifndef VV_LIKES_OFFSET
#define VV_LIKES_OFFSET 0x398
#endif
#ifndef VV_DISLIKES_OFFSET
#define VV_DISLIKES_OFFSET 0x3A8
#endif
#ifndef VV_LIKE_SLOT_COUNT
#define VV_LIKE_SLOT_COUNT 4
#endif
#ifndef VV_ALREADY_LIKES_TEXT
#define VV_ALREADY_LIKES_TEXT "Already 4 likes."
#endif
#ifndef VV_HEAD_OFFSET
#define VV_HEAD_OFFSET 0x360
#endif
#ifndef VV_CLOTHING_OFFSET
#define VV_CLOTHING_OFFSET 0x364
#endif
#ifndef VV_GENDER_OFFSET
#define VV_GENDER_OFFSET 0x350
#endif
#ifndef VV_GENDER_MALE
#define VV_GENDER_MALE 1
#endif
/* Purely cosmetic mask overlay choice (0 = none, 1..5 = mask variant).
   +0x374 is confirmed unused anywhere in the exact-build binary -- a
   full-.text capstone scan found zero static references to any of
   +0x374..+0x38B (24 contiguous free bytes), well clear of every other
   mapped field (the last real one before it is the +0x36C action-id
   check, the next is the +0x3D0 job-preference field from Equal
   Division of Labor). Deliberately NOT the native nursing-baby-icon
   flag at +0x29 -- that byte is real per-villager gameplay state (a
   genuinely nursing mother already has it set), so reusing it here
   would either double-draw over her real baby icon or silently steal
   it. This field is drawn by an entirely separate, additive render-loop
   hook that never reads or writes +0x29/+0x2A/+0x344. */
#ifndef VV_MASK_OFFSET
#define VV_MASK_OFFSET 0x374
#endif
#ifndef VV_MASK_COUNT
#define VV_MASK_COUNT 6
#endif

static HINSTANCE module_instance;

/* None of this DLL's three dialog templates (IDD_ORIGINS_TECH,
   IDD_ORIGINS_VILLAGER, IDD_ORIGINS_APPEARANCE -- see the .rc file's
   "DIALOGEX 0, 0, ..." lines) specify DS_CENTER, so without this,
   DialogBoxParamA places each one at literal screen pixel (0,0) -- the
   real display's extreme top-left corner. That is easy to miss by
   accident in a small windowed game, but VV1 is an old game rendered at
   a small logical resolution that SDL scales up to fill the real
   display (SDL_RenderSetLogicalSize is imported and used for this).
   Once the real display is much larger than the game's own logical
   resolution, as it always is in fullscreen, a dialog pinned at (0,0)
   is effectively unreachable rather than merely off-center.

   Centers on the owner window's own current rect -- which SDL keeps
   accurate to the real on-screen window, fullscreen or windowed, unlike
   the game's internal logical resolution -- then clamps to that owner's
   monitor work area so the title bar and buttons stay fully reachable
   even if the owner window is smaller than the dialog or sits near a
   monitor edge. */
static void center_dialog_on_owner(HWND dialog) {
    HWND owner = GetWindow(dialog, GW_OWNER);
    RECT dlg_rect;
    RECT owner_rect;
    MONITORINFO monitor_info;
    int width;
    int height;
    int x;
    int y;

    if (owner == NULL || !IsWindow(owner)) {
        owner = GetForegroundWindow();
        if (owner != NULL && !IsWindow(owner)) {
            owner = NULL;
        }
    }
    if (!GetWindowRect(dialog, &dlg_rect)) {
        return;
    }
    width = dlg_rect.right - dlg_rect.left;
    height = dlg_rect.bottom - dlg_rect.top;

    if (owner != NULL && GetWindowRect(owner, &owner_rect)) {
        x = owner_rect.left + ((owner_rect.right - owner_rect.left) - width) / 2;
        y = owner_rect.top + ((owner_rect.bottom - owner_rect.top) - height) / 2;
    } else {
        x = (GetSystemMetrics(SM_CXSCREEN) - width) / 2;
        y = (GetSystemMetrics(SM_CYSCREEN) - height) / 2;
    }

    monitor_info.cbSize = sizeof(monitor_info);
    if (GetMonitorInfo(
            MonitorFromWindow(
                owner != NULL ? owner : dialog,
                MONITOR_DEFAULTTONEAREST
            ),
            &monitor_info
        )) {
        const RECT *work_rect = &monitor_info.rcWork;
        if (x + width > work_rect->right) {
            x = work_rect->right - width;
        }
        if (y + height > work_rect->bottom) {
            y = work_rect->bottom - height;
        }
        if (x < work_rect->left) {
            x = work_rect->left;
        }
        if (y < work_rect->top) {
            y = work_rect->top;
        }
    }

    SetWindowPos(dialog, NULL, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
}

/* Reported: the game's own view goes black behind the dialog while it's
   open, and (more importantly) stays black even after it closes.
   Two earlier attempts at fixing this from inside this DLL both failed
   badly enough to need a live revert:

   1. Calling the game's own native fullscreen leave/enter pair directly
      (raw hardcoded VAs through an engine singleton pointer) -- crashed
      the game immediately: the singleton's address turned out to fall
      inside a byte range this repo's own Origins village-wide payload
      already claims as scratch cave space, so on a patched build that
      address no longer holds what it holds in the stock exe.
   2. Forcing a synchronous RedrawWindow(..., RDW_UPDATENOW | RDW_FRAME)
      on the owner right after DialogBoxParamA returned -- hung the whole
      game instead (confirmed via process inspection: no crash dialog,
      just an unresponsive process that had to be force-closed), almost
      certainly by reentering something in SDL's or the driver's
      fullscreen present path from inside this DLL's own call stack
      before the game's own loop had a chance to resume on its own.

   The actual root cause (found by checking VV2's already-merged,
   playtest-confirmed fix for the identical symptom -- VV2 shares this
   exact file) is neither of those: in exclusive SDL fullscreen, the
   game's own SDL runtime minimizes the window the instant it loses
   focus to our modal dialog, dropping the player to the bare desktop
   behind it -- which is what reads as "black" and, apparently, is also
   what the freeze-on-close was: restoring from a real Win32-minimized
   state while SDL still believes it owns exclusive fullscreen is a
   known-hazardous transition. vv1_prep_fullscreen below heads this off
   before it happens, and vv1_surface_dialog (called from each dialog's
   own WM_INITDIALOG) makes sure the dialog itself is actually visible
   above the game's topmost fullscreen surface once it doesn't minimize
   out from under it. Neither call touches game internals: both are
   standard, documented Win32/SDL APIs against the game's own
   already-loaded SDL2.dll and our own dialog window. */
static void vv1_surface_dialog(HWND window) {
    SetWindowPos(
        window, HWND_TOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    );
    SetForegroundWindow(window);
}

static void vv1_prep_fullscreen(void) {
    HMODULE sdl = GetModuleHandleA("SDL2.dll");
    if (sdl != NULL) {
        typedef int(__cdecl * set_hint_t)(const char *, const char *);
        set_hint_t set_hint = (set_hint_t)GetProcAddress(sdl, "SDL_SetHint");
        if (set_hint != NULL) {
            set_hint("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0");
        }
    }
}

enum {
    IDD_ORIGINS_TECH = 201,
    IDD_ORIGINS_VILLAGER = 202,
    IDD_ORIGINS_APPEARANCE = 203,
    ID_BUY_FIRST = 1000,
    ID_BUY_LAST = 1010,
    ID_CHECK_FIRST = 1100,
    /* IDC_HEAD_PREVIEW/IDC_BODY_PREVIEW: owner-draw STATIC controls that
       preview the real head/body sprite cropped from the stock game art
       (see appearance_draw below) -- these reuse the same control IDs the
       plain-text labels used before this dialog grew real art. */
    IDC_HEAD_PREVIEW = 2000,
    ID_HEAD_PREV = 2001,
    ID_HEAD_NEXT = 2002,
    IDC_BODY_PREVIEW = 2010,
    ID_BODY_PREV = 2011,
    ID_BODY_NEXT = 2012,
    ID_MASK_PREV = 2020,
    IDC_MASK_LABEL = 2021,
    ID_MASK_NEXT = 2022,
    IDB_HEAD_M = 3001,
    IDB_HEAD_F = 3002,
    IDB_BODY_M = 3011,
    IDB_BODY_F = 3012,
    STATE_VILLAGER = 0x10000,
    STATE_VILLAGE_WIDE = 0x20000,
    STATE_RUNNING_ONLY = 0x40000,
    STATE_VILLAGE_WIDE_BUY = 0x80000
};

/* Every strip built by scripts/build_vv1_appearance_bitmaps.py is a single
   40-wide column holding all 20 variant rows stacked vertically (one
   villager-record index per row), 65 pixels tall each -- exactly the cell
   geometry the stock exe's own sprite-sheet loader computes for these same
   source images (see that script's docstring for the decompiled proof). */
#define APPEARANCE_CELL_W 40
#define APPEARANCE_CELL_H 65

/* Only one appearance picker can be open at a time (it is a modal dialog),
   so a single file-scope slot for its working state is sufficient -- this
   mirrors module_instance above, which is the same kind of single-instance
   global already used in this file. The tech-point balance check and
   charge live in the caller (the same reused code path every other
   Villager Upgrades row already charges through), not here: this dialog
   only ever previews and either keeps or reverts the head/body fields.

   valid_count is not a fixed 20 for both fields: the villager-creation
   code assigns head and body their random starting value from RNG(19)
   for male villagers and RNG(20) for everyone else (confirmed by
   decompiling the exact-build initializer), so male villagers only have
   19 valid values (0-18) for both fields, not 20 -- cycling through 19
   for a male villager would write a value the stock renderer was never
   given a sprite for. */
static struct {
    unsigned char *villager;
    int original_head;
    int original_body;
    int original_mask;
    int valid_count;
    int male;
    /* Set once the player accepts the head-genetics warning below, so it
       only ever shows once per picker session (the OFFICIAL spreadsheet's
       "changing it first shows..." wording), not on every arrow click. */
    int head_warned;
} appearance_state;

static const char *vv1_mask_name(int mask) {
    switch (mask) {
        case 1: return "Blue Mask";
        case 2: return "Orange Mask";
        case 3: return "Red Mask";
        case 4: return "Purple Mask";
        case 5: return "Tribal Chief Mask";
        default: return "(None)";
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        module_instance = instance;
    }
    return TRUE;
}

static INT_PTR CALLBACK upgrade_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        int villager_menu = (lparam & STATE_VILLAGER) != 0;
        int village_wide_buy = (lparam & STATE_VILLAGE_WIDE_BUY) != 0;
        int row_count = villager_menu
            ? 5
            : ((lparam & STATE_RUNNING_ONLY) != 0
                ? 7
                : ((lparam & STATE_VILLAGE_WIDE) != 0 ? 9 : 6));
        int row;
        center_dialog_on_owner(window);
        vv1_surface_dialog(window);
        /* Rows 9/10 (Equal Division of Labor) are outside row_count's own
           tiered range below -- unlike rows 6-8, they aren't gated behind
           the optional village-wide extension payload (STATE_VILLAGE_WIDE),
           they're always present, and they never have an "owned" state to
           report (no checkmark, no Remove/Unavailable text) -- so they
           only need their checkmark hidden here and are otherwise left at
           the .rc template's own default (Buy, enabled). Hidden up to 11,
           not just row_count's own max of 9, so their checkmarks (IDs
           1109/1110) don't default to visible like every other ICON
           control in this dialog does when nothing hides it first. */
        for (row = 0; row < 11; ++row) {
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
        }
        for (row = 0; row < row_count; ++row) {
            if ((lparam & (1 << row)) != 0) {
                ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
                if (villager_menu) {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Done");
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
                } else if (village_wide_buy && row >= 6) {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Buy");
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), TRUE);
                } else {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Remove");
                }
            } else if ((lparam & (1 << (8 + row))) != 0) {
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
            }
        }
        return TRUE;
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command >= ID_BUY_FIRST && command <= ID_BUY_LAST) {
            EndDialog(window, (INT_PTR)(command - ID_BUY_FIRST));
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
    int resource = villager_menu ? IDD_ORIGINS_VILLAGER : IDD_ORIGINS_TECH;
    HWND owner = GetForegroundWindow();
    int result;
    vv1_prep_fullscreen();
    if (villager_menu) {
        dialog_state |= STATE_VILLAGER;
    }
    result = (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(resource),
        owner,
        upgrade_dialog,
        dialog_state
    );
    return result;
}

/* Crops row `index` (one villager-record value = one 40x65 row) out of
   the strip for the current villager's sex and stretches it to fill the
   owner-draw control's actual rect, the same StretchBlt/COLORONCOLOR
   approach the stock renderer itself would use for an arbitrary preview
   size. */
static void appearance_draw(DRAWITEMSTRUCT *item, int bitmap_id, int index) {
    RECT rc = item->rcItem;
    int width = rc.right - rc.left;
    int height = rc.bottom - rc.top;
    HBRUSH background = CreateSolidBrush(RGB(236, 236, 236));
    HBITMAP bitmap;
    HDC source;
    HBITMAP previous;

    FillRect(item->hDC, &rc, background);
    DeleteObject(background);

    bitmap = LoadBitmapA(module_instance, MAKEINTRESOURCEA(bitmap_id));
    if (bitmap == NULL) {
        return;
    }
    source = CreateCompatibleDC(item->hDC);
    previous = (HBITMAP)SelectObject(source, bitmap);

    SetStretchBltMode(item->hDC, COLORONCOLOR);
    StretchBlt(
        item->hDC, rc.left, rc.top, width, height,
        source, 0, index * APPEARANCE_CELL_H, APPEARANCE_CELL_W, APPEARANCE_CELL_H,
        SRCCOPY
    );

    SelectObject(source, previous);
    DeleteDC(source);
    DeleteObject(bitmap);
}

static void appearance_repaint(HWND window, int control_id) {
    InvalidateRect(GetDlgItem(window, control_id), NULL, TRUE);
}

static void appearance_revert(void) {
    *(int *)(appearance_state.villager + VV_HEAD_OFFSET) = appearance_state.original_head;
    *(int *)(appearance_state.villager + VV_CLOTHING_OFFSET) = appearance_state.original_body;
    *(appearance_state.villager + VV_MASK_OFFSET) = (unsigned char)appearance_state.original_mask;
}

/* The head field is hereditary (it's the one the villager's children
   inherit from), so the OFFICIAL Origins Upgrade Prompts spreadsheet
   requires a one-time OK/Cancel warning the first time the player
   actually tries to change it in this picker session -- Cancel leaves
   that specific arrow click without effect, no field write at all.
   Returns 1 to proceed (already warned, or just accepted), 0 to abort
   the click that triggered it. */
static int vv1_confirm_head_genetics_warning(HWND window) {
    if (appearance_state.head_warned) {
        return 1;
    }
    if (MessageBoxA(
            window,
            "Warning: This will change the villager's head genetics.",
            "Villager Upgrades",
            MB_OKCANCEL | MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND
        ) != IDOK) {
        return 0;
    }
    appearance_state.head_warned = 1;
    return 1;
}

/* Writes each tentative value straight into the live villager record so
   the stock renderer (which already reads these exact fields every
   frame, the same field the F6 clothing-cycle cheat uses for body) shows
   the change immediately behind this dialog -- no separate preview
   rendering is built or needed here. Reverted on Cancel/close. On OK,
   returns 1 if the head or body actually differs from what it was when
   the picker opened (the caller charges and keeps the change), or 2 if
   OK was pressed but nothing was actually changed (the caller charges
   nothing and reports that explicitly, per the OFFICIAL spreadsheet --
   fields already match their originals in that case, so there is
   nothing to revert either). The tech-point balance check and charge
   are the caller's job (the exact same charge code every other Villager
   Upgrades row already uses) -- this dialog never touches tech points,
   only the head/body fields. */
static INT_PTR CALLBACK appearance_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    (void)lparam;
    if (message == WM_INITDIALOG) {
        /* appearance_state was already populated by ShowOriginsAppearancePicker
           before this dialog was created; WM_DRAWITEM below paints the
           starting values on the dialog's own first paint, nothing else to
           do here besides positioning (see center_dialog_on_owner). The
           mask row has no owner-draw preview (it's a plain text label,
           not a bitmap strip cell), so its starting text is set directly
           here rather than through WM_DRAWITEM. */
        center_dialog_on_owner(window);
        vv1_surface_dialog(window);
        SetDlgItemTextA(
            window,
            IDC_MASK_LABEL,
            vv1_mask_name(*(appearance_state.villager + VV_MASK_OFFSET))
        );
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        DRAWITEMSTRUCT *item = (DRAWITEMSTRUCT *)lparam;
        if (item->CtlID == IDC_HEAD_PREVIEW) {
            appearance_draw(
                item,
                appearance_state.male ? IDB_HEAD_M : IDB_HEAD_F,
                *(int *)(appearance_state.villager + VV_HEAD_OFFSET)
            );
            return TRUE;
        }
        if (item->CtlID == IDC_BODY_PREVIEW) {
            appearance_draw(
                item,
                appearance_state.male ? IDB_BODY_M : IDB_BODY_F,
                *(int *)(appearance_state.villager + VV_CLOTHING_OFFSET)
            );
            return TRUE;
        }
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        int count = appearance_state.valid_count;
        int *head = (int *)(appearance_state.villager + VV_HEAD_OFFSET);
        int *body = (int *)(appearance_state.villager + VV_CLOTHING_OFFSET);
        if (command == ID_HEAD_PREV) {
            if (!vv1_confirm_head_genetics_warning(window)) {
                return TRUE;
            }
            *head = (*head + count - 1) % count;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == ID_HEAD_NEXT) {
            if (!vv1_confirm_head_genetics_warning(window)) {
                return TRUE;
            }
            *head = (*head + 1) % count;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == ID_BODY_PREV) {
            *body = (*body + count - 1) % count;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == ID_BODY_NEXT) {
            *body = (*body + 1) % count;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == ID_MASK_PREV || command == ID_MASK_NEXT) {
            unsigned char *mask = appearance_state.villager + VV_MASK_OFFSET;
            int next = command == ID_MASK_PREV
                ? (*mask + VV_MASK_COUNT - 1) % VV_MASK_COUNT
                : (*mask + 1) % VV_MASK_COUNT;
            *mask = (unsigned char)next;
            SetDlgItemTextA(window, IDC_MASK_LABEL, vv1_mask_name(next));
            return TRUE;
        }
        if (command == IDOK) {
            int changed = (*head != appearance_state.original_head)
                || (*body != appearance_state.original_body)
                || (*(appearance_state.villager + VV_MASK_OFFSET)
                    != (unsigned char)appearance_state.original_mask);
            EndDialog(window, changed ? 1 : 2);
            return TRUE;
        }
        if (command == IDCANCEL) {
            appearance_revert();
            EndDialog(window, 0);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        appearance_revert();
        EndDialog(window, 0);
        return TRUE;
    }
    return FALSE;
}

__declspec(dllexport) int __stdcall ShowOriginsAppearancePicker(
    int villager_ptr
) {
    unsigned char *villager = (unsigned char *)(UINT_PTR)(unsigned int)villager_ptr;
    HWND owner;
    int result;
    if (villager == NULL) {
        return 0;
    }
    appearance_state.villager = villager;
    appearance_state.original_head = *(int *)(villager + VV_HEAD_OFFSET);
    appearance_state.original_body = *(int *)(villager + VV_CLOTHING_OFFSET);
    appearance_state.original_mask = *(villager + VV_MASK_OFFSET);
    appearance_state.male = *(int *)(villager + VV_GENDER_OFFSET) == VV_GENDER_MALE;
    appearance_state.valid_count = appearance_state.male ? 19 : 20;
    appearance_state.head_warned = 0;
    vv1_prep_fullscreen();
    owner = GetForegroundWindow();
    result = (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_ORIGINS_APPEARANCE),
        owner,
        appearance_dialog,
        (LPARAM)(UINT_PTR)villager
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
            if (*(int *)(villager + VV_AGE_OFFSET) <= 100) {
                dialog_state |= 1 << 0;
            }
            if (*(int *)(villager + VV_SKILL_FARMING_OFFSET) == 100
                && *(int *)(villager + VV_SKILL_BUILDING_OFFSET) == 100
                && *(int *)(villager + VV_SKILL_RESEARCH_OFFSET) == 100
                && *(int *)(villager + VV_SKILL_HEALING_OFFSET) == 100
                && *(int *)(villager + VV_SKILL_PARENTING_OFFSET) == 100) {
                dialog_state |= 1 << 1;
            }
            for (row = 0; row < VV_LIKE_SLOT_COUNT; ++row) {
                int like = *(int *)(villager + VV_LIKES_OFFSET + row * 4);
                if (like == 38) {
                    running_like = 1;
                } else if (like == -1) {
                    available_like = 1;
                }
                if (*(int *)(villager + VV_DISLIKES_OFFSET + row * 4) == 38) {
                    running_dislike = 1;
                }
            }
            if (running_like) {
                dialog_state |= 1 << 2;
            } else if (!available_like) {
                dialog_state |= 1 << (8 + 2);
            }
            if (*(int *)(villager + VV_AGE_OFFSET) == 360) {
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

/* Row names for the confirmation prompt below. Kept here rather than as
   ASM string-table entries: the .shr string budget is already tight, and
   this is the only place these particular names are ever shown, so
   there's no reason to spend .shr bytes on them at all. */
static const char *vv1_tech_row_name(int row) {
    switch (row) {
    case 0: return "Time Warp";
    case 1: return "Island Event";
    case 2: return "Barrel of Babies";
    case 3: return "Tech Point Doubler";
    case 4: return "Food Point Doubler";
    case 5: return "Full Heal / Cure All";
    case 6: return "Grant Running to All Villagers";
    case 7: return "Grant Full Mastery to All Villagers";
    case 8: return "All Villagers are Exactly 18";
    case 9: return "Equal Division of Labor (Includes Parenting)";
    case 10: return "Equal Division of Labor (No Parenting)";
    default: return "Origins upgrade";
    }
}

/* Correct singular/plural for a villager count, matching the OFFICIAL
   Origins Upgrade Prompts spreadsheet's own note: "counts use correct
   singular/plural ('1 Villager' vs '3 Villagers')". */
static const char *vv1_vpl(unsigned int n) { return n == 1 ? "Villager" : "Villagers"; }

/* Renders value with thousands separators ("1000000" -> "1,000,000") for
   the confirmation prompt below -- wsprintfA's %d has no such thing, and
   the OFFICIAL spreadsheet's confirm wording always shows costs comma-
   formatted. out must be at least 16 bytes; every VV1 upgrade cost is at
   most 7 digits (1,000,000), so that is always enough room. */
static void vv1_format_cost(int value, char *out) {
    char digits[16];
    int count = 0;
    int position;
    int written = 0;
    if (value < 0) {
        value = 0;
    }
    do {
        digits[count++] = (char)('0' + (value % 10));
        value /= 10;
    } while (value > 0 && count < (int)sizeof(digits));
    for (position = count - 1; position >= 0; --position) {
        out[written++] = digits[position];
        if (position > 0 && (position % 3) == 0) {
            out[written++] = ',';
        }
    }
    out[written] = '\0';
}

static const char *vv1_detail_row_name(int row) {
    switch (row) {
    case 0: return "Grant Youth";
    case 1: return "Grant Full Mastery";
    case 2: return "Grant Running";
    case 3: return "Set Age to 18";
    case 4: return "Change Appearance";
    default: return "Origins upgrade";
    }
}

/* Shared confirmation prompt: every purchasable row on both the Tech
   screen (including its Village-Wide rows) and the Villager Details
   screen routes through this before any charge or change happens.
   Names the row and its exact cost rather than a generic warning, and
   uses OK/Cancel (not Yes/No) -- matching the wording style already
   proposed for VV5's own Task9 Origins upgrades
   (native/vv5_task9_origins/vv5_task9_origins.c's ConfirmVV5Task9Action)
   for parity across games. Only ever called for a real purchase, not
   for removing an owned doubler -- the caller (menu) only reaches this
   on the Buy path, after it already knows the row isn't being removed. */
__declspec(dllexport) int __stdcall ShowOriginsPermanentChangeConfirm(
    int is_detail,
    int row,
    int cost
) {
    char message[192];
    char cost_text[16];
    const char *name = is_detail ? vv1_detail_row_name(row) : vv1_tech_row_name(row);
    vv1_format_cost(cost, cost_text);
    wsprintfA(
        message,
        "Do you want to buy %s for %s tech points?\r\nPress OK to confirm, or Cancel.",
        name,
        cost_text
    );
    return MessageBoxA(
        GetForegroundWindow(),
        message,
        is_detail ? "Villager Upgrades" : "Origins Upgrades",
        MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND
    ) == IDOK;
}

/* Full Heal/Cure All Villagers: the .shr helper only calls this once it
   already knows at least one villager was sick or below full health (and
   has already charged for it), so this never needs its own "nothing
   happened" branch -- that message is a plain string shown directly by
   the helper without ever resolving this export. */
__declspec(dllexport) int __stdcall ShowOriginsCureResult(
    int sick_cured,
    int healed_restored
) {
    char message[128];
    wsprintfA(
        message,
        "Cured sickness from %d villagers.\r\n\r\nRestored %d villagers to full health.",
        sick_cured,
        healed_restored
    );
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}

/* Grant Running to All Villagers: reports each outcome on its own line, in
   the exact order and wording the OFFICIAL Origins Upgrade Prompts
   spreadsheet specifies -- granted, then dislikes removed, then each skip
   reason, with correct singular/plural throughout. granted comes from a
   fixed .shr scratch dword the native payload's running_va writes right
   before returning (see RUNNING_GRANTED_VA in
   scripts/build_vv1_origins_feature.py and report_running_granted in
   scripts/build_village_wide_origins_features.py) -- there was no register
   left to carry it back through directly. Called only for command 6
   (Running); command 8 (Set All Villagers to 18) now routes its own
   result through the generic ShowOriginsRowMessage below instead, since
   the spreadsheet gives it a plain "completed." line with no counts. */
__declspec(dllexport) int __stdcall ShowOriginsVillageWideResult(
    int command,
    int granted,
    int full_like_skipped,
    int already_running_skipped,
    int removed_running_dislike
) {
    char message[384];
    char line[128];
    if (command != 6) {
        return 0;
    }
    wsprintfA(
        message,
        "Granted Running to %d %s.",
        granted, vv1_vpl(granted)
    );
    wsprintfA(
        line,
        "\r\n\r\nRemoved a Running dislike from %d %s.",
        removed_running_dislike, vv1_vpl(removed_running_dislike)
    );
    lstrcatA(message, line);
    wsprintfA(
        line,
        "\r\n\r\nSkipped %d %s: already like Running.",
        already_running_skipped, vv1_vpl(already_running_skipped)
    );
    lstrcatA(message, line);
    wsprintfA(
        line,
        "\r\n\r\nSkipped %d %s: already have %d likes.",
        full_like_skipped, vv1_vpl(full_like_skipped), VV_LIKE_SLOT_COUNT
    );
    lstrcatA(message, line);
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}

/* All Villagers are 18: granted/already/golden_child come from three fixed
   .shr scratch dwords age_va (in the shared village-wide script,
   report_age_granted opt-in) zeroes at its own start and increments as it
   goes (AGE_GRANTED_VA/AGE_ALREADY_VA/AGE_GOLDEN_CHILD_VA) -- same shape
   as ShowOriginsMasteryResult's own granted/already-satisfied pairing,
   extended with one more count. Restored per the OFFICIAL Origins Upgrade
   Prompts spreadsheet, which asks for a counted result here after all (an
   earlier pass had briefly simplified this row to a plain "completed."
   line to match what the spreadsheet said at the time).

   The Golden Child is always excluded (hardcoded to stay a child, per the
   user) regardless of how many the village happens to have -- age_va's
   own per-villager loop compares each candidate against the live
   dword ptr [0x48B614] singleton (the stock game's own lazily-created
   "current Golden Child" pointer, confirmed via disassembly of its
   matching getter/destructor pair) rather than assuming there is exactly
   one, so this reports however many were actually skipped for that
   reason, same as every other count here. */
__declspec(dllexport) int __stdcall ShowOriginsAgeResult(
    int granted,
    int already,
    int golden_child
) {
    char message[256];
    char line[128];
    wsprintfA(
        message,
        "Set %d %s to Age 18.",
        granted, vv1_vpl(granted)
    );
    wsprintfA(
        line,
        "\r\n\r\nSkipped %d %s: already exactly 18.",
        already, vv1_vpl(already)
    );
    lstrcatA(message, line);
    wsprintfA(
        line,
        "\r\n\r\nSkipped %d %s: is Golden Child.",
        golden_child, vv1_vpl(golden_child)
    );
    lstrcatA(message, line);
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}

/* Equal Division of Labor (both the Includes-Parenting and No-Parenting
   Tech screen rows share this one export): granted/golden_child_skipped
   come from two fixed .shr scratch dwords equal_division_core zeroes at
   its own start and increments as it goes (VV1-only, not part of the
   shared cross-game village-wide extension -- see equal_division_core's
   own comment in build_vv1_origins_feature.py). Unlike Grant Running/
   Mastery/Age, there is no "already correct" state to skip past: every
   eligible villager's job preference is reassigned unconditionally, so
   granted is simply how many villagers were actually eligible (active,
   alive, not the Golden Child).

   male_counts/female_counts each point at 5 more scratch dwords indexed
   by the same table position equal_division_core's own cyclic index
   (esi) uses -- 0=Farming, 1=Building, 2=Research, 3=Healing,
   4=Breeding, matching EQUAL_DIVISION_TABLE_BYTES's own on-screen Skills
   order, not the raw 1-5 job-preference codes written to the record.
   include_parenting selects how many of the 5 entries to report (4 for
   the No-Parenting row, which never reaches the trailing Breeding
   entry). */
__declspec(dllexport) int __stdcall ShowOriginsEqualDivisionResult(
    int granted,
    int golden_child_skipped,
    int include_parenting,
    const int *male_counts,
    const int *female_counts
) {
    static const char *job_names[5] = {
        "Farming", "Building", "Research", "Healing", "Breeding"
    };
    char message[768];
    char line[192];
    int job_count = include_parenting ? 5 : 4;
    int i;
    wsprintfA(
        message,
        "Set %d %s' Job Preferences.",
        granted, vv1_vpl(granted)
    );
    for (i = 0; i < job_count; ++i) {
        int total = male_counts[i] + female_counts[i];
        wsprintfA(
            line,
            "\r\n\r\n%s: %d %s (%d Male, %d Female).",
            job_names[i], total, vv1_vpl(total),
            male_counts[i], female_counts[i]
        );
        lstrcatA(message, line);
    }
    wsprintfA(
        line,
        "\r\n\r\nSkipped %d %s: is Golden Child.",
        golden_child_skipped, vv1_vpl(golden_child_skipped)
    );
    lstrcatA(message, line);
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}

/* Grant Full Mastery to All Villagers: granted/already_mastered come from
   two fixed .shr scratch dwords mastery_va zeroes at its own start and
   increments as it goes (MASTERY_GRANTED_VA/MASTERY_ALREADY_VA) -- unlike
   Running's single count, mastery_va also has an early-exit failure path
   (mastery_failure) that a stack-based accumulator couldn't survive
   cleanly, so scratch memory was the only safe option for either count. */
__declspec(dllexport) int __stdcall ShowOriginsMasteryResult(
    int granted,
    int already_mastered
) {
    char message[192];
    char line[128];
    wsprintfA(
        message,
        "Granted Full Mastery to %d %s.",
        granted, vv1_vpl(granted)
    );
    wsprintfA(
        line,
        "\r\n\r\nSkipped %d %s: already fully mastered.",
        already_mastered, vv1_vpl(already_mastered)
    );
    lstrcatA(message, line);
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}

/* No-change wording for the Tech screen's three village-wide rows (Grant
   Running to All Villagers, Grant Full Mastery to All Villagers, Set All
   Villagers to 18) -- the only three Tech rows the OFFICIAL spreadsheet
   gives distinct no-change text to instead of the shared fallback. Rows 9
   and 10 (Equal Division of Labor) share one no-change case: unlike the
   three rows above, this row never checks a villager's existing state
   before reassigning, so "no change" only means no eligible villager was
   found at all (an empty or all-Golden-Child village), not "already
   correct". */
static const char *vv1_tech_no_change_text(int row) {
    switch (row) {
    case 6: return "Everyone already likes running, or has full Likes slots. No tech points have been deducted.";
    case 7: return "Everyone has already mastered their skills. No tech points have been deducted.";
    case 8: return "Everyone is already exactly 18. No tech points have been deducted.";
    case 9:
    case 10: return "No villagers were eligible. No tech points have been deducted.";
    default: return "No changes were needed. No tech points have been deducted.";
    }
}

/* No-change wording for the Villager Details screen's rows. Set Age to 18
   (row 3) happens to already use the shared fallback text verbatim per the
   spreadsheet, so only rows 0/1/2/4 need their own case. */
static const char *vv1_detail_no_change_text(int row) {
    switch (row) {
    case 0: return "This villager is already full of youth. No tech points have been deducted.";
    case 1: return "This villager is already fully mastered. No tech points have been deducted.";
    case 2: return "This villager already likes Running. No tech points have been deducted.";
    case 4: return "The appearance is unchanged. No tech points have been deducted.";
    default: return "No changes were needed. No tech points have been deducted.";
    }
}

enum {
    VV1_ROWMSG_SUCCESS = 0,
    VV1_ROWMSG_NO_CHANGE = 1,
    VV1_ROWMSG_NO_SLOT = 2,
    VV1_ROWMSG_REMOVED = 3,
    VV1_ROWMSG_POPULATION_FULL = 4,
    VV1_ROWMSG_NO_SLOT_DISLIKE_REMOVED = 5,
    VV1_ROWMSG_IS_GOLDEN_CHILD = 6
};

/* Generic result box for every Tech/Details row whose wording is either a
   plain "<Upgrade> completed." success line or one of a small set of
   fixed no-change/removed/blocked lines -- everything in the OFFICIAL
   Origins Upgrade Prompts spreadsheet that isn't a counted multi-line
   result (those keep their own dedicated export above: Cure, Grant
   Running to All, Grant Full Mastery to All). Replaces what used to be
   five separate ASM string-table entries (purchase_complete/removed/
   no_change/event_queued/running_unavailable) plus the now-removed
   ShowOriginsAgeResult export -- moving the text here costs the tight
   .shr string cave nothing and only a few bytes of code per call site. */
__declspec(dllexport) int __stdcall ShowOriginsRowMessage(
    int is_detail,
    int row,
    int status
) {
    char message[192];
    const char *name = is_detail ? vv1_detail_row_name(row) : vv1_tech_row_name(row);
    switch (status) {
    case VV1_ROWMSG_NO_CHANGE:
        lstrcpyA(
            message,
            is_detail ? vv1_detail_no_change_text(row) : vv1_tech_no_change_text(row)
        );
        break;
    case VV1_ROWMSG_NO_SLOT:
        lstrcpyA(message, "This villager already has full Likes slots. Running can not be added.");
        break;
    case VV1_ROWMSG_NO_SLOT_DISLIKE_REMOVED:
        lstrcpyA(
            message,
            "This villager's Likes are full, so Running could not be added, "
            "but its Running dislike was removed. No tech points have been deducted."
        );
        break;
    case VV1_ROWMSG_REMOVED:
        wsprintfA(message, "%s was removed. No refund was issued.", name);
        break;
    case VV1_ROWMSG_POPULATION_FULL:
        lstrcpyA(message, "Village population is close to its maximum. The Barrel of Babies needs room for 3 children. No tech points have been deducted.");
        break;
    case VV1_ROWMSG_IS_GOLDEN_CHILD:
        lstrcpyA(message, "This villager is the Golden Child. No tech points have been deducted.");
        break;
    default:
        wsprintfA(message, "%s completed.", name);
        break;
    }
    MessageBoxA(
        GetForegroundWindow(),
        message,
        is_detail ? "Villager Upgrades" : "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}
