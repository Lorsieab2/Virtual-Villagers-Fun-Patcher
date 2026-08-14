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
        return TRUE;
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command >= ID_BUY_FIRST && command <= ID_BUY_LAST) {
            if (MessageBoxA(
                    window,
                    "This upgrade makes permanent changes to your village. "
                    "Do you still want to purchase this?",
                    "Confirm Purchase",
                    MB_YESNO | MB_ICONWARNING) == IDYES) {
                EndDialog(window, (INT_PTR)(command - ID_BUY_FIRST));
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
    if (villager_menu) {
        dialog_state |= STATE_VILLAGER;
    }
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(resource),
        GetForegroundWindow(),
        upgrade_dialog,
        dialog_state
    );
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

__declspec(dllexport) int __stdcall ShowOriginsVillageWideResult(
    int command,
    int full_like_skipped,
    int already_running_skipped,
    int removed_running_dislike
) {
    char message[128];
    if (command == 6) {
        wsprintfA(
            message,
            "Skipped over %d villagers. Reason: Already 3 likes.\r\nskipped over %d villagers. Reason: already likes running",
            full_like_skipped,
            already_running_skipped
        );
        if (removed_running_dislike > 0) {
            char removal[64];
            wsprintfA(
                removal,
                "\r\nRemoved running dislike from %d villagers",
                removed_running_dislike
            );
            lstrcatA(message, removal);
        }
        MessageBoxA(
            GetForegroundWindow(),
            message,
            "Origins Upgrades",
            MB_OK | MB_ICONINFORMATION
        );
    }
    return 0;
}

__declspec(dllexport) int __stdcall ShowOriginsVillageWideResult20(
    int command,
    unsigned int granted,
    unsigned int already_like,
    unsigned int full_like,
    unsigned int removed_dislike
) {
    char message[256];
    char line[96];
    if (command != 6) {
        return 0;
    }
    wsprintfA(message, "Granted Running to %u villagers", granted);
    wsprintfA(
        line,
        "\r\nSkipped over %u villagers. Reason: already likes running",
        already_like
    );
    lstrcatA(message, line);
    wsprintfA(
        line,
        "\r\nSkipped over %u villagers. Reason: all like slots are occupied",
        full_like
    );
    lstrcatA(message, line);
    wsprintfA(
        line,
        "\r\nRemoved running dislike from %u villagers",
        removed_dislike
    );
    lstrcatA(message, line);
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION
    );
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
        MB_OK | MB_ICONINFORMATION
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
    vv3_appearance_sex = sex ? 1 : 0;
    vv3_appearance_old = age >= 1100 ? 1 : 0;
    vv3_appearance_head = (head && *head >= 0 && *head < VV3_HEAD_COUNT) ? *head : 0;
    vv3_appearance_body = (body && *body >= 0 && *body < VV3_BODY_COUNT) ? *body : 0;

    result = DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_VV3_APPEARANCE),
        GetForegroundWindow(),
        vv3_appearance_dialog,
        0
    );
    if (result == 1) {
        if (head) {
            *head = vv3_appearance_head;
        }
        if (body) {
            *body = vv3_appearance_body;
        }
        return 1;
    }
    return 0;
}
