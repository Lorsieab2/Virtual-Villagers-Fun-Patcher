#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static HINSTANCE module_instance;
static HWND origins_owner;

enum {
    IDD_ORIGINS_TECH = 201,
    IDD_ORIGINS_VILLAGER = 202,
    ID_BUY_FIRST = 1000,
    ID_BUY_LAST = 1009,
    ID_CHECK_FIRST = 1100,
    STATE_VILLAGER = 0x10000
};

enum {
    ACTION_YOUTH = 0,
    ACTION_MASTERY = 1,
    ACTION_RUNNING = 2,
    ACTION_AGE18 = 3,
    ACTION_HEAL = 4,
    ACTION_APPEARANCE = 5,
    ACTION_TECH_BASE = 16,
    ACTION_COMPLETE_COLLECTIONS = 16,
    ACTION_RESET_COLLECTIONS = 17,
    ACTION_TECH_DOUBLER = 18,
    ACTION_FOOD_DOUBLER = 19,
    ACTION_GRANT_RUNNING_ALL = 20,
    ACTION_GRANT_MASTERY_ALL = 21
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

/* ---------- VV5 Change Appearance chooser (VV2-style) ----------
   Owner-drawn modal picker showing the selected villager's head and body
   sprites cropped from the stock game art (embedded BMP strips: male/female x
   young/old heads, male/female bodies). It reports only the chosen head/body
   indices back to the caller through the head/body pointers; the native task9
   handler owns the believer gate, the 5,000-tech charge, and the record
   writes, so this DLL never touches save data. Head catalog is 30 (0..29),
   body/outfit catalog is 29 (0..28); young/old is a head-atlas swap. */
#define IDD_APPEARANCE   203
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
#define APPEARANCE_HEAD_COUNT 30
#define APPEARANCE_BODY_COUNT 29
#define APPEARANCE_CELL_W 40
#define APPEARANCE_CELL_H 65

static int appearance_sex;   /* 0 = male, 1 = female */
static int appearance_old;   /* 0 = young head atlas, 1 = old head atlas */
static int appearance_head;
static int appearance_body;

static int appearance_head_bitmap(void) {
    if (appearance_sex) {
        return appearance_old ? IDB_HEAD_F_OLD : IDB_HEAD_F_YOUNG;
    }
    return appearance_old ? IDB_HEAD_M_OLD : IDB_HEAD_M_YOUNG;
}

static int appearance_body_bitmap(void) {
    return appearance_sex ? IDB_BODY_F : IDB_BODY_M;
}

static void appearance_draw(DRAWITEMSTRUCT *item, int bitmap_id, int index) {
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

    scale_x = (double)width / APPEARANCE_CELL_W;
    scale_y = (double)height / APPEARANCE_CELL_H;
    scale = scale_x < scale_y ? scale_x : scale_y;
    draw_w = (int)(APPEARANCE_CELL_W * scale);
    draw_h = (int)(APPEARANCE_CELL_H * scale);
    draw_x = rc.left + (width - draw_w) / 2;
    draw_y = rc.top + (height - draw_h) / 2;

    SetStretchBltMode(item->hDC, COLORONCOLOR);
    StretchBlt(
        item->hDC, draw_x, draw_y, draw_w, draw_h,
        source, index * APPEARANCE_CELL_W, 0, APPEARANCE_CELL_W, APPEARANCE_CELL_H,
        SRCCOPY
    );

    SelectObject(source, previous);
    DeleteDC(source);
    DeleteObject(bitmap);
}

static void appearance_repaint(HWND window, int control) {
    InvalidateRect(GetDlgItem(window, control), NULL, TRUE);
}

static INT_PTR CALLBACK appearance_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        DRAWITEMSTRUCT *item = (DRAWITEMSTRUCT *)lparam;
        if (item->CtlID == IDC_BODY_PREVIEW) {
            appearance_draw(item, appearance_body_bitmap(), appearance_body);
            return TRUE;
        }
        if (item->CtlID == IDC_HEAD_PREVIEW) {
            appearance_draw(item, appearance_head_bitmap(), appearance_head);
            return TRUE;
        }
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command == IDC_BODY_PREV) {
            appearance_body = (appearance_body + APPEARANCE_BODY_COUNT - 1) % APPEARANCE_BODY_COUNT;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_BODY_NEXT) {
            appearance_body = (appearance_body + 1) % APPEARANCE_BODY_COUNT;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_PREV) {
            appearance_head = (appearance_head + APPEARANCE_HEAD_COUNT - 1) % APPEARANCE_HEAD_COUNT;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_NEXT) {
            appearance_head = (appearance_head + 1) % APPEARANCE_HEAD_COUNT;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
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

__declspec(dllexport) int __stdcall ShowAppearanceChooser(
    int sex,
    int age,
    int *head,
    int *body
) {
    INT_PTR result;
    appearance_sex = sex ? 1 : 0;
    appearance_old = age >= 1100 ? 1 : 0;
    appearance_head = (head && *head >= 0 && *head < APPEARANCE_HEAD_COUNT) ? *head : 0;
    appearance_body = (body && *body >= 0 && *body < APPEARANCE_BODY_COUNT) ? *body : 0;

    result = DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_APPEARANCE),
        GetForegroundWindow(),
        appearance_dialog,
        0
    );
    if (result == 1) {
        if (head) {
            *head = appearance_head;
        }
        if (body) {
            *body = appearance_body;
        }
        return 1;
    }
    return 0;
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
        int row_count = villager_menu ? 5 : 10;
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
    case ACTION_HEAL: return "Full Heal/Cure All Villagers";
    case ACTION_APPEARANCE: return "Change Appearance";
    case ACTION_COMPLETE_COLLECTIONS: return "Complete all Collections";
    case ACTION_RESET_COLLECTIONS: return "Reset all Collections";
    case ACTION_TECH_DOUBLER: return "Tech Point Doubler";
    case ACTION_FOOD_DOUBLER: return "Food Point Doubler";
    case ACTION_GRANT_RUNNING_ALL: return "Grant Running to All Villagers";
    case ACTION_GRANT_MASTERY_ALL: return "Grant Full Mastery to All Villagers";
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
    const char *title = (action == ACTION_HEAL || action >= ACTION_TECH_BASE)
        ? "Origins Upgrades"
        : "Villager Upgrades";
    if (owner == NULL) {
        return 0;
    }
    /* The two point doublers historically had no detailed confirmation; they go
       straight to the shared permanent-change warning below. Every other action
       shows its detailed prompt first, then the same warning as a second gate. */
    if (action != ACTION_TECH_DOUBLER && action != ACTION_FOOD_DOUBLER) {
        if (action == ACTION_HEAL) {
            wsprintfA(
                message,
                "Full Heal/Cure All Villagers will clear sickness from %u Villagers and restore full health to %u Villagers for 30,000 tech points.\r\nPress OK to confirm, or Cancel.",
                amount_a,
                amount_b
            );
        } else {
            unsigned int price;
            switch (action) {
            case ACTION_MASTERY: price = 100000U; break;
            case ACTION_RUNNING: price = 40000U; break;
            case ACTION_COMPLETE_COLLECTIONS:
            case ACTION_RESET_COLLECTIONS: price = 1000000U; break;
            case ACTION_GRANT_RUNNING_ALL: price = 150000U; break;
            case ACTION_GRANT_MASTERY_ALL: price = 300000U; break;
            default: price = 50000U; break;
            }
            wsprintfA(
                message,
                "%s for %u tech points?\r\nPress OK to confirm, or Cancel.",
                action_name(action),
                price
            );
        }
        if (MessageBoxA(owner, message, title, MB_OKCANCEL | MB_ICONQUESTION) != IDOK) {
            return 0;
        }
    }
    /* Shared final gate for every upgrade (tech-screen and details-screen). */
    return MessageBoxA(
        owner,
        "This upgrade makes permanent changes to your village. Do you still want to purchase this?",
        title,
        MB_YESNO | MB_ICONWARNING
    ) == IDYES;
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
            wsprintfA(message, "Cured sickness from %u villagers.\r\n\r\nRestored %u villagers to full health.", amount_a, amount_b);
        } else if (action == ACTION_COMPLETE_COLLECTIONS) {
            lstrcpyA(message, "All collections are complete. Every collectible was added and the collection goals updated accordingly.");
        } else if (action == ACTION_RESET_COLLECTIONS) {
            lstrcpyA(message, "All collections were reset. Every collectible was cleared and the collection goals were marked incomplete again.\r\n\r\nNote: game-wide totals and any one-time rewards from completing the collections are not reversed.");
        } else if (action == ACTION_GRANT_RUNNING_ALL) {
            wsprintfA(
                message,
                "%u villagers already like running; skipped over.\r\n\r\n"
                "%u villagers already have 3 likes; skipped over.\r\n\r\n"
                "Granted Running to %u villagers.\r\n\r\n"
                "Removed Running Dislike from %u villagers.",
                amount_a >> 16, amount_a & 0xFFFF, amount_b >> 16, amount_b & 0xFFFF
            );
        } else if (action == ACTION_GRANT_MASTERY_ALL) {
            wsprintfA(
                message,
                "Granted Full Mastery to %u Villagers.\r\n\r\n"
                "%u villagers are already Fully Mastered. Skipped over.",
                amount_a, amount_b
            );
        } else {
            wsprintfA(message, "%s completed.", name);
        }
        break;
    case RESULT_NO_CHANGE:
        if (action == ACTION_RUNNING) {
            lstrcpyA(message, "This Villager already likes Running. All Dislikes were preserved.\r\nNo tech points have been deducted.");
        } else if (action == ACTION_HEAL) {
            lstrcpyA(message, "Everyone is at full health already. No villagers are sick. No tech points have been deducted.");
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
