#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static HINSTANCE module_instance;

enum {
    IDD_ORIGINS_TECH = 201,
    IDD_ORIGINS_VILLAGER = 202,
    IDD_ORIGINS_FULL_MASTERY = 203,
    ID_BUY_FIRST = 1000,
    ID_BUY_LAST = 1010,
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
    "Set All Villagers to 18", "Complete All Collections",
    "Reset All Collections"
};
static const char *const tech_costs[] = {
    "50,000", "30,000", "75,000", "500,000", "500,000", "30,000",
    "1,000,000", "1,000,000", "1,000,000", "1,000,000", "1,000,000"
};
static const char *const detail_names[] = {
    "Grant Youth", "Grant Full Mastery", "Grant Running", "Set Age to 18",
    "Change Appearance"
};
static const char *const detail_costs[] = {
    "50,000", "100,000", "40,000", "50,000", "5,000"
};

/* Set at WM_INITDIALOG so WM_COMMAND knows whether this is the Tech (0) or
   Villager Details (1) menu.  The menus are modal and shown one at a time. */
static int s_villager_menu;

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        module_instance = instance;
    }
    return TRUE;
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

/* State saved between begin/end so we restore the game window's exact
   borderless-fullscreen style and bounds.  The upgrade menus are modal and
   shown one at a time. */
static HWND s_fs_owner;
static LONG s_fs_style;
static LONG s_fs_exstyle;
static RECT s_fs_rect;
static int s_fs_windowized;

/* Make the upgrade menus usable in fullscreen, the way the player-confirmed VV
   fullscreen fixes do -- leave fullscreen while the menu is up, restore it
   after -- but derived for VV3's own architecture.  VV3's "fullscreen" is a
   plain Win32 borderless window covering the monitor: it never calls
   SDL_SetWindowFullscreen (a dead import) and never changes the display mode
   (ChangeDisplaySettings is not imported), and its in-game Fullscreen setting
   toggles exactly this window state.  So we reproduce that toggle in Win32: for
   the lifetime of the modal dialog, convert the game window to a normal titled,
   non-topmost window centered on the monitor (a mode the game already supports,
   ldw.ini FullScreen=0), then restore its saved style and full-monitor bounds.
   The game's own WndProc runs inside the modal's message loop, so it re-renders
   windowed and the dialog is fully visible; we touch only the Win32 window,
   never any engine or SDL state.  Only acts when the window actually covers the
   monitor, so a windowed game is left alone.  Returns the game window (or NULL)
   for end_modal_over_game to restore. */
static HWND begin_modal_over_game(void) {
    HWND owner = GetForegroundWindow();
    DWORD pid = 0;
    HMONITOR monitor;
    MONITORINFO mi;
    RECT rc;
    int work_w, work_h, win_w, win_h, win_x, win_y;

    s_fs_windowized = 0;
    s_fs_owner = NULL;
    if (owner == NULL) {
        return NULL;
    }
    GetWindowThreadProcessId(owner, &pid);
    if (pid != GetCurrentProcessId()) {
        return NULL;
    }
    monitor = MonitorFromWindow(owner, MONITOR_DEFAULTTONEAREST);
    mi.cbSize = sizeof(mi);
    if (!GetMonitorInfoA(monitor, &mi)) {
        return owner;
    }
    GetWindowRect(owner, &rc);
    /* Only intervene when the game window covers (or exceeds) the whole monitor,
       i.e. it is in borderless-fullscreen.  A windowed game needs nothing. */
    if (rc.left > mi.rcMonitor.left || rc.top > mi.rcMonitor.top
        || rc.right < mi.rcMonitor.right || rc.bottom < mi.rcMonitor.bottom) {
        return owner;
    }

    s_fs_owner = owner;
    s_fs_style = GetWindowLongA(owner, GWL_STYLE);
    s_fs_exstyle = GetWindowLongA(owner, GWL_EXSTYLE);
    s_fs_rect = rc;
    s_fs_windowized = 1;

    /* Windowed size: 70% of the monitor work area, centered. */
    work_w = mi.rcWork.right - mi.rcWork.left;
    work_h = mi.rcWork.bottom - mi.rcWork.top;
    win_w = work_w * 7 / 10;
    win_h = work_h * 7 / 10;
    win_x = mi.rcWork.left + (work_w - win_w) / 2;
    win_y = mi.rcWork.top + (work_h - win_h) / 2;

    SetWindowLongA(owner, GWL_STYLE,
        (s_fs_style & ~(LONG)WS_POPUP) | WS_OVERLAPPEDWINDOW | WS_VISIBLE);
    SetWindowLongA(owner, GWL_EXSTYLE, s_fs_exstyle & ~(LONG)WS_EX_TOPMOST);
    SetWindowPos(owner, HWND_NOTOPMOST, win_x, win_y, win_w, win_h,
                 SWP_FRAMECHANGED | SWP_NOACTIVATE);
    return owner;
}

