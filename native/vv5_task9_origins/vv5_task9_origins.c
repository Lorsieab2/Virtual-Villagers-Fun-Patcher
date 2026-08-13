#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static HINSTANCE module_instance;
static HWND origins_owner;

enum {
    IDD_ORIGINS_TECH = 201,
    IDD_ORIGINS_VILLAGER = 202,
    ID_BUY_FIRST = 1000,
    ID_BUY_LAST = 1005,
    ID_CHECK_FIRST = 1100,
    STATE_VILLAGER = 0x10000
};

enum {
    ACTION_YOUTH = 0,
    ACTION_MASTERY = 1,
    ACTION_RUNNING = 2,
    ACTION_AGE18 = 3,
    ACTION_HEAL = 4,
    ACTION_TECH_BASE = 16
};

enum {
    RESULT_SUCCESS = 0,
    RESULT_NO_CHANGE = 1,
    RESULT_INVALID = 2,
    RESULT_INSUFFICIENT = 3,
    RESULT_CANCELLED = 4,
    RESULT_RECHECK = 5,
    RESULT_RETAINED = 6,
    RESULT_CHARGE_UNKNOWN = 7,
    RESULT_NO_SLOT = 8,
    RESULT_INVALID_SKILL = 9,
    RESULT_UNAVAILABLE = 10,
    RESULT_REMOVED = 11,
    RESULT_PURCHASED = 12,
    RESULT_UNSUPPORTED_SICKNESS = 13
};

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        module_instance = instance;
        origins_owner = NULL;
    }
    return TRUE;
}

static HWND validate_same_process_window(HWND window) {
    DWORD process_id = 0;
    if (window == NULL || !IsWindow(window)) {
        return NULL;
    }
    if (GetWindowThreadProcessId(window, &process_id) == 0
        || process_id != GetCurrentProcessId()) {
        return NULL;
    }
    return window;
}

__declspec(dllexport) int __stdcall BeginOriginsOwner(void) {
    HWND candidate = validate_same_process_window(GetForegroundWindow());
    origins_owner = candidate;
    return candidate != NULL;
}

__declspec(dllexport) HWND __stdcall GetOriginsOwner(void) {
    HWND owner = validate_same_process_window(origins_owner);
    if (owner == NULL) {
        origins_owner = NULL;
    }
    return owner;
}

__declspec(dllexport) void __stdcall EndOriginsOwner(void) {
    origins_owner = NULL;
}

static INT_PTR CALLBACK upgrade_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        int villager_menu = (lparam & STATE_VILLAGER) != 0;
        int row_count = villager_menu ? 4 : 6;
        int row;
        for (row = 0; row < row_count; ++row) {
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
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
        return TRUE;
    }
    if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command >= ID_BUY_FIRST && command <= ID_BUY_LAST) {
            EndDialog(window, (INT_PTR)(command - ID_BUY_FIRST));
            return TRUE;
        }
        if (command == IDCANCEL) {
            EndDialog(window, -1);
            return TRUE;
        }
    }
    if (message == WM_CLOSE) {
        EndDialog(window, -1);
        return TRUE;
    }
    return FALSE;
}

__declspec(dllexport) int __stdcall ShowOriginsUpgradeMenuState(
    int villager_menu,
    int dialog_state
) {
    HWND owner = GetOriginsOwner();
    if (owner == NULL) {
        return -1;
    }
    if (villager_menu) {
        dialog_state |= STATE_VILLAGER;
    }
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(villager_menu ? IDD_ORIGINS_VILLAGER : IDD_ORIGINS_TECH),
        owner,
        upgrade_dialog,
        dialog_state
    );
}

static const char *action_name(unsigned int action) {
    switch (action) {
    case ACTION_YOUTH: return "Grant Youth";
    case ACTION_MASTERY: return "Full Mastery";
    case ACTION_RUNNING: return "Grant Running";
    case ACTION_AGE18: return "Set Age to 18";
    case ACTION_HEAL: return "Full Heal / Cure All";
    default: return "Origins upgrade";
    }
}