static void end_modal_over_game(HWND owner) {
    HWND z_order;
    if (!s_fs_windowized || owner == NULL || owner != s_fs_owner) {
        return;
    }
    z_order = (s_fs_exstyle & WS_EX_TOPMOST) ? HWND_TOPMOST : HWND_NOTOPMOST;
    SetWindowLongA(owner, GWL_STYLE, s_fs_style);
    SetWindowLongA(owner, GWL_EXSTYLE, s_fs_exstyle);
    SetWindowPos(owner, z_order,
                 s_fs_rect.left, s_fs_rect.top,
                 s_fs_rect.right - s_fs_rect.left,
                 s_fs_rect.bottom - s_fs_rect.top,
                 SWP_FRAMECHANGED | SWP_NOACTIVATE);
    s_fs_windowized = 0;
    s_fs_owner = NULL;
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
            char prompt[256];
            wsprintfA(
                prompt,
                "Do you want to buy %s for %s tech points?\r\n"
                "Press OK to confirm, or Cancel.",
                name, cost);
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
    HWND owner;
    int result;
    if (villager_menu) {
        dialog_state |= STATE_VILLAGER;
    }
    owner = begin_modal_over_game();
    result = (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(resource),
        owner,
        upgrade_dialog,
        dialog_state
    );
    end_modal_over_game(owner);
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
            lstrcpyA(message, "Everyone is already 18. No tech points have been deducted.");
        } else {
            wsprintfA(message, "Set %u %s to Age 18.",
                      vw_granted, villagers_word(vw_granted));
            wsprintfA(line, "\r\n\r\nSkipped %u %s: already 18.",
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
#define VV3_APPEARANCE_CELL_W 40
#define VV3_APPEARANCE_CELL_H 65
#define VV3_HEAD_COUNT 30
#define VV3_BODY_COUNT 29

static int vv3_appearance_sex;
static int vv3_appearance_old;
static int vv3_appearance_head;
static int vv3_appearance_body;

static int vv3_appearance_head_bitmap(void) {
    if (vv3_appearance_sex) {
        return vv3_appearance_old ? IDB_HEAD_F_OLD : IDB_HEAD_F_YOUNG;
    }
    return vv3_appearance_old ? IDB_HEAD_M_OLD : IDB_HEAD_M_YOUNG;
}

static int vv3_appearance_body_bitmap(void) {
    return vv3_appearance_sex ? IDB_BODY_F : IDB_BODY_M;
}

static void vv3_appearance_draw(DRAWITEMSTRUCT *item, int bitmap_id, int index) {
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

    scale_x = (double)width / VV3_APPEARANCE_CELL_W;
    scale_y = (double)height / VV3_APPEARANCE_CELL_H;
    scale = scale_x < scale_y ? scale_x : scale_y;
    draw_w = (int)(VV3_APPEARANCE_CELL_W * scale);
    draw_h = (int)(VV3_APPEARANCE_CELL_H * scale);
    draw_x = rc.left + (width - draw_w) / 2;
    draw_y = rc.top + (height - draw_h) / 2;

    SetStretchBltMode(item->hDC, COLORONCOLOR);
    StretchBlt(
        item->hDC, draw_x, draw_y, draw_w, draw_h,
        source, index * VV3_APPEARANCE_CELL_W, 0,
        VV3_APPEARANCE_CELL_W, VV3_APPEARANCE_CELL_H, SRCCOPY
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
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        DRAWITEMSTRUCT *item = (DRAWITEMSTRUCT *)lparam;
        if (item->CtlID == IDC_BODY_PREVIEW) {
            vv3_appearance_draw(item, vv3_appearance_body_bitmap(), vv3_appearance_body);
            return TRUE;
        }
        if (item->CtlID == IDC_HEAD_PREVIEW) {
            vv3_appearance_draw(item, vv3_appearance_head_bitmap(), vv3_appearance_head);
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
    int *body
) {
    INT_PTR result;
    HWND owner;
    int orig_head;
    int orig_body;
    vv3_appearance_sex = sex ? 1 : 0;
    vv3_appearance_old = age >= 1100 ? 1 : 0;
    vv3_appearance_head = (head && *head >= 0 && *head < VV3_HEAD_COUNT) ? *head : 0;
    vv3_appearance_body = (body && *body >= 0 && *body < VV3_BODY_COUNT) ? *body : 0;
    orig_head = vv3_appearance_head;
    orig_body = vv3_appearance_body;

    owner = begin_modal_over_game();
    result = DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_VV3_APPEARANCE),
        owner,
        vv3_appearance_dialog,
        0
    );
    end_modal_over_game(owner);

    /* Cancel / close: no change, no charge, no message. */
    if (result != 1) {
        return 0;
    }
    /* OK with nothing changed: report it and do not charge. */
    if (vv3_appearance_head == orig_head && vv3_appearance_body == orig_body) {
        MessageBoxA(GetForegroundWindow(),
            "The appearance is unchanged. No tech points have been deducted.",
            "Villager Upgrades",
            MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    /* The head field is hereditary, so changing it warns first; Cancel backs
       out with no write and no charge. */
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
    return 1;
}