__declspec(dllexport) int __stdcall ConfirmVV5Task9Action(
    unsigned int action,
    unsigned int amount_a,
    unsigned int amount_b
) {
    HWND owner = GetOriginsOwner();
    char message[384];
    if (owner == NULL) {
        return 0;
    }
    if (action == ACTION_HEAL) {
        wsprintfA(
            message,
            "Full Heal / Cure All will clear sickness from %u Villagers and restore full health to %u Villagers for 30,000 tech points.\r\nPress OK to confirm, or Cancel.",
            amount_a,
            amount_b
        );
    } else {
        unsigned int price = action == ACTION_MASTERY
            ? 100000U
            : (action == ACTION_RUNNING ? 40000U : 50000U);
        wsprintfA(
            message,
            "%s for %u tech points?\r\nPress OK to confirm, or Cancel.",
            action_name(action),
            price
        );
    }
    return MessageBoxA(
        owner,
        message,
        action == ACTION_HEAL ? "Origins Upgrades" : "Villager Upgrades",
        MB_OKCANCEL | MB_ICONQUESTION
    ) == IDOK;
}

__declspec(dllexport) int __stdcall ShowVV5Task9Result(
    unsigned int action,
    unsigned int status,
    unsigned int amount_a,
    unsigned int amount_b
) {
    HWND owner = GetOriginsOwner();
    char message[512];
    const char *name = action_name(action);
    if (owner == NULL) {
        return 0;
    }
    switch (status) {
    case RESULT_SUCCESS:
        if (action == ACTION_HEAL) {
            wsprintfA(message, "Cleared sickness from %u Villagers and restored full health to %u Villagers.", amount_a, amount_b);
        } else {
            wsprintfA(message, "%s completed.", name);
        }
        break;
    case RESULT_NO_CHANGE:
        if (action == ACTION_RUNNING) {
            lstrcpyA(message, "This Villager already likes Running. All Dislikes were preserved.\r\nNo tech points have been deducted.");
        } else {
            wsprintfA(message, "%s is already complete.\r\nNo tech points have been deducted.", name);
        }
        break;
    case RESULT_INVALID:
        lstrcpyA(message, "No valid living Believer is selected.\r\nNo tech points have been deducted.");
        break;
    case RESULT_INSUFFICIENT:
        lstrcpyA(message, "Not enough tech points.\r\nNo tech points have been deducted.");
        break;
    case RESULT_CANCELLED:
        wsprintfA(message, "%s was canceled.\r\nNo tech points have been deducted.", name);
        break;
    case RESULT_RECHECK:
        lstrcpyA(message, "The selected Villager, village snapshot, or tech-point balance changed during confirmation.\r\nNo tech points have been deducted.");
        break;
    case RESULT_RETAINED:
        lstrcpyA(message, "The action could not be fully verified after native writes began. Earlier verified effects may remain.\r\nNo tech points have been deducted.");
        break;
    case RESULT_CHARGE_UNKNOWN:
        lstrcpyA(message, "The action effects were verified, but the final tech-point balance did not match the exact expected deduction. The charge outcome is unknown.");
        break;
    case RESULT_NO_SLOT:
        lstrcpyA(message, "This Villager has no empty Like slot. All Dislikes were preserved.\r\nNo tech points have been deducted.");
        break;
    case RESULT_INVALID_SKILL:
        lstrcpyA(message, "Full Mastery cannot be applied because a skill is NaN, infinite, negative, or outside 0..100.\r\nNo tech points have been deducted.");
        break;
    case RESULT_UNAVAILABLE:
        lstrcpyA(message, "This VV5 native action remains unavailable.\r\nNo tech points have been deducted.");
        break;
    case RESULT_REMOVED:
        lstrcpyA(message, "The point doubler was removed. No refund was issued.");
        break;
    case RESULT_PURCHASED:
        lstrcpyA(message, "The point doubler was purchased.");
        break;
    case RESULT_UNSUPPORTED_SICKNESS:
        lstrcpyA(message, "Full Heal / Cure All is unavailable because an eligible Villager has sickness type 12, whose additional native effects are not yet implemented.\r\nNo tech points have been deducted.");
        break;
    default:
        lstrcpyA(message, "The action stopped without a verified charge.");
        break;
    }
    MessageBoxA(
        owner,
        message,
        action == ACTION_HEAL || action >= ACTION_TECH_BASE
            ? "Origins Upgrades"
            : "Villager Upgrades",
        MB_OK | (status == RESULT_SUCCESS || status == RESULT_PURCHASED || status == RESULT_REMOVED
            ? MB_ICONINFORMATION : MB_ICONWARNING)
    );
    return 0;
}
